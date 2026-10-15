# W5 pencere kuralı v2 (ön kayıt, K34, 2026-10-15)

v1 (`tools/veri/w5_pencere.py`) donmuş ve değişmedi; dilim 1 sonuçları v1'e
göre raporlanır. v2 ayrı bir kural olarak burada tanımlanır ve adım 1b'nin
yeni tohumlarında (9–12) sınanır. Dayanağı: dilim 1 adım 1 tohum 5'te v1'in
ıskası ve fizik (ρ, görüntü merkezi güvenli sınıfta değilse 0). Kod değişikliği
yok.

## Tanım

    v2 = v1  VE  nadir_ic

- **nadir noktası:** VALIDATE girişinde aracın gerçek yatay konumu
  (`duzenli.csv` `x_gercek`, `y_gercek`), v1'in h_doy için kullandığı örnekle
  aynı örnek (t_gz'ye göre sıralı, `t_validate`'te ya da hemen sonrası).
  Kamera `base_link`'e göre (0, 0, 0.10) m'de, aşağı bakıyor
  (`x500_seg_cam_down/model.sdf`): yatay montaj ofseti yok. Yatış ve yunuslama
  hesaba katılmaz (v1 de katmıyor; VALIDATE girişinde ölçülen ~0°).
- **nadir_ic:** nadir noktası hedefin dikdörtgeninin içinde ya da sınırında
  (dünya yaml'ındaki `hedef` yüzeyinin ilk dikdörtgeni; W5: −5…+5 m, −5…+5 m).
- **grup_v2** = pencereli, eğer v1 pencereli **ve** nadir_ic; değilse penceresiz.
- **sinirda_v2** = sinirda_v1, eğer nadir_ic; değilse 0.
- Bilgi sütunu (kuralın parçası değil): `nadir_kenar_m`, nadir noktasının
  dikdörtgen kenarına işaretli uzaklığı (içeride +, dışarıda −).

Ölçülen denetim v1'deki gibi: VALIDATE ile Gazebo teması arasında
view_bounded ve ρ > 0 olan ≥ 10 kare → pencereli.

## Değerlendirme

Tahminler adım 1b'de her koşudan hemen sonra, kare sayısına bakılmadan,
v1 ve v2 birlikte `dilim1_adim1b_pencere_tahmini.csv`'ye yazılıp commit'lenir
(K35). Kullanılan hesap (veriyle birlikte saklanır,
`~/eland_veri/_yasa_dilim1/pencere_v2.py`):

```python
out = w5_pencere.pencere(bolum, olcum=False)                 # v1
x, y = duzenli x_gercek, y_gercek @ v1'in örneği
x0, x1, y0, y1 = hedef dikdörtgeni
nadir_ic = x0 <= x <= x1 and y0 <= y <= y1
grup_v2 = 'pencereli' if out['grup'] == 'pencereli' and nadir_ic else 'penceresiz'
sinirda_v2 = out['sinirda'] if nadir_ic else 0
```

Geriye dönük bilgi (sınama değil; v2 bu bölümlerden biri görülerek yazıldı):
29 kayıtlı W5 bölümünde v1 28/29, v2 29/29. Tohum 5'te nadir noktası
(0.15, 5.09): platform kenarının **0.09 m** dışında. v2'nin t5 kararı bu
9 cm'ye dayanıyor. Öteki 28 bölümde nadir noktası içeride, kenara
0.65–3.08 m.
