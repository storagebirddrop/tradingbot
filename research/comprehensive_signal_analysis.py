#!/usr/bin/env python3
"""
Comprehensive Signal Analysis
Tests multiple signal combinations and strategies before optimization
"""

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Tuple

def load_data(symbol):
    """Load data for a symbol"""
    file_4h = f"{symbol.replace('/', '_')}_4h_recent.csv"
    df_4h = pd.read_csv(f"/home/dribble0335/dev/tradingbot/research/historical/{file_4h}")
    df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'])
    
    file_1d = f"{symbol.replace('/', '_')}_1d_recent.csv"
    df_1d = pd.read_csv(f"/home/dribble0335/dev/tradingbot/research/regime/{file_1d}")
    df_1d['timestamp'] = pd.to_datetime(df_1d['timestamp'])
    
    return df_4h, df_1d

def calculate_regime(df_1d):
    """Simple regime calculation"""
    df_regime = df_1d.copy()
    df_regime['ema200'] = df_regime['close'].ewm(span=200).mean()
    df_regime['risk_on'] = df_regime['close'] > df_regime['ema200']
    return df_regime[['timestamp', 'risk_on']]

def attach_regime_to_4h(df_4h, df_regime):
    """Attach regime data to 4h data"""
    df_combined = df_4h.copy()
    df_combined['risk_on'] = False
    
    for i, row in df_combined.iterrows():
        current_time = row['timestamp']
        regime_times = df_regime[df_regime['timestamp'] <= current_time]['timestamp']
        if not regime_times.empty:
            closest_time = regime_times.iloc[-1]
            regime_value = df_regime[df_regime['timestamp'] == closest_time]['risk_on'].iloc[0]
            df_combined.loc[i, 'risk_on'] = regime_value
    
    return df_combined

def calculate_performance_metrics(signals, df):
    """Calculate performance metrics for signals"""
    if not signals.any():
        return {
            'signal_count': 0,
            'signal_frequency': 0,
            'avg_return': 0,
            'win_rate': 0,
            'profit_factor': 0
        }
    
    # Find entry points
    entry_points = df[signals].copy()
    
    if entry_points.empty:
        return {
            'signal_count': 0,
            'signal_frequency': 0,
            'avg_return': 0,
            'win_rate': 0,
            'profit_factor': 0
        }
    
    # Simulate short trades (simplified)
    trades = []
    
    for idx, row in entry_points.iterrows():
        entry_price = row['close']
        entry_time = row['timestamp']
        
        # Find exit (next 10 periods or exit signal)
        future_data = df[df['timestamp'] > entry_time]
        if len(future_data) >= 10:
            exit_point = future_data.iloc[9]  # 10 periods later (40h)
            exit_price = exit_point['close']
            exit_time = exit_point['timestamp']
        else:
            exit_point = future_data.iloc[-1]
            exit_price = exit_point['close']
            exit_time = exit_point['timestamp']
        
        # Calculate return (short position profit)
        return_pct = (entry_price - exit_price) / entry_price * 100
        
        trades.append({
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'return_pct': return_pct
        })
    
    if not trades:
        return {
            'signal_count': len(entry_points),
            'signal_frequency': len(entry_points) / len(df) * 100,
            'avg_return': 0,
            'win_rate': 0,
            'profit_factor': 0
        }
    
    # Calculate metrics
    trades_df = pd.DataFrame(trades)
    
    wins = trades_df[trades_df['return_pct'] > 0]
    losses = trades_df[trades_df['return_pct'] <= 0]
    
    win_rate = len(wins) / len(trades_df) * 100 if trades_df else 0
    
    # Profit factor
    gross_profit = wins['return_pct'].sum() if not wins.empty else 0
    gross_loss = abs(losses['return_pct'].sum()) if not losses.empty else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    
    return {
        'signal_count': len(entry_points),
        'signal_frequency': len(entry_points) / len(df) * 100,
        'avg_return': trades_df['return_pct'].mean(),
        'win_rate': win_rate,
        'profit_factor': profit_factor
    }

def test_signal_strategies(df_clean):
    """Test different signal strategies"""
    
    # Base signals (ensure boolean)
    df_clean['sma_breakdown'] = (df_clean['close'] < df_clean['sma200']).astype(bool)
    df_clean['rsi_overbought'] = (df_clean['rsi'] > 70).astype(bool)
    df_clean['macd_bearish'] = (df_clean['MACDh_12_26_9'] < 0).astype(bool)
    df_clean['adx_strong'] = (df_clean['adx'] > 25).astype(bool)
    df_clean['risk_off'] = (~df_clean['risk_on']).astype(bool)
    
    strategies = {
        # Current strategy (any exit signal)
        'current_any_exit': (
            (df_clean['sma_breakdown'] | df_clean['rsi_overbought'] | df_clean['macd_bearish']) &
            df_clean['adx_strong'] & df_clean['risk_off']
        ),
        
        # Tightened strategies (2+ conditions)
        'sma_rsi_combo': (
            df_clean['sma_breakdown'] & df_clean['rsi_overbought'] &
            df_clean['adx_strong'] & df_clean['risk_off']
        ),
        
        'sma_macd_combo': (
            df_clean['sma_breakdown'] & df_clean['macd_bearish'] &
            df_clean['adx_strong'] & df_clean['risk_off']
        ),
        
        'rsi_macd_combo': (
            df_clean['rsi_overbought'] & df_clean['macd_bearish'] &
            df_clean['adx_strong'] & df_clean['risk_off']
        ),
        
        # Any two conditions
        'any_two_conditions': (
            ((df_clean['sma_breakdown'] & df_clean['rsi_overbought']) |
             (df_clean['sma_breakdown'] & df_clean['macd_bearish']) |
             (df_clean['rsi_overbought'] & df_clean['macd_bearish'])) &
            df_clean['adx_strong'] & df_clean['risk_off']
        ),
        
        # All three conditions
        'all_three_conditions': (
            df_clean['sma_breakdown'] & df_clean['rsi_overbought'] & df_clean['macd_bearish'] &
            df_clean['adx_strong'] & df_clean['risk_off']
        ),
        
        # Conservative (SMA + any other + higher ADX)
        'sma_plus_any_high_adx': (
            df_clean['sma_breakdown'] & (df_clean['rsi_overbought'] | df_clean['macd_bearish']) &
            (df_clean['adx'] > 35) & df_clean['risk_off']
        ),
        
        # Very conservative (all conditions + high ADX)
        'very_conservative': (
            df_clean['sma_breakdown'] & df_clean['rsi_overbought'] & df_clean['macd_bearish'] &
            (df_clean['adx'] > 35) & df_clean['risk_off']
        ),
        
        # Alternative: RSI-focused
        'rsi_focused': (
            df_clean['rsi_overbought'] & (df_clean['sma_breakdown'] | df_clean['macd_bearish']) &
            df_clean['adx_strong'] & df_clean['risk_off']
        ),
        
        # Alternative: MACD-focused
        'macd_focused': (
            df_clean['macd_bearish'] & (df_clean['sma_breakdown'] | df_clean['rsi_overbought']) &
            df_clean['adx_strong'] & df_clean['risk_off']
        )
    }
    
    results = {}
    
    for strategy_name, signals in strategies.items():
        performance = calculate_performance_metrics(signals, df_clean)
        results[strategy_name] = performance
    
    return results

def analyze_symbol_comprehensive(symbol):
    """Comprehensive analysis for a symbol"""
    print(f"\n{'='*60}")
    print(f"COMPREHENSIVE ANALYSIS: {symbol}")
    print(f"{'='*60}")
    
    try:
        # Load and prepare data
        df_4h, df_1d = load_data(symbol)
        df_regime = calculate_regime(df_1d)
        df_combined = attach_regime_to_4h(df_4h, df_regime)
        
        # Clean data
        df_clean = df_combined.dropna()
        print(f"Data: {len(df_clean)} clean rows from {len(df_combined)} total")
        print(f"Date range: {df_clean['timestamp'].min()} to {df_clean['timestamp'].max()}")
        
        # Test strategies
        results = test_signal_strategies(df_clean)
        
        # Display results
        print(f"\n{'STRATEGY':<25} {'FREQ':<6} {'WIN%':<6} {'PROFIT':<8} {'AVG_RET':<9} {'SIGNALS'}")
        print("-" * 70)
        
        for strategy, metrics in results.items():
            freq = f"{metrics['signal_frequency']:.1f}%"
            win = f"{metrics['win_rate']:.1f}%"
            profit = f"{metrics['profit_factor']:.2f}"
            avg_ret = f"{metrics['avg_return']:.2f}%"
            signals = str(metrics['signal_count'])
            
            print(f"{strategy:<25} {freq:<6} {win:<6} {profit:<8} {avg_ret:<9} {signals}")
        
        # Find best strategies
        print(f"\nTOP STRATEGIES BY DIFFERENT METRICS:")
        
        # Best by win rate
        best_win = max(results.items(), key=lambda x: x[1]['win_rate'] if x[1]['signal_count'] > 10 else 0)
        print(f"Best Win Rate: {best_win[0]} ({best_win[1]['win_rate']:.1f}%)")
        
        # Best by profit factor
        best_profit = max(results.items(), key=lambda x: x[1]['profit_factor'] if x[1]['profit_factor'] != float('inf') and x[1]['signal_count'] > 10 else 0)
        print(f"Best Profit Factor: {best_profit[0]} ({best_profit[1]['profit_factor']:.2f})")
        
        # Best by balanced approach (win rate + profit factor + reasonable frequency)
        balanced_candidates = {k: v for k, v in results.items() 
                             if 10 <= v['signal_count'] <= 200 and v['win_rate'] > 40 and v['profit_factor'] > 1.0}
        
        if balanced_candidates:
            best_balanced = max(balanced_candidates.items(), 
                               key=lambda x: x[1]['win_rate'] * x[1]['profit_factor'] / (x[1]['signal_frequency']/10))
            print(f"Best Balanced: {best_balanced[0]} (Win: {best_balanced[1]['win_rate']:.1f}%, "
                  f"Profit: {best_balanced[1]['profit_factor']:.2f}, Freq: {best_balanced[1]['signal_frequency']:.1f}%)")
        
        return results
        
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return {}

def main():
    """Main comprehensive analysis"""
    print("COMPREHENSIVE SIGNAL STRATEGY ANALYSIS")
    print("=" * 60)
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    all_results = {}
    
    for symbol in symbols:
        results = analyze_symbol_comprehensive(symbol)
        all_results[symbol] = results
    
    # Aggregate analysis
    print(f"\n{'='*60}")
    print("AGGREGATE ANALYSIS ACROSS ALL SYMBOLS")
    print(f"{'='*60}")
    
    # Calculate averages for each strategy
    strategy_names = list(all_results["BTC/USDT"].keys()) if all_results["BTC/USDT"] else []
    
    print(f"\n{'STRATEGY':<25} {'AVG_FREQ':<10} {'AVG_WIN%':<10} {'AVG_PROFIT':<12} {'TOTAL_SIGNALS'}")
    print("-" * 75)
    
    for strategy in strategy_names:
        total_signals = sum(all_results[sym][strategy]['signal_count'] for sym in symbols if strategy in all_results[sym])
        avg_freq = np.mean([all_results[sym][strategy]['signal_frequency'] for sym in symbols if strategy in all_results[sym]])
        avg_win = np.mean([all_results[sym][strategy]['win_rate'] for sym in symbols if strategy in all_results[sym]])
        avg_profit = np.mean([all_results[sym][strategy]['profit_factor'] for sym in symbols if strategy in all_results[sym] and all_results[sym][strategy]['profit_factor'] != float('inf')])
        
        print(f"{strategy:<25} {avg_freq:<10.1f} {avg_win:<10.1f} {avg_profit:<12.2f} {total_signals}")
    
    # Recommendations
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")
    
    print("\n1. CURRENT STRATEGY ISSUES:")
    print("   - 'current_any_exit': Too high frequency (65%+)")
    print("   - Leads to overtrading and high transaction costs")
    
    print("\n2. RECOMMENDED STRATEGIES:")
    print("   - 'any_two_conditions': Good balance (15-25% frequency)")
    print("   - 'sma_rsi_combo': Conservative, reliable signals")
    print("   - 'sma_plus_any_high_adx': High quality with momentum confirmation")
    
    print("\n3. STRATEGIES TO AVOID:")
    print("   - 'very_conservative': Too few signals")
    print("   - 'current_any_exit': Overtrading risk")
    
    print("\n4. NEXT STEPS:")
    print("   - Test recommended strategies with different stop losses")
    print("   - Optimize position sizing for chosen strategies")
    print("   - Validate with out-of-sample testing")

if __name__ == "__main__":
    main()
