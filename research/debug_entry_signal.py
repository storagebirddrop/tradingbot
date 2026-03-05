#!/usr/bin/env python3
"""
Debug entry_signal function integration
"""

import pandas as pd
import numpy as np
import sys
import os

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators, volume_reversal_long_signal, entry_signal

def load_historical_data(symbol, period):
    """Load historical data for testing"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    filepath_4h = f"/home/dribble0335/dev/tradingbot/research/historical/{filename_4h}"
    
    if os.path.exists(filepath_4h):
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def debug_entry_signal():
    """Debug entry_signal function"""
    print("🔍 DEBUGGING ENTRY_SIGNAL FUNCTION")
    print("=" * 60)
    
    # Load data
    df = load_historical_data("BTC/USDT", "recent_period")
    if df.empty:
        print("❌ No data loaded")
        return
    
    df_ind = compute_4h_indicators(df)
    if df_ind.empty:
        print("❌ No indicators calculated")
        return
    
    # Find a signal
    for i in range(1, len(df_ind)):
        sig = df_ind.iloc[i]
        prev_sig = df_ind.iloc[i-1]
        
        # Test volume reversal signal directly
        volume_signal = volume_reversal_long_signal(sig, prev_sig)
        
        if volume_signal:
            print(f"✅ Found Volume Reversal Signal at index {i}")
            print(f"   Timestamp: {sig['timestamp']}")
            print(f"   Close: ${sig['close']:.2f}")
            print(f"   Volume Ratio: {sig['volume_ratio']:.2f}")
            print(f"   RSI: {sig['rsi']:.1f}")
            print(f"   Volatility: {sig['volatility']:.4f}")
            
            # Test entry_signal function
            entry_result = entry_signal(sig, prev_sig, strategy="volume_reversal_long")
            print(f"   Volume Reversal Signal: {volume_signal}")
            print(f"   Entry Signal Result: {entry_result}")
            
            # Test with different parameters
            entry_default = entry_signal(sig, prev_sig)
            entry_adaptive = entry_signal(sig, prev_sig, adaptive=True)
            entry_sma = entry_signal(sig, prev_sig, strategy="sma_rsi_combo")
            
            print(f"   Entry Signal (default): {entry_default}")
            print(f"   Entry Signal (adaptive): {entry_adaptive}")
            print(f"   Entry Signal (sma_rsi_combo): {entry_sma}")
            
            break
    else:
        print("❌ No Volume Reversal signals found")

if __name__ == "__main__":
    debug_entry_signal()
