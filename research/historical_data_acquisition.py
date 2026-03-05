#!/usr/bin/env python3
"""
Historical Data Acquisition for Comprehensive Research
Covers multiple market conditions and time periods
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os

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

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAMES = ["4h", "1d"]

def setup_exchange():
    """Setup CCXT exchange"""
    exchange = ccxt.phemex({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    return exchange

def fetch_historical_data(exchange, symbol, timeframe, start_date, end_date):
    """Fetch historical data for specific period"""
    print(f"Fetching {symbol} {timeframe} from {start_date.date()} to {end_date.date()}")
    
    try:
        # Convert to milliseconds
        since = int(start_date.timestamp() * 1000)
        until = int(end_date.timestamp() * 1000)
        
        all_data = []
        current_since = since
        batch_size = 500  # CCXT limit
        
        while current_since < until:
            try:
                # Fetch data in batches
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=batch_size)
                
                if not ohlcv:
                    print(f"  No more data available")
                    break
                
                # Filter to our date range
                filtered_ohlcv = [candle for candle in ohlcv if current_since <= candle[0] <= until]
                all_data.extend(filtered_ohlcv)
                
                # Update timestamp
                if ohlcv:
                    current_since = ohlcv[-1][0] + 1
                
                # Progress indicator
                if len(all_data) % 1000 == 0:
                    latest_date = datetime.fromtimestamp(ohlcv[-1][0] / 1000)
                    print(f"  Progress: {len(all_data)} candles, latest: {latest_date.date()}")
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"  Batch error: {e}")
                time.sleep(1)
                continue
        
        if not all_data:
            print(f"  No data retrieved for {symbol} {timeframe}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"  Retrieved {len(df)} candles")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"  Error fetching {symbol} {timeframe}: {e}")
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

def save_historical_data(df, symbol, timeframe, period_name, data_type):
    """Save historical data"""
    if df.empty:
        print(f"  No data to save for {symbol} {timeframe} {period_name}")
        return None
    
    filename = f"{symbol.replace('/', '_')}_{timeframe}_{period_name}.csv"
    
    if data_type == '4h':
        filepath = f"/home/dribble0335/dev/tradingbot/research/historical/{filename}"
    else:  # 1d
        filepath = f"/home/dribble0335/dev/tradingbot/research/regime/{filename}"
    
    df.to_csv(filepath, index=False)
    print(f"  Saved {len(df)} rows to {filepath}")
    return filepath

def acquire_period_data(period_name, period_info):
    """Acquire data for a specific market period"""
    print(f"\n{'='*60}")
    print(f"ACQUIRING DATA: {period_name.upper()}")
    print(f"Description: {period_info['description']}")
    print(f"Period: {period_info['start'].date()} to {period_info['end'].date()}")
    print(f"{'='*60}")
    
    exchange = setup_exchange()
    acquired_files = {}
    
    for symbol in SYMBOLS:
        symbol_files = {}
        
        for timeframe in TIMEFRAMES:
            print(f"\n{symbol} {timeframe}:")
            
            # Fetch data
            df = fetch_historical_data(exchange, symbol, timeframe, 
                                      period_info['start'], period_info['end'])
            
            if not df.empty:
                # Calculate indicators
                df_with_indicators = calculate_indicators(df)
                
                # Save data
                filepath = save_historical_data(df_with_indicators, symbol, timeframe, 
                                              period_name, timeframe)
                symbol_files[timeframe] = filepath
            else:
                symbol_files[timeframe] = None
            
            # Rate limiting between symbols
            time.sleep(0.5)
        
        acquired_files[symbol] = symbol_files
    
    return acquired_files

def main():
    """Main historical data acquisition"""
    print("COMPREHENSIVE HISTORICAL DATA ACQUISITION")
    print("=" * 60)
    print("This will acquire data from multiple market periods")
    print("to test strategy performance across different conditions")
    
    # Create directories
    os.makedirs("/home/dribble0335/dev/tradingbot/research/historical", exist_ok=True)
    os.makedirs("/home/dribble0335/dev/tradingbot/research/regime", exist_ok=True)
    
    all_acquisitions = {}
    
    # Acquire data for each period
    for period_name, period_info in MARKET_PERIODS.items():
        try:
            acquired_files = acquire_period_data(period_name, period_info)
            all_acquisitions[period_name] = acquired_files
        except Exception as e:
            print(f"Error acquiring {period_name}: {e}")
            all_acquisitions[period_name] = {}
    
    # Summary
    print(f"\n{'='*60}")
    print("ACQUISITION SUMMARY")
    print(f"{'='*60}")
    
    for period_name, files in all_acquisitions.items():
        print(f"\n{period_name}:")
        for symbol, timeframes in files.items():
            print(f"  {symbol}:")
            for tf, filepath in timeframes.items():
                status = "✅" if filepath else "❌"
                print(f"    {tf}: {status}")
    
    print(f"\nData acquisition complete!")
    print("Ready for comprehensive multi-period analysis")

if __name__ == "__main__":
    main()