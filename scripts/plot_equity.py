import argparse
import pandas as pd
import matplotlib.pyplot as plt

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity-log", default="paper_equity.csv")
    args = ap.parse_args()

    eq = pd.read_csv(args.equity_log)
    eq["time_utc"] = pd.to_datetime(eq["time_utc"], utc=True, errors="coerce")

    col = "equity" if "equity" in eq.columns else "equity_est_usdt"
    eq[col] = pd.to_numeric(eq[col], errors="coerce")
    eq = eq.dropna(subset=[col]).sort_values("time_utc").reset_index(drop=True)

    eq["peak"] = eq[col].cummax()
    eq["dd_pct"] = (eq[col] / eq["peak"] - 1.0) * 100.0

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
