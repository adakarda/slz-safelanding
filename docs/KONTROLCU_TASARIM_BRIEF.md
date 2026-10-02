# Görüntü-Tabanlı Dikey İniş Kontrolcüsü — Tasarım Brifi

Tarih: 2026-10-02 · Kod: `github.com/adakarda/slz-safelanding`, `main` @ `v4.3-koridor-olcum`

**Bu dosya ne için:** Projede dikey iniş için **görüntü-tabanlı** bir kontrolcü
tasarlayacağım. Tasarımı bir sohbet asistanıyla (chatbot) birlikte yapacağım.
Bu dosya o asistana projeyi, mevcut durumu, ölçülmüş gerçekleri ve kısıtları
tek seferde anlatmak için yazıldı. Dosyanın tamamını sohbete yapıştırıp en
alttaki açılış mesajıyla başlamak yeterli.

Buradaki sayılar simülasyonda **ölçülmüştür**. Geometriden hesaplananlar
(§6) ve tahminler ayrıca işaretli.

---

## 1. Proje, tek paragraf

Lisans bitirme tezi. PX4 v1.17 SITL + Gazebo Harmonic + ROS 2 Jazzy üzerinde
bir **acil iniş sistemi**: bağlantı kopunca devreye giren, PX4'ün Return
modunun yerine kayıtlı resmi bir uçuş modu (`px4_ros2::ModeBase`, offboard
değil). Araç (x500 quadrotor, 2.0 kg) aşağı bakan tek bir **segmentasyon
kamerası** taşır. Sınıf maskesi yere izdüşürülüp bir haritada birleştirilir,
bu haritadan güvenli bir iniş noktası seçilir, araç o noktanın üstüne gider
ve dikey olarak iner. Hareketli insan ve araçların gideceği yer tahmin edilip
iniş noktası seçiminde dışlanır.

Tezin iki ana hattından biri bu dosyanın konusu: **seçilen zemine, görüntüden
ölçülen büyüklüklerle kontrollü dikey iniş.**

---

## 2. Görüntüden motora zincir

```
Gazebo segmentasyon kamerası   320×240, yatay FOV 99.7°, 10 Hz, gövdeye sabit (gimbal yok)
        │  ~8 ms
perception_node                sınıf maskesi: mono8, piksel = sınıf no (0..7), ~9.7 Hz
        │  ~16-20 ms (yakalamadan itibaren)
mapping_node                   yere izdüşüm + zamanda füzyon: 40×40 m harita, 0.2 m hücre
        │  ~24 ms (yakalamadan itibaren)
detector_node                  iniş noktası seçimi (2 Hz ile sınırlı, fiilen ~1.8 Hz)
        │                      + maskeden kapsama oranı ρ (her maskede, 10 Hz hesaplanır)
        ▼
emergency_landing_mode (C++)   durum makinesi + alçalma yasası + dikey hız kontrolcüsü
        │  dikey hız komutu (m/s) + yatay konum hedefi
        ▼
PX4                            hız → ivme → tutum → açısal hız döngüleri (dokunulmuyor)
```

Sınıflar: 0 yumuşak güvenli zemin (çim), 1 sert güvenli zemin (asfalt),
2 arazi tehlikesi, 3 yapı, 4 su, 5 araç/hayvan, 6 insan, 7 bilinmeyen.
İnilebilir sınıflar: 0 ve 1.

**Önemli:** maske şu an Gazebo'nun **kusursuz etiketleri**. Sonradan eğitilmiş
bir segmentasyon modeli takılacak; o zaman maske gürültülü olacak. Kontrolcü
kusursuz maskeye güvenmemeli.

---

## 3. İniş senaryosu (durum makinesi)

| Durum | Ne yapar | Dikey eksen |
|---|---|---|
| SEARCH | 15 m'de bekler, aday arar | irtifa tutma |
| APPROACH | adayın üstüne yatay gider (≤ 3 m/s), irtifa sabit | irtifa tutma |
| **VALIDATE** | adayın üstünde alçalır, aday her an yeniden doğrulanır | **kontrolcünün çalıştığı faz** |
| HOLD | 5 m altında aday 3 s kaybolursa yerinde bekler (5 s) | sabit |
| ABORT | arama irtifasına geri tırmanır | tırmanma |
| COMMIT | 2 m'de başlar, geri dönüşsüz; iniş algılanana kadar aşağı iter | açık çevrim hız komutu |

VALIDATE yaklaşık 15-20 m'den 2 m'ye kadar sürer. Yatayda araç seçilen noktanın
konumunu PX4'ün konum kontrolüyle tutar; **yatay eksen bu tasarımın dışında.**

---

## 4. Dikey eksende bugün ne var

Üç katman:

```
alçalma yasası ──v_ref──▶ PI + ileri besleme ──v_cmd──▶ PX4 iç döngüleri ──▶ araç
                                  ▲
                          ölçülen dikey hız (EKF)
```

**(a) Alçalma yasası — referansı üretir.** Birimler m/s, aşağı pozitif.

```
v_tavan = clamp(0.20·√A, 0.3, 1.5)            A: seçilen bölgenin alanı [m²], haritadan

site kadraja tam sığıyorsa (view_bounded):
    v_ref = clamp(v_tavan·(1 − ρ), 0.3, v_tavan)      ρ: kapsama oranı, görüntüden
sığmıyorsa (yedek):
    v_ref = clamp(0.35·h, 0.3, v_tavan)               h: irtifa [m], EKF'den
```

**(b) Dikey hız kontrolcüsü — referansı izler.**

```
e     = v_ref − v_ölçülen
u     = v_ref + Kp·e + I                  Kp = 0.8, Ki = 0.6, Kd = 0
I    += (Ki·e + Kaw·(u_sat − u))·dt       Kaw = 1.0 (geri hesaplamalı anti-windup)
v_cmd = u_sat = clamp(u, 0, 1.5)
```

VALIDATE'e her girişte integral sıfırlanır (çarpmasız geçiş). Bu döngü RMS
takip hatasını 0.32'den 0.20 m/s'ye indirdi ve çalışıyor.

**(c) COMMIT (son 2 m).** PI devrede değil; yasanın çıktısı doğrudan dikey hız
komutu olarak verilir (açık alanda 0.7 → 0.3 m/s) ve PX4 iniş algılayana kadar
sürer.
COMMIT'te yeni aday mesajı kabul edilmez; ρ ve alan son değerde kalır.

**Gözden kaçmaması gereken bir şey:** irtifa yedeği `v = 0.35·h`, aslında
`v/h = 0.35 1/s` yani **sabit ıraksama** (constant divergence) yasasıdır;
yalnızca `h`'yi görüntüden değil EKF'den alır ve 4.3 m'nin üstünde 1.5 m/s'de
doyar.

---

## 5. Asıl problem: görüntü-tabanlı dal pratikte çalışmıyor

Tasarımda "kapsama arttıkça yavaşla" var, ama ölçüm şunu gösterdi:

**Ölçüm 1 — açık alanda ρ dalı inişin %0'ında aktif.**

| İrtifa | ρ | ρ dalı aktif | Komut edilen hız |
|---|---|---|---|
| 10+ m | 0.87 | %0 | 1.50 m/s |
| 5-10 m | 0.91 | %0 | 1.50 |
| 2-5 m | 0.91 | %0 | 1.09 |
| 0-2 m | 0.69 | %0 | 0.40 |

Sebep: güvenli bölge kadrajdan taşıyor. Taşan bir bölgenin ρ değeri yalnızca
bir alt sınırdır; "yere çok yakınım" ile "alan çok büyük" aynı görünür. ρ
0.87-0.91'de **doyuyor** ve alçaldıkça değişmiyor. Yani şu an yavaşlama
kameradan değil irtifadan geliyor.

Tarihsel not: yalnız ρ kullanan ilk sürümde açık çimende iniş 0.3 m/s ile
73 s sürüyordu (normali ~21-27 s), çünkü ρ 0.81'de takılıydı.

**Ölçüm 2 — etiket maskesinde yere yakınken yapı kalmıyor.**

| İrtifa | Maskedeki sınıf sınırı pikseli |
|---|---|
| 15+ m | 1561 |
| 10-15 m | 1086 |
| 5-10 m | 61 |
| 5 m altı | **0** |

İyi bir iniş alanı homojendir; homojen alanın etiket görüntüsü de tek renktir.
Açık alanda son 5 metrede maskeden yakınlık bilgisi çıkmaz.

**Ölçüm 3 — RGB optik akış denemesi yarım.** `rgb-akis-denemesi` dalında
160×120 RGB kamera eklendi, Farneback akışından ıraksama kestirildi; ilk
sonuç yetersiz (gerçek `v/h` ile korelasyon −0.24). Muhtemel sebep taban
süresinin kısalığı (0.1 s'de genleşme %0.75). Dal parkta.

---

## 6. Kamera geometrisi ve ρ'nun irtifayla ilişkisi

Yatay FOV 99.7°, görüntü 4:3. `h` irtifasında yerdeki ayak izi:

```
genişlik = 2.37·h      yükseklik = 1.78·h      alan = 4.22·h²
```

Bölge kadraja tam sığdığı sürece (alanı `A`):

```
ρ = A / (4.22·h²)              →  ρ ∝ 1/h²
ρ̇/ρ = 2·v/h = 2·D              D = v/h: ıraksama [1/s],  temas süresi τ = 1/D = 2ρ/ρ̇
```

Yani **kapsamanın logaritmik türevi doğrudan ıraksamadır**; irtifa bilgisi
gerekmez. Bu ilişki henüz simülasyonda doğrulanmadı (yapılacaklar listesinde).

Bölge ne zamana kadar kadraja sığar (aracın tam altında, kare bölge; yukarıdaki
geometriden **hesaplandı**, ölçülmedi):

| Bölge | Sığdığı irtifa | O irtifada ρ |
|---|---|---|
| 4×4 m | 2.25 m üstü | 15 m'de 0.02, 5 m'de 0.15, 3 m'de 0.42 |
| 10×10 m | 5.6 m üstü | 15 m'de 0.11, 10 m'de 0.24, 6 m'de 0.66 |
| 20×20 m | 11.2 m üstü | 15 m'de 0.42 |
| Açık alan (~1270 m²) | ~20 m üstü | iniş boyunca hiç sığmaz |

Sığma bittiği anda ρ kare bölgede ~0.75, daire bölgede ~0.59'dur; ρ'nun
"bilgi taşıyan" aralığı 0 ile bu değer arasıdır. Seçilebilen en küçük bölge
9 m², pratikte ≥ 4 m genişlik. **Dar sitelerde sinyal VALIDATE'in neredeyse
sonuna kadar geçerli, geniş alanlarda hiç geçerli değil.**

Kamera gövdeye sabit: araç yatınca ayak izi kayar ve bozulur (20-30° yatışta
görüntünün üçte biri haritalanamaz hâle gelir). Dikey inişte yatış küçüktür,
ama rüzgârda büyür.

---

## 7. Kontrol edilen sistem (tesis) modeli

Tesis yalnız hava aracı değil: PX4'ün hız denetleyicisi + araç + ROS-PX4
köprüsü. Dikey hız komutuna kare dalga verilerek ölçüldü:

- Kazanç **K ≈ 1.01-1.03** (istenen hız veriliyor).
- Ölü zaman **θ ≈ 0.28 s**.
- Geçici rejim **jerk/ivme sınırlı**; birinci mertebe model uymuyor (ölçülen
  eğim 1.88 m/s'lik basamakta 4.94 m/s², 0.55 m/s'lik basamakta 1.67 m/s²).
- Hız üst sınırı **1.5 m/s** (PX4 `MPC_Z_V_AUTO_DN`). Yasa tavanını bunun
  üstüne çıkarmak işe yaramadı.
- PX4'e hız **sınırı** vermek referans vermek değildir; hız komutu
  (`TrajectorySetpoint.withVelocityZ`) verilmelidir. Sınır verildiğinde bir
  uçuş inmeyi bırakıp asılı kaldı.

Ölü zaman baskın IMC ile türetilen iç döngü kazancı `Kp = 0, Ki = 1.39`;
uçuşta elle ayarlananla (`Kp = 0.8, Ki = 0.6`) eşdeğer çıktı (RMS 0.197 ve
0.201 m/s).

---

## 8. Kontrolcünün kullanabileceği sinyaller

| Sinyal | Kaynak | Hız | Not |
|---|---|---|---|
| Sınıf maskesi | `/eland/semantic_mask` | ~9.7 Hz | yakalamadan 16-20 ms sonra (p90 45-64 ms) |
| ρ, kapsama oranı | maskede görüntü merkezinin altındaki bağlı güvenli bölgenin piksel payı | 10 Hz hesaplanıyor, **moda ~1.8 Hz ulaşıyor** | aşağıya bak |
| `view_bounded` | o bölge görüntü kenarına değmiyor mu | ρ ile aynı | ρ'nun geçerlilik bayrağı |
| `area_m2` | haritadaki bağlı bölgenin alanı | ~1.8 Hz | harita 40×40 m ile sınırlı |
| `radius` | seçilen noktaya sığan en büyük dairenin yarıçapı [m] | ~1.8 Hz | haritadan |
| Dikey hız `vz` | PX4 EKF | ~48 Hz | iç döngü bunu kullanıyor |
| İrtifa `h` | PX4 EKF (yerel konum) | ~48 Hz | dünya düz; gerçekte eğimli zeminde yanlış olur |
| Tutum (yatış) | PX4 | ~48 Hz | ayak izi düzeltmesi için kullanılabilir |

**ρ'nun hızı bir darboğaz.** ρ her maskede hesaplanıyor ama moda iniş adayı
mesajının içinde, karar hızında (~1.8 Hz) gidiyor. Görüntü-tabanlı bir döngü
için ρ'yu ayrı bir konudan 10 Hz'de yayınlamak küçük bir değişiklik; tasarım
bunu varsayabilir.

Döngüdeki toplam gecikme (tahmin): tesis 0.28 s + örnekleme beklemesi
(10 Hz'de ortalama 0.05 s) + işleme 0.02 s ≈ **0.35 s**; ρ türevi için
süzgeç eklenirse daha fazla.

Henüz kullanılmayan ama maskeden üretilebilecek özellikler: `ρ̇/ρ`,
görüntü merkezinden en yakın güvenli-olmayan piksele uzaklık (piksel
cinsinden iç daire yarıçapı, bölge kadrajdayken `1/h` ile büyür), bölge
sınırının uzunluğu. Hepsinin ortak zaafı Ölçüm 2: açık alanda yere yakınken
kadrajda sınır kalmaz. RGB dokusu bu boşluğu doldurabilecek tek kaynak.

Derinlik sensörü, lidar ya da stereo **yok**; eklenmesi planlanmıyor.

---

## 9. Tasarım kısıtları

1. **Çıktı tek bir skaler:** dikey hız, aşağı pozitif, **[0, 1.5] m/s**.
   VALIDATE'te tırmanma komutu yok.
2. **Önerilen yer:** yeni kontrolcü §4'teki alçalma yasasının yerine geçip
   `v_ref` üretir; mevcut PI iç döngü onu izlemeye devam eder. Başka bir yapı
   da önerilebilir, ama gerekçesiyle.
3. **Mevcut yasa silinmeyecek.** Yeni kontrolcü bir parametreyle seçilen ayrı
   bir kip olacak; aynı senaryoda yan yana karşılaştırılacak.
4. **Yedek zorunlu.** Görüntü sinyali geçersizken (bölge kadrajdan taşıyor,
   bölge kayboldu, maske bayat) irtifa yasasına **sıçramasız** geçilmeli.
5. **Asla asılı kalmamalı.** Hızın alt tabanı var (bugün 0.3 m/s); acil iniş
   modunda havada beklemek iniş değildir.
6. **Yere değme hızı** küçük kalmalı (bugün komut 0.3-0.4 m/s).
7. **Aday kaybı kuralları değişmiyor:** aday 3 s görünmezse 5 m üstünde
   aramaya dönülür, 5 m altında HOLD.
8. **Yatay eksene ve PX4 iç döngülerine dokunulmuyor.**
9. **Hesap yükü küçük olmalı:** maske başına birkaç ms (bugün karar karesi ~5 ms).

---

## 10. Açık tasarım soruları (asistanla konuşulacaklar)

1. **Hangi görüntü büyüklüğü kontrol edilecek?** ρ'nun kendisi mi (hedef ρ*),
   ıraksama mı (`ρ̇/ρ`, hedef D*), yoksa ikisinin birleşimi mi?
2. **Referans ne olacak?** Sabit ρ*, sabit D*, ya da irtifaya/alana göre profil.
3. **Doyum nasıl ele alınacak?** Bölge kadrajdan taşınca hangi koşulla,
   hangi histerezisle yedeğe geçilecek; geri dönüş olacak mı?
4. **ρ̇ nasıl kestirilecek?** 10 Hz'lik, kenar gürültülü bir sinyalin türevi;
   süzgeç ve onun getirdiği gecikme.
5. **Kazanç çizelgeleme gerekli mi?** Iraksama kontrolünde hızdan ıraksamaya
   kazanç `1/h` ile büyür; sabit kazançla alçaldıkça salınım literatürde
   bilinen bir sorun.
6. **Son 2 metre (COMMIT):** görüntü-tabanlı yasa burada da çalışacak mı,
   yoksa 2 m'de bırakıp mevcut açık çevrim inişe mi devredecek?
7. **Kararlılık gösterimi:** 0.35 s ölü zamanla hangi kazanç aralığı
   kararlı; faz payı ne?
8. **Gürültülü maskeye dayanıklılık:** gerçek model takılınca ρ titreyecek.
9. **Gösterim sahnesi:** kontrolcünün gerçekten çalıştığı, sınırlı bir site
   (ör. 6×6 m ya da 10×10 m izole yama) gerekiyor; açık alanda %0 aktif.

---

## 11. Nasıl değerlendirilecek

Düzenek hazır: `tools/batch_run.sh N` aynı tohumlarla N rastgele dünyada
uçurur ve her uçuş için metrik yazar. Kol başına **en az 3 uçuş** (tek koşu
bu projede işareti bile yanlış verdi).

| Metrik | Mevcut sistem (5 dünya, ortanca) |
|---|---|
| İniş başarısı | 5/5 |
| Alçalma süresi | 21.1 s |
| Dikey hız takip hatası (RMS) | 0.19-0.20 m/s |
| Dokunmanın seçilen noktadan sapması | 0.03-0.06 m |
| ABORT / 3 s üstü aday boşluğu | 0 / 0 |

Yeni kontrolcü için eklenecek ölçümler: ρ dalının aktif olduğu süre yüzdesi,
ölçülen ile gerçek `v/h` uyumu, yere değme dikey hızı.

Karşılaştırma kolları: (0) mevcut irtifa yasası, (1) yeni görüntü-tabanlı
kontrolcü; her ikisi hem sınırlı sitede hem açık alanda.

---

## 12. Tasarım bitince uygulamaya getirilecek çıktı

Tasarımı ben yapıyorum, koda dökme işini Claude Code yapacak. Tasarım şu
biçimde teslim edilirse doğrudan uygulanabilir:

1. **Girdiler:** hangi sinyaller, hangi hızda.
2. **Denklemler:** ayrık zamanda, örnekleme süresiyle; birimler açık.
3. **Parametreler:** ad, değer, birim, nasıl seçildiği.
4. **Kip geçişleri:** hangi koşulda görüntü yasası, hangi koşulda yedek;
   sözde kod olarak.
5. **Başlangıç ve sıfırlama:** integral, süzgeç durumları, geçişte ne olacağı.
6. **Doyum ve anti-windup.**
7. **Beklenen davranış:** sınırlı sitede ve açık alanda hız-irtifa eğrisinin
   nasıl görünmesi gerektiği (kabul ölçütü).

---

## 13. Sözlük

- **ρ (kapsama oranı):** görüntüde, aracın tam altındaki bağlı güvenli
  bölgenin kapladığı piksel payı, 0..1.
- **view_bounded:** o bölgenin görüntü kenarına değmemesi; ρ ancak o zaman
  yakınlık bilgisi taşır.
- **Iraksama D:** `v/h` [1/s]; sabit tutulursa irtifa ve hız üstel azalır.
- **τ (temas süresi):** `h/v = 1/D` [s].
- **VALIDATE / COMMIT:** alçalma fazı / 2 m altındaki geri dönüşsüz iniş fazı.
- **Tesis:** kontrol edilen sistem (PX4 hız döngüsü + araç).
- **Yedek:** görüntü sinyali geçersizken kullanılan irtifa yasası.

İlgili dosyalar: `src/eland_mode/include/emergency_landing_mode.hpp`
(`descentSpeed`, `DescentRateController`),
`src/eland_mapping/eland_mapping/detector_node.py` (`on_mask`: ρ),
`docs/TEZ_NOTLARI.md` §2 (kontrol ölçümleri),
`docs/ARASTIRMA_KONTROL_SEGMENTASYON.md` (literatür haritası; künyeler
doğrulanmalı).

---

## 14. Asistan için açılış mesajı (kopyala-yapıştır)

> Yukarıdaki brif, lisans bitirme tezimdeki acil iniş projesinin dikey iniş
> kısmını anlatıyor. Senden bir **görüntü-tabanlı dikey iniş kontrolcüsü**
> tasarlamamda bana yardım etmeni istiyorum.
>
> Kurallar:
> - Brifteki ölçümleri veri olarak al; onlarla çelişen bir varsayım yapacaksan
>   önce söyle.
> - §9'daki kısıtların dışına çıkma. Derinlik sensörü ya da lidar önerme.
> - Emin olmadığın yerde "emin değilim" de; kaynak uydurma. Bir makaleye
>   atıf yapacaksan yazar, yıl ve başlığı ver ki doğrulayabileyim.
> - Adım adım ilerleyelim: önce §10'daki sorulardan 1-3'ü tartışalım ve bir
>   yapı seçelim, sonra denklemleri ve kazançları çıkaralım, en son §12'deki
>   biçimde teslim edilecek tasarım özetini yazalım.
> - Türetimleri göster; lisans öğrencisiyim ve bunu tezde savunabilmem
>   gerekiyor.
>
> İlk olarak: bu sistemde kapsama oranını (ρ) mı, ıraksamayı (`ρ̇/ρ`) mı
> kontrol etmek daha mantıklı? İkisinin artılarını, eksilerini ve §5'teki
> doyum sorununa nasıl dayandıklarını karşılaştır.
