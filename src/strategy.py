import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timezone

def timeframe_seconds(tf: str) -> int:
    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    if tf.endswith("h"):
        return int(tf[:-1]) * 3600
    if tf.endswith("d"):
        return int(tf[:-1]) * 86400
    raise ValueError(f"Unsupported timeframe: {tf}")

def drop_incomplete_last_candle(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    if df.empty:
        return df
    tf_sec = timeframe_seconds(tf)
    last_open = int(df.iloc[-1]["timestamp"].timestamp())
    now_sec = int(datetime.now(timezone.utc).timestamp())
    if now_sec < last_open + tf_sec:
        return df.iloc[:-1].copy()
    return df

def compute_4h_indicators(df4h: pd.DataFrame) -> pd.DataFrame:
    d = df4h.copy()
    d["sma200_4h"] = ta.sma(d["close"], length=200)
    d["rsi"] = ta.rsi(d["close"], length=14)
    macd = ta.macd(d["close"])
    d = pd.concat([d, macd], axis=1)
    d["adx"] = ta.adx(d["high"], d["low"], d["close"], length=14)["ADX_14"]
    
    # Add ImpulseMACD for adaptive strategy
    d["impulse_macd"] = calculate_impulse_macd(d["close"])
    
    # Add Volume Reversal indicators
    d["volume_sma"] = ta.sma(d["volume"], length=20)
    # Guard against division by zero for volume_ratio
    d["volume_ratio"] = np.where(d["volume_sma"] != 0, d["volume"] / d["volume_sma"], 0)
    d["price_change"] = d["close"].pct_change()
    d["volatility"] = d["price_change"].rolling(window=20).std()
    
    # Enhanced Volume Indicators
    d["volume_ema"] = ta.ema(d["volume"], length=20)
    # Guard against division by zero for volume_rvol
    volume_mean = d["volume"].rolling(window=20).mean()
    d["volume_rvol"] = np.where(volume_mean != 0, d["volume"] / volume_mean, 0)  # Relative Volume
    # Guard against division by zero for volume_ema_ratio
    d["volume_ema_ratio"] = np.where(d["volume_ema"] != 0, d["volume"] / d["volume_ema"], 0)
    
    # Stochastic RSI
    stochrsi = ta.stochrsi(d["close"], length=14)
    d["stochrsi_k"] = stochrsi["STOCHRSIk_14_14_3_3"]

    # ATR (Average True Range) — used for volatility-aware stop sizing
    d["atr"] = ta.atr(d["high"], d["low"], d["close"], length=14)

    # Supertrend — dynamic support/resistance trend line
    st = ta.supertrend(d["high"], d["low"], d["close"], length=10, multiplier=3.0)
    d["supertrend"] = st["SUPERT_10_3.0"]
    d["supertrend_dir"] = st["SUPERTd_10_3.0"]  # 1 = bullish, -1 = bearish

    # On-Balance Volume (OBV)
    d["obv"] = ta.obv(d["close"], d["volume"])
    d["obv_sma"] = ta.sma(d["obv"], length=20)
    d["obv_divergence"] = calculate_obv_divergence(d["close"], d["obv"])
    
    # Money Flow Index (MFI)
    d["mfi"] = ta.mfi(d["high"], d["low"], d["close"], d["volume"], length=14)
    d["mfi_divergence"] = calculate_mfi_divergence(d["close"], d["mfi"])
    
    # Accumulation/Distribution Line
    d["ad_line"] = ta.ad(d["high"], d["low"], d["close"], d["volume"])
    d["ad_sma"] = ta.sma(d["ad_line"], length=20)
    d["ad_divergence"] = calculate_ad_divergence(d["close"], d["ad_line"])
    
    # Chaikin Money Flow (CMF)
    d["cmf"] = ta.cmf(d["high"], d["low"], d["close"], d["volume"], length=20)
    d["cmf_divergence"] = calculate_cmf_divergence(d["close"], d["cmf"])
    
    # VWAP (Volume Weighted Average Price)
    d["vwap"], d["vwap_upper"], d["vwap_lower"] = calculate_vwap(d)
    d["vwap_support_resistance"] = calculate_vwap_sr(d["close"], d["vwap"], d["vwap_upper"], d["vwap_lower"])
    
    return d.dropna().reset_index(drop=True)

def calculate_impulse_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """Calculate ImpulseMACD signal for adaptive strategy"""
    # Standard MACD
    exp1 = close.ewm(span=fast).mean()
    exp2 = close.ewm(span=slow).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line
    
    # Impulse component - rate of change of histogram
    impulse = histogram.diff()
    
    # Impulse signal (positive momentum)
    impulse_signal = (impulse > 0) & (histogram > 0)
    
    return impulse_signal.astype(int)

def calculate_obv_divergence(close: pd.Series, obv: pd.Series, lookback: int = 20) -> pd.Series:
    """Calculate OBV divergence (bullish when price makes lower lows but OBV makes higher lows)"""
    divergence = pd.Series(0, index=close.index)
    
    for i in range(lookback, len(close)):
        price_window = close.iloc[i-lookback:i+1]
        obv_window = obv.iloc[i-lookback:i+1]
        
        # Find the two most recent local lows in price and OBV
        # Get local minima indices (simplified approach)
        price_local_mins = []
        obv_local_mins = []
        
        # Find local minima (simple approach: points lower than neighbors)
        for j in range(1, len(price_window) - 1):
            if (price_window.iloc[j] < price_window.iloc[j-1] and 
                price_window.iloc[j] < price_window.iloc[j+1]):
                price_local_mins.append((j, price_window.iloc[j]))
            if (obv_window.iloc[j] < obv_window.iloc[j-1] and 
                obv_window.iloc[j] < obv_window.iloc[j+1]):
                obv_local_mins.append((j, obv_window.iloc[j]))
        
        # If we have at least 2 local minima for both, compare the most recent two
        if len(price_local_mins) >= 2 and len(obv_local_mins) >= 2:
            # Get the two most recent local lows
            price_local_mins.sort(key=lambda x: x[0], reverse=True)
            obv_local_mins.sort(key=lambda x: x[0], reverse=True)
            
            # Most recent lows
            price_current_low = price_local_mins[0][1]
            price_prev_low = price_local_mins[1][1]
            obv_current_low = obv_local_mins[0][1]
            obv_prev_low = obv_local_mins[1][1]
            
            # Check for bullish divergence: lower price low but higher OBV low
            if (price_current_low < price_prev_low and obv_current_low > obv_prev_low):
                divergence.iloc[i] = 1
    
    return divergence

def calculate_mfi_divergence(close: pd.Series, mfi: pd.Series, lookback: int = 14) -> pd.Series:
    """Calculate MFI divergence (bullish when price makes lower lows but MFI makes higher lows)"""
    divergence = pd.Series(0, index=close.index)
    
    for i in range(lookback, len(close)):
        price_window = close.iloc[i-lookback:i+1]
        mfi_window = mfi.iloc[i-lookback:i+1]
        
        # Find recent lows
        price_low_idx = price_window.idxmin()
        mfi_low_idx = mfi_window.idxmin()
        
        # Check for bullish divergence
        if (price_low_idx != mfi_low_idx and 
            price_window.loc[price_low_idx] < price_window.iloc[-2] and
            mfi_window.loc[mfi_low_idx] > mfi_window.iloc[-2] and
            mfi_window.iloc[-1] < 50):  # MFI oversold
            divergence.iloc[i] = 1
    
    return divergence

def calculate_ad_divergence(close: pd.Series, ad_line: pd.Series, lookback: int = 20) -> pd.Series:
    """Calculate Accumulation/Distribution divergence"""
    divergence = pd.Series(0, index=close.index)
    
    for i in range(lookback, len(close)):
        price_window = close.iloc[i-lookback:i+1]
        ad_window = ad_line.iloc[i-lookback:i+1]
        
        # Find recent lows
        price_low_idx = price_window.idxmin()
        ad_low_idx = ad_window.idxmin()
        
        # Check for bullish divergence
        if (price_low_idx != ad_low_idx and 
            price_window.loc[price_low_idx] < price_window.iloc[-2] and
            ad_window.loc[ad_low_idx] > ad_window.iloc[-2]):
            divergence.iloc[i] = 1
    
    return divergence

def calculate_cmf_divergence(close: pd.Series, cmf: pd.Series, lookback: int = 20) -> pd.Series:
    """Calculate Chaikin Money Flow divergence"""
    divergence = pd.Series(0, index=close.index)
    
    for i in range(lookback, len(close)):
        price_window = close.iloc[i-lookback:i+1]
        cmf_window = cmf.iloc[i-lookback:i+1]
        
        # Find recent lows
        price_low_idx = price_window.idxmin()
        cmf_low_idx = cmf_window.idxmin()
        
        # Check for bullish divergence
        if (price_low_idx != cmf_low_idx and 
            price_window.loc[price_low_idx] < price_window.iloc[-2] and
            cmf_window.loc[cmf_low_idx] > cmf_window.iloc[-2] and
            cmf_window.iloc[-1] < -0.1):  # CMF oversold
            divergence.iloc[i] = 1
    
    return divergence

def calculate_vwap(df: pd.DataFrame, length: int = 20) -> tuple:
    """Calculate VWAP with standard deviation bands"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = typical_price * df['volume']
    vwap_cumsum = vwap.rolling(window=length).sum()
    volume_cumsum = df['volume'].rolling(window=length).sum()
    vwap_avg = vwap_cumsum / volume_cumsum
    
    # VWAP standard deviation bands
    variance = ((typical_price - vwap_avg) ** 2 * df['volume']).rolling(window=length).sum()
    std_dev = np.sqrt(variance / volume_cumsum)
    
    vwap_upper = vwap_avg + (std_dev * 2)
    vwap_lower = vwap_avg - (std_dev * 2)
    
    return vwap_avg, vwap_upper, vwap_lower

def calculate_vwap_sr(close: pd.Series, vwap: pd.Series, vwap_upper: pd.Series, vwap_lower: pd.Series) -> pd.Series:
    """Calculate VWAP support/resistance signals"""
    sr_signal = pd.Series(0, index=close.index)
    
    # Support: price near VWAP lower band
    support_condition = (close - vwap_lower).abs() < (close * 0.01)  # Within 1% of lower band
    
    # Resistance: price near VWAP upper band  
    resistance_condition = (close - vwap_upper).abs() < (close * 0.01)  # Within 1% of upper band
    
    # Neutral: price near VWAP
    neutral_condition = (close - vwap).abs() < (close * 0.005)  # Within 0.5% of VWAP
    
    sr_signal[support_condition] = 1  # Support
    sr_signal[resistance_condition] = -1  # Resistance
    sr_signal[neutral_condition] = 0  # Neutral
    
    return sr_signal

def compute_daily_regime(df1d: pd.DataFrame, regime_ma_len: int, regime_slope_len: int, confirm_days: int) -> pd.DataFrame:
    d = df1d.copy()
    d["ema200"] = ta.ema(d["close"], length=regime_ma_len)
    d["ema_slope_ok"] = d["ema200"] > d["ema200"].shift(regime_slope_len)

    above = d["close"] > d["ema200"]
    above_nd = above.copy()
    for k in range(1, confirm_days):
        above_nd = above_nd & above.shift(k)

    d["risk_on_raw"] = above_nd & d["ema_slope_ok"]
    d["risk_on"] = d["risk_on_raw"].shift(1)  # avoid lookahead
    d = d.dropna(subset=["risk_on"]).reset_index(drop=True)
    return d[["timestamp", "risk_on"]]

def attach_regime_to_4h(df4h_ind: pd.DataFrame, df_regime: pd.DataFrame) -> pd.DataFrame:
    a = df4h_ind.sort_values("timestamp").copy()
    b = df_regime.sort_values("timestamp").copy()
    out = pd.merge_asof(a, b, on="timestamp", direction="backward")
    out["risk_on"] = out["risk_on"].fillna(False)
    return out

def classify_market_type(df: pd.DataFrame, lookback_days: int = 5) -> str:
    """Classify market type based on price trend and regime"""
    if len(df) < lookback_days:
        return "unknown"
    
    # Calculate price trend over lookback period
    price_change = (df["close"].iloc[-1] - df["close"].iloc[-lookback_days]) / df["close"].iloc[-lookback_days]
    
    # Get current regime
    current_regime = df["risk_on"].iloc[-1] if "risk_on" in df.columns else False
    
    # Market classification logic
    if current_regime and price_change > 0.02:  # Bull regime + positive trend
        return "bull"
    elif not current_regime and price_change < -0.02:  # Bear regime + negative trend
        return "bear"
    else:
        return "transition"

def rsi_momentum_pullback_signal(sig: pd.Series, prev_sig: pd.Series) -> bool:
    """
    Buy-the-dip in an established uptrend.
    Mandatory: price above SMA200 (uptrend only) AND ADX > 20 AND RSI 25-45.
    Momentum confirmation: 2-of-3 must fire:
      1. MACD histogram turning up
      2. ImpulseMACD == 1 (histogram positive AND accelerating)
      3. StochRSI K < 0.3 (oversold stochastic)
    """
    above_sma200  = sig["close"] > sig["sma200_4h"]
    trend_exists  = sig["adx"] > 20
    rsi_val       = sig["rsi"]
    pulled_back   = 25 < rsi_val < 45

    macd_turning_up   = sig["MACDh_12_26_9"] > prev_sig["MACDh_12_26_9"]
    impulse_firing    = sig["impulse_macd"] == 1
    stochrsi_oversold = sig["stochrsi_k"] < 30

    momentum_score = sum([macd_turning_up, impulse_firing, stochrsi_oversold])
    return above_sma200 and trend_exists and pulled_back and momentum_score >= 2


def vwap_band_bounce_signal(sig: pd.Series, prev_sig: pd.Series) -> bool:
    """
    Mean reversion when price hits VWAP lower band (-2σ).
    Entry: price below vwap_lower AND RSI < 40 AND MFI < 35.
    Works in ranging/volatile markets where trend-following fails.
    """
    below_band = sig["close"] < sig["vwap_lower"]
    rsi_oversold = sig["rsi"] < 40
    mfi_oversold = sig["mfi"] < 35
    return below_band and rsi_oversold and mfi_oversold


def obv_breakout_signal(sig: pd.Series, prev_sig: pd.Series) -> bool:
    """
    OBV accumulation confirmed breakout.
    Entry: OBV above its SMA (upward volume trend) AND bullish OBV divergence AND
           green candle AND volume confirming (ratio > 1.3).
    Trend-following strategy with highest R:R target.
    Note: Supertrend gate was tested and found to hurt returns on TRX/ETH by blocking
    valid early-trend entries — omitted intentionally.
    """
    obv_trending = sig["obv"] > sig["obv_sma"]
    accumulation = sig["obv_divergence"] == 1
    green_candle = sig["close"] > prev_sig["close"]
    volume_confirming = sig["volume_ratio"] > 1.3
    return obv_trending and accumulation and green_candle and volume_confirming


def entry_signal(sig: pd.Series, prev_sig: pd.Series, strategy: str = "rsi_momentum_pullback") -> bool:
    """Dispatch entry signal by strategy name."""
    if strategy == "rsi_momentum_pullback":
        return rsi_momentum_pullback_signal(sig, prev_sig)
    elif strategy == "vwap_band_bounce":
        return vwap_band_bounce_signal(sig, prev_sig)
    elif strategy == "obv_breakout":
        return obv_breakout_signal(sig, prev_sig)
    return False


def exit_signal(sig: pd.Series, strategy: str = "rsi_momentum_pullback") -> bool:
    """Dispatch exit signal by strategy name."""
    if strategy == "rsi_momentum_pullback":
        return sig["rsi"] > 68
    elif strategy == "vwap_band_bounce":
        return sig["close"] >= sig["vwap"]
    elif strategy == "obv_breakout":
        # Require both OBV trend broken AND MACD histogram negative to avoid whipsaws
        return sig["obv"] < sig["obv_sma"] and sig["MACDh_12_26_9"] < 0
    return False
