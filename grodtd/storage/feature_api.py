"""
Feature Store API

This module provides a high-level API for feature store operations including
real-time feature computation, caching, and retrieval optimized for trading operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from grodtd.storage.interfaces import OHLCVBar
from grodtd.storage.feature_store import FeatureStore, FeatureStoreConfig, CachedFeature, RegimeFeature
from grodtd.features.regime_features import RegimeFeatureCalculator, RegimeFeatureConfig, RegimeFeatureResult
from grodtd.features.indicators import TechnicalIndicators


@dataclass
class FeatureAPIConfig:
    """Configuration for the feature store API."""
    db_path: str
    cache_ttl_minutes: int = 60
    max_cache_size_mb: int = 100
    enable_real_time_updates: bool = True
    enable_regime_features: bool = True
    default_parameters: Dict[str, Any] = None


@dataclass
class FeatureRequest:
    """Request for feature computation or retrieval."""
    symbol: str
    timestamp: datetime
    indicator_types: List[str]
    parameters: Dict[str, Any] = None
    force_recompute: bool = False


@dataclass
class FeatureResponse:
    """Response from feature computation or retrieval."""
    symbol: str
    timestamp: datetime
    features: Dict[str, float]
    cached: bool
    computation_time_ms: float


class FeatureStoreAPI:
    """
    High-level API for feature store operations.
    
    This class provides:
    - Real-time feature computation and caching
    - Optimized feature retrieval for trading
    - Feature consistency validation
    - Performance monitoring and metrics
    """
    
    def __init__(self, config: FeatureAPIConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        feature_config = FeatureStoreConfig(
            db_path=config.db_path,
            cache_ttl_minutes=config.cache_ttl_minutes,
            max_cache_size_mb=config.max_cache_size_mb,
            enable_real_time_updates=config.enable_real_time_updates,
            enable_regime_features=config.enable_regime_features
        )
        
        self.feature_store = FeatureStore(feature_config)
        self.indicators = TechnicalIndicators()
        
        if config.enable_regime_features:
            regime_config = RegimeFeatureConfig()
            self.regime_calculator = RegimeFeatureCalculator(regime_config)
        else:
            self.regime_calculator = None
        
        # Default parameters
        self.default_parameters = config.default_parameters or {
            'vwap_period': 20,
            'ema_fast': 9,
            'ema_slow': 20,
            'atr_period': 14,
            'rsi_period': 14
        }
    
    def get_features(
        self,
        request: FeatureRequest
    ) -> FeatureResponse:
        """
        Get features for a symbol and timestamp.
        
        Args:
            request: Feature request
            
        Returns:
            Feature response with computed or cached features
        """
        start_time = datetime.now()
        
        try:
            features = {}
            cached_count = 0
            
            # Check cache first (unless force recompute)
            if not request.force_recompute:
                for indicator_type in request.indicator_types:
                    params = request.parameters or self.default_parameters
                    cached_value = self.feature_store.get_cached_indicator(
                        request.symbol,
                        request.timestamp,
                        indicator_type,
                        params
                    )
                    
                    if cached_value is not None:
                        features[indicator_type] = cached_value
                        cached_count += 1
            
            # Compute missing features
            missing_indicators = [ind for ind in request.indicator_types if ind not in features]
            if missing_indicators:
                computed_features = self._compute_missing_features(
                    request.symbol,
                    request.timestamp,
                    missing_indicators,
                    request.parameters
                )
                features.update(computed_features)
            
            # Calculate response metrics
            computation_time = (datetime.now() - start_time).total_seconds() * 1000
            cached = cached_count > 0
            
            return FeatureResponse(
                symbol=request.symbol,
                timestamp=request.timestamp,
                features=features,
                cached=cached,
                computation_time_ms=computation_time
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get features for {request.symbol}: {e}")
            return FeatureResponse(
                symbol=request.symbol,
                timestamp=request.timestamp,
                features={},
                cached=False,
                computation_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
    
    def _compute_missing_features(
        self,
        symbol: str,
        timestamp: datetime,
        indicator_types: List[str],
        parameters: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Compute missing features for a symbol and timestamp.
        
        Args:
            symbol: Trading symbol
            timestamp: Data timestamp
            indicator_types: List of indicator types to compute
            parameters: Computation parameters
            
        Returns:
            Dictionary of computed features
        """
        try:
            # Get recent data for computation
            data = self._get_recent_data(symbol, timestamp)
            if not data:
                self.logger.warning(f"No data available for {symbol} at {timestamp}")
                return {}
            
            # Convert to DataFrame
            import pandas as pd
            df_data = pd.DataFrame([bar.to_dict() for bar in data])
            df_data['timestamp'] = pd.to_datetime(df_data['timestamp'])
            df_data.set_index('timestamp', inplace=True)
            
            # Use provided parameters or defaults
            params = parameters or self.default_parameters
            
            # Compute features
            features = {}
            for indicator_type in indicator_types:
                try:
                    if indicator_type == 'vwap':
                        vwap = self.indicators.calculate_vwap(df_data, params.get('vwap_period', 20))
                        if not vwap.empty and pd.notna(vwap.iloc[-1]):
                            features['vwap'] = vwap.iloc[-1]
                            self._cache_feature(symbol, timestamp, 'vwap', features['vwap'], params)
                    
                    elif indicator_type == 'ema_fast':
                        ema = self.indicators.calculate_ema(df_data['close'], params.get('ema_fast', 9))
                        if not ema.empty and pd.notna(ema.iloc[-1]):
                            features['ema_fast'] = ema.iloc[-1]
                            self._cache_feature(symbol, timestamp, 'ema_fast', features['ema_fast'], params)
                    
                    elif indicator_type == 'ema_slow':
                        ema = self.indicators.calculate_ema(df_data['close'], params.get('ema_slow', 20))
                        if not ema.empty and pd.notna(ema.iloc[-1]):
                            features['ema_slow'] = ema.iloc[-1]
                            self._cache_feature(symbol, timestamp, 'ema_slow', features['ema_slow'], params)
                    
                    elif indicator_type == 'atr':
                        atr = self.indicators.calculate_atr(df_data, params.get('atr_period', 14))
                        if not atr.empty and pd.notna(atr.iloc[-1]):
                            features['atr'] = atr.iloc[-1]
                            self._cache_feature(symbol, timestamp, 'atr', features['atr'], params)
                    
                    elif indicator_type == 'rsi':
                        rsi = self.indicators.calculate_rsi(df_data['close'], params.get('rsi_period', 14))
                        if not rsi.empty and pd.notna(rsi.iloc[-1]):
                            features['rsi'] = rsi.iloc[-1]
                            self._cache_feature(symbol, timestamp, 'rsi', features['rsi'], params)
                    
                    elif indicator_type == 'bb_upper':
                        bb_upper, _, _ = self.indicators.calculate_bollinger_bands(df_data['close'])
                        if not bb_upper.empty and pd.notna(bb_upper.iloc[-1]):
                            features['bb_upper'] = bb_upper.iloc[-1]
                            self._cache_feature(symbol, timestamp, 'bb_upper', features['bb_upper'], params)
                    
                    elif indicator_type == 'bb_lower':
                        _, _, bb_lower = self.indicators.calculate_bollinger_bands(df_data['close'])
                        if not bb_lower.empty and pd.notna(bb_lower.iloc[-1]):
                            features['bb_lower'] = bb_lower.iloc[-1]
                            self._cache_feature(symbol, timestamp, 'bb_lower', features['bb_lower'], params)
                    
                    elif indicator_type == 'macd':
                        macd_line, _, _ = self.indicators.calculate_macd(df_data['close'])
                        if not macd_line.empty and pd.notna(macd_line.iloc[-1]):
                            features['macd'] = macd_line.iloc[-1]
                            self._cache_feature(symbol, timestamp, 'macd', features['macd'], params)
                    
                except Exception as e:
                    self.logger.error(f"Failed to compute {indicator_type} for {symbol}: {e}")
                    continue
            
            self.logger.debug(f"Computed {len(features)} features for {symbol} at {timestamp}")
            return features
            
        except Exception as e:
            self.logger.error(f"Failed to compute missing features for {symbol}: {e}")
            return {}
    
    def _get_recent_data(
        self,
        symbol: str,
        timestamp: datetime,
        lookback_hours: int = 24
    ) -> List[OHLCVBar]:
        """
        Get recent data for feature computation.
        
        Args:
            symbol: Trading symbol
            timestamp: Current timestamp
            lookback_hours: Hours of data to look back
            
        Returns:
            List of recent OHLCV bars
        """
        try:
            import sqlite3
            from grodtd.storage.interfaces import OHLCVBar
            
            start_time = timestamp - timedelta(hours=lookback_hours)
            
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                # Query market_data table for recent OHLCV data
                cursor.execute("""
                    SELECT timestamp, open, high, low, close, volume
                    FROM market_data 
                    WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                """, (symbol, start_time.isoformat(), timestamp.isoformat()))
                
                results = cursor.fetchall()
                
                if not results:
                    self.logger.warning(f"No market data found for {symbol} between {start_time} and {timestamp}")
                    return []
                
                # Convert to OHLCVBar objects
                bars = []
                for row in results:
                    bar = OHLCVBar(
                        timestamp=datetime.fromisoformat(row[0]),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5])
                    )
                    bars.append(bar)
                
                self.logger.debug(f"Retrieved {len(bars)} bars for {symbol}")
                return bars
                
        except Exception as e:
            self.logger.error(f"Failed to get recent data for {symbol}: {e}")
            return []
    
    def _cache_feature(
        self,
        symbol: str,
        timestamp: datetime,
        indicator_type: str,
        value: float,
        parameters: Dict[str, Any]
    ):
        """Cache a computed feature."""
        try:
            self.feature_store.cache_technical_indicator(
                symbol, timestamp, indicator_type, value, parameters
            )
        except Exception as e:
            self.logger.error(f"Failed to cache {indicator_type} for {symbol}: {e}")
    
    def get_regime_features(
        self,
        symbol: str,
        timestamp: datetime,
        force_recompute: bool = False
    ) -> List[RegimeFeatureResult]:
        """
        Get regime features for a symbol and timestamp.
        
        Args:
            symbol: Trading symbol
            timestamp: Data timestamp
            force_recompute: Force recomputation even if cached
            
        Returns:
            List of regime feature results
        """
        if not self.regime_calculator:
            self.logger.warning("Regime features not enabled")
            return []
        
        try:
            # Check cache first
            if not force_recompute:
                cached_features = self._get_cached_regime_features(symbol, timestamp)
                if cached_features:
                    return cached_features
            
            # Compute regime features
            data = self._get_recent_data(symbol, timestamp)
            if not data:
                return []
            
            regime_features = self.regime_calculator.compute_regime_features_for_data(data, symbol)
            
            # Cache computed features
            for feature in regime_features:
                self.feature_store.cache_regime_feature(
                    feature.symbol,
                    feature.timestamp,
                    feature.feature_type,
                    feature.value,
                    feature.regime_class
                )
            
            return regime_features
            
        except Exception as e:
            self.logger.error(f"Failed to get regime features for {symbol}: {e}")
            return []
    
    def _get_cached_regime_features(
        self,
        symbol: str,
        timestamp: datetime
    ) -> List[RegimeFeatureResult]:
        """Get cached regime features."""
        try:
            import sqlite3
            
            with sqlite3.connect(self.config.db_path) as conn:
                cursor = conn.cursor()
                
                # Query regime_features table for cached features
                cursor.execute("""
                    SELECT feature_type, value, regime_class, computed_at
                    FROM regime_features 
                    WHERE symbol = ? AND timestamp = ?
                    ORDER BY feature_type
                """, (symbol, timestamp.isoformat()))
                
                results = cursor.fetchall()
                
                if not results:
                    self.logger.debug(f"No cached regime features found for {symbol} at {timestamp}")
                    return []
                
                # Convert to RegimeFeatureResult objects
                cached_features = []
                for row in results:
                    feature = RegimeFeatureResult(
                        symbol=symbol,
                        timestamp=timestamp,
                        feature_type=row[0],
                        value=float(row[1]),
                        regime_class=row[2],
                        confidence=1.0  # Cached features have full confidence
                    )
                    cached_features.append(feature)
                
                self.logger.debug(f"Retrieved {len(cached_features)} cached regime features for {symbol}")
                return cached_features
                
        except Exception as e:
            self.logger.error(f"Failed to get cached regime features for {symbol}: {e}")
            return []
    
    def batch_compute_features(
        self,
        symbol: str,
        data: List[OHLCVBar],
        indicator_types: List[str] = None,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, List[float]]:
        """
        Batch compute features for a dataset.
        
        Args:
            symbol: Trading symbol
            data: List of OHLCV bars
            indicator_types: List of indicator types to compute
            parameters: Computation parameters
            
        Returns:
            Dictionary of computed features
        """
        if not data:
            return {}
        
        try:
            # Use default indicator types if not specified
            if not indicator_types:
                indicator_types = ['vwap', 'ema_fast', 'ema_slow', 'atr', 'rsi']
            
            # Use provided parameters or defaults
            params = parameters or self.default_parameters
            
            # Compute and cache features
            cached_features = self.feature_store.compute_and_cache_features(
                symbol, data, params
            )
            
            self.logger.info(f"Batch computed features for {symbol}: {len(cached_features)} indicator types")
            return cached_features
            
        except Exception as e:
            self.logger.error(f"Failed to batch compute features for {symbol}: {e}")
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
        Get historical feature values.
        
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
            return self.feature_store.get_feature_history(
                symbol, indicator_type, start_time, end_time, parameters
            )
        except Exception as e:
            self.logger.error(f"Failed to get feature history for {symbol} {indicator_type}: {e}")
            return []
    
    def cleanup_old_features(self, days_to_keep: int = 30) -> int:
        """
        Clean up old cached features.
        
        Args:
            days_to_keep: Number of days of features to keep
            
        Returns:
            Number of records deleted
        """
        try:
            return self.feature_store.cleanup_old_features(days_to_keep)
        except Exception as e:
            self.logger.error(f"Failed to cleanup old features: {e}")
            return 0
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get feature store performance statistics.
        
        Returns:
            Dictionary with performance statistics
        """
        try:
            return self.feature_store.get_cache_stats()
        except Exception as e:
            self.logger.error(f"Failed to get performance stats: {e}")
            return {}
    
    def validate_feature_consistency(
        self,
        symbol: str,
        timestamp: datetime,
        indicator_type: str,
        parameters: Dict[str, Any] = None
    ) -> bool:
        """
        Validate feature consistency between live and cached calculations.
        
        Args:
            symbol: Trading symbol
            timestamp: Data timestamp
            indicator_type: Type of indicator
            parameters: Computation parameters
            
        Returns:
            True if consistent, False otherwise
        """
        try:
            # Get cached value
            cached_value = self.feature_store.get_cached_indicator(
                symbol, timestamp, indicator_type, parameters or self.default_parameters
            )
            
            if cached_value is None:
                return True  # No cached value to compare
            
            # Get live data and compute
            data = self._get_recent_data(symbol, timestamp)
            if not data:
                return True  # No data to compare
            
            # Compute live value
            import pandas as pd
            df_data = pd.DataFrame([bar.to_dict() for bar in data])
            df_data['timestamp'] = pd.to_datetime(df_data['timestamp'])
            df_data.set_index('timestamp', inplace=True)
            
            params = parameters or self.default_parameters
            live_value = None
            
            if indicator_type == 'vwap':
                vwap = self.indicators.calculate_vwap(df_data, params.get('vwap_period', 20))
                if not vwap.empty and pd.notna(vwap.iloc[-1]):
                    live_value = vwap.iloc[-1]
            elif indicator_type == 'ema_fast':
                ema = self.indicators.calculate_ema(df_data['close'], params.get('ema_fast', 9))
                if not ema.empty and pd.notna(ema.iloc[-1]):
                    live_value = ema.iloc[-1]
            # Add other indicator types as needed
            
            if live_value is None:
                return True  # Cannot compute live value
            
            # Check consistency (allow small floating point differences)
            tolerance = 1e-6
            is_consistent = abs(cached_value - live_value) < tolerance
            
            if not is_consistent:
                self.logger.warning(
                    f"Feature inconsistency detected for {symbol} {indicator_type}: "
                    f"cached={cached_value}, live={live_value}"
                )
            
            return is_consistent
            
        except Exception as e:
            self.logger.error(f"Failed to validate feature consistency for {symbol} {indicator_type}: {e}")
            return False


# Factory function for creating feature store API
def create_feature_store_api(config: FeatureAPIConfig) -> FeatureStoreAPI:
    """Create a new feature store API instance."""
    return FeatureStoreAPI(config)
