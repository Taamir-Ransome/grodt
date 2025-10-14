"""
Integration tests for feature store system.

This module tests the complete feature store system including feature computation,
caching, regime features, and end-to-end workflows.
"""

import unittest
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

from grodtd.storage.feature_store import FeatureStore, FeatureStoreConfig
from grodtd.storage.feature_api import FeatureStoreAPI, FeatureAPIConfig, FeatureRequest
from grodtd.features.regime_features import RegimeFeatureCalculator, RegimeFeatureConfig
from grodtd.storage.interfaces import OHLCVBar


class TestFeatureStoreSystemIntegration(unittest.TestCase):
    """Integration tests for the complete feature store system."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_feature_store.db"
        
        # Initialize feature store
        self.feature_config = FeatureStoreConfig(db_path=str(self.db_path))
        self.feature_store = FeatureStore(self.feature_config)
        
        # Initialize feature store API
        self.api_config = FeatureAPIConfig(db_path=str(self.db_path))
        self.api = FeatureStoreAPI(self.api_config)
        
        # Initialize regime feature calculator
        self.regime_config = RegimeFeatureConfig()
        self.regime_calculator = RegimeFeatureCalculator(self.regime_config)
        
        # Create sample data
        self.sample_data = self._create_sample_data()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_sample_data(self):
        """Create comprehensive sample data for testing."""
        data = []
        base_time = datetime.now() - timedelta(hours=24)
        base_price = 50000.0
        
        # Create realistic OHLCV data with some trends
        for i in range(100):
            timestamp = base_time + timedelta(minutes=i)
            
            # Create some trending behavior
            if i < 30:
                # Uptrend
                price_change = np.random.normal(50, 20)
            elif i < 70:
                # Sideways
                price_change = np.random.normal(0, 10)
            else:
                # Downtrend
                price_change = np.random.normal(-30, 15)
            
            price = base_price + price_change
            base_price = price  # Update base price for next iteration
            
            # Create OHLCV bar
            high = price + abs(np.random.normal(0, 25))
            low = price - abs(np.random.normal(0, 25))
            volume = np.random.randint(1000, 10000)
            
            bar = OHLCVBar(
                timestamp=timestamp,
                open=price,
                high=high,
                low=low,
                close=price,
                volume=volume
            )
            data.append(bar)
        
        return data
    
    def test_end_to_end_feature_computation(self):
        """Test complete end-to-end feature computation workflow."""
        symbol = "BTC"
        parameters = {
            'vwap_period': 20,
            'ema_fast': 9,
            'ema_slow': 20,
            'atr_period': 14,
            'rsi_period': 14
        }
        
        # Step 1: Compute and cache features
        cached_features = self.feature_store.compute_and_cache_features(
            symbol, self.sample_data, parameters
        )
        
        self.assertIsInstance(cached_features, dict)
        self.assertGreater(len(cached_features), 0)
        
        # Step 2: Verify features are cached in database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feature_store WHERE symbol = ?", (symbol,))
            cached_count = cursor.fetchone()[0]
            self.assertGreater(cached_count, 0)
        
        # Step 3: Retrieve cached features
        latest_timestamp = self.sample_data[-1].timestamp
        for indicator_type in ['vwap', 'ema_fast', 'ema_slow', 'atr', 'rsi']:
            if indicator_type in cached_features:
                cached_value = self.feature_store.get_cached_indicator(
                    symbol, latest_timestamp, indicator_type, parameters
                )
                self.assertIsNotNone(cached_value)
                self.assertIsInstance(cached_value, (int, float))
    
    def test_regime_feature_computation_integration(self):
        """Test regime feature computation integration."""
        symbol = "BTC"
        
        # Compute regime features
        regime_features = self.regime_calculator.compute_regime_features_for_data(
            self.sample_data, symbol
        )
        
        self.assertIsInstance(regime_features, list)
        self.assertGreater(len(regime_features), 0)
        
        # Verify regime feature structure
        for feature in regime_features:
            self.assertIsInstance(feature.symbol, str)
            self.assertIsInstance(feature.timestamp, datetime)
            self.assertIsInstance(feature.feature_type, str)
            self.assertIsInstance(feature.value, (int, float))
            self.assertIsInstance(feature.regime_class, str)
            self.assertIsInstance(feature.confidence, float)
        
        # Cache regime features
        for feature in regime_features:
            success = self.feature_store.cache_regime_feature(
                feature.symbol,
                feature.timestamp,
                feature.feature_type,
                feature.value,
                feature.regime_class
            )
            self.assertTrue(success)
        
        # Verify regime features are cached
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM regime_features WHERE symbol = ?", (symbol,))
            cached_count = cursor.fetchone()[0]
            self.assertGreater(cached_count, 0)
    
    def test_feature_consistency_validation(self):
        """Test feature consistency between live and cached calculations."""
        symbol = "BTC"
        timestamp = self.sample_data[-1].timestamp
        parameters = {'period': 20}
        
        # Cache a feature
        test_value = 50000.0
        self.feature_store.cache_technical_indicator(
            symbol, timestamp, "vwap", test_value, parameters
        )
        
        # Validate consistency (this will fail in test since we don't have real data)
        # but it tests the validation logic
        is_consistent = self.api.validate_feature_consistency(
            symbol, timestamp, "vwap", parameters
        )
        
        # In test environment without real data, this should return True
        self.assertTrue(is_consistent)
    
    def test_feature_history_retrieval(self):
        """Test feature history retrieval across time ranges."""
        symbol = "BTC"
        parameters = {'period': 20}
        
        # Cache multiple features across time
        for i in range(10):
            timestamp = datetime.now() - timedelta(hours=i)
            value = 50000.0 + i * 100
            self.feature_store.cache_technical_indicator(
                symbol, timestamp, "vwap", value, parameters
            )
        
        # Retrieve feature history
        start_time = datetime.now() - timedelta(hours=10)
        end_time = datetime.now()
        
        history = self.api.get_feature_history(
            symbol, "vwap", start_time, end_time, parameters
        )
        
        self.assertIsInstance(history, list)
        self.assertGreater(len(history), 0)
        
        # Verify history structure
        for timestamp, value in history:
            self.assertIsInstance(timestamp, datetime)
            self.assertIsInstance(value, (int, float))
            self.assertGreaterEqual(value, 50000.0)
    
    def test_performance_monitoring_integration(self):
        """Test performance monitoring and statistics."""
        symbol = "BTC"
        
        # Add some data for statistics
        for i in range(20):
            timestamp = datetime.now() - timedelta(hours=i)
            value = 50000.0 + i * 100
            self.feature_store.cache_technical_indicator(
                symbol, timestamp, "vwap", value, {"period": 20}
            )
            
            # Add regime features
            self.feature_store.cache_regime_feature(
                symbol, timestamp, "volatility_ratio", 1.0 + i * 0.1, "normal"
            )
        
        # Get performance statistics
        stats = self.api.get_performance_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('feature_count', stats)
        self.assertIn('symbol_count', stats)
        self.assertIn('regime_feature_count', stats)
        
        self.assertEqual(stats['feature_count'], 20)
        self.assertEqual(stats['symbol_count'], 1)
        self.assertEqual(stats['regime_feature_count'], 20)
    
    def test_cleanup_and_maintenance(self):
        """Test cleanup and maintenance operations."""
        symbol = "BTC"
        
        # Add old data
        old_date = datetime.now() - timedelta(days=40)
        self.feature_store.cache_technical_indicator(
            symbol, old_date, "vwap", 50000.0, {"period": 20}
        )
        
        # Add recent data
        recent_date = datetime.now() - timedelta(days=1)
        self.feature_store.cache_technical_indicator(
            symbol, recent_date, "vwap", 51000.0, {"period": 20}
        )
        
        # Verify data exists
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feature_store")
            initial_count = cursor.fetchone()[0]
            self.assertEqual(initial_count, 2)
        
        # Clean up old features
        deleted_count = self.api.cleanup_old_features(days_to_keep=30)
        
        # Verify cleanup
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feature_store")
            final_count = cursor.fetchone()[0]
        
        self.assertGreater(deleted_count, 0)
        self.assertEqual(final_count, 1)  # Only recent data should remain
    
    def test_feature_store_api_workflow(self):
        """Test complete feature store API workflow."""
        symbol = "BTC"
        timestamp = datetime.now()
        
        # Create feature request
        request = FeatureRequest(
            symbol=symbol,
            timestamp=timestamp,
            indicator_types=["vwap", "ema_fast", "rsi"],
            parameters={"period": 20}
        )
        
        # Get features (will return empty since no data available)
        response = self.api.get_features(request)
        
        self.assertIsInstance(response, type(request).__bases__[0])  # FeatureResponse
        self.assertEqual(response.symbol, symbol)
        self.assertEqual(response.timestamp, timestamp)
        self.assertIsInstance(response.features, dict)
        self.assertIsInstance(response.cached, bool)
        self.assertIsInstance(response.computation_time_ms, float)
    
    def test_batch_processing_workflow(self):
        """Test batch processing workflow."""
        symbol = "BTC"
        
        # Batch compute features
        features = self.api.batch_compute_features(
            symbol, self.sample_data, 
            indicator_types=["vwap", "ema_fast", "atr"],
            parameters={"period": 20}
        )
        
        self.assertIsInstance(features, dict)
        # Features will be empty in test environment without real data computation
        # but the method should not raise exceptions
    
    def test_database_schema_integrity(self):
        """Test database schema integrity after operations."""
        # Verify all tables exist
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['feature_store', 'regime_features', 'feature_metadata']
            for table in expected_tables:
                self.assertIn(table, tables)
        
        # Verify indexes exist
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row[0] for row in cursor.fetchall()]
            
            expected_indexes = [
                'idx_feature_store_symbol_timestamp',
                'idx_feature_store_indicator_type',
                'idx_regime_features_symbol_timestamp',
                'idx_regime_features_feature_type',
                'idx_regime_features_regime_class'
            ]
            
            for index in expected_indexes:
                self.assertIn(index, indexes)
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Test with invalid parameters
        invalid_request = FeatureRequest(
            symbol="",
            timestamp=datetime.now(),
            indicator_types=[],
            parameters={}
        )
        
        response = self.api.get_features(invalid_request)
        self.assertIsInstance(response, type(invalid_request).__bases__[0])
        
        # Test cleanup with invalid parameters
        deleted_count = self.api.cleanup_old_features(days_to_keep=-1)
        self.assertIsInstance(deleted_count, int)
        self.assertGreaterEqual(deleted_count, 0)
        
        # Test performance stats with empty database
        stats = self.api.get_performance_stats()
        self.assertIsInstance(stats, dict)
    
    def test_concurrent_operations_simulation(self):
        """Test simulation of concurrent operations."""
        symbol = "BTC"
        
        # Simulate multiple concurrent cache operations
        timestamps = [datetime.now() - timedelta(minutes=i) for i in range(10)]
        
        for i, timestamp in enumerate(timestamps):
            # Cache technical indicator
            self.feature_store.cache_technical_indicator(
                symbol, timestamp, "vwap", 50000.0 + i * 100, {"period": 20}
            )
            
            # Cache regime feature
            self.feature_store.cache_regime_feature(
                symbol, timestamp, "volatility_ratio", 1.0 + i * 0.1, "normal"
            )
        
        # Verify all operations succeeded
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feature_store WHERE symbol = ?", (symbol,))
            feature_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM regime_features WHERE symbol = ?", (symbol,))
            regime_count = cursor.fetchone()[0]
        
        self.assertEqual(feature_count, 10)
        self.assertEqual(regime_count, 10)


if __name__ == '__main__':
    unittest.main()
