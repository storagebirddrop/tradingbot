#!/usr/bin/env python3
"""
Advanced Indicators Rapid Testing Framework
Tests multiple sophisticated indicators against sma_rsi_combo baseline
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

# Market periods and symbols
MARKET_PERIODS = {
    'covid_crash': {'description': 'COVID crash & recovery - extreme volatility'},
    'bull_peak_bear': {'description': 'Bull market peak & bear transition'},
    'recovery_period': {'description': 'Post-bear market recovery'},
    'recent_period': {'description': 'Recent risk-off period'}
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

def calculate_advanced_indicators(df):
    """Calculate all advanced indicators"""
    if df.empty:
        return df
    
    df_adv = df.copy()
    
    # 1. ImpulseMACD
    df_adv['impulse_macd'] = calculate_impulse_macd(df_adv['close'])
    
    # 2. LogarithmicMACD
    df_adv['log_macd'] = calculate_log_macd(df_adv['close'])
    
    # 3. OBV (On-Balance Volume)
    df_adv['obv'] = calculate_obv(df_adv['close'], df_adv['volume'])
    
    # 4. Bollinger Bands
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df_adv['close'])
    df_adv['bb_upper'] = bb_upper
    df_adv['bb_middle'] = bb_middle
    df_adv['bb_lower'] = bb_lower
    df_adv['bb_percent'] = (df_adv['close'] - bb_lower) / (bb_upper - bb_lower)
    
    # 5. Stochastic RSI
    df_adv['stoch_rsi'] = calculate_stochastic_rsi(df_adv['close'])
    
    return df_adv

def calculate_impulse_macd(close, fast=12, slow=26, signal=9):
    """Calculate ImpulseMACD - enhanced momentum indicator"""
    # Standard MACD
    exp1 = close.ewm(span=fast).mean()
    exp2 = close.ewm(span=slow).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line
    
    # Impulse component - rate of change of histogram
    impulse = histogram.diff()
    
    # Normalize impulse signal
    impulse_signal = (impulse > 0) & (histogram > 0)
    
    return impulse_signal.astype(int)

def calculate_log_macd(close, fast=12, slow=26, signal=9):
    """Calculate Logarithmic MACD for trending markets"""
    # Apply logarithmic transformation
    log_close = np.log(close)
    
    # Calculate MACD on log prices
    exp1 = log_close.ewm(span=fast).mean()
    exp2 = log_close.ewm(span=slow).mean()
    log_macd = exp1 - exp2
    signal_line = log_macd.ewm(span=signal).mean()
    histogram = log_macd - signal_line
    
    # Bearish signal (histogram turning negative)
    bearish_signal = (histogram < 0) & (histogram.diff() < 0)
    
    return bearish_signal.astype(int)

def calculate_obv(close, volume):
    """Calculate On-Balance Volume"""
    obv = []
    obv_value = 0
    
    for i in range(len(close)):
        if i == 0:
            obv_value = volume.iloc[i]
        else:
            if close.iloc[i] > close.iloc[i-1]:
                obv_value += volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv_value -= volume.iloc[i]
            # If equal, OBV doesn't change
        
        obv.append(obv_value)
    
    # OBV divergence signal (price up, OBV down = bearish divergence)
    obv_series = pd.Series(obv)
    price_up = close.diff() > 0
    obv_down = obv_series.diff() < 0
    bearish_divergence = price_up & obv_down
    
    return bearish_divergence.astype(int)

def calculate_bollinger_bands(close, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return upper, middle, lower

def calculate_stochastic_rsi(close, rsi_period=14, stoch_period=14, k_period=3):
    """Calculate Stochastic RSI"""
    # Calculate RSI first
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Calculate Stochastic of RSI
    rsi_min = rsi.rolling(window=stoch_period).min()
    rsi_max = rsi.rolling(window=stoch_period).max()
    stoch_rsi = ((rsi - rsi_min) / (rsi_max - rsi_min)) * 100
    
    # Smooth with %K
    stoch_k = stoch_rsi.rolling(window=k_period).mean()
    
    # Overbought signal (Stoch RSI > 80)
    overbought_signal = stoch_k > 80
    
    return overbought_signal.astype(int)

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
    
    # Simulate short trades
    trades = []
    
    for idx, row in entry_points.iterrows():
        entry_price = row['close']
        
        # Find exit (next 10 periods or end of data)
        current_idx = df.index.get_loc(idx)
        if current_idx + 10 < len(df):
            exit_point = df.iloc[current_idx + 10]
        else:
            exit_point = df.iloc[-1]
        
        exit_price = exit_point['close']
        return_pct = (entry_price - exit_price) / entry_price * 100
        
        trades.append(return_pct)
    
    if not trades:
        return {
            'signal_count': len(entry_points),
            'signal_frequency': len(entry_points) / len(df) * 100,
            'avg_return': 0,
            'win_rate': 0,
            'profit_factor': 0
        }
    
    # Calculate metrics
    trades_series = pd.Series(trades)
    
    wins = trades_series[trades_series > 0]
    losses = trades_series[trades_series <= 0]
    
    win_rate = len(wins) / len(trades_series) * 100 if len(trades_series) > 0 else 0
    
    # Profit factor
    gross_profit = wins.sum() if not wins.empty else 0
    gross_loss = abs(losses.sum()) if not losses.empty else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    
    return {
        'signal_count': len(entry_points),
        'signal_frequency': len(entry_points) / len(df) * 100,
        'avg_return': trades_series.mean(),
        'win_rate': win_rate,
        'profit_factor': profit_factor
    }

def test_advanced_strategies(df_clean):
    """Test all advanced strategies against baseline"""
    
    # Base signals (from our proven strategy)
    sma_breakdown = df_clean['close'] < df_clean['sma200']
    rsi_overbought = df_clean['rsi'] > 70
    adx_strong = df_clean['adx'] > 25
    risk_off = ~df_clean['risk_on']
    
    # Baseline strategy
    baseline = (sma_breakdown & rsi_overbought & adx_strong & risk_off)
    
    # Advanced strategies
    strategies = {
        # Baseline
        'sma_rsi_combo': baseline,
        
        # Individual advanced indicators
        'impulse_macd': (df_clean['impulse_macd'] == 1) & adx_strong & risk_off,
        'log_macd': (df_clean['log_macd'] == 1) & adx_strong & risk_off,
        'obv_divergence': (df_clean['obv'] == 1) & adx_strong & risk_off,
        'bb_upper_touch': (df_clean['close'] > df_clean['bb_upper']) & adx_strong & risk_off,
        'stoch_rsi_overbought': (df_clean['stoch_rsi'] == 1) & adx_strong & risk_off,
        
        # Combination strategies
        'sma_rsi_impulse': baseline & (df_clean['impulse_macd'] == 1),
        'sma_rsi_log_macd': baseline & (df_clean['log_macd'] == 1),
        'sma_rsi_obv': baseline & (df_clean['obv'] == 1),
        'sma_rsi_bb': baseline & (df_clean['bb_percent'] > 0.95),
        'sma_rsi_stoch': baseline & (df_clean['stoch_rsi'] == 1),
        
        # Advanced combinations
        'impulse_log_combo': (df_clean['impulse_macd'] == 1) & (df_clean['log_macd'] == 1) & adx_strong & risk_off,
        'bb_stoch_combo': (df_clean['bb_percent'] > 0.95) & (df_clean['stoch_rsi'] == 1) & adx_strong & risk_off,
        'triple_advanced': (df_clean['impulse_macd'] == 1) & (df_clean['bb_percent'] > 0.9) & (df_clean['stoch_rsi'] == 1) & adx_strong & risk_off
    }
    
    results = {}
    
    for strategy_name, signals in strategies.items():
        performance = calculate_performance_metrics(signals, df_clean)
        results[strategy_name] = performance
    
    return results

def analyze_period_advanced(period_name, period_info):
    """Analyze advanced strategies for a specific period"""
    print(f"\n{'='*60}")
    print(f"ADVANCED ANALYSIS: {period_name.upper()}")
    print(f"Description: {period_info['description']}")
    print(f"{'='*60}")
    
    period_results = {}
    
    for symbol in SYMBOLS:
        print(f"\n{symbol}:")
        
        # Load and prepare data
        df_4h = load_historical_data(symbol, period_name)
        
        if df_4h.empty:
            print(f"  ❌ No data available")
            continue
        
        # Calculate advanced indicators
        df_adv = calculate_advanced_indicators(df_4h)
        
        # Clean data
        df_clean = df_adv.dropna()
        print(f"  📊 Clean data: {len(df_clean)} candles")
        
        # Simple regime (based on price trend)
        price_trend = df_clean['close'].iloc[-1] > df_clean['close'].iloc[0]
        df_clean['risk_on'] = price_trend
        
        # Test strategies
        results = test_advanced_strategies(df_clean)
        
        # Display results
        print(f"  {'STRATEGY':<20} {'FREQ':<6} {'WIN%':<6} {'PROFIT':<8} {'SIGNALS'}")
        print(f"  {'-'*50}")
        
        symbol_results = {}
        for strategy, metrics in results.items():
            if metrics['signal_count'] > 0:
                freq = f"{metrics['signal_frequency']:.1f}%"
                win = f"{metrics['win_rate']:.1f}%"
                profit = f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] != float('inf') else "∞"
                signals = str(metrics['signal_count'])
                
                print(f"  {strategy:<20} {freq:<6} {win:<6} {profit:<8} {signals}")
                symbol_results[strategy] = metrics
        
        period_results[symbol] = symbol_results
    
    return period_results

def aggregate_advanced_results(all_results):
    """Aggregate results across all periods"""
    print(f"\n{'='*60}")
    print("ADVANCED INDICATORS AGGREGATE ANALYSIS")
    print(f"{'='*60}")
    
    # Aggregate by strategy
    strategy_aggregates = {}
    
    for period_name, period_data in all_results.items():
        for symbol, symbol_data in period_data.items():
            for strategy, metrics in symbol_data.items():
                if strategy not in strategy_aggregates:
                    strategy_aggregates[strategy] = {
                        'total_signals': 0,
                        'total_wins': 0,
                        'total_return': 0,
                        'periods_tested': set(),
                        'symbols_tested': set()
                    }
                
                # Aggregate metrics
                strategy_aggregates[strategy]['total_signals'] += metrics['signal_count']
                strategy_aggregates[strategy]['total_wins'] += metrics['signal_count'] * metrics['win_rate'] / 100
                strategy_aggregates[strategy]['total_return'] += metrics['avg_return'] * metrics['signal_count']
                strategy_aggregates[strategy]['periods_tested'].add(period_name)
                strategy_aggregates[strategy]['symbols_tested'].add(symbol)
    
    # Calculate aggregate metrics
    print(f"\n{'STRATEGY':<20} {'SIGNALS':<8} {'WIN%':<6} {'PROFIT':<8} {'PERIODS':<8} {'AVG_RET'}")
    print(f"{'-'*70}")
    
    best_strategy = None
    best_score = 0
    
    for strategy, agg in strategy_aggregates.items():
        if agg['total_signals'] > 0:
            avg_win_rate = agg['total_wins'] / agg['total_signals'] * 100
            avg_return = agg['total_return'] / agg['total_signals']
            
            # Calculate score (weighted by win rate and profit factor)
            profit_factor = avg_win_rate / (100 - avg_win_rate) if avg_win_rate < 100 else 10
            score = avg_win_rate * 0.6 + profit_factor * 20  # Weighted score
            
            periods = len(agg['periods_tested'])
            
            print(f"{strategy:<20} {agg['total_signals']:<8} {avg_win_rate:<6.1f} {profit_factor:<8.2f} {periods:<8} {avg_return:<7.2f}%")
            
            if score > best_score and agg['total_signals'] >= 50:  # Minimum sample size
                best_score = score
                best_strategy = strategy
    
    return strategy_aggregates, best_strategy

def main():
    """Main advanced indicators testing"""
    print("ADVANCED INDICATORS RAPID TESTING")
    print("=" * 60)
    print("Testing sophisticated indicators against sma_rsi_combo baseline")
    
    all_results = {}
    
    # Analyze each period
    for period_name, period_info in MARKET_PERIODS.items():
        try:
            period_results = analyze_period_advanced(period_name, period_info)
            all_results[period_name] = period_results
        except Exception as e:
            print(f"Error analyzing {period_name}: {e}")
            all_results[period_name] = {}
    
    # Aggregate results
    strategy_aggregates, best_strategy = aggregate_advanced_results(all_results)
    
    # Final recommendation
    print(f"\n{'='*60}")
    print("ADVANCED INDICATORS FINAL RECOMMENDATION")
    print(f"{'='*60}")
    
    if best_strategy:
        print(f"\n🏆 BEST PERFORMING STRATEGY: {best_strategy}")
        
        baseline_metrics = strategy_aggregates.get('sma_rsi_combo', {})
        best_metrics = strategy_aggregates.get(best_strategy, {})
        
        if baseline_metrics and best_metrics:
            baseline_win = baseline_metrics['total_wins'] / baseline_metrics['total_signals'] * 100
            best_win = best_metrics['total_wins'] / best_metrics['total_signals'] * 100
            
            improvement = best_win - baseline_win
            
            print(f"\n📊 PERFORMANCE COMPARISON:")
            print(f"   Baseline (sma_rsi_combo): {baseline_win:.1f}% win rate")
            print(f"   Best Strategy ({best_strategy}): {best_win:.1f}% win rate")
            print(f"   Improvement: {improvement:+.1f} percentage points")
            
            if improvement > 4:
                print(f"\n✅ RECOMMENDATION: Adopt {best_strategy}")
                print(f"   Significant improvement justifies complexity increase")
            elif improvement > 0:
                print(f"\n🤔 RECOMMENDATION: Consider {best_strategy}")
                print(f"   Marginal improvement - evaluate complexity vs. benefit")
            else:
                print(f"\n❌ RECOMMENDATION: Stick with sma_rsi_combo")
                print(f"   No meaningful improvement over baseline")
    else:
        print(f"\n❌ No clear winner found")
        print(f"   RECOMMENDATION: Stick with proven sma_rsi_combo baseline")

if __name__ == "__main__":
    main()
