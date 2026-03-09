import argparse
import json
import ccxt
import os
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()

from .brokers import PaperBroker, ExchangeBroker
from .runner import run_loop, configure_logging

def validate_strategy_parameters(strategy_params: Dict[str, Any]) -> None:
    """Validate strategy parameters against safe ranges"""
    safe_ranges = {
        "stop_loss_pct": (0.005, 0.03),      # 0.5% - 3%
        "take_profit_pct": (0.02, 0.08),     # 2% - 8%  
        "risk_per_trade": (0.005, 0.02),     # 0.5% - 2%
        "volume_ratio_threshold": (1.5, 3.0), # 1.5x - 3x
        "rsi_threshold": (20, 40),            # Oversold range
        "max_holding_periods": (5, 50),       # 5-50 periods
        "max_portfolio_exposure": (0.1, 0.5)  # 10%-50%
    }
    
    warnings = []
    
    for param, (min_val, max_val) in safe_ranges.items():
        if param in strategy_params:
            try:
                value = float(strategy_params[param])
                if value < min_val or value > max_val:
                    warnings.append(f"{param}: {value:.3f} outside safe range [{min_val:.3f}, {max_val:.3f}]")
            except (ValueError, TypeError):
                warnings.append(f"{param}: Invalid value {strategy_params[param]}")
    
    if warnings:
        print("⚠️  Strategy Parameter Warnings:")
        for warning in warnings:
            print(f"   {warning}")
        print("   Consider adjusting to safer ranges.")

def load_config(profile: str) -> Dict[str, Any]:
    """Load configuration for specified profile"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        if profile not in config.get('profiles', {}):
            raise ValueError(f"Profile '{profile}' not found in config.json")
        
        return config['profiles'][profile]
    except FileNotFoundError:
        raise FileNotFoundError("config.json not found. Please create it from config.json.template")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config.json: {e}")

def create_broker(profile_config: Dict[str, Any]):
    """Create appropriate broker based on profile"""
    mode = profile_config.get('mode', 'paper')

    if mode == 'paper':
        market_exchange = ccxt.phemex({"enableRateLimit": True})
        return PaperBroker(profile_config, market_exchange), market_exchange
    else:
        broker = ExchangeBroker(profile_config)
        return broker, broker.ex

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Phemex Momentum Trading Bot')
    parser.add_argument('--profile', required=True, 
                       choices=['local_paper', 'phemex_testnet', 'phemex_live'],
                       help='Trading profile to use')
    parser.add_argument('--validate-only', action='store_true',
                       help='Validate configuration and exit')
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.profile)
        
        # Validate strategy parameters
        strategy_name = config.get('strategy', 'volume_reversal_strategy')
        if strategy_name in config:
            validate_strategy_parameters(config[strategy_name])
        
        if args.validate_only:
            print("✅ Configuration validation passed")
            return
        
        # Inject profile name so ExchangeBroker can select the right API keys
        config["profile"] = args.profile

        # Ensure directories for state files exist
        for key in ("state_file", "runtime_state_file", "fills_state_file", "log_file"):
            path = config.get(key)
            if path:
                os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None

        # Configure logging to profile-specific log file
        log_file = config.get("log_file", f"{args.profile}.log")
        configure_logging(log_file)

        # Create broker
        broker, market_exchange = create_broker(config)

        # Run trading loop
        print(f"🚀 Starting Phemex Momentum Trading Bot")
        print(f"📊 Profile: {args.profile}")
        print(f"📈 Strategy: {strategy_name}")
        print(f"🔧 Mode: {config.get('mode', 'paper')}")

        run_loop(config, broker, market_exchange)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())