import argparse
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity-log", default="paper_equity.csv")
    args = ap.parse_args()

    # Input validation
    if not os.path.exists(args.equity_log):
        print(f"Error: File {args.equity_log} not found")
        return
    
    if os.path.getsize(args.equity_log) == 0:
        print(f"Error: File {args.equity_log} is empty")
        return

    eq = pd.read_csv(args.equity_log)
    
    # Validate required columns
    if 'time_utc' not in eq.columns:
        print("Error: Missing 'time_utc' column")
        return
    
    if 'equity' not in eq.columns and 'equity_est_usdt' not in eq.columns:
        print("Error: Missing 'equity' or 'equity_est_usdt' column")
        return
    
    if eq.empty:
        print("Error: DataFrame is empty after reading")
        return

    eq["time_utc"] = pd.to_datetime(eq["time_utc"], utc=True, errors="coerce")

    col = "equity" if "equity" in eq.columns else "equity_est_usdt"
    eq[col] = pd.to_numeric(eq[col], errors="coerce")
    eq = eq.dropna(subset=[col]).sort_values("time_utc").reset_index(drop=True)
    
    if eq.empty:
        print("Error: No valid data after cleaning")
        return

    eq["peak"] = eq[col].cummax()
    # Guard against division by zero in drawdown calculation
    eq["dd_pct"] = (eq[col] / eq["peak"].replace(0, np.nan) - 1.0) * 100.0

    plt.figure()
    plt.plot(eq["time_utc"], eq[col])
    plt.title(f"Equity Curve ({args.equity_log})")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Equity")
    plt.tight_layout()
    plt.show()

    plt.figure()
    plt.plot(eq["time_utc"], eq["dd_pct"])
    plt.title("Drawdown (%)")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Drawdown %")
    plt.tight_layout()
    plt.show()

    if "realized_pnl_usdt" in eq.columns:
        eq["realized_pnl_usdt"] = pd.to_numeric(eq["realized_pnl_usdt"], errors="coerce")
        plt.figure()
        plt.plot(eq["time_utc"], eq["realized_pnl_usdt"])
        plt.title("Realized PnL (USDT)")
        plt.xlabel("Time (UTC)")
        plt.ylabel("Realized PnL")
        plt.tight_layout()
        plt.show()

    if "unrealized_pnl_est_usdt" in eq.columns:
        eq["unrealized_pnl_est_usdt"] = pd.to_numeric(eq["unrealized_pnl_est_usdt"], errors="coerce")
        plt.figure()
        plt.plot(eq["time_utc"], eq["unrealized_pnl_est_usdt"])
        plt.title("Unrealized PnL (Estimated, USDT)")
        plt.xlabel("Time (UTC)")
        plt.ylabel("Unrealized PnL")
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    main()
