# Veri toplama — Tur 2 sonuç raporu (2026-10-04)

Ayrıntı ve bütün tablolar: `docs/VERI_TOPLAMA.md`, "Tur 2 — yürütme". Veri:
`~/eland_veri/` (WSL), sözlük `tools/veri/data_dictionary.md`. Etiketler:
`v5.1-veri-temizlik`, `v5.2-ruzgar-kalibrasyon`, `v5.3-veri-tur2`.

## 1. 6a / W5 hükmü (a) — COMMIT tetiği

EKF yüksekliğine bağlı. Satırlar O2 sonrası:
- `src/eland_mode/include/emergency_landing_mode.hpp:322`:
  `if (altitude_m <= _landing_altitude_m && !_ident_enabled)` → COMMIT.
- `:269`: `altitude_m = -pos_ned.z()` (EKF yerel z, kalkış noktasına göre).
- `landing_altitude` = 2.0: `src/eland_sim/config/eland_params.yaml:286`,
  varsayılan `hpp:508`.

## 2. Eski taban çizgi hangi PX4 parametreleriyle ölçüldü

`MPC_Z_V_AUTO_DN = MPC_Z_VEL_MAX_DN = 2.0`; 2026-09-05 20:54'ten beri
değişmedi (266 PX4 kaydının başlığı tarandı). Brifteki taban çizgi
2026-09-26'da, hep 2.0 / 2.0 ile. Parametreler 2.0'da bırakıldı.

## 3. Adım başına

Hepsi temiz sistemde.

| Adım | Kol | Bölüm | Başarılı | Duvar süresi |
|---|---|---|---|---|
| 1 | Kol 0: W2-W6 ×3, W1 ×3, 10 ada | 28 | 24; 4 negatif örnek beklendiği gibi başarısız | 40 dk |
| 2 | K1: W2-W5 × {0.4, 0.7, 1.0, 1.5} × 2 | 32 | 32 (1'i tekrar: PX4 açılmadı) | 44 dk |
| 3 | K2: D* {0.2, 0.35, 0.5} × W2-W5 × 2 | 24 | 24 (1'i tekrar: mod komutu kayboldu) | 34 dk |
| 4 | K5 rüzgârlı: A 0.6 / 1.0 × 3 (+ rüzgârsız eş) | 6 + 1 | tanımlama, inmiyor | 14 dk |
| 5 | K4: 40 m, W3 | 12 | 12 | 24 dk |
| 6 | Aşama 5: 5 bozucu × {K2 0.35, K1 1.0} × 2, W3 | 20 | 20 | 27 dk |
| 7 | K3: W2-W8 ×4 + 52 ada inişi | 80 | 80 (1'i tekrar: doğuş hatası) | 109 dk |

Veri seti 218 bölüm (Tur 1'in K5'i ve 3 açık alan bölümü dahil).
- **Başarı:** 195 başarılı; kalanların hepsi beklenen (19 K5 tanımlama,
  4 negatif).
- **Bölme (`tum_ozet.csv`, `_bolme/`):** anahtar düzeyinde %73 / %12 / %15,
  bölüm düzeyinde 140 / 31 / 47. K4 ve Aşama 5'te test bölümü yok (tek
  dünya, az tohum).

## 4. W5, Kol 0 (W5 hükmü d), ölçülen

| | t1 | t2 | t3 |
|---|---|---|---|
| COMMIT girildi mi | hayır | hayır | hayır |
| Temas hızı (Gazebo) | 1.47 m/s | 1.47 m/s | 1.48 m/s |
| Temasta h_ekf − h_gercek_hedef | 3.81 m | 3.81 m | 3.87 m |
| Temastan önce v_ref | 1.40 m/s | 1.40 m/s | 1.45 m/s |
| PX4 landed, temastan sonra | 1.05 s | 1.06 s | 1.07 s |

Beklentiyle aynı: EKF ~4 m, ~1.4 m/s, COMMIT yok. K1 / K2 / K3'ün W5
bölümlerinde (devir yok, 2.5 m altında 0.5 m/s, 18 bölüm) temas 0.48-0.51 m/s,
fark 3.92-4.04 m, COMMIT yok.

## 5. Yapılmayanlar, şüpheliler, şartnameden sapmalar

1. **İlk K1 / K2 toplaması çöpe gitti, yeniden toplandı.**
   - `run_sim.sh`'nin kapanış listesinde `tracker_node` ve `obstacle_driver`
     yok; `kosu.sh` ile kapatılınca geride kalıyorlar. 64 çift birikti.
   - EKF vz hatası 1.2 m/s'ye, yükseklik kayması 2.7 m'ye çıktı. K2'nin
     çoğunda mod DDS keşfinde zaman aşımına uğradı.
   - Etkilenen 56 bölüm karantinada. `kosu.sh` artık her bölümün süreçlerini
     ortam işaretiyle kapatıyor.
   - `run_sim.sh`'nin kendi listesine bu iki düğümü eklemek onay bekliyor.
2. **Rüzgâr etiketi "boş" değildi, ~6 kat fazla güçlüydü.**
   - 2.5 m/s ile 15° yatış, fiziksel ~8 m/s gibi. Şartname yalnız "fark yok"
     durumunu tanımlıyordu; ben ölçeği yeniden ayarladım.
   - gz-sim 8 sabit ölçeğin karesini alıyor (`v²`). PX4 motor modeli de
     rüzgârda zaten 0.59 N rotor sürüklemesi uyguluyor.
   - Seçim: etkin 0.075, yani motor modelinin üstüne gövde sürüklemesi
     (0.375 N, _tahmin). Ölçülen toplam eğim 2.67°, öngörülen 2.73.
   - Rüzgâr dikey tesisi değiştirmiyor (K, θ, t90 aynı).
3. **Mevcut modda sert temas:**
   - COMMIT yüksekte girilir ve o an `view_bounded` doğruysa hız donmuş ρ ile
     sabit kalıyor (`hpp:622-623`, `:593-618`). 3 K3 bölümünde 1.1-1.33 m/s
     temas.
   - Başarı ölçütü hız içermiyor; W5 Kol 0'ın 1.47 m/s'si de "başarılı".
   - Koda dokunulmadı; öneri `docs/VERI_TOPLAMA.md` Adım 7'de.
4. **K2'de sabit ıraksama penceresi kısa:** D* = 0.2'de 5.6 s, 0.35'te 1.6 s,
   0.5'te 0.4 s. Kırpma [0.3, 1.5] ve 2.5 m devir yüzünden. D* = 0.5 kolu
   pratikte "1.5 m/s in, devret". Pencere içinde takip iyi: D − D* RMS
   0.004-0.013 1/s.
5. **K1:** sabit hız takibi RMS ≤ 0.034 m/s. 1.5 m/s'de gerçek hız ~3 cm/s
   düşük; EKF bunu görmüyor (EKF kaynaklı).
6. **Doğuş hatası:** `baslangic.py` W8 tohum 3'te aracı 0.52 m'lik sınıf
   sınırı nesnesinin üstünde doğurdu, gerçek yükseklikler 0.5 m kaydı.
   - Düzeltildi: hedef dışı ya da yükseltilmiş yüzeyde yeniden çekiliyor.
     W5 platform köşesi de kapsandı.
   - Taramada başka etkilenen yok. Bölüm yeniden uçuruldu.
7. **Rüzgârlı ikizler önce farklı başlangıç alıyordu.** Dünya adı tohuma
   karışıyordu. Uçurulmadan düzeltildi; ikizler artık yalnız rüzgârda farklı.
8. **K3'te ilk liste 30 adaya aynı rastgele diziyi veriyordu.** Uçurulmadan
   düzeltildi, her bölümde ayrı politika tohumu.
9. **Adım 1 günlüğünün 7 satırı yeniden kuruldu.** WSL boşta kalınca
   yeniden başladı ve `/tmp` silindi. Satırlar bölüm klasörünün
   zamanlarından kuruldu, `~` ile işaretli. Günlükler artık
   `~/eland_veri/_gunlukler/` altında.
10. **W1 kör inişlerinin temas alanları sonradan dolduruldu** (`ozet_yenile.py`,
    eski değerler `onceki` altında). Temas 0.29-0.30 m/s.
11. **Bekleyen onaylar:**
    - A) 10 Hz ayrı ρ yayını (uygulanmadı),
    - `run_sim.sh` temizlik listesi,
    - COMMIT'te donmuş ρ.
12. **O2b verilmedi; I_hesap yerine çevrimdışı PI tekrarı:** komut farkı
    RMS 0.030 m/s, integral farkı 0.031 m/s. Sebep: v_ref durum kanalından
    10 Hz geliyor.
13. **Temas sonrası devrilme (`kol0_veri_ada_t2010_t1`):** 0.30 m/s'lik
    düzgün temastan 7.5 s sonra devrildi, 62.5 m savruldu. `landed` temastan
    36.2 s sonra geldi. Dünyada bir hareketli kişi var (çarpma, doğrulanmadı).
    199 temaslı bölümde tek. Analizleri `t_temas_gercek`'te kesin.
