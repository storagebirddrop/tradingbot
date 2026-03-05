#!/usr/bin/env python3
"""
Simple data acquisition for research - get recent data only
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os

# Configuration
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAMES = ["4h", "1d"]

def setup_exchange():
    """Setup CCXT exchange for historical data"""
    exchange = ccxt.phemex({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    return exchange

def fetch_recent_data(exchange, symbol, timeframe, limit=1000):
    """Fetch recent data for given symbol and timeframe"""
    print(f"Fetching {symbol} {timeframe} data (last {limit} candles)...")
    
    try:
        # Get recent data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        if not ohlcv:
            print(f"  No data available for {symbol} {timeframe}")
            return pd.DataFrame()
                
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"  Retrieved {len(df)} candles")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def calculate_indicators(df):
    """Calculate technical indicators"""
    if df.empty:
        return df
    
    df_ind = df.copy()
    
    # Calculate SMA200
    df_ind['sma200'] = df_ind['close'].rolling(window=200).mean()
    
    # Calculate RSI
    delta = df_ind['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_ind['rsi'] = 100 - (100 / (1 + rs))
    
    # Calculate MACD
    exp1 = df_ind['close'].ewm(span=12).mean()
    exp2 = df_ind['close'].ewm(span=26).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=9).mean()
    histogram = macd - signal_line
    
    df_ind['MACD_12_26_9'] = macd
    df_ind['MACDs_12_26_9'] = signal_line
    df_ind['MACDh_12_26_9'] = histogram
    
    # Calculate ADX (simplified)
    df_ind['adx'] = calculate_adx(df_ind['high'], df_ind['low'], df_ind['close'])
    
    return df_ind

def calculate_adx(high, low, close, period=14):
    """Calculate ADX indicator (simplified)"""
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate Directional Movement
    dm_plus = np.where((high - high.shift(1)) > (low.shift(1) - low), 
                      np.maximum(high - high.shift(1), 0), 0)
    dm_minus = np.where((low.shift(1) - low) > (high - high.shift(1)), 
                        np.maximum(low.shift(1) - low, 0), 0)
    
    # Smooth values
    atr = pd.Series(tr).rolling(window=period).mean()
    di_plus = pd.Series(dm_plus).rolling(window=period).mean() / atr * 100
    di_minus = pd.Series(dm_minus).rolling(window=period).mean() / atr * 100
    
    # Calculate ADX
    dx = abs(di_plus - di_minus) / (di_plus + di_minus) * 100
    adx = dx.rolling(window=period).mean()
    
    return adx

def save_data(df, symbol, timeframe, base_path):
    """Save data to CSV file"""
    if df.empty:
        print(f"  No data to save for {symbol} {timeframe}")
        return None
    
    filename = f"{symbol.replace('/', '_')}_{timeframe}_recent.csv"
    filepath = os.path.join(base_path, filename)
    
    df.to_csv(filepath, index=False)
    print(f"  Saved {len(df)} rows to {filepath}")
    return filepath

def main():
    """Main data acquisition function"""
    print("Starting simple data acquisition for research...")
    print(f"Symbols: {SYMBOLS}")
    print(f"Timeframes: {TIMEFRAMES}")
    
    # Setup exchange
    exchange = setup_exchange()
    
    # Create directories
    historical_path = "/home/dribble0335/dev/tradingbot/research/historical"
    regime_path = "/home/dribble0335/dev/tradingbot/research/regime"
    
    # Data storage
    all_data = {}
    
    # Fetch data for each symbol and timeframe
    for symbol in SYMBOLS:
        symbol_data = {}
        
        for timeframe in TIMEFRAMES:
            try:
                # Fetch OHLCV data
                df = fetch_recent_data(exchange, symbol, timeframe)
                
                # Calculate indicators
                df_with_indicators = calculate_indicators(df)
                
                # Save data
                if timeframe == "4h":
                    save_path = historical_path
                else:  # 1d for regime analysis
                    save_path = regime_path
                
                filepath = save_data(df_with_indicators, symbol, timeframe, save_path)
                symbol_data[timeframe] = filepath
                
                # Small delay between requests
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error processing {symbol} {timeframe}: {e}")
                symbol_data[timeframe] = None
        
        all_data[symbol] = symbol_data
    
    print(f"\nData acquisition complete!")
    print(f"Data saved to:")
    print(f"  - 4h data: {historical_path}")
    print(f"  - 1d data: {regime_path}")

if __name__ == "__main__":
    main()
