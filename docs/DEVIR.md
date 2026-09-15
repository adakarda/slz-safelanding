# Proje Devir Dosyası — slz-safelanding

Bu dosya projeyi devralan kişi içindir. Amaç: depoyu klonladıktan sonra **bu tek
dosyayı okuyarak** sistemi kurabilmek, çalıştırabilmek, neyin neden öyle
yapıldığını anlayabilmek ve Claude Code ile geliştirmeye devam edebilmek.

Depo: `git@github.com:adakarda/slz-safelanding.git`
Ana dal: `main` · Yan dal: `rgb-akis-denemesi` (yarım iş, §13.2)

---

## 1. Proje nedir

İHA için **acil durum iniş yeri seçimi ve inişi**. PX4'ün kendi "eve dön"
davranışının yerine geçen, kayıtlı bir uçuş modu. Aşağı bakan kameradan gelen
sınıf maskesini yer düzlemine yansıtıp bir harita kuruyor, bu haritadan güvenli
bir iniş alanı seçiyor ve oraya iniyor.

Bitirme tezi kapsamında geliştiriliyor. İki referans nokta önemli:

- **SORA** (risk temelli insansız hava aracı düzenlemesi): sınıflar ve
  ayrım mesafeleri buradan geliyor — insana/araca minimum uzaklık gibi.
- **SafeLand**: benzer bir çalışma; tepkisel davranır (tehlike görünce bekler
  ya da iptal eder). Bu projenin katkısı **dördüncü test**: hareketli engelin
  *gideceği yeri* de hesaba katmak. SafeLand'in tepkisel HOLD/ABORT davranışı
  arkada yedek olarak duruyor, kaldırılmadı.

Her şey simülasyonda: PX4 v1.17 SITL + Gazebo Harmonic + ROS 2 Jazzy.

---

## 2. Mimari — veri nereden nereye akıyor

```
 Gazebo segmentasyon kamerası (320x240, 5 Hz, etiketli)
        │  gz topic: seg_cam
        ▼  ros_gz_image köprüsü
 /camera/segmentation           ham etiket görüntüsü
        │
        ▼  perception_node
 /eland/semantic_mask           sınıf maskesi (0..7)
        │
        ▼  mapping_node   (IPM: ters perspektif dönüşümü + zaman füzyonu)
 /eland/ground_map              füzyonlu sınıf haritası (40x40 m, 0.2 m/hücre)
 /eland/ground_map_instant      füzyonsuz, tek kare  ─┐
        │                                             │
        ▼  detector_node                              ▼  tracker_node
 /eland/candidate               iniş adayı       /eland/dynamic_obstacles
        │                                             │
        └──────────────┬──────────────────────────────┘
                       ▼  emergency_landing_mode  (C++, px4_ros2::ModeBase)
                 PX4 setpoint'leri (goto / trajectory)
                       │
                 /eland/state   durum makinesi çıktısı → hud_node
```

**Neden iki harita var:** füzyonlu harita hareketli nesneyi gösteremiyor. Bir
hücrenin kanıtı `hız × tau` ile doyuyor (3 Hz ve 30 s bellekte ~90), oysa 3 m/s
giden bir araç bir hücrede 1.5 s kalıyor ve ~5 kanıt bırakıyor. Ölçülmüş:
etiketli bir araç orijinden geçerken Gazebo iki araç lekesi gösterirken füzyonlu
harita yalnızca park hâlindekini gösteriyordu. Bu yüzden `tracker_node`
**füzyonsuz** haritayı okuyor.

### Düğümler

| Düğüm | Dil | İşi |
|---|---|---|
| `perception_node` | Python | Gazebo etiketlerini proje taksonomisine çevirir |
| `mapping_node` | Python | IPM ile yer düzlemine izdüşüm + zaman füzyonu |
| `tracker_node` | Python | Hareketli engelleri izler, hız kestirir |
| `detector_node` | Python | Dört testi uygular, iniş adayını seçer ve skorlar |
| `emergency_landing_mode` | C++ | PX4 uçuş modu: durum makinesi + iniş yasası + dikey PID |
| `hud_node` | Python | Harita + karar üstü bindirme (HUD) |
| `control_station` | Python | Klavye ile teleoperasyon, manuel kontrol akışı |
| `obstacle_driver` | Python | Simülasyondaki yaya/araçları rotalarında sürer |

### Mesajlar (`eland_msgs`)

- `LandingCandidate` — seçilen site: konum, açıklık yarıçapı, risk, alan,
  `area_ratio` (görüntüyü doldurma oranı), `view_bounded`, `valid`
- `LandingState` — durum makinesi: durum, sebep metni, irtifa, komut edilen
  dikey hız, tavan, `area_ratio`
- `DynamicObstacle` / `DynamicObstacleArray` — izlenen engeller: konum, hız,
  güven, öngörülen konumlar

---

## 3. Karar mantığı — dört test

Aday hücre şu dört testten geçmeli:

1. **SORA ayrımı** (`r_hazard = 3.0 m`) — tehlike sınıflarına (yapı, su, araç,
   insan) minimum uzaklık. Pazarlıksız.
2. **Geometrik sığma** (`r_fit = 1.0 m`) — inilebilir olmayan en yakın hücreye
   uzaklık. Küçük bir sayı, politika değil geometri.
3. **Sınıf dikişi** (`r_class_edge = 2.0 m`) — **farklı sınıftan** en yakın
   hücreye uzaklık. Sonradan eklendi: çim ile asfalt arasındaki dikiş,
   `safe_classes` ikisini de içerdiği için görünmüyordu ve araç bordüre iniyordu.
4. **Yörünge testi** — hareketli engellerin gideceği yer. **Bu projenin
   katkısı.**

Bölge büyüklüğü (`min_area_m2 = 9.0`) bağlantılı bileşen analiziyle ayrı bir
ölçüt olarak bakılıyor.

### Dördüncü testin iç yapısı (önemli — burada bir kez yanlış yapıldı)

Üç şey var ve **yalnızca biri yasak**:

| Katman | Anlam | Etki |
|---|---|---|
| Koridor diskleri | Tehlikenin **olacağı** yer | **Sert dışlama** |
| Geçilmiş zemin (bellek) | Bir şeyin **geçtiği** yer | Skora ceza (`w_memory` 0.35), tazelikle ölçekli |
| Yaklaşma gölgesi | Siteye giderken tehlikenin üstünden geçmek | Skora ceza (`w_route` 0.20) |

Başlangıçta üçü de sert dışlamaydı ve sonuç felaketti: trafik varken statik
testleri geçen ~20.000 hücrenin **tamamı** siliniyordu, 152 karenin 79'unda hiç
aday üretilmiyordu, mod 3 s aday göremeyince inişi bırakıp PX4'ün **kör**
Descend'ine düşüyordu. Yani güvenliği artırmak için eklenen katman, inişi
bitiren şeydi.

**Genel ders (postere de girdi):** kısıt eklemek her zaman güvenliği artırmaz —
hiçbir seçenek bırakmayan bir kısıt, sistemi daha kötü bir yedeğe düşürür.

---

## 4. Sınıf taksonomisi

Yedi sınıf + `UNKNOWN`. `eland_common/classes.py` tek kaynak.

| # | Sınıf | Güvenli mi |
|---|---|---|
| 0 | safe-soft (çim, toprak) | ✅ |
| 1 | safe-hard (asfalt, beton) | ✅ |
| 2 | terrain-hazard (eğimli/engebeli) | ❌ |
| 3 | structure (bina, ağaç) | ❌ tehlike |
| 4 | water | ❌ tehlike |
| 5 | vehicle-animal | ❌ tehlike, hareketli |
| 6 | person | ❌ tehlike, hareketli |
| 7 | UNKNOWN | görülmemiş/sınıflanmamış |

`GZ_LABEL_OFFSET = 1`: Gazebo dünyasında etiketler `taksonomi + 1` yazılır,
çünkü Gazebo'nun 0'ı "etiketsiz" demektir. `perception_node` bir çıkarır.

---

## 5. Kontrol — dikey hız döngüsü

Tezin kontrol bölümü bu. Tam anlatım `docs/TEZ_NOTLARI.md` §2'de; burada özet.

### İniş yasası (hız referansı nasıl üretiliyor)

```
v_tavan = clamp(0.20 · √alan , 0.3 , 1.5)          alan: m²
v_ref   = clamp(v_tavan · (1 − ρ) , 0.3 , v_tavan)  ρ: sitenin görüntüyü doldurma oranı
```

Yedek yol: site kadrajdan taşıyorsa (`view_bounded == false`) ρ anlamsızdır
("yere değmek üzereyim" ile "tarla kocaman" aynı görünür), yakınlık için
irtifaya dönülür: `v_ref = clamp(0.35 · irtifa , 0.3 , v_tavan)`.

**Bilinmesi gereken ölçüm:** açık çimende ρ yolu inişin **%0'ında** aktif.
Bölge her zaman kadrajdan taştığı için bütün iniş irtifa yedeğiyle yapılıyor.
Bu, tasarım hatası değil ölçek belirsizliği: tek karede tek tip bir çimenlik
20 m'den de 5 m'den de aynı görünür. Ayrıntı ve rakamlar §13.1'de.

### Kapalı çevrim (eklenen kısım)

Yasa doğru sayıyı üretiyordu ama PX4'e **komut değil üst sınır** olarak
veriliyordu. PX4 tarafında `GotoControl.cpp:203` isteneni `MPC_Z_V_AUTO_DN` ile
kırpıyor ve hedefe kendi yumuşatılmış profilini planlıyor. Sınır izlenecek bir
referans değildir: 2.00 m/s isteniyor, 1.30 m/s gerçekleşiyordu.

Şimdi dikey eksen hız komutu olarak sürülüyor (yatay eksen konum kontrollü
kalıyor ki doğrulanmış alandan kaymasın):

```
e      = v_ref − v_ölçülen
u      = v_ref + Kp·e + I                  (ileri besleme + PI)
I     += (Ki·e + Kaw·(u_sat − u))·dt       (geri hesaplamalı doygunluk koruması)
u_sat  = clamp(u , 0 , v_max)
```

Üç tasarım kararı:

- **İleri besleme referansın kendisi.** Tesis PX4'ün hız denetleyicisi; beklenen
  durum "v iste v al". Bu yapı sayesinde `Kp = Ki = 0` eski açık çevrimi birebir
  üretir — iki kolu karşılaştırılabilir kılan şey bu.
- **Geri hesaplamalı integral koruması.** Çıkış son iki metrede taban hızda
  doyuyor; koruma olmazsa integral şişer ve yere en yakın anda aşım yapar.
- **Çarpmasız geçiş.** Her alçalma girişinde integral sıfırlanır.

### Kazançlar nereden geliyor

Elle seçilmedi, **ölçülerek türetildi**. Moda kare dalga tanımlama kipi eklendi
(`ident_enabled`), tesis sürüldü ve model çıkarıldı. Beklenen birinci mertebe
model **uymadı** — ve uymaması bilgi verdi: τ her genlikte ızgara tabanına
yapıştı, ölçülen eğim genlik küçülünce düştü (4.94 → 1.67 m/s²). Sabit ivme
sınırı olsa eğim genlikten bağımsız olurdu; düşmesi **jerk sınırlaması** demek.

Kalan model: birim kazanç (K = 1.01-1.03), ölü zaman θ ≈ 0.28 s. Ölü zaman
baskın IMC kuralı neredeyse saf integratöre çöküyor:

```
Ki = 1 / (K·(λ + θ)) ,  Kp → 0        λ = 1.5θ = 0.42 s → Ki = 1.39
```

`Kp → 0` dejenere değil doğru sonuç: döngü referansı zaten ileri besliyor,
K ≈ 1 olduğu için oransal terimin kalıcı rejimde işi yok.

**Varsayılan hâlâ elle ayarlı (Kp 0.8, Ki 0.6)**, çünkü türetilmişle ölçüm
gürültüsü içinde aynı çıktı ve değiştirmek için sebep yoktu.

---

## 6. Sıfırdan kurulum

### Gereksinimler

- Ubuntu 24.04 (WSL2 üzerinde çalışıyor, doğal Linux'ta da çalışır)
- ROS 2 **Jazzy**
- Gazebo **Harmonic** (gz-sim 8.11)
- `MicroXRCEAgent`, `ros_gz_image`
- PX4-Autopilot (aşağıdaki commit'e sabitli)

### Adımlar

```bash
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone git@github.com:adakarda/slz-safelanding.git .
git clone --recursive https://github.com/Auterion/px4-ros2-interface-lib
git clone https://github.com/PX4/px4_msgs
```

**Sürüm eşleşmesi kritiktir.** `px4_msgs`, `px4-ros2-interface-lib` ve PX4 aynı
tarihten olmalı. Değilse mod kaydı şununla düşer:

```
MessageFormatResponse::success == false for fmu/in/setpoint_config
Registration failed
```

Bu makinedeki eşleşme:

```bash
cd ~/ros2_ws/src/px4_msgs               && git checkout e62353e
cd ~/ros2_ws/src/px4-ros2-interface-lib && git checkout 9fb7cea
# PX4-Autopilot: f63b0d6b6f (2026-05-01)
```

`px4_msgs` commit mesajları `Update to PX4 <sha>` formatında, yani PX4'ü
güncellersen eşleşeni bulmak kolay.

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash
```

**Not:** Gazebo etiketleri yalnızca `ogre2` render motorunda çalışır. `ogre`
seçilirse maske boş gelir ve hiçbir hata mesajı görmezsin.

---

## 7. Çalıştırma

### Tek komut — `dene.sh` (önerilen)

```bash
cd ~/ros2_ws && ./src/eland_sim/scripts/dene.sh hud
```

Kipler:

| Kip | Ne yapar | Süre |
|---|---|---|
| `hud` | Gazebo penceresi + HUD + kontrol istasyonu, kontrol sende | — |
| `otomatik` | Penceresiz, kalkış+mod otomatik, karar döngüsü sayıları | ~3 dk |
| `olcum` | 90 s izleme skoru (gerçek vs kestirilen hız) | ~4 dk |
| `toplu` | N rastgele dünyada uçur, CSV + başarı oranı | N×2 dk |
| `ruzgar` | Yanal kuvvet bozucusu altında iniş (`GORSEL=1` ile pencereli) | ~4 dk |
| `tanim` | Sistem tanımlama + IMC ile kazanç türetimi | ~4 dk |
| `sekil` | Poster şekilleri (sim gerekmez) | anında |

Ortam değişkenleri: `KISI` (3), `ARAC` (2), `N`, `FORCE`, `PROFIL`, `YON`,
`GENLIK`, `OUT`, `GORSEL`, `SURE`.

### HUD tuşları

| Tuş | Ne yapar |
|---|---|
| `t` | Kalkış |
| `m` | Emergency Landing modunu seç |
| `9` | Modu kayıttan düşür — PX4 kendi Return'üne döner (operatör kaçış yolu) |
| `W/S/A/D/Q/E/R/F` | Manuel uçuş |
| `SPACE` | Çubukları ortala |
| `2` | Manuel kontrolü al (POSCTL) |
| `L` / `X` / `ESC` | PX4 iniş / disarm / çık |

### Alt seviye — `run_sim.sh`

```bash
~/ros2_ws/src/eland_sim/scripts/run_sim.sh --scenario person --auto
```

Önemli seçenekler: `--fixed` / `--seed N` / `--scenario {default,person,yard}`
/ `--pose X,Y,Z,R,P,Y` / `--takeoff [ALT]` / `--auto` / `--link-drop` /
`--headless` / `--no-hud` / `--params DOSYA` / `--px4-param K=V`.

Ctrl+C hepsini birden kapatır — PX4, gz sunucusu, gz arayüzü, ajan ve ROS
düğümleri.

---

## 8. Ölçüm araçları (`tools/`)

| Araç | Ne ölçer |
|---|---|
| `run_scorer.py` | Bir uçuşu puanlar: aday üretimi, durum geçişleri, irtifa bandına göre dikey hız takip hatası, inilen yerin riski, dokunma sapması. Dokunmada kendi kendine biter. |
| `batch_run.sh` + `batch_summary.py` | N rastgele dünyada uçur, CSV yaz, ortanca + çeyrekler özeti |
| `fit_fopdt.py` | Kare dalgadan tesis modeli çıkarır, IMC ile kazanç türetir |
| `measure_tracking.py` | Hareketli engel izleme skoru; izlenmeyen kareleri sebebe göre ayırır |
| `perception_probe.py` | Harita kalitesini eğim ve hıza göre böler |
| `wind_inject.py` | Gövdeye yanal kuvvet bozucusu (adım/hamle/rampa) |
| `tilt_watch.py` | Canlı yatış, kayma, irtifa |
| `plot_control.py` | Poster şekilleri |
| `make_params.py` | Koşu başına parametre türevi üretir |

**Ölçüm disiplini (çok önemli):** `make_params.py` kurulu varsayılanlardan
türetir, çünkü dünya üreteci de aynı YAML'ı okuyor ve eksik anahtarla koşu
çöküyor. Parametre dosyasını elle yazma.

---

## 9. Dokümanlar haritası

| Dosya | İçerik |
|---|---|
| `docs/OZET.md` | Bir sayfalık özet — ilk okunacak |
| `docs/DURUM.md` | Mühendislik günlüğü, §1-22. Her bölüm bir iş paketi + ölçümleri + açık maddeleri |
| `docs/TEZ_NOTLARI.md` | Teze/postere doğrudan girecek savunulabilir sayılar ve gerekçeler |
| `docs/PLAN.md` | Tasarım gerekçeleri, fazlar, kararlar |
| `docs/CHECKLIST.md` | Gereksinim listesi |
| `docs/ISTEKLER_2026-09-04.md` | Danışman/kullanıcı istekleri ve karşılıkları |
| `src/README.md` | Kurulum, çalıştırma, HUD, failsafe politikası, ayarlanabilir yerler |

**Etiket tarihçesi** (`git tag`) bir yol haritası gibi okunabilir: `v1.0-baseline`
→ `v2.0-sora-taxonomy` → `v2.2-decision-loop` → `v2.7-descent-rate-loop` →
`v3.2-perception-tilt` → `v3.4-wind-visual`. Her etiket bir modülün bittiği
noktadır ve commit mesajı neyin neden yapıldığını ölçümle birlikte anlatır.

---

## 10. Ölçülmüş sonuçlar (özet)

### Karar döngüsü

| Ölçüm | Öncesi | Sonrası |
|---|---|---|
| Yörünge testi (karar karesinin %95'i) | 44.2 ms | **2.6 ms** |
| Aday üretilmeyen kare | 79/152 | **0/152** |
| Aday kaybı (iniş terk edilmesi) | 3 | **0** |
| Durum geçişi | 8 | **3** |
| SEARCH'te geçen süre | 15.0 s | **0.3 s** |

### Kontrol

| Kol (3'er uçuş) | RMS takip hatası, ortanca | En kötü |
|---|---|---|
| Açık çevrim | 0.323 m/s | 1.829 |
| Elle ayarlı PI (0.8/0.6) | **0.201** | 0.206 |
| Türetilmiş (Kp 0, Ki 1.39) | **0.197** | 0.214 |

### Toplu koşum

10 rastgele dünya, tek konfigürasyon: **10/10 iniş**, alçalma 22.15 s
[21.97, 22.19], RMS 0.19 [0.18, 0.20], ABORT 0.

### Bozucu (yanal kuvvet)

| Kuvvet | Eşdeğer rüzgâr | İniş |
|---|---|---|
| 10 N | ~13 m/s | **4/4** |
| 15 N | ~16 m/s | **1/4** |
| 20 N | ~18 m/s | ✗ |

Araç rampa ile **20 N'a kadar konumunu koruyor** (teorik sınır
`m·g·tan45° = 19.6 N`). Kırılan şey kontrol değil **algı**: 15 N için gereken
37° yatışta anlık haritanın bilinmeyen oranı 0.11 → 0.37 çıkıyor, mod aday
göremeyince kör inişe geçiyor.

### İniş alanı kalitesi

| Seçilen site | Öncesi | Sonrası |
|---|---|---|
| Sınıf dikişine uzaklık, ortanca | 0.80 m | **7.58 m** |
| 2 m'nin altında kalan örnek | 14/22 | **0/22** |

---

## 11. Tuzaklar — bunlara bir kez düştük, sen düşme

Bu bölüm dosyanın en değerli kısmı olabilir.

### Ortam

- **WSL `/tmp` temizleniyor.** Her `wsl.exe` çağrısı arası silinebiliyor. Kalıcı
  olması gereken dosyaları `/tmp`'ye yazma.
- **CRLF.** Windows tarafından düzenlenen bash betiği çalışmaz. Düzenledikten
  sonra `sed -i 's/\r$//'` ve `chmod +x`.
- **Exec biti** Windows'tan düzenleyince kayboluyor.
- **PX4 portları hemen bırakmıyor.** İki koşu arasında en az 8-10 s bekle,
  yoksa "PX4 topic'leri görünmedi" alırsın ve koşu boş döner.

### Ölçüm

- **`pkill -f` kendi kabuğunu öldürüyor.** Temizlik betikleri
  `pkill -f tracker_node` çalıştırıyor; komut satırında o adı geçiren **çağıran
  kabuk da** eşleşiyor ve ölüyor. Bu tuzağa üç kez düşüldü. Parametre adlarını
  betiğin içine yaz, dış komut satırına değil.
- **Tek koşu kanıt değildir.** Aynı ayarla aday sıçraması 1 ile 7 arasında
  değişti; açık çevrim RMS'i bir uçuşta 0.235, başkasında 0.413 çıktı. Sınır
  bölgesinde tek koşu **işaretin kendisini** bile yanlış verdi (ilk 15 N uçuşu
  indi, sonraki üçü battı).
- **Varsayılan değiştiğinde kol betikleri de değişmeli.** Kapalı çevrim
  varsayılan yapıldıktan sonra "açık çevrim" kolu üç uçuş boyunca sessizce
  kapalı çevrim ölçtü. Kol betiği artık `descent_closed_loop=false`'u açıkça
  veriyor.
- **Var olmayan bir şeye yayın yapmak hata vermiyor.** İlk dört "rüzgârlı" koşu
  aslında rüzgârsızdı: PX4 modele örnek indisi ekliyor
  (`x500_seg_cam_down_0`), benim gönderdiğim `x500_seg_cam_down`'du,
  `gz topic` sıfır dönüyor ve hiçbir şey olmuyordu. Havada 10 N uygulayıp konum
  ölçen bir kontrol koşusu bunu yakaladı (0.02 m). **Bozucu deneyinde ilk
  doğrulanacak şey, bozucunun gerçekten uygulandığıdır.**
- **Metrik yanlış şeyi ölçebilir.** Yatay hata "o an yayınlanan siteye uzaklık"
  idi; site sıçradığında uçak hiçbir yere kaymadan uzak görünüyordu. Rüzgârsız
  koşu 0.96 m, rüzgârlı koşu 0.08 m çıkmıştı. Ortanca + p90'a geçildi.
- **Örnekleme hızı modeli belirler.** Tanımlamada durum kanalından (~10 Hz)
  örnekleyip 70 ms'lik zaman sabiti "bulundu" — 100 ms örneklemeyle. Hız
  mesajından (~48 Hz) örneklenince gerçek yapı çıktı.

### Kod

- **`--focus -3.23,...`** argparse'a seçenek gibi görünüyor: negatif X'te doğan
  uçakta dünya hiç üretilemiyordu. `--focus=` biçimi kullanılıyor. Bu kusuru
  toplu koşum düzeneği ikinci rastgele dünyada buldu.
- **XML yorumlarındaki `--`** ElementTree'yi kırıyor; ayrıştırmadan önce
  yorumlar temizleniyor.
- **Engeller disk değil kapsül.** Yarı-köşegenle disk modellenince 300/300 rota
  adayı reddedilmişti.
- **HUD ile mod aynı parametreyi okumalı.** Alçalma tavanı modda 1.5'e
  indirilince HUD bir süre 2.0 göstermeye devam etti.

---

## 12. Açık maddeler

`docs/DURUM.md` içinde numaralı listeler hâlinde; buradakiler güncel olanlar:

| # | Konu |
|---|---|
| 15 | GUI'li koşu hiç doğrulanmadı — otomasyon bağlamında X sunucusu yok. `dene.sh hud` insan gözüyle geçmeli. |
| 18 | Mob rotaları düz çizgi; gerçek trafik engellerin etrafından dolaşır. |
| 24 | Araç hız kestirimi harita içinde bile gerçeğin ~%52'si. LSQ penceresi örnek sayısıyla tanımlı; süreyle tanımlı, hıza göre kısalan pencere denenmedi. |
| 25 | Aday koşu başına 3-4 kez 4 m'den fazla sıçrıyor (mandal serbest bırakılmadan). |
| 27 | Rüzgâr yalnızca tek yönden (45°) ölçüldü; yön bağımlılığı denenmedi. |

---

## 13. Şu an nerede kaldık

### 13.1 Devam eden tartışma: kapsama-tabanlı PID

İstenen: **seçilen alanın kamerayı doldurma oranına göre** hızı düşüren bir PID.

Geometri elverişli görünüyor: site yarıçapı R sabit, ayak izi yarıçapı
`F = h·tan(FOV/2)` olduğundan

```
ρ ≈ (R/F)²  →  ρ ∝ 1/h²      (site kadraja sığdığı sürece)
```

**Ama ρ = 1'de doyuyor.** Site ayak izinden büyükse kadraj tamamen dolar ve
alçaldıkça değişmez. Ölçüldü: açık çimende ρ zaten 0.87-0.91 ve oran yasası
inişin %0'ında aktif; bütün iniş irtifa yedeğiyle yapılıyor.

Etiket maskesinden yakınlık çıkarma denemesi de **ölçülerek elendi**: sınır
pikseli sayısı 15 m üstünde 1561, 5-10 m arası 61, 5 m altında **0**. Bir alanı
iyi iniş yeri yapan şey (homojen, tek tip) onu yakınlık ipucu olarak
kullanılamaz yapıyor.

Karar verilmesi gereken: PID neyi kontrol etsin?

1. Kapsama oranının kendisi — doyduğunda hata sıfır kalır, kontrolcü serbest
   düşer. **Riskli.**
2. Kapsamanın büyüme hızı (`τ = 2ρ/(dρ/dt)` sabit) — kontrol açısından en zarif,
   ama doyumda "daha hızlı in" der. **Doyum tespiti şart.**
3. Hedef kapsamaya varış (ρ* = 0.95 sabit setpoint) — doyumda güvenli yöne hata
   yapar (yavaşlar). **Önerilen.**

### 13.2 Parkta bekleyen: RGB kamera + optik akış

`rgb-akis-denemesi` dalında. Etiket maskesi yakınlık veremeyince dokudan optik
akışla `1/τ` kestirme denendi. İlk ölçüm yetersizdi (korelasyon −0.24), sebep
muhtemelen kısa taban: 0.1 s'de genleşme %0.75, kare kenarında yarım pikselin
altında. Denenecekler dalın commit mesajında yazılı: 0.5 s taban, ötelemeyi de
modele katmak (`u = a + k·r`), gerekirse 320×240.

### 13.3 Sıradaki büyük iş: segmentasyon modeli

Şu an maske **Gazebo'nun etiket kamerasından** geliyor, yani doğruluk %100
çünkü bu bir ölçüm değil, tanım. Danışman haklı olarak "tahmin üzerinden
çalışsın" dedi. Plan: veri kümesi hazır olunca gerçek bir segmentasyon modeli
eklenecek.

Bu iş için hazır avantaj: **etiket kamerası bedava mükemmel etiket üretiyor.**
Yani RGB + etiket çiftlerini kaydeden bir düğümle, elle etiketleme olmadan veri
kümesi üretilebilir. Sistem yalnızca simülasyonda kalacaksa alan farkı sorunu da
ortadan kalkar.

Kritik risk: 20 m'de bir insan maskede **79-164 piksel**. En yüksek sonuçlu
sınıf, en küçük nesne. Değerlendirmeyi asimetrik kur — sınıf başına
**yanlış-güvenli oranı** (suya/insana "safe" demek) ayrı raporlansın.

---

## 14. Claude Code ile çalışmak

Bu proje Claude Code ile geliştirildi. Verimli devam etmek için:

**İlk oturumda okutulacaklar:** `docs/DEVIR.md` (bu dosya), `docs/OZET.md`,
`docs/TEZ_NOTLARI.md`. `docs/DURUM.md` uzun; ilgili bölümü işaret et.

**İşe yarayan alışkanlıklar:**

- **Her modül bittiğinde etiketle.** `git tag -a vX.Y-konu -m "..."`. Depodaki
  etiket tarihçesi bu yüzden bir yol haritası gibi okunuyor.
- **Ölçmeden değiştirme.** Bu projedeki her önemli bulgu ("kısıt eklemek
  güvenliği düşürdü", "kazançlar zaten doğruydu", "kırılma algıda") bir
  tahminden değil bir ölçümden çıktı. Claude'a "optimize et" deme; "profil çıkar,
  darboğazı bul, sayıyla göster" de.
- **Öncesi/sonrası tablo iste.** "Düzeltildi" cümlesi yerine sayı.
- **Tek koşuya güvenme**, `dene.sh toplu` ile tekrar al.
- **Reddedilen denemeleri de yazdır.** Bu depoda birkaç fikir ölçülüp
  reddedildi (dönüş kırpma, eğim tavanı, PX4 sınırını yükseltme, etiket
  maskesinden τ). Tezde bunlar kabul edilenler kadar değerli.

**Dokunulmaması istenenler** (proje sahibinin açık talimatı):

- Segmentasyon zinciri — veri kümesi hazır olunca ele alınacak.
- Araç hız kestirimi (`tracker_node` LSQ penceresi) — habersiz değiştirilmeyecek.

---

## 15. Hızlı başlangıç — devralan kişi için ilk yarım saat

```bash
# 1. Kur (§6), sonra ilk koşu:
cd ~/ros2_ws && ./src/eland_sim/scripts/dene.sh otomatik
```

Beklenen çıktı: `aday uretilmeyen 0/150`, `aday kaybi: 0`, üç durum geçişi,
tek denemede iniş. Bunu görüyorsan sistem sağlam.

```bash
# 2. Gözünle bak:
cd ~/ros2_ws && ./src/eland_sim/scripts/dene.sh hud
```

`t` ile kalk, `m` ile modu seç. Yeşil daire seçilen site, kesikli daire hedef
açıklık, kırmızı çerçeveli alan tek yasak bölge (koridor).

```bash
# 3. İstatistik:
cd ~/ros2_ws && N=5 ./src/eland_sim/scripts/dene.sh toplu
```

Beklenen: 5/5 iniş.

```bash
# 4. Kontrol tarafını gör:
cd ~/ros2_ws && ./src/eland_sim/scripts/dene.sh tanim
```

Beklenen: K ≈ 1.0, ölü zaman ≈ 0.3 s, "geçici rejim ivme/jerk sınırlı" uyarısı.

Bu dördü çalışıyorsa devir tamamdır. Takıldığın yer olursa `/tmp/eland_logs/pipeline.log`
her şeyi yazıyor.
