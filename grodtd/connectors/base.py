"""
Abstract base class for execution handlers.

This module defines the ExecutionHandler abstract base class that all
broker-specific implementations must inherit from. This allows for easy
switching between different brokers (e.g., Alpaca paper trading vs Robinhood live)
via configuration.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class Order:
    """Represents a trading order."""
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "gtc"  # Good Till Cancelled
    client_order_id: Optional[str] = None


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    quantity: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    average_cost: float
    current_price: float


@dataclass
class AccountBalance:
    """Represents account balance information."""
    buying_power: float
    cash: float
    portfolio_value: float
    currency: str = "USD"


class ExecutionHandler(ABC):
    """
    Abstract base class for execution handlers.
    
    All broker-specific implementations must inherit from this class
    and implement all abstract methods.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the execution handler.
        
        Args:
            config: Configuration dictionary containing broker-specific settings
        """
        self.config = config
        self.logger = None  # Will be set by subclasses
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the broker.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the broker."""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> str:
        """
        Place a new order.
        
        Args:
            order: Order object containing order details
            
        Returns:
            str: Order ID if successful
            
        Raises:
            Exception: If order placement fails
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: ID of the order to cancel
            
        Returns:
            bool: True if cancellation successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get the status of an order.
        
        Args:
            order_id: ID of the order to check
            
        Returns:
            Dict containing order status information
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position information for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'BTC-USD')
            
        Returns:
            Position object if position exists, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_all_positions(self) -> List[Position]:
        """
        Get all current positions.
        
        Returns:
            List of Position objects
        """
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> AccountBalance:
        """
        Get account balance information.
        
        Returns:
            AccountBalance object
        """
        pass
    
    @abstractmethod
    async def get_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of orders, optionally filtered by status.
        
        Args:
            status: Optional status filter (e.g., 'open', 'filled', 'cancelled')
            
        Returns:
            List of order dictionaries
        """
        pass
    
    # Market data methods (optional for execution handlers)
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Quote dictionary or None if not available
        """
        return None
    
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime, 
        interval: str = "1m"
    ) -> List[Dict[str, Any]]:
        """
        Get historical data for a symbol.
        
        Args:
            symbol: Trading symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Data interval (e.g., '1m', '1h', '1d')
            
        Returns:
            List of historical data points
        """
        return []
    
    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
