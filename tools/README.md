# tools/ — ölçüm ve analiz araçları

Uçuş zincirinin parçası değil, ölçmek için. Hiçbiri PX4'e ya da moda yazmaz;
tersi belirtilmedikçe yalnız dinler.

- **Veri toplama araçları:** [`veri/`](veri/README.md) (kayıt, dünyalar,
  toplu koşu, veri seti, analizler).
- **Simülasyonu açan betikler:** `src/eland_sim/scripts/`
  ([`../src/README.md`](../src/README.md)).

| Araç | Ne yapar | Ne zaman |
|---|---|---|
| `make_params.py` | Kaynaktaki `eland_params.yaml`'dan koşu başına parametre dosyası türetir: `make_params.py OUT node.param=değer ...` | Her karşılaştırma koşusu. **Parametre dosyasını elle yazma:** dünya üreteci de aynı YAML'ı okuyor, eksik anahtarla koşu çöker |
| `run_scorer.py` | Bir uçuşu puanlar: aday üretimi, durum geçişleri, irtifa bandına göre dikey hız takip hatası, inilen yerin riski, dokunma sapması | `dene.sh` / `batch_run.sh` içinden |
| `batch_run.sh` | Aynı ayarı N rastgele dünyada uçurur, uçuş başına bir CSV satırı | Tek koşuyla değil dağılımla karşılaştırmak için |
| `batch_summary.py` | Toplu CSV'nin özeti: başarı oranı ve her metriğin ortanca/çeyrekleri | `batch_run.sh` sonrası |
| `fit_fopdt.py` | Kare dalgadan dikey kanalın modelini çıkarır, IMC ile PI kazancı türetir | Eski tanımlama yöntemi; geçerli model için `veri/tesis_analizi.py` (bkz. `docs/KONTROLCU_OLCUMLERI.md` §1.4) |
| `measure_tracking.py` | `tracker_node`'u Gazebo gerçeğiyle puanlar; izlenmeyen kareleri sebebe göre ayırır, tahmin hatasını boyuna/dik böler | İzleyici ve koridor işleri |
| `perception_probe.py` | Araç itilirken haritanın neden site sunmayı bıraktığını eğim ve hıza göre böler | Bozucu / algı çöküşü |
| `wind_inject.py` | Gövdeye yanal kuvvet bozucusu (adım, hamle, rampa) | Kuvvet bozucusu deneyi (aerodinamik rüzgâr değil) |
| `tilt_watch.py` | Canlı yatış, kayma, irtifa | Bozucu koşusunu gözle izlemek |
| `plot_control.py` | Kontrol bölümünün iki poster şekli | Tez / poster |

**Çalıştırma notu:**
- Kullanıcı dizinindeki numpy 2, sistemdeki scipy ile çakışıyor. scipy
  kullanan betikleri şöyle çalıştır:
  `PYTHONPATH=/usr/lib/python3/dist-packages python3 tools/...`.
- `tools/veri/kosu.sh` bunu kendisi yapıyor.
