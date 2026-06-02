"""İlk portföy kurulum hesaplayıcısı.

SAF ARİTMETİK + canlı fiyat. Hedef oran dondurulmuş (%87.5/%12.5);
bu modül yalnızca "kaç lot ZPX30 + kaç TL mevduat" rakamını hesaplar.
Lot tam sayı olmalı (kısmi pay alınamaz) → artık nakit mevduata eklenir.
Gerçek alım-satım YÜRÜTÜLMEZ.
"""
from __future__ import annotations

import math

from ballast.data.fetcher import fetch_macro_symbol

ZPX30_SYMBOL = "ZPX30.IS"
HEDEF_BORSA_ORAN = 0.875


def hesapla_ilk_portfoy(
    toplam_tl: float,
    zpx30_fiyat: float | None = None,
    hedef_borsa_oran: float = HEDEF_BORSA_ORAN,
) -> dict:
    """İlk portföy dağılımını hesaplar.

    Args:
        toplam_tl: Toplam yatırılacak TL.
        zpx30_fiyat: ZPX30 birim fiyatı. **None → fetch_macro_symbol ile CANLI çekilir**
                     (gerçek kurulumda canlı fiyat kullanılır, gömülü sabit DEĞİL).
        hedef_borsa_oran: Hedef borsa oranı (default 0.875).

    Returns:
        dict: borsa_tl, nakit_tl, zpx30_lot, zpx30_fiyat, zpx30_gercek_tl,
              artik_nakit_tl, gercek_borsa_oran.

    Raises:
        ValueError: toplam_tl <= 0, fiyat çekilemedi, ya da fiyat <= 0.
    """
    if toplam_tl <= 0:
        raise ValueError("toplam_tl pozitif olmalı")

    if zpx30_fiyat is None:
        zpx30_fiyat = fetch_macro_symbol(ZPX30_SYMBOL)
        if zpx30_fiyat is None:
            raise ValueError(
                f"{ZPX30_SYMBOL} canlı fiyatı çekilemedi - zpx30_fiyat parametresini verin"
            )
    if zpx30_fiyat <= 0:
        raise ValueError("zpx30_fiyat pozitif olmalı")

    borsa_tl = toplam_tl * hedef_borsa_oran
    nakit_tl = toplam_tl * (1.0 - hedef_borsa_oran)
    zpx30_lot = math.floor(borsa_tl / zpx30_fiyat)
    zpx30_gercek_tl = zpx30_lot * zpx30_fiyat
    artik_nakit_tl = nakit_tl + (borsa_tl - zpx30_gercek_tl)
    gercek_borsa_oran = zpx30_gercek_tl / toplam_tl

    return {
        "borsa_tl": borsa_tl,
        "nakit_tl": nakit_tl,
        "zpx30_lot": zpx30_lot,
        "zpx30_fiyat": zpx30_fiyat,
        "zpx30_gercek_tl": zpx30_gercek_tl,
        "artik_nakit_tl": artik_nakit_tl,
        "gercek_borsa_oran": gercek_borsa_oran,
    }


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    # Canlı fiyatla örnek kurulum (gerçek tutar kullanıcı tarafından girilir)
    r = hesapla_ilk_portfoy(300_000.0)  # zpx30_fiyat=None → canlı
    print(f"ZPX30 canlı fiyat : {r['zpx30_fiyat']:.2f} TL")
    print(f"ZPX30 lot         : {r['zpx30_lot']}")
    print(f"ZPX30 gerçek tutar: {r['zpx30_gercek_tl']:,.2f} TL")
    print(f"Mevduat (artık)   : {r['artik_nakit_tl']:,.2f} TL")
    print(f"Gerçek borsa oranı: {r['gercek_borsa_oran']*100:.2f}%")
