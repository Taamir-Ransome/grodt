"""
Base strategy interface.

This module defines the base strategy interface that all trading strategies
must implement.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

import pandas as pd


@dataclass
class Signal:
    """Represents a trading signal."""
    symbol: str
    side: str  # 'buy' or 'sell'
    strength: float  # Signal strength (0.0 to 1.0)
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class StrategyState:
    """Represents the current state of a strategy."""
    symbol: str
    current_price: float
    position: Optional[Dict[str, Any]] = None
    indicators: Optional[Dict[str, float]] = None
    market_data: Optional[pd.DataFrame] = None
    timestamp: datetime = None


class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, name: str, symbol: str, config: Dict[str, Any]):
        self.name = name
        self.symbol = symbol
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.enabled = config.get("enabled", True)
    
    @abstractmethod
    async def prepare(self, state: StrategyState) -> None:
        """
        Prepare strategy for signal generation.
        
        This method is called before generate_signals to allow
        the strategy to precompute any necessary data.
        
        Args:
            state: Current strategy state
        """
        pass
    
    @abstractmethod
    async def generate_signals(self, state: StrategyState) -> List[Signal]:
        """
        Generate trading signals based on current state.
        
        Args:
            state: Current strategy state
        
        Returns:
            List of trading signals
        """
        pass
    
    @abstractmethod
    async def on_fill(self, signal: Signal, fill_data: Dict[str, Any]) -> None:
        """
        Handle order fill event.
        
        Args:
            signal: The signal that was filled
            fill_data: Fill information
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if strategy is enabled."""
        return self.enabled
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration."""
        return self.config
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update strategy configuration."""
        self.config.update(new_config)
        self.logger.info(f"Updated configuration for {self.name}")


class StrategyManager:
    """Manages multiple trading strategies."""
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_strategy(self, strategy: BaseStrategy):
        """Add a strategy to the manager."""
        self.strategies[strategy.name] = strategy
        self.logger.info(f"Added strategy: {strategy.name}")
    
    def remove_strategy(self, name: str):
        """Remove a strategy from the manager."""
        if name in self.strategies:
            del self.strategies[name]
            self.logger.info(f"Removed strategy: {name}")
    
    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Get a strategy by name."""
        return self.strategies.get(name)
    
    def get_enabled_strategies(self) -> List[BaseStrategy]:
        """Get all enabled strategies."""
        return [s for s in self.strategies.values() if s.is_enabled()]
    
    async def run_strategies(self, state: StrategyState) -> List[Signal]:
        """
        Run all enabled strategies and collect signals.
        
        Args:
            state: Current market state
        
        Returns:
            List of all generated signals
        """
        all_signals = []
        
        for strategy in self.get_enabled_strategies():
            try:
                # Prepare strategy
                await strategy.prepare(state)
                
                # Generate signals
                signals = await strategy.generate_signals(state)
                all_signals.extend(signals)
                
                self.logger.debug(f"Strategy {strategy.name} generated {len(signals)} signals")
                
            except Exception as e:
                self.logger.error(f"Error running strategy {strategy.name}: {e}")
        
        return all_signals
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get summary of all strategies."""
        return {
            "total_strategies": len(self.strategies),
            "enabled_strategies": len(self.get_enabled_strategies()),
            "strategies": [
                {
                    "name": name,
                    "symbol": strategy.symbol,
                    "enabled": strategy.is_enabled(),
                    "config": strategy.get_config()
                }
                for name, strategy in self.strategies.items()
            ]
        }


# Factory function for creating strategy manager
def create_strategy_manager() -> StrategyManager:
    """Create a new strategy manager."""
    return StrategyManager()
