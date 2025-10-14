"""
Data loader for historical OHLCV data.

This module handles fetching, normalizing, and storing historical
market data from various sources, primarily Robinhood Crypto API.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from grodtd.connectors.robinhood import RobinhoodConnector, create_robinhood_connector


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
    
    async def load_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m",
        connector: Optional[RobinhoodConnector] = None
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


# Factory function for creating data loader
def create_data_loader(data_dir: Path = Path("data")) -> DataLoader:
    """Create a new data loader instance."""
    return DataLoader(data_dir)
