"""
Robinhood Crypto API connector.

This module provides the interface for interacting with Robinhood's
cryptocurrency trading API, including authentication, market data,
and order management.
"""

import asyncio
import logging
import base64
import hashlib
import hmac
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import nacl.signing
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from grodtd.storage.interfaces import MarketDataInterface, OHLCVBar
from grodtd.connectors.base import ExecutionHandler, Order, Position, AccountBalance, OrderSide, OrderType


@dataclass
class Order:
    """Represents a trading order."""
    id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: Optional[float] = None
    order_type: str = 'market'  # 'market', 'limit', 'stop_limit'
    status: str = 'pending'
    created_at: datetime = None
    filled_at: Optional[datetime] = None
    filled_quantity: float = 0.0
    average_fill_price: Optional[float] = None


@dataclass
class Quote:
    """Represents a market quote."""
    symbol: str
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    timestamp: datetime


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    quantity: float
    average_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float


class RobinhoodAuth:
    """Handles Robinhood API authentication with signature-based auth."""
    
    def __init__(self, api_key: str, private_key: str, public_key: str):
        self.api_key = api_key
        self.private_key = private_key
        self.public_key = public_key
        self.logger = logging.getLogger(__name__)
        
        # Convert base64 keys to nacl objects
        try:
            # The private key is 64 bytes (32-byte seed + 32-byte public key)
            # We need to extract just the first 32 bytes for the seed
            private_key_bytes = base64.b64decode(private_key)
            self._public_key_bytes = base64.b64decode(public_key)
            
            # Extract the first 32 bytes as the seed
            private_key_seed = private_key_bytes[:32]
            
            # Create signing key from the seed
            self._signing_key = nacl.signing.SigningKey(private_key_seed)
            self._verify_key = nacl.signing.VerifyKey(self._public_key_bytes)
        except Exception as e:
            self.logger.error(f"Failed to initialize signing keys: {e}")
            raise
    
    def generate_signature(self, path: str, method: str, body: str = "", timestamp: Optional[int] = None) -> str:
        """Generate signature for API request."""
        if timestamp is None:
            timestamp = int(time.time())
        
        # Create message to sign
        message = f"{self.api_key}{timestamp}{path}{method}{body}"
        
        # Sign the message
        signed = self._signing_key.sign(message.encode("utf-8"))
        
        # Return base64 encoded signature
        return base64.b64encode(signed.signature).decode("utf-8")
    
    def get_auth_headers(self, path: str, method: str, body: str = "") -> Dict[str, str]:
        """Get authentication headers for API request."""
        timestamp = int(time.time())
        signature = self.generate_signature(path, method, body, timestamp)
        
        return {
            "x-api-key": self.api_key,
            "x-timestamp": str(timestamp),
            "x-signature": signature,
            "Content-Type": "application/json; charset=utf-8"
        }
    
    def is_token_valid(self) -> bool:
        """Check if authentication is valid (always true for API key auth)."""
        return True
    


class RobinhoodLiveHandler(ExecutionHandler, MarketDataInterface):
    """Main connector for Robinhood Crypto API."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Robinhood live trading handler.
        
        Args:
            config: Configuration dictionary containing:
                - api_key: Robinhood API key
                - private_key: Robinhood private key
                - public_key: Robinhood public key
        """
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.private_key = config.get("private_key")
        self.public_key = config.get("public_key")
        
        if not all([self.api_key, self.private_key, self.public_key]):
            raise ValueError("Robinhood API key, private key, and public key are required")
        
        self.auth = RobinhoodAuth(self.api_key, self.private_key, self.public_key)
        self.base_url = "https://trading.robinhood.com"
        self.client: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(__name__)
        self._subscriptions: Dict[str, Callable] = {}
        self._rate_limit_delay = 0.5  # 500ms between requests
        self._last_request_time = 0.0
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self):
        """Initialize the HTTP client."""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
        )
        self.logger.info("Connected to Robinhood API")
    
    async def _rate_limit(self):
        """Implement rate limiting between requests."""
        import time
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._rate_limit_delay:
            sleep_time = self._rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.RequestError))
    )
    async def _make_request(self, method: str, endpoint: str, body: str = "", **kwargs) -> httpx.Response:
        """Make a rate-limited request with retry logic and proper authentication."""
        await self._rate_limit()
        
        if not self.client:
            raise RuntimeError("Connector not connected. Call connect() first.")
        
        try:
            # Get authentication headers
            auth_headers = self.auth.get_auth_headers(endpoint, method, body)
            
            # Merge with any additional headers
            headers = {**auth_headers, **kwargs.get('headers', {})}
            kwargs['headers'] = headers
            
            response = await self.client.request(method, endpoint, **kwargs)
            
            # Handle rate limiting
            if response.status_code == 429:
                self.logger.warning("Rate limited, backing off...")
                await asyncio.sleep(2)
                raise httpx.HTTPError("Rate limited")
            
            # Handle authentication errors
            if response.status_code == 401:
                self.logger.error("Authentication failed - check your API key and signature")
                raise httpx.HTTPError("Authentication failed")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            raise
    
    async def disconnect(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.logger.info("Disconnected from Robinhood API")
    
    async def get_trading_pairs(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Get trading pair information for given symbols."""
        try:
            # Build query parameters for multiple symbols
            params = {}
            for symbol in symbols:
                params["symbol"] = symbol  # Robinhood expects multiple symbol params
            
            # Build the full path with query parameters
            query_string = "&".join([f"symbol={symbol}" for symbol in symbols])
            endpoint = f"/api/v1/crypto/trading/trading_pairs/?{query_string}"
            
            response = await self._make_request(
                "GET", 
                endpoint
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                self.logger.error(f"Failed to get trading pairs: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting trading pairs: {e}")
            return []
    
    async def get_best_bid_ask(self, symbols: List[str]) -> List[Quote]:
        """Get current best bid/ask prices for symbols."""
        try:
            # Build the full path with query parameters
            query_string = "&".join([f"symbol={symbol}" for symbol in symbols])
            endpoint = f"/api/v1/crypto/marketdata/best_bid_ask/?{query_string}"
            
            response = await self._make_request(
                "GET",
                endpoint
            )
            
            if response.status_code == 200:
                data = response.json()
                quotes = []
                for quote_data in data.get("results", []):
                    quote = Quote(
                        symbol=quote_data.get("symbol", ""),
                        bid_price=float(quote_data.get("bid_price", 0)),
                        ask_price=float(quote_data.get("ask_price", 0)),
                        bid_size=float(quote_data.get("bid_size", 0)),
                        ask_size=float(quote_data.get("ask_size", 0)),
                        timestamp=datetime.now()  # Best bid/ask doesn't have timestamp
                    )
                    quotes.append(quote)
                return quotes
            else:
                self.logger.error(f"Failed to get best bid/ask: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting best bid/ask: {e}")
            return []
    
    async def get_estimated_price(self, symbol: str, side: str, quantity: str) -> List[Dict[str, Any]]:
        """Get estimated price for a symbol and quantity."""
        try:
            response = await self._make_request(
                "GET",
                "/marketdata/api/v1/estimated_price/",
                params={
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                self.logger.error(f"Failed to get estimated price: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting estimated price: {e}")
            return []
    
    async def place_order(self, order: Order) -> str:
        """Place a new order on Robinhood."""
        try:
            # Convert our Order to Robinhood format
            order_data = {
                "symbol": order.symbol,
                "side": order.side.value,
                "type": order.order_type.value,
                "quantity": str(order.quantity),
                "time_in_force": order.time_in_force
            }
            
            # Add optional fields
            if order.price:
                order_data["limit_price"] = str(order.price)
            if order.stop_price:
                order_data["stop_price"] = str(order.stop_price)
            if order.client_order_id:
                order_data["client_order_id"] = order.client_order_id
            
            # Convert to JSON string for signature
            body = json.dumps(order_data)
            
            response = await self._make_request(
                "POST",
                "/api/v1/crypto/trading/orders/",
                body=body
            )
            
            if response.status_code == 201:
                order_response = response.json()
                order_id = order_response.get("id")
                self.logger.info(f"Order placed successfully: {order_id}")
                return order_id
            else:
                error_msg = response.text
                self.logger.error(f"Failed to place order: {response.status_code} - {error_msg}")
                raise Exception(f"Order placement failed: {error_msg}")
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            raise
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get the status of an order."""
        # TODO: Implement actual API call
        self.logger.info(f"Getting status for order: {order_id}")
        return {"id": order_id, "status": "pending"}
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        # TODO: Implement actual API call
        self.logger.info(f"Canceling order: {order_id}")
        return True
    
    async def get_account_balance(self) -> Dict[str, float]:
        """Get account balance information."""
        # TODO: Implement actual API call
        self.logger.info("Getting account balance")
        return {"cash": 0.0, "buying_power": 0.0}
    
    async def get_positions(self) -> List[Position]:
        """Get current trading positions."""
        # TODO: Implement actual API call
        self.logger.info("Getting current positions")
        return []
    
    async def get_orders(self, status: Optional[str] = None) -> List[Order]:
        """Get orders, optionally filtered by status."""
        # TODO: Implement actual API call
        self.logger.info(f"Getting orders with status: {status}")
        return []
    
    # MarketDataInterface implementation
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime, 
        interval: str = "1m"
    ) -> List[OHLCVBar]:
        """Get historical OHLCV data for a symbol."""
        self.logger.info(f"Getting historical data for {symbol} from {start_date} to {end_date}")
        
        if not self.client:
            raise RuntimeError("Connector not connected. Call connect() first.")
        
        try:
            # For now, return empty list as Robinhood's new API doesn't have historical data endpoint
            # In a real implementation, you'd need to use a different data source for historical data
            self.logger.warning("Historical data not available in Robinhood Crypto API")
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting historical data: {e}")
            return []
    
    async def get_real_time_data(self, symbol: str) -> OHLCVBar:
        """Get current real-time OHLCV data for a symbol."""
        self.logger.info(f"Getting real-time data for {symbol}")
        
        if not self.client:
            raise RuntimeError("Connector not connected. Call connect() first.")
        
        try:
            # Get current best bid/ask
            quotes = await self.get_best_bid_ask([symbol])
            if not quotes:
                raise RuntimeError(f"No quote data available for {symbol}")
            
            quote = quotes[0]
            current_price = (quote.bid_price + quote.ask_price) / 2
            
            # Create OHLCV bar with current price
            return OHLCVBar(
                timestamp=datetime.now(),
                open=current_price,
                high=current_price,
                low=current_price,
                close=current_price,
                volume=0.0  # Real-time volume not available from quotes
            )
            
        except Exception as e:
            self.logger.error(f"Error getting real-time data: {e}")
            # Return a placeholder bar on error
            return OHLCVBar(
                timestamp=datetime.now(),
                open=0.0,
                high=0.0,
                low=0.0,
                close=0.0,
                volume=0.0
            )
    
    async def subscribe_to_updates(self, symbol: str, callback: Callable) -> None:
        """Subscribe to real-time data updates."""
        self.logger.info(f"Subscribing to updates for {symbol}")
        self._subscriptions[symbol] = callback
        
        # TODO: Implement WebSocket subscription to Robinhood
        # For now, just store the callback
    
    # Implementation of ExecutionHandler abstract methods
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        try:
            response = await self._make_request(
                "DELETE",
                f"/api/v1/crypto/trading/orders/{order_id}"
            )
            
            if response.status_code == 200:
                self.logger.info(f"Order {order_id} cancelled successfully")
                return True
            else:
                self.logger.error(f"Failed to cancel order {order_id}: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position information for a symbol."""
        try:
            response = await self._make_request(
                "GET",
                f"/api/v1/crypto/trading/holdings/?asset_code={symbol}"
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    holding = data["results"][0]
                    return Position(
                        symbol=holding.get("asset_code", ""),
                        quantity=float(holding.get("quantity", 0)),
                        market_value=float(holding.get("market_value", 0)),
                        unrealized_pnl=float(holding.get("unrealized_pnl", 0)),
                        realized_pnl=float(holding.get("realized_pnl", 0)),
                        average_cost=float(holding.get("average_cost", 0)),
                        current_price=float(holding.get("current_price", 0))
                    )
            return None
                
        except Exception as e:
            self.logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    async def get_all_positions(self) -> List[Position]:
        """Get all current positions."""
        try:
            response = await self._make_request(
                "GET",
                "/api/v1/crypto/trading/holdings/"
            )
            
            if response.status_code == 200:
                data = response.json()
                positions = []
                
                for holding in data.get("results", []):
                    position = Position(
                        symbol=holding.get("asset_code", ""),
                        quantity=float(holding.get("quantity", 0)),
                        market_value=float(holding.get("market_value", 0)),
                        unrealized_pnl=float(holding.get("unrealized_pnl", 0)),
                        realized_pnl=float(holding.get("realized_pnl", 0)),
                        average_cost=float(holding.get("average_cost", 0)),
                        current_price=float(holding.get("current_price", 0))
                    )
                    positions.append(position)
                
                return positions
            else:
                self.logger.error(f"Failed to get positions: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_account_balance(self) -> AccountBalance:
        """Get account balance information."""
        try:
            response = await self._make_request(
                "GET",
                "/api/v1/crypto/trading/accounts/"
            )
            
            if response.status_code == 200:
                data = response.json()
                return AccountBalance(
                    buying_power=float(data.get("buying_power", 0)),
                    cash=float(data.get("buying_power", 0)),  # Robinhood doesn't separate cash
                    portfolio_value=float(data.get("buying_power", 0)),  # Simplified
                    currency=data.get("buying_power_currency", "USD")
                )
            else:
                self.logger.error(f"Failed to get account balance: {response.status_code}")
                return AccountBalance(0, 0, 0)
                
        except Exception as e:
            self.logger.error(f"Error getting account balance: {e}")
            return AccountBalance(0, 0, 0)
    
    async def get_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of orders, optionally filtered by status."""
        try:
            params = {}
            if status:
                params["state"] = status
            
            response = await self._make_request(
                "GET",
                "/api/v1/crypto/trading/orders/",
                params=params
            )
            
            if response.status_code == 200:
                return response.json().get("results", [])
            else:
                self.logger.error(f"Failed to get orders: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting orders: {e}")
            return []


# Factory function for creating connector instances
def create_robinhood_handler(config: Dict[str, Any]) -> RobinhoodLiveHandler:
    """Create a new Robinhood live trading handler instance."""
    return RobinhoodLiveHandler(config)
