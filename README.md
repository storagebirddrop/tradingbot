# Phemex Spot Momentum Bot (4H) — Extended Deployment & User Guide

> **Disclaimer**: This is educational tooling. You are responsible for exchange rules, taxes, compliance, and risk. Spot markets can move fast; losses are possible.

**Profiles supported (same codebase):**
- `local_paper` — local paper trading (live market data, simulated fills)
- `phemex_testnet` — exchange-side simulated trading (Phemex testnet)
- `phemex_live` — live trading (Phemex spot)

**Phemex referral link (optional):** https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral

---

## A) Quick commands (paper trading bot)

### A1) Run paper trading
```bash
python3 run_bot.py --profile local_paper
```

### A2) Check paper profits/performance
```bash
python3 equity_report.py --equity-log paper_equity.csv --starting 50
python3 trades_report.py --trades-log paper_trades.csv
python3 plot_equity.py --equity-log paper_equity.csv
tail -n 30 paper_equity.csv
tail -n 80 paper_trades.csv
```

### A3) Check current settings (paper profile)
```bash
python3 -c "import json;print(json.dumps(json.load(open('config.json'))['profiles']['local_paper'], indent=2))"
```

If you have `jq` installed:
```bash
jq '.profiles.local_paper | {symbols, signal_timeframe, regime_timeframe, risk_per_trade, stop_pct, trail_pct, max_positions, max_position_pct, max_total_exposure_pct, daily_loss_limit_pct, api_error_threshold, api_error_window_sec, api_kill_cooldown_sec}' config.json
```

### A4) Health check (any profile)
```bash
python3 healthcheck.py --profile local_paper
python3 healthcheck.py --profile phemex_testnet
python3 healthcheck.py --profile phemex_live
```

---

## B) Setup & run instructions (all profiles)

### B1) One-time setup
From inside your bot directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install ccxt pandas pandas_ta matplotlib
```

Sanity import:
```bash
python -c "import ccxt, pandas, pandas_ta; print('ok')"
```

### B2) If `python` is not found (common on VPS/Linux)

If you see:
```bash
-bash: python: command not found
```

Do this:

1) Check whether `python3` exists:
```bash
which python3
python3 --version
```

2) Create your virtual environment with `python3`:
```bash
python3 -m venv .venv
source .venv/bin/activate
python --version   # inside the venv, this should work
```

3) If `python3` is missing (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

4) Optional: make `python` point to `python3` system-wide (Ubuntu/Debian):
```bash
sudo apt install -y python-is-python3
```

### B3) Common operational files

#### Logs

**Paper**
- `paper_trades.csv` — simulated trades (includes realized `pnl`)
- `paper_equity.csv` — equity snapshots (cash/equity/exposure)

**Exchange (testnet/live)**
- `*_orders.csv` — bot events + order ids + **API_KILL_ON/OFF** events
- `*_fills.csv` — fills pulled from `fetch_my_trades()` (source of truth for **realized PnL**)
- `*_equity.csv` — equity snapshots + `realized_pnl_usdt` + estimated `unrealized_pnl_est_usdt`

#### State
- `*_state.json` — open positions / stop order ids
- `*_runtime_state.json` — daily kill switch + cooldowns + API kill switch timers
- `*_fills_state.json` — reconciliation cursor (`since_ms`) and avg-cost inventory state

> If you delete state files, you reset the bot’s memory. Do that **only** when you intentionally want to start fresh **and** you are flat / have no open orders.

---

## C) Comprehensive deployment & user guide by profile

## Profile 1 — `local_paper`

### What it is
Runs the strategy on **live market data**, but **never sends orders**. It simulates fills/fees/slippage locally.

### How to run
```bash
python3 run_bot.py --profile local_paper
```

### How to stop
- `Ctrl + C`

### How to read performance
```bash
python3 equity_report.py --equity-log paper_equity.csv --starting 50
python3 trades_report.py --trades-log paper_trades.csv
python3 plot_equity.py --equity-log paper_equity.csv
```

### What safety controls mean here
- **Daily loss kill**: stops opening new simulated positions for the rest of the UTC day.
- **API kill**: if your data calls are failing repeatedly, the bot pauses actions.
- **Cooldown**: prevents immediate re-entry after exits.

### Typical workflow
- Run for multiple weeks.
- Check:
  - time-in-market (exposure line)
  - drawdown duration
  - whether it trades too frequently in chop (cooldown helps)
- Only then move to testnet.

---

## Profile 2 — `phemex_testnet` (exchange-side simulated)

### What it is
Places **real orders on Phemex testnet**, including **exchange-native conditional stop-market orders**. This is the first environment where “hard stops” truly protect you even if your bot dies.

### Setup
Create Phemex testnet API keys (in testnet UI), then export:
```bash
export PHEMEX_API_KEY="TESTNET_KEY"
export PHEMEX_API_SECRET="TESTNET_SECRET"
```

### Dry-run first (recommended)
`dry_run: true` means **no orders placed**, but the bot still runs logic/logging:
```bash
python3 run_bot.py --profile phemex_testnet
```

### Enable real testnet orders
1) Set this env var:
```bash
export ENABLE_TESTNET_TRADING=YES
```
2) Edit `config.json` → set `phemex_testnet.dry_run` to `false`
3) Run:
```bash
python3 run_bot.py --profile phemex_testnet
```

### Confirm hard stop behavior
When an entry happens, in `testnet_orders.csv` you should see:
- `BUY`
- `STOP_CREATED`
- `STOP_CONFIRMED`

If stop confirm fails, you should see:
- `STOP_CONFIRM_FAILED_EXITING` (fail-closed behavior)

### Track profits (realized PnL from fills)
```bash
python3 equity_report.py --equity-log testnet_equity.csv --starting 50
python3 trades_report.py --fills-log testnet_fills.csv
python3 plot_equity.py --equity-log testnet_equity.csv
```

### How the API kill switch shows up
In `testnet_orders.csv` you will see:
- `API_KILL_ON` with a reason
- `API_KILL_OFF` when the cooldown ends

During API kill, **no new orders** will be sent. Your last on-exchange stop remains active.

---

## Profile 3 — `phemex_live` (real money)

### What it is
Same bot as testnet, but on live spot, with:
- hard stop-market conditional orders on exchange
- reconciliation-based realized PnL
- daily loss kill switch
- API error-rate kill switch

### Setup
Create live API keys (use least permissions needed: spot trading, read balances, read trades), then export:
```bash
export PHEMEX_API_KEY="LIVE_KEY"
export PHEMEX_API_SECRET="LIVE_SECRET"
```

### Dry-run first (mandatory)
Keep `phemex_live.dry_run = true` first:
```bash
python3 run_bot.py --profile phemex_live
```

### Enable live orders
1) Set:
```bash
export ENABLE_LIVE_TRADING=YES
```
2) Set `phemex_live.dry_run = false`
3) Run:
```bash
python3 run_bot.py --profile phemex_live
```

### Live profit tracking
```bash
python3 equity_report.py --equity-log live_equity.csv --starting 50
python3 trades_report.py --fills-log live_fills.csv
python3 plot_equity.py --equity-log live_equity.csv
```

---

## D) Deployment guide (VPS + systemd)

If you want “set-and-forget” with maximum stability, run on a VPS.

### D1) Create a service user
```bash
sudo adduser --disabled-password --gecos "" botuser
sudo su - botuser
```

### D2) Put bot code in a directory
```bash
mkdir -p ~/bot
cd ~/bot
# copy your files here
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install ccxt pandas pandas_ta matplotlib
```

### D3) Store keys securely (environment file)
Create `~/bot/.env` (permissions 600):
```bash
chmod 600 ~/bot/.env
nano ~/bot/.env
```

Example contents for testnet:
```ini
PHEMEX_API_KEY=...
PHEMEX_API_SECRET=...
ENABLE_TESTNET_TRADING=YES
```

### D4) Create a systemd service
As root:
```bash
sudo nano /etc/systemd/system/phemex-bot.service
```

Paste (edit paths/profile):
```ini
[Unit]
Description=Phemex Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/bot
EnvironmentFile=/home/botuser/bot/.env
ExecStart=/home/botuser/bot/.venv/bin/python /home/botuser/bot/run_bot.py --profile phemex_testnet
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable + start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable phemex-bot
sudo systemctl start phemex-bot
```

View logs:
```bash
sudo journalctl -u phemex-bot -f
```

Stop:
```bash
sudo systemctl stop phemex-bot
```

---

## E) Operating rules (to keep it “unemotional” and not overcomplicated)

- Always run **DRY_RUN** first after any code/config change.
- For live:
  - start with tiny USDT
  - confirm `STOP_CONFIRMED` rows appear
  - confirm `live_fills.csv` is being populated
- If you see frequent `API_KILL_ON`:
  - raise `api_error_threshold` a bit (e.g. 18–25) or increase `api_error_window_sec`
- Don’t touch parameters daily. Let the bot behave. Review weekly.

---

## Referral link
https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral
