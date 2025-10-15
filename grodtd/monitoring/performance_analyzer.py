"""
Performance analysis module for GRODT trading system.

This module provides performance bottleneck identification, trend analysis,
and performance optimization recommendations.
"""

import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Bottleneck:
    """Performance bottleneck identification."""
    component: str
    metric: str
    current_value: float
    threshold: float
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    recommendation: str


@dataclass
class PerformanceTrend:
    """Performance trend analysis."""
    metric: str
    trend_direction: str  # 'improving', 'degrading', 'stable'
    change_percent: float
    confidence: float
    time_period: str


@dataclass
class PerformanceBaseline:
    """Performance baseline establishment."""
    metric: str
    baseline_value: float
    standard_deviation: float
    percentile_95: float
    percentile_99: float
    sample_size: int


class PerformanceAnalyzer:
    """
    Performance analysis and bottleneck identification system.
    
    Analyzes performance metrics to identify bottlenecks, track trends,
    and provide optimization recommendations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize performance analyzer.
        
        Args:
            config: Configuration dictionary with analysis settings
        """
        self.config = config or {}
        self.logger = structlog.get_logger(__name__)
        
        # Analysis thresholds
        self.thresholds = {
            'cpu_critical': self.config.get('cpu_critical_threshold', 95.0),
            'cpu_high': self.config.get('cpu_high_threshold', 85.0),
            'cpu_medium': self.config.get('cpu_medium_threshold', 75.0),
            'memory_critical': self.config.get('memory_critical_threshold', 95.0),
            'memory_high': self.config.get('memory_high_threshold', 85.0),
            'memory_medium': self.config.get('memory_medium_threshold', 75.0),
            'response_time_critical': self.config.get('response_time_critical_threshold', 5000.0),
            'response_time_high': self.config.get('response_time_high_threshold', 2000.0),
            'response_time_medium': self.config.get('response_time_medium_threshold', 1000.0),
            'query_time_critical': self.config.get('query_time_critical_threshold', 1000.0),
            'query_time_high': self.config.get('query_time_high_threshold', 500.0),
            'query_time_medium': self.config.get('query_time_medium_threshold', 200.0)
        }
        
        # Trend analysis settings
        self.trend_window_hours = self.config.get('trend_window_hours', 24)
        self.min_samples_for_trend = self.config.get('min_samples_for_trend', 10)
        
        self.logger.info("Performance analyzer initialized", 
                        thresholds=self.thresholds)
    
    def identify_bottlenecks(self, metrics: Dict[str, Any]) -> List[Bottleneck]:
        """
        Identify performance bottlenecks from current metrics.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            List of identified bottlenecks
        """
        bottlenecks = []
        
        try:
            system = metrics.get('system', {})
            application = metrics.get('application', {})
            database = metrics.get('database', {})
            trading = metrics.get('trading', {})
            
            # Analyze system bottlenecks
            bottlenecks.extend(self._analyze_system_bottlenecks(system))
            
            # Analyze application bottlenecks
            bottlenecks.extend(self._analyze_application_bottlenecks(application))
            
            # Analyze database bottlenecks
            bottlenecks.extend(self._analyze_database_bottlenecks(database))
            
            # Analyze trading bottlenecks
            bottlenecks.extend(self._analyze_trading_bottlenecks(trading))
            
            if bottlenecks:
                self.logger.warning("Performance bottlenecks identified",
                                  bottleneck_count=len(bottlenecks),
                                  critical_count=len([b for b in bottlenecks if b.severity == 'critical']))
            else:
                self.logger.info("No performance bottlenecks detected")
            
            return bottlenecks
            
        except Exception as e:
            self.logger.error("Failed to identify bottlenecks", error=str(e))
            return []
    
    def _analyze_system_bottlenecks(self, system_metrics: Dict[str, Any]) -> List[Bottleneck]:
        """Analyze system resource bottlenecks."""
        bottlenecks = []
        
        # CPU bottleneck analysis
        cpu_percent = system_metrics.get('cpu_percent', 0)
        if cpu_percent >= self.thresholds['cpu_critical']:
            bottlenecks.append(Bottleneck(
                component='CPU',
                metric='cpu_percent',
                current_value=cpu_percent,
                threshold=self.thresholds['cpu_critical'],
                severity='critical',
                description=f'CPU usage is critically high at {cpu_percent:.1f}%',
                recommendation='Consider scaling up CPU resources or optimizing CPU-intensive operations'
            ))
        elif cpu_percent >= self.thresholds['cpu_high']:
            bottlenecks.append(Bottleneck(
                component='CPU',
                metric='cpu_percent',
                current_value=cpu_percent,
                threshold=self.thresholds['cpu_high'],
                severity='high',
                description=f'CPU usage is high at {cpu_percent:.1f}%',
                recommendation='Monitor CPU usage and consider optimization'
            ))
        elif cpu_percent >= self.thresholds['cpu_medium']:
            bottlenecks.append(Bottleneck(
                component='CPU',
                metric='cpu_percent',
                current_value=cpu_percent,
                threshold=self.thresholds['cpu_medium'],
                severity='medium',
                description=f'CPU usage is elevated at {cpu_percent:.1f}%',
                recommendation='Monitor CPU usage trends'
            ))
        
        # Memory bottleneck analysis
        memory_percent = system_metrics.get('memory_percent', 0)
        if memory_percent >= self.thresholds['memory_critical']:
            bottlenecks.append(Bottleneck(
                component='Memory',
                metric='memory_percent',
                current_value=memory_percent,
                threshold=self.thresholds['memory_critical'],
                severity='critical',
                description=f'Memory usage is critically high at {memory_percent:.1f}%',
                recommendation='Immediate memory optimization or scaling required'
            ))
        elif memory_percent >= self.thresholds['memory_high']:
            bottlenecks.append(Bottleneck(
                component='Memory',
                metric='memory_percent',
                current_value=memory_percent,
                threshold=self.thresholds['memory_high'],
                severity='high',
                description=f'Memory usage is high at {memory_percent:.1f}%',
                recommendation='Review memory usage patterns and optimize'
            ))
        elif memory_percent >= self.thresholds['memory_medium']:
            bottlenecks.append(Bottleneck(
                component='Memory',
                metric='memory_percent',
                current_value=memory_percent,
                threshold=self.thresholds['memory_medium'],
                severity='medium',
                description=f'Memory usage is elevated at {memory_percent:.1f}%',
                recommendation='Monitor memory usage trends'
            ))
        
        return bottlenecks
    
    def _analyze_application_bottlenecks(self, app_metrics: Dict[str, Any]) -> List[Bottleneck]:
        """Analyze application performance bottlenecks."""
        bottlenecks = []
        
        # Response time analysis
        response_time_ms = app_metrics.get('response_time_ms', 0)
        if response_time_ms >= self.thresholds['response_time_critical']:
            bottlenecks.append(Bottleneck(
                component='Application',
                metric='response_time_ms',
                current_value=response_time_ms,
                threshold=self.thresholds['response_time_critical'],
                severity='critical',
                description=f'Response time is critically slow at {response_time_ms:.1f}ms',
                recommendation='Immediate performance optimization required'
            ))
        elif response_time_ms >= self.thresholds['response_time_high']:
            bottlenecks.append(Bottleneck(
                component='Application',
                metric='response_time_ms',
                current_value=response_time_ms,
                threshold=self.thresholds['response_time_high'],
                severity='high',
                description=f'Response time is slow at {response_time_ms:.1f}ms',
                recommendation='Optimize application performance'
            ))
        elif response_time_ms >= self.thresholds['response_time_medium']:
            bottlenecks.append(Bottleneck(
                component='Application',
                metric='response_time_ms',
                current_value=response_time_ms,
                threshold=self.thresholds['response_time_medium'],
                severity='medium',
                description=f'Response time is elevated at {response_time_ms:.1f}ms',
                recommendation='Monitor response time trends'
            ))
        
        # Error rate analysis
        error_rate = app_metrics.get('error_rate_percent', 0)
        if error_rate > 10.0:
            bottlenecks.append(Bottleneck(
                component='Application',
                metric='error_rate_percent',
                current_value=error_rate,
                threshold=10.0,
                severity='critical',
                description=f'Error rate is critically high at {error_rate:.1f}%',
                recommendation='Immediate error investigation and resolution required'
            ))
        elif error_rate > 5.0:
            bottlenecks.append(Bottleneck(
                component='Application',
                metric='error_rate_percent',
                current_value=error_rate,
                threshold=5.0,
                severity='high',
                description=f'Error rate is high at {error_rate:.1f}%',
                recommendation='Investigate and resolve errors'
            ))
        
        return bottlenecks
    
    def _analyze_database_bottlenecks(self, db_metrics: Dict[str, Any]) -> List[Bottleneck]:
        """Analyze database performance bottlenecks."""
        bottlenecks = []
        
        # Query time analysis
        query_time_ms = db_metrics.get('query_time_ms', 0)
        if query_time_ms >= self.thresholds['query_time_critical']:
            bottlenecks.append(Bottleneck(
                component='Database',
                metric='query_time_ms',
                current_value=query_time_ms,
                threshold=self.thresholds['query_time_critical'],
                severity='critical',
                description=f'Database query time is critically slow at {query_time_ms:.1f}ms',
                recommendation='Immediate database optimization required'
            ))
        elif query_time_ms >= self.thresholds['query_time_high']:
            bottlenecks.append(Bottleneck(
                component='Database',
                metric='query_time_ms',
                current_value=query_time_ms,
                threshold=self.thresholds['query_time_high'],
                severity='high',
                description=f'Database query time is slow at {query_time_ms:.1f}ms',
                recommendation='Optimize database queries and indexes'
            ))
        elif query_time_ms >= self.thresholds['query_time_medium']:
            bottlenecks.append(Bottleneck(
                component='Database',
                metric='query_time_ms',
                current_value=query_time_ms,
                threshold=self.thresholds['query_time_medium'],
                severity='medium',
                description=f'Database query time is elevated at {query_time_ms:.1f}ms',
                recommendation='Monitor database performance trends'
            ))
        
        # Connection count analysis
        connection_count = db_metrics.get('connection_count', 0)
        if connection_count > 100:  # Assuming max connections threshold
            bottlenecks.append(Bottleneck(
                component='Database',
                metric='connection_count',
                current_value=connection_count,
                threshold=100,
                severity='high',
                description=f'Database connection count is high at {connection_count}',
                recommendation='Review connection pooling and usage patterns'
            ))
        
        return bottlenecks
    
    def _analyze_trading_bottlenecks(self, trading_metrics: Dict[str, Any]) -> List[Bottleneck]:
        """Analyze trading operation bottlenecks."""
        bottlenecks = []
        
        # Order processing time analysis
        order_time_ms = trading_metrics.get('order_processing_time_ms', 0)
        if order_time_ms > 1000:  # 1 second threshold for order processing
            bottlenecks.append(Bottleneck(
                component='Trading',
                metric='order_processing_time_ms',
                current_value=order_time_ms,
                threshold=1000,
                severity='critical',
                description=f'Order processing time is critically slow at {order_time_ms:.1f}ms',
                recommendation='Immediate trading system optimization required'
            ))
        elif order_time_ms > 500:
            bottlenecks.append(Bottleneck(
                component='Trading',
                metric='order_processing_time_ms',
                current_value=order_time_ms,
                threshold=500,
                severity='high',
                description=f'Order processing time is slow at {order_time_ms:.1f}ms',
                recommendation='Optimize order processing pipeline'
            ))
        
        # Signal generation time analysis
        signal_time_ms = trading_metrics.get('signal_generation_time_ms', 0)
        if signal_time_ms > 2000:  # 2 second threshold for signal generation
            bottlenecks.append(Bottleneck(
                component='Trading',
                metric='signal_generation_time_ms',
                current_value=signal_time_ms,
                threshold=2000,
                severity='high',
                description=f'Signal generation time is slow at {signal_time_ms:.1f}ms',
                recommendation='Optimize signal generation algorithms'
            ))
        
        return bottlenecks
    
    def analyze_performance_trends(self, metrics_history: List[Dict[str, Any]]) -> List[PerformanceTrend]:
        """
        Analyze performance trends from historical data.
        
        Args:
            metrics_history: Historical performance metrics
            
        Returns:
            List of performance trends
        """
        trends = []
        
        try:
            if len(metrics_history) < self.min_samples_for_trend:
                self.logger.warning("Insufficient data for trend analysis",
                                  samples=len(metrics_history),
                                  required=self.min_samples_for_trend)
                return trends
            
            # Analyze system trends
            trends.extend(self._analyze_system_trends(metrics_history))
            
            # Analyze application trends
            trends.extend(self._analyze_application_trends(metrics_history))
            
            # Analyze database trends
            trends.extend(self._analyze_database_trends(metrics_history))
            
            self.logger.info("Performance trends analyzed",
                           trend_count=len(trends))
            
            return trends
            
        except Exception as e:
            self.logger.error("Failed to analyze performance trends", error=str(e))
            return []
    
    def _analyze_system_trends(self, metrics_history: List[Dict[str, Any]]) -> List[PerformanceTrend]:
        """Analyze system performance trends."""
        trends = []
        
        # Extract CPU and memory data
        cpu_data = [m['system']['cpu_percent'] for m in metrics_history if 'system' in m and 'cpu_percent' in m['system']]
        memory_data = [m['system']['memory_percent'] for m in metrics_history if 'system' in m and 'memory_percent' in m['system']]
        
        if len(cpu_data) >= self.min_samples_for_trend:
            cpu_trend = self._calculate_trend(cpu_data, 'cpu_percent')
            if cpu_trend:
                trends.append(cpu_trend)
        
        if len(memory_data) >= self.min_samples_for_trend:
            memory_trend = self._calculate_trend(memory_data, 'memory_percent')
            if memory_trend:
                trends.append(memory_trend)
        
        return trends
    
    def _analyze_application_trends(self, metrics_history: List[Dict[str, Any]]) -> List[PerformanceTrend]:
        """Analyze application performance trends."""
        trends = []
        
        # Extract response time and throughput data
        response_times = [m['application']['response_time_ms'] for m in metrics_history if 'application' in m and 'response_time_ms' in m['application']]
        throughputs = [m['application']['throughput_rps'] for m in metrics_history if 'application' in m and 'throughput_rps' in m['application']]
        
        if len(response_times) >= self.min_samples_for_trend:
            response_trend = self._calculate_trend(response_times, 'response_time_ms')
            if response_trend:
                trends.append(response_trend)
        
        if len(throughputs) >= self.min_samples_for_trend:
            throughput_trend = self._calculate_trend(throughputs, 'throughput_rps')
            if throughput_trend:
                trends.append(throughput_trend)
        
        return trends
    
    def _analyze_database_trends(self, metrics_history: List[Dict[str, Any]]) -> List[PerformanceTrend]:
        """Analyze database performance trends."""
        trends = []
        
        # Extract query time data
        query_times = [m['database']['query_time_ms'] for m in metrics_history if 'database' in m and 'query_time_ms' in m['database']]
        
        if len(query_times) >= self.min_samples_for_trend:
            query_trend = self._calculate_trend(query_times, 'query_time_ms')
            if query_trend:
                trends.append(query_trend)
        
        return trends
    
    def _calculate_trend(self, data: List[float], metric_name: str) -> Optional[PerformanceTrend]:
        """Calculate trend for a metric."""
        if len(data) < 2:
            return None
        
        # Simple linear regression for trend calculation
        n = len(data)
        x = list(range(n))
        
        # Calculate slope
        x_mean = sum(x) / n
        y_mean = sum(data) / n
        
        numerator = sum((x[i] - x_mean) * (data[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return None
        
        slope = numerator / denominator
        
        # Determine trend direction
        if slope > 0.1:
            direction = 'degrading'
        elif slope < -0.1:
            direction = 'improving'
        else:
            direction = 'stable'
        
        # Calculate change percentage
        change_percent = ((data[-1] - data[0]) / data[0] * 100) if data[0] != 0 else 0
        
        # Calculate confidence (simple correlation coefficient)
        correlation = numerator / (denominator * sum((data[i] - y_mean) ** 2 for i in range(n))) ** 0.5
        confidence = abs(correlation) if correlation else 0
        
        return PerformanceTrend(
            metric=metric_name,
            trend_direction=direction,
            change_percent=change_percent,
            confidence=confidence,
            time_period=f'{n} samples'
        )
    
    def establish_baseline(self, metrics_history: List[Dict[str, Any]]) -> List[PerformanceBaseline]:
        """
        Establish performance baselines from historical data.
        
        Args:
            metrics_history: Historical performance metrics
            
        Returns:
            List of performance baselines
        """
        baselines = []
        
        try:
            if not metrics_history:
                self.logger.warning("No historical data available for baseline establishment")
                return baselines
            
            # Extract metrics for baseline calculation
            metrics_to_analyze = [
                ('system', 'cpu_percent'),
                ('system', 'memory_percent'),
                ('application', 'response_time_ms'),
                ('application', 'throughput_rps'),
                ('database', 'query_time_ms')
            ]
            
            for component, metric in metrics_to_analyze:
                values = []
                for m in metrics_history:
                    if component in m and metric in m[component]:
                        values.append(m[component][metric])
                
                if len(values) >= 10:  # Minimum samples for baseline
                    baseline = PerformanceBaseline(
                        metric=f'{component}.{metric}',
                        baseline_value=statistics.mean(values),
                        standard_deviation=statistics.stdev(values) if len(values) > 1 else 0,
                        percentile_95=self._calculate_percentile(values, 95),
                        percentile_99=self._calculate_percentile(values, 99),
                        sample_size=len(values)
                    )
                    baselines.append(baseline)
            
            self.logger.info("Performance baselines established",
                           baseline_count=len(baselines))
            
            return baselines
            
        except Exception as e:
            self.logger.error("Failed to establish performance baselines", error=str(e))
            return []
    
    def _calculate_percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        n = len(sorted_data)
        index = (percentile / 100) * (n - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower_idx = int(index)
            upper_idx = min(lower_idx + 1, n - 1)
            lower = sorted_data[lower_idx]
            upper = sorted_data[upper_idx]
            return lower + (upper - lower) * (index - lower_idx)
    
    def detect_performance_regression(self, current_metrics: Dict[str, Any], 
                                   baselines: List[PerformanceBaseline]) -> List[str]:
        """
        Detect performance regression against baselines.
        
        Args:
            current_metrics: Current performance metrics
            baselines: Established performance baselines
            
        Returns:
            List of regression alerts
        """
        regressions = []
        
        try:
            for baseline in baselines:
                component, metric = baseline.metric.split('.', 1)
                current_value = current_metrics.get(component, {}).get(metric, 0)
                
                # Check if current value exceeds 99th percentile
                if current_value > baseline.percentile_99:
                    regressions.append(
                        f"Performance regression detected: {baseline.metric} "
                        f"({current_value:.2f}) exceeds 99th percentile "
                        f"({baseline.percentile_99:.2f})"
                    )
                # Check if current value exceeds 95th percentile
                elif current_value > baseline.percentile_95:
                    regressions.append(
                        f"Performance degradation detected: {baseline.metric} "
                        f"({current_value:.2f}) exceeds 95th percentile "
                        f"({baseline.percentile_95:.2f})"
                    )
            
            if regressions:
                self.logger.warning("Performance regressions detected",
                                  regression_count=len(regressions))
            
            return regressions
            
        except Exception as e:
            self.logger.error("Failed to detect performance regression", error=str(e))
            return []
