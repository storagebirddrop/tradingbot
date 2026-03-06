# Phemex Momentum Trading Bot - Makefile
# Provides common commands for development and deployment

.PHONY: help install install-dev test lint format clean docker-build docker-run docker-stop

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linting"
	@echo "  format       - Format code"
	@echo "  clean        - Clean temporary files"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo "  docker-stop  - Stop Docker container"
	@echo "  paper-trade  - Run paper trading"
	@echo "  health-check - Run health check"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

# Development
test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	flake8 src/ scripts/ strategies/
	mypy src/

format:
	black src/ scripts/ strategies/
	isort src/ scripts/ strategies/

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/

# Docker
docker-build:
	docker build -t phemex-trading-bot .

docker-run:
	docker-compose --profile paper up -d

docker-stop:
	docker-compose down

# Trading
paper-trade:
	python3 src/run_bot.py --profile local_paper

health-check:
	python3 src/healthcheck.py --profile local_paper

# Scripts
equity-report:
	python3 scripts/equity_report.py --equity-log data/paper_equity.csv --starting 50

trades-report:
	python3 scripts/trades_report.py --trades-log data/paper_trades.csv

plot-equity:
	python3 scripts/plot_equity.py --equity-file data/paper_equity.csv

# Strategy testing
test-strategy:
	python3 strategies/optimized_momentum_strategy.py

test-all-strategies:
	python3 strategies/comprehensive_strategy_backtest.py

# Development helpers
check-deps:
	pip-audit
	safety check

update-deps:
	pip-compile requirements.in
	pip install -r requirements.txt

# Deployment
setup-service:
	sudo cp tradingbot.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable tradingbot

# Monitoring
logs:
	tail -f logs/bot.log

status:
	./scripts/diagnose_paths.sh

# Archive
archive-old:
	tar -czf archive/backup-$(shell date +%Y%m%d).tar.gz \
		data/ logs/ *.csv *.json.enc *.log