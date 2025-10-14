Product Requirements Document: S1 VWAP+EMA Trend Scalper
Status: Approved

Author: John, Product Manager

Date: 2025-10-13

## Project Analysis and Context

### Existing Project Overview
Analysis Source: IDE-based fresh analysis of flattened-codebase.xml.

Current Project State: The project is the "BMAD-METHOD," a framework for AI-assisted software development. The core infrastructure for data loading, technical indicators, risk management, and execution is complete.

### Enhancement Scope Definition
Type: New Feature Addition

Feature: S1: VWAP+EMA trend scalper strategy.

## Product Requirements: User Stories

### Epic: S1 Strategy - VWAP+EMA Trend Scalper
Description: As a trader, I want to deploy an automated strategy that identifies and acts on short-term trends by using VWAP and EMA indicators, so that I can generate profits from small price movements (scalping).

### User Stories

#### Story 1: Trend Identification

As a trading strategy, I need to calculate the Volume-Weighted Average Price (VWAP) and a short-term Exponential Moving Average (EMA) for BTC and ETH on a 1-minute timeframe.

Acceptance Criteria:

The system correctly fetches 1-minute OHLCV data.

VWAP is calculated and updated with each new bar.

A configurable short-term EMA (e.g., 9-period) is calculated and updated.

A trend is considered "up" when the price is above both VWAP and EMA.

A trend is considered "down" when the price is below both VWAP and EMA.

#### Story 2: Trade Entry

As a trading strategy, I need to execute a market buy order when an uptrend is confirmed and a market sell order when a downtrend is confirmed.

Acceptance Criteria:

A buy order is placed when price > VWAP AND price > EMA.

A sell order is placed when price < VWAP AND price < EMA.

Orders are routed through the execution engine.

The position size is calculated based on the ATR-based stop distance defined in the risk management system.

#### Story 3: Trade Exit (Take Profit & Stop Loss)

As a trading strategy, I need to place bracket orders (Take Profit and Stop Loss) immediately after a position is opened to manage risk.

Acceptance Criteria:

A Take Profit (TP) order is placed at a configurable risk/reward ratio (e.g., 1.5:1).

A Stop Loss (SL) order is placed based on the Average True Range (ATR) at the time of entry.

The execution engine successfully emulates OCO/bracket functionality.

## Technical Specifications & Implementation Plan

### Component Architecture & Integration
The S1_VWAP_EMA_Scalper will be a new module implementing the existing Strategy Interface. It will integrate with the Data Loader, Technical Indicators library, Position Sizing module, Execution Engine, and Bracket Emulation feature.

### Data Flow
Fetch: Historical Data Fetcher retrieves 1m OHLCV data.

Stream: Data is passed to the S1_VWAP_EMA_Scalper.

Calculate: The strategy computes VWAP, EMA, and ATR.

Signal: A trade signal is generated based on the entry logic.

Size: The Position Sizing module returns the order quantity.

Execute: The Execution Engine places the initial order.

Bracket: On fill, the Bracket Emulation logic places TP/SL orders.

### Configuration
A new configuration file, strategies.yaml, will manage strategy parameters:

```yaml
S1_VWAP_EMA_Scalper:
  enabled: true
  symbols: [BTC/USD, ETH/USD]
  timeframe: 1m
  ema_period: 9
  atr_period: 14
  risk_reward_ratio: 1.5
```

## Dependencies

### Core Dependencies (Must be completed first)
📊 Historical data fetcher (1m/3m) for BTC, ETH

⚠️ Position sizing with ATR-based stop distance

🎯 Bracket emulation (TP & SL on fill)

🔧 Strategy parameter configuration from YAML files

### Indirect Dependencies
🔌 HTTP client & WebSocket client

🧠 Regime Classification Features (for future performance analysis)