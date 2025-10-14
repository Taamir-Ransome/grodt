"""
Data interfaces for market data connectors.

This module provides abstract interfaces for market data operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Callable
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class OHLCVBar:
    """Represents a single OHLCV bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame creation."""
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


class MarketDataInterface(ABC):
    """Abstract interface for market data connectors."""
    
    @abstractmethod
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime, 
        interval: str = "1m"
    ) -> List[OHLCVBar]:
        """Get historical OHLCV data for a symbol."""
        pass
    
    @abstractmethod
    async def get_real_time_data(
        self, 
        symbol: str
    ) -> OHLCVBar:
        """Get current real-time OHLCV data for a symbol."""
        pass
    
    @abstractmethod
    async def subscribe_to_updates(
        self, 
        symbol: str, 
        callback: Callable
    ) -> None:
        """Subscribe to real-time data updates."""
        pass
