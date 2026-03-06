#!/usr/bin/env python3
"""
Optimized Momentum Strategy Implementation
Relaxed parameters for more trading opportunities while maintaining quality
"""

import pandas as pd
import ccxt
from datetime import datetime, timedelta, timezone
import numpy as np

def fetch_historical_data(symbol, months=6):
    """Fetch historical data for strategy implementation"""
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
    """Calculate all indicators for the optimized strategy"""
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    # Handle division by zero
    rs = gain / loss
    rs = rs.replace([float('inf'), -float('inf')], float('nan'))
    # When loss is 0 (all gains), RSI should be 100
    rs = rs.fillna(float('inf'))  # Treat inf as all gains
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi'] = df['rsi'].fillna(100)  # All gains = 100 RSI
    
    # EMAs for multi-timeframe analysis
    df['ema_9'] = df['close'].ewm(span=9).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['ema_200'] = df['close'].ewm(span=200).mean()
    
    # ATR for volatility-based stops
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = true_range.rolling(window=14).mean()
    
    # Volume indicators
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'].div(df['volume_sma'])
    df['volume_ratio'] = df['volume_ratio'].replace([float('inf'), -float('inf')], float('nan'))
    
    # Price momentum
    df['price_change'] = df['close'].pct_change()
    df['price_momentum'] = df['close'].pct_change(periods=3)
    
    # MACD
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
    df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
    
    # Multi-timeframe signals
    df['bullish_mtf'] = (df['ema_9'] > df['ema_21']) & (df['ema_21'] > df['ema_50'])
    df['bearish_mtf'] = (df['ema_9'] < df['ema_21']) & (df['ema_21'] < df['ema_50'])
    
    return df.dropna()

def optimized_momentum_strategy(df, params):
    """Optimized momentum strategy with relaxed conditions"""
    trades = []
    
    for i in range(50, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Long entry conditions (more flexible - 3/5 indicators)
        long_signals = 0
        
        # SuperTrend approximation (using price vs EMAs)
        if current['close'] > current['ema_21'] and current['ema_9'] > current['ema_21']:
            long_signals += 1
        
        # RSI condition (more relaxed)
        if current['rsi'] < params['rsi_long_threshold']:
            long_signals += 1
        
        # Volume confirmation
        if current['volume_ratio'] > params['volume_threshold']:
            long_signals += 1
        
        # MACD momentum
        if current['macd'] > current['macd_signal'] and current['macd_histogram'] > 0:
            long_signals += 1
        
        # Price momentum
        if current['price_momentum'] > params['momentum_threshold']:
            long_signals += 1
        
        # Multi-timeframe confirmation
        if current['bullish_mtf']:
            long_signals += 1
        
        # Short entry conditions (more flexible - 3/5 indicators)
        short_signals = 0
        
        # SuperTrend approximation
        if current['close'] < current['ema_21'] and current['ema_9'] < current['ema_21']:
            short_signals += 1
        
        # RSI condition (more relaxed)
        if current['rsi'] > params['rsi_short_threshold']:
            short_signals += 1
        
        # Volume confirmation
        if current['volume_ratio'] > params['volume_threshold']:
            short_signals += 1
        
        # MACD momentum
        if current['macd'] < current['macd_signal'] and current['macd_histogram'] < 0:
            short_signals += 1
        
        # Price momentum
        if current['price_momentum'] < -params['momentum_threshold']:
            short_signals += 1
        
        # Multi-timeframe confirmation
        if current['bearish_mtf']:
            short_signals += 1
        
        # Entry decisions (need at least 3/6 signals)
        if long_signals >= 3:
            entry_price = current['close']
            
            # Dynamic position sizing based on signal strength
            signal_strength = long_signals / 6.0  # Normalize to 0-1
            position_risk = params['base_risk_per_trade'] * (0.5 + signal_strength)
            position_risk = min(params['max_risk_per_trade'], position_risk)
            
            # ATR-based stop loss
            atr_pct = (current['atr'] * params['atr_multiplier']) / entry_price
            stop_loss_pct = max(params['min_stop_loss'], atr_pct)
            
            outcome = simulate_trade(df, i, entry_price, stop_loss_pct, 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=True)
            if outcome:
                trades.append({
                    'strategy': 'optimized_momentum',
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
                    'signals_met': long_signals,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio'],
                    'macd_histogram': current['macd_histogram']
                })
        
        elif short_signals >= 3:
            entry_price = current['close']
            
            # Dynamic position sizing for shorts
            signal_strength = short_signals / 6.0  # Normalize to 0-1
            position_risk = params['base_risk_per_trade'] * (0.5 + signal_strength)
            position_risk = min(params['max_risk_per_trade'], position_risk)
            
            # ATR-based stop loss
            atr_pct = (current['atr'] * params['atr_multiplier']) / entry_price
            stop_loss_pct = max(params['min_stop_loss'], atr_pct)
            
            outcome = simulate_trade(df, i, entry_price, stop_loss_pct, 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=False)
            if outcome:
                trades.append({
                    'strategy': 'optimized_momentum',
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
                    'signals_met': short_signals,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio'],
                    'macd_histogram': current['macd_histogram']
                })
    
    return trades

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=24, is_long=True):
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
        if j > entry_idx + 4:  # Wait at least 4 periods
            sig = df.iloc[j]
            if is_long:
                # Multiple reversal signals for longs
                reversal_signals = 0
                if sig['rsi'] > 75:
                    reversal_signals += 1
                if sig['macd'] < sig['macd_signal']:
                    reversal_signals += 1
                if sig['close'] < sig['ema_21']:
                    reversal_signals += 1
                
                if reversal_signals >= 2:
                    return {
                        'exit_time': current_candle['timestamp'],
                        'exit_price': current_price,
                        'exit_reason': 'signal_reversal',
                        'return_pct': (current_price - entry_price) / entry_price * 100,
                        'holding_periods': j - entry_idx
                    }
            else:
                # Multiple reversal signals for shorts
                reversal_signals = 0
                if sig['rsi'] < 25:
                    reversal_signals += 1
                if sig['macd'] > sig['macd_signal']:
                    reversal_signals += 1
                if sig['close'] > sig['ema_21']:
                    reversal_signals += 1
                
                if reversal_signals >= 2:
                    return {
                        'exit_time': current_candle['timestamp'],
                        'exit_price': current_price,
                        'exit_reason': 'signal_reversal',
                        'return_pct': (entry_price - current_price) / entry_price * 100,
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

def run_optimized_strategy_backtest():
    """Run the optimized momentum strategy backtest"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    
    # Optimized strategy parameters (more relaxed)
    optimized_params = {
        'rsi_long_threshold': 45,      # Much more relaxed
        'rsi_short_threshold': 55,     # Much more relaxed
        'volume_threshold': 1.2,       # Lower volume requirement
        'momentum_threshold': 0.002,   # 0.2% minimum momentum (very low)
        'base_risk_per_trade': 0.08,   # 8% base risk (4% effective with 2x leverage)
        'max_risk_per_trade': 0.12,    # 12% maximum risk (6% effective)
        'take_profit_pct': 0.15,       # 15% take profit (more achievable)
        'min_stop_loss': 0.03,          # 3% minimum stop loss
        'atr_multiplier': 2.0,         # ATR multiplier for stops
        'max_holding_periods': 24       # 24 hours maximum (shorter)
    }
    
    print("🚀 OPTIMIZED MOMENTUM STRATEGY BACKTEST")
    print("=" * 80)
    print(f"Strategy: Multi-Indicator Momentum (3/6 signals required)")
    print(f"Indicators: EMA SuperTrend + RSI + MACD + Volume + Momentum")
    print(f"Leverage: 2x (effective)")
    print(f"Risk Range: 4-6% per trade")
    print(f"Take Profit: 15% (more achievable)")
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
        trades = optimized_momentum_strategy(df, optimized_params)
        
        if trades:
            symbol_results[symbol] = {
                'trades': len(trades),
                'wins': sum(1 for t in trades if t['return_pct'] > 0),
                'avg_return': sum(t['return_pct'] for t in trades) / len(trades),
                'avg_risk': sum(t['position_risk'] for t in trades) / len(trades),
                'avg_signal': sum(t['signal_strength'] for t in trades) / len(trades),
                'avg_signals_met': sum(t['signals_met'] for t in trades) / len(trades),
                'longs': sum(1 for t in trades if t['direction'] == 'long'),
                'shorts': sum(1 for t in trades if t['direction'] == 'short')
            }
            all_trades.extend(trades)
            
            print(f"  ✅ {len(trades)} trades, {symbol_results[symbol]['wins']} wins")
            print(f"  📊 Avg Signal: {symbol_results[symbol]['avg_signal']:.2f}")
            print(f"  🎯 Avg Signals Met: {symbol_results[symbol]['avg_signals_met']:.1f}/6")
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
    if annual_return >= 25:
        print("✅ EXCELLENT: High return strategy achieved")
    elif annual_return >= 15:
        print("✅ GOOD: Solid return strategy")
    elif annual_return >= 10:
        print("⚠️  MODERATE: Acceptable returns")
    else:
        print("❌ POOR: Low returns, needs improvement")
    
    if metrics['max_drawdown'] <= 20:
        print("✅ Risk: Low drawdown")
    elif metrics['max_drawdown'] <= 35:
        print("✅ Risk: Acceptable drawdown")
    else:
        print("⚠️  Risk: High drawdown warning")
    
    if metrics['win_rate'] >= 65:
        print("✅ Quality: High win rate")
    elif metrics['win_rate'] >= 60:
        print("✅ Quality: Good win rate")
    elif metrics['win_rate'] >= 55:
        print("✅ Quality: Acceptable win rate")
    else:
        print("⚠️  Quality: Low win rate warning")
    
    # Exit reason analysis
    exit_reasons = {}
    for trade in all_trades:
        reason = trade['exit_reason']
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    
    print(f"\n📊 EXIT REASON ANALYSIS")
    total_trades = len(all_trades)
    if total_trades == 0:
        print("No trades to analyze")
        return
    
    for reason, count in exit_reasons.items():
        percentage = (count / total_trades) * 100
        print(f"{reason}: {count} ({percentage:.1f}%)")
    
    return metrics

if __name__ == "__main__":
    run_optimized_strategy_backtest()