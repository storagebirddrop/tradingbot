#!/usr/bin/env python3
"""
Aggressive Strategy Backtest
Optimized for higher returns with acceptable risk management
"""

import pandas as pd
import ccxt
from datetime import datetime, timedelta, timezone

def fetch_historical_data(symbol, months=6):
    """Fetch historical data for backtesting"""
    exchange = ccxt.phemex()
    exchange.set_sandbox_mode(True)
    
    try:
        limit = months * 30 * 24  # 1h candles
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
        
        # Remove incomplete last candle
        if len(df) > 0:
            time_diff = (datetime.now(timezone.utc) - df['timestamp'].iloc[-1]).total_seconds() / 3600
            if time_diff < 1:  # Last candle is incomplete
                df = df.iloc[:-1]
        
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=months*30)
        df = df[df['timestamp'] >= six_months_ago]
        
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

def calculate_indicators(df):
    """Calculate all necessary indicators for strategies"""
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Moving Averages
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean()
    
    # Bollinger Bands
    df['bb_middle'] = df['sma_20']
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # Volume
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'].div(df['volume_sma'])
    df['volume_ratio'] = df['volume_ratio'].replace([float('inf'), -float('inf')], float('nan'))
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = true_range.rolling(window=14).mean()
    
    # Volatility
    df['price_change'] = df['close'].pct_change()
    df['volatility'] = df['price_change'].rolling(window=20).std()
    
    return df.dropna()

def aggressive_mean_reversion_strategy(df, params):
    """Aggressive Mean Reversion with relaxed conditions"""
    trades = []
    
    for i in range(50, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Aggressive long entry conditions (relaxed thresholds)
        long_conditions = (
            current['rsi'] < params['rsi_oversold'] and  # Much higher RSI threshold
            current['volume_ratio'] > params['volume_threshold'] and  # Lower volume requirement
            current['volatility'] > params['min_volatility'] and
            current['close'] > prev['close']  # Price reversal
        )
        
        # Aggressive short entry conditions
        short_conditions = (
            current['rsi'] > params['rsi_overbought'] and  # Much lower RSI threshold
            current['volume_ratio'] > params['volume_threshold'] and  # Lower volume requirement
            current['volatility'] > params['min_volatility'] and
            current['close'] < prev['close']  # Price reversal
        )
        
        if long_conditions:
            entry_price = current['close']
            
            # Dynamic position sizing based on signal strength
            rsi_strength = (params['rsi_oversold'] - current['rsi']) / params['rsi_oversold']
            volume_strength = (current['volume_ratio'] - 1) / 2  # Normalize volume strength
            
            signal_strength = rsi_strength * 0.6 + volume_strength * 0.4
            
            if signal_strength > 0.7:  # Very strong signal
                position_risk = params['max_risk_per_trade']
                take_profit = params['take_profit_pct'] * 1.5
            elif signal_strength > 0.4:  # Strong signal
                position_risk = params['risk_per_trade']
                take_profit = params['take_profit_pct']
            else:  # Moderate signal
                position_risk = params['min_risk_per_trade']
                take_profit = params['take_profit_pct'] * 0.8
            
            outcome = simulate_trade(df, i, entry_price, params['stop_loss_pct'], 
                                   take_profit, params['max_holding_periods'], 
                                   is_long=True)
            if outcome:
                trades.append({
                    'strategy': 'aggressive_mean_reversion',
                    'direction': 'long',
                    'entry_time': current['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'position_risk': position_risk,
                    'signal_strength': signal_strength,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio']
                })
        
        elif short_conditions:
            entry_price = current['close']
            
            # Dynamic position sizing for shorts
            rsi_strength = (current['rsi'] - params['rsi_overbought']) / (100 - params['rsi_overbought'])
            volume_strength = (current['volume_ratio'] - 1) / 2
            
            signal_strength = rsi_strength * 0.6 + volume_strength * 0.4
            
            if signal_strength > 0.7:
                position_risk = params['max_risk_per_trade']
                take_profit = params['take_profit_pct'] * 1.5
            elif signal_strength > 0.4:
                position_risk = params['risk_per_trade']
                take_profit = params['take_profit_pct']
            else:
                position_risk = params['min_risk_per_trade']
                take_profit = params['take_profit_pct'] * 0.8
            
            outcome = simulate_trade(df, i, entry_price, params['stop_loss_pct'], 
                                   take_profit, params['max_holding_periods'], 
                                   is_long=False)
            if outcome:
                trades.append({
                    'strategy': 'aggressive_mean_reversion',
                    'direction': 'short',
                    'entry_time': current['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'position_risk': position_risk,
                    'signal_strength': signal_strength,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio']
                })
    
    return trades

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=12, is_long=True):
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
        elif not is_long and current_price >= stop_loss_price:
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
        elif not is_long and current_price <= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct * 100,
                'holding_periods': j - entry_idx
            }
        
        # Check signal reversal (more lenient)
        if j > entry_idx + 2:
            sig = current_candle
            if is_long and sig['rsi'] > 70:  # Only RSI reversal
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (current_price - entry_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
            elif not is_long and sig['rsi'] < 30:  # Only RSI reversal
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (entry_price - current_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
    
    # Max holding period reached
    actual_holding = min(max_holding_periods, (len(df) - 1) - entry_idx)
    final_idx = entry_idx + actual_holding
    final_price = df.iloc[final_idx]['close']
    return_pct = (final_price - entry_price) / entry_price * 100 if is_long else (entry_price - final_price) / entry_price * 100
    
    return {
        'exit_time': df.iloc[final_idx]['timestamp'],
        'exit_price': final_price,
        'exit_reason': 'max_holding',
        'return_pct': return_pct,
        'holding_periods': actual_holding
    }

def calculate_performance_metrics(trades, initial_capital):
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
            'sharpe_ratio': 0,
            'avg_position_risk': 0,
            'long_trades': 0,
            'short_trades': 0
        }
    
    total_trades = len(trades)
    winning_trades = [t for t in trades if t['return_pct'] > 0]
    losing_trades = [t for t in trades if t['return_pct'] < 0]
    long_trades = [t for t in trades if t.get('direction') == 'long']
    short_trades = [t for t in trades if t.get('direction') == 'short']
    
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
        'long_trades': len(long_trades),
        'short_trades': len(short_trades),
        'win_rate': win_rate,
        'avg_return': avg_return,
        'profit_factor': profit_factor,
        'total_return_pct': total_return_pct,
        'final_capital': final_capital,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'avg_position_risk': avg_position_risk
    }

def run_aggressive_backtest():
    """Run aggressive strategy backtest"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    
    # Aggressive parameters - much more relaxed
    aggressive_params = {
        'rsi_oversold': 45,      # Much higher (was 30)
        'rsi_overbought': 55,    # Much lower (was 70)
        'volume_threshold': 1.2, # Much lower (was 1.5)
        'min_volatility': 0.008, # Lower (was 0.012)
        'min_risk_per_trade': 0.03,  # 3% minimum
        'risk_per_trade': 0.04,      # 4% base
        'max_risk_per_trade': 0.05,  # 5% maximum
        'stop_loss_pct': 0.025,       # 2.5% stop loss
        'take_profit_pct': 0.08,      # 8% take profit
        'max_holding_periods': 12      # Shorter holding
    }
    
    print("🚀 AGGRESSIVE STRATEGY BACKTEST")
    print("=" * 80)
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Risk Range: 3%-5% per trade")
    print(f"Take Profit: 8% (higher targets)")
    print(f"Entry: Relaxed RSI (45/55) + Volume (>1.2x)")
    print(f"Test Period: Last 6 months")
    print(f"Symbols: {', '.join(symbols)}")
    print()
    
    all_trades = []
    symbol_results = {}
    
    for symbol in symbols:
        print(f"🔍 Analyzing {symbol}...")
        
        df = fetch_historical_data(symbol)
        if df.empty:
            print(f"  ❌ No data available")
            continue
        
        df = calculate_indicators(df)
        trades = aggressive_mean_reversion_strategy(df, aggressive_params)
        
        if trades:
            symbol_results[symbol] = {
                'trades': len(trades),
                'wins': sum(1 for t in trades if t['return_pct'] > 0),
                'avg_return': sum(t['return_pct'] for t in trades) / len(trades),
                'avg_risk': sum(t['position_risk'] for t in trades) / len(trades),
                'avg_signal': sum(t['signal_strength'] for t in trades) / len(trades),
                'longs': sum(1 for t in trades if t['direction'] == 'long'),
                'shorts': sum(1 for t in trades if t['direction'] == 'short')
            }
            all_trades.extend(trades)
            
            print(f"  ✅ {len(trades)} trades, {symbol_results[symbol]['wins']} wins")
            print(f"  📊 Avg Signal: {symbol_results[symbol]['avg_signal']:.2f}")
            print(f"  💰 Avg Risk: {symbol_results[symbol]['avg_risk']*100:.1f}%")
            print(f"  📈 Avg Return: {symbol_results[symbol]['avg_return']:.2f}%")
            print(f"  🔄 Long/Short: {symbol_results[symbol]['longs']}/{symbol_results[symbol]['shorts']}")
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
    print(f"Long/Short: {metrics['long_trades']}/{metrics['short_trades']}")
    
    # Trade frequency
    trades_per_month = metrics['total_trades'] / 6
    print(f"\n📊 TRADE FREQUENCY")
    print(f"Trades per month: {trades_per_month:.1f}")
    
    # Annual projection
    annual_return = metrics['total_return_pct'] * 2
    print(f"\n🎯 ANNUAL PROJECTION")
    print(f"Projected Annual Return: {annual_return:.1f}%")
    
    # Viability assessment
    print(f"\n📊 VIABILITY ASSESSMENT")
    if annual_return >= 15:
        print("✅ EXCELLENT: High return strategy")
    elif annual_return >= 10:
        print("✅ GOOD: Solid return strategy")
    elif annual_return >= 5:
        print("⚠️  MODERATE: Acceptable returns")
    else:
        print("❌ POOR: Low returns, needs improvement")
    
    if metrics['max_drawdown'] <= 15:
        print("✅ Risk: Low drawdown")
    elif metrics['max_drawdown'] <= 25:
        print("✅ Risk: Acceptable drawdown")
    else:
        print("⚠️  Risk: High drawdown warning")
    
    if metrics['win_rate'] >= 60:
        print("✅ Quality: High win rate")
    elif metrics['win_rate'] >= 50:
        print("✅ Quality: Good win rate")
    else:
        print("⚠️  Quality: Low win rate warning")
    
    return metrics

if __name__ == "__main__":
    run_aggressive_backtest()