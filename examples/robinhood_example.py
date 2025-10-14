"""
Example script showing how to use the Robinhood connector.

This script demonstrates how to:
1. Authenticate with Robinhood API
2. Fetch historical data
3. Get real-time quotes
4. Use the data loader

Note: You need valid Robinhood credentials to run this script.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from grodtd.connectors.robinhood import create_robinhood_connector
from grodtd.storage.data_loader import create_data_loader
from grodtd.config.robinhood_config import create_connector_from_config


async def main():
    """Main example function."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Method 1: Use configuration file (recommended)
        logger.info("Creating Robinhood connector from config...")
        try:
            connector = create_connector_from_config()
            logger.info("✅ Loaded configuration from configs/robinhood.yaml")
        except FileNotFoundError:
            logger.warning("⚠️  Config file not found, using direct API key...")
            
            # Method 2: Direct API key (for testing)
            api_key = "your_api_key_here"  # Replace with your actual API key
            api_secret = None
            connector = create_robinhood_connector(api_key, api_secret)
        
        # Connect to API
        logger.info("Connecting to Robinhood API...")
        async with connector:
            # Test getting historical data
            logger.info("Fetching historical data for BTC...")
            start_date = datetime.now() - timedelta(days=7)
            end_date = datetime.now()
            
            bars = await connector.get_historical_data("BTC", start_date, end_date, "1h")
            logger.info(f"Retrieved {len(bars)} bars for BTC")
            
            if bars:
                latest_bar = bars[-1]
                logger.info(f"Latest BTC price: ${latest_bar.close:.2f}")
            
            # Test getting real-time data
            logger.info("Getting real-time BTC quote...")
            real_time_bar = await connector.get_real_time_data("BTC")
            logger.info(f"Current BTC price: ${real_time_bar.close:.2f}")
            
            # Test using data loader
            logger.info("Testing data loader...")
            data_loader = create_data_loader(Path("data"))
            
            # Load historical data using the connector
            df = await data_loader.load_historical_data(
                "BTC",
                start_date,
                end_date,
                "1h",
                connector
            )
            
            logger.info(f"Data loader returned {len(df)} rows")
            if not df.empty:
                logger.info(f"Data columns: {list(df.columns)}")
                logger.info(f"Date range: {df.index.min()} to {df.index.max()}")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Make sure you have valid Robinhood credentials and internet connection")


if __name__ == "__main__":
    print("Robinhood API Example")
    print("=" * 50)
    print("This example shows how to use the Robinhood connector.")
    print()
    print("🔑 To set up your API keys, choose one of these methods:")
    print()
    print("Method 1 (Recommended): Edit configs/robinhood.yaml")
    print("  - Replace 'your_private_key_here' with your actual private key")
    print("  - Your API key and public key are already set")
    print("  - Get your keys from: Robinhood App > Settings > API Trading")
    print()
    print("Method 2: Set environment variables")
    print("  - export ROBINHOOD_API_KEY='rh-api-82a3d6b0-55bb-451d-acd0-659df6d26083'")
    print("  - export ROBINHOOD_PRIVATE_KEY='your_private_key_here'")
    print("  - export ROBINHOOD_PUBLIC_KEY='RPAzXu0YTchPtLJc6QrOIiCCDnqx/XJk75lSJcKUpqo='")
    print()
    print("Method 3: Edit this script directly")
    print("  - Replace the keys in the code below")
    print("=" * 50)
    
    # Run the example
    asyncio.run(main())
