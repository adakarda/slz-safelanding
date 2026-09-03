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
