"""
Performance trend tracking service for GRODT trading system.

This module provides comprehensive performance trend tracking, baseline establishment,
and regression detection capabilities.
"""

import asyncio
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import structlog
import json
from pathlib import Path

from .performance_monitor import PerformanceMonitor
from .performance_analyzer import PerformanceAnalyzer, PerformanceBaseline, PerformanceTrend

logger = structlog.get_logger(__name__)


@dataclass
class TrendDataPoint:
    """Individual data point for trend analysis."""
    timestamp: datetime
    metric_name: str
    value: float
    component: str


@dataclass
class TrendAnalysis:
    """Complete trend analysis result."""
    metric_name: str
    component: str
    trend_direction: str
    change_percent: float
    confidence: float
    data_points: int
    time_period_hours: float
    baseline_value: float
    current_value: float
    trend_strength: str  # 'weak', 'moderate', 'strong'


class PerformanceTrendService:
    """
    Performance trend tracking and analysis service.
    
    Provides comprehensive trend analysis, baseline establishment,
    and performance regression detection.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize performance trend service.
        
        Args:
            config: Configuration dictionary with trend analysis settings
        """
        self.config = config or {}
        self.logger = structlog.get_logger(__name__)
        
        # Trend analysis settings
        self.trend_window_hours = self.config.get('trend_window_hours', 24)
        self.min_samples_for_trend = self.config.get('min_samples_for_trend', 10)
        self.baseline_period_hours = self.config.get('baseline_period_hours', 168)  # 1 week
        self.regression_threshold = self.config.get('regression_threshold', 0.2)  # 20% degradation
        
        # Data storage
        self.trend_data: List[TrendDataPoint] = []
        self.baselines: Dict[str, PerformanceBaseline] = {}
        self.trend_cache: Dict[str, TrendAnalysis] = {}
        
        # Cache settings
        self.cache_ttl_seconds = self.config.get('cache_ttl_seconds', 300)  # 5 minutes
        self.max_cache_size = self.config.get('max_cache_size', 1000)
        
        self.logger.info("Performance trend service initialized",
                        trend_window_hours=self.trend_window_hours,
                        min_samples=self.min_samples_for_trend)
    
    async def collect_trend_data(self, monitor: PerformanceMonitor) -> None:
        """
        Collect performance data for trend analysis.
        
        Args:
            monitor: PerformanceMonitor instance to collect data from
        """
        try:
            # Collect current metrics
            current_metrics = await monitor.collect_all_metrics()
            timestamp = datetime.now()
            
            # Extract trend data points
            trend_points = self._extract_trend_data_points(current_metrics, timestamp)
            
            # Store trend data
            self.trend_data.extend(trend_points)
            
            # Maintain data size limit
            self._maintain_data_size()
            
            self.logger.debug("Trend data collected",
                            data_points=len(trend_points),
                            total_points=len(self.trend_data))
            
        except Exception as e:
            self.logger.error("Failed to collect trend data", error=str(e))
            raise
    
    def _extract_trend_data_points(self, metrics: Dict[str, Any], timestamp: datetime) -> List[TrendDataPoint]:
        """Extract trend data points from metrics."""
        trend_points = []
        
        # System metrics
        if 'system' in metrics:
            system = metrics['system']
            for metric_name, value in system.items():
                if isinstance(value, (int, float)):
                    trend_points.append(TrendDataPoint(
                        timestamp=timestamp,
                        metric_name=metric_name,
                        value=float(value),
                        component='system'
                    ))
        
        # Application metrics
        if 'application' in metrics:
            app = metrics['application']
            for metric_name, value in app.items():
                if isinstance(value, (int, float)):
                    trend_points.append(TrendDataPoint(
                        timestamp=timestamp,
                        metric_name=metric_name,
                        value=float(value),
                        component='application'
                    ))
        
        # Database metrics
        if 'database' in metrics:
            db = metrics['database']
            for metric_name, value in db.items():
                if isinstance(value, (int, float)):
                    trend_points.append(TrendDataPoint(
                        timestamp=timestamp,
                        metric_name=metric_name,
                        value=float(value),
                        component='database'
                    ))
        
        # Trading metrics
        if 'trading' in metrics:
            trading = metrics['trading']
            for metric_name, value in trading.items():
                if isinstance(value, (int, float)):
                    trend_points.append(TrendDataPoint(
                        timestamp=timestamp,
                        metric_name=metric_name,
                        value=float(value),
                        component='trading'
                    ))
        
        return trend_points
    
    def _maintain_data_size(self) -> None:
        """Maintain trend data size within limits."""
        max_data_points = self.config.get('max_data_points', 10000)
        
        if len(self.trend_data) > max_data_points:
            # Keep only the most recent data points
            self.trend_data = self.trend_data[-max_data_points:]
    
    async def analyze_trends(self, analyzer: PerformanceAnalyzer) -> List[TrendAnalysis]:
        """
        Analyze performance trends from collected data.
        
        Args:
            analyzer: PerformanceAnalyzer instance for trend analysis
            
        Returns:
            List of trend analysis results
        """
        try:
            # Convert trend data to metrics history format
            metrics_history = self._convert_to_metrics_history()
            
            # Analyze trends using the analyzer
            trends = analyzer.analyze_performance_trends(metrics_history)
            
            # Convert to trend analysis format
            trend_analyses = []
            for trend in trends:
                # Get current and baseline values
                current_value = self._get_current_value(trend.metric)
                baseline_value = self._get_baseline_value(trend.metric)
                
                # Calculate trend strength
                trend_strength = self._calculate_trend_strength(trend.confidence, abs(trend.change_percent))
                
                trend_analysis = TrendAnalysis(
                    metric_name=trend.metric,
                    component=self._get_component_from_metric(trend.metric),
                    trend_direction=trend.trend_direction,
                    change_percent=trend.change_percent,
                    confidence=trend.confidence,
                    data_points=len(self._get_metric_data(trend.metric)),
                    time_period_hours=self.trend_window_hours,
                    baseline_value=baseline_value,
                    current_value=current_value,
                    trend_strength=trend_strength
                )
                
                trend_analyses.append(trend_analysis)
            
            # Cache results
            self._cache_trend_results(trend_analyses)
            
            self.logger.info("Trend analysis completed",
                           trend_count=len(trend_analyses))
            
            return trend_analyses
            
        except Exception as e:
            self.logger.error("Failed to analyze trends", error=str(e))
            return []
    
    def _convert_to_metrics_history(self) -> List[Dict[str, Any]]:
        """Convert trend data to metrics history format."""
        # Group data by timestamp
        timestamp_groups = {}
        for point in self.trend_data:
            timestamp_key = point.timestamp.isoformat()
            if timestamp_key not in timestamp_groups:
                timestamp_groups[timestamp_key] = {
                    'timestamp': timestamp_key,
                    'system': {},
                    'application': {},
                    'database': {},
                    'trading': {}
                }
            
            timestamp_groups[timestamp_key][point.component][point.metric_name] = point.value
        
        # Convert to list and sort by timestamp
        metrics_history = list(timestamp_groups.values())
        metrics_history.sort(key=lambda x: x['timestamp'])
        
        return metrics_history
    
    def _get_current_value(self, metric_name: str) -> float:
        """Get current value for a metric."""
        # Find the most recent data point for this metric
        recent_points = [p for p in self.trend_data if p.metric_name == metric_name]
        if recent_points:
            return recent_points[-1].value
        return 0.0
    
    def _get_baseline_value(self, metric_name: str) -> float:
        """Get baseline value for a metric."""
        if metric_name in self.baselines:
            return self.baselines[metric_name].baseline_value
        return 0.0
    
    def _get_component_from_metric(self, metric_name: str) -> str:
        """Get component name from metric name."""
        if '.' in metric_name:
            return metric_name.split('.')[0]
        return 'unknown'
    
    def _get_metric_data(self, metric_name: str) -> List[TrendDataPoint]:
        """Get all data points for a specific metric."""
        return [p for p in self.trend_data if p.metric_name == metric_name]
    
    def _calculate_trend_strength(self, confidence: float, change_percent: float) -> str:
        """Calculate trend strength based on confidence and change percentage."""
        if confidence >= 0.8 and change_percent >= 20:
            return 'strong'
        elif confidence >= 0.6 and change_percent >= 10:
            return 'moderate'
        else:
            return 'weak'
    
    def _cache_trend_results(self, trend_analyses: List[TrendAnalysis]) -> None:
        """Cache trend analysis results."""
        for analysis in trend_analyses:
            cache_key = f"{analysis.component}.{analysis.metric_name}"
            self.trend_cache[cache_key] = analysis
        
        # Maintain cache size
        if len(self.trend_cache) > self.max_cache_size:
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(self.trend_cache.keys())[:len(self.trend_cache) - self.max_cache_size]
            for key in keys_to_remove:
                del self.trend_cache[key]
    
    async def establish_baselines(self, analyzer: PerformanceAnalyzer) -> Dict[str, PerformanceBaseline]:
        """
        Establish performance baselines from historical data.
        
        Args:
            analyzer: PerformanceAnalyzer instance for baseline establishment
            
        Returns:
            Dictionary of established baselines
        """
        try:
            # Convert trend data to metrics history format
            metrics_history = self._convert_to_metrics_history()
            
            # Establish baselines using the analyzer
            baselines = analyzer.establish_baseline(metrics_history)
            
            # Store baselines
            for baseline in baselines:
                self.baselines[baseline.metric] = baseline
            
            self.logger.info("Performance baselines established",
                           baseline_count=len(baselines))
            
            return {baseline.metric: baseline for baseline in baselines}
            
        except Exception as e:
            self.logger.error("Failed to establish baselines", error=str(e))
            return {}
    
    async def detect_regressions(self, analyzer: PerformanceAnalyzer) -> List[str]:
        """
        Detect performance regressions against established baselines.
        
        Args:
            analyzer: PerformanceAnalyzer instance for regression detection
            
        Returns:
            List of regression alerts
        """
        try:
            if not self.baselines:
                self.logger.warning("No baselines available for regression detection")
                return []
            
            # Get current metrics
            current_metrics = self._get_current_metrics()
            
            # Detect regressions
            regressions = analyzer.detect_performance_regression(current_metrics, list(self.baselines.values()))
            
            if regressions:
                self.logger.warning("Performance regressions detected",
                                  regression_count=len(regressions))
            
            return regressions
            
        except Exception as e:
            self.logger.error("Failed to detect regressions", error=str(e))
            return []
    
    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics from trend data."""
        current_metrics = {
            'system': {},
            'application': {},
            'database': {},
            'trading': {}
        }
        
        # Get the most recent data points for each metric
        for component in current_metrics:
            component_data = {}
            for point in self.trend_data:
                if point.component == component:
                    # Keep only the most recent value for each metric
                    if point.metric_name not in component_data:
                        component_data[point.metric_name] = point.value
            
            current_metrics[component] = component_data
        
        return current_metrics
    
    async def get_trend_summary(self) -> Dict[str, Any]:
        """
        Get summary of current trends.
        
        Returns:
            Dictionary with trend summary information
        """
        try:
            # Count trends by direction
            improving_count = len([t for t in self.trend_cache.values() if t.trend_direction == 'improving'])
            degrading_count = len([t for t in self.trend_cache.values() if t.trend_direction == 'degrading'])
            stable_count = len([t for t in self.trend_cache.values() if t.trend_direction == 'stable'])
            
            # Count trends by strength
            strong_count = len([t for t in self.trend_cache.values() if t.trend_strength == 'strong'])
            moderate_count = len([t for t in self.trend_cache.values() if t.trend_strength == 'moderate'])
            weak_count = len([t for t in self.trend_cache.values() if t.trend_strength == 'weak'])
            
            summary = {
                'total_trends': len(self.trend_cache),
                'trend_directions': {
                    'improving': improving_count,
                    'degrading': degrading_count,
                    'stable': stable_count
                },
                'trend_strengths': {
                    'strong': strong_count,
                    'moderate': moderate_count,
                    'weak': weak_count
                },
                'data_points': len(self.trend_data),
                'baselines_established': len(self.baselines),
                'cache_size': len(self.trend_cache)
            }
            
            return summary
            
        except Exception as e:
            self.logger.error("Failed to get trend summary", error=str(e))
            return {}
    
    async def export_trend_data(self, file_path: str) -> bool:
        """
        Export trend data to file.
        
        Args:
            file_path: Path to export file
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            export_data = {
                'trend_data': [
                    {
                        'timestamp': point.timestamp.isoformat(),
                        'metric_name': point.metric_name,
                        'value': point.value,
                        'component': point.component
                    }
                    for point in self.trend_data
                ],
                'baselines': {
                    metric: {
                        'baseline_value': baseline.baseline_value,
                        'standard_deviation': baseline.standard_deviation,
                        'percentile_95': baseline.percentile_95,
                        'percentile_99': baseline.percentile_99,
                        'sample_size': baseline.sample_size
                    }
                    for metric, baseline in self.baselines.items()
                },
                'trend_cache': {
                    key: {
                        'metric_name': analysis.metric_name,
                        'component': analysis.component,
                        'trend_direction': analysis.trend_direction,
                        'change_percent': analysis.change_percent,
                        'confidence': analysis.confidence,
                        'trend_strength': analysis.trend_strength
                    }
                    for key, analysis in self.trend_cache.items()
                }
            }
            
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info("Trend data exported", file_path=file_path)
            return True
            
        except Exception as e:
            self.logger.error("Failed to export trend data", error=str(e), file_path=file_path)
            return False
    
    async def import_trend_data(self, file_path: str) -> bool:
        """
        Import trend data from file.
        
        Args:
            file_path: Path to import file
            
        Returns:
            True if import successful, False otherwise
        """
        try:
            with open(file_path, 'r') as f:
                import_data = json.load(f)
            
            # Import trend data
            if 'trend_data' in import_data:
                self.trend_data = [
                    TrendDataPoint(
                        timestamp=datetime.fromisoformat(point['timestamp']),
                        metric_name=point['metric_name'],
                        value=point['value'],
                        component=point['component']
                    )
                    for point in import_data['trend_data']
                ]
            
            # Import baselines
            if 'baselines' in import_data:
                for metric, baseline_data in import_data['baselines'].items():
                    self.baselines[metric] = PerformanceBaseline(
                        metric=metric,
                        baseline_value=baseline_data['baseline_value'],
                        standard_deviation=baseline_data['standard_deviation'],
                        percentile_95=baseline_data['percentile_95'],
                        percentile_99=baseline_data['percentile_99'],
                        sample_size=baseline_data['sample_size']
                    )
            
            self.logger.info("Trend data imported", file_path=file_path)
            return True
            
        except Exception as e:
            self.logger.error("Failed to import trend data", error=str(e), file_path=file_path)
            return False
