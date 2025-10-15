"""
Notification channels for GRODT alerting system.

Provides notification delivery via multiple channels:
- Email notifications via MailDiver API
- Telegram bot notifications
- Future extensibility for other channels
"""

from .email_notification import EmailNotificationChannel
from .telegram_notification import TelegramNotificationChannel

__all__ = [
    'EmailNotificationChannel',
    'TelegramNotificationChannel'
]
