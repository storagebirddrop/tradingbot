import argparse
import json
import ccxt

from brokers import PaperBroker, ExchangeBroker
from runner import run_loop

def load_profile(path: str, profile: str) -> dict:
    with open(path, "r") as f:
        data = json.load(f)
    prof = (data.get("profiles") or {}).get(profile)
    if not prof:
        raise SystemExit(f"Profile not found: {profile}")
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
