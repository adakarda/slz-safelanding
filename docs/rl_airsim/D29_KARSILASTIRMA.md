# Düzeltme 29 — tam karşılaştırma matrisi

> **Tarih:** 2026-10-27. **Ön kayıt ve karar:** [`../onkayit/rl_f0_onkayit.md`](../onkayit/rl_f0_onkayit.md),
> Düzeltme 29. **Ham sayılar:** [`veri/d29_ozet.csv`](veri/d29_ozet.csv) (tohum başına başarı dahil).
> **Görsel sürüm:** https://claude.ai/artifact/RNceK2XkYg7j92fSY8gAhN (özel; paylaşım sahibinden).
> Bütün sayılar **ölçülen**. Etiketler: _hesap, _tahmin.

## Düzen

- **Ortam:** hafif RL ortamı (`src/eland_rl`), v4 doğrulama seti: 175 sahne (FloodNet 60, MESSI 115) × 4 başlangıç
  = **700 iniş/hücre**. 20–30 m başlangıç, 30 s sınır, nominal dinamik, gimbal kamera. Her deneme yeni bir ortamla.
- **Başarı** her zaman gerçek etiketle ölçülür (zemin kuralı: güvenli zemin, insan/araçtan 2 m uzak). Dron ise seçilen
  segmentasyonun maskesini görür; eski kalkan ve kilitli kalkan da o maskeyle çalışır.
- **Ajanlar** (hepsi c13 tarifi: `zemin_v3`, eğitimde 30 s, kayarken alçal, eğitimde eski kalkan 10 m, 1M adım):
  - Eski veri + irtifa: c13 s0–s2, 600 MESSI karesi, düz zemin derinliği (pratikte irtifa).
  - Eski veri + Depth Anything: Düzeltme 27 C_da s0–s2, 133 fotoğraflı MESSI karesi.
  - Yeni veri + irtifa: v4_flat s0–s4, v4 dengeli set (730 sahne: MESSI 365 + FloodNet 365).
  - Yeni veri + Depth Anything: v4_da s0–s4, aynı set.
- **Segmentasyon:** gerçek etiket; v3 (`best_v3.pth`); v4 (`best_v4.pth`). Maskeler fotoğraftan, sahadaki kamerayı
  taklit için 9 cm/piksele indirilerek üretildi (`tools/rl_inis/v4/seg_maske.py`). Piksel uyumu v3 %86.0, v4 %91.7;
  tehlikeliyi güvenli sanma v3 %12.0, v4 %4.8.
- **Kalkan:** yok · eski (son 10 m alçalmayı güvensiz yerde durdurur) · kilitli (eski + güvenli noktaya kilitlenme).

## Başarılı iniş (%)

| Ajan | Segmentasyon | Kalkan yok | Eski kalkan | Kilitli kalkan |
|---|---|---|---|---|
| Eski veri + irtifa (c13) | gerçek etiket | 68.1 | 85.8 | 94.0 |
|  | v3 | 65.1 | 78.0 | 85.0 |
|  | v4 | 65.9 | 79.7 | 86.7 |
| Eski veri + Depth Anything | gerçek etiket | 46.9 | 78.0 | 91.4 |
|  | v3 | 44.6 | 70.7 | 82.1 |
|  | v4 | 45.8 | 74.1 | 84.2 |
| Yeni veri + irtifa | gerçek etiket | 68.1 | 84.5 | 90.5 |
|  | v3 | 64.9 | 77.0 | 81.8 |
|  | v4 | 65.8 | 79.1 | 84.1 |
| Yeni veri + Depth Anything | gerçek etiket | 46.7 | 83.6 | 93.2 |
|  | v3 | 46.8 | 74.1 | 82.7 |
|  | v4 | 46.5 | 77.3 | 86.2 |

## Güvensiz iniş (%)

| Ajan | Segmentasyon | Kalkan yok | Eski kalkan | Kilitli kalkan |
|---|---|---|---|---|
| Eski veri + irtifa (c13) | gerçek etiket | 31.5 | 2.9 | 1.5 |
|  | v3 | 34.9 | 13.0 | 13.6 |
|  | v4 | 34.0 | 8.6 | 8.8 |
| Eski veri + Depth Anything | gerçek etiket | 52.4 | 6.5 | 3.1 |
|  | v3 | 54.2 | 16.5 | 15.1 |
|  | v4 | 53.5 | 12.0 | 10.4 |
| Yeni veri + irtifa | gerçek etiket | 25.1 | 2.9 | 1.5 |
|  | v3 | 31.4 | 13.9 | 13.4 |
|  | v4 | 28.0 | 9.5 | 8.6 |
| Yeni veri + Depth Anything | gerçek etiket | 53.1 | 5.5 | 2.5 |
|  | v3 | 53.2 | 17.3 | 15.9 |
|  | v4 | 53.4 | 11.7 | 9.3 |

## Ortalama iniş süresi (başarılı inişler, s; başlangıçtan 5 m'ye)

| Ajan | Segmentasyon | Kalkan yok | Eski kalkan | Kilitli kalkan |
|---|---|---|---|---|
| Eski veri + irtifa (c13) | gerçek etiket | 10.77 | 12.61 | 12.78 |
|  | v3 | 10.79 | 12.34 | 12.62 |
|  | v4 | 10.82 | 12.33 | 12.7 |
| Eski veri + Depth Anything | gerçek etiket | 11.56 | 14.09 | 14.19 |
|  | v3 | 11.43 | 13.96 | 14.09 |
|  | v4 | 11.61 | 14.06 | 14.16 |
| Yeni veri + irtifa | gerçek etiket | 11.56 | 12.99 | 13.16 |
|  | v3 | 11.68 | 12.91 | 13.04 |
|  | v4 | 11.57 | 12.82 | 13.02 |
| Yeni veri + Depth Anything | gerçek etiket | 10.58 | 13.46 | 13.52 |
|  | v3 | 10.62 | 13.28 | 13.31 |
|  | v4 | 10.61 | 13.21 | 13.45 |

## En iyi tohumların süresi (kilitli kalkan)

| Ajan | Gerçek etiket: başarı / ort. / medyan | v4: başarı / ort. / medyan | FloodNet / MESSI (v4) |
|---|---|---|---|
| Eski veri + irtifa (c13) | %95.4 / 12.6 s / 12.5 s | %88.9 / 12.1 s / 12.0 s | 11.3 / 12.4 s |
| Eski veri + Depth Anything | %93.1 / 14.3 s / 13.8 s | %84.7 / 13.4 s / 12.5 s | 12.8 / 13.7 s |
| Yeni veri + irtifa | %94.6 / 12.3 s / 12.0 s | %86.4 / 12.4 s / 12.0 s | 11.4 / 12.9 s |
| Yeni veri + Depth Anything | %95.6 / 13.4 s / 12.5 s | %88.4 / 13.3 s / 12.5 s | 12.3 / 13.8 s |

En hızlı %10'luk inişler ~8.2 s. 25 m'den 5 m'ye 2 m/s ile düz iniş ~10 s sürer (_hesap); makale 11.8 s.

## Kararlar ve okuma

- **H29a tutmadı:** c13 + kilitli kalkanla v4 %86.7, v3 %85.0 (+1.7 < 3). Bütün gruplarda v4 − v3 = +1.7 … +3.5 puan.
- **H29b:** kilitli ≥ eski ≥ yok sırası 12 hücrenin 12'sinde tuttu.
- **H29c:** v4 + kilitli kalkanla en iyi grup eski veri + irtifa (c13), %86.7.
- **Kalkan en büyük etken.** Kalkansız başarı %45–68, güvensiz %25–54. Depth Anything'li ajanlar kalkansızken
  %53 güvensiz: kalkana yaslanıyorlar, kalkansız kullanılmamalı.
- **v4 segmentasyonu güvenliği artırıyor:** kilitli kalkanla güvensiz iniş v3'te %13–16, v4'te %8.6–10.4.
- **Veri ve derinlik:** v4 + kilitli kalkanla dört grup %84–87; fark tohum gürültüsü düzeyinde. Depth Anything
  eğitimi kararlı yapıyor (Düzeltme 27–28), ama ortalamayı yükseltmiyor; ~1 s da yavaşlatıyor.
- **Darboğaz algı:** gerçek etiketle v4 arasında 6–9 puan fark.

## Sınırlar

- Hafif ortam; AirSim ölçümü ayrı adım (c13 + v4, Faz 7'nin 30 başlangıcı).
- v4 segmentasyonu bu kaynakların eğitim bölümlerini gördü; v3 FloodNet'i görmedi.
- Eski c13 bazı Agamim doğrulama uçuşlarını eğitimde görmüş olabilir.
