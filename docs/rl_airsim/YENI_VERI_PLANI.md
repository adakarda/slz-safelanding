# v4 verisiyle yeni eğitim — plan ve şimdiye kadarki dersler

> **Tarih:** 2026-10-25. **Kim için:** Arda, Sefa ve bu işi devralan her AI ajanı.
> Sonuçların kaynağı [`../onkayit/rl_f0_onkayit.md`](../onkayit/rl_f0_onkayit.md) (Düzeltme 27–28) ve
> [`RAPOR.md`](RAPOR.md). Etiketler: **ölçülen**, **_hesap**, **_tahmin**.
> **Veri herkese açık bir yere konmaz** (VDD dağıtılamaz; MESSI CC BY-NC-SA). Depoda yalnız betikler ve sayılar var.

---

## 1. v4 veri paketi (ölçülen)

- `veri_v4.zip` (14.4 GB, SHA256 `dd019375…`) → `~/eland_veri/v4_zip/veri_v4/`. 4050 kare, hepsinde RGB + maske.
- Kaynaklar: FloodNet 1953, MESSI 1297, TU Graz 400, VDD 400. Bölümler `split_v4.json` (bölge ve uçuş bazında).
- Maskeler segmentasyon tarafında 8 sınıfa eşlenmiş (`masks8`): SORA 7 + `road`; belirsizler 252–254; 255 etiketsiz.
- Segmentasyon modeli v4: `best_v4.pth` (SegFormer-B3, SHA256 `d17d2771…`). Segmentasyon Arda'nın tarafı; RL
  tarafı modeli yalnız çalıştırır, değiştirmez.

### RL'ye çeviri (`~/rl_inis/v4/hazirla.py`)

| masks8 | RL sınıfı | Not |
|---|---|---|
| 0–6 | aynı | SORA 7 |
| 7 road | 2 terrain-hazard | README'deki gibi; yol inilemez |
| 252 çim ya da bitki (VDD) | 2 | temkinli |
| 253 su ya da yol (FloodNet) | 4 water | ikisi de inilemez |
| 254 sert zemin ya da yol (TU Graz) | 2 | temkinli |
| 255 etiketsiz | 7 unknown | |

- **Seçim:** yalnız ölçeği bilinen ve kameranın 20–30 m'de gördüğü alana yeten kareler (en az 60 × 45 m).
  - FloodNet: hepsi ~80 × 60 m, kullanıldı.
  - MESSI: eğitimin 365/700'ü yeterince büyük.
  - TU Graz: 5–30 m'den çekilmiş, sahne çok küçük; dışarıda.
  - VDD: irtifa ve ölçek bilinmiyor; dışarıda.
- Maske 8 cm/piksele örneklenir. Sonuç: **eğitim 1810** (FloodNet 1445 + MESSI 365), **doğrulama 175**, test 560.
- **Sınıf payları (eğitim):** FloodNet %58 çim, %15 su, %22 bitki/yol, sert zemin yok. MESSI %15 çim, %15 sert,
  %41 bitki/yol, %27 yapı. FloodNet eğitimin %80'i; sonuçlar kaynak başına ayrı raporlanır.
- Depth Anything V2 Small haritaları her sahne için hesaplanır (`da_v4.py`; tam görüntü, %5–%99.5 ölçekleme).

## 2. Dersler (yeni eğitimde uygulananlar)

- **Kalkan eğitimin içinde.** 30 s sınırı kalkansız kullanılınca politika çöktü (D, E, F). c13 tarifi kullanılır.
- **Ödül sırası:** yanlış yere inme cezası, süre aşımı cezasından ağır (`zemin_v3`: −60'a −50).
- **Hız ayarları:** yanal hız 1 m/s (H24); hızlı son iniş yok (H23).
- **Derinlik:** Depth Anything eğitimi kararlı yapıyor (H27: 3/3 tohum ≥ %89.8; düz zeminle 2/3 tohum çöktü).
- **Tohum:** karar en az 5 tohumla verilir. Tek model doğrulama setine bakılarak seçilmez.
- **Değerlendirme:** her deneme yeni bir `LandingEnv` ile. Paylaşılan ortam reset sonrası durum taşıyor (25.10).
- **Gimbal ve kilitli kalkan** değerlendirmede ve sahada açık; gimbal'la eğitim fayda vermedi (H25b, H26).
- **İşletim:**
  - Ortam: `env -u PYTHONPATH -u AMENT_PREFIX_PATH` + `ortam.sh`.
  - Aynı anda en çok 2 eğitim; 1810 sahne ~1.9 GB tutuyor (ölçülen).
  - Uzun tur donmuş kodla koşar (`~/rl_inis/v4/kod`).
  - Uyku tutucu açılır, kapak kapatılmaz.
  - WSL bir kez `HCS_E_CONNECTION_TIMEOUT` verdi; `wsl --shutdown` ile düzeldi.

## 3. Bilinen açıklar

- **Depth Anything eğitimde ve sahada farklı görüntüde çalışıyor:** eğitimde tam fotoğrafta, sahada kamera
  karesinde. Fark ölçülecek; büyükse eğitim kamera kırpıntılarıyla yeniden yapılır.
- **Segmentasyon hatası:** politika kusursuz etiketle eğitiliyor. Segmentasyon tarafındaki hata modeli
  (BASVURU_METINLERI: "kusursuz etiketi bozan modül") ikinci aşama eğitimde kullanılabilir.
- **AirSim:** segmentasyon (v4) ve Depth Anything canlı ve paralel çalışmalı; kilitli kalkan `policy_node`'a
  taşınmalı (Sefa).
- **FloodNet ağırlığı:** sel sahneleri kolay ve çimli. Politika kentsel sahnelerde (MESSI) zayıf kalırsa MESSI
  örneklemesi artırılır (yeni ön kayıtla).

## 4. Sıra

1. ✓ Envanter, sınıf çevirisi, sahneler, Depth Anything (25.10).
2. Düzeltme 28: c13 + Depth Anything, v4 eğitim, 5 tohum, 1M adım. Kıyas: eski son aday ve Düzeltme 27 modelleri,
   v4 doğrulamasında.
3. Depth Anything'in tam görüntü ↔ kamera karesi farkının ölçümü.
4. AirSim: v4 segmentasyonu + canlı Depth Anything + kilitli kalkan; Faz 8.
5. Son test (IrYamim / v4 test bölümü) yalnız Arda "koş" deyince.

## 5. Açık kararlar (Arda)

1. Belirsiz sınıfların temkinli çevirisi (yukarıdaki tablo) uygun mu?
2. VDD için ölçek bilgisi var mı? Varsa eğitim setine katılır.
3. Depth Anything ve v4 segmentasyonunun AirSim hattına eklenmesi için onay.
