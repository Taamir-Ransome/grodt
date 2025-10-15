"""
Performance alerting service for GRODT trading system.

This module provides comprehensive performance alerting capabilities including
degradation alerts, resource threshold alerts, regression detection, and anomaly detection.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import json
from pathlib import Path

from .performance_monitor import PerformanceMonitor
from .performance_analyzer import PerformanceAnalyzer
from .performance_trend_service import PerformanceTrendService
from .alerting_service import AlertingService, Alert, AlertSeverity, AlertCategory


class AlertType(Enum):
    """Types of performance alerts."""
    PERFORMANCE_DEGRADATION = "performance_degradation"
    RESOURCE_THRESHOLD = "resource_threshold"
    PERFORMANCE_REGRESSION = "performance_regression"
    PERFORMANCE_ANOMALY = "performance_anomaly"
    BOTTLENECK_DETECTED = "bottleneck_detected"
    TREND_ANOMALY = "trend_anomaly"


@dataclass
class PerformanceAlertRule:
    """Performance alert rule configuration."""
    rule_id: str
    name: str
    description: str
    alert_type: AlertType
    metric_name: str
    component: str
    threshold_value: float
    comparison_operator: str  # '>', '<', '>=', '<=', '==', '!='
    severity: AlertSeverity
    enabled: bool = True
    cooldown_minutes: int = 15
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0


@dataclass
class PerformanceAlert:
    """Performance alert instance."""
    alert_id: str
    rule_id: str
    timestamp: datetime
    metric_name: str
    component: str
    current_value: float
    threshold_value: float
    severity: AlertSeverity
    message: str
    details: Dict[str, Any]


class PerformanceAlertingService:
    """
    Performance alerting service for GRODT trading system.
    
    Provides comprehensive performance alerting including degradation alerts,
    resource threshold alerts, regression detection, and anomaly detection.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize performance alerting service.
        
        Args:
            config: Configuration dictionary with alerting settings
        """
        self.config = config or {}
        self.logger = structlog.get_logger(__name__)
        
        # Alerting settings
        self.enabled = self.config.get('enabled', True)
        self.default_cooldown_minutes = self.config.get('default_cooldown_minutes', 15)
        self.max_alerts_per_hour = self.config.get('max_alerts_per_hour', 100)
        
        # Alert rules storage
        self.alert_rules: Dict[str, PerformanceAlertRule] = {}
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        
        # Alerting service integration
        self.alerting_service: Optional[AlertingService] = None
        
        # Performance monitoring components
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.performance_analyzer: Optional[PerformanceAnalyzer] = None
        self.trend_service: Optional[PerformanceTrendService] = None
        
        # Alert statistics
        self.alert_stats = {
            'total_alerts': 0,
            'alerts_by_type': {},
            'alerts_by_severity': {},
            'alerts_last_hour': 0
        }
        
        self.logger.info("Performance alerting service initialized",
                        enabled=self.enabled)
    
    def set_alerting_service(self, alerting_service: AlertingService) -> None:
        """Set the alerting service for sending alerts."""
        self.alerting_service = alerting_service
        self.logger.info("Alerting service configured")
    
    def set_performance_components(self, monitor: PerformanceMonitor, 
                                 analyzer: PerformanceAnalyzer,
                                 trend_service: PerformanceTrendService) -> None:
        """Set performance monitoring components."""
        self.performance_monitor = monitor
        self.performance_analyzer = analyzer
        self.trend_service = trend_service
        self.logger.info("Performance components configured")
    
    def add_alert_rule(self, rule: PerformanceAlertRule) -> None:
        """
        Add a performance alert rule.
        
        Args:
            rule: Performance alert rule to add
        """
        self.alert_rules[rule.rule_id] = rule
        self.logger.info("Alert rule added",
                        rule_id=rule.rule_id,
                        name=rule.name,
                        alert_type=rule.alert_type.value)
    
    def remove_alert_rule(self, rule_id: str) -> bool:
        """
        Remove a performance alert rule.
        
        Args:
            rule_id: ID of the rule to remove
            
        Returns:
            True if rule was removed, False if not found
        """
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            self.logger.info("Alert rule removed", rule_id=rule_id)
            return True
        return False
    
    def update_alert_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a performance alert rule.
        
        Args:
            rule_id: ID of the rule to update
            updates: Dictionary of updates to apply
            
        Returns:
            True if rule was updated, False if not found
        """
        if rule_id not in self.alert_rules:
            return False
        
        rule = self.alert_rules[rule_id]
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        self.logger.info("Alert rule updated", rule_id=rule_id, updates=updates)
        return True
    
    async def check_performance_alerts(self) -> List[PerformanceAlert]:
        """
        Check all performance alert rules and generate alerts.
        
        Returns:
            List of generated performance alerts
        """
        if not self.enabled or not self.performance_monitor:
            return []
        
        try:
            generated_alerts = []
            
            # Collect current performance metrics
            current_metrics = await self.performance_monitor.collect_all_metrics()
            
            # Check each alert rule
            for rule_id, rule in self.alert_rules.items():
                if not rule.enabled:
                    continue
                
                # Check cooldown
                if self._is_rule_in_cooldown(rule):
                    continue
                
                # Check rule conditions
                alert = await self._check_rule_condition(rule, current_metrics)
                if alert:
                    generated_alerts.append(alert)
                    rule.last_triggered = datetime.now()
                    rule.trigger_count += 1
            
            # Send alerts if alerting service is available
            if self.alerting_service and generated_alerts:
                await self._send_alerts(generated_alerts)
            
            # Update statistics
            self._update_alert_statistics(generated_alerts)
            
            self.logger.info("Performance alerts checked",
                           rules_checked=len(self.alert_rules),
                           alerts_generated=len(generated_alerts))
            
            return generated_alerts
            
        except Exception as e:
            self.logger.error("Failed to check performance alerts", error=str(e))
            return []
    
    def _is_rule_in_cooldown(self, rule: PerformanceAlertRule) -> bool:
        """Check if a rule is in cooldown period."""
        if not rule.last_triggered:
            return False
        
        cooldown_duration = timedelta(minutes=rule.cooldown_minutes)
        return datetime.now() - rule.last_triggered < cooldown_duration
    
    async def _check_rule_condition(self, rule: PerformanceAlertRule, 
                                  metrics: Dict[str, Any]) -> Optional[PerformanceAlert]:
        """Check if a rule condition is met."""
        try:
            # Get metric value
            metric_value = self._get_metric_value(metrics, rule.metric_name, rule.component)
            if metric_value is None:
                return None
            
            # Check threshold condition
            if not self._evaluate_condition(metric_value, rule.threshold_value, rule.comparison_operator):
                return None
            
            # Generate alert
            alert = PerformanceAlert(
                alert_id=f"perf_{rule.rule_id}_{datetime.now().timestamp()}",
                rule_id=rule.rule_id,
                timestamp=datetime.now(),
                metric_name=rule.metric_name,
                component=rule.component,
                current_value=metric_value,
                threshold_value=rule.threshold_value,
                severity=rule.severity,
                message=self._generate_alert_message(rule, metric_value),
                details={
                    'rule_name': rule.name,
                    'rule_description': rule.description,
                    'alert_type': rule.alert_type.value,
                    'comparison_operator': rule.comparison_operator
                }
            )
            
            return alert
            
        except Exception as e:
            self.logger.error("Failed to check rule condition",
                            rule_id=rule.rule_id,
                            error=str(e))
            return None
    
    def _get_metric_value(self, metrics: Dict[str, Any], metric_name: str, component: str) -> Optional[float]:
        """Get metric value from metrics dictionary."""
        try:
            if component in metrics and metric_name in metrics[component]:
                value = metrics[component][metric_name]
                if isinstance(value, (int, float)):
                    return float(value)
            return None
        except Exception:
            return None
    
    def _evaluate_condition(self, current_value: float, threshold_value: float, operator: str) -> bool:
        """Evaluate threshold condition."""
        try:
            if operator == '>':
                return current_value > threshold_value
            elif operator == '<':
                return current_value < threshold_value
            elif operator == '>=':
                return current_value >= threshold_value
            elif operator == '<=':
                return current_value <= threshold_value
            elif operator == '==':
                return abs(current_value - threshold_value) < 0.001  # Float comparison
            elif operator == '!=':
                return abs(current_value - threshold_value) >= 0.001
            else:
                return False
        except Exception:
            return False
    
    def _generate_alert_message(self, rule: PerformanceAlertRule, current_value: float) -> str:
        """Generate alert message."""
        return (f"Performance alert: {rule.name}\n"
                f"Metric: {rule.metric_name} ({rule.component})\n"
                f"Current value: {current_value:.2f}\n"
                f"Threshold: {rule.threshold_value:.2f}\n"
                f"Condition: {current_value:.2f} {rule.comparison_operator} {rule.threshold_value:.2f}")
    
    async def _send_alerts(self, alerts: List[PerformanceAlert]) -> None:
        """Send alerts through the alerting service."""
        if not self.alerting_service:
            return
        
        try:
            for alert in alerts:
                # Convert to standard alert format
                standard_alert = Alert(
                    alert_id=alert.alert_id,
                    title=f"Performance Alert: {alert.metric_name}",
                    message=alert.message,
                    severity=alert.severity,
                    category=AlertCategory.PERFORMANCE,
                    source="performance_monitoring",
                    timestamp=alert.timestamp,
                    metadata=alert.details
                )
                
                await self.alerting_service.send_alert(standard_alert)
                
                # Store active alert
                self.active_alerts[alert.alert_id] = alert
            
            self.logger.info("Performance alerts sent", alert_count=len(alerts))
            
        except Exception as e:
            self.logger.error("Failed to send performance alerts", error=str(e))
    
    def _update_alert_statistics(self, alerts: List[PerformanceAlert]) -> None:
        """Update alert statistics."""
        self.alert_stats['total_alerts'] += len(alerts)
        
        for alert in alerts:
            # Count by type
            alert_type = alert.details.get('alert_type', 'unknown')
            if alert_type not in self.alert_stats['alerts_by_type']:
                self.alert_stats['alerts_by_type'][alert_type] = 0
            self.alert_stats['alerts_by_type'][alert_type] += 1
            
            # Count by severity
            severity = alert.severity.value
            if severity not in self.alert_stats['alerts_by_severity']:
                self.alert_stats['alerts_by_severity'][severity] = 0
            self.alert_stats['alerts_by_severity'][severity] += 1
        
        # Update hourly count
        self.alert_stats['alerts_last_hour'] += len(alerts)
    
    async def check_regression_alerts(self) -> List[PerformanceAlert]:
        """
        Check for performance regression alerts.
        
        Returns:
            List of regression alerts
        """
        if not self.trend_service or not self.performance_analyzer:
            return []
        
        try:
            # Get current regressions
            regressions = await self.trend_service.detect_regressions(self.performance_analyzer)
            
            alerts = []
            for regression in regressions:
                alert = PerformanceAlert(
                    alert_id=f"regression_{datetime.now().timestamp()}",
                    rule_id="regression_detection",
                    timestamp=datetime.now(),
                    metric_name=regression,
                    component="system",
                    current_value=0.0,  # Will be filled by regression details
                    threshold_value=0.0,
                    severity=AlertSeverity.HIGH,
                    message=f"Performance regression detected: {regression}",
                    details={
                        'alert_type': AlertType.PERFORMANCE_REGRESSION.value,
                        'regression_metric': regression
                    }
                )
                alerts.append(alert)
            
            return alerts
            
        except Exception as e:
            self.logger.error("Failed to check regression alerts", error=str(e))
            return []
    
    async def check_anomaly_alerts(self) -> List[PerformanceAlert]:
        """
        Check for performance anomaly alerts.
        
        Returns:
            List of anomaly alerts
        """
        if not self.performance_analyzer or not self.performance_monitor:
            return []
        
        try:
            # Collect current metrics
            current_metrics = await self.performance_monitor.collect_all_metrics()
            
            # Check for anomalies
            anomalies = []
            for component, metrics in current_metrics.items():
                for metric_name, value in metrics.items():
                    if isinstance(value, (int, float)):
                        # Simple anomaly detection (can be enhanced)
                        if self._is_anomaly(metric_name, value):
                            anomalies.append({
                                'metric_name': metric_name,
                                'component': component,
                                'value': value
                            })
            
            alerts = []
            for anomaly in anomalies:
                alert = PerformanceAlert(
                    alert_id=f"anomaly_{datetime.now().timestamp()}",
                    rule_id="anomaly_detection",
                    timestamp=datetime.now(),
                    metric_name=anomaly['metric_name'],
                    component=anomaly['component'],
                    current_value=anomaly['value'],
                    threshold_value=0.0,
                    severity=AlertSeverity.MEDIUM,
                    message=f"Performance anomaly detected: {anomaly['metric_name']} = {anomaly['value']}",
                    details={
                        'alert_type': AlertType.PERFORMANCE_ANOMALY.value,
                        'anomaly_value': anomaly['value']
                    }
                )
                alerts.append(alert)
            
            return alerts
            
        except Exception as e:
            self.logger.error("Failed to check anomaly alerts", error=str(e))
            return []
    
    def _is_anomaly(self, metric_name: str, value: float) -> bool:
        """Simple anomaly detection (can be enhanced with ML models)."""
        # Example anomaly detection logic
        if 'cpu_percent' in metric_name and value > 95:
            return True
        elif 'memory_percent' in metric_name and value > 95:
            return True
        elif 'response_time' in metric_name and value > 5000:  # 5 seconds
            return True
        elif 'query_time' in metric_name and value > 1000:  # 1 second
            return True
        
        return False
    
    async def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        return {
            'total_alerts': self.alert_stats['total_alerts'],
            'alerts_by_type': self.alert_stats['alerts_by_type'],
            'alerts_by_severity': self.alert_stats['alerts_by_severity'],
            'alerts_last_hour': self.alert_stats['alerts_last_hour'],
            'active_alerts': len(self.active_alerts),
            'alert_rules': len(self.alert_rules),
            'enabled_rules': len([r for r in self.alert_rules.values() if r.enabled])
        }
    
    async def clear_alert_statistics(self) -> None:
        """Clear alert statistics."""
        self.alert_stats = {
            'total_alerts': 0,
            'alerts_by_type': {},
            'alerts_by_severity': {},
            'alerts_last_hour': 0
        }
        self.active_alerts.clear()
        self.logger.info("Alert statistics cleared")
    
    async def export_alert_rules(self, file_path: str) -> bool:
        """Export alert rules to file."""
        try:
            export_data = {
                'alert_rules': [
                    {
                        'rule_id': rule.rule_id,
                        'name': rule.name,
                        'description': rule.description,
                        'alert_type': rule.alert_type.value,
                        'metric_name': rule.metric_name,
                        'component': rule.component,
                        'threshold_value': rule.threshold_value,
                        'comparison_operator': rule.comparison_operator,
                        'severity': rule.severity.value,
                        'enabled': rule.enabled,
                        'cooldown_minutes': rule.cooldown_minutes
                    }
                    for rule in self.alert_rules.values()
                ]
            }
            
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info("Alert rules exported", file_path=file_path)
            return True
            
        except Exception as e:
            self.logger.error("Failed to export alert rules", error=str(e))
            return False
    
    async def import_alert_rules(self, file_path: str) -> bool:
        """Import alert rules from file."""
        try:
            with open(file_path, 'r') as f:
                import_data = json.load(f)
            
            imported_count = 0
            for rule_data in import_data.get('alert_rules', []):
                rule = PerformanceAlertRule(
                    rule_id=rule_data['rule_id'],
                    name=rule_data['name'],
                    description=rule_data['description'],
                    alert_type=AlertType(rule_data['alert_type']),
                    metric_name=rule_data['metric_name'],
                    component=rule_data['component'],
                    threshold_value=rule_data['threshold_value'],
                    comparison_operator=rule_data['comparison_operator'],
                    severity=AlertSeverity(rule_data['severity']),
                    enabled=rule_data.get('enabled', True),
                    cooldown_minutes=rule_data.get('cooldown_minutes', 15)
                )
                
                self.alert_rules[rule.rule_id] = rule
                imported_count += 1
            
            self.logger.info("Alert rules imported", file_path=file_path, count=imported_count)
            return True
            
        except Exception as e:
            self.logger.error("Failed to import alert rules", error=str(e))
            return False
