# 🚀 Phemex Trading Bot - Deployment Guide

## Quick Start Options

Choose one of the following deployment methods:

### 🐳 Option 1: Docker (Recommended)
**Best for**: Production, reproducible environments, easy updates

### 📦 Option 2: Installation Script
**Best for**: VMs, LXC containers, bare metal servers

### 🛠️ Option 3: Manual Setup
**Best for**: Development, custom environments

---

## 🐳 Docker Deployment (Recommended)

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+

### Quick Start

1. **Clone the repository**:
```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
```

2. **Create environment file**:
```bash
cp .env.template .env
nano .env
```

3. **Start paper trading**:
```bash
docker-compose --profile paper up -d
```

4. **Check status**:
```bash
docker-compose ps
docker-compose logs -f bot-paper
```

### Profile Management

#### Paper Trading
```bash
docker-compose --profile paper up -d
docker-compose logs -f bot-paper
```

#### Testnet Trading
```bash
# Set environment variables in .env
docker-compose --profile testnet up -d
docker-compose logs -f bot-testnet
```

#### Live Trading
```bash
# Set environment variables in .env
docker-compose --profile live up -d
docker-compose logs -f bot-live
```

### Docker Commands

```bash
# View logs
docker-compose logs -f [service-name]

# Stop bot
docker-compose stop [service-name]

# Restart bot
docker-compose restart [service-name]

# Update bot
git pull
docker-compose build
docker-compose up -d
```

---

## 📦 Installation Script Deployment

### Prerequisites
- Fresh VM/LXC container with:
  - Ubuntu 20.04+, Debian 10+, CentOS 8+, or Alpine 3.15+
  - Internet access
  - Non-root user (recommended)

### One-Command Installation

1. **Clone repository**:
```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
```

2. **Run installation script**:
```bash
./install.sh
```

The script will:
- ✅ Detect your operating system
- ✅ Install system dependencies
- ✅ Create Python virtual environment
- ✅ Install Python packages
- ✅ Create helper scripts
- ✅ Verify installation

### Using the Bot

After installation, use these helper scripts:

#### Run the Bot
```bash
./run_bot.sh local_paper      # Paper trading
./run_bot.sh phemex_testnet   # Testnet trading  
./run_bot.sh phemex_live       # Live trading
```

#### Check Status
```bash
./status.sh                    # Show bot status and recent logs
```

#### Health Check
```bash
./health_check.sh local_paper  # Check paper trading health
./health_check.sh phemex_testnet
./health_check.sh phemex_live
```

---

## 🛠️ Manual Setup

### System Requirements
- Python 3.8+
- 2GB RAM minimum
- 1GB disk space minimum

### Step-by-Step Installation

1. **Install system dependencies**:

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev git curl build-essential libssl-dev libffi-dev
```

**CentOS/RHEL**:
```bash
sudo dnf install -y python3 python3-pip python3-devel git curl gcc openssl-devel libffi-devel
```

**Alpine**:
```bash
sudo apk update
sudo apk add python3 py3-pip py3-venv py3-dev git curl build-base openssl-dev libffi-dev
```

2. **Clone repository**:
```bash
git clone git@github.com:storagebirddrop/tradingbot.git
cd tradingbot
```

3. **Create virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

4. **Install Python packages**:
```bash
pip install -U pip
pip install ccxt==4.2.99 pandas pandas_ta matplotlib cryptography
```

5. **Run the bot**:
```bash
python3 run_bot.py --profile local_paper
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file from template:
```bash
cp .env.template .env
```

#### Required for Exchange Profiles
```bash
PHEMEX_API_KEY=your_api_key_here
PHEMEX_API_SECRET=your_api_secret_here
```

#### Trading Enable Flags
```bash
ENABLE_TESTNET_TRADING=YES    # Enable testnet trading
ENABLE_LIVE_TRADING=YES       # Enable live trading
```

#### Optional Security
```bash
# Custom encryption key for state files
BOT_ENCRYPTION_KEY=your_custom_key_here
```

### Profile Configuration

Edit `config.json` to adjust:
- Symbols to trade
- Risk parameters
- Timeframes
- Position sizing

---

## 🔒 Security Considerations

### Production Deployment

1. **Use non-root user**
2. **Set file permissions**:
```bash
chmod 600 .env
chmod 755 *.sh
```
3. **Enable API key IP whitelisting** (in Phemex settings)
4. **Use custom encryption key**
5. **Monitor logs regularly**

### Firewall Rules

```bash
# Allow outbound HTTPS (for exchange API)
sudo ufw allow out 443/tcp

# Allow SSH (for management)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

---

## 📊 Monitoring

### Log Files

- `bot.log` - Main application logs
- `*_equity.csv` - Equity snapshots
- `*_trades.csv` - Trade records
- `*_orders.csv` - Order events (exchange profiles)

### Health Checks

```bash
# Check bot health
python3 healthcheck.py --profile [profile]

# View recent activity
tail -f bot.log

# Check system resources
docker stats  # Docker deployment
top            # Direct deployment
```

### Alerts

Monitor for these log patterns:
- `API_KILL_ON` - API errors detected
- `DAILY_KILL_SWITCH` - Daily loss limit reached
- `ERROR` - Application errors
- `WARNING` - Configuration issues

---

## 🔄 Updates and Maintenance

### Docker Updates
```bash
git pull
docker-compose build
docker-compose up -d
```

### Script Updates
```bash
git pull
source .venv/bin/activate
pip install -U ccxt pandas pandas_ta matplotlib cryptography
```

### Backup Strategy

**Important files to backup**:
- `.env` - Environment variables
- `*_state.json.enc` - Encrypted state files
- `config.json` - Bot configuration
- `BOT_ENCRYPTION_KEY` - Custom encryption key

**Automated backup script**:
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backup/tradingbot-$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

cp .env $BACKUP_DIR/
cp config.json $BACKUP_DIR/
cp *_state.json.enc $BACKUP_DIR/ 2>/dev/null || true
cp *_runtime_state.json.enc $BACKUP_DIR/ 2>/dev/null || true

tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

echo "Backup created: $BACKUP_DIR.tar.gz"
```

---

## 🐛 Troubleshooting

### Common Issues

#### Permission Denied
```bash
chmod +x install.sh run_bot.sh health_check.sh status.sh
```

#### Python Version Issues
```bash
python3 --version  # Should be 3.8+
```

#### Missing Dependencies
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

#### API Connection Issues
```bash
# Check environment variables
env | grep PHEMEX

# Test API connection
python3 -c "
import os
import ccxt
ex = ccxt.phemex({
    'apiKey': os.environ.get('PHEMEX_API_KEY'),
    'secret': os.environ.get('PHEMEX_API_SECRET'),
    'sandbox': True
})
print(ex.fetch_balance())
"
```

#### State File Corruption
```bash
# Remove corrupted state files
rm *_state.json* *_runtime_state.json*
# Bot will recreate them on next run
```

### Getting Help

1. Check logs: `tail -f bot.log`
2. Run health check: `./health_check.sh [profile]`
3. Verify configuration: `python3 -c "from run_bot import validate_config; ..."`
4. Check system resources: `free -h && df -h`

---

## 📱 Systemd Service (Optional)

For automatic startup on system boot:

```ini
# /etc/systemd/system/phemex-bot.service
[Unit]
Description=Phemex Trading Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/tradingbot
EnvironmentFile=/home/botuser/tradingbot/.env
ExecStart=/home/botuser/tradingbot/.venv/bin/python /home/botuser/tradingbot/run_bot.py --profile local_paper
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable phemex-bot
sudo systemctl start phemex-bot
sudo systemctl status phemex-bot
```

---

## 🎯 Best Practices

1. **Start with paper trading** - Always test thoroughly
2. **Use version control** - Track configuration changes
3. **Monitor regularly** - Check logs and performance
4. **Backup frequently** - Protect your data
5. **Update security** - Keep dependencies current
6. **Test disaster recovery** - Verify backup/restore procedures

---

## 📞 Support

For deployment issues:
1. Check this guide first
2. Review `bot.log` for error messages
3. Run health check: `./health_check.sh [profile]`
4. Verify environment variables and permissions

---

**Deployment Status**: ✅ Production Ready  
**Last Updated**: 2026-03-05  
**Version**: v1.1.0-security
