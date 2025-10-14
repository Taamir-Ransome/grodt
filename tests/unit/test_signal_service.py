"""
Unit tests for Trade Signal Service.

Tests the TradeSignalService class for signal processing and order creation.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from grodtd.execution.signal_service import TradeSignalService, SignalProcessingResult, create_signal_service
from grodtd.strategies.base import Signal
from grodtd.execution.engine import ExecutionEngine, ExecutionResult, OrderStatus
from grodtd.risk.manager import RiskManager, RiskLimits, Position
from grodtd.connectors.robinhood import Order


class TestTradeSignalService:
    """Test cases for TradeSignalService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_execution_engine = Mock(spec=ExecutionEngine)
        self.mock_risk_manager = Mock(spec=RiskManager)
        
        # Mock risk manager methods
        self.mock_risk_manager.get_risk_summary.return_value = {
            "account_balance": 10000.0
        }
        self.mock_risk_manager.calculate_position_size.return_value = 100.0
        
        self.service = TradeSignalService(self.mock_execution_engine, self.mock_risk_manager)
    
    def test_initialization(self):
        """Test service initialization."""
        assert self.service.execution_engine == self.mock_execution_engine
        assert self.service.risk_manager == self.mock_risk_manager
        assert len(self.service.active_signals) == 0
        assert len(self.service.signal_callbacks) == 0
    
    def test_validate_signal_valid(self):
        """Test signal validation with valid signal."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        result = self.service._validate_signal(signal)
        assert result["valid"] == True
        assert result["reason"] == "Signal is valid"
    
    def test_validate_signal_invalid_strength(self):
        """Test signal validation with low strength."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.3,  # Below minimum
            price=100.0,
            timestamp=datetime.now()
        )
        
        result = self.service._validate_signal(signal)
        assert result["valid"] == False
        assert "strength too low" in result["reason"]
    
    def test_validate_signal_invalid_price(self):
        """Test signal validation with invalid price."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=0.0,  # Invalid price
            timestamp=datetime.now()
        )
        
        result = self.service._validate_signal(signal)
        assert result["valid"] == False
        assert "Invalid price" in result["reason"]
    
    def test_validate_signal_invalid_side(self):
        """Test signal validation with invalid side."""
        signal = Signal(
            symbol="BTC",
            side="invalid",  # Invalid side
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        result = self.service._validate_signal(signal)
        assert result["valid"] == False
        assert "Invalid signal side" in result["reason"]
    
    def test_validate_signal_invalid_symbol(self):
        """Test signal validation with invalid symbol."""
        signal = Signal(
            symbol="",  # Empty symbol
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        result = self.service._validate_signal(signal)
        assert result["valid"] == False
        assert "Invalid symbol" in result["reason"]
    
    def test_has_conflicting_signal_no_conflict(self):
        """Test conflict detection when no conflict exists."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        # No active signals
        assert not self.service._has_conflicting_signal(signal)
    
    def test_has_conflicting_signal_same_side(self):
        """Test conflict detection with same side signal."""
        # Add existing signal
        existing_signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=95.0,
            timestamp=datetime.now()
        )
        self.service.active_signals["BTC"] = existing_signal
        
        new_signal = Signal(
            symbol="BTC",
            side="buy",  # Same side
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        # Should not conflict (same side)
        assert not self.service._has_conflicting_signal(new_signal)
    
    def test_has_conflicting_signal_opposite_side(self):
        """Test conflict detection with opposite side signal."""
        # Add existing signal
        existing_signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=95.0,
            timestamp=datetime.now()
        )
        self.service.active_signals["BTC"] = existing_signal
        
        new_signal = Signal(
            symbol="BTC",
            side="sell",  # Opposite side
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        # Should conflict (opposite side)
        assert self.service._has_conflicting_signal(new_signal)
    
    def test_calculate_position_size(self):
        """Test position size calculation."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            stop_loss=98.0,
            timestamp=datetime.now()
        )
        
        # Mock risk manager calculation
        self.mock_risk_manager.calculate_position_size.return_value = 50.0
        
        position_size = self.service._calculate_position_size(signal)
        assert position_size == 50.0
        
        # Verify risk manager was called correctly
        self.mock_risk_manager.calculate_position_size.assert_called_once_with(
            symbol="BTC",
            entry_price=100.0,
            stop_loss=98.0
        )
    
    def test_calculate_position_size_no_stop_loss(self):
        """Test position size calculation without stop loss."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            stop_loss=None,  # No stop loss
            timestamp=datetime.now()
        )
        
        # Mock risk manager calculation
        self.mock_risk_manager.calculate_position_size.return_value = 25.0
        
        position_size = self.service._calculate_position_size(signal)
        assert position_size == 25.0
    
    def test_create_order_from_signal(self):
        """Test order creation from signal."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            stop_loss=98.0,
            timestamp=datetime.now()
        )
        
        # Mock position size calculation
        with patch.object(self.service, '_calculate_position_size', return_value=50.0):
            order = self.service._create_order_from_signal(signal)
        
        assert order is not None
        assert order.symbol == "BTC"
        assert order.side == "buy"
        assert order.quantity == 50.0
        assert order.price == 100.0
        assert order.order_type == "market"
        assert order.status == "pending"
    
    def test_create_order_from_signal_invalid_size(self):
        """Test order creation with invalid position size."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            stop_loss=98.0,
            timestamp=datetime.now()
        )
        
        # Mock invalid position size
        with patch.object(self.service, '_calculate_position_size', return_value=0.0):
            order = self.service._create_order_from_signal(signal)
        
        assert order is None
    
    @pytest.mark.asyncio
    async def test_process_signal_success(self):
        """Test successful signal processing."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        # Mock execution result
        execution_result = ExecutionResult(
            order_id="order_123",
            status=OrderStatus.ACKNOWLEDGED,
            execution_time=datetime.now()
        )
        self.mock_execution_engine.submit_order = AsyncMock(return_value=execution_result)
        
        result = await self.service.process_signal(signal)
        
        assert result.success == True
        assert result.order_id == "order_123"
        assert result.execution_result == execution_result
        assert result.error_message is None
        
        # Verify signal was added to active signals
        assert "BTC" in self.service.active_signals
    
    @pytest.mark.asyncio
    async def test_process_signal_validation_failure(self):
        """Test signal processing with validation failure."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.3,  # Low strength
            price=100.0,
            timestamp=datetime.now()
        )
        
        result = await self.service.process_signal(signal)
        
        assert result.success == False
        assert "strength too low" in result.error_message
        assert result.order_id is None
    
    @pytest.mark.asyncio
    async def test_process_signal_conflict(self):
        """Test signal processing with conflicting signal."""
        # Add existing signal
        existing_signal = Signal(
            symbol="BTC",
            side="sell",
            strength=0.8,
            price=95.0,
            timestamp=datetime.now()
        )
        self.service.active_signals["BTC"] = existing_signal
        
        new_signal = Signal(
            symbol="BTC",
            side="buy",  # Opposite side
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        result = await self.service.process_signal(new_signal)
        
        assert result.success == False
        assert "Conflicting signal" in result.error_message
    
    @pytest.mark.asyncio
    async def test_process_signal_execution_failure(self):
        """Test signal processing with execution failure."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        # Mock execution failure
        execution_result = ExecutionResult(
            order_id="order_123",
            status=OrderStatus.REJECTED,
            error_message="Insufficient funds"
        )
        self.mock_execution_engine.submit_order = AsyncMock(return_value=execution_result)
        
        result = await self.service.process_signal(signal)
        
        assert result.success == False
        assert result.error_message == "Insufficient funds"
    
    @pytest.mark.asyncio
    async def test_process_multiple_signals(self):
        """Test processing multiple signals."""
        signals = [
            Signal(symbol="BTC", side="buy", strength=0.8, price=100.0, timestamp=datetime.now()),
            Signal(symbol="ETH", side="sell", strength=0.7, price=200.0, timestamp=datetime.now())
        ]
        
        # Mock execution results
        execution_result = ExecutionResult(
            order_id="order_123",
            status=OrderStatus.ACKNOWLEDGED,
            execution_time=datetime.now()
        )
        self.mock_execution_engine.submit_order = AsyncMock(return_value=execution_result)
        
        results = await self.service.process_multiple_signals(signals)
        
        assert len(results) == 2
        assert all(result.success for result in results)
    
    @pytest.mark.asyncio
    async def test_cancel_signal_success(self):
        """Test successful signal cancellation."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        self.service.active_signals["BTC"] = signal
        
        result = await self.service.cancel_signal("BTC")
        
        assert result == True
        assert "BTC" not in self.service.active_signals
    
    @pytest.mark.asyncio
    async def test_cancel_signal_not_found(self):
        """Test signal cancellation when signal not found."""
        result = await self.service.cancel_signal("BTC")
        
        assert result == False
    
    def test_get_active_signals(self):
        """Test getting active signals."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        self.service.active_signals["BTC"] = signal
        
        active_signals = self.service.get_active_signals()
        assert len(active_signals) == 1
        assert active_signals["BTC"] == signal
    
    def test_get_signal_summary(self):
        """Test getting signal summary."""
        signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        self.service.active_signals["BTC"] = signal
        
        summary = self.service.get_signal_summary()
        
        assert "active_signals" in summary
        assert "max_concurrent_signals" in summary
        assert "signals" in summary
        assert summary["active_signals"] == 1
        assert len(summary["signals"]) == 1


def test_create_signal_service():
    """Test factory function for creating signal service."""
    mock_execution_engine = Mock(spec=ExecutionEngine)
    mock_risk_manager = Mock(spec=RiskManager)
    
    service = create_signal_service(mock_execution_engine, mock_risk_manager)
    
    assert isinstance(service, TradeSignalService)
    assert service.execution_engine == mock_execution_engine
    assert service.risk_manager == mock_risk_manager
