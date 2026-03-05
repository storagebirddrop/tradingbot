import argparse
import pandas as pd

def report_from_paper(trades_log: str):
    df = pd.read_csv(trades_log)
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True, errors="coerce")

    sells = df[(df["side"] == "SELL") & df["pnl"].notna()].copy()
    sells["pnl"] = pd.to_numeric(sells["pnl"], errors="coerce")
    sells = sells.dropna(subset=["pnl"])

    realized = float(sells["pnl"].sum()) if len(sells) else 0.0
    winrate = float((sells["pnl"] > 0).mean() * 100) if len(sells) else 0.0

    print("=== TRADES SUMMARY (PAPER) ===")
    print(f"Trades log       : {trades_log}")
    print(f"Closed trades    : {len(sells)}")
    print(f"Win rate         : {winrate:.1f}%")
    print(f"Realized PnL     : {realized:+.6f}")
    if len(sells):
        print("\\n=== Realized PnL by symbol ===")
        print(sells.groupby("symbol")["pnl"].sum().sort_values(ascending=False).to_string())

def report_from_fills(fills_log: str):
    df = pd.read_csv(fills_log)
    if df.empty:
        print("No fills found.")
        return

    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df["realized_delta_usdt"] = pd.to_numeric(df["realized_delta_usdt"], errors="coerce").fillna(0.0)

    realized = float(df["realized_delta_usdt"].sum())
    sells = df[df["side"].str.lower() == "sell"].copy()
    winrate = float((sells["realized_delta_usdt"] > 0).mean() * 100) if len(sells) else 0.0

    print("=== FILLS SUMMARY (EXCHANGE) ===")
    print(f"Fills log        : {fills_log}")
    print(f"Fills            : {len(df)}")
    print(f"Sell fills       : {len(sells)}")
    print(f"Win rate (sells) : {winrate:.1f}%")
    print(f"Realized PnL     : {realized:+.6f} USDT")

    print("\\n=== Realized PnL by symbol ===")
    print(df.groupby("symbol")["realized_delta_usdt"].sum().sort_values(ascending=False).to_string())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades-log", default="paper_trades.csv")
    ap.add_argument("--fills-log", default=None)
    args = ap.parse_args()

    if args.fills_log:
        report_from_fills(args.fills_log)
        return

    df = pd.read_csv(args.trades_log, nrows=5)
    if "pnl" in df.columns:
        report_from_paper(args.trades_log)
    else:
        print("Exchange order log detected. Provide --fills-log to compute realized PnL from fills.")

if __name__ == "__main__":
    main()
