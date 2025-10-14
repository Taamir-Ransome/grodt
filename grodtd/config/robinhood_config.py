"""
Robinhood API configuration loader.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv


class RobinhoodConfig(BaseModel):
    """Robinhood API configuration."""
    api_key: str
    private_key: str
    public_key: str
    base_url: str = "https://trading.robinhood.com"
    rate_limit_delay_ms: int = 500
    max_retries: int = 3
    default_interval: str = "1m"
    max_bars_per_request: int = 1000


def load_robinhood_config(config_path: Optional[Path] = None) -> RobinhoodConfig:
    """Load Robinhood configuration from .env file or environment variables."""
    
    # Load .env file if it exists
    load_dotenv()
    
    # Try environment variables first (most secure)
    api_key = os.getenv("ROBINHOOD_API_KEY")
    private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")
    public_key = os.getenv("ROBINHOOD_PUBLIC_KEY")
    
    if api_key and private_key and public_key:
        return RobinhoodConfig(
            api_key=api_key,
            private_key=private_key,
            public_key=public_key,
            base_url=os.getenv("ROBINHOOD_BASE_URL", "https://trading.robinhood.com"),
            rate_limit_delay_ms=int(os.getenv("ROBINHOOD_RATE_LIMIT_MS", "500")),
            max_retries=int(os.getenv("ROBINHOOD_MAX_RETRIES", "3")),
            default_interval=os.getenv("ROBINHOOD_DEFAULT_INTERVAL", "1m"),
            max_bars_per_request=int(os.getenv("ROBINHOOD_MAX_BARS", "1000"))
        )
    
    # Fall back to config file
    if config_path is None:
        config_path = Path("configs/robinhood.yaml")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    return RobinhoodConfig(
        api_key=config_data["api"]["key"],
        private_key=config_data["api"]["private_key"],
        public_key=config_data["api"]["public_key"],
        base_url=config_data["api"].get("base_url", "https://trading.robinhood.com"),
        rate_limit_delay_ms=config_data.get("rate_limit", {}).get("delay_ms", 500),
        max_retries=config_data.get("rate_limit", {}).get("max_retries", 3),
        default_interval=config_data.get("data", {}).get("default_interval", "1m"),
        max_bars_per_request=config_data.get("data", {}).get("max_bars_per_request", 1000)
    )


def create_connector_from_config(config_path: Optional[Path] = None):
    """Create a Robinhood connector using configuration."""
    from grodtd.connectors.robinhood import create_robinhood_connector
    
    config = load_robinhood_config(config_path)
    return create_robinhood_connector(config.api_key, config.private_key, config.public_key)
