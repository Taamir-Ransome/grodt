# Trade Exit Test Design

## Overview

Comprehensive test strategy for the trade exit functionality, covering unit tests, integration tests, and end-to-end scenarios. This design ensures robust testing of all components and their interactions.

## Test Architecture

### Test Categories

1. **Unit Tests** - Individual component testing
2. **Integration Tests** - Component interaction testing
3. **End-to-End Tests** - Complete workflow testing
4. **Performance Tests** - Load and performance testing
5. **Error Handling Tests** - Error scenario testing

## Unit Test Design

### TradeExitService Tests

```python
# tests/unit/test_trade_exit_service.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from grodtd.execution.trade_exit_service import TradeExitService, BracketOrder, BracketOrderStatus
from grodtd.execution.engine import Order, OrderStatus

class TestTradeExitService:
    """Unit tests for TradeExitService."""
    
    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""
        connector = Mock()
        risk_manager = Mock()
        execution_engine = Mock()
        return connector, risk_manager, execution_engine
    
    @pytest.fixture
    def trade_exit_service(self, mock_components):
        """Create TradeExitService instance for testing."""
        connector, risk_manager, execution_engine = mock_components
        config = {
            'risk_reward': {'base_ratio': 1.5},
            'atr': {'multiplier': 2.0}
        }
        return TradeExitService(connector, risk_manager, execution_engine, "AAPL", config)
    
    async def test_service_initialization(self, trade_exit_service):
        """Test service initialization."""
        assert trade_exit_service.symbol == "AAPL"
        assert trade_exit_service.is_running == False
        assert len(trade_exit_service.active_brackets) == 0
    
    async def test_start_service(self, trade_exit_service):
        """Test service startup."""
        await trade_exit_service.start()
        assert trade_exit_service.is_running == True
    
    async def test_stop_service(self, trade_exit_service):
        """Test service shutdown."""
        await trade_exit_service.start()
        await trade_exit_service.stop()
        assert trade_exit_service.is_running == False
    
    async def test_create_bracket_order(self, trade_exit_service):
        """Test bracket order creation."""
        # Mock entry order
        entry_order = Order(
            id="entry_123",
            symbol="AAPL",
            side="buy",
            quantity=100,
            price=150.0,
            order_type="market",
            status="filled",
            filled_quantity=100,
            average_fill_price=150.0,
            filled_at=datetime.now()
        )
        
        # Mock ATR calculation
        with patch.object(trade_exit_service.atr_calculator, 'calculate_atr_for_symbol') as mock_atr:
            mock_atr.return_value = Mock(atr_value=2.0)
            
            # Mock risk/reward calculation
            with patch.object(trade_exit_service.risk_reward_calculator, 'calculate_take_profit') as mock_tp:
                mock_tp.return_value = 155.0
                
                # Mock execution engine
                trade_exit_service.execution_engine.submit_bracket_order = AsyncMock(
                    return_value=Mock(status=OrderStatus.ACKNOWLEDGED)
                )
                
                # Create bracket order
                result = await trade_exit_service._create_bracket_order_for_entry(entry_order)
                
                # Verify bracket order was created
                assert len(trade_exit_service.active_brackets) == 1
                bracket_order = list(trade_exit_service.active_brackets.values())[0]
                assert bracket_order.symbol == "AAPL"
                assert bracket_order.quantity == 100
                assert bracket_order.entry_price == 150.0
```

### ATR Calculator Tests

```python
# tests/unit/test_atr_calculator.py

import pytest
import pandas as pd
import numpy as np
from grodtd.execution.trade_exit_service import ATRCalculator

class TestATRCalculator:
    """Unit tests for ATRCalculator."""
    
    @pytest.fixture
    def sample_market_data(self):
        """Create sample market data for testing."""
        dates = pd.date_range('2024-01-01', periods=20, freq='D')
        data = {
            'high': np.random.uniform(100, 110, 20),
            'low': np.random.uniform(90, 100, 20),
            'close': np.random.uniform(95, 105, 20)
        }
        return pd.DataFrame(data, index=dates)
    
    async def test_atr_calculation(self, sample_market_data):
        """Test ATR calculation."""
        calculator = ATRCalculator(period=14)
        result = await calculator.calculate_atr(sample_market_data)
        
        assert result.atr_value > 0
        assert result.period == 14
        assert result.confidence > 0
    
    async def test_stop_loss_calculation_long(self):
        """Test stop loss calculation for long position."""
        calculator = ATRCalculator()
        
        entry_price = 100.0
        atr_value = 2.0
        atr_multiplier = 2.0
        side = "buy"
        
        stop_loss = await calculator.calculate_stop_loss(
            entry_price, atr_value, atr_multiplier, side
        )
        
        expected_stop = entry_price - (atr_value * atr_multiplier)
        assert stop_loss == expected_stop
        assert stop_loss < entry_price  # Stop loss should be below entry for long
    
    async def test_stop_loss_calculation_short(self):
        """Test stop loss calculation for short position."""
        calculator = ATRCalculator()
        
        entry_price = 100.0
        atr_value = 2.0
        atr_multiplier = 2.0
        side = "sell"
        
        stop_loss = await calculator.calculate_stop_loss(
            entry_price, atr_value, atr_multiplier, side
        )
        
        expected_stop = entry_price + (atr_value * atr_multiplier)
        assert stop_loss == expected_stop
        assert stop_loss > entry_price  # Stop loss should be above entry for short
```

### Bracket Order Manager Tests

```python
# tests/unit/test_bracket_order_manager.py

import pytest
from unittest.mock import Mock, AsyncMock
from grodtd.execution.trade_exit_service import BracketOrderManager, BracketOrder, BracketOrderStatus

class TestBracketOrderManager:
    """Unit tests for BracketOrderManager."""
    
    @pytest.fixture
    def bracket_manager(self):
        """Create BracketOrderManager instance."""
        execution_engine = Mock()
        return BracketOrderManager(execution_engine)
    
    async def test_create_bracket_order(self, bracket_manager):
        """Test bracket order creation."""
        parent_order = Mock()
        parent_order.id = "parent_123"
        parent_order.symbol = "AAPL"
        parent_order.filled_quantity = 100
        parent_order.average_fill_price = 150.0
        parent_order.side = "buy"
        
        atr_value = 2.0
        risk_reward_ratio = 1.5
        
        bracket_order = await bracket_manager.create_bracket_order(
            parent_order, atr_value, risk_reward_ratio
        )
        
        assert bracket_order.parent_order_id == "parent_123"
        assert bracket_order.symbol == "AAPL"
        assert bracket_order.quantity == 100
        assert bracket_order.entry_price == 150.0
        assert bracket_order.status == BracketOrderStatus.PENDING
    
    async def test_place_bracket_orders(self, bracket_manager):
        """Test placing bracket orders."""
        bracket_order = BracketOrder(
            id="bracket_123",
            parent_order_id="parent_123",
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            take_profit_price=155.0,
            stop_loss_price=145.0,
            risk_reward_ratio=1.5,
            atr_value=2.0,
            status=BracketOrderStatus.PENDING,
            created_at=datetime.now()
        )
        
        # Mock execution engine
        bracket_manager.execution_engine.submit_order = AsyncMock(
            return_value=Mock(status=OrderStatus.ACKNOWLEDGED, order_id="order_123")
        )
        
        result = await bracket_manager.place_bracket_orders(bracket_order)
        
        assert result == True
        assert bracket_order.take_profit_order_id is not None
        assert bracket_order.stop_loss_order_id is not None
        assert bracket_order.status == BracketOrderStatus.ACTIVE
```

## Integration Test Design

### End-to-End Bracket Order Flow

```python
# tests/integration/test_bracket_order_flow.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from grodtd.execution.trade_exit_service import TradeExitService
from grodtd.execution.engine import Order, OrderStatus

class TestBracketOrderFlow:
    """Integration tests for complete bracket order flow."""
    
    @pytest.fixture
    async def setup_trade_exit_service(self):
        """Set up complete trade exit service for testing."""
        connector = Mock()
        risk_manager = Mock()
        execution_engine = Mock()
        
        # Configure mocks
        connector.get_quote = AsyncMock(return_value=Mock(price=150.0))
        risk_manager.limits.atr_multiplier = 2.0
        
        config = {
            'risk_reward': {'base_ratio': 1.5},
            'atr': {'multiplier': 2.0}
        }
        
        service = TradeExitService(connector, risk_manager, execution_engine, "AAPL", config)
        await service.start()
        
        return service, connector, risk_manager, execution_engine
    
    async def test_complete_bracket_order_flow(self, setup_trade_exit_service):
        """Test complete bracket order flow from entry to exit."""
        service, connector, risk_manager, execution_engine = await setup_trade_exit_service
        
        # Mock entry order fill
        entry_order = Order(
            id="entry_123",
            symbol="AAPL",
            side="buy",
            quantity=100,
            price=150.0,
            order_type="market",
            status="filled",
            filled_quantity=100,
            average_fill_price=150.0,
            filled_at=datetime.now()
        )
        
        # Mock ATR calculation
        with patch.object(service.atr_calculator, 'calculate_atr_for_symbol') as mock_atr:
            mock_atr.return_value = Mock(atr_value=2.0)
            
            # Mock risk/reward calculation
            with patch.object(service.risk_reward_calculator, 'calculate_take_profit') as mock_tp:
                mock_tp.return_value = 155.0
                
                # Mock execution engine bracket order submission
                execution_engine.submit_bracket_order = AsyncMock(
                    return_value=Mock(status=OrderStatus.ACKNOWLEDGED)
                )
                
                # Simulate entry order fill
                await service._on_entry_order_fill("order_filled", entry_order)
                
                # Verify bracket order was created
                assert len(service.active_brackets) == 1
                bracket_order = list(service.active_brackets.values())[0]
                assert bracket_order.symbol == "AAPL"
                assert bracket_order.entry_price == 150.0
                assert bracket_order.take_profit_price == 155.0
```

### OCO Emulation Tests

```python
# tests/integration/test_oco_emulation.py

import pytest
from unittest.mock import Mock, AsyncMock
from grodtd.execution.trade_exit_service import OCOEmulator, BracketOrder, BracketOrderStatus

class TestOCOEmulation:
    """Integration tests for OCO emulation."""
    
    @pytest.fixture
    def oco_emulator(self):
        """Create OCOEmulator instance."""
        execution_engine = Mock()
        return OCOEmulator(execution_engine)
    
    async def test_take_profit_fill_cancels_stop_loss(self, oco_emulator):
        """Test that take profit fill cancels stop loss."""
        bracket_order = BracketOrder(
            id="bracket_123",
            parent_order_id="parent_123",
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            take_profit_price=155.0,
            stop_loss_price=145.0,
            risk_reward_ratio=1.5,
            atr_value=2.0,
            status=BracketOrderStatus.ACTIVE,
            created_at=datetime.now(),
            take_profit_order_id="tp_123",
            stop_loss_order_id="sl_123"
        )
        
        # Mock execution engine
        oco_emulator.execution_engine.cancel_order = AsyncMock(return_value=True)
        
        # Mock take profit order
        tp_order = Mock()
        tp_order.id = "tp_123"
        
        # Handle take profit fill
        await oco_emulator._handle_take_profit_fill(bracket_order, tp_order)
        
        # Verify stop loss was cancelled
        oco_emulator.execution_engine.cancel_order.assert_called_once_with("sl_123")
        
        # Verify bracket order status
        assert bracket_order.status == BracketOrderStatus.COMPLETED
        assert bracket_order.completed_at is not None
    
    async def test_stop_loss_fill_cancels_take_profit(self, oco_emulator):
        """Test that stop loss fill cancels take profit."""
        bracket_order = BracketOrder(
            id="bracket_123",
            parent_order_id="parent_123",
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            take_profit_price=155.0,
            stop_loss_price=145.0,
            risk_reward_ratio=1.5,
            atr_value=2.0,
            status=BracketOrderStatus.ACTIVE,
            created_at=datetime.now(),
            take_profit_order_id="tp_123",
            stop_loss_order_id="sl_123"
        )
        
        # Mock execution engine
        oco_emulator.execution_engine.cancel_order = AsyncMock(return_value=True)
        
        # Mock stop loss order
        sl_order = Mock()
        sl_order.id = "sl_123"
        
        # Handle stop loss fill
        await oco_emulator._handle_stop_loss_fill(bracket_order, sl_order)
        
        # Verify take profit was cancelled
        oco_emulator.execution_engine.cancel_order.assert_called_once_with("tp_123")
        
        # Verify bracket order status
        assert bracket_order.status == BracketOrderStatus.COMPLETED
        assert bracket_order.completed_at is not None
```

## Performance Test Design

### Load Testing

```python
# tests/performance/test_trade_exit_performance.py

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock
from grodtd.execution.trade_exit_service import TradeExitService

class TestTradeExitPerformance:
    """Performance tests for trade exit functionality."""
    
    @pytest.fixture
    async def performance_service(self):
        """Create service for performance testing."""
        connector = Mock()
        risk_manager = Mock()
        execution_engine = Mock()
        
        # Configure mocks for performance
        connector.get_quote = AsyncMock(return_value=Mock(price=150.0))
        execution_engine.submit_bracket_order = AsyncMock(
            return_value=Mock(status=OrderStatus.ACKNOWLEDGED)
        )
        
        config = {
            'risk_reward': {'base_ratio': 1.5},
            'atr': {'multiplier': 2.0}
        }
        
        service = TradeExitService(connector, risk_manager, execution_engine, "AAPL", config)
        await service.start()
        
        return service
    
    async def test_bracket_order_creation_performance(self, performance_service):
        """Test bracket order creation performance."""
        # Create multiple entry orders
        entry_orders = []
        for i in range(100):
            entry_order = Order(
                id=f"entry_{i}",
                symbol="AAPL",
                side="buy",
                quantity=100,
                price=150.0,
                order_type="market",
                status="filled",
                filled_quantity=100,
                average_fill_price=150.0,
                filled_at=datetime.now()
            )
            entry_orders.append(entry_order)
        
        # Measure creation time
        start_time = time.time()
        
        # Create bracket orders
        tasks = []
        for entry_order in entry_orders:
            task = performance_service._create_bracket_order_for_entry(entry_order)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Verify performance
        assert creation_time < 5.0  # Should create 100 bracket orders in under 5 seconds
        assert len(performance_service.active_brackets) == 100
    
    async def test_memory_usage_with_multiple_brackets(self, performance_service):
        """Test memory usage with multiple bracket orders."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create many bracket orders
        for i in range(1000):
            entry_order = Order(
                id=f"entry_{i}",
                symbol="AAPL",
                side="buy",
                quantity=100,
                price=150.0,
                order_type="market",
                status="filled",
                filled_quantity=100,
                average_fill_price=150.0,
                filled_at=datetime.now()
            )
            
            await performance_service._create_bracket_order_for_entry(entry_order)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Verify memory usage is reasonable (less than 100MB for 1000 brackets)
        assert memory_increase < 100 * 1024 * 1024  # 100MB
```

## Error Handling Test Design

### Error Scenario Tests

```python
# tests/error_handling/test_trade_exit_errors.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from grodtd.execution.trade_exit_service import TradeExitService, BracketOrderStatus

class TestTradeExitErrorHandling:
    """Error handling tests for trade exit functionality."""
    
    @pytest.fixture
    def error_service(self):
        """Create service for error testing."""
        connector = Mock()
        risk_manager = Mock()
        execution_engine = Mock()
        
        config = {
            'risk_reward': {'base_ratio': 1.5},
            'atr': {'multiplier': 2.0}
        }
        
        return TradeExitService(connector, risk_manager, execution_engine, "AAPL", config)
    
    async def test_atr_calculation_failure(self, error_service):
        """Test handling of ATR calculation failures."""
        entry_order = Mock()
        entry_order.id = "entry_123"
        entry_order.symbol = "AAPL"
        entry_order.filled_quantity = 100
        entry_order.average_fill_price = 150.0
        entry_order.side = "buy"
        
        # Mock ATR calculation failure
        with patch.object(error_service.atr_calculator, 'calculate_atr_for_symbol') as mock_atr:
            mock_atr.side_effect = Exception("ATR calculation failed")
            
            # Mock fallback calculation
            with patch.object(error_service.atr_calculator, 'calculate_stop_loss') as mock_sl:
                mock_sl.return_value = 147.0  # 2% fallback
                
                # Should not raise exception
                await error_service._create_bracket_order_for_entry(entry_order)
                
                # Verify fallback was used
                mock_sl.assert_called_once()
    
    async def test_bracket_order_placement_failure(self, error_service):
        """Test handling of bracket order placement failures."""
        entry_order = Mock()
        entry_order.id = "entry_123"
        entry_order.symbol = "AAPL"
        entry_order.filled_quantity = 100
        entry_order.average_fill_price = 150.0
        entry_order.side = "buy"
        
        # Mock successful ATR calculation
        with patch.object(error_service.atr_calculator, 'calculate_atr_for_symbol') as mock_atr:
            mock_atr.return_value = Mock(atr_value=2.0)
            
            # Mock bracket order placement failure
            error_service.execution_engine.submit_bracket_order = AsyncMock(
                return_value=Mock(status=OrderStatus.REJECTED, error_message="Insufficient funds")
            )
            
            # Should not raise exception
            await error_service._create_bracket_order_for_entry(entry_order)
            
            # Verify no bracket orders were created
            assert len(error_service.active_brackets) == 0
    
    async def test_oco_emulation_failure(self, error_service):
        """Test handling of OCO emulation failures."""
        bracket_order = Mock()
        bracket_order.id = "bracket_123"
        bracket_order.take_profit_order_id = "tp_123"
        bracket_order.stop_loss_order_id = "sl_123"
        bracket_order.status = BracketOrderStatus.ACTIVE
        
        # Mock order cancellation failure
        error_service.execution_engine.cancel_order = AsyncMock(return_value=False)
        
        # Should not raise exception
        await error_service._handle_bracket_fill(bracket_order, Mock())
        
        # Verify cancellation was attempted
        error_service.execution_engine.cancel_order.assert_called()
```

## Test Configuration

### Test Environment Setup

```python
# tests/conftest.py

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from grodtd.execution.trade_exit_service import TradeExitService
from grodtd.execution.engine import ExecutionEngine
from grodtd.risk.manager import RiskManager, RiskLimits

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_connector():
    """Create mock connector."""
    connector = Mock()
    connector.get_quote = AsyncMock(return_value=Mock(price=150.0))
    connector.place_order = AsyncMock(return_value="order_123")
    connector.cancel_order = AsyncMock(return_value=True)
    return connector

@pytest.fixture
def mock_risk_manager():
    """Create mock risk manager."""
    limits = RiskLimits()
    risk_manager = Mock(spec=RiskManager)
    risk_manager.limits = limits
    risk_manager.can_open_position = Mock(return_value=(True, "OK"))
    return risk_manager

@pytest.fixture
def mock_execution_engine():
    """Create mock execution engine."""
    engine = Mock(spec=ExecutionEngine)
    engine.submit_order = AsyncMock(return_value=Mock(status=OrderStatus.ACKNOWLEDGED))
    engine.submit_bracket_order = AsyncMock(return_value=Mock(status=OrderStatus.ACKNOWLEDGED))
    engine.cancel_order = AsyncMock(return_value=True)
    return engine

@pytest.fixture
def test_config():
    """Create test configuration."""
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

## Test Execution Strategy

### Test Execution Order

1. **Unit Tests** - Run first for fast feedback
2. **Integration Tests** - Run after unit tests pass
3. **Performance Tests** - Run in separate environment
4. **Error Handling Tests** - Run with unit tests

### Continuous Integration

```yaml
# .github/workflows/test.yml
name: Trade Exit Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=grodtd.execution.trade_exit_service
  
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run integration tests
        run: pytest tests/integration/ -v
  
  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run performance tests
        run: pytest tests/performance/ -v --durations=10
```

## Test Coverage Goals

- **Unit Tests**: 95%+ code coverage
- **Integration Tests**: All critical paths covered
- **Performance Tests**: Latency and memory benchmarks
- **Error Handling**: All error scenarios tested

## Test Data Management

### Mock Data Generation

```python
# tests/utils/test_data_generator.py

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class TestDataGenerator:
    """Generate test data for trade exit tests."""
    
    @staticmethod
    def generate_market_data(symbol: str, days: int = 30) -> pd.DataFrame:
        """Generate realistic market data for testing."""
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=days),
            end=datetime.now(),
            freq='D'
        )
        
        # Generate realistic price data
        base_price = 150.0
        returns = np.random.normal(0, 0.02, len(dates))  # 2% daily volatility
        
        prices = [base_price]
        for return_val in returns[1:]:
            prices.append(prices[-1] * (1 + return_val))
        
        data = {
            'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }
        
        return pd.DataFrame(data, index=dates)
    
    @staticmethod
    def generate_entry_order(symbol: str, side: str = "buy") -> Order:
        """Generate realistic entry order for testing."""
        return Order(
            id=f"entry_{symbol}_{int(datetime.now().timestamp())}",
            symbol=symbol,
            side=side,
            quantity=100,
            price=150.0,
            order_type="market",
            status="filled",
            filled_quantity=100,
            average_fill_price=150.0,
            filled_at=datetime.now()
        )
```
