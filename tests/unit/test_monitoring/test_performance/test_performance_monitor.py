"""
Unit tests for performance monitor.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from grodtd.monitoring.performance_monitor import PerformanceMonitor, SystemMetrics, ApplicationMetrics, DatabaseMetrics, TradingMetrics


class TestPerformanceMonitor:
    """Test suite for PerformanceMonitor class."""
    
    @pytest.fixture
    def monitor_config(self):
        """Provide test configuration for performance monitor."""
        return {
            'max_history_size': 100,
            'cpu_threshold': 80.0,
            'memory_threshold': 85.0,
            'disk_threshold': 90.0,
            'response_time_threshold': 1000.0,
            'query_time_threshold': 100.0
        }
    
    @pytest.fixture
    def performance_monitor(self, monitor_config):
        """Provide PerformanceMonitor instance for testing."""
        return PerformanceMonitor(monitor_config)
    
    def test_initialization(self, performance_monitor, monitor_config):
        """Test performance monitor initialization."""
        assert performance_monitor.config == monitor_config
        assert performance_monitor.max_history_size == 100
        assert performance_monitor.thresholds['cpu_percent'] == 80.0
        assert performance_monitor.thresholds['memory_percent'] == 85.0
        assert performance_monitor.thresholds['disk_percent'] == 90.0
        assert performance_monitor.thresholds['response_time_ms'] == 1000.0
        assert performance_monitor.thresholds['query_time_ms'] == 100.0
        assert performance_monitor.request_count == 0
        assert performance_monitor.error_count == 0
        assert len(performance_monitor.metrics_history) == 0
    
    @pytest.mark.asyncio
    async def test_collect_system_metrics(self, performance_monitor):
        """Test system metrics collection."""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk, \
             patch('psutil.net_io_counters') as mock_network:
            
            # Mock system metrics
            mock_cpu.return_value = 45.5
            mock_memory.return_value = Mock(
                percent=65.2,
                used=1024*1024*1024,  # 1GB
                available=512*1024*1024  # 512MB
            )
            mock_disk.return_value = Mock(
                used=50*1024*1024*1024,  # 50GB
                total=100*1024*1024*1024,  # 100GB
                free=50*1024*1024*1024  # 50GB
            )
            mock_network.return_value = Mock(
                bytes_sent=1024*1024,  # 1MB
                bytes_recv=2*1024*1024  # 2MB
            )
            
            metrics = await performance_monitor.collect_system_metrics()
            
            assert isinstance(metrics, SystemMetrics)
            assert metrics.cpu_percent == 45.5
            assert metrics.memory_percent == 65.2
            assert metrics.memory_used_mb == 1024.0
            assert metrics.memory_available_mb == 512.0
            assert metrics.disk_usage_percent == 50.0
            assert metrics.disk_used_gb == 50.0
            assert metrics.disk_free_gb == 50.0
            assert metrics.network_sent_mb == 1.0
            assert metrics.network_recv_mb == 2.0
    
    @pytest.mark.asyncio
    async def test_collect_application_metrics(self, performance_monitor):
        """Test application metrics collection."""
        # Set up some request history
        performance_monitor.request_count = 100
        performance_monitor.error_count = 5
        performance_monitor.start_time = datetime.now().timestamp() - 60  # 60 seconds ago
        
        metrics = await performance_monitor.collect_application_metrics()
        
        assert isinstance(metrics, ApplicationMetrics)
        assert metrics.throughput_rps > 0  # Should be > 0 since we have requests
        assert metrics.error_rate_percent == 5.0  # 5 errors out of 100 requests
    
    @pytest.mark.asyncio
    async def test_collect_database_metrics(self, performance_monitor):
        """Test database metrics collection."""
        metrics = await performance_monitor.collect_database_metrics()
        
        assert isinstance(metrics, DatabaseMetrics)
        assert metrics.query_time_ms == 0.0  # Placeholder value
        assert metrics.connection_count == 0  # Placeholder value
        assert metrics.cache_hit_ratio == 0.0  # Placeholder value
        assert metrics.slow_queries_count == 0  # Placeholder value
    
    @pytest.mark.asyncio
    async def test_collect_trading_metrics(self, performance_monitor):
        """Test trading metrics collection."""
        metrics = await performance_monitor.collect_trading_metrics()
        
        assert isinstance(metrics, TradingMetrics)
        assert metrics.order_processing_time_ms == 0.0  # Placeholder value
        assert metrics.signal_generation_time_ms == 0.0  # Placeholder value
        assert metrics.strategy_execution_time_ms == 0.0  # Placeholder value
        assert metrics.trade_count == 0  # Placeholder value
    
    @pytest.mark.asyncio
    async def test_collect_all_metrics(self, performance_monitor):
        """Test collection of all metrics."""
        with patch.object(performance_monitor, 'collect_system_metrics') as mock_system, \
             patch.object(performance_monitor, 'collect_application_metrics') as mock_app, \
             patch.object(performance_monitor, 'collect_database_metrics') as mock_db, \
             patch.object(performance_monitor, 'collect_trading_metrics') as mock_trading:
            
            # Mock metrics
            mock_system.return_value = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=50.0,
                memory_percent=60.0,
                memory_used_mb=1000.0,
                memory_available_mb=2000.0,
                disk_usage_percent=70.0,
                disk_used_gb=30.0,
                disk_free_gb=70.0,
                network_sent_mb=10.0,
                network_recv_mb=20.0
            )
            mock_app.return_value = ApplicationMetrics(
                timestamp=datetime.now(),
                response_time_ms=100.0,
                throughput_rps=10.0,
                active_connections=5,
                error_rate_percent=2.0,
                queue_size=0
            )
            mock_db.return_value = DatabaseMetrics(
                timestamp=datetime.now(),
                query_time_ms=50.0,
                connection_count=3,
                cache_hit_ratio=0.95,
                slow_queries_count=1
            )
            mock_trading.return_value = TradingMetrics(
                timestamp=datetime.now(),
                order_processing_time_ms=200.0,
                signal_generation_time_ms=150.0,
                strategy_execution_time_ms=100.0,
                trade_count=5
            )
            
            all_metrics = await performance_monitor.collect_all_metrics()
            
            assert 'timestamp' in all_metrics
            assert 'system' in all_metrics
            assert 'application' in all_metrics
            assert 'database' in all_metrics
            assert 'trading' in all_metrics
            
            # Check that metrics were stored in history
            assert len(performance_monitor.metrics_history) == 1
    
    def test_track_request(self, performance_monitor):
        """Test request tracking functionality."""
        initial_count = performance_monitor.request_count
        initial_errors = performance_monitor.error_count
        
        # Track successful request
        performance_monitor.track_request(150.0, is_error=False)
        
        assert performance_monitor.request_count == initial_count + 1
        assert performance_monitor.error_count == initial_errors
        
        # Track failed request
        performance_monitor.track_request(200.0, is_error=True)
        
        assert performance_monitor.request_count == initial_count + 2
        assert performance_monitor.error_count == initial_errors + 1
    
    def test_track_database_query(self, performance_monitor):
        """Test database query tracking."""
        # This should not raise an exception
        performance_monitor.track_database_query(75.0)
        performance_monitor.track_database_query(150.0)
    
    def test_track_order_processing(self, performance_monitor):
        """Test order processing tracking."""
        # This should not raise an exception
        performance_monitor.track_order_processing(300.0)
        performance_monitor.track_order_processing(500.0)
    
    def test_get_metrics_summary(self, performance_monitor):
        """Test metrics summary generation."""
        # Set up some data
        performance_monitor.request_count = 50
        performance_monitor.error_count = 2
        performance_monitor.start_time = datetime.now().timestamp() - 120  # 2 minutes ago
        
        summary = performance_monitor.get_metrics_summary()
        
        assert 'uptime_seconds' in summary
        assert 'total_requests' in summary
        assert 'total_errors' in summary
        assert 'error_rate_percent' in summary
        assert 'throughput_rps' in summary
        assert 'history_size' in summary
        assert 'thresholds' in summary
        
        assert summary['total_requests'] == 50
        assert summary['total_errors'] == 2
        assert summary['error_rate_percent'] == 4.0  # 2/50 * 100
        assert summary['uptime_seconds'] > 0
    
    def test_check_performance_thresholds(self, performance_monitor):
        """Test performance threshold checking."""
        # Test metrics within thresholds
        normal_metrics = {
            'system': {
                'cpu_percent': 50.0,
                'memory_percent': 60.0,
                'disk_usage_percent': 70.0
            }
        }
        
        violations = performance_monitor.check_performance_thresholds(normal_metrics)
        assert len(violations) == 0
        
        # Test metrics exceeding thresholds
        high_metrics = {
            'system': {
                'cpu_percent': 85.0,  # Exceeds 80% threshold
                'memory_percent': 90.0,  # Exceeds 85% threshold
                'disk_usage_percent': 95.0  # Exceeds 90% threshold
            }
        }
        
        violations = performance_monitor.check_performance_thresholds(high_metrics)
        assert len(violations) == 3
        assert any('CPU usage' in v for v in violations)
        assert any('Memory usage' in v for v in violations)
        assert any('Disk usage' in v for v in violations)
    
    def test_metrics_history_storage(self, performance_monitor):
        """Test metrics history storage and size limit."""
        # Add metrics to history using the proper method
        for i in range(150):  # More than max_history_size (100)
            performance_monitor._store_metrics_history({'test': f'metric_{i}'})
        
        # Should be limited to max_history_size
        assert len(performance_monitor.metrics_history) == 100
        assert performance_monitor.metrics_history[-1]['test'] == 'metric_149'
    
    def test_prometheus_registry(self, performance_monitor):
        """Test Prometheus registry access."""
        registry = performance_monitor.get_prometheus_registry()
        assert registry is not None
        assert hasattr(registry, 'collect')
    
    @pytest.mark.asyncio
    async def test_error_handling_in_metrics_collection(self, performance_monitor):
        """Test error handling during metrics collection."""
        with patch('psutil.cpu_percent', side_effect=Exception("CPU monitoring failed")):
            with pytest.raises(Exception):
                await performance_monitor.collect_system_metrics()
    
    def test_threshold_configuration(self, performance_monitor):
        """Test that thresholds are properly configured."""
        assert performance_monitor.thresholds['cpu_percent'] == 80.0
        assert performance_monitor.thresholds['memory_percent'] == 85.0
        assert performance_monitor.thresholds['disk_percent'] == 90.0
        assert performance_monitor.thresholds['response_time_ms'] == 1000.0
        assert performance_monitor.thresholds['query_time_ms'] == 100.0
