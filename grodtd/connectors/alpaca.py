"""
Alpaca paper trading execution handler.

This module implements the ExecutionHandler interface for Alpaca's paper trading API,
allowing for risk-free testing and development.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from grodtd.connectors.base import (
    ExecutionHandler, Order, Position, AccountBalance, 
    OrderSide, OrderType
)


class AlpacaPaperHandler(ExecutionHandler):
    """
    Alpaca paper trading execution handler.
    
    Provides paper trading functionality using Alpaca's paper trading API.
    Perfect for testing strategies without real money.
    """
    
    def __init__(self, config):
        """
        Initialize Alpaca paper trading handler.
        
        Args:
            config: AlpacaConfig object or dictionary containing:
                - api_key: Alpaca API key
                - secret_key: Alpaca secret key
                - base_url: Alpaca API base URL (default: paper trading)
        """
        # Handle both Pydantic model and dict
        if hasattr(config, 'api_key'):
            # Pydantic model
            self.api_key = config.api_key
            self.secret_key = config.secret_key
            self.base_url = config.base_url
        else:
            # Dictionary
            self.api_key = config.get("api_key")
            self.secret_key = config.get("secret_key")
            self.base_url = config.get("base_url", "https://paper-api.alpaca.markets")
        
        # Initialize base class with empty dict since we handle config ourselves
        super().__init__({})
        self.client: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(__name__)
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API key and secret key are required")
    
    async def connect(self) -> bool:
        """Establish connection to Alpaca paper trading API."""
        try:
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "APCA-API-KEY-ID": self.api_key,
                    "APCA-API-SECRET-KEY": self.secret_key,
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            
            # Test connection by getting account info
            response = await self.client.get("/v2/account")
            if response.status_code == 200:
                self.logger.info("Successfully connected to Alpaca paper trading API")
                return True
            else:
                self.logger.error(f"Failed to connect to Alpaca: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to Alpaca: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close connection to Alpaca API."""
        if self.client:
            await self.client.aclose()
            self.logger.info("Disconnected from Alpaca API")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.RequestError))
    )
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Make a request to Alpaca API with retry logic."""
        if not self.client:
            raise RuntimeError("Not connected to Alpaca API")
        
        try:
            response = await self.client.request(method, endpoint, **kwargs)
            
            if response.status_code == 429:  # Rate limited
                self.logger.warning("Rate limited, backing off...")
                await asyncio.sleep(2)
                raise httpx.HTTPError("Rate limited")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            raise
    
    async def place_order(self, order: Order) -> str:
        """Place a new order on Alpaca paper trading."""
        try:
            # Convert our Order to Alpaca format
            alpaca_order = {
                "symbol": order.symbol,
                "qty": str(order.quantity),
                "side": order.side.value,
                "type": order.order_type.value,
                "time_in_force": order.time_in_force
            }
            
            # Add optional fields
            if order.price:
                alpaca_order["limit_price"] = str(order.price)
            if order.stop_price:
                alpaca_order["stop_price"] = str(order.stop_price)
            if order.client_order_id:
                alpaca_order["client_order_id"] = order.client_order_id
            
            response = await self._make_request(
                "POST",
                "/v2/orders",
                json=alpaca_order
            )
            
            if response.status_code in [200, 201]:
                order_data = response.json()
                order_id = order_data.get("id")
                self.logger.info(f"Order placed successfully: {order_id}")
                return order_id
            else:
                error_msg = response.text
                self.logger.error(f"Failed to place order: {response.status_code} - {error_msg}")
                raise Exception(f"Order placement failed: {error_msg}")
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        try:
            response = await self._make_request(
                "DELETE",
                f"/v2/orders/{order_id}"
            )
            
            if response.status_code == 204:
                self.logger.info(f"Order {order_id} cancelled successfully")
                return True
            else:
                self.logger.error(f"Failed to cancel order {order_id}: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get the status of an order."""
        try:
            response = await self._make_request(
                "GET",
                f"/v2/orders/{order_id}"
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Failed to get order status: {response.status_code}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting order status: {e}")
            return {}
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position information for a symbol."""
        try:
            response = await self._make_request(
                "GET",
                f"/v2/positions/{symbol}"
            )
            
            if response.status_code == 200:
                data = response.json()
                return Position(
                    symbol=data.get("symbol", ""),
                    quantity=float(data.get("qty", 0)),
                    market_value=float(data.get("market_value", 0)),
                    unrealized_pnl=float(data.get("unrealized_pl", 0)),
                    realized_pnl=float(data.get("realized_pl", 0)),
                    average_cost=float(data.get("avg_entry_price", 0)),
                    current_price=float(data.get("current_price", 0))
                )
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    async def get_all_positions(self) -> List[Position]:
        """Get all current positions."""
        try:
            response = await self._make_request(
                "GET",
                "/v2/positions"
            )
            
            if response.status_code == 200:
                positions_data = response.json()
                positions = []
                
                for data in positions_data:
                    position = Position(
                        symbol=data.get("symbol", ""),
                        quantity=float(data.get("qty", 0)),
                        market_value=float(data.get("market_value", 0)),
                        unrealized_pnl=float(data.get("unrealized_pl", 0)),
                        realized_pnl=float(data.get("realized_pl", 0)),
                        average_cost=float(data.get("avg_entry_price", 0)),
                        current_price=float(data.get("current_price", 0))
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
                "/v2/account"
            )
            
            if response.status_code == 200:
                data = response.json()
                return AccountBalance(
                    buying_power=float(data.get("buying_power", 0)),
                    cash=float(data.get("cash", 0)),
                    portfolio_value=float(data.get("portfolio_value", 0)),
                    currency=data.get("currency", "USD")
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
                params["status"] = status
            
            response = await self._make_request(
                "GET",
                "/v2/orders",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Failed to get orders: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting orders: {e}")
            return []
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current quote for a symbol."""
        try:
            response = await self._make_request(
                "GET",
                f"/v2/stocks/{symbol}/quotes/latest"
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting quote for {symbol}: {e}")
            return None
