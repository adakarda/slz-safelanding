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

---

# 14. Rastgele başlangıç konumu (2026-09-04)

**Sorun:** doğuş noktası sabitti (orijin), yani her koşu aynı yirmi metrelik
çimi test ediyordu. Bir iniş algoritması hep aynı mahalleyi görüyorsa yalnız
o mahalleye karşı sınanmış olur.

**Yapılan:** `scripts/pick_spawn.py` üretilen dünyayı okuyup engellerden ve
hareketli engel güzergâhlarından uzak bir poz seçiyor; `run_sim.sh` varsayılan
olarak bunu kullanıyor.

- Engel sayılan şey: yüksekliği ≥ 0.5 m olan modeller. Yol, çakıl, toprak ve
  gölet 2 cm'lik kutular — zemine sürülmüş boya; sınıfları iniş kararı için
  önemli, doğuş noktası için değil.
- Dinamik engellerin güzergâhı da (doğru parçası olarak) dışlanıyor.
- `--seed N` ile tekrarlanabilir; seçilen poz ve seed hem ekrana hem
  `/tmp/eland_logs/spawn.txt`'e yazılıyor.
- `--fixed` (veya `--scenario` / `--pose`) eski sabit davranışı geri veriyor.

**Ölçüm — 200 örnek, varsayılan sınırlar (±25 m):**

| | öncesi | sonrası |
|---|---|---|
| Farklı doğuş noktası | 1 | **200/200** |
| x yayılımı | — | −24.4 … 24.9 m (std 16.4) |
| y yayılımı | — | −24.9 … 24.6 m (std 17.3) |
| En yakın engele boşluk | — | min **6.04 m**, ort. 8.79 m |
| Engel güzergâhına boşluk | — | min **8.23 m**, ort. 16.16 m |
| Başarısız seçim | — | 0 |

Uçtan uca doğrulama: `--seed 12345` ile seçilen poz `-4.17,-24.49,0,0,0,2.0433`;
Gazebo aynı koşuda aracı `x=-4.170, y=-24.490` konumunda gösterdi. Aynı seed
iki kez çalıştırıldığında aynı poz çıktı.

**Not:** ölçüm ve regresyon script'lerinin `--fixed` kullanması gerekiyor;
aksi hâlde karşılaştırma koşuları farklı yerlerden başlar ve sayılar
kıyaslanamaz hâle gelir.

---

# 15. Daha fazla sınıf, daha fazla engel (2026-09-04)

**İstenen:** dünyada daha fazla sınıf ve engel; dinamik taraf tek insan/tek
araçla sınırlı kalmasın; sınıf şeması tek kaynaktan türesin; hızın ne kadar
etkilendiği ölçülsün.

## 15.1 Yeni sınıflar

`eland_common/classes.py`'ye üç sınıf eklendi — şema **eklemeli**, mevcut
ID'ler değişmedi. Maske piksel değeri olarak bu ID'leri taşıyor ve harita
dizileri onlarla indeksleniyor; var olan bir sınıfı yeniden numaralamak eski
her kaydı sessizce başka bir şeye çevirirdi.

| ID | Sınıf | Risk | Rol |
|---|---|---|---|
| 10 | `FENCE` | 1.0 | Tehlike (SORA ayrımı ister). 12 cm kalınlık = harita çözünürlüğünde ~1 hücre |
| 11 | `POLE` | 1.0 | Tehlike. 32 cm çap = ~2 hücre |
| 12 | `SAND` | 0.15 | **İnilebilir**, çakıldan yumuşak |

`NUM_CLASSES` 10 → 13; `CLASS_NAMES`, `DEFAULT_CLASS_RISK`, `CLASS_COLORS`,
`DEFAULT_SAFE_CLASSES`, `DEFAULT_HAZARD_CLASSES` hepsi aynı dosyada güncellendi
ve mapping / detector / HUD bunları oradan türetiyor — hiçbir yere ikinci bir
liste yazılmadı.

İnce yapılar kasten seçildi: mesafe dönüşümü engelin **büyüklüğünü** değil,
uzaklığını umursar. Bir çitin bir binadan daha az saygı görmemesi gerekir.

## 15.2 Yeni statik engeller

Üç çit hattı, üç direk, bir kum yaması, üç ağaçlık bir koru, ve alçak-uzun bir
depo binası. Dünya 24 → **37 model**. Yerleşim haritanın ortasını kasten açık
bırakıyor: amaç seçimi zorlaştırmak, inişi imkânsızlaştırmak değil.

## 15.3 Çoklu dinamik engel

Sayılar parametre: `person_count` (3), `vehicle_count` (2),
`person_spacing_m`, `vehicle_spacing_m`.

Kural: engel 0 parametredeki güzergâhı aynen kullanır; sonrakiler o hattın
**yanına** kaydırılır (1, −1, 2, −2 … sırasıyla, grup hattın üstünde merkezli
kalsın diye) ve her biri kendi güzergâhında **faz kaydırmalı** ilerler. Üç araç
20 saniyelik bir bacakta yaklaşık yedi saniye arayla geçer — konvoy değil,
trafik.

`gen_world.py` modelleri `dyn_person_0..2`, `dyn_vehicle_0..1` olarak üretiyor;
`obstacle_driver` hepsini sürüyor. Truth topic'i artık **önce araçlar, sonra
insanlar** sırasıyla hepsini yayınlıyor — sıra sözleşme, çünkü `PoseArray`'de
isim yok.

## 15.4 Ölçüm

20 m'de asılı, sabit doğuş (`--fixed`), 90 s:

| | öncesi (8 sınıf, 1+1 engel) | sonrası (11 sınıf, 3+2 engel) |
|---|---|---|
| `/eland/semantic_mask` | 3.11 Hz | **3.19 Hz** |
| En uzun kare boşluğu | 0.43 s | 0.71 s |
| Tek karede görülen sınıf | 8 | **11** |
| İnsan izleme | 272/272, hata 1.37 m | **150/150, hata 1.32 m** |
| Araç izleme | 207/272, hata 1.86 m | 114/150, hata **2.16 m** |

Maskede tek karede görülenler (ortalama piksel):

```
grass 55696 · pavement 10831 · vegetation 4149 · sand 2742 · fence 1484
vehicle 1370 · person 165 · dirt 195 · building 85 · pole 65 · gravel 26
```

**Hız etkilenmedi.** 3.07–3.19 Hz aralığı koşular arası gürültü; sınıf ve
engel sayısını artırmak segmentasyonu yavaşlatmıyor — render maliyeti piksel
sayısında, model sayısında değil.

**Bedeli olan yer izleme:** araç konum hatası 1.86 → 2.16 m ve izlenme oranı
%76 → %76 (114/150). İki araç aynı sınıftan iki leke demek; en yakın komşu
eşlemesi ikisini karıştırabiliyor. Bu, çoklu engelin gerçek maliyeti ve
açık madde olarak duruyor.

**Yeni sınıflar görülüyor:** fence 1484 px ve pole 65 px ile her karede
mevcut — 32 cm'lik bir direk 25 m'den görülüyor.

---

# 16. Teleoperasyon: kök neden, ve önceki teşhisin düzeltilmesi (2026-09-04)

**İstenen:** semptomu bastırmak değil, öbeklenmenin kaynağını izole etmek;
sonra gerçek düzeltme; ayrıca operatör kaçış yolu (§13.5/16).

## 16.1 Zincir üç noktadan ölçüldü

Manuel komutun geçtiği her aşamaya ayrı sayaç kondu:

| Nokta | Ne ölçer |
|---|---|
| **P1** yayıncı zamanlayıcısı | Süreç gerçekte ne zaman gönderebildi |
| **P2** `/fmu/in/manual_control_input` aboneliği | ROS 2 / DDS teslimi |
| **P3** `/fmu/out/manual_control_setpoint` | uXRCE-DDS ajanı + PX4 |

Sonuç (60 s, sabit 20 Hz yayın):

```
P1 yayıncı  : 19.85 Hz, aralık p50 50.0 ms, p99  53.7 ms, en uzun  352.9 ms
P2 ROS/DDS  : 19.83 Hz, aralık p50 50.0 ms, p99  53.5 ms, en uzun  686.5 ms
P3 PX4 echo : 20.04 Hz, aralık p50 50.0 ms, p99  83.5 ms, en uzun  686.3 ms
```

Üç noktada da 60 saniyede **tek** bir >0.5 s boşluk. Yani öbeklenme
taşımada yok.

## 16.2 Önceki teşhis yanlıştı — düzeltme

§13.1'de "PX4'ün kullandığı hız 0–31 Hz arasında salınıyor" diye rapor
edilmişti. O sayı, ölçen node'un **kendi** tek-thread'li executor'ında
yayınlama, abone olma, bayrak işleme ve `print` yapmasıyla üretilmişti:
executor takıldığında hem yayın duruyor hem de geri sayım 3 saniyelik
pencerede önce 0 sonra 31 gösteriyordu. PX4 kumandayı haklı olarak kayıp
saydı — çünkü akış gerçekten durmuştu, ama **tanı aracında**, taşımada değil.

Doğru ifade: *manuel kontrolü meşgul bir tek-thread executor'dan yayınlayan
her node bu failsafe'i tetikler.* Kontrol istasyonu bunu zaten tasarımıyla
önlüyordu (arka plan executor + ayrı zamanlayıcı); artık **kanıtlıyor** da.

## 16.3 Gerçek istasyon ölçüldü

İstasyon kendi yayın düzenliliğini 10 saniyede bir raporluyor
(`stream_report_s`). Ortalama değil **en uzun boşluk** raporlanıyor, çünkü
failsafe'i tetikleyen odur.

| Koşul | İstasyon akışı | PX4 echo | PX4 "kumanda kayıp" | nav_state |
|---|---|---|---|---|
| Yüksüz | 33.1 Hz, en uzun **36 ms** | max 280 ms, >0.5 s: 0 | **0 kez** | — |
| 8 CPU yükü (yük ort. 16) | 33.1 Hz, en uzun **54 ms** | max 234 ms, >0.5 s: 0 | **0 kez** | — |
| 8 CPU yükü + **varsayılan 0.5 s eşik** | 33.0 Hz, en uzun **60.6 ms** | max 253 ms, >0.5 s: 0 | **0 kez** | 60 s boyunca POSCTL |

Son satır asıl olan: `COM_RC_LOSS_T` PX4 varsayılanında (0.5 s), makine 12
çekirdekte 18 yük ortalamasıyla boğulmuşken bile araç bir kez bile operatörün
elinden çıkmadı.

## 16.4 Yapılan düzeltmeler

| Değişiklik | Gerekçe |
|---|---|
| **`COM_RC_LOSS_T` geri alındı** (varsayılan 0.5 s) | 3 s'ye çıkarılması yanlış ölçüme dayanan bir workaround'du. Kök neden anlaşıldığına göre tolerans gevşetmesi kalkmalı. |
| `NAV_RCL_ACT=1` (Hold) **kaldı** | Bu bir politika: operatör bağlantısındaki boşluk aracı park etmeli, indirmemeli. Workaround değil. `NAV_DLL_ACT` Return'de kaldığı için bağlantı-kopması senaryosu aynen çalışıyor. |
| İstasyon kendi akışını raporluyor | Bir daha bu tür bir sorun tahminle değil, ölçümle teşhis edilsin: "en uzun boşluk 36 ms" diyen bir node, kendisinin aç bırakılmadığını kanıtlar. |
| İstasyon `window: false` ile penceresiz çalışabiliyor | Ekransız ölçüm ve ssh üzerinden kullanım. Klavye gider, akış/heartbeat/niyet korunması kalır. |

## 16.5 Operatör kaçış yolu (açık madde #16 kapandı)

Mod, Return'ün yerine kayıtlı olduğu sürece kasıtlı bir RTL de acil inişe
dönüyordu ve bu **çalışma anında değiştirilemez** — hangi iç modun yerine
geçildiği kayıt sırasında PX4'e söylenir.

Değiştirilebilen şey, kayıtlı olup olmadığı. `/eland/mode_enable` üzerine
`false` yayınlamak modu kayıttan düşürüyor ve süreç çıkıyor; PX4 kendi
Return'üne dönüyor. Bu yeni bir mekanizma değil: Faz 3'te node öldürüldüğünde
`nav_state 23 → 5 (AUTO_RTL)` olarak zaten ölçülmüştü. Yapılan, o hazır düşüş
yolunu **kasıtlı ve erişilebilir** kılmak.

Kontrol istasyonunda `9` tuşu. Tek yönlü: uçuş ortasında modun geri gelmesi,
az önce gitmesini isteyen operatörün altında bir modun belirmesi demek olurdu;
geri getirmek yeniden başlatmaktır.

Doğrulandı: `9`'a eşdeğer yayın sonrası mod
`mode_enable(false): unregistering...` yazdı ve süreç sayısı 0'a düştü.

## 16.6 Hâlâ açık

| # | Konu |
|---|---|
| 15 | **GUI'li koşu benim tarafımdan doğrulanmadı.** Otomasyon bağlamımda X sunucusuna erişemiyorum (`qt.qpa.xcb: could not connect to display :0`), bu yüzden Gazebo penceresi + istasyon penceresi açıkken ölçemedim. Yerine mekanizmayı sınadım: 8 çekirdek yükü altında akış bozulmadı. GUI'nin ek yükü CPU değil bellek bant genişliği ise bu sınama onu kapsamaz. |
| 17 | Kaçış yolu tek yönlü; uçuş ortasında modu geri getirmek yok (kasıtlı). |

---

# 17. Sınırlı sayıda, rastgele konumlu çoklu mob (2026-09-05)

**İstenen:** aynı anda daha fazla hareketli varlık, ama üst sınırlı; her
mob'un güzergâhı da rastgele ve çakışmasız; her koşu gerçekten farklı bir
senaryo.

## 17.1 Tek çekiliş, tek kayıt

Rotalar `gen_world.py` tarafından çiziliyor ve `worlds/mob_layout.yaml`'a
yazılıyor. Hem dünya modelleri hem `obstacle_driver` **o dosyayı** okuyor.

Alternatif (ikisinin de aynı seed'den aynı düzeni yeniden türetmesi) reddedildi:
iki program aynı hesabı iki kere yaparsa er geç ayrışır ve ayrışma sessiz olur —
modeller bir yerde durur, pozlar başka yere komut edilir.

Katman kurulu paylaşım dizinine de kopyalanıyor; yoksa yeni çekiliş modelleri
taşırken sürücü son `colcon build` anındaki konumlara komut etmeye devam ederdi.

## 17.2 Sıra değişti: önce doğuş, sonra dünya

Mob rotaları **aracın doğduğu noktanın çevresinden** geçirilmek zorunda, yoksa
trafik aracın hiç bakmadığı yerde olur. Bu yüzden `run_sim.sh` artık önce
doğuş noktasını seçiyor (şablondaki statik engellere karşı), sonra dünyayı o
noktaya odaklı üretiyor.

Ölçülen gerekçe: ilk sürüm rotaları dünyaya rastgele saçtı; 5 mob çizildi,
sürücü hepsini sürdü, ve **izleyici bütün uçuş boyunca 0 hareketli gördü.**

## 17.3 Yol boyunca düzeltilen üç şey

1. **Engeller disk değil kapsül.** 12 m'lik bir çit, sınırlayıcı kutusunun
   yarı-köşegeniyle 6 m yarıçaplı bir disk oluyordu; 4 m boşluk istenince
   rota, bir metre yanından geçebileceği çitten 10 m uzak durmak zorunda
   kalıyordu. Ölçülen bedel: **300 aday rotanın 300'ü de reddedildi.** Artık
   her engel bir eksen + yarıçap (kapsül); direk ve ağaç sıfır uzunlukta,
   yani disk.
2. **Bir mob yerleşemeyince kalanlar atlanıyordu.** `break` yerine `continue`:
   erken bir başarısızlık koşuyu "tek araç, hiç insan" hâline getiriyordu ki bu
   "daha az mob" değil, başka bir senaryo.
3. **Rotalar kesişebilmeli.** "Her yerde 6 m uzak" kuralı, hepsi aynı 18 m'lik
   diskten geçmek zorunda olunca ikinci mob'u imkânsız kılıyordu. Kural artık
   yalnızca **aracın yanından geçtikleri noktalar** arasında; trafik kesişir,
   ama iki mob aynı hattı kullanmaz.

## 17.4 Ölçüm

100 çekiliş, `max_mobs: 6`, istenen 3 insan + 2 araç:

| | öncesi (sabit düzen) | sonrası (rastgele) |
|---|---|---|
| Mob sayısı | 5, hep aynı yerde | **5** (min 5, max 5) |
| Farklı başlangıç noktası | 5 | **498/500** |
| Rota–engel boşluğu | — | min **2.50 m**, ort. 4.79 m |
| Rota–araç mesafesi | — | min **8.05 m**, max **17.99 m** |
| 0 mob çıkan koşu | — | 0/240 (dört farklı odak noktasında) |

Odak noktasına göre yerleştirme başarısı (60 çekiliş, her odak için):

| Odak | ortalama mob |
|---|---|
| (0, 0) — dünyanın kalabalık ortası | 4.92 |
| (5, −8) | 5.00 |
| (−15, 10) | 5.00 |
| (20, −20) | 5.00 |

Canlı doğrulama (`--fixed`, 25 m'de asılı): 5 mob çizildi, sürücü beşini de
katmandaki bacaklarla yükledi (faz 0.00/0.20/0.40/0.60/0.80), truth topic'i 5
poz yayınladı, ve **izleyici aynı anda 6 hareketli gördü** (beş gerçek + bir
yanlış eşleme).

## 17.5 Açık

| # | Konu |
|---|---|
| 18 | Mob sayısı kalabalık bölgelerde düşebiliyor (odak (0,0)'da 4.92). Rotalar düz çizgi; gerçek trafik engellerin etrafından dolaşır. |
| 19 | İzleyici 5 gerçek mob'a karşı 6 track gösterdi — aynı sınıftan komşu lekelerin eşleme gürültüsü, açık madde #9 ile aynı kök. |

---

# 18. SORA taksonomisi: sim ile modelin aynı sınıf uzayı (2026-09-05)

**İstenen:** simülasyon dünyasının sınıf şeması, gerçek segmentasyon modelinin
eğitildiği 7 sınıflık SORA şemasıyla birebir aynı olsun; risk skoru da o
tablodaki ağırlık sütunundan üretilsin.

## 18.1 Taksonomi birebir alındı

`eland_common/classes.py` artık modelin kendi indekslerini, kendi sırasıyla
taşıyor:

| idx | sınıf | Gazebo'da hangi nesneler |
|---|---|---|
| 0 | `safe-soft` | çim, toprak, kum |
| 1 | `safe-hard` | çakıl, asfalt |
| 2 | `terrain-hazard` | ağaçlar, çalı |
| 3 | `structure` | binalar, çitler, direkler |
| 4 | `water` | göletler |
| 5 | `vehicle-animal` | araçlar |
| 6 | `person` | insanlar |
| 7 | `unknown` | **modelde yok**, boru hattına ait |

Sim'in ürettiği ground-truth ile modelin çıktısı artık aynı uzayda: çeviri
tablosu olmadan piksel piksel karşılaştırılabilir.

**Vegetation → terrain-hazard** (safe-soft değil). Yukarıdan bakınca bir
"vegetation" pikseli bir tepe örtüsüdür ve örtünün altındaki zemin hiç
gözlenmemiştir; araç görmediği bir zemine kendini bağlamış olur. 25 m'den bir
çalı da bir çim de yeşildir, ama yalnızca birine inilebilir — taksonomide tam
olarak bu ayrım için bir sınıf var.

## 18.2 Etiket kaydırması: neden dünyada `indeks + 1` yazılı

Gazebo etiketsiz her şeye **0** döndürüyor ve taksonomide 0 = `safe-soft`.
Doğrudan indeks yazılsaydı gökyüzü, etiketsiz bir model ve her etiketleme
hatası dünyanın en güvenli zemini olarak okunurdu.

Bu yüzden dünya `indeks + 1` yazıyor, `perception_node` bir çıkarıyor ve
Gazebo'nun 0'ı **UNKNOWN(7)** oluyor — inilemez, yani hata güvenli yöne
düşüyor. Kaydırma tam iki yerde: etiketleri yazan üreteç/şablon ve okuyan
node.

## 18.3 Ağırlık sütunu risk değil — ölçülerek gösterildi

Tez tablosundaki ağırlıkların **ters-frekans eğitim ağırlıkları** olduğu
aritmetikle doğrulandı:

```
ağırlık = 0.35 · sqrt(46.167 / piksel%)
```

| sınıf | piksel % | tablodaki ağırlık | formül |
|---|---|---|---|
| safe-soft | 15.558 | 0.61 | 0.60 |
| safe-hard | 46.167 | 0.35 | 0.35 |
| terrain-hazard | 5.705 | 1.00 | 1.00 |
| structure | 29.411 | 0.44 | 0.44 |
| water | 1.047 | 2.33 | 2.32 |
| vehicle-animal | 1.738 | 1.81 | 1.80 |
| person | 0.374 | 3.91 | 3.89 |

Yedisi de iki ondalıkta tutuyor. Bunlar risk olsaydı `structure` (0.44)
`safe-soft`'tan (0.61) **daha güvenli** sayılırdı — yani bir binaya inmek çime
inmekten iyi, çünkü veri setinde bina çok, çim az. Bu, sınıf dengeleme
ağırlığının tanımıdır, risk sıralaması değil.

**Yapılan:** ağırlıklar `classes.py`'de `TRAIN_WEIGHTS` olarak aynen duruyor
(eğitim tarafı için, tek kopya), risk ise SORA sıralamasından geliyor:

| sınıf | risk | gerekçe |
|---|---|---|
| safe-soft | 0.0 | |
| safe-hard | 0.2 | inilebilir ama gövdeye sert, ve altyapının/trafiğin olduğu yer |
| terrain-hazard | 0.7 | örtünün altı görülmemiş |
| structure / water / vehicle-animal / person | 1.0 | SORA izin vermiyor |
| unknown | 1.0 | değerlendirilmemiş piksel, temizlenmiş değildir |

## 18.4 Su sınıfı artık gerçekten görülüyor (madde 5)

Ölçüm: taksonomi geçişinden hemen sonraki 90 s'lik uçuşta altı sınıf 271/271
karede vardı, **water hiçbirinde yoktu** — tek gölet (−34, −4)'te ve çoğu
doğuş noktasından kamera ayak izinin dışında. Dünyanın hiç göstermediği bir
SORA sınıfı, boru hattının hiç sınanmadığı bir sınıftır.

İkinci ve küçük bir gölet (−17, −7) eklendi. Sonuç:

| sınıf | 271 karede görülme | ortalama piksel |
|---|---|---|
| safe-soft | **271/271** | 56314 |
| safe-hard | **271/271** | 10907 |
| terrain-hazard | **271/271** | 4159 |
| structure | **271/271** | 1598 |
| water | **271/271** | **2321** |
| vehicle-animal | **271/271** | 1338 |
| person | **271/271** | 164 |

Yedi SORA sınıfının **hepsi** tek karede temsil ediliyor.

## 18.5 Ölçüm: taksonomi neyi değiştirdi

Sabitlenmiş senaryo (`--fixed` + `randomize_mobs: false`), 90 s:

| | 13 sınıflık şema | 7 sınıflık SORA şeması |
|---|---|---|
| Maske hızı | 3.19 Hz | **3.02 Hz** |
| Tek karede sınıf | 11 | **7/7** (tamamı) |
| İnsan izleme | 150/150, hata 1.32 m | 136/136, hata **1.40 m** |
| Araç izleme | 114/150, hata 2.16 m | 97/136, hata **2.14 m** |
| Araç truth hızı (duvar saati) | — | 2.92 m/s (yapılandırılan 3.0) |

İzleme performansı değişmedi; sınıfların birleştirilmesi lekeleri ne
iyileştirdi ne bozdu. Hız farkı koşular arası gürültü.

## 18.6 Yol boyunca bulunan bir tutarsızlık

Sabit düzen dalı mob'ları **insanlar önce** yazıyordu, oysa hem rastgele dal
hem truth topic'inin sözleşmesi "önce araçlar" diyor. Sonuç: indeks 0 bir
insan oluyordu ve araç ölçümü, bir aracın tahminini bir insanın truth'una
karşı karşılaştırıp **"araç hiç izlenmedi"** diye raporluyordu. Araç gayet iyi
izleniyordu.

Bu, katman dosyasının önlemek için var olduğu sessiz tutarsızlığın ta
kendisi — ama sıra sözleşmesi dosyada değil kodda olduğu için oradan sızdı.
Düzeltildi; her iki dal da aynı sırayı yazıyor.

## 18.7 Açık

| # | Konu |
|---|---|
| 20 | Eski 13 sınıflık ölçümler (§15, §12) artık başka bir şema ile alınmış; sayılar tarihsel, doğrudan kıyaslanamaz. |
| 21 | `TRAIN_WEIGHTS` boru hattında kullanılmıyor. Eğitim tarafı bunu okumaya başlarsa iki kopya olmasın diye buraya kondu, ama şu an tek yönlü bir kayıt. |

# 19. Karar döngüsü: profil, darboğaz ve çıkan asıl kusur (madde 8)

Şikâyet "iniş yeri seçimi uzun sürüyor" idi. Öneri, dinamik nesnenin kabuğu
uzaktayken tahmin yapıp inebilmekti. Ölçmeden hangi katmanın yavaşlattığı
bilinmediği için önce her aşama ayrı ayrı zamanlandı.

## 19.1 Kare maliyeti nereye gidiyor

`mapping_node` ve `detector_node` içine aşama sayacı kondu (`stage()` /
`report_stages()`, 10 s'de bir p50/p95 olarak loglanır). Sabitlenmiş sahnede,
trafik varken:

| Aşama | Öncesi p50/p95 (ms) | Sonrası p50/p95 (ms) |
|---|---|---|
| Harita: izdüşüm | 3.1 / 3.9 | 3.1 / 3.9 |
| Harita: füzyon | 0.9 / 1.3 | 0.9 / 1.3 |
| Harita: yayın | 3.3 / 4.2 | 3.3 / 4.2 |
| Karar: güvenli maske | 0.3 / 0.5 | 0.3 / 0.5 |
| Karar: mesafe dönüşümü | 0.9 / 0.9 | 0.8 / 1.3 |
| Karar: bileşenler | 0.2 / 0.3 | 0.1 / 0.6 |
| Karar: uygunluk | 0.9 / 1.4 | 0.7 / 0.8 |
| **Karar: yörünge testi** | **44.2 / 65.1** | **0.1 / 0.1** |
| Karar: skor + yayın | 1.1 / 1.2 | 2.0 / 2.5 |

Yörünge testi karar karesinin ~%95'iydi: her aday hücre için her koridor
diskine uzaklık, Python döngüsünde. Yerine maskeyi bir kez rasterleyen
`rasterise_block()` geldi — diskler `cv2.circle`, yaklaşma yolu gölgesi
teğet dörtgen olarak `cv2.fillPoly`. Aynı geometri, aynı karar, 44.2 ms →
0.1–2.6 ms. Ölü kod (`trajectory_clear`, `_segment_point_distance`) silindi.

## 19.2 Hız tavanı darboğaz değil, dengeleyici

Karar karesi ~5 ms'ye indikten sonra `max_rate_hz: 2.0` tavanı akla geldi.
Açmak işleri **kötüleştirdi**:

| Ölçüm | tavan 2.0 Hz | tavan 4.0 Hz |
|---|---|---|
| `/eland/candidate` | 1.46 Hz | 2.18 Hz |
| Durum geçişi | 5 | 8 |
| SEARCH'te geçen süre | 15.4 s | 31.3 s |
| Aday sıçraması (>4 m) | 4 | 8 |

Daha sık karar vermek, daha erken karar vermek değil; daha sık fikir
değiştirmek. Tavan 2.0'da bırakıldı — gerekçesi artık yapılandırma
dosyasında yazılı.

## 19.3 Mandal hücreye değil bölgeye bağlandı

Mandal yalnızca **aynı hücre** hâlâ uygunsa tutuyordu; maskenin bir karelik
oynaması mandalı tümden düşürüyordu. 90 s sabit irtifada, trafik altında
yayınlanan site'ın kat ettiği toplam yol:

| Ölçüm | eski (aynı hücre) k1 | eski k2 | yeni (2.0 m yarıçap) |
|---|---|---|---|
| Ardışık kayma ortalaması | 0.25 m | 1.12 m | **0.05 m** |
| En büyük kayma | 5.75 m | 24.72 m | **3.09 m** |
| >4 m sıçrama | 4 | 10 | **0** |
| Site'ın kat ettiği yol | 32.7 m | 144.3 m | **6.2 m** |

Ölçüm kasten sabit irtifada yapıldı: kapalı çevrimde aynı ayar koşudan koşuya
1 ile 7 arası sıçrama veriyor, çünkü sıçrama uçağın nereye gittiğini, o da bir
sonraki karede ne gördüğünü değiştiriyor.

## 19.4 Asıl kusur: dördüncü katman kendi döngüsünü aç bırakıyordu

Mod günlüğündeki `candidate lost at 12.03 m` satırındaki sayı **mesafe değil
irtifa**. Kaybı tetikleyen şey adayın kayması değil, 3 s boyunca hiç geçerli
aday gelmemesi (`candidate_timeout_s`). Sayılınca:

- 152 karenin **79'unda** hiç aday yayınlanmamış,
- 6 boşluk serisinin **hepsi** 3 s eşiğini aşmış, en uzunu 23.2 s.

Sebep loglanınca tek bir cümleye indi: statik testleri geçen **~20.000 hücrenin
tamamı** bizim dördüncü katmanımız tarafından siliniyordu — 5 hareketli için
biriken ~50 "geçilmiş zemin" diski görüş alanını kaplıyordu. İnişi güvenli
kılmak için eklenen katman, inişi bitiren şeydi; üstelik PX4'ün kendi kör
Descend'ine bırakarak, ki bu birinin yürüdüğü zemine inmekten kesinlikle daha
kötü.

Düzeltme sıralamaya dayanıyor: **bellek geçmişi, koridor geleceği anlatır ve
yalnızca ikincisine çarpılabilir.** Küme boşalırsa önce bellek maskesi
bırakılır (uyarı loglanır), koridor durur. Koridor tek başına da her yeri
kapatıyorsa bu gerçek bir cevaptır ve HOLD/ABORT doğru sonuçtur — SafeLand'in
tepkisel davranışı, baştan beri tasarlandığı gibi yedek olarak kalır.

| Ölçüm (3 kişi + 2 araç, sabit sahne) | Öncesi | Sonrası (3 koşu) |
|---|---|---|
| Aday üretilmeyen kare | 79/152 (%52) | **0/151, 0/152, 0/151** |
| 3 s eşiğini aşan boşluk | 6 | **0** |
| Aday kaybı (mod günlüğü) | 3 | **0, 0, 0** |
| Durum geçişi | 8 | **3, 3, 3** |
| SEARCH'te geçen süre | 15.0 s | **0.3 s, 0.2 s, 0.6 s** |
| Sonuç | 3/3 deneme tükendi, "yine de iniyorum" | tek denemede iniş |

Kullanıcının "uzunca süre bekliyor" dediği şey buydu: CPU değil, tavan değil,
kendi bellek katmanımız.

## 19.5 Hız kestirimindeki sistematik düşüklük (açık madde #9)

Saat açıklaması elendi: harita damgaları duvar saatini 1.012 oranıyla takip
ediyor, yani ölçek hatası yok. Kalan iki aday tek tek denendi.

| Senaryo | Gerçek | Kestirim | Oran |
|---|---|---|---|
| Tek engel, eski eşleme | 1.17 / 3.05 m/s | 1.09 / 2.16 | %93 / %71 |
| Tek engel, tahminli eşleme | 1.19 / 2.98 m/s | 1.16 / 2.08 | **%97** / %70 |
| Çoklu (3+2), eski eşleme | 1.10 / 2.92 m/s | 0.75 / 1.88 | %68 / %64 |
| Çoklu, tahminli eşleme | 1.12 / 2.85 m/s | 0.90 / 1.63 | **%80** / %57 |

(Her hücrede önce insan, sonra araç.) Eşleme artık izin son görüldüğü yere
değil, uyduğu doğrunun **o an olması gereken** yerine bakıyor; insan tarafında
kazanç net (%68 → %80), araç tarafında fark koşu gürültüsünün içinde kalıyor —
aracın asıl sorunu eşleme değil, karelerin %30-40'ında hiç izlenememesi ve
2 m'lik konum hatası.

Dönüş anını kırpma denendi ve **reddedildi**: ham ardışık adım yönüne bakan
sürüm sonucu %32'ye düşürdü, çünkü leke merkezi kareler arasında insanın
kendisinden daha çok oynuyor. Gürültü eşiğine bağlanmış sürüm (1.5 m'lik iki
bacak) %83 / %61 verdi, yani koşu farkı kadar. Parametre kodda duruyor,
varsayılanı 0 (kapalı), gerekçesi yapılandırma dosyasında yazılı.

## 19.6 Yol boyunca öğrenilenler

- Ölçüm betiği `pkill -f tracker_node` çalıştırıyor; komut satırında bu adı
  geçiren **çağıran kabuk da öldü**. Parametre adları artık betiğin içinde.
- Skorlayıcının "115 kare" saydığı şey izleyicinin hızı değil, `obstacle_driver`
  truth yayınının hızıydı (5 hareketliyle 1.0 Hz'e düşüyor). İzleyici 2.85 Hz'de
  sağlamdı. Boru hattı kusuru sanılan şey ölçüm çözünürlüğüydü.
- Durum enum'u dosyadan okunmadan tahmin edildi ve tamamlanmış bir COMMIT,
  "120 s boyunca ABORT'ta takılı" diye raporlandı.
- İki koşu arka arkaya başlatılınca PX4 önceki koşunun portlarını bırakmamıştı;
  temizlik ile başlangıç arası bekleme 2 s'den 10 s'ye çıkarıldı.

## 19.7 Açık

| # | Konu |
|---|---|
| 22 | ~~Bellek bırakıldığı karelerde site 4-7 kez 4 m'den fazla sıçrıyor.~~ §20'de kapandı: bellek artık ceza, sıçrama 3-4'e indi. |
| 23 | ~~Araç karelerin %30-40'ında hiç izlenmiyor.~~ §20.4'te kapandı: 44 karenin 43'ünde araç haritanın dışındaydı, kusur değil. |

# 20. Veto değil fiyat: dördüncü katmanın yeniden düzenlenmesi (madde 22-23)

## 20.1 §19.4'teki teşhis eksikti

Dün "geçilmiş zemin belleği her şeyi kapatıyor" denmişti ve konan yedek dal,
küme boşalınca `site_blocked` dışındaki her şeyi bırakıyordu — yani yalnızca
belleği değil, **yaklaşma yolu gölgesini de**. Bellek skora ceza olarak
taşınıp gölge sert maske olarak bırakılınca boşalma geri geldi (155 karenin
53'ü), böylece hangi maskenin suçlu olduğu ölçülebildi:

| Kare örneği | Statik testleri geçen | Koridor tek başına bırakır | Gölge tek başına bırakır |
|---|---|---|---|
| 1 | 21100 | 12109 | **0** |
| 2 | 20932 | 8230 | **0** |
| 3 | 20774 | 4494 | **0** |
| 4 | 20766 | 6314 | **0** |
| 5 | 20113 | 8174 | **0** |

Yaklaşma gölgesi trafik varken **her karede haritanın tamamını** örtüyordu.
Hiçbir şey bırakmayan bir test, test değildir.

İki sebebi vardı. Gölge, her koridor örneği için uçaktan çizilen teğet
kamadan oluşuyor ve harita köşegeni boyunca uzatılıyordu; 26-78 örnekle bu
kamaların birleşimi her yönü kapsıyor. İkincisi ve daha ağırı: uçak yatayda
herhangi bir diskin içine düştüğünde kod `route[:] = 1` ile haritayı tümden
kapatıyordu — oysa uçak diskin **15 m üstünde**, içinde değil. Altından bir
insan geçmesi tüm haritayı yasaklıyordu.

## 20.2 Yeni ayrım: tek sert dışlama, iki fiyat

- **Koridor diskleri (sert):** tehlikenin *olacağı* zemin. Uçağın üstüne
  oturmaması gereken tek şey budur; burası boşalırsa cevap gerçekten
  "yer yok"tur ve HOLD/ABORT doğrudur — SafeLand'in tepkisel davranışı yedek
  olarak yerinde durur.
- **Geçilmiş zemin (fiyat, `w_memory` 0.35):** tazelikle ölçekli. 2 s önce
  geçilmiş yer tam ceza öder, 28 s önce geçilmiş yer neredeyse hiç; ikisi de
  alternatif hiçlikse inilebilir kalır.
- **Yaklaşma gölgesi (fiyat, `w_route` 0.20):** tehlikenin gölgesinde kalan
  site kaybeder ama yasaklanmaz. Dosyanın kendi ifadesiyle: bir güzergâh
  oturmak için kötü bir yerdir, on beş metreden üstünden geçmek için değil.

`route[:] = 1` dalı kaldırıldı: uçağın yatayda diskin içinde olması gölge
üretmez, disk zaten site olarak dışlanmıştır.

## 20.3 Ölçüm (3 kişi + 2 araç, sabit sahne)

| Ölçüm | §19 öncesi | §19'daki yedek dal | Şimdi (2 koşu) |
|---|---|---|---|
| Aday üretilmeyen kare | 79/152 | 0/151 | **0/151, 0/154** |
| Aday kaybı | 3 | 0 | **0, 0** |
| Durum geçişi | 8 | 3 | **3, 3** |
| SEARCH'te geçen süre | 15.0 s | 0.3 s | **0.3 s, 0.6 s** |
| Aday sıçraması (>4 m) | 4-7 | 4-7 | **4, 3** |

Katman devre dışı kalmadı: koridor hâlâ uygun hücrelerin ~%28'ini eliyor
(`trajectory filter removed 3533 of 13389` tipi satırlar, 39 kez).
Açık madde 22'nin istediği sıçrama azalması kısmen geldi (4-7 → 3-4); kalanı
mandalın tuttuğu hücrenin uygun kümeden çıkması, mandal serbest bırakma
sayısı 0.

## 20.4 Araç neden izlenmiyordu (madde 23): kusur değilmiş

İzlenmeyen kareler üç ayrı sebebe ayrıldı ve sonuç tek satırda çıktı:

| Sebep | Kare |
|---|---|
| Araç haritalanmış zeminin **dışında** | 43 (ve ikinci koşuda 34) |
| Harita içinde, o sınıftan leke yok | **0** |
| Leke var ama 6 m'den uzak | 1 |

Yani "araç karelerin %30-40'ında izlenmiyor" ifadesi yanlıştı: araç 40×70 m'lik
rotasında 40×40 m'lik harita alanının dışına çıkıyor. Kamera görüş alanının
dışındaki bir nesneyi izlememek doğru davranış.

Hız düşüklüğünün bir kısmı da buradan geliyor. Kenara olan uzaklığa göre
ayrıldığında (gerçek 2.95 m/s):

| Kare kümesi | Kestirilen hız |
|---|---|
| Kenara 4 m'den yakın | 1.13 m/s (32 kare) |
| Kenara 4 m'den uzak | 1.54 m/s (54 kare) |

Kenar yakınlığı ~%27 kaybettiriyor; ama iç karelerde bile gerçeğin %52'sinde
kalınıyor. Kalan pay büyük olasılıkla rota dönüşleri: araç 3 m/s'de 16-70 m'lik
bir bacağı 5-23 s'de bitiriyor, LSQ penceresi ~2.6 s, yani pencerelerin kayda
değer bir bölümü bir dönüşü içeriyor. İnsan için aynı bacak 15-60 s sürdüğü
için insan kestirimi %80-90'da. Bu, `reversal_leg_m` denemesinin neden insanda
işe yaramadığını da açıklıyor: sorun insanda zaten yoktu.

**Kalan risk ve neden şimdilik kabul edilebilir:** düşük kestirilen hız
koridoru kısaltır. Karşı ağırlık, koridor yarıçapının `(2 - confidence)` ile
ölçeklenmesi — kısa ve gürültülü izler zaten düşük güvenle geliyor ve
karşılığında daha geniş bir koridor üretiyor.

## 20.5 Açık

| # | Konu |
|---|---|
| 24 | Araç hız kestirimi, harita içinde bile gerçeğin ~%52'si. Sebep büyük olasılıkla LSQ penceresinin dönüşleri içermesi; örnek sayısıyla değil süreyle tanımlı, hıza göre kısalan bir pencere denenmedi. |
| 25 | Aday hâlâ koşu başına 3-4 kez 4 m'den fazla sıçrıyor (mandal serbest bırakılmadan). Mandalın tuttuğu hücre uygun kümeden çıktığında ne olacağı ayrıca ele alınmalı. |
