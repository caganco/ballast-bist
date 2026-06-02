"""Unit tests for ballast.portfolio - saf mantık, canlı çağrı yok.

Kapsam:
  - hesapla_ilk_portfoy: tam-lot floor, oran/artık-nakit tutarlılığı, canlı-fiyat mock
  - rebalance_kontrol: AL/SAT/None sinyali, bant sınırları, islem_lot floor
"""
from __future__ import annotations

import math
from unittest.mock import patch

import pytest

from ballast.portfolio.rebalance_check import rebalance_kontrol
from ballast.portfolio.setup_calculator import hesapla_ilk_portfoy


class TestHesaplaIlkPortfoy:
    """hesapla_ilk_portfoy(): kurulum aritmetiği (sentetik fiyat=198)."""

    def test_tam_lot_floor(self):
        """300K, fiyat=198 → lot = floor(262500/198) = 1325."""
        r = hesapla_ilk_portfoy(300_000.0, zpx30_fiyat=198.0)
        assert r["zpx30_lot"] == math.floor(262_500.0 / 198.0)
        assert r["zpx30_lot"] == 1325

    def test_oran_ve_nakit_tutarlilik(self):
        """borsa_tl + nakit_tl == toplam; artık nakit ≥ 0; gerçek oran ≤ hedef."""
        r = hesapla_ilk_portfoy(300_000.0, zpx30_fiyat=198.0)
        assert r["borsa_tl"] + r["nakit_tl"] == pytest.approx(300_000.0)
        assert r["artik_nakit_tl"] >= 0.0
        # Tam-lot floor → gerçek borsa oranı hedefin biraz altında
        assert r["gercek_borsa_oran"] <= 0.875
        assert r["gercek_borsa_oran"] == pytest.approx(
            r["zpx30_gercek_tl"] / 300_000.0
        )

    def test_artik_nakit_korunum(self):
        """artik_nakit = nakit + (borsa_tl - zpx30_gercek_tl) korunum kontrolü."""
        r = hesapla_ilk_portfoy(300_000.0, zpx30_fiyat=198.0)
        beklenen = r["nakit_tl"] + (r["borsa_tl"] - r["zpx30_gercek_tl"])
        assert r["artik_nakit_tl"] == pytest.approx(beklenen)
        # Toplam korunur: gerçek borsa + artık nakit == toplam
        assert r["zpx30_gercek_tl"] + r["artik_nakit_tl"] == pytest.approx(300_000.0)

    def test_canli_fiyat_none_ise_fetch_edilir(self):
        """zpx30_fiyat=None → fetch_macro_symbol çağrılır (mock), sabit gömülmez."""
        with patch(
            "ballast.portfolio.setup_calculator.fetch_macro_symbol",
            return_value=200.0,
        ) as mock_fetch:
            r = hesapla_ilk_portfoy(100_000.0)  # fiyat None → canlı
        mock_fetch.assert_called_once()
        assert r["zpx30_fiyat"] == 200.0
        assert r["zpx30_lot"] == math.floor(87_500.0 / 200.0)

    def test_canli_fiyat_cekilemezse_hata(self):
        """fetch_macro_symbol None dönerse ValueError."""
        with patch(
            "ballast.portfolio.setup_calculator.fetch_macro_symbol",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="canlı fiyatı çekilemedi"):
                hesapla_ilk_portfoy(100_000.0)

    def test_negatif_toplam_hata(self):
        with pytest.raises(ValueError, match="toplam_tl pozitif"):
            hesapla_ilk_portfoy(-1.0, zpx30_fiyat=198.0)


class TestRebalanceKontrol:
    """rebalance_kontrol(): bant-tetikli sinyal (hedef %87.5, bant ±%7.5)."""

    def test_band_icinde_islem_yok(self):
        """Oran tam hedefte (%87.5) → rebalance_gerekli False, yon None."""
        # borsa=87.5, nakit=12.5 → oran 0.875
        r = rebalance_kontrol(zpx30_lot=875, zpx30_fiyat=0.1, nakit_tl=12.5)
        assert r["mevcut_borsa_oran"] == pytest.approx(0.875)
        assert r["rebalance_gerekli"] is False
        assert r["yon"] is None
        assert r["islem_lot"] == 0

    def test_ust_band_asimi_sat(self):
        """Oran %95'in üstü → SAT sinyali."""
        # borsa=96, nakit=4 → oran 0.96 > 0.95
        r = rebalance_kontrol(zpx30_lot=960, zpx30_fiyat=0.1, nakit_tl=4.0)
        assert r["mevcut_borsa_oran"] == pytest.approx(0.96)
        assert r["rebalance_gerekli"] is True
        assert r["yon"] == "SAT"
        assert r["islem_lot"] >= 1

    def test_alt_band_asimi_al(self):
        """Oran %80'in altı → AL sinyali."""
        # borsa=78, nakit=22 → oran 0.78 < 0.80
        r = rebalance_kontrol(zpx30_lot=780, zpx30_fiyat=0.1, nakit_tl=22.0)
        assert r["mevcut_borsa_oran"] == pytest.approx(0.78)
        assert r["rebalance_gerekli"] is True
        assert r["yon"] == "AL"
        assert r["islem_lot"] >= 1

    def test_band_siniri_haric(self):
        """Tam %95 (sapma=+0.075) → abs(sapma) > bant False (sınır dahil değil)."""
        # borsa=95, nakit=5 → oran 0.95, sapma=0.075, abs>0.075 False
        r = rebalance_kontrol(zpx30_lot=950, zpx30_fiyat=0.1, nakit_tl=5.0)
        assert r["sapma"] == pytest.approx(0.075)
        assert r["rebalance_gerekli"] is False

    def test_islem_lot_floor(self):
        """islem_lot = floor(islem_tl / fiyat) - kısmi pay yok."""
        r = rebalance_kontrol(zpx30_lot=960, zpx30_fiyat=7.0, nakit_tl=280.0)
        assert r["rebalance_gerekli"] is True
        assert r["islem_lot"] == math.floor(r["islem_tl"] / 7.0)

    def test_sifir_fiyat_hata(self):
        with pytest.raises(ValueError, match="zpx30_fiyat pozitif"):
            rebalance_kontrol(zpx30_lot=100, zpx30_fiyat=0.0, nakit_tl=10.0)
