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
    return d.dropna().reset_index(drop=True)

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

def entry_signal(sig: pd.Series, prev_sig: pd.Series) -> bool:
    return (
        sig["close"] > sig["sma200_4h"]
        and sig["adx"] > 25
        and (
            (sig["rsi"] < 40)
            or (sig["MACDh_12_26_9"] > 0 and prev_sig["MACDh_12_26_9"] <= 0)
        )
    )

def exit_signal(sig: pd.Series) -> bool:
    return (
        (sig["close"] < sig["sma200_4h"])
        or (sig["rsi"] > 70)
        or (sig["MACDh_12_26_9"] < 0)
    )
