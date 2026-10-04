# Geri bildirim (Tur 2) — veri toplandı; kontrolcü tasarımı için elindekiler

> **Bu metin ne:** Acil iniş projesinde MATLAB/Simulink'te dikey iniş
> kontrolcüsü tasarlamak ve bir RL ajanı eğitmek için bana bir veri toplama
> görevi yazmıştın. Ardından ikinci tur kararlarını verdin: O1 ve O2 verildi,
> O2b verilmedi, K4 40 m'den, şartname değişiklikleri 1-7, W5 hükmü ve
> öncelik sırası. Görevi projede Claude Code uyguladı. **Yedi adımın hepsi
> bitti.**
>
> Aşağıda üç şey var: istediğin rapor maddeleri, kontrolcü tasarımında
> doğrudan kullanabileceğin veri / model / araçlar, ve kararını bekleyen
> konular.
>
> - **Tarih:** 2026-10-04.
> - **Kod:** `github.com/adakarda/slz-safelanding`, `main` @
>   `v5.4-veri-geri-bildirim-tur2`.
> - **Etiketler:** **ölçülen**, **_hesap** (ölçülenden hesaplanan),
>   **_tahmin** (varsayım içeren).
> - **İş tanımı:** en sondaki "Senden istediğim" bölümünü yanıtla.

---

## 1. Tek bakışta

| Adım | Kol | Bölüm | Sonuç | Duvar süresi |
|---|---|---|---|---|
| 1 | Kol 0: W2-W6 ×3, W1 ×3, 10 ada | 28 | 24 başarılı + 4 negatif örnek (beklenen başarısız) | 40 dk |
| 2 | K1: W2-W5 × {0.4, 0.7, 1.0, 1.5} × 2 | 32 | 32 | 44 dk |
| 3 | K2: D* {0.2, 0.35, 0.5} × W2-W5 × 2 | 24 | 24 | 34 dk |
| 4 | K5 rüzgârlı: basamak 1.2 / 2.0 m/s × 3 (+ rüzgârsız eş) | 6 + 1 | tanımlama (inmiyor) | 14 dk |
| 5 | K4: 40 m, W3 | 12 | 12 | 24 dk |
| 6 | Aşama 5: 5 bozucu × {K2 0.35, K1 1.0} × 2, W3 | 20 | 20 | 27 dk |
| 7 | K3: W2-W8 ×4 + 52 ada inişi | 80 | 80 | 109 dk |

- **Toplam 218 bölüm** (Tur 1'in 12 K5 ve 3 açık alan bölümü dahil).
- **Başarı:** 195 başarılı; kalan 23 beklenen (19 tanımlama, 4 negatif).
- **Kural ihlali yok.** Mevcut koda yalnız onaylı O1 ve O2 eklendi:
  parametreyle seçiliyor, varsayılanı kapalı. Alçalma yasası, PI, durum
  makinesi, mesajlar ve PX4 parametreleri (2.0 / 2.0) aynı.

## 2. İstediğin rapor maddeleri

**6a / W5 hükmü (a) — COMMIT tetiği:** EKF yüksekliğine bağlı.
- `emergency_landing_mode.hpp:322`:
  `if (altitude_m <= _landing_altitude_m && !_ident_enabled)`.
- `altitude_m = -pos_ned.z()` (`:269`), kalkış noktasına göre.
- `landing_altitude` 2.0 (`src/eland_sim/config/eland_params.yaml:286`).

**Eski taban çizgi:** `MPC_Z_V_AUTO_DN = MPC_Z_VEL_MAX_DN = 2.0`, 2026-09-05
20:54'ten beri (266 PX4 kaydının başlığı tarandı). Brifteki taban çizgi de
2.0 / 2.0 ile ölçüldü.

**W5, Kol 0 (W5 hükmü d), ölçülen:**
- COMMIT 3/3 bölümde yok.
- Temas 1.47-1.48 m/s.
- Temasta `h_ekf − h_gercek_hedef` 3.81-3.87 m.
- Temastan önce v_ref 1.40-1.45 m/s.
- PX4 `landed` temastan 1.05 s sonra.

Beklentinle aynı. Veri kipinde (devir yok, 2.5 m altında 0.5 m/s; K1/K2/K3'te
18 bölüm): temas 0.48-0.51 m/s, fark 3.92-4.04 m, COMMIT yok.

## 3. Kontrolcü tasarımı için elindekiler

### 3.1 Tesis: v_cmd → vz (PX4 hız döngüsü dahil), ölçülen

**K5**, açık çevrim kare dalga, 8 s, 22 m, yalnız gerçek yükseklik > 8 m,
Gazebo hızıyla:

| Basamak | K | θ (%10'a varış) | t90 | En büyük ivme | Yavaşlatma / hızlanma |
|---|---|---|---|---|---|
| 0.6 m/s | 1.000 | 0.06 s | 0.26 s | 3.6 m/s² | 3.7 / 3.0 |
| 1.2 m/s | 0.992 | 0.04 s | 0.28 s | 6.1 m/s² | 6.2 / 5.4 |
| 2.0 m/s | 0.997 | 0.06 s | 0.36 s | 6.7 m/s² | 6.2 / 7.9 |
| 2.5 m/s | 0.991 | 0.06 s | 0.40 s | 8.4 m/s² | 6.3 / 8.5 |

- **EKF hızıyla:** K 1.01-1.02, θ 0.06-0.08 s, t90 0.28-0.44 s.
- **Model:**
  - **K ≈ 1, θ ≈ 0.05 s.** Eski 0.28 s geçersiz; o değerle türetilen her
    şey yeniden yapılmalı.
  - Küçük basamakta birinci mertebe, τ ≈ 0.1 s (_hesap).
  - Büyük basamakta ivme sınırlı ve asimetrik: yavaşlatma ~6.2 m/s²,
    aşağı hızlanma ~8.5 m/s².
  - Izgara 50 Hz, θ çözünürlüğü 0.02 s.
- **2.5 m/s yan rüzgârda (K5r) aynı:** 1.2 m/s basamakta K 0.994, θ 0.06,
  t90 0.30; 2.0 m/s'de K 0.992, θ 0.06, t90 0.36. Rüzgâr yatayda 2.7° eğim
  verir, dikey tesisi değiştirmez.
- **K4, kapalı çevrim tanıma** (v_ref → vz, mevcut PI içinde): 12 uçuş,
  40 m'den.
  - 20 s çoklu-sinüs: 0.05-1.0 Hz, 7 frekans, 0.9 ± 0.6 m/s.
  - 20 s basamak: 0.3 ↔ 1.5 m/s, 1.5-3.5 s bekleme.
  - Sıra tohumla değişiyor; kırpma yok.
  - vz_gercek − v_ref RMS 0.16-0.23 m/s (geçici yanıt dahil).

### 3.2 Bugünkü kapalı çevrim, ölçülen

**Parametreler** (`eland_params.yaml:286-337`):
- **PI:** Kp 0.8, Ki 0.6, Kaw 1.0, Kd 0.
- **Alçalma yasası:**
  - İrtifa yasası `clamp(0.35·h_ekf, 0.3, tavan)`.
  - Bölge kadraja sığınca (`view_bounded`) alan yasası
    `clamp(tavan·(1−ρ), 0.3, tavan)`.
  - Tavan `clamp(0.20·√alan, 0.3, 1.5)`.
- **COMMIT:** EKF 2.0 m'de giriliyor; hız setpoint'i yere kadar
  `descentSpeed(h)`.

**K1 sabit hız takibi** (VALIDATE'in ilk 2 s'si hariç):

| v_ref | Bölüm | vz_gercek − v_ref ort / RMS | vz_ekf − v_ref ort / RMS |
|---|---|---|---|
| 0.4 | 7 | −0.002 / 0.007 m/s | +0.000 / 0.005 |
| 0.7 | 8 | −0.007 / 0.010 | +0.001 / 0.007 |
| 1.0 | 8 | −0.011 / 0.013 | +0.003 / 0.009 |
| 1.5 | 8 | −0.032 / 0.034 | −0.006 / 0.008 |

- **İç döngü sabit hızı ~1 cm/s tutuyor.**
- **1.5 m/s'de gerçek hız 3 cm/s düşük:** EKF hız kestirimi kaynaklı, PI'dan
  değil.

**K2 kâhin sabit ıraksama:** `v = D*·h_gercek`, [0.3, 1.5] içinde, 2.5 m
devir.

| D* | Tavanda (1.5 m/s) | Sabit ıraksamada | D − D* RMS |
|---|---|---|---|
| 0.2 | 4.6 s | 5.6 s | 0.007 1/s |
| 0.35 | 7.1 s | 1.6 s | 0.004 1/s |
| 0.5 | 7.6 s | 0.4 s | 0.013 1/s |

**Pencere içinde iç döngü ıraksamayı çok iyi tutuyor, ama pencereler kısa**
(kırpma ve devir yüzünden).

### 3.3 Görüntü sinyali ρ

- **Tanım:** ρ = görüntü merkezinin altındaki güvenli bölgenin piksel payı.
  Bölge kadraja sığınca `ρ = A/(4.22·h²)`; buradan `ρ̇/ρ = 2D`, D = v/h
  (brif §6).
- **Kayıtta:** maske başına (10 Hz) `rho`, `view_bounded`, yakalama damgası
  `t_yakalama`. Geometrik doğru değer `rho_hesap = A_gercek/(4.22·h_kamera²)`
  (yalnız sığarken anlamlı).
- **Gecikme:** maske yakalamadan kayda p50 ~19 ms, p90 ~40 ms, p99 ~95 ms.
- **Mod ρ'yu bugün yalnız aday mesajı içinde, ~1.8 Hz'de alıyor.** 10 Hz ayrı
  yayın (madde A) hâlâ onay bekliyor.
- **Aşama 5 (20 bölüm):** ρ'nun temiz ve bozuk hâli aynı yakalama damgasıyla
  yan yana kayıtlı (`rho_temiz`, `rho_bozuk`, `view_bounded_bozuk`,
  `t_alma_bozuk`).

| Bozucu | ort \|ρ_bozuk − ρ_temiz\| | Ek gecikme |
|---|---|---|
| Sınır titremesi ±2 px | 0.000 | — |
| %2 piksel çevirme | 0.011 | — |
| Karelerin %5'inde merkez bölge kaybı | 0.020 | — |
| 0.2 s gecikme | — | 203 ms |
| İçerik 3 karede bir güncellenir | 0.010 | — |

- **Bu kollarda inişi politika sürdü, ρ değil.** Bozuk ρ, ρ-tabanlı bir
  yasanın **çevrimdışı** sınanması için; uçuşa etkisi yoktu.
- **Gazebo etiketleri kusursuz:** tek piksel keskin sınır, lens bozulması yok.
  Bozucu seviyeleri parametre; eğitilmiş modelin hata dağılımı iddiası değil.

### 3.4 Kollar ve ne işe yarar

| Kol | Bölüm | İçerik | Kullanım |
|---|---|---|---|
| Kol 0 | 31 | mevcut sistem: W1-W6, 10 ada, açık alan | taban çizgi; 4 negatif örnek (aday yok → kör iniş) |
| K1 | 32 | sabit v_ref 0.4 / 0.7 / 1.0 / 1.5 | kapalı çevrim takip; hız başına ρ(t), ρ-h ilişkisi |
| K2 | 24 | kâhin sabit ıraksama (Gazebo yüksekliğiyle) | uzman gösterimi, ıraksama takibi (pencere kısa) |
| K3 | 80 | rastgele v_ref: parça-sabit U[0.3, 1.5] (0.5-2 s) ya da yasa × U[0.5, 1.5]; her bölümde ayrı tohum | çevrimdışı RL (davranış politikası `v_ref_dis` kayıtlı) |
| K4 | 12 | 40 m'den çoklu-sinüs + basamak | kapalı çevrim tanıma |
| K5 | 12 | açık çevrim kare dalga, rüzgârsız | tesis tanıma |
| K5r | 6 + 1 | aynısı, 2.5 m/s rüzgâr + rüzgârsız eş | rüzgâr etkisi |
| Aşama 5 | 20 | 5 bozucu, ρ temiz/bozuk yan yana | ρ yasasının gürültü/gecikme dayanıklılığı |

### 3.5 Dosyalar, MATLAB

- **Kök:** `~/eland_veri/` (WSL; Windows'tan
  `\\wsl.localhost\ubuntu\home\arda\eland_veri`).
- **`tum_ozet.csv`:** 218 satır. Kol, dünya, tohum, bölme, başarı, gerçek
  temas anı ve hızı, PX4 bayrak gecikmeleri, COMMIT irtifaları (EKF ve
  gerçek), ABORT/HOLD, aday kayıpları.
- **`_bolme/{train,val,test}/birlesik_<bölme>.mat`:** `ep` (bölüm tablosu),
  `duzenli`, `maske`, `karar`. Sayısal sütunlar float32 ve `ep_idx` taşıyor
  (0 = `ep`'in ilk satırı).
  - Bölme anahtarlı: bir ada ya da bir dünya+tohum bütünüyle tek bölmede;
    aynı başlangıç bölmeler arasında sızmıyor.
  - Anahtar düzeyinde %73 / %12 / %15, bölüm düzeyinde 140 / 31 / 47.
  - **K4 ve Aşama 5'te test yok.**
- **Bölüm başına `ep.mat`:** `duzenli`, `maske`, `karar`, `gecis`,
  `ozet_json` (`jsondecode`). Ayrıca CSV'ler, `kosul.yaml` (koşullar, PX4
  parametreleri, git sürümü) ve ham maskeler (`maskeler.npz`).
- **Önemli sütunlar (`duzenli`, 50 Hz, her kanalın son değeri + `_yas_ms`):**
  - **Zaman ve durum:** `t_gz` (sim s); `durum` (0 SEARCH … 2 VALIDATE …
    5 COMMIT).
  - **EKF:** `h_ekf` (**kalkış noktasına göre**), `vz_ekf`.
  - **Referans ve komut:**
    - `v_ref`: modun referansı, ≤ 10 Hz.
    - `v_ref_dis`: politikanın referansı, 50 Hz.
    - `v_cmd`: PI çıkışı, PX4'e giden.
    - `I_hesap`: integral, geri çatım.
    - `aktif_girdi`: 1 alan yasası, 0 irtifa yasası.
  - **Gerçek değerler (Gazebo):** `h_gercek_hedef`, `h_gercek_zemin`,
    `vz_gercek_hesap` (Gazebo z türevi), `x/y_gercek`.
  - **Tutum:** roll, pitch, yaw.
  - **PX4 bayrakları:** `landed`, `ground_contact`.
- **İşaretler:** dikey hızlar **aşağı +**, yükseklikler yukarı +.
- **Sözlük:** `tools/veri/data_dictionary.md`.

### 3.6 Araçlar (yeni dosyalar, Python)

- `tools/veri/tesis_analizi.py`: basamak başına K, θ, t90, ivme.
- `tools/veri/pi_tekrar.py`: PI'nın çevrimdışı tekrarı.
- `tools/veri/zaman_hizasi.py`: kanal yaşları, gecikme dağılımı.
- `tools/veri/ozellik.py`: maskeden ρ ve diğer öznitelikler, çevrimdışı (ham
  maskelerle yeniden hesaplanabilir).
- `tools/veri/birlestir.py`: veri seti ve bölme.
- `tools/veri/ruzgar_karsilastir.py`, `adim_ozet.py`.
- **Kapalı çevrim deneme altyapısı:** tasarladığın dış döngüyü **moda
  dokunmadan** simde deneyebilirsin.
  - `tools/veri/politika.py`'ye yeni bir kip eklenir, `/eland/veri/v_ref`'e
    yayınlar. Mod (`veri_toplama_kipi: true`) VALIDATE'te onu PI'ya referans
    verir.
  - ρ gerekiyorsa kip maskeden 10 Hz hesaplar (`ozellik.py`).
  - `tools/veri/kosu.sh` / `toplu.sh` bölümü kaydediciyle birlikte uçurur.
  - **Yalnız simülasyon:** COMMIT devri Gazebo yüksekliğiyle (2.5 m).

### 3.7 Veriyi kullanırken dikkat

1. **`h_ekf` hedef yüzeye göre değil.** Gerçek yükseklik için
   `h_gercek_hedef`; W5'te fark ~4 m.
2. **Analizleri `t_temas_gercek`'te kes.**
   - PX4 `landed` gecikmesi temas hızına bağlı (ortanca): 0.3 m/s'lik temasta
     ~4.7 s, 0.5 m/s ve üstünde ~1.1 s.
   - Bir bölüm (`kol0_veri_ada_t2010_t1`) düzgün temastan 7.5 s sonra
     devrildi ve 62.5 m savruldu. Dünyada bir hareketli kişi var.
3. **Başarı ölçütü hız içermiyor.** 6 sert temas "başarılı" sayılıyor: W5
   Kol 0 ×3 (1.47 m/s) ve K3 ×3 (1.10-1.33 m/s, madde 5.1).
   `temas_dikey_hiz_gercek_hesap_mps` ile süz.
4. **`v_ref` ≤ 10 Hz geliyor, `I_hesap` ±0.03 m/s belirsiz.** O2b
   verilmediği için tekrar: komut farkı RMS 0.030 m/s. MATLAB'da `v_ref`'i
   yasadan yeniden hesaplamak daha doğru.
5. **`karar.area_m2` 40×40 m harita tavanıyla sınırlı.** Büyük bölgelerde
   gerçek alan değil.
6. **EKF sağlığı (yeniden toplanan veride):** vz_ekf − vz_gercek RMS
   0.01-0.04 m/s (K1), 0.02-0.13 m/s (K2/K4 dinamik).
7. **Rüzgâr etiketi kalibre edildi.** Ham Gazebo ölçeği 2.5 m/s'yi ~8 m/s
   gibi yapıyordu (gz ölçeğin karesini alıyor). Şimdi: motor modelinin rotor
   sürüklemesi (0.59 N) + gövde sürüklemesi (0.375 N, _tahmin). Ölçülen
   toplam eğim 2.67°.

## 4. Yol boyunca bulunup düzeltilenler

Ayrıntı `docs/VERI_TOPLAMA.md`, "Tur 2 — yürütme".

- **Sızan süreçler:** ilk K1/K2 toplaması çöpe gitti, yeniden toplandı.
  - `run_sim.sh` betikle kapatılınca `tracker_node` ve `obstacle_driver`'ı
    bırakıyordu; 64 çift birikti.
  - EKF dikey hız hatası 1.2 m/s'ye çıktı; mod DDS keşfinde zaman aşımına
    uğradı.
  - 56 bölüm karantinada. Kayıt betiği artık her bölümün süreçlerini kendisi
    kapatıyor.
- **W8 tohum 3:** araç 0.52 m'lik nesnenin üstünde doğdu, gerçek yükseklikler
  0.5 m kaydı. Başlangıç çekimi düzeltildi, bölüm yeniden uçuruldu.
- **Uçurulmadan düzeltilenler:**
  - rüzgârlı ikizlerin başlangıcı farklıydı,
  - K3'te 30 ada aynı rastgele diziyi alıyordu.

## 5. Kararını bekleyenler

1. **COMMIT'te donmuş ρ → sert temas (mevcut mod).**
   - **Mekanizma:** COMMIT aday dinlemiyor (`hpp:622-623`). `view_bounded`
     doğruyken yüksekte girilirse `descentSpeed` (`:593-618`) donmuş ρ ile
     `tavan·(1−ρ)` verir. Hız irtifadan bağımsız sabit kalıyor, yere kadar
     1.1-1.33 m/s.
   - **Ne zaman yüksekte giriliyor:** aday 3 kez kaybolunca ("committing
     anyway"), 6.8-14.6 m'de.
   - **Sıklık:** 218 bölümde 9 erken COMMIT, 3'ü sert.
   - Koda dokunulmadı.
2. **K2 devir irtifası:** sabit ıraksamanın uzun örneği gerekiyorsa
   `veri_devir_irtifasi` düşürülebilir (şu an şartnamedeki 2.5 m).
3. **A) 10 Hz ayrı ρ yayını** (mesaj + dedektörde ~10 satır + modda ~25
   satır, varsayılan kapalı): uygulanmadı, onay bekliyor.
4. **`run_sim.sh` temizlik listesine iki düğüm:** veri araçları kendi
   temizliğini yapıyor, mevcut betik için onay bekliyor.

---

## Senden istediğim

1. **İç döngü:** §3.1-3.2'deki ölçülen tesisle (K ≈ 1, θ ≈ 0.05 s,
   asimetrik ivme sınırı, K4 frekans verisi) PI'yi ve kazanç türetimini
   güncelle. Eski θ = 0.28 s'ye dayanan her şeyi işaretle.
2. **Dış döngü (görüntü-tabanlı):**
   - ρ ya da ıraksama (`ρ̇/ρ = 2D`) tabanlı yasanı öner.
   - Gecikme bütçesi: maske ~20 ms + 10 Hz örnekleme; mod yolunda ~1.8 Hz.
   - Aşama 5 verisiyle gürültü / gecikme / bayat kare dayanıklılığını
     çevrimdışı nasıl sınayacağını yaz.
   - A) 10 Hz yayın şart mı, söyle.
3. **COMMIT (madde 5.1):**
   - Düzeltme öner: parametreyle, varsayılan kapalı (ör. COMMIT'te
     `min(alan, irtifa)` ya da yalnız irtifa yasası).
   - Başarı ölçütüne bir temas hızı eşiği eklensin mi, eklenirse kaç m/s?
4. **K2:** uzun sabit ıraksama örneği gerekiyor mu? Gerekiyorsa devir
   irtifası ve bölüm sayısı.
5. **RL:**
   - K3 (80) + K1/K2/Kol 0 ile gözlem, eylem (`v_ref_dis`) ve ödülü tanımla.
     Gerçekte ölçülebilen sütunlar gözlem, Gazebo sütunları yalnız ödül ve
     değerlendirme.
   - 80 rastgele iniş yeterli mi, ilk plandaki ≥ 400'e çıkalım mı?
6. **Kapalı çevrim deneme planı:** tasarladığın yasayı §3.6'daki altyapıyla
   denemek için dünyalar, tohumlar, bölüm sayısı ve metrikler.
7. **Kurallar aynı:** mevcut koda dokunan her şey onaylı, parametreyle,
   varsayılan kapalı. Önerilerini buna göre yaz.
