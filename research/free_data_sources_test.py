#!/usr/bin/env python3
"""
Testing Free Data Sources for Historical Cryptocurrency Data
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os

def test_binance_public_api():
    """Test Binance public API for historical data"""
    print("Testing Binance public API...")
    
    try:
        # Test with BTC/USDT recent data
        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': 'BTCUSDT',
            'interval': '4h',
            'limit': 100
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data:
            print(f"✅ Binance API working - retrieved {len(data)} recent data points")
            
            # Convert to DataFrame
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            print(f"Sample: {df[['timestamp', 'open', 'high', 'low', 'close']].head(2)}")
            return True
        else:
            print("❌ Binance API returned no data")
            return False
            
    except Exception as e:
        print(f"❌ Binance API test failed: {e}")
        return False

def fetch_binance_historical(symbol, interval, start_date, end_date):
    """Fetch historical data from Binance"""
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

def test_yahoo_finance_api():
    """Test Yahoo Finance API (yfinance)"""
    print("Testing Yahoo Finance API...")
    
    try:
        import yfinance as yf
        
        # Test with Bitcoin
        btc = yf.Ticker('BTC-USD')
        data = btc.history(period="5d", interval="1h")
        
        if not data.empty:
            print(f"✅ Yahoo Finance API working - retrieved {len(data)} recent data points")
            print(f"Sample: {data.head(2)}")
            return True
        else:
            print("❌ Yahoo Finance API returned no data")
            return False
            
    except ImportError:
        print("❌ yfinance library not installed")
        print("   Install with: pip install yfinance")
        return False
    except Exception as e:
        print(f"❌ Yahoo Finance API test failed: {e}")
        return False

def fetch_yahoo_finance_data(symbol, start_date, end_date):
    """Fetch data from Yahoo Finance"""
    try:
        import yfinance as yf
        
        # Convert symbol format
        ticker = symbol.replace('/USDT', '-USD')
        
        # Create ticker object
        ticker_obj = yf.Ticker(ticker)
        
        # Fetch historical data
        data = ticker_obj.history(start=start_date, end=end_date, interval="1h")
        
        if data.empty:
            print(f"  No data retrieved for {symbol}")
            return pd.DataFrame()
        
        # Clean and format
        data.reset_index(inplace=True)
        data = data.rename(columns={
            'Datetime': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        data = data[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        print(f"  Retrieved {len(data)} hourly candles")
        print(f"  Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
        
        return data
        
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

def test_free_sources():
    """Test all free data sources"""
    print("TESTING FREE DATA SOURCES")
    print("=" * 50)
    
    # Test APIs
    binance_works = test_binance_public_api()
    yahoo_works = test_yahoo_finance_api()
    
    print(f"\nResults:")
    print(f"  Binance API: {'✅ Working' if binance_works else '❌ Failed'}")
    print(f"  Yahoo Finance: {'✅ Working' if yahoo_works else '❌ Failed'}")
    
    if not binance_works and not yahoo_works:
        print("\n❌ No free APIs working for historical data")
        return False
    
    return True

def sample_historical_acquisition():
    """Try to acquire sample historical data"""
    print("\n" + "="*50)
    print("SAMPLE HISTORICAL DATA ACQUISITION")
    print("="*50)
    
    # Test periods
    test_periods = {
        'covid_sample': (datetime(2020, 3, 15), datetime(2020, 4, 15)),
        'bull_sample': (datetime(2021, 11, 15), datetime(2021, 12, 15))
    }
    
    symbols = ['BTC/USDT', 'ETH/USDT']
    
    for period_name, (start_date, end_date) in test_periods.items():
        print(f"\nTesting {period_name}:")
        
        for symbol in symbols:
            print(f"  {symbol}:")
            
            # Try Binance first
            try:
                df = fetch_binance_historical(symbol, '4h', start_date, end_date)
                
                if not df.empty:
                    # Calculate indicators
                    df_indicators = calculate_indicators(df)
                    
                    print(f"    ✅ {len(df)} candles from Binance")
                    
                    # Save sample
                    filename = f"{symbol.replace('/', '_')}_4h_{period_name}_binance.csv"
                    filepath = f"/home/dribble0335/dev/tradingbot/research/historical/{filename}"
                    df_indicators.to_csv(filepath, index=False)
                    print(f"    💾 Saved to {filepath}")
                else:
                    print(f"    ❌ No data from Binance")
                    
            except Exception as e:
                print(f"    ❌ Binance error: {e}")
            
            time.sleep(0.5)

def main():
    """Main function"""
    print("FREE DATA SOURCES TESTING")
    print("=" * 60)
    
    # Create directories
    os.makedirs("/home/dribble0335/dev/tradingbot/research/historical", exist_ok=True)
    os.makedirs("/home/dribble0335/dev/tradingbot/research/regime", exist_ok=True)
    
    # Test free sources
    if test_free_sources():
        # Try sample acquisition
        sample_historical_acquisition()
    
    print(f"\n{'='*60}")
    print("FREE DATA SOURCES TESTING COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
