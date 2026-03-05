# Phemex Spot Momentum Bot (4H) — Deployment & User Guide

> **Disclaimer**: This repository is educational tooling. You are responsible for compliance, taxes, exchange rules, and risk.

**Profiles supported (same codebase):**
- `local_paper`: local paper trading (live market data, simulated fills)
- `phemex_testnet`: exchange-side simulated trading (Phemex testnet)
- `phemex_live`: live trading (Phemex spot)

Phemex referral link (optional): https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral

---

## Paper bot quick checks (profits + settings)

### Profit / performance
```bash
python equity_report.py --equity-log paper_equity.csv --starting 50
python trades_report.py --trades-log paper_trades.csv
python plot_equity.py --equity-log paper_equity.csv
tail -n 30 paper_equity.csv
tail -n 80 paper_trades.csv
```

### Settings inspection
```bash
python -c "import json;print(json.dumps(json.load(open('config.json'))['profiles']['local_paper'], indent=2))"
```

If you have jq:
```bash
jq '.profiles.local_paper | {{symbols, signal_timeframe, regime_timeframe, risk_per_trade, stop_pct, trail_pct, max_positions, max_position_pct, max_total_exposure_pct, daily_loss_limit_pct, api_error_threshold, api_error_window_sec, api_kill_cooldown_sec}}' config.json
```

### Healthcheck
```bash
python healthcheck.py --profile local_paper
```

---

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install ccxt pandas pandas_ta matplotlib
```

---

## Run profiles

### local_paper
```bash
python run_bot.py --profile local_paper
```

### phemex_testnet
```bash
export PHEMEX_API_KEY="TESTNET_KEY"
export PHEMEX_API_SECRET="TESTNET_SECRET"
python run_bot.py --profile phemex_testnet   # dry_run: true
```

Enable testnet trading:
```bash
export ENABLE_TESTNET_TRADING=YES
# set phemex_testnet.dry_run=false in config.json
python run_bot.py --profile phemex_testnet
```

### phemex_live
```bash
export PHEMEX_API_KEY="LIVE_KEY"
export PHEMEX_API_SECRET="LIVE_SECRET"
python run_bot.py --profile phemex_live      # dry_run: true
```

Enable live trading:
```bash
export ENABLE_LIVE_TRADING=YES
# set phemex_live.dry_run=false in config.json
python run_bot.py --profile phemex_live
```

---

## Monitoring (testnet/live)
```bash
python healthcheck.py --profile phemex_testnet
python trades_report.py --fills-log testnet_fills.csv
tail -n 80 testnet_orders.csv
```

---

## Phemex referral link
https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral
