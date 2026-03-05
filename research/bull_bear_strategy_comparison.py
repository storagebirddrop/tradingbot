#!/usr/bin/env python3
"""
Bull vs Bear Market Strategy Comparison
Focused comparison of sma_rsi_combo vs sma_rsi_impulse
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

# Market periods with clear bull/bear classification
MARKET_PERIODS = {
    'covid_crash': {
        'description': 'COVID crash & recovery',
        'market_type': 'bear_to_bull',
        'characteristics': 'Extreme volatility, sharp reversal'
    },
    'bull_peak_bear': {
        'description': 'Bull peak to bear transition',
        'market_type': 'bull_to_bear',
        'characteristics': 'Major trend reversal'
    },
    'recovery_period': {
        'description': 'Post-bear recovery',
        'market_type': 'bull',
        'characteristics': 'Gradual uptrend'
    },
    'recent_period': {
        'description': 'Recent risk-off',
        'market_type': 'bear',
        'characteristics': 'Bearish bias'
    }
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

def calculate_impulse_macd(close, fast=12, slow=26, signal=9):
    """Calculate ImpulseMACD signal"""
    # Standard MACD
    exp1 = close.ewm(span=fast).mean()
    exp2 = close.ewm(span=slow).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line
    
    # Impulse component - rate of change of histogram
    impulse = histogram.diff()
    
    # Impulse signal (positive momentum)
    impulse_signal = (impulse > 0) & (histogram > 0)
    
    return impulse_signal.astype(int)

def calculate_performance_metrics(signals, df):
    """Calculate detailed performance metrics"""
    if not signals.any():
        return {
            'signal_count': 0,
            'signal_frequency': 0,
            'avg_return': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0,
            'total_profit': 0,
            'total_loss': 0
        }
    
    # Find entry points
    entry_points = df[signals].copy()
    
    if entry_points.empty:
        return {
            'signal_count': 0,
            'signal_frequency': 0,
            'avg_return': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0,
            'total_profit': 0,
            'total_loss': 0
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
            'profit_factor': 0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0,
            'total_profit': 0,
            'total_loss': 0
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
    
    # Consecutive wins/losses
    results = [1 if x > 0 else -1 for x in trades]
    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_streak = 0
    
    for result in results:
        if result == 1:
            current_streak = current_streak + 1 if current_streak > 0 else 1
            max_consecutive_wins = max(max_consecutive_wins, current_streak)
        else:
            current_streak = current_streak - 1 if current_streak < 0 else -1
            max_consecutive_losses = max(max_consecutive_losses, abs(current_streak))
    
    return {
        'signal_count': len(entry_points),
        'signal_frequency': len(entry_points) / len(df) * 100,
        'avg_return': trades_series.mean(),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_consecutive_wins': max_consecutive_wins,
        'max_consecutive_losses': max_consecutive_losses,
        'total_profit': gross_profit,
        'total_loss': gross_loss
    }

def analyze_bull_bear_performance(period_name, period_info):
    """Analyze strategy performance for specific market type"""
    print(f"\n{'='*60}")
    print(f"BULL/BEAR ANALYSIS: {period_name.upper()}")
    print(f"Market Type: {period_info['market_type'].upper()}")
    print(f"Characteristics: {period_info['characteristics']}")
    print(f"{'='*60}")
    
    period_results = {}
    
    for symbol in SYMBOLS:
        print(f"\n{symbol}:")
        
        # Load data
        df_4h = load_historical_data(symbol, period_name)
        
        if df_4h.empty:
            print(f"  ❌ No data available")
            continue
        
        # Calculate ImpulseMACD
        df_4h['impulse_macd'] = calculate_impulse_macd(df_4h['close'])
        
        # Clean data
        df_clean = df_4h.dropna()
        print(f"  📊 Clean data: {len(df_clean)} candles")
        
        # Determine market regime (simplified)
        price_change = (df_clean['close'].iloc[-1] - df_clean['close'].iloc[0]) / df_clean['close'].iloc[0]
        market_trend = 'bull' if price_change > 0.05 else 'bear' if price_change < -0.05 else 'neutral'
        print(f"  📈 Market trend: {market_trend} ({price_change:+.1%})")
        
        # Base signals
        sma_breakdown = df_clean['close'] < df_clean['sma200']
        rsi_overbought = df_clean['rsi'] > 70
        adx_strong = df_clean['adx'] > 25
        impulse_positive = df_clean['impulse_macd'] == 1
        
        # Risk regime (simplified)
        risk_off = market_trend == 'bear'  # In bear markets, assume risk-off
        
        # Strategies to compare
        strategies = {
            'sma_rsi_combo': (sma_breakdown & rsi_overbought & adx_strong & risk_off),
            'sma_rsi_impulse': (sma_breakdown & rsi_overbought & adx_strong & impulse_positive & risk_off)
        }
        
        print(f"  {'STRATEGY':<20} {'FREQ':<6} {'WIN%':<6} {'PROFIT':<8} {'SIGNALS'} {'MAX_WIN'} {'MAX_LOSS'}")
        print(f"  {'-'*70}")
        
        symbol_results = {}
        for strategy, signals in strategies.items():
            performance = calculate_performance_metrics(signals, df_clean)
            
            if performance['signal_count'] > 0:
                freq = f"{performance['signal_frequency']:.1f}%"
                win = f"{performance['win_rate']:.1f}%"
                profit = f"{performance['profit_factor']:.2f}" if performance['profit_factor'] != float('inf') else "∞"
                signals_str = str(performance['signal_count'])
                max_win = str(performance['max_consecutive_wins'])
                max_loss = str(performance['max_consecutive_losses'])
                
                print(f"  {strategy:<20} {freq:<6} {win:<6} {profit:<8} {signals_str:<7} {max_win:<7} {max_loss}")
                
                symbol_results[strategy] = performance
            else:
                print(f"  {strategy:<20} {'N/A':<6} {'N/A':<6} {'N/A':<8} {'0':<7} {'0':<7} {'0'}")
                symbol_results[strategy] = performance
        
        period_results[symbol] = {
            'results': symbol_results,
            'market_trend': market_trend,
            'price_change': price_change
        }
    
    return period_results

def aggregate_bull_bear_results(all_results):
    """Aggregate results by market type"""
    print(f"\n{'='*60}")
    print("BULL vs BEAR MARKET AGGREGATE ANALYSIS")
    print(f"{'='*60}")
    
    # Group by market type
    bull_results = {}
    bear_results = {}
    transition_results = {}
    
    for period_name, period_data in all_results.items():
        period_info = MARKET_PERIODS[period_name]
        market_type = period_info['market_type']
        
        for symbol, data in period_data.items():
            if 'results' not in data:
                continue
                
            strategy_data = data['results']
            
            for strategy, metrics in strategy_data.items():
                if market_type == 'bull':
                    if strategy not in bull_results:
                        bull_results[strategy] = {
                            'total_signals': 0,
                            'total_wins': 0,
                            'total_return': 0,
                            'periods': 0,
                            'symbols': set()
                        }
                    
                    bull_results[strategy]['total_signals'] += metrics['signal_count']
                    bull_results[strategy]['total_wins'] += metrics['signal_count'] * metrics['win_rate'] / 100
                    bull_results[strategy]['total_return'] += metrics['avg_return'] * metrics['signal_count']
                    bull_results[strategy]['periods'] += 1
                    bull_results[strategy]['symbols'].add(symbol)
                    
                elif market_type == 'bear':
                    if strategy not in bear_results:
                        bear_results[strategy] = {
                            'total_signals': 0,
                            'total_wins': 0,
                            'total_return': 0,
                            'periods': 0,
                            'symbols': set()
                        }
                    
                    bear_results[strategy]['total_signals'] += metrics['signal_count']
                    bear_results[strategy]['total_wins'] += metrics['signal_count'] * metrics['win_rate'] / 100
                    bear_results[strategy]['total_return'] += metrics['avg_return'] * metrics['signal_count']
                    bear_results[strategy]['periods'] += 1
                    bear_results[strategy]['symbols'].add(symbol)
                    
                else:  # transition periods
                    if strategy not in transition_results:
                        transition_results[strategy] = {
                            'total_signals': 0,
                            'total_wins': 0,
                            'total_return': 0,
                            'periods': 0,
                            'symbols': set()
                        }
                    
                    transition_results[strategy]['total_signals'] += metrics['signal_count']
                    transition_results[strategy]['total_wins'] += metrics['signal_count'] * metrics['win_rate'] / 100
                    transition_results[strategy]['total_return'] += metrics['avg_return'] * metrics['signal_count']
                    transition_results[strategy]['periods'] += 1
                    transition_results[strategy]['symbols'].add(symbol)
    
    # Display results by market type
    market_types = [
        ('BULL MARKETS', bull_results),
        ('BEAR MARKETS', bear_results),
        ('TRANSITION MARKETS', transition_results)
    ]
    
    for market_name, results in market_types:
        print(f"\n{market_name}:")
        print(f"  {'STRATEGY':<20} {'SIGNALS':<8} {'WIN%':<6} {'PROFIT':<8} {'AVG_RET'}")
        print(f"  {'-'*60}")
        
        for strategy, data in results.items():
            if data['total_signals'] > 0:
                avg_win = data['total_wins'] / data['total_signals'] * 100
                avg_return = data['total_return'] / data['total_signals']
                
                # Calculate profit factor
                wins = data['total_wins']
                losses = data['total_signals'] - wins
                profit_factor = wins / losses if losses > 0 else float('inf') if wins > 0 else 0
                
                profit_str = f"{profit_factor:.2f}" if profit_factor != float('inf') else "∞"
                
                print(f"  {strategy:<20} {data['total_signals']:<8} {avg_win:<6.1f} {profit_str:<8} {avg_return:<7.2f}%")
    
    return bull_results, bear_results, transition_results

def head_to_head_comparison(bull_results, bear_results):
    """Head-to-head comparison between strategies"""
    print(f"\n{'='*60}")
    print("HEAD-TO-HEAD COMPARISON")
    print(f"{'='*60}")
    
    strategies = ['sma_rsi_combo', 'sma_rsi_impulse']
    
    for strategy in strategies:
        print(f"\n{strategy.upper()}:")
        
        # Bull market performance
        bull_data = bull_results.get(strategy, {})
        bull_win = bull_data['total_wins'] / bull_data['total_signals'] * 100 if bull_data.get('total_signals', 0) > 0 else 0
        
        # Bear market performance
        bear_data = bear_results.get(strategy, {})
        bear_win = bear_data['total_wins'] / bear_data['total_signals'] * 100 if bear_data.get('total_signals', 0) > 0 else 0
        
        print(f"  📈 Bull Markets: {bull_win:.1f}% win rate")
        print(f"  📉 Bear Markets: {bear_win:.1f}% win rate")
        
        if bull_win > 0 and bear_win > 0:
            bull_advantage = bull_win - bear_win
            print(f"  📊 Bull Advantage: {bull_advantage:+.1f} percentage points")
            
            if bull_advantage > 5:
                print(f"  💡 Strategy performs significantly better in bull markets")
            elif bull_advantage < -5:
                print(f"  💡 Strategy performs significantly better in bear markets")
            else:
                print(f"  💡 Strategy performance balanced across market types")

def main():
    """Main bull vs bear comparison"""
    print("BULL vs BEAR MARKET STRATEGY COMPARISON")
    print("=" * 60)
    print("Focused comparison: sma_rsi_combo vs sma_rsi_impulse")
    
    all_results = {}
    
    # Analyze each period
    for period_name, period_info in MARKET_PERIODS.items():
        try:
            period_results = analyze_bull_bear_performance(period_name, period_info)
            all_results[period_name] = period_results
        except Exception as e:
            print(f"Error analyzing {period_name}: {e}")
            all_results[period_name] = {}
    
    # Aggregate by market type
    bull_results, bear_results, transition_results = aggregate_bull_bear_results(all_results)
    
    # Head-to-head comparison
    head_to_head_comparison(bull_results, bear_results)
    
    # Final recommendation
    print(f"\n{'='*60}")
    print("FINAL BULL/BEAR RECOMMENDATION")
    print(f"{'='*60}")
    
    # Compare strategies in different market conditions
    combo_bull = bull_results.get('sma_rsi_combo', {})
    combo_bear = bear_results.get('sma_rsi_combo', {})
    impulse_bull = bull_results.get('sma_rsi_impulse', {})
    impulse_bear = bear_results.get('sma_rsi_impulse', {})
    
    if all([combo_bull, combo_bear, impulse_bull, impulse_bear]):
        combo_bull_win = combo_bull['total_wins'] / combo_bull['total_signals'] * 100
        combo_bear_win = combo_bear['total_wins'] / combo_bear['total_signals'] * 100
        impulse_bull_win = impulse_bull['total_wins'] / impulse_bull['total_signals'] * 100
        impulse_bear_win = impulse_bear['total_wins'] / impulse_bear['total_signals'] * 100
        
        print(f"\n📊 MARKET CONDITION PERFORMANCE:")
        print(f"   sma_rsi_combo - Bull: {combo_bull_win:.1f}%, Bear: {combo_bear_win:.1f}%")
        print(f"   sma_rsi_impulse - Bull: {impulse_bull_win:.1f}%, Bear: {impulse_bear_win:.1f}%")
        
        # Determine which is better for current conditions
        if impulse_bear_win > combo_bear_win and impulse_bull_win > combo_bull_win:
            print(f"\n✅ RECOMMENDATION: sma_rsi_impulse")
            print(f"   Superior in both bull and bear markets")
        elif impulse_bear_win > combo_bear_win:
            print(f"\n✅ RECOMMENDATION: sma_rsi_impulse (for bear markets)")
            print(f"   Better performance in bear market conditions")
        elif impulse_bull_win > combo_bull_win:
            print(f"\n✅ RECOMMENDATION: sma_rsi_impulse (for bull markets)")
            print(f"   Better performance in bull market conditions")
        else:
            print(f"\n✅ RECOMMENDATION: sma_rsi_combo")
            print(f"   Consistent performance, simpler implementation")

if __name__ == "__main__":
    main()
