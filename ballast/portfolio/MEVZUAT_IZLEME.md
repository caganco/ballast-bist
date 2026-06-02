# MEVZUAT İZLEME - ZPX30 Vergi/Statü (6-aylık)

> Periyot: **Haziran + Aralık** (yılda 2). ZPX30'un cazibesi yerli-hisse vergi
> rejimine dayanır; bu istisnalar değişirse gözden geçirilir.
> Bu bir izleme prosedürüdür - otomatik işlem/karar üretmez.

## İzlenecek Kalemler

1. **Hisse-senedi-yoğun fon stopaj istisnası (%0) korunuyor mu?**
   - Kaynak: GİB, KAP duyuruları, vergi-takip siteleri (ör. vergialgi.com benzeri).
   - Risk: **Mart 2026 taslağı** - %51+ hisse fonları için değişiklik gündemdeydi.
     ZPX30 hisse-senedi-yoğun (%80+) → şimdilik istisna korunuyor.
   - Değişirse: ZPX30 net getiri cazibesi düşer → **gözden geçir**.

2. **Yerli hisse kazanç stopajı %0 (Geçici-67) devam ediyor mu?**
   - `transaction_cost_v2.GAIN_TAX_RATE` bu varsayıma dayanır (şu an 0.0).

3. **ZPX30 TER (gider oranı) değişti mi?**
   - Kaynak: yıllık KAP gider oranı bildirimi. Backtest TER drag = 0.00022 (yıllık).

4. **ZPX30 fon statüsü** (kapatma / birleşme riski).
   - Kaynak: KAP duyuruları.

## Çıktı

6-aylık **kısa not**: her kalem için "değişmedi / değişti (detay)".
Herhangi bir değişiklik varsa → gözden geçirilir.
