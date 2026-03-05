import argparse
import json
import ccxt
from typing import Dict, Any

from brokers import PaperBroker, ExchangeBroker
from runner import run_loop

def validate_config(cfg: Dict[str, Any]) -> None:
    """Validate configuration parameters to prevent runtime errors"""
    required_fields = ["mode", "symbols", "signal_timeframe", "risk_per_trade", "stop_pct"]
    
    for field in required_fields:
        if field not in cfg:
            raise ValueError(f"Missing required config field: {field}")
    
    # Validate numeric parameters
    numeric_fields = {
        "risk_per_trade": (0.001, 0.1),  # 0.1% to 10%
        "stop_pct": (0.005, 0.2),        # 0.5% to 20%
        "trail_pct": (0.005, 0.2),       # 0.5% to 20%
        "max_positions": (1, 10),
        "max_position_pct": (0.01, 0.5),  # 1% to 50%
        "max_total_exposure_pct": (0.1, 1.0),  # 10% to 100%
        "daily_loss_limit_pct": (0.0, 20.0),  # 0% to 20%
        "api_error_threshold": (1, 100),
        "api_error_window_sec": (30, 3600),
        "api_kill_cooldown_sec": (60, 3600),
        "poll_seconds": (5, 300),
        "regime_ma_len": (50, 500),
        "regime_slope_len": (1, 20),
        "regime_confirm_days": (1, 7),
        "cooldown_candles": (0, 10)
    }
    
    for field, (min_val, max_val) in numeric_fields.items():
        if field in cfg:
            try:
                value = float(cfg[field])
                if not (min_val <= value <= max_val):
                    raise ValueError(f"{field} must be between {min_val} and {max_val}, got {value}")
                cfg[field] = value  # Ensure it's a float
            except (ValueError, TypeError):
                raise ValueError(f"Invalid numeric value for {field}: {cfg[field]}")
    
    # Validate symbols
    if not isinstance(cfg["symbols"], list) or len(cfg["symbols"]) == 0:
        raise ValueError("symbols must be a non-empty list")
    
    for symbol in cfg["symbols"]:
        if not isinstance(symbol, str) or "/" not in symbol:
            raise ValueError(f"Invalid symbol format: {symbol}")
    
    # Validate timeframes
    valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"]
    for tf_field in ["signal_timeframe", "regime_timeframe"]:
        if tf_field in cfg and cfg[tf_field] not in valid_timeframes:
            raise ValueError(f"Invalid {tf_field}: {cfg[tf_field]}")

def load_profile(path: str, profile: str) -> dict:
    with open(path, "r") as f:
        data = json.load(f)
    prof = (data.get("profiles") or {}).get(profile)
    if not prof:
        raise SystemExit(f"Profile not found: {profile}")
    
    # Validate the profile configuration
    validate_config(prof)
    return prof

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--profile", required=True, choices=["local_paper", "phemex_testnet", "phemex_live"])
    args = ap.parse_args()

    cfg = load_profile(args.config, args.profile)

    if cfg["mode"] == "paper":
        market_exchange = ccxt.phemex({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        broker = PaperBroker(cfg, market_exchange)
        run_loop(cfg, broker, market_exchange)
        return

    if cfg["mode"] == "exchange":
        broker = ExchangeBroker(cfg)
        market_exchange = broker.exchange()
        run_loop(cfg, broker, market_exchange)
        return

    raise SystemExit(f"Unknown mode: {cfg['mode']}")

if __name__ == "__main__":
    main()
