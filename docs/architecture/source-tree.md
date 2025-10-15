# Source Tree Structure

## Overview

This document defines the source tree structure for the GRODT trading system, providing clear organization and navigation guidelines for developers.

## Root Directory Structure

```
grodt/
├── README.md                    # Project overview and setup instructions
├── LICENSE                      # MIT License
├── pyproject.toml              # Python project configuration
├── uv.lock                      # Dependency lock file
├── Makefile                     # Build and development commands
├── .gitignore                   # Git ignore patterns
├── .pre-commit-config.yaml      # Pre-commit hooks configuration
├── .env.example                 # Environment variables template
├── docker/                      # Docker configuration
├── docs/                        # Documentation
├── grodtd/                      # Main application code
├── grodtbt/                     # Backtesting framework
├── tests/                       # Test suite
├── configs/                     # Configuration files
├── data/                        # Data storage
├── logs/                        # Application logs
└── infra/                       # Infrastructure configuration
```

## Core Application (`grodtd/`)

### Main Application Structure
```
grodtd/
├── __init__.py                  # Package initialization
├── app.py                       # Application entry point
├── web_app.py                   # Flask web application
├── config/                      # Configuration management
│   ├── __init__.py
│   ├── alpaca_config.py         # Alpaca API configuration
│   └── robinhood_config.py      # Robinhood API configuration
├── connectors/                  # External API connectors
│   ├── __init__.py
│   ├── base.py                  # Base connector interface
│   ├── factory.py               # Connector factory
│   ├── alpaca.py                # Alpaca API connector
│   └── robinhood.py             # Robinhood API connector
├── execution/                   # Trading execution engine
│   ├── __init__.py
│   ├── engine.py                # Main execution engine
│   ├── signal_service.py        # Signal processing
│   ├── strategy_gating_service.py # Strategy enable/disable
│   ├── trade_entry_service.py   # Trade entry logic
│   └── trade_exit_service.py    # Trade exit logic
├── features/                    # Feature engineering
│   ├── __init__.py
│   ├── indicators.py           # Technical indicators
│   └── regime_features.py       # Regime classification features
├── monitoring/                  # Monitoring and metrics
│   ├── __init__.py
│   ├── metrics_collector.py     # Metrics collection
│   ├── metrics_endpoint.py      # Prometheus endpoint
│   ├── trading_metrics.py       # Trading-specific metrics
│   ├── system_metrics.py        # System performance metrics
│   └── business_metrics.py       # Business metrics
├── regime/                      # Market regime classification
│   ├── __init__.py
│   ├── classifier.py            # Regime classifier
│   ├── integration.py           # Integration with trading
│   ├── logging.py               # Regime logging
│   └── service.py               # Regime service
├── risk/                        # Risk management
│   ├── __init__.py
│   └── manager.py               # Risk management logic
├── storage/                     # Data storage layer
│   ├── __init__.py
│   ├── backup_cli.py            # Backup command line tool
│   ├── backup_manager.py        # Backup management
│   ├── data_loader.py           # Data loading utilities
│   ├── feature_api.py           # Feature store API
│   ├── feature_store.py         # Feature store implementation
│   ├── interfaces.py            # Storage interfaces
│   ├── retention_cleanup.py     # Data retention cleanup
│   ├── retention_cli.py         # Retention command line tool
│   ├── retention_config.py      # Retention configuration
│   ├── retention_integrity.py   # Data integrity checks
│   ├── retention_logging.py     # Retention logging
│   ├── retention_manager.py     # Retention management
│   ├── retention_models.py      # Retention data models
│   ├── retention_monitoring.py  # Retention monitoring
│   └── retention_scheduler.py   # Retention scheduling
├── strategies/                  # Trading strategies
│   ├── __init__.py
│   ├── base.py                  # Base strategy class
│   └── s1_trend_strategy.py     # Trend following strategy
├── analytics/                   # Analytics and reporting
│   ├── __init__.py
│   └── regime_performance_service.py # Regime performance analysis
└── utils/                       # Utility functions
    ├── __init__.py
    ├── data_utils.py            # Data manipulation utilities
    ├── math_utils.py            # Mathematical utilities
    └── time_utils.py            # Time handling utilities
```

## Backtesting Framework (`grodtbt/`)

### Backtesting Structure
```
grodtbt/
├── __init__.py                  # Package initialization
└── engine/                      # Backtesting engine
    ├── __init__.py
    └── backtester.py            # Main backtesting engine
```

## Test Suite (`tests/`)

### Test Organization
```
tests/
├── __init__.py                  # Test package initialization
├── unit/                        # Unit tests
│   ├── __init__.py
│   ├── test_monitoring/         # Monitoring unit tests
│   │   └── test_grafana_dashboards.py
│   ├── test_execution/          # Execution unit tests
│   ├── test_strategies/          # Strategy unit tests
│   ├── test_storage/             # Storage unit tests
│   └── test_utils/               # Utility unit tests
├── integration/                 # Integration tests
│   ├── __init__.py
│   ├── test_monitoring/         # Monitoring integration tests
│   │   └── test_grafana_integration.py
│   ├── test_api/                 # API integration tests
│   ├── test_database/            # Database integration tests
│   └── test_trading/             # Trading integration tests
└── e2e/                         # End-to-end tests
    ├── __init__.py
    ├── test_trading_workflow.py  # Complete trading workflow
    └── test_monitoring_workflow.py # Monitoring workflow
```

## Configuration (`configs/`)

### Configuration Files
```
configs/
├── backup.yaml                  # Backup configuration
├── regime.yaml                  # Regime classification config
├── retention.yaml               # Data retention configuration
├── risk.yaml                    # Risk management configuration
├── robinhood.yaml               # Robinhood API configuration
├── settings.yaml                # General application settings
└── strategy_gating.yaml         # Strategy gating configuration
```

## Docker Configuration (`docker/`)

### Docker Structure
```
docker/
├── Dockerfile                   # Main application Dockerfile
├── docker-compose.yml           # Multi-container orchestration
├── grafana/                     # Grafana configuration
│   ├── grafana.ini              # Grafana server configuration
│   ├── datasources/             # Data source configurations
│   │   └── prometheus.yml       # Prometheus data source
│   └── dashboards/              # Dashboard definitions
│       ├── dashboard.yml        # Dashboard provisioning
│       ├── home.json            # Overview dashboard
│       ├── trading-performance.json # Trading metrics dashboard
│       ├── system-health.json   # System health dashboard
│       ├── regime-classification.json # Regime dashboard
│       └── strategy-performance.json # Strategy dashboard
└── prometheus/                  # Prometheus configuration
    └── prometheus.yml           # Prometheus server configuration
```

## Documentation (`docs/`)

### Documentation Structure
```
docs/
├── architecture/               # Architecture documentation
│   ├── index.md                # Architecture overview
│   ├── introduction.md         # System introduction
│   ├── system-overview-logical-architecture.md
│   ├── data-architecture.md    # Data architecture
│   ├── deployment-architecture.md # Deployment architecture
│   ├── monitoring-observability.md # Monitoring architecture
│   ├── component-deep-dive.md  # Component details
│   ├── architectural-goals-constraints.md
│   ├── cicd-pipeline-github-actions.md
│   ├── coding-standards.md     # Development standards
│   ├── tech-stack.md           # Technology stack
│   └── source-tree.md          # This file
├── prd/                        # Product requirements
│   ├── index.md                # PRD overview
│   ├── dependencies.md         # Project dependencies
│   ├── product-requirements-user-stories.md
│   ├── project-analysis-and-context.md
│   └── technical-specifications-implementation-plan.md
├── prd-phase2/                 # Phase 2 requirements
├── prd-phase3/                 # Phase 3 requirements
├── prd-phase4/                 # Phase 4 requirements
├── stories/                    # User stories
│   ├── 1.1.trend-identification.md
│   ├── 1.2.trade-entry.md
│   ├── 1.3.trade-exit.md
│   ├── 2.1.1.market-regime-classification.md
│   ├── 2.1.2.regime-based-strategy-gating.md
│   ├── 2.1.3.regime-performance-analytics.md
│   ├── 2.2.1.historical-data-pipeline.md
│   ├── 2.2.2.parquet-backup-system.md
│   ├── 2.2.3.data-retention-cleanup.md
│   ├── 2.2.4.feature-store-implementation.md
│   ├── 2.3.1.prometheus-metrics-collection.md
│   └── 2.3.2.grafana-dashboard-creation.md
├── qa/                         # Quality assurance
│   ├── assessments/            # QA assessments
│   └── gates/                  # Quality gates
└── system-architecture.md      # System architecture overview
```

## Data Storage (`data/`)

### Data Organization
```
data/
├── backups/                    # Database backups
├── features/                   # Feature store data
└── raw/                        # Raw market data
```

## Infrastructure (`infra/`)

### Infrastructure Configuration
```
infra/
├── grafana/                    # Grafana infrastructure
├── nginx/                      # Nginx configuration
└── prometheus/                 # Prometheus infrastructure
```

## File Naming Conventions

### Python Files
- **Modules**: `snake_case.py`
- **Classes**: `PascalCase` in files
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`

### Configuration Files
- **YAML**: `kebab-case.yaml`
- **JSON**: `kebab-case.json`
- **INI**: `kebab-case.ini`

### Documentation Files
- **Markdown**: `kebab-case.md`
- **Sections**: Use `#` for main headings, `##` for subsections

## Import Organization

### Standard Library Imports
```python
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
```

### Third-Party Imports
```python
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify
from sqlalchemy import create_engine
```

### Local Imports
```python
from grodtd.execution.engine import ExecutionEngine
from grodtd.storage.feature_store import FeatureStore
from grodtd.monitoring.metrics_collector import MetricsCollector
```

## Module Responsibilities

### Core Application (`grodtd/`)
- **app.py**: Application entry point and initialization
- **web_app.py**: Flask web interface and API endpoints
- **config/**: Configuration management and environment handling
- **connectors/**: External API integration (Alpaca, Robinhood)
- **execution/**: Trading execution logic and order management
- **features/**: Feature engineering and technical indicators
- **monitoring/**: Metrics collection and observability
- **regime/**: Market regime classification and analysis
- **risk/**: Risk management and position sizing
- **storage/**: Data persistence and retrieval
- **strategies/**: Trading strategy implementations
- **analytics/**: Performance analysis and reporting
- **utils/**: Shared utility functions

### Backtesting (`grodtbt/`)
- **engine/**: Backtesting engine for strategy validation

### Testing (`tests/`)
- **unit/**: Isolated unit tests for individual components
- **integration/**: Integration tests for component interactions
- **e2e/**: End-to-end tests for complete workflows

## Development Guidelines

### Adding New Features
1. **Create module** in appropriate directory
2. **Add tests** in corresponding test directory
3. **Update documentation** in docs/ directory
4. **Add configuration** if needed in configs/
5. **Update imports** and dependencies

### File Organization
- **One class per file** for complex classes
- **Group related functions** in utility modules
- **Separate concerns** across different modules
- **Keep modules focused** on single responsibility

### Documentation Requirements
- **Module docstrings** for all Python modules
- **Function docstrings** for all public functions
- **Class docstrings** for all classes
- **Type hints** for all function signatures
- **Examples** in docstrings where helpful

## Conclusion

This source tree structure provides clear organization and navigation for the GRODT trading system. Following these guidelines ensures consistent code organization and makes the codebase maintainable and scalable.

For questions about the source tree structure or adding new components, please refer to the development team or project documentation.
