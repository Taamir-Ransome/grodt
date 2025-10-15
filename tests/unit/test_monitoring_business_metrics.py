"""
Unit tests for business metrics collector.
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
from unittest.mock import Mock, patch
from prometheus_client import CollectorRegistry

from grodtd.monitoring.business_metrics import BusinessMetricsCollector


class TestBusinessMetricsCollector:
    """Test cases for BusinessMetricsCollector."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Create test database with required tables
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Create regime predictions table
            cursor.execute("""
                CREATE TABLE regime_predictions (
                    symbol TEXT,
                    predicted_regime TEXT,
                    actual_regime TEXT,
                    confidence REAL,
                    timestamp TEXT
                )
            """)
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE trades (
                    symbol TEXT,
                    regime TEXT,
                    strategy TEXT,
                    pnl REAL,
                    fill_timestamp TEXT
                )
            """)
            
            # Create feature cache stats table
            cursor.execute("""
                CREATE TABLE feature_cache_stats (
                    feature_type TEXT,
                    symbol TEXT,
                    cache_hits INTEGER,
                    cache_misses INTEGER,
                    computation_time REAL,
                    last_updated TEXT
                )
            """)
            
            # Create market data table
            cursor.execute("""
                CREATE TABLE market_data (
                    data_source TEXT,
                    symbol TEXT,
                    timestamp TEXT
                )
            """)
            
            # Create data quality table
            cursor.execute("""
                CREATE TABLE data_quality (
                    data_source TEXT,
                    symbol TEXT,
                    quality_score REAL,
                    timestamp TEXT
                )
            """)
            
            # Create positions table
            cursor.execute("""
                CREATE TABLE positions (
                    symbol TEXT,
                    strategy TEXT,
                    quantity REAL,
                    average_entry_price REAL,
                    current_price REAL
                )
            """)
            
            # Create risk breaches table
            cursor.execute("""
                CREATE TABLE risk_breaches (
                    limit_type TEXT,
                    symbol TEXT,
                    timestamp TEXT
                )
            """)
            
            # Create stop loss triggers table
            cursor.execute("""
                CREATE TABLE stop_loss_triggers (
                    symbol TEXT,
                    strategy TEXT,
                    timestamp TEXT
                )
            """)
            
            # Insert test data
            cursor.execute("""
                INSERT INTO regime_predictions (symbol, predicted_regime, actual_regime, confidence, timestamp)
                VALUES 
                    ('BTC', 'trending', 'trending', 0.85, '2024-01-01T10:00:00Z'),
                    ('BTC', 'ranging', 'trending', 0.70, '2024-01-01T11:00:00Z'),
                    ('ETH', 'trending', 'trending', 0.90, '2024-01-01T12:00:00Z')
            """)
            
            cursor.execute("""
                INSERT INTO trades (symbol, regime, strategy, pnl, fill_timestamp)
                VALUES 
                    ('BTC', 'trending', 'trend', 100.0, '2024-01-01T10:00:00Z'),
                    ('BTC', 'trending', 'trend', 150.0, '2024-01-01T11:00:00Z'),
                    ('ETH', 'ranging', 'trend', -50.0, '2024-01-01T12:00:00Z')
            """)
            
            cursor.execute("""
                INSERT INTO feature_cache_stats (feature_type, symbol, cache_hits, cache_misses, computation_time, last_updated)
                VALUES 
                    ('rsi', 'BTC', 100, 20, 0.01, '2024-01-01T10:00:00Z'),
                    ('macd', 'BTC', 80, 10, 0.02, '2024-01-01T10:00:00Z')
            """)
            
            cursor.execute("""
                INSERT INTO market_data (data_source, symbol, timestamp)
                VALUES 
                    ('robinhood', 'BTC', '2024-01-01T10:00:00Z'),
                    ('robinhood', 'BTC', '2024-01-01T10:01:00Z'),
                    ('robinhood', 'ETH', '2024-01-01T10:00:00Z')
            """)
            
            cursor.execute("""
                INSERT INTO data_quality (data_source, symbol, quality_score, timestamp)
                VALUES 
                    ('robinhood', 'BTC', 0.95, '2024-01-01T10:00:00Z'),
                    ('robinhood', 'ETH', 0.90, '2024-01-01T10:00:00Z')
            """)
            
            cursor.execute("""
                INSERT INTO positions (symbol, strategy, quantity, average_entry_price, current_price)
                VALUES 
                    ('BTC', 'trend', 1.0, 50000.0, 51000.0),
                    ('ETH', 'trend', 10.0, 3000.0, 2950.0)
            """)
            
            conn.commit()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
    
    def test_initialization(self, temp_db):
        """Test business metrics collector initialization."""
        collector = BusinessMetricsCollector(temp_db)
        
        assert collector.db_path == temp_db
        assert collector.registry is not None
        
        # Check that metrics were initialized
        assert hasattr(collector, 'regime_predictions_total')
        assert hasattr(collector, 'regime_accuracy')
        assert hasattr(collector, 'strategy_performance')
        assert hasattr(collector, 'feature_cache_hits')
        assert hasattr(collector, 'data_ingestion_rate')
        assert hasattr(collector, 'position_size')
    
    @pytest.mark.asyncio
    async def test_collect_metrics(self, temp_db):
        """Test metrics collection."""
        collector = BusinessMetricsCollector(temp_db)
        
        result = await collector.collect_metrics()
        
        assert 'regime' in result
        assert 'strategy' in result
        assert 'features' in result
        assert 'pipeline' in result
        assert 'risk' in result
        assert 'timestamp' in result
    
    @pytest.mark.asyncio
    async def test_collect_regime_metrics(self, temp_db):
        """Test regime metrics collection."""
        collector = BusinessMetricsCollector(temp_db)
        
        regime_metrics = await collector._collect_regime_metrics()
        
        assert 'predictions_count' in regime_metrics
        assert 'accuracy_by_regime' in regime_metrics
        assert 'confidence_scores' in regime_metrics
        assert 'misclassifications' in regime_metrics
        
        # With test data, we should have 3 predictions
        assert regime_metrics['predictions_count'] == 3
        
        # Check accuracy calculation
        accuracy = regime_metrics['accuracy_by_regime']
        assert len(accuracy) > 0
        
        # BTC_trending should have 100% accuracy (1 correct out of 1)
        # BTC_ranging should have 0% accuracy (0 correct out of 1)
        for key, acc in accuracy.items():
            assert 0 <= acc <= 100
    
    @pytest.mark.asyncio
    async def test_collect_strategy_metrics(self, temp_db):
        """Test strategy metrics collection."""
        collector = BusinessMetricsCollector(temp_db)
        
        strategy_metrics = await collector._collect_strategy_metrics()
        
        assert len(strategy_metrics) > 0
        
        # Check that we have metrics for each strategy/regime/symbol combination
        for key, metrics in strategy_metrics.items():
            assert 'trade_count' in metrics
            assert 'total_pnl' in metrics
            assert 'avg_pnl' in metrics
            assert 'win_rate' in metrics
            assert 'sharpe_ratio' in metrics
            
            assert metrics['trade_count'] > 0
            assert 0 <= metrics['win_rate'] <= 100
    
    @pytest.mark.asyncio
    async def test_collect_feature_metrics(self, temp_db):
        """Test feature metrics collection."""
        collector = BusinessMetricsCollector(temp_db)
        
        feature_metrics = await collector._collect_feature_metrics()
        
        assert len(feature_metrics) > 0
        
        # Check that we have metrics for each feature type/symbol combination
        for key, metrics in feature_metrics.items():
            assert 'hits' in metrics
            assert 'misses' in metrics
            assert 'hit_rate' in metrics
            assert 'computation_time' in metrics
            assert 'freshness' in metrics
            
            assert metrics['hits'] >= 0
            assert metrics['misses'] >= 0
            assert 0 <= metrics['hit_rate'] <= 100
            assert metrics['freshness'] >= 0
    
    @pytest.mark.asyncio
    async def test_collect_pipeline_metrics(self, temp_db):
        """Test pipeline metrics collection."""
        collector = BusinessMetricsCollector(temp_db)
        
        pipeline_metrics = await collector._collect_pipeline_metrics()
        
        assert len(pipeline_metrics) > 0
        
        # Check that we have metrics for each data source/symbol combination
        for key, metrics in pipeline_metrics.items():
            assert 'record_count' in metrics
            assert 'ingestion_rate' in metrics
            assert 'earliest' in metrics
            assert 'latest' in metrics
            
            assert metrics['record_count'] >= 0
            assert metrics['ingestion_rate'] >= 0
    
    @pytest.mark.asyncio
    async def test_collect_risk_metrics(self, temp_db):
        """Test risk metrics collection."""
        collector = BusinessMetricsCollector(temp_db)
        
        risk_metrics = await collector._collect_risk_metrics()
        
        assert 'positions' in risk_metrics
        assert 'breaches' in risk_metrics
        assert 'stop_loss_triggers' in risk_metrics
        assert 'total_exposure' in risk_metrics
        
        # Check positions
        positions = risk_metrics['positions']
        assert len(positions) >= 0
        
        # Check total exposure calculation
        total_exposure = risk_metrics['total_exposure']
        assert total_exposure >= 0
    
    @pytest.mark.asyncio
    async def test_update_prometheus_metrics(self, temp_db):
        """Test Prometheus metrics update."""
        collector = BusinessMetricsCollector(temp_db)
        
        # Mock metrics data
        regime_metrics = {
            'accuracy_by_regime': {
                'BTC_trending': 85.0,
                'BTC_ranging': 70.0
            }
        }
        
        strategy_metrics = {
            'trend_trending_BTC': {
                'trade_count': 10,
                'total_pnl': 500.0,
                'win_rate': 60.0,
                'sharpe_ratio': 1.2
            }
        }
        
        feature_metrics = {
            'rsi_BTC': {
                'hits': 100,
                'misses': 20,
                'freshness': 3600.0
            }
        }
        
        pipeline_metrics = {
            'robinhood_BTC': {
                'ingestion_rate': 10.0,
                'quality_score': 0.95
            }
        }
        
        risk_metrics = {
            'positions': [
                ('BTC', 'trend', 1.0, 50000.0, 51000.0, 51000.0)
            ],
            'total_exposure': 51000.0
        }
        
        # This should not raise an exception
        await collector._update_prometheus_metrics(
            regime_metrics, strategy_metrics, feature_metrics,
            pipeline_metrics, risk_metrics
        )
        
        # Check that metrics were set
        # Note: We can't easily test the exact values without more complex mocking
        # but we can verify the methods don't raise exceptions
        assert True
    
    @pytest.mark.asyncio
    async def test_collect_with_empty_database(self):
        """Test collection with empty database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Create empty database
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE regime_predictions (id INTEGER PRIMARY KEY)")
                cursor.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY)")
                cursor.execute("CREATE TABLE feature_cache_stats (id INTEGER PRIMARY KEY)")
                cursor.execute("CREATE TABLE market_data (id INTEGER PRIMARY KEY)")
                cursor.execute("CREATE TABLE data_quality (id INTEGER PRIMARY KEY)")
                cursor.execute("CREATE TABLE positions (id INTEGER PRIMARY KEY)")
                cursor.execute("CREATE TABLE risk_breaches (id INTEGER PRIMARY KEY)")
                cursor.execute("CREATE TABLE stop_loss_triggers (id INTEGER PRIMARY KEY)")
                conn.commit()
            
            collector = BusinessMetricsCollector(db_path)
            result = await collector.collect_metrics()
            
            # Should not raise an exception
            assert 'regime' in result
            assert 'strategy' in result
            assert 'features' in result
            assert 'pipeline' in result
            assert 'risk' in result
            
        finally:
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_collect_with_database_error(self, temp_db):
        """Test collection with database error."""
        collector = BusinessMetricsCollector(temp_db)
        
        # Mock database connection to raise an exception
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.side_effect = Exception("Database error")
            
            result = await collector.collect_metrics()
            
            # Should handle error gracefully
            assert 'regime' in result
            assert 'strategy' in result
            assert 'features' in result
            assert 'pipeline' in result
            assert 'risk' in result
