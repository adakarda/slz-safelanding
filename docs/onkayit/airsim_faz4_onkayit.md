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

## Yürütme notu (2026-10-18 03:30): PX4 yanlış rootfs'ta çalışıyordu, ikinci tur

**Bulgu.** run_airsim.sh PX4'ü `cd rootfs_airsim` ile başlatıyordu. Ama PX4 v1.17 seçenek verilmeyince
çalıştığı klasörü yok sayıyor ve `build/rootfs`'u kullanıyor (`platforms/posix/.../main.cpp`). Bu Gazebo'nun
rootfs'u. Sonuçları:

- Gazebo'nun kayıtlı parametreleri ezildi: `SYS_AUTOSTART` 10016 oldu. Bir sonraki Gazebo açılışı parametreleri
  sıfırlardı.
- Faz 2–4'ün ilk turu PX4 varsayılanlarıyla uçtu: `MPC_Z_VEL_MAX_DN` 1.5 (Gazebo'da 2.0), `COM_RC_LOSS_T` 0.5
  (Gazebo'da 3.0), `EKF2_SENS_EN` 8191 (Gazebo'da 8189).

**Düzeltme.**
- PX4 `-w rootfs_airsim` ile başlatılıyor.
- Gazebo'nun kayıtlı parametreleri, AirSim'den önceki son Gazebo uçuşunun ULog'undan geri yüklendi
  (`rl_inis/tanilama/param_geri_yukle.py`, 17.10 18:43 UTC). Bozulmuş dosya `parameters.bson.airsim_yedek`.
  Doğrulama: AirSim koşusundan önce ve sonra Gazebo dosyasının md5'i aynı.
- AirSim'in PX4'üne Gazebo'nun kayıtlı değerleri uygulanıyor (`config/px4_gazebo_esdeger.params`).
  Airframe'e ait farklar (rotor geometrisi, `MPC_THR_HOVER`) araç modelinin parçası, uygulanmıyor.

**Dinamik (F1 programı, ölçülen).**

| | Gazebo kos1 | AirSim ilk (varsayılan) | AirSim ikinci (eş parametre) |
|---|---|---|---|
| tau_xy | 0.30 s | 0.30 s | 0.30 s |
| a_max | 1.25 | 1.00 | 1.00 m/s² |
| yatay gecikme | 0.20 s | 0.14 s | 0.12 s |
| tau_z | 0.15 s | 0.50 s | 0.35 s |
| dikey gecikme | 0.10 s | 0.00 s | 0.06 s |
| 2 m/s alçal → ulaşılan | 2.07 | 1.64 | 2.13 m/s |
| 1 m/s yatay → ulaşılan | 1.04 | 1.17 | 1.18 m/s |

Ön kayıttaki kural: fark %50'yi aşarsa hafif ortama ikinci bir parametre seti önerilir. tau_z farkı %130
(_hesap). **Öneri:** AirSim için ikinci set tau_z 0.35 s, dikey gecikme 0.06 s, a_max 1.0 m/s². Yalnız
öneri; eğitime dokunulmadı.

**İkinci tur.** Faz 3'ün iki kolu (GT, v3) ve Faz 4'ün R1/R2 kolları eş parametrelerle yeniden koşuluyor
(`rl_inis/airsim_pilot/faz34_ikinci_tur.sh`). İlk tur sonuçları "PX4 varsayılanlarıyla" etiketiyle saklanıyor.
