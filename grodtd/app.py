"""
Main application entry point for GRODT daemon.
"""

import asyncio
import logging
from pathlib import Path

import structlog
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    env: str = "dev"
    log_level: str = "INFO"
    database_url: str = "sqlite:///data/grodt.db"
    
    model_config = ConfigDict(env_file=".env")


async def main():
    """Main application entry point."""
    settings = Settings()

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()
    logger.info("Starting GRODT daemon", env=settings.env)

    # TODO: Initialize components
    # - Database connection
    # - Robinhood connector
    # - Strategy engine
    # - Risk manager
    # - Execution engine

    logger.info("GRODT daemon started successfully")


if __name__ == "__main__":
    asyncio.run(main())
