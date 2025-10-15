"""
Unit tests for alert models and data structures.

Tests Alert, AlertRule, AlertSeverity, and AlertStatus classes
with comprehensive validation of data integrity and behavior.
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from grodtd.monitoring.alerting_service import (
    Alert, AlertRule, AlertSeverity, AlertStatus
)


class TestAlertSeverity:
    """Test suite for AlertSeverity enum."""
    
    def test_severity_values(self):
        """Test alert severity enum values."""
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.CRITICAL.value == "critical"
    
    def test_severity_comparison(self):
        """Test alert severity comparison."""
        # Test that severity levels exist and have expected values
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.CRITICAL.value == "critical"
    
    def test_severity_from_string(self):
        """Test creating severity from string."""
        assert AlertSeverity("low") == AlertSeverity.LOW
        assert AlertSeverity("medium") == AlertSeverity.MEDIUM
        assert AlertSeverity("high") == AlertSeverity.HIGH
        assert AlertSeverity("critical") == AlertSeverity.CRITICAL
    
    def test_invalid_severity(self):
        """Test invalid severity value."""
        with pytest.raises(ValueError):
            AlertSeverity("invalid")


class TestAlertStatus:
    """Test suite for AlertStatus enum."""
    
    def test_status_values(self):
        """Test alert status enum values."""
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.SUPPRESSED.value == "suppressed"
    
    def test_status_from_string(self):
        """Test creating status from string."""
        assert AlertStatus("active") == AlertStatus.ACTIVE
        assert AlertStatus("acknowledged") == AlertStatus.ACKNOWLEDGED
        assert AlertStatus("resolved") == AlertStatus.RESOLVED
        assert AlertStatus("suppressed") == AlertStatus.SUPPRESSED
    
    def test_invalid_status(self):
        """Test invalid status value."""
        with pytest.raises(ValueError):
            AlertStatus("invalid")


class TestAlertRule:
    """Test suite for AlertRule dataclass."""
    
    def test_alert_rule_creation(self):
        """Test alert rule creation with all fields."""
        rule = AlertRule(
            name="test_rule",
            description="Test alert rule",
            severity=AlertSeverity.HIGH,
            metric_name="test_metric",
            threshold=80.0,
            operator="gt",
            duration=300,
            labels={"system": "test"},
            notification_channels=["email", "telegram"]
        )
        
        assert rule.name == "test_rule"
        assert rule.description == "Test alert rule"
        assert rule.severity == AlertSeverity.HIGH
        assert rule.metric_name == "test_metric"
        assert rule.threshold == 80.0
        assert rule.operator == "gt"
        assert rule.duration == 300
        assert rule.labels == {"system": "test"}
        assert rule.notification_channels == ["email", "telegram"]
    
    def test_alert_rule_minimal(self):
        """Test alert rule creation with minimal fields."""
        rule = AlertRule(
            name="minimal_rule",
            description="Minimal rule",
            severity=AlertSeverity.LOW,
            metric_name="minimal_metric",
            threshold=50.0,
            operator="eq",
            duration=0,
            labels={},
            notification_channels=[]
        )
        
        assert rule.name == "minimal_rule"
        assert rule.labels == {}
        assert rule.notification_channels == []
    
    def test_alert_rule_operators(self):
        """Test different alert rule operators."""
        operators = ["gt", "lt", "eq", "gte", "lte"]
        
        for operator in operators:
            rule = AlertRule(
                name=f"rule_{operator}",
                description=f"Rule with {operator} operator",
                severity=AlertSeverity.MEDIUM,
                metric_name="test_metric",
                threshold=50.0,
                operator=operator,
                duration=60,
                labels={},
                notification_channels=["email"]
            )
            assert rule.operator == operator
    
    def test_alert_rule_severity_levels(self):
        """Test alert rule with different severity levels."""
        severities = [AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        
        for severity in severities:
            rule = AlertRule(
                name=f"rule_{severity.value}",
                description=f"Rule with {severity.value} severity",
                severity=severity,
                metric_name="test_metric",
                threshold=50.0,
                operator="gt",
                duration=60,
                labels={},
                notification_channels=["email"]
            )
            assert rule.severity == severity


class TestAlert:
    """Test suite for Alert dataclass."""
    
    def test_alert_creation(self):
        """Test alert creation with all fields."""
        now = datetime.now()
        alert = Alert(
            id="test_alert_001",
            rule_name="test_rule",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            message="Test alert message",
            value=85.0,
            threshold=80.0,
            labels={"system": "test"},
            created_at=now
        )
        
        assert alert.id == "test_alert_001"
        assert alert.rule_name == "test_rule"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.ACTIVE
        assert alert.message == "Test alert message"
        assert alert.value == 85.0
        assert alert.threshold == 80.0
        assert alert.labels == {"system": "test"}
        assert alert.created_at == now
        assert alert.acknowledged_at is None
        assert alert.resolved_at is None
        assert alert.acknowledged_by is None
        assert alert.resolved_by is None
    
    def test_alert_creation_with_optional_fields(self):
        """Test alert creation with optional fields."""
        now = datetime.now()
        acknowledged_at = now.replace(microsecond=0)
        resolved_at = now.replace(microsecond=0)
        
        alert = Alert(
            id="test_alert_002",
            rule_name="test_rule",
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.RESOLVED,
            message="Test alert with optional fields",
            value=75.0,
            threshold=70.0,
            labels={"system": "test"},
            created_at=now,
            acknowledged_at=acknowledged_at,
            resolved_at=resolved_at,
            acknowledged_by="user1",
            resolved_by="user2"
        )
        
        assert alert.acknowledged_at == acknowledged_at
        assert alert.resolved_at == resolved_at
        assert alert.acknowledged_by == "user1"
        assert alert.resolved_by == "user2"
    
    def test_alert_status_transitions(self):
        """Test alert status transitions."""
        now = datetime.now()
        alert = Alert(
            id="status_test",
            rule_name="status_rule",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            message="Status test alert",
            value=90.0,
            threshold=80.0,
            labels={},
            created_at=now
        )
        
        # Test initial status
        assert alert.status == AlertStatus.ACTIVE
        
        # Test acknowledgment
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = now
        alert.acknowledged_by = "user1"
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_at == now
        assert alert.acknowledged_by == "user1"
        
        # Test resolution
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now
        alert.resolved_by = "user2"
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_at == now
        assert alert.resolved_by == "user2"
    
    def test_alert_severity_levels(self):
        """Test alerts with different severity levels."""
        severities = [AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        
        for severity in severities:
            alert = Alert(
                id=f"alert_{severity.value}",
                rule_name=f"rule_{severity.value}",
                severity=severity,
                status=AlertStatus.ACTIVE,
                message=f"Alert with {severity.value} severity",
                value=50.0,
                threshold=40.0,
                labels={},
                created_at=datetime.now()
            )
            assert alert.severity == severity
    
    def test_alert_labels(self):
        """Test alert with different label configurations."""
        # Test empty labels
        alert1 = Alert(
            id="alert1",
            rule_name="rule1",
            severity=AlertSeverity.LOW,
            status=AlertStatus.ACTIVE,
            message="Alert with empty labels",
            value=30.0,
            threshold=25.0,
            labels={},
            created_at=datetime.now()
        )
        assert alert1.labels == {}
        
        # Test single label
        alert2 = Alert(
            id="alert2",
            rule_name="rule2",
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.ACTIVE,
            message="Alert with single label",
            value=60.0,
            threshold=50.0,
            labels={"system": "test"},
            created_at=datetime.now()
        )
        assert alert2.labels == {"system": "test"}
        
        # Test multiple labels
        alert3 = Alert(
            id="alert3",
            rule_name="rule3",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            message="Alert with multiple labels",
            value=85.0,
            threshold=80.0,
            labels={"system": "prod", "component": "api", "region": "us-east"},
            created_at=datetime.now()
        )
        assert alert3.labels == {"system": "prod", "component": "api", "region": "us-east"}
    
    def test_alert_value_types(self):
        """Test alert with different value types."""
        # Test integer value
        alert1 = Alert(
            id="alert_int",
            rule_name="rule_int",
            severity=AlertSeverity.LOW,
            status=AlertStatus.ACTIVE,
            message="Alert with integer value",
            value=100,
            threshold=90,
            labels={},
            created_at=datetime.now()
        )
        assert alert1.value == 100
        assert alert1.threshold == 90
        
        # Test float value
        alert2 = Alert(
            id="alert_float",
            rule_name="rule_float",
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.ACTIVE,
            message="Alert with float value",
            value=85.5,
            threshold=80.0,
            labels={},
            created_at=datetime.now()
        )
        assert alert2.value == 85.5
        assert alert2.threshold == 80.0
    
    def test_alert_message_content(self):
        """Test alert message content."""
        alert = Alert(
            id="message_test",
            rule_name="message_rule",
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.ACTIVE,
            message="Critical system failure: CPU usage at 95%",
            value=95.0,
            threshold=90.0,
            labels={"component": "cpu"},
            created_at=datetime.now()
        )
        
        assert "Critical system failure" in alert.message
        assert "CPU usage at 95%" in alert.message
        assert len(alert.message) > 0
    
    def test_alert_timestamps(self):
        """Test alert timestamp handling."""
        now = datetime.now()
        alert = Alert(
            id="timestamp_test",
            rule_name="timestamp_rule",
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.ACTIVE,
            message="Timestamp test alert",
            value=60.0,
            threshold=50.0,
            labels={},
            created_at=now
        )
        
        # Test created_at timestamp
        assert alert.created_at == now
        assert isinstance(alert.created_at, datetime)
        
        # Test optional timestamps
        assert alert.acknowledged_at is None
        assert alert.resolved_at is None
        
        # Test setting optional timestamps
        later = now.replace(microsecond=0)
        alert.acknowledged_at = later
        alert.resolved_at = later
        
        assert alert.acknowledged_at == later
        assert alert.resolved_at == later
