"""
Alert management API endpoints for GRODT system.

Provides REST API endpoints for:
- Alert acknowledgment and resolution
- Alert history and status queries
- Alert testing and validation
- Alert configuration management
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from flask import Flask, request, jsonify, Blueprint

import structlog

logger = structlog.get_logger(__name__)

# Create Blueprint for alert API
alert_bp = Blueprint('alerts', __name__, url_prefix='/alerts')


class AlertAPI:
    """
    Alert management API for GRODT system.
    
    Provides REST endpoints for alert management operations including
    acknowledgment, resolution, history, and testing.
    """
    
    def __init__(self, alerting_service):
        """
        Initialize alert API.
        
        Args:
            alerting_service: AlertingService instance
        """
        self.alerting_service = alerting_service
    
    @alert_bp.route('/acknowledge', methods=['POST'])
    async def acknowledge_alert(self):
        """
        Acknowledge an alert.
        
        Request body:
        {
            "alert_id": "string",
            "acknowledged_by": "string"
        }
        
        Returns:
            JSON response with success status
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            alert_id = data.get('alert_id')
            acknowledged_by = data.get('acknowledged_by')
            
            if not alert_id:
                return jsonify({'error': 'alert_id is required'}), 400
            
            if not acknowledged_by:
                return jsonify({'error': 'acknowledged_by is required'}), 400
            
            # Acknowledge the alert
            success = await self.alerting_service.acknowledge_alert(alert_id, acknowledged_by)
            
            if success:
                logger.info("Alert acknowledged via API", 
                           alert_id=alert_id,
                           acknowledged_by=acknowledged_by)
                return jsonify({
                    'success': True,
                    'message': 'Alert acknowledged successfully',
                    'alert_id': alert_id
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Alert not found or already acknowledged'
                }), 404
                
        except Exception as e:
            logger.error("Error acknowledging alert", error=str(e))
            return jsonify({
                'success': False,
                'error': 'Internal server error'
            }), 500
    
    @alert_bp.route('/resolve', methods=['POST'])
    async def resolve_alert(self):
        """
        Resolve an alert.
        
        Request body:
        {
            "alert_id": "string",
            "resolved_by": "string"
        }
        
        Returns:
            JSON response with success status
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            alert_id = data.get('alert_id')
            resolved_by = data.get('resolved_by')
            
            if not alert_id:
                return jsonify({'error': 'alert_id is required'}), 400
            
            if not resolved_by:
                return jsonify({'error': 'resolved_by is required'}), 400
            
            # Resolve the alert
            success = await self.alerting_service.resolve_alert(alert_id, resolved_by)
            
            if success:
                logger.info("Alert resolved via API", 
                           alert_id=alert_id,
                           resolved_by=resolved_by)
                return jsonify({
                    'success': True,
                    'message': 'Alert resolved successfully',
                    'alert_id': alert_id
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Alert not found or already resolved'
                }), 404
                
        except Exception as e:
            logger.error("Error resolving alert", error=str(e))
            return jsonify({
                'success': False,
                'error': 'Internal server error'
            }), 500
    
    @alert_bp.route('/history', methods=['GET'])
    async def get_alert_history(self):
        """
        Get alert history.
        
        Query parameters:
        - limit: Maximum number of alerts to return (default: 100)
        - severity: Filter by severity level
        - status: Filter by status
        - start_date: Start date filter (ISO format)
        - end_date: End date filter (ISO format)
        
        Returns:
            JSON response with alert history
        """
        try:
            # Get query parameters
            limit = int(request.args.get('limit', 100))
            severity = request.args.get('severity')
            status = request.args.get('status')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            # Get alert history
            alerts = self.alerting_service.get_alert_history(limit)
            
            # Apply filters
            filtered_alerts = []
            for alert in alerts:
                # Severity filter
                if severity and alert.severity.value != severity:
                    continue
                
                # Status filter
                if status and alert.status.value != status:
                    continue
                
                # Date filters
                if start_date:
                    try:
                        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                        if alert.created_at < start_dt:
                            continue
                    except ValueError:
                        return jsonify({'error': 'Invalid start_date format'}), 400
                
                if end_date:
                    try:
                        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        if alert.created_at > end_dt:
                            continue
                    except ValueError:
                        return jsonify({'error': 'Invalid end_date format'}), 400
                
                filtered_alerts.append(alert)
            
            # Convert alerts to dictionary format
            alert_data = []
            for alert in filtered_alerts:
                alert_data.append({
                    'id': alert.id,
                    'rule_name': alert.rule_name,
                    'severity': alert.severity.value,
                    'status': alert.status.value,
                    'message': alert.message,
                    'value': alert.value,
                    'threshold': alert.threshold,
                    'labels': alert.labels,
                    'created_at': alert.created_at.isoformat(),
                    'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                    'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                    'acknowledged_by': alert.acknowledged_by,
                    'resolved_by': alert.resolved_by
                })
            
            return jsonify({
                'success': True,
                'alerts': alert_data,
                'count': len(alert_data)
            })
            
        except Exception as e:
            logger.error("Error getting alert history", error=str(e))
            return jsonify({
                'success': False,
                'error': 'Internal server error'
            }), 500
    
    @alert_bp.route('/active', methods=['GET'])
    async def get_active_alerts(self):
        """
        Get active alerts.
        
        Returns:
            JSON response with active alerts
        """
        try:
            alerts = self.alerting_service.get_active_alerts()
            
            # Convert alerts to dictionary format
            alert_data = []
            for alert in alerts:
                alert_data.append({
                    'id': alert.id,
                    'rule_name': alert.rule_name,
                    'severity': alert.severity.value,
                    'status': alert.status.value,
                    'message': alert.message,
                    'value': alert.value,
                    'threshold': alert.threshold,
                    'labels': alert.labels,
                    'created_at': alert.created_at.isoformat(),
                    'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                    'acknowledged_by': alert.acknowledged_by
                })
            
            return jsonify({
                'success': True,
                'alerts': alert_data,
                'count': len(alert_data)
            })
            
        except Exception as e:
            logger.error("Error getting active alerts", error=str(e))
            return jsonify({
                'success': False,
                'error': 'Internal server error'
            }), 500
    
    @alert_bp.route('/test', methods=['POST'])
    async def test_alert(self):
        """
        Test alert configuration.
        
        Request body:
        {
            "rule_name": "string",
            "channels": ["email", "telegram"]
        }
        
        Returns:
            JSON response with test results
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            rule_name = data.get('rule_name')
            channels = data.get('channels', ['email', 'telegram'])
            
            if not rule_name:
                return jsonify({'error': 'rule_name is required'}), 400
            
            # Create test alert
            from .alerting_service import Alert, AlertSeverity, AlertStatus
            
            test_alert = Alert(
                id='test_alert_001',
                rule_name=rule_name,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.ACTIVE,
                message=f'Test alert for rule: {rule_name}',
                value=100.0,
                threshold=50.0,
                labels={'test': 'true'},
                created_at=datetime.now()
            )
            
            # Test notification channels
            results = {}
            for channel_name in channels:
                if channel_name in self.alerting_service.notification_channels:
                    channel = self.alerting_service.notification_channels[channel_name]
                    try:
                        success = await channel.send_alert(test_alert)
                        results[channel_name] = {
                            'success': success,
                            'message': 'Test notification sent' if success else 'Test notification failed'
                        }
                    except Exception as e:
                        results[channel_name] = {
                            'success': False,
                            'message': f'Error: {str(e)}'
                        }
                else:
                    results[channel_name] = {
                        'success': False,
                        'message': 'Channel not configured'
                    }
            
            logger.info("Alert test completed", rule_name=rule_name, results=results)
            
            return jsonify({
                'success': True,
                'message': 'Alert test completed',
                'rule_name': rule_name,
                'results': results
            })
            
        except Exception as e:
            logger.error("Error testing alert", error=str(e))
            return jsonify({
                'success': False,
                'error': 'Internal server error'
            }), 500
    
    @alert_bp.route('/statistics', methods=['GET'])
    async def get_alert_statistics(self):
        """
        Get alert statistics.
        
        Returns:
            JSON response with alert statistics
        """
        try:
            stats = self.alerting_service.get_alert_statistics()
            
            return jsonify({
                'success': True,
                'statistics': stats
            })
            
        except Exception as e:
            logger.error("Error getting alert statistics", error=str(e))
            return jsonify({
                'success': False,
                'error': 'Internal server error'
            }), 500
    
    @alert_bp.route('/health', methods=['GET'])
    async def health_check(self):
        """
        Health check for alerting system.
        
        Returns:
            JSON response with system health status
        """
        try:
            # Check if alerting service is operational
            active_alerts = len(self.alerting_service.get_active_alerts())
            total_rules = len(self.alerting_service.alert_rules)
            notification_channels = len(self.alerting_service.notification_channels)
            
            health_status = {
                'status': 'healthy',
                'active_alerts': active_alerts,
                'total_rules': total_rules,
                'notification_channels': notification_channels,
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify({
                'success': True,
                'health': health_status
            })
            
        except Exception as e:
            logger.error("Error in health check", error=str(e))
            return jsonify({
                'success': False,
                'error': 'Health check failed',
                'status': 'unhealthy'
            }), 500


def create_alert_api(alerting_service):
    """
    Create and configure alert API.
    
    Args:
        alerting_service: AlertingService instance
        
    Returns:
        Configured Flask Blueprint
    """
    api = AlertAPI(alerting_service)
    
    # Register routes
    alert_bp.add_url_rule('/acknowledge', 'acknowledge_alert', 
                         api.acknowledge_alert, methods=['POST'])
    alert_bp.add_url_rule('/resolve', 'resolve_alert', 
                         api.resolve_alert, methods=['POST'])
    alert_bp.add_url_rule('/history', 'get_alert_history', 
                         api.get_alert_history, methods=['GET'])
    alert_bp.add_url_rule('/active', 'get_active_alerts', 
                         api.get_active_alerts, methods=['GET'])
    alert_bp.add_url_rule('/test', 'test_alert', 
                         api.test_alert, methods=['POST'])
    alert_bp.add_url_rule('/statistics', 'get_alert_statistics', 
                         api.get_alert_statistics, methods=['GET'])
    alert_bp.add_url_rule('/health', 'health_check', 
                         api.health_check, methods=['GET'])
    
    return alert_bp
