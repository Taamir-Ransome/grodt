"""
Unit tests for metrics endpoint.
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
from unittest.mock import Mock, patch
from flask import Flask
from prometheus_client import CollectorRegistry

from grodtd.monitoring.metrics_endpoint import MetricsEndpoint, create_metrics_endpoint


class TestMetricsEndpoint:
    """Test cases for MetricsEndpoint."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Create test database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY)")
            conn.commit()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
    
    def test_initialization(self, temp_db):
        """Test metrics endpoint initialization."""
        endpoint = MetricsEndpoint(temp_db)
        
        assert endpoint.db_path == temp_db
        assert endpoint.registry is not None
        assert endpoint._collection_interval == 1.0
        assert not endpoint._is_collecting
        
        # Check that collectors were initialized
        assert endpoint.trading_collector is not None
        assert endpoint.system_collector is not None
        assert endpoint.business_collector is not None
    
    @pytest.mark.asyncio
    async def test_collect_all_metrics(self, temp_db):
        """Test collecting metrics from all collectors."""
        endpoint = MetricsEndpoint(temp_db)
        
        # Mock the collectors to return test data
        endpoint.trading_collector.collect = Mock(return_value={'trading': 'data'})
        endpoint.system_collector.collect = Mock(return_value={'system': 'data'})
        endpoint.business_collector.collect = Mock(return_value={'business': 'data'})
        
        result = await endpoint.collect_all_metrics()
        
        assert 'trading' in result
        assert 'system' in result
        assert 'business' in result
        assert 'timestamp' in result
        
        assert result['trading'] == {'trading': 'data'}
        assert result['system'] == {'system': 'data'}
        assert result['business'] == {'business': 'data'}
    
    @pytest.mark.asyncio
    async def test_collect_all_metrics_with_error(self, temp_db):
        """Test collecting metrics when one collector fails."""
        endpoint = MetricsEndpoint(temp_db)
        
        # Mock collectors - one succeeds, one fails
        endpoint.trading_collector.collect = Mock(return_value={'trading': 'data'})
        endpoint.system_collector.collect = Mock(side_effect=Exception("System error"))
        endpoint.business_collector.collect = Mock(return_value={'business': 'data'})
        
        result = await endpoint.collect_all_metrics()
        
        # Should handle errors gracefully
        assert 'trading' in result
        assert 'system' in result
        assert 'business' in result
        assert 'timestamp' in result
        
        assert result['trading'] == {'trading': 'data'}
        assert result['system'] == {}  # Empty due to error
        assert result['business'] == {'business': 'data'}
    
    def test_get_metrics_response(self, temp_db):
        """Test getting Prometheus metrics response."""
        endpoint = MetricsEndpoint(temp_db)
        
        response = endpoint.get_metrics_response()
        
        assert response is not None
        assert response.mimetype == 'text/plain; version=0.0.4; charset=utf-8'
        assert 'Cache-Control' in response.headers
        assert 'Pragma' in response.headers
        assert 'Expires' in response.headers
    
    def test_get_metrics_response_with_error(self, temp_db):
        """Test getting metrics response when generation fails."""
        endpoint = MetricsEndpoint(temp_db)
        
        # Mock generate_latest to raise an exception
        with patch('grodtd.monitoring.metrics_endpoint.generate_latest') as mock_generate:
            mock_generate.side_effect = Exception("Generation error")
            
            response = endpoint.get_metrics_response()
            
            assert response.status_code == 500
            assert "Error generating metrics" in response.get_data(as_text=True)
    
    @pytest.mark.asyncio
    async def test_start_continuous_collection(self, temp_db):
        """Test starting continuous collection."""
        endpoint = MetricsEndpoint(temp_db)
        
        # Mock collect_all_metrics to avoid actual collection
        endpoint.collect_all_metrics = Mock()
        
        # Start collection with a short interval
        endpoint.set_collection_interval(0.1)
        
        # Start collection task
        collection_task = asyncio.create_task(endpoint.start_continuous_collection())
        
        # Let it run for a short time
        await asyncio.sleep(0.2)
        
        # Stop collection
        endpoint.stop_continuous_collection()
        
        # Wait for task to complete
        await collection_task
        
        # Check that collection was called
        assert endpoint.collect_all_metrics.call_count > 0
    
    def test_stop_continuous_collection(self, temp_db):
        """Test stopping continuous collection."""
        endpoint = MetricsEndpoint(temp_db)
        
        # Start collection
        endpoint._is_collecting = True
        
        # Stop collection
        endpoint.stop_continuous_collection()
        
        assert not endpoint._is_collecting
    
    def test_get_collection_status(self, temp_db):
        """Test getting collection status."""
        endpoint = MetricsEndpoint(temp_db)
        
        status = endpoint.get_collection_status()
        
        assert 'is_collecting' in status
        assert 'collection_interval' in status
        assert 'last_collection_time' in status
        assert 'collectors' in status
        
        assert status['is_collecting'] == False
        assert status['collection_interval'] == 1.0
        assert 'trading' in status['collectors']
        assert 'system' in status['collectors']
        assert 'business' in status['collectors']
    
    def test_set_collection_interval(self, temp_db):
        """Test setting collection interval."""
        endpoint = MetricsEndpoint(temp_db)
        
        # Set valid interval
        endpoint.set_collection_interval(2.0)
        assert endpoint._collection_interval == 2.0
        
        # Test invalid interval
        with pytest.raises(ValueError, match="Collection interval must be positive"):
            endpoint.set_collection_interval(-1.0)
        
        with pytest.raises(ValueError, match="Collection interval must be positive"):
            endpoint.set_collection_interval(0.0)
    
    def test_get_registry(self, temp_db):
        """Test getting the Prometheus registry."""
        endpoint = MetricsEndpoint(temp_db)
        
        registry = endpoint.get_registry()
        
        assert registry is not None
        assert registry is endpoint.registry
    
    def test_add_custom_metric(self, temp_db):
        """Test adding a custom metric."""
        endpoint = MetricsEndpoint(temp_db)
        
        # Create a mock metric
        mock_metric = Mock()
        mock_metric._name = 'test_metric'
        
        # Add the metric
        endpoint.add_custom_metric(mock_metric)
        
        # This should not raise an exception
        assert True
    
    def test_remove_custom_metric(self, temp_db):
        """Test removing a custom metric."""
        endpoint = MetricsEndpoint(temp_db)
        
        # Create a mock metric
        mock_metric = Mock()
        mock_metric._name = 'test_metric'
        
        # Remove the metric
        endpoint.remove_custom_metric(mock_metric)
        
        # This should not raise an exception
        assert True


class TestCreateMetricsEndpoint:
    """Test cases for create_metrics_endpoint function."""
    
    def test_create_metrics_endpoint(self):
        """Test creating a metrics endpoint."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Create empty database
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY)")
                conn.commit()
            
            endpoint = create_metrics_endpoint(db_path)
            
            assert isinstance(endpoint, MetricsEndpoint)
            assert endpoint.db_path == db_path
            
        finally:
            os.unlink(db_path)
