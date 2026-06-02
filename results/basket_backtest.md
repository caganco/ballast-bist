# Sepet Testi Backtest Sonuçları (Stage-0)

> **Not:** Bu rapor yalnızca **ham sayı** içerir; "şu seçenek daha iyi" türü
> yorum içermez. Parametreler Stage-0'da önceden
> tescil edilmiş ve dondurulmuştur; post-hoc ayarlama yapılmamıştır.

## 1. Stage-0 Dondurulmuş Parametreler

| Parametre | Değer |
|-----------|-------|
| Dönem (istenen) | 2019-01-01 .. 2026-05-31 |
| Dönem (gerçekleşen ortak takvim) | 2019-01-04 .. 2026-05-26 |
| İşlem günü sayısı | 1829 gün (~7.39 yıl) |
| Birincil metrik | Kümülatif **TL-reel** getiri (TÜFE-deflate) |
| İkincil metrikler | TL-nominal, USD-reel, TL-reel CAGR |
| Getiri tanımı | Günlük log-getiri → kümülatif → exp(çarpan) |
| TÜFE deflatörü | TP.FG.J0 (aylık CPI, günlük ffill) |
| USD deflatörü | TRY=X (USDTRY) |

### Seçenekler
| Kod | Tanım | Kaynak |
|-----|-------|--------|
| SEÇ-A | XU050 (BIST-50) | **VERİ YOK** - aşağıya bakınız |
| SEÇ-B | XU030.IS ham | yfinance |
| SEÇ-C | XU030.IS − TER drag (0.00022/252 günlük) | ZPX30 proxy |
| NULL-1 | XU100.IS | yfinance |
| NULL-2 | TL mevduat (TP.TRY.MT02), bileşik | EVDS/TCMB |

## 2. Veri Kalitesi

| Seri | Ham satır | Not |
|------|-----------|-----|
| XU030.IS | 1835 | Volume==0 → NaN, ffill ≤5g, dropna uygulandı |
| XU100.IS | 1845 | aynı temizlik kuralı |
| TRY=X | 1928 | FX volume yapısal olarak 0 → volume filtresi uygulanmadı |
| TÜFE (TP.FG.J0) | 2708 günlük (aylıktan ffill) | 398.07 → 3683.83 (çarpan 9.254x) |
| Mevduat (TP.TRY.MT02) | 385 haftalık gözlem → günlük ffill | %22.85 → %48.96 yıllık |
| **Ortak takvim (inner-join)** | **1829** | Üç fiyat serisinin kesişimi; TÜFE+mevduat ffill ile hizalandı |

**Dönem boyu deflatör çarpanları:** TÜFE = **9.254x**, USDTRY = **8.387x**.

### SEÇ-A (XU050) - VERİ YOK
ZPX30/XU050 tarihsel günlük kapanış verisi **yfinance'ta mevcut değil** (yalnızca
1g/5g anlık snapshot döner, 2019-2026 tarihsel seri yok). `finans.mynet.com`
XU050 sayfası da denenmiştir: ana sayfa + endekshisseleri (sabit liste) ve anlık
veri uçları erişilebilir, ancak **tarihsel günlük kapanış sunan bir uç yok**
(zaman-serisi / tarihselveriler / history alt-yolları HTTP 404). SEÇ-A bu nedenle
boş bırakılmıştır. Yeni veri kaynağı açılmamıştır.

### SEÇ-C (ZPX30) - proxy notu
**SEÇ-C = XU030 proxy − TER drag.** ZPX30 tarihsel verisi yfinance'ta mevcut
değildir; XU030.IS getirisi üzerine günlük TER drag (0.00022/252) uygulanmıştır.
**Tracking error ihmal edilmiştir.**

## 3. Sonuçlar (HAM)

| Seçenek | TL-nominal | TL-reel* | USD-reel | TL-reel CAGR |
|---------|-----------:|---------:|---------:|-------------:|
| SEÇ-A (XU050) | - | - | - | - |
| SEÇ-B (XU030 ham) | 13.909x | **1.503x** | 1.658x | 5.67% |
| SEÇ-C (XU030 − TER) | 13.886x | **1.501x** | 1.656x | 5.65% |
| NULL-1 (XU100) | 15.381x | **1.662x** | 1.834x | 7.12% |
| NULL-2 (TL mevduat) | 6.789x | **0.734x** | 0.809x | −4.10% |

\* = **birincil metrik** (TÜFE-deflate kümülatif TL-reel çarpan; 1.0 = reel başabaş).

## 4. Kapsam Dışı (yapılmayanlar)

- Hiçbir seçenek "daha iyi/kazanan" olarak işaretlenmedi - sayılar ham.
- Stage-0 parametreleri (dönem, metrik, seçenekler, TER) değiştirilmedi.
- TER dışında maliyet parametresi uydurulmadı; temettü verimi için kaynaksız sayı üretilmedi.
- ZPX30 yerine başka ETF "eşdeğer" sayılmadı; SEÇ-C açıkça XU030 proxy'dir.

## 5. Üretilebilirlik

```
python scripts/basket_backtest.py          # PYTHONPATH=. , .env'de EVDS_API_KEY gerekli
```
Veri canlı çekilir (yfinance + EVDS); çalıştırma tarihine göre son satır kayabilir.
