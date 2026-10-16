# RL iniş — F0 ön kayıt

Tarih: 2026-10-16. Durum: kullanıcı onayladı (2026-10-16, "Onay"). Eğitim ve koşulardan önce commit edildi.
Push: tasarım sohbetinin "tamam"ından sonra.

Referans: Bartolomei, Kompis, Teixeira, Chli, "Autonomous Emergency Landing for Multicopters using Deep Reinforcement Learning", IROS 2022.
Yazar deposu (github.com/v4rl-ucy/multirotors_landing) GPLv3 lisanslı. Depo yalnız okundu; kod kopyalanmadı.
Etiketler: ölçülen / _hesap / _tahmin. "paper" = paper metni, "kod" = yazar deposundaki config ve ortam kodu.

## 1. Alınan kararlar

| No | Karar | Seçim | Kim |
|---|---|---|---|
| D1 | Eğitim yeri | Hafif Python ortamı (numpy + Gymnasium + SB3 PPO) | kullanıcı |
| D2 | Sahne | S1: veri setinden düz foto sahneler | kullanıcı |
| D3 | Güvenli sınıflar | SORA tasarımı: safe-soft + safe-hard (`DEFAULT_SAFE_CLASSES`) | kullanıcı |
| D4 | R_S'de güvensiz sınıf ağırlığı | −1 (paper metni). Kod 0 kullanıyor; sapma §7'de. | kullanıcı onayı ("gerisini onayla") |
| D5 | PX4 tarafı | Yeni paket, yeni px4_ros2 modu. Mevcut dosya değişmez. | kullanıcı onayı |
| D6 | İndirmeler | gymnasium 1.4.0 + stable-baselines3 2.9.0, yeni venv `~/rl_inis/venv`. Kuruldu (ölçülen). | kullanıcı onayı |

MuJoCo kullanılmaz. Gerekçe §2.4'te.

## 2. Ortam

### 2.1 Sahneler (S1)
- Kaynak: MESSI ham görüntüleri ve maskeleri (`messi_raw.zip`, `adakarda/uav-landing-data`). **Kullanıcı indirecek** (özel depo).
- Kamera: DJI FC6310R, 13.2 × 8.8 mm sensör, 8.8 mm odak, 5472 × 3648 px.
  - GSD = H × 2.741e-4 m/px. İz = 1.5 H × 1.0 H (_hesap).
  - Kontrol: DJI_0097 için 1.17 cm/px → H = 42.7 m (_hesap).
- Seçim kuralı: kare irtifası H ≥ 80 m. Bu, en az 120 × 80 m sahne verir (_hesap).
  - Eşik, metadata görüldükten sonra ve eğitimden önce kesinleşir. Sonuçlara bakılarak değişmez.
- Sahne düzlemi gerçek boyutta. Sahne dışı pikseller UNKNOWN (7) sınıfı.
- Eğitim/test ayrımı:
  - Test sahnesi sayısı 7 (paper Tablo I karşılığı).
  - Test sahneleri farklı bir MESSI bölgesinden veya farklı bir uçuş yolundan alınır.
  - Ardışık MESSI kareleri örtüşür. Bu yüzden eğitim ve test kareleri örtüşmemeli.
- Geliştirme (F1): yereldeki 5 foto (H ≈ 43 m) yalnız birim testi için kullanılır, eğitim için kullanılmaz.

### 2.2 Kamera ve gözlem
- Gazebo'daki RGB kamera ile aynı: 640 × 480, HFOV 99.7°, gövdeye sabit, aşağı bakar.
  - İz: 2.374 h × 1.78 h (_hesap). 25 m'de 59 × 45 m, 5 m'de 12 × 9 m (_hesap).
- Görüntü: ray–düzlem izdüşümü (`gt_kare()` mantığı).
  - Gazebo render'ı ile NCC 0.80 (ölçülen, 2026-10-15 doku yönü testi).
- Gözlem: 2 kanal, 128 × 128.
  - Semantik: sınıf no / 7. En yakın komşu ile küçültülür, kırpma yok.
  - Derinlik: optik eksen derinliği / 40 m, [0, 1] aralığına kırpılır.
  - Düz zeminde ve eğim yokken derinlik görüntüsü sabittir (= h). Derinlik yalnız irtifa ve eğim taşır.
- Çözünürlük: 25 m'de 46 cm/px, 5 m'de 9.3 cm/px (_hesap).

### 2.3 Eylemler
- 10 ayrık eylem (paper, kod):
  - 0 = dur;
  - 1–8 = yanal, dünya çerçevesinde 45°'lik 8 yön;
  - 9 = alçal.
- Yanal 1 m/s, dikey 2 m/s, adım 0.25 s (kod). Adım başına 0.25 m yanal, 0.5 m dikey (_hesap).
- Yaw sabit.

### 2.4 Dinamik
- Model: basit, fizik motoru yok.
  - Hız tepkisi birinci dereceden: v̇ = (v_cmd − v) / τ. Ayrı τ_xy ve τ_z.
  - |a_xy| ≤ a_max.
  - Eğim = atan(a / g), ivme yönünde. Kamera gövdeyle birlikte eğilir.
  - Algı gecikmesi L: gözlem, t − L anındaki durumdan render edilir.
  - Alt adım 0.05 s.
- Parametreler F1'de Gazebo + PX4'te ölçülür. Ölçüm, kısa bir hız-basamağı uçuşudur (depo dışı betik).
  - Eğitimde rastgeleleştirme: τ ±%50, L 0–0.4 s, a_max ±%30.
- Gerekçe: Eğimin etkisi büyük.
  - 2 m/s² ivmede eğim 11.5°'dir (_hesap; ivme değeri _tahmin).
  - 25 m'de bu eğim görüntü merkezini 5.1 m kaydırır (_hesap). Bu, bir yanal adımın 20 katı.
  - v3 gecikmesi 140–270 ms (ölçülen).
- MuJoCo neden yok:
  - Düz dokulu düzlemin kamera görüntüsü tam bir homografidir. Ray–düzlem hesabı bu görüntüyü tam ve daha hızlı verir.
  - MuJoCo'nun segmentasyon render'ı geom no verir; tek düzlem tek no'dur. Sınıf maskesi yine dokudan okunmalı.
  - MuJoCo'daki quad kendi kontrolcümüzü ister ve bu kontrolcü PX4 değildir. Aktarım farkını PX4'ün ölçülen tepkisi kapatır.
  - WSL'de başsız OpenGL (EGL) ek kurulum riski taşır.
  - MuJoCo, 3D engel ve temas gerektiğinde (S2/S3) yeniden değerlendirilir.

### 2.5 Bölüm
- Başlangıç: irtifa U(20, 30) m (paper). x, y öyle seçilir ki başlangıç görüntüsünün en az %70'i sahne içinde olsun.
- Bitiş:
  - z ≤ 5 m (kod hedef yükseklik). O anda tam görüntünün çoğunluk sınıfı güvenli ise başarı.
  - Süre: eğitimde 90 s (kod), testte 30 s (paper).
  - Merkez sahne dışına çıkarsa bölüm biter, ödül −5 (kod).
  - Erken bitiş ("bir sınıf ≥ %90") KAPALI. Sapma §7'de.

## 3. Ödül (paper denklem 1–6)

R = ω_t R_t + ω_S R_S + ω_C R_C + ω_A R_A + R_T. Ağırlıklar: ω_t 1, ω_S 1, ω_C 0.5, ω_A 1.

| Terim | Değer |
|---|---|
| R_t | −0.2 her adım; bitişte 0 |
| R_S | Σ ω_s · (s sınıfının piksel payı). Güvenli sınıflar (safe-soft, safe-hard) +1, diğerleri ve UNKNOWN −1. |
| R_C | d_min ≥ d* ise 0; r < d_min < d* ise −1/(d_min − r). d* 3 m, r 0.5 m. d_min = derinlik görüntüsünün en küçük değeri. |
| R_A | yanal −0.05, dur −0.5, alçal +1 |
| R_T | güvenli iniş +50, güvensiz −20, çarpma −20, süre doldu −50 |

R_C kodda var ama S1'de hep 0. Düz zeminde d_min ≥ 5 m > d*.

## 4. Eğitim

- Ağ (paper):
  - ortak: Conv 8×8/4, Conv 4×4/2, Conv 3×3/1, FC128;
  - actor: 3 × FC64;
  - critic: 2 × FC32.
- PPO, SB3 varsayılanları. Paper hiperparametre vermiyor.
  - Öğrenme hızı 3e-4'ten 0'a doğrusal azalır.
  - 4 paralel ortam (paper).
- GT girdi ile 500k adım (paper). Tohumlar 0, 1, 2. Paper 1 tohum kullandı; 3 tohum sapmadır, bkz. §7.
- Ablasyon: ikili semantik (güvenli / güvensiz), aynı ödül, 3 tohum.
- F3 ince ayarı:
  - 100k adım, lr 1e-4 (paper).
  - Girdi: v3 çıktısı. Ortam RGB'yi render eder, v3 640 px ve ölçeklemesiz çalışır.
  - Süre: 100k × 65–75 ms ≈ 2 saat (_hesap; ms ölçülen).
- v3 kısıtı: v3 MESSI'nin çoğunu eğitimde gördü (karışık split). F3 gürültüsü gerçekten iyimser olur.
  - Mümkünse v3 val görüntüleri kullanılır. Bunun için v3 eğitim manifesti gerekir.

## 5. Test ve metrikler

- Hafif ortam: 7 test sahnesi × 15 başlangıç. Her yöntem ve tohum için koşulur.
- Gazebo (F5):
  - 7 sahne × 15 başlangıç × 4 yöntem = 420 koşu.
  - Yöntemler: düz iniş, detector (params_v3.yaml, 2026-10-16 hali), RL, RL-ikili.
- Birincil metrik: başarı % (paper tanımı, §2.5).
- İkincil metrikler:
  - Süre, yalnız başarılı koşularda, ort ± std.
  - SORA uyumu: iniş noktasının structure, water, vehicle-animal ve person piksellerine en yakın mesafesi ≥ 3 m mi? GT maskeden hesaplanır, ayrı raporlanır.

## 6. Hipotezler (_tahmin, sonuçtan önce yazıldı)

- H1: Hafif ortamda, GT girdi ile, test sahnelerinde RL başarısı ≥ %80.
- H2: RL başarısı düz inişten en az 30 puan yüksek.
- H3: İkili semantik, tam semantikten düşük. Paper'da 7 sahnenin 7'sinde böyle.
- H4: Gazebo'da (PX4 + v3) başarı, hafif ortama göre en çok 15 puan düşer. Koşul: dinamik tanılama yapılmış olmalı.
- H5: SORA uyumu, paper başarısından düşük çıkar. Çoğunluk kuralı yakındaki insanı ve aracı görmez.

## 7. Paper'dan sapmalar

1. Güvenli sınıflar: paper yalnız terrain kullanır, biz safe-soft + safe-hard kullanırız (D3).
2. R_S güvensiz ağırlığı −1: paper metni ile aynı, kod ile farklı (kod 0).
3. Erken bitiş kapalı: kod açık. Kapalı olmazsa politika, yüksekte "%90 çim" görünce bölüm biter ve sonrasını hiç öğrenmez. Gazebo'da bu durum dağılım dışı kalır.
4. Dinamik: Flightmare yerine ölçülen PX4 tepkisi + rastgeleleştirme.
5. Segmentasyon: paper [18] yerine v3. Derinlik: tamamlama ağı yerine GT veya Gazebo derinliği. S1'de derinlik bilgi taşımaz.
6. 3 tohum: paper 1 tohum.
7. Sahneler: fotogrametri 3D modeller yerine düz MESSI fotoları. Çarpışma kısmı test edilemez.

## 8. Lisans ve kurallar

- Yazar kodu ve ORB-SLAM3 GPLv3 lisanslı. Depoya girmez.
- SB3 MIT, Gymnasium MIT lisanslı.
- Yeni kod yeni paketlerde:
  - `src/eland_rl/`: ortam, eğitim, ROS 2 düğümü;
  - yeni px4_ros2 mod paketi.
- Mevcut dosyalarda değişiklik yok. Gerekirse tam diff ve onay.
- control_station, segmentasyon, kaydedici.py ve PX4 parametreleri değişmez.
- Uzun eğitim ve koşulardan önce keep-awake istenir.

## 9. Kullanıcıdan gereken

1. `messi_raw.zip` dosyası, `adakarda/uav-landing-data` deposundan. Downloads'a veya `~/eland_veri/rl/` altına konulacak.
2. MESSI irtifa metadata'sı (`meta/` veya irtifa CSV), zip içinde değilse.
3. Varsa v3 eğitim manifesti (`manifest.csv`, train/val ayrımı için).
4. (Onaylandı, 2026-10-16.)

## 10. F1 kapsamı (onaydan sonra)

1. Ortam kodu: sahne, kamera, dinamik, ödül.
2. Birim testi: aynı pozda, ortam GT karesi ile Gazebo GT karesi arasında IoU ≥ 0.95. Bu bir hedeftir.
3. PX4 tepki ölçümü: Gazebo'da kısa uçuş. Çıktı: τ_xy, τ_z, a_max ve eğim. ölçülen.
4. Rastgele politika ile ortam hızı ölçümü (adım/s).
