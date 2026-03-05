#!/usr/bin/env python3
"""
Phase 1A: Alternative Strategy Discovery
Research fundamentally different strategies to replace the flawed short approach
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators

# Extended market periods for comprehensive testing
EXTENDED_PERIODS = {
    'recent_period': {'description': 'Recent risk-off (2024)', 'volatility': 'moderate'},
    'recovery_period': {'description': 'Post-bear recovery (2023)', 'volatility': 'moderate'},
    'bull_peak_bear': {'description': 'Bull peak to bear (2022)', 'volatility': 'high'},
    'covid_crash': {'description': 'COVID crash & recovery (2020-21)', 'volatility': 'extreme'},
}

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

def load_historical_data(symbol, period):
    """Load historical data for a symbol and period"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    filepath_4h = f"/home/dribble0335/dev/tradingbot/research/historical/{filename_4h}"
    
    if os.path.exists(filepath_4h):
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def calculate_extended_indicators(df):
    """Calculate extended indicators for alternative strategies"""
    if df.empty:
        return df
    
    # Base indicators from strategy.py
    df_ind = compute_4h_indicators(df)
    
    # Additional indicators for alternative strategies
    df_ind['bb_upper'], df_ind['bb_middle'], df_ind['bb_lower'] = calculate_bollinger_bands(df_ind['close'])
    df_ind['atr'] = calculate_atr(df_ind)
    df_ind['volume_sma'] = df_ind['volume'].rolling(window=20).mean()
    df_ind['volume_ratio'] = df_ind['volume'] / df_ind['volume_sma']
    df_ind['price_change'] = df_ind['close'].pct_change()
    df_ind['volatility'] = df_ind['price_change'].rolling(window=20).std()
    
    return df_ind.dropna()

def calculate_bollinger_bands(close, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    true_range = np.maximum(high_low, np.maximum(high_close, low_close))
    atr = true_range.rolling(window=period).mean()
    
    return atr

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=20, is_long=True):
    """Simulate a trade with proper risk management"""
    if is_long:
        stop_loss_price = entry_price * (1 - stop_loss_pct)
        take_profit_price = entry_price * (1 + take_profit_pct)
    else:  # short
        stop_loss_price = entry_price * (1 + stop_loss_pct)
        take_profit_price = entry_price * (1 - take_profit_pct)
    
    for j in range(entry_idx + 1, min(entry_idx + max_holding_periods + 1, len(df))):
        current_candle = df.iloc[j]
        current_price = current_candle['close']
        
        # Check stop loss
        if is_long and current_price <= stop_loss_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': stop_loss_price,
                'exit_reason': 'stop_loss',
                'return_pct': -stop_loss_pct,
                'holding_periods': j - entry_idx
            }
        elif not is_long and current_price >= stop_loss_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': stop_loss_price,
                'exit_reason': 'stop_loss',
                'return_pct': -stop_loss_pct,
                'holding_periods': j - entry_idx
            }
        
        # Check take profit
        if is_long and current_price >= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct,
                'holding_periods': j - entry_idx
            }
        elif not is_long and current_price <= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct,
                'holding_periods': j - entry_idx
            }
        
        # Check signal reversal (simplified)
        if j > entry_idx + 1:
            sig = current_candle
            
            # For long positions: exit if RSI > 70 or price crosses below SMA
            if is_long and (sig['rsi'] > 70 or sig['close'] < sig['sma200_4h']):
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (current_price - entry_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
            # For short positions: exit if RSI < 30 or price crosses above SMA
            elif not is_long and (sig['rsi'] < 30 or sig['close'] > sig['sma200_4h']):
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (entry_price - current_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
    
    # Max holding period reached
    final_price = df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['close']
    return_pct = (final_price - entry_price) / entry_price * 100 if is_long else (entry_price - final_price) / entry_price * 100
    
    return {
        'exit_time': df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['timestamp'],
        'exit_price': final_price,
        'exit_reason': 'max_holding',
        'return_pct': return_pct,
        'holding_periods': max_holding_periods
    }

def calculate_risk_metrics(trades):
    """Calculate comprehensive risk metrics"""
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_return': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'avg_holding_periods': 0,
            'stop_loss_rate': 0,
            'take_profit_rate': 0,
            'signal_reversal_rate': 0,
            'max_consecutive_losses': 0,
            'sharpe_ratio': 0
        }
    
    returns = [trade['return_pct'] for trade in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    
    # Basic metrics
    total_trades = len(trades)
    win_rate = len(wins) / total_trades * 100
    avg_return = np.mean(returns)
    
    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    
    # Drawdown calculation
    cumulative_returns = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdowns = running_max - cumulative_returns
    max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
    
    # Exit reason rates
    exit_reasons = [trade['exit_reason'] for trade in trades]
    stop_loss_rate = exit_reasons.count('stop_loss') / total_trades * 100
    take_profit_rate = exit_reasons.count('take_profit') / total_trades * 100
    signal_reversal_rate = exit_reasons.count('signal_reversal') / total_trades * 100
    
    # Holding periods
    avg_holding_periods = np.mean([trade['holding_periods'] for trade in trades])
    
    # Consecutive losses
    loss_streaks = []
    current_streak = 0
    for r in returns:
        if r <= 0:
            current_streak += 1
        else:
            if current_streak > 0:
                loss_streaks.append(current_streak)
            current_streak = 0
    if current_streak > 0:
        loss_streaks.append(current_streak)
    max_consecutive_losses = max(loss_streaks) if loss_streaks else 0
    
    # Sharpe ratio
    if len(returns) > 1:
        sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
    else:
        sharpe_ratio = 0
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'avg_return': avg_return,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'avg_holding_periods': avg_holding_periods,
        'stop_loss_rate': stop_loss_rate,
        'take_profit_rate': take_profit_rate,
        'signal_reversal_rate': signal_reversal_rate,
        'max_consecutive_losses': max_consecutive_losses,
        'sharpe_ratio': sharpe_ratio
    }

# Alternative Strategy 1: RSI Mean Reversion (Long)
def rsi_mean_reversion_long(df, stop_loss_pct=0.02, take_profit_pct=0.04):
    """RSI oversold mean reversion strategy (long positions)"""
    trades = []
    
    for i in range(1, len(df)):
        sig = df.iloc[i]
        prev_sig = df.iloc[i-1]
        
        # Entry: RSI oversold (<30) with volume confirmation
        if (sig['rsi'] < 30 and 
            sig['volume_ratio'] > 1.2 and  # High volume
            sig['close'] < sig['sma200_4h']):  # Below SMA (oversold)
            
            entry_price = sig['close']
            outcome = simulate_trade(df, i, entry_price, stop_loss_pct, take_profit_pct, 20, is_long=True)
            
            if outcome:
                trades.append({
                    'entry_time': sig['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods']
                })
    
    return trades

# Alternative Strategy 2: Bollinger Band Mean Reversion (Long)
def bollinger_band_reversion_long(df, stop_loss_pct=0.02, take_profit_pct=0.04):
    """Bollinger Band mean reversion strategy (long positions)"""
    trades = []
    
    for i in range(1, len(df)):
        sig = df.iloc[i]
        prev_sig = df.iloc[i-1]
        
        # Entry: Price touches lower Bollinger Band with volume spike
        if (sig['close'] <= sig['bb_lower'] and 
            sig['volume_ratio'] > 1.5 and  # Strong volume
            sig['rsi'] < 35):  # Oversold confirmation
            
            entry_price = sig['close']
            outcome = simulate_trade(df, i, entry_price, stop_loss_pct, take_profit_pct, 20, is_long=True)
            
            if outcome:
                trades.append({
                    'entry_time': sig['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods']
                })
    
    return trades

# Alternative Strategy 3: Moving Average Crossover (Long)
def ma_crossover_long(df, stop_loss_pct=0.02, take_profit_pct=0.04):
    """Moving average crossover strategy (long positions)"""
    trades = []
    
    # Calculate short-term MA
    df['ma50'] = df['close'].rolling(window=50).mean()
    
    for i in range(51, len(df)):  # Need 50 periods for MA50
        sig = df.iloc[i]
        prev_sig = df.iloc[i-1]
        
        # Entry: Golden cross (MA50 crosses above SMA200)
        if (prev_sig['ma50'] <= prev_sig['sma200_4h'] and 
            sig['ma50'] > sig['sma200_4h'] and
            sig['adx'] > 20 and  # Trend strength
            sig['volume_ratio'] > 1.0):  # Volume confirmation
            
            entry_price = sig['close']
            outcome = simulate_trade(df, i, entry_price, stop_loss_pct, take_profit_pct, 20, is_long=True)
            
            if outcome:
                trades.append({
                    'entry_time': sig['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods']
                })
    
    return trades

# Alternative Strategy 4: ATR Breakout (Long)
def atr_breakout_long(df, stop_loss_pct=0.02, take_profit_pct=0.06):
    """ATR-based breakout strategy (long positions)"""
    trades = []
    
    for i in range(15, len(df)):  # Need ATR calculation
        sig = df.iloc[i]
        prev_sig = df.iloc[i-1]
        
        # Entry: Price breaks above recent high with ATR confirmation
        recent_high = df['high'].iloc[i-10:i].max()
        atr_multiplier = 1.5
        breakout_level = recent_high + (sig['atr'] * atr_multiplier)
        
        if (sig['close'] > breakout_level and
            sig['volume_ratio'] > 1.5 and  # Strong volume
            sig['rsi'] > 50 and  # Not oversold
            sig['adx'] > 25):  # Strong trend
            
            entry_price = sig['close']
            # Use tighter stop loss for breakout
            outcome = simulate_trade(df, i, entry_price, stop_loss_pct, take_profit_pct, 15, is_long=True)
            
            if outcome:
                trades.append({
                    'entry_time': sig['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods']
                })
    
    return trades

# Alternative Strategy 5: Volume-Weighted Reversal (Long)
def volume_reversal_long(df, stop_loss_pct=0.02, take_profit_pct=0.04):
    """Volume-weighted reversal strategy (long positions)"""
    trades = []
    
    for i in range(1, len(df)):
        sig = df.iloc[i]
        prev_sig = df.iloc[i-1]
        
        # Entry: High volume reversal after downtrend
        if (sig['volume_ratio'] > 2.0 and  # Very high volume
            sig['close'] > prev_sig['close'] and  # Price reversal
            prev_sig['close'] < prev_sig['sma200_4h'] and  # Was below SMA
            sig['rsi'] < 40 and  # Still oversold
            len(df) > 50):  # Check if we have enough data for volatility calculation
            
            # Calculate volatility mean safely
            volatility_mean = df['volatility'].iloc[:i].mean() if i > 50 else sig['volatility']
            
            if sig['volatility'] > volatility_mean:  # High volatility
                entry_price = sig['close']
                outcome = simulate_trade(df, i, entry_price, stop_loss_pct, take_profit_pct, 20, is_long=True)
                
                if outcome:
                    trades.append({
                        'entry_time': sig['timestamp'],
                        'entry_price': entry_price,
                        'exit_time': outcome['exit_time'],
                        'exit_price': outcome['exit_price'],
                        'exit_reason': outcome['exit_reason'],
                        'return_pct': outcome['return_pct'],
                        'holding_periods': outcome['holding_periods']
                    })
    
    return trades

def test_alternative_strategies():
    """Test all alternative strategies across all periods"""
    print("🚀 ALTERNATIVE STRATEGY DISCOVERY")
    print("=" * 80)
    
    strategies = {
        'RSI Mean Reversion (Long)': rsi_mean_reversion_long,
        'Bollinger Band Reversion (Long)': bollinger_band_reversion_long,
        'MA Crossover (Long)': ma_crossover_long,
        'ATR Breakout (Long)': atr_breakout_long,
        'Volume Reversal (Long)': volume_reversal_long
    }
    
    results = {}
    
    for strategy_name, strategy_func in strategies.items():
        print(f"\n📊 Testing {strategy_name}")
        print("-" * 60)
        
        strategy_results = {}
        all_trades = []
        
        for period_name, period_info in EXTENDED_PERIODS.items():
            period_trades = []
            
            for symbol in SYMBOLS:
                df = load_historical_data(symbol, period_name)
                if df.empty:
                    continue
                
                # Calculate extended indicators
                df_ind = calculate_extended_indicators(df)
                
                # Test strategy
                trades = strategy_func(df_ind)
                period_trades.extend(trades)
            
            if period_trades:
                metrics = calculate_risk_metrics(period_trades)
                strategy_results[period_name] = metrics
                all_trades.extend(period_trades)
                
                print(f"  {period_name}: {metrics['total_trades']} trades, "
                      f"Win Rate {metrics['win_rate']:.1f}%, "
                      f"Profit Factor {metrics['profit_factor']:.2f}")
        
        # Overall metrics
        if all_trades:
            overall_metrics = calculate_risk_metrics(all_trades)
            results[strategy_name] = {
                'period_results': strategy_results,
                'overall': overall_metrics
            }
            
            print(f"  OVERALL: {overall_metrics['total_trades']} trades, "
                  f"Win Rate {overall_metrics['win_rate']:.1f}%, "
                  f"Profit Factor {overall_metrics['profit_factor']:.2f}, "
                  f"Sharpe {overall_metrics['sharpe_ratio']:.2f}")
        else:
            print(f"  ❌ No trades generated")
    
    return results

def rank_strategies(results):
    """Rank strategies by performance"""
    print("\n" + "=" * 80)
    print("🏆 STRATEGY RANKING")
    print("=" * 80)
    
    strategy_rankings = []
    
    for strategy_name, data in results.items():
        overall = data.get('overall', {})
        if not overall or overall['total_trades'] < 10:
            continue
        
        # Score based on multiple factors
        score = (overall['win_rate'] * 0.3 + 
                overall['profit_factor'] * 30 + 
                overall['sharpe_ratio'] * 20 - 
                overall['max_drawdown'] * 0.5)
        
        strategy_rankings.append({
            'name': strategy_name,
            'score': score,
            'win_rate': overall['win_rate'],
            'profit_factor': overall['profit_factor'],
            'sharpe_ratio': overall['sharpe_ratio'],
            'max_drawdown': overall['max_drawdown'],
            'total_trades': overall['total_trades']
        })
    
    # Sort by score
    strategy_rankings.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n📊 RANKED STRATEGIES:")
    for i, strategy in enumerate(strategy_rankings, 1):
        print(f"  {i}. {strategy['name']}")
        print(f"     Score: {strategy['score']:.1f}")
        print(f"     Win Rate: {strategy['win_rate']:.1f}%, "
              f"Profit Factor: {strategy['profit_factor']:.2f}, "
              f"Sharpe: {strategy['sharpe_ratio']:.2f}")
        print(f"     Max Drawdown: {strategy['max_drawdown']:.1f}%, "
              f"Trades: {strategy['total_trades']}")
        print()
    
    return strategy_rankings

def main():
    """Main alternative strategy discovery function"""
    print("🔍 PHASE 1A: ALTERNATIVE STRATEGY DISCOVERY")
    print("=" * 80)
    
    try:
        # Test all alternative strategies
        results = test_alternative_strategies()
        
        # Rank strategies
        rankings = rank_strategies(results)
        
        print(f"🎉 PHASE 1A COMPLETE!")
        print(f"✅ Tested 5 alternative strategies across 4 market periods")
        print(f"✅ Identified promising candidates for further validation")
        
        if rankings:
            print(f"\n🏆 TOP 3 STRATEGIES FOR PHASE 1B:")
            for i, strategy in enumerate(rankings[:3], 1):
                print(f"  {i}. {strategy['name']} (Score: {strategy['score']:.1f})")
        
        return rankings
        
    except Exception as e:
        print(f"❌ Strategy discovery failed: {e}")
        return None

if __name__ == "__main__":
    rankings = main()
