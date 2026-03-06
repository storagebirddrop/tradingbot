import argparse
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity-log", default="paper_equity.csv")
    ap.add_argument("--starting", type=float, default=50.0)
    args = ap.parse_args()

    eq = pd.read_csv(args.equity_log)
    eq["time_utc"] = pd.to_datetime(eq["time_utc"], utc=True, errors="coerce")

    col = "equity" if "equity" in eq.columns else "equity_est_usdt"
    eq[col] = pd.to_numeric(eq[col], errors="coerce")
    eq = eq.dropna(subset=[col]).sort_values("time_utc").reset_index(drop=True)

    eq["peak"] = eq[col].cummax()
    eq["dd_pct"] = (eq[col] / eq["peak"] - 1.0) * 100.0

    final_equity = float(eq[col].iloc[-1])
    ret_pct = (final_equity / args.starting - 1) * 100.0
    max_dd = float(eq["dd_pct"].min())

    print("=== EQUITY SUMMARY ===")
    print(f"Equity log       : {args.equity_log}")
    print(f"Start equity     : {args.starting:.2f}")
    print(f"Final equity     : {final_equity:.2f}")
    print(f"Return           : {ret_pct:+.2f}%")
    print(f"Max drawdown     : {max_dd:.2f}%")

    if "realized_pnl_usdt" in eq.columns:
        eq["realized_pnl_usdt"] = pd.to_numeric(eq["realized_pnl_usdt"], errors="coerce")
        realized_last = float(eq["realized_pnl_usdt"].dropna().iloc[-1]) if eq["realized_pnl_usdt"].notna().any() else 0.0
        print(f"Realized PnL     : {realized_last:+.4f} USDT")

    if "unrealized_pnl_est_usdt" in eq.columns:
        eq["unrealized_pnl_est_usdt"] = pd.to_numeric(eq["unrealized_pnl_est_usdt"], errors="coerce")
        unreal_last = float(eq["unrealized_pnl_est_usdt"].dropna().iloc[-1]) if eq["unrealized_pnl_est_usdt"].notna().any() else 0.0
        print(f"Unrealized (est) : {unreal_last:+.4f} USDT")

if __name__ == "__main__":
    main()
