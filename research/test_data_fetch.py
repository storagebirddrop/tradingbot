#!/usr/bin/env python3
"""
Test script to debug data fetching issues
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time

def test_data_fetch():
    """Test basic data fetching"""
    print("Testing basic data fetch...")
    
    # Setup exchange
    exchange = ccxt.phemex({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    
    # Test with BTC/USDT 4h
    try:
        print("Fetching BTC/USDT 4h data...")
        
        # Get recent data (last 100 candles)
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '4h', limit=100)
        
        print(f"Successfully fetched {len(ohlcv)} candles")
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        
        print(f"DataFrame shape: {df.shape}")
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"Sample data:\n{df.head()}")
        
        return df
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_historical_fetch():
    """Test historical data fetching"""
    print("\nTesting historical data fetch...")
    
    exchange = ccxt.phemex({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    
    try:
        # Try to get data from 2023
        start_date = datetime(2023, 1, 1)
        since = int(start_date.timestamp() * 1000)
        
        print(f"Fetching data since {start_date} (timestamp: {since})")
        
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '4h', since=since, limit=500)
        
        print(f"Successfully fetched {len(ohlcv)} candles")
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    # Test basic fetch
    df1 = test_data_fetch()
    
    # Test historical fetch
    df2 = test_historical_fetch()
    
    if df1 is not None:
        print("\nBasic fetch successful!")
    
    if df2 is not None:
        print("Historical fetch successful!")
