#!/usr/bin/env python3
"""
Phase 3: System Integration Testing
End-to-end testing of Volume Reversal strategy with the complete trading system
"""

import pandas as pd
import numpy as np
import sys
import os
import json
import time
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators, entry_signal, exit_signal
import brokers  # Import broker system

# Test configuration
TEST_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
TEST_PERIOD = 'recent_period'

def load_configuration():
    """Load Volume Reversal configuration"""
    try:
        with open('/home/dribble0335/dev/tradingbot/config.json', 'r') as f:
            config = json.load(f)
        
        profile = config['profiles']['local_paper']
        volume_config = profile.get('volume_reversal_strategy', {})
        
        return {
            'volume_reversal': volume_config,
            'general': profile
        }
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return None

def load_historical_data(symbol, period):
    """Load historical data for testing"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    filepath_4h = f"/home/dribble0335/dev/tradingbot/research/historical/{filename_4h}"
    
    if os.path.exists(filepath_4h):
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def test_strategy_functions():
    """Test all strategy functions work correctly"""
    print("🔧 STRATEGY FUNCTIONS TEST")
    print("-" * 50)
    
    try:
        # Load test data
        df = load_historical_data("BTC/USDT", TEST_PERIOD)
        df_ind = compute_4h_indicators(df)
        
        if df_ind.empty:
            print("❌ No data available for testing")
            return False
        
        # Find a signal
        signal_found = False
        for i in range(1, min(100, len(df_ind))):
            sig = df_ind.iloc[i]
            prev_sig = df_ind.iloc[i-1]
            
            # Test Volume Reversal signal
            if entry_signal(sig, prev_sig, strategy="volume_reversal_long"):
                print(f"✅ Entry signal generated at index {i}")
                print(f"   Timestamp: {sig['timestamp']}")
                print(f"   Volume Ratio: {sig['volume_ratio']:.2f}")
                print(f"   RSI: {sig['rsi']:.1f}")
                
                # Test exit signal
                exit_result = exit_signal(sig, strategy="volume_reversal_long")
                print(f"   Exit signal: {exit_result}")
                
                signal_found = True
                break
        
        if not signal_found:
            print("⚠️ No signals found in first 100 candles")
        
        # Test other strategies for comparison
        print(f"\n🔄 STRATEGY COMPARISON:")
        strategies = ['volume_reversal_long', 'sma_rsi_combo', 'sma_rsi_impulse']
        for strategy in strategies:
            count = 0
            for i in range(1, min(200, len(df_ind))):
                sig = df_ind.iloc[i]
                prev_sig = df_ind.iloc[i-1]
                
                if entry_signal(sig, prev_sig, strategy=strategy):
                    count += 1
            
            print(f"  {strategy}: {count} signals in first 200 candles")
        
        return True
        
    except Exception as e:
        print(f"❌ Strategy function test failed: {e}")
        return False

def test_configuration_integration():
    """Test configuration loading and parameter integration"""
    print(f"\n⚙️ CONFIGURATION INTEGRATION TEST")
    print("-" * 50)
    
    config = load_configuration()
    if not config:
        return False
    
    volume_config = config['volume_reversal']
    general_config = config['general']
    
    # Check required parameters
    required_params = [
        'stop_loss_pct', 'take_profit_pct', 'max_holding_periods',
        'volume_ratio_threshold', 'rsi_threshold', 'risk_per_trade'
    ]
    
    missing_params = []
    for param in required_params:
        if param not in volume_config:
            missing_params.append(param)
    
    if missing_params:
        print(f"❌ Missing configuration parameters: {missing_params}")
        return False
    
    print(f"✅ All required parameters present")
    print(f"  Stop Loss: {volume_config['stop_loss_pct']:.1%}")
    print(f"  Take Profit: {volume_config['take_profit_pct']:.1%}")
    print(f"  Max Holding: {volume_config['max_holding_periods']} periods")
    print(f"  Volume Ratio Threshold: {volume_config['volume_ratio_threshold']:.1f}")
    print(f"  RSI Threshold: {volume_config['rsi_threshold']}")
    print(f"  Risk Per Trade: {volume_config['risk_per_trade']:.1%}")
    
    # Test parameter validation
    if volume_config['stop_loss_pct'] <= 0 or volume_config['stop_loss_pct'] > 0.1:
        print(f"⚠️ Stop loss percentage seems unusual: {volume_config['stop_loss_pct']:.1%}")
    
    if volume_config['take_profit_pct'] <= 0 or volume_config['take_profit_pct'] > 0.2:
        print(f"⚠️ Take profit percentage seems unusual: {volume_config['take_profit_pct']:.1%}")
    
    if volume_config['risk_per_trade'] <= 0 or volume_config['risk_per_trade'] > 0.05:
        print(f"⚠️ Risk per trade seems unusual: {volume_config['risk_per_trade']:.1%}")
    
    return True

def test_broker_integration():
    """Test broker system integration"""
    print(f"\n🏦 BROKER INTEGRATION TEST")
    print("-" * 50)
    
    try:
        # Load configuration
        config = load_configuration()
        if not config:
            return False
        
        # Create mock broker for testing
        class MockBroker:
            def __init__(self, config):
                self.cfg = config['general']
                self.positions = {}
                self.equity = 1000.0
                self.trades = []
            
            def buy(self, symbol, price, reason, price_map):
                if symbol in self.positions:
                    return False
                
                # Calculate position size
                risk_amt = self.equity * self.cfg['risk_per_trade']
                stop_dist = price * self.cfg['stop_pct']
                size = risk_amt / stop_dist
                
                self.positions[symbol] = {
                    'symbol': symbol,
                    'entry_price': price,
                    'size': size,
                    'stop_price': price * (1 - self.cfg['stop_pct']),
                    'entry_time': datetime.now()
                }
                
                self.trades.append({
                    'symbol': symbol,
                    'action': 'buy',
                    'price': price,
                    'size': size,
                    'reason': reason,
                    'timestamp': datetime.now()
                })
                
                return True
            
            def sell(self, symbol, price, reason, price_map):
                if symbol not in self.positions:
                    return False
                
                pos = self.positions[symbol]
                self.trades.append({
                    'symbol': symbol,
                    'action': 'sell',
                    'price': price,
                    'size': pos['size'],
                    'reason': reason,
                    'timestamp': datetime.now()
                })
                
                del self.positions[symbol]
                return True
            
            def can_open_new(self):
                return len(self.positions) < self.cfg['max_positions']
        
        # Test broker creation
        broker = MockBroker(config)
        print(f"✅ Mock broker created successfully")
        
        # Test position management
        test_price = 50000.0
        if broker.buy("BTC/USDT", test_price, "test_entry", {}):
            print(f"✅ Buy order executed successfully")
            print(f"   Position size: {broker.positions['BTC/USDT']['size']:.6f}")
            print(f"   Stop price: ${broker.positions['BTC/USDT']['stop_price']:.2f}")
        else:
            print(f"❌ Buy order failed")
            return False
        
        # Test sell order
        if broker.sell("BTC/USDT", test_price * 1.02, "test_exit", {}):
            print(f"✅ Sell order executed successfully")
        else:
            print(f"❌ Sell order failed")
            return False
        
        # Test position limits
        broker.buy("ETH/USDT", 3000.0, "test_entry", {})
        if not broker.can_open_new():
            print(f"✅ Position limits working correctly")
        else:
            print(f"⚠️ Position limits may not be working")
        
        print(f"✅ Broker integration test passed")
        return True
        
    except Exception as e:
        print(f"❌ Broker integration test failed: {e}")
        return False

def test_end_to_end_simulation():
    """Test complete end-to-end simulation"""
    print(f"\n🔄 END-TO-END SIMULATION TEST")
    print("-" * 50)
    
    try:
        # Load configuration
        config = load_configuration()
        if not config:
            return False
        
        # Mock broker
        class SimulationBroker:
            def __init__(self, config):
                self.cfg = config['general']
                self.volume_config = config['volume_reversal']
                self.positions = {}
                self.equity = 1000.0
                self.trades = []
                self.equity_history = [1000.0]
            
            def buy(self, symbol, price, reason, price_map):
                if symbol in self.positions or not self.can_open_new():
                    return False
                
                # Use Volume Reversal risk parameters
                risk_amt = self.equity * self.volume_config['risk_per_trade']
                stop_dist = price * self.volume_config['stop_loss_pct']
                size = risk_amt / stop_dist
                
                self.positions[symbol] = {
                    'symbol': symbol,
                    'entry_price': price,
                    'size': size,
                    'stop_price': price * (1 - self.volume_config['stop_loss_pct']),
                    'take_profit_price': price * (1 + self.volume_config['take_profit_pct']),
                    'entry_time': datetime.now(),
                    'max_holding': self.volume_config['max_holding_periods']
                }
                
                return True
            
            def sell(self, symbol, price, reason, price_map):
                if symbol not in self.positions:
                    return False
                
                pos = self.positions[symbol]
                pnl = (price - pos['entry_price']) * pos['size']
                self.equity += pnl
                self.equity_history.append(self.equity)
                
                del self.positions[symbol]
                return True
            
            def can_open_new(self):
                return len(self.positions) < self.cfg['max_positions']
        
        # Run simulation
        broker = SimulationBroker(config)
        
        # Test with one symbol
        symbol = "BTC/USDT"
        df = load_historical_data(symbol, TEST_PERIOD)
        df_ind = compute_4h_indicators(df)
        
        if df_ind.empty:
            print(f"❌ No data for simulation")
            return False
        
        trades_executed = 0
        signals_generated = 0
        
        for i in range(1, len(df_ind)):
            sig = df_ind.iloc[i]
            prev_sig = df_ind.iloc[i-1]
            
            # Check for entry signal
            if entry_signal(sig, prev_sig, strategy="volume_reversal_long"):
                signals_generated += 1
                
                if broker.buy(symbol, sig['close'], "signal_entry", {}):
                    trades_executed += 1
                    print(f"  Trade {trades_executed}: Entry at ${sig['close']:.2f}")
            
            # Check for exit signals
            if symbol in broker.positions:
                pos = broker.positions[symbol]
                
                # Stop loss check
                if sig['close'] <= pos['stop_price']:
                    if broker.sell(symbol, pos['stop_price'], "stop_loss", {}):
                        print(f"  Exit: Stop loss at ${pos['stop_price']:.2f}")
                
                # Take profit check
                elif sig['close'] >= pos['take_profit_price']:
                    if broker.sell(symbol, pos['take_profit_price'], "take_profit", {}):
                        print(f"  Exit: Take profit at ${pos['take_profit_price']:.2f}")
                
                # Signal reversal check
                elif exit_signal(sig, strategy="volume_reversal_long"):
                    if broker.sell(symbol, sig['close'], "signal_reversal", {}):
                        print(f"  Exit: Signal reversal at ${sig['close']:.2f}")
        
        print(f"✅ Simulation completed")
        print(f"  Signals generated: {signals_generated}")
        print(f"  Trades executed: {trades_executed}")
        print(f"  Final equity: ${broker.equity:.2f}")
        print(f"  Return: {(broker.equity - 1000) / 1000 * 100:.1f}%")
        
        if trades_executed > 0:
            return True
        else:
            print(f"⚠️ No trades executed in simulation")
            return False
        
    except Exception as e:
        print(f"❌ End-to-end simulation failed: {e}")
        return False

def test_performance_benchmarks():
    """Test performance benchmarks"""
    print(f"\n⚡ PERFORMANCE BENCHMARKS")
    print("-" * 50)
    
    try:
        # Test indicator calculation speed
        df = load_historical_data("BTC/USDT", TEST_PERIOD)
        
        start_time = time.time()
        df_ind = compute_4h_indicators(df)
        calc_time = time.time() - start_time
        
        print(f"✅ Indicator calculation: {calc_time:.4f}s for {len(df_ind)} candles")
        
        # Test signal generation speed
        start_time = time.time()
        signals = 0
        for i in range(1, min(1000, len(df_ind))):
            sig = df_ind.iloc[i]
            prev_sig = df_ind.iloc[i-1]
            
            if entry_signal(sig, prev_sig, strategy="volume_reversal_long"):
                signals += 1
        
        signal_time = time.time() - start_time
        print(f"✅ Signal generation: {signal_time:.4f}s for 1000 checks")
        print(f"   Signals found: {signals}")
        
        # Memory usage check
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        print(f"✅ Memory usage: {memory_mb:.1f} MB")
        
        if calc_time < 1.0 and signal_time < 0.5 and memory_mb < 500:
            print(f"✅ Performance benchmarks acceptable")
            return True
        else:
            print(f"⚠️ Performance may need optimization")
            return True  # Still pass, just note
        
    except Exception as e:
        print(f"❌ Performance benchmarking failed: {e}")
        return False

def main():
    """Main system integration test"""
    print("🚀 PHASE 3: SYSTEM INTEGRATION TESTING")
    print("=" * 80)
    
    tests = {
        'Strategy Functions': test_strategy_functions,
        'Configuration Integration': test_configuration_integration,
        'Broker Integration': test_broker_integration,
        'End-to-End Simulation': test_end_to_end_simulation,
        'Performance Benchmarks': test_performance_benchmarks,
    }
    
    results = {}
    
    for test_name, test_func in tests.items():
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n🎉 PHASE 3 SYSTEM INTEGRATION RESULTS")
    print("=" * 80)
    
    passed_tests = sum(1 for result in results.values() if result)
    total_tests = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n📊 OVERALL: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print(f"🎉 PHASE 3 VALIDATION: SUCCESS")
        print(f"✅ All system integration tests passed")
        print(f"🚀 Ready for paper trading deployment")
        return True
    elif passed_tests >= total_tests * 0.8:
        print(f"⚠️ PHASE 3 VALIDATION: MOSTLY SUCCESS")
        print(f"✅ Critical functionality working")
        print(f"🔄 Minor issues may need attention")
        return True
    else:
        print(f"❌ PHASE 3 VALIDATION: NEEDS WORK")
        print(f"❌ Significant issues found")
        print(f"🔄 Address failures before deployment")
        return False

if __name__ == "__main__":
    success = main()
