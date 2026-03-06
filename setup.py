"""
Phemex Momentum Trading Bot - Setup Configuration
"""

from setuptools import setup, find_packages
import os

# Read requirements.txt
def read_requirements():
    with open('requirements.txt', 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read README.md
def read_readme():
    with open('README.md', 'r', encoding='utf-8') as f:
        return f.read()

setup(
    name="phemex-momentum-trading-bot",
    version="2.0.0",
    author="Trading Bot Team",
    author_email="support@tradingbot.com",
    description="Production-ready cryptocurrency momentum trading bot with enterprise security",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/storagebirddrop/tradingbot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Office/Business :: Financial :: Accounting",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
        "docker": [
            "docker>=5.0",
            "docker-compose>=1.29",
        ],
    },
    entry_points={
        "console_scripts": [
            "trading-bot=src.run_bot:main",
            "bot-health=src.healthcheck:main",
            "bot-report=scripts.equity_report:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.json", "*.md", "*.txt", "*.yml", "*.yaml"],
    },
    zip_safe=False,
    keywords="cryptocurrency, trading, bot, momentum, phemex, bitcoin, ethereum",
    project_urls={
        "Bug Reports": "https://github.com/storagebirddrop/tradingbot/issues",
        "Source": "https://github.com/storagebirddrop/tradingbot",
        "Documentation": "https://github.com/storagebirddrop/tradingbot/blob/main/README.md",
    },
)