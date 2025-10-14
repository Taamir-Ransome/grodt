# Data Architecture

## Data Flow
Real-time: WebSocket Connector streams quotes and trades -> Data Layer processes into 1-minute OHLCV bars -> Strategy Engine consumes bars.

Historical: HTTP Connector fetches historical data on startup -> Data Layer backfills the SQLite database.

Trade Data: Execution Engine writes all orders and fills -> SQLite Database.

## Database Schema (SQLite)
trades: Records every filled trade (id, timestamp, symbol, side, price, quantity).

orders: Tracks the lifecycle of every order (id, client_order_id, status, symbol, quantity, submit_timestamp, fill_timestamp).

positions: Maintains the current portfolio positions (symbol, quantity, average_entry_price).

equity_curve: Stores a timeseries of portfolio value for performance tracking (timestamp, portfolio_value).

## Data Backup
A scheduled nightly job reads the SQLite database, converts the main tables to the Parquet format, and saves them to a backup location. This provides a compressed, column-oriented backup suitable for analytics.
