import pandas as pd
import pandas_ta as ta
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

def sma_rsi_combo_signal(sig: pd.Series, prev_sig: pd.Series) -> bool:
    """Bear market optimized strategy: sma_rsi_combo"""
    return (
        sig["close"] < sig["sma200_4h"]  # Short entry (below SMA)
        and sig["adx"] > 25
        and sig["rsi"] > 70  # Overbought for short
        and not sig.get("risk_on", True)  # Risk-off condition
    )

def sma_rsi_impulse_signal(sig: pd.Series, prev_sig: pd.Series) -> bool:
    """Bull/Transition market optimized strategy: sma_rsi_impulse"""
    return (
        sig["close"] < sig["sma200_4h"]  # Short entry (below SMA)
        and sig["adx"] > 25
        and sig["rsi"] > 70  # Overbought for short
        and sig.get("impulse_macd", 0) == 1  # ImpulseMACD confirmation
        and not sig.get("risk_on", True)  # Risk-off condition
    )

def adaptive_short_entry_signal(sig: pd.Series, prev_sig: pd.Series, market_type: str = "bear") -> bool:
    """Adaptive strategy selector based on market type"""
    if market_type == "bull":
        return sma_rsi_impulse_signal(sig, prev_sig)
    elif market_type == "bear":
        return sma_rsi_combo_signal(sig, prev_sig)
    else:  # transition or unknown
        return sma_rsi_impulse_signal(sig, prev_sig)  # Better in transitions

def entry_signal(sig: pd.Series, prev_sig: pd.Series, adaptive: bool = False, market_type: str = "bear") -> bool:
    """Entry signal with optional adaptive strategy"""
    if adaptive:
        return adaptive_short_entry_signal(sig, prev_sig, market_type)
    else:
        # Original long strategy (backward compatibility)
        return (
            sig["close"] > sig["sma200_4h"]
            and sig["adx"] > 25
            and (
                (sig["rsi"] < 40)
                or (sig["MACDh_12_26_9"] > 0 and prev_sig["MACDh_12_26_9"] <= 0)
            )
        )

def short_entry_signal(sig: pd.Series, prev_sig: pd.Series, adaptive: bool = False, market_type: str = "bear") -> bool:
    """Short entry signal with optional adaptive strategy"""
    if adaptive:
        return adaptive_short_entry_signal(sig, prev_sig, market_type)
    else:
        # Default to bear market optimized strategy (sma_rsi_combo)
        return sma_rsi_combo_signal(sig, prev_sig)

def exit_signal(sig: pd.Series) -> bool:
    return (
        (sig["close"] < sig["sma200_4h"])
        or (sig["rsi"] > 70)
        or (sig["MACDh_12_26_9"] < 0)
    )
