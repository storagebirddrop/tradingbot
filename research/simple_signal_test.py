#!/usr/bin/env python3
"""
Simple signal test to debug the analysis
"""

import pandas as pd
import numpy as np
import os

def load_data(symbol):
    """Load data for a symbol"""
    # Load 4h data
    file_4h = f"{symbol.replace('/', '_')}_4h_recent.csv"
    df_4h = pd.read_csv(f"/home/dribble0335/dev/tradingbot/research/historical/{file_4h}")
    df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'])
    
    # Load 1d data for regime
    file_1d = f"{symbol.replace('/', '_')}_1d_recent.csv"
    df_1d = pd.read_csv(f"/home/dribble0335/dev/tradingbot/research/regime/{file_1d}")
    df_1d['timestamp'] = pd.to_datetime(df_1d['timestamp'])
    
    return df_4h, df_1d

def calculate_regime(df_1d):
    """Simple regime calculation"""
    df_regime = df_1d.copy()
    
    # Calculate EMA200
    df_regime['ema200'] = df_regime['close'].ewm(span=200).mean()
    
    # Simple regime: above EMA200 = risk_on
    df_regime['risk_on'] = df_regime['close'] > df_regime['ema200']
    
    return df_regime[['timestamp', 'risk_on']]

def attach_regime_to_4h(df_4h, df_regime):
    """Attach regime data to 4h data"""
    # Simple merge on timestamp
    df_combined = df_4h.copy()
    
    # For each 4h row, find the most recent regime
    regime_dict = df_regime.set_index('timestamp')['risk_on'].to_dict()
    
    # Apply regime (simplified - just use previous day's regime)
    df_combined['risk_on'] = False  # Default
    
    for i, row in df_combined.iterrows():
        # Find regime from previous day
        current_time = row['timestamp']
        previous_day = current_time - pd.Timedelta(days=1)
        
        # Find closest regime timestamp
        regime_times = df_regime[df_regime['timestamp'] <= current_time]['timestamp']
        if not regime_times.empty:
            closest_time = regime_times.iloc[-1]
            regime_value = df_regime[df_regime['timestamp'] == closest_time]['risk_on'].iloc[0]
            df_combined.loc[i, 'risk_on'] = regime_value
    
    return df_combined

def test_signals(df_combined):
    """Test signal generation"""
    print(f"Testing signals on {len(df_combined)} rows")
    print(f"Date range: {df_combined['timestamp'].min()} to {df_combined['timestamp'].max()}")
    
    # Check for NaN values
    print(f"NaN values in key columns:")
    print(f"  close: {df_combined['close'].isna().sum()}")
    print(f"  sma200: {df_combined['sma200'].isna().sum()}")
    print(f"  rsi: {df_combined['rsi'].isna().sum()}")
    print(f"  MACDh: {df_combined['MACDh_12_26_9'].isna().sum()}")
    print(f"  adx: {df_combined['adx'].isna().sum()}")
    print(f"  risk_on: {df_combined['risk_on'].isna().sum()}")
    
    # Generate signals (drop NaN values first)
    df_clean = df_combined.dropna()
    print(f"After dropping NaN: {len(df_clean)} rows")
    
    if df_clean.empty:
        print("No clean data available for signal testing")
        return
    
    # Generate basic signals
    df_clean['sma_breakdown'] = df_clean['close'] < df_clean['sma200']
    df_clean['rsi_overbought'] = df_clean['rsi'] > 70
    df_clean['macd_bearish'] = df_clean['MACDh_12_26_9'] < 0
    df_clean['adx_strong'] = df_clean['adx'] > 25
    df_clean['risk_off'] = ~df_clean['risk_on']
    
    # Combined exit signal (current long exit logic)
    df_clean['exit_signal'] = (
        df_clean['sma_breakdown'] | 
        df_clean['rsi_overbought'] | 
        df_clean['macd_bearish']
    )
    
    # Combined short entry signal (with filters)
    df_clean['short_entry'] = (
        df_clean['exit_signal'] & 
        df_clean['adx_strong'] & 
        df_clean['risk_off']
    )
    
    # Count signals
    print(f"\nSignal counts:")
    print(f"  SMA breakdown: {df_clean['sma_breakdown'].sum()}")
    print(f"  RSI overbought: {df_clean['rsi_overbought'].sum()}")
    print(f"  MACD bearish: {df_clean['macd_bearish'].sum()}")
    print(f"  ADX strong: {df_clean['adx_strong'].sum()}")
    print(f"  Risk off: {df_clean['risk_off'].sum()}")
    print(f"  Exit signals: {df_clean['exit_signal'].sum()}")
    print(f"  Short entries: {df_clean['short_entry'].sum()}")
    
    # Calculate percentages
    total_rows = len(df_clean)
    print(f"\nSignal frequencies:")
    print(f"  SMA breakdown: {df_clean['sma_breakdown'].sum() / total_rows * 100:.1f}%")
    print(f"  RSI overbought: {df_clean['rsi_overbought'].sum() / total_rows * 100:.1f}%")
    print(f"  MACD bearish: {df_clean['macd_bearish'].sum() / total_rows * 100:.1f}%")
    print(f"  Exit signals: {df_clean['exit_signal'].sum() / total_rows * 100:.1f}%")
    print(f"  Short entries: {df_clean['short_entry'].sum() / total_rows * 100:.1f}%")
    
    # Show some examples
    short_entries = df_clean[df_clean['short_entry']]
    if not short_entries.empty:
        print(f"\nSample short entries:")
        print(short_entries[['timestamp', 'close', 'sma200', 'rsi', 'MACDh_12_26_9', 'adx']].head(3))
    
    return df_clean

def main():
    """Main test function"""
    print("Simple signal test...")
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    for symbol in symbols:
        print(f"\n{'='*50}")
        print(f"Testing {symbol}")
        print(f"{'='*50}")
        
        try:
            # Load data
            df_4h, df_1d = load_data(symbol)
            
            # Calculate regime
            df_regime = calculate_regime(df_1d)
            
            # Attach regime
            df_combined = attach_regime_to_4h(df_4h, df_regime)
            
            # Test signals
            df_clean = test_signals(df_combined)
            
        except Exception as e:
            print(f"Error testing {symbol}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
