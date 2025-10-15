"""
End-to-end integration tests for GRODT alerting system.

Tests complete alert workflow from rule evaluation to notification delivery
with real database operations and comprehensive error handling.
"""

import pytest
import asyncio
import tempfile
import os
import yaml
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from grodtd.monitoring.alerting_service import (
    AlertingService, AlertRule, Alert, AlertSeverity, AlertStatus
)
from grodtd.monitoring.notifications.email_notification import EmailNotificationChannel
from grodtd.monitoring.notifications.telegram_notification import TelegramNotificationChannel
from tests.utils.test_prometheus import clean_prometheus_registry


class TestAlertingSystemIntegration:
    """End-to-end integration tests for the alerting system."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        os.unlink(db_path)
    
    @pytest.fixture
    def notification_channels(self):
        """Create notification channels with mocked external services."""
        email_channel = Mock(spec=EmailNotificationChannel)
        email_channel.send_alert = AsyncMock(return_value=True)
        email_channel.send_test_email = AsyncMock(return_value=True)
        
        telegram_channel = Mock(spec=TelegramNotificationChannel)
        telegram_channel.send_alert = AsyncMock(return_value=True)
        telegram_channel.send_test_message = AsyncMock(return_value=True)
        
        return {
            'email': email_channel,
            'telegram': telegram_channel
        }
    
    @pytest.fixture
    def alerting_service(self, temp_db, notification_channels, clean_prometheus_registry):
        """Create AlertingService instance for testing."""
        return AlertingService(temp_db, notification_channels)
    
    @pytest.fixture
    def sample_alert_rules(self):
        """Create sample alert rules for testing."""
        return [
            AlertRule(
                name="high_cpu_usage",
                description="CPU usage exceeds threshold",
                severity=AlertSeverity.HIGH,
                metric_name="system_cpu_usage_percent",
                threshold=80.0,
                operator="gt",
                duration=300,
                labels={"cpu_type": "total"},
                notification_channels=["email", "telegram"]
            ),
            AlertRule(
                name="high_drawdown",
                description="Portfolio drawdown exceeds threshold",
                severity=AlertSeverity.HIGH,
                metric_name="trading_drawdown_current",
                threshold=10.0,
                operator="gt",
                duration=300,
                labels={"strategy": "default", "symbol": "total"},
                notification_channels=["email", "telegram"]
            ),
            AlertRule(
                name="regime_change",
                description="Market regime change detected",
                severity=AlertSeverity.MEDIUM,
                metric_name="regime_change_detected",
                threshold=1.0,
                operator="eq",
                duration=0,
                labels={"regime_type": "change"},
                notification_channels=["email", "telegram"]
            )
        ]
    
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
                    'total': 12.0
                }
            },
            'trading_pnl_total': {
                'default': {
                    'total': -500.0
                }
            },
            'regime_change_detected': {
                'change': 1.0
            }
        }
    
    @pytest.mark.asyncio
    async def test_complete_alert_workflow(self, alerting_service, sample_alert_rules, sample_metrics_data):
        """Test complete alert workflow from rule evaluation to resolution."""
        # Add alert rules
        for rule in sample_alert_rules:
            alerting_service.add_alert_rule(rule)
        
        # Evaluate alerts
        triggered_alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Verify alerts were triggered
        assert len(triggered_alerts) == 3  # All three rules should trigger
        
        # Verify alert details
        alert_ids = [alert.id for alert in triggered_alerts]
        assert len(set(alert_ids)) == 3  # All alerts should have unique IDs
        
        # Test acknowledgment
        alert_id = triggered_alerts[0].id
        success = await alerting_service.acknowledge_alert(alert_id, "test_user")
        assert success is True
        
        # Verify acknowledgment
        alert = alerting_service.active_alerts[alert_id]
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "test_user"
        assert alert.acknowledged_at is not None
        
        # Test resolution
        success = await alerting_service.resolve_alert(alert_id, "test_user")
        assert success is True
        
        # Verify resolution
        assert alert_id not in alerting_service.active_alerts
        assert len(alerting_service.alert_history) == 1
        
        resolved_alert = alerting_service.alert_history[0]
        assert resolved_alert.status == AlertStatus.RESOLVED
        assert resolved_alert.resolved_by == "test_user"
        assert resolved_alert.resolved_at is not None
    
    @pytest.mark.asyncio
    async def test_notification_delivery_integration(self, alerting_service, sample_alert_rules, sample_metrics_data, notification_channels):
        """Test notification delivery integration."""
        # Add alert rules
        for rule in sample_alert_rules:
            alerting_service.add_alert_rule(rule)
        
        # Evaluate alerts
        triggered_alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Verify notifications were sent
        assert len(triggered_alerts) == 3
        
        # Check that all notification channels were called for each alert
        # Verify that email and telegram channels were called 3 times each (once per alert)
        assert notification_channels['email'].send_alert.call_count == 3
        assert notification_channels['telegram'].send_alert.call_count == 3
        
        # Verify that all calls were made with Alert objects
        for call in notification_channels['email'].send_alert.call_args_list:
            assert hasattr(call[0][0], 'id')  # Check it's an Alert object
        for call in notification_channels['telegram'].send_alert.call_args_list:
            assert hasattr(call[0][0], 'id')  # Check it's an Alert object
    
    @pytest.mark.asyncio
    async def test_alert_rule_evaluation_edge_cases(self, alerting_service):
        """Test alert rule evaluation with edge cases."""
        # Create rules with different operators
        rules = [
            AlertRule(
                name="gt_rule",
                description="Greater than rule",
                severity=AlertSeverity.MEDIUM,
                metric_name="test_metric",
                threshold=50.0,
                operator="gt",
                duration=0,
                labels={},
                notification_channels=["email"]
            ),
            AlertRule(
                name="lt_rule",
                description="Less than rule",
                severity=AlertSeverity.MEDIUM,
                metric_name="test_metric",
                threshold=50.0,
                operator="lt",
                duration=0,
                labels={},
                notification_channels=["email"]
            ),
            AlertRule(
                name="eq_rule",
                description="Equal rule",
                severity=AlertSeverity.MEDIUM,
                metric_name="test_metric",
                threshold=50.0,
                operator="eq",
                duration=0,
                labels={},
                notification_channels=["email"]
            )
        ]
        
        for rule in rules:
            alerting_service.add_alert_rule(rule)
        
        # Test metrics that should trigger gt rule
        metrics_high = {'test_metric': 75.0}
        alerts_high = await alerting_service.evaluate_alerts(metrics_high)
        assert len(alerts_high) == 1
        assert alerts_high[0].rule_name == "gt_rule"
        
        # Test metrics that should trigger lt rule
        metrics_low = {'test_metric': 25.0}
        alerts_low = await alerting_service.evaluate_alerts(metrics_low)
        assert len(alerts_low) == 1
        assert alerts_low[0].rule_name == "lt_rule"
        
        # Test metrics that should trigger eq rule
        metrics_equal = {'test_metric': 50.0}
        alerts_equal = await alerting_service.evaluate_alerts(metrics_equal)
        assert len(alerts_equal) == 1
        assert alerts_equal[0].rule_name == "eq_rule"
    
    @pytest.mark.asyncio
    async def test_alert_duplicate_prevention(self, alerting_service, sample_alert_rules, sample_metrics_data):
        """Test that duplicate alerts are prevented."""
        # Add alert rules
        for rule in sample_alert_rules:
            alerting_service.add_alert_rule(rule)
        
        # Trigger alerts multiple times
        alerts1 = await alerting_service.evaluate_alerts(sample_metrics_data)
        alerts2 = await alerting_service.evaluate_alerts(sample_metrics_data)
        alerts3 = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Verify only one set of alerts was created
        assert len(alerts1) == 3
        assert len(alerts2) == 0  # No new alerts
        assert len(alerts3) == 0  # No new alerts
        assert len(alerting_service.active_alerts) == 3
    
    @pytest.mark.asyncio
    async def test_alert_statistics_integration(self, alerting_service, sample_alert_rules, sample_metrics_data):
        """Test alert statistics integration."""
        # Add alert rules
        for rule in sample_alert_rules:
            alerting_service.add_alert_rule(rule)
        
        # Trigger alerts
        await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Get statistics
        stats = alerting_service.get_alert_statistics()
        
        # Verify statistics
        assert stats['total_alerts'] == 3
        assert stats['active_alerts'] == 3
        assert stats['resolved_alerts'] == 0
        assert 'severity_breakdown' in stats
        
        # Test with some resolved alerts
        alert_id = list(alerting_service.active_alerts.keys())[0]
        await alerting_service.resolve_alert(alert_id, "test_user")
        
        stats_after_resolution = alerting_service.get_alert_statistics()
        assert stats_after_resolution['active_alerts'] == 2
        assert stats_after_resolution['resolved_alerts'] == 1
    
    @pytest.mark.asyncio
    async def test_alert_history_integration(self, alerting_service, sample_alert_rules, sample_metrics_data):
        """Test alert history integration."""
        # Add alert rules
        for rule in sample_alert_rules:
            alerting_service.add_alert_rule(rule)
        
        # Trigger alerts
        triggered_alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Resolve some alerts
        alert_ids = [alert.id for alert in triggered_alerts[:2]]
        for alert_id in alert_ids:
            await alerting_service.resolve_alert(alert_id, "test_user")
        
        # Get history
        history = alerting_service.get_alert_history()
        
        # Verify history
        assert len(history) == 2
        for alert in history:
            assert alert.status == AlertStatus.RESOLVED
            assert alert.resolved_by == "test_user"
    
    @pytest.mark.asyncio
    async def test_alert_rule_configuration_loading(self, alerting_service):
        """Test loading alert rules from configuration."""
        # Create configuration data
        config_data = {
            'system_alerts': [
                {
                    'name': 'config_cpu_usage',
                    'description': 'CPU usage from config',
                    'severity': 'high',
                    'metric_name': 'system_cpu_usage_percent',
                    'threshold': 85.0,
                    'operator': 'gt',
                    'duration': 300,
                    'labels': {'cpu_type': 'total'},
                    'notification_channels': ['email', 'telegram']
                }
            ]
        }
        
        # Load rules from configuration
        for rule_config in config_data['system_alerts']:
            rule = AlertRule(
                name=rule_config['name'],
                description=rule_config['description'],
                severity=AlertSeverity(rule_config['severity']),
                metric_name=rule_config['metric_name'],
                threshold=rule_config['threshold'],
                operator=rule_config['operator'],
                duration=rule_config['duration'],
                labels=rule_config['labels'],
                notification_channels=rule_config['notification_channels']
            )
            alerting_service.add_alert_rule(rule)
        
        # Verify rule was loaded
        assert 'config_cpu_usage' in alerting_service.alert_rules
        
        # Test rule evaluation
        metrics_data = {'system_cpu_usage_percent': {'total': 90.0}}
        alerts = await alerting_service.evaluate_alerts(metrics_data)
        
        assert len(alerts) == 1
        assert alerts[0].rule_name == 'config_cpu_usage'
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, alerting_service):
        """Test error handling in alert evaluation."""
        # Create rule with invalid metric name
        invalid_rule = AlertRule(
            name="invalid_rule",
            description="Rule with invalid metric",
            severity=AlertSeverity.LOW,
            metric_name="nonexistent_metric",
            threshold=50.0,
            operator="gt",
            duration=0,
            labels={},
            notification_channels=["email"]
        )
        
        alerting_service.add_alert_rule(invalid_rule)
        
        # Test with empty metrics data
        alerts = await alerting_service.evaluate_alerts({})
        assert len(alerts) == 0
        
        # Test with malformed metrics data
        malformed_metrics = {
            'valid_metric': 'not_a_number',
            'another_metric': None
        }
        alerts = await alerting_service.evaluate_alerts(malformed_metrics)
        assert len(alerts) == 0
    
    @pytest.mark.asyncio
    async def test_notification_channel_error_handling(self, alerting_service, sample_alert_rules, sample_metrics_data):
        """Test error handling in notification delivery."""
        # Create channels that will fail
        failing_email_channel = Mock(spec=EmailNotificationChannel)
        failing_email_channel.send_alert = AsyncMock(side_effect=Exception("Email service unavailable"))
        
        failing_telegram_channel = Mock(spec=TelegramNotificationChannel)
        failing_telegram_channel.send_alert = AsyncMock(side_effect=Exception("Telegram service unavailable"))
        
        # Replace notification channels
        alerting_service.notification_channels = {
            'email': failing_email_channel,
            'telegram': failing_telegram_channel
        }
        
        # Add alert rules
        for rule in sample_alert_rules:
            alerting_service.add_alert_rule(rule)
        
        # Should not crash when notifications fail
        alerts = await alerting_service.evaluate_alerts(sample_metrics_data)
        
        # Alerts should still be created despite notification failures
        assert len(alerts) == 3
        assert len(alerting_service.active_alerts) == 3
        
        # Verify notification channels were called (and failed)
        failing_email_channel.send_alert.assert_called()
        failing_telegram_channel.send_alert.assert_called()
    
    @pytest.mark.asyncio
    async def test_alert_escalation_simulation(self, alerting_service):
        """Test alert escalation simulation."""
        # Create escalation rule
        escalation_rule = AlertRule(
            name="critical_system_failure",
            description="Critical system failure",
            severity=AlertSeverity.CRITICAL,
            metric_name="system_cpu_usage_percent",
            threshold=95.0,
            operator="gt",
            duration=60,  # 1 minute
            labels={"cpu_type": "total"},
            notification_channels=["email", "telegram"]
        )
        
        alerting_service.add_alert_rule(escalation_rule)
        
        # Test escalation scenario
        metrics_data = {'system_cpu_usage_percent': {'total': 98.0}}
        alerts = await alerting_service.evaluate_alerts(metrics_data)
        
        # Verify critical alert was triggered
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL
        assert alerts[0].value == 98.0
        assert alerts[0].threshold == 95.0
    
    @pytest.mark.asyncio
    async def test_alert_suppression_simulation(self, alerting_service):
        """Test alert suppression simulation."""
        # Create rule that might be suppressed
        suppressible_rule = AlertRule(
            name="maintenance_alert",
            description="Maintenance window alert",
            severity=AlertSeverity.LOW,
            metric_name="system_maintenance_mode",
            threshold=1.0,
            operator="eq",
            duration=0,
            labels={"maintenance": "true"},
            notification_channels=["email"]
        )
        
        alerting_service.add_alert_rule(suppressible_rule)
        
        # Test suppression scenario
        metrics_data = {'system_maintenance_mode': 1.0}
        alerts = await alerting_service.evaluate_alerts(metrics_data)
        
        # Alert should still be created (suppression logic would be in higher-level service)
        assert len(alerts) == 1
        assert alerts[0].rule_name == "maintenance_alert"
