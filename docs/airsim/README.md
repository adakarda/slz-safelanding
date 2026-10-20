# AirSim hattı

Gazebo'nun yanında ikinci bir simülasyon hattı. Dal `airsim`. Gazebo hattı silinmedi ve çalışır durumda.

- **Windows tarafı:** AirSim 1.8.1 (Unreal 4.27) dünyayı, fiziği, kamerayı ve segmentasyonu çalıştırır.
- **WSL tarafı:** PX4 SITL v1.17 (`none_iris`), uXRCE-DDS, algı zinciri, modlar ve RL politikası.

RL eğitimi her zamanki hafif ortamda sürer. AirSim yalnız test dünyasıdır.

## Neler nerede

| Yer | İçerik |
|---|---|
| `C:\Users\arda_\airsim\AirSimNH\`, `CityEnviron\` | Hazır AirSim dünyaları (GitHub microsoft/AirSim v1.8.1 sürümü) |
| `C:\Users\arda_\airsim\venv\` | Windows Python + `airsim` paketi + msgpack-rpc ara katmanı (kamera kipindeki çekimler için) |
| `C:\Users\arda_\airsim\pilot\` | Kamera kipi ayarları ve çekim betikleri (Windows'tan koşar) |
| `~/airsim-venv` | WSL'deki AirSim istemcisi (`airsim` + `data/msgpackrpc_shim.py`, sistem paketleri açık) |
| `src/eland_airsim/` | ROS 2 paketi: köprü, sınıf kuralları, çerçeve dönüşümü, ölçüm araçları |
| `PX4-Autopilot/build/px4_sitl_default/rootfs_airsim/` | AirSim'in PX4 klasörü. Gazebo'nunkinden (`rootfs`) ayrı. |

## Çalıştırma

```bash
# AirSim + PX4 + ROS 2 zinciri; 25 m'ye kalk, Emergency Landing'i seç
src/eland_airsim/scripts/run_airsim.sh --takeoff 25 --trigger

# Aynısı, maske v3'ten
src/eland_airsim/scripts/run_airsim.sh --takeoff 25 --trigger --v3

# RL modu (hafif ortamda eğitilmiş politika), 10 m kalkanla
src/eland_airsim/scripts/run_airsim.sh --takeoff 25 --trigger --rl ~/rl_inis/kos/b_B2_s0/model.zip --kalkan 10

# Başlangıç noktası (PlayerStart'a göre NED m) ve 5 m/s doğu rüzgârı
src/eland_airsim/scripts/run_airsim.sh --takeoff 25 --trigger --baslangic -124.1,-64.3 --ruzgar 0,5,0

# Toplu ölçüm: başlangıç listesinden inişler, AirSim gerçeğiyle ölçülür
src/eland_airsim/scripts/inis_sina.sh ~/eland_veri/airsim_nh_baslangiclar.csv [--v3] [--rl M] [--kalkan 10]

# PX4 bağlantı sınaması (kalk, 60 s askı, in; 3 kez)
src/eland_airsim/scripts/px4_sina.sh
```

Başka bir sim açıkken (px4 ya da gz) run_airsim.sh başlamaz. Windows'ta en az 1.8 GB boş bellek ister.
Bellek bekçisi: boş bellek 30 s boyunca 500 MB'ın altında kalırsa AirSim'i kapatır.

## Gazebo'daki her parça neye karşılık geliyor

| Gazebo | AirSim | Not |
|---|---|---|
| `gz sim` + `x500_seg_cam_down` | AirSim çok rotorlu araç, `config/settings_px4.json` | Kamera `asagi`: 640×480 RGB, 320×240 segmentasyon, FOV 99.7°, dikey |
| PX4 `gz_x500` (4001) | PX4 `none_iris` (10016), TCP 4560, kilitli adım | `-w rootfs_airsim` şart (aşağıda) |
| ros_gz_image köprüleri | `eland_airsim.kopru` | `/camera/image`, `/camera/segmentation` (sınıf+1), `/eland/gercek_poz` |
| gz etiket haritası | `eland_airsim.siniflar`: nesne adı → SORA sınıfı → segmentasyon kimliği | Kurallar AirSimNH ve CityEnviron adlarıyla denendi |
| gz `dynamic_pose` | `simGetGroundTruthKinematics` → `/eland/gercek_poz` (ENU/FLU) | Aracın kendi doğuş noktasına göre |
| rüzgâr modeli | `simSetWind` (`--ruzgar`, `ruzgar_ned` parametresi) | |
| engel sürücüsü | yok | AirSimNH'de yürüyen insan ya da araç yok; yalnız hayvanlar |
| algı, harita, dedektör, modlar, HUD | aynı, kod değişmeden | `obstacles:=false` |
| RL `policy_node` | aynı düğüm | `pose_source:=topic` |

## Kurallar ve sınırlar

- **PX4 parametreleri.** AirSim'in PX4'üne Gazebo rootfs'unun kayıtlı değerleri uygulanır
  (`config/px4_gazebo_esdeger.params`). Airframe farkları araç modelinin parçasıdır.
- **Segmentasyon gerçeği kaba.**
  - AirSimNH'nin `Road` karoları asfaltla birlikte kenardaki çim şeridini ve kaldırımı da kapsar.
  - CityEnviron'da asfalt, `Landscape` nesnesinin parçasıdır.
  - İniş noktası bu yüzden ortografik etiket haritasından değerlendirilir (`araclar/inis_harita.py`).
- **v3 hazır dünyalarda eşiği geçmedi** (Faz 1). AirSimNH'de güvenli/değil doğruluğu 0.754, mIoU 0.521; eşik
  0.85 / 0.55. v3, asfaltı "sert zemin" sanıyor.

## Bulunan ve düzeltilen hatalar

Her biri bir koşuyu ya da ölçümü bozdu. Ayrıntı ön kayıtlarda.

| Hata | Belirti | Düzeltme |
|---|---|---|
| Uzun regex kalıbı AirSim'de sessizce başarısız | CityEnviron'da bir sınıf boyanmıyor | Kalıplar 6 kelimelik parçalar (`siniflar.CHUNK`) |
| Köprü RGB'nin `camera_info`'sunu yayınlıyordu | mapping_node K'yı 320×240 maskeye uyguladı; aday yaklaşırken kayboldu | `kamera_bilgisi` varsayılan kapalı, Gazebo gibi |
| `ros2 launch`'ın alt düğümleri yetim kaldı | Koşudan koşuya birikti; bellek 623 MB'a düştü | Kapanışta ada göre de kapatılıyor |
| PX4 v1.17 `-w` olmadan `build/rootfs`'u kullanır | Gazebo'nun kayıtlı parametreleri ezildi | `-w rootfs_airsim`; Gazebo dosyası ULog'dan geri yüklendi |
| policy_node etiket aboneliği "reliable" | Politika hiç adım atmadı | Best effort (`SENSOR_QOS`) |
| RL modu DDS hazır olmadan başlatıldı | "Registration failed" | Kalkıştan sonra başlatılıyor |
| AirSim uçuşta ya da açılışta öldü (önce 4/10, sonra ~%9) | Bütün API bağlantıları birden düştü, PX4 kilitli adımda dondu, PX4 komutları sonsuza dek bekledi | Kök neden açık. Ölçüm betiğinin 20 Hz derinlik isteği 1 Hz'e indi; PX4 istemci komutlarına 10 s zaman aşımı; batch çöken ya da başlamayan denemeyi 3 kereye kadar tekrarlıyor ve sayıyor |
| Çalışan bir bash betiğini düzenlemek | Çalışan kopya yarı eski, yarı yeni satır okur | Betik gövdeleri `{ ... exit; }` içinde |

## Sonuçlar

Ölçülen; tek tohum, AirSimNH'de 10 başlangıç, ikinci tur (PX4 eş parametreleriyle). Ön sonuç.

| Kol | İndi | Güvenli zemin | SORA (tehlikeye ≥ 3 m) | Ağaç/çit/yapıya temas |
|---|---|---|---|---|
| Klasik mod, AirSim etiketi | 10/10 | 10 | 8 | 0 |
| Klasik mod, v3 maskesi | 10/10 | 4 (6 yol) | 4 | 0 |
| RL B2-s0, kalkansız | 10/10 | 7 | 5 | 1 |
| RL B2-s0, kalkan 10 m | 10/10 | 10 | 5 | 0 |
| Klasik, 5 m/s rüzgâr | 10/10 | 8 (temasa göre 10) | 5 | 0 |
| RL kalkansız, 5 m/s rüzgâr | 10/10 | 8 | 4 | 2 |

Ayrıntılı tablolar ve görseller: AirSim Taşıma Yol Haritası sayfası. Ön kayıtlar:

- `docs/onkayit/airsim_faz3_onkayit.md`
- `docs/onkayit/airsim_faz4_onkayit.md`
- `docs/onkayit/airsim_faz5_onkayit.md`

**Sonrası (2026-10-18 – 10-20):** Faz 6 (v3 maskesiyle RL 10 inişin 9'unda yola indi), havada başlangıç
(`run_airsim.sh --havada`) ve çatı üstü gösterim (c13 s0, 6/6 çatıdan kayıp güvenli zemine indi). Tablolar ve
yorum: [`../rl_airsim/RAPOR.md`](../rl_airsim/RAPOR.md) §5.2. Çalıştırma ve kurulum:
[`../rl_airsim/README.md`](../rl_airsim/README.md).

## Açık konular

- **Dünya seçimi (Arda).** AirSimNH ile devam, UE5 (Colosseum ya da Cosys-AirSim), fotogrametri, ya da v3 ince
  ayarı.
- **`COM_RC_LOSS_T`.** Gazebo rootfs'unda 3.0 kayıtlı, run_sim.sh ise 0.5'in doğru olduğunu söylüyor. AirSim de
  şimdilik Gazebo'nun değerini (3.0) kullanıyor.
- **Mod.** Bir koşuda COMMIT'te PX4 "invalid setpoints → blind land" failsafe'i verdi. Bu, camera_info
  hatasının yanlış adayıyla oldu ve sonra tekrarlanmadı. Mod koduna dokunulmadı.
- **Hafif ortam için ikinci dinamik set (öneri).** tau_z 0.35 s, dikey gecikme 0.06 s, a_max 1.0 m/s². AirSim
  ölçümünden; eğitime dokunulmadı.
- **Engeller.** AirSim'de engel sürücüsü yok. Hazır dünyada hareketli insan ya da araç yok.
