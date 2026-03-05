#!/usr/bin/env python3
"""
Alternative APIs Data Acquisition
Testing CoinMarketCap and CoinPaprika for comprehensive historical data
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import json

# API Configurations
APIS = {
    'coinmarketcap': {
        'base_url': 'https://pro-api.coinmarketcap.com/v1',
        'headers': {'X-CMC_PRO_API_KEY': 'YOUR_API_KEY_HERE'},  # Need API key
        'rate_limit': 30.0  # seconds between calls for free tier
    },
    'coinpaprika': {
        'base_url': 'https://api.coinpaprika.com/v1',
        'rate_limit': 1.0  # conservative rate limiting
    }
}

# Symbol mappings for different APIs
SYMBOL_MAPPINGS = {
    'coinmarketcap': {
        'BTC/USDT': '1',  # Bitcoin ID
        'ETH/USDT': '1027',  # Ethereum ID
        'SOL/USDT': '5426'  # Solana ID
    },
    'coinpaprika': {
        'BTC/USDT': 'btc-bitcoin',
        'ETH/USDT': 'eth-ethereum',
        'SOL/USDT': 'sol-solana'
    }
}

def test_coinpaprika_api():
    """Test CoinPaprika API connectivity"""
    print("Testing CoinPaprika API...")
    
    try:
        # Test with Bitcoin recent data
        url = "https://api.coinpaprika.com/v1/coins/btc-bitcoin/ohlcv/latest"
        params = {'quote': 'usd'}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data:
            print(f"✅ CoinPaprika API working - retrieved {len(data)} recent data points")
            print(f"Sample data: {data[:2]}")
            return True
        else:
            print("❌ CoinPaprika API returned no data")
            return False
            
    except Exception as e:
        print(f"❌ CoinPaprika API test failed: {e}")
        return False

def fetch_coinpaprika_historical(coin_id, start_date, end_date):
    """Fetch historical data from CoinPaprika"""
    print(f"Fetching {coin_id} from {start_date.date()} to {end_date.date()}")
    
    try:
        # Convert to required format
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        url = f"https://api.coinpaprika.com/v1/coins/{coin_id}/ohlcv/historical"
        params = {
            'quote': 'usd',
            'start': start_str,
            'end': end_str,
            'interval': '1h'  # Use 1h and resample to 4h
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            print(f"  No data returned for {coin_id}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Rename columns to match our format
        df = df.rename(columns={
            'time_open': 'timestamp',
            'open': 'open',
            'high': 'high', 
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter to date range
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
        
        print(f"  Retrieved {len(df)} hourly candles")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"  Error fetching {coin_id}: {e}")
        return pd.DataFrame()

def test_coinmarketcap_api():
    """Test CoinMarketCap API (requires API key)"""
    print("Testing CoinMarketCap API...")
    
    # Note: This requires a paid API key
    api_key = os.getenv('CMC_API_KEY')
    if not api_key:
        print("❌ CoinMarketCap API key not found in CMC_API_KEY environment variable")
        print("   CoinMarketCap requires a paid API key for historical data")
        return False
    
    try:
        headers = {'X-CMC_PRO_API_KEY': api_key}
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        params = {'limit': 1, 'convert': 'USD'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status', {}).get('error_code') == 0:
            print("✅ CoinMarketCap API working")
            return True
        else:
            print(f"❌ CoinMarketCap API error: {data.get('status', {}).get('error_message')}")
            return False
            
    except Exception as e:
        print(f"❌ CoinMarketCap API test failed: {e}")
        return False

def fetch_coinmarketcap_historical(symbol_id, start_date, end_date):
    """Fetch historical data from CoinMarketCap (requires API key)"""
    api_key = os.getenv('CMC_API_KEY')
    if not api_key:
        print("  CoinMarketCap API key required")
        return pd.DataFrame()
    
    try:
        headers = {'X-CMC_PRO_API_KEY': api_key}
        
        # Convert dates
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())
        
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/ohlcv/historical"
        params = {
            'id': symbol_id,
            'convert': 'USD',
            'time_start': start_ts,
            'time_end': end_ts,
            'interval': 'hourly'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('data', {}).get('quotes'):
            print(f"  No data returned for symbol {symbol_id}")
            return pd.DataFrame()
        
        # Parse the data
        quotes = data['data']['quotes']['USD']
        ohlcv_data = []
        
        for entry in quotes:
            ohlcv_data.append([
                entry['timestamp'],
                entry['open'],
                entry['high'], 
                entry['low'],
                entry['close'],
                entry.get('volume', 0)
            ])
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f"  Retrieved {len(df)} hourly candles")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"  Error fetching CoinMarketCap data: {e}")
        return pd.DataFrame()

def resample_to_timeframe(df, timeframe_hours):
    """Resample data to specific timeframe"""
    if df.empty:
        return df
    
    df_resampled = df.set_index('timestamp')
    freq = f'{timeframe_hours}h'
    df_resampled = df_resampled.resample(freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    return df_resampled.reset_index()

def calculate_indicators(df):
    """Calculate technical indicators"""
    if df.empty:
        return df
    
    df_ind = df.copy()
    
    # SMA200
    df_ind['sma200'] = df_ind['close'].rolling(window=200).mean()
    
    # RSI
    delta = df_ind['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_ind['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df_ind['close'].ewm(span=12).mean()
    exp2 = df_ind['close'].ewm(span=26).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=9).mean()
    histogram = macd - signal_line
    
    df_ind['MACD_12_26_9'] = macd
    df_ind['MACDs_12_26_9'] = signal_line
    df_ind['MACDh_12_26_9'] = histogram
    
    # ADX (simplified)
    df_ind['adx'] = calculate_adx(df_ind['high'], df_ind['low'], df_ind['close'])
    
    return df_ind

def calculate_adx(high, low, close, period=14):
    """Calculate ADX indicator"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    dm_plus = np.where((high - high.shift(1)) > (low.shift(1) - low), 
                      np.maximum(high - high.shift(1), 0), 0)
    dm_minus = np.where((low.shift(1) - low) > (high - high.shift(1)), 
                        np.maximum(low.shift(1) - low, 0), 0)
    
    atr = pd.Series(tr).rolling(window=period).mean()
    di_plus = pd.Series(dm_plus).rolling(window=period).mean() / atr * 100
    di_minus = pd.Series(dm_minus).rolling(window=period).mean() / atr * 100
    
    dx = abs(di_plus - di_minus) / (di_plus + di_minus) * 100
    adx = dx.rolling(window=period).mean()
    
    return adx

def acquire_alternative_api_data():
    """Test and acquire data from alternative APIs"""
    print("ALTERNATIVE APIS DATA ACQUISITION")
    print("=" * 60)
    
    # Market periods to test
    test_periods = {
        'covid_crash': (datetime(2020, 3, 1), datetime(2020, 7, 1)),
        'bull_peak': (datetime(2021, 11, 1), datetime(2022, 1, 31)),
        'recovery': (datetime(2023, 1, 1), datetime(2023, 6, 1))
    }
    
    # Test APIs
    coinpaprika_works = test_coinpaprika_api()
    coinmarketcap_works = test_coinmarketcap_api()
    
    print(f"\nAPI Test Results:")
    print(f"  CoinPaprika: {'✅ Working' if coinpaprika_works else '❌ Failed'}")
    print(f"  CoinMarketCap: {'✅ Working' if coinmarketcap_works else '❌ Failed (needs API key)'}")
    
    if not coinpaprika_works and not coinmarketcap_works:
        print("\n❌ No working APIs available for historical data acquisition")
        return
    
    # Try to acquire sample data with working APIs
    working_api = 'coinpaprika' if coinpaprika_works else 'coinmarketcap'
    symbol_mapping = SYMBOL_MAPPINGS[working_api]
    
    print(f"\n{'='*60}")
    print(f"TESTING {working_api.upper()} FOR HISTORICAL DATA")
    print(f"{'='*60}")
    
    # Test with Bitcoin for one period
    test_symbol = 'BTC/USDT'
    coin_id = symbol_mapping[test_symbol]
    
    for period_name, (start_date, end_date) in test_periods.items():
        print(f"\nTesting {period_name}:")
        
        if working_api == 'coinpaprika':
            df = fetch_coinpaprika_historical(coin_id, start_date, end_date)
        else:
            symbol_id = symbol_mapping[test_symbol]
            df = fetch_coinmarketcap_historical(symbol_id, start_date, end_date)
        
        if not df.empty:
            print(f"  ✅ Successfully retrieved {len(df)} hourly candles")
            
            # Resample to 4h and calculate indicators
            df_4h = resample_to_timeframe(df, 4)
            df_4h_indicators = calculate_indicators(df_4h)
            
            print(f"  ✅ Resampled to {len(df_4h)} 4h candles with indicators")
            print(f"  📊 Date range: {df_4h['timestamp'].min()} to {df_4h['timestamp'].max()}")
            
            # Save sample
            filename = f"{test_symbol.replace('/', '_')}_4h_{period_name}_{working_api}.csv"
            filepath = f"/home/dribble0335/dev/tradingbot/research/historical/{filename}"
            df_4h_indicators.to_csv(filepath, index=False)
            print(f"  💾 Saved to {filepath}")
        else:
            print(f"  ❌ Failed to retrieve data for {period_name}")
        
        # Rate limiting
        time.sleep(2.0)

def main():
    """Main function to test alternative APIs"""
    print("TESTING ALTERNATIVE APIs FOR HISTORICAL DATA")
    print("=" * 60)
    
    # Create directories
    os.makedirs("/home/dribble0335/dev/tradingbot/research/historical", exist_ok=True)
    os.makedirs("/home/dribble0335/dev/tradingbot/research/regime", exist_ok=True)
    
    acquire_alternative_api_data()
    
    print(f"\n{'='*60}")
    print("ALTERNATIVE API TESTING COMPLETE")
    print(f"{'='*60}")
    print("Check the research/historical directory for any acquired data")
    print("If successful, we can proceed with comprehensive historical analysis")

if __name__ == "__main__":
    main()
