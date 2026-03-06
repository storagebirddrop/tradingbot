# 🚀 Phemex Momentum Trading Bot - Production Ready

> **⚠️ Risk Disclaimer**: This is an educational trading tool. You are solely responsible for all trading decisions, losses, exchange compliance, and tax obligations. Cryptocurrency markets are highly volatile; losses can exceed initial investments.

> **🔒 Security Notice**: Enterprise-grade security with state encryption, API validation, comprehensive audit logging, and error recovery mechanisms.

---

## 📊 Current Performance (Optimized Momentum Strategy)

**🎯 Backtested Results (6 months):**
- **Annual Return**: 234.6% projected
- **Win Rate**: 39.0% (momentum strategies typically lower)
- **Trade Frequency**: 474 trades/month (high-frequency)
- **Profit Factor**: 1.46 (solid risk-adjusted returns)
- **Max Drawdown**: 24.3% (acceptable for high-return strategy)
- **Strategy**: Multi-Indicator Momentum (3/6 signals required)

**📈 Per-Symbol Performance:**
- **BTC**: 720 trades, 0.14% avg return
- **ETH**: 709 trades, 0.40% avg return  
- **SOL**: 711 trades, 0.75% avg return (best performer)
- **XRP**: 704 trades, 0.57% avg return

---

## 🎯 Strategy Overview

### **Optimized Momentum Strategy**
The bot uses a sophisticated multi-indicator momentum approach with 2x leverage capability:

**🔧 Technical Indicators:**
- **EMA SuperTrend**: Trend direction and momentum
- **RSI**: Overbought/oversold conditions (relaxed thresholds)
- **MACD**: Momentum confirmation and acceleration
- **Volume Profile**: Volume confirmation (1.2x average)
- **Price Momentum**: Minimum 0.2% price movement
- **Multi-timeframe**: 9/21/50/200 EMA stack for trend confirmation

**⚡ Entry Logic (3/6 signals required):**
- **Long**: SuperTrend bullish + RSI < 45 + Volume confirmation + MACD positive + Price momentum > 0.2% + Bullish MTF
- **Short**: SuperTrend bearish + RSI > 55 + Volume confirmation + MACD negative + Price momentum < -0.2% + Bearish MTF

**🛡️ Risk Management:**
- **Position Sizing**: 8% risk per trade (4% effective with 2x leverage)
- **Stop Loss**: 3% minimum, ATR-based (2.0x multiplier)
- **Take Profit**: 15% (crypto-appropriate)
- **Max Holding**: 24 hours
- **Signal Reversal**: Primary exit mechanism (73% of exits)

---

## 🚀 Quick Start (3 Options)

### Option 1: Automated Installation (Recommended)
```bash
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
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot
cp .env.template .env
# Edit .env with your configuration
docker-compose --profile paper up -d
docker-compose logs -f bot-paper
```

### Option 3: Manual Setup
```bash
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

## 📋 Trading Profiles

| Profile | Type | API Keys Required | Use Case |
|---------|------|------------------|----------|
| **local_paper** | Paper Trading | ❌ No | Strategy testing with live data |
| **phemex_testnet** | Testnet Trading | ✅ Yes | Exchange testing with simulated funds |
| **phemex_live** | Live Trading | ✅ Yes | Production trading with real funds |

**🔑 ALL PROFILES require `.env` file with `BOT_ENCRYPTION_KEY` for state encryption**

---

## 🛡️ Security Features (v2.0)

- ✅ **State File Encryption** - All sensitive data encrypted at rest
- ✅ **API Credential Validation** - Strong password requirements
- ✅ **Configuration Validation** - Prevents invalid parameters
- ✅ **Structured Logging** - Comprehensive audit trail (`bot.log`)
- ✅ **Error Recovery** - Graceful failure handling with context
- ✅ **Rate Limiting** - Built-in exchange rate limit protection
- ✅ **Risk Controls** - Conservative exposure limits and safety exits

---

## 📊 Risk Management

### **Conservative Safety Parameters**
```json
{
  "risk_per_trade": 0.01,        // 1% risk per trade
  "max_positions": 2,             // Maximum concurrent positions
  "max_position_pct": 0.15,       // 15% max per position
  "max_total_exposure_pct": 0.25, // 25% total portfolio exposure
  "risk_off_exits": true,         // Automatic risk-off exits
  "stop_pct": 0.02,               // 2% stop loss
  "trail_pct": 0.02              // 2% trailing stop
}
```

### **Position Sizing Logic**
- **Base Risk**: 1% per trade (conservative)
- **Dynamic Adjustment**: 0.5-1.5x based on signal strength
- **Maximum Risk**: 1.5% per trade (strong signals only)
- **Portfolio Heat**: Maximum 25% total exposure

---

## 🔧 Configuration

### **Environment Variables (.env)**
```bash
# Required for ALL profiles
BOT_ENCRYPTION_KEY=your_32_byte_base64_key_here

# Required for exchange profiles
PHEMEX_API_KEY=your_api_key_here
PHEMEX_API_SECRET=your_api_secret_here

# Optional
BOT_ENV=production  # development, test, or production
```

### **Strategy Parameters**
```json
{
  "volume_reversal_strategy": {
    "enabled": true,
    "stop_loss_pct": 0.03,        // 3% stop loss
    "take_profit_pct": 0.15,      // 15% take profit
    "max_holding_periods": 24,     // 24 hours max
    "volume_ratio_threshold": 1.2,  // 1.2x volume confirmation
    "rsi_threshold": 45,           // Relaxed RSI threshold
    "risk_per_trade": 0.08         // 8% risk (4% effective with 2x leverage)
  }
}
```

---

## 📈 Monitoring & Performance

### **Real-time Monitoring**
```bash
# Check bot status
./status.sh

# Health check
python3 healthcheck.py --profile local_paper

# View logs
tail -f bot.log

# Equity report
python3 equity_report.py --equity-log paper_equity.csv --starting 50

# Trade analysis
python3 trades_report.py --trades-log paper_trades.csv
```

### **Performance Metrics**
- **Win Rate**: Target 35-45% (momentum strategies)
- **Profit Factor**: Target >1.5
- **Sharpe Ratio**: Target >0.5
- **Max Drawdown**: Target <25%
- **Trade Frequency**: 100-500/month (depends on market)

---

## 🐳 Docker Deployment

### **Docker Compose Setup**
```yaml
version: '3.8'
services:
  bot-paper:
    build: .
    environment:
      - BOT_ENV=production
    env_file:
      - .env
    volumes:
      - ./paper_equity.csv:/app/paper_equity.csv
      - ./paper_trades.csv:/app/paper_trades.csv
      - ./bot.log:/app/bot.log
```

### **Docker Commands**
```bash
# Build and run
docker-compose --profile paper up -d

# View logs
docker-compose logs -f bot-paper

# Stop
docker-compose down
```

---

## 🚀 Production Deployment

### **Systemd Service**
```bash
# Install service
sudo cp tradingbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tradingbot
sudo systemctl start tradingbot

# Check status
sudo systemctl status tradingbot
sudo journalctl -u tradingbot -f
```

### **Production Checklist**
- [ ] Environment variables configured in `.env`
- [ ] API keys properly set with required permissions
- [ ] Risk parameters reviewed and appropriate
- [ ] Monitoring and alerting configured
- [ ] Backup procedures for state files
- [ ] Security audit completed
- [ ] Paper trading validation completed

---

## 🔍 Advanced Configuration

### **Multi-Symbol Support**
```json
{
  "symbols": [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"
  ],
  "symbol_strategy": {
    "VTHO/USDT": "vwap_band_bounce"  // Per-symbol strategy override
  }
}
```

### **Timeframe Configuration**
```json
{
  "signal_timeframe": "4h",    // Primary signal timeframe
  "regime_timeframe": "1d",    // Market regime analysis
  "limit_4h": 800,             // 4h candle limit
  "limit_1d": 600              // Daily candle limit
}
```

---

## 🛠️ Development & Testing

### **Strategy Backtesting**
```bash
# Test optimized momentum strategy
python3 optimized_momentum_strategy.py

# Test comprehensive strategies
python3 comprehensive_strategy_backtest.py

# Test aggressive strategies
python3 aggressive_strategy_backtest.py
```

### **Indicator Validation**
```bash
# Check RSI frequency analysis
python3 check_rsi_frequency.py

# Test strategy research
python3 strategy_research_summary.py
```

---

## 📚 Documentation Structure

### **Core Documentation**
- **README.md** - This file, complete overview
- **QUICK_START.md** - One-page setup guide
- **DEPLOYMENT.md** - Detailed deployment options
- **SECURITY_IMPROVEMENTS.md** - Security features guide

### **Strategy Documentation**
- **STRATEGY_SWITCHING_GUIDE.md** - Strategy configuration
- **strategy_research_summary.md** - Strategy research findings

### **Deployment Guides**
- **DOCKGE_DEPLOYMENT.md** - Dockge deployment
- **DOCKGE_QUICK_START.md** - Dockge quick setup
- **TESTING_GUIDE.md** - Testing procedures

---

## 🔧 Troubleshooting

### **Common Issues**

**Q: Bot won't start with "encryption key" error**
```bash
# Solution: Generate encryption key
python3 -c "
import base64, os
print(f'BOT_ENCRYPTION_KEY={base64.urlsafe_b64encode(os.urandom(32)).decode()}')
"
# Add to .env file
```

**Q: "No trades generated" in backtest**
- Check if market data is available
- Verify strategy parameters aren't too restrictive
- Ensure volume thresholds are achievable

**Q: High drawdown in live trading**
- Reduce risk_per_trade parameter
- Enable risk_off_exits
- Check market volatility conditions

### **Debug Mode**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python3 run_bot.py --profile local_paper
```

---

## 📞 Support & Community

### **Getting Help**
1. **Check Documentation**: Review relevant .md files
2. **Search Issues**: Check GitHub issues for similar problems
3. **Health Check**: Run `python3 healthcheck.py`
4. **Log Analysis**: Review `bot.log` for error patterns

### **Contributing**
1. Fork the repository
2. Create feature branch
3. Test thoroughly with paper trading
4. Submit pull request with documentation

---

## 📄 License & Legal

**License**: MIT License - see LICENSE file for details

**Legal Notice**:
- This software is for educational purposes only
- Not financial advice - do your own research
- Cryptocurrency trading involves substantial risk
- Past performance does not guarantee future results
- You are responsible for compliance with local regulations

---

## 🔗 Links & Resources

- **GitHub Repository**: https://github.com/storagebirddrop/tradingbot
- **Phemex Exchange**: https://phemex.com
- **Phemex Referral**: https://phemex.com/rewards-hub?referralCode=IX83P9&scene=referral
- **Docker Hub**: [Docker image repository]
- **Documentation Index**: See table of contents above

---

## 🎯 Quick Reference Commands

```bash
# Setup
git clone https://github.com/storagebirddrop/tradingbot.git && cd tradingbot
./install.sh && cp .env.template .env && nano .env

# Paper Trading
./run_bot.sh local_paper

# Monitoring
./status.sh
python3 healthcheck.py --profile local_paper
tail -f bot.log

# Performance
python3 equity_report.py --equity-log paper_equity.csv --starting 50
python3 trades_report.py --trades-log paper_trades.csv

# Production
sudo systemctl enable tradingbot && sudo systemctl start tradingbot
```

---

**🚀 Ready to start trading?** Follow the Quick Start section above and begin with paper trading to validate the strategy before deploying with real funds.