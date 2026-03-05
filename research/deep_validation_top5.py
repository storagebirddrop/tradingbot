#!/usr/bin/env python3
"""
Deep Validation of Top 5 Strategies
Comprehensive testing with parameter optimization for the top performing strategies
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime
import itertools

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators

# Test configuration
TEST_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]  # XRP data not available yet
TEST_PERIODS = {
    'recent_period': 'Recent risk-off (2024)',
    'recovery_period': 'Post-bear recovery (2023)',
    'bull_peak_bear': 'Bull peak to bear (2022)',
    'covid_crash': 'COVID crash & recovery (2020-21)',
}

def load_historical_data(symbol, period):
    """Load historical data for testing"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    filepath_4h = f"/home/dribble0335/dev/tradingbot/research/historical/{filename_4h}"
    
    if os.path.exists(filepath_4h):
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=20):
    """Simulate a trade with proper risk management"""
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
                'return_pct': -stop_loss_pct * 100,  # Convert to percentage
                'holding_periods': j - entry_idx
            }
        
        # Check take profit
        if current_price >= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct * 100,  # Convert to percentage
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

def test_strategy_with_params(strategy_name, strategy_func, params):
    """Test a strategy with specific parameters"""
    all_trades = []
    
    for period_name, period_desc in TEST_PERIODS.items():
        for symbol in TEST_SYMBOLS:
            df = load_historical_data(symbol, period_name)
            if df.empty:
                continue
            
            df_ind = compute_4h_indicators(df)
            if df_ind.empty:
                continue
            
            # Test strategy with specific parameters
            for i in range(1, len(df_ind)):
                sig = df_ind.iloc[i]
                prev_sig = df_ind.iloc[i-1]
                
                # Base conditions (downtrend context + price reversal)
                base_conditions = (
                    prev_sig['close'] < prev_sig['sma200_4h'] and  # Downtrend
                    sig['close'] > prev_sig['close'] and  # Price reversal
                    sig['rsi'] < params.get('rsi_threshold', 40)  # Oversold
                )
                
                # Add specific strategy condition
                if base_conditions and strategy_func(sig, prev_sig, params):
                    entry_price = sig['close']
                    
                    # Simulate trade
                    outcome = simulate_trade(df_ind, i, entry_price, 
                                           params.get('stop_loss_pct', 0.02), 
                                           params.get('take_profit_pct', 0.04), 
                                           params.get('max_holding_periods', 20))
                    
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
    
    return calculate_risk_metrics(all_trades), all_trades

def optimize_strategy_parameters(strategy_name, strategy_func, param_grid):
    """Optimize strategy parameters using grid search"""
    print(f"\n🔧 OPTIMIZING {strategy_name.upper()} PARAMETERS")
    print("-" * 60)
    
    best_score = 0
    best_params = None
    best_metrics = None
    best_trades = None
    
    total_combinations = len(list(itertools.product(*param_grid.values())))
    current_combination = 0
    
    # Generate all parameter combinations
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    
    for combination in itertools.product(*param_values):
        current_combination += 1
        params = dict(zip(param_names, combination))
        
        # Test this parameter combination
        metrics, trades = test_strategy_with_params(strategy_name, strategy_func, params)
        
        # Skip if no trades
        if metrics['total_trades'] < 5:
            continue
        
        # Calculate composite score
        score = calculate_strategy_score(metrics)
        
        # Update best if better
        if score > best_score:
            best_score = score
            best_params = params
            best_metrics = metrics
            best_trades = trades
        
        # Progress update
        if current_combination % 10 == 0:
            print(f"  Tested {current_combination}/{total_combinations} combinations...")
    
    print(f"  Best score: {best_score:.1f}")
    print(f"  Best parameters: {best_params}")
    
    if best_metrics:
        print(f"  Performance: {best_metrics['total_trades']} trades, "
              f"Win Rate {best_metrics['win_rate']:.1f}%, "
              f"Profit Factor {best_metrics['profit_factor']:.2f}, "
              f"Sharpe {best_metrics['sharpe_ratio']:.2f}")
    
    return best_params, best_metrics, best_trades, best_score

def calculate_strategy_score(metrics):
    """Calculate composite score for strategy evaluation"""
    if metrics['total_trades'] == 0:
        return 0
    
    # Weighted scoring system
    score = 0
    
    # Win rate (30% weight) - target > 60%
    win_rate_score = min(metrics['win_rate'] / 60, 2.0) * 30
    
    # Profit factor (25% weight) - target > 3.0
    pf_score = min(metrics['profit_factor'] / 3.0, 3.0) * 25
    
    # Sharpe ratio (20% weight) - target > 0.6
    sharpe_score = min(metrics['sharpe_ratio'] / 0.6, 2.0) * 20
    
    # Trade frequency (15% weight) - target 20-80 trades
    trade_count = metrics['total_trades']
    if 20 <= trade_count <= 80:
        freq_score = 15
    elif trade_count < 20:
        freq_score = trade_count / 20 * 15
    else:
        freq_score = max(0, 15 - (trade_count - 80) / 80 * 15)
    
    # Max drawdown penalty (10% weight) - lower is better
    drawdown_penalty = min(metrics['max_drawdown'] / 5, 1.0) * -10
    
    score = win_rate_score + pf_score + sharpe_score + freq_score + drawdown_penalty
    
    return score

# Strategy functions for top 5
def volume_mfi_cmf_strategy(sig, prev_sig, params):
    """Volume + MFI + CMF strategy"""
    volume_threshold = params.get('volume_threshold', 2.0)
    mfi_threshold = params.get('mfi_threshold', 20)
    cmf_threshold = params.get('cmf_threshold', -0.1)
    
    return (sig['volume_ratio'] > volume_threshold and 
            sig['mfi'] < mfi_threshold and 
            sig['cmf'] < cmf_threshold)

def volume_ema_ratio_strategy(sig, prev_sig, params):
    """Volume EMA Ratio strategy"""
    volume_threshold = params.get('volume_threshold', 2.0)
    
    return sig['volume_ema_ratio'] > volume_threshold

def volume_ratio_strategy(sig, prev_sig, params):
    """Volume Ratio strategy (baseline)"""
    volume_threshold = params.get('volume_threshold', 2.0)
    
    return sig['volume_ratio'] > volume_threshold

def volume_rvol_strategy(sig, prev_sig, params):
    """Relative Volume strategy"""
    volume_threshold = params.get('volume_threshold', 2.0)
    
    return sig['volume_rvol'] > volume_threshold

def high_volume_green_strategy(sig, prev_sig, params):
    """High Volume + Green Candle strategy"""
    volume_threshold = params.get('volume_threshold', 2.0)
    
    return (sig['volume_ratio'] > volume_threshold and 
            sig['close'] > prev_sig['close'])

def main():
    """Main deep validation function"""
    try:
        print("🚀 DEEP VALIDATION OF TOP 5 STRATEGIES")
        print("=" * 80)
        print("Comprehensive parameter optimization and validation")
        
        # Define strategies and their parameter grids
        strategies = {
            'volume_mfi_cmf': {
                'func': volume_mfi_cmf_strategy,
                'params': {
                    'volume_threshold': [1.5, 2.0, 2.5, 3.0],
                    'mfi_threshold': [15, 20, 25, 30],
                    'cmf_threshold': [-0.15, -0.1, -0.05, 0.0],
                    'stop_loss_pct': [0.015, 0.02, 0.025],
                    'take_profit_pct': [0.03, 0.04, 0.05],
                    'rsi_threshold': [35, 40, 45]
                }
            },
            'volume_ema_ratio': {
                'func': volume_ema_ratio_strategy,
                'params': {
                    'volume_threshold': [1.5, 2.0, 2.5, 3.0],
                    'stop_loss_pct': [0.015, 0.02, 0.025],
                    'take_profit_pct': [0.03, 0.04, 0.05],
                    'rsi_threshold': [35, 40, 45]
                }
            },
            'volume_ratio': {
                'func': volume_ratio_strategy,
                'params': {
                    'volume_threshold': [1.5, 2.0, 2.5, 3.0],
                    'stop_loss_pct': [0.015, 0.02, 0.025],
                    'take_profit_pct': [0.03, 0.04, 0.05],
                    'rsi_threshold': [35, 40, 45]
                }
            },
            'volume_rvol': {
                'func': volume_rvol_strategy,
                'params': {
                    'volume_threshold': [1.5, 2.0, 2.5, 3.0],
                    'stop_loss_pct': [0.015, 0.02, 0.025],
                    'take_profit_pct': [0.03, 0.04, 0.05],
                    'rsi_threshold': [35, 40, 45]
                }
            },
            'high_volume_green': {
                'func': high_volume_green_strategy,
                'params': {
                    'volume_threshold': [1.5, 2.0, 2.5, 3.0],
                    'stop_loss_pct': [0.015, 0.02, 0.025],
                    'take_profit_pct': [0.03, 0.04, 0.05],
                    'rsi_threshold': [35, 40, 45]
                }
            }
        }
        
        # Optimize each strategy
        optimized_results = {}
        
        for strategy_name, strategy_config in strategies.items():
            best_params, best_metrics, best_trades, best_score = optimize_strategy_parameters(
                strategy_name, 
                strategy_config['func'], 
                strategy_config['params']
            )
            
            optimized_results[strategy_name] = {
                'best_params': best_params,
                'best_metrics': best_metrics,
                'best_trades': best_trades,
                'best_score': best_score
            }
        
        # Rank optimized strategies
        ranked_strategies = sorted(
            [(name, result['best_score'], result['best_metrics'], result['best_params']) 
             for name, result in optimized_results.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        # Display final rankings
        print(f"\n🏆 FINAL OPTIMIZED STRATEGY RANKINGS")
        print("=" * 80)
        
        for i, (name, score, metrics, params) in enumerate(ranked_strategies):
            print(f"{i+1}. {name}")
            print(f"   Score: {score:.1f}")
            print(f"   Parameters: {params}")
            
            # Check if metrics is not None before accessing
            if metrics is not None:
                print(f"   Performance: {metrics['total_trades']} trades, "
                      f"Win Rate {metrics['win_rate']:.1f}%, "
                      f"Profit Factor {metrics['profit_factor']:.2f}, "
                      f"Sharpe {metrics['sharpe_ratio']:.2f}")
            else:
                print(f"   Performance: No valid results (fewer than 5 trades)")
            print()
        
        # Select best strategy with null safety
        if ranked_strategies and len(ranked_strategies) > 0:
            best_strategy_name = ranked_strategies[0][0]
            best_strategy = optimized_results[best_strategy_name]
            
            print(f"🎯 RECOMMENDED STRATEGY: {best_strategy_name}")
            
            # Safely access best_params and best_metrics
            best_params = best_strategy.get('best_params')
            best_metrics = best_strategy.get('best_metrics')
            
            if best_params:
                print(f"   Optimal Parameters: {best_params}")
            else:
                print(f"   Optimal Parameters: unavailable")
            
            if best_metrics:
                print(f"   Expected Performance: {best_metrics['total_trades']} trades, "
                      f"Win Rate {best_metrics['win_rate']:.1f}%, "
                      f"Profit Factor {best_metrics['profit_factor']:.2f}")
            else:
                print(f"   Expected Performance: metrics unavailable")
        else:
            print(f"🎯 NO VALID STRATEGY FOUND")
            print(f"   All strategies failed validation")
            return
        
        print(f"\n🎉 DEEP VALIDATION COMPLETE!")
        print(f"✅ Optimized all top 5 strategies")
        print(f"✅ Identified best performing strategy")
        print(f"🚀 Ready for implementation and Phase 3 testing")
        
        return {
            'optimized_results': optimized_results,
            'ranked_strategies': ranked_strategies,
            'best_strategy': best_strategy_name,
            'best_config': best_strategy
        }
        
    except Exception as e:
        print(f"❌ Deep validation failed: {e}")
        return None

if __name__ == "__main__":
    result = main()
