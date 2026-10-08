# slz-safelanding — İHA acil iniş: güvenli iniş yeri seçimi ve görüntü-tabanlı dikey iniş

> **English summary.** Bachelor-thesis project: an emergency landing system
> for a multicopter, in simulation (PX4 v1.17 SITL + Gazebo Harmonic + ROS 2
> Jazzy). A registered PX4 flight mode (`px4_ros2::ModeBase`, replaces RTL)
> does the following:
> - Projects a downward segmentation camera's class mask onto a ground map.
> - Picks a landing site that passes four tests (SORA separation, fit, class
>   edge, and where moving people and vehicles are going).
> - Descends onto it with a closed-loop vertical-speed controller.
>
> A vision-based vertical descent controller is being designed (MATLAB/
> Simulink) from a 218-episode recorded dataset, downloadable from the
> [`v6.8-veri-seti` release](https://github.com/adakarda/slz-safelanding/releases/tag/v6.8-veri-seti).
> Docs are in Turkish; start with [`AGENTS.md`](AGENTS.md) (working rules)
> and [`docs/README.md`](docs/README.md) (map of all documents).

**Projeye yeni katıldıysan:** [`docs/YENI_KATILAN.md`](docs/YENI_KATILAN.md).
Rolüne göre nereden başlayacağını, veriyi nereden indireceğini ve AI ajanınla
nasıl çalışacağını anlatır. Bu projede bilgi kaynağı GitHub: dokümanlar,
kod, sürüm etiketleri ve veri seti Release'i.

---

## Proje

Lisans bitirme tezi. Bağlantı kopunca devreye giren, PX4'ün Return modunun
yerine kayıtlı resmi bir uçuş modu (offboard değil).

- **Araç ve algı:** x500 quadrotor (2.0 kg), aşağı bakan tek bir
  segmentasyon kamerası.
- **Harita:** sınıf maskesi yere izdüşürülüp zamanda birleştirilir
  (40 × 40 m, 0.2 m hücre).
- **İniş yeri seçimi, dört test:**
  1. SORA ayrımı (insan, araç, yapı, suya ≥ 3 m);
  2. geometrik sığma;
  3. sınıf dikişi;
  4. **hareketli engellerin gideceği yer.** Bu çalışmanın katkısı;
     SafeLand'in tepkisel HOLD/ABORT davranışı yedek olarak duruyor.
- **İniş:** seçilen noktanın üstüne gidiş, sonra kapalı çevrim dikey hız
  kontrolüyle iniş.

Tezin iki ana hattı:
1. **Hareketli engelleri hesaba katan iniş yeri seçimi:** çalışıyor, ölçüldü.
2. **Görüntüden ölçülen büyüklüklerle dikey iniş kontrolcüsü:** tasarım
   sürüyor; veri toplandı.

## Şu an nerede (2026-10-05)

| | Durum |
|---|---|
| Uçtan uca acil iniş (simülasyon) | çalışıyor; 10 rastgele dünyada 10/10 iniş, RMS dikey takip 0.19 m/s |
| Dikey hız iç döngüsü (PI + ileri besleme) | çalışıyor; RMS takip hatası 0.32 → 0.20 m/s |
| Veri toplama hattı ve veri seti | **218 bölüm**, indir: Release [`v6.8-veri-seti`](https://github.com/adakarda/slz-safelanding/releases/tag/v6.8-veri-seti), açıklama [`docs/VERI_SETI.md`](docs/VERI_SETI.md). Araçlar `tools/veri/` |
| Görüntü-tabanlı dikey kontrolcü | **tasarımda.** Proje sahibi ayrı bir sohbette (Simulink) tasarlıyor. Gözlemcili dış çevrim Simulink'te nominal çalışıyor (2026-10-05); mod kodunda henüz yok. Durum ve kararlar [`docs/KONTROLCU_TASARIM_DURUMU.md`](docs/KONTROLCU_TASARIM_DURUMU.md); ölçümler [`docs/KONTROLCU_OLCUMLERI.md`](docs/KONTROLCU_OLCUMLERI.md) |
| Mod `/eland/rho` (ρ, 10 Hz) kullanımı | yayın hazır (varsayılan kapalı); modda kullanımı tasarım doğrulanınca |
| Yükseltilmiş hedef (W5) | bilinen sınır: EKF irtifası hedefin ~4 m üstünde, temas ~1.5 m/s; gözlemci tasarlanacak |
| Gerçek segmentasyon modeli | ertelendi; maske şu an Gazebo'nun kusursuz etiketi |

- **Son sürüm:** `v6.8-veri-seti` (veri seti Release'i ve yeni katılan
  dokümanları).
- **Çalışan sürüm yedeği:** etiket `yedek-calisan-2026-10-05`.
- **Ayrıntılı durum ve açık işler:**
  - [`docs/YAPILACAKLAR.md`](docs/YAPILACAKLAR.md), başındaki güncel durum
    bölümü;
  - [`docs/KONTROLCU_TASARIM_DURUMU.md`](docs/KONTROLCU_TASARIM_DURUMU.md).

## Mimari

```
Gazebo segmentasyon kamerası (320×240, 10 Hz, gövdeye sabit)
  -> /camera/segmentation          ros_gz_image köprüsü
  -> perception_node    -> /eland/semantic_mask        sınıf maskesi (0..7)
  -> mapping_node       -> /eland/ground_map           füzyonlu harita (iniş kararı)
                        -> /eland/ground_map_instant   tek kare (hareket)
  -> tracker_node       -> /eland/dynamic_obstacles    hareketli engeller + tahmin
  -> detector_node      -> /eland/candidate            iniş adayı (~1.8 Hz)
                        -> /eland/rho                  ρ, maske hızında (varsayılan kapalı)
  -> emergency_landing_mode (C++)  durum makinesi + alçalma yasası + PI -> PX4 setpoint'leri, /eland/state
```

- **PX4'e yazan tek düğüm** `emergency_landing_mode`.
- **Durumlar:** SEARCH → APPROACH → VALIDATE (alçalma, kontrolcünün çalıştığı
  faz) → COMMIT (son 2 m) → iniş. Yan durumlar HOLD ve ABORT.
- **Ayrıntı:** [`docs/DEVIR.md`](docs/DEVIR.md) §2-§5,
  [`src/README.md`](src/README.md).

## Hızlı başlangıç

**Yalnız veriyle çalışacaksan** (MATLAB/Simulink, Python): simülasyon kurmana
gerek yok.
- Veriyi [`v6.8-veri-seti`](https://github.com/adakarda/slz-safelanding/releases/tag/v6.8-veri-seti)
  Release'inden indir; `eland_veri_matlab_2026-10-04.zip` yeterli.
- Okuma örnekleri ve tuzaklar: [`docs/VERI_SETI.md`](docs/VERI_SETI.md).

**Simülasyonu çalıştıracaksan:**

**Gereksinimler:**
- Ubuntu (bu proje WSL2'de), ROS 2 Jazzy, Gazebo Harmonic (gz-sim 8),
  `MicroXRCEAgent`, `ros_gz_image`.
- PX4-Autopilot, `~/PX4-Autopilot`'ta, commit `f63b0d6b6f`.

**Sürüm eşleşmesi zorunlu:**
- `px4_msgs` ve `px4-ros2-interface-lib` [`dependencies.repos`](dependencies.repos)'taki
  commit'lerde olmalı.
- Yoksa mod kaydı "Registration failed" ile düşer.

```bash
cd ~/ros2_ws && vcs import src < dependencies.repos
source /opt/ros/jazzy/setup.bash && colcon build && source install/setup.bash
~/ros2_ws/src/eland_sim/scripts/link_px4_assets.sh     # modelleri PX4 ağacına bağla (bir kez)
```

Çalıştır:

```bash
./src/eland_sim/scripts/dene.sh otomatik    # penceresiz, kalkış + mod otomatik; karar döngüsü özeti
./src/eland_sim/scripts/dene.sh hud         # Gazebo + HUD + kontrol istasyonu, elle uçur
N=5 ./src/eland_sim/scripts/dene.sh toplu   # 5 rastgele dünyada istatistik
./src/eland_sim/scripts/run_sim.sh --headless --auto   # alt seviye, tek komut
```

**`dene.sh otomatik`'ten beklenen:** `aday uretilmeyen 0/150`,
`aday kaybi: 0`, üç durum geçişi, tek denemede iniş.

Kayıtlı bir veri bölümü:

```bash
RUN_SIM_MOD_TEKRAR=2 tools/veri/kosu.sh 1 kol0 veri_w2
```

Kurulumun tamamı ve sorun giderme: [`src/README.md`](src/README.md),
[`docs/DEVIR.md`](docs/DEVIR.md) §6-§7, §11.

## Depo haritası

```
README.md              bu dosya
AGENTS.md              AI ajanları ve insanlar için çalışma kuralları (CLAUDE.md bunu içe alır)
CLAUDE.md              Claude Code girişi
dependencies.repos     px4_msgs, px4-ros2-interface-lib sabit commit'leri (vcs import)
src/
  eland_msgs/          LandingCandidate, LandingState, DynamicObstacle(Array), GoruntuKapsami
  eland_common/        sınıf tablosu, palet, QoS, PX4 topic adları
  eland_perception/    kamera -> sınıf maskesi
  eland_mapping/       IPM + füzyon haritası, tracker_node, detector_node
  eland_mode/          C++ PX4 modu: durum makinesi, alçalma yasası, dikey PI
  eland_viz/           HUD ve kontrol istasyonu
  eland_sim/           Gazebo modelleri ve dünyaları, launch, config/eland_params.yaml,
                       scripts/ (run_sim.sh, dene.sh, link_px4_assets.sh, ...)
tools/                 ölçüm ve analiz araçları          -> tools/README.md
  veri/                veri toplama ve veri seti          -> tools/veri/README.md
docs/                  dokümanlar                         -> docs/README.md
  YENI_KATILAN.md          yeni katılan için başlangıç
  KONTROLCU_TASARIM_DURUMU.md  kontrolcü işi nerede, kararlar, sıradaki
  KONTROLCU_OLCUMLERI.md   kontrolcü için ölçülmüş her şey
  VERI_SETI.md             veri seti: indirme, yapı, okuma, tuzaklar
  geri_bildirim/       kontrolcüyü tasarlayan sohbete giden promptlar
```

- **Depoda olmayanlar** (`.gitignore`): `build/`, `install/`, `log/`,
  `src/px4_msgs/`, `src/px4-ros2-interface-lib/`.
- **Veri seti GitHub Release'inde** (`v6.8-veri-seti`), deponun içinde değil.
  Proje sahibinin makinesinde `~/eland_veri/`; tam arşiv ev dizinine
  açılınca aynı yol oluşur.
- **PX4-Autopilot depo dışında:** `~/PX4-Autopilot`, commit `f63b0d6b6f`.
- **Simulink modeli proje sahibinde,** depoda değil.

## Dokümanlar

Harita: [`docs/README.md`](docs/README.md).

| Ne arıyorsun | Dosya |
|---|---|
| Nereden başlarım | [`docs/YENI_KATILAN.md`](docs/YENI_KATILAN.md) |
| Kontrolcü işi ne durumda, ne kararlaştırıldı | [`docs/KONTROLCU_TASARIM_DURUMU.md`](docs/KONTROLCU_TASARIM_DURUMU.md) |
| Veri seti: indirme, yapı, MATLAB'da okuma | [`docs/VERI_SETI.md`](docs/VERI_SETI.md) |
| Kontrolcü için ölçümler (tesis, gecikmeler, ρ, EKF, temas hızı) | [`docs/KONTROLCU_OLCUMLERI.md`](docs/KONTROLCU_OLCUMLERI.md) |
| Kontrolcü tasarım brifi | [`docs/KONTROLCU_TASARIM_BRIEF.md`](docs/KONTROLCU_TASARIM_BRIEF.md) |
| Projeyi baştan devralmak | [`docs/DEVIR.md`](docs/DEVIR.md) |
| Veri toplama, turlar, kararlar | [`docs/VERI_TOPLAMA.md`](docs/VERI_TOPLAMA.md) |
| Mühendislik günlüğü | [`docs/DURUM.md`](docs/DURUM.md) |
| Teze girecek sayılar | [`docs/TEZ_NOTLARI.md`](docs/TEZ_NOTLARI.md) |

## Çalışma kuralları (özet)

Tam liste ve gerekçeleri: [`AGENTS.md`](AGENTS.md).

1. **Mevcut kodu değiştirmeden önce plan yaz, onay al.** Değişiklik
   parametreyle seçilsin, varsayılanı kapalı olsun. Kapalıyken eski davranış
   bir koşuyla gösterilsin.
2. **Ölçmediğini "çalışıyor" diye yazma.** Her sayının yanında nasıl
   ölçüldüğü; etiket ölçülen / _hesap / _tahmin.
3. **Biten her modül commit + sürüm etiketi (`vX.Y-konu`) + push.**
4. **Segmentasyon zincirine ve araç hız kestirimine** proje sahibine
   sormadan dokunma.

## Sürümler

Etiket geçmişi projenin yol haritası; her etiket çalışan bir durum ve
mesajı neyin neden yapıldığını söyler. Tamamı:
`git tag -n1 --sort=creatordate`.

| Etiket | Kilometre taşı |
|---|---|
| `v1.0-baseline` | ilk uçtan uca çalışan sürüm |
| `v1.2-dynamic-obstacles` | hareketli engeller ve yörünge-farkında karar |
| `v2.0-sora-taxonomy` | simülatör ve model aynı 7 sınıflı SORA taksonomisinde |
| `v2.2-decision-loop` | karar döngüsü profili ve düzeltmeleri |
| `v2.7-descent-rate-loop` | dikey eksen: PI + ileri besleme |
| `v3.1-disturbance` | bozucu bastırma: 20 N tutuluyor, 15 N'da algı çöküyor |
| `v3.5-devir` | devir dokümanı |
| `v4.2-kamera-10hz` | kamera 10 Hz |
| `v4.4-kontrolcu-brifi` | görüntü-tabanlı kontrolcü tasarım brifi |
| `v4.6-veri-kaydedici` | veri kaydedicisi |
| `v4.8-k5-tesis` | tesis yeniden ölçüldü: ölü zaman 0.04-0.06 s |
| `v5.3-veri-tur2` | veri seti: 218 bölüm |
| `v5.7-rho-yayini-commit-irtifa` | `/eland/rho` yayını, COMMIT irtifa yasası |
| `v6.1-commit-irtifa-varsayilan` | COMMIT irtifa yasası varsayılan |
| `v6.3-tur4-kararlar` | birincil ölçüt `basarili_v10`, `run_sim` temizliği |
| `v6.5-mod-secim-tekrar` | mod seçme kontrolü ve yeniden deneme (varsayılan kapalı) |
| `yedek-calisan-2026-10-05` | doküman düzenlemesinden önceki çalışan sürüm (yedek; aynı adlı dal da var) |
| `v6.7-dokuman-duzeni` | README, AGENTS/CLAUDE, doküman haritası, kontrolcü ölçümleri tek dosyada |
| `v6.8-veri-seti` | veri seti Release'i (218 bölüm), yeni katılan ve kontrolcü durum dokümanları |

Geri dönmek için: `git checkout <etiket>`.

## Katkı

- **Yeni katılanlar:** önce [`docs/YENI_KATILAN.md`](docs/YENI_KATILAN.md),
  sonra [`AGENTS.md`](AGENTS.md) ve [`docs/README.md`](docs/README.md).
- **Önerilen akış:** kendi dalında çalış, değişikliği PR ile öner.
- **Mevcut uçuş davranışını değiştiren her şey** proje sahibinin onayıyla.
- **Proje sahibi:** [@adakarda](https://github.com/adakarda).
