"""
Train a 3-state GaussianHMM on daily OHLCV to classify market regimes.

States: BULL / SIDEWAYS / BEAR
Features: daily return, log-volume z-score, ATR/close ratio, 5-day return

Outputs:
  models/regime_hmm.pkl          — trained HMM model
  models/regime_hmm_states.json  — state label mapping + config

Usage:
    python3 research/train_regime_hmm.py --symbol ETH --data-dir data/
    python3 research/train_regime_hmm.py --symbol ETH --data-dir data/ --n-states 3 --plot
"""

import os
import sys
import argparse
import json
import pickle
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def load_daily_ohlcv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    return df


def compute_features(df: pd.DataFrame) -> np.ndarray:
    """Compute regime features from daily OHLCV."""
    close = df["close"].values
    volume = df["volume"].values

    daily_ret = np.diff(np.log(close), prepend=np.log(close[0]))
    ret_5d = pd.Series(close).pct_change(5).fillna(0).values

    # Log-volume z-score (20-day rolling)
    log_vol = np.log1p(volume)
    vol_s = pd.Series(log_vol)
    vol_mean = vol_s.rolling(20, min_periods=5).mean().bfill().values
    vol_std  = vol_s.rolling(20, min_periods=5).std().bfill().fillna(1.0).replace(0, 1.0).values
    vol_zscore = (log_vol - vol_mean) / vol_std

    # ATR ratio
    high = df["high"].values
    low  = df["low"].values
    tr = np.maximum(high - low,
         np.maximum(np.abs(high - np.roll(close, 1)),
                    np.abs(low  - np.roll(close, 1))))
    tr[0] = high[0] - low[0]
    atr = pd.Series(tr).rolling(14, min_periods=5).mean().bfill().values
    atr_ratio = atr / np.where(close > 0, close, 1.0)

    X = np.column_stack([daily_ret, ret_5d, vol_zscore, atr_ratio])
    return X


def label_states(model, X: np.ndarray, df: pd.DataFrame) -> dict:
    """Assign BULL/SIDEWAYS/BEAR labels to HMM states by return signature."""
    states = model.predict(X)
    n_states = model.n_components
    close = df["close"].values

    state_returns = {}
    for s in range(n_states):
        mask = states == s
        if mask.sum() < 2:
            state_returns[s] = 0.0
            continue
        ret = np.diff(np.log(close[mask]))
        state_returns[s] = float(np.mean(ret)) * 252  # annualised

    sorted_states = sorted(state_returns.items(), key=lambda x: x[1])
    # lowest return → BEAR, highest → BULL, middle → SIDEWAYS
    labels = {}
    if n_states == 3:
        labels[str(sorted_states[0][0])] = "bear"
        labels[str(sorted_states[1][0])] = "sideways"
        labels[str(sorted_states[2][0])] = "bull"
    else:
        for i, (s, _) in enumerate(sorted_states):
            labels[str(s)] = f"state_{i}"

    print(f"  State return signatures (annualised):")
    for s, ret in sorted(state_returns.items()):
        lbl = labels[str(s)]
        frac = (states == s).mean()
        print(f"    State {s} ({lbl}): {ret:+.1%} ann. ret | {frac:.1%} of bars")

    return labels


def main():
    parser = argparse.ArgumentParser(description="Train regime HMM")
    parser.add_argument("--symbol", default="ETH",
                        help="Symbol base name for training data (default: ETH)")
    parser.add_argument("--data-dir", default=os.path.join(_ROOT, "data"),
                        help="Directory containing daily CSV files")
    parser.add_argument("--n-states", type=int, default=3,
                        help="Number of HMM states (default: 3)")
    parser.add_argument("--n-iter", type=int, default=200,
                        help="HMM training iterations (default: 200)")
    parser.add_argument("--models-dir", default=os.path.join(_ROOT, "models"),
                        help="Output directory for model files")
    parser.add_argument("--prob-threshold", type=float, default=0.7,
                        help="Minimum posterior probability to assign state (default: 0.7)")
    parser.add_argument("--hold-bars", type=int, default=2,
                        help="Minimum bars before state can change (default: 2)")
    parser.add_argument("--smooth-span", type=int, default=3,
                        help="EMA span for posterior smoothing (default: 3)")
    parser.add_argument("--plot", action="store_true",
                        help="Plot regime overlay (requires matplotlib)")
    args = parser.parse_args()

    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError:
        print("ERROR: hmmlearn not installed. Run: pip install hmmlearn")
        sys.exit(1)

    sym = args.symbol.upper()
    path_1d = os.path.join(args.data_dir, f"{sym}_1d.csv")
    if not os.path.exists(path_1d):
        print(f"ERROR: {path_1d} not found. Run fetch_data.py first.")
        sys.exit(1)

    print(f"Loading daily OHLCV for {sym}...")
    df = load_daily_ohlcv(path_1d)
    print(f"  {len(df)} bars from {df['timestamp'].iloc[0].date()} to {df['timestamp'].iloc[-1].date()}")

    X = compute_features(df)
    print(f"  Feature matrix: {X.shape}")

    print(f"\nTraining {args.n_states}-state GaussianHMM ({args.n_iter} iterations)...")
    model = GaussianHMM(
        n_components=args.n_states,
        covariance_type="full",
        n_iter=args.n_iter,
        random_state=42,
    )
    model.fit(X)
    print(f"  Converged: {model.monitor_.converged}  |  Log-likelihood: {model.score(X):.1f}")

    state_labels = label_states(model, X, df)

    os.makedirs(args.models_dir, exist_ok=True)
    pkl_path  = os.path.join(args.models_dir, "regime_hmm.pkl")
    json_path = os.path.join(args.models_dir, "regime_hmm_states.json")

    with open(pkl_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\nSaved model → {pkl_path}")

    states_cfg = {
        "state_labels":    state_labels,
        "prob_threshold":  args.prob_threshold,
        "hold_bars":       args.hold_bars,
        "smooth_span":     args.smooth_span,
        "training_symbol": sym,
        "n_bars":          len(df),
    }
    with open(json_path, "w") as f:
        json.dump(states_cfg, f, indent=2)
    print(f"Saved states config → {json_path}")
    print(f"\nState label mapping: {state_labels}")

    if args.plot:
        try:
            import matplotlib.pyplot as plt

            states = model.predict(X)
            probs  = model.predict_proba(X)

            # Map state ints to colours
            colour_map = {"bull": "green", "sideways": "yellow", "bear": "red"}
            colours = []
            for s in states:
                lbl = state_labels.get(str(s), "sideways")
                colours.append(colour_map.get(lbl, "grey"))

            fig, axes = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
            axes[0].semilogy(df["timestamp"], df["close"], lw=1)
            axes[0].set_title(f"{sym} daily close with HMM regime overlay")
            for i in range(len(df) - 1):
                axes[0].axvspan(df["timestamp"].iloc[i], df["timestamp"].iloc[i+1],
                                alpha=0.15, color=colours[i], linewidth=0)
            axes[1].stackplot(df["timestamp"], probs.T, alpha=0.7,
                              labels=[f"State {s} ({state_labels.get(str(s),'?')})"
                                      for s in range(args.n_states)])
            axes[1].set_ylabel("Posterior probability")
            axes[1].legend(loc="upper left", fontsize=8)
            plt.tight_layout()
            plt.show()
        except Exception as e:
            print(f"Plot failed: {e}")


if __name__ == "__main__":
    main()
