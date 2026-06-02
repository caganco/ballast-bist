"""Bantlı rebalance kontrolü (yalnızca SİNYAL üretir).

Hedef %87.5 ± %7.5 → ZPX30 oranı %80 (alt) - %95 (üst). Bant dışına çıkınca
rebalance sinyali. Takvim-tetikli DEĞİL - yalnızca bant-tetikli.
Gerçek alım-satım YÜRÜTÜLMEZ; çıktı, aracı kurumda elle uygulanacak yön+lot.
"""
from __future__ import annotations

import math

HEDEF_ORAN = 0.875
BANT = 0.075


def rebalance_kontrol(
    zpx30_lot: int,
    zpx30_fiyat: float,
    nakit_tl: float,
    hedef_oran: float = HEDEF_ORAN,
    bant: float = BANT,
) -> dict:
    """Mevcut borsa oranını hesaplar, bant kontrolü yapar.

    Args:
        zpx30_lot: Elde tutulan ZPX30 lot sayısı.
        zpx30_fiyat: Güncel ZPX30 birim fiyatı.
        nakit_tl: Mevduat/nakit TL.
        hedef_oran: Hedef borsa oranı (default 0.875).
        bant: Sapma eşiği (default 0.075 → %80-%95 aralığı).

    Returns:
        dict: mevcut_borsa_oran, sapma, rebalance_gerekli, yon ("AL"/"SAT"/None),
              islem_tl, islem_lot.

    Raises:
        ValueError: fiyat <= 0 ya da portföy değeri <= 0.
    """
    if zpx30_fiyat <= 0:
        raise ValueError("zpx30_fiyat pozitif olmalı")

    borsa_tl = zpx30_lot * zpx30_fiyat
    port = borsa_tl + nakit_tl
    if port <= 0:
        raise ValueError("portföy değeri pozitif olmalı")

    mevcut_oran = borsa_tl / port
    sapma = mevcut_oran - hedef_oran
    rebalance_gerekli = abs(sapma) > bant

    if not rebalance_gerekli:
        yon: str | None = None
        islem_tl = 0.0
        islem_lot = 0
    else:
        # sapma<0 → borsa eksik → AL; sapma>0 → borsa fazla → SAT
        yon = "AL" if sapma < 0 else "SAT"
        islem_tl = abs(hedef_oran * port - borsa_tl)
        islem_lot = math.floor(islem_tl / zpx30_fiyat)

    return {
        "mevcut_borsa_oran": mevcut_oran,
        "sapma": sapma,
        "rebalance_gerekli": rebalance_gerekli,
        "yon": yon,
        "islem_tl": islem_tl,
        "islem_lot": islem_lot,
    }
