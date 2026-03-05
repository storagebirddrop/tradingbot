#!/usr/bin/env python3
"""
Debug Strategy Signals
Check if sma_rsi_combo signals are being generated properly
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# Add parent directory to path for imports dynamically
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from strategy import compute_4h_indicators, sma_rsi_combo_signal

def load_historical_data(symbol, period):
    """Load historical data for a symbol and period"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    # Build path relative to script location
    script_dir = Path(__file__).resolve().parent
    filepath_4h = script_dir / "historical" / filename_4h
    
    if filepath_4h.exists():
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def debug_strategy_signals():
    """Debug strategy signal generation"""
    print("🔍 DEBUGGING STRATEGY SIGNALS")
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
    print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    
    # Calculate indicators
    df_ind = compute_4h_indicators(df)
    
    if df_ind.empty:
        print("❌ No indicators calculated (insufficient data)")
        return
    
    print(f"📈 Indicators calculated: {len(df_ind)} candles")
    print(f"   SMA200 range: ${df_ind['sma200_4h'].min():.2f} - ${df_ind['sma200_4h'].max():.2f}")
    print(f"   RSI range: {df_ind['rsi'].min():.1f} - {df_ind['rsi'].max():.1f}")
    print(f"   ADX range: {df_ind['adx'].min():.1f} - {df_ind['adx'].max():.1f}")
    
    # Check strategy conditions
    print(f"\n🔍 STRATEGY CONDITIONS ANALYSIS:")
    
    signals = []
    
    for i in range(1, len(df_ind)):
        sig = df_ind.iloc[i]
        prev_sig = df_ind.iloc[i-1]
        
        # Check individual conditions
        below_sma = sig['close'] < sig['sma200_4h']
        rsi_overbought = sig['rsi'] > 70
        adx_strong = sig['adx'] > 25
        risk_off = not sig.get('risk_on', True)  # Default to risk-off
        
        # Check full signal
        full_signal = sma_rsi_combo_signal(sig, prev_sig)
        
        if full_signal:
            signals.append(i)
            print(f"   Signal {len(signals)} at {sig['timestamp']}:")
            print(f"     Price: ${sig['close']:.2f}, SMA200: ${sig['sma200_4h']:.2f}")
            print(f"     RSI: {sig['rsi']:.1f}, ADX: {sig['adx']:.1f}")
            print(f"     Below SMA: {below_sma}, RSI>70: {rsi_overbought}, ADX>25: {adx_strong}, Risk-off: {risk_off}")
    
    # Overall statistics
    print(f"\n📊 SIGNAL STATISTICS:")
    print(f"   Total signals: {len(signals)}")
    print(f"   Signal frequency: {len(signals)/len(df_ind)*100:.2f}%")
    
    # Check condition frequencies
    below_sma_count = (df_ind['close'] < df_ind['sma200_4h']).sum()
    rsi_overbought_count = (df_ind['rsi'] > 70).sum()
    adx_strong_count = (df_ind['adx'] > 25).sum()
    
    print(f"\n📈 CONDITION FREQUENCIES:")
    print(f"   Below SMA200: {below_sma_count}/{len(df_ind)} ({below_sma_count/len(df_ind)*100:.1f}%)")
    print(f"   RSI > 70: {rsi_overbought_count}/{len(df_ind)} ({rsi_overbought_count/len(df_ind)*100:.1f}%)")
    print(f"   ADX > 25: {adx_strong_count}/{len(df_ind)} ({adx_strong_count/len(df_ind)*100:.1f}%)")
    
    # Check if conditions are too restrictive
    all_conditions = ((df_ind['close'] < df_ind['sma200_4h']) & 
                     (df_ind['rsi'] > 70) & 
                     (df_ind['adx'] > 25))
    
    all_conditions_count = all_conditions.sum()
    print(f"   All conditions met: {all_conditions_count}/{len(df_ind)} ({all_conditions_count/len(df_ind)*100:.1f}%)")
    
    if len(signals) == 0:
        print(f"\n❌ NO SIGNALS GENERATED")
        print(f"   Strategy may be too restrictive for current market conditions")
        print(f"   Consider relaxing conditions or checking different timeframes")
        
        # Suggest alternative parameters
        print(f"\n💡 SUGGESTED ADJUSTMENTS:")
        if rsi_overbought_count < len(df_ind) * 0.1:
            print(f"   • Lower RSI threshold from 70 to 65")
        if adx_strong_count < len(df_ind) * 0.3:
            print(f"   • Lower ADX threshold from 25 to 20")
        if below_sma_count < len(df_ind) * 0.3:
            print(f"   • Strategy may not be suitable for current market (mostly above SMA)")
    else:
        print(f"\n✅ STRATEGY WORKING NORMALLY")
        print(f"   Generated {len(signals)} signals over {len(df_ind)} candles")

def main():
    """Main debug function"""
    try:
        debug_strategy_signals()
        return 0
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
