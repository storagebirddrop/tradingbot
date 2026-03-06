"""
Backtest for the 3 new strategies: rsi_momentum_pullback, vwap_band_bounce, obv_breakout
Covers 2020-01-01 to 2026-01-01 on BTC/USDT, ETH/USDT, SOL/USDT, XRP/USDT (4h candles)
Uses Binance for historical data (wider coverage than Phemex).
"""
import sys
import time
import warnings
import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
import ccxt

warnings.filterwarnings("ignore")
# Use portable path resolution
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from strategy import (
    compute_4h_indicators,
    compute_daily_regime,
    attach_regime_to_4h,
    entry_signal,
    exit_signal,
)

# ── Config ────────────────────────────────────────────────────────────────────
SYMBOLS     = ["RUNE/USDT"]
START_DATE  = "2020-01-01"
END_DATE    = "2026-01-01"
INITIAL_CAP = 10_000.0   # larger capital for readable $ figures; % results are what matter
FEE_RATE    = 0.001       # 0.1% per side (Binance standard)

STRATEGIES = {
    "rsi_momentum_pullback": {
        "ignore_regime_filter": True,
        "stop_loss_pct":        0.03,
        "take_profit_pct":      0.08,
        "max_holding_periods":  20,
        "risk_per_trade":       0.03,
    },
    "vwap_band_bounce": {
        "ignore_regime_filter": False,
        "stop_loss_pct":        0.035,
        "take_profit_pct":      0.06,
        "max_holding_periods":  12,
        "risk_per_trade":       0.03,
    },
    "obv_breakout": {
        "ignore_regime_filter": False,
        "stop_loss_pct":        0.04,
        "take_profit_pct":      0.10,
        "max_holding_periods":  30,
        "risk_per_trade":       0.03,
    },
}

REGIME_PARAMS = dict(regime_ma_len=200, regime_slope_len=5, confirm_days=2)

# ── Data fetching ─────────────────────────────────────────────────────────────
def fetch_ohlcv(exchange, symbol: str, timeframe: str, since_ms: int, until_ms: int) -> pd.DataFrame:
    """Fetch all candles for a symbol/timeframe between two epoch-ms timestamps."""
    all_rows = []
    limit    = 1000
    since    = since_ms
    max_retries = 5
    retry_count = 0
    while since < until_ms:
        try:
            rows = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            retry_count = 0  # Reset on success
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                print(f"  [error] Max retries exceeded for {symbol} {timeframe}: {e}")
                raise
            print(f"  [warn] fetch error {symbol} {timeframe} (attempt {retry_count}/{max_retries}): {e}; retrying in 5s")
            time.sleep(5)
            continue
        if not rows:
            break
        all_rows.extend(rows)
        last_ts = rows[-1][0]
        if last_ts >= until_ms or len(rows) < limit:
            break
        since = last_ts + 1
        time.sleep(exchange.rateLimit / 1000)

    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df[df["timestamp"] < pd.to_datetime(until_ms, unit="ms", utc=True)]
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


# ── Backtester ────────────────────────────────────────────────────────────────
def run_backtest(df4h: pd.DataFrame, df1d: pd.DataFrame, strategy_name: str, scfg: dict) -> dict:
    """
    Run a single strategy on pre-computed indicator dataframe.
    Returns a dict of performance metrics and a list of trade records.
    """
    ignore_regime  = scfg["ignore_regime_filter"]
    sl_pct         = scfg["stop_loss_pct"]
    tp_pct         = scfg["take_profit_pct"]
    max_hold       = scfg["max_holding_periods"]
    risk_per_trade = scfg["risk_per_trade"]

    # Attach regime
    regime_df = compute_daily_regime(
        df1d,
        regime_ma_len=REGIME_PARAMS["regime_ma_len"],
        regime_slope_len=REGIME_PARAMS["regime_slope_len"],
        confirm_days=REGIME_PARAMS["confirm_days"],
    )
    df = attach_regime_to_4h(df4h, regime_df).reset_index(drop=True)

    equity   = INITIAL_CAP
    position = None   # dict: entry_px, stop_px, tp_px, qty, entry_idx
    trades   = []
    equity_curve = [equity]

    for i in range(1, len(df)):
        row      = df.iloc[i]
        prev_row = df.iloc[i - 1]
        risk_on  = bool(row.get("risk_on", False))

        # ── Exit checks on open position ──────────────────────────────────────
        if position is not None:
            entry_idx = position["entry_idx"]
            entry_px  = position["entry_px"]
            stop_px   = position["stop_px"]
            tp_px     = position["tp_px"]
            qty       = position["qty"]

            # Use intra-candle high/low for realistic stop/TP triggers
            candle_low  = row["low"]
            candle_high = row["high"]
            candle_close = row["close"]

            exit_px     = None
            exit_reason = None

            # 1. Stop loss (use candle low; assume filled at stop price)
            if candle_low <= stop_px:
                exit_px     = stop_px
                exit_reason = "stop"
            # 2. Take profit (use candle high; assume filled at TP price)
            elif candle_high >= tp_px:
                exit_px     = tp_px
                exit_reason = "take_profit"
            # 3. Max holding
            elif (i - entry_idx) >= max_hold:
                exit_px     = candle_close
                exit_reason = "max_hold_exit"
            # 4. Regime exit (for strategies that respect regime)
            elif not ignore_regime and not risk_on:
                exit_px     = candle_close
                exit_reason = "risk_off_exit"
            # 5. Signal exit
            elif exit_signal(row, strategy=strategy_name):
                exit_px     = candle_close
                exit_reason = "signal_exit"

            if exit_px is not None:
                proceeds = qty * exit_px * (1 - FEE_RATE)
                cost     = qty * entry_px * (1 + FEE_RATE)
                pnl      = proceeds - cost
                pnl_pct  = pnl / cost
                equity  += pnl
                trades.append({
                    "entry_time":  df.iloc[entry_idx]["timestamp"],
                    "exit_time":   row["timestamp"],
                    "entry_px":    entry_px,
                    "exit_px":     exit_px,
                    "pnl":         pnl,
                    "pnl_pct":     pnl_pct,
                    "exit_reason": exit_reason,
                    "hold_candles": i - entry_idx,
                })
                position = None

        # ── Entry check ───────────────────────────────────────────────────────
        if position is None:
            regime_ok = risk_on or ignore_regime
            if regime_ok and entry_signal(row, prev_row, strategy=strategy_name):
                entry_px  = row["close"]
                risk_amt  = equity * risk_per_trade
                stop_px   = entry_px * (1 - sl_pct)
                tp_px     = entry_px * (1 + tp_pct)
                # Size based on risk: risk_amt = qty * (entry - stop)
                risk_per_unit = entry_px - stop_px
                if risk_per_unit <= 0:
                    continue
                qty = risk_amt / risk_per_unit
                cost = qty * entry_px * (1 + FEE_RATE)
                if cost > equity * 0.95:  # cap at 95% of equity
                    qty  = (equity * 0.95) / (entry_px * (1 + FEE_RATE))
                    cost = qty * entry_px * (1 + FEE_RATE)
                position = {
                    "entry_px":  entry_px,
                    "stop_px":   stop_px,
                    "tp_px":     tp_px,
                    "qty":       qty,
                    "entry_idx": i,
                }

        equity_curve.append(equity)

    # Force-close any open position at last candle
    if position is not None:
        last = df.iloc[-1]
        exit_px = last["close"]
        proceeds = position["qty"] * exit_px * (1 - FEE_RATE)
        cost     = position["qty"] * position["entry_px"] * (1 + FEE_RATE)
        pnl      = proceeds - cost
        equity  += pnl
        trades.append({
            "entry_time":  df.iloc[position["entry_idx"]]["timestamp"],
            "exit_time":   last["timestamp"],
            "entry_px":    position["entry_px"],
            "exit_px":     exit_px,
            "pnl":         pnl,
            "pnl_pct":     pnl / cost,
            "exit_reason": "end_of_data",
            "hold_candles": len(df) - 1 - position["entry_idx"],
        })

    if not trades:
        return {"trades": 0, "win_rate": 0, "total_return_pct": 0,
                "annual_return_pct": 0, "max_drawdown_pct": 0,
                "profit_factor": 0, "avg_hold_candles": 0,
                "trades_per_month": 0, "sharpe": 0, "trade_list": []}

    tdf        = pd.DataFrame(trades)
    n_trades   = len(tdf)
    wins       = tdf[tdf["pnl"] > 0]
    losses     = tdf[tdf["pnl"] <= 0]
    win_rate   = len(wins) / n_trades if n_trades else 0
    gross_profit = wins["pnl"].sum() if len(wins) else 0
    gross_loss   = abs(losses["pnl"].sum()) if len(losses) else 1e-9
    profit_factor = gross_profit / gross_loss

    total_return_pct = (equity - INITIAL_CAP) / INITIAL_CAP * 100
    years = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).days / 365.25
    months = years * 12
    annual_return_pct = ((equity / INITIAL_CAP) ** (1 / max(years, 0.1)) - 1) * 100
    trades_per_month  = n_trades / max(months, 1)

    # Max drawdown on equity curve
    eq_arr   = np.array(equity_curve)
    peak     = np.maximum.accumulate(eq_arr)
    drawdown = (eq_arr - peak) / peak
    max_dd   = drawdown.min() * 100

    # Sharpe (daily returns approximation)
    returns  = tdf["pnl_pct"].values
    sharpe   = (returns.mean() / (returns.std() + 1e-9)) * np.sqrt(trades_per_month * 12) if n_trades > 1 else 0

    return {
        "trades":             n_trades,
        "win_rate":           win_rate * 100,
        "total_return_pct":   total_return_pct,
        "annual_return_pct":  annual_return_pct,
        "max_drawdown_pct":   max_dd,
        "profit_factor":      profit_factor,
        "avg_hold_candles":   tdf["hold_candles"].mean(),
        "trades_per_month":   trades_per_month,
        "sharpe":             sharpe,
        "exit_reasons":       tdf["exit_reason"].value_counts().to_dict(),
        "trade_list":         trades,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    exchange = ccxt.binance({"enableRateLimit": True})
    since_ms = int(pd.Timestamp(START_DATE, tz="UTC").timestamp() * 1000)
    until_ms = int(pd.Timestamp(END_DATE,   tz="UTC").timestamp() * 1000)

    print(f"\n{'='*70}")
    print(f"  BACKTEST: 3 Strategies | {START_DATE} → {END_DATE}")
    print(f"  Pairs: {', '.join(SYMBOLS)}")
    print(f"  Capital: ${INITIAL_CAP:,.0f} | Fee: {FEE_RATE*100:.1f}% per side")
    print(f"{'='*70}\n")

    # Fetch data for all symbols once
    data_4h = {}
    data_1d = {}
    for sym in SYMBOLS:
        print(f"Fetching {sym} 4h candles ...")
        data_4h[sym] = fetch_ohlcv(exchange, sym, "4h", since_ms, until_ms)
        print(f"  → {len(data_4h[sym])} candles")
        print(f"Fetching {sym} 1d candles ...")
        data_1d[sym] = fetch_ohlcv(exchange, sym, "1d", since_ms, until_ms)
        print(f"  → {len(data_1d[sym])} candles")

    print("\nComputing indicators (this may take a minute) ...")
    ind_4h = {}
    for sym in SYMBOLS:
        if data_4h[sym].empty:
            print(f"  [skip] {sym}: no 4h data")
            continue
        try:
            ind_4h[sym] = compute_4h_indicators(data_4h[sym])
            print(f"  {sym}: {len(ind_4h[sym])} indicator rows")
        except Exception as e:
            print(f"  [error] {sym} indicators: {e}")

    # Results table
    all_results = {}
    for strategy_name, scfg in STRATEGIES.items():
        all_results[strategy_name] = {}
        print(f"\n{'─'*70}")
        print(f"  Strategy: {strategy_name}")
        print(f"{'─'*70}")
        for sym in SYMBOLS:
            if sym not in ind_4h or data_1d[sym].empty:
                print(f"  {sym}: skipped (no data)")
                continue
            try:
                res = run_backtest(ind_4h[sym].copy(), data_1d[sym].copy(), strategy_name, scfg)
                all_results[strategy_name][sym] = res
                print(
                    f"  {sym:10s} | trades={res['trades']:4d} | "
                    f"win={res['win_rate']:5.1f}% | "
                    f"ann={res['annual_return_pct']:+7.1f}% | "
                    f"dd={res['max_drawdown_pct']:6.1f}% | "
                    f"PF={res['profit_factor']:.2f} | "
                    f"{res['trades_per_month']:.1f}t/mo | "
                    f"Sharpe={res['sharpe']:.2f}"
                )
                if res.get("exit_reasons"):
                    reasons = ", ".join(f"{k}:{v}" for k,v in res["exit_reasons"].items())
                    print(f"  {'':10s}   exits: {reasons}")
            except Exception as e:
                print(f"  {sym}: ERROR — {e}")
                import traceback; traceback.print_exc()

    # Summary table
    print(f"\n\n{'='*70}")
    print("  SUMMARY — Averaged across all pairs")
    print(f"{'='*70}")
    print(f"  {'Strategy':<28} {'Trades/mo':>9} {'Win%':>6} {'Ann Ret%':>9} {'MaxDD%':>7} {'PF':>5} {'Sharpe':>7}")
    print(f"  {'-'*68}")
    for sname, sym_results in all_results.items():
        if not sym_results:
            continue
        vals = list(sym_results.values())
        avg = lambda k: np.mean([v[k] for v in vals])
        print(
            f"  {sname:<28} "
            f"{avg('trades_per_month'):>9.1f} "
            f"{avg('win_rate'):>6.1f} "
            f"{avg('annual_return_pct'):>+9.1f} "
            f"{avg('max_drawdown_pct'):>7.1f} "
            f"{avg('profit_factor'):>5.2f} "
            f"{avg('sharpe'):>7.2f}"
        )
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
