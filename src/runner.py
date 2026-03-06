import time, json, os, logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional

from strategy import timeframe_seconds, entry_signal, exit_signal
from brokers import get_latest_signal_rows, get_current_tf_open_ts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def utc_day_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()

def load_runtime_state(path: str) -> dict:
    if not path or not os.path.exists(path):
        logger.info(f"Runtime state file not found: {path}, using empty state")
        return {}
    try:
        with open(path, "r") as f:
            state = json.load(f)
            logger.info(f"Loaded runtime state from {path}")
            return state
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in runtime state file {path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load runtime state from {path}: {e}")
        return {}

def save_runtime_state(path: str, state: dict) -> None:
    if not path:
        logger.warning("Cannot save runtime state: no path provided")
        return
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
        logger.debug(f"Saved runtime state to {path}")
    except Exception as e:
        logger.error(f"Failed to save runtime state to {path}: {e}")

# Constants
COOLDOWN_RESET_VALUE = -10**18  # Far past timestamp to reset cooldowns

def run_loop(cfg: dict, broker, market_exchange):
    logger.info(f"Starting bot loop with {len(cfg['symbols'])} symbols")
    tf_sec = timeframe_seconds(cfg["signal_timeframe"])
    last_tf_open: Dict[str, Optional[int]] = {s: None for s in cfg["symbols"]}
    cooldown_until: Dict[str, int] = {s: COOLDOWN_RESET_VALUE for s in cfg["symbols"]}

    runtime_path = cfg.get("runtime_state_file", "")
    rt = load_runtime_state(runtime_path)

    rt.setdefault("day", utc_day_key())
    rt.setdefault("day_start_equity", None)
    rt.setdefault("kill_switch", False)

    rt.setdefault("api_kill_until_ts", 0)
    rt.setdefault("api_err_ts", [])
    rt.setdefault("api_kill_active", False)

    saved_cd = rt.get("cooldown_until") or {}
    for s in cfg["symbols"]:
        if s in saved_cd:
            cooldown_until[s] = int(saved_cd[s])

    for s in cfg["symbols"]:
        last_tf_open[s] = get_current_tf_open_ts(market_exchange, s, cfg["signal_timeframe"])

    api_err_ts = deque(float(x) for x in (rt.get("api_err_ts") or []))

    window_sec = int(cfg.get("api_error_window_sec", 120))
    threshold = int(cfg.get("api_error_threshold", 12))
    cooldown_sec = int(cfg.get("api_kill_cooldown_sec", 300))

    loop = 0

    while True:
        loop += 1
        now = time.time()

        price_map = broker.get_prices(cfg["symbols"])

        new_errs = int(getattr(broker, "pop_api_error_count", lambda: 0)())
        for _ in range(new_errs):
            api_err_ts.append(now)
        while api_err_ts and (now - api_err_ts[0] > window_sec):
            api_err_ts.popleft()

        api_kill_until = float(rt.get("api_kill_until_ts", 0) or 0)
        api_killed = now < api_kill_until

        if (not api_killed) and threshold > 0 and len(api_err_ts) >= threshold:
            rt["api_kill_until_ts"] = now + cooldown_sec
            api_kill_until = rt["api_kill_until_ts"]
            api_killed = True
            api_err_ts.clear()

        if api_killed and (not bool(rt.get("api_kill_active", False))):
            rt["api_kill_active"] = True
            until_iso = datetime.fromtimestamp(api_kill_until, tz=timezone.utc).isoformat()
            broker.log_event("API_KILL_ON", f"errors>={threshold} in {window_sec}s; cooldown until {until_iso}")
        if (not api_killed) and bool(rt.get("api_kill_active", False)):
            rt["api_kill_active"] = False
            broker.log_event("API_KILL_OFF", "cooldown ended; trading actions resumed")

        if not api_killed:
            broker.reconcile_fills_if_due(loop, price_map)

        eq_now = None
        try:
            eq_now = broker.equity_usdt(price_map)
            if eq_now is not None:
                logger.debug(f"Current equity: {eq_now:.2f} USDT")
        except Exception as e:
            logger.error(f"Failed to fetch equity: {e}")
            # Continue with None equity - will be handled gracefully

        current_day = utc_day_key()
        if rt.get("day") != current_day:
            rt["day"] = current_day
            rt["day_start_equity"] = eq_now
            rt["kill_switch"] = False
        if rt.get("day_start_equity") is None and eq_now is not None:
            rt["day_start_equity"] = eq_now

        limit_pct = float(cfg.get("daily_loss_limit_pct", 0.0))
        if limit_pct > 0 and eq_now is not None and rt.get("day_start_equity") is not None:
            day_start = float(rt["day_start_equity"])
            threshold_eq = day_start * (1.0 - limit_pct / 100.0)
            if (not rt.get("kill_switch", False)) and (eq_now <= threshold_eq):
                rt["kill_switch"] = True
        kill_switch = bool(rt.get("kill_switch", False))

        if api_killed:
            if loop % int(cfg["equity_log_every_n_loops"]) == 0:
                broker.snapshot_equity(price_map)
            broker.persist()
            rt["cooldown_until"] = {s: int(cooldown_until[s]) for s in cfg["symbols"]}
            rt["api_err_ts"] = list(api_err_ts)[-5000:]
            save_runtime_state(runtime_path, rt)
            if loop % int(cfg["status_every_n_loops"]) == 0:
                until = datetime.fromtimestamp(api_kill_until, tz=timezone.utc).isoformat()
                print(f"[{datetime.now(timezone.utc).isoformat()}] API_KILL=ON until {until} | POS={list(broker.positions().keys())}")
            time.sleep(int(cfg["poll_seconds"]))
            continue

        removed = broker.sync_positions(price_map)
        for sym in removed:
            cur_open = get_current_tf_open_ts(market_exchange, sym, cfg["signal_timeframe"])
            if cur_open is not None:
                candle_idx = int(cur_open // tf_sec)
                cooldown_until[sym] = candle_idx + int(cfg.get("cooldown_candles", 0))

        default_strategy = cfg.get("strategy", "rsi_momentum_pullback")
        symbol_strategy_map = cfg.get("symbol_strategy", {})

        # trailing updates + take profit (per-symbol strategy aware)
        for sym, pos in list(broker.positions().items()):
            px = price_map.get(sym)
            if px is None:
                continue
            sym_strategy = symbol_strategy_map.get(sym, default_strategy)
            sym_strategy_cfg = cfg.get(sym_strategy, {})
            take_profit_pct = float(sym_strategy_cfg.get("take_profit_pct", 0))
            trail_pct = float(sym_strategy_cfg.get("trail_pct", cfg.get("trail_pct", 0.03)))
            pos.high_water = max(pos.high_water, px)
            trail = pos.high_water * (1 - trail_pct)
            new_stop = max(pos.stop_px, trail)
            if new_stop > pos.stop_px:
                broker.on_stop_updated(sym, pos, new_stop, price_map)
            if (not bool(cfg.get("hard_stops", False))) and (px <= pos.stop_px):
                if broker.sell(sym, px, "stop", price_map):
                    cur_open = get_current_tf_open_ts(market_exchange, sym, cfg["signal_timeframe"])
                    if cur_open is not None:
                        candle_idx = int(cur_open // tf_sec)
                        cooldown_until[sym] = candle_idx + int(cfg.get("cooldown_candles", 0))
                continue
            if take_profit_pct > 0 and px >= pos.entry_px * (1 + take_profit_pct):
                if broker.sell(sym, px, "take_profit", price_map):
                    cur_open = get_current_tf_open_ts(market_exchange, sym, cfg["signal_timeframe"])
                    if cur_open is not None:
                        candle_idx = int(cur_open // tf_sec)
                        cooldown_until[sym] = candle_idx + int(cfg.get("cooldown_candles", 0))
                    continue

        # candle boundary (per-symbol strategy aware)
        for sym in cfg["symbols"]:
            sym_strategy = symbol_strategy_map.get(sym, default_strategy)
            sym_strategy_cfg = cfg.get(sym_strategy, {})
            max_holding = int(sym_strategy_cfg.get("max_holding_periods", 0))
            ignore_regime = bool(sym_strategy_cfg.get("ignore_regime_filter", False))

            current_open = get_current_tf_open_ts(market_exchange, sym, cfg["signal_timeframe"])
            if current_open is None:
                continue
            if last_tf_open.get(sym) is None:
                last_tf_open[sym] = current_open
                continue
            if current_open > last_tf_open[sym]:
                last_tf_open[sym] = current_open
                candle_idx = int(current_open // tf_sec)
                px = price_map.get(sym)
                if px is None:
                    continue
                sig_rows = get_latest_signal_rows(market_exchange, cfg, sym)
                if sig_rows is None:
                    continue
                sig, prev_sig = sig_rows
                risk_on = bool(sig.get("risk_on", False))
                has_pos = sym in broker.positions()

                if has_pos and bool(cfg.get("risk_off_exits", True)) and (not risk_on):
                    if broker.sell(sym, px, "risk_off_exit", price_map):
                        cooldown_until[sym] = candle_idx + int(cfg.get("cooldown_candles", 0))
                    continue

                if has_pos and max_holding > 0:
                    pos = broker.positions()[sym]
                    entry_candle_idx = int(datetime.fromisoformat(pos.entry_time).timestamp() // tf_sec)
                    if candle_idx - entry_candle_idx >= max_holding:
                        if broker.sell(sym, px, "max_hold_exit", price_map):
                            cooldown_until[sym] = candle_idx + int(cfg.get("cooldown_candles", 0))
                        continue

                if has_pos and exit_signal(sig, strategy=sym_strategy):
                    if broker.sell(sym, px, "signal_exit", price_map):
                        cooldown_until[sym] = candle_idx + int(cfg.get("cooldown_candles", 0))
                    continue

                if kill_switch:
                    continue
                if candle_idx < int(cooldown_until.get(sym, -10**18)):
                    continue
                regime_ok = risk_on or ignore_regime
                if (not has_pos) and regime_ok and broker.can_open_new():
                    if entry_signal(sig, prev_sig, strategy=sym_strategy):
                        broker.buy(sym, px, "signal_entry", price_map)

        if loop % int(cfg["equity_log_every_n_loops"]) == 0:
            broker.snapshot_equity(price_map)
        broker.persist()
        rt["cooldown_until"] = {s: int(cooldown_until[s]) for s in cfg["symbols"]}
        rt["api_err_ts"] = list(api_err_ts)[-5000:]
        save_runtime_state(runtime_path, rt)

        if loop % int(cfg["status_every_n_loops"]) == 0:
            print(f"[{datetime.now(timezone.utc).isoformat()}] MODE={cfg['mode']} ENV={cfg.get('exchange_env')} DAILY_KILL={kill_switch} EQUITY~={(eq_now if eq_now is not None else float('nan')):.2f} POS={list(broker.positions().keys())}")
        time.sleep(int(cfg["poll_seconds"]))
