# Gereksinim Checklist'i — Uyumluluk Değerlendirmesi

Değerlendirme tarihi: 2026-09-01
Değerlendirilen kod: `~/ros2_ws/src/eland_*`

Özet: **17 değerlendirilebilir madde — 15 ✅, 2 ⚠️, 0 ❌.**

> **2026-09-01 ikinci geçiş.** İlk değerlendirmedeki 3 ❌ de kapandı: PID'in
> kontrol değişkeni alan oranına çevrildi (2 madde) ve "bağlantı koptu"
> senaryosu gerçek failsafe'e bağlandı. Ayrıca bir ⚠️ (minimum alan eşiği)
> ✅ oldu. Değişen maddelerin altında ölçüm sonuçları var.
>
> Ayrıca IPM tamamlandı ve iki gizli hata ortaya çıkardı (heading'in yok
> sayılması, haritanın kuzey-güney aynalanması).
>
> Kalan 2 ⚠️: 7 SORA sınıfıyla birebir olmama (kasıtlı, label-0 gerekçesiyle)
> ve alan-oranı kriterinin dar geçerlilik alanı (`view_bounded`).

---

## 1. Kamera / Görüntü Alma

**✅ Kamera top-down (pitch ≈ -90°)**
`x500_seg_cam_down/model.sdf` hem include pozunda hem `CameraJoint`'te
`1.5707` rad pitch uyguluyor — PX4'ün kendi `x500_mono_cam_down` modelinden
birebir devralınan yapı.

**✅ Çıktı doğru topic üzerinden segmentasyona ulaşıyor**
`/seg_cam/labels_map` → `ros_gz_image image_bridge` → `/camera/segmentation`
→ `perception_node` → `/eland/semantic_mask`. Ölçüldü: 320x240 `rgb8`, 5 Hz.

---

## 2. Segmentasyon

**✅ Piksel-bazlı semantik sınıflandırma**
`perception_node` `mono8` maske yayınlıyor, her pikselin değeri sınıf ID'si.

**✅ GT mi model mi — net**
Şu an Gazebo ground-truth sensörü (`use_gt_segmentation: true`). Arayüz
sabitlendi: `perception_node` her iki durumda da aynı `/eland/semantic_mask`
sözleşmesini yayınlıyor, `use_gt_segmentation:=false` dalı Faz 5 için hazır
duruyor. Yani model değiştiğinde aşağı akıştaki hiçbir node değişmiyor.

**❌→⚠️ 7 SORA sınıfıyla birebir örtüşme — KASITLI OLARAK HAYIR**
10 sınıf kullanılıyor, birebir değil. Sebep teknik ve bağlayıcı:

> Gazebo'da **etiketlenmemiş her şey label 0**. Brief'in şemasında
> `0 = safe-soft`. O şemayla gökyüzü, etiketsiz zemin ve her etiketleme
> hatası "güvenli iniş alanı" olarak okunurdu.

Bu yüzden `0 = UNKNOWN` (risk 1.0) tutuldu ve SORA sınıfları bunun üzerine
bir eşleme olarak tanımlandı:

| SORA sınıfı | eland ID'leri |
|---|---|
| safe-soft | GRASS(1), DIRT(2) |
| safe-hard | GRAVEL(3), PAVEMENT(4) |
| terrain-hazard | VEGETATION(5) |
| structure | BUILDING(6) |
| water | WATER(7) |
| vehicle-animal | VEHICLE(8) |
| person | PERSON(9) |
| *(SORA'da yok)* | UNKNOWN(0) — risk 1.0 |

Eşleme kayıplı değil: 7 SORA sınıfının hepsi temsil ediliyor, ikisi daha ince
taneli. Birebir istenirse `classes.py` + `class_risk` + world label'ları
birlikte değişmeli — ama 0'ın UNKNOWN kalması şart.

---

## 3. İniş Bölgesi Seçim Algoritması

**✅ SORA risk sınıflandırmasına göre çalışıyor**
`detector_node`: `safe_classes: [1,2,3]` (grass/dirt/gravel) maskeleniyor,
`class_risk` tablosunda person ve vehicle 1.0. Bölge dışlama mesafe dönüşümü
ile: bir hücre, en yakın güvensiz hücreden `r_safe = 3.0 m` uzakta değilse
eleniyor.

Ölçülen kanıt: drone insanın 3 m yanına doğduğunda aday yarıçapı **3.03 m**;
aynı noktada yakında insan yokken **8.5 m**. Yani kısıt bağlayıcı, insan iniş
noktasını kaydırıyor.

**✅ "En uygun bölge" tanımı net ve kodda**
`argmin(alpha * risk + beta * normalize_edilmiş_mesafe)`, `alpha=0.7`,
`beta=0.3`, yalnızca `r_safe`'i geçen hücreler üzerinde.
Yani: **risk-ağırlıklı, eşitlikte drone'a en yakın.** Gerekçe: acil durumda
enerji ve zaman en kısa yol lehine, ama risk üç kat daha ağır tartılıyor.

Not: checklist'teki "en büyük bağlı alan" seçeneği uygulanmadı — alan
büyüklüğü doğrudan değil, `radius` (boşluk yarıçapı) üzerinden dolaylı olarak
dikkate alınıyor.

**✅ Minimum boyut/alan eşiği** *(ikinci geçişte eklendi)*
`cv2.connectedComponentsWithStats` ile bağlı bileşen analizi yapılıyor, her
bölgenin metrik alanı hesaplanıyor, `min_area_m2 = 9.0` altındakiler eleniyor.

Ayrıca eski tek `r_safe` ikiye ayrıldı, çünkü tek bir sayı iki farklı işi
birden yapıyordu:

| | değer | ne soruyor |
|---|---|---|
| `r_hazard` | 3.0 m | SORA: insan/araç/yapı/sudan ayrım. Mutlak, pazarlıksız. |
| `r_fit` | 1.0 m | Araç fiziksel olarak sığıyor mu (x500 ≈ 0.5 m). |
| `min_area_m2` | 9.0 m² | Bölge şeklinden bağımsız olarak yeterince büyük mü. |

Neden önemliydi: tek 3 m eşiğiyle 4 m × 4 m'lik bir çim yaması, etrafında
hiç tehlike olmasa bile seçilemiyordu (ulaşabileceği maksimum boşluk 2 m).
Ayrım ölçüldü ve SORA kısıtı hâlâ bağlayıcı: drone insanın 3 m yanına
doğduğunda aday `radius: 3.04 m` ile tam `r_hazard` sınırında çıkıyor.

**✅ Görüntü → gerçek dünya koordinat dönüşümü** *(ikinci geçişte tamamlandı)*

Gerçek IPM yazıldı. Her piksel bir ışın: yönü `K^-1 p`, NED'e döndürülüp yer
düzlemiyle kesiştiriliyor. Zemin düzlem olduğu için tüm eşleme tek bir 3×3
homografiye iniyor ve `cv2.warpPerspective` (INTER_NEAREST — sınıf ID'leri
interpole edilemez) ile uygulanıyor.

**Düzeltme:** Daha önce buraya "intrinsic'ler `/camera/camera_info`'dan geliyor,
doğrulandı" yazmıştım. Yanlıştı — topic'in `ros2 topic list`'te *göründüğünü*
doğrulamışım, veri aktığını değil. `ros2 topic hz` hiçbir şey vermiyor:
`ros_gz_image` topic'i ilan ediyor ama labels_map akışı için hiç yayınlamıyor.
Yani baştan beri FOV yedeği çalışıyor. Zararsız: gz'nin kendi camera_info'su
`fx = 134.984` diyor, yedeğin ürettiği 134.7 — %0.2 fark. CameraInfo yolu
gerçek sensör için duruyor.

Yerini aldığı nadir yaklaşımında, roll/pitch'i yok saymanın ötesinde **iki
gerçek hata** varmış:

1. **Heading tamamen yok sayılıyordu** — harita yalnızca kuzeye bakarken
   anlamlıydı.
2. **Kuzey-güney ters yapıştırılıyordu.** OccupancyGrid satır 0 origin
   satırıdır, yani en güney; görüntü satır 0 ise kadrajın üstü, yani aracın
   ileri yönü. Harita aynalanmıştı.

İkisi de önceki testlerde görünmemişti çünkü seçilen iniş noktası hep aracın
neredeyse tam altındaydı — orada aynalanmış harita ile doğrusu aynı cevabı
veriyor.

Doğrulama: insan gerçekte drone'un 3 m güneyinde. Heading'leri 90° farklı iki
koşu:

| koşu | PX4 heading | ölçülen insan konumu |
|---|---|---|
| A | 1.68 rad (96°) | east −0.28, north **−3.04** |
| B | 0.11 rad (6°) | east −0.38, north **−3.10** |

Heading'i yok sayan bir uygulama insanı bu iki koşu arasında ~90° döndürürdü;
ters çeviren bir uygulama north **+3** verirdi. Kalan ~0.3 m doğu sapması
izole edilmedi (adaylar: insanın 1.8 m boyunun düz zemin varsayımını ihlali,
kamera kol mesafesinin ihmali) — SORA'nın 3 m marjının çok içinde.

Ek olarak `max_tilt_deg: 30` ile eğim kapısı: 99.7° FOV'da ufuk ~40°'de
kadraja giriyor ve ufka yakın ışınlar absürt mesafelere projekte oluyor.
Kareyi düşürmek, bulanık bir kareyi füzyona katmaktan iyi.

---

## 4. İniş Kontrolü (PID)

**✅ Kontrol değişkeni artık alan oranı** *(ikinci geçişte değiştirildi)*

```cpp
ceiling = clamp(descent_size_gain * sqrt(area_m2), v_min, v_max)
v       = clamp(ceiling * (1 - area_ratio), v_min, ceiling)
```

`area_ratio`, `detector_node` tarafından **görüntü uzayında** hesaplanıyor:
maskede aracın tam altındaki (görüntü merkezindeki) bağlı güvenli bölgenin
piksel sayısı / toplam piksel. İrtifa girdisi yok.

Neden `ceiling` de var: ham alan oranı "ne kadar yakınım" ile "hedef ne kadar
büyük"ü karıştırıyor. 5 m'de 10 m'lik bir yama görüşün %95'ini, 4 m'lik bir
yama %15'ini doldurur — ham oranla drone **en dar alana en hızlı** inerdi.
Tavanı bölgenin kendi boyutundan türetmek bunu düzeltiyor: 15 m'de 10 m'lik
yamaya 1.79 m/s, 4 m'lik yamaya 0.79 m/s.

**✅ "Oran büyüdükçe hız azalır" — ölçüldü**

İzole 392 m²'lik toprak yaması üzerinde, 20 m'den emredilen hız dizisi:

```
1.52 → 1.50 → 1.46 → 1.41 → 1.35 → 1.29 → 1.22 → 1.14 → 1.05 → 0.92 → 0.78 → 0.68 m/s   [area]
```

Gerçekleşen `vz` bunu takip etti (3 s: 1.37, 9 s: 1.52, 12 s: 1.49, 15 s: 0.43).
`area_ratio` 20 m'de 0.234 ölçüldü; teorik değer 0.237.

**⚠️ Kriterin bir geçerlilik koşulu var — kodda ayrı bir dal olarak duruyor**

`oran → 1.0` **belirsiz**: ya "çok yakınım" ya "alan devasa" demek. Ölçek
referansı olmadan ayırt edilemez, ve bu akademik bir kaygı değil — açık çim
arazide oran 20 m'den itibaren 0.81'de sabit kaldı, ham oranla yasa tüm inişi
0.3 m/s tabanında süründürdü: **27 s yerine 73 s**, ve yere yakın hiç
yavaşlama olmadı çünkü yavaşlayacak yer kalmamıştı.

Ayırt edici tek işaret: bölge görüntü kenarına değiyor mu. Değiyorsa oran
bölgenin alt sınırından başka bir şey söylemiyor. `view_bounded` alanı bunu
taşıyor:

| durum | kullanılan yasa | ölçülen iniş süresi |
|---|---|---|
| `view_bounded: true` (izole yama) | alan oranı | 24 s |
| `view_bounded: false` (açık arazi) | irtifa (tavan yine alandan) | 26 s |

⚠️ olmasının sebebi: kriter yalnızca güvenli bölge görüş alanından küçükken
gerçek bir yakınlık sinyali. Bu, ölçülmüş ve kodda açıkça ele alınmış bir
sınır — ama yine de spesifikasyonun varsaydığından dar bir geçerlilik alanı.

**✅ Yatay konumlama ile dikey alçalma ayrı yönetiliyor**
- `APPROACH`: yalnızca yatay, irtifa sabit (`target.z = pos.z`).
- `VALIDATE`: goto setpoint'i `max_horizontal_speed` ve `max_vertical_speed`
  limitlerini ayrı ayrı alıyor.
- `COMMIT`: tamamen ayrık — yatayda pozisyon (`withPositionX/Y`), dikeyde hız
  (`withVelocityZ`).

**⚠️ Son yaklaşmada ekstra güvenlik/yavaşlama**
Var ama kısmi:
- Alçalma hızı tabanı 0.3 m/s, ~0.9 m altında bu değere sabitleniyor.
- `COMMIT`'te pozisyon kontrolünden hız kontrolüne geçiliyor (PX4'ün iniş
  dedektörünün tetiklenmesi için zorunlu — bkz. aşağıdaki not).

Olmayan: düşük irtifada **tekrar segmentasyon doğrulaması**, dinamik engel
görünce duraklama/yeniden rotalama. `COMMIT` bilinçli olarak geri dönüşsüz.

---

## 5. PX4 / Mod Entegrasyonu

**✅ Resmi custom flight mode mekanizması**
`px4_ros2::ModeBase`'den türeyen `EmergencyLandingMode`,
`px4_ros2::NodeWithMode<>` ile kaydediliyor. Manuel offboard script **yok**;
`/fmu/in/*`'a yazan tek bir satır bile kalmadı (`px4_topics.py` artık sadece
`/fmu/out` sabitleri taşıyor).

**✅ QGroundControl mod listesinde görünüyor ve tetiklenebiliyor**
Protokol seviyesinde doğrulandı — QGC'nin mod menüsünü kurduğu `AVAILABLE_MODES`
(MAVLink 435) mesajı sorgulandı:

| | slot 19 |
|---|---|
| Mod kaydından **önce** | `(Mode not available)` |
| Mod kaydından **sonra** | **`Emergency Landing`**, `custom_mode 184811520` |

Tetikleme de standart GCS yolundan denendi: `MAV_CMD_DO_SET_MODE`,
`base_mode = CUSTOM_MODE_ENABLED`, `main_mode=4`, `sub_mode=11`
→ `COMMAND_ACK result=0 (ACCEPTED)`, `HEARTBEAT custom_mode=184811520`,
`nav_state=23`, mod aktive oldu.

Uyarı: makinedeki `QGroundControl.AppImage` **Mart 2025** tarihli (Daily
değil). PX4 tarafının doğru olduğu kanıtlandı, ama o özel build'in GUI'sinde
gözle görülmedi.

**✅ "Bağlantı koptu" senaryosu gerçek failsafe ile bağlı** *(ikinci geçişte eklendi)*

`replace_internal_mode: "rtl"` parametresiyle mod PX4'ün Return modunun yerine
kaydediliyor. Hedef seçimi ölçümle netleşti: **`Descend` yanlış hedefti.**
`NAV_RCL_ACT` seçenekleri Hold(1) / Return(2, varsayılan) / Land(3) /
Terminate(5) / Disarm(6) — Descend listede yok. Descend yalnızca pozisyon
kaybında yedek olarak giriliyor, ki bu mod zaten pozisyona muhtaç. Yani
Descend'i değiştirmek, bağlantı kopmasında hiç tetiklenmeyen bir mod üretirdi.

Return hem brief'in dediği hem de PX4'ün varsayılan failsafe eylemi, dolayısıyla
**hiçbir PX4 parametresi değiştirmeden** tetikleniyor.

*Test 1 — komutla:* `DO_SET_MODE` ile Return istendi (`custom_mode 84148224`)
→ `HEARTBEAT custom_mode` **184811520** döndü, yani RTL'inki değil bizimki.
`nav_state: 23`, mod iniş dizisini başlattı.

*Test 2 — gerçek bağlantı kopması:* Enjekte edilmiş arıza yerine gerçek bir
GCS bağlantısı kuruldu (iki yönlü heartbeat doğrulandı), 20 s sonra kesildi.
`NAV_DLL_ACT=2`, `COM_DL_LOSS_T=10 s`:

| kopmadan sonra | nav_state | irtifa |
|---|---|---|
| 15 s | 4 (Hold) | 20.0 m |
| **20 s** | **23 (bu mod)** | 16.2 m |
| 25 s | 23 | 8.8 m |

Gecikme = `COM_DL_LOSS_T` 10 s + PX4'ün 5 s Hold bekleme süresi.
Sonrasında hiçbir manuel müdahale olmadan: SEARCH → APPROACH → VALIDATE →
COMMIT (1.99 m) → `touchdown detected`, `landed: True`, disarm.
Aktivasyondan temasa **26 s**.

Ters yön de ölçülü ve çalışıyor: ROS node'u öldürüldüğünde PX4 kendi moduna
geri düşüyor, araç düşmüyor.

Bilinmesi gereken yan etki: bu mod kayıtlıyken **kasıtlı bir RTL de** eve
dönmek yerine burada acil iniş yapar. İstenmiyorsa `replace_internal_mode`
`"land"` (NAV_RCL_ACT=3 ile) veya `"none"` yapılabilir.

---

## 6. Genel Uyumluluk

**✅ PX4 mod/setpoint kurallarına uygun**
- Kütüphanenin izin verdiği setpoint tipleri kullanılıyor:
  `MulticopterGotoSetpointType` ve `TrajectorySetpointType`.
- Arming/mode geçişleri kütüphaneye bırakıldı; el ile `DO_SET_MODE` /
  `COMPONENT_ARM_DISARM` gönderilmiyor.
- Mod arming check'lerine katılıyor (`Arming check request` logu).
- Node ölümünde PX4 kendi moduna düşüyor (ölçüldü).

**Faz durumu**

| Faz | Durum |
|---|---|
| 1 — Segmentasyon pipeline testi | ✅ |
| 2 — Seçim algoritması | ✅ zamansal füzyon ✅, IPM/attitude ✅ (bu satır bir süre "IPM ❌" diyordu; bayattı, IPM 2026-09-01'de tamamlandı ve doğrulandı) |
| 3 — Mod iskeleti | ✅ |
| 4 — Entegrasyon | ✅ (`replaceInternalMode` hariç) |
| 5 — Gerçek model | ✗ başlanmadı |

---

## Belirsizliklerin cevapları

**"En uygun bölge" kriterinin tam tanımı**
Netleşti ve kodda. Üç bağımsız uygunluk testi:
`bölge_alanı ≥ min_area_m2` **ve** `dist_fit ≥ r_fit` **ve**
`dist_hazard ≥ r_hazard`. Bunları geçen hücreler arasında
`0.7 * risk + 0.3 * normalize_mesafe` skorunu minimize eden seçiliyor —
risk-ağırlıklı, eşitlikte drone'a en yakın. "En büyük alan" kriteri
uygulanmadı; alan bir *eşik*, seçim ölçütü değil.

**PID'in "alan yüzdesi" mantığı koda yansımış mı**
İkinci geçişte **evet.** Kontrol değişkeni artık görüntü uzayında ölçülen
`area_ratio`, tavanı bölgenin metrik alanından geliyor, irtifa yalnızca
`view_bounded` false iken yedek olarak kullanılıyor. İlk geçişteki
"irtifa tabanlı" sapma kapandı.

---

# 7. Dinamik engeller + yörünge-farkında karar

Değerlendirme tarihi: 2026-09-03. Kaynak gereksinim:
`dinamik-engel-yorunge-gorev.md`. Ölçüm çıktılarının tamamı
`docs/DURUM.md` §12'de; burada madde başına uyum.

Özet: **9 değerlendirilebilir madde — 7 ✅, 2 ⚠️, 0 ❌.**

## 7.1 Gazebo'da dinamik modeller

**⚠️ Dinamik insan `<actor>` ile — çalışıyor ama varsayılan değil**
`gen_world.py` hem `<actor>` hem `<model>` üretebiliyor (`person_kind`).
Actor'ün Label eklentisiyle etiketlendiği **ölçülerek** doğrulandı: sınama
dünyasında etiket 3 ile 123 px, centroid 5 s'de 124.8 → 207.0 px kaydı,
statik kontroller kıpırdamadı. Varsayılanın `model` olmasının sebebi
ölçülebilirlik: Gazebo actor pozunu yayınlamıyor ve script'in dediği hızda
yürütmüyor (33.3 s'lik tur ~28 s), yani tahmin doğruluğunu puanlayacak bir
referans yok. ⚠️ işareti bu sapma için; gereksinim "actor ile" diyordu,
uygulama actor'ü destekliyor ama ölçüm için modeli kullanıyor.

**✅ Dinamik araç, tanımlı yörüngede sabit hızla**
`dyn_vehicle`, VEHICLE(8) etiketli kutu, `obstacle_driver` tarafından sim
saatinde ışınlanıyor. Düz hat, sabit hız, `once` veya `pingpong`.

**✅ Her ikisi de doğru sınıfa etiketli**
PERSON(9) ve VEHICLE(8), `eland_common/classes.py`'deki tek kaynağa göre.
Maskede ölçüldü: 278/278 karede her iki sınıf da mevcut, hiç kaybolmadı.

**✅ Yörüngeler kod içinde parametrik**
`eland_params.yaml` → `obstacle_driver`: `*_start`, `*_goal`, `*_speed`,
`vehicle_mode`. Aynı sayılar hem dünyayı üretiyor hem çalışma anında sürüyor,
yani geometri ile yörünge ayrışamıyor. Ölçüm koşularında dört farklı senaryo
tek satır değiştirilerek kuruldu (±30 y=0, ±12 y=0, ±40 y=0, ±30 y=+15).

**✅ Yörünge iniş alanının içinden geçiyor**
Varsayılan araç güzergâhı `y = 0`, yani doğuş noktasının ve varsayılan iniş
alanının tam üstünden. Uzaktan izlenen bir engel değil: filtre kapalıyken
araç, inmiş aracın 35 cm yanından geçti.

## 7.2 Yörünge tahmini

**✅ Dinamik sınıflar zaman içinde takip ediliyor**
`tracker_node`: bağlantılı bileşen → en yakın komşu eşleme → son N centroid
üzerinden en-küçük-kareler hız kestirimi. Kalman yok; gerekçesi node
başlığında (ölçülen hata bütçesi bir filtrenin modelleyebileceğinden farklı
kaynaklardan geliyor).

**✅ Gelecek konumlar doğrusal projeksiyonla hesaplanıyor**
`horizon_s: 10.0`, `prediction_steps: 5`. Ufkun 4 s'den 10 s'ye çıkarılması
ölçümle zorunlu oldu: 4 s'lik ufukla araç haritanın dışındayken karar verildi
ve araç sonra temas noktasının 0.10 m yanından geçti.

**✅ Kesişim/yakınlık kontrolü hem nokta hem rota için yapılıyor**
`detector_node.trajectory_clear`: her aday hücre koridor disklerinin dışında
olmak zorunda, ve `check_approach_path` açıkken drone→hücre doğru parçası da.

**⚠️ Tahmin doğruluğu ufkun ucunda zayıf**
Ölçülen (güvenilir track'ler): +2 s'de 2.1 m (insan) / 3.4 m (araç), +10 s'de
10.1 m / 16.9 m. Ayrıca hız sistematik olarak düşük kestiriliyor (insanda %87,
araçta %68) ve bu **güvensiz yönde** bir hata — koridor kısa çıkıyor. Kısmen
telafi ediliyor (süpürülmüş güzergâh hafızası + mevcut reaktif HOLD/ABORT),
ama kapatılmadı. `docs/PLAN.md` bölüm 4, madde 7.

## 7.3 Karar mantığına entegrasyon

**✅ Dördüncü test eklendi, diğer üçüyle aynı sırada**
`trajectory_clear`, `min_area_m2` / `r_fit` / `r_hazard` ile aynı seviyede bir
eleme. Skora terim olarak eklenmedi; gerekçe `PLAN.md` K7'de: SORA ayrımı
pazarlık konusu değilse, yeterince iyi bir hücre engelin gideceği yerde olmayı
telafi edemez.

**✅ SafeLand'in reaktif mekanizması korundu**
`HOLD` / `ABORT` durumları, `candidate_timeout_s`, `max_landing_attempts`
hiç değiştirilmedi. Ölçüm koşularında ikisinin birlikte çalıştığı görüldü:
Ö4'te bir aday kaybı reaktif yoldan işlendi (attempt 1/3), iniş yine de
prediktif filtrenin izin verdiği noktaya yapıldı.

**Not — entegrasyonun ortaya çıkardığı bir sorun ve çözümü.** Filtre, koridor
kayınca kazanan hücreyi 12 m öteye atlatıyor; mod bunu "aday kaybı" sayıp
deneme bütçesini tüketiyor ve `no retries left, committing anyway` ile zaten
reddedilmiş noktaya iniyordu. Eklenen `w_stickiness`, uygunluk testlerinden
sonra uygulanan bir tercih terimi: seçimi uzatır, reddedilmiş hücreyi geri
getirmez.

## 7.4 Ölçüm planı

| Madde | Durum | Sonuç |
|---|---|---|
| 1. Segmentasyon dayanıklılığı | ✅ | 3.11 Hz, en uzun boşluk 0.43 s; sınıf 8 ve 9 **278/278 karede** mevcut. Not: ground-truth segmentasyon, %100 tutarlılık simülatörün özelliği. |
| 2. Yörünge tahmini doğruluğu | ✅ | Konum hatası 1.37 m (insan) / 1.79 m (araç); tahmin hatası +2 s'de 2.1 / 3.4 m, +10 s'de 10.1 / 16.9 m. |
| 3. Yanlış pozitif yok | ✅ | Engel 15 m uzakta ve kesişmiyorken temas (−0.09, −0.29) — baseline'ın seçtiği yer, 17 s, iptal yok. |
| 4. Kesişme senaryosu | ✅ | Araç yaklaşırken tetiklendi; temas (1.26, −4.64), araç hattından **4.64 m**. Tam SEARCH→COMMIT logu `DURUM.md` §12.3'te. |
| 5. Karşılaştırma | ✅ | Filtre kapalı, aynı senaryo: temas (−0.10, −0.35), hattan **0.35 m**. Araç, inmiş aracın 35 cm yanından geçti. Fark: 4.29 m. |

## 7.5 Faz durumu (güncel)

| Faz | Durum |
|---|---|
| 1 — Segmentasyon pipeline testi | ✅ |
| 2 — Seçim algoritması | ✅ (zamansal füzyon ✅, IPM ✅ — bu tablonun eski hâli bayattı) |
| 3 — Mod iskeleti | ✅ |
| 4 — Entegrasyon | ✅ |
| 5 — Gerçek segmentasyon modeli | ✗ başlanmadı (GPU bekliyor) |
| 6 — Dinamik engeller + yörünge-farkında karar | ✅ |
