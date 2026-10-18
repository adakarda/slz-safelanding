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
