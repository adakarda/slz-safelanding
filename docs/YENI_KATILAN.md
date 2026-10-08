# Projeye yeni katılan için

> Bu projede bilgi kaynağın GitHub: dokümanlar, kod, sürüm etiketleri ve veri
> seti (Release). Bu dosya rolüne göre nereden başlayacağını, AI ajanınla
> nasıl çalışacağını ve katkının nasıl yapılacağını anlatır. Güncel:
> 2026-10-08.

---

## 0. Önce 5 dakika

[`../README.md`](../README.md): proje ne, şu an nerede, mimari.

Kısaca:
- **Ne:** simülasyonda bir İHA acil iniş sistemi. PX4'e kayıtlı uçuş modu;
  kameradan güvenli iniş yeri seçiyor ve iniyor.
- **İniş yeri seçimi çalışıyor.**
- **Asıl açık iş:** görüntüden ölçülen büyüklüklerle dikey iniş
  kontrolcüsü. Durumu:
  [`KONTROLCU_TASARIM_DURUMU.md`](KONTROLCU_TASARIM_DURUMU.md).

## 1. Rolüne göre başla

### A. Kontrolcü / MATLAB-Simulink / veri analizi

**Simülasyon kurman gerekmez.** Gereken: MATLAB (Simulink isteğe bağlı) ya
da Python + scipy.

1. [`KONTROLCU_TASARIM_DURUMU.md`](KONTROLCU_TASARIM_DURUMU.md): kim ne yapıyor,
   kararlar, sıradaki iş.
2. [`KONTROLCU_OLCUMLERI.md`](KONTROLCU_OLCUMLERI.md): tesis modeli,
   gecikmeler, ρ, EKF, temas hızı, bozucular. Bütün sayılar kaynağıyla.
3. [`KONTROLCU_TASARIM_BRIEF.md`](KONTROLCU_TASARIM_BRIEF.md): tasarım
   problemi, kısıtlar, açık sorular, beklenen çıktı biçimi (§12).
4. [`VERI_SETI.md`](VERI_SETI.md): veriyi indir.
   - `eland_veri_matlab_2026-10-04.zip`, 57 MB, MATLAB için yeterli.
   - Okuma örneği ve **§6'daki tuzaklar** orada.
5. Sütunların anlamı:
   [`../tools/veri/data_dictionary.md`](../tools/veri/data_dictionary.md).

### B. Simülasyon / ROS 2 / uçuş kodu

**Ortam** (proje sahibinin makinesi):

| | |
|---|---|
| İşletim sistemi | Windows 11 + WSL2 Ubuntu 24.04 |
| Yazılım | ROS 2 Jazzy, Gazebo Harmonic (gz-sim 8) |
| PX4-Autopilot | `f63b0d6b6f` |
| Donanım | 12 çekirdek, 11 GB RAM, GPU yok (yazılımla görüntüleme) |

- **Kurulum ve ilk koşu:** [`../README.md`](../README.md) "Hızlı başlangıç".
  Ayrıntılar [`DEVIR.md`](DEVIR.md) §6-§7 ve
  [`../src/README.md`](../src/README.md).
- **Önce oku:** [`../AGENTS.md`](../AGENTS.md).
  - Kurallar: plan ve onay; parametreli, varsayılan kapalı.
  - WSL tuzakları: `/tmp` siliniyor, CRLF, exec biti.
- **Beklenen ilk sonuç:** `./src/eland_sim/scripts/dene.sh otomatik` →
  `aday uretilmeyen 0/150`, `aday kaybi: 0`, tek denemede iniş.

### C. Tez / poster / doküman

- [`TEZ_NOTLARI.md`](TEZ_NOTLARI.md): savunulabilir sayılar.
- [`ARASTIRMA_KONTROL_SEGMENTASYON.md`](ARASTIRMA_KONTROL_SEGMENTASYON.md):
  literatür ve araştırma promptları.
- [`README.md`](README.md): bütün dokümanların haritası.

## 2. AI ajanınla çalışmak

- **Claude Code:** depoyu klonla, kök klasörde aç.
  - `CLAUDE.md`'yi kendisi okur; o da [`../AGENTS.md`](../AGENTS.md)'yi içe
    alır.
  - İlk mesaj önerisi: *"AGENTS.md ve docs/README.md'yi oku, sonra
    docs/KONTROLCU_TASARIM_DURUMU.md'yi özetle."*
- **Codex, Cursor ve benzerleri:** `AGENTS.md`'yi okur. Okumuyorsa ilk mesajda
  ona göster.
- **Depoyu göremeyen sohbet asistanları** (web'de ChatGPT, Gemini...): ilgili
  dosyaları yapıştır ya da ham bağlantısını ver:
  `https://raw.githubusercontent.com/adakarda/slz-safelanding/main/<dosya yolu>`.
  - Kontrolcü için en verimli üçlü: `docs/KONTROLCU_TASARIM_DURUMU.md`,
    `docs/KONTROLCU_OLCUMLERI.md`, `docs/KONTROLCU_TASARIM_BRIEF.md`.
  - Brif zaten bir sohbet asistanına verilmek için yazıldı; §14'te açılış
    mesajı var.
- **Ajanına hatırlat** (AGENTS.md §3):
  - Ölçmediğini "çalışıyor" diye yazmasın.
  - Mevcut uçuş kodunu onaysız değiştirmesin.
  - Sayıların kaynağını versin.

## 3. Katkı akışı

- **Kendi dalında çalış** (`git checkout -b ad/konu`), değişikliği **PR** ile
  öner.
- **Uçuş davranışını değiştiren her şey** (`src/`, `eland_params.yaml`) önce
  planla ve proje sahibinin onayıyla.
  - Yeni davranış parametreyle seçilir, varsayılanı kapalı.
  - Kapalıyken eski davranışın aynı kaldığı bir koşuyla gösterilir.
- **Yeni ölçüm ya da bulgu:** nereye yazılacağı [`README.md`](README.md) §3'te.
  Her sayının yanında nasıl ölçüldüğü ve etiketi: ölçülen / _hesap / _tahmin.
- **`main`'e birleştirme ve sürüm etiketleri** (`vX.Y-konu`) proje sahibinde
  (öneri).

## 4. Sık sorulanlar

| Soru | Cevap |
|---|---|
| Veri nerede? | GitHub Release [`v6.8-veri-seti`](https://github.com/adakarda/slz-safelanding/releases/tag/v6.8-veri-seti); açıklama [`VERI_SETI.md`](VERI_SETI.md) |
| Kontrolcü tasarımı nerede, ne durumda? | [`KONTROLCU_TASARIM_DURUMU.md`](KONTROLCU_TASARIM_DURUMU.md) |
| Simulink modeli nerede? | proje sahibinde; depoda değil |
| "Kol 0, K1-K5, Tur, W5, devir, ρ" ne? | [`../AGENTS.md`](../AGENTS.md) §6 sözlük |
| Dokümanlarda `~/eland_veri/...` diye yollar var, bende yok | proje sahibinin makinesindeki veri kökü. Release'deki tam arşivi ev dizinine açarsan aynı yollar sende de olur |
| Bir sayı iki dokümanda farklı | güncel olan `KONTROLCU_OLCUMLERI.md`'deki; eskileri orada "geçersiz" diye işaretli. Geri bildirim metinleri (`geri_bildirim/`) yazıldıkları anın fotoğrafı |
| Hangi sürüm çalışıyor? | her `vX.Y` etiketi; doküman düzenlemesinden önceki çalışan sürüm `yedek-calisan-2026-10-05` |
