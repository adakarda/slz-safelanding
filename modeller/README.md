# modeller — eğitilmiş RL iniş politikaları

Dört PPO politikası (stable-baselines3 2.9.0). Her klasörde:

- `model.zip`: politika,
- `args.json`: eğitim ayarları. `policy_node` gözlemi buradan kurar, `model.zip` ile aynı klasörde durmalı.
- `eval_val_b32_10.csv`: doğrulama değerlendirmesinin ham satırları (320 deneme × yöntem).

Ayrıntı: [`../docs/rl_airsim/README.md`](../docs/rl_airsim/README.md) §5. Sonuçlar:
[`../docs/rl_airsim/RAPOR.md`](../docs/rl_airsim/RAPOR.md).

| Klasör | Ayar | Kalkanlı başarı | Süre | Kalkansız başarı | Kalkansız güvensiz | Kaynak koşu |
|---|---|---|---|---|---|---|
| `c13_s0` | `zemin_v3`, eğitimde 30 s, kayarak alçal (`--diag`), kalkan eğitimde (`--shield-train-m 10`), tohum 0 | %69.7 | 13.8 s | %69.7 | %7.2 | `kos/arama/t2_c13_f_kayarak_kalkan` |
| `c13_s1` | aynı, tohum 1 | %68.8 | 14.4 s | %68.8 | %8.8 | `kos/arama/t3_c13_f_kayarak_kalkan_s1` |
| `c13_s2` | aynı, tohum 2 | %60.6 | 16.9 s | %60.6 | %15.3 | `kos/arama/t3_c13_f_kayarak_kalkan_s2` |
| `b2_s0` | `zemin_v1` + aynalama, eğitimde 90 s, tohum 0 | %76.9 | 17.4 s | %72.5 | %8.8 | `kos/b_B2_s0` |

Ölçülen: `val_b32`, 32 sahne × 10 başlangıç, 30 s, argmax, nominal dinamik, zemin kuralı. Süre başarılı
inişlerin ortalaması. c13'te kalkan eğitimin içinde, bu yüzden kalkanlı ve kalkansız aynı.

## Kullanım

```bash
source ~/rl_inis/ortam.sh
# değerlendirme (c13'ün bayrakları eğitimiyle aynı olmalı)
$RL_PY -m eland_rl.evaluate --scenes ~/eland_veri/rl/messi_ds4/val_b32.txt --model modeller/c13_s0/model.zip \
  --starts 10 --reward zemin_v3 --obs sem_depth_sora --sora-cell 0.25 --diag --shield-train-m 10 --only-rl --out /tmp/c13.csv
# AirSim, havada rastgele başlangıç, 10 m kalkan
src/eland_airsim/scripts/run_airsim.sh --havada rastgele:7 --rl ~/ros2_ws/modeller/c13_s0/model.zip --kalkan 10 --trigger --izle
```

- Yükleme için `eland_rl` paketinin içe aktarılabilir olması gerekir: kodlayıcı (`eland_rl.policy.PaperCNN`) onun
  içinde.
- Eğitim verisi (MESSI paketi) depoda değil ve özel.

## Doğrulama (SHA-256)

```
93962760347c54b6acaad2f872d4b2576b711e3d6d2bca4a2849a033240c1dcf  c13_s0/model.zip
05a6380b0c618d0d123d7e93893131ed23198b8faa5250f7a188db7cdc7c3013  c13_s1/model.zip
f9ff875cf18ee779972b13319f0029c0122e794eb414005a039977b021645434  c13_s2/model.zip
a339f24804237428d9302102bbd6b98fbf830cf35fd2faf67882f1c184d7e8fb  b2_s0/model.zip
```
