"""
Integration tests for monitoring system.
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
import time
from unittest.mock import Mock, patch
from flask import Flask
from prometheus_client import generate_latest

from grodtd.monitoring.metrics_endpoint import create_metrics_endpoint
from grodtd.monitoring.trading_metrics import TradingMetricsCollector
from grodtd.monitoring.system_metrics import SystemMetricsCollector
from grodtd.monitoring.business_metrics import BusinessMetricsCollector


class TestMonitoringIntegration:
    """Integration tests for the monitoring system."""
    
    @pytest.fixture
    def temp_db_with_data(self):
        """Create a temporary database with test data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Create test database with comprehensive data
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Create all required tables
            cursor.execute("""
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    quantity REAL,
                    price REAL,
                    pnl REAL,
                    fill_timestamp TEXT,
                    strategy TEXT,
                    regime TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE positions (
                    symbol TEXT PRIMARY KEY,
                    quantity REAL,
                    average_entry_price REAL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE equity_curve (
                    timestamp TEXT,
                    portfolio_value REAL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE regime_predictions (
                    symbol TEXT,
                    predicted_regime TEXT,
                    actual_regime TEXT,
                    confidence REAL,
                    timestamp TEXT
                )
            """)
            
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
            
            cursor.execute("""
                CREATE TABLE market_data (
                    data_source TEXT,
                    symbol TEXT,
                    timestamp TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE data_quality (
                    data_source TEXT,
                    symbol TEXT,
                    quality_score REAL,
                    timestamp TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE risk_breaches (
                    limit_type TEXT,
                    symbol TEXT,
                    timestamp TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE stop_loss_triggers (
                    symbol TEXT,
                    strategy TEXT,
                    timestamp TEXT
                )
            """)
            
            # Insert comprehensive test data
            cursor.execute("""
                INSERT INTO trades (symbol, side, quantity, price, pnl, fill_timestamp, strategy, regime)
                VALUES 
                    ('BTC', 'buy', 1.0, 50000.0, 100.0, '2024-01-01T10:00:00Z', 'trend', 'trending'),
                    ('BTC', 'sell', 1.0, 51000.0, 100.0, '2024-01-01T11:00:00Z', 'trend', 'trending'),
                    ('ETH', 'buy', 10.0, 3000.0, -50.0, '2024-01-01T12:00:00Z', 'trend', 'ranging'),
                    ('BTC', 'buy', 0.5, 52000.0, 200.0, '2024-01-01T13:00:00Z', 'trend', 'trending'),
                    ('ETH', 'sell', 5.0, 3100.0, 50.0, '2024-01-01T14:00:00Z', 'trend', 'ranging')
            """)
            
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, average_entry_price)
                VALUES 
                    ('BTC', 0.5, 52000.0),
                    ('ETH', 5.0, 3000.0)
            """)
            
            cursor.execute("""
                INSERT INTO equity_curve (timestamp, portfolio_value)
                VALUES 
                    ('2024-01-01T09:00:00Z', 10000.0),
                    ('2024-01-01T10:00:00Z', 10100.0),
                    ('2024-01-01T11:00:00Z', 10200.0),
                    ('2024-01-01T12:00:00Z', 10150.0),
                    ('2024-01-01T13:00:00Z', 10350.0),
                    ('2024-01-01T14:00:00Z', 10400.0)
            """)
            
            cursor.execute("""
                INSERT INTO regime_predictions (symbol, predicted_regime, actual_regime, confidence, timestamp)
                VALUES 
                    ('BTC', 'trending', 'trending', 0.85, '2024-01-01T10:00:00Z'),
                    ('BTC', 'ranging', 'trending', 0.70, '2024-01-01T11:00:00Z'),
                    ('ETH', 'trending', 'trending', 0.90, '2024-01-01T12:00:00Z'),
                    ('BTC', 'trending', 'trending', 0.88, '2024-01-01T13:00:00Z'),
                    ('ETH', 'ranging', 'ranging', 0.75, '2024-01-01T14:00:00Z')
            """)
            
            cursor.execute("""
                INSERT INTO feature_cache_stats (feature_type, symbol, cache_hits, cache_misses, computation_time, last_updated)
                VALUES 
                    ('rsi', 'BTC', 100, 20, 0.01, '2024-01-01T10:00:00Z'),
                    ('macd', 'BTC', 80, 10, 0.02, '2024-01-01T10:00:00Z'),
                    ('rsi', 'ETH', 60, 15, 0.015, '2024-01-01T10:00:00Z')
            """)
            
            cursor.execute("""
                INSERT INTO market_data (data_source, symbol, timestamp)
                VALUES 
                    ('robinhood', 'BTC', '2024-01-01T10:00:00Z'),
                    ('robinhood', 'BTC', '2024-01-01T10:01:00Z'),
                    ('robinhood', 'ETH', '2024-01-01T10:00:00Z'),
                    ('robinhood', 'ETH', '2024-01-01T10:01:00Z')
            """)
            
            cursor.execute("""
                INSERT INTO data_quality (data_source, symbol, quality_score, timestamp)
                VALUES 
                    ('robinhood', 'BTC', 0.95, '2024-01-01T10:00:00Z'),
                    ('robinhood', 'ETH', 0.90, '2024-01-01T10:00:00Z')
            """)
            
            conn.commit()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_full_metrics_collection(self, temp_db_with_data):
        """Test full metrics collection from all collectors."""
        endpoint = create_metrics_endpoint(temp_db_with_data)
        
        # Collect metrics from all collectors
        result = await endpoint.collect_all_metrics()
        
        # Verify all collectors returned data
        assert 'trading' in result
        assert 'system' in result
        assert 'business' in result
        assert 'timestamp' in result
        
        # Verify trading metrics
        trading = result['trading']
        assert 'portfolio' in trading
        assert 'trade_statistics' in trading
        assert 'performance' in trading
        
        # Verify system metrics
        system = result['system']
        assert 'cpu' in system or 'memory' in system or 'disk' in system
        
        # Verify business metrics
        business = result['business']
        assert 'regime' in business
        assert 'strategy' in business
        assert 'features' in business
        assert 'pipeline' in business
        assert 'risk' in business
    
    @pytest.mark.asyncio
    async def test_metrics_collection_performance(self, temp_db_with_data):
        """Test that metrics collection completes within reasonable time."""
        endpoint = create_metrics_endpoint(temp_db_with_data)
        
        start_time = time.time()
        result = await endpoint.collect_all_metrics()
        end_time = time.time()
        
        # Should complete within 5 seconds
        assert (end_time - start_time) < 5.0
        
        # Should return valid data
        assert 'trading' in result
        assert 'system' in result
        assert 'business' in result
    
    def test_prometheus_metrics_generation(self, temp_db_with_data):
        """Test that Prometheus metrics can be generated."""
        endpoint = create_metrics_endpoint(temp_db_with_data)
        
        # Get metrics response
        response = endpoint.get_metrics_response()
        
        # Should be successful
        assert response.status_code == 200
        assert response.mimetype == 'text/plain; version=0.0.4; charset=utf-8'
        
        # Should contain metrics data
        metrics_data = response.get_data(as_text=True)
        assert len(metrics_data) > 0
        
        # Should contain some expected metric names
        assert 'trading_pnl_total' in metrics_data or 'system_memory_usage_bytes' in metrics_data
    
    @pytest.mark.asyncio
    async def test_continuous_collection(self, temp_db_with_data):
        """Test continuous metrics collection."""
        endpoint = create_metrics_endpoint(temp_db_with_data)
        
        # Set short collection interval for testing
        endpoint.set_collection_interval(0.1)
        
        # Start continuous collection
        collection_task = asyncio.create_task(endpoint.start_continuous_collection())
        
        # Let it run for a short time
        await asyncio.sleep(0.3)
        
        # Stop collection
        endpoint.stop_continuous_collection()
        
        # Wait for task to complete
        await collection_task
        
        # Check that collection was running
        assert not endpoint._is_collecting
    
    def test_collection_status(self, temp_db_with_data):
        """Test collection status reporting."""
        endpoint = create_metrics_endpoint(temp_db_with_data)
        
        status = endpoint.get_collection_status()
        
        assert 'is_collecting' in status
        assert 'collection_interval' in status
        assert 'last_collection_time' in status
        assert 'collectors' in status
        
        # Check collector status
        collectors = status['collectors']
        assert 'trading' in collectors
        assert 'system' in collectors
        assert 'business' in collectors
        
        # Each collector should have summary information
        for collector_name, collector_status in collectors.items():
            assert 'collector_type' in collector_status
            assert 'uptime_seconds' in collector_status
            assert 'collection_count' in collector_status
    
    @pytest.mark.asyncio
    async def test_individual_collectors(self, temp_db_with_data):
        """Test individual collectors work correctly."""
        # Test trading metrics collector
        trading_collector = TradingMetricsCollector(temp_db_with_data)
        trading_result = await trading_collector.collect()
        
        assert 'portfolio' in trading_result
        assert 'trade_statistics' in trading_result
        assert 'performance' in trading_result
        
        # Test system metrics collector
        system_collector = SystemMetricsCollector(temp_db_with_data)
        system_result = await system_collector.collect()
        
        assert 'system' in system_result
        assert 'process' in system_result
        assert 'database' in system_result
        
        # Test business metrics collector
        business_collector = BusinessMetricsCollector(temp_db_with_data)
        business_result = await business_collector.collect()
        
        assert 'regime' in business_result
        assert 'strategy' in business_result
        assert 'features' in business_result
        assert 'pipeline' in business_result
        assert 'risk' in business_result
    
    @pytest.mark.asyncio
    async def test_error_handling(self, temp_db_with_data):
        """Test error handling in metrics collection."""
        endpoint = create_metrics_endpoint(temp_db_with_data)
        
        # Mock one collector to raise an exception
        endpoint.trading_collector.collect = Mock(side_effect=Exception("Trading error"))
        
        # Collection should still work for other collectors
        result = await endpoint.collect_all_metrics()
        
        assert 'trading' in result
        assert 'system' in result
        assert 'business' in result
        
        # Trading should be empty due to error
        assert result['trading'] == {}
        
        # System and business should still have data
        assert result['system'] != {}
        assert result['business'] != {}
    
    def test_metrics_registry_integration(self, temp_db_with_data):
        """Test that all metrics are properly registered."""
        endpoint = create_metrics_endpoint(temp_db_with_data)
        
        registry = endpoint.get_registry()
        
        # Get all registered metrics
        metrics = list(registry.collect())
        
        # Should have metrics from all collectors
        metric_names = [metric.name for metric in metrics]
        
        # Check for some expected metric names
        expected_metrics = [
            'metrics_collection_duration_seconds',
            'metrics_collection_errors_total',
            'trading_pnl_total',
            'system_memory_usage_bytes',
            'regime_predictions_total'
        ]
        
        # At least some of these should be present
        found_metrics = [name for name in expected_metrics if name in metric_names]
        assert len(found_metrics) > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_collection(self, temp_db_with_data):
        """Test concurrent metrics collection."""
        endpoint = create_metrics_endpoint(temp_db_with_data)
        
        # Start multiple collection tasks concurrently
        tasks = [
            endpoint.collect_all_metrics()
            for _ in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All collections should succeed
        assert len(results) == 5
        
        for result in results:
            assert 'trading' in result
            assert 'system' in result
            assert 'business' in result
