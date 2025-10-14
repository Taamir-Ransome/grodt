"""
Trade Exit Service.

This module provides functionality for managing trade exits through bracket orders,
including Take Profit (TP) and Stop Loss (SL) orders based on ATR and risk/reward ratios.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from grodtd.connectors.robinhood import Order
from grodtd.execution.engine import ExecutionEngine
from grodtd.risk.manager import RiskManager, Position


@dataclass
class BracketOrder:
    """Represents a bracket order with Take Profit and Stop Loss."""
    entry_order_id: str
    take_profit_order: Optional[Order] = None
    stop_loss_order: Optional[Order] = None
    symbol: str = ""
    quantity: float = 0.0
    entry_price: float = 0.0
    take_profit_price: float = 0.0
    stop_loss_price: float = 0.0
    risk_reward_ratio: float = 1.5
    created_at: datetime = None
    status: str = "pending"  # pending, active, filled, cancelled


@dataclass
class TradeExitResult:
    """Result of trade exit processing."""
    success: bool
    bracket_order_id: str
    take_profit_placed: bool
    stop_loss_placed: bool
    error_message: Optional[str] = None
    processing_time: float = 0.0


class TradeExitService:
    """
    Service for managing trade exits through bracket orders.
    
    This service handles:
    1. Take Profit order creation based on risk/reward ratios
    2. Stop Loss order creation based on ATR calculations
    3. Bracket order management and OCO emulation
    4. Integration with execution engine and risk management
    """

    def __init__(
        self,
        execution_engine: ExecutionEngine,
        risk_manager: RiskManager,
        config: Dict[str, Any]
    ):
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.config = config
        
        # Bracket order tracking
        self.active_brackets: Dict[str, BracketOrder] = {}
        self.bracket_callbacks: List[Any] = []
        
        # Configuration
        self.default_risk_reward_ratio = config.get('risk_reward_ratio', 1.5)
        self.atr_multiplier = config.get('atr_multiplier', 2.0)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized TradeExitService")

    async def create_bracket_order(
        self,
        entry_order: Order,
        entry_price: float,
        atr: float,
        risk_reward_ratio: Optional[float] = None
    ) -> TradeExitResult:
        """
        Create a bracket order with Take Profit and Stop Loss.
        
        Args:
            entry_order: The filled entry order
            entry_price: Actual entry price
            atr: Average True Range at entry
            risk_reward_ratio: Risk/reward ratio (uses default if None)
            
        Returns:
            TradeExitResult with creation details
        """
        start_time = datetime.now()
        
        try:
            # Use provided ratio or default
            rr_ratio = risk_reward_ratio or self.default_risk_reward_ratio
            
            # Calculate stop loss and take profit prices
            stop_loss_price, take_profit_price = self._calculate_exit_prices(
                entry_price, atr, rr_ratio, entry_order.side
            )
            
            # Create bracket order
            bracket = BracketOrder(
                entry_order_id=entry_order.id,
                symbol=entry_order.symbol,
                quantity=entry_order.filled_quantity,
                entry_price=entry_price,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
                risk_reward_ratio=rr_ratio,
                created_at=datetime.now()
            )
            
            # Create Take Profit order
            tp_order = await self._create_take_profit_order(bracket)
            if tp_order:
                bracket.take_profit_order = tp_order
                self.logger.info(f"Created TP order: {tp_order.id} @ {take_profit_price}")
            
            # Create Stop Loss order
            sl_order = await self._create_stop_loss_order(bracket)
            if sl_order:
                bracket.stop_loss_order = sl_order
                self.logger.info(f"Created SL order: {sl_order.id} @ {stop_loss_price}")
            
            # Track bracket order
            bracket_id = f"bracket_{entry_order.id}"
            self.active_brackets[bracket_id] = bracket
            
            # Update position with exit levels
            self._update_position_exit_levels(entry_order.symbol, stop_loss_price, take_profit_price)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Check if both orders were placed successfully
            success = tp_order is not None and sl_order is not None
            error_message = None
            
            if not success:
                if tp_order is None and sl_order is None:
                    error_message = "Both TP and SL orders failed to place"
                elif tp_order is None:
                    error_message = "Take Profit order failed to place"
                elif sl_order is None:
                    error_message = "Stop Loss order failed to place"
            
            return TradeExitResult(
                success=success,
                bracket_order_id=bracket_id,
                take_profit_placed=tp_order is not None,
                stop_loss_placed=sl_order is not None,
                error_message=error_message,
                processing_time=processing_time
            )
            
        except Exception as e:
            error_msg = f"Failed to create bracket order: {e}"
            self.logger.error(error_msg)
            
            return TradeExitResult(
                success=False,
                bracket_order_id="",
                take_profit_placed=False,
                stop_loss_placed=False,
                error_message=error_msg,
                processing_time=(datetime.now() - start_time).total_seconds()
            )

    def _calculate_exit_prices(
        self,
        entry_price: float,
        atr: float,
        risk_reward_ratio: float,
        side: str
    ) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit prices.
        
        Args:
            entry_price: Entry price
            atr: Average True Range
            risk_reward_ratio: Risk/reward ratio
            side: Order side ('buy' or 'sell')
            
        Returns:
            Tuple of (stop_loss_price, take_profit_price)
        """
        # Calculate stop distance based on ATR
        stop_distance = atr * self.atr_multiplier
        
        if side == "buy":
            # Long position
            stop_loss_price = entry_price - stop_distance
            # Take profit = entry + (stop_distance * risk_reward_ratio)
            take_profit_price = entry_price + (stop_distance * risk_reward_ratio)
        else:
            # Short position
            stop_loss_price = entry_price + stop_distance
            # Take profit = entry - (stop_distance * risk_reward_ratio)
            take_profit_price = entry_price - (stop_distance * risk_reward_ratio)
        
        self.logger.info(
            f"Calculated exit prices for {side} @ {entry_price}: "
            f"SL={stop_loss_price:.4f}, TP={take_profit_price:.4f} "
            f"(ATR={atr:.4f}, RR={risk_reward_ratio})"
        )
        
        return stop_loss_price, take_profit_price

    async def _create_take_profit_order(self, bracket: BracketOrder) -> Optional[Order]:
        """Create Take Profit order."""
        try:
            # Determine order side (opposite of entry)
            tp_side = "sell" if bracket.quantity > 0 else "buy"
            
            # Create limit order for take profit
            tp_order = Order(
                id=f"tp_{bracket.entry_order_id}",
                symbol=bracket.symbol,
                side=tp_side,
                quantity=abs(bracket.quantity),
                price=bracket.take_profit_price,
                order_type="limit",
                status="pending",
                created_at=datetime.now()
            )
            
            # Submit to execution engine
            result = await self.execution_engine.submit_order(tp_order)
            
            if result.status.value == "acknowledged":
                return tp_order
            else:
                self.logger.error(f"Failed to place TP order: {result.error_message}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating TP order: {e}")
            return None

    async def _create_stop_loss_order(self, bracket: BracketOrder) -> Optional[Order]:
        """Create Stop Loss order."""
        try:
            # Determine order side (opposite of entry)
            sl_side = "sell" if bracket.quantity > 0 else "buy"
            
            # Create stop order for stop loss
            sl_order = Order(
                id=f"sl_{bracket.entry_order_id}",
                symbol=bracket.symbol,
                side=sl_side,
                quantity=abs(bracket.quantity),
                price=bracket.stop_loss_price,
                order_type="stop",
                status="pending",
                created_at=datetime.now()
            )
            
            # Submit to execution engine
            result = await self.execution_engine.submit_order(sl_order)
            
            if result.status.value == "acknowledged":
                return sl_order
            else:
                self.logger.error(f"Failed to place SL order: {result.error_message}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating SL order: {e}")
            return None

    def _update_position_exit_levels(
        self,
        symbol: str,
        stop_loss_price: float,
        take_profit_price: float
    ):
        """Update position with exit levels in risk manager."""
        if symbol in self.risk_manager.positions:
            position = self.risk_manager.positions[symbol]
            position.stop_loss = stop_loss_price
            position.take_profit = take_profit_price
            
            self.logger.info(
                f"Updated position {symbol} exit levels: "
                f"SL={stop_loss_price:.4f}, TP={take_profit_price:.4f}"
            )

    async def handle_bracket_fill(self, order_id: str, fill_data: Dict[str, Any]):
        """
        Handle when one of the bracket orders fills.
        
        Args:
            order_id: ID of the filled order
            fill_data: Fill information
        """
        # Find the bracket order
        bracket = None
        bracket_id = None
        for bid, b in self.active_brackets.items():
            if (b.take_profit_order and b.take_profit_order.id == order_id) or \
               (b.stop_loss_order and b.stop_loss_order.id == order_id):
                bracket = b
                bracket_id = bid
                break
        
        if not bracket:
            self.logger.warning(f"No bracket found for filled order {order_id}")
            return
        
        # Cancel the other order (OCO behavior)
        await self._cancel_other_bracket_order(bracket, order_id)
        
        # Update bracket status
        bracket.status = "filled"
        
        # Update position in risk manager
        exit_price = fill_data.get('average_fill_price', 0.0)
        realized_pnl = self.risk_manager.close_position(bracket.symbol, exit_price)
        
        # Remove from active brackets
        if bracket_id:
            del self.active_brackets[bracket_id]
        
        self.logger.info(
            f"Bracket order filled: {order_id} @ {exit_price}, "
            f"Realized PnL: ${realized_pnl:.2f}"
        )
        
        # Trigger callbacks
        await self._trigger_bracket_callbacks("bracket_filled", bracket, fill_data)

    async def _cancel_other_bracket_order(self, bracket: BracketOrder, filled_order_id: str):
        """Cancel the other bracket order (OCO behavior)."""
        try:
            if bracket.take_profit_order and bracket.take_profit_order.id != filled_order_id:
                await self.execution_engine.cancel_order(bracket.take_profit_order.id)
                self.logger.info(f"Cancelled TP order: {bracket.take_profit_order.id}")
            
            if bracket.stop_loss_order and bracket.stop_loss_order.id != filled_order_id:
                await self.execution_engine.cancel_order(bracket.stop_loss_order.id)
                self.logger.info(f"Cancelled SL order: {bracket.stop_loss_order.id}")
                
        except Exception as e:
            self.logger.error(f"Error cancelling other bracket order: {e}")

    async def cancel_bracket_order(self, bracket_id: str) -> bool:
        """
        Cancel a bracket order and all its components.
        
        Args:
            bracket_id: ID of the bracket order
            
        Returns:
            True if cancellation was successful
        """
        if bracket_id not in self.active_brackets:
            self.logger.warning(f"Bracket order {bracket_id} not found")
            return False
        
        bracket = self.active_brackets[bracket_id]
        cancelled_count = 0
        
        try:
            # Cancel take profit order
            if bracket.take_profit_order:
                if await self.execution_engine.cancel_order(bracket.take_profit_order.id):
                    cancelled_count += 1
            
            # Cancel stop loss order
            if bracket.stop_loss_order:
                if await self.execution_engine.cancel_order(bracket.stop_loss_order.id):
                    cancelled_count += 1
            
            # Update bracket status
            bracket.status = "cancelled"
            
            # Remove from active brackets
            del self.active_brackets[bracket_id]
            
            self.logger.info(f"Cancelled bracket order {bracket_id} ({cancelled_count} orders)")
            return cancelled_count > 0
            
        except Exception as e:
            self.logger.error(f"Error cancelling bracket order {bracket_id}: {e}")
            return False

    def get_active_brackets(self) -> List[BracketOrder]:
        """Get list of active bracket orders."""
        return list(self.active_brackets.values())

    def get_bracket_summary(self) -> Dict[str, Any]:
        """Get summary of bracket orders."""
        return {
            "active_brackets": len(self.active_brackets),
            "brackets": [
                {
                    "id": bracket_id,
                    "symbol": bracket.symbol,
                    "quantity": bracket.quantity,
                    "entry_price": bracket.entry_price,
                    "take_profit_price": bracket.take_profit_price,
                    "stop_loss_price": bracket.stop_loss_price,
                    "risk_reward_ratio": bracket.risk_reward_ratio,
                    "status": bracket.status,
                    "created_at": bracket.created_at
                }
                for bracket_id, bracket in self.active_brackets.items()
            ]
        }

    async def _trigger_bracket_callbacks(self, event_type: str, bracket: BracketOrder, data: Dict[str, Any]):
        """Trigger bracket order callbacks."""
        for callback in self.bracket_callbacks:
            try:
                await callback(event_type, bracket, data)
            except Exception as e:
                self.logger.error(f"Error in bracket callback: {e}")

    def add_bracket_callback(self, callback):
        """Add a bracket order callback."""
        self.bracket_callbacks.append(callback)
        self.logger.info("Added bracket order callback")


# Factory function for creating trade exit service
def create_trade_exit_service(
    execution_engine: ExecutionEngine,
    risk_manager: RiskManager,
    config: Dict[str, Any]
) -> TradeExitService:
    """Create a new trade exit service."""
    return TradeExitService(execution_engine, risk_manager, config)
