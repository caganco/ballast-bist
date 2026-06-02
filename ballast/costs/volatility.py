"""Düşük-varyanslı OHLC volatilite tahmincileri (GOAL kalibrasyonu).

Amaç: `kyle_impact`'in σ_daily girdisini DAHA AZ GÜRÜLTÜ ile tahmin etmek.
Estimand DEĞİŞMEZ - hepsi *günlük getiri standart sapması* (σ_daily) tahmin
eder; yalnız örnekleme-varyansı (gün-günden zıplama) düşer. XU030 üzerinde
ölçüldü (scripts/calib_research.py): OHLC tahmincileri close-to-close'a göre
~1.4-1.6x daha az gürültü.

Tahminci seçimi (önemli ayrım - metodoloji korunumu):
  - **Yang-Zhang**: gece (overnight) + gün-içi + Rogers-Satchell bileşeni içerir;
    drift-bağımsız, gece-sıçramasına dayanıklı. Seviyesi close-to-close ile
    en uyumlu (XU030: oran 0.932) çünkü TÜM günlük varyansı (gece dahil) yakalar.
    Bu yüzden estimand'i KORUR → varsayılan opt-in tercih.
  - Parkinson / Garman-Klass / Rogers-Satchell: gece varyansını dışlar →
    seviyeyi düşük tahmin eder (estimand kayar). Daha düşük gürültü verseler de
    σ_daily'yi yanlı tahmin ettikleri için kyle_impact varsayılanı OLMAZLAR;
    araştırma/karşılaştırma için sağlanır.

Tüm fonksiyonlar pencere-bazlı SON tahmini (tek float) döner - kyle_impact'in
close-to-close std davranışıyla bire-bir aynı arayüz.

Kaynak:
  Parkinson, M. (1980). "The Extreme Value Method for Estimating the Variance
    of the Rate of Return." Journal of Business 53(1), 61-65.
  Garman, M. & Klass, M. (1980). "On the Estimation of Security Price
    Volatilities from Historical Data." Journal of Business 53(1), 67-78.
  Rogers, L.C.G. & Satchell, S.E. (1991). "Estimating Variance from High, Low
    and Closing Prices." Annals of Applied Probability 1(4), 504-512.
  Yang, D. & Zhang, Q. (2000). "Drift-Independent Volatility Estimation Based
    on High, Low, Open, and Close Prices." Journal of Business 73(3), 477-491.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VALID_ESTIMATORS = (
    "close_to_close",
    "parkinson",
    "garman_klass",
    "rogers_satchell",
    "yang_zhang",
)


def _require_len(close: pd.Series, window: int) -> None:
    if len(close.dropna()) < window + 1:
        raise ValueError(
            f"Yetersiz veri: {len(close.dropna())} geçerli kapanış < window+1 "
            f"({window + 1}). σ_daily tahmini için en az window+1 gün gerekli."
        )


def close_to_close_sigma(close: pd.Series, window: int = 21) -> float:
    """Mevcut kyle_impact davranışı: ln(C_t/C_{t-1}) son `window` gün std.

    Referans (varsayılan) tahminci - diğerleri buna göre gürültü-azaltır.
    """
    _require_len(close, window)
    log_ret = np.log(close / close.shift(1)).dropna()
    return float(log_ret.iloc[-window:].std())


def parkinson_sigma(high: pd.Series, low: pd.Series, window: int = 21) -> float:
    """Parkinson (1980): yalnız High-Low aralığı. σ² = mean[(ln H/L)²]/(4 ln2).

    Gece varyansını DIŞLAR → σ_daily'yi düşük tahmin eder (yanlı). Düşük
    gürültü ama estimand kayar - kyle varsayılanı değil.
    """
    _require_len(high, window)
    hl = np.log(high / low) ** 2
    var = hl.iloc[-window:].mean() / (4.0 * np.log(2.0))
    return float(np.sqrt(max(var, 0.0)))


def garman_klass_sigma(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, window: int = 21
) -> float:
    """Garman-Klass (1980): HL aralığı + open-close. Yüksek verim, gece hariç."""
    _require_len(close, window)
    hl = 0.5 * np.log(high / low) ** 2
    co = (2.0 * np.log(2.0) - 1.0) * np.log(close / open_) ** 2
    var = (hl - co).iloc[-window:].mean()
    return float(np.sqrt(max(var, 0.0)))


def rogers_satchell_sigma(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, window: int = 21
) -> float:
    """Rogers-Satchell (1991): drift-bağımsız (trendli seride yansız), gece hariç."""
    _require_len(close, window)
    ho = np.log(high / open_)
    lo = np.log(low / open_)
    co = np.log(close / open_)
    rs = ho * (ho - co) + lo * (lo - co)
    var = rs.iloc[-window:].mean()
    return float(np.sqrt(max(var, 0.0)))


def yang_zhang_sigma(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, window: int = 21
) -> float:
    """Yang-Zhang (2000): overnight + open-close + Rogers-Satchell.

    Minimum-varyans OHLC tahmincisi; drift-bağımsız, gece-sıçramasına dayanıklı.
    TÜM günlük varyansı (gece dahil) yakaladığı için close-to-close ile aynı
    estimand'i tahmin eder - sadece daha az gürültüyle. kyle_impact için
    önerilen opt-in.
    """
    _require_len(close, window)
    o = np.log(open_ / close.shift(1))   # overnight getiri
    c = np.log(close / open_)            # open-to-close getiri
    ho = np.log(high / open_)
    lo = np.log(low / open_)
    co = np.log(close / open_)
    rs = ho * (ho - co) + lo * (lo - co)

    o_w = o.iloc[-window:].dropna()
    c_w = c.iloc[-window:].dropna()
    rs_w = rs.iloc[-window:].dropna()
    n = len(o_w)
    if n < 2:
        raise ValueError("Yang-Zhang için en az 2 gece-getirisi gerekli.")

    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    vo = float(o_w.var(ddof=1))          # overnight varyans
    vc = float(c_w.var(ddof=1))          # open-close varyans
    vrs = float(rs_w.mean())             # Rogers-Satchell ortalaması
    var = vo + k * vc + (1.0 - k) * vrs
    return float(np.sqrt(max(var, 0.0)))


def estimate_sigma_daily(
    close: pd.Series,
    high: pd.Series | None = None,
    low: pd.Series | None = None,
    open_: pd.Series | None = None,
    window: int = 21,
    method: str = "close_to_close",
) -> float:
    """σ_daily tahmincisi seçici (kyle_impact opt-in girişi).

    method:
      "close_to_close" (VARSAYILAN) - mevcut davranış, geriye-uyum garantisi.
      "yang_zhang"     - önerilen düşük-gürültü, estimand-koruyan (OHLC gerekli).
      "parkinson" / "garman_klass" / "rogers_satchell" - gece-hariç, yanlı; araştırma.

    OHLC gerektiren methodlarda high/low (ve GK/RS/YZ için open_) verilmezse
    ValueError. close_to_close yalnız close ister → mevcut çağrılar değişmeden çalışır.
    """
    if method == "close_to_close":
        return close_to_close_sigma(close, window)
    if method == "parkinson":
        if high is None or low is None:
            raise ValueError("parkinson için high ve low gerekli.")
        return parkinson_sigma(high, low, window)
    if method in ("garman_klass", "rogers_satchell", "yang_zhang"):
        if high is None or low is None or open_ is None:
            raise ValueError(f"{method} için open_, high, low gerekli.")
        if method == "garman_klass":
            return garman_klass_sigma(open_, high, low, close, window)
        if method == "rogers_satchell":
            return rogers_satchell_sigma(open_, high, low, close, window)
        return yang_zhang_sigma(open_, high, low, close, window)
    raise ValueError(
        f"Bilinmeyen method '{method}'. Geçerli: {', '.join(VALID_ESTIMATORS)}."
    )
