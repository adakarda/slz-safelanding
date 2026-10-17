# Ön kayıt: AirSim Faz 4, RL zinciri (AirSimNH)

Yazıldı: 18.10.2026 ~00:35, RL koşularından önce. Dal `airsim`.

## Soru

Hafif ortamda eğitilen politika, AirSim'de PX4 + RL Landing modu üzerinden iniyor mu? Sonuç hafif
ortamdakiyle ne kadar uyumlu? AirSim'in PX4 dinamiği, hafif ortamın (Gazebo'dan tanılanmış) dinamiğine
ne kadar yakın?

## Kurulum

- Dünya AirSimNH; Faz 3 ile aynı 10 başlangıç (`airsim_faz3_onkayit.md`).
- `run_airsim.sh --rl MODEL --takeoff 25 --trigger --no-hud`. `eland_rl_mode` ve `eland_rl.policy_node`
  kullanılır:
  - konum `/eland/gercek_poz`'dan (AirSim gerçeği, ENU);
  - etiket `/camera/segmentation`'dan (AirSim GT) ya da `--v3` ile `/eland/v3/etiket`'ten;
  - gözlem eğitim koşusunun `args.json`'una göre kurulur (`policy_node.training_config`).
- Model: `b_B2_s0` (zemin_v1 + aynalama). Hafif ortamda val_b32'de en iyi tek tohum:
  - RL %72.5 zemin başarısı;
  - RL + kalkan %76.9.
- Kollar (her biri 10 başlangıç, birer kez):
  - **R1**: B2-s0, GT etiket, kalkansız.
  - **R2**: B2-s0, GT etiket, kalkan 10 m (evaluate.py'deki rl_kalkan ile aynı).
  - **R3**: B2-s0, v3 etiket, kalkan 10 m. Bellek izin verirse.
- Dinamik: `tanilama/kos_airsim.sh`. F1'deki adım + rastgele eylem programı AirSim'de uçulur. `analiz.py`
  ile tau_xy, a_max, gecikme, tau_z ölçülür ve Gazebo kos1 ile karşılaştırılır.

## Ölçüm

Faz 3 ile aynı (`inis_sina.py`): indi mi, temas hızı, iniş sınıfı, çarpışma nesnesi, uzaklık.
Zemin başarısı yaklaşık olarak "iniş sınıfı 0 ya da 1" diye alınır. İnsan ya da araca 2 m tampon AirSim
koşusunda ölçülmüyor. AirSimNH'de araçlar park halinde ve insan yok; fark küçük (_tahmin).

## Kapı (yol haritasından)

RL modu her başlangıçta devreye girer ve iner. Hafif ortam ile AirSim arasındaki sonuç uyumu raporlanır.
Sayı hedefi yok.

## Tahminler (_tahmin)

- **R1.** 10 koşunun 10'unda mod devreye girer. İnenlerin %40–70'i güvenli sınıfa iner. Politika MESSI
  fotoğraflarında eğitildi; AirSimNH'nin sınıf dağılımı farklı (çok ağaç ve yol), bu yüzden hafif
  ortamdaki %72.5'in altında.
- **R2 ≥ R1.** Kalkan, son 10 m'de güvensiz merkeze alçalmayı engeller.
- **R3 < R2.** v3'ün AirSimNH'deki yol hatası (%45 "sert zemin") yola inişleri artırır.
- **Dinamik.** AirSim'de tau_xy ve gecikme Gazebo'dakinden farklı. Fark %50'yi aşarsa hafif ortama ikinci
  bir parametre seti önerilir. Bu yalnız öneri; eğitime dokunulmaz.
