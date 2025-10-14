"""
Unit tests for Trade Exit Service.

Tests the TradeExitService class for bracket order functionality,
OCO emulation, and ATR-based stop loss calculations.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from grodtd.execution.trade_exit_service import (
    TradeExitService, 
    BracketOrder, 
    TradeExitResult,
    create_trade_exit_service
)
from grodtd.execution.engine import ExecutionEngine, ExecutionResult, OrderStatus
from grodtd.risk.manager import RiskManager, RiskLimits, Position
from grodtd.connectors.robinhood import Order


class TestTradeExitService:
    """Test cases for TradeExitService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create mock components
        self.mock_execution_engine = Mock(spec=ExecutionEngine)
        self.mock_risk_manager = Mock(spec=RiskManager)
        
        # Mock execution engine methods
        self.mock_execution_engine.submit_order = AsyncMock()
        self.mock_execution_engine.cancel_order = AsyncMock()
        
        # Mock risk manager methods
        self.mock_risk_manager.positions = {}
        self.mock_risk_manager.close_position = Mock(return_value=100.0)
        
        self.config = {
            'risk_reward_ratio': 1.5,
            'atr_multiplier': 2.0
        }
        
        self.service = TradeExitService(
            self.mock_execution_engine,
            self.mock_risk_manager,
            self.config
        )
    
    def test_initialization(self):
        """Test service initialization."""
        assert self.service.execution_engine == self.mock_execution_engine
        assert self.service.risk_manager == self.mock_risk_manager
        assert self.service.default_risk_reward_ratio == 1.5
        assert self.service.atr_multiplier == 2.0
        assert len(self.service.active_brackets) == 0
    
    def test_calculate_exit_prices_long(self):
        """Test exit price calculation for long positions."""
        entry_price = 100.0
        atr = 2.0
        risk_reward_ratio = 1.5
        
        stop_loss, take_profit = self.service._calculate_exit_prices(
            entry_price, atr, risk_reward_ratio, "buy"
        )
        
        # Stop distance = ATR * multiplier = 2.0 * 2.0 = 4.0
        expected_stop_loss = 100.0 - 4.0  # 96.0
        expected_take_profit = 100.0 + (4.0 * 1.5)  # 106.0
        
        assert stop_loss == expected_stop_loss
        assert take_profit == expected_take_profit
    
    def test_calculate_exit_prices_short(self):
        """Test exit price calculation for short positions."""
        entry_price = 100.0
        atr = 2.0
        risk_reward_ratio = 2.0
        
        stop_loss, take_profit = self.service._calculate_exit_prices(
            entry_price, atr, risk_reward_ratio, "sell"
        )
        
        # Stop distance = ATR * multiplier = 2.0 * 2.0 = 4.0
        expected_stop_loss = 100.0 + 4.0  # 104.0
        expected_take_profit = 100.0 - (4.0 * 2.0)  # 92.0
        
        assert stop_loss == expected_stop_loss
        assert take_profit == expected_take_profit
    
    @pytest.mark.asyncio
    async def test_create_bracket_order_success(self):
        """Test successful bracket order creation."""
        # Create mock entry order
        entry_order = Order(
            id="entry_123",
            symbol="BTC",
            side="buy",
            quantity=1.0,
            price=100.0,
            order_type="market",
            status="filled",
            filled_quantity=1.0,
            average_fill_price=100.0,
            created_at=datetime.now()
        )
        
        # Mock successful order submissions
        self.mock_execution_engine.submit_order.return_value = ExecutionResult(
            order_id="test_id",
            status=OrderStatus.ACKNOWLEDGED
        )
        
        # Create bracket order
        result = await self.service.create_bracket_order(
            entry_order=entry_order,
            entry_price=100.0,
            atr=2.0,
            risk_reward_ratio=1.5
        )
        
        # Verify result
        assert result.success is True
        assert result.bracket_order_id == "bracket_entry_123"
        assert result.take_profit_placed is True
        assert result.stop_loss_placed is True
        assert result.error_message is None
        
        # Verify bracket order was created
        assert "bracket_entry_123" in self.service.active_brackets
        bracket = self.service.active_brackets["bracket_entry_123"]
        assert bracket.symbol == "BTC"
        assert bracket.quantity == 1.0
        assert bracket.entry_price == 100.0
        assert bracket.risk_reward_ratio == 1.5
    
    @pytest.mark.asyncio
    async def test_create_bracket_order_failure(self):
        """Test bracket order creation failure."""
        # Create mock entry order
        entry_order = Order(
            id="entry_123",
            symbol="BTC",
            side="buy",
            quantity=1.0,
            price=100.0,
            order_type="market",
            status="filled",
            filled_quantity=1.0,
            average_fill_price=100.0,
            created_at=datetime.now()
        )
        
        # Mock failed order submission
        self.mock_execution_engine.submit_order.return_value = ExecutionResult(
            order_id="test_id",
            status=OrderStatus.REJECTED,
            error_message="Order rejected"
        )
        
        # Create bracket order
        result = await self.service.create_bracket_order(
            entry_order=entry_order,
            entry_price=100.0,
            atr=2.0,
            risk_reward_ratio=1.5
        )
        
        # Verify result
        assert result.success is False
        assert result.take_profit_placed is False
        assert result.stop_loss_placed is False
        assert "Both TP and SL orders failed to place" in result.error_message
    
    @pytest.mark.asyncio
    async def test_handle_bracket_fill(self):
        """Test bracket order fill handling."""
        # Create a bracket order with order objects
        bracket = BracketOrder(
            entry_order_id="entry_123",
            symbol="BTC",
            quantity=1.0,
            entry_price=100.0,
            take_profit_price=106.0,
            stop_loss_price=96.0,
            risk_reward_ratio=1.5,
            created_at=datetime.now()
        )
        
        # Create mock order objects
        tp_order = Order(
            id="tp_entry_123",
            symbol="BTC",
            side="sell",
            quantity=1.0,
            price=106.0,
            order_type="limit",
            status="pending",
            created_at=datetime.now()
        )
        
        sl_order = Order(
            id="sl_entry_123",
            symbol="BTC",
            side="sell",
            quantity=1.0,
            price=96.0,
            order_type="stop",
            status="pending",
            created_at=datetime.now()
        )
        
        bracket.take_profit_order = tp_order
        bracket.stop_loss_order = sl_order
        
        # Add to active brackets
        self.service.active_brackets["bracket_123"] = bracket
        
        # Mock position in risk manager
        position = Position(
            symbol="BTC",
            quantity=1.0,
            entry_price=100.0,
            current_price=100.0
        )
        self.mock_risk_manager.positions["BTC"] = position
        
        # Handle bracket fill
        fill_data = {
            "average_fill_price": 106.0,
            "filled_quantity": 1.0
        }
        
        await self.service.handle_bracket_fill("tp_entry_123", fill_data)
        
        # Verify position was closed
        self.mock_risk_manager.close_position.assert_called_once_with("BTC", 106.0)
    
    @pytest.mark.asyncio
    async def test_cancel_bracket_order(self):
        """Test bracket order cancellation."""
        # Create a bracket order with order objects
        bracket = BracketOrder(
            entry_order_id="entry_123",
            symbol="BTC",
            quantity=1.0,
            entry_price=100.0,
            take_profit_price=106.0,
            stop_loss_price=96.0,
            risk_reward_ratio=1.5,
            created_at=datetime.now()
        )
        
        # Create mock order objects
        tp_order = Order(
            id="tp_entry_123",
            symbol="BTC",
            side="sell",
            quantity=1.0,
            price=106.0,
            order_type="limit",
            status="pending",
            created_at=datetime.now()
        )
        
        sl_order = Order(
            id="sl_entry_123",
            symbol="BTC",
            side="sell",
            quantity=1.0,
            price=96.0,
            order_type="stop",
            status="pending",
            created_at=datetime.now()
        )
        
        bracket.take_profit_order = tp_order
        bracket.stop_loss_order = sl_order
        
        # Add to active brackets
        self.service.active_brackets["bracket_123"] = bracket
        
        # Mock successful cancellation
        self.mock_execution_engine.cancel_order.return_value = True
        
        # Cancel bracket order
        result = await self.service.cancel_bracket_order("bracket_123")
        
        # Verify result
        assert result is True
        assert "bracket_123" not in self.service.active_brackets
        assert self.mock_execution_engine.cancel_order.call_count == 2  # TP and SL
    
    def test_get_active_brackets(self):
        """Test getting active bracket orders."""
        # Add some bracket orders
        bracket1 = BracketOrder(entry_order_id="entry_1", symbol="BTC")
        bracket2 = BracketOrder(entry_order_id="entry_2", symbol="ETH")
        
        self.service.active_brackets["bracket_1"] = bracket1
        self.service.active_brackets["bracket_2"] = bracket2
        
        # Get active brackets
        active_brackets = self.service.get_active_brackets()
        
        assert len(active_brackets) == 2
        assert bracket1 in active_brackets
        assert bracket2 in active_brackets
    
    def test_get_bracket_summary(self):
        """Test getting bracket order summary."""
        # Add a bracket order
        bracket = BracketOrder(
            entry_order_id="entry_123",
            symbol="BTC",
            quantity=1.0,
            entry_price=100.0,
            take_profit_price=106.0,
            stop_loss_price=96.0,
            risk_reward_ratio=1.5,
            created_at=datetime.now()
        )
        
        self.service.active_brackets["bracket_123"] = bracket
        
        # Get summary
        summary = self.service.get_bracket_summary()
        
        assert summary["active_brackets"] == 1
        assert len(summary["brackets"]) == 1
        assert summary["brackets"][0]["symbol"] == "BTC"
        assert summary["brackets"][0]["quantity"] == 1.0
        assert summary["brackets"][0]["risk_reward_ratio"] == 1.5
    
    def test_update_position_exit_levels(self):
        """Test updating position exit levels."""
        # Create a position
        position = Position(
            symbol="BTC",
            quantity=1.0,
            entry_price=100.0,
            current_price=100.0
        )
        self.mock_risk_manager.positions["BTC"] = position
        
        # Update exit levels
        self.service._update_position_exit_levels("BTC", 96.0, 106.0)
        
        # Verify position was updated
        assert position.stop_loss == 96.0
        assert position.take_profit == 106.0
    
    @pytest.mark.asyncio
    async def test_bracket_callback(self):
        """Test bracket order callbacks."""
        callback_called = False
        callback_data = None
        
        async def test_callback(event_type, bracket, data):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = (event_type, bracket, data)
        
        # Add callback
        self.service.add_bracket_callback(test_callback)
        
        # Create a bracket order
        bracket = BracketOrder(entry_order_id="entry_123", symbol="BTC")
        
        # Trigger callback
        await self.service._trigger_bracket_callbacks("test_event", bracket, {"test": "data"})
        
        # Verify callback was called
        assert callback_called is True
        assert callback_data[0] == "test_event"
        assert callback_data[1] == bracket
        assert callback_data[2] == {"test": "data"}


class TestBracketOrder:
    """Test cases for BracketOrder dataclass."""
    
    def test_bracket_order_creation(self):
        """Test BracketOrder creation."""
        bracket = BracketOrder(
            entry_order_id="entry_123",
            symbol="BTC",
            quantity=1.0,
            entry_price=100.0,
            take_profit_price=106.0,
            stop_loss_price=96.0,
            risk_reward_ratio=1.5,
            created_at=datetime.now()
        )
        
        assert bracket.entry_order_id == "entry_123"
        assert bracket.symbol == "BTC"
        assert bracket.quantity == 1.0
        assert bracket.entry_price == 100.0
        assert bracket.take_profit_price == 106.0
        assert bracket.stop_loss_price == 96.0
        assert bracket.risk_reward_ratio == 1.5
        assert bracket.status == "pending"


class TestTradeExitResult:
    """Test cases for TradeExitResult dataclass."""
    
    def test_trade_exit_result_creation(self):
        """Test TradeExitResult creation."""
        result = TradeExitResult(
            success=True,
            bracket_order_id="bracket_123",
            take_profit_placed=True,
            stop_loss_placed=True,
            processing_time=0.1
        )
        
        assert result.success is True
        assert result.bracket_order_id == "bracket_123"
        assert result.take_profit_placed is True
        assert result.stop_loss_placed is True
        assert result.processing_time == 0.1
        assert result.error_message is None


class TestFactoryFunction:
    """Test cases for factory function."""
    
    def test_create_trade_exit_service(self):
        """Test trade exit service factory function."""
        mock_execution_engine = Mock(spec=ExecutionEngine)
        mock_risk_manager = Mock(spec=RiskManager)
        config = {"risk_reward_ratio": 2.0}
        
        service = create_trade_exit_service(mock_execution_engine, mock_risk_manager, config)
        
        assert isinstance(service, TradeExitService)
        assert service.execution_engine == mock_execution_engine
        assert service.risk_manager == mock_risk_manager
        assert service.default_risk_reward_ratio == 2.0


class TestIntegration:
    """Integration tests for TradeExitService."""
    
    @pytest.mark.asyncio
    async def test_full_bracket_order_workflow(self):
        """Test complete bracket order workflow."""
        # Setup
        mock_execution_engine = Mock(spec=ExecutionEngine)
        mock_risk_manager = Mock(spec=RiskManager)
        mock_risk_manager.positions = {}
        mock_risk_manager.close_position = Mock(return_value=50.0)
        
        service = TradeExitService(mock_execution_engine, mock_risk_manager, {})
        
        # Create entry order
        entry_order = Order(
            id="entry_123",
            symbol="BTC",
            side="buy",
            quantity=1.0,
            price=100.0,
            order_type="market",
            status="filled",
            filled_quantity=1.0,
            average_fill_price=100.0,
            created_at=datetime.now()
        )
        
        # Mock successful order submissions
        mock_execution_engine.submit_order.return_value = ExecutionResult(
            order_id="test_id",
            status=OrderStatus.ACKNOWLEDGED
        )
        
        # Create bracket order
        result = await service.create_bracket_order(
            entry_order=entry_order,
            entry_price=100.0,
            atr=2.0,
            risk_reward_ratio=1.5
        )
        
        # Verify bracket order was created
        assert result.success is True
        assert len(service.active_brackets) == 1
        
        # Simulate take profit fill
        fill_data = {"average_fill_price": 106.0, "filled_quantity": 1.0}
        await service.handle_bracket_fill("tp_entry_123", fill_data)
        
        # Verify position was closed
        mock_risk_manager.close_position.assert_called_once_with("BTC", 106.0)
