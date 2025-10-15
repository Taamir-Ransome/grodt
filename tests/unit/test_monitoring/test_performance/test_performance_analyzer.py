"""
Unit tests for performance analyzer.
"""

import pytest
from datetime import datetime, timedelta
from grodtd.monitoring.performance_analyzer import PerformanceAnalyzer, Bottleneck, PerformanceTrend, PerformanceBaseline


class TestPerformanceAnalyzer:
    """Test suite for PerformanceAnalyzer class."""
    
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
    def performance_analyzer(self, analyzer_config):
        """Provide PerformanceAnalyzer instance for testing."""
        return PerformanceAnalyzer(analyzer_config)
    
    def test_initialization(self, performance_analyzer, analyzer_config):
        """Test performance analyzer initialization."""
        assert performance_analyzer.config == analyzer_config
        assert performance_analyzer.thresholds['cpu_critical'] == 95.0
        assert performance_analyzer.thresholds['cpu_high'] == 85.0
        assert performance_analyzer.thresholds['cpu_medium'] == 75.0
        assert performance_analyzer.trend_window_hours == 24
        assert performance_analyzer.min_samples_for_trend == 10
    
    def test_identify_bottlenecks_normal_metrics(self, performance_analyzer):
        """Test bottleneck identification with normal metrics."""
        normal_metrics = {
            'system': {
                'cpu_percent': 50.0,
                'memory_percent': 60.0,
                'disk_usage_percent': 70.0
            },
            'application': {
                'response_time_ms': 100.0,
                'error_rate_percent': 1.0
            },
            'database': {
                'query_time_ms': 50.0,
                'connection_count': 5
            },
            'trading': {
                'order_processing_time_ms': 200.0,
                'signal_generation_time_ms': 300.0
            }
        }
        
        bottlenecks = performance_analyzer.identify_bottlenecks(normal_metrics)
        assert len(bottlenecks) == 0
    
    def test_identify_bottlenecks_critical_cpu(self, performance_analyzer):
        """Test bottleneck identification with critical CPU usage."""
        critical_metrics = {
            'system': {
                'cpu_percent': 98.0,  # Critical
                'memory_percent': 60.0,
                'disk_usage_percent': 70.0
            },
            'application': {
                'response_time_ms': 100.0,
                'error_rate_percent': 1.0
            },
            'database': {
                'query_time_ms': 50.0,
                'connection_count': 5
            },
            'trading': {
                'order_processing_time_ms': 200.0,
                'signal_generation_time_ms': 300.0
            }
        }
        
        bottlenecks = performance_analyzer.identify_bottlenecks(critical_metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].component == 'CPU'
        assert bottlenecks[0].severity == 'critical'
        assert 'critically high' in bottlenecks[0].description
    
    def test_identify_bottlenecks_high_memory(self, performance_analyzer):
        """Test bottleneck identification with high memory usage."""
        high_memory_metrics = {
            'system': {
                'cpu_percent': 50.0,
                'memory_percent': 90.0,  # High
                'disk_usage_percent': 70.0
            },
            'application': {
                'response_time_ms': 100.0,
                'error_rate_percent': 1.0
            },
            'database': {
                'query_time_ms': 50.0,
                'connection_count': 5
            },
            'trading': {
                'order_processing_time_ms': 200.0,
                'signal_generation_time_ms': 300.0
            }
        }
        
        bottlenecks = performance_analyzer.identify_bottlenecks(high_memory_metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].component == 'Memory'
        assert bottlenecks[0].severity == 'high'
        assert 'high' in bottlenecks[0].description
    
    def test_identify_bottlenecks_slow_response_time(self, performance_analyzer):
        """Test bottleneck identification with slow response time."""
        slow_response_metrics = {
            'system': {
                'cpu_percent': 50.0,
                'memory_percent': 60.0,
                'disk_usage_percent': 70.0
            },
            'application': {
                'response_time_ms': 3000.0,  # High
                'error_rate_percent': 1.0
            },
            'database': {
                'query_time_ms': 50.0,
                'connection_count': 5
            },
            'trading': {
                'order_processing_time_ms': 200.0,
                'signal_generation_time_ms': 300.0
            }
        }
        
        bottlenecks = performance_analyzer.identify_bottlenecks(slow_response_metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].component == 'Application'
        assert bottlenecks[0].severity == 'high'
        assert 'slow' in bottlenecks[0].description
    
    def test_identify_bottlenecks_high_error_rate(self, performance_analyzer):
        """Test bottleneck identification with high error rate."""
        high_error_metrics = {
            'system': {
                'cpu_percent': 50.0,
                'memory_percent': 60.0,
                'disk_usage_percent': 70.0
            },
            'application': {
                'response_time_ms': 100.0,
                'error_rate_percent': 15.0  # High error rate
            },
            'database': {
                'query_time_ms': 50.0,
                'connection_count': 5
            },
            'trading': {
                'order_processing_time_ms': 200.0,
                'signal_generation_time_ms': 300.0
            }
        }
        
        bottlenecks = performance_analyzer.identify_bottlenecks(high_error_metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].component == 'Application'
        assert bottlenecks[0].severity == 'critical'
        assert 'critically high' in bottlenecks[0].description
    
    def test_identify_bottlenecks_slow_database(self, performance_analyzer):
        """Test bottleneck identification with slow database queries."""
        slow_db_metrics = {
            'system': {
                'cpu_percent': 50.0,
                'memory_percent': 60.0,
                'disk_usage_percent': 70.0
            },
            'application': {
                'response_time_ms': 100.0,
                'error_rate_percent': 1.0
            },
            'database': {
                'query_time_ms': 800.0,  # High
                'connection_count': 5
            },
            'trading': {
                'order_processing_time_ms': 200.0,
                'signal_generation_time_ms': 300.0
            }
        }
        
        bottlenecks = performance_analyzer.identify_bottlenecks(slow_db_metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].component == 'Database'
        assert bottlenecks[0].severity == 'high'
        assert 'slow' in bottlenecks[0].description
    
    def test_identify_bottlenecks_slow_order_processing(self, performance_analyzer):
        """Test bottleneck identification with slow order processing."""
        slow_trading_metrics = {
            'system': {
                'cpu_percent': 50.0,
                'memory_percent': 60.0,
                'disk_usage_percent': 70.0
            },
            'application': {
                'response_time_ms': 100.0,
                'error_rate_percent': 1.0
            },
            'database': {
                'query_time_ms': 50.0,
                'connection_count': 5
            },
            'trading': {
                'order_processing_time_ms': 1500.0,  # Critical
                'signal_generation_time_ms': 300.0
            }
        }
        
        bottlenecks = performance_analyzer.identify_bottlenecks(slow_trading_metrics)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].component == 'Trading'
        assert bottlenecks[0].severity == 'critical'
        assert 'critically slow' in bottlenecks[0].description
    
    def test_analyze_performance_trends_insufficient_data(self, performance_analyzer):
        """Test trend analysis with insufficient data."""
        insufficient_data = [
            {'system': {'cpu_percent': 50.0}},
            {'system': {'cpu_percent': 55.0}}
        ]  # Only 2 samples, need 10 minimum
        
        trends = performance_analyzer.analyze_performance_trends(insufficient_data)
        assert len(trends) == 0
    
    def test_analyze_performance_trends_sufficient_data(self, performance_analyzer):
        """Test trend analysis with sufficient data."""
        # Create sample data with clear trend
        sufficient_data = []
        for i in range(15):  # More than minimum required
            sufficient_data.append({
                'system': {'cpu_percent': 50.0 + i * 2.0},  # Increasing trend
                'application': {'response_time_ms': 100.0 + i * 10.0}  # Increasing trend
            })
        
        trends = performance_analyzer.analyze_performance_trends(sufficient_data)
        assert len(trends) >= 1  # Should have at least one trend
        
        # Check that trends are properly formatted
        for trend in trends:
            assert hasattr(trend, 'metric')
            assert hasattr(trend, 'trend_direction')
            assert hasattr(trend, 'change_percent')
            assert hasattr(trend, 'confidence')
            assert hasattr(trend, 'time_period')
    
    def test_establish_baseline_insufficient_data(self, performance_analyzer):
        """Test baseline establishment with insufficient data."""
        insufficient_data = [
            {'system': {'cpu_percent': 50.0}},
            {'system': {'cpu_percent': 55.0}}
        ]  # Only 2 samples, need 10 minimum
        
        baselines = performance_analyzer.establish_baseline(insufficient_data)
        assert len(baselines) == 0
    
    def test_establish_baseline_sufficient_data(self, performance_analyzer):
        """Test baseline establishment with sufficient data."""
        # Create sample data
        sufficient_data = []
        for i in range(20):  # More than minimum required
            sufficient_data.append({
                'system': {'cpu_percent': 50.0 + (i % 10) * 2.0},
                'application': {'response_time_ms': 100.0 + (i % 5) * 10.0}
            })
        
        baselines = performance_analyzer.establish_baseline(sufficient_data)
        assert len(baselines) >= 1  # Should have at least one baseline
        
        # Check that baselines are properly formatted
        for baseline in baselines:
            assert hasattr(baseline, 'metric')
            assert hasattr(baseline, 'baseline_value')
            assert hasattr(baseline, 'standard_deviation')
            assert hasattr(baseline, 'percentile_95')
            assert hasattr(baseline, 'percentile_99')
            assert hasattr(baseline, 'sample_size')
    
    def test_detect_performance_regression_no_baselines(self, performance_analyzer):
        """Test regression detection with no baselines."""
        current_metrics = {
            'system': {'cpu_percent': 80.0},
            'application': {'response_time_ms': 500.0}
        }
        
        regressions = performance_analyzer.detect_performance_regression(current_metrics, [])
        assert len(regressions) == 0
    
    def test_detect_performance_regression_with_baselines(self, performance_analyzer):
        """Test regression detection with baselines."""
        current_metrics = {
            'system': {'cpu_percent': 80.0},
            'application': {'response_time_ms': 500.0}
        }
        
        # Create mock baselines
        baselines = [
            PerformanceBaseline(
                metric='system.cpu_percent',
                baseline_value=50.0,
                standard_deviation=10.0,
                percentile_95=70.0,
                percentile_99=80.0,
                sample_size=100
            ),
            PerformanceBaseline(
                metric='application.response_time_ms',
                baseline_value=100.0,
                standard_deviation=20.0,
                percentile_95=150.0,
                percentile_99=200.0,
                sample_size=100
            )
        ]
        
        regressions = performance_analyzer.detect_performance_regression(current_metrics, baselines)
        assert len(regressions) == 2  # Both metrics exceed 99th percentile
        assert any('system.cpu_percent' in r for r in regressions)
        assert any('application.response_time_ms' in r for r in regressions)
    
    def test_calculate_trend_improving(self, performance_analyzer):
        """Test trend calculation for improving performance."""
        data = [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0, 10.0]
        trend = performance_analyzer._calculate_trend(data, 'test_metric')
        
        assert trend is not None
        assert trend.metric == 'test_metric'
        assert trend.trend_direction == 'improving'
        assert trend.change_percent < 0  # Negative change for improvement
    
    def test_calculate_trend_degrading(self, performance_analyzer):
        """Test trend calculation for degrading performance."""
        data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        trend = performance_analyzer._calculate_trend(data, 'test_metric')
        
        assert trend is not None
        assert trend.metric == 'test_metric'
        assert trend.trend_direction == 'degrading'
        assert trend.change_percent > 0  # Positive change for degradation
    
    def test_calculate_trend_stable(self, performance_analyzer):
        """Test trend calculation for stable performance."""
        data = [50.0, 51.0, 49.0, 50.0, 51.0, 49.0, 50.0, 51.0, 49.0, 50.0]
        trend = performance_analyzer._calculate_trend(data, 'test_metric')
        
        assert trend is not None
        assert trend.metric == 'test_metric'
        assert trend.trend_direction == 'stable'
        assert abs(trend.change_percent) < 5.0  # Small change for stability
    
    def test_calculate_percentile(self, performance_analyzer):
        """Test percentile calculation."""
        data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        
        p95 = performance_analyzer._calculate_percentile(data, 95)
        p99 = performance_analyzer._calculate_percentile(data, 99)
        
        assert abs(p95 - 95.0) < 1.0  # 95th percentile should be approximately 95.0
        assert abs(p99 - 99.0) < 1.0  # 99th percentile should be approximately 99.0
    
    def test_calculate_percentile_empty_data(self, performance_analyzer):
        """Test percentile calculation with empty data."""
        data = []
        p95 = performance_analyzer._calculate_percentile(data, 95)
        assert p95 == 0.0
    
    def test_analyze_system_trends(self, performance_analyzer):
        """Test system trends analysis."""
        metrics_history = []
        for i in range(15):
            metrics_history.append({
                'system': {
                    'cpu_percent': 50.0 + i * 2.0,
                    'memory_percent': 60.0 + i * 1.0
                }
            })
        
        trends = performance_analyzer._analyze_system_trends(metrics_history)
        assert len(trends) >= 1  # Should have at least one trend
    
    def test_analyze_application_trends(self, performance_analyzer):
        """Test application trends analysis."""
        metrics_history = []
        for i in range(15):
            metrics_history.append({
                'application': {
                    'response_time_ms': 100.0 + i * 5.0,
                    'throughput_rps': 10.0 + i * 0.5
                }
            })
        
        trends = performance_analyzer._analyze_application_trends(metrics_history)
        assert len(trends) >= 1  # Should have at least one trend
    
    def test_analyze_database_trends(self, performance_analyzer):
        """Test database trends analysis."""
        metrics_history = []
        for i in range(15):
            metrics_history.append({
                'database': {
                    'query_time_ms': 50.0 + i * 2.0
                }
            })
        
        trends = performance_analyzer._analyze_database_trends(metrics_history)
        assert len(trends) >= 1  # Should have at least one trend
