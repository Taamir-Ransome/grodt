# GRODT

Cryptocurrency trading system with daemon runtime (grodtd) and backtesting simulator (grodtbt) for automated trading on Robinhood Crypto API.

## Features

- **Automated Trading**: VWAP+EMA trend scalping, mean-reversion strategies
- **Risk Management**: Comprehensive risk controls and position sizing
- **Backtesting**: Vectorized and event-driven simulation
- **Real-time Monitoring**: Metrics, alerts, and dashboards

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Robinhood Crypto API access

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Taamir-Ransome/grodt.git
cd grodt
```

2. Install dependencies:
```bash
make setup
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your Robinhood API credentials
```

### Development

```bash
# Format code
make fmt

# Lint code
make lint

# Run tests
make test

# Start development server
make run-dev
```

## Project Structure

```
grodt/
├── grodtd/                   # Runtime (live/paper)
│   ├── connectors/           # Robinhood API adapter
│   ├── storage/              # Database adapters
│   ├── features/             # VWAP/EMA/ATR indicators
│   ├── strategies/            # Trading strategies
│   ├── regime/               # Market regime classifier
│   ├── risk/                 # Risk management
│   ├── execution/            # Order execution
│   └── monitoring/           # Logging and metrics
├── grodtbt/                  # Backtesting & simulation
│   ├── loader/               # Historical data loaders
│   ├── engine/              # Backtesting engine
│   ├── metrics/              # Performance metrics
│   └── reports/              # Result reports
├── configs/                  # Configuration files
├── data/                     # Data storage
└── tests/                    # Test suite
```

## License

MIT License - see LICENSE file for details.
