#!/usr/bin/env python3
"""
Strategy Enhancement Backtesting
Tests multiple parameter scenarios to validate profit enhancement hypotheses
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
    
    limit = months * 30 * 6  # ~1080 candles
    
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
        df = drop_incomplete_last_candle(df, '4h')
        
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=months*30)
        df = df[df['timestamp'] >= six_months_ago]
        
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

def enhanced_volume_reversal_strategy(df, params):
    """Enhanced volume reversal strategy with custom parameters"""
    trades = []
    
    # Add volume reversal indicators
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'].div(df['volume_sma'])
    df['volume_ratio'] = df['volume_ratio'].replace([float('inf'), -float('inf')], float('nan'))
    df['price_change'] = df['close'].pct_change()
    df['volatility'] = df['price_change'].rolling(window=20).std()
    
    df = df.dropna()
    
    for i in range(1, len(df)):
        sig = df.iloc[i]
        prev_sig = df.iloc[i-1]
        
        volatility_mean = df['volatility'].iloc[:i].mean() if i > 20 else sig['volatility']
        
        # Entry conditions with custom parameters
        entry_conditions = (
            sig['volume_ratio'] > params['volume_ratio_threshold'] and
            sig['close'] > prev_sig['close'] and
            prev_sig['close'] < prev_sig['sma200_4h'] and
            sig['rsi'] < params['rsi_threshold'] and
            sig['volatility'] > volatility_mean
        )
        
        if entry_conditions:
            entry_price = sig['close']
            outcome = simulate_trade(df, i, entry_price, 
                                   params['stop_loss_pct'], 
                                   params['take_profit_pct'], 
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
                    'volume_ratio_at_entry': sig['volume_ratio'],
                    'rsi_at_entry': sig['rsi'],
                    'volatility_at_entry': sig['volatility'],
                    'price_reversal_pct': (sig['close'] - prev_sig['close']) / prev_sig['close'] * 100
                })
    
    return trades

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=20, is_long=True):
    """Simulate a trade with proper risk management"""
    if is_long:
        stop_loss_price = entry_price * (1 - stop_loss_pct)
        take_profit_price = entry_price * (1 + take_profit_pct)
    else:
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
                'return_pct': -stop_loss_pct * 100,
                'holding_periods': j - entry_idx
            }
        
        # Check take profit
        if is_long and current_price >= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct * 100,
                'holding_periods': j - entry_idx
            }
        
        # Check signal reversal
        if j > entry_idx + 1:
            sig = current_candle
            if is_long and (sig['rsi'] > 70 or sig['close'] < sig['sma200_4h']):
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (current_price - entry_price) / entry_price * 100,
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

def calculate_performance_metrics(trades, initial_capital, risk_per_trade):
    """Calculate comprehensive performance metrics"""
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_return': 0,
            'profit_factor': 0,
            'total_return_pct': 0,
            'final_capital': initial_capital,
            'max_drawdown': 0,
            'sharpe_ratio': 0
        }
    
    total_trades = len(trades)
    winning_trades = [t for t in trades if t['return_pct'] > 0]
    losing_trades = [t for t in trades if t['return_pct'] < 0]
    
    win_rate = len(winning_trades) / total_trades * 100
    avg_return = sum(t['return_pct'] for t in trades) / total_trades
    
    # Calculate position-based returns
    position_size = initial_capital * risk_per_trade
    total_profit = sum(t['return_pct']/100 * position_size for t in winning_trades)
    total_loss = abs(sum(t['return_pct']/100 * position_size for t in losing_trades))
    
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    final_capital = initial_capital + total_profit - total_loss
    total_return_pct = (final_capital - initial_capital) / initial_capital * 100
    
    # Calculate drawdown (simplified)
    cumulative_returns = []
    running_capital = initial_capital
    for trade in trades:
        if trade['return_pct'] > 0:
            running_capital += trade['return_pct']/100 * position_size
        else:
            running_capital -= abs(trade['return_pct']/100) * position_size
        cumulative_returns.append((running_capital - initial_capital) / initial_capital * 100)
    
    max_drawdown = 0
    peak = 0
    for ret in cumulative_returns:
        if ret > peak:
            peak = ret
        drawdown = peak - ret
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # Simplified Sharpe ratio (annualized)
    if len(trades) > 1:
        returns = [t['return_pct'] for t in trades]
        avg_monthly_return = sum(returns) / len(returns)
        return_std = pd.Series(returns).std()
        sharpe_ratio = (avg_monthly_return * 12) / (return_std * 3.46) if return_std > 0 else 0
    else:
        sharpe_ratio = 0
    
    return {
        'total_trades': total_trades,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'avg_return': avg_return,
        'profit_factor': profit_factor,
        'total_return_pct': total_return_pct,
        'final_capital': final_capital,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio
    }

def run_backtest_scenarios():
    """Run all backtest scenarios"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    
    # Test scenarios
    scenarios = {
        'Baseline (Current)': {
            'risk_per_trade': 0.01,
            'volume_ratio_threshold': 2.0,
            'rsi_threshold': 35,
            'stop_loss_pct': 0.015,
            'take_profit_pct': 0.04,
            'max_holding_periods': 20
        },
        'Conservative Enhancement': {
            'risk_per_trade': 0.02,
            'volume_ratio_threshold': 1.8,
            'rsi_threshold': 38,
            'stop_loss_pct': 0.015,
            'take_profit_pct': 0.06,
            'max_holding_periods': 20
        },
        'Aggressive Enhancement': {
            'risk_per_trade': 0.03,
            'volume_ratio_threshold': 1.5,
            'rsi_threshold': 40,
            'stop_loss_pct': 0.015,
            'take_profit_pct': 0.10,
            'max_holding_periods': 20
        }
    }
    
    print("📊 STRATEGY ENHANCEMENT BACKTEST RESULTS")
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
            trades = enhanced_volume_reversal_strategy(df_ind, params)
            
            if trades:
                symbol_results[symbol] = {
                    'trades': len(trades),
                    'wins': sum(1 for t in trades if t['return_pct'] > 0),
                    'avg_return': sum(t['return_pct'] for t in trades) / len(trades)
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
        
        print("Symbol Breakdown:")
        for symbol, result in symbol_results.items():
            print(f"  {symbol}: {result['trades']} trades, {result['wins']} wins, {result['avg_return']:.1f}% avg")
        
        print()
    
    # Comparison summary
    print("📈 COMPARISON SUMMARY")
    print("=" * 50)
    print(f"{'Scenario':<25} {'Trades':<8} {'Win%':<6} {'Return%':<9} {'DD%':<6} {'Sharpe'}")
    print("-" * 70)
    
    for scenario_name, result in results.items():
        m = result['metrics']
        print(f"{scenario_name:<25} {m['total_trades']:<8} {m['win_rate']:<6.1f} {m['total_return_pct']:<9.1f} {m['max_drawdown']:<6.1f} {m['sharpe_ratio']:<6.2f}")
    
    print()
    
    # Recommendation
    best_scenario = max(results.items(), key=lambda x: x[1]['metrics']['total_return_pct'])
    print(f"🏆 RECOMMENDATION: {best_scenario[0]}")
    print(f"   Highest Return: {best_scenario[1]['metrics']['total_return_pct']:.1f}%")
    print(f"   Win Rate: {best_scenario[1]['metrics']['win_rate']:.1f}%")
    print(f"   Max Drawdown: {best_scenario[1]['metrics']['max_drawdown']:.1f}%")

if __name__ == "__main__":
    run_backtest_scenarios()