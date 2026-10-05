# Geri bildirim (Tur 3, ayrıntılı) — kontrolcü tasarımı için yapılanlar

> **Bu metin ne:** Kontrolcü tasarımı için Tur 3'te beş madde istedin (A-E).
> Önce planları ve çevrimdışı sonuçları gönderdim. Sen A ve B'yi onayladın.
>
> Kararların:
> 1. A: yeni `GoruntuKapsami` mesajı, `publish_rho` varsayılan false.
> 2. B: tavan donmuş alandan.
> 3. İki parametre `false` olarak `eland_params.yaml`'a.
> 4. Mod `/eland/rho`'yu şimdilik kullanmasın.
> 5. Ek ölçüm yok.
>
> Doğrulama isteğin: B'de ayar başına ≥ 5 tohum, temas hızının ortancası ve
> en büyüğü; kapalıyken eski davranış koşuyla.
>
> Bu metin Tur 3'ün tamamını tek yerde topluyor: ne yapıldı, nasıl
> doğrulandı, ne ölçülemedi, kod, dosya ve etiket dizini. Kısa sonuç raporu
> ayrıca `docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR3_SONUC.md`'de; bu metin onun
> ayrıntılı hâli.
>
> - **Tarih:** 2026-10-04.
> - **Kod (açık depo):** <https://github.com/adakarda/slz-safelanding>.
>   - Uygulama: etiket `v5.7-rho-yayini-commit-irtifa` (commit
>     [`34b6b3a`](https://github.com/adakarda/slz-safelanding/commit/34b6b3a)).
> - **Veri ve koşular GitHub'da değil:** bu makinede, `~/eland_veri/`.
> - **Etiketler:** **ölçülen**, **_hesap** (ölçülenden ya da geometriden
>   hesaplanan), **_tahmin** (varsayım içeren).
> - **İş tanımı:** en sondaki "Senden istediğim" bölümünü yanıtla.

---

## 0. Kısa özet

1. **ρ'nun 10 Hz ayrı yayını (A) var, varsayılan kapalı.**
   - Açıkken `/eland/rho`: her maskede bir mesaj; ~10 Hz (ölçülen 9.79-10.00).
   - Yakalamadan alıma p50 19.5 ms, p90 39.6 ms; dedektörün eklediği p50 0.9 ms.
   - Mod henüz dinlemiyor.
2. **COMMIT irtifa yasası (B) var, varsayılan kapalı.** Zorlanmış erken
   COMMIT'te, 5 tohum × 2 ayar, temas hızı ortanca / en büyük:
   - kapalı: **1.20 / 1.22 m/s**,
   - açık: **0.30 / 0.31 m/s**.
3. **Kapalıyken eski davranış koşuyla gösterildi.**
   - 6 Kol 0 bölümünün ölçüleri kayıtlı bölümlerin yayılımı içinde.
   - Tek fark (W3 t2'de APPROACH atlanması) eski sürümde de 20 bölümde 11 kez
     olmuş.
4. **Çevrimdışı kısım (C, D, E):** Aşama 5 bozucularının uygulandığı
   doğrulandı, eğiklik-ρ ilişkisi çıkarıldı, örnek MATLAB seti hazır.
5. **Toplanmış veri hâlâ geçerli.** Mevcut 218 bölüm eski davranışla
   kaydedildi; yeni sürüm varsayılanlarla aynı davranıyor.
6. **Açık konular:** modun `/eland/rho`'yu kullanması, B'nin varsayılanı, W5
   tipi yükseltilmiş hedef (§8).

---

## 1. Tur 3'ün akışı

| Madde | İsteğin | Yapılan | Durum |
|---|---|---|---|
| A | ρ, view_bounded ve yakalama damgası maske hızında ayrı konudan; aday mesajına dokunma; parametreyle, varsayılan kapalı; hız ve gecikme raporu | yeni mesaj + dedektörde koşullu yayın; ölçüldü | **yapıldı, doğrulandı** (`v5.7`) |
| B | `commit_irtifa_yasasi` (false); COMMIT'te donmuş ρ yerine `clamp(alt_gain · h, min, tavan)`; mevcut parametrelerle | modda ayrı yardımcı + seçim; 5+5 tohum ve K3 tekrarları | **yapıldı, doğrulandı** (`v5.7`) |
| C | Aşama 5 titreme kontrolü, yalnız sayılar | `tools/veri/bozucu_dogrula.py` | **yapıldı** (`v5.5`) |
| D | eğiklik ve ρ − ρ_hesap; merkez güvensizken ρ = 0 oranı | `tools/veri/egiklik_rho.py` | **yapıldı** (`v5.5`) |
| E | küçük örnek MATLAB seti, sözlükle | `tools/veri/ornek_mat.py` | **yapıldı** (`v5.5`) |

---

## 2. Kontrolcü için yeni sinyal: `/eland/rho` (A)

### 2.1 Ne yayınlanıyor

| | |
|---|---|
| Mesaj | `eland_msgs/msg/GoruntuKapsami` (yeni; mevcut mesajlar değişmedi) |
| Alanlar | `std_msgs/Header header`, `float32 rho`, `bool view_bounded` |
| `header.stamp` | **maskenin yakalama damgası** (sim zamanı, Gazebo'nun kareyi işlediği an); `frame_id` maskeninki |
| `rho` | görüntü merkezinin altındaki 8-bağlı güvenli bölgenin piksel payı, 0..1 (aday mesajındaki `area_ratio` ile aynı tanım ve aynı hesap) |
| `view_bounded` | bölge hiçbir kare kenarına değmiyor; ρ ancak o zaman yakınlık bilgisi taşır |
| Merkez güvensizse | `rho = 0`, `view_bounded = false` (dedektörün mevcut kuralı) |
| Konu | `rho_topic`, varsayılan `/eland/rho` |
| QoS | `SENSOR_QOS`: BEST_EFFORT, VOLATILE, KEEP_LAST 1. RELIABLE bir abone bu yayıncıyla eşleşmez |
| Hız | maske hızı; ölçülen ~10 Hz |
| Aday mesajı | değişmedi; ρ'yu karar hızında (~1.8 Hz) taşımaya devam ediyor |

### 2.2 Nasıl açılır

`detector_node.publish_rho` düğüm başlarken okunur; çalışırken `ros2 param set`
etkisizdir.
- Ya `src/eland_sim/config/eland_params.yaml`'da `true` yapılır,
- ya da veri araçlarıyla geçersiz kılınır:
  `tools/veri/kosu.sh 1 kol0 veri_w2 detector_node.publish_rho=true`.

### 2.3 Ölçülen (Kol 0, W2, tohum 1-3, açık)

| Bölüm | Mesaj / maske | Hız tüm / VALIDATE | Yakalama → `/eland/rho` alma, p50 / p90 | Maske alma → `/eland/rho` alma, p50 / p90 | ρ farkı (yayın − kaydedici), en büyük | view_bounded uyuşmayan | Uçuş (durum dizisi) |
|---|---|---|---|---|---|---|---|
| t1 | 494 / 494 | 10.00 / 9.99 Hz | 19.5 / 41.2 ms | 0.9 / 1.4 ms | 0.000001 | 0 | kayıtlıyla aynı |
| t2 | 424 / 424 | 9.79 / 9.87 Hz | 19.5 / 40.1 ms | 0.9 / 1.4 ms | 0.000001 | 0 | aynı |
| t3 | 427 / 427 | 9.95 / 9.86 Hz | 19.3 / 38.8 ms | 0.9 / 1.4 ms | 0.000001 | 0 | aynı |

**Üçü birlikte:** yakalama → alma p50 19.5 ms, p90 39.6 ms; dedektörün eklediği
p50 0.9 ms, p90 1.4 ms.

**Yöntem:**
- Kaydedici `/eland/rho`'yu dinleyip `rho_yayini.csv`'ye yazıyor: alma
  zamanı (sim), yakalama damgası, ρ, view_bounded.
- Maske tablosuyla (`maske_olaylari.csv`) yakalama damgasından eşlendi;
  mesajların hepsi eşlendi.
- "Maske alma → rho alma", kaydedicinin aynı maskeyi ve aynı karenin ρ'sunu
  alması arasındaki fark: dedektörün kare başına eklediği süre.
- ρ farkı 1e-6: CSV'nin 6 anlamlı basamak yuvarlaması.

**Ölçülemeyen:**
- Alma zamanları kaydedicinin saatiyle. Dedektörün gönderme anı ayrıca
  ölçülmedi.
- Açık bölümde `ros2 node info /detector_node` (`--no-daemon`) düğümü
  bulamadı. Yayıncı bilgisi `ros2 topic info /eland/rho -v`'den:
  `Publisher count: 1`, düğüm `detector_node`, BEST_EFFORT.

**Bugünkü sonuç:** ρ yakalamadan ~20 ms sonra (p90 ~40 ms), 10 Hz'de
alınabiliyor. Modun bugünkü yolu (aday mesajı) ~1.8 Hz.

### 2.4 Kod

```diff
+++ src/eland_msgs/msg/GoruntuKapsami.msg (yeni)
+std_msgs/Header header   # stamp = the mask's capture stamp
+float32 rho              # safe-region pixel share under the image centre, 0..1
+bool view_bounded        # region does not touch the frame edge

+++ src/eland_msgs/CMakeLists.txt
   "msg/DynamicObstacleArray.msg"
+  "msg/GoruntuKapsami.msg"

+++ src/eland_mapping/eland_mapping/detector_node.py
-from eland_msgs.msg import DynamicObstacleArray, LandingCandidate
+from eland_msgs.msg import DynamicObstacleArray, GoruntuKapsami, LandingCandidate
 ...
+        self.declare_parameter('publish_rho', False)
+        self.declare_parameter('rho_topic', '/eland/rho')
 ...
+        self.rho_pub = None
+        if self.get_parameter('publish_rho').value:
+            self.rho_pub = self.create_publisher(
+                GoruntuKapsami, self.get_parameter('rho_topic').value, SENSOR_QOS)
 ...  (on_mask sonu)
         self.have_mask = True
+        if self.rho_pub is not None:
+            out = GoruntuKapsami()
+            out.header = msg.header          # the mask's capture stamp
+            out.rho = float(self.area_ratio)
+            out.view_bounded = bool(self.view_bounded)
+            self.rho_pub.publish(out)
```

Bağlantı:
[`detector_node.py:387-392`](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_mapping/eland_mapping/detector_node.py#L387-L392),
[`GoruntuKapsami.msg`](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_msgs/msg/GoruntuKapsami.msg).

---

## 3. COMMIT irtifa yasası (B)

### 3.1 Sorun (Tur 2 verisinden, ölçülen)

- **218 bölümde 9 erken COMMIT** (COMMIT'e > 3 m'de giriş), **3'ü sert**:
  1.10, 1.27, 1.33 m/s; COMMIT 6.8-14.6 m'de.
- **Mekanizma** (`emergency_landing_mode.hpp`, `v5.6`):
  - COMMIT yeni aday dinlemiyor (`:622-623`), `_area_ratio` ve
    `_view_bounded` girişteki değerde donuyor.
  - `descentSpeed` (`:593-618`) `view_bounded` doğruysa alan dalını
    çalıştırıyor: `tavan · (1 − ρ_donmuş)`. Hız irtifadan bağımsız sabit
    kalıyor ve yere kadar öyle gidiyor.
  - Diğer 6 erken COMMIT'te `view_bounded` yanlıştı; irtifa dalı çalıştı ve
    temas 0.30 m/s oldu.

### 3.2 Değişiklik

- **Parametre:** `emergency_landing_mode.commit_irtifa_yasasi`, bool,
  varsayılan `false`; düğüm başlarken okunur.
- **Açıkken COMMIT hızı:**
  - `v = clamp(descent_altitude_gain · h_ekf, descent_min_mps, tavan)`.
  - `tavan = clamp(descent_size_gain · √area_m2, descent_min_mps, descent_max_mps)`;
    alan ölçümü yoksa `descent_max_mps`.
  - Bu, `descentSpeed`'in irtifa dalının aynısı; yalnız `view_bounded`'a
    bakılmıyor.
- **Yeni sabit yok.** Bugünkü değerler: `descent_altitude_gain` 0.35,
  `descent_min_mps` 0.3, `descent_size_gain` 0.20, `descent_max_mps` 1.5.
- **`/eland/state` doğru gösteriyor:** açıkken `area_law_active = false`,
  komut ve tavan da güncelleniyor.
- **Kapalıyken:** COMMIT satırı eski çağrının aynısı, `descentSpeed(h)`.

### 3.3 Hız-irtifa profili (_hesap, bugünkü parametrelerle)

| COMMIT'e giriş | Kapalı (eski) | Açık (yeni) |
|---|---|---|
| 10 m, bölge kadraja sığıyor (W3, ρ_donmuş ≈ 0.2) | sabit `1.5 · (1 − 0.21)` ≈ 1.19 m/s, yere kadar | 1.5 m/s'den başlar; h < 4.29 m'de `0.35 · h`; h < 0.86 m'de 0.3 |
| 2 m (normal), bölge kadraja sığmıyor | `0.35 · h`: 0.7 → 0.3 | aynı |

- **2 m'de bölge çoğu sitede kadraja sığmıyor.** 4×4 m'lik bir bölge ancak
  2.25 m'nin üstünde sığar (brif §6). Bu yüzden normal COMMIT'te iki ayar aynı
  davranır (_hesap).
- **Ölçülen karşılığı:** K3 tekrarlarında normal devirle (~2.4 m) giren
  bölümlerin hepsi iki ayarda da 0.29-0.30 m/s ile indi (§3.4).

### 3.4 Ölçülen

**Zorlanmış erken COMMIT** (istenen ≥ 5 tohum):
- **Senaryo:** sert temaslar rastlantıyla oluyordu (aday 3 kez kaybolunca).
  Erken COMMIT mevcut bir parametreyle zorlandı: yalnız bu test için
  `landing_altitude: 10.0`.
- W3 (10×10 m ada); kayıtlı veride bölge 10-16 m'de %100 kadraja sığıyor.
- Kalkış 18 m, tohum 1-5, her tohum iki ayarla.

| Ayar | Bölüm | COMMIT h_gerçek | COMMIT'te alan yasası | v_cmd: giriş → temastan önce | Temas hızı ortanca / **en büyük** / en küçük |
|---|---|---|---|---|---|
| kapalı | 5 | 10.06-10.16 m | %100 | 1.18-1.19 → 1.18-1.19 m/s (sabit) | **1.20 / 1.22 / 1.18 m/s** |
| açık | 5 | 10.02-10.16 m | %0 | 1.50 → 0.30 m/s | **0.30 / 0.31 / 0.30 m/s** |

**Bölüm bölüm temas hızı:** kapalı 1.20, 1.22, 1.18, 1.19, 1.20; açık 0.30,
0.31, 0.30, 0.30, 0.30 m/s. 10/10 başarılı; başarı ölçütü hız içermiyor.

**Sert temaslı 3 K3 bölümü, aynı politika tohumuyla yeniden:**

| Ayar | Bölüm | COMMIT h_gerçek | Alan yasası | Temas | İlk uçuşta |
|---|---|---|---|---|---|
| kapalı | k3_carpan_veri_ada_t2029_t2 | 2.47 m (normal devir) | %0 | 0.30 m/s | 1.10 |
| kapalı | k3_parca_veri_ada_t2024_t2 | 2.36 m (normal devir) | %0 | 0.29 | 1.33 |
| kapalı | k3_parca_veri_ada_t2029_t1 | **13.94 m (erken)** | %100 | **1.27** | 1.27 |
| açık | k3_carpan_veri_ada_t2029_t2 | 2.45 m (normal devir) | %0 | 0.29 | 1.10 |
| açık | k3_parca_veri_ada_t2024_t2 | **14.31 m (erken)** | %0 | **0.30** | 1.33 |
| açık | k3_parca_veri_ada_t2029_t1 | **14.66 m (erken)** | %0 | **0.30** | 1.27 |

- **Erken COMMIT rastlantıya bağlı tekrarlıyor:** kapalıda 3'te 1, açıkta
  3'te 2.
- **Kapalıyken** erken giren bölüm ilk uçuştakiyle aynı hızda (1.27 m/s) yere
  vurdu.
- **Açıkken** erken giren ikisi 0.30 m/s ile indi.

### 3.5 Bilinen sınır

`h_ekf` kalkış noktasına göre. W5 gibi yükseltilmiş hedefte platformun üstünde
~4 m gösterir; irtifa yasası orada da ~1.4 m/s verir. Tur 2'de W5 Kol 0
temasları 1.47 m/s idi. **B bunu çözmez.**

### 3.6 Kod

```diff
+++ src/eland_mode/include/emergency_landing_mode.hpp
@@ COMMIT
-        const float touchdown_speed = descentSpeed(altitude_m);
+        const float touchdown_speed =
+            _commit_irtifa_yasasi ? commitAltitudeSpeed(altitude_m) : descentSpeed(altitude_m);
@@ declareParameters()
+    _commit_irtifa_yasasi = _node.declare_parameter<bool>("commit_irtifa_yasasi", false);
@@ descentSpeed()'in arkası
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
@@ üyeler
+  bool _commit_irtifa_yasasi{false};
```

Bağlantı:
[COMMIT seçimi `:480-481`](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_mode/include/emergency_landing_mode.hpp#L480-L481),
[`commitAltitudeSpeed` `:627-641`](https://github.com/adakarda/slz-safelanding/blob/v5.7-rho-yayini-commit-irtifa/src/eland_mode/include/emergency_landing_mode.hpp#L627-L641).
`eland_params.yaml`'da iki satır, ikisi de `false`, açıklamalarıyla.

---

## 4. "Kapalıyken eski davranış" — koşuyla

Yeni sürüm, iki parametre varsayılan (`false`), Kol 0. Kayıtlı bölümlerle aynı
dünya ve tohum:

| Bölüm | Durum dizisi | COMMIT h_ekf kayıtlı / yeni | COMMIT h_gerçek kayıtlı / yeni | Temas kayıtlı / yeni | VALIDATE→landed kayıtlı / yeni | `/eland/rho` mesajı |
|---|---|---|---|---|---|---|
| kol0_veri_w2_t1 | aynı | 1.95 / 1.98 m | 1.99 / 2.03 m | 0.31 / 0.29 m/s | 25.6 / 26.2 s | 0 |
| kol0_veri_w2_t2 | aynı | 1.93 / 1.97 | 1.98 / 1.99 | 0.30 / 0.29 | 22.1 / 21.9 | 0 |
| kol0_veri_w2_t3 | aynı | 1.96 / 1.98 | 1.99 / 2.07 | 0.30 / 0.31 | 22.9 / 22.9 | 0 |
| kol0_veri_w3_t1 | aynı | 1.97 / 1.94 | 2.04 / 2.09 | 0.30 / 0.31 | 23.0 / 23.0 | 0 |
| kol0_veri_w3_t2 | **farklı**: SEARCH→VALIDATE (kayıtlıda SEARCH→APPROACH→VALIDATE) | 1.93 / 1.95 | 2.03 / 2.01 | 0.30 / 0.31 | 19.8 / 19.5 | 0 |
| kol0_veri_w3_t3 | aynı | 1.95 / 1.94 | 2.05 / 1.99 | 0.31 / 0.31 | 19.7 / 19.9 | 0 |

- **SITL bit bit tekrarlanmıyor.** "Aynı" demek aynı durum dizisi ve kayıtlı
  değerlerin yayılımı içinde kalan ölçümler.
- **W3 t2'deki fark:** eski sürümle kaydedilmiş 20 W3-tohum-2 bölümünde (her
  kol) APPROACH 11'inde atlanmış, 9'unda girilmiş. VALIDATE'ten önceki davranış
  koldan bağımsız.
- **Grafik** (bölüm ortasında, kapalı):
  - `ros2 topic info /eland/rho -v`: `Publisher count: 0`. Konu yalnız
    kaydedici dinlediği için görünüyor.
  - `ros2 node info /detector_node` yayıncıları: `/eland/candidate`,
    `/eland/trajectory_block`, `/parameter_events`, `/rosout`.
- **B kapalıyken eski davranış ayrıca:** zorlanmış testin "kapalı" kolu eski
  donmuş-ρ davranışını aynen gösterdi (§3.4, hız 1.18-1.19 m/s'de sabit).

---

## 5. Doğrulama nasıl yapıldı

- **Derleme:** `colcon build --packages-select eland_msgs eland_mapping eland_mode`,
  uyarısız.
  - Önce kurulu dosyaların kaynakla birebir aynı olduğu kontrol edildi;
    derleme yalnız A ve B'yi taşıyor.
  - Derleme sonrası kontrol: `ros2 interface show eland_msgs/msg/GoruntuKapsami`;
    kurulu dedektörde yeni satırlar; mod ikilisinde parametre adı.
- **Koşu aracı:** `tools/veri/kosu.sh`. Bölüm başına sim + kaydedici, sonra
  temizlik.
- **Koşular (26 bölüm):**
  - Kapalı: Kol 0 W2 / W3 × 3.
  - A açık: W2 × 3.
  - B: 5 tohum × 2 ayar.
  - K3 tekrarları: 3 × 2.
  - Hepsi veri setinin dışında, `~/eland_veri/_tur3_dogrulama/`.
  - 1 bölümde (K3 tekrarı, kapalı, `t2029_t2`) PX4 kalkmadı ("irtifa 0 m",
    mod devreye girmedi). O bölüm bir kez yeniden uçuruldu; ilk deneme
    `_basarisiz/` altında.
- **Yeni yardımcılar** (mevcut koda dokunmuyor):
  - `tools/veri/kaydedici.py`: `/eland/rho` → `rho_yayini.csv`,
    `ep_ozet.json`'da `rho_yayini_sayisi`.
  - `tools/veri/kosu.sh`: `DUGUM_BILGI=1`, bölüm ortasında `ros2 topic info`
    ve `ros2 node info` görüntüsü.
  - `tools/veri/tur3_dogrula.py`: §2-4'teki tabloları üretir.
- **Tablolar:** `~/eland_veri/_tur3/tur3_dogrula.md`; ayrıca
  `docs/VERI_TOPLAMA.md`, "A ve B — uygulandı".

---

## 6. Çevrimdışı kısım (C, D, E) — kısa

Ayrıntı `docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR3.md` ve `docs/VERI_TOPLAMA.md`
"Tur 3".

- **C — bozucular uygulanmış.** VALIDATE'te `rho_bozuk − rho_temiz`:

  | Bozucu | d ≠ 0 kare oranı | ort \|d\| |
  |---|---|---|
  | sınır titremesi | %88-99 | 0.0004 |
  | %2 çevirme | %100 | 0.007-0.018 |
  | kayıp | %3-8 | 0.009-0.034 |
  | tekrar | %62-66 | 0.006-0.010 |
  | 0.2 s gecikme | 0 (içerik aynı, 203 ms geç) | 0 |

  Çevrimiçi bozuk maskelerin kendisi kaydedilmemiş; piksel sayımı bozucunun
  kendi koduyla kayıtlı temiz karelere uygulandı.
- **D — eğiklik ve ρ, VALIDATE:**

  | | Eğiklik < 5° | Eğiklik ≥ 5° |
  |---|---|---|
  | K1, ρ − ρ_hesap ort / RMS | +0.0003 / 0.0015 | +0.012 / 0.020 (göreli +%3.4) |
  | K3, ρ − ρ_hesap ort / RMS | −0.0002 / 0.0019 | +0.002 / 0.010 (göreli +%2.8) |

  - **≥ 5° kare oranı:** K1 %1.3, K3 %8.4.
  - **Merkez güvensiz ve ρ = 0, VALIDATE'te:** bölümlerin ortancası 0.
    Oranı > 0 olan 24 bölümün 12'si W5; W5'te veri kipi devretmediği için mod
    temastan sonra da VALIDATE'te kalıyor ve bu kareler temastan sonra.
- **E — örnek MATLAB seti:**
  - **İçerik:** 6 bölüm (K5 ×2, K1 0.7 / 1.5, K2 D* = 0.2, Aşama 5 gecikme),
    2.6 MB zip.
  - **Yer:** bu makinede `~/eland_veri/_ornek_matlab/` ve kullanıcının
    `Downloads\ornek_matlab.zip`.
  - **Doğrulama:** Python'da geri okunup CSV ile karşılaştırıldı.
    **MATLAB'da açılmadı.**

---

## 7. Dosya ve etiket dizini

| Etiket | İçerik |
|---|---|
| [`v5.0-veri-kipi`](https://github.com/adakarda/slz-safelanding/tree/v5.0-veri-kipi) | O1 (`--world` / `--model`), O2 (`veri_toplama_kipi`), politika ve bozucu düğümleri |
| [`v5.1-veri-temizlik`](https://github.com/adakarda/slz-safelanding/tree/v5.1-veri-temizlik) | bölüm sonu artık süreç temizliği (sızıntı olayı sonrası) |
| [`v5.2-ruzgar-kalibrasyon`](https://github.com/adakarda/slz-safelanding/tree/v5.2-ruzgar-kalibrasyon) | rüzgâr ölçeği (gz karesini alıyor), etkin 0.075 |
| [`v5.3-veri-tur2`](https://github.com/adakarda/slz-safelanding/tree/v5.3-veri-tur2) | Tur 2 toplama tamam, 218 bölüm; doğuş düzeltmesi |
| [`v5.4-veri-geri-bildirim-tur2`](https://github.com/adakarda/slz-safelanding/tree/v5.4-veri-geri-bildirim-tur2) | Tur 2 geri bildirim promptu |
| [`v5.5-tur3-cevrimdisi`](https://github.com/adakarda/slz-safelanding/tree/v5.5-tur3-cevrimdisi) | C, D, E araçları |
| [`v5.6-veri-geri-bildirim-tur3`](https://github.com/adakarda/slz-safelanding/tree/v5.6-veri-geri-bildirim-tur3) | Tur 3 geri bildirimi (planlar) |
| [`v5.7-rho-yayini-commit-irtifa`](https://github.com/adakarda/slz-safelanding/tree/v5.7-rho-yayini-commit-irtifa) | **A ve B uygulaması + doğrulama araçları** |
| [`v5.8-veri-geri-bildirim-tur3-sonuc`](https://github.com/adakarda/slz-safelanding/tree/v5.8-veri-geri-bildirim-tur3-sonuc) | Tur 3 kısa sonuç raporu |
| `v5.9-veri-geri-bildirim-tur3-ayrintili` | bu metin |

**Belgeler:**
- `docs/KONTROLCU_TASARIM_BRIEF.md`: brif.
- `docs/VERI_TOPLAMA.md`: canlı rapor, bütün tablolar.
- `docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR2.md`: veri, tesis, kollar.
- `tools/veri/data_dictionary.md`: sütun sözlüğü (`rho_yayini.csv` dahil).

---

## 8. Açık konular

1. **Mod `/eland/rho`'yu kullanmıyor** (kararın). Kullanacaksa ayrı madde ve
   ayrı parametre (varsayılan kapalı).
   - Bilmen gerekenler: abone BEST_EFFORT olmalı; damga yakalama anı (bayatlık
     ondan ölçülür); geçerlilik bayrağı `view_bounded`.
2. **B'nin varsayılanı `false`.** Açılırsa uçuş davranışı yalnız COMMIT'e
   `view_bounded` doğruyken girildiğinde değişir; normal 2 m COMMIT'te aynı
   (§3.3).
3. **W5 tipi yükseltilmiş hedef:** irtifa yasası EKF yüksekliğiyle çalıştığı
   için orada sert temas sürüyor (1.47 m/s, Tur 2). Hedef yüzeye göre
   yükseklik kestirimi gerekiyor.
4. **Tur 2'den kalan:** K2'de sabit ıraksama pencereleri kısa (D* = 0.5'te
   0.4 s). Devir irtifası 2.5 m'de.
5. **Başarı ölçütünde temas hızı eşiği yok.** 6 sert temas "başarılı"
   sayılıyor (W5 Kol 0 ×3, K3 ×3).

---

## Senden istediğim

1. **`/eland/rho` ile görüntü-tabanlı dış döngü:** ölçülen ~10 Hz / p90
   ~40 ms ile tasarımın örnekleme ve gecikme varsayımlarını güncelle. Modun
   konuyu kullanacağı maddeyi brif §12 biçiminde tarif et: girdiler, ayrık
   denklemler, parametreler, kip geçişleri, sıfırlama, doyum, kabul ölçütü.
2. **B:** `commit_irtifa_yasasi` varsayılan kalsın mı, açılsın mı? Açılacaksa
   hangi koşullarla yeniden doğrulayayım?
3. **W5 / yükseltilmiş hedef:** nasıl ele alınacak? Örnekler: görüntüden ya
   da haritadan hedef yüksekliği, ya da bu senaryonun kapsam dışı bırakılması.
4. **Başarı ölçütü:** temas hızı eşiği eklensin mi (ör. ≤ 0.5 m/s)?
   Eklenirse mevcut veri yeniden puanlanır, yeni koşu gerekmez.
5. **Kurallar aynı:** mevcut koda dokunan her şey onaylı, parametreyle,
   varsayılan kapalı; kapalıyken eski davranış koşuyla gösterilecek.
