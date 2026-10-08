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
  Buradakiler yalnız oradan gelen kararlar ve oraya gönderilenler.
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
| Modun `/eland/rho`'yu kullanması (görüntü-tabanlı dış döngü) | diğer sohbet: tasarım Simulink'te doğrulanınca brif §12 biçiminde tarif gelecek | ölçülen: ~10 Hz, yakalamadan alınmasına p50 19.5 / p90 39.6 ms, BEST_EFFORT |
| W5 / yükseltilmiş hedef: hedefe göre yükseklik kestirimi (gözlemci) | diğer sohbet | ölçülen: EKF temasta hedefin 3.8-4.0 m üstünde, temas 1.47-1.49 m/s |
| İç döngü kazançlarının yeni θ ile IMC türetimi | açık | eski türetim θ = 0.28 s ile; yeni θ 0.04-0.08 s |
| ρ̇/ρ = 2D'nin gürültülü veride sınanması | açık | statik ilişki ρ = A/(4.22·h²) doğrulandı (eğiklik < 5°'de RMS ≤ 0.002) |
| Uzun sabit ıraksama örnekleri | karar bekliyor | K2'de pencereler kısa (D* = 0.5'te 0.4 s); devir irtifası düşürülebilir ya da yalnız D* = 0.2 kullanılır |
| Gerçek segmentasyon modeli | ertelendi | maske şu an Gazebo'nun kusursuz etiketi |

## 6. Katkı vermek istersen

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
