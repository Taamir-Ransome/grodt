# System Overview (Logical Architecture)
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
