#!/usr/bin/env python3
"""
Debug Volume Reversal Strategy
Identify why no signals are being generated
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# Add parent directory to path for imports dynamically
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from strategy import compute_4h_indicators

def load_historical_data(symbol, period):
    """Load historical data for testing"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    # Build path relative to script location
    script_dir = Path(__file__).resolve().parent
    filepath_4h = script_dir / "historical" / filename_4h
    
    try:
        if filepath_4h.exists():
            df = pd.read_csv(filepath_4h)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
            else:
                print(f"Error: 'timestamp' column not found in {filepath_4h}")
                return pd.DataFrame()
        else:
            print(f"Warning: File not found: {filepath_4h}")
            return pd.DataFrame()
    except (IOError, pd.errors.ParserError, UnicodeDecodeError) as e:
        print(f"Error loading data for {symbol} {period}: {e}")
        return pd.DataFrame()

def debug_volume_reversal():
    """Debug Volume Reversal strategy"""
    print("🔍 DEBUGGING VOLUME REVERSAL STRATEGY")
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
    
    if df_ind.empty:
        print("❌ No indicators calculated")
        return
    
    print(f"📈 Indicators calculated: {len(df_ind)} candles")
    print(f"   Price range: ${df_ind['close'].min():.2f} - ${df_ind['close'].max():.2f}")
    print(f"   Volume ratio range: {df_ind['volume_ratio'].min():.2f} - {df_ind['volume_ratio'].max():.2f}")
    print(f"   RSI range: {df_ind['rsi'].min():.1f} - {df_ind['rsi'].max():.1f}")
    print(f"   Volatility range: {df_ind['volatility'].min():.4f} - {df_ind['volatility'].max():.4f}")
    
    # Test entry conditions
    print(f"\n🔍 ENTRY CONDITIONS ANALYSIS:")
    
    # Strategy parameters
    volume_ratio_threshold = 2.0
    rsi_threshold = 40
    
    condition_counts = {
        'volume': 0,
        'price_reversal': 0,
        'downtrend': 0,
        'rsi': 0,
        'volatility': 0,
        'all_conditions': 0
    }
    
    potential_signals = []
    
    for i in range(1, len(df_ind)):
        sig = df_ind.iloc[i]
        prev_sig = df_ind.iloc[i-1]
        
        # Check individual conditions
        volume_condition = sig['volume_ratio'] > volume_ratio_threshold
        price_reversal_condition = sig['close'] > prev_sig['close']
        downtrend_condition = prev_sig['close'] < prev_sig['sma200_4h']
        rsi_condition = sig['rsi'] < rsi_threshold
        volatility_mean = df_ind['volatility'].iloc[:i].mean() if i > 50 else sig['volatility']
        volatility_condition = sig['volatility'] > volatility_mean
        
        if volume_condition:
            condition_counts['volume'] += 1
        if price_reversal_condition:
            condition_counts['price_reversal'] += 1
        if downtrend_condition:
            condition_counts['downtrend'] += 1
        if rsi_condition:
            condition_counts['rsi'] += 1
        if volatility_condition:
            condition_counts['volatility'] += 1
            
        # Check all conditions
        if volume_condition and price_reversal_condition and downtrend_condition and rsi_condition and volatility_condition:
            condition_counts['all_conditions'] += 1
            potential_signals.append({
                'timestamp': sig['timestamp'],
                'close': sig['close'],
                'volume_ratio': sig['volume_ratio'],
                'rsi': sig['rsi'],
                'volatility': sig['volatility'],
                'prev_close': prev_sig['close'],
                'prev_sma200': prev_sig['sma200_4h']
            })
    
    # Guard against division by zero when df_ind is empty
    if len(df_ind) == 0:
        print("   Volume condition: 0/0 (N/A)")
        print("   Price reversal condition: 0/0 (N/A)")
        print("   Downtrend condition: 0/0 (N/A)")
        print("   RSI condition: 0/0 (N/A)")
        print("   Volatility condition: 0/0 (N/A)")
        print("   All conditions: 0/0 (N/A)")
    else:
        print(f"   Volume condition: {condition_counts['volume']}/{len(df_ind)} ({condition_counts['volume']/len(df_ind)*100:.1f}%)")
        print(f"   Price reversal condition: {condition_counts['price_reversal']}/{len(df_ind)} ({condition_counts['price_reversal']/len(df_ind)*100:.1f}%)")
        print(f"   Downtrend condition: {condition_counts['downtrend']}/{len(df_ind)} ({condition_counts['downtrend']/len(df_ind)*100:.1f}%)")
        print(f"   RSI condition: {condition_counts['rsi']}/{len(df_ind)} ({condition_counts['rsi']/len(df_ind)*100:.1f}%)")
        print(f"   Volatility condition: {condition_counts['volatility']}/{len(df_ind)} ({condition_counts['volatility']/len(df_ind)*100:.1f}%)")
        print(f"   All conditions: {condition_counts['all_conditions']}/{len(df_ind)} ({condition_counts['all_conditions']/len(df_ind)*100:.1f}%)")
    
    if potential_signals:
        print(f"\n✅ POTENTIAL SIGNALS FOUND: {len(potential_signals)}")
        print(f"📊 SAMPLE SIGNALS:")
        for i, signal in enumerate(potential_signals[:5]):  # Show first 5
            print(f"   Signal {i+1}: {signal['timestamp']}")
            print(f"     Price: ${signal['close']:.2f}, Prev Close: ${signal['prev_close']:.2f}")
            print(f"     Volume Ratio: {signal['volume_ratio']:.2f}, RSI: {signal['rsi']:.1f}")
            print(f"     Volatility: {signal['volatility']:.4f}")
            print(f"     Prev SMA200: ${signal['prev_sma200']:.2f}")
    else:
        print(f"\n❌ NO SIGNALS GENERATED")
        print(f"🔍 ISSUE ANALYSIS:")
        
        if condition_counts['volume'] < len(df_ind) * 0.05:
            print(f"   • Volume condition too restrictive")
            print(f"   • Consider reducing volume threshold from {volume_ratio_threshold} to 1.5")
        
        if condition_counts['downtrend'] < len(df_ind) * 0.3:
            print(f"   • Downtrend condition too restrictive")
            print(f"   • Market may not be in downtrend context")
        
        if condition_counts['rsi'] < len(df_ind) * 0.2:
            print(f"   • RSI condition too restrictive")
            print(f"   • Consider increasing RSI threshold from {rsi_threshold} to 50")
        
        # Show sample data for debugging
        print(f"\n🔍 SAMPLE CANDLE DATA:")
        for i in range(min(5, len(df_ind))):
            sig = df_ind.iloc[i]
            prev_sig = df_ind.iloc[i-1] if i > 0 else sig
            
            volume_condition = sig['volume_ratio'] > volume_ratio_threshold
            price_reversal_condition = sig['close'] > prev_sig['close'] if i > 0 else False
            downtrend_condition = prev_sig['close'] < prev_sig['sma200_4h'] if i > 0 else False
            rsi_condition = sig['rsi'] < rsi_threshold
            volatility_mean = df_ind['volatility'].iloc[:i].mean() if i > 50 else sig['volatility']
            volatility_condition = sig['volatility'] > volatility_mean
            
            print(f"   Candle {i}:")
            print(f"     Close: ${sig['close']:.2f}, Volume Ratio: {sig['volume_ratio']:.2f}")
            print(f"     RSI: {sig['rsi']:.1f}, Volatility: {sig['volatility']:.4f}")
            print(f"     Conditions: V:{volume_condition} P:{price_reversal_condition} D:{downtrend_condition} R:{rsi_condition} Vol:{volatility_condition}")
            
            if i >= 2:  # Only show first 3
                break
        
        # Suggest parameter adjustments
        print(f"\n💡 SUGGESTED ADJUSTMENTS:")
        suggestions = []
        
        if condition_counts['volume'] < len(df_ind) * 0.05:
            suggestions.append("Reduce volume threshold to 1.5")
        
        if condition_counts['downtrend'] < len(df_ind) * 0.3:
            suggestions.append("Remove downtrend requirement or use longer lookback")
        
        if condition_counts['rsi'] < len(df_ind) * 0.2:
            suggestions.append("Increase RSI threshold to 50")
        
        if suggestions:
            for suggestion in suggestions:
                print(f"   • {suggestion}")
        else:
            print(f"   • Strategy may not be suitable for current market conditions")

def main():
    """Main debug function"""
    try:
        debug_volume_reversal()
        return 0
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
