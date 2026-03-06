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
from datetime import datetime, timezone

import pandas as pd
import ccxt

try:
    import requests as _requests
except ImportError:
    _requests = None

_HERE    = os.path.dirname(os.path.abspath(__file__))
_ROOT    = os.path.dirname(_HERE)
DATA_DIR = os.path.join(_ROOT, "data")

DEFAULT_SYMBOLS = ["ETH", "SOL", "TRX", "ADA", "VTHO", "BAT", "LTC", "RUNE"]

LIMITS = {
    "4h": 35000,  # ≈9 years; actual depth capped by exchange availability
    "1d": 4000,   # ≈11 years
}


def _make_exchange(name: str) -> ccxt.Exchange:
    if name == "binance":
        return ccxt.binance({"enableRateLimit": True})
    return ccxt.phemex({"enableRateLimit": True})


def fetch_ohlcv_paginated(exchange: ccxt.Exchange, symbol: str, timeframe: str,
                           total_bars: int, batch: int = 1000,
                           since_ms: int = None) -> pd.DataFrame:
    """
    Fetch up to `total_bars` of OHLCV via paginated requests (walks forwards in time from `since`).
    Respects Binance's 1000-bar-per-request limit. Deduplicates and sorts ascending.

    If `since_ms` is provided it is used as the start epoch directly, overriding the
    `now - total_bars * tf_ms` calculation (useful for fixed start-date fetches).
    """
    all_rows = []
    tf_ms = {
        "4h": 4 * 3600 * 1000,
        "1h": 3600 * 1000,
        "1d": 86400 * 1000,
    }.get(timeframe, 3600 * 1000)
    since = since_ms if since_ms is not None else int(time.time() * 1000) - total_bars * tf_ms

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


_TF_TO_COINAPI = {"4h": "4HRS", "1d": "1DAY"}
_TF_TO_CC      = {"4h": "histohour", "1d": "histoday"}
_TF_AGG        = {"4h": 4, "1d": 1}   # CryptoCompare aggregate multiplier


def _ohlcv_from_rows(rows: list, ts_col: str = "timestamp") -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    return df.drop_duplicates(ts_col).sort_values(ts_col).reset_index(drop=True)


def fetch_ohlcv_coinapi(symbol: str, timeframe: str,
                         since_ms: int, api_key: str) -> pd.DataFrame:
    """
    Fetch OHLCV from CoinAPI REST (free tier: 100 req/day, 1 yr history on free plan).
    symbol e.g. 'ETH', timeframe '4h' or '1d'.
    Returns DataFrame with columns: timestamp, open, high, low, close, volume.
    """
    if _requests is None:
        return pd.DataFrame()
    period = _TF_TO_COINAPI.get(timeframe)
    if period is None:
        return pd.DataFrame()
    start = datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    url = (f"https://rest.coinapi.io/v1/ohlcv/BINANCE_SPOT_{symbol}_USDT/history"
           f"?period_id={period}&time_start={start}&limit=100000")
    headers = {"X-CoinAPI-Key": api_key}
    rows = []
    try:
        r = _requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        for bar in r.json():
            rows.append({
                "timestamp": bar["time_period_start"],
                "open": bar["price_open"], "high": bar["price_high"],
                "low": bar["price_low"],  "close": bar["price_close"],
                "volume": bar["volume_traded"],
            })
    except Exception as e:
        print(f"    CoinAPI error: {e}")
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    return _ohlcv_from_rows(rows)


def fetch_ohlcv_cryptocompare(symbol: str, timeframe: str,
                               since_ms: int, api_key: str = "") -> pd.DataFrame:
    """
    Fetch OHLCV from CryptoCompare (free, 2000 bars/request, paginated).
    symbol e.g. 'ETH', timeframe '4h' or '1d'.
    """
    if _requests is None:
        return pd.DataFrame()
    endpoint = _TF_TO_CC.get(timeframe)
    agg      = _TF_AGG.get(timeframe, 1)
    if endpoint is None:
        return pd.DataFrame()
    tf_sec = 3600 * agg if timeframe == "4h" else 86400
    all_rows = []
    toTs = int(time.time())
    since_s = since_ms // 1000
    headers = {"authorization": f"Apikey {api_key}"} if api_key else {}
    while True:
        params = {"fsym": symbol, "tsym": "USDT", "aggregate": agg,
                  "limit": 2000, "toTs": toTs, "e": "Binance"}
        try:
            r = _requests.get(f"https://min-api.cryptocompare.com/data/{endpoint}",
                              params=params, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json().get("Data", [])
        except Exception as e:
            print(f"    CryptoCompare error: {e}")
            break
        if not data:
            break
        page_rows = []
        for bar in data:
            if bar["time"] < since_s:
                continue
            page_rows.append({
                "timestamp": pd.Timestamp(bar["time"], unit="s", tz="UTC"),
                "open": bar["open"], "high": bar["high"],
                "low": bar["low"],   "close": bar["close"],
                "volume": bar["volumeto"],
            })
        all_rows = page_rows + all_rows
        earliest = data[0]["time"]
        if earliest <= since_s:
            break
        toTs = earliest - tf_sec
        time.sleep(0.2)
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def fetch_symbol(base: str, exchange_name: str, force: bool, since_ms: int = None) -> dict:
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
                df_b = fetch_ohlcv_paginated(ex_b, symbol, tf, total_bars=limit, since_ms=since_ms)
                if len(df_b) > len(df):
                    df = df_b
                    print(f"  [{base}/{tf}] Binance returned {len(df)} bars")
            except Exception as e2:
                print(f"  [{base}/{tf}] Binance fallback error: {e2}")

        # Fallback 2: CryptoCompare (free, no key needed for Binance data)
        if len(df) < limit * 0.8 and since_ms is not None:
            print(f"  [{base}/{tf}] Trying CryptoCompare fallback...")
            try:
                cc_key = os.environ.get("CRYPTOCOMPARE_API_KEY", "")
                df_cc = fetch_ohlcv_cryptocompare(base, tf, since_ms, api_key=cc_key)
                if len(df_cc) > len(df):
                    df = df_cc
                    print(f"  [{base}/{tf}] CryptoCompare returned {len(df)} bars")
            except Exception as e3:
                print(f"  [{base}/{tf}] CryptoCompare error: {e3}")

        # Fallback 3: CoinAPI (requires COINAPI_KEY env var)
        coinapi_key = os.environ.get("COINAPI_KEY", "")
        if len(df) < limit * 0.8 and since_ms is not None and coinapi_key:
            print(f"  [{base}/{tf}] Trying CoinAPI fallback...")
            try:
                df_ca = fetch_ohlcv_coinapi(base, tf, since_ms, api_key=coinapi_key)
                if len(df_ca) > len(df):
                    df = df_ca
                    print(f"  [{base}/{tf}] CoinAPI returned {len(df)} bars")
            except Exception as e4:
                print(f"  [{base}/{tf}] CoinAPI error: {e4}")

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
    parser.add_argument("--since",    default=None, metavar="YYYY-MM-DD",
                        help="Fetch from this UTC date. Overrides LIMITS lookback window.")
    args = parser.parse_args()

    since_ms = None
    if args.since:
        since_ms = int(pd.Timestamp(args.since, tz="UTC").timestamp() * 1000)
        print(f"Fetching from {args.since} (epoch {since_ms})")

    print(f"Fetching data from {args.exchange} for: {args.symbols}")
    print(f"Output dir: {DATA_DIR}\n")

    total_written = 0
    for base in args.symbols:
        print(f"--- {base}/USDT ---")
        written = fetch_symbol(base, args.exchange, args.force, since_ms=since_ms)
        total_written += len(written)

    print(f"\nDone. {total_written} file(s) written/verified in {DATA_DIR}/")
    print("\nNext step:")
    print("  python3 research/compare_enhancements.py --symbols ETH SOL TRX --strategy obv_breakout --wfo")


if __name__ == "__main__":
    main()
