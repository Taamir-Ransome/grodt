"""
Telegram notification channel for GRODT alerts.

Provides instant messaging notifications via Telegram bot API with:
- Secure bot token management via environment variables
- Rich message formatting with emojis and markdown
- Rate limiting and error handling
- Support for different alert types
"""

import asyncio
import aiohttp
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

import structlog

logger = structlog.get_logger(__name__)


class TelegramNotificationChannel:
    """
    Telegram notification channel for GRODT alerts.
    
    Handles instant messaging delivery via Telegram bot API with
    proper formatting, rate limiting, and error handling.
    """
    
    def __init__(self, 
                 bot_token: Optional[str] = None,
                 chat_id: Optional[str] = None,
                 rate_limit_per_minute: int = 30):
        """
        Initialize Telegram notification channel.
        
        Args:
            bot_token: Telegram bot token (defaults to TELEGRAM_BOT_TOKEN env var)
            chat_id: Telegram chat ID (defaults to TELEGRAM_CHAT_ID env var)
            rate_limit_per_minute: Rate limit for message sending
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")
        
        self.rate_limit_per_minute = rate_limit_per_minute
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Rate limiting
        self._sent_messages = []
        self._last_cleanup = time.time()
        
        logger.info("Telegram notification channel initialized", 
                   chat_id=self.chat_id,
                   rate_limit=rate_limit_per_minute)
    
    def _cleanup_rate_limit(self) -> None:
        """Clean up old entries from rate limiting."""
        current_time = time.time()
        if current_time - self._last_cleanup > 60:  # Clean up every minute
            cutoff_time = current_time - 60  # Keep only last minute
            self._sent_messages = [t for t in self._sent_messages if t > cutoff_time]
            self._last_cleanup = current_time
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        self._cleanup_rate_limit()
        return len(self._sent_messages) < self.rate_limit_per_minute
    
    def _format_alert_message(self, alert) -> str:
        """
        Format alert message for Telegram.
        
        Args:
            alert: Alert object to format
            
        Returns:
            Formatted message string
        """
        # Choose emoji based on severity
        severity_emojis = {
            'low': '🟢',
            'medium': '🟡', 
            'high': '🟠',
            'critical': '🔴'
        }
        
        emoji = severity_emojis.get(alert.severity.value, '🔔')
        
        # Format message based on alert type
        if 'system' in alert.rule_name.lower() or 'failure' in alert.rule_name.lower():
            message = f"""
{emoji} *SYSTEM FAILURE ALERT*

🚨 *Alert ID:* `{alert.id}`
⚡ *Severity:* {alert.severity.value.upper()}
📋 *Rule:* {alert.rule_name}
💬 *Message:* {alert.message}
📊 *Value:* {alert.value}
🎯 *Threshold:* {alert.threshold}
⏰ *Time:* {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

🔧 *Recommended Actions:*
• Check system logs for detailed error information
• Verify system resources (CPU, memory, disk)
• Check database connectivity and performance
• Review recent configuration changes

_This is an automated alert from the GRODT trading system._
            """
        elif 'trading' in alert.rule_name.lower() or 'pnl' in alert.rule_name.lower() or 'drawdown' in alert.rule_name.lower():
            message = f"""
{emoji} *TRADING PERFORMANCE ALERT*

📊 *Alert ID:* `{alert.id}`
⚡ *Severity:* {alert.severity.value.upper()}
📋 *Rule:* {alert.rule_name}
💬 *Message:* {alert.message}
📊 *Value:* {alert.value}
🎯 *Threshold:* {alert.threshold}
⏰ *Time:* {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

📈 *Performance Analysis:*
• Review recent trading performance metrics
• Check for unusual market conditions
• Analyze strategy effectiveness
• Consider position sizing adjustments

_This trading performance alert requires attention._
            """
        elif 'regime' in alert.rule_name.lower() or 'market' in alert.rule_name.lower():
            message = f"""
{emoji} *MARKET REGIME CHANGE ALERT*

🔄 *Alert ID:* `{alert.id}`
⚡ *Severity:* {alert.severity.value.upper()}
📋 *Rule:* {alert.rule_name}
💬 *Message:* {alert.message}
📊 *Value:* {alert.value}
🎯 *Threshold:* {alert.threshold}
⏰ *Time:* {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

🌊 *Regime Analysis:*
• Market conditions have shifted significantly
• Review strategy gating and performance
• Consider adjusting risk parameters
• Monitor for continued regime stability

_Market regime changes may require strategy adjustments._
            """
        else:
            message = f"""
{emoji} *SYSTEM ALERT*

🔔 *Alert ID:* `{alert.id}`
⚡ *Severity:* {alert.severity.value.upper()}
📋 *Rule:* {alert.rule_name}
💬 *Message:* {alert.message}
📊 *Value:* {alert.value}
🎯 *Threshold:* {alert.threshold}
⏰ *Time:* {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

_This is an automated alert from the GRODT trading system._
            """
        
        return message.strip()
    
    async def send_alert(self, alert) -> bool:
        """
        Send Telegram alert.
        
        Args:
            alert: Alert object to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check rate limit
            if not self._check_rate_limit():
                logger.warning("Rate limit exceeded for Telegram notifications")
                return False
            
            # Format message
            message = self._format_alert_message(alert)
            
            # Prepare request data
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            # Send via Telegram API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        if response_data.get('ok'):
                            # Track successful send
                            self._sent_messages.append(time.time())
                            
                            logger.info("Telegram alert sent successfully", 
                                      alert_id=alert.id,
                                      severity=alert.severity.value)
                            return True
                        else:
                            logger.error("Telegram API returned error", 
                                       alert_id=alert.id,
                                       error=response_data.get('description'))
                            return False
                    else:
                        error_text = await response.text()
                        logger.error("Failed to send Telegram alert", 
                                   alert_id=alert.id,
                                   status_code=response.status,
                                   error=error_text)
                        return False
            
        except asyncio.TimeoutError:
            logger.error("Telegram notification timeout", alert_id=alert.id)
            return False
        except Exception as e:
            logger.error("Error sending Telegram alert", 
                        alert_id=alert.id,
                        error=str(e))
            return False
    
    async def send_test_message(self) -> bool:
        """
        Send a test message to verify configuration.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            test_message = f"""
✅ *GRODT Telegram Notification Test*

🤖 *Bot Status:* Active
⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
📱 *Chat ID:* `{self.chat_id}`

_If you received this message, the GRODT Telegram notification system is configured correctly._
            """.strip()
            
            data = {
                'chat_id': self.chat_id,
                'text': test_message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        if response_data.get('ok'):
                            logger.info("Test Telegram message sent successfully")
                            return True
                        else:
                            logger.error("Telegram API returned error", 
                                       error=response_data.get('description'))
                            return False
                    else:
                        error_text = await response.text()
                        logger.error("Failed to send test Telegram message", 
                                   status_code=response.status,
                                   error=error_text)
                        return False
            
        except Exception as e:
            logger.error("Error sending test Telegram message", error=str(e))
            return False
    
    async def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """
        Get bot information to verify configuration.
        
        Returns:
            Bot information dictionary or None if failed
        """
        try:
            info_url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    info_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok'):
                            return data.get('result')
                        else:
                            logger.error("Telegram API returned error", 
                                       error=data.get('description'))
                            return None
                    else:
                        logger.error("Failed to get bot info", 
                                   status_code=response.status)
                        return None
            
        except Exception as e:
            logger.error("Error getting bot info", error=str(e))
            return None
