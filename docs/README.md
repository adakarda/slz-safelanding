# Doküman haritası

> Bu klasörde ne var, hangi sırayla okunur, yeni bilgi nereye yazılır.
> Güncel: 2026-10-05.
>
> Uzun dosyaları (`DURUM.md` ~1800, `VERI_TOPLAMA.md` ~1500 satır) baştan
> sona okuma. Aşağıdaki bölüm dizinlerinden ilgili yere git.

---

## 1. Okuma sırası

Yeni gelen biri (insan ya da AI ajanı):

1. [`../README.md`](../README.md): proje ne, şu an nerede, nasıl çalıştırılır.
2. [`YENI_KATILAN.md`](YENI_KATILAN.md): rolüne göre başlangıç, AI ajanıyla
   çalışma, katkı akışı.
3. [`../AGENTS.md`](../AGENTS.md): çalışma kuralları. Ajanlar için zorunlu,
   insanlar için de geçerli.
4. Bu dosya: konuna göre aşağıdan seç.

| Konu | Önce | Sonra |
|---|---|---|
| Dikey iniş kontrolcüsü | [`KONTROLCU_TASARIM_DURUMU.md`](KONTROLCU_TASARIM_DURUMU.md), [`KONTROLCU_OLCUMLERI.md`](KONTROLCU_OLCUMLERI.md) | [`KONTROLCU_TASARIM_BRIEF.md`](KONTROLCU_TASARIM_BRIEF.md), [`TEZ_NOTLARI.md`](TEZ_NOTLARI.md) §2 |
| Veri setini kullanmak (MATLAB/Simulink, Python, RL) | [`VERI_SETI.md`](VERI_SETI.md) (indirme Release'ten) | [`../tools/veri/data_dictionary.md`](../tools/veri/data_dictionary.md) |
| Veri toplamak / nasıl toplandı | [`VERI_TOPLAMA.md`](VERI_TOPLAMA.md) (en son tur en altta) | [`../tools/veri/README.md`](../tools/veri/README.md) |
| Sistemi baştan anlamak | [`DEVIR.md`](DEVIR.md) | [`../src/README.md`](../src/README.md) |
| Ne yapıldı, ne bekliyor | [`YAPILACAKLAR.md`](YAPILACAKLAR.md) | `VERI_TOPLAMA.md`'nin son "Tur" bölümü |
| Algı, karar, harita, engeller | [`DURUM.md`](DURUM.md) (dizin §3) | [`TEZ_NOTLARI.md`](TEZ_NOTLARI.md) §3 |
| Tez / poster | [`TEZ_NOTLARI.md`](TEZ_NOTLARI.md) | [`ARASTIRMA_KONTROL_SEGMENTASYON.md`](ARASTIRMA_KONTROL_SEGMENTASYON.md) |

---

## 2. Dosyalar

### Giriş ve durum

| Dosya | Ne | Güncel mi |
|---|---|---|
| [`../README.md`](../README.md) | proje özeti, durum, çalıştırma, depo haritası | güncel |
| [`../AGENTS.md`](../AGENTS.md) | AI ajanları (ve insanlar) için çalışma kuralları, komutlar, tuzaklar | güncel |
| [`YENI_KATILAN.md`](YENI_KATILAN.md) | yeni katılan için: rolüne göre başlangıç, AI ajanıyla çalışma, katkı akışı, sık sorulanlar | güncel (2026-10-08) |
| [`DEVIR.md`](DEVIR.md) | tam devir: mimari, dört test, sınıflar, kontrol, kurulum, tuzaklar, Claude Code ile çalışma | 2026-09; mimari ve tuzaklar geçerli. **Bazı sayılar eski:** kamera 5 Hz yazıyor, artık 10 Hz; tesis ölü zamanı 0.3 s yazıyor, artık 0.04-0.08 s. Güncel sayılar `KONTROLCU_OLCUMLERI.md`'de |
| [`YAPILACAKLAR.md`](YAPILACAKLAR.md) | isterler ↔ yapılanlar, açık maddeler, karar bekleyenler | başında 2026-10-08 güncel durum bölümü; asıl değerlendirme 2026-09-26 |
| [`OZET.md`](OZET.md) | 2026-09-03/04 oturumunun bir sayfalık özeti | tarihsel |

### Kontrol

| Dosya | Ne | Güncel mi |
|---|---|---|
| [`KONTROLCU_TASARIM_DURUMU.md`](KONTROLCU_TASARIM_DURUMU.md) | **kontrolcü işi nerede:** kim tasarlıyor, Tur 1-4 kararları, kodda bugün hangi parametre ne, açık işler, katkı | güncel (2026-10-08) |
| [`KONTROLCU_OLCUMLERI.md`](KONTROLCU_OLCUMLERI.md) | **kontrolcü için ölçülmüş her şey tek yerde:** tesis, iç döngü, alçalma ve COMMIT yasaları, sinyal hızları ve gecikmeler, ρ, EKF, temas hızı, bozucular, reddedilenler | güncel (2026-10-05) |
| [`KONTROLCU_TASARIM_BRIEF.md`](KONTROLCU_TASARIM_BRIEF.md) | görüntü-tabanlı dikey iniş kontrolcüsü tasarım brifi; tasarımı yapan sohbet asistanına verilmek için yazıldı (§14 açılış mesajı, §12 beklenen çıktı biçimi) | 2026-10-02; §7 tesis 2026-10-03'te güncellendi |
| [`TEZ_NOTLARI.md`](TEZ_NOTLARI.md) | teze/postere girecek savunulabilir sayılar ve gerekçeler | §2 kontrol, §3 karar döngüsü, §4 yöntem |

### Mühendislik günlüğü — `DURUM.md`

İş paketi başına bir bölüm: ne yapıldı, ölçümler, açık maddeler.
Veri toplama dönemi (2026-10-03 sonrası) burada değil, `VERI_TOPLAMA.md`'de.

| Bölüm | Konu |
|---|---|
| §1-§11 | bir bakışta, ortam ve sürüm pinleri, paketler, karar mantığı, doğrulanmış ölçümler (§6), tuzaklar (§7), açık kusurlar, hızlı referans |
| §12 | dinamik engeller ve yörünge-farkında karar (dördüncü test) |
| §13 | teleoperasyon: kendi kendine iniş ve devralmanın geri alınması |
| §14 | rastgele başlangıç konumu |
| §15 | daha fazla sınıf, daha fazla engel |
| §16 | teleoperasyon: kök neden ve önceki teşhisin düzeltilmesi |
| §17 | sınırlı sayıda, rastgele konumlu çoklu mob |
| §18 | SORA taksonomisi: sim ile modelin aynı sınıf uzayı |
| §19 | karar döngüsü: profil, darboğaz ve asıl kusur |
| §20 | veto değil fiyat: dördüncü katmanın yeniden düzenlenmesi |
| §21 | sınıf dikişi ve HUD |
| §22 | kontrol tarafı: kapalı çevrim, kazanç türetimi, bozucu (özet; ayrıntı `TEZ_NOTLARI.md` §2) |
| §23 | rastgele doğuş, HUD hızı, izleyici penceresi |
| §24 | WSL saati, kapanış hijyeni, HUD 10 Hz (§24.3 gecikme tablosu), koridor genişliği |

### Veri seti — `VERI_SETI.md`

[`VERI_SETI.md`](VERI_SETI.md): 218 bölümlük veri setinin kullanım kılavuzu.
- **İndirme:** GitHub Release `v6.8-veri-seti`.
- **İçerik:** dosya yapısı, MATLAB ve Python'da okuma, yanlış sonuca götüren
  tuzaklar.

### Veri toplama — `VERI_TOPLAMA.md`

Kontrolcü tasarımı (MATLAB/Simulink) ve RL için kayıtlı iniş verisinin nasıl
toplandığı.

| Bölüm | Konu |
|---|---|
| baş | görev, kollar (Kol 0, K1-K5), ek bulgular (E1-E9), Aşama 1 kaydedici, uçan doğrulama, kararlar, Aşama 2 dünyalar, K5 tesis testi |
| Tur 2 | kararlar, doğrulamalar, uçuşsuz işler, onaylı kod değişiklikleri |
| Tur 2 — yürütme | sızan süreç olayı, Adım 1-7 (Kol 0, K1, K2, K5 rüzgârlı, K4, bozucular, K3), veri seti (218 bölüm) |
| Tur 3 | C bozucu doğrulaması, D eğiklik ve ρ, E örnek MATLAB seti, A `/eland/rho` ve B COMMIT irtifa yasası |
| Tur 4 | temas hızıyla başarı ölçütü, `commit_irtifa_yasasi` varsayılanı, kararlar, mod seçme yeniden denemesi |

- Veri dosyalarının sütunları:
  [`../tools/veri/data_dictionary.md`](../tools/veri/data_dictionary.md).
- **Veri deponun içinde değil,** Release'te. Dokümanlardaki `~/eland_veri/...`
  yolları proje sahibinin makinesindeki kök; Release'teki tam arşiv ev
  dizinine açılınca aynısı oluşur.

### Diğer sohbetle yazışma — `geri_bildirim/`

Kontrolcü, proje sahibinin ayrı bir sohbetinde (Simulink) tasarlanıyor.
- Buradaki metinler o sohbete giden promptlar; o sohbetin kararları
  `VERI_TOPLAMA.md`'de kayıtlı.
- **Her metin yazıldığı anın fotoğrafı.** Güncel sayılar
  `KONTROLCU_OLCUMLERI.md`'de.

| Sıra | Dosya | Etiket | İçerik |
|---|---|---|---|
| 1 | [`VERI_TOPLAMA_GERI_BILDIRIM.md`](geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM.md) | `v4.9` | veri toplama görevi nerede (Tur 1) |
| 2 | [`VERI_TOPLAMA_RAPOR_TUR2.md`](geri_bildirim/VERI_TOPLAMA_RAPOR_TUR2.md) | `v5.3` | Tur 2 sonuç raporu |
| 3 | [`VERI_TOPLAMA_GERI_BILDIRIM_TUR2.md`](geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR2.md) | `v5.4` | Tur 2: veri toplandı, kontrolcü için elindekiler |
| 4 | [`VERI_TOPLAMA_GERI_BILDIRIM_TUR3.md`](geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR3.md) | `v5.6` | Tur 3 eksikleri: yapılanlar ve planlar |
| 5 | [`VERI_TOPLAMA_GERI_BILDIRIM_TUR3_SONUC.md`](geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR3_SONUC.md) | `v5.8` | Tur 3 sonuç: A ve B doğrulandı |
| 6 | [`VERI_TOPLAMA_GERI_BILDIRIM_TUR3_AYRINTILI.md`](geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR3_AYRINTILI.md) | `v5.9` | Tur 3'ün tamamı, ayrıntılı |
| 7 | [`VERI_TOPLAMA_GERI_BILDIRIM_TUR4.md`](geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR4.md) | `v6.2` | Tur 4 ara: temas hızı ölçütü, varsayılan değişikliği |
| 8 | [`VERI_TOPLAMA_GERI_BILDIRIM_TUR4_SONUC.md`](geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR4_SONUC.md) | `v6.4` | Tur 4 sonuç: 48 bölümlük doğrulama, kararlar 1-4 |
| 9 | [`VERI_TOPLAMA_GERI_BILDIRIM_TUR4_EK.md`](geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TUR4_EK.md) | `v6.6` | mod seçme kontrolü ve yeniden deneme |

2026-10-05'e kadar `docs/` kökündeydiler. Etiketli GitHub bağlantıları
(`.../blob/v6.2.../docs/VERI_TOPLAMA_...`) eski yerle çalışmaya devam eder.

### Plan, gereksinim, araştırma

| Dosya | Ne | Güncel mi |
|---|---|---|
| [`PLAN.md`](PLAN.md) | geçiş ve uygulama planı, fazlar, tasarım kararları (K1-K14) | 2026-09-03; tarihsel gerekçe kaynağı |
| [`CHECKLIST.md`](CHECKLIST.md) | gereksinim checklist'i, uyumluluk değerlendirmesi | 2026-09-01 |
| [`ISTEKLER_2026-09-04.md`](ISTEKLER_2026-09-04.md) | danışman / kullanıcı istekleri ve karşılıkları | kaynak ister; `YAPILACAKLAR.md` buna atıf veriyor |
| [`ARASTIRMA_KONTROL_SEGMENTASYON.md`](ARASTIRMA_KONTROL_SEGMENTASYON.md) | segmentasyon eğitimi ve görüntü-tabanlı iniş kontrolü: araştırma notu ve promptlar | 2026-09-25 |

### Kod yanındaki dokümanlar

| Dosya | Ne |
|---|---|
| [`../src/README.md`](../src/README.md) | paketler, kurulum, çalıştırma (`run_sim.sh`, `dene.sh`), HUD, failsafe politikası, ayar noktaları |
| [`../tools/README.md`](../tools/README.md) | ölçüm ve analiz araçları dizini |
| [`../tools/veri/README.md`](../tools/veri/README.md) | veri toplama araçları dizini ve tipik akış |
| [`../tools/veri/data_dictionary.md`](../tools/veri/data_dictionary.md) | kayıt dosyaları, `ep_ozet.json`, `tum_ozet.csv` sütunları |
| `../src/eland_sim/config/eland_params.yaml` | bütün düğüm parametreleri, yorumlu (yasa, kazançlar, eşikler) |

---

## 3. Nereye ne yazılır

| Yeni bilgi | Yeri |
|---|---|
| Kontrolcüyle ilgili yeni ölçüm | `KONTROLCU_OLCUMLERI.md` (özet + kaynak), ayrıntısı kendi dokümanında |
| Veri toplama işi, yeni tur | `VERI_TOPLAMA.md`'ye yeni "Tur N" bölümü, en alta |
| Diğer sohbete gidecek prompt | `geri_bildirim/VERI_TOPLAMA_GERI_BILDIRIM_TURn[_SONUC\|_EK].md` |
| Algı / karar / sistem mühendisliği | `DURUM.md`'ye yeni bölüm (§25 ...) |
| Teze girecek sayı | `TEZ_NOTLARI.md` |
| Yeni araç | `../tools/README.md` ya da `../tools/veri/README.md`'ye bir satır |
| Kayda sütun ekleyen değişiklik | `../tools/veri/data_dictionary.md` |
| Varsayılanı değişen parametre | `eland_params.yaml` yorumu ve ilgili doküman ("varsayılan değişti" açıkça) |

**Biçim:**
- Her sayının yanında nasıl ölçüldüğü.
- Etiket: **ölçülen** / **_hesap** / **_tahmin**.
- Kodu ya da veriyi değiştiren her iş commit edilir, sürüm etiketi alır
  (`vX.Y-konu`) ve push'lanır; kurallar [`../AGENTS.md`](../AGENTS.md).
