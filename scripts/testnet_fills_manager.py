#!/usr/bin/env python3
"""
Testnet Fills State Management

Secure handling of testnet fills state without committing encrypted artifacts
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from secure_state import SecureStateManager

class TestnetFillsManager(SecureStateManager):
    """Specialized manager for testnet fills state"""
    
    def __init__(self):
        super().__init__("testnet")
    
    def generate_fills_state(self, initial_balance: float = 10000.0) -> dict:
        """Generate testnet fills state dynamically"""
        return {
            "profile": "testnet",
            "type": "fills_state",
            "initial_balance": initial_balance,
            "current_balance": initial_balance,
            "fills": [],
            "last_update": datetime.utcnow().isoformat(),
            "exchange": "phemex_testnet",
            "security_note": "Generated dynamically - never commit encrypted state",
            "version": "1.0"
        }
    
    def add_fill(self, fill_data: dict):
        """Add a fill to the state"""
        state = self.load_state(encrypted=True) or self.generate_fills_state()
        
        fill_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": fill_data.get("symbol", ""),
            "side": fill_data.get("side", ""),
            "amount": fill_data.get("amount", 0.0),
            "price": fill_data.get("price", 0.0),
            "fee": fill_data.get("fee", 0.0),
            "order_id": fill_data.get("order_id", ""),
            "trade_id": fill_data.get("trade_id", "")
        }
        
        state["fills"].append(fill_record)
        state["last_update"] = datetime.utcnow().isoformat()
        
        # Update balance
        if fill_data.get("side") == "buy":
            state["current_balance"] -= fill_data.get("cost", 0.0) + fill_data.get("fee", 0.0)
        else:
            state["current_balance"] += fill_data.get("cost", 0.0) - fill_data.get("fee", 0.0)
        
        self.save_state(state, encrypt=True)
        return state
    
    def get_fills_summary(self) -> dict:
        """Get summary of fills"""
        state = self.load_state(encrypted=True)
        if not state:
            return {"error": "No state found"}
        
        fills = state.get("fills", [])
        if not fills:
            return {
                "total_fills": 0,
                "current_balance": state.get("current_balance", 0.0),
                "initial_balance": state.get("initial_balance", 0.0),
                "pnl": 0.0
            }
        
        total_fees = sum(fill.get("fee", 0.0) for fill in fills)
        pnl = state.get("current_balance", 0.0) - state.get("initial_balance", 0.0)
        
        return {
            "total_fills": len(fills),
            "total_fees": total_fees,
            "current_balance": state.get("current_balance", 0.0),
            "initial_balance": state.get("initial_balance", 0.0),
            "pnl": pnl,
            "last_update": state.get("last_update"),
            "exchange": state.get("exchange", "phemex_testnet")
        }

def main():
    """CLI for testnet fills management"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 testnet_fills_manager.py <command> [options]")
        print("Commands:")
        print("  generate [balance]  - Generate new fills state")
        print("  add_fill <json>     - Add fill data (JSON string)")
        print("  summary            - Get fills summary")
        print("  load               - Load existing state")
        sys.exit(1)
    
    command = sys.argv[1]
    manager = TestnetFillsManager()
    
    if command == "generate":
        balance = float(sys.argv[2]) if len(sys.argv) > 2 else 10000.0
        state = manager.generate_fills_state(balance)
        manager.save_state(state, encrypt=True)
        print(f"✅ Testnet fills state generated with balance: ${balance}")
        
    elif command == "add_fill":
        if len(sys.argv) < 3:
            print("❌ Fill data required as JSON string")
            sys.exit(1)
        
        try:
            fill_data = json.loads(sys.argv[2])
            state = manager.add_fill(fill_data)
            print(f"✅ Fill added for {fill_data.get('symbol', 'unknown')}")
        except json.JSONDecodeError:
            print("❌ Invalid JSON format for fill data")
            sys.exit(1)
        
    elif command == "summary":
        summary = manager.get_fills_summary()
        print("📊 Testnet Fills Summary:")
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"  {key}: ${value:.2f}")
            else:
                print(f"  {key}: {value}")
        
    elif command == "load":
        state = manager.load_state(encrypted=True)
        if state:
            print(f"✅ Testnet fills state loaded")
            print(f"💰 Current balance: ${state.get('current_balance', 0):.2f}")
            print(f"📈 Total fills: {len(state.get('fills', []))}")
        else:
            print("❌ No testnet fills state found")
            
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
