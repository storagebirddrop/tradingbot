#!/usr/bin/env python3
"""
Winning Momentum Strategy Implementation
SuperTrend + RSI + Volume with 2x leverage and long/short capability
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
    """Calculate all indicators for the winning strategy"""
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
    
    # SuperTrend calculation
    df = calculate_supertrend(df)
    
    # Multi-timeframe signals (simplified for 1h data)
    df['bullish_mtf'] = (df['ema_9'] > df['ema_21']) & (df['ema_21'] > df['ema_50'])
    df['bearish_mtf'] = (df['ema_9'] < df['ema_21']) & (df['ema_21'] < df['ema_50'])
    
    return df.dropna()

def calculate_supertrend(df, period=10, multiplier=3.0):
    """Calculate SuperTrend indicator"""
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = df['atr'].ffill()
    
    # Calculate basic bands
    df['final_upperband'] = hl2 + (multiplier * df['atr'])
    df['final_lowerband'] = hl2 - (multiplier * df['atr'])
    
    # Initialize Supertrend
    df['supertrend'] = True
    df['supertrend_direction'] = 1  # 1 for up, -1 for down
    
    for i in range(1, len(df)):
        if df['close'].iloc[i] <= df['final_lowerband'].iloc[i-1]:
            df.loc[df.index[i], 'supertrend'] = True
            df.loc[df.index[i], 'supertrend_direction'] = 1
        elif df['close'].iloc[i] >= df['final_upperband'].iloc[i-1]:
            df.loc[df.index[i], 'supertrend'] = False
            df.loc[df.index[i], 'supertrend_direction'] = -1
        else:
            df.loc[df.index[i], 'supertrend'] = df['supertrend'].iloc[i-1]
            df.loc[df.index[i], 'supertrend_direction'] = df['supertrend_direction'].iloc[i-1]
    
    return df

def winning_momentum_strategy(df, params):
    """Winning momentum strategy with SuperTrend + RSI + Volume"""
    trades = []
    
    for i in range(50, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Long entry conditions (ALL must be met)
        long_conditions = (
            current['supertrend'] == True and  # SuperTrend bullish
            current['rsi'] < params['rsi_long_threshold'] and  # RSI not overbought
            current['volume_ratio'] > params['volume_threshold'] and  # Volume confirmation
            current['price_momentum'] > params['momentum_threshold'] and  # Minimum momentum
            current['bullish_mtf'] == True  # Multi-timeframe confirmation
        )
        
        # Short entry conditions (ALL must be met)
        short_conditions = (
            current['supertrend'] == False and  # SuperTrend bearish
            current['rsi'] > params['rsi_short_threshold'] and  # RSI not oversold
            current['volume_ratio'] > params['volume_threshold'] and  # Volume confirmation
            current['price_momentum'] < -params['momentum_threshold'] and  # Minimum momentum
            current['bearish_mtf'] == True  # Multi-timeframe confirmation
        )
        
        if long_conditions:
            entry_price = current['close']
            
            # Dynamic position sizing based on signal strength
            signal_strength = calculate_signal_strength(current, params, direction='long')
            position_risk = min(params['max_risk_per_trade'], params['base_risk_per_trade'] * signal_strength)
            
            # ATR-based stop loss
            atr_pct = (current['atr'] * params['atr_multiplier']) / entry_price
            stop_loss_pct = max(params['min_stop_loss'], atr_pct)
            
            outcome = simulate_trade(df, i, entry_price, stop_loss_pct, 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=True)
            if outcome:
                trades.append({
                    'strategy': 'winning_momentum',
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
                    'volume_ratio': current['volume_ratio'],
                    'supertrend_direction': current['supertrend_direction']
                })
        
        elif short_conditions:
            entry_price = current['close']
            
            # Dynamic position sizing for shorts
            signal_strength = calculate_signal_strength(current, params, direction='short')
            position_risk = min(params['max_risk_per_trade'], params['base_risk_per_trade'] * signal_strength)
            
            # ATR-based stop loss
            atr_pct = (current['atr'] * params['atr_multiplier']) / entry_price
            stop_loss_pct = max(params['min_stop_loss'], atr_pct)
            
            outcome = simulate_trade(df, i, entry_price, stop_loss_pct, 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=False)
            if outcome:
                trades.append({
                    'strategy': 'winning_momentum',
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
                    'volume_ratio': current['volume_ratio'],
                    'supertrend_direction': current['supertrend_direction']
                })
    
    return trades

def calculate_signal_strength(current, params, direction='long'):
    """Calculate signal strength for dynamic position sizing"""
    if direction == 'long':
        # RSI strength (lower RSI = stronger signal)
        rsi_strength = max(0, (params['rsi_long_threshold'] - current['rsi']) / params['rsi_long_threshold'])
        
        # Volume strength
        volume_strength = min(2.0, (current['volume_ratio'] - 1) / 2)
        
        # Momentum strength
        momentum_strength = min(1.0, current['price_momentum'] / params['momentum_threshold'])
        
        # SuperTrend confirmation
        supertrend_strength = 1.0 if current['supertrend'] == True else 0.0
        
    else:  # short
        # RSI strength (higher RSI = stronger signal)
        rsi_strength = max(0, (current['rsi'] - params['rsi_short_threshold']) / (100 - params['rsi_short_threshold']))
        
        # Volume strength
        volume_strength = min(2.0, (current['volume_ratio'] - 1) / 2)
        
        # Momentum strength (negative momentum for shorts)
        momentum_strength = min(1.0, abs(current['price_momentum']) / params['momentum_threshold'])
        
        # SuperTrend confirmation
        supertrend_strength = 1.0 if current['supertrend'] == False else 0.0
    
    # Weighted average
    signal_strength = (
        rsi_strength * 0.3 +
        volume_strength * 0.3 +
        momentum_strength * 0.2 +
        supertrend_strength * 0.2
    )
    
    return max(0.5, min(1.5, signal_strength))  # Clamp between 0.5 and 1.5

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=48, is_long=True):
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
        
        # Check SuperTrend reversal
        if j > entry_idx + 6:  # Wait at least 6 periods
            sig = df.iloc[j]
            if is_long and sig['supertrend'] == False:  # SuperTrend turned bearish
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'supertrend_reversal',
                    'return_pct': (current_price - entry_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
            elif not is_long and sig['supertrend'] == True:  # SuperTrend turned bullish
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'supertrend_reversal',
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

def run_winning_strategy_backtest():
    """Run the winning momentum strategy backtest"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    
    # Winning strategy parameters based on research
    winning_params = {
        'rsi_long_threshold': 35,      # More aggressive than traditional 30
        'rsi_short_threshold': 65,     # More aggressive than traditional 70
        'volume_threshold': 1.5,       # Volume confirmation
        'momentum_threshold': 0.005,   # 0.5% minimum momentum
        'base_risk_per_trade': 0.08,   # 8% base risk (4% effective with 2x leverage)
        'max_risk_per_trade': 0.12,    # 12% maximum risk (6% effective)
        'take_profit_pct': 0.20,       # 20% take profit (appropriate for crypto)
        'min_stop_loss': 0.025,        # 2.5% minimum stop loss
        'atr_multiplier': 2.5,         # ATR multiplier for stops
        'max_holding_periods': 48       # 48 hours maximum
    }
    
    print("🚀 WINNING MOMENTUM STRATEGY BACKTEST")
    print("=" * 80)
    print(f"Strategy: SuperTrend + RSI + Volume")
    print(f"Leverage: 2x (effective)")
    print(f"Risk Range: 4-6% per trade")
    print(f"Take Profit: 20% (crypto-appropriate)")
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
        trades = winning_momentum_strategy(df, winning_params)
        
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
        return metrics
    
    for reason, count in exit_reasons.items():
        percentage = (count / total_trades) * 100
        print(f"{reason}: {count} ({percentage:.1f}%)")
    
    return metrics

if __name__ == "__main__":
    run_winning_strategy_backtest()