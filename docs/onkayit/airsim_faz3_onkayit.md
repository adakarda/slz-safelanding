# Ön kayıt: AirSim Faz 3, algı zinciri + klasik acil iniş (AirSimNH)

Yazıldı: 18.10.2026 ~00:19, koşulardan önce (ilk koşu 00:22'de başladı). Dal `airsim`.

## Soru

Gazebo'daki algı zinciri ve EmergencyLandingMode, AirSim'de kod değişmeden uçtan uca iniyor mu?
Maskeyi AirSim'in gerçek etiketi verdiğinde ve v3 verdiğinde iniş sonuçları ne?

## Kurulum

- Dünya AirSimNH. PX4 v1.17 `none_iris`, kilitli adım. `run_airsim.sh --takeoff 25 --trigger --no-hud`.
- Algı, harita, dedektör ve mod parametreleri `eland_params.yaml`'daki gibi, değişiklik yok. Dedektörün kuralları:
  - güvenli {0,1}, tehlike {3,4,5,6};
  - r_fit 1.0, r_class_edge 2.0, r_hazard 3.0;
  - min_area 9 m².
- Kollar:
  - **GT**: perception_node AirSim segmentasyonunu okur (`/camera/segmentation`).
  - **v3**: `--v3` ile maske v3'ten gelir (`/eland/v3/etiket`). v3 değiştirilmez.
- Başlangıçlar: ortografik GT haritasından (`orto_analiz.py`, tohum 0) seçilen 10 nokta. Seçim kuralı:
  - yol hücresi;
  - ağaç, yapı, su ve araçtan ≥ 4 m uzak;
  - 8–20 m içinde SORA'ya uygun hücre var;
  - noktalar birbirinden ≥ 40 m uzak.

  NED (m), PlayerStart'a göre:
  (-124.1,-64.3) (130.5,125.7) (131.7,-111.1) (-71.1,130.3) (-4.3,-132.3)
  (-8.9,-0.7) (126.3,7.3) (-130.7,41.1) (29.5,123.1) (-84.7,-133.9)
- Her başlangıç her kolda bir kez koşulur. Tek tohum, ön sonuç.

## Ölçüm (`eland_airsim.inis_sina`, AirSim gerçeğinden)

- **İndi mi.** 3 s durağan ve kamera merkezinde zemin < 1 m. Zaman aşımı 300 s.
- **Temas hızı.** Durmadan önceki son 0.5 s'deki en büyük aşağı hız.
- **İniş sınıfı.** İnişten sonra aşağı kameranın merkez %30'undaki en sık sınıf. Bilinmeyen sayılmaz.
- **Güvenli iniş.** İniş sınıfı 0 veya 1.
- **Çarpışma nesnesi.** AirSim'in bildirdiği son temas.
- **Yatay uzaklık.** Mod seçildiği noktadan iniş noktasına.

## Kapı (yol haritasından)

Sayı hedefi yok. Zincir kopmadan çalışmalı: her koşuda mod devreye girmeli ve ya inmeli ya da gerekçesini
günlüğe yazmalı ("aday yok …"). Sonuçlar Gazebo ile aynı ölçütlerle raporlanır.

## Yürütme notu (00:30)

GT kolunun ilk koşusu (başlangıç 1) geçersiz sayıldı ve kol baştan başlatıldı. Nedeni:
- Köprü `/camera/camera_info`'yu 640×480 RGB için yayınlıyordu.
- mapping_node bu K'yı 320×240 maskeye uyguladı: odak 2 kat, merkez noktası köşede.
- Harita ölçeği ve konumu bu yüzden yanlıştı. Belirti: "candidate lost during approach", sonra kör iniş, yola.

Düzeltme yalnız köprüde (`kamera_bilgisi` varsayılan kapalı, Gazebo'daki gibi). Algı koduna dokunulmadı.
Bu koşudan kalan, ölçümle ilgisiz bir bulgu var: COMMIT'te PX4 "invalid setpoints → blind land"
failsafe'i verdi. Bu mod tarafında, ayrı incelenecek.

## Tahminler (_tahmin, koşudan önce)

- **GT kolu.** 10 koşunun ≥ 8'i iner. İnenlerin hepsi güvenli sınıfa iner (dedektör kuralları GT'de
  sağlanıyor). Temas hızı < 1 m/s.
- **v3 kolu.** Daha az güvenli iniş: 5–8/10. Pilot ölçümünde v3 AirSimNH asfaltının %45'ini "sert zemin"
  dedi, bu yüzden bazı inişler yola olabilir.
- **İki kolda da risk.** Ağaç tepesi ya da çatı kenarına yakın adaylarda iniş sırasında temas.
