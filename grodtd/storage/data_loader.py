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
        connector: "RobinhoodConnector",
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> pd.DataFrame:
        """Fetch data from the API."""
        self.logger.info(f"Fetching data from API for {symbol}")
        
        try:
            # Get historical data from connector
            bars = await connector.get_historical_data(symbol, start_date, end_date, interval)
            
            if not bars:
                self.logger.warning(f"No data returned for {symbol}")
                # Return empty DataFrame with proper structure
                columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                data = pd.DataFrame(columns=columns)
                data['timestamp'] = pd.to_datetime(data['timestamp'])
                return data
            
            # Convert bars to DataFrame
            data = self.convert_bars_to_dataframe(bars)
            
            # Validate the data
            if not self.validate_ohlcv_data(data):
                self.logger.error(f"Data validation failed for {symbol}")
                raise ValueError("Data validation failed")
            
            self.logger.info(f"Successfully fetched {len(data)} records for {symbol}")
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching data from API: {e}")
            # Return empty DataFrame on error
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            data = pd.DataFrame(columns=columns)
            data['timestamp'] = pd.to_datetime(data['timestamp'])
            return data
    
    def _store_data(self, data: pd.DataFrame, file_path: Path):
        """Store data to Parquet file with optimization."""
        self.logger.info(f"Storing data to {file_path}")
        
        # Ensure timestamp is datetime
        if 'timestamp' in data.columns:
            data['timestamp'] = pd.to_datetime(data['timestamp'])
        
        # Add partitioning columns for daily partitioning
        if 'timestamp' in data.columns:
            data['date'] = data['timestamp'].dt.date
            data['year'] = data['timestamp'].dt.year
            data['month'] = data['timestamp'].dt.month
            data['day'] = data['timestamp'].dt.day
        
        # Store with compression and optimization
        data.to_parquet(
            file_path, 
            index=False,
            compression='snappy',  # Fast compression
            engine='pyarrow',
            partition_cols=['date'] if 'date' in data.columns else None
        )
    
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
    
    def get_data_for_backtesting(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """Get optimized data for backtesting with fast access."""
        self.logger.info(f"Loading backtesting data for {symbol} from {start_date} to {end_date}")
        
        # Try to load from cache first
        cached_data = self.load_cached_data(symbol, start_date, end_date, interval)
        if cached_data is not None:
            # Filter to exact date range
            cached_data = cached_data[
                (cached_data['timestamp'] >= start_date) & 
                (cached_data['timestamp'] <= end_date)
            ]
            return cached_data
        
        # If no cache, load from API
        if hasattr(self, 'connector') and self.connector:
            # Load from API and store
            data = self.load_historical_data(symbol, start_date, end_date, interval, self.connector)
            return data
        
        return pd.DataFrame()
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics and optimization info."""
        total_files = len(list(self.raw_dir.glob("*.parquet")))
        total_size = sum(f.stat().st_size for f in self.raw_dir.glob("*.parquet"))
        
        return {
            "total_files": total_files,
            "total_size_mb": total_size / (1024 * 1024),
            "data_directory": str(self.raw_dir),
            "compression": "snappy",
            "partitioning": "daily by date"
        }
    
    def validate_ohlcv_data(self, data: pd.DataFrame) -> bool:
        """Validate OHLCV data completeness and integrity with comprehensive checks."""
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        # Check required columns exist
        if not all(col in data.columns for col in required_columns):
            self.logger.error(f"Missing required columns. Expected: {required_columns}")
            return False
        
        if data.empty:
            self.logger.warning("Empty dataset provided for validation")
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
        
        # Check for outliers using statistical methods
        for col in ['open', 'high', 'low', 'close']:
            if self._detect_outliers(data[col]):
                self.logger.warning(f"Potential outliers detected in {col} column")
        
        # Check for data gaps
        if 'timestamp' in data.columns:
            self._check_data_gaps(data)
        
        self.logger.info("OHLCV data validation passed")
        return True
    
    def _detect_outliers(self, series: pd.Series, threshold: float = 3.0) -> bool:
        """Detect outliers using Z-score method."""
        if len(series) < 3:
            return False
        
        z_scores = abs((series - series.mean()) / series.std())
        return (z_scores > threshold).any()
    
    def _check_data_gaps(self, data: pd.DataFrame):
        """Check for data gaps in time series."""
        if 'timestamp' not in data.columns or len(data) < 2:
            return
        
        # Sort by timestamp
        data_sorted = data.sort_values('timestamp')
        time_diffs = data_sorted['timestamp'].diff()
        
        # Check for gaps larger than expected interval
        expected_interval = pd.Timedelta(minutes=1)  # 1-minute data
        large_gaps = time_diffs > expected_interval * 2
        
        if large_gaps.any():
            gap_count = large_gaps.sum()
            self.logger.warning(f"Found {gap_count} potential data gaps in time series")
    
    def detect_missing_data(self, data: pd.DataFrame, expected_interval: str = "1m") -> List[datetime]:
        """Detect missing data points in time series."""
        if 'timestamp' not in data.columns or data.empty:
            return []
        
        # Create expected time range
        start_time = data['timestamp'].min()
        end_time = data['timestamp'].max()
        expected_range = pd.date_range(start=start_time, end=end_time, freq=expected_interval)
        
        # Find missing timestamps
        actual_timestamps = set(data['timestamp'])
        expected_timestamps = set(expected_range)
        missing_timestamps = expected_timestamps - actual_timestamps
        
        return sorted(list(missing_timestamps))
    
    def get_data_quality_report(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive data quality report."""
        report = {
            "total_records": len(data),
            "date_range": {
                "start": data['timestamp'].min() if 'timestamp' in data.columns else None,
                "end": data['timestamp'].max() if 'timestamp' in data.columns else None
            },
            "missing_values": data.isnull().sum().to_dict(),
            "data_gaps": len(self.detect_missing_data(data)),
            "outliers_detected": {},
            "validation_passed": self.validate_ohlcv_data(data)
        }
        
        # Check for outliers in each price column
        for col in ['open', 'high', 'low', 'close']:
            if col in data.columns:
                report["outliers_detected"][col] = self._detect_outliers(data[col])
        
        return report
    
    async def incremental_update(
        self,
        symbol: str,
        connector: Optional["RobinhoodConnector"] = None,
        force_update: bool = False
    ) -> Dict[str, Any]:
        """Perform incremental data update to avoid gaps."""
        self.logger.info(f"Starting incremental update for {symbol}")
        
        # Get latest data timestamp
        latest_timestamp = self._get_latest_timestamp(symbol)
        
        if latest_timestamp is None:
            # No existing data, fetch last 7 days
            start_date = datetime.now() - timedelta(days=7)
            self.logger.info(f"No existing data found, fetching from {start_date}")
        else:
            # Start from latest timestamp
            start_date = latest_timestamp
            self.logger.info(f"Updating from latest timestamp: {start_date}")
        
        end_date = datetime.now()
        
        # Fetch new data
        if connector:
            new_data = await self.load_historical_data(symbol, start_date, end_date, "1m", connector)
            
            if not new_data.empty:
                # Check for conflicts and merge
                merged_data = self._merge_data_without_conflicts(symbol, new_data)
                
                # Store updated data
                file_path = self.raw_dir / f"{symbol}_1m_{start_date.date()}_{end_date.date()}.parquet"
                self._store_data(merged_data, file_path)
                
                return {
                    "success": True,
                    "new_records": len(new_data),
                    "total_records": len(merged_data),
                    "date_range": f"{start_date} to {end_date}"
                }
        
        return {"success": False, "error": "No connector available"}
    
    def _get_latest_timestamp(self, symbol: str) -> Optional[datetime]:
        """Get the latest timestamp for a symbol."""
        pattern = f"{symbol}_*.parquet"
        files = list(self.raw_dir.glob(pattern))
        
        if not files:
            return None
        
        latest_timestamp = None
        for file_path in files:
            try:
                data = pd.read_parquet(file_path)
                if 'timestamp' in data.columns and not data.empty:
                    file_latest = data['timestamp'].max()
                    if latest_timestamp is None or file_latest > latest_timestamp:
                        latest_timestamp = file_latest
            except Exception as e:
                self.logger.warning(f"Error reading {file_path}: {e}")
        
        return latest_timestamp
    
    def _merge_data_without_conflicts(self, symbol: str, new_data: pd.DataFrame) -> pd.DataFrame:
        """Merge new data with existing data, resolving conflicts."""
        # Load existing data
        existing_files = list(self.raw_dir.glob(f"{symbol}_*.parquet"))
        
        if not existing_files:
            return new_data
        
        # Combine all existing data
        existing_data = []
        for file_path in existing_files:
            try:
                data = pd.read_parquet(file_path)
                existing_data.append(data)
            except Exception as e:
                self.logger.warning(f"Error reading {file_path}: {e}")
        
        if not existing_data:
            return new_data
        
        # Combine existing data
        all_existing = pd.concat(existing_data, ignore_index=True)
        
        # Remove duplicates based on timestamp
        combined = pd.concat([all_existing, new_data], ignore_index=True)
        combined = combined.drop_duplicates(subset=['timestamp'], keep='last')
        combined = combined.sort_values('timestamp')
        
        return combined
    
    def query_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m",
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Flexible data query interface for backtesting and analysis."""
        self.logger.info(f"Querying data for {symbol} from {start_date} to {end_date}")
        
        # Load cached data
        cached_data = self.load_cached_data(symbol, start_date, end_date, interval)
        
        if cached_data is not None and not cached_data.empty:
            # Filter to exact date range
            filtered_data = cached_data[
                (cached_data['timestamp'] >= start_date) & 
                (cached_data['timestamp'] <= end_date)
            ]
            
            # Select specific columns if requested
            if columns:
                available_columns = [col for col in columns if col in filtered_data.columns]
                filtered_data = filtered_data[available_columns]
            
            return filtered_data
        
        return pd.DataFrame()
    
    def get_data_summary(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for stored data."""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()
        
        data = self.query_data(symbol, start_date, end_date)
        
        if data.empty:
            return {
                "symbol": symbol,
                "status": "no_data",
                "record_count": 0,
                "date_range": None,
                "data_quality": None
            }
        
        # Calculate summary statistics
        summary = {
            "symbol": symbol,
            "status": "available",
            "record_count": len(data),
            "date_range": {
                "start": data['timestamp'].min(),
                "end": data['timestamp'].max()
            },
            "data_quality": self.get_data_quality_report(data),
            "price_stats": {
                "open": {"min": data['open'].min(), "max": data['open'].max(), "mean": data['open'].mean()},
                "high": {"min": data['high'].min(), "max": data['high'].max(), "mean": data['high'].mean()},
                "low": {"min": data['low'].min(), "max": data['low'].max(), "mean": data['low'].mean()},
                "close": {"min": data['close'].min(), "max": data['close'].max(), "mean": data['close'].mean()},
                "volume": {"min": data['volume'].min(), "max": data['volume'].max(), "mean": data['volume'].mean()}
            }
        }
        
        return summary
    
    def export_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        format: str = "csv",
        output_path: Optional[Path] = None
    ) -> Path:
        """Export data in various formats for external use."""
        data = self.query_data(symbol, start_date, end_date)
        
        if data.empty:
            raise ValueError(f"No data available for {symbol} in the specified date range")
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.raw_dir / f"{symbol}_export_{timestamp}.{format}"
        
        if format.lower() == "csv":
            data.to_csv(output_path, index=False)
        elif format.lower() == "json":
            data.to_json(output_path, orient="records", date_format="iso")
        elif format.lower() == "parquet":
            data.to_parquet(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self.logger.info(f"Data exported to {output_path}")
        return output_path
    
    def schedule_incremental_updates(self, symbols: List[str], interval_minutes: int = 5):
        """Schedule automatic incremental updates."""
        import asyncio
        
        async def update_loop():
            while True:
                for symbol in symbols:
                    try:
                        await self.incremental_update(symbol)
                    except Exception as e:
                        self.logger.error(f"Error updating {symbol}: {e}")
                
                await asyncio.sleep(interval_minutes * 60)
        
        return update_loop
    
    def get_data_freshness(self, symbol: str) -> Dict[str, Any]:
        """Check data freshness and identify stale data."""
        latest_timestamp = self._get_latest_timestamp(symbol)
        
        if latest_timestamp is None:
            return {
                "status": "no_data",
                "latest_timestamp": None,
                "age_hours": None,
                "stale": True
            }
        
        age_hours = (datetime.now() - latest_timestamp).total_seconds() / 3600
        stale = age_hours > 2  # Consider stale if older than 2 hours
        
        return {
            "status": "stale" if stale else "fresh",
            "latest_timestamp": latest_timestamp,
            "age_hours": age_hours,
            "stale": stale
        }
    
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
