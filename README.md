# Algorithmic Trading Bot

## Project Overview

This project is an automated, event-driven algorithmic trading bot designed to execute high-frequency scalping strategies on cryptocurrency pairs using the Robinhood API.

The core of the system is a sophisticated trading engine built on Python, leveraging a modern, high-performance technology stack. It is designed for modularity, allowing for the easy addition of new trading strategies, data sources, and risk management modules.

The first strategy implemented is the S1: VWAP+EMA Trend Scalper, which serves as the foundational model for future strategy development. The system includes a vectorized backtester for strategy optimization, real-time monitoring with Prometheus and Grafana, and a robust CI/CD pipeline for automated testing and deployment.

## The BMAD-METHOD Framework

This project is developed using the BMAD-METHOD (Breakthrough Method for Agile AI-Driven Development). This is a framework that utilizes specialized AI agents (like myself, your PM) to collaboratively generate and refine project artifacts, ensuring a high level of precision and alignment from planning to deployment. All planning documents, including the PRD and architecture, are versioned in Git to provide a single source of truth.

## System Architecture
The system is designed as a modular, containerized application, with distinct services for data handling, strategy execution, and monitoring.

Data Layer: Responsible for fetching both historical and real-time market data from the Robinhood API (via HTTP and WebSocket). It also manages data storage in a local SQLite database and nightly backups to Parquet files.

Core Engine: The central component that houses the trading logic. It includes the strategy interface, execution engine, risk management system, and technical indicator library.

Monitoring & Alerting: A dedicated stack using Prometheus for metrics collection and Grafana for visualization. Structured logging with structlog provides detailed operational insights.

Backtesting Engine: An offline, vectorized backtester (vectorbt) allows for rapid testing and optimization of strategies against historical data.

## Technology Stack

- **Programming Language**: Python 3.11+
- **Package Management**: uv (a high-performance Python package manager written in Rust)

### API Interaction
- **robin_stocks**: A Python library for interacting with the Robinhood API
- **requests**: For HTTP API calls
- **websockets**: For real-time data streaming

### Data & Storage
- **pandas**: For data manipulation and analysis
- **numpy**: For numerical operations
- **SQLite**: For storing trades, orders, and portfolio data
- **pyarrow**: For working with the Apache Parquet file format for backups
- **vectorbt**: A high-performance vectorized backtesting library

### Monitoring & Logging
- **Prometheus**: For time-series metrics
- **Grafana**: For dashboarding and visualization
- **structlog**: For structured, context-aware logging

### Containerization
- **Docker**: To containerize the application and its services
- **Docker Compose**: To orchestrate the multi-container environment
- **CI/CD**: GitHub Actions for automated builds, testing, and deployment
- **Configuration**: YAML for all configuration files

## Project Structure
/
├── .github/              # GitHub Actions CI/CD workflows
├── .vscode/              # VSCode editor settings
├── data/                 # Data storage (SQLite DB, Parquet backups)
├── docs/                 # Project documentation (PRD, Architecture)
├── src/                  # Main source code
│   ├── api/              # Robinhood API connectors
│   ├── backtester/       # Vectorized backtesting engine
│   ├── config/           # YAML configuration files
│   ├── core/             # Core trading engine components
│   ├── strategies/       # Trading strategy implementations (e.g., S1)
│   └── utils/            # Utility functions and helpers
├── tests/                # Unit and integration tests
├── .dockerignore         # Files to ignore in Docker builds
├── .gitignore            # Files to ignore in Git
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Dockerfile for the main application
├── Makefile              # Makefile for common commands
├── README.md             # This file
└── settings.yaml         # Main application settings
## Configuration

The bot's behavior is controlled by a set of YAML files located in `src/config/`:

- **settings.yaml**: Main application settings, including symbols, timeframes, and API endpoints
- **risk.yaml**: Global risk management parameters (daily loss caps, max positions, etc.)
- **regime.yaml**: Parameters for the market regime filter
- **strategies.yaml**: Configuration for individual trading strategies

## Setup and Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd <repository-name>
   ```

2. **Install uv:**
   ```bash
   pip install uv
   ```

3. **Create virtual environment and install dependencies:**
   ```bash
   make setup
   ```

4. **Configure API Keys:**
   - Copy the `.env.example` file to `.env`
   - Add your Robinhood API credentials to the `.env` file

## Running the Bot

### Development Mode
```bash
make run-dev
```

### Production Mode (with Docker Compose)
```bash
make docker-build
make docker-up
```

## Backtesting and Optimization

The vectorized backtester can be run to test strategies against historical data:

```bash
make bt --strategy=S1 --start-date="2023-01-01" --end-date="2023-12-31"
```

This command will run the S1 strategy on the specified date range and output performance metrics (Profit Factor, Sharpe Ratio, Max Drawdown, etc.).

## Monitoring and Logging

Once the application is running in Docker, you can access:

- **Grafana Dashboards**: http://localhost:3000
- **Prometheus Metrics**: http://localhost:9090

Logs are output in a structured JSON format for easy parsing and analysis.

## CI/CD Pipeline

The CI/CD pipeline is defined in `.github/workflows/`. On every push to the main branch or on pull requests, the pipeline will:

- Lint and format the code
- Run all unit and integration tests
- Build the Docker image
- (On merge to main) Push the image to a container registry and deploy to the production environment

## Testing

- **Unit Tests**: Located in the `tests/` directory, covering individual components. Run with `make test`
- **Integration Tests**: Test the interaction between different components, especially the API connectors
- **Paper Trading**: The bot should be run in a paper trading environment for 2-4 weeks to validate performance before live deployment

## Security

- **API Keys**: Never commit API keys or other secrets to the repository. Use environment variables and a `.env` file
- **Key Rotation**: Rotate API keys quarterly
- **IP Whitelisting**: If supported by the exchange, whitelist the IP addresses of your production servers

## Roadmap

- Implement additional strategies (S2: Mean Reversion, S3: Breakout)
- Expand data sources to include other exchanges
- Develop a more sophisticated machine learning-based regime filter
- Enhance Grafana dashboards with more detailed performance analytics