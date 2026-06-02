"""Unit tests for transaction_cost_v2. 8 test, tümü synthetic veri."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ballast.costs.transaction_cost_v2 import (
    abdi_ranaldo_spread,
    dividend_net,
    gain_tax,
    kyle_impact,
    round_trip_cost_v2,
)

# ---------------------------------------------------------------------------
# Yardımcı fabrikalar
# ---------------------------------------------------------------------------

def _bounce_series(n: int = 50) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Close midpoint etrafında alterne eder → garantili negatif gamma."""
    close = pd.Series([99.0 if i % 2 == 0 else 101.0 for i in range(n)])
    high = pd.Series([102.0] * n)
    low = pd.Series([98.0] * n)
    return close, high, low


def _flat_series(n: int = 50, price: float = 100.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Sabit fiyat - diff=0 → gamma=0 → spread=0."""
    s = pd.Series([price] * n)
    return s, s.copy(), s.copy()


def _trending_close(n: int = 50, seed: int = 42) -> pd.Series:
    """Hafif trendli close - sıfır olmayan sigma."""
    rng = np.random.default_rng(seed)
    log_ret = rng.normal(0.0002, 0.018, n)
    return pd.Series(100.0 * np.exp(np.cumsum(log_ret)))


# ---------------------------------------------------------------------------
# T-1 / T-2 - abdi_ranaldo_spread
# ---------------------------------------------------------------------------

class TestAbdiRanaldoSpread:

    def test_T1_negative_covariance_gives_positive_spread(self):
        """T-1: Bounce seri → negatif gamma → spread_pct > 0."""
        close, high, low = _bounce_series(n=50)
        result = abdi_ranaldo_spread(close, high, low, window=21)
        last = result.dropna().iloc[-1]
        assert last > 0, f"Spread 0'dan büyük olmalı, got {last}"

    def test_T2_flat_series_zero_spread(self):
        """T-2: Sabit seri → diff=0 → gamma=0 → spread_pct == 0."""
        close, high, low = _flat_series(n=50)
        result = abdi_ranaldo_spread(close, high, low, window=21)
        last = result.dropna().iloc[-1]
        assert last == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# T-3 / T-4 - kyle_impact
# ---------------------------------------------------------------------------

class TestKyleImpact:

    def test_T3_small_order_negligible_impact(self):
        """T-3: order/adv = 0.001 → impact_pct < 0.01 (ihmal düzeyinde)."""
        close = _trending_close(n=50)
        adv = 1_000_000.0
        order_value = adv * 0.001
        impact = kyle_impact(close, order_value, adv, window=21)
        assert impact < 0.01, f"impact={impact:.6f}; < 0.01 bekleniyor"

    def test_T4_order_equals_adv_scale_check(self):
        """T-4: order_value == adv → impact_pct == lambda_kyle * sigma_daily."""
        close = _trending_close(n=50)
        adv = 500_000.0
        order_value = adv          # oran = 1.0 → sqrt(1) = 1
        lambda_kyle = 1.0
        impact = kyle_impact(close, order_value, adv, window=21, lambda_kyle=lambda_kyle)
        log_ret = np.log(close / close.shift(1)).dropna()
        sigma = float(log_ret.iloc[-21:].std())
        assert impact == pytest.approx(lambda_kyle * sigma, rel=1e-9)


# ---------------------------------------------------------------------------
# T-5 / T-6 - vergi utility
# ---------------------------------------------------------------------------

class TestTaxUtility:

    def test_T5_dividend_net_100_tl(self):
        """T-5: 100 TL brüt → 85 TL net (DIVIDEND_TAX_RATE=0.15)."""
        assert dividend_net(100.0) == pytest.approx(85.0)

    def test_T6_gain_tax_always_zero(self):
        """T-6: Geçici-67 → kazanç stopajı = 0.0 (GAIN_TAX_RATE=0.0)."""
        assert gain_tax(50_000.0) == pytest.approx(0.0)
        assert gain_tax(1.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T-7 / T-8 - round_trip_cost_v2
# ---------------------------------------------------------------------------

class TestRoundTripCostV2:

    def test_T7_round_trip_equals_twice_spread_plus_impact(self):
        """T-7: round_trip == 2*(spread+impact), commission == 0."""
        close, high, low = _bounce_series(n=50)
        result = round_trip_cost_v2(close, high, low, order_value=1_000.0, adv=1_000_000.0)
        expected_rt = 2 * (result["spread_cost_pct"] + result["impact_cost_pct"])
        assert result["round_trip_cost_pct"] == pytest.approx(expected_rt, rel=1e-9)
        assert result["commission_pct"] == pytest.approx(0.0)

    def test_T8_commission_always_zero(self):
        """T-8: commission_pct her parametre kombinasyonunda 0.0 (yerli hisse)."""
        close, high, low = _bounce_series(n=50)
        for order in [500.0, 10_000.0, 500_000.0]:
            result = round_trip_cost_v2(close, high, low, order_value=order, adv=1_000_000.0)
            assert result["commission_pct"] == 0.0, f"order={order}: commission sıfır olmalı"
