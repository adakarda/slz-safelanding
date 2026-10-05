# Geri bildirim (Tur 4, sonuç) — madde 2'nin doğrulaması ve Tur 4 kararlarının uygulanması

> **Bu metin ne:** iki parça.
> - **A. Madde 2'nin doğrulaması tamamlandı** (§1-§4): `commit_irtifa_yasasi`
>   varsayılanı `true`, Kol 0'da açık ve kapalı yan yana, 48 bölüm.
> - **B. Tur 4 kararları uygulandı** (§5-§7):
>   1. Birincil ölçüt `basarili_v10`; `basarili` yeniden tanımlanmadı.
>      Raporlarda temas hızının ortancası ve en büyüğü var.
>   2. W5 yalnız 1.0 seviyesiyle değerlendiriliyor; veri olduğu gibi, yeni
>      koşu yok.
>   3. `tum_ozet.csv`'de `commit_irtifa_yasasi` sütunu.
>   4. `run_sim.sh` temizliğinde `tracker_node` ve `obstacle_driver`:
>      **varsayılan davranış değişti** (§7).
>
> 3 ve 4, istediğin gibi 48 bölüm bittikten sonra uygulandı; koşular sürerken
> o araçlara dokunulmadı.
>
> - **Tarih:** 2026-10-04.
> - **Kod (açık depo):** <https://github.com/adakarda/slz-safelanding>.
>   - Madde 2'nin değişikliği, koşu listesi ve doğrulama betiği:
>     [`v6.1-commit-irtifa-varsayilan`](https://github.com/adakarda/slz-safelanding/tree/v6.1-commit-irtifa-varsayilan).
>   - Kararlar 1-4 ve madde 2'nin sonuç tabloları: etiket
>     [`v6.3-tur4-kararlar`](https://github.com/adakarda/slz-safelanding/tree/v6.3-tur4-kararlar).
>   - Önceki ara metin:
>     [`v6.2-veri-geri-bildirim-tur4`](https://github.com/adakarda/slz-safelanding/blob/v6.2-veri-geri-bildirim-tur4/docs/VERI_TOPLAMA_GERI_BILDIRIM_TUR4.md).
>   - Bütün tablolar: `docs/VERI_TOPLAMA.md`, "Tur 4".
> - **Veri GitHub'da değil:** koşular `~/eland_veri/_tur4_dogrulama/`, tablo
>   `~/eland_veri/_tur4/tur4_dogrula.md`.
> - **Etiketler:** **ölçülen**, **_hesap**, **_tahmin**.

---

## 0. Kısa sonuç

**Madde 2 (48 bölüm, ölçülen):**

| Ayar | Bölüm | Temas ortanca | En büyük | v ≥ 1.0 | **Başarılı, v < 1.0 (birincil)** | v ≥ 0.5 (W5 dışı 21) | Başarılı, v < 0.5 (W5 dışı 21) | Başarılı (eski) |
|---|---|---|---|---|---|---|---|---|
| kapalı (`false`) | 24 | 0.31 m/s | 1.49 m/s (W5) | 3 (W5 ×3) | **21** | 0 | 21 | 24 |
| açık (`true`, yaml varsayılanı) | 24 | 0.31 | 1.48 (W5) | 3 (W5 ×3) | **21** | 0 | 21 | 24 |

- **Ayar gerçekten uygulandı:** `params.yaml`'a göre kapalı 24/24 `false`,
  açık 24/24 `true`.
- **Bu 24 Kol 0 koşulunda iki ayar aynı komutu verdi:**
  - COMMIT'te alan yasası 48 bölümün hiçbirinde çalışmadı. Pay her bölümde 0;
    W5'te COMMIT'e hiç girilmiyor.
  - Temastan önceki komut her bölümde 0.30 m/s.
  - Ayarın uçuşu değiştirdiği yer erken COMMIT. Orada Tur 3'te ölçülmüştü:
    1.20 → 0.30 m/s.
- **W5 dışında temas** (21 + 21 bölüm): kapalıda 0.30-0.36, açıkta
  0.26-0.496 m/s.
- **Tek aykırı değer kestiriciden:** açık W6 t1, 0.496 m/s (§3).
  - Komut 0.30 m/s, ama son 0.6 s'de EKF iniş hızı 0.27 m/s iken gerçek
    ~0.49 m/s (+0.22 m/s).
  - EKF yüksekliği temastan 0.1 s önce +0.14 m fazla.
  - W5 dışındaki diğer 41 bölümde bu fark −0.06 ile +0.03 m/s arasında.
- **W5:** iki ayarda da 3/3 sert temas, 1.47-1.49 m/s, COMMIT yok. Ara
  metindeki beklentiyle (_tahmin) aynı, şimdi ölçülen.
- **Durum dizisi farkları COMMIT'ten önce, yani ayardan değil:**
  - Kapalı ile açık 24 koşulun 14'ünde aynı.
  - Kapalı ile veri seti (ikisi de eski yasa) yalnız 10'unda aynı. Fark,
    aynı yasayla iki koşu arasında daha da büyük.
  - Farklar APPROACH'a girilip girilmemesi ve adalarda SEARCH ↔ APPROACH
    tekrarları.
- **2 bölüm yeniden uçuruldu** (mod komutu kayboldu, §1).

**Kararlar 1-4:** uygulandı ve doğrulandı (§5-§7).
- 218 bölüm birincil ölçütle (v < 1.0): 195'in 189'u başarılı.
- `tum_ozet.csv`'de `commit_irtifa_yasasi` 218/218 `false`.
- `run_sim.sh` artık iki düğümü de kapatıyor; iki koşuyla gösterildi (§7).

---

## 1. Yöntem (madde 2)

- **Değişiklik:** `eland_params.yaml`'da `commit_irtifa_yasasi: true`. Kod
  değişmedi. Varsayılan davranış değişikliğinin tarifi ara metnin §0'ında.
- **24 koşul:**
  - W2-W6 × tohum 1-3 (15).
  - Dokuz pozitif ada (t2003-t2011) × tohum 1 (9).
  - Veri setindeki Kol 0 koşulları. W1 ve t2012 negatif örnek olduğu için
    dışarıda.
- **Koşul başına iki bölüm,** arka arkaya:
  - kapalı: `emergency_landing_mode.commit_irtifa_yasasi=false` (eski yasa);
  - açık: geçersiz kılma yok, yaml varsayılanı (`true`) sınanıyor.
- **Liste:**
  [`tools/veri/listeler/tur4_kol0_commit.txt`](https://github.com/adakarda/slz-safelanding/blob/v6.1-commit-irtifa-varsayilan/tools/veri/listeler/tur4_kol0_commit.txt).
- **Tablo:** `tools/veri/tur4_dogrula.py`.
  - Her bölümün gerçekten koştuğu değer klasöründeki `params.yaml`'dan
    okunuyor, listeye güvenilmiyor.
  - COMMIT'teki alan yasası payı ve temastan önceki komut 50 Hz tablodan
    (Tur 3'teki `commit_profili()`).
  - Başarı: `basari.py` (madde 4).
- **Temas hızı:** Gazebo yüksekliğinin dinlenme yüksekliğine 3 cm'den çok
  yaklaştığı ilk andan önceki 0.3 s'deki en büyük aşağı hız (**ölçülen**).
- **Yeniden uçurulan 2 bölüm:** açık W6 t2 ve kapalı ada t2006 t1.
  - İkisinde de mod PX4'e kaydoldu ve araç kalktı. Ama `run_sim.sh`'nin mod
    seçme komutu sonuçsuz kaldı: `nav_state` 23'e geçmedi, kayıt 240 s boş.
  - Mod devreye girmediği için parametreyle ilgisi yok.
  - Her biri bir kez yeniden uçuruldu, ikisi de indi. İlk denemeler
    `_tur4_dogrulama/_basarisiz/` altında.
- **Koşuların kullandığı dosyalar baştan sona aynı.**
  - Koşular sürerken atılan commit'ler yalnız çalışma ağacında zaten olan
    değişiklikleri kaydetti.
  - Bu yüzden `kosul.yaml`'daki `git` alanı bölümden bölüme farklı etiket
    gösteriyor.
  - Kararlar 3 ve 4'teki araçlara (`birlestir.py`, `run_sim.sh`) 48 bölüm
    bitene kadar dokunulmadı.

---

## 2. Ayar ve dünya başına (ölçülen)

| Dünya | Ayar | Bölüm | Temas ortanca (m/s) | En büyük (m/s) | v ≥ 1.0 | **Başarılı, v < 1.0** | v ≥ 0.5 | Başarılı, v < 0.5 | Başarılı (eski) |
|---|---|---|---|---|---|---|---|---|---|
| W2 | kapalı | 3 | 0.31 | 0.31 | 0 | **3** | 0 | 3 | 3 |
| W2 | açık | 3 | 0.30 | 0.31 | 0 | **3** | 0 | 3 | 3 |
| W3 | kapalı | 3 | 0.30 | 0.32 | 0 | **3** | 0 | 3 | 3 |
| W3 | açık | 3 | 0.30 | 0.31 | 0 | **3** | 0 | 3 | 3 |
| W4 | kapalı | 3 | 0.30 | 0.31 | 0 | **3** | 0 | 3 | 3 |
| W4 | açık | 3 | 0.30 | 0.31 | 0 | **3** | 0 | 3 | 3 |
| W5 | kapalı | 3 | 1.48 | 1.49 | 3 | **0** | uygulanmaz | uygulanmaz | 3 |
| W5 | açık | 3 | 1.48 | 1.48 | 3 | **0** | uygulanmaz | uygulanmaz | 3 |
| W6 | kapalı | 3 | 0.31 | 0.31 | 0 | **3** | 0 | 3 | 3 |
| W6 | açık | 3 | 0.30 | 0.496 | 0 | **3** | 0 | 3 | 3 |
| 9 ada | kapalı | 9 | 0.31 | 0.36 | 0 | **9** | 0 | 9 | 9 |
| 9 ada | açık | 9 | 0.31 | 0.31 | 0 | **9** | 0 | 9 | 9 |
| **tümü** | kapalı | 24 | 0.31 | 1.49 | 3 | **21** | 0 / 21 (W5 dışı) | 21 / 21 (W5 dışı) | 24 |
| **tümü** | açık | 24 | 0.31 | 1.48 | 3 | **21** | 0 / 21 (W5 dışı) | 21 / 21 (W5 dışı) | 24 |

- W6 açığın en büyüğü 0.496 m/s: 0.5'in altında, sert temas sayılmadı.
- "Başarılı (eski)" 24/24: W5'in üç sert teması eski ölçütle başarılı
  sayılıyordu.

---

## 3. Koşul başına, yan yana (kapalı / açık)

**W5 dışındaki 21 koşulun hepsinde, iki ayarda da:**
- COMMIT'te alan yasası payı 0.
- Temastan önceki komut 0.30 m/s.

W5'te COMMIT'e girilmedi.

| Koşul | Temas kapalı / açık (m/s) | COMMIT h_gerçek kapalı / açık (m) | Başarılı, v < 1.0 | Durum dizisi |
|---|---|---|---|---|
| W2 t1 | 0.31 / 0.29 | 1.99 / 2.03 | evet / evet | aynı |
| W2 t2 | 0.31 / 0.31 | 2.08 / 2.05 | evet / evet | farklı |
| W2 t3 | 0.30 / 0.30 | 2.05 / 2.10 | evet / evet | farklı |
| W3 t1 | 0.30 / 0.31 | 2.05 / 2.08 | evet / evet | aynı |
| W3 t2 | 0.32 / 0.27 | 2.05 / 2.12 | evet / evet | aynı |
| W3 t3 | 0.30 / 0.30 | 2.00 / 2.12 | evet / evet | aynı |
| W4 t1 | 0.31 / 0.31 | 2.08 / 2.06 | evet / evet | aynı |
| W4 t2 | 0.30 / 0.30 | 2.10 / 2.03 | evet / evet | aynı |
| W4 t3 | 0.30 / 0.29 | 2.06 / 2.00 | evet / evet | aynı |
| W5 t1 | 1.48 / 1.48 | COMMIT yok | hayır / hayır | aynı |
| W5 t2 | 1.48 / 1.47 | COMMIT yok | hayır / hayır | aynı |
| W5 t3 | 1.49 / 1.48 | COMMIT yok | hayır / hayır | aynı |
| W6 t1 | 0.30 / **0.496** | 2.07 / 2.10 | evet / evet | farklı |
| W6 t2 | 0.31 / 0.30 | 2.06 / 2.09 | evet / evet | farklı |
| W6 t3 | 0.31 / 0.30 | 2.07 / 1.98 | evet / evet | aynı |
| ada t2003 | 0.31 / 0.31 | 2.01 / 2.04 | evet / evet | farklı |
| ada t2004 | 0.30 / 0.31 | 2.06 / 2.05 | evet / evet | farklı |
| ada t2005 | 0.30 / 0.26 | 2.03 / 2.20 | evet / evet | farklı |
| ada t2006 | 0.31 / 0.30 | 2.02 / 2.12 | evet / evet | farklı |
| ada t2007 | 0.31 / 0.31 | 2.09 / 2.01 | evet / evet | aynı |
| ada t2008 | 0.30 / 0.30 | 2.04 / 2.00 | evet / evet | farklı |
| ada t2009 | 0.33 / 0.31 | 2.02 / 2.04 | evet / evet | aynı |
| ada t2010 | 0.30 / 0.31 | 2.09 / 2.06 | evet / evet | aynı |
| ada t2011 | 0.36 / 0.31 | 2.04 / 2.06 | evet / evet | farklı |

- **Durum dizisi** 24 koşulun 14'ünde aynı. Farklı olanların hepsi
  COMMIT'ten önce: APPROACH'a girilip girilmemesi, adalarda SEARCH ↔
  APPROACH tekrarları, bir yerde HOLD. Tam diziler
  `~/eland_veri/_tur4/tur4_dogrula.md`'de.
- **Açık W6 t1, 0.496 m/s** (bölümün 50 Hz tablosu):
  - Komut sona kadar 0.30 m/s.
  - Gerçek iniş hızı son ~1 s'de 0.37'den 0.50'ye çıktı.
  - EKF'nin dikey hızı aynı aralıkta ortalama 0.27 m/s (son 0.6 s).
  - EKF yüksekliği temastan 0.1 s önce gerçeğin 0.135 m üstünde.
  - Yani kontrolcü EKF'ye göre 0.30'u izledi, EKF gerçeği eksik gördü.
  - **Kestiriciyle temas arasındaki fark, 42 bölüm** (W5 hariç), son 0.6 s:

    | | `vz_gerçek − vz_ekf` | `h_ekf − h_gerçek` (temastan 0.1 s önce) |
    |---|---|---|
    | ortanca | +0.01 m/s | 0.00 m |
    | aralık | −0.06 ile +0.03 m/s (W6 t1 açık: +0.22) | −0.17 ile +0.06 m (W6 t1 açık: +0.14) |

  - İki ayar burada aynı komutu verdiği için bu sapma ayardan değil. Gözlemci
    tasarımın için yer yakınında EKF hatası örneği olarak işine yarayabilir.

---

## 4. Kapalı, veri setindeki aynı koşulla

Kapalı koşular eski yasayla uçtu. Veri setindeki aynı koşul da eski kodla
(parametre yokken) kaydedilmişti.

| Koşul | Durum dizisi | Temas veri seti / kapalı (m/s) |
|---|---|---|
| W2 t1 / t2 / t3 | aynı / aynı / aynı | 0.31 / 0.31, 0.30 / 0.31, 0.30 / 0.30 |
| W3 t1 / t2 / t3 | aynı / farklı / aynı | 0.30 / 0.30, 0.30 / 0.32, 0.31 / 0.30 |
| W4 t1 / t2 / t3 | farklı / aynı / farklı | 0.31 / 0.31, 0.31 / 0.30, 0.29 / 0.30 |
| W5 t1 / t2 / t3 | aynı / aynı / aynı | 1.47 / 1.48, 1.47 / 1.48, 1.48 / 1.49 |
| W6 t1 / t2 / t3 | farklı / farklı / aynı | 0.30 / 0.30, 0.28 / 0.31, 0.30 / 0.31 |
| 9 ada | 9'unda farklı | en büyük fark t2011: 0.30 / 0.36; diğerleri ≤ 0.02 |

- **Durum dizisi:** 24 koşulun 10'unda aynı.
  - Aynı yasayla iki koşu, kapalı ile açıktan (14/24) daha sık ayrışıyor.
  - Yani §3'teki farklar ayardan değil, koşudan koşuya değişkenlik.
- **Temas hızı:** iki koşu arasındaki fark ≤ 0.06 m/s. W5 iki koşuda da
  1.47-1.49 m/s.

---

## 5. Karar 1 ve 2 — birincil ölçüt `basarili_v10`, W5 yalnız 1.0

**Veri değişmedi.**
- `basarili`, `basarili_v10`, `basarili_v05` alanları ve `tum_ozet.csv`
  aynı.
- Değişen yalnız raporlar: üç rapor betiği ve bu metin.

**Raporlar artık şöyle:**
- **Birincil sütun** "başarılı, v < 1.0 (birincil)", ilk başarı sütunu.
- **Temas hızının ortancası ve en büyüğü** her tabloda.
- **W5'te 0.5 seviyesi "uygulanmaz".** Toplamlarda 0.5 seviyesi W5 dışındaki
  bölümlerden sayılıyor.
- **Değişen betikler:**
  - `tools/veri/temas_puanla.py`: yeniden puanlama raporu.
  - `tools/veri/tur4_dogrula.py`: bu metnin tabloları.
  - `tools/veri/adim_ozet.py`: toplu koşu ara raporu.
    - Başarılı / başarısız artık `basarili_v10`'a göre.
    - Eski ölçüt ayrı sütunda.
    - Sert teması başarısızlık nedeni olarak yazıyor.
    - Kol 0 günlüğüyle denendi: W5 ×3 "sert temas 1.47-1.48 m/s".

**Mevcut 218 bölüm, yeni kurallarla** (`temas_puanla.py`, yeni koşu yok):

| | Bölüm | Temas ortanca | En büyük | v ≥ 1.0 | **Başarılı, v < 1.0 (birincil)** | W5 dışı bölüm | v ≥ 0.5 (W5 dışı) | Başarılı, v < 0.5 (W5 dışı) | Başarılı (eski) |
|---|---|---|---|---|---|---|---|---|---|
| K5/K5r ve negatifler hariç | 195 | 0.30 m/s | 1.48 m/s | 6 | **189** | 174 | 3 | 171 | 195 |

- **Birincil ölçütten düşen 6 bölüm:**
  - Kol 0 W5 ×3: 1.47-1.48 m/s, COMMIT'e hiç girilmedi.
  - K3 ×3: erken COMMIT, 1.10-1.33 m/s.
- **0.5 seviyesi (W5 dışı):** yalnız bu üç K3 bölümü düşüyor.
- **W5'te 0.5 uygulanmıyor.** Uygulansaydı ayrıca 6 W5 veri kipi bölümü
  düşerdi (0.501-0.507 m/s).

---

## 6. Karar 3 — `tum_ozet.csv`'de `commit_irtifa_yasasi`

**Ne:**
- `tum_ozet.csv`'ye ve `birlesik_*.mat`'in `ep` yapısına
  `commit_irtifa_yasasi` sütunu eklendi. Koşul sütunlarının yanında
  (`bozucu`'dan sonra).
- **Değer:** bölüm klasöründeki `params.yaml`'dan
  (`emergency_landing_mode.ros__parameters.commit_irtifa_yasasi`). Dosya ya da
  anahtar yoksa `false`, istediğin gibi.

**Varsayılan davranış:** `tum_ozet.csv`'ye yalnız bir sütun eklendi, diğer
sütunlar aynı.

**Doğrulama (ölçülen):**
- **Yedek:** önce `~/eland_veri/_tur4/tum_ozet_madde3oncesi.csv` alındı.
- **`birlestir.py` yeniden:** 218 satır, aynı bölümler, eski sütunlarda 0
  fark, bölme aynı (140 / 31 / 47).
- **Yeni sütun:** 218/218 `false`.
  - 218 bölümün hepsinin `params.yaml`'ı var.
  - Hiçbiri yeni yasayla uçmadı; hepsi parametreden önce kaydedildi.
- **Sütunu dolduran fonksiyon,** değerin bilindiği koşularda:
  - Tur 4 kapalı 24/24 `false`, açık 24/24 `true`.
  - `params.yaml` olmayan klasör: `false`.
- **`birlesik_val.mat`'in `ep` yapısında** alan var (`scipy.io.loadmat` ile
  okundu).

---

## 7. Karar 4 — `run_sim.sh` temizliği: varsayılan davranış değişti

**Varsayılan davranış değişti.** `run_sim.sh` kapanırken (`cleanup()`, EXIT /
INT / TERM'de) artık `tracker_node` ve `obstacle_driver`'ı da adıyla
kapatıyor (`pkill -x`).
- **Eski davranış:** `RUN_SIM_ESKI_TEMIZLIK=1`. Yardım metninde yazıyor.
- **Uçuşa dokunmuyor:** yalnız kapanışta çalışıyor.
- **Neden:** Tur 2'deki olay. Betikle durdurulan koşularda bu iki düğüm sağ
  kalıyordu. Bir toplu koşuda 64 çift birikti; EKF dikey hızı 1 m/s'ye kadar
  saptı, mod DDS keşfinde zaman aşımına düştü.
- **Kimi etkiler:** etkileşimli `run_sim.sh` kullanımı ve `kosu.sh` koşuları.
  - `kosu.sh` bunları zaten kendi işaretiyle temizliyordu; o temizlik yedek
    olarak duruyor, yorumu güncellendi.
- **Bilinen sınır:** kapatma adla. Aynı makinede başka bir oturumun bu iki
  düğümü varsa onlar da kapanır.
  - `run_sim.sh` diğer düğümler için de zaten böyle yapıyordu.
  - `kosu.sh` başka simülasyon varken başlamıyor.
- **Kurulum gerekmiyor:** `run_sim.sh` kaynaktan çalışıyor.

**Doğrulama (ölçülen):** iki Kol 0 koşusu, W2 tohum 1. Ölçüt: `kosu.sh`'nin,
`run_sim.sh` kapandıktan sonra hâlâ yaşayan süreçleri yazdığı
`artik_surecler.txt`.

| Ayar | `artik_surecler.txt` (pid, ad) | Bölüm |
|---|---|---|
| yeni varsayılan | `1280 python3` | indi, temas 0.30 m/s |
| `RUN_SIM_ESKI_TEMIZLIK=1` | `2666 python3`, `2784 tracker_node`, `2786 obstacle_driver` | indi, temas 0.30 m/s |

- **Yeni temizlikte** iki düğüm `run_sim.sh` kapanırken kapandı.
- **Eski ayarla** ikisi de kaldı (önceki davranış), onları `kosu.sh` kapattı.
- **Kalan `python3`** ros2 daemon'u (`ros2 ...` komutlarının başlattığı); bu
  karar dışında, `kosu.sh` kapatıyor.
- **İki koşudan sonra** makinede `tracker_node` / `obstacle_driver` sayısı
  0 / 0.
- Koşular `~/eland_veri/_tur4_dogrulama/temizlik/{yeni,eski}/`; günlük
  `_gunlukler/tur4_temizlik.log`.

---

## 8. Kod

### 8.1 `run_sim.sh` — karar 4

[`src/eland_sim/scripts/run_sim.sh`](https://github.com/adakarda/slz-safelanding/blob/v6.3-tur4-kararlar/src/eland_sim/scripts/run_sim.sh),
`cleanup()` (kurulmuyor, `colcon build` gerekmiyor):

```diff
 	pkill -x image_bridge 2>/dev/null
+	# tracker_node and obstacle_driver too: they outlived script-stopped runs
+	# and piled up (64 pairs over one batch, 2026-10-03) until the EKF
+	# vertical velocity drifted. RUN_SIM_ESKI_TEMIZLIK=1 leaves them running,
+	# as before 2026-10-04.
+	if [ "${RUN_SIM_ESKI_TEMIZLIK:-0}" != 1 ]; then
+		pkill -x tracker_node 2>/dev/null
+		pkill -x obstacle_driver 2>/dev/null
+	fi
 	pkill emergency_land 2>/dev/null
```

Yardım metnine:

```diff
   -h, --help
+
+Environment:
+  RUN_SIM_ESKI_TEMIZLIK=1  on exit, leave tracker_node and obstacle_driver
+                     running (the cleanup before 2026-10-04)
```

`tools/veri/kosu.sh`: yalnız yorum güncellendi. İşaretli artık süreç
temizliği yedek olarak duruyor.

### 8.2 `birlestir.py` — karar 3

[`tools/veri/birlestir.py`](https://github.com/adakarda/slz-safelanding/blob/v6.3-tur4-kararlar/tools/veri/birlestir.py)

```diff
-             'ruzgar_mps', 'politika', 'bozucu', 'basarili', 'basarili_v05',
-             'basarili_v10', 'temas_yeri_uygun',
+             'ruzgar_mps', 'politika', 'bozucu', 'commit_irtifa_yasasi', 'basarili',
+             'basarili_v05', 'basarili_v10', 'temas_yeri_uygun',
```

```python
def commit_yasasi(ep_dir):
    """commit_irtifa_yasasi the episode flew with, from its params.yaml; false
    when the file or the key is missing (recorded before the parameter
    existed, i.e. the old law)."""
    path = os.path.join(ep_dir, 'params.yaml')
    if not os.path.exists(path):
        return False
    doc = yaml.safe_load(open(path)) or {}
    mod = (doc.get('emergency_landing_mode') or {}).get('ros__parameters') or {}
    return bool(mod.get('commit_irtifa_yasasi', False))
```

Satırda: `'commit_irtifa_yasasi': commit_yasasi(ep_dir),`.

### 8.3 Rapor betikleri — kararlar 1 ve 2

Veri ve başarı alanları değişmedi; yalnız raporların sütunları:
- [`tools/veri/temas_puanla.py`](https://github.com/adakarda/slz-safelanding/blob/v6.3-tur4-kararlar/tools/veri/temas_puanla.py)
- [`tools/veri/tur4_dogrula.py`](https://github.com/adakarda/slz-safelanding/blob/v6.3-tur4-kararlar/tools/veri/tur4_dogrula.py)
- [`tools/veri/adim_ozet.py`](https://github.com/adakarda/slz-safelanding/blob/v6.3-tur4-kararlar/tools/veri/adim_ozet.py)

Hepsinde ortak kural:

```python
# basarili_v10 is the primary criterion and W5 is judged at the 1.0
# level only (Tur 4 decisions): the 0.5 columns count the other worlds.
r05 = [r for r in rows if not r['w5']]
```

`adim_ozet.py` başarılı / başarısızı `basari.temas_seviyeleri(oz)['basarili_v10']`
ile ayırıyor. Başarısızlık nedenlerine şunu ekledi:

```python
v_t = oz.get('temas_dikey_hiz_gercek_hesap_mps')
if oz.get('basarili') and v_t is not None and v_t >= 1.0:
    why.append(f'sert temas {v_t:.2f} m/s (v >= 1.0)')
```

---

## 9. Açık konular

1. **Madde 1:** modun `/eland/rho`'yu kullanacağı maddeyi Simulink
   doğrulamasından sonra bekliyorum.
2. **W5 / yükseltilmiş hedef** (gözlemcinin test senaryosu). Elimdeki
   ölçülenler:
   - Kol 0 W5'te iki ayarda da COMMIT'e girilmiyor, temas 1.47-1.49 m/s (§2).
   - Temastan hemen önce `h_ekf − h_gercek_hedef` 3.81-3.87 m, `v_ref`
     1.40-1.45 m/s (veri setindeki Kol 0 W5 ×3, `adim_ozet.py`).
3. **Mod komutunun kaybolması:** bu turda 48 koşunun 2'sinde oldu (§1).
   - Mod PX4'e kaydoldu, araç kalktı, ama `run_sim.sh`'nin mod seçme komutu
     sonuçsuz kaldı (`nav_state` 23'e geçmedi).
   - Tur 2 ve 3'te de görülmüştü. Şimdiye kadar yeniden uçurarak geçtim.
   - İstersen `run_sim.sh`'nin mod seçme adımına "seçildi mi" kontrolü ve bir
     yeniden deneme ekleyebilirim (parametreli). Onay bekliyor.
