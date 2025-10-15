"""
Alerting service for GRODT trading system.

Provides comprehensive alerting capabilities including:
- Prometheus alert rule evaluation
- Alert severity levels and escalation
- Alert acknowledgment and resolution tracking
- Integration with notification channels
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from prometheus_client import Gauge, Counter, Histogram, CollectorRegistry

import structlog

logger = structlog.get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status states."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    description: str
    severity: AlertSeverity
    metric_name: str
    threshold: float
    operator: str  # 'gt', 'lt', 'eq', 'gte', 'lte'
    duration: int  # seconds
    labels: Dict[str, str]
    notification_channels: List[str]


@dataclass
class Alert:
    """Alert instance."""
    id: str
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    value: float
    threshold: float
    labels: Dict[str, str]
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None


class AlertingService:
    """
    Core alerting service for the GRODT system.
    
    Handles alert rule evaluation, alert lifecycle management,
    and integration with notification channels.
    """
    
    def __init__(self, db_path: str, notification_channels: Dict[str, Any], registry: Optional[CollectorRegistry] = None):
        """
        Initialize the alerting service.
        
        Args:
            db_path: Path to SQLite database
            notification_channels: Dictionary of notification channel instances
            registry: Custom Prometheus registry for testing
        """
        self.db_path = db_path
        self.notification_channels = notification_channels
        self.registry = registry
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        
        # Prometheus metrics for alerting
        self._initialize_metrics()
        
        # Initialize database tables
        self._initialize_database()
    
    def _initialize_metrics(self) -> None:
        """Initialize Prometheus metrics for alerting."""
        
        # Alert metrics
        self.alerts_total = Counter(
            'alerts_total',
            'Total number of alerts',
            ['severity', 'status', 'rule_name'],
            registry=self.registry
        )
        
        self.alerts_active = Gauge(
            'alerts_active',
            'Number of active alerts',
            ['severity'],
            registry=self.registry
        )
        
        self.alert_evaluation_duration = Histogram(
            'alert_evaluation_duration_seconds',
            'Time spent evaluating alert rules',
            ['rule_name'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )
        
        self.alert_notification_duration = Histogram(
            'alert_notification_duration_seconds',
            'Time spent sending notifications',
            ['channel', 'severity'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry
        )
        
        self.alert_notification_errors = Counter(
            'alert_notification_errors_total',
            'Total notification errors',
            ['channel', 'error_type'],
            registry=self.registry
        )
    
    def _initialize_database(self) -> None:
        """Initialize database tables for alerting."""
        import sqlite3
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    rule_name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    value REAL NOT NULL,
                    threshold REAL NOT NULL,
                    labels TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    acknowledged_at TIMESTAMP,
                    resolved_at TIMESTAMP,
                    acknowledged_by TEXT,
                    resolved_by TEXT
                )
            """)
            
            # Create alert rules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_rules (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    operator TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    labels TEXT NOT NULL,
                    notification_channels TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def add_alert_rule(self, rule: AlertRule) -> None:
        """
        Add a new alert rule.
        
        Args:
            rule: Alert rule configuration
        """
        self.alert_rules[rule.name] = rule
        
        # Save to database
        import sqlite3
        import json
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO alert_rules 
                (name, description, severity, metric_name, threshold, operator, 
                 duration, labels, notification_channels, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule.name,
                rule.description,
                rule.severity.value,
                rule.metric_name,
                rule.threshold,
                rule.operator,
                rule.duration,
                json.dumps(rule.labels),
                json.dumps(rule.notification_channels),
                datetime.now().isoformat()
            ))
            conn.commit()
        
        logger.info("Alert rule added", rule_name=rule.name, severity=rule.severity.value)
    
    async def evaluate_alerts(self, metrics_data: Dict[str, Any]) -> List[Alert]:
        """
        Evaluate all alert rules against current metrics.
        
        Args:
            metrics_data: Current metrics data from Prometheus
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        for rule_name, rule in self.alert_rules.items():
            try:
                start_time = time.time()
                
                # Get metric value
                metric_value = self._get_metric_value(metrics_data, rule.metric_name, rule.labels)
                
                if metric_value is None:
                    continue
                
                # Check if rule is triggered
                is_triggered = self._evaluate_rule(metric_value, rule)
                
                if is_triggered:
                    # Check if alert already exists
                    alert_id = self._generate_alert_id(rule_name, rule.labels)
                    
                    if alert_id not in self.active_alerts:
                        # Create new alert
                        alert = Alert(
                            id=alert_id,
                            rule_name=rule_name,
                            severity=rule.severity,
                            status=AlertStatus.ACTIVE,
                            message=f"{rule.description}: {metric_value} {rule.operator} {rule.threshold}",
                            value=metric_value,
                            threshold=rule.threshold,
                            labels=rule.labels,
                            created_at=datetime.now()
                        )
                        
                        self.active_alerts[alert_id] = alert
                        triggered_alerts.append(alert)
                        
                        # Send notifications
                        await self._send_notifications(alert)
                        
                        # Update metrics
                        self.alerts_total.labels(
                            severity=alert.severity.value,
                            status=alert.status.value,
                            rule_name=alert.rule_name
                        ).inc()
                        
                        logger.warning("Alert triggered", 
                                     alert_id=alert_id,
                                     rule_name=rule_name,
                                     severity=alert.severity.value,
                                     value=metric_value,
                                     threshold=rule.threshold)
                
                # Update evaluation duration metric
                duration = time.time() - start_time
                self.alert_evaluation_duration.labels(rule_name=rule_name).observe(duration)
                
            except Exception as e:
                logger.error("Error evaluating alert rule", 
                           rule_name=rule_name, 
                           error=str(e))
        
        return triggered_alerts
    
    def _get_metric_value(self, metrics_data: Dict[str, Any], metric_name: str, labels: Dict[str, str]) -> Optional[float]:
        """Extract metric value from metrics data."""
        try:
            # Navigate through metrics data structure
            if metric_name in metrics_data:
                metric_data = metrics_data[metric_name]
                
                # Handle different metric data structures
                if isinstance(metric_data, dict):
                    # Try to match labels for nested structures
                    if labels:
                        # Look for exact label match in nested structure
                        current_level = metric_data
                        for label_key, label_value in labels.items():
                            if isinstance(current_level, dict) and label_value in current_level:
                                current_level = current_level[label_value]
                            else:
                                # If no exact match, try to find any numeric value
                                for key, value in current_level.items():
                                    if isinstance(value, (int, float)):
                                        return float(value)
                                return None
                        
                        # If we navigated successfully, check if final value is numeric
                        if isinstance(current_level, (int, float)):
                            return float(current_level)
                    else:
                        # No labels specified, look for any numeric value
                        for key, value in metric_data.items():
                            if isinstance(value, (int, float)):
                                return float(value)
                elif isinstance(metric_data, (int, float)):
                    return float(metric_data)
            
            return None
            
        except Exception as e:
            logger.error("Error getting metric value", 
                        metric_name=metric_name, 
                        error=str(e))
            return None
    
    def _evaluate_rule(self, value: float, rule: AlertRule) -> bool:
        """Evaluate if a rule is triggered."""
        try:
            if rule.operator == 'gt':
                return value > rule.threshold
            elif rule.operator == 'lt':
                return value < rule.threshold
            elif rule.operator == 'eq':
                return abs(value - rule.threshold) < 0.001
            elif rule.operator == 'gte':
                return value >= rule.threshold
            elif rule.operator == 'lte':
                return value <= rule.threshold
            else:
                logger.error("Unknown operator", operator=rule.operator)
                return False
                
        except Exception as e:
            logger.error("Error evaluating rule", 
                        rule_name=rule.name, 
                        error=str(e))
            return False
    
    def _generate_alert_id(self, rule_name: str, labels: Dict[str, str]) -> str:
        """Generate unique alert ID."""
        import hashlib
        
        # Create hash from rule name and labels
        label_str = "_".join(f"{k}={v}" for k, v in sorted(labels.items()))
        content = f"{rule_name}_{label_str}"
        
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    async def _send_notifications(self, alert: Alert) -> None:
        """Send notifications for an alert."""
        try:
            # Get notification channels for this alert
            rule = self.alert_rules.get(alert.rule_name)
            if not rule:
                return
            
            for channel_name in rule.notification_channels:
                if channel_name in self.notification_channels:
                    channel = self.notification_channels[channel_name]
                    
                    start_time = time.time()
                    
                    try:
                        await channel.send_alert(alert)
                        
                        # Update notification duration metric
                        duration = time.time() - start_time
                        self.alert_notification_duration.labels(
                            channel=channel_name,
                            severity=alert.severity.value
                        ).observe(duration)
                        
                    except Exception as e:
                        # Track notification errors
                        self.alert_notification_errors.labels(
                            channel=channel_name,
                            error_type=type(e).__name__
                        ).inc()
                        
                        logger.error("Error sending notification", 
                                   channel=channel_name,
                                   alert_id=alert.id,
                                   error=str(e))
                        
        except Exception as e:
            logger.error("Error in notification process", 
                        alert_id=alert.id,
                        error=str(e))
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID to acknowledge
            acknowledged_by: User who acknowledged the alert
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.now()
                alert.acknowledged_by = acknowledged_by
                
                # Update database
                await self._update_alert_in_database(alert)
                
                # Update metrics
                self.alerts_total.labels(
                    severity=alert.severity.value,
                    status=alert.status.value,
                    rule_name=alert.rule_name
                ).inc()
                
                logger.info("Alert acknowledged", 
                           alert_id=alert_id,
                           acknowledged_by=acknowledged_by)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error("Error acknowledging alert", 
                        alert_id=alert_id,
                        error=str(e))
            return False
    
    async def resolve_alert(self, alert_id: str, resolved_by: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID to resolve
            resolved_by: User who resolved the alert
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                alert.resolved_by = resolved_by
                
                # Move to history
                self.alert_history.append(alert)
                del self.active_alerts[alert_id]
                
                # Update database
                await self._update_alert_in_database(alert)
                
                # Update metrics
                self.alerts_total.labels(
                    severity=alert.severity.value,
                    status=alert.status.value,
                    rule_name=alert.rule_name
                ).inc()
                
                logger.info("Alert resolved", 
                           alert_id=alert_id,
                           resolved_by=resolved_by)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error("Error resolving alert", 
                        alert_id=alert_id,
                        error=str(e))
            return False
    
    async def _update_alert_in_database(self, alert: Alert) -> None:
        """Update alert in database."""
        import sqlite3
        import json
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO alerts 
                (id, rule_name, severity, status, message, value, threshold, 
                 labels, created_at, acknowledged_at, resolved_at, 
                 acknowledged_by, resolved_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.id,
                alert.rule_name,
                alert.severity.value,
                alert.status.value,
                alert.message,
                alert.value,
                alert.threshold,
                json.dumps(alert.labels),
                alert.created_at.isoformat(),
                alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                alert.resolved_at.isoformat() if alert.resolved_at else None,
                alert.acknowledged_by,
                alert.resolved_by
            ))
            conn.commit()
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        return self.alert_history[-limit:]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        total_alerts = len(self.active_alerts) + len(self.alert_history)
        
        severity_counts = {}
        for alert in list(self.active_alerts.values()) + self.alert_history:
            severity = alert.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            'total_alerts': total_alerts,
            'active_alerts': len(self.active_alerts),
            'resolved_alerts': len(self.alert_history),
            'severity_breakdown': severity_counts
        }
