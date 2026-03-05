# 🐳 Dockge Deployment Guide for Phemex Trading Bot

## 🚀 Quick Start with Dockge

### Prerequisites
- Dockge installed and running
- Git access to clone the repository

### Step 1: Clone Repository in Dockge

1. In Dockge, create a new stack
2. Use these settings:
   - **Stack Name**: `phemex-bot`
   - **Repository**: `git@github.com:storagebirddrop/tradingbot.git`
   - **Branch**: `main`
   - **Compose File**: `dockge-compose.yml`

### Step 2: Configure Environment Variables

Create `.env` file or set in Dockge:

```bash
# Optional: Custom encryption key
BOT_ENCRYPTION_KEY=your_custom_key_here

# For exchange profiles (when ready)
PHEMEX_API_KEY=your_api_key_here
PHEMEX_API_SECRET=your_api_secret_here
ENABLE_TESTNET_TRADING=YES
ENABLE_LIVE_TRADING=YES
```

### Step 3: Deploy Paper Trading

1. **Enable only paper trading**:
   - In Dockge, edit the stack
   - Comment out or remove testnet/live services
   - Keep only `bot-paper` and `profit-checker` services

2. **Deploy the stack**:
   - Click "Deploy" in Dockge
   - Wait for containers to start

3. **Verify deployment**:
   - Check container logs in Dockge
   - Look for "Starting bot loop" message

## 📊 Checking Paper Trading Profits

### Method 1: Use Profit Checker Service (Recommended)

Run the profit checker on-demand:

```bash
# In Dockge, start the profit-checker container
docker-compose up profit-checker

# Or run it once
docker-compose run --rm profit-checker
```

**Expected Output:**
```
==================================================
📊 PHEMEX BOT - PAPER TRADING PROFITS
==================================================
💰 Current Equity: $52.34
💵 Cash: $52.34
📈 Exposure: $0.00
📊 Open Positions: 
🕐 Last Update: 2026-03-05T17:15:30.123456+00:00
📈 Total Return: +4.68%
📉 Max Drawdown: -1.23%

📋 RECENT TRADES:
------------------------------
🟢 2026-03-05T16:45:30 | BTC/USDT | SELL | 0.001 @ $43250.00 | PnL: +$2.3400
🔴 2026-03-05T15:30:15 | ETH/USDT | SELL | 0.01 @ $2450.00 | PnL: -$0.8900
⚪ 2026-03-05T14:20:00 | BTC/USDT | BUY | 0.001 @ $42000.00 | PnL: $0.0000

📊 TRADING SUMMARY:
------------------------------
📈 Total Trades: 15
🎯 Win Rate: 66.7%
💰 Realized PnL: +$3.456000
📊 Avg Win: +$0.2340
📉 Avg Loss: -$0.0890
🎯 Profit Factor: 2.63
==================================================
✅ Profit check completed!
==================================================
```

### Method 2: Check Container Logs

```bash
# View real-time logs
docker logs -f phemex-bot-paper

# Check recent activity
docker logs --tail 50 phemex-bot-paper
```

### Method 3: Access Files Directly

The bot creates these files in your mounted volume:

```bash
# Check equity curve
docker exec phemex-bot-paper tail -20 paper_equity.csv

# Check recent trades
docker exec phemex-bot-paper tail -10 paper_trades.csv

# Run Python analysis
docker exec phemex-bot-paper python3 -c "
import pandas as pd
equity = pd.read_csv('paper_equity.csv')
print('Latest equity:', equity.iloc[-1]['equity'])
"
```

### Method 4: Use Built-in Reports

```bash
# Run equity report
docker exec phemex-bot-paper python3 equity_report.py --equity-log paper_equity.csv --starting 50

# Run trades report
docker exec phemex-bot-paper python3 trades_report.py --trades-log paper_trades.csv

# Generate equity plot (if display available)
docker exec phemex-bot-paper python3 plot_equity.py --equity-log paper_equity.csv
```

## 🔧 Dockge Management

### Starting/Stopping Services

```bash
# Start paper trading
docker-compose up -d bot-paper

# Stop paper trading
docker-compose stop bot-paper

# View status
docker-compose ps

# View logs
docker-compose logs -f bot-paper
```

### Updating the Bot

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose up -d --build bot-paper
```

### Adding Exchange Profiles

When ready for testnet/live trading:

1. **Uncomment services** in `dockge-compose.yml`:
   ```yaml
   # Remove the profiles: lines to enable
   bot-testnet:
     # ... existing config
     # profiles:
     #   - testnet  # Comment this out
   ```

2. **Add API keys** to environment variables

3. **Deploy updated stack**

## 📁 File Structure in Dockge

```
/tradingbot/
├── dockge-compose.yml          # Dockge configuration
├── Dockerfile                   # Container build
├── data/                        # Persistent data volume
├── logs/                        # Log files volume
├── paper_equity.csv             # Equity snapshots
├── paper_trades.csv             # Trade records
├── paper_state.json.enc         # Encrypted state
└── paper_runtime_state.json.enc # Encrypted runtime state
```

## 🔍 Monitoring in Dockge

### Container Health

- **Status**: Should show "Running" in Dockge
- **Logs**: Check for errors or API issues
- **Resources**: Monitor CPU/memory usage

### Expected Log Patterns

**Normal operation:**
```
[INFO] Starting bot loop with 5 symbols
[INFO] Loaded runtime state from paper_runtime_state.json
[DEBUG] Current equity: 50.00 USDT
```

**Trading activity:**
```
[INFO] BUY signal detected for BTC/USDT
[INFO] Position opened: BTC/USDT @ $43250.00
[INFO] SELL signal detected for BTC/USDT
[INFO] Position closed: PnL +$2.34
```

**Security events:**
```
[INFO] API credentials validated (key length: 32, secret length: 64)
[WARNING] API_KILL_ON: errors>=12 in 120s; cooldown until 2026-03-05T18:00:00
```

## 🚨 Troubleshooting

### Common Issues

1. **Container won't start**:
   - Check Docker logs: `docker logs phemex-bot-paper`
   - Verify environment variables
   - Ensure volumes are mounted correctly

2. **No trading activity**:
   - Check market data connectivity
   - Verify symbol configuration
   - Review strategy parameters

3. **Permission errors**:
   - Check volume permissions
   - Ensure .env file is readable

4. **Memory issues**:
   - Monitor container resources
   - Check for memory leaks in logs

### Getting Help

1. **Check logs**: `docker logs phemex-bot-paper`
2. **Run profit checker**: `docker-compose run --rm profit-checker`
3. **Verify configuration**: Check environment variables
4. **Review documentation**: See `DEPLOYMENT.md` and `SECURITY_IMPROVEMENTS.md`

## 🎯 Best Practices

1. **Start with paper trading** - Always validate first
2. **Monitor regularly** - Check logs and profits daily
3. **Backup data** - Save CSV files regularly
4. **Update carefully** - Test updates in paper first
5. **Security first** - Use strong API keys for exchange profiles

---

## 📱 Quick Commands Summary

```bash
# Deploy paper trading
docker-compose up -d bot-paper

# Check profits
docker-compose run --rm profit-checker

# View logs
docker logs -f phemex-bot-paper

# Update bot
git pull && docker-compose up -d --build

# Stop bot
docker-compose stop bot-paper
```

**Dockge Status**: ✅ Fully Compatible  
**Last Updated**: 2026-03-05  
**Version**: v1.1.0-security
