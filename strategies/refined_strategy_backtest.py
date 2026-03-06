#!/usr/bin/env python3
"""
Refined Strategy Testing
Tests hybrid approaches based on initial backtest results
"""

import pandas as pd
import ccxt
from datetime import datetime, timedelta, timezone
from strategy import compute_4h_indicators, drop_incomplete_last_candle

# Import functions from previous script
exec(open('strategy_enhancement_backtest.py').read())

def hybrid_volume_reversal_strategy(df, params):
    """Hybrid strategy with dynamic thresholds based on market conditions"""
    trades = []
    
    # Add volume reversal indicators
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'].div(df['volume_sma'])
    df['volume_ratio'] = df['volume_ratio'].replace([float('inf'), -float('inf')], float('nan'))
    df['price_change'] = df['close'].pct_change()
    df['volatility'] = df['volume'].rolling(window=20).std()
    
    df = df.dropna()
    
    for i in range(1, len(df)):
        sig = df.iloc[i]
        prev_sig = df.iloc[i-1]
        
        volatility_mean = df['volatility'].iloc[:i].mean() if i > 20 else sig['volatility']
        
        # Dynamic thresholds based on volume strength
        volume_strength = sig['volume_ratio']
        
        # High volume signals get relaxed conditions
        if volume_strength > 3.0:
            rsi_threshold = params['rsi_threshold'] + 5  # More relaxed
            volume_threshold = params['volume_ratio_threshold'] - 0.3
        elif volume_strength > 2.0:
            rsi_threshold = params['rsi_threshold']
            volume_threshold = params['volume_ratio_threshold']
        else:
            rsi_threshold = params['rsi_threshold'] - 5  # More strict
            volume_threshold = params['volume_ratio_threshold'] + 0.5
        
        # Entry conditions with dynamic thresholds
        entry_conditions = (
            volume_strength > volume_threshold and
            sig['close'] > prev_sig['close'] and
            prev_sig['close'] < prev_sig['sma200_4h'] and
            sig['rsi'] < rsi_threshold and
            sig['volatility'] > volatility_mean
        )
        
        if entry_conditions:
            entry_price = sig['close']
            
            # Dynamic take profit based on signal strength
            if volume_strength > 3.0 and sig['rsi'] < 30:
                take_profit = 0.08  # 8% for very strong signals
            elif volume_strength > 2.5:
                take_profit = 0.06  # 6% for strong signals
            else:
                take_profit = params['take_profit_pct']  # Default
            
            outcome = simulate_trade(df, i, entry_price, 
                                   params['stop_loss_pct'], 
                                   take_profit, 
                                   params['max_holding_periods'], 
                                   is_long=True)
            
            if outcome:
                trades.append({
                    'entry_time': sig['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'volume_ratio_at_entry': volume_strength,
                    'rsi_at_entry': sig['rsi'],
                    'volatility_at_entry': sig['volatility'],
                    'price_reversal_pct': (sig['close'] - prev_sig['close']) / prev_sig['close'] * 100
                })
    
    return trades

def run_refined_backtests():
    """Run refined strategy tests"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    
    # Refined test scenarios
    scenarios = {
        'Smart Volume Hybrid': {
            'risk_per_trade': 0.02,
            'volume_ratio_threshold': 1.8,
            'rsi_threshold': 38,
            'stop_loss_pct': 0.015,
            'take_profit_pct': 0.06,
            'max_holding_periods': 20
        },
        'Quality Over Quantity': {
            'risk_per_trade': 0.025,
            'volume_ratio_threshold': 2.2,
            'rsi_threshold': 36,
            'stop_loss_pct': 0.015,
            'take_profit_pct': 0.08,
            'max_holding_periods': 25
        },
        'Balanced Approach': {
            'risk_per_trade': 0.02,
            'volume_ratio_threshold': 1.6,
            'rsi_threshold': 42,
            'stop_loss_pct': 0.02,
            'take_profit_pct': 0.07,
            'max_holding_periods': 20
        }
    }
    
    print("🧠 REFINED STRATEGY BACKTEST RESULTS")
    print("=" * 80)
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Test Period: Last 6 months")
    print(f"Symbols: {', '.join(symbols)}")
    print()
    
    results = {}
    
    for scenario_name, params in scenarios.items():
        print(f"🔍 Testing: {scenario_name}")
        print("-" * 50)
        
        all_trades = []
        symbol_results = {}
        
        for symbol in symbols:
            df = fetch_historical_data(symbol)
            if df.empty:
                continue
                
            df_ind = compute_4h_indicators(df)
            trades = hybrid_volume_reversal_strategy(df_ind, params)
            
            if trades:
                symbol_results[symbol] = {
                    'trades': len(trades),
                    'wins': sum(1 for t in trades if t['return_pct'] > 0),
                    'avg_return': sum(t['return_pct'] for t in trades) / len(trades),
                    'avg_volume': sum(t['volume_ratio_at_entry'] for t in trades) / len(trades),
                    'avg_rsi': sum(t['rsi_at_entry'] for t in trades) / len(trades)
                }
                all_trades.extend(trades)
        
        # Calculate overall metrics
        metrics = calculate_performance_metrics(all_trades, initial_capital, params['risk_per_trade'])
        results[scenario_name] = {
            'metrics': metrics,
            'symbol_results': symbol_results
        }
        
        # Print results
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Win Rate: {metrics['win_rate']:.1f}%")
        print(f"Average Return: {metrics['avg_return']:.2f}%")
        print(f"Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"Total Return: {metrics['total_return_pct']:.1f}%")
        print(f"Final Capital: ${metrics['final_capital']:.2f}")
        print(f"Max Drawdown: {metrics['max_drawdown']:.1f}%")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        
        if symbol_results:
            print("Symbol Breakdown:")
            for symbol, result in symbol_results.items():
                print(f"  {symbol}: {result['trades']} trades, {result['wins']} wins, {result['avg_return']:.1f}% avg")
                print(f"         Avg Volume: {result['avg_volume']:.1f}, Avg RSI: {result['avg_rsi']:.1f}")
        
        print()
    
    # Find best performer
    best_scenario = max(results.items(), key=lambda x: x[1]['metrics']['total_return_pct'])
    print(f"🏆 BEST PERFORMER: {best_scenario[0]}")
    print(f"   Total Return: {best_scenario[1]['metrics']['total_return_pct']:.1f}%")
    print(f"   Win Rate: {best_scenario[1]['metrics']['win_rate']:.1f}%")
    print(f"   Profit Factor: {best_scenario[1]['metrics']['profit_factor']:.2f}")
    print(f"   Max Drawdown: {best_scenario[1]['metrics']['max_drawdown']:.1f}%")
    
    # Analysis and recommendations
    print("\n📊 ANALYSIS & RECOMMENDATIONS")
    print("=" * 40)
    
    viable_scenarios = {k: v for k, v in results.items() if v['metrics']['win_rate'] >= 60 and v['metrics']['profit_factor'] >= 1.5}
    
    if viable_scenarios:
        print("✅ VIABLE STRATEGIES (Win Rate ≥ 60%, Profit Factor ≥ 1.5):")
        for name, result in viable_scenarios.items():
            m = result['metrics']
            print(f"   {name}: {m['total_return_pct']:.1f}% return, {m['win_rate']:.1f}% win rate")
    else:
        print("❌ No strategies meet viability criteria")
    
    # Trade frequency analysis
    print(f"\n📈 TRADE FREQUENCY ANALYSIS:")
    for name, result in results.items():
        trades_per_month = result['metrics']['total_trades'] / 6
        print(f"   {name}: {trades_per_month:.1f} trades/month")
    
    return results

if __name__ == "__main__":
    run_refined_backtests()