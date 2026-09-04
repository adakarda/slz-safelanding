# Durum Raporu — Şu Ana Kadar Yapılanlar

Tarih: 2026-09-02
Çalışma alanı: `~/ros2_ws` (git deposu, 2 commit)
Kapsam: `src/eland_*` paketleri

Bu dosya projeyi **geliştirmeye devam etmek için** yazıldı: ne var, ne
doğrulandı, nereye dokunulursa ne kırılır, sırada ne var. Tasarım gerekçeleri
`docs/PLAN.md`'de, gereksinim uyumu `docs/CHECKLIST.md`'de, çalıştırma
talimatı `src/README.md`'de — burada onlar tekrarlanmıyor, özetlenip
işaret ediliyor.

---

## 1. Bir bakışta

Aşağı bakan bir segmentasyon kamerasından SORA risk kurallarına göre iniş
noktası seçen ve oraya inen, **PX4'e kayıtlı bir ROS 2 uçuş modu**. Offboard
script değil: mod PX4'ün mod listesine giriyor, arming check'lere katılıyor,
failsafe ile tetiklenebiliyor ve ROS node'u ölürse PX4 kendi moduna geri
düşüyor.

Uçtan uca çalışıyor. Doğrulanmış senaryo: gerçek bir GCS bağlantısı kesiliyor →
PX4 failsafe → bu mod devreye giriyor → aday nokta seçiliyor → yaklaşıyor →
iniyor → **disarm**. Kimse müdahale etmiyor.

| | |
|---|---|
| Toplam kod | ~3.400 satır (7 paket) |
| Faz durumu | 0 ✅ · 1 ✅ · 2 ✅\* · 3 ✅ · 4 ✅ · 5 ✗ başlanmadı |

\* Faz 2'nin gövdesi (zamansal füzyon + gerçek IPM + renkli debug görüntüsü)
tamamlandı ve doğrulandı, ama `PLAN.md`'nin başlığı ile `CHECKLIST.md`'nin faz
tablosu hâlâ "IPM bekliyor" diyor — bu iki satır bayat, bkz. §8/8.
| Checklist | 17 madde: **15 ✅, 2 ⚠️, 0 ❌** |
| Aktivasyondan disarm'a | **27 s** (16.8 s alçalma + 9.7 s temas) |

---

## 2. Ortam — pinler yük taşıyor

| Bileşen | Sürüm / durum |
|---|---|
| ROS 2 | Jazzy |
| Gazebo | `gz sim 8.11.0` (Harmonic) |
| PX4-Autopilot | `main` @ `f63b0d6b6f` (2026-05-01, v1.17.0-alpha1-1670) |
| px4_msgs | `e62353e` — **sabit** |
| px4-ros2-interface-lib | `9fb7cea` — **sabit** |
| GPU | **yok** — llvmpipe (yazılımsal render) |

Bu üçlü aynı tarihten olmak zorunda. Değilse hata derlemede değil, **mod
kaydında** çıkar:

```
MessageFormatResponse::success == false for fmu/in/setpoint_config
Registration failed
```

Pinler `dependencies.repos` içinde, gerekçesiyle birlikte. PX4 güncellenirse
diğer ikisi de ilerletilmeli (`px4_msgs` commit mesajları `Update to PX4 <sha>`
formatında, eşleşeni bulmak mekanik).

GPU yokluğu Faz 5'i (gerçek segmentasyon modeli) fiilen bloke ediyor: llvmpipe
üzerinde CPU inference + CPU render aynı anda anlamlı hızda çalışmıyor.

---

## 3. Depo durumu

```
4679d19  Control station: HUD and keyboard in one window     (2026-09-02)
3d92530  Emergency landing mode: working end-to-end baseline  (2026-09-02)
```

Çalışma ağacında yalnızca 4 script'te **dosya izni (mode) değişikliği** var
(`100755 → 100644`) — Windows/WSL üzerinden dokunulduğu için. İçerik
değişikliği yok. WSL tarafında `chmod +x` ile geri alınabilir; script'ler
`run_sim.sh` tarafından çağrıldığı için execute biti gerçekten gerekli.

Vendor edilmeyenler (`.gitignore`): `src/px4_msgs/`,
`src/px4-ros2-interface-lib/` (kendi depoları, pinleri `dependencies.repos`'ta),
`src/ilk_offboard/` (bu işle ilgisi olmayan eski paket).

---

## 4. Paketler ve veri akışı

| Paket | Dil | Satır | İş |
|---|---|---|---|
| `eland_msgs` | CMake | — | `LandingCandidate`, `LandingState` |
| `eland_common` | Python | 169 | Sınıf ID'leri, renk paleti, QoS profilleri, PX4 topic adları |
| `eland_perception` | Python | 188 | Kamera → `mono8` semantik maske |
| `eland_mapping` | Python | 833 | IPM + zamansal füzyon (472) ve aday seçimi (361) |
| `eland_mode` | C++ | 657 | `px4_ros2::ModeBase` — PX4'e kayıtlı "Emergency Landing" |
| `eland_viz` | Python | 749 | HUD (341) + kontrol istasyonu (408) |
| `eland_sim` | Python | ~780 | Gazebo modelleri, dünya, launch, parametreler, script'ler |

```
gz segmentation camera
  -> /camera/segmentation      (ros_gz_image bridge)
  -> perception_node   -> /eland/semantic_mask      (~3 Hz)
  -> mapping_node      -> /eland/ground_map         (~3 Hz, + _colored)
  -> detector_node     -> /eland/candidate          (~1.4 Hz)
  -> eland_mode        -> PX4 setpoint'leri, /eland/state
```

**`eland_mode` dışında hiçbir node PX4'e yazmaz.** Bu sınır kasıtlı; yeni bir
node eklerken korunmalı.

---

## 5. Karar mantığı — özet

**Sınıflar (10):** unknown / grass / dirt / gravel / pavement / vegetation /
building / water / vehicle / person. Tek kaynak: `eland_common/classes.py`.
`unknown = 1.0 risk` — etiketsiz piksel değerlendirilmemiş pikseldir,
değerlendirilmemiş piksel de temizlenmiş sayılmaz.

**Uygunluk — üç bağımsız test (hepsi geçilmeli):**

| Test | Değer | Ne sorar |
|---|---|---|
| `bölge_alanı ≥ min_area_m2` | 9.0 m² | Şekilden bağımsız, oturulacak yer var mı |
| `dist_fit ≥ r_fit` | 1.0 m | Araç fiziksel olarak sığıyor mu (geometri) |
| `dist_hazard ≥ r_hazard` | 3.0 m | SORA ayrımı — **mutlak, pazarlıksız** |

`r_fit` ile `r_hazard`'ı ayırmak kritikti: tek bir 3 m eşiği, çevresi tamamen
boş olsa bile 6 m'den dar her bölgeyi eliyordu.

**Skor (minimize edilir):**
`0.50 * risk + 0.15 * normalize_mesafe + 0.35 * clearance_shortfall`

`w_clearance` olmadan formül "en yakın uygun hücre"ye çöküyor — çimde risk her
yerde 0 olduğu için — ve o hücre tanım gereği dışlama bölgesinin sınırı, yani
yolun kenarı. `r_ideal` (8.0 m) sığdırılmaya çalışılan daire; büyütmek daha
açık ama daha uzak noktalar seçtirir.

**Alçalma yasası** (`v_ceiling = clamp(k*sqrt(area_m2), 0.3, 2.0)`,
`v = clamp(v_ceiling * (1 - area_ratio), 0.3, v_ceiling)`): kontrol değişkeni
irtifa değil, iniş bölgesinin görüntüyü doldurma oranı. `area_ratio` "ne kadar
yakınım", `area_m2` "ne kadar büyük" — ikincisi tavanı belirliyor, yoksa 4 m'lik
bir pada 10 m'likten daha hızlı dalınırdı. `view_bounded` false iken (bölge
kadrajdan taşıyor) oran yakınlık bilgisi taşımadığı için irtifa yedeğe geçiyor.

Yasa gerçekten oransal: integral terim rüzgârsız uçuşta yalnızca windup üretir,
türev terimin işini de goto setpoint'inin jerk sınırlı yumuşatıcısı yapar.

**Durum makinesi** (C++ modun içinde, `SEARCH / APPROACH / VALIDATE / HOLD /
ABORT / COMMIT`), her geçiş `reason` string'iyle `/eland/state`'te yayınlanıyor.
Sınırlar: `max_landing_attempts: 3`, `search_timeout_s: 60`. İkisi de `<= 0` ile
kapatılabilir.

---

## 6. Doğrulanmış ölçümler

Hepsi bu makinede, SITL'de ölçüldü — iddia değil.

**Algı zinciri:** 25 m'de 8 sınıf görülüyor; maske ~3 Hz, harita ~3 Hz, aday
~1.4 Hz; `real_time_factor` 1.00 (tüm pipeline çalışırken).

**SORA ayrımı bağlayıcı:**

| Senaryo | Aday yarıçapı |
|---|---|
| Açık çim, insan yok | **8.56 m** (mesafe dönüşümü insanı buluyor: 8.49 m) |
| İnsan 3 m yanda | **3.03 m** — nokta kaydı, `r_hazard = 3.0`'ı ancak geçiyor |

**Uçtan uca iniş** (insanın 3 m yanına doğuş, 20 m'ye kalkış, mod tetikleme):

```
SEARCH   -> APPROACH: candidate #115 accepted, r=3.03 m
APPROACH -> VALIDATE: reached candidate, 0.16 m error
VALIDATE -> COMMIT:   at 1.99 m, committing to touchdown
touchdown detected, mode complete
```

`landed: True`, `arming_state: 1 (DISARMED)`, aktivasyondan disarm'a 27 s.

**Failsafe zinciri** (enjekte edilmiş arıza değil, kurulan GCS bağlantısı
kesildi):

| Kopmadan sonra | nav_state | irtifa |
|---|---|---|
| 15 s | 4 (Hold) | 20.0 m |
| **20 s** | **23 (bu mod)** | 16.2 m |
| 25 s | 23 | 8.8 m |

Gecikme = `COM_DL_LOSS_T` (10 s) + PX4'ün 5 s Hold beklemesi. Sonrası tamamen
otonom, temasa 26 s.

**Mod yaşam döngüsü:** kayıt `Got RegisterExtComponentReply`; atanan ID **23**
(`NAVIGATION_STATE_EXTERNAL1`); node öldürülünce nav_state 23 → **5 (AUTO_RTL)**,
araç düşmüyor. Brief'in "node çökerse PX4 devralır" iddiasının kanıtı bu satır.
Mod ID'si sabit varsayılmamalı — birden fazla harici mod kayıtlıysa değişir.

**IPM doğruluğu**, heading'leri 90° farklı iki koşu (insan gerçekte 3 m güneyde):

| Koşu | PX4 heading | Ölçülen |
|---|---|---|
| A | 1.68 rad | east −0.28, north **−3.04** |
| B | 0.11 rad | east −0.38, north **−3.10** |

Kalan ~0.3 m doğu sapması izole edilmedi (insan boyunun düz zemin varsayımını
ihlali + kamera kol mesafesi). SORA'nın 3 m marjının çok içinde.

**Kontrol istasyonu:** devir 4 → 2, 14.7 m çubukla uçuş, +6.4 m komutlu tırmanış,
süre boyunca failsafe devralması yok.

---

## 7. Tekrar düşülmemesi gereken tuzaklar

Her biri bir kez zaman yedi. Yeni bir şey eklerken bunları hatırla:

1. **Harita hafızası opsiyonel değil.** Kamera ayak izi `2*irtifa*tan(hfov/2)`:
   15 m'de 36 m, 3 m'de 7 m. Hafızasız harita, araç alçalmaya adandığı anda
   zeminin dışını UNKNOWN gösteriyor → `VALIDATE→HOLD→ABORT` döngüsü, 90 s'de
   dört tur, **hiç iniş yok**. `memory_tau_s: 30` bunu kapatıyor. Güvenlikle de
   ilgili: füzyon kapalıyken insan ayak izinden çıkınca haritadan siliniyor ve
   **3 m'lik SORA tamponu da onunla birlikte kayboluyor.**
2. **Temas pozisyon kontrolüyle olmuyor.** Yer seviyesine goto verince araç
   iniyor ama kontrolcü sıfır hataya karşı hover itkisi tutuyor, PX4 `landed`
   demiyor, disarm olmuyor. Son metrelerde dikey eksen **hız** kontrolüne
   geçiyor (`withVelocityZ`), yatay eksen pozisyonda kalıyor.
3. **Projeksiyon attitude ister.** Nadir yaklaşımı heading'i yok sayıyordu ve
   harita kuzey-güney **aynalanmıştı** (grid satır 0 = en güney, görüntü satır 0
   = ileri). Aday hep aracın altındayken ikisi de görünmüyordu.
4. **PX4 ağacına symlink şart.** `px4-rc.gzsim`, `PX4_GZ_WORLDS`/`PX4_GZ_MODELS`'i
   koşulsuz üzerine yazıyor; `GZ_SIM_RESOURCE_PATH` yalnızca iç içe `<uri>`leri
   çözüyor. `link_px4_assets.sh` bunun için var, PX4 `make clean` sonrası tekrar
   çalıştırılmalı.
5. **Yerdeki drone hiçbir şey göremez.** Kamera 0.28 m'de, 99.7° FOV ile 0.66 m
   görüyor — neredeyse tamamen kendi etiketsiz iniş takımı. Maske %100 UNKNOWN
   döner; bozuk sensör değil, doğru davranış.
6. **`replaceInternalMode(Descend)` mümkün değil.** `NAV_RCL_ACT` seçenekleri
   Hold / Return / Land / Terminate / Disarm; Descend listede yok. `"rtl"` seçildi.
7. **GCS bağlantısı olmadan uçuş yok.** `NAV_DLL_ACT` varsayılanı Return ve bu
   mod Return'ün yerine kayıtlı → hiç GCS yoksa araç kalkıştan ~15 s sonra kendi
   kendine iniyor, ne yapıyor olursan ol. Kontrol istasyonu bu yüzden saniyede
   bir GCS heartbeat yolluyor.
8. **Manuel kontrol akışı kendi thread'inde olmalı.** `COM_RC_LOSS_T` 0.5 s;
   `cv2.imshow` takılınca PX4 bunu kumanda kaybı sayıyor. Ayrıca PX4, hiç
   görmediği bir manuel kontrol kaynağına devretmiyor — istasyon önce 2 saniye
   nötr çubuk yayınlıyor.
9. **Label 0 = arka plan.** Gazebo'nun segmentasyon eklentisinde 0 arka plan
   olduğu için sınıf şeması kaydırıldı; SORA'nın 7 sınıfıyla birebir örtüşmeme
   sebebi bu.

---

## 8. Açık kusurlar ve eksikler

| # | Konu | Durum |
|---|---|---|
| 1 | **QGroundControl GUI doğrulaması** | Yapılmadı. Kayıt / aktivasyon / nav_state PX4 topic'lerinden ölçüldü; "QGC listesinde görünüyor" iddiası kanıtlanmadı (dinamik mod listesi için QGC **Daily** gerekiyor). |
| 2 | **Modu geri almanın yolu yok** | `replace_internal_mode: "rtl"` kayıtlıyken kasıtlı RTL de acil inişe dönüşüyor. Operatörün "hayır, gerçekten eve dön" diyebileceği kaçış yolu yok. |
| 3 | **Gerçek segmentasyon modeli (Faz 5)** | Başlanmadı. `use_gt_segmentation:=false` dalı ve `mask_topic` sözleşmesi hazır; GPU'lu makine bekliyor. |
| 4 | **7 SORA sınıfıyla birebir örtüşme yok** ⚠️ | Kasıtlı, label-0 gerekçesiyle. `docs/CHECKLIST.md:45`. |
| 5 | **Alan-oranı kriterinin dar geçerlilik alanı** ⚠️ | `view_bounded` false iken oran yakınlık bilgisi taşımıyor, irtifa yedeğine düşülüyor. `docs/CHECKLIST.md:189`. |
| 6 | **Çözünürlük tavanı** | 15 m'de 0.111 m/px → 0.6 m'lik insan ~5 piksel; 25 m'de ~3 piksel. İrtifa artarsa **önce insan tespiti bozulur.** |
| 7 | **~0.3 m doğu sapması** | IPM'de kalan sistematik sapma izole edilmedi. Marjın içinde ama açıklanmadı. |
| 8 | **Bayat doküman satırları** | `PLAN.md`'nin baş özeti ve `CHECKLIST.md`'nin faz tablosu Faz 2'yi "IPM bekliyor" gösteriyor; ikisi de aynı dosyaların gövdesiyle çelişiyor (IPM tamam ve doğrulandı). Ayrıca 2026-09-02'de eklenen kontrol istasyonu her iki dokümanda da yok — yalnızca `src/README.md`'de. |

---

## 9. Sırada ne var — öneri sırası

1. **QGC Daily ile GUI doğrulaması** (kusur 1). En ucuz açık madde; mod
   listesinde göründüğünü bir kez görüp ekran görüntüsü almak yeter.
   `src/eland_sim/scripts/query_modes.py` zaten PX4 tarafını sorguluyor.
2. **Operatör kaçış yolu** (kusur 2). En küçük hâli: modu runtime'da devre dışı
   bırakan bir servis/parametre, ya da `replace_internal_mode`'u `"none"` yapıp
   failsafe'i ayrı bir yoldan tetiklemek. Güvenlik açısından en anlamlı bir
   sonraki iş bu.
3. **Dünyayı zorlaştır** (PLAN.md açık soru 1). Hareketli insan, ya da iniş
   noktasının çok uzakta olduğu bir senaryo — uzun APPROACH fazını ve füzyonun
   ufkunu birlikte zorlar. `eland_test.sdf` + `run_sim.sh --scenario` altyapısı
   hazır, yeni senaryo eklemek ucuz.
4. **Faz 5 — gerçek segmentasyon** (kusur 3). GPU'lu makine / native Linux
   gerektiriyor. Sözleşme hazır olduğu için pipeline'ın geri kalanı
   değişmeyecek: `perception_node` `mono8` maske üretmeye devam eder.
5. **Regresyon koşusunu otomatikleştir.** Şu an her doğrulama elle. Üç senaryoyu
   `--auto` ile koşup `/eland/state`'ten son durumu ve süreyi toplayan bir
   script, bundan sonraki her değişikliğin bedelini düşürür.

---

## 10. Hızlı referans

```bash
cd ~/ros2_ws && colcon build && source install/setup.bash
```

```bash
~/ros2_ws/src/eland_sim/scripts/link_px4_assets.sh
```

```bash
~/ros2_ws/src/eland_sim/scripts/run_sim.sh --scenario person --auto
```

```bash
~/ros2_ws/src/eland_sim/scripts/run_sim.sh --link-drop
```

```bash
ros2 topic echo /eland/state
```

Loglar: `/tmp/eland_logs/{px4,agent,pipeline}.log`

Kontrol istasyonu tuşları (önce pencereye tıkla): `1` arm · `2` kalkış ·
`3` manuel (POSCTL) · `WASD` / `QE` / `RF` uç · `SPACE` çubukları ortala ·
`0` **acil iniş** · `L` PX4 ile in · `X` disarm · `ESC` çık.

---

## 11. Doküman haritası

| Dosya | İçerik |
|---|---|
| `docs/DURUM.md` | **bu dosya** — anlık durum, ölçümler, sıradaki işler |
| `docs/PLAN.md` | Tasarım kararları, fazlar, tuzakların uzun gerekçeleri |
| `docs/CHECKLIST.md` | Gereksinim maddesi başına uyumluluk değerlendirmesi |
| `src/README.md` | Kurulum ve çalıştırma talimatı |
| `dependencies.repos` | Üçüncü parti pinler + neden yük taşıdıkları |
| `src/eland_sim/config/eland_params.yaml` | Bütün ayarlanabilir sayılar, yorumlu |

Kaynak dosyaların başlıkları (`mapping_node.py`, `emergency_landing_mode.hpp`,
`control_station.py`, `link_px4_assets.sh`) kendi kararlarının gerekçesini
taşıyor — bir davranış tuhaf geldiğinde önce oraya bak.

---

# 12. Dinamik engeller ve yörünge-farkında karar (2026-09-03)

Bu bölüm §1–11'in üstüne eklendi; öncesi olduğu gibi geçerli. Baseline etiketi
`v1.1-hud-baseline` (commit `2b741df`) — bir şey bozulursa dönülecek nokta
orası.

## 12.1 Ne eklendi

| Bileşen | Dosya | İş |
|---|---|---|
| Dünya üreteci | `eland_sim/scripts/gen_world.py` | Şablon + parametre → `eland_test.sdf`. Dinamik insan ve aracı parametrelerden yazar. |
| Dünya şablonu | `eland_sim/worlds/eland_test.sdf.in` | Statik sahne. Dinamik engeller burada **yok**; tek kaynaktan üretiliyor. |
| Engel sürücüsü | `eland_sim/eland_sim/obstacle_driver.py` | Engelleri gz `set_pose` ile sim saatinde hareket ettirir; `/eland/obstacle_truth` yayınlar (**yalnız ölçüm için**). |
| İzleyici | `eland_mapping/eland_mapping/tracker_node.py` | Dinamik sınıfları izler, doğrusal hız kestirir, `/eland/dynamic_obstacles` yayınlar. |
| Anlık harita | `mapping_node.py` (ek) | `/eland/ground_map_instant` — füzyondan **önceki** kare. |
| Dördüncü test | `detector_node.py` (ek) | `trajectory_clear` — aday ve yaklaşma rotası, tahmini engel koridoruna karşı. |
| Mesajlar | `eland_msgs/DynamicObstacle{,Array}.msg` | id, sınıf, konum, hız, güven, tahmin dizisi. |

Veri akışının değişen kısmı:

```
mapping_node ─┬─► /eland/ground_map            (füzyonlu, iniş kararı)
              └─► /eland/ground_map_instant    (ham kare, hareket için)
                        │
                        ▼
                  tracker_node ─► /eland/dynamic_obstacles
                        │
                        ▼
                  detector_node  (4. test: trajectory_clear)
```

## 12.2 SafeLand'den farkı — hangisi literatür, hangisi bizim

SafeLand (arXiv:2603.17430) dinamik engeli **anlık konumla** ele alıyor: engel
güvenlik yarıçapına girerse 5 s duraklat, hâlâ oradaysa arama irtifasına
tırmanıp başka noktaya reroute et. Tahmin yok.

Bu depoda:

- **Reaktif yarı korunuyor** — `HOLD` / `ABORT` durumları ve deneme bütçesi
  aynen duruyor, hiçbiri kaldırılmadı. Tahminin yanıldığı her durumda
  (dönen engel, hiç izlenmemiş engel) devreye giren bu.
- **Üstüne prediktif katman eklendi** — `trajectory_clear`, adayı ve rotayı
  engelin *gideceği* yere karşı önceden eliyor. Bu katman bizim katkımız.

Kod ve commit mesajlarında bu ayrım açıkça yazılı (`detector_node.py` başlığı).

## 12.3 Ölçümler

Hepsi bu makinede SITL'de, `real-time factor 1.00` altında ölçüldü.
Ham çıktılar `run_sim.sh` koşularından; senaryo parametreleri
`eland_params.yaml` → `obstacle_driver`.

### Ö1 — Segmentasyon dinamik nesnelerde bozulmuyor

90 s'lik uçuş, 20 m'de asılı, araç 3 m/s ile geçiyor, insan 1.2 m/s yürüyor:

| Ölçüm | Değer |
|---|---|
| `/eland/semantic_mask` | 278 kare, **3.11 Hz**, en uzun boşluk 0.43 s |
| `/eland/ground_map_instant` | 273 kare, 3.11 Hz, en uzun boşluk 1.99 s |
| Sınıf 8 (araç) tutarlılığı | **278/278 kare (%100)**, 1037 px ort., 221 px std |
| Sınıf 9 (insan) tutarlılığı | **278/278 kare (%100)**, 80 px ort., 5 px std |

Sınıf hiç kaybolmuyor ve hiç değişmiyor. **Dikkat:** bu ground-truth
segmentasyon; %100 tutarlılık simülatörün özelliği, öğrenilmiş bir modelin
değil. Faz 5'te gerçek model gelince bu ölçüm baştan yapılmalı — buradaki
sayılar o zaman "tavan" olarak kullanılabilir.

Piksel std'si araçta insanınkinin 44 katı: 1.5 m yüksekliğindeki bir gövde
nadir dışına çıktıkça düz zemin varsayımı altında yayılıyor. Aynı etki
aşağıdaki hız kestirimini de düşürüyor.

### Ö2 — Yörünge tahmini doğruluğu

Referans: `/eland/obstacle_truth` (komut edilen poz; sürücü engelleri
ışınlıyor, dolayısıyla referans kestirimden bağımsız).

| | insan (1.2 m/s) | araç (3.0 m/s) |
|---|---|---|
| İzlenme oranı | **272/272 (%100)** | 207/272 (%76) |
| Konum hatası (ort. / maks.) | **1.37 m** / 3.22 m | 1.86 m / 5.99 m |
| Güven ≥ 0.5 iken konum hatası | 1.37 m | 1.79 m |
| Kestirilen hız (güven ≥ 0.5) | 1.04 m/s | 2.04 m/s |

Tahmin hatası, ufka göre (güvenilir track'ler):

| ufuk | insan | araç |
|---|---|---|
| +2 s | 2.12 m | 3.40 m |
| +4 s | 3.75 m | 4.64 m |
| +6 s | 5.92 m | 7.38 m |
| +8 s | 8.07 m | 11.77 m |
| +10 s | 10.05 m | 16.87 m |

Üç şeyi açıkça söylemek gerekiyor:

1. **Hız sistematik olarak düşük çıkıyor** (%87 insanda, %68 araçta). İki
   sebep: (a) 8 örneklik (~2.6 s) pencere dönüş anlarını içine alınca eğim
   düşüyor, (b) araç haritadan çıkıp girdikçe track yeniden kuruluyor ve taze
   track'ler hız üretmiyor. Bu **güvensiz yönde** bir hata: koridor gerçekte
   olması gerekenden kısa çıkıyor. Telafisi §12.4'teki süpürülmüş güzergâh
   hafızası ve mevcut reaktif HOLD/ABORT.
2. **10 s ufkun ucu güvenilir değil** (araçta 17 m hata). Koridorun değeri
   yakın alanda (2–4 s, 3–5 m hata). Ufkun uzun tutulmasının sebebi
   §12.4'te — kısa ufuk ölçülerek yetersiz bulundu.
3. Araç %24 oranında hiç izlenmiyor: ±30 m'lik güzergâhının bir kısmı 40 m'lik
   haritanın dışında.

### Ö3 — Yanlış pozitif yok (çakışmayan senaryo)

Araç `y = +15` hattında, iniş alanına 15 m uzakta; insan `y = +8`'de. Filtre
**açık**:

```
SEARCH -> APPROACH: candidate #70 accepted, r=8.16 m
APPROACH -> VALIDATE: reached candidate, 0.12 m error
VALIDATE -> HOLD: candidate lost at 2.20 m, too low to re-acquire
HOLD -> VALIDATE: candidate recovered after 0.57 s hold
VALIDATE -> COMMIT: at 1.99 m, committing to touchdown
```

Temas noktası **(−0.09, −0.29)** — baseline'ın seçtiği yerin aynısı,
aktivasyondan temasa 17 s. Tek HOLD 2.2 m'de ve 0.57 s sürdü; bu, filtre
öncesinden beri var olan düşük irtifa davranışı, engelle ilgisi yok.
**Filtre, kesişme yokken iniş noktasını kaydırmıyor.**

### Ö4 — Kesişme senaryosu (filtre açık)

Araç `y = 0` hattında, yani iniş alanının tam içinden geçiyor. Mod, araç
**yaklaşırken** (x = −21.1 m, kapanıyor) tetiklendi:

```
SEARCH   -> APPROACH: candidate #68 accepted, r=8.00 m
APPROACH -> VALIDATE: reached candidate, 0.98 m error
VALIDATE -> SEARCH:   candidate lost at 19.02 m (attempt 1/3)
SEARCH   -> APPROACH: candidate #81 accepted, r=8.00 m
APPROACH -> VALIDATE: reached candidate, 0.21 m error
VALIDATE -> COMMIT:   at 1.99 m, committing to touchdown
```

| Ölçüm | Değer |
|---|---|
| Temas noktası | (1.26, −4.64) |
| **Araç hattına (y=0) uzaklık** | **4.64 m** |
| Aracın temas noktasına en yakın geçişi | 4.64 m |
| Aktivasyondan temasa | 22 s |

### Ö5 — Karşılaştırma: aynı senaryo, filtre kapalı

`trajectory_filter_enabled: false`, başka her şey aynı, mod yine araç
yaklaşırken tetiklendi (x = 27.9 m, kapanıyor):

```
SEARCH -> APPROACH: candidate #97 accepted, r=8.12 m
APPROACH -> VALIDATE: reached candidate, 0.17 m error
VALIDATE -> COMMIT: at 1.99 m, committing to touchdown
```

| | filtre **açık** | filtre **kapalı** |
|---|---|---|
| Temas noktası | (1.26, −4.64) | (−0.10, −0.35) |
| **Araç hattına uzaklık** | **4.64 m** | **0.35 m** |
| Aracın temas noktasına en yakın geçişi | 4.64 m | **0.35 m** |
| Durum geçişi sayısı | 6 (1 kayıp aday) | 4 |
| Aktivasyondan temasa | 22 s | 16 s |

Filtre kapalıyken araç, inmiş aracın **35 cm yanından** geçiyor. Açıkken
4.64 m. Eklenen katmanın fark yarattığının kanıtı bu satır; bedeli 6 saniye
ve bir fazladan aday değişimi.

## 12.4 Yol boyunca ölçülerek düzeltilen dört şey

Hepsi çalışır görünen bir sürümü ölçüp yanlış bulmakla ortaya çıktı.

1. **Füzyonlu harita hareket edeni göremez.** Kanıt hücre başına birikiyor ve
   `rate × tau`'ya oturuyor (3 Hz, τ=30 s → ~90). 1.5 s'de geçen bir araç ~5
   kanıt bırakıyor ve argmax'ı asla kazanamıyor. Ölçüm: gz'nin kendi
   segmentasyonunda iki araç lekesi (biri hareketli) görünürken
   `/eland/ground_map`'te yalnız park hâlindeki vardı, centroid 12 örnek
   boyunca 0.2 m içinde sabitti. Çözüm: füzyondan önceki kareyi ayrı topic'te
   yayınlamak (`/eland/ground_map_instant`). Haritanın hafızası
   **düşürülmedi** — §7/1'deki sebep hâlâ geçerli.
2. **4 saniyelik ufuk yetmiyor.** 3 m/s'de 12 m'lik bir yol parçasını koruyor,
   oysa korunması gereken iniş bunun kaç katı sürüyor. Ölçülen sonuç: araç
   haritanın dışındayken iniş noktasına karar verildi ve araç sonra tam o
   noktanın üstünden geçti — **en yakın yaklaşma 0.10 m**. Ufuk 10 s yapıldı.
3. **Belirsizlik yanlış eksende büyütülüyordu.** Ölçülen tahmin hatası
   (~0.9 m/s) neredeyse tamamen yol *boyunca*; koridor zaten aynı hat üzerinde
   örneklenmiş disklerin birleşimi olduğu için o hata hâlihazırda kapsanıyor.
   Her diski o kadar genişletmek hatayı iki kez sayıp haritanın yarısını
   eliyordu. Disk yarıçapı artık yalnız **yanal** hatayı taşıyor
   (`pred_sigma_cross_rate_mps: 0.25`).
4. **İleri koridor tek başına yetmiyor: geçen araç geri geliyor.** Filtre,
   araç yaklaşırken noktayı doğru şekilde reddetti, bekledi ve araç geçer
   geçmez tam oraya indi — hattan 0.37 m. Eklenen: **süpürülmüş güzergâh
   hafızası** (`corridor_memory_s: 25`). Hareket eden bir şey, kendisi
   hakkında olduğu kadar *zemin* hakkında da kanıttır: az önce buradan bir
   araç geçtiyse orası bir güzergâhtır ve oturulacak yer değildir.
   - Hafıza diskleri **yaklaşma rotası testine dahil değil**. İkisi birleşince
     ölçülen sonuç haritanın **%95'inin** kapanmasıydı; 15 m'den üstünden
     uçmak tehlike değil, üstüne oturmak tehlike.

Ayrıca: **filtre adayı zıplatıyor, mod bunu "aday kaybı" sayıyor.** Koridor
kayınca kazanan hücre 12 m öteye atlıyor, mod bunu kayıp sayıp deneme
bütçesini tüketiyor ve "no retries left, committing anyway" ile zaten
reddedilmiş yere iniyordu. Eklenen: seçim kararlılığı (`w_stickiness: 0.15`,
3 m yarıçap), uygunluk testlerinden **sonra** uygulanıyor — bir seçimi
uzatabilir, reddedilmiş bir hücreyi geri getiremez.

## 12.5 Ölçüm altyapısında bulunan iki tuzak

Bunlar koda değil, ölçüme ait; ama ölçüm yanlışsa kod da yanlış çıkar.

1. **WSL'de `/tmp` oturumlar arasında siliniyor.** Karşılaştırma koşuları için
   `/tmp` altına yazılan parametre dosyası, koşu başlarken yoktu; `ros2 launch`
   sessizce her node'u kendi kod içi varsayılanlarıyla başlattı. Sonuç: engeller
   parametre dosyasının söylediği yerde değildi ve birkaç koşu ölçtüğünü
   sandığı şeyi ölçmedi. İki düzeltme: `run_sim.sh --params` artık dosya yoksa
   **hata verip duruyor**, ve varyant dosyalar kalıcı bir dizine yazılıyor.
2. **Artık ROS node'ları bir sonraki koşuya sızıyor.** İkinci bir
   `obstacle_driver` aynı topic'e kendi truth'unu yayınlayıp aynı modelleri
   ışınlıyor; truth 5 saniyede iki farklı faz arasında zıplıyordu. Koşu
   script'leri artık başlarken pipeline node'larını tek tek öldürüyor.

## 12.6 Yeni ayar noktaları

`eland_params.yaml` içinde, hepsi yorumlu:

| Anahtar | Varsayılan | Ne yapar |
|---|---|---|
| `obstacle_driver.*` | — | Senaryo: iki engelin başlangıç/hedef/hızı, `person_kind` (`model`/`actor`) |
| `tracker_node.horizon_s` | 10.0 | Tahmin ufku |
| `tracker_node.track_timeout_s` | 6.0 | Haritadan çıkan engel ne kadar "yaşamaya" devam eder |
| `tracker_node.ignore_border_blobs` | true | Kenardan kırpılmış leke atılır (yoksa hız düşük kestiriliyor) |
| `detector_node.trajectory_filter_enabled` | true | **Karşılaştırma koşusu için kapatılır** |
| `detector_node.corridor_memory_s` | 25.0 | Süpürülmüş güzergâh hafızası |
| `detector_node.check_approach_path` | true | Yaklaşma rotası da test edilir |
| `detector_node.w_stickiness` | 0.15 | Seçim kararlılığı |

## 12.7 Bu işin bıraktığı açık kusurlar

| # | Konu | Durum |
|---|---|---|
| 9 | **Hız kestirimi %30'a varan oranda düşük** | Güvensiz yön: koridor kısa çıkıyor. Sebepleri Ö2'de. Çare adayları: dönüş anını tespit edip pencereyi kısaltmak, ya da lekenin parallaks kaymasını irtifa ile düzeltmek. |
| 10 | **10 s ufkun ucu güvenilmez** (araçta 17 m) | Sabit hızlı doğrusal model. Koridorun asıl değeri 2–4 s'de. |
| 11 | **Ping-pong engel gerçekçi değil** | Test tekrarlanabilirliği için seçildi; gerçek trafik geri gelmez. Hafıza süresi (25 s) bu senaryoya göre ayarlandı, gerçek bir sahnede yeniden bakılmalı. |
| 12 | **Actor kullanılmıyor** | `person_kind: actor` çalışıyor ve etiketleniyor, ama Gazebo actor pozunu yayınlamıyor ve istenen hızda yürütmüyor (33.3 s'lik tur ~28 s sürdü), yani ölçüm için referans yok. Varsayılan `model`. |
| 13 | **Hafıza + yaklaşma rotası birleşimi denenmedi** | Kasten ayrıldı (%95 kapanma). Zaman-uzay muhakemesi yapan bir sürüm bunu güvenli şekilde birleştirebilir. |

## 12.8 Bu işten sonra sıradakiler

1. **Hız kestirimindeki sistematik düşüklüğü kapat** (kusur 9). Güvenlikle
   doğrudan ilgili tek açık madde bu.
2. **Zaman-uzay çakışma testi.** Şu anki test "rota koridoru kesiyor mu" diye
   soruyor, "aynı anda mı orada olacağız" diye değil. Aracın kendi iniş süresi
   zaten biliniyor (alçalma yasası), yani bu hesaplanabilir.
3. **Hareketli engelli senaryoyu HUD'a yansıt.** İzlenen engeller ve koridor
   şu an yalnız logda; HUD'da çizilirse davranış anlaşılır hâle gelir.
4. §9'daki eski liste hâlâ geçerli (QGC doğrulaması, operatör kaçış yolu,
   Faz 5 gerçek segmentasyon).

## 12.9 Yeni komutlar

```bash
python3 ~/ros2_ws/src/eland_sim/scripts/gen_world.py
```

```bash
~/ros2_ws/src/eland_sim/scripts/run_sim.sh --headless --takeoff 20
```

```bash
ros2 topic echo /eland/dynamic_obstacles
```

Filtreyi kapatıp karşılaştırma koşusu yapmak için parametre dosyasının bir
kopyasında `trajectory_filter_enabled: false` yapıp:

```bash
~/ros2_ws/src/eland_sim/scripts/run_sim.sh --headless --takeoff 20 --params /kalici/yol/params_off.yaml
```

---

# 13. Teleoperasyon: kendi kendine iniş ve devralmanın geri alınması (2026-09-04)

Kullanıcı üç şikâyet bildirdi: HUD açıkken hiçbir tuşa basmadan araç iniyor,
manuel kontrol geri alınsa bile iniş durmuyor, ve teleoperasyon genel olarak
tutarsız. Üçü de **aynı tek sebebe** çıktı.

## 13.1 Kök neden

PX4'ün kabul ettiği manuel kontrol akışı **kesintili**. İstasyon sabit 20 Hz
`ManualControlSetpoint` yayınlarken, PX4'ün geri yayınladığı (yani fiilen
kullandığı) hız ölçüldü:

```
we send 20 Hz  ->  px4 manual echo: 0.0, 14.7, 0.0, 0.3, 20.0, 27.0, 1.0, 31.7 Hz
```

20 Hz'in üstündeki değerler mesajların **öbekler hâlinde** geldiğini gösteriyor:
saniyelerce boşluk, sonra biriken mesajlar birden. Her boşluk
`COM_RC_LOSS_T`'yi (varsayılan **0.5 s**) aşıyor, PX4 kumandayı kayıp sayıyor,
`NAV_RCL_ACT` varsayılanı **Return**, ve acil iniş modu Return'ün yerine kayıtlı
olduğu için her kayıp bildirimi bir acil inişe dönüşüyor.

Ölçülen zincir (`failsafe_flags` topic'inden, düzeltmeden önce):

```
[47.5] stick akışı başlatıldı
[47.8] manual_control_signal_lost temizlendi
[50.0] POSCTL istendi -> nav=POSCTL, took_over=True     (devralma başarılı)
[52.1] manual_control_signal_lost YİNE true             (akış hâlâ 20 Hz!)
[52.2] failsafe=True, nav=AUTO_LOITER (5 s Hold)
[54.0] nav=EMERGENCY_LANDING                            (mod aracı geri aldı)
```

Yani: devralma **çalışıyordu**, dört saniye sonra failsafe geri alıyordu.
Kullanıcının "manuel moda geçmiyor" dediği şey buydu. Gazebo penceresi açıkken
makine daha da yüklendiği için boşluklar büyüyor — şikâyetin GUI'li koşuda
belirginleşmesinin sebebi bu.

**Ayrıca doğrulandı:** GCS kalp atışı mekanizması sağlam. Gerçek istasyon
açıkken 100 saniye boyunca `gcs_lost=False`, hiç failsafe yok. Sorun kalp
atışında değildi.

İkinci, bağımsız bulgu: **stick akışı canlı değilken POSCTL isteği reddediliyor.**

```
akış yokken  POSCTL istendi -> 4 s sonra hâlâ EMERGENCY_LANDING  (REFUSED)
akış varken  POSCTL istendi -> anında nav=POSCTL                 (WORKED)
```

İstasyon zaten önce akışı başlatıp 2 s sonra istiyor, yani bu yol doğruydu; ama
elle `ros2 topic pub` ile mod değiştirmeye çalışan biri bunu bilmeden reddedilir.

## 13.2 Yapılan düzeltmeler

| Nerede | Ne | Gerekçe |
|---|---|---|
| `run_sim.sh` | `NAV_RCL_ACT=1` (Hold) | Operatör bağlantısındaki boşluk aracı **park etmeli**, indirmemeli. GCS kopması senaryosu etkilenmiyor: o `NAV_DLL_ACT` üzerinden gider ve Return'de bırakıldı. |
| `run_sim.sh` | `COM_RC_LOSS_T=3` | 0.5 s gerçek bir vericinin sayısı; buradaki bağlantı, yazılımsal render ile CPU paylaşan bir DDS köprüsü. Ölçülen öbeklenmeyi karşılıyor. |
| `control_station` | Manuel akış 20 → 33 Hz | Boşlukları kapatmıyor ama her öbeğe daha çok mesaj koyuyor. Asıl düzeltme yukarıdaki timeout. |
| `control_station` | Operatör niyeti korunuyor | Failsafe aracı geri alırsa istasyon POSCTL'i tekrar istiyor ve **sebebini yazıyor**. `0` veya `L` niyeti temizliyor. |
| `control_station` | Failsafe sebebi ekranda | `failsafe_flags` okunuyor; "kumanda baglantisi kopuk sayiliyor" gibi bir satır çıkıyor. Operatör aracın kendisini yok saymadığını görüyor. |
| `detector_node` | Nokta kilidi (`latch_site`) | Aday zıplaması azaldı; ayrıntı §13.4. |

Bunlar **simülasyon ergonomisi**. Gerçek donanımda gerçek bir verici ile PX4
varsayılanları doğru sayılardır; `run_sim.sh`'deki iki satır oraya kopyalanmaz —
bu, kodda da yazılı.

## 13.3 Düzeltme sonrası ölçüm

Aynı deney, aynı script, düzeltmelerden sonra:

```
[50.1] POSCTL istendi -> nav=POSCTL, took_over=True
[53.6] flags: manual_control_signal_lost YOK
[53.8] nav=POSCTL, failsafe=False
[78.5] 25 saniye sonra: nav=POSCTL          <-- araç operatörde kaldı
```

Öncesinde aynı noktada araç 4 saniye içinde acil inişe dönüyordu. **25 saniye
boyunca hiç failsafe yok.**

## 13.4 "Karar vermesi uzun sürüyor" — değerlendirme ve düzeltme

Kullanıcının önerisi: *HUD'daki dış çember ile dinamik nesnenin çemberi
birbirinden uzak olduğu sürece tahmin yapıp inebilmeli.*

**Değerlendirme: gözlem doğru, ama sebep eksik bir kural değil.** Ayrılık testi
zaten var — `trajectory_clear` tam olarak bunu yapıyor, aday hücre koridor
disklerinin dışında olmak zorunda. Gecikme, kuralın yokluğundan değil,
**kararın her karede yeniden verilmesinden** geliyordu: koridor süpürüldükçe
kazanan hücre 12 m öteye atlıyor, uçuş modu bu atlamayı "aday kaybı" sayıyor,
üç kayıp deneme bütçesini bitiriyor ve `no retries left, committing anyway`
ile araç zaten reddedilmiş yere iniyordu.

Uygulanan: **nokta kilidi.** Seçilen nokta, bütün testleri geçmeye devam ettiği
sürece korunuyor; uygunluk testleri önce çalıştığı için kilit bir kararı
uzatabilir ama koridorun kapattığı bir noktayı yaşatamaz. Kilit yalnızca başka
bir nokta `latch_release_margin` (0.20) kadar daha iyi olduğunda bırakılıyor.

| | kilitten önce | kilitten sonra |
|---|---|---|
| Aday kaybı (bir iniş boyunca) | 3 | **1** |
| Sonuç | `committing anyway` | normal COMMIT, 1.99 m'de |
| Araç hattına uzaklık | 0.06–0.19 m | **4.73 m** |

Yani kullanıcının istediği sonuç (beklemeden, ayrılığa bakarak inme) kilitle
geldi; ayrılık testi zaten yerindeydi.

## 13.5 Bu bölümün bıraktığı açık maddeler

| # | Konu | Durum |
|---|---|---|
| 14 | **Manuel akıştaki öbeklenmenin kendisi giderilmedi** | Semptom `COM_RC_LOSS_T` ile karşılandı, kaynağı (uXRCE-DDS köprüsü mü, ROS zamanlayıcı mı, CPU doygunluğu mu) izole edilmedi. Gerçek donanımda aynı toleransla uçmak **doğru olmaz**. |
| 15 | **GUI'li koşu ölçülmedi** | Bütün ölçümler `--headless`. Kullanıcının şikâyeti Gazebo penceresi açıkken çıktı; düzeltmeler orada da işe yaramalı ama bu doğrulanmadı. |
| 16 | **Operatör kaçış yolu hâlâ yok** | §8/2 duruyor: mod kayıtlıyken kasıtlı bir RTL de acil inişe dönüyor. İstasyonun ısrarlı POSCTL isteği bunu maskeliyor, çözmüyor. |
