#!/usr/bin/env python3
"""
Comprehensive Historical Data Acquisition via Binance API
Covers multiple market periods for robust strategy testing
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os

# Market periods for comprehensive research
MARKET_PERIODS = {
    'covid_crash': {
        'start': datetime(2020, 2, 1),
        'end': datetime(2020, 6, 30),
        'description': 'COVID crash & recovery - extreme volatility'
    },
    'bull_peak_bear': {
        'start': datetime(2021, 11, 1),
        'end': datetime(2022, 3, 31),
        'description': 'Bull market peak & bear transition - major trend reversal'
    },
    'recovery_period': {
        'start': datetime(2023, 1, 1),
        'end': datetime(2023, 6, 30),
        'description': 'Post-bear market recovery - transition period'
    },
    'recent_period': {
        'start': datetime(2025, 9, 1),
        'end': datetime(2026, 3, 31),
        'description': 'Recent risk-off period - current market conditions'
    }
}

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAMES = ["4h", "1d"]

def fetch_binance_historical(symbol, interval, start_date, end_date):
    """Fetch historical data from Binance API"""
    print(f"Fetching {symbol} {interval} from {start_date.date()} to {end_date.date()}")
    
    try:
        url = "https://api.binance.com/api/v3/klines"
        
        all_data = []
        current_start = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        
        while current_start < end_timestamp:
            params = {
                'symbol': symbol.replace('/', ''),
                'interval': interval,
                'startTime': current_start,
                'endTime': end_timestamp,
                'limit': 1000
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                break
                
            all_data.extend(data)
            
            # Update start time to avoid duplicates
            if data:
                current_start = data[-1][0] + 1
            
            # Rate limiting
            time.sleep(0.1)
        
        if not all_data:
            print(f"  No data retrieved for {symbol}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        # Convert and clean
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        
        print(f"  Retrieved {len(df)} {interval} candles")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return pd.DataFrame()

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

def save_historical_data(df, symbol, timeframe, period_name):
    """Save historical data with proper naming"""
    if df.empty:
        print(f"  No data to save for {symbol} {timeframe} {period_name}")
        return None
    
    filename = f"{symbol.replace('/', '_')}_{timeframe}_{period_name}_binance.csv"
    
    if timeframe == '4h':
        filepath = f"/home/dribble0335/dev/tradingbot/research/historical/{filename}"
    else:  # 1d
        filepath = f"/home/dribble0335/dev/tradingbot/research/regime/{filename}"
    
    df.to_csv(filepath, index=False)
    print(f"  Saved {len(df)} rows to {filepath}")
    return filepath

def acquire_comprehensive_historical_data():
    """Acquire comprehensive historical data across all market periods"""
    print("COMPREHENSIVE HISTORICAL DATA ACQUISITION")
    print("=" * 60)
    print("Using Binance API for maximum historical coverage")
    
    # Create directories
    os.makedirs("/home/dribble0335/dev/tradingbot/research/historical", exist_ok=True)
    os.makedirs("/home/dribble0335/dev/tradingbot/research/regime", exist_ok=True)
    
    all_acquisitions = {}
    
    # Acquire data for each period
    for period_name, period_info in MARKET_PERIODS.items():
        print(f"\n{'='*60}")
        print(f"ACQUIRING: {period_name.upper()}")
        print(f"Description: {period_info['description']}")
        print(f"Period: {period_info['start'].date()} to {period_info['end'].date()}")
        print(f"{'='*60}")
        
        period_data = {}
        
        for symbol in SYMBOLS:
            symbol_data = {}
            
            for timeframe in TIMEFRAMES:
                print(f"\n{symbol} {timeframe}:")
                
                # Fetch data
                df = fetch_binance_historical(symbol, timeframe, 
                                             period_info['start'], period_info['end'])
                
                if not df.empty:
                    # Calculate indicators
                    df_indicators = calculate_indicators(df)
                    
                    # Save data
                    filepath = save_historical_data(df_indicators, symbol, timeframe, period_name)
                    symbol_data[timeframe] = filepath
                    
                    # Basic stats
                    clean_data = df_indicators.dropna()
                    print(f"  Clean data: {len(clean_data)} rows")
                    print(f"  Price range: ${df_indicators['close'].min():.2f} - ${df_indicators['close'].max():.2f}")
                else:
                    symbol_data[timeframe] = None
                
                # Rate limiting between requests
                time.sleep(0.5)
            
            period_data[symbol] = symbol_data
        
        all_acquisitions[period_name] = period_data
    
    return all_acquisitions

def analyze_data_coverage(all_acquisitions):
    """Analyze the coverage of acquired data"""
    print(f"\n{'='*60}")
    print("DATA COVERAGE ANALYSIS")
    print(f"{'='*60}")
    
    coverage_summary = {}
    
    for period_name, period_data in all_acquisitions.items():
        print(f"\n{period_name.upper()}:")
        
        period_summary = {'symbols': {}, 'total_candles': 0}
        
        for symbol, symbol_data in period_data.items():
            symbol_summary = {'4h': 0, '1d': 0}
            
            for timeframe, filepath in symbol_data.items():
                if filepath and os.path.exists(filepath):
                    df = pd.read_csv(filepath)
                    symbol_summary[timeframe] = len(df)
                    period_summary['total_candles'] += len(df)
                    
                    print(f"  {symbol} {timeframe}: {len(df)} candles ✅")
                else:
                    print(f"  {symbol} {timeframe}: 0 candles ❌")
            
            period_summary['symbols'][symbol] = symbol_summary
        
        coverage_summary[period_name] = period_summary
    
    # Overall summary
    print(f"\n{'='*60}")
    print("OVERALL ACQUISITION SUMMARY")
    print(f"{'='*60}")
    
    total_candles = sum(period['total_candles'] for period in coverage_summary.values())
    print(f"Total candles acquired: {total_candles:,}")
    print(f"Market periods covered: {len(coverage_summary)}")
    print(f"Symbols covered: {len(SYMBOLS)}")
    print(f"Timeframes: {len(TIMEFRAMES)}")
    
    return coverage_summary

def main():
    """Main function"""
    print("BINANCE COMPREHENSIVE HISTORICAL DATA ACQUISITION")
    print("=" * 60)
    
    try:
        # Acquire comprehensive data
        all_acquisitions = acquire_comprehensive_historical_data()
        
        # Analyze coverage
        coverage = analyze_data_coverage(all_acquisitions)
        
        print(f"\n{'='*60}")
        print("ACQUISITION COMPLETE")
        print(f"{'='*60}")
        print("Historical data ready for comprehensive multi-period analysis")
        print("Ready to test strategies across different market conditions")
        
    except Exception as e:
        print(f"Error during acquisition: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
