# Aşama 1 planı — çözünürlük stratejisi (onaya sunulur, 2026-10-17)

Bu belge yalnız plandır. Onaydan sonra başlanır.
Ölçümler eğitim kuyruğu bittikten sonra koşar (K73; bellek, bkz. yürütme notu 14:57).

## 1. Soru ve hipotez

- 5472×3648 fotoğrafı doğrudan 128×128'e sıkıştırmak mantıklı mı?
- İrtifaya göre küçülen bir pencere ve çözünürlük piramidi daha mı iyi?
- Hangi alt-örnekleme küçük tehlikeleri (insan, araç, su) korur?

## 2. Bugünkü uygulama (ölçüm değil, kod)

Ortam zaten "pencere" mantığıyla çalışıyor:
- Sanal kamera Gazebo kamerasıyla aynı: HFOV 1.74 rad = 99.7°, 4:3.
- Her adımda, bulunduğu irtifadan yere ışın atar (ışın–düzlem kesişimi). Pencere irtifayla küçülür, yaw ve eğimle döner.
- Kaynak: ÷4 küçültülmüş sora7 maskesi (tehlike öncelikli). 128×128 ışın bu maskeden **en yakın komşu** ile örneklenir.
- Fotoğraf dışı: sınıf 7 (bilinmeyen).
- Başlangıç: 20–30 m. Görüşün en az %70'i foto içinde olmalı.
- Araç fotoğraf dışına çıkarsa bölüm biter, ceza −50.

Kullanıcı hipotezindeki piramit yok. Aşama 1 şunu ölçer: bugünkü yöntem (÷4 + en yakın komşu) küçük sınıfları kaybediyor mu, piramit ve başka bir küçültme daha iyi mi?

Pencere boyutları (_hesap, foto 100 m, GSD 2.35 cm/px):

| İrtifa | Pencere (m) | Tam çözünürlükte (px) | 128 gözlemde | Piramit seviyesi L = ⌊log₂(px/128)⌋ |
|---|---|---|---|---|
| 5 m | 11.9 × 8.9 | 504 | 9.3 cm/px | 1 (252 px) |
| 10 m | 23.7 × 17.8 | 1009 | 18.5 cm/px | 2 (252 px) |
| 20 m | 47.4 × 35.6 | 2018 | 37.0 cm/px | 3 (252 px) |
| 30 m | 71.1 × 53.3 | 3026 | 55.6 cm/px | 4 (189 px) |

Bir insan ~0.5 m genişliğinde. 30 m'de bu ~1 piksel eder (_hesap). "≥3–4 piksel" ölçütü 10 m'nin üstünde hiçbir yöntemle sağlanamayabilir. Bunu (g) ölçecek.

## 3. Örneklem

- 30 kare, eğitim kümelerinden (60 m eşiği), her kümeden 5 kare:
  - {0001, 0002, 0031, 0035, 0036}
  - {0003}
  - {0005, 0006}
  - {0037, 0038, 0042}
  - {0040, 0041, Path A}
  - {Path C}
- **IrYamim kullanılmaz** (K75: yalnız final test). Doğrulama kümesi {0004, 0043, Path B} de kullanılmaz. Böylece tasarım kararları doğrulamaya sızmaz.
- Kaynak: `~/eland_veri/rl/messi_rl/masks_sora7` (tam çözünürlük, salt okuma).
- Pencere: her kare × her irtifa için 20 rastgele merkez, pencere tamamen foto içinde. Tohumlar sabit.
- Pencereler eksenle hizalı (yaw 0). Dönüş ayrı bir etki, burada ölçülmez.

## 4. Ölçümler

| Kod | Ne | Nasıl | Çıktı |
|---|---|---|---|
| a, g | Sınıf hayatta kalma | 5, 10, 20, 30 m pencere → 128×128. Üç küçültme: en yakın komşu, çoğunluk oyu, tehlike öncelikli. Person, vehicle-animal ve water için: tam çözünürlükteki bağlı bileşenlerin kaçı 128'de ≥1 px ve ≥3 px kalıyor; piksel ve kare sayıları. | sınıf × irtifa × yöntem tablosu |
| b | Bilgi kaybı | 128 sürümü tam çözünürlüğe en yakın komşuyla geri büyütülür. Pencere içinde mIoU ve sınıf başına IoU. | yöntem × irtifa tablosu |
| c | Karar kalitesi | Her iki çözünürlükte mesafe dönüşümüyle en iyi iniş noktası (SORA: inilebilir + 3 m tampon). İki nokta arası mesafe (m). 128'in seçtiği nokta tam çözünürlükte gerçekten SORA-güvenli mi? | "gerçekten güvenli" oranı, ortalama ± std |
| d | Maliyet | Gözlem başına ms ve sahne başına bellek. Üç seçenek: bugünkü (÷4 + ışın), piramit + seviye seçimi, piramitsiz tam çözünürlük. | ms, MB |
| e | Gözlem boyutu | 64, 96, 128, 192 px, aynı yer alanı. a, b, c ölçütleriyle. | boyut × irtifa tablosu |
| f | Rastgele ölçek | ±%10–20 GSD sapması ve piramit seviyesi sapması. Faydası yalnız RL ile ölçülür. Bu aşamada sadece config anahtarı yazılır; RL testi (3 tohum) ayrıca onaya gelir. | anahtar + test |
| h | Foto kenarı | Pencere boyutu config'ten gelir (HFOV, en-boy oranı). Her foto irtifası ve başlangıç irtifası için, pencerenin tamamen foto içinde kaldığı başlangıç alanı yüzdesi. Foto dışına taşma için seçenekler sunulur, karar verilmez. | tablo + seçenek listesi |

(h) için ön hesap (_hesap, eksenle hizalı, yaw 0):

| Foto irtifası | 10 m | 20 m | 30 m | 40 m |
|---|---|---|---|---|
| 80 m (103 × 69 m) | %57.0 | %26.0 | %6.9 | %0 |
| 100 m (129 × 86 m) | %64.6 | %36.9 | %16.9 | %4.5 |
| 120.5 m (155 × 103 m) | %70.1 | %45.5 | %26.2 | %12.1 |

Foto dışına taşma seçenekleri (karar sende):
1. Bugünkü: dışarısı "bilinmeyen" sınıf. Bölüm, araç fotoğraftan çıkınca biter.
2. Katı: pencere fotoğraftan taşınca bölüm biter. Geçerli başlangıç alanı küçülür (tablo).
3. Yumuşak: taşan pay kadar adım başı ceza.

## 5. "Safe" şemaları (K78)

Tek bir YAML dosyası (`config/siniflar.yaml`) kullanılacak. RL ajanı, klasik yöntem ve değerlendirme aynı dosyadan okuyacak.

| sora7 sınıfı | A: 7 sınıf | B: 3 grup (öneri) | C: ikili |
|---|---|---|---|
| 0 safe-soft | safe | yumuşak zemin, safe | safe |
| 1 safe-hard | safe | sert zemin, safe | safe |
| 2 terrain-hazard | değil | tehlikeli | değil |
| 3 structure | değil, 3 m tampon | tehlikeli | değil |
| 4 water | değil, 3 m tampon | tehlikeli | değil |
| 5 vehicle-animal | değil, 3 m tampon | tehlikeli | değil |
| 6 person | değil, 3 m tampon | tehlikeli | değil |
| 7 bilinmeyen | değil | tehlikeli (temkinli) — **sana soru** | değil |

- 3 m tampon ve tampon sınıfları bugünkü `sora_v1` kuralıyla aynı.
- GT maskeleri sora7. v3 tahmin maskeleri ayrı etiketle tutulur ("v3_tahmin, iyimser").

## 6. Karar kuralları (ölçümden önce yazıldı)

- **Küçültme yöntemi:** (c)'deki "gerçekten güvenli" oranı en yüksek olan seçilir. Fark < 2 puansa (b)'de güvenli sınıf IoU'su daha yüksek olan seçilir.
  - Tehlike öncelikli yöntemin güvenli alanı daraltma bedeli (c) ve (b) ile görünür.
- **Piramit:** (a–c) sonuçları bugünkü yöntemle eşit veya daha iyiyse ve (d) maliyeti ≤ 1.5 katsa uygulanır. Değilse bugünkü yöntem kalır ve gerekçesi yazılır.
- **Gözlem boyutu:** 128 kalır. 192, (c)'de ≥ 3 puan iyileştirirse 3 tohumlu kısa RL testi önerilir.
- **Rastgele ölçek:** Bu aşamada karar yok, sadece anahtar.

## 7. Kod ve testler

- `src/eland_rl/eland_rl/pencere.py`: pencere boyutu, piramit seviyesi, üç küçültme yöntemi.
- `config/siniflar.yaml` ve `config/asama1.yaml`: şemalar, örneklem, tohumlar, irtifalar.
- Testler (`test/test_pencere.py`):
  - seviye formülü,
  - pencere geometrisi,
  - küçültmede sınıf kümesinin orijinalin alt kümesi kalması (assert),
  - tehlike önceliğinin doğru sınıfı seçmesi.
- Ölçüm betikleri `tools/asama1_*.py`. Çıktılar repo dışında: `~/eland_veri/rl/turetilmis/asama1/`.
- Sürümler (numpy, opencv, python) ve tohumlar her çıktının yanına yazılır.

## 8. S26 — süre ve disk (_tahmin)

- Kod, testler ve rapor: 1–1.5 çalışma günü.
- Hesap:
  - 30 kare × 4 irtifa × 20 pencere = 2400 pencere; her pencere için 3 yöntem × 4 boyut.
  - Süre ~15–30 dakika (tek çekirdek). Bellek < 1 GB.
- Disk:
  - Aşama 1 çıktıları (CSV, şekiller, 30 karelik örnek piramit) < 100 MB.
  - Bütün veri için piramit (Aşama 6) ~0.3 GB PNG (_hesap: sora7 PNG kare başına ~0.21 MB × 1.33).
- RL'ye bağlı kısım (f, ve gerekirse e): her kol 3 tohum. Kısa koşu (300k adım) ~30 dk (_hesap, ~170 adım/s). Ayrıca onaya gelir.

## 9. S25 için veri (karar Arda'nın)

- Bugünkü başlangıç 20–30 m. Bu değer ön kayıt F0'dan geliyor (makaledeki aralık).
- "Foto irtifasının %60–80'i" kuralı, sanal kameranın görüş açısı fotoğraf kamerasınınkiyle aynıysa anlamlı. Fotoğraf kamerasının yatay görüş açısı 65.5°; o zaman pencere fotoğrafın %60–80'ini kaplar.
- Bizim sanal kameramız Gazebo kamerası, görüş açısı 99.7°. Aynı kural pencereyi fotoğraftan büyük yapar: %60'ta 1.11 kat, %80'de 1.47 kat (_hesap). Yani bizim kamerayla uygulanamaz.
- Bizim kamerayla pencerenin fotoğrafın %60–80'ini kaplaması için başlangıç irtifası, foto irtifasının ~%33–43'ü olmalı (100 m'lik fotoda 33–43 m). Bugünkü 20–30 m, pencerenin fotoğrafın %37–55'ini kaplaması demek.

## 10. K79 notu

- "Baseline makaleye birebir yeniden üretilmeden" şartı için bir not: makale gerçek derinlik kullanıyor (sentetik ortam). MESSI'de derinlik yok (Aşama 0).
- Bu yüzden birebir üretim bu veriyle mümkün değil. Mümkün olan en yakın şey:
  - makale ödülü (`paper` preset),
  - makale ağı,
  - düz zemin derinliği (fotoğraf düzlemi).
- Hangisinin "baseline" sayılacağına karar verilmesi gerekiyor.
- Daha önceki karar ("makaleyi birebir kurgulamak amacımız değil") ile birlikte değerlendirilmeli.
