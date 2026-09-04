# Özet — 2026-09-03/04 oturumunda yapılanlar

Kısa bakış. Ayrıntı ve tam ölçüm tabloları: `docs/DURUM.md` §12–13,
tasarım gerekçeleri `docs/PLAN.md` (Faz 6, K6–K14), gereksinim uyumu
`docs/CHECKLIST.md` §7.

Başlangıç noktası: `v1.1-hud-baseline` (`2b741df`) — HUD + kontrol istasyonu +
çalışan acil iniş. Bir şey bozulursa dönülecek yer orası.

---

## 1. Dinamik engeller + yörünge-farkında karar (`efaf559`)

Statik dünyaya yürüyen bir insan ve giden bir araç eklendi; ikisinin de
başlangıç/hedef/hızı parametre, dünya bu parametrelerden üretiliyor.

| Yeni bileşen | İş |
|---|---|
| `gen_world.py` + `eland_test.sdf.in` | Dünyayı parametrelerden üretir |
| `obstacle_driver` | Engelleri sim saatinde hareket ettirir, `/eland/obstacle_truth` yayınlar (yalnız ölçüm için) |
| `tracker_node` | Dinamik sınıfları izler, doğrusal hız kestirir, `/eland/dynamic_obstacles` |
| `/eland/ground_map_instant` | Füzyondan **önceki** kare |
| `detector_node` 4. testi | `trajectory_clear` — aday **ve** yaklaşma rotası |

**SafeLand'den farkı:** reaktif duraklat/reroute (HOLD/ABORT) hiç
değiştirilmedi; üstüne, engelin *gideceği* yere göre önceden eleyen prediktif
bir katman eklendi. Ayrım kodda ve commit mesajında yazılı.

**Asıl kanıt — aynı senaryo, filtre açık/kapalı:**

| | filtre açık | filtre kapalı |
|---|---|---|
| Temas noktası | (1.26, −4.64) | (−0.10, −0.35) |
| Araç hattına uzaklık | **4.64 m** | **0.35 m** |

Filtre kapalıyken araç, inmiş aracın 35 cm yanından geçiyor.

**Diğer ölçümler:** maske 3.11 Hz (en uzun boşluk 0.43 s), sınıf 8 ve 9
278/278 karede mevcut; izleme konum hatası 1.37 m (insan) / 1.79 m (araç);
tahmin hatası +2 s'de 2.1/3.4 m, +10 s'de 10.1/16.9 m. Çakışma yokken filtre
iniş noktasını **kaydırmıyor** (temas −0.09, −0.29; iptal yok).

**Ölçerek düzeltilen dört tasarım hatası:** füzyonlu harita hareket edeni
göremiyor (ayrı topic); 4 s ufuk yetmiyor (10 s); belirsizlik yanlış eksende
büyütülüyordu (yalnız yanal); ileri koridor tek başına yetmiyor (süpürülmüş
güzergâh hafızası).

---

## 2. HUD görselleştirmesi (`12767e4`)

Filtre yalnızca logda görünüyordu. Artık HUD'da:

- kırmızı taralı bölge = engelin tahmini güzergâhı
- amber bölge = az önce üstünden geçilen zemin
- oklar = izlenen hareketliler (hız + güven)
- sağ panelde `MOVING HAZARDS`: hızlar, güven, haritanın kapanan yüzdesi

Dışlama bölgesi HUD'da yeniden hesaplanmıyor; dedektör **fiilen uyguladığı**
maskeyi yayınlıyor, HUD onu çiziyor. Ayrıca `run_sim.sh` her açılışta dünyayı
parametrelerden yeniden üretiyor.

---

## 3. Teleoperasyon düzeltmeleri (`44bc57a`)

Üç şikâyet — kendi kendine iniş, devralmanın işe yaramaması, genel tutarsızlık
— tek mekanizmaya çıktı.

**Kök neden:** manuel kontrol akışı PX4'e öbekler hâlinde ulaşıyor. 20 Hz
gönderilirken PX4'ün kullandığı hız 0–31 Hz arasında salınıyor; her boşluk
`COM_RC_LOSS_T`'yi (0.5 s) aşıyor, PX4 kumandayı kayıp sayıyor, `NAV_RCL_ACT`
varsayılanı Return ve mod Return'ün yerine kayıtlı → her boşluk bir acil iniş.

Ölçülen (düzeltmeden önce): devralma başarılı oluyor, **4 saniye sonra**
failsafe aracı geri alıyor.

| Düzeltme | Sonuç |
|---|---|
| `NAV_RCL_ACT=1` (Hold) + `COM_RC_LOSS_T=3` | **25 s boyunca POSCTL'de kaldı**, hiç failsafe yok |
| İstasyon operatör niyetini koruyor + sebebi yazıyor | Geri alınırsa POSCTL tekrar isteniyor, ekranda sebep görünüyor |
| Nokta kilidi (`latch_site`) | Aday kaybı 3 → **1**, `committing anyway` yok, hattan uzaklık 0.06 m → **4.73 m** |

`NAV_DLL_ACT` (GCS datalink) **değiştirilmedi** — `--link-drop` senaryosu
aynen çalışıyor. İki parametre de simülasyon ergonomisi, gerçek donanıma
kopyalanmaz.

**"Karar uzun sürüyor" değerlendirmesi:** ayrılık testi zaten vardı; gecikme
kararın her karede sıfırdan verilmesindendi. Kilit bunu çözdü.

---

## Açık kalanlar

| # | Konu |
|---|---|
| 9 | Hız kestirimi %30'a varan oranda düşük — güvensiz yön, koridoru kısaltıyor |
| 10 | 10 s ufkun ucu güvenilmez (araçta 17 m hata) |
| 14 | Manuel akıştaki öbeklenmenin **kaynağı** izole edilmedi, semptom tolere edildi |
| 15 | Bütün teleop ölçümleri `--headless`; GUI'li koşu doğrulanmadı |
| 16 | Operatör kaçış yolu yok: mod kayıtlıyken kasıtlı RTL de acil inişe dönüyor |
| — | Faz 5 (gerçek segmentasyon modeli) GPU bekliyor |

---

## Çalıştırma

```bash
~/ros2_ws/src/eland_sim/scripts/run_sim.sh --takeoff 20
```

HUD penceresine tıkla; `3` manuel kontrol, `0` acil iniş, `Ctrl+C` kapatır.
Gazebo penceresi ağır gelirse `--headless` ekle.

Filtresiz karşılaştırma için parametre dosyasının bir kopyasında
`trajectory_filter_enabled: false` yapıp `--params <dosya>` ile çalıştır.
