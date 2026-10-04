# Geri bildirim (Tur 3, sonuç) — A ve B uygulandı, doğrulandı

> **Bu metin ne:** Tur 3 geri bildirimine verdiğin kararlar uygulandı:
> 1. A: yeni `GoruntuKapsami` mesajı, `publish_rho` varsayılan false.
> 2. B: tavan donmuş alandan.
> 3. İki parametre `false` olarak `eland_params.yaml`'da.
> 4. Mod `/eland/rho`'yu kullanmıyor.
> 5. Ek ölçüm yok.
>
> İstediğin doğrulama: B'de ayar başına ≥ 5 tohum, temas hızının ortancası ve
> en büyüğü; kapalıyken eski davranış koşuyla. Aşağıda sonuçlar, yöntem,
> ölçülemeyenler ve kodun kendisi var.
>
> - **Tarih:** 2026-10-04.
> - **Kod (açık depo):** <https://github.com/adakarda/slz-safelanding>.
>   - Uygulama: etiket
>     [`v5.7-rho-yayini-commit-irtifa`](https://github.com/adakarda/slz-safelanding/tree/v5.7-rho-yayini-commit-irtifa),
>     commit
>     [`34b6b3a`](https://github.com/adakarda/slz-safelanding/commit/34b6b3a).
>   - Bütün tablolar: `docs/VERI_TOPLAMA.md`, "A ve B — uygulandı".
> - **Veri GitHub'da değil:** koşular bu makinede,
>   `~/eland_veri/_tur3_dogrulama/`; tablo
>   `~/eland_veri/_tur3/tur3_dogrula.md`.
> - **Etiketler:** **ölçülen**, **_hesap**, **_tahmin**.

---

## 1. Durum

| Madde | Durum | Doğrulama |
|---|---|---|
| A — `/eland/rho` | **yapıldı** | kapalı 6 + açık 3 Kol 0 bölümü |
| B — `commit_irtifa_yasasi` | **yapıldı** | zorlanmış erken COMMIT, 5 tohum × 2 ayar; ayrıca sert temaslı 3 K3 bölümü × 2 ayar |
| İki parametre `eland_params.yaml`'da | **yapıldı** | ikisi de `false` |
| Mod `/eland/rho`'yu kullanmıyor | **öyle** | modda abonelik eklenmedi |

**Derleme:** `colcon build --packages-select eland_msgs eland_mapping eland_mode`,
uyarısız. Derlemeden önce kurulu dosyaların kaynakla aynı olduğu kontrol edildi;
derleme yalnız bu değişiklikleri taşıyor.

**Koşular:** 26 bölüm, hepsi veri setinin dışında. 1'inde PX4 kalkmadı
(K3 tekrarı, kapalı, `t2029_t2`: "irtifa 0 m", mod devreye girmedi); o bölüm
bir kez yeniden uçuruldu, ilk deneme `_basarisiz/` altında.

---

## 2. Kapalıyken eski davranış (iki parametre varsayılan `false`)

Kol 0, kayıtlı bölümlerle aynı dünya ve tohum:

| Bölüm | Durum dizisi | COMMIT h_ekf kayıtlı / yeni | COMMIT h_gerçek kayıtlı / yeni | Temas kayıtlı / yeni | VALIDATE→landed kayıtlı / yeni | `/eland/rho` mesajı |
|---|---|---|---|---|---|---|
| kol0_veri_w2_t1 | aynı | 1.95 / 1.98 m | 1.99 / 2.03 m | 0.31 / 0.29 m/s | 25.6 / 26.2 s | 0 |
| kol0_veri_w2_t2 | aynı | 1.93 / 1.97 | 1.98 / 1.99 | 0.30 / 0.29 | 22.1 / 21.9 | 0 |
| kol0_veri_w2_t3 | aynı | 1.96 / 1.98 | 1.99 / 2.07 | 0.30 / 0.31 | 22.9 / 22.9 | 0 |
| kol0_veri_w3_t1 | aynı | 1.97 / 1.94 | 2.04 / 2.09 | 0.30 / 0.31 | 23.0 / 23.0 | 0 |
| kol0_veri_w3_t2 | **farklı:** SEARCH→VALIDATE (kayıtlıda SEARCH→APPROACH→VALIDATE) | 1.93 / 1.95 | 2.03 / 2.01 | 0.30 / 0.31 | 19.8 / 19.5 | 0 |
| kol0_veri_w3_t3 | aynı | 1.95 / 1.94 | 2.05 / 1.99 | 0.31 / 0.31 | 19.7 / 19.9 | 0 |

- **W3 t2:** eski sürümle kaydedilmiş 20 W3-tohum-2 bölümünde (her kol)
  APPROACH 11'inde atlanmış, 9'unda girilmiş. VALIDATE'ten önceki davranış
  koldan bağımsız.
- **SITL bit bit tekrarlanmıyor.** "Aynı" demek aynı durum dizisi ve kayıtlı
  değerlerin yayılımı içinde kalan ölçümler.
- **Grafik**, bölüm ortasında `ros2 topic info /eland/rho -v`:
  `Publisher count: 0`. Konu yalnız kaydedici dinlediği için görünüyor
  (`Subscription count: 1`, `veri_kaydedici`).
- **Dedektörün yayıncıları** (`ros2 node info /detector_node`):
  `/eland/candidate`, `/eland/trajectory_block`, `/parameter_events`,
  `/rosout`.

---

## 3. A açık: `detector_node.publish_rho: true` (Kol 0 W2 t1-t3)

| Bölüm | Mesaj / maske | Hız tüm / VALIDATE | Yakalama → `/eland/rho` alma, p50 / p90 | Maske alma → `/eland/rho` alma, p50 / p90 | ρ farkı (yayın − kaydedici), en büyük | view_bounded uyuşmayan | Durum dizisi |
|---|---|---|---|---|---|---|---|
| t1 | 494 / 494 | 10.00 / 9.99 Hz | 19.5 / 41.2 ms | 0.9 / 1.4 ms | 0.000001 | 0 | kayıtlıyla aynı |
| t2 | 424 / 424 | 9.79 / 9.87 Hz | 19.5 / 40.1 ms | 0.9 / 1.4 ms | 0.000001 | 0 | aynı |
| t3 | 427 / 427 | 9.95 / 9.86 Hz | 19.3 / 38.8 ms | 0.9 / 1.4 ms | 0.000001 | 0 | aynı |

**Üç bölüm birlikte:**
- Yakalamadan `/eland/rho`'nun alınmasına p50 19.5 ms, p90 39.6 ms.
- Dedektörün eklediği p50 0.9 ms, p90 1.4 ms.

**Yöntem:**
- Kaydedici `/eland/rho`'yu dinleyip `rho_yayini.csv`'ye yazıyor (alma
  zamanı, yakalama damgası, ρ, view_bounded).
- Maske tablosuyla yakalama damgasından eşlendi; her mesaj eşlendi.
- ρ farkı 1e-6: CSV'nin 6 anlamlı basamak yuvarlaması.
- Yayın açıkken de uçuş kayıtlıyla aynı; mod konuyu dinlemiyor.

**Ölçülemeyen:**
- Alma zamanları kaydedicinin sim saatiyle. Dedektörün gönderme anı ayrıca
  ölçülmedi.
- Bu bölümde `ros2 node info /detector_node` (`--no-daemon`) düğümü
  bulamadı ("Unable to find node"). Yayıncı bilgisi `topic info`'dan:
  `Publisher count: 1`, `detector_node`, `BEST_EFFORT`.

---

## 4. B — `commit_irtifa_yasasi`

### 4.1 Zorlanmış erken COMMIT (istenen ≥ 5 tohum)

**Senaryo:**
- Sert temaslar aday 3 kez kaybolunca rastlantıyla oluyordu. Erken COMMIT
  mevcut bir parametreyle zorlandı: yalnız bu test için
  `landing_altitude: 10.0`.
- W3 (10×10 m ada); bölge 10-16 m'de kayıtlı verinin %100'ünde kadraja
  sığıyor. Kalkış 18 m, tohum 1-5, her tohum iki ayarla.

| Ayar | Bölüm | COMMIT h_gerçek | COMMIT'te alan yasası | v_cmd: COMMIT girişi → temastan önce | **Temas hızı ortanca / en büyük** | en küçük |
|---|---|---|---|---|---|---|
| kapalı | 5 | 10.06-10.16 m | %100 | 1.18-1.19 → 1.18-1.19 m/s (sabit) | **1.20 / 1.22 m/s** | 1.18 |
| açık | 5 | 10.02-10.16 m | %0 | 1.50 → 0.30 m/s | **0.30 / 0.31 m/s** | 0.30 |

**Bölüm bölüm temas hızı:** kapalı 1.20, 1.22, 1.18, 1.19, 1.20; açık 0.30,
0.31, 0.30, 0.30, 0.30 m/s. 10 bölümün 10'u başarılı; başarı ölçütü hız
içermiyor.

### 4.2 Sert temaslı 3 K3 bölümü, aynı politika tohumuyla yeniden

| Ayar | Bölüm | COMMIT h_gerçek | COMMIT'te alan yasası | Temas | İlk uçuşta |
|---|---|---|---|---|---|
| kapalı | k3_carpan_veri_ada_t2029_t2 | 2.47 m (normal devir) | %0 | 0.30 m/s | 1.10 |
| kapalı | k3_parca_veri_ada_t2024_t2 | 2.36 m (normal devir) | %0 | 0.29 | 1.33 |
| kapalı | k3_parca_veri_ada_t2029_t1 | **13.94 m (erken)** | %100 | **1.27** | 1.27 |
| açık | k3_carpan_veri_ada_t2029_t2 | 2.45 m (normal devir) | %0 | 0.29 | 1.10 |
| açık | k3_parca_veri_ada_t2024_t2 | **14.31 m (erken)** | %0 | **0.30** | 1.33 |
| açık | k3_parca_veri_ada_t2029_t1 | **14.66 m (erken)** | %0 | **0.30** | 1.27 |

Erken COMMIT tekrar edip etmemesi rastlantıya bağlı: kapalıda 3'te 1, açıkta
3'te 2.
- Kapalıyken erken giren bölüm ilk uçuştakiyle aynı hızda (1.27 m/s) yere
  vurdu.
- Açıkken erken giren ikisi 0.30 m/s ile indi.

**Bilinen sınır (değişmedi):** W5 gibi yükseltilmiş hedefte `h_ekf`
platformun üstünde ~4 m gösterir; irtifa yasası orada da yüksek hız verir. B
bunu çözmez.

---

## 5. Kod (uygulanan, `v5.6` → `v5.7` farkı, `src/` altı)

Bağlantılar `v5.7` etiketinde:
- [`GoruntuKapsami.msg`](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_msgs/msg/GoruntuKapsami.msg)
- [`detector_node.py` (yayın, `:387-392`)](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_mapping/eland_mapping/detector_node.py#L387-L392)
- [`emergency_landing_mode.hpp` (COMMIT seçimi `:480-481`)](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_mode/include/emergency_landing_mode.hpp#L480-L481)
- [`emergency_landing_mode.hpp` (`commitAltitudeSpeed`, `:627-641`)](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_mode/include/emergency_landing_mode.hpp#L627-L641)
- [`eland_params.yaml`](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_sim/config/eland_params.yaml)

```diff
--- a/src/eland_msgs/msg/GoruntuKapsami.msg   (yeni)
+++ b/src/eland_msgs/msg/GoruntuKapsami.msg
+# Image-space coverage of the safe region under the image centre, one message
+# per mask from detector_node when its publish_rho parameter is true. Same
+# definitions as LandingCandidate.area_ratio / view_bounded, but at mask rate
+# (~10 Hz) instead of decision rate (~1.8 Hz).
+std_msgs/Header header   # stamp = the mask's capture stamp
+float32 rho              # safe-region pixel share under the image centre, 0..1
+bool view_bounded        # region does not touch the frame edge

--- a/src/eland_msgs/CMakeLists.txt
+++ b/src/eland_msgs/CMakeLists.txt
@@ -15,6 +15,7 @@ rosidl_generate_interfaces(${PROJECT_NAME}
   "msg/LandingState.msg"
   "msg/DynamicObstacle.msg"
   "msg/DynamicObstacleArray.msg"
+  "msg/GoruntuKapsami.msg"
   DEPENDENCIES std_msgs geometry_msgs
 )

--- a/src/eland_mapping/eland_mapping/detector_node.py
+++ b/src/eland_mapping/eland_mapping/detector_node.py
@@ -69,7 +69,7 @@ from sensor_msgs.msg import Image
-from eland_msgs.msg import DynamicObstacleArray, LandingCandidate
+from eland_msgs.msg import DynamicObstacleArray, GoruntuKapsami, LandingCandidate
@@ -114,6 +114,10 @@ class DetectorNode(Node):
         self.declare_parameter('candidate_topic', '/eland/candidate')
+        # rho at mask rate on its own topic. Off by default; the candidate
+        # message keeps carrying it at decision rate either way.
+        self.declare_parameter('publish_rho', False)
+        self.declare_parameter('rho_topic', '/eland/rho')
@@ -300,6 +304,10 @@ class DetectorNode(Node):
         self.candidate_pub = self.create_publisher(
             LandingCandidate,
             self.get_parameter('candidate_topic').value, DECISION_QOS)
+        self.rho_pub = None
+        if self.get_parameter('publish_rho').value:
+            self.rho_pub = self.create_publisher(
+                GoruntuKapsami, self.get_parameter('rho_topic').value, SENSOR_QOS)
@@ -376,6 +384,12 @@ class DetectorNode(Node):
         self.have_mask = True
+        if self.rho_pub is not None:
+            out = GoruntuKapsami()
+            out.header = msg.header          # the mask's capture stamp
+            out.rho = float(self.area_ratio)
+            out.view_bounded = bool(self.view_bounded)
+            self.rho_pub.publish(out)

--- a/src/eland_mode/include/emergency_landing_mode.hpp
+++ b/src/eland_mode/include/emergency_landing_mode.hpp
@@ -477,7 +477,8 @@ (COMMIT)
-        const float touchdown_speed = descentSpeed(altitude_m);
+        const float touchdown_speed =
+            _commit_irtifa_yasasi ? commitAltitudeSpeed(altitude_m) : descentSpeed(altitude_m);
@@ -546,6 +547,12 @@ (declareParameters)
     _veri_kipi = _node.declare_parameter<bool>("veri_toplama_kipi", false);
+    // In COMMIT, take the speed from the altitude law alone. The default
+    // (false) keeps descentSpeed(), whose area branch runs on the ratio
+    // frozen at COMMIT entry: entered high with view_bounded, that held the
+    // speed flat to the ground (3 of 218 data episodes touched down at
+    // 1.10-1.33 m/s).
+    _commit_irtifa_yasasi = _node.declare_parameter<bool>("commit_irtifa_yasasi", false);
@@ -617,6 +624,22 @@ (descentSpeed'in arkası)
+  /// COMMIT with commit_irtifa_yasasi: descentSpeed()'s altitude branch,
+  /// whatever view_bounded was when COMMIT froze the candidate. Same gain,
+  /// floor and ceiling; no new constants.
+  float commitAltitudeSpeed(float altitude_m)
+  {
+    const float ceiling =
+        _have_area_measurement
+            ? std::clamp(_descent_size_gain * std::sqrt(_area_m2), _descent_min_mps, _descent_max_mps)
+            : _descent_max_mps;
+    _area_law_active = false;
+    _last_ceiling_mps = ceiling;
+    _last_commanded_mps =
+        std::clamp(_descent_altitude_gain * altitude_m, _descent_min_mps, ceiling);
+    return _last_commanded_mps;
+  }
@@ -835,6 +858,7 @@ (üyeler)
   bool _veri_kipi{false};
+  bool _commit_irtifa_yasasi{false};

--- a/src/eland_sim/config/eland_params.yaml
+++ b/src/eland_sim/config/eland_params.yaml
@@ detector_node
     candidate_topic: "/eland/candidate"
+    # rho and view_bounded at mask rate (~10 Hz) on rho_topic, one
+    # eland_msgs/GoruntuKapsami per mask with the mask's capture stamp. The
+    # candidate keeps carrying them at decision rate (~1.8 Hz) either way.
+    # Nothing in the flight stack subscribes to it yet (the data recorder does).
+    publish_rho: false
+    rho_topic: "/eland/rho"
@@ emergency_landing_mode
     descent_altitude_gain: 0.35
+    # COMMIT speed from the altitude law alone,
+    #   v = clamp(descent_altitude_gain * altitude, descent_min_mps, v_ceiling)
+    # instead of the law above, whose area branch runs on the ratio frozen at
+    # COMMIT entry. false = the old behaviour.
+    commit_irtifa_yasasi: false
```

**Açmak için:** iki parametre de düğüm başlarken okunur; çalışırken
`ros2 param set` etkisizdir.
- Ya `src/eland_sim/config/eland_params.yaml`'da `true` yapılır,
- ya da veri araçlarıyla geçersiz kılınır:

```bash
tools/veri/kosu.sh 1 kol0 veri_w3 detector_node.publish_rho=true emergency_landing_mode.commit_irtifa_yasasi=true
```

**Doğrulama araçları** (yeni, mevcut koda dokunmuyor):
- [`tools/veri/tur3_dogrula.py`](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/tools/veri/tur3_dogrula.py).
- `tools/veri/kaydedici.py`: `/eland/rho` → `rho_yayini.csv` ve
  `rho_yayini_sayisi`.
- `tools/veri/kosu.sh`: `DUGUM_BILGI=1`, bölüm ortasında grafik görüntüsü.

---

## Senden istediğim

1. **Mod `/eland/rho`'yu kullanacaksa:** ayrı maddeyi tarif et (dediğin
   gibi). Yayın artık var: ~10 Hz, yakalamadan p50 ~20 ms, p90 ~40 ms.
2. **B'nin varsayılanı:** `commit_irtifa_yasasi` şimdilik `false`.
   Açılması senin kararın; açılırsa kapalıyken koşulan karşılaştırma
   yeniden yapılır.
3. **W5 tipi yükseltilmiş hedef:** B, EKF yüksekliğine dayandığı için orada
   da yüksek hız verir. Bu açık bir soru olarak kalıyor.
4. **Kurallar aynı:** mevcut koda dokunan her şey onaylı, parametreyle,
   varsayılan kapalı.
