"""
Offline training script for the LightGBM signal quality filter.

Trains a binary classifier to predict whether a signal that fires will result
in a profitable trade within max_holding_periods candles. Uses purged
GroupKFold cross-validation (group=calendar month) with a 12-bar embargo to
avoid data leakage, replicating the same methodology as backtest_engine.py.

Usage:
    python3 research/train_signal_filter.py \\
        --csv4h  data/ETH_4h.csv  data/SOL_4h.csv \\
        --csv1d  data/ETH_1d.csv  data/SOL_1d.csv \\
        --strategy obv_breakout \\
        --output  models/ \\
        [--n-splits 5] [--embargo-bars 12] [--threshold 0.55]

Outputs:
    models/signal_filter_{strategy}.pkl  — trained model (pickle)
    models/signal_filter_{strategy}_cv.json — cross-validation summary

Requirements:
    pip install lightgbm scikit-learn
"""

import os
import sys
import json
import pickle
import argparse
import warnings
from typing import List, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(os.path.dirname(_HERE), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from strategy import (
    compute_4h_indicators,
    compute_daily_regime,
    attach_regime_to_4h,
    entry_signal,
)
from signal_filter import FEATURE_COLUMNS
from backtest_engine import load_ohlcv_csv


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _extract_features(sig: pd.Series) -> List[float]:
    features = []
    for col in FEATURE_COLUMNS:
        val = sig.get(col, np.nan)
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = np.nan
        features.append(val)
    return features


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------

def build_dataset(
    df4h_raw: pd.DataFrame,
    df1d_raw: pd.DataFrame,
    strategy: str,
    params: dict,
    take_profit_pct: float,
    max_holding: int,
    regime_ma_len: int = 200,
    regime_slope_len: int = 5,
    regime_confirm_days: int = 2,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Builds (X, y, groups) arrays for ML training.

    X      : feature matrix, shape (n_signals, n_features)
    y      : binary label — 1 if trade reached TP within max_holding bars
    groups : calendar-month group index for GroupKFold
    """
    df4h = compute_4h_indicators(df4h_raw.copy())
    df_reg = compute_daily_regime(
        df1d_raw.copy(),
        regime_ma_len=regime_ma_len,
        regime_slope_len=regime_slope_len,
        confirm_days=regime_confirm_days,
    )
    df = attach_regime_to_4h(df4h, df_reg).dropna().reset_index(drop=True)

    X_rows, y_rows, groups = [], [], []

    for i in range(1, len(df)):
        sig      = df.iloc[i]
        prev_sig = df.iloc[i - 1]
        risk_on  = bool(sig.get("risk_on", False))
        ignore_r = bool(params.get("ignore_regime_filter", False))

        if not (risk_on or ignore_r):
            continue
        if not entry_signal(sig, prev_sig, strategy=strategy, params=params):
            continue

        # Label: did price reach TP within max_holding bars?
        entry_px = float(sig["close"])
        target   = entry_px * (1 + take_profit_pct)
        hit_tp   = False
        for j in range(i + 1, min(i + max_holding + 1, len(df))):
            if float(df.iloc[j]["close"]) >= target:
                hit_tp = True
                break

        X_rows.append(_extract_features(sig))
        y_rows.append(1 if hit_tp else 0)
        # Group by calendar month
        ts = sig["timestamp"]
        groups.append(ts.year * 100 + ts.month)

    if not X_rows:
        return np.empty((0, len(FEATURE_COLUMNS))), np.empty(0), np.empty(0)

    return np.array(X_rows), np.array(y_rows), np.array(groups)


# ---------------------------------------------------------------------------
# Training with purged GroupKFold
# ---------------------------------------------------------------------------

def train_and_evaluate(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    n_splits: int = 5,
    embargo_bars: int = 12,
) -> Tuple[object, dict]:
    """
    Train LightGBM with purged GroupKFold CV.
    Returns (final_model_trained_on_full_data, cv_metrics_dict).
    """
    try:
        import lightgbm as lgb
        from sklearn.model_selection import GroupKFold
        from sklearn.metrics import roc_auc_score, precision_score, recall_score
    except ImportError:
        print("ERROR: lightgbm and scikit-learn are required.")
        print("  pip install lightgbm scikit-learn")
        sys.exit(1)

    unique_groups = np.unique(groups)
    n_groups = len(unique_groups)
    # Use np.array_split to ensure all groups are covered, including remainder
    group_splits = np.array_split(unique_groups, n_splits)
    
    cv_aucs, cv_precs, cv_recs = [], [], []

    for k, test_groups in enumerate(group_splits):
        test_mask    = np.isin(groups, test_groups)
        # Embargo: exclude samples whose group is within embargo_bars of test boundary
        test_min_grp = test_groups.min() if len(test_groups) else 0
        test_max_grp = test_groups.max() if len(test_groups) else 0
        # Convert group (yyyymm) to ordinal month for embargo check
        def grp_to_ord(g):
            y, m = divmod(g, 100)
            return y * 12 + m
        test_ord_range = range(grp_to_ord(test_min_grp), grp_to_ord(test_max_grp) + 1)
        embargo_mask = np.array([
            any(abs(grp_to_ord(g) - t) <= embargo_bars for t in test_ord_range)
            for g in groups
        ])
        train_mask = ~test_mask & ~embargo_mask

        if train_mask.sum() < 20 or test_mask.sum() < 5:
            continue

        X_train, y_train = X[train_mask], y[train_mask]
        X_test,  y_test  = X[test_mask],  y[test_mask]

        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            num_leaves=15,
            min_child_samples=10,
            subsample=0.8,
            colsample_bytree=0.8,
            class_weight="balanced",
            random_state=42,
            verbose=-1,
        )
        model.fit(X_train, y_train,
                  eval_set=[(X_test, y_test)],
                  callbacks=[lgb.early_stopping(20, verbose=False),
                             lgb.log_evaluation(-1)])

        prob = model.predict_proba(X_test)[:, 1]
        pred = (prob >= 0.5).astype(int)
        auc_str = "N/A"
        if len(np.unique(y_test)) > 1:
            auc_val = roc_auc_score(y_test, prob)
            cv_aucs.append(auc_val)
            auc_str = f"{auc_val:.3f}"
        cv_precs.append(precision_score(y_test, pred, zero_division=0))
        cv_recs.append(recall_score(y_test,  pred, zero_division=0))
        print(f"  Fold {k+1}: AUC={auc_str}  Prec={cv_precs[-1]:.3f}  Rec={cv_recs[-1]:.3f}  (n_train={train_mask.sum()}, n_test={test_mask.sum()})")

    cv_metrics = {
        "n_signals": int(len(y)),
        "positive_rate": float(y.mean()),
        "cv_auc_mean":  float(np.mean(cv_aucs))  if cv_aucs  else None,
        "cv_auc_std":   float(np.std(cv_aucs))   if cv_aucs  else None,
        "cv_prec_mean": float(np.mean(cv_precs)) if cv_precs else None,
        "cv_rec_mean":  float(np.mean(cv_recs))  if cv_recs  else None,
    }

    # Final model — train on all data
    final_model = lgb.LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=4,
        num_leaves=15,
        min_child_samples=10,
        subsample=0.8,
        colsample_bytree=0.8,
        class_weight="balanced",
        random_state=42,
        verbose=-1,
    )
    final_model.fit(X, y)

    return final_model, cv_metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train LightGBM signal filter")
    parser.add_argument("--csv4h",    nargs="+", required=True, help="Path(s) to 4h OHLCV CSV(s)")
    parser.add_argument("--csv1d",    nargs="+", required=True, help="Path(s) to 1d OHLCV CSV(s) (same order as csv4h)")
    parser.add_argument("--strategy", default="obv_breakout",
                        choices=["obv_breakout", "vwap_band_bounce", "rsi_momentum_pullback"])
    parser.add_argument("--output",   default="models", help="Output directory for model files")
    parser.add_argument("--n-splits",     type=int,   default=5)
    parser.add_argument("--embargo-bars", type=int,   default=12)
    parser.add_argument("--threshold",    type=float, default=0.55)
    args = parser.parse_args()

    if len(args.csv4h) != len(args.csv1d):
        print("ERROR: --csv4h and --csv1d must have the same number of paths")
        sys.exit(1)

    strategy_params = {
        "obv_breakout": {
            "ignore_regime_filter": False, "volume_ratio_threshold": 1.3,
            "take_profit_pct": 0.10, "max_holding_periods": 30,
        },
        "vwap_band_bounce": {
            "ignore_regime_filter": False, "rsi_threshold": 40, "mfi_threshold": 35,
            "take_profit_pct": 0.06, "max_holding_periods": 12,
        },
        "rsi_momentum_pullback": {
            "ignore_regime_filter": True, "adx_threshold": 20,
            "rsi_lower": 25, "rsi_upper": 45, "rsi_exit": 68,
            "take_profit_pct": 0.08, "max_holding_periods": 20,
        },
    }
    params = strategy_params[args.strategy]

    print(f"\nBuilding dataset for strategy: {args.strategy}")
    all_X, all_y, all_groups = [], [], []

    for csv4h_path, csv1d_path in zip(args.csv4h, args.csv1d):
        print(f"  Loading {csv4h_path} + {csv1d_path}...")
        df4h = load_ohlcv_csv(csv4h_path)
        df1d = load_ohlcv_csv(csv1d_path)
        X, y, groups = build_dataset(
            df4h, df1d,
            strategy=args.strategy,
            params=params,
            take_profit_pct=float(params["take_profit_pct"]),
            max_holding=int(params["max_holding_periods"]),
        )
        print(f"    {len(y)} signals found ({y.sum()} positive, {(~y.astype(bool)).sum()} negative)")
        if len(y) > 0:
            all_X.append(X)
            all_y.append(y)
            all_groups.append(groups)

    if not all_X:
        print("ERROR: No signals found in any dataset. Check data quality.")
        sys.exit(1)

    X_all     = np.vstack(all_X)
    y_all     = np.concatenate(all_y)
    grp_all   = np.concatenate(all_groups)

    print(f"\nTotal signals: {len(y_all)}  (positive rate: {y_all.mean():.1%})")
    print(f"Features: {FEATURE_COLUMNS}")
    print(f"\nRunning purged CV ({args.n_splits} folds, {args.embargo_bars}-bar embargo)...")

    model, cv_metrics = train_and_evaluate(
        X_all, y_all, grp_all,
        n_splits=args.n_splits,
        embargo_bars=args.embargo_bars,
    )

    os.makedirs(args.output, exist_ok=True)
    model_path = os.path.join(args.output, f"signal_filter_{args.strategy}.pkl")
    cv_path    = os.path.join(args.output, f"signal_filter_{args.strategy}_cv.json")

    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    with open(cv_path, "w") as f:
        json.dump(cv_metrics, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Model saved:   {model_path}")
    print(f"CV results:    {cv_path}")
    auc_mean = cv_metrics.get('cv_auc_mean')
    auc_std  = cv_metrics.get('cv_auc_std', 0)
    print(f"CV AUC:        {auc_mean:.3f} ± {auc_std:.3f}" if auc_mean is not None else "CV AUC:        N/A (insufficient data for CV)")
    prec_mean = cv_metrics.get('cv_prec_mean')
    print(f"CV Precision:  {prec_mean:.3f}" if prec_mean is not None else "CV Precision:  N/A")
    print(f"Positive rate: {cv_metrics.get('positive_rate', 0):.1%}")
    print(f"\nTo enable at runtime, add to config.json per profile:")
    print(f'  "signal_filter": {{"enabled": true, "threshold": {args.threshold}, "model_dir": "{args.output}"}}')
