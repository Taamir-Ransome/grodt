"""
Unit tests for the base metrics collector.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from prometheus_client import CollectorRegistry

from grodtd.monitoring.metrics_collector import MetricsCollector


class MockMetricsCollector(MetricsCollector):
    """Test implementation of MetricsCollector."""
    
    def _initialize_metrics(self) -> None:
        """Initialize test metrics."""
        self.test_counter = self.create_counter(
            'test_counter_total',
            'Test counter metric',
            ['test_label']
        )
        
        self.test_gauge = self.create_gauge(
            'test_gauge',
            'Test gauge metric',
            ['test_label']
        )
    
    async def collect_metrics(self) -> dict:
        """Collect test metrics."""
        return {'test': 'data'}


class TestMetricsCollectorBase:
    """Test cases for the base MetricsCollector class."""
    
    def test_initialization(self):
        """Test metrics collector initialization."""
        collector = MockMetricsCollector()
        
        assert collector.registry is not None
        assert collector._collection_count == 0
        assert collector._last_collection_time == 0.0
    
    def test_initialization_with_custom_registry(self):
        """Test initialization with custom registry."""
        custom_registry = CollectorRegistry()
        collector = MockMetricsCollector(registry=custom_registry)
        
        assert collector.registry is custom_registry
    
    def test_create_common_labels(self):
        """Test common labels creation."""
        collector = MockMetricsCollector()
        
        # Test with no additional labels
        labels = collector.create_common_labels()
        assert labels['system'] == 'grodt'
        assert labels['version'] == '0.1.0'
        
        # Test with additional labels
        labels = collector.create_common_labels(
            strategy='test_strategy',
            symbol='BTC',
            regime='trending'
        )
        assert labels['system'] == 'grodt'
        assert labels['strategy'] == 'test_strategy'
        assert labels['symbol'] == 'BTC'
        assert labels['regime'] == 'trending'
    
    def test_create_counter(self):
        """Test counter metric creation."""
        # Use a fresh registry to avoid conflicts
        custom_registry = CollectorRegistry()
        collector = MockMetricsCollector(registry=custom_registry)
        
        counter = collector.create_counter(
            'test_counter_unique',
            'Test counter',
            ['label1', 'label2'],
            strategy='test'
        )
        
        assert counter is not None
        assert counter._name == 'test_counter_unique'
        assert counter._documentation == 'Test counter'
    
    def test_create_histogram(self):
        """Test histogram metric creation."""
        # Use a fresh registry to avoid conflicts
        custom_registry = CollectorRegistry()
        collector = MockMetricsCollector(registry=custom_registry)
        
        histogram = collector.create_histogram(
            'test_histogram_unique',
            'Test histogram',
            buckets=[0.1, 0.5, 1.0],
            labelnames=['label1'],
            strategy='test'
        )
        
        assert histogram is not None
        assert histogram._name == 'test_histogram_unique'
        assert histogram._documentation == 'Test histogram'
    
    def test_create_gauge(self):
        """Test gauge metric creation."""
        # Use a fresh registry to avoid conflicts
        custom_registry = CollectorRegistry()
        collector = MockMetricsCollector(registry=custom_registry)
        
        gauge = collector.create_gauge(
            'test_gauge_unique',
            'Test gauge',
            ['label1'],
            strategy='test'
        )
        
        assert gauge is not None
        assert gauge._name == 'test_gauge_unique'
        assert gauge._documentation == 'Test gauge'
    
    def test_create_summary(self):
        """Test summary metric creation."""
        # Use a fresh registry to avoid conflicts
        custom_registry = CollectorRegistry()
        collector = MockMetricsCollector(registry=custom_registry)
        
        summary = collector.create_summary(
            'test_summary_unique',
            'Test summary',
            ['label1'],
            strategy='test'
        )
        
        assert summary is not None
        assert summary._name == 'test_summary_unique'
        assert summary._documentation == 'Test summary'
    
    @pytest.mark.asyncio
    async def test_collect_success(self):
        """Test successful metrics collection."""
        collector = MockMetricsCollector()
        
        result = await collector.collect()
        
        assert result == {'test': 'data'}
        assert collector._collection_count == 1
        assert collector._last_collection_time > 0
    
    @pytest.mark.asyncio
    async def test_collect_with_error(self):
        """Test metrics collection with error."""
        collector = MockMetricsCollector()
        
        # Mock collect_metrics to raise an exception
        async def failing_collect():
            raise Exception("Test error")
        
        collector.collect_metrics = failing_collect
        
        with pytest.raises(Exception, match="Test error"):
            await collector.collect()
        
        # Check that error was tracked - use the correct way to access Counter value
        error_metric = collector._collection_errors
        # Get the value from the metric's samples
        samples = list(error_metric.collect()[0].samples)
        error_count = sum(sample.value for sample in samples)
        assert error_count > 0
    
    def test_get_metrics_summary(self):
        """Test metrics summary generation."""
        collector = MockMetricsCollector()
        
        summary = collector.get_metrics_summary()
        
        assert 'collector_type' in summary
        assert 'uptime_seconds' in summary
        assert 'collection_count' in summary
        assert 'last_collection_time' in summary
        assert 'average_frequency_per_second' in summary
        
        assert summary['collector_type'] == 'MockMetricsCollector'
        assert summary['collection_count'] == 0
    
    def test_get_registry(self):
        """Test registry retrieval."""
        collector = MockMetricsCollector()
        registry = collector.get_registry()
        
        assert registry is not None
        assert registry is collector.registry
