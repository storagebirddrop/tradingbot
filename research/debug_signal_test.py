#!/usr/bin/env python3
"""
Debug signal test to identify the pandas boolean issue
"""

import pandas as pd
import numpy as np

def test_signal_generation():
    """Test signal generation step by step"""
    print("Debugging signal generation...")
    
    # Load BTC data
    df_4h = pd.read_csv("/home/dribble0335/dev/tradingbot/research/historical/BTC_USDT_4h_recent.csv")
    df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'])
    
    df_1d = pd.read_csv("/home/dribble0335/dev/tradingbot/research/regime/BTC_USDT_1d_recent.csv")
    df_1d['timestamp'] = pd.to_datetime(df_1d['timestamp'])
    
    print(f"Loaded data: 4h={len(df_4h)}, 1d={len(df_1d)}")
    
    # Simple regime
    df_regime = df_1d.copy()
    df_regime['ema200'] = df_regime['close'].ewm(span=200).mean()
    df_regime['risk_on'] = df_regime['close'] > df_regime['ema200']
    
    # Attach regime (simplified)
    df_combined = df_4h.copy()
    df_combined['risk_on'] = False
    
    # Use last available regime for all rows (simplified)
    if not df_regime.empty:
        last_regime = df_regime.iloc[-1]['risk_on']
        df_combined['risk_on'] = last_regime
    
    print(f"Regime attached: risk_on={last_regime}")
    
    # Clean data
    df_clean = df_combined.dropna()
    print(f"Clean data: {len(df_clean)} rows")
    
    # Test basic signals
    print("Testing basic signal generation...")
    
    try:
        # Test individual signals
        sma_breakdown = df_clean['close'] < df_clean['sma200']
        print(f"SMA breakdown type: {type(sma_breakdown)}")
        print(f"SMA breakdown shape: {sma_breakdown.shape}")
        print(f"SMA breakdown sum: {sma_breakdown.sum()}")
        
        rsi_overbought = df_clean['rsi'] > 70
        print(f"RSI overbought sum: {rsi_overbought.sum()}")
        
        # Test combination
        combined = sma_breakdown & rsi_overbought
        print(f"Combined signal sum: {combined.sum()}")
        
        # Test with ADX
        adx_strong = df_clean['adx'] > 25
        print(f"ADX strong sum: {adx_strong.sum()}")
        
        # Test full combination
        full_signal = combined & adx_strong
        print(f"Full signal sum: {full_signal.sum()}")
        
        print("Signal generation works!")
        
        # Test different strategy
        print("\nTesting different strategies...")
        
        # Strategy 1: Any exit signal
        any_exit = sma_breakdown | rsi_overbought | (df_clean['MACDh_12_26_9'] < 0)
        strategy1 = any_exit & adx_strong & (~df_clean['risk_on'])
        print(f"Strategy 1 (any exit): {strategy1.sum()} signals ({strategy1.sum()/len(df_clean)*100:.1f}%)")
        
        # Strategy 2: Two conditions required
        two_conditions = (sma_breakdown & rsi_overbought) | (sma_breakdown & (df_clean['MACDh_12_26_9'] < 0))
        strategy2 = two_conditions & adx_strong & (~df_clean['risk_on'])
        print(f"Strategy 2 (two conditions): {strategy2.sum()} signals ({strategy2.sum()/len(df_clean)*100:.1f}%)")
        
        # Strategy 3: Conservative
        conservative = sma_breakdown & rsi_overbought & (df_clean['MACDh_12_26_9'] < 0)
        strategy3 = conservative & adx_strong & (~df_clean['risk_on'])
        print(f"Strategy 3 (conservative): {strategy3.sum()} signals ({strategy3.sum()/len(df_clean)*100:.1f}%)")
        
        return True
        
    except Exception as e:
        print(f"Error in signal generation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_signal_generation()
    if success:
        print("\nSignal generation test successful!")
    else:
        print("\nSignal generation test failed!")
