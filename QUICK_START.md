# ⚡ Phemex Trading Bot - Quick Start Guide

## 🚀 One-Command Setup

### Option 1: Fresh VM/LXC Container (Recommended)

```bash
# Clone and install
git clone <repository-url>
cd tradingbot
chmod +x install.sh
./install.sh

# Configure environment
cp .env.template .env
nano .env

# Run paper trading
./run_bot.sh local_paper
```

### Option 2: Docker (Easiest)

```bash
# Clone and setup
git clone <repository-url>
cd tradingbot

# Configure environment
cp .env.template .env
nano .env

# Start paper trading
docker-compose --profile paper up -d

# View logs
docker-compose logs -f bot-paper
```

## 📋 What You Need

### For Paper Trading
- ✅ Just the bot code
- ✅ Internet connection

### For Exchange Trading
- ✅ Phemex API keys
- ✅ Environment variables set

## 🎯 Choose Your Profile

### 1. Paper Trading (Start Here)
```bash
./run_bot.sh local_paper
```
- No API keys needed
- Live market data
- Simulated trades
- Zero risk

### 2. Testnet Trading
```bash
# Create .env file with testnet credentials
cp .env.template .env
# Edit .env and add:
# PHEMEX_API_KEY=your_testnet_key
# PHEMEX_API_SECRET=your_testnet_secret
# ENABLE_TESTNET_TRADING=YES

./run_bot.sh phemex_testnet
```
- Testnet API keys required
- Real exchange simulation
- Test stop orders

### 3. Live Trading
```bash
# Add live credentials to .env file
# Edit .env and add:
# PHEMEX_API_KEY=your_live_key
# PHEMEX_API_SECRET=your_live_secret
# ENABLE_LIVE_TRADING=YES

./run_bot.sh phemex_live
```
- Live API keys required
- Real money trading
- Full security features

## 📊 Monitor Your Bot

### Check Status
```bash
./status.sh                    # Quick status overview
tail -f bot.log                # Real-time logs
```

### Health Check
```bash
./health_check.sh local_paper  # Verify bot health
```

### View Performance
```bash
python3 equity_report.py --equity-log paper_equity.csv --starting 50
python3 trades_report.py --trades-log paper_trades.csv
```

## 🔧 Common Commands

```bash
# Stop the bot
Ctrl+C  # or kill the process

# Restart with different profile
./run_bot.sh phemex_testnet

# Check what's running
./status.sh

# Fix issues
./health_check.sh [profile]
```

## 🚨 Important Safety Rules

1. **ALWAYS start with paper trading**
2. **NEVER use live API keys in paper trading**
3. **ALWAYS validate configuration first**
4. **MONITOR logs regularly**
5. **BACKUP your encryption key**

## 📱 What to Expect

### First Run (Paper Trading)
```
[INFO] Starting bot loop with 5 symbols
[INFO] Loaded runtime state from paper_runtime_state.json
[INFO] Current equity: 50.00 USDT
```

### Files Created
- `bot.log` - Activity logs
- `paper_equity.csv` - Equity tracking
- `paper_trades.csv` - Trade records
- `paper_state.json.enc` - Encrypted state

### Normal Operation
- Bot polls every 20 seconds
- No trades initially (normal)
- Logs show market analysis
- Equity snapshots saved regularly

## 🆘 Need Help?

### Quick Fixes
```bash
# Permission issues
chmod +x *.sh

# Dependency issues
./install.sh  # Reinstall

# Configuration issues
./health_check.sh local_paper  # Validates configuration
```

### Check Logs
```bash
# Recent errors
grep -i error bot.log | tail -10

# API issues
grep -i api bot.log | tail -10

# Security events
grep -i security bot.log | tail -10
```

### Still Stuck?
1. Check `DEPLOYMENT.md` for detailed setup
2. Review `SECURITY_IMPROVEMENTS.md` for security info
3. Run `./health_check.sh [profile]` for diagnostics

---

## 🎉 You're Ready!

**Paper Trading**: `./run_bot.sh local_paper`  
**Testnet Trading**: `./run_bot.sh phemex_testnet`  
**Live Trading**: `./run_bot.sh phemex_live`  

Start with paper trading, verify everything works, then move to testnet before considering live trading.

**Happy Trading! 🚀**
