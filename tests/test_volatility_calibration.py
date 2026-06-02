"""GOAL kalibrasyon testleri - düşük-gürültü OHLC tahmincileri + opt-in entegrasyon.

Disiplin: tüm opt-in eklemeler VARSAYILANDA mevcut davranışı bire-bir korur.
Bu testler hem (a) yeni tahmincilerin matematiğini, hem (b) varsayılan-koruma
garantisini (regression) doğrular. Saf-mantık, sentetik veri, canlı çağrı yok.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ballast.costs.transaction_cost_v2 import (
    _spread_point_estimate,
    abdi_ranaldo_spread,
    kyle_impact,
    round_trip_cost_v2,
)
from ballast.costs.volatility import (
    VALID_ESTIMATORS,
    close_to_close_sigma,
    estimate_sigma_daily,
    garman_klass_sigma,
    parkinson_sigma,
    rogers_satchell_sigma,
    yang_zhang_sigma,
)


def _ohlc(n: int = 60, seed: int = 7):
    """Geçerli sentetik OHLC: High>=max(O,C), Low<=min(O,C)."""
    rng = np.random.default_rng(seed)
    close = pd.Series(100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n))))
    prev = close.shift(1)
    prev.iloc[0] = close.iloc[0]
    open_ = prev * (1.0 + rng.normal(0.0, 0.002, n))
    hi_base = np.maximum(open_, close)
    lo_base = np.minimum(open_, close)
    high = hi_base * (1.0 + np.abs(rng.normal(0.0, 0.004, n)))
    low = lo_base * (1.0 - np.abs(rng.normal(0.0, 0.004, n)))
    return open_, high, low, close


# ---------------------------------------------------------------------------
# Tahminci matematiği
# ---------------------------------------------------------------------------
class TestEstimatorMath:

    def test_close_to_close_matches_inline_std(self):
        """close_to_close_sigma == ln-getiri son-window std (kyle ile aynı)."""
        _, _, _, close = _ohlc()
        log_ret = np.log(close / close.shift(1)).dropna()
        expected = float(log_ret.iloc[-21:].std())
        assert close_to_close_sigma(close, 21) == pytest.approx(expected, rel=1e-12)

    def test_parkinson_closed_form_constant_ratio(self):
        """Sabit H/L oranı r → sigma = sqrt((ln r)^2 / (4 ln2)), kapalı form."""
        n = 30
        high = pd.Series([101.0] * n)   # H/L = 101/99
        low = pd.Series([99.0] * n)
        r = np.log(101.0 / 99.0)
        expected = np.sqrt(r ** 2 / (4.0 * np.log(2.0)))
        assert parkinson_sigma(high, low, 21) == pytest.approx(expected, rel=1e-12)

    def test_yang_zhang_hand_computed_small_window(self):
        """YZ formülünü küçük pencerede elle hesapla → birebir."""
        open_, high, low, close = _ohlc(n=40, seed=3)
        w = 10
        o = np.log(open_ / close.shift(1))
        c = np.log(close / open_)
        ho = np.log(high / open_)
        lo = np.log(low / open_)
        co = np.log(close / open_)
        rs = ho * (ho - co) + lo * (lo - co)
        ow, cw, rw = o.iloc[-w:].dropna(), c.iloc[-w:].dropna(), rs.iloc[-w:].dropna()
        nn = len(ow)
        k = 0.34 / (1.34 + (nn + 1) / (nn - 1))
        var = ow.var(ddof=1) + k * cw.var(ddof=1) + (1 - k) * rw.mean()
        expected = float(np.sqrt(max(var, 0.0)))
        assert yang_zhang_sigma(open_, high, low, close, w) == pytest.approx(expected, rel=1e-12)

    def test_all_ohlc_estimators_positive_finite(self):
        """Tüm OHLC tahmincileri gerçekçi seride pozitif + sonlu."""
        open_, high, low, close = _ohlc()
        for sig in (
            parkinson_sigma(high, low, 21),
            garman_klass_sigma(open_, high, low, close, 21),
            rogers_satchell_sigma(open_, high, low, close, 21),
            yang_zhang_sigma(open_, high, low, close, 21),
        ):
            assert np.isfinite(sig) and sig > 0.0

    def test_estimators_same_order_of_magnitude(self):
        """Aynı estimand → tahminciler aynı büyüklük mertebesinde (yanlılık sınırlı)."""
        open_, high, low, close = _ohlc(n=120, seed=11)
        c2c = close_to_close_sigma(close, 21)
        yz = yang_zhang_sigma(open_, high, low, close, 21)
        assert 0.4 < yz / c2c < 2.5

    def test_insufficient_data_raises(self):
        close = pd.Series([100.0, 101.0, 100.5])
        with pytest.raises(ValueError, match="Yetersiz veri"):
            close_to_close_sigma(close, 21)


# ---------------------------------------------------------------------------
# estimate_sigma_daily seçici
# ---------------------------------------------------------------------------
class TestEstimateSigmaDaily:

    def test_default_is_close_to_close(self):
        """method varsayılanı close_to_close → mevcut davranış."""
        _, _, _, close = _ohlc()
        assert estimate_sigma_daily(close, window=21) == pytest.approx(
            close_to_close_sigma(close, 21), rel=1e-12
        )

    def test_dispatch_yang_zhang(self):
        open_, high, low, close = _ohlc()
        assert estimate_sigma_daily(
            close, high=high, low=low, open_=open_, window=21, method="yang_zhang"
        ) == pytest.approx(yang_zhang_sigma(open_, high, low, close, 21), rel=1e-12)

    def test_ohlc_method_without_data_raises(self):
        _, _, _, close = _ohlc()
        with pytest.raises(ValueError, match="gerekli"):
            estimate_sigma_daily(close, window=21, method="yang_zhang")

    def test_unknown_method_raises(self):
        _, _, _, close = _ohlc()
        with pytest.raises(ValueError, match="Bilinmeyen method"):
            estimate_sigma_daily(close, window=21, method="bogus")

    def test_valid_estimators_constant(self):
        assert "yang_zhang" in VALID_ESTIMATORS
        assert "close_to_close" in VALID_ESTIMATORS


# ---------------------------------------------------------------------------
# kyle_impact opt-in - varsayılan korunumu (regression)
# ---------------------------------------------------------------------------
class TestKyleImpactCalibration:

    def test_default_unchanged_regression(self):
        """sigma_method varsayılanı → eski inline formülle birebir aynı."""
        _, _, _, close = _ohlc()
        adv, order = 1_000_000.0, 5_000.0
        log_ret = np.log(close / close.shift(1)).dropna()
        sigma = float(log_ret.iloc[-21:].std())
        expected = 1.0 * sigma * np.sqrt(order / adv)
        assert kyle_impact(close, order, adv) == pytest.approx(expected, rel=1e-12)

    def test_yang_zhang_opt_in_uses_ohlc(self):
        open_, high, low, close = _ohlc()
        adv, order = 1_000_000.0, 5_000.0
        yz = yang_zhang_sigma(open_, high, low, close, 21)
        expected = 1.0 * yz * np.sqrt(order / adv)
        got = kyle_impact(
            close, order, adv, sigma_method="yang_zhang", high=high, low=low, open_=open_
        )
        assert got == pytest.approx(expected, rel=1e-12)


# ---------------------------------------------------------------------------
# spread nokta-tahmin agregasyonu
# ---------------------------------------------------------------------------
class TestSpreadPointEstimate:

    def test_last_equals_iloc_minus1(self):
        s = pd.Series([0.001, 0.002, 0.003, 0.004, 0.005])
        assert _spread_point_estimate(s, "last") == pytest.approx(0.005)

    def test_mean_and_median_over_window(self):
        s = pd.Series([0.001, 0.002, 0.003, 0.004, 0.010])
        assert _spread_point_estimate(s, "mean", agg_window=5) == pytest.approx(0.004)
        assert _spread_point_estimate(s, "median", agg_window=5) == pytest.approx(0.003)

    def test_median_resists_outlier(self):
        """Son değer aykırı (0.10) → median etkilenmez, last fırlar."""
        s = pd.Series([0.002, 0.002, 0.003, 0.002, 0.100])
        assert _spread_point_estimate(s, "last") == pytest.approx(0.100)
        assert _spread_point_estimate(s, "median", agg_window=5) == pytest.approx(0.002)

    def test_unknown_agg_raises(self):
        s = pd.Series([0.001, 0.002])
        with pytest.raises(ValueError, match="Bilinmeyen spread_agg"):
            _spread_point_estimate(s, "bogus")


# ---------------------------------------------------------------------------
# round_trip_cost_v2 opt-in - varsayılan korunumu
# ---------------------------------------------------------------------------
class TestRoundTripCalibration:

    def test_default_unchanged_regression(self):
        """spread_agg/sigma_method varsayılanları → eski sonuç birebir."""
        open_, high, low, close = _ohlc()
        adv, order = 1_000_000.0, 1_000.0
        spread_last = float(abdi_ranaldo_spread(close, high, low, 21).dropna().iloc[-1])
        log_ret = np.log(close / close.shift(1)).dropna()
        sigma = float(log_ret.iloc[-21:].std())
        impact = sigma * np.sqrt(order / adv)
        r = round_trip_cost_v2(close, high, low, order, adv)
        assert r["spread_cost_pct"] == pytest.approx(spread_last, rel=1e-12)
        assert r["impact_cost_pct"] == pytest.approx(impact, rel=1e-12)
        assert r["round_trip_cost_pct"] == pytest.approx(2 * (spread_last + impact), rel=1e-12)
        assert r["commission_pct"] == 0.0

    def test_median_agg_changes_spread_keeps_formula(self):
        """spread_agg=median → spread değişebilir ama formül + commission korunur."""
        open_, high, low, close = _ohlc(n=120, seed=5)
        r = round_trip_cost_v2(
            close, high, low, 1_000.0, 1_000_000.0,
            sigma_method="yang_zhang", open_=open_, spread_agg="median", agg_window=5,
        )
        assert r["commission_pct"] == 0.0
        assert r["round_trip_cost_pct"] == pytest.approx(
            2 * (r["spread_cost_pct"] + r["impact_cost_pct"]), rel=1e-12
        )
        assert r["spread_cost_pct"] >= 0.0
