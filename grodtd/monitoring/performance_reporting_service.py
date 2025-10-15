"""
Performance reporting service for GRODT trading system.

This module provides comprehensive performance reporting capabilities including
report generation, dashboard integration, data export, and analysis recommendations.
"""

import asyncio
import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import structlog
from jinja2 import Template

from .performance_monitor import PerformanceMonitor
from .performance_analyzer import PerformanceAnalyzer
from .performance_trend_service import PerformanceTrendService
from .performance_alerting_service import PerformanceAlertingService


@dataclass
class PerformanceReport:
    """Performance report data structure."""
    report_id: str
    title: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    summary: Dict[str, Any]
    metrics: Dict[str, Any]
    trends: List[Dict[str, Any]]
    bottlenecks: List[Dict[str, Any]]
    recommendations: List[str]
    alerts: List[Dict[str, Any]]


@dataclass
class ReportSection:
    """Report section data structure."""
    title: str
    content: str
    charts: List[Dict[str, Any]]
    metrics: Dict[str, Any]


class PerformanceReportingService:
    """
    Performance reporting service for GRODT trading system.
    
    Provides comprehensive performance reporting including report generation,
    dashboard integration, data export, and analysis recommendations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize performance reporting service.
        
        Args:
            config: Configuration dictionary with reporting settings
        """
        self.config = config or {}
        self.logger = structlog.get_logger(__name__)
        
        # Reporting settings
        self.enabled = self.config.get('enabled', True)
        self.report_formats = self.config.get('formats', ['json', 'html', 'csv'])
        self.output_directory = Path(self.config.get('output_directory', 'reports/performance'))
        self.template_directory = Path(self.config.get('template_directory', 'templates/performance'))
        
        # Report generation settings
        self.default_period_hours = self.config.get('default_period_hours', 24)
        self.include_charts = self.config.get('include_charts', True)
        self.include_recommendations = self.config.get('include_recommendations', True)
        
        # Performance monitoring components
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.performance_analyzer: Optional[PerformanceAnalyzer] = None
        self.trend_service: Optional[PerformanceTrendService] = None
        self.alerting_service: Optional[PerformanceAlertingService] = None
        
        # Report templates
        self.html_template = self._load_html_template()
        
        # Create output directory
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("Performance reporting service initialized",
                        enabled=self.enabled,
                        output_directory=str(self.output_directory))
    
    def set_performance_components(self, monitor: PerformanceMonitor,
                                 analyzer: PerformanceAnalyzer,
                                 trend_service: PerformanceTrendService,
                                 alerting_service: PerformanceAlertingService) -> None:
        """Set performance monitoring components."""
        self.performance_monitor = monitor
        self.performance_analyzer = analyzer
        self.trend_service = trend_service
        self.alerting_service = alerting_service
        self.logger.info("Performance components configured")
    
    def _load_html_template(self) -> Template:
        """Load HTML report template."""
        template_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report.title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f4f4f4; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .metric { display: inline-block; margin: 10px; padding: 10px; background-color: #f9f9f9; border-radius: 3px; }
        .alert { padding: 10px; margin: 5px 0; border-radius: 3px; }
        .alert-high { background-color: #ffebee; border-left: 4px solid #f44336; }
        .alert-medium { background-color: #fff3e0; border-left: 4px solid #ff9800; }
        .alert-low { background-color: #e8f5e8; border-left: 4px solid #4caf50; }
        .recommendation { padding: 10px; margin: 5px 0; background-color: #e3f2fd; border-left: 4px solid #2196f3; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ report.title }}</h1>
        <p>Generated: {{ report.generated_at.strftime('%Y-%m-%d %H:%M:%S') }}</p>
        <p>Period: {{ report.period_start.strftime('%Y-%m-%d %H:%M') }} - {{ report.period_end.strftime('%Y-%m-%d %H:%M') }}</p>
    </div>
    
    <div class="section">
        <h2>Summary</h2>
        <div class="metric">
            <strong>Total Alerts:</strong> {{ report.summary.total_alerts }}
        </div>
        <div class="metric">
            <strong>Critical Issues:</strong> {{ report.summary.critical_issues }}
        </div>
        <div class="metric">
            <strong>Performance Score:</strong> {{ report.summary.performance_score }}/100
        </div>
    </div>
    
    <div class="section">
        <h2>Key Metrics</h2>
        <table>
            <tr><th>Metric</th><th>Current Value</th><th>Threshold</th><th>Status</th></tr>
            {% for metric, data in report.metrics.items() %}
            <tr>
                <td>{{ metric }}</td>
                <td>{{ data.value }}</td>
                <td>{{ data.threshold }}</td>
                <td style="color: {{ 'red' if data.status == 'critical' else 'orange' if data.status == 'warning' else 'green' }}">
                    {{ data.status }}
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    
    <div class="section">
        <h2>Performance Trends</h2>
        {% for trend in report.trends %}
        <div class="metric">
            <strong>{{ trend.metric }}:</strong> {{ trend.direction }} ({{ trend.change_percent }}%)
        </div>
        {% endfor %}
    </div>
    
    <div class="section">
        <h2>Bottlenecks</h2>
        {% for bottleneck in report.bottlenecks %}
        <div class="alert alert-{{ 'high' if bottleneck.severity == 'high' else 'medium' if bottleneck.severity == 'medium' else 'low' }}">
            <strong>{{ bottleneck.component }}:</strong> {{ bottleneck.description }}
        </div>
        {% endfor %}
    </div>
    
    <div class="section">
        <h2>Recommendations</h2>
        {% for recommendation in report.recommendations %}
        <div class="recommendation">{{ recommendation }}</div>
        {% endfor %}
    </div>
    
    <div class="section">
        <h2>Recent Alerts</h2>
        {% for alert in report.alerts %}
        <div class="alert alert-{{ 'high' if alert.severity == 'high' else 'medium' if alert.severity == 'medium' else 'low' }}">
            <strong>{{ alert.timestamp }}:</strong> {{ alert.message }}
        </div>
        {% endfor %}
    </div>
</body>
</html>
        """
        return Template(template_content)
    
    async def generate_performance_report(self, period_hours: Optional[int] = None) -> PerformanceReport:
        """
        Generate a comprehensive performance report.
        
        Args:
            period_hours: Number of hours to include in the report
            
        Returns:
            Performance report object
        """
        if not self.enabled:
            raise RuntimeError("Performance reporting is disabled")
        
        try:
            period_hours = period_hours or self.default_period_hours
            period_end = datetime.now()
            period_start = period_end - timedelta(hours=period_hours)
            
            # Generate report ID
            report_id = f"perf_report_{period_end.strftime('%Y%m%d_%H%M%S')}"
            
            # Collect data
            summary = await self._generate_report_summary(period_start, period_end)
            metrics = await self._collect_metrics_data()
            trends = await self._analyze_trends()
            bottlenecks = await self._identify_bottlenecks()
            recommendations = await self._generate_recommendations()
            alerts = await self._collect_recent_alerts(period_start, period_end)
            
            # Create report
            report = PerformanceReport(
                report_id=report_id,
                title=f"Performance Report - {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}",
                generated_at=period_end,
                period_start=period_start,
                period_end=period_end,
                summary=summary,
                metrics=metrics,
                trends=trends,
                bottlenecks=bottlenecks,
                recommendations=recommendations,
                alerts=alerts
            )
            
            self.logger.info("Performance report generated",
                           report_id=report_id,
                           period_hours=period_hours)
            
            return report
            
        except Exception as e:
            self.logger.error("Failed to generate performance report", error=str(e))
            raise
    
    async def _generate_report_summary(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Generate report summary."""
        try:
            # Get alert statistics
            alert_stats = {}
            if self.alerting_service:
                alert_stats = await self.alerting_service.get_alert_statistics()
            
            # Calculate performance score
            performance_score = self._calculate_performance_score()
            
            summary = {
                'total_alerts': alert_stats.get('total_alerts', 0),
                'critical_issues': alert_stats.get('alerts_by_severity', {}).get('high', 0),
                'performance_score': performance_score,
                'period_hours': (period_end - period_start).total_seconds() / 3600,
                'data_points': len(self.trend_service.trend_data) if self.trend_service else 0
            }
            
            return summary
            
        except Exception as e:
            self.logger.error("Failed to generate report summary", error=str(e))
            return {}
    
    def _calculate_performance_score(self) -> int:
        """Calculate overall performance score (0-100)."""
        try:
            score = 100
            
            # Deduct points for high resource usage
            if self.performance_monitor:
                current_metrics = asyncio.run(self.performance_monitor.collect_all_metrics())
                
                # CPU usage
                if 'system' in current_metrics and 'cpu_percent' in current_metrics['system']:
                    cpu_usage = current_metrics['system']['cpu_percent']
                    if cpu_usage > 90:
                        score -= 20
                    elif cpu_usage > 80:
                        score -= 10
                
                # Memory usage
                if 'system' in current_metrics and 'memory_percent' in current_metrics['system']:
                    memory_usage = current_metrics['system']['memory_percent']
                    if memory_usage > 90:
                        score -= 20
                    elif memory_usage > 80:
                        score -= 10
                
                # Response time
                if 'application' in current_metrics and 'response_time_ms' in current_metrics['application']:
                    response_time = current_metrics['application']['response_time_ms']
                    if response_time > 5000:
                        score -= 15
                    elif response_time > 2000:
                        score -= 10
            
            return max(0, min(100, score))
            
        except Exception as e:
            self.logger.error("Failed to calculate performance score", error=str(e))
            return 50  # Default score
    
    async def _collect_metrics_data(self) -> Dict[str, Any]:
        """Collect current metrics data."""
        try:
            if not self.performance_monitor:
                return {}
            
            current_metrics = await self.performance_monitor.collect_all_metrics()
            
            # Format metrics for report
            formatted_metrics = {}
            
            # System metrics
            if 'system' in current_metrics:
                for metric_name, value in current_metrics['system'].items():
                    formatted_metrics[f"system.{metric_name}"] = {
                        'value': f"{value:.2f}",
                        'threshold': self._get_threshold_for_metric(metric_name),
                        'status': self._get_metric_status(metric_name, value)
                    }
            
            # Application metrics
            if 'application' in current_metrics:
                for metric_name, value in current_metrics['application'].items():
                    formatted_metrics[f"application.{metric_name}"] = {
                        'value': f"{value:.2f}",
                        'threshold': self._get_threshold_for_metric(metric_name),
                        'status': self._get_metric_status(metric_name, value)
                    }
            
            return formatted_metrics
            
        except Exception as e:
            self.logger.error("Failed to collect metrics data", error=str(e))
            return {}
    
    def _get_threshold_for_metric(self, metric_name: str) -> str:
        """Get threshold for a metric."""
        thresholds = {
            'cpu_percent': '85%',
            'memory_percent': '85%',
            'disk_percent': '90%',
            'response_time_ms': '2000ms',
            'query_time_ms': '500ms'
        }
        return thresholds.get(metric_name, 'N/A')
    
    def _get_metric_status(self, metric_name: str, value: float) -> str:
        """Get status for a metric value."""
        if 'cpu_percent' in metric_name:
            if value > 95:
                return 'critical'
            elif value > 85:
                return 'warning'
            else:
                return 'good'
        elif 'memory_percent' in metric_name:
            if value > 95:
                return 'critical'
            elif value > 85:
                return 'warning'
            else:
                return 'good'
        elif 'response_time' in metric_name:
            if value > 5000:
                return 'critical'
            elif value > 2000:
                return 'warning'
            else:
                return 'good'
        else:
            return 'unknown'
    
    async def _analyze_trends(self) -> List[Dict[str, Any]]:
        """Analyze performance trends."""
        try:
            if not self.trend_service or not self.performance_analyzer:
                return []
            
            # Get trend analysis
            trends = await self.trend_service.analyze_trends(self.performance_analyzer)
            
            # Format trends for report
            formatted_trends = []
            for trend in trends:
                formatted_trends.append({
                    'metric': trend.metric_name,
                    'direction': trend.trend_direction,
                    'change_percent': f"{trend.change_percent:.1f}%",
                    'confidence': f"{trend.confidence:.2f}",
                    'strength': trend.trend_strength
                })
            
            return formatted_trends
            
        except Exception as e:
            self.logger.error("Failed to analyze trends", error=str(e))
            return []
    
    async def _identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks."""
        try:
            if not self.performance_analyzer or not self.performance_monitor:
                return []
            
            # Get current metrics
            current_metrics = await self.performance_monitor.collect_all_metrics()
            
            # Identify bottlenecks
            bottlenecks = self.performance_analyzer.identify_bottlenecks(current_metrics)
            
            # Format bottlenecks for report
            formatted_bottlenecks = []
            for bottleneck in bottlenecks:
                formatted_bottlenecks.append({
                    'component': bottleneck.component,
                    'description': bottleneck.description,
                    'severity': bottleneck.severity,
                    'recommendation': bottleneck.recommendation
                })
            
            return formatted_bottlenecks
            
        except Exception as e:
            self.logger.error("Failed to identify bottlenecks", error=str(e))
            return []
    
    async def _generate_recommendations(self) -> List[str]:
        """Generate performance recommendations."""
        try:
            recommendations = []
            
            # Get current metrics
            if self.performance_monitor:
                current_metrics = await self.performance_monitor.collect_all_metrics()
                
                # CPU recommendations
                if 'system' in current_metrics and 'cpu_percent' in current_metrics['system']:
                    cpu_usage = current_metrics['system']['cpu_percent']
                    if cpu_usage > 80:
                        recommendations.append("Consider optimizing CPU-intensive processes or scaling resources")
                
                # Memory recommendations
                if 'system' in current_metrics and 'memory_percent' in current_metrics['system']:
                    memory_usage = current_metrics['system']['memory_percent']
                    if memory_usage > 80:
                        recommendations.append("Consider increasing memory allocation or optimizing memory usage")
                
                # Response time recommendations
                if 'application' in current_metrics and 'response_time_ms' in current_metrics['application']:
                    response_time = current_metrics['application']['response_time_ms']
                    if response_time > 2000:
                        recommendations.append("Consider optimizing application code or database queries")
            
            # Add general recommendations
            recommendations.extend([
                "Monitor performance trends regularly to identify issues early",
                "Set up automated alerts for critical performance thresholds",
                "Consider implementing performance testing in CI/CD pipeline",
                "Review and optimize database queries regularly"
            ])
            
            return recommendations
            
        except Exception as e:
            self.logger.error("Failed to generate recommendations", error=str(e))
            return []
    
    async def _collect_recent_alerts(self, period_start: datetime, period_end: datetime) -> List[Dict[str, Any]]:
        """Collect recent alerts."""
        try:
            if not self.alerting_service:
                return []
            
            # Get alert statistics
            alert_stats = await self.alerting_service.get_alert_statistics()
            
            # Format alerts for report
            alerts = []
            for severity, count in alert_stats.get('alerts_by_severity', {}).items():
                if count > 0:
                    alerts.append({
                        'timestamp': period_end.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': f"{count} {severity} severity alerts",
                        'severity': severity
                    })
            
            return alerts
            
        except Exception as e:
            self.logger.error("Failed to collect recent alerts", error=str(e))
            return []
    
    async def export_report(self, report: PerformanceReport, format: str = 'json') -> str:
        """
        Export performance report to file.
        
        Args:
            report: Performance report to export
            format: Export format ('json', 'html', 'csv')
            
        Returns:
            Path to exported file
        """
        try:
            if format not in self.report_formats:
                raise ValueError(f"Unsupported format: {format}")
            
            # Generate filename
            filename = f"{report.report_id}.{format}"
            file_path = self.output_directory / filename
            
            if format == 'json':
                await self._export_json_report(report, file_path)
            elif format == 'html':
                await self._export_html_report(report, file_path)
            elif format == 'csv':
                await self._export_csv_report(report, file_path)
            
            self.logger.info("Report exported", file_path=str(file_path), format=format)
            return str(file_path)
            
        except Exception as e:
            self.logger.error("Failed to export report", error=str(e), format=format)
            raise
    
    async def _export_json_report(self, report: PerformanceReport, file_path: Path) -> None:
        """Export report as JSON."""
        report_data = {
            'report_id': report.report_id,
            'title': report.title,
            'generated_at': report.generated_at.isoformat(),
            'period_start': report.period_start.isoformat(),
            'period_end': report.period_end.isoformat(),
            'summary': report.summary,
            'metrics': report.metrics,
            'trends': report.trends,
            'bottlenecks': report.bottlenecks,
            'recommendations': report.recommendations,
            'alerts': report.alerts
        }
        
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2)
    
    async def _export_html_report(self, report: PerformanceReport, file_path: Path) -> None:
        """Export report as HTML."""
        html_content = self.html_template.render(report=report)
        
        with open(file_path, 'w') as f:
            f.write(html_content)
    
    async def _export_csv_report(self, report: PerformanceReport, file_path: Path) -> None:
        """Export report as CSV."""
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write summary
            writer.writerow(['Section', 'Metric', 'Value'])
            writer.writerow(['Summary', 'Total Alerts', report.summary.get('total_alerts', 0)])
            writer.writerow(['Summary', 'Critical Issues', report.summary.get('critical_issues', 0)])
            writer.writerow(['Summary', 'Performance Score', report.summary.get('performance_score', 0)])
            
            # Write metrics
            for metric, data in report.metrics.items():
                writer.writerow(['Metrics', metric, data['value']])
            
            # Write trends
            for trend in report.trends:
                writer.writerow(['Trends', trend['metric'], f"{trend['direction']} ({trend['change_percent']})"])
            
            # Write bottlenecks
            for bottleneck in report.bottlenecks:
                writer.writerow(['Bottlenecks', bottleneck['component'], bottleneck['description']])
    
    async def generate_dashboard_data(self) -> Dict[str, Any]:
        """Generate data for dashboard integration."""
        try:
            if not self.performance_monitor:
                return {}
            
            # Get current metrics
            current_metrics = await self.performance_monitor.collect_all_metrics()
            
            # Get trend data
            trend_summary = {}
            if self.trend_service:
                trend_summary = await self.trend_service.get_trend_summary()
            
            # Get alert statistics
            alert_stats = {}
            if self.alerting_service:
                alert_stats = await self.alerting_service.get_alert_statistics()
            
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'current_metrics': current_metrics,
                'trend_summary': trend_summary,
                'alert_statistics': alert_stats,
                'performance_score': self._calculate_performance_score()
            }
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error("Failed to generate dashboard data", error=str(e))
            return {}
    
    async def schedule_periodic_reports(self, interval_hours: int = 24) -> None:
        """Schedule periodic report generation."""
        try:
            while True:
                # Generate report
                report = await self.generate_performance_report(interval_hours)
                
                # Export in all formats
                for format in self.report_formats:
                    await self.export_report(report, format)
                
                # Wait for next interval
                await asyncio.sleep(interval_hours * 3600)
                
        except Exception as e:
            self.logger.error("Failed to generate periodic report", error=str(e))
    
    async def cleanup_old_reports(self, days_to_keep: int = 30) -> None:
        """Clean up old report files."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            deleted_count = 0
            for file_path in self.output_directory.glob('*'):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
            
            self.logger.info("Old reports cleaned up", deleted_count=deleted_count, days_to_keep=days_to_keep)
            
        except Exception as e:
            self.logger.error("Failed to cleanup old reports", error=str(e))
