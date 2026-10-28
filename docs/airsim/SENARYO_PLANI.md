# AirSim acil iniş senaryosu — plan

> **Tarih:** 2026-10-28. **İsteyen:** Arda. **Durum:** plan; kodlama Arda'nın onayından sonra.
> Etiketler: **ölçülen**, **_hesap**, **_tahmin**.

## 1. Senaryo (Arda'nın tarifi)

1. Her açılışta dron AirSimNH haritasında **farklı bir yerde doğar**.
2. **Farklı ve özgün bir rota** oluşturulur. Rota sabit bir yükseklikte ve haritanın merkez bölgesi içinde kalır.
3. Dron rotayı izler. Rotanın rastgele bir noktasında **birden acil iniş başlar**.
4. İnişi **son segmentasyon modelimiz (v4)** ve **RL politikası** yapar.
5. Ekranda aynı anda görünenler:
   - kuşbakışı haritada çizili rota ve dronun canlı izi;
   - AirSim'in gimbal'lı segmentasyon kamerası (gerçek etiket);
   - bizim segmentasyon kameramız (v4);
   - RL komutları.

## 2. Elimizde olanlar (ölçülen, koddan)

| Parça | Nerede | Senaryoda kullanımı |
|---|---|---|
| Kuşbakışı harita | `C:\Users\arda_\airsim\orto_nh\harita.npz` + `harita_rgb.jpg`: 4000 × 4000 piksel, 0.2 m/px, ±400 m (PlayerStart merkezli); sınıf haritası ve "inilebilir" maskesi | rota çizimi, doğma yeri seçimi, iniş puanlama |
| Havada bir noktaya gitme | `run_airsim.sh --havada`: PX4'e `VEHICLE_CMD_DO_REPOSITION` (192), Hold modunda | rota noktaları tek tek gönderilir |
| Bilinen temiz doğma noktaları | `~/eland_veri/airsim_nh_baslangiclar.csv` (10 nokta) | yedek doğma listesi |
| RL tetiği | `eland_airsim.rl_tetik`, istasyonda "0" | acil iniş anı |
| v4 segmentasyonu | `run_airsim.sh --v3 --seg-model best_v4.pth` (28.10'da eklendi) | inişi yöneten maske |
| Gimbal kamera | `--gimbal` | dik bakan kamera |
| İniş puanlama | `inis_harita.py` (ortografik harita, zemin kuralı + SORA) | her koşunun sonucu |

## 3. Yapılacak parçalar

### A. Senaryo üreteci (`senaryo_uret.py`, ROS'suz, tek başına denenebilir)

- **Tohum:** her açılışta saatten alınır ve kaydedilir. Aynı senaryo istenirse `--tohum N` ile yeniden üretilir.
- **Merkez bölge:** PlayerStart çevresinde R yarıçaplı daire (öneri **R = 150 m**). Haritanın kenarından en az 30 m içeride.
- **Doğma yeri:** merkez içindeki "inilebilir" hücrelerden rastgele seçilir. Yapıya ve ağaca en az 5 m uzak olmalı. Kalkışta sorun çıkarsa bilinen 10 temiz noktaya geri dönülür.
- **Rota:** 3–6 nokta, sabit yükseklik (öneri **30 m**: ağaçların üstü ve eğitimdeki başlangıç aralığı 20–30 m).
  - Bacak uzunluğu 40–120 m.
  - Keskin geri dönüş yok (dönüş açısı ≤ 135°).
  - Bütün noktalar merkez içinde.
- **Özgünlük:** her rotanın bir özeti (noktalar 10 m'ye yuvarlanır) `senaryo_gecmisi.jsonl`'a yazılır. Daha önce görülmüş bir özet gelirse yeniden çekilir.
- **Acil iniş anı:** rota uzunluğunun %30–%85'i arasında rastgele bir nokta. Bir köşe noktasına en az 15 m uzak olur, böylece dron dönüş ortasında değil düz uçuşta yakalanır. Dron oraya varmadan haritada gösterilmez.
- **Çıktı:** `senaryo.json` (tohum, doğma yeri, rota, acil iniş noktası ve sebep metni). Ayrıca rotanın haritaya çizilmiş bir önizleme PNG'si.

### B. Görev uçuşu düğümü (`senaryo_ucus.py`)

- Kalkış (30 m) → rota noktaları `DO_REPOSITION` ile sırayla gönderilir. Bir noktaya 3 m kalınca sonrakine geçilir.
- Acil iniş noktasına gelince **RL Landing** tetiklenir. Gösterilecek sebep rastgele seçilir: "bağlantı kaybı", "batarya kritik" ya da "motor uyarısı". Sebep yalnız ekranda yazar; PX4'e arıza enjekte edilmez.
- **2. aşama (isteğe bağlı):** gerçek arıza akışı. Kumanda sinyali kesilir → PX4 arıza akışı → RL modu devreye girer. Bunun için RL modunun PX4'ün RTL modunun yerine kaydedilmesi gerekir (isteğe bağlı parametre, varsayılan kapalı). PX4 parametresi değişmez.
- İniş bitince sonuç ölçülür:
  - süre: acil durumdan temasa;
  - temas hızı;
  - iniş noktası, sınıf, zemin kuralı ve SORA (ortografik haritadan);
  - koşu klasörüne `sonuc.json`.

### C. Görev haritası paneli (`/eland/senaryo/harita` görüntü konusu)

- Merkez bölgenin kuşbakışı RGB görüntüsü (`harita_rgb.jpg`'den kesit).
- Üstüne çizilenler:
  - planlanan rota (numaralı noktalar);
  - dronun canlı izi ve yönü;
  - kameranın gördüğü alan (dörtgen);
  - acil iniş başlayınca kırmızı işaret ve "ACİL İNİŞ: sebep";
  - iniş noktası ve sonuç (yeşil: güvenli, kırmızı: güvensiz).
- Durum satırı: Kalkış / Rota WP 2/5 / ACİL İNİŞ / İndi (sınıf, süre).

### D. Tek ekran gösterim penceresi (`gosterim_izle.py`'nin yeni hâli)

Pencereler ayrı ayrı açılınca üst üste biniyordu (28.10 gece denemesi). Bu yüzden dört görüntü tek pencerede, sabit
yerleşimle gösterilir:

| Sol üst | Sağ üst |
|---|---|
| **Görev haritası** (rota + canlı iz) | **AirSim gimbal'lı segmentasyon** (gerçek etiket) |
| **Bizim segmentasyonumuz (v4)** | **RL komutları** |

AirSim'in kendi penceresi (3B görüntü) ayrı kalır.

### E. Toplu koşu ve ölçüm

- `senaryo_kos.sh --n 30`: her koşu farklı senaryo; sonuçlar tek tabloda.
- Ölçütler: güvenli iniş (zemin kuralı), SORA, süre, temas hızı, güvensiz iniş türü.
- Ön kayıtla, Faz 8'in bir parçası olarak koşulur (`docs/onkayit/airsim_faz7_onkayit.md`'nin devamı). İstenirse aynı
  senaryolar gerçek etiketle de koşulur (algı etkisini ayırmak için).

## 4. Model ve ayarlar

- **RL:** c13 tohum 0. v4 segmentasyonuyla hafif ortamda en iyi model: %88.9, 12.1 s (Düzeltme 29).
- **Kalkan:** eski kalkan 10 m. Kilitli kalkan `policy_node`'da henüz yok (Sefa taşıyor).
- **Segmentasyon:** v4 (`best_v4.pth`). AirSim'de ~1.3 kare/s (ölçülen, 28.10).
- **Depth Anything'li ajanlar** canlı Depth Anything ister; o ayrı bir iş.
- **Kurallar:** PX4 parametreleri değişmez. Açılıştan önce çalışan sim ya da eğitim kontrol edilir. Windows boş belleği
  izlenir.

## 5. İş sırası ve süre (_tahmin)

| Adım | İş | Süre |
|---|---|---|
| 1 | Senaryo üreteci + haritada rota önizlemesi (AirSim'siz denenir) | ~1 saat |
| 2 | Görev uçuşu düğümü + acil iniş tetiği | ~2 saat |
| 3 | Görev haritası paneli + tek ekran gösterim | ~1.5 saat |
| 4 | 5 deneme koşusu, düzeltmeler | ~1 saat |
| 5 | Masaüstü kısayolu (`AirSim_Senaryo.bat`) | kısa |
| 6 | (İsteğe bağlı) 30 koşuluk ölçüm, ön kayıtla | ~1.5 saat |
| 7 | (İsteğe bağlı) gerçek arıza akışı (2. aşama) | ~2 saat |

## 6. Bilinen riskler

- **v4 ile AirSim'de inişler henüz güvenilir değil:** 28.10 gece denemesinde 4 inişin 3'ü "bitki/yol" sınıfına
  oldu. Senaryo bunu açıkça gösterecek; gerçek etiketle karşılaştırma seçeneği bu yüzden var.
- **Rastgele doğma yeri:** ağaç altı ya da eğimli zemin kalkışı bozabilir. Bu yüzden inilebilir hücre filtresi ve
  10 noktalık yedek liste var.
- **AirSim performansı:** segmentasyon (GPU) + AirSim + PX4 aynı makinede çalışıyor. Rota uçuşunda kare hızı
  düşebilir; gerekirse rota hızı 3–4 m/s ile sınırlanır.

## 7. Arda'nın kararları (varsayılanlar parantez içinde)

1. Uçuş yüksekliği (30 m)?
2. Merkez bölgenin yarıçapı (150 m)?
3. Doğma yeri: tamamen rastgele inilebilir hücre mi, bilinen 10 nokta mı (rastgele hücre + yedek liste)?
4. Acil durum sebebi yalnız ekranda mı yazsın, yoksa 2. aşamada gerçek arıza akışı mı kullanılsın (önce ekranda)?
5. 30 koşuluk ölçüm yapılsın mı (evet, gösterim hazır olduktan sonra)?
