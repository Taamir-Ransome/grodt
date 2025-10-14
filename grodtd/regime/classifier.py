"""
Market regime classification logic.

This module implements the core regime classification algorithm that analyzes
volatility, momentum, and price action to determine market regime.
"""

import logging
import numpy as np
import pandas as pd
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from grodtd.storage.interfaces import OHLCVBar
from grodtd.features.indicators import VWAPCalculator, TechnicalIndicators
from .logging import get_regime_logger, RegimeLogger


class RegimeType(Enum):
    """Market regime types."""
    TRENDING = "trending"
    RANGING = "ranging"
    TRANSITION = "transition"
    HIGH_VOLATILITY = "high_volatility"


@dataclass
class RegimeFeatures:
    """Features used for regime classification."""
    vwap_slope: float
    atr_percentile: float
    volatility_ratio: float
    price_momentum: float
    volume_trend: float


@dataclass
class RegimeConfig:
    """Configuration for regime classification thresholds."""
    # VWAP slope thresholds
    vwap_slope_trending_threshold: float = 0.001  # 0.1% per period
    vwap_slope_ranging_threshold: float = 0.0005  # 0.05% per period
    
    # ATR percentile thresholds
    atr_high_volatility_percentile: float = 0.8  # 80th percentile
    atr_low_volatility_percentile: float = 0.3  # 30th percentile
    
    # Volatility ratio thresholds
    volatility_ratio_high: float = 1.5  # 50% above historical
    volatility_ratio_low: float = 0.7  # 30% below historical
    
    # Price momentum thresholds
    momentum_trending_threshold: float = 0.02  # 2% momentum
    momentum_ranging_threshold: float = 0.005  # 0.5% momentum
    
    # Volume trend thresholds
    volume_trend_threshold: float = 0.1  # 10% volume change
    
    # Time windows
    vwap_slope_window: int = 20  # 20 periods for VWAP slope
    atr_lookback_days: int = 30  # 30 days for ATR percentiles
    volatility_lookback_days: int = 30  # 30 days for volatility ratio


class RegimeClassifier:
    """
    Market regime classifier that analyzes market data to determine
    the current regime (trending, ranging, transition, high volatility).
    """
    
    def __init__(self, symbol: str, config: Optional[RegimeConfig] = None):
        self.symbol = symbol
        self.config = config or RegimeConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize indicators
        self.vwap_calculator = VWAPCalculator(symbol)
        self.technical_indicators = TechnicalIndicators()
        
        # Historical data storage for percentile calculations
        self._historical_atr: List[float] = []
        self._historical_volatility: List[float] = []
        self._price_history: List[float] = []
        self._volume_history: List[float] = []
        self._vwap_history: List[float] = []
        
        # Current regime state
        self._current_regime: Optional[RegimeType] = None
        self._last_classification_time: Optional[pd.Timestamp] = None
        self._classification_confidence: float = 0.0
        
        # Deterministic behavior guarantees
        self._deterministic_mode: bool = True
        self._classification_history: List[Tuple[pd.Timestamp, RegimeType, float]] = []
        
        # Performance tracking
        self._performance_times: List[float] = []
        
        # Initialize regime logger
        self._regime_logger = get_regime_logger()
        
        self.logger.info(f"RegimeClassifier initialized for {symbol}")
    
    def update(self, bar: OHLCVBar) -> RegimeType:
        """
        Update regime classification with new market data.
        
        Args:
            bar: New OHLCV bar data
            
        Returns:
            Current market regime
        """
        start_time = time.time()
        feature_calc_start = 0.0
        classification_start = 0.0
        
        try:
            # Update indicators
            vwap = self.vwap_calculator.update(bar)
            
            # Store historical data
            self._price_history.append(bar.close)
            self._volume_history.append(bar.volume)
            self._vwap_history.append(vwap)
            
            # Calculate ATR for historical storage
            if len(self._price_history) >= 14:  # Need at least 14 periods for ATR
                recent_data = pd.DataFrame({
                    'high': [bar.high] * 14,
                    'low': [bar.low] * 14,
                    'close': self._price_history[-14:]
                })
                atr = self.technical_indicators.calculate_atr(recent_data, period=14)
                if not atr.empty and not pd.isna(atr.iloc[-1]):
                    self._historical_atr.append(atr.iloc[-1])
            
            # Calculate volatility for historical storage
            if len(self._price_history) >= 20:  # Need at least 20 periods for volatility
                recent_prices = self._price_history[-20:]
                returns = np.diff(np.log(recent_prices))
                volatility = np.std(returns) * np.sqrt(252)  # Annualized volatility
                self._historical_volatility.append(volatility)
            
            # Maintain historical data size (keep last 30 days worth)
            max_history = 30 * 24 * 12  # 30 days * 24 hours * 12 (5-minute bars)
            if len(self._price_history) > max_history:
                self._price_history = self._price_history[-max_history:]
                self._volume_history = self._volume_history[-max_history:]
                self._vwap_history = self._vwap_history[-max_history:]
                self._historical_atr = self._historical_atr[-max_history:]
                self._historical_volatility = self._historical_volatility[-max_history:]
            
            # Calculate features with timing
            feature_calc_start = time.time()
            features = self._calculate_features(bar, vwap)
            feature_calc_time = (time.time() - feature_calc_start) * 1000
            
            # Classify regime with timing
            classification_start = time.time()
            regime = self._classify_regime(features)
            classification_time = (time.time() - classification_start) * 1000
            
            # Store previous regime for transition logging
            previous_regime = self._current_regime
            previous_confidence = self._classification_confidence
            
            # Update state
            if regime != self._current_regime:
                self.logger.info(f"Regime changed for {self.symbol}: {self._current_regime} -> {regime}")
                self._current_regime = regime
                self._last_classification_time = pd.Timestamp.now()
                
                # Log regime transition
                if previous_regime is not None:
                    transition_duration = 0.0  # Default for first transition
                    if len(self._classification_history) > 0:
                        last_transition_time = self._classification_history[-1][0]
                        transition_duration = (self._last_classification_time - last_transition_time).total_seconds() / 60
                    
                    self._regime_logger.log_regime_transition(
                        self.symbol, previous_regime, regime,
                        previous_confidence, self._classification_confidence,
                        transition_duration, features
                    )
            
            # Calculate confidence
            self._classification_confidence = self._calculate_confidence(features, regime)
            
            # Store classification in history for deterministic behavior
            self._classification_history.append((
                self._last_classification_time or pd.Timestamp.now(),
                regime,
                self._classification_confidence
            ))
            
            # Keep only last 1000 classifications for memory management
            if len(self._classification_history) > 1000:
                self._classification_history = self._classification_history[-1000:]
            
            # Calculate total processing time
            total_time = (time.time() - start_time) * 1000
            self._performance_times.append(total_time)
            
            # Keep only last 100 performance times
            if len(self._performance_times) > 100:
                self._performance_times = self._performance_times[-100:]
            
            # Generate reasoning for classification
            reasoning = self._generate_classification_reasoning(features, regime)
            
            # Log comprehensive classification decision
            self._regime_logger.log_classification_decision(
                self.symbol, regime, self._classification_confidence,
                features, reasoning, total_time
            )
            
            # Log performance metrics
            memory_usage = self._estimate_memory_usage()
            self._regime_logger.log_performance_metrics(
                self.symbol, classification_time, feature_calc_time,
                total_time, memory_usage
            )
            
            # Log classification decision
            self.logger.debug(
                f"Regime classification for {self.symbol}: {regime.value} "
                f"(confidence: {self._classification_confidence:.2f}, "
                f"reasoning: {reasoning})"
            )
            
            return regime
            
        except Exception as e:
            self.logger.error(f"Error in regime classification for {self.symbol}: {e}")
            # Return previous regime or default to transition
            return self._current_regime or RegimeType.TRANSITION
    
    def _calculate_features(self, bar: OHLCVBar, vwap: float) -> RegimeFeatures:
        """Calculate features for regime classification."""
        
        # VWAP slope calculation
        vwap_slope = self._calculate_vwap_slope()
        
        # ATR percentile calculation
        atr_percentile = self._calculate_atr_percentile()
        
        # Volatility ratio calculation
        volatility_ratio = self._calculate_volatility_ratio()
        
        # Price momentum calculation
        price_momentum = self._calculate_price_momentum(bar.close)
        
        # Volume trend calculation
        volume_trend = self._calculate_volume_trend(bar.volume)
        
        return RegimeFeatures(
            vwap_slope=vwap_slope,
            atr_percentile=atr_percentile,
            volatility_ratio=volatility_ratio,
            price_momentum=price_momentum,
            volume_trend=volume_trend
        )
    
    def _calculate_vwap_slope(self) -> float:
        """Calculate VWAP slope over the configured window."""
        if len(self._vwap_history) < self.config.vwap_slope_window:
            return 0.0
        
        recent_vwap = self._vwap_history[-self.config.vwap_slope_window:]
        if len(recent_vwap) < 2:
            return 0.0
        
        # Calculate slope using linear regression
        x = np.arange(len(recent_vwap))
        y = np.array(recent_vwap)
        
        # Simple linear regression slope
        n = len(x)
        slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - np.sum(x)**2)
        
        return slope
    
    def _calculate_atr_percentile(self) -> float:
        """Calculate current ATR percentile relative to historical data."""
        if len(self._historical_atr) < 10:  # Need at least 10 historical ATR values
            return 0.5  # Default to median
        
        current_atr = self._historical_atr[-1] if self._historical_atr else 0.0
        if current_atr == 0.0:
            return 0.5
        
        # Calculate percentile
        historical_atr = np.array(self._historical_atr[:-1])  # Exclude current value
        percentile = np.sum(historical_atr <= current_atr) / len(historical_atr)
        
        return percentile
    
    def _calculate_volatility_ratio(self) -> float:
        """Calculate current volatility ratio vs historical average."""
        if len(self._historical_volatility) < 10:  # Need at least 10 historical values
            return 1.0  # Default to 1.0 (no change)
        
        current_volatility = self._historical_volatility[-1] if self._historical_volatility else 0.0
        if current_volatility == 0.0:
            return 1.0
        
        # Calculate historical average (exclude current value)
        historical_volatility = self._historical_volatility[:-1]
        if not historical_volatility:
            return 1.0
        
        historical_avg = np.mean(historical_volatility)
        if historical_avg == 0.0:
            return 1.0
        
        return current_volatility / historical_avg
    
    def _calculate_price_momentum(self, current_price: float) -> float:
        """Calculate price momentum over recent periods."""
        if len(self._price_history) < 20:  # Need at least 20 periods
            return 0.0
        
        # Calculate momentum as percentage change over last 20 periods
        old_price = self._price_history[-20]
        if old_price == 0.0:
            return 0.0
        
        momentum = (current_price - old_price) / old_price
        return momentum
    
    def _calculate_volume_trend(self, current_volume: float) -> float:
        """Calculate volume trend over recent periods."""
        if len(self._volume_history) < 10:  # Need at least 10 periods
            return 0.0
        
        # Calculate volume trend as percentage change
        recent_volumes = self._volume_history[-10:]
        avg_volume = np.mean(recent_volumes[:-1])  # Exclude current volume
        
        if avg_volume == 0.0:
            return 0.0
        
        volume_trend = (current_volume - avg_volume) / avg_volume
        return volume_trend
    
    def _classify_regime(self, features: RegimeFeatures) -> RegimeType:
        """Classify regime based on calculated features."""
        
        # High volatility check (highest priority)
        if (features.atr_percentile >= self.config.atr_high_volatility_percentile or
            features.volatility_ratio >= self.config.volatility_ratio_high):
            return RegimeType.HIGH_VOLATILITY
        
        # Trending regime check
        if (abs(features.vwap_slope) >= self.config.vwap_slope_trending_threshold and
            abs(features.price_momentum) >= self.config.momentum_trending_threshold):
            return RegimeType.TRENDING
        
        # Ranging regime check
        if (abs(features.vwap_slope) <= self.config.vwap_slope_ranging_threshold and
            abs(features.price_momentum) <= self.config.momentum_ranging_threshold):
            return RegimeType.RANGING
        
        # Default to transition
        return RegimeType.TRANSITION
    
    def _calculate_confidence(self, features: RegimeFeatures, regime: RegimeType) -> float:
        """Calculate confidence score for the classification."""
        confidence = 0.5  # Base confidence
        
        # Adjust confidence based on feature strength
        if regime == RegimeType.HIGH_VOLATILITY:
            if features.atr_percentile >= self.config.atr_high_volatility_percentile:
                confidence += 0.3
            if features.volatility_ratio >= self.config.volatility_ratio_high:
                confidence += 0.2
        
        elif regime == RegimeType.TRENDING:
            slope_strength = min(abs(features.vwap_slope) / self.config.vwap_slope_trending_threshold, 2.0)
            momentum_strength = min(abs(features.price_momentum) / self.config.momentum_trending_threshold, 2.0)
            confidence += (slope_strength + momentum_strength) * 0.15
        
        elif regime == RegimeType.RANGING:
            slope_stability = 1.0 - min(abs(features.vwap_slope) / self.config.vwap_slope_ranging_threshold, 1.0)
            momentum_stability = 1.0 - min(abs(features.price_momentum) / self.config.momentum_ranging_threshold, 1.0)
            confidence += (slope_stability + momentum_stability) * 0.15
        
        # Cap confidence between 0.0 and 1.0
        return max(0.0, min(1.0, confidence))
    
    def get_current_regime(self) -> Optional[RegimeType]:
        """Get the current regime."""
        return self._current_regime
    
    def get_classification_confidence(self) -> float:
        """Get the confidence of the current classification."""
        return self._classification_confidence
    
    def get_last_classification_time(self) -> Optional[pd.Timestamp]:
        """Get the timestamp of the last classification."""
        return self._last_classification_time
    
    def get_regime_features(self) -> Optional[RegimeFeatures]:
        """Get the latest calculated features."""
        if len(self._price_history) < 2:
            return None
        
        # Use the most recent bar data
        recent_bar = OHLCVBar(
            timestamp=pd.Timestamp.now(),
            open=self._price_history[-1],
            high=self._price_history[-1],
            low=self._price_history[-1],
            close=self._price_history[-1],
            volume=self._volume_history[-1] if self._volume_history else 0.0
        )
        
        vwap = self.vwap_calculator.get_current_vwap()
        return self._calculate_features(recent_bar, vwap)
    
    def _generate_classification_reasoning(self, features: RegimeFeatures, regime: RegimeType) -> str:
        """Generate human-readable reasoning for classification decision."""
        reasons = []
        
        if regime == RegimeType.HIGH_VOLATILITY:
            if features.atr_percentile >= self.config.atr_high_volatility_percentile:
                reasons.append(f"ATR percentile {features.atr_percentile:.2f} >= {self.config.atr_high_volatility_percentile}")
            if features.volatility_ratio >= self.config.volatility_ratio_high:
                reasons.append(f"Volatility ratio {features.volatility_ratio:.2f} >= {self.config.volatility_ratio_high}")
        
        elif regime == RegimeType.TRENDING:
            if abs(features.vwap_slope) >= self.config.vwap_slope_trending_threshold:
                reasons.append(f"VWAP slope {features.vwap_slope:.4f} >= {self.config.vwap_slope_trending_threshold}")
            if abs(features.price_momentum) >= self.config.momentum_trending_threshold:
                reasons.append(f"Price momentum {features.price_momentum:.3f} >= {self.config.momentum_trending_threshold}")
        
        elif regime == RegimeType.RANGING:
            if abs(features.vwap_slope) <= self.config.vwap_slope_ranging_threshold:
                reasons.append(f"VWAP slope {features.vwap_slope:.4f} <= {self.config.vwap_slope_ranging_threshold}")
            if abs(features.price_momentum) <= self.config.momentum_ranging_threshold:
                reasons.append(f"Price momentum {features.price_momentum:.3f} <= {self.config.momentum_ranging_threshold}")
        
        else:  # TRANSITION
            reasons.append("No clear regime indicators - defaulting to transition")
        
        return "; ".join(reasons) if reasons else "No specific reasoning available"
    
    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage in MB."""
        # Rough estimation of memory usage
        price_memory = len(self._price_history) * 8  # 8 bytes per float
        volume_memory = len(self._volume_history) * 8
        vwap_memory = len(self._vwap_history) * 8
        atr_memory = len(self._historical_atr) * 8
        volatility_memory = len(self._historical_volatility) * 8
        history_memory = len(self._classification_history) * 100  # Rough estimate for tuples
        
        total_bytes = (price_memory + volume_memory + vwap_memory + 
                      atr_memory + volatility_memory + history_memory)
        
        return total_bytes / (1024 * 1024)  # Convert to MB
    
    def get_classification_history(self, hours: int = 24) -> List[Tuple[pd.Timestamp, RegimeType, float]]:
        """
        Get classification history for the specified time period.
        
        Args:
            hours: Number of hours of history to return
            
        Returns:
            List of (timestamp, regime, confidence) tuples
        """
        cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=hours)
        return [(ts, regime, conf) for ts, regime, conf in self._classification_history 
                if ts >= cutoff_time]
    
    def get_performance_summary(self) -> Dict[str, float]:
        """Get performance summary statistics."""
        if not self._performance_times:
            return {'error': 'No performance data available'}
        
        return {
            'avg_time_ms': np.mean(self._performance_times),
            'max_time_ms': np.max(self._performance_times),
            'min_time_ms': np.min(self._performance_times),
            'std_time_ms': np.std(self._performance_times),
            'total_classifications': len(self._performance_times)
        }
    
    def is_deterministic(self) -> bool:
        """Check if the classifier is in deterministic mode."""
        return self._deterministic_mode
    
    def set_deterministic_mode(self, enabled: bool):
        """Enable or disable deterministic mode."""
        self._deterministic_mode = enabled
        self.logger.info(f"Deterministic mode {'enabled' if enabled else 'disabled'} for {self.symbol}")
    
    def get_regime_stability(self, hours: int = 1) -> float:
        """
        Calculate regime stability over the specified time period.
        
        Args:
            hours: Time period to analyze
            
        Returns:
            Stability score (0.0 to 1.0, where 1.0 is most stable)
        """
        history = self.get_classification_history(hours)
        if len(history) < 2:
            return 0.0
        
        # Count regime changes
        regime_changes = 0
        for i in range(1, len(history)):
            if history[i][1] != history[i-1][1]:
                regime_changes += 1
        
        # Calculate stability (fewer changes = higher stability)
        max_possible_changes = len(history) - 1
        if max_possible_changes == 0:
            return 1.0
        
        stability = 1.0 - (regime_changes / max_possible_changes)
        return max(0.0, min(1.0, stability))
    
    def reset(self):
        """Reset the classifier state."""
        self.vwap_calculator.reset()
        self._historical_atr.clear()
        self._historical_volatility.clear()
        self._price_history.clear()
        self._volume_history.clear()
        self._vwap_history.clear()
        self._current_regime = None
        self._last_classification_time = None
        self._classification_confidence = 0.0
        self._classification_history.clear()
        self._performance_times.clear()
        self.logger.info(f"RegimeClassifier reset for {self.symbol}")
