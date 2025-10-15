# Development Standards

## Overview

This document establishes comprehensive development standards for the GRODT trading system to ensure consistent, maintainable, and high-quality code across all components.

## Table of Contents

1. [General Principles](#general-principles)
2. [Code Style & Formatting](#code-style--formatting)
3. [Python Standards](#python-standards)
4. [Testing Standards](#testing-standards)
5. [Documentation Standards](#documentation-standards)
6. [Configuration Management](#configuration-management)
7. [Docker & Infrastructure](#docker--infrastructure)
8. [Security Standards](#security-standards)
9. [Performance Standards](#performance-standards)
10. [Version Control (Git)](#version-control-git)
11. [Review Process](#review-process)

## General Principles

### Code Quality Philosophy
- **Readability First**: Code should be self-documenting and easy to understand
- **Test-Driven Development**: Write tests before or alongside implementation
- **Fail Fast**: Implement proper error handling and validation
- **Single Responsibility**: Each function/class should have one clear purpose
- **DRY Principle**: Don't Repeat Yourself - extract common functionality

### Project & Dependencies
- **Package Management**: Use `uv` for all package and virtual environment management
- **Configuration**: Never hardcode parameters; all settings (risk, strategy, API keys) must be in `.yaml` configuration and `.env` files
- **External Services**: Abstract all external services using handler classes for brokers, data sources, etc.

### Project Structure
```
grodt/
├── grodtd/                 # Main application code
│   ├── __init__.py
│   ├── app.py             # Application entry point
│   ├── web_app.py         # Web interface
│   ├── monitoring/         # Monitoring and metrics
│   ├── execution/         # Trading execution
│   ├── storage/           # Data storage
│   └── ...
├── grodtbt/               # Backtesting framework
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── docker/               # Docker configurations
├── docs/                 # Documentation
└── configs/              # Configuration files
```

## Code Style & Formatting

### Python Code Style
- **Formatter**: Use `black` with line length 88 characters - ALL code must be auto-formatted
- **Import Sorting**: Use `isort` with black profile
- **Linting**: Use `ruff` for fast linting - ALL code must be linted
- **Type Hints**: MANDATORY for all function signatures and variable declarations
- **Naming Conventions**: Strictly follow PEP 8 (snake_case for functions, PascalCase for classes)
- **File Size**: Soft rule to keep files focused and modular, aiming for under 500 lines
- **Documentation**: Write clear docstrings for every public function, class, and module

### Configuration Files
```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py312']

[tool.isort]
profile = "black"
multi_line_output = 3

[tool.ruff]
target-version = "py312"
line-length = 88
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501", "B008", "C901"]
```

### Naming Conventions
- **Variables/Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private Methods**: `_leading_underscore`
- **Files/Modules**: `snake_case.py`

## Python Standards

### Type Hints
```python
from typing import Dict, List, Optional, Union
from pathlib import Path

def process_trades(
    trades: List[Dict[str, Union[str, float]]],
    output_path: Optional[Path] = None
) -> Dict[str, float]:
    """Process trading data with type safety."""
    pass
```

### Error Handling
```python
import structlog
from typing import Optional, Dict, Any

logger = structlog.get_logger(__name__)

def safe_operation(data: Dict[str, Any]) -> Optional[float]:
    """Perform operation with proper error handling."""
    try:
        result = complex_calculation(data)
        logger.info("Operation completed successfully", 
                   operation="safe_operation", 
                   result=result)
        return result
    except ValueError as e:
        logger.error("Invalid data provided", 
                    operation="safe_operation", 
                    error=str(e), 
                    data=data)
        return None
    except Exception as e:
        logger.error("Unexpected error in safe_operation", 
                    operation="safe_operation", 
                    error=str(e), 
                    data=data)
        raise
```

### Structured Logging with structlog
```python
import structlog
from typing import Dict, Any

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
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Usage in trading operations
def execute_trade(symbol: str, quantity: int, side: str) -> Dict[str, Any]:
    """Execute a trade with structured logging."""
    logger = structlog.get_logger("trading")
    
    logger.info("Trade execution started",
               symbol=symbol,
               quantity=quantity,
               side=side)
    
    try:
        # Execute trade logic
        result = process_trade(symbol, quantity, side)
        
        logger.info("Trade executed successfully",
                   symbol=symbol,
                   quantity=quantity,
                   side=side,
                   trade_id=result.get('id'),
                   price=result.get('price'))
        
        return result
        
    except Exception as e:
        logger.error("Trade execution failed",
                    symbol=symbol,
                    quantity=quantity,
                    side=side,
                    error=str(e))
        raise
```

### Async/Await Patterns
```python
import asyncio
from typing import AsyncGenerator

async def fetch_market_data(symbol: str) -> AsyncGenerator[Dict, None]:
    """Async generator for streaming market data."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/api/market/{symbol}") as response:
            async for line in response.content:
                yield parse_market_data(line)
```

### Class Design
```python
from abc import ABC, abstractmethod
from typing import Protocol
import structlog

class TradingStrategy(ABC):
    """Abstract base class for trading strategies."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = structlog.get_logger(self.__class__.__name__)
    
    @abstractmethod
    def generate_signals(self, market_data: Dict) -> List[Signal]:
        """Generate trading signals from market data."""
        pass
    
    def validate_config(self) -> bool:
        """Validate strategy configuration."""
        required_fields = ['symbol', 'timeframe', 'risk_level']
        return all(field in self.config for field in required_fields)
```

### Architecture & Design Principles
- **External Service Abstraction**: Abstract all external services using handler classes for brokers, data sources, etc.
- **Structured Logging**: Use structlog for structured JSON logging to make post-trade analysis easy
- **Single Responsibility**: Follow the Single Responsibility Principle - each class and function does one thing well

## Testing Standards

### Test Structure
```python
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

class TestTradingStrategy:
    """Test suite for trading strategy implementation."""
    
    @pytest.fixture
    def sample_market_data(self) -> Dict[str, Any]:
        """Provide sample market data for testing."""
        return {
            'symbol': 'AAPL',
            'price': 150.0,
            'volume': 1000,
            'timestamp': '2024-01-01T10:00:00Z'
        }
    
    def test_signal_generation_with_valid_data(self, sample_market_data):
        """Test signal generation with valid market data."""
        # Given
        strategy = TradingStrategy({'symbol': 'AAPL'})
        
        # When
        signals = strategy.generate_signals(sample_market_data)
        
        # Then
        assert len(signals) > 0
        assert all(isinstance(signal, Signal) for signal in signals)
    
    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async operations."""
        # Given
        async def async_function():
            return "result"
        
        # When
        result = await async_function()
        
        # Then
        assert result == "result"
```

### Test Categories
- **Unit Tests**: Test individual functions/classes in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete user workflows
- **Performance Tests**: Test system performance under load

### Test Coverage Requirements
- **Minimum Coverage**: 85% for new code (targeting >85% code coverage)
- **Critical Paths**: 95% coverage for trading logic
- **Monitoring**: 90% coverage for metrics collection
- **TDD Practice**: Practice Test-Driven Development (TDD) for critical features
- **External APIs**: Mock all external API calls in unit tests; use integration tests for live connections

## Documentation Standards

### Docstring Format
```python
def calculate_sharpe_ratio(
    returns: List[float], 
    risk_free_rate: float = 0.02
) -> float:
    """
    Calculate Sharpe ratio for a series of returns.
    
    Args:
        returns: List of periodic returns
        risk_free_rate: Risk-free rate (default: 2%)
    
    Returns:
        Sharpe ratio as a float
        
    Raises:
        ValueError: If returns list is empty or contains invalid values
        
    Example:
        >>> returns = [0.01, 0.02, -0.01, 0.03]
        >>> sharpe = calculate_sharpe_ratio(returns)
        >>> print(f"Sharpe ratio: {sharpe:.2f}")
    """
    if not returns:
        raise ValueError("Returns list cannot be empty")
    
    # Implementation here
    pass
```

### API Documentation
```python
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class TradeRequest(BaseModel):
    """Request model for trade execution."""
    
    symbol: str = Field(..., description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Number of shares")
    side: str = Field(..., regex="^(buy|sell)$", description="Trade side")
    order_type: str = Field(default="market", description="Order type")
    
    class Config:
        schema_extra = {
            "example": {
                "symbol": "AAPL",
                "quantity": 100,
                "side": "buy",
                "order_type": "market"
            }
        }
```

## Configuration Management

### Environment-Based Configuration
```python
from pydantic_settings import BaseSettings
from typing import Optional
import yaml
from pathlib import Path

class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Database
    database_url: str = "sqlite:///grodt.db"
    
    # API Configuration
    api_host: str = "localhost"
    api_port: int = 8000
    
    # Trading Configuration - NEVER hardcode these values
    max_position_size: float = 10000.0
    risk_tolerance: float = 0.02
    
    # Monitoring
    metrics_enabled: bool = True
    log_level: str = "INFO"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load from YAML configuration files
        self._load_yaml_configs()
    
    def _load_yaml_configs(self):
        """Load configuration from YAML files."""
        config_dir = Path("configs")
        if config_dir.exists():
            for config_file in config_dir.glob("*.yaml"):
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                    # Merge configuration data
                    self._merge_config(config_data)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### Configuration Management Rules
- **NO HARDCODING**: Never hardcode parameters in code
- **YAML Configuration**: All settings (risk, strategy, API keys) must be in `.yaml` configuration files
- **Environment Variables**: Sensitive data (API keys, passwords) in `.env` files
- **Configuration Loading**: Load configurations at application startup
- **Validation**: Validate all configuration values on startup

### Configuration Files
```yaml
# configs/trading.yaml
trading:
  max_position_size: 10000
  risk_tolerance: 0.02
  stop_loss_percentage: 0.05
  
strategies:
  trend_following:
    enabled: true
    parameters:
      lookback_period: 20
      threshold: 0.02
```

## Docker & Infrastructure

### Dockerfile Standards
```dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start application
CMD ["python", "-m", "grodtd.app"]
```

### Docker Compose Standards
```yaml
version: '3.8'

services:
  grodt:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=production
      - DATABASE_URL=sqlite:///app/data/grodt.db
    volumes:
      - ./data:/app/data
      - ./configs:/app/configs
    depends_on:
      - prometheus
      - grafana
    restart: unless-stopped
    
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./docker/prometheus:/etc/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped
```

## Security Standards

### Input Validation
```python
from pydantic import BaseModel, validator
from typing import List

class TradeOrder(BaseModel):
    """Validated trade order model."""
    
    symbol: str
    quantity: int
    side: str
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v.isalpha() or len(v) > 10:
            raise ValueError('Invalid symbol format')
        return v.upper()
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0 or v > 10000:
            raise ValueError('Quantity must be between 1 and 10000')
        return v
    
    @validator('side')
    def validate_side(cls, v):
        if v not in ['buy', 'sell']:
            raise ValueError('Side must be buy or sell')
        return v
```

### Secret Management
```python
import os
from cryptography.fernet import Fernet

class SecretManager:
    """Secure secret management."""
    
    def __init__(self):
        self.key = os.getenv('ENCRYPTION_KEY')
        if not self.key:
            raise ValueError("ENCRYPTION_KEY environment variable required")
        self.cipher = Fernet(self.key.encode())
    
    def encrypt_secret(self, secret: str) -> str:
        """Encrypt a secret value."""
        return self.cipher.encrypt(secret.encode()).decode()
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt a secret value."""
        return self.cipher.decrypt(encrypted_secret.encode()).decode()
```

## Performance Standards

### Async Operations
```python
import asyncio
import aiohttp
from typing import List, Dict

async def fetch_multiple_symbols(symbols: List[str]) -> Dict[str, Dict]:
    """Fetch data for multiple symbols concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_symbol_data(session, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            symbol: result for symbol, result in zip(symbols, results)
            if not isinstance(result, Exception)
        }
```

### Caching
```python
from functools import lru_cache
from typing import Dict, Any

@lru_cache(maxsize=128)
def get_market_data(symbol: str, timeframe: str) -> Dict[str, Any]:
    """Cached market data retrieval."""
    # Expensive operation here
    return fetch_from_api(symbol, timeframe)
```

### Database Optimization
```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

class DatabaseManager:
    """Optimized database operations."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def bulk_insert_trades(self, trades: List[Dict]) -> None:
        """Efficient bulk insert for trades."""
        with self.engine.connect() as conn:
            conn.execute(
                text("INSERT INTO trades (symbol, quantity, price) VALUES (:symbol, :quantity, :price)"),
                trades
            )
            conn.commit()
```

## Version Control (Git)

### Git Workflow
- **Branch Protection**: Never commit directly to the main branch
- **Feature Branches**: All work must be done in feature branches
- **Conventional Commits**: Use Conventional Commits for clear, atomic commit messages
  - Format: `type(scope): description` (e.g., `feat(risk): add capital thermostat`)
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- **Pull Requests**: All code must be reviewed and approved via a Pull Request (PR) before merging

### Commit Message Examples
```bash
feat(execution): add stop-loss order support
fix(monitoring): resolve metrics collection memory leak
docs(api): update trading endpoint documentation
test(strategy): add unit tests for trend detection
refactor(storage): extract database connection logic
chore(deps): update prometheus-client to v0.17.0
```

### Branch Naming Convention
- **Feature branches**: `feature/description` (e.g., `feature/stop-loss-orders`)
- **Bug fixes**: `fix/description` (e.g., `fix/metrics-memory-leak`)
- **Hotfixes**: `hotfix/description` (e.g., `hotfix/critical-trading-bug`)

## Review Process

### Code Review Checklist
- [ ] Code follows style guidelines (black, isort, ruff)
- [ ] Type hints are present and accurate
- [ ] Tests are comprehensive and pass
- [ ] Documentation is updated
- [ ] Security considerations addressed
- [ ] Performance implications considered
- [ ] Error handling is appropriate
- [ ] Logging is implemented correctly

### Pull Request Requirements
- **Title**: Clear, descriptive title
- **Description**: Detailed description of changes
- **Tests**: All tests must pass
- **Coverage**: Maintain or improve test coverage
- **Documentation**: Update relevant documentation
- **Breaking Changes**: Clearly marked and documented

### Quality Gates
- **Unit Tests**: 80% coverage minimum
- **Integration Tests**: All critical paths covered
- **Security Scan**: No high-severity vulnerabilities
- **Performance**: No significant performance regressions
- **Documentation**: All public APIs documented

## Tools and Automation

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.12
        args: [--line-length=88]
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: [--profile=black]
  
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.280
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, structlog]
        args: [--strict]
  
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
```

### CI/CD Pipeline
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      
      - name: Run linting
        run: uv run ruff check .
      
      - name: Run tests
        run: uv run pytest --cov=grodtd --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Key Requirements Summary

### 🚨 **MANDATORY REQUIREMENTS**

#### Project & Dependencies
- ✅ **Use `uv`** for all package and virtual environment management
- ✅ **NO HARDCODING** - All settings (risk, strategy, API keys) must be in `.yaml` configuration and `.env` files
- ✅ **Abstract external services** using handler classes for brokers, data sources, etc.

#### Code Style & Readability
- ✅ **Auto-format** ALL code with `black` and lint with `ruff`
- ✅ **Strictly follow PEP 8** naming conventions (snake_case for functions, PascalCase for classes)
- ✅ **MANDATORY type hinting** for all function signatures and variable declarations
- ✅ **Keep files focused** and modular, aiming for under 500 lines
- ✅ **Write clear docstrings** for every public function, class, and module

#### Testing & Quality
- ✅ **Target >85% code coverage** for all new logic
- ✅ **Practice TDD** for critical features
- ✅ **Mock all external API calls** in unit tests; use integration tests for live connections

#### Architecture & Design
- ✅ **Use structlog** for structured JSON logging to make post-trade analysis easy
- ✅ **Follow Single Responsibility Principle** - each class and function does one thing well

#### Version Control (Git)
- ✅ **Never commit directly to main** - All work must be done in feature branches
- ✅ **Use Conventional Commits** for clear, atomic commit messages (e.g., `feat(risk): add capital thermostat`)
- ✅ **All code must be reviewed** and approved via Pull Request (PR) before merging

## Conclusion

These development standards ensure consistent, maintainable, and high-quality code across the GRODT trading system. All team members should follow these guidelines to maintain code quality and project consistency.

**Remember**: These are not suggestions - they are mandatory requirements for all code contributions to the GRODT project.

For questions or clarifications, please refer to the project documentation or contact the development team.
