#!/usr/bin/env python3
"""
Robust Historical Data Acquisition
Works within API limitations to get maximum historical coverage
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import json

# API Configuration
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
RATE_LIMIT_DELAY = 2.0  # Conservative rate limiting

# Simplified approach - get maximum available data
SYMBOLS = {
    'BTC/USDT': 'bitcoin',
    'ETH/USDT': 'ethereum', 
    'SOL/USDT': 'solana'
}

def fetch_max_coingecko_data(coin_id):
    """Fetch maximum available historical data from CoinGecko"""
    print(f"Fetching maximum available data for {coin_id}...")
    
    try:
        # Use 'max' days parameter
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/ohlc"
        params = {
            'vs_currency': 'usd',
            'days': 'max'
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        
        if not data:
            print(f"  No data returned for {coin_id}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Add placeholder volume
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

def analyze_data_coverage(df, symbol):
    """Analyze what market periods are covered in the data"""
    if df.empty:
        return {}
    
    coverage = {
        'total_candles': len(df),
        'date_range': {
            'start': df['timestamp'].min(),
            'end': df['timestamp'].max()
        },
        'market_periods': {}
    }
    
    # Define key market periods
    periods = {
        'covid_crash': (datetime(2020, 2, 1), datetime(2020, 12, 31)),
        'bull_peak_bear': (datetime(2021, 11, 1), datetime(2022, 12, 31)),
        'recovery_period': (datetime(2023, 1, 1), datetime(2024, 12, 31)),
        'recent_period': (datetime(2025, 1, 1), datetime(2026, 3, 31))
    }
    
    for period_name, (start, end) in periods.items():
        period_data = df[(df['timestamp'] >= start) & (df['timestamp'] <= end)]
        coverage['market_periods'][period_name] = {
            'covered': len(period_data) > 0,
            'candles': len(period_data),
            'start_date': period_data['timestamp'].min() if not period_data.empty else None,
            'end_date': period_data['timestamp'].max() if not period_data.empty else None
        }
    
    return coverage

def save_comprehensive_data(df, symbol, timeframe):
    """Save comprehensive data"""
    if df.empty:
        print(f"  No data to save for {symbol} {timeframe}")
        return None
    
    filename = f"{symbol.replace('/', '_')}_{timeframe}_comprehensive.csv"
    
    if timeframe == '4h':
        filepath = f"/home/dribble0335/dev/tradingbot/research/historical/{filename}"
    else:  # 1d
        filepath = f"/home/dribble0335/dev/tradingbot/research/regime/{filename}"
    
    df.to_csv(filepath, index=False)
    print(f"  Saved {len(df)} rows to {filepath}")
    return filepath

def main():
    """Main robust data acquisition"""
    print("ROBUST HISTORICAL DATA ACQUISITION")
    print("=" * 60)
    print("Getting maximum available data within API limitations")
    
    # Create directories
    os.makedirs("/home/dribble0335/dev/tradingbot/research/historical", exist_ok=True)
    os.makedirs("/home/dribble0335/dev/tradingbot/research/regime", exist_ok=True)
    
    all_data = {}
    coverage_analysis = {}
    
    # Acquire data for each symbol
    for symbol, coin_id in SYMBOLS.items():
        print(f"\n{'='*50}")
        print(f"PROCESSING {symbol} ({coin_id})")
        print(f"{'='*50}")
        
        # Fetch maximum available data
        df_daily = fetch_max_coingecko_data(coin_id)
        
        if not df_daily.empty:
            # Calculate indicators
            df_daily_indicators = calculate_indicators(df_daily)
            
            # Analyze coverage
            coverage = analyze_data_coverage(df_daily_indicators, symbol)
            coverage_analysis[symbol] = coverage
            
            print(f"\nCoverage Analysis:")
            print(f"  Total candles: {coverage['total_candles']}")
            print(f"  Date range: {coverage['date_range']['start']} to {coverage['date_range']['end']}")
            
            for period, info in coverage['market_periods'].items():
                if info['covered']:
                    print(f"  {period}: ✅ {info['candles']} candles")
                else:
                    print(f"  {period}: ❌ Not covered")
            
            # Save daily data
            daily_filepath = save_comprehensive_data(df_daily_indicators, symbol, '1d')
            
            # Resample to 4h and save
            df_4h = resample_to_timeframe(df_daily_indicators, 4)
            df_4h_indicators = calculate_indicators(df_4h)
            fourh_filepath = save_comprehensive_data(df_4h_indicators, symbol, '4h')
            
            all_data[symbol] = {
                'daily': daily_filepath,
                '4h': fourh_filepath,
                'coverage': coverage
            }
        else:
            coverage_analysis[symbol] = {'error': 'No data retrieved'}
            all_data[symbol] = {'error': 'No data retrieved'}
        
        # Rate limiting between symbols
        time.sleep(RATE_LIMIT_DELAY)
    
    # Save coverage analysis
    with open("/home/dribble0335/dev/tradingbot/research/data_coverage_analysis.json", 'w') as f:
        json.dump(coverage_analysis, f, indent=2, default=str)
    
    # Summary
    print(f"\n{'='*60}")
    print("ACQUISITION SUMMARY")
    print(f"{'='*60}")
    
    for symbol, data in all_data.items():
        print(f"\n{symbol}:")
        if 'error' in data:
            print(f"  ❌ {data['error']}")
        else:
            print(f"  ✅ Daily data: {data['daily']}")
            print(f"  ✅ 4h data: {data['4h']}")
            coverage = data['coverage']
            covered_periods = [p for p, info in coverage['market_periods'].items() if info['covered']]
            print(f"  📊 Covered periods: {', '.join(covered_periods)}")
    
    print(f"\nData acquisition complete!")
    print("Coverage analysis saved to: data_coverage_analysis.json")
    print("Ready for comprehensive multi-period analysis")

if __name__ == "__main__":
    main()
