# Veri ve modeller — envanter

> **Tarih:** 2026-10-27. Bu depo herkese açık. **Veri setleri ve segmentasyon ağırlıkları burada değil.** Sebepler:
> - Lisans: VDD dağıtılamaz; MESSI CC BY-NC-SA 3.0; v4 paketinin README'si "herkese açık bir yere konmamalı" diyor.
>   Ağırlıklar bu verilerle eğitildi.
> - Boyut: v4 paketi 14 GB, her segmentasyon modeli ~189 MB (GitHub dosya sınırı 100 MB).
>
> Dosyalar Arda'dan özel kanalla alınır. Aşağıdaki SHA256 özetleriyle doğrulanır (`sha256sum -c`).

## Segmentasyon modelleri (Arda'nın tarafı; RL tarafı yalnız çalıştırır)

| Ad | Dosya | Boyut | SHA256 | Mimari | Sınıflar |
|---|---|---|---|---|---|
| v3 | `best_v3.pth` | 189,138,663 B | `3e7b372fd29deefb8983783ab370218ddeca3f66e0c06d795a6264507c15973f` | SegFormer-B3 | 8 (SORA 7 + yol) |
| v4 | `best_v4.pth` | 189,047,514 B | `d17d2771972f2ed7314f4a38385ebfb59d45b9d4aa0ba988ff9066bc2d386621` | SegFormer-B3 | 8 (SORA 7 + yol) |

- Yükleme ve çıkarım: Arda'nın `v3_model.py`'si (`yukle`, `segmentle`; v4 de aynı yükleyiciyle açılıyor). RL için yol
  sınıfı terrain-hazard'a eşlenir.
- Bu makinede: `~/v3_test/model/best_v3.pth`, `~/v4_seg/best_v4.pth`.
- v4: MESSI, TU Graz, FloodNet ve VDD eğitim bölümleriyle eğitildi (22.10.2026).

## Veri

| Ad | Dosya | Boyut | SHA256 | İçerik |
|---|---|---|---|---|
| v4 paketi | `veri_v4.zip` | 14,405,273,244 B | `dd01937513fca203bd9a947dfcc2ae460dd8241524e9d3cfaba90e7a93163364` | 4050 kare: FloodNet 1953, MESSI 1297, TU Graz 400, VDD 400; RGB + 8 sınıf maske + kaynak maske, `manifest.csv`, `split_v4.json`, `siniflar.json` |
| MESSI RL paketi (eski) | `~/eland_veri/rl/messi_rl` | — | — | 716 kare, `masks_sora7`; bu makinede 173'ünün fotoğrafı var |

### Kaynaklar ve lisanslar

- MESSI — Pinkovich vd., 2025, TMLR. CC BY-NC-SA 3.0.
- FloodNet — Rahnemoonfar vd., 2021, IEEE Access, doi:10.1109/ACCESS.2021.3090981. CC BY-SA 4.0.
- VDD — Cai vd., 2023, arXiv:2305.13608. Ticari olmayan; veri ya da değiştirilmiş hâli dağıtılamaz.
- Semantic Drone Dataset — TU Graz, ICG. Koşulları kaynağında.

## RL tarafında türetilenler (bu makinede, depoda değil)

| Ne | Yer | Nasıl üretilir (depodaki betik) |
|---|---|---|
| RL sahne maskeleri (8 cm/px, RL sınıfları) | `~/eland_veri/rl/v4/maske/` | `tools/rl_inis/v4/hazirla.py` |
| Eğitim listeleri | `~/eland_veri/rl/v4/{train,train_denge,val,test}.txt` | `hazirla.py`; dengeli set: `random.Random(0)` ile FloodNet 365 + MESSI 365 |
| Depth Anything yükseklik haritaları | `~/eland_veri/rl/v4/elev/` | `tools/rl_inis/v4/da_v4.py` (Depth Anything V2 Small, Apache-2.0) |
| v3 / v4 tahmin maskeleri (doğrulama) | `~/eland_veri/rl/v4/pred_v3`, `pred_v4` | `tools/rl_inis/v4/seg_maske.py` |
| RL modelleri | `~/rl_inis/kos/v4/v4_da_s*`, `v4_flat_s*`; `~/rl_inis/kos/arama/…c13…` | `tools/rl_inis/v4/tur.py`, `tur29.py` |

Depoda paylaşılan RL modelleri için [`modeller/README.md`](../../modeller/README.md)'ye bakın. RL ağırlıkları yalnız
etiketlerden (sınıf maskesi) öğrenir; veri dağıtımıyla aynı kısıta girip girmediği Arda'nın kararıdır.
