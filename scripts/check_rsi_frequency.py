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
        # Get indices where RSI < 35 for proper interval calculation
        rsi_below_35 = df_ind[df_ind['rsi'] < 35]
        occurrence_indices = rsi_below_35.index.tolist()
        
        # Calculate intervals between consecutive occurrences
        if len(occurrence_indices) > 1:
            intervals = [occurrence_indices[i+1] - occurrence_indices[i] 
                        for i in range(len(occurrence_indices)-1)]
            avg_interval = sum(intervals) / len(intervals)
        else:
            avg_interval = total_periods  # Only one occurrence
        
        print(f'Average time between occurrences: {avg_interval:.1f} periods ({avg_interval*4:.1f} hours)')
        
        print(f'\nMost recent RSI < 35:')
        print(rsi_below_35[['timestamp', 'rsi', 'close']].tail(3))
    else:
        print('No RSI < 35 occurrences in the analyzed period')
        
except Exception as e:
    print(f'Error: {e}')