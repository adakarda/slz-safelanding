# Veri seti — 218 kayıtlı iniş (2026-10-04)

> **Bu dosya ne:** dikey iniş kontrolcüsü (MATLAB/Simulink) ve RL için
> simülasyonda kaydedilmiş iniş verisi. Her bölüm bir iniş: kalkıştan yere
> değmeye kadar 50 Hz tablo, maske başına ve aday başına olay tabloları,
> Gazebo'nun gerçek konumu.
>
> - **İndirme:** GitHub Release
>   [`v6.8-veri-seti`](https://github.com/adakarda/slz-safelanding/releases/tag/v6.8-veri-seti).
>   Veri deponun içinde değil.
> - **Sütunların tanımı:** [`../tools/veri/data_dictionary.md`](../tools/veri/data_dictionary.md).
> - **Nasıl toplandığı, kararlar, turlar:** [`VERI_TOPLAMA.md`](VERI_TOPLAMA.md).
> - **Ölçümlerin özeti:** [`KONTROLCU_OLCUMLERI.md`](KONTROLCU_OLCUMLERI.md).

---

## 1. İndir

| Dosya | Boyut | İçinde | Kimin için |
|---|---|---|---|
| [`eland_veri_matlab_2026-10-04.zip`](https://github.com/adakarda/slz-safelanding/releases/download/v6.8-veri-seti/eland_veri_matlab_2026-10-04.zip) | 57 MB | `birlesik_train.mat`, `birlesik_val.mat`, `birlesik_test.mat`, `tum_ozet.csv`, `data_dictionary.md`, `BENIOKU.md` | **MATLAB/Simulink ile kontrolcü tasarlayan. Başlamak için bu yeter.** |
| [`eland_veri_ornek_matlab.zip`](https://github.com/adakarda/slz-safelanding/releases/download/v6.8-veri-seti/eland_veri_ornek_matlab.zip) | 2.6 MB | 6 temsilî bölüm, her biri tek `.mat` + kısa sözlük | ilk bakış |
| [`eland_veri_bolumler_2026-10-04.zip`](https://github.com/adakarda/slz-safelanding/releases/download/v6.8-veri-seti/eland_veri_bolumler_2026-10-04.zip) | 171 MB | 218 bölüm klasörünün tamamı (CSV'ler, bölüm başına `ep.mat`, ham maskeler `maskeler.npz`, `kosul.yaml`, günlükler), ada dünyaları, `tum_ozet.csv` | Python ile çalışan, ham maskeden yeni öznitelik çıkaracak ya da bölüm bölüm inceleyecek |

- **Bütünlük:** Release'deki `SHA256SUMS.txt`.
- **Tam arşivin yeri:** ev dizinine açılırsa `~/eland_veri/` olur. Bu,
  proje sahibinin makinesindeki düzenin aynısı, yani dokümanlardaki
  `~/eland_veri/...` yolları çalışır.

---

## 2. Ne var

**218 bölüm.**

| Kol | Bölüm | Ne |
|---|---|---|
| Kol 0 (`kol0`) | 31 | modun kendi yasasıyla iniş. W1-W6, 10 rastgele ada, açık alan |
| K1 (`k1_v0.4` ... `k1_v1.5`) | 32 | sabit hız referansı: 0.4 / 0.7 / 1.0 / 1.5 m/s |
| K2 (`k2_d0.2`, `k2_d0.35`, `k2_d0.5`) | 24 | kâhin sabit ıraksama, `v = D*·h_gerçek` |
| K3 (`k3_carpan`, `k3_parca`) | 80 | rastgele hız politikaları. W2-W8 ve 52 ada-tohum |
| K4 (`k4`) | 12 | 40 m'den basamak ve çoklu sinüs referansı (W3) |
| K5 (`k5_A0.3` ... `k5_A1.5`) | 12 | tesis tanımlama: açık çevrim kare dalga, **iniş yok** |
| K5r (`k5r_A0.6`, `k5r_A1.0`) | 7 | K5, 2.5 m/s rüzgârlı (ve rüzgârsız eşi), **iniş yok** |
| Aşama 5 (`a5_k1v1.0`, `a5_k2d0.35`) | 20 | algı bozucuları altında iniş: sınır, çevir, kayıp, gecikme, tekrar (W3) |

- **K1-K4 ve Aşama 5 "veri kipi"nde uçtu:**
  - VALIDATE'te referansı politika verir.
  - Gazebo'ya göre hedef yüksekliği 2.5 m'nin altına inince mod kendi
    COMMIT'ine devreder.
  - W5'te devir yok; politika 2.5 m altında 0.5 m/s ister.
- **Başarı:**
  - Eski ölçütle 195 bölüm başarılı.
  - **Birincil ölçütle (`basarili_v10`, temas < 1.0 m/s) 189.**
  - Kalan 23 başarısızlık beklenen: 19 tanımlama bölümü inmiyor,
    4 negatif örnek (W1 ×3, ada t2012) aday üretmiyor.
- **Dünyalar:**
  - sabit adalar W1-W8 (`src/eland_sim/worlds/veri/`);
  - tohumdan 45 rastgele ada (`veri_ada_tNNNN`, tam arşivde `dunyalar/`);
  - açık alan;
  - rüzgârlı eşler `_r2p5`.
- **Bölme:** train 140 / val 31 / test 47 bölüm.
  - Kararlı bir özetle (hash), anahtar düzeyinde: bir ada bütünüyle tek
    bölmede; diğer dünyalarda anahtar dünya + tohum.
  - Aynı başlangıç koşulu iki bölmeye düşmez.
  - K4 ve Aşama 5'te test yok.
- **COMMIT yasası:** 218 bölümün hepsi eski yasayla kaydedildi
  (`commit_irtifa_yasasi = false`). Varsayılan 2026-10-04'ten beri `true`
  ([`KONTROLCU_OLCUMLERI.md`](KONTROLCU_OLCUMLERI.md) §6.4).

---

## 3. Dosya yapısı

### `birlesik_<bölme>.mat` (MATLAB paketinde)

Dört yapı; alanlar sütun.

| Yapı | Satır | Ne |
|---|---|---|
| `ep` | bölüm başına 1 | bölüm tablosu, 30 alan (`tum_ozet.csv` ile aynı sütunlar). **Bütün alanlar metin:** MATLAB'da hücre dizisi; sayılar ve `True`/`False` dahil |
| `duzenli` | 50 Hz, bütün bölümler alt alta | 50 sayısal sütun (float32). `ep_idx` hangi bölüm olduğunu verir |
| `maske` | maske başına (~10 Hz) | 27 sütun: ρ, `view_bounded`, `rho_hesap`, `rho_temiz` / `rho_bozuk`, yakalama ve alma damgaları, kamera yüksekliği, bölge geometrisi |
| `karar` | iniş adayı başına (~1.8 Hz) | 13 sütun: `area_m2`, `area_ratio`, `view_bounded`, `radius_m`, `risk`, `gecerli`, konum |

**`ep_idx` sıfırdan başlar:** `ep_idx = k` olan satır `ep`'in `k+1`'inci
satırına (MATLAB) ait.

`duzenli`'nin ana sütunları:

| Grup | Sütunlar |
|---|---|
| zaman | `t_gz` (sim saati, s; 20 ms ızgara) |
| EKF (PX4) | `h_ekf`, `vz_ekf`, `x_ekf_kuzey`, `y_ekf_dogu`, `vx`, `vy` |
| Gazebo gerçeği | `h_gercek_zemin`, `h_gercek_hedef`, `vz_gercek_hesap`, `x_gercek`, `y_gercek` |
| tutum | `roll`, `pitch`, `yaw` (rad) |
| mod | `v_ref`, `v_cmd`, `durum`, `aktif_girdi`, `nav_state`, `I_hesap` (geri çatılmış integral) |
| politika (veri kipi) | `v_ref_dis` |
| PX4 iniş bayrakları | `landed`, `ground_contact` |
| yatay hata | `yatay_hata_m`, `yatay_hata_hedef_gercek_m` |

- **`_yas_ms` sütunları:** her sinyalin ızgara anındaki yaşı (son örnekten
  geçen süre).
- **Birimler:** m, m/s, aşağı pozitif hız.
- **Tam tanımlar:** `data_dictionary.md`.

### Bölüm klasörü (tam arşivde)

`eland_veri/<kol>/<dunya>/<ep_id>/`:
- `duzenli.csv`, `maske_olaylari.csv`, `karar_olaylari.csv`,
  `durum_gecisleri.csv`;
- `ep_ozet.json` (bölüm özeti), `kosul.yaml` (koşullar), `params.yaml`
  (koştuğu parametreler);
- `ep.mat` (aynı tablolar, tek bölüm), `maskeler.npz` (ham sınıf maskeleri);
- `run_sim.log`, `pipeline.log`, `kaydedici.log`.

---

## 4. MATLAB'da okuma

> MATLAB bu makinede yok. Aşağıdaki kod MATLAB'da denenmedi. Dosyaların
> yapısı (alan adları, tipler, uzunluklar) `scipy.io.loadmat` ile geri
> okunarak doğrulandı.

```matlab
S  = load('birlesik_train.mat');      % S.ep, S.duzenli, S.maske, S.karar
ep = S.ep;                            % her alan hücre dizisi (metin)
v_temas = str2double(ep.temas_dikey_hiz_gercek_hesap_mps);
basari  = strcmp(ep.basarili_v10, 'True');      % birincil başarı
fprintf('%d bolum, %d basarili (v<1.0)\n', numel(ep.ep_id), sum(basari));

d = S.duzenli;                        % 50 Hz, bütün bölümler alt alta
k = 0;                                % ep_idx 0 tabanlı -> ep satırı k+1
m = d.ep_idx == k;
t = d.t_gz(m);  h = d.h_gercek_zemin(m);  vz = d.vz_gercek_hesap(m);
vref = d.v_ref(m);  vcmd = d.v_cmd(m);
plot(t, vz, t, vref, t, vcmd); legend('vz gercek', 'v\_ref', 'v\_cmd');
title(ep.ep_id{k+1}, 'Interpreter', 'none');

mk = S.maske;  mm = mk.ep_idx == k;   % ayni bolumun maskeleri (~10 Hz)
rho = mk.rho(mm);  vb = mk.view_bounded(mm);  tc = mk.t_yakalama(mm);
```

## 5. Python'da okuma

```python
import scipy.io
S = scipy.io.loadmat('birlesik_train.mat', squeeze_me=True, struct_as_record=False)
ep, d = S['ep'], S['duzenli']
basari = ep.basarili_v10 == 'True'
k = 0
m = d.ep_idx == k
t, vz = d.t_gz[m], d.vz_gercek_hesap[m]
```

Kullanıcı dizininde numpy 2 ve sistemde eski scipy varsa çakışabilir. Bu
projedeki çözüm: `PYTHONPATH=/usr/lib/python3/dist-packages`.

---

## 6. Bilmen gerekenler (yanlış sonuca götürenler)

1. **`h_ekf` kalkış noktasına göre, hedef yüzeye göre değil.** Düz zeminde
   fark yok. W5'te (4 m platform) EKF temasta hedefin ~3.8-4.0 m üstünü
   gösteriyor. Hedefe göre gerçek yükseklik `h_gercek_hedef`.
2. **Temas anı `t_temas_gercek`** (`ep`), hızı
   `temas_dikey_hiz_gercek_hesap_mps`; ikisi de Gazebo'dan.
   - PX4 `landed` 3-5 s geç; mod arada aracı yerde itmeye devam ediyor.
   - **Analizleri `t_temas_gercek`'te kes.**
   - `kol0_veri_ada_t2010_t1`'de araç temastan 7.5 s sonra devrildi;
     temas sonrası kuyruk çöp.
3. **`area_m2` gerçek alan değil:** 40 × 40 m harita tavanıyla sınırlı
   (~1600 m²). Gerçek ada alanı dünya yaml'ında; `rho_hesap` onu kullanıyor.
4. **`duzenli.v_ref`, modun ~10 Hz durum kanalından tutulmuş değer.**
   - PI'ı yeniden oynatırken irtifa yedeğindeki `v_ref`'i
     `clamp(0.35·h_ekf, 0.3, v_tavan)` ile yeniden hesapla.
   - Bu yapılmadığında integral ±0.03 m/s'den iyi bilinemiyor
     (`tools/veri/pi_tekrar.py`).
5. **ρ yalnız `view_bounded = 1`'ken bilgi taşır.** Açık alanda ve geniş
   adalarda bölge kadraja sığmaz, ρ doyar (§4.2 `KONTROLCU_OLCUMLERI.md`).
6. **Maskeler Gazebo'nun kusursuz etiketi;** segmentasyon gürültüsü yok.
   Gürültülü sürümler için Aşama 5 bölümlerinde `rho_bozuk` /
   `view_bounded_bozuk` / `t_alma_bozuk`.
7. **Başarı ölçütü:** birincil `basarili_v10`.
   - W5'i yalnız 1.0 seviyesiyle değerlendir: veri kipinde 0.5 m/s ile
     indiği için 0.5 seviyesi gürültüyle bölünüyor.
   - Temas hızının ortancası ve en büyüğü ile birlikte raporla.
8. **İnmeyen ve beklenen başarısız bölümler:** K5/K5r inmiyor
   (`basarili = False` beklenen). Negatif örnekler `negatif_ornek = True`.
9. **Eski kaydedici sütunları:** Tur 1 kaydedicisiyle alınan bölümlerde (K5,
   açık alan Kol 0) sonradan eklenen sütunlar (`x_gercek` gibi) yok. Birleşik
   dosyada NaN.
10. **Açık alanın üç Kol 0 bölümü** (t1001-t1003) yüzey yükseklikleri
    tanımlanmadan kaydedildi. Yol/yama üstünde `h_gercek_*` 0.02 m fazla,
    bina/ağaç üstünden geçerken yanlış.
11. **`ep.yol` proje sahibinin makinesindeki mutlak yol**
    (`/home/arda/eland_veri/...`). Tam arşivi açtığın yere göre önekini
    değiştir.

---

## 7. Sürüm ve yeniden üretme

- **Bu sürüm:** Tur 2 toplaması (`v5.3-veri-tur2`) ve Tur 4'te eklenen
  sütunlar (`basarili_v05`, `basarili_v10`, `commit_irtifa_yasasi`). Tablolar
  2026-10-04 hâli.
- **Yeniden üretme:** `tools/veri/birlestir.py` bölüm klasörlerinden
  `tum_ozet.csv` ve `.mat`'ları kurar; araçlar
  [`../tools/veri/README.md`](../tools/veri/README.md).
- **Yeni veri toplanırsa:** yeni bir Release etiketiyle yayınlanacak; bu
  dosya güncellenecek.
