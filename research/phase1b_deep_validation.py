#!/usr/bin/env python3
"""
Phase 1B: Deep Validation of Top 3 Strategies
Extended historical testing and walk-forward analysis
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators

# Top 3 strategies from Phase 1A
TOP_STRATEGIES = {
    'Volume Reversal (Long)': 'volume_reversal_long',
    'ATR Breakout (Long)': 'atr_breakout_long', 
    'RSI Mean Reversion (Long)': 'rsi_mean_reversion_long'
}

# Extended periods for comprehensive testing
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
    df_ind['ma50'] = df_ind['close'].rolling(window=50).mean()
    
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
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0
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
        
        # Sortino ratio (downside deviation)
        downside_returns = [r for r in returns if r < 0]
        downside_deviation = np.std(downside_returns) if len(downside_returns) > 1 else 0
        sortino_ratio = np.mean(returns) / downside_deviation if downside_deviation > 0 else 0
        
        # Calmar ratio (return / max drawdown)
        calmar_ratio = np.mean(returns) / max_drawdown if max_drawdown > 0 else 0
    else:
        sharpe_ratio = 0
        sortino_ratio = 0
        calmar_ratio = 0
    
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
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': calmar_ratio
    }

# Top 3 Strategy Implementations (copied from Phase 1A)

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

def walk_forward_analysis(df, strategy_func, window_size=100, step_size=50):
    """Perform walk-forward analysis on a strategy"""
    if len(df) < window_size + step_size:
        return []
    
    results = []
    
    for start_idx in range(0, len(df) - window_size, step_size):
        end_idx = start_idx + window_size
        
        # Training window
        train_df = df.iloc[start_idx:end_idx]
        
        # Test window (next step_size candles)
        test_start = end_idx
        test_end = min(test_start + step_size, len(df))
        
        if test_end <= test_start:
            continue
            
        test_df = df.iloc[test_start:test_end]
        
        # Test strategy on test window
        trades = strategy_func(test_df)
        
        if trades:
            metrics = calculate_risk_metrics(trades)
            results.append({
                'train_start': train_df.iloc[0]['timestamp'],
                'train_end': train_df.iloc[-1]['timestamp'],
                'test_start': test_df.iloc[0]['timestamp'],
                'test_end': test_df.iloc[-1]['timestamp'],
                'metrics': metrics,
                'trades': trades
            })
    
    return results

def monte_carlo_simulation(trades, num_simulations=1000):
    """Perform Monte Carlo simulation on trade results"""
    if not trades:
        return {}
    
    returns = [trade['return_pct'] for trade in trades]
    
    simulation_results = []
    
    for _ in range(num_simulations):
        # Randomly sample trades with replacement
        sampled_returns = np.random.choice(returns, size=len(returns), replace=True)
        
        # Calculate metrics for this simulation
        cumulative_return = np.sum(sampled_returns)
        win_rate = len([r for r in sampled_returns if r > 0]) / len(sampled_returns) * 100
        profit_factor = sum([r for r in sampled_returns if r > 0]) / abs(sum([r for r in sampled_returns if r <= 0])) if sum([r for r in sampled_returns if r <= 0]) != 0 else float('inf')
        
        # Drawdown
        cumulative_returns = np.cumsum(sampled_returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = running_max - cumulative_returns
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
        
        simulation_results.append({
            'cumulative_return': cumulative_return,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown
        })
    
    # Calculate confidence intervals
    cumulative_returns = [s['cumulative_return'] for s in simulation_results]
    win_rates = [s['win_rate'] for s in simulation_results]
    profit_factors = [s['profit_factor'] for s in simulation_results]
    max_drawdowns = [s['max_drawdown'] for s in simulation_results]
    
    return {
        'cumulative_return': {
            'mean': np.mean(cumulative_returns),
            'std': np.std(cumulative_returns),
            'percentile_5': np.percentile(cumulative_returns, 5),
            'percentile_95': np.percentile(cumulative_returns, 95)
        },
        'win_rate': {
            'mean': np.mean(win_rates),
            'std': np.std(win_rates),
            'percentile_5': np.percentile(win_rates, 5),
            'percentile_95': np.percentile(win_rates, 95)
        },
        'profit_factor': {
            'mean': np.mean(profit_factors),
            'std': np.std(profit_factors),
            'percentile_5': np.percentile(profit_factors, 5),
            'percentile_95': np.percentile(profit_factors, 95)
        },
        'max_drawdown': {
            'mean': np.mean(max_drawdowns),
            'std': np.std(max_drawdowns),
            'percentile_5': np.percentile(max_drawdowns, 5),
            'percentile_95': np.percentile(max_drawdowns, 95)
        }
    }

def deep_validate_strategy(strategy_name, strategy_func):
    """Perform deep validation on a single strategy"""
    print(f"\n🔍 DEEP VALIDATION: {strategy_name}")
    print("=" * 80)
    
    all_trades = []
    period_results = {}
    
    # Collect all trades across periods
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
            period_results[period_name] = metrics
            all_trades.extend(period_trades)
            
            print(f"  {period_name}: {metrics['total_trades']} trades, "
                  f"Win Rate {metrics['win_rate']:.1f}%, "
                  f"Profit Factor {metrics['profit_factor']:.2f}")
    
    # Overall metrics
    if all_trades:
        overall_metrics = calculate_risk_metrics(all_trades)
        
        print(f"\n📊 OVERALL PERFORMANCE:")
        print(f"  Total Trades: {overall_metrics['total_trades']}")
        print(f"  Win Rate: {overall_metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {overall_metrics['profit_factor']:.2f}")
        print(f"  Average Return: {overall_metrics['avg_return']:.2f}%")
        print(f"  Max Drawdown: {overall_metrics['max_drawdown']:.1f}%")
        print(f"  Sharpe Ratio: {overall_metrics['sharpe_ratio']:.2f}")
        print(f"  Sortino Ratio: {overall_metrics['sortino_ratio']:.2f}")
        print(f"  Calmar Ratio: {overall_metrics['calmar_ratio']:.2f}")
        print(f"  Max Consecutive Losses: {overall_metrics['max_consecutive_losses']}")
        
        # Monte Carlo simulation
        print(f"\n🎲 MONTE CARLO SIMULATION (1000 iterations):")
        mc_results = monte_carlo_simulation(all_trades)
        
        print(f"  Cumulative Return: {mc_results['cumulative_return']['mean']:.2f}% "
              f"(±{mc_results['cumulative_return']['std']:.2f}%)")
        print(f"    95% CI: [{mc_results['cumulative_return']['percentile_5']:.2f}%, "
              f"{mc_results['cumulative_return']['percentile_95']:.2f}%]")
        
        print(f"  Win Rate: {mc_results['win_rate']['mean']:.1f}% "
              f"(±{mc_results['win_rate']['std']:.1f}%)")
        print(f"    95% CI: [{mc_results['win_rate']['percentile_5']:.1f}%, "
              f"{mc_results['win_rate']['percentile_95']:.1f}%]")
        
        print(f"  Profit Factor: {mc_results['profit_factor']['mean']:.2f} "
              f"(±{mc_results['profit_factor']['std']:.2f})")
        print(f"    95% CI: [{mc_results['profit_factor']['percentile_5']:.2f}, "
              f"{mc_results['profit_factor']['percentile_95']:.2f}]")
        
        print(f"  Max Drawdown: {mc_results['max_drawdown']['mean']:.1f}% "
              f"(±{mc_results['max_drawdown']['std']:.1f}%)")
        print(f"    95% CI: [{mc_results['max_drawdown']['percentile_5']:.1f}%, "
              f"{mc_results['max_drawdown']['percentile_95']:.1f}%]")
        
        # Walk-forward analysis on largest dataset
        print(f"\n🚶 WALK-FORWARD ANALYSIS:")
        walk_forward_results = []
        
        for symbol in SYMBOLS:
            df = load_historical_data(symbol, 'recent_period')  # Use most recent data
            if df.empty:
                continue
            
            df_ind = calculate_extended_indicators(df)
            wf_results = walk_forward_analysis(df_ind, strategy_func)
            walk_forward_results.extend(wf_results)
        
        if walk_forward_results:
            wf_win_rates = [r['metrics']['win_rate'] for r in walk_forward_results if r['metrics']['total_trades'] > 0]
            wf_profit_factors = [r['metrics']['profit_factor'] for r in walk_forward_results if r['metrics']['total_trades'] > 0]
            
            if wf_win_rates:
                print(f"  Walk-forward windows: {len(walk_forward_results)}")
                print(f"  Average Win Rate: {np.mean(wf_win_rates):.1f}% (±{np.std(wf_win_rates):.1f}%)")
                print(f"  Average Profit Factor: {np.mean(wf_profit_factors):.2f} (±{np.std(wf_profit_factors):.2f})")
                print(f"  Consistency: {len([wr for wr in wf_win_rates if wr > 50])}/{len(wf_win_rates)} windows profitable")
        
        return {
            'strategy_name': strategy_name,
            'overall_metrics': overall_metrics,
            'period_results': period_results,
            'monte_carlo': mc_results,
            'walk_forward': walk_forward_results
        }
    else:
        print(f"  ❌ No trades generated")
        return None

def final_strategy_ranking(validation_results):
    """Rank strategies based on deep validation results"""
    print("\n" + "=" * 80)
    print("🏆 FINAL STRATEGY RANKING")
    print("=" * 80)
    
    strategy_scores = []
    
    for result in validation_results:
        if not result:
            continue
            
        metrics = result['overall_metrics']
        mc = result['monte_carlo']
        
        # Comprehensive scoring based on multiple factors
        score = 0
        
        # Base performance metrics (40% weight)
        score += metrics['win_rate'] * 0.15
        score += metrics['profit_factor'] * 15
        score += metrics['sharpe_ratio'] * 10
        
        # Risk metrics (30% weight)
        score -= metrics['max_drawdown'] * 0.5
        score += (100 - metrics['max_consecutive_losses']) * 0.1
        
        # Monte Carlo consistency (20% weight)
        score += mc['win_rate']['mean'] * 0.1
        score += mc['profit_factor']['mean'] * 5
        score -= mc['max_drawdown']['mean'] * 0.1
        
        # Trade frequency (10% weight) - prefer reasonable frequency
        if metrics['total_trades'] < 10:
            score -= 20  # Too few trades
        elif metrics['total_trades'] > 500:
            score -= 10  # Too many trades
        else:
            score += 10  # Good frequency
        
        strategy_scores.append({
            'name': result['strategy_name'],
            'score': score,
            'win_rate': metrics['win_rate'],
            'profit_factor': metrics['profit_factor'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'total_trades': metrics['total_trades'],
            'mc_win_rate': mc['win_rate']['mean'],
            'mc_profit_factor': mc['profit_factor']['mean'],
            'mc_max_drawdown': mc['max_drawdown']['mean']
        })
    
    # Sort by score
    strategy_scores.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n📊 FINAL RANKINGS:")
    for i, strategy in enumerate(strategy_scores, 1):
        print(f"  {i}. {strategy['name']}")
        print(f"     Score: {strategy['score']:.1f}")
        print(f"     Performance: Win Rate {strategy['win_rate']:.1f}%, "
              f"Profit Factor {strategy['profit_factor']:.2f}, "
              f"Sharpe {strategy['sharpe_ratio']:.2f}")
        print(f"     Risk: Max DD {strategy['max_drawdown']:.1f}%, "
              f"Trades {strategy['total_trades']}")
        print(f"     Monte Carlo: Win Rate {strategy['mc_win_rate']:.1f}%, "
              f"Profit Factor {strategy['mc_profit_factor']:.2f}, "
              f"Max DD {strategy['mc_max_drawdown']:.1f}%")
        print()
    
    return strategy_scores

def main():
    """Main deep validation function"""
    print("🔍 PHASE 1B: DEEP VALIDATION")
    print("=" * 80)
    
    # Strategy functions
    strategies = {
        'Volume Reversal (Long)': volume_reversal_long,
        'ATR Breakout (Long)': atr_breakout_long,
        'RSI Mean Reversion (Long)': rsi_mean_reversion_long
    }
    
    validation_results = []
    
    # Deep validate each strategy
    for strategy_name, strategy_func in strategies.items():
        result = deep_validate_strategy(strategy_name, strategy_func)
        validation_results.append(result)
    
    # Final ranking
    rankings = final_strategy_ranking(validation_results)
    
    print(f"🎉 PHASE 1B COMPLETE!")
    print(f"✅ Deep validation completed for top 3 strategies")
    print(f"✅ Monte Carlo simulation and walk-forward analysis performed")
    
    if rankings:
        print(f"\n🏆 RECOMMENDED STRATEGY:")
        print(f"  {rankings[0]['name']} (Score: {rankings[0]['score']:.1f})")
        
        # Check if top strategy meets minimum criteria
        top = rankings[0]
        meets_criteria = (
            top['win_rate'] > 55 and
            top['profit_factor'] > 1.5 and
            top['max_drawdown'] < 25 and
            top['sharpe_ratio'] > 0.5
        )
        
        if meets_criteria:
            print(f"✅ MEETS ALL DEPLOYMENT CRITERIA")
            print(f"🚀 READY FOR PHASE 1C: STRATEGY SELECTION")
        else:
            print(f"⚠️ DOES NOT MEET ALL CRITERIA")
            print(f"🔄 CONSIDER STRATEGY REFINEMENT")
    
    return rankings

if __name__ == "__main__":
    rankings = main()
