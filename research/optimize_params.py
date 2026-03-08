"""
Per-symbol parameter optimization via purged cross-validation.

Uses purged_cv() Sharpe as objective. Grid search over param combinations.
Warns if best OOS Sharpe exceeds baseline by more than OVERFIT_WARN.

Usage:
    python3 research/optimize_params.py --symbols ETH SOL TRX ADA LTC BAT RUNE --strategy obv_breakout
    python3 research/optimize_params.py --symbols VTHO --strategy vwap_band_bounce --out-json
    python3 research/optimize_params.py --symbols ETH --strategy rsi_momentum_pullback
"""

import os
import sys
import argparse
import itertools
import json
import warnings

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from backtest_engine import BacktestConfig, purged_cv, load_ohlcv_csv

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Parameter grids
# ---------------------------------------------------------------------------

PARAM_GRIDS = {
    "obv_breakout": {
        "volume_ratio_threshold": [1.1, 1.2, 1.3, 1.5, 1.7],
        "take_profit_pct":        [0.06, 0.08, 0.10, 0.12],
        "max_holding_periods":    [20, 30, 40],
    },
    "vwap_band_bounce": {
        "rsi_threshold":       [35, 40, 45],
        "mfi_threshold":       [30, 35, 40],
        "take_profit_pct":     [0.05, 0.06, 0.08],
        "max_holding_periods": [10, 12, 16],
    },
    "rsi_momentum_pullback": {
        "adx_threshold":       [15, 20, 25],
        "rsi_lower":           [20, 25, 30],
        "rsi_upper":           [40, 45, 50],
        "rsi_exit":            [62, 68, 75],
        "take_profit_pct":     [0.06, 0.08, 0.10],
        "max_holding_periods": [15, 20, 25],
    },
}

# Fixed params not varied in grid (strategy-specific)
FIXED_PARAMS = {
    "obv_breakout":          {"ignore_regime_filter": True, "stop_loss_pct": 0.04},
    "vwap_band_bounce":      {"ignore_regime_filter": True, "stop_loss_pct": 0.035},
    "rsi_momentum_pullback": {"ignore_regime_filter": True, "stop_loss_pct": 0.04},
}

MIN_FOLD_TRADES = 3   # folds with fewer trades are excluded from mean Sharpe
OVERFIT_WARN   = 0.5  # warn if best Sharpe exceeds baseline by this amount


def _baseline_sharpe(symbol: str, strategy: str, df_4h: pd.DataFrame, df_1d: pd.DataFrame, n_splits: int) -> float:
    """Run purged_cv with default params to get baseline OOS Sharpe."""
    fixed = FIXED_PARAMS.get(strategy, {})
    cfg = BacktestConfig(
        symbol=symbol,
        df_4h=df_4h,
        df_1d=df_1d,
        strategy=strategy,
        params=dict(fixed),
        ignore_regime_filter=bool(fixed.get("ignore_regime_filter", False)),
    )
    results = purged_cv(cfg, n_splits=n_splits)
    sharpes = [r.metrics["sharpe"] for r in results if r.metrics.get("trade_count", 0) >= MIN_FOLD_TRADES]
    return float(np.mean(sharpes)) if sharpes else 0.0


def optimize_symbol(symbol: str, strategy: str, df_4h: pd.DataFrame, df_1d: pd.DataFrame,
                    n_splits: int, out_json: bool) -> dict:
    grid = PARAM_GRIDS.get(strategy)
    if grid is None:
        print(f"  No grid defined for strategy '{strategy}'")
        return {}

    fixed = FIXED_PARAMS.get(strategy, {})
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))

    print(f"\n{'='*60}")
    print(f"  {symbol}  |  {strategy}  |  {len(combos)} combinations  |  {n_splits} folds")
    print(f"{'='*60}")

    baseline = _baseline_sharpe(symbol, strategy, df_4h, df_1d, n_splits)
    print(f"  Baseline OOS Sharpe: {baseline:.3f}")

    best_sharpe = -999.0
    best_params = None
    best_trades = 0

    for i, combo in enumerate(combos):
        params = dict(fixed)
        params.update(dict(zip(keys, combo)))

        cfg = BacktestConfig(
            symbol=symbol,
            df_4h=df_4h,
            df_1d=df_1d,
            strategy=strategy,
            params=params,
            ignore_regime_filter=bool(fixed.get("ignore_regime_filter", False)),
        )
        results = purged_cv(cfg, n_splits=n_splits)
        sharpes = [r.metrics["sharpe"] for r in results if r.metrics.get("trade_count", 0) >= MIN_FOLD_TRADES]
        mean_sharpe = float(np.mean(sharpes)) if sharpes else -999.0
        total_trades = sum(r.metrics.get("trade_count", 0) for r in results)

        if mean_sharpe > best_sharpe:
            best_sharpe = mean_sharpe
            best_params = params
            best_trades = total_trades

        if (i + 1) % 50 == 0 or (i + 1) == len(combos):
            print(f"  [{i+1:4d}/{len(combos)}] best so far: Sharpe={best_sharpe:.3f}  params={best_params}")

    delta = best_sharpe - baseline
    overfit_flag = " *** OVERFIT WARNING ***" if delta > OVERFIT_WARN else ""

    print(f"\n  BEST: Sharpe={best_sharpe:.3f}  (Δ={delta:+.3f}{overfit_flag})")
    print(f"  Trades across folds: {best_trades}")
    print(f"  Params: {best_params}")

    if out_json and best_params:
        # Exclude fixed params from JSON output
        user_params = {k: v for k, v in best_params.items() if k not in fixed or fixed[k] != v}
        print(f"\n  config.json block for {symbol}:")
        print(json.dumps(user_params, indent=4))

    return {"symbol": symbol, "strategy": strategy, "sharpe": best_sharpe,
            "baseline": baseline, "delta": delta, "trades": best_trades,
            "params": best_params}


def main():
    parser = argparse.ArgumentParser(description="Per-symbol parameter optimizer")
    parser.add_argument("--symbols", nargs="+", required=True,
                        help="Symbol base names (e.g. ETH SOL TRX)")
    parser.add_argument("--strategy", required=True,
                        choices=list(PARAM_GRIDS.keys()),
                        help="Strategy to optimize")
    parser.add_argument("--n-splits", type=int, default=5,
                        help="Number of purged CV folds (default: 5)")
    parser.add_argument("--data-dir", default=os.path.join(_ROOT, "data"),
                        help="Directory containing OHLCV CSV files")
    parser.add_argument("--out-json", action="store_true",
                        help="Print best params as config.json-ready JSON block")
    args = parser.parse_args()

    results_summary = []
    for sym in args.symbols:
        sym_upper = sym.upper()
        pair = f"{sym_upper}/USDT"

        path_4h = os.path.join(args.data_dir, f"{sym_upper}_4h.csv")
        path_1d = os.path.join(args.data_dir, f"{sym_upper}_1d.csv")

        if not os.path.exists(path_4h):
            print(f"\n[SKIP] {sym_upper}: {path_4h} not found")
            continue
        if not os.path.exists(path_1d):
            print(f"\n[SKIP] {sym_upper}: {path_1d} not found")
            continue

        df_4h = load_ohlcv_csv(path_4h)
        df_1d = load_ohlcv_csv(path_1d)

        result = optimize_symbol(
            symbol=pair,
            strategy=args.strategy,
            df_4h=df_4h,
            df_1d=df_1d,
            n_splits=args.n_splits,
            out_json=args.out_json,
        )
        if result:
            results_summary.append(result)

    # Summary table
    if results_summary:
        print(f"\n{'='*70}")
        print(f"  OPTIMIZATION SUMMARY — {args.strategy}")
        print(f"{'='*70}")
        print(f"  {'Symbol':<12} {'Baseline':>10} {'Best':>10} {'Delta':>8} {'Trades':>8}")
        print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
        for r in results_summary:
            overfit = " !" if r["delta"] > OVERFIT_WARN else ""
            print(f"  {r['symbol']:<12} {r['baseline']:>10.3f} {r['sharpe']:>10.3f} "
                  f"{r['delta']:>+8.3f} {r['trades']:>8}{overfit}")

        if args.out_json:
            print(f"\n  JSON block for config.json (copy under strategy sub-object):")
            for r in results_summary:
                if r["params"]:
                    fixed = FIXED_PARAMS.get(args.strategy, {})
                    user_params = {k: v for k, v in r["params"].items()
                                   if k not in fixed}
                    print(f"\n  # {r['symbol']}")
                    print(json.dumps(user_params, indent=4))


if __name__ == "__main__":
    main()
