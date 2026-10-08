# Kontrolcü tasarımı — nerede, nasıl yürüyor

> **Bu dosya ne:** görüntü-tabanlı dikey iniş kontrolcüsü işinin durumu.
> Projeye sonradan katılan biri (ya da AI ajanı) yalnız GitHub'a bakarak
> şunları anlasın:
> - kim, nerede tasarlıyor;
> - şimdiye kadar ne kararlaştırıldı;
> - kodda ne var;
> - sırada ne var.
>
> Güncel: 2026-10-08.

---

## 1. İş nasıl yürüyor

- **Tasarımı proje sahibi (@adakarda) yapıyor,** ayrı bir AI sohbetinde,
  MATLAB/Simulink ile. Dokümanlarda "diğer sohbet" diye geçer.
- **Bu depo ve içinde çalışan Claude Code o tasarıma hizmet ediyor:**
  ölçüm yapıyor, veri topluyor, onaylanan kod değişikliklerini uyguluyor.
- **Alışveriş turlar hâlinde (Tur N):**
  1. Diğer sohbet ister.
  2. Proje sahibi bunu buraya aktarır.
  3. Burada plan yazılır, onay alınır, uygulanır ve ölçülür.
  4. Sonuç bir prompt olarak yazılır (`docs/geri_bildirim/`).
  5. Proje sahibi onu diğer sohbete götürür. Diğer sohbetin kararları
     `VERI_TOPLAMA.md`'de "Tur N" bölümlerinde kayıtlı.
- **Depoda olmayanlar:** Simulink modeli ve diğer sohbetin kendisi.
  Buradakiler yalnız oradan gelen kararlar, durum özetleri (§6) ve oraya
  gönderilenler.
  Proje sahibi modeli eklemek isterse yeri `kontrolcu/` (öneri).
- **Tasarım bitince beklenen çıktı:**
  [`KONTROLCU_TASARIM_BRIEF.md`](KONTROLCU_TASARIM_BRIEF.md) §12 biçiminde.
  - İçeriği: girdiler, ayrık denklemler, parametreler, kip geçişleri,
    sıfırlama, doyum, kabul ölçütü.
  - Uygulaması: mevcut yasanın yanına, parametreyle seçilen ayrı bir kip.
    Aynı senaryolarda yan yana karşılaştırılacak.

## 2. Problem, kısaca

- **Bugünkü durum:**
  - Alçalma yasası bölge alanından bir hız tavanı ve kapsama oranından (ρ) bir
    yavaşlama üretiyor.
  - Ama açık alanda ve geniş adalarda bölge kadraja sığmıyor, ρ doyuyor.
  - Yavaşlama pratikte kameradan değil EKF irtifasından geliyor (ρ dalı
    inişin %0'ında aktif).
- **Hedef:** görüntüden ölçülen bir büyüklükle alçalma ve
  geçersizken irtifa yasasına sıçramasız yedek.
  - Görüntü büyüklüğü ρ olabilir, ıraksama da (ρ̇/ρ = 2D, bölge kadraja
    sığarken).
  - Asla asılı kalmamalı, temas hızı küçük kalmalı.
- **Tasarım kısıtları:** brif §9.
  - Çıktı tek skaler, [0, 1.5] m/s.
  - Mevcut iç PI referansı izlemeye devam eder.
  - Yatay eksene ve PX4 iç döngülerine dokunulmaz.
- **Bütün sayılar:** [`KONTROLCU_OLCUMLERI.md`](KONTROLCU_OLCUMLERI.md).

## 3. Turlar ve kararlar

| Tur | Tarih | Diğer sohbetin istediği / kararı | Burada yapılan | Rapor |
|---|---|---|---|---|
| 1 | 2026-10-03 | Kontrolcü ve RL için veri toplama (7 aşamalı şartname). Kararlar: ada çevresi "arazi tehlikesi" sınıfı, gerçek Gazebo rüzgârı, PX4 parametreleri bugünkü hâliyle | kaydedici, ada dünyaları, rüzgârlı model, K5 tesis testi (θ 0.04-0.06 s; eski 0.28 s geçersiz) | `geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM.md` |
| 2 | 2026-10-03 | O1 (dünya/model seçimi) ve O2 (veri kipi) onay; K4 tanımı; şartname düzeltmeleri | 218 bölüm toplandı; rüzgâr kalibrasyonu; veri seti ve bölme | `geri_bildirim/VERI_TOPLAMA_RAPOR_TUR2.md`, `..._TUR2.md` |
| 3 | 2026-10-04 | A: ρ'yu maske hızında yayınla. B: COMMIT'te irtifa yasası. C: bozucular gerçekten uygulandı mı. D: eğiklik ve ρ. E: örnek MATLAB seti | A `/eland/rho` (varsayılan kapalı), B `commit_irtifa_yasasi` (o zaman varsayılan kapalı); C, D, E çevrimdışı | `..._TUR3.md`, `..._TUR3_SONUC.md`, `..._TUR3_AYRINTILI.md` |
| 4 | 2026-10-04 | Mod `/eland/rho`'yu henüz kullanmasın. `commit_irtifa_yasasi` varsayılanı `true`. W5 gözlemcinin test senaryosu olsun. Başarıya temas hızı (0.5 / 1.0 m/s). Sonra: birincil ölçüt `basarili_v10`, W5 yalnız 1.0, `tum_ozet`'e sütun, `run_sim` temizliği | hepsi uygulandı ve doğrulandı (48 bölüm) | `..._TUR4.md`, `..._TUR4_SONUC.md` |
| 4 ek | 2026-10-04 | `run_sim.sh` mod seçme kontrolü ve yeniden deneme (parametreli). Toplu listelerde `RUN_SIM_MOD_TEKRAR=2` | uygulandı (varsayılan kapalı), sınandı | `..._TUR4_EK.md` |

Ayrıntılar: [`VERI_TOPLAMA.md`](VERI_TOPLAMA.md), aynı adlı bölümler.

## 4. Kodda bugün ne var (kontrolcü açısından)

`src/eland_sim/config/eland_params.yaml` ve `src/eland_mode/`.

| Parametre | Varsayılan | Ne | Etiket |
|---|---|---|---|
| `descent_size_gain`, `descent_min_mps`, `descent_max_mps`, `descent_altitude_gain` | 0.20, 0.3, 1.5, 0.35 | alçalma yasası: tavan `0.20·√A`, ρ dalı (`view_bounded`'ken), irtifa yedeği `0.35·h` | `v2.7` ve öncesi |
| `descent_closed_loop`, `descent_kp`, `descent_ki`, `descent_kaw` | true, 0.8, 0.6, 1.0 | iç döngü: PI + ileri besleme, geri hesaplamalı anti-windup | `v2.7` |
| `landing_altitude` | 2.0 m | COMMIT eşiği (EKF irtifası) | |
| `commit_irtifa_yasasi` | **true** (yaml); düğümün kendi varsayılanı false | COMMIT'te hız `clamp(0.35·h, 0.3, tavan)`; `false` = eski yasa (donmuş ρ) | `v5.7`, varsayılan `v6.1` |
| `detector_node.publish_rho` | false | `/eland/rho` (`GoruntuKapsami`: ρ, `view_bounded`, yakalama damgası), ~10 Hz. **Mod henüz dinlemiyor** | `v5.7` |
| `veri_toplama_kipi` | false (yalnız C++'ta) | veri kipi: VALIDATE referansı `/eland/veri/v_ref`'ten, Gazebo hedef yüksekliği < 2.5 m'de devir | `v5.0` |
| `ident_enabled` | false (yalnız C++'ta) | tesis tanımlama kipi: kare dalga, açık çevrim, iniş yok | `v2.9` |
| `RUN_SIM_MOD_TEKRAR` (ortam) | yok = kapalı | `run_sim.sh` modu seçti mi kontrol eder, gerekirse yeniden gönderir | `v6.5` |

## 5. Açık / sırada

| İş | Kimde | Not |
|---|---|---|
| Modun `/eland/rho`'yu kullanması (görüntü-tabanlı dış döngü) | diğer sohbet: tasarım Simulink'te doğrulanınca brif §12 biçiminde tarif gelecek | Simulink'te nominal çalışıyor; aykırı kare kapısı ve anti-windup orada henüz açık (§6). Ölçülen: ~10 Hz, yakalamadan alınmasına p50 19.5 / p90 39.6 ms, BEST_EFFORT |
| W5 / yükseltilmiş hedef: hedefe göre yükseklik kestirimi (gözlemci) | diğer sohbet | Simulink'te (gürültüsüz): 3.85 m yanlış başlangıçla hata 6.5 s'de ~0.17 m, temas 0.30 m/s (§6). Gazebo'da ölçülen: EKF temasta hedefin 3.8-4.0 m üstünde, temas 1.47-1.49 m/s |
| İç döngü kazançlarının yeni θ ile IMC türetimi | açık | eski türetim θ = 0.28 s ile; yeni θ 0.04-0.08 s |
| ρ̇/ρ = 2D'nin gürültülü veride sınanması | açık | statik ilişki ρ = A/(4.22·h²) doğrulandı (eğiklik < 5°'de RMS ≤ 0.002) |
| Uzun sabit ıraksama örnekleri | karar bekliyor | K2'de pencereler kısa (D* = 0.5'te 0.4 s); devir irtifası düşürülebilir ya da yalnız D* = 0.2 kullanılır |
| Gerçek segmentasyon modeli | ertelendi | maske şu an Gazebo'nun kusursuz etiketi |

## 6. Simulink'teki tasarım (durum: 2026-10-05)

### 6.1 Diğer sohbetin özeti (olduğu gibi)

Proje sahibi 2026-10-08'de aktardı. Metin değiştirilmedi.

```text
Kontrolcü tasarımı durumu (Simulink, 5 Ekim)

Mimari: iç çevrim (PI + ileri besleme, v_ref'i izler) + dış çevrim
(ρ'dan yükseklik kestiren gözlemci + alçalma yasası).

Simulink'te kurulup çalıştırılanlar (nominal, gürültüsüz):
- Plant (K5 verisinden): K=1, τ=0.1 s, gecikme 0.055 s, ivme sınırı +8.5/−6.2.
- İç çevrim: Kp 0.8, Ki 0.6, doyum [0, 1.5] m/s.
- Ortam: h' = −vz, ρ = min(1, A/(4.22·h²)), A = 100 m².
- Sensör: 10 Hz örnekleme + 0.03 s gecikme.
- Alçalma yasası: v_ref = sat(0.35·ĥ, 0.3, 1.5).
- Gözlemci: x = ln h, c = ln(A/4.22) bilinmiyor.
  ν = ln ρ_ölç − (c − 2x);  x' = −vz·e^(−x) − 3.5·ν;  c' = −5·ν.
  ρ_ölç ≥ 0.75 iken düzeltme kapalı.
- Sonuç: 3.85 m yanlış başlangıç yüksekliğiyle bile hata 6.5 s'de
  yaklaşık 0.17 m'ye indi, temas hızı 0.30 m/s.

Yalnızca Python kopyasında denenenler (Simulink'te doğrulanmadı):
- %2 aykırı kare, korumasız: koşuların yaklaşık yarısında temas > 1.0 m/s.
  |ν| > 0.5 kapısıyla düzeliyor.
- A = 400 m² ve yanlış başlangıç: gözlemci düzeltemiyor, temas 0.72 m/s.

Yapılmayanlar:
- Simulink plant'i gerçek K5 verisiyle üst üste çizilmedi.
- ρ formülü Gazebo'daki gerçek ρ ile karşılaştırılmadı.
- Aykırı kare ve kapı Simulink'te çalışmıyor (kablolama hatası).
- Anti-windup doğrulanmadı.
- Mod koduna hiçbir şey girmedi, Gazebo'da denenmedi.
```

### 6.2 Depodaki ölçümlerle karşılaştırma

> Claude Code, 2026-10-08. Simulink modeli burada açılmadı, koşulmadı.
> Yalnız yukarıdaki varsayımlar depodaki ölçümlerle karşılaştırıldı.
> § numaraları [`KONTROLCU_OLCUMLERI.md`](KONTROLCU_OLCUMLERI.md)'nin.
> _hesap = elle hesap, ölçüm değil.

| # | Simulink'te | Depoda | Sonuç |
|---|---|---|---|
| 1 | Tesis K = 1, τ = 0.1 s, gecikme 0.055 s | K 0.99-1.02, θ 0.04-0.08 s, küçük basamakta τ ≈ 0.1 s. t90 ölçülen 0.26-0.44 s; modelin t90'ı 0.055 + 2.3·0.1 ≈ 0.29 s (_hesap) (§1.2) | Uyumlu. Büyük basamakta t90'ı ivme sınırı uzatıyor. K5 verisi Release'te (12 bölüm), üst üste çizim için hazır. |
| 2 | İvme sınırı +8.5 / −6.2 m/s² | Hızlanma ~8.5, yavaşlatma ~6.2 m/s² (1.5 m/s genlik) (§1.2) | Uyumlu ("+" = alçalma hızını artırma kabul edildi). |
| 3 | PI: Kp 0.8, Ki 0.6, doyum [0, 1.5] | Kodda aynı. Ek olarak Kaw = 1.0 geri hesaplamalı anti-windup ve VALIDATE'e her girişte integral sıfırlama (§2.2) | Anti-windup için veri hazır: bölümlerde `v_ref`, ölçülen hız ve gönderilen komut var. `tools/veri/pi_tekrar.py` aynı karşılaştırmayı Python'da yapıyor. `v_ref`'i yeniden hesapla ([`VERI_SETI.md`](VERI_SETI.md) tuzak 4). |
| 4 | ρ = A/(4.22·h²) | Gazebo'da ölçülerek doğrulandı: eğiklik < 5°'de RMS 0.0014-0.0019, ≥ 5°'de 0.010-0.020 (§4.4, Tur 3 D) | "ρ formülü Gazebo ile karşılaştırılmadı" maddesinin karşılığı depoda var. |
| 5 | `min(1, ·)` ve kapı: ρ_ölç ≥ 0.75'te düzeltme kapalı | Formül yalnız `view_bounded = 1` iken geçerli. Sığma bittiği anda ρ: kare bölgede ~0.75, daire bölgede ~0.59 (§4.1). Bunun üstünde ρ formülü izlemez, 1'e doğru doyar (§4.2). `/eland/rho` mesajı `view_bounded` bayrağını taşıyor (§3.3) | Kare bölge için 0.75 eşiği doğru. Daire bölgede 0.59-0.75 arası formül dışı. Karar diğer sohbette. |
| 6 | Sensör 10 Hz, gecikme 0.03 s | 9.8-10.0 Hz; yakalama → alma p50 19.5 / p90 39.6 ms (§3.3) | Uyumlu. p90 ≈ 0.04 s. |
| 7 | A = 100 m², başlangıç hatası 3.85 m | W5: 10×10 m platform (100 m²), 4 m yüksek. EKF temastan hemen önce hedefin 3.81-4.04 m üstünde (§5.4) | Bu test W5'in karşılığı. |
| 8 | A = 400 m²'de düzeltme yok (yalnız Python) | 20×20 m bölge yalnız 11.2 m üstünde kadraja sığar. Açık alan (~1270 m²) ~20 m altında sığmaz (§4.1) | Olası açıklama: düzeltme penceresi kısa (_hesap, sınanmadı). Açık alanda gözlemci hiç düzeltme almaz. |
| 9 | c = ln(A/4.22) bilinmiyor | `/eland/candidate` `area_m2` yayınlıyor (~1.8 Hz), ama 40×40 m harita tavanıyla sınırlı, gerçek alan değil (§3.2; `VERI_SETI.md` tuzak 3) | Bilgi. |
| 10 | Yasa sat(0.35·ĥ, 0.3, 1.5) | Kodda tavan `clamp(0.20·√A, 0.3, 1.5)`: A < 56 m²'de 1.5'ten düşük (_hesap) (§2.1) | A = 100'de aynı. |
| 11 | COMMIT aşaması tarifte yok | Modda EKF h < 2.0 m'de COMMIT: PI yok, `v = clamp(0.35·h_ekf, 0.3, tavan)` (§2.2, §6.4). W5'te h_ekf 2 m'nin altına inmiyor; COMMIT'e hiç girilmiyor (§5.4) | Açık soru: mod koduna girerken ĥ COMMIT eşiğinde de kullanılacak mı. |

## 7. Katkı vermek istersen

- **Kontrolcü tarafı (MATLAB/Simulink; simülasyon kurmak gerekmez):**
  1. Veriyi indir: [`VERI_SETI.md`](VERI_SETI.md).
  2. Ölçümleri ve brifi oku: [`KONTROLCU_OLCUMLERI.md`](KONTROLCU_OLCUMLERI.md),
     [`KONTROLCU_TASARIM_BRIEF.md`](KONTROLCU_TASARIM_BRIEF.md).
  3. Tasarım ya da analiz sonuçlarını proje sahibiyle paylaş: issue, PR ya
     da doğrudan. Simülasyonda denenmesi gereken bir şey varsa brif §12
     biçiminde yaz.
- **Simülasyon tarafı:** kurulum [`../README.md`](../README.md), kurallar
  [`../AGENTS.md`](../AGENTS.md).
  - Uçuş davranışını değiştiren her şey önce planla ve proje sahibinin
    onayıyla.
  - Parametreli, varsayılan kapalı; kapalıyken eski davranış bir koşuyla
    gösterilmeli.
