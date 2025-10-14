System Architecture Document: Algorithmic Trading Bot
Status: Final

Author: John, Product Manager (Synthesized from Project Requirements)

Date: 2025-10-13

## Introduction
This document outlines the software architecture for the Algorithmic Trading Bot. The system is designed to be a modular, resilient, and performant platform for developing and deploying automated trading strategies. The initial implementation focuses on executing the S1: VWAP+EMA Trend Scalper strategy via the Robinhood API, with a clear path for future expansion.

## Architectural Goals & Constraints
The architecture is designed to meet the following key objectives:

Modularity: Components are decoupled, allowing for independent development, testing, and replacement. A new strategy or API connector can be added with minimal impact on the rest of the system.

Performance: The system must handle real-time market data and execute orders with low latency to minimize slippage.

Reliability: The system must be resilient to failures, including API disconnects and unexpected errors. It incorporates features like kill switches and robust error handling.

Testability: The architecture supports comprehensive testing, from unit tests of individual components to end-to-end backtesting and paper trading validation.

Scalability: While the initial deployment is a single node, the containerized design allows for future scaling of individual components.

## System Overview (Logical Architecture)
The system is composed of several high-level logical blocks that work together to execute the trading lifecycle.

Code snippet

graph TD
    subgraph "External"
        A[Robinhood API]
    end

    subgraph "Trading Bot System"
        B[API Connectors] -- Market Data --> C{Data Layer}
        C -- OHLCV Bars --> D[Strategy Engine]
        D -- Trade Signals --> E[Execution Engine]
        E -- Orders --> B
        A -- Order Fills & State --> B
        B -- Fill Confirmations --> E

        F[Indicator Library] --> D
        G[Risk Management] --> D
        H[Configuration Files] --> D
        H --> G
        H --> E
    end

    style A fill:#FF9999
    style B fill:#99CCFF
    style C fill:#99FF99
    style D fill:#FFFF99
    style E fill:#FFCC99
API Connectors: The gateway to the external world. Manages all communication with the Robinhood API (both WebSocket for real-time data and REST for orders).

Data Layer: Responsible for ingesting, storing, and providing market data. It writes to and reads from a local SQLite database.

Strategy Engine: The brain of the system. It consumes market data, applies technical indicators, and generates trading signals based on the logic of the loaded strategy (e.g., S1).

Execution Engine: Acts on signals from the Strategy Engine. It constructs and places orders, manages their lifecycle (e.g., NEW → FILLED), and emulates complex order types like brackets.

Risk Management: A critical service that is queried by the Strategy Engine before placing any trade. It enforces rules like position sizing and global loss limits.

Indicator Library: A collection of reusable technical analysis functions (VWAP, EMA, ATR, etc.).

## Deployment Architecture
The application is fully containerized using Docker and orchestrated with Docker Compose for local deployment and testing. This ensures a consistent and reproducible environment.

Code snippet

graph TD
    subgraph "Docker Host"
        subgraph "Docker Network"
            A[Trading Bot App]
            B[Prometheus]
            C[Grafana]
        end
        D[(SQLite DB Volume)]

        A -- Python App --> D
        A -- /metrics endpoint --> B
        B -- Prometheus Query --> C
    end

    style A fill:#99CCFF
    style B fill:#FFCC99
    style C fill:#99FF99
Trading Bot App: The main Python application container running all core services (data, strategy, execution).

Prometheus: A time-series database container that scrapes the /metrics endpoint exposed by the Trading Bot App.

Grafana: A visualization platform container that connects to Prometheus as a data source to display real-time performance dashboards.

SQLite DB Volume: A persistent Docker volume is used to store the SQLite database file, ensuring that trade history and other data survive container restarts.

## Data Architecture

### Data Flow
Real-time: WebSocket Connector streams quotes and trades -> Data Layer processes into 1-minute OHLCV bars -> Strategy Engine consumes bars.

Historical: HTTP Connector fetches historical data on startup -> Data Layer backfills the SQLite database.

Trade Data: Execution Engine writes all orders and fills -> SQLite Database.

### Database Schema (SQLite)
trades: Records every filled trade (id, timestamp, symbol, side, price, quantity).

orders: Tracks the lifecycle of every order (id, client_order_id, status, symbol, quantity, submit_timestamp, fill_timestamp).

positions: Maintains the current portfolio positions (symbol, quantity, average_entry_price).

equity_curve: Stores a timeseries of portfolio value for performance tracking (timestamp, portfolio_value).

### Data Backup
A scheduled nightly job reads the SQLite database, converts the main tables to the Parquet format, and saves them to a backup location. This provides a compressed, column-oriented backup suitable for analytics.

## Component Deep Dive
API Connectors: Implements retry logic with exponential backoff and handles API rate limits. Uses a clientOrderId scheme for idempotency.

Execution Engine: Features a finite state machine for order tracking (NEW → ACK → PARTIAL → FILLED / CANCELED). The bracket emulation logic listens for a fill confirmation of an entry order and immediately submits the corresponding Take Profit and Stop Loss orders.

Risk Management: Calculates position sizes based on the ATR-based stop distance. It also checks against global limits (e.g., daily_loss_cap, max_positions) defined in risk.yaml before approving any trade signal.

Strategy Interface: A base class that defines the required methods for any new strategy (e.g., on_bar(bar_data), on_fill(fill_data)). The S1 strategy is the first implementation of this interface.

## Monitoring & Observability
Metrics (Prometheus): The Python application exposes key performance indicators (KPIs) on a /metrics endpoint, including PnL, max drawdown, slippage, and API latency.

Logging (structlog): All log output is in a structured JSON format. This allows for easy parsing and searching, and includes contextual information like strategy_name or order_id.

Visualization (Grafana): Pre-built dashboards provide real-time visualization of PnL curves, open positions, operational metrics, and system health.

## CI/CD Pipeline (GitHub Actions)
The pipeline automates quality assurance and deployment:

Trigger: On push to main or pull request.

Lint & Format: Runs code formatters and linters.

Test: Executes the full suite of unit tests with make test.

Build: Builds the Docker image.

Deploy: Pushes the new Docker image to a container registry and triggers a webhook to redeploy the application in the production environment.