#!/usr/bin/env python3
"""
Test script to verify Robinhood API connection.
"""

import asyncio
import logging
from datetime import datetime

from grodtd.config.robinhood_config import create_connector_from_config


async def test_robinhood_connection():
    """Test the Robinhood API connection."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🔑 Loading Robinhood configuration...")
        connector = create_connector_from_config()
        logger.info("✅ Configuration loaded successfully")
        
        logger.info("🔌 Connecting to Robinhood API...")
        async with connector:
            logger.info("✅ Connected to Robinhood API")
            
            # Test 1: Get trading pairs
            logger.info("📊 Testing trading pairs endpoint...")
            trading_pairs = await connector.get_trading_pairs(["BTC-USD"])
            logger.info(f"✅ Found {len(trading_pairs)} trading pairs")
            
            if trading_pairs:
                pair = trading_pairs[0]
                logger.info(f"   Example pair: {pair.get('symbol', 'N/A')}")
            
            # Test 2: Get best bid/ask
            logger.info("💰 Testing best bid/ask endpoint...")
            quotes = await connector.get_best_bid_ask(["BTC-USD"])
            logger.info(f"✅ Retrieved {len(quotes)} quotes")
            
            if quotes:
                quote = quotes[0]
                logger.info(f"   BTC-USD: Bid=${quote.bid_price:.2f}, Ask=${quote.ask_price:.2f}")
            
            # Test 3: Get estimated price
            logger.info("📈 Testing estimated price endpoint...")
            prices = await connector.get_estimated_price("BTC-USD", "ask", "0.1")
            logger.info(f"✅ Retrieved {len(prices)} price estimates")
            
            if prices:
                price = prices[0]
                logger.info(f"   Estimated price for 0.1 BTC: ${price.get('estimated_price', 'N/A')}")
            
            logger.info("🎉 All tests passed! Robinhood API is working correctly.")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        logger.error("Make sure your API keys are correct and you have internet connection")


if __name__ == "__main__":
    print("Robinhood API Connection Test")
    print("=" * 50)
    print("Testing your Robinhood API integration...")
    print("=" * 50)
    
    asyncio.run(test_robinhood_connection())
