# Kontrolcü Ölçümleri — dikey iniş kontrolcüsü için ölçülmüş her şey

> **Bu dosya ne:** dikey iniş kontrolcüsünü tasarlayan ya da değiştiren
> birinin (insan ya da AI ajanı) ihtiyaç duyacağı ölçümlerin tek yeri.
> Sayılar başka dokümanlara dağılmıştı; burada konuya göre toplandı.
> - Her sayının yanında birimi, nasıl ölçüldüğü ve kaynağı var.
> - Kaynak dosya, bölüm ve sürüm etiketiyle verildi.
>
> - **Güncel:** 2026-10-05 (etiket `v6.6` sonrası).
> - **Etiketler:**
>   - **ölçülen:** simülasyonda koşuldu.
>   - **_hesap:** geometriden ya da formülden.
>   - **_tahmin:** varsayım.
> - **Ortam:** hepsi PX4 v1.17 SITL + Gazebo Harmonic + ROS 2 Jazzy, bu
>   makinede. Araç x500, 2.0 kg, aşağı bakan sabit kamera.
> - **Yöntem notu:** "gerçek" = Gazebo'nun kendi pozu (ground truth),
>   "EKF" = PX4'ün kestirimi. Zaman tabanı sim saati. Veri kayıtları 50 Hz
>   ızgarada (`tools/veri/kaydedici.py`).
>
> **Kural:** bir sayı değişirse burada güncelle ve kaynağına bağla. Eski
> değeri silme, gerekçesiyle "geçersiz" diye işaretle (örnek: §1.4).

---

## 0. Hızlı bakış

| Büyüklük | Değer | Tür | Bölüm |
|---|---|---|---|
| Tesis kazancı K (dikey hız komutu → gerçek dikey hız) | ≈ 1.0 (0.99-1.00) | ölçülen | §1.2 |
| Tesis ölü zamanı θ (%10 ölçütü) | **0.04-0.08 s** (eski 0.28 s geçersiz) | ölçülen | §1.2, §1.4 |
| %90 yükselme süresi | 0.26-0.44 s | ölçülen | §1.2 |
| İvme sınırı (büyük basamak) | yavaşlatma ~6.2, hızlanma ~8.5 m/s² | ölçülen | §1.2 |
| Komut edilebilen dikey hız | [0, 1.5] m/s (mod kırpıyor) | parametre | §1.5 |
| İç döngü (PI + ileri besleme) RMS takip hatası | 0.20 m/s (açık çevrim 0.32) | ölçülen | §2.3 |
| Sabit hız takibi (iç döngü) | ~1 cm/s; 1.5 m/s'de −3 cm/s | ölçülen | §2.5 |
| Maske hızı / yakalamadan maskeye | ~9.7-10 Hz / 16-20 ms | ölçülen | §3.1 |
| `/eland/rho` hızı / gecikme p50, p90 | ~10 Hz / 19.5, 39.6 ms | ölçülen | §3.3 |
| İniş adayı hızı (ρ'nun eski yolu) | ~1.8 Hz | ölçülen | §3.2 |
| ρ geometrisi | ρ = A / (4.22·h²), ρ̇/ρ = 2D | _hesap; ilk ilişki ölçülerek doğrulandı | §4.1, §4.4 |
| Açık alanda ρ dalının aktif olduğu pay | %0 | ölçülen | §4.2 |
| EKF yükseklik hatası (bias / RMS) | +0.01..+0.04 / 0.13-0.14 m | ölçülen | §5.1 |
| EKF dikey hız hatası RMS | 0.01-0.13 m/s (kola göre) | ölçülen | §5.1 |
| PX4 `landed` bayrağı gecikmesi | yumuşak temasta 3.8-4.9 s, serte 1.05 s | ölçülen | §5.3 |
| Tipik temas hızı | 0.30 m/s (`descent_min_mps`) | ölçülen | §6 |
| Erken COMMIT'te temas, eski / yeni yasa | 1.20 / 0.30 m/s (ortanca) | ölçülen | §6.4 |
| W5 (yükseltilmiş hedef) temas | 1.47-1.49 m/s; EKF hedefin ~3.8-4.0 m üstünde | ölçülen | §5.4, §6.5 |
| 2.5 m/s yan rüzgârın dikey tesise etkisi | yok (çözünürlük içinde) | ölçülen | §7.3 |
| Yanal kuvvet bozucusu | 10 N: 4/4 iniş; 15 N: 1/4 | ölçülen | §7.1 |

---

## 1. Kontrol edilen sistem (tesis)

### 1.1 Tesis ne

- **Kapsam:** tesis yalnız hava aracı değil; PX4'ün hız denetleyicisi, araç
  ve uXRCE-DDS köprüsü birlikte.
- **Giriş:** moddan `TrajectorySetpoint`'in dikey hız alanı
  (`withVelocityZ`), m/s, aşağı pozitif.
- **Çıkış:** aracın dikey hızı.
- **Dokunulmayan:** PX4 iç döngüleri (hız → ivme → tutum → açısal hız).

Kaynak: `docs/KONTROLCU_TASARIM_BRIEF.md` §2, §7.

### 1.2 K5 tesis testi — geçerli model (2026-10-03, ölçülen)

**Deney:**
- Açık çevrim kare dalga, 8 s periyot, kalkış 22 m.
- Komut −min(A, 1.0) ile +A arasında.
- Genlik başına 3 uçuş, toplam 12 uçuş.
- Yalnız gerçek yükseklik > 8 m olan satırlar.
- Komut 50 Hz setpoint'ten, hız Gazebo'dan.

Analiz: `tools/veri/tesis_analizi.py`.

| Genlik | Kaynak | n basamak | K ortanca | θ (%10) | %90 süresi | En büyük ivme | Yavaşlatma / hızlanma |
|---|---|---|---|---|---|---|---|
| 0.3 | Gazebo | 55 | 1.000 | 0.06 s | 0.26 s | 3.6 m/s² | 3.7 / 3.0 |
| 0.6 | Gazebo | 55 | 0.992 | 0.04 s | 0.28 s | 6.1 m/s² | 6.2 / 5.4 |
| 1.0 | Gazebo | 54 | 0.997 | 0.06 s | 0.36 s | 6.7 m/s² | 6.2 / 7.9 |
| 1.5 | Gazebo | 19 | 0.991 | 0.06 s | 0.40 s | 8.4 m/s² | 6.3 / 8.5 |
| 0.3-1.5 | EKF | 183 | 1.014-1.024 | 0.06-0.08 s | 0.28-0.44 s | 3.7-7.7 m/s² | |

**Okuma:**
- **K ≈ 1.0.**
- **θ ≈ 0.04-0.08 s.** Izgara çözünürlüğü 0.02 s.
- **Küçük basamakta birinci mertebe gibi** (τ ≈ 0.1 s).
- **Büyük basamakta ivme sınırlı**, ~6-8.5 m/s². Yavaşlatma/tırmanma yönü
  (~6.2) hızlanma yönünden (~8.5) yavaş.
- **1.5 genliğinde basamak az (19):** asimetrik dalga aracı aşağı sürüklüyor,
  8 m koruması basamakları bozuyor.

**Kaynak:**
- `docs/VERI_TOPLAMA.md` "K5 — tesis testi" (`v4.8-k5-tesis`).
- `docs/KONTROLCU_TASARIM_BRIEF.md` §7.
- Ham veri `~/eland_veri/k5_A*/`; şekil
  `~/eland_veri/dogrulama/k5/tesis_basamak.png`.

### 1.3 Rüzgârlı tesis (K5r, 2.5 m/s yan rüzgâr, ölçülen)

W4 rüzgârlı (`_r2p5`), etkin rüzgâr ölçeği 0.075 (§7.3), basamak 1.2 ve
2.0 m/s, × 3 uçuş.

| Genlik | Hız kaynağı | Basamak | K ortanca | θ | t90 | İvme sınırı ortanca (yukarı / aşağı) |
|---|---|---|---|---|---|---|
| 0.6 rüzgârlı | gerçek | 56 | 0.994 | 0.060 s | 0.30 s | 6.01 (6.04 / 5.34) m/s² |
| 0.6 rüzgârsız | gerçek | 55 | 0.992 | 0.040 s | 0.28 s | 6.13 (6.16 / 5.41) m/s² |
| 1.0 rüzgârlı | gerçek | 56 | 0.992 | 0.060 s | 0.36 s | 7.24 (6.12 / 7.83) m/s² |
| 1.0 rüzgârsız | gerçek | 54 | 0.997 | 0.060 s | 0.36 s | 6.67 (6.24 / 7.86) m/s² |

- **Yan rüzgâr dikey tesisi değiştirmiyor.** K, θ ve t90 ölçüm çözünürlüğü
  (20 ms) içinde aynı.
- Yatay kuvvet dikey ekseni ancak eğimin kosinüsüyle etkiler: cos 2.7° = 0.999
  (_hesap).

Kaynak: `docs/VERI_TOPLAMA.md` "Adım 4" (`v5.3-veri-tur2`).

### 1.4 Geçersiz sayılan eski model: θ ≈ 0.28 s

- **Önceki tanımlama** (`v2.9-system-id`): K = 1.01-1.03, ölü zaman
  θ ≈ 0.28 s, eğim 1.67-4.94 m/s².
- **Neden geçersiz:** komut 10 Hz'lik durum kanalından okunmuş ve rampa
  uydurulmuştu. Doğru örneklemeyle (50 Hz setpoint + Gazebo hızı) θ beşte
  birine indi (§1.2).
- **O deneyden geçerli kalan:** geçici rejim tek bir zaman sabitiyle değil,
  PX4'ün yörünge planlayıcısının ivme/jerk sınırlarıyla şekilleniyor.
  - Eğim genlikle değişiyordu (4.94 → 1.67 m/s²).
  - Birinci mertebe + ölü zaman modeli büyük basamakta uymuyor.

Kaynak: `docs/TEZ_NOTLARI.md` §2.5 ve düzeltme notu.

### 1.5 Hız sınırları

- **Modun kırpması:** `descent_max_mps = 1.5` (`eland_params.yaml`). Dikey
  hız komutu [0, 1.5] m/s'de kırpılıyor; VALIDATE'te tırmanma komutu yok.
- **PX4 parametreleri bu makinede varsayılan değil:** `MPC_Z_V_AUTO_DN = 2.0`,
  `MPC_Z_VEL_MAX_DN = 2.0` (PX4 varsayılanı 1.5 / 1.5). Kalıcılar ve her
  bölümde `kosul.yaml`'a yazılıyorlar.
  - Kapalı çevrim alçalmada etkisizler; mod 1.5'te kırpıyor.
  - Karar K4: bugünkü hâliyle kalıyor.
  - Kaynak: `docs/VERI_TOPLAMA.md` "Ek bulgular" E1.
- **Sınır vermek referans vermek değil** (ölçülen):
  - Eski sürüm hızı `goto`'nun `max_vertical_speed` alanına üst sınır olarak
    veriyordu.
  - Gerçekleşen hız 1.5'i hiç geçmedi.
  - PX4 sınırını 2.0'a çıkarmak işe yaramadı: ortalama hata −0.52 m/s, daha
    kötü.
  - Kaynak: `docs/TEZ_NOTLARI.md` §2.1-2.2.

---

## 2. Bugün uçan dikey kontrol yapısı

### 2.1 Alçalma yasası (referans üretir)

Birimler m/s, aşağı pozitif. `src/eland_mode/include/emergency_landing_mode.hpp`.

```
v_tavan = clamp(0.20·√A, 0.3, 1.5)               A: seçilen bölgenin alanı [m²], haritadan

VALIDATE'te:
  bölge kadraja tam sığıyorsa (view_bounded):
      v_ref = clamp(v_tavan·(1 − ρ), 0.3, v_tavan)    ρ: kapsama oranı (§4)
  sığmıyorsa (irtifa yedeği):
      v_ref = clamp(0.35·h_ekf, 0.3, v_tavan)

COMMIT'te (EKF irtifası ≤ landing_altitude = 2.0 m; geri dönüşsüz):
  commit_irtifa_yasasi = true  (varsayılan, 2026-10-04'ten beri):
      v = clamp(0.35·h_ekf, 0.3, v_tavan)
  commit_irtifa_yasasi = false (eski davranış):
      VALIDATE'teki yasa, COMMIT girişinde donmuş ρ ve view_bounded ile
```

- **İrtifa yedeği aslında sabit ıraksama yasası:** `v = 0.35·h`, yani
  `v/h = 0.35 1/s`. `h`'yi EKF'den alıyor; 4.3 m üstünde 1.5 m/s'de doyuyor
  (_hesap).
- **COMMIT'te yeni aday kabul edilmez,** ρ ve alan son değerde donar. Eski
  yasanın sert temas sebebi bu (§6.4).

Kaynak: `docs/KONTROLCU_TASARIM_BRIEF.md` §4; `docs/VERI_TOPLAMA.md`
"Tur 3 / A ve B" ve "Tur 4".

### 2.2 İç döngü (referansı izler)

```
e     = v_ref − v_ölçülen (EKF)
u     = v_ref + Kp·e + I                  Kp = 0.8, Ki = 0.6, Kd = 0
I    += (Ki·e + Kaw·(u_sat − u))·dt       Kaw = 1.0 (geri hesaplamalı anti-windup)
v_cmd = u_sat = clamp(u, 0, 1.5)
```

- **İleri besleme referansın kendisi.** Kp = Ki = 0 eski açık çevrimi
  birebir üretir.
- **Çarpmasız geçiş:** VALIDATE'e her girişte integral sıfırlanır.
- **COMMIT'te PI yok:** yasanın çıktısı doğrudan komut.

Kaynak: `docs/TEZ_NOTLARI.md` §2.3; `docs/KONTROLCU_TASARIM_BRIEF.md` §4.

### 2.3 Açık çevrim → kapalı çevrim (ölçülen)

**Taban, açık çevrim, yasa tavanı 2.0 m/s** (tek uçuş):

| İrtifa bandı | Komut | Gerçekleşen | Hata |
|---|---|---|---|
| 10 m üstü | 2.00 m/s | 1.30 m/s | −0.70 |
| 5-10 m | 1.98 | 1.50 | −0.49 |
| 2-5 m | 0.89 | 0.40 | −0.48 |
| 0-2 m | 0.36 | 0.27 | −0.09 |

**Tavan hizalama:**

| Deneme | Ortalama hata | 10 m üstü |
|---|---|---|
| Tavan 2.0 (taban) | −0.40 m/s | −0.70 |
| **Tavan 1.5** (seçilen) | **−0.26** | **−0.51** |
| PX4 sınırı 2.0'a çıkarıldı | −0.52 | −0.73 |

**Döngü kapatıldı,** tavan 1.5, birer uçuş:

| Kol | Ortalama hata | Mutlak ortalama | RMS | 10 m üstü | 5-10 m |
|---|---|---|---|---|---|
| Açık çevrim | −0.26 m/s | 0.27 | 0.413 | −0.51 | −0.06 |
| **PI + ileri besleme** | **−0.09** | **0.10** | **0.207** | **−0.09** | **−0.01** |
| Yalnız P (Ki = 0) | −0.14 | 0.15 | 0.226 | −0.15 | −0.10 |

**Üç kol, üçer uçuş** (asıl karşılaştırma, `v3.0-control-validation`):

| Kol | RMS takip hatası, ortanca [en iyi, en kötü] | Ortalama hata |
|---|---|---|
| Açık çevrim (yasa çıktısı üst sınır) | 0.323 [0.322, **1.829**] | −0.17 |
| Elle ayarlı PI (Kp 0.8, Ki 0.6) | **0.201** [0.190, 0.206] | −0.09 |
| IMC'den türetilmiş (Kp 0, Ki 1.39) | **0.197** [0.186, 0.214] | −0.08 |

- **Açık çevrimin asıl sorunu kuyruğu.**
  - Bir uçuşta alçalma 22 s yerine 39 s sürdü.
  - Araç doğrulanmış siteden 3.40 m uzağa dokundu.
  - 0-2 m'de komut 0.36 iken gerçekleşen −0.02 m/s: araç inmeyi bırakıp
    asılı kaldı.
- **Kapalı çevrimde dokunma sapması** 0.02-0.27 m.
- **Kalan hata 0-2 m bandında** (−0.14 m/s): yer etkisi ve iniş algılama.
- **Toplu koşum** (`v2.8-batch-harness`): 10 rastgele dünyada 10/10 iniş.
  Alçalma 22.15 s [21.97, 22.19], RMS 0.19 [0.18, 0.20].

Kaynak: `docs/TEZ_NOTLARI.md` §2.1-2.6; `docs/DEVIR.md` §10.

### 2.4 Kazanç türetimi (IMC) — yeniden yapılmalı

```
Ki = 1 / (K·(λ + θ)),  Kp → 0      λ = 1.5·θ
eski θ = 0.28 s  →  Ki = 1.39 1/s, Kp = 0
```

- **Uçuşta:** türetilmiş kazanç elle ayarlananla ölçüm gürültüsü içinde aynı
  (0.197 / 0.201, §2.3).
- **`Kp → 0` doğru sonuç:** döngü referansı ileri besliyor ve K ≈ 1.
- **Açık iş:** türetim eski θ = 0.28 s ile yapıldı. Yeni θ = 0.04-0.08 s
  (§1.2) ile yeniden yapılmadı.

Kaynak: `docs/TEZ_NOTLARI.md` §2.5, `tools/fit_fopdt.py`.

### 2.5 Sabit referans takibi (K1, ölçülen)

VALIDATE'in ilk 2 s'si hariç, devre (2.5 m) kadar; 31 bölüm.

| Hız | Bölüm | Süre / bölüm | vz_gerçek − v_ref ort / RMS | vz_ekf − v_ref ort / RMS |
|---|---|---|---|---|
| 0.4 | 7 | 29.3 s | −0.002 / 0.007 m/s | +0.000 / 0.005 m/s |
| 0.7 | 8 | 14.6 s | −0.007 / 0.010 m/s | +0.001 / 0.007 m/s |
| 1.0 | 8 | 9.8 s | −0.011 / 0.013 m/s | +0.003 / 0.009 m/s |
| 1.5 | 8 | 6.2 s | −0.032 / 0.034 m/s | −0.006 / 0.008 m/s |

- **İç döngü sabit hızı ~1 cm/s içinde tutuyor.**
- **1.5 m/s'de gerçek hız ~3 cm/s düşük;** EKF bunu görmüyor. Fark EKF'nin
  hız kestiriminde, PI'da değil.

Kaynak: `docs/VERI_TOPLAMA.md` "Adım 2".

### 2.6 Sabit ıraksama takibi (K2 kâhin, ölçülen)

Yasa `v = D*·h` (h gerçek), [0.3, 1.5]'te kırpılıyor, 2.5 m'de devrediliyor.
Sabit ıraksama yalnız `1.5/D*` ile 2.5 m arasında uçuluyor.

| D* | Bölüm | Tavanda (1.5 m/s), ort | Sabit ıraksamada, ort | Gerçekleşen D ort | D − D* RMS |
|---|---|---|---|---|---|
| 0.2 | 8 | 4.6 s | 5.6 s | 0.197 1/s | 0.007 1/s |
| 0.35 | 7 | 7.1 s | 1.6 s | 0.353 1/s | 0.004 1/s |
| 0.5 | 8 | 7.6 s | 0.4 s | 0.507 1/s | 0.013 1/s |

- **Pencere içinde takip çok iyi.**
- **Pencereler kısa:** D* = 0.5 pratikte "1.5 m/s ile in, 3 m'de 0.4 s
  ıraksa, devret".
- Uzun sabit ıraksama örneği için D* = 0.2 kolu ya da daha alçak devir
  irtifası gerekiyor (açık konu).

Kaynak: `docs/VERI_TOPLAMA.md` "Adım 3".

### 2.7 Basamak ve çoklu sinüs referansı (K4, 40 m, ölçülen)

- 12/12 iniş.
- `v_ref` 0.30-1.50 m/s aralığında, kırpmasız.
- **vz_gerçek − v_ref RMS 0.16-0.23 m/s.** İç döngünün basamaklardaki geçici
  yanıtı dahil.
- EKF vz hata RMS 0.02-0.13 m/s.

Kaynak: `docs/VERI_TOPLAMA.md` "Adım 5".

---

## 3. Görüntü sinyalleri ve zamanlama

### 3.1 Zincir gecikmesi (yakalama damgasından, ölçülen)

| | Kamera 5 Hz (eski) | **Kamera 10 Hz** (bugün, `v4.2-kamera-10hz`) |
|---|---|---|
| Yakalama → köprü | 5 ms | 8 ms |
| → maske | 16 ms | 16-20 ms |
| → füzyonlu harita | 24 ms | 24-26 ms |
| Harita hızı | 5.0 Hz | 9.6 Hz |
| Gerçek zaman oranı (penceresiz) | 1.00 | 1.00 |

- **Kamera:** 320×240, yatay FOV 99.7°, gövdeye sabit (gimbal yok).
- **Maske:** mono8, piksel = sınıf no (0..7).
- **Uçan inişte maske yaşı** p50 19-20 ms, p90 31-39 ms (açık alan, 3 iniş).

Kaynak: `docs/DURUM.md` §24.3; `docs/VERI_TOPLAMA.md` "Uçan doğrulama".

### 3.2 Kontrolcünün kullanabileceği sinyaller

| Sinyal | Kaynak | Hız | Not |
|---|---|---|---|
| Sınıf maskesi | `/eland/semantic_mask` | ~9.7-10 Hz | Gazebo'nun kusursuz etiketi; sonra eğitilmiş model gelecek, gürültülü olacak |
| ρ, `view_bounded` | `/eland/rho` (`eland_msgs/GoruntuKapsami`) | ~10 Hz | **`publish_rho` varsayılan kapalı**; mod henüz dinlemiyor (§3.3) |
| ρ, `view_bounded` (eski yol) | `/eland/candidate` içinde | ~1.8 Hz | karar hızında |
| `area_m2`, `radius` | `/eland/candidate` | ~1.8 Hz | harita 40×40 m ile sınırlı |
| Dikey hız `vz`, irtifa `h` | PX4 EKF | ~48-50 Hz | dünya düz varsayılıyor; W5'te yanlış (§5.4) |
| Tutum (roll, pitch) | PX4 | ~50 Hz | ayak izi düzeltmesi için |

- Derinlik sensörü, lidar, stereo yok.
- RGB kamera yalnız `rgb-akis-denemesi` dalında var (§4.6).

Kaynak: `docs/KONTROLCU_TASARIM_BRIEF.md` §8; `docs/DURUM.md` §24.3.

### 3.3 `/eland/rho` — ρ'nun maske hızında ayrı yayını (ölçülen)

**Mesaj ve ayar:**
- **Mesaj:** `std_msgs/Header header` (damga = maskenin yakalama anı),
  `float32 rho`, `bool view_bounded`.
- **QoS:** BEST_EFFORT, VOLATILE, KEEP_LAST 1. RELIABLE bir abone
  eşleşmez.
- **Açmak:** `detector_node.publish_rho: true`. Varsayılan `false`;
  kapalıyken yayıncı hiç oluşmuyor (`Publisher count: 0`, ölçüldü).

**Ölçülenler** (Kol 0 W2, 3 bölüm, `v5.7`):

| Ölçüm | Değer |
|---|---|
| Hız tüm kayıt / VALIDATE | 9.79-10.00 / 9.86-9.99 Hz |
| Yakalama → alma, p50 / p90 | 19.5 / 39.6 ms (üç bölüm birlikte) |
| Dedektörün eklediği (maske alma → ρ alma), p50 / p90 | 0.9 / 1.4 ms |
| Yayınlanan ρ − kaydedicinin aynı maskeden hesapladığı | en çok 0.000001 (CSV yuvarlaması) |

**Ölçülmeyen:** yayıncının kendi gönderme anı.

Kaynak: `docs/VERI_TOPLAMA.md` "A ve B — uygulandı";
`docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR3_AYRINTILI.md` §2.

### 3.4 Kaydedicinin kanal hızları (pasif test, yerde 20 s, ölçülen)

| Kanal | Hız | En uzun boşluk | Kayıp |
|---|---|---|---|
| PX4 konum | 50.3 Hz | 24 ms | 0 |
| PX4 tutum | 50.3 Hz | 24 ms | 0 |
| Gerçek poz | 50.7 Hz | 24 ms | 0 |
| Sim saati | 250 Hz | 4 ms | 0 |
| Maske | 10.0 Hz | 200 ms | 1 |
| Aday | 1.83 Hz | 647 ms | 0 |

Kaynak: `docs/VERI_TOPLAMA.md` "Aşama 1".

### 3.5 Döngüdeki toplam gecikme (_tahmin)

| Bileşen | Süre |
|---|---|
| tesis ölü zamanı | ~0.06 s |
| yükselme (τ) | ~0.1 s |
| 10 Hz örnekleme beklemesi | ~0.05 s |
| maske gecikmesi | ~0.02 s |
| **toplam** | **≈ 0.25 s mertebesi** |

ρ türevi için süzgeç eklenirse daha fazla.

Kaynak: `docs/KONTROLCU_TASARIM_BRIEF.md` §8.

---

## 4. ρ (kapsama oranı)

**Tanım:** maskede görüntü merkezinin altındaki bağlı güvenli bölgenin
piksel payı.
- `view_bounded`: bu bölge görüntü kenarına değmiyor mu.
- ρ yalnız `view_bounded` doğruyken bilgi taşır.

### 4.1 Geometri (_hesap)

Yatay FOV 99.7°, 4:3. `h` irtifasında yerdeki ayak izi:

```
genişlik = 2.37·h,  yükseklik = 1.78·h,  alan = 4.22·h²     (katsayı 4.216)
ρ = A / (4.22·h²)          bölge kadraja tam sığarken
ρ̇/ρ = 2·v/h = 2·D          D: ıraksama [1/s], temasa kalan süre τ = 1/D = 2ρ/ρ̇
```

Kapsamanın logaritmik türevi doğrudan ıraksama; irtifa gerekmez.

**Bölge ne zamana kadar kadraja sığar** (aracın tam altında, kare):

| Bölge | Sığdığı irtifa | O irtifada ρ |
|---|---|---|
| 4×4 m | 2.25 m üstü | 15 m'de 0.02, 5 m'de 0.15, 3 m'de 0.42 |
| 10×10 m | 5.6 m üstü | 15 m'de 0.11, 10 m'de 0.24, 6 m'de 0.66 |
| 20×20 m | 11.2 m üstü | 15 m'de 0.42 |
| Açık alan (~1270 m²) | ~20 m üstü | iniş boyunca hiç sığmaz |

- **Sığma bittiği anda ρ:** kare bölgede ~0.75, daire bölgede ~0.59. ρ'nun
  bilgi taşıyan aralığı 0 ile bu değer arası.
- **En küçük seçilebilir bölge** `min_area_m2 = 9` m².
- **Pratikte genişlik ~4.4 m'den az olmamalı:** iniş noktası sınıf sınırından
  ≥ 2 m uzakta isteniyor ve 0.2 m'lik ızgarada daha dar bir adada hiçbir
  hücre aday olamıyor (`tools/veri/data_dictionary.md`, "4.4 m eşiği").

Kaynak: `docs/KONTROLCU_TASARIM_BRIEF.md` §6.

### 4.2 Açık alanda ρ dalı hiç çalışmıyor (ölçülen)

| İrtifa | ρ | ρ dalı aktif | Komut edilen hız |
|---|---|---|---|
| 10+ m | 0.87 | %0 | 1.50 m/s |
| 5-10 m | 0.91 | %0 | 1.50 |
| 2-5 m | 0.91 | %0 | 1.09 |
| 0-2 m | 0.69 | %0 | 0.40 |

- **Sebep:** güvenli bölge kadrajdan taşıyor. Taşan bölgede ρ yalnız bir alt
  sınır ve doyuyor; yavaşlama kameradan değil irtifadan geliyor.
- **Veri kaydedicisiyle tekrar** (açık alan, 3 iniş): VALIDATE'te ρ ortancası
  0.998-1.000, kadraja sığma %0.
- **Tarihsel:** yalnız ρ kullanan ilk sürümde açık çimende iniş 0.3 m/s ile
  73 s sürüyordu (normali ~21-27 s); ρ 0.81'de takılıydı.

Kaynak: `docs/KONTROLCU_TASARIM_BRIEF.md` §5; `docs/VERI_TOPLAMA.md`
"Uçan doğrulama".

### 4.3 Yere yakınken etiket maskesinde yapı kalmıyor (ölçülen)

| İrtifa | Maskedeki sınıf sınırı pikseli |
|---|---|
| 15+ m | 1561 |
| 10-15 m | 1086 |
| 5-10 m | 61 |
| 5 m altı | **0** |

Homojen iyi bir iniş alanının etiket görüntüsü tek renk. Açık alanda son
5 m'de maskeden yakınlık bilgisi çıkmaz (veri kaydedicisiyle: sınır
pikselleri ~1.3 m civarında sıfıra iniyor).

Kaynak: `docs/KONTROLCU_TASARIM_BRIEF.md` §5.

### 4.4 Ölçülen ρ ile geometriden hesaplanan ρ, eğikliğe göre (Tur 3 D, ölçülen)

- **`rho_hesap`** = `A_gerçek / (4.22·h_kamera_gerçek²)`. A dünya
  dosyasından, h Gazebo'dan.
- **Eğiklik** = `arccos(cos roll · cos pitch)`.
- **Kareler:** yalnız `view_bounded = 1` ve `ρ > 0`.

**`ρ − rho_hesap`:**

| Kol | Aralık | Eğiklik | Kare | Ort | Ortanca | RMS | p95 \|·\| |
|---|---|---|---|---|---|---|---|
| K1 | tüm | < 5° | 3572 | +0.0002 | +0.0000 | 0.0014 | 0.0016 |
| K1 | tüm | ≥ 5° | 139 | +0.0079 | +0.0001 | 0.0179 | 0.0358 |
| K1 | VALIDATE | < 5° | 2472 | +0.0003 | +0.0000 | 0.0015 | 0.0017 |
| K1 | VALIDATE | ≥ 5° | 72 | +0.0123 | +0.0003 | 0.0204 | 0.0439 |
| K3 | tüm | < 5° | 7729 | −0.0004 | −0.0003 | 0.0019 | 0.0033 |
| K3 | tüm | ≥ 5° | 664 | +0.0038 | +0.0036 | 0.0121 | 0.0250 |
| K3 | VALIDATE | < 5° | 3227 | −0.0002 | −0.0001 | 0.0019 | 0.0038 |
| K3 | VALIDATE | ≥ 5° | 220 | +0.0021 | +0.0032 | 0.0098 | 0.0176 |

- **ρ = A/(4.22·h²) ilişkisi eğiklik < 5°'de çok iyi tutuyor**, RMS
  0.0014-0.0019.
- **≥ 5°'de sapma büyüyor** (RMS 0.010-0.020).
- **VALIDATE'te eğiklik:**
  - K1: ortanca 0.28°, p95 2.44°, en çok 9.57°.
  - K3: ortanca 0.36°, p95 7.89°, en çok 43.7°.
- **Ölçülmeyen:** türev ilişkisi ρ̇/ρ = 2D gürültülü veride henüz
  sınanmadı.

Kaynak: `docs/VERI_TOPLAMA.md` "Tur 3 / D"; `tools/veri/egiklik_rho.py`.

### 4.5 Algı bozucuları altında ρ (Tur 2 Adım 6 ve Tur 3 C, ölçülen)

Bozucular maskeye yapay hata ekler (`tools/veri/bozucu.py`).

| Bozucu | Tanım | VALIDATE'te \|ρ_bozuk − ρ_temiz\| ortalama | p99 |
|---|---|---|---|
| sınır 2 px | sınıra 2 px'ten yakın her piksel ±2 px içindeki rastgele bir komşunun sınıfını alır | 0.00036-0.00043 | 0.00095-0.00130 |
| çevir 0.02 | piksellerin %2'si başka sınıfa çevrilir | 0.0070-0.0184 | 0.017-0.238 |
| kayıp 0.05 | her karede %5 olasılıkla merkezin altındaki güvenli bölge o kare için UNKNOWN olur | 0.0092-0.0339 | 0.233-0.936 |
| gecikme 0.2 s | her kare kendi yakalama damgasıyla 0.2 s geç yayınlanır | 0 (yalnız gecikme, p50 203 ms) | 0 |
| tekrar 2 | içerik yalnız 3 karede bir güncellenir; aradakiler eski maskeyi yeni damgayla tekrarlar (damganın göstermediği bayatlık) | 0.0060-0.0100 | 0.029-0.057 |

- **Aday seçimi beş bozucuda da ayakta kaldı:** 20/20 iniş, HOLD / ABORT 0.
- **Ham bozuk maskeler kaydedilmedi.** Kayıtlı olanlar `rho_temiz`,
  `rho_bozuk`, `view_bounded_bozuk`, `t_alma_bozuk`; kontrolcü bunlarla
  çevrimdışı denenebilir.

Kaynak: `docs/VERI_TOPLAMA.md` "Adım 6" ve "Tur 3 / C";
`tools/veri/bozucu_dogrula.py`.

### 4.6 RGB optik akış denemesi (parkta)

- **Ne denendi:** `rgb-akis-denemesi` dalında 160×120 RGB kamera, Farneback
  akışından ıraksama.
- **Sonuç:** gerçek `v/h` ile korelasyon −0.24, yetersiz.
- **Muhtemel sebep:** taban süresi kısa. 0.1 s'de genleşme %0.75 (_hesap).

Kaynak: `docs/KONTROLCU_TASARIM_BRIEF.md` §5; `docs/DEVIR.md` §13.2.

---

## 5. Durum kestirimi (EKF) doğruluğu

### 5.1 Uçuşta (ölçülen)

| Ölçüm | Değer | Kaynak |
|---|---|---|
| EKF − gerçek yükseklik, bias / RMS | +0.01..+0.04 / 0.13-0.14 m | açık alan, 3 iniş |
| vz_ekf − vz_gerçek RMS | 0.028-0.052 m/s | açık alan, 3 iniş |
| vz hata RMS, K1 / K2 / K3 | 0.01-0.04 / 0.02-0.11 / 0.02-0.03 m/s | Tur 2 |
| vz hata RMS, K4 / Aşama 5 | 0.02-0.13 / 0.02-0.04 m/s | Tur 2 |
| Yükseklik kayması, K1 / K2 | ≤ 0.09 / ≤ 0.27 m | Tur 2 |

**Dikkat:** başka süreçler makineyi yüklediğinde (Tur 2'deki süreç sızıntısı)
EKF vz hatası 0.2-1.2 m/s'ye çıktı. O veri karantinada. Toplu koşudan sonra
EKF hatasını gerçekle karşılaştırmadan veriye güvenme.

Kaynak: `docs/VERI_TOPLAMA.md` "Uçan doğrulama", "Adım 1-7", "Olay: sızan
süreçler".

### 5.2 Yere yakın: son 0.6 s (Tur 4, 42 bölüm, W5 hariç, ölçülen)

| | vz_gerçek − vz_ekf | h_ekf − h_gerçek (temastan 0.1 s önce) |
|---|---|---|
| ortanca | +0.01 m/s | 0.00 m |
| aralık (41 bölüm) | −0.06 ile +0.03 m/s | −0.17 ile +0.06 m |
| **aykırı: Tur 4 açık W6 t1** | **+0.22 m/s** | **+0.135 m** |

- **Aykırı bölümde ne oldu:**
  - EKF iniş hızını 0.27 m/s gördü, gerçek ~0.49 m/s'ydi.
  - Kontrolcü EKF'ye göre 0.30'u izledi.
  - Gerçek temas 0.496 m/s oldu.
- **Kontrolcüye etkisi:** yer yakınında EKF hatası, iç döngünün izlediği
  hızı doğrudan bozuyor.

Kaynak: `docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR4_SONUC.md` §3.

### 5.3 PX4 iniş algılayıcısı geç (ölçülen)

| Durum | `ground_contact` gecikmesi | `landed` gecikmesi |
|---|---|---|
| Yumuşak temas (0.3 m/s, açık alan) | 3.11-4.19 s | 3.80-4.88 s |
| Yumuşak temas (W2) | | 4.6-4.8 s |
| Sert temas (W5, 1.47 m/s) | | 1.05-1.07 s |

- **Mod bu arada aracı yerde aşağı itmeyi sürdürüyor.** Eski "mod → landed"
  süreleri yerde geçen 4-5 s'yi içeriyor.
- **Temas anı ve hızı yalnız Gazebo'dan alınmalı;** veri kayıtlarında öyle.

Kaynak: `docs/VERI_TOPLAMA.md` "Uçan doğrulama" ve "Adım 1".

### 5.4 Yükseltilmiş hedef (W5, 10×10×4 m platform, ölçülen)

- **Araç yerde doğuyor;** EKF orijini yerde.
- **Platforma inerken EKF irtifası hedefin ~4 m üstünde kalıyor.** Temastan
  hemen önce `h_ekf − h_gerçek_hedef`:
  - Kol 0: 3.81-3.87 m;
  - K1: 3.99-4.04 m;
  - K2: 3.92-4.04 m.
- **Sonuç:**
  - COMMIT'e hiç girilmiyor.
  - İrtifa yasası 0.35·4 ≈ 1.4 m/s veriyor (temastan önce `v_ref`
    1.40-1.45).
  - Temas 1.47-1.49 m/s.
- **COMMIT irtifa yasası bunu çözmez;** EKF yüksekliği yanlış.
- **Tasarlanacak gözlemcinin test senaryosu** (Tur 4 kararı). Hedef yüzeye
  göre yükseklik kestirimi gerekiyor.

Kaynak: `docs/VERI_TOPLAMA.md` "Adım 1-3"; `tools/veri/adim_ozet.py`.

---

## 6. Temas (yere değme) hızı

### 6.1 Tanım

- **`temas_dikey_hiz_gercek_hesap_mps`:** Gazebo yüksekliğinin dinlenme
  yüksekliğine ilk kez 3 cm'den fazla yaklaştığı andan önceki 0.3 s'deki en
  büyük aşağı hız.
- Gazebo konumunun türevinden. PX4 bayrağından değil (§5.3).

### 6.2 Başarı ölçütü (Tur 4 kararları)

| Alan | Tanım |
|---|---|
| `basarili` | PX4 landed + kör iniş değil + temas noktası hedef yüzeyde. **Anlamı değişmez.** |
| **`basarili_v10`** | `basarili` **ve** temas < 1.0 m/s. **Birincil ölçüt.** |
| `basarili_v05` | `basarili` ve temas < 0.5 m/s. **W5'te uygulanmaz.** |

- **W5'te 0.5 seviyesi neden uygulanmıyor:** veri kipi W5'te
  `--son-hiz 0.5` ile uçuyor. Temaslar 0.476-0.507 m/s; 0.5 seviyesi onları
  gürültüyle ikiye bölüyor.
- **Raporlarda** temas hızının ortancası ve en büyüğü her zaman verilir.

Kod: `tools/veri/basari.py`.

### 6.3 218 bölümlük veri seti (ölçülen)

| | Bölüm | **Başarılı, v < 1.0 (birincil)** | Başarılı, v < 0.5 (W5 dışı) | Başarılı (eski) | Temas ortanca / en büyük |
|---|---|---|---|---|---|
| K5/K5r ve negatifler hariç | 195 | **189** | 171 / 174 | 195 | 0.30 / 1.48 m/s |

**Dağılım üç kümeli:**
- ~0.30 m/s: `descent_min_mps`.
- 0.48-0.51 m/s: W5 veri kipi.
- 1.10-1.48 m/s: sert temaslar. Bunlar Kol 0 W5 ×3 ve erken COMMIT'li
  K3 ×3.

0.507 ile 1.096 m/s arasında hiç temas yok.

Kaynak: `docs/VERI_TOPLAMA.md` "Tur 4 / Madde 4"; `tools/veri/temas_puanla.py`.

### 6.4 COMMIT irtifa yasası (Tur 3 B, Tur 4, ölçülen)

**Sorun:**
- Aday 3 kez kaybolunca mod "committing anyway" ile yüksekte COMMIT'e
  giriyor.
- Eski yasa `view_bounded` doğruysa donmuş ρ ile sabit `v_tavan·(1 − ρ)`
  veriyordu.
- Araç yere kadar 1.1-1.3 m/s ile indi.
- 218 bölümde 9 erken COMMIT (> 3 m), 3'ü sert.

**Zorlanmış erken COMMIT** (`landing_altitude = 10` yalnız test için, W3,
kalkış 18 m, 5 tohum × 2 ayar):

| Ayar | COMMIT'te alan yasası | Komut, COMMIT girişi → temastan önce | Temas ortanca / en büyük / en küçük |
|---|---|---|---|
| `false` (eski) | %100 | 1.18-1.19 → 1.18-1.19 m/s (sabit) | **1.20 / 1.22 / 1.18 m/s** |
| `true` (yeni) | %0 | 1.50 → 0.30 m/s | **0.30 / 0.31 / 0.30 m/s** |

- **K3'ün sert temaslı 3 bölümü yeniden uçuruldu:** erken COMMIT eskide
  3'te 1 kez oldu (1.27 m/s), yenide 3'te 2 kez (ikisi de 0.30 m/s).
- **Varsayılan `true`** (`v6.1`, 2026-10-04).
- **Kol 0'da 24 koşul × 2 ayar = 48 bölüm** (`v6.3`):
  - COMMIT'te alan yasası hiçbir bölümde çalışmadı; iki ayar aynı komutu
    verdi (0.30 m/s).
  - Birincil ölçüt iki ayarda da 21/24; kalan 3, W5.
  - Ayar yalnız erken COMMIT'te fark ediyor.

Kaynak: `docs/geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR3_SONUC.md`,
`..._TUR4_SONUC.md`; `docs/VERI_TOPLAMA.md` "Adım 7", "Tur 4".

### 6.5 W5

İki ayarda da 3/3 sert temas, 1.47-1.49 m/s; COMMIT yok (§5.4).

---

## 7. Bozucular

### 7.1 Gövdeye yanal kuvvet (`tools/wind_inject.py`, ölçülen)

- **Bu aerodinamik rüzgâr değil, kuvvet bozucusu.** Dönme momenti yok.
- **Rüzgâr eşdeğeri:** `F ≈ 0.06·v²` N (_tahmin). 10 N ≈ 13 m/s.

**Kalıcı rejimde yetki** (kuvvet 80 s'de 0 → 20 N rampa, araç asılı):

| Kuvvet | 2 | 6 | 10 | 12 | 16 | 20 N |
|---|---|---|---|---|---|---|
| Konum sapması | 0.03 | 0.21 | 0.10 | 1.68 | 0.28 | 0.04 m |

Araç 20 N'a kadar konumunu koruyor. Teorik sınır `m·g·tan45° = 19.6 N`
(_hesap).

**Adım bozucusu altında iniş:**

| Bozucu | İniş | Dikey RMS | Dokunma sapması |
|---|---|---|---|
| Yok | ✓ | 0.186 m/s | 0.06 m |
| 10 N (~13 m/s) | **4/4** | 0.19-0.22 | 0.48-2.15 m |
| 15 N | **1/4** | — | 39-590 m |
| 20 N (~18 m/s) | ✗ | — | — |

- **Kırılan kontrol değil, algı.** 15 N'da 157 adayın 156'sı geçersizdi;
  mod kör inişe geçti.
- **Dikey döngü 10 N'da etkilenmedi** (0.19-0.22'ye karşı 0.186 m/s).

Kaynak: `docs/TEZ_NOTLARI.md` §2.7-2.8 (`v3.1-disturbance`).

### 7.2 Eğim algıyı nasıl bozuyor (ölçülen)

Uçak 20 m'de asılı, eğim rampa ile artırıldı:

| Eğim | Anlık haritada bilinmeyen | Füzyonlu haritada bilinmeyen |
|---|---|---|
| 0-5° | 0.11 | 0.06 |
| 5-10° | 0.16 | 0.04 |
| 10-20° | 0.25 | 0.03 |
| 20-30° | 0.37 | 0.02 |

- **15 N için gereken yatış 37°** (_hesap). Araç aynı anda sürüklendiği için
  füzyonun düşeceği eski kanıt da yok; uygun hücre kümesi boşalıyor.
- **Çözüm önerisi** (kontrol tarafında değil): gimbal, ya da kararda harita
  tazeliği.

Kaynak: `docs/TEZ_NOTLARI.md` §2.9 (`v3.2-perception-tilt`).

### 7.3 Gazebo rüzgârı kalibrasyonu (ölçülen)

W4, 2.5 m/s, aynı başlangıç; rüzgârsız eşiyle karşılaştırma:

| Ayar | Eşine göre eğim farkı | Kuvvet karşılığı | Yatay sapma p95 / en çok |
|---|---|---|---|
| WindEffects ölçek 1.0 | 15.2° | ~5.5 N | 0.23 / 1.16 m |
| WindEffects kapalı | 1.7° | ~0.59 N (PX4 motor modelinin rotor sürüklemesi) | 0.08 / 0.43 m |
| **etkin 0.075 (SDF'de 0.2739)** | **2.67°** | **~0.94 N** | 0.06 / 0.13 m |

- **gz-sim 8 sabit ölçeğin karesini alıyor.** SDF'ye karekök yazılıyor
  (`dunya_uret.py --ruzgar-olcek`).
- **Öngörülen eğim 2.73°, ölçülen 2.67°.** Rüzgârlı 6 bölümde toplam eğim
  2.6-2.8°.

Kaynak: `docs/VERI_TOPLAMA.md` "Adım 4" (`v5.2-ruzgar-kalibrasyon`).

---

## 8. Ölçülerek reddedilenler (tekrar denemeden önce oku)

| Fikir | Neden reddedildi | Kaynak |
|---|---|---|
| PX4 hız sınırını 2.0'a çıkarmak | hata büyüdü (−0.52 m/s), iniş uzadı | `TEZ_NOTLARI.md` §2.2 |
| Yasa çıktısını PX4'e üst sınır olarak vermek | izlenmiyor; bir uçuş asılı kaldı | `TEZ_NOTLARI.md` §2.6 |
| Yalnız ρ'ya dayalı yasa | açık alanda ρ doyuyor, iniş 73 s | `KONTROLCU_TASARIM_BRIEF.md` §5 |
| Etiket maskesinden yakınlık (sınır pikseli) | 5 m altında 0 piksel | `KONTROLCU_TASARIM_BRIEF.md` §5 |
| RGB optik akış, ilk deneme | korelasyon −0.24 | `DEVIR.md` §13.2 |
| θ = 0.28 s ile model | ölçüm yöntemi hatalı | §1.4 |

---

## 9. Henüz ölçülmeyenler / açık işler

- **IMC kazanç türetimi** yeni θ = 0.04-0.08 s ile yapılmadı (§2.4).
- **ρ̇/ρ = 2D** gürültülü veride sınanmadı (§4.4).
- **Mod `/eland/rho`'yu henüz kullanmıyor.** Tasarım Simulink'te
  doğrulanınca ayrı madde gelecek.
- **W5:** hedef yüzeye göre yükseklik kestirimi (gözlemci) yok (§5.4).
- **Gerçek bir mod komutu kaybında yeniden denemenin işe yaradığı** henüz
  görülmedi. Yalnız ilk komut bilerek atlanarak sınandı (`v6.5`).
- **Gazebo penceresi açıkken** 10 Hz kameranın gerçek zaman oranı ölçülmedi
  (`DURUM.md` #30).

---

## 10. Veri ve yeniden üretme

- **218 bölümlük veri seti:** GitHub Release
  [`v6.8-veri-seti`](https://github.com/adakarda/slz-safelanding/releases/tag/v6.8-veri-seti).
  Kullanımı [`VERI_SETI.md`](VERI_SETI.md).
- **Bu dosyadaki doğrulama koşuları ve ara raporlar** (`_tur3_dogrulama/`,
  `_tur4_dogrulama/`, `_tur3/`, `_tur4/`) Release'te değil; proje sahibinin
  makinesinde `~/eland_veri/` altında. Sayıları bu dosyada ve kaynak
  dokümanlarda.

| Tablo | Betik |
|---|---|
| Tesis (K5) | `tools/veri/tesis_analizi.py` |
| Toplu adım raporu | `tools/veri/adim_ozet.py GUNLUK` |
| Temas puanlaması | `tools/veri/temas_puanla.py` |
| ρ ve eğiklik | `tools/veri/egiklik_rho.py` |
| Bozucu doğrulaması | `tools/veri/bozucu_dogrula.py` |
| Tur 3 / Tur 4 doğrulama | `tools/veri/tur3_dogrula.py`, `tools/veri/tur4_dogrula.py` |
| Uçuş puanlama (veri kaydedicisi öncesi) | `tools/run_scorer.py`, `tools/batch_run.sh` |
| Tesis tanımlama, eski yöntem | `tools/fit_fopdt.py` |

- **Sütunların tanımı:** `tools/veri/data_dictionary.md`.
- **Betikler** sistem scipy'siyle çalışır:
  `PYTHONPATH=/usr/lib/python3/dist-packages python3 ...`.
