# Veri toplama — dikey iniş kontrolcüsü (MATLAB/Simulink) ve RL için

Başlangıç: 2026-10-03 · Kod: `main` @ `v4.5-hud-canli-kamera` · Görev tanımı:
kullanıcının verdiği 7 aşamalı şartname (projenin akışı değişmeyecek; mevcut
koda her ekleme onayla, parametreyle seçilir, varsayılan kapalı).

Etiketler: **ölçülen** · **_hesap** (ölçülenden hesaplanan) · **_tahmin**
(varsayım içeren).

---

## Aşama 0 — okuma (dosya:satır)

### 1. EKF irtifası neye göre?

**Kalkış noktasına göre, alttaki zemine göre değil.** Mod irtifayı
`emergency_landing_mode.hpp:244` (`altitude_m = -pos_ned.z()`) ile alıyor: EKF
yerel çerçevesinin z'si, orijin EKF'nin açılışta yerde kurduğu nokta.
`mapping_node.py:219` ve `hud_node` `dist_bottom` geçerliyse onu kullanıyor;
**ölçülen** canlı durumda `dist_bottom_valid = false`,
`dist_bottom_sensor_bitfield = 0`: x500'de mesafe sensörü yok (`x500_base`
yalnız basınç, manyetometre, IMU, GNSS taşıyor). `EKF2_HGT_REF = 1` (barometre),
`EKF2_GPS_CTRL = 7`. Yani her yerde fiilen `−z` kullanılıyor ve
`LandingState.altitude_agl` adına rağmen AGL değil. Düz dünyada fark yok;
4 m'lik platformda (W5) yerden kalkılırsa EKF platformun üstünde 4 m fazla okur.

### 2. Maske ve ρ hangi damgayı taşıyor, moda nasıl gidiyor?

- **Maske: yakalama damgası.** `perception_node.py:147` `out.header = msg.header`:
  Gazebo'nun kareyi işlediği sim zamanı olduğu gibi geçiyor. Alma damgası yok;
  kaydedici kendisi ölçüyor (pasif testte yakalamadan kaydediciye **ölçülen**
  ortanca 41.6 ms, p90 63 ms; Gazebo penceresi açıkken).
- **ρ:** `detector_node.py:340-378` her maskede (10 Hz) hesaplıyor, ama moda
  yalnızca `LandingCandidate.area_ratio` içinde gidiyor (`detector_node.py:835`),
  karar hızında: sınır `max_rate_hz: 2.0` (`eland_params.yaml:132`), **ölçülen**
  1.78-1.83 Hz.
- **Damga uyuşmazlığı:** adayın damgası haritanınki (`detector_node.py:827`),
  `area_ratio` ise o ana kadar gelen son maskeden; iki ayrı abonelik, en çok
  bir kare kayabilir.
- **Modda:** `onCandidate` değeri tutuyor (`emergency_landing_mode.hpp:570-586`).
  `LandingState` onu ≤ 10 Hz'de yeniden yayınlıyor (`publishState`, `:667`,
  0.1 s kısma).

### 3. area ≈ 1584-1591 m² ve clearance = 20.00 m gerçek mi?

**İkisi de 40×40 m harita tavanı** (`eland_params.yaml:25-26`, 1600 m²).
`cv2.distanceTransform` ızgara kenarını sınır saymıyor; **ölçülen** sentetik
denemede tamamen güvenli ızgarada merkez açıklığı 6.3·10⁶ m, kenarda tek
hücrelik bilinmeyen halkayla 19.80 m çıktı. Harita araçla kaydıkça kenara
bilinmeyen hücreler giriyor; merkezdeki araçtan kenara ~20 m. Alan da 1600 m²
eksi bu kenar hücreleri. Gerçek alan daha büyük.

Karara etkisi yok: açıklık skorda `min(…, r_ideal = 8 m)` ile, alan da hız
tavanında `0.20·√A` olarak kullanılıyor ve A > 56 m²'de 1.5 m/s'de doyuyor.
Ama `area_m2` gerçek alan olarak **kullanılmamalı**; `rho_hesap` dünya
yaml'ındaki alanla hesaplanıyor.

### 4. 83.7 m'de APPROACH, arama irtifası 15 m — neden?

**Ölçülen**, PX4 kaydı `2026-10-03/10_40_52.ulg`: nav_state 4 → 2 (POSCTL,
manuel) t = 30 s'de, gaz çubuğu en fazla 1.00, araç 83.9 m'ye çıkıyor; mod
(nav_state 23) t = 90 s'de **83.9 m'de** devreye giriyor. Yani araç elle
yükseltilmiş.

Mod onu indirmiyor çünkü aday hazırsa SEARCH ilk adımda APPROACH'a geçiyor
(`emergency_landing_mode.hpp:254-277`) ve APPROACH **o anki irtifada** gidiyor
(`:287`, `target_ned = {cand.x(), cand.y(), pos_ned.z()}`). Arama irtifası
(`eland_params.yaml:282`, 15 m) yalnız aday yokken uygulanıyor. Bu bir kusur
değil, tasarım özelliği: mod, devreye girdiği irtifayı devralıyor. 83.9 m'de
kamera yerde ~199×149 m görüyor (**_hesap**), harita ise 40 m.

### 5. Kamera tam aşağı mı, bozulma var mı, sınır keskin mi?

- **Yön:** `x500_seg_cam_down/model.sdf:27` ve `CameraJoint` (`:30`), eğim
  1.5707 rad = 89.9947°; nadirden 0.0053° (**_hesap**). Kamera model
  orijininin 0.10 m üstünde.
- **Bozulma yok:** `seg_cam/model.sdf`'de `<distortion>` yok, ideal iğne delik.
  320×240, yatay FOV 1.74 rad, 10 Hz (`:85`). İç parametreler FOV'dan:
  fx = 134.7; Gazebo'nun kendi değeri 134.984, fark %0.2
  (`mapping_node.py:232`).
- **Sınır keskin:** Gazebo piksel başına tek etiket veriyor, kenar yumuşatma
  yok. GT yolu yalnız etiket ofsetini çıkarıyor (`perception_node.py:160-190`);
  yeniden boyutlandırma ya da süzme yok. Sınırlar tek piksel keskinliğinde;
  eğitilmiş model böyle olmayacak.

### 6. COMMIT'te iniş nasıl algılanıyor, yere değme anı nereden?

- **Mod:** `emergency_landing_mode.hpp:410` `_land_detected->landed()`, yani
  `/fmu/out/vehicle_land_detected.landed`.
- **PX4 iniş algılayıcısı:** `ground_contact → maybe_landed → landed`, her
  basamakta ~1/3 s gecikme; mesafe sensörü olmadığı için toplam 1 s
  (`MulticopterLandDetector.cpp:126-134`). **Ölçülen** 10 uçuşta (2026-09-26)
  `landed`, `ground_contact`'tan 0.69 s sonra geliyor; onda onunda aynı.
- **Gerçek temas:** ikisi de bir kestirim. Gerçek an Gazebo'dan geliyor (model
  yüksekliği dinlenme değerinin 0.03 m içine indiği an). Kaydedici bunu
  `t_temas_gercek` olarak ve iki bayrağın ona göre gecikmesiyle birlikte yazıyor.
- **run_scorer:** "indi" demek için COMMIT + durum kanalının 3 s susmasını
  bekliyor (`run_scorer.py:181-185`), yani daha da geç.

### 7. Gazebo gerçek konum ve yüzey yüksekliği nereden?

- **Araç konumu:** `/world/eland_test/dynamic_pose/info` (gz.msgs.Pose_V,
  **ölçülen** 50.7 Hz, modelin dünya ENU pozu; linkler modele göre).
  `/world/eland_test/pose/info` her şeyi düzensiz aralıkla veriyor.
- **Hız yok:** PX4'ün gz köprüsü `/model/x500_seg_cam_down_0/odometry_with_covariance`'a
  abone (`GZBridge.cpp:249-252`), ama modelde odometri eklentisi olmadığı için
  kimse yayınlamıyor (**ölçülen**: yayıncı yok). Gerçek dikey hız z'nin türevi:
  `vz_gercek_hesap`.
- **ROS köprüsü isimleri kaybediyor:** `ros_gz_bridge` Pose_V → TFMessage
  çevirisinde `child_frame_id` boş (**ölçülen**). Kaydedici gz-transport'u
  Python'dan doğrudan dinliyor.
- **Yüzey yüksekliği:** konusu yok; dünyalar düz kutulardan yapılı, yükseklik
  dünya tanımından (`tools/veri/dunya.py`). Model orijini yerde dururken
  z = −0.013 m (**ölçülen**).
- **Hareketli engeller:** `/eland/obstacle_truth` (sim zamanıyla damgalı).

### 8. Gerçek zamandan hızlı koşabilir mi, bir iniş kaç saniye?

- **Mümkün ama önerilmez.** Dünya `real_time_factor 1.0`, 4 ms adım
  (`eland_test.sdf.in:57-61`); PX4 `PX4_SIM_SPEED_FACTOR`'u destekliyor
  (`px4-rc.gzsim:154-158`). **Ölçülen** RTF 0.96-1.00, gz sunucusu 10 Hz
  kamerayla tek çekirdeğin %70-100'ünde (GPU yok, llvmpipe).
- **Neden önerilmez:**
  - İşlemci zaten dolu.
  - Hiçbir düğüm sim zamanı kullanmıyor (`use_sim_time` yok). Karar
    sınırlayıcısı (2 Hz), aday zaman aşımı (3 s) ve harita unutması duvar
    saatinde. 2× hızda karar döngüsü fiziğe göre yarı hızda kalır, veri temsil
    edici olmaz. Düzeltmek mevcut ayarı değiştirmek demek (onay ister).
- **Süre (ölçülen):** mod devreye girişi (~17.5 m) → PX4 `landed`: ortanca
  **21.7 s** [21.0, 23.1], n = 10. Arm → disarm 52-57 s. Toplu koşuda bir
  iniş, açılış-kapanış dahil **79-90 s duvar saati**.

---

## Ek bulgular (görevi etkiliyor)

| # | Bulgu | Etki |
|---|---|---|
| E1 | **PX4 parametreleri varsayılan değil ve kalıcı:** `MPC_Z_V_AUTO_DN = 2.0`, `MPC_Z_VEL_MAX_DN = 2.0` (varsayılan 1.5 / 1.5), `MIS_TAKEOFF_ALT = 18`. `run_sim --px4-param` ile verilenler PX4'ün parametre dosyasına yazılıp sonraki koşulara taşınıyor. Brif ve TEZ_NOTLARI 1.5 diyor. | Kapalı çevrim alçalmada etkisiz (mod komutu 1.5'te kırpıyor); goto fazlarında etkili olabilir. Şartname "PX4 parametrelerine dokunma" diyor: her bölümde `kosul.yaml`'a yazılıyor, geri almak senin kararın (K4). |
| E2 | **Su ya da yapıyla çevrili küçük adalar seçilemiyor.** Su ve yapı tehlike sınıfı (`eland_params.yaml:64`) ve 3 m mesafe şart (`:89`). 4×4 m adada merkez sudan 2 m, 6×6 m'de en iyi ihtimalle 3.0 m. | W1 hiç, W2 büyük ihtimalle aday üretmez. Aday yoksa mod VALIDATE'e girmez, alçalma verisi çıkmaz (K kipleri dahil); 60 s sonra kör iniş. Karar K1. |
| E3 | **K4 kendi içinde çelişkili:** tırmanma yok, v ∈ [0.3, 1.5], 15 m'de 20-30 s. Ortalama ~0.9 m/s ile 25 s'de 22 m iner, 15 m yetmez. | Karar K2. |
| E4 | **Gazebo rüzgârı yok:** `WindEffects` model linklerinde `<enable_wind>` ister, x500'de yok; eklemek modeli değiştirmek demek. Elde olan yanal kuvvet (`wind_inject.py`); 2-3 m/s ≈ 0.24-0.54 N (**_tahmin**, `F ≈ 0.06·v²`). | Karar K3. |
| E5 | **W5 (platform):** 0-4 m ofset 10×10 m platformun içine düşer; araç platformda doğarsa EKF orijini platformun üstü olur ve fark ölçülemez. | Doğuş platformun dışında, yerde olmalı (ofset ≥ 6 m). **_tahmin:** EKF 2 m'de tetiklenen COMMIT platformun 2 m altına denk gelir, temas VALIDATE'te ~1.4 m/s ile olur. Kol 0'da W5 tam bunu ölçecek. |
| E6 | PI'nin integrali yayınlanmıyor. | Şimdilik `I_hesap` (geri çatım, yalnız VALIDATE'te ve doyumsuzken). Kesin değer için O2b. |
| E7 | **Makine ortak:** `run_sim.sh` açık bir simi kapatıyor (2026-10-03'te bir kez oldu). | `tools/veri/kosu.sh` açık sim görürse başlamıyor. Toplama için ~24 saatlik tek başına sim zamanı gerek. Karar K5. |
| E8 | Bu makinede MATLAB/Octave yok. | `.mat` yalnız `scipy.io.loadmat` ile geri okunarak doğrulandı. |
| E9 | `/tmp/eland_logs` her koşuda üzerine yazılıyor. | Koşucu logları bölüm klasörüne kopyalıyor. |

---

## Aşama 1 — kayıt düğümü

**Durum: tamam, uçan inişte doğrulandı** (`v4.6-veri-kaydedici`). Açık
alanda Kol 0, tohum 1001-1003, üç iniş; sonuçlar aşağıda.

Dosyalar (yeni, mevcut koda dokunmuyor): `tools/veri/kaydedici.py`,
`tools/veri/ozellik.py`, `tools/veri/dunya.py`, `tools/veri/kosu.sh`,
`tools/veri/data_dictionary.md`.

- **Yalnız dinliyor.** ROS'ta PX4 çıkışları, modun setpoint'leri,
  `/eland/state`, `/eland/candidate`, maske; Gazebo'da sim saati ve gerçek poz.
  Hiçbir şey yayınlamıyor.
- **Önce kayıt, sonra tablo.** Her mesaj geldiği sim zamanıyla tutuluyor;
  tablolar bölüm sonunda kuruluyor. 50 Hz ızgara sıfırıncı mertebe tutmalı,
  her kanal için `_yas_ms`.
- **Çıktılar:** `duzenli.csv`, `maske_olaylari.csv`, `karar_olaylari.csv`,
  `durum_gecisleri.csv`, `ep_ozet.json`, `kosul.yaml`, `ep.mat` (v7),
  `maskeler.npz`.
- **Pasif test (ölçülen,** senin yerdeki aracında, 20 s):

  | Kanal | Hız | En uzun boşluk | Kayıp |
  |---|---|---|---|
  | PX4 konum | 50.3 Hz | 24 ms | 0 |
  | PX4 tutum | 50.3 Hz | 24 ms | 0 |
  | Gerçek poz | 50.7 Hz | 24 ms | 0 |
  | Sim saati | 250 Hz | 4 ms | 0 |
  | Maske | 10.0 Hz | 200 ms | 1 |
  | Aday | 1.83 Hz | 647 ms | 0 |

  `.mat` ve `.npz` geri okundu. Mod yerde etkin olmadığı için durum ve
  setpoint kanalları boştu.
- **Öznitelik birim testi:** 100×100 px kare → ρ = 0.1302, iç daire 50 px,
  kadraja sığıyor; açık alan → ρ = 1, 4 kenar, iç daire 120 px (kare kenarı
  sınır); merkez suda → ρ = 0; çim + asfalt tek bölge. Ayak izi katsayısı
  4.216 (**_hesap**).

### Uçan doğrulama — açık alan, Kol 0, 3 iniş (ölçülen)

`tools/veri/dogrula.py`; tablo ve grafikler `~/eland_veri/dogrulama/kol0_acik_alan/`.

| | t1001 | t1002 | t1003 |
|---|---|---|---|
| Başarılı | ✓ | ✓ | ✓ |
| Spesifikasyon sütunları, alçalmada dolu | %100 | %100 | %100 |
| EKF − gerçek yükseklik, bias / RMS | +0.03 / 0.14 m | +0.04 / 0.13 m | +0.01 / 0.14 m |
| vz_ekf − vz_gercek RMS | 0.036 | 0.028 | 0.052 m/s |
| Takip RMS (vz − v_ref, VALIDATE) | 0.12 | 0.15 | 0.22 m/s |
| Maske yaşı p50 / p90 | 19 / 36 ms | 19 / 31 ms | 20 / 39 ms |
| ρ ortancası / kadraja sığma (VALIDATE) | 0.999 / %0 | 1.000 / %0 | 0.998 / %0 |
| **Gerçek temas hızı** | 0.29 m/s | 0.31 m/s | 0.30 m/s |
| **PX4 `ground_contact` gecikmesi** | 4.19 s | 4.01 s | 3.11 s |
| **PX4 `landed` gecikmesi** | 4.88 s | 4.69 s | 3.80 s |
| COMMIT anında EKF / gerçek yükseklik | 1.95 / 2.03 m | 1.97 / 2.01 m | 1.97 / 2.07 m |
| Konum mesajı en uzun boşluk | 107 ms | 39 ms | 343 ms |
| Bölüm boyutu | 1.3 MB | 0.9 MB | 1.1 MB |

**Yeni bulgu — PX4'ün iniş bayrakları gerçek temastan 3-5 s geç.** Gazebo'da
araç t = 18.7 s'de yere değiyor (yükseklik 0, hız 0.3 → 0 m/s). PX4
`ground_contact`'ı 3.1-4.2 s, `landed`'ı 3.8-4.9 s sonra veriyor. Arada mod
aracı yerde 0.3 m/s komutla aşağı itmeyi sürdürüyor; itki ancak o zaman
düşüyor ve algılayıcı tetikleniyor. Sonuç: şimdiye kadar raporlanan
"mod → landed" süreleri (ör. 21.7 s) yerde geçen ~4-5 s'yi içeriyor. Yere
değme anı ve temas hızı yalnızca Gazebo'dan alınmalı; bu kayıtlarda öyle.

Diğer gözlemler:
- `v_cmd` mod iniş sonrası tamamlanınca kesiliyor; durum COMMIT'te kaldığı
  için alçalma satırlarının %12-15'inde boş.
- Açık alanda ρ zaten 0.93-1.0'da ve kadraja hiç sığmıyor; sınıf sınırı
  pikselleri 1.3 m civarında sıfıra iniyor. Önceki ölçümlerle tutarlı.
- **Sınır:** açık alan dünyasının yüzey yükseklikleri henüz tanımlanmadı
  (yol ve yamalar 0.02 m kalınlıkta kutu, binalar 9 m). Kaydedici zemini
  z = 0 alıyor; yamalar üzerinde ±0.02 m, bir binanın üstünden geçerken 9 m
  hata olur. Aşama 2'de dünya dosyasından üretilecek.

Eksik: birleşik `.mat` ve `tum_ozet.csv` (Aşama 6).

---

## Kararlar (kullanıcı, 2026-10-03)

| | Karar |
|---|---|
| K1 | Adaların çevresi **tehlike sayılmayan bir sınıf**: arazi tehlikesi (sınıf 2) |
| K3 | **Gerçek Gazebo rüzgârı** (kuvvet eşdeğeri değil) |
| K4 | PX4 parametreleri **bugünkü hâliyle** (`MPC_Z_V_AUTO_DN = 2.0`) kalır |
| O3 / K5 | **Onaylandı** |
| K2 | Açık — Aşama 4 yeniden anlatıldı |

## Aşama 2 — dünyalar (üretildi, henüz uçurulmadı)

`tools/veri/dunya_uret.py`, yeni dosyalar:
- **Sabit dünyalar:** W1-W8 `src/eland_sim/worlds/veri/` altında; her birinin
  `_r2p5` rüzgârlı eşi var (2.5 m/s, 45°).
- **Rastgele adalar:** tohumdan, `~/eland_veri/dunyalar/` altına üretiliyor.
  Şekil kare/L/daire, boyut 3-20 m, konum ofseti ±8 m, 0-2 hareketli kişi.
- **Ground truth:** her dünyanın yaml'ında yüzey yükseklikleri, hedef adanın
  alanı / merkezi / şekli, tohumdan başlangıç koşulları (irtifa 10-20 m,
  ofset 0-4 m), rüzgâr ve kişilerin rotası.
- **Zemin:** her yer arazi tehlikesi sınıfı, adalar çim. Hepsi `gz sdf -k`
  ile geçerli.

Geometriden çıkan sonuçlar (dedektörün kendi kurallarıyla, 0.2 m ızgara):
- **W1 (4×4 m) aday üretmez,** sınıf çevresi tehlike olmasa bile: sınıf
  dikişi kuralı 2 m, ızgarada merkezin dikişe uzaklığı 1.8 m. 4.4 m'den dar
  her ada için aynı. "Site yok" örneği olarak kaldı; mod 60 s sonra kör
  iner.
- **W6:** L'nin kolları 6 m (4 m'lik kol aday üretmez).
- **W8:** ortadaki 2×2 m nesne de tehlike sayılmayan sınıfta (yapı olsaydı
  3 m mesafe + 2 m dikiş kuralı 10×10 m adada hiçbir yer bırakmazdı).
- **W5:** platform 10×10×4 m, üstü çim. Doğuş platformun dışında, 6.5-8 m
  ofsetle; EKF orijini yerde kalsın, 4 m fark ölçülsün diye.

**Rüzgâr:** Gazebo'nun WindEffects sistemi yalnız `enable_wind` işaretli
linkleri iter; PX4'ün x500'ünde bu yok. SDF'nin dahil-et-değiştir yöntemi bu
alanı ekleyemiyor (ölçülen hata: "Could not find element", "missing a 'name'
attribute"). Bu yüzden `tools/veri/ruzgar_modeli_uret.py` PX4'ün x500
dosyalarını okuyup yalnız o satırı ekleyen bir model zinciri üretiyor:
`x500_seg_cam_down_ruzgar`. PX4'ün dosyaları değişmedi. Rüzgârlı dünyalar
WindEffects'i ve PX4'ün eklenti listesinin tamamını taşıyor (dünya kendi
eklentisini tanımlayınca PX4'ün varsayılan listesi yüklenmiyor). Kuvvet
ölçeği ilk rüzgârlı uçuşta ölçülecek.

**Uçurmak için O1 gerekiyor** (dünya ve model seçimi).

## K5 — tesis testi, rüzgârsız (tamam)

Açık alan, mevcut tanımlama kipi (kod eklemesi yok), açık çevrim kare dalga,
8 s periyot, kalkış 22 m. Genlik A: komut −min(A, 1.0) ile +A arasında.
Kol başına 3 uçuş (tohum 1001-1003), toplam 12 uçuş. Yalnız
`h_gercek_zemin > 8 m` satırları; iki yanında tam yarım periyot olan
basamaklar. `tools/veri/tesis_analizi.py`.

| Genlik | Kaynak | n basamak | K ortanca | θ (%10) | %90 süresi | En büyük ivme | Yavaşlatma / hızlanma |
|---|---|---|---|---|---|---|---|
| 0.3 | Gazebo | 55 | 1.000 | 0.06 s | 0.26 s | 3.6 m/s² | 3.7 / 3.0 |
| 0.6 | Gazebo | 55 | 0.992 | 0.04 s | 0.28 s | 6.1 m/s² | 6.2 / 5.4 |
| 1.0 | Gazebo | 54 | 0.997 | 0.06 s | 0.36 s | 6.7 m/s² | 6.2 / 7.9 |
| 1.5 | Gazebo | 19 | 0.991 | 0.06 s | 0.40 s | 8.4 m/s² | 6.3 / 8.5 |
| 0.3-1.5 | EKF | 183 | 1.014-1.024 | 0.06-0.08 s | 0.28-0.44 s | 3.7-7.7 m/s² | |

- **Ölü zaman eski değerin beşte biri.** Eski 0.28 s, komutu 10 Hz'lik durum
  kanalından okuyan ve rampa uydurulan yöntemdendi. Tez notlarına ve brife
  düzeltme eklendi; IMC kazanç türetimi yeni θ ile yeniden yapılmalı.
- **1.5 genliğinde basamak az (19):** asimetrik dalga aracı aşağı sürüklüyor,
  8 m koruması devreye girip basamakları bozuyor.
- **Izgara 50 Hz:** θ'nın çözünürlüğü 0.02 s.

Şekil: `~/eland_veri/dogrulama/k5/tesis_basamak.png`. Rüzgârlı yarısı O1
bekliyor.

---

## Onay bekleyenler — mevcut koda eklemeler

Hepsi parametreyle seçilir, varsayılan kapalı, mevcut davranış değişmez.

**O1 — Aşama 2'yi ve rüzgârı uçurabilmek için (`run_sim.sh`, `batch_run.sh`).**
`run_sim.sh`'e iki seçenek; verilmezse bugünküyle aynı:
- `--world AD`: `PX4_GZ_WORLD=AD`; `gen_world.py` ve rastgele doğuş atlanır,
  doğuş dünyanın yaml'ından `--pose` ile gelir; dünya dosyası PX4'ün dünya
  klasörüne bağlanır (`link_px4_assets.sh`'in yaptığı gibi).
- `--model AD`: `PX4_SIM_MODEL=gz_AD` (rüzgârlı araç için); model PX4'ün
  model klasörüne bağlanır.

`batch_run.sh`'e isteğe bağlı `DUNYA` / `MODEL` ortam değişkenleri. ~20
satır. Gerekçe: şartname "mevcut batch_run.sh ile uçurulabilmeli" diyor;
dünya ve model adı şu an `run_sim.sh`'te sabit.

**O2 — Aşama 4 (K1-K4) için (`emergency_landing_mode.hpp`).**
`veri_toplama_kipi` parametresi (varsayılan false). Açıkken VALIDATE'te `v_ref`
yeni bir konudan gelir (`/eland/veri/v_ref`, std_msgs/Float32); konu 0.3 s'den
bayatsa mevcut yasa kullanılır. COMMIT'e geçiş, mevcut EKF 2 m kuralına ek
olarak `/eland/veri/h_gercek_hedef < 2.5 m` olunca. PI iç döngü, durum makinesi
ve mesajlar aynı kalır. ~40 satır. Politikaların hepsi (sabit hız, kâhin
ıraksama, rastgele, basamak/çoklu-sinüs) ve gerçek irtifa yayını yeni
düğümlerde (`tools/veri/`). Gerekçe: v_ref'i dışarıdan vermenin, mod
değişmeden başka yolu yok.
- **O2b (isteğe bağlı):** aynı bayrak açıkken `/eland/veri/hiz_dongusu`
  (v_cmd, I, e, v_ölçülen) yayını. Gerekçe: integralin kesin değeri (E6).

**O3 — K5 (tırmanmalı tesis testi).** **Onaylandı;** rüzgârsız yarısı
yapıldı (yukarıda). Kod eklemesi gerekmedi.

**Bilgi (onay gerekmiyor) — Aşama 5.** Bozucu yeni bir düğüm.
`detector_node`, `mapping_node` ve `hud_node`'un zaten `mask_topic` parametresi
var; parametre dosyasından `/eland/semantic_mask_bozuk`'a çevrilir. Füzyonlu
harita da bozulmuş maskeyi görür; şartnamenin "maske hattından sonra" dediği bu.

---

## Açık kalan karar

- **K2 (E3):** K4 (basamak/çoklu sinüs) tırmanmasız ve 15 m'den başlarsa
  20-30 s sürmez, araç yere iner. Seçenekler: (a) 40 m'den başlat,
  (b) tanımlamayı K5'e bırak (K5 artık var), (c) 12 s'ye kısalt.
- **Toplama zamanı (E7):** tek başına sim gerekiyor.

---

## Süre ve disk tahmini (_tahmin, bölüm başına ~85 s ölçümünden)

| İş | Bölüm | Süre |
|---|---|---|
| Kol 0 (W2, W3, W5, W6, 20 ada, açık alan; ×3) | 75 | ~1.8 sa |
| K1 (4 hız × 5 dünya × 3) | 60 | ~1.4 sa |
| K2 (5 D* × 5 dünya × 3) | 75 | ~1.8 sa |
| K3 (≥ 400) | 400 | ~9.5 sa |
| K4 + K5 | ~45 | ~1.1 sa |
| Aşama 5 (~9 bozucu ayarı × ~26) | ~230 | ~5.5 sa |
| **Toplam** | **~885** | **~21 sa** |

Disk: bölüm başına ~1 MB (ölçülen, 3 iniş), toplam ~1 GB.

**Ham veri yolu:** `~/eland_veri/<kol>/<dunya>/<ep_id>/` (Windows'tan
`\\wsl.localhost\ubuntu\home\arda\eland_veri`). Pasif test çıktısı:
`/tmp/veri_test/ep_pasif/`.

---

# Tur 2 — diğer sohbetin kararlarından sonra (2026-10-03 akşam)

Kararlar (kullanıcı, diğer sohbet üzerinden):
- **O1 verildi, O2 verildi, O2b verilmedi.**
- **K4:** 40 m'den, [0.3, 1.5] içinde kırpmasız, 0.9 ± 0.6 m/s çevresinde
  çoklu-sinüs ve basamak, ~20 s periyot, 2 tur, yalnız W3, 12 uçuş.
- **Şartname değişiklikleri 1-7** uygulandı (aşağıda).

## Doğrulamalar

**6a / W5 hükmü (a) — COMMIT tetiği EKF yüksekliğine bağlı mı?** Evet.
`emergency_landing_mode.hpp:297`:
`if (altitude_m <= _landing_altitude_m && !_ident_enabled)` → COMMIT.
`altitude_m` `:244`'te `-pos_ned.z()` (EKF yerel z, kalkış noktasına göre).
`landing_altitude` `eland_params.yaml:286` = 2.0 (varsayılan `:467`). W5'te
platform 4 m yüksekte olduğu için bu kural platformun üstünde tetiklenmez.

**6 — Eski taban çizgi hangi parametrelerle ölçüldü?** PX4'ün 266 uçuş
kaydının parametre başlığı tarandı (ölçülen):

| Kayıt aralığı | MPC_Z_V_AUTO_DN | MPC_Z_VEL_MAX_DN |
|---|---|---|
| 2026-09-04 08:38 → 2026-09-05 20:50 | 1.5 | 1.5 |
| 2026-09-05 20:50 | 1.5 | 2.0 |
| **2026-09-05 20:54 → bugün** | **2.0** | **2.0** |

Brifteki taban çizgi (alçalma 21 s, takip RMS 0.19-0.20, 5/5 iniş) 2026-09-26
akşamı ölçüldü (53 kayıt, hepsi 2.0 / 2.0). Kapalı çevrim (`v2.7`, 2026-09-06)
ve sonrasındaki her ölçüm de 2.0 / 2.0. Yalnız TEZ_NOTLARI §2.1'deki ilk açık
çevrim ölçümü 1.5 / 1.5 döneminden. Kontrolcü tasarım sınırı yine [0, 1.5] m/s
(modun kendi kırpması).

**O2b yerine — `I_hesap` ile çevrimdışı PI yeniden oynatma** (`tools/veri/pi_tekrar.py`,
Kp 0.8, Ki 0.6, Kaw 1.0, VALIDATE girişinde sıfırlama, 50 Hz ızgarada):

| Bölüm | n | v_cmd: yeniden oynatma − kayıt, RMS / ort / en çok | I: yeniden oynatma − I_hesap, RMS / ort / en çok |
|---|---|---|---|
| kol0_acik_alan_t1001 | 566 | 0.028 / +0.021 / 0.100 m/s | 0.029 / +0.021 / 0.100 m/s |
| kol0_acik_alan_t1002 | 475 | 0.036 / +0.025 / 0.124 m/s | 0.037 / +0.026 / 0.124 m/s |
| kol0_acik_alan_t1003 | 489 | 0.026 / +0.016 / 0.090 m/s | 0.028 / +0.019 / 0.090 m/s |

- **Yeniden oynatma komutu 0.03 m/s RMS ile tutturuyor.** Ama integral için
  fark (0.031 m/s RMS) integralin kendi büyüklüğü mertebesinde (|I| p95
  0.10-0.16 m/s); korelasyon −0.6 ile +0.7 arasında.
- **Yani integral ızgaradan ±0.03 m/s'den iyi bilinemiyor.** Sebep: `v_ref`
  durum kanalından ≤ 10 Hz geliyor, mod ise kendi döngüsünde (~30-50 Hz)
  taze yasa değeriyle hesaplıyor. Yasa irtifayla sürekli azaldığı için tutulan
  `v_ref` hep biraz yüksek kalıyor; artı yönlü sapmanın sebebi bu.
- **MATLAB'da yeniden oynatırken öneri:** irtifa yedeğindeyken `v_ref`'i
  `clamp(0.35·h_ekf, 0.3, tavan)` ile yeniden hesaplamak, tutulan değeri
  kullanmaktan iyi.

## Uçuş gerektirmeyen işler

**A) 10 Hz ayrı ρ yayını — değişecek dosyalar (uygulanmadı, ayrı onay bekliyor):**
1. `src/eland_msgs/msg/GoruntuKapsami.msg` (yeni):
   - `std_msgs/Header header` — damga = maskenin yakalama damgası
   - `float32 area_ratio`, `bool view_bounded` — aynı mesajda
   - `uint32 bolge_piksel`, `uint8 merkez_sinif`
2. `src/eland_msgs/CMakeLists.txt`: `rosidl_generate_interfaces` listesine
   bir satır.
3. `src/eland_mapping/eland_mapping/detector_node.py`, `on_mask`
   (`:340-378`): ρ ve `view_bounded` zaten her maskede (10 Hz) hesaplanıyor;
   kısma yalnız `on_map`'te (`:583`). Sonuna `publish_area_ratio`
   parametresiyle (varsayılan false, konu `/eland/area_ratio`) mesajı
   yayınlayan ~10 satır.
4. `src/eland_mode/include/emergency_landing_mode.hpp`: `use_fast_area_ratio`
   (varsayılan false). Açıkken `_area_ratio` / `_view_bounded` bu konudan,
   bayatlık kontrolüyle güncellenir; `area_m2` adaydan gelmeye devam eder.
   ~25 satır.
5. İsteğe bağlı: kaydedici ve HUD yeni konuyu da okuyabilir.

**B) Veri seti düzeni** (`tools/veri/birlestir.py`):
- `tum_ozet.csv`: bölüm başına bir satır, bölmesiyle.
- **Bölme 70/15/15, kararlı bir özetle (hash):** rastgele adalarda adanın
  tamamı tek anahtar (test adası hiçbir desenle, hiçbir rüzgârla eğitime
  girmez); diğer dünyalarda anahtar dünya + tohum.
- `_bolme/{train,val,test}/` bölüm klasörlerine bağlantılar ve her bölme için
  `birlesik_<bolme>.mat`: sayısal sütunlar float32, `ep_idx` sütunu, `ep`
  tablosu. Test ayrı klasörde.

**C)** `data_dictionary.md`'ye eklendi: `h_ekf` kalkış noktasına göre, hedef
yüzeye göre değil; `altitude_agl` adı yanıltıcı. Ayrıca 4.4 m eşiği (W1, W6
kolları, negatif örnekler), W8 sınıf sınırı nesnesi, `kosul.yaml` alanları.

**D)** Açık alan yüzey yükseklikleri tanımlandı:
`src/eland_sim/worlds/veri/acik_alan.yaml`, şablonun çarpışma geometrisinden,
30 yüzey. Kaydedici artık bunu kullanıyor. Öncesindeki 3 açık alan bölümü zemin
0 ile kaydedildi; sözlükte etkilenen sütunlar yazılı.

**E) Zaman hizası — bir ep.mat** (`tools/veri/zaman_hizasi.py`, k1_v1.0_veri_w3_t3001):

| Yapı | Alan | Sayısal | Metin (MATLAB'da cell) | Uzunluk |
|---|---|---|---|---|
| duzenli | 44 | 40 | ep_id, dunya_id, tohum, kol | 2547 |
| maske | 26 | 26 | — | 505 |
| karar | 12 | 12 | — | 91 |
| gecis | 4 | 1 | onceki, sonraki, neden | 3 |

- **Maske yakalama → kayıt:** p50 19.1 ms, p90 39.7 ms, p99 94.5 ms, en çok
  295 ms.
- **Izgara:** aralık tam 20.000 ms (yapı gereği jitter 0). Zamanlama
  kanalların yaşında görünüyor:

| Kanal | Yaş p50 | p95 | Not |
|---|---|---|---|
| h_ekf, roll | 11 ms | 11 ms | 50 Hz |
| h_gercek_zemin | 12 ms | 20 ms | Gazebo, 50 Hz |
| v_ref_dis | 19 ms | 19 ms | politika, 50 Hz |
| v_ref, durum | 66 ms | 1600 ms | 10 Hz; mod durunca (iniş sonrası) yaşlanıyor |
| v_cmd | 6 ms | 1576 ms | 50 Hz; aynı sebep |
| landed | 493 ms | 952 ms | PX4 yalnız değişince/1 Hz yayınlıyor |

- **Yapı:** `duzenli`'de 4 metin sütunu her satırda aynı değeri taşıyor;
  MATLAB'da cell dizisi olarak gelir. Bozuk yapı görülmedi; MATLAB yok, yalnız
  scipy ile okundu.

## Kod değişiklikleri (onaylı, parametreyle, varsayılan kapalı)

**O1:**
- `run_sim.sh`: `--world AD|DOSYA` ve `--model AD`. Verilmezse eski davranış:
  `eland_test`, `gen_world`, rastgele doğuş, `x500_seg_cam_down`.
- `batch_run.sh`: `DUNYA` / `MODEL` ortam değişkenleri ve bunların
  `obstacle_driver` ayarları (`tools/veri/dunya_parametreleri.py`).

**O2:** `emergency_landing_mode.hpp`, `veri_toplama_kipi` (varsayılan false;
kapalıyken hiçbir abonelik oluşmuyor).
- **Açıkken:** VALIDATE'te referans `/eland/veri/v_ref`'ten gelir, 0.3 s'den
  bayatsa yasaya düşer. Gazebo hedef yüksekliği
  (`/eland/veri/h_gercek_hedef`) < 2.5 m olunca COMMIT'e devreder.
- **Değişmeyenler:** PI, sınırları, durum makinesi, mesajlar.
- **W5 hükmü:** politika `--devir-yok --son-hiz 0.5` ile yüksekliği hiç
  yayınlamaz (devir yok) ve 2.5 m altında 0.5 m/s komut eder. Temas
  Gazebo'dan ölçülür. `kosul.yaml`'da `gt_devir` alanı.

**Yeni dosyalar (onay gerekmiyor):**
- `tools/veri/politika.py` (K1-K4)
- `tools/veri/bozucu.py` (Aşama 5, varsayılan kapalı)
- `tools/veri/baslangic.py` (tohumdan başlangıç)
- `tools/veri/toplu.sh`, `tools/veri/adim_ozet.py`, `tools/veri/pi_tekrar.py`
- `tools/veri/zaman_hizasi.py`, `tools/veri/ruzgar_karsilastir.py`
- `tools/veri/acik_alan_yuzey.py`

**Şartname değişiklikleri:**
1. W1 yalnız Kol 0.
2. Rastgele adalar 5-20 m, ~%10 negatif (45 adadan 4'ü), `negatif_ornek`
   etiketli.
3. W5 doğuş ofseti 6.5-8 m.
4. W6 kolları 6 m, sözlükte.
5. W8'deki nesne "sınıf sınırı nesnesi".
6. PX4 2.0 sabit.
7. Rüzgâr karşılaştırması 4. adımda.

**Ek düzeltme:** sabit dünyalarda başlangıç dünya yaml'ında tek değerdi, aynı
dünyanın 3 tekrarı aynı noktadan başlardı. Artık (dünya, tohum) çiftinden
çekiliyor.
