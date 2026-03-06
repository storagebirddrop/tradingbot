#!/usr/bin/env python3
"""
Comprehensive Strategy Backtesting
Tests Enhanced Mean Reversion, Hybrid Adaptive, and Multi-Indicator strategies
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
    # Handle division by zero
    rs = gain / loss
    rs = rs.replace([float('inf'), -float('inf')], float('nan'))
    # When loss is 0 (all gains), RSI should be 100
    rs = rs.fillna(float('inf'))  # Treat inf as all gains
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi'] = df['rsi'].fillna(100)  # All gains = 100 RSI
    
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
    
    # Trend detection
    df['price_trend'] = df['sma_20'].pct_change(periods=10)
    
    return df.dropna()

def enhanced_mean_reversion_strategy(df, params):
    """Enhanced Mean Reversion Strategy"""
    trades = []
    position_open = False
    
    i = 50
    while i < len(df):
        current = df.iloc[i]
        
        # Skip if position is already open
        if position_open:
            i += 1
            continue
        
        # Long entry conditions
        long_conditions = (
            current['rsi'] < params['rsi_oversold'] and
            current['close'] < current['bb_lower'] and
            current['volume_ratio'] > params['volume_threshold'] and
            current['volatility'] > params['min_volatility']
        )
        
        # Short entry conditions
        short_conditions = (
            current['rsi'] > params['rsi_overbought'] and
            current['close'] > current['bb_upper'] and
            current['volume_ratio'] > params['volume_threshold'] and
            current['volatility'] > params['min_volatility']
        )
        
        if long_conditions:
            entry_price = current['close']
            position_risk = params['risk_per_trade']
            outcome = simulate_trade(df, i, entry_price, params['stop_loss_pct'], 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=True)
            if outcome:
                trades.append({
                    'strategy': 'enhanced_mean_reversion',
                    'direction': 'long',
                    'entry_time': current['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'position_risk': position_risk,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio']
                })
                position_open = True
                i += outcome['holding_periods']  # Skip ahead while position is open
                position_open = False
            else:
                i += 1
        
        elif short_conditions:
            entry_price = current['close']
            position_risk = params['risk_per_trade']
            outcome = simulate_trade(df, i, entry_price, params['stop_loss_pct'], 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=False)
            if outcome:
                trades.append({
                    'strategy': 'enhanced_mean_reversion',
                    'direction': 'short',
                    'entry_time': current['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'position_risk': position_risk,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio']
                })
                position_open = True
                i += outcome['holding_periods']  # Skip ahead while position is open
                position_open = False
            else:
                i += 1
        else:
            i += 1
    
    return trades

def hybrid_adaptive_strategy(df, params):
    """Hybrid Adaptive Strategy with regime detection"""
    trades = []
    in_position = False
    
    for i in range(50, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Skip if already in position
        if in_position:
            continue
        
        # Regime detection
        if current['price_trend'] > params['trend_threshold'] and current['volatility'] > params['volatility_threshold']:
            regime = "trending_bull"
        elif current['price_trend'] < -params['trend_threshold'] and current['volatility'] > params['volatility_threshold']:
            regime = "trending_bear"
        else:
            regime = "ranging"
        
        # Strategy selection based on regime
        if regime == "trending_bull":
            # Momentum breakout (long only)
            entry_conditions = (
                current['close'] > current['sma_20'] and
                current['close'] > prev['close'] and
                current['volume_ratio'] > params['volume_threshold'] and
                current['rsi'] > 50 and current['rsi'] < 70
            )
            direction = 'long'
        elif regime == "trending_bear":
            # Momentum breakdown (short only)
            entry_conditions = (
                current['close'] < current['sma_20'] and
                current['close'] < prev['close'] and
                current['volume_ratio'] > params['volume_threshold'] and
                current['rsi'] < 50 and current['rsi'] > 30
            )
            direction = 'short'
        else:
            # Mean reversion (both directions)
            long_conditions = (
                current['rsi'] < params['rsi_oversold'] and
                current['volume_ratio'] > params['volume_threshold']
            )
            short_conditions = (
                current['rsi'] > params['rsi_overbought'] and
                current['volume_ratio'] > params['volume_threshold']
            )
            
            if long_conditions:
                entry_conditions = True
                direction = 'long'
            elif short_conditions:
                entry_conditions = True
                direction = 'short'
            else:
                entry_conditions = False
                direction = None
        
        if entry_conditions and direction:
            entry_price = current['close']
            position_risk = params['risk_per_trade']
            outcome = simulate_trade(df, i, entry_price, params['stop_loss_pct'], 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=(direction == 'long'))
            if outcome:
                trades.append({
                    'strategy': 'hybrid_adaptive',
                    'direction': direction,
                    'regime': regime,
                    'entry_time': current['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'position_risk': position_risk,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio']
                })
                in_position = True
                # Skip ahead by holding periods to avoid overlapping trades
                i += outcome['holding_periods']
                in_position = False
    
    return trades

def multi_indicator_strategy(df, params):
    """Multi-Indicator System with 3/5 confirmation"""
    trades = []
    
    for i in range(50, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Count indicators for long signal
        long_indicators = 0
        if current['rsi'] < params['rsi_oversold']:
            long_indicators += 1
        if current['close'] < current['bb_lower']:
            long_indicators += 1
        if current['volume_ratio'] > params['volume_threshold']:
            long_indicators += 1
        if current['volatility'] > params['min_volatility']:
            long_indicators += 1
        if current['close'] > prev['close']:  # Price reversal
            long_indicators += 1
        
        # Count indicators for short signal
        short_indicators = 0
        if current['rsi'] > params['rsi_overbought']:
            short_indicators += 1
        if current['close'] > current['bb_upper']:
            short_indicators += 1
        if current['volume_ratio'] > params['volume_threshold']:
            short_indicators += 1
        if current['volatility'] > params['min_volatility']:
            short_indicators += 1
        if current['close'] < prev['close']:  # Price reversal
            short_indicators += 1
        
        # Entry decisions (3/5 indicators required)
        if long_indicators >= 3:
            entry_price = current['close']
            position_risk = params['risk_per_trade']
            outcome = simulate_trade(df, i, entry_price, params['stop_loss_pct'], 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=True)
            if outcome:
                trades.append({
                    'strategy': 'multi_indicator',
                    'direction': 'long',
                    'indicators_met': long_indicators,
                    'entry_time': current['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'position_risk': position_risk,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio']
                })
        
        elif short_indicators >= 3:
            entry_price = current['close']
            position_risk = params['risk_per_trade']
            outcome = simulate_trade(df, i, entry_price, params['stop_loss_pct'], 
                                   params['take_profit_pct'], params['max_holding_periods'], 
                                   is_long=False)
            if outcome:
                trades.append({
                    'strategy': 'multi_indicator',
                    'direction': 'short',
                    'indicators_met': short_indicators,
                    'entry_time': current['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods'],
                    'position_risk': position_risk,
                    'rsi_at_entry': current['rsi'],
                    'volume_ratio': current['volume_ratio']
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
        
        # Check stop loss (use intraday extremes)
        if is_long and current_candle['low'] <= stop_loss_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': stop_loss_price,
                'exit_reason': 'stop_loss',
                'return_pct': -stop_loss_pct * 100,
                'holding_periods': j - entry_idx
            }
        elif not is_long and current_candle['high'] >= stop_loss_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': stop_loss_price,
                'exit_reason': 'stop_loss',
                'return_pct': -stop_loss_pct * 100,
                'holding_periods': j - entry_idx
            }
        
        # Check take profit (use intraday extremes)
        if is_long and current_candle['high'] >= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct * 100,
                'holding_periods': j - entry_idx
            }
        elif not is_long and current_candle['low'] <= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct * 100,
                'holding_periods': j - entry_idx
            }
        
        # Check signal reversal
        if j > entry_idx + 3:
            sig = current_candle
            if is_long and (sig['rsi'] > 75 or sig['close'] < sig['sma_20']):
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (current_price - entry_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
            elif not is_long and (sig['rsi'] < 25 or sig['close'] > sig['sma_20']):
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
    if cumulative_returns:
        peak = cumulative_returns[0]  # Initialize with first value
        for ret in cumulative_returns:
            if ret > peak:
                peak = ret
            drawdown = peak - ret
            if drawdown > max_drawdown:
                max_drawdown = drawdown
    else:
        peak = 0
    
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

def run_comprehensive_backtest():
    """Run comprehensive backtest for all 3 strategies"""
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT']
    initial_capital = 50.0
    
    # Strategy parameters
    enhanced_params = {
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'volume_threshold': 1.5,
        'min_volatility': 0.012,
        'risk_per_trade': 0.025,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.06,
        'max_holding_periods': 15
    }
    
    hybrid_params = {
        'trend_threshold': 0.005,
        'volatility_threshold': 0.015,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'volume_threshold': 1.4,
        'risk_per_trade': 0.02,
        'stop_loss_pct': 0.025,
        'take_profit_pct': 0.05,
        'max_holding_periods': 18
    }
    
    multi_params = {
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'volume_threshold': 1.8,
        'min_volatility': 0.015,
        'risk_per_trade': 0.02,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'max_holding_periods': 12
    }
    
    print("🚀 COMPREHENSIVE STRATEGY BACKTEST")
    print("=" * 80)
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Test Period: Last 6 months")
    print(f"Symbols: {', '.join(symbols)}")
    print()
    
    results = {}
    
    # Test Enhanced Mean Reversion
    print("🔍 TESTING ENHANCED MEAN REVERSION")
    print("-" * 50)
    
    enhanced_trades = []
    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        df = fetch_historical_data(symbol)
        if df.empty:
            print(f"  ❌ No data available")
            continue
        
        df = calculate_indicators(df)
        trades = enhanced_mean_reversion_strategy(df, enhanced_params)
        enhanced_trades.extend(trades)
        print(f"  ✅ {len(trades)} trades")
    
    enhanced_metrics = calculate_performance_metrics(enhanced_trades, initial_capital)
    results['Enhanced Mean Reversion'] = enhanced_metrics
    
    print(f"\nEnhanced Mean Reversion Results:")
    print(f"  Total Trades: {enhanced_metrics['total_trades']}")
    print(f"  Win Rate: {enhanced_metrics['win_rate']:.1f}%")
    print(f"  Total Return: {enhanced_metrics['total_return_pct']:.1f}%")
    print(f"  Profit Factor: {enhanced_metrics['profit_factor']:.2f}")
    print(f"  Max Drawdown: {enhanced_metrics['max_drawdown']:.1f}%")
    print(f"  Sharpe Ratio: {enhanced_metrics['sharpe_ratio']:.2f}")
    print(f"  Long/Short: {enhanced_metrics['long_trades']}/{enhanced_metrics['short_trades']}")
    
    # Test Hybrid Adaptive
    print(f"\n🔄 TESTING HYBRID ADAPTIVE")
    print("-" * 50)
    
    hybrid_trades = []
    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        df = fetch_historical_data(symbol)
        if df.empty:
            print(f"  ❌ No data available")
            continue
        
        df = calculate_indicators(df)
        trades = hybrid_adaptive_strategy(df, hybrid_params)
        hybrid_trades.extend(trades)
        print(f"  ✅ {len(trades)} trades")
    
    hybrid_metrics = calculate_performance_metrics(hybrid_trades, initial_capital)
    results['Hybrid Adaptive'] = hybrid_metrics
    
    print(f"\nHybrid Adaptive Results:")
    print(f"  Total Trades: {hybrid_metrics['total_trades']}")
    print(f"  Win Rate: {hybrid_metrics['win_rate']:.1f}%")
    print(f"  Total Return: {hybrid_metrics['total_return_pct']:.1f}%")
    print(f"  Profit Factor: {hybrid_metrics['profit_factor']:.2f}")
    print(f"  Max Drawdown: {hybrid_metrics['max_drawdown']:.1f}%")
    print(f"  Sharpe Ratio: {hybrid_metrics['sharpe_ratio']:.2f}")
    print(f"  Long/Short: {hybrid_metrics['long_trades']}/{hybrid_metrics['short_trades']}")
    
    # Test Multi-Indicator
    print(f"\n📊 TESTING MULTI-INDICATOR SYSTEM")
    print("-" * 50)
    
    multi_trades = []
    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        df = fetch_historical_data(symbol)
        if df.empty:
            print(f"  ❌ No data available")
            continue
        
        df = calculate_indicators(df)
        trades = multi_indicator_strategy(df, multi_params)
        multi_trades.extend(trades)
        print(f"  ✅ {len(trades)} trades")
    
    multi_metrics = calculate_performance_metrics(multi_trades, initial_capital)
    results['Multi-Indicator System'] = multi_metrics
    
    print(f"\nMulti-Indicator System Results:")
    print(f"  Total Trades: {multi_metrics['total_trades']}")
    print(f"  Win Rate: {multi_metrics['win_rate']:.1f}%")
    print(f"  Total Return: {multi_metrics['total_return_pct']:.1f}%")
    print(f"  Profit Factor: {multi_metrics['profit_factor']:.2f}")
    print(f"  Max Drawdown: {multi_metrics['max_drawdown']:.1f}%")
    print(f"  Sharpe Ratio: {multi_metrics['sharpe_ratio']:.2f}")
    print(f"  Long/Short: {multi_metrics['long_trades']}/{multi_metrics['short_trades']}")
    
    # Comprehensive comparison
    print(f"\n📊 COMPREHENSIVE STRATEGY COMPARISON")
    print("=" * 80)
    print(f"{'Strategy':<25} {'Trades':<8} {'Win%':<6} {'Return%':<9} {'DD%':<6} {'Sharpe'} {'L/S'}")
    print("-" * 80)
    
    for name, metrics in results.items():
        long_short = f"{metrics['long_trades']}/{metrics['short_trades']}"
        print(f"{name:<25} {metrics['total_trades']:<8} {metrics['win_rate']:<6.1f} {metrics['total_return_pct']:<9.1f} {metrics['max_drawdown']:<6.1f} {metrics['sharpe_ratio']:<6.2f} {long_short}")
    
    # Find best performer
    best_strategy = max(results.items(), key=lambda x: x[1]['sharpe_ratio'])
    print(f"\n🏆 BEST PERFORMER (Sharpe Ratio): {best_strategy[0]}")
    print(f"   Sharpe Ratio: {best_strategy[1]['sharpe_ratio']:.2f}")
    print(f"   Total Return: {best_strategy[1]['total_return_pct']:.1f}%")
    print(f"   Win Rate: {best_strategy[1]['win_rate']:.1f}%")
    print(f"   Trades per month: {best_strategy[1]['total_trades']/6:.1f}")
    print(f"   Long/Short: {best_strategy[1]['long_trades']}/{best_strategy[1]['short_trades']}")
    
    # Annual projections
    print(f"\n🎯 ANNUAL PROJECTIONS")
    print("-" * 40)
    for name, metrics in results.items():
        # Convert total return to decimal and compound for 6 months to 1 year
        total_return_decimal = metrics['total_return_pct'] / 100
        annual_return_decimal = (1 + total_return_decimal) ** 2 - 1  # 6 months to 1 year
        annual_return = annual_return_decimal * 100
        trades_per_month = metrics['total_trades'] / 6
        print(f"{name}: {annual_return:.1f}% annual, {trades_per_month:.1f} trades/mo")
    
    # Viability assessment
    print(f"\n📊 VIABILITY ASSESSMENT")
    print("-" * 30)
    for name, metrics in results.items():
        # Convert total return to decimal and compound for 6 months to 1 year
        total_return_decimal = metrics['total_return_pct'] / 100
        annual_return_decimal = (1 + total_return_decimal) ** 2 - 1  # 6 months to 1 year
        annual_return = annual_return_decimal * 100
        if annual_return >= 15 and metrics['win_rate'] >= 55 and metrics['max_drawdown'] <= 25:
            viability = "✅ VIABLE"
        elif annual_return >= 10 and metrics['win_rate'] >= 50 and metrics['max_drawdown'] <= 30:
            viability = "⚠️  MODERATE"
        else:
            viability = "❌ NOT VIABLE"
        
        print(f"{name}: {viability}")
    
    return results

if __name__ == "__main__":
    run_comprehensive_backtest()