"""
Main application entry point.

This module demonstrates how to use the new execution handler system
to switch between different brokers via configuration.
"""

import asyncio
import logging
from typing import Optional

from grodtd.connectors.factory import get_execution_handler
from grodtd.connectors.base import Order, OrderSide, OrderType


class TradingApp:
    """Main trading application."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.execution_handler: Optional[ExecutionHandler] = None
    
    async def initialize(self):
        """Initialize the trading application."""
        try:
            # Load execution handler from configuration
            self.logger.info("Loading execution handler from configuration...")
            self.execution_handler = get_execution_handler()
            
            # Connect to the broker
            self.logger.info("Connecting to broker...")
            await self.execution_handler.connect()
            
            self.logger.info("Trading application initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading application: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the trading application."""
        if self.execution_handler:
            await self.execution_handler.disconnect()
            self.logger.info("Trading application shutdown complete")
    
    async def get_account_info(self):
        """Get account information."""
        if not self.execution_handler:
            self.logger.error("Execution handler not initialized")
            return
        
        try:
            # Get account balance
            balance = await self.execution_handler.get_account_balance()
            self.logger.info(f"Account Balance: ${balance.buying_power:.2f} {balance.currency}")
            
            # Get all positions
            positions = await self.execution_handler.get_all_positions()
            self.logger.info(f"Found {len(positions)} positions")
            
            for position in positions:
                self.logger.info(f"Position: {position.symbol} - {position.quantity} @ ${position.current_price:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
    
    async def place_test_order(self, symbol: str = "BTC-USD"):
        """Place a test order (paper trading only)."""
        if not self.execution_handler:
            self.logger.error("Execution handler not initialized")
            return
        
        try:
            # Create a small test order
            order = Order(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=0.001,  # Very small amount for testing
                order_type=OrderType.MARKET
            )
            
            self.logger.info(f"Placing test order: {order.symbol} {order.side.value} {order.quantity}")
            order_id = await self.execution_handler.place_order(order)
            self.logger.info(f"Order placed successfully: {order_id}")
            
            # Get order status
            status = await self.execution_handler.get_order_status(order_id)
            self.logger.info(f"Order status: {status}")
            
        except Exception as e:
            self.logger.error(f"Error placing test order: {e}")
    
    async def run(self):
        """Run the trading application."""
        # Initialize
        if not await self.initialize():
            return
        
        try:
            # Get account information
            await self.get_account_info()
            
            # Place a test order (only in paper trading mode)
            handler_type = self.execution_handler.__class__.__name__
            if "Paper" in handler_type:
                await self.place_test_order()
            else:
                self.logger.warning("Live trading mode - skipping test order")
            
        finally:
            # Always shutdown
            await self.shutdown()


async def main():
    """Main entry point."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and run the trading app
    app = TradingApp()
    await app.run()


if __name__ == "__main__":
    print("Trading Application")
    print("=" * 50)
    print("This app demonstrates the new execution handler system.")
    print("Check configs/settings.yaml to switch between brokers.")
    print("=" * 50)
    
    asyncio.run(main())