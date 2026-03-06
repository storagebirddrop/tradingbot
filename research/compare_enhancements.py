"""
Baseline vs. Enhanced backtest comparison.

Runs the same strategy with two configurations for each symbol:
  - baseline:  fixed stop_pct, no ATR sizing, no vol-regime scaling
  - enhanced:  ATR-scaled stop (2x ATR), vol-regime position scaling

Prints a side-by-side table and optional walk-forward fold breakdown.

Usage:
    python3 research/compare_enhancements.py --symbols ETH SOL TRX --strategy obv_breakout
    python3 research/compare_enhancements.py --symbols ETH SOL TRX --strategy obv_breakout --wfo
    python3 research/compare_enhancements.py --symbols VTHO --strategy vwap_band_bounce
"""

import os
import sys
import argparse
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
DATA_DIR = os.path.join(_ROOT, "data")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from backtest_engine import (
    BacktestConfig, run_backtest, walk_forward,
    load_ohlcv_csv, print_results_table, BacktestResult,
)

STRATEGY_DEFAULTS = {
    "obv_breakout": {
        "ignore_regime_filter": False,
        "volume_ratio_threshold": 1.3,
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.10,
        "max_holding_periods": 30,
        "trail_pct": 0.04,
    },
    "vwap_band_bounce": {
        "ignore_regime_filter": False,
        "rsi_threshold": 40,
        "mfi_threshold": 35,
        "stop_loss_pct": 0.035,
        "take_profit_pct": 0.06,
        "max_holding_periods": 12,
    },
    "rsi_momentum_pullback": {
        "ignore_regime_filter": True,
        "adx_threshold": 20,
        "rsi_lower": 25,
        "rsi_upper": 45,
        "rsi_exit": 68,
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.08,
        "max_holding_periods": 20,
    },
}


def _cfg(base, df4h, df1d, strategy, params, use_atr, atr_mult=2.0) -> BacktestConfig:
    return BacktestConfig(
        symbol=f"{base}/USDT",
        df_4h=df4h.copy(),
        df_1d=df1d.copy(),
        strategy=strategy,
        params=params,
        initial_capital=10_000.0,
        risk_per_trade=0.01,
        stop_pct=float(params.get("stop_loss_pct", 0.04)),
        trail_pct=float(params.get("trail_pct", 0.04)),
        slippage_bps=10.0,
        fee_pct=0.001,
        max_position_pct=0.15,
        max_positions=2,
        ignore_regime_filter=bool(params.get("ignore_regime_filter", False)),
        use_atr_sizing=use_atr,
        atr_stop_multiplier=atr_mult,
    )


def _metric_delta(enhanced: dict, baseline: dict, key: str, lower_is_better: bool = False) -> str:
    b = baseline.get(key, 0)
    e = enhanced.get(key, 0)
    delta = e - b
    if lower_is_better:
        arrow = "↓" if delta < 0 else ("↑" if delta > 0 else "→")
    else:
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
    return f"{arrow}{abs(delta):.3f}"


def print_comparison_table(rows: list) -> None:
    """
    rows: list of dicts with keys:
      symbol, strategy, config, trade_count, win_rate, profit_factor,
      sharpe, max_drawdown, total_return_pct
    """
    header = (
        f"{'Symbol':<8} {'Strategy':<20} {'Config':<10} "
        f"{'Trades':>6} {'WinR%':>6} {'PF':>6} "
        f"{'Sharpe':>7} {'MaxDD%':>7} {'Ret%':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['symbol']:<8} {r['strategy']:<20} {r['config']:<10} "
            f"{r['trade_count']:>6} "
            f"{r['win_rate']*100:>6.1f} "
            f"{r['profit_factor']:>6.2f} "
            f"{r['sharpe']:>7.3f} "
            f"{r['max_drawdown']*100:>7.2f} "
            f"{r['total_return_pct']:>7.1f}"
        )


def print_delta_summary(base_rows: list, enh_rows: list) -> None:
    """Print enhancement delta for each symbol."""
    print("\n  Enhancement delta (enhanced - baseline):")
    print(f"  {'Symbol':<8} {'Sharpe':>8} {'MaxDD%':>8} {'PF':>8}")
    print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    base_by_sym = {r["symbol"]: r for r in base_rows}
    enh_by_sym  = {r["symbol"]: r for r in enh_rows}
    for sym in enh_by_sym:
        if sym not in base_by_sym:
            continue
        b = base_by_sym[sym]
        e = enh_by_sym[sym]
        sharpe_d = e["sharpe"] - b["sharpe"]
        dd_d     = e["max_drawdown"] - b["max_drawdown"]
        pf_d     = e["profit_factor"] - b["profit_factor"]
        sharpe_s = f"+{sharpe_d:.3f}" if sharpe_d >= 0 else f"{sharpe_d:.3f}"
        dd_s     = f"+{dd_d*100:.2f}%" if dd_d >= 0 else f"{dd_d*100:.2f}%"
        pf_s     = f"+{pf_d:.3f}" if pf_d >= 0 else f"{pf_d:.3f}"
        print(f"  {sym:<8} {sharpe_s:>8} {dd_s:>8} {pf_s:>8}")


def main():
    parser = argparse.ArgumentParser(description="Baseline vs enhanced backtest comparison")
    parser.add_argument("--symbols",   nargs="+", default=["ETH", "SOL", "TRX"],
                        help="Base symbols to compare (default: ETH SOL TRX)")
    parser.add_argument("--strategy",  default="obv_breakout",
                        choices=list(STRATEGY_DEFAULTS.keys()))
    parser.add_argument("--wfo",       action="store_true",
                        help="Also run 5-fold walk-forward optimisation")
    parser.add_argument("--atr-mult",  type=float, default=2.0,
                        help="ATR multiplier for enhanced config (default: 2.0)")
    args = parser.parse_args()

    params = STRATEGY_DEFAULTS[args.strategy]
    base_rows, enh_rows = [], []
    wfo_base_sharpes, wfo_enh_sharpes = [], []

    for base in args.symbols:
        csv4h = os.path.join(DATA_DIR, f"{base}_4h.csv")
        csv1d = os.path.join(DATA_DIR, f"{base}_1d.csv")
        # Check which files are missing and provide specific warning
        missing_files = []
        if not os.path.exists(csv4h):
            missing_files.append(csv4h)
        if not os.path.exists(csv1d):
            missing_files.append(csv1d)
        
        if missing_files:
            missing_str = ", ".join(missing_files)
            print(f"[{base}] WARNING: CSV file(s) not found: {missing_str} — run fetch_data.py first. Skipping.")
            continue

        print(f"\nLoading {base}/USDT data...")
        df4h = load_ohlcv_csv(csv4h)
        df1d = load_ohlcv_csv(csv1d)
        print(f"  4h: {len(df4h)} bars | 1d: {len(df1d)} bars")

        # --- Baseline ---
        print(f"  Running baseline ({base})...")
        base_cfg = _cfg(base, df4h, df1d, args.strategy, params, use_atr=False)
        base_result = run_backtest(base_cfg)
        m = base_result.metrics
        base_rows.append({
            "symbol": base, "strategy": args.strategy, "config": "baseline",
            **m
        })

        # --- Enhanced ---
        print(f"  Running enhanced ({base})...")
        enh_cfg = _cfg(base, df4h, df1d, args.strategy, params, use_atr=True, atr_mult=args.atr_mult)
        enh_result = run_backtest(enh_cfg)
        m = enh_result.metrics
        enh_rows.append({
            "symbol": base, "strategy": args.strategy, "config": "enhanced",
            **m
        })

        # --- WFO ---
        if args.wfo:
            print(f"  Walk-forward baseline ({base})...")
            wfo_b = walk_forward(base_cfg, n_splits=5)
            wfo_e_results = walk_forward(enh_cfg, n_splits=5)
            b_sharpes = [r.metrics.get("sharpe", 0) for r in wfo_b]
            e_sharpes = [r.metrics.get("sharpe", 0) for r in wfo_e_results]
            wfo_base_sharpes.append((base, b_sharpes))
            wfo_enh_sharpes.append((base, e_sharpes))

    # --- Print results ---
    print(f"\n{'='*75}")
    print(f"  Strategy: {args.strategy}")
    print(f"{'='*75}\n")

    all_rows = []
    sym_order = [r["symbol"] for r in base_rows]
    base_by_sym = {r["symbol"]: r for r in base_rows}
    enh_by_sym  = {r["symbol"]: r for r in enh_rows}
    for sym in sym_order:
        if sym in base_by_sym:
            all_rows.append(base_by_sym[sym])
        if sym in enh_by_sym:
            all_rows.append(enh_by_sym[sym])

    print_comparison_table(all_rows)
    print_delta_summary(base_rows, enh_rows)

    if args.wfo:
        print(f"\n{'='*75}")
        print("  Walk-Forward Sharpe per Fold")
        print(f"{'='*75}")
        print(f"  {'Symbol':<8} {'Config':<10} {'Fold1':>7} {'Fold2':>7} {'Fold3':>7} {'Fold4':>7} {'Fold5':>7} {'Mean':>7} {'Std':>6}")
        print(f"  {'-'*8} {'-'*10} " + " ".join([f"{'':>7}"] * 7))
        for base, sharpes in wfo_base_sharpes:
            vals = [f"{s:>7.3f}" for s in sharpes]
            vals += ["     -"] * (5 - len(vals))
            mean = np.mean(sharpes) if sharpes else 0
            std  = np.std(sharpes)  if sharpes else 0
            print(f"  {base:<8} {'baseline':<10} " + " ".join(vals) + f" {mean:>7.3f} {std:>6.3f}")
        for base, sharpes in wfo_enh_sharpes:
            vals = [f"{s:>7.3f}" for s in sharpes]
            vals += ["     -"] * (5 - len(vals))
            mean = np.mean(sharpes) if sharpes else 0
            std  = np.std(sharpes)  if sharpes else 0
            print(f"  {base:<8} {'enhanced':<10} " + " ".join(vals) + f" {mean:>7.3f} {std:>6.3f}")

        # Stability check
        all_stds = [np.std(s) for _, s in wfo_enh_sharpes if s]
        if all_stds:
            avg_std = np.mean(all_stds)
            status = "PASS" if avg_std < 0.5 else "WARN — high variance across folds"
            print(f"\n  WFO stability check: avg fold-Sharpe std = {avg_std:.3f} [{status}]")


if __name__ == "__main__":
    main()
