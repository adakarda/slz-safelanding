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
`emergency_landing_mode.hpp:244` (O2 sonrası `:269`) (`altitude_m = -pos_ned.z()`) ile alıyor: EKF
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
Satır numaraları O2 sonrası (`v5.0-veri-kipi` ve sonrası); parantez içinde O2
öncesi:
- `emergency_landing_mode.hpp:322` (:297):
  `if (altitude_m <= _landing_altitude_m && !_ident_enabled)` → COMMIT.
- `altitude_m` `:269`'da (:244) `-pos_ned.z()` (EKF yerel z, kalkış
  noktasına göre).
- `landing_altitude` `src/eland_sim/config/eland_params.yaml:286` = 2.0
  (varsayılan `hpp:508`, önce :467).
- W5'te platform 4 m yüksekte olduğu için bu kural platformun üstünde
  tetiklenmez.

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

---

# Tur 2 — yürütme (2026-10-03 gece)

Günlükler: `~/eland_veri/_gunlukler/` (her adım için `adimN_*.log`: başlangıç,
bitiş, duvar saniyesi, çıkış kodu, komut; ayrıntı `.ayrinti`'de).

## Olay: sızan süreçler — K1 ve K2'nin ilk toplaması karantinada

**Ne oldu:** `run_sim.sh`'nin kapanış temizliği boru hattını adla öldürüyor;
`tracker_node` ve `obstacle_driver` listede yok (`run_sim.sh:241-251`).
`tools/batch_run.sh` bu ikisini kendisi öldürdüğü için orada sorun yok, ama
`kosu.sh` `run_sim.sh`'yi doğrudan TERM ile kapatıyor. Adım 1b'den itibaren
her bölüm bir çift bıraktı: 8 + 32 + 24 = 64 çift. Son durumda ~10 GB bellek,
~8 çekirdek (her `obstacle_driver` ~%12 CPU).

**Etkisi (ölçülen, zincir sırasına göre):**

| Bölümler | Sızan çift (başta) | vz_ekf − vz_gercek RMS (m/s) | EKF yükseklik kayması (m) | Maske yaşı p50 (ms) |
|---|---|---|---|---|
| Adım 1, Kol 0 (28) | 0 – 7 (1b); ilk 20 için bilinmiyor | 0.02 – 0.08 | ≤ 0.14 | 18 – 29 |
| K1 W2 (8) | 8 – 15 | 0.01 – 0.04 | ≤ 0.04 | 20 – 22 |
| K1 W3 (8) | 16 – 23 | 0.04 – 0.16 | −0.54'e kadar | 22 – 24 |
| K1 W4 (8) | 24 – 31 | 0.08 – 0.45 | −0.80'e kadar | 22 – 26 |
| K1 W5 (8) | 32 – 39 | 0.12 – 1.19 | 1.32'ye kadar | 26 – 29 |
| K2 W2 (4) | 40 – 43 | 0.24 – 0.92 | 2.73'e kadar | 29 – 30 |
| K2 kalan (20) | 44 – 63 | — | — | 31 – 46 |

- **K1 W5'te 0.5 m/s komuta karşı 1.25 m/s temas:** EKF 0.6 m/s alçaldığını
  sanırken araç gerçekte 1.4 m/s alçalıyordu. PI, EKF hızını referansa
  çekmek için komutu artırdı.
- **K2'nin kalan 20 bölümünden 13'ünde mod süreci öldü.** 9'unda açıkça
  `timeout while waiting for FMU publisher discovery` → `Registration failed`.
  Ayrıca 5 bölümde kör iniş oldu; yalnız 1 bölüm başarılı.
- **Bölümler silinmedi:** `~/eland_veri/_karantina/2026-10-03_sizinti/` altında,
  `BENIOKU.md` ile. Veri setine girmiyor.

**Düzeltme (`v5.1-veri-temizlik`, yalnız yeni dosyalar):**
- `kosu.sh` her alt süreci `VERI_KOSU_ISARET` ortam işaretiyle başlatıyor.
  Kapanışta işaretli artıkları kapatıp bölümün `artik_surecler.txt`
  dosyasına yazıyor. Her bölümde 3 artık çıkıyor: `tracker_node`,
  `obstacle_driver` ve bir `python3` (politika ya da bozucu, TERM'den sonra
  hâlâ kapanıyor).
- Kaydedici ve `run_sim` için zaman sınırı var. Eski K1 v1.5 W3 t1, özetini
  yazdıktan sonra 13 dk asılı kalmıştı.
- `kosul.yaml` mod seçildikten sonra yazılıyor. Sabit 20 s bekleme yavaş
  makinede önceki bölümün `MIS_TAKEOFF_ALT`'ını okuyordu. Tutulan 43 bölümün
  hepsinde değer kalkış irtifasıyla aynı (kontrol edildi).
- **`run_sim.sh`'ye dokunulmadı.** Temizlik listesine bu iki düğümü eklemek
  mevcut koda ekleme, onay bekliyor.

**Doğrulama:** 132 artık süreç öldürüldü, bayat FastDDS `/dev/shm` dosyaları
silindi. Aynı K1 W5 bölümü (v0.7, t1) temiz sistemde yeniden uçuruldu:

| | Eski (sızıntı altında) | Yeni |
|---|---|---|
| vz hata RMS | 0.42 m/s | 0.02 m/s |
| EKF yükseklik kayması | 1.32 m | −0.02 m |
| Temas hızı | 1.25 m/s | 0.53 m/s |
| Temasta `h_ekf − h_gercek_hedef` | 5.26 m | 4.05 m |

**Yan kayıp:** artıklar öldürülünce WSL dağıtımı boşta kalıp yeniden başladı
ve `/tmp` silindi. Kayıplar:
- **1.–3. adımın günlükleri.** 1b, K1 ve K2 satırları bu oturumun çıktısından
  aynen geri alındı.
- **Adım 1'in 7 satırı** (W3 ×3, W4 t1, W5 t3, W6 t1-t2). Bölüm klasörünün
  doğum / son yazma zamanından yeniden kuruldu, `~` ile işaretli.

Günlükler artık `/tmp`'de değil.

## Adım 1 — Kol 0 (28 bölüm, tamam)

| Dünya | Bölüm | Başarılı | Duvar süresi, ortanca | Temas hızı (gerçek), ortanca |
|---|---|---|---|---|
| W2 | 3 | 3 | 78 s | 0.30 m/s |
| W3 | 3 | 3 | 74 s | 0.30 m/s |
| W4 | 3 | 3 | 70 s | 0.31 m/s |
| W5 | 3 | 3* | 65 s | **1.47 m/s** |
| W6 | 3 | 3 | 76 s | 0.30 m/s |
| W1 (negatif) | 3 | 0 (beklenen) | 134 s | 0.29-0.30 m/s |
| 10 ada (t2003-t2012) | 10 | 9 / 9 + 1 negatif (beklenen başarısız) | 83 s | 0.29-0.31 m/s |

Toplam duvar süresi 40 dk.

- **W1:** aday hiç yok. Mod 60 s arayıp 15 m'den kör iniyor (SEARCH → COMMIT).
  Temas 0.29-0.30 m/s; 3 bölümün 2'si şans eseri adaya indi.
  `ozet_yenile.py` bu üç bölümün boş kalan temas alanlarını doldurdu.
  Eski değerler `onceki` altında.
- **t2012 negatif ada (< 4.4 m):** aday yok, kör iniş, hedef dışı.
  Başarısızlık beklenen.
- **\* W5:** "başarılı" ölçütü hız içermiyor; 1.47 m/s sert temas. Ayrıca
  işaretlenmeli.

**W5, Kol 0 (W5 hükmü d), ölçülen:**

| Bölüm | COMMIT girildi mi | Temas hızı (gerçek) | Temasta h_ekf − h_gercek_hedef | Temastan hemen önce v_ref | PX4 landed, temastan sonra |
|---|---|---|---|---|---|
| kol0_veri_w5_t1 | hayır | 1.47 m/s | 3.81 m | 1.40 m/s | 1.05 s |
| kol0_veri_w5_t2 | hayır | 1.47 m/s | 3.81 m | 1.40 m/s | 1.06 s |
| kol0_veri_w5_t3 | hayır | 1.48 m/s | 3.87 m | 1.45 m/s | 1.07 s |

- **Beklentiyle aynı:** EKF temasta ~4 m gösteriyor, komut 0.35·4 ≈ 1.4 m/s,
  COMMIT yok.
- **Land detector:** sert temasta 1.05 s, yumuşak temasta (W2, 0.30 m/s)
  4.6-4.8 s sonra `landed` diyor.

## Adım 2 — K1 sabit hız (32 bölüm, temiz sistemde yeniden)

| Hız | Bölüm | Başarılı | Duvar süresi, ortanca | Temas hızı: W2-W4 / W5 |
|---|---|---|---|---|
| 0.4 m/s | 8 | 7 + 1 sim açılmadı | 86-106 s | 0.29-0.30 / 0.49-0.51 m/s |
| 0.7 m/s | 8 | 8 | 77-90 s | 0.30 / 0.50 m/s |
| 1.0 m/s | 8 | 8 | 74-83 s | 0.29-0.31 / 0.50 m/s |
| 1.5 m/s | 8 | 8 | 72-79 s | 0.30-0.31 / 0.50 m/s |

Toplam duvar süresi 43.5 dk.

- **`k1_v0.4_veri_w4_t1`:** PX4 açılmadı (`run_sim`: "PX4 acilmadi").
  `px4.log` sonraki bölümlerin altında kaldı; `kosu.sh` artık bu durumda onu
  da bölüme kopyalıyor. Takılı kalan `px4` ve başlangıç kabukları işaretle
  kapatıldı, sonraki bölüm normal kalktı. Bu bölüm adımların sonunda
  yeniden uçurulacak.
- **EKF sağlığı (31 bölüm):** vz_ekf − vz_gercek RMS 0.01-0.04 m/s, yükseklik
  kayması ≤ 0.09 m, maske yaşı p50 18-24 ms. Adım 1 ile aynı.
- **W5 (devir yok, 2.5 m altında 0.5 m/s):** 8/8'de COMMIT yok. Temas
  0.49-0.51 m/s, temasta `h_ekf − h_gercek_hedef` 3.99-4.04 m.

**Sabit referans takibi** (VALIDATE'in ilk 2 s'si hariç, devre kadar; W5'te
son 0.5 m/s'lik kısım hariç):

| Hız | Bölüm | Süre / bölüm | vz_gercek − v_ref ort / RMS | vz_ekf − v_ref ort / RMS |
|---|---|---|---|---|
| 0.4 | 7 | 29.3 s | −0.002 / 0.007 m/s | +0.000 / 0.005 m/s |
| 0.7 | 8 | 14.6 s | −0.007 / 0.010 m/s | +0.001 / 0.007 m/s |
| 1.0 | 8 | 9.8 s | −0.011 / 0.013 m/s | +0.003 / 0.009 m/s |
| 1.5 | 8 | 6.2 s | −0.032 / 0.034 m/s | −0.006 / 0.008 m/s |

- **İç döngü sabit hızı 1 cm/s mertebesinde tutuyor.** 1.5 m/s'de gerçek
  hız ~3 cm/s düşük kalıyor.
- **EKF bunu görmüyor:** vz_ekf − v_ref ~0. Fark EKF'nin hız kestiriminde,
  PI'da değil.

## Adım 3 — K2 kâhin sabit ıraksama (24 bölüm, temiz sistemde yeniden)

| D* | Bölüm | Başarılı | Duvar süresi, ortanca | Temas hızı: W2-W4 / W5 |
|---|---|---|---|---|
| 0.2 | 8 | 8 | 72-82 s | 0.28-0.30 / 0.48-0.50 m/s |
| 0.35 | 8 | 7 + 1 mod devreye girmedi | 68-80 s | 0.29-0.31 / 0.50 m/s |
| 0.5 | 8 | 8 | 70-82 s | 0.28-0.31 / 0.48-0.49 m/s |

Toplam duvar süresi 33.8 dk.

- **`k2_d0.35_veri_w4_t1`:** mod PX4'e kaydoldu, kalkış oldu, ama
  "Emergency Landing modu seciliyor" komutu hiç etki etmedi. Araç 240 s
  boyunca 11.7 m'de `nav_state 4`'te (loiter) bekledi. Muhtemel sebep:
  `run_sim.sh`'nin tek seferlik `ros2 topic pub -1` mod komutu kayboldu
  (best effort). Bu bölüm sonda yeniden uçurulacak.
- **EKF sağlığı (23 bölüm):** vz hata RMS 0.02-0.11 m/s, yükseklik kayması
  ≤ 0.27 m (bir bölüm). Kâhin desenleri hızlı değiştiği için K1'den biraz
  yüksek, ama sızıntı dönemindeki 0.2-1.2'nin çok altında.
- **W5:** 6/6'da COMMIT yok. Temas 0.48-0.50 m/s, temasta
  `h_ekf − h_gercek_hedef` 3.92-4.04 m.

**Sabit ıraksama gerçekte ne kadar uçuluyor?** Yasa `D*·h`, [0.3, 1.5]
içinde kırpılıyor ve 2.5 m'de devrediliyor. Bu yüzden sabit ıraksama yalnız
`1.5/D*` ile 2.5 m arasında:

| D* | Bölüm | Tavanda (1.5 m/s), ort | Sabit ıraksamada, ort | Gerçekleşen D ort | D − D* RMS |
|---|---|---|---|---|---|
| 0.2 | 8 | 4.6 s | 5.6 s | 0.197 1/s | 0.007 1/s |
| 0.35 | 7 | 7.1 s | 1.6 s | 0.353 1/s | 0.004 1/s |
| 0.5 | 8 | 7.6 s | 0.4 s | 0.507 1/s | 0.013 1/s |

- **Pencere içinde takip çok iyi.**
- **Ama D* = 0.5 kolu pratikte "1.5 m/s ile in, 3 m'de 0.4 s ıraksa, devret".**
  D* = 0.35 de 1.6 s.
- **Uzun sabit ıraksama örneği isteniyorsa iki seçenek, karar senin:**
  - devir irtifası daha alçak (`veri_devir_irtifasi`, şu an şartnamedeki
    2.5 m),
  - ya da yalnız D* = 0.2 kolu esas alınır.

## Adım 4 — K5 rüzgârlı: önce etiket kalibrasyonu

**İlk çift** (W4, tohum 1, aynı model `x500_seg_cam_down_ruzgar`, aynı
başlangıç, K5 deseni A = 0.6): rüzgârlı bölüm ile rüzgârsız eşi.

| Bölüm | WindEffects (etkin) | roll ort / RMS | pitch ort / RMS | Eşine göre eğim farkı | Yatay sapma p95 / en çok |
|---|---|---|---|---|---|
| rüzgârsız eş (veri_w4) | — | −0.20 / 0.26° | −0.01 / 0.12° | — | 0.06 / 0.16 m |
| 2.5 m/s, ölçek 1.0 | 1.0 | −15.07 / 15.10° | −3.04 / 3.07° | **15.2°** (~5.5 N) | 0.23 / 1.16 m |
| 2.5 m/s, WindEffects kapalı | ~0 | −1.86 / 1.88° | −0.22 / 0.26° | 1.7° (~0.59 N) | 0.08 / 0.43 m |
| 2.5 m/s, SDF 0.075 | 0.0056 | −1.92 / 1.94° | −0.19 / 0.24° | 1.7° | 0.06 / 0.41 m |
| **2.5 m/s, etkin 0.075 (SDF 0.2739)** | 0.075 | −2.85 / 2.86° | −0.31 / 0.33° | **2.67°** (~0.94 N) | 0.06 / 0.13 m |

- **Etiket boş değildi, fazla güçlüydü:** 1.0'da 15° yatış, fiziksel olarak
  ~8 m/s rüzgâr gibi. Bu bölüm veri setinde değil,
  `~/eland_veri/_ruzgar_kalibrasyon/` altında.
- **PX4 motor modeli rüzgârı zaten görüyor:** WindEffects kapalıyken 0.59 N
  rotor sürüklemesi var. x500'ün `rotorDragCoefficient` (8.06e-5) ve
  `motorConstant` değerlerinden asılı uçuşta beklenen 4 × 8.06e-5 × ~757 rad/s
  × 2.5 m/s ≈ 0.61 N.
- **gz-sim 8 sabit ölçeğin karesini alıyor:** `MakeConstantScalingFactor(v)`
  → `AdditivelySeparableScalarField3d(k = v/3, p = q = r = v)`, değerlendirme
  `k·(p+q+r) = v²` (gz-math `AdditivelySeparableScalarField3.hh:78`). 1.0'da
  görünmüyor. 0.075 yazınca etkin 0.0056 oldu ve WindEffects ~0.03 N kaldı
  (ölçüldü).
- **Seçim: etkin 0.075.** Motor modelinin üstüne yalnız gövde sürüklemesi
  ekleniyor: 0.06·v² = 0.375 N, 2.5 m/s'de (_tahmin, Cd·A ≈ 0.1 m²).
  WindEffects doğrusal (`F = m·k·Δv`), bu yüzden eşitlik yalnız 2.5 m/s'de
  geçerli.
- **Doğrulama:** öngörülen eğim 2.73°, ölçülen 2.67°. Kuvvet etkin ölçekle
  doğrusal: 0.075'te 0.35 N, 1.0'da 4.9 N.
- **Kayıt:** `dunya_uret.py` artık `--ruzgar-olcek`'i etkin ölçek alıyor ve
  SDF'ye karekökünü yazıyor. Dünya yaml'ında `olcek` / `olcek_sdf`,
  `kosul.yaml`'da `ruzgar_olcek` (etkin) var. `v5.2-ruzgar-kalibrasyon`.

**K5 rüzgârlı, 6 bölüm** (W4 _r2p5, etkin 0.075; basamak 1.2 ve 2.0 m/s,
yani A = 0.6 ve 1.0, ×3): 6/6 tamam, her biri ~136 s duvar.
- **Eğim:** 6 bölümün hepsinde toplam eğim 2.6-2.8°. Roll/pitch dağılımı
  başlığa göre değişiyor.
- **Yatay sapma:** p95 0.06-0.07 m.

| Genlik | Hız kaynağı | Basamak | K ortanca | Ölü zaman θ | t90 | Eğim sınırı ortanca (yukarı / aşağı) |
|---|---|---|---|---|---|---|
| 0.6 rüzgârlı | vz_gercek | 56 | 0.994 | 0.060 s | 0.30 s | 6.01 (6.04 / 5.34) m/s² |
| 0.6 rüzgârsız | vz_gercek | 55 | 0.992 | 0.040 s | 0.28 s | 6.13 (6.16 / 5.41) m/s² |
| 1.0 rüzgârlı | vz_gercek | 56 | 0.992 | 0.060 s | 0.36 s | 7.24 (6.12 / 7.83) m/s² |
| 1.0 rüzgârsız | vz_gercek | 54 | 0.997 | 0.060 s | 0.36 s | 6.67 (6.24 / 7.86) m/s² |

- **2.5 m/s yan rüzgâr dikey tesisi değiştirmiyor:** K, θ ve t90 ölçüm
  çözünürlüğü (20 ms) içinde aynı. Beklenen sonuç: yatay kuvvet dikey
  ekseni ancak eğimin kosinüsüyle (cos 2.7° = 0.999) etkiler.
- **Rüzgârın dikey veriye görünür etkisi yok.** Rüzgârlı veri RL tarafında
  yatay bozucu olarak işe yarar.

## Adım 5 — K4 (12 bölüm, 40 m, W3)

12/12 başarılı. Duvar süresi ortanca 118 s, toplam 23.5 dk. Temas 0.30 m/s.
EKF vz hata RMS 0.02-0.13 m/s.

| | Değer |
|---|---|
| Tur sırası | tek tohumda basamak, çift tohumda çoklu-sinüs önce (6 / 6) |
| Turlar | her biri ~20 s (bir bölümde ikinci tur 19.7 s'de devre ulaştı) |
| VALIDATE | 39.7-50.8 s; sonra 0.3 m/s ile 0-10.8 s, devir 2.35-2.49 m |
| v_ref aralığı | 0.30-1.50 m/s, kırpmasız |
| vz_gercek − v_ref RMS | 0.16-0.23 m/s (basamaklarda iç döngünün geçici yanıtı dahil) |

## Adım 6 — Aşama 5 bozucular (20 bölüm, W3)

20/20 başarılı. Toplam duvar süresi ~27 dk. EKF vz hata RMS 0.02-0.04 m/s.

| Bozucu | Politika | Bölüm | Başarılı | HOLD / ABORT | Aday kaybı | VALIDATE | ort \|ρ_bozuk − ρ_temiz\| | Ek gecikme p50 | Temas |
|---|---|---|---|---|---|---|---|---|---|
| sınır 2 px | K2 0.35 / K1 1.0 | 2 / 2 | 2 / 2 | 0 / 0 | 0 | 9.6 / 13.8 s | 0.000 | 1 ms | 0.30 m/s |
| çevir 0.02 | K2 0.35 / K1 1.0 | 2 / 2 | 2 / 2 | 0 / 0 | 0 | 9.7 / 13.4 s | 0.011-0.012 | 1 ms | 0.30-0.31 m/s |
| kayıp 0.05 | K2 0.35 / K1 1.0 | 2 / 2 | 2 / 2 | 0 / 0 | 0 | 9.5 / 13.6 s | 0.019-0.020 | 1 ms | 0.30 m/s |
| gecikme 0.2 s | K2 0.35 / K1 1.0 | 2 / 2 | 2 / 2 | 0 / 0 | 0 | 9.6 / 13.6 s | 0.000 | 203 ms | 0.30-0.31 m/s |
| tekrar 2 | K2 0.35 / K1 1.0 | 2 / 2 | 2 / 2 | 0 / 0 | 0 | 9.6 / 13.5 s | 0.010-0.011 | 1 ms | 0.30 m/s |

- **Bu kollarda iniş hızını politika veriyor** (kâhin ya da sabit), ρ değil.
  Bozucu yalnız aday seçimini ve kaydedilen ρ'yu etkiliyor.
- **Aday seçimi beş bozucuda da ayakta kaldı.**
- **Asıl çıktı yan yana kaydedilen `rho_temiz` / `rho_bozuk`,
  `view_bounded_bozuk`, `t_alma_bozuk`.** Kontrolcü bunlarla çevrimdışı
  bozulmuş ölçüme karşı denenebilir.
- **Sınır titremesi ortalama ρ'yu değiştirmiyor** (simetrik). Etkisi tek tek
  karelerde.

## Adım 7 — K3 rastgele politika (80 bölüm)

80/80 başarılı (W8 t3 tekrarıyla birlikte). Toplam duvar süresi 109 dk,
bölüm başına ~80 s. Kapsam: W2-W8 ×4 tohum (28) + 30 ada 1. tohumla + 22 ada
2. tohumla (52). EKF vz hata RMS 0.02-0.03 m/s.

- **Politika tohumu her bölümde ayrı:** sabit dünyada `<dünya no><tohum>`
  (21-84), adada `<ada no><tohum>` (20131-20452). İlk liste 30 adaya aynı
  rastgele diziyi veriyordu; uçurulmadan düzeltildi.
- **Temas:** W5'teki 4 bölüm 0.49-0.50 m/s. Diğer 76 bölümün 73'ü
  0.29-0.32 m/s, 3'ü **sert temas** (aşağıda).

**Sert temaslar — mevcut modun davranışı, veri araçlarının değil:**

| Bölüm | COMMIT (gerçek / EKF) | COMMIT'te vz | Temas |
|---|---|---|---|
| k3_parca_veri_ada_t2024_t2 | 13.6 / 13.5 m | 1.33-1.36 m/s, sabit | 1.33 m/s |
| k3_parca_veri_ada_t2029_t1 | 14.6 / 14.6 m | 1.27-1.31 m/s, sabit | 1.27 m/s |
| k3_carpan_veri_ada_t2029_t2 | 6.8 / 6.7 m | 1.10-1.14 m/s, sabit | 1.10 m/s |

- **COMMIT yüksekte girildi.** Mod aday 3 kez kaybolunca "committing anyway"
  ile giriyor (t2024_t2'de günlükte açıkça yazıyor). Diğer ikisinde geçiş
  gerekçesinin üstüne COMMIT'in kendi mesajı yazıldığı için gerekçe kayıtta
  görünmüyor.
- **Hız neden sabit kalıyor:** COMMIT'te `onCandidate` hemen dönüyor
  (`emergency_landing_mode.hpp:622-623`), `_area_ratio` ve `_view_bounded`
  son değerinde donuyor. `descentSpeed` (`:593-618`) `view_bounded` doğruysa
  alan yasasını donmuş ρ ile çalıştırıyor:
  `ceiling·(1 − ρ_donmuş)`, irtifadan bağımsız sabit. Yere kadar
  1.1-1.3 m/s.
- **Karşı örnek:** aynı şekilde yüksekte giren diğer 6 bölümde (4'ü Kol 0
  kör iniş, 2'si K3) `view_bounded` yanlıştı. İrtifa yasası çalıştı, hız
  1.5'ten 0.3'e indi, temas 0.30 m/s.
- **218 bölümde 9 erken COMMIT (> 3 m), 3'ü sert.** Başarı ölçütü hız
  içermediği için üçü de "başarılı" sayıldı.
- **Mevcut koda dokunmadım.** Öneri (onayınla): COMMIT'te alan yasasını
  irtifa yasasıyla sınırlamak, `min(alan, irtifa)`, ya da donmuş ρ yerine
  yalnız irtifa yasası. Bu senin kontrolcü tasarımının konusu.

## Yeniden uçurulacaklar (adımların sonunda)

| Bölüm | Sebep |
|---|---|
| `k1_v0.4_veri_w4_t1` | PX4 açılmadı |
| `k2_d0.35_veri_w4_t1` | mod komutu etki etmedi, loiter'da kaldı |
| `k3_parca_veri_w8_t3` | 0.52 m'lik sınıf sınırı nesnesinin üstünde doğdu (aşağıda) |

**W8 tohum 3, nesnenin üstünde doğuş:**
- `baslangic.py` hedef merkezden 0-4 m ofset çekiyor. W8'de merkezdeki
  2×2 m nesne bu dairenin içinde: tohum 3 (−0.37, −0.96) noktasına, nesnenin
  üstüne düştü.
- EKF orijini ve dinlenme yüksekliği nesnenin tepesinde kaldı, bütün
  `h_gercek_*` 0.5 m kaydı. COMMIT, EKF kuralıyla gerçek 2.62 m'de geldi,
  Gazebo devri 2.5 m'den önce. Araç adaya (geçerli bir noktaya) yumuşak indi,
  ama temas 0.03 m eşiğinin altına hiç inmedi; özet başarısız / "bilinmiyor"
  oldu.
- **Düzeltme:** başlangıç hedef dışındaki ya da yükseltilmiş bir yüzeyin
  üstüne düşerse ofset aynı akıştan yeniden çekiliyor. W5'te 10×10
  platformun köşesi 7.07 m; 6.5-8 m ofset köşeye düşebilir, o da kapsanıyor.
- **Tarama:** W1-W8 ve 45 ada dünyasının hepsi, tohum 1-4. Etkilenen tek çift
  W8 tohum 3'tü. Diğer bütün başlangıçlar aynı kaldı (uçurulmuş bölümlerin
  `dogus` alanıyla karşılaştırıldı).

**Tekrarlar (03:04-03:08):** üçü de başarılı, temas 0.30 m/s. İlk denemeleri
`_karantina/2026-10-04_basarisiz/` altında.

## Veri seti (Aşama 6, `tools/veri/birlestir.py`)

**218 bölüm, `~/eland_veri/tum_ozet.csv`.** Başarılı 195. Kalan 23'ün hepsi
beklenen:
- 19'u K5 / K5r tanımlama (inmiyor),
- 4'ü negatif örnek (W1 ×3, ada t2012).

Ayrıca 6 bölüm "başarılı" sayılıyor ama sert temas:
- W5 Kol 0 ×3, 1.47 m/s,
- K3 ×3, 1.10-1.33 m/s.

Bölme anahtar düzeyinde (85 anahtar): train 62 / val 10 / test 13 (%73 / %12 /
%15). Bölüm düzeyinde 140 / 31 / 47 (%64 / %14 / %22). Fark, anahtarların
bölüm sayılarının eşit olmamasından: bir ada ya da bir dünya+tohum bütünüyle
tek bölmeye gidiyor.

| Kol | train | val | test |
|---|---|---|---|
| Kol 0 | 19 | 5 | 7 |
| K1 | 16 | 4 | 12 |
| K2 | 12 | 3 | 9 |
| K3 | 64 | 6 | 10 |
| K4 | 9 | 3 | 0 |
| K5 (rüzgârsız) | 8 | 0 | 4 |
| K5r (rüzgârlı + eş) | 2 | 0 | 5 |
| Aşama 5 | 10 | 10 | 0 |

- **K4'te ve Aşama 5'te test yok.** Tek dünya (W3) ve az tohum var; anahtar
  dünya+tohum olduğu için bu kollar 2-12 anahtara düşüyor.
- **Aynı (dünya, tohum) farklı kollarda hep aynı bölmede.** Aynı başlangıç
  koşulu bölmeler arasında sızmıyor. Bilinçli bir seçim.
- **Kol bazında dengeli test istenirse** kol katmanlı bir bölme eklenebilir,
  ama o zaman aynı başlangıç farklı bölmelere düşer.

Birleşik dosyalar `_bolme/<bölme>/birlesik_<bölme>.mat`: train 36.9 MB,
val 8.9 MB, test 12.8 MB.

**Temas sonrası devrilme, `kol0_veri_ada_t2010_t1`:** 199 temaslı bölümden
yalnız bu.
- **Olay:** araç 0.30 m/s ile adaya düzgün indi. Temastan 7.5 s sonra
  devrilmeye başladı, motorlar dönerken 62.5 m savruldu.
- **Kayıt:** PX4 `landed` ancak temastan 36.2 s sonra geldi. Dünyada bir
  hareketli kişi var; muhtemelen araca çarptı (doğrulamadım).
- **Ölçüt:** başarı ölçütü (landed + kör değil + hedefte) bunu "başarılı"
  sayıyor.
- **Etki:** alçalma ve temas verisi sağlam, temas sonrası kuyruk çöp.
  **Analizleri `t_temas_gercek`'te kesin.**

---

# Tur 3 — kontrolcü tasarımı için eksikler (2026-10-04)

İstek: diğer sohbetten (A-E). A ve B mevcut koda dokunuyor, **plan yazıldı, onay
bekliyor**. C, D, E çevrimdışı, yapıldı. Çıktılar `~/eland_veri/_tur3/`.

## C — Aşama 5 bozucularının uygulandığının doğrulanması

`tools/veri/bozucu_dogrula.py`; tam tablo `~/eland_veri/_tur3/bozucu_dogrula.md`.

- **Kayıt düzeni:** çevrimiçi bozuk maskelerin kendisi kaydedilmemiş; yalnız
  öznitelikleri (`rho_bozuk`, `view_bounded_bozuk`, `t_alma_bozuk`) var.
  Piksel sayımı, `bozucu.py`'nin kendi `disturb()` kodu kayıtlı temiz karelere
  çevrimdışı uygulanarak yapıldı (aynı seviye, aynı tohum; çevrimiçi karelerin
  birebiri değil).
- **Yuvarlama:** Tur 2 raporundaki "sınır titremesi 0.000" üç ondalığa
  yuvarlanmış değerdi.

**`d = rho_bozuk − rho_temiz`** (kayıtlı, yakalama damgasıyla eşlenmiş;
4'er bölüm, aralıklar bölümler arası):

| Bozucu | Aralık | max \|d\| | p99 \|d\| | ort \|d\| | d ≠ 0 kare oranı |
|---|---|---|---|---|---|
| sınır 2 | tüm kayıt | 0.00135-0.00182 | 0.00106-0.00118 | 0.00020-0.00023 | 0.475-0.555 |
| sınır 2 | VALIDATE | 0.00104-0.00154 | 0.00095-0.00130 | 0.00036-0.00043 | 0.879-0.992 |
| çevir 0.02 | tüm kayıt | 0.887-1.000 | 0.079-0.116 | 0.0106-0.0121 | 0.681-0.751 |
| çevir 0.02 | VALIDATE | 0.098-0.875 | 0.017-0.238 | 0.0070-0.0184 | 1.000 |
| kayıp 0.05 | tüm kayıt | 1.000 | 0.809-0.999 | 0.0162-0.0219 | 0.029-0.040 |
| kayıp 0.05 | VALIDATE | 0.534-1.000 | 0.233-0.936 | 0.0092-0.0339 | 0.034-0.083 |
| gecikme 0.2 | tüm kayıt / VALIDATE | 0 | 0 | 0 | 0 |
| tekrar 2 | tüm kayıt | 1.000 | 0.036-0.058 | 0.0097-0.0113 | 0.329-0.356 |
| tekrar 2 | VALIDATE | 0.029-0.061 | 0.029-0.057 | 0.0060-0.0100 | 0.623-0.664 |

**Değişen piksel** (VALIDATE'ten eşit aralıklı 4 kare / bölüm, 76800 pikselden):

| Bozucu | Değişen piksel | Merkez bölge pikseli, temiz → bozuk |
|---|---|---|
| sınır 2 | 0-913 (2.5 m'de kare tek sınıf: 0) | en çok 78 piksel fark |
| çevir 0.02 | her karede 1536 | 86-1286 piksel azalma |
| kayıp 0.05 | örneklenen 16 karede 0 (%5 tetiklenir); seviye 1.0 ile zorla: bölgenin tamamı (5976-76800) | zorla: bölge → 0 |
| gecikme 0.2 | 0 (yalnız 0.2 s geç) | aynı |
| tekrar 2 | 0-2626 (tutulan karede 0) | en çok 2626 piksel fark |

**view_bounded** (kayıtlı; temiz / bozuk):
- **VALIDATE'te:**
  - t1 bölümlerinde temiz 0.660-0.695;
  - t2 bölümlerinde temiz 0.355-0.494;
  - bozuk tarafta fark en çok −0.059 (kayıp), +0.024 (tekrar).
- **Tüm kayıtta:** temiz 0.221-0.406.
- **VALIDATE'te ortanca `rho_temiz`:** 0.229-0.350.

## D — eğiklik ve ρ

`tools/veri/egiklik_rho.py`; çıktılar `~/eland_veri/_tur3/egiklik_rho.md`,
bölüm başına `merkez_guvensiz_rho0_bolum.csv`.

- **Eğiklik** `arccos(cos roll · cos pitch)`. roll/pitch `maske_olaylari.csv`'de
  yok; `duzenli.csv`'deki `roll`, `pitch` (rad, `vehicle_attitude`, 50 Hz)
  maskenin `t_yakalama`'sına doğrusal ara değerlendi.
- **Kareler:** yalnız `view_bounded = 1` ve `rho > 0` (`rho_hesap` ancak
  bölge sığarken anlamlı).

**`rho − rho_hesap`:**

| Kol | Aralık | Eğiklik | Kare | Ort | Ortanca | RMS | p95 \|·\| | Göreli ort / ortanca |
|---|---|---|---|---|---|---|---|---|
| K1 | tüm | < 5° | 3572 | +0.0002 | +0.0000 | 0.0014 | 0.0016 | +0.001 / +0.000 |
| K1 | tüm | ≥ 5° | 139 | +0.0079 | +0.0001 | 0.0179 | 0.0358 | +0.027 / +0.004 |
| K1 | VALIDATE | < 5° | 2472 | +0.0003 | +0.0000 | 0.0015 | 0.0017 | +0.001 / +0.000 |
| K1 | VALIDATE | ≥ 5° | 72 | +0.0123 | +0.0003 | 0.0204 | 0.0439 | +0.034 / +0.006 |
| K3 | tüm | < 5° | 7729 | −0.0004 | −0.0003 | 0.0019 | 0.0033 | −0.002 / −0.003 |
| K3 | tüm | ≥ 5° | 664 | +0.0038 | +0.0036 | 0.0121 | 0.0250 | +0.037 / +0.037 |
| K3 | VALIDATE | < 5° | 3227 | −0.0002 | −0.0001 | 0.0019 | 0.0038 | −0.000 / −0.000 |
| K3 | VALIDATE | ≥ 5° | 220 | +0.0021 | +0.0032 | 0.0098 | 0.0176 | +0.028 / +0.033 |

**VALIDATE'te eğiklik:**
- K1: ortanca 0.28°, p95 2.44°, en çok 9.57°, ≥ 5° oranı 0.013.
- K3: ortanca 0.36°, p95 7.89°, en çok 43.7°, ≥ 5° oranı 0.084.

**Merkez piksel güvenli değil ve ρ = 0 olan kare oranı** (bölüm başına
CSV'de):

| Kol | Bölüm | Tüm kayıt ortanca / en çok | VALIDATE ortanca / en çok (> 0 olan bölüm) | VALIDATE, temastan önce en çok (> 0 olan bölüm) | Merkez güvensiz ama ρ ≠ 0 |
|---|---|---|---|---|---|
| K1 | 32 | 0.313 / 0.667 | 0.000 / 0.299 (8) | 0.043 (4) | 0 kare |
| K3 | 80 | 0.299 / 0.666 | 0.000 / 0.312 (16) | 0.221 (12) | 0 kare |

- **Kayıt kalkıştan önce, yerde başlıyor.**
- **VALIDATE'te > 0 olan 24 bölümün 12'si W5.** W5'te veri kipi devretmediği
  için mod temastan sonra da VALIDATE'te kalıyor. Örnek
  `k3_carpan_veri_w5_t2`: 44 kare, hepsi temastan sonra, `h_kamera_gercek`
  0.09 m, merkez sınıfı 2.
- **Ada örnekleri:** `k3_carpan_veri_ada_t2016_t1` 25 kare, 7.6-14.4 m,
  sınıf 2; `k3_parca_veri_ada_t2042_t1` 9 kare, 11.4-12.4 m.

## E — örnek MATLAB seti

`tools/veri/ornek_mat.py` → `~/eland_veri/_ornek_matlab/` (Windows'tan
`\\wsl.localhost\ubuntu\home\arda\eland_veri\_ornek_matlab`), zip'i
`~/eland_veri/_ornek_matlab.zip` (2.6 MB).

| Dosya | KB | duzenli (sütun × satır) | maske | karar |
|---|---|---|---|---|
| k5_A0.6_acik_alan_t1001.mat | 608 | 37 × 5023 | 22 × 951 | 12 × 177 |
| k5_A1.0_acik_alan_t1001.mat | 598 | 37 × 5014 | 22 × 923 | 12 × 175 |
| k1_v0.7_veri_w3_t1.mat | 392 | 48 × 2731 | 26 × 537 | 12 × 99 |
| k1_v1.5_veri_w3_t1.mat | 306 | 48 × 2162 | 26 × 412 | 12 × 76 |
| k2_d0.2_veri_w3_t1.mat | 353 | 48 × 2428 | 26 × 468 | 12 × 84 |
| a5_k2d0.35_veri_w3_t1_gecikme0.2.mat | 306 | 48 × 2220 | 26 × 426 | 12 × 73 |

- **Seçimler:**
  - K2'den D* = 0.2: sabit ıraksama penceresi en uzun kol (5.6 s).
  - Aşama 5'ten 0.2 s gecikme: aynı dosyada `rho_temiz` / `rho_bozuk` ve
    `t_alma_bozuk` var.
  - K5 dosyaları Tur 1 kaydedicisinden; `x_gercek` gibi sonradan eklenen
    sütunlar yok (37 sütun).
- **İçerik:** her `.mat`'ta `duzenli`, `maske`, `karar`, `gecis`, `bilgi`
  (bölüm ve anlar), `ozet_json`, `kosul_yaml`. Kaydedicinin sütun adları
  aynen. Her satırda tekrar eden 4 metin sütunu `bilgi`'ye taşındı. Yanında
  `<ep_id>_sozluk.md` (koşullar, anlar, okuma örneği, sütun tablosu
  `data_dictionary.md`'den) ve `BENIOKU.md`.
- **Doğrulama:** her dosya `scipy.io.loadmat` ile geri okundu; her sütunun
  satır sayısı ve NaN sayısı CSV ile aynı.
- **Denenmedi:** MATLAB bu makinede yok, dosyalar MATLAB'da açılmadı. Bir alan
  adı 31 karakteri aşıyor (`bilgi.temas_dikey_hiz_gercek_hesap_mps`, 32);
  MATLAB R2006a'dan beri 63'e kadar kabul ediyor.

## A ve B — uygulandı (2026-10-04, onaylı)

**Kararlar** (diğer sohbet):
- A: yeni `GoruntuKapsami` mesajı, `publish_rho` varsayılan false.
- B: tavan donmuş alandan.
- İki parametre `false` olarak `eland_params.yaml`'a yazıldı.
- Mod `/eland/rho`'yu kullanmıyor.
- **İstenen doğrulama:** B için ayar başına ≥ 5 tohum, temas hızının
  ortancası ve en büyüğü; kapalıyken eski davranış koşuyla.

**Değişen dosyalar:**
- `src/eland_msgs/msg/GoruntuKapsami.msg` (yeni) ve `CMakeLists.txt`.
- `detector_node.py`: içe aktarma, `publish_rho` / `rho_topic`, koşullu
  yayıncı, `on_mask` sonunda yayın.
- `emergency_landing_mode.hpp`: `commit_irtifa_yasasi`,
  `commitAltitudeSpeed()`, COMMIT'te seçim.
- `eland_params.yaml`: iki `false` satırı.
- **Kendi araçlarım:**
  - `kaydedici.py`: `/eland/rho` → `rho_yayini.csv`, `rho_yayini_sayisi`.
  - `kosu.sh`: `DUGUM_BILGI=1`.
  - `tur3_dogrula.py`.

Derleme: `colcon build --packages-select eland_msgs eland_mapping eland_mode`.
Önce kurulu dosyaların kaynakla aynı olduğu kontrol edildi; derleme yalnız bu
değişiklikleri taşıyor.

**Doğrulama koşuları:** veri setinin dışında, `~/eland_veri/_tur3_dogrulama/`.
- 26 bölüm. 1'inde (K3 tekrarı, kapalı, `t2029_t2`) PX4 kalkmadı ("irtifa
  0 m"); o bölüm yeniden uçuruldu, ilk deneme `_basarisiz/` altında.
- Tablo: `~/eland_veri/_tur3/tur3_dogrula.md`.

**1. İki parametre kapalı (varsayılan), Kol 0, kayıtlı bölümlerle:**

| Bölüm | Durum dizisi | COMMIT h_ekf kayıtlı / yeni | COMMIT h_gerçek kayıtlı / yeni | Temas kayıtlı / yeni | VALIDATE→landed kayıtlı / yeni | `/eland/rho` mesajı |
|---|---|---|---|---|---|---|
| kol0_veri_w2_t1 | aynı | 1.95 / 1.98 m | 1.99 / 2.03 m | 0.31 / 0.29 m/s | 25.6 / 26.2 s | 0 |
| kol0_veri_w2_t2 | aynı | 1.93 / 1.97 | 1.98 / 1.99 | 0.30 / 0.29 | 22.1 / 21.9 | 0 |
| kol0_veri_w2_t3 | aynı | 1.96 / 1.98 | 1.99 / 2.07 | 0.30 / 0.31 | 22.9 / 22.9 | 0 |
| kol0_veri_w3_t1 | aynı | 1.97 / 1.94 | 2.04 / 2.09 | 0.30 / 0.31 | 23.0 / 23.0 | 0 |
| kol0_veri_w3_t2 | farklı: APPROACH atlandı | 1.93 / 1.95 | 2.03 / 2.01 | 0.30 / 0.31 | 19.8 / 19.5 | 0 |
| kol0_veri_w3_t3 | aynı | 1.95 / 1.94 | 2.05 / 1.99 | 0.31 / 0.31 | 19.7 / 19.9 | 0 |

- **W3 t2:** eski sürümle kaydedilmiş 20 W3-tohum-2 bölümünde (her kol)
  APPROACH 11'inde atlanmış, 9'unda girilmiş. VALIDATE'ten önceki kısım koldan
  bağımsız.
- **Kapalıyken grafik** (bölüm ortasında `ros2 topic info /eland/rho`):
  `Publisher count: 0`. Konu yalnız kaydedici dinlediği için görünüyor.
- **Dedektörün yayıncıları kapalıyken:** `/eland/candidate`,
  `/eland/trajectory_block`, `/parameter_events`, `/rosout`. `/eland/rho`
  yok.

**2. A açık** (`detector_node.publish_rho: true`, Kol 0 W2 t1-t3):

| Bölüm | Mesaj / maske | Hız tüm / VALIDATE | Yakalama → `/eland/rho` alma p50 / p90 | Maske alma → `/eland/rho` alma p50 / p90 | ρ farkı (yayın − kaydedici), en büyük | view_bounded uyuşmayan | Durum dizisi |
|---|---|---|---|---|---|---|---|
| t1 | 494 / 494 | 10.00 / 9.99 Hz | 19.5 / 41.2 ms | 0.9 / 1.4 ms | 0.000001 (CSV yuvarlaması) | 0 | kayıtlıyla aynı |
| t2 | 424 / 424 | 9.79 / 9.87 Hz | 19.5 / 40.1 ms | 0.9 / 1.4 ms | 0.000001 | 0 | aynı |
| t3 | 427 / 427 | 9.95 / 9.86 Hz | 19.3 / 38.8 ms | 0.9 / 1.4 ms | 0.000001 | 0 | aynı |

- **Üçü birlikte:** yakalamadan `/eland/rho`'nun alınmasına p50 19.5 ms, p90
  39.6 ms. Dedektörün eklediği p50 0.9 ms, p90 1.4 ms.
- **Alma zamanları** kaydedicinin sim saatiyle. Yayıncının kendi gönderme anı
  ölçülmedi.
- **Grafik açıkken:** `Publisher count: 1`, yayıncı `detector_node`,
  `BEST_EFFORT`.
- **Bu bölümde düğüm listesi alınamadı:** `ros2 node info /detector_node`
  `--no-daemon` ile düğümü bulamadı ("Unable to find node").

**3. B: zorlanmış erken COMMIT** (`landing_altitude: 10.0` yalnız test için,
W3, kalkış 18 m, 5 tohum × 2 ayar):

| Ayar | Bölüm | COMMIT h_gerçek | COMMIT'te alan yasası | v_cmd COMMIT girişi → temastan önce | Temas hızı ortanca / en büyük / en küçük |
|---|---|---|---|---|---|
| kapalı | 5 | 10.06-10.16 m | %100 | 1.18-1.19 → 1.18-1.19 m/s (sabit) | **1.20 / 1.22 / 1.18 m/s** |
| açık | 5 | 10.02-10.16 m | %0 | 1.50 → 0.30 m/s | **0.30 / 0.31 / 0.30 m/s** |

10 bölümün 10'u başarılı (başarı ölçütü hız içermiyor).

**4. B: sert temaslı 3 K3 bölümü, iki ayarla yeniden:**

| Ayar | Bölüm | COMMIT h_gerçek | COMMIT'te alan yasası | Temas | İlk uçuştaki temas |
|---|---|---|---|---|---|
| kapalı | k3_carpan_veri_ada_t2029_t2 | 2.47 m (normal devir) | %0 | 0.30 m/s | 1.10 m/s |
| kapalı | k3_parca_veri_ada_t2024_t2 | 2.36 m (normal devir) | %0 | 0.29 | 1.33 |
| kapalı | k3_parca_veri_ada_t2029_t1 | **13.94 m (erken)** | %100 | **1.27** | 1.27 |
| açık | k3_carpan_veri_ada_t2029_t2 | 2.45 m (normal devir) | %0 | 0.29 | 1.10 |
| açık | k3_parca_veri_ada_t2024_t2 | **14.31 m (erken)** | %0 | **0.30** | 1.33 |
| açık | k3_parca_veri_ada_t2029_t1 | **14.66 m (erken)** | %0 | **0.30** | 1.27 |

Erken COMMIT tekrarı rastlantıya bağlı. Kapalıda 3'te 1, açıkta 3'te 2
kez oldu.
- Kapalıyken erken giren bölüm ilk uçuştakiyle aynı hızda (1.27 m/s) yere
  vurdu.
- Açıkken erken giren ikisi 0.30 m/s ile indi.

**A — ρ'nun maske hızında ayrı yayını (`/eland/rho`).**

Değişecek dosyalar:
1. `src/eland_msgs/msg/GoruntuKapsami.msg` (yeni): `std_msgs/Header header`
   (damga = maskenin yakalama damgası), `float32 rho`, `bool view_bounded`.
2. `src/eland_msgs/CMakeLists.txt`: `rosidl_generate_interfaces`'e bir satır.
   Mevcut mesajlar değişmiyor.
3. `src/eland_mapping/eland_mapping/detector_node.py`:
   - `publish_rho` (false) ve `rho_topic` (`/eland/rho`) parametreleri
     (`:113-116` yanı).
   - Yayıncı yalnız açıkken oluşturuluyor (`:300` yanı).
   - `on_mask` sonunda (`:378`) aynı maskenin başlığıyla yayın, ~6 satır.
   - ρ hesabı, aday mesajı ve `on_map` aynı.
4. Kendi aracım `kaydedici.py`: konu varsa alma zamanlarını kaydeder.

**Mod bu konuyu dinlemeyecek** (istek yalnız yayın).

Doğrulama:
- **Kapalıyken:** konu yok, düğümün yayıncı listesi aynı. Kol 0 W2 t1-t3
  yeniden uçurulup kayıtlılarla karşılaştırılacak (geçiş dizisi, COMMIT
  irtifası, temas hızı, süre).
- **Açıkken:** aynı 3 bölümde yayın hızı ve iki gecikmenin p50 / p90'ı.
  - yakalama → `/eland/rho` alma,
  - maskenin alınması → `/eland/rho` alma.
- **Ayrıca:** yayınlanan ρ, aynı maskeden hesaplananla aynı mı.

**B — `commit_irtifa_yasasi` (false).**

Yalnız `emergency_landing_mode.hpp`:
- **Parametre:** bool parametre ve üye.
- **COMMIT (`:480`):** açıkken `descentSpeed` yerine yeni bir yardımcı;
  kapalıyken satır aynı çağrı.
- **Yardımcı:** `v = clamp(descent_altitude_gain · h_ekf, descent_min_mps,
  tavan)`.
  - Tavan `descentSpeed`'in irtifa dalıyla aynı: alan ölçümü varsa
    `clamp(descent_size_gain·√area, min, max)`, yoksa `descent_max_mps`.
  - Yeni sabit yok. `area_law_active` ve son komut / tavan güncellenir.
- **Bilinen sınır:** W5 gibi yükseltilmiş hedefte EKF yüksekliği ~4 m kalır,
  B bunu çözmez.

Doğrulama:
- **Kapalıyken:** A'daki Kol 0 koşusu.
- **Açıkken:** sert temasların tekrarı rastlantıya bağlı (aday 3 kez
  kaybolmalı). Bu yüzden erken COMMIT mevcut bir parametreyle zorlanacak:
  yalnız test için `landing_altitude: 8.0`, W3'te (bölge kadraja sığsın),
  3 tohum × {kapalı, açık}. COMMIT'teki hız profili ve temas hızı
  karşılaştırılacak.
- **Ayrıca:** sert temas yaşayan 3 K3 bölümü her iki ayarla yeniden
  uçurulacak.

---

# Tur 4 — Tur 3 sonucuna kararlar (2026-10-04)

**Kararlar** (diğer sohbet):
1. Mod `/eland/rho`'yu şimdilik kullanmıyor. Tasarım Simulink'te
   doğrulanınca ayrı madde gelecek. **Yapılan bir şey yok.**
2. `commit_irtifa_yasasi` varsayılanı `true` (yaml'da); `false` karşılaştırma
   için kalıyor. Yeniden doğrulama: Kol 0, W2-W6 ve adalar, ≥ 20 bölüm; temas
   hızı ortanca / en büyük / sert temas sayısı (≥ 0.5 ve ≥ 1.0 m/s), açık ve
   kapalı yan yana.
3. W5 kapsam dışı değil; tasarlanacak gözlemcinin test senaryosu olacak.
   **Yapılan bir şey yok.**
4. Başarı ölçütüne temas hızı: 0.5 ve 1.0 m/s iki seviye, ortanca ve en büyük
   hızla birlikte. Mevcut 218 bölüm yeniden puanlanacak, yeni koşu yok.

Kurallar aynı: onaylı, parametreli; varsayılan davranış değişiyorsa açıkça
yazılacak.

## Madde 4 — temas hızıyla yeniden puanlama (tamam)

**Varsayılan değişmedi.** `basarili` aynı anlamda kaldı (landed + kör değil +
temas yeri uygun). Yanına iki alan eklendi:
- `basarili_v10`: başarılı **ve** temas hızı < 1.0 m/s.
- `basarili_v05`: başarılı **ve** temas hızı < 0.5 m/s.

Temas hızı yoksa ikisi de false. "Sert temas" = hız ≥ seviye. Eşikler tek
yerde: `tools/veri/basari.py`.

**Değişen dosyalar** (yalnız veri araçları, uçuş yığınına dokunulmadı):
- `tools/veri/basari.py` (yeni): iki seviye ve `temas_seviyeleri()`.
- `kaydedici.py`: yeni bölümler iki alanı `basarili`'nin hemen ardından
  kendisi yazıyor.
- `ozet_yenile.py`: başarıyı yeniden hesapladığı yerde iki alanı da.
- `birlestir.py`: `tum_ozet.csv` ve `birlesik_*.mat`'e iki sütun, değerler
  `basari.py`'den.
- `temas_puanla.py` (yeni): bölümlerin `ep_ozet.json`'una iki alanı yazıyor,
  raporu çıkarıyor (`~/eland_veri/_tur4/temas_puanla.md`).
- `data_dictionary.md`.

**Doğrulama:**
- **Yedek:** önce `~/eland_veri/_tur4/ep_ozet_yedek_tur4oncesi.tar.gz` (218
  `ep_ozet.json`) ve `tum_ozet_tur4oncesi.csv` alındı.
- **`ep_ozet.json`:** yedekle karşılaştırıldı. 218 dosyaya yalnız
  `basarili_v05` / `basarili_v10` eklendi, eski alanlarda 0 fark.
- **`birlestir.py` yeniden:** 218 satır, aynı bölümler, eski sütunlarda 0
  fark. Bölme aynı (train 140 / val 31 / test 47). `birlesik_test.mat`'in `ep`
  yapısında iki alan var (`scipy.io.loadmat` ile okundu).
- **`kaydedici.py`:** Tur 4'ün ilk doğrulama koşusu
  (`kapali/kol0_veri_w2_t1`) iki alanı kendisi yazdı.
- **Örnek MATLAB seti** (`_ornek_matlab`, Tur 3 E) yeniden üretilmedi, bu
  alanlar onda yok.

**Sonuç: 195 başarılı bölümün 189'u 1.0 seviyesini, 183'ü 0.5 seviyesini
geçiyor.**

| | Bölüm | Başarılı (eski) | Başarılı, v < 1.0 | Başarılı, v < 0.5 | Temas ortanca | En büyük | v ≥ 0.5 | v ≥ 1.0 |
|---|---|---|---|---|---|---|---|---|
| Toplam | 218 | 195 | 189 | 183 | 0.30 m/s | 1.48 m/s | 12 | 6 |
| K5/K5r ve negatifler hariç | 195 | 195 | 189 | 183 | 0.30 | 1.48 | 12 | 6 |

Kol başına:

| Kol | Bölüm | Başarılı (eski) | v < 1.0 | v < 0.5 | Ortanca | En büyük | v ≥ 0.5 | v ≥ 1.0 |
|---|---|---|---|---|---|---|---|---|
| kol0 | 31 | 27 | 24 | 24 | 0.30 | 1.48 | 3 | 3 |
| k1_v0.4 / v0.7 / v1.0 / v1.5 | 8 + 8 + 8 + 8 | 8 her biri | 8 her biri | 7 her biri | 0.30-0.31 | 0.50-0.51 | 1 her biri | 0 |
| k2_d0.2 / d0.35 | 8 + 8 | 8 her biri | 8 her biri | 7 her biri | 0.30 | 0.50 | 1 her biri | 0 |
| k2_d0.5 | 8 | 8 | 8 | 8 | 0.30 | 0.49 | 0 | 0 |
| k3_carpan | 40 | 40 | 39 | 39 | 0.31 | 1.10 | 1 | 1 |
| k3_parca | 40 | 40 | 38 | 38 | 0.30 | 1.33 | 2 | 2 |
| k4 | 12 | 12 | 12 | 12 | 0.30 | 0.31 | 0 | 0 |
| a5_k1v1.0, a5_k2d0.35 | 10 + 10 | 10 her biri | 10 her biri | 10 her biri | 0.30 | 0.31 | 0 | 0 |
| k5 / k5r (6 kol) | 19 | 0 | 0 | 0 | — (inmiyor) | — | 0 | 0 |

Kol 0'da W1 ×3 ve t2012 negatif örnek (başarısızlık beklenen). Diğer Kol 0
dünyalarında temas 0.29-0.31 m/s, W5 hariç.

**Seviyelerin düşürdüğü 12 bölüm:**

| Bölüm | Temas hızı | v < 1.0 | v < 0.5 |
|---|---|---|---|
| kol0_veri_w5_t3 / t1 / t2 | 1.479 / 1.472 / 1.467 m/s | hayır | hayır |
| k3_parca_veri_ada_t2024_t2 | 1.333 | hayır | hayır |
| k3_parca_veri_ada_t2029_t1 | 1.273 | hayır | hayır |
| k3_carpan_veri_ada_t2029_t2 | 1.096 | hayır | hayır |
| k1_v0.4_veri_w5_t1 | 0.507 | evet | hayır |
| k2_d0.2_veri_w5_t2, k2_d0.35_veri_w5_t1 | 0.504, 0.504 | evet | hayır |
| k1_v0.7_veri_w5_t1 | 0.503 | evet | hayır |
| k1_v1.0_veri_w5_t2 | 0.502 | evet | hayır |
| k1_v1.5_veri_w5_t2 | 0.501 | evet | hayır |

- **v ≥ 1.0 (6):** Tur 2'de "başarılı sayılan sert temas" diye bildirilen
  altı bölüm.
  - Kol 0 W5 ×3: COMMIT'e hiç girilmedi (EKF yüksekliği platformun ~4 m
    üstünde kalıyor).
  - K3 ×3: erken COMMIT (Gazebo hedef yüksekliği 6.8 / 13.6 / 14.6 m'de).
    Tur 3'te B ile yeniden uçurulanlar bunlar.
- **0.5 ≤ v < 1.0 (6): hepsi K1/K2'nin W5 bölümleri, ve bu seviye orada
  gürültüyle bölüyor.**
  - Veri kipindeki 18 W5 bölümü (K1, K2, K3) `--devir-yok --son-hiz 0.5`
    ile uçtu: politika sona kadar 0.5 m/s istiyor.
  - Temas hızları 0.476-0.507 m/s. 6'sı 0.500'ün üstünde, 12'si altında.
  - Yani bu bölümlerde 0.5 seviyesini geçmek ya da kalmak ±0.01 m/s'lik
    farka bağlı.
- **Dağılım üç kümeli:**
  - ~0.30 m/s: modun alt sınırı `descent_min_mps`.
  - 0.48-0.51 m/s: W5 veri kipi.
  - 1.10-1.48 m/s: sert temaslar.
  - 0.507 ile 1.096 m/s arasında temas yok.

## Madde 2 — `commit_irtifa_yasasi` varsayılanı `true` (uygulandı, doğrulama sürüyor)

**Varsayılan uçuş davranışı değişti.**
- `eland_params.yaml`: `commit_irtifa_yasasi: true`, yanında iki yorum.
- **Kod değişmedi.** Düğümün kendi varsayılanı `false`: bu yaml olmadan
  başlatılan mod eski yasayla uçar.
- **Kurulu yaml:** `colcon build --packages-select eland_sim` ile yenilendi.
  - Etkileşimli `run_sim.sh` (`--params` olmadan) kurulu yaml'ı okuyor. Kurulu
    kopya Tur 3'ten beri eskiydi (`publish_rho` ve `commit_irtifa_yasasi`
    satırları yoktu; düğüm varsayılanları da `false`, davranış farkı yoktu).
  - Şimdi kaynakla aynı (`diff`).
  - Derleme ayrıca rüzgârlı üç modeli kuruluma ekledi ve `mob_layout.yaml`'ı
    değiştirdi. Bu dosya her koşuda yeniden yazılıyor.
- **`kosu.sh`:** `make_params.py` kaynaktaki yaml'ı okuyor. Varsayılan `true`,
  `emergency_landing_mode.commit_irtifa_yasasi=false` ile `false` (ikisi de
  üretilen dosyada görüldü).
- **Ne zaman fark eder:** yalnız COMMIT'e alan yasası etkinken girildiğinde.
  Veri kipi (K1-K4) koşuları da bundan sonra yeni yasayla iner.

**Doğrulama:** liste `tools/veri/listeler/tur4_kol0_commit.txt`, tablo
`tools/veri/tur4_dogrula.py`.
- **24 koşul:** W2-W6 × tohum 1-3 ve dokuz pozitif ada (t2003-t2011) ×
  tohum 1. Veri setindeki Kol 0 koşulları; W1 ve t2012 negatif örnek olduğu
  için dışarıda.
- **Koşul başına iki bölüm:** önce kapalı (`=false`), sonra açık
  (geçersiz kılma yok, yaml varsayılanı).
- **Toplam 48 bölüm,** veri setinin dışında: `~/eland_veri/_tur4_dogrulama/`.

**Ara durum (8 / 48 bölüm, 4 koşul × 2 ayar; final değil):**
- **Ayar:** `params.yaml`'a göre kapalı 4/4 `false`, açık 4/4 `true`.
  Kaydedici temas seviyelerini 8/8 bölümde kendisi yazdı.
- **Temas:** iki ayarda da 0.29-0.31 m/s.
  - COMMIT'te alan yasası payı iki ayarda da 0.
  - Temastan önceki komut iki ayarda da 0.30 m/s.
- **Durum dizisi:** W2 t2 ve t3'te açık koşu APPROACH'a girdi, kapalı
  girmedi.
  - Parametre yalnız COMMIT'te etkili; bu fark ondan önce.
  - Eski kodla kaydedilmiş veri setinde W2 tohum 2'nin 9 bölümünün 5'inde
    APPROACH var, 4'ünde yok; tohum 3'ün 2 bölümünün 1'inde var.
  - Tur 3'te de W2 t2 ve t3 APPROACH'sız uçtu.
- **Kapalı, veri setindeki aynı koşulla:** 4/4 durum dizisi aynı.
