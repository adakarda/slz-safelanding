# Ön kayıt: AirSim Faz 6, `zemin_v2` (C1) ile B2-s0 (AirSimNH)

Yazıldı: 18.10.2026 ~14:55. C deneyinin karar betiği çalışmadan ve AirSim koşularından önce yazıldı. C1 tohum 0
ve 1'in değerlendirmesi bitti, ama `h11_karar.py` çıktısına bakılmadı. Dal `airsim`.

## Soru

`zemin_v2` ile eğitilen politika (C1), AirSim'de B2-s0'dan daha sık çime iniyor mu? Özellikle v3 etiketiyle,
çünkü v3 yolu "sert zemin" sayıyor.

## Gerekçe (ölçülen, önceki koşular)

- **Klasik mod + v3** (ikinci tur): 10 inişin 6'sı yola, 4'ü çime.
- **B2-s0 + GT + kalkan 10 m** (R2, ikinci tur): 10 inişin 7'si çime, 3'ü sert zemine. Hepsi zemin kuralına uygun.
- **B2-s0 + v3** batch olarak koşulmadı (Faz 4'te R3 ertelendi). Kullanıcının elle yaptığı denemelerde yola indi.
- **Hafif ortam:** B2-s0 15 m üstünde %100 "alçal" seçiyor. İlk yanal eylemin medyan irtifası 9.2 m.

## Kurulum

- Faz 3–5 ile aynı:
  - AirSimNH, aynı 10 başlangıç (`airsim_nh_baslangiclar.csv`);
  - `inis_sina.sh` üzerinden `run_airsim.sh --takeoff 25 --trigger --no-hud`;
  - PX4 kendi rootfs'unda, Gazebo eş parametreleriyle;
  - rüzgâr yok;
  - kalkan 10 m (kullanıcının AirSim'deki ayarı).
- **Model seçimi:**
  - C1'in tohumunu `h11_karar.py` seçer (Düzeltme 11): H11b ve H11c'yi kendi tohum çiftinde sağlayanlar içinden yumuşak inişi en yüksek olan. Hiçbiri sağlamazsa, yumuşak inişi en yüksek tohum.
  - Seçim AirSim sonucundan önce yapılır ve değiştirilmez.
- **Kollar** (her biri 10 başlangıç, birer kez; çöken ya da başlamayan koşu `inis_sina.sh` kuralıyla yeniden koşulur):

  | Kol | Model | Etiket |
  |---|---|---|
  | A0 | B2-s0 | v3 |
  | A1 | C1 (seçilen tohum) | v3 |
  | G1 | C1 (seçilen tohum) | GT |

  G1'in kıyası G0'dır: önceki R2 ikinci tur sonucu (B2-s0, GT, kalkan 10). Yeniden koşulmaz.
- **Sıra:** A0, A1, G1. Bütün koşular C kuyruğu bittikten sonra, sim yanında eğitim yokken yapılır.
- **Betik:** `~/rl_inis/airsim_pilot/faz6_zemin_v2.sh`.

## Ölçüm

`inis_sina.py` ve ortografik GT haritası (`inis_harita.py`), Faz 3–5 ile aynı. Kol başına sayılanlar:
- **Çim:** harita sınıfı çim, zemin kuralına uygun.
- **Sert:** harita sınıfı sert, zemin kuralına uygun.
- **Yol**, **ağaç** ve diğer sınıflar.
- **Zemin kuralı**, **SORA 3 m**, **gerçek temas** (çarpışma nesnesi zemin değil), **temas hızı**.
- **Tanımlayıcı:**
  - Politikanın kendi seçtiği ilk yanal eylemin irtifası (`ilk_yanal.py`, kalkan sayılmaz). Önceki B2-s0 + GT kolunda medyan 12.3 m.
  - Hafif ortamda aynı ölçüt, B1 ve C1'in üç tohumu için (`eylem_irtifa_env.py`).

## Tahminler (_tahmin)

- **T1 (birincil):** A1'in çim sayısı ≥ A0'ınki + 2.
- **T2:** A1'in zemin kuralına uygun inişi ≥ A0'ınki − 1.
- **T3:** A1'in yola inişi ≤ A0'ınki.
- **T4:** G1'in çim sayısı ≥ 8 (G0: 7). G1'in zemin kuralına uygun inişi ≥ 9 (G0: 10).
- **Beklenen A0:** 3–5 çim, 3–6 yol (klasik + v3 gibi).

## Karar

- **Örneklem küçük:** tek tohum ve 10 başlangıç. Sonuç ön sonuç sayılır; yalnız yön gösterir.
- **AirSim'in varsayılan RL modeli** (kullanıcı denemeleri için): T1 ve T2 sağlanırsa ve C deneyinde `zemin_v2` benimsendiyse C1 olur. Öbür durumlarda B2-s0 kalır.
- **`zemin_v2` benimsenmediyse:** bu faz yalnız tanımlayıcıdır. Model değişikliği Arda'nın kararıdır.
- Gerçek temasla güvensiz iniş (ağaç, çit, araç, yapı) her kolda ayrıca raporlanır.
