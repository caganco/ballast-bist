"""TÜFE CPI fetch yardimcilari.

Kullanim:
    from ballast.data.macro_sources import fetch_tufe_series
    tufe_daily = fetch_tufe_series("2024-01-01", "2026-04-30")  # pd.Series or None

TÜFE aylik endeksi EVDS'den cekilir, gunluk DatetimeIndex'e forward-fill ile doner.
Sepet testi TÜFE-deflate hesabi icin kullanilir.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# EVDS TÜFE seri sabitleri (thresholds.py'den inline edildi).
EVDS_TUFE_SERIES: str = "TP.FG.J0"     # canonical (fresher than TP.FE.OKTG01)
EVDS_TUFE_STALE_DAYS: int = 45         # aylik; TÜİK ~ayin 3'unde yayinlar


def fetch_tufe_series(start: str, end: str) -> "pd.Series | None":
    """TÜFE (TP.FG.J0) aylik CPI endeksini EVDS'den ceker, gunluk ffill ile doner.

    Args:
        start: "YYYY-MM-DD" format backtest baslangici
        end:   "YYYY-MM-DD" format backtest bitisi

    Returns:
        pd.Series with daily DatetimeIndex, forward-filled monthly CPI values.
        None on any failure (network, auth, empty data).
    """
    from ballast.data.evds_client import EvdsError, fetch_series

    try:
        start_evds = pd.to_datetime(start).strftime("%d-%m-%Y")
        end_evds   = pd.to_datetime(end).strftime("%d-%m-%Y")
        raw = fetch_series(EVDS_TUFE_SERIES, start_date=start_evds, end_date=end_evds)
        df = pd.DataFrame(raw)
        df["date"]  = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")  # EVDS bazen string doner
        monthly = df.set_index("date")["value"].dropna().sort_index()
        if monthly.empty:
            logger.warning("fetch_tufe_series: EVDS veri alindi ama tum degerler NaN")
            return None
        daily_idx = pd.date_range(
            start=pd.to_datetime(start),
            end=pd.to_datetime(end),
            freq="D",
        )
        return monthly.reindex(daily_idx, method="ffill")
    except (EvdsError, Exception) as exc:
        logger.warning("fetch_tufe_series: basarisiz - %s", exc)
        return None
