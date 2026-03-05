#!/usr/bin/env python3
"""
Debug ATR Breakout Strategy
Identify why no trades are being generated
"""

import pandas as pd
import numpy as np
import sys
import os

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators

def load_historical_data(symbol, period):
    """Load historical data for a symbol and period"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    filepath_4h = f"/home/dribble0335/dev/tradingbot/research/historical/{filename_4h}"
    
    if os.path.exists(filepath_4h):
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    true_range = np.maximum(high_low, np.maximum(high_close, low_close))
    atr = true_range.rolling(window=period).mean()
    
    return atr

def debug_atr_breakout():
    """Debug ATR Breakout strategy"""
    print("🔍 DEBUGGING ATR BREAKOUT STRATEGY")
    print("=" * 60)
    
    # Test with one symbol and period
    symbol = "BTC/USDT"
    period = "recent_period"
    
    print(f"Testing {symbol} - {period}")
    
    # Load data
    df = load_historical_data(symbol, period)
    
    if df.empty:
        print("❌ No data available")
        return
    
    print(f"📊 Data loaded: {len(df)} candles")
    
    # Calculate indicators
    df_ind = compute_4h_indicators(df)
    df_ind['atr'] = calculate_atr(df_ind)
    df_ind['volume_sma'] = df_ind['volume'].rolling(window=20).mean()
    # Guard against division by zero for volume_ratio
    df_ind['volume_ratio'] = np.where(df_ind['volume_sma'] != 0, df_ind['volume'] / df_ind['volume_sma'], 0)
    df_ind['recent_high'] = df_ind['high'].rolling(window=10).max()
    
    if df_ind.empty:
        print("❌ No indicators calculated")
        return
    
    print(f"📈 Indicators calculated: {len(df_ind)} candles")
    print(f"   Price range: ${df_ind['close'].min():.2f} - ${df_ind['close'].max():.2f}")
    print(f"   ATR range: ${df_ind['atr'].min():.2f} - ${df_ind['atr'].max():.2f}")
    print(f"   Volume ratio range: {df_ind['volume_ratio'].min():.2f} - {df_ind['volume_ratio'].max():.2f}")
    print(f"   RSI range: {df_ind['rsi'].min():.1f} - {df_ind['rsi'].max():.1f}")
    print(f"   ADX range: {df_ind['adx'].min():.1f} - {df_ind['adx'].max():.1f}")
    
    # Test entry conditions
    print(f"\n🔍 ENTRY CONDITIONS ANALYSIS:")
    
    # Strategy parameters (updated)
    atr_multiplier = 1.0  # Reduced from 1.5
    volume_ratio_threshold = 1.5
    rsi_threshold = 50
    adx_threshold = 25
    lookback_periods = 10
    
    condition_counts = {
        'breakout': 0,
        'volume': 0,
        'rsi': 0,
        'adx': 0,
        'all_conditions': 0
    }
    
    potential_signals = []
    
    for i in range(15, len(df_ind)):  # Need ATR calculation
        sig = df_ind.iloc[i]
        
        # Check individual conditions
        recent_high = sig['recent_high']
        breakout_level = recent_high + (sig['atr'] * atr_multiplier)
        breakout_condition = sig['close'] > breakout_level
        volume_condition = sig['volume_ratio'] > volume_ratio_threshold
        rsi_condition = sig['rsi'] > rsi_threshold
        adx_condition = sig['adx'] > adx_threshold
        
        if breakout_condition:
            condition_counts['breakout'] += 1
        if volume_condition:
            condition_counts['volume'] += 1
        if rsi_condition:
            condition_counts['rsi'] += 1
        if adx_condition:
            condition_counts['adx'] += 1
            
        # Check all conditions
        if breakout_condition and volume_condition and rsi_condition and adx_condition:
            condition_counts['all_conditions'] += 1
            potential_signals.append({
                'timestamp': sig['timestamp'],
                'close': sig['close'],
                'breakout_level': breakout_level,
                'atr': sig['atr'],
                'volume_ratio': sig['volume_ratio'],
                'rsi': sig['rsi'],
                'adx': sig['adx']
            })
    
    print(f"   Breakout condition: {condition_counts['breakout']}/{len(df_ind)} ({condition_counts['breakout']/len(df_ind)*100:.1f}%)")
    print(f"   Volume condition: {condition_counts['volume']}/{len(df_ind)} ({condition_counts['volume']/len(df_ind)*100:.1f}%)")
    print(f"   RSI condition: {condition_counts['rsi']}/{len(df_ind)} ({condition_counts['rsi']/len(df_ind)*100:.1f}%)")
    print(f"   ADX condition: {condition_counts['adx']}/{len(df_ind)} ({condition_counts['adx']/len(df_ind)*100:.1f}%)")
    print(f"   All conditions: {condition_counts['all_conditions']}/{len(df_ind)} ({condition_counts['all_conditions']/len(df_ind)*100:.1f}%)")
    
    if potential_signals:
        print(f"\n✅ POTENTIAL SIGNALS FOUND: {len(potential_signals)}")
        print(f"📊 SAMPLE SIGNALS:")
        for i, signal in enumerate(potential_signals[:5]):  # Show first 5
            print(f"   Signal {i+1}: {signal['timestamp']}")
            print(f"     Price: ${signal['close']:.2f}, Breakout Level: ${signal['breakout_level']:.2f}")
            print(f"     ATR: ${signal['atr']:.2f}, Volume Ratio: {signal['volume_ratio']:.2f}")
            print(f"     RSI: {signal['rsi']:.1f}, ADX: {signal['adx']:.1f}")
    else:
        print(f"\n❌ NO SIGNALS GENERATED")
        print(f"🔍 ISSUE ANALYSIS:")
        
        # Additional debugging for breakout condition
        print(f"\n🔍 BREAKOUT CONDITION DEBUG:")
        print(f"   Recent highs vs current prices:")
        
        for i in range(10, min(20, len(df_ind))):  # Start from index 10 (after rolling window)
            sig = df_ind.iloc[i]
            recent_high = sig['recent_high']
            breakout_level = recent_high + (sig['atr'] * atr_multiplier)
            price_diff = sig['close'] - recent_high
            atr_diff = sig['atr'] * atr_multiplier
            
            print(f"   Candle {i}: Price ${sig['close']:.2f}, Recent High ${recent_high:.2f}")
            print(f"     Price diff: ${price_diff:.2f}, ATR buffer: ${atr_diff:.2f}")
            print(f"     Breakout level: ${breakout_level:.2f}")
            
            if i >= 14:  # Only show 5 examples
                break
        
        if condition_counts['breakout'] == 0:
            print(f"   • Breakout condition too restrictive")
            print(f"   • Consider reducing ATR multiplier from {atr_multiplier} to 0.5")
            print(f"   • Or use simple price > recent_high without ATR buffer")
        
        if condition_counts['volume'] < len(df_ind) * 0.1:
            print(f"   • Volume condition too restrictive")
            print(f"   • Consider reducing volume threshold from {volume_ratio_threshold} to 1.2")
        
        if condition_counts['adx'] < len(df_ind) * 0.3:
            print(f"   • ADX condition too restrictive")
            print(f"   • Consider reducing ADX threshold from {adx_threshold} to 20")
        
        # Suggest parameter adjustments
        print(f"\n💡 SUGGESTED ADJUSTMENTS:")
        suggestions = []
        
        if condition_counts['breakout'] == 0:
            suggestions.append("Reduce ATR multiplier to 0.5")
            suggestions.append("Or use simple price > recent_high (no ATR buffer)")
        
        if condition_counts['volume'] < len(df_ind) * 0.1:
            suggestions.append("Reduce volume threshold to 1.2")
        
        if condition_counts['adx'] < len(df_ind) * 0.3:
            suggestions.append("Reduce ADX threshold to 20")
        
        if suggestions:
            for suggestion in suggestions:
                print(f"   • {suggestion}")
        else:
            print(f"   • Strategy may not be suitable for current market conditions")

def main():
    """Main debug function"""
    try:
        debug_atr_breakout()
        return 0
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
