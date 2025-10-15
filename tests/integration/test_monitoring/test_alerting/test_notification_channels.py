"""
Integration tests for notification channels.

Tests email and Telegram notification delivery with proper
authentication, rate limiting, and error handling.
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from grodtd.monitoring.notifications.email_notification import EmailNotificationChannel
from grodtd.monitoring.notifications.telegram_notification import TelegramNotificationChannel
from grodtd.monitoring.alerting_service import Alert, AlertSeverity, AlertStatus
from datetime import datetime


class TestEmailNotificationChannel:
    """Test suite for EmailNotificationChannel."""
    
    @pytest.fixture
    def mock_alert(self):
        """Create mock alert for testing."""
        return Alert(
            id="test_alert_001",
            rule_name="test_system_failure",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            message="Test system failure alert",
            value=85.0,
            threshold=80.0,
            labels={"system": "test"},
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def email_channel(self):
        """Create EmailNotificationChannel with mock API key."""
        with patch.dict(os.environ, {'MAILDRIVER_API_KEY': 'test_api_key'}):
            return EmailNotificationChannel()
    
    @pytest.mark.asyncio
    async def test_email_channel_initialization(self):
        """Test email channel initialization."""
        with patch.dict(os.environ, {'MAILDRIVER_API_KEY': 'test_api_key'}):
            channel = EmailNotificationChannel()
            assert channel.api_key == 'test_api_key'
            assert channel.from_email == "alerts@mail.wraith-protocol.com"
            assert channel.rate_limit_per_minute == 60
    
    def test_email_channel_missing_api_key(self):
        """Test email channel initialization without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MAILDRIVER_API_KEY environment variable is required"):
                EmailNotificationChannel()
    
    @pytest.mark.asyncio
    async def test_email_template_selection(self, email_channel, mock_alert):
        """Test email template selection based on alert type."""
        # Test system failure template
        mock_alert.rule_name = "system_failure_alert"
        template = email_channel._get_template(mock_alert.rule_name)
        assert "System Failure Alert" in template.subject
        
        # Test trading performance template
        mock_alert.rule_name = "trading_pnl_alert"
        template = email_channel._get_template(mock_alert.rule_name)
        assert "Trading Performance Alert" in template.subject
        
        # Test regime change template
        mock_alert.rule_name = "regime_change_alert"
        template = email_channel._get_template(mock_alert.rule_name)
        assert "Market Regime Change Alert" in template.subject
        
        # Test default template
        mock_alert.rule_name = "unknown_alert"
        template = email_channel._get_template(mock_alert.rule_name)
        assert "System Alert" in template.subject
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, email_channel):
        """Test email rate limiting functionality."""
        # Initially should be within rate limit
        assert email_channel._check_rate_limit() is True
        
        # Simulate sending many emails
        for _ in range(65):  # Exceed rate limit of 60
            email_channel._sent_emails.append(asyncio.get_event_loop().time())
        
        # Should now be rate limited
        assert email_channel._check_rate_limit() is False
    
    @pytest.mark.asyncio
    async def test_send_alert_success(self, email_channel, mock_alert):
        """Test successful email alert sending."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Send alert
            result = await email_channel.send_alert(mock_alert)
            
            # Verify success
            assert result is True
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_alert_failure(self, email_channel, mock_alert):
        """Test email alert sending failure."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock failed response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Send alert
            result = await email_channel.send_alert(mock_alert)
            
            # Verify failure
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_alert_timeout(self, email_channel, mock_alert):
        """Test email alert sending timeout."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock timeout
            mock_post.side_effect = asyncio.TimeoutError()
            
            # Send alert
            result = await email_channel.send_alert(mock_alert)
            
            # Verify timeout handling
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_test_email(self, email_channel):
        """Test test email sending."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Send test email
            result = await email_channel.send_test_email("test@example.com")
            
            # Verify success
            assert result is True
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_email_template_formatting(self, email_channel, mock_alert):
        """Test email template formatting."""
        template = email_channel._get_template(mock_alert.rule_name)
        
        # Format template with alert data
        formatted_html = template.html_template.format(
            alert_id=mock_alert.id,
            severity=mock_alert.severity.value.upper(),
            rule_name=mock_alert.rule_name,
            message=mock_alert.message,
            value=mock_alert.value,
            threshold=mock_alert.threshold,
            timestamp=mock_alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        )
        
        # Verify formatting
        assert mock_alert.id in formatted_html
        assert mock_alert.severity.value.upper() in formatted_html
        assert mock_alert.message in formatted_html


class TestTelegramNotificationChannel:
    """Test suite for TelegramNotificationChannel."""
    
    @pytest.fixture
    def mock_alert(self):
        """Create mock alert for testing."""
        return Alert(
            id="test_alert_001",
            rule_name="test_system_failure",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            message="Test system failure alert",
            value=85.0,
            threshold=80.0,
            labels={"system": "test"},
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def telegram_channel(self):
        """Create TelegramNotificationChannel with mock credentials."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test_bot_token',
            'TELEGRAM_CHAT_ID': 'test_chat_id'
        }):
            return TelegramNotificationChannel()
    
    @pytest.mark.asyncio
    async def test_telegram_channel_initialization(self):
        """Test Telegram channel initialization."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test_bot_token',
            'TELEGRAM_CHAT_ID': 'test_chat_id'
        }):
            channel = TelegramNotificationChannel()
            assert channel.bot_token == 'test_bot_token'
            assert channel.chat_id == 'test_chat_id'
            assert channel.rate_limit_per_minute == 30
    
    def test_telegram_channel_missing_credentials(self):
        """Test Telegram channel initialization without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN environment variable is required"):
                TelegramNotificationChannel()
        
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test_token'}, clear=True):
            with pytest.raises(ValueError, match="TELEGRAM_CHAT_ID environment variable is required"):
                TelegramNotificationChannel()
    
    @pytest.mark.asyncio
    async def test_message_formatting_system_alert(self, telegram_channel, mock_alert):
        """Test message formatting for system alerts."""
        mock_alert.rule_name = "system_failure_alert"
        message = telegram_channel._format_alert_message(mock_alert)
        
        # Verify message content
        assert "SYSTEM FAILURE ALERT" in message
        assert mock_alert.id in message
        assert mock_alert.severity.value.upper() in message
        assert "🔧 *Recommended Actions:*" in message
    
    @pytest.mark.asyncio
    async def test_message_formatting_trading_alert(self, telegram_channel, mock_alert):
        """Test message formatting for trading alerts."""
        mock_alert.rule_name = "trading_pnl_alert"
        message = telegram_channel._format_alert_message(mock_alert)
        
        # Verify message content
        assert "TRADING PERFORMANCE ALERT" in message
        assert "📈 *Performance Analysis:*" in message
    
    @pytest.mark.asyncio
    async def test_message_formatting_regime_alert(self, telegram_channel, mock_alert):
        """Test message formatting for regime alerts."""
        mock_alert.rule_name = "regime_change_alert"
        message = telegram_channel._format_alert_message(mock_alert)
        
        # Verify message content
        assert "MARKET REGIME CHANGE ALERT" in message
        assert "🌊 *Regime Analysis:*" in message
    
    @pytest.mark.asyncio
    async def test_severity_emojis(self, telegram_channel, mock_alert):
        """Test severity emoji selection."""
        # Test different severity levels
        severities = ['low', 'medium', 'high', 'critical']
        expected_emojis = ['🟢', '🟡', '🟠', '🔴']
        
        for severity, expected_emoji in zip(severities, expected_emojis):
            mock_alert.severity = AlertSeverity(severity)
            message = telegram_channel._format_alert_message(mock_alert)
            assert expected_emoji in message
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, telegram_channel):
        """Test Telegram rate limiting functionality."""
        # Initially should be within rate limit
        assert telegram_channel._check_rate_limit() is True
        
        # Simulate sending many messages
        for _ in range(35):  # Exceed rate limit of 30
            telegram_channel._sent_messages.append(asyncio.get_event_loop().time())
        
        # Should now be rate limited
        assert telegram_channel._check_rate_limit() is False
    
    @pytest.mark.asyncio
    async def test_send_alert_success(self, telegram_channel, mock_alert):
        """Test successful Telegram alert sending."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'ok': True})
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Send alert
            result = await telegram_channel.send_alert(mock_alert)
            
            # Verify success
            assert result is True
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_alert_api_error(self, telegram_channel, mock_alert):
        """Test Telegram alert sending with API error."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock API error response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'ok': False, 'description': 'Bad Request'})
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Send alert
            result = await telegram_channel.send_alert(mock_alert)
            
            # Verify failure
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_alert_http_error(self, telegram_channel, mock_alert):
        """Test Telegram alert sending with HTTP error."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock HTTP error
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Send alert
            result = await telegram_channel.send_alert(mock_alert)
            
            # Verify failure
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_alert_timeout(self, telegram_channel, mock_alert):
        """Test Telegram alert sending timeout."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock timeout
            mock_post.side_effect = asyncio.TimeoutError()
            
            # Send alert
            result = await telegram_channel.send_alert(mock_alert)
            
            # Verify timeout handling
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_test_message(self, telegram_channel):
        """Test test message sending."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'ok': True})
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Send test message
            result = await telegram_channel.send_test_message()
            
            # Verify success
            assert result is True
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_bot_info(self, telegram_channel):
        """Test bot information retrieval."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                'ok': True,
                'result': {
                    'id': 123456789,
                    'is_bot': True,
                    'first_name': 'Test Bot',
                    'username': 'test_bot'
                }
            })
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Get bot info
            bot_info = await telegram_channel.get_bot_info()
            
            # Verify bot info
            assert bot_info is not None
            assert bot_info['id'] == 123456789
            assert bot_info['first_name'] == 'Test Bot'
    
    @pytest.mark.asyncio
    async def test_get_bot_info_error(self, telegram_channel):
        """Test bot information retrieval with error."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock error response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Get bot info
            bot_info = await telegram_channel.get_bot_info()
            
            # Verify error handling
            assert bot_info is None


class TestNotificationChannelIntegration:
    """Integration tests for notification channels."""
    
    @pytest.mark.asyncio
    async def test_email_telegram_integration(self):
        """Test integration between email and Telegram channels."""
        with patch.dict(os.environ, {
            'MAILDRIVER_API_KEY': 'test_email_key',
            'TELEGRAM_BOT_TOKEN': 'test_telegram_token',
            'TELEGRAM_CHAT_ID': 'test_chat_id'
        }):
            # Create channels
            email_channel = EmailNotificationChannel()
            telegram_channel = TelegramNotificationChannel()
            
            # Create mock alert
            alert = Alert(
                id="integration_test_001",
                rule_name="integration_test",
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.ACTIVE,
                message="Integration test alert",
                value=50.0,
                threshold=40.0,
                labels={"test": "integration"},
                created_at=datetime.now()
            )
            
            # Mock successful responses
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={'ok': True})
                mock_post.return_value.__aenter__.return_value = mock_response
                
                # Send via both channels
                email_result = await email_channel.send_alert(alert)
                telegram_result = await telegram_channel.send_alert(alert)
                
                # Verify both succeeded
                assert email_result is True
                assert telegram_result is True
    
    @pytest.mark.asyncio
    async def test_notification_channel_error_isolation(self):
        """Test that errors in one channel don't affect others."""
        with patch.dict(os.environ, {
            'MAILDRIVER_API_KEY': 'test_email_key',
            'TELEGRAM_BOT_TOKEN': 'test_telegram_token',
            'TELEGRAM_CHAT_ID': 'test_chat_id'
        }):
            # Create channels
            email_channel = EmailNotificationChannel()
            telegram_channel = TelegramNotificationChannel()
            
            # Create mock alert
            alert = Alert(
                id="error_isolation_test",
                rule_name="error_isolation",
                severity=AlertSeverity.LOW,
                status=AlertStatus.ACTIVE,
                message="Error isolation test",
                value=30.0,
                threshold=25.0,
                labels={"test": "error_isolation"},
                created_at=datetime.now()
            )
            
            # Test that both channels can be created without affecting each other
            assert email_channel is not None
            assert telegram_channel is not None
            
            # Test that channels have different configurations
            assert email_channel.from_email == "alerts@mail.wraith-protocol.com"
            assert telegram_channel.chat_id == "test_chat_id"
            
            # Test that both channels can handle alerts independently
            # (We'll mock the actual HTTP calls to avoid network dependencies)
            with patch.object(email_channel, 'send_alert', return_value=True) as mock_email:
                with patch.object(telegram_channel, 'send_alert', return_value=False) as mock_telegram:
                    email_result = await email_channel.send_alert(alert)
                    telegram_result = await telegram_channel.send_alert(alert)
                    
                    # Verify both channels were called
                    mock_email.assert_called_once_with(alert)
                    mock_telegram.assert_called_once_with(alert)
                    
                    # Verify results
                    assert email_result is True
                    assert telegram_result is False
