import pandas as pd
import ccxt
from strategy import compute_4h_indicators, drop_incomplete_last_candle

# Initialize exchange
ex = ccxt.phemex()
ex.set_sandbox_mode(True)

# Fetch recent data for BTC
symbol = 'BTC/USDT'
timeframe = '4h'
limit = 500

try:
    # Get OHLCV data
    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
    df = drop_incomplete_last_candle(df, timeframe)
    
    # Calculate indicators
    df_ind = compute_4h_indicators(df)
    
    # Analyze RSI below 35
    rsi_below_35 = df_ind[df_ind['rsi'] < 35]
    total_periods = len(df_ind)
    below_35_count = len(rsi_below_35)
    
    if total_periods == 0:
        print(f'No data available for {symbol}')
        exit()
    
    percentage = (below_35_count / total_periods) * 100
    
    print(f'Analysis of {symbol} RSI < 35 (Last {total_periods} 4H periods):')
    print(f'Total periods analyzed: {total_periods}')
    print(f'RSI < 35 occurrences: {below_35_count}')
    print(f'Percentage of time: {percentage:.2f}%')
    if below_35_count > 0:
        print(f'Average time between occurrences: {total_periods/below_35_count:.1f} periods ({total_periods/below_35_count*4:.1f} hours)')
        
        print(f'\nMost recent RSI < 35:')
        print(rsi_below_35[['timestamp', 'rsi', 'close']].tail(3))
    else:
        print('No RSI < 35 occurrences in the analyzed period')
        
except Exception as e:
    print(f'Error: {e}')