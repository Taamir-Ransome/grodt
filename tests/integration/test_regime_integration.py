"""
Integration tests for regime classification system.

This module contains integration tests that verify the regime classification
system works correctly with existing indicators and the broader trading system.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import tempfile
import os

from grodtd.regime import (
    RegimeClassifier, RegimeType, RegimeConfig, RegimeStateService,
    RegimeIndicatorIntegration, RegimeIntegrationManager
)
from grodtd.features.indicators import VWAPCalculator, TechnicalIndicators, TrendDetector
from grodtd.storage.interfaces import OHLCVBar


class TestRegimeIndicatorIntegration:
    """Integration tests for regime classification with existing indicators."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.symbol = "TEST"
        self.integration = RegimeIndicatorIntegration(self.symbol)
        
        # Create realistic market data
        self.trending_data = self._create_trending_data()
        self.ranging_data = self._create_ranging_data()
        self.volatile_data = self._create_volatile_data()
    
    def _create_trending_data(self):
        """Create trending market data."""
        data = []
        base_price = 100.0
        for i in range(50):
            # Strong uptrend
            price = base_price + (i * 0.2)
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 0.1,
                low=price - 0.1,
                close=price,
                volume=1000.0 + (i * 10)  # Increasing volume
            )
            data.append(bar)
        return data
    
    def _create_ranging_data(self):
        """Create ranging market data."""
        data = []
        base_price = 100.0
        for i in range(50):
            # Oscillating around base price
            price = base_price + (0.5 * np.sin(i * 0.3))
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 0.1,
                low=price - 0.1,
                close=price,
                volume=1000.0
            )
            data.append(bar)
        return data
    
    def _create_volatile_data(self):
        """Create high volatility market data."""
        data = []
        base_price = 100.0
        np.random.seed(42)  # For reproducible tests
        for i in range(50):
            # High volatility with large price swings
            price = base_price + (2.0 * np.random.normal(0, 1))
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=1000.0 + (i * 5)
            )
            data.append(bar)
        return data
    
    def test_trending_pattern_integration(self):
        """Test integration with trending market pattern."""
        results = []
        for bar in self.trending_data:
            result = self.integration.update_with_bar(bar)
            results.append(result)
        
        # Check final result
        final_result = results[-1]
        assert final_result['regime'] == 'trending'
        assert final_result['confidence'] > 0.0
        assert 'vwap' in final_result
        assert 'trend' in final_result
        
        # Check regime stability over time
        stability = self.integration.get_regime_stability(hours=1)
        assert stability > 0.5  # Should be relatively stable
    
    def test_ranging_pattern_integration(self):
        """Test integration with ranging market pattern."""
        # Reset integration
        self.integration.reset()
        
        results = []
        for bar in self.ranging_data:
            result = self.integration.update_with_bar(bar)
            results.append(result)
        
        # Check final result
        final_result = results[-1]
        assert final_result['regime'] == 'ranging'
        assert final_result['confidence'] > 0.0
        
        # Check that VWAP slope is low (indicating ranging)
        features = final_result.get('regime_features', {})
        assert abs(features.get('vwap_slope', 0)) < 0.001
    
    def test_volatile_pattern_integration(self):
        """Test integration with high volatility pattern."""
        # Reset integration
        self.integration.reset()
        
        results = []
        for bar in self.volatile_data:
            result = self.integration.update_with_bar(bar)
            results.append(result)
        
        # Check final result
        final_result = results[-1]
        assert final_result['regime'] == 'high_volatility'
        assert final_result['confidence'] > 0.0
        
        # Check volatility features
        features = final_result.get('regime_features', {})
        assert features.get('volatility_ratio', 0) > 1.0  # Above historical average
    
    def test_regime_transitions(self):
        """Test regime transitions during integration."""
        # Start with ranging data
        ranging_results = []
        for bar in self.ranging_data[:20]:
            result = self.integration.update_with_bar(bar)
            ranging_results.append(result)
        
        # Switch to trending data
        trending_results = []
        for bar in self.trending_data[:20]:
            result = self.integration.update_with_bar(bar)
            trending_results.append(result)
        
        # Check that regime transitioned
        assert ranging_results[-1]['regime'] == 'ranging'
        assert trending_results[-1]['regime'] == 'trending'
        
        # Check transition history
        transitions = self.integration.get_regime_transitions(hours=1)
        assert len(transitions) > 0
        assert transitions[-1]['from_regime'] == 'ranging'
        assert transitions[-1]['to_regime'] == 'trending'
    
    def test_performance_benchmarks(self):
        """Test performance benchmarks for 5-minute update cycle."""
        import time
        
        # Measure performance over multiple updates
        start_time = time.time()
        results = []
        
        for i, bar in enumerate(self.trending_data[:20]):
            update_start = time.time()
            result = self.integration.update_with_bar(bar)
            update_time = (time.time() - update_start) * 1000  # Convert to ms
            results.append(update_time)
        
        total_time = time.time() - start_time
        avg_time = np.mean(results)
        max_time = np.max(results)
        
        # Performance requirements for 5-minute update cycle
        assert avg_time < 100  # Average should be under 100ms
        assert max_time < 500  # Maximum should be under 500ms
        assert total_time < 1.0  # Total time should be under 1 second
        
        # Check performance summary
        perf_summary = self.integration.regime_classifier.get_performance_summary()
        assert 'avg_time_ms' in perf_summary
        assert perf_summary['avg_time_ms'] < 100
    
    def test_memory_usage(self):
        """Test memory usage during extended operation."""
        # Run for extended period to test memory management
        for i in range(100):
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=100.0 + (i * 0.1),
                high=101.0 + (i * 0.1),
                low=99.0 + (i * 0.1),
                close=100.0 + (i * 0.1),
                volume=1000.0
            )
            result = self.integration.update_with_bar(bar)
        
        # Check that memory usage is reasonable
        memory_usage = self.integration.regime_classifier._estimate_memory_usage()
        assert memory_usage < 10.0  # Should be under 10MB
        
        # Check that historical data is being managed
        history = self.integration.get_regime_history(hours=24)
        assert len(history) <= 100  # Should not exceed reasonable limits


class TestRegimeServiceIntegration:
    """Integration tests for RegimeStateService with multiple symbols."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.service = RegimeStateService()
        self.symbols = ["AAPL", "GOOGL", "MSFT"]
        
        # Create test data for each symbol
        self.test_data = {}
        for symbol in self.symbols:
            self.test_data[symbol] = []
            for i in range(20):
                bar = OHLCVBar(
                    timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                    open=100.0 + (i * 0.1),
                    high=101.0 + (i * 0.1),
                    low=99.0 + (i * 0.1),
                    close=100.0 + (i * 0.1),
                    volume=1000.0
                )
                self.test_data[symbol].append(bar)
    
    def test_multi_symbol_regime_tracking(self):
        """Test regime tracking across multiple symbols."""
        # Update regimes for all symbols
        for symbol in self.symbols:
            for bar in self.test_data[symbol]:
                regime = self.service.update_regime(symbol, bar)
        
        # Check that all symbols have regimes
        all_regimes = self.service.get_all_regimes()
        assert len(all_regimes) == len(self.symbols)
        
        for symbol in self.symbols:
            assert symbol in all_regimes
            assert all_regimes[symbol] is not None
    
    def test_regime_service_performance(self):
        """Test RegimeStateService performance with multiple symbols."""
        import time
        
        start_time = time.time()
        
        # Update all symbols simultaneously
        for i in range(20):
            for symbol in self.symbols:
                bar = self.test_data[symbol][i]
                self.service.update_regime(symbol, bar)
        
        total_time = time.time() - start_time
        
        # Performance should be reasonable for multiple symbols
        assert total_time < 2.0  # Should complete in under 2 seconds
        
        # Check service summary
        summary = self.service.get_regime_summary()
        assert len(summary) == len(self.symbols)
        
        for symbol in self.symbols:
            assert symbol in summary
            assert summary[symbol]['regime'] is not None
            assert summary[symbol]['confidence'] > 0.0
    
    def test_regime_service_stale_detection(self):
        """Test stale regime detection across multiple symbols."""
        # Update all symbols
        for symbol in self.symbols:
            for bar in self.test_data[symbol]:
                self.service.update_regime(symbol, bar)
        
        # Check that no symbols are stale immediately
        stale_symbols = self.service.get_stale_symbols(max_age_minutes=1)
        assert len(stale_symbols) == 0
        
        # Check individual symbol staleness
        for symbol in self.symbols:
            assert not self.service.is_regime_stale(symbol, max_age_minutes=1)


class TestRegimeIntegrationManager:
    """Integration tests for RegimeIntegrationManager."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.manager = RegimeIntegrationManager()
        self.symbols = ["AAPL", "GOOGL"]
        
        # Create test data
        self.test_data = {}
        for symbol in self.symbols:
            self.test_data[symbol] = []
            for i in range(15):
                bar = OHLCVBar(
                    timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                    open=100.0 + (i * 0.1),
                    high=101.0 + (i * 0.1),
                    low=99.0 + (i * 0.1),
                    close=100.0 + (i * 0.1),
                    volume=1000.0
                )
                self.test_data[symbol].append(bar)
    
    def test_manager_initialization(self):
        """Test integration manager initialization."""
        assert self.manager is not None
        assert len(self.manager._integrations) == 0
    
    def test_symbol_integration_creation(self):
        """Test creation of symbol integrations."""
        for symbol in self.symbols:
            integration = self.manager.get_integration(symbol)
            assert integration is not None
            assert integration.symbol == symbol
        
        # Check that integrations are cached
        assert len(self.manager._integrations) == len(self.symbols)
    
    def test_multi_symbol_updates(self):
        """Test updates across multiple symbols."""
        results = {}
        
        for symbol in self.symbols:
            symbol_results = []
            for bar in self.test_data[symbol]:
                result = self.manager.update_symbol(symbol, bar)
                symbol_results.append(result)
            results[symbol] = symbol_results
        
        # Check that all symbols have results
        for symbol in self.symbols:
            assert len(results[symbol]) == len(self.test_data[symbol])
            assert results[symbol][-1]['regime'] is not None
    
    def test_all_regimes_retrieval(self):
        """Test retrieval of all regime information."""
        # Update all symbols
        for symbol in self.symbols:
            for bar in self.test_data[symbol]:
                self.manager.update_symbol(symbol, bar)
        
        # Get all regimes
        all_regimes = self.manager.get_all_regimes()
        assert len(all_regimes) == len(self.symbols)
        
        for symbol in self.symbols:
            assert symbol in all_regimes
            assert 'regime' in all_regimes[symbol]
            assert 'confidence' in all_regimes[symbol]
            assert 'stability' in all_regimes[symbol]
            assert 'recommendations' in all_regimes[symbol]
    
    def test_manager_reset_functionality(self):
        """Test manager reset functionality."""
        # Update all symbols
        for symbol in self.symbols:
            for bar in self.test_data[symbol]:
                self.manager.update_symbol(symbol, bar)
        
        # Reset all
        self.manager.reset_all()
        
        # Check that all integrations are reset
        for symbol in self.symbols:
            integration = self.manager.get_integration(symbol)
            assert integration.get_current_regime() is None


class TestRegimeAccuracyValidation:
    """Integration tests for regime classification accuracy validation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.classifier = RegimeClassifier("TEST")
        
        # Create known market patterns for accuracy testing
        self.known_patterns = {
            'trending': self._create_known_trending_pattern(),
            'ranging': self._create_known_ranging_pattern(),
            'high_volatility': self._create_known_volatile_pattern()
        }
    
    def _create_known_trending_pattern(self):
        """Create a known trending pattern."""
        data = []
        for i in range(50):
            # Strong uptrend with consistent momentum
            price = 100.0 + (i * 0.3)
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 0.2,
                low=price - 0.1,
                close=price,
                volume=1000.0 + (i * 20)
            )
            data.append(bar)
        return data
    
    def _create_known_ranging_pattern(self):
        """Create a known ranging pattern."""
        data = []
        for i in range(50):
            # Oscillating around base price
            price = 100.0 + (0.3 * np.sin(i * 0.2))
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 0.1,
                low=price - 0.1,
                close=price,
                volume=1000.0
            )
            data.append(bar)
        return data
    
    def _create_known_volatile_pattern(self):
        """Create a known high volatility pattern."""
        data = []
        np.random.seed(42)
        for i in range(50):
            # High volatility with large swings
            price = 100.0 + (3.0 * np.random.normal(0, 1))
            bar = OHLCVBar(
                timestamp=pd.Timestamp.now() + timedelta(minutes=5*i),
                open=price,
                high=price + 1.5,
                low=price - 1.5,
                close=price,
                volume=1000.0 + (i * 10)
            )
            data.append(bar)
        return data
    
    def test_trending_pattern_accuracy(self):
        """Test accuracy on known trending pattern."""
        self.classifier.reset()
        
        for bar in self.known_patterns['trending']:
            regime = self.classifier.update(bar)
        
        # Should classify as trending with high confidence
        assert regime == RegimeType.TRENDING
        assert self.classifier.get_classification_confidence() > 0.7
    
    def test_ranging_pattern_accuracy(self):
        """Test accuracy on known ranging pattern."""
        self.classifier.reset()
        
        for bar in self.known_patterns['ranging']:
            regime = self.classifier.update(bar)
        
        # Should classify as ranging with high confidence
        assert regime == RegimeType.RANGING
        assert self.classifier.get_classification_confidence() > 0.7
    
    def test_volatile_pattern_accuracy(self):
        """Test accuracy on known volatile pattern."""
        self.classifier.reset()
        
        for bar in self.known_patterns['high_volatility']:
            regime = self.classifier.update(bar)
        
        # Should classify as high volatility with high confidence
        assert regime == RegimeType.HIGH_VOLATILITY
        assert self.classifier.get_classification_confidence() > 0.7
    
    def test_overall_accuracy_validation(self):
        """Test overall accuracy across multiple patterns."""
        accuracy_results = {}
        
        for pattern_name, pattern_data in self.known_patterns.items():
            self.classifier.reset()
            
            # Classify the pattern
            for bar in pattern_data:
                regime = self.classifier.update(bar)
            
            # Check if classification matches expected pattern
            expected_regime = {
                'trending': RegimeType.TRENDING,
                'ranging': RegimeType.RANGING,
                'high_volatility': RegimeType.HIGH_VOLATILITY
            }[pattern_name]
            
            accuracy_results[pattern_name] = {
                'correct': regime == expected_regime,
                'confidence': self.classifier.get_classification_confidence(),
                'regime': regime.value
            }
        
        # Calculate overall accuracy
        correct_classifications = sum(1 for result in accuracy_results.values() if result['correct'])
        total_classifications = len(accuracy_results)
        overall_accuracy = correct_classifications / total_classifications
        
        # Should achieve >80% accuracy as per requirements
        assert overall_accuracy >= 0.8, f"Accuracy {overall_accuracy:.2f} below required 80%"
        
        # All classifications should have reasonable confidence
        for pattern_name, result in accuracy_results.items():
            assert result['confidence'] > 0.5, f"Low confidence for {pattern_name}: {result['confidence']:.2f}"


if __name__ == "__main__":
    pytest.main([__file__])
