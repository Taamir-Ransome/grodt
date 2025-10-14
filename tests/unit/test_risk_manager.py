"""
Unit tests for risk manager.
"""

import pytest
from datetime import datetime, timedelta
from grodtd.risk.manager import RiskManager, RiskLimits, Position


class TestRiskManager:
    """Test cases for RiskManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.limits = RiskLimits()
        self.account_balance = 10000.0
        self.risk_manager = RiskManager(self.limits, self.account_balance)
    
    def test_calculate_position_size(self):
        """Test position size calculation."""
        symbol = "BTC-USD"
        entry_price = 50000.0
        stop_loss = 49000.0
        
        position_size = self.risk_manager.calculate_position_size(
            symbol, entry_price, stop_loss
        )
        
        # Expected: risk_per_trade = 0.0075 * 10000 = 75
        # Risk per unit = 50000 - 49000 = 1000
        # Risk-based position size = 75 / 1000 = 0.075
        # Max position size = 10% of account / entry_price = 1000 / 50000 = 0.02
        # Final position size = min(0.075, 0.02) = 0.02
        expected_size = min(75.0 / 1000.0, 1000.0 / 50000.0)  # min(risk-based, max-size)
        assert abs(position_size - expected_size) < 0.001
    
    def test_can_open_position(self):
        """Test position opening checks."""
        symbol = "BTC-USD"
        
        # Should be able to open position initially
        can_open, reason = self.risk_manager.can_open_position(symbol)
        assert can_open
        assert reason == "Position can be opened"
    
    def test_max_concurrent_positions(self):
        """Test maximum concurrent positions limit."""
        # Add positions up to the limit
        for i in range(self.limits.max_concurrent_positions):
            symbol = f"SYMBOL-{i}"
            position = Position(
                symbol=symbol,
                quantity=1.0,
                entry_price=100.0,
                current_price=100.0,
                created_at=datetime.now()
            )
            self.risk_manager.add_position(position)
        
        # Should not be able to open another position
        can_open, reason = self.risk_manager.can_open_position("NEW-SYMBOL")
        assert not can_open
        assert "Maximum concurrent positions" in reason
    
    def test_daily_loss_cap(self):
        """Test daily loss cap enforcement."""
        # Set daily PnL to exceed loss cap
        self.risk_manager.daily_pnl = -self.account_balance * self.limits.daily_loss_cap - 100
        
        can_open, reason = self.risk_manager.can_open_position("BTC-USD")
        assert not can_open
        assert "Daily loss cap exceeded" in reason
    
    def test_cooldown_period(self):
        """Test cooldown after consecutive losses."""
        # Set consecutive losses to trigger cooldown
        self.risk_manager.consecutive_losses = self.limits.cooldown_after_losses
        self.risk_manager.last_loss_time = datetime.now()
        
        can_open, reason = self.risk_manager.can_open_position("BTC-USD")
        assert not can_open
        assert "cooldown period" in reason
    
    def test_position_management(self):
        """Test adding and closing positions."""
        symbol = "BTC-USD"
        position = Position(
            symbol=symbol,
            quantity=1.0,
            entry_price=50000.0,
            current_price=50000.0,
            created_at=datetime.now()
        )
        
        # Add position
        self.risk_manager.add_position(position)
        assert symbol in self.risk_manager.positions
        
        # Update position
        self.risk_manager.update_position(symbol, 51000.0)
        assert self.risk_manager.positions[symbol].current_price == 51000.0
        assert self.risk_manager.positions[symbol].unrealized_pnl == 1000.0
        
        # Close position
        realized_pnl = self.risk_manager.close_position(symbol, 52000.0)
        assert realized_pnl == 2000.0
        assert symbol not in self.risk_manager.positions
        assert self.risk_manager.daily_pnl == 2000.0
    
    def test_kill_switches(self):
        """Test kill switch conditions."""
        # Test slippage kill switch
        triggered = self.risk_manager.check_kill_switches(slippage=4.0, latency=100, api_failures=0)
        assert "slippage_threshold_exceeded" in triggered
        
        # Test latency kill switch
        triggered = self.risk_manager.check_kill_switches(slippage=1.0, latency=2000, api_failures=0)
        assert "latency_threshold_exceeded" in triggered
        
        # Test API failure kill switch
        triggered = self.risk_manager.check_kill_switches(slippage=1.0, latency=100, api_failures=6)
        assert "api_failure_threshold_exceeded" in triggered
    
    def test_risk_summary(self):
        """Test risk summary generation."""
        summary = self.risk_manager.get_risk_summary()
        
        assert "account_balance" in summary
        assert "daily_pnl" in summary
        assert "unrealized_pnl" in summary
        assert "total_pnl" in summary
        assert "consecutive_losses" in summary
        assert "active_positions" in summary
        assert "max_positions" in summary
        
        assert summary["account_balance"] == self.account_balance
        assert summary["active_positions"] == 0
        assert summary["max_positions"] == self.limits.max_concurrent_positions
