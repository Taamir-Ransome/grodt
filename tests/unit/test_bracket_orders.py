"""
Unit tests for Bracket Order functionality in ExecutionEngine.

Tests the enhanced ExecutionEngine for bracket order tracking,
OCO emulation, and bracket order management.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from grodtd.execution.engine import ExecutionEngine, OrderStatus
from grodtd.risk.manager import RiskManager, RiskLimits
from grodtd.connectors.robinhood import Order


class TestExecutionEngineBracketOrders:
    """Test cases for ExecutionEngine bracket order functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create mock components
        self.mock_connector = Mock()
        self.mock_risk_manager = Mock(spec=RiskManager)
        
        # Create execution engine
        self.engine = ExecutionEngine(self.mock_connector, self.mock_risk_manager)
    
    def test_initialization(self):
        """Test execution engine initialization with bracket tracking."""
        assert hasattr(self.engine, 'bracket_orders')
        assert hasattr(self.engine, 'bracket_callbacks')
        assert isinstance(self.engine.bracket_orders, dict)
        assert isinstance(self.engine.bracket_callbacks, list)
        assert len(self.engine.bracket_orders) == 0
        assert len(self.engine.bracket_callbacks) == 0
    
    def test_register_bracket_order(self):
        """Test bracket order registration."""
        entry_order_id = "entry_123"
        tp_order_id = "tp_123"
        sl_order_id = "sl_123"
        
        # Register bracket order
        self.engine.register_bracket_order(entry_order_id, tp_order_id, sl_order_id)
        
        # Verify registration
        assert entry_order_id in self.engine.bracket_orders
        assert self.engine.bracket_orders[entry_order_id] == [tp_order_id, sl_order_id]
    
    def test_register_multiple_bracket_orders(self):
        """Test registering multiple bracket orders."""
        # Register first bracket
        self.engine.register_bracket_order("entry_1", "tp_1", "sl_1")
        
        # Register second bracket
        self.engine.register_bracket_order("entry_2", "tp_2", "sl_2")
        
        # Verify both are registered
        assert len(self.engine.bracket_orders) == 2
        assert "entry_1" in self.engine.bracket_orders
        assert "entry_2" in self.engine.bracket_orders
        assert self.engine.bracket_orders["entry_1"] == ["tp_1", "sl_1"]
        assert self.engine.bracket_orders["entry_2"] == ["tp_2", "sl_2"]
    
    @pytest.mark.asyncio
    async def test_handle_bracket_fill_take_profit(self):
        """Test handling take profit fill with OCO behavior."""
        # Register bracket order
        entry_order_id = "entry_123"
        tp_order_id = "tp_123"
        sl_order_id = "sl_123"
        
        self.engine.register_bracket_order(entry_order_id, tp_order_id, sl_order_id)
        
        # Add orders to active orders
        self.engine.active_orders[tp_order_id] = Mock()
        self.engine.active_orders[sl_order_id] = Mock()
        
        # Mock cancel order
        self.engine.cancel_order = AsyncMock(return_value=True)
        
        # Handle take profit fill
        fill_data = {"average_fill_price": 106.0, "filled_quantity": 1.0}
        await self.engine.handle_bracket_fill(tp_order_id, fill_data)
        
        # Verify stop loss was cancelled
        self.engine.cancel_order.assert_called_once_with(sl_order_id)
        
        # Verify bracket was removed
        assert entry_order_id not in self.engine.bracket_orders
    
    @pytest.mark.asyncio
    async def test_handle_bracket_fill_stop_loss(self):
        """Test handling stop loss fill with OCO behavior."""
        # Register bracket order
        entry_order_id = "entry_123"
        tp_order_id = "tp_123"
        sl_order_id = "sl_123"
        
        self.engine.register_bracket_order(entry_order_id, tp_order_id, sl_order_id)
        
        # Add orders to active orders
        self.engine.active_orders[tp_order_id] = Mock()
        self.engine.active_orders[sl_order_id] = Mock()
        
        # Mock cancel order
        self.engine.cancel_order = AsyncMock(return_value=True)
        
        # Handle stop loss fill
        fill_data = {"average_fill_price": 96.0, "filled_quantity": 1.0}
        await self.engine.handle_bracket_fill(sl_order_id, fill_data)
        
        # Verify take profit was cancelled
        self.engine.cancel_order.assert_called_once_with(tp_order_id)
        
        # Verify bracket was removed
        assert entry_order_id not in self.engine.bracket_orders
    
    @pytest.mark.asyncio
    async def test_handle_bracket_fill_unknown_order(self):
        """Test handling fill for unknown order."""
        # Register bracket order
        self.engine.register_bracket_order("entry_123", "tp_123", "sl_123")
        
        # Handle fill for unknown order
        fill_data = {"average_fill_price": 100.0, "filled_quantity": 1.0}
        await self.engine.handle_bracket_fill("unknown_order", fill_data)
        
        # Verify bracket still exists (no cancellation)
        assert "entry_123" in self.engine.bracket_orders
    
    @pytest.mark.asyncio
    async def test_bracket_callback_registration(self):
        """Test bracket callback registration and triggering."""
        callback_called = False
        callback_data = None
        
        async def test_callback(event_type, data):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = (event_type, data)
        
        # Add callback
        self.engine.add_bracket_callback(test_callback)
        
        # Trigger callback
        test_data = {"test": "data"}
        await self.engine._trigger_bracket_callbacks("test_event", test_data)
        
        # Verify callback was called
        assert callback_called is True
        assert callback_data[0] == "test_event"
        assert callback_data[1] == test_data
    
    @pytest.mark.asyncio
    async def test_bracket_callback_error_handling(self):
        """Test bracket callback error handling."""
        async def failing_callback(event_type, data):
            raise Exception("Callback error")
        
        async def working_callback(event_type, data):
            return "success"
        
        # Add both callbacks
        self.engine.add_bracket_callback(failing_callback)
        self.engine.add_bracket_callback(working_callback)
        
        # Trigger callbacks (should not raise exception)
        test_data = {"test": "data"}
        await self.engine._trigger_bracket_callbacks("test_event", test_data)
        
        # Should complete without error
        assert True  # Test passes if no exception is raised
    
    def test_get_bracket_summary(self):
        """Test getting bracket order summary."""
        # Register some bracket orders
        self.engine.register_bracket_order("entry_1", "tp_1", "sl_1")
        self.engine.register_bracket_order("entry_2", "tp_2", "sl_2")
        
        # Get summary
        summary = self.engine.get_bracket_summary()
        
        # Verify summary
        assert summary["active_brackets"] == 2
        assert len(summary["brackets"]) == 2
        
        # Check bracket details
        bracket_entries = [b["entry_order_id"] for b in summary["brackets"]]
        assert "entry_1" in bracket_entries
        assert "entry_2" in bracket_entries
    
    def test_get_execution_summary_with_brackets(self):
        """Test execution summary includes bracket information."""
        # Register a bracket order
        self.engine.register_bracket_order("entry_123", "tp_123", "sl_123")
        
        # Get execution summary
        summary = self.engine.get_execution_summary()
        
        # Verify bracket information is included
        assert "active_brackets" in summary
        assert summary["active_brackets"] == 1
    
    @pytest.mark.asyncio
    async def test_bracket_fill_with_callbacks(self):
        """Test bracket fill triggers callbacks."""
        callback_called = False
        callback_data = None
        
        async def test_callback(event_type, data):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = (event_type, data)
        
        # Add callback
        self.engine.add_bracket_callback(test_callback)
        
        # Register bracket order
        entry_order_id = "entry_123"
        tp_order_id = "tp_123"
        sl_order_id = "sl_123"
        
        self.engine.register_bracket_order(entry_order_id, tp_order_id, sl_order_id)
        
        # Add orders to active orders
        self.engine.active_orders[tp_order_id] = Mock()
        self.engine.active_orders[sl_order_id] = Mock()
        
        # Mock cancel order
        self.engine.cancel_order = AsyncMock(return_value=True)
        
        # Handle bracket fill
        fill_data = {"average_fill_price": 106.0, "filled_quantity": 1.0}
        await self.engine.handle_bracket_fill(tp_order_id, fill_data)
        
        # Verify callback was triggered
        assert callback_called is True
        assert callback_data[0] == "bracket_filled"
        assert callback_data[1]["entry_order_id"] == entry_order_id
        assert callback_data[1]["filled_order_id"] == tp_order_id
        assert callback_data[1]["fill_data"] == fill_data


class TestBracketOrderIntegration:
    """Integration tests for bracket order functionality."""
    
    @pytest.mark.asyncio
    async def test_complete_bracket_order_lifecycle(self):
        """Test complete bracket order lifecycle."""
        # Setup
        mock_connector = Mock()
        mock_risk_manager = Mock(spec=RiskManager)
        engine = ExecutionEngine(mock_connector, mock_risk_manager)
        
        # Create orders
        entry_order = Order(
            id="entry_123",
            symbol="BTC",
            side="buy",
            quantity=1.0,
            price=100.0,
            order_type="market",
            status="filled",
            created_at=datetime.now()
        )
        
        tp_order = Order(
            id="tp_123",
            symbol="BTC",
            side="sell",
            quantity=1.0,
            price=106.0,
            order_type="limit",
            status="pending",
            created_at=datetime.now()
        )
        
        sl_order = Order(
            id="sl_123",
            symbol="BTC",
            side="sell",
            quantity=1.0,
            price=96.0,
            order_type="stop",
            status="pending",
            created_at=datetime.now()
        )
        
        # Register bracket order
        engine.register_bracket_order("entry_123", "tp_123", "sl_123")
        
        # Add orders to active orders
        engine.active_orders["tp_123"] = tp_order
        engine.active_orders["sl_123"] = sl_order
        
        # Mock cancel order
        engine.cancel_order = AsyncMock(return_value=True)
        
        # Simulate take profit fill
        fill_data = {"average_fill_price": 106.0, "filled_quantity": 1.0}
        await engine.handle_bracket_fill("tp_123", fill_data)
        
        # Verify stop loss was cancelled
        engine.cancel_order.assert_called_once_with("sl_123")
        
        # Verify bracket was removed
        assert "entry_123" not in engine.bracket_orders
    
    def test_multiple_bracket_orders_management(self):
        """Test managing multiple bracket orders."""
        # Setup
        mock_connector = Mock()
        mock_risk_manager = Mock(spec=RiskManager)
        engine = ExecutionEngine(mock_connector, mock_risk_manager)
        
        # Register multiple bracket orders
        engine.register_bracket_order("entry_1", "tp_1", "sl_1")
        engine.register_bracket_order("entry_2", "tp_2", "sl_2")
        engine.register_bracket_order("entry_3", "tp_3", "sl_3")
        
        # Verify all are registered
        assert len(engine.bracket_orders) == 3
        
        # Get summary
        summary = engine.get_bracket_summary()
        assert summary["active_brackets"] == 3
        
        # Verify execution summary includes brackets
        exec_summary = engine.get_execution_summary()
        assert exec_summary["active_brackets"] == 3
