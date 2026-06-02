# PLAYBOOK - Bantlı Rebalance Bakımı (Faz-2)

> Donmuş kararlar: araç **ZPX30**, hedef **%87.5 borsa / %12.5 mevduat**,
> bant **±%7.5** (ZPX30 oranı %80-%95). Bu prosedür mekaniktir - sinyal araç verir,
> **emirler aracı kurumda elle girilir**. Bu araç canlı alım-satım yürütmez.

## Aylık Kontrol (≈5 dk, mekanik)

1. Güncel ZPX30 fiyatını al ve `rebalance_kontrol(...)` çalıştır:
   ```
   python -c "from ballast.portfolio.rebalance_check import rebalance_kontrol; \
   from ballast.portfolio.state import load_state; \
   from ballast.data.fetcher import fetch_macro_symbol; \
   s=load_state(); f=fetch_macro_symbol('ZPX30.IS'); \
   print(rebalance_kontrol(s['zpx30_lot'], f, s['nakit_tl']))"
   ```
2. `rebalance_gerekli == False` → **HİÇBİR ŞEY YAPMA.**
   State'e kontrol kaydı düş: `kontrol_gecmisi`'ye `{tarih, rebalance_gerekli: false}`,
   `son_kontrol` güncelle. Bu "kaçınılan işlem" sayısını besler (disiplin kanıtı).
3. `rebalance_gerekli == True` → "Rebalance Yürütme" adımına geç.

## Rebalance Yürütme (yalnızca bant aşıldığında)

1. Çıktıdaki `yon` (AL/SAT) + `islem_lot`'u oku.
2. Belirtilen lot kadar AL veya SAT emri **aracı kurumda elle** girilir.
3. Yeni `zpx30_lot` ve `nakit_tl`'yi state'e yaz (`save_state`).
4. `rebalance_gecmisi`'ye kayıt ekle: `{tarih, yon, lot, maliyet_tl}`;
   `son_rebalance` güncelle.

## Yapılmayacaklar (disiplin)

- Bant aşılmadıysa **işlem YOK** (takvim-tetikli değil, bant-tetikli).
- "Borsa düşüyor" diye **panik SAT YOK**.
- "Borsa yükseliyor" diye **FOMO AL YOK**.
- **Günlük bakma YOK** - aylık kontrol yeterli.
- Oranı/bandı/aracı keyfî değiştirme YOK (ayrı bir karardır).
