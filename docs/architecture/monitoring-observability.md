# Monitoring & Observability
Metrics (Prometheus): The Python application exposes key performance indicators (KPIs) on a /metrics endpoint, including PnL, max drawdown, slippage, and API latency.

Logging (structlog): All log output is in a structured JSON format. This allows for easy parsing and searching, and includes contextual information like strategy_name or order_id.

Visualization (Grafana): Pre-built dashboards provide real-time visualization of PnL curves, open positions, operational metrics, and system health.
