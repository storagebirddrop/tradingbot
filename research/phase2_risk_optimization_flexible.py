#!/usr/bin/env python3
"""
Phase 2: Risk Parameter Optimization (Flexible Strategy)
Optimizes parameters with flexible strategy conditions
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators

# Market periods and symbols for testing
MARKET_PERIODS = {
    'covid_crash': {'description': 'COVID crash & recovery', 'volatility': 'extreme'},
    'bull_peak_bear': {'description': 'Bull peak to bear transition', 'volatility': 'high'},
    'recovery_period': {'description': 'Post-bear recovery', 'volatility': 'moderate'},
    'recent_period': {'description': 'Recent risk-off', 'volatility': 'moderate'}
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

def flexible_sma_rsi_signal(sig, prev_sig, rsi_threshold=70, adx_threshold=25):
    """Flexible version of sma_rsi_combo_signal with adjustable thresholds"""
    return (
        sig["close"] < sig["sma200_4h"]  # Short entry (below SMA)
        and sig["adx"] > adx_threshold
        and sig["rsi"] > rsi_threshold  # Overbought for short
        and not sig.get("risk_on", True)  # Risk-off condition
    )

def calculate_trade_outcomes(df, stop_loss_pct, take_profit_pct, max_holding_periods=20, 
                           rsi_threshold=70, adx_threshold=25):
    """Calculate trade outcomes with given risk parameters"""
    if df.empty:
        return []
    
    # Calculate indicators
    df_ind = compute_4h_indicators(df)
    
    trades = []
    
    for i in range(1, len(df_ind)):
        sig = df_ind.iloc[i]
        prev_sig = df_ind.iloc[i-1]
        
        # Check for entry signal with flexible parameters
        if flexible_sma_rsi_signal(sig, prev_sig, rsi_threshold, adx_threshold):
            entry_price = sig['close']
            entry_time = sig['timestamp']
            
            # Simulate trade execution
            outcome = simulate_trade(df_ind, i, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods)
            
            if outcome:
                trades.append({
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods']
                })
    
    return trades

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods):
    """Simulate a single trade with risk parameters"""
    stop_loss_price = entry_price * (1 - stop_loss_pct)
    take_profit_price = entry_price * (1 + take_profit_pct)
    
    for j in range(entry_idx + 1, min(entry_idx + max_holding_periods + 1, len(df))):
        current_candle = df.iloc[j]
        current_price = current_candle['close']
        
        # Check stop loss
        if current_price <= stop_loss_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': stop_loss_price,
                'exit_reason': 'stop_loss',
                'return_pct': -stop_loss_pct,
                'holding_periods': j - entry_idx
            }
        
        # Check take profit
        if current_price >= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct,
                'holding_periods': j - entry_idx
            }
        
        # Check signal reversal (additional exit condition)
        if j > entry_idx + 1:  # Allow at least 1 period
            sig = current_candle
            prev_sig = df.iloc[j-1]
            
            # Exit if signal reverses (RSI drops below 30 or price crosses above SMA)
            if sig['rsi'] < 30 or sig['close'] > sig['sma200_4h']:
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (entry_price - current_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
    
    # Max holding period reached
    final_price = df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['close']
    return {
        'exit_time': df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['timestamp'],
        'exit_price': final_price,
        'exit_reason': 'max_holding',
        'return_pct': (entry_price - final_price) / entry_price * 100,
        'holding_periods': max_holding_periods
    }

def calculate_risk_metrics(trades):
    """Calculate comprehensive risk metrics for trade results"""
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
    
    # Sharpe ratio (simplified)
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

def test_strategy_parameters():
    """Test different strategy parameter combinations"""
    print("🔍 TESTING STRATEGY PARAMETER COMBINATIONS")
    print("=" * 60)
    
    # Test different RSI and ADX thresholds
    rsi_options = [65, 70, 75]  # More flexible RSI thresholds
    adx_options = [20, 25, 30]  # More flexible ADX thresholds
    
    stop_loss_pct = 0.02  # Fixed 2% stop loss
    take_profit_pct = 0.04  # Fixed 4% take profit
    max_holding_periods = 20
    
    results = {}
    
    for rsi_threshold in rsi_options:
        for adx_threshold in adx_options:
            print(f"\n📊 Testing RSI>{rsi_threshold}, ADX>{adx_threshold}")
            
            all_trades = []
            
            for period_name in MARKET_PERIODS.keys():
                for symbol in SYMBOLS:
                    df = load_historical_data(symbol, period_name)
                    if df.empty:
                        continue
                    
                    trades = calculate_trade_outcomes(df, stop_loss_pct, take_profit_pct, 
                                                   max_holding_periods, rsi_threshold, adx_threshold)
                    all_trades.extend(trades)
            
            if all_trades:
                metrics = calculate_risk_metrics(all_trades)
                key = f"rsi_{rsi_threshold}_adx_{adx_threshold}"
                results[key] = metrics
                
                print(f"  Total trades: {metrics['total_trades']}")
                print(f"  Win rate: {metrics['win_rate']:.1f}%")
                print(f"  Profit factor: {metrics['profit_factor']:.2f}")
                print(f"  Avg return: {metrics['avg_return']:.2f}%")
            else:
                print(f"  No trades generated")
    
    return results

def test_risk_parameters():
    """Test stop loss and take profit parameters with best strategy settings"""
    print("\n🔍 TESTING RISK PARAMETERS")
    print("=" * 60)
    
    # Use best strategy parameters from previous test (or defaults)
    rsi_threshold = 65  # More flexible
    adx_threshold = 20  # More flexible
    
    stop_loss_options = [0.015, 0.02, 0.025, 0.03]  # 1.5% to 3%
    take_profit_options = [0.03, 0.04, 0.05, 0.06]  # 3% to 6%
    max_holding_periods = 20
    
    results = {}
    
    for stop_loss_pct in stop_loss_options:
        for take_profit_pct in take_profit_options:
            print(f"\n📊 Testing SL:{stop_loss_pct*100:.1f}%, TP:{take_profit_pct*100:.1f}%")
            
            all_trades = []
            
            for period_name in MARKET_PERIODS.keys():
                for symbol in SYMBOLS:
                    df = load_historical_data(symbol, period_name)
                    if df.empty:
                        continue
                    
                    trades = calculate_trade_outcomes(df, stop_loss_pct, take_profit_pct, 
                                                   max_holding_periods, rsi_threshold, adx_threshold)
                    all_trades.extend(trades)
            
            if all_trades:
                metrics = calculate_risk_metrics(all_trades)
                key = f"sl_{stop_loss_pct*100:.1f}_tp_{take_profit_pct*100:.1f}"
                results[key] = metrics
                
                print(f"  Trades: {metrics['total_trades']}, Win Rate: {metrics['win_rate']:.1f}%")
                print(f"  Profit Factor: {metrics['profit_factor']:.2f}, Sharpe: {metrics['sharpe_ratio']:.2f}")
                print(f"  Stop Loss: {metrics['stop_loss_rate']:.1f}%, Take Profit: {metrics['take_profit_rate']:.1f}%")
            else:
                print(f"  No trades generated")
    
    return results

def generate_optimization_results(strategy_results, risk_results):
    """Generate final optimization recommendations"""
    print("\n" + "=" * 80)
    print("🎯 RISK PARAMETER OPTIMIZATION RESULTS")
    print("=" * 80)
    
    # Find best strategy parameters
    print("\n📊 STRATEGY PARAMETER ANALYSIS:")
    best_strategy = None
    best_strategy_score = -float('inf')
    
    for key, metrics in strategy_results.items():
        if metrics['total_trades'] < 10:  # Need minimum trades
            continue
            
        # Score based on win rate, profit factor, and trade frequency
        score = metrics['win_rate'] + (metrics['profit_factor'] * 10) + (metrics['total_trades'] * 0.1)
        
        print(f"  {key}: Win Rate {metrics['win_rate']:.1f}%, "
              f"Profit Factor {metrics['profit_factor']:.2f}, "
              f"Trades {metrics['total_trades']}, Score {score:.1f}")
        
        if score > best_strategy_score:
            best_strategy_score = score
            best_strategy = key
    
    # Find best risk parameters
    print("\n📊 RISK PARAMETER ANALYSIS:")
    best_risk = None
    best_risk_score = -float('inf')
    
    for key, metrics in risk_results.items():
        if metrics['total_trades'] < 10:  # Need minimum trades
            continue
            
        # Score based on Sharpe ratio and profit factor
        score = (metrics['sharpe_ratio'] * 10) + (metrics['profit_factor'] * 10)
        
        print(f"  {key}: Sharpe {metrics['sharpe_ratio']:.2f}, "
              f"Profit Factor {metrics['profit_factor']:.2f}, "
              f"Win Rate {metrics['win_rate']:.1f}%, Score {score:.1f}")
        
        if score > best_risk_score:
            best_risk_score = score
            best_risk = key
    
    # Extract best parameters
    if best_strategy:
        rsi_threshold = int(best_strategy.split('_')[1])
        adx_threshold = int(best_strategy.split('_')[3])
        print(f"\n✅ BEST STRATEGY PARAMETERS:")
        print(f"  RSI Threshold: >{rsi_threshold}")
        print(f"  ADX Threshold: >{adx_threshold}")
    else:
        rsi_threshold = 65
        adx_threshold = 20
        print(f"\n✅ DEFAULT STRATEGY PARAMETERS:")
        print(f"  RSI Threshold: >{rsi_threshold}")
        print(f"  ADX Threshold: >{adx_threshold}")
    
    if best_risk:
        stop_loss_pct = float(best_risk.split('_')[1]) / 100
        take_profit_pct = float(best_risk.split('_')[3]) / 100
        print(f"\n✅ BEST RISK PARAMETERS:")
        print(f"  Stop Loss: {stop_loss_pct*100:.1f}%")
        print(f"  Take Profit: {take_profit_pct*100:.1f}%")
    else:
        stop_loss_pct = 0.02
        take_profit_pct = 0.04
        print(f"\n✅ DEFAULT RISK PARAMETERS:")
        print(f"  Stop Loss: {stop_loss_pct*100:.1f}%")
        print(f"  Take Profit: {take_profit_pct*100:.1f}%")
    
    # Test final combination
    print(f"\n🔍 FINAL VALIDATION:")
    all_trades = []
    
    for period_name in MARKET_PERIODS.keys():
        for symbol in SYMBOLS:
            df = load_historical_data(symbol, period_name)
            if df.empty:
                continue
            
            trades = calculate_trade_outcomes(df, stop_loss_pct, take_profit_pct, 
                                           20, rsi_threshold, adx_threshold)
            all_trades.extend(trades)
    
    if all_trades:
        final_metrics = calculate_risk_metrics(all_trades)
        
        print(f"📊 FINAL PERFORMANCE METRICS:")
        print(f"  Total Trades: {final_metrics['total_trades']}")
        print(f"  Win Rate: {final_metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {final_metrics['profit_factor']:.2f}")
        print(f"  Average Return: {final_metrics['avg_return']:.2f}%")
        print(f"  Max Drawdown: {final_metrics['max_drawdown']:.1f}%")
        print(f"  Sharpe Ratio: {final_metrics['sharpe_ratio']:.2f}")
        print(f"  Max Consecutive Losses: {final_metrics['max_consecutive_losses']}")
        
        print(f"\n🔄 EXIT REASON BREAKDOWN:")
        print(f"  Stop Loss: {final_metrics['stop_loss_rate']:.1f}%")
        print(f"  Take Profit: {final_metrics['take_profit_rate']:.1f}%")
        print(f"  Signal Reversal: {final_metrics['signal_reversal_rate']:.1f}%")
        print(f"  Max Holding: {100 - final_metrics['stop_loss_rate'] - final_metrics['take_profit_rate'] - final_metrics['signal_reversal_rate']:.1f}%")
        
        print(f"\n🎯 FINAL RECOMMENDATIONS:")
        print(f"  Strategy: RSI>{rsi_threshold}, ADX>{adx_threshold}")
        print(f"  Stop Loss: {stop_loss_pct*100:.1f}%")
        print(f"  Take Profit: {take_profit_pct*100:.1f}%")
        print(f"  Risk Per Trade: 1.0% (conservative)")
        print(f"  Max Holding Period: 20 candles (80 hours)")
        print(f"  Expected Win Rate: {final_metrics['win_rate']:.1f}%")
        print(f"  Expected Profit Factor: {final_metrics['profit_factor']:.2f}")
        
        return {
            'rsi_threshold': rsi_threshold,
            'adx_threshold': adx_threshold,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'expected_metrics': final_metrics
        }
    else:
        print(f"❌ No trades generated with final parameters")
        return None

def main():
    """Main risk optimization function"""
    print("🚀 PHASE 2: RISK PARAMETER OPTIMIZATION (FLEXIBLE)")
    print("=" * 80)
    
    try:
        # Test strategy parameters
        strategy_results = test_strategy_parameters()
        
        # Test risk parameters
        risk_results = test_risk_parameters()
        
        # Generate recommendations
        recommendations = generate_optimization_results(strategy_results, risk_results)
        
        if recommendations:
            print(f"\n🎉 PHASE 2 COMPLETE!")
            print(f"✅ Risk parameters optimized with flexible strategy conditions")
            print(f"✅ Conservative approach with realistic signal generation")
            print(f"✅ Ready for Phase 3: Market Condition Analysis")
        else:
            print(f"\n⚠️ PHASE 2 PARTIAL!")
            print(f"✅ Analysis completed but no viable strategy found")
            print(f"✅ Consider further parameter relaxation or different strategy")
        
        return recommendations
        
    except Exception as e:
        print(f"❌ Risk optimization failed: {e}")
        return None

if __name__ == "__main__":
    recommendations = main()
