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

**Sonuç (aynı senaryo, tavan üç kolda da 1.5 m/s, birer uçuş — tekrarlı
ölçüm §2.6'da):**

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
- **Üç sayı** (üçer uçuşun ortancası, §2.6): RMS takip hatası **0.323 → 0.197
  m/s**; en kötü uçuş **1.83 → 0.21 m/s**; doğrulanmış siteden dokunma sapması
  **3.40 m → 0.27 m**.
- **Tek cümle:** "İniş yasasının çıktısı bir üst sınır olarak veriliyordu;
  referans olarak izlenmeye başlanınca hem hata yarıya indi hem de en kötü
  uçuş en iyisine yaklaştı."
- **İkinci şekil (varsa):** üç kolun RMS dağılımı — açık çevrimin kuyruğu
  tek bakışta görünür."

### 2.5 Kazançlar nereden geliyor (sistem tanımlama)

Önceki sürümde kazançlar (Kp 0.8, Ki 0.6) mühendislik seçimiydi. Türetmek için
tesisin ölçülmesi gerekiyordu — ve buradaki "tesis" yalnızca hava aracı değil,
**PX4'ün hız denetleyicisi + hava aracı + uXRCE bağlantısı**dır. Tek dürüst yol,
denetleyicinin kullandığı aynı setpoint yolundan bilinen bir işaretle sürmektir.

**Deney.** Moda bir kare-dalga tanımlama kipi eklendi (`ident_enabled`): alçalma
yasasının yerine simetrik kare dalga geçer, **kapalı çevrim devre dışıdır**
(ölçülen şey tesis olmalı, kontrolcü değil) ve mod inişe geçmez. Tek alçalma
basamağı yerine kare dalga, çünkü tek basamak yer gelmeden önce bir geçici
rejim verir; kare dalga her yarım periyotta bir verir ve inişin gerçekten
olduğu irtifada kalır. Örnekleme PX4'ün hız mesajından, ~48 Hz.

**Sonuç — ve beklenen modelin reddi.** Üç genlikte ölçüldü:

| Genlik | Basamak | Kazanç K | Ölçülen eğim | Rampa süresi | Uydurulan τ |
|---|---|---|---|---|---|
| ±1.0 m/s | 1.88 m/s | 1.011 | 4.94 m/s² | 0.40 s | 0.010 s (ızgara tabanı) |
| ±0.3 m/s | 0.55 m/s | 1.025 | 1.67 m/s² | 0.34 s | 0.010 s (ızgara tabanı) |

Birinci mertebe + ölü zaman modeli **uymadı ve uymaması bilgi verdi**: τ her
genlikte arama ızgarasının tabanına yapıştı, ölçülen eğim ise genlik küçülünce
düştü (4.94 → 1.67 m/s²). Sabit bir ivme sınırı olsaydı eğim genlikten
bağımsız olurdu; düşmesi **jerk sınırlaması** demektir. Yani geçici rejimi
PX4'ün yörünge planlayıcısının jerk/ivme limitleri şekillendiriyor, bir zaman
sabiti değil. Üstel eğriye rampa uydurmak, ölü zamanı 0.92-1.25 s gibi anlamsız
değerlere itiyordu — modelin yanlış olduğunun işareti buydu.

**Kalan model:** birim kazanç (K = 1.01-1.03, üç ölçümde tutarlı), küçük
işarette ölü zaman θ ≈ 0.28 s, geçici rejim limit-şekilli.

**Türetim.** IMC kuralı τ → 0 (ölü zaman baskın) durumunda neredeyse saf
integratöre çöker:

```
Ki = 1 / (K · (λ + θ))        Kp → 0
λ = 1.5·θ = 0.42 s  →  Ki = 1.39 1/s ,  Kp = 0
```

`Kp → 0` burada dejenere bir sonuç değil, **doğru sonuç**: döngü referansı zaten
ileri besliyor ve K ≈ 1 olduğu için oransal terimin kalıcı rejimde sağlayacağı
bir şey yok. İşi yapan ileri beslemedir; integral yalnızca kalan sapmayı alır.

**Doğrulama.** Türetilmiş kazançlar (Kp 0, Ki 1.39) uçuruldu ve elle
ayarlananla karşılaştırıldı — sonuçlar §2.6'da. Kısaca: ikisi ölçüm gürültüsü
içinde aynı, yani elle seçim doğru bölgedeymiş; fakat artık **neden** o
bölgede olduğu gösterilebiliyor ve oransal terimin gereksiz olduğu ölçülmüş
durumda.

### 2.6 Doğrulama: üç kol, üçer uçuş

Tek koşu yetmedi ve bunu ölçerek öğrendik: açık çevrim kolu aynı sabit
senaryoda bir uçuşta RMS 0.413, başkasında 0.235 verdi, çünkü açık çevrimdeki
eksiklik `goto` planlayıcısının o uçuşta kurduğu profile bağlı. Bu yüzden her
kol üç kez uçuruldu.

| Kol | RMS takip hatası, ortanca [en iyi, en kötü] | Ortalama hata |
|---|---|---|
| Açık çevrim (yasa çıktısı = üst sınır) | **0.323** [0.322, **1.829**] | −0.17 |
| Elle ayarlı PI (Kp 0.8, Ki 0.6) | **0.201** [0.190, 0.206] | −0.09 |
| Türetilmiş (Kp 0, Ki 1.39) | **0.197** [0.186, 0.214] | −0.08 |

İki okuma çıkıyor ve ikisi de tezlik:

**1. Türetilmiş kazanç elle ayarlananla aynı.** 0.197 ile 0.201 arasındaki fark
ölçüm gürültüsünün içinde. Yani elle seçim doğru bölgedeymiş — ama artık
neden orada olduğu gösterilebiliyor ve **oransal terimin gereksiz olduğu**
ölçülmüş durumda (türetilmiş kolda Kp = 0).

**2. Açık çevrimin asıl sorunu ortalaması değil, kuyruğu.** Üç uçuşun ikisi
0.32 civarında, biri **1.83**. O uçuşta alçalma 22 s yerine **39 s** sürdü ve
uçak doğrulanmış siteden **3.40 m** uzağa dokundu; 0-2 m bandında komut
0.36 m/s iken gerçekleşen −0.02 m/s, yani araç inmeyi bırakıp asılı kaldı.
Sebep yapısal: `goto` bir konum setpoint'ine planladığı için hedef irtifaya
yaklaşırken dikey hızı kendiliğinden sıfırlıyor; yasa hâlâ "alçal" diyor ama
söylediği şey bir sınır olduğu için kimse onu takip etmiyor. Kapalı çevrimde
aynı senaryoda dokunma sapması 0.02-0.27 m.

Poster cümlesi: *"Açık çevrimde ortalama iyi görünüyordu; üç uçuşun biri
inmeyi bırakıp asılı kaldı. Kapalı çevrimde en kötü uçuş bile en iyisine
yakın."*

### 2.7 Bozucu bastırma: yöntem ve iki ölçüm tuzağı

**Bozucu nasıl veriliyor.** Gazebo'nun `WindEffects` sistemi, kuvvet uyguladığı
her linkte `<enable_wind>` ister; bizim hava aracı PX4'ün x500'ünü `merge` ile
içeriyor ve orada o bayrak yok. Onu eklemek, projenin kasten çatallamadığı tek
yere yerel bir yama koymak olurdu. PX4'ün SITL sunucusu ise zaten
`gz-sim-apply-link-wrench-system` yüklüyor, dolayısıyla gövdeye doğrudan
**yanal kuvvet** verilebiliyor (`tools/wind_inject.py`; adım, hamle, rampa
profilleri).

Tezde açıkça yazılması gereken sınır: bu bir **kuvvet bozucusudur**,
aerodinamik rüzgâr modeli değil. Eşdeğeri, küçük bir multikopter için sürükleme
kabaca `F ≈ 0.5·ρ·Cd·A·v² ≈ 0.06·v²` N alınarak verilebilir — 10 N ≈ 13 m/s.
Model, dönme momenti üretmez ve hız bileşenine bağlı değildir; yani gerçek
rüzgârın uçağı çevirme etkisi bu deneyde yoktur.

**Tuzak 1 — kuvvet hiç uygulanmamıştı.** İlk dört "rüzgârlı" koşu kaydedildi ve
sonuçları anlamsızdı: 4 N'da yatay sapma, rüzgârsız koşudan *küçük* çıkıyordu.
Sebep, PX4'ün modele kendi örnek indisini eklemesi: model
`x500_seg_cam_down_0`, benim gönderdiğim ise `x500_seg_cam_down`. Var olmayan
bir linke wrench yayınlamak **hata vermez**, `gz topic` sıfır döner ve hiçbir
şey olmaz. Havada asılıyken 10 N uygulayıp konumu ölçen bir kontrol koşusu
bunu ortaya çıkardı: 0.02 m. Araç adı artık çalışma anında topic listesinden
bulunuyor.

Genel ders, poster için de geçerli: **bir bozucu deneyinde ilk doğrulanması
gereken şey, bozucunun gerçekten uygulandığıdır.** Düzeltmeden sonra aynı
ölçüm 10 N altında 0.55 m kayma verdi.

**Tuzak 2 — yatay hata metriği site hareketini sapma sanıyordu.** Uçağın
*o an yayınlanan* siteye uzaklığı ölçülüyordu; site sıçradığında uçak hiçbir
yere kaymadan aniden "uzak" görünüyor. Ortalama, tek bir sıçramayı kalıcı bir
kayma gibi gösteriyordu (rüzgârsız koşu 0.96 m ortalama, rüzgârlı koşu 0.08 m —
tek fark sıçrama sayısıydı). Metrik ortanca + p90 + en büyük olarak
değiştirildi ve `site_jumps` ile birlikte okunuyor.

### 2.8 Bozucu bastırma: sonuçlar

**Kalıcı rejimde yetki sınırı.** Kuvvet 80 s boyunca 0'dan 20 N'a doğrusal
artırılırken uçak havada tutuldu ve konum sapması ölçüldü. Basamak basamak
denemek yerine rampa: her nokta bir uçuşa mal olmuyor ve sınır kaba bir ızgaraya
düşmüyor.

| Kuvvet | 2 | 6 | 10 | 12 | 16 | 20 N |
|---|---|---|---|---|---|---|
| Sapma | 0.03 | 0.21 | 0.10 | **1.68** | 0.28 | 0.04 m |

Uçak **20 N'a kadar konumunu koruyor**; sapma yalnızca kuvvet değişirken
geçici olarak büyüyor (en fazla 1.68 m) ve sonra sıfıra dönüyor — konum
denetleyicisinin integral etkisi. Teorik sınırla tutarlı: m = 2.0 kg ve
`MPC_TILTMAX_AIR` = 45° ile karşılanabilecek azami yanal kuvvet
`m·g·tan45° = 19.6 N`; 10 N için gereken eğim `atan(10/19.6) = 27°`.

**İniş sonucu, adım bozucusu altında.** Kalıcı yetki ile iniş başarısı aynı
şey değil:

| Bozucu | İniş | Dikey RMS | Siteye ortanca sapma | Dokunma sapması |
|---|---|---|---|---|
| Yok | ✓ | 0.186 m/s | 0.04 m | 0.06 m |
| 10 N adım (~13 m/s) | **4/4** | 0.19-0.22 | 0.12-0.48 m | 0.48-2.15 m |
| 15 N adım | **1/4** | — | 18-38 m | 39-590 m |
| 20 N adım (~18 m/s) | ✗ | — | 458 m | — |

10 N'da dikey takip rüzgârsız koşudan ayırt edilemiyor (0.19-0.22'ye karşı
0.186 m/s) ve dört uçuşun dördünde de hiç geçersiz aday üretilmedi. Bozulan tek
şey dokunma hassasiyeti: 0.06 m yerine 0.48-2.15 m. Yani 10 N'da sistem
"çalışıyor ama daha az isabetli"; 15 N'da ise çalışmıyor. Geçiş keskin.

**Kritik bulgu: kontrolcü değil, algı çöküyor.** 15 N'da başarısız olan uçuşta
157 adayın **156'sı geçersizdi** — dedektör "no cells in C_safe" ve "nothing
eligible" diyordu, yani harita hiç uygun hücre üretemedi. Mod arama zaman
aşımına düşüp kör inişe geçti ve kuvvet itmeye devam ettiği için araç 625 m
uzağa sürüklendi. Dikey döngü bu sırada çalışmaya devam ediyordu; kaybedilen
şey iniş yerinin kendisiydi.

Yani zarfın sınırını belirleyen **aracın kontrol yetkisi değil, algı
zincirinin bozucu altında aday üretebilmesi**. Tez için doğru cümle bu:
*bozucu bastırma bir kontrol problemi olarak çözülmüş görünse de, sistemin
kırılma noktası algı tarafındadır.*

**Yöntem uyarısı ve tekrarlar.** 15 N'da ilk uçuş sorunsuz indi; bu tek sonuca
güvenmeyip üç tekrar daha alındı ve **üçü de başarısız** oldu (biri "indi"
raporladı ama doğrulanmış siteden 317 m uzakta, üstelik hız kayıtları fiziğin
patladığını gösteriyor). Toplam: 15 N'da 4 denemede 1 başarı. Başarısız
uçuşlarda 125-128 kare aday üretilemedi.

Ders, sayının kendisinden daha taşınabilir: **sınır bölgesinde tek koşu, işareti
bile yanlış verebilir.** İlk 15 N uçuşuna bakıp "dayanıyor" demek, üç uçuşluk
kanıtın tam tersi olurdu.

### 2.9 Algı neden çöküyor: ölçülen mekanizma

"Algı çöküyor" bir gözlemdi, açıklama değildi. İki aday vardı ve farklı
çözümler gerektiriyorlardı: **eğim** (yanal kuvvet sürekli bir yatış gerektirir,
yatan bir araçta aşağı bakan kamera başka yere bakar) ve **sürüklenme**
(füzyonlu harita bir hücrenin sınıfı oturana kadar birkaç kare kanıt ister,
sürüklenen araç her karede yeni zemin tarar).

Adım bozucusu bu soruyu cevaplayamaz: 15 N'lık koşuda araç takla attı (eğim
154°, hız 83 m/s) ve sonrasındaki her örnek bir çarpışmayı tarif ediyor. Rampa
ise konumu koruyarak eğimi 0'dan ~40°'ye yürütüyor — böylece eğim **tek başına**
bağımsız değişken oluyor.

**Sonuç (uçak 20 m'de asılı, hız ≤ 2.6 m/s):**

| Eğim | Anlık haritada bilinmeyen | Füzyonlu haritada bilinmeyen |
|---|---|---|
| 0-5° | 0.11 | 0.06 |
| 5-10° | 0.16 | 0.04 |
| 10-20° | 0.25 | 0.03 |
| 20-30° | **0.37** | **0.02** |

Anlık haritada güvenli sınıf oranı 0.77'den 0.57'ye düşüyor. Yani eğim
gerçekten anlık görüşü bozuyor — ama füzyonlu harita neredeyse hiç
etkilenmiyor, çünkü araç yerinde durdukça daha önce görülmüş zemin bellekte
kalıyor.

**Birleşik açıklama.** Tek başına eğim iniş için yeterli değil; tek başına
sürüklenme de değil. 15 N'da ikisi birlikte oluyor: 15 N için gereken yatış
`atan(15/19.6) = 37°` — anlık kapsamın üçte birinden fazlasını götüren bir
açı — ve araç aynı anda hareket ettiği için füzyonun geri düşeceği eski kanıt
da yok. Uygun hücre kümesi bu yüzden boşalıyor.

Bu, gelecek iş için somut bir yön de veriyor ve tezde öyle yazılmalı:
**çözüm kontrol tarafında değil.** Ya kamera yatıştan bağımsızlaştırılmalı
(gimbal; PX4'ün kendi `x500_gimbal` modeli var), ya da karar katmanı harita
tazeliğini bir girdi olarak kullanmalı — "burayı 8 saniyedir görmedim" ile
"burayı şimdi görüyorum" aynı güvenle kullanılmamalı.

### 2.10 Sıradaki kontrol işleri

1. **Bozucu bastırma:** Gazebo rüzgârıyla basamak ve darbe; toparlanma süresi ve
   iniş konum hatası.
2. **Yatay eksen:** şu an tamamen PX4'ün konum döngüsünde. Hareketli engel
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

## 3.2 Toplu koşum: tek koşudan istatistiğe

O ana kadar her sayı tek bir koşudan geliyordu. Bu, iki ayarı karşılaştırmak
için doğru yöntemdir (sabitlenmiş sahne, tek değişken), ama "sistem çalışıyor"
demek için yanlıştır. `tools/batch_run.sh` N rastgele dünyada uçurur — her koşu
kendi doğuş konumunu ve kendi hareketli düzenini koşu indisinden çeker, yani
küme tekrarlanabilir (koşu i her zaman 1000+i tohumunu alır).

**10 rastgele dünya, tek konfigürasyon:**

| Ölçüm | Ortanca | Çeyrekler arası | En kötü |
|---|---|---|---|
| İniş tamamlanan | **10/10 (%100)** | — | — |
| Alçalma süresi | 22.15 s | [21.97, 22.19] | 22.63 |
| Dikey hız RMS takip hatası | 0.19 m/s | [0.18, 0.20] | 0.22 |
| Aday yayın hızı | 1.42 Hz | [1.42, 1.45] | 1.46 |
| Aday üretilmeyen kare | 2.5 | [0.25, 3.00] | 4 |
| 3 s üstü aday boşluğu | **0** | [0, 0] | 0 |
| Durum geçişi | 2 | [2, 3] | 3 |
| ABORT | **0** | [0, 0] | 0 |

Ortanca ve çeyrekler, ortalama ve standart sapma değil: dağılımlar küçük ve
çarpık, ve kötü giden bir koşuyu ortalamanın saklamasına izin verilmemeli.

**Düzenek kurulur kurulmaz bir kusur buldu.** İkinci rastgele dünyada uçak
orijinin batısında doğdu ve dünya hiç üretilemedi: `--focus -3.23,-22.60`
argümanı, değeri eksi işaretiyle başladığı için argparse tarafından bir sonraki
seçenek sanılıyordu. O güne kadarki bütün ölçümler orijinden ya da doğusundan
başladığı için kusur görünmemişti. Postere değecek cümle: *tek senaryoda
görünmeyen kusur, on rastgele dünyada ikinci koşuda çıktı.*

**Dikkat:** "iniş tamamlandı" iniş algılayıcısının tetiklendiğini söyler,
güvenli bir yere inildiğini değil. Skorlayıcı bu yüzden inilen yerin risk
skorunu, açıklığını ve dokunmanın doğrulanmış siteden sapmasını da kaydeder.

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
