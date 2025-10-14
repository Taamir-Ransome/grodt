"""
Unit tests for feature store components.

This module tests the feature store implementation including database schema,
caching mechanisms, feature computation, and performance monitoring.
"""

import unittest
import tempfile
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

from grodtd.storage.feature_store import (
    FeatureStore, FeatureStoreConfig, CachedFeature, RegimeFeature, FeatureMetadata
)
from grodtd.storage.feature_api import (
    FeatureStoreAPI, FeatureAPIConfig, FeatureRequest, FeatureResponse
)
from grodtd.features.regime_features import (
    RegimeFeatureCalculator, RegimeFeatureConfig, RegimeFeatureResult
)
from grodtd.storage.interfaces import OHLCVBar


class TestFeatureStoreDatabaseSchema(unittest.TestCase):
    """Test feature store database schema creation and structure."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_feature_store.db"
        self.config = FeatureStoreConfig(db_path=str(self.db_path))
        self.feature_store = FeatureStore(self.config)
    
    def tearDown(self):
        """Clean up test database."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_database_initialization(self):
        """Test that database schema is created correctly."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check that all tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            self.assertIn('feature_store', tables)
            self.assertIn('regime_features', tables)
            self.assertIn('feature_metadata', tables)
    
    def test_feature_store_table_schema(self):
        """Test feature_store table schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(feature_store)")
            columns = cursor.fetchall()
            
            column_names = [col[1] for col in columns]
            expected_columns = ['id', 'symbol', 'timestamp', 'indicator_type', 'value', 'parameters', 'computed_at']
            
            for expected_col in expected_columns:
                self.assertIn(expected_col, column_names)
    
    def test_regime_features_table_schema(self):
        """Test regime_features table schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(regime_features)")
            columns = cursor.fetchall()
            
            column_names = [col[1] for col in columns]
            expected_columns = ['id', 'symbol', 'timestamp', 'feature_type', 'value', 'regime_class', 'computed_at']
            
            for expected_col in expected_columns:
                self.assertIn(expected_col, column_names)
    
    def test_feature_metadata_table_schema(self):
        """Test feature_metadata table schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(feature_metadata)")
            columns = cursor.fetchall()
            
            column_names = [col[1] for col in columns]
            expected_columns = ['id', 'feature_type', 'parameters', 'version', 'created_at']
            
            for expected_col in expected_columns:
                self.assertIn(expected_col, column_names)
    
    def test_indexes_created(self):
        """Test that performance indexes are created."""
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
            
            for expected_idx in expected_indexes:
                self.assertIn(expected_idx, indexes)


class TestFeatureStoreCaching(unittest.TestCase):
    """Test feature store caching functionality."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_feature_store.db"
        self.config = FeatureStoreConfig(db_path=str(self.db_path))
        self.feature_store = FeatureStore(self.config)
    
    def tearDown(self):
        """Clean up test database."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_cache_technical_indicator(self):
        """Test caching technical indicators."""
        symbol = "BTC"
        timestamp = datetime.now()
        indicator_type = "vwap"
        value = 50000.0
        parameters = {"period": 20}
        
        result = self.feature_store.cache_technical_indicator(
            symbol, timestamp, indicator_type, value, parameters
        )
        
        self.assertTrue(result)
    
    def test_get_cached_indicator(self):
        """Test retrieving cached indicators."""
        symbol = "BTC"
        timestamp = datetime.now()
        indicator_type = "vwap"
        value = 50000.0
        parameters = {"period": 20}
        
        # Cache the indicator
        self.feature_store.cache_technical_indicator(
            symbol, timestamp, indicator_type, value, parameters
        )
        
        # Retrieve the indicator
        cached_value = self.feature_store.get_cached_indicator(
            symbol, timestamp, indicator_type, parameters
        )
        
        self.assertEqual(cached_value, value)
    
    def test_cache_regime_feature(self):
        """Test caching regime features."""
        symbol = "BTC"
        timestamp = datetime.now()
        feature_type = "volatility_ratio"
        value = 1.5
        regime_class = "high_volatility"
        
        result = self.feature_store.cache_regime_feature(
            symbol, timestamp, feature_type, value, regime_class
        )
        
        self.assertTrue(result)
    
    def test_get_cached_regime_feature(self):
        """Test retrieving cached regime features."""
        symbol = "BTC"
        timestamp = datetime.now()
        feature_type = "volatility_ratio"
        value = 1.5
        regime_class = "high_volatility"
        
        # Cache the regime feature
        self.feature_store.cache_regime_feature(
            symbol, timestamp, feature_type, value, regime_class
        )
        
        # Retrieve the regime feature
        cached_value = self.feature_store.get_cached_regime_feature(
            symbol, timestamp, feature_type, regime_class
        )
        
        self.assertEqual(cached_value, value)
    
    def test_cache_miss(self):
        """Test cache miss scenario."""
        symbol = "BTC"
        timestamp = datetime.now()
        indicator_type = "nonexistent"
        parameters = {"period": 20}
        
        cached_value = self.feature_store.get_cached_indicator(
            symbol, timestamp, indicator_type, parameters
        )
        
        self.assertIsNone(cached_value)


class TestFeatureStoreComputation(unittest.TestCase):
    """Test feature store computation functionality."""
    
    def setUp(self):
        """Set up test database and sample data."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_feature_store.db"
        self.config = FeatureStoreConfig(db_path=str(self.db_path))
        self.feature_store = FeatureStore(self.config)
        
        # Create sample OHLCV data
        self.sample_data = self._create_sample_data()
    
    def tearDown(self):
        """Clean up test database."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_sample_data(self):
        """Create sample OHLCV data for testing."""
        data = []
        base_time = datetime.now() - timedelta(hours=24)
        base_price = 50000.0
        
        for i in range(100):
            timestamp = base_time + timedelta(minutes=i)
            price_change = np.random.normal(0, 100)  # Random price change
            price = base_price + price_change
            
            # Create OHLCV bar
            high = price + abs(np.random.normal(0, 50))
            low = price - abs(np.random.normal(0, 50))
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
    
    def test_compute_and_cache_features(self):
        """Test computing and caching features for a dataset."""
        symbol = "BTC"
        parameters = {
            'vwap_period': 20,
            'ema_fast': 9,
            'ema_slow': 20,
            'atr_period': 14,
            'rsi_period': 14
        }
        
        cached_features = self.feature_store.compute_and_cache_features(
            symbol, self.sample_data, parameters
        )
        
        # Check that features were computed
        self.assertIsInstance(cached_features, dict)
        self.assertGreater(len(cached_features), 0)
        
        # Check that features are cached in database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feature_store WHERE symbol = ?", (symbol,))
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
    
    def test_get_feature_history(self):
        """Test retrieving feature history."""
        symbol = "BTC"
        parameters = {'period': 20}
        
        # Cache some features first
        for i in range(10):
            timestamp = datetime.now() - timedelta(hours=i)
            value = 50000.0 + i * 100
            self.feature_store.cache_technical_indicator(
                symbol, timestamp, "vwap", value, parameters
            )
        
        # Get feature history
        start_time = datetime.now() - timedelta(hours=10)
        end_time = datetime.now()
        
        history = self.feature_store.get_feature_history(
            symbol, "vwap", start_time, end_time, parameters
        )
        
        self.assertIsInstance(history, list)
        self.assertGreater(len(history), 0)
        
        # Check that history contains tuples of (timestamp, value)
        for timestamp, value in history:
            self.assertIsInstance(timestamp, datetime)
            self.assertIsInstance(value, (int, float))


class TestFeatureStoreCleanup(unittest.TestCase):
    """Test feature store cleanup functionality."""
    
    def setUp(self):
        """Set up test database with old data."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_feature_store.db"
        self.config = FeatureStoreConfig(db_path=str(self.db_path))
        self.feature_store = FeatureStore(self.config)
        
        # Add old data
        self._add_old_data()
    
    def tearDown(self):
        """Clean up test database."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _add_old_data(self):
        """Add old data for cleanup testing."""
        old_date = datetime.now() - timedelta(days=40)
        
        # Add old feature_store records
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feature_store 
                (symbol, timestamp, indicator_type, value, parameters, computed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("BTC", old_date, "vwap", 50000.0, '{"period": 20}', old_date))
            
            # Add old regime_features records
            cursor.execute("""
                INSERT INTO regime_features 
                (symbol, timestamp, feature_type, value, regime_class, computed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("BTC", old_date, "volatility_ratio", 1.5, "high_volatility", old_date))
            
            conn.commit()
    
    def test_cleanup_old_features(self):
        """Test cleanup of old features."""
        # Verify old data exists
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feature_store")
            initial_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM regime_features")
            initial_regime_count = cursor.fetchone()[0]
        
        self.assertGreater(initial_count, 0)
        self.assertGreater(initial_regime_count, 0)
        
        # Clean up old features (keep 30 days)
        deleted_count = self.feature_store.cleanup_old_features(days_to_keep=30)
        
        # Verify cleanup
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feature_store")
            final_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM regime_features")
            final_regime_count = cursor.fetchone()[0]
        
        self.assertGreater(deleted_count, 0)
        self.assertEqual(final_count, 0)
        self.assertEqual(final_regime_count, 0)


class TestFeatureStoreStats(unittest.TestCase):
    """Test feature store statistics functionality."""
    
    def setUp(self):
        """Set up test database with sample data."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_feature_store.db"
        self.config = FeatureStoreConfig(db_path=str(self.db_path))
        self.feature_store = FeatureStore(self.config)
        
        # Add sample data
        self._add_sample_data()
    
    def tearDown(self):
        """Clean up test database."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _add_sample_data(self):
        """Add sample data for statistics testing."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Add feature_store data
            for i in range(10):
                timestamp = datetime.now() - timedelta(hours=i)
                cursor.execute("""
                    INSERT INTO feature_store 
                    (symbol, timestamp, indicator_type, value, parameters, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("BTC", timestamp, "vwap", 50000.0 + i * 100, '{"period": 20}', timestamp))
            
            # Add regime_features data
            for i in range(5):
                timestamp = datetime.now() - timedelta(hours=i)
                cursor.execute("""
                    INSERT INTO regime_features 
                    (symbol, timestamp, feature_type, value, regime_class, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("BTC", timestamp, "volatility_ratio", 1.0 + i * 0.1, "normal", timestamp))
            
            conn.commit()
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        stats = self.feature_store.get_cache_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('feature_count', stats)
        self.assertIn('symbol_count', stats)
        self.assertIn('indicator_types', stats)
        self.assertIn('regime_feature_count', stats)
        self.assertIn('regime_feature_types', stats)
        
        self.assertEqual(stats['feature_count'], 10)
        self.assertEqual(stats['symbol_count'], 1)
        self.assertEqual(stats['regime_feature_count'], 5)


class TestRegimeFeatureCalculator(unittest.TestCase):
    """Test regime feature calculator functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.config = RegimeFeatureConfig()
        self.calculator = RegimeFeatureCalculator(self.config)
        
        # Create sample DataFrame
        self.sample_df = self._create_sample_dataframe()
    
    def _create_sample_dataframe(self):
        """Create sample DataFrame for testing."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
        np.random.seed(42)  # For reproducible tests
        
        data = {
            'open': 50000 + np.random.randn(100) * 100,
            'high': 50000 + np.random.randn(100) * 100 + 50,
            'low': 50000 + np.random.randn(100) * 100 - 50,
            'close': 50000 + np.random.randn(100) * 100,
            'volume': np.random.randint(1000, 10000, 100)
        }
        
        df = pd.DataFrame(data, index=dates)
        return df
    
    def test_calculate_volatility_ratio(self):
        """Test volatility ratio calculation."""
        vol_ratio = self.calculator.calculate_volatility_ratio(self.sample_df)
        
        self.assertIsInstance(vol_ratio, pd.Series)
        self.assertEqual(len(vol_ratio), len(self.sample_df))
        self.assertFalse(vol_ratio.isna().all())
    
    def test_calculate_momentum_indicators(self):
        """Test momentum indicators calculation."""
        momentum_features = self.calculator.calculate_momentum_indicators(self.sample_df)
        
        self.assertIsInstance(momentum_features, dict)
        expected_features = ['price_momentum', 'volume_momentum', 'high_momentum', 'low_momentum', 'range_momentum']
        
        for feature in expected_features:
            self.assertIn(feature, momentum_features)
            self.assertIsInstance(momentum_features[feature], pd.Series)
    
    def test_calculate_trend_strength(self):
        """Test trend strength calculation."""
        trend_strength = self.calculator.calculate_trend_strength(self.sample_df)
        
        self.assertIsInstance(trend_strength, pd.Series)
        self.assertEqual(len(trend_strength), len(self.sample_df))
    
    def test_calculate_volume_regime_features(self):
        """Test volume regime features calculation."""
        volume_features = self.calculator.calculate_volume_regime_features(self.sample_df)
        
        self.assertIsInstance(volume_features, dict)
        expected_features = ['volume_trend', 'volume_volatility', 'volume_price_correlation', 'volume_acceleration']
        
        for feature in expected_features:
            self.assertIn(feature, volume_features)
            self.assertIsInstance(volume_features[feature], pd.Series)
    
    def test_calculate_regime_classification_features(self):
        """Test regime classification features calculation."""
        features = self.calculator.calculate_regime_classification_features(self.sample_df, "BTC")
        
        self.assertIsInstance(features, dict)
        self.assertGreater(len(features), 0)
    
    def test_classify_regime(self):
        """Test regime classification."""
        # Create sample features
        features = {
            'volatility_ratio': pd.Series([1.2]),
            'price_momentum': pd.Series([0.05]),
            'trend_strength': pd.Series([0.6]),
            'rsi': pd.Series([65])
        }
        
        regime_class, confidence = self.calculator.classify_regime(features, datetime.now())
        
        self.assertIsInstance(regime_class, str)
        self.assertIsInstance(confidence, float)
        self.assertIn(regime_class, ['bullish', 'bearish', 'sideways', 'mixed', 'unknown'])
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)


class TestFeatureStoreAPI(unittest.TestCase):
    """Test feature store API functionality."""
    
    def setUp(self):
        """Set up test API."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_feature_store.db"
        self.config = FeatureAPIConfig(db_path=str(self.db_path))
        self.api = FeatureStoreAPI(self.config)
    
    def tearDown(self):
        """Clean up test database."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_feature_request_creation(self):
        """Test feature request creation."""
        request = FeatureRequest(
            symbol="BTC",
            timestamp=datetime.now(),
            indicator_types=["vwap", "ema_fast"],
            parameters={"period": 20}
        )
        
        self.assertEqual(request.symbol, "BTC")
        self.assertIn("vwap", request.indicator_types)
        self.assertIn("ema_fast", request.indicator_types)
    
    def test_get_features_empty_data(self):
        """Test getting features with no data available."""
        request = FeatureRequest(
            symbol="BTC",
            timestamp=datetime.now(),
            indicator_types=["vwap"]
        )
        
        response = self.api.get_features(request)
        
        self.assertIsInstance(response, FeatureResponse)
        self.assertEqual(response.symbol, "BTC")
        self.assertEqual(len(response.features), 0)
        self.assertFalse(response.cached)
    
    def test_batch_compute_features_empty_data(self):
        """Test batch computing features with no data."""
        features = self.api.batch_compute_features("BTC", [])
        
        self.assertIsInstance(features, dict)
        self.assertEqual(len(features), 0)
    
    def test_get_feature_history(self):
        """Test getting feature history."""
        history = self.api.get_feature_history(
            "BTC", "vwap", 
            datetime.now() - timedelta(days=1),
            datetime.now()
        )
        
        self.assertIsInstance(history, list)
    
    def test_cleanup_old_features(self):
        """Test cleanup of old features."""
        deleted_count = self.api.cleanup_old_features(days_to_keep=30)
        
        self.assertIsInstance(deleted_count, int)
        self.assertGreaterEqual(deleted_count, 0)
    
    def test_get_performance_stats(self):
        """Test getting performance statistics."""
        stats = self.api.get_performance_stats()
        
        self.assertIsInstance(stats, dict)


if __name__ == '__main__':
    unittest.main()
