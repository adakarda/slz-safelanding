# Ön kayıt: AirSim Faz 5, sabit rüzgârda iniş (AirSimNH)

Yazıldı: 18.10.2026 ~03:40, rüzgâr koşularından önce. Dal `airsim`.

## Soru

Klasik mod ve RL modu, 5 m/s sabit yan rüzgârda AirSim'de nasıl iniyor?
Rüzgârsız ikinci tur (eş PX4 parametreleriyle) ile kıyaslanır.

## Kurulum

- Faz 3/4 ile aynı: AirSimNH, aynı 10 başlangıç, `run_airsim.sh --takeoff 25 --trigger --no-hud`.
- PX4 kendi rootfs'unda, Gazebo eş parametreleriyle (`config/px4_gazebo_esdeger.params`).
- Rüzgâr: `--ruzgar 0,5,0` (NED, doğuya doğru esen 5 m/s). AirSim `simSetWind`, köprü açılırken uygulanır ve
  koşu boyunca sabit kalır.
- Kollar (her biri 10 başlangıç, birer kez):
  - **W1**: klasik mod, GT etiket.
  - **W2**: RL B2-s0, GT etiket, kalkansız.
- Kıyas: aynı kolların rüzgârsız ikinci turu (`*_t2`).

## Ölçüm

Faz 3/4 ile aynı (`inis_sina.py` + ortografik harita): indi mi, iniş sınıfı, SORA (tehlikeye ≥ 3 m), zemin
kuralı, temas hızı, süre. Ek olarak:
- **Yatay uzaklık:** mod seçildiği noktadan iniş noktasına.
- **Sürüklenme:** iniş noktasının rüzgâr yönündeki (doğu) bileşeni.

## Tahminler (_tahmin)

- **W1.** 10/10 iner. Güvenli sınıfa iniş rüzgârsızdakinden en çok 1 eksik. Temas hızı < 1 m/s. Konum kontrolü
  rüzgârı karşılar; iniş noktası seçilen adaydan ortalama 1 m'den az kayar.
- **W2.** 10/10 iner. Zemin kuralına uygunluk rüzgârsızdan en çok 2 eksik. Politika rüzgârla eğitilmedi ama hız
  komutlarını PX4'ün hız denetleyicisi uyguluyor; rüzgâr büyük ölçüde karşılanır.
- **Risk.** 5 m'den sonraki dikine inişte (RL modu politikayı bırakır) rüzgâr yönünde 0.5–1 m sürüklenme.

## Sonuç (2026-10-18 06:00)

Ölçülen; tek tohum, 10 başlangıç, harita ile. Rüzgâr köprü günlüğünde doğrulandı ("baslangic ruzgari [0, 5, 0]").

| Kol | İndi | Güvenli sınıf (harita) | Zemin kuralı | SORA | Temas | Temas hızı |
|---|---|---|---|---|---|---|
| W1 klasik, rüzgâr | 10/10 | 8 | 8 | 5 | 0 | 0.27–0.32 m/s |
| Klasik, rüzgârsız (ikinci tur) | 10/10 | 10 | 10 | 8 | 0 | 0.28–0.34 m/s |
| W2 RL, rüzgâr | 10/10 | 8 | 8 | 4 | 2 (ağaç, çit) | 0.66–1.38 m/s |
| RL, rüzgârsız (ikinci tur) | 10/10 | 7 | 7 | 5 | 1 | 0.67–0.83 m/s |

**Tahminler:**
- **W1, 10/10 iner:** tuttu.
- **W1, "güvenli iniş rüzgârsızdan en çok 1 eksik":** haritaya göre tutmadı (10 → 8). Ama W1'in "ağaç" görünen
  2 inişinin temas nesnesi zemin (`Landscape`), kameranın altı çim. Bunlar ağaç tacı kenarında; haritanın
  sınırı. Temasa göre W1 10/10 güvenli.
- **W1, temas < 1 m/s:** tuttu.
- **W2, 10/10 iner ve zemin uygunluğu en çok 2 eksik:** tuttu (7 → 8).
- **W2 riski:** tahmin edilenden kötü. 2 iniş gerçek temasla güvensiz: bir ağaç tepesine (yerden 8 m, 1.3 m/s)
  ve bir çitin üstüne. Kalkansız RL rüzgârda ağaç ve çit kenarına sürükleniyor (_tahmin).
