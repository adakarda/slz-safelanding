# Aşama 0 — MESSI veri paketi keşfi (2026-10-17)

Kaynak: `messi_rl-20261016T203334Z-1-001.zip` (1774.8 MB, İndirilenler).
Bu aşamada yalnız okuma ve ölçme yapıldı. Zip açılmadan okundu.
Daha önce açılmış kopya (`~/eland_veri/rl/messi_rl/`) zip ile karşılaştırıldı: 1608 dosyanın 1608'i aynı boyut ve aynı CRC32. Yani orijinale yazılmamış (ölçülen).
Betikler: `~/rl_inis/veri_hatti/asama0/` (`kesif_zip.py`, `kesif2.py`, `kesif3.py`, `crc_karsilastir.py`).

## 1. Sorun ve hipotez

RL ortamı fotoğrafı ve maskeyi bir "dünya" olarak kullanır. Bu aşamada sorulan sorular:
- Paket içinde ne var?
- Kullanıcının varsayımları doğru mu?
- Hangi bölme (split) sızıntısız olur?

## 2. Yöntem

- Zip listesi: klasör, uzantı, boyut.
- `manifest.csv` ve `README.md` tam okundu.
- 1433 maskenin başlığı (mod, boyut) okundu. Görüntüyle boyut eşleşmesine bakıldı.
- 38 karede (her uçuştan ilk ve son kare) tam piksel kontrolü yapıldı:
  - ham sınıf değerleri,
  - README tablosuyla `raw16 → sora7` dönüşümü,
  - manifest'teki sınıf paylarıyla karşılaştırma.
- 173 JPG'de EXIF ve XMP okundu: odak, 35 mm eşdeğeri, `RelativeAltitude`.
- GPS: uçuş başına merkez ve yayılım, uçuşlar arası mesafe, sahne kümeleri.

## 3. Sonuç

### 3.1 Paket içeriği (ölçülen)

| Parça | Sayı | Not |
|---|---|---|
| `manifest.csv` | 716 satır, 716 benzersiz id | 31 sütun (aşağıda) |
| `masks_raw16/` | 716 PNG | MESSI'nin kendi sınıfları 0–15 |
| `masks_sora7/` | 717 PNG | 716 + 1 kopya (`100_0042/HYPERLAPSE_0087(1).png`, asıl dosyayla bayt bayt aynı, manifest'te yok; zararsız) |
| `images/` | **173 JPG** | **716'nın 543'ü eksik.** Sadece Agamim Descend 0001, 0002 (3/45), 0003, 0004, 0006 var. Zip adı "-1-001": büyük ihtimalle ikinci parça var. |
| `README.md` | 1 | SORA tablosu, sütun açıklamaları |
| Derinlik | **yok** | Pakette derinlik dosyası yok. |

Bütün kareler: 5472×3648, kamera L1D-20c, gimbal eğimi −89.7…−90° (dik aşağı). Boyut uyuşmayan kare: 0.

### 3.2 Varsayımların kontrolü

| Varsayım | Ölçüm | Sonuç |
|---|---|---|
| 5472×3648, DJI, dikey çekim | 716/716 5472×3648, L1D-20c, eğim −89.7…−90° | Doğru |
| Maskeler palet indeksli PNG | 1433/1433 **mod L** (gri, tek kanal); piksel = sınıf numarası | Palet değil, ama kullanım aynı |
| Sınıf numaraları 0–14 | raw16'da **0–15** (16 değer, 0 = etiketsiz) | Kısmen; bu pakette 16 değer |
| 7 SORA sınıfı, tablo veride | Tablo `README.md`'de; `masks_sora7` hazır (0–6, 7 = bilinmeyen) | Doğru |
| raw16 → sora7 dönüşümü tutarlı | 38 karede README tablosuyla **0 uyuşmayan piksel** | Doğru; kodumuzdaki `MESSI_TO_TAXONOMY` ile birebir aynı |
| Derinlik yok | Yok | Doğru |
| EXIF'te yükseklik ve odak var | 173 JPG'de var; XMP `RelativeAltitude` − manifest `rel_alt_m` = 0.00 m | Doğru |
| 5 fotoğraftan 4'ü 50 m, 1'i 100 m | Bu pakette **bütün kareler 80.0–120.5 m** (paket `rel_alt ≥ 80` ile süzülmüş) | Bu paket için geçerli değil; 5 örnek başka bir setten olabilir |
| Sensör genişliği 13.2 mm | EXIF: odak 10.26 mm, 35 mm eşdeğeri 28 mm → 36 × 10.26 / 28 = **13.19 mm** | Doğru |

### 3.3 Yükseklik ve GSD

| Büyüklük | Değer (ölçülen, manifest) |
|---|---|
| Göreli irtifa | 80.0–120.5 m, ortanca 99.9 m |
| GSD | 1.88–2.83 cm/px, ortanca 2.35 cm/px |
| Odak | 10.26 mm (hepsi) |

Yere düşen alan (_hesap, GSD × piksel):

| İrtifa | Alan |
|---|---|
| 80 m | 103 × 69 m |
| 100 m | 129 × 86 m |
| 120.5 m | 155 × 103 m |

İrtifa histogramı (80–85, …, 115–121 m): 86, 88, 86, 119, 120, 91, 77, 49 kare.

### 3.4 Sınıf dağılımı

SORA 7 sınıfı, 716 kare (manifest `p_*`, 1/8 örneklem). Tam piksel sayımıyla fark en çok 0.0011 (38 karede ölçülen).

| Sınıf | Piksel payı (ort.) | İçeren kare |
|---|---|---|
| 0 safe-soft | %16.93 | 716 |
| 1 safe-hard | %15.12 | 716 |
| 2 terrain-hazard (asfalt, ağaç) | %40.22 | 716 |
| 3 structure | %25.75 | 716 |
| 4 water | %0.02 | 265 |
| 5 vehicle-animal | %1.94 | 712 |
| 6 person | %0.01 | 628 |
| 7 unknown | %0.01 | 481 |

- İnsan piksellerin sadece %0.01'i. Ama 716 karenin 628'inde var. Yani küçük ama sık. Aşama 1'deki "sınıf hayatta kalma" ölçümü bu yüzden önemli.
- Test kareleri (IrYamim, 20) daha güvenli: safe-soft + safe-hard %56.8. Eğitimde bu oran %31.3.

### 3.5 Mevcut ayrımlar

| Sütun | Değerler |
|---|---|
| `etiket` | trainval 696 (Agamim: Descend 652, Path 44), test 20 (IrYamim Path) |
| `v3_kullanim` | v3 segmentasyonu için: train 200, val 61, test 20, kullanılmadı 435 |

- README "Ha-Medinah Square"ı da görülmemiş bölge olarak anıyor. Ama manifest'te Ha-Medinah satırı yok (büyük ihtimalle 80 m süzgeci yüzünden).
- v3 modeli, Agamim'in her uçuşundan kare gördü (train veya val). Yani v3'ün Agamim tahminleri iyimser. Bu, 0004 uçuşu için de geçerli: 13 karesi v3 eğitimindeydi.

### 3.6 GPS ve sahne kümeleri

- Her Descend uçuşu tek bir noktada asılı kalıp 120 m'den 80 m'ye iniyor. Uçuş içi yatay yayılım en çok 1.9 m (ölçülen).
- Bu yüzden bir Descend uçuşu = tek sahne, farklı yüksekliklerden.
- Uçuş merkezleri arası en yakın mesafe 1.2–58 m. Bir kare yerde ~129 m genişlik görüyor. Bu yüzden komşu uçuşlar büyük ölçüde aynı yeri çekmiş.

Kümeler, merkez mesafesi < eşik (ölçülen):

| Eşik | Küme sayısı | Kümeler |
|---|---|---|
| 60 m | 8 | {0001, 0002, 0031, 0035, 0036}, {0003}, {0004, 0043, Path B}, {0005, 0006}, {0037, 0038, 0042}, {0040, 0041, Path A}, {Path C}, {IrYamim} |
| 86 m | 6 | 0004 kümesi 0037–0043 ve Path A/B ile birleşir |
| 129 m | 3 | Agamim iki büyük küme + IrYamim |

Not: Path uçuşları 200–330 m'lik bir rota. Merkezleri temsil edici değil; kare bazında iz örtüşmesi daha doğru olur (Aşama 2).

**Sızıntı açısından bugünkü deneyler:**
- **A1, A2b** (eğitim: bütün Agamim, test: IrYamim):
  - IrYamim 1.15 km uzakta. Sızıntı yok.
  - Ama test seti tek rotadan 20 kare ve kareler birbiriyle örtüşüyor. Bu yüzden test küçük ve sonuçların belirsizliği büyük.
- **Depth Anything deneyi** (eğitim: 0001/0002/0003/0006, test: 0004):
  - Merkez mesafeleri ≥ 193 m. 120 m'deki en kötü durumda izlerin örtüşme sınırı ~185 m (_hesap). Sızıntı yok, ama pay az.
  - **v3, 0004'ün 13 karesiyle eğitildi.** Bu yüzden PA–PD kollarının test sonuçları iyimser. Kollar birbirleriyle karşılaştırılabilir. Ama "tahmin maskesi ile gerçek maske arasındaki fark" olduğundan küçük görünür.

## 4. Karar

- Veri paketi tutarlı:
  - maske–manifest eşleşmesi tam,
  - SORA dönüşümü doğrulandı,
  - boyutlar eşit,
  - EXIF ile manifest aynı.
- Derinlik yok. Paketten derinlik üretilmeyecek.
- Bölme sahne kümesine göre yapılmalı, uçuşa göre değil (Aşama 2). Gerçekten görülmemiş tek bölge IrYamim.
- Bu aşamada hiçbir türetilmiş veri yazılmadı. Tek çıktı bu rapor ve okuma betikleri.

## 5. Riskler ve bilinmeyenler

- 543 görüntü eksik. RL maskeyle çalışır, ama RGB şu işler için gerekli:
  - v3 tahmin maskeleri,
  - görsel kontrol.
  Bu işler şimdilik 173 kareyle sınırlı.
- Agamim içinde bağımsız doğrulama sahnesi az. 60 m eşiğinde 7 küme var, ama kümeler arası mesafeler iz boyuna yakın.
- IrYamim testi tek rota, 20 kare. Sonuçlar için güven aralığı geniş olacak.
- Bu pakette yükseklik en az 80 m. İnişin 5–30 m arasındaki görüntüleri, 80–120 m fotoğrafın sanal kamerayla yakından örneklenmesiyle elde ediliyor. Bu yöntem bina yüksekliği ve paralaks içermez (düz dünya varsayımı).

## 6. Açık sorular

1. Zip'in ikinci parçası (eksik 543 görüntü) var mı?
2. Bugün koşan kuyruk (A1, A2b, Depth Anything kolları) tek tohumlu ve ön kayıtlı. Yeni kural "en az 3 tohum" istiyor.
   - Önerim: kuyruk bitsin. Sonuçlar "ön sonuç, tek tohum" diye raporlansın. Yeni kural bundan sonraki deneylere uygulansın.
3. Depth Anything bir tahmin (göreli yükseklik). Yeni kural "derinlik uydurma; tahmin kullanacaksan önce sor" diyor. Daha önce açıkça istediğin için deneyi "tahmin" etiketiyle koşuyorum. Devam mı, dursun mu?
4. Bölme önerisi (Aşama 2'de kesinleşir):
   - test: IrYamim,
   - doğrulama: Agamim'den bir küme, örneğin {0004, 0043, Path B},
   - eğitim: kalan Agamim.
   Uygun mu?
