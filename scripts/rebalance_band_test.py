"""Rebalance Bant Testi (Stage-0, pre-registered, frozen params).

Reports RAW numbers only - no judgment, no "this band is better".

Stage-0 frozen parameters:
  Period:    2019-01-04 .. 2026-05-26 (önceki backtest ortak takvimi)
  Portfolio: ZPX30_proxy (XU030 - TER) + TL deposit (TP.TRY.MT02)
  Target:    %80 borsa / %20 mevduat  (test varsayımı; oran kararı ayrı)
  Bands:     ±3%, ±5%, ±7.5%, ±10%, ±15%
  Primary:   TL-real cumulative return (TÜFE TP.FG.J0 deflate)
  Secondary: rebalance count, total cost (bps)
  Spread:    Abdi-Ranaldo (XU030 OHLCV, window=21) - ZPX30 proxy, upper bound
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

from ballast.costs.transaction_cost_v2 import abdi_ranaldo_spread
from scripts.basket_backtest import END, START, TER_DAILY, build_panel

TARGET = 0.80                       # hedef borsa oranı
BANDS = [0.03, 0.05, 0.075, 0.10, 0.15]
SPREAD_WINDOW = 21


def _xu030_ohlc(idx: pd.DatetimeIndex) -> pd.DataFrame:
    """XU030.IS High/Low/Close, reindexed to the basket-test panel calendar."""
    df = yf.download("XU030.IS", start=START, end=END, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = df.index.tz_localize(None)
    return df[["High", "Low", "Close"]].reindex(idx).ffill()


def simulate(
    band: float,
    ret: np.ndarray,
    dep_factor: np.ndarray,
    spread: np.ndarray,
    dates: pd.DatetimeIndex,
) -> dict:
    """Daily 80/20 band-rebalance simulation for one band threshold."""
    borsa, nakit = TARGET, 1.0 - TARGET
    n_rebal = 0
    toplam_bps = 0.0
    kayitlar: list[tuple[str, str, float]] = []

    for t in range(len(ret)):
        # 1) getiriler
        borsa *= (1.0 + ret[t])
        borsa *= (1.0 - TER_DAILY)
        nakit *= dep_factor[t]
        port = borsa + nakit

        # 2) mevcut borsa oranı
        oran = borsa / port
        sapma = oran - TARGET

        # 3) bant kontrolü
        if abs(sapma) > band:
            # 4) rebalance
            yeni_borsa = TARGET * port
            islem = abs(yeni_borsa - borsa)
            s = float(spread[t])
            maliyet_tl = islem * s            # tam spread × işlem (üst sınır)
            borsa = yeni_borsa
            nakit = (1.0 - TARGET) * port - maliyet_tl
            n_rebal += 1
            toplam_bps += s * 10000.0
            kayitlar.append(
                (dates[t].date().isoformat(), "+" if sapma > 0 else "-", islem)
            )

    port_final = borsa + nakit
    return {
        "band": band,
        "port_final": port_final,
        "n_rebal": n_rebal,
        "toplam_bps": toplam_bps,
        "kayitlar": kayitlar,
    }


def run() -> dict:
    panel = build_panel()
    ohlc = _xu030_ohlc(panel.index)

    spread = abdi_ranaldo_spread(
        ohlc["Close"], ohlc["High"], ohlc["Low"], window=SPREAD_WINDOW
    ).bfill().to_numpy()                       # warm-up NaN → bfill (rapor notu)

    ret = panel["xu030"].pct_change().fillna(0.0).to_numpy()
    dep_factor = np.exp(panel["dep_logret"].to_numpy())
    tufe_mult = float(panel["tufe"].iloc[-1] / panel["tufe"].iloc[0])

    results = []
    for band in BANDS:
        r = simulate(band, ret, dep_factor, spread, panel.index)
        r["tl_real_mult"] = r["port_final"] / tufe_mult
        results.append(r)

    return {
        "results": results,
        "n_days": len(panel),
        "start": panel.index[0].date().isoformat(),
        "end": panel.index[-1].date().isoformat(),
        "tufe_mult": tufe_mult,
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    res = run()
    print(f"Calendar: {res['start']} .. {res['end']}  ({res['n_days']} gün)  "
          f"TÜFE çarpanı: {res['tufe_mult']:.3f}x")
    print(f"{'Bant':>7}{'Rebalance':>11}{'TL-reel*':>11}{'Toplam maliyet (bps)':>22}")
    for r in res["results"]:
        print(f"{r['band']*100:>6.1f}%{r['n_rebal']:>11d}{r['tl_real_mult']:>10.3f}x"
              f"{r['toplam_bps']:>22.1f}")
    print("* = birincil metrik (TÜFE-deflate)")
