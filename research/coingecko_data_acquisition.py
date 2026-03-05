#!/usr/bin/env python3
"""
Historical Data Acquisition via CoinGecko API
Comprehensive market coverage across multiple periods
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import json

# CoinGecko API configuration
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
RATE_LIMIT_DELAY = 1.0  # 1 second between requests

# Market periods to research
MARKET_PERIODS = {
    'covid_crash': {
        'start': datetime(2020, 2, 1),
        'end': datetime(2020, 12, 31),
        'description': 'COVID crash & recovery - extreme volatility'
    },
    'bull_peak_bear': {
        'start': datetime(2021, 11, 1),
        'end': datetime(2022, 12, 31),
        'description': 'Bull market peak & bear market - major trend reversal'
    },
    'recovery_period': {
        'start': datetime(2023, 1, 1),
        'end': datetime(2024, 12, 31),
        'description': 'Post-bear market recovery - transition period'
    }
}

# Symbol mapping for CoinGecko
COINGECKO_SYMBOLS = {
    'BTC/USDT': 'bitcoin',
    'ETH/USDT': 'ethereum', 
    'SOL/USDT': 'solana'
}

TIMEFRAMES = {
    '4h': {'hours': 4},
    '1d': {'hours': 24}
}

def fetch_coingecko_ohlcv(coin_id, start_date, end_date, days='max'):
    """Fetch OHLCV data from CoinGecko API"""
    print(f"Fetching {coin_id} data from {start_date.date()} to {end_date.date()}")
    
    try:
        # Convert dates to timestamps
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        # Calculate days between dates
        days_between = (end_date - start_date).days
        if days_between > 365:
            days_param = 'max'
        else:
            days_param = days_between + 10  # Add buffer
        
        # Make API request
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/ohlc"
        params = {
            'vs_currency': 'usd',
            'days': days_param
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse response (CoinGecko returns [timestamp, open, high, low, close])
        data = response.json()
        
        if not data:
            print(f"  No data returned for {coin_id}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Filter to our date range
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
        
        # Add placeholder volume (CoinGecko free API doesn't provide volume in OHLC)
        df['volume'] = 0.0
        
        print(f"  Retrieved {len(df)} candles")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"  API error for {coin_id}: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"  Error processing {coin_id}: {e}")
        return pd.DataFrame()

def resample_to_timeframe(df, timeframe_hours):
    """Resample data to specific timeframe"""
    if df.empty:
        return df
    
    # Set timestamp as index
    df_resampled = df.set_index('timestamp')
    
    # Resample based on timeframe
    freq = f'{timeframe_hours}h'
    df_resampled = df_resampled.resample(freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # Reset index
    df_resampled = df_resampled.reset_index()
    
    return df_resampled

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

def save_coingecko_data(df, symbol, timeframe, period_name, data_type):
    """Save CoinGecko data"""
    if df.empty:
        print(f"  No data to save for {symbol} {timeframe} {period_name}")
        return None
    
    filename = f"{symbol.replace('/', '_')}_{timeframe}_{period_name}_coingecko.csv"
    
    if data_type == '4h':
        filepath = f"/home/dribble0335/dev/tradingbot/research/historical/{filename}"
    else:  # 1d
        filepath = f"/home/dribble0335/dev/tradingbot/research/regime/{filename}"
    
    df.to_csv(filepath, index=False)
    print(f"  Saved {len(df)} rows to {filepath}")
    return filepath

def acquire_coingecko_period(period_name, period_info):
    """Acquire data for a specific market period using CoinGecko"""
    print(f"\n{'='*60}")
    print(f"ACQUIRING COINGECKO DATA: {period_name.upper()}")
    print(f"Description: {period_info['description']}")
    print(f"Period: {period_info['start'].date()} to {period_info['end'].date()}")
    print(f"{'='*60}")
    
    acquired_files = {}
    
    for symbol, coin_id in COINGECKO_SYMBOLS.items():
        symbol_files = {}
        
        print(f"\n{symbol} ({coin_id}):")
        
        # Fetch daily data (CoinGecko's primary format)
        df_daily = fetch_coingecko_ohlcv(coin_id, period_info['start'], period_info['end'])
        
        if not df_daily.empty:
            # Calculate indicators on daily data
            df_daily_indicators = calculate_indicators(df_daily)
            
            # Save daily data
            daily_filepath = save_coingecko_data(df_daily_indicators, symbol, '1d', period_name, '1d')
            symbol_files['1d'] = daily_filepath
            
            # Resample to 4h
            df_4h = resample_to_timeframe(df_daily, 4)
            df_4h_indicators = calculate_indicators(df_4h)
            
            # Save 4h data
            fourh_filepath = save_coingecko_data(df_4h_indicators, symbol, '4h', period_name, '4h')
            symbol_files['4h'] = fourh_filepath
        else:
            symbol_files['1d'] = None
            symbol_files['4h'] = None
        
        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)
    
    acquired_files[symbol] = symbol_files
    
    return acquired_files

def test_coingecko_api():
    """Test CoinGecko API connectivity"""
    print("Testing CoinGecko API connectivity...")
    
    try:
        # Test with Bitcoin recent data
        url = f"{COINGECKO_BASE_URL}/coins/bitcoin/ohlc"
        params = {'vs_currency': 'usd', 'days': 7}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data:
            print(f"✅ CoinGecko API working - retrieved {len(data)} recent data points")
            return True
        else:
            print("❌ CoinGecko API returned no data")
            return False
            
    except Exception as e:
        print(f"❌ CoinGecko API test failed: {e}")
        return False

def main():
    """Main CoinGecko data acquisition"""
    print("COINGECKO HISTORICAL DATA ACQUISITION")
    print("=" * 60)
    print("Acquiring comprehensive historical data across multiple market periods")
    
    # Test API connectivity first
    if not test_coingecko_api():
        print("API connectivity failed - aborting acquisition")
        return
    
    # Create directories
    os.makedirs("/home/dribble0335/dev/tradingbot/research/historical", exist_ok=True)
    os.makedirs("/home/dribble0335/dev/tradingbot/research/regime", exist_ok=True)
    
    all_acquisitions = {}
    
    # Acquire data for each period
    for period_name, period_info in MARKET_PERIODS.items():
        try:
            acquired_files = acquire_coingecko_period(period_name, period_info)
            all_acquisitions[period_name] = acquired_files
        except Exception as e:
            print(f"Error acquiring {period_name}: {e}")
            all_acquisitions[period_name] = {}
    
    # Summary
    print(f"\n{'='*60}")
    print("COINGECKO ACQUISITION SUMMARY")
    print(f"{'='*60}")
    
    for period_name, files in all_acquisitions.items():
        print(f"\n{period_name}:")
        for symbol, timeframes in files.items():
            print(f"  {symbol}:")
            for tf, filepath in timeframes.items():
                status = "✅" if filepath else "❌"
                print(f"    {tf}: {status}")
    
    # Save metadata
    metadata = {
        'source': 'coingecko_api',
        'acquisition_date': datetime.now().isoformat(),
        'periods': list(MARKET_PERIODS.keys()),
        'symbols': list(COINGECKO_SYMBOLS.keys()),
        'timeframes': list(TIMEFRAMES.keys()),
        'limitations': [
            'Volume data not available in free API',
            'API rate limited to ~10 calls/minute',
            'Data may have gaps for very old periods'
        ]
    }
    
    with open("/home/dribble0335/dev/tradingbot/research/coingecko_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nCoinGecko data acquisition complete!")
    print("Ready for comprehensive multi-period analysis")

if __name__ == "__main__":
    main()
