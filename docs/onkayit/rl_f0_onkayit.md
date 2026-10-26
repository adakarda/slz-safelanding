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

## Düzeltme 12 (2026-10-18): eğitimde 30 s süre sınırı — D deneyi, eğitimden önce

**Gerekçe (ölçülen, tanılama, `~/rl_inis/sure_etkisi.py`):** B2-s0, val_b32'nin aynı 320 denemesi, yalnız test süresi değişti.

| Test süresi | RL | RL + kalkan | Süre doldu (RL + kalkan) | Güvensiz (RL) |
|---|---|---|---|---|
| 30 s (ön kayıtlı test) | 72.5 | 76.9 | 22.8 | 8.8 |
| 60 s | 77.5 | 86.6 | 13.1 | 10.0 |
| 90 s (eğitimdeki sınır) | 80.0 | 88.1 | 11.6 | 10.6 |

- Kayıpların çoğu süre dolmasından geliyor. Politika doğru yere gidiyor ama yavaş.
- Eğitimde bölüm sınırı 90 s, testte 30 s. Politika 30 s içinde inmeyi hiç öğrenmedi (_tahmin).
- **Test süresi değişmez (30 s).** Yukarıdaki tablo yalnız tanılamadır, sonuç olarak raporlanmaz.
- **Kullanıcı kararı (Arda, 2026-10-18):** D deneyi yapılır, AirSim Faz 6'dan sonra.

**D1:**
- Tek fark: eğitimde bölüm sınırı 30 s (`train.py --max-t 30`). Test zaten 30 s.
- **Ödül:** C deneyinin kararına göre seçilir.
  - `zemin_v2` benimsendiyse D1 `zemin_v2` ile eğitilir, kıyas C1 olur.
  - Benimsenmediyse D1 `zemin_v1` ile eğitilir, kıyas B1 olur.
- Öbür ayarlar kıyas koluyla aynı: tohum 0, 1 ve 2, 1M adım, ent 0.01, 4 ortam, `--shard`, SORA hücresi 0.25 m, `--vec dummy`, aynalama yok.
- **Kod:** `train.py --max-t` (yalnız verilirse `EnvConfig.max_t`'yi değiştirir; eski koşuların ayarı değişmez). 49 birim testi geçti (1'i yeni).
- **Değerlendirme:** kıyasla aynı (val_b32 × 10 = 320 deneme, 30 s, nominal dinamik, argmax).
- **Koşum:** `~/rl_inis/kuyruk_d.sh`. C kuyruğu ve AirSim Faz 6 bitince başlar. Aynı anda en fazla 2 eğitim, en az 7 GB boş bellek.
- **Karar betiği:** `~/rl_inis/h12_karar.py`.

**Tahminler (_tahmin):**
- **H12a (birincil):** D1'in kalkansız RL zemin başarısı ≥ kıyasınki + 5 puan.
- **H12b:** D1'in RL + kalkan zemin başarısı ≥ kıyasınki + 5 puan.
- **H12c (güvenlik koruması):** D1'in kalkansız güvensiz inişi ≤ kıyasınki + 5 puan.
- **Karar:**
  - H12a ve H12c ortalamada sağlanmalı.
  - İkisi de tohum çiftlerinin (D1-sN ile kıyas-sN) en az 2'sinde sağlanmalı.
  - İkisi de olursa eğitimde 30 s sınırı benimsenir. H12b destekleyici olarak raporlanır.
- **Tanımlayıcı:** süre doldu, çime iniş, ilk yanal eylemin irtifası (`eylem_irtifa_env.py`).
  - Paper'ın %87.6'sı da yan yana yazılır. Ama kural ve veri farklı olduğu için karşılaştırma değildir.
- **Beklenen (_tahmin):** D1 RL + kalkan ≥ %85, süre doldu ≤ %10.
- **Not:** val_b32 artık birçok kararda kullanıldı, ona göre aşırı uyum riski var. Son sayı ancak IrYamim final testinde verilir (K75); o test bu deneyde kullanılmaz.

## Sonuç: Düzeltme 11, C deneyi (2026-10-18 16:08)

3 koşu bitti (C1 = `zemin_v2`, tohum 0–2, 1M adım). Değerlendirme: val_b32, 320 deneme / koşu, argmax, 30 s.
Kural `~/rl_inis/h11_karar.py` ile uygulandı. Ölçülen, 3 tohumun ortalaması ± standart sapma, 320 denemenin yüzdesi.

**RL, kalkansız (birincil):**

| Kol | Çime iniş | Zemin başarısı | Güvensiz | Sert iniş | Süre doldu |
|---|---|---|---|---|---|
| B1 (`zemin_v1`) | 15.8 ± 5.3 | 56.9 ± 10.9 | 18.6 ± 10.3 | 41.0 ± 6.6 | 24.5 ± 16.3 |
| C1 (`zemin_v2`) | 19.8 ± 8.7 | 50.9 ± 5.6 | 21.0 ± 8.2 | 31.1 ± 5.6 | 27.8 ± 13.3 |

**RL + kalkan:** B1 zemin başarısı 66.7 ± 13.1, çim 16.4; C1 zemin başarısı 60.4 ± 6.5, çim 20.6, süre doldu 37.3 (B1: 30.5).

**Tahminler:**
- **H11a tutmadı.** Çime iniş +4.0 puan (gereken +10). Tohum bazında +9.4, +6.2, −3.8.
- **H11b tutmadı.** Zemin başarısı 50.9; eşik 51.9 (B1 − 5). Tohum 0 ve 1'de tuttu, tohum 2'de tutmadı.
- **H11c tuttu.** Güvensiz iniş 21.0 ≤ 23.6, üç tohumda da.

**Karar (ön kayıtlı kurala göre): `zemin_v2` benimsenmez.** AirSim'in varsayılan modeli B2-s0 kalır.
- Faz 6, C1-s0 ile yalnız tanımlayıcı olarak koşar. C1-s0, `h11_karar.py`'nin seçimi: çim 29.7, zemin başarısı 56.6.
- D deneyi (Düzeltme 12) bu karara göre `zemin_v1` ile koşar. Kıyası B1.

**Not (tanımlayıcı):**
- Sert iniş 10 puan azaldı. Ama bunun ancak 4 puanı çime iniş olarak geri döndü. Kalanı süre dolmasına ve güvensiz inişe kaydı.
- Düzeltme 11'deki risk notu gerçekleşti: ajan çim için daha çok yol gidiyor, 30 s sınırı yetmiyor.
- `zemin_v2` + eğitimde 30 s birlikte denenmedi. Denenmesi yeni bir ön kayıt gerektirir.

## Düzeltme 13 (2026-10-18): kayarken alçal eylemleri — E deneyi, eğitimden önce

**Gerekçe (ölçülen, B2-s0, val_b32, başarılı inişler):**
- İniş süresi: RL 16.1 ± 5.1 s, düz alçalma 10.5 ± 1.5 s, görüş kâhini 13.8 ± 4.1 s.
- Paper Tablo I: RL 11.8 s, düz alçalma 10.3 s (7 sahne ortalaması, _hesap). Düz alçalma iki tarafta neredeyse aynı; fark politikada.
- Hafif ortamda B2-s0 önce ~9 m'ye alçalıyor (15 m üstünde %100 "alçal"), sonra 5–10 m arasında yana kayıyor. Eylemler ya kayma ya alçalma olduğu için iki süre toplanıyor. Fazladan ~5.6 s, yani ~22 kayma adımı (_hesap).
- **Kullanıcı isteği (Arda, 2026-10-18):** RL'yi hız için iyileştir, paper'daki gibi hızlı insin. Seçilen yol: kayarken alçal eylemleri.

**E1 = D1 + kayarken alçal:**
- Eylem uzayı 10'dan 18'e çıkar. Yeni 10–17 eylemleri, 1–8 yönlerinde 1 m/s kayarken aynı anda 2 m/s alçalır. Eski 10 eylem değişmez.
- Eylem ödülü: alçal (+0.5) + kayma (−0.05) = +0.45. Öbür ödüller `zemin_v1` ile aynı.
- **Kalkan:** kayarak alçalmayı da alçalma sayar. 10 m altında, merkez güvenli değilse, en yakın güvenli piksele düz kaymaya çevirir.
- **Öbür ayarlar D1 ile aynı:** `zemin_v1` (C kararı), eğitimde 30 s, tohum 0–2, 1M adım, ent 0.01, 4 ortam, `--shard`, SORA hücresi 0.25 m, `--vec dummy`.
- **Kod:**
  - `env.py`: `diag_actions`, `lateral_index`, `descends`.
  - `pilots.py`: kalkan.
  - `train.py` / `evaluate.py`: `--diag`.
  - `policy_node.py`: 10–17'yi 3 boyutlu hıza çevirir, görüş panelinde "ALCAL+YÖN" yazar. PX4 modu zaten 3 boyutlu hız alıyor, değişmez.
  - `politika_ozet.py`: eylem adları.
  - Eski ayarlar değişmez: `diag_actions` varsayılanı kapalı, eylem uzayı 10.
  - 51 birim testi (2'si yeni).
- **Teori (_hesap):** 20–30 m'den 5 m'ye alçalmak 7.5–12.5 s sürer. Bu sürede 7.5–12.5 m kayılabilir. B2-s0'ın ortalama ~5.6 m kayması tamamen alçalmaya binebilir. Süre düz alçalmaya (10.5 s) yaklaşır.

**E deneyi:**
- **Kıyas:** D1, aynı tohumlar. Değerlendirme aynı (val_b32 × 10 = 320 deneme, 30 s, nominal dinamik, argmax, `--diag`).
- **Koşum:** `~/rl_inis/kuyruk_e.sh`. D kuyruğu üç tohumu da başlattıktan sonra boş yer bekler. Aynı anda en fazla 2 eğitim, en az 7 GB boş bellek, AirSim açıkken başlamaz.
- **Karar betiği:** `~/rl_inis/h13_karar.py`.

**Ölçütler (kalkansız RL birincil):**
- **İniş süresi:** zemin kuralına göre başarılı bölümlerin ortalama süresi. Paper'ın tanımı: 20–30 m başlangıç, 30 s sınır, yalnız başarılı koşular.
- Zemin başarısı ve güvensiz iniş, önceki deneylerdeki gibi.
- **Tanımlayıcı:** RL + kalkan, süre doldu, çime iniş, kayarken alçal eylemlerinin payı, ilk yanal eylemin irtifası. Paper (11.8 s), düz alçalma ve kâhin süreleri yan yana yazılır.

**Tahminler (_tahmin):**
- **H13a (birincil, hız):** E1'in ortalama iniş süresi ≤ D1'inki − 2 s.
- **H13b:** E1'in zemin başarısı ≥ D1'inki − 3 puan.
- **H13c (güvenlik koruması):** E1'in güvensiz inişi ≤ D1'inki + 5 puan.
- **Karar:**
  - Üçü de ortalamada sağlanmalı.
  - Her biri tohum çiftlerinin (E1-sN ile D1-sN) en az 2'sinde de sağlanmalı.
  - İkisi de olursa kayarken alçal eylemleri benimsenir.
- **Beklenen (_tahmin):** E1 ortalama iniş süresi 12–13 s.

## Düzeltme 14 (2026-10-18): `zemin_v3` ödülü + eğitimde 30 s — F deneyi, eğitimden önce

**Gerekçe (ölçülen, D1 tohum 0 ve 1, val_b32, kalkansız RL):**
- D1 çöktü. Başarı %25.9 ve %28.8, güvensiz iniş %74.1 ve %64.1.
- D1-s0 her zaman dümdüz alçalıyor (eylemlerin %100'ü), D1-s1 %79 oranında.
- Başarılı inişler hızlı: 10.5 ve 12.3 s. Paper'da 11.8 s.
- **Teşhis (_tahmin):** `zemin_v1`'de yola veya ağaca inmek (−40), süre dolmasından (−50) daha ucuz. 30 s baskısında ajan, aramak yerine dosdoğru inip cezayı göze alıyor.
- **Kullanıcı kararı (Arda, 2026-10-18):**
  - Yol, ağaç ve bilinmeyen zeminin cezası süre dolmasından ağır olsun.
  - Alçal ödülü paper'daki gibi +1 olsun.
  - Eğitimde süre sınırı doğrudan 30 s olsun (paper'ın test sınırı).
  - Görüş terimi ve kademeli süre önerileri seçilmedi.

**`zemin_v3` (yeni ödül ayarı) = `zemin_v1` + iki değişiklik:**
1. **Ceza:** asfalt/ağaç (sınıf 2) ve bilinmeyen (sınıf 7) inişi −60 olur. Öncesi −40 ve −50. Süre doldu −50 olarak kalır.
2. **Alçal eylemi ödülü:** +1, öncesi +0.5.
- Öbür ödüller aynı: çim +50, sert +30, bina −60, su −70, araç −90, insan −100, alan dışı −50, adım −0.2, kayma −0.05, şekillendirme k = 2.
- Kod: `env.py` (`zemin_v3`), `train.py`. 56 birim testi geçti (5'i yeni). Eski ayarlar değişmedi.

**F deneyi:**
- **F1:** `zemin_v3`, eğitimde 30 s (`--max-t 30`), kayarken alçal yok, aynalama yok. Tohum 0, 1 ve 2, 1M adım. Öbür ayarlar B1 ile aynı.
- **Kıyas:**
  - Başarı ve güvenlik için B1 (aynı tohumlar). İniş süresi için de B1.
  - D1 (aynı süre, eski ödül) tanımlayıcı: ödül düzeltmesinin çöküşü önleyip önlemediğini gösterir.
- **Değerlendirme:** val_b32 × 10 = 320 deneme, 30 s, nominal dinamik, argmax.
- **Koşum:** `~/rl_inis/kuyruk_f.sh`. E kuyruğu üç tohumu da başlattıktan sonra boş yer bekler. Aynı anda en fazla 2 eğitim, en az 7 GB boş bellek, AirSim açıkken başlamaz.
- **Karar betiği:** `~/rl_inis/h14_karar.py`.

**Tahminler (_tahmin, kalkansız RL birincil):**
- **H14a:** F1'in zemin başarısı ≥ B1'inki − 3 puan (B1: 56.9).
- **H14b (hız):** F1'in başarılı iniş süresi ≤ B1'inki − 2 s (B1: 15.2 s).
- **H14c (güvenlik koruması):** F1'in güvensiz inişi ≤ B1'inki + 5 puan (B1: 18.6).
- **Karar:**
  - Üçü de ortalamada sağlanmalı.
  - Her biri tohum çiftlerinin (F1-sN ile B1-sN) en az 2'sinde de sağlanmalı.
  - İkisi de olursa `zemin_v3` + eğitimde 30 s benimsenir.
- **Tanımlayıcı:** D1 ile kıyas (düz alçalma payı, güvensiz iniş), RL + kalkan, çime iniş, süre doldu. Paper (11.8 s, %87.6) yan yana yazılır ama kural farklıdır.
- **Beklenen (_tahmin):** başarı ~%55–65, süre ~13 s, düz alçalma payı < %60.

**Faz 7'ye etkisi (Faz 7 koşmadan önce yazıldı):** Faz 7'nin RL modeli sırası şöyle olur:
1. F benimsendiyse F1 (val_b32'de RL + kalkan başarısı en yüksek tohum).
2. Değilse E.
3. Değilse D.
4. Değilse B2-s0.

## Düzeltme 15 (2026-10-18): ödül ve eğitim ayarları taraması — eğitimlerden önce

**Kullanıcı isteği (Arda, 2026-10-18):**
- Performansı en yüksek düzeye çıkarana kadar çok sayıda deneme ve ödül kombinasyonu yapılsın.
- İniş süresi ortalamada paper gibi kısa olsun (paper 11.8 s).

Tek tek tam deneyler (3 tohum × 1M) çok yavaş. Bu yüzden ön kayıtlı, aşamalı bir tarama yapılır. Önce ucuz bir eleme, sonra en iyilerin tam değerlendirmesi.

**Ölçüt — tarama skoru:** S = B_K + 0.5 × B_RL − 4 × max(0, T_K − 12)
- B_K: RL + kalkan zemin başarısı (%).
- B_RL: kalkansız zemin başarısı (%).
- T_K: RL + kalkanın başarılı iniş süresi (s).
- Sahada kalkan kullanılıyor, bu yüzden ağırlık onda. Paper süresinin (~12 s) her 1 s fazlası 4 puan götürür.
- Eğitimde kalkanı olan ayarlar değerlendirmede de ortam içi kalkanla koşar.

**Listeler:**
- Eleme: `val_b64` (val_b'nin val_b32 dışındaki 64 karesi). val_b32 her denemede tüketilmesin diye.
- Son karar: val_b32. IrYamim kullanılmaz (K75, final test).

**Tur 1 (eleme):** 16 ayar, tohum 0. 400k adımda durdurulur, öğrenme oranı 1M programında kalır (`--stop-at`). val_b64 × 5 başlangıç = 320 deneme, yalnız RL ve RL + kalkan. Ayarlar (`~/rl_inis/arama/konfig_t1.json`):

| Ad | Ayar |
|---|---|
| c00 | B1 kontrol (`zemin_v1`, 90 s) |
| c01 | F temel (`zemin_v3`, 30 s) |
| c02 | F + kayarken alçal |
| c03 | F + kayarken alçal, 45 s |
| c04 | F, yol/ağaç/bilinmeyen −80 |
| c05 | F, adım cezası −0.5 |
| c06 | F, alçal +2 |
| c07 | F, şekillendirme k = 4 |
| c08 | F, kalkan eğitimde |
| c09 | F, görüş terimi 0.5 (paper'ın R_S'si) |
| c10 | F, PPO γ = 0.98 (şekillendirme γ'sı da) |
| c11 | F, entropi 0.02 |
| c12 | `zemin_v1` + kayarken alçal, 90 s |
| c13 | F + kayarken alçal + kalkan eğitimde |
| c14 | F + kayarken alçal + adım −0.5 |
| c15 | F, PPO n_steps 1024, batch 128 |

**Tur 2:** Tur 1'de skoru en yüksek 4 ayar aynı koşudan 1M'ye tamamlanır (`--resume`). val_b64 × 10 = 640 deneme.

**Tur 3:** Tur 2'de skoru en yüksek 2 ayarın tohum 1 ve 2'si sıfırdan 1M eğitilir. Üç tohum val_b32 × 10 = 320 denemede tam değerlendirilir (kâhin dahil).

**Karar (H15, `~/rl_inis/arama/kararla.py`):** Tur 3'te ortalama S'si en yüksek ayar, B1 ile karşılaştırılır. Şu dört koşulun hepsi tutarsa yeni en iyi ayar olur:
- **H15a:** ortalama S ≥ B1'in S'si + 5, ve tohum çiftlerinin en az 2'sinde de.
- **H15b:** ortalama B_K ≥ B1'inki − 3.
- **H15c:** ortalama T_K ≤ 13.5 s.
- **H15d:** ortalama kalkansız güvensiz iniş ≤ B1'inki + 5.

**Kod:**
- `train.py`: `--env-json`, `--ppo-json`, `--stop-at`. Ön ayar alanlarının üstüne yazılabilir. PPO γ verilirse şekillendirme γ'sı da değişir.
- `evaluate.py`: `--only-rl`.
- Orkestratör: `~/rl_inis/arama/arama.py` (yer kuralları kuyruklarla aynı). Duman testi geçti. 57 birim testi geçti.

**Sıra:**
- Tarama, F kuyruğu üç tohumunu başlattıktan sonra boş yerlerde başlar.
- F bitince havada başlangıç denemesi önce koşar.
- Faz 7, taramanın kazananıyla taramadan sonra koşar.

**Sonraki aşamalar** (her biri ayrı ön kayıtla, bu taramanın sonucuna göre):
- **Ağ gövdesi (IMPALA / iki kol):** K79 kilidi. Arda'nın onayını bekler.
- **2M adım ve tohum seçimi.**
- **AirSim Faz 7 ve final IrYamim testi:** bir kez.

## Sonuç: Düzeltme 12, D deneyi (2026-10-18 23:02)

3 koşu bitti (D1 = `zemin_v1` + eğitimde 30 s). Değerlendirme: val_b32, 320 deneme / koşu. Kural `h12_karar.py` ile uygulandı. Ölçülen, ortalama ± sapma:

| | B1 (kıyas) | D1 |
|---|---|---|
| RL zemin başarısı | 56.9 ± 10.9 | 24.8 ± 4.6 |
| RL güvensiz iniş | 18.6 ± 10.3 | 59.6 ± 17.2 |
| RL + kalkan başarısı | 66.7 ± 13.1 | 53.6 ± 18.3 |

- **Karar: eğitimde 30 s benimsenmez.** H12a, H12b ve H12c tutmadı.
- **Politika çöktü:** D1-s0 eylemlerinin %100'ü "alçal", D1-s1'in %79'u.
- Başarılı inişler hızlı (10.5–12.3 s), ama güvensiz.
- **Teşhis (_tahmin):** yola veya ağaca inmek (−40), süre dolmasından (−50) daha ucuz. Düzeltme 14 (F) bunu düzeltmek için açıldı.

## Düzeltme 16 (2026-10-18): gözlem turu — risk hafızası, hedef noktası, kademeli risk — eğitimlerden önce

**Kaynak:** de la Torre-Vanegas ve ark. 2025, "Vision-Based Risk Aware Emergency Landing for UAVs in Complex Urban Environments" (arXiv 2505.20423). Yöntemleri klasik: risk haritası, risk hafızası, irtifaya bağlı genişletme, risk + uzaklık en küçüğü. **Kullanıcı isteği (Arda, 2026-10-18):** bu fikirler RL'ye gözlem kanalı olarak eklensin, iyi planlanıp sıralansın.

**Yeni kanallar** (`gozlem.py`; ortam ve ROS düğümü aynı kodu kullanır, eğitim ve sahada aynı girdi):
- **`risk`:** her pikselin sınıfına göre kademeli risk (0–1). Çim 0, sert 0.15, asfalt/ağaç 0.5, bina 0.7, su 0.8, araç 0.95, insan 1, bilinmeyen 0.6.
- **`hedef`:** hedef piksellerinden "1.5 m bulanıklaştırılmış risk + 0.5 × merkeze metrik uzaklık / yarım görüntü genişliği" en küçük olan nokta, küçük bir leke olarak. Görüşte hedef yoksa sıfır. Makaledeki yerel en küçük seçimi.
- **`hafiza`:** bölüm başından beri her zemin hücresinde (0.25 m) görülen en yüksek risk, makaledeki genel risk haritası. Araç etrafında 48 m'lik, burun yukarı bir harita olarak verilir. Hiç görülmemiş hücre 1 (riskli) sayılır. Yukarıdan görülen alan, alçalınca kameranın görüşü daralsa da haritada kalır.
  - AirSim'de RL Landing başlayınca sıfırlanır: modun durum konusu 2 s sessizlikten sonra geldiğinde.
- **Kod:** `env.py` (`kanallar`), `train.py` / `evaluate.py` (`--kanallar`), `policy_node.py`. Ek olarak devam eden koşular yeni dizinde `args.json` da yazar.
  - 64 birim testi geçti (7'si yeni). Testler hafızanın yönünü, kalıcılığını ve sıfırlanmasını, hedefin doğru tarafı göstermesini kapsıyor. Eski ayarlar değişmedi.
  - Hız (ölçülen): üç kanal birlikte ortam adımı 745 → 315 adım/s. Eğitim hızında etkisi ~%20 (_hesap).

**Taban:** taramanın (Düzeltme 15) Tur 3'ünde ortalama skoru en yüksek ayar. H15 kabul etmese de bilinen en iyi aday budur. Tabanın koşuları yeniden koşulmaz.

**Turlar** (`~/rl_inis/arama/gozlem_tur.py`; skor ve yer kuralları taramayla aynı; tarama bitince başlar):
- **G-A:** 4 çeşit (+hafiza, +hedef, +risk, +üçü birden), tohum 0, 400k adım, val_b64 × 5. Kıyas: tabanın Tur 1 koşusu.
- **G-B:** G-A'nın en iyi 2 çeşidi aynı koşudan 1M'ye, val_b64 × 10. Kıyas: tabanın Tur 2 koşusu.
- **G-C:** G-B'nin en iyisinin tohum 1 ve 2'si sıfırdan 1M. Üç tohum val_b32 × 10 = 320 denemede tam değerlendirilir. Kıyas: tabanın Tur 3 koşuları.

**Karar (H16, `gozlem_karar.py`):** çeşit benimsenir, eğer şu dördü de tutarsa:
- **H16a:** ortalama S ≥ taban + 5, ve tohum çiftlerinin en az 2'sinde de.
- **H16b:** ortalama B_K ≥ taban − 3.
- **H16c:** ortalama T_K ≤ taban + 0.5 s.
- **H16d:** ortalama kalkansız güvensiz iniş ≤ taban + 5.

**Tahminler (_tahmin):**
- `hafiza` en çok kazandıran çeşit olur. Daha erken karar verir, yani daha kısa iniş, ve 5–20 m uzaktaki hedeflerde daha yüksek başarı.
- `hedef` uzak hedeflerde yardım eder.
- `risk` küçük bir etki yapar.

**Sıra:**
1. D/E/F (ön kayıtlı)
2. Tarama (Düzeltme 15)
3. Havada başlangıç denemesi (F bitince, ilk boşlukta)
4. Gözlem turu (Düzeltme 16)
5. Faz 7, en iyi modelle

**Faz 7'nin RL modeli sırası:**
1. Gözlem turu benimsediyse onun çeşidi.
2. Değilse H15 kazananı.
3. Değilse F, E, D, B2-s0.

### Düzeltme 15b (2026-10-19 00:30, taramanın hiçbir eğitimi başlamadan önce)

**Gerekçe (ölçülen):**
- D1 (eğitimde 30 s) dümdüz alçalmaya çöktü.
- E1-s0 (30 s + kayarken alçal) ise tersine çöktü: eylemlerin %97.5'i düz kayma, 96 denemenin 92'sinde süre doldu, başarı %8.4.
- Eğitimde 30 s baskısı politikayı iki farklı uca çöktürebiliyor (_tahmin). Tur 1'de neredeyse bütün ayarlar 30 s'de. Bu yüzden süre ekseni genişletildi.

**Tur 1'e 4 ayar eklendi.** Toplam 20 ayar. Öbür turlar, skor ve karar kuralı (H15) değişmedi.

| Ad | Ayar |
|---|---|
| c16 | `zemin_v3`, 60 s |
| c17 | `zemin_v3`, 60 s + kayarken alçal |
| c18 | `zemin_v3`, 90 s (yalnız ödül düzeltmesi, süre baskısı yok) |
| c19 | `zemin_v3`, 90 s + kayarken alçal |

Orkestratör yeniden başlatıldı. Hiçbir tarama eğitimi koşmamıştı, sadece val_b64 referans değerlendirmeleri yapılmıştı. Onlar yeniden kullanılıyor.

## Sonuç: Düzeltme 13, E deneyi (2026-10-19 00:53)

3 koşu bitti (E1 = D1 + kayarken alçal, eğitimde 30 s). Kural `h13_karar.py` ile uygulandı. Ölçülen, ortalama ± sapma, kalkansız RL:

| | D1 | E1 |
|---|---|---|
| Başarılı iniş süresi | 12.2 ± 1.7 s | 15.9 ± 1.5 s |
| Zemin başarısı | 24.8 ± 4.6 | 23.9 ± 25.9 |
| Güvensiz iniş | 59.6 ± 17.2 | 2.5 ± 4.3 |
| Süre doldu | 15.0 ± 20.1 | 70.5 ± 28.2 |

- **Karar: kayarken alçal benimsenmez.** H13a (süre) tutmadı. H13b ve H13c tuttu.
- **E1 ters yönde çöktü:** iniş yerine dolaşıyor. E1-s0'da eylemlerin %97.5'i düz kayma.
- **Tanılama sürüyor (tanımlayıcı):** eğitimde (olasılıkla eylem seçimi) başarı ~%60, argmax testinde %8–24. 18 eylemde argmax yanıltıcı olabilir. Ayrıntı ayrı bir notta.

## Düzeltme 17 (2026-10-19 01:20): final test protokolü — sonuçlardan önce

**Amaç:** tezde verilecek son sayılar. Bütün seçimler val_b32 ve val_b64 ile yapıldı. Bu yüzden son sayı, hiçbir seçimde kullanılmayan IrYamim karelerinde ölçülür (K75).
- **Not:** IrYamim, Düzeltme 6'da (A1 / A2b, B deneyinden önce) bir kez test için kullanıldı. O günden beri hiçbir karar IrYamim'e bakılarak verilmedi.

**Final model:** Faz 7'deki sırayla, sonuçlardan önce sabit:
1. Gözlem turu (H16) benimsediyse onun çeşidi.
2. Değilse tarama (H15) kazananı.
3. Değilse F, E, D.
4. Değilse B2-s0.

Final modelin bütün tohumları raporlanır. "En iyi tohum" ayrıca belirtilir ama ana sayı ortalamadır. B1'in üç tohumu kıyas olarak yanına konur.

**Liste:** `test.txt`: 20 IrYamim karesi × 15 başlangıç = 300 deneme / koşu. Süre sınırı 30 s, nominal dinamik, argmax.

**Yöntemler:**
- RL ve RL + kalkan.
- Düz alçalma ve düz alçalma + kalkan.
- Kanal pilotu.
- Görüş kâhini (tavan).

**Ölçütler:**
- Zemin başarısı, güvensiz iniş, süre doldu, çime iniş.
- Başarılı iniş süresi (ortalama ve medyan).
- SORA 3 m başarısı.
- Paper'ın çoğunluk kuralı, tanımlayıcı olarak.

**Kural:**
- Test bir kez koşulur. Sonuca göre model, ayar ya da ölçüt değiştirilmez.
- Sonuç ne çıkarsa raporlanır.
- Final test yalnız gözlem turu ve Faz 7 bittikten sonra, Arda'nın "koş" demesiyle yapılır. Bu adım geri alınamaz.

**Betik:** `~/rl_inis/final_test.sh` (hazırlandı, koşulmadı).

### Not: E1 tanılaması (2026-10-19 01:10, tanımlayıcı)

| Model | Eğitim sırasında (olasılıkla, rastgele dinamik, eğitim sahneleri) | Eğitim sahneleri (argmax, nominal) | val_b32 (argmax) | val_b32 (olasılıkla) |
|---|---|---|---|---|
| E1-s0 | 62.5 | 24.7 | 8.4 | 10.9 |
| E1-s1 | 59.8 | 71.6 | 53.8 | — |
| B1-s0 | 84.1 | 65.9 | 61.6 | 58.1 |

- **Argmax sebep değil.** E1-s0'da alçalan eylemlerin toplam olasılığı medyan 0.17, yani model gerçekten alçalmıyor.
- **E1-s0 eğitim sahnelerinde bile düşük.** Bu tohum kararsız bir çözüme oturmuş.
- **B1 iyi genelleşiyor:** eğitim sahnelerinde 65.9, doğrulamada 61.6.
- Eğitim sırasındaki başarı ile testteki başarı arasındaki farkın kalanı, rastgele dinamik ve olasılıkla seçimden geliyor (_tahmin).
- Bu not karar değiştirmez.

### Düzeltme 15c (2026-10-19 02:50, Tur 1'in ilk eğitimi 200k adımdayken durduruldu)

**Gerekçe (ölçülen):** F1 (`zemin_v3` + eğitimde 30 s), tohum 0 ve 1:
- Başarı 29.1 ± 11.9, süre doldu 65.6 ± 7.1.
- Eylemlerin %63–83'ü kayma. Model dolaşmaya çöktü, E1 gibi.

**Teşhis (_tahmin):** eğitimde süre kısayken belirsiz durumda iki son yarışıyor: yanlış yere inmek ya da süreyi doldurmak. Cezası küçük olan son, ajanın varsayılanı oluyor.
- D'de yol −40 > süre −50 olduğu için model hep alçaldı.
- F'de yol −60 < süre −50 olduğu için model hiç alçalmadı.
- 90 s eğitimde süre nadiren doluyor, bu çatışma oluşmuyor (B1).

**Değişiklikler:**
1. **Sıra:** 90 s ve 60 s'li ayarlar öne alındı. 30 s'li ayarlar sona kaldı.
2. **Yeni 90 s ayarları:** hız süre sınırıyla değil, ödülle zorlanıyor (`zemin_v1` tabanı).

   | Ad | Ayar |
   |---|---|
   | c20 | adım cezası −0.5 |
   | c21 | alçal +1 |
   | c22 | γ 0.98 |
   | c23 | adım −0.5 + alçal +1 |
   | c24 | kayarken alçal + adım −0.5 |

3. **Mevcut koşular yeniden eğitilmez.** c00 (B1 kontrol) ile B1, c01 (F temel) ile F1 aynı ayar ve tohumda.
   - Tur 1 modeli: o koşunun 400k kayıt noktası. Öğrenme oranı programı aynı (1M).
   - Tur 2 modeli: 1M modeli.
   - Tur 3 modelleri: tohum 1 ve 2.
   - (`arama.py` `mevcut_hazirla`)

Toplam 25 ayar, 23 yeni eğitim. Tur 2, Tur 3 ve skor ile karar kuralı (H15) değişmedi. Durdurulan c00 eğitimi kullanılmıyor.

## Sonuç: Düzeltme 14, F deneyi (2026-10-19 03:55)

3 koşu bitti (F1 = `zemin_v3` + eğitimde 30 s). Kural `h14_karar.py` ile uygulandı. Ölçülen, ortalama ± sapma:

| | B1 | D1 | F1 |
|---|---|---|---|
| RL başarı | 56.9 ± 10.9 | 24.8 ± 4.6 | 35.6 ± 14.2 |
| RL başarılı iniş süresi (s) | 15.1 ± 0.5 | 12.2 ± 1.7 | 16.7 ± 2.2 |
| RL güvensiz | 18.6 ± 10.3 | 60.2 ± 16.1 | 14.1 ± 15.5 |
| RL süre doldu | 24.5 ± 16.3 | 15.0 ± 20.1 | 50.3 ± 27.0 |
| RL + kalkan başarı | 66.7 ± 13.1 | 53.6 ± 18.3 | 40.3 ± 20.4 |

- **Karar: `zemin_v3` + eğitimde 30 s benimsenmez.** H14a ve H14b tutmadı, H14c tuttu.
- **Ödül düzeltmesi çöküşün yönünü değiştirdi:** D dümdüz alçalıyordu, F1 süre doldurmaya kaydı.
- **Tanımlayıcı:** taramanın Tur 1'inde `zemin_v3` 90 s ile de yavaş (c18, 400k: kalkanla %41.9, süre doldu %57.8). Yol/ağaç cezasını süre dolmasının altına indirmek, ajanı belirsiz durumda beklemeye itiyor (_tahmin).

## Düzeltme 18 (2026-10-19 17:30): birleşim turu ve 2M — eğitimlerden önce

**Kullanıcı kararı (Arda, 2026-10-19):** "Tamam, en iyi performansı yakalamak için kullanabildiğin kadar kullan." Bu cevap şu önerilere verildi: birleşim, 2M adım ve IMPALA. IMPALA için "evet demen yeterli" denmişti.
- Bu cevap K79 için de onay sayıldı.
- Arda itiraz ederse IMPALA çeşidi (k3) çıkarılır ve sonuçlardan ayrı tutulur.

**Gerekçe (ölçülen, tarama Tur 2 ve Tur 3 tohum 0):**
- En iyi iki ayar farklı yoldan geliyor:
  - c13: 30 s + kayarken alçal + kalkan eğitimde. Tur 2 skoru 91.8, val_b32'de 97.4, iniş 13.8 s.
  - c23: 90 s + adım −0.5 + alçal +1. Tur 2 skoru 87.6.
- Eğitim eğrileri 1M'de hâlâ hafifçe yükseliyor.
- Ön elemede IMPALA +3 puan doğruluk vermişti (Düzeltme 10).

**Taban (sonuçtan önce sabit):** gözlem turu (H16) bir çeşidi benimsediyse o çeşit, değilse taramanın Tur 3'ünde ortalama S'si en yüksek ayar.

**Çeşitler** (tabanın argümanları üzerine; tabanda zaten olan değişiklik düşer, `birlesim_tur.py`):

| Ad | Değişiklik |
|---|---|
| k1_hiz | + adım cezası −0.5 ve alçal +1 (c23'ün hız ödülü) |
| k2_odul | ödül değişir: `zemin_v3` ↔ `zemin_v1` |
| k3_impala | + IMPALA gövdesi |
| k4_90s_hiz | eğitimde 90 s + hız ödülü |

**Turlar:**
- K-A: 400k, val_b64 × 5.
- K-B: en iyi 2, 1M, val_b64 × 10.
- K-C: en iyisi 3 tohum, val_b32 × 10.
- K-D: final aday 2M'ye uzatılır. Final aday, H18 kabul ettiyse çeşit, değilse taban. Üç tohum kendi 1M modelinden `--resume`, `--steps 2000000` ile devam eder. Öğrenme oranı 2M programına göre 1.5e-4'ten 0'a iner.

**Kararlar (`birlesim_karar.py`):**
- **H18:** çeşit benimsenir. Kriterler H16 ile aynı: S ≥ taban + 5 (tohum çiftlerinin en az 2'sinde de), kalkanlı başarı ≥ taban − 3, süre ≤ taban + 0.5 s, kalkansız güvensiz ≤ taban + 5.
- **H18b:** 2M kullanılır, eğer ortalama S ≥ 1M + 3 ise ve üç tohumun en az 2'sinde S artıyorsa.

**Sıra:** tarama → gözlem turu → birleşim turu → Faz 7 (AirSim, 30 havada başlangıç). Faz 7'nin modeli birleşim turunun final adayıdır (`faz7_model.py`, en önce bu). Final IrYamim testi en sonda, Arda "koş" deyince.

**Not:** tarama Tur 3 sürerken Arda'nın isteğiyle AirSim'de en iyi modelin (c13 tohum 0) gösterimi yapılır: 4 havada rastgele iniş, GT ve v3. Bu bir ölçüm değildir, hiçbir karara girmez.

## Düzeltme 19 (2026-10-19 22:30): B2-s0'ı hızlandırma (ince ayar) — eğitimden önce

**Kullanıcı isteği (Arda):** "B2-s0'ı hızlandırabilir miyiz?"
- B2-s0 en yüksek kalkanlı başarıya sahip tek model: %76.9. Ama yavaş: 17.4 s.
- Kayarken alçal eklenemez: eylem uzayı 10'dan 18'e çıkar, çıkış katmanı değişir.
- PX4'ün alçalma hızı sınırı (2 m/s) değişmez.

**Yöntem:** B2-s0'ın 1M modelinden, B2'nin ayarlarıyla (`zemin_v1` + aynalama), +500k adım ince ayar.
- `--resume`, `--steps 1500000`. Öğrenme oranı 1e-4'ten 0'a iner.
- Tek tohum, çünkü B2-s0 tek bir model.

| Ad | Ek |
|---|---|
| h1_hiz | adım −0.5, alçal +1 (90 s) |
| h2_hiz_45s | hız ödülü, eğitimde 45 s |
| h3_hiz_kalkan | hız ödülü, kalkan eğitimde (10 m) |

**Değerlendirme:** val_b32 × 10 = 320 deneme, tam.

**Karar (H19, `b2hiz_karar.py`):** çeşit kabul edilir, eğer şu üçü de tutarsa:
- RL + kalkan süresi ≤ 17.4 − 1.5 = 15.9 s.
- RL + kalkan başarısı ≥ 76.9 − 3 = %73.9.
- Kalkansız güvensiz iniş ≤ B2-s0 + 5.

Birden çok çeşit kabul edilirse skoru en yüksek olan "hızlandırılmış B2" olur. Bu tek tohumluk bir sonuçtur. Ana karşılaştırmalar 3 tohumla kalır.

**Sıra:** tarama → B2 hızlandırma → gözlem turu → birleşim turu → Faz 7.
- `kararla.py` içe aktarılınca artık çıktı vermiyor (`main` koruması).
- Davranış değişmedi.

## Sonuç: Düzeltme 15, tarama (2026-10-20 16:45)

Üç tur bitti:
- Tur 1: 25 ayar, 400k adım, val_b64 × 5.
- Tur 2: ilk 4 ayar, 1M adım, val_b64 × 10.
- Tur 3: ilk 2 ayar × 3 tohum, val_b32 × 10.

Kural `kararla.py` ile uygulandı. Tam tablo `tools/rl_inis/arama/ozet.md`, günlük `tools/rl_inis/arama/arama.log`.

**Kesinti:** 2026-10-20 00:31'de bilgisayar uyudu ("Application API"). c23'ün tohum 1 ve 2'si 600k kayıt noktasından
16:01'de sürdü. Ayarlar ve listeler değişmedi.

**Tur 3** (ölçülen, val_b32, 320 deneme / koşu, 3 tohum ortalaması):

| Ayar | S (tohum 0, 1, 2) | Kalkan B | Kalkan T | RL B | RL güvensiz |
|---|---|---|---|---|---|
| c23 (`zemin_v1`, adım −0.5, alçal +1, 90 s) | **88.9** (87.7, 88.3, 90.7) | 72.5 | 16.6 s | 69.9 | 13.9 |
| c13 (`zemin_v3`, 30 s, kayarak alçal, kalkan eğitimde) | 87.3 (97.4, 93.4, 71.1) | 66.4 | 15.1 s | 66.4 | 10.4 |
| B1 (kıyas) | 76.7 | 66.7 | 16.6 s | 56.9 | 18.6 |

**Tahminler** (aday: ortalama S'si en yüksek ayar, c23):
- **H15a tutmadı.** Ortalama S +12.2 puan (gereken +5), ama tohum çiftlerinden yalnız birinde ≥ +5 (gereken 2).
- **H15b tuttu.** Kalkanlı başarı 72.5 ≥ 63.7.
- **H15c tutmadı.** Kalkanlı süre 16.6 s > 13.5 s.
- **H15d tuttu.** Kalkansız güvensiz iniş 13.9 ≤ 23.6.

**Karar (ön kayıtlı kurala göre): c23, B1/B2-s0'ın yerini almaz.**

**Tanımlayıcı:**
- c23 tohumlara karşı kararlı (87.7–90.7). c13 dağınık (71.1–97.4).
- c23'te hız ödülü (adım −0.5, alçal +1) kalkansız başarıyı B1'e göre 13 puan artırdı (69.9 / 56.9) ve güvensiz inişi
  4.7 puan azalttı. Kalkanlı süre değişmedi (16.6 s).
- c13 daha hızlı (15.1 s) ama tohuma duyarlı.
- Hiçbir ayar 13.5 s'nin altına inmedi.
- Zincir sürüyor: B2 hızlandırma (Düzeltme 19) 16:49'da başladı. Gözlem turunun tabanı, `gozlem_tur.taban()`'ın kuralıyla
  Tur 3'te ortalama S'si en yüksek ayar, yani c23.

## Sonuç: Düzeltme 19, B2-s0 hızlandırma (2026-10-20 18:23)

Üç çeşit, B2-s0'ın 1M modelinden +500k adım (1.5M), tek tohum. Değerlendirme: val_b32 × 10, 320 deneme, 30 s.
Kural `b2hiz_karar.py` ile uygulandı. Ölçülen:

| Çeşit | S | Kalkan B | Kalkan T | RL B | RL T | RL güvensiz | RL süre doldu |
|---|---|---|---|---|---|---|---|
| B2-s0 (kıyas) | 91.6 | 76.9 | 17.4 s | 72.5 | 16.1 s | 8.8 | 18.8 |
| h1_hiz (adım −0.5, alçal +1, 90 s) | 75.7 | 63.4 | 17.3 s | 67.2 | 16.9 s | 2.8 | 30.0 |
| h2_hiz_45s (+ eğitimde 45 s) | 91.2 | **77.8** | 17.0 s | 66.9 | 15.2 s | 20.0 | 13.1 |
| h3_hiz_kalkan (+ kalkan eğitimde) | 89.8 | 72.8 | 16.8 s | 72.8 | 16.8 s | 4.1 | 23.1 |

**Şartlar** (B2-s0'a göre: kalkanlı T ≤ 15.9 s, kalkanlı B ≥ 73.9, kalkansız güvensiz ≤ 13.8):
- h1: süre tutmadı (17.3), başarı tutmadı (63.4), güvensiz tuttu (2.8).
- h2: süre tutmadı (17.0), başarı tuttu (77.8), güvensiz tutmadı (20.0).
- h3: süre tutmadı (16.8), başarı tutmadı (72.8), güvensiz tuttu (4.1).

**Karar (ön kayıtlı kurala göre): hiçbir çeşit H19'u sağlamadı. B2-s0 aynen kalır.**

**Tanımlayıcı:**
- Hız ödülüyle ince ayar kalkanlı süreyi en çok 0.6 s kısalttı (17.4 → 16.8 s). Gereken 1.5 s.
- h2 kalkanlı başarıda B2-s0'ı geçti (%77.8). Ama kalkansız güvensiz inişi %20.0'ye çıktı. Tek tohum.
- Gözlem turu (Düzeltme 16) "b2hiz bitti"yi gördü ve sıradaki adım olarak başlıyor.

## Yürütme notu (2026-10-20 19:31): gözlem turunda bellek taştı, eğitimler artık tek tek

**Olay (ölçülen, `dmesg` ve `journalctl`):**
- G-A'nın g3_risk ve g4_hepsi çeşitleri aynı anda eğitiliyordu. Ek gözlem kanallarıyla bir eğitim ~6.5 GB RSS ve ~2 GB
  takas tuttu (önceki eğitimler 3–4 GB).
- WSL'in 12 GB'ı doldu. Çekirdek bir eğitimi öldürdü (OOM), ardından Ubuntu dağıtımı yeniden başladı ve zincirin bütün
  süreçleri kapandı.
- Kalanlar: g1_hafiza ve g2_hedef'in sonuçları yazılmıştı. g3_risk 200k, g4_hepsi 100k kayıt noktasındaydı.

**Önlem (sonucu değiştirmez):**
- `arama.py`'ye `EN_COK` (aynı anda en çok kaç eğitim) eklendi, varsayılan 2 (eskisi gibi).
- `gozlem_tur.py` bunu 1 yapar. `birlesim_tur.py` de tabanı `--kanallar` içeriyorsa 1 yapar.
- Zincir 19:33'te yeniden başladı. g3 ve g4 kayıt noktalarından sürer (`--resume`). Öğrenme oranı programı korunur,
  rollout tamponu sıfırdan başlar (2026-10-17 yürütme notundaki gibi).
- Ayarlar, listeler, adım sayıları, tahminler ve karar kuralları değişmedi. Yalnız sıra değişti: G-A'nın kalan iki
  çeşidi aynı anda değil, art arda koşar.

## Düzeltme 20 (2026-10-20 22:30): birleşim turuna k5 — c13 tarifi + gözlem kanalı — eğitimlerden önce

**Kullanıcı kararı (Arda, 2026-10-20):** "Evet, k5'i ekle." Soru şuydu: risk kanalının başarısı c13'ün hızıyla birleşsin
mi?

**Gerekçe (ölçülen):**
- Gözlem turunun G-B'sinde `g3_risk` (c23 + risk kanalı, 1M, val_b64 × 10): S 91.9, kalkanlı %74.4, 16.4 s. Taban c23'ün
  Tur 2'si: S 87.6, %72.5, 16.3 s. Risk kanalı başarıyı artırdı, süreyi değiştirmedi.
- Taramanın en hızlı tarifi c13: `zemin_v3`, eğitimde 30 s, kayarken alçal, kalkan eğitimde. val_b32'de 3 tohum
  ortalaması 15.1 s (c23: 16.6 s).
- Birleşim turunun çeşitleri tabana göre kurulur. Taban c23 + bir kanal olursa k1_hiz ve k4_90s_hiz tabanla aynı çıkar
  ve düşer. Geriye hız için bir çeşit kalmaz.

**Değişiklik (`birlesim_tur.py`, `cesitler`):**
- **k5_c13_kanal:** `--reward zemin_v3 --max-t 30 --diag --shield-train-m 10` + tabanın `--kanallar` değeri.
- Yalnız taban bir gözlem kanalı içeriyorsa eklenir. İçermiyorsa k5, c13'ün kendisidir ve taramada zaten ölçüldü.
- K-A'da öbür çeşitlerle aynı koşullarla yarışır: 400k, tohum 0, val_b64 × 5. K-B, K-C, K-D ve **H18 / H18b
  değişmez.**
- Bu turun eğitimleri tek tek koşar (`arama.EN_COK = 1`, 19:31 yürütme notu).

**Tahmin (_tahmin; karar kuralı değil, tanımlayıcı):**
- **H20a:** k5, K-A'da tabandan en az 1.5 s hızlı iner (kalkanlı süre).
- **H20b:** k5'in K-A skoru, c13'ün Tur 1 skorundan (73.6) yüksek çıkar.

**Durum:** birleşim turu henüz başlamadı (gözlem turunu bekliyor). Orkestratör yeni kodla yeniden başlatıldı.

## Düzeltme 21 (2026-10-20 23:00): süre dolmadan yedek iniş — ölçümden önce

**Kullanıcı kararı (Arda, 2026-10-20):** "Yedek iniş kuralı." Soru şuydu: süre aşımları için hangisi ön kayıtla denensin
(yedek iniş kuralı, kalan süre kanalı, ikisi, hiçbiri)?

**Gerekçe (ölçülen):**
- Başarısızlığın çoğu süre aşımı. c13 s0: 320 denemede 74 süre aşımı, 23 güvensiz iniş.
- Süre aşımlarının çoğu daha uzun sürede inilebilir. B2-s0 + kalkan 30 s'de %76.9, 90 s'de %88.1.
- Kalkan, güvensiz inişi süre aşımına çeviriyor. B2-s0'a kalkan eklenince güvensiz 28 → 1, süre aşımı 60 → 73.
- Politikanın gözleminde saat yok. Çoğu model 90 s ile eğitildi, test 30 s.

**Kural (`eland_rl/yedek.py`, değerlendirmede bir yöntem; kalkan gibi, eğitim yok):**
- Kalan süre ≤ (kamera yüksekliği − 5 m) / 2 m/s + 2 s olunca politika geçersiz kılınır:
  - hedef kanalı (gözlemin 3. kanalı) merkezi güvenli diyorsa → alçal (9);
  - görüşte güvenli piksel varsa → en yakınına: model kayarken alçalabiliyorsa (`--diag`) kayarak alçal (10–17), değilse
    kay (1–8);
  - görüşte güvenli piksel yoksa → politikanın kendi eylemi.
- Güvensiz zemine zorla indirmez. Kalkan varsa bu kuraldan sonra yine uygulanır.
- Kullandığı bilgi: gözlem, kamera yüksekliği, bölümün saati. Ayrıcalıklı bilgi yok.
- Pay 2 s (komut gecikmesi, PX4 gecikmesi, ivmelenme). Ölçümden önce sabit.

**Kod (onaylı, varsayılan kapalı):**
- Yeni dosya `eland_rl/yedek.py` ve `test/test_yedek.py` (5 test).
- `evaluate.py`'ye `--yedek` ve `--yalniz-yedek` bayrakları: yeni yöntemler `rl_yedek` ve `rl_kalkan_yedek`.
- **Kapalıyken davranış bire bir eski** (ölçülen): B2-s0, val_b32 × 1. Eski kod ile yeni kodun CSV'si bayrak kapalıyken
  bit bit aynı. Bayrak açıkken `rl` ve `rl_kalkan` satırları yine aynı.

**Ölçüm:** var olan modeller, val_b32 × 10 (320 deneme), 30 s, argmax, nominal dinamik.
- Birincil: c13 ve c23 (taramanın Tur 3'ü, 3'er tohum). Tanımlayıcı: B2-s0.
- Yalnız yeni yöntemler koşar (`--yalniz-yedek`). Kıyas, aynı modelin eski CSV'sindeki `rl_kalkan` satırları. Aynı
  başlangıçlar, eşli kıyas.
- Betik `~/rl_inis/yedek/kos.sh`. Yanında bir eğitim koşarken tek tek ve en az 3 GB boş bellekle.

**Karar (H21, `~/rl_inis/yedek/h21_karar.py`):** her ayar için tohum başına dB = B(rl_kalkan_yedek) − B(rl_kalkan),
dU = güvensizdeki fark (yüzde puan).
- **H21a:** ortalama dB ≥ +3, ve tohumların en az 2'sinde dB ≥ +3.
- **H21b:** ortalama dU ≤ +2.
- **Yedek iniş benimsenir**, eğer H21a ve H21b c13'te **ve** c23'te tutarsa.
- Benimsenirse: final testte (Düzeltme 17) `rl_kalkan_yedek` ek yöntem olarak raporlanır. AirSim'e taşınması
  (`policy_node`) ayrı bir iş, Arda'nın onayıyla.

**Tahminler (_tahmin):**
- c13'te H21a tutar: süre aşımlarının en az dörtte biri başarıya döner.
- Başarılı inişlerin ortalama süresi 1–3 s uzar: yeni başarılar bölümün sonunda iner.
- Güvensiz iniş az artar: kural güvensiz zemine zorla indirmez, ama hedef kanalı her zaman doğru değil.

## Sonuç: Düzeltme 21, yedek iniş (2026-10-21 00:16)

7 değerlendirme bitti (val_b32 × 10, yalnız yeni yöntemler; kıyas aynı modelin eski `rl_kalkan` satırları). Kural
`h21_karar.py` ile uygulandı. Ölçülen, kalkanlı:

| Model | Başarı | Güvensiz | Süre aşımı | Süre | Süre aşımları neye döndü |
|---|---|---|---|---|---|
| c13 s0 | 69.7 → 70.0 | 7.2 → 7.2 | 23.1 → 22.8 | 13.8 → 13.8 s | 1 başarı, 73 yine süre aşımı |
| c13 s1 | 68.8 → 70.0 | 8.8 → 8.4 | 22.5 → 21.6 | 14.4 → 14.7 s | 3 başarı, 69 |
| c13 s2 | 60.6 → 61.2 | 15.3 → 14.7 | 24.1 → 24.1 | 16.9 → 17.1 s | 1 başarı, 1 güvensiz, 75 |
| c23 s0 | 71.6 → 73.1 | 2.2 → 2.2 | 26.2 → 24.7 | 16.0 → 16.3 s | 5 başarı, 79 |
| c23 s1 | 73.4 → 75.0 | 2.2 → 3.1 | 24.4 → 21.9 | 17.4 → 17.6 s | 6 başarı, 3 güvensiz, 69 |
| c23 s2 | 72.5 → 73.1 | 4.4 → 4.4 | 23.1 → 22.5 | 16.6 → 16.7 s | 3 başarı, 1 güvensiz, 70 |
| B2 s0 (tanımlayıcı) | 76.9 → **82.2** | 0.3 → 1.6 | 22.8 → 16.2 | 17.4 → 18.1 s | 17 başarı, 4 güvensiz, 52 |

- **H21a tutmadı:** ortalama dB c13'te +0.7 (+0.3, +1.2, +0.6), c23'te +1.2 (+1.6, +1.6, +0.6). Gereken +3.
- **H21b tuttu:** ortalama dU c13'te −0.3, c23'te +0.3.
- **Karar (ön kayıtlı kurala göre): yedek iniş benimsenmez.** Tahmin ("c13'te H21a tutar") tutmadı.
- B2 s0'da etki büyük (+5.3 puan), ama tek model ve tanımlayıcı.

**Teşhis (tanımlayıcı, `~/rl_inis/yedek/teshis.py`, `teshis2.py`; kalan süre aşımları, son 10 s):**
- Araç 5–10 m arasında, kalkanın alçalmayı engellediği bölgede takılı (bitiş yüksekliği medyan 8.8 m; c13'te 73/73).
- Görüşte güvenli piksel var (görüşün boş kaldığı adım payı medyan 0) ve merkez blok sığacak yer var.
- En yakın güvenli piksel çok yakın: c13 ~1.6 m, c23 ~0.6 m, B2 ~3 m (8.8 m'de 1 piksel ~0.16 m).
- **Araç salınıyor:** c13'te 40 adımda medyan 11 ters yöne dönüş, net yer değiştirme / yol 0.36. Aracın altındaki gerçek
  nokta neredeyse hiç hedef değil (adım payı medyan 0). Eğim yanılması değil, gerçekten üstüne geçemiyor.
- Yedek kural 26.3 s'de (medyan) tetikleniyor: 8.8 m'de gereken süre 3.9 s. Bu, salınımı çözmeye yetmiyor.
- **Yorum (_tahmin):** kalkan her adımda "en yakın güvenli pikseli" yeniden seçiyor. Araç hareket ettikçe bu piksel bir
  yandan öbür yana geçiyor (dar şerit, 0.24 s komut gecikmesi) ve araç kenarda zikzak çiziyor. Kalan süre aşımları bir
  saat sorunu değil, alçak irtifada "son metre" kontrol sorunu.

## Sonuç: Düzeltme 16, gözlem turu (2026-10-21 01:49)

Taban c23 (taramanın Tur 3'ünde ortalama S'si en yüksek ayar). Eğitimler 19:31 yürütme notundan sonra tek tek koştu.
Ölçülen:

| Aşama | Çeşit | S | Kalkan B | Kalkan T |
|---|---|---|---|---|
| G-A (400k, val_b64 × 5) | g3_risk | 81.5 | 72.2 | 17.9 s |
| | g2_hedef | 74.2 | 67.8 | 17.8 s |
| | g1_hafiza | 45.4 | 49.1 | 19.3 s |
| | g4_hepsi | 37.1 | 41.9 | 17.9 s |
| G-B (1M, val_b64 × 10) | g3_risk | 91.9 | 74.4 | 16.4 s |
| | g2_hedef | 53.2 | 47.5 | 16.5 s |
| G-C (val_b32 × 10) | g3_risk s0 / s1 / s2 | 92.3 / 87.1 / 64.3 | 73.8 / 73.1 / 57.8 | 16.3 / 16.4 / 17.9 s |
| | **g3_risk ortalama** | **81.2** | **68.2** | **16.9 s** |
| | taban c23 ortalama | 88.9 | 72.5 | 16.6 s |

- **H16a tutmadı** (hiçbir tohum çiftinde +5), **H16b tutmadı** (68.2 < 69.5), **H16c tuttu**, **H16d tuttu**.
- **Karar (ön kayıtlı kurala göre): `risk` kanalı benimsenmez.** Birleşim turunun tabanı c23 kalır; k5 (Düzeltme 20) bu
  yüzden düşer.
- **Tanımlayıcı:** tohum 0 ve 1'de risk kanalı tabanla aynı ya da üstünde, tohum 2 çöktü (S 64.3, süre aşımı %36.9).
  Hafıza ve üç kanal birden 400k'da zayıftı.

## Sonuç: Düzeltme 18, birleşim turu ve 2M (2026-10-21 09:17)

Taban c23 (H16 benimsenmedi). k1_hiz ve k4_90s_hiz tabanla aynı olduğu için, k5 taban kanal içermediği için düştü.
Ölçülen:

| Aşama | Çeşit | S | Kalkan B | Kalkan T | RL güvensiz | RL süre doldu |
|---|---|---|---|---|---|---|
| K-A (400k, val_b64 × 5) | k2_odul (`zemin_v3`) | 66.2 | 61.9 | 18.6 s | 15.3 | 23.4 |
| | k3_impala | 63.3 | 66.6 | 16.1 s | 73.8 | 0.0 |
| | taban | 81.2 | | | | |
| K-B (1M, val_b64 × 10) | k2_odul | 69.8 | 62.7 | 18.1 s | 3.9 | 32.7 |
| | k3_impala | 62.0 | 62.8 | 15.3 s | 75.3 | 0.0 |
| K-C (val_b32 × 10) | k2_odul s0 / s1 / s2 | 73.7 / 97.2 / 63.4 | 65.6 / 79.4 / 55.9 | 18.0 / 16.9 / 17.7 s | | |
| | **k2_odul ortalama** | **78.1** | **67.0** | **17.5 s** | 10.7 | |
| K-D (2M, val_b32 × 10) | taban c23 s0 / s1 / s2 | 82.3 / 85.3 / **103.1** | 67.8 / 71.9 / **84.4** | 17.2 / 17.0 / 17.3 s | 7.2 / 11.6 / 7.2 | 21.9 / 21.2 / 13.1 |
| | **2M ortalama** | **90.3** | **74.7** | **17.2 s** | 8.6 | |
| | 1M ortalama (kıyas) | 88.9 | 72.5 | 16.6 s | 13.9 | |

- **H18 (k2_odul): tutmadı.** a (S +5, tohumların 2'sinde) tutmadı, b ve c tutmadı, d tuttu. **Karar: benimsenmez.**
- **H18b (2M): tutmadı.** Ortalama S +1.4 (gereken +3); S yalnız tohum 2'de arttı. **Karar: 2M kullanılmaz.** Faz 7'nin
  modeli tabanın en iyi 1M tohumu (c23 s1, `faz7_model.py`).
- **Tanımlayıcı:**
  - IMPALA, kalkansız hâlinde düz alçalmaya çöktü (güvensiz %74–75, süre aşımı 0). Kalkanla %63–67.
  - c23 s2'nin 2M modeli şimdiye kadarki en iyi tek model: kalkanlı %84.4, 17.3 s, kalkansız güvensiz %7.2, S 103.1.
    Tek tohum; kural dışı, yalnız bilgi.
  - 2M, kalkansız güvensizi 13.9'dan 8.6'ya indirdi (3 tohum ortalaması).

## Düzeltme 22 (2026-10-21 14:30): kilitli kalkan — ölçümden önce

**Kullanıcı kararı (Arda, 2026-10-21):** "Evet, dene." Soru şuydu: kilitlenen kalkan (`rl_kalkan2`) ön kayıtla denensin
mi; eski kalkan değişmez.

**Gerekçe:** Düzeltme 21'in teşhisi. Kalan süre aşımlarında araç 5–10 m'de, güvenli zeminin 0.6–3 m yanında zikzak
çiziyor (c13 s0: 40 adımda medyan 11 ters dönüş). Kalkan her 0.25 s'de en yakın güvenli pikseli yeniden seçiyor; bu
piksel güvenli alanın kenarında.

**Kural (`eland_rl/kilitli_kalkan.py`, değerlendirmede bir yöntem, eğitim yok):**
- Kalkan 10 m'nin altında bir alçalmayı ilk kez durdurmak zorunda kalınca bir hedef seçer:
  - güvenli alanın kenarından en az min(0.5 m + merkez bloğun yarısı, alanın en derin noktası) içerideki pikseller
    arasından görüntü merkezine en yakını;
  - bu pikseli kamera pozuyla yerdeki bir noktaya çevirir (kameranın kullandığı ışın–düzlem izdüşümü).
- O noktaya uçar (yön sabit) ve araç noktanın 0.4 m yakınına gelene kadar politikayı geçersiz kılar.
- Vardığında merkez güvenliyse alçalır. Değilse ya da kilit 8 s'den eskiyse bırakır, bir sonraki durdurulan alçalmada
  yeniden seçer.
- Görüşte güvenli bir şey yoksa bekler (eski kalkan gibi).
- Kullandığı bilgi: gözlem, aracın kendi poz kestirimi, kamera modeli. Ayrıcalıklı bilgi yok.
- Sabitler ölçümden önce: 10 m, 0.5 m pay, 0.4 m varış, 8 s ömür.

**Kod (onaylı, varsayılan kapalı):**
- Yeni dosya `eland_rl/kilitli_kalkan.py` ve `test/test_kilitli_kalkan.py` (4 test: düz zeminde ve 1.2 m'lik şeritte
  iner, güvenli yer yoksa inmez).
- `evaluate.py`'ye `--kalkan2` ve `--yalniz-kalkan2` bayrakları, yeni yöntem `rl_kalkan2`.
- **Kapalıyken davranış bire bir eski** (ölçülen, B2-s0, val_b32 × 1): bayrak kapalıyken CSV bit bit aynı; açıkken eski
  yöntemlerin satırları aynı.
- Yapay sahnelerde (tanımlayıcı): geniş çimde ve 1.2 m şeritte eski kalkan da iniyor (yeni kalkan 1–2 s daha yavaş);
  0.8 m'lik şeritte eski kalkan asfalta indi, yenisi beklerken süre doldu.

**Ölçüm ve karar:** Düzeltme 21 ile aynı modeller, aynı liste, aynı eşli kıyas ve aynı kural.
- `~/rl_inis/yedek/kos2.sh` (Faz 7 bitince koşar), `~/rl_inis/yedek/h22_karar.py`.
- **H22a:** her ayar (c13, c23) için ortalama dB = B(rl_kalkan2) − B(rl_kalkan) ≥ +3, ve tohumların en az 2'sinde.
- **H22b:** ortalama dU ≤ +2.
- **Kilitli kalkan benimsenir**, eğer H22a ve H22b c13'te ve c23'te tutarsa. Benimsenirse final testte ek yöntem olarak
  raporlanır; AirSim'e (`policy_node`) taşınması ayrı iş, Arda'nın onayıyla.

**Tahminler (_tahmin):**
- c13 ve c23'te süre aşımlarının en az üçte biri başarıya döner, H22a tutar.
- Başarılı iniş süresi biraz uzar (kilitlenen hedefe gidiş).

## Sonuç: Düzeltme 22, kilitli kalkan (2026-10-21 18:20)

7 değerlendirme bitti (val_b32 × 10, yalnız `rl_kalkan2`; kıyas aynı modelin eski `rl_kalkan` satırları, eşli).
`h22_karar.py` ile uygulandı. Ölçülen, kalkanlı:

| Model | Başarı | Güvensiz | Süre aşımı | Süre | Süre aşımları neye döndü |
|---|---|---|---|---|---|
| c13 s0 | 69.7 → 82.8 | 7.2 → 1.2 | 23.1 → 15.9 | 13.8 → 16.0 s | 29 başarı, 45 yine süre aşımı |
| c13 s1 | 68.8 → 88.1 | 8.8 → 0.9 | 22.5 → 10.9 | 14.4 → 16.8 s | 43 başarı, 2 güvensiz, 27 |
| c13 s2 | 60.6 → **95.6** | 15.3 → 0.6 | 24.1 → 3.8 | 16.9 → 18.8 s | 67 başarı, 1 güvensiz, 9 |
| c23 s0 | 71.6 → 89.7 | 2.2 → 0.6 | 26.2 → 9.7 | 16.0 → 16.8 s | 54 başarı, 2 güvensiz, 28 |
| c23 s1 | 73.4 → 74.4 | 2.2 → 0.9 | 24.4 → 24.7 | 17.4 → 17.1 s | 18 başarı, 1 dışarı, 59 |
| c23 s2 | 72.5 → 82.5 | 4.4 → 0.0 | 23.1 → 17.5 | 16.6 → 16.7 s | 29 başarı, 45 |
| B2 s0 (tanımlayıcı) | 76.9 → 80.6 | 0.3 → 0.0 | 22.8 → 19.4 | 17.4 → 17.2 s | 27 başarı, 46 |

- **H22a tuttu:** ortalama dB c13'te +22.5 (+13.1, +19.4, +35.0), c23'te +9.7 (+18.1, +0.9, +10.0). Gereken +3, iki
  tohumda.
- **H22b tuttu:** ortalama dU c13'te −9.5, c23'te −2.4.
- **Karar (ön kayıtlı kurala göre): kilitli kalkan benimsenir.** Final testte (Düzeltme 17) `rl_kalkan2` ek yöntem olarak
  raporlanır. AirSim'e (`policy_node`) taşınması ayrı iş, Arda'nın onayıyla.
- **Tahminler tuttu:** süre aşımlarının üçte birinden fazlası başarıya döndü (c13 s2'de 76'nın 67'si); süre 0.1–2.2 s
  uzadı.

**Tanımlayıcı:**
- c13'ün 3 tohum ortalaması: kalkanlı %88.8, 17.2 s, güvensiz %0.9, S 101.1. Tohumlar arasındaki fark küçüldü (82.8–95.6;
  eski kalkanla 60.6–69.7). Zayıf tohum (s2) en iyisi oldu.
- c23 s1'de etki yok (+0.9): süre aşımlarının çoğu yine süre aşımı. Bu tohumun takıldığı yer başka (_tahmin).
- Düzeltme 21'in teşhisi doğrulandı: süre aşımlarının çoğu bir saat sorunu değil, alçak irtifada hedef seçme sorunuydu.

## Düzeltme 25 (2026-10-21 18:45): gimbal'lı kamera — değerlendirme, eğitim, AirSim — ölçümlerden önce

**Kullanıcı kararı (Arda, 2026-10-21):** "Hepsi." Soru şuydu: gimbal için ön kayıtlı deneyler (ortamda değerlendirme,
gimbal'la eğitim, AirSim'de RL + gimbal) sıraya eklensin mi? Arda'nın hipotezi: AirSim'deki yalpalama, kameranın eğimiyle
oluşan komut karmaşasından.

**Gerekçe (ölçülen, tanımlayıcı, `hiz2/gimbal_teshis.py`):** aynı model (c23 s1), aynı 320 başlangıç, eski kalkan;
gövdeye sabit kamera ↔ gimbal (eğitim yok): başarı %73.4 → %80.3, süre 17.4 → 16.8 s, güvensiz %2.2 → %0.6, adım başına
eylem değişimi 0.306 → 0.146, ters dönüş 0.080 → 0.019. Gerçek dronlarda kamera gimbal'da; MESSI fotoğrafları da öyle.

**Kod (onaylı, varsayılan kapalı):**
- `env.py`: `EnvConfig.gimbal` (False). Açıkken kamera düz durur, yalnız yönü araçla döner. `LandingEnv.kamera_pozu()`
  gözlemin kamera pozu. `evaluate.py`'nin `rl_kalkan2`'si hedefini bu pozla izdüşürür. Kapalıyken CSV bit bit aynı
  (ölçülen, c13 s0 val_b32 × 1, üç yöntem); `--env-json '{"gimbal": true}'` ile açılır.
- AirSim: `run_airsim.sh --gimbal` (kameranın yönelimi dünya ekseninde sabit: dik, kuzey üstte) ve `policy_node gimbal`
  (gözlem dik ve kuzeye bakan kameradan, eylemler görüntünün yönüyle). Gösterimde ölçülen: kamera ekseni dikeyden 0.0°,
  görüntünün üstü 0.0°, araç 20°'ye kadar eğilirken.

**25a — ortamda gimbal değerlendirmesi** (eğitim yok): 7 model (c13 s0–s2, c23 s0–s2, B2 s0), val_b32 × 10, yöntemler
rl, rl_kalkan, rl_kalkan2, `gimbal: true`. Kıyas: aynı modellerin gimbal'sız CSV'leri (eşli).
- **H25a** (c13 ve c23 için ayrı ayrı, 3 tohum ortalaması, yöntem `rl_kalkan2`):
  - başarı ≥ gimbal'sız − 1, ve
  - (süre ≤ gimbal'sız − 1.0 s **ya da** başarı ≥ gimbal'sız + 3), ve
  - güvensiz ≤ gimbal'sız + 2.
- İkisinde de tutarsa **gimbal benimsenir** (son sistemin kamera düzeni olarak).

**25b — gimbal'la eğitim:** c23 tarifi + `gimbal: true`, 3 tohum, 1M, val_b32 × 10 tam (gimbal'la), `rl_kalkan2` dahil.
Yanal hız turuyla aynı kuyrukta (`hiz2_tur.py`, aynı anda en çok 2 eğitim).
- **H25b** (3 tohum ortalaması, `rl_kalkan2`, kıyas 25a'daki c23'ün gimbal'la değerlendirmesi): başarı ≥ kıyas + 3,
  **ya da** (süre ≤ kıyas − 1.0 s ve başarı ≥ kıyas − 1); ve güvensiz ≤ kıyas + 2. Tutarsa gimbal'la eğitim benimsenir.

**25c — AirSim'de RL + gimbal:** Faz 7'nin 30 havada başlangıcı, c23 s1, AirSim etiketi, kalkan 10 (`policy_node`'un eski
kalkanı), `--gimbal`. Kıyas: Faz 7'nin R-GT kolu (eşli).
- **H25c:** zemin kuralına uygun ≥ R-GT (24/30), SORA ≥ R-GT (11/30) ve süre medyanı ≤ R-GT + 1 s (17.7 s). Üçü tutarsa
  AirSim'de gimbal benimsenir.
- Tanımlayıcı: RL modu etkinken adım başına eylem değişimi ve ters dönüş (politika.csv, `rl_mod.log`'daki etkinleşme
  anından sonra).

**Sıra:** son 5 m hızlandırması (Düzeltme 23) → 25c (AirSim, eğitim yokken) → 25a (değerlendirme) → yanal hız ve 25b
eğitimleri.

**Tahminler (_tahmin):**
- 25a: gimbal kilitli kalkanla da süreyi ~0.5–1 s kısaltır; başarı benzer kalır.
- 25b: gimbal'la eğitilen model, gimbal'la değerlendirilen eski modelden 2–5 puan iyi.
- 25c: RL'nin AirSim'deki eylem değişimi azalır; zemin kuralı ve SORA benzer ya da biraz iyi.

## Düzeltme 23 (2026-10-21 15:45): RL modunda daha hızlı son iniş — ölçümden önce

**Kullanıcı kararı (Arda, 2026-10-21):** "İkisi de" (son 5 m hızlandırması ve yanal hız). Soru şuydu: iniş süresini
kısaltmak için hangisi ön kayıtla denensin?

**Gerekçe (kaynak kod ve _hesap):**
- RL modu 5 m'nin altında politikayı dinlemez, 0.7 m/s ile dikey iner. Son 5 m ~7.1 s (_hesap). AirSim'de ölçülen
  16–23 s'lik inişlerin üçte biri bu kısım.
- Alçalma hızı zaten PX4'ün sınırında (`MPC_Z_VEL_MAX_DN 2.0`). PX4 parametreleri değişmez.

**Değişiklik (onaylı, varsayılan kapalı):**
- `eland_rl_mode`: `hizli_son_irtifa_m` (varsayılan −1 = kapalı) ve `hizli_son_hiz_m_s` (2.0). Açıkken 5 m'den
  `hizli_son_irtifa_m`'ye kadar 2 m/s, altında yine 0.7 m/s. Kapalıyken tek hız, eskisi gibi.
- `run_airsim.sh` ve `inis_sina.sh`: `--hizli-son METRE`.
- Seçilen değer: **2 m.** Son 2 m 0.7 m/s ile iner. Son kısım ~7.1 s'den ~4.4 s'ye (_hesap).
- **Risk:** irtifa EKF'den, kalkış noktasına göre. Faz 7'de arazinin hedef bölgede kalkış noktasından ~15 m yüksek olduğu
  başlangıçlar görüldü. Arazi kalkıştan 2–5 m yüksekse temas 0.7 yerine 2 m/s'ye yakın olabilir. Bu yüzden temas hızı
  karar kuralında.

**Ölçüm:** AirSim, Faz 7'nin 30 havada başlangıcı (tohum 2026), aynı model (c23 s1), AirSim etiketi, kalkan 10 m,
`--hizli-son 2`. Kıyas: Faz 7'nin `f7_rl_k10_gt` kolu; aynı başlangıçlar, eşli. Faz 7 ve kilitli kalkan ölçümü bitince
koşar.

**Karar (H23, `~/rl_inis/hiz2/h23_karar.py`):** benimsenir, eğer üçü de tutarsa:
- **H23a:** her iki kolda da inen eşli koşularda iniş süresi farkının medyanı ≤ −2.0 s.
- **H23b:** temas hızı 1.0 m/s'yi aşan iniş sayısı kıyastan fazla değil.
- **H23c:** zemin kuralına uygun iniş (ortografik harita) kıyastan en çok 1 az.

**Tahmin (_tahmin):** medyan fark −2.5 s; temas hızı ortalaması değişmez.

## Düzeltme 24 (2026-10-21 15:45): yanal hız 1.5 ve 2.0 m/s — eğitimlerden önce

**Kullanıcı kararı:** Düzeltme 23'teki "İkisi de".

**Gerekçe:** c13 s0'ın 13.8 s'sinin ~10 s'si 25 m'den 5 m'ye düz iniş (2 m/s, PX4 sınırı); kalan ~3.8 s kayma ve bekleme
(_hesap). Kayma 1 m/s (makalenin değeri); PX4 daha fazlasına izin veriyor. Uzaktaki güvenli alanlara 30 s'de yetişmek
de kolaylaşır.

**Çeşitler** (c23 tarifi: `zemin_v1`, adım −0.5, alçal +1, eğitimde 90 s; `--env-json` ile `v_lateral`):
- **y15:** yanal 1.5 m/s. **y20:** yanal 2.0 m/s. Kayarken alçalma yok (c23'te de yok).
- 3'er tohum (0, 1, 2), 1M adım, val_b32 × 10 tam değerlendirme. Aynı anda en çok 2 eğitim.
- Betik `~/rl_inis/hiz2/hiz2_tur.py`; Düzeltme 23'ün AirSim ölçümü bitince başlar.

**Kıyas:** c23'ün Tur 3'ü (3 tohum): S 88.9, kalkanlı B 72.5, kalkanlı T 16.6 s, kalkansız güvensiz 13.9.

**Karar (H24, `~/rl_inis/hiz2/h24_karar.py`):** bir çeşit benimsenir, eğer 3 tohum ortalamasında üçü de tutarsa:
- **H24a:** kalkanlı süre ≤ 15.1 s (c23 − 1.5 s).
- **H24b:** kalkanlı başarı ≥ 69.5 (c23 − 3).
- **H24c:** kalkansız güvensiz ≤ 18.9 (c23 + 5).
- İkisi de tutarsa skoru (S) yüksek olan.

**Tahminler (_tahmin):**
- y15 süreyi ~1 s, y20 ~1.5 s kısaltır.
- Hız arttıkça "son metre" zikzakı artar (Düzeltme 21 teşhisi), kalkanlı başarı biraz düşebilir.

**AirSim'e taşıma (ayrı iş):** `policy_node` yanal hızı bir ROS parametresinden alıyor (`v_lateral`, varsayılan 1.0),
`args.json`'dan değil. Benimsenen bir çeşit AirSim'de aynı hızla koşulmalı.

## Yürütme notu (2026-10-22 00:30): Düzeltme 23 ve 24'ün ilk koşusu geçersiz

**Olay (ölçülen, günlüklerden):**
- Düzeltme 23'ün AirSim ölçümü: 30 başlangıcın hiçbiri başlamadı. `run_airsim.sh`, `--hizli-son 2`'yi tamsayı ROS
  parametresi olarak verdi; `rl_landing_mode` double bekliyor ve başlarken çöktü. Bayrak kapalıyken yapılan doğrulama
  koşusu ise iniyor (dokunuş 0.70 m/s, "faster down" satırı yok).
- Düzeltme 24'ün eğitimleri "hata 2" ile düştü (54 deneme): zincir betiği derleme için ROS kurulumunu yükledi, kurulumdaki
  eski `eland_rl` PYTHONPATH'te öne geçti ve eski `train.py` yeni seçenekleri tanımadı. Hiçbir eğitim koşmadı.

**Düzeltme:** `run_airsim.sh` parametreyi `%.2f` ile verir; eğitimler temiz ortamda başlar (`env -u PYTHONPATH`, yalnız
`ortam.sh`). Yeni sıra `~/rl_inis/hiz2/sira2.sh`: gimbal adımı (25c, 25a) → Düzeltme 23 yeniden → eğitimler (24, 25b).
Ayarlar, tahminler ve karar kuralları değişmedi.

## Sonuç: Düzeltme 25c, AirSim'de RL + gimbal (2026-10-22 01:42)

30 havada başlangıç (Faz 7'nin listesi), c23 s1, AirSim etiketi, eski kalkan 10 m, `--gimbal`. Kıyas Faz 7'nin R-GT kolu.
`h25c_karar.py` ile. Ölçülen:

| | R-GT (gimbal yok) | R-GT + gimbal |
|---|---|---|
| İndi | 29/30 | 30/30 |
| Zemin kuralına uygun | 24 | 23 |
| SORA uygun | 11 | 10 |
| Süre medyanı | 16.7 s | 15.9 s |
| RL etkinken eylem değişimi / ters dönüş (adım başına) | 0.111 / 0.012 | 0.128 / 0.014 |

- **H25c tutmadı:** zemin 23 < 24, SORA 10 < 11 (süre şartı tuttu). **Karar: AirSim'de gimbal benimsenmez.**
- **Tanımlayıcı:** farklar 30 denemede birer iniş, gürültü düzeyinde. AirSim'de RL'nin eylem değişimi zaten düşük (0.11/adım;
  eğitim ortamında 0.31) ve gimbal onu düşürmedi. AirSim'deki yalpalamanın kaynağı kamera eğimi değil gibi (_tahmin).
- Koşu 9'da AirSim dondu; `ros2 topic pub -1` 29 dk takıldı (`run_airsim.sh` 10 s zaman aşımıyla düzeltildi). 5 koşu
  yeniden denendi.

## Sonuç: Düzeltme 25a, ortamda gimbal (2026-10-22 02:00)

7 model, val_b32 × 10, eğitim yok; kıyas aynı modellerin gimbal'sız sonuçları (eşli). `h25a_karar.py` ile. Ölçülen, 3 tohum
ortalaması:

| Ayar, yöntem | Başarı | Süre | Güvensiz |
|---|---|---|---|
| c13, rl_kalkan2 | 88.9 → **92.5** | 17.2 → **14.1 s** | 0.9 → 1.8 |
| c13, rl (= rl_kalkan; kalkan eğitimde) | 66.4 → 77.6 | 15.1 → 14.2 s | 10.4 → 5.7 |
| c23, rl_kalkan2 | 82.2 → **92.1** | 16.9 → 15.9 s | 0.5 → 0.2 |
| c23, rl_kalkan | 72.5 → 81.4 | 16.6 → 16.3 s | 2.9 → 0.5 |
| c23, rl | 69.9 → 71.1 | 15.5 → 15.3 s | 13.9 → 15.6 |
| B2 s0, rl_kalkan2 (tanımlayıcı) | 80.6 → 86.2 | 17.2 → 16.2 s | 0.0 → 0.0 |

- **H25a iki ayarda da tuttu** (başarı korunuyor, süre ya da başarı kazancı var, güvensiz +2 içinde). **Karar: gimbal
  benimsenir** (son sistemin kamera düzeni).
- Tahmin ("süre ~0.5–1 s kısalır, başarı benzer") fazlasıyla aşıldı: c13'te süre 3.1 s kısaldı, başarı +3.6.
- **Çelişki notu:** ortamda büyük kazanç, AirSim'de (25c, eski kalkan, c23 s1) yok. Olası sebepler (_tahmin): AirSim'de
  kilitli kalkan yok; c23 s1 kilitli kalkandan da yararlanmayan tohum; AirSim dinamiği farklı. Yeni bir AirSim ölçümü
  kilitli kalkan `policy_node`'a taşındıktan sonra anlamlı olur (Arda'nın onayı).

## Sonuç: Düzeltme 23, hızlı son iniş (2026-10-22 02:54)

Yeniden koşu (ilk koşu geçersiz, 22.10 00:30 yürütme notu). 30 havada başlangıç, c23 s1, AirSim etiketi, kalkan 10,
`--hizli-son 2`; 29 koşuda RL modu hızlı aşamayı yazdı. Kıyas Faz 7'nin R-GT kolu (eşli). `h23_karar.py` ile. Ölçülen:

| | R-GT (0.7 m/s) | Hızlı son (2 m'ye kadar 2 m/s) |
|---|---|---|
| İndi | 29/30 | 30/30 |
| Zemin kuralına uygun | 24 | 25 |
| SORA uygun | 11 | 11 |
| Süre medyanı | 16.7 s | 13.4 s (eşli fark medyanı −3.2 s) |
| Temas hızı ort. / en çok | 0.71 / 0.73 m/s | 1.10 / 2.28 m/s |
| Temas > 1.0 m/s | 0 | 14 |

- **H23a tuttu** (−3.2 s), **H23b tutmadı** (14 > 0), **H23c tuttu** (25 ≥ 23). **Karar: hızlı son iniş benimsenmez.**
- **Tanımlayıcı:** kalkış seviyesindeki düz zeminde bile temaslar 1.0–1.4 m/s; 2 m, 2 m/s'den 0.7 m/s'ye yavaşlamaya
  yetmiyor. Zeminin kalkıştan yüksek olduğu koşularda 2.0–2.3 m/s (bir koşu çatı köşesine, 9.9 m'de). Daha yüksek bir geçiş
  irtifası (3.5–4 m) ya da gerçek bir mesafe sensörü ayrı bir ön kayıt ister.

## Düzeltme 26 (2026-10-22 20:45): c13 tarifiyle gimbal'lı eğitim (g13) — eğitimlerden önce

**Kullanıcı sorusu (Arda, 2026-10-22):** "son gimballı eğitimleri ortalama olarak hızlandırabilir miyiz".

**Gerekçe (ölçülen, tanımlayıcı; val_b32 × 10 özetlerindeki eylem payları):**
- 25b'nin g modelleri c23 tarifinde. Her adımda ya kayar ya alçalır. Adımların ~%40'ı yalnız kayma. Kilitli kalkanla
  süre 15.9 ve 16.0 s (g s0, s1).
- 20–30 m'den (ort. 25 m) 5 m'ye 2 m/s ile düz iniş ~10 s (_hesap). c23'te alçalma payı ~0.6 × 16 s ≈ 9.6 s. Kalan
  ~6 s yalnız kayma.
- c13 tarifi kayarken alçalabiliyor (Düzeltme 13). Gimbal'la değerlendirmede, kilitli kalkanla %92.5, 14.15 s (25a).
- 25b ara sonucu (2 tohum): gimbal'la eğitim yalın RL'yi iyileştirdi (c23: %71.1 → %87.0, güvensiz %15.6 → %3.8).
  c13 tarifi bu kazancı henüz almadı.

**Çeşit:** g13 = c13 tarifi (`zemin_v3`, eğitimde 30 s, kayarken alçal, eğitimde kalkan 10 m) + `--env-json
'{"gimbal": true}'`. 3 tohum (0, 1, 2), 1M adım, val_b32 × 10 tam değerlendirme. Değerlendirme gimbal'la yapılır ve
`rl_kalkan2` içerir. Aynı anda en çok 2 eğitim. Betik `~/rl_inis/g13/g13_tur.py`. 25b'nin eğitimleri ve Sefa için
PX4 sınaması (`px4_sina.sh` × 3) bitince başlar.

**Kıyas:** 25a'daki c13'ün gimbal'la değerlendirmesi (c13 s0–s2, `rl_kalkan2`, ölçülen): başarı 92.50, süre 14.15 s,
güvensiz 1.77.

**Karar (H26, `~/rl_inis/g13/h26_karar.py`, 3 tohum ortalaması, `rl_kalkan2`):**
- (süre ≤ kıyas − 1.0 s **ve** başarı ≥ kıyas − 1) **ya da** başarı ≥ kıyas + 3; **ve**
- güvensiz ≤ kıyas + 2.
- Tutarsa g13 son aday olur (c13 + kilitli kalkan + gimbal yerine).
- Tanımlayıcı: yalın RL ve eski kalkan da raporlanır. 25b'nin g modelleri de aynı tabloda gösterilir.

**Tahminler (_tahmin):**
- Kilitli kalkanla süre 13–13.5 s, başarı %92–94.
- Yalın RL başarısı c13'ün gimbal'la değerlendirmesinden (%77.6) belirgin yüksek. Bunun nedeni 25b'deki kazancın
  tekrarlanması.
- c13 tohuma duyarlı (Düzeltme 15). Bir tohumun düşük çıkması ortalamayı çekebilir.

## Yürütme notu (2026-10-22 19:35): bilgisayar uykuya geçti, tur yeniden başlatıldı

Bilgisayar 22.10 08:49'da uykuya geçti (Windows kaydı: "Application API"). 14:40'ta uyandı, 16:04–16:13 arası bir kez
daha uyudu. WSL 19:34'te yeniden başladı. y15 ve y20'nin 6 eğitimi ve değerlendirmesi uykudan önce bitmişti. g s0 ve g s1
1M'e ulaşmıştı ama değerlendirilmemişti. g s2 08:42'de başlamış, ara kayıt bırakmamıştı. `hiz2_tur.py` aynı işlerle
yeniden başlatıldı (temiz ortam: `env -u PYTHONPATH -u AMENT_PREFIX_PATH` + `ortam.sh`). Biten işler atlandı, g s2
sıfırdan eğitildi. Hiçbir karar kuralı ve ayar değişmedi.

## Sonuç: Düzeltme 24, yanal hız 1.5 ve 2.0 m/s (2026-10-22 21:02)

3 tohum ortalaması, val_b32 × 10, `h24_karar.py` ile. Ölçülen:

| | c23 (kıyas) | y15 | y20 |
|---|---|---|---|
| S (tohumlar) | 88.9 (87.7, 88.3, 90.7) | 55.2 (94.0, 22.3, 49.3) | 40.3 (48.1, 69.7, 3.1) |
| Kalkanlı başarı | 72.5 | 51.1 | 43.4 |
| Kalkanlı süre | 16.6 s | 17.4 s | 18.5 s |
| Kalkansız başarı | 69.9 | 51.7 | 45.9 |
| Kalkansız güvensiz | 13.9 | 10.9 | 7.1 |

- İki çeşitte de **H24a tutmadı** (süre kısalmadı, uzadı), **H24b tutmadı**, H24c tuttu.
  **Karar: yanal hız 1.0 m/s kalır.**
- Tahmin ("y15 ~1 s, y20 ~1.5 s kısaltır") tutmadı. Daha hızlı kaymada politikalar tohuma çok duyarlı: aynı tarif S 3.1 ile
  94.0 arasında. Süre aşımı bazı tohumlarda %64–70. Hızlanma, kararsız öğrenmeyle yitiyor (_tahmin).

## Sonuç: Düzeltme 25b, gimbal'la eğitim (2026-10-22 21:02)

c23 tarifi + `gimbal: true`, 3 tohum, 1M, val_b32 × 10 gimbal'la. Kıyas: 25a'daki c23'ün gimbal'la değerlendirmesi.
`h25b_karar.py` ile. Ölçülen:

| Yöntem | c23 gimbal'la değerlendirme | g (gimbal'la eğitim; tohumlar) |
|---|---|---|
| Yalın RL: başarı / süre / güvensiz | 71.1 / 15.3 s / 15.6 | 84.3 (85.6, 88.4, 78.8) / 15.5 s / 7.3 |
| Eski kalkan | 81.4 / 16.3 s / 0.5 | 88.4 (88.8, 89.7, 86.9) / 16.3 s / 0.5 |
| Kilitli kalkan (karar) | 92.1 / 15.9 s / 0.2 | 91.0 (89.4, 92.2, 91.6) / 15.8 s / 0.5 |

- **H25b tutmadı** (kilitli kalkanla başarı −1.1, süre −0.1 s). **Karar: gimbal'la eğitim (c23 tarifi) benimsenmez.**
- **Tanımlayıcı:** gimbal'la eğitim yalın RL'yi +13.2 puan iyileştirdi ve güvensizi yarıya indirdi. Eski kalkanla +7.0.
  Kilitli kalkan bu kazancı zaten sağlıyor. Arama skoru S (eski kalkan + yalın RL) 113.4 (114.0, 116.6, 109.7). Bu,
  şimdiye kadarki en yüksek değer (c23: 88.9).
- **AirSim için not:** `policy_node`'da kilitli kalkan yok, eski kalkan var. Kilitli kalkan taşınana kadar AirSim'de g
  modelleri daha iyi aday (eski kalkanla 88.4 ↔ 81.4, ortamda).
- Tahmin ("2–5 puan iyi") kilitli kalkanla tutmadı, eski kalkanla aşıldı.
- Süre aynı kaldı (15.8 s). Sebebi c23 tarifinde kayarken alçalma olmaması. Bunu Düzeltme 26 (g13) sınıyor.

## Sonuç: Düzeltme 26, c13 tarifiyle gimbal'lı eğitim (2026-10-23 00:34)

g13 = c13 tarifi + `gimbal: true`, 3 tohum, 1M, val_b32 × 10 gimbal'la. Kıyas: 25a'daki c13'ün gimbal'la değerlendirmesi.
`h26_karar.py` ile. Ölçülen (kilitli kalkan; tohumlar 0, 1, 2):

| | c13 gimbal'la değerlendirme | g13 (gimbal'la eğitim) | g (25b, c23 tarifi) |
|---|---|---|---|
| Kilitli kalkan: başarı | 92.5 (88.1, 93.4, 95.9) | 87.7 (86.9, **99.1**, 77.2) | 91.0 (89.4, 92.2, 91.6) |
| Kilitli kalkan: süre | 14.15 s (13.1, 14.0, 15.4) | 14.96 s (14.4, **13.2**, 17.4) | 15.8 s |
| Kilitli kalkan: güvensiz | 1.77 | 1.35 | 0.5 |
| Yalın RL: başarı / güvensiz | 77.6 / 5.7 | 81.0 (81.2, 90.6, 71.2) / 3.1 | 84.3 / 7.3 |

- **H26 tutmadı** (başarı −4.8, süre +0.8 s). **Karar: c13 tarifiyle gimbal'lı eğitim benimsenmez.** Son aday
  c13 + kilitli kalkan + gimbal (değerlendirmede) olarak kalır.
- Tahmin ("13–13.5 s, %92–94") ortalamada tutmadı. Yalnız s1'de tuttu: %99.1, 13.2 s, güvensiz %0.6, S 130.4. Bu,
  şimdiye kadar val_b32'de ölçülen en iyi tek model.
- **Tanımlayıcı:** tohumlar arası fark çok büyük (77.2–99.1). c13 tarifinin tohuma duyarlılığı (Düzeltme 15) gimbal'la
  azalmadı, arttı. s2 süre aşımında %24.4.
- **Seçim yanlılığı notu:** s1'i val_b32 sonucuna bakarak seçmek iyimser bir tahmin verir. s1 ancak val_b32 dışında bir
  ölçümle (ayrı sahneler ya da AirSim) doğrulanırsa aday olabilir. Bu ayrı bir ön kayıt ister.

## Düzeltme 27 (2026-10-25): derinlik girdisi karşılaştırması — eğitimlerden önce

**Kullanıcı isteği (Arda, 2026-10-25):** "Makaledeki gibi bir derinlik verisi girince sonuçlarımız daha mı kötü çıkıyor
... şuanki durum, 0 derinlik girdisi ve Depth Anything ile eğitim, 3 durumu karşılaştırabilir misin."

**Gerekçe:** Bugünkü "düz zemin derinliği" kamera-zemin uzaklığıdır. Zemin düz kabul edildiği için pratikte irtifayı
taşır; gimbal'la tek renktir. Gerçek derinlik yok. Depth Anything bir kez denendi (Düzeltme 7), ama eski ödülle, eski
kuralla ve tek tohumla. O sonuç bugünkü sisteme taşınamaz.

**Veri kısıtı (ölçülen):** Depth Anything RGB fotoğraf ister. `train_b`'nin 600 karesinin 133'ünün, `val_b32`'nin
32 karesinin 14'ünün fotoğrafı var. Düzeltme 7'nin yükseklik haritaları bu 133 + 40 kare (0004 uçuşu) için hazır.
Adil kıyas için üç kol da aynı 133 fotoğraflı karede yeniden eğitilir. Bu yüzden mutlak sayılar 600 kareyle eğitilen
son adaydan düşük olabilir; kıyas kollar arasıdır.

**Kollar** (c13 tarifi: `zemin_v3`, eğitimde 30 s, kayarken alçal, eğitimde kalkan 10 m; 1M adım; tohum 0, 1, 2):
- **A_irtifa:** bugünkü düz zemin derinliği.
- **B_yok:** derinlik kanalı sıfır (`depth_norm_m` 1e9; kanal 0.000, ölçülen).
- **C_da:** Depth Anything V2 Small göreli yüksekliği (`--depth-mode elev`). Düzeltme 7'deki haritalar, yeni indirme yok.

**Değerlendirme:** 0004 uçuşunun 40 karesi (`test_foto.txt`, eğitimde yok) × 10 başlangıç = 400 deneme. Koşullar 30 s,
nominal dinamik, argmax ve gimbal. Yöntemler: `rl` ve `rl_kalkan2`. **Her deneme yeni bir ortamla koşulur.** 25.10'da
paylaşılan ortamda aynı başlangıcın farklı süre verdiği görüldü; ayrı bir oturum bunu inceliyor. Kod donmuş kopyadan
çalışır (`~/rl_inis/derinlik2/kod`, 0775798). Betikler: `~/rl_inis/derinlik2/{tur,degerlendir,h27_karar}.py`.

**Karar (H27, 3 tohum ortalaması, `rl_kalkan2`, kıyas A_irtifa):**
- **H27b:** B_yok başarı ≥ A − 2 ve süre ≤ A + 0.5 s ise "irtifa kanalı gerekmiyor"; yoksa "gerekli".
- **H27c:** C_da (başarı ≥ A + 3 **ya da** (süre ≤ A − 1.0 s ve başarı ≥ A − 1)) **ve** güvensiz ≤ A + 2 ise "Depth
  Anything eklemeye değer" (sahada çalıştırılması ayrı bir iş); yoksa "eklenmez".
- Tanımlayıcı: yalın RL de raporlanır.

**Tahminler (_tahmin):**
- B, A'dan 2–5 puan düşük. İrtifayı bilmeyen politika alçalma zamanlamasını maskenin ölçeğinden çıkarmak zorunda.
- C, A'ya yakın ya da güvensizde kötü. Göreli yükseklik ağaç/çimde zayıf (AUC 0.82) ve irtifa bilgisi kayboluyor.

## Sonuç: Düzeltme 27, derinlik girdisi karşılaştırması (2026-10-25 08:42)

133 fotoğraflı karede eğitim, 0004 uçuşunun 40 karesinde × 10 başlangıç (400 iniş). Her deneme yeni bir ortamla
koşuldu. Ölçülen (3 tohum; tohumlar 0, 1, 2):

| Kol | Kilitli kalkan: başarı (tohumlar) | Süre | Güvensiz | Yalın RL: başarı | Yalın RL güvensiz |
|---|---|---|---|---|---|
| A_irtifa (bugünkü) | 57.3 (95.0, 36.8, 40.2) | 17.77 s | 6.6 | 54.7 | 7.2 |
| B_yok | 84.9 (61.2, 95.5, 98.0) | 16.48 s | 4.1 | 70.7 | 7.2 |
| C_da (Depth Anything) | **93.7** (89.8, 93.8, 97.5) | **15.56 s** | 4.3 | 78.6 | 10.2 |

- **H27b tuttu** (B ≥ A − 2, süre ≤ A + 0.5 s): irtifa kanalı gerekmiyor.
- **H27c tuttu** (C başarı +36.4, süre −2.2 s, güvensiz −2.3): Depth Anything eklemeye değer.
- **Dikkat (tanımlayıcı):** A'nın ortalamasını iki çöken tohum (36.8, 40.2) düşürüyor. Her kolun en iyi tohumu
  benzer (95.0 / 98.0 / 97.5). C'nin asıl farkı **kararlılık**: üç tohumun üçü de %89.8 ve üstünde. Yalın RL'de C'nin
  güvensizi daha yüksek (10.2 ↔ 7.2), ama kilitli kalkan bunu kapatıyor.
- Tahminler tutmadı: B, A'dan kötü değil; C, A'dan iyi.
- **Sınırlar:** 133 karelik küçük eğitim seti, tek test uçuşu (0004), 3 tohum. Son aday 600 kareyle eğitildi; Depth
  Anything o 600 karenin 467'sinde kullanılamaz (RGB fotoğraf yok). Sahada kullanmak için Depth Anything'in AirSim'de
  kamera görüntüsü üzerinde çalışması gerekir; bu ayrı bir iş ve Arda'nın kararı.

## Düzeltme 28 (2026-10-25): v4 verisiyle yeni eğitim — eğitimlerden önce

**Kullanıcı isteği (Arda, 2026-10-25):** yeni veri paketi (`veri_v4.zip`), segmentasyon modeli v4 ve "yürürlükteki
plan ile eğitimlere başla". Plan: [`../rl_airsim/YENI_VERI_PLANI.md`](../rl_airsim/YENI_VERI_PLANI.md).

**Veri (ölçülen):** v4'ün FloodNet ve MESSI kareleri, en az 60 × 45 m olanlar; masks8 → RL sınıfları (yol ve belirsizler
temkinli; tablo plan belgesinde); 8 cm/piksel. Eğitim 1810 (FloodNet 1445, MESSI 365), doğrulama 175 (FloodNet 60,
MESSI 115). TU Graz ve VDD ölçek yüzünden dışarıda. Her sahne için Depth Anything V2 Small yüksekliği.

**Kol:** v4_da = c13 tarifi (`zemin_v3`, eğitimde 30 s, kayarken alçal, eğitimde kalkan 10 m) + `--depth-mode elev`,
v4 eğitim sahneleri, **5 tohum** (0–4), 1M adım. Donmuş kod `~/rl_inis/v4/kod` (7ca8d7a). Betikler
`~/rl_inis/v4/{hazirla,da_v4,tur,degerlendir,h28_karar}.py`.

**Değerlendirme:** v4 doğrulama, 175 sahne × 5 başlangıç = 875 deneme. 30 s, nominal dinamik, argmax, gimbal.
Yöntemler `rl` ve `rl_kalkan2`. Her deneme yeni ortamla. Kıyaslar aynı sahnelerde:
- eski son aday c13 s0–s2 (600 MESSI karesi, düz zemin derinliği);
- Düzeltme 27'nin C_da s0–s2 (133 kare, Depth Anything).
Not: eski c13 bazı Agamim doğrulama uçuşlarını eğitimde görmüş olabilir; bu, kıyası eski modelin lehine çevirir.

**Karar (H28, `rl_kalkan2`, bütün doğrulama):**
- **H28a:** v4_da (5 tohum ortalaması) eski c13'e (3 tohum) karşı: (başarı ≥ eski + 3 **ya da** (süre ≤ eski − 1.0 s
  ve başarı ≥ eski − 1)) **ve** güvensiz ≤ eski + 2.
- **H28b:** v4_da'nın en kötü tohumu ≥ %80.
- İkisi de tutarsa v4_da yeni son aday olur.
- Tanımlayıcı: kaynak başına (FloodNet, MESSI), yalın RL, Düzeltme 27 modelleri.

**Tahminler (_tahmin):**
- FloodNet'te eski c13 zayıf kalır (su ve sel sahnelerini hiç görmedi); v4_da belirgin iyi.
- MESSI'de v4_da eski c13'e yakın (eğitimin yalnız %20'si MESSI).
- 5 tohumun hepsi %80'in üstünde.

### Düzeltme 28b (2026-10-25 22:15, hiçbir sonuç görülmeden): dengeli eğitim seti

**Kullanıcı kararı (Arda):** "FloodNet'teki sınıf ağırlığını genel eğitimde dengeli olacak şekilde ayarla, FloodNet'in
hepsini kullanmaman daha iyi olabilir."

- Eğitim seti `train_denge.txt`: MESSI'nin 365 sahnesi + FloodNet eğitiminden rastgele 365 sahne (`random.Random(0)`).
  Toplam 730. Sınıf payları (ölçülen): çim 33.4, sert 8.3, bitki+yol 33.3, yapı 16.8, su 6.2, araç 1.2.
  Tam set (1810) çimde %50'nin üstündeydi.
- Tam setle başlayan v4_da s0, 369 bin adımda durduruldu ve `kos/v4_iptal/`'e taşındı; değerlendirilmez.
- Doğrulama seti, kollar, karar kuralı (H28) ve tahminler değişmedi.

## Sonuç: Düzeltme 28, v4 verisiyle yeni eğitim (2026-10-26 17:29)

Dengeli set (28b, 730 sahne), 5 tohum. Bilgisayar 26.10 gece kapandı; s2 300 bin adımlık ara kayıttan sürdürüldü
(`--resume`), s0 ve s1 tamdı. v4 doğrulama: 175 sahne × 5 = 875 iniş, her deneme yeni ortam. Ölçülen (kilitli kalkan):

| | Hepsi: başarı (tohumlar) | Süre | Güvensiz | FloodNet | MESSI |
|---|---|---|---|---|---|
| v4_da (yeni, 5 tohum) | 93.4 (95.2, 92.3, 91.3, 92.9, 95.3) | 13.68 s | 2.2 | 88.3 | 96.1 |
| eski c13 (3 tohum) | 94.2 (95.5, 95.1, 92.0) | 12.93 s | 1.3 | 88.2 | 97.3 |
| Düzeltme 27 C_da (3 tohum) | 91.5 (88.5, 93.3, 92.8) | 14.37 s | 2.7 | 83.9 | 95.5 |

Yalın RL: v4_da 84.0, eski c13 86.4, C_da 78.9.

- **H28a tutmadı** (başarı −0.8, süre +0.75 s). **H28b tuttu** (en kötü tohum 91.3). **Karar: v4_da son aday olmaz;
  eski c13 + kilitli kalkan + gimbal yerinde kalır.**
- **Tanımlayıcı:**
  - Yeni model çok kararlı: FloodNet'te beş tohum 87.7–88.7.
  - Eski model FloodNet'i hiç görmediği hâlde orada aynı başarıyı aldı (88.2). Politika güvenli alan kanalına
    dayanıyor ve bu kanal yeni sahnelere iyi genelleşiyor.
  - FloodNet'te iki model de ~%88'de kalıyor. Bu bir tavan gibi görünüyor; sebebi ayrıca incelenmeli (_tahmin: su
    ağırlıklı sahneler ya da 20–30 m'den ulaşılamayan güvenli alan).
  - MESSI'de eski model biraz önde. Eski model bazı Agamim doğrulama uçuşlarını eğitimde görmüş olabilir.
  - Daha büyük veri bu ölçümde politikayı iyileştirmedi. AirSim'deki asıl darboğaz algı (Faz 7: GT 24/30, v3 16/30).
- Tahminler: FloodNet'te eski c13'ün zayıf kalacağı tahmini tutmadı. MESSI'de yakın olacağı tahmini tuttu. 5 tohumun
  hepsinin %80 üstünde olacağı tahmini tuttu.

## Düzeltme 29 (2026-10-27): veri × derinlik × segmentasyon × kalkan tam karşılaştırması — ölçümlerden önce

**Kullanıcı isteği (Arda, 2026-10-26):** "Yeni dataset, yeni segmentasyon modeli veya eski dataset, eski
segmentasyon modelleri arasında birbirlerinin kombinasyonlarını kullanarak kalkanlı, kalkansız, depth'li,
depth'siz bütün kombinasyonları deneyerek detaylıca bir karşılaştırma." Ayrıca `best_v4.pth` simülasyonda.

**Düzeltme (önceki sonuçlar için):** Düzeltme 27–28'deki "yalın RL" ölçümlerinde ortamın iç kalkanı (10 m, c13'ün
eğitimdeki kalkanı) açıktı. Bunlar "kalkansız" değil "eski kalkanlı" sonuçlardır. Bu düzeltmede kalkansız ayrıca
ölçülür.

**Etkenler** (hafif ortam, v4 doğrulama 175 sahne × 4 başlangıç = 700 iniş/hücre; her deneme yeni ortam; gimbal;
başarı her zaman gerçek etiketle):
- **Ajan (veri × derinlik), c13 tarifi:** eski veri + irtifa (c13 s0–s2), eski veri + Depth Anything (Düzeltme 27
  C_da s0–s2; 133 karede), yeni veri + irtifa (**v4_flat, yeni eğitim**: `train_denge`, 5 tohum), yeni veri + Depth
  Anything (v4_da s0–s4). Eski c13'e Depth Anything verilemez; model eğitildiği girdiyi bekler.
- **Segmentasyon:** gerçek etiket; v3 (`best_v3.pth`); v4 (`best_v4.pth`). Maskeler fotoğraftan, sahadaki kamerayı
  taklit için 9 cm/piksele indirilerek, Arda'nın `segmentle()` işleviyle (`~/rl_inis/v4/seg_maske.py`). Modellere
  dokunulmaz. Ön ölçüm (ölçülen, 175 sahne): piksel uyumu v3 %86.0, v4 %91.7; tehlikeliyi güvenli sanma v3 %12.0,
  v4 %4.8. Not: v4 bu kaynakların eğitim bölümlerini gördü, v3 FloodNet'i görmedi.
- **Kalkan:** yok (iç kalkan kapalı); eski (iç kalkan 10 m); kilitli (eski + kilitli kalkan).

**Kararlar (`~/rl_inis/v4/h29_ozet.py`):**
- **H29a:** c13 + kilitli kalkanla v4 maskesindeki başarı ≥ v3 maskesindeki + 3 ise "v4 segmentasyonu RL için daha iyi".
- **H29b:** kilitli ≥ eski ≥ yok sırasının kaç hücrede tuttuğu (tanımlayıcı).
- **H29c:** v4 segmentasyonu + kilitli kalkanla en iyi ajan grubu (tanımlayıcı).

**AirSim kısmı (ayrı adım, bu turdan sonra):** c13 s1, Faz 7'nin 30 başlangıcı, eski kalkan, v4 segmentasyonu.
Kıyas Faz 7: gerçek etiket 24/30, v3 16/30. Kural: zemin kuralına uygun iniş ≥ 19/30 ise v4 AirSim'de v3'ten iyi.
Depth Anything ve kilitli kalkan `policy_node`'da henüz yok; o kombinasyonlar AirSim'de şimdilik ölçülemez.

**Tahminler (_tahmin):** v4 maskesiyle başarı v3'ten 3–8 puan yüksek; kalkansız en çok segmentasyon hatasından
etkilenen; yeni veri + Depth Anything v4 maskesinde en iyi grup.
