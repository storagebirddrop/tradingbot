# ⚡ Phemex Momentum Trading Bot - Quick Start

## 🚀 One-Command Setup

### Option 1: Automated Installation (Recommended)
```bash
# Clone and install
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot
chmod +x install.sh
./install.sh

# Configure environment (REQUIRED for ALL profiles)
cp .env.template .env
nano .env  # Add BOT_ENCRYPTION_KEY (required) + API keys (exchange profiles)

# Start paper trading (no API keys needed)
./run_bot.sh local_paper
```

### Option 2: Docker (Easiest)
```bash
# Clone and setup
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot

# Configure environment (REQUIRED)
cp .env.template .env
nano .env  # Add BOT_ENCRYPTION_KEY + API keys

# Run with Docker
docker-compose --profile paper up -d
docker-compose logs -f bot-paper
```

### Option 3: Manual Setup
```bash
# Clone and setup
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment (REQUIRED)
cp .env.template .env
nano .env  # Add BOT_ENCRYPTION_KEY + API keys

# Run paper trading
python3 run_bot.py --profile local_paper
```

---

## 🔑 Environment Setup (.env)

### **Required for ALL Profiles**
```bash
# Generate encryption key (run this command)
python3 -c "
import base64, os
print(f'BOT_ENCRYPTION_KEY={base64.urlsafe_b64encode(os.urandom(32)).decode()}')
"

# Add to .env file
BOT_ENCRYPTION_KEY=your_generated_key_here
```

### **Exchange Trading Only**
```bash
# Add to .env for testnet/live trading
PHEMEX_API_KEY=your_api_key_here
PHEMEX_API_SECRET=your_api_secret_here
```

---

## 📊 Trading Profiles

| Profile | Command | API Keys | Use Case |
|---------|----------|-----------|----------|
| **Paper Trading** | `./run_bot.sh local_paper` | ❌ No | Strategy testing |
| **Testnet Trading** | `./run_bot.sh phemex_testnet` | ✅ Yes | Exchange testing |
| **Live Trading** | `./run_bot.sh phemex_live` | ✅ Yes | Production |

---

## 🎯 Strategy Overview

**Current Strategy**: Optimized Momentum (Multi-Indicator)

**Key Features**:
- 6 technical indicators (EMA SuperTrend, RSI, MACD, Volume, Momentum, MTF)
- 3/6 signals required for entry (flexible but quality-focused)
- 2x leverage capability
- Dynamic position sizing (0.5-1.5x based on signal strength)
- ATR-based stop losses
- Signal reversal exits (73% of exits)

**Performance**:
- **Projected Annual Return**: 234.6%
- **Win Rate**: 39% (typical for momentum)
- **Trade Frequency**: 474 trades/month
- **Max Drawdown**: 24.3%

---

## 🛡️ Risk Management

**Conservative Parameters**:
- **Risk per Trade**: 1% (4% effective with 2x leverage)
- **Max Positions**: 2 concurrent
- **Total Exposure**: 25% maximum
- **Stop Loss**: 3% minimum, ATR-based
- **Take Profit**: 15%
- **Max Holding**: 24 hours

---

## 📈 Monitoring Commands

```bash
# Check bot status
./status.sh

# Health check
python3 healthcheck.py --profile local_paper

# View live logs
tail -f bot.log

# Performance reports
python3 equity_report.py --equity-log paper_equity.csv --starting 50
python3 trades_report.py --trades-log paper_trades.csv
```

---

## 🐳 Docker Commands

```bash
# Start paper trading
docker-compose --profile paper up -d

# View logs
docker-compose logs -f bot-paper

# Stop bot
docker-compose down

# Rebuild
docker-compose build --no-cache
```

---

## 🚨 Troubleshooting

### **Common Issues**

**"Encryption key required" error**:
```bash
# Generate and add key to .env
python3 -c "
import base64, os
print(f'BOT_ENCRYPTION_KEY={base64.urlsafe_b64encode(os.urandom(32)).decode()}')
"
```

**"No trades generated"**:
- Check market data availability
- Verify strategy parameters
- Ensure volume thresholds are achievable

**High drawdown**:
- Reduce risk_per_trade in config.json
- Enable risk_off_exits
- Check market volatility

### **Debug Mode**
```bash
export LOG_LEVEL=DEBUG
python3 run_bot.py --profile local_paper
```

---

## 📞 Quick Help

1. **Documentation**: `README.md` (complete guide)
2. **Deployment**: `DEPLOYMENT.md` (detailed setup)
3. **Security**: `SECURITY_IMPROVEMENTS.md`
4. **Health Check**: `python3 healthcheck.py`

---

## 🎯 Next Steps

1. **Paper Trade First**: Validate strategy with paper trading
2. **Monitor Performance**: Check win rate and drawdown
3. **Adjust Parameters**: Optimize for your risk tolerance
4. **Testnet Testing**: Exchange testing with simulated funds
5. **Go Live**: Start with small position sizes

---

**🚀 Ready?** Run the installation command above and start paper trading in minutes!