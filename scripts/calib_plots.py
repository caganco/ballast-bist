"""Render calibration evidence figures into results/ (read-only, no trades).

Produces:
  results/calib_vol_noise.png   - rolling sigma: close-to-close vs Yang-Zhang
                                   (same estimand, lower sampling noise) + per-estimator
                                   relative-noise bars.
  results/calib_cost_noise.png  - round-trip cost estimate: default vs opt-in,
                                   day-to-day jump distribution (variance reduction).

Real XU030.IS OHLC (2019-2026). Falls back to a clear message if data is empty.
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402

from ballast.costs.transaction_cost_v2 import round_trip_cost_v2  # noqa: E402
from ballast.costs.volatility import (  # noqa: E402
    garman_klass_sigma,
    parkinson_sigma,
    rogers_satchell_sigma,
    yang_zhang_sigma,
)
from ballast.utils.config import ROOT_DIR  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

WINDOW = 21
OUT = ROOT_DIR / "results"


def fetch() -> pd.DataFrame | None:
    df = yf.Ticker("XU030.IS").history(start="2019-01-01", end="2026-05-31", auto_adjust=True)
    if df is None or df.empty:
        return None
    df = df[["Open", "High", "Low", "Close"]].dropna()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def _roll(fn, df, window):
    """Rolling last-window estimate as a series (for plotting), via expanding tail."""
    out = pd.Series(index=df.index, dtype=float)
    for i in range(window + 1, len(df)):
        sl = df.iloc[: i + 1]
        out.iloc[i] = fn(sl)
    return out.dropna()


def vol_figure(df: pd.DataFrame) -> None:
    c2c = _roll(
        lambda s: float(np.log(s["Close"] / s["Close"].shift(1)).dropna().iloc[-WINDOW:].std()),
        df, WINDOW,
    )
    yz = _roll(lambda s: yang_zhang_sigma(s["Open"], s["High"], s["Low"], s["Close"], WINDOW), df, WINDOW)

    rel = {}
    for name, fn in {
        "close-to-close": lambda s: float(np.log(s["Close"] / s["Close"].shift(1)).dropna().iloc[-WINDOW:].std()),
        "Parkinson": lambda s: parkinson_sigma(s["High"], s["Low"], WINDOW),
        "Garman-Klass": lambda s: garman_klass_sigma(s["Open"], s["High"], s["Low"], s["Close"], WINDOW),
        "Rogers-Satchell": lambda s: rogers_satchell_sigma(s["Open"], s["High"], s["Low"], s["Close"], WINDOW),
        "Yang-Zhang": lambda s: yang_zhang_sigma(s["Open"], s["High"], s["Low"], s["Close"], WINDOW),
    }.items():
        ser = _roll(fn, df, WINDOW)
        d = ser.diff().abs().dropna()
        rel[name] = d.mean() / ser.mean()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))
    ax1.plot(c2c.index, c2c.values, lw=0.8, alpha=0.65, label="close-to-close (current)", color="#c0392b")
    ax1.plot(yz.index, yz.values, lw=1.1, label="Yang-Zhang (opt-in)", color="#2c3e50")
    ax1.set_title(f"Rolling daily σ ({WINDOW}d) - same estimand, less noise")
    ax1.set_ylabel("σ_daily")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25)

    names = list(rel.keys())
    vals = [rel[n] for n in names]
    base = rel["close-to-close"]
    colors = ["#c0392b" if n == "close-to-close" else ("#2c3e50" if n == "Yang-Zhang" else "#7f8c8d") for n in names]
    bars = ax2.bar(range(len(names)), vals, color=colors)
    ax2.set_xticks(range(len(names)))
    ax2.set_xticklabels(names, rotation=25, ha="right", fontsize=8)
    ax2.set_ylabel("relative noise  (|Δσ| / σ)")
    ax2.set_title("Estimator sampling noise (lower = better)")
    for b, n in zip(bars, names):
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height(),
                 f"{base / rel[n]:.2f}x", ha="center", va="bottom", fontsize=8)
    ax2.grid(alpha=0.25, axis="y")

    fig.tight_layout()
    p = OUT / "calib_vol_noise.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    print(f"wrote {p}")


def cost_figure(df: pd.DataFrame) -> None:
    order, adv = 30_000.0, 50_000_000.0
    default, optin = [], []
    idx = range(40, len(df))
    for i in idx:
        sl = df.iloc[: i + 1]
        default.append(round_trip_cost_v2(sl["Close"], sl["High"], sl["Low"], order, adv)["round_trip_cost_pct"])
        optin.append(round_trip_cost_v2(
            sl["Close"], sl["High"], sl["Low"], order, adv,
            sigma_method="yang_zhang", open_=sl["Open"], spread_agg="median", agg_window=5,
        )["round_trip_cost_pct"])
    dts = df.index[list(idx)]
    d = pd.Series(default, index=dts)
    o = pd.Series(optin, index=dts)
    dj = d.diff().abs().dropna() * 100
    oj = o.diff().abs().dropna() * 100

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))
    ax1.plot(d.index, d.values * 100, lw=0.7, alpha=0.6, label="default (last spread, C2C σ)", color="#c0392b")
    ax1.plot(o.index, o.values * 100, lw=1.0, label="opt-in (median@5, YZ σ)", color="#2c3e50")
    ax1.set_title("Round-trip cost estimate over time")
    ax1.set_ylabel("cost %")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25)

    bins = np.linspace(0, max(dj.quantile(0.99), oj.quantile(0.99)), 40)
    ax2.hist(dj, bins=bins, alpha=0.55, label=f"default  (mean |Δ| {dj.mean():.3f}%)", color="#c0392b")
    ax2.hist(oj, bins=bins, alpha=0.7, label=f"opt-in  (mean |Δ| {oj.mean():.3f}%)", color="#2c3e50")
    ax2.set_title(f"Day-to-day cost jump - {dj.mean() / oj.mean():.2f}x less noise")
    ax2.set_xlabel("|Δ cost| (pp)")
    ax2.set_ylabel("days")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25, axis="y")

    fig.tight_layout()
    p = OUT / "calib_cost_noise.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    print(f"wrote {p}")


def main() -> int:
    df = fetch()
    if df is None or len(df) < 60:
        print("DATA UNAVAILABLE: XU030 OHLC empty - figures not generated.")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"XU030 OHLC: {len(df)} days")
    vol_figure(df)
    cost_figure(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
