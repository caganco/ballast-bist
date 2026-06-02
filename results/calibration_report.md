# Kalibrasyon Raporu - Hesaplama Araçlarında Gürültü Azaltma (GOAL)

**Tarih:** 2026-06-02
**Amaç:** Sistemin hiçbir temel mantığını değiştirmeden, mevcut hesaplama
araçlarının *doğruluğunu* (örnekleme-gürültüsünü) artırmak. Metodoloji aynı kalır;
araçlar daha az gürültü üretir, daha net olur.
**Ölçüm aracı:** `scripts/calib_research.py` (salt-okunur, gerçek XU030.IS OHLC
2019-01-02 → 2026-05-26, **1835 gün**).

---

## 0. Disiplin / Kapsam

Bu çalışma **kalibrasyon**dur, model değişikliği değil. İlke:

> **Estimand sabit, varyans düşük.** Her ekleme aynı büyüklüğü (σ_daily, spread
> seviyesi) tahmin eder; yalnız tahmincinin örnekleme-gürültüsü azalır.

Tüm değişiklikler **opt-in** ve **varsayılanda davranış-koruyan**. Varsayılan
çağrılar (eski imza) bire-bir aynı sayıyı döndürür - regression testleriyle kanıtlı
(`tests/test_volatility_calibration.py::test_default_unchanged_regression`).

**Dokunulmayanlar:** round-trip mantığı, Abdi-Ranaldo gamma formülü (çekirdek),
vergi sabitleri, dondurulmuş Stage-0 parametre ve sonuçları
(bu salt-okunur bir tanılamadır, yeni bir ölçüm değildir).

---

## 1. Tespit - Mevcut araçlardaki gürültü kaynakları

İki hesaplama girdisi gürültülü nokta-tahmin üretiyor:

1. **`kyle_impact` σ_daily girdisi** - close-to-close `std(ln C_t/C_{t-1})`. Yalnız
   kapanışları kullanır; gün-içi High/Low/Open bilgisini atar → düşük istatistiksel
   verim, yüksek gün-günden zıplama.
2. **`round_trip_cost_v2` spread nokta-tahmini** - Abdi-Ranaldo serisinin *son günü*
   (`iloc[-1]`). Tek günün tahmini, AR'nin doğası gereği oynak.

---

## 2. Ölçüm A - σ_daily tahminci gürültüsü (window=21)

Gürültü ölçüsü `rel_noise` = ardışık-gün |Δσ| ortalaması / σ seviyesi. Aynı
estimand'i tahmin eden iki seride **düşük rel_noise = az örnekleme gürültüsü**
(gerçek günlük volatilite günden güne yavaş değişir; yüksek-frekanslı zıplama
tahmincinin kendi varyansıdır).

| Tahminci | σ seviye | rel_noise | C2C'ye göre gürültü-azaltma |
|---|---|---|---|
| close-to-close (MEVCUT) | 0.01667 | 0.0378 | 1.00x |
| Parkinson (1980) | 0.01405 | 0.0252 | 1.50x |
| Garman-Klass (1980) | 0.01360 | 0.0239 | **1.58x** |
| Rogers-Satchell (1991) | 0.01341 | 0.0261 | 1.45x |
| **Yang-Zhang (2000)** | **0.01554** | **0.0266** | **1.42x** |

**Seviye/estimand uyumu:** Yang-Zhang / close-to-close = **0.932** (~1.0).

### Neden varsayılan-opt-in = Yang-Zhang (Garman-Klass değil)

Garman-Klass gürültüyü en çok düşürür (1.58x) **ama** σ seviyesini düşük tahmin eder
(0.0136 vs 0.0167; oran 0.816) çünkü **gece (overnight) varyansını dışlar**. Bu,
*estimand'i kaydırır* - σ_daily artık aynı şey değildir. Disiplin gereği reddedildi.

Yang-Zhang gece + gün-içi + Rogers-Satchell bileşenlerini birleştirir; **tüm günlük
varyansı yakalar** → seviyesi close-to-close ile en uyumlu (0.932). Estimand'i
KORUYARAK 1.42x gürültü azaltır. BIST'te gece sıçramaları (gap) önemli olduğundan
doğru tercih budur (Yang & Zhang 2000, drift-bağımsız + gap-dayanıklı).

> Parkinson/Garman-Klass/Rogers-Satchell yine de sağlanır (araştırma/karşılaştırma),
> ama gece-hariç oldukları için **kyle varsayılan opt-in'i Yang-Zhang**.

---

## 3. Ölçüm B - Abdi-Ranaldo spread nokta-tahmini gürültüsü

| Metrik | Değer |
|---|---|
| Geçerli pencere | 1814 |
| Truncation oranı (gamma≥0 → spread=0) | **0.418** |
| Spread ort / medyan | 0.00476 / 0.00296 |
| Son-değer `rel_noise` (`iloc[-1]`) | **0.1760** |

%42 truncation + 0.176 rel_noise → tek-gün nokta-tahmini oynak.

### Reddedilen yol: gamma'yı trimlemek/medyanlamak

İlk aday "robust gamma merkezi" (trimmed/median) idi. **Reddedildi:** AR gamma'sı
`E[diff_t · diff_{t-1}]` kovaryansıdır; çarpım dağılımı asimetriktir → trimmed mean
*yanlı* olur, AR estimand'ini kaydırır. Bu, "temel mantığı değiştirme" yasağını
ihlal eder. Çekirdek `abdi_ranaldo_spread` **hiç değiştirilmedi**.

### Seçilen yol: nokta-tahmin agregasyonu (estimand-koruyan)

Zaten hesaplanmış geçerli spread serisinin trailing **mean/median**'ı - *aynı spread
seviyesi*, daha düşük varyans:

| Agregasyon | rel_noise (median) | seviye/son-değer |
|---|---|---|
| son-değer (MEVCUT) | 0.1760 | 1.000 |
| trailing 3g | 0.1015 | 1.000 |
| **trailing 5g** | **0.0833** (~2.1x) | 0.999 |
| trailing 10g | 0.0654 (~2.7x) | 1.001 |

Seviye oranı ~1.000 → estimand korunur. **median@5 → 2.1x gürültü azaltma**,
aykırı-dayanıklı. `round_trip_cost_v2(spread_agg="median")` opt-in olarak eklendi.

---

## 4. Uygulanan değişiklikler (hepsi additive / opt-in / default-koruyan)

| Dosya | Değişiklik |
|---|---|
| `ballast/costs/volatility.py` (YENİ) | Parkinson/Garman-Klass/Rogers-Satchell/Yang-Zhang σ_daily tahmincileri + `estimate_sigma_daily` seçici |
| `ballast/costs/transaction_cost_v2.py` | `kyle_impact(sigma_method=…, open_/high/low)` opt-in; `round_trip_cost_v2(sigma_method, spread_agg, agg_window)` opt-in; `_spread_point_estimate` yardımcı. **Varsayılanlar bire-bir korunur**; AR gamma çekirdeği değişmedi |
| `tests/test_volatility_calibration.py` (YENİ) | 19 test: tahminci matematiği (kapalı-form + elle-hesap), dispatch, **default-korumanın regression kanıtı** |
| `scripts/calib_research.py` (YENİ) | Salt-okunur ölçüm aracı (gürültü tanılaması; tekrar çalıştırılabilir) |

---

## 5. Doğrulama

- **Testler:** `python -m pytest tests/ -v` → **64 passed** (45 mevcut + 19 yeni).
  Mevcut 45 testin tamamı değişmeden geçer; default-koruma regression testleriyle
  kanıtlanmış (σ ve spread varsayılan yolu eski formülle `rel=1e-12` eşit).
- **Estimand korunumu:** YZ/C2C seviye 0.932; spread agg seviye ~1.000.
- **Gürültü azaltma:** σ_daily 1.42x (Yang-Zhang), spread 2.1x (median@5).

---

## 6. Kullanım (Faz-2 araçları için öneri)

Maliyet tahmini gerektiğinde daha az gürültülü çağrı:

```python
round_trip_cost_v2(
    close, high, low, order_value, adv,
    sigma_method="yang_zhang", open_=open_,   # σ_daily: 1.42x az gürültü, estimand korunur
    spread_agg="median", agg_window=5,         # spread: 2.1x az gürültü, aykırı-dayanıklı
)
```

Eski çağrılar (yeni argüman vermeden) **aynen** çalışır.

---

## Kaynaklar

- Parkinson, M. (1980). *J. Business* 53(1), 61-65.
- Garman, M. & Klass, M. (1980). *J. Business* 53(1), 67-78.
- Rogers, L.C.G. & Satchell, S.E. (1991). *Ann. Applied Prob.* 1(4), 504-512.
- Yang, D. & Zhang, Q. (2000). *J. Business* 73(3), 477-491.
- Abdi, F. & Ranaldo, A. (2017). *Review of Financial Studies* 30(12), 4437-4480.
