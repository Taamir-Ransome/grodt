"""
Alpaca API configuration loader.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv


class AlpacaConfig(BaseModel):
    """Alpaca API configuration."""
    api_key: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"
    rate_limit_delay_ms: int = 500
    max_retries: int = 3


def load_alpaca_config(config_path: Optional[Path] = None) -> AlpacaConfig:
    """Load Alpaca configuration from .env file or environment variables."""
    
    # Load .env file if it exists
    load_dotenv()
    
    # Try environment variables first (most secure)
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    
    if api_key and secret_key:
        return AlpacaConfig(
            api_key=api_key,
            secret_key=secret_key,
            base_url=base_url,
            rate_limit_delay_ms=int(os.getenv("ALPACA_RATE_LIMIT_MS", "500")),
            max_retries=int(os.getenv("ALPACA_MAX_RETRIES", "3"))
        )
    
    # Fall back to config file
    if config_path is None:
        config_path = Path("configs/alpaca.yaml")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    return AlpacaConfig(
        api_key=config_data["api"]["key"],
        secret_key=config_data["api"]["secret_key"],
        base_url=config_data["api"].get("base_url", "https://paper-api.alpaca.markets"),
        rate_limit_delay_ms=config_data.get("rate_limit", {}).get("delay_ms", 500),
        max_retries=config_data.get("rate_limit", {}).get("max_retries", 3)
    )
