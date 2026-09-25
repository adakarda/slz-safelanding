# Araştırma Notu — Segmentasyon Eğitimi ve Görüntü-Tabanlı İniş Kontrolü

Bu dosya iki iş için hazırlandı:

1. **Tez posteri/sunumu için iki ana hattın** mevcut projedeki karşılığını
   göstermek.
2. Bu iki hattı derinleştirmek için **hazır araştırma promptları** ve
   literatürdeki karşılıklarını vermek.

Kaynaklar 2026-09-25'te web aramasıyla toplandı. **Künyeleri kendin doğrula** —
aşağıdaki bağlantılar arama sonucudur, hepsi okunup teyit edilmedi.

İlgili diğer dosyalar: `docs/DEVIR.md` (tüm proje), `docs/TEZ_NOTLARI.md`
(ölçülmüş sonuçlar), `docs/DURUM.md` (mühendislik günlüğü).

---

# BÖLÜM A — Projenin şu anki durumu, iki hat açısından

## A.1 Hat 1 (segmentasyon) açısından: şu an ne var

**Var olan:** Gazebo'nun **etiket kamerası** (`segmentation` tipi sensör,
320×240, 5 Hz). Dünyadaki her modele SDF'de bir etiket yazılı; kamera o
etiketleri piksel piksel döndürüyor. `perception_node` bunu proje
taksonomisine çeviriyor (7 sınıf + UNKNOWN).

**Olmayan:** Öğrenilmiş bir model. Yani mevcut "segmentasyon doğruluğu %100"
ifadesi bir ölçüm değil, **tanımın kendisi**. Danışman bunu doğru tespit etti:
sistem tahmin üzerinden çalışmalı.

**Projeye özel avantaj:** Etiket kamerası, RGB görüntüyle **hizalı ve mükemmel**
etiket üretiyor. Yani elle etiketleme olmadan, istenen büyüklükte bir veri
kümesi üretilebilir. Bu, literatürdeki sentetik veri hatlarının tam olarak
yaptığı şey (§C.4).

**Bilinen risk (ölçülmüş):** 20 m irtifada bir insan maskede **79-164 piksel**.
En yüksek sonuçlu sınıf, en küçük nesne. Düşük çözünürlüklü bir model insanı
tamamen kaybedebilir ve bu "biraz daha düşük mIoU" değil, üstüne inilen bir
insan demektir.

## A.2 Hat 2 (kontrolcü) açısından: şu an ne var, ne ölçüldü

Dikey eksende **kapalı çevrim PI + ileri besleme** çalışıyor (ayrıntı
`TEZ_NOTLARI.md` §2). Bu kontrolcünün referansı şu yasadan geliyor:

```
v_tavan = clamp(0.20·√alan , 0.3 , 1.5)               alan: m²  (metrik harita)
v_ref   = clamp(v_tavan·(1 − ρ) , 0.3 , v_tavan)      ρ: sitenin görüntüyü doldurma oranı
```

**Senin istediğin şey (ρ ile hız düşürme) tasarımda zaten var.** Ama ölçüm şunu
söyledi ve tüm kontrolcü tasarımını bu kısıtlar:

### Ölçüm 1 — ρ yolu açık alanda hiç çalışmıyor

Sabitlenmiş senaryoda bir iniş boyunca:

| İrtifa | Ekran doluluğu ρ | ρ yasası aktif | Komut edilen hız |
|---|---|---|---|
| 10+ m | 0.87 | **%0** | 1.50 m/s |
| 5-10 m | 0.91 | %0 | 1.50 |
| 2-5 m | 0.91 | %0 | 1.09 |
| 0-2 m | 0.69 | %0 | 0.40 |

Sebep: site kadrajdan taştığı sürece (`view_bounded == false`) ρ yakınlık
bilgisi taşımaz. Geometri:

```
ρ ≈ (R / F)²,   F = h·tan(FOV/2)    →    ρ ∝ 1/h²     ANCAK site kadraja sığdığı sürece
```

Site ayak izinden büyükse ρ → 1'de **doyar**. Açık çimende ρ zaten 0.87-0.91 ve
alçaldıkça değişmiyor. Bu yüzden kod irtifa yedeğine düşüyor — tembellikten
değil, bilgi olmadığı için.

Tarihsel not: eskiden yalnızca ρ kullanılıyordu ve açık çimende bütün iniş
0.3 m/s ile **73 saniye** sürüyordu (normali 27 s), çünkü ρ 0.81'de takılı
kalıyordu.

### Ölçüm 2 — Etiket maskesinden yakınlık çıkarılamıyor

"Kareler arası büyüme" fikri denendi: sınıf sınırlarının piksel uzunluğu `B`,
irtifa yarıya inince iki katına çıkmalı (`B ∝ 1/h`), o zaman
`τ = B / (dB/dt)` temas süresini verir. Ölçüldü:

| İrtifa | Sınır pikseli B | B×h (sabit olmalıydı) |
|---|---|---|
| 15+ m | 1561 | 26439 |
| 10-15 m | 1086 | 15239 |
| 5-10 m | **61** | 532 |
| 2-5 m | **0** | 0 |
| 0-2 m | **0** | 0 |

**Son 5 metrede etiket görüntüsünde hiçbir yapı kalmıyor.** İroni tezlik:
bir alanı iyi iniş yeri yapan şey (homojen, engelsiz, tek tip) onu yakınlık
ipucu olarak kullanılamaz yapıyor.

**Sonuç:** kamera-tabanlı yakınlık kontrolü **etiket maskesinden** kurulamaz.
RGB dokusundan kurulabilir (§B.2) — çimen tek *sınıf* ama tek *doku* değil.

### Ölçüm 3 — Tesis modeli (kontrolcü tasarımının girdisi)

Kare dalga tanımlamasıyla ölçüldü:

- Kazanç **K = 1.01-1.03** (ne istersen onu veriyor)
- Ölü zaman **θ ≈ 0.28 s**
- Geçici rejim **jerk/ivme sınırlı**, birinci mertebe değil (ölçülen eğim
  genlik küçülünce 4.94 → 1.67 m/s²'ye düştü; sabit ivme sınırı olsa
  değişmezdi)
- PX4 `GotoControl.cpp:203` istenen dikey hızı `MPC_Z_V_AUTO_DN` ile kırpıyor
  ve kendi profilini planlıyor → **sınır vermek referans vermek değildir**

Ölü zaman baskın IMC ile türetilen kazanç: `Ki = 1/(K(λ+θ))`, `Kp → 0`.

### Ölçüm 4 — Yarım kalan: RGB + optik akış

`rgb-akis-denemesi` dalında. 160×120 RGB kamera eklendi, Farneback akışından
ıraksama kestirilmeye çalışıldı, **ilk sonuç yetersizdi** (korelasyon −0.24).
Muhtemel sebep: taban çok kısa — 0.1 s'de genleşme %0.75, kare kenarında yarım
pikselin altında. Denenecekler dalın commit mesajında: 0.5 s taban, ötelemeyi
de modele katmak (`u = a + k·r`), gerekirse 320×240.

---

# BÖLÜM B — Hat 2: kontrolcü tasarımı için yol haritası

## B.1 Problem ifadesi (tez için)

> Segmentasyonla seçilmiş bir iniş alanına, **irtifa ölçümüne dayanmadan**,
> yalnızca görüntü düzlemindeki büyüklüklerle kontrollü bir iniş yapmak.

Bu ifade önemli çünkü "irtifa zaten var, EKF veriyor" itirazının cevabı:
eğimli/yükseltilmiş zeminde AGL yanlıştır, GPS kaybında irtifa kestirimi
bozulur, ve görüntü-tabanlı yaklaşım bu ikisinden bağımsızdır. Literatürde
bu argüman **constant divergence landing** çalışmalarının standart
gerekçesidir.

## B.2 Aday kontrolcüler

### (a) Kapsama oranı setpoint'i — PID

```
e(t) = ρ* − ρ(t)                     ρ* = 0.95 gibi sabit hedef
v_cmd = clamp(Kp·e + Ki∫e + Kd·ė , v_min , v_tavan)
```

- **Artısı:** en basit, mevcut `area_ratio` doğrudan kullanılır, doyumda
  güvenli yöne hata yapar (ρ > ρ* olduğunda hız tabana iner).
- **Eksisi:** ρ doyduğunda hata sabitlenir, kontrolcü bilgi almaz — "yavaş in"
  der ama *neden* olduğunu bilmez. Açık alanda 73 saniyelik sürünme riski.
- **Ne zaman uygun:** site kadraja sığdığında, yani dar/sınırlı alanlarda.

### (b) Sabit ıraksama / temas süresi (τ) kontrolü — **literatürün ana hattı**

Arılardan esinlenen klasik yasa. Dikey inişte optik akış ıraksaması
`D = vz/h` ve temas süresi `τ = 1/D`. `D` sabit tutulursa hem irtifa hem hız
üstel olarak azalır — yumuşak iniş kendiliğinden çıkar.

```
D_ölçülen = akış ıraksaması  (veya  2ρ̇/ρ  kapsamadan türetilmişi)
e = D* − D_ölçülen
v_cmd = PI(e)                        D* ≈ 0.1 … 1.0 1/s
```

- **Artısı:** irtifadan tamamen bağımsız; literatürde yerleşik; tez için en
  gösterişli; kapsama doyduğunda bile RGB dokusundan hesaplanabilir.
- **Eksisi:** `D` kestirimi gürültülü ve **irtifa düştükçe kararsızlaşıyor**
  (literatürde bilinen bir olgu: alçaldıkça efektif kazanç artar ve sabit
  kazançlı kontrolcü salınıma girer — bu yüzden **uyarlamalı kazanç**
  çalışmaları var, §C.1).
- **Kapsamadan türetilmiş hâli:** site kadraja sığdığı sürece `ρ ∝ 1/h²`
  olduğundan `ρ̇/ρ = 2vz/h = 2D` — yani **kapsamanın logaritmik türevi doğrudan
  ıraksamadır.** Bu, senin fikrinle literatürün ana hattını birleştiren köprü
  ve tezde vurgulanacak nokta budur.

### (c) Görüntü momentleriyle IBVS

Klasik görsel servolama: görüntü özelliklerini doğrudan hata olarak kullan.
İniş için kullanılan özellik genelde **alan momenti** — çünkü alan, derinliğin
(irtifanın) tersiyle ölçeklenir.

```
s = [x_g , y_g , a_n]        a_n = √(a*/a)  normalize alan (derinlik vekili)
ė = L_s · v                  L_s: etkileşim matrisi
v = −λ · L_s⁺ · (s − s*)
```

- **Artısı:** yatay ve dikey ekseni **birlikte** çözer (senin projende yatay
  eksen şu an tamamen PX4'te — bu gerçek bir boşluk); teorik çerçevesi sağlam.
- **Eksisi:** quadrotor **eksik tahrikli** (yatay kuvvet için yatmak zorunda),
  bu yüzden literatürde "sanal görüntü düzlemi" / "küresel izdüşüm" gibi
  ek yapılar kullanılıyor; matematiği en ağır seçenek.
- **Not:** bizim ölçtüğümüz yatış-kapsam bozulması (20-30°'de bilinmeyen oranı
  0.11 → 0.37) tam da IBVS literatüründeki "görüş alanı kısıtı" problemidir.

### (d) Denetimli (supervisory) melez — **pratikte önerilen**

Tek bir yasa her rejimde çalışmıyor. Üç rejim var ve her birinin doğal
gözlemcisi farklı:

| Rejim | Gözlem | Yasa |
|---|---|---|
| Site kadraja sığıyor (ρ < ~0.85) | ρ ve ρ̇ | (a) veya (b)'nin kapsama hâli |
| Site kadrajdan taşıyor, doku var | akış ıraksaması | (b) RGB ile |
| Doku da yok / güven düşük | irtifa (EKF) | mevcut yedek |

Anahtarlama kuralı ve **çarpmasız geçiş** (integral sıfırlama) zaten kodda var
— `emergency_landing_mode.hpp` içindeki `DescentRateController::reset()`.

## B.3 Deney tasarımı — neyi nasıl ölçeceksin

Her kontrolcü için **aynı** metrikler, `tools/run_scorer.py` zaten üretiyor:

| Metrik | Neden |
|---|---|
| Dokunma dikey hızı | Güvenli iniş ölçütü |
| Toplam alçalma süresi | Verimlilik; τ kontrolünün doğal maliyeti |
| İrtifa bandına göre takip hatası | Kontrolcü gerçekten takip ediyor mu |
| Dokunmanın doğrulanmış siteden sapması | Yatay eksen bozulmuş mu |
| Aday üretilmeyen kare | Algı kontrolü boğuyor mu |
| N rastgele dünyada başarı oranı | Tek koşu kanıt değil (`dene.sh toplu`) |

Karşılaştırma kolları: **(0) mevcut irtifa-tabanlı**, (a) ρ-PID, (b) τ-kontrol,
(d) melez. Kol başına en az 3 uçuş — bu projede tek koşunun işaretin kendisini
bile yanlış verdiği ölçüldü.

## B.4 Bu projeden çıkmış, tasarımı bağlayan gerçekler

Kontrolcü tasarlarken bunları varsayım değil **veri** olarak kullan:

1. ρ açık alanda doyuyor → saf ρ kontrolü açık alanda kör.
2. Etiket maskesi son 5 m'de bilgisiz → τ için RGB dokusu gerekli.
3. Tesis K ≈ 1, θ ≈ 0.28 s, jerk sınırlı → yüksek kazançlı D terimi anlamsız,
   ölü zaman baskın tasarım kuralları geçerli.
4. PX4'e sınır değil **referans** verilmeli.
5. Yatış 30°'yi aşınca kamera kapsamı üçte bir kayboluyor → görüş alanı kısıtı
   kontrolcünün içinde olmalı (IBVS literatürü bunu FOV constraint diye
   çözüyor).

---

# BÖLÜM C — Literatür haritası

## C.1 Sabit ıraksama / optik akış ile iniş (senin fikrinin ana hattı)

Arıların inişinden esinlenen ve "irtifa bilmeden in" diyen hat. Senin
"seçilen alanın karedeki değişim hızı" fikrinin literatürdeki tam karşılığı.

- **Adaptive Control Strategy for Constant Optical Flow Divergence Landing** —
  alçaldıkça efektif kazancın artması ve buna karşı uyarlamalı kazanç.
  https://arxiv.org/pdf/1609.06767
- **Vertical Landing for Micro Air Vehicles using Event-Based Optical Flow** —
  olay-tabanlı kamerayla, çerçeve-tabanlıdan çok daha yüksek ıraksama
  setpoint'leri (1.0 1/s'e kadar). https://arxiv.org/pdf/1702.00061
- **Constant Optical Flow Divergence based Robust Adaptive Control for
  Autonomous Vertical Landing of Quadrotors** (AIAA SciTech 2023) — model
  belirsizliği ve dış bozucu altında.
  https://arc.aiaa.org/doi/abs/10.2514/6.2023-1150
- **Evolution of robust high speed optical-flow-based landing for autonomous
  MAVs** (Robotics and Autonomous Systems) —
  https://www.sciencedirect.com/science/article/abs/pii/S0921889019302404
- **Neuromorphic control for optic-flow-based landings of MAVs using the Loihi
  processor** — https://arxiv.org/pdf/2011.00534
- **Monocular distance estimation with optical flow maneuvers and efference
  copies** — kararlılık-tabanlı mesafe kestirimi.
  https://iopscience.iop.org/article/10.1088/1748-3190/11/1/016004
- **Vertical Planetary Landing on Sloped Terrain Using Optical Flow Divergence
  Estimates** — eğimli zemin hâli. https://arxiv.org/pdf/2512.04373

**Tezde kullanılacak cümle:** *"Kapsama oranının logaritmik türevi, optik akış
ıraksamasının segmentasyon-tabanlı bir tahmincisidir: `ρ̇/ρ = 2·vz/h = 2D`."*
Bu, senin fikrini literatürün merkezine bağlar.

## C.2 Görüntü momentleriyle görsel servolama (IBVS) ile iniş

- **Autonomous landing of a VTOL UAV on a moving platform using image-based
  visual servoing** (ICRA) — https://ieeexplore.ieee.org/document/6224828/
- **Robust Image-Based Landing Control of a Quadrotor on an Unpredictable
  Moving Vehicle Using Circle Features** — daire momentleri, dönme
  değişmezliği, öteleme/dönme ayrıştırması.
  https://www.researchgate.net/publication/361242780
- **Image-based Visual Servoing Control of UAV Dynamic Landing under Field of
  View Constraints** — görüş alanı kısıtı; bizim yatış bulgumuzun literatür
  karşılığı. https://pure.bit.edu.cn/en/publications/image-based-visual-servoing-control-of-uav-dynamic-landing-under-/
- **Visual servoing of quadrotor UAVs for slant targets with autonomous object
  search** — https://journals.sagepub.com/doi/10.1177/09596518221144490

Anahtar kavram: **bölge-tabanlı görüntü momentleri** (nokta-tabanlıya karşı).
Alan momenti derinlik vekili olarak kullanılıyor — bu senin "kapsama oranı"
fikrinin klasik kontrol dilindeki adı.

## C.3 Segmentasyonla güvenli iniş alanı tespiti (projenin algı tarafı)

- **A Real-Time Semantic Segmentation Method Based on STDC-CT for Recognizing
  UAV Emergency Landing Zones** —
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10386455/
- **Safe Landing Zones Detection for UAVs Using Deep Regression** (IEEE) —
  https://ieeexplore.ieee.org/document/9867062/
- **Image Segmentation to Identify Safe Landing Zones for UAVs** —
  https://arxiv.org/abs/2111.14557
- **VisLanding: Monocular 3D Perception for UAV Safe Landing via Depth-Normal
  Synergy** — https://arxiv.org/pdf/2506.14525
- **Semantic segmentation based mapping systems for the safe and precise
  landing of flying vehicles** (IFAC) —
  https://www.sciencedirect.com/science/article/pii/S2405896323003105
- **Lightweight monocular vision pipeline for real-time safe landing zone
  detection** —
  https://www.sciencedirect.com/science/article/abs/pii/S0952197626008420

Bu hatta yaygın kalıp: **segmentasyon sınıflarını risk skorlarına eşlemek** —
bizim `class_risk` tablomuzun yaptığı şey. SegFormer gibi ViT tabanlı modellerin
risk haritalamada kullanıldığı belirtiliyor.

## C.4 Veri kümeleri ve sentetik veri üretimi (Hat 1'in omurgası)

- **MESSI: A Multi-Elevation Semantic Segmentation Image Dataset of an Urban
  Environment** — 2525 görüntü, **30/50/70/100 m** irtifalardan; irtifanın
  segmentasyona etkisini incelemek için tasarlanmış. Bizim "20 m'de insan 79
  piksel" problemimizin doğrudan muhatabı.
  https://arxiv.org/abs/2505.08589 · https://github.com/messi-dataset/messi-dataset
- **Semantic Drone Dataset (TU Graz)** — 5-30 m, 6000×4000, 22 sınıf
  (ağaç, çim, toprak, su, insan, araba, engel…), 400 eğitim / 200 test.
- **Synthetic-to-Real Pipeline for Safe Landing Zone Detection** — sentetik veri
  motoru + OneFormer; tam olarak bizim yapacağımız işin literatür karşılığı.
  https://arxiv.org/pdf/2606.14767
- **Synthetic Training Data for Semantic Segmentation of the Environment from
  UAV Perspective** (Aerospace 2023) — https://doi.org/10.3390/aerospace10070604
- **Semantic Segmentation Learning for Autonomous UAVs using Simulators and
  Real Data** — https://www.researchgate.net/publication/335714815
- **Domain Randomization and Pyramid Consistency** — hedef alan verisine
  erişmeden genelleme. https://arxiv.org/pdf/1909.00889

**Literatürden çıkan pratik kural:** sentetik veriyi **ara alan** olarak
kullanıp sonra gerçek veriyle eğitmek, doğrudan transfer öğrenmeden daha iyi
sonuç veriyor — yeter ki sentetik küme gerçek dünyadaki değişkenlikleri
(ışık, doku, irtifa) içersin.

---

# BÖLÜM D — Hazır araştırma promptları

Aşağıdakileri Claude Code'a ya da başka bir araştırma aracına doğrudan
yapıştırabilirsin. Her biri **çıktı formatını da** söylüyor; yoksa genel
özet alırsın.

## D.1 Kontrolcü tasarımı araştırması

```
Bir quadrotor için görüntü-tabanlı otonom iniş kontrolcüsü tasarlıyorum.
Bağlam: aşağı bakan kameradan semantik segmentasyon geliyor; seçilen güvenli
iniş alanının görüntüyü doldurma oranını (rho) ölçebiliyorum. Amaç, irtifa
ölçümüne dayanmadan alçalma hızını kontrol etmek.

Elimdeki ölçülmüş kısıtlar:
- rho, site kameranın ayak izinden büyük olduğunda 1'e doymakta ve yakınlık
  bilgisi taşımamakta (açık alanda rho = 0.87-0.91 sabit).
- Site kadraja sığdığında rho ~ 1/h^2, dolayısıyla rho'nun logaritmik türevi
  optik akış ıraksamasına eşit: rho_dot/rho = 2*vz/h.
- Tesis (PX4 hız denetleyicisi + gövde): kazanç K = 1.02, ölü zaman 0.28 s,
  geçici rejim jerk/ivme sınırlı (birinci mertebe DEĞİL).

Şunları istiyorum:
1. Bu kısıtlar altında uygulanabilir kontrolcü ailelerini karşılaştır:
   (a) rho setpoint PID, (b) sabit ıraksama/temas süresi (tau) kontrolü,
   (c) alan momentiyle IBVS, (d) denetimli melez.
   Her biri için: kontrol yasası denklemi, gerekli ölçümler, kararlılık
   davranışı, bilinen zayıflıkları.
2. Ölü zaman baskın ve jerk sınırlı bir tesiste tau kontrolünün kazanç
   seçimi nasıl yapılır? Literatürde uyarlamalı kazanç neden gerekiyor?
3. rho doyduğunda (site kadrajdan taşıyor) hangi denetim stratejileri
   öneriliyor? Anahtarlamalı kontrolde çarpmasız geçiş nasıl kurulur?
4. Her aile için en az 2 hakemli kaynak, künyeleriyle.

Çıktı: karşılaştırma tablosu + denklemler + kaynak listesi. Spekülasyon ile
kaynaklı bilgiyi açıkça ayır.
```

## D.2 Benzer çalışmalar taraması

```
Şu sistemin literatürdeki en yakın karşılıklarını bul: PX4 + Gazebo + ROS 2
üzerinde, aşağı bakan kameradan semantik segmentasyon ile acil durum iniş
alanı seçen ve oraya inen bir sistem. Ayırt edici özelliği: hareketli
engellerin (yaya, araç) GELECEK konumunu tahmin edip iniş alanı seçiminden
dışlaması.

Şunları ayrı ayrı ara:
1. Semantik segmentasyonla iniş alanı seçimi yapan sistemler — sınıfları risk
   skoruna eşleyenler.
2. Hareketli engel tahminini iniş kararına katan çalışmalar (varsa).
3. SORA/JARUS risk çerçevesini iniş alanı seçimine uygulayan çalışmalar.
4. Simülasyonda (Gazebo/AirSim/Isaac) doğrulanmış uçtan uca iniş sistemleri.

Her çalışma için: ne yaptığı, hangi metrikle ölçtüğü, benim sistemimden farkı,
künyesi. Benzerlik iddialarını abartma; gerçekten benzer olanları işaretle.
```

## D.3 Segmentasyon eğitimi ve veri kümesi

```
Gazebo'da çalışan bir İHA acil iniş sistemi için semantik segmentasyon modeli
eğiteceğim. Simülatörün etiket kamerası, RGB ile hizalı mükemmel etiket
üretebiliyor, yani sınırsız sentetik veri mümkün. Sistem SADECE simülasyonda
çalışacak, ama gerçek hava görüntüleriyle (TU Graz Semantic Drone Dataset,
MESSI) ön eğitim yapmayı düşünüyorum.

Sorular:
1. Sentetik veri + gerçek veri karışımı için literatürdeki en iyi uygulamalar
   neler? Sentetik veriyi ara alan olarak kullanma stratejisi nasıl kuruluyor?
2. Hangi alan rastgeleleştirme (domain randomization) eksenleri aerial
   segmentasyonda en çok fayda sağlıyor: doku, ışık, güneş açısı, irtifa?
3. Küçük nesne problemi: 20 m irtifada bir insan maskede 79-164 piksel.
   Hangi mimariler ve kayıp fonksiyonları bu rejimde insan sınıfını koruyor?
4. Güvenlik-kritik değerlendirme: mIoU yerine hangi metrikler? "Yanlış-güvenli"
   (suya/insana safe demek) oranını raporlayan çalışma var mı?
5. Gerçek zamanlı çıkarım: ROS 2 düğümü içinde model mi, ayrı çıkarım sunucusu
   mu, TensorRT/ONNX mü? Gecikme bütçesi 3 Hz harita için ne olmalı?

Çıktı: her soru için kaynaklı cevap + somut öneri. Künyeleri doğrulanabilir
biçimde ver.
```

## D.4 Kapsama-ıraksama köprüsünün doğrulanması

```
Şu matematiksel iddiayı doğrula ve literatürde karşılığı var mı bul:

Aşağı bakan bir kamerada, yarıçapı R olan düz bir hedef bölge, irtifa h'de
görüntünün rho = (R/(h*tan(FOV/2)))^2 kadarını doldurur (rho < 1 iken).
Buradan rho_dot/rho = -2*h_dot/h = 2*vz/h = 2*D, yani kapsama oranının
logaritmik türevi optik akış ıraksamasının iki katıdır.

Sorular:
1. Bu türetim doğru mu? Hangi varsayımlar altında (düz zemin, nadir bakış,
   perspektif izdüşüm) geçerli?
2. Kamera yatınca (nadir olmayan bakış) bu ilişki nasıl bozulur?
3. Literatürde "alan tabanlı ıraksama kestirimi" veya "segmentasyon tabanlı
   time-to-contact" çalışması var mı? Optik akış yerine bölge alanı kullanan?
4. Gürültü açısından karşılaştır: piksel-düzeyi optik akış mı, bölge alanının
   türevi mi daha kararlı?
```

---

# BÖLÜM E — Poster ve sunum için çerçeve

## Hat 1 — Segmentasyon ve veri

**Anlatı:** "Simülatörün etiket kamerası bir ölçüm değil, tanımdır. Sistemi
tahmin üzerinden çalıştırmak için model eğitildi; veri kümesi simülatörün
kendi mükemmel etiketlerinden üretildi."

**Şekil:** RGB | gerçek etiket | model tahmini üçlüsü, yan yana.

**Sayı:** sınıf başına yanlış-güvenli oranı (mIoU değil) + 20 m'de insan
sınıfının piksel bütçesi.

## Hat 2 — Görüntü-tabanlı iniş kontrolü

**Anlatı:** "İniş hızı irtifadan değil, kameradan gelsin. Seçilen alanın
görüntüyü doldurma oranının logaritmik türevi, optik akış ıraksamasının
segmentasyon-tabanlı tahmincisidir."

**Şekil:** İrtifa–hız eğrisi, üç kol: irtifa-tabanlı / kapsama-tabanlı /
τ-kontrol. Yanına doyum bölgesi taranmış.

**Sayı:** dokunma hızı, alçalma süresi, N koşuda başarı oranı.

**Dürüstlük notu (savunmada sorulur, hazır olsun):** kapsama oranı, site
kameranın ayak izinden büyük olduğunda doyar ve yakınlık bilgisi taşımaz;
ölçüldü, açık alanda bu yasa inişin %0'ında aktifti. Bu yüzden ya RGB
dokusundan ıraksama kestirilmeli ya da denetimli melez kurulmalı.

---

## Kaynaklar

Yukarıdaki bağlantıların toplandığı aramalar (2026-09-25):

- https://arxiv.org/pdf/1609.06767
- https://arxiv.org/pdf/1702.00061
- https://arc.aiaa.org/doi/abs/10.2514/6.2023-1150
- https://www.sciencedirect.com/science/article/abs/pii/S0921889019302404
- https://arxiv.org/pdf/2011.00534
- https://iopscience.iop.org/article/10.1088/1748-3190/11/1/016004
- https://arxiv.org/pdf/2512.04373
- https://ieeexplore.ieee.org/document/6224828/
- https://www.researchgate.net/publication/361242780
- https://pure.bit.edu.cn/en/publications/image-based-visual-servoing-control-of-uav-dynamic-landing-under-/
- https://journals.sagepub.com/doi/10.1177/09596518221144490
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10386455/
- https://ieeexplore.ieee.org/document/9867062/
- https://arxiv.org/abs/2111.14557
- https://arxiv.org/pdf/2506.14525
- https://www.sciencedirect.com/science/article/pii/S2405896323003105
- https://www.sciencedirect.com/science/article/abs/pii/S0952197626008420
- https://arxiv.org/abs/2505.08589
- https://github.com/messi-dataset/messi-dataset
- https://arxiv.org/pdf/2606.14767
- https://doi.org/10.3390/aerospace10070604
- https://www.researchgate.net/publication/335714815
- https://arxiv.org/pdf/1909.00889
