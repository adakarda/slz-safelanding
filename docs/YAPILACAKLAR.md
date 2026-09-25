# Yapılacaklar — İster ↔ Yapılan Karşılaştırması

Değerlendirme tarihi: 2026-09-26 · Kod: `main` @ `v3.6-arastirma-notu`

Bu dosya projenin **baştan sona ne istendiğini** ve **ne yapıldığını** tek
yerde karşılaştırır, sonunda yapılacaklar listesi verir. Kaynak isterler
repo dışında da dağınık durduğu için hepsi tek tek okundu ve kodla teyit
edildi.

**İşaretler:** ✅ tamam · 🟡 kısmi ya da gerekçeli sapma · ❌ yapılmadı ·
❓ durumu bu makineden doğrulanamıyor · 🔒 güvenlik

---

## 0. Kaynak isterler

| # | Kaynak | Nerede | Kapsam |
|---|---|---|---|
| A | `gazebo-acil-inis-simulasyon-brief.md` | repo dışı (Downloads) | Kök ister: mod, segmentasyon, seçim, PID, Faz 1-5 |
| B | `dinamik-engel-yorunge-gorev.md` | repo dışı | Dinamik engeller + yörünge-farkında karar |
| C | `DUZELTME_ISTEKLERI (1).md` | repo dışı | 8 madde + 3b, sıralı |
| D | `YENI_ISTEKLER.md` → `docs/ISTEKLER_2026-09-04.md` | repoda | Sınıf dikişi, HUD, segmentasyona dokunma |
| E | Sohbet içi istekler | — | Kontrol/PID, toplu koşum, tanımlama, rüzgâr, devir, araştırma |
| F | `PROJE_DEVIR.md`, `EGITIM_DEVRALMA.md`, `KAGGLE_EGITIM.md` | repo dışı | **Segmentasyon eğitim hattı** |

**Tavsiye:** A, B, C ve F'yi `docs/isterler/` altına alın. Şu an projenin
neyi karşılaması gerektiği, projenin kendisinde yazılı değil.

---

## 1. 🔒 Önce bunu — güvenlik

- [ ] **Hugging Face token'ını iptal et.** `PROJE_DEVIR.md` ve
  `EGITIM_DEVRALMA.md` içinde düz metin olarak yazılı (her iki dosya da
  "proje bitince iptal edilmeli" diyor). Repoya ve git geçmişine **girmemiş**
  — kontrol edildi — ama bu dosyalar birine gönderildiyse token açıkta.
  hf.co/settings/tokens → iptal → yenisini **Kaggle Secrets**'a koy
  (`KAGGLE_EGITIM.md` zaten doğru yolu kullanıyor).
- [ ] Bu iki dosyayı `docs/isterler/`'e taşırken token satırlarını sil.

---

## 2. Kaynak kaynak durum

### A — Kök brief

| İster | Durum | Kanıt / not |
|---|---|---|
| QGC'de seçilebilen **resmi** PX4 modu, offboard hack değil | ✅ | `px4_ros2::ModeBase`, `/fmu/in/*`'a elle yazan kod yok |
| QGC mod listesinde görünür | 🟡 | MAVLink `AVAILABLE_MODES` ile **protokol düzeyinde** kanıtlandı; QGC **GUI'sinde gözle görülmedi** (makinedeki QGC Daily değil) |
| Bağlantı kopmasında devreye girer | ✅ | Gerçek GCS kopması, 20 s'de nav_state 23, otonom iniş |
| Node çökerse PX4'e geri düşer | ✅ | Ölçüldü: 23 → 5 (RTL), araç düşmedi |
| Aşağı bakan segmentasyon kamerası | ✅ | 320×240, 5 Hz, ogre2 |
| Etiketler 7 SORA sınıfıyla | ✅ | §18, `v2.0-sora-taxonomy` (başta 10 sınıftı, sonra birebir yapıldı) |
| Güvenli sınıflar + bağlı bileşen + min alan | ✅ | `min_area_m2 = 9`, connected components |
| IPM ile metrik koordinat | ✅ | Tam homografi + attitude; iki gizli hata bulundu (heading, K-G ayna) |
| En yakın uygun bölge | 🟡 | "En yakın" yerine risk + mesafe + açıklık skoru — gerekçeli, `CHECKLIST.md` §3 |
| İnsan/araç yarıçapı dışlaması | ✅ | `r_hazard = 3.0 m`, ölçülü kanıt: aday yarıçapı 8.5 → 3.03 m |
| "Yaklaştıkça PID ile yavaşla" | 🟡 | Yasa var ve artık **kapalı çevrim** (`v2.7`); ama görüntü-tabanlı dal açık alanda **%0** aktif (§4) |
| Son metrelerde **tekrar segmentasyon kontrolü** + dinamik engelde duraklama | ❌ | Brief'te "ileri faz". 5 m altında aday kaybolursa HOLD var, ama bilinçli bir yeniden doğrulama adımı yok |
| Faz 1-4 | ✅ | |
| Faz 5 — gerçek segmentasyon modeli | ❌ | `use_gt_segmentation: true`, `false` dalı hazır ama boş |

### B — Dinamik engeller

| İster | Durum | Kanıt / not |
|---|---|---|
| Adım 0: baseline push + etiket | ✅ | `v1.1-hud-baseline` |
| Dinamik insan **`<actor>`** ile | 🟡 | Destekleniyor (`person_kind: actor`), varsayılan `model` — actor pozunu yayınlamıyor, ölçülemiyor |
| Dinamik araç, parametrik yörünge | ✅ | `obstacle_driver`, sim saatiyle |
| Yörünge iniş alanını kesiyor | ✅ | |
| Doğrusal yörünge tahmini | ✅ | `tracker_node`, LSQ, 10 s ufuk |
| Dördüncü test `trajectory_clear` | ✅ | Sonra yeniden düzenlendi: yalnız koridor sert, bellek ve gölge skor cezası (§20) |
| SafeLand HOLD/ABORT korunuyor | ✅ | |
| 5 ölçüm (dayanıklılık, doğruluk, yanlış pozitif, kesişme, karşılaştırma) | ✅ | `CHECKLIST.md` §7.4 |
| Doküman güncellemesi | ✅ | |

### C — Düzeltme istekleri

| # | İster | Durum | Kanıt / not |
|---|---|---|---|
| 1 | Rastgele doğuş + seed + sabit mod geri açılabilir | ✅ | `v1.5-random-spawn` |
| 2 | Daha fazla sınıf/engel + maske hızı ölçümü | ✅ | `v1.6-more-classes`, §15 |
| 3 | Teleop kök nedeni | ✅ | §16 — **önceki teşhis yanlış çıktı** (ölçen düğümün kendi executor'ı), `COM_RC_LOSS_T` geri alındı |
| 3 | **GUI'li koşuda doğrulama** | ❌ | Otomasyonda X sunucusu yok; **senin yapman gereken** |
| 3 | Operatör kaçış yolu | ✅ | `9` tuşu → `/eland/mode_enable` → mod kapanır, PX4 Return'e döner |
| 3b | Anlık (momentary) çubuk + HUD gerçek değeri göstersin | ✅ | `v1.8-momentary-sticks` |
| 4 | Sınırlı sayıda rastgele mob | ✅ | `v1.9-multi-mob`, `max_mobs: 6` |
| 5 | Her SORA sınıfından en az bir örnek | ✅ | Su dahil (§18.4) |
| 6 | Sim taksonomisi = model taksonomisi | ✅ | `v2.0` |
| 6 | Risk skoru **ağırlık sütunundan** | 🟡 **gerekçeli sapma** | Ölçüldü: ağırlıklar `0.35·√(46.167/piksel%)` ile birebir → **sınıf dengeleme ağırlığı, risk değil**. Risk olsaydı bina çimden güvenli sayılırdı. `TRAIN_WEIGHTS` olarak saklandı. **Onayın gerekiyor.** |
| 7 | Gerçek modele geçiş — durdurma noktası | 🟡 | Araştırma yapıldı ve raporlandı; uygulama başlamadı |
| 8 | Karar döngüsü profili + hız kestirimi + çoklu mob | ✅ | `v2.2`, `v2.3`; asıl darboğaz CPU değil, dördüncü katmanın kendisiymiş |

### D — Yeni istekler (2026-09-04)

| # | İster | Durum |
|---|---|---|
| 1 | Sınıf dikişine iniş olmasın | ✅ `v2.5-class-edge` — dikişe ortanca uzaklık 0.80 → 7.58 m |
| 2 | Segmentasyona dokunma | ✅ Dokunulmadı |
| 3 | HUD daireleri / araç vektörleri GT mi? | ✅ `v2.6` — algoritmik oldukları için boyut korundu, renk düzeltildi; vektörler **GT değil**, tahmin |
| 4 | Push | ✅ |
| 5 | İstekleri .md olarak kaydet | ✅ `docs/ISTEKLER_2026-09-04.md` |

### E — Sohbet içi istekler

| İster | Durum | Etiket |
|---|---|---|
| Dikey kontrolü gerçek PID yap | ✅ | `v2.7-descent-rate-loop` |
| Toplu koşum düzeneği | ✅ | `v2.8-batch-harness` — 10/10 iniş |
| Kazançları türet | ✅ | `v2.9-system-id`, `v3.0` — Ki 1.39 / Kp 0, elle ayarlıyla eşdeğer |
| Bozucu (rüzgâr) bastırma | ✅ | `v3.1`, `v3.2` — 20 N tutuluyor, 15 N'da algı çöküyor |
| Test kipleri + görsel rüzgâr | ✅ | `v3.3`, `v3.4` |
| Tez/poster notları | ✅ | `docs/TEZ_NOTLARI.md` |
| Devir dosyası | ✅ | `v3.5-devir` |
| Araştırma notu | ✅ | `v3.6-arastirma-notu` |
| **Kapsama oranına göre PID** (ρ ile yavaşla) | ❌ **karar bekliyor** | Üç seçenek sunuldu (§4) |
| RGB + optik akış ile yakınlık | ❌ **parkta** | `rgb-akis-denemesi` dalı, ilk ölçüm yetersiz |

### F — Segmentasyon eğitim hattı

Durum bu dosyaların yazıldığı tarihe (30-31 Ağustos) göre. **Eğitimler o
tarihten sonra koşulduysa buradaki ❓'leri güncelle** —
`adakarda/uav-landing-ckpt` reposundaki `best_*.pt` / `hist_*.json`
dosyaları cevabı verir.

| İş | Durum |
|---|---|
| 3 veri kümesi (TU Graz, Houston/Harvey, MESSI) 7 sınıfa indirgendi | ✅ |
| GSD normalizasyonu (2.5 cm/px), ~33.400 tile, HF'ye yüklendi | ✅ |
| Eğitim kodu (SegFormer MiT-B3, focal + dice, oversampling) | ✅ |
| Kaggle RAM sızıntısı düzeltmesi | ✅ `KAGGLE_EGITIM.md` |
| **Karışık split baseline eğitimi** | ❓ |
| **LODO × 3** (tugraz / satellite / messi kör) | ❓ |
| Sonuç tablosu (mIoU, person IoU, water IoU) | ❓ |
| DINOv2 + PEFT karşılaştırması | ❌ planlandı |
| **Gazebo'dan veri kümesi üretimi** | ❌ |
| Modelin simülasyona takılması | ❌ |

**Çelişki — karar gerekiyor:** `PROJE_DEVIR.md` "Gazebo'yu yalnızca karar
mantığının doğrulaması için kullan, segmentasyon mIoU'sunu yalnız gerçek
veride raporla (SafeLand da böyle yapmış)" öneriyor. Danışman ise
simülasyonun **tahmin üzerinden** çalışmasını istedi. İkisi uzlaştırılabilir
(§5.1) ama hangisinin tezin ana iddiası olduğu senin kararın.

---

## 3. Açık maddeler — güncel durum

`DURUM.md`'deki tablolar **bayat**: bazı satırlar sonradan kapandı ama
güncellenmedi. Güncel hâli:

| # | Konu | Güncel durum |
|---|---|---|
| 1 | QGC GUI doğrulaması | 🟡 protokol ✅, GUI ❌ |
| 2 | Modu geri alma yolu | ✅ **kapandı** — `9` tuşu (DURUM satırı bayat) |
| 3 | Gerçek segmentasyon modeli | ❌ |
| 4 | 7 SORA sınıfıyla birebir olmama | ✅ **kapandı** §18 (satır bayat) |
| 5 | Alan-oranı yasasının dar geçerliliği | ❌ artık **ölçülü**: açık alanda %0 aktif |
| 6 | Çözünürlük tavanı (20 m'de insan 79-164 px) | ❌ model için kritik |
| 7 | IPM'de ~0.3 m doğu sapması | ❌ izole edilmedi |
| 8 | Bayat doküman satırları | ❌ **büyüdü**, §6'ya bak |
| 9 | Hız kestirimi düşük | 🟡 insan %68 → %80 iyileşti; araç #24'te |
| 10 | 10 s ufkun ucu güvenilmez | ❌ |
| 11 | Ping-pong engel gerçekçi değil | 🟡 artık rastgele rotalar, ama düz çizgi (#18) |
| 12 | Actor kullanılmıyor | 🟡 bilinçli |
| 13 | Bellek + yaklaşma rotası birleşimi | ✅ **dönüştü** — ikisi de artık skor cezası (§20) |
| 14 | Manuel akış öbeklenmesi | ✅ **kapandı** — teşhis yanlıştı (§16) |
| 15 | GUI'li koşu ölçülmedi | ❌ senin yapman gereken |
| 16 | Operatör kaçış yolu | ✅ **kapandı** (#2 ile aynı) |
| 17 | Kaçış tek yönlü | bilinçli tasarım |
| 18 | Mob rotaları düz çizgi | ❌ |
| 19 | İzleyici 5 moba 6 iz | ❌ #24 ile aynı kök |
| 20 | Eski 13 sınıflık ölçümler tarihsel | not |
| 21 | `TRAIN_WEIGHTS` boru hattında kullanılmıyor | not |
| 22 | Bellekte site sıçraması | ✅ kapandı |
| 23 | Araç izlenmiyor | ✅ kapandı — kusur değilmiş |
| 24 | **Araç hız kestirimi ~%52** | ❌ **senin onayını bekliyor** |
| 25 | Aday koşu başına 3-4 kez >4 m sıçrıyor | ❌ |
| 26 | 15-20 N'da algı neden çöküyor | ✅ kapandı — ölçüldü |
| 27 | Rüzgâr tek yönden | ❌ |

---

## 4. Karar bekleyenler (işi senin kararın durduruyor)

- [ ] **Kapsama-tabanlı PID hangi formda?** (Hat 2'nin kalbi)
  1. ρ setpoint PID — basit, doyumda kör
  2. **τ / ıraksama kontrolü** (`ρ̇/ρ = 2D`) — literatürün ana hattı, doyumda
     ters yöne iter, doyum tespiti şart
  3. Sabit hedef ρ* = 0.95 — doyumda güvenli yöne hata yapar *(önerilen başlangıç)*
- [ ] **Araç hız kestirimi** (#24): süreye göre ve hıza göre kısalan LSQ
  penceresini denememe izin veriyor musun?
- [ ] **Ağırlık-risk sapması** (C-6): gerekçeli sapmayı onaylıyor musun?
- [ ] **Tez iddiası**: sim, karar mantığının doğrulaması mı (SafeLand
  yaklaşımı), yoksa tahmin üzerinden uçtan uca mı? (§2-F çelişkisi)
- [ ] **RGB dalı**: optik akışa devam mı, yoksa yalnız kapsama-PID mi?

---

## 5. Yapılacaklar

Öncelik: **P0** tez için şart · **P1** tezi güçlendirir · **P2** iyi olur

### 5.1 Hat 1 — Segmentasyon ve veri kümesi

- [ ] **P0** Karışık split baseline + LODO × 3 eğitimlerinin durumunu HF'den
  doğrula; bitmediyse `KAGGLE_EGITIM.md` ile koş (~23 GPU saati, bir hafta).
- [ ] **P0** Sonuç tablosu: karışık vs üç kör fold (mIoU, person IoU, water IoU).
  Tezin ana bulgusu bu — "karışık split ile LODO arasındaki fark = domain
  shift'in zararı".
- [ ] **P0** Sim'e RGB kamera geri ekle (`rgb-akis-denemesi` dalında hazır)
  ve RGB + etiket **çiftlerini kaydeden** bir düğüm yaz — elle etiketleme
  olmadan sentetik veri kümesi.
- [ ] **P1** Alan rastgeleleştirme: güneş açısı, doku, irtifa, rastgele doğuş
  ve mob düzeni zaten var (`--seed`), ışık ve doku eklenmeli.
- [ ] **P1** Modeli `perception_node`'un `use_gt_segmentation: false` dalına
  bağla; `/eland/semantic_mask` sözleşmesi değişmez.
- [ ] **P0** Değerlendirme **asimetrik**: sınıf başına **yanlış-güvenli oranı**
  (suya/insana "safe" demek), mIoU'dan ayrı raporlanacak.
- [ ] **P1** Aynı senaryo, iki kol: GT maske vs model tahmini → karar
  seviyesindeki fark (aday kaybı, iniş yerinin riski, başarı oranı).
- [ ] **P2** DINOv2 + PEFT karşılaştırması (aynı LODO protokolü).

**Bilinen risk:** 20 m'de insan 79-164 piksel. SegFormer çıkışı 1/4
çözünürlükte — insan birkaç piksele düşer. Sınıf başına irtifaya göre
recall ölç.

### 5.2 Hat 2 — Görüntü-tabanlı iniş kontrolü

- [ ] **P0** §4'teki karar → seçilen kontrolcüyü `DescentRateController`'ın
  yanına yeni bir kip olarak ekle (mevcut irtifa yasası karşılaştırma kolu
  olarak kalsın).
- [ ] **P0** `ρ̇/ρ = 2·vz/h` köprüsünü **ölç**: site kadraja sığdığı sürece
  kapsamadan türetilen ıraksama ile gerçek `vz/h` ne kadar uyuşuyor?
- [ ] **P0** Doyum tespiti: `view_bounded` + ρ > eşik → yedeğe geçiş,
  çarpmasız (integral sıfırlama zaten var).
- [ ] **P1** Dar site senaryosu: kapsama yasasının **gerçekten çalıştığı**
  bir sahne (izole yama; eskiden 392 m²'lik toprak yamasıyla gösterilmişti).
  Açık alanda %0 aktif olduğu için şart.
- [ ] **P1** Karşılaştırma: irtifa-tabanlı / kapsama-PID / τ-kontrol, kol
  başına ≥3 uçuş — dokunma hızı, alçalma süresi, takip hatası, başarı.
- [ ] **P2** RGB optik akış (dal parkta): 0.5 s taban + öteleme modeli.
- [ ] **P2** Yatay eksen için kendi dış çevrim yasamız (şu an tamamen PX4'te).

### 5.3 Algı ve karar kusurları

- [ ] **P1** #25 — aday sıçraması: mandalın tuttuğu hücre uygun kümeden
  çıkınca ne olacağı.
- [ ] **P1** Brief'in son-metre maddesi: düşük irtifada **bilinçli yeniden
  doğrulama** adımı.
- [ ] **P2** #24 — araç hız kestirimi (onayla).
- [ ] **P2** #7 — IPM ~0.3 m doğu sapması.
- [ ] **P2** #10 — 10 s ufuk (koridorun asıl değeri 2-4 s'de).
- [ ] **P2** #18 — mob rotaları düz çizgi.
- [ ] **P2** #27 — rüzgâr yön bağımlılığı (4 yön × 10 N).

### 5.4 Doğrulama — senin yapman gerekenler

- [ ] **P0** `dene.sh hud` ile GUI'li koşu (#15) — otomasyonda hiç görülmedi.
- [ ] **P1** `GORSEL=1 FORCE=10 dene.sh ruzgar` — yatışı gözle doğrula.
- [ ] **P2** QGC Daily ile mod listesinde gözle doğrulama (#1).

### 5.5 Dokümantasyon — bayat yerler

Kodla **çelişen** satırlar; tez yazarken buradan alıntı yapılırsa yanlış olur:

- [ ] **P0** `PLAN.md` başlık: "Faz 0-4 ve 6 tamam" → Faz 5 ve sonrası eksik;
  §1 K3 "PID aslında goto hız limiti, I terimi eklenmiyor" → **artık kapalı
  çevrim PI** (`v2.7`).
- [ ] **P0** `PLAN.md` §0 ve `CHECKLIST.md` §2: **10 sınıflık şema** anlatılıyor
  → artık 7 SORA + UNKNOWN(7) (`v2.0`).
- [ ] **P0** `CHECKLIST.md` §3: `safe_classes: [1,2,3]`, skor `0.7·risk +
  0.3·mesafe` → artık `[0,1]` ve `0.5 / 0.15 / 0.35` + bellek + gölge +
  mandal + sınıf dikişi.
- [ ] **P0** `CHECKLIST.md` §4 "✅ Kontrol değişkeni alan oranı" → ölçüldü,
  açık alanda **%0** aktif; ⚠️ olmalı.
- [ ] **P1** `PLAN.md` K7 ve `CHECKLIST.md` §7.3 "dördüncü test tek sert
  eleme" → artık yalnız koridor sert, bellek ve gölge skor cezası.
- [ ] **P1** `PLAN.md` §4 madde 6 ve 10, `DURUM.md` §8/2, #14, #16 →
  kapandı olarak işaretle.
- [ ] **P1** `CHECKLIST.md`'ye yeni bir bölüm: §19-22'nin isterleri
  (kontrol, toplu koşum, bozucu) karşılama durumu.
- [ ] **P2** Kaynak isterleri `docs/isterler/` altına al (§0).

### 5.6 Tez ve poster teslimleri

| Teslim | Durum |
|---|---|
| Kontrol bölümü metni + sayıları | ✅ `TEZ_NOTLARI.md` §2 |
| Şekil: irtifa–hata (açık vs kapalı) | ✅ `kontrol_bant.png` |
| Şekil: üç kol RMS dağılımı | ✅ `kontrol_dagilim.png` |
| Şekil: yatış–kapsam | ✅ `algi_egim.png` |
| **Şekil: RGB \| gerçek \| tahmin üçlüsü** | ❌ model gerekiyor |
| **Tablo: karışık vs LODO** | ❓ eğitime bağlı |
| **Şekil: irtifa–hız, üç yasa** (irtifa / kapsama / τ) | ❌ Hat 2'ye bağlı |
| Literatür karşılaştırması | ✅ `ARASTIRMA_KONTROL_SEGMENTASYON.md` (künyeler doğrulanmalı) |

---

## 6. Özet

**Kök brief'in Faz 1-4'ü, dinamik engel görevi, düzeltme isteklerinin
tamamı (7 hariç) ve yeni istekler bitti.** Kontrol tarafı brief'in
istediğinin ötesine geçti (kapalı çevrim, türetilmiş kazançlar, bozucu
bastırma, toplu istatistik).

**Eksik olan iki şey, tezin iki ana hattının ta kendisi:**

1. **Faz 5 — gerçek segmentasyon modeli.** Eğitim hattının veri tarafı hazır;
   eğitim sonuçları ve simülasyona bağlanması eksik.
2. **Görüntü-tabanlı iniş kontrolü.** Yasa var ama açık alanda hiç çalışmıyor
   (ölçüldü, %0). Hangi kontrolcünün yazılacağı senin kararını bekliyor.

İkisinin dışında: bir güvenlik işi (token), bir doğrulama işi (GUI) ve
kodla çelişen doküman satırları.

**Önerilen sıra:** 🔒 token → §4 kararları → Hat 1 eğitim sonuçları (arka
planda GPU'da koşarken) → Hat 2 kontrolcü → bayat dokümanlar → GUI
doğrulaması.
