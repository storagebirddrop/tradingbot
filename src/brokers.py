import os, csv, json, time, hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any, Tuple
import base64
import binascii
from cryptography.fernet import Fernet, InvalidToken

# Module-level cache for encryption key
_cached_encryption_key = None

import ccxt
import pandas as pd

from .strategy import drop_incomplete_last_candle, compute_4h_indicators, compute_daily_regime, attach_regime_to_4h
from scripts.reconcile import reconcile_fills, pnl_totals

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _get_encryption_key() -> bytes:
    """Generate or retrieve encryption key from environment"""
    import binascii
    
    key_env = os.environ.get("BOT_ENCRYPTION_KEY")
    if key_env:
        try:
            # Check if it's already a valid Fernet key (44 chars, base64 format, ends with =)
            if len(key_env) == 44 and key_env.endswith('=') and ('-' in key_env or '_' in key_env):
                # It's already a Fernet key - use directly
                return key_env.encode()
            elif len(key_env) == 64 and all(c in '0123456789abcdefABCDEF' for c in key_env):
                # It's a hex key from OpenSSL - convert to Fernet format
                key_bytes = bytes.fromhex(key_env)
                return base64.urlsafe_b64encode(key_bytes)
            else:
                # Try to decode as base64 and validate (fallback for existing keys)
                try:
                    decoded = base64.urlsafe_b64decode(key_env.encode())
                    if len(decoded) == 32:
                        # Valid 32-byte key, re-encode to ensure proper format
                        return base64.urlsafe_b64encode(decoded)
                    else:
                        raise ValueError("Decoded key is not 32 bytes")
                except Exception as e:
                    raise ValueError(f"Invalid BOT_ENCRYPTION_KEY format: {e}")
        except (binascii.Error, TypeError, ValueError) as e:
            raise ValueError(f"Invalid BOT_ENCRYPTION_KEY format: {e}")
    
    # For development/testing only, generate a random key once and cache it
    # In production, BOT_ENCRYPTION_KEY must be set
    global _cached_encryption_key
    if os.environ.get("BOT_ENV") in ["development", "test"]:
        if _cached_encryption_key is None:
            _cached_encryption_key = base64.urlsafe_b64encode(os.urandom(32))
        return _cached_encryption_key
    
    raise ValueError("BOT_ENCRYPTION_KEY environment variable must be set in production")

def _encrypt_data(data: str) -> bytes:
    """Encrypt sensitive data"""
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        return f.encrypt(data.encode())
    except ValueError as e:
        # Re-raise ValueError from _get_encryption_key
        raise
    except (TypeError, AttributeError) as e:
        raise ValueError(f"Invalid encryption key format: {e}")
    except Exception as e:
        raise ValueError(f"Encryption failed: {e}")

def _decrypt_data(encrypted_data: bytes) -> str:
    """Decrypt sensitive data"""
    if not isinstance(encrypted_data, bytes):
        raise ValueError("Encrypted data must be bytes")
    
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data)
        return decrypted.decode() if isinstance(decrypted, bytes) else decrypted
    except (KeyError, TypeError) as e:
        raise ValueError(f"Failed to get encryption key: {e}")
    except InvalidToken:
        raise ValueError("Invalid encryption token - data may be corrupted or encrypted with different key")
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")

def ensure_csv(path: str, header: List[str]) -> None:
    if os.path.exists(path): return
    with open(path, "w", newline="") as f:
        csv.writer(f).writerow(header)

def append_csv(path: str, row: List[Any]) -> None:
    with open(path, "a", newline="") as f:
        csv.writer(f).writerow(row)

def save_json(path: str, obj, encrypt: bool = False) -> None:
    """Save JSON data with optional encryption for sensitive files"""
    tmp = path + ".tmp"
    data = json.dumps(obj, indent=2, sort_keys=True)
    
    if encrypt and ("state" in path or "runtime" in path):
        # Encrypt sensitive state files
        encrypted_data = _encrypt_data(data)
        with open(tmp, "wb") as f:
            f.write(encrypted_data)
        # Mark as encrypted by adding .enc extension
        encrypted_path = path + ".enc"
        os.replace(tmp, encrypted_path)
        
        # Remove unencrypted file if it exists after successful encryption
        if os.path.exists(path):
            os.remove(path)
    else:
        # Regular unencrypted save
        with open(tmp, "w") as f:
            f.write(data)
        os.replace(tmp, path)

def load_json(path: str):
    """Load JSON data with automatic decryption support"""
    if not path:
        return None
    
    # Prefer encrypted version if it exists
    if not path.endswith('.enc'):
        encrypted_path = path + '.enc'
        if os.path.exists(encrypted_path):
            path = encrypted_path
        elif not os.path.exists(path):
            return None
    elif not os.path.exists(path):
        return None
    
    try:
        if path.endswith('.enc'):
            # Encrypted file - read as bytes and decrypt
            with open(path, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = _decrypt_data(encrypted_data)
            # Ensure decrypted data is string for json.loads
            if isinstance(decrypted_data, bytes):
                decrypted_data = decrypted_data.decode('utf-8')
            return json.loads(decrypted_data)
        else:
            # Regular text file
            with open(path, "r") as f:
                return json.load(f)
    except FileNotFoundError:
        print(f"File not found: {path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in {path}: {e}")
        return None
    except PermissionError:
        print(f"Permission denied accessing {path}")
        return None
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None

def fetch_ohlcv_df(exchange: ccxt.Exchange, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)

def get_latest_signal_rows(exchange: ccxt.Exchange, cfg: dict, symbol: str) -> Optional[Tuple[pd.Series, pd.Series]]:
    df4h = fetch_ohlcv_df(exchange, symbol, cfg["signal_timeframe"], cfg["limit_4h"])
    df1d = fetch_ohlcv_df(exchange, symbol, cfg["regime_timeframe"], cfg["limit_1d"])
    df4h = drop_incomplete_last_candle(df4h, cfg["signal_timeframe"])
    df1d = drop_incomplete_last_candle(df1d, cfg["regime_timeframe"])
    if len(df4h) < 250 or len(df1d) < int(cfg["regime_ma_len"]) + 20:
        return None
    df4h_ind = compute_4h_indicators(df4h)
    df_reg = compute_daily_regime(df1d,
                                  regime_ma_len=int(cfg["regime_ma_len"]),
                                  regime_slope_len=int(cfg["regime_slope_len"]),
                                  confirm_days=int(cfg["regime_confirm_days"]))
    df = attach_regime_to_4h(df4h_ind, df_reg).dropna().reset_index(drop=True)
    if len(df) < 3:
        return None
    return df.iloc[-1], df.iloc[-2]

def get_current_tf_open_ts(exchange: ccxt.Exchange, symbol: str, timeframe: str) -> Optional[int]:
    try:
        df = fetch_ohlcv_df(exchange, symbol, timeframe, limit=3)
        if df.empty: return None
        return int(df.iloc[-1]["timestamp"].timestamp())
    except Exception:
        return None

def configure_phemex_env(ex: ccxt.Exchange, env: str) -> None:
    if env != "testnet": return
    try:
        ex.set_sandbox_mode(True)
        print("Configured Phemex testnet sandbox mode")
    except Exception as e:
        print(f"Warning: Failed to set sandbox mode: {e}")
    # best-effort REST override - use proper API structure
    try:
        if hasattr(ex, 'urls') and isinstance(ex.urls, dict):
            # Update the API URLs for testnet
            ex.urls['api']['public'] = "https://testnet-api.phemex.com"
            ex.urls['api']['private'] = "https://testnet-api.phemex.com"
            ex.urls['www'] = "https://testnet.phemex.com"
            print("Configured Phemex testnet API URLs")
    except Exception as e:
        print(f"Warning: Failed to configure testnet URLs: {e}")

@dataclass
class Position:
    qty: float
    entry_px: float
    stop_px: float
    high_water: float
    entry_time: str
    stop_order_id: Optional[str] = None

class BaseBroker:
    def __init__(self):
        self._api_error_count = 0
    def record_api_error(self, *_args, **_kwargs):
        self._api_error_count += 1
    def pop_api_error_count(self) -> int:
        n = self._api_error_count
        self._api_error_count = 0
        return int(n)
    def log_event(self, event: str, details: str = "") -> None:
        return
    def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """Returns current perpetual funding rate or None if unavailable/not applicable."""
        return None
    def on_stop_updated(self, symbol: str, pos, new_stop_px: float, price_map: dict) -> None:
        """Called when trailing stop is raised. Base implementation updates stop_px in-place."""
        pos.stop_px = new_stop_px

class PaperBroker(BaseBroker):
    def __init__(self, cfg: dict, market_exchange: ccxt.Exchange):
        super().__init__()
        self.cfg = cfg
        self.ex = market_exchange
        self.cash = float(cfg["starting_cash"])
        self._positions: Dict[str, Position] = {}
        self._last_prices: Dict[str, float] = {}
        ensure_csv(cfg["trade_log"], ["time_utc","symbol","side","qty","price","fee","slippage_bps","reason","cash_after","equity_after","pnl"])
        ensure_csv(cfg["equity_log"], ["time_utc","cash","equity","exposure","open_positions"])
        self._equity_history: List[Tuple[str,float]] = []
        self._fills_state: Dict[str,Any] = {}
        if "fills_state_file" in cfg:
            try:
                with open(cfg["fills_state_file"], "r") as f:
                    self._fills_state = json.load(f)
            except FileNotFoundError:
                pass
        self._restore()

    def _restore(self):
        st = load_json(self.cfg["state_file"]) or {}
        try:
            self.cash = float(st.get("cash", self.cash))
            positions_data = st.get("positions") or {}
            self._positions = {s: Position(**p) for s,p in positions_data.items()}
        except (ValueError, TypeError, KeyError) as e:
            print(f"Warning: Failed to restore state: {e}")
            # Continue with default values
        except Exception as e:
            print(f"Error: Unexpected error during state restore: {e}")
            # Continue with default values

    def persist(self):
        save_json(self.cfg["state_file"], 
                 {"cash": self.cash, "positions": {s: asdict(p) for s,p in self._positions.items()}, "saved_at": now_iso()}, 
                 encrypt=True)

    def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        out = {}
        for s in symbols:
            try:
                t = self.ex.fetch_ticker(s)
                px = t.get("last") or t.get("close")
                if px is not None:
                    out[s] = float(px)
                    self._last_prices[s] = float(px)
            except Exception:
                self.record_api_error("paper.fetch_ticker")
        for s,px in self._last_prices.items():
            out.setdefault(s, px)
        return out

    def positions(self) -> Dict[str, Position]:
        return self._positions

    def can_open_new(self) -> bool:
        return len(self._positions) < int(self.cfg["max_positions"])

    def equity_usdt(self, price_map: Dict[str,float]) -> float:
        eq = self.cash
        for s,p in self._positions.items():
            px = price_map.get(s)
            if px is not None:
                eq += p.qty * px
        return eq

    def _exposure(self, price_map: Dict[str,float]) -> float:
        exp = 0.0
        for s,p in self._positions.items():
            px = price_map.get(s)
            if px is not None:
                exp += p.qty * px
        return exp

    def buy(self, symbol: str, px: float, reason: str, price_map: Dict[str,float],
             stop_px: Optional[float] = None, size_scale: float = 1.0, strategy_stop_pct: Optional[float] = None) -> bool:
        eq = self.equity_usdt(price_map)
        risk_amt = eq * float(self.cfg["risk_per_trade"]) * size_scale
        # Use provided stop_px if valid, otherwise fall back to strategy-specific stop_pct, then global stop_pct
        if stop_px is not None:
            if stop_px < px:
                effective_stop = stop_px
            else:
                # Invalid stop_px (>= entry price) - log warning and fall back
                print(f"Warning: Invalid stop_px ${stop_px:.2f} >= entry price ${px:.2f} for {symbol}. Falling back to strategy/global stop loss.")
                if strategy_stop_pct is not None:
                    effective_stop = px * (1 - strategy_stop_pct)
                else:
                    effective_stop = px * (1 - float(self.cfg["stop_pct"]))
        elif strategy_stop_pct is not None:
            effective_stop = px * (1 - strategy_stop_pct)
        else:
            effective_stop = px * (1 - float(self.cfg["stop_pct"]))
        stop_dist = px - effective_stop
        if stop_dist <= 0: return False
        qty = min(risk_amt/stop_dist,
                  (eq*float(self.cfg["max_position_pct"]))/px,
                  max(0.0, (eq*float(self.cfg["max_total_exposure_pct"]) - self._exposure(price_map)))/px,
                  self.cash/(px*(1+float(self.cfg["fee_rate"]))))
        if qty <= 0: return False
        fee = qty*px*float(self.cfg["fee_rate"])
        cost = qty*px + fee
        if cost > self.cash: return False
        self.cash -= cost
        self._positions[symbol] = Position(qty=qty, entry_px=px, stop_px=effective_stop, high_water=px, entry_time=now_iso())
        append_csv(self.cfg["trade_log"], [now_iso(), symbol, "BUY", qty, px, fee, self.cfg["slippage_bps"], reason, self.cash, self.equity_usdt(price_map), ""])
        return True

    def sell(self, symbol: str, px: float, reason: str, price_map: Dict[str,float]) -> bool:
        pos = self._positions.get(symbol)
        if not pos: return False
        fee_exit = pos.qty*px*float(self.cfg["fee_rate"])
        proceeds = pos.qty*px - fee_exit
        fee_entry = pos.qty*pos.entry_px*float(self.cfg["fee_rate"])
        pnl = proceeds - (pos.qty*pos.entry_px + fee_entry)
        self.cash += proceeds
        del self._positions[symbol]
        append_csv(self.cfg["trade_log"], [now_iso(), symbol, "SELL", pos.qty, px, fee_exit, self.cfg["slippage_bps"], reason, self.cash, self.equity_usdt(price_map), pnl])
        return True

    def snapshot_equity(self, price_map: Dict[str,float]) -> None:
        append_csv(self.cfg["equity_log"], [now_iso(), self.cash, self.equity_usdt(price_map), self._exposure(price_map), "|".join(sorted(self._positions.keys()))])

    def reconcile_fills_if_due(self, loop: int, price_map: Dict[str,float]) -> None:
        # Paper trading doesn't need fill reconciliation
        return

    def sync_positions(self, price_map: Dict[str,float]) -> List[str]:
        # Paper trading doesn't need position syncing with exchange
        return []

def _validate_api_credentials(api_key: str, api_secret: str) -> None:
    """Validate API key format and strength"""
    import re
    
    if not api_key or len(api_key) < 32:
        raise ValueError("API key too short (minimum 32 characters)")
    
    if not api_secret or len(api_secret) < 32:
        raise ValueError("API secret too short (minimum 32 characters)")
    
    # Check for weak patterns
    if api_key == api_key[0] * len(api_key):
        raise ValueError("API key appears to be weak/repeated characters")
    
    if api_secret == api_secret[0] * len(api_secret):
        raise ValueError("API secret appears to be weak/repeated characters")

class ExchangeBroker(BaseBroker):
    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self._positions: Dict[str, Position] = {}
        self._last_prices: Dict[str, float] = {}
        ensure_csv(cfg["trade_log"], ["time_utc","symbol","event","qty","price_hint","trigger_price","reason","dry_run","order_id","order_json_trunc"])
        ensure_csv(cfg["equity_log"], ["time_utc","equity_est_usdt","realized_pnl_usdt","unrealized_pnl_est_usdt","open_positions","dry_run"])
        
        # Get API keys from environment variables with fallbacks
        profile = cfg.get("profile", "").lower()
        
        if "testnet" in profile:
            api_key = os.environ.get("PHEMEX_TESTNET_API_KEY") or os.environ.get("PHEMEX_API_KEY")
            api_secret = os.environ.get("PHEMEX_TESTNET_API_SECRET") or os.environ.get("PHEMEX_API_SECRET")
        elif "live" in profile:
            api_key = os.environ.get("PHEMEX_LIVE_API_KEY") or os.environ.get("PHEMEX_API_KEY")
            api_secret = os.environ.get("PHEMEX_LIVE_API_SECRET") or os.environ.get("PHEMEX_API_SECRET")
        else:
            api_key = os.environ.get("PHEMEX_API_KEY")
            api_secret = os.environ.get("PHEMEX_API_SECRET")
        
        if not api_key or not api_secret:
            raise SystemExit("Missing PHEMEX_API_KEY / PHEMEX_API_SECRET env vars.")
        
        # Validate API credentials
        _validate_api_credentials(api_key, api_secret)
        
        # Log API key validation (without exposing the actual keys)
        print(f"API credentials validated (key length: {len(api_key)}, secret length: {len(api_secret)})")
        
        self.ex = ccxt.phemex({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True, "options": {"defaultType":"spot"}})
        configure_phemex_env(self.ex, cfg.get("exchange_env","live"))
        self.ex.load_markets()
        self._fills_state_path = cfg.get("fills_state_file","fills_state.json")
        self._fills_log_path = cfg.get("fills_log","fills.csv")
        self._fills_state = load_json(self._fills_state_path) or {"since_ms": None, "by_symbol": {}}
        self._restore()

    def exchange(self) -> ccxt.Exchange:
        return self.ex

    def log_event(self, event: str, details: str = "") -> None:
        append_csv(self.cfg["trade_log"], [now_iso(), "*", event, "", "", "", details, self.cfg.get("dry_run", True), "", ""])

    def _restore(self):
        st = load_json(self.cfg["state_file"]) or {}
        try:
            self._positions = {s: Position(**p) for s,p in (st.get("positions") or {}).items()}
        except Exception:
            pass

    def persist(self):
        save_json(self.cfg["state_file"], {"positions": {s: asdict(p) for s,p in self._positions.items()}, "saved_at": now_iso()}, encrypt=True)
        save_json(self._fills_state_path, self._fills_state, encrypt=True)

    def _guard(self):
        if bool(self.cfg.get("dry_run", True)):
            return
        env = self.cfg.get("exchange_env","live")
        if env == "testnet":
            if os.environ.get("ENABLE_TESTNET_TRADING","").upper() != "YES":
                raise SystemExit("Refusing to trade on TESTNET. Set ENABLE_TESTNET_TRADING=YES.")
        else:
            if os.environ.get("ENABLE_LIVE_TRADING","").upper() != "YES":
                raise SystemExit("Refusing to trade LIVE. Set ENABLE_LIVE_TRADING=YES.")

    def reconcile_fills_if_due(self, loop: int, price_map: Dict[str,float]) -> None:
        every = int(self.cfg.get("fills_reconcile_every_n_loops", 2))
        if every <= 0 or loop % every != 0: return
        if bool(self.cfg.get("dry_run", True)): return
        try:
            self._fills_state = reconcile_fills(self.ex, self.cfg["symbols"], self._fills_state, self._fills_log_path)
        except Exception:
            self.record_api_error("exchange.fetch_my_trades")

    def get_prices(self, symbols: List[str]) -> Dict[str,float]:
        out = {}
        for s in symbols:
            try:
                t = self.ex.fetch_ticker(s)
                px = t.get("last") or t.get("close")
                if px is not None:
                    out[s] = float(px)
                    self._last_prices[s] = float(px)
            except Exception:
                self.record_api_error("exchange.fetch_ticker")
        for s,px in self._last_prices.items():
            out.setdefault(s, px)
        return out

    def positions(self) -> Dict[str, Position]:
        return self._positions

    def can_open_new(self) -> bool:
        return len(self._positions) < int(self.cfg["max_positions"])

    def equity_usdt(self, price_map: Dict[str,float]) -> float:
        bal = self.ex.fetch_balance()
        total = float(((bal.get("free") or {}).get("USDT",0.0)) or 0.0)
        for sym in self.cfg["symbols"]:
            base = sym.split("/")[0]
            qty = float(((bal.get("free") or {}).get(base,0.0)) or 0.0)
            px = price_map.get(sym)
            if px is not None:
                total += qty * px
        return total

    def _pnl_totals(self, price_map: Dict[str,float]) -> Tuple[float,float]:
        r,u,_ = pnl_totals(self._fills_state, price_map)
        return r,u

    def _create_hard_stop(self, symbol: str, qty: float, stop_px: float) -> str:
        params = {"triggerPrice": float(stop_px), "triggerPriceType": str(self.cfg.get("trigger_price_type","last"))}
        if bool(self.cfg.get("dry_run", True)):
            return "DRY_STOP"
        self._guard()
        order = self.ex.create_order(symbol, "market", "sell", qty, None, params)
        oid = order.get("id") or order.get("orderID") or order.get("orderId")
        if not oid:
            raise RuntimeError(f"Stop order missing id: {order}")
        return str(oid)

    def _confirm_stop(self, symbol: str, stop_order_id: str) -> bool:
        if stop_order_id in (None,"","DRY_STOP"): return True
        if bool(self.cfg.get("dry_run", True)): return True
        timeout = int(self.cfg.get("stop_confirm_timeout_sec", 20))
        deadline = time.time() + max(3, timeout)
        while time.time() < deadline:
            try:
                o = self.ex.fetch_order(stop_order_id, symbol)
                status = (o.get("status") or "").lower()
                if status in ("open","new","created"): return True
                if status in ("canceled","rejected"): return False
                # Status is neither confirmed open nor canceled, continue checking
                time.sleep(0.6)
                continue
            except Exception:
                self.record_api_error("exchange.fetch_order_stop_confirm")
                time.sleep(0.6)
        return False

    def _cancel_hard_stop(self, symbol: str, stop_order_id: str) -> None:
        if not stop_order_id or stop_order_id == "DRY_STOP": return
        if bool(self.cfg.get("dry_run", True)): return
        try:
            self._guard()
            self.ex.cancel_order(stop_order_id, symbol)
        except Exception:
            self.record_api_error("exchange.cancel_order")

    def _amend_hard_stop(self, symbol: str, stop_order_id: str, qty: float, new_stop_px: float) -> str:
        if not stop_order_id: return stop_order_id
        if bool(self.cfg.get("dry_run", True)): return stop_order_id
        self._guard()
        params = {"triggerPrice": float(new_stop_px), "triggerPriceType": str(self.cfg.get("trigger_price_type","last"))}
        try:
            self.ex.edit_order(stop_order_id, symbol, "market", "sell", qty, None, params)
            return stop_order_id
        except Exception as e:
            print(f"Warning: Failed to edit stop order: {e}")
            self.record_api_error("exchange.edit_order_stop")
            new_id = self._create_hard_stop(symbol, qty, new_stop_px)
            try:
                self.ex.cancel_order(stop_order_id, symbol)
            except Exception as e2:
                print(f"Warning: Failed to cancel old stop after replacement: {e2}")
                self.record_api_error("exchange.cancel_old_stop_after_replace")
            return new_id

    def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """Fetch current perpetual funding rate. Returns None on any error (fail-open)."""
        # Phemex requires the perpetual swap symbol (BASE/USDT:USDT), not the spot symbol
        perp_symbol = symbol if ":" in symbol else f"{symbol}:USDT"
        try:
            fr = self.ex.fetch_funding_rate(perp_symbol)
            # ccxt normalises to fundingRate, but Phemex populates nextFundingRate instead
            rate = fr.get("fundingRate")
            if rate is None:
                rate = fr.get("nextFundingRate")
            if rate is None:
                rate = (fr.get("info") or {}).get("fundingRateRr")
            return float(rate) if rate is not None else None
        except Exception:
            return None

    def buy(self, symbol: str, px: float, reason: str, price_map: Dict[str,float],
             stop_px: Optional[float] = None, size_scale: float = 1.0, strategy_stop_pct: Optional[float] = None) -> bool:
        # size using risk model
        eq = self.equity_usdt(price_map)
        risk_amt = eq * float(self.cfg["risk_per_trade"]) * size_scale
        # Use provided stop_px if valid, otherwise fall back to strategy-specific stop_pct, then global stop_pct
        if stop_px is not None:
            if stop_px < px:
                effective_stop_dist = px - stop_px
            else:
                # Invalid stop_px (>= entry price) - log warning and fall back
                print(f"Warning: Invalid stop_px ${stop_px:.2f} >= entry price ${px:.2f} for {symbol}. Falling back to strategy/global stop loss.")
                if strategy_stop_pct is not None:
                    effective_stop_dist = px * strategy_stop_pct
                else:
                    effective_stop_dist = px * float(self.cfg["stop_pct"])
        elif strategy_stop_pct is not None:
            effective_stop_dist = px * strategy_stop_pct
        else:
            effective_stop_dist = px * float(self.cfg["stop_pct"])
        if effective_stop_dist <= 0: return False
        qty = min(risk_amt/effective_stop_dist, (eq*float(self.cfg["max_position_pct"]))/px)
        qty = float(self.ex.amount_to_precision(symbol, qty))
        if qty <= 0: return False

        if bool(self.cfg.get("dry_run", True)):
            buy_order = {"dry_run": True, "id":"DRY_BUY", "filled": qty, "average": px}
        else:
            self._guard()
            try:
                buy_order = self.ex.create_order(symbol, "market", "buy", qty)
            except Exception as e:
                print(f"Warning: Failed to create buy order: {e}")
                self.record_api_error("exchange.create_order_buy")
                return False

        filled = float(buy_order.get("filled") or qty)
        avg = float(buy_order.get("average") or px)
        append_csv(self.cfg["trade_log"], [now_iso(), symbol, "BUY", filled, px, "", reason, self.cfg.get("dry_run", True), buy_order.get("id",""), json.dumps(buy_order)[:1500]])

        # hard stop + confirm — use caller-supplied stop_px if valid, else fixed pct
        if stop_px is not None and stop_px < avg:
            stop_px_final = stop_px
        else:
            stop_px_final = avg * (1 - float(self.cfg["stop_pct"]))
        stop_id = None
        if bool(self.cfg.get("hard_stops", False)):
            try:
                stop_id = self._create_hard_stop(symbol, filled, stop_px_final)
                append_csv(self.cfg["trade_log"], [now_iso(), symbol, "STOP_CREATED", filled, px, stop_px_final, "protective_stop", self.cfg.get("dry_run", True), stop_id, ""])
                if not self._confirm_stop(symbol, stop_id):
                    append_csv(self.cfg["trade_log"], [now_iso(), symbol, "STOP_CONFIRM_FAILED_EXITING", filled, px, stop_px_final, "fail_closed", self.cfg.get("dry_run", True), stop_id, ""])
                    self._cancel_hard_stop(symbol, stop_id)
                    if not bool(self.cfg.get("dry_run", True)):
                        self._guard()
                        self.ex.create_order(symbol, "market", "sell", filled)
                    return False
                append_csv(self.cfg["trade_log"], [now_iso(), symbol, "STOP_CONFIRMED", filled, px, stop_px_final, "ok", self.cfg.get("dry_run", True), stop_id, ""])
            except Exception:
                return False

        self._positions[symbol] = Position(qty=filled, entry_px=avg, stop_px=stop_px_final, high_water=avg, entry_time=now_iso(), stop_order_id=stop_id)
        return True

    def sell(self, symbol: str, px: float, reason: str, price_map: Dict[str,float]) -> bool:
        pos = self._positions.get(symbol)
        if not pos: return False
        if bool(self.cfg.get("hard_stops", False)) and pos.stop_order_id:
            self._cancel_hard_stop(symbol, pos.stop_order_id)

        qty = float(self.ex.amount_to_precision(symbol, pos.qty))
        if qty <= 0: return False

        if bool(self.cfg.get("dry_run", True)):
            sell_order = {"dry_run": True, "id":"DRY_SELL", "amount": qty}
        else:
            self._guard()
            try:
                sell_order = self.ex.create_order(symbol, "market", "sell", qty)
            except Exception:
                self.record_api_error("exchange.create_order_sell")
                return False

        append_csv(self.cfg["trade_log"], [now_iso(), symbol, "SELL", qty, px, "", reason, self.cfg.get("dry_run", True), sell_order.get("id",""), json.dumps(sell_order)[:1500]])
        del self._positions[symbol]
        return True

    def snapshot_equity(self, price_map: Dict[str,float]) -> None:
        try:
            eq = self.equity_usdt(price_map)
        except Exception:
            return  # equity fetch is informational; don't count against API error threshold
        realized, unreal = self._pnl_totals(price_map)
        pos_list = "|".join(sorted(self._positions.keys()))
        append_csv(self.cfg["equity_log"], [now_iso(), round(eq,10), round(realized,10), round(unreal,10), pos_list, self.cfg.get("dry_run", True)])

    def on_stop_updated(self, symbol: str, pos: Position, new_stop_px: float, price_map: Dict[str,float]) -> None:
        if not bool(self.cfg.get("hard_stops", False)): return
        if not pos.stop_order_id: return
        if new_stop_px <= pos.stop_px: return
        old = pos.stop_px
        pos.stop_px = new_stop_px
        if bool(self.cfg.get("dry_run", True)):
            append_csv(self.cfg["trade_log"], [now_iso(), symbol, "STOP_AMENDED_DRY", pos.qty, price_map.get(symbol,""), new_stop_px, f"trail_from={old}", True, pos.stop_order_id, ""])
            return
        try:
            new_id = self._amend_hard_stop(symbol, pos.stop_order_id, pos.qty, new_stop_px)
            ev = "STOP_REPLACED" if new_id != pos.stop_order_id else "STOP_AMENDED"
            append_csv(self.cfg["trade_log"], [now_iso(), symbol, ev, pos.qty, price_map.get(symbol,""), new_stop_px, f"trail_from={old}", self.cfg.get("dry_run", True), new_id, ""])
            pos.stop_order_id = new_id
        except Exception:
            pos.stop_px = old

    def sync_positions(self, price_map: Dict[str,float]) -> List[str]:
        removed = []
        if bool(self.cfg.get("dry_run", True)): return removed
        if not bool(self.cfg.get("hard_stops", False)): return removed
        for sym,pos in list(self._positions.items()):
            if not pos.stop_order_id: continue
            try:
                o = self.ex.fetch_order(pos.stop_order_id, sym)
                if (o.get("status") or "").lower() == "closed":
                    append_csv(self.cfg["trade_log"], [now_iso(), sym, "STOP_FILLED_SYNC", pos.qty, price_map.get(sym,""), pos.stop_px, "exchange_stop_filled", self.cfg.get("dry_run", True), pos.stop_order_id, ""])
                    del self._positions[sym]
                    removed.append(sym)
            except Exception:
                self.record_api_error("exchange.fetch_order_sync")
        return removed
