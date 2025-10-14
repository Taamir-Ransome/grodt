"""
Unit tests for Robinhood connector.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from grodtd.connectors.robinhood import RobinhoodAuth, RobinhoodConnector, create_robinhood_connector
from grodtd.storage.interfaces import OHLCVBar


class TestRobinhoodAuth:
    """Test Robinhood authentication."""
    
    def test_auth_initialization(self):
        """Test auth initialization."""
        auth = RobinhoodAuth("test_user", "test_pass")
        assert auth.username == "test_user"
        assert auth.password == "test_pass"
        assert auth.mfa_code is None
        assert auth.access_token is None
        assert auth.refresh_token is None
    
    def test_auth_with_mfa(self):
        """Test auth initialization with MFA."""
        auth = RobinhoodAuth("test_user", "test_pass", "123456")
        assert auth.mfa_code == "123456"
    
    def test_token_validation(self):
        """Test token validation."""
        auth = RobinhoodAuth("test_user", "test_pass")
        
        # No token
        assert not auth.is_token_valid()
        
        # Expired token
        auth.access_token = "test_token"
        auth.token_expires_at = datetime.now() - timedelta(hours=1)
        assert not auth.is_token_valid()
        
        # Valid token
        auth.token_expires_at = datetime.now() + timedelta(hours=1)
        assert auth.is_token_valid()
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Test successful authentication."""
        auth = RobinhoodAuth("test_user", "test_pass")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 86400
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await auth.authenticate()
            
            assert result is True
            assert auth.access_token == "test_access_token"
            assert auth.refresh_token == "test_refresh_token"
            assert auth.token_expires_at is not None
    
    @pytest.mark.asyncio
    async def test_authenticate_failure(self):
        """Test authentication failure."""
        auth = RobinhoodAuth("test_user", "test_pass")
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await auth.authenticate()
            
            assert result is False
            assert auth.access_token is None


class TestRobinhoodConnector:
    """Test Robinhood connector."""
    
    def test_connector_initialization(self):
        """Test connector initialization."""
        auth = RobinhoodAuth("test_user", "test_pass")
        connector = RobinhoodConnector(auth)
        
        assert connector.auth == auth
        assert connector.base_url == "https://api.robinhood.com"
        assert connector.client is None
        assert connector._rate_limit_delay == 0.5
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        auth = RobinhoodAuth("test_user", "test_pass")
        auth.access_token = "test_token"
        auth.token_expires_at = datetime.now() + timedelta(hours=1)
        
        connector = RobinhoodConnector(auth)
        
        with patch('httpx.AsyncClient') as mock_client:
            await connector.connect()
            
            assert connector.client is not None
            assert connector.client.headers["Authorization"] == "Bearer test_token"
    
    @pytest.mark.asyncio
    async def test_connect_authentication_required(self):
        """Test connection when authentication is required."""
        auth = RobinhoodAuth("test_user", "test_pass")
        connector = RobinhoodConnector(auth)
        
        with patch.object(auth, 'authenticate', return_value=True) as mock_auth:
            with patch('httpx.AsyncClient'):
                await connector.connect()
                
                mock_auth.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_historical_data(self):
        """Test getting historical data."""
        auth = RobinhoodAuth("test_user", "test_pass")
        auth.access_token = "test_token"
        auth.token_expires_at = datetime.now() + timedelta(hours=1)
        
        connector = RobinhoodConnector(auth)
        
        # Mock the connector's client
        mock_client = AsyncMock()
        connector.client = mock_client
        
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data_points": [
                {
                    "begins_at": "2024-01-01T00:00:00Z",
                    "open_price": "100.0",
                    "high_price": "105.0",
                    "low_price": "95.0",
                    "close_price": "102.0",
                    "volume": "1000.0"
                }
            ]
        }
        mock_client.request.return_value = mock_response
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)
        
        bars = await connector.get_historical_data("BTC", start_date, end_date, "1m")
        
        assert len(bars) == 1
        assert isinstance(bars[0], OHLCVBar)
        assert bars[0].open == 100.0
        assert bars[0].high == 105.0
        assert bars[0].low == 95.0
        assert bars[0].close == 102.0
        assert bars[0].volume == 1000.0
    
    @pytest.mark.asyncio
    async def test_get_real_time_data(self):
        """Test getting real-time data."""
        auth = RobinhoodAuth("test_user", "test_pass")
        auth.access_token = "test_token"
        auth.token_expires_at = datetime.now() + timedelta(hours=1)
        
        connector = RobinhoodConnector(auth)
        
        # Mock the connector's client
        mock_client = AsyncMock()
        connector.client = mock_client
        
        # Mock the quotes response
        mock_quotes_response = MagicMock()
        mock_quotes_response.status_code = 200
        mock_quotes_response.json.return_value = {
            "results": [
                {
                    "symbol": "BTC",
                    "bid_price": "100.0",
                    "ask_price": "101.0",
                    "bid_size": "1.0",
                    "ask_size": "1.0",
                    "updated_at": "2024-01-01T00:00:00Z"
                }
            ]
        }
        mock_client.request.return_value = mock_quotes_response
        
        bar = await connector.get_real_time_data("BTC")
        
        assert isinstance(bar, OHLCVBar)
        assert bar.open == 100.5  # (100.0 + 101.0) / 2
        assert bar.high == 100.5
        assert bar.low == 100.5
        assert bar.close == 100.5


class TestFactoryFunction:
    """Test factory function."""
    
    def test_create_connector(self):
        """Test creating connector with factory function."""
        connector = create_robinhood_connector("test_user", "test_pass")
        
        assert isinstance(connector, RobinhoodConnector)
        assert connector.auth.username == "test_user"
        assert connector.auth.password == "test_pass"
    
    def test_create_connector_with_mfa(self):
        """Test creating connector with MFA."""
        connector = create_robinhood_connector("test_user", "test_pass", "123456")
        
        assert isinstance(connector, RobinhoodConnector)
        assert connector.auth.mfa_code == "123456"


if __name__ == "__main__":
    pytest.main([__file__])
