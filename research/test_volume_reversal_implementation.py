#!/usr/bin/env python3
"""
Phase 1: Volume Reversal Strategy Implementation Test
Test the implemented Volume Reversal strategy with historical data
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators, volume_reversal_long_signal, entry_signal, exit_signal

# Test configuration
TEST_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TEST_PERIODS = {
    'recent_period': 'Recent risk-off (2024)',
    'recovery_period': 'Post-bear recovery (2023)',
    'bull_peak_bear': 'Bull peak to bear (2022)',
    'covid_crash': 'COVID crash & recovery (2020-21)',
}

def load_historical_data(symbol, period):
    """Load historical data for testing"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    filepath_4h = f"/home/dribble0335/dev/tradingbot/research/historical/{filename_4h}"
    
    if os.path.exists(filepath_4h):
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def test_volume_reversal_strategy():
    """Test the Volume Reversal strategy implementation"""
    print("🚀 PHASE 1: VOLUME REVERSAL IMPLEMENTATION TEST")
    print("=" * 80)
    
    total_signals = 0
    period_results = {}
    
    for period_name, period_desc in TEST_PERIODS.items():
        print(f"\n📊 Testing {period_name}: {period_desc}")
        print("-" * 60)
        
        period_signals = 0
        period_trades = []
        
        for symbol in TEST_SYMBOLS:
            df = load_historical_data(symbol, period_name)
            if df.empty:
                print(f"  {symbol}: No data available")
                continue
            
            # Calculate indicators
            df_ind = compute_4h_indicators(df)
            
            if df_ind.empty:
                print(f"  {symbol}: No indicators calculated")
                continue
            
            # Test strategy signals
            symbol_signals = 0
            symbol_trades = []
            
            for i in range(1, len(df_ind)):
                sig = df_ind.iloc[i]
                prev_sig = df_ind.iloc[i-1]
                
                # Test Volume Reversal signal
                volume_signal = volume_reversal_long_signal(sig, prev_sig)
                
                # Test entry_signal function with Volume Reversal
                entry_signal_result = entry_signal(sig, prev_sig, strategy="volume_reversal_long")
                
                # Test exit_signal function
                exit_signal_result = exit_signal(sig, strategy="volume_reversal_long")
                
                if volume_signal:
                    symbol_signals += 1
                    symbol_trades.append({
                        'timestamp': sig['timestamp'],
                        'symbol': symbol,
                        'close': sig['close'],
                        'volume_ratio': sig['volume_ratio'],
                        'rsi': sig['rsi'],
                        'volatility': sig['volatility'],
                        'entry_signal': entry_signal_result,
                        'exit_signal': exit_signal_result
                    })
            
            print(f"  {symbol}: {symbol_signals} signals, Entry Signal: {entry_signal_result if symbol_signals > 0 else 'N/A'}")
            period_signals += symbol_signals
            period_trades.extend(symbol_trades)
        
        period_results[period_name] = {
            'signals': period_signals,
            'trades': period_trades
        }
        total_signals += period_signals
        
        print(f"  Period Total: {period_signals} signals")
    
    print(f"\n📈 IMPLEMENTATION TEST RESULTS:")
    print(f"  Total Signals Generated: {total_signals}")
    print(f"  Average Signals per Period: {total_signals / len(TEST_PERIODS):.1f}")
    
    # Validate signal quality
    print(f"\n🔍 SIGNAL QUALITY ANALYSIS:")
    for period_name, results in period_results.items():
        trades = results['trades']
        if trades:
            avg_volume_ratio = np.mean([t['volume_ratio'] for t in trades])
            avg_rsi = np.mean([t['rsi'] for t in trades])
            avg_volatility = np.mean([t['volatility'] for t in trades])
            
            print(f"  {period_name}:")
            print(f"    Avg Volume Ratio: {avg_volume_ratio:.2f}")
            print(f"    Avg RSI: {avg_rsi:.1f}")
            print(f"    Avg Volatility: {avg_volatility:.4f}")
        else:
            print(f"  {period_name}: No signals generated")
    
    # Test strategy function integration
    print(f"\n🔧 STRATEGY FUNCTION INTEGRATION:")
    test_df = load_historical_data("BTC/USDT", "recent_period")
    if not test_df.empty:
        test_ind = compute_4h_indicators(test_df)
        if len(test_ind) > 1:
            test_sig = test_ind.iloc[100]  # Test with a specific candle
            test_prev_sig = test_ind.iloc[99]
            
            # Test all strategy functions
            volume_signal = volume_reversal_long_signal(test_sig, test_prev_sig)
            entry_signal_result = entry_signal(test_sig, test_prev_sig, strategy="volume_reversal_long")
            exit_signal_result = exit_signal(test_sig, strategy="volume_reversal_long")
            
            print(f"  Volume Reversal Signal: {volume_signal}")
            print(f"  Entry Signal (Volume Reversal): {entry_signal_result}")
            print(f"  Exit Signal (Volume Reversal): {exit_signal_result}")
            
            # Test other strategies for comparison
            sma_signal = entry_signal(test_sig, test_prev_sig, strategy="sma_rsi_combo")
            impulse_signal = entry_signal(test_sig, test_prev_sig, strategy="sma_rsi_impulse")
            
            print(f"  Entry Signal (SMA RSI Combo): {sma_signal}")
            print(f"  Entry Signal (SMA RSI Impulse): {impulse_signal}")
    
    return total_signals, period_results

def test_configuration_loading():
    """Test configuration loading for Volume Reversal"""
    print(f"\n⚙️ CONFIGURATION LOADING TEST:")
    
    try:
        import json
        with open('/home/dribble0335/dev/tradingbot/config.json', 'r') as f:
            config = json.load(f)
        
        # Check if Volume Reversal config exists
        local_paper = config['profiles']['local_paper']
        volume_config = local_paper.get('volume_reversal_strategy', {})
        
        print(f"  Volume Reversal Config Found: {bool(volume_config)}")
        
        if volume_config:
            print(f"  Enabled: {volume_config.get('enabled', False)}")
            print(f"  Stop Loss: {volume_config.get('stop_loss_pct', 0):.1%}")
            print(f"  Take Profit: {volume_config.get('take_profit_pct', 0):.1%}")
            print(f"  Volume Ratio Threshold: {volume_config.get('volume_ratio_threshold', 0):.1f}")
            print(f"  RSI Threshold: {volume_config.get('rsi_threshold', 0)}")
            print(f"  Max Holding Periods: {volume_config.get('max_holding_periods', 0)}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Configuration loading failed: {e}")
        return False

def test_indicator_calculation():
    """Test that all required indicators are calculated correctly"""
    print(f"\n📊 INDICATOR CALCULATION TEST:")
    
    try:
        df = load_historical_data("BTC/USDT", "recent_period")
        if df.empty:
            print(f"  ❌ No test data available")
            return False
        
        df_ind = compute_4h_indicators(df)
        
        if df_ind.empty:
            print(f"  ❌ No indicators calculated")
            return False
        
        # Check required indicators
        required_indicators = [
            'sma200_4h', 'rsi', 'adx', 'volume_sma', 
            'volume_ratio', 'price_change', 'volatility'
        ]
        
        missing_indicators = []
        for indicator in required_indicators:
            if indicator not in df_ind.columns:
                missing_indicators.append(indicator)
        
        if missing_indicators:
            print(f"  ❌ Missing indicators: {missing_indicators}")
            return False
        
        print(f"  ✅ All required indicators present")
        print(f"  ✅ Data points: {len(df_ind)}")
        print(f"  ✅ Volume Ratio Range: {df_ind['volume_ratio'].min():.2f} - {df_ind['volume_ratio'].max():.2f}")
        print(f"  ✅ RSI Range: {df_ind['rsi'].min():.1f} - {df_ind['rsi'].max():.1f}")
        print(f"  ✅ Volatility Range: {df_ind['volatility'].min():.4f} - {df_ind['volatility'].max():.4f}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Indicator calculation failed: {e}")
        return False

def main():
    """Main implementation test function"""
    try:
        print("🔍 VOLUME REVERSAL STRATEGY IMPLEMENTATION VALIDATION")
        print("=" * 80)
        
        # Test indicator calculation
        indicator_test = test_indicator_calculation()
        
        # Test configuration loading
        config_test = test_configuration_loading()
        
        # Test strategy implementation
        total_signals, period_results = test_volume_reversal_strategy()
        
        # Overall results
        print(f"\n🎉 PHASE 1 IMPLEMENTATION TEST COMPLETE!")
        print(f"=" * 80)
        
        print(f"✅ Indicator Calculation: {'PASS' if indicator_test else 'FAIL'}")
        print(f"✅ Configuration Loading: {'PASS' if config_test else 'FAIL'}")
        print(f"✅ Strategy Implementation: {'PASS' if total_signals > 0 else 'NEEDS ADJUSTMENT'}")
        
        if total_signals > 0:
            print(f"✅ Total Signals Generated: {total_signals}")
            print(f"✅ Strategy ready for Phase 2 validation")
        else:
            print(f"⚠️ No signals generated - strategy parameters may need adjustment")
            print(f"🔄 Consider relaxing volume ratio or RSI thresholds")
        
        return {
            'indicator_test': indicator_test,
            'config_test': config_test,
            'total_signals': total_signals,
            'period_results': period_results,
            'ready_for_phase2': total_signals > 0
        }
        
    except Exception as e:
        print(f"❌ Implementation test failed: {e}")
        return None

if __name__ == "__main__":
    result = main()
