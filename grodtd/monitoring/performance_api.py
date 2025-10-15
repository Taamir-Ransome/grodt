"""
Performance monitoring API endpoints for GRODT trading system.

This module provides REST API endpoints for performance monitoring,
including metrics collection, bottleneck identification, and performance reports.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import Blueprint, jsonify, request
import structlog

from .performance_monitor import PerformanceMonitor
from .performance_analyzer import PerformanceAnalyzer

logger = structlog.get_logger(__name__)

# Create Blueprint for performance monitoring API
performance_bp = Blueprint('performance', __name__, url_prefix='/performance')

# Global instances (will be initialized by the application)
performance_monitor: Optional[PerformanceMonitor] = None
performance_analyzer: Optional[PerformanceAnalyzer] = None


def init_performance_api(monitor: PerformanceMonitor, analyzer: PerformanceAnalyzer) -> None:
    """
    Initialize performance API with monitor and analyzer instances.
    
    Args:
        monitor: PerformanceMonitor instance
        analyzer: PerformanceAnalyzer instance
    """
    global performance_monitor, performance_analyzer
    performance_monitor = monitor
    performance_analyzer = analyzer
    logger.info("Performance API initialized")


@performance_bp.route('/metrics', methods=['GET'])
def get_current_metrics() -> Dict[str, Any]:
    """
    Get current performance metrics.
    
    Returns:
        JSON response with current performance metrics
    """
    try:
        if not performance_monitor:
            return jsonify({'error': 'Performance monitor not initialized'}), 500
        
        # Collect all current metrics
        metrics = await performance_monitor.collect_all_metrics()
        
        logger.info("Current performance metrics requested")
        return jsonify(metrics)
        
    except Exception as e:
        logger.error("Failed to get current metrics", error=str(e))
        return jsonify({'error': 'Failed to collect metrics'}), 500


@performance_bp.route('/trends', methods=['GET'])
def get_performance_trends() -> Dict[str, Any]:
    """
    Get performance trends analysis.
    
    Query Parameters:
        hours: Number of hours to analyze (default: 24)
        
    Returns:
        JSON response with performance trends
    """
    try:
        if not performance_monitor or not performance_analyzer:
            return jsonify({'error': 'Performance components not initialized'}), 500
        
        # Get hours parameter
        hours = request.args.get('hours', 24, type=int)
        
        # Get historical metrics for trend analysis
        # This would typically come from a time-series database
        # For now, we'll use the monitor's history
        metrics_history = performance_monitor.metrics_history
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_history = [
            m for m in metrics_history 
            if datetime.fromisoformat(m['timestamp']) >= cutoff_time
        ]
        
        # Analyze trends
        trends = performance_analyzer.analyze_performance_trends(filtered_history)
        
        response = {
            'time_window_hours': hours,
            'trends': [
                {
                    'metric': trend.metric,
                    'direction': trend.trend_direction,
                    'change_percent': trend.change_percent,
                    'confidence': trend.confidence,
                    'time_period': trend.time_period
                }
                for trend in trends
            ]
        }
        
        logger.info("Performance trends requested", 
                   hours=hours, 
                   trend_count=len(trends))
        return jsonify(response)
        
    except Exception as e:
        logger.error("Failed to get performance trends", error=str(e))
        return jsonify({'error': 'Failed to analyze trends'}), 500


@performance_bp.route('/bottlenecks', methods=['GET'])
def get_performance_bottlenecks() -> Dict[str, Any]:
    """
    Get identified performance bottlenecks.
    
    Returns:
        JSON response with performance bottlenecks
    """
    try:
        if not performance_monitor or not performance_analyzer:
            return jsonify({'error': 'Performance components not initialized'}), 500
        
        # Get current metrics
        current_metrics = await performance_monitor.collect_all_metrics()
        
        # Identify bottlenecks
        bottlenecks = performance_analyzer.identify_bottlenecks(current_metrics)
        
        response = {
            'timestamp': datetime.now().isoformat(),
            'bottlenecks': [
                {
                    'component': bottleneck.component,
                    'metric': bottleneck.metric,
                    'current_value': bottleneck.current_value,
                    'threshold': bottleneck.threshold,
                    'severity': bottleneck.severity,
                    'description': bottleneck.description,
                    'recommendation': bottleneck.recommendation
                }
                for bottleneck in bottlenecks
            ],
            'summary': {
                'total_bottlenecks': len(bottlenecks),
                'critical_count': len([b for b in bottlenecks if b.severity == 'critical']),
                'high_count': len([b for b in bottlenecks if b.severity == 'high']),
                'medium_count': len([b for b in bottlenecks if b.severity == 'medium']),
                'low_count': len([b for b in bottlenecks if b.severity == 'low'])
            }
        }
        
        logger.info("Performance bottlenecks requested",
                   total_bottlenecks=len(bottlenecks),
                   critical_count=response['summary']['critical_count'])
        return jsonify(response)
        
    except Exception as e:
        logger.error("Failed to get performance bottlenecks", error=str(e))
        return jsonify({'error': 'Failed to identify bottlenecks'}), 500


@performance_bp.route('/reports', methods=['GET'])
def get_performance_reports() -> Dict[str, Any]:
    """
    Get performance reports and analysis.
    
    Query Parameters:
        report_type: Type of report ('summary', 'detailed', 'trends')
        hours: Number of hours to include in report (default: 24)
        
    Returns:
        JSON response with performance reports
    """
    try:
        if not performance_monitor or not performance_analyzer:
            return jsonify({'error': 'Performance components not initialized'}), 500
        
        # Get query parameters
        report_type = request.args.get('report_type', 'summary')
        hours = request.args.get('hours', 24, type=int)
        
        # Get current metrics
        current_metrics = await performance_monitor.collect_all_metrics()
        
        # Get historical data
        cutoff_time = datetime.now() - timedelta(hours=hours)
        historical_metrics = [
            m for m in performance_monitor.metrics_history
            if datetime.fromisoformat(m['timestamp']) >= cutoff_time
        ]
        
        # Generate report based on type
        if report_type == 'summary':
            report = _generate_summary_report(current_metrics, historical_metrics)
        elif report_type == 'detailed':
            report = _generate_detailed_report(current_metrics, historical_metrics, performance_analyzer)
        elif report_type == 'trends':
            report = _generate_trends_report(historical_metrics, performance_analyzer)
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        logger.info("Performance report requested",
                   report_type=report_type,
                   hours=hours)
        return jsonify(report)
        
    except Exception as e:
        logger.error("Failed to get performance reports", error=str(e))
        return jsonify({'error': 'Failed to generate reports'}), 500


@performance_bp.route('/baseline', methods=['POST'])
def establish_baseline() -> Dict[str, Any]:
    """
    Establish performance baselines from historical data.
    
    Returns:
        JSON response with established baselines
    """
    try:
        if not performance_analyzer:
            return jsonify({'error': 'Performance analyzer not initialized'}), 500
        
        # Get historical metrics
        historical_metrics = performance_monitor.metrics_history if performance_monitor else []
        
        if not historical_metrics:
            return jsonify({'error': 'No historical data available'}), 400
        
        # Establish baselines
        baselines = performance_analyzer.establish_baseline(historical_metrics)
        
        response = {
            'timestamp': datetime.now().isoformat(),
            'baselines': [
                {
                    'metric': baseline.metric,
                    'baseline_value': baseline.baseline_value,
                    'standard_deviation': baseline.standard_deviation,
                    'percentile_95': baseline.percentile_95,
                    'percentile_99': baseline.percentile_99,
                    'sample_size': baseline.sample_size
                }
                for baseline in baselines
            ]
        }
        
        logger.info("Performance baselines established",
                   baseline_count=len(baselines))
        return jsonify(response)
        
    except Exception as e:
        logger.error("Failed to establish performance baselines", error=str(e))
        return jsonify({'error': 'Failed to establish baselines'}), 500


@performance_bp.route('/regression', methods=['GET'])
def check_performance_regression() -> Dict[str, Any]:
    """
    Check for performance regression against established baselines.
    
    Returns:
        JSON response with regression analysis
    """
    try:
        if not performance_monitor or not performance_analyzer:
            return jsonify({'error': 'Performance components not initialized'}), 500
        
        # Get current metrics
        current_metrics = await performance_monitor.collect_all_metrics()
        
        # Get historical data for baseline
        historical_metrics = performance_monitor.metrics_history if performance_monitor else []
        
        if not historical_metrics:
            return jsonify({'error': 'No historical data available for regression analysis'}), 400
        
        # Establish baselines
        baselines = performance_analyzer.establish_baseline(historical_metrics)
        
        # Check for regression
        regressions = performance_analyzer.detect_performance_regression(current_metrics, baselines)
        
        response = {
            'timestamp': datetime.now().isoformat(),
            'regressions': regressions,
            'summary': {
                'total_regressions': len(regressions),
                'has_regression': len(regressions) > 0
            }
        }
        
        logger.info("Performance regression check requested",
                   regression_count=len(regressions))
        return jsonify(response)
        
    except Exception as e:
        logger.error("Failed to check performance regression", error=str(e))
        return jsonify({'error': 'Failed to check regression'}), 500


@performance_bp.route('/health', methods=['GET'])
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for performance monitoring system.
    
    Returns:
        JSON response with system health status
    """
    try:
        if not performance_monitor:
            return jsonify({'status': 'unhealthy', 'error': 'Performance monitor not initialized'}), 500
        
        # Get metrics summary
        summary = performance_monitor.get_metrics_summary()
        
        # Check if system is healthy
        is_healthy = (
            summary.get('error_rate_percent', 0) < 5.0 and
            summary.get('throughput_rps', 0) > 0
        )
        
        response = {
            'status': 'healthy' if is_healthy else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'summary': summary
        }
        
        logger.info("Performance monitoring health check",
                   status=response['status'])
        return jsonify(response)
        
    except Exception as e:
        logger.error("Failed to perform health check", error=str(e))
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


def _generate_summary_report(current_metrics: Dict[str, Any], 
                           historical_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate summary performance report."""
    return {
        'report_type': 'summary',
        'timestamp': datetime.now().isoformat(),
        'current_metrics': current_metrics,
        'historical_summary': {
            'data_points': len(historical_metrics),
            'time_span_hours': 24  # Default time span
        }
    }


def _generate_detailed_report(current_metrics: Dict[str, Any],
                             historical_metrics: List[Dict[str, Any]],
                             analyzer: PerformanceAnalyzer) -> Dict[str, Any]:
    """Generate detailed performance report."""
    # Analyze bottlenecks
    bottlenecks = analyzer.identify_bottlenecks(current_metrics)
    
    # Analyze trends
    trends = analyzer.analyze_performance_trends(historical_metrics)
    
    return {
        'report_type': 'detailed',
        'timestamp': datetime.now().isoformat(),
        'current_metrics': current_metrics,
        'bottlenecks': [
            {
                'component': b.component,
                'metric': b.metric,
                'severity': b.severity,
                'description': b.description,
                'recommendation': b.recommendation
            }
            for b in bottlenecks
        ],
        'trends': [
            {
                'metric': t.metric,
                'direction': t.trend_direction,
                'change_percent': t.change_percent,
                'confidence': t.confidence
            }
            for t in trends
        ],
        'summary': {
            'bottleneck_count': len(bottlenecks),
            'trend_count': len(trends),
            'critical_bottlenecks': len([b for b in bottlenecks if b.severity == 'critical'])
        }
    }


def _generate_trends_report(historical_metrics: List[Dict[str, Any]],
                           analyzer: PerformanceAnalyzer) -> Dict[str, Any]:
    """Generate trends-focused performance report."""
    trends = analyzer.analyze_performance_trends(historical_metrics)
    
    return {
        'report_type': 'trends',
        'timestamp': datetime.now().isoformat(),
        'trends': [
            {
                'metric': t.metric,
                'direction': t.trend_direction,
                'change_percent': t.change_percent,
                'confidence': t.confidence,
                'time_period': t.time_period
            }
            for t in trends
        ],
        'summary': {
            'total_trends': len(trends),
            'improving_trends': len([t for t in trends if t.trend_direction == 'improving']),
            'degrading_trends': len([t for t in trends if t.trend_direction == 'degrading']),
            'stable_trends': len([t for t in trends if t.trend_direction == 'stable'])
        }
    }
