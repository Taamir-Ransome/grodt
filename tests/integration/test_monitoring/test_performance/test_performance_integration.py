"""
Integration tests for performance monitoring system.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from grodtd.monitoring.performance_monitor import PerformanceMonitor
from grodtd.monitoring.performance_analyzer import PerformanceAnalyzer
from grodtd.monitoring.performance_api import init_performance_api


class TestPerformanceIntegration:
    """Integration tests for performance monitoring system."""
    
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
    def analyzer_config(self):
        """Provide test configuration for performance analyzer."""
        return {
            'cpu_critical_threshold': 95.0,
            'cpu_high_threshold': 85.0,
            'cpu_medium_threshold': 75.0,
            'memory_critical_threshold': 95.0,
            'memory_high_threshold': 85.0,
            'memory_medium_threshold': 75.0,
            'response_time_critical_threshold': 5000.0,
            'response_time_high_threshold': 2000.0,
            'response_time_medium_threshold': 1000.0,
            'query_time_critical_threshold': 1000.0,
            'query_time_high_threshold': 500.0,
            'query_time_medium_threshold': 200.0,
            'trend_window_hours': 24,
            'min_samples_for_trend': 10
        }
    
    @pytest.fixture
    def performance_monitor(self, monitor_config):
        """Provide PerformanceMonitor instance for testing."""
        return PerformanceMonitor(monitor_config)
    
    @pytest.fixture
    def performance_analyzer(self, analyzer_config):
        """Provide PerformanceAnalyzer instance for testing."""
        return PerformanceAnalyzer(analyzer_config)
    
    @pytest.mark.asyncio
    async def test_monitor_analyzer_integration(self, performance_monitor, performance_analyzer):
        """Test integration between monitor and analyzer."""
        # Collect metrics using monitor
        with patch('psutil.cpu_percent', return_value=85.0), \
             patch('psutil.virtual_memory', return_value=Mock(percent=90.0, used=1024*1024*1024, available=512*1024*1024)), \
             patch('psutil.disk_usage', return_value=Mock(used=50*1024*1024*1024, total=100*1024*1024*1024, free=50*1024*1024*1024)), \
             patch('psutil.net_io_counters', return_value=Mock(bytes_sent=1024*1024, bytes_recv=2*1024*1024)):
            
            metrics = await performance_monitor.collect_all_metrics()
            
            # Analyze bottlenecks using analyzer
            bottlenecks = performance_analyzer.identify_bottlenecks(metrics)
            
            # Should identify high CPU and memory usage
            assert len(bottlenecks) >= 1
            cpu_bottlenecks = [b for b in bottlenecks if b.component == 'CPU']
            memory_bottlenecks = [b for b in bottlenecks if b.component == 'Memory']
            
            assert len(cpu_bottlenecks) >= 1
            assert len(memory_bottlenecks) >= 1
    
    @pytest.mark.asyncio
    async def test_performance_trend_analysis_integration(self, performance_monitor, performance_analyzer):
        """Test integration of trend analysis with historical data."""
        # Generate historical data with clear trends
        historical_data = []
        for i in range(20):
            with patch('psutil.cpu_percent', return_value=50.0 + i * 2.0), \
                 patch('psutil.virtual_memory', return_value=Mock(percent=60.0 + i, used=1024*1024*1024, available=512*1024*1024)), \
                 patch('psutil.disk_usage', return_value=Mock(used=50*1024*1024*1024, total=100*1024*1024*1024, free=50*1024*1024*1024)), \
                 patch('psutil.net_io_counters', return_value=Mock(bytes_sent=1024*1024, bytes_recv=2*1024*1024)):
                
                metrics = await performance_monitor.collect_all_metrics()
                historical_data.append(metrics)
        
        # Analyze trends
        trends = performance_analyzer.analyze_performance_trends(historical_data)
        
        # Should identify degrading trends for CPU and memory
        assert len(trends) >= 1
        cpu_trends = [t for t in trends if 'cpu_percent' in t.metric]
        memory_trends = [t for t in trends if 'memory_percent' in t.metric]
        
        assert len(cpu_trends) >= 1
        assert len(memory_trends) >= 1
        
        # Check trend directions
        for trend in trends:
            assert trend.trend_direction in ['improving', 'degrading', 'stable']
            assert 0.0 <= trend.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_baseline_establishment_integration(self, performance_monitor, performance_analyzer):
        """Test integration of baseline establishment with historical data."""
        # Generate historical data for baseline
        historical_data = []
        for i in range(20):
            with patch('psutil.cpu_percent', return_value=50.0 + (i % 10) * 2.0), \
                 patch('psutil.virtual_memory', return_value=Mock(percent=60.0 + (i % 5), used=1024*1024*1024, available=512*1024*1024)), \
                 patch('psutil.disk_usage', return_value=Mock(used=50*1024*1024*1024, total=100*1024*1024*1024, free=50*1024*1024*1024)), \
                 patch('psutil.net_io_counters', return_value=Mock(bytes_sent=1024*1024, bytes_recv=2*1024*1024)):
                
                metrics = await performance_monitor.collect_all_metrics()
                historical_data.append(metrics)
        
        # Establish baselines
        baselines = performance_analyzer.establish_baseline(historical_data)
        
        # Should have established baselines
        assert len(baselines) >= 1
        
        # Check baseline properties
        for baseline in baselines:
            assert baseline.baseline_value > 0
            assert baseline.standard_deviation >= 0
            assert baseline.percentile_95 > baseline.baseline_value
            assert baseline.percentile_99 > baseline.percentile_95
            assert baseline.sample_size == 20
    
    @pytest.mark.asyncio
    async def test_regression_detection_integration(self, performance_monitor, performance_analyzer):
        """Test integration of regression detection with baselines."""
        # Generate historical data for baseline
        historical_data = []
        for i in range(20):
            with patch('psutil.cpu_percent', return_value=50.0 + (i % 10) * 2.0), \
                 patch('psutil.virtual_memory', return_value=Mock(percent=60.0 + (i % 5), used=1024*1024*1024, available=512*1024*1024)), \
                 patch('psutil.disk_usage', return_value=Mock(used=50*1024*1024*1024, total=100*1024*1024*1024, free=50*1024*1024*1024)), \
                 patch('psutil.net_io_counters', return_value=Mock(bytes_sent=1024*1024, bytes_recv=2*1024*1024)):
                
                metrics = await performance_monitor.collect_all_metrics()
                historical_data.append(metrics)
        
        # Establish baselines
        baselines = performance_analyzer.establish_baseline(historical_data)
        
        # Generate current metrics that exceed baselines
        with patch('psutil.cpu_percent', return_value=95.0), \
             patch('psutil.virtual_memory', return_value=Mock(percent=95.0, used=1024*1024*1024, available=512*1024*1024)), \
             patch('psutil.disk_usage', return_value=Mock(used=50*1024*1024*1024, total=100*1024*1024*1024, free=50*1024*1024*1024)), \
             patch('psutil.net_io_counters', return_value=Mock(bytes_sent=1024*1024, bytes_recv=2*1024*1024)):
            
            current_metrics = await performance_monitor.collect_all_metrics()
            
            # Detect regressions
            regressions = performance_analyzer.detect_performance_regression(current_metrics, baselines)
            
            # Should detect regressions for high CPU and memory usage
            assert len(regressions) >= 1
            assert any('system.cpu_percent' in r for r in regressions)
            assert any('system.memory_percent' in r for r in regressions)
    
    @pytest.mark.asyncio
    async def test_performance_overhead_measurement(self, performance_monitor):
        """Test that performance monitoring has minimal overhead."""
        import time
        
        # Measure time without monitoring
        start_time = time.time()
        for _ in range(100):
            pass  # Simulate some work
        baseline_time = time.time() - start_time
        
        # Measure time with monitoring
        start_time = time.time()
        for _ in range(100):
            performance_monitor.track_request(1.0, False)
        monitoring_time = time.time() - start_time
        
        # Overhead should be minimal
        overhead = monitoring_time - baseline_time
        assert overhead < 0.1  # Less than 100ms overhead for 100 requests
    
    @pytest.mark.asyncio
    async def test_metrics_history_management(self, performance_monitor):
        """Test that metrics history is properly managed."""
        # Add more metrics than max_history_size
        for i in range(150):
            with patch('psutil.cpu_percent', return_value=50.0), \
                 patch('psutil.virtual_memory', return_value=Mock(percent=60.0, used=1024*1024*1024, available=512*1024*1024)), \
                 patch('psutil.disk_usage', return_value=Mock(used=50*1024*1024*1024, total=100*1024*1024*1024, free=50*1024*1024*1024)), \
                 patch('psutil.net_io_counters', return_value=Mock(bytes_sent=1024*1024, bytes_recv=2*1024*1024)):
                
                await performance_monitor.collect_all_metrics()
        
        # History should be limited to max_history_size
        assert len(performance_monitor.metrics_history) == 100
        
        # Most recent metrics should be preserved
        assert performance_monitor.metrics_history[-1] is not None
    
    @pytest.mark.asyncio
    async def test_prometheus_metrics_integration(self, performance_monitor):
        """Test integration with Prometheus metrics."""
        # Track some requests
        performance_monitor.track_request(100.0, False)
        performance_monitor.track_request(200.0, True)
        performance_monitor.track_database_query(50.0)
        performance_monitor.track_order_processing(300.0)
        
        # Get Prometheus registry
        registry = performance_monitor.get_prometheus_registry()
        assert registry is not None
        
        # Collect metrics
        metrics = list(registry.collect())
        assert len(metrics) > 0
        
        # Check that our custom metrics are present
        metric_names = [m.name for m in metrics]
        assert 'application_response_time_seconds' in metric_names
        assert 'application_requests_total' in metric_names
        assert 'application_errors_total' in metric_names
        assert 'database_query_time_seconds' in metric_names
        assert 'trading_order_processing_seconds' in metric_names
    
    @pytest.mark.asyncio
    async def test_threshold_violation_detection(self, performance_monitor):
        """Test detection of threshold violations."""
        # Test metrics that exceed thresholds
        high_metrics = {
            'system': {
                'cpu_percent': 85.0,  # Exceeds 80% threshold
                'memory_percent': 90.0,  # Exceeds 85% threshold
                'disk_usage_percent': 95.0  # Exceeds 90% threshold
            }
        }
        
        violations = performance_monitor.check_performance_thresholds(high_metrics)
        
        # Should detect all three violations
        assert len(violations) == 3
        assert any('CPU usage' in v for v in violations)
        assert any('Memory usage' in v for v in violations)
        assert any('Disk usage' in v for v in violations)
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, performance_monitor, performance_analyzer):
        """Test error handling in integrated system."""
        # Test with invalid metrics data
        invalid_metrics = {
            'system': {
                'cpu_percent': 'invalid',  # Invalid type
                'memory_percent': None,    # None value
                'disk_usage_percent': -1   # Negative value
            }
        }
        
        # Should handle errors gracefully
        bottlenecks = performance_analyzer.identify_bottlenecks(invalid_metrics)
        assert isinstance(bottlenecks, list)  # Should return empty list, not crash
        
        # Test with empty metrics
        empty_metrics = {}
        bottlenecks = performance_analyzer.identify_bottlenecks(empty_metrics)
        assert isinstance(bottlenecks, list)  # Should return empty list, not crash
    
    @pytest.mark.asyncio
    async def test_concurrent_metrics_collection(self, performance_monitor):
        """Test concurrent metrics collection."""
        async def collect_metrics():
            with patch('psutil.cpu_percent', return_value=50.0), \
                 patch('psutil.virtual_memory', return_value=Mock(percent=60.0, used=1024*1024*1024, available=512*1024*1024)), \
                 patch('psutil.disk_usage', return_value=Mock(used=50*1024*1024*1024, total=100*1024*1024*1024, free=50*1024*1024*1024)), \
                 patch('psutil.net_io_counters', return_value=Mock(bytes_sent=1024*1024, bytes_recv=2*1024*1024)):
                
                return await performance_monitor.collect_all_metrics()
        
        # Run multiple concurrent collections
        tasks = [collect_metrics() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All collections should succeed
        assert len(results) == 10
        for result in results:
            assert 'system' in result
            assert 'application' in result
            assert 'database' in result
            assert 'trading' in result
