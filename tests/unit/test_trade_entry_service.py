"""
Unit tests for Trade Entry Service.

Tests the TradeEntryService class for complete trade entry functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from grodtd.execution.trade_entry_service import TradeEntryService, TradeEntryResult, create_trade_entry_service
from grodtd.strategies.base import Signal
from grodtd.connectors.robinhood import RobinhoodConnector, RobinhoodAuth
from grodtd.risk.manager import RiskManager, RiskLimits
from grodtd.storage.interfaces import OHLCVBar


class TestTradeEntryService:
    """Test cases for TradeEntryService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create mock components
        self.mock_connector = Mock(spec=RobinhoodConnector)
        self.mock_risk_manager = Mock(spec=RiskManager)
        
        # Mock risk manager methods
        self.mock_risk_manager.get_risk_summary.return_value = {
            "account_balance": 10000.0,
            "daily_pnl": 0.0,
            "active_positions": 0
        }
        
        self.config = {
            'strategy': {
                'ema_period': 9,
                'signal_cooldown_seconds': 60,
                'min_signal_strength': 0.6
            }
        }
        
        self.service = TradeEntryService(
            self.mock_connector,
            self.mock_risk_manager,
            "BTC",
            self.config
        )
    
    def test_initialization(self):
        """Test service initialization."""
        assert self.service.connector == self.mock_connector
        assert self.service.risk_manager == self.mock_risk_manager
        assert self.service.symbol == "BTC"
        assert not self.service.is_running
        assert self.service.last_processing_time is None
    
    @pytest.mark.asyncio
    async def test_start_service(self):
        """Test starting the service."""
        await self.service.start()
        
        assert self.service.is_running == True
    
    @pytest.mark.asyncio
    async def test_start_service_already_running(self):
        """Test starting service when already running."""
        self.service.is_running = True
        
        # Should not raise exception
        await self.service.start()
    
    @pytest.mark.asyncio
    async def test_stop_service(self):
        """Test stopping the service."""
        self.service.is_running = True
        
        await self.service.stop()
        
        assert self.service.is_running == False
    
    @pytest.mark.asyncio
    async def test_stop_service_not_running(self):
        """Test stopping service when not running."""
        # Should not raise exception
        await self.service.stop()
    
    @pytest.mark.asyncio
    async def test_process_market_data_not_running(self):
        """Test processing market data when service not running."""
        bar = OHLCVBar(
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000.0
        )
        
        result = await self.service.process_market_data(bar)
        
        assert result.success == False
        assert "Service is not running" in result.errors
        assert result.signals_generated == 0
        assert result.orders_placed == 0
    
    @pytest.mark.asyncio
    async def test_process_market_data_success(self):
        """Test successful market data processing."""
        # Start service
        await self.service.start()
        
        # Create market data bar
        bar = OHLCVBar(
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000.0
        )
        
        # Mock strategy to return no signals
        with patch.object(self.service.strategy, 'generate_signals', return_value=[]):
            result = await self.service.process_market_data(bar)
        
        assert result.success == True
        assert result.signals_generated == 0
        assert result.orders_placed == 0
        assert len(result.errors) == 0
        assert result.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_process_market_data_with_signals(self):
        """Test market data processing with signal generation."""
        # Start service
        await self.service.start()
        
        # Create market data bar
        bar = OHLCVBar(
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000.0
        )
        
        # Mock strategy to return signals
        mock_signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=102.0,
            timestamp=datetime.now()
        )
        
        with patch.object(self.service.strategy, 'generate_signals', return_value=[mock_signal]):
            with patch.object(self.service.signal_service, 'process_multiple_signals') as mock_process:
                # Mock successful signal processing
                from grodtd.execution.signal_service import SignalProcessingResult
                mock_process.return_value = [
                    SignalProcessingResult(
                        signal=mock_signal,
                        order_id="order_123",
                        success=True
                    )
                ]
                
                result = await self.service.process_market_data(bar)
        
        assert result.success == True
        assert result.signals_generated == 1
        assert result.orders_placed == 1
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_process_market_data_with_errors(self):
        """Test market data processing with errors."""
        # Start service
        await self.service.start()
        
        # Create market data bar
        bar = OHLCVBar(
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000.0
        )
        
        # Mock strategy to raise exception
        with patch.object(self.service.strategy, 'generate_signals', side_effect=Exception("Strategy error")):
            result = await self.service.process_market_data(bar)
        
        assert result.success == False
        assert len(result.errors) > 0
        assert "Strategy error" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_get_service_status(self):
        """Test getting service status."""
        # Start service
        await self.service.start()
        
        status = await self.service.get_service_status()
        
        assert "service_running" in status
        assert "symbol" in status
        assert "last_processing_time" in status
        assert "strategy" in status
        assert "signals" in status
        assert "execution" in status
        assert "risk" in status
        
        assert status["service_running"] == True
        assert status["symbol"] == "BTC"
    
    @pytest.mark.asyncio
    async def test_cancel_all_signals(self):
        """Test cancelling all signals."""
        # Start service
        await self.service.start()
        
        # Mock active signals
        with patch.object(self.service.signal_service, 'get_active_signals', return_value={"BTC": Mock()}):
            with patch.object(self.service.signal_service, 'cancel_signal', return_value=True) as mock_cancel:
                cancelled_count = await self.service.cancel_all_signals()
        
        assert cancelled_count == 1
        mock_cancel.assert_called_once_with("BTC")
    
    @pytest.mark.asyncio
    async def test_on_order_fill(self):
        """Test order fill event handling."""
        # Start service
        await self.service.start()
        
        # Create mock order
        mock_order = Mock()
        mock_order.symbol = "BTC"
        mock_order.side = "buy"
        mock_order.average_fill_price = 100.0
        mock_order.filled_quantity = 1.0
        mock_order.filled_at = datetime.now()
        
        # Mock strategy on_fill method
        with patch.object(self.service.strategy, 'on_fill', new_callable=AsyncMock) as mock_on_fill:
            await self.service._on_order_fill("order_filled", mock_order)
        
        # Verify strategy was notified
        mock_on_fill.assert_called_once()
        call_args = mock_on_fill.call_args
        signal = call_args[0][0]
        fill_data = call_args[0][1]
        
        assert signal.symbol == "BTC"
        assert signal.side == "buy"
        assert signal.price == 100.0
        assert fill_data["order_id"] == mock_order.id
        assert fill_data["quantity"] == 1.0
    
    @pytest.mark.asyncio
    async def test_on_signal_processed(self):
        """Test signal processed event handling."""
        # Start service
        await self.service.start()
        
        mock_signal = Signal(
            symbol="BTC",
            side="buy",
            strength=0.8,
            price=100.0,
            timestamp=datetime.now()
        )
        
        # Should not raise exception
        await self.service._on_signal_processed("signal_processed", mock_signal, None)
    
    @pytest.mark.asyncio
    async def test_trigger_processing_callbacks(self):
        """Test processing callback triggering."""
        # Start service
        await self.service.start()
        
        # Add mock callback
        mock_callback = AsyncMock()
        self.service.add_processing_callback(mock_callback)
        
        # Trigger callback
        test_data = {"test": "data"}
        await self.service._trigger_processing_callbacks("test_event", test_data)
        
        # Verify callback was called
        mock_callback.assert_called_once_with("test_event", test_data)
    
    def test_add_processing_callback(self):
        """Test adding processing callback."""
        mock_callback = Mock()
        
        self.service.add_processing_callback(mock_callback)
        
        assert mock_callback in self.service.processing_callbacks


class TestTradeEntryServiceIntegration:
    """Integration tests for TradeEntryService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_connector = Mock(spec=RobinhoodConnector)
        self.mock_risk_manager = Mock(spec=RiskManager)
        
        # Mock risk manager methods
        self.mock_risk_manager.get_risk_summary.return_value = {
            "account_balance": 10000.0,
            "daily_pnl": 0.0,
            "active_positions": 0
        }
        
        self.config = {
            'strategy': {
                'ema_period': 9,
                'signal_cooldown_seconds': 0,  # No cooldown for testing
                'min_signal_strength': 0.1  # Low threshold for testing
            }
        }
        
        self.service = TradeEntryService(
            self.mock_connector,
            self.mock_risk_manager,
            "BTC",
            self.config
        )
    
    @pytest.mark.asyncio
    async def test_full_trade_entry_flow(self):
        """Test complete trade entry flow."""
        # Start service
        await self.service.start()
        
        # Create market data that should trigger a signal
        bar = OHLCVBar(
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000.0
        )
        
        # Mock the entire flow
        with patch.object(self.service.strategy, 'prepare', new_callable=AsyncMock):
            with patch.object(self.service.strategy, 'generate_signals', return_value=[]):
                with patch.object(self.service.signal_service, 'process_multiple_signals', return_value=[]):
                    result = await self.service.process_market_data(bar)
        
        assert result.success == True
        assert result.signals_generated == 0
        assert result.orders_placed == 0
        assert len(result.errors) == 0


def test_create_trade_entry_service():
    """Test factory function for creating trade entry service."""
    mock_connector = Mock(spec=RobinhoodConnector)
    risk_limits = RiskLimits()
    account_balance = 10000.0
    symbol = "BTC"
    config = {'strategy': {'ema_period': 9}}
    
    service = create_trade_entry_service(
        mock_connector,
        risk_limits,
        account_balance,
        symbol,
        config
    )
    
    assert isinstance(service, TradeEntryService)
    assert service.connector == mock_connector
    assert service.symbol == symbol
    assert service.config == config
