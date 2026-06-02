"""BIST round-trip transaction cost model v2.

Bölüm 1: Abdi-Ranaldo (2017) OHLCV-temelli bid-ask spread proxy.
Bölüm 2: Kyle square-root market impact.
Bölüm 3: K0 vergi utility (kazanç + temettü).

Kaynak:
  Abdi, F. & Ranaldo, A. (2017). "A Simple Estimation of Bid-Ask Spreads
    from Daily Close, High, and Low Prices." Review of Financial Studies,
    30(12), 4437-4480.
  Almgren, R., Thum, C., Hauptmann, E. & Li, H. (2005). "Direct Estimation
    of Equity Market Impact." Risk, 18(7), 58-62.
  Kyle, A.S. (1985). "Continuous Auctions and Insider Trading." Econometrica,
    53(6), 1315-1335.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# K0 Vergi Sabitleri (YOL2_SPEC §2b)
# Mevzuat değişince sadece bu iki satır güncellenir.
# ---------------------------------------------------------------------------
GAIN_TAX_RATE: float = 0.0        # Geçici-67: yerli hisse uzun-tutuş, bireysel yatırımcı
DIVIDEND_TAX_RATE: float = 0.15   # GVK Geç.67/4-b mevcut mevzuat


def abdi_ranaldo_spread(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    window: int = 21,
) -> pd.Series:
    """Hisse-bazlı rolling Abdi-Ranaldo (2017) spread tahmini.

    Formül:
        c_t   = ln(Close_t)
        m_t   = (ln(High_t) + ln(Low_t)) / 2
        gamma = rolling_mean[(c_t - m_t) * (c_{t-1} - m_t)]
        spread_pct = 2 * sqrt(max(-gamma, 0))

    Dönüş: yüzde cinsinden pd.Series (0.01 = %1).
    İlk window satır NaN (rolling warm-up).
    Negatif olmayan garantisi: max(-gamma, 0) - Abdi-Ranaldo §2.

    Kaynak: Review of Financial Studies 30(12), 4437-4480.
    """
    c = np.log(close)
    m = (np.log(high) + np.log(low)) / 2
    diff = c - m
    gamma = (diff * diff.shift(1)).rolling(window).mean()
    return 2 * np.sqrt(np.maximum(-gamma, 0))


def kyle_impact(
    close: pd.Series,
    order_value: float,
    adv: float,
    window: int = 21,
    lambda_kyle: float = 1.0,  # KALIBRASYON GEREKİYOR - şu an 1.0 placeholder
    sigma_method: str = "close_to_close",
    high: pd.Series | None = None,
    low: pd.Series | None = None,
    open_: pd.Series | None = None,
) -> float:
    """Tek yön Kyle square-root market impact yüzdesi.

    Formül:
        sigma_daily = std(ln(Close_t / Close_{t-1}))  [son window gün]
        impact_pct  = lambda_kyle * sigma_daily * sqrt(order_value / adv)

    ~300K TL portföyde order/ADV << 1 → impact ihmal düzeyinde.
    Bu fonksiyon küçük-para avantajını sayısal olarak gösterir.

    lambda_kyle BIST verisiyle kalibre edilmeli; şu an 1.0 placeholder.

    KALİBRASYON (GOAL, opt-in): sigma_method ile σ_daily tahmincisi seçilir.
    Estimand DEĞİŞMEZ (hep günlük getiri std'i); yalnız örnekleme-gürültüsü düşer.
        "close_to_close" (VARSAYILAN) - mevcut davranış, bire-bir korunur.
        "yang_zhang" - düşük-gürültü, estimand-koruyan (OHLC: open_/high/low gerekli).
        "parkinson"/"garman_klass"/"rogers_satchell" - gece-hariç (yanlı), araştırma.
    Varsayılan yol hiçbir yeni bağımlılık kullanmaz → eski çağrılar aynen çalışır.
    Ölçüm: scripts/calib_research.py (XU030: OHLC ~1.4-1.6x daha az gürültü).

    Kaynak: Almgren et al. (2005) Risk; Kyle (1985) Econometrica;
            OHLC tahmincileri için bkz. ballast.costs.volatility.
    """
    if sigma_method == "close_to_close":
        log_ret = np.log(close / close.shift(1)).dropna()
        sigma_daily = float(log_ret.iloc[-window:].std())
    else:
        from ballast.costs.volatility import estimate_sigma_daily

        sigma_daily = estimate_sigma_daily(
            close, high=high, low=low, open_=open_, window=window, method=sigma_method
        )
    return lambda_kyle * sigma_daily * np.sqrt(order_value / adv)


def dividend_net(gross_tl: float) -> float:
    """Temettü brütten nete. gross * (1 − DIVIDEND_TAX_RATE)."""
    return gross_tl * (1 - DIVIDEND_TAX_RATE)


def gain_tax(realized_gain_tl: float) -> float:
    """Kazanç stopajı - Geçici-67 kapsamında şu an daima 0.0.

    Mevzuat değişince GAIN_TAX_RATE güncellenecek; çağıran kod değişmez.
    """
    return realized_gain_tl * GAIN_TAX_RATE


def _spread_point_estimate(
    spread_series: pd.Series, spread_agg: str = "last", agg_window: int = 5
) -> float:
    """Geçerli spread serisinden temsilî nokta-tahmin.

    AYNI estimand (cari spread seviyesi); yalnız örnekleme-gürültüsü değişir.
    spread_agg:
        "last"   (VARSAYILAN) - son geçerli değer (iloc[-1]), mevcut davranış.
        "mean"   - son `agg_window` geçerli değerin ortalaması (düşük-gürültü).
        "median" - son `agg_window` geçerli değerin medyanı (aykırı-dayanıklı).
    Ölçüm (XU030, scripts/calib_research.py): median@5 → ~2.1x daha az gürültü,
    seviye korunur (oran ~0.999). Trunc (gamma>=0→0) doğal olarak agregeye dahil.
    """
    if spread_agg == "last":
        return float(spread_series.iloc[-1])
    tail = spread_series.iloc[-agg_window:]
    if spread_agg == "mean":
        return float(tail.mean())
    if spread_agg == "median":
        return float(tail.median())
    raise ValueError(
        f"Bilinmeyen spread_agg '{spread_agg}'. Geçerli: last, mean, median."
    )


def round_trip_cost_v2(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    order_value: float,
    adv: float,
    window: int = 21,
    lambda_kyle: float = 1.0,
    sigma_method: str = "close_to_close",
    open_: pd.Series | None = None,
    spread_agg: str = "last",
    agg_window: int = 5,
) -> dict:
    """Round-trip maliyet tahmini.

    Dönüş:
        spread_cost_pct     - Abdi-Ranaldo tek yön (yüzde)
        impact_cost_pct     - Kyle tek yön (yüzde)
        commission_pct      - yerli hisse (BIST) = 0.0 (sabit)
        round_trip_cost_pct - 2*(spread+impact) + commission

    Gerekçe round-trip = 2×: giriş ve çıkışta spread + impact ödenir.

    KALİBRASYON (GOAL, opt-in - varsayılanlar mevcut davranışı bire-bir korur):
        sigma_method - Kyle σ_daily tahmincisi ("yang_zhang" için open_ ver);
                       bkz. kyle_impact / ballast.costs.volatility.
        spread_agg   - spread nokta-tahmini agregasyonu ("median"/"mean" düşük-gürültü).
    Estimand HİÇBİRİNDE değişmez; yalnız örnekleme-gürültüsü düşer.

    Raises:
        ValueError: Seri uzunluğu < window+1 - spread hesaplanamaz.
            En az window+1 günlük OHLCV veri gereklidir.
    """
    spread_series = abdi_ranaldo_spread(close, high, low, window).dropna()
    if spread_series.empty:
        raise ValueError(
            f"Yetersiz veri: {len(close)} satır < window+1 ({window + 1}). "
            "abdi_ranaldo_spread() için en az window+1 günlük OHLCV gerekli."
        )
    spread = _spread_point_estimate(spread_series, spread_agg, agg_window)
    impact = kyle_impact(
        close, order_value, adv, window, lambda_kyle,
        sigma_method=sigma_method, high=high, low=low, open_=open_,
    )
    return {
        "spread_cost_pct": spread,
        "impact_cost_pct": impact,
        "commission_pct": 0.0,
        "round_trip_cost_pct": 2 * (spread + impact),
    }
