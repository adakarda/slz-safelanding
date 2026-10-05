# Geri bildirim (Tur 3) — kontrolcü tasarımı için eksikler: yapılanlar ve planlar

> **Bu metin ne:** Tur 3'te bana beş madde verdin (A-E). Kod projede Claude
> Code tarafından yazıldı. Aşağıda her madde için durum, nasıl doğrulandığı,
> ölçülemeyenler ve yazılan kod var.
>
> | Madde | Durum |
> |---|---|
> | C, D, E | çevrimdışı işler, **yapıldı** |
> | A, B | mevcut koda dokunuyor; **yalnız plan ve önerilen kod**, uygulanmadı, **onayını bekliyor** |
>
> - **Tarih:** 2026-10-04.
> - **Kod (açık depo):** <https://github.com/adakarda/slz-safelanding>.
>   - C, D, E: etiket
>     [`v5.5-tur3-cevrimdisi`](https://github.com/adakarda/slz-safelanding/tree/v5.5-tur3-cevrimdisi).
>   - A/B planı:
>     [`03b161e`](https://github.com/adakarda/slz-safelanding/commit/03b161e).
>   - Bu dosya: `v5.6-veri-geri-bildirim-tur3`.
> - **Veri GitHub'da değil:** çıktılar bu makinede, `~/eland_veri/_tur3/` ve
>   `~/eland_veri/_ornek_matlab/`.
> - **Etiketler:** **ölçülen**, **_hesap** (ölçülenden hesaplanan),
>   **_tahmin** (varsayım içeren).
> - **İş tanımı:** en sondaki "Senden istediğim" bölümünü yanıtla.

---

## 1. Özet

| Madde | Durum | Doğrulama | Ölçülemeyen |
|---|---|---|---|
| A — ρ'nun 10 Hz ayrı yayını | **onay bekliyor** (plan + önerilen kod §5) | uygulanınca: kapalı / açık koşu, yayın hızı, gecikme p50 / p90 | henüz hiçbir şey ölçülmedi |
| B — COMMIT irtifa yasası | **onay bekliyor** (plan + önerilen kod §6) | uygulanınca: kapalı / açık koşu, zorlanmış erken COMMIT | henüz hiçbir şey ölçülmedi |
| C — Aşama 5 titreme kontrolü | **yapıldı** | 20 bölümün kaydı; piksel sayımı kayıtlı temiz karelerde | çevrimiçi bozuk maskeler kaydedilmemiş (§2) |
| D — eğiklik ve ρ | **yapıldı** | K1 (32) + K3 (80) kaydı | — |
| E — örnek MATLAB seti | **yapıldı** | Python'da geri okunup CSV ile karşılaştırıldı | MATLAB'da açılıp denenmedi (makinede MATLAB yok) |

---

## 2. C — Aşama 5 titreme kontrolü (yalnız sayılar)

**Araç:**
[`tools/veri/bozucu_dogrula.py`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/tools/veri/bozucu_dogrula.py).
Tam tablo (20 bölüm, satır satır) `~/eland_veri/_tur3/bozucu_dogrula.md`.

**Kayıt düzeni:**
- Kaydedici çevrimiçi bozuk maskelerin kendisini saklamamış; yalnız
  özniteliklerini saklamış: `rho_bozuk`, `view_bounded_bozuk`,
  `t_alma_bozuk`.
- Ham olarak yalnız temiz maskeler var (`maskeler.npz`).
- Bu yüzden piksel sayımı (madde 2), bozucunun **kendi**
  [`disturb()`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/tools/veri/bozucu.py#L65-L102)
  kodu kayıtlı temiz karelere **çevrimdışı** uygulanarak yapıldı: aynı
  seviye, aynı tohum. Çevrimiçi karelerin birebiri değil.

**Yuvarlama:** Tur 2 raporundaki "sınır titremesi → ort |ρ_bozuk − ρ_temiz| =
0.000" üç ondalığa yuvarlanmış değerdi.

**1. `d = rho_bozuk − rho_temiz`** (kayıtlı, yakalama damgasıyla eşlenmiş; her
bozucuda 4 bölüm, aralıklar bölümler arası):

| Bozucu | Aralık | max \|d\| | p99 \|d\| | ort \|d\| | d ≠ 0 kare oranı |
|---|---|---|---|---|---|
| sınır 2 px | tüm kayıt | 0.00135-0.00182 | 0.00106-0.00118 | 0.00020-0.00023 | 0.475-0.555 |
| sınır 2 px | VALIDATE | 0.00104-0.00154 | 0.00095-0.00130 | 0.00036-0.00043 | 0.879-0.992 |
| çevir 0.02 | tüm kayıt | 0.887-1.000 | 0.079-0.116 | 0.0106-0.0121 | 0.681-0.751 |
| çevir 0.02 | VALIDATE | 0.098-0.875 | 0.017-0.238 | 0.0070-0.0184 | 1.000 |
| kayıp 0.05 | tüm kayıt | 1.000 | 0.809-0.999 | 0.0162-0.0219 | 0.029-0.040 |
| kayıp 0.05 | VALIDATE | 0.534-1.000 | 0.233-0.936 | 0.0092-0.0339 | 0.034-0.083 |
| gecikme 0.2 s | tüm kayıt / VALIDATE | 0 | 0 | 0 | 0 |
| tekrar 2 | tüm kayıt | 1.000 | 0.036-0.058 | 0.0097-0.0113 | 0.329-0.356 |
| tekrar 2 | VALIDATE | 0.029-0.061 | 0.029-0.057 | 0.0060-0.0100 | 0.623-0.664 |

**2. Değişen piksel** (76800 pikselden; bölüm başına VALIDATE'ten eşit
aralıklı 4 kare; çevrimdışı uygulama):

| Bozucu | Değişen piksel | Merkez bölge pikseli, temiz → bozuk |
|---|---|---|
| sınır 2 px | 0-913 (2.5 m'de kare tek sınıf: 0) | en çok 78 piksel fark |
| çevir 0.02 | her karede 1536 | 86-1286 piksel azalma |
| kayıp 0.05 | örneklenen 16 karede 0 (karelerin %5'inde tetikleniyor). Aynı kareler seviye 1.0 ile zorlanınca bölgenin tamamı: 5976-76800 | zorla: bölge → 0 |
| gecikme 0.2 s | 0 (içerik aynı, 0.2 s geç) | aynı |
| tekrar 2 | 0-2626 (tutulan karede 0) | en çok 2626 piksel fark |

**3. view_bounded = 1 oranı:**

| | Temiz | Bozuk tarafta en büyük fark |
|---|---|---|
| VALIDATE, tohum 1 bölümleri | 0.660-0.695 | −0.059 (kayıp) |
| VALIDATE, tohum 2 bölümleri | 0.355-0.494 | +0.024 (tekrar) |
| Tüm kayıt | 0.221-0.406 | |

VALIDATE'te ortanca `rho_temiz` 0.229-0.350.

**Kodun özü** (tam dosya bağlantıda):

```python
def disturber(tur, seviye, tohum):
    """bozucu.Bozucu.disturb without a ROS node around it."""
    import bozucu  # noqa: E402  (needs rclpy importable, not running)
    obj = types.SimpleNamespace(a=types.SimpleNamespace(tur=tur, seviye=seviye),
                                rng=np.random.default_rng(tohum), n_kayip=0)
    return lambda m: bozucu.Bozucu.disturb(obj, m)

# 1. kayıttan: rho_bozuk ile rho_temiz aynı yakalama damgasıyla eşlenmiş
both = np.isfinite(m['rho_bozuk']) & np.isfinite(m['rho_temiz'])
val = both & (m['t_yakalama'] >= (tv or np.inf)) & (m['t_yakalama'] <= tc)
for etiket, sel in (('tum', both), ('VALIDATE', val)):
    dd = (m['rho_bozuk'] - m['rho_temiz'])[sel]
    ad = np.abs(dd)
    rows1.append((name, etiket, int(sel.sum()), int(both.size),
                  float(ad.max()), float(np.percentile(ad, 99)),
                  float(ad.mean()), float(np.mean(dd != 0))))

# 2. kayıtlı temiz kareye aynı bozucu kodu, VALIDATE'ten eşit aralıklı kareler
pick = inval[np.linspace(0, len(inval) - 1, a.kare).astype(int)]
f = disturber(tur, seviye, tohum)
for i in pick:
    clean = masks[i]
    bad = f(clean)
    rows2.append((name, ..., int(np.count_nonzero(bad != clean)), clean.size,
                  centre_region(clean), centre_region(bad), ''))
```

---

## 3. D — eğiklik ve ρ

**Araç:**
[`tools/veri/egiklik_rho.py`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/tools/veri/egiklik_rho.py).
Çıktılar `~/eland_veri/_tur3/egiklik_rho.md`, bölüm başına
`merkez_guvensiz_rho0_bolum.csv`. Yeni toplama yapılmadı.

**Yöntem:**
- **Eğiklik:** `arccos(cos roll · cos pitch)`, gövde z ekseni ile düşey
  arası açı (kamera gövdeye sabit).
- **roll / pitch nerede:** `maske_olaylari.csv`'de **yok**. `duzenli.csv`'de
  `roll`, `pitch` var (rad, `vehicle_attitude`, 50 Hz ızgara); maskenin
  `t_yakalama`'sına doğrusal ara değerlendi.
- **Durum:** yakalama anındaki `durum`, ızgaradaki son değer (sıfırıncı
  dereceden tutma).
- **Karşılaştırılan kareler:** yalnız `rho_hesap`'ın anlamlı olduğu kareler,
  `view_bounded = 1` ve `rho > 0`.
- `rho_hesap = A_gercek / (4.22 · h_kamera_gercek²)`, seviyeli kamera için
  geometrik değer.

**ρ − ρ_hesap:**

| Kol | Aralık | Eğiklik | Kare | Ort | Ortanca | RMS | p95 \|·\| | Göreli ort / ortanca (ρ/ρ_hesap − 1) |
|---|---|---|---|---|---|---|---|---|
| K1 | tüm kayıt | < 5° | 3572 | +0.0002 | +0.0000 | 0.0014 | 0.0016 | +0.001 / +0.000 |
| K1 | tüm kayıt | ≥ 5° | 139 | +0.0079 | +0.0001 | 0.0179 | 0.0358 | +0.027 / +0.004 |
| K1 | VALIDATE | < 5° | 2472 | +0.0003 | +0.0000 | 0.0015 | 0.0017 | +0.001 / +0.000 |
| K1 | VALIDATE | ≥ 5° | 72 | +0.0123 | +0.0003 | 0.0204 | 0.0439 | +0.034 / +0.006 |
| K3 | tüm kayıt | < 5° | 7729 | −0.0004 | −0.0003 | 0.0019 | 0.0033 | −0.002 / −0.003 |
| K3 | tüm kayıt | ≥ 5° | 664 | +0.0038 | +0.0036 | 0.0121 | 0.0250 | +0.037 / +0.037 |
| K3 | VALIDATE | < 5° | 3227 | −0.0002 | −0.0001 | 0.0019 | 0.0038 | −0.000 / −0.000 |
| K3 | VALIDATE | ≥ 5° | 220 | +0.0021 | +0.0032 | 0.0098 | 0.0176 | +0.028 / +0.033 |

**VALIDATE içinde eğiklik dağılımı** (bütün kareler):

| Kol | Kare | Ortanca | p95 | En çok | ≥ 5° oranı |
|---|---|---|---|---|---|
| K1 | 5880 | 0.28° | 2.44° | 9.57° | 0.013 |
| K3 | 9802 | 0.36° | 7.89° | 43.73° | 0.084 |

**Merkez piksel güvenli değil ve ρ = 0 olan kare oranı** (bölüm başına
değerler CSV'de):

| Kol | Bölüm | Tüm kayıt, ortanca / en çok | VALIDATE, ortanca / en çok (> 0 olan bölüm) | VALIDATE ve temastan önce, en çok (> 0 olan bölüm) | Merkez güvensiz ama ρ ≠ 0 |
|---|---|---|---|---|---|
| K1 | 32 | 0.313 / 0.667 | 0.000 / 0.299 (8) | 0.043 (4) | 0 kare |
| K3 | 80 | 0.299 / 0.666 | 0.000 / 0.312 (16) | 0.221 (12) | 0 kare |

Ölçülen olgular:
1. **Kayıt kalkıştan önce, yerde başlıyor.** "Tüm kayıt" yerdeki ve
   tırmanmadaki kareleri de içeriyor.
2. **VALIDATE'te oranı > 0 olan 24 bölümün 12'si W5.** Veri kipi W5'te
   COMMIT'e devretmediği için mod temastan sonra da VALIDATE'te kalıyor.
   - Örnek `k3_carpan_veri_w5_t2`: 44 kare, hepsi temastan sonra,
     `h_kamera_gercek` 0.09 m, merkez sınıfı 2.
3. **Ada örnekleri:**
   - `k3_carpan_veri_ada_t2016_t1`: 25 kare, 7.6-14.4 m, sınıf 2.
   - `k3_parca_veri_ada_t2042_t1`: 9 kare, 11.4-12.4 m.

**Kodun özü:**

```python
t = m['t_yakalama']
roll = np.interp(t, d['t_gz'], d['roll'])
pitch = np.interp(t, d['t_gz'], d['pitch'])
tilt = np.degrees(np.arccos(np.clip(np.cos(roll) * np.cos(pitch), -1, 1)))
# state at capture: last grid value at or before t (zero-order hold)
idx = np.clip(np.searchsorted(d['t_gz'], t, side='right') - 1, 0, len(d['t_gz']) - 1)
val = d['durum'][idx] == 2
ok = (m['view_bounded'] == 1) & (m['rho'] > 0) & np.isfinite(m['rho_hesap'])
for aralik, rs in (('tum', ok), ('VALIDATE', ok & val)):
    for b, sel in (('< 5', rs & (tilt < 5)), ('>= 5', rs & (tilt >= 5))):
        fark.setdefault((grup, aralik, b), []).extend((m['rho'] - m['rho_hesap'])[sel].tolist())

unsafe = ~np.isin(m['merkez_sinif'], SAFE)      # SAFE = (0, 1)
z = unsafe & (m['rho'] == 0)
vo = val & (t < oz['t_temas_gercek'])           # VALIDATE, temastan önce
```

---

## 4. E — örnek MATLAB seti

**Araç:**
[`tools/veri/ornek_mat.py`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/tools/veri/ornek_mat.py).

**Yer:** `~/eland_veri/_ornek_matlab/`. Windows'tan
`\\wsl.localhost\ubuntu\home\arda\eland_veri\_ornek_matlab`; zip'i
`~/eland_veri/_ornek_matlab.zip`, 2.6 MB.

| Dosya | KB | duzenli (sütun × satır) | maske | karar |
|---|---|---|---|---|
| k5_A0.6_acik_alan_t1001.mat | 608 | 37 × 5023 | 22 × 951 | 12 × 177 |
| k5_A1.0_acik_alan_t1001.mat | 598 | 37 × 5014 | 22 × 923 | 12 × 175 |
| k1_v0.7_veri_w3_t1.mat | 392 | 48 × 2731 | 26 × 537 | 12 × 99 |
| k1_v1.5_veri_w3_t1.mat | 306 | 48 × 2162 | 26 × 412 | 12 × 76 |
| k2_d0.2_veri_w3_t1.mat | 353 | 48 × 2428 | 26 × 468 | 12 × 84 |
| a5_k2d0.35_veri_w3_t1_gecikme0.2.mat | 306 | 48 × 2220 | 26 × 426 | 12 × 73 |

**Seçimler:**
- **K5:** 1.2 ve 2.0 m/s basamaklı rüzgârsız tanımlama. Tur 1
  kaydedicisinden oldukları için `x_gercek` gibi sonradan eklenen sütunlar
  yok (37 sütun).
- **K2:** D* = 0.2; sabit ıraksama penceresi en uzun kol (5.6 s).
- **Aşama 5:** 0.2 s gecikme. Aynı dosyada `rho_temiz`, `rho_bozuk` ve
  `t_alma_bozuk` yan yana.

**İçerik:**
- Her `.mat` v7 ve sıkıştırılmış. Yapılar: `duzenli`, `maske`, `karar`,
  `gecis`, `bilgi` (bölüm, politika, bozucu, rüzgâr ve anlar), ayrıca
  `ozet_json` ve `kosul_yaml` metin olarak.
- **Sütun adları kaydedicininkiyle aynı.** Yalnız `duzenli`'de her satırda
  tekrar eden 4 metin sütunu (`ep_id`, `dunya_id`, `tohum`, `kol`) `bilgi`'ye
  taşındı.
- Her dosyanın yanında `<ep_id>_sozluk.md`: koşullar, anlar, okuma örneği,
  `data_dictionary.md`'den sütun tablosu. Ayrıca bir `BENIOKU.md`.

**Doğrulama:**
- Her dosya `scipy.io.loadmat` ile geri okundu; her sütunun satır sayısı ve
  NaN sayısı CSV ile aynı.
- **Denenmedi:** MATLAB'da açılmadı. Bir alan adı 31 karakteri aşıyor
  (`bilgi.temas_dikey_hiz_gercek_hesap_mps`, 32); MATLAB R2006a'dan beri 63'e
  kadar kabul ediyor.

**MATLAB'da okuma:**

```matlab
S = load('k1_v0.7_veri_w3_t1.mat');
D = S.duzenli;  M = S.maske;  K = S.karar;  B = S.bilgi;
plot(D.t_gz, D.vz_gercek_hesap, D.t_gz, D.v_cmd); xline(B.t_validate); xline(B.t_temas_gercek)
ozet = jsondecode(S.ozet_json);
```

**Kodun özü:**

```python
data = {
    'duzenli': duz_num, 'maske': msk, 'karar': kar,
    'gecis': {k: (v if v.dtype != object else v.astype(object)) for k, v in gec.items()},
    'bilgi': bilgi,
    'ozet_json': json.dumps(oz, ensure_ascii=False),
    'kosul_yaml': kosul_txt,
}
sio.savemat(mat, data, do_compression=True, oned_as='column', long_field_names=True)

# read it back: every column there, same length, same NaN count
back = sio.loadmat(mat, squeeze_me=True, struct_as_record=False)
for name, src in (('duzenli', duz_num), ('maske', msk), ('karar', kar)):
    for c, v in src.items():
        bv = np.atleast_1d(getattr(back[name], c))
        if bv.shape[0] != v.shape[0]:
            problems.append(f'{name}.{c} boy {bv.shape[0]} != {v.shape[0]}')
        elif v.dtype != object and int(np.isnan(bv.astype(float)).sum()) != int(np.isnan(v).sum()):
            problems.append(f'{name}.{c} NaN sayisi farkli')
```

Sonuç: 6 dosyanın hepsinde `problems` boş.

---

## 5. A — ρ'nun 10 Hz ayrı yayını: plan ve önerilen kod (UYGULANMADI)

**Bugün:** `detector_node.on_mask`
([`detector_node.py:340-378`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/src/eland_mapping/eland_mapping/detector_node.py#L340-L378))
ρ'yu her maskede hesaplıyor. Ama ρ moda yalnız aday mesajının içinde,
karar hızında (~1.8 Hz) gidiyor.

**Değişecek dosyalar:**
1. `src/eland_msgs/msg/GoruntuKapsami.msg` (yeni).
2. [`src/eland_msgs/CMakeLists.txt:13-19`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/src/eland_msgs/CMakeLists.txt#L13-L19):
   bir satır. Mevcut mesajlar, aday mesajı dahil, değişmiyor.
3. `src/eland_mapping/eland_mapping/detector_node.py`: içe aktarma,
   2 parametre, koşullu yayıncı, `on_mask` sonunda ~6 satır.
   - ρ hesabı ve `on_map` aynı.
   - Parametre kapalıyken yayıncı hiç oluşmuyor.
4. Ölçüm için kendi aracım `tools/veri/kaydedici.py`: konu varsa alma
   zamanlarını kaydedecek.

**Mod bu konuyu dinlemeyecek:** istek yalnız yayındı. Modun kullanması
ayrı bir madde olur, ayrı parametreyle.

**Önerilen kod:**

```text
# src/eland_msgs/msg/GoruntuKapsami.msg (yeni)
# Image-space coverage of the safe region under the image centre, one message
# per mask from detector_node when publish_rho is true. Same definitions as
# LandingCandidate.area_ratio / view_bounded, at mask rate instead of
# decision rate.
std_msgs/Header header   # stamp = the mask's capture stamp
float32 rho              # safe-region pixel share under the image centre, 0..1
bool view_bounded        # region does not touch the frame edge
```

```diff
--- a/src/eland_msgs/CMakeLists.txt
+++ b/src/eland_msgs/CMakeLists.txt
 rosidl_generate_interfaces(${PROJECT_NAME}
   "msg/LandingCandidate.msg"
   "msg/LandingState.msg"
   "msg/DynamicObstacle.msg"
   "msg/DynamicObstacleArray.msg"
+  "msg/GoruntuKapsami.msg"
   DEPENDENCIES std_msgs geometry_msgs
 )
```

```diff
--- a/src/eland_mapping/eland_mapping/detector_node.py
+++ b/src/eland_mapping/eland_mapping/detector_node.py
@@ :72, içe aktarma
-from eland_msgs.msg import DynamicObstacleArray, LandingCandidate
+from eland_msgs.msg import DynamicObstacleArray, GoruntuKapsami, LandingCandidate
@@ :116, parametreler
         self.declare_parameter('candidate_topic', '/eland/candidate')
+        # rho at mask rate on its own topic. Off by default; the candidate
+        # message keeps carrying it at decision rate either way.
+        self.declare_parameter('publish_rho', False)
+        self.declare_parameter('rho_topic', '/eland/rho')
@@ :300-302, yayıncılar
         self.candidate_pub = self.create_publisher(
             LandingCandidate,
             self.get_parameter('candidate_topic').value, DECISION_QOS)
+        self.rho_pub = None
+        if self.get_parameter('publish_rho').value:
+            self.rho_pub = self.create_publisher(
+                GoruntuKapsami, self.get_parameter('rho_topic').value, SENSOR_QOS)
@@ :378, on_mask sonu
         self.have_mask = True
+        if self.rho_pub is not None:
+            out = GoruntuKapsami()
+            out.header = msg.header          # the mask's capture stamp
+            out.rho = float(self.area_ratio)
+            out.view_bounded = bool(self.view_bounded)
+            self.rho_pub.publish(out)
```

**Alternatif:** `eland_msgs`'e hiç dokunmadan hazır
`geometry_msgs/PointStamped` (x = ρ, y = view_bounded). Daha az temiz;
tercih senin.

**Doğrulama planı (uygulandıktan sonra):**
- **Kapalıyken (varsayılan):**
  - `/eland/rho` konusu yok; `detector_node`'un yayıncı listesi
    öncekiyle aynı.
  - Kol 0 W2'nin 3 bölümü yeniden uçurulup kayıtlı
    `kol0_veri_w2_t1-t3` ile karşılaştırılacak: geçiş dizisi, COMMIT
    irtifası, temas hızı, süre.
  - SITL bit bit tekrarlanmıyor: "aynı" demek aynı geçiş dizisi ve
    kayıtlıların yayılımı içinde kalan ölçümler.
- **Açıkken (`detector_node.publish_rho: true`):** aynı 3 bölümde
  ölçülecekler:
  - yayın hızı (VALIDATE'te, Hz),
  - gecikme p50 / p90: yakalama damgasından `/eland/rho`'nun alınmasına,
    ve maskenin alınmasından `/eland/rho`'nun alınmasına (dedektörün
    eklediği),
  - yayınlanan ρ'nun aynı maskeden hesaplanan ρ ile eşitliği.

---

## 6. B — `commit_irtifa_yasasi`: plan ve önerilen kod (UYGULANMADI)

**Bugün:**
- COMMIT'te hız `descentSpeed(h_ekf)`'den geliyor
  ([`emergency_landing_mode.hpp:480-488`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/src/eland_mode/include/emergency_landing_mode.hpp#L480-L488)).
- COMMIT yeni aday dinlemiyor
  ([`:622-623`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/src/eland_mode/include/emergency_landing_mode.hpp#L620-L637)),
  bu yüzden ρ ve `view_bounded` donuyor.
- `descentSpeed`
  ([`:593-618`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/src/eland_mode/include/emergency_landing_mode.hpp#L593-L618)),
  `view_bounded` doğruysa alan dalını donmuş ρ ile çalıştırıyor:

```cpp
    _area_law_active = true;
    const float ratio = std::clamp(_area_ratio, 0.f, 1.f);
    _last_commanded_mps = std::clamp(ceiling * (1.f - ratio), _descent_min_mps, ceiling);
    return _last_commanded_mps;
```

**Değişecek dosya:** yalnız `src/eland_mode/include/emergency_landing_mode.hpp`.

**Yasa:** `v = clamp(descent_altitude_gain · h_ekf, descent_min_mps, tavan)`.
- `descentSpeed`'in irtifa dalıyla aynı, yalnız `view_bounded`'a
  bakılmıyor.
- **Tavan da aynı:** alan ölçümü varsa
  `clamp(descent_size_gain · √area_m2, min, max)`, yoksa `descent_max_mps`.
- Yeni sabit yok: 0.35, 0.3, 0.20, 1.5
  ([`eland_params.yaml:286-337`](https://github.com/adakarda/slz-safelanding/blob/v5.5-tur3-cevrimdisi/src/eland_sim/config/eland_params.yaml#L286-L337)).

**Önerilen kod:**

```diff
--- a/src/eland_mode/include/emergency_landing_mode.hpp
+++ b/src/eland_mode/include/emergency_landing_mode.hpp
@@ :480, COMMIT
-        const float touchdown_speed = descentSpeed(altitude_m);
+        const float touchdown_speed =
+            _commit_irtifa_yasasi ? commitAltitudeSpeed(altitude_m) : descentSpeed(altitude_m);
@@ :548, declareParameters(), veri_toplama_kipi'nin yanı
     _veri_kipi = _node.declare_parameter<bool>("veri_toplama_kipi", false);
+    // In COMMIT, take the speed from the altitude law alone. The default
+    // (false) keeps descentSpeed(), whose area branch runs on the ratio
+    // frozen at COMMIT entry.
+    _commit_irtifa_yasasi = _node.declare_parameter<bool>("commit_irtifa_yasasi", false);
@@ :618, descentSpeed()'in arkası
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
@@ :837, üyeler
   bool _veri_kipi{false};
+  bool _commit_irtifa_yasasi{false};
```

**Seçim:** tavan donmuş alandan gelsin (önerim; brifteki irtifa yedeğinin
aynısı) mi, yoksa doğrudan `descent_max_mps` (1.5) mi?

**Bilinen sınır:** W5 gibi yükseltilmiş hedefte `h_ekf` platformun üstünde
~4 m gösterir; yasa ~1.4 m/s verir. B bunu çözmez.

**Doğrulama planı (uygulandıktan sonra):**
- **Kapalıyken:** §5'teki Kol 0 koşusu. COMMIT hızı ve temas hızı
  kayıtlılarla aynı.
- **Açıkken:** sert temasların tekrarı rastlantıya bağlı (aday 3 kez
  kaybolmalı). Bu yüzden erken COMMIT mevcut bir parametreyle zorlanacak:
  - yalnız test için `landing_altitude: 8.0`, W3'te (bölge kadraja
    sığsın),
  - 3 tohum × {kapalı, açık},
  - beklenen: kapalıyken COMMIT'te hız sabit (`tavan·(1−ρ_donmuş)`);
    açıkken `0.35·h` ile azalıp 0.3'e iner,
  - temas hızları karşılaştırılacak.
- **Ayrıca:** sert temas yaşayan 3 K3 bölümü (`t2024_t2`, `t2029_t1`,
  `t2029_t2`) her iki ayarla yeniden uçurulacak. Erken COMMIT tekrar
  olmazsa öyle raporlanacak.

---

## 7. Yeniden üretmek

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash   # bozucu.py rclpy'yi içe aktarıyor
python3 tools/veri/bozucu_dogrula.py --kare 4 --cikti ~/eland_veri/_tur3
python3 tools/veri/egiklik_rho.py --cikti ~/eland_veri/_tur3
python3 tools/veri/ornek_mat.py --cikti ~/eland_veri/_ornek_matlab \
    ~/eland_veri/k5_A0.6/acik_alan/k5_A0.6_acik_alan_t1001 ...
```

**İlgili belgeler:**
- [`docs/VERI_TOPLAMA.md`](https://github.com/adakarda/slz-safelanding/blob/main/docs/VERI_TOPLAMA.md):
  "Tur 3" bölümü, bütün tablolar.
- [`docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR2.md`](https://github.com/adakarda/slz-safelanding/blob/main/docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR2.md):
  veri ve tesis özeti.
- [`docs/KONTROLCU_TASARIM_BRIEF.md`](https://github.com/adakarda/slz-safelanding/blob/main/docs/KONTROLCU_TASARIM_BRIEF.md):
  kontrolcü brifi.
- [`tools/veri/data_dictionary.md`](https://github.com/adakarda/slz-safelanding/blob/main/tools/veri/data_dictionary.md):
  sütun sözlüğü.

---

## Senden istediğim

1. **A için onay**, ve mesaj tipi seçimi: yeni `GoruntuKapsami` (önerim) mi,
   `geometry_msgs/PointStamped` mi?
2. **B için onay**, ve tavan seçimi: donmuş alandan (önerim) mi,
   `descent_max_mps` mi?
3. **İsteğe bağlı:** iki parametrenin `false` değeriyle
   `src/eland_sim/config/eland_params.yaml`'a da yazılması (görünürlük
   için). Kodda varsayılan zaten false; istemezsen dokunmam.
4. **A sonrası:** mod `/eland/rho`'yu kullansın mı? Kullanacaksa ayrı madde
   ve ayrı parametre (varsayılan kapalı) olarak tarif et.
5. **C ve D'nin yorumu sende.** Bu sayılardan sonra ek ölçüm gerekiyorsa
   yaz. Örneğin bozuk maskelerin ham olarak da kaydedilmesi: kaydedicide
   bir seçenek, yeni toplama gerektirir.
6. **Kurallar aynı:** mevcut koda dokunan her şey onaylı, parametreyle,
   varsayılan kapalı. Kapalıyken eski davranış koşuyla gösterilecek.
