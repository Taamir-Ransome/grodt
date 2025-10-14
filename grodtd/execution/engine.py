"""
Order execution engine.

This module handles order routing, OCO emulation, and execution monitoring
for the trading system.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

from grodtd.connectors.robinhood import Order, Quote


class OrderStatus(Enum):
    """Order status enumeration."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class ExecutionResult:
    """Result of order execution."""
    order_id: str
    status: OrderStatus
    filled_quantity: float = 0.0
    average_fill_price: Optional[float] = None
    execution_time: Optional[datetime] = None
    error_message: Optional[str] = None


class OrderStateMachine:
    """Manages order state transitions."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._transitions = {
            OrderStatus.NEW: [OrderStatus.ACKNOWLEDGED, OrderStatus.REJECTED],
            OrderStatus.ACKNOWLEDGED: [OrderStatus.PARTIAL_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED],
            OrderStatus.PARTIAL_FILLED: [OrderStatus.FILLED, OrderStatus.CANCELLED],
            OrderStatus.FILLED: [],  # Terminal state
            OrderStatus.CANCELLED: [],  # Terminal state
            OrderStatus.REJECTED: [],  # Terminal state
        }
    
    def can_transition(self, from_status: OrderStatus, to_status: OrderStatus) -> bool:
        """Check if a state transition is valid."""
        return to_status in self._transitions.get(from_status, [])
    
    def transition(self, current_status: OrderStatus, new_status: OrderStatus) -> OrderStatus:
        """Perform state transition if valid."""
        if self.can_transition(current_status, new_status):
            self.logger.debug(f"Order transition: {current_status.value} -> {new_status.value}")
            return new_status
        else:
            self.logger.warning(f"Invalid transition: {current_status.value} -> {new_status.value}")
            return current_status


class ExecutionEngine:
    """Handles order execution and monitoring."""
    
    def __init__(self, connector, risk_manager):
        self.connector = connector
        self.risk_manager = risk_manager
        self.state_machine = OrderStateMachine()
        self.active_orders: Dict[str, Order] = {}
        self.execution_callbacks: List[Callable] = []
        self.logger = logging.getLogger(__name__)
    
    async def submit_order(self, order: Order) -> ExecutionResult:
        """
        Submit a new order for execution.
        
        Args:
            order: Order to submit
        
        Returns:
            Execution result
        """
        self.logger.info(f"Submitting order: {order.symbol} {order.side} {order.quantity}")
        
        try:
            # Check risk limits before submission
            can_open, reason = self.risk_manager.can_open_position(order.symbol)
            if not can_open:
                return ExecutionResult(
                    order_id=order.id,
                    status=OrderStatus.REJECTED,
                    error_message=f"Risk check failed: {reason}"
                )
            
            # Submit order to connector
            order_id = await self.connector.place_order(order)
            order.id = order_id
            order.status = "submitted"
            
            # Track active order
            self.active_orders[order_id] = order
            
            # Start monitoring
            asyncio.create_task(self._monitor_order(order_id))
            
            return ExecutionResult(
                order_id=order_id,
                status=OrderStatus.ACKNOWLEDGED,
                execution_time=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to submit order {order.id}: {e}")
            return ExecutionResult(
                order_id=order.id,
                status=OrderStatus.REJECTED,
                error_message=str(e)
            )
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancellation was successful
        """
        if order_id not in self.active_orders:
            self.logger.warning(f"Order {order_id} not found in active orders")
            return False
        
        try:
            success = await self.connector.cancel_order(order_id)
            if success:
                self.active_orders[order_id].status = "cancelled"
                del self.active_orders[order_id]
                self.logger.info(f"Cancelled order {order_id}")
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def _monitor_order(self, order_id: str):
        """Monitor order execution status."""
        while order_id in self.active_orders:
            try:
                status = await self.connector.get_order_status(order_id)
                
                if status.get("status") == "filled":
                    await self._handle_order_fill(order_id, status)
                    break
                elif status.get("status") == "cancelled":
                    await self._handle_order_cancellation(order_id)
                    break
                elif status.get("status") == "rejected":
                    await self._handle_order_rejection(order_id, status)
                    break
                
                # Wait before next check
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error monitoring order {order_id}: {e}")
                break
    
    async def _handle_order_fill(self, order_id: str, fill_data: Dict[str, Any]):
        """Handle order fill event."""
        order = self.active_orders.get(order_id)
        if not order:
            return
        
        # Update order with fill information
        order.status = "filled"
        order.filled_quantity = fill_data.get("filled_quantity", order.quantity)
        order.average_fill_price = fill_data.get("average_fill_price")
        order.filled_at = datetime.now()
        
        # Create position in risk manager
        from grodtd.risk.manager import Position
        position = Position(
            symbol=order.symbol,
            quantity=order.filled_quantity,
            entry_price=order.average_fill_price or order.price,
            current_price=order.average_fill_price or order.price,
            created_at=datetime.now()
        )
        
        self.risk_manager.add_position(position)
        
        # Trigger callbacks
        await self._trigger_callbacks("order_filled", order)
        
        # Remove from active orders
        del self.active_orders[order_id]
        
        self.logger.info(f"Order {order_id} filled: {order.filled_quantity} @ {order.average_fill_price}")
    
    async def _handle_order_cancellation(self, order_id: str):
        """Handle order cancellation."""
        order = self.active_orders.get(order_id)
        if order:
            order.status = "cancelled"
            await self._trigger_callbacks("order_cancelled", order)
            del self.active_orders[order_id]
        
        self.logger.info(f"Order {order_id} was cancelled")
    
    async def _handle_order_rejection(self, order_id: str, rejection_data: Dict[str, Any]):
        """Handle order rejection."""
        order = self.active_orders.get(order_id)
        if order:
            order.status = "rejected"
            await self._trigger_callbacks("order_rejected", order)
            del self.active_orders[order_id]
        
        self.logger.warning(f"Order {order_id} was rejected: {rejection_data.get('reason', 'Unknown')}")
    
    async def _trigger_callbacks(self, event_type: str, order: Order):
        """Trigger execution callbacks."""
        for callback in self.execution_callbacks:
            try:
                await callback(event_type, order)
            except Exception as e:
                self.logger.error(f"Error in execution callback: {e}")
    
    def add_execution_callback(self, callback: Callable):
        """Add execution callback."""
        self.execution_callbacks.append(callback)
    
    def get_active_orders(self) -> List[Order]:
        """Get list of active orders."""
        return list(self.active_orders.values())
    
    def create_market_buy_order(self, symbol: str, quantity: float, price: float) -> Order:
        """
        Create a market buy order.
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            price: Current market price
            
        Returns:
            Order object
        """
        order_id = f"buy_{symbol}_{int(datetime.now().timestamp())}"
        
        return Order(
            id=order_id,
            symbol=symbol,
            side="buy",
            quantity=quantity,
            price=price,
            order_type="market",
            status="pending",
            created_at=datetime.now()
        )
    
    def create_market_sell_order(self, symbol: str, quantity: float, price: float) -> Order:
        """
        Create a market sell order.
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            price: Current market price
            
        Returns:
            Order object
        """
        order_id = f"sell_{symbol}_{int(datetime.now().timestamp())}"
        
        return Order(
            id=order_id,
            symbol=symbol,
            side="sell",
            quantity=quantity,
            price=price,
            order_type="market",
            status="pending",
            created_at=datetime.now()
        )
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        return {
            "active_orders": len(self.active_orders),
            "orders": [
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": order.quantity,
                    "status": order.status
                }
                for order in self.active_orders.values()
            ]
        }


# Factory function for creating execution engine
def create_execution_engine(connector, risk_manager) -> ExecutionEngine:
    """Create a new execution engine."""
    return ExecutionEngine(connector, risk_manager)
