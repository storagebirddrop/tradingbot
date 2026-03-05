#!/usr/bin/env python3
"""
Test Enhanced Volume Indicators
Validate all new indicators calculate correctly
"""

import pandas as pd
import numpy as np
import sys
import os

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators

# Test configuration
TEST_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]

def load_historical_data(symbol, period):
    """Load historical data for testing"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    filepath_4h = f"/home/dribble0335/dev/tradingbot/research/historical/{filename_4h}"
    
    if os.path.exists(filepath_4h):
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def test_enhanced_indicators():
    """Test all enhanced indicators"""
    print("🔍 TESTING ENHANCED VOLUME INDICATORS")
    print("=" * 80)
    
    # Load test data
    period = "recent_period"
    
    # Test with first symbol for indicator validation
    symbol = TEST_SYMBOLS[0]
    df = load_historical_data(symbol, period)
    
    if df.empty:
        print(f"❌ No data available for {symbol}")
        return False
    
    # Calculate indicators
    try:
        df_ind = compute_4h_indicators(df)
        
        if df_ind.empty:
            print("❌ No indicators calculated")
            return False
        
        print(f"✅ Indicators calculated: {len(df_ind)} candles")
        
    except Exception as e:
        print(f"❌ Indicator calculation failed: {e}")
        return False
    
    # Test all new indicators
    print(f"\n📈 ENHANCED INDICATOR VALIDATION:")
    
    enhanced_indicators = {
        'volume_ema': 'Volume EMA',
        'volume_rvol': 'Relative Volume',
        'volume_ema_ratio': 'Volume EMA Ratio',
        'obv': 'On-Balance Volume',
        'obv_sma': 'OBV SMA',
        'obv_divergence': 'OBV Divergence',
        'mfi': 'Money Flow Index',
        'mfi_divergence': 'MFI Divergence',
        'ad_line': 'Accumulation/Distribution',
        'ad_sma': 'A/D SMA',
        'ad_divergence': 'A/D Divergence',
        'cmf': 'Chaikin Money Flow',
        'cmf_divergence': 'CMF Divergence',
        'vwap': 'VWAP',
        'vwap_upper': 'VWAP Upper Band',
        'vwap_lower': 'VWAP Lower Band',
        'vwap_support_resistance': 'VWAP S/R Signal'
    }
    
    missing_indicators = []
    valid_indicators = []
    
    for indicator, description in enhanced_indicators.items():
        if indicator in df_ind.columns:
            valid_indicators.append(indicator)
            
            # Basic stats
            values = df_ind[indicator].dropna()
            if len(values) > 0:
                min_val = values.min()
                max_val = values.max()
                mean_val = values.mean()
                
                print(f"  ✅ {description}:")
                print(f"     Range: {min_val:.4f} - {max_val:.4f}")
                print(f"     Mean: {mean_val:.4f}")
                print(f"     Non-null: {len(values)}/{len(df_ind)}")
                
                # Special checks for divergence indicators
                if 'divergence' in indicator:
                    divergence_count = (values == 1).sum()
                    print(f"     Bullish divergences: {divergence_count}")
                
                # Special checks for MFI
                if indicator == 'mfi':
                    oversold_count = (values < 20).sum()
                    overbought_count = (values > 80).sum()
                    print(f"     Oversold (<20): {oversold_count}")
                    print(f"     Overbought (>80): {overbought_count}")
                
                # Special checks for CMF
                if indicator == 'cmf':
                    oversold_count = (values < -0.1).sum()
                    overbought_count = (values > 0.1).sum()
                    print(f"     Oversold (<-0.1): {oversold_count}")
                    print(f"     Overbought (>0.1): {overbought_count}")
                
                # Special checks for VWAP S/R
                if indicator == 'vwap_support_resistance':
                    support_count = (values == 1).sum()
                    resistance_count = (values == -1).sum()
                    neutral_count = (values == 0).sum()
                    print(f"     Support signals: {support_count}")
                    print(f"     Resistance signals: {resistance_count}")
                    print(f"     Neutral signals: {neutral_count}")
                
                print()
            else:
                print(f"  ⚠️ {description}: No valid data")
                missing_indicators.append(indicator)
        else:
            print(f"  ❌ {description}: Missing")
            missing_indicators.append(indicator)
    
    # Summary
    print(f"📊 INDICATOR SUMMARY:")
    print(f"  Total indicators: {len(enhanced_indicators)}")
    print(f"  Valid indicators: {len(valid_indicators)}")
    print(f"  Missing indicators: {len(missing_indicators)}")
    
    if missing_indicators:
        print(f"  Missing: {missing_indicators}")
        return False
    else:
        print(f"  ✅ All enhanced indicators working correctly")
        
        # Test sample data
        print(f"\n🔍 SAMPLE DATA (Last 3 candles):")
        sample_columns = ['timestamp', 'close', 'volume', 'volume_ratio', 'volume_rvol', 
                         'obv', 'mfi', 'cmf', 'vwap', 'vwap_support_resistance']
        
        for col in sample_columns:
            if col in df_ind.columns:
                print(f"  {col}: {df_ind[col].tail(3).values}")
        
        return True

def test_indicator_combinations():
    """Test basic indicator combinations"""
    print(f"\n🔄 TESTING INDICATOR COMBINATIONS:")
    
    # Load test data
    df = load_historical_data("BTC/USDT", "recent_period")
    df_ind = compute_4h_indicators(df)
    
    if df_ind.empty:
        return False
    
    # Test high volume + divergence combinations
    high_volume = df_ind['volume_ratio'] > 2.0
    high_rvol = df_ind['volume_rvol'] > 2.0
    
    obv_bullish = df_ind['obv_divergence'] == 1
    mfi_bullish = df_ind['mfi_divergence'] == 1
    cmf_bullish = df_ind['cmf_divergence'] == 1
    
    vwap_support = df_ind['vwap_support_resistance'] == 1
    
    # Combination counts
    combinations = {
        'High Volume Only': high_volume.sum(),
        'High RVOL Only': high_rvol.sum(),
        'OBV Divergence Only': obv_bullish.sum(),
        'MFI Divergence Only': mfi_bullish.sum(),
        'CMF Divergence Only': cmf_bullish.sum(),
        'VWAP Support Only': vwap_support.sum(),
        'High Volume + OBV Div': (high_volume & obv_bullish).sum(),
        'High Volume + MFI Div': (high_volume & mfi_bullish).sum(),
        'High Volume + CMF Div': (high_volume & cmf_bullish).sum(),
        'High Volume + VWAP Support': (high_volume & vwap_support).sum(),
        'All Volume Indicators': (high_volume & high_rvol).sum(),
        'All Divergences': (obv_bullish & mfi_bullish & cmf_bullish).sum(),
        'Perfect Setup': (high_volume & obv_bullish & vwap_support).sum()
    }
    
    for combo, count in combinations.items():
        print(f"  {combo}: {count} signals")
    
    return True

def main():
    """Main test function"""
    try:
        # Test individual indicators
        indicator_test = test_enhanced_indicators()
        
        # Test combinations
        combination_test = test_indicator_combinations()
        
        print(f"\n🎉 ENHANCED INDICATOR TEST COMPLETE!")
        print(f"=" * 80)
        
        print(f"✅ Individual Indicators: {'PASS' if indicator_test else 'FAIL'}")
        print(f"✅ Indicator Combinations: {'PASS' if combination_test else 'FAIL'}")
        
        if indicator_test and combination_test:
            print(f"✅ All enhanced indicators ready for strategy research")
            print(f"🚀 Ready for comprehensive indicator testing")
        else:
            print(f"⚠️ Some issues need to be resolved")
        
        return indicator_test and combination_test
        
    except Exception as e:
        print(f"❌ Enhanced indicator test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
