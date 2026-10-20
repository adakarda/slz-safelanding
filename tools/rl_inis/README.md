# tools/rl_inis — RL iniş ve AirSim çalışma betikleri (ayna)

Proje sahibinin makinesindeki `~/rl_inis` klasörünün aynası. Ana belge:
[`docs/rl_airsim/README.md`](../../docs/rl_airsim/README.md).

## Ne var, ne yok

- **Var:** betikler (`.py`, `.sh`), küçük metin sonuçları (`.txt`, `.csv`, `.md`, küçük `.json`), taramanın
  günlüğü `arama/arama.log` ve sonuç tablosu `arama/ozet.md`.
- **Yok:**
  - `venv/` (Python ortamı). Aşağıda nasıl kurulacağı yazıyor.
  - `kos/`: eğitilmiş modeller, eğitim ve değerlendirme çıktıları (~9 GB).
  - Veri: MESSI sahneleri `~/eland_veri/rl/` altında ve özel. Sahibinden izin gerekir.
  - Görüntüler, `.npz` dizileri, koşu günlükleri, tek seferlik commit yardımcıları.

## Kullanmadan önce

- **Yollar bu makineye göre yazıldı:** `~/rl_inis`, `~/eland_veri`, `~/ros2_ws`, Windows'ta
  `C:\Users\arda_\airsim`. Başka bir makinede önce kopyala:

  ```bash
  rsync -a ~/ros2_ws/tools/rl_inis/ ~/rl_inis/
  ```

  Çıktılar `~/rl_inis/kos/` altına yazılır.
- **Ortam:** `source ~/rl_inis/ortam.sh`. Bu dosya `PYTHONPATH`'e depodaki `src/eland_rl` ve `src/eland_common`'ı
  ekler, `RL_PY`'yi venv'in python'una bağlar.
- **Aynayı yenilemek** (yalnız `~/rl_inis`'in olduğu makinede):

  ```bash
  bash ~/ros2_ws/tools/rl_inis/esitle.sh
  ```

- **Depodaki öbür kopyalar:** `src/eland_rl/arama/`, `src/eland_rl/gorsel/` ve `src/eland_airsim/araclar/`.
  Ön kayıtlar bu yollara atıf yapar. İçerikleri 2026-10-20'de buradakilerle aynı. Çalışan asıl kopya
  `~/rl_inis`'tedir.

## Python ortamları

| Ortam | Kurulum | Paketler |
|---|---|---|
| `~/rl_inis/venv` (eğitim, değerlendirme) | `python3 -m venv --system-site-packages ~/rl_inis/venv`, sonra `pip install -r requirements_rl_venv.txt` | gymnasium 1.4.0, stable-baselines3 2.9.0, scipy, transformers (yalnız Depth Anything deneyi için). **Kullanıcı dizininden gelenler:** torch 2.13.0+cu130, numpy 2.5.1, opencv-python 4.14.0. Python 3.12.3, Ubuntu 24.04 |
| `~/airsim-venv` (WSL'de AirSim istemcisi) | `airsim_pilot/venv_kur.sh` | `airsim==1.8.1` bağımlılıksız + `msgpack` + bizim `msgpackrpc` katmanımız (`src/eland_airsim/data/msgpackrpc_shim.py`). Liste: `requirements_airsim_wsl.txt` |
| Windows Python (ortografik harita, kamera kipi) | `pip install airsim==1.8.1 numpy pillow` + aynı katman | `airsim_pilot/orto.py`, `yakala.py` |
| `~/v3_test/venv` (segmentasyon v3) | depoda değil | Segmentasyon modeline dokunulmaz (AGENTS.md §3.6) |

## Klasörler

| Yer | Ne | Ön kayıt |
|---|---|---|
| `ortam.sh`, `py.sh`, `test_kos.sh`, `derle_mod.sh` | Ortam, betik çalıştırıcı, birim testleri (64 test), yeni paketlerin derlemesi | — |
| `pilot_kos.sh`, `ust_sinir.py`, `odul_*.py`, `v1_*`, `v2_*`, `gorus_kahini.py`, `kalkan_testi*.py`, `kanal_teshis.py` | İlk pilotlar: düz alçalmaya çöküş, ödül taraması, `sora_v1`, SORA kanalı, kalkan | Düzeltme 2–5 |
| `messi/` | MESSI paketinden eğitim sahneleri (`hazirla.py`), A1 ve A2b eğitimleri | Düzeltme 6, 8 |
| `derinlik/` | Depth Anything deneyi (PA–PD kolları, `h7_karar.py`) | Düzeltme 7 |
| `vekil_kos.sh`, `vekil_ozet.py` | Kodlayıcı karşılaştırmasının vekil görevi | Düzeltme 10 |
| `kuyruk_b.sh` … `kuyruk_f.sh`, `h9_karar.py` … `h14_karar.py`, `ozet_b.py`, `kol_ozet.py` | B, C, D, E, F deneyleri: kuyruk ve ön kayıtlı karar kuralı | Düzeltme 9, 11–14 |
| `arama/` | Ödül ve eğitim ayarları taraması (`arama.py`, `konfig_t1.json`, `kararla.py`), sonraki turlar (`b2hiz_*`, `gozlem_*`, `birlesim_*`), günlük ve tablo | Düzeltme 15, 16, 18, 19 |
| `final_test.sh` | Final test (IrYamim). **Bir kez ve yalnız Arda "koş" deyince** | Düzeltme 17 |
| `airsim_pilot/` | AirSim taşıma fazları 0–7: pilotlar, ortografik harita, toplu koşular, ölçüm araçları | `docs/onkayit/airsim_faz*.md` |
| `demo/` | AirSim gösterimleri: rastgele havada başlangıç, çatı üstü başlangıç (`cati_sec.py`, `cati/sonuc.txt`) | gösterim, ölçüm değil |
| `gorsel/` | Tez çıktıları (eğriler, tablolar, Wilson aralıkları), eğitim izi videoları, saatlik yenileme | — |
| `tanilama/` | PX4 hız döngüsü tanılaması (F1), ortam hız profili, PX4 parametre araçları | Düzeltme 1 |
| `eslesme/`, `f4/` | F1 eşleşme testi (Gazebo sınıf haritası ↔ ortam izdüşümü), F4 Gazebo + PX4 pilotu | Düzeltme 1, 3 |
| `hiz/` | Hız yamaları ve `zemin` kuralının geliştirme kopyaları (artık `src/eland_rl`'de) | yürütme notu 2026-10-17 |
| `alan_analizi.py`, `eylem_*.py`, `stokastik_test.py`, `sure_etkisi.py`, `hiz_izle.py`, `egitim_dokum.py` | Tanımlayıcı analizler: inilebilir alan, eylem dağılımı, argmax / olasılıklı, test süresi 30/60/90 s | tanımlayıcı, karar yok |
| `durum*.sh`, `durum_json.py`, `pano_veri.py`, `bekle.sh` | Anlık durum ve izleme | — |
| `denetim/`, `anlat/`, `ogren/`, `ornek_gorus.py` | Açıklama sayfalarının verisi ve öğrenme yardımcıları | — |
| `veri_hatti/` | MESSI paket keşfi (Aşama 0) | `docs/rl_veri/` |
