"""
HMM regime model inference for live trading.

Loads models/regime_hmm.pkl and predicts the current market regime
(bull / sideways / bear) from daily OHLCV data.

The model was trained by research/train_regime_hmm.py using 6 features:
  daily_ret, ret_5d, vol_zscore, atr_ratio, sma200_slope, sma200_dist
"""

import json
import logging
import os
import pickle
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_HMM_MODEL  = None
_HMM_SCALER = None
_HMM_STATES: Optional[dict] = None  # {state_int_str: label_str}


# ---------------------------------------------------------------------------
# Feature computation — must match research/train_regime_hmm.py exactly
# ---------------------------------------------------------------------------

def _compute_features(df: pd.DataFrame) -> np.ndarray:
    close  = df["close"].values
    volume = df["volume"].values
    high   = df["high"].values
    low    = df["low"].values

    daily_ret = np.diff(np.log(close), prepend=np.log(close[0]))
    ret_5d    = pd.Series(close).pct_change(5).fillna(0).values

    log_vol    = np.log1p(volume)
    vol_s      = pd.Series(log_vol)
    vol_mean   = vol_s.rolling(20, min_periods=5).mean().bfill().values
    vol_std    = vol_s.rolling(20, min_periods=5).std().bfill().fillna(1.0).replace(0, 1.0).values
    vol_zscore = (log_vol - vol_mean) / vol_std

    tr = np.maximum(high - low,
         np.maximum(np.abs(high - np.roll(close, 1)),
                    np.abs(low  - np.roll(close, 1))))
    tr[0] = high[0] - low[0]
    atr       = pd.Series(tr).rolling(14, min_periods=5).mean().bfill().values
    atr_ratio = atr / np.where(close > 0, close, 1.0)

    sma200       = pd.Series(close).rolling(200, min_periods=50).mean().bfill().values
    sma200_safe  = np.where(sma200 > 0, sma200, 1.0)
    sma200_slope = (sma200 - np.roll(sma200, 5)) / (sma200_safe * 5)
    sma200_slope[:5] = 0.0
    sma200_dist  = (close - sma200) / sma200_safe

    return np.column_stack([daily_ret, ret_5d, vol_zscore, atr_ratio,
                            sma200_slope, sma200_dist])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_hmm(model_dir: str = "models") -> bool:
    """Load HMM model and scaler from disk.  Returns True on success."""
    global _HMM_MODEL, _HMM_SCALER, _HMM_STATES

    pkl_path  = os.path.join(model_dir, "regime_hmm.pkl")
    json_path = os.path.join(model_dir, "regime_hmm_states.json")

    if not os.path.exists(pkl_path):
        logger.warning(f"HMM model not found at {pkl_path} — HMM regime routing disabled")
        return False
    if not os.path.exists(json_path):
        logger.warning(f"HMM states config not found at {json_path} — HMM regime routing disabled")
        return False

    try:
        with open(pkl_path, "rb") as f:
            bundle = pickle.load(f)
        if isinstance(bundle, dict) and "model" in bundle:
            _HMM_MODEL  = bundle["model"]
            _HMM_SCALER = bundle.get("scaler", None)
        else:
            _HMM_MODEL  = bundle
            _HMM_SCALER = None

        with open(json_path, "r") as f:
            states_cfg = json.load(f)
        # Support both {"states": {...}} and flat {"0": "bull", ...} formats
        raw = states_cfg.get("state_labels", states_cfg.get("states", states_cfg))
        _HMM_STATES = {str(k): v for k, v in raw.items()
                       if k not in ("feature_names", "prob_threshold",
                                    "hold_bars", "smooth_span",
                                    "training_symbol", "n_bars")}

        scaler_str = "with scaler" if _HMM_SCALER is not None else "no scaler"
        logger.info(f"HMM model loaded ({scaler_str}), states={_HMM_STATES}")
        return True
    except Exception as e:
        logger.error(f"Failed to load HMM model: {e}")
        _HMM_MODEL = _HMM_SCALER = _HMM_STATES = None
        return False


def predict_regime(df_1d: pd.DataFrame) -> Optional[str]:
    """Predict current regime label ('bull'/'sideways'/'bear') from daily OHLCV.

    Returns None if the model is not loaded or data is insufficient.
    """
    if _HMM_MODEL is None or _HMM_STATES is None:
        return None
    if len(df_1d) < 220:
        return None
    try:
        X = _compute_features(df_1d)
        if _HMM_SCALER is not None:
            X = _HMM_SCALER.transform(X)
        state_int = int(_HMM_MODEL.predict(X)[-1])
        return _HMM_STATES.get(str(state_int), None)
    except Exception as e:
        logger.warning(f"HMM prediction error: {e}")
        return None


def is_loaded() -> bool:
    return _HMM_MODEL is not None
