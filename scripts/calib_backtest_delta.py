"""Kalibrasyon opt-in AÇILIRSA rebalance-bant maliyet tahmininde ne değişir?

Salt-okunur. Gerçek XU030 OHLC üzerinde, her günü hipotetik bir rebalance anı
sayıp, mevcut (default) maliyet tahmini ile opt-in (yang_zhang σ + median@5 spread)
tahminini kıyaslar. Amaç: (a) toplam/seviye ~değişmez mi (estimand korunumu),
(b) tek-karar dağılımı ne kadar daralır (gürültü azalması).
"""
from __future__ import annotations

import sys

import pandas as pd
import yfinance as yf

from ballast.costs.transaction_cost_v2 import round_trip_cost_v2

sys.stdout.reconfigure(encoding="utf-8")

ORDER, ADV = 30_000.0, 50_000_000.0  # 300K port, ZPX30 BYF tipik ADV; oran<<1


def fetch() -> pd.DataFrame | None:
    df = yf.Ticker("XU030.IS").history(start="2019-01-01", end="2026-05-31", auto_adjust=True)
    if df is None or df.empty:
        return None
    df = df[["Open", "High", "Low", "Close"]].dropna()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def cost_at(df: pd.DataFrame, end_i: int, opt_in: bool) -> float:
    """end_i gününe kadarki veriyle round-trip maliyet yüzdesi."""
    sl = df.iloc[: end_i + 1]
    kw = {}
    if opt_in:
        kw = dict(sigma_method="yang_zhang", open_=sl["Open"],
                  spread_agg="median", agg_window=5)
    r = round_trip_cost_v2(sl["Close"], sl["High"], sl["Low"], ORDER, ADV, **kw)
    return r["round_trip_cost_pct"]


def main() -> int:
    df = fetch()
    if df is None or len(df) < 60:
        print("VERI YOK")
        return 1

    idx = range(40, len(df))  # window+warmup sonrası her gün
    default = pd.Series([cost_at(df, i, False) for i in idx])
    optin = pd.Series([cost_at(df, i, True) for i in idx])

    d_jump = default.diff().abs().dropna()
    o_jump = optin.diff().abs().dropna()
    print(f"XU030 {len(df)} gün; {len(default)} hipotetik rebalance-anı maliyeti")
    print("=" * 66)
    print(f"{'':<22}{'DEFAULT':>14}{'OPT-IN':>14}")
    print(f"{'ort maliyet %':<22}{default.mean()*100:>14.4f}{optin.mean()*100:>14.4f}")
    print(f"{'medyan maliyet %':<22}{default.median()*100:>14.4f}{optin.median()*100:>14.4f}")
    print(f"{'std (dağılım) %':<22}{default.std()*100:>14.4f}{optin.std()*100:>14.4f}")
    print(f"{'gün-içi |Δ| ort %':<22}{d_jump.mean()*100:>14.4f}{o_jump.mean()*100:>14.4f}")
    print("=" * 66)
    print(f"  seviye oranı (opt/def)     : {optin.mean()/default.mean():.4f}  (~1 = estimand korundu)")
    print(f"  tek-karar gürültü azalması : {d_jump.mean()/o_jump.mean():.2f}x")
    print(f"  default en yüksek maliyet % : {default.max()*100:.4f}  (aykırı/tek-gün spike)")
    print(f"  opt-in  en yüksek maliyet % : {optin.max()*100:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
