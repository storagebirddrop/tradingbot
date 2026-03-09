# Phemex Momentum Trading Bot

> **Risk Disclaimer**: Educational trading tool. You are solely responsible for all trading decisions, losses, and regulatory compliance. Cryptocurrency markets are highly volatile.

> **Support**: ⚡ stupiddrone987@minibits.cash | [Phemex Referral](https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral)

---

## Architecture

The bot is a polling loop that fetches OHLCV candles, computes indicators, generates signals, and submits orders via a broker abstraction.

| File | Role |
|------|------|
| [src/run_bot.py](src/run_bot.py) | Entry point — loads profile, validates config, starts loop |
| [src/runner.py](src/runner.py) | `run_loop()` — polls candles, calls strategy, manages positions |
| [src/strategy.py](src/strategy.py) | Pure indicator + signal functions (no side effects) |
| [src/brokers.py](src/brokers.py) | `PaperBroker` / `ExchangeBroker` — unified order interface |
| [config.json](config.json) | All trading profiles and strategy parameters |

---

## Strategies

Three strategies are implemented, selected per-profile or per-symbol via `symbol_strategy` in config:

### `obv_breakout` (default)
OBV accumulation + volume breakout, trend-following.
Active pairs: ETH, ADA. SL 4%, TP 10%, max 30 candles.

### `rsi_momentum_pullback`
RSI pullback in SMA200 uptrend. 2-of-3 momentum scoring (MACDh, ImpulseMACD, StochRSI).
Bypasses regime filter (`ignore_regime_filter: true`).
Active pairs: SOL, TRX, LTC, BAT, RUNE, NEAR.

Per-symbol OOS Sharpe (purged CV, 5 folds):

| Symbol | OOS Sharpe |
|--------|-----------|
| RUNE | 1.085 |
| BAT | 0.934 |
| SOL | 0.733 |
| TRX | 0.691 |
| LTC | 0.299 |

### `vwap_band_bounce`
Mean reversion at VWAP lower band (−2σ). Active pair: VTHO.
SL 3.5%, TP 6%, max 12 candles.

---

## Profiles

| Profile | Mode | API Keys | Description |
|---------|------|----------|-------------|
| `local_paper` | Paper | No | Strategy testing with live market data |
| `phemex_testnet` | Exchange | Yes | Testnet with simulated funds |
| `phemex_live` | Exchange | Yes | Production (`dry_run: true` by default) |

Exchange profiles require `BOT_ENCRYPTION_KEY` in `.env` for state file encryption.

---

## Deployment

### Option A — Docker (Dockge or CLI)

The image is built and pushed to `ghcr.io` automatically on every push to `main` via GitHub Actions.
The host needs only `docker-compose.yml`, `.env`, and `config.json` — no source code.

**1. Create the directory structure on the host:**

```bash
mkdir -p tradingbot/{state,data,logs}
cd tradingbot
```

The expected layout:
```
tradingbot/
├── docker-compose.yml   # from the repo
├── config.json          # from the repo
├── .env                 # your secrets (never committed)
├── state/               # encrypted position/runtime state (written by bot)
├── data/                # optional: OHLCV CSVs for research scripts
└── logs/                # bot log files (written by bot)
```

**2. Set directory permissions:**

The container runs as your host user (uid/gid injected via `UID`/`GID` env vars, defaulting to 1000).
Export them before running so Docker Compose picks them up:

```bash
export UID GID
chmod 755 state logs
```

> On most Linux systems `UID` is already exported. If you see permission errors, verify with `id -u`.

**3. Create `.env`:**

```bash
# Generate an encryption key
python3 -c "import base64, os; print('BOT_ENCRYPTION_KEY=' + base64.urlsafe_b64encode(os.urandom(32)).decode())"

cat > .env <<'EOF'
# Image reference (must be lowercase)
GITHUB_REPOSITORY=storagebirddrop/tradingbot

# Encryption key — required for all profiles
BOT_ENCRYPTION_KEY=<paste generated key>

# Exchange API keys — required for testnet/live profiles
PHEMEX_API_KEY=
PHEMEX_API_SECRET=

# Safety interlocks — must be set to YES to enable real trading
ENABLE_TESTNET_TRADING=NO
ENABLE_LIVE_TRADING=NO
EOF
```

**4. Download `docker-compose.yml` and `config.json` from the repo:**

```bash
curl -fsSL https://raw.githubusercontent.com/storagebirddrop/tradingbot/main/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/storagebirddrop/tradingbot/main/config.json -o config.json
```

**5. Pull the image and start:**

```bash
export UID GID
docker compose pull

# Choose one profile:
docker compose --profile paper up -d     # paper trading (no API keys needed)
docker compose --profile testnet up -d   # testnet
docker compose --profile live up -d      # live
```

> For local testing without a pushed image, build locally and use the `IMAGE` override:
> ```bash
> docker build -t phemex-bot:local .
> export UID GID && IMAGE=phemex-bot:local docker compose --profile paper up
> ```

**Updating (Dockge or CLI):**

```bash
docker compose pull && docker compose up -d
```

The bot handles `SIGTERM` gracefully: it completes the current polling iteration (≤ 30 s),
persists all state to `./state/`, then exits. Active positions survive restarts.

---

### Option B — VM / LXC (bare-metal)

```bash
# Clone and set up
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Create runtime directories
mkdir -p state

# Configure environment
cp .env.template .env   # fill in BOT_ENCRYPTION_KEY
                        # set BOT_ENV=development to skip key requirement for local testing

# Run
python3 -m src.run_bot --profile local_paper      # paper trading
python3 -m src.run_bot --profile phemex_testnet   # testnet
python3 -m src.run_bot --profile phemex_live      # live
```

**Updating:**

```bash
git pull
pip install -r requirements.txt
# Restart the bot process
```

---

## Configuration

### Per-profile requirements

| | `local_paper` | `phemex_testnet` | `phemex_live` |
|---|---|---|---|
| `BOT_ENCRYPTION_KEY` | optional† | required | required |
| `PHEMEX_API_KEY` / `PHEMEX_API_SECRET` | — | required | required |
| `ENABLE_TESTNET_TRADING=YES` | — | required | — |
| `ENABLE_LIVE_TRADING=YES` | — | — | required |
| `GITHUB_REPOSITORY` | Docker only | Docker only | Docker only |

† Set `BOT_ENV=development` in `.env` to skip the key requirement for local testing only.

---

### `local_paper` — paper trading

No API keys needed. Uses live Phemex market data but never submits real orders.

**Key config.json settings:**

| Key | Default | Notes |
|-----|---------|-------|
| `starting_cash` | `50.0` | Simulated USDT balance |
| `symbols` | 9 pairs | Edit to trade a subset |
| `max_positions` | `2` | Max concurrent open trades |
| `risk_per_trade` | `0.01` | 1% of portfolio per trade |
| `stop_pct` | `0.02` | 2% stop-loss |
| `daily_loss_limit_pct` | `3.0` | Halt entries if down 3% on the day |
| `poll_seconds` | `20` | Loop cadence |
| `dry_run` | `true` | Always true for paper |

---

### `phemex_testnet` — exchange testnet

Connects to Phemex testnet. Submits real API calls with simulated testnet funds.

**Required `.env` additions:**
```bash
PHEMEX_API_KEY=<testnet key>
PHEMEX_API_SECRET=<testnet secret>
BOT_ENCRYPTION_KEY=<generated key>
ENABLE_TESTNET_TRADING=YES
```

> Get testnet API keys at [testnet.phemex.com](https://testnet.phemex.com) → API Management.

**Key config.json settings:**

| Key | Default | Notes |
|-----|---------|-------|
| `dry_run` | `true` | **Set to `false` to actually submit orders to testnet** |
| `hard_stops` | `true` | Places exchange-side stop-market orders |
| `max_positions` | `5` | Higher than live — testnet is for validation |
| `risk_per_trade` | `0.03` | 3% of portfolio per trade |
| `funding_filter.enabled` | `true` | Blocks longs when funding rate is elevated |
| `daily_loss_limit_pct` | `3.0` | Kill switch threshold |

---

### `phemex_live` — live trading

Connects to Phemex mainnet. Real money.

**Required `.env` additions:**
```bash
PHEMEX_API_KEY=<live key>
PHEMEX_API_SECRET=<live secret>
BOT_ENCRYPTION_KEY=<generated key>
ENABLE_LIVE_TRADING=YES
```

> ⚠️ The bot ships with `"dry_run": true` in the live profile. This means it connects to the live exchange, fetches real prices, and logs signals — but does **not** submit any orders. Set `"dry_run": false` in `config.json` only when you are ready to trade real funds.

**Key config.json settings:**

| Key | Default | Notes |
|-----|---------|-------|
| `dry_run` | `true` | **Must change to `false` to place real orders** |
| `hard_stops` | `true` | Places exchange-side stop-market orders on Phemex |
| `max_positions` | `2` | Conservative default — adjust to your risk tolerance |
| `max_position_pct` | `0.15` | Max 15% of portfolio in a single position |
| `max_total_exposure_pct` | `0.25` | Max 25% of portfolio across all open positions |
| `risk_per_trade` | `0.01` | 1% of portfolio per trade |
| `stop_pct` | `0.02` | 2% stop-loss |
| `daily_loss_limit_pct` | `3.0` | Kill switch — entries halt, exits still fire |
| `funding_filter.enabled` | `true` | Blocks longs when funding rate > 0.05% |
| `risk_off_exits` | `true` | Force-exits all positions if regime flips to bear |

**Before going live — checklist:**

- [ ] Tested strategy on `local_paper` for at least one full week
- [ ] Validated order flow end-to-end on `phemex_testnet` with `dry_run: false`
- [ ] `BOT_ENCRYPTION_KEY` is backed up securely (losing it makes state files unreadable)
- [ ] `max_positions`, `risk_per_trade`, and `max_total_exposure_pct` sized to your actual balance
- [ ] Set `dry_run: false` in `config.json` — the only change needed to go from simulation to live

---

## Environment Variables (`.env`)

```bash
# Required for exchange profiles
BOT_ENCRYPTION_KEY=<32-byte base64 key>
PHEMEX_API_KEY=<key>
PHEMEX_API_SECRET=<secret>

# Safety interlocks — must be YES to enable real trading
ENABLE_TESTNET_TRADING=NO
ENABLE_LIVE_TRADING=NO

# Docker only — image reference (must be lowercase)
GITHUB_REPOSITORY=storagebirddrop/tradingbot

# Local dev only — skips BOT_ENCRYPTION_KEY requirement
# BOT_ENV=development
```

Generate an encryption key:
```bash
python3 -c "import base64, os; print('BOT_ENCRYPTION_KEY=' + base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

---

## Monitoring

```bash
# Health check
python3 -m src.healthcheck --profile local_paper

# Equity curve
python3 scripts/equity_report.py --equity-log paper_equity.csv --starting 50
python3 scripts/plot_equity.py

# Trade summary
python3 scripts/trades_report.py --trades-log paper_trades.csv

# Reconcile fills vs orders
python3 scripts/reconcile.py

# Live log
tail -f local_paper.log
grep -E "FUNDING_RATE|SIGNAL_FILTERED|HMM_LABELS|ENTRY|EXIT" local_paper.log
```

For Docker, prefix with `docker compose exec bot-paper`:
```bash
docker compose exec bot-paper python3 -m src.healthcheck --profile local_paper
docker compose logs -f bot-paper
```

---

## Risk Controls

- **ATR sizing**: `use_atr_sizing: true` — tightens stops in volatile conditions
- **HMM regime filter**: `compute_daily_regime()` gates entries in bear regime; `risk_off_exits` force-exits on flip
- **Daily loss limit**: halts entries when daily drawdown exceeds `daily_loss_limit_pct`
- **API circuit breaker**: halts loop after `api_error_threshold` errors in `api_error_window_sec`
- **Vol regime params**: scales stop multiplier and position size by volatility tier (high/normal/low)
- **Funding filter**: blocks longs when funding > `block_long_above` (exchange profiles)

---

## Research Scripts

Located in [research/](research/):

| Script | Purpose |
|--------|---------|
| `fetch_data.py` | Download OHLCV history from Binance/CryptoCompare |
| `backtest_engine.py` | `run_backtest()`, `walk_forward()`, `purged_cv()` |
| `optimize_params.py` | Per-symbol grid search over purged CV Sharpe |
| `regime_strategy_analysis.py` | HMM regime-switching backtest/WFO |
| `train_regime_hmm.py` | Train 3-state GaussianHMM on daily OHLCV |
| `train_signal_filter.py` | Train LightGBM signal quality classifier |

```bash
# Fetch data
python3 research/fetch_data.py --symbol ETH --since 2020-01-01

# Optimize RSI pullback params
python3 research/optimize_params.py --symbols ETH SOL --strategy rsi_momentum_pullback --out-json

# Train / retrain HMM regime model
python3 research/train_regime_hmm.py --symbol ETH --data-dir data/ --plot

# Regime strategy analysis (WFO)
python3 research/regime_strategy_analysis.py \
  --symbols ETH SOL TRX ADA LTC BAT RUNE VTHO \
  --hmm models/regime_hmm.pkl \
  --hmm-states models/regime_hmm_states.json
```

---

## Security

- State files (`state/*_state.json`) are Fernet-encrypted at rest; written atomically via `.tmp` + `os.replace`
- `.env`, `*.json.enc`, state files, and CSVs are gitignored
- `BOT_ENV=development` bypasses key requirement for local dev only — never use in production

---

## License

MIT — see LICENSE. Not financial advice. Past performance does not guarantee future results.
