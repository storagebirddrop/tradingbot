"""
Phemex Trading Bot - Core Application Package

This package contains the core trading bot components:
- run_bot.py: Main entry point
- brokers.py: Exchange broker implementations
- runner.py: Main trading loop
- strategy.py: Trading strategy implementations
- healthcheck.py: System health monitoring
"""

__version__ = "2.0.0"
__author__ = "Trading Bot Team"
__email__ = "support@tradingbot.com"

from .run_bot import main
from .brokers import PaperBroker, ExchangeBroker
from .runner import run_loop
from .strategy import *
from .healthcheck import HealthChecker

__all__ = [
    "main",
    "PaperBroker", 
    "ExchangeBroker",
    "run_loop",
    "HealthChecker"
]