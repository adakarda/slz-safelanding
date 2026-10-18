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
