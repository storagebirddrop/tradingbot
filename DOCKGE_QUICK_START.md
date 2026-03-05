# 🚀 Dockge Quick Start for Phemex Trading Bot

## ⚡ 5-Minute Setup

### 1. Create Stack in Dockge

**Repository**: `https://github.com/your-username/tradingbot.git`  
**Compose File**: `dockge-compose.yml`  
**Branch**: `main`

### 2. Deploy Paper Trading

Click **Deploy** in Dockge - only the `bot-paper` service will start.

### 3. Check Profits

```bash
# Method 1: Use built-in profit checker
docker-compose run --rm profit-checker

# Method 2: Use local script (after cloning)
./profit_check.sh local_paper

# Method 3: View logs
docker logs -f phemex-bot-paper
```

## 📊 Expected Output

```
==================================================
📊 PHEMEX BOT - LOCAL_PAPER TRADING PROFITS
==================================================
💰 Current Equity: $50.00
💵 Cash: $50.00
📈 Exposure: $0.00
📊 Open Positions: None
🕐 Last Update: 2026-03-05T17:30:00.123456+00:00
📈 Total Return: +0.00%
📉 Max Drawdown: +0.00%

📋 RECENT TRADES:
------------------------------
❌ No trades data available

📊 TRADING SUMMARY:
------------------------------
❌ No trades data available

📁 STATE FILES:
------------------------------
❌ paper_state.json (not found)
❌ paper_state.json.enc (not found)
❌ paper_runtime_state.json (not found)
❌ paper_runtime_state.json.enc (not found)
==================================================
✅ Profit analysis completed!
==================================================
```

## 🔧 Management Commands

```bash
# Start/Stop
docker-compose up -d bot-paper
docker-compose stop bot-paper

# Update
git pull
docker-compose up -d --build

# Logs
docker logs -f phemex-bot-paper

# Profits
docker-compose run --rm profit-checker
```

## 📱 What to Monitor

1. **Container Status**: Should show "Running" in Dockge
2. **Log Activity**: Look for "Starting bot loop" messages
3. **Equity Growth**: Check profit checker daily
4. **Trading Activity**: Monitor for BUY/SELL signals

## 🎯 Next Steps

1. **Run paper trading** for at least 1-2 weeks
2. **Monitor performance** with profit checker
3. **Add testnet** when ready (uncomment in dockge-compose.yml)
4. **Consider live trading** after successful testnet run

---

**Status**: ✅ Dockge Ready  
**Setup Time**: 5 minutes  
**Monitoring**: Built-in profit checker
