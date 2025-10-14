"""
Unit tests for regime classification functionality.

This module contains comprehensive unit tests for the regime classification
system, including classifier logic, feature calculations, and deterministic behavior.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import tempfile
import os

from grodtd.regime.classifier import (
    RegimeClassifier, RegimeType, RegimeConfig, RegimeFeatures
)
from grodtd.regime.service import RegimeStateService
from grodtd.regime.integration import RegimeIndicatorIntegration
from grodtd.storage.interfaces import OHLCVBar


class TestRegimeClassifier:
    """Test cases for RegimeClassifier class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.symbol = "TEST"
        self.config = RegimeConfig()
        self.classifier = RegimeClassifier(self.symbol, self.config)
        
        # Create sample OHLCV bar
        self.sample_bar = OHLCVBar(
            timestamp=pd.Timestamp.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )
    
    def test_initialization(self):
        """Test classifier initialization."""
        assert self.classifier.symbol == self.symbol
        assert self.classifier.config == self.config
        assert self.classifier.get_current_regime() is None
        assert self.classifier.get_classification_confidence() == 0.0
        assert self.classifier.is_deterministic() is True
    
    def test_first_classification(self):
        """Test first classification with minimal data."""
        regime = self.classifier.update(self.sample_bar)
        
        # Should return transition for first classification
        assert regime == RegimeType.TRANSITION
        assert self.classifier.get_current_regime() == RegimeType.TRANSITION
        assert self.classifier.get_classification_confidence() >= 0.0
    
    def test_trending_regime_classification(self):
        """Test classification of trending regime."""
        # Create trending price data
        base_price = 100.0
        for i in range(25):  # Enough data for classification
            price = base_price + (i * 0.5)  # Upward trend
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=1000.0
            )
            regime = self.classifier.update(bar)
        
        # Should classify as trending
        assert regime == RegimeType.TRENDING
        assert self.classifier.get_classification_confidence() > 0.0
    
    def test_ranging_regime_classification(self):
        """Test classification of ranging regime."""
        # Create ranging price data
        base_price = 100.0
        for i in range(25):
            # Oscillate around base price
            price = base_price + (0.1 * np.sin(i * 0.5))
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 0.1,
                low=price - 0.1,
                close=price,
                volume=1000.0
            )
            regime = self.classifier.update(bar)
        
        # Should classify as ranging
        assert regime == RegimeType.RANGING
        assert self.classifier.get_classification_confidence() > 0.0
    
    def test_high_volatility_regime_classification(self):
        """Test classification of high volatility regime."""
        # Create high volatility data
        base_price = 100.0
        for i in range(25):
            # High volatility with large price swings
            price = base_price + (2.0 * np.random.normal(0, 1))
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=1000.0
            )
            regime = self.classifier.update(bar)
        
        # Should classify as high volatility
        assert regime == RegimeType.HIGH_VOLATILITY
        assert self.classifier.get_classification_confidence() > 0.0
    
    def test_feature_calculation(self):
        """Test feature calculation methods."""
        # Add some historical data
        for i in range(30):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.0 + i,
                volume=1000.0
            )
            self.classifier.update(bar)
        
        features = self.classifier.get_regime_features()
        assert features is not None
        assert isinstance(features.vwap_slope, float)
        assert isinstance(features.atr_percentile, float)
        assert isinstance(features.volatility_ratio, float)
        assert isinstance(features.price_momentum, float)
        assert isinstance(features.volume_trend, float)
    
    def test_deterministic_behavior(self):
        """Test deterministic behavior guarantees."""
        # Reset classifier
        self.classifier.reset()
        
        # Create deterministic test data
        test_data = []
        for i in range(20):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0
            )
            test_data.append(bar)
        
        # Run classification multiple times with same data
        results = []
        for _ in range(3):
            classifier_copy = RegimeClassifier(self.symbol, self.config)
            for bar in test_data:
                regime = classifier_copy.update(bar)
            results.append(regime)
        
        # All results should be identical
        assert all(r == results[0] for r in results)
    
    def test_regime_transitions(self):
        """Test regime transition detection."""
        # Start with ranging data
        for i in range(10):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=100.5,
                low=99.5,
                close=100.0,
                volume=1000.0
            )
            self.classifier.update(bar)
        
        # Switch to trending data
        for i in range(10, 20):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0 + (i-10) * 0.5,
                high=100.5 + (i-10) * 0.5,
                low=99.5 + (i-10) * 0.5,
                close=100.0 + (i-10) * 0.5,
                volume=1000.0
            )
            regime = self.classifier.update(bar)
        
        # Should have transitioned to trending
        assert regime == RegimeType.TRENDING
    
    def test_performance_tracking(self):
        """Test performance tracking functionality."""
        # Add some data to generate performance metrics
        for i in range(10):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0
            )
            self.classifier.update(bar)
        
        # Check performance summary
        perf_summary = self.classifier.get_performance_summary()
        assert 'avg_time_ms' in perf_summary
        assert 'max_time_ms' in perf_summary
        assert 'total_classifications' in perf_summary
        assert perf_summary['total_classifications'] > 0
    
    def test_regime_stability(self):
        """Test regime stability calculation."""
        # Add stable ranging data
        for i in range(20):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=100.2,
                low=99.8,
                close=100.0,
                volume=1000.0
            )
            self.classifier.update(bar)
        
        stability = self.classifier.get_regime_stability(hours=1)
        assert 0.0 <= stability <= 1.0
    
    def test_reset_functionality(self):
        """Test classifier reset functionality."""
        # Add some data
        for i in range(10):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0
            )
            self.classifier.update(bar)
        
        # Reset classifier
        self.classifier.reset()
        
        # Check that state is reset
        assert self.classifier.get_current_regime() is None
        assert self.classifier.get_classification_confidence() == 0.0
        assert len(self.classifier.get_classification_history()) == 0


class TestRegimeStateService:
    """Test cases for RegimeStateService class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.service = RegimeStateService()
        self.symbol = "TEST"
        self.sample_bar = OHLCVBar(
            timestamp=pd.Timestamp.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )
    
    def test_symbol_registration(self):
        """Test symbol registration."""
        classifier = self.service.register_symbol(self.symbol)
        assert classifier is not None
        assert self.symbol in self.service.get_registered_symbols()
    
    def test_regime_update(self):
        """Test regime update functionality."""
        regime = self.service.update_regime(self.symbol, self.sample_bar)
        assert regime is not None
        assert self.service.get_current_regime(self.symbol) == regime
    
    def test_regime_confidence(self):
        """Test regime confidence tracking."""
        self.service.update_regime(self.symbol, self.sample_bar)
        confidence = self.service.get_regime_confidence(self.symbol)
        assert 0.0 <= confidence <= 1.0
    
    def test_regime_summary(self):
        """Test regime summary functionality."""
        self.service.update_regime(self.symbol, self.sample_bar)
        summary = self.service.get_regime_summary()
        assert self.symbol in summary
        assert 'regime' in summary[self.symbol]
        assert 'confidence' in summary[self.symbol]
    
    def test_stale_regime_detection(self):
        """Test stale regime detection."""
        # Update regime
        self.service.update_regime(self.symbol, self.sample_bar)
        
        # Check if stale (should not be stale immediately)
        assert not self.service.is_regime_stale(self.symbol, max_age_minutes=1)
        
        # Check for stale symbols
        stale_symbols = self.service.get_stale_symbols(max_age_minutes=1)
        assert self.symbol not in stale_symbols
    
    def test_symbol_reset(self):
        """Test symbol reset functionality."""
        self.service.update_regime(self.symbol, self.sample_bar)
        self.service.reset_symbol(self.symbol)
        
        # Check that symbol is no longer in current regimes
        assert self.service.get_current_regime(self.symbol) is None
    
    def test_service_reset(self):
        """Test service reset functionality."""
        self.service.update_regime(self.symbol, self.sample_bar)
        self.service.reset_all()
        
        # Check that all regimes are cleared
        assert len(self.service.get_all_regimes()) == 0


class TestRegimeIndicatorIntegration:
    """Test cases for RegimeIndicatorIntegration class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.symbol = "TEST"
        self.integration = RegimeIndicatorIntegration(self.symbol)
        self.sample_bar = OHLCVBar(
            timestamp=pd.Timestamp.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )
    
    def test_integration_initialization(self):
        """Test integration initialization."""
        assert self.integration.symbol == self.symbol
        assert self.integration.get_current_regime() is None
    
    def test_bar_update(self):
        """Test bar update functionality."""
        result = self.integration.update_with_bar(self.sample_bar)
        
        assert 'symbol' in result
        assert 'regime' in result
        assert 'confidence' in result
        assert result['symbol'] == self.symbol
    
    def test_regime_history(self):
        """Test regime history functionality."""
        # Add some data
        for i in range(10):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0
            )
            self.integration.update_with_bar(bar)
        
        history = self.integration.get_regime_history(hours=1)
        assert len(history) > 0
    
    def test_regime_stability(self):
        """Test regime stability calculation."""
        # Add stable data
        for i in range(20):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=100.1,
                low=99.9,
                close=100.0,
                volume=1000.0
            )
            self.integration.update_with_bar(bar)
        
        stability = self.integration.get_regime_stability(hours=1)
        assert 0.0 <= stability <= 1.0
    
    def test_regime_recommendations(self):
        """Test regime-based recommendations."""
        # Add some data
        for i in range(10):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0
            )
            self.integration.update_with_bar(bar)
        
        recommendations = self.integration.get_regime_recommendations()
        assert 'recommendation' in recommendations
        assert 'confidence' in recommendations
        assert 'regime' in recommendations
    
    def test_integration_reset(self):
        """Test integration reset functionality."""
        # Add some data
        for i in range(5):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0
            )
            self.integration.update_with_bar(bar)
        
        # Reset integration
        self.integration.reset()
        
        # Check that state is reset
        assert self.integration.get_current_regime() is None


class TestRegimeConfig:
    """Test cases for RegimeConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RegimeConfig()
        
        # Check default values
        assert config.vwap_slope_trending_threshold == 0.001
        assert config.vwap_slope_ranging_threshold == 0.0005
        assert config.atr_high_volatility_percentile == 0.8
        assert config.volatility_ratio_high == 1.5
        assert config.momentum_trending_threshold == 0.02
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RegimeConfig(
            vwap_slope_trending_threshold=0.002,
            atr_high_volatility_percentile=0.9,
            volatility_ratio_high=2.0
        )
        
        assert config.vwap_slope_trending_threshold == 0.002
        assert config.atr_high_volatility_percentile == 0.9
        assert config.volatility_ratio_high == 2.0


class TestRegimeFeatures:
    """Test cases for RegimeFeatures class."""
    
    def test_features_initialization(self):
        """Test features initialization."""
        features = RegimeFeatures(
            vwap_slope=0.001,
            atr_percentile=0.5,
            volatility_ratio=1.0,
            price_momentum=0.01,
            volume_trend=0.05
        )
        
        assert features.vwap_slope == 0.001
        assert features.atr_percentile == 0.5
        assert features.volatility_ratio == 1.0
        assert features.price_momentum == 0.01
        assert features.volume_trend == 0.05


class TestRegimeType:
    """Test cases for RegimeType enum."""
    
    def test_regime_types(self):
        """Test regime type values."""
        assert RegimeType.TRENDING.value == "trending"
        assert RegimeType.RANGING.value == "ranging"
        assert RegimeType.TRANSITION.value == "transition"
        assert RegimeType.HIGH_VOLATILITY.value == "high_volatility"
    
    def test_regime_type_comparison(self):
        """Test regime type comparison."""
        regime1 = RegimeType.TRENDING
        regime2 = RegimeType.TRENDING
        regime3 = RegimeType.RANGING
        
        assert regime1 == regime2
        assert regime1 != regime3


# Performance and accuracy tests
class TestRegimeAccuracy:
    """Test cases for regime classification accuracy."""
    
    def test_accuracy_with_known_patterns(self):
        """Test accuracy with known market patterns."""
        classifier = RegimeClassifier("TEST")
        
        # Test trending pattern
        trending_bars = []
        for i in range(30):
            price = 100.0 + (i * 0.1)  # Clear uptrend
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 0.05,
                low=price - 0.05,
                close=price,
                volume=1000.0
            )
            trending_bars.append(bar)
        
        # Classify trending pattern
        for bar in trending_bars:
            regime = classifier.update(bar)
        
        # Should classify as trending
        assert regime == RegimeType.TRENDING
        
        # Test ranging pattern
        classifier.reset()
        ranging_bars = []
        for i in range(30):
            price = 100.0 + (0.1 * np.sin(i * 0.2))  # Oscillating pattern
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 0.05,
                low=price - 0.05,
                close=price,
                volume=1000.0
            )
            ranging_bars.append(bar)
        
        # Classify ranging pattern
        for bar in ranging_bars:
            regime = classifier.update(bar)
        
        # Should classify as ranging
        assert regime == RegimeType.RANGING


if __name__ == "__main__":
    pytest.main([__file__])
