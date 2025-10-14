# Bracket Orders and OCO Emulation Design

## Overview

Bracket orders consist of a Take Profit (TP) and Stop Loss (SL) order that are automatically placed after a position entry. The OCO (One-Cancels-Other) functionality ensures that when one order fills, the other is automatically cancelled.

## Bracket Order Architecture

### Core Classes

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List

class BracketOrderStatus(Enum):
    """Bracket order status enumeration."""
    PENDING = "pending"
    ACTIVE = "active"
    PARTIAL_FILLED = "partial_filled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"

@dataclass
class BracketOrder:
    """Represents a bracket order (TP + SL)."""
    id: str
    parent_order_id: str
    symbol: str
    quantity: float
    entry_price: float
    take_profit_price: float
    stop_loss_price: float
    risk_reward_ratio: float
    atr_value: float
    status: BracketOrderStatus
    created_at: datetime
    take_profit_order_id: Optional[str] = None
    stop_loss_order_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class BracketOrderManager:
    """Manages bracket order lifecycle and OCO emulation."""
    
    def __init__(self, execution_engine: ExecutionEngine):
        self.execution_engine = execution_engine
        self.active_brackets: Dict[str, BracketOrder] = {}
        self.bracket_callbacks: List[Callable] = []
        self.logger = logging.getLogger(__name__)
    
    async def create_bracket_order(
        self,
        parent_order: Order,
        atr_value: float,
        risk_reward_ratio: float
    ) -> BracketOrder:
        """Create a new bracket order."""
        
    async def place_bracket_orders(
        self,
        bracket_order: BracketOrder
    ) -> bool:
        """Place both TP and SL orders."""
        
    async def handle_order_fill(
        self,
        order_id: str,
        fill_data: Dict[str, Any]
    ) -> None:
        """Handle when one part of bracket order fills."""
        
    async def cancel_bracket_order(
        self,
        bracket_id: str
    ) -> bool:
        """Cancel a bracket order and its components."""
```

### OCO Emulation Logic

```python
class OCOEmulator:
    """Emulates One-Cancels-Other functionality."""
    
    def __init__(self, execution_engine: ExecutionEngine):
        self.execution_engine = execution_engine
        self.bracket_orders: Dict[str, BracketOrder] = {}
        self.logger = logging.getLogger(__name__)
    
    async def register_bracket_order(
        self,
        bracket_order: BracketOrder
    ) -> None:
        """Register a bracket order for OCO monitoring."""
        
    async def handle_tp_fill(
        self,
        bracket_order: BracketOrder,
        tp_order: Order
    ) -> None:
        """Handle take profit fill - cancel stop loss."""
        
    async def handle_sl_fill(
        self,
        bracket_order: BracketOrder,
        sl_order: Order
    ) -> None:
        """Handle stop loss fill - cancel take profit."""
        
    async def monitor_bracket_orders(self) -> None:
        """Monitor all active bracket orders."""
```

## Bracket Order Lifecycle

### 1. Creation Phase
```
Entry Order Fill → Calculate ATR → Calculate TP/SL → Create Bracket Order
```

### 2. Placement Phase
```
Create TP Order → Create SL Order → Register for OCO → Start Monitoring
```

### 3. Monitoring Phase
```
Monitor Order Status → Handle Fills → Cancel Opposite Order → Update Position
```

### 4. Completion Phase
```
One Order Fills → Cancel Other → Update Position → Cleanup
```

## OCO Emulation Implementation

### State Machine

```python
class BracketOrderStateMachine:
    """Manages bracket order state transitions."""
    
    def __init__(self):
        self._transitions = {
            BracketOrderStatus.PENDING: [BracketOrderStatus.ACTIVE, BracketOrderStatus.ERROR],
            BracketOrderStatus.ACTIVE: [BracketOrderStatus.PARTIAL_FILLED, BracketOrderStatus.COMPLETED, BracketOrderStatus.CANCELLED],
            BracketOrderStatus.PARTIAL_FILLED: [BracketOrderStatus.COMPLETED, BracketOrderStatus.CANCELLED],
            BracketOrderStatus.COMPLETED: [],  # Terminal state
            BracketOrderStatus.CANCELLED: [],  # Terminal state
            BracketOrderStatus.ERROR: [],     # Terminal state
        }
    
    def can_transition(self, from_status: BracketOrderStatus, to_status: BracketOrderStatus) -> bool:
        """Check if state transition is valid."""
        return to_status in self._transitions.get(from_status, [])
    
    def transition(self, current_status: BracketOrderStatus, new_status: BracketOrderStatus) -> BracketOrderStatus:
        """Perform state transition if valid."""
        if self.can_transition(current_status, new_status):
            return new_status
        else:
            self.logger.warning(f"Invalid transition: {current_status.value} -> {new_status.value}")
            return current_status
```

### OCO Logic Implementation

```python
async def handle_bracket_fill(
    self,
    bracket_order: BracketOrder,
    filled_order: Order
) -> None:
    """Handle when one part of bracket order fills."""
    
    if filled_order.id == bracket_order.take_profit_order_id:
        # Take profit filled - cancel stop loss
        await self._cancel_stop_loss(bracket_order)
        bracket_order.status = BracketOrderStatus.COMPLETED
        bracket_order.completed_at = datetime.now()
        
    elif filled_order.id == bracket_order.stop_loss_order_id:
        # Stop loss filled - cancel take profit
        await self._cancel_take_profit(bracket_order)
        bracket_order.status = BracketOrderStatus.COMPLETED
        bracket_order.completed_at = datetime.now()
    
    # Update position in risk manager
    await self._update_position_exit(bracket_order, filled_order)
    
    # Trigger callbacks
    await self._trigger_bracket_callbacks("bracket_completed", bracket_order)
```

## Error Handling

### Common Error Scenarios

1. **Order Placement Failures**
   - Retry with exponential backoff
   - Fallback to manual order placement
   - Log errors for monitoring

2. **OCO Emulation Failures**
   - Manual cancellation of remaining orders
   - Alert for manual intervention
   - Update position status

3. **Risk Limit Violations**
   - Reject bracket orders that exceed limits
   - Adjust quantities to fit limits
   - Log violations for analysis

### Error Recovery

```python
async def handle_bracket_error(
    self,
    bracket_order: BracketOrder,
    error: Exception
) -> None:
    """Handle bracket order errors."""
    
    bracket_order.status = BracketOrderStatus.ERROR
    bracket_order.error_message = str(error)
    
    # Cancel any active orders
    if bracket_order.take_profit_order_id:
        await self.execution_engine.cancel_order(bracket_order.take_profit_order_id)
    
    if bracket_order.stop_loss_order_id:
        await self.execution_engine.cancel_order(bracket_order.stop_loss_order_id)
    
    # Trigger error callbacks
    await self._trigger_bracket_callbacks("bracket_error", bracket_order)
```

## Performance Considerations

### Memory Management
- Limit active bracket orders
- Cleanup completed brackets
- Monitor memory usage

### Latency Optimization
- Async order placement
- Parallel order monitoring
- Efficient state updates

### Scalability
- Support multiple symbols
- Handle high-frequency trading
- Optimize database operations

## Configuration

```yaml
bracket_orders:
  max_active_brackets: 50
  bracket_timeout_seconds: 3600
  retry_attempts: 3
  retry_delay_seconds: 5
  monitoring_interval_seconds: 1
  cleanup_interval_seconds: 300
```

## Testing Strategy

### Unit Tests
- Bracket order creation
- OCO emulation logic
- State transitions
- Error handling

### Integration Tests
- End-to-end bracket lifecycle
- Execution engine integration
- Risk management integration
- Error recovery scenarios

### Performance Tests
- Bracket order creation latency
- OCO monitoring performance
- Memory usage with multiple brackets
- Concurrent bracket handling
