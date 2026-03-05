#!/usr/bin/env python3
"""
Phase 2: Volume Reversal Strategy Historical Validation
Comprehensive testing of the Volume Reversal strategy with trade simulation
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators, entry_signal, exit_signal

# Test configuration
TEST_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
TEST_PERIODS = {
    'recent_period': {'description': 'Recent risk-off (2024)', 'volatility': 'moderate'},
    'recovery_period': {'description': 'Post-bear recovery (2023)', 'volatility': 'moderate'},
    'bull_peak_bear': {'description': 'Bull peak to bear (2022)', 'volatility': 'high'},
    'covid_crash': {'description': 'COVID crash & recovery (2020-21)', 'volatility': 'extreme'},
}

# Volume Reversal strategy parameters
STRATEGY_PARAMS = {
    'stop_loss_pct': 0.02,
    'take_profit_pct': 0.04,
    'max_holding_periods': 20,
    'risk_per_trade': 0.01,
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

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods=20):
    """Simulate a trade with proper risk management"""
    stop_loss_price = entry_price * (1 - stop_loss_pct)
    take_profit_price = entry_price * (1 + take_profit_pct)
    
    for j in range(entry_idx + 1, min(entry_idx + max_holding_periods + 1, len(df))):
        current_candle = df.iloc[j]
        current_price = current_candle['close']
        
        # Check stop loss
        if current_price <= stop_loss_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': stop_loss_price,
                'exit_reason': 'stop_loss',
                'return_pct': -stop_loss_pct,
                'holding_periods': j - entry_idx
            }
        
        # Check take profit
        if current_price >= take_profit_price:
            return {
                'exit_time': current_candle['timestamp'],
                'exit_price': take_profit_price,
                'exit_reason': 'take_profit',
                'return_pct': take_profit_pct,
                'holding_periods': j - entry_idx
            }
        
        # Check signal reversal
        if j > entry_idx + 1:
            sig = current_candle
            
            # For long positions: exit if RSI > 70 or price crosses below SMA
            if (sig['rsi'] > 70) or (sig['close'] < sig['sma200_4h']):
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (current_price - entry_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
    
    # Max holding period reached
    final_price = df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['close']
    return_pct = (final_price - entry_price) / entry_price * 100
    
    return {
        'exit_time': df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['timestamp'],
        'exit_price': final_price,
        'exit_reason': 'max_holding',
        'return_pct': return_pct,
        'holding_periods': max_holding_periods
    }

def calculate_risk_metrics(trades):
    """Calculate comprehensive risk metrics"""
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_return': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'avg_holding_periods': 0,
            'stop_loss_rate': 0,
            'take_profit_rate': 0,
            'signal_reversal_rate': 0,
            'max_consecutive_losses': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0
        }
    
    returns = [trade['return_pct'] for trade in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    
    # Basic metrics
    total_trades = len(trades)
    win_rate = len(wins) / total_trades * 100
    avg_return = np.mean(returns)
    
    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    
    # Drawdown calculation
    cumulative_returns = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdowns = running_max - cumulative_returns
    max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
    
    # Exit reason rates
    exit_reasons = [trade['exit_reason'] for trade in trades]
    stop_loss_rate = exit_reasons.count('stop_loss') / total_trades * 100
    take_profit_rate = exit_reasons.count('take_profit') / total_trades * 100
    signal_reversal_rate = exit_reasons.count('signal_reversal') / total_trades * 100
    
    # Holding periods
    avg_holding_periods = np.mean([trade['holding_periods'] for trade in trades])
    
    # Consecutive losses
    loss_streaks = []
    current_streak = 0
    for r in returns:
        if r <= 0:
            current_streak += 1
        else:
            if current_streak > 0:
                loss_streaks.append(current_streak)
            current_streak = 0
    if current_streak > 0:
        loss_streaks.append(current_streak)
    max_consecutive_losses = max(loss_streaks) if loss_streaks else 0
    
    # Sharpe ratio
    if len(returns) > 1:
        sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = [r for r in returns if r < 0]
        downside_deviation = np.std(downside_returns) if len(downside_returns) > 1 else 0
        sortino_ratio = np.mean(returns) / downside_deviation if downside_deviation > 0 else 0
        
        # Calmar ratio (return / max drawdown)
        calmar_ratio = np.mean(returns) / max_drawdown if max_drawdown > 0 else 0
    else:
        sharpe_ratio = 0
        sortino_ratio = 0
        calmar_ratio = 0
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'avg_return': avg_return,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'avg_holding_periods': avg_holding_periods,
        'stop_loss_rate': stop_loss_rate,
        'take_profit_rate': take_profit_rate,
        'signal_reversal_rate': signal_reversal_rate,
        'max_consecutive_losses': max_consecutive_losses,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': calmar_ratio
    }

def test_volume_reversal_strategy():
    """Test Volume Reversal strategy with trade simulation"""
    print("🚀 PHASE 2: VOLUME REVERSAL STRATEGY VALIDATION")
    print("=" * 80)
    
    all_trades = []
    period_results = {}
    
    for period_name, period_info in TEST_PERIODS.items():
        print(f"\n📊 Testing {period_name}: {period_info['description']}")
        print("-" * 60)
        
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
            
            # Test strategy with trade simulation
            symbol_trades = []
            
            for i in range(1, len(df_ind)):
                sig = df_ind.iloc[i]
                prev_sig = df_ind.iloc[i-1]
                
                # Check for entry signal
                if entry_signal(sig, prev_sig, strategy="volume_reversal_long"):
                    entry_price = sig['close']
                    
                    # Simulate trade
                    outcome = simulate_trade(
                        df_ind, i, entry_price,
                        STRATEGY_PARAMS['stop_loss_pct'],
                        STRATEGY_PARAMS['take_profit_pct'],
                        STRATEGY_PARAMS['max_holding_periods']
                    )
                    
                    if outcome:
                        trade = {
                            'symbol': symbol,
                            'entry_time': sig['timestamp'],
                            'entry_price': entry_price,
                            'exit_time': outcome['exit_time'],
                            'exit_price': outcome['exit_price'],
                            'exit_reason': outcome['exit_reason'],
                            'return_pct': outcome['return_pct'],
                            'holding_periods': outcome['holding_periods'],
                            'volume_ratio': sig['volume_ratio'],
                            'rsi': sig['rsi'],
                            'volatility': sig['volatility']
                        }
                        
                        symbol_trades.append(trade)
            
            if symbol_trades:
                metrics = calculate_risk_metrics(symbol_trades)
                print(f"  {symbol}: {metrics['total_trades']} trades, "
                      f"Win Rate {metrics['win_rate']:.1f}%, "
                      f"Profit Factor {metrics['profit_factor']:.2f}")
                
                period_trades.extend(symbol_trades)
            else:
                print(f"  {symbol}: No trades generated")
        
        # Period metrics
        if period_trades:
            period_metrics = calculate_risk_metrics(period_trades)
            period_results[period_name] = period_metrics
            all_trades.extend(period_trades)
            
            print(f"  Period Total: {period_metrics['total_trades']} trades, "
                  f"Win Rate {period_metrics['win_rate']:.1f}%, "
                  f"Profit Factor {period_metrics['profit_factor']:.2f}")
        else:
            print(f"  Period Total: No trades generated")
    
    # Overall metrics
    if all_trades:
        overall_metrics = calculate_risk_metrics(all_trades)
        
        print(f"\n📊 OVERALL PERFORMANCE METRICS:")
        print(f"  Total Trades: {overall_metrics['total_trades']}")
        print(f"  Win Rate: {overall_metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {overall_metrics['profit_factor']:.2f}")
        print(f"  Average Return: {overall_metrics['avg_return']:.2f}%")
        print(f"  Max Drawdown: {overall_metrics['max_drawdown']:.1f}%")
        print(f"  Sharpe Ratio: {overall_metrics['sharpe_ratio']:.2f}")
        print(f"  Sortino Ratio: {overall_metrics['sortino_ratio']:.2f}")
        print(f"  Calmar Ratio: {overall_metrics['calmar_ratio']:.2f}")
        print(f"  Max Consecutive Losses: {overall_metrics['max_consecutive_losses']}")
        
        print(f"\n🔄 EXIT REASON BREAKDOWN:")
        print(f"  Stop Loss: {overall_metrics['stop_loss_rate']:.1f}%")
        print(f"  Take Profit: {overall_metrics['take_profit_rate']:.1f}%")
        print(f"  Signal Reversal: {overall_metrics['signal_reversal_rate']:.1f}%")
        print(f"  Max Holding: {100 - overall_metrics['stop_loss_rate'] - overall_metrics['take_profit_rate'] - overall_metrics['signal_reversal_rate']:.1f}%")
        
        # Success criteria check
        print(f"\n✅ SUCCESS CRITERIA CHECK:")
        criteria_met = []
        
        if overall_metrics['win_rate'] > 55:
            criteria_met.append("✅ Win Rate > 55%")
        else:
            criteria_met.append("❌ Win Rate < 55%")
            
        if overall_metrics['profit_factor'] > 1.5:
            criteria_met.append("✅ Profit Factor > 1.5")
        else:
            criteria_met.append("❌ Profit Factor < 1.5")
            
        if overall_metrics['max_drawdown'] < 25:
            criteria_met.append("✅ Max Drawdown < 25%")
        else:
            criteria_met.append("❌ Max Drawdown > 25%")
            
        if overall_metrics['sharpe_ratio'] > 0.5:
            criteria_met.append("✅ Sharpe Ratio > 0.5")
        else:
            criteria_met.append("❌ Sharpe Ratio < 0.5")
        
        for criterion in criteria_met:
            print(f"  {criterion}")
        
        # Final decision
        all_criteria_met = all("✅" in criterion for criterion in criteria_met)
        
        if all_criteria_met:
            print(f"\n🎉 PHASE 2 VALIDATION: SUCCESS")
            print(f"✅ Strategy meets all minimum criteria")
            print(f"🚀 Ready for Phase 3: System Integration Testing")
        else:
            print(f"\n⚠️ PHASE 2 VALIDATION: NEEDS ADJUSTMENT")
            print(f"❌ Strategy does not meet all criteria")
            print(f"🔄 Consider parameter adjustments")
        
        return {
            'overall_metrics': overall_metrics,
            'period_results': period_results,
            'criteria_met': criteria_met,
            'validation_passed': all_criteria_met
        }
    else:
        print(f"\n❌ No trades generated across all periods")
        return None

def main():
    """Main validation function"""
    try:
        result = test_volume_reversal_strategy()
        
        print(f"\n🎉 PHASE 2 VALIDATION COMPLETE!")
        print(f"=" * 80)
        
        if result and result['validation_passed']:
            print(f"✅ Volume Reversal strategy validated successfully")
            print(f"✅ Performance meets or exceeds research expectations")
            print(f"✅ Ready for Phase 3: System Integration Testing")
        else:
            print(f"⚠️ Strategy validation needs refinement")
            print(f"🔄 Review parameters and market conditions")
        
        return result
        
    except Exception as e:
        print(f"❌ Phase 2 validation failed: {e}")
        return None

if __name__ == "__main__":
    result = main()
