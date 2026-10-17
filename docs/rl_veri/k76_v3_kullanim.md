# K76 — RGB'si olan 173 karede v3 kullanımı (salt okuma, 2026-10-17)

Kaynaklar:
- `manifest.csv` (`v3_kullanim` sütunu),
- `~/eland_veri/rl/messi_ds4/pred_ozet.csv` (v3'ün kare başına doğruluk ve mIoU'su; yarım çözünürlük, GT sora7 ile).

Betik: `~/rl_inis/veri_hatti/asama0/k76.py`.

## Uçuş × v3 kullanımı (ölçülen)

| Uçuş | train | val | kullanılmadı | test | Toplam |
|---|---|---|---|---|---|
| 100_0001 | 14 | 0 | 29 | 0 | 43 |
| 100_0002 | 0 | 1 | 2 | 0 | 3 |
| 100_0003 | 13 | 0 | 26 | 0 | 39 |
| 100_0004 | 13 | 0 | 27 | 0 | 40 |
| 100_0006 | 16 | 0 | 32 | 0 | 48 |
| **Toplam** | **56** | **1** | **116** | **0** | **173** |

"Kullanılmadı" demek: v3 o kareyi görmedi. Ama aynı uçuşun komşu karelerini gördü, yani aynı yeri gördü (README).

## v3 doğruluğu kategoriye göre (ölçülen)

| Kategori | Kare | Doğruluk | mIoU |
|---|---|---|---|
| train | 56 | 0.946 ± 0.008 | 0.785 ± 0.077 |
| val | 1 | 0.950 | 0.864 |
| kullanılmadı | 116 | 0.946 ± 0.008 | 0.788 ± 0.073 |

"Kullanılmadı" karelerdeki doğruluk, eğitim kareleriyle aynı. Bu, komşu karelerin neredeyse aynı yeri gösterdiğini doğrular: v3 bu kareleri de "biliyor".

## Değerlendirme listelerinin bileşimi

| Liste | Kare | train | val | kullanılmadı |
|---|---|---|---|---|
| `train_foto.txt` (Depth Anything deneyi, eğitim) | 133 | 43 | 1 | 89 |
| `test_foto.txt` (Depth Anything deneyi, test = 0004) | 40 | 13 | 0 | 27 |

## Cevap: hangi kareler iyimser değil?

- **173 karenin hiçbiri iyimserlikten arınmış değil.** Hepsi v3'ün eğitimde veya doğrulamada gördüğü Agamim uçuşlarından.
- En az iyimser olan tek kare, 0002'deki 1 `val` karesi. Ama 0002, 0001'e (v3 train) 43 m uzakta, izleri örtüşüyor.
- v3'ün hiç görmediği tek bölge IrYamim (`test`, 20 kare). Ama bu karelerin RGB'si bu zip'te yok. Bu yüzden v3'ün gerçek genellemesi bu paketle ölçülemez.
- Sonuç: v3 tahmin maskesiyle yapılan bütün değerlendirmeler (PA ve Depth Anything kolları) "iyimser" etiketiyle raporlanacak.
- PA bitince başarı ayrıca `train` ve `kullanılmadı` karelerine göre ayrılarak raporlanacak.
