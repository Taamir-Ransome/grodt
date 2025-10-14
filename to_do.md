0) Accounts, Access, and Policies

 Robinhood account in good standing; 2FA enabled.

 Robinhood Crypto Trading API access enabled; create API keys/credentials.

 Decide environments: dev (paper/micro-live), prod (live).

 Exchange terms reviewed (order limits, rate limits, supported order types).

 Legal/Tax: log jurisdiction, record-keeping policy for trades (CSV/DB export).

1) Repositories and Project Structure

Create a mono-repo with two Python packages: grodtd (daemon/runtime) and grodtbt (backtesting/simulation).

grodt/
├─ README.md
├─ LICENSE
├─ pyproject.toml            # poetry config
├─ poetry.lock
├─ Makefile
├─ .env.example
├─ .gitignore
├─ .pre-commit-config.yaml
├─ docker/
│  ├─ Dockerfile
│  └─ docker-compose.yml
├─ infra/
│  ├─ grafana/               # dashboards (optional)
│  ├─ prometheus/            # metrics config (optional)
│  └─ nginx/                 # reverse proxy for dashboards (optional)
├─ configs/
│  ├─ settings.yaml          # global runtime config
│  ├─ risk.yaml              # risk limits
│  ├─ symbols.yaml           # tradable instruments
│  ├─ regime.yaml            # regime thresholds
│  └─ fees.yaml              # fee/slippage assumptions
├─ data/
│  ├─ raw/                   # raw candles/trades (parquet)
│  └─ features/              # feature store (parquet)
├─ grodtd/                   # runtime (live/paper)
│  ├─ __init__.py
│  ├─ app.py                 # entrypoint
│  ├─ connectors/            # robinhood api adapter, websockets
│  ├─ storage/               # sqlite/postgres adapters
│  ├─ features/              # VWAP/EMA/ATR/etc
│  ├─ strategies/            # S1/S2/S3 interfaces
│  ├─ regime/                # classifier/gating
│  ├─ risk/                  # sizing, limits, kill switch
│  ├─ execution/             # order router, OCO emulation
│  ├─ monitoring/            # logging, metrics, alerts
│  └─ utils/                 # common helpers
├─ grodtbt/                  # backtest & simulator
│  ├─ __init__.py
│  ├─ loader/                # historical data loaders
│  ├─ engine/                # vectorized + event simulation
│  ├─ metrics/               # PF, Sharpe, DD, IC
│  └─ reports/               # result writers
└─ tests/
   ├─ unit/
   └─ integration/

2) Tooling and Environment

 Python 3.11 (or newer, consistent across dev/CI/prod).

 Package manager: poetry.

 Lint/format: ruff, black, isort.

 Type checks: mypy (strict for core modules).

 Pre-commit hooks enabled (pre-commit).

 Docker installed; Docker Compose (or Podman).

 Make targets for common tasks (make setup test run fmt lint build).

 VSCode or PyCharm project settings (recommended linters/formatters on save).

3) Python Libraries (pin versions in pyproject.toml)

Core runtime:

 pandas (time series ops)

 numpy

 pyarrow (parquet IO)

 polars (optional fast dataframes)

 pandas_ta (or ta) for indicators

 numba (optional vectorization)

 httpx (async HTTP) or requests (sync)

 websockets or aiohttp (if WS is available)

 pydantic (settings validation)

 pyyaml (config files)

 python-dotenv (env loading)

 tenacity (retry/backoff)

 structlog (structured logging)

 prometheus-client (metrics, optional)

 schedule or APScheduler (cron-like jobs)

 sqlite3 (builtin) or sqlalchemy + psycopg for Postgres (later)
Backtesting & analysis:

 scikit-learn (simple models, regime classification)

 scipy (stats)

 matplotlib or plotly (reports)

 joblib (caching)
Dev/quality:

 pytest, pytest-cov

 mypy, ruff, black, isort

 pre-commit

4) Secrets and Configuration

 .env file (never commit) with:

RH_API_KEY, RH_API_SECRET, RH_ACCOUNT_ID (names per Robinhood spec)

ENV=dev|prod

DB strings (if Postgres later)

Notification tokens (email/Telegram) for alerts

 .env.example committed with placeholders.

 OS keychain or secret manager (optional) for prod.

 Config validation on boot with pydantic.

5) Data and Storage

 Historical OHLCV fetcher (1m/3m) for BTC, ETH (others later).

 Normalize and store as Parquet under data/raw/.

 Feature store writer:

anchored VWAP (UTC daily)

EMA(9), EMA(20), ATR(14), RSI(14)

optional: realized volatility, volume z-scores

 SQLite schema (MVP):

trades (executions)

orders (state machine)

positions (per symbol)

equity_curve (daily)

metrics_daily

 Backups: nightly Parquet/DB snapshot to off-box storage.

6) Connectors: Robinhood Crypto API

 HTTP client with retries/backoff, rate-limit handling.

 Minimal endpoints (wrap as methods):

get instruments / symbols

get quotes/aggregations (1m, 3m)

place order (market, limit, stop-limit)

get order status

cancel order

account/balance/positions

 Idempotency: clientOrderId scheme (e.g., symbol-timestamp-nonce).

 Clock/time-sync check (NTP) to ensure timestamps are reliable.

 OCO/bracket emulation in execution layer (submit TP/SL legs on fill; cancel sibling on execution).

7) Strategy Interfaces (no implementation yet)

 Base protocol:

prepare(state) -> None (precompute)

generate_signals(state) -> list[Signal]

on_fill(event) -> None

 S1 (VWAP+EMA trend scalper): parameters specified in configs/settings.yaml.

 S2 (Mean-reversion to VWAP): parameters in configs (disabled until regime=range).

 S3 (Breakout on trend days): gated by regime (disabled for MVP if desired).

8) Regime Classifier (lightweight MVP)

 Features: VWAP slope, ATR percentile, realized vol ratio.

 Rule-based thresholds in regime.yaml:

trend if |VWAP slope| > T1 and ATR% > T2

range if |VWAP slope| ≤ T3 and ATR% within band

 Unit tests to ensure gating behaves deterministically.

9) Risk Engine (hard rules before trading)

 Position sizing: risk per trade ≤ 0.75% equity; ATR-based stop distance.

 Global limits:

daily loss cap: min(3R, 3% equity)

max concurrent positions: 3

cooldown after 3 consecutive losses

 Kill switches:

slippage > 3σ baseline

latency spikes or repeated API failures

price feed desync vs secondary source (optional)

10) Execution Layer

 Maker-first preference for entries when feasible; market for exits.

 Quote/Order state machine:

NEW → ACK → PARTIAL_FILLED → FILLED → CANCELED/REPLACED

 Bracket emulation:

upon entry fill: place TP & SL; cancel opposite on execution.

 Re-quote logic:

if not filled within X seconds and spread widens, adjust or cancel.

 Slippage tracker:

record expected vs actual fill; rolling stats to metrics.

11) Backtesting and Simulation

 Vectorized backtester (fast parameter sweeps) with:

fee model, spread model, slip model

walk-forward splits (train/test by time)

 Event-driven simulator mirroring live engine:

latency model, partial fills, bracket behavior

 Report pack:

equity curve, drawdown, PF, Sharpe, hit rate, avg win/loss, trade distribution

 Reproducibility:

seed control, parameter snapshot with each run

12) Monitoring, Metrics, and Alerts

 Structured logs (structlog), rotating file handler.

 Metrics:

PnL, DD, PF, Sharpe (daily), hit rate

slippage, spread, latency, error counts

 Prometheus endpoint (optional) → Grafana dashboards.

 Alerts (email/Telegram):

fill notifications

daily PnL summary

risk breach or kill-switch trigger

connector/API errors

13) CI/CD and Quality Gates

 GitHub Actions (or similar):

lint, type-check, tests on PR

build Docker image on main

 Code owners for critical modules (even if single dev, enforce review ritual).

 Artifact retention: backtest result files uploaded to CI artifact store.

14) Runbooks and SOPs

 “First Boot” runbook: environment setup, .env creation, config sanity checks.

 “Daily Ops” runbook: start/stop services, logs to watch, metrics thresholds.

 “Incident” runbook: what to do on API outage, kill switch, or DB corruption.

 “Release” checklist: version bump, change log, rollback plan.

15) Acceptance Gates Before Any Live Trade

 Unit tests ≥ 85% coverage for risk/execution/accounting paths.

 Backtest results meet minimums on last 90 days (after fees & slippage):

PF ≥ 1.3, Max DD ≤ 12%, hit rate ≥ 60%, positive net expectancy.

 Paper trading 2–4 weeks:

PnL ≥ 0, PF ≥ 1.2, tracking error vs backtest within tolerance.

 Micro-live with tiny size (e.g., $5–$20 per order) ≥ 2 weeks:

live PF ≥ 1.2, DD ≤ 10%, operational KPIs green.

16) Makefile Targets (examples to define)

 make setup → install poetry deps, pre-commit, init DB.

 make fmt → run black + isort.

 make lint → ruff, mypy.

 make test → pytest with coverage.

 make bt → run backtests with config file.

 make run-dev → start runtime with ENV=dev.

 make docker-build / make docker-up.

17) Minimal Config Files (to create now)

 configs/settings.yaml:

symbols, timeframes, min liquidity/volume guards

endpoints, timeouts, retry/backoff

 configs/risk.yaml:

per-trade risk %, daily cap, cooldowns, max positions

 configs/regime.yaml:

VWAP slope thresholds, ATR percentiles

 configs/fees.yaml:

taker/maker, spread assumptions by symbol

 configs/symbols.yaml:

list of tradable coins on Robinhood (start: BTC, ETH)

18) Security and Reliability

 API keys read from env; never committed.

 Rotate API keys quarterly; restrict scopes to trade+read only.

 IP allow-list if supported; otherwise, alert on location change.

 Health checks:

liveness/readiness endpoints for container

periodic test call to API (no-op endpoint) with alarms

19) Initial Work Sequencing (what to do first)

 Create repo, commit scaffolding files, configure pre-commit.

 Add poetry config with pinned dependencies; run make setup.

 Implement Robinhood connector stubs (auth, quotes, place/cancel, status).

 Implement data loader (historical OHLCV) and Parquet writer.

 Implement feature store (VWAP/EMA/ATR) and validate against known formulas.

 Define risk + execution interfaces; stub strategy interface.

 Build vectorized backtester skeleton (fees/slippage included).

 Add unit tests for risk sizing, PnL accounting, and bracket emulation.

 Only then start coding S1 (VWAP+EMA) logic.