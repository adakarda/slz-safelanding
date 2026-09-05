# Tez ve poster notları

Postere ve bitirme dokümanına doğrudan girebilecek malzeme. Ayrıntılı mühendislik
günlüğü `docs/DURUM.md`'de; burası yalnızca **savunulabilir sayılar ve gerekçeler**.
Bu dosya iş ilerledikçe güncellenir; her yeni sonuç postere/rapora konulabilirliğine
göre buraya eklenir.

Ölçümlerin tamamı sabitlenmiş senaryoda alınmıştır: sabit başlangıç konumu, sabit
hareketli düzeni (3 yaya + 2 araç), aynı dünya. `./src/eland_sim/scripts/dene.sh`
ile tekrarlanabilir.

---

## 1. Sistem, tek paragraf

PX4 v1.17 SITL + Gazebo Harmonic üzerinde, PX4'ün kendi Return davranışının
yerine geçen kayıtlı bir uçuş modu (`px4_ros2::ModeBase`). Aşağı bakan kameradan
gelen sınıf maskesi ters perspektif dönüşümüyle yer düzlemine yansıtılır, zaman
içinde füzyonlanır; iniş alanı dört testten geçen hücreler arasından seçilir
(SORA ayrımı, geometrik sığma, bölge büyüklüğü, **hareketli engellerin gideceği
yer**). Dördüncü test bu çalışmanın katkısıdır; SafeLand'in tepkisel HOLD/ABORT
davranışı arkada yedek olarak durur.

---

## 2. Kontrol: dikey hız döngüsü

### 2.1 Bulunan kusur

İniş yasası bir dikey hız üretiyor ve bunu PX4'e **komut değil, üst sınır**
olarak veriyordu (`goto` setpoint'inin `max_vertical_speed` alanı). PX4 tarafında
(`GotoControl.cpp:203`):

```
max_vertical_speed = constrain(istenen, 0, MPC_Z_V_AUTO_DN)
```

Yani istenen hız hem araç parametresiyle kırpılıyor hem de hedefe doğru **kendi
yumuşatılmış profili** planlanıyor. Sınır, izlenecek bir referans değildir — ve
kimse istenen ile olan arasındaki farkı ölçmüyordu.

**Taban ölçüm (açık çevrim, yasa tavanı 2.0 m/s):**

| İrtifa bandı | Komut | Gerçekleşen | Hata |
|---|---|---|---|
| 10 m üstü | 2.00 m/s | 1.30 m/s | −0.70 |
| 5-10 m | 1.98 | 1.50 | −0.49 |
| 2-5 m | 0.89 | 0.40 | −0.48 |
| 0-2 m | 0.36 | 0.27 | −0.09 |

Eksiklik yere yaklaşırken değil **yüksekte** en büyük; yani "hedefe yaklaşırken
yavaşlıyor" açıklaması geçersiz. Gerçekleşen hız hiçbir koşuda 1.5 m/s'yi
geçmedi — `MPC_Z_V_AUTO_DN` varsayılanı.

### 2.2 Adım 0 — doygunluğu hizala

Yasanın tavanı (2.0) tesisin sınırının (1.5) üstündeydi: komut aralığının üst
dörtte biri erişilemezdi. İki yön de denendi.

| Deneme | Ortalama hata | 10 m üstü | Sonuç |
|---|---|---|---|
| Tavan 2.0 (taban) | −0.40 m/s | −0.70 | erişilemez aralık |
| **Tavan 1.5'e indirildi** | **−0.26** | **−0.51** | tercih edilen |
| PX4 sınırı 2.0'a çıkarıldı | −0.52 | −0.73 | işe yaramadı |

Sınırı yükseltmek yardımcı olmadı: hız yine 1.5'te kaldı, iniş uzadı. Çünkü
`goto` denetleyicisi hızı takip etmiyor, konuma göre profil planlıyor. Bu, tek
başına bir bulgudur: **açık çevrimde tavanı yükseltmek hızlandırmaz.**

### 2.3 Adım 1 — döngüyü kapat

Alçalma fazında yatay eksen konum kontrollü kalır (doğrulanmış alandan kaymamak
için), dikey eksen hız komutu olarak sürülür:

```
v_tavan = clamp(k_boyut · √A , v_min , v_max)          A: alan [m²]
v_ref   = clamp(v_tavan · (1 − ρ) , v_min , v_tavan)   ρ: alanın görüntüyü doldurma oranı
e       = v_ref − v_ölçülen
u       = v_ref + Kp·e + I                    (ileri besleme + PI)
I      += (Ki·e + Kaw·(u_sat − u)) · dt       (geri hesaplamalı doygunluk koruması)
u_sat   = clamp(u , 0 , v_max)
```

Üç tasarım kararı ve gerekçeleri:

- **İleri besleme referansın kendisidir.** Tesis, PX4'ün hız denetleyicisidir;
  beklenen durum "v iste, v al"dır. Bu yapı sayesinde Kp = Ki = 0 seçimi eski
  açık çevrim davranışını birebir üretir — iki kolu karşılaştırılabilir kılan şey
  budur.
- **Geri hesaplamalı integral koruması.** Çıkış son iki metrede taban hızda
  doyuyor; koruma olmadan integral şişer ve yere en yakın anda aşım yapar.
- **Çarpmasız geçiş.** Her alçalma girişinde integral sıfırlanır; HOLD'dan veya
  terk edilmiş bir denemeden taşınan integral, komutu tam da yere yakın anda
  sıçratır.

**Sonuç (aynı senaryo, tavan üç kolda da 1.5 m/s):**

| Kol | Ortalama hata | Mutlak ortalama | RMS | 10 m üstü | 5-10 m |
|---|---|---|---|---|---|
| Açık çevrim | −0.26 m/s | 0.27 | **0.413** | −0.51 | −0.06 |
| **PI + ileri besleme** | **−0.09** | **0.10** | **0.207** | **−0.09** | **−0.01** |
| Yalnız P (Ki = 0) | −0.14 | 0.15 | 0.226 | −0.15 | −0.10 |

Kapalı çevrim RMS izleme hatasını **yarıya** indirir. İntegralin katkısı yüksek
irtifa bandında tutarlı ama küçüktür (−0.15 → −0.09); dürüst ifade: asıl kazanç
açık→kapalı geçişindedir, P→PI ikincil bir iyileştirmedir.

Kalan hata 0-2 m bandında yoğunlaşır (−0.14 m/s): yer etkisi ve iniş algılama
eşiği. Kapatılması amaçlanmadı — dokunma anında yavaş kalmak güvenli yöndür.

### 2.4 Postere ne koymalı

- **Tek şekil:** irtifa-hata çubuk grafiği, açık vs kapalı çevrim (yukarıdaki
  tablonun son iki sütunu).
- **Üç sayı:** RMS 0.413 → 0.207 m/s; 10 m üstü hata −0.51 → −0.09 m/s;
  erişilemez komut aralığı %25 → %0.
- **Tek cümle:** "İniş yasasının çıktısı bir üst sınır olarak veriliyordu;
  referans olarak izlenmeye başlanınca izleme hatası yarıya indi."

### 2.5 Sıradaki kontrol işleri

1. **Sistem tanımlama:** dikey kanala basamak (0.5 → 1.5 m/s), birinci mertebe +
   ölü zaman modeli, IMC/λ kuralıyla analitik kazanç seçimi, elle ayarla
   karşılaştırma. Şu anki kazançlar (Kp 0.8, Ki 0.6) mühendislik seçimidir,
   türetilmiş değildir — tezde bu açıkça yazılmalı.
2. **Bozucu bastırma:** Gazebo rüzgârıyla basamak ve darbe; toparlanma süresi ve
   iniş konum hatası.
3. **Yatay eksen:** şu an tamamen PX4'ün konum döngüsünde. Hareketli engel
   tahminini ileri besleme olarak kullanan bir dış çevrim güdüm yasası, daha
   büyük ama daha özgün bir katkı olur.

---

## 3. Karar döngüsü (poster için özet)

Şikâyet "iniş yeri seçimi uzun sürüyor" idi. Profil çıkarıldığında darboğaz
beklenen yerde değildi.

| Ölçüm | Öncesi | Sonrası |
|---|---|---|
| Yörünge testi (karar karesinin %95'i) | 44.2 ms | **2.6 ms** |
| Aday üretilmeyen kare | 79/152 | **0/152** |
| Aday kaybı (iniş terk edilmesi) | 3 | **0** |
| Durum geçişi | 8 | **3** |
| SEARCH'te geçen süre | 15.0 s | **0.3 s** |
| Sonuç | 3 deneme tükendi | tek denemede iniş |

Asıl kusur hız değil **mantıktı**: güvenliği artırmak için eklenen katman
(geçilmiş zemin + yaklaşma gölgesi) trafik varken uygun hücrelerin tamamını
siliyor, mod 3 s aday göremeyince inişi bırakıp PX4'ün kör Descend'ine
düşüyordu. Düzeltme bir sıralama ilkesi: **yalnızca tehlikenin gideceği yer
yasaktır; geçmiş ve yaklaşma yolu skorda ödenen bir bedeldir.**

Poster cümlesi: *"Kısıt eklemek her zaman güvenliği artırmaz — hiçbir seçenek
bırakmayan bir kısıt, sistemi daha kötü bir yedeğe düşürür."*

### 3.1 İniş alanı sınıf sınırına oturmasın

Açıklık ölçüsü "inilebilir olmayan en yakın hücreye uzaklık" idi; iki inilebilir
sınıfın (çim/asfalt) arasındaki dikiş görünmüyordu.

| Seçilen site | Öncesi | Sonrası |
|---|---|---|
| Sınıf dikişine uzaklık, ortanca | 0.80 m | **7.58 m** |
| 2 m'nin altında kalan örnek | 14/22 | **0/22** |

Gerekçe kontrol tarafıyla da ilgili: dikiş, maskenin en güvenilmez olduğu yerdir
ve genelde gerçek bir basamaktır (bordür) — iniş takımı için devrilme riski.

---

## 4. Yöntem notları (savunmada sorulur)

- **Tekrarlanabilirlik:** sabit tohum, sabit hareketli düzeni. Rastgele düzenden
  alınan sayılar birbiriyle karşılaştırılamaz.
- **Tek koşu kanıt değildir:** aynı ayarla aday sıçraması koşudan koşuya 1 ile 7
  arasında değişti. Kapalı çevrim ölçümleri sabit senaryoda ve aynı fazda
  (VALIDATE + COMMIT) alınmıştır.
- **Ölçüm araçları depoda:** `tools/descent_probe.py` (dikey hız izleme),
  `tools/measure_tracking.py` (hareketli engel izleme), `tools/make_params.py`
  (koşu başına parametre türevi).
- **Bilinen açıklar:** araç hız kestirimi gerçeğin ~%52'si (LSQ penceresi rota
  dönüşlerini içeriyor); segmentasyon hâlâ Gazebo etiket kamerasından geliyor,
  tahmin modeli veri kümesi hazır olduğunda eklenecek.
