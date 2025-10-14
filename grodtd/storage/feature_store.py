"""
Feature Store Implementation

This module provides a feature store for precomputing and caching technical indicators
and regime features for fast access during trading operations.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import json

from grodtd.storage.interfaces import OHLCVBar
from grodtd.features.indicators import TechnicalIndicators


@dataclass
class FeatureStoreConfig:
    """Configuration for the feature store."""
    db_path: str
    cache_ttl_minutes: int = 60
    max_cache_size_mb: int = 100
    enable_real_time_updates: bool = True
    enable_regime_features: bool = True


@dataclass
class FeatureMetadata:
    """Metadata for a cached feature."""
    feature_type: str
    symbol: str
    timestamp: datetime
    parameters: Dict[str, Any]
    version: str
    computed_at: datetime


@dataclass
class CachedFeature:
    """A cached feature value."""
    id: int
    symbol: str
    timestamp: datetime
    indicator_type: str
    value: float
    parameters: str  # JSON string
    computed_at: datetime


@dataclass
class RegimeFeature:
    """A regime-specific feature."""
    id: int
    symbol: str
    timestamp: datetime
    feature_type: str
    value: float
    regime_class: str
    computed_at: datetime


class FeatureStore:
    """
    Feature store for caching precomputed technical indicators and regime features.
    
    This class provides:
    - Real-time feature computation and caching
    - Fast feature retrieval for trading operations
    - Feature consistency validation
    - Performance monitoring and metrics
    """
    
    def __init__(self, config: FeatureStoreConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.indicators = TechnicalIndicators()
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the feature store database schema."""
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                # Create feature_store table for technical indicators
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS feature_store (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        indicator_type TEXT NOT NULL,
                        value REAL NOT NULL,
                        parameters TEXT NOT NULL,
                        computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timestamp, indicator_type, parameters)
                    )
                """)
                
                # Create regime_features table for regime-specific features
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS regime_features (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        feature_type TEXT NOT NULL,
                        value REAL NOT NULL,
                        regime_class TEXT NOT NULL,
                        computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timestamp, feature_type, regime_class)
                    )
                """)
                
                # Create feature_metadata table for tracking computation parameters
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS feature_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        feature_type TEXT NOT NULL,
                        parameters TEXT NOT NULL,
                        version TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(feature_type, parameters, version)
                    )
                """)
                
                # Create indexes for fast retrieval
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_store_symbol_timestamp ON feature_store(symbol, timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_store_indicator_type ON feature_store(indicator_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_regime_features_symbol_timestamp ON regime_features(symbol, timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_regime_features_feature_type ON regime_features(feature_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_regime_features_regime_class ON regime_features(regime_class)")
                
                conn.commit()
                self.logger.info("Feature store database schema initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize feature store database: {e}")
            raise
    
    def cache_technical_indicator(
        self,
        symbol: str,
        timestamp: datetime,
        indicator_type: str,
        value: float,
        parameters: Dict[str, Any]
    ) -> bool:
        """
        Cache a technical indicator value.
        
        Args:
            symbol: Trading symbol
            timestamp: Data timestamp
            indicator_type: Type of indicator (vwap, ema, atr, rsi, etc.)
            value: Computed indicator value
            parameters: Parameters used for computation
            
        Returns:
            True if successfully cached, False otherwise
        """
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO feature_store 
                    (symbol, timestamp, indicator_type, value, parameters, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    indicator_type,
                    value,
                    json.dumps(parameters),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                self.logger.debug(f"Cached {indicator_type} for {symbol} at {timestamp}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to cache indicator {indicator_type} for {symbol}: {e}")
            return False
    
    def get_cached_indicator(
        self,
        symbol: str,
        timestamp: datetime,
        indicator_type: str,
        parameters: Dict[str, Any]
    ) -> Optional[float]:
        """
        Retrieve a cached technical indicator value.
        
        Args:
            symbol: Trading symbol
            timestamp: Data timestamp
            indicator_type: Type of indicator
            parameters: Parameters used for computation
            
        Returns:
            Cached value if found, None otherwise
        """
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT value FROM feature_store
                    WHERE symbol = ? AND timestamp = ? AND indicator_type = ? AND parameters = ?
                """, (symbol, timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp), 
                      indicator_type, json.dumps(parameters)))
                
                result = cursor.fetchone()
                if result:
                    self.logger.debug(f"Retrieved cached {indicator_type} for {symbol} at {timestamp}")
                    return result[0]
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve cached indicator {indicator_type} for {symbol}: {e}")
            return None
    
    def cache_regime_feature(
        self,
        symbol: str,
        timestamp: datetime,
        feature_type: str,
        value: float,
        regime_class: str
    ) -> bool:
        """
        Cache a regime-specific feature value.
        
        Args:
            symbol: Trading symbol
            timestamp: Data timestamp
            feature_type: Type of regime feature
            value: Computed feature value
            regime_class: Regime classification
            
        Returns:
            True if successfully cached, False otherwise
        """
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO regime_features 
                    (symbol, timestamp, feature_type, value, regime_class, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    feature_type,
                    value,
                    regime_class,
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                self.logger.debug(f"Cached regime feature {feature_type} for {symbol} at {timestamp}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to cache regime feature {feature_type} for {symbol}: {e}")
            return False
    
    def get_cached_regime_feature(
        self,
        symbol: str,
        timestamp: datetime,
        feature_type: str,
        regime_class: str
    ) -> Optional[float]:
        """
        Retrieve a cached regime feature value.
        
        Args:
            symbol: Trading symbol
            timestamp: Data timestamp
            feature_type: Type of regime feature
            regime_class: Regime classification
            
        Returns:
            Cached value if found, None otherwise
        """
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT value FROM regime_features
                    WHERE symbol = ? AND timestamp = ? AND feature_type = ? AND regime_class = ?
                """, (symbol, timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp), 
                      feature_type, regime_class))
                
                result = cursor.fetchone()
                if result:
                    self.logger.debug(f"Retrieved cached regime feature {feature_type} for {symbol} at {timestamp}")
                    return result[0]
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve cached regime feature {feature_type} for {symbol}: {e}")
            return None
    
    def compute_and_cache_features(
        self,
        symbol: str,
        data: List[OHLCVBar],
        parameters: Dict[str, Any] = None
    ) -> Dict[str, List[float]]:
        """
        Compute and cache technical indicators for a dataset.
        
        Args:
            symbol: Trading symbol
            data: List of OHLCV bars
            parameters: Computation parameters
            
        Returns:
            Dictionary of computed features
        """
        if not data:
            return {}
        
        # Default parameters
        default_params = {
            'vwap_period': 20,
            'ema_fast': 9,
            'ema_slow': 20,
            'atr_period': 14,
            'rsi_period': 14
        }
        if parameters:
            default_params.update(parameters)
        
        try:
            # Convert to DataFrame for computation
            import pandas as pd
            df_data = pd.DataFrame([bar.to_dict() for bar in data])
            df_data['timestamp'] = pd.to_datetime(df_data['timestamp'])
            df_data.set_index('timestamp', inplace=True)
            
            # Compute all features
            features_df = self.indicators.calculate_all_features(
                df_data,
                vwap_period=default_params['vwap_period'],
                ema_fast=default_params['ema_fast'],
                ema_slow=default_params['ema_slow'],
                atr_period=default_params['atr_period'],
                rsi_period=default_params['rsi_period']
            )
            
            # Cache computed features
            cached_features = {}
            for timestamp, row in features_df.iterrows():
                # Convert pandas Timestamp to datetime if needed
                dt_timestamp = timestamp.to_pydatetime() if hasattr(timestamp, 'to_pydatetime') else timestamp
                
                if pd.notna(row.get('vwap')):
                    self.cache_technical_indicator(
                        symbol, dt_timestamp, 'vwap', row['vwap'], 
                        {'period': default_params['vwap_period']}
                    )
                    cached_features.setdefault('vwap', []).append(row['vwap'])
                
                if pd.notna(row.get('ema_fast')):
                    self.cache_technical_indicator(
                        symbol, dt_timestamp, 'ema_fast', row['ema_fast'],
                        {'period': default_params['ema_fast']}
                    )
                    cached_features.setdefault('ema_fast', []).append(row['ema_fast'])
                
                if pd.notna(row.get('ema_slow')):
                    self.cache_technical_indicator(
                        symbol, dt_timestamp, 'ema_slow', row['ema_slow'],
                        {'period': default_params['ema_slow']}
                    )
                    cached_features.setdefault('ema_slow', []).append(row['ema_slow'])
                
                if pd.notna(row.get('atr')):
                    self.cache_technical_indicator(
                        symbol, dt_timestamp, 'atr', row['atr'],
                        {'period': default_params['atr_period']}
                    )
                    cached_features.setdefault('atr', []).append(row['atr'])
                
                if pd.notna(row.get('rsi')):
                    self.cache_technical_indicator(
                        symbol, dt_timestamp, 'rsi', row['rsi'],
                        {'period': default_params['rsi_period']}
                    )
                    cached_features.setdefault('rsi', []).append(row['rsi'])
            
            self.logger.info(f"Computed and cached features for {symbol}: {len(cached_features)} indicator types")
            return cached_features
            
        except Exception as e:
            self.logger.error(f"Failed to compute and cache features for {symbol}: {e}")
            return {}
    
    def get_feature_history(
        self,
        symbol: str,
        indicator_type: str,
        start_time: datetime,
        end_time: datetime,
        parameters: Dict[str, Any] = None
    ) -> List[Tuple[datetime, float]]:
        """
        Get historical feature values for a symbol and indicator type.
        
        Args:
            symbol: Trading symbol
            indicator_type: Type of indicator
            start_time: Start of time range
            end_time: End of time range
            parameters: Parameters used for computation
            
        Returns:
            List of (timestamp, value) tuples
        """
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                if parameters:
                    cursor.execute("""
                        SELECT timestamp, value FROM feature_store
                        WHERE symbol = ? AND indicator_type = ? AND parameters = ?
                        AND timestamp BETWEEN ? AND ?
                        ORDER BY timestamp
                    """, (symbol, indicator_type, json.dumps(parameters), 
                          start_time.isoformat(), end_time.isoformat()))
                else:
                    cursor.execute("""
                        SELECT timestamp, value FROM feature_store
                        WHERE symbol = ? AND indicator_type = ?
                        AND timestamp BETWEEN ? AND ?
                        ORDER BY timestamp
                    """, (symbol, indicator_type, start_time.isoformat(), end_time.isoformat()))
                
                results = cursor.fetchall()
                return [(datetime.fromisoformat(row[0]), row[1]) for row in results]
                
        except Exception as e:
            self.logger.error(f"Failed to get feature history for {symbol} {indicator_type}: {e}")
            return []
    
    def cleanup_old_features(self, days_to_keep: int = 30) -> int:
        """
        Clean up old cached features to manage storage.
        
        Args:
            days_to_keep: Number of days of features to keep
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete old feature_store records
                cursor.execute("DELETE FROM feature_store WHERE computed_at < ?", (cutoff_date.isoformat(),))
                feature_store_deleted = cursor.rowcount
                
                # Delete old regime_features records
                cursor.execute("DELETE FROM regime_features WHERE computed_at < ?", (cutoff_date.isoformat(),))
                regime_features_deleted = cursor.rowcount
                
                conn.commit()
                
                total_deleted = feature_store_deleted + regime_features_deleted
                self.logger.info(f"Cleaned up {total_deleted} old feature records (cutoff: {cutoff_date})")
                return total_deleted
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old features: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get feature store cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                # Get feature_store stats
                cursor.execute("SELECT COUNT(*) FROM feature_store")
                feature_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT symbol) FROM feature_store")
                symbol_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT indicator_type) FROM feature_store")
                indicator_types = cursor.fetchone()[0]
                
                # Get regime_features stats
                cursor.execute("SELECT COUNT(*) FROM regime_features")
                regime_feature_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT feature_type) FROM regime_features")
                regime_feature_types = cursor.fetchone()[0]
                
                # Get oldest and newest cached features
                cursor.execute("SELECT MIN(computed_at), MAX(computed_at) FROM feature_store")
                oldest, newest = cursor.fetchone()
                
                return {
                    'feature_count': feature_count,
                    'symbol_count': symbol_count,
                    'indicator_types': indicator_types,
                    'regime_feature_count': regime_feature_count,
                    'regime_feature_types': regime_feature_types,
                    'oldest_cached': oldest,
                    'newest_cached': newest,
                    'cache_size_mb': self._estimate_cache_size()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    def _estimate_cache_size(self) -> float:
        """Estimate cache size in MB."""
        try:
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
                size_bytes = cursor.fetchone()[0]
                return size_bytes / (1024 * 1024)  # Convert to MB
        except:
            return 0.0


# Factory function for creating feature store
def create_feature_store(config: FeatureStoreConfig) -> FeatureStore:
    """Create a new feature store instance."""
    return FeatureStore(config)
