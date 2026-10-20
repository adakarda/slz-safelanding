# RL iniş ve AirSim — sonuç raporu

> **Güncel:** 2026-10-20 17:30. **Durum:** tarama bitti (H15: c23 B1/B2-s0'ın yerini almaz). B2 hızlandırma
> (H19) 16:49'da başladı. Gözlem turu, birleşim turu ve AirSim Faz 7 sırada bekliyor. Bu rapor her karardan sonra
> güncellenmeli.
> **Kim için:** tezi yazan, deneyi devralan ya da sonuçları kullanan herkes.
> **Nasıl kurulur, nasıl çalıştırılır:** [`README.md`](README.md).
> **Kaynak:** her sonucun ön kaydı ve sonucu [`../onkayit/rl_f0_onkayit.md`](../onkayit/rl_f0_onkayit.md)'de.
> Tabloların ham hâli `tools/rl_inis/arama/ozet.md` ve `~/rl_inis/kos/*/eval_*.csv`'de.

Etiketler: **ölçülen** (koşuldu), **_hesap** (formül), **_tahmin** (varsayım). Aksi yazmıyorsa sayılar
ölçülendir.

---

## 1. Bulgular

1. **En iyi model iki ölçüte göre ayrışıyor.** Doğrulama seti `val_b32`, 320 deneme, 30 s.
   - Skor: c13 s0. %69.7 başarı, 13.8 s, %7.2 güvensiz.
   - Başarı: B2 s0 + kalkan. %76.9 başarı, 17.4 s, %0.3 güvensiz.
   - 3 tohum ortalamasında (kalkanlı): c23 %72.5 ve 16.6 s, c13 %66.4 ve 15.1 s, B1 %66.7 ve 16.6 s. c23 en
     yüksek ortalama skoru aldı (88.9) ama ön kayıtlı kuralı geçmedi: hız şartı (≤ 13.5 s) ve tohum şartı
     tutmadı. B1/B2-s0 yerinde kalır.
   - c13, B1 ile aynı başarıda ~1.5 s daha hızlı ama tohuma duyarlı.
2. **Kaybın çoğu süre aşımı.**
   - c13 s0'ın 320 denemesi: 223 başarı, 74 süre aşımı, 23 güvensiz.
   - B2 s0 + kalkan aynı başlangıçlarda 90 s verilince %76.9 → %88.1.
   - Politika güvenli yeri buluyor ama 30 s'ye sığmıyor. 30 s sınırında hız ile başarı aynı problem.
3. **Eğitimde 30 s sınırı, kalkan eğitimin içinde değilse politikayı çökertiyor.**
   - D: hep alçalıyor, %59.6 güvensiz.
   - E ve F: dolaşıyor, %50–70 süre aşımı.
   - c13 (30 s + kayarak alçalma + kalkan eğitimde) çökmedi ve taramanın en iyisi oldu.
4. **Kalkan güvensiz inişi neredeyse sıfırlıyor.**
   - B2 s0'a sonradan eklenince güvensiz iniş 28'den 1'e iniyor (320 denemede).
   - Eğitimin içine konunca politikanın kendi güvensiz inişi %27.0 → %7.7 (c00 → c13, val_b64 × 10).
5. **Tohumlar çok farklı.** c13: %69.7 / %68.8 / %60.6. B2'nin tohum 1 ve 2'si çoğunlukla süre doldurdu. Tek
   tohumla karar verilemez.
6. **Gözlem ve ağ:**
   - Depth Anything kanalı benimsenmedi: kalkanlı başarıyı artırdı ama güvensiz inişi kural sınırından çok
     artırdı.
   - Vekil görevde IMPALA kodlayıcı en iyisi (dengeli doğruluk 0.628, makalenin CNN'i 0.596; 3 tohum). PPO
     testi birleşim turunda.
7. **AirSim'de darboğaz politika değil, algı.**
   - AirSim'in gerçek etiketiyle RL güvenli iniyor: B2 + kalkan 10/10 zemin (Faz 4), çatı üstü başlangıç 6/6
     (gösterim).
   - v3 segmentasyon maskesiyle RL 10 inişin 9'unda yola indi (Faz 6). v3 asfaltı "sert zemin" sanıyor
     (Faz 1).
8. **Hafif ortam PX4'ü iyi taklit ediyor.**
   - Ölçülen PX4 tepkisine uydurulan model, tanılama uçuşunu yatayda 0.036–0.084 m/s RMSE ile yeniden oynattı.
   - Gazebo + PX4'te aynı 15 başlangıç 13 kez aynı sonucu verdi. İniş noktası farkının medyanı 0.10 m.

---

## 2. Yöntem

### 2.1 Ortam (`src/eland_rl/eland_rl/env.py`)

| | Değer | Kaynak |
|---|---|---|
| Gözlem | 128×128. Kanallar: sınıf/7, derinlik/40 m, güvenli-alan maskesi (`sem_depth_sora`). İsteğe bağlı risk, hedef, hafıza | Düzeltme 5, 16 |
| Kamera | HFOV 99.7°, 4:3, aşağı bakan. Her adımda ışın–düzlem kesişimi; etiket en yakın komşuyla örneklenir | §2.2, Düzeltme 1 |
| Eylemler | 0 dur; 1–8 yana 1 m/s (gövdeye göre 8 yön); 9 alçal 2 m/s. `--diag`: 10–17 yana kayarken alçal | §2.3, Düzeltme 13 |
| Adım | 0.25 s | §2.3 |
| Dinamik | Birinci derece hız tepkisi + saf gecikme. τ_xy 0.50 s, τ_z 0.15 s, a_max 2.0 m/s², gecikme xy 0.24 s, z 0.10 s, trim eğimi 0.9°. Eğitimde rastgeleleştirilir (τ ±%50, gecikme ±%50, a_max ±%30) | Düzeltme 1, ölçülen |
| Başlangıç | Fotoğraf üstünde rastgele, 20–30 m, rastgele yön (bölüm içinde sabit) | §2.5 |
| Bitiş | Kamera 5 m'ye inince iniş; fotoğraftan çıkış; çarpışma; süre (eğitim 90 s ya da `--max-t`, test 30 s) | §2.5 |

**Ödül ön ayarları** (`REWARD_PRESETS`). Ortak gövde makalenin denklemleri: adım cezası, görüş terimi,
çarpışma terimi, eylem terimi, bitiş ödülü.

| Ön ayar | Başarı kuralı | Fark | Sonuç |
|---|---|---|---|
| `paper` | 5 m'de görüşün çoğunluk sınıfı güvenli | makale | pilotta düz alçalmaya çöktü |
| `sora_v1` | altındaki nokta SORA-güvenli (tehlikeye ≥ 3 m) | en yakın güvenli noktaya potansiyel şekillendirme, alçal +0.5, görüş terimi 0 | Düzeltme 4 |
| `zemin_v1` | **zemin kuralı:** altındaki sınıf çim ya da sert zemin, 2 m içinde insan/araç yok | sınıfa göre bitiş ödülü: çim +50, sert +30, yol/ağaç −40, yapı −60, su −70, araç −90, insan −100, bilinmeyen −50; süre aşımı −50 | Düzeltme 9 |
| `zemin_v2` | zemin | sert +5, şekillendirme 10 m içinde çime yönelir | benimsenmedi (C) |
| `zemin_v3` | zemin | yol/ağaç ve bilinmeyen −60 (süre aşımından pahalı), alçal +1 | tek başına benimsenmedi (F); c13'ün ödülü |

### 2.2 Veri

- **Kaynak:** MESSI hava fotoğrafları ve sınıf maskeleri (özel paket; `docs/rl_veri/`). Fotoğraf başına GSD
  kendi EXIF ve XMP verisinden (Düzeltme 1).
- **Listeler** (`~/eland_veri/rl/messi_ds4/`): `train_b` 600 sahne, `val_b32` 32 sahne, `val_b64` 64 sahne.
  `test` IrYamim'in 20 karesi; final test için ayrıldı (Düzeltme 17).
- Eğitim 4 ortamla, sahneler ortamlara bölünerek (`--shard`).

### 2.3 Değerlendirme

- `val_b32` × 10 başlangıç = 320 deneme. Tohum `k` her yöntemde aynı başlangıcı verir.
- Argmax eylem, nominal dinamik, 30 s.
- Ölçütler: **B** zemin başarısı, **T** başarılı inişlerin ortalama süresi, **U** güvensiz iniş, **TO** süre
  aşımı. Yöntemler: RL, RL + kalkan (10 m), düz alçalma, görüş kâhini (tavan).
- **Skor:** `S = B_kalkan + 0.5·B_RL − 4·max(0, T_kalkan − 12)` (Düzeltme 15).
- **Belirsizlik:** 320 denemede %70 başarının Wilson %95 aralığı %64.4–%74.5 (_hesap). Kararlar 3 tohumla.

---

## 3. Zaman çizelgesi

| Tarih | Ne oldu |
|---|---|
| 2026-10-16 | F0 ön kaydı. PX4 tepkisi ölçüldü ve modele uyduruldu (F1). Pilot düz alçalmaya çöktü. F4 Gazebo testi. Karar: makaleyi birebir kopyalama, kendi ödülümüzü kur (`sora_v1`, SORA kanalı) |
| 2026-10-17 | MESSI eğitimleri (A1, A2b). Depth Anything deneyi (PA–PD). B deneyi (`zemin_v1`, aynalama). Kodlayıcı vekil görevi. Hız yaması (sonuç bit bit aynı). İki kesinti: uyku ve bellek taşması |
| 2026-10-18 | B, Depth Anything ve C sonuçları. D deneyi. AirSim Faz 3–6. Tarama ön kaydı (Düzeltme 15) |
| 2026-10-19 | E ve F sonuçları. Tarama Tur 1–2 ve Tur 3'ün c13 tohumları. Final test protokolü (Düzeltme 17). Gözlem, birleşim ve B2 hızlandırma ön kayıtları. Havada başlangıç (`--havada`) |
| 2026-10-20 | 00:31'de bilgisayar uyudu, zincir 15 saat durdu, 16:01'de kayıt noktasından sürdü. AirSim çatı gösterimi 6/6. Tarama bitti (H15: c23 yerini almaz). B2 hızlandırma başladı |

---

## 4. Hafif ortam deneyleri

### 4.1 Pilotlar (5 yerel fotoğraf, 75 bölüm, SORA kuralı, Düzeltme 2–5)

| Kol | SORA başarısı | Not |
|---|---|---|
| Pilot (`paper`, 500k) | %9.3 (çoğunluk kuralıyla %21.3) | düz alçalmayla aynı sonuç; entropi 1.85 → 0.39 |
| `paper` + entropi | %10.7 (çoğunluk %26.7) | kontrol |
| `sora_v1` + entropi | %9.3 | 26 bölümde süre doldu, eylemlerin %55'i yanal |
| `sora_v1` + SORA kanalı, tohum 0 / 1 | %37.3 / %18.7 | Düzeltme 5 |
| Düz alçalma | %12.0 | |
| Görüş kâhini (yalnız gördüğünü bilir) | %82.7 | tavan |

- **Ders:** sorun ödülde değil, görüntüden güvenli yeri okumakta. Kâhin aynı görüşle %82.7 alıyor. SORA kanalı
  bu yüzden eklendi.

### 4.2 MESSI eğitimleri (Düzeltme 6, 8; IrYamim, 20 kare × 15 başlangıç, `sora_v1` kuralı)

| Kol | RL | RL + kalkan | Düz alçalma | Kâhin |
|---|---|---|---|---|
| A1 (2M adım) | %56.3 (106 güvensiz) | %60.7 (2 güvensiz, 115 süre aşımı) | %18.3 | %81.0 |
| A2b (kalkan eğitimde) | %60.7 (4 güvensiz, 106 süre aşımı) | %60.7 | %54.3 | %68.3 |

- A2b'nin değerlendirme ortamında kalkan içeride. Bu yüzden onun "düz alçalma"sı da kalkanlı (%54.3) ve RL ile
  RL + kalkan aynı.
- Tek tohum, ön sonuç (K73). Bu değerlendirme IrYamim'i bir kez kullandı. O günden beri hiçbir seçim
  IrYamim'e bakılarak yapılmadı (Düzeltme 17 notu).

### 4.3 Depth Anything (Düzeltme 7; test uçuşu 0004, 600 iniş, SORA başarısı / güvensiz)

| Kol | RL | RL güvensiz | RL + kalkan | RL + kalkan güvensiz |
|---|---|---|---|---|
| P0 (GT, kıyas) | 15.8 | 9.7 | 17.5 | 0.0 |
| PA (v3 maskesi) | 13.3 | 28.5 | 10.3 | 1.7 |
| PB | 4.7 | 95.3 | 33.0 | 20.2 |
| PC | 7.7 | 92.3 | 31.7 | 17.3 |
| PD | 15.2 | 71.3 | 25.0 | 6.0 |

**Karar: eklenmez.** Kalkanlı başarı 14–23 puan arttı ama güvensiz iniş 4–19 puan kötüleşti. Kural 3 puandan
fazlasına izin vermiyor.

### 4.4 Kodlayıcı vekil görevi (Düzeltme 10, aşama 1; görüş kâhininin eylemini tahmin, val_b32, 3 tohum)

| Kodlayıcı | Dengeli doğruluk | Doğruluk | Alçal/alçalma doğruluğu | Parametre |
|---|---|---|---|---|
| `paper` (Nature CNN) | 0.596 ± 0.014 | 0.673 | 0.907 | 1.26M |
| `paper_onehot` | 0.595 ± 0.012 | 0.671 | 0.914 | 1.27M |
| `iki_kol` (geç birleştirme) | 0.599 ± 0.012 | 0.674 | 0.915 | 1.88M |
| `impala` (+ CoordConv) | **0.628 ± 0.005** | 0.700 | 0.911 | 2.20M |

- IMPALA +3.2 puan. Öbür ikisi makalenin CNN'inden farksız.
- PPO aşaması (aşama 2) K79 kilidi yüzünden bekledi. Arda'nın onayıyla birleşim turuna (k3) girdi.

### 4.5 B deneyi (Düzeltme 9; 3 kol × 3 tohum, 1M adım, val_b32, zemin kuralı, ortalama ± sapma)

| Kol | RL başarı | RL güvensiz | RL süre doldu | RL + kalkan başarı |
|---|---|---|---|---|
| B0 (`sora_v1`) | 22.1 ± 17.7 | 17.7 ± 27.5 | 60.2 ± 45.2 | 24.2 ± 21.0 |
| **B1 (`zemin_v1`)** | **56.9 ± 10.9** | 18.6 ± 10.3 | 24.5 ± 16.3 | **66.7 ± 13.1** |
| B2 (`zemin_v1` + aynalama) | 35.6 ± 32.0 | 3.1 ± 4.9 | 55.8 ± 32.1 | 37.2 ± 34.5 |

- **Karar (ön kayıtlı kural): `zemin_v1` ve aynalama benimsenmedi.** H9a tutmadı: B1'in güvensiz inişi
  B0'ınkinden az değil.
- **Kural hatası (not):** B0'ın düşük güvensiz oranı, denemelerin %60'ında hiç inmemesinden geliyor. Birincil
  ölçütte B1 açıkça önde. Kural sonradan değiştirilmedi. Yeniden yargı yeni ön kayıt ister.
- B2 s0 tek başına iyi bir model (kalkanla %76.9). Tohum 1 ve 2 süre doldurmaya çöktü.

### 4.6 C, D, E, F deneyleri (Düzeltme 11–14; 3 tohum, val_b32, kalkansız RL)

| | B1 (kıyas) | C1 `zemin_v2` | D1 eğitimde 30 s | E1 D1 + kayarak alçal | F1 `zemin_v3` + 30 s |
|---|---|---|---|---|---|
| Başarı | 56.9 ± 10.9 | 50.9 ± 5.6 | 24.8 ± 4.6 | 23.9 ± 25.9 | 35.6 ± 14.2 |
| Güvensiz | 18.6 ± 10.3 | 21.0 ± 8.2 | 59.6 ± 17.2 | 2.5 ± 4.3 | 14.1 ± 15.5 |
| Süre doldu | 24.5 ± 16.3 | 27.8 ± 13.3 | 15.0 ± 20.1 | 70.5 ± 28.2 | 50.3 ± 27.0 |
| Başarılı iniş süresi | 15.1 ± 0.5 s | — | 12.2 ± 1.7 s | 15.9 ± 1.5 s | 16.7 ± 2.2 s |
| RL + kalkan başarı | 66.7 ± 13.1 | 60.4 ± 6.5 | 53.6 ± 18.3 | — | 40.3 ± 20.4 |
| Karar | — | benimsenmedi | benimsenmedi | benimsenmedi | benimsenmedi |

- **C:** çime iniş yalnız +4 puan arttı (gereken +10). Ajan çim için daha uzağa gidiyor, 30 s yetmiyor.
- **D:** politika çöktü. D1-s0 eylemlerinin %100'ü "alçal". Başarılı inişler hızlı ama güvensiz.
- **E:** ters yöne çöktü, dolaşıyor. E1-s0'da eylemlerin %97.5'i düz kayma. Argmax sebep değil: alçalan
  eylemlerin toplam olasılığı medyan 0.17.
- **F:** ödül düzeltmesi çöküşün yönünü değiştirdi, D dümdüz alçalıyordu, F süre dolduruyor.

### 4.7 Tarama (Düzeltme 15)

25 ayar, ortak taban: 1M adım, `ent_coef` 0.01, `sem_depth_sora`, 4 ortam. Tam liste
`tools/rl_inis/arama/konfig_t1.json`, tam tablo `tools/rl_inis/arama/ozet.md`.

**Tur 1** (400k adım, val_b64 × 5, tek tohum), ilk 8:

| Ayar | Ne değişti | S | Kalkan B | Kalkan T | RL güvensiz | RL süre doldu |
|---|---|---|---|---|---|---|
| c23 | `zemin_v1`, adım −0.5, alçal +1 (90 s) | 81.2 | 65.3 | 17.1 s | 8.1 | 19.1 |
| c00 | `zemin_v1` (B1'in kendisi) | 75.6 | 67.5 | 18.5 s | 4.7 | 27.5 |
| c13 | `zemin_v3`, 30 s, kayarak alçal, kalkan eğitimde | 73.6 | 63.4 | 17.4 s | 9.4 | 27.2 |
| c05 | `zemin_v3`, 30 s, adım −0.5 | 65.7 | 64.1 | 17.5 s | 24.4 | 28.8 |
| c06 | `zemin_v3`, 30 s, alçal +2 | 59.0 | 58.8 | 18.5 s | 23.1 | 24.7 |
| c21 | `zemin_v1`, alçal +1 | 57.7 | 52.5 | 18.2 s | 7.5 | 32.8 |
| c20 | `zemin_v1`, adım −0.5 | 54.0 | 55.0 | 18.7 s | 13.8 | 34.4 |
| c19 | `zemin_v3`, 90 s, kayarak alçal | 53.9 | 46.2 | 15.9 s | 0.6 | 53.1 |

En kötüler: c10 (`gamma` 0.98, S −21.2), c04 (yol cezası −80, S −18.4), c11 (entropi 0.02, S −8.7). Üçü de
çoğunlukla süre doldurdu (%80–91).

**Tur 2** (1M adım, val_b64 × 10, tek tohum):

| Ayar | S | Kalkan B | Kalkan T | RL B | RL güvensiz | RL süre doldu |
|---|---|---|---|---|---|---|
| **c13** | **91.8** | 66.2 | **13.9 s** | 66.2 | 7.7 | 26.1 |
| c23 | 87.6 | 72.5 | 16.3 s | 64.8 | 21.7 | 13.4 |
| c00 | 86.5 | 71.6 | 16.1 s | 62.8 | 27.0 | 10.2 |
| c05 | 76.0 | 67.7 | 17.8 s | 63.4 | 13.6 | 23.0 |

**Tur 3** (val_b32 × 10, 3 tohum):

| Ayar, tohum | S | Kalkan B | Kalkan T | RL B | RL güvensiz | RL süre doldu |
|---|---|---|---|---|---|---|
| c13 s0 | 97.4 | 69.7 | 13.8 s | 69.7 | 7.2 | 23.1 |
| c13 s1 | 93.4 | 68.8 | 14.4 s | 68.8 | 8.8 | 22.5 |
| c13 s2 | 71.1 | 60.6 | 16.9 s | 60.6 | 15.3 | 24.1 |
| **c13 ortalama** | **87.3** | **66.4** | **15.1 s** | 66.4 | 10.4 | 23.2 |
| c23 s0 | 87.7 | 71.6 | 16.0 s | 64.1 | 21.6 | 14.4 |
| c23 s1 | 88.3 | 73.4 | 17.4 s | 72.8 | 5.3 | 21.9 |
| c23 s2 | 90.7 | 72.5 | 16.6 s | 72.8 | 14.7 | 12.5 |
| **c23 ortalama** | **88.9** | **72.5** | **16.6 s** | 69.9 | 13.9 | 16.3 |
| B1 (3 tohum, kıyas) | 76.7 | 66.7 | 16.6 s | 56.9 | 18.6 | 24.5 |

- **H15 sonucu** (Düzeltme 15, `kararla.py`): aday c23 (ortalama S en yüksek).
  - H15a tutmadı: ortalama +12.2 puan, ama tohum çiftlerinin yalnız birinde ≥ +5.
  - H15b tuttu: kalkanlı başarı 72.5 ≥ 63.7.
  - H15c tutmadı: 16.6 s > 13.5 s.
  - H15d tuttu: kalkansız güvensiz 13.9 ≤ 23.6.
  - **Karar: c23, B1/B2-s0'ın yerini almaz.**
- **c13 ve c23 farklı şeyler satıyor.** c13 hızlı ve az güvensiz, ama süre aşımı yüksek ve tohuma duyarlı. c23
  daha başarılı ve tohumlara karşı kararlı (87.7–90.7), ama yavaş. Hiçbiri 13.5 s'nin altına inmedi.

### 4.8 Tanılamalar (tanımlayıcı, karar değiştirmez)

| Soru | Sonuç | Betik |
|---|---|---|
| Test süresi uzarsa? | B2 s0 + kalkan: 30 s %76.9 → 90 s %88.1 | `sure_etkisi.py` |
| Düz alçalma + kalkan ne verir? | %65.3, B1 + kalkan %66.7'ye yakın | 2026-10-19 tanılaması |
| Başarısızlık nerede? | Çoğu, en yakın güvenli hedef 5–20 m uzaktayken | 2026-10-19 tanılaması |
| Bazı sahneler imkânsız mı? | Hayır. c13 s0'da her sahnede 10 denemeden en az 4'ü başarılı | 2026-10-20 sayımı |
| Argmax mı bozuyor? | Hayır (E1 tanılaması). B1 eğitim sahnelerinde %65.9, doğrulamada %61.6, iyi genelleşiyor | `stokastik_test.py` |
| Politika ne zaman yana kayıyor? | B2 s0 15 m üstünde %100 alçalıyor, ilk yanal eylem medyan 9.2 m'de | `eylem_irtifa_env.py` |

### 4.9 Eğitim hızı

| | Değer | Kaynak |
|---|---|---|
| Eğitim hızı, yanında ikinci eğitim varken | B1 166, B2 171, c23 165 adım/s → 1M adım ~1.7 saat | `progress.csv`, `time/fps` |
| c13, Tur 1 | 204 adım/s | aynı |
| c13 Tur 3 tohumları | duvar saati 6.2 saat; arada bilgisayar üç kez uyudu, hız ölçüsü değil | aynı |
| Ortamın tek adımı | 1.22 ms, tek çekirdekte ~820 adım/s | `tanilama/hiz_olc.out`, 2026-10-17 |
| Hız yaması (sonuç bit bit aynı) | ortam adımı 2.22 → 1.49 ms (A1 ayarı) | yürütme notu 2026-10-17 |

- Ortam tek başına ~820 adım/s, eğitim ~170 adım/s. Zamanın çoğu PPO güncellemesinde ve 4 ortamın tek süreçte
  sırayla koşmasında (_tahmin; profil gerekir).

---

## 5. PX4 ve AirSim

### 5.1 PX4 aktarımı (Gazebo)

- **F1 tanılama uçuşu:** uydurulan model kaydı yeniden oynattı. RMSE basamaklarda xy 0.036 / z 0.044 m/s,
  rastgele eylemlerde xy 0.084 / z 0.128 m/s. Gecikmesiz eski model xy 0.190 m/s veriyordu.
- **F4 pilotu** (aynı 15 başlangıç, ortam ↔ Gazebo + PX4): 15'in 13'ünde aynı sonuç (birinde kayıt yok). İniş
  noktası farkı medyan 0.10 m, en çok 0.77 m. Politika çıkarımı medyan 3.5 ms.

### 5.2 AirSim

- **Faz 1** (v3 hazır dünyada): AirSimNH'de güvenli/değil doğruluğu 0.754, mIoU 0.521. Eşik 0.85 / 0.55;
  geçmedi. v3 asfaltı "sert zemin" sanıyor.
- **Faz 3–5** (AirSimNH, 10 başlangıç, tek tohum, yoldan tetik):

| Kol | İndi | Güvenli zemin | SORA | Ağaç/çit/yapıya temas |
|---|---|---|---|---|
| Klasik mod, AirSim etiketi | 10/10 | 10 | 8 | 0 |
| Klasik mod, v3 | 10/10 | 4 (6 yol) | 4 | 0 |
| RL B2 s0, kalkansız | 10/10 | 7 | 5 | 1 |
| RL B2 s0, kalkan 10 m | 10/10 | 10 | 5 | 0 |
| Klasik, 5 m/s rüzgâr | 10/10 | 8 (temasa göre 10) | 5 | 0 |
| RL kalkansız, 5 m/s rüzgâr | 10/10 | 8 | 4 | 2 |

- **Faz 6** (kalkan 10 m, aynı 10 başlangıç):

| Kol | Çim | Sert | Yol | Diğer | Zemin kuralı |
|---|---|---|---|---|---|
| B2 s0, AirSim etiketi (önceki tur) | 7 | 3 | 0 | 0 | 10 |
| B2 s0, v3 | 1 | 0 | 9 | 0 | 1 |
| C1 s0, v3 | 1 | 0 | 9 | 0 | 1 |
| C1 s0, AirSim etiketi | 6 | 2 | 0 | 2 (harita sınırı; temas zemin) | 8 (temasa göre 10) |

  - **Yorum:** araç yolda doğup yolun tam üstünden tetiklendi. v3 yolu "sert" dediği için politika altındaki
    zemini kabul etti. Bu kurulum testi yanlı yapıyor (Arda'nın gözlemi). Sonraki kıyaslar havada başlangıçla.
- **Havada başlangıç** (`--havada`, B2 s0, AirSim etiketi, kalkan 10): 2/2 zemine indi (42.3 s ve 11.7 s).
- **Gösterim, 2026-10-19** (c13 s0, rastgele havada): 4 denemenin 1'i koştu, 16.0 s'de zemine indi. Öbür 3'ü
  Windows belleği yetmediği için başlamadı.
- **Çatı üstü gösterim, 2026-10-20** (c13 s0, AirSim etiketi, kalkan 10, 30 m, 6 çatının iç noktası):

| Çatı | Süre | İndiği yer |
|---|---|---|
| 1 | 17.2 s | garaj yolu |
| 2 | 19.1 s | çim |
| 3 | 17.1 s | çim |
| 4 | 16.8 s | çim |
| 5 | 18.0 s | çim (klasik dedektöre uygun en yakın alan 24.2 m) |
| 6 | 17.9 s | garaj yolu |

  - 6/6, ortalama 17.7 s (_hesap). Çatıya temas yok. Tek koşu, ölçüm değil.
  - Politika zemini düz sayıyor. Çatı ~8 m ise 10 m kalkan çatının ~2 m üstünde devreye girer (_hesap).
    v3 ile denenmedi.
- **Faz 7** (30 havada başlangıç; klasik ↔ RL, AirSim etiketi ↔ v3, final modelle): ön kayıtlı, birleşim turu
  bitince koşacak.

---

## 6. Yorum

### 6.1 30 s eğitimi neden çöküyor

- 30 s içinde güvenli yere ulaşamayan bölümlerde ajan iki bitişten birini seçmek zorunda: yanlış yere inmek ya
  da süreyi doldurmak. Hangisi ucuzsa varsayılan o olur.
  - `zemin_v1`: yol/ağaç −40, süre −50 → ajan alçalıyor (D).
  - `zemin_v3`: yol/ağaç −60, süre −50 → ajan bekliyor (F).
- **Kalkan eğitimin içinde olunca** 10 m altında yanlış yere alçalmak mümkün değil. Ajan güvenli yeri aramak
  zorunda kalıyor, kayarak alçalma da aramayı ucuzlatıyor. c13 bu yüzden çökmedi (_tahmin; mekanizma doğrudan
  ölçülmedi).

### 6.2 Başarıyı ne sınırlıyor

- 30 s'de en büyük kayıp süre aşımı (c13 s0: %23.1). 90 s tanılaması bu payın çoğunun gerçekten inilebilir
  olduğunu gösteriyor.
- Güvensiz iniş küçük (c13 s0: %7.2; 9 yol/ağaç, 14 yapı).
- Sahnelerin hiçbiri imkânsız değil. Sorun hedef 5–20 m uzaktayken zamanında oraya gitmek.
- **Sonuç:** başarıyı artırmanın en kısa yolu hızlanmak ya da süre dolmadan karar vermek.

### 6.3 Makaleyle kıyas

| | Makale | Bu çalışma |
|---|---|---|
| Başarı | %87.6 | %69.7 (c13 s0), %76.9 (B2 s0 + kalkan); 90 s'de %88.1 |
| Süre | 11.8 s | 13.8 s (c13 s0) |
| Başarı kuralı | 5 m'de görüşün çoğunluk sınıfı | altındaki nokta güvenli zemin + insan/araç tamponu (daha sıkı) |
| Sahneler | makalenin kendi sahneleri | MESSI fotoğrafları, eğitimde görülmeyen 32 sahne |

Kurallar ve sahneler farklı. Sayılar doğrudan karşılaştırılamaz, yalnız yön gösterir.

### 6.4 AirSim'den ders

- Politika, AirSim'in gerçek etiketiyle hafif ortamdaki gibi davranıyor: güvenli zemin, çatıdan kaçış.
- v3 maskesiyle başarısız. Sebep algı (asfalt → sert zemin), politika değil.
- Segmentasyon bu çalışmanın dışında ve Arda'nın kararı (AGENTS.md §3.6). Rapor yalnız etkiyi gösterir.

---

## 7. Öneriler (önceliğe göre)

1. **Ön kayıtlı zinciri bitir:** H19 (B2 hızlandırma, sürüyor), H16 (gözlem; tabanı c23), H18 (birleşim),
   Faz 7. H15 bitti.
2. **Süre dolmadan yedek iniş** (yeni ön kayıt). Son birkaç saniyede kalkanın onayladığı en yakın güvenli
   noktaya in. Hedef havuz: c13 s0'ın %23.1'lik süre aşımı. Risk: güvensiz iniş artabilir.
3. **Tohum çeşitliliği** (yeni ön kayıt): 3 tohumun oylaması ya da doğrulamayla tohum seçimi. Zayıf tohumun
   etkisini azaltır.
4. **Kolaydan zora eğitim** (yeni ön kayıt): önce güvenli alana yakın başlangıçlar.
5. **Eğitim hızı:** önce profil. Sonra ortamları ayrı süreçlere bölmek (`--vec subproc`) ya da tek eğitim +
   daha çok ortam. Bellek sınırı 12 GB.
6. **AirSim'de algı:** v3'ün AirSim davranışını Arda'ya rapor et. Kod değişikliği Arda'nın onayıyla.
7. **Çatı ve 3B engeller:** derinliği gerçek bir sensörden (lidar ya da stereo) almak, düz zemin varsayımını
   kaldırır. Gelecek iş.
8. **Final test:** zincir bitince, Arda "koş" deyince, bir kez.

---

## 8. Sınırlar

- **Eğitim dünyası 2B.** Fotoğraf düz bir zemin. Yükseklik ve 3B engel yok. Çarpışma yalnız derinlik eşiğiyle.
- **Doğrulama seti küçük:** 32 sahne. ±5 puanlık belirsizlik.
- **AirSim örneklemleri küçük:** faz başına 10 başlangıç, çoğunlukla tek model. Ön sonuç.
- **AirSim'de çoğu koşu gerçek etiketle.** Gerçek algıyla (v3) sonuç çok daha kötü.
- **IrYamim** Düzeltme 6'da bir kez kullanıldı.
- **Duvar saati** uyku süresini de sayıyor. Eğitim süreleri `time/fps`'ten okunmalı.

---

## 9. Kaynak dosyalar

| Ne | Nerede |
|---|---|
| Ön kayıtlar ve sonuçlar | `docs/onkayit/rl_f0_onkayit.md`, `docs/onkayit/airsim_faz*_onkayit.md` |
| Tarama günlüğü ve tablosu | `tools/rl_inis/arama/arama.log`, `tools/rl_inis/arama/ozet.md` |
| Karar kuralları | `tools/rl_inis/h*_karar.py`, `tools/rl_inis/arama/*_karar.py`, `kararla.py` |
| Çatı gösterimi | `tools/rl_inis/demo/cati_sec.py`, `tools/rl_inis/demo/cati/sonuc.txt` |
| Ham değerlendirmeler, modeller | sahibinin makinesinde `~/rl_inis/kos/` (depoda değil) |
| AirSim koşu günlükleri | sahibinin makinesinde `~/eland_veri/_gunlukler/` (depoda değil) |
