# tools/veri/ — veri toplama araçları

Dikey iniş kontrolcüsü (MATLAB/Simulink) ve RL için kayıtlı iniş bölümleri
üretir.
- **Görev, kararlar, turlar:** [`../../docs/VERI_TOPLAMA.md`](../../docs/VERI_TOPLAMA.md).
- **Sütunların tanımı:** [`data_dictionary.md`](data_dictionary.md).
- **Mevcut koda dokunulmuyor:** mevcut düğümler yalnız parametreyle
  yönlendiriliyor (veri kipi `veri_toplama_kipi`, varsayılan kapalı).

---

## Tipik akış

```bash
cd ~/ros2_ws
# 1. (gerekirse) ada dünyası üret -> ~/eland_veri/dunyalar/
python3 tools/veri/dunya_uret.py ...

# 2. tek bölüm: sim aç, kaydet, in, kapat -> ~/eland_veri/<kol>/<dunya>/<ep_id>/
RUN_SIM_MOD_TEKRAR=2 tools/veri/kosu.sh TOHUM KOL DUNYA [node.param=değer ...]

# 3. çok bölüm: listeyi sırayla koş, günlük ~/eland_veri/_gunlukler/
setsid nohup tools/veri/toplu.sh tools/veri/listeler/LISTE.txt ~/eland_veri/_gunlukler/AD.log >/dev/null 2>&1 &

# 4. ara rapor, sonra veri setini kur
PYTHONPATH=/usr/lib/python3/dist-packages python3 tools/veri/adim_ozet.py ~/eland_veri/_gunlukler/AD.log
PYTHONPATH=/usr/lib/python3/dist-packages python3 tools/veri/birlestir.py
```

**Kurallar:**
- **Başka bir simülasyon açıksa başlatma.**
  - `run_sim.sh` makinedeki PX4/Gazebo'yu kapatır.
  - `kosu.sh` açık sim görürse reddeder; önce `pgrep -x px4; pgrep -x ruby`
    ile kendin bak.
- **Toplu listelerde her satır `RUN_SIM_MOD_TEKRAR=2` ile başlar** (Tur 4
  kararı). `run_sim.sh`'nin varsayılanı kapalı kalır.
- **Raporda:**
  - Yeniden deneme gereken koşuları say:
    `grep -l 'deneme [2-9])' <kok>/*/*/*/run_sim.log`.
  - Birincil başarı `basarili_v10`.
  - W5 yalnız 1.0 seviyesiyle değerlendirilir.
  - Temas hızının ortancası ve en büyüğü verilir.
- **Günlükleri `/tmp`'ye yazma:** WSL boşta kalınca dağıtımı yeniden başlatıp
  `/tmp`'yi siliyor. `toplu.sh` varsayılan olarak `~/eland_veri/_gunlukler/`'e
  yazar.

---

## Araçlar

### Koşu

| Araç | Ne yapar |
|---|---|
| `kosu.sh` | Bir kayıtlı bölüm: sim aç, kaydediciyi başlat, modu seç, temas bekle, kapat. Ortam: `POLITIKA`, `BOZUCU`, `MODEL`, `EP_EK`, `KAYIT_SURE`, `INIS_BEKLE`, `BASLANGIC_IRTIFA`, `DUGUM_BILGI`, `VERI_KOK` (başlıkta ayrıntı). Kendi başlattığı süreçleri işaretler, kapanışta artakalanları kapatıp `artik_surecler.txt`'ye yazar |
| `toplu.sh` | Liste dosyasını sırayla koşar (satır başına bir komut, `#` yorum); bölüm başına duvar süresi ve çıkış kodu |
| `zincir.sh` | Birkaç listeyi arka arkaya koşar; `--bekle PID` ile önce süren işin bitmesini bekler |
| `listeler/` | Koşulmuş listeler (adım ve tur adına göre). Yeni liste için örnek alınabilir, ama `RUN_SIM_MOD_TEKRAR=2` eklenmeli |

### Kayıt ve bölüm sonu

| Araç | Ne yapar |
|---|---|
| `kaydedici.py` | Bölüm kaydedici: yalnız dinler. Sim zamanıyla kaydeder, sonunda 50 Hz tablo kurar. Çıktılar: `duzenli.csv`, `maske_olaylari.csv`, `karar_olaylari.csv`, `durum_gecisleri.csv`, `rho_yayini.csv`, `ep_ozet.json`, `kosul.yaml`, `ep.mat`, `maskeler.npz` |
| `ozellik.py` | Görüntü-uzayı öznitelikleri: ρ, `view_bounded`, iç daire, sınır pikselleri (kaydedici ve analizler kullanır) |
| `dunya.py` | Dünya geometrisi: yüzey yükseklikleri, hedef yüzey (gerçek değerler için) |
| `basari.py` | Başarı seviyeleri: `basarili_v10` (birincil), `basarili_v05` |
| `ozet_yenile.py` | Kaydedicinin boş bıraktığı temas alanlarını sonradan doldurur (W1 kör inişleri) |
| `dogrula.py` | Kayıtlı bölümleri denetler: eksiksizlik, hizalama, temas; bölüm başına şekil |
| `adim_ozet.py` | Bir toplu adımın ara raporu (`toplu.sh` günlüğünden): kol × dünya başına başarı (birincil), süre, temas ortanca/en büyük, başarısızlık nedenleri, W5 sayıları |

### Dünyalar ve koşullar

| Araç | Ne yapar |
|---|---|
| `dunya_uret.py` | Ada dünyaları: sabit W1-W8 (`src/eland_sim/worlds/veri/`) ve tohumdan rastgele adalar (`~/eland_veri/dunyalar/`); rüzgârlı eşleri (`_r2p5`). `--ruzgar-olcek` etkin ölçek alır |
| `dunya_parametreleri.py` | Bir ada dünyasının istediği parametre geçersiz kılmaları (`make_params` argümanları) |
| `baslangic.py` | (dünya, tohum)'dan başlangıç koşulları; hedef dışına ya da yükseltilmiş yüzeye düşen başlangıcı yeniden çeker |
| `acik_alan_yuzey.py` | Mevcut açık alan dünyasının yüzey yükseklikleri |
| `ruzgar_modeli_uret.py` | `x500_seg_cam_down_ruzgar`: rüzgâr açık araç modeli (PX4 dosyalarına dokunmadan) |
| `politika.py` | Veri kipinin hız desenleri (K1 sabit hız, K2 kâhin sabit ıraksama, K3 rastgele, K4 basamak / çoklu sinüs). Gazebo hedef yüksekliği < 2.5 m'de moda devreder |
| `bozucu.py` | Maske ile sonrası arasına algı bozucuları (sınır, çevir, kayıp, gecikme, tekrar); tohumlu |

### Veri seti ve analizler

| Araç | Ne yapar |
|---|---|
| `birlestir.py` | Veri seti: `tum_ozet.csv`, tohum/ada anahtarlı 70/15/15 bölme, birleşik `.mat` (`_bolme/`) |
| `temas_puanla.py` | Bölümleri temas hızı seviyeleriyle yeniden puanlar ve raporlar (yeni koşu yok) |
| `tesis_analizi.py` | K5 kare dalgadan tesis tanımlama (K, θ, t90, ivme sınırı) |
| `ruzgar_karsilastir.py` | Rüzgârlı bölüm ile rüzgârsız eşi: eğim, yatay sapma |
| `pi_tekrar.py` | Modun PI'ını kayıtlı referans ve hızdan çevrimdışı yeniden oynatır, gönderilen komutla karşılaştırır |
| `zaman_hizasi.py` | Bir `ep.mat`'ın zaman hizası ve yapısı, MATLAB'ın göreceği gibi |
| `ornek_mat.py` | Küçük, temsilî MATLAB seti (bölüm başına bir `.mat` + kısa sözlük) |
| `egiklik_rho.py` | Eğiklik ve ρ: ölçülen ρ ile geometriden hesaplanan ρ (Tur 3 D) |
| `bozucu_dogrula.py` | Bozucular gerçekten uygulandı mı, sayılarla (Tur 3 C) |
| `tur3_dogrula.py`, `tur4_dogrula.py` | Tur 3 A/B ve Tur 4 madde 2 doğrulama tabloları |

---

## Veri kökü (`~/eland_veri/`)

- **Veri setinin kendisi deponun içinde değil,** GitHub Release
  [`v6.8-veri-seti`](https://github.com/adakarda/slz-safelanding/releases/tag/v6.8-veri-seti)'te
  ([`../../docs/VERI_SETI.md`](../../docs/VERI_SETI.md)).
- **Tam arşiv** (`eland_veri_bolumler_2026-10-04.zip`) ev dizinine açılınca bu
  düzen oluşur. Alt çizgili klasörler arşivde yok.

```
<kol>/<dunya>/<ep_id>/      bölüm klasörleri (veri seti; kol: kol0, k1_v1.0, k2_d0.35, k3_*, k4, k5_A*, ...)
tum_ozet.csv                bölüm başına bir satır
_bolme/{train,val,test}/    bağlantılar ve birlesik_<bölme>.mat
dunyalar/                   rastgele ada dünyaları (sdf + yaml)
_gunlukler/                 toplu koşu günlükleri
_*                          veri setine girmeyenler (doğrulama koşuları, karantina, raporlar)
```

Alt çizgili klasörlerin listesi: `data_dictionary.md`.
