#!/usr/bin/env python3
"""
Historical Performance Analysis for Volume Reversal Strategy
6-month backtest on SOL, BTC, ETH, XRP with $50 starting capital
"""

import pandas as pd
import ccxt
from datetime import datetime, timedelta, timezone
from strategy import compute_4h_indicators, drop_incomplete_last_candle
from research.phase1c_final_strategy_selection import volume_reversal_strategy

def fetch_historical_data(symbol, months=6):
    """Fetch 6 months of historical data"""
    exchange = ccxt.phemex()
    exchange.set_sandbox_mode(True)
    
    # Calculate limit needed (6 months * 30 days * 6 candles per day)
    limit = months * 30 * 6  # ~1080 candles
    
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
        df = drop_incomplete_last_candle(df, '4h')
        
        # Filter to last 6 months
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=months*30)
        df = df[df['timestamp'] >= six_months_ago]
        
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

def simulate_strategy_performance():
    """Simulate strategy performance across all symbols"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    risk_per_trade = 0.01  # 1% per trade from config
    
    print("📊 VOLUME REVERSAL STRATEGY - 6 MONTH HISTORICAL PERFORMANCE")
    print("=" * 70)
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Risk Per Trade: {risk_per_trade*100}% of capital")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: Last 6 months")
    print()
    
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    total_return_pct = 0
    current_capital = initial_capital
    
    symbol_results = {}
    
    for symbol in symbols:
        print(f"🔍 Analyzing {symbol}...")
        
        # Fetch data
        df = fetch_historical_data(symbol)
        if df.empty:
            print(f"  ❌ No data available")
            continue
            
        # Calculate indicators
        df_ind = compute_4h_indicators(df)
        
        # Add volume reversal indicators
        df_ind['volume_sma'] = df_ind['volume'].rolling(window=20).mean()
        df_ind['volume_ratio'] = df_ind['volume'].div(df_ind['volume_sma'])
        df_ind['volume_ratio'] = df_ind['volume_ratio'].replace([float('inf'), -float('inf')], float('nan'))
        df_ind['price_change'] = df_ind['close'].pct_change()
        df_ind['volatility'] = df_ind['price_change'].rolling(window=20).std()
        
        df_ind = df_ind.dropna()
        
        # Run strategy
        trades = volume_reversal_strategy(df_ind)
        
        if trades:
            symbol_trades = len(trades)
            symbol_wins = sum(1 for t in trades if t['return_pct'] > 0)
            symbol_losses = symbol_trades - symbol_wins
            symbol_avg_return = sum(t['return_pct'] for t in trades) / len(trades)
            
            # Calculate position size and returns
            position_size = current_capital * risk_per_trade
            symbol_profit = sum(t['return_pct']/100 * position_size for t in trades)
            
            symbol_results[symbol] = {
                'trades': symbol_trades,
                'wins': symbol_wins,
                'losses': symbol_losses,
                'win_rate': symbol_wins/symbol_trades*100,
                'avg_return': symbol_avg_return,
                'profit': symbol_profit
            }
            
            total_trades += symbol_trades
            winning_trades += symbol_wins
            losing_trades += symbol_losses
            total_return_pct += symbol_avg_return * symbol_trades
            current_capital += symbol_profit
            
            print(f"  ✅ {symbol_trades} trades, {symbol_wins} wins, {symbol_losses} losses")
            print(f"  📈 Win Rate: {symbol_wins/symbol_trades*100:.1f}%")
            print(f"  💰 Avg Return: {symbol_avg_return:.2f}%")
            print(f"  💵 Profit: ${symbol_profit:.2f}")
        else:
            print(f"  ❌ No trades generated")
        
        print()
    
    # Overall results
    print("📈 OVERALL PERFORMANCE")
    print("=" * 40)
    
    if total_trades > 0:
        overall_win_rate = winning_trades / total_trades * 100
        overall_avg_return = total_return_pct / total_trades
        total_profit = current_capital - initial_capital
        total_return = (total_profit / initial_capital) * 100
        
        print(f"Total Trades: {total_trades}")
        print(f"Winning Trades: {winning_trades}")
        print(f"Losing Trades: {losing_trades}")
        print(f"Overall Win Rate: {overall_win_rate:.1f}%")
        print(f"Average Return per Trade: {overall_avg_return:.2f}%")
        print()
        print(f"Initial Capital: ${initial_capital:.2f}")
        print(f"Final Capital: ${current_capital:.2f}")
        print(f"Total Profit: ${total_profit:.2f}")
        print(f"Total Return: {total_return:.1f}%")
        print()
        
        # Monthly breakdown
        monthly_return = total_return / 6
        print(f"Average Monthly Return: {monthly_return:.1f}%")
        print(f"Annualized Return: {monthly_return*12:.1f}%")
        
    else:
        print("❌ No trades generated in 6-month period")
        print(f"Final Capital: ${initial_capital:.2f} (no change)")

if __name__ == "__main__":
    simulate_strategy_performance()