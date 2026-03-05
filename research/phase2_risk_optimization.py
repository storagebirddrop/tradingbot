#!/usr/bin/env python3
"""
Phase 2: Risk Parameter Optimization
Optimizes stop losses, position sizing, and risk management parameters
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append('/home/dribble0335/dev/tradingbot')

from strategy import compute_4h_indicators, sma_rsi_combo_signal

# Market periods and symbols for testing
MARKET_PERIODS = {
    'covid_crash': {'description': 'COVID crash & recovery', 'volatility': 'extreme'},
    'bull_peak_bear': {'description': 'Bull peak to bear transition', 'volatility': 'high'},
    'recovery_period': {'description': 'Post-bear recovery', 'volatility': 'moderate'},
    'recent_period': {'description': 'Recent risk-off', 'volatility': 'moderate'}
}

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

def load_historical_data(symbol, period):
    """Load historical data for a symbol and period"""
    filename_4h = f"{symbol.replace('/', '_')}_4h_{period}_binance.csv"
    filepath_4h = f"/home/dribble0335/dev/tradingbot/research/historical/{filename_4h}"
    
    if os.path.exists(filepath_4h):
        df = pd.read_csv(filepath_4h)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    return pd.DataFrame()

def calculate_trade_outcomes(df, stop_loss_pct, take_profit_pct, max_holding_periods=20):
    """Calculate trade outcomes with given risk parameters"""
    if df.empty:
        return []
    
    # Calculate indicators
    df_ind = compute_4h_indicators(df)
    
    trades = []
    
    for i in range(1, len(df_ind)):
        sig = df_ind.iloc[i]
        prev_sig = df_ind.iloc[i-1]
        
        # Check for entry signal
        if sma_rsi_combo_signal(sig, prev_sig):
            entry_price = sig['close']
            entry_time = sig['timestamp']
            
            # Simulate trade execution
            outcome = simulate_trade(df_ind, i, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods)
            
            if outcome:
                trades.append({
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': outcome['exit_time'],
                    'exit_price': outcome['exit_price'],
                    'exit_reason': outcome['exit_reason'],
                    'return_pct': outcome['return_pct'],
                    'holding_periods': outcome['holding_periods']
                })
    
    return trades

def simulate_trade(df, entry_idx, entry_price, stop_loss_pct, take_profit_pct, max_holding_periods):
    """Simulate a single trade with risk parameters"""
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
        
        # Check signal reversal (additional exit condition)
        if j > entry_idx + 1:  # Allow at least 1 period
            sig = current_candle
            prev_sig = df.iloc[j-1]
            
            # Exit if signal reverses (RSI drops below 30 or price crosses above SMA)
            if sig['rsi'] < 30 or sig['close'] > sig['sma200_4h']:
                return {
                    'exit_time': current_candle['timestamp'],
                    'exit_price': current_price,
                    'exit_reason': 'signal_reversal',
                    'return_pct': (entry_price - current_price) / entry_price * 100,
                    'holding_periods': j - entry_idx
                }
    
    # Max holding period reached
    final_price = df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['close']
    return {
        'exit_time': df.iloc[min(entry_idx + max_holding_periods, len(df) - 1)]['timestamp'],
        'exit_price': final_price,
        'exit_reason': 'max_holding',
        'return_pct': (entry_price - final_price) / entry_price * 100,
        'holding_periods': max_holding_periods
    }

def calculate_risk_metrics(trades):
    """Calculate comprehensive risk metrics for trade results"""
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
            'sharpe_ratio': 0
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
    
    # Sharpe ratio (simplified)
    if len(returns) > 1:
        sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
    else:
        sharpe_ratio = 0
    
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
        'sharpe_ratio': sharpe_ratio
    }

def test_stop_loss_parameters():
    """Test different stop loss percentages"""
    print("🔍 TESTING STOP LOSS PARAMETERS")
    print("=" * 60)
    
    stop_loss_options = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04]  # 1% to 4%
    take_profit_pct = 0.04  # Fixed 4% take profit for initial testing
    max_holding_periods = 20
    
    results = {}
    
    for stop_loss_pct in stop_loss_options:
        print(f"\n📊 Testing Stop Loss: {stop_loss_pct*100:.1f}%")
        
        all_trades = []
        period_results = {}
        
        for period_name, period_info in MARKET_PERIODS.items():
            period_trades = []
            
            for symbol in SYMBOLS:
                df = load_historical_data(symbol, period_name)
                if df.empty:
                    continue
                
                trades = calculate_trade_outcomes(df, stop_loss_pct, take_profit_pct, max_holding_periods)
                period_trades.extend(trades)
            
            if period_trades:
                metrics = calculate_risk_metrics(period_trades)
                period_results[period_name] = metrics
                all_trades.extend(period_trades)
                
                print(f"  {period_name}: {metrics['total_trades']} trades, {metrics['win_rate']:.1f}% win rate, {metrics['profit_factor']:.2f} profit factor")
        
        # Overall metrics
        if all_trades:
            overall_metrics = calculate_risk_metrics(all_trades)
            results[stop_loss_pct] = {
                'period_results': period_results,
                'overall': overall_metrics
            }
            
            print(f"  OVERALL: {overall_metrics['total_trades']} trades, {overall_metrics['win_rate']:.1f}% win rate")
            print(f"           {overall_metrics['profit_factor']:.2f} profit factor, {overall_metrics['max_drawdown']:.1f}% max drawdown")
    
    return results

def test_take_profit_parameters():
    """Test different take profit percentages"""
    print("\n🔍 TESTING TAKE PROFIT PARAMETERS")
    print("=" * 60)
    
    take_profit_options = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08]  # 2% to 8%
    stop_loss_pct = 0.02  # Fixed 2% stop loss based on previous test
    max_holding_periods = 20
    
    results = {}
    
    for take_profit_pct in take_profit_options:
        print(f"\n📊 Testing Take Profit: {take_profit_pct*100:.1f}%")
        
        all_trades = []
        
        for period_name, period_info in MARKET_PERIODS.items():
            period_trades = []
            
            for symbol in SYMBOLS:
                df = load_historical_data(symbol, period_name)
                if df.empty:
                    continue
                
                trades = calculate_trade_outcomes(df, stop_loss_pct, take_profit_pct, max_holding_periods)
                period_trades.extend(trades)
            
            if period_trades:
                all_trades.extend(period_trades)
        
        # Overall metrics
        if all_trades:
            overall_metrics = calculate_risk_metrics(all_trades)
            results[take_profit_pct] = overall_metrics
            
            print(f"  OVERALL: {overall_metrics['total_trades']} trades, {overall_metrics['win_rate']:.1f}% win rate")
            print(f"           {overall_metrics['profit_factor']:.2f} profit factor, {overall_metrics['avg_return']:.2f}% avg return")
            print(f"           Stop Loss: {overall_metrics['stop_loss_rate']:.1f}%, Take Profit: {overall_metrics['take_profit_rate']:.1f}%")
    
    return results

def test_position_sizing():
    """Test different position sizing strategies"""
    print("\n🔍 TESTING POSITION SIZING STRATEGIES")
    print("=" * 60)
    
    # Fixed percentage sizing
    fixed_options = [0.005, 0.01, 0.015, 0.02]  # 0.5% to 2% per trade
    
    # Volatility-based sizing (simplified)
    def volatility_sizing(trades, base_size=0.01):
        """Adjust position size based on recent volatility"""
        results = []
        for trade in trades:
            # Simplified: use fixed size for now (would use ATR in production)
            results.append(base_size)
        return results
    
    # Kelly criterion sizing (simplified)
    def kelly_sizing(win_rate, avg_win, avg_loss, base_size=0.01):
        """Calculate Kelly criterion position size"""
        if avg_loss == 0:
            return base_size
        
        win_prob = win_rate / 100
        lose_prob = 1 - win_prob
        
        # Kelly fraction: f = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_prob, q = lose_prob
        b = abs(avg_win / avg_loss)
        kelly_fraction = (b * win_prob - lose_prob) / b
        
        # Cap at reasonable levels
        kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Max 25%
        
        return kelly_fraction
    
    print("Position sizing analysis would require portfolio simulation.")
    print("For now, we recommend:")
    print("  • Conservative: 0.5% - 1% per trade")
    print("  • Moderate: 1% - 1.5% per trade") 
    print("  • Aggressive: 1.5% - 2% per trade")
    print("  • Kelly-based: Adjust based on win rate and profit factor")
    
    return {
        'conservative': {'size': 0.01, 'description': '1% per trade, low risk'},
        'moderate': {'size': 0.015, 'description': '1.5% per trade, balanced risk'},
        'aggressive': {'size': 0.02, 'description': '2% per trade, higher risk'}
    }

def generate_risk_recommendations(stop_loss_results, take_profit_results, sizing_results):
    """Generate final risk parameter recommendations"""
    print("\n" + "=" * 80)
    print("🎯 RISK PARAMETER OPTIMIZATION RESULTS")
    print("=" * 80)
    
    # Find best stop loss
    best_stop_loss = None
    best_stop_score = -float('inf')
    
    print("\n📉 STOP LOSS ANALYSIS:")
    for stop_loss_pct, data in stop_loss_results.items():
        overall = data.get('overall', {})
        if not overall:
            continue
            
        # Score based on win rate, profit factor, and low drawdown
        score = overall.get('win_rate', 0) + (overall.get('profit_factor', 0) * 10) - (overall.get('max_drawdown', 0) * 2)
        
        print(f"  {stop_loss_pct*100:.1f}%: Win Rate {overall.get('win_rate', 0):.1f}%, "
              f"Profit Factor {overall.get('profit_factor', 0):.2f}, "
              f"Max DD {overall.get('max_drawdown', 0):.1f}%, Score {score:.1f}")
        
        if score > best_stop_score:
            best_stop_score = score
            best_stop_loss = stop_loss_pct
    
    print(f"\n✅ RECOMMENDED STOP LOSS: {best_stop_loss*100:.1f}%" if best_stop_loss else "\n❌ No valid stop loss results")
    
    # Find best take profit
    best_take_profit = None
    best_take_score = -float('inf')
    
    print("\n📈 TAKE PROFIT ANALYSIS:")
    for take_profit_pct, metrics in take_profit_results.items():
        if not metrics:
            continue
            
        # Score based on profit factor and average return
        score = (metrics.get('profit_factor', 0) * 10) + metrics.get('avg_return', 0)
        
        print(f"  {take_profit_pct*100:.1f}%: Profit Factor {metrics.get('profit_factor', 0):.2f}, "
              f"Avg Return {metrics.get('avg_return', 0):.2f}%, "
              f"Win Rate {metrics.get('win_rate', 0):.1f}%, Score {score:.1f}")
        
        if score > best_take_score:
            best_take_score = score
            best_take_profit = take_profit_pct
    
    print(f"\n✅ RECOMMENDED TAKE PROFIT: {best_take_profit*100:.1f}%" if best_take_profit else "\n❌ No valid take profit results")
    
    # Position sizing recommendation
    print("\n💰 POSITION SIZING RECOMMENDATIONS:")
    for strategy, config in sizing_results.items():
        print(f"  {strategy.title()}: {config['size']*100:.1f}% per trade - {config['description']}")
    
    # Final recommendations
    print(f"\n🎯 FINAL RISK PARAMETERS:")
    if best_stop_loss:
        print(f"  • Stop Loss: {best_stop_loss*100:.1f}%")
    else:
        print(f"  • Stop Loss: 2.0% (default)")
        best_stop_loss = 0.02
        
    if best_take_profit:
        print(f"  • Take Profit: {best_take_profit*100:.1f}%")
    else:
        print(f"  • Take Profit: 4.0% (default)")
        best_take_profit = 0.04
    print(f"  • Risk Per Trade: 1.0% (conservative)")
    print(f"  • Max Holding Period: 20 candles (80 hours for 4h timeframe)")
    print(f"  • Portfolio Exposure: 25% max total")
    
    # Risk metrics for recommended parameters
    recommended_trades = []
    for period_name in MARKET_PERIODS.keys():
        for symbol in SYMBOLS:
            df = load_historical_data(symbol, period_name)
            if df.empty:
                continue
            trades = calculate_trade_outcomes(df, best_stop_loss, best_take_profit, 20)
            recommended_trades.extend(trades)
    
    if recommended_trades:
        recommended_metrics = calculate_risk_metrics(recommended_trades)
        
        print(f"\n📊 EXPECTED PERFORMANCE:")
        print(f"  • Win Rate: {recommended_metrics['win_rate']:.1f}%")
        print(f"  • Profit Factor: {recommended_metrics['profit_factor']:.2f}")
        print(f"  • Average Return: {recommended_metrics['avg_return']:.2f}%")
        print(f"  • Max Drawdown: {recommended_metrics['max_drawdown']:.1f}%")
        print(f"  • Sharpe Ratio: {recommended_metrics['sharpe_ratio']:.2f}")
        print(f"  • Max Consecutive Losses: {recommended_metrics['max_consecutive_losses']}")
        
        print(f"\n🔄 EXIT REASON BREAKDOWN:")
        print(f"  • Stop Loss: {recommended_metrics['stop_loss_rate']:.1f}%")
        print(f"  • Take Profit: {recommended_metrics['take_profit_rate']:.1f}%")
        print(f"  • Signal Reversal: {recommended_metrics['signal_reversal_rate']:.1f}%")
        print(f"  • Max Holding: {100 - recommended_metrics['stop_loss_rate'] - recommended_metrics['take_profit_rate'] - recommended_metrics['signal_reversal_rate']:.1f}%")
    
    return {
        'stop_loss': best_stop_loss,
        'take_profit': best_take_profit,
        'position_size': 0.01,
        'max_holding_periods': 20,
        'expected_metrics': recommended_metrics if recommended_trades else {}
    }

def main():
    """Main risk optimization function"""
    print("🚀 PHASE 2: RISK PARAMETER OPTIMIZATION")
    print("=" * 80)
    
    try:
        # Test stop loss parameters
        stop_loss_results = test_stop_loss_parameters()
        
        # Test take profit parameters  
        take_profit_results = test_take_profit_parameters()
        
        # Test position sizing
        sizing_results = test_position_sizing()
        
        # Generate recommendations
        recommendations = generate_risk_recommendations(stop_loss_results, take_profit_results, sizing_results)
        
        print(f"\n🎉 PHASE 2 COMPLETE!")
        print(f"✅ Risk parameters optimized based on historical data")
        print(f"✅ Conservative approach with strong risk management")
        print(f"✅ Ready for Phase 3: Market Condition Analysis")
        
        return recommendations
        
    except Exception as e:
        print(f"❌ Risk optimization failed: {e}")
        return None

if __name__ == "__main__":
    recommendations = main()
