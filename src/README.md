# Acil İniş Simülasyonu — `eland_*` paketleri

Aşağı bakan segmentasyon kamerasından SORA risk sınıflandırmasına göre iniş
noktası seçen ve oraya PID kontrollü inen, PX4'e kayıtlı bir ROS 2 uçuş modu.

Tasarım kararları, ölçümler ve bilinen sınırlar: `docs/PLAN.md` ve
`docs/CHECKLIST.md`. Bu dosya yalnızca çalıştırma talimatı.

---

## Paketler

| Paket | Dil | İş |
|---|---|---|
| `eland_msgs` | CMake | `LandingCandidate`, `LandingState` |
| `eland_common` | Python | Sınıf ID'leri, renk paleti, QoS profilleri, PX4 topic adları |
| `eland_perception` | Python | Kamera → `mono8` semantik maske |
| `eland_mapping` | Python | Maske → metrik zemin haritası (IPM + zamansal füzyon), hareketli engel izleme, ve aday seçimi |
| `eland_mode` | C++ | `px4_ros2::ModeBase` — PX4'e kayıtlı "Emergency Landing" modu |
| `eland_viz` | Python | İniş HUD'ı (`/eland/hud`) ve kontrol istasyonu |
| `eland_sim` | Python | Gazebo modelleri, dünya, launch, parametreler, rviz |

Veri akışı:

```
gz segmentation camera
  -> /camera/segmentation      (ros_gz_image bridge)
  -> perception_node   -> /eland/semantic_mask
  -> mapping_node      -> /eland/ground_map          (füzyonlu; iniş kararı)
                       -> /eland/ground_map_instant  (ham kare; hareket)
                       -> /eland/ground_map_colored  (görsel)
  -> tracker_node      -> /eland/dynamic_obstacles
  -> detector_node     -> /eland/candidate
  -> eland_mode        -> PX4 setpoint'leri, /eland/state
```

`eland_mode` dışında hiçbir node PX4'e yazmaz.

**Neden iki harita:** füzyonlu harita hızlı hareket edeni göremez — kanıt
hücre başına `rate × tau`'ya oturuyor (~90) ve 1.5 s'de geçen bir araç ~5
kanıt bırakıp argmax'ı kaybediyor. Hafızayı düşürmek alçalmayı bozar, o yüzden
izleyici füzyondan **önceki** kareyi okuyor. Ayrıntı `docs/DURUM.md` §12.

**Dinamik engeller:** `eland_sim/obstacle_driver` bir insan ve bir aracı
`eland_params.yaml`'daki parametrelere göre hareket ettirir ve **yalnız ölçüm
için** `/eland/obstacle_truth` yayınlar. Zincirdeki hiçbir node bunu okumaz;
araç engelin nereye gittiğini kendi kamerasından çıkarır.

---

## Kurulum

Bağımlılıklar: ROS 2 Jazzy, Gazebo Harmonic (gz-sim 8), PX4-Autopilot,
`MicroXRCEAgent`, `ros_gz_image`.

```bash
cd ~/ros2_ws/src
git clone --recursive https://github.com/Auterion/px4-ros2-interface-lib
git clone https://github.com/PX4/px4_msgs
```

**Sürüm eşleşmesi kritiktir.** `px4_msgs`, `px4-ros2-interface-lib` ve PX4
aynı tarihten olmalı; değilse mod kaydı şu hatayla düşer:

```
MessageFormatResponse::success == false for fmu/in/setpoint_config
Registration failed
```

Bu makinede PX4 `f63b0d6b6f` (2026-05-01) olduğu için diğer ikisi geriye
sabitlendi:

```bash
cd ~/ros2_ws/src/px4_msgs               && git checkout e62353e
cd ~/ros2_ws/src/px4-ros2-interface-lib && git checkout 9fb7cea
```

`px4_msgs` commit mesajları `Update to PX4 <sha>` formatında, yani PX4'ü
güncellersen eşleşeni bulmak kolay.

Derleme:

```bash
cd ~/ros2_ws && colcon build && source install/setup.bash
```

Dünyayı üret (dinamik engeller parametrelerden yazılır; `run_sim.sh` her
açılışta kendisi çalıştırır, elle kurulumda bir kez gerekir):

```bash
python3 ~/ros2_ws/src/eland_sim/scripts/gen_world.py
```

`worlds/eland_test.sdf` **üretilen** dosyadır. Statik sahne için
`eland_test.sdf.in`'i, engeller için `config/eland_params.yaml` içindeki
`obstacle_driver` bölümünü düzenle; üretilen dosyaya yazılan her şey bir
sonraki koşuda kaybolur.

Gazebo varlıklarını PX4 ağacına bağla (bir kez; PX4 `make clean` veya
`git submodule update` sonrası tekrar):

```bash
~/ros2_ws/src/eland_sim/scripts/link_px4_assets.sh
```

Neden gerekli: `px4-rc.gzsim`, `gz_env.sh`'i source ederken `PX4_GZ_WORLDS` ve
`PX4_GZ_MODELS`'i koşulsuz üzerine yazıyor, ayrıca modeli literal yolla
spawn ediyor. `GZ_SIM_RESOURCE_PATH` yalnızca iç içe `<uri>`'leri çözüyor.
Script'in kendi başlığında ayrıntısı var.

---

## Çalıştırma — tek komut

```bash
~/ros2_ws/src/eland_sim/scripts/run_sim.sh --scenario person --auto
```

PX4 + Gazebo, uXRCE-DDS ajanı ve ROS 2 zincirini doğru sırada, her birinin
gerçekten hazır olmasını bekleyerek açar. **Ctrl+C hepsini birden kapatır** —
elle uğraşırken asıl can sıkan kısım budur, çünkü PX4, gz sunucusu, gz
arayüzü, ajan ve beş ROS node'unun hepsinin gitmesi gerekir.

| Seçenek | Ne yapar |
|---|---|
| *(varsayılan)* | **Doğuş noktası rastgele** — engellerden ≥6 m, hareketli engel güzergâhlarından ≥8 m uzakta. Seçilen poz ve seed ekrana ve `/tmp/eland_logs/spawn.txt`'e yazılır. |
| `--seed N` | Aynı seed, aynı doğuş noktası (koşuyu tekrarlamak için) |
| `--spawn-bounds x0,y0,x1,y1` | Rastgele pozun çekildiği alan (varsayılan ±25 m) |
| `--fixed` | Eski davranış: orijinden kalk (regresyon karşılaştırmaları için) |
| `--scenario default\|person\|yard` | Sabit doğuş yeri seçer |
| `--pose X,Y,Z,R,P,Y` | Elle doğuş pozu |
| `--takeoff [ALT]` | Her şey açıldıktan sonra arm + kalkış (varsayılan 18 m) |
| `--auto` | Kalkış + modu seç (tam demo) |
| `--link-drop` | Kalkış, sonra gerçek GCS bağlantısını kes — failsafe modu kendi getirir |
| `--params FILE` | Kurulu yerine bu parametre dosyasıyla çalış (karşılaştırma koşuları). Dosya yoksa **durur** — sessizce varsayılanlara düşmek ölçümü bozar. |
| `--launch-arg A:=B` | Ek launch argümanı, tekrarlanabilir |
| `--headless` | Gazebo penceresi açma (bu makinede belirgin şekilde hızlı) |
| `--no-hud` | HUD hiç çalışmasın |
| `--hud-headless` | `/eland/hud` yayınlansın ama pencere açılmasın |

**HUD penceresi varsayılan olarak açılır** — ayrı terminalde `rqt_image_view`
çalıştırmana gerek yok. `--headless` yalnızca *Gazebo* penceresini kapatır,
HUD yine açılır; ikisini birden istemiyorsan `--headless --hud-headless`.

**Bir koşuyu tekrar üretmek:** çıktının başındaki iki satır bunun içindir.

```
[run_sim] rastgele dogus: pose -4.17,-24.49,0,0,0,2.0433  (seed 12345)
[run_sim]   ayni koşuyu tekrarlamak icin: --seed 12345
[run_sim]   ya da tam olarak: --pose -4.17,-24.49,0,0,0,2.0433
```

`--pose` olanı daha sağlamdır: seed, seçim kodunun aynı kalmasına bağlıdır,
poz bağlı değildir.

Üç sabit senaryo (`--scenario` ile):

| | Ne görürsün |
|---|---|
| `default` | Açık çim; nokta aracın altında ama artık 8 m boşlukla |
| `person` | İnsanın 3 m yanı; SORA ayrımı noktayı kaydırır |
| `yard` | Asfalt avlu, ağaçlar ve insanlar; ~14 m yatay seyir |

Loglar `/tmp/eland_logs/` altında: `px4.log`, `agent.log`, `pipeline.log`.

PX4 bu script içinde `-d` ile çalışır (etkileşimli `pxh>` istemi yok), çünkü
her şey tek terminali paylaşırken o istem zaten kullanılamaz. Arm ve kalkış
`px4-commander` üzerinden gider.

---

## Çalıştırma — elle, üç terminal

Script'in ne yaptığını görmek ya da adımları ayrı ayrı kontrol etmek istersen:

```bash
# 1 - PX4 SITL + Gazebo
cd ~/PX4-Autopilot/build/px4_sitl_default/rootfs
HEADLESS=1 PX4_GZ_WORLD=eland_test PX4_SYS_AUTOSTART=4001 \
  PX4_SIM_MODEL=gz_x500_seg_cam_down GZ_IP=127.0.0.1 ../bin/px4
```

```bash
# 2 - uXRCE-DDS köprüsü
MicroXRCEAgent udp4 -p 8888
```

```bash
# 3 - algı zinciri + uçuş modu
ros2 launch eland_sim eland_sim.launch.py
#   rviz:=true            görselleştirme
#   mode:=false           yalnızca algı, araç üzerinde hiç yetki yok
#   bridge_colored:=false segmentasyonun renkli görselini köprüleme
```

`PX4_GZ_MODEL_POSE="x,y,z,r,p,y"` ile doğuş yeri seçilir. İlginç noktalar:

| Poz | Senaryo |
|---|---|
| *(varsayılan)* | Açık çim; aday aracın hemen altında |
| `-6,-3,0,0,0,0` | İnsanın 3 m yanı — SORA ayrımı iniş noktasını kaydırır |
| `45,-45,0,0,0,0` | Asfalt avlu; ağaçlar ve insanlar var, en yakın çim ~14 m — uzun APPROACH |

**Dikkat:** yerdeki drone hiçbir şey göremez. Kamera 0.28 m yükseklikte, 99.7°
FOV ile 0.66 m'lik bir alan görüyor — neredeyse tamamen kendi etiketsiz iniş
takımı. Maske %100 UNKNOWN döner; bu doğru davranış, bozuk sensör değil.

---

## Modu tetikleme

**QGroundControl'den:** mod listesinde "Emergency Landing" görünür (dinamik mod
kaydı için QGC **Daily** gerekir). PX4 tarafı `AVAILABLE_MODES` ile doğrulandı.

**GCS olmadan:**

```bash
ros2 topic pub -1 /fmu/in/vehicle_command px4_msgs/msg/VehicleCommand \
  "{command: 100001, param1: 23.0, target_system: 1, target_component: 1, \
    source_system: 255, source_component: 190, from_external: true}" \
  --qos-reliability best_effort --qos-durability transient_local
```

`100001` = `VEHICLE_CMD_SET_NAV_STATE`, `param1` = modun ID'si. Mod aktive
olurken kendi ID'sini logluyor — 23 sabit varsayma, birden fazla harici mod
kayıtlıysa değişir.

**Failsafe ile (asıl senaryo):** mod varsayılan olarak PX4'ün Return modunun
yerine kayıtlı (`replace_internal_mode: "rtl"`), ve Return zaten `NAV_RCL_ACT`
ile `NAV_DLL_ACT`'in varsayılan eylemi. Yani gerçek bir GCS bağlantısı kurulup
kesilirse `COM_DL_LOSS_T` (10 s) + PX4'ün 5 s bekleme süresi sonunda bu mod
kendiliğinden devreye girer.

Yan etki: mod kayıtlıyken **kasıtlı bir RTL de** eve dönmek yerine burada acil
iniş yapar. İstenmiyorsa `replace_internal_mode` `"land"` (NAV_RCL_ACT=3 ile)
veya `"none"` yapılabilir.

---

## İzleme

```bash
ros2 topic echo /eland/state              # durum makinesi + her geçişin gerekçesi
ros2 topic echo /eland/candidate          # seçilen nokta, alan, oran, yarıçap
ros2 topic echo /eland/dynamic_obstacles  # izlenen hareketli engeller + tahmin
ros2 run rqt_image_view rqt_image_view /eland/hud
```

Yörünge filtresi bir şey elediğinde `detector_node` bunu INFO seviyesinde
yazar: `trajectory filter removed N of M otherwise eligible cells`. Hiç satır
yoksa ya hareketli engel yok ya da filtre kapalı.

`/eland/state` yalnızca mod aktifken yayınlanır — PX4 pasif moda
`updateSetpoint` çağırmaz.

`/eland/ground_map` sınıf ID'si taşır, 0-100 occupancy değil; rviz'in Map
display'i onu simsiyah gösterir, o yüzden config'de kapalı.
Renkli görünüm için `/eland/ground_map_colored` kullan.

### Kontrol istasyonu — HUD + klavye

`run_sim.sh` varsayılan olarak açar. Tek pencerede HUD, tuş listesi, çubuk
göstergeleri ve araç durumu var. **Klavyenin çalışması için pencereye tıkla.**

| Tuş | |
|---|---|
| `W` / `S` | ileri / geri |
| `A` / `D` | sola / sağa kay |
| `Q` / `E` | sola / sağa dön |
| `R` / `F` | yüksel / alçal |
| `SPACE` | çubukları ortala |
| `1` / `X` | arm / disarm |
| `2` | kalkış |
| `3` | manuel kontrolü al (POSCTL) |
| `0` | **acil iniş modunu tetikle** |
| `L` | PX4 ile in |
| `ESC` | çık |

Çubuklar **yapışkan**: OpenCV tuş bırakma olayı vermediği için bir tuş çubuğu
kaydırır ve orada kalır. Test için bu daha kullanışlı — yönü ver, uçuşu izle,
`SPACE` ile durdur.

Tipik akış: `1` arm → `2` kalkış → `3` manuel kontrol → WASD ile ilginç bir
yere uç → `SPACE` → `0` acil iniş. Böylece her senaryo için baştan
başlatmana gerek kalmıyor.

Manuel kontrol `/fmu/in/manual_control_input` üzerinden gidiyor, yani PX4 bunu
joystick gibi görüyor ve Position modda uçuyor; çubuklar gövde-göreli, "ileri"
burnun baktığı yön. Offboard setpoint **kullanılmıyor** — bu projenin tümüyle
kaçındığı mekanizma o, ve desteklenen bir giriş yolu varken bir test aracının
onu kullanması için sebep yok.

#### Failsafe eşikleri simülasyona göre ayarlı

`run_sim.sh` açılışta iki PX4 parametresi yazar:

| Parametre | Değer | Neden |
|---|---|---|
| `NAV_RCL_ACT` | 1 (Hold) | Operatör kumandasındaki boşluk aracı park etmeli, indirmemeli |
| `COM_RC_LOSS_T` | 3 s | Buradaki bağlantı bir verici değil, yazılımsal render ile CPU paylaşan bir DDS köprüsü |

Sebebi ölçüldü: istasyon sabit 20 Hz manuel kontrol yayınlarken PX4'ün fiilen
kullandığı hız 0 ile 31 Hz arasında salınıyor — mesajlar öbekler hâlinde,
aralarda saniyelerce boşlukla geliyor. 0.5 s'lik varsayılan eşik her boşlukta
"verici kayboldu" diyordu ve bu mod Return'ün yerine kayıtlı olduğu için her
biri bir acil inişe dönüşüyordu. Devralma başarılı oluyor, dört saniye sonra
failsafe geri alıyordu.

**`NAV_DLL_ACT` (GCS datalink) değiştirilmedi** — `--link-drop` senaryosu
olduğu gibi çalışır.

Bu iki satır gerçek donanıma kopyalanmaz; orada varsayılanlar doğrudur.

#### Manuel kontrol geri alınırken

- `3`'e basınca istasyon önce çubuk akışını başlatır, ~2 s sonra POSCTL ister.
  **Sıra önemli:** akış canlı değilken PX4 devretmiyor (ölçüldü: akışsız istek
  reddedildi, akışlıyken anında kabul edildi).
- Bir failsafe aracı geri alırsa istasyon POSCTL'i **tekrar ister** ve alt
  satırda sebebini yazar (`sebep: kumanda baglantisi kopuk sayiliyor` gibi).
  `0` (acil iniş) veya `L` (PX4 ile in) tuşları bu ısrarı bırakır.
- Durum panelinde `FAILSAFE` satırı ve `nav_state` yanında mod adı görünür.

#### Bilmen gereken: istasyon GCS bağlantısını canlı tutar

PX4 bir yer istasyonunun konuşup konuşmadığını takip eder ve `NAV_DLL_ACT`
varsayılanı Return'dür. Hiç GCS bağlı değilse kalkıştan `COM_DL_LOSS_T` (10 s)
sonra `gcs_connection_lost` doğru olur, failsafe tetiklenir — ve acil iniş modu
Return'ün yerine kayıtlı olduğu için **araç ne yapıyor olursan ol kendi kendine
iner.** Bu bir hata değil, failsafe'in çalışması; ama teleop denemelerinin ilk
üçünü bozuk kumanda gibi gösterdi.

Bu yüzden istasyon saniyede bir GCS heartbeat gönderiyor (`pymavlink` ile,
PX4'ün dinlediği 18570 portuna). Pencere açıkken bağlantı var, kapanınca
kopuyor — kopunca da failsafe acil iniş modunu getiriyor, ki bu zaten
gösterilmek istenen davranış.

`gcs_heartbeat: false` ile kapatılabilir, ama o zaman her uçuş ~15 saniyede
kendiliğinden iner.

### HUD — iniş sırasında bakılacak asıl yer

`/eland/hud`. Solda kuzey-yukarı zemin haritası, üstünde seçim mantığının
fiilen kullandığı üç çember:

- **kalın yeşil** — seçilen noktaya sığan en büyük daire (ulaşılan boşluk)
- **kesikli gri** — `r_ideal`, sığdırılmaya çalışılan hedef daire
- **ince mavi** — insan/araç/yapıya karşı SORA ayrım mesafesi

Yeşil çember kesikliye ulaştıysa nokta politikanın istediği kadar açık; yeşil
belirgin şekilde küçükse araç daha dar bir yere razı olmuş. İkisi eşitse yeşil
kesiklinin tam üstüne biner ve kesikli görünmez — bu iyi haber.

Sağdaki panel: durum ve gerekçesi, irtifa, yatay ve dikey hız, alçalma
yasasının o anki girdisi (alan oranı mı irtifa yedeği mi), tavan ve emredilen
hız, katsayılar, seçilen noktanın boşluğu/alanı/riski/uzaklığı.

Emredilen hız ve tavan `/eland/state`'ten okunuyor, HUD'da yeniden
hesaplanmıyor — böylece HUD ile kontrolcü sessizce ayrışamaz.

Panelde "P, not PID" yazıyor, çünkü yasa gerçekten oransal: integral terim
rüzgârsız uçuşta yalnızca windup üretir, türev terimin işini de goto
setpoint'inin jerk-sınırlı yumuşatıcısı zaten yapıyor. Ki ve Kd'yi sıfır diye
göstermek olmayan bir ayar düğmesi varmış izlenimi verirdi.

`hud:=false` ile kapatılabilir.

---

## Ayarlanabilir yerler

Hepsi `eland_sim/config/eland_params.yaml` içinde, hepsi yorumlu. En çok
dokunacakların:

- `safe_classes` / `hazard_classes` — neyin inilebilir, neyin ayrım gerektirdiği
- `r_hazard` (3.0 m) — SORA ayrımı. Mutlak.
- `r_fit` (1.0 m) — araç sığıyor mu. Geometri, politika değil.
- `min_area_m2` (9.0) — bölge şeklinden bağımsız alan eşiği
- `r_ideal` (8.0 m) — **sığdırılmak istenen daire.** İniş noktasını kenardan
  içeri çeken şey bu. Büyütürsen daha açık ama daha uzak yerlere gider.
- `w_risk` / `w_distance` / `w_clearance` (0.50 / 0.15 / 0.35) — skorun üç
  terimi. `w_clearance` olmadan çim üzerinde risk her yerde 0 olduğu için
  formül "en yakın uygun hücre"ye çöker, o da dışlama bölgesinin tam sınırı
  yani yolun kenarıdır.
- `descent_size_gain` / `descent_min_mps` / `descent_max_mps` — alçalma yasası
- `max_landing_attempts` (3) / `search_timeout_s` (60) — pes etme sınırları
- `memory_tau_s` (30 s) — harita hafızası. **Düşürme:** onsuz araç inemiyor,
  gerekçesi `mapping_node.py` başlığında.

Hareketli engeller ve yörünge-farkında karar:

- `obstacle_driver.*` — senaryo: iki engelin başlangıç/hedef/hızı,
  `person_kind` (`model` / `actor`), `vehicle_mode` (`once` / `pingpong`).
  Simülasyon tarafı; uçuş zinciri bunları okumaz.
- `tracker_node.horizon_s` (10 s) — tahmin ufku. 4 s ölçülerek yetersiz
  bulundu: araç haritanın dışındayken karar verilip tam üstüne inilmişti.
- `tracker_node.track_timeout_s` (6 s) — haritadan çıkan engel ne kadar
  "yaşamaya" devam eder. Güven bu süre boyunca sıfıra iner.
- `detector_node.trajectory_filter_enabled` — **karşılaştırma koşusu için
  kapatılır.** Kapalıyken sistem tamamen reaktif SafeLand davranışına döner.
- `detector_node.corridor_memory_s` (25 s) — süpürülmüş güzergâh hafızası.
  Sıfırlanırsa araç, engel geçer geçmez tam onun hattına iner (ölçüldü:
  hattan 0.37 m).
- `detector_node.w_stickiness` (0.15) — seçim kararlılığı. Sıfırlanırsa
  koridor kaydıkça aday zıplar ve mod bunu aday kaybı sayar.
- `detector_node.latch_site` (true) — seçilen nokta bütün testleri geçmeye
  devam ettiği sürece korunur. Kapatılırsa karar her karede yeniden verilir;
  ölçülen bedeli bir inişte 1 yerine 3 aday kaybı ve `committing anyway` ile
  reddedilmiş noktaya iniş.
- `control_station.reassert_manual` (true) — failsafe aracı geri alırsa
  POSCTL isteğini tekrarlar. `false` yapmak eski davranışı verir: tuş çalışır
  gibi görünür, araç yine de iner.
