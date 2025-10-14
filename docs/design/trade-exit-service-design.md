# Trade Exit Service Design

## Overview

The TradeExitService is responsible for managing bracket orders (Take Profit and Stop Loss) that are automatically placed after a position is opened. It integrates with the existing execution engine to provide OCO (One-Cancels-Other) emulation and risk management.

## Architecture

### Core Components

1. **TradeExitService** - Main service class
2. **BracketOrderManager** - Manages bracket order lifecycle
3. **ATRCalculator** - Calculates ATR-based stop distances
4. **RiskRewardCalculator** - Calculates take profit levels
5. **OCOEmulator** - Emulates One-Cancels-Other functionality

### Class Design

```python
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

@dataclass
class TradeExitResult:
    """Result of trade exit processing."""
    success: bool
    bracket_orders_created: int
    errors: list[str]
    processing_time: float

class TradeExitService:
    """Main service for trade exit functionality."""
    
    def __init__(
        self,
        connector: RobinhoodConnector,
        risk_manager: RiskManager,
        execution_engine: ExecutionEngine,
        symbol: str,
        config: dict[str, Any]
    ):
        self.connector = connector
        self.risk_manager = risk_manager
        self.execution_engine = execution_engine
        self.symbol = symbol
        self.config = config
        
        # Initialize components
        self.bracket_manager = BracketOrderManager(execution_engine)
        self.atr_calculator = ATRCalculator()
        self.risk_reward_calculator = RiskRewardCalculator()
        self.oco_emulator = OCOEmulator(execution_engine)
        
        # Service state
        self.is_running = False
        self.active_brackets: Dict[str, BracketOrder] = {}
        self.exit_callbacks: List[Callable] = []
        
        self.logger = logging.getLogger(__name__)
```

### Key Methods

```python
async def create_bracket_order(
    self,
    parent_order: Order,
    atr_value: float,
    risk_reward_ratio: float
) -> TradeExitResult:
    """Create bracket order after position entry."""

async def calculate_stop_loss(
    self,
    entry_price: float,
    atr_value: float,
    side: str
) -> float:
    """Calculate stop loss price based on ATR."""

async def calculate_take_profit(
    self,
    entry_price: float,
    stop_loss_price: float,
    risk_reward_ratio: float,
    side: str
) -> float:
    """Calculate take profit price based on risk/reward ratio."""

async def handle_bracket_fill(
    self,
    bracket_order: BracketOrder,
    filled_order: Order
) -> None:
    """Handle when one part of bracket order fills."""

async def cancel_bracket_order(
    self,
    bracket_id: str
) -> bool:
    """Cancel a bracket order and its components."""
```

## Integration Points

### 1. Execution Engine Integration

- **Order Fill Callbacks**: Listen for entry order fills to trigger bracket creation
- **Order State Management**: Track bracket order states
- **OCO Emulation**: Implement One-Cancels-Other logic

### 2. Risk Management Integration

- **ATR Calculations**: Use risk manager for ATR-based stop distances
- **Position Tracking**: Update positions with stop/target levels
- **Risk Limits**: Validate bracket orders against risk limits

### 3. Configuration Integration

- **Risk/Reward Ratios**: Configurable ratios from strategy config
- **ATR Multipliers**: Use risk limits for ATR calculations
- **Order Types**: Support for different order types (market, limit, stop)

## Data Flow

1. **Entry Order Fill** → Trigger bracket creation
2. **ATR Calculation** → Calculate stop loss distance
3. **Risk/Reward Calculation** → Calculate take profit level
4. **Bracket Order Creation** → Create TP and SL orders
5. **OCO Monitoring** → Monitor for fills and cancellations
6. **Position Update** → Update risk manager with exit levels

## Error Handling

- **ATR Calculation Failures**: Fallback to fixed percentage stops
- **Order Placement Failures**: Retry with exponential backoff
- **OCO Emulation Failures**: Manual cancellation of remaining orders
- **Risk Limit Violations**: Reject bracket orders that exceed limits

## Configuration

```yaml
trade_exit:
  risk_reward_ratio: 1.5
  atr_multiplier: 2.0
  max_bracket_orders: 10
  bracket_timeout_seconds: 3600
  retry_attempts: 3
  retry_delay_seconds: 5
```

## Testing Strategy

### Unit Tests
- Bracket order creation and management
- ATR-based stop loss calculations
- Risk/reward ratio calculations
- OCO emulation logic

### Integration Tests
- End-to-end bracket order lifecycle
- Integration with execution engine
- Risk management integration
- Error handling scenarios

### Performance Tests
- Bracket order creation latency
- OCO monitoring performance
- Memory usage with multiple brackets
