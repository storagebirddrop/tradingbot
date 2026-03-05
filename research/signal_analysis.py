#!/usr/bin/env python3
"""
Signal Analysis Framework for Short Strategy Research
Analyzes current exit signals as potential short entry points
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Tuple, Optional

# Import existing strategy functions
import sys
sys.path.append('/home/dribble0335/dev/tradingbot')
from strategy import compute_4h_indicators, compute_daily_regime, attach_regime_to_4h

class SignalAnalyzer:
    def __init__(self, data_path: str = "/home/dribble0335/dev/tradingbot/research"):
        self.data_path = data_path
        self.historical_path = os.path.join(data_path, "historical")
        self.regime_path = os.path.join(data_path, "regime")
        self.results_path = os.path.join(data_path, "results", "signal_analysis")
        os.makedirs(self.results_path, exist_ok=True)
        
        # Load metadata
        with open(os.path.join(data_path, "data_metadata.json"), 'r') as f:
            self.metadata = json.load(f)
        
        self.symbols = self.metadata['symbols']
        
    def load_data(self, symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load 4h and 1d data for a symbol"""
        # Load 4h data
        file_4h = f"{symbol.replace('/', '_')}_4h_recent.csv"
        df_4h = pd.read_csv(os.path.join(self.historical_path, file_4h))
        df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'])
        
        # Load 1d data for regime
        file_1d = f"{symbol.replace('/', '_')}_1d_recent.csv"
        df_1d = pd.read_csv(os.path.join(self.regime_path, file_1d))
        df_1d['timestamp'] = pd.to_datetime(df_1d['timestamp'])
        
        return df_4h, df_1d
    
    def generate_signals(self, df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> pd.DataFrame:
        """Generate short entry signals based on current exit logic"""
        
        # Calculate regime data
        regime_ma_len = 200
        regime_slope_len = 5
        confirm_days = 2
        
        df_regime = compute_daily_regime(
            df_1d, regime_ma_len, regime_slope_len, confirm_days
        )
        
        # Attach regime to 4h data
        df_combined = attach_regime_to_4h(df_4h, df_regime)
        
        # Generate signals
        df_combined['long_exit_signal'] = (
            (df_combined['close'] < df_combined['sma200']) |
            (df_combined['rsi'] > 70) |
            (df_combined['MACDh_12_26_9'] < 0)
        ).astype(bool)
        
        # Add research filters
        df_combined['adx_filter'] = (df_combined['adx'] > 25).astype(bool)
        df_combined['regime_filter'] = (~df_combined['risk_on']).astype(bool)
        
        # Combined short entry signals
        df_combined['short_entry_signal'] = (
            df_combined['long_exit_signal'] &
            df_combined['adx_filter'] &
            df_combined['regime_filter']
        ).astype(bool)
        
        # Generate short exit signals
        df_combined['short_exit_signal'] = (
            (df_combined['rsi'] < 30) |
            (df_combined['MACDh_12_26_9'] > 0) |
            (df_combined['close'] > df_combined['sma200'])
        ).astype(bool)
        
        return df_combined
    
    def analyze_signal_components(self, df: pd.DataFrame) -> Dict:
        """Analyze individual signal components"""
        
        components = {
            'sma_breakdown': (df['close'] < df['sma200']).astype(bool),
            'rsi_overbought': (df['rsi'] > 70).astype(bool),
            'macd_bearish': (df['MACDh_12_26_9'] < 0).astype(bool),
            'adx_strength': (df['adx'] > 25).astype(bool),
            'regime_filter': (~df['risk_on']).astype(bool)
        }
        
        results = {}
        
        for name, signals in components.items():
            performance = self.calculate_signal_performance(signals, df)
            results[name] = performance
        
        # Test combinations
        combinations = {
            'sma_rsi': components['sma_breakdown'] & components['rsi_overbought'],
            'sma_macd': components['sma_breakdown'] & components['macd_bearish'],
            'rsi_macd': components['rsi_overbought'] & components['macd_bearish'],
            'all_three': components['sma_breakdown'] & components['rsi_overbought'] & components['macd_bearish'],
            'with_filters': components['sma_breakdown'] & components['rsi_overbought'] & components['macd_bearish'] & components['adx_strength'] & components['regime_filter']
        }
        
        for name, signals in combinations.items():
            performance = self.calculate_signal_performance(signals, df)
            results[f"combo_{name}"] = performance
        
        return results
    
    def calculate_signal_performance(self, signals: pd.Series, df: pd.DataFrame) -> Dict:
        """Calculate performance metrics for given signals"""
        
        if not signals.any():
            return {
                'signal_count': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'avg_return': 0,
                'avg_holding_period': 0
            }
        
        # Find entry points
        entry_points = df[signals].copy()
        
        if entry_points.empty:
            return {
                'signal_count': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'avg_return': 0,
                'avg_holding_period': 0
            }
        
        # Simulate short trades (simplified)
        trades = []
        
        for idx, row in entry_points.iterrows():
            entry_price = row['close']
            entry_time = row['timestamp']
            
            # Find exit (next signal or end of data)
            future_data = df[df['timestamp'] > entry_time]
            if future_data.empty:
                continue
            
            # Simplified: exit on next short_exit_signal or after fixed period
            exit_signal = future_data['short_exit_signal'].fillna(False)
            exit_points = future_data[exit_signal]
            
            if not exit_points.empty:
                exit_point = exit_points.iloc[0]
                exit_price = exit_point['close']
                exit_time = exit_point['timestamp']
            else:
                # Exit after 10 periods (4h * 10 = 40h) if no exit signal
                if len(future_data) >= 10:
                    exit_point = future_data.iloc[9]
                    exit_price = exit_point['close']
                    exit_time = exit_point['timestamp']
                else:
                    exit_point = future_data.iloc[-1]
                    exit_price = exit_point['close']
                    exit_time = exit_point['timestamp']
            
            # Calculate return (short position profit)
            return_pct = (entry_price - exit_price) / entry_price * 100
            
            trades.append({
                'entry_time': entry_time,
                'entry_price': entry_price,
                'exit_time': exit_time,
                'exit_price': exit_price,
                'return_pct': return_pct,
                'holding_periods': (exit_time - entry_time).total_seconds() / 14400  # 4h periods
            })
        
        if not trades:
            return {
                'signal_count': len(entry_points),
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'avg_return': 0,
                'avg_holding_period': 0
            }
        
        # Calculate metrics
        trades_df = pd.DataFrame(trades)
        
        wins = trades_df[trades_df['return_pct'] > 0]
        losses = trades_df[trades_df['return_pct'] <= 0]
        
        win_rate = len(wins) / len(trades_df) * 100 if trades_df else 0
        
        # Profit factor
        gross_profit = wins['return_pct'].sum() if not wins.empty else 0
        gross_loss = abs(losses['return_pct'].sum()) if not losses.empty else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
        
        # Maximum drawdown (simplified)
        cumulative_returns = trades_df['return_pct'].cumsum()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max)
        max_drawdown = drawdown.min() if not drawdown.empty else 0
        
        # Sharpe ratio (simplified)
        returns_std = trades_df['return_pct'].std()
        sharpe_ratio = trades_df['return_pct'].mean() / returns_std if returns_std > 0 else 0
        
        return {
            'signal_count': len(entry_points),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'avg_return': trades_df['return_pct'].mean(),
            'avg_holding_period': trades_df['holding_periods'].mean()
        }
    
    def analyze_symbol(self, symbol: str) -> Dict:
        """Analyze signals for a specific symbol"""
        print(f"Analyzing {symbol}...")
        
        # Load data
        df_4h, df_1d = self.load_data(symbol)
        
        # Generate signals
        df_signals = self.generate_signals(df_4h, df_1d)
        
        # Analyze components
        component_results = self.analyze_signal_components(df_signals)
        
        # Analyze overall strategy
        overall_performance = self.calculate_signal_performance(
            df_signals['short_entry_signal'], df_signals
        )
        
        return {
            'symbol': symbol,
            'data_period': {
                'start': df_signals['timestamp'].min(),
                'end': df_signals['timestamp'].max(),
                'total_periods': len(df_signals)
            },
            'overall_performance': overall_performance,
            'component_analysis': component_results,
            'signal_frequency': {
                'short_entries': df_signals['short_entry_signal'].sum(),
                'short_exits': df_signals['short_exit_signal'].sum(),
                'entry_frequency': df_signals['short_entry_signal'].sum() / len(df_signals) * 100
            }
        }
    
    def run_full_analysis(self) -> Dict:
        """Run analysis for all symbols"""
        print("Starting signal analysis for all symbols...")
        
        all_results = {}
        
        for symbol in self.symbols:
            try:
                symbol_results = self.analyze_symbol(symbol)
                all_results[symbol] = symbol_results
                print(f"  {symbol}: Win rate {symbol_results['overall_performance']['win_rate']:.1f}%, "
                      f"Profit factor {symbol_results['overall_performance']['profit_factor']:.2f}")
            except Exception as e:
                print(f"  Error analyzing {symbol}: {e}")
                all_results[symbol] = {'error': str(e)}
        
        # Calculate aggregate results
        self.calculate_aggregate_results(all_results)
        
        # Save results
        self.save_results(all_results)
        
        return all_results
    
    def calculate_aggregate_results(self, all_results: Dict):
        """Calculate aggregate results across all symbols"""
        valid_results = {k: v for k, v in all_results.items() if 'error' not in v}
        
        if not valid_results:
            return
        
        # Aggregate metrics
        total_signals = sum(r['overall_performance']['signal_count'] for r in valid_results.values())
        total_wins = sum(r['overall_performance']['signal_count'] * r['overall_performance']['win_rate'] / 100 
                        for r in valid_results.values())
        
        aggregate_win_rate = total_wins / total_signals * 100 if total_signals > 0 else 0
        
        # Average other metrics
        avg_profit_factor = np.mean([r['overall_performance']['profit_factor'] 
                                    for r in valid_results.values() if r['overall_performance']['profit_factor'] != float('inf')])
        avg_sharpe = np.mean([r['overall_performance']['sharpe_ratio'] 
                             for r in valid_results.values()])
        avg_drawdown = np.mean([r['overall_performance']['max_drawdown'] 
                                for r in valid_results.values()])
        
        aggregate_results = {
            'total_symbols': len(valid_results),
            'total_signals': total_signals,
            'aggregate_win_rate': aggregate_win_rate,
            'avg_profit_factor': avg_profit_factor,
            'avg_sharpe_ratio': avg_sharpe,
            'avg_max_drawdown': avg_drawdown
        }
        
        all_results['aggregate'] = aggregate_results
    
    def save_results(self, results: Dict):
        """Save analysis results"""
        results_file = os.path.join(self.results_path, 'signal_analysis_results.json')
        
        # Convert datetime objects to strings for JSON serialization
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            return obj
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=convert_datetime)
        
        print(f"Results saved to {results_file}")
        
        # Generate summary report
        self.generate_summary_report(results)
    
    def generate_summary_report(self, results: Dict):
        """Generate a summary report of the analysis"""
        report_file = os.path.join(self.results_path, 'signal_analysis_summary.txt')
        
        with open(report_file, 'w') as f:
            f.write("SIGNAL ANALYSIS SUMMARY REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            if 'aggregate' in results:
                agg = results['aggregate']
                f.write("AGGREGATE RESULTS:\n")
                f.write(f"Total Symbols: {agg['total_symbols']}\n")
                f.write(f"Total Signals: {agg['total_signals']}\n")
                f.write(f"Aggregate Win Rate: {agg['aggregate_win_rate']:.1f}%\n")
                f.write(f"Average Profit Factor: {agg['avg_profit_factor']:.2f}\n")
                f.write(f"Average Sharpe Ratio: {agg['avg_sharpe_ratio']:.2f}\n")
                f.write(f"Average Max Drawdown: {agg['avg_max_drawdown']:.2f}%\n\n")
            
            f.write("INDIVIDUAL SYMBOL RESULTS:\n")
            f.write("-" * 30 + "\n")
            
            for symbol, result in results.items():
                if symbol == 'aggregate' or 'error' in result:
                    continue
                
                perf = result['overall_performance']
                f.write(f"\n{symbol}:\n")
                f.write(f"  Win Rate: {perf['win_rate']:.1f}%\n")
                f.write(f"  Profit Factor: {perf['profit_factor']:.2f}\n")
                f.write(f"  Sharpe Ratio: {perf['sharpe_ratio']:.2f}\n")
                f.write(f"  Max Drawdown: {perf['max_drawdown']:.2f}%\n")
                f.write(f"  Signal Count: {perf['signal_count']}\n")
                f.write(f"  Entry Frequency: {result['signal_frequency']['entry_frequency']:.2f}%\n")
        
        print(f"Summary report saved to {report_file}")

def main():
    """Main function to run signal analysis"""
    print("Starting signal analysis for short strategy research...")
    
    analyzer = SignalAnalyzer()
    results = analyzer.run_full_analysis()
    
    print("\nSignal analysis complete!")
    print(f"Results saved to: {analyzer.results_path}")
    
    # Print quick summary
    if 'aggregate' in results:
        agg = results['aggregate']
        print(f"\nQUICK SUMMARY:")
        print(f"  Aggregate Win Rate: {agg['aggregate_win_rate']:.1f}%")
        print(f"  Average Profit Factor: {agg['avg_profit_factor']:.2f}")
        print(f"  Average Sharpe Ratio: {agg['avg_sharpe_ratio']:.2f}")
        print(f"  Average Max Drawdown: {agg['avg_max_drawdown']:.2f}%")

if __name__ == "__main__":
    main()
