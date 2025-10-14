"""
Data loader for historical OHLCV data.

This module handles fetching, normalizing, and storing historical
market data from various sources, primarily Robinhood Crypto API.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np
from grodtd.storage.interfaces import OHLCVBar, MarketDataInterface

if TYPE_CHECKING:
    from grodtd.connectors.robinhood import RobinhoodConnector


class DataLoader:
    """Handles loading and storing historical market data."""
    
    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.raw_dir = data_dir / "raw"
        self.features_dir = data_dir / "features"
        self.logger = logging.getLogger(__name__)
        
        # Create directories if they don't exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)
        
        # Real-time data buffers for 1-minute aggregation
        self._real_time_buffers: Dict[str, List[OHLCVBar]] = {}
        self._current_minute_bars: Dict[str, Optional[OHLCVBar]] = {}
    
    async def load_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m",
        connector: Optional["RobinhoodConnector"] = None
    ) -> pd.DataFrame:
        """Load historical OHLCV data for a symbol."""
        self.logger.info(f"Loading historical data for {symbol} from {start_date} to {end_date}")
        
        # Check if data already exists locally
        local_file = self.raw_dir / f"{symbol}_{interval}_{start_date.date()}_{end_date.date()}.parquet"
        
        if local_file.exists():
            self.logger.info(f"Loading existing data from {local_file}")
            return pd.read_parquet(local_file)
        
        # Fetch data from API if not available locally
        if connector is None:
            # TODO: Create connector with proper credentials
            raise ValueError("Connector is required for fetching new data")
        
        data = await self._fetch_data_from_api(
            connector, symbol, start_date, end_date, interval
        )
        
        # Store data locally
        self._store_data(data, local_file)
        
        return data
    
    async def _fetch_data_from_api(
        self,
        connector: RobinhoodConnector,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> pd.DataFrame:
        """Fetch data from the API."""
        # TODO: Implement actual API data fetching
        # For now, return empty DataFrame with proper structure
        self.logger.info(f"Fetching data from API for {symbol}")
        
        # Create empty DataFrame with proper structure
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        data = pd.DataFrame(columns=columns)
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        
        return data
    
    def _store_data(self, data: pd.DataFrame, file_path: Path):
        """Store data to Parquet file."""
        self.logger.info(f"Storing data to {file_path}")
        data.to_parquet(file_path, index=False)
    
    def load_cached_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m"
    ) -> Optional[pd.DataFrame]:
        """Load cached data if available."""
        local_file = self.raw_dir / f"{symbol}_{interval}_{start_date.date()}_{end_date.date()}.parquet"
        
        if local_file.exists():
            self.logger.info(f"Loading cached data from {local_file}")
            return pd.read_parquet(local_file)
        
        return None
    
    def get_available_data(self, symbol: str) -> List[Path]:
        """Get list of available data files for a symbol."""
        pattern = f"{symbol}_*.parquet"
        return list(self.raw_dir.glob(pattern))
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data files."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for file_path in self.raw_dir.glob("*.parquet"):
            if file_path.stat().st_mtime < cutoff_date.timestamp():
                self.logger.info(f"Removing old data file: {file_path}")
                file_path.unlink()
    
    def validate_ohlcv_data(self, data: pd.DataFrame) -> bool:
        """Validate OHLCV data completeness and integrity."""
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        # Check required columns exist
        if not all(col in data.columns for col in required_columns):
            self.logger.error(f"Missing required columns. Expected: {required_columns}")
            return False
        
        # Check for null values in critical columns
        critical_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in critical_columns:
            if data[col].isnull().any():
                self.logger.error(f"Null values found in {col} column")
                return False
        
        # Check OHLC relationships
        invalid_ohlc = (
            (data['high'] < data['low']) |
            (data['high'] < data['open']) |
            (data['high'] < data['close']) |
            (data['low'] > data['open']) |
            (data['low'] > data['close'])
        )
        
        if invalid_ohlc.any():
            self.logger.error("Invalid OHLC relationships found")
            return False
        
        # Check volume is non-negative
        if (data['volume'] < 0).any():
            self.logger.error("Negative volume values found")
            return False
        
        self.logger.info("OHLCV data validation passed")
        return True
    
    def aggregate_to_1minute(self, tick_data: List[OHLCVBar], symbol: str) -> List[OHLCVBar]:
        """Aggregate tick data into 1-minute OHLCV bars."""
        if not tick_data:
            return []
        
        # Sort by timestamp
        tick_data.sort(key=lambda x: x.timestamp)
        
        # Group by minute
        minute_bars = {}
        for tick in tick_data:
            minute_key = tick.timestamp.replace(second=0, microsecond=0)
            
            if minute_key not in minute_bars:
                minute_bars[minute_key] = []
            minute_bars[minute_key].append(tick)
        
        # Create 1-minute bars
        bars = []
        for minute_key, ticks in minute_bars.items():
            if not ticks:
                continue
                
            # Sort ticks within the minute
            ticks.sort(key=lambda x: x.timestamp)
            
            # Calculate OHLCV
            open_price = ticks[0].open
            close_price = ticks[-1].close
            high_price = max(tick.high for tick in ticks)
            low_price = min(tick.low for tick in ticks)
            total_volume = sum(tick.volume for tick in ticks)
            
            bar = OHLCVBar(
                timestamp=minute_key,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=total_volume
            )
            bars.append(bar)
        
        self.logger.info(f"Aggregated {len(tick_data)} ticks into {len(bars)} 1-minute bars for {symbol}")
        return bars
    
    def add_real_time_tick(self, symbol: str, tick: OHLCVBar) -> Optional[OHLCVBar]:
        """Add a real-time tick and return completed 1-minute bar if ready."""
        current_minute = tick.timestamp.replace(second=0, microsecond=0)
        
        # Initialize buffer for symbol if needed
        if symbol not in self._real_time_buffers:
            self._real_time_buffers[symbol] = []
            self._current_minute_bars[symbol] = None
        
        # Check if we're in a new minute
        if (self._current_minute_bars[symbol] is not None and 
            self._current_minute_bars[symbol].timestamp != current_minute):
            # Complete the previous minute's bar
            completed_bar = self._current_minute_bars[symbol]
            self._current_minute_bars[symbol] = None
            self._real_time_buffers[symbol] = []
            return completed_bar
        
        # Add tick to current minute buffer
        self._real_time_buffers[symbol].append(tick)
        
        # Aggregate current minute's data
        current_bars = self.aggregate_to_1minute(self._real_time_buffers[symbol], symbol)
        if current_bars:
            self._current_minute_bars[symbol] = current_bars[0]
        
        return None
    
    def get_current_minute_bar(self, symbol: str) -> Optional[OHLCVBar]:
        """Get the current incomplete 1-minute bar for a symbol."""
        return self._current_minute_bars.get(symbol)
    
    def convert_bars_to_dataframe(self, bars: List[OHLCVBar]) -> pd.DataFrame:
        """Convert list of OHLCVBar objects to pandas DataFrame."""
        if not bars:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        data = [bar.to_dict() for bar in bars]
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df


# Factory function for creating data loader
def create_data_loader(data_dir: Path = Path("data")) -> DataLoader:
    """Create a new data loader instance."""
    return DataLoader(data_dir)
