"""
Email notification channel using MailDiver API.

Provides secure email notifications for GRODT alerts with:
- MailDiver API integration
- Secure API key management via environment variables
- Email templates for different alert types
- Rate limiting and throttling
"""

import asyncio
import aiohttp
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EmailTemplate:
    """Email template configuration."""
    subject: str
    html_template: str
    text_template: str


class EmailNotificationChannel:
    """
    Email notification channel using MailDiver API.
    
    Handles secure email delivery for GRODT alerts with proper
    authentication, rate limiting, and error handling.
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 from_email: str = "alerts@mail.wraith-protocol.com",
                 rate_limit_per_minute: int = 60):
        """
        Initialize email notification channel.
        
        Args:
            api_key: MailDiver API key (defaults to MAILDRIVER_API_KEY env var)
            from_email: Sender email address
            rate_limit_per_minute: Rate limit for email sending
        """
        self.api_key = api_key or os.getenv('MAILDRIVER_API_KEY')
        if not self.api_key:
            raise ValueError("MAILDRIVER_API_KEY environment variable is required")
        
        self.from_email = from_email
        self.rate_limit_per_minute = rate_limit_per_minute
        self.api_url = "https://api.maildiver.com/v1/messages"
        
        # Rate limiting
        self._sent_emails = []
        self._last_cleanup = time.time()
        
        # Email templates
        self._templates = self._initialize_templates()
        
        logger.info("Email notification channel initialized", 
                   from_email=from_email,
                   rate_limit=rate_limit_per_minute)
    
    def _initialize_templates(self) -> Dict[str, EmailTemplate]:
        """Initialize email templates for different alert types."""
        return {
            'system_failure': EmailTemplate(
                subject="🚨 GRODT System Failure Alert",
                html_template="""
                <html>
                <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <div style="background-color: #dc3545; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; font-size: 24px;">🚨 System Failure Alert</h1>
                        </div>
                        <div style="padding: 20px;">
                            <h2 style="color: #dc3545; margin-top: 0;">Alert Details</h2>
                            <p><strong>Alert ID:</strong> {alert_id}</p>
                            <p><strong>Severity:</strong> <span style="color: #dc3545; font-weight: bold;">{severity}</span></p>
                            <p><strong>Rule:</strong> {rule_name}</p>
                            <p><strong>Message:</strong> {message}</p>
                            <p><strong>Value:</strong> {value}</p>
                            <p><strong>Threshold:</strong> {threshold}</p>
                            <p><strong>Time:</strong> {timestamp}</p>
                            
                            <h3 style="color: #333;">Recommended Actions</h3>
                            <ul>
                                <li>Check system logs for detailed error information</li>
                                <li>Verify system resources (CPU, memory, disk)</li>
                                <li>Check database connectivity and performance</li>
                                <li>Review recent configuration changes</li>
                            </ul>
                            
                            <div style="margin-top: 30px; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #dc3545; border-radius: 4px;">
                                <p style="margin: 0; font-size: 14px; color: #666;">
                                    This is an automated alert from the GRODT trading system. 
                                    Please investigate and resolve the issue promptly.
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
                """,
                text_template="""
                🚨 GRODT System Failure Alert
                
                Alert ID: {alert_id}
                Severity: {severity}
                Rule: {rule_name}
                Message: {message}
                Value: {value}
                Threshold: {threshold}
                Time: {timestamp}
                
                Recommended Actions:
                - Check system logs for detailed error information
                - Verify system resources (CPU, memory, disk)
                - Check database connectivity and performance
                - Review recent configuration changes
                
                This is an automated alert from the GRODT trading system.
                """
            ),
            
            'trading_performance': EmailTemplate(
                subject="📊 GRODT Trading Performance Alert",
                html_template="""
                <html>
                <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <div style="background-color: #ffc107; color: #212529; padding: 20px; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; font-size: 24px;">📊 Trading Performance Alert</h1>
                        </div>
                        <div style="padding: 20px;">
                            <h2 style="color: #ffc107; margin-top: 0;">Performance Alert Details</h2>
                            <p><strong>Alert ID:</strong> {alert_id}</p>
                            <p><strong>Severity:</strong> <span style="color: #ffc107; font-weight: bold;">{severity}</span></p>
                            <p><strong>Rule:</strong> {rule_name}</p>
                            <p><strong>Message:</strong> {message}</p>
                            <p><strong>Value:</strong> {value}</p>
                            <p><strong>Threshold:</strong> {threshold}</p>
                            <p><strong>Time:</strong> {timestamp}</p>
                            
                            <h3 style="color: #333;">Performance Analysis</h3>
                            <ul>
                                <li>Review recent trading performance metrics</li>
                                <li>Check for unusual market conditions</li>
                                <li>Analyze strategy effectiveness</li>
                                <li>Consider position sizing adjustments</li>
                            </ul>
                            
                            <div style="margin-top: 30px; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                                <p style="margin: 0; font-size: 14px; color: #856404;">
                                    This trading performance alert requires attention to maintain optimal system performance.
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
                """,
                text_template="""
                📊 GRODT Trading Performance Alert
                
                Alert ID: {alert_id}
                Severity: {severity}
                Rule: {rule_name}
                Message: {message}
                Value: {value}
                Threshold: {threshold}
                Time: {timestamp}
                
                Performance Analysis:
                - Review recent trading performance metrics
                - Check for unusual market conditions
                - Analyze strategy effectiveness
                - Consider position sizing adjustments
                
                This trading performance alert requires attention.
                """
            ),
            
            'regime_change': EmailTemplate(
                subject="🔄 GRODT Market Regime Change Alert",
                html_template="""
                <html>
                <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <div style="background-color: #17a2b8; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; font-size: 24px;">🔄 Market Regime Change Alert</h1>
                        </div>
                        <div style="padding: 20px;">
                            <h2 style="color: #17a2b8; margin-top: 0;">Regime Change Details</h2>
                            <p><strong>Alert ID:</strong> {alert_id}</p>
                            <p><strong>Severity:</strong> <span style="color: #17a2b8; font-weight: bold;">{severity}</span></p>
                            <p><strong>Rule:</strong> {rule_name}</p>
                            <p><strong>Message:</strong> {message}</p>
                            <p><strong>Value:</strong> {value}</p>
                            <p><strong>Threshold:</strong> {threshold}</p>
                            <p><strong>Time:</strong> {timestamp}</p>
                            
                            <h3 style="color: #333;">Regime Analysis</h3>
                            <ul>
                                <li>Market conditions have shifted significantly</li>
                                <li>Review strategy gating and performance</li>
                                <li>Consider adjusting risk parameters</li>
                                <li>Monitor for continued regime stability</li>
                            </ul>
                            
                            <div style="margin-top: 30px; padding: 15px; background-color: #d1ecf1; border-left: 4px solid #17a2b8; border-radius: 4px;">
                                <p style="margin: 0; font-size: 14px; color: #0c5460;">
                                    Market regime changes may require strategy adjustments for optimal performance.
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
                """,
                text_template="""
                🔄 GRODT Market Regime Change Alert
                
                Alert ID: {alert_id}
                Severity: {severity}
                Rule: {rule_name}
                Message: {message}
                Value: {value}
                Threshold: {threshold}
                Time: {timestamp}
                
                Regime Analysis:
                - Market conditions have shifted significantly
                - Review strategy gating and performance
                - Consider adjusting risk parameters
                - Monitor for continued regime stability
                
                Market regime changes may require strategy adjustments.
                """
            ),
            
            'default': EmailTemplate(
                subject="🔔 GRODT System Alert",
                html_template="""
                <html>
                <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <div style="background-color: #6c757d; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; font-size: 24px;">🔔 System Alert</h1>
                        </div>
                        <div style="padding: 20px;">
                            <h2 style="color: #6c757d; margin-top: 0;">Alert Details</h2>
                            <p><strong>Alert ID:</strong> {alert_id}</p>
                            <p><strong>Severity:</strong> <span style="color: #6c757d; font-weight: bold;">{severity}</span></p>
                            <p><strong>Rule:</strong> {rule_name}</p>
                            <p><strong>Message:</strong> {message}</p>
                            <p><strong>Value:</strong> {value}</p>
                            <p><strong>Threshold:</strong> {threshold}</p>
                            <p><strong>Time:</strong> {timestamp}</p>
                            
                            <div style="margin-top: 30px; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #6c757d; border-radius: 4px;">
                                <p style="margin: 0; font-size: 14px; color: #6c757d;">
                                    This is an automated alert from the GRODT trading system.
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
                """,
                text_template="""
                🔔 GRODT System Alert
                
                Alert ID: {alert_id}
                Severity: {severity}
                Rule: {rule_name}
                Message: {message}
                Value: {value}
                Threshold: {threshold}
                Time: {timestamp}
                
                This is an automated alert from the GRODT trading system.
                """
            )
        }
    
    def _get_template(self, alert_rule_name: str) -> EmailTemplate:
        """Get appropriate email template for alert type."""
        # Map rule names to templates
        if 'system' in alert_rule_name.lower() or 'failure' in alert_rule_name.lower():
            return self._templates['system_failure']
        elif 'trading' in alert_rule_name.lower() or 'pnl' in alert_rule_name.lower() or 'drawdown' in alert_rule_name.lower():
            return self._templates['trading_performance']
        elif 'regime' in alert_rule_name.lower() or 'market' in alert_rule_name.lower():
            return self._templates['regime_change']
        else:
            return self._templates['default']
    
    def _cleanup_rate_limit(self) -> None:
        """Clean up old entries from rate limiting."""
        current_time = time.time()
        if current_time - self._last_cleanup > 60:  # Clean up every minute
            cutoff_time = current_time - 60  # Keep only last minute
            self._sent_emails = [t for t in self._sent_emails if t > cutoff_time]
            self._last_cleanup = current_time
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        self._cleanup_rate_limit()
        return len(self._sent_emails) < self.rate_limit_per_minute
    
    async def send_alert(self, alert) -> bool:
        """
        Send email alert via MailDiver API.
        
        Args:
            alert: Alert object to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check rate limit
            if not self._check_rate_limit():
                logger.warning("Rate limit exceeded for email notifications")
                return False
            
            # Get template
            template = self._get_template(alert.rule_name)
            
            # Prepare email data
            email_data = {
                'from': {
                    'email': self.from_email,
                    'name': 'GRODT Trading System'
                },
                'to': [
                    {
                        'email': 'alerts@mail.wraith-protocol.com',  # Default recipient
                        'name': 'System Administrator'
                    }
                ],
                'subject': template.subject,
                'html': template.html_template.format(
                    alert_id=alert.id,
                    severity=alert.severity.value.upper(),
                    rule_name=alert.rule_name,
                    message=alert.message,
                    value=alert.value,
                    threshold=alert.threshold,
                    timestamp=alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
                ),
                'text': template.text_template.format(
                    alert_id=alert.id,
                    severity=alert.severity.value.upper(),
                    rule_name=alert.rule_name,
                    message=alert.message,
                    value=alert.value,
                    threshold=alert.threshold,
                    timestamp=alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
                )
            }
            
            # Send via MailDiver API
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=email_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        # Track successful send
                        self._sent_emails.append(time.time())
                        
                        logger.info("Email alert sent successfully", 
                                  alert_id=alert.id,
                                  severity=alert.severity.value)
                        return True
                    else:
                        error_text = await response.text()
                        logger.error("Failed to send email alert", 
                                   alert_id=alert.id,
                                   status_code=response.status,
                                   error=error_text)
                        return False
            
        except asyncio.TimeoutError:
            logger.error("Email notification timeout", alert_id=alert.id)
            return False
        except Exception as e:
            logger.error("Error sending email alert", 
                        alert_id=alert.id,
                        error=str(e))
            return False
    
    async def send_test_email(self, recipient: str) -> bool:
        """
        Send a test email to verify configuration.
        
        Args:
            recipient: Email address to send test to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            test_data = {
                'from': {
                    'email': self.from_email,
                    'name': 'GRODT Trading System'
                },
                'to': [
                    {
                        'email': recipient,
                        'name': 'Test Recipient'
                    }
                ],
                'subject': 'GRODT Email Notification Test',
                'html': '''
                <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2>✅ GRODT Email Notification Test</h2>
                    <p>This is a test email to verify that email notifications are working correctly.</p>
                    <p><strong>Time:</strong> {}</p>
                    <p>If you received this email, the GRODT email notification system is configured correctly.</p>
                </body>
                </html>
                '''.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')),
                'text': '''
                GRODT Email Notification Test
                
                This is a test email to verify that email notifications are working correctly.
                
                Time: {}
                
                If you received this email, the GRODT email notification system is configured correctly.
                '''.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=test_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        logger.info("Test email sent successfully", recipient=recipient)
                        return True
                    else:
                        error_text = await response.text()
                        logger.error("Failed to send test email", 
                                   recipient=recipient,
                                   status_code=response.status,
                                   error=error_text)
                        return False
            
        except Exception as e:
            logger.error("Error sending test email", 
                        recipient=recipient,
                        error=str(e))
            return False
