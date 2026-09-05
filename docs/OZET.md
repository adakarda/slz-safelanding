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

---

# 2026-09-04 düzeltme isteklerinin karşılığı

Üç madde, üç ayrı commit ve sürüm etiketi. Ayrıntı `docs/DURUM.md` §14–16.

## 4. Rastgele başlangıç konumu (`v1.5-random-spawn`)

Doğuş noktası artık rastgele; engellerden ve hareketli engel güzergâhlarından
uzak duruyor, seed ile tekrar üretilebiliyor, `--fixed` ile eski davranışa
dönülüyor.

| | öncesi | sonrası |
|---|---|---|
| Farklı doğuş noktası | 1 | **200/200** |
| En yakın engele boşluk | — | min 6.04 m |
| Güzergâha boşluk | — | min 8.23 m |

Uçtan uca: `--seed 12345` → poz `-4.17,-24.49`; Gazebo aracı tam orada gösterdi.

## 5. Daha fazla sınıf ve engel (`v1.6-more-classes`)

`FENCE(10)`, `POLE(11)`, `SAND(12)` tek kaynağa (`classes.py`) eklendi; şema
eklemeli, mevcut ID'ler değişmedi. Dünya 24 → 37 model. Dinamik engel sayısı
parametre (`person_count: 3`, `vehicle_count: 2`), her biri hattın yanına
kaydırılıp faz farkıyla hareket ediyor.

| | öncesi | sonrası |
|---|---|---|
| Maske hızı | 3.11 Hz | **3.19 Hz** |
| Tek karede sınıf | 8 | **11** |
| İnsan izleme hatası | 1.37 m | 1.32 m |
| Araç izleme hatası | 1.86 m | 2.16 m *(iki araç, eşleme zorlaştı)* |

İnce yapılar görülüyor: çit 1484 px, direk 65 px — 32 cm'lik bir direk 25 m'den.

## 6. Teleoperasyon kök nedeni (`v1.7-teleop-rootcause`)

Zincir üç noktadan ölçüldü (yayıncı / DDS / PX4) ve **temiz çıktı**.

**Önceki teşhis yanlıştı ve düzeltildi:** "0–31 Hz öbeklenme" ölçümü, ölçen
node'un kendi tek-thread'li executor'ından geliyordu — akış gerçekten
duruyordu, ama tanı aracında. Doğru ifade: *manuel kontrolü meşgul bir
tek-thread executor'dan yayınlayan her node bu failsafe'i tetikler.*

| Koşul | İstasyon akışı | PX4 "kumanda kayıp" | nav_state |
|---|---|---|---|
| Yüksüz | 33.1 Hz, en uzun 36 ms | 0 kez | — |
| 8 CPU yükü | 33.1 Hz, en uzun 54 ms | 0 kez | — |
| 8 CPU yükü + **varsayılan 0.5 s eşik** | 33.0 Hz, en uzun 60.6 ms | **0 kez** | 60 s POSCTL |

Sonuç: `COM_RC_LOSS_T` workaround'u **geri alındı**, PX4 varsayılanı kullanılıyor.
`NAV_RCL_ACT=1` politika olarak kaldı. İstasyon artık kendi en uzun yayın
boşluğunu raporluyor, penceresiz çalışabiliyor.

**Operatör kaçış yolu eklendi** (açık madde #16 kapandı): `9` tuşu modu
kayıttan düşürüyor, PX4 kendi Return'üne dönüyor. Doğrulandı.

**Hâlâ açık:** GUI'li koşu benim tarafımdan doğrulanamadı (otomasyon
bağlamında X sunucusu yok); yerine 8 çekirdek CPU yüküyle mekanizma sınandı.

## Karar döngüsü (madde 8, 2026-09-05)

Şikâyet "iniş yeri seçimi uzun sürüyor" idi; ölçüldüğünde sebep CPU da,
yayın hızı tavanı da değildi. **Kendi dördüncü katmanımız kendi döngüsünü aç
bırakıyordu:** statik testleri geçen ~20.000 hücrenin tamamı, 5 hareketli için
biriken "geçilmiş zemin" diskleriyle siliniyor, 152 karenin 79'unda hiç aday
üretilmiyordu. Mod 3 s aday göremeyince inişi bırakıyordu — üstelik PX4'ün kör
Descend'ine.

Bellek geçmişi, koridor geleceği anlatır ve yalnızca ikincisine çarpılabilir:
küme boşalırsa önce bellek bırakılır, koridor durur, o da her yeri kapatıyorsa
HOLD/ABORT doğru cevaptır.

| Ölçüm (3 kişi + 2 araç, sabit sahne) | Öncesi | Sonrası (3 koşu) |
|---|---|---|
| Aday üretilmeyen kare | 79/152 | 0/151, 0/152, 0/151 |
| Aday kaybı | 3 | 0, 0, 0 |
| Durum geçişi | 8 | 3, 3, 3 |
| SEARCH'te geçen süre | 15.0 s | 0.3 / 0.2 / 0.6 s |
| Sonuç | 3/3 deneme tükendi | tek denemede iniş |

Ayrıca: yörünge testi 44.2 ms → 2.6 ms (rasterleme), mandal hücre yerine 2 m
yarıçapa bağlandı (site'ın gezdiği yol 32.7/144.3 m → 6.2 m), izleme eşleşmesi
kestirilen konuma taşındı (insan hız kestirimi %68 → %80). Ayrıntı ve
reddedilen denemeler: `docs/DURUM.md` §19.
