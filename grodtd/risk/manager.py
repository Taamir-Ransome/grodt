"""
Risk management system.

This module implements position sizing, risk limits, and kill switches
to protect capital and manage trading risk.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import pandas as pd


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    risk_per_trade: float = 0.0075  # 0.75% of equity per trade
    max_position_size: float = 0.1  # 10% of equity max per position
    daily_loss_cap: float = 0.03    # 3% of equity daily loss cap
    max_concurrent_positions: int = 3
    cooldown_after_losses: int = 3   # Cooldown after 3 consecutive losses
    cooldown_hours: int = 24
    atr_multiplier: float = 2.0      # ATR multiplier for stop distance


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    created_at: datetime = None


class RiskManager:
    """Manages trading risk and position sizing."""
    
    def __init__(self, limits: RiskLimits, account_balance: float):
        self.limits = limits
        self.account_balance = account_balance
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.last_loss_time: Optional[datetime] = None
        self.logger = logging.getLogger(__name__)
    
    def calculate_position_size(
        self, 
        symbol: str, 
        entry_price: float, 
        stop_loss: float,
        atr: Optional[float] = None
    ) -> float:
        """
        Calculate position size based on risk per trade.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            atr: Average True Range (optional)
        
        Returns:
            Position size in units
        """
        # Calculate risk per unit
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit <= 0:
            return 0.0
        
        # Calculate maximum risk amount
        max_risk_amount = self.account_balance * self.limits.risk_per_trade
        
        # Calculate position size
        position_size = max_risk_amount / risk_per_unit
        
        # Apply maximum position size limit
        max_position_value = self.account_balance * self.limits.max_position_size
        max_position_size = max_position_value / entry_price
        
        position_size = min(position_size, max_position_size)
        
        # Ensure position size is not negative
        position_size = max(0.0, position_size)
        
        self.logger.info(
            f"Calculated position size for {symbol}: {position_size:.4f} units "
            f"(risk: ${max_risk_amount:.2f})"
        )
        
        return position_size
    
    def can_open_position(self, symbol: str) -> Tuple[bool, str]:
        """
        Check if a new position can be opened.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Tuple of (can_open, reason)
        """
        # Check if already in cooldown
        if self._is_in_cooldown():
            return False, "In cooldown period after consecutive losses"
        
        # Check daily loss cap
        if self.daily_pnl <= -self.account_balance * self.limits.daily_loss_cap:
            return False, "Daily loss cap exceeded"
        
        # Check maximum concurrent positions
        if len(self.positions) >= self.limits.max_concurrent_positions:
            return False, "Maximum concurrent positions reached"
        
        # Check if position already exists
        if symbol in self.positions:
            return False, "Position already exists for this symbol"
        
        return True, "Position can be opened"
    
    def _is_in_cooldown(self) -> bool:
        """Check if currently in cooldown period."""
        if self.consecutive_losses < self.limits.cooldown_after_losses:
            return False
        
        if not self.last_loss_time:
            return False
        
        cooldown_end = self.last_loss_time + timedelta(hours=self.limits.cooldown_hours)
        return datetime.now() < cooldown_end
    
    def add_position(self, position: Position):
        """Add a new position."""
        self.positions[position.symbol] = position
        self.logger.info(f"Added position: {position.symbol} {position.quantity} @ {position.entry_price}")
    
    def update_position(self, symbol: str, current_price: float):
        """Update position with current price."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        position.current_price = current_price
        position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
        
        self.logger.debug(f"Updated position {symbol}: PnL ${position.unrealized_pnl:.2f}")
    
    def close_position(self, symbol: str, exit_price: float) -> float:
        """
        Close a position and return realized PnL.
        
        Args:
            symbol: Trading symbol
            exit_price: Exit price
        
        Returns:
            Realized PnL
        """
        if symbol not in self.positions:
            return 0.0
        
        position = self.positions[symbol]
        realized_pnl = (exit_price - position.entry_price) * position.quantity
        
        # Update daily PnL
        self.daily_pnl += realized_pnl
        
        # Track consecutive losses
        if realized_pnl < 0:
            self.consecutive_losses += 1
            self.last_loss_time = datetime.now()
        else:
            self.consecutive_losses = 0
        
        # Remove position
        del self.positions[symbol]
        
        self.logger.info(
            f"Closed position {symbol}: PnL ${realized_pnl:.2f} "
            f"(Daily PnL: ${self.daily_pnl:.2f})"
        )
        
        return realized_pnl
    
    def check_kill_switches(
        self, 
        slippage: float, 
        latency: float, 
        api_failures: int
    ) -> List[str]:
        """
        Check kill switch conditions.
        
        Args:
            slippage: Current slippage
            latency: Current latency in milliseconds
            api_failures: Number of consecutive API failures
        
        Returns:
            List of triggered kill switches
        """
        triggered = []
        
        # Slippage kill switch (3 sigma above baseline)
        if slippage > 3.0:  # TODO: Calculate actual 3-sigma threshold
            triggered.append("slippage_threshold_exceeded")
        
        # Latency kill switch
        if latency > 1000:  # 1 second
            triggered.append("latency_threshold_exceeded")
        
        # API failure kill switch
        if api_failures >= 5:
            triggered.append("api_failure_threshold_exceeded")
        
        # Daily loss cap kill switch
        if self.daily_pnl <= -self.account_balance * self.limits.daily_loss_cap:
            triggered.append("daily_loss_cap_exceeded")
        
        if triggered:
            self.logger.warning(f"Kill switches triggered: {triggered}")
        
        return triggered
    
    def get_risk_summary(self) -> Dict[str, float]:
        """Get current risk summary."""
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        
        return {
            "account_balance": self.account_balance,
            "daily_pnl": self.daily_pnl,
            "unrealized_pnl": total_unrealized_pnl,
            "total_pnl": self.daily_pnl + total_unrealized_pnl,
            "consecutive_losses": self.consecutive_losses,
            "active_positions": len(self.positions),
            "max_positions": self.limits.max_concurrent_positions,
        }


# Factory function for creating risk manager
def create_risk_manager(
    limits: RiskLimits, 
    account_balance: float
) -> RiskManager:
    """Create a new risk manager instance."""
    return RiskManager(limits, account_balance)
