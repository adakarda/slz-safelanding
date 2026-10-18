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

## Düzeltme 6 (2026-10-17): MESSI ana eğitimi, eğitimden önce

**Karar (kullanıcı):** MESSI ile düzgün bir eğitim yapılacak, performans ölçülecek. Sonuç iyi değilse düzeltilip yeniden eğitilecek. Depth Anything yalnız ölçülen bir fayda getirirse eklenecek.

**Veri:**
- `messi_rl` paketi (kullanıcının arkadaşından): 716 kare, 80–120 m, GSD 1.88–2.83 cm/px.
- Eğitim: 696 Agamim karesi (`etiket=trainval`).
- Test: 20 IrYamim karesi (`etiket=test`). v3 bu bölgeyi görmedi.
  - `test7`: bu 20 karenin her 3. karesi. "Path" uçuşundaki ardışık kareler örtüşüyor; seyrekleştirmenin amacı bu.
- Maskeler SORA-7. Küçültme 4 kat, tehlike öncelikli: bir blokta person > vehicle > water > structure > terrain-hazard > unknown > safe-hard > safe-soft sırasıyla en tehlikeli sınıf kalır. Sonuç 7.5–11 cm/px.
  - Bellek için SORA ızgarası 0.25 m. Değerlendirme de aynı ızgarayla yapılır.
- Sahneler 4 ortama paylaştırılır (`--shard`).

**Eğitim (A1):**
- `sora_v1`, `obs sem_depth_sora`, `ent_coef` 0.01, 2M adım, tohum 0.
- Çıktı `~/rl_inis/kos/messi_a1_s0`.
- Bellek nedeniyle koşular tek tek yapılır.

**Değerlendirme:**
- `test` (20 × 15 = 300 bölüm), `test7` (105 bölüm) ve eğitimden 20 sahnelik bir örnek (aşırı öğrenme kontrolü).
- 30 s sınır, nominal dinamik, argmax.
- Yöntemler: RL, RL + kalkan (< 10 m), dümdüz iniş, kanal pilotu, görüş kâhini (üst sınır).
- Birincil metrik SORA başarısı. Güvensiz iniş ve süre doldu ayrı raporlanır.

**Tahminler (_tahmin):**
- H6a: `test` üzerinde RL SORA başarısı ≥ 2 × dümdüz iniş.
- H6b: RL + kalkan güvensiz iniş ≤ bölümlerin %2'si.
- H6c: Eğitim örneği ile `test` arasındaki RL SORA başarısı farkı ≤ 10 puan.

**Sonraki düzeltmeler** (her biri koşudan önce ayrı bir düzeltme olarak yazılır):
- kalkanın eğitime katılması,
- "tırman" eylemi,
- daha uzun eğitim,
- Depth Anything ile yükseklik bilgili derinlik kanalı.

## Düzeltme 7 (2026-10-17): Depth Anything deneyi, eğitimden önce

**Soru:** Depth Anything V2 Small (Apache-2.0) yükseklik bilgisi, segmentasyon gürültülüyken RL'nin SORA başarısını artırıyor mu? Kullanıcı kuralı: yalnız ölçülen bir fayda varsa eklenir.

**Ön ölçüm (eğitimden bağımsız, ölçülen):** 24 MESSI fotosunda göreli derinliğin AUC değeri:
- bina / zemin: medyan 0.975 (en kötü 0.886);
- ağaç / çim: medyan 0.82 (en kötü 0.58).

**Veri:**
- Fotosu olan 173 Agamim karesi.
- Eğitim: 0001, 0002, 0003 ve 0006 uçuşları (133 kare). Test: 0004 uçuşunun tamamı (40 kare).
- v3 tahmini (`pred`): v3 bu karelerin çoğunu eğitimde gördü; gürültü bu yüzden iyimser.
- Yükseklik haritası (`elev`): Depth Anything çıktısı, her karede %5–%99.5 yüzdelikleri arasında 0–1'e ölçeklenir.
- Eşik τ = 0.12. Yalnız eğitim uçuşlarından, Youden J ile seçildi (`esik_sec.py`): yükseltilmişi yakalama %75.2, zemini yanlış işaretleme %12.1.

**Kollar.** Hepsi `sora_v1`, `ent_coef` 0.01, 1M adım, tohum 0. Ödül ve başarı her kolda GT'dendir.

| Kol | Sınıflar | Kanal 2 | SORA kanalı |
|---|---|---|---|
| P0 | GT | düz derinlik | GT |
| PA | v3 | düz derinlik | v3 |
| PB | v3 | Depth Anything yüksekliği | v3 |
| PC | v3 | düz derinlik | v3 ve yükseklik ≤ τ |
| PD | v3 | Depth Anything yüksekliği | v3 ve yükseklik ≤ τ |

**Değerlendirme:**
- Test uçuşu: 40 kare × 15 başlangıç, 30 s, argmax.
- Yöntemler: RL, RL + kalkan, kanal pilotu (kolun kendi SORA kanalıyla), dümdüz iniş, görüş kâhini.
- Birincil metrik SORA başarısı, ikincil güvensiz iniş oranı.

**Karar kuralı (önceden):** Depth Anything ancak şu koşulla eklenir: PB, PC ya da PD, PA'ya göre RL veya RL + kalkan için
- SORA başarısını en az 3 puan artırmalı, ya da
- güvensiz inişi en az %25 (göreli) azaltmalı,
- ve bunu yaparken öteki metriği 3 puandan fazla kötüleştirmemeli.

Hiçbiri sağlamazsa Depth Anything eklenmez ve bu sonuç raporlanır.

**Tahminler (_tahmin):**
- H7a: PA, P0'dan düşük. Segmentasyon gürültüsü zarar verir.
- H7b: PC, karar kuralını sağlar. Yükseltilmiş yapıyı ve ağacı SORA kanalından çıkarmak, v3'ün kaçırdığı yerleri düzeltir.

## Düzeltme 8 (2026-10-17): A2b — kalkan eğitimin içinde, eğitimden önce

**Gerekçe:**
- Pilot sahnelerde kalkan güvensiz inişi sıfırladı (tohum 0: 46 → 0).
- Ama bölümlerin çoğu süre dolarak bitti (1 → 41).
- Politika kalkansız eğitildiği için kalkanın engellediği durumlarda ne yapacağını bilmiyor.

**A2b:** A1 ile aynı, tek fark `shield_m = 10`. Kalkan ortamın içinde çalışır: 10 m altında, SORA kanalı ortayı güvenli göstermiyorsa "alçal" yerine en yakın güvenli piksele kayma uygulanır. Politika bunu eğitim boyunca yaşar.
- 2M adım, tohum 0. Çıktı `~/rl_inis/kos/messi_a2b_s0`.
- A1 bitince otomatik başlar.

**Değerlendirme:** A1 ile aynı listeler (`test`, `test7`, `train_ornek20`), kalkan açık.

**Tahminler (_tahmin):**
- H8a: `test` üzerinde A2b SORA başarısı ≥ A1'in RL + kalkan sonucu + 5 puan.
- H8b: A2b güvensiz iniş ≤ %2.
- H8c: A2b süre doldu oranı < A1'in RL + kalkan oranı.

**Gece kuyruğu (2026-10-17):**
1. Düzeltme 7'nin 5 kolu sırayla: P0, PA, PB, PC, PD; her biri eğitim + test.
2. A1 bitince A2b.

Bellek: A1 veya A2b ile bir kol aynı anda koşar (~9.5 GB / 11 GB, _hesap).
- Uygulama notu (01:25): kollar `--vec dummy` ile koşar: 4 ortam tek süreçte. Algoritma ve veri aynıdır. İlk denemede (SubprocVecEnv) swap'a 1.7 GB taşıldı. P0 8k adımda durduruldu ve baştan başlatıldı.

## Yürütme notu (2026-10-17 13:55): bilgisayar uykuya geçti, koşular yeniden başlatıldı

**Olay (ölçülen, Windows System günlüğü):**
- 01:25:09 `winlogon.exe` uyku istedi (Kernel-Power 187, neden "Application API"). Boşta kalma zaman aşımı değil.
- 11:01 güç kaynağı değişti (105, adaptör çıktı) ve bilgisayar yine uyudu. 13:42'de uyandı, WSL yeniden başladı.
- Ölen koşular:
  - A1 753 664 / 2M adımda kaldı. Son checkpoint 600 000 adım. `model.zip` ve değerlendirme yok.
  - P0 49 152 adımda kaldı.
  - A2b hiç başlamadı.

**Yeniden başlatma:**
- A1, `ckpt/model_600000_steps.zip`'den devam eder (`train.py --resume`).
  - Geri gelenler: ağırlıklar, Adam durumu, adım sayacı.
  - Öğrenme oranı programı toplam 2M adıma göre sürer.
  - Rollout tamponu ve bölümler sıfırdan başlar. Ortam tohumları 600 000 kaydırılır, aynı sahne sırası tekrar etmez.
  - 600k–753k arası eğitim atılır. İlk kısmın `monitor_*.csv` dosyalarında bu aralık kalır. Analizde ilk kısım 600 000 adımda kesilir; devam kısmı `monitor_devam600000_*` ve `devam600000/progress.csv` dosyalarındadır.
  - Sonuçlar, kesintisiz bir 2M koşusuyla birebir aynı değildir. Fark, rollout'un yeniden başlamasıyla ve tohumla sınırlıdır.
- Düzeltme 7'nin beş kolu baştan başlar. P0'ın yarım klasörü `kos/_olu/` altına taşınır.
- A2b, A1 değerlendirmesinden sonra başlar (değişmedi).
- Hipotezler, karar kuralları, listeler ve adım sayıları değişmedi.

**İkinci kesinti (14:57, ölçülen):**
- Sebep benim hatam. Eğitimler koşarken bir hız ölçümü başlattım. WSL belleği (12 GB) taştı.
  - Çekirdek P0'ı öldürdü (OOM). Ardından bütün koşular durdu.
  - WSL dağıtımı, GPU kullanan her işte yeniden çöktü. `wsl --shutdown` ile temizlendi.
- Kalan kayıt noktaları: A1 1 000 000 adım, P0 500 000 adım. Koşular bu noktalardan aynı `--resume` yöntemiyle devam eder.
  - A1'in 1.0M–~1.2M arası atılır.
  - P0'ın 500k–~549k arası atılır.
- Önlemler:
  - Eğitim koşarken başka bir GPU veya bellek işi çalıştırılmaz.
  - Kuyruk, bağlı bir `wsl.exe` istemcisiyle ön planda koşar (`~/rl_inis/kuyruk.sh`).
- Hipotezler, listeler ve adım sayıları değişmedi.

**Hız yaması (2026-10-17 ~16:10, sonucu değiştirmez):**
- Değişiklikler:
  - `dynamics.py`: Tutum matrisi yalnız kameranın kullandığı kayıt için hesaplanır. Aynı `rotation()` aynı sayılarla çağrılır, sadece ~5 kat daha az.
  - `camera.py`:
    - `sora_channel`'da `np.isin` yerine uint8 arama tablosu kullanılır.
    - 3-vektör çapraz çarpım elle yapılır; çarpımlar ve farklar aynıdır.
  - `scene.py`: Harita okuma tek toplama ile yapılır. Fotoğraf üstündeki indeks, eskisiyle aynı kesilmiş çarpımdır.
- Doğrulama (ölçülen): HEAD kodu ile yamalı kod, 6 kol ayarında aynı tohum ve aynı eylemlerle koşuldu.
  - Her ayarda 40 bölüm koşuldu, toplam ~21 000 adım.
  - Gözlemlerin SHA-256 özeti, ödüller, ödül bileşenleri, eylemler, kalkan bayrakları, iniş noktaları ve sonuçlar **bit bit aynı** çıktı.
  - 26 birim testi geçti.
- Hız (ölçülen, arkada iki eğitim koşarken, 4 turun en iyisi): Ortam adımı A1 ayarında 2.22 → 1.49 ms, PD ayarında 3.32 → 2.26 ms.
- Koşan süreçler eski kodla devam eder, sonraki kollar yeni kodla başlar. Sonuçlar bit bit aynı olduğu için karşılaştırma bozulmaz.
- Uygulanmayanlar: Aşağıdakiler öğrenmeyi veya girdiyi değiştirir. Ancak ayrı ve ön kayıtlı bir kolla denenebilirler.
  - batch 512
  - gözlemi uint8 veya float16 saklamak

**Karar K73/K74 (2026-10-17 ~16:45):**
- Kuyruk (A1, A2b) biter. Kuyruğa yeni giriş eklenmez.
- Bütün sonuçlar **"ön sonuç, tek tohum"** etiketiyle raporlanır. ≥3 tohum kuralı bundan sonraki deneyler içindir.
- K74 varsayılanı: Depth Anything deneyinde koşan kol (PA) biter, yeni kol başlamaz. `da_kollar.sh` döngüsü durduruldu; PA, `pa_bitir.sh` ile değerlendirilir.
  - PB/PC/PD koşmadı. Bu yüzden düzeltme 7'nin karar kuralı (H7) şimdilik karara bağlanamaz.
  - Depth Anything sonuçları "tahmin, göreli derinlik, metrik değil" etiketiyle raporlanır.
- K76: v3, test uçuşu 0004'ün 13 karesiyle eğitildi. 173 RGB karesinin hiçbiri iyimserlikten arınmış değil (`docs/rl_veri/k76_v3_kullanim.md`). Tahmin maskeli değerlendirmeler "iyimser" etiketi taşır.
- **K74 cevabı (Arda, 2026-10-17 ~16:55): devam.** PA'nın değerlendirmesi bitince PB, PC ve PD, ön kayıttaki sırayla ve aynı ayarlarla koşar (`derinlik/da_devam.sh`). Bu yeni bir giriş değil: kuyruğun ilk planındaki kollar geri açıldı. PB, PC ve PD yeni hız yamalı kodla koşar; sonuçlar bit bit aynıdır (yukarıdaki not).

## Düzeltme 9 (2026-10-17): `zemin_v1` ödülü ve aynalama — B deneyi, eğitimden önce

**Gerekçe (ölçülen):**
- A1'in iniş noktalarını tampona göre yeniden yargıladım (aynı 300 deneme, `tanilama/tampon_politika.py`). Tamponu kaldırmak RL'ye yalnız +3.7 puan kazandırıyor (%56.3 → %60.0). Düz alçalma ise %18.3 → %46.3 çıkıyor.
  - Yani RL'nin güvensiz inişleri (%35) tampon yüzünden değil. Çoğunda araç inilemez zemine iniyor.
- `sora_v1` ödülünde güvensiz iniş (−20), süre dolmasından (−50) hafif. Ajan emin olmadığında inmeyi seçiyor.
- **Kullanıcı kararı (Arda, 2026-10-17):**
  - Yapılar ve su için 3 m tampon kalkar.
  - İnsan ve araç için 2 m tampon kalır.
  - Yumuşak zemin tercih edilir.
  - Ceza artırılır.
  - Aynalama denenir.

**`zemin_v1` (yeni ödül ayarı):**
- **Başarı:** Aracın altındaki nokta inilebilir (yumuşak veya sert) ve 2 m içinde insan veya araç yok.
- **Terminal ödül, inilen sınıfa göre** (2 m içinde insan veya araç varsa o sınıf sayılır):

  | Sınıf | Ödül |
  |---|---|
  | yumuşak | +50 |
  | sert | +30 |
  | asfalt/ağaç | −40 |
  | bina | −60 |
  | su | −70 |
  | araç | −90 |
  | insan | −100 |
  | bilinmeyen | −50 |
  | süre doldu | −50 (değişmedi) |

- **Değişmeyenler:** adım ve eylem ödülleri, potansiyel şekillendirme katsayısı (k = 2), alanın dışına çıkma (−50).
- **Gözlemin 3. kanalı, şekillendirme hedefi ve görüş kâhini** yeni hedefi kullanır: inilebilir zemin, insan ve araçtan 2 m uzak.
- **Teori (_hesap, γ = 0.99, 0.25 s adım):**
  - +50/+30 ile ajan, yumuşak zemin için en fazla ~5 m fazladan yol gider.
  - İnsan, araç, bina ve su cezaları süre dolmasından ağır. Ajan vakti varken bunlara inmez.
- **Aynalama:** Her eğitim bölümünde sahne, 0.5 olasılıkla x ekseninde aynalanır. Değerlendirmede aynalama yok.
- **Kod:** `env.py`, `scene.py`, `pilots.py`, `train.py`, `evaluate.py`.
  - Eski ayarlar HEAD ile 6 kol ayarında bit bit aynı.
  - 34 birim testi geçti (8'i yeni).
  - Değerlendirmeye `duz_kalkan` (düz alçalma + kalkan) taban çizgisi eklendi.

**B deneyi:**
- Kollar:
  - B0: `sora_v1` (kıyas),
  - B1: `zemin_v1`,
  - B2: `zemin_v1` + aynalama.
- Her kol için tohum 0, 1 ve 2, her biri 1M adım. Ayarlar A1 ile aynı: ent 0.01, 4 ortam, `--shard`, SORA hücresi 0.25 m, `--vec dummy`.
- **Eğitim listesi:** `train_b.txt`, 600 kare. Agamim'den {0004, 0043, Path B} çıkarıldı.
- **Doğrulama:** `val_b32.txt` (`val_b.txt`'deki 96 karenin her 3. karesi, 32 kare) × 10 başlangıç = 320 deneme. Süre sınırı 30 s, nominal dinamik.
- **IrYamim bu deneyde hiç kullanılmaz** (K75: yalnız final test).
- **Raporlama:**
  - Her kol için 3 tohumun ortalaması ± standart sapma.
  - Bütün kollar iki kuralla da yargılanır: zemin başarısı ve 3 m SORA başarısı.
  - Ayrıca yumuşak zemin payı, inilen sınıfların dağılımı ve süre dolma oranı.
- **Birincil ölçüt:** RL'nin kalkansız zemin başarısı.

**Tahminler (_tahmin):**
- **H9a:** B1'in kalkansız güvensiz inişi (zemin kuralına göre), B0'ınkinden en az %25 az.
- **H9b:** B1'in zemin başarısı ≥ B0'ınki + 5 puan.
- **H9c:** Başarılı inişler içinde yumuşak zemin payı B1'de B0'dan yüksek.
- **H9d:** B2'nin zemin başarısı ≥ B1'inki + 3 puan.
- **Karar:** H9a ve H9b ortalamada sağlanır ve 3 tohumun en az 2'sinde aynı yöndeyse `zemin_v1` benimsenir. H9d sağlanırsa aynalama da benimsenir.

**Koşum sırası:**
- Tohum sırasıyla: önce B0, B1, B2 tohum 0; sonra tohum 1; sonra tohum 2.
- Aynı anda en fazla 2 eğitim çalışır, Depth Anything kolları dahil. Yeni koşu ancak WSL'de en az 7 GB boş bellek varsa başlar.
- Tahmini bitiş ertesi sabah (_hesap).

## Düzeltme 10 (2026-10-17): kodlayıcı (ağ gövdesi) karşılaştırması, eğitimden önce

**Gerekçe:**
- Kullanıcı isteği (Arda): semantik maske ile derinliği ayrı kollardan beslemek ve makalenin CNN'inden farklı yapıları denemek.
- Makalenin gövdesi Atari'nin "Nature CNN"i. CoinRun ve Procgen'de IMPALA-CNN yeni seviyelere daha iyi genelleşti (Cobbe ve ark. 2019, 2020).
- Bizim görevde kararı güvenli alanın görüntüdeki yeri veriyor. CoordConv (Liu ve ark. 2018) bu "nerede" bilgisini kolaylaştırır.
- Gri sınıf kodlaması (sınıf/7) sınıflar arasında sahte bir sıra ve mesafe kurar. One-hot bunu önler (görev planı, Aşama 4).

**Kodlayıcılar (`policy.py`, başlıklar makaledeki gibi: actor 3×FC64, critic 2×FC32):**

| Kod | Ad | Yapı | Parametre (başlıkla) |
|---|---|---|---|
| E0 | `paper` | Makale: gri sınıf + derinlik + maske üst üste (erken birleştirme), Nature CNN, FC128 | 1.26M |
| E1 | `paper_onehot` | Aynı gövde, sınıflar 8 one-hot kanal | 1.27M |
| E2 | `iki_kol` | Geç birleştirme: semantik kol (one-hot + maske, Nature CNN) ve derinlik kolu (dar Nature CNN), yükseklik ayrı bir sayı, FC128 | 1.88M |
| E3 | `impala` | IMPALA-CNN (3 aşama, artık bloklar) + iki koordinat kanalı (CoordConv), one-hot, FC256 | 2.20M |

**Aşama 1, vekil görev (ucuz ön eleme):**
- **Görev:** Gözlemden görüş kâhininin eylemini tahmin etmek (10 sınıf). Kâhin gerçek maskeyle karar verir, kodlayıcı ise sadece gözlemi görür.
- **Veri:**
  - Eğitim: `train_b`'nin her 4. karesi (150 kare), 20 000 rastgele başlangıç.
  - Doğrulama: `val_b32` (32 kare), 4 000 başlangıç.
  - Başlangıç yüksekliği 5–30 m, `zemin_v1` hedefi.
  - Derinlik saklarken 40/255 m'ye nicelenir.
- **Eğitim bütçesi:** Her kodlayıcı aynı bütçeyle: 6 epok, Adam 3e-4, batch 256. Tohum 0, 1 ve 2.
- **Ölçüt:** Doğrulamada dengeli doğruluk (sınıf başına doğruluğun ortalaması). Ayrıca düz doğruluk ve "alçal mı, alçalma mı" doğruluğu.
- **Ne zaman:** Bellek uygun olunca kendiliğinden koşar: en az 4.5 GB boş bellek ve en çok bir eğitim çalışıyor olmalı.
- Vekil görevde iyi çıkan her kodlayıcı PPO'da da iyi çıkmak zorunda değil. Bu yüzden ikinci aşama var.

**Aşama 2, PPO doğrulaması (B deneyinden sonra, ayrıca başlatılır):**
- Vekil görevde dengeli doğruluğu en yüksek iki kodlayıcı (E0 hariç) koşulur. Her biri 3 tohum, 1M adım.
- Ödül, B deneyinin karar kuralıyla seçilen ödül. Liste, doğrulama ve öbür ayarlar B ile aynı.
- Kıyas: B'nin kazanan kolu (E0, aynı 3 tohum).

**Tahminler (_tahmin):**
- **H10a:** E1, E0'dan dengeli doğrulukta en az 2 puan iyi.
- **H10b:** E2 ≥ E1.
- **H10c:** Vekil görevde en iyisi E3.
- **H10d:** PPO'da en iyi kodlayıcı, doğrulamadaki zemin başarısını E0'a göre ortalamada en az 3 puan artırır, 3 tohumun en az 2'sinde aynı yönde.

**K79 notu:** Tasarım kararı K79, Impoola ve benzeri "iyileştirme" mimarilerini kilitliyor. E3 (IMPALA + CoordConv) bu kilide yakın. Vekil görev, görev planının Aşama 4'ündeki küçük ölçekli testtir. E3'ün PPO aşamasına geçmesi Arda'nın veya tasarım sohbetinin onayını bekler.

**Yürütme notu (2026-10-17 22:35): PD yeniden koşulacak**
- **Olay:** PC eğitimi bitince B kuyruğu boş yeri gördü ve B2-s0'ı başlattı. B1-s0 zaten koşuyordu. Ardından `da_kollar.sh` PD'yi bellek kontrolü yapmadan başlattı. Sonuç: aynı anda 3 eğitim, boş bellek 586 MB (ölçülen).
- **Önlem:** Taşmayı önlemek için PD bir dakika sonra durduruldu. Kayıt noktası yoktu.
- **Yeniden koşma:** PD aynı ayarlarla `derinlik/pd_tekrar.sh` ile yeniden koşacak. Ancak en çok bir eğitim çalışırken ve en az 5.5 GB boş bellek varken başlar.
- Kollar arasında sıra değişti, ayarlar değişmedi.

## Sonuç: Düzeltme 7, Depth Anything deneyi (2026-10-18 02:55)

PD 02:10'da bitti (yeniden koşu; ilk deneme bellek yüzünden durdurulmuştu). Değerlendirme: test uçuşu 0004,
600 iniş, argmax, tek tohum (ön sonuç). Karar kuralı `~/rl_inis/derinlik/h7_karar.py` ile uygulandı.
SORA başarısı ve güvensiz iniş oranı (ölçülen):

| Kol | RL SORA | RL güvensiz | RL+kalkan SORA | RL+kalkan güvensiz | Kural (PA'ya göre) |
|---|---|---|---|---|---|
| P0 (GT, kıyas) | 15.8 | 9.7 | 17.5 | 0.0 | — |
| PA (v3) | 13.3 | 28.5 | 10.3 | 1.7 | — |
| PB | 4.7 | 95.3 | 33.0 | 20.2 | sağlamaz |
| PC | 7.7 | 92.3 | 31.7 | 17.3 | sağlamaz |
| PD | 15.2 | 71.3 | 25.0 | 6.0 | sağlamaz |

**Karar: Depth Anything eklenmez.** PB, PC ve PD'nin üçünde de RL + kalkan SORA başarısını 14–23 puan
artırdı. Ama güvensiz inişi 4–19 puan kötüleştirdi; kural 3 puandan fazlasına izin vermiyor. Kalkansız RL
iki kolda çöktü (PB %95, PC %92 güvensiz: neredeyse her zaman "alçal").

- **H7a tuttu.** PA, P0'dan düşük: RL 13.3 < 15.8, RL + kalkan 10.3 < 17.5. Segmentasyon gürültüsü zarar veriyor.
- **H7b tutmadı.** PC karar kuralını sağlamadı.

Not: kalkanlı SORA artışı gerçek bir etki olabilir. Ama güvensiz inişteki artış daha büyük ve ön kayıt bunu
karşılaştırmanın şartı yaptı. Yeni bir deneme ancak yeni bir ön kayıtla açılabilir; bu sonuç değiştirilmez.

## Sonuç: Düzeltme 9, B deneyi (2026-10-18 07:40)

9 koşu bitti (3 kol × 3 tohum, 1M adım). Değerlendirme: val_b32, 320 deneme / koşu, argmax, süre sınırı 30 s.
Kural `~/rl_inis/h9_karar.py` ile uygulandı. Ölçülen, 3 tohumun ortalaması ± standart sapma, zemin kuralıyla.

**RL, kalkansız (birincil):**

| Kol | Zemin başarısı | Güvensiz iniş | Süre doldu | Başarılarda yumuşak payı | SORA 3 m |
|---|---|---|---|---|---|
| B0 (sora_v1) | 22.1 ± 17.7 | 17.7 ± 27.5 | 60.2 ± 45.2 | 59.6 ± 39.5 | 16.4 ± 8.6 |
| B1 (zemin_v1) | 56.9 ± 10.9 | 18.6 ± 10.3 | 24.5 ± 16.3 | 27.4 ± 5.3 | 12.2 ± 2.4 |
| B2 (zemin_v1 + aynalama) | 35.6 ± 32.0 | 3.1 ± 4.9 | 55.8 ± 32.1 | 55.7 ± 37.1 | 10.8 ± 3.6 |

**RL + kalkan:**
- B0: 24.2 ± 21.0
- B1: 66.7 ± 13.1
- B2: 37.2 ± 34.5

**Tahminler:**
- **H9a tutmadı.** B1'in güvensiz inişi B0'ınkinden az değil (18.6 / 17.7). Tohum bazında yalnız tohum 0'da tuttu.
- **H9b tuttu.** B1 ≥ B0 + 5, üç tohumda da. Ortalamada +34.8 puan.
- **H9c tutmadı.** B1'de yumuşak payı daha düşük. B0'ın az sayıdaki başarısı çoğunlukla yumuşak.
- **H9d tutmadı.** B2'nin tohum 1 ve 2'si çoğunlukla süre doldurdu (aynalama eğitimi kararsızlaştırdı, _tahmin).

**Karar (ön kayıtlı kurala göre): `zemin_v1` benimsenmez; aynalama benimsenmez.**

Not: B0'ın düşük güvensiz oranı, denemelerin %60'ında hiç inmeyip süreyi doldurmasından geliyor. Kural bu
durumu ödüllendiriyor. Birincil ölçüt (zemin başarısı) B1'de açıkça yüksek. Kural sonradan değiştirilmedi.
Yeni bir yargı ancak yeni ön kayıtla yapılır; bu Arda'nın kararı.

## Düzeltme 11 (2026-10-18): `zemin_v2` ödülü — C deneyi, eğitimden önce

**Gerekçe:**
- **Kullanıcı isteği (Arda, 2026-10-18):** AirSim'de RL + v3 sert zemine (yol) iniyor. Arda yumuşak zemine (çim) daha sık inmesini istiyor. Seçtiği yol: yeniden eğitim (`zemin_v2`).
- **Ölçülen, B1 (val_b32, kalkansız RL):** yumuşak iniş 15.8 ± 5.3, sert iniş 41.0 ± 6.6 (320 denemenin yüzdesi). Görüş kâhini (B2-s0 değerlendirmesi) %34.1 yumuşak iniyor.
- **Ölçülen, B2-s0 hafif ortamda (val_b32, 96 bölüm):**
  - 15 m üstünde eylemlerin %100'ü "alçal".
  - İlk yanal eylemin medyan irtifası 9.2 m. Yanal eylemlerin çoğu 5–10 m arasında.
- **Ölçülen, AirSim'de aynı model:** 3 RL inişinde de 10 m'ye kadar %100 "alçal".
- `zemin_v1`'de sert iniş +30, yumuşak +50. Fark küçük, ajan altındaki sert zemini kabul ediyor.

**`zemin_v2` (yeni ödül ayarı) = `zemin_v1` + iki değişiklik:**
1. **Sert zemine iniş +5** (önce +30). Öbür sınıfların ödülleri aynı (yumuşak +50, asfalt/ağaç −40, … , süre doldu −50).
2. **Şekillendirme yumuşak zemine yönelir:**
   - Potansiyel = −k · min(d_yumuşak, d_hedef + 10 m, 20 m), k = 2.
   - d_hedef: en yakın inilebilir hedef (`zemin_v1` ile aynı).
   - d_yumuşak: en yakın yumuşak hedef (yumuşak sınıf, insan ve araçtan 2 m uzak).
   - Yumuşak zemin, en yakın hedeften 10 m'den fazla uzaktaysa çekim yok, ajan `zemin_v1` gibi davranır.
- **Değişmeyenler:**
  - Başarı kuralı (zemin), adım ve eylem ödülleri, alan dışı (−50).
  - Gözlem: 3. kanal yine inilebilir hedef. Yumuşak/sert ayrımı 1. kanalda (sınıf) zaten var.
  - Kalkan. AirSim'deki politika düğümü değişmez.
- **Teori (_hesap, γ = 0.99, 0.25 s adım, yanal adım −0.25):**
  - Ajan yumuşak zemin için en fazla ~23 m fazladan yol gider. `zemin_v1`'de aynı hesapla ~7.5 m.
  - Risk: test süre sınırı 30 s. 20–30 m'den 5 m'ye alçalmak 7.5–12.5 s sürer, yanal yol için 17–22 s kalır. Eğitimde sınır 90 s. Süre dolması artabilir (_tahmin).
- **Kod:** `env.py` (`zemin_v2` ayarı, `soft_bias_m`, `soft_classes`), `scene.py` (hedef ızgarasına sınıf seçimi), `train.py`, `evaluate.py` (`--land-hard` ayarın üstüne yazar).
  - Eski ayarlar değişmedi: `soft_bias_m` varsayılanı −1 (kapalı).
  - 48 birim testi geçti (6'sı yeni).

**C deneyi:**
- **C1:** `zemin_v2`, tohum 0, 1 ve 2, her biri 1M adım. Ayarlar B1 ile aynı: ent 0.01, 4 ortam, `--shard`, SORA hücresi 0.25 m, `--vec dummy`, aynalama yok, kodlayıcı `paper`.
- **Kıyas:** B1 (`zemin_v1`, tohum 0–2). Yeniden koşulmaz; değerlendirme aynı (val_b32 × 10 başlangıç = 320 deneme, 30 s, nominal dinamik).
- **Eğitim listesi** `train_b.txt`. IrYamim kullanılmaz.
- **Koşum:** `~/rl_inis/kuyruk_c.sh`.
  - Aynı anda en fazla 2 eğitim. Yeni koşu için en az 7 GB boş bellek.
  - AirSim oturumu açıkken başlamaz.
- **Karar betiği:** `~/rl_inis/h11_karar.py`.

**Ölçütler (320 denemenin yüzdesi, kalkansız RL birincil):**
- Yumuşak iniş: yumuşak zemine başarılı iniş (2 m içinde insan veya araç yok).
- Zemin başarısı.
- Güvensiz iniş: indi ama zemin başarısı yok.
- **Tanımlayıcı (karara girmez):** sert iniş, süre doldu, SORA 3 m, RL + kalkan, ilk yanal eylemin medyan irtifası.

**Tahminler (_tahmin):**
- **H11a:** C1'in yumuşak inişi ≥ B1'inki + 10 puan (B1: 15.8).
- **H11b:** C1'in zemin başarısı ≥ B1'inki − 5 puan (B1: 56.9).
- **H11c:** C1'in güvensiz inişi ≤ B1'inki + 5 puan (B1: 18.6). Bu bir güvenlik koruması: yumuşak zemin arayışı güvensiz inişi artırmamalı.
- **Karar:**
  - H11a, H11b ve H11c ortalamada sağlanmalı.
  - Her biri tohum çiftlerinin (C1-sN ile B1-sN) en az 2'sinde de sağlanmalı.
  - İkisi de olursa `zemin_v2` benimsenir.
- **AirSim modeli:** Benimsenirse, H11b ve H11c'yi kendi tohum çiftinde sağlayan C1 tohumları arasından yumuşak inişi en yüksek olan seçilir. AirSim'de B2-s0 ile aynı başlangıçlarda karşılaştırılır.
- Benimsenmezse AirSim'de B2-s0 kalır. Yeni bir deneme ancak yeni ön kayıtla açılır.
