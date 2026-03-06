#!/bin/bash

echo "=== Trading Bot Path Diagnostic ==="
echo ""

# Check bot directory
echo "Bot directory:"
ls -la /home/tradingbot/tradingbot/
echo ""

# Check virtual environment
echo "Virtual environment:"
ls -la /home/tradingbot/tradingbot/.venv/bin/
echo ""

# Check Python executable
echo "Python executable check:"
if [ -f "/home/tradingbot/tradingbot/.venv/bin/python3" ]; then
    echo "✓ Python3 found"
    ls -la /home/tradingbot/tradingbot/.venv/bin/python3
else
    echo "✗ Python3 NOT found"
fi
echo ""

# Check run_bot.py
echo "run_bot.py check:"
if [ -f "/home/tradingbot/tradingbot/run_bot.py" ]; then
    echo "✓ run_bot.py found"
    ls -la /home/tradingbot/tradingbot/run_bot.py
else
    echo "✗ run_bot.py NOT found"
fi
echo ""

# Test the command manually
echo "Testing command manually:"
/home/tradingbot/tradingbot/.venv/bin/python3 /home/tradingbot/tradingbot/run_bot.py --help
