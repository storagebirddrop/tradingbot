# Phemex Momentum Trading Bot - Makefile

.PHONY: help install clean paper testnet live health equity trades logs

help:
	@echo "Usage:"
	@echo "  make install     Install dependencies into .venv"
	@echo "  make clean       Remove .pyc files and __pycache__"
	@echo "  make paper       Run paper trading (local_paper profile)"
	@echo "  make testnet     Run testnet profile"
	@echo "  make live        Run live profile"
	@echo "  make health      Health check (paper)"
	@echo "  make equity      Print equity report (paper)"
	@echo "  make trades      Print trades report (paper)"
	@echo "  make logs        Tail paper trading log"

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +

# --- Trading ---

paper:
	python3 -m src.run_bot --profile local_paper

testnet:
	python3 -m src.run_bot --profile phemex_testnet

live:
	python3 -m src.run_bot --profile phemex_live

# --- Monitoring ---

health:
	python3 -m src.healthcheck --profile local_paper

equity:
	python3 scripts/equity_report.py --equity-log paper_equity.csv --starting 50

trades:
	python3 scripts/trades_report.py --trades-log paper_trades.csv

logs:
	tail -f local_paper.log
