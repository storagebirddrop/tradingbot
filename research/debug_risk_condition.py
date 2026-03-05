#!/usr/bin/env python3
"""
Debug Risk Condition
Check if risk-off condition is preventing signals
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

def debug_risk_condition():
    """Debug risk condition impact on signals"""
    print("🔍 DEBUGGING RISK CONDITION IMPACT")
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
    
    # Calculate indicators
    df_ind = compute_4h_indicators(df)
    
    if df_ind.empty:
        print("❌ No indicators calculated")
        return
    
    print(f"📊 Data: {len(df_ind)} candles")
    
    # Test conditions without risk-off requirement
    print(f"\n🔍 CONDITIONS ANALYSIS (WITHOUT RISK-OFF):")
    
    below_sma_count = 0
    rsi_overbought_count = 0
    adx_strong_count = 0
    all_conditions_count = 0
    
    for i in range(1, len(df_ind)):
        sig = df_ind.iloc[i]
        
        below_sma = sig['close'] < sig['sma200_4h']
        rsi_overbought = sig['rsi'] > 65  # Use relaxed RSI
        adx_strong = sig['adx'] > 20  # Use relaxed ADX
        
        if below_sma:
            below_sma_count += 1
        if rsi_overbought:
            rsi_overbought_count += 1
        if adx_strong:
            adx_strong_count += 1
            
        if below_sma and rsi_overbought and adx_strong:
            all_conditions_count += 1
    
    # Calculate percentages using actual counted rows (loop processes len(df_ind)-1 rows)
    count_denominator = max(1, len(df_ind) - 1)
    
    print(f"   Below SMA200: {below_sma_count}/{count_denominator} ({below_sma_count/count_denominator*100:.1f}%)")
    print(f"   RSI > 65: {rsi_overbought_count}/{count_denominator} ({rsi_overbought_count/count_denominator*100:.1f}%)")
    print(f"   ADX > 20: {adx_strong_count}/{count_denominator} ({adx_strong_count/count_denominator*100:.1f}%)")
    print(f"   All conditions: {all_conditions_count}/{count_denominator} ({all_conditions_count/count_denominator*100:.1f}%)")
    
    if all_conditions_count > 0:
        print(f"\n✅ STRATEGY VIABLE WITHOUT RISK-OFF")
        print(f"   Risk-off condition is preventing {all_conditions_count} potential signals")
        print(f"   Consider removing or relaxing risk-off requirement")
        
        # Show sample signals
        print(f"\n📊 SAMPLE POTENTIAL SIGNALS:")
        count = 0
        for i in range(1, len(df_ind)):
            sig = df_ind.iloc[i]
            
            if (sig['close'] < sig['sma200_4h'] and 
                sig['rsi'] > 65 and 
                sig['adx'] > 20):
                
                count += 1
                if count <= 5:  # Show first 5
                    print(f"   Signal {count}: {sig['timestamp']}")
                    print(f"     Price: ${sig['close']:.2f}, SMA200: ${sig['sma200_4h']:.2f}")
                    print(f"     RSI: {sig['rsi']:.1f}, ADX: {sig['adx']:.1f}")
    else:
        print(f"\n❌ STRATEGY NOT VIABLE EVEN WITHOUT RISK-OFF")
        print(f"   Need to consider different strategy or timeframe")

def main():
    """Main debug function"""
    try:
        debug_risk_condition()
        return 0
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
