# Ön kayıt: AirSim Faz 7, havada rastgele başlangıç — klasik zincir ile RL (AirSimNH)

Yazıldı: 18.10.2026 ~20:15. D ve E eğitimleri sürerken, AirSim koşularından önce. Dal `airsim`.

## Soru

Araç yolda doğup tam üstünden tetiklenmediğinde, havada rastgele bir noktadan başladığında:
- Klasik zincir (dedektör yeri seçer, mod oraya götürüp indirir) ne kadar güvenli ve hızlı iniyor?
- RL ne kadar güvenli ve hızlı iniyor?
- İkisi GT etiketle ve v3 etiketle nasıl farklılaşıyor?

## Gerekçe

- **Faz 6 (ölçülen):** B2-s0 ve C1-s0, v3 ile 10 inişin 9'unda yola indi. Araç yolda doğuyor ve tam üstünden tetikleniyordu. Arda'nın gözlemi: bu test yanlı.
- **Faz 3/4 ikinci tur (ölçülen, GT, yoldan tetik):**
  - Klasik: zemin kuralına 10/10 uygun, süre medyan 25.4 s.
  - RL B2-s0 + kalkan: zemin kuralına 10/10 uygun, süre medyan 21.6 s, en uzun 110.8 s.
- **Arda'nın sorusu (2026-10-18):** yeri klasik bir algoritma seçse, RL yalnız komut verse daha mantıklı olur mu? İki yaklaşımın aynı başlangıçlarda kıyası bu soruya veri sağlar.

## Kurulum

- **Dünya:** AirSimNH. PX4 kendi rootfs'unda, Gazebo eş parametreleriyle. Rüzgâr yok.
- **Başlangıç:** `havada_sec.py --tohum 2026 --n 10` ile çekilir.
  - Doğma noktası Faz 3'ün 10 güvenli noktasından biri.
  - Araç 30 m'ye kalkar. Doğma noktasından 10–50 m uzaktaki hedefe uçar, 20–30 m irtifaya iner (`run_airsim.sh --havada`). Tetik orada verilir.
  - Liste koşudan önce yazılır ve sabittir.
- **Ön koşul:** `--havada` önce `havada_sonra.sh` denemesinden geçmeli (2/2 iniş) ve ana dala birleşmeli. Geçmezse Faz 7 koşulmaz.
- **RL modeli** (`faz7_model.py`, sonuçtan önce sabit kural):
  - Düzeltme 13 (E) benimsendiyse E1 tohumları arasından, değilse ve Düzeltme 12 (D) benimsendiyse D1 tohumları arasından seçilir.
  - Seçim ölçütü: val_b32'de RL + kalkan zemin başarısı en yüksek tohum.
  - İkisi de benimsenmediyse B2-s0.
- **Kollar** (her biri aynı 10 başlangıç, birer kez; çöken ya da başlamayan koşu `inis_sina.sh` kuralıyla yeniden koşulur):

  | Kol | Yöntem | Etiket |
  |---|---|---|
  | K-GT | klasik zincir | GT |
  | R-GT | RL + kalkan 10 m | GT |
  | K-v3 | klasik zincir | v3 |
  | R-v3 | RL + kalkan 10 m | v3 |

- **Koşum:** D, E ve havada denemesi bittikten sonra, sim yanında eğitim yokken (`~/rl_inis/airsim_pilot/faz7_havada.sh`).

## Ölçüm

Faz 3–6 ile aynı (`inis_sina.py` + ortografik harita). Kol başına:
- Zemin kuralına uygun iniş; çim, sert, yol ve diğer sınıflar.
- Gerçek temas (çarpışma nesnesi zemin değil).
- İniş süresi: tetikten temasa; ortalama ve medyan.
- Yatay yol.

## Tahminler (_tahmin)

- **T7a:** R-GT'nin zemin kuralına uygun inişi ≥ K-GT'ninki − 1.
- **T7b:** R-GT'nin medyan iniş süresi ≤ K-GT'ninki − 3 s.
- **T7c:** v3 ile ikisi de GT'den kötü. K-v3 ve R-v3'ün zemin kuralına uygun inişi ≤ 7/10. Darboğaz algı (v3 yolu "sert" sayıyor), kontrolcü değil.
- **T7d:** Havadan başlayınca R-v3'ün yola inişi Faz 6'dakinden (9/10) az: ≤ 6/10.

## Karar

- **Örneklem küçük** (10 başlangıç, tek model). Sonuç ön sonuç sayılır, yön gösterir.
- Bu faz model seçmez. Klasik / RL / karma yapı tartışmasına veri sağlar. Karar Arda'nındır.
- Gerçek temasla güvensiz iniş (ağaç, çit, araç, yapı) her kolda ayrıca raporlanır.

## Düzeltme (2026-10-18 ~22:00, Faz 7 koşmadan önce)

F deneyi (Düzeltme 14) eklendi. RL modeli sırası şöyle olur:
1. F benimsendiyse F1 tohumları.
2. Değilse E1 tohumları.
3. Değilse D1 tohumları.
4. Değilse B2-s0.

Seçim ölçütü aynı: val_b32'de RL + kalkan başarısı en yüksek tohum. Faz 7 F de bitince koşar, çünkü eğitim sürerken beklemeye devam eder.

## Düzeltme 2 (2026-10-18 ~22:30, Faz 7 koşmadan önce)

Arda tarama istedi (rl_f0 Düzeltme 15). Faz 7, taramanın sonuna ertelendi. Böylece RL kolu en iyi modelle koşar.

RL modeli sırası:
1. Tarama kararı (H15) kazanan ayarı yeni en iyi saydıysa, onun üç tohumundan val_b32'de RL + kalkan başarısı en yüksek olanı.
2. Değilse önceki sıra: F, E, D, B2-s0.

Kollar, başlangıçlar ve tahminler değişmedi.

## Düzeltme 3 (2026-10-19 03:00, Faz 7 koşmadan önce): 30 başlangıç

**Sebep:** 10 başlangıçla klasik zincir ile RL arasındaki fark istatistiksel olarak ayrılamaz.
- Örnek: 7/10 ile 9/10 arasındaki fark, Fisher testinde anlamlı değil (_hesap).
- Bu karşılaştırma tezin bir bölümü olacak. Arda bilgisayarı açık bırakıyor, süre var.

**Değişiklik:** `havada_sec.py --tohum 2026 --n 30`. Aynı tohumdan çekilir, ilk 10 başlangıç öncekilerle aynıdır.
- Kollar, ölçüm ve tahminler değişmedi. Tahminlerdeki "/10" oranları "/30"a orantılı okunur.
  - T7c: ≤ 21/30.
  - T7d: ≤ 18/30.
- Ek tanımlayıcı: klasik ile RL arasında zemin kuralı oranları için Fisher kesin testi, GT ve v3 için ayrı ayrı.
- Süre: ~4–5 saat (_tahmin).

## Düzeltme 4 (2026-10-19 17:30, Faz 7 koşmadan önce)

Faz 7, birleşim turunun (rl_f0 Düzeltme 18) sonuna alındı.

RL modeli sırası:
1. Birleşim turunun final adayı: 2M seçildiyse 2M, H18 çeşidi benimsediyse çeşit, değilse onun tabanı.
2. Değilse gözlem turu.
3. Değilse tarama.
4. Değilse önceki sıra.

Seçim ölçütü aynı: val_b32'de RL + kalkan başarısı en yüksek tohum.

## Yürütme notu (2026-10-21 14:00): ilk Faz 7 koşusu geçersiz, düzeltilip yeniden koşuluyor

**Olay (ölçülen, `_gunlukler/airsim_inis_f7_*_20261021_*`):**
- Faz 7 09:20'de başladı (model c23 s1, Düzeltme 4'ün sırasıyla: birleşim turunun tabanı, val_b32'de kalkanlı başarısı en
  yüksek tohum, %73.4).
- 120 koşudan yalnız ilki uçtu (klasik + AirSim etiketi, çime indi, 28.5 s).
- Koşu 2: araç hedef noktaya vardı ama hedef yüksekliğe inmedi (konum z −28.7 m, hedef 26.2 m; "havada hedefe
  varılamadı"). Yükseklik komutu tek bir best-effort mesaj ve kaybolabiliyor.
- Koşu 2'nin temizliği yarıda kesildi. `inis_sina.sh`, HATA satırını görünce TERM gönderiyordu; temizlik zaten
  başlamıştı ve TERM tuzağı onu PX4 kapanmadan bitirdi. Kalan PX4 yüzünden sonraki 119 koşunun hepsi "çalışan bir sim
  var" diyerek başlamadı, 4 kolun hepsinde.

**Düzeltme (Arda'nın onayıyla, `src/eland_airsim/scripts`):**
- `run_airsim.sh`: havada başlangıçta konum ve yükseklik komutu, araç varana kadar 5 s'de bir yeniden gönderilir.
- `run_airsim.sh`: temizlik INT ve TERM'i yok sayar, yarıda kesilmez.
- `inis_sina.sh`: her denemeden önce AirSim'in kendi PX4'ü (çalışma dizini `rootfs_airsim`) kalmışsa kapatılır. Gazebo
  PX4'üne dokunulmaz.

**Doğrulama (ölçülen):**
- Koşu 2'nin başlangıcı (130.5, 125.7) → (35.4, −31.5, 26.2) yeniden uçuldu: 26.4 m'ye indi, çime indi (23.8 s).
- `run_airsim.sh`'e temizlik sırasında art arda üç TERM: kalan PX4 0, AirSim 0.

**Yeniden koşu:** aynı 30 başlangıç (tohum 2026), aynı 4 kol, aynı model (c23 s1). Tahminler, ölçütler ve karar kuralı
değişmedi. Geçersiz koşunun sonuçları `airsim_faz3/f7_*_gecersiz_20261021.jsonl` olarak saklandı, hiçbir karara girmez.
