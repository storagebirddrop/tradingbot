# Phemex Momentum Trading Bot

> **Risk Disclaimer**: Educational trading tool. You are solely responsible for all trading decisions, losses, and regulatory compliance. Cryptocurrency markets are highly volatile.

> **Support**: ⚡ stupiddrone987@minibits.cash | [Phemex Referral](https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral)

---

## Architecture

The bot is a polling loop that fetches OHLCV candles, computes indicators, generates signals, and submits orders via a broker abstraction.

| File | Role |
|------|------|
| [run_bot.py](run_bot.py) | Entry point — loads profile, validates config, starts loop |
| [runner.py](runner.py) | `run_loop()` — polls candles, calls strategy, manages positions |
| [src/strategy.py](src/strategy.py) | Pure indicator + signal functions (no side effects) |
| [brokers.py](brokers.py) | `PaperBroker` / `ExchangeBroker` — unified order interface |
| [config.json](config.json) | All trading profiles and strategy parameters |

---

## Strategies

Three strategies are implemented, selected per-profile or per-symbol:

### `obv_breakout` (default)
OBV accumulation + volume breakout, trend-following.
Active pairs: ETH, SOL, TRX, ADA, BAT, LTC, RUNE.
SL 4%, TP 10%, max 30 candles.

### `vwap_band_bounce`
Mean reversion at VWAP lower band (−2σ). Active pair: VTHO.
SL 3.5%, TP 6%, max 12 candles.

### `rsi_momentum_pullback`
RSI pullback in SMA200 uptrend. 2-of-3 momentum scoring (MACDh, ImpulseMACD, StochRSI).
Bypasses regime filter (`ignore_regime_filter: true`).
Per-symbol optimized OOS Sharpe (purged CV, 5 folds):

| Symbol | OOS Sharpe |
|--------|-----------|
| RUNE | 1.085 |
| BAT | 0.934 |
| SOL | 0.733 |
| TRX | 0.691 |
| LTC | 0.299 |

Per-symbol strategy routing: `"symbol_strategy": {"VTHO/USDT": "vwap_band_bounce"}` in config.

---

## Profiles

| Profile | Mode | API Keys | Description |
|---------|------|----------|-------------|
| `local_paper` | Paper | No | Strategy testing with live market data |
| `phemex_testnet` | Exchange | Yes | Testnet with simulated funds |
| `phemex_live` | Exchange | Yes | Production (dry_run: true by default) |

**Production and staging profiles require `BOT_ENCRYPTION_KEY` in `.env`** for state file encryption. In development mode (`BOT_ENV=development`), the key requirement is bypassed for local testing.

---

## Quick Start

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env   # Add BOT_ENCRYPTION_KEY (skip if BOT_ENV=development)

# Paper trading (no API keys needed)
python3 run_bot.py --profile local_paper

# Or via shell wrapper
./run_bot.sh local_paper
```

### Environment Variables (`.env`)

```bash
BOT_ENCRYPTION_KEY=<32-byte base64 key>   # required for production/staging
PHEMEX_API_KEY=<key>                       # required — exchange profiles
PHEMEX_API_SECRET=<secret>                 # required — exchange profiles
BOT_ENV=development                        # skip key requirement in dev/test
```

Generate an encryption key:
```bash
python3 -c "import base64, os; print('BOT_ENCRYPTION_KEY=' + base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

---

## Monitoring

```bash
# Health check
python3 healthcheck.py

# Equity curve
python3 equity_report.py --equity-log paper_equity.csv --starting 50
python3 plot_equity.py

# Trade summary
python3 trades_report.py --trades-log paper_trades.csv

# Reconcile fills vs orders
python3 reconcile.py

# Live log
tail -f bot.log
grep -E "FUNDING_RATE|SIGNAL_FILTERED|ENTRY|EXIT" bot.log
```

---

## Risk Controls

- **ATR sizing**: `use_atr_sizing: true` — tightens stops in volatile conditions
- **Regime filter**: `compute_daily_regime()` gates entries in bear regime; `risk_off_exits` force-exits on flip
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

# Optimize RSI pullback params for ETH and SOL
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

- State files (`*_state.json`) are Fernet-encrypted at rest; written atomically via `.tmp` + `os.replace`
- `.env`, `*.json.enc`, state files, and CSVs are gitignored
- `BOT_ENV=development` bypasses key requirement for local dev only
- **Security Warning**: Never run with `BOT_ENV=development` in production - always set `BOT_ENCRYPTION_KEY` in production/staging environments

---

## License

MIT — see LICENSE. Not financial advice. Past performance does not guarantee future results.
