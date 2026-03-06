#!/usr/bin/env python3
"""
Ultra-Aggressive Strategy Implementation
Combines multi-timeframe analysis with higher risk parameters for meaningful returns
"""

import pandas as pd
import ccxt
from datetime import datetime, timedelta, timezone
from strategy import compute_4h_indicators, drop_incomplete_last_candle

def fetch_multi_timeframe_data(symbol, months=6):
    """Fetch data for multiple timeframes"""
    exchange = ccxt.phemex()
    exchange.set_sandbox_mode(True)
    
    timeframes = ['30m', '1h', '4h']
    data = {}
    
    for tf in timeframes:
        try:
            limit = months * 30 * (24 // int(tf.replace('h', '').replace('m', '')))  # Approximate candles needed
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
            df = drop_incomplete_last_candle(df, tf)
            
            six_months_ago = datetime.now(timezone.utc) - timedelta(days=months*30)
            df = df[df['timestamp'] >= six_months_ago]
            
            if tf == '4h':
                df = compute_4h_indicators(df)
            
            data[tf] = df
            
        except Exception as e:
            print(f"Error fetching {symbol} {tf}: {e}")
            return {}
    
    return data

def ultra_aggressive_multi_timeframe_strategy(symbol_data, params):
    """Ultra-aggressive multi-timeframe strategy"""
    trades = []
    
    df_4h = symbol_data['4h']
    df_1h = symbol_data['1h']
    df_30m = symbol_data['30m']
    
    if df_4h.empty or df_1h.empty or df_30m.empty:
        return trades
    
    # Add indicators to all timeframes
    for tf, df in symbol_data.items():
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'].div(df['volume_sma'])
        df['volume_ratio'] = df['volume_ratio'].replace([float('inf'), -float('inf')], float('nan'))
        if tf != '4h':  # 4h already has indicators
            df['rsi'] = df['close'].rolling(window=14).mean()  # Simplified RSI
            df['sma200'] = df['close'].rolling(window=200).mean()
    
    # Align timestamps
    for i in range(1, len(df_4h)):
        sig_4h = df_4h.iloc[i]
        prev_sig_4h = df_4h.iloc[i-1]
        
        # Find corresponding 1h and 30m signals
        current_time = sig_4h['timestamp']
        
        # Look for signals in recent timeframes
        recent_1h = df_1h[df_1h['timestamp'] <= current_time].tail(3)
        recent_30m = df_30m[df_30m['timestamp'] <= current_time].tail(6)
        
        if recent_1h.empty or recent_30m.empty:
            continue
        
        # Multi-timeframe signal scoring
        score = 0
        
        # 4h: Main trend and regime (2 points)
        if (sig_4h['volume_ratio'] > params['volume_ratio_threshold_4h'] and
            sig_4h['close'] > prev_sig_4h['close'] and
            sig_4h['rsi'] < params['rsi_threshold_4h']):
            score += 2
        
        # 1h: Momentum confirmation (2 points)
        latest_1h = recent_1h.iloc[-1]
        if (latest_1h['volume_ratio'] > params['volume_ratio_threshold_1h'] and
            latest_1h['rsi'] < params['rsi_threshold_1h']):
            score += 2
        
        # 30m: Early entry signal (1 point)
        latest_30m = recent_30m.iloc[-1]
        if (latest_30m['volume_ratio'] > params['volume_ratio_threshold_30m'] and
            latest_30m['close'] > latest_30m['sma200']):
            score += 1
        
        # Enter with high confidence (score >= 4) or medium confidence (score >= 3 with strong volume)
        strong_volume = sig_4h['volume_ratio'] > 3.0 or latest_1h['volume_ratio'] > 3.0
        
        if (score >= 4) or (score >= 3 and strong_volume):
            entry_price = sig_4h['close']
            
            # Dynamic position sizing based on signal strength
            if score >= 5:
                position_risk = params['max_risk_per_trade']  # 5% for very strong signals
                take_profit = 0.12  # 12% target
            elif score >= 4:
                position_risk = params['high_risk_per_trade']  # 4% for strong signals
                take_profit = 0.10  # 10% target
            else:
                position_risk = params['risk_per_trade']  # 3% for medium signals
                take_profit = 0.08  # 8% target
            
            outcome = simulate_trade(df_4h, i, entry_price, 
                                   params['stop_loss_pct'], 
                                   take_profit, 
                                   params['max_holding_periods'], 
                                   is_long=True)
            
            if outcome:
                trades.append({
                    'entry_time': sig_4h['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'score': score,
                    'position_risk': position_risk,
                    'take_profit': take_profit,
                    'volume_ratio_4h': sig_4h['volume_ratio'],
                    'rsi_4h': sig_4h['rsi']
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
            if is_long and (sig['rsi'] > 75 or sig['close'] < sig['sma200_4h']):
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

def calculate_performance_metrics(trades, initial_capital):
    """Calculate comprehensive performance metrics with variable position sizing"""
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_return': 0,
            'profit_factor': 0,
            'total_return_pct': 0,
            'final_capital': initial_capital,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'avg_position_risk': 0
        }
    
    total_trades = len(trades)
    winning_trades = [t for t in trades if t['return_pct'] > 0]
    losing_trades = [t for t in trades if t['return_pct'] < 0]
    
    win_rate = len(winning_trades) / total_trades * 100
    avg_return = sum(t['return_pct'] for t in trades) / total_trades
    
    # Calculate returns with variable position sizing
    total_profit = 0
    total_loss = 0
    avg_position_risk = sum(t['position_risk'] for t in trades) / total_trades
    
    for trade in trades:
        position_size = initial_capital * trade['position_risk']
        if trade['return_pct'] > 0:
            total_profit += trade['return_pct']/100 * position_size
        else:
            total_loss += abs(trade['return_pct']/100) * position_size
    
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    final_capital = initial_capital + total_profit - total_loss
    total_return_pct = (final_capital - initial_capital) / initial_capital * 100
    
    # Calculate drawdown
    cumulative_returns = []
    running_capital = initial_capital
    for trade in trades:
        position_size = initial_capital * trade['position_risk']
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
    
    # Sharpe ratio
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
        'sharpe_ratio': sharpe_ratio,
        'avg_position_risk': avg_position_risk
    }

def test_ultra_aggressive_strategy():
    """Test the ultra-aggressive multi-timeframe strategy"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    
    # Ultra-aggressive parameters
    params = {
        'risk_per_trade': 0.03,           # 3% base risk
        'high_risk_per_trade': 0.04,      # 4% for strong signals
        'max_risk_per_trade': 0.05,       # 5% for very strong signals
        'volume_ratio_threshold_4h': 1.8,  # Relaxed for 4h
        'volume_ratio_threshold_1h': 1.6,  # More relaxed for 1h
        'volume_ratio_threshold_30m': 1.4, # Most relaxed for 30m
        'rsi_threshold_4h': 40,           # Relaxed RSI
        'rsi_threshold_1h': 45,           # More relaxed for 1h
        'stop_loss_pct': 0.02,            # 2% stop loss
        'max_holding_periods': 30          # Longer holding
    }
    
    print("🚀 ULTRA-AGGRESSIVE MULTI-TIMEFRAME STRATEGY")
    print("=" * 80)
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Risk Range: 3%-5% per trade (dynamic)")
    print(f"Take Profit: 8%-12% (dynamic)")
    print(f"Timeframes: 30m + 1h + 4h")
    print(f"Symbols: {', '.join(symbols)}")
    print()
    
    all_trades = []
    symbol_results = {}
    
    for symbol in symbols:
        print(f"🔍 Analyzing {symbol}...")
        
        symbol_data = fetch_multi_timeframe_data(symbol)
        if not symbol_data:
            print(f"  ❌ No data available")
            continue
        
        trades = ultra_aggressive_multi_timeframe_strategy(symbol_data, params)
        
        if trades:
            symbol_results[symbol] = {
                'trades': len(trades),
                'wins': sum(1 for t in trades if t['return_pct'] > 0),
                'avg_return': sum(t['return_pct'] for t in trades) / len(trades),
                'avg_score': sum(t['score'] for t in trades) / len(trades),
                'avg_risk': sum(t['position_risk'] for t in trades) / len(trades)
            }
            all_trades.extend(trades)
            
            print(f"  ✅ {len(trades)} trades, {symbol_results[symbol]['wins']} wins")
            print(f"  📊 Avg Score: {symbol_results[symbol]['avg_score']:.1f}/5")
            print(f"  💰 Avg Risk: {symbol_results[symbol]['avg_risk']*100:.1f}%")
        else:
            print(f"  ❌ No trades generated")
    
    # Calculate overall metrics
    metrics = calculate_performance_metrics(all_trades, initial_capital)
    
    print(f"\n📈 OVERALL PERFORMANCE")
    print("=" * 50)
    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Win Rate: {metrics['win_rate']:.1f}%")
    print(f"Average Return: {metrics['avg_return']:.2f}%")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"Average Position Risk: {metrics['avg_position_risk']*100:.1f}%")
    print(f"Total Return: {metrics['total_return_pct']:.1f}%")
    print(f"Final Capital: ${metrics['final_capital']:.2f}")
    print(f"Max Drawdown: {metrics['max_drawdown']:.1f}%")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    
    # Trade frequency
    trades_per_month = metrics['total_trades'] / 6
    print(f"\n📊 TRADE FREQUENCY")
    print(f"Trades per month: {trades_per_month:.1f}")
    
    # Annual projection
    annual_return = metrics['total_return_pct'] * 2  # 6 months to annual
    print(f"\n🎯 ANNUAL PROJECTION")
    print(f"Projected Annual Return: {annual_return:.1f}%")
    
    # Score distribution
    if all_trades:
        score_dist = {}
        for trade in all_trades:
            score = trade['score']
            score_dist[score] = score_dist.get(score, 0) + 1
        
        print(f"\n📊 SIGNAL SCORE DISTRIBUTION")
        for score in sorted(score_dist.keys()):
            count = score_dist[score]
            print(f"Score {score}: {count} trades")
    
    return metrics

if __name__ == "__main__":
    test_ultra_aggressive_strategy()