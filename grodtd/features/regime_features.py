"""
Regime Feature Computation

This module provides regime-specific feature calculations including volatility ratios,
momentum indicators, and other regime-dependent features for market regime classification.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from grodtd.storage.interfaces import OHLCVBar
from grodtd.features.indicators import TechnicalIndicators


@dataclass
class RegimeFeatureConfig:
    """Configuration for regime feature computation."""
    volatility_lookback: int = 20
    momentum_lookback: int = 14
    trend_lookback: int = 10
    volume_lookback: int = 10


@dataclass
class RegimeFeatureResult:
    """Result of regime feature computation."""
    symbol: str
    timestamp: datetime
    feature_type: str
    value: float
    regime_class: str
    confidence: float


class RegimeFeatureCalculator:
    """
    Calculator for regime-specific features.
    
    This class provides:
    - Volatility ratio calculations
    - Momentum indicator computations
    - Trend strength measurements
    - Volume-based regime features
    """
    
    def __init__(self, config: RegimeFeatureConfig = None):
        self.config = config or RegimeFeatureConfig()
        self.logger = logging.getLogger(__name__)
        self.indicators = TechnicalIndicators()
    
    def calculate_volatility_ratio(
        self,
        data: pd.DataFrame,
        short_period: int = 5,
        long_period: int = 20
    ) -> pd.Series:
        """
        Calculate volatility ratio (short-term vs long-term volatility).
        
        Args:
            data: DataFrame with OHLCV data
            short_period: Short-term volatility period
            long_period: Long-term volatility period
            
        Returns:
            Series with volatility ratios
        """
        try:
            # Calculate returns
            returns = data['close'].pct_change()
            
            # Calculate short-term volatility
            short_vol = returns.rolling(window=short_period).std()
            
            # Calculate long-term volatility
            long_vol = returns.rolling(window=long_period).std()
            
            # Calculate volatility ratio
            vol_ratio = short_vol / long_vol
            
            return vol_ratio.fillna(0)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate volatility ratio: {e}")
            return pd.Series(index=data.index, dtype=float).fillna(0)
    
    def calculate_momentum_indicators(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> Dict[str, pd.Series]:
        """
        Calculate momentum indicators for regime classification.
        
        Args:
            data: DataFrame with OHLCV data
            period: Lookback period for momentum calculation
            
        Returns:
            Dictionary with momentum indicators
        """
        try:
            results = {}
            
            # Price momentum
            price_momentum = data['close'].pct_change(periods=period)
            results['price_momentum'] = price_momentum.fillna(0)
            
            # Volume momentum
            volume_momentum = data['volume'].pct_change(periods=period)
            results['volume_momentum'] = volume_momentum.fillna(0)
            
            # High-Low momentum
            high_momentum = data['high'].pct_change(periods=period)
            low_momentum = data['low'].pct_change(periods=period)
            results['high_momentum'] = high_momentum.fillna(0)
            results['low_momentum'] = low_momentum.fillna(0)
            
            # Range momentum (high-low range)
            range_momentum = ((data['high'] - data['low']) / data['close']).pct_change(periods=period)
            results['range_momentum'] = range_momentum.fillna(0)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to calculate momentum indicators: {e}")
            return {}
    
    def calculate_trend_strength(
        self,
        data: pd.DataFrame,
        period: int = 10
    ) -> pd.Series:
        """
        Calculate trend strength indicator.
        
        Args:
            data: DataFrame with OHLCV data
            period: Lookback period for trend calculation
            
        Returns:
            Series with trend strength values
        """
        try:
            # Calculate price change over period
            price_change = data['close'].pct_change(periods=period)
            
            # Calculate volume-weighted price change
            volume_weighted_change = (data['close'].pct_change() * data['volume']).rolling(window=period).sum()
            volume_sum = data['volume'].rolling(window=period).sum()
            volume_weighted_change = volume_weighted_change / volume_sum
            
            # Trend strength is the correlation between price change and volume
            trend_strength = price_change.rolling(window=period).corr(volume_weighted_change)
            
            return trend_strength.fillna(0)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate trend strength: {e}")
            return pd.Series(index=data.index, dtype=float).fillna(0)
    
    def calculate_volume_regime_features(
        self,
        data: pd.DataFrame,
        period: int = 10
    ) -> Dict[str, pd.Series]:
        """
        Calculate volume-based regime features.
        
        Args:
            data: DataFrame with OHLCV data
            period: Lookback period for volume calculation
            
        Returns:
            Dictionary with volume regime features
        """
        try:
            results = {}
            
            # Volume trend
            volume_trend = data['volume'].rolling(window=period).mean()
            results['volume_trend'] = volume_trend.fillna(0)
            
            # Volume volatility
            volume_volatility = data['volume'].rolling(window=period).std()
            results['volume_volatility'] = volume_volatility.fillna(0)
            
            # Volume-price correlation
            volume_price_corr = data['close'].rolling(window=period).corr(data['volume'])
            results['volume_price_correlation'] = volume_price_corr.fillna(0)
            
            # Volume acceleration (second derivative)
            volume_acceleration = data['volume'].diff().diff()
            results['volume_acceleration'] = volume_acceleration.fillna(0)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to calculate volume regime features: {e}")
            return {}
    
    def calculate_regime_classification_features(
        self,
        data: pd.DataFrame,
        symbol: str
    ) -> Dict[str, pd.Series]:
        """
        Calculate comprehensive regime classification features.
        
        Args:
            data: DataFrame with OHLCV data
            symbol: Trading symbol
            
        Returns:
            Dictionary with regime classification features
        """
        try:
            results = {}
            
            # Volatility features
            vol_ratio = self.calculate_volatility_ratio(data)
            results['volatility_ratio'] = vol_ratio
            
            # Momentum features
            momentum_features = self.calculate_momentum_indicators(data)
            results.update(momentum_features)
            
            # Trend strength
            trend_strength = self.calculate_trend_strength(data)
            results['trend_strength'] = trend_strength
            
            # Volume regime features
            volume_features = self.calculate_volume_regime_features(data)
            results.update(volume_features)
            
            # Technical indicators for regime classification
            if len(data) >= 20:
                # RSI for momentum regime
                rsi = self.indicators.calculate_rsi(data['close'])
                results['rsi'] = rsi.fillna(50)  # Neutral RSI
                
                # ATR for volatility regime
                atr = self.indicators.calculate_atr(data)
                results['atr'] = atr.fillna(0)
                
                # EMA trend regime
                ema_fast = self.indicators.calculate_ema(data['close'], 9)
                ema_slow = self.indicators.calculate_ema(data['close'], 20)
                results['ema_fast'] = ema_fast.fillna(data['close'])
                results['ema_slow'] = ema_slow.fillna(data['close'])
            
            self.logger.debug(f"Calculated {len(results)} regime features for {symbol}")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to calculate regime classification features for {symbol}: {e}")
            return {}
    
    def classify_regime(
        self,
        features: Dict[str, pd.Series],
        timestamp: datetime
    ) -> Tuple[str, float]:
        """
        Classify market regime based on computed features.
        
        Args:
            features: Dictionary of computed features
            timestamp: Timestamp for classification
            
        Returns:
            Tuple of (regime_class, confidence)
        """
        try:
            # Get latest feature values
            latest_features = {}
            for name, series in features.items():
                if not series.empty and pd.notna(series.iloc[-1]):
                    latest_features[name] = series.iloc[-1]
            
            if not latest_features:
                return "unknown", 0.0
            
            # Simple regime classification logic
            regime_score = 0.0
            confidence = 0.0
            
            # Volatility regime classification
            if 'volatility_ratio' in latest_features:
                vol_ratio = latest_features['volatility_ratio']
                if vol_ratio > 1.5:
                    regime_score += 1.0  # High volatility
                elif vol_ratio < 0.5:
                    regime_score -= 1.0  # Low volatility
                confidence += 0.3
            
            # Momentum regime classification
            if 'price_momentum' in latest_features:
                momentum = latest_features['price_momentum']
                if momentum > 0.05:
                    regime_score += 1.0  # Strong upward momentum
                elif momentum < -0.05:
                    regime_score -= 1.0  # Strong downward momentum
                confidence += 0.3
            
            # Trend regime classification
            if 'trend_strength' in latest_features:
                trend = latest_features['trend_strength']
                if trend > 0.5:
                    regime_score += 0.5  # Strong trend
                elif trend < -0.5:
                    regime_score -= 0.5  # Weak trend
                confidence += 0.2
            
            # RSI regime classification
            if 'rsi' in latest_features:
                rsi = latest_features['rsi']
                if rsi > 70:
                    regime_score += 0.5  # Overbought
                elif rsi < 30:
                    regime_score -= 0.5  # Oversold
                confidence += 0.2
            
            # Determine regime class
            if regime_score > 1.0:
                regime_class = "bullish"
            elif regime_score < -1.0:
                regime_class = "bearish"
            elif abs(regime_score) < 0.5:
                regime_class = "sideways"
            else:
                regime_class = "mixed"
            
            # Normalize confidence
            confidence = min(confidence, 1.0)
            
            return regime_class, confidence
            
        except Exception as e:
            self.logger.error(f"Failed to classify regime: {e}")
            return "unknown", 0.0
    
    def compute_regime_features_for_data(
        self,
        data: List[OHLCVBar],
        symbol: str
    ) -> List[RegimeFeatureResult]:
        """
        Compute regime features for a dataset.
        
        Args:
            data: List of OHLCV bars
            symbol: Trading symbol
            
        Returns:
            List of regime feature results
        """
        if not data:
            return []
        
        try:
            # Convert to DataFrame
            df_data = pd.DataFrame([bar.to_dict() for bar in data])
            df_data['timestamp'] = pd.to_datetime(df_data['timestamp'])
            df_data.set_index('timestamp', inplace=True)
            
            # Calculate regime features
            features = self.calculate_regime_classification_features(df_data, symbol)
            
            # Classify regime for each timestamp
            results = []
            for timestamp, row in df_data.iterrows():
                # Get features for this timestamp
                timestamp_features = {}
                for name, series in features.items():
                    if timestamp in series.index and pd.notna(series[timestamp]):
                        timestamp_features[name] = series[timestamp]
                
                # Classify regime
                regime_class, confidence = self.classify_regime(
                    {name: pd.Series([value]) for name, value in timestamp_features.items()},
                    timestamp
                )
                
                # Create regime feature results
                for feature_name, feature_value in timestamp_features.items():
                    result = RegimeFeatureResult(
                        symbol=symbol,
                        timestamp=timestamp,
                        feature_type=feature_name,
                        value=feature_value,
                        regime_class=regime_class,
                        confidence=confidence
                    )
                    results.append(result)
            
            self.logger.info(f"Computed {len(results)} regime features for {symbol}")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to compute regime features for {symbol}: {e}")
            return []


# Factory function for creating regime feature calculator
def create_regime_feature_calculator(config: RegimeFeatureConfig = None) -> RegimeFeatureCalculator:
    """Create a new regime feature calculator instance."""
    return RegimeFeatureCalculator(config)
