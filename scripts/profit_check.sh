#!/bin/bash

# Phemex Trading Bot - Profit Checker Script
# Usage: ./profit_check.sh [profile]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default profile
PROFILE=${1:-local_paper}

echo -e "${BLUE}📊 Phemex Trading Bot - Profit Checker${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}[ERROR]${NC} Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check if data files exist
if [ ! -f "${PROFILE}_equity.csv" ]; then
    echo -e "${YELLOW}[WARNING]${NC} No equity data found for profile: $PROFILE"
    echo "The bot may not have run yet or hasn't created equity snapshots."
    exit 0
fi

echo -e "${GREEN}[INFO]${NC} Analyzing profits for profile: $PROFILE"
echo ""

# Run profit analysis
python3 -c "
import pandas as pd
import json
import os
from datetime import datetime, timezone

# Define PROFILE from shell variable
PROFILE = '$PROFILE'

def format_currency(amount):
    return f'\${amount:,.2f}'

def format_percentage(pct):
    return f'{pct:+.2f}%'

print('=' * 60)
print(f'📊 PHEMEX BOT - {PROFILE.upper()} TRADING PROFITS')
print('=' * 60)

# Check equity
try:
    equity_df = pd.read_csv('${PROFILE}_equity.csv')
    if not equity_df.empty:
        latest_equity = equity_df.iloc[-1]
        print(f'💰 Current Equity: {format_currency(latest_equity[\"equity\"])}')
        print(f'💵 Cash: {format_currency(latest_equity[\"cash\"])}')
        print(f'📈 Exposure: {format_currency(latest_equity[\"exposure\"])}')
        print(f'📊 Open Positions: {latest_equity[\"open_positions\"] or \"None\"}')
        print(f'🕐 Last Update: {latest_equity[\"time_utc\"]}')
        
        # Calculate returns
        if len(equity_df) > 1:
            start_equity = equity_df.iloc[0]['equity']
            current_equity = latest_equity['equity']
            return_pct = ((current_equity - start_equity) / start_equity) * 100
            print(f'📈 Total Return: {format_percentage(return_pct)}')
            
            # Calculate max drawdown
            equity_df['equity'] = pd.to_numeric(equity_df['equity'])
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] / equity_df['peak'] - 1) * 100
            max_dd = equity_df['drawdown'].min()
            print(f'📉 Max Drawdown: {format_percentage(max_dd)}')
            
            # Calculate Sharpe ratio and volatility with dynamic annualization
            if len(equity_df) > 10:
                equity_df['returns'] = equity_df['equity'].pct_change()
                equity_df['timestamp'] = pd.to_datetime(equity_df['time_utc'])
                
                # Infer sampling frequency from timestamps
                time_diffs = equity_df['timestamp'].diff().dropna()
                median_delta_seconds = time_diffs.median().total_seconds()
                
                # Calculate periods per year
                seconds_per_year = 365.25 * 24 * 3600
                periods_per_year = seconds_per_year / median_delta_seconds if median_delta_seconds > 0 else 365
                
                # Calculate annualized metrics
                sharpe = equity_df['returns'].mean() / equity_df['returns'].std() * (periods_per_year**0.5) if equity_df['returns'].std() > 0 else 0
                print(f'📊 Sharpe Ratio: {sharpe:.2f}')
                
                volatility = equity_df['returns'].std() * (periods_per_year**0.5) * 100
                print(f'📊 Annual Volatility: {format_percentage(volatility)}')
                
                # Log the inferred frequency for transparency
                if periods_per_year >= 350:
                    freq_label = "daily"
                elif periods_per_year >= 150:
                    freq_label = "4-hourly"
                elif periods_per_year >= 50:
                    freq_label = "hourly"
                else:
                    freq_label = f"{periods_per_year:.0f} periods/year"
                
                print(f'📊 Inferred Frequency: {freq_label} ({periods_per_year:.1f} periods/year)')
    else:
        print('❌ No equity data available')
except FileNotFoundError:
    print('❌ Equity file not found')
except Exception as e:
    print(f'❌ Error reading equity data: {e}')

print()

# Check trades
try:
    trades_df = pd.read_csv('${PROFILE}_trades.csv')
    if not trades_df.empty:
        print('📋 RECENT TRADES:')
        print('-' * 40)
        # Show last 10 trades
        recent_trades = trades_df.tail(10)[['time_utc', 'symbol', 'side', 'qty', 'price', 'pnl']]
        for _, trade in recent_trades.iterrows():
            pnl_value = float(trade['pnl'])
            pnl_color = '🟢' if pnl_value > 0 else '🔴' if pnl_value < 0 else '⚪'
            print(f'{pnl_color} {trade[\"time_utc\"]} | {trade[\"symbol\"]} | {trade[\"side\"]} | {trade[\"qty\"]} @ ${trade[\"price\"]:.2f} | PnL: {format_currency(pnl_value)}')
        
        # Summary statistics
        sells = trades_df[trades_df['side'] == 'SELL']
        if not sells.empty:
            total_pnl = sells['pnl'].sum()
            win_rate = (sells['pnl'] > 0).mean() * 100
            num_trades = len(sells)
            
            print()
            print('📊 TRADING SUMMARY:')
            print('-' * 40)
            print(f'📈 Total Closed Trades: {num_trades}')
            print(f'🎯 Win Rate: {win_rate:.1f}%')
            print(f'💰 Realized PnL: {format_currency(total_pnl)}')
            
            if num_trades > 0:
                wins = sells[sells['pnl'] > 0]['pnl']
                losses = sells[sells['pnl'] < 0]['pnl']
                
                # Profit factor calculation (gross profit / gross loss)
                gross_profit = sells[sells['pnl'] > 0]['pnl'].sum()
                gross_loss = abs(sells[sells['pnl'] < 0]['pnl'].sum())
                
                if gross_loss > 0:
                    profit_factor = gross_profit / gross_loss
                    print(f'🎯 Profit Factor: {profit_factor:.2f}')
                elif gross_profit > 0:
                    print(f'🎯 Profit Factor: ∞ (no losses)')
                else:
                    print(f'🎯 Profit Factor: N/A (no profitable trades)')
                
                # Average win/loss for reference
                avg_win = wins.mean() if len(wins) > 0 else 0
                avg_loss = losses.mean() if len(losses) > 0 else 0
                
                print(f'📊 Avg Win: {format_currency(avg_win)}')
                print(f'📉 Avg Loss: {format_currency(avg_loss)}')
                print(f'💰 Gross Profit: {format_currency(gross_profit)}')
                print(f'💸 Gross Loss: {format_currency(gross_loss)}')
                
                # Largest win/loss
                if len(wins) > 0:
                    largest_win = wins.max()
                    print(f'🏆 Largest Win: {format_currency(largest_win)}')
                
                if len(losses) > 0:
                    largest_loss = losses.min()
                    print(f'💀 Largest Loss: {format_currency(largest_loss)}')
                
                # Consecutive wins/losses (three-way logic)
                pnl_series = sells['pnl'].tolist()
                current_streak = 0
                max_win_streak = 0
                max_loss_streak = 0
                
                for pnl in pnl_series:
                    if pnl > 0:
                        current_streak = current_streak + 1 if current_streak > 0 else 1
                        max_win_streak = max(max_win_streak, current_streak)
                    elif pnl < 0:
                        current_streak = current_streak - 1 if current_streak < 0 else -1
                        max_loss_streak = max(max_loss_streak, abs(current_streak))
                    else:  # pnl == 0, treat as neutral
                        current_streak = 0  # Reset streak
                
                print(f'🔥 Max Win Streak: {max_win_streak}')
                print(f'❄️  Max Loss Streak: {max_loss_streak}')
    else:
        print('❌ No trades data available')
except FileNotFoundError:
    print('❌ Trades file not found')
except Exception as e:
    print(f'❌ Error reading trades data: {e}')

print()

# Check state files
print('📁 STATE FILES:')
print('-' * 40)
state_files = [
    '${PROFILE}_state.json',
    '${PROFILE}_state.json.enc',
    '${PROFILE}_runtime_state.json',
    '${PROFILE}_runtime_state.json.enc'
]

for state_file in state_files:
    if os.path.exists(state_file):
        size = os.path.getsize(state_file)
        mtime = datetime.fromtimestamp(os.path.getmtime(state_file), tz=timezone.utc)
        status = '✅' if size > 0 else '⚠️'
        encrypted = '🔒' if state_file.endswith('.enc') else '📄'
        print(f'{status} {encrypted} {state_file} ({size} bytes, updated: {mtime.strftime(\"%Y-%m-%d %H:%M\")})')
    else:
        print(f'❌ {state_file} (not found)')

print()
print('=' * 60)
print('✅ Profit analysis completed!')
print('=' * 60)
"

echo ""
echo -e "${BLUE}💡 Tips:${NC}"
echo "- Run this script regularly to track performance"
echo "- Use './profit_check.sh phemex_testnet' for testnet profits"
echo "- Check 'bot.log' for detailed trading activity"
echo "- Use './status.sh' for current bot status"
