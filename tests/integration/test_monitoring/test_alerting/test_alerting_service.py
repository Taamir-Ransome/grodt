"""
Integration tests for GRODT alerting service.

Tests alert rule evaluation, notification delivery, and alert management
functionality with comprehensive coverage of the alerting system.
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from grodtd.monitoring.alerting_service import (
    AlertingService, AlertRule, Alert, AlertSeverity, AlertStatus
)
from grodtd.monitoring.notifications.email_notification import EmailNotificationChannel
from grodtd.monitoring.notifications.telegram_notification import TelegramNotificationChannel
from tests.utils.test_prometheus import clean_prometheus_registry


class TestAlertingService:
    """Test suite for AlertingService."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        os.unlink(db_path)
    
    @pytest.fixture
    def mock_notification_channels(self):
        """Create mock notification channels."""
        email_channel = Mock(spec=EmailNotificationChannel)
        email_channel.send_alert = AsyncMock(return_value=True)
        
        telegram_channel = Mock(spec=TelegramNotificationChannel)
        telegram_channel.send_alert = AsyncMock(return_value=True)
        
        return {
            'email': email_channel,
            'telegram': telegram_channel
        }
    
    @pytest.fixture
    def alerting_service(self, temp_db, mock_notification_channels, clean_prometheus_registry):
        """Create AlertingService instance for testing."""
        return AlertingService(temp_db, mock_notification_channels)
    
    @pytest.fixture
    def sample_alert_rule(self):
        """Create sample alert rule for testing."""
        return AlertRule(
            name="test_cpu_usage",
            description="Test CPU usage alert",
            severity=AlertSeverity.HIGH,
            metric_name="system_cpu_usage_percent",
            threshold=80.0,
            operator="gt",
            duration=300,
            labels={"cpu_type": "total"},
            notification_channels=["email", "telegram"]
        )
    
    @pytest.fixture
    def sample_metrics_data(self):
        """Create sample metrics data for testing."""
        return {
            'system_cpu_usage_percent': {
                'total': 85.0
            },
            'system_memory_usage_percent': {
                'total': 70.0
            },
            'trading_drawdown_current': {
                'default': {
                    'total': 5.0
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_alert_rule_creation(self, alerting_service, sample_alert_rule):
        """Test alert rule creation and storage."""
        # Add alert rule
        alerting_service.add_alert_rule(sample_alert_rule)
        
        # Verify rule was added
        assert sample_alert_rule.name in alerting_service.alert_rules
        assert alerting_service.alert_rules[sample_alert_rule.name] == sample_alert_rule
    
    @pytest.mark.asyncio
    async def test_alert_evaluation_triggered(self, alerting_service, sample_alert_rule, sample_metrics_data):
        """Test alert evaluation when rule is triggered."""
        # Add alert rule
        alerting_service.add_alert_rule(sample_alert_rule)
        
        # Evaluate alerts with triggering metrics
        triggered_alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Verify alert was triggered
        assert len(triggered_alerts) == 1
        alert = triggered_alerts[0]
        assert alert.rule_name == sample_alert_rule.name
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.ACTIVE
        assert alert.value == 85.0
        assert alert.threshold == 80.0
    
    @pytest.mark.asyncio
    async def test_alert_evaluation_not_triggered(self, alerting_service, sample_alert_rule):
        """Test alert evaluation when rule is not triggered."""
        # Add alert rule
        alerting_service.add_alert_rule(sample_alert_rule)
        
        # Evaluate alerts with non-triggering metrics
        metrics_data = {
            'system_cpu_usage_percent': {
                'total': 70.0  # Below threshold
            }
        }
        
        triggered_alerts = await alerting_service.evaluate_alerts(metrics_data)
        
        # Verify no alerts were triggered
        assert len(triggered_alerts) == 0
    
    @pytest.mark.asyncio
    async def test_alert_acknowledgment(self, alerting_service, sample_alert_rule, sample_metrics_data):
        """Test alert acknowledgment functionality."""
        # Add alert rule and trigger alert
        alerting_service.add_alert_rule(sample_alert_rule)
        triggered_alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        alert_id = triggered_alerts[0].id
        
        # Acknowledge alert
        success = await alerting_service.acknowledge_alert(alert_id, "test_user")
        
        # Verify acknowledgment
        assert success is True
        alert = alerting_service.active_alerts[alert_id]
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "test_user"
        assert alert.acknowledged_at is not None
    
    @pytest.mark.asyncio
    async def test_alert_resolution(self, alerting_service, sample_alert_rule, sample_metrics_data):
        """Test alert resolution functionality."""
        # Add alert rule and trigger alert
        alerting_service.add_alert_rule(sample_alert_rule)
        triggered_alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        alert_id = triggered_alerts[0].id
        
        # Resolve alert
        success = await alerting_service.resolve_alert(alert_id, "test_user")
        
        # Verify resolution
        assert success is True
        assert alert_id not in alerting_service.active_alerts
        assert len(alerting_service.alert_history) == 1
        
        resolved_alert = alerting_service.alert_history[0]
        assert resolved_alert.status == AlertStatus.RESOLVED
        assert resolved_alert.resolved_by == "test_user"
        assert resolved_alert.resolved_at is not None
    
    @pytest.mark.asyncio
    async def test_notification_delivery(self, alerting_service, sample_alert_rule, sample_metrics_data, mock_notification_channels):
        """Test notification delivery for triggered alerts."""
        # Add alert rule
        alerting_service.add_alert_rule(sample_alert_rule)
        
        # Evaluate alerts
        triggered_alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Verify notifications were sent
        assert len(triggered_alerts) == 1
        
        # Check that notification channels were called
        mock_notification_channels['email'].send_alert.assert_called_once()
        mock_notification_channels['telegram'].send_alert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_alert_rule_operators(self, alerting_service):
        """Test different alert rule operators."""
        # Test greater than operator
        gt_rule = AlertRule(
            name="test_gt",
            description="Test greater than",
            severity=AlertSeverity.MEDIUM,
            metric_name="test_metric",
            threshold=50.0,
            operator="gt",
            duration=0,
            labels={},
            notification_channels=["email"]
        )
        
        # Test less than operator
        lt_rule = AlertRule(
            name="test_lt",
            description="Test less than",
            severity=AlertSeverity.MEDIUM,
            metric_name="test_metric",
            threshold=50.0,
            operator="lt",
            duration=0,
            labels={},
            notification_channels=["email"]
        )
        
        alerting_service.add_alert_rule(gt_rule)
        alerting_service.add_alert_rule(lt_rule)
        
        # Test metrics that should trigger gt rule
        metrics_high = {'test_metric': 75.0}
        alerts_high = await alerting_service.evaluate_alerts(metrics_high)
        assert len(alerts_high) == 1
        assert alerts_high[0].rule_name == "test_gt"
        
        # Test metrics that should trigger lt rule
        metrics_low = {'test_metric': 25.0}
        alerts_low = await alerting_service.evaluate_alerts(metrics_low)
        assert len(alerts_low) == 1
        assert alerts_low[0].rule_name == "test_lt"
    
    @pytest.mark.asyncio
    async def test_alert_statistics(self, alerting_service, sample_alert_rule, sample_metrics_data):
        """Test alert statistics functionality."""
        # Add alert rule and trigger some alerts
        alerting_service.add_alert_rule(sample_alert_rule)
        await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Get statistics
        stats = alerting_service.get_alert_statistics()
        
        # Verify statistics
        assert 'total_alerts' in stats
        assert 'active_alerts' in stats
        assert 'resolved_alerts' in stats
        assert 'severity_breakdown' in stats
        
        assert stats['active_alerts'] == 1
        assert stats['resolved_alerts'] == 0
        assert stats['severity_breakdown']['high'] == 1
    
    @pytest.mark.asyncio
    async def test_alert_history(self, alerting_service, sample_alert_rule, sample_metrics_data):
        """Test alert history functionality."""
        # Add alert rule and trigger alert
        alerting_service.add_alert_rule(sample_alert_rule)
        triggered_alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        alert_id = triggered_alerts[0].id
        
        # Resolve alert to move it to history
        await alerting_service.resolve_alert(alert_id, "test_user")
        
        # Get history
        history = alerting_service.get_alert_history()
        
        # Verify history
        assert len(history) == 1
        assert history[0].id == alert_id
        assert history[0].status == AlertStatus.RESOLVED
    
    @pytest.mark.asyncio
    async def test_alert_duplicate_prevention(self, alerting_service, sample_alert_rule, sample_metrics_data):
        """Test that duplicate alerts are prevented."""
        # Add alert rule
        alerting_service.add_alert_rule(sample_alert_rule)
        
        # Trigger alert multiple times
        alerts1 = await alerting_service.evaluate_alerts(sample_metrics_data)
        alerts2 = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Verify only one alert was created
        assert len(alerts1) == 1
        assert len(alerts2) == 0  # No new alert should be created
        assert len(alerting_service.active_alerts) == 1
    
    @pytest.mark.asyncio
    async def test_alert_rule_evaluation_error_handling(self, alerting_service):
        """Test error handling in alert rule evaluation."""
        # Create rule with invalid metric name
        invalid_rule = AlertRule(
            name="test_invalid",
            description="Test invalid metric",
            severity=AlertSeverity.LOW,
            metric_name="nonexistent_metric",
            threshold=50.0,
            operator="gt",
            duration=0,
            labels={},
            notification_channels=["email"]
        )
        
        alerting_service.add_alert_rule(invalid_rule)
        
        # Evaluate with empty metrics data
        alerts = await alerting_service.evaluate_alerts({})
        
        # Should not crash and return empty list
        assert len(alerts) == 0
    
    @pytest.mark.asyncio
    async def test_notification_channel_error_handling(self, alerting_service, sample_alert_rule, sample_metrics_data):
        """Test error handling in notification delivery."""
        # Create mock channel that raises exception
        error_channel = Mock()
        error_channel.send_alert = AsyncMock(side_effect=Exception("Notification error"))
        
        # Replace notification channels
        alerting_service.notification_channels = {'email': error_channel}
        
        # Add alert rule
        alerting_service.add_alert_rule(sample_alert_rule)
        
        # Should not crash when notification fails
        alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Alert should still be created despite notification failure
        assert len(alerts) == 1
        assert len(alerting_service.active_alerts) == 1


class TestAlertRuleEvaluation:
    """Test alert rule evaluation logic."""
    
    def test_metric_value_extraction(self):
        """Test metric value extraction from metrics data."""
        from grodtd.monitoring.alerting_service import AlertingService
        
        # Create service with mock database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            service = AlertingService(db_path, {})
            
            # Test simple metric value
            metrics_data = {'cpu_usage': 85.0}
            value = service._get_metric_value(metrics_data, 'cpu_usage', {})
            assert value == 85.0
            
            # Test nested metric value
            metrics_data = {'system': {'cpu_usage': 85.0}}
            value = service._get_metric_value(metrics_data, 'system', {})
            assert value == 85.0  # Should find first numeric value in nested structure
            
            # Test missing metric
            value = service._get_metric_value(metrics_data, 'missing_metric', {})
            assert value is None
            
        finally:
            os.unlink(db_path)
    
    def test_rule_evaluation_operators(self):
        """Test different rule evaluation operators."""
        from grodtd.monitoring.alerting_service import AlertingService, AlertRule, AlertSeverity
        
        # Create service with mock database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            service = AlertingService(db_path, {})
            
            # Test greater than
            rule = AlertRule(
                name="test", description="test", severity=AlertSeverity.LOW,
                metric_name="test", threshold=50.0, operator="gt", duration=0,
                labels={}, notification_channels=[]
            )
            assert service._evaluate_rule(75.0, rule) is True
            assert service._evaluate_rule(25.0, rule) is False
            
            # Test less than
            rule.operator = "lt"
            assert service._evaluate_rule(25.0, rule) is True
            assert service._evaluate_rule(75.0, rule) is False
            
            # Test equal
            rule.operator = "eq"
            assert service._evaluate_rule(50.0, rule) is True
            assert service._evaluate_rule(51.0, rule) is False
            
            # Test greater than or equal
            rule.operator = "gte"
            assert service._evaluate_rule(50.0, rule) is True
            assert service._evaluate_rule(51.0, rule) is True
            assert service._evaluate_rule(49.0, rule) is False
            
            # Test less than or equal
            rule.operator = "lte"
            assert service._evaluate_rule(50.0, rule) is True
            assert service._evaluate_rule(49.0, rule) is True
            assert service._evaluate_rule(51.0, rule) is False
            
        finally:
            os.unlink(db_path)
