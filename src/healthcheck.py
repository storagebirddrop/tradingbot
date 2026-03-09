#!/usr/bin/env python3
"""
healthcheck.py
Quick operator health check for the bot.

What it does:
- Reads profile config from config.json
- Reads runtime state (daily kill switch + API kill switch + cooldowns)
- Reads broker state (open positions + stop order ids)
- Reads fills state/log (last fill time + realized PnL snapshot) when present
- Prints a concise status summary and exits with a useful code:
    0 = OK
    1 = WARN (kill switches active or stale)
    2 = ERROR (state files missing or inconsistent)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd

from .brokers import load_json


def _load_profile(config_path: str, profile: str) -> Dict[str, Any]:
    with open(config_path, "r") as f:
        cfg = json.load(f)
    prof = (cfg.get("profiles") or {}).get(profile)
    if not prof:
        raise SystemExit(f"Profile not found: {profile}")
    return prof


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_ts(ts: Optional[float]) -> str:
    if not ts or ts == 0.0:
        return "n/a"
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _last_line_time_csv(path: str, time_col: str) -> Optional[datetime]:
    if not path or not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        if df.empty or time_col not in df.columns:
            return None
        t = pd.to_datetime(df[time_col], utc=True, errors="coerce").dropna()
        if t.empty:
            return None
        return t.iloc[-1].to_pydatetime()
    except Exception:
        return None


def _last_fill_time_from_fills_csv(path: str) -> Optional[datetime]:
    if not path or not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        if df.empty:
            return None
        if "datetime" in df.columns:
            t = pd.to_datetime(df["datetime"], utc=True, errors="coerce").dropna()
            if not t.empty:
                return t.iloc[-1].to_pydatetime()
        if "timestamp" in df.columns:
            ts = pd.to_numeric(df["timestamp"], errors="coerce").dropna()
            if not ts.empty:
                # Detect timestamp unit using digit count heuristics
                last_ts = float(ts.iloc[-1])
                # Treat values > 1e12 as milliseconds (13+ digits)
                # Treat values <= 1e10 as seconds (10 or fewer digits)  
                # Handle 11-12 digit range conservatively as milliseconds
                if last_ts > 1e12:  # 13+ digits = milliseconds
                    return datetime.fromtimestamp(last_ts / 1000.0, tz=timezone.utc)
                elif last_ts <= 1e10:  # 10 or fewer digits = seconds
                    return datetime.fromtimestamp(last_ts, tz=timezone.utc)
                else:  # 11-12 digits, treat as milliseconds conservatively
                    return datetime.fromtimestamp(last_ts / 1000.0, tz=timezone.utc)
    except Exception:
        return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json", help="Path to config.json")
    ap.add_argument("--profile", required=True, choices=["local_paper", "phemex_testnet", "phemex_live"])
    ap.add_argument("--stale-seconds", type=int, default=900,
                    help="WARN if no equity snapshot in this many seconds (default 900=15m).")
    ap.add_argument("--fills-stale-seconds", type=int, default=86400,
                    help="WARN if no fills in this many seconds (exchange profiles only; default 1d).")
    args = ap.parse_args()

    prof = _load_profile(args.config, args.profile)
    now = _utcnow()

    state_file = prof.get("state_file")
    runtime_state_file = prof.get("runtime_state_file")
    equity_log = prof.get("equity_log")
    trade_log = prof.get("trade_log")

    fills_log = prof.get("fills_log")
    fills_state_file = prof.get("fills_state_file")

    state = load_json(state_file) or {}
    rt = load_json(runtime_state_file) or {}

    exit_code = 0
    problems = []

    mode = prof.get("mode")
    env = prof.get("exchange_env")
    dry_run = prof.get("dry_run", True)

    positions = (state.get("positions") or {}) if isinstance(state, dict) else {}
    num_positions = len(positions)

    daily_kill = bool(rt.get("kill_switch", False))
    day_start_equity = rt.get("day_start_equity")
    day = rt.get("day")

    api_kill_until = _safe_float(rt.get("api_kill_until_ts", 0.0), 0.0)
    api_kill_active = now.timestamp() < api_kill_until

    last_equity_time = _last_line_time_csv(equity_log, "time_utc")
    equity_age = None
    if last_equity_time:
        equity_age = (now - last_equity_time).total_seconds()

    if last_equity_time is None:
        problems.append(f"Missing or unreadable equity log: {equity_log}")
        exit_code = max(exit_code, 2)
    elif equity_age is not None and equity_age > args.stale_seconds:
        problems.append(f"Equity log stale: last snapshot {int(equity_age)}s ago")
        exit_code = max(exit_code, 1)

    last_fill_time = None
    fills_age = None
    realized_total = None

    if mode == "exchange":
        last_fill_time = _last_fill_time_from_fills_csv(fills_log)
        if last_fill_time:
            fills_age = (now - last_fill_time).total_seconds()
            if fills_age > args.fills_stale_seconds:
                problems.append(f"Fills stale: last fill {int(fills_age)}s ago (may be normal if no trades)")
                exit_code = max(exit_code, 1)
        else:
            problems.append("No fills observed yet (fills_log missing/empty) — OK if no trades placed.")
            exit_code = max(exit_code, 1)

        fills_state = load_json(fills_state_file) or {}
        by_symbol = (fills_state.get("by_symbol") or {}) if isinstance(fills_state, dict) else {}
        try:
            realized_total = sum(float(v.get("realized_pnl") or 0.0) for v in by_symbol.values())
        except Exception:
            realized_total = None

    if daily_kill:
        problems.append("DAILY_KILL_SWITCH is ON (new entries blocked until next UTC day).")
        exit_code = max(exit_code, 1)

    if api_kill_active:
        problems.append(f"API_KILL_SWITCH is ON until {_fmt_ts(api_kill_until)} (all trading actions halted).")
        exit_code = max(exit_code, 1)

    if mode == "exchange" and bool(prof.get("hard_stops", False)) and num_positions > 0:
        missing_stops = []
        for sym, p in positions.items():
            if not isinstance(p, dict):
                continue
            if not p.get("stop_order_id"):
                missing_stops.append(sym)
        if missing_stops:
            problems.append(f"Open positions missing stop_order_id (hard stop may not be set): {missing_stops}")
            exit_code = max(exit_code, 1)

    print("=== BOT HEALTHCHECK ===")
    print(f"Profile          : {args.profile}")
    print(f"Mode             : {mode}   Env: {env}   Dry-run: {dry_run}")
    print(f"Now (UTC)        : {now.isoformat()}")

    print("\n--- Switches ---")
    print(f"Daily kill       : {daily_kill}   (day={day}, day_start_equity={day_start_equity})")
    print(f"API kill         : {api_kill_active}   (until={_fmt_ts(api_kill_until)})")

    print("\n--- Positions ---")
    print(f"Open positions   : {num_positions}")
    if num_positions:
        for sym, p in positions.items():
            if isinstance(p, dict):
                print(f"  - {sym}: qty={p.get('qty')} entry={p.get('entry_px')} stop={p.get('stop_px')} stop_order_id={p.get('stop_order_id')}")
            else:
                print(f"  - {sym}: {p}")

    print("\n--- Logs ---")
    print(f"Trade log        : {trade_log}   ({'exists' if trade_log and os.path.exists(trade_log) else 'missing'})")
    if last_equity_time:
        print(f"Equity log       : {equity_log}   last={last_equity_time.isoformat()} age={int(equity_age)}s")
    else:
        print(f"Equity log       : {equity_log}   last=n/a")

    if mode == "exchange":
        if last_fill_time:
            print(f"Fills log        : {fills_log}   last={last_fill_time.isoformat()} age={int(fills_age)}s")
        else:
            print(f"Fills log        : {fills_log}   last=n/a")
        if realized_total is not None:
            print(f"Realized PnL     : {realized_total:+.6f} USDT (from fills_state)")
        else:
            print("Realized PnL     : n/a")

    print("\n--- Findings ---")
    if problems:
        for p in problems:
            print(f"- {p}")
    else:
        print("No issues detected.")

    print(f"\nExit code        : {exit_code}  (0=OK, 1=WARN, 2=ERROR)")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
