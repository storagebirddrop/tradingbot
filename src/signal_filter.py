"""
LightGBM signal quality filter.

This module provides an optional ML-based gate that sits AFTER the rule-based
entry_signal() check in runner.py. A pre-trained LightGBM binary classifier
predicts P(trade is profitable) from existing indicator features. Only signals
scoring above a configurable threshold are allowed to proceed to execution.

IMPORTANT: The model must be trained offline via research/train_signal_filter.py
before this filter can be enabled. Set "signal_filter": {"enabled": false} in
config.json (the default) to bypass this entirely with zero overhead.

Training:
    cd /path/to/tradingbot
    python3 research/train_signal_filter.py \
        --csv4h data/ETH_4h.csv --csv1d data/ETH_1d.csv \
        --strategy obv_breakout --output models/

Enabling at runtime (config.json):
    "signal_filter": {
        "enabled": true,
        "threshold": 0.55,
        "model_dir": "models"
    }
"""

import os
import pickle
from typing import Optional

import numpy as np
import pandas as pd


# Feature columns expected by the model (subset of compute_4h_indicators output)
FEATURE_COLUMNS = [
    "rsi",
    "MACDh_12_26_9",
    "adx",
    "stochrsi_k",
    "volume_ratio",
    "obv_divergence",
    "cmf",
    "supertrend_dir",
    "risk_on",
    "volatility",
]


class SignalFilter:
    """
    Wraps a trained LightGBM (or compatible sklearn-API) binary classifier.

    If the model file is not found, the filter is transparently disabled and
    all signals pass through (no false negatives at the cost of no filtering).
    """

    def __init__(self, cfg: dict):
        self._enabled = bool((cfg.get("signal_filter") or {}).get("enabled", False))
        self._threshold = float((cfg.get("signal_filter") or {}).get("threshold", 0.55))
        model_dir = (cfg.get("signal_filter") or {}).get("model_dir", "models")
        self._models: dict = {}
        if self._enabled:
            self._load_models(model_dir)

    def _load_models(self, model_dir: str) -> None:
        strategies = ["obv_breakout", "vwap_band_bounce", "rsi_momentum_pullback"]
        for strat in strategies:
            path = os.path.join(model_dir, f"signal_filter_{strat}.pkl")
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        self._models[strat] = pickle.load(f)
                    print(f"[signal_filter] Loaded model for {strat} from {path}")
                except Exception as e:
                    print(f"[signal_filter] WARNING: Failed to load model for {strat}: {e}")

    def is_enabled(self) -> bool:
        return self._enabled and bool(self._models)

    def score_signal(self, sig: pd.Series, strategy: str) -> float:
        """
        Returns P(profitable) in [0, 1].
        Returns 1.0 (always pass) if filter is disabled or model unavailable.
        """
        if not self._enabled:
            return 1.0
        model = self._models.get(strategy)
        if model is None:
            return 1.0  # fail-open: no model = no filtering

        features = []
        for col in FEATURE_COLUMNS:
            val = sig.get(col, np.nan)
            try:
                val = float(val)
            except (TypeError, ValueError):
                val = np.nan
            features.append(val)

        X = np.array(features).reshape(1, -1)
        try:
            prob = model.predict_proba(X)[0, 1]
            return float(prob)
        except Exception:
            return 1.0  # fail-open on inference error

    def should_enter(self, sig: pd.Series, strategy: str) -> bool:
        """Returns True if the signal passes the ML quality threshold."""
        return self.score_signal(sig, strategy) >= self._threshold


# Module-level singleton — instantiated once at bot startup
_filter_instance: Optional[SignalFilter] = None


def init_filter(cfg: dict) -> SignalFilter:
    """Call once at startup from run_bot.py to initialise the filter."""
    global _filter_instance
    _filter_instance = SignalFilter(cfg)
    return _filter_instance


def get_filter() -> Optional[SignalFilter]:
    return _filter_instance
