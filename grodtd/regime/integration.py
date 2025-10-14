"""
Integration module for regime classification with existing indicators.

This module provides integration between the regime classification system
and existing technical indicators, ensuring seamless operation with
the current trading system.
"""

import logging
import yaml
from typing import Dict, Optional, List, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from .classifier import RegimeClassifier, RegimeType, RegimeConfig, RegimeFeatures
from .service import RegimeStateService, get_regime_service
from grodtd.features.indicators import VWAPCalculator, TechnicalIndicators, TrendDetector
from grodtd.storage.interfaces import OHLCVBar


class RegimeIndicatorIntegration:
    """
    Integration class that combines regime classification with existing indicators.
    
    This class provides a unified interface for accessing both regime information
    and technical indicators, ensuring consistent data flow throughout the system.
    """
    
    def __init__(self, symbol: str, config_path: Optional[str] = None):
        self.symbol = symbol
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize regime classifier
        self.regime_classifier = RegimeClassifier(symbol, self.config)
        
        # Initialize existing indicators
        self.vwap_calculator = VWAPCalculator(symbol)
        self.technical_indicators = TechnicalIndicators()
        self.trend_detector = TrendDetector(symbol)
        
        # Integration state
        self._last_regime_update: Optional[datetime] = None
        self._regime_history: List[Tuple[datetime, RegimeType, float]] = []
        self._indicator_cache: Dict[str, any] = {}
        
        self.logger.info(f"RegimeIndicatorIntegration initialized for {symbol}")
    
    def _load_config(self, config_path: Optional[str] = None) -> RegimeConfig:
        """Load regime configuration from YAML file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "configs" / "regime.yaml"
        
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Create RegimeConfig from YAML data
            config = RegimeConfig(
                vwap_slope_trending_threshold=config_data.get('vwap_slope', {}).get('trending_threshold', 0.001),
                vwap_slope_ranging_threshold=config_data.get('vwap_slope', {}).get('ranging_threshold', 0.0005),
                vwap_slope_window=config_data.get('vwap_slope', {}).get('window', 20),
                atr_high_volatility_percentile=config_data.get('atr_percentiles', {}).get('high_volatility_percentile', 0.8),
                atr_low_volatility_percentile=config_data.get('atr_percentiles', {}).get('low_volatility_percentile', 0.3),
                volatility_ratio_high=config_data.get('volatility_ratio', {}).get('high_threshold', 1.5),
                volatility_ratio_low=config_data.get('volatility_ratio', {}).get('low_threshold', 0.7),
                momentum_trending_threshold=config_data.get('momentum', {}).get('trending_threshold', 0.02),
                momentum_ranging_threshold=config_data.get('momentum', {}).get('ranging_threshold', 0.005)
            )
            
            self.logger.info(f"Loaded regime configuration from {config_path}")
            return config
            
        except Exception as e:
            self.logger.warning(f"Failed to load regime config from {config_path}: {e}. Using defaults.")
            return RegimeConfig()
    
    def update_with_bar(self, bar: OHLCVBar) -> Dict[str, any]:
        """
        Update all indicators and regime classification with new bar data.
        
        Args:
            bar: New OHLCV bar data
            
        Returns:
            Dictionary containing all updated indicators and regime information
        """
        try:
            # Update existing indicators
            vwap = self.vwap_calculator.update(bar)
            trend = self.trend_detector.update(bar)
            
            # Update regime classification
            regime = self.regime_classifier.update(bar)
            regime_confidence = self.regime_classifier.get_classification_confidence()
            
            # Update integration state
            self._last_regime_update = datetime.now()
            self._regime_history.append((self._last_regime_update, regime, regime_confidence))
            
            # Keep only last 100 regime updates
            if len(self._regime_history) > 100:
                self._regime_history = self._regime_history[-100:]
            
            # Update indicator cache
            self._indicator_cache.update({
                'vwap': vwap,
                'trend': trend,
                'regime': regime,
                'regime_confidence': regime_confidence,
                'timestamp': bar.timestamp
            })
            
            # Log regime changes
            if len(self._regime_history) > 1:
                prev_regime = self._regime_history[-2][1]
                if regime != prev_regime:
                    self.logger.info(
                        f"Regime change for {self.symbol}: {prev_regime.value} -> {regime.value} "
                        f"(confidence: {regime_confidence:.2f})"
                    )
            
            # Return comprehensive indicator data
            return {
                'symbol': self.symbol,
                'timestamp': bar.timestamp,
                'price': bar.close,
                'volume': bar.volume,
                'vwap': vwap,
                'trend': trend,
                'regime': regime.value,
                'regime_confidence': regime_confidence,
                'regime_features': self._get_regime_features_dict(),
                'indicator_summary': self._get_indicator_summary()
            }
            
        except Exception as e:
            self.logger.error(f"Error updating indicators for {self.symbol}: {e}")
            return self._get_error_response(bar)
    
    def _get_regime_features_dict(self) -> Dict[str, float]:
        """Get regime features as a dictionary."""
        features = self.regime_classifier.get_regime_features()
        if features is None:
            return {}
        
        return {
            'vwap_slope': features.vwap_slope,
            'atr_percentile': features.atr_percentile,
            'volatility_ratio': features.volatility_ratio,
            'price_momentum': features.price_momentum,
            'volume_trend': features.volume_trend
        }
    
    def _get_indicator_summary(self) -> Dict[str, any]:
        """Get summary of all current indicators."""
        return {
            'vwap': self.vwap_calculator.get_current_vwap(),
            'trend': self.trend_detector.get_current_trend(),
            'trend_indicators': self.trend_detector.get_current_indicators(),
            'regime': self.regime_classifier.get_current_regime(),
            'regime_confidence': self.regime_classifier.get_classification_confidence()
        }
    
    def _get_error_response(self, bar: OHLCVBar) -> Dict[str, any]:
        """Get error response when indicator update fails."""
        return {
            'symbol': self.symbol,
            'timestamp': bar.timestamp,
            'price': bar.close,
            'volume': bar.volume,
            'error': True,
            'regime': 'unknown',
            'regime_confidence': 0.0
        }
    
    def get_current_regime(self) -> Optional[RegimeType]:
        """Get current regime."""
        return self.regime_classifier.get_current_regime()
    
    def get_regime_confidence(self) -> float:
        """Get current regime confidence."""
        return self.regime_classifier.get_classification_confidence()
    
    def get_regime_history(self, hours: int = 24) -> List[Tuple[datetime, RegimeType, float]]:
        """
        Get regime history for the specified time period.
        
        Args:
            hours: Number of hours of history to return
            
        Returns:
            List of (timestamp, regime, confidence) tuples
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [(ts, regime, conf) for ts, regime, conf in self._regime_history 
                if ts >= cutoff_time]
    
    def get_regime_stability(self, hours: int = 1) -> float:
        """
        Calculate regime stability over the specified time period.
        
        Args:
            hours: Time period to analyze
            
        Returns:
            Stability score (0.0 to 1.0, where 1.0 is most stable)
        """
        history = self.get_regime_history(hours)
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
    
    def get_regime_transitions(self, hours: int = 24) -> List[Dict[str, any]]:
        """
        Get regime transitions over the specified time period.
        
        Args:
            hours: Time period to analyze
            
        Returns:
            List of transition dictionaries
        """
        history = self.get_regime_history(hours)
        transitions = []
        
        for i in range(1, len(history)):
            prev_ts, prev_regime, prev_conf = history[i-1]
            curr_ts, curr_regime, curr_conf = history[i]
            
            if prev_regime != curr_regime:
                transitions.append({
                    'timestamp': curr_ts,
                    'from_regime': prev_regime.value,
                    'to_regime': curr_regime.value,
                    'from_confidence': prev_conf,
                    'to_confidence': curr_conf,
                    'duration_minutes': (curr_ts - prev_ts).total_seconds() / 60
                })
        
        return transitions
    
    def is_regime_stable(self, stability_threshold: float = 0.8, hours: int = 1) -> bool:
        """
        Check if the current regime is stable.
        
        Args:
            stability_threshold: Minimum stability score required
            hours: Time period to analyze
            
        Returns:
            True if regime is stable
        """
        stability = self.get_regime_stability(hours)
        return stability >= stability_threshold
    
    def get_regime_recommendations(self) -> Dict[str, any]:
        """
        Get trading recommendations based on current regime.
        
        Returns:
            Dictionary with regime-based recommendations
        """
        current_regime = self.get_current_regime()
        confidence = self.get_regime_confidence()
        
        if current_regime is None:
            return {'recommendation': 'unknown', 'confidence': 0.0}
        
        recommendations = {
            RegimeType.TRENDING: {
                'recommendation': 'trend_following',
                'description': 'Market is trending - consider trend-following strategies',
                'risk_level': 'medium'
            },
            RegimeType.RANGING: {
                'recommendation': 'mean_reversion',
                'description': 'Market is ranging - consider mean reversion strategies',
                'risk_level': 'low'
            },
            RegimeType.HIGH_VOLATILITY: {
                'recommendation': 'reduce_exposure',
                'description': 'High volatility detected - consider reducing position sizes',
                'risk_level': 'high'
            },
            RegimeType.TRANSITION: {
                'recommendation': 'wait',
                'description': 'Market is transitioning - wait for clearer signals',
                'risk_level': 'medium'
            }
        }
        
        base_rec = recommendations.get(current_regime, {})
        return {
            **base_rec,
            'confidence': confidence,
            'regime': current_regime.value,
            'stability': self.get_regime_stability()
        }
    
    def reset(self):
        """Reset all indicators and regime classification."""
        self.regime_classifier.reset()
        self.vwap_calculator.reset()
        self.trend_detector.reset()
        self._regime_history.clear()
        self._indicator_cache.clear()
        self._last_regime_update = None
        self.logger.info(f"Reset all indicators for {self.symbol}")


class RegimeIntegrationManager:
    """
    Manager class for handling multiple symbol integrations.
    
    This class provides a centralized way to manage regime classification
    and indicator integration across multiple symbols.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        self._integrations: Dict[str, RegimeIndicatorIntegration] = {}
        self._regime_service = get_regime_service()
        
        self.logger.info("RegimeIntegrationManager initialized")
    
    def get_integration(self, symbol: str) -> RegimeIndicatorIntegration:
        """
        Get or create integration for a symbol.
        
        Args:
            symbol: Symbol to get integration for
            
        Returns:
            RegimeIndicatorIntegration instance
        """
        if symbol not in self._integrations:
            self._integrations[symbol] = RegimeIndicatorIntegration(symbol, self.config_path)
            self.logger.info(f"Created integration for {symbol}")
        
        return self._integrations[symbol]
    
    def update_symbol(self, symbol: str, bar: OHLCVBar) -> Dict[str, any]:
        """
        Update indicators and regime for a symbol.
        
        Args:
            symbol: Symbol to update
            bar: New market data
            
        Returns:
            Updated indicator data
        """
        integration = self.get_integration(symbol)
        return integration.update_with_bar(bar)
    
    def get_all_regimes(self) -> Dict[str, Dict[str, any]]:
        """Get regime information for all managed symbols."""
        regimes = {}
        for symbol, integration in self._integrations.items():
            regimes[symbol] = {
                'regime': integration.get_current_regime(),
                'confidence': integration.get_regime_confidence(),
                'stability': integration.get_regime_stability(),
                'recommendations': integration.get_regime_recommendations()
            }
        return regimes
    
    def reset_symbol(self, symbol: str):
        """Reset integration for a symbol."""
        if symbol in self._integrations:
            self._integrations[symbol].reset()
            self.logger.info(f"Reset integration for {symbol}")
    
    def reset_all(self):
        """Reset all integrations."""
        for integration in self._integrations.values():
            integration.reset()
        self.logger.info("Reset all integrations")


# Global integration manager
_integration_manager: Optional[RegimeIntegrationManager] = None


def get_integration_manager() -> RegimeIntegrationManager:
    """Get the global integration manager."""
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = RegimeIntegrationManager()
    return _integration_manager
