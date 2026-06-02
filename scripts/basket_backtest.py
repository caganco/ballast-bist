"""Sepet Testi Backtest (Stage-0, pre-registered, frozen params).

Reports RAW numbers only - no judgment, no "this option is better".

Stage-0 frozen parameters:
  Period:  2019-01-01 .. 2026-05-31
  Primary metric: cumulative TL-real return (TÜFE-deflate)
  Options:
    SEÇ-A  XU050  → veri yok (yfinance + mynet historical unavailable)
    SEÇ-B  XU030.IS raw
    SEÇ-C  XU030.IS − TER drag (0.00022/252 daily)   [ZPX30 proxy]
  Nulls:
    NULL-1 XU100.IS
    NULL-2 TL deposit (TP.TRY.MT02), compounded
  Deflators: TÜFE TP.FG.J0 (TL-real), USDTRY TRY=X (USD-real)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from ballast.data.evds_client import fetch_series
from ballast.data.macro_sources import fetch_tufe_series

load_dotenv()

START = "2019-01-01"
END = "2026-05-31"
TER_DAILY = 0.00022 / 252  # ZPX30 TER drag, per trading day (SEÇ-C)
DEPOSIT_SERIES = "TP.TRY.MT02"  # 1-aylık TL mevduat faizi, yıllık %


def _yf_close(symbol: str, use_volume: bool = True) -> pd.Series:
    """Daily auto-adjusted Close; Volume==0 → NaN Close; ffill ≤5d then drop.

    use_volume=False for FX pairs (TRY=X), which structurally report 0 volume -
    the Volume==0→NaN rule applies only to equity/index baskets.
    """
    df = yf.download(symbol, start=START, end=END, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close = df["Close"].copy()
    if use_volume and "Volume" in df.columns:
        close = close.where(df["Volume"].fillna(0) > 0)
    close = close.ffill(limit=5).dropna()
    close.index = close.index.tz_localize(None)
    return close


def _deposit_daily_logret(idx: pd.DatetimeIndex) -> pd.Series:
    """TP.TRY.MT02 annual % → daily compound log-return on calendar idx.

    daily_logret = ln(1 + annual/100) / 252  (compounds to annual rate over 252d).
    Weekly EVDS obs forward-filled onto trading calendar.
    """
    raw = fetch_series(DEPOSIT_SERIES, start_date="01-01-2019", end_date="31-05-2026")
    s = pd.Series(
        {pd.to_datetime(d["date"]): float(d["value"]) for d in raw}
    ).sort_index()
    annual = s.reindex(idx, method="ffill")
    return np.log1p(annual / 100.0) / 252.0


def build_panel() -> pd.DataFrame:
    """Fetch + clean + inner-join all series onto a common trading calendar."""
    xu030 = _yf_close("XU030.IS").rename("xu030")
    xu100 = _yf_close("XU100.IS").rename("xu100")
    usdtry = _yf_close("TRY=X", use_volume=False).rename("usdtry")

    # Common calendar = intersection of the three price series
    panel = pd.concat([xu030, xu100, usdtry], axis=1, join="inner").dropna()

    tufe = fetch_tufe_series(START, END)
    if tufe is None:
        raise RuntimeError("TÜFE fetch returned None - cannot deflate")
    tufe.index = pd.to_datetime(tufe.index).tz_localize(None)
    panel["tufe"] = tufe.reindex(panel.index, method="ffill")

    panel["dep_logret"] = _deposit_daily_logret(panel.index)
    panel = panel.dropna()
    return panel


def compute(panel: pd.DataFrame) -> dict:
    """Daily log-returns → cumulative; TL-nominal, TL-real, USD-real growth multiples."""
    r_xu030 = np.log(panel["xu030"]).diff()
    r_xu100 = np.log(panel["xu100"]).diff()
    r_usd = np.log(panel["usdtry"]).diff()      # USDTRY depreciation
    r_tufe = np.log(panel["tufe"]).diff()        # CPI inflation

    options = {
        "SEC-B  (XU030 raw)": r_xu030,
        "SEC-C  (XU030 - TER)": r_xu030 - TER_DAILY,
        "NULL-1 (XU100)": r_xu100,
        "NULL-2 (TL mevduat)": panel["dep_logret"],
    }

    out = {}
    n = len(panel)
    years = (panel.index[-1] - panel.index[0]).days / 365.25
    for name, r in options.items():
        r = r.fillna(0.0)
        cum_nom = r.cumsum()
        cum_real = (r - r_tufe.fillna(0.0)).cumsum()      # TÜFE-deflate (PRIMARY)
        cum_usd = (r - r_usd.fillna(0.0)).cumsum()        # USD-real
        mult_nom = float(np.exp(cum_nom.iloc[-1]))
        mult_real = float(np.exp(cum_real.iloc[-1]))
        mult_usd = float(np.exp(cum_usd.iloc[-1]))
        cagr_real = mult_real ** (1 / years) - 1
        out[name] = {
            "tl_nominal_mult": mult_nom,
            "tl_real_mult": mult_real,       # PRIMARY METRIC
            "usd_real_mult": mult_usd,
            "tl_real_cagr": cagr_real,
        }
    return {
        "results": out,
        "n_days": n,
        "years": years,
        "start": panel.index[0].date().isoformat(),
        "end": panel.index[-1].date().isoformat(),
        "tufe_mult": float(panel["tufe"].iloc[-1] / panel["tufe"].iloc[0]),
        "usdtry_mult": float(panel["usdtry"].iloc[-1] / panel["usdtry"].iloc[0]),
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    panel = build_panel()
    res = compute(panel)
    print(f"Calendar: {res['start']} .. {res['end']}  ({res['n_days']} gün, {res['years']:.2f} yıl)")
    print(f"TÜFE çarpanı: {res['tufe_mult']:.3f}x   USDTRY çarpanı: {res['usdtry_mult']:.3f}x")
    print(f"{'Seçenek':<24}{'TL-nominal':>13}{'TL-reel*':>12}{'USD-reel':>12}{'TL-reel CAGR':>14}")
    for name, m in res["results"].items():
        print(f"{name:<24}{m['tl_nominal_mult']:>12.3f}x{m['tl_real_mult']:>11.3f}x"
              f"{m['usd_real_mult']:>11.3f}x{m['tl_real_cagr']*100:>13.2f}%")
    print("* = birincil metrik (TÜFE-deflate)")
