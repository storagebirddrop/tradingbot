"""
Regime-conditioned strategy analysis using HMM state labels.

Runs each strategy isolated per regime state to measure per-regime performance,
then optionally runs regime-switching WFO where strategy selection is driven
by the HMM state at each bar.

Usage:
    # Full-history analysis (no WFO), skip sideways entries
    python3 research/regime_strategy_analysis.py \
        --symbols ETH SOL TRX ADA LTC BAT RUNE VTHO \
        --hmm models/regime_hmm.pkl \
        --hmm-states models/regime_hmm_states.json \
        --no-wfo --skip-sideways

    # With sideways-regime entry filters (Option 2)
    python3 research/regime_strategy_analysis.py \
        --symbols ETH --hmm models/regime_hmm.pkl \
        --hmm-states models/regime_hmm_states.json \
        --no-wfo --sideways-filters

    # Full WFO with regime switching
    python3 research/regime_strategy_analysis.py \
        --symbols ETH SOL --hmm models/regime_hmm.pkl \
        --hmm-states models/regime_hmm_states.json
"""

import os
import sys
import argparse
import json
import pickle
import warnings
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from backtest_engine import BacktestConfig, run_backtest, walk_forward, purged_cv, load_ohlcv_csv, print_results_table

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Default strategy config per regime
# ---------------------------------------------------------------------------

DEFAULT_REGIME_STRATEGY_MAP = {
    "bull":     {"strategy": "rsi_momentum_pullback", "risk_scale": 1.0, "take_profit_pct": 0.08},
    "sideways": {"strategy": "obv_breakout",          "risk_scale": 0.7, "take_profit_pct": 0.10},
    "bear":     {"strategy": "rsi_momentum_pullback", "risk_scale": 0.5, "take_profit_pct": 0.05},
}

# Default params per strategy (ignore_regime so we can test regime-isolated)
DEFAULT_STRATEGY_PARAMS = {
    "obv_breakout":          {"ignore_regime_filter": True, "stop_loss_pct": 0.04, "take_profit_pct": 0.10, "max_holding_periods": 30},
    "vwap_band_bounce":      {"ignore_regime_filter": True, "stop_loss_pct": 0.035,"take_profit_pct": 0.06, "max_holding_periods": 12},
    "rsi_momentum_pullback": {"ignore_regime_filter": True, "stop_loss_pct": 0.04, "take_profit_pct": 0.08, "max_holding_periods": 20},
}

MIN_TRADES = 5


# ---------------------------------------------------------------------------
# HMM helpers
# ---------------------------------------------------------------------------

def load_hmm(pkl_path: str, states_path: str):
    """Load trained HMM model (and optional scaler) + state label config.

    Supports both old format (raw model) and new format (dict with
    'model' and 'scaler' keys, produced after StandardScaler was added).
    Returns (model, scaler_or_None, states_cfg).
    """
    with open(pkl_path, "rb") as f:
        bundle = pickle.load(f)
    if isinstance(bundle, dict) and "model" in bundle:
        model  = bundle["model"]
        scaler = bundle.get("scaler", None)
    else:
        model  = bundle
        scaler = None
    with open(states_path, "r") as f:
        states_cfg = json.load(f)
    return model, scaler, states_cfg


def compute_hmm_regime_df(model, scaler, states_cfg: dict, df_1d: pd.DataFrame) -> pd.DataFrame:
    """
    Apply HMM to daily OHLCV and return DataFrame with columns:
      timestamp, hmm_state_int, hmm_label, hmm_conf
    Using EMA-smoothed posteriors, confidence threshold, and hold buffer.
    """
    from train_regime_hmm import compute_features

    state_labels  = states_cfg["state_labels"]         # {"0": "bull", ...}
    prob_threshold = float(states_cfg.get("prob_threshold", 0.7))
    hold_bars      = int(states_cfg.get("hold_bars", 2))
    smooth_span    = int(states_cfg.get("smooth_span", 3))

    X = compute_features(df_1d)
    if scaler is not None:
        X = scaler.transform(X)
    probs = model.predict_proba(X)   # (n_bars, n_states)

    # EMA-smooth each state posterior
    probs_df = pd.DataFrame(probs)
    probs_smooth = probs_df.ewm(span=smooth_span, adjust=False).mean().values

    # Assign state with hold buffer
    n = len(df_1d)
    raw_state  = np.argmax(probs_smooth, axis=1)
    raw_conf   = np.max(probs_smooth, axis=1)

    final_state = np.zeros(n, dtype=int)
    final_state[0] = raw_state[0]
    hold_counter = 0

    for i in range(1, n):
        if raw_conf[i] >= prob_threshold and raw_state[i] != final_state[i - 1]:
            if hold_counter >= hold_bars:
                final_state[i] = raw_state[i]
                hold_counter = 0
            else:
                final_state[i] = final_state[i - 1]
                hold_counter += 1
        else:
            final_state[i] = final_state[i - 1]

    labels = [state_labels.get(str(s), "sideways") for s in final_state]
    result = pd.DataFrame({
        "timestamp":    df_1d["timestamp"].values,
        "hmm_state_int": final_state,
        "hmm_label":    labels,
        "hmm_conf":     raw_conf,
    })
    return result


def attach_hmm_to_4h(df_4h: pd.DataFrame, hmm_df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill daily HMM state onto 4h bars."""
    df_4h = df_4h.copy()
    hmm_daily = hmm_df.copy()
    # Normalize timestamps to tz-naive dates for merge
    hmm_daily["date"] = pd.to_datetime(hmm_daily["timestamp"]).dt.tz_localize(None).dt.normalize()
    df_4h["date"] = pd.to_datetime(df_4h["timestamp"]).dt.tz_localize(None).dt.normalize()

    merged = df_4h.merge(
        hmm_daily[["date", "hmm_label", "hmm_state_int", "hmm_conf"]],
        on="date", how="left"
    )
    merged["hmm_label"] = merged["hmm_label"].fillna("sideways")
    merged["hmm_state_int"] = merged["hmm_state_int"].fillna(0).astype(int)
    merged["hmm_conf"] = merged["hmm_conf"].fillna(0.0)
    merged.drop(columns=["date"], inplace=True)
    return merged


# ---------------------------------------------------------------------------
# Regime-isolated analysis
# ---------------------------------------------------------------------------

def run_regime_isolated(
    symbol: str,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    hmm_df: pd.DataFrame,
    strategies: List[str],
    strategy_params: dict,
) -> Dict[str, Dict[str, object]]:
    """
    For each HMM regime label, mask the 4h data to only those bars
    and run each strategy in isolation. Returns nested dict:
      {regime_label: {strategy: BacktestResult}}
    """
    df_4h_hmm = attach_hmm_to_4h(df_4h, hmm_df)
    regime_labels = sorted(df_4h_hmm["hmm_label"].unique())

    results = {}
    for label in regime_labels:
        mask = df_4h_hmm["hmm_label"] == label
        df_regime_4h = df_4h_hmm[mask].reset_index(drop=True)

        # Align daily data
        if len(df_regime_4h) == 0:
            continue
        t_min = df_regime_4h["timestamp"].min()
        t_max = df_regime_4h["timestamp"].max()
        df_regime_1d = df_1d[
            (df_1d["timestamp"] >= t_min) & (df_1d["timestamp"] <= t_max)
        ].reset_index(drop=True)

        results[label] = {}
        for strat in strategies:
            params = dict(strategy_params.get(strat, {}))
            cfg = BacktestConfig(
                symbol=symbol,
                df_4h=df_regime_4h.drop(columns=["hmm_label", "hmm_state_int", "hmm_conf"], errors="ignore"),
                df_1d=df_regime_1d,
                strategy=strat,
                params=params,
                ignore_regime_filter=bool(params.get("ignore_regime_filter", True)),
            )
            results[label][strat] = run_backtest(cfg)

    return results


def print_regime_table(symbol: str, regime_results: Dict[str, Dict[str, object]]) -> None:
    print(f"\n{'='*80}")
    print(f"  {symbol}  — Per-Regime Strategy Performance")
    print(f"{'='*80}")
    header = f"  {'Regime':<12} {'Strategy':<24} {'Trades':>6} {'WinR%':>6} {'Sharpe':>7} {'MaxDD%':>7} {'Ret%':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for label in sorted(regime_results.keys()):
        for strat, res in sorted(regime_results[label].items()):
            m = res.metrics
            trades = m.get("trade_count", 0)
            flag = ""
            print(
                f"  {label:<12} {strat:<24} "
                f"{trades:>6} "
                f"{m.get('win_rate',0)*100:>6.1f} "
                f"{m.get('sharpe',0):>7.3f} "
                f"{m.get('max_drawdown',0)*100:>7.2f} "
                f"{m.get('total_return_pct',0):>7.1f}"
            )


# ---------------------------------------------------------------------------
# Regime-switching backtest (strategy selected per bar by HMM state)
# ---------------------------------------------------------------------------

def run_regime_switching_backtest(
    symbol: str,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    hmm_df: pd.DataFrame,
    regime_strategy_map: dict,
    strategy_params: dict,
    skip_sideways: bool = False,
    sideways_filters: bool = False,
) -> object:
    """
    Single-pass backtest where strategy and risk params are selected per bar
    based on the HMM regime label.
    """
    from strategy import compute_4h_indicators, compute_daily_regime, attach_regime_to_4h, entry_signal, exit_signal, compute_atr_stop
    import math

    df_4h_hmm = attach_hmm_to_4h(df_4h, hmm_df)
    df4h_ind  = compute_4h_indicators(df_4h_hmm.copy())
    df_reg    = compute_daily_regime(df_1d.copy(), regime_ma_len=200, regime_slope_len=5, confirm_days=2)
    from strategy import attach_regime_to_4h as _attach
    df = _attach(df4h_ind, df_reg).dropna().reset_index(drop=True)

    if len(df) < 10:
        from backtest_engine import BacktestResult, _compute_metrics
        eq = pd.Series([10_000.0])
        return BacktestResult(symbol=symbol, strategy="regime_switching",
                              trades=[], equity_curve=eq, metrics=_compute_metrics([], eq))

    from backtest_engine import Trade, BacktestResult, _compute_metrics

    equity      = 10_000.0
    cash        = 10_000.0
    positions   = {}
    trades_list = []
    equity_vals = [equity]
    fee_pct     = 0.001
    slip_mul    = 10 / 10_000.0

    for i in range(1, len(df)):
        sig      = df.iloc[i]
        prev_sig = df.iloc[i - 1]
        px       = float(sig["close"])
        hmm_lbl  = str(sig.get("hmm_label", "sideways"))

        regime_cfg = regime_strategy_map.get(hmm_lbl, regime_strategy_map.get("sideways", {}))
        strat      = regime_cfg.get("strategy", "obv_breakout")
        risk_scale = float(regime_cfg.get("risk_scale", 1.0))
        tp_pct     = float(regime_cfg.get("take_profit_pct",
                           strategy_params.get(strat, {}).get("take_profit_pct", 0.08)))
        params     = dict(strategy_params.get(strat, {}))
        params["take_profit_pct"] = tp_pct

        if sideways_filters and hmm_lbl == "sideways":
            if strat == "obv_breakout":
                params["adx_upper_threshold"] = 25
            elif strat == "rsi_momentum_pullback":
                params["bb_proximity_pct"] = 0.03

        max_hold    = int(params.get("max_holding_periods", 30))
        stop_pct    = float(params.get("stop_loss_pct", 0.04))
        ignore_reg  = bool(params.get("ignore_regime_filter", False))
        risk_on     = bool(sig.get("risk_on", False))

        # Manage open position (close if strategy changed regime)
        if symbol in positions:
            pos = positions[symbol]
            pos["high_water"] = max(pos["high_water"], px)
            trail = pos["high_water"] * (1 - stop_pct)
            if trail > pos["stop_px"]:
                pos["stop_px"] = trail

            exit_reason = None
            if px <= pos["stop_px"]:
                exit_reason = "stop"
            elif tp_pct > 0 and px >= pos["entry_px"] * (1 + tp_pct):
                exit_reason = "take_profit"
            elif (not ignore_reg) and (not risk_on):
                exit_reason = "risk_off_exit"
            elif max_hold > 0 and (i - pos["entry_bar"]) >= max_hold:
                exit_reason = "max_hold"
            elif exit_signal(sig, strategy=pos["strategy"], params=params):
                exit_reason = "signal_exit"

            if exit_reason:
                slip = px * slip_mul
                exit_px_eff = px - slip
                fee = pos["qty"] * exit_px_eff * fee_pct
                gross = pos["qty"] * (exit_px_eff - pos["entry_px"])
                net   = gross - fee - pos["entry_fee"] - slip * pos["qty"]
                cash += pos["qty"] * exit_px_eff - fee
                trades_list.append(Trade(
                    symbol=symbol,
                    entry_bar=pos["entry_bar"], exit_bar=i,
                    entry_px=pos["entry_px"], exit_px=exit_px_eff,
                    qty=pos["qty"],
                    gross_pnl=gross, fees=fee + pos["entry_fee"],
                    slippage=slip * pos["qty"],
                    net_pnl=net,
                    exit_reason=exit_reason,
                    hold_bars=i - pos["entry_bar"],
                    regime_at_entry=pos["regime_at_entry"],
                ))
                del positions[symbol]

        # Check entry
        skip_entry = skip_sideways and hmm_lbl == "sideways"
        if symbol not in positions and not skip_entry:
            regime_ok = risk_on or ignore_reg
            if regime_ok and entry_signal(sig, prev_sig, strategy=strat, params=params):
                effective_stop = px * (1 - stop_pct)
                atr_stop = compute_atr_stop(sig, multiplier=2.0)
                if not math.isnan(atr_stop) and atr_stop < px and atr_stop > effective_stop:
                    effective_stop = atr_stop
                stop_dist = px - effective_stop
                if stop_dist <= 0:
                    equity_vals.append(cash)
                    continue
                risk_amt = equity * 0.01 * risk_scale
                slip = px * slip_mul
                entry_px_eff = px + slip
                qty = min(risk_amt / stop_dist, (equity * 0.15) / entry_px_eff)
                cost = qty * entry_px_eff
                fee_entry = cost * fee_pct
                if cost + fee_entry > cash or qty <= 0:
                    equity_vals.append(cash)
                    continue
                cash -= cost + fee_entry
                positions[symbol] = {
                    "qty": qty, "entry_px": entry_px_eff,
                    "stop_px": effective_stop, "high_water": px,
                    "entry_bar": i, "entry_fee": fee_entry,
                    "strategy": strat, "regime_at_entry": risk_on,
                }

        open_val = sum(positions[s]["qty"] * float(df.iloc[i]["close"]) for s in positions)
        equity = cash + open_val
        equity_vals.append(equity)

    equity_curve = pd.Series(equity_vals, name="equity")
    metrics = _compute_metrics(trades_list, equity_curve)
    from backtest_engine import BacktestResult
    return BacktestResult(symbol=symbol, strategy="regime_switching",
                          trades=trades_list, equity_curve=equity_curve, metrics=metrics)


def run_regime_switching_wfo(
    symbol: str,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    hmm_df: pd.DataFrame,
    regime_strategy_map: dict,
    strategy_params: dict,
    n_splits: int = 5,
    skip_sideways: bool = False,
    sideways_filters: bool = False,
) -> List[object]:
    """Walk-forward regime switching backtest."""
    # Normalize all timestamp columns to tz-naive for consistent comparison
    def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
        if pd.api.types.is_datetime64tz_dtype(df["timestamp"]):
            df = df.copy()
            df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        return df

    df_4h  = _strip_tz(df_4h)
    df_1d  = _strip_tz(df_1d)
    hmm_df = _strip_tz(hmm_df)

    n = len(df_4h)
    window_size = n // n_splits
    results = []

    for k in range(n_splits):
        start = k * window_size
        end   = start + window_size if k < n_splits - 1 else n
        split_4h = df_4h.iloc[start:end].reset_index(drop=True)
        t_min = split_4h["timestamp"].min()
        t_max = split_4h["timestamp"].max()
        split_1d = df_1d[(df_1d["timestamp"] >= t_min) & (df_1d["timestamp"] <= t_max)].reset_index(drop=True)
        split_hmm = hmm_df[(hmm_df["timestamp"] >= t_min) & (hmm_df["timestamp"] <= t_max)].reset_index(drop=True)
        if len(split_1d) < 50 or len(split_4h) < 10:
            continue
        r = run_regime_switching_backtest(
            symbol=symbol, df_4h=split_4h, df_1d=split_1d, hmm_df=split_hmm,
            regime_strategy_map=regime_strategy_map, strategy_params=strategy_params,
            skip_sideways=skip_sideways, sideways_filters=sideways_filters,
        )
        results.append(r)
        m = r.metrics
        print(f"  Fold {k+1}: trades={m['trade_count']} sharpe={m['sharpe']:.3f} "
              f"ret={m['total_return_pct']:.1f}% maxdd={m['max_drawdown']*100:.1f}%")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Regime-conditioned strategy analysis")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--hmm",        required=True, help="Path to regime_hmm.pkl")
    parser.add_argument("--hmm-states", required=True, help="Path to regime_hmm_states.json")
    parser.add_argument("--data-dir", default=os.path.join(_ROOT, "data"))
    parser.add_argument("--no-wfo",  action="store_true", help="Full-history only (skip WFO)")
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--skip-sideways", action="store_true",
                        help="Skip all entries when HMM state is sideways")
    parser.add_argument("--sideways-filters", action="store_true",
                        help="Apply tighter entry filters during sideways (adx_upper, bb_proximity)")
    parser.add_argument("--isolated", action="store_true",
                        help="Show per-regime isolated strategy performance table")
    args = parser.parse_args()

    print(f"Loading HMM from {args.hmm}...")
    model, scaler, states_cfg = load_hmm(args.hmm, args.hmm_states)
    print(f"  State labels: {states_cfg['state_labels']}")

    strategy_params = {k: dict(v) for k, v in DEFAULT_STRATEGY_PARAMS.items()}
    if args.sideways_filters:
        strategy_params["obv_breakout"]["adx_upper_threshold"] = 25
        strategy_params["rsi_momentum_pullback"]["bb_proximity_pct"] = 0.03
        print("  Sideways filters: adx_upper_threshold=25 (OBV), bb_proximity_pct=0.03 (RSI)")

    for sym in args.symbols:
        sym_upper = sym.upper()
        pair = f"{sym_upper}/USDT"
        path_4h = os.path.join(args.data_dir, f"{sym_upper}_4h.csv")
        path_1d = os.path.join(args.data_dir, f"{sym_upper}_1d.csv")

        if not os.path.exists(path_4h) or not os.path.exists(path_1d):
            print(f"\n[SKIP] {sym_upper}: missing CSV files")
            continue

        print(f"\n{'='*60}")
        print(f"  {pair}")
        print(f"{'='*60}")

        df_4h = load_ohlcv_csv(path_4h)
        df_1d = load_ohlcv_csv(path_1d)

        # Compute HMM regime labels on daily data
        print("  Computing HMM regime labels...")
        hmm_df = compute_hmm_regime_df(model, scaler, states_cfg, df_1d)
        dist = hmm_df["hmm_label"].value_counts(normalize=True)
        for lbl, frac in dist.items():
            print(f"    {lbl}: {frac:.1%}")

        if args.isolated:
            print("\n  Running regime-isolated analysis...")
            strategies = ["obv_breakout", "vwap_band_bounce", "rsi_momentum_pullback"]
            regime_res = run_regime_isolated(
                symbol=pair, df_4h=df_4h, df_1d=df_1d, hmm_df=hmm_df,
                strategies=strategies, strategy_params=strategy_params,
            )
            print_regime_table(pair, regime_res)

        if args.no_wfo:
            print("\n  Running regime-switching full-history backtest...")
            r = run_regime_switching_backtest(
                symbol=pair, df_4h=df_4h, df_1d=df_1d, hmm_df=hmm_df,
                regime_strategy_map=DEFAULT_REGIME_STRATEGY_MAP,
                strategy_params=strategy_params,
                skip_sideways=args.skip_sideways,
                sideways_filters=args.sideways_filters,
            )
            m = r.metrics
            skip_tag  = " [skip_sideways]" if args.skip_sideways else ""
            filter_tag = " [sideways_filters]" if args.sideways_filters else ""
            print(f"  Result{skip_tag}{filter_tag}: trades={m['trade_count']} "
                  f"sharpe={m['sharpe']:.3f} ret={m['total_return_pct']:.1f}% "
                  f"maxdd={m['max_drawdown']*100:.1f}%")
        else:
            print(f"\n  Running regime-switching WFO ({args.n_splits} folds)...")
            fold_results = run_regime_switching_wfo(
                symbol=pair, df_4h=df_4h, df_1d=df_1d, hmm_df=hmm_df,
                regime_strategy_map=DEFAULT_REGIME_STRATEGY_MAP,
                strategy_params=strategy_params,
                n_splits=args.n_splits,
                skip_sideways=args.skip_sideways,
                sideways_filters=args.sideways_filters,
            )
            sharpes = [r.metrics["sharpe"] for r in fold_results if r.metrics["trade_count"] >= MIN_TRADES]
            mean_sh = np.mean(sharpes) if sharpes else 0.0
            print(f"  WFO mean OOS Sharpe: {mean_sh:.3f}  ({len(sharpes)}/{args.n_splits} valid folds)")


if __name__ == "__main__":
    main()
