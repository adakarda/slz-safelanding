# Karar paketi 01 — 2026-10-08 (taslak)

> **Durum notları (önce bunlar):**
> - **Şablon yok.** `docs/kararlar/SABLON.md` depoda bulunmuyor. Her maddede
>   görev tanımındaki dört alan var: ne, neden, parametre ve varsayılan, sayıyla
>   kabul ölçütü. Yerleşim geçici; şablon eklenirse ona uydurulur.
> - **Yeni rapor yok.** `geri_bildirim/` altındaki son rapor Tur 4 SONUC ve
>   Tur 4 EK (2026-10-04). R-NNN adlı rapor yok. Bu paket yalnız
>   `KONTROLCU_OLCUMLERI.md` (2026-10-05) ve o iki rapordaki sayılara dayanıyor.
> - **Etiketler:** **ölçülen** (raporda koşuldu), **_hesap** (aşağıdaki
>   formülden, kontrol edildi), **hedef** (benim istediğim değer; sonuç değil).
> - **Bu pakette hiçbir varsayılan değişmiyor.**
> - **Segmentasyon ve araç hız tahmini:** hiçbir madde `eland_perception`'a ya
>   da `tracker_node`'a dokunmuyor. Her maddede ayrıca yazıldı.

| # | Madde | Tür | Kod değişir mi | Seg. / araç hızı |
|---|---|---|---|---|
| 1 | K2'ye uzun sabit ıraksama kolu (D* = 0.15) | veri toplama | yalnız K2 D*'ı parametre değilse | dokunmaz |
| 2 | İç döngü kazançları: önce ölçüm, sonra aday | ölçüm + uçuş karşılaştırması | hayır | dokunmaz |
| 3 | ρ̇/ρ = 2D'nin gürültülü veride çevrimdışı sınanması | çevrimdışı analiz | yalnız yeni betik | dokunmaz (gerçek modele bağımlı, aşağıda) |
| 4 | W5: hedefe göre yükseklik kestirimi ön analizi | çevrimdışı analiz | yalnız yeni betik | dokunmaz (`area_m2`'yi okur) |

---

## 1. K2'ye uzun sabit ıraksama kolu

**Ne.** Devir irtifası 2.5 m'de kalır. K2'ye D* = 0.15 1/s kolu eklenir.

**Neden.**
- K2'de sabit ıraksama pencereleri kısa. **Ölçülen** (OLCUMLERI §2.6,
  `VERI_TOPLAMA.md` "Adım 3"): D* = 0.2 / 0.35 / 0.5 için 5.6 / 1.6 / 0.4 s.
- **_hesap:** pencere `T = ln(h_giriş / h_devir) / D*`, `h_giriş = 1.5 / D*`
  (hız 1.5 m/s tavanından çıktığı irtifa). h_devir = 2.5 m ile:

  | D* | h_giriş | T (_hesap) | T (ölçülen) |
  |---|---|---|---|
  | 0.5 | 3.00 m | 0.36 s | 0.4 s |
  | 0.35 | 4.29 m | 1.54 s | 1.6 s |
  | 0.2 | 7.50 m | 5.49 s | 5.6 s |
  | **0.15** | **10.00 m** | **9.24 s** | yok |

  Formül üç ölçüme tutuyor.
- **Devir irtifasını düşürmek çözüm değil.** D* = 0.35'te 3 s için h_devir =
  1.5 m gerekir (_hesap). COMMIT EKF'de 2.0 m'de başlıyor ve girişteki gerçek
  yükseklik 1.98-2.20 m (ölçülen, Tur 4 SONUC §3). Politika COMMIT'e girer.
- D* = 0.2 kolu zaten var (8 bölüm, 5.6 s). Daha uzun pencere için D*
  küçülmeli.

**Parametre ve varsayılan.**
- D* = 0.15 1/s. Başka D* yok; 0.1 için h_giriş = 15 m gerekir ve K2'nin
  VALIDATE başlangıç irtifası bu dokümanlarda yazmıyor (`MIS_TAKEOFF_ALT` =
  18 m).
- 8 bölüm. Dünya ve tohum düzeni K2'nin mevcut kolununkiyle aynı.
- Devir irtifası 2.5 m, PX4 parametreleri, COMMIT: değişmez.
- Her satır `RUN_SIM_MOD_TEKRAR=2` ile başlar (AGENTS §3.9).
- K2 D*'ı parametre olarak alıyorsa kod yok. Almıyorsa Claude Code önce plan
  yazar ve onay bekler (AGENTS §3.1).
- Raporda her bölümün VALIDATE başlangıç irtifası verilir.

**Kabul ölçütü (hedef).**
- 8/8 bölümde `basarili_v10`.
- Sabit ıraksama penceresi: ortanca ≥ 8.0 s, en kısa ≥ 7.0 s. Pencere
  tanımı Adım 3'teki gibi (yasa kırpılmadan, 2.5 m'de devre kadar).
- Gerçekleşen D − D* RMS ≤ 0.010 1/s. Mevcut en kötüsü 0.013 (D* = 0.5), en
  iyisi 0.004 (D* = 0.35).
- Temas hızının ortancası ve en büyüğü raporlanır (AGENTS §3.9).

**İşaret:** segmentasyona dokunmaz, araç hız tahminine dokunmaz.

---

## 2. İç döngü kazançları: önce ölçüm, sonra aday

**Ne.** Üç adım. Birincisi bu pakette istenir, ikincisi bende, üçüncüsü aday
gelince.
1. Claude Code döngü hızını ve EKF vz gecikmesini ölçüp raporlar (kod
   değişmez).
2. Ben yeni θ ile Simulink'te aday (Kp, Ki) türetirim ve ayrı bir mesajla
   veririm.
3. Aday uçuşta, mevcut PI ile eşli karşılaştırılır. Kabul ölçütü aşağıda,
   adaydan önce sabitlendi.

**Neden.**
- IMC türetimi eski θ = 0.28 s ile yapıldı; yeni θ = 0.04-0.08 s (ölçülen,
  OLCUMLERI §1.2, §2.4).
- **_hesap:** `Ki = 1 / (K·(λ + θ))`, λ = 1.5·θ, K = 1.0 ile θ = 0.04 / 0.06 /
  0.08 s için Ki = 10.0 / 6.7 / 5.0 1/s. Eski türetim 1.39 vermişti. Mevcut
  elle ayarlı Ki = 0.6.
- **Bu sayıyı doğrudan almıyorum:**
  - Küçük basamakta τ ≈ 0.1 s (ölçülen). θ ile aynı mertebede. Eski türetimdeki
    `Kp → 0` sonucu θ ≫ τ iken doğruydu; şimdi sınanmadı.
  - Büyük basamakta ivme sınırlı (6-8.5 m/s²), birinci mertebe model uymuyor.
  - Döngü hızı belirsiz: kod yorumu EKF vz için 30 Hz diyor
    (`emergency_landing_mode.hpp`, `DescentRateController`), kaydedici 48-50 Hz
    ölçtü. **Ölçülmedi**, hangisi doğru bilinmiyor.
- Mevcut PI (0.8, 0.6) ve IMC (0, 1.39) uçuşta ölçüm gürültüsü içinde aynı:
  RMS 0.201 / 0.197 (ölçülen, `v3.0`). Ayar yapmanın kazancı küçük olabilir;
  ölçmeden değiştirmek gereksiz risk.

**Parametre ve varsayılan.**
- `descent_kp = 0.8`, `descent_ki = 0.6`, `descent_kaw = 1.0`: **değişmez**.
- Adım 1 çıktısı: `DescentRateController::update`'in gerçek çağrı hızı (dt
  dağılımı: ortanca, p95) ve `vz_ekf`'in `vz_gercek_hesap`'a göre gecikmesi
  (çapraz korelasyon, 20 ms ızgara). Yeni betik ya da mevcut kayıtlar; kod
  değişmez.
- Adım 3'te aday değerler `tools/make_params.py` ile koşu başına verilir.
  Yaml'a yazılmaz.

**Kabul ölçütü (Adım 3, hedef).** Üç kol × en az 3 uçuş, `v3.0` düzeninde,
mevcut PI kolu aynı turda yeniden uçurulur (AGENTS §3.5, eski sayıya
güvenilmez).
- Aday: ortanca RMS takip hatası ≤ aynı turdaki mevcut PI'ın ortancası.
- En kötü uçuş RMS ≤ aynı turdaki mevcut PI'ın en kötüsünün 1.05 katı.
- 10 m üstünde ortalama hata |·| ≤ 0.09 m/s (mevcut PI: −0.09, ölçülen).
- Temas: n/n `basarili_v10`; ortanca ve en büyük raporlanır.
- Aşım ve v_cmd − v_ref tepe değeri bu turda **taban olarak ölçülür**; kabul
  ölçütü olarak henüz sayı vermiyorum, çünkü karşılaştıracak ölçüm yok.

**İşaret:** segmentasyona dokunmaz, araç hız tahminine dokunmaz.

---

## 3. ρ̇/ρ = 2D'nin gürültülü veride çevrimdışı sınanması

**Ne.** Yeni çevrimdışı betik (örnek ad `tools/veri/d_kestirim.py`; mevcut
dosyalara dokunmaz). Maske tablosundaki ρ'dan ıraksama kestirilir ve gerçek
ıraksamayla karşılaştırılır.

**Neden.**
- Statik ilişki ρ = A / (4.22·h²) eğiklik < 5°'de doğrulandı, RMS 0.0014-0.0019
  (ölçülen, OLCUMLERI §4.4). **Türev ilişkisi ölçülmedi** (aynı yer, §9).
- Kapalı çevrimde ölçülecek büyüklük D. D'nin kalitesi bilinmeden görüntü
  tabanlı yasa tasarımı varsayıma dayanır.
- **_hesap:** `D̂ = ½ · d(ln ρ)/dt` (ρ̇/ρ = 2D). Türev almak gürültüyü büyütür;
  pencere uzadıkça gürültü azalır ama gecikme artar. N bu yüzden taranıyor.

**Parametre ve varsayılan.**
- Kestirici: son N maskede ln ρ'ya en küçük kareler doğrusu. N ∈ {3, 5, 8} kare
  (10 Hz'de 0.2 / 0.4 / 0.7 s) taranır. **Varsayılan aday N = 5.**
- Karşılaştırma: `D_gerçek = vz_gercek_hesap / h`, h = maske tablosundaki
  kamera yüksekliği (Gazebo).
- Satırlar: yalnız `view_bounded = 1` (gürültülü maskede
  `view_bounded_bozuk = 1`). Eğiklik < 5° ve ≥ 5° ayrı raporlanır.
- Veri: temiz için K1, K2, K3 VALIDATE kareleri. Gürültülü için Aşama 5 (20
  bölüm; sınır 2 px, çevir 0.02, kayıp 0.05, gecikme 0.2 s, tekrar 2;
  `rho_bozuk`).
- Çıktı: kol × N × eğiklik için kare sayısı, ortalama, ortanca, RMS, p95;
  D̂'nin D'ye en iyi çapraz korelasyon kayması [s].

**Kabul ölçütü (hedef; gereksinim varsayımı, Simulink sonrası revize
edilebilir).**
- Temiz maske, eğiklik < 5°: |D̂ − D| RMS ≤ 0.05 1/s. Gerekçe: D* = 0.2-0.5
  aralığında bu %10-25.
- Gürültülü maske (beş bozucunun hepsi, eğiklik < 5°): RMS ≤ 0.10 1/s.
- Gecikme (çapraz korelasyon kayması) ≤ 0.4 s. Bütçe: örnekleme + maske
  gecikmesi + süzgeç, ~0.25 s mertebesi (_tahmin, OLCUMLERI §3.5).
- Hiçbir kol için "geçti / kaldı" yazılmadan önce kare sayısı verilir; n < 100
  olan hücre sonuç sayılmaz.

**İşaret:** segmentasyona **dokunmaz** (`/eland/rho`'nun kayıtlı çıktısını
okur). Ama **sonuç yalnız Gazebo etiketi ve beş yapay bozucu için geçerli**;
gerçek segmentasyon modeli ölçülmedi (ertelendi). Gerçek modelle geçerli diye
yazılmayacak.

---

## 4. W5: hedefe göre yükseklik kestirimi ön analizi

**Ne.** Yeni çevrimdışı betik. W5 bölümlerinde hedef yüzeye göre yükseklik,
ρ ve aday alanından kestirilir; EKF sapmasının ilk (kadraja sığan) bölümde
öğrenilip sonra tutulması fikri çevrimdışı sınanır.

**Neden.**
- W5'te COMMIT'e girilmiyor, temas 1.47-1.49 m/s, EKF hedefin 3.8-4.0 m
  üstünde (ölçülen, Tur 4 SONUC §2 ve OLCUMLERI §5.4). EKF orijini kalkış
  noktasında; sapma platformun yüksekliği.
- **_hesap:** `ĥ_hedef = √(A / (4.22·ρ))`. 10×10 m bölge kadraja yalnız
  h_hedef > 5.6 m'de sığar (OLCUMLERI §4.1); platform 4 m ise bu h_zemin > 9.6
  m demek. Son 5.6 m'de ρ bilgi taşımaz.
- **Bu yüzden önerilen yapı:** `b̂ = h_ekf − ĥ_hedef` sığma penceresinde
  kestirilir ve pencere bitince sabit tutulur; sonra `ĥ_hedef = h_ekf − b̂`.
  Bu bir **_tahmin**: platform yüksekliği iniş boyunca sabit olmalı.
- ρ hatasının etkisi küçük: ρ = 0.3, A = 100 m² için h ≈ 8.9 m ve ρ hatası
  0.002 ile ĥ hatası ≈ 0.03 m (_hesap).
- **Ölçülmedi:** `area_m2`'nin (`/eland/candidate`, ~1.8 Hz, haritadan) gerçek
  alana ne kadar yakın olduğu. Tüm analizin ön koşulu bu.

**Parametre ve varsayılan.**
- Veri: kayıtlı tüm W5 bölümleri (Kol 0 ×3 ve K1-K3'te olanlar). Bölüm sayısı
  `ep` tablosundan raporlanır.
- Yalnız `view_bounded = 1` satırlar.
- Önce `area_m2` ile dünya yaml'ındaki gerçek A karşılaştırılır; sonra ĥ ve b̂.
- Kod yok, parametre yok, varsayılan yok.

**Kabul ölçütü (hedef).** EKF yükseklik RMS'i 0.13-0.14 m (ölçülen); hedef
bunun yaklaşık iki katı.
- `area_m2` / A_gerçek: ortanca 0.9-1.1 aralığında. Dışarıdaysa analiz durur,
  rapor bunu yazar.
- ĥ_hedef − h_gercek_hedef: ortanca |·| ≤ 0.3 m, p95 ≤ 0.6 m.
- b̂ pencere içi standart sapma ≤ 0.2 m.
- Temasa 0.1 s kala |(h_ekf − b̂) − h_gercek_hedef| ≤ 0.3 m.
- Her sayının yanında kare ve bölüm sayısı.

**İşaret:** segmentasyona ve araç hız tahminine **dokunmaz**; harita çıktısı
`area_m2`'yi yalnız okur. **Ayrı işaret (⚑):** `area_m2` tutmazsa çözüm
haritanın alan hesabına dokunur; o madde bu pakette yok ve ayrıca onay ister.

---

## Bu pakette olmayanlar

| Konu | Neden yok |
|---|---|
| Modun `/eland/rho`'yu kullanması | Tasarım depoda yok; Simulink doğrulaması bekliyor (DURUM §5). Madde 3'ün sonucu girdi olacak. |
| Gerçek segmentasyon modeli | Ertelendi; dokunulmuyor ⚑. |
| PX4 parametreleri | Dokunulmaz (AGENTS §3.6). |
| `commit_irtifa_yasasi` ve W6 t1 (0.496 m/s) | Tur 4'te raporlandı; aykırı değer kestirici hatası, ayardan değil. Yeni madde gerekmedi. |
| Gerçek komut kaybında `RUN_SIM_MOD_TEKRAR` | Ölçülmedi (Tur 4 EK §2). Maddelerde açık; koşulurken biriken sayılar raporlanır. |

## Uygulama sırası

1. Madde 3 ve 4 (kod yok) ve Madde 2 / Adım 1 (ölçüm): onaysız başlayabilir
   (AGENTS §3.1 istisnası: yeni dosya, çevrimdışı).
2. Madde 1: K2 D*'ı parametre alıyorsa uçuş, almıyorsa önce plan.
3. Madde 2 / Adım 3: aday gelince.

Rapor biçimi: her tabloda kare/bölüm sayısı, temas hızı ortanca ve en büyük,
"ölçülmedi" olanlar ayrı satırda.
