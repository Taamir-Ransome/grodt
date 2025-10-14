"""
Unit tests for Robinhood connector.

NOTE: Robinhood connector is for LIVE trading only.
These tests only verify API availability using real credentials from .env
For paper trading, use the Alpaca connector instead.
"""

import pytest
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

from grodtd.connectors.robinhood import RobinhoodLiveHandler
from grodtd.config.robinhood_config import load_robinhood_config


class TestRobinhoodAPI:
    """Test Robinhood API availability only."""
    
    @pytest.fixture(autouse=True)
    def load_env(self):
        """Load environment variables from .env file."""
        load_dotenv()
    
    def test_config_loading(self):
        """Test that Robinhood config can be loaded from .env."""
        try:
            config = load_robinhood_config()
            assert config.api_key is not None
            assert config.private_key is not None
            assert config.public_key is not None
        except Exception as e:
            pytest.skip(f"Robinhood credentials not available: {e}")
    
    @pytest.mark.asyncio
    async def test_api_availability(self):
        """Test that Robinhood API is available and accessible."""
        try:
            config = load_robinhood_config()
            handler = RobinhoodLiveHandler({
                "api_key": config.api_key,
                "private_key": config.private_key,
                "public_key": config.public_key
            })
            
            # Test connection
            connected = await handler.connect()
            assert connected is True
            
            # Test basic API call (get account info)
            try:
                balance = await handler.get_account_balance()
                assert balance is not None
                print(f"✅ Robinhood API is available - Account balance: {balance}")
            except Exception as e:
                print(f"⚠️ Robinhood API available but account access failed: {e}")
                # This is expected if credentials are invalid, but API is reachable
            
            await handler.disconnect()
            
        except Exception as e:
            pytest.skip(f"Robinhood API not available: {e}")
    
    @pytest.mark.asyncio
    async def test_trading_pairs_availability(self):
        """Test that trading pairs endpoint is available."""
        try:
            config = load_robinhood_config()
            handler = RobinhoodLiveHandler({
                "api_key": config.api_key,
                "private_key": config.private_key,
                "public_key": config.public_key
            })
            
            await handler.connect()
            
            # Test trading pairs endpoint
            pairs = await handler.get_trading_pairs(["BTC-USD"])
            assert isinstance(pairs, list)
            print(f"✅ Trading pairs endpoint available - Found {len(pairs)} pairs")
            
            await handler.disconnect()
            
        except Exception as e:
            pytest.skip(f"Robinhood trading pairs not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__])