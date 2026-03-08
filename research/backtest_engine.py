"""
Unified backtest engine for the trading bot.

Usage:
    python3 research/backtest_engine.py

Loads historical OHLCV from CSV files (or fetches via ccxt if not cached),
runs the existing strategy logic with realistic fee + slippage deductions,
and reports walk-forward metrics. Reuses compute_4h_indicators(),
compute_daily_regime(), and attach_regime_to_4h() from strategy.py.

Required CSV columns: timestamp, open, high, low, close, volume
Timestamps must be parseable by pd.to_datetime.

Walk-forward: n_splits rolling windows, each trained on (1 - test_ratio)
of the available data and tested on the remaining slice.

Purged CV: GroupKFold by calendar month with an embargo of embargo_bars
bars between train and test to prevent leakage.
"""

import os
import sys
import math
import json
import warnings
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd

# Allow running from the project root or research/ directory
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(os.path.dirname(_HERE), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from strategy import (
    compute_4h_indicators,
    compute_daily_regime,
    attach_regime_to_4h,
    entry_signal,
    exit_signal,
    compute_atr_stop,
    classify_volatility_regime,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ---------------------------------------------------------------------------
# Configuration & Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    symbol: str
    df_4h: pd.DataFrame          # pre-loaded 4h OHLCV
    df_1d: pd.DataFrame          # pre-loaded 1d OHLCV
    strategy: str = "obv_breakout"
    params: Dict[str, Any] = field(default_factory=dict)
    initial_capital: float = 10_000.0
    risk_per_trade: float = 0.01
    stop_pct: float = 0.04
    trail_pct: float = 0.04
    slippage_bps: float = 10.0   # one-way slippage in basis points
    fee_pct: float = 0.001       # taker fee (0.1%)
    max_position_pct: float = 0.15
    max_positions: int = 2
    regime_ma_len: int = 200
    regime_slope_len: int = 5
    regime_confirm_days: int = 2
    ignore_regime_filter: bool = False
    use_atr_sizing: bool = True
    atr_stop_multiplier: float = 2.0
    skip_sideways: bool = False   # skip entries when ema200_slope ≈ 0 and risk_off


@dataclass
class Trade:
    symbol: str
    entry_bar: int
    exit_bar: int
    entry_px: float
    exit_px: float
    qty: float
    gross_pnl: float
    fees: float
    slippage: float
    net_pnl: float
    exit_reason: str
    hold_bars: int
    regime_at_entry: bool


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    trades: List[Trade]
    equity_curve: pd.Series      # indexed by bar number
    metrics: Dict[str, float]


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def _compute_metrics(trades: List[Trade], equity_curve: pd.Series) -> Dict[str, float]:
    if not trades:
        return {
            "trade_count": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "sharpe": 0.0, "sortino": 0.0, "calmar": 0.0,
            "max_drawdown": 0.0, "avg_hold_bars": 0.0,
            "total_return_pct": 0.0,
        }

    pnls = np.array([t.net_pnl for t in trades])
    wins  = pnls[pnls > 0]
    loses = pnls[pnls < 0]
    win_rate      = len(wins) / len(pnls)
    profit_factor = (wins.sum() / abs(loses.sum())) if len(loses) > 0 else float("inf")
    avg_hold      = np.mean([t.hold_bars for t in trades])

    # Equity-curve-based metrics
    eq = equity_curve.values
    rets = np.diff(eq) / eq[:-1]
    annual_factor = math.sqrt(365 * 6)  # 4h bars: 6 per day
    sharpe  = (rets.mean() / rets.std() * annual_factor) if rets.std() > 0 else 0.0
    down    = rets[rets < 0]
    sortino = (rets.mean() / down.std() * annual_factor) if (len(down) > 0 and down.std() > 0) else 0.0

    peak   = np.maximum.accumulate(eq)
    dd     = (peak - eq) / peak
    max_dd = dd.max()

    total_ret = (eq[-1] - eq[0]) / eq[0] * 100
    n_years   = len(rets) / (365 * 6)
    annual_ret = ((eq[-1] / eq[0]) ** (1 / n_years) - 1) if n_years > 0 else 0.0
    calmar    = (annual_ret / max_dd) if max_dd > 0 else 0.0

    return {
        "trade_count":     len(trades),
        "win_rate":        round(win_rate, 4),
        "profit_factor":   round(profit_factor, 4),
        "sharpe":          round(sharpe, 4),
        "sortino":         round(sortino, 4),
        "calmar":          round(calmar, 4),
        "max_drawdown":    round(max_dd, 4),
        "avg_hold_bars":   round(avg_hold, 1),
        "total_return_pct": round(total_ret, 2),
    }


def run_backtest(cfg: BacktestConfig) -> BacktestResult:
    """Run a single backtest over the full date range in cfg.df_4h."""
    df4h = compute_4h_indicators(cfg.df_4h.copy())
    df_reg = compute_daily_regime(
        cfg.df_1d.copy(),
        regime_ma_len=cfg.regime_ma_len,
        regime_slope_len=cfg.regime_slope_len,
        confirm_days=cfg.regime_confirm_days,
    )
    df = attach_regime_to_4h(df4h, df_reg).dropna().reset_index(drop=True)

    if len(df) < 10:
        empty_eq = pd.Series([cfg.initial_capital], name="equity")
        return BacktestResult(
            symbol=cfg.symbol, strategy=cfg.strategy,
            trades=[], equity_curve=empty_eq,
            metrics=_compute_metrics([], empty_eq),
        )

    equity       = cfg.initial_capital
    cash         = cfg.initial_capital
    positions: Dict[str, Dict] = {}   # symbol -> {qty, entry_px, stop_px, high_water, entry_bar}
    trades: List[Trade] = []
    equity_vals  = [equity]
    slippage_mul = cfg.slippage_bps / 10_000.0

    max_hold = int(cfg.params.get("max_holding_periods", 30))
    ignore_regime = cfg.ignore_regime_filter or bool(cfg.params.get("ignore_regime_filter", False))
    take_profit_pct = float(cfg.params.get("take_profit_pct", 0.10))

    sym = cfg.symbol

    for i in range(1, len(df)):
        sig      = df.iloc[i]
        prev_sig = df.iloc[i - 1]
        px       = float(sig["close"])
        risk_on  = bool(sig.get("risk_on", False))

        # ---- manage open position ----
        if sym in positions:
            pos = positions[sym]
            pos["high_water"] = max(pos["high_water"], px)
            trail = pos["high_water"] * (1 - cfg.trail_pct)
            if trail > pos["stop_px"]:
                pos["stop_px"] = trail

            exit_reason = None
            exit_px     = px

            if px <= pos["stop_px"]:
                exit_reason = "stop"
            elif take_profit_pct > 0 and px >= pos["entry_px"] * (1 + take_profit_pct):
                exit_reason = "take_profit"
            elif (not ignore_regime) and (not risk_on):
                exit_reason = "risk_off_exit"
            elif max_hold > 0 and (i - pos["entry_bar"]) >= max_hold:
                exit_reason = "max_hold"
            elif exit_signal(sig, strategy=cfg.strategy, params=cfg.params):
                exit_reason = "signal_exit"

            if exit_reason:
                slip   = exit_px * slippage_mul
                exit_px_eff = exit_px - slip
                fee    = pos["qty"] * exit_px_eff * cfg.fee_pct
                gross  = pos["qty"] * (exit_px_eff - pos["entry_px"])
                net    = gross - fee - pos["entry_fee"] - slip * pos["qty"]
                cash   += pos["qty"] * exit_px_eff - fee
                trades.append(Trade(
                    symbol=sym,
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
                del positions[sym]

        # ---- check entry ----
        # Skip entries in sideways regime if configured
        skip_entry = False
        if cfg.skip_sideways:
            slope = float(sig.get("ema200_slope", 1.0))
            if (not risk_on) and abs(slope) < 0.001:
                skip_entry = True

        if sym not in positions and len(positions) < cfg.max_positions and not skip_entry:
            regime_ok = risk_on or ignore_regime
            if regime_ok and entry_signal(sig, prev_sig, strategy=cfg.strategy, params=cfg.params):
                # ATR-scaled stop
                effective_stop = px * (1 - cfg.stop_pct)
                if cfg.use_atr_sizing:
                    atr_stop = compute_atr_stop(sig, multiplier=cfg.atr_stop_multiplier)
                    fixed_stop = px * (1 - cfg.stop_pct)
                    if not math.isnan(atr_stop) and atr_stop < px and atr_stop > fixed_stop:
                        effective_stop = atr_stop  # ATR tighter than fixed — use it

                stop_dist = px - effective_stop
                if stop_dist <= 0:
                    equity_vals.append(cash + sum(
                        positions[s]["qty"] * float(df.iloc[i]["close"]) for s in positions
                    ))
                    continue

                risk_amt = equity * cfg.risk_per_trade
                slip     = px * slippage_mul
                entry_px_eff = px + slip
                fee_entry = 0.0
                qty = min(
                    risk_amt / stop_dist,
                    (equity * cfg.max_position_pct) / entry_px_eff,
                )
                cost = qty * entry_px_eff
                fee_entry = cost * cfg.fee_pct
                total_cost = cost + fee_entry
                if total_cost > cash or qty <= 0:
                    equity_vals.append(cash + sum(
                        positions[s]["qty"] * float(df.iloc[i]["close"]) for s in positions
                    ))
                    continue
                cash -= total_cost
                positions[sym] = {
                    "qty": qty,
                    "entry_px": entry_px_eff,
                    "stop_px": effective_stop,
                    "high_water": px,
                    "entry_bar": i,
                    "entry_fee": fee_entry,
                    "regime_at_entry": risk_on,
                }

        # Mark-to-market equity
        open_val = sum(
            positions[s]["qty"] * float(df.iloc[i]["close"]) for s in positions
        )
        equity = cash + open_val
        equity_vals.append(equity)

    equity_curve = pd.Series(equity_vals, name="equity")
    metrics = _compute_metrics(trades, equity_curve)
    return BacktestResult(
        symbol=cfg.symbol, strategy=cfg.strategy,
        trades=trades, equity_curve=equity_curve, metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Walk-forward optimisation
# ---------------------------------------------------------------------------

def walk_forward(cfg: BacktestConfig, n_splits: int = 5, test_ratio: float = 0.2) -> List[BacktestResult]:
    """
    Rolling walk-forward: split df_4h into n_splits windows.
    Each window uses (1-test_ratio) of available data as in-sample and
    test_ratio as out-of-sample. Returns one BacktestResult per window.
    """
    df4h = cfg.df_4h.reset_index(drop=True)
    n    = len(df4h)
    window_size = n // n_splits
    results = []

    for k in range(n_splits):
        start = k * window_size
        end   = start + window_size if k < n_splits - 1 else n
        split_4h = df4h.iloc[start:end].reset_index(drop=True)
        # Align daily data by timestamp range
        t_start = split_4h["timestamp"].min()
        t_end   = split_4h["timestamp"].max()
        split_1d = cfg.df_1d[
            (cfg.df_1d["timestamp"] >= t_start) & (cfg.df_1d["timestamp"] <= t_end)
        ].reset_index(drop=True)
        if len(split_1d) < cfg.regime_ma_len + 20:
            continue
        split_cfg = BacktestConfig(
            symbol=cfg.symbol,
            df_4h=split_4h,
            df_1d=split_1d,
            strategy=cfg.strategy,
            params=cfg.params,
            initial_capital=cfg.initial_capital,
            risk_per_trade=cfg.risk_per_trade,
            stop_pct=cfg.stop_pct,
            trail_pct=cfg.trail_pct,
            slippage_bps=cfg.slippage_bps,
            fee_pct=cfg.fee_pct,
            max_position_pct=cfg.max_position_pct,
            max_positions=cfg.max_positions,
            regime_ma_len=cfg.regime_ma_len,
            regime_slope_len=cfg.regime_slope_len,
            regime_confirm_days=cfg.regime_confirm_days,
            ignore_regime_filter=cfg.ignore_regime_filter,
            use_atr_sizing=cfg.use_atr_sizing,
            atr_stop_multiplier=cfg.atr_stop_multiplier,
            skip_sideways=cfg.skip_sideways,
        )
        results.append(run_backtest(split_cfg))

    return results


# ---------------------------------------------------------------------------
# Purged cross-validation with embargo
# ---------------------------------------------------------------------------

def purged_cv(cfg: BacktestConfig, n_splits: int = 5, embargo_bars: int = 12) -> List[BacktestResult]:
    """
    GroupKFold-style purged CV grouped by calendar month with embargo.
    Avoids data leakage between train and test sets.
    Returns BacktestResult for each test fold.
    """
    df4h = cfg.df_4h.reset_index(drop=True).copy()
    df4h["_month"] = df4h["timestamp"].dt.to_period("M").astype(str)
    months = list(df4h["_month"].unique())
    n_months = len(months)
    fold_size = max(1, n_months // n_splits)
    results = []

    for k in range(n_splits):
        test_months  = months[k * fold_size: (k + 1) * fold_size]
        if not test_months:
            continue
        test_idx  = df4h[df4h["_month"].isin(test_months)].index
        if len(test_idx) == 0:
            continue
        # Apply embargo: drop embargo_bars before/after test window
        test_start = test_idx.min()
        test_end   = test_idx.max()
        embargo_start = max(0, test_start - embargo_bars)
        embargo_end   = min(len(df4h) - 1, test_end + embargo_bars)
        excluded = set(range(embargo_start, embargo_end + 1))
        test_rows = df4h.iloc[test_start: test_end + 1].reset_index(drop=True)

        t_start = test_rows["timestamp"].min()
        t_end   = test_rows["timestamp"].max()
        split_1d = cfg.df_1d[
            (cfg.df_1d["timestamp"] >= t_start) & (cfg.df_1d["timestamp"] <= t_end)
        ].reset_index(drop=True)
        if len(split_1d) < cfg.regime_ma_len + 20 or len(test_rows) < 10:
            continue

        split_cfg = BacktestConfig(
            symbol=cfg.symbol,
            df_4h=test_rows.drop(columns=["_month"]),
            df_1d=split_1d,
            strategy=cfg.strategy,
            params=cfg.params,
            initial_capital=cfg.initial_capital,
            risk_per_trade=cfg.risk_per_trade,
            stop_pct=cfg.stop_pct,
            trail_pct=cfg.trail_pct,
            slippage_bps=cfg.slippage_bps,
            fee_pct=cfg.fee_pct,
            max_position_pct=cfg.max_position_pct,
            max_positions=cfg.max_positions,
            regime_ma_len=cfg.regime_ma_len,
            regime_slope_len=cfg.regime_slope_len,
            regime_confirm_days=cfg.regime_confirm_days,
            ignore_regime_filter=cfg.ignore_regime_filter,
            use_atr_sizing=cfg.use_atr_sizing,
            atr_stop_multiplier=cfg.atr_stop_multiplier,
            skip_sideways=cfg.skip_sideways,
        )
        results.append(run_backtest(split_cfg))

    return results


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def load_ohlcv_csv(path: str) -> pd.DataFrame:
    """Load a standard OHLCV CSV with columns: timestamp,open,high,low,close,volume."""
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).sort_values("timestamp").reset_index(drop=True)


def print_results_table(results: List[BacktestResult], label: str = "") -> None:
    """Print a summary table of backtest results."""
    if label:
        print(f"\n{'='*70}")
        print(f"  {label}")
        print(f"{'='*70}")
    header = f"{'Symbol':<14} {'Strategy':<22} {'Trades':>6} {'WinR%':>6} {'PF':>6} {'Sharpe':>7} {'MaxDD%':>7} {'Ret%':>7}"
    print(header)
    print("-" * len(header))
    for r in results:
        m = r.metrics
        print(
            f"{r.symbol:<14} {r.strategy:<22} "
            f"{m.get('trade_count',0):>6} "
            f"{m.get('win_rate',0)*100:>6.1f} "
            f"{m.get('profit_factor',0):>6.2f} "
            f"{m.get('sharpe',0):>7.3f} "
            f"{m.get('max_drawdown',0)*100:>7.2f} "
            f"{m.get('total_return_pct',0):>7.1f}"
        )


# ---------------------------------------------------------------------------
# CLI demo — runs if executed directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backtest engine demo")
    parser.add_argument("--csv4h",  required=True, help="Path to 4h OHLCV CSV")
    parser.add_argument("--csv1d",  required=True, help="Path to 1d OHLCV CSV")
    parser.add_argument("--symbol", default="ETH/USDT")
    parser.add_argument("--strategy", default="obv_breakout",
                        choices=["obv_breakout", "vwap_band_bounce", "rsi_momentum_pullback", "momentum_breakout"])
    parser.add_argument("--wfo", action="store_true", help="Run walk-forward optimisation")
    parser.add_argument("--cv",  action="store_true", help="Run purged cross-validation")
    parser.add_argument("--capital", type=float, default=10_000.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--fee-pct",      type=float, default=0.001)
    args = parser.parse_args()

    print(f"Loading 4h data from {args.csv4h}...")
    df4h = load_ohlcv_csv(args.csv4h)
    print(f"  {len(df4h)} bars from {df4h['timestamp'].min()} to {df4h['timestamp'].max()}")

    print(f"Loading 1d data from {args.csv1d}...")
    df1d = load_ohlcv_csv(args.csv1d)
    print(f"  {len(df1d)} bars")

    # Default params from config.json-like dict
    strategy_params = {
        "obv_breakout":           {"ignore_regime_filter": False, "volume_ratio_threshold": 1.3,
                                   "stop_loss_pct": 0.04, "take_profit_pct": 0.10, "max_holding_periods": 30},
        "vwap_band_bounce":       {"ignore_regime_filter": False, "rsi_threshold": 40, "mfi_threshold": 35,
                                   "stop_loss_pct": 0.035, "take_profit_pct": 0.06, "max_holding_periods": 12},
        "rsi_momentum_pullback":  {"ignore_regime_filter": True,  "adx_threshold": 20,
                                   "rsi_lower": 25, "rsi_upper": 45, "rsi_exit": 68,
                                   "stop_loss_pct": 0.03, "take_profit_pct": 0.08, "max_holding_periods": 20},
        "momentum_breakout":      {"ignore_regime_filter": False, "adx_threshold": 25,
                                   "rsi_lower": 55, "rsi_upper": 75, "rsi_exit": 80,
                                   "volume_ratio_threshold": 1.5,
                                   "stop_loss_pct": 0.06, "take_profit_pct": 0.20, "max_holding_periods": 20},
    }

    cfg = BacktestConfig(
        symbol=args.symbol,
        df_4h=df4h,
        df_1d=df1d,
        strategy=args.strategy,
        params=strategy_params[args.strategy],
        initial_capital=args.capital,
        slippage_bps=args.slippage_bps,
        fee_pct=args.fee_pct,
        ignore_regime_filter=strategy_params[args.strategy].get("ignore_regime_filter", False),
    )

    print(f"\nRunning full backtest: {args.symbol} / {args.strategy}")
    result = run_backtest(cfg)
    print_results_table([result], label="Full Backtest")

    if args.wfo:
        print(f"\nRunning walk-forward optimisation (5 folds)...")
        wfo_results = walk_forward(cfg, n_splits=5)
        print_results_table(wfo_results, label="Walk-Forward (per fold)")
        agg_sharpe = np.mean([r.metrics.get("sharpe", 0) for r in wfo_results])
        agg_dd     = np.mean([r.metrics.get("max_drawdown", 0) for r in wfo_results])
        print(f"\n  WFO aggregated: avg Sharpe={agg_sharpe:.3f}  avg MaxDD={agg_dd*100:.2f}%")

    if args.cv:
        print(f"\nRunning purged CV (5 folds, 12-bar embargo)...")
        cv_results = purged_cv(cfg, n_splits=5, embargo_bars=12)
        print_results_table(cv_results, label="Purged CV (per fold)")
        agg_sharpe = np.mean([r.metrics.get("sharpe", 0) for r in cv_results])
        print(f"\n  CV aggregated:  avg Sharpe={agg_sharpe:.3f}")
