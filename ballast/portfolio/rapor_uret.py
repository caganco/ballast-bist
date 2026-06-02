"""6-aylık portföy raporu.

Sepet-testi metodolojisini (log/nominal → kümülatif → TÜFE-deflate TL-reel) **kütüphane
fonksiyonlarıyla** yeniden kullanır (scripts/'e bağlanmaz). State'ten gerçek portföyü
okur; canlı ZPX30 fiyatı, TÜFE, USDTRY, XU100 çeker; HAM metrik üretir.
Yorum YAPMAZ - sayı üretir. Gerçek işlem yürütmez.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from ballast.data.fetcher import fetch_macro_symbol
from ballast.data.macro_sources import fetch_tufe_series
from ballast.portfolio.setup_calculator import ZPX30_SYMBOL
from ballast.portfolio.state import load_state
from ballast.utils.config import get_reports_dir


def _close_ratio(symbol: str, start: str, end: str) -> float | None:
    """symbol için end/start kapanış oranı (ör. dönem büyüme çarpanı). None on failure."""
    try:
        df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"].dropna()
        if len(close) < 2:
            return None
        return float(close.iloc[-1] / close.iloc[0])
    except Exception:
        return None


def _tufe_mult(start: str, end: str) -> float | None:
    """TÜFE dönem çarpanı (son/ilk). None on failure."""
    try:
        t = fetch_tufe_series(start, end)
        if t is None or t.empty:
            return None
        return float(t.iloc[-1] / t.iloc[0])
    except Exception:
        return None


def hesapla_metrikler(state: dict | None = None) -> dict:
    """State + canlı veriden ham rapor metriklerini hesaplar."""
    state = state or load_state()
    bugun = date.today().isoformat()
    kurulum_tarihi: str = state["kurulum_tarihi"]
    kurulum_tl: float = state["kurulum_toplam_tl"]
    lot: int = state["zpx30_lot"]
    nakit: float = state["nakit_tl"]

    fiyat = fetch_macro_symbol(ZPX30_SYMBOL)
    guncel_deger = (lot * fiyat + nakit) if fiyat is not None else None

    nominal_carpan = (guncel_deger / kurulum_tl) if guncel_deger is not None else None
    tufe_mult = _tufe_mult(kurulum_tarihi, bugun)
    usdtry_mult = _close_ratio("TRY=X", kurulum_tarihi, bugun)
    xu100_mult = _close_ratio("XU100.IS", kurulum_tarihi, bugun)

    tl_reel_carpan = (
        nominal_carpan / tufe_mult
        if (nominal_carpan is not None and tufe_mult) else None
    )
    usd_reel_carpan = (
        nominal_carpan / usdtry_mult
        if (nominal_carpan is not None and usdtry_mult) else None
    )
    xu100_relative = (
        nominal_carpan / xu100_mult
        if (nominal_carpan is not None and xu100_mult) else None
    )

    rebalance_gecmisi = state.get("rebalance_gecmisi", [])
    kontrol_gecmisi = state.get("kontrol_gecmisi", [])
    toplam_maliyet_tl = sum(float(r.get("maliyet_tl", 0.0)) for r in rebalance_gecmisi)
    kacinilan_islem = sum(
        1 for k in kontrol_gecmisi if not k.get("rebalance_gerekli", False)
    )

    return {
        "rapor_tarihi": bugun,
        "kurulum_tarihi": kurulum_tarihi,
        "kurulum_tl": kurulum_tl,
        "guncel_fiyat": fiyat,
        "guncel_deger": guncel_deger,
        "nominal_carpan": nominal_carpan,
        "tufe_mult": tufe_mult,
        "usdtry_mult": usdtry_mult,
        "xu100_mult": xu100_mult,
        "tl_reel_carpan": tl_reel_carpan,
        "usd_reel_carpan": usd_reel_carpan,
        "xu100_relative": xu100_relative,
        "toplam_maliyet_tl": toplam_maliyet_tl,
        "kacinilan_islem": kacinilan_islem,
        "rebalance_sayisi": len(rebalance_gecmisi),
        "rebalance_gecmisi": rebalance_gecmisi,
    }


def _fmt(x, suffix="x", pct=False):
    if x is None:
        return "veri yok"
    if pct:
        return f"{(x - 1) * 100:+.2f}%"
    return f"{x:.3f}{suffix}"


def uret_rapor(state: dict | None = None, yaz: bool = True) -> str:
    """Markdown rapor üretir; yaz=True ise results/portfoy_rapor_<YYYY-MM>.md'ye yazar."""
    m = hesapla_metrikler(state)
    md = f"""# Portföy Raporu - {m['rapor_tarihi']}

> Ham sayı; yorum yok. Gerçek işlem yürütülmez.

## Genel
- Kurulum tarihi: {m['kurulum_tarihi']}
- Kurulum tutarı: {m['kurulum_tl']:,.2f} TL
- Güncel ZPX30 fiyat: {_fmt(m['guncel_fiyat'], suffix=' TL')}
- Güncel portföy değeri: {_fmt(m['guncel_deger'], suffix=' TL')}

## Getiri (birincil = TL-reel, TÜFE-deflate)
| Metrik | Çarpan | Getiri |
|--------|-------:|-------:|
| TL-nominal | {_fmt(m['nominal_carpan'])} | {_fmt(m['nominal_carpan'], pct=True)} |
| **TL-reel*** | {_fmt(m['tl_reel_carpan'])} | {_fmt(m['tl_reel_carpan'], pct=True)} |
| USD-reel | {_fmt(m['usd_reel_carpan'])} | {_fmt(m['usd_reel_carpan'], pct=True)} |
| XU100-relative | {_fmt(m['xu100_relative'])} | {_fmt(m['xu100_relative'], pct=True)} |

Deflatörler - TÜFE: {_fmt(m['tufe_mult'])}, USDTRY: {_fmt(m['usdtry_mult'])}, XU100: {_fmt(m['xu100_mult'])}.
\\* = birincil metrik (1.0 = reel başabaş).

## Disiplin / Maliyet
- Rebalance sayısı: {m['rebalance_sayisi']}
- Toplam ödenen maliyet: {m['toplam_maliyet_tl']:,.2f} TL
- Kaçınılan işlem (bant aşılmadı): {m['kacinilan_islem']}

## Rebalance Tarihleri
"""
    if m["rebalance_gecmisi"]:
        for r in m["rebalance_gecmisi"]:
            md += (f"- {r.get('tarih','?')} | {r.get('yon','?')} | "
                   f"{r.get('lot','?')} lot | {float(r.get('maliyet_tl',0)):,.2f} TL\n")
    else:
        md += "- (henüz rebalance yok)\n"

    if yaz:
        out = get_reports_dir() / f"portfoy_rapor_{m['rapor_tarihi'][:7]}.md"
        out.write_text(md, encoding="utf-8")
    return md


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(uret_rapor())
