# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env  # then edit .env with BOT_ENCRYPTION_KEY

# Run (activate venv first)
python3 run_bot.py --profile local_paper      # paper trading, no API keys needed
python3 run_bot.py --profile phemex_testnet   # testnet, requires API keys in .env
python3 run_bot.py --profile phemex_live      # live trading, requires API keys in .env

# Alternatively via shell wrapper
./run_bot.sh local_paper

# Reporting utilities
python3 equity_report.py
python3 trades_report.py
python3 plot_equity.py
python3 healthcheck.py
python3 reconcile.py
```

## Environment Variables (.env)

- `BOT_ENCRYPTION_KEY` — required for all profiles (encrypts state files at rest)
- `PHEMEX_API_KEY` / `PHEMEX_API_SECRET` — required for testnet/live profiles
- `BOT_ENV` — set to `development` or `test` to allow auto-generated encryption keys (bypasses `BOT_ENCRYPTION_KEY` requirement for local dev)

## Testing

No automated test suite exists. Validate strategy logic by running scripts in [research/](research/) against historical data.

## Architecture

The bot is a polling loop that fetches OHLCV candles, computes indicators, generates signals, and submits orders through a broker abstraction.

**Entry point**: [run_bot.py](run_bot.py) — parses `--profile` arg, loads [config.json](config.json), validates config, instantiates the correct broker, then calls `run_loop()`.

**Main loop**: [runner.py](runner.py) — `run_loop()` polls on `poll_seconds` cadence, calls broker to fetch candles, calls strategy for signals, manages position state, tracks daily loss limits and API error circuit breaker.

**Strategy**: [strategy.py](strategy.py) — pure functions for indicator computation and signal generation. Key functions:
- `compute_4h_indicators()` — computes SMA200, RSI, MACD, ADX, volume indicators, MFI, CMF for signal timeframe
- `compute_daily_regime()` — computes 200-day MA slope to classify bull/bear/neutral regime
- `entry_signal()` / `exit_signal()` — return buy/sell decisions based on active strategy (dispatches by `strategy` name)
- Three strategy modes (select via `"strategy"` key in config profile):
  - `"obv_breakout"` — OBV accumulation + volume breakout, trend-following. **Active default.** Active pairs: ETH, SOL, TRX, ADA, BAT, LTC, RUNE. ~3–10% annual, SL 4%, TP 10%, max 30 candles.
  - `"vwap_band_bounce"` — mean reversion at VWAP lower band (-2σ). Active pair: VTHO (via `symbol_strategy` override). SL 3.5%, TP 6%, max 12 candles.
  - `"rsi_momentum_pullback"` — RSI pullback in SMA200 uptrend. Uses 2-of-3 momentum scoring (MACDh, ImpulseMACD, StochRSI). Bypasses regime filter (`ignore_regime_filter: true`).
- Per-symbol strategy routing: `"symbol_strategy": {"VTHO/USDT": "vwap_band_bounce"}` overrides the default strategy for specific symbols.
- Strategy parameter blocks live as sub-objects keyed by strategy name inside each profile (e.g. `obv_breakout: {...}`).

**Brokers**: [brokers.py](brokers.py) — `PaperBroker` (simulated fills, local state) and `ExchangeBroker` (real ccxt orders). Both share the same interface. State files are Fernet-encrypted. `ExchangeBroker` supports `hard_stops` via stop-market orders on Phemex.

**Configuration**: [config.json](config.json) — profiles (`local_paper`, `phemex_testnet`, `phemex_live`) each containing all trading parameters. Strategy parameters live inside nested sub-objects per strategy name within each profile.

**Reporting utilities** (standalone scripts, not part of the loop):
- [reconcile.py](reconcile.py) — reconciles fills vs orders, computes PnL
- [equity_report.py](equity_report.py) / [trades_report.py](trades_report.py) — tabular summaries from CSV logs
- [plot_equity.py](plot_equity.py) — matplotlib equity curve
- [healthcheck.py](healthcheck.py) — checks if bot process is running and log is recent

**State files** (encrypted JSON, per-profile):
- `*_state.json` — open positions and portfolio state
- `*_runtime_state.json` — cooldown timers, daily loss tracking
- `*_fills_state.json` — fill reconciliation state (exchange profiles only)

**Research scripts**: [research/](research/) — backtesting and strategy validation scripts (not used at runtime):
- `backtest_engine.py` — `BacktestConfig`, `run_backtest()`, `walk_forward()`, `purged_cv()`
- `optimize_params.py` — per-symbol grid search over purged CV Sharpe objective
- `regime_strategy_analysis.py` — HMM regime switching backtest/WFO analysis
- `train_regime_hmm.py` — train 3-state GaussianHMM on daily OHLCV (bull/sideways/bear)
- `train_signal_filter.py` — train LightGBM signal quality classifier
- `fetch_data.py` — download OHLCV history (Binance/CryptoCompare fallback)

**Models**: [models/](models/) — trained model artifacts:
- `regime_hmm.pkl` — GaussianHMM trained on ETH daily (3352 bars, 2017–2026)
- `regime_hmm_states.json` — state label mapping + HMM inference config

## Docker Deployment

The bot can be run via Docker Compose for consistent, isolated deployments.

```bash
# Smoke test (paper, local image)
docker build -t phemex-bot:local .
docker run --rm --env-file .env \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/logs:/app/logs \
  phemex-bot:local python3 -m src.run_bot --profile local_paper

# Deploy testnet
docker compose --profile testnet up -d

# Deploy live (only after 24h clean testnet run)
docker compose --profile live up -d
```

**Before any deployment, run through the full checklist in [docs/deploy-sop.md](docs/deploy-sop.md).**

All log/CSV paths use `logs/` prefix and `HEALTHCHECK` uses module syntax — both verified 2026-03-09.

## Git Hygiene

Follow these practices for all changes in this repo:

- **Branch per feature/fix**: Never commit directly to `main`. Create a branch first:
  ```bash
  git checkout -b feat/short-description   # new feature
  git checkout -b fix/short-description    # bug fix
  git checkout -b chore/short-description  # config, deps, docs
  ```
- **Atomic commits**: Each commit should represent one logical change. Do not bundle unrelated edits.
- **Commit message format** (Conventional Commits):
  ```
  <type>(<scope>): <short summary>

  # Types: feat, fix, chore, docs, refactor, test
  # Examples:
  feat(config): add RUNE/USDT to all profiles
  fix(strategy): correct obv_breakout stop_loss_pct
  chore(config): bump max_positions to 5
  docs(claude): update active pair list
  ```
- **Never force-push `main`**. Rebase or merge feature branches before merging.
- **Keep `main` green**: Only merge branches that run without errors (`python3 run_bot.py --profile local_paper` starts cleanly).
- **`.env` and state files are never committed**: `*.json.enc`, `paper_state.json`, `*_state.json`, `*.csv`, `.env` must stay in `.gitignore`.
- **Review before pushing**: Run `git diff --stat` and `git log --oneline -5` before pushing to confirm scope.

## MCP Servers Available

These MCP servers are configured and should be used proactively when relevant.

### General Utilities (stdio, auto-spawned)
- **filesystem** (`filesystem`) — Local filesystem read/write via Node.js server at `/home/dribble0335/filesystem-mcp-server/`.
- **fetch** (`fetch`) — HTTP fetch tool for retrieving web content. Via `npx mcp-fetch-server`.
- **sequential-thinking** (`sequential-thinking`) — Step-by-step reasoning scaffolding. Via `npx @modelcontextprotocol/server-sequential-thinking`.
- **context7** (`context7`) — Up-to-date library documentation lookup. Via `npx @upstash/context7-mcp`.
- **github** (`github`) — GitHub API: issues, PRs, repos, code search. Via `npx @modelcontextprotocol/server-github`.
- **git** (`git`) — Git operations (log, diff, commit, etc). Via `npx @cyanheads/git-mcp-server`.
- **firecrawl** (`firecrawl`) — Web scraping and crawling. Via `npx firecrawl-mcp`. Requires `FIRECRAWL_API_KEY`.

### Remote / Always-On (no pre-start needed)
- **deepwiki** (`deepwiki`) — Deep Wikipedia search and knowledge lookup. SSE endpoint: `https://mcp.deepwiki.com/mcp`.
- **composer** (`composer`) — Automated investment strategy research and execution on Composer.trade. HTTP endpoint: `https://ai.composer.trade/mcp`. Requires Composer account (OAuth in browser).

### HTTP servers (must be running — start via systemd)
- **graphiti** (`graphiti`) — Local knowledge graph memory (Neo4j + Ollama). Persists entities and facts across sessions. Endpoint: `http://localhost:8000/mcp/`. Start: `systemctl --user start graphiti-mcp`. Config: `/home/dribble0335/graphiti/mcp_server/config/config-local-ollama.yaml`.
- **fmp-imbenrabi** (`fmp-imbenrabi`) — Financial Modeling Prep, 253+ tools (stocks, earnings, macro, technicals, insider data). Endpoint: `http://localhost:8082/mcp`. Start: `systemctl --user start fmp-imbenrabi`. Most comprehensive FMP server.

### Trading & Market Data (stdio, auto-spawned)
- **alpaca** (`alpaca`) — Paper trading execution, account info, order management, portfolio queries. Via `uvx alpaca-mcp-server`. Pointed at paper-trading endpoint (safe, no real money).
- **quantconnect** (`quantconnect`) — Backtesting, strategy research, historical data, algorithm deployment. Via `uvx quantconnect-mcp`. Use when running or evaluating backtests.
- **alphavantage** (`alphavantage`) — Market data: OHLCV, fundamentals, earnings, economic indicators, forex, crypto. Via `uvx alphavantage-mcp`. Free tier: 500 req/day.
- **fmp-houtini** (`fmp-houtini`) — FMP financial data, focused tool set. Via `npx @houtini/fmp-mcp`. Uses `FMP_API_KEY`.
- **fmp-vipbat** (`fmp-vipbat`) — Lightweight Python FMP stdio server. Binary: `/home/dribble0335/vipbat-fmp-mcp/.venv/bin/python`. Uses `FMP_API_KEY`.
- **finance-tools** (`finance-tools`) — Yahoo Finance, FRED macro data, technical analysis (TA-Lib). Binary: `/home/dribble0335/finance-tools-mcp-env/bin/finance-tools-mcp`. No API key required for basic use.

## Key Design Decisions

- The incomplete last candle is always dropped before signal computation to avoid acting on partial data (`drop_incomplete_last_candle()`).
- The regime filter (`compute_daily_regime`) gates entries: entries only occur in bull or neutral regime unless `risk_off_exits` is enabled, which also force-exits on regime flip to bear.
- API error circuit breaker: if more than `api_error_threshold` errors occur within `api_error_window_sec`, the bot halts for `api_kill_cooldown_sec`.
- State files use atomic write (write to `.tmp` then `os.replace`) to prevent corruption.
- `dry_run: true` in config prevents actual order submission even for exchange profiles.
