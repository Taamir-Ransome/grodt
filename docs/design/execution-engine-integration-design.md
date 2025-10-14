# Execution Engine Integration Design

## Overview

The TradeExitService integrates with the existing ExecutionEngine to provide bracket order functionality and OCO emulation. This design ensures seamless integration while maintaining the existing architecture patterns.

## Integration Architecture

### Enhanced ExecutionEngine

```python
class EnhancedExecutionEngine(ExecutionEngine):
    """Enhanced execution engine with bracket order support."""
    
    def __init__(self, connector, risk_manager):
        super().__init__(connector, risk_manager)
        self.bracket_orders: Dict[str, BracketOrder] = {}
        self.oco_emulator = OCOEmulator(self)
        self.bracket_callbacks: List[Callable] = []
        self.logger = logging.getLogger(__name__)
    
    async def submit_bracket_order(
        self,
        bracket_order: BracketOrder
    ) -> ExecutionResult:
        """Submit a bracket order (TP + SL)."""
        
        try:
            # Create take profit order
            tp_order = self._create_take_profit_order(bracket_order)
            tp_result = await self.submit_order(tp_order)
            
            if not tp_result.status == OrderStatus.ACKNOWLEDGED:
                return ExecutionResult(
                    order_id=bracket_order.id,
                    status=OrderStatus.REJECTED,
                    error_message=f"Take profit order failed: {tp_result.error_message}"
                )
            
            # Create stop loss order
            sl_order = self._create_stop_loss_order(bracket_order)
            sl_result = await self.submit_order(sl_order)
            
            if not sl_result.status == OrderStatus.ACKNOWLEDGED:
                # Cancel take profit order if stop loss fails
                await self.cancel_order(tp_order.id)
                return ExecutionResult(
                    order_id=bracket_order.id,
                    status=OrderStatus.REJECTED,
                    error_message=f"Stop loss order failed: {sl_result.error_message}"
                )
            
            # Register bracket order for OCO monitoring
            bracket_order.take_profit_order_id = tp_order.id
            bracket_order.stop_loss_order_id = sl_order.id
            bracket_order.status = BracketOrderStatus.ACTIVE
            
            self.bracket_orders[bracket_order.id] = bracket_order
            await self.oco_emulator.register_bracket_order(bracket_order)
            
            # Start OCO monitoring
            asyncio.create_task(self.oco_emulator.monitor_bracket_orders())
            
            return ExecutionResult(
                order_id=bracket_order.id,
                status=OrderStatus.ACKNOWLEDGED,
                execution_time=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to submit bracket order {bracket_order.id}: {e}")
            return ExecutionResult(
                order_id=bracket_order.id,
                status=OrderStatus.REJECTED,
                error_message=str(e)
            )
    
    def _create_take_profit_order(self, bracket_order: BracketOrder) -> Order:
        """Create take profit order from bracket order."""
        
        order_id = f"tp_{bracket_order.symbol}_{int(datetime.now().timestamp())}"
        
        return Order(
            id=order_id,
            symbol=bracket_order.symbol,
            side="sell" if bracket_order.quantity > 0 else "buy",
            quantity=abs(bracket_order.quantity),
            price=bracket_order.take_profit_price,
            order_type="limit",
            status="pending",
            created_at=datetime.now()
        )
    
    def _create_stop_loss_order(self, bracket_order: BracketOrder) -> Order:
        """Create stop loss order from bracket order."""
        
        order_id = f"sl_{bracket_order.symbol}_{int(datetime.now().timestamp())}"
        
        return Order(
            id=order_id,
            symbol=bracket_order.symbol,
            side="sell" if bracket_order.quantity > 0 else "buy",
            quantity=abs(bracket_order.quantity),
            price=bracket_order.stop_loss_price,
            order_type="stop",
            status="pending",
            created_at=datetime.now()
        )
```

### OCO Emulation Integration

```python
class OCOEmulator:
    """Emulates One-Cancels-Other functionality."""
    
    def __init__(self, execution_engine: EnhancedExecutionEngine):
        self.execution_engine = execution_engine
        self.bracket_orders: Dict[str, BracketOrder] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.logger = logging.getLogger(__name__)
    
    async def register_bracket_order(self, bracket_order: BracketOrder) -> None:
        """Register a bracket order for OCO monitoring."""
        
        self.bracket_orders[bracket_order.id] = bracket_order
        
        # Add execution callbacks for both orders
        self.execution_engine.add_execution_callback(
            lambda event_type, order: self._handle_order_event(event_type, order, bracket_order)
        )
        
        self.logger.info(f"Registered bracket order {bracket_order.id} for OCO monitoring")
    
    async def _handle_order_event(
        self,
        event_type: str,
        order: Order,
        bracket_order: BracketOrder
    ) -> None:
        """Handle order events for OCO logic."""
        
        if event_type == "order_filled":
            if order.id == bracket_order.take_profit_order_id:
                await self._handle_take_profit_fill(bracket_order, order)
            elif order.id == bracket_order.stop_loss_order_id:
                await self._handle_stop_loss_fill(bracket_order, order)
    
    async def _handle_take_profit_fill(
        self,
        bracket_order: BracketOrder,
        tp_order: Order
    ) -> None:
        """Handle take profit fill - cancel stop loss."""
        
        self.logger.info(f"Take profit filled for bracket {bracket_order.id}")
        
        # Cancel stop loss order
        if bracket_order.stop_loss_order_id:
            await self.execution_engine.cancel_order(bracket_order.stop_loss_order_id)
        
        # Update bracket order status
        bracket_order.status = BracketOrderStatus.COMPLETED
        bracket_order.completed_at = datetime.now()
        
        # Trigger callbacks
        await self._trigger_bracket_callbacks("bracket_completed", bracket_order)
    
    async def _handle_stop_loss_fill(
        self,
        bracket_order: BracketOrder,
        sl_order: Order
    ) -> None:
        """Handle stop loss fill - cancel take profit."""
        
        self.logger.info(f"Stop loss filled for bracket {bracket_order.id}")
        
        # Cancel take profit order
        if bracket_order.take_profit_order_id:
            await self.execution_engine.cancel_order(bracket_order.take_profit_order_id)
        
        # Update bracket order status
        bracket_order.status = BracketOrderStatus.COMPLETED
        bracket_order.completed_at = datetime.now()
        
        # Trigger callbacks
        await self._trigger_bracket_callbacks("bracket_completed", bracket_order)
```

## TradeExitService Integration

### Service Initialization

```python
class TradeExitService:
    """Main service for trade exit functionality."""
    
    def __init__(
        self,
        connector: RobinhoodConnector,
        risk_manager: RiskManager,
        execution_engine: EnhancedExecutionEngine,
        symbol: str,
        config: dict[str, Any]
    ):
        self.connector = connector
        self.risk_manager = risk_manager
        self.execution_engine = execution_engine
        self.symbol = symbol
        self.config = config
        
        # Initialize components
        self.atr_calculator = ATRCalculator()
        self.risk_reward_calculator = RiskRewardCalculator(
            RiskRewardConfig.from_dict(config.get('risk_reward', {}))
        )
        
        # Service state
        self.is_running = False
        self.active_brackets: Dict[str, BracketOrder] = {}
        self.exit_callbacks: List[Callable] = []
        
        self.logger = logging.getLogger(__name__)
    
    async def start(self):
        """Start the trade exit service."""
        
        if self.is_running:
            self.logger.warning("Trade exit service is already running")
            return
        
        self.is_running = True
        self.logger.info("Started trade exit service")
        
        # Add execution callbacks for entry order fills
        self.execution_engine.add_execution_callback(self._on_entry_order_fill)
    
    async def _on_entry_order_fill(self, event_type: str, order: Order):
        """Handle entry order fill events."""
        
        if event_type == "order_filled" and order.symbol == self.symbol:
            self.logger.info(f"Entry order filled for {order.symbol}, creating bracket order")
            
            # Create bracket order
            await self._create_bracket_order_for_entry(order)
```

### Bracket Order Creation

```python
async def _create_bracket_order_for_entry(self, entry_order: Order) -> None:
    """Create bracket order after entry order fills."""
    
    try:
        # Calculate ATR for stop loss
        atr_calculation = await self.atr_calculator.calculate_atr_for_symbol(
            self.symbol, period=14
        )
        
        # Calculate stop loss price
        stop_loss_price = await self.atr_calculator.calculate_stop_loss(
            entry_order.average_fill_price or entry_order.price,
            atr_calculation.atr_value,
            self.risk_manager.limits.atr_multiplier,
            entry_order.side
        )
        
        # Calculate take profit price
        take_profit_price = await self.risk_reward_calculator.calculate_take_profit(
            entry_order.average_fill_price or entry_order.price,
            stop_loss_price,
            entry_order.side,
            self.symbol
        )
        
        # Create bracket order
        bracket_order = BracketOrder(
            id=f"bracket_{self.symbol}_{int(datetime.now().timestamp())}",
            parent_order_id=entry_order.id,
            symbol=self.symbol,
            quantity=entry_order.filled_quantity,
            entry_price=entry_order.average_fill_price or entry_order.price,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            risk_reward_ratio=self.config.get('risk_reward', {}).get('base_ratio', 1.5),
            atr_value=atr_calculation.atr_value,
            status=BracketOrderStatus.PENDING,
            created_at=datetime.now()
        )
        
        # Submit bracket order
        result = await self.execution_engine.submit_bracket_order(bracket_order)
        
        if result.status == OrderStatus.ACKNOWLEDGED:
            self.active_brackets[bracket_order.id] = bracket_order
            self.logger.info(f"Created bracket order {bracket_order.id}")
        else:
            self.logger.error(f"Failed to create bracket order: {result.error_message}")
            
    except Exception as e:
        self.logger.error(f"Error creating bracket order: {e}")
```

## Event Handling Integration

### Callback System

```python
class TradeExitEventManager:
    """Manages trade exit events and callbacks."""
    
    def __init__(self):
        self.callbacks: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_callback(self, event_type: str, callback: Callable) -> None:
        """Add callback for specific event type."""
        
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        
        self.callbacks[event_type].append(callback)
        self.logger.debug(f"Added callback for {event_type}")
    
    async def trigger_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Trigger callbacks for event type."""
        
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    await callback(event_type, data)
                except Exception as e:
                    self.logger.error(f"Error in callback for {event_type}: {e}")
    
    async def trigger_bracket_created(self, bracket_order: BracketOrder) -> None:
        """Trigger bracket created event."""
        
        await self.trigger_event("bracket_created", {
            "bracket_order": bracket_order,
            "symbol": bracket_order.symbol,
            "timestamp": datetime.now()
        })
    
    async def trigger_bracket_completed(self, bracket_order: BracketOrder) -> None:
        """Trigger bracket completed event."""
        
        await self.trigger_event("bracket_completed", {
            "bracket_order": bracket_order,
            "symbol": bracket_order.symbol,
            "timestamp": datetime.now()
        })
```

## Error Handling Integration

### Error Recovery

```python
class TradeExitErrorHandler:
    """Handles errors in trade exit functionality."""
    
    def __init__(self, execution_engine: EnhancedExecutionEngine):
        self.execution_engine = execution_engine
        self.logger = logging.getLogger(__name__)
    
    async def handle_bracket_order_error(
        self,
        bracket_order: BracketOrder,
        error: Exception
    ) -> None:
        """Handle bracket order errors."""
        
        self.logger.error(f"Bracket order error for {bracket_order.id}: {error}")
        
        # Cancel any active orders
        if bracket_order.take_profit_order_id:
            await self.execution_engine.cancel_order(bracket_order.take_profit_order_id)
        
        if bracket_order.stop_loss_order_id:
            await self.execution_engine.cancel_order(bracket_order.stop_loss_order_id)
        
        # Update bracket order status
        bracket_order.status = BracketOrderStatus.ERROR
        bracket_order.error_message = str(error)
        
        # Trigger error callbacks
        await self._trigger_error_callbacks("bracket_error", bracket_order, error)
    
    async def handle_atr_calculation_error(
        self,
        symbol: str,
        error: Exception
    ) -> float:
        """Handle ATR calculation errors with fallback."""
        
        self.logger.warning(f"ATR calculation failed for {symbol}: {error}")
        
        # Use fallback percentage stop
        fallback_percentage = 0.02  # 2% stop loss
        
        # Get current price
        quote = await self.execution_engine.connector.get_quote(symbol)
        current_price = quote.price
        
        return current_price * (1 - fallback_percentage)  # Conservative fallback
```

## Configuration Integration

### Configuration Loading

```python
class TradeExitConfigLoader:
    """Loads trade exit configuration."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
    
    async def load_config(self) -> Dict[str, Any]:
        """Load trade exit configuration."""
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            return config.get('trade_exit', {})
            
        except Exception as e:
            self.logger.error(f"Failed to load trade exit config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        
        return {
            'risk_reward': {
                'strategy': 'fixed_ratio',
                'base_ratio': 1.5,
                'min_ratio': 1.0,
                'max_ratio': 3.0
            },
            'atr': {
                'period': 14,
                'multiplier': 2.0,
                'fallback_percentage': 0.02
            },
            'bracket_orders': {
                'max_active_brackets': 50,
                'timeout_seconds': 3600
            }
        }
```

## Testing Integration

### Integration Test Framework

```python
class TradeExitIntegrationTest:
    """Integration tests for trade exit functionality."""
    
    def __init__(self):
        self.mock_connector = MockRobinhoodConnector()
        self.mock_risk_manager = MockRiskManager()
        self.execution_engine = EnhancedExecutionEngine(
            self.mock_connector, self.mock_risk_manager
        )
        self.trade_exit_service = TradeExitService(
            self.mock_connector,
            self.mock_risk_manager,
            self.execution_engine,
            "AAPL",
            self._get_test_config()
        )
    
    async def test_bracket_order_creation(self):
        """Test bracket order creation flow."""
        
        # Start service
        await self.trade_exit_service.start()
        
        # Simulate entry order fill
        entry_order = self._create_mock_entry_order()
        await self.trade_exit_service._on_entry_order_fill("order_filled", entry_order)
        
        # Verify bracket order was created
        assert len(self.trade_exit_service.active_brackets) == 1
        
        # Verify both TP and SL orders were placed
        bracket_order = list(self.trade_exit_service.active_brackets.values())[0]
        assert bracket_order.take_profit_order_id is not None
        assert bracket_order.stop_loss_order_id is not None
```

## Performance Considerations

### Memory Management
- Limit active bracket orders
- Cleanup completed brackets
- Monitor memory usage

### Latency Optimization
- Async bracket order creation
- Parallel order monitoring
- Efficient event handling

### Scalability
- Support multiple symbols
- Handle high-frequency trading
- Optimize database operations
