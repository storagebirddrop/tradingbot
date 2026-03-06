"""
Historical OHLCV data fetcher for backtest validation.

Downloads 4h and 1d candles for all bot symbols and saves them as CSV files
in the data/ directory. Uses the Phemex public API (no credentials needed)
with an automatic fallback to Binance for any symbol that returns no data.

Usage:
    python3 research/fetch_data.py
    python3 research/fetch_data.py --symbols ETH SOL TRX
    python3 research/fetch_data.py --force          # re-download even if file exists
    python3 research/fetch_data.py --exchange binance

Output files (relative to project root):
    data/ETH_4h.csv, data/ETH_1d.csv
    data/SOL_4h.csv, data/SOL_1d.csv
    ... etc.
"""

import os
import sys
import time
import argparse

import pandas as pd
import ccxt

_HERE    = os.path.dirname(os.path.abspath(__file__))
_ROOT    = os.path.dirname(_HERE)
DATA_DIR = os.path.join(_ROOT, "data")

DEFAULT_SYMBOLS = ["ETH", "SOL", "TRX", "ADA", "VTHO", "BAT", "LTC", "RUNE"]

LIMITS = {
    "4h": 2000,   # ≈333 days
    "1d": 800,    # ≈2.2 years
}


def _make_exchange(name: str) -> ccxt.Exchange:
    if name == "binance":
        return ccxt.binance({"enableRateLimit": True})
    return ccxt.phemex({"enableRateLimit": True})


def fetch_ohlcv_paginated(exchange: ccxt.Exchange, symbol: str, timeframe: str,
                           total_bars: int, batch: int = 1000) -> pd.DataFrame:
    """
    Fetch up to `total_bars` of OHLCV via paginated requests (walks forwards in time from `since`).
    Respects Binance's 1000-bar-per-request limit. Deduplicates and sorts ascending.
    """
    all_rows = []
    # Calculate `since` for total_bars ago and walk forwards
    tf_ms = {
        "4h": 4 * 3600 * 1000,
        "1h": 3600 * 1000,
        "1d": 86400 * 1000,
    }.get(timeframe, 3600 * 1000)
    since = int(time.time() * 1000) - total_bars * tf_ms

    remaining = total_bars
    cursor = since
    while remaining > 0:
        fetch_limit = min(batch, remaining)
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe,
                                          since=cursor, limit=fetch_limit)
        except Exception as e:
            print(f"    Paginated fetch error (will stop): {e}")
            break
        if not ohlcv:
            break
        all_rows.extend(ohlcv)
        last_ts = ohlcv[-1][0]
        cursor = last_ts + tf_ms
        remaining -= len(ohlcv)
        if len(ohlcv) < fetch_limit:
            break  # reached end of available data
        time.sleep(0.25)

    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def fetch_symbol(base: str, exchange_name: str, force: bool) -> dict:
    """Fetch 4h and 1d data for one base symbol. Returns {tf: path} for files written."""
    os.makedirs(DATA_DIR, exist_ok=True)
    symbol = f"{base}/USDT"
    written = {}

    for tf, limit in LIMITS.items():
        out_path = os.path.join(DATA_DIR, f"{base}_{tf}.csv")
        if os.path.exists(out_path) and not force:
            with open(out_path, 'r', encoding='utf-8') as f:
                rows = sum(1 for _ in f) - 1
            print(f"  [{base}/{tf}] Skipping — file exists ({rows} rows). Use --force to re-download.")
            written[tf] = out_path
            continue

        df = pd.DataFrame()

        # Try primary exchange first (non-paginated, quick)
        ex = _make_exchange(exchange_name)
        try:
            ex.load_markets()
            ohlcv = ex.fetch_ohlcv(symbol, timeframe=tf, limit=min(limit, 1000))
            if ohlcv:
                df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
        except Exception as e:
            print(f"  [{base}/{tf}] {exchange_name} error: {e}")

        # Use Binance for paginated bulk fetch if we need more bars
        if len(df) < limit * 0.8:
            src = "Binance (paginated)" if exchange_name != "binance" else "Binance (paginated)"
            if exchange_name != "binance" and not df.empty:
                print(f"  [{base}/{tf}] Only {len(df)} bars from {exchange_name}, fetching more from Binance...")
            elif df.empty:
                print(f"  [{base}/{tf}] Falling back to Binance (paginated)...")
            try:
                ex_b = _make_exchange("binance")
                ex_b.load_markets()
                df_b = fetch_ohlcv_paginated(ex_b, symbol, tf, total_bars=limit)
                if len(df_b) > len(df):
                    df = df_b
                    print(f"  [{base}/{tf}] Binance returned {len(df)} bars")
            except Exception as e2:
                print(f"  [{base}/{tf}] Binance fallback error: {e2}")

        if df.empty:
            print(f"  [{base}/{tf}] ERROR: No data returned. Skipping.")
            continue

        df.to_csv(out_path, index=False)
        print(f"  [{base}/{tf}] Saved {len(df)} bars ({df['timestamp'].min().date()} → {df['timestamp'].max().date()}) → {out_path}")
        written[tf] = out_path
        time.sleep(0.3)

    return written


def main():
    parser = argparse.ArgumentParser(description="Fetch historical OHLCV for backtest")
    parser.add_argument("--symbols",  nargs="+", default=DEFAULT_SYMBOLS,
                        help="Base symbols to fetch (default: all 8 bot symbols)")
    parser.add_argument("--exchange", default="phemex", choices=["phemex", "binance"],
                        help="Primary exchange to fetch from (default: phemex)")
    parser.add_argument("--force",    action="store_true",
                        help="Re-download even if CSV already exists")
    args = parser.parse_args()

    print(f"Fetching data from {args.exchange} for: {args.symbols}")
    print(f"Output dir: {DATA_DIR}\n")

    total_written = 0
    for base in args.symbols:
        print(f"--- {base}/USDT ---")
        written = fetch_symbol(base, args.exchange, args.force)
        total_written += len(written)

    print(f"\nDone. {total_written} file(s) written/verified in {DATA_DIR}/")
    print("\nNext step:")
    print("  python3 research/compare_enhancements.py --symbols ETH SOL TRX --strategy obv_breakout --wfo")


if __name__ == "__main__":
    main()
