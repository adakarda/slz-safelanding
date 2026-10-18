# eland_airsim/araclar

Taşıma sırasında kullanılan ölçüm araçları. Paketin bir parçası olarak kurulmaz; yerinden çalıştırılır.

| Araç | Ne yapar | Nerede çalışır |
|---|---|---|
| `yakala.py`, `pilot_kos.sh` | Kamera kipinde 20/25/30/100 m'den RGB + SORA gerçeği (Faz 1 pilotu) | Windows venv / WSL |
| `v3_olc.py`, `v3_tani.py` | v3'ü o karelerde koşturup gerçekle kıyaslar (ham 8 sınıf: yol ayrı) | `~/v3_test/venv` |
| `orto.py`, `orto_kos.sh` | Ortografik tepe çekimi (karolar, 10 cm/piksel), yollar ayrı etiketli | Windows venv |
| `orto_analiz.py` | Karoları birleştirir, dedektör kurallarıyla uygun alanı ve başlangıç noktalarını bulur | `~/v3_test/venv` |
| `inis_harita.py` | İniş noktalarını haritada değerlendirir (sınıf, tehlikeye uzaklık, SORA, zemin kuralı) | `~/v3_test/venv` |
| `birlestir.py` | Bir kolun ana batch'ini, eksik başlangıçların yeniden koşusuyla birleştirir | python3 |
| `politika_ozet.py` | policy_node'un politika.csv'sinin özeti | python3 |
| `yumusak_say.py` | Kolların harita sonucundan özet: çim, sert, yol, zemin kuralı, SORA | python3 |
| `ilk_yanal.py` | Bir batch'te politikanın RL modu devredeyken seçtiği ilk yanal eylemin irtifası | python3 |
| `mod_degisim.py` | ULog'da nav_state değişimleri ve o anki çubuk değerleri (RL modu neden bırakıldı) | python3 + pyulog |
| `faz6_zemin_v2.sh` | Faz 6 sürücüsü: C kuyruğunu bekler, C1 tohumunu seçer, A0/A1/G1 kollarını koşar | WSL |
| `v3_airsim.py` | v3'ü AirSim kamerasında canlı koşturan düğüm (`run_airsim.sh --v3` başlatır; asıl kopya `~/v3_test`) | `~/v3_test/venv` |
| `kos_airsim.sh` | F1 dinamik tanılama uçuşu, AirSim'de | WSL |
| `param_bson.py`, `ulg_param.py`, `ulg_fark.py`, `param_geri_yukle.py` | PX4 parametre dosyası ve ULog parametreleri: okuma, kıyas, geri yükleme | python3 + pyulog |

Yollar bu makineye göre yazıldı (`~/rl_inis` ve Windows'ta `C:/Users/arda_/airsim`).
Ayarlar: `../config/settings_cv.json` (kamera kipi), `../config/settings_orto.json` (ortografik).
