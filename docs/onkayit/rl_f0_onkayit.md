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

## Düzeltme 1 (2026-10-16, F1 ölçümlerinden sonra, hiçbir eğitimden önce)

Sonuç görülmeden yazıldı. Hiçbir politika eğitilmedi.

1. **Kamera formülü yanlıştı.** Yereldeki MESSI fotoları DJI FC6310R ile değil, Hasselblad L1D-20c ile çekilmiş: f = 10.26 mm, EXIF'ten ölçülen.
   - Kural: GSD her fotonun kendi EXIF odak uzaklığı ve XMP RelativeAltitude değeri ile hesaplanır. GSD = H × 13.2 mm / (f × W). Kod: `eland_rl.scene.dji_ground_size`.
   - Düzeltilmiş iz: 1.287 H × 0.858 H (_hesap). 80 m'de 103 × 69 m, 100 m'de 129 × 86 m.
   - §2.1'deki "80 m → 120 × 80 m" yanlış. Eşik kuralı değişmez: metadata görüldükten sonra, eğitimden önce kesinleşir.
2. **Dinamik modele saf komut gecikmesi ve sabit trim eğimi eklendi.**
   - Tanılama uçuşu `~/rl_inis/tanilama/kos1`: x500_seg_cam_rgb_down, offboard hız setpoint'i. Önce basamaklar, sonra politika benzeri 160 rastgele eylem.
   - Bütün kayda uydurulan değerler (ölçülen):

     | Parametre | Değer |
     |---|---|
     | τ_xy | 0.50 s |
     | a_max | 2.0 m/s² |
     | xy komut gecikmesi | 0.24 s |
     | τ_z | 0.15 s |
     | z komut gecikmesi | 0.10 s |
     | Eğim | 0.91 × atan(a/g) + 0.69° (r 0.977) |
     | Hover trim eğimi | 0.9° |

   - Ortam kodu aynı komutlarla kaydı yeniden oynattı (ölçülen):

     | Bölüm | xy RMSE | z RMSE |
     |---|---|---|
     | Basamaklar | 0.036 m/s | 0.044 m/s |
     | Rastgele | 0.084 m/s | 0.128 m/s |

     Gecikmesiz eski varsayılan rastgele bölümde xy 0.190 m/s verdi.
   - Rastgeleleştirmeye eklenenler: komut gecikmeleri ±%50, trim eğimi rastgele yönde 0–1.5°. Diğer aralıklar §2.4'teki gibi.
3. **Yaw (açıklama).** Bölüm içinde sabittir. Her bölüm başında rastgele çekilir (veri artırma). Gazebo testinde yaw, başlangıç pozundan gelir.
4. **Gözlem örneklemesi (açıklama).** 128 × 128 ışınlar, 320 × 240 etiket görüntüsünde `cv2.resize(INTER_NEAREST)` işleminin seçtiği piksellerdir. Birim testi bunu doğrular.

## Düzeltme 2 (2026-10-16): pilot eğitim, MESSI verisi gelmeden önce

Kullanıcı isteği: politikayı şimdi eğit, komutlarını PX4'te dene. MESSI ham verisi henüz yok. Bu yüzden aşağıdaki pilot koşulur.

- **Amaç:** eğitim hattının ve PX4 entegrasyonunun (F4) sınanması. Pilot sayıları tez sonucu değildir ve Tablo I karşılığına girmez.
- **Sahneler:** yereldeki 5 foto (`~/rl_inis/sahneler_pilot.txt`). §2.1'deki "yalnız birim testi" kuralının bilinçli bir istisnası.
  - Bu 5 foto v3 eğitiminde de kullanıldı. Nihai test setine girmezler.
- **Eğitim:** 500k adım, tohum 0, GT girdi, §4 ayarları (`python -m eland_rl.train`).
- **Değerlendirme:** aynı 5 sahne × 15 başlangıç, 30 s, nominal dinamik (`python -m eland_rl.evaluate`). Eğitim sahnesinde test edildiği için genelleme ölçmez.
- **Pilot beklentisi (_tahmin):** RL başarısı, düz inişten en az 20 puan yüksek.
- **Gazebo (F4):** orto_dji0097 dünyası, eğitim sahnelerinden biri. Ayrıntılar F4 koşusundan önce yazılır.

## Düzeltme 3 (2026-10-16): F4 pilot Gazebo testi, koşudan önce

- **Kurulum:**
  - Pilot politika (`~/rl_inis/kos/pilot_s0/model.zip`).
  - Dünya orto_dji0097, model x500_seg_cam_rgb_down.
  - Yeni `eland_rl_mode` ("RL Landing", hiçbir iç modun yerine geçmez) ve `eland_rl.policy_node`.
- **Girdi:** `label_source=gt`. Kameranın gerçek pozundan (gz dynamic_pose) eğitimdeki izdüşüm. Derinlik düz zemin varsayımıyla aynı pozdan. Amaç yalnız PX4 tarafındaki aktarım farkını görmek; v3 girdisi sonraki adım.
- **Başlangıçlar:** `evaluate.py` sahne 0 (DJI_0097), tohum 0–14. Aynı x, y, yaw ve kalkış irtifası kullanılır (`~/rl_inis/f4/baslangiclar.txt`).
- **Başarı:** ortamla aynı tanım.
  - Mod etkinleştikten sonra 30 s içinde kamera 5 m'ye iner.
  - O andaki tam görüşün çoğunluk sınıfı safe-soft veya safe-hard olur.
  - Bu satır politika günlüğünden okunur.
  - 5 m altında mod dikey olarak iner. SORA mesafesi iniş noktasından ayrıca raporlanır.
- **Tahmin (_tahmin):** Gazebo başarısı, aynı 15 başlangıçta ortamdaki başarıdan en çok 2 koşu (~13 puan) farklı çıkar.
- **Pilot sınırı:** eğitim sahnesinde test. Genelleme değil, aktarım ölçer.

## Düzeltme 4 (2026-10-16): bizim iniş ödülü (`sora_v1`), eğitimden önce

**Karar (kullanıcı):** Paper birebir kopyalanmayacak. Hedef, bize uygun bir iniş ödülü tasarlamak ve onunla eğitmek.

**Gerekçe (pilot ve teşhis):**
- Pilot politika dümdüz inişe çöktü: başarı %21.3, dümdüz inişle aynı.
- Aynı 75 bölümde sabit pilotlarla ödül taraması yapıldı (`~/rl_inis/odul_testi.py`, `odul_varyant.py`, `odul_sora.py`). Ölçülen bulgular:
  - Paper ödülü altında SORA'ya göre arama yapan kâhin, dümdüz inişi yalnız +1.2 puan geçiyor. Paper ödülü SORA-güvenli inişi neredeyse ödüllendirmiyor.
  - "Alçal" ödülünü düşürmek farkı değiştirmiyor (+9.7 → +12.1).
  - Seçilen ödülle fark +24.3. Gezgin −38, bekleyen −114, kaçak −56 puan alıyor; dümdüz iniş +12.8.
  - SORA başarısı: dümdüz %12, kâhin %56.

**`sora_v1` (env.REWARD_PRESETS):**

| Bileşen | Değer |
|---|---|
| Başarı | 5 m'de aracın altındaki nokta landable sınıfta ve structure / water / vehicle / person'dan ≥ 3 m uzakta |
| Bitiş | +50 / −20 |
| Süre doldu | −50 |
| Sahne dışı | −50 (paper −5; kaçış açığını kapatır) |
| Şekillendirme | potansiyel −2 × min(en yakın SORA-güvenli noktaya mesafe, 20 m), γ = 0.99 (Ng vd. 1999). Gerçek durumdan hesaplanır; politika görmez. |
| Adım | zaman −0.2, alçal +0.5, yanal −0.05, dur −0.5 |
| Görüş terimi R_S | ağırlık 0 |

**Eğitim:**
- Ana koşu: `sora_v1`, `ent_coef` 0.01, 1M adım, tohum 0, 5 pilot sahnesi, GT girdi. Çıktı `~/rl_inis/kos/sora_v1_s0`.
- Kontrol koşusu: `paper` ödülü, `ent_coef` 0.01, aynı ayarlar. Çıktı `~/rl_inis/kos/paper_ent_s0`. Amaç, iyileşmenin ödülden mi entropiden mi geldiğini ayırmak.

**Değerlendirme:**
- Aynı 5 sahne × 15 başlangıç, 30 s, nominal dinamik.
- Birincil metrik: SORA başarısı. İkincil: çoğunluk başarısı (paper tanımı).
- Bu hâlâ eğitim sahnesi testidir; genelleme MESSI verisiyle ölçülecek.

**Tahminler (_tahmin):**
- `sora_v1` RL SORA başarısı ≥ %35. Referanslar: dümdüz %12, kâhin %56.
- Kontrol koşusunun (paper + entropi) SORA başarısı ≤ %20.

## Düzeltme 5 (2026-10-16): SORA kanalı (gözlem v2), eğitimden önce

**Düzeltme 4 sonuçları (ölçülen, 75 bölüm, 30 s, argmax):**
- `sora_v1` + entropi: SORA başarısı %9.3, 26 bölümde süre doldu, eylemlerin %55'i yanal. Tahmin (≥ %35) tutmadı.
- Paper + entropi (kontrol): SORA %10.7, çoğunluk %26.7. Tahmin (≤ %20) tuttu.
- `sora_v1` için 90 s sınır ve olasılıkla eylem seçimi en iyi durumda %14.7 veriyor.

**Teşhis (sabit pilotlar, ölçülen):**
- Görüş kâhini: yalnız kameranın gördüğü alanın gerçek SORA bilgisini biliyor. SORA başarısı %82.7. Tüm harita kâhini %56.0, dümdüz iniş %12.0.
  - Sonuç: gereken bilgi görüşte var. Politika onu sınıf görüntüsünden okuyamıyor.
- Kanal pilotu: yalnız araçta hesaplanabilen SORA kanalını kullanıyor.
  - SORA başarısı %28; tutum düzeltmesiyle %32.
  - Güvensiz iniş 0, süre doldu 54.
- Kanalın merkez doğruluğu:

  | İrtifa | Kesinlik | Duyarlılık |
  |---|---|---|
  | 18–30 m | %90 | %58 |
  | 10–18 m | %100 | %86 |
  | 5–10 m | %100 | %99 |

- Eksik olan, kayma ile alçalma arasındaki denge. Bu, öğrenmenin işi.

**Gözlem v2 (`obs_mode=sem_depth_sora`):**
- Üçüncü kanal `camera.sora_channel`.
- Piksel SORA-güvenli sayılır: landable sınıf ve görüntüdeki en yakın hazard pikseline ≥ 3 m.
- Mesafe, 4:3 oranına geri açılmış görüntüde ve nadir piksel boyutu 2·h·tan(HFOV/2)/128 ile ölçülür.
- Yalnız segmentasyon ve irtifadan hesaplanır, araçta da hesaplanabilir.

**Eğitim:**
- `sora_v1`, `ent_coef` 0.01, 1M adım, `obs sem_depth_sora`, 5 pilot sahnesi, GT girdi.
- Tohum 0 ve 1, paralel. Çıktı `~/rl_inis/kos/sora_v2_s{0,1}`.

**Tahmin (_tahmin):** İki tohumun ortalama SORA başarısı ≥ %35. Referanslar: kanal pilotu %28, dümdüz %12, görüş kâhini %83. Değerlendirme Düzeltme 4'teki gibi.
