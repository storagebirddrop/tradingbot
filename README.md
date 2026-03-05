# Phemex Spot Momentum Bot (4H) — Production-Ready Trading System

> **Disclaimer**: This is educational tooling. You are responsible for exchange rules, taxes, compliance, and risk. Spot markets can move fast; losses are possible.

> **Security Notice**: This version includes enterprise-grade security features including data encryption, API validation, and comprehensive audit logging.

**🔑 API Keys Summary:**
- **Paper Trading**: ❌ No API keys needed - works immediately
- **Testnet Trading**: ✅ API keys required (see section B5)
- **Live Trading**: ✅ API keys required (see section B5)

**Profiles supported (same codebase):**
- `local_paper` — local paper trading (live market data, simulated fills)
- `phemex_testnet` — exchange-side simulated trading (Phemex testnet)
- `phemex_live` — live trading (Phemex spot)

**🔒 Security Features (v1.1.0+):**
- ✅ **State File Encryption** - Sensitive trading data encrypted at rest
- ✅ **API Credential Validation** - Strong password requirements for API keys
- ✅ **Configuration Validation** - Prevents invalid parameters
- ✅ **Structured Logging** - Comprehensive audit trail to `bot.log`
- ✅ **Error Recovery** - Graceful handling of failures with detailed context

**Phemex referral link (optional):** https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral

---

## 🚀 Quick Start (3 Options)

### Option 1: Automated Installation (Recommended for VM/LXC)
```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
chmod +x install.sh
./install.sh

# PAPER TRADING (No API keys needed)
./run_bot.sh local_paper

# EXCHANGE TRADING (API keys required - see section B5)
# ./run_bot.sh phemex_testnet
# ./run_bot.sh phemex_live
```

### Option 2: Docker (Easiest)
```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
cp .env.template .env
# Add API keys to .env for exchange profiles (paper trading needs none)
docker-compose --profile paper up -d
docker-compose logs -f bot-paper
```

### Option 3: Manual Setup
```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# PAPER TRADING (works immediately)
python3 run_bot.py --profile local_paper

# EXCHANGE TRADING (requires API keys - see section B5)
# export PHEMEX_API_KEY="your_key"
# export PHEMEX_API_SECRET="your_secret"
# python3 run_bot.py --profile phemex_testnet
```

**📋 Profile Summary:**
- `local_paper` - Paper trading, **no API keys required**
- `phemex_testnet` - Testnet trading, **API keys required**
- `phemex_live` - Live trading, **API keys required**

**🔑 For API key setup, see section B5: "API Keys Setup for VM/LXC"**

---

## A) Quick commands (after installation)

### A1) Run paper trading (NEW: Use helper scripts)
```bash
# Recommended: Use helper script with validation
./run_bot.sh local_paper

# Or direct Python execution
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

### A3) Bot status and monitoring (NEW)
```bash
./status.sh                    # Quick status overview
./health_check.sh local_paper  # Health verification
tail -f bot.log                # Real-time logs
```

### A4) Check current settings (paper profile)
```bash
python3 -c "import json;print(json.dumps(json.load(open('config.json'))['profiles']['local_paper'], indent=2))"
```

If you have `jq` installed:
```bash
jq '.profiles.local_paper | {symbols, signal_timeframe, regime_timeframe, risk_per_trade, stop_pct, trail_pct, max_positions, max_position_pct, max_total_exposure_pct, daily_loss_limit_pct, api_error_threshold, api_error_window_sec, api_kill_cooldown_sec}' config.json
```

### A5) Health check (any profile)
```bash
python3 healthcheck.py --profile local_paper
python3 healthcheck.py --profile phemex_testnet
python3 healthcheck.py --profile phemex_live
```

### A6) View security logs (NEW)
```bash
# View real-time bot activity and security events
tail -f bot.log

# View recent security-related events
grep -i "error\|warning\|security\|api" bot.log | tail -20
```

### A7) Configuration validation (NEW)
```bash
# Test your configuration before running
python3 -c "
import json
from run_bot import validate_config
cfg = json.load(open('config.json'))['profiles']['local_paper']
validate_config(cfg)
print('✅ Configuration is valid')
"
```

---

## B) Setup & run instructions

### B1) Automated Installation (Recommended)
**For fresh VM/LXC containers or new systems:**

```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
chmod +x install.sh
./install.sh
```

The script will:
- ✅ Detect your OS (Ubuntu, Debian, CentOS, Alpine)
- ✅ Install system dependencies automatically
- ✅ Create Python virtual environment
- ✅ Install required Python packages
- ✅ Create helper scripts (`run_bot.sh`, `health_check.sh`, `status.sh`)
- ✅ Verify installation and dependencies

**After installation:**
```bash
# Configure environment (for exchange profiles)
cp .env.template .env
nano .env

# Run your chosen profile
./run_bot.sh local_paper      # Paper trading
./run_bot.sh phemex_testnet   # Testnet trading
./run_bot.sh phemex_live       # Live trading
```

### B2) Docker Installation (Easiest)
**For containerized deployment:**

```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
cp .env.template .env
nano .env  # Add your API keys for exchange profiles

# Start paper trading
docker-compose --profile paper up -d

# Monitor logs
docker-compose logs -f bot-paper
```

### B3) Manual Setup (Advanced)
**If you prefer manual setup or need custom configuration:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install ccxt pandas pandas_ta matplotlib cryptography
```

### B4) Security setup (NEW)
```bash
# RECOMMENDED: Set custom encryption key for state files
export BOT_ENCRYPTION_KEY="$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"

# Verify encryption setup
python3 -c "
from brokers import _get_encryption_key
print('✅ Encryption key generated successfully')
print(f'Key length: {len(_get_encryption_key())} bytes')
"
```

### B5) API Keys Setup for VM/LXC (IMPORTANT)

**For Paper Trading (No API Keys Needed):**
```bash
./run_bot.sh local_paper
# Paper trading works immediately - no API keys required!
```

**For Testnet/Live Trading (API Keys Required):**

#### Step 1: Get API Keys from Phemex
1. Login to Phemex testnet/live
2. Go to API Management → Create API Key
3. Set permissions: Spot Trading, Read Balances, Read Trades
4. Copy API Key and Secret

#### Step 2: Configure Environment Variables

**Option A: Environment File (Recommended)**
```bash
# Create environment file
cp .env.template .env

# Edit the file
nano .env
```

Add your keys to `.env`:
```bash
# For Testnet Trading
PHEMEX_API_KEY=your_testnet_api_key_here
PHEMEX_API_SECRET=your_testnet_api_secret_here
ENABLE_TESTNET_TRADING=YES

# For Live Trading (when ready)
# PHEMEX_API_KEY=your_live_api_key_here  
# PHEMEX_API_SECRET=your_live_api_secret_here
# ENABLE_LIVE_TRADING=YES

# RECOMMENDED: Set custom encryption key
BOT_ENCRYPTION_KEY=your_custom_encryption_key_here
```

**Option B: Export Variables (Temporary)**
```bash
# For current session only
export PHEMEX_API_KEY="your_api_key_here"
export PHEMEX_API_SECRET="your_api_secret_here"
export ENABLE_TESTNET_TRADING=YES

# Then run the bot
./run_bot.sh phemex_testnet
```

**Option C: Systemd Service (Permanent)**
```bash
# Create service with environment file
sudo nano /etc/systemd/system/phemex-bot.service
```

Add to service file:
```ini
[Service]
EnvironmentFile=/home/user/tradingbot/.env
ExecStart=/home/user/tradingbot/run_bot.sh phemex_testnet
```

#### Step 3: Verify API Key Setup
```bash
# Test API connection
python3 -c "
import os
import ccxt
key = os.environ.get('PHEMEX_API_KEY')
secret = os.environ.get('PHEMEX_API_SECRET')
if key and secret:
    ex = ccxt.phemex({'apiKey': key, 'secret': secret, 'sandbox': True})
    print('✅ API keys loaded successfully')
else:
    print('❌ API keys not found in environment')
"
```

#### Step 4: Run Exchange Profile
```bash
# Testnet (after setting testnet keys)
./run_bot.sh phemex_testnet

# Live (after setting live keys)  
./run_bot.sh phemex_live
```

**🔒 Security Notes:**
- Never commit `.env` file to git
- Set file permissions: `chmod 600 .env`
- Use IP whitelisting in Phemex settings
- API keys must be at least 32 characters (for user/API credentials, not the bot's Fernet encryption key which is generated separately)

### B6) Troubleshooting (NEW)
```bash
# Check installation
./install.sh  # Re-run if issues occur

# Verify dependencies
source .venv/bin/activate
python3 -c "import ccxt, pandas, pandas_ta, cryptography; print('✅ All dependencies ok')"

# Check bot status
./status.sh

# Run health check
./health_check.sh local_paper
```

### B7) Common operational files

#### Logs

**Universal (All Profiles)**
- `bot.log` — **NEW**: Structured logging with security events, errors, and bot activity

**Paper**
- `paper_trades.csv` — simulated trades (includes realized `pnl`)
- `paper_equity.csv` — equity snapshots (cash/equity/exposure)

**Exchange (testnet/live)**
- `*_orders.csv` — bot events + order ids + **API_KILL_ON/OFF** events
- `*_fills.csv` — fills pulled from `fetch_my_trades()` (source of truth for **realized PnL**)
- `*_equity.csv` — equity snapshots + `realized_pnl_usdt` + estimated `unrealized_pnl_est_usdt`

#### State (ENCRYPTED - NEW)
- `*_state.json.enc` — **ENCRYPTED**: open positions / stop order ids (encrypted at rest)
- `*_runtime_state.json.enc` — **ENCRYPTED**: daily kill switch + cooldowns + API kill switch timers
- `*_fills_state.json` — reconciliation cursor (`since_ms`) and avg-cost inventory state

> **🔒 Security Note**: State files are now encrypted by default. The bot automatically handles encryption/decryption. Existing unencrypted files will still work for backward compatibility.

> If you delete state files, you reset the bot's memory. Do that **only** when you intentionally want to start fresh **and** you are flat / have no open orders.

---

## 📚 Additional Documentation

- **DEPLOYMENT.md** - Comprehensive deployment guide with Docker, VM/LXC setup
- **QUICK_START.md** - One-page quick start guide
- **SECURITY_IMPROVEMENTS.md** - Detailed security features and implementation guide
- **bot.log** - Real-time security events and operational logs
- **healthcheck.py** - Comprehensive system health monitoring

---

## C) Comprehensive deployment & user guide by profile

## Profile 1 — `local_paper`

### What it is
Runs the strategy on **live market data**, but **never sends orders**. It simulates fills/fees/slippage locally.

### How to run
```bash
# Recommended: Use helper script with validation
./run_bot.sh local_paper

# Or direct Python execution
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

### Bot monitoring (NEW)
```bash
./status.sh                    # Quick status overview
./health_check.sh local_paper  # Health verification
tail -f bot.log                # Real-time logs
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

**🔒 API Security Requirements (NEW):**
- API keys must be at least 32 characters long (for user/API credentials, not the bot's Fernet encryption key which is generated separately)
- Keys cannot consist of repeated characters (e.g., "aaaaaaaa...")
- Strong, randomly generated keys are recommended
- Bot will validate key strength on startup and reject weak credentials

### Dry-run first (recommended)
`dry_run: true` means **no orders placed**, but the bot still runs logic/logging:
```bash
./run_bot.sh phemex_testnet
```

### Enable real testnet orders
1) Set this env var:
```bash
export ENABLE_TESTNET_TRADING=YES
```
2) Edit `config.json` → set `phemex_testnet.dry_run` to `false`
3) Run:
```bash
./run_bot.sh phemex_testnet
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

**🔒 LIVE TRADING SECURITY (NEW):**
- **MANDATORY**: Use strong, randomly generated API keys (minimum 32 characters)
- **MANDATORY**: Enable IP whitelisting in Phemex settings for your API keys
- **RECOMMENDED**: Set custom encryption key for state files: `export BOT_ENCRYPTION_KEY="your_key_here"`
- **RECOMMENDED**: Monitor `bot.log` for security events and API validation
- **WARNING**: Bot will reject weak API keys and refuse to start

### Dry-run first (mandatory)
Keep `phemex_live.dry_run = true` first:
```bash
./run_bot.sh phemex_live
```

### Enable live orders
1) Set:
```bash
export ENABLE_LIVE_TRADING=YES
```
2) Set `phemex_live.dry_run = false`
3) Run:
```bash
./run_bot.sh phemex_live
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
BOT_ENCRYPTION_KEY=...  # RECOMMENDED: Custom encryption key
```

**🔒 Security Best Practices:**
- Set file permissions: `chmod 600 ~/bot/.env`
- Use strong API keys (minimum 32 characters)
- RECOMMENDED: Set custom encryption key for additional security
- Monitor `~/bot/bot.log` for security events

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

# Or use helper script (NEW):
# ExecStart=/home/botuser/bot/run_bot.sh phemex_testnet
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

### E1) Security & Safety Rules (NEW)
- **ALWAYS** validate configuration before running: see section A7
- **MANDATORY**: Use strong API keys (minimum 32 characters, no repeated patterns)
- **RECOMMENDED**: Set custom encryption key for state files
- **MONITOR**: Check `bot.log` regularly for security events and errors
- **BACKUP**: Keep secure backups of your encryption key and configuration

### E2) Trading Operations Rules
- Always run **DRY_RUN** first after any code/config change.
- For live:
  - start with tiny USDT
  - confirm `STOP_CONFIRMED` rows appear
  - confirm `live_fills.csv` is being populated
- If you see frequent `API_KILL_ON`:
  - raise `api_error_threshold` a bit (e.g. 18–25) or increase `api_error_window_sec`
- Don't touch parameters daily. Let the bot behave. Review weekly.

### E3) Monitoring & Maintenance (NEW)
- **Daily**: Check `bot.log` for errors and security events
- **Weekly**: Review equity curves and drawdowns
- **Monthly**: Verify API key security and rotate if needed
- **Issues**: Check healthcheck output: `python3 healthcheck.py --profile <profile>`

---

## Referral link
https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral

---

## 📚 Additional Documentation

- **SECURITY_IMPROVEMENTS.md** - Detailed security features and implementation guide
- **bot.log** - Real-time security events and operational logs
- **healthcheck.py** - Comprehensive system health monitoring

---

## 🏷️ Version Information

**Current Version**: v1.1.0-security  
**Release Date**: 2026-03-05  
**Status**: Production Ready ✅  

### Key Changes in v1.1.0
- 🔒 State file encryption (AES-128)
- 🛡️ API credential validation
- 📝 Structured logging system
- ⚙️ Configuration validation
- 🔄 Enhanced error recovery
- 📊 Improved monitoring capabilities
- 🚀 Automated installation script
- 🐳 Docker deployment support
- 📋 Helper scripts for easy operation

---

## 🎯 Deployment Summary

### **For Quick Start:**
```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
./install.sh
./run_bot.sh local_paper
```

### **For Docker:**
```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
docker-compose --profile paper up -d
```

### **For Production:**
1. Review `DEPLOYMENT.md` for comprehensive setup
2. Use `QUICK_START.md` for one-page reference
3. Monitor with `./status.sh` and `./health_check.sh`
4. Check `SECURITY_IMPROVEMENTS.md` for security features

**All deployment methods include:**
- ✅ Automatic dependency installation
- ✅ Security configuration
- ✅ Environment validation
- ✅ Helper scripts for operation
- ✅ Comprehensive logging
- ✅ Health monitoring

---
