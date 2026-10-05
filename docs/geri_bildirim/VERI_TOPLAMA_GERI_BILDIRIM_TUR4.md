# Geri bildirim (Tur 4) — temas hızı ölçütü yapıldı; `commit_irtifa_yasasi` varsayılanı `true`, doğrulaması sürüyor

> **Bu metin ne:** Tur 3 sonucuna verdiğin dört kararın uygulanması, şu anki
> durumuyla.
> 1. Mod `/eland/rho`'yu kullanmıyor: **yapılan bir şey yok.**
> 2. `commit_irtifa_yasasi` varsayılanı `true` (yaml'da): **uygulandı,
>    varsayılan uçuş davranışı değişti** (§0).
>    - İstediğin doğrulama (Kol 0, açık / kapalı yan yana) **sürüyor:**
>      48 bölümün 8'i bitti.
>    - §3'te ara sonuç var; **final değil.**
>    - Tam tabloyu koşular bitince ayrı bir sonuç metniyle göndereceğim.
> 3. W5: kapsam dışı bırakılmadı, **yapılan bir şey yok.** Doğrulama
>    koşularında W5 de var (§3).
> 4. Başarı ölçütüne temas hızı, 0.5 ve 1.0 m/s: **tamam.** 218 bölüm
>    yeniden puanlandı, yeni koşu yok. **`basarili` değişmedi**, yanına iki
>    alan (§2).
>
> - **Tarih:** 2026-10-04.
> - **Kod (açık depo):** <https://github.com/adakarda/slz-safelanding>.
>   - Madde 4: etiket
>     [`v6.0-basari-temas-hizi`](https://github.com/adakarda/slz-safelanding/tree/v6.0-basari-temas-hizi),
>     commit [`a1746e3`](https://github.com/adakarda/slz-safelanding/commit/a1746e3).
>   - Madde 2 (yaml, koşu listesi, doğrulama betiği): etiket
>     [`v6.1-commit-irtifa-varsayilan`](https://github.com/adakarda/slz-safelanding/tree/v6.1-commit-irtifa-varsayilan).
>   - Bütün tablolar: `docs/VERI_TOPLAMA.md`, "Tur 4".
> - **Veri GitHub'da değil:** bu makinede.
>   - Yeniden puanlama raporu: `~/eland_veri/_tur4/temas_puanla.md`.
>   - Doğrulama koşuları: `~/eland_veri/_tur4_dogrulama/`.
> - **Etiketler:** **ölçülen**, **_hesap**, **_tahmin**.

---

## 0. Varsayılan davranış değişikliği — açıkça

**Değişen tek satır:** `src/eland_sim/config/eland_params.yaml`,
`emergency_landing_mode` altında `commit_irtifa_yasasi: false` → **`true`**
(yanında iki yorum güncellendi, §4.4).
- **Kod değişmedi.** Düğümün kendi varsayılanı
  (`declare_parameter<bool>("commit_irtifa_yasasi", false)`) `false` kaldı.
  Bu yaml olmadan başlatılan bir mod eski yasayla uçar.

**Nerede geçerli:**
- **`kosu.sh` koşuları:** `make_params.py` kaynaktaki yaml'ı okuyor, değer
  `true`. Bölüm klasöründeki `params.yaml`'da görülüyor.
- **Etkileşimli `run_sim.sh`** (`--params` olmadan): kurulu yaml'ı okuyor.
  - `colcon build --packages-select eland_sim` ile kurulu kopya yenilendi.
    `diff` ile kaynakla aynı olduğu görüldü.
  - Kurulu kopya Tur 3'ten beri eskiydi: `publish_rho` ve
    `commit_irtifa_yasasi` satırları yoktu. Düğüm varsayılanları da `false`
    olduğu için o arada davranış farkı yoktu.
  - Derlemenin taşıdığı başka şeyler: rüzgârlı üç model klasörü (kurulumda
    yoktu, eklendi) ve `mob_layout.yaml` (her koşuda yeniden yazılan dosya).
- **Veri kipi (K1-K4):** devirden sonraki COMMIT modun kendi yasası, yani
  bundan sonraki veri kipi koşuları da yeni yasayla iner.

**Uçuşta ne zaman fark eder:**
- **Yalnız** COMMIT'e alan yasası etkinken girildiğinde fark eder. Bu,
  bölgenin kadraja sığdığı (`view_bounded` doğru) ve ρ'nun COMMIT girişinde
  donduğu durum.
- **Tur 3'te ölçülen:**
  - Zorlanmış erken COMMIT: temas 1.20 → 0.30 m/s (ortanca).
  - K3 erken COMMIT: 1.27 → 0.30 m/s.
- **Normal 2 m COMMIT:** alan yasası COMMIT girişinde zaten devre dışıysa
  (`view_bounded` yanlış) iki ayar aynı komutu verir.
  - Bu tur bunu Kol 0'da 48 koşuyla ölçüyor (§3).
  - **Ara sonuç (ilk 4 koşul):** COMMIT'te alan yasası payı iki ayarda da 0,
    temas iki ayarda da 0.29-0.31 m/s.

**Eski davranış:** `emergency_landing_mode.commit_irtifa_yasasi=false`
(`kosu.sh`'ye ek parametre ya da `--params` dosyasında).

**Veri seti:**
- 218 bölüm eski yasayla kaydedildi (parametre yokken ya da `false`).
- Yeni bölümlerde değer bölüm klasöründeki `params.yaml`'da.
- `tum_ozet.csv`'de bunun için sütun yok (§5, soru 3).

---

## 1. Durum

| Madde | Durum | Doğrulama |
|---|---|---|
| 1. Mod `/eland/rho`'yu kullanmıyor | öyle; değişiklik yok | — |
| 2. `commit_irtifa_yasasi` varsayılanı `true` | **uygulandı; varsayılan davranış değişti** (§0) | **sürüyor:** Kol 0, 24 koşul × {kapalı, açık} = 48 bölüm; 8'i bitti (§3) |
| 3. W5 | değişiklik yok | W5, §3'teki koşularda (3 tohum × 2 ayar) |
| 4. Başarı ölçütüne temas hızı | **yapıldı; `basarili` değişmedi** | 218 bölüm yeniden puanlandı; yedekle alan alan karşılaştırıldı (§2) |

---

## 2. Madde 4 — başarı ölçütüne temas hızı

### 2.1 Ne değişti

- **`basarili` aynı:** PX4 landed + kör iniş değil + temas noktası hedef
  yüzeyde (açık alanda: temastan önceki maskenin merkezi inilebilir sınıf).
- **Yanına iki alan:**
  - `basarili_v10` = `basarili` **ve** temas hızı < 1.0 m/s.
  - `basarili_v05` = `basarili` **ve** temas hızı < 0.5 m/s.
  - Temas hızı yoksa ikisi de false.
- **Sert temas** = hız ≥ seviye (aşağıdaki "v ≥ 0.5", "v ≥ 1.0" sayıları).
- **Temas hızı** (değişmedi): `temas_dikey_hiz_gercek_hesap_mps`, Gazebo
  yüksekliğinin dinlenme yüksekliğine 3 cm'den çok yaklaştığı ilk andan önceki
  0.3 s'deki en büyük aşağı hız. **Ölçülen** (Gazebo konumunun türevi).
- **Eşikler tek yerde:** `tools/veri/basari.py`.
- **Nerede:**
  - Her bölümün `ep_ozet.json`'u.
  - `tum_ozet.csv`'de `basarili`'nin yanında iki sütun.
  - `birlesik_{train,val,test}.mat` içindeki `ep` yapısı.
  - Eski bölümlerin `ep.mat`'indeki `ozet_json` kayıt anındaki hâliyle
    kaldı. Tur 3 E'deki örnek MATLAB seti yeniden üretilmedi.

### 2.2 Nasıl doğrulandı

- **Yedek:** önce 218 `ep_ozet.json` ve eski `tum_ozet.csv` yedeklendi
  (`~/eland_veri/_tur4/`).
- **`ep_ozet.json`:** yedekle alan alan karşılaştırıldı. 218 dosyaya yalnız
  `basarili_v05` ve `basarili_v10` eklendi; eski alanlarda **0 fark**.
- **`tum_ozet.csv`:** `birlestir.py` yeniden çalıştırıldı.
  - 218 satır, aynı bölümler, eski sütunlarda **0 fark**.
  - Bölme aynı: train 140, val 31, test 47.
  - `birlesik_test.mat` geri okundu, `ep`'de iki alan var.
- **Kaydedici yeni bölümlerde kendisi yazıyor:** madde 2 koşularının
  bitenlerinde 8/8 bölümde yazdı (koşular sürüyor).

### 2.3 Sonuç (ölçülen, yeni koşu yok)

**Başarılı 195 bölümün 189'u 1.0 seviyesini, 183'ü 0.5 seviyesini geçiyor.**

| | Bölüm | Başarılı (eski) | Başarılı, v < 1.0 | Başarılı, v < 0.5 | Temas ortanca | En büyük | v ≥ 0.5 | v ≥ 1.0 |
|---|---|---|---|---|---|---|---|---|
| Toplam | 218 | 195 | 189 | 183 | 0.30 m/s | 1.48 m/s | 12 | 6 |
| K5/K5r (inmiyor) ve negatifler hariç | 195 | 195 | 189 | 183 | 0.30 | 1.48 | 12 | 6 |

Ortanca, en büyük ve "v ≥" sayıları gruptaki temas hızı ölçülen bütün
bölümlerden.

**Kol başına:**

| Kol | Bölüm | Başarılı (eski) | v < 1.0 | v < 0.5 | Ortanca | En büyük | v ≥ 0.5 | v ≥ 1.0 |
|---|---|---|---|---|---|---|---|---|
| kol0 | 31 | 27 | 24 | 24 | 0.30 | 1.48 | 3 | 3 |
| k1_v0.4 / v0.7 / v1.0 / v1.5 | 8 + 8 + 8 + 8 | 8 her biri | 8 her biri | 7 her biri | 0.30-0.31 | 0.50-0.51 | 1 her biri | 0 |
| k2_d0.2 / d0.35 | 8 + 8 | 8 her biri | 8 her biri | 7 her biri | 0.30 | 0.50 | 1 her biri | 0 |
| k2_d0.5 | 8 | 8 | 8 | 8 | 0.30 | 0.49 | 0 | 0 |
| k3_carpan | 40 | 40 | 39 | 39 | 0.31 | 1.10 | 1 | 1 |
| k3_parca | 40 | 40 | 38 | 38 | 0.30 | 1.33 | 2 | 2 |
| k4 | 12 | 12 | 12 | 12 | 0.30 | 0.31 | 0 | 0 |
| a5_k1v1.0, a5_k2d0.35 | 10 + 10 | 10 her biri | 10 her biri | 10 her biri | 0.30 | 0.31 | 0 | 0 |
| k5 / k5r (6 kol) | 19 | 0 | 0 | 0 | — (inmiyor) | — | 0 | 0 |

Kol 0'da başarısız 4 bölüm negatif örnek (W1 ×3, t2012). Kol 0'ın diğer
dünyalarında temas 0.29-0.31 m/s, W5 hariç.

**Seviyelerin düşürdüğü 12 bölüm:**

| Bölüm | Temas hızı | v < 1.0 | v < 0.5 | Not |
|---|---|---|---|---|
| kol0_veri_w5_t1 / t2 / t3 | 1.472 / 1.467 / 1.479 m/s | hayır | hayır | COMMIT'e hiç girilmedi |
| k3_parca_veri_ada_t2024_t2 | 1.333 | hayır | hayır | erken COMMIT, 13.6 m |
| k3_parca_veri_ada_t2029_t1 | 1.273 | hayır | hayır | erken COMMIT, 14.6 m |
| k3_carpan_veri_ada_t2029_t2 | 1.096 | hayır | hayır | erken COMMIT, 6.8 m |
| k1_v0.4_veri_w5_t1 | 0.507 | evet | hayır | W5, veri kipi |
| k2_d0.2_veri_w5_t2 | 0.504 | evet | hayır | W5, veri kipi |
| k2_d0.35_veri_w5_t1 | 0.504 | evet | hayır | W5, veri kipi |
| k1_v0.7_veri_w5_t1 | 0.503 | evet | hayır | W5, veri kipi |
| k1_v1.0_veri_w5_t2 | 0.502 | evet | hayır | W5, veri kipi |
| k1_v1.5_veri_w5_t2 | 0.501 | evet | hayır | W5, veri kipi |

COMMIT yükseklikleri Gazebo'nun hedef yüzeye göre yüksekliği.

**Bilmen gereken: 0.5 seviyesi W5 veri kipi bölümlerini gürültüyle bölüyor.**
- Veri kipindeki 18 W5 bölümü (K1, K2, K3) `--devir-yok --son-hiz 0.5` ile
  uçtu. Politika sona kadar 0.5 m/s istiyor; bu seçim Tur 2'deydi.
- Temas hızları **0.476-0.507 m/s.** 6'sı 0.500'ün üstünde (yukarıdaki
  tablo), 12'si altında.
- Bu bölümlerde 0.5 seviyesini geçip geçmemek ±0.01 m/s'lik farka bağlı.
  Bu, politikanın son hız ayarını ölçüyor, kontrolcünün kalitesini değil.

**Dağılım üç kümeli** (bütün veri seti):
- ~0.30 m/s: modun alt sınırı `descent_min_mps`.
- 0.48-0.51 m/s: W5 veri kipi.
- 1.10-1.48 m/s: sert temaslar.
- **0.507 ile 1.096 m/s arasında hiç temas yok.** Bu yüzden bu veride
  0.51 ile 1.09 m/s arasındaki her eşik 1.0 seviyesiyle aynı sonucu veriyor
  (_hesap, dağılımdan).

---

## 3. Madde 2 — `commit_irtifa_yasasi` varsayılanı `true`, yeniden doğrulama

### 3.1 Ne koşuluyor

- **24 koşul:**
  - W2-W6 × tohum 1-3 (15 koşul).
  - Dokuz pozitif ada (t2003-t2011) × tohum 1 (9 koşul).
  - Veri setindeki Kol 0 koşullarıyla aynı. W1 ve t2012 negatif örnek olduğu
    için dışarıda.
- **Koşul başına iki bölüm,** arka arkaya:
  - kapalı: `emergency_landing_mode.commit_irtifa_yasasi=false` (eski yasa);
  - açık: geçersiz kılma yok, yaml varsayılanı (`true`) sınanıyor.
- **Toplam 48 bölüm,** hepsi veri setinin dışında
  (`~/eland_veri/_tur4_dogrulama/{kapali,acik}/`).
- **Her bölümün gerçekten koştuğu değer** klasöründeki `params.yaml`'dan
  okunuyor, listeye güvenilmiyor.

### 3.2 Ara sonuç: ilk 4 koşul, 8 bölüm (19:51'de; final değil)

| Koşul | Temas kapalı / açık | COMMIT'te alan yasası payı | v_cmd temastan önce | COMMIT h_gerçek kapalı / açık | Başarılı | Durum dizisi |
|---|---|---|---|---|---|---|
| W2 t1 | 0.31 / 0.29 m/s | 0 / 0 | 0.30 / 0.30 m/s | 1.99 / 2.03 m | evet / evet | aynı |
| W2 t2 | 0.31 / 0.31 | 0 / 0 | 0.30 / 0.30 | 2.08 / 2.05 | evet / evet | farklı: açıkta APPROACH girildi |
| W2 t3 | 0.30 / 0.30 | 0 / 0 | 0.30 / 0.30 | 2.05 / 2.10 | evet / evet | farklı: açıkta APPROACH girildi |
| W3 t1 | 0.30 / 0.31 | 0 / 0 | 0.30 / 0.30 | 2.05 / 2.08 | evet / evet | aynı |

- **Ayar gerçekten uygulandı mı:** `params.yaml`'a göre kapalı 4/4 `false`,
  açık 4/4 `true`.
- **Bu 4 koşulda iki ayar aynı:**
  - COMMIT'te alan yasası hiç çalışmadı, iki ayarda da pay 0.
  - Temastan önceki komut iki ayarda da alt sınır 0.30 m/s.
  - Temas 0.29-0.31 m/s, sert temas (≥ 0.5) yok.
- **W2 t2 / t3 durum dizisi farkı parametreden değil:**
  - Parametre yalnız COMMIT'te etkili; fark COMMIT'ten önce (APPROACH'a
    girilip girilmemesi).
  - Eski kodla kaydedilmiş veri setinde W2 tohum 2'nin 9 bölümünün 5'inde
    APPROACH var, 4'ünde yok. Tohum 3'ün 2 bölümünün 1'inde var.
  - Tur 3'te de W2 t2 ve t3 APPROACH'sız uçtu.
  - Yani koşudan koşuya değişkenlik (Tur 3'teki W3 t2 gibi).
- **Kapalı, veri setindeki aynı koşulla:** 4/4 durum dizisi aynı. Temas
  veri seti / kapalı: 0.31 / 0.31, 0.30 / 0.31, 0.30 / 0.30, 0.30 / 0.30 m/s.

### 3.3 Kalan

- **40 bölüm.** Bölüm başına 74-85 s (ölçülen, ilk 8), yani yaklaşık 55 dk
  (_tahmin).
- **Bitince ayrı bir sonuç metniyle** göndereceğim
  (`docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR4_SONUC.md`). İçinde:
  - Ayar ve dünya başına temas ortanca / en büyük, v ≥ 0.5 ve v ≥ 1.0 sayısı,
    açık / kapalı yan yana.
  - Başarı: eski ölçüt ve iki seviye.
  - Koşul başına tablo.
  - Kapalının veri setindeki aynı koşulla karşılaştırması.
- **W5 için beklenti (_tahmin, henüz ölçülmedi):** iki ayarda da
  ~1.47 m/s sert temas.
  - Veri setindeki Kol 0 W5 bölümlerinde COMMIT'e hiç girilmedi.
  - Parametre yalnız COMMIT'te etkili.
  - Ölçülen sonuç sonuç metninde gelecek.

---

## 4. Kod

### 4.1 `tools/veri/basari.py` (yeni, madde 4)

[GitHub](https://github.com/adakarda/slz-safelanding/blob/v6.0-basari-temas-hizi/tools/veri/basari.py)

```python
import math

# (field, threshold m/s), the two levels decided in Tur 4
TEMAS_SEVIYELERI = (('basarili_v05', 0.5), ('basarili_v10', 1.0))


def temas_seviyeleri(oz):
    """{'basarili_v05': bool, 'basarili_v10': bool} for one ep_ozet."""
    v = oz.get('temas_dikey_hiz_gercek_hesap_mps')
    hiz_var = v is not None and math.isfinite(float(v))
    return {ad: bool(oz.get('basarili')) and hiz_var and float(v) < esik
            for ad, esik in TEMAS_SEVIYELERI}
```

### 4.2 Bu tanımı kullananlar (madde 4)

[`kaydedici.py`](https://github.com/adakarda/slz-safelanding/blob/v6.0-basari-temas-hizi/tools/veri/kaydedici.py):
yeni bölümler.

```diff
 sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
+import basari  # noqa: E402
 import dunya as dunya_mod  # noqa: E402
@@ def build(node, a):
     oz['temas_yeri_uygun'] = yer_ok
     oz['basarili'] = bool(inis and not oz['kor_inis'] and bool(yer_ok))
+    # and two levels of it by touchdown speed, < 0.5 and < 1.0 m/s
+    oz.update(basari.temas_seviyeleri(oz))
```

[`ozet_yenile.py`](https://github.com/adakarda/slz-safelanding/blob/v6.0-basari-temas-hizi/tools/veri/ozet_yenile.py):
başarıyı yeniden hesapladığı yerde.

```diff
         oz['basarili'] = bool(oz.get('t_px4_landed') is not None and not oz.get('kor_inis')
                               and bool(oz.get('temas_yeri_uygun')))
+        oz.update(basari.temas_seviyeleri(oz))
```

[`birlestir.py`](https://github.com/adakarda/slz-safelanding/blob/v6.0-basari-temas-hizi/tools/veri/birlestir.py):
`tum_ozet.csv` ve `birlesik_*.mat`.

```diff
-             'ruzgar_mps', 'politika', 'bozucu', 'basarili', 'temas_yeri_uygun',
+             'ruzgar_mps', 'politika', 'bozucu', 'basarili', 'basarili_v05',
+             'basarili_v10', 'temas_yeri_uygun',
@@ def main():
             'yol': ep_dir,
+            # from basarili and the touchdown speed, whether or not the
+            # episode's ep_ozet.json was rescored
+            **basari.temas_seviyeleri(oz),
         }
```

### 4.3 Yeniden puanlama ve rapor (madde 4)

[`tools/veri/temas_puanla.py`](https://github.com/adakarda/slz-safelanding/blob/v6.0-basari-temas-hizi/tools/veri/temas_puanla.py)
(yeni):
- `birlestir.py`'nin bulduğu bölümlerin `ep_ozet.json`'una iki alanı yazıyor,
  başka alana dokunmuyor. `--yalniz-rapor` ile hiçbir şey yazmıyor.
- Raporu kol başına ve Kol 0 için dünya başına çıkarıyor. Seviyelerin
  düşürdüğü bölümleri listeliyor.
- Çalıştırma:
  `PYTHONPATH=/usr/lib/python3/dist-packages python3 tools/veri/temas_puanla.py --cikti ~/eland_veri/_tur4`.
  `PYTHONPATH`, kullanıcı dizinindeki numpy 2'nin sistem scipy'siyle
  çakışmasından; `kosu.sh` da aynısını yapıyor.

### 4.4 `eland_params.yaml` (madde 2)

[GitHub](https://github.com/adakarda/slz-safelanding/blob/v6.1-commit-irtifa-varsayilan/src/eland_sim/config/eland_params.yaml)

```diff
-    # Only used before the first area measurement arrives.
+    # Used before the first area measurement arrives and, with
+    # commit_irtifa_yasasi below, all through COMMIT.
     descent_altitude_gain: 0.35
     # COMMIT speed from the altitude law alone,
     #   v = clamp(descent_altitude_gain * altitude, descent_min_mps, v_ceiling)
     # instead of the law above, whose area branch runs on the ratio frozen at
-    # COMMIT entry. false = the old behaviour.
-    commit_irtifa_yasasi: false
+    # COMMIT entry. On since Tur 4 (decided 2026-10-04); false = the old
+    # behaviour, kept for comparison. The node's own default is still false:
+    # a launch without this file gets the old law.
+    commit_irtifa_yasasi: true
```

Parametrenin kodu Tur 3'teki gibi duruyor
([`emergency_landing_mode.hpp`](https://github.com/adakarda/slz-safelanding/blob/v6.1-commit-irtifa-varsayilan/src/eland_mode/include/emergency_landing_mode.hpp)):

```cpp
// COMMIT
const float touchdown_speed =
    _commit_irtifa_yasasi ? commitAltitudeSpeed(altitude_m) : descentSpeed(altitude_m);
// parametre, düğümün kendi varsayılanı false
_commit_irtifa_yasasi = _node.declare_parameter<bool>("commit_irtifa_yasasi", false);
```

### 4.5 Doğrulama (madde 2)

- **Liste:**
  [`tools/veri/listeler/tur4_kol0_commit.txt`](https://github.com/adakarda/slz-safelanding/blob/v6.1-commit-irtifa-varsayilan/tools/veri/listeler/tur4_kol0_commit.txt).
  - Koşul başına önce kapalı
    (`emergency_landing_mode.commit_irtifa_yasasi=false`), sonra açık.
  - Açıkta geçersiz kılma yok: yaml varsayılanı sınanıyor.
- **Tablo:**
  [`tools/veri/tur4_dogrula.py`](https://github.com/adakarda/slz-safelanding/blob/v6.1-commit-irtifa-varsayilan/tools/veri/tur4_dogrula.py).
  - Her bölümün gerçekten koştuğu değeri `params.yaml`'dan okuyor.
  - COMMIT'teki alan yasası payı ve komut, Tur 3'teki `commit_profili()` ile.

---

## 5. Açık konular ve sorular

1. **Raporlarda hangi başarı?**
   - `basarili` değişmedi (varsayılan değişmesin diye).
   - Birincil ölçüt `basarili_v05` mi `basarili_v10` mu olsun? Yoksa
     `basarili`'nin kendisi mi yeniden tanımlansın? İkincisi, tüketenler için
     varsayılan değişikliği olur, açıkça yazarım.
2. **W5 veri kipi ve 0.5 seviyesi** (§2.3): `--son-hiz 0.5` bu seviyeyle
   çakışıyor, 18 bölüm gürültüyle ikiye bölünüyor. Seçenekler:
   - (a) Olduğu gibi bırak, W5 veri kipinde 0.5 seviyesinin anlamsız olduğunu
     not et.
   - (b) İleride W5 veri kipi koşularında son hızı 0.5'in altına al. Yeni
     koşu gerekir; mevcut 18 bölüm değişmez.
   - (c) W5'i gözlemcin gelene kadar yalnız 1.0 seviyesiyle değerlendir.
   - Önerim (a) + (c): yeni koşu gerektirmiyor, W5 zaten gözlemcinin test
     senaryosu olacak.
3. **Veri seti hijyeni:**
   - Yeni veri toplanacaksa `tum_ozet.csv`'ye `commit_irtifa_yasasi`
     sütunu eklemeyi öneriyorum. Değer bölümün `params.yaml`'ından, yoksa
     `false`.
   - Böylece eski ve yeni yasayla inen bölümler karışmaz.
   - Onay bekliyor. Şu an karışma yok: doğrulama koşuları veri setinin
     dışında (`_tur4_dogrulama`).
4. **Hâlâ bekleyen (Tur 2'den):** `run_sim.sh` temizliğine `tracker_node` ve
   `obstacle_driver`'ın eklenmesi.
   - `kosu.sh` sızan süreçleri kendi işaretiyle temizliyor.
   - Etkileşimli kullanımda sızıntı sürüyor.
   - Onay bekliyor.
5. **Madde 1:** Simulink'te tasarım doğrulanınca `/eland/rho` maddesini
   bekliyorum. Konunun ölçülen özellikleri Tur 3'te: ~10 Hz, yakalamadan
   alınmasına p50 19.5 / p90 39.6 ms, BEST_EFFORT.
