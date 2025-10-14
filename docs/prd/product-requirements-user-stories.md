# Product Requirements: User Stories

## Epic: S1 Strategy - VWAP+EMA Trend Scalper
Description: As a trader, I want to deploy an automated strategy that identifies and acts on short-term trends by using VWAP and EMA indicators, so that I can generate profits from small price movements (scalping).

## User Stories

### Story 1: Trend Identification

As a trading strategy, I need to calculate the Volume-Weighted Average Price (VWAP) and a short-term Exponential Moving Average (EMA) for BTC and ETH on a 1-minute timeframe.

Acceptance Criteria:

The system correctly fetches 1-minute OHLCV data.

VWAP is calculated and updated with each new bar.

A configurable short-term EMA (e.g., 9-period) is calculated and updated.

A trend is considered "up" when the price is above both VWAP and EMA.

A trend is considered "down" when the price is below both VWAP and EMA.

### Story 2: Trade Entry

As a trading strategy, I need to execute a market buy order when an uptrend is confirmed and a market sell order when a downtrend is confirmed.

Acceptance Criteria:

A buy order is placed when price > VWAP AND price > EMA.

A sell order is placed when price < VWAP AND price < EMA.

Orders are routed through the execution engine.

The position size is calculated based on the ATR-based stop distance defined in the risk management system.

### Story 3: Trade Exit (Take Profit & Stop Loss)

As a trading strategy, I need to place bracket orders (Take Profit and Stop Loss) immediately after a position is opened to manage risk.

Acceptance Criteria:

A Take Profit (TP) order is placed at a configurable risk/reward ratio (e.g., 1.5:1).

A Stop Loss (SL) order is placed based on the Average True Range (ATR) at the time of entry.

The execution engine successfully emulates OCO/bracket functionality.
