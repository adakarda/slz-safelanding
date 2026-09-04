# Acil İniş Simülasyonu — Geçiş ve Uygulama Planı

Kaynak brief: `gazebo-acil-inis-simulasyon-brief.md`
Referans kod: `~/ws_slz` (dokunulmuyor, olduğu gibi duruyor)
Çalışma alanı: `~/ros2_ws`
Son güncelleme: 2026-09-03 — **Faz 0, 1, 2, 3, 4 ve 6 tamamlandı ve
doğrulandı. Faz 5 (gerçek segmentasyon modeli) GPU'lu makine bekliyor.**

(Bu satırın 2026-09-01 tarihli hâli "Faz 2 kısmen, IPM hâlâ bekliyor" diyordu
ve aynı dosyanın gövdesiyle çelişiyordu: IPM 09-01'de tamamlanıp
doğrulanmıştı. Düzeltme burada, kaydı için.)

Uçtan uca sonuç: QGC modu tetiklendiğinde drone 20 m'den aday noktaya gidiyor,
yaklaştıkça yavaşlayarak alçalıyor, iniyor ve disarm oluyor — aktivasyondan
disarm'a **27 saniye**. İnsanın 3 m'lik SORA yarıçapı iniş noktasını
kaydırıyor.

---

## 0. Doğrulanmış ortam gerçekleri

Plan bu ölçümlerin üzerine kurulu. Hepsi bu makinede doğrulandı.

| Bileşen | Durum |
|---|---|
| ROS 2 | Jazzy |
| Gazebo | `gz sim 8.11.0` (Harmonic) |
| PX4-Autopilot | `main` @ `f63b0d6b6f` (2026-05-01), v1.17.0-alpha1-1670 |
| px4_msgs | `e62353e`, dal `px4-2026-05-01` — **sabitlendi**, bkz. tuzak 6 |
| px4-ros2-interface-lib | `9fb7cea`, dal `px4-2026-05-01` — **sabitlendi**, bkz. tuzak 6 |
| Segmentasyon sensörü | `libgz-sensors8-segmentation_camera.so` — **çalışıyor** |
| Label eklentisi | `libgz-sim8-label-system.so` — **çalışıyor** |
| GPU | **yok — llvmpipe (yazılımsal render)** |

### Kritik tuzak 1 — brief'in WSL önerisi segmentasyonu öldürür

Brief "gerekirse `--render-engine ogre` kullan" diyor. Ölçüm:

```
libgz-rendering8-ogre2.so : 42 adet SegmentationCamera sembolü
libgz-rendering8-ogre.so  :  0 adet
```

Segmentasyon kamerası **yalnızca ogre2'de** var. `ogre`'ye düşersek sensör hata
vermez, sessizce hiç veri üretmez. PX4'ün bu fallback için bir kancası da var
(`PX4_GZ_SIM_RENDER_ENGINE`, bkz. `px4-rc.gzsim`) — **kullanılmamalı.**

### Kritik tuzak 2 — llvmpipe (çözüldü)

`glxinfo`: `OpenGL renderer string: llvmpipe`. GPU yok, her piksel CPU'da.
PX4'ün stok `mono_cam` sensörü 1280x960 @ 30 Hz.

Uygulanan karşı önlem: segmentasyon kamerası **320x240 @ 5 Hz**, RGB kamera
modelden çıkarıldı, `HEADLESS=1`.

**Ölçülen sonuç: real_time_factor = 1.00**, pipeline'ın tamamı (gz + PX4 +
uXRCE-DDS + 3 ROS node) aynı anda çalışırken. Bu faz için performans sorunu
yok. Faz 5'te (CPU inference + render) yeniden değerlendirilmeli.

### Kritik tuzak 3 — label 0 = arka plan

Gazebo'da etiketlenmemiş her şey label **0**. Brief'in 7 sınıflık şemasında
`0 = safe-soft` yazıyor. Bu şemayla gökyüzü, etiketsiz zemin ve her etiketleme
hatası "güvenli iniş alanı" olarak okunurdu.

Karar: `ws_slz`'nin 10 sınıflık şeması korundu — `0 = UNKNOWN`, risk 1.0.
Brief'in SORA sınıfları bunun üzerine rapor eşlemesi olarak duruyor:

| SORA sınıfı (brief) | eland sınıf ID'leri |
|---|---|
| safe-soft | GRASS(1), DIRT(2) |
| safe-hard | GRAVEL(3), PAVEMENT(4) |
| terrain-hazard | VEGETATION(5) |
| structure | BUILDING(6) |
| water | WATER(7) |
| vehicle-animal | VEHICLE(8) |
| person | PERSON(9) |
| *(SORA'da karşılığı yok)* | UNKNOWN(0) — arka plan, risk 1.0 |

Bu kararın işe yaradığı ölçüldü: 25 m irtifadan alınan karede 8 sınıf birden
ayırt edildi (grass %76.5, pavement %12.9, vegetation %4.2, dirt %2.8, gravel
%1.7, building %1.3, vehicle %0.5, person %0.03).

### Kritik tuzak 4 — PX4 ağacına symlink ŞART (planın ilk hâli yanlıştı)

İlk plan, `GZ_SIM_RESOURCE_PATH` sayesinde model ve world dosyalarının
PX4 ağacının dışında kalabileceğini varsayıyordu. `PX4_GZ_WORLD=eland_test` ile
denendiğinde PX4 şunu yazdı:

```
INFO [init] Starting gazebo with world: /home/arda/PX4-Autopilot/Tools/simulation/gz/worlds/eland_test.sdf
Unable to find or download file
```

`ROMFS/px4fmu_common/init.d-posix/px4-rc.gzsim` okununca iki bağımsız sebep
çıktı:

1. Script `build/px4_sitl_default/rootfs/gz_env.sh`'i source ediyor; o dosya
   `export PX4_GZ_WORLDS=<px4>/Tools/simulation/gz/worlds` yapıyor. `${VAR:=default}`
   değil, koşulsuz atama — yani env'den geçersiz kılınamıyor.
2. Model, literal yolla spawn ediliyor:
   `<uri>file://${PX4_GZ_MODELS}/${MODEL_NAME}/model.sdf</uri>`.
   `GZ_SIM_RESOURCE_PATH` bu dosyanın *içindeki* include'ları (`x500`,
   `model://seg_cam`) çözüyor, ama üst seviye modeli değil.

Çözüm: `eland_sim/scripts/link_px4_assets.sh` üç symlink kuruyor. Kaynak
dosyalar pakette kalıyor, PX4 ağacına yalnızca symlink giriyor — `make clean`
veya yeni bir PX4 checkout'undan sonra script tekrar çalıştırılır.

### Kritik tuzak 5 — yerdeki drone hiçbir şey göremez

İlk uçtan uca testte segmentasyon %100 label 0 döndü ve bu bir hata sanıldı.
Değildi: drone yerdeyken kamera 0.28 m yükseklikte, 99.7° FOV ile yalnızca
0.66 m'lik bir alan görüyor — yani neredeyse tamamen kendi etiketsiz iniş
takımını. 2.5 m'ye çıkınca %100 grass, 25 m'ye çıkınca 8 sınıf geldi.

Bunu teşhis ederken kurulan izole test dünyası (`/tmp/label_probe.sdf`) label
sisteminin üç yerleşimini birden doğruladı: `<plane>` geometrisi + model
seviyesi plugin, `<box>` + model seviyesi, `<box>` + **visual** seviyesi.
Üçü de çalışıyor. PX4'ün `server.config`'inin (`gz-sim-label-system`
içermiyor) label'ları engellemediği de aynı testle elendi.

### Kritik tuzak 6 — px4_msgs / kütüphane / PX4 üçlüsü aynı tarihte olmalı

Brief "px4_msgs (main), px4-ros2-interface-lib, PX4 main" diyor. Üçünü de
`main`'den almak **bu makinede çalışmıyor**, çünkü yerel PX4 ağacı
2026-05-01 tarihli, `px4_msgs` upstream'i ise 2026-08-10 ve sonrasını takip
ediyor. Mod kaydı şu hatayla düştü:

```
[FATAL] MessageFormatResponse::success == false for fmu/in/setpoint_config
[ERROR] Mismatch for the following topics, update PX4 or the px4_ros2 library and px4_msgs:
  - fmu/in/actuator_servos
  - fmu/out/home_position
terminate called after throwing an instance of 'px4_ros2::Exception'
  what():  Registration failed
```

Kütüphane kayıt sırasında mesaj formatlarının hash'ini PX4'e sorup
doğruluyor; 4 aylık fark bunu geçemiyor.

**Neden PX4'ü güncellemedik:** PX4 çalışma ağacı temiz değil —
`4022_gz_rc_cessna_cam` adlı, versiyon kontrolüne girmemiş kendi airframe'in
ve `airframes/CMakeLists.txt`'te ona ait bir kayıt var. `git pull` bunları
riske atardı ve ~20 dakikalık bir yeniden derleme gerektirirdi. Onun yerine
diğer iki bileşen PX4'ün tarihine sabitlendi:

```bash
cd ~/ros2_ws/src/px4_msgs              && git checkout px4-2026-05-01   # e62353e
cd ~/ros2_ws/src/px4-ros2-interface-lib && git checkout px4-2026-05-01  # 9fb7cea
```

Her ikisi de `px4-2026-05-01` adlı yerel dalda duruyor, yani hangi
sürümde olduğumuz `git branch` ile görünür.

**PX4'ü ileride güncellersen** bu iki dalı da ileri taşımak zorundasın.
`px4_msgs` commit mesajları "Update to PX4 `<sha>`" formatında olduğu için
eşleşen commit'i bulmak kolay.

### Kritik tuzak 7 — Tools/simulation/gz bir submodule

`link_px4_assets.sh`'in kurduğu symlink'ler `PX4-Autopilot/Tools/simulation/gz`
içine giriyor ve orası **submodule** (`3eb05f7`, PX4-gazebo-models).
Sonuçları:

- `git status` PX4'te `M Tools/simulation/gz` gösteriyor — bu bizim
  symlink'lerimiz, endişelenecek bir şey değil.
- `git submodule update --force` symlink'leri **siler**. Sildiğinde
  `link_px4_assets.sh`'i tekrar çalıştır.

---

## 1. Mimari kararlar

### K1 — State machine C++ custom mode'un içine taşınır

Brief'in en net şartı: "hack/manuel offboard script değil". `ws_slz`'deki
`offboard_control_node.py` tam olarak o: `/fmu/in/offboard_control_mode`
heartbeat'i + `DO_SET_MODE(1,6)` + `COMPONENT_ARM_DISARM`. QGC'de mod olarak
görünmez, failsafe entegrasyonu yoktur, node çökerse PX4 offboard timeout'a düşer.

```
Python (algı)                        C++ (kontrol)
─────────────────────────────        ──────────────────────────────
perception_node                      EmergencyLandingMode : ModeBase
  -> /eland/semantic_mask              - LandingCandidate subscriber
mapping_node                           - state machine (SEARCH..COMMIT)
  -> /eland/ground_map                 - MulticopterGotoSetpointType
detector_node                          - P kontrollü alçalma
  -> /eland/candidate  ---------->     -> /eland/state (debug)
```

- `landing_manager_node.py` → C++'a port edilir.
- `offboard_control_node.py` → hiç taşınmadı, taşınmayacak.
- Algı tarafı Python'da kalır.

### K2 — Diller arası paylaşılan sabit yok

C++ mode yalnızca `LandingCandidate` tüketir (metrik ENU koordinat + yarıçap +
risk skoru). Sınıf ID'lerini hiç görmez, dolayısıyla `classes.py`'nin C++
kopyası gerekmiyor. Sınıf politikası tek yerde: `detector_node`.

### K3 — "PID" aslında goto setpoint'in dikey hız limiti

Brief: `descent_vel = clamp(k * altitude, v_min, v_max)` — bu bir P kontrolcü.
Kütüphanenin gerçek imzası (`px4_ros2_cpp/.../multicopter/goto.hpp`):

```cpp
void update(const Eigen::Vector3f& position,
            const std::optional<float>& heading = {},
            const std::optional<float>& max_horizontal_speed = {},
            const std::optional<float>& max_vertical_speed = {},
            const std::optional<float>& max_heading_rate = {});
```

`max_vertical_speed = clamp(k*alt, v_min, v_max)` geçmek brief'in formülünün
birebir karşılığı. Goto smoother jerk-sınırlı olduğu için D terimi gereksiz;
I terimi rüzgârsız SITL'de windup'tan başka iş görmez, eklenmiyor.

**Dikkat: `position` NED.** `_vehicle_local_position->positionNed()` de NED
döner. Algı zinciri baştan sona ENU. ENU→NED dönüşümü mode'un içinde, tek bir
yerde yapılmalı — `ws_slz`'nin `enu_to_ned()`'i bu disiplini zaten kurmuştu,
aynısı C++'ta tekrarlanacak.

### K4 — replaceInternalMode(kModeIDDescend), ama en sonda

Doğru API `.replaceMode(...)` değil (planın ilk hâlinde öyle yazıyordu):

```cpp
ModeBase(node, Settings{kName}.preventArming(true)
                              .replaceInternalMode(ModeBase::kModeIDDescend))
```

`mode.hpp`'de mevcut sabitler: `kModeIDPosctl`, `kModeIDTakeoff`,
`kModeIDDescend`, `kModeIDLand`, `kModeIDRtl`, `kModeIDPrecisionLand`,
`kModeIDLoiter`.

Faz 3'te **ayrı mod** olarak kaydedilir (QGC listesinde görünür, elle
tetiklenir, debug edilebilir). `replaceInternalMode` Faz 4'ün **sonunda**
eklenir; önce takılırsa modu manuel test etmek imkânsızlaşır.

### K5 — ws_slz'nin iki stub'ı gerçekten yazılacak

- `mapping_node.project()`: nadir varsayımı, attitude yok, `decay_alpha`
  parametresi tanımlı ama kullanılmıyor.
- `perception_node.remap_gt()`: identity remap — world kendi ID'lerimizle
  etiketlendiği için artık *doğru*, ama `NUM_CLASSES` üstünü UNKNOWN'a çeken
  guard kalmalı.

---

## 2. Workspace yapısı (kurulu)

```
~/ros2_ws/
├── docs/PLAN.md                      <- bu dosya
└── src/
    ├── px4_msgs/                     (mevcuttu)
    ├── px4-ros2-interface-lib/       (klonlandı, derlendi)
    ├── ilk_offboard/                 (eski, ilgisiz, dokunulmadı)
    ├── eland_msgs/                   LandingCandidate, LandingState
    ├── eland_common/                 classes, qos, px4_topics
    ├── eland_perception/             perception_node
    ├── eland_mapping/                mapping_node, detector_node
    ├── eland_sim/                    gz modelleri + world + launch + params
    │   ├── models/seg_cam/
    │   ├── models/x500_seg_cam_down/
    │   ├── worlds/eland_test.sdf
    │   ├── scripts/link_px4_assets.sh
    │   ├── launch/eland_sim.launch.py
    │   ├── config/eland_params.yaml
    │   └── rviz/eland.rviz
    └── eland_mode/                   EmergencyLandingMode (C++, px4_ros2)
```

`ws_slz`'den taşınanlar: mesajlar, `classes.py`, `qos.py`, `px4_topics.py`,
`perception_node`, `mapping_node`, `slz_detector_node` → `detector_node`,
launch dosyasındaki numpy uyumluluk hack'i. Taşınmayan: `landing_manager_node`
(Faz 4'te C++'a port), `offboard_control_node` (hiç).

---

## 3. Fazlar

### ✅ Faz 0 — Workspace kurulumu (tamam)

`px4-ros2-interface-lib` klonlandı. `px4_msgs` bayat bir build artefaktı
yüzünden patladı (`ament_cmake_python` symlink çakışması),
`build/px4_msgs` + `install/px4_msgs` silinip yeniden kuruldu. `px4_ros2_cpp`
bu `px4_msgs` ile **temiz derleniyor** — Faz 3'ün sürüm uyumluluğu riski
kapandı. Beş `eland_*` paketi derleniyor.

### ✅ Faz 1 — Gazebo segmentasyon kamerası (tamam)

- `seg_cam`: `type="segmentation"`, `semantic`, 320x240 @ 5 Hz, hfov 1.74 rad
  (mono_cam'den devralındı, `camera_hfov_deg: 99.7` parametresiyle tutarlı).
- `x500_seg_cam_down`: PX4'ün `x500_mono_cam_down`'ının birebir karşılığı.
- `eland_test.sdf`: etiketli zemin (grass), iki asfalt yol, toprak ve çakıl
  yaması, gölet, üç bina, beş ağaç, bir araç, bir insan.
- `link_px4_assets.sh` ile PX4 ağacına symlink.

Çalıştırma:

```bash
cd ~/PX4-Autopilot/build/px4_sitl_default/rootfs
HEADLESS=1 PX4_GZ_WORLD=eland_test PX4_SYS_AUTOSTART=4001 \
  PX4_SIM_MODEL=gz_x500_seg_cam_down GZ_IP=127.0.0.1 ../bin/px4
```

Ayrı terminallerde `MicroXRCEAgent udp4 -p 8888` ve
`ros2 launch eland_sim eland_sim.launch.py`.

**Doğrulanan sonuçlar:**

| Ölçüm | Değer |
|---|---|
| gz topic'leri | `/seg_cam/labels_map`, `/seg_cam/colored_map`, `/seg_cam/camera_info` |
| Görüntü | 320x240, `rgb8`, label R/G/B kanallarının üçünde de aynı |
| Sensör hızı | 5 Hz (hedeflenen) |
| real_time_factor | 1.00 (tüm pipeline çalışırken) |
| 25 m'de görülen sınıf | 8 (grass, dirt, gravel, pavement, vegetation, building, vehicle, person) |
| `/eland/semantic_mask` | ~3 Hz |
| `/eland/ground_map` | ~3 Hz |
| `/eland/candidate` | ~1.4 Hz, `valid: true` |

Aday nokta: `(-0.16, -0.06)`, `risk_score 0.0` (çim), `radius 8.56 m`.
Bu yarıçap (-6,-6)'daki insana olan mesafeyle (8.49 m) örtüşüyor — yani
mesafe dönüşümü en yakın güvensiz hücre olarak **insanı** buluyor. SORA
insan dışlaması ölçülebilir şekilde çalışıyor.

### ✅ Faz 2 — Algı zincirini sağlamlaştır (tamam)

#### ✅ Zamansal füzyon — "sonraya bırakılabilir" değilmiş

Bu maddeyi Faz 4'e ertelemiştim. **Yanlıştı: iniş bunsuz mümkün değil.**

Kamera ayak izi `2 * irtifa * tan(hfov/2)`: 15 m'de ~36 m, 3 m'de ~7 m. Hafızasız
haritada ayak izinin dışı UNKNOWN, `detector_node` de onu haklı olarak
inilemez sayıyor. Dolayısıyla mesafe dönüşümü ayak izi genişliğinin yarısından
fazla boşluk raporlayamıyor ve ayak izi `2 * r_safe`'in altına düşünce hiçbir
hücre güvenlik yarıçapını geçemiyor. Dedektör ~3 m'de `valid: false`
yayınlamaya başlıyor — yani tam alçalmaya adanmış anda.

Düzeltmeden önce ölçülen: araç 90 saniyede dört kez
`VALIDATE -> HOLD -> ABORT -> tırmanış -> SEARCH -> VALIDATE` döngüsüne girdi,
adayı 2.77 / 2.86 / 3.09 / 3.15 m'de kaybetti. **Hiç inmedi.**

Uygulanan çözüm (`mapping_node`): hücre başına sınıf başına kanıt biriktiren
`HxWxNUM_CLASSES` dizi.

- Kanıt gözlemlendikçe artıyor, gözlemlenmeyince üstel sönümleniyor
  (`memory_tau_s: 30.0`). Sönüm **duvar saatine göre**, kare başına değil —
  segmentasyon kamerası render yükü altında kare düşürüyor ve kare başına bir
  sabit hafıza ufkunu sessizce değiştirirdi.
- Harita araç merkezli olduğu için akümülatör her karede tam hücre kadar
  kaydırılıyor (`np.roll` + sarmalanan kenarı sıfırlama), böylece kanıt diziye
  değil zemine bağlı kalıyor. Hücre altı kalan kasten atılıyor: sınıf ID'leri
  komşulara yayılamaz.
- `min_evidence` altına düşen hücre UNKNOWN'a dönüyor — unutmak "bilmiyorum"
  üretmeli, bayat ama kendinden emin bir cevap değil.

Sonuç: aynı senaryoda döngü tamamen kayboldu, tek geçişte indi.

#### ✅ Gerçek IPM (tamam) — ve iki gizli hata

`mapping_node.observe()` artık `cv2.warpPerspective` ile yer düzlemine
homografi uyguluyor: `M = R_ned_body @ R_body_cam @ K^-1`, ışın-düzlem kesişimi
tek bir 3×3 matrise iniyor. Intrinsic'ler `/camera/camera_info`'dan (bridge
ediliyor, doğrulandı), yoksa FOV'dan.

Nadir yaklaşımında roll/pitch'i yok saymanın ötesinde iki gerçek hata vardı:

1. **Heading tamamen yok sayılıyordu** — harita yalnızca kuzeye bakarken
   anlamlıydı.
2. **Kuzey-güney ters yapıştırılıyordu.** OccupancyGrid satır 0 = origin =
   en güney; görüntü satır 0 = kadraj üstü = aracın ileri yönü.

İkisi de önceki testlerde görünmedi çünkü aday hep aracın neredeyse tam
altındaydı — orada aynalanmış harita ile doğrusu aynı cevabı veriyor.

Doğrulama, heading'leri 90° farklı iki koşu (insan gerçekte 3 m güneyde):

| koşu | PX4 heading | ölçülen |
|---|---|---|
| A | 1.68 rad | east −0.28, north **−3.04** |
| B | 0.11 rad | east −0.38, north **−3.10** |

Kalan ~0.3 m doğu sapması izole edilmedi; adaylar insanın 1.8 m boyunun düz
zemin varsayımını ihlali ve kamera kol mesafesinin ihmali. SORA'nın 3 m
marjının çok içinde.

Ayrıca `max_tilt_deg: 30` eğim kapısı eklendi (99.7° FOV'da ufuk ~40°'de
kadraja giriyor). Uçtan uca inişte hiç kare düşmedi.

#### Kalan Faz 2 işleri

1. ~~Renkli debug görüntüsü~~ — **tamam**, bkz. bölüm 4 madde 4.
   Eski not: `OccupancyGrid.data` sınıf ID'si taşıyor, 0-100
   occupancy değil — rviz'in Map display'i bunu simsiyah gösteriyor. Ayrı bir
   renkli `Image` topic'i gerekiyor.
2. Çözünürlük notu: 15 m'de 320 piksel ≈ 0.111 m/px, yani 0.6 m'lik bir insan
   ~5 piksel. 25 m'de ~3 piksel. Alt sınır bu; irtifa artarsa insan tespiti
   önce bozulur.

### ✅ Faz 3 — PX4 custom mode iskeleti (tamam)

`eland_mode` paketi: `EmergencyLandingMode : px4_ros2::ModeBase`,
`px4_ros2::NodeWithMode<>` ile ayağa kalkıyor. Faz 3 davranışı bilerek sıkıcı:
aktivasyonda pozisyonu yakalayıp 10 m yukarısına gidiyor ve orada tutuyor.
Bu fazın amacı yörünge değil, kayıt / mod yaşam döngüsü / failsafe entegrasyonu.

Referans aldığı örnekler: `examples/cpp/modes/goto` (yapı, `positionReached`),
`examples/cpp/modes/rtl_replacement` (`replaceInternalMode` kullanımı).

**Doğrulanan sonuçlar:**

| Adım | Sonuç |
|---|---|
| Kayıt | `Got RegisterExtComponentReply`, arming check'lere cevap veriyor |
| Atanan mod ID | **23** = `NAVIGATION_STATE_EXTERNAL1` |
| Aktivasyon | `vehicle_status.nav_state` 4 (LOITER) → **23** |
| Davranış | 15.0 m'de aktive edildi, hedef NED z = -24.99, ulaşılan **-24.98 m** |
| Node öldürülünce | nav_state 23 → **5 (AUTO_RTL)**, PX4 failsafe RTL başlattı, araç düşmedi |

Son satır brief'in "node çökerse PX4'ün dahili moduna otomatik geri düşüyor"
iddiasının bu kurulumda doğrulanmasıdır — offboard script yaklaşımının
veremeyeceği tek şey buydu.

**GCS olmadan modu tetiklemek** (QGroundControl Daily yoksa veya headless
test ediyorsan):

```bash
ros2 topic pub -1 /fmu/in/vehicle_command px4_msgs/msg/VehicleCommand \
  "{command: 100001, param1: 23.0, target_system: 1, target_component: 1, \
    source_system: 255, source_component: 190, from_external: true}" \
  --qos-reliability best_effort --qos-durability transient_local
```

`100001` = `VEHICLE_CMD_SET_NAV_STATE`, `param1` = mod ID. Mod aktive
olduğunda kendi ID'sini logluyor, yani 23 sabit varsayılmamalı — birden fazla
harici mod kaydedilirse 24, 25... olur.

**QGroundControl notu:** mod listesinin dinamik güncellenmesi için
QGroundControl **Daily** gerekiyor (`~/QGroundControl.AppImage`'ın sürümü
kontrol edilmeli). Bu, henüz GUI ile doğrulanmadı — yukarıdaki tablo
tamamen PX4'ün kendi durum topic'leri üzerinden ölçüldü.

### ✅ Faz 4 — Entegrasyon (tamam)

`landing_manager_node.py`'nin state machine'i `EmergencyLandingMode` içine
port edildi: `SEARCH / APPROACH / VALIDATE / HOLD / ABORT / COMMIT`, `reason`
string'leri ve `candidate_timeout_s` mantığı korunarak. Alçalma K3'teki
`clamp(k*alt, v_min, v_max)` dikey hız limiti ile.

**Mode executor kullanılmadı.** Plan `ModeExecutorBase`'in `land()` /
`waitUntilDisarmed()` yolunu öngörüyordu; örneği okuyunca executor'ın tam
otonom görev dizisi (takeoff → mod → RTL) için tasarlandığı görüldü. Bizim
modumuz uçuş ortasında operatör ya da failsafe tarafından tetikleniyor, yani
aktivasyon semantiği uymuyor. Tek `ModeBase` + `px4_ros2::LandDetected` daha
az kod ve daha doğru.

#### Tuzak 8 — pozisyon kontrollü temas iniş dedektörünü asla tetiklemez

İlk COMMIT uygulaması goto setpoint'ini yer seviyesine (NED d = 0) hedefliyordu.
Araç fiziksel olarak indi ama:

```
altitude_agl: 0.003   vz: 0.003
has_low_throttle: False   ground_contact: False   landed: False
arming_state: 2 (ARMED)
```

Pozisyon kontrolcüsü sıfır hataya karşı hover itkisini mutlu mesut tutuyor,
PX4'ün iniş dedektörü de düşük gaz görmeden tetiklenmiyor. Araç yerde, hâlâ
armed, mod hiç tamamlanmıyor.

Çözüm PX4'ün kendi Land modunun yaptığı şey: dikey eksende **hız** komutu ver.
`px4_ros2::TrajectorySetpoint` ile yatay pozisyon tutulup dikeyde
`withVelocityZ(descentSpeed)` veriliyor — araç inişi bittikten sonra da inmeye
zorlanınca itki düşüyor ve dedektör tetikleniyor. Yatay eksen pozisyon
kontrolünde kalıyor ki doğrulanmış noktadan kaymasın.

#### Doğrulanan uçtan uca dizi

Drone kasten insanın 3 m yanına doğuruldu (`PX4_GZ_MODEL_POSE="-6,-3,0,0,0,0"`),
20 m'ye kalkış, sonra mod tetiklendi:

```
Emergency Landing activated (mode id / nav_state = 23)
SEARCH   -> APPROACH: candidate #115 accepted, r=3.03 m
APPROACH -> VALIDATE: reached candidate, 0.16 m error
VALIDATE -> COMMIT:   at 1.99 m, committing to touchdown
touchdown detected, mode complete
```

| Ölçüm | Değer |
|---|---|
| Aktivasyondan disarm'a | **27 s** (16.8 s alçalma + 9.7 s temas) |
| Land detector | `ground_contact: True`, `has_low_throttle: True`, `landed: True` |
| `arming_state` | **1 (DISARMED)** |
| Son pozisyon | (−0.32, −0.44), yerde |
| Aday yarıçapı | 3.03 m — insan yokken aynı noktada 8.5 m'ydi |

Son satır SORA kuralının bağlayıcı olduğunun kanıtı: `r_safe=3.0`'ı ancak
geçen nokta seçilmiş, yani insanın varlığı iniş noktasını kaydırmış.

#### ✅ Failsafe entegrasyonu (tamam)

`replace_internal_mode: "rtl"` ile mod PX4'ün Return modunun yerine
kaydediliyor. **K4'teki `kModeIDDescend` önerisi yanlıştı:** `NAV_RCL_ACT`
seçenekleri Hold(1) / Return(2, varsayılan) / Land(3) / Terminate(5) /
Disarm(6) — Descend listede yok, yalnızca pozisyon kaybında yedek olarak
giriliyor. Descend'i değiştirmek, bağlantı kopmasında hiç tetiklenmeyen bir
mod üretirdi.

Gerçek bağlantı kopması testi (enjekte edilmiş arıza değil: kurulan bir GCS
bağlantısı kesildi):

| kopmadan sonra | nav_state | irtifa |
|---|---|---|
| 15 s | 4 (Hold) | 20.0 m |
| **20 s** | **23 (bu mod)** | 16.2 m |
| 25 s | 23 | 8.8 m |

Gecikme = `COM_DL_LOSS_T` 10 s + PX4'ün 5 s Hold bekleme süresi. Sonrası
tamamen otonom: SEARCH → APPROACH → VALIDATE → COMMIT (1.99 m) → temas,
`landed: True`, disarm. Aktivasyondan temasa 26 s.

Yan etki: mod kayıtlıyken kasıtlı bir RTL de eve dönmek yerine burada iniyor.
`replace_internal_mode` `"land"` / `"none"` ile değiştirilebilir.

### Faz 5 — Gerçek segmentasyon modeli

`perception_node`'un `use_gt_segmentation:=false` dalı hazır (şu an sentetik
maske). DINOv2/SegFormer sarmalayıcısı buraya girer, `mask_topic` sözleşmesi
değişmez. `x500_seg_cam_down`'a RGB kamera geri eklenir.

llvmpipe üzerinde CPU inference + CPU render aynı anda anlamlı hızda
çalışmaz — bu faz GPU'lu bir makine ya da native Linux ister.

---

### Faz 6 — Dinamik engeller ve yörünge-farkında karar (2026-09-03, tamam)

Ölçümler ve tam sonuç tabloları `docs/DURUM.md` §12'de; burada yalnız tasarım
kararları ve neden başka türlü yapılmadığı.

#### K6 — İzleme füzyonlu haritadan değil, füzyondan önceki kareden

Füzyonlu harita hızlı hareket edeni **yapısal olarak** göremiyor: kanıt hücre
başına `rate × tau`'ya oturuyor (3 Hz, τ=30 s → ~90) ve 1.5 s'de geçen bir
araç ~5 kanıt bırakıyor, argmax'ı asla kazanamıyor. Ölçüldü: gz'nin kendi
segmentasyonunda iki araç lekesi varken `/eland/ground_map`'te yalnız park
hâlindeki görünüyordu.

Üç seçenek vardı: (a) dinamik sınıflara kısa τ vermek, (b) izleyicinin kendi
IPM'ini yazması, (c) `mapping_node`'un ham kareyi ikinci bir topic'te
yayınlaması. (a) alçalmanın dayandığı hafızayı bozar (tuzak 1'in kendisi),
(b) ikinci bir projeksiyon uygulaması demek ve ikisi zamanla ayrışır.
(c) seçildi: `/eland/ground_map_instant`, aynı homografi, aynı geometri.

#### K7 — Dördüncü test, skora ek terim değil

`trajectory_clear`, `min_area_m2` / `r_fit` / `r_hazard` ile aynı sırada bir
**uygunluk testi**. Skora ağırlıklı bir terim olarak eklemek de mümkündü;
seçilmemesinin sebebi SORA ayrımının pazarlık konusu olmaması: yeterince
"iyi" bir hücre, engelin gideceği yerde olmayı telafi edemez. Ayrıca eleme
olarak tutmak logu okunur kılıyor — kaç hücrenin neden düştüğü tek satır.

Seçim kararlılığı (`w_stickiness`) ise skorda, çünkü o gerçekten bir tercih:
eşitliği bozar, uygunluğu değiştirmez. Uygunluk testlerinden **sonra**
uygulanıyor, yani reddedilmiş bir hücreyi geri getiremez.

#### K8 — Koridor, tahminin kendi hatası kadar geniş

Ayrımı tahmin edilen noktadan tam `r_hazard` kadar almak, metrelerce yanlış
olan bir noktadan 3 m ayrılmak demekti. Koridor yarıçapı:

```
r(t) = r_hazard + (sigma_base + sigma_cross_rate * t) * (2 - confidence)
```

`sigma_cross_rate` kasten küçük (0.25 m/s). Ölçülen tahmin hatası ~0.9 m/s
büyüyor ama neredeyse tamamı yol **boyunca**; koridor aynı hat üzerinde
örneklenmiş disklerin birleşimi olduğu için o bileşen zaten kapsanıyor. Her
diski onunla genişletmek hatayı iki kez sayıyor ve haritanın yarısını eliyor.
Disk yarıçapı yalnız **yanal** hatayı taşır.

#### K9 — İleri koridor + süpürülmüş güzergâh hafızası

Yalnız ileri koridorla ölçülen davranış: araç yaklaşırken nokta doğru şekilde
reddedildi, beklendi, araç geçer geçmez tam oraya inildi — hattan 0.37 m.
Sabit hızlı bir model "bu araç geri gelecek" diyemez.

Eklenen: hareket eden bir şeyin **gözlendiği** her nokta, `corridor_memory_s`
boyunca dışlanmış kalıyor. Gerekçe, tahmin değil kanıt: az önce buradan bir
araç geçtiyse orası bir güzergâhtır. Yalnız gözlenen kısım hatırlanıyor,
tahmin edilen kısım değil — yoksa bir ekstrapolasyon, hiçbir şeyin bulunmadığı
bir yerin kalıcı kaydına dönüşürdü.

**Hafıza diskleri yaklaşma rotası testine dahil değil.** İkisi birleşince
ölçülen sonuç haritanın %95'inin kapanmasıydı: aracın 30 saniyede geçtiği her
yer, drone'dan bakınca bir yönü gölgeliyor. 15 m'den üstünden uçmak tehlike
değil; üstüne oturmak tehlike.

#### K10 — İnsan `<actor>` değil, `<model>` (varsayılan olarak)

`<actor>` denendi ve segmentasyon açısından **çalışıyor**: Label eklentisiyle
etiketleniyor, yürüyor, izleyici görüyor (etiket 3 ile yapılan sınamada 123 px,
centroid 5 s'de 124.8 → 207.0 px kaydı, statik kontroller kıpırdamadı).

Kullanılmamasının sebebi ölçülebilirlik: Gazebo actor pozunu **yayınlamıyor**
(ne `pose/info` ne `dynamic_pose/info` bir actor listeliyor) ve script'in
dediği hızda yürütmüyor — 33.3 s'lik tur ~28 s sürdü, yani ~%17 hızlı. Gerçek
konumu ne komut edilen ne gözlenebilen bir engel, konum kestiricisini
puanlayamaz: her hata kestirici ile referans arasında belirsiz kalır.

`person_kind: actor` ile geri açılabilir; sınıf etiketi, yörünge parametreleri
ve aşağı akıştaki her şey aynı.

#### K11 — Engeller ışınlanıyor, itilmiyor

`set_pose` servisi, hız komutu değil. Üç sebep, göz ardı edilince maliyetine
göre sıralı: (1) tekrarlanabilir test tekrarlanabilir engel ister, hız kontrolü
pozu sürtünmeye ve çözücüye bırakır; (2) engel, tehlike oluşturduğu aracın
kendisi tarafından itilmemeli; (3) zincirde kuvvet okuyan hiçbir şey yok, kamera
piksel görüyor.

Ölçülerek seçildi: statik etiketli bir modele tek `set_pose` çağrısı,
segmentasyon lekesini (100.7, 119.5) → (101.8, 212.6) px taşıdı — render yolu
ışınlanan modeli takip ediyor ve etiket taşınmayı atlatıyor.

#### K12 — Dünya üretiliyor, elle yazılmıyor

Actor'ün hareketi kendi SDF'indeki waypoint script'i; "başlangıç, hedef ve hız
parametredir" ancak SDF'i o parametrelerden yazarak sağlanabiliyor. Araç için
şart değil (çalışma anında sürülüyor) ama aynı dosyadan üretiliyor ki
geometri ile yörünge ayrışmasın.

Tuzak: marker'ı şablonun başlık yorumunda da anmak, metin değiştirme sırasında
engelleri o yoruma da yazdırdı. Üreteç artık marker'ın **tam bir kez**
geçtiğini doğruluyor.

#### K13 — Simülasyondaki failsafe eşikleri (2026-09-04 düzeltildi)

**Bu bölümün ilk hâli yanlış bir ölçüme dayanıyordu ve `COM_RC_LOSS_T`
gevşetmesi geri alındı; gerekçesi ve yeni ölçümler `docs/DURUM.md` §16'da.
Kalan tek parametre `NAV_RCL_ACT=1`, ve o bir politika seçimi.**

Aşağıdaki metin kaydı için duruyor.



`run_sim.sh` açılışta iki PX4 parametresi yazıyor: `NAV_RCL_ACT=1` (Hold) ve
`COM_RC_LOSS_T=3`. İkisi de ölçüme dayanıyor.

İstasyon sabit 20 Hz manuel kontrol yayınlarken PX4'ün fiilen kullandığı hız
0 ile 31 Hz arasında salınıyor — mesajlar öbekler hâlinde, aralarda saniyelerce
boşlukla geliyor. 0.5 s'lik varsayılan eşik her boşlukta "verici kayboldu"
diyor, `NAV_RCL_ACT` varsayılanı Return, ve bu mod Return'ün yerine kayıtlı
olduğu için her biri bir acil inişe dönüşüyordu. Ölçülen: devralma başarılı
oluyor, dört saniye sonra failsafe aracı geri alıyor.

Ayrım önemli: **`NAV_DLL_ACT` (GCS datalink) Return'de bırakıldı.** Bağlantı
kopması senaryosu — bu projenin asıl gösterdiği şey — olduğu gibi çalışıyor.
Değişen yalnızca operatörün kumanda bağlantısındaki boşluğun cezası: iniş
değil, bekleme.

Bunlar gerçek bir vericiyle uçan bir araca kopyalanmaz. 0.5 s orada doğru
sayıdır; buradaki bağlantı yazılımsal render ile CPU paylaşan bir DDS
köprüsüdür. Öbeklenmenin kaynağı izole edilmedi (bölüm 4, madde 10).

#### K14 — Seçilen nokta kilitleniyor

Aday seçimi her karede sıfırdan yapılıyordu. Koridor süpürüldükçe kazanan hücre
12 m öteye atlıyor, uçuş modu bu atlamayı kaybolmuş aday sayıyor, üç kayıp
deneme bütçesini bitiriyor ve `committing anyway` ile araç zaten reddedilmiş
noktaya iniyordu — filtrenin varlık sebebinin tam tersi.

Kilit, uygunluk testlerinden **sonra** çalışıyor: bir kararı uzatabilir,
reddedilmiş bir hücreyi geri getiremez. Bırakma eşiği (`latch_release_margin`)
gerçekten daha iyi bir yer çıkarsa kilidi açıyor.

Ölçülen: bir iniş boyunca aday kaybı 3 → 1, sonuç `committing anyway` yerine
1.99 m'de normal COMMIT, araç hattına uzaklık 0.06 m yerine 4.73 m.

---

## 4. Bilinen açık kusurlar

1. ~~**Sınırsız yeniden deneme.**~~ **Kapandı.** `max_landing_attempts` (3).
   Vazgeçilen her alçalma `abandonDescent()` üzerinden geçiyor, böylece bütçe
   farklı bir durum çifti üzerinden dolaşılarak atlatılamıyor.

   İlk uygulamam eksikti ve test bunu yakaladı: sayaç yalnızca
   `HOLD -> ABORT` yolunda artıyordu, dolayısıyla aday `min_radius_altitude`
   üstünde kaybolduğunda makine `VALIDATE <-> SEARCH` arasında sonsuza kadar
   salınabiliyordu — aynı sınırsız döngü, farklı isimlerle. Her iki yol da
   artık sayılıyor.

   Doğrulandı (`min_area_m2` yükseltilip füzyon kapatılarak kayıp zorlandı):
   ```
   VALIDATE -> SEARCH: candidate lost at 13.24 m (attempt 1/3)
   VALIDATE -> SEARCH: candidate lost at 12.68 m (attempt 2/3)
   VALIDATE -> COMMIT: candidate lost at 13.27 m; attempt 3/3, no retries left,
                       committing anyway
   ```

2. ~~**Aday yokken sonsuz loiter.**~~ **Kapandı.** `search_timeout_s` (60 s).
   Süre dolduğunda: daha önce kabul edilmiş bir aday varsa ona, hiç yoksa
   bulunduğu yere körlemesine iniyor — PX4'ün kendi Descend failsafe'inin
   yaptığı şey. Doğrulanmamış bir zemine inmek kötü bir sonuç; bataryanın
   karar vermesini beklemek daha kötüsü ve eski kodun garanti ettiği sonuçtu.

   Kör iniş için hedef COMMIT'e girerken donduruluyor: aksi hâlde
   `candidateNed()` varsayılan kurulmuş bir mesajı okuyup aracı aşağı değil
   yerel orijine uçururdu.

   Doğrulandı (hiç aday üretilemeyecek şekilde yapılandırılarak):
   ```
   SEARCH -> COMMIT: search timed out after 20.00 s with no candidate ever
                     found; DESCENDING BLIND
   ```

3. **Not: `r_fit` ayrımının beklenmedik bir yan etkisi.** Deneme sınırını test
   ederken orijinal düşük irtifa aday kaybı **artık tekrar üretilemedi**:
   3 m'de ayak izi ~7 m, eski tek `r_safe = 3.0 m` eşiği geçilemiyordu ama
   yeni `r_fit = 1.0 m` rahat geçiliyor. Yani `r_safe`'i bölmek, zamansal
   füzyondan bağımsız olarak aynı kusuru ikinci kez kapatmış. Döngü artık iki
   ayrı mekanizmayla korunuyor.

   Bunun tersi de doğru ve güvenlikle ilgili: füzyon kapalıyken insan ayak
   izinden çıktığı anda haritadan siliniyor, hücreleri UNKNOWN'a dönüyor.
   O hücreler inilebilir olmuyor (UNKNOWN güvenli değil) ama **çevresindeki
   3 m'lik SORA tamponu kayboluyor** — `r_hazard` görünmeyen bir tehlikeyi
   uygulayamaz. Füzyon süreklilik için değil, güvenlik için gerekli.

4. ~~**rviz görselleştirmesi eksik.**~~ **Kapandı.**
   `/eland/ground_map_colored` (rgb8, 200×200, ~3.5 Hz) eklendi; palet
   `classes.py`'de tek kaynakta. Görüntü çıkarken dikey çevriliyor: grid satır
   0 OccupancyGrid origin satırı yani en güney, görüntüde ise ilk satır üstte
   çizilir — çevirmeden her harita okuma alışkanlığına ters düşerdi. (Fark
   edilmemiş hâliyle aynı karışıklık, IPM'den önce projeksiyonun kendisini
   aynalayan şeydi.)

   Doğrulandı: 7 farklı renk, insan rengi merkezin 15 satır altında =
   3.0 m güney, yani kuzey-yukarı yönelimi doğru.

   rviz config'inde ham `Map` display'i `Enabled: false` yapıldı — sınıf
   ID'lerini 0-100 occupancy sanıp simsiyah gösteriyordu. Launch'taki
   `static_transform_publisher` hâlâ yalnızca TF ağacını köklemek için var.
5. **QGroundControl GUI doğrulaması yapılmadı.** Kayıt, aktivasyon ve nav_state
   geçişleri PX4'ün kendi topic'lerinden ölçüldü; "QGC mod listesinde görünüyor"
   iddiası henüz kanıtlanmadı.
6. **Modu geri almanın yolu yok.** `replace_internal_mode: "rtl"` kayıtlıyken
   kasıtlı bir RTL de acil inişe dönüşüyor. Operatörün "hayır, gerçekten eve
   dön" diyebileceği bir kaçış yolu yok.

7. **Hız kestirimi sistematik olarak düşük** (Faz 6). Ölçülen: insanda %87,
   araçta %68 (2.04 m/s / 3.0 m/s). Sebepleri: dönüş anını içine alan
   en-küçük-kareler penceresi, ve haritadan çıkıp giren engelin track'inin
   yeniden kurulması. **Güvensiz yön**: koridor olması gerekenden kısa çıkıyor.
8. **10 saniyelik ufkun ucu güvenilmez** (Faz 6). Araçta +10 s tahmin hatası
   16.9 m. Koridorun asıl değeri 2–4 s aralığında (3.4–4.6 m).
9. **Süpürülmüş güzergâh hafızası ile yaklaşma rotası testi birleştirilmedi.**
   Birleşince haritanın %95'i kapanıyor; zaman-uzay muhakemesi yapan bir sürüm
   ikisini güvenli şekilde birleştirebilir.
10. **Manuel kontrol akışındaki öbeklenmenin kaynağı bulunmadı** (Faz 6).
    20 Hz gönderilirken PX4'ün kullandığı hız 0–31 Hz arasında salınıyor.
    Semptom `COM_RC_LOSS_T=3` ile karşılandı; kaynağı (uXRCE-DDS köprüsü, ROS
    zamanlayıcı, CPU doygunluğu) izole edilmedi. Gerçek donanımda aynı
    toleransla uçmak doğru olmaz.
11. **GUI'li koşu ölçülmedi.** Bütün teleoperasyon ölçümleri `--headless`;
    şikâyet Gazebo penceresi açıkken çıkmıştı.

## 5. Açık sorular

1. **World tasarımı genişletilsin mi?** Şu anki sahne SORA kurallarını test
   etmeye yetiyor. Daha zor bir senaryo istenirse: iniş noktasının drone'dan
   uzakta olması (uzun APPROACH fazı), ya da hareketli bir insan.
2. ~~**`replaceInternalMode` hedefi** — `Descend` mi `Return` mü?~~
   **Kapandı, ölçümle.** `Descend` mümkün değil: `NAV_RCL_ACT` seçenekleri
   Hold / Return / Land / Terminate / Disarm; Descend listede yok, yalnızca
   pozisyon kaybında yedek olarak giriliyor. `Return` seçildi — brief'in dediği
   ve PX4'ün varsayılanı, dolayısıyla parametre değişikliği gerektirmiyor.
