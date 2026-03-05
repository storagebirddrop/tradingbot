#!/usr/bin/env python3
"""
Data Acquisition Script for Short Strategy Research
Downloads historical data for signal validation and backtesting
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import json

# Configuration
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]  # Start with 3 symbols for testing
TIMEFRAMES = ["4h", "1d"]
START_DATE = datetime(2024, 1, 1)  # Use 2024 for more recent data
END_DATE = datetime(2024, 12, 31)

def setup_exchange():
    """Setup CCXT exchange for historical data"""
    exchange = ccxt.phemex({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    return exchange

def fetch_ohlcv_data(exchange, symbol, timeframe, start_date, end_date):
    """Fetch OHLCV data for given symbol and timeframe"""
    print(f"Fetching {symbol} {timeframe} data from {start_date.date()} to {end_date.date()}")
    
    # Try to get recent data first (more reliable)
    try:
        # Get recent data (last 1000 candles)
        limit = 1000
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        if not ohlcv:
            print(f"  No data available for {symbol} {timeframe}")
            return pd.DataFrame()
                
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Filter to desired date range
        start_ts = pd.Timestamp(start_date, tz='UTC')
        end_ts = pd.Timestamp(end_date, tz='UTC')
        df = df[(df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)]
        
        print(f"  Retrieved {len(df)} candles from {len(ohlcv)} total")
        
        # If no data in range, return recent data for testing
        if len(df) == 0:
            print(f"  No data in specified range, using recent data for testing")
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Use last 6 months for testing
            six_months_ago = pd.Timestamp.now() - pd.Timedelta(days=180)
            df = df[df['timestamp'] >= six_months_ago]
        
        return df
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def calculate_indicators(df):
    """Calculate technical indicators for analysis"""
    # Import strategy functions with proper path handling
    import sys
    sys.path.append('/home/dribble0335/dev/tradingbot')
    
    try:
        from strategy import compute_4h_indicators, compute_daily_regime, attach_regime_to_4h
    except ImportError:
        print("Warning: Could not import strategy functions, using basic indicators")
        return calculate_basic_indicators(df)
    
    # Make a copy to avoid modifying original
    df_ind = df.copy()
    
    # Calculate basic indicators
    df_ind['sma200'] = df_ind['close'].rolling(window=200).mean()
    df_ind['rsi'] = calculate_rsi(df_ind['close'])
    
    # Calculate MACD
    macd = calculate_macd(df_ind['close'])
    df_ind = pd.concat([df_ind, macd], axis=1)
    
    # Calculate ADX
    df_ind['adx'] = calculate_adx(df_ind['high'], df_ind['low'], df_ind['close'])
    
    return df_ind

def calculate_basic_indicators(df):
    """Calculate basic indicators without strategy module"""
    df_ind = df.copy()
    
    # Calculate basic indicators
    df_ind['sma200'] = df_ind['close'].rolling(window=200).mean()
    df_ind['rsi'] = calculate_rsi(df_ind['close'])
    
    # Calculate MACD
    macd = calculate_macd(df_ind['close'])
    df_ind = pd.concat([df_ind, macd], axis=1)
    
    # Calculate ADX
    df_ind['adx'] = calculate_adx(df_ind['high'], df_ind['low'], df_ind['close'])
    
    return df_ind

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD indicator"""
    exp1 = prices.ewm(span=fast).mean()
    exp2 = prices.ewm(span=slow).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line
    
    return pd.DataFrame({
        'MACD_12_26_9': macd,
        'MACDs_12_26_9': signal_line,
        'MACDh_12_26_9': histogram
    })

def calculate_adx(high, low, close, period=14):
    """Calculate ADX indicator"""
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
    filename = f"{symbol.replace('/', '_')}_{timeframe}_{START_DATE.year}_{END_DATE.year}.csv"
    filepath = os.path.join(base_path, filename)
    
    df.to_csv(filepath, index=False)
    print(f"Saved {len(df)} rows to {filepath}")
    return filepath

def fetch_funding_rates(exchange, symbols, start_date, end_date):
    """Fetch funding rates for perpetual swaps (if available)"""
    print("Fetching funding rates...")
    
    funding_data = {}
    
    for symbol in symbols:
        try:
            # Convert to perpetual swap symbol format
            perp_symbol = f"{symbol.replace('/', '')}:USDT"
            
            # Note: Phemex may not have public funding rate history
            # This is a placeholder for future implementation
            print(f"Funding rates for {perp_symbol} not yet implemented")
            funding_data[symbol] = None
            
        except Exception as e:
            print(f"Could not fetch funding rates for {symbol}: {e}")
            funding_data[symbol] = None
    
    return funding_data

def main():
    """Main data acquisition function"""
    print("Starting data acquisition for short strategy research")
    print(f"Symbols: {SYMBOLS}")
    print(f"Timeframes: {TIMEFRAMES}")
    print(f"Date range: {START_DATE.date()} to {END_DATE.date()}")
    
    # Setup exchange
    exchange = setup_exchange()
    
    # Create directories
    historical_path = "/home/dribble0335/dev/tradingbot/research/historical"
    regime_path = "/home/dribble0335/dev/tradingbot/research/regime"
    funding_path = "/home/dribble0335/dev/tradingbot/research/funding_rates"
    
    # Data storage
    all_data = {}
    
    # Fetch data for each symbol and timeframe
    for symbol in SYMBOLS:
        symbol_data = {}
        
        for timeframe in TIMEFRAMES:
            try:
                # Fetch OHLCV data
                df = fetch_ohlcv_data(exchange, symbol, timeframe, START_DATE, END_DATE)
                
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
    
    # Try to fetch funding rates
    funding_data = fetch_funding_rates(exchange, SYMBOLS, START_DATE, END_DATE)
    
    # Save metadata
    metadata = {
        'symbols': SYMBOLS,
        'timeframes': TIMEFRAMES,
        'start_date': START_DATE.isoformat(),
        'end_date': END_DATE.isoformat(),
        'data_files': all_data,
        'funding_data': funding_data
    }
    
    metadata_path = "/home/dribble0335/dev/tradingbot/research/data_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nData acquisition complete!")
    print(f"Metadata saved to {metadata_path}")
    print(f"Data saved to:")
    print(f"  - 4h data: {historical_path}")
    print(f"  - 1d data: {regime_path}")
    print(f"  - Funding data: {funding_path}")

if __name__ == "__main__":
    main()
