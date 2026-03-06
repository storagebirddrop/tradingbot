# 🚀 Phemex Momentum Trading Bot - Deployment Guide

## 📋 Deployment Options

| Method | Difficulty | Best For | Features |
|--------|------------|----------|----------|
| **Docker** | ⭐ Easy | Production, reproducible environments | Containerized, isolated, easy updates |
| **Installation Script** | ⭐⭐ Medium | VMs, LXC, bare metal | Automated setup, system integration |
| **Manual Setup** | ⭐⭐⭐ Hard | Development, custom environments | Full control, customizable |

---

## 🐳 Docker Deployment (Recommended)

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB+ RAM
- 10GB+ disk space

### Quick Start
```bash
# Clone repository
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot

# Configure environment
cp .env.template .env
nano .env  # Add BOT_ENCRYPTION_KEY + API keys

# Start paper trading
docker-compose --profile paper up -d

# View logs
docker-compose logs -f bot-paper
```

### Docker Compose Configuration
```yaml
version: '3.8'
services:
  bot-paper:
    build: .
    restart: unless-stopped
    environment:
      - BOT_ENV=production
    env_file:
      - .env
    volumes:
      - ./paper_equity.csv:/app/paper_equity.csv
      - ./paper_trades.csv:/app/paper_trades.csv
      - ./bot.log:/app/bot.log
      - ./paper_state.json.enc:/app/paper_state.json.enc
    networks:
      - tradingbot

  bot-testnet:
    build: .
    restart: unless-stopped
    environment:
      - BOT_ENV=production
    env_file:
      - .env
    volumes:
      - ./testnet_equity.csv:/app/testnet_equity.csv
      - ./testnet_trades.csv:/app/testnet_trades.csv
      - ./bot.log:/app/bot.log
      - ./testnet_state.json.enc:/app/testnet_state.json.enc
    networks:
      - tradingbot
    profiles:
      - testnet

  bot-live:
    build: .
    restart: unless-stopped
    environment:
      - BOT_ENV=production
    env_file:
      - .env
    volumes:
      - ./live_equity.csv:/app/live_equity.csv
      - ./live_trades.csv:/app/live_trades.csv
      - ./bot.log:/app/bot.log
      - ./live_state.json.enc:/app/live_state.json.enc
    networks:
      - tradingbot
    profiles:
      - live

networks:
  tradingbot:
    driver: bridge
```

### Docker Commands
```bash
# Paper trading
docker-compose --profile paper up -d
docker-compose logs -f bot-paper

# Testnet trading
docker-compose --profile testnet up -d
docker-compose logs -f bot-testnet

# Live trading
docker-compose --profile live up -d
docker-compose logs -f bot-live

# Stop all
docker-compose down

# Update bot
git pull
docker-compose build --no-cache
docker-compose up -d
```

---

## 📦 Installation Script Deployment

### Prerequisites
- Ubuntu 20.04+ / Debian 11+
- Python 3.8+
- 2GB+ RAM
- 10GB+ disk space

### Automated Installation
```bash
# Clone and install
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot
chmod +x install.sh
./install.sh

# Configure environment
cp .env.template .env
nano .env  # Add BOT_ENCRYPTION_KEY + API keys

# Run paper trading
./run_bot.sh local_paper
```

### Installation Script Features
- ✅ Automatic dependency installation
- ✅ Python virtual environment setup
- ✅ System user creation (tradingbot)
- ✅ File permissions configuration
- ✅ Systemd service setup
- ✅ Log rotation configuration
- ✅ Security hardening

### Service Management
```bash
# Enable and start service
sudo systemctl enable tradingbot
sudo systemctl start tradingbot

# Check status
sudo systemctl status tradingbot
sudo journalctl -u tradingbot -f

# Restart service
sudo systemctl restart tradingbot

# View logs
sudo journalctl -u tradingbot --since "1 hour ago"
```

---

## 🛠️ Manual Deployment

### Prerequisites
- Python 3.8+
- pip package manager
- Git
- Text editor

### Step-by-Step Setup
```bash
# 1. Clone repository
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.template .env
nano .env  # Add BOT_ENCRYPTION_KEY + API keys

# 5. Test configuration
python3 healthcheck.py --profile local_paper

# 6. Run paper trading
python3 run_bot.py --profile local_paper
```

### Manual Systemd Service
```bash
# Create service file
sudo nano /etc/systemd/system/tradingbot.service
```

```ini
[Unit]
Description=Trading Bot Service
After=network.target

[Service]
Type=simple
User=tradingbot
Group=tradingbot
WorkingDirectory=/home/tradingbot/tradingbot
EnvironmentFile=/home/tradingbot/tradingbot/.env
Environment=BOT_ENV=production
ExecStart=/bin/bash -c 'source /home/tradingbot/tradingbot/.venv/bin/activate && python3 /home/tradingbot/tradingbot/run_bot.py --profile local_paper'
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradingbot

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable tradingbot
sudo systemctl start tradingbot
```

---

## 🔒 Security Configuration

### Environment Variables Security
```bash
# Set proper file permissions
chmod 600 .env
chown tradingbot:tradingbot .env

# Validate configuration
python3 healthcheck.py --security-check
```

### System Security
```bash
# Create dedicated user
sudo useradd -m -s /bin/bash tradingbot
sudo usermod -a -G tradingbot $USER

# Set file permissions
sudo chown -R tradingbot:tradingbot /home/tradingbot/tradingbot
chmod 755 /home/tradingbot/tradingbot
chmod 600 /home/tradingbot/tradingbot/.env
```

### Firewall Configuration
```bash
# Allow outbound HTTPS (for exchange API)
sudo ufw allow out 443/tcp
sudo ufw allow out 80/tcp

# Optional: Allow inbound monitoring
sudo ufw allow from 192.168.1.0/24 to any port 22/tcp
```

---

## 📊 Monitoring & Logging

### Log Management
```bash
# View real-time logs
tail -f bot.log

# Rotate logs (logrotate)
sudo nano /etc/logrotate.d/tradingbot
```

```
/home/tradingbot/tradingbot/bot.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    su tradingbot tradingbot
}
```

### Performance Monitoring
```bash
# System resources
htop
iostat -x 1

# Bot-specific monitoring
./status.sh
python3 healthcheck.py --profile local_paper

# Performance reports
python3 equity_report.py --equity-log paper_equity.csv --starting 50
python3 trades_report.py --trades-log paper_trades.csv
```

### Alerting Setup
```bash
# Create monitoring script
nano monitor_bot.sh
```

```bash
#!/bin/bash
# Bot monitoring script
BOT_PID=$(pgrep -f "python3.*run_bot.py")
if [ -z "$BOT_PID" ]; then
    echo "Bot is not running! Restarting..."
    ./run_bot.sh local_paper
    # Send alert (email, webhook, etc.)
fi

# Check for errors
ERROR_COUNT=$(grep -c "ERROR" bot.log | tail -1)
if [ "$ERROR_COUNT" -gt 10 ]; then
    echo "High error count detected: $ERROR_COUNT"
    # Send alert
fi
```

```bash
# Make executable and add to crontab
chmod +x monitor_bot.sh
crontab -e
```

```
*/5 * * * * /home/tradingbot/tradingbot/monitor_bot.sh
```

---

## 🔄 Backup & Recovery

### Data Backup
```bash
# Create backup script
nano backup_bot.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/backups/tradingbot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup configuration and data
tar -czf $BACKUP_DIR/bot_backup_$DATE.tar.gz \
    .env \
    config.json \
    *_equity.csv \
    *_trades.csv \
    *_state.json.enc \
    bot.log

# Keep last 30 days
find $BACKUP_DIR -name "bot_backup_*.tar.gz" -mtime +30 -delete
```

```bash
# Schedule daily backups
chmod +x backup_bot.sh
crontab -e
```

```
0 2 * * * /home/tradingbot/tradingbot/backup_bot.sh
```

### Recovery Procedures
```bash
# Restore from backup
tar -xzf /backups/tradingbot/bot_backup_YYYYMMDD_HHMMSS.tar.gz

# Restart bot
./run_bot.sh local_paper
```

---

## 🚀 Production Deployment Checklist

### Pre-Deployment
- [ ] Environment variables configured (.env)
- [ ] API keys tested and validated
- [ ] Risk parameters reviewed
- [ ] Security audit completed
- [ ] Backup procedures implemented
- [ ] Monitoring configured
- [ ] Alert thresholds set

### Deployment Steps
1. **Paper Trading Validation**
   ```bash
   ./run_bot.sh local_paper
   # Monitor for 1-2 weeks
   ```

2. **Performance Review**
   ```bash
   python3 equity_report.py --equity-log paper_equity.csv --starting 50
   python3 trades_report.py --trades-log paper_trades.csv
   ```

3. **Testnet Testing**
   ```bash
   ./run_bot.sh phemex_testnet
   # Monitor for 1 week
   ```

4. **Live Trading (Small Scale)**
   ```bash
   # Reduce position sizes in config.json
   ./run_bot.sh phemex_live
   # Monitor closely
   ```

5. **Full Scale Production**
   ```bash
   # Restore normal position sizes
   ./run_bot.sh phemex_live
   ```

### Post-Deployment
- [ ] Monitor win rate and drawdown
- [ ] Check error logs daily
- [ ] Review performance weekly
- [ ] Update strategy parameters as needed
- [ ] Maintain backup schedule

---

## 🔧 Advanced Configuration

### Multi-Instance Deployment
```bash
# Create separate instances
cp -r tradingbot tradingbot_2
cd tradingbot_2

# Use different configuration
nano .env  # Different API keys
nano config.json  # Different parameters

# Run second instance
./run_bot.sh local_paper
```

### Load Balancing
```bash
# Use multiple API keys
# Configure different symbols per instance
# Set different timeframes
```

### High Availability
```bash
# Multiple servers
# Shared state storage (database)
# Failover configuration
```

---

## 📚 Additional Resources

### Documentation
- **README.md** - Complete overview
- **QUICK_START.md** - One-page guide
- **SECURITY_IMPROVEMENTS.md** - Security features
- **TESTING_GUIDE.md** - Testing procedures

### Community & Support
- GitHub Issues: Report bugs and request features
- Documentation: Check existing guides first
- Health Check: `python3 healthcheck.py`

### Troubleshooting
```bash
# Common issues and solutions
./diagnose_paths.sh
python3 healthcheck.py --verbose
python3 healthcheck.py --profile local_paper --debug
```

---

## 🎯 Deployment Summary

### Recommended Production Setup
1. **Docker** for containerization
2. **Systemd** for service management
3. **Logrotate** for log management
4. **Cron** for monitoring and backups
5. **Firewall** for security
6. **Dedicated user** for isolation

### Quick Production Command
```bash
# Complete production setup
git clone https://github.com/storagebirddrop/tradingbot.git
cd tradingbot
cp .env.template .env && nano .env  # Configure
docker-compose --profile live up -d
docker-compose logs -f bot-live
```

---

**🚀 Ready for production?** Follow the Production Deployment Checklist and start with paper trading to validate your setup!