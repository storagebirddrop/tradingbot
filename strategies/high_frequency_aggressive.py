#!/usr/bin/env python3
"""
High-Frequency Aggressive Strategy
Uses 1h + 4h with much more aggressive parameters for meaningful returns
"""

import pandas as pd
import ccxt
from datetime import datetime, timedelta, timezone
from strategy import compute_4h_indicators, drop_incomplete_last_candle

def fetch_dual_timeframe_data(symbol, months=6):
    """Fetch data for 1h and 4h timeframes"""
    exchange = ccxt.phemex()
    exchange.set_sandbox_mode(True)
    
    data = {}
    
    # Fetch 4h data
    try:
        limit_4h = months * 30 * 6  # ~1080 candles
        ohlcv_4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=limit_4h)
        df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp','open','high','low','close','volume'])
        df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], unit='ms', utc=True)
        df_4h = df_4h.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
        df_4h = drop_incomplete_last_candle(df_4h, '4h')
        df_4h = compute_4h_indicators(df_4h)
        
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=months*30)
        df_4h = df_4h[df_4h['timestamp'] >= six_months_ago]
        
        data['4h'] = df_4h
        
    except Exception as e:
        print(f"Error fetching {symbol} 4h: {e}")
        return {}
    
    # Fetch 1h data
    try:
        limit_1h = months * 30 * 24  # ~4320 candles
        ohlcv_1h = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=limit_1h)
        df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp','open','high','low','close','volume'])
        df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], unit='ms', utc=True)
        df_1h = df_1h.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
        df_1h = drop_incomplete_last_candle(df_1h, '1h')
        
        df_1h = df_1h[df_1h['timestamp'] >= six_months_ago]
        
        # Add indicators to 1h
        df_1h['volume_sma'] = df_1h['volume'].rolling(window=20).mean()
        df_1h['volume_ratio'] = df_1h['volume'].div(df_1h['volume_sma'])
        df_1h['volume_ratio'] = df_1h['volume_ratio'].replace([float('inf'), -float('inf')], float('nan'))
        df_1h['rsi'] = df_1h['close'].rolling(window=14).mean()  # Simplified RSI
        df_1h['sma200'] = df_1h['close'].rolling(window=200).mean()
        df_1h['price_change'] = df_1h['close'].pct_change()
        df_1h['volatility'] = df_1h['price_change'].rolling(window=20).std()
        
        data['1h'] = df_1h.dropna()
        
    except Exception as e:
        print(f"Error fetching {symbol} 1h: {e}")
        return {}
    
    return data

def high_frequency_aggressive_strategy(symbol_data, params):
    """High-frequency aggressive strategy with dual timeframes"""
    trades = []
    
    df_4h = symbol_data['4h']
    df_1h = symbol_data['1h']
    
    if df_4h.empty or df_1h.empty:
        return trades
    
    # Scan every 1h candle for opportunities
    for i in range(1, len(df_1h)):
        sig_1h = df_1h.iloc[i]
        prev_sig_1h = df_1h.iloc[i-1]
        
        # Check for aggressive entry conditions
        score = 0
        
        # 1h signals (primary)
        if sig_1h['volume_ratio'] > params['volume_ratio_threshold_1h']:
            score += 2
        
        if sig_1h['rsi'] < params['rsi_threshold_1h']:
            score += 2
        
        if sig_1h['close'] > prev_sig_1h['close']:  # Price reversal
            score += 1
        
        if sig_1h['volatility'] > params['volatility_threshold']:
            score += 1
        
        # 4h confirmation (secondary)
        current_time = sig_1h['timestamp']
        recent_4h = df_4h[df_4h['timestamp'] <= current_time].tail(2)
        
        if not recent_4h.empty:
            latest_4h = recent_4h.iloc[-1]
            if latest_4h['rsi'] < params['rsi_threshold_4h']:
                score += 1
            if latest_4h['volume_ratio'] > params['volume_ratio_threshold_4h']:
                score += 1
        
        # Dynamic entry based on score
        min_score = 4  # Require minimum confidence
        
        # Lower threshold for very high volume
        if sig_1h['volume_ratio'] > 4.0:
            min_score = 3
        
        if score >= min_score:
            entry_price = sig_1h['close']
            
            # Dynamic position sizing and targets
            if score >= 6:
                position_risk = params['max_risk_per_trade']  # 6% for very strong
                take_profit = 0.15  # 15% target
            elif score >= 5:
                position_risk = params['high_risk_per_trade']  # 5% for strong
                take_profit = 0.12  # 12% target
            else:
                position_risk = params['risk_per_trade']  # 4% for normal
                take_profit = 0.10  # 10% target
            
            outcome = simulate_trade(df_1h, i, entry_price, 
                                   params['stop_loss_pct'], 
                                   take_profit, 
                                   params['max_holding_periods'], 
                                   is_long=True)
            
            if outcome:
                trades.append({
                    'entry_time': sig_1h['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'score': score,
                    'position_risk': position_risk,
                    'take_profit': take_profit,
                    'volume_ratio_1h': sig_1h['volume_ratio'],
                    'rsi_1h': sig_1h['rsi'],
                    'volatility_1h': sig_1h['volatility']
                })
    
    return trades

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=15, is_long=True):
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
        
        # Check signal reversal (more lenient)
        if j > entry_idx + 2:  # Allow more time
            sig = current_candle
            if is_long and (sig['rsi'] > 80 or sig['close'] < sig['sma200']):
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

def test_high_frequency_aggressive_strategy():
    """Test the high-frequency aggressive strategy"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    
    # High-frequency aggressive parameters
    params = {
        'risk_per_trade': 0.04,           # 4% base risk
        'high_risk_per_trade': 0.05,      # 5% for strong signals
        'max_risk_per_trade': 0.06,       # 6% for very strong signals
        'volume_ratio_threshold_1h': 1.3, # Very relaxed for 1h
        'volume_ratio_threshold_4h': 1.5, # Relaxed for 4h
        'rsi_threshold_1h': 50,          # Much more relaxed
        'rsi_threshold_4h': 45,          # Relaxed for 4h
        'volatility_threshold': 0.02,     # Minimum volatility
        'stop_loss_pct': 0.025,           # 2.5% stop loss
        'max_holding_periods': 15         # Shorter holding for quick trades
    }
    
    print("🔥 HIGH-FREQUENCY AGGRESSIVE STRATEGY")
    print("=" * 80)
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Risk Range: 4%-6% per trade (dynamic)")
    print(f"Take Profit: 10%-15% (dynamic)")
    print(f"Timeframes: 1h + 4h")
    print(f"Entry Threshold: Score 4-6 (very relaxed)")
    print(f"Symbols: {', '.join(symbols)}")
    print()
    
    all_trades = []
    symbol_results = {}
    
    for symbol in symbols:
        print(f"🔍 Analyzing {symbol}...")
        
        symbol_data = fetch_dual_timeframe_data(symbol)
        if not symbol_data:
            print(f"  ❌ No data available")
            continue
        
        trades = high_frequency_aggressive_strategy(symbol_data, params)
        
        if trades:
            symbol_results[symbol] = {
                'trades': len(trades),
                'wins': sum(1 for t in trades if t['return_pct'] > 0),
                'avg_return': sum(t['return_pct'] for t in trades) / len(trades),
                'avg_score': sum(t['score'] for t in trades) / len(trades),
                'avg_risk': sum(t['position_risk'] for t in trades) / len(trades),
                'avg_volume': sum(t['volume_ratio_1h'] for t in trades) / len(trades)
            }
            all_trades.extend(trades)
            
            print(f"  ✅ {len(trades)} trades, {symbol_results[symbol]['wins']} wins")
            print(f"  📊 Avg Score: {symbol_results[symbol]['avg_score']:.1f}/6")
            print(f"  💰 Avg Risk: {symbol_results[symbol]['avg_risk']*100:.1f}%")
            print(f"  📈 Avg Volume: {symbol_results[symbol]['avg_volume']:.1f}x")
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
    
    # Viability assessment
    print(f"\n📊 VIABILITY ASSESSMENT")
    if annual_return >= 20:
        print("✅ EXCELLENT: High return strategy")
    elif annual_return >= 10:
        print("✅ GOOD: Solid return strategy")
    elif annual_return >= 5:
        print("⚠️  MODERATE: Acceptable returns")
    else:
        print("❌ POOR: Low returns, needs improvement")
    
    if metrics['max_drawdown'] <= 15:
        print("✅ Risk: Acceptable drawdown")
    else:
        print("⚠️  Risk: High drawdown warning")
    
    return metrics

if __name__ == "__main__":
    test_high_frequency_aggressive_strategy()