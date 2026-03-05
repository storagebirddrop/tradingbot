#!/usr/bin/env python3
"""
Comprehensive Indicator Research
Test every single indicator and combination across all market periods
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports dynamically
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from strategy import compute_4h_indicators

# Test configuration
TEST_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
TEST_PERIODS = {
    'recent_period': 'Recent risk-off (2024)',
    'recovery_period': 'Post-bear recovery (2023)',
    'bull_peak_bear': 'Bull peak to bear (2022)',
    'covid_crash': 'COVID crash & recovery (2020-21)',
}

def safe_col(sig, col_name, default=0):
    """Safely get column value with default"""
    return sig.get(col_name, default)

def validate_indicator_columns(df_ind):
    """Validate that all required columns exist"""
    required_columns = [
        'volume_ratio', 'volume_rvol', 'volume_ema_ratio',
        'obv_divergence', 'mfi_divergence', 'cmf_divergence', 'ad_divergence',
        'mfi', 'cmf', 'vwap_support_resistance', 'vwap_lower', 'vwap_upper',
        'impulse_macd', 'close', 'sma200_4h', 'rsi'
    ]
    
    missing_columns = [col for col in required_columns if col not in df_ind.columns]
    if missing_columns:
        print(f"Missing required columns: {missing_columns}")
        return False
    return True

def load_historical_data(symbol, period):
    """Load historical data for testing"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    # Build path relative to script location
    script_dir = Path(__file__).resolve().parent
    filepath_4h = script_dir / "historical" / filename_4h
    
    try:
        if filepath_4h.exists():
            df = pd.read_csv(filepath_4h)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
            else:
                print(f"Error: 'timestamp' column not found in {filepath_4h}")
                return pd.DataFrame()
        else:
            print(f"Warning: File not found: {filepath_4h}")
            return pd.DataFrame()
    except (IOError, pd.errors.ParserError, UnicodeDecodeError) as e:
        print(f"Error loading data for {symbol} {period}: {e}")
        return pd.DataFrame()

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=20):
    """Simulate a trade with proper risk management"""
    stop_loss_price = entry_price * (1 - stop_loss_pct)
    take_profit_price = entry_price * (1 + take_profit_pct)
    
    for j in range(entry_idx + 1, min(entry_idx + max_holding_periods + 1, len(df))):
        current_candle = df.iloc[j]
        current_price = current_candle['close']
        
        # Check stop loss (intra-candle wick)
        if current_candle['low'] <= stop_loss_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': stop_loss_price,
                'exit_reason': 'stop_loss',
                'return_pct': (stop_loss_price - entry_price) / entry_price * 100,
                'holding_periods': j - entry_idx
            }
        
        # Check take profit (intra-candle wick)
        if current_candle['high'] >= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': (take_profit_price - entry_price) / entry_price * 100,
                'holding_periods': j - entry_idx
            }
        
        # Check signal reversal (simple exit)
        if j > entry_idx + 1:
            sig = current_candle
            if sig['rsi'] > 70 or sig['close'] < sig['sma200_4h']:
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (current_price - entry_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
    
    # Max holding period reached
    final_price = df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['close']
    return_pct = (final_price - entry_price) / entry_price * 100
    
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
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': calmar_ratio
    }

def test_single_indicators():
    """Test each single indicator across all market periods"""
    print("🔍 TESTING SINGLE INDICATORS")
    print("=" * 80)
    
    # Define all indicators to test
    single_indicators = {
        # Current baseline
        'volume_ratio': lambda sig, prev_sig: safe_col(sig, 'volume_ratio') > 2.0,
        
        # Enhanced volume indicators
        'volume_rvol': lambda sig, prev_sig: safe_col(sig, 'volume_rvol') > 2.0,
        'volume_ema_ratio': lambda sig, prev_sig: safe_col(sig, 'volume_ema_ratio') > 2.0,
        
        # Divergence indicators
        'obv_divergence': lambda sig, prev_sig: safe_col(sig, 'obv_divergence') == 1,
        'mfi_divergence': lambda sig, prev_sig: safe_col(sig, 'mfi_divergence') == 1,
        'cmf_divergence': lambda sig, prev_sig: safe_col(sig, 'cmf_divergence') == 1,
        'ad_divergence': lambda sig, prev_sig: safe_col(sig, 'ad_divergence') == 1,
        
        # Flow indicators (oversold conditions)
        'mfi_oversold': lambda sig, prev_sig: safe_col(sig, 'mfi') < 20,
        'cmf_oversold': lambda sig, prev_sig: safe_col(sig, 'cmf') < -0.1,
        
        # VWAP indicators
        'vwap_support': lambda sig, prev_sig: safe_col(sig, 'vwap_support_resistance') == 1,
        'vwap_near_lower': lambda sig, prev_sig: (
            safe_col(sig, 'close') > safe_col(sig, 'vwap_lower') * 0.98 and 
            safe_col(sig, 'close') < safe_col(sig, 'vwap_lower') * 1.02
        ),
        
        # Momentum indicators
        'impulse_macd': lambda sig, prev_sig: safe_col(sig, 'impulse_macd') == 1,
        
        # Volume + price action
        'high_volume_green': lambda sig, prev_sig: (
            safe_col(sig, 'volume_ratio') > 2.0 and 
            safe_col(sig, 'close') > safe_col(prev_sig, 'close')
        ),
        'high_rvol_green': lambda sig, prev_sig: (
            safe_col(sig, 'volume_rvol') > 2.0 and 
            safe_col(sig, 'close') > safe_col(prev_sig, 'close')
        ),
    }
    
    results = {}
    
    for indicator_name, indicator_func in single_indicators.items():
        print(f"\n📊 Testing {indicator_name}:")
        print("-" * 50)
        
        all_trades = []
        period_results = {}
        
        for period_name, period_desc in TEST_PERIODS.items():
            period_trades = []
            
            for symbol in TEST_SYMBOLS:
                df = load_historical_data(symbol, period_name)
                if df.empty:
                    continue
                
                df_ind = compute_4h_indicators(df)
                if df_ind.empty:
                    continue
                
                # Validate required columns exist
                if not validate_indicator_columns(df_ind):
                    print(f"Skipping {symbol} {period_name} due to missing columns")
                    continue
                
                # Test strategy with this indicator
                for i in range(1, len(df_ind)):
                    sig = df_ind.iloc[i]
                    prev_sig = df_ind.iloc[i-1]
                    
                    # Base conditions (downtrend context + price reversal)
                    base_conditions = (
                        prev_sig['close'] < prev_sig['sma200_4h'] and  # Downtrend
                        sig['close'] > prev_sig['close'] and  # Price reversal
                        sig['rsi'] < 40  # Oversold
                    )
                    
                    # Add specific indicator condition
                    if base_conditions and indicator_func(sig, prev_sig):
                        entry_price = sig['close']
                        
                        # Simulate trade
                        outcome = simulate_trade(df_ind, i, entry_price, 0.02, 0.04, 20)
                        
                        if outcome:
                            trade = {
                                'symbol': symbol,
                                'entry_time': sig['timestamp'],
                                'entry_price': entry_price,
                                'exit_time': outcome['exit_time'],
                                'exit_price': outcome['exit_price'],
                                'exit_reason': outcome['exit_reason'],
                                'return_pct': outcome['return_pct'],
                                'holding_periods': outcome['holding_periods']
                            }
                            
                            period_trades.append(trade)
            
            if period_trades:
                metrics = calculate_risk_metrics(period_trades)
                period_results[period_name] = metrics
                all_trades.extend(period_trades)
                
                print(f"  {period_name}: {metrics['total_trades']} trades, "
                      f"Win Rate {metrics['win_rate']:.1f}%, "
                      f"Profit Factor {metrics['profit_factor']:.2f}")
        
        # Overall metrics for this indicator
        if all_trades:
            overall_metrics = calculate_risk_metrics(all_trades)
            results[indicator_name] = {
                'overall_metrics': overall_metrics,
                'period_results': period_results,
                'total_trades': overall_metrics['total_trades']
            }
            
            print(f"  Overall: {overall_metrics['total_trades']} trades, "
                  f"Win Rate {overall_metrics['win_rate']:.1f}%, "
                  f"Profit Factor {overall_metrics['profit_factor']:.2f}, "
                  f"Sharpe {overall_metrics['sharpe_ratio']:.2f}")
        else:
            print(f"  Overall: No trades generated")
            results[indicator_name] = {
                'overall_metrics': {'total_trades': 0, 'win_rate': 0, 'profit_factor': 0, 'sharpe_ratio': 0},
                'period_results': {},
                'total_trades': 0
            }
    
    return results

def test_indicator_combinations():
    """Test promising indicator combinations"""
    print(f"\n🔄 TESTING INDICATOR COMBINATIONS")
    print("=" * 80)
    
    # Define promising combinations based on single indicator results
    combinations = {
        # Volume + Divergence combinations
        'volume_obv_div': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and sig['obv_divergence'] == 1,
        'volume_mfi_div': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and sig['mfi_divergence'] == 1,
        'volume_cmf_div': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and sig['cmf_divergence'] == 1,
        
        # Volume + Flow combinations
        'volume_mfi_oversold': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and sig['mfi'] < 20,
        'volume_cmf_oversold': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and sig['cmf'] < -0.1,
        
        # Volume + VWAP combinations
        'volume_vwap_support': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and sig['vwap_support_resistance'] == 1,
        'volume_vwap_near_lower': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and (sig['close'] > sig['vwap_lower'] * 0.98 and sig['close'] < sig['vwap_lower'] * 1.02),
        
        # Enhanced volume combinations
        'rvol_mfi_oversold': lambda sig, prev_sig: sig['volume_rvol'] > 2.0 and sig['mfi'] < 20,
        'rvol_cmf_oversold': lambda sig, prev_sig: sig['volume_rvol'] > 2.0 and sig['cmf'] < -0.1,
        
        # Multi-indicator combinations
        'volume_mfi_cmf': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and sig['mfi'] < 20 and sig['cmf'] < -0.1,
        'volume_obv_mfi': lambda sig, prev_sig: sig['volume_ratio'] > 2.0 and sig['obv_divergence'] == 1 and sig['mfi'] < 20,
        
        # Momentum + Volume combinations
        'impulse_volume': lambda sig, prev_sig: sig['impulse_macd'] == 1 and sig['volume_ratio'] > 2.0,
        
        # Perfect setup (high volume + reversal + divergence + support)
        'perfect_setup': lambda sig, prev_sig: (sig['volume_ratio'] > 2.0 and 
                                             sig['close'] > prev_sig['close'] and
                                             prev_sig['close'] < prev_sig['sma200_4h'] and
                                             (sig['obv_divergence'] == 1 or sig['mfi_divergence'] == 1) and
                                             sig['vwap_support_resistance'] == 1),
    }
    
    results = {}
    
    for combo_name, combo_func in combinations.items():
        print(f"\n📊 Testing {combo_name}:")
        print("-" * 50)
        
        all_trades = []
        
        for period_name, period_desc in TEST_PERIODS.items():
            for symbol in TEST_SYMBOLS:
                df = load_historical_data(symbol, period_name)
                if df.empty:
                    continue
                
                df_ind = compute_4h_indicators(df)
                if df_ind.empty:
                    continue
                
                # Test strategy with this combination
                for i in range(1, len(df_ind)):
                    sig = df_ind.iloc[i]
                    prev_sig = df_ind.iloc[i-1]
                    
                    # Base conditions (same three filters as test_single_indicators)
                    base_conditions = (
                        prev_sig['close'] < prev_sig['sma200_4h'] and  # Downtrend
                        sig['close'] > prev_sig['close'] and  # Price reversal  
                        sig['rsi'] < 40  # Oversold
                    )
                    
                    # Add specific combination condition
                    if base_conditions and combo_func(sig, prev_sig):
                        entry_price = sig['close']
                        
                        # Simulate trade
                        outcome = simulate_trade(df_ind, i, entry_price, 0.02, 0.04, 20)
                        
                        if outcome:
                            trade = {
                                'symbol': symbol,
                                'entry_time': sig['timestamp'],
                                'entry_price': entry_price,
                                'exit_time': outcome['exit_time'],
                                'exit_price': outcome['exit_price'],
                                'exit_reason': outcome['exit_reason'],
                                'return_pct': outcome['return_pct'],
                                'holding_periods': outcome['holding_periods']
                            }
                            
                            all_trades.append(trade)
        
        # Overall metrics for this combination
        if all_trades:
            overall_metrics = calculate_risk_metrics(all_trades)
            results[combo_name] = {
                'overall_metrics': overall_metrics,
                'total_trades': overall_metrics['total_trades']
            }
            
            print(f"  Overall: {overall_metrics['total_trades']} trades, "
                  f"Win Rate {overall_metrics['win_rate']:.1f}%, "
                  f"Profit Factor {overall_metrics['profit_factor']:.2f}, "
                  f"Sharpe {overall_metrics['sharpe_ratio']:.2f}")
        else:
            print(f"  Overall: No trades generated")
            results[combo_name] = {
                'overall_metrics': {'total_trades': 0, 'win_rate': 0, 'profit_factor': 0, 'sharpe_ratio': 0},
                'total_trades': 0
            }
    
    return results

def rank_strategies(single_results, combo_results):
    """Rank all strategies by performance"""
    print(f"\n🏆 STRATEGY RANKINGS")
    print("=" * 80)
    
    all_strategies = {}
    
    # Add single indicators
    for name, result in single_results.items():
        all_strategies[f"single_{name}"] = result
    
    # Add combinations
    for name, result in combo_results.items():
        all_strategies[f"combo_{name}"] = result
    
    # Filter strategies with minimum trades
    viable_strategies = {k: v for k, v in all_strategies.items() if v['total_trades'] >= 5}
    
    # Sort by composite score (weighted ranking)
    def calculate_score(metrics):
        if metrics['total_trades'] == 0:
            return 0
        
        # Weighted scoring system
        score = 0
        
        # Win rate (30% weight) - target > 55%
        win_rate_score = min(metrics['win_rate'] / 55, 2.0) * 30
        
        # Profit factor (25% weight) - target > 2.0
        pf_score = min(metrics['profit_factor'] / 2.0, 3.0) * 25
        
        # Sharpe ratio (20% weight) - target > 0.5
        sharpe_score = min(metrics['sharpe_ratio'] / 0.5, 2.0) * 20
        
        # Trade frequency (15% weight) - target 20-100 trades
        trade_count = metrics['total_trades']
        if 20 <= trade_count <= 100:
            freq_score = 15
        elif trade_count < 20:
            freq_score = trade_count / 20 * 15
        else:
            freq_score = max(0, 15 - (trade_count - 100) / 100 * 15)
        
        # Max drawdown penalty (10% weight) - lower is better
        drawdown_penalty = min(metrics['max_drawdown'] / 10, 1.0) * -10
        
        score = win_rate_score + pf_score + sharpe_score + freq_score + drawdown_penalty
        
        return score
    
    # Calculate scores and rank
    ranked_strategies = []
    for name, result in viable_strategies.items():
        metrics = result['overall_metrics']
        score = calculate_score(metrics)
        
        ranked_strategies.append({
            'name': name,
            'score': score,
            'metrics': metrics
        })
    
    # Sort by score
    ranked_strategies.sort(key=lambda x: x['score'], reverse=True)
    
    # Display rankings
    print(f"🥇 TOP 15 STRATEGIES:")
    print("-" * 80)
    
    for i, strategy in enumerate(ranked_strategies[:15]):
        name = strategy['name'].replace('single_', '').replace('combo_', '')
        metrics = strategy['metrics']
        score = strategy['score']
        
        print(f"{i+1:2d}. {name:<25} Score: {score:6.1f}")
        print(f"    Trades: {metrics['total_trades']:3d}, Win Rate: {metrics['win_rate']:5.1f}%, "
              f"PF: {metrics['profit_factor']:5.2f}, Sharpe: {metrics['sharpe_ratio']:5.2f}")
    
    return ranked_strategies

def main():
    """Main comprehensive research function"""
    try:
        print("🚀 COMPREHENSIVE INDICATOR RESEARCH")
        print("=" * 80)
        print("Testing all single indicators and combinations across all market periods")
        
        # Test single indicators
        single_results = test_single_indicators()
        
        # Test combinations
        combo_results = test_indicator_combinations()
        
        # Rank strategies
        ranked_strategies = rank_strategies(single_results, combo_results)
        
        # Get top 5 for deep testing
        top_5 = ranked_strategies[:5]
        
        print(f"\n🎯 TOP 5 STRATEGIES FOR DEEP TESTING:")
        for i, strategy in enumerate(top_5):
            name = strategy['name'].replace('single_', '').replace('combo_', '')
            print(f"{i+1}. {name}")
        
        print(f"\n🎉 COMPREHENSIVE RESEARCH COMPLETE!")
        print(f"✅ Tested {len(single_results)} single indicators")
        print(f"✅ Tested {len(combo_results)} combinations")
        print(f"✅ Identified top 5 strategies for deep validation")
        
        return {
            'single_results': single_results,
            'combo_results': combo_results,
            'ranked_strategies': ranked_strategies,
            'top_5': top_5
        }
        
    except Exception as e:
        print(f"❌ Comprehensive research failed: {e}")
        return None

if __name__ == "__main__":
    result = main()
