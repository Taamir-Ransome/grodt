"""
Execution handler factory.

This module provides a factory for creating execution handlers based on configuration.
It allows easy switching between different brokers (Alpaca paper vs Robinhood live)
via configuration settings.
"""

import logging
from typing import Dict, Any, Type
from pathlib import Path
import yaml

from grodtd.connectors.base import ExecutionHandler
from grodtd.connectors.alpaca import AlpacaPaperHandler
from grodtd.connectors.robinhood import RobinhoodLiveHandler


class ExecutionHandlerFactory:
    """Factory for creating execution handlers."""
    
    _handlers: Dict[str, Type[ExecutionHandler]] = {
        "alpaca_paper": AlpacaPaperHandler,
        "robinhood_live": RobinhoodLiveHandler,
    }
    
    @classmethod
    def create_handler(cls, handler_type: str, config: Dict[str, Any]) -> ExecutionHandler:
        """
        Create an execution handler instance.
        
        Args:
            handler_type: Type of handler to create (e.g., 'alpaca_paper', 'robinhood_live')
            config: Configuration dictionary for the handler
            
        Returns:
            ExecutionHandler instance
            
        Raises:
            ValueError: If handler_type is not supported
        """
        if handler_type not in cls._handlers:
            available = ", ".join(cls._handlers.keys())
            raise ValueError(f"Unknown handler type: {handler_type}. Available: {available}")
        
        handler_class = cls._handlers[handler_type]
        return handler_class(config)
    
    @classmethod
    def get_available_handlers(cls) -> list[str]:
        """Get list of available handler types."""
        return list(cls._handlers.keys())
    
    @classmethod
    def register_handler(cls, name: str, handler_class: Type[ExecutionHandler]) -> None:
        """
        Register a new handler type.
        
        Args:
            name: Name of the handler type
            handler_class: Handler class that inherits from ExecutionHandler
        """
        cls._handlers[name] = handler_class


def load_execution_handler(config_path: str = "configs/settings.yaml") -> ExecutionHandler:
    """
    Load execution handler from configuration file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        ExecutionHandler instance
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If handler type is not supported
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        settings = yaml.safe_load(f)
    
    # Get handler type from settings
    handler_type = settings.get("execution", {}).get("handler")
    if not handler_type:
        raise ValueError("No execution handler specified in configuration")
    
    # Load handler-specific configuration
    handler_config = _load_handler_config(handler_type)
    
    # Create and return handler
    return ExecutionHandlerFactory.create_handler(handler_type, handler_config)


def _load_handler_config(handler_type: str) -> Dict[str, Any]:
    """
    Load configuration for a specific handler type.
    
    Args:
        handler_type: Type of handler to load config for
        
    Returns:
        Configuration dictionary for the handler
    """
    if handler_type == "alpaca_paper":
        # Load Alpaca configuration
        from grodtd.config.alpaca_config import load_alpaca_config
        return load_alpaca_config()
    
    elif handler_type == "robinhood_live":
        # Load Robinhood configuration
        from grodtd.config.robinhood_config import load_robinhood_config
        return load_robinhood_config()
    
    else:
        raise ValueError(f"Unknown handler type: {handler_type}")


# Convenience function for easy access
def get_execution_handler() -> ExecutionHandler:
    """
    Get the configured execution handler.
    
    This is a convenience function that loads the handler from the default
    configuration file.
    
    Returns:
        ExecutionHandler instance
    """
    return load_execution_handler()
