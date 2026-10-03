# Geri bildirim — veri toplama görevi nerede?

> **Bu metin ne:** Daha önce bana, acil iniş projesinde MATLAB/Simulink'te
> dikey iniş kontrolcüsü tasarlamak ve bir RL ajanı eğitmek için 7 aşamalı bir
> **veri toplama görevi** yazmıştın. Görevi projede Claude Code uyguluyor.
> Aşağıda yapılanlar, ölçülen sonuçlar, verdiğim kararlar ve açık sorular var.
> Tarih: 2026-10-03. Kod: `github.com/adakarda/slz-safelanding`, `main` @
> `v4.8-k5-tesis`.
>
> Etiketler senin istediğin gibi: **ölçülen**, **_hesap** (ölçülenden
> hesaplanan), **_tahmin** (varsayım içeren).
>
> En sondaki "Senden istediğim" bölümünü yanıtla.

---

## 1. Tek bakışta durum

| Aşama | Durum |
|---|---|
| 0 — okuma | ✅ 8 soru dosya:satırla cevaplandı |
| 1 — kayıt düğümü | ✅ Yazıldı, uçan inişte doğrulandı |
| 2 — yeni dünyalar | 🟡 Üretildi ve doğrulandı (`gz sdf`), **henüz uçurulmadı** (onay O1 bekliyor) |
| 3 — Kol 0 | 🟡 Yalnız açık alan yapıldı (3 iniş); adalar O1 bekliyor |
| 4 — uyaran/keşif kipleri | ❌ Başlamadı (onay O2 + karar K2 bekliyor) |
| K5 — tırmanmalı tesis testi | 🟡 Rüzgârsız yarısı bitti (12 uçuş); rüzgârlı yarısı O1 bekliyor |
| 5 — algı bozucuları | ❌ Başlamadı (mevcut koda dokunmayı gerektirmiyor) |
| 6 — veri seti düzeni | 🟡 Bölüm klasörleri var; birleşik `.mat`, `tum_ozet.csv`, train/val/test bölmesi yok |
| 7 — rapor | 🟡 Doğrulama araçları var, tam rapor yok |

**Kural ihlali yok:** mevcut koda, alçalma yasasına, PI'ye, durum makinesine,
mesajlara, dünyalara ve PX4 parametrelerine dokunulmadı. Her şey yeni dosya.

---

## 2. Aşama 0 cevapları (kısa)

1. **EKF irtifası kalkış noktasına göre, alttaki zemine göre değil.** Mesafe
   sensörü yok; `dist_bottom_valid` hep false. `LandingState.altitude_agl`
   adına rağmen AGL değil.
2. **Maske yakalama damgası (Gazebo sim zamanı) taşıyor, alma damgası yok.**
   ρ her maskede (10 Hz) hesaplanıyor ama moda yalnız iniş adayı mesajı
   içinde, karar hızında (~1.8 Hz) gidiyor. Adayın damgası haritanınki, ρ son
   maskeden; bir kareye kadar kayabiliyor.
3. **area ≈ 1590 m² ve clearance = 20.00 m 40×40 m harita tavanı.** Mesafe
   dönüşümü harita kenarını sınır saymıyor. Kararı etkilemiyor, ama
   `area_m2` gerçek alan diye kullanılmamalı.
4. **83.7 m'deki APPROACH:** PX4 kaydına göre araç manuel kipte, tam gazla
   83.9 m'ye çıkarılmış, mod o irtifada devreye girmiş. Aday hazırsa mod
   arama irtifasına (15 m) inmeden, devraldığı irtifada yaklaşıyor.
5. **Kamera nadirden 0.005° sapıyor, lens bozulması yok, sınırlar tek piksel
   keskin.** Gazebo etiketi; eğitilmiş model böyle olmayacak. 320×240,
   yatay FOV 99.7°, 10 Hz, gövdeye sabit (gimbal yok).
6. **COMMIT, PX4 `vehicle_land_detected.landed` ile bitiyor.** Gerçek temas
   anı Gazebo'dan alınıyor (aşağıda yeni bulgu).
7. **Gerçek konum `/world/<dünya>/dynamic_pose/info`'dan (~50 Hz).**
   Simülatör hız yayınlamıyor; gerçek dikey hız z'nin türevi
   (`vz_gercek_hesap`). Yüzey yükseklikleri dünya tanımından.
8. **Gerçek zamandan hızlı koşturma önerilmez.** İşlemci zaten dolu, ve
   düğümler duvar saatiyle çalıştığı için hızlandırılmış veri temsil edici
   olmaz. Bir iniş (mod → gerçek temas) 15-19 s (3 iniş, ölçülen); bölüm
   başına duvar saati ~1.5-2 dk (iniş), ~3 dk (100 s'lik tesis testi).

---

## 3. Planı etkileyen bulgular

| # | Bulgu | Etki |
|---|---|---|
| B1 | **PX4'ün iniş bayrakları gerçek temastan 3-5 s geç (ölçülen).** `ground_contact` 3.1-4.2 s, `landed` 3.8-4.9 s sonra. Araç yere değdikten sonra mod 0.3 m/s komutla itmeyi sürdürüyor, itki ancak sonra düşüyor. | Temas anı ve temas hızı yalnız Gazebo'dan alınıyor. Eski "mod → landed" süreleri yerde geçen ~4-5 s'yi içeriyordu. |
| B2 | **Tesis ölü zamanı 0.28 s değil, ~0.05 s (ölçülen, K5).** Eski değer farklı bir yöntemdendi (komut 10 Hz'lik durum kanalından, rampa uydurma). | Kontrolcü tasarımında yeni değerleri kullan (§6). Eski IMC kazanç türetimi (Ki = 1.39) geçersiz. |
| B3 | **PX4 parametreleri varsayılan değil:** `MPC_Z_V_AUTO_DN = 2.0`, `MPC_Z_VEL_MAX_DN = 2.0` (varsayılan 1.5). Eski bir deneyden kalıcı kalmış. | Kullanıcı kararı: **böyle kalacak**, toplama boyunca sabit. Her bölümün `kosul.yaml`'ına yazılıyor. |
| B4 | **W1 (4×4 m) aday üretemez,** adanın çevresi tehlike sayılmayan sınıf olsa bile. Seçicinin kuralı iniş noktasını sınıf sınırından ≥ 2 m istiyor; 0.2 m ızgarada 4 m'lik adanın merkezi sınıra 1.8 m. 4.4 m'den dar her ada için aynı. | W1 ve küçük rastgele adalar "site yok" örneği: mod 60 s arar, sonra kör iner. Bu adalarda alçalma verisi çıkmaz (K kipleri dahil). |
| B5 | **K4 kendi içinde çelişkili:** yalnız aşağı hız serbest ([0.3, 1.5]), 15 m'de 20-30 s isteniyor. Ortalama ~0.9 m/s ile ~15 s'de yere varır. | Karar K2 açık. Öneri: 40 m'den başlat (tırmanmalı tanıma zaten K5'te var). |
| B6 | **Gazebo rüzgârı PX4'ün x500'ünde kapalı.** WindEffects yalnız `enable_wind` işaretli linkleri itiyor; SDF'nin dahil-et-değiştir yöntemi bu alanı ekleyemiyor. | PX4'ün dosyalarını okuyup tek satır ekleyen bir üretici yazıldı: `x500_seg_cam_down_ruzgar` (§5). Kuvvet ölçeği ilk rüzgârlı uçuşta ölçülecek. |
| B7 | **PI'nin integrali yayınlanmıyor.** | Şimdilik `I_hesap` (geri çatım; yalnız VALIDATE'te ve çıkış doymamışken). Kesin değer için O2b (isteğe bağlı) gerekiyor. |
| B8 | **Makine ortak.** Simülasyonu başlatan betik açık bir simi kapatıyor (bir kez oldu). | Koşu betiği açık sim görürse başlamıyor. Toplama için tek başına sim zamanı gerekiyor. |
| B9 | Bu makinede MATLAB yok. | `.mat` (v7) yalnız `scipy.io.loadmat` ile geri okunarak doğrulandı. |

---

## 4. Aşama 1 — kayıt düğümü (bitti)

`tools/veri/kaydedici.py` yalnız dinliyor; hiçbir şey yayınlamıyor.

**Kaynaklar:**
- PX4: konum, tutum, iniş algılama, durum; modun PX4'e verdiği setpoint
  (`/fmu/in/trajectory_setpoint`).
- Proje: `/eland/state`, `/eland/candidate`, maske.
- Gazebo (gz-transport'tan doğrudan): sim saati ve gerçek poz. ROS köprüsü
  Pose_V'nin model adlarını kaybettiği için köprü kullanılmıyor.

**Bölüm başına dosyalar:**
- `duzenli.csv` (50 Hz ızgara, her kanalın son değeri, her kanala
  `_yas_ms`)
- `maske_olaylari.csv` (maske başına, kendi damgasıyla)
- `karar_olaylari.csv` (~1.8 Hz)
- `durum_gecisleri.csv` (HOLD/ABORT nedenleri dahil)
- `ep_ozet.json` (süreler, gerçek temas anı ve hızı, PX4 bayrak gecikmeleri,
  başarı, aday kayıpları, kanal başına süreklilik/kayıp/jitter)
- `kosul.yaml`, `params.yaml`
- `ep.mat` (v7)
- `maskeler.npz` (ham maskeler, her bölüm)

Birimler ve işaretler `tools/veri/data_dictionary.md`'de. Dikey hızlar
**aşağı pozitif**, yükseklikler yukarı pozitif, zaman sim saniyesi (`t_gz`).
Maske öznitelikleri `tools/veri/ozellik.py` ile çevrimdışı yeniden
hesaplanabiliyor.

**Doğrulama — açık alan, Kol 0, 3 iniş (ölçülen):**

| | t1001 | t1002 | t1003 |
|---|---|---|---|
| Başarılı | ✓ | ✓ | ✓ |
| Alçalmada şartname sütunları dolu | %100 | %100 | %100 |
| EKF − gerçek yükseklik, bias / RMS | +0.03 / 0.14 m | +0.04 / 0.13 m | +0.01 / 0.14 m |
| vz_ekf − vz_gercek RMS | 0.036 | 0.028 | 0.052 m/s |
| Takip RMS (vz − v_ref, VALIDATE) | 0.12 | 0.15 | 0.22 m/s |
| Maske yaşı p50 / p90 | 19 / 36 ms | 19 / 31 ms | 20 / 39 ms |
| ρ ortancası / kadraja sığma (VALIDATE) | 0.999 / %0 | 1.000 / %0 | 0.998 / %0 |
| Gerçek temas hızı | 0.29 | 0.31 | 0.30 m/s |
| COMMIT'te EKF / gerçek yükseklik | 1.95 / 2.03 m | 1.97 / 2.01 m | 1.97 / 2.07 m |

**Kanal hızları:** PX4 konum ve setpoint 50 Hz, gerçek poz 50 Hz, sim saati
250 Hz, maske 10 Hz, mod durumu 9 Hz, aday 1.8 Hz. Bölüm ~1 MB.

**Bilinen sınırlar:**
- Açık alan dünyasının yüzey yükseklikleri henüz tanımlı değil. Yol ve
  yamalar 0.02 m'lik kutu, binalar 9 m; kaydedici zemini 0 alıyor.
- `v_cmd`, mod iniş sonrası tamamlanınca kesiliyor.
- Izgara 50 Hz, zaman çözünürlüğü 0.02 s.

---

## 5. Aşama 2 — dünyalar (üretildi, uçurulmadı)

`tools/veri/dunya_uret.py`.

**Kullanıcı kararı:** adaların çevresi **tehlike sayılmayan bir sınıf** (arazi
tehlikesi, sınıf 2). Su ve yapı 3 m güvenlik mesafesi istediği için küçük
adaları seçilemez yapıyordu.

- **Dünyalar:** W1-W8 sabit; tohumdan istenen sayıda rastgele ada
  (kare/L/daire, 3-20 m, konum ofseti, 0-2 hareketli kişi). W1-W8'in 2.5 m/s
  rüzgârlı eşleri de var.
- **Her dünyanın yaml'ı:** yüzey yükseklikleri, hedef adanın alanı / merkezi
  / şekli, tohumdan başlangıç koşulları (irtifa 10-20 m, ofset 0-4 m),
  rüzgâr, kişi rotaları.
- **Uyarlamalar:**
  - W6'nın L kolları 6 m: 4 m'lik kol aday üretmez.
  - W8'in ortasındaki 2×2 m nesne de tehlike sayılmayan sınıfta: yapı olsa
    10×10 m adada iniş yeri kalmaz.
  - W5'te araç platformun dışında, yerde doğuyor (ofset 6.5-8 m). EKF orijini
    yerde kalsın ve 4 m fark ölçülebilsin diye; şartnamedeki 0-4 m ofset
    platformun üstüne düşürürdü.
- **Rüzgâr:** gerçek Gazebo rüzgârı (kullanıcı kararı). Rüzgârlı dünyalar
  WindEffects'i ve PX4'ün eklenti listesinin tamamını taşıyor; araç için
  `x500_seg_cam_down_ruzgar` model zinciri.
- **Uçurmak için O1 gerekiyor** (dünya ve model seçimi).

---

## 6. K5 — tesis testi, rüzgârsız (bitti) — kontrolcü tasarımı için

Açık çevrim kare dalga (modun mevcut tanımlama kipi), 8 s periyot, kalkış
22 m. Genlik A için komut −min(A, 1.0) ile +A arası (aşağı +). Genlik başına
3 uçuş, 12 uçuş, 183 basamak; yalnız gerçek yükseklik > 8 m.

| Basamak | K | Ölü zaman θ (%10'a varış) | %90'a varış | En büyük ivme |
|---|---|---|---|---|
| 0.6 m/s | 1.000 | 0.06 s | 0.26 s | 3.6 m/s² |
| 1.2 m/s | 0.992 | 0.04 s | 0.28 s | 6.1 m/s² |
| 2.0 m/s | 0.997 | 0.06 s | 0.36 s | 6.7 m/s² |
| 2.5 m/s | 0.991 | 0.06 s | 0.40 s | 8.4 m/s² |

(Gazebo hızıyla. EKF hızıyla: K 1.01-1.02, θ 0.06-0.08 s.)

**Model (ölçülen):**
- **K ≈ 1.0, θ ≈ 0.04-0.08 s.**
- **Küçük basamakta birinci mertebe gibi** (τ ≈ 0.1 s, _hesap:
  t90 ≈ θ + 2.3τ).
- **Büyük basamakta ivme sınırlı**, ~6-8.5 m/s². Yavaşlatma/tırmanma yönü
  ~6.2 m/s², hızlanma (aşağı) ~8.5 m/s².
- **İç döngünün sınırları:** komut VALIDATE'te [0, 1.5] m/s, tırmanma yok.
  2 m'de COMMIT.

**Gecikme zinciri:** maske 10 Hz, yakalamadan kayda ~20 ms. ρ şu an moda
~1.8 Hz'de ulaşıyor; görüntü-tabanlı döngü için 10 Hz'lik ayrı bir yayın
gerekecek. Görüntü-tabanlı bir döngünün toplam gecikmesi ~0.25 s mertebesi
(_tahmin).

Rüzgârlı yarısı (2-3 m/s Gazebo rüzgârı) O1 bekliyor.

---

## 7. Onay ve karar bekleyenler

Kullanıcının verdiği kararlar:
- **K1:** adaların çevresi tehlike sayılmayan sınıf.
- **K3:** gerçek Gazebo rüzgârı.
- **K4:** PX4 parametreleri 2.0'da kalır.
- **K5:** onaylandı.

Açık olanlar (onayı kullanıcı verir):
- **O1 — `run_sim.sh`'e `--world` ve `--model`, `batch_run.sh`'e iki ortam
  değişkeni (~20 satır).** Verilmezse bugünküyle aynı. Ada dünyalarını ve
  rüzgârlı aracı uçurmak için şart.
- **O2 — moda `veri_toplama_kipi` (~40 satır, varsayılan kapalı).** Açıkken
  VALIDATE'te `v_ref` yeni bir konudan gelir, gerçek yükseklik 2.5 m'nin
  altına inince mevcut COMMIT'e devreder. Hız desenleri (K1 sabit, K2 kâhin
  ıraksama, K3 rastgele, K4 basamak/sinüs) yeni bir düğümde. PI, durum
  makinesi ve mesajlar aynı kalır.
- **O2b (isteğe bağlı):** integralin kesin değerinin yayını.
- **K2:** K4 çelişkisi (B5). Öneri: 40 m'den başlat.
- **Toplama zamanı:** tek başına sim gerekiyor.

**Süre ve disk (_tahmin, bölüm başına ~85 s ölçümünden):**

| İş | Bölüm | Süre |
|---|---|---|
| Kol 0 | 75 | ~1.8 sa |
| K1 | 60 | ~1.4 sa |
| K2 | 75 | ~1.8 sa |
| K3 | ≥ 400 | ~9.5 sa |
| K4 + K5 | ~45 | ~1.1 sa |
| Aşama 5 | ~230 | ~5.5 sa |
| **Toplam** | **~885** | **~21 sa** |

Disk ~1 GB.

---

## 8. Veri nerede, nasıl okunur

- **Bölümler:** `~/eland_veri/<kol>/<dünya>/<ep_id>/`. Şimdiye kadar 15 bölüm
  (3 Kol 0, 12 K5), toplam 41 MB.
- **Doğrulama tabloları ve PNG'ler:** `~/eland_veri/dogrulama/`.
- **MATLAB:** `load('ep.mat')` → `duzenli`, `maske`, `karar`, `gecis` yapıları
  (sütunlar alan olarak) ve `ozet_json` (`jsondecode`).
- **Belgeler:** canlı rapor `docs/VERI_TOPLAMA.md`; kontrolcü brifi
  `docs/KONTROLCU_TASARIM_BRIEF.md` (§7 yeni tesis değerleriyle
  güncellendi).

---

## Senden istediğim

1. **Planı güncelle.** B1-B6'ya göre şartnamede değişmesi gerekenleri yaz:
   W1 ve küçük adaların "site yok" örneği olarak kalması, W5 doğuş ofseti,
   W6 kol genişliği, K4 (B5).
2. **K2 için önerin** ve gerekçesi.
3. **Önceliklendir.** ~21 saatlik toplama tek seferde yapılamayabilir.
   Kontrolcü tasarımı ve RL için en değerli ilk ~6 saat hangi bölümler olsun?
   K3'ün 400 inişi azaltılabilir mi?
4. **Kontrolcü:** §6'daki yeni tesis değerleriyle (θ ≈ 0.05 s, K ≈ 1,
   ivme sınırı) iç döngü ve görüntü-tabanlı dış döngü için tasarım
   varsayımlarını güncelle. Eski θ = 0.28 s ile türetilen her şeyi gözden
   geçir.
5. **RL:** mevcut sütunlardan gözlem, eylem ve ödülü tanımla. Hangi sütun
   gözlem, hangisi yalnız ödül/değerlendirme için (ground truth) olmalı?
6. **Kurallar aynı:** mevcut koda dokunan her şey onaylı, parametreyle,
   varsayılan kapalı. Önerilerini buna uygun yaz.
