# Rebalance Bant Testi Sonuçları (Stage-0)

> **Not:** Yalnızca **ham sayı**; "şu bant daha iyi" yorumu içermez.
> Parametreler Stage-0'da önceden tescil edilmiş ve
> dondurulmuştur; post-hoc ayarlama yapılmamıştır.

## 1. Stage-0 Parametreleri (değişmedi teyidi)

| Parametre | Değer |
|-----------|-------|
| Dönem | 2019-01-04 .. 2026-05-26 (önceki backtest ortak takvimi, 1829 gün) |
| Portföy | ZPX30_proxy (XU030 − TER) + TL mevduat (TP.TRY.MT02) |
| Başlangıç hedef | %80 borsa / %20 mevduat (test varsayımı; oran kararı ayrı) |
| Bantlar | ±3%, ±5%, ±7.5%, ±10%, ±15% |
| TER günlük | 0.00022 / 252 |
| Spread | Abdi-Ranaldo (XU030 OHLCV, window=21) - ZPX30 proxy, üst sınır |
| Birincil metrik | TL-reel kümülatif çarpan (TÜFE TP.FG.J0 deflate; 1.0 = reel başabaş) |
| TÜFE çarpanı (dönem) | 9.254x |

**Veri:** Önceki backtest'in `build_panel()` fonksiyonu yeniden kullanıldı (birebir aynı takvim + XU030 close +
mevduat + TÜFE). Spread için yalnızca XU030.IS OHLCV (High/Low/Close) ek olarak çekildi.
Spread warm-up (ilk 21 gün rolling NaN) `bfill` ile dolduruldu.

## 2. Sonuç Tablosu (HAM)

| Bant | Rebalance sayısı | TL-reel kümülatif* | Toplam maliyet (bps) |
|------|-----------------:|-------------------:|---------------------:|
| ±3%   | 13 | 1.359x | 760.3 |
| ±5%   |  4 | 1.353x | 208.9 |
| ±7.5% |  3 | 1.382x |  49.3 |
| ±10%  |  1 | 1.360x |  38.3 |
| ±15%  |  0 | 1.347x |   0.0 |

\* = birincil metrik (TÜFE-deflate kümülatif TL-reel çarpan).
Toplam maliyet (bps) = her rebalance'taki spread (bps) toplamı.

## 3. Rebalance Tarihleri

Format: `YYYY-MM-DD | yön (+ borsa fazla / − borsa eksik) | işlem büyüklüğü (normalize portföy birimi)`

### ±3% (n=13)
```
2020-03-16 | − | 0.0397
2020-06-22 | + | 0.0374
2021-12-01 | + | 0.0526
2021-12-16 | + | 0.0728
2021-12-21 | − | 0.0595
2022-04-11 | + | 0.0755
2022-09-05 | + | 0.1015
2022-11-07 | + | 0.1228
2023-01-02 | + | 0.1519
2023-02-01 | − | 0.1214
2023-07-17 | + | 0.1760
2024-10-03 | − | 0.2470
2025-03-21 | − | 0.2820
```

### ±5% (n=4)
```
2021-12-16 | + | 0.1199
2022-10-17 | + | 0.1758
2023-07-17 | + | 0.2808
2025-02-21 | − | 0.4222
```

### ±7.5% (n=3)
```
2022-08-22 | + | 0.2045
2023-07-17 | + | 0.4177
2025-04-29 | − | 0.6265
```

### ±10% (n=1)
```
2022-11-01 | + | 0.3523
```

### ±15% (n=0)
```
(rebalance yok - borsa oranı dönem boyunca ±15% bandını hiç aşmadı = saf al-tut 80/20)
```

## 4. Kapsam Dışı (yapılmayanlar)

- **N=1:** tek başlangıç tarihi (2019-01-04), tek tarihsel patika. İstatistiksel anlamlılık yok.
- **Spread = XU030 OHLCV proxy, üst sınır.** ZPX30 ETF bid-ask genelde daha düşüktür;
  tracking error ihmal edildi. Maliyet formülü tam spread × işlem (halve edilmedi).
- **%80/%20 başlangıç oranı bir test varsayımıdır;** oran kararı bu testin kapsamı dışında.
- Hiçbir bant "kazanan/daha iyi" işaretlenmedi; sayılar ham.

## 5. Ham Karar Sorusu (yorumsuz)

> "Dar bant artan getiri mi sağlıyor, yoksa maliyet mi artıyor?"

Sayılar tabloda; bu rapor yorum içermez.

## 6. Sanity Check

`n_rebal(±15%)=0 < n_rebal(±3%)=13` ✓ - rebalance sayısı bant genişledikçe monoton azalır
(13 → 4 → 3 → 1 → 0). Mantık hatası yok.

## 7. Üretilebilirlik

```
python scripts/rebalance_band_test.py     # PYTHONPATH=. , .env'de EVDS_API_KEY gerekli
```
Veri canlı çekilir (yfinance + EVDS); çalıştırma tarihine göre son satır kayabilir.
