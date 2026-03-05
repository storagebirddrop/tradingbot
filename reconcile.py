import csv
import os
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

import ccxt

@dataclass
class SymbolPnL:
    inv_qty: float = 0.0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0

def _ensure_csv(path: str, header: List[str]) -> None:
    if os.path.exists(path):
        return
    with open(path, "w", newline="") as f:
        csv.writer(f).writerow(header)

def _append_csv(path: str, row: List[Any]) -> None:
    with open(path, "a", newline="") as f:
        csv.writer(f).writerow(row)

def fee_to_usdt(trade: dict) -> float:
    fee = trade.get("fee") or {}
    fee_cost = float(fee.get("cost") or 0.0)
    fee_ccy = fee.get("currency")
    if fee_cost == 0.0 or not fee_ccy:
        return 0.0

    symbol = trade.get("symbol") or ""
    base = quote = None
    if "/" in symbol:
        base, quote = symbol.split("/", 1)

    price = float(trade.get("price") or 0.0)

    if fee_ccy == "USDT":
        return fee_cost
    if quote and fee_ccy == quote:
        return fee_cost
    if base and fee_ccy == base and price > 0:
        return fee_cost * price

    return 0.0

def process_trade(pnl: SymbolPnL, trade: dict) -> Tuple[SymbolPnL, float]:
    side = (trade.get("side") or "").lower()
    amount = float(trade.get("amount") or 0.0)
    price = float(trade.get("price") or 0.0)
    cost = trade.get("cost")

    notional = float(cost) if cost is not None else (price * amount)
    fee_usdt = fee_to_usdt(trade)

    realized_delta = 0.0

    if side == "buy":
        total_cost = pnl.avg_cost * pnl.inv_qty + notional + fee_usdt
        new_qty = pnl.inv_qty + amount
        if new_qty > 0:
            pnl.avg_cost = total_cost / new_qty
            pnl.inv_qty = new_qty
        else:
            pnl.avg_cost = 0.0
            pnl.inv_qty = 0.0

    elif side == "sell":
        proceeds = notional - fee_usdt
        realized_delta = proceeds - (amount * pnl.avg_cost)
        pnl.realized_pnl += realized_delta
        pnl.inv_qty -= amount

        if pnl.inv_qty < 0 and abs(pnl.inv_qty) < 1e-12:
            pnl.inv_qty = 0.0
        if pnl.inv_qty <= 0:
            pnl.inv_qty = 0.0
            pnl.avg_cost = 0.0

    return pnl, realized_delta

def fetch_new_trades(ex: ccxt.Exchange, symbols: List[str], since_ms: Optional[int], limit: int = 200) -> List[dict]:
    if not ex.has.get("fetchMyTrades", False):
        return []

    trades: List[dict] = []
    try:
        batch = ex.fetch_my_trades(None, since=since_ms, limit=limit)
        if batch:
            trades.extend(batch)
            return trades
    except Exception:
        pass

    for s in symbols:
        try:
            batch = ex.fetch_my_trades(s, since=since_ms, limit=limit)
            if batch:
                trades.extend(batch)
        except Exception:
            continue

    return trades

def reconcile_fills(ex: ccxt.Exchange, symbols: List[str], state: dict, fills_log_path: str) -> dict:
    _ensure_csv(fills_log_path, [
        "timestamp","datetime","trade_id","order_id","symbol","side","amount","price","cost",
        "fee_cost","fee_currency","fee_usdt","realized_delta_usdt"
    ])

    since_ms = state.get("since_ms")
    by_symbol = state.get("by_symbol") or {}

    pnl_map: Dict[str, SymbolPnL] = {}
    for s in symbols:
        ps = by_symbol.get(s) or {}
        pnl_map[s] = SymbolPnL(
            inv_qty=float(ps.get("inv_qty") or 0.0),
            avg_cost=float(ps.get("avg_cost") or 0.0),
            realized_pnl=float(ps.get("realized_pnl") or 0.0),
        )

    trades = fetch_new_trades(ex, symbols, since_ms, limit=200)
    if not trades:
        state["by_symbol"] = {s: pnl_map[s].__dict__ for s in symbols}
        return state

    trades_sorted = sorted(trades, key=lambda t: (t.get("timestamp") or 0, t.get("id") or ""))
    seen = set(state.get("seen_trade_ids") or [])

    max_ts = since_ms or 0
    for t in trades_sorted:
        tid = t.get("id") or ""
        sym = t.get("symbol")
        ts = int(t.get("timestamp") or 0)
        if not sym or sym not in pnl_map or not ts:
            continue
        if tid and tid in seen:
            continue

        fee = t.get("fee") or {}
        fee_cost = float(fee.get("cost") or 0.0)
        fee_ccy = fee.get("currency") or ""
        fee_usdt = fee_to_usdt(t)

        pnl_map[sym], realized_delta = process_trade(pnl_map[sym], t)

        _append_csv(fills_log_path, [
            ts,
            t.get("datetime") or "",
            tid,
            t.get("order") or "",
            sym,
            t.get("side") or "",
            float(t.get("amount") or 0.0),
            float(t.get("price") or 0.0),
            float(t.get("cost") or (float(t.get("price") or 0.0) * float(t.get("amount") or 0.0))),
            fee_cost,
            fee_ccy,
            fee_usdt,
            realized_delta
        ])

        if tid:
            seen.add(tid)
        if ts > max_ts:
            max_ts = ts

    state["since_ms"] = int(max_ts + 1)
    state["seen_trade_ids"] = list(seen)[-5000:]
    state["by_symbol"] = {s: pnl_map[s].__dict__ for s in symbols}
    return state

def pnl_totals(state: dict, price_map: Dict[str, float]) -> Tuple[float, float, Dict[str, float]]:
    by_symbol = state.get("by_symbol") or {}
    realized_total = 0.0
    unreal_total = 0.0
    realized_by_symbol: Dict[str, float] = {}

    for sym, ps in by_symbol.items():
        inv_qty = float(ps.get("inv_qty") or 0.0)
        avg_cost = float(ps.get("avg_cost") or 0.0)
        realized = float(ps.get("realized_pnl") or 0.0)
        realized_total += realized
        realized_by_symbol[sym] = realized

        px = price_map.get(sym)
        if px is not None and inv_qty > 0:
            unreal_total += inv_qty * (float(px) - avg_cost)

    return realized_total, unreal_total, realized_by_symbol
