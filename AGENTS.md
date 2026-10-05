# AGENTS.md — bu depoda çalışan AI ajanları (ve insanlar) için

Claude Code, Codex, Cursor, Copilot ya da başka bir ajanla bu depoda
çalışıyorsan önce bunu oku. `CLAUDE.md` bu dosyayı içe alır.
- **Kurallar** proje sahibinin talimatı.
- **Tuzaklar** bu projede gerçekten yaşandı ve ölçüldü.

---

## 1. Proje, 60 saniyede

- **Ne:** İHA acil iniş sistemi, lisans bitirme tezi. Tamamen simülasyonda:
  PX4 v1.17 SITL + Gazebo Harmonic + ROS 2 Jazzy, WSL2 Ubuntu.
- **Nasıl:**
  - PX4'e kayıtlı bir uçuş modu var (`src/eland_mode`, C++, Return'ün
    yerine).
  - Aşağı bakan segmentasyon kameradan harita kurar.
  - Dört testle iniş yeri seçer; dördüncüsü hareketli engellerin gideceği
    yer.
  - Kapalı çevrim dikey hız kontrolüyle iner.
- **Şu anki ana iş:** görüntü-tabanlı dikey iniş kontrolcüsü.
  - Proje sahibi bunu ayrı bir sohbette (MATLAB/Simulink) tasarlıyor.
  - Bu depo ona ölçüm ve kayıtlı veri sağlıyor (`tools/veri/`,
    218 bölüm).
  - O sohbetin kararları `docs/VERI_TOPLAMA.md`'de "Tur N" bölümlerinde.
- **Proje sahibi:** @adakarda.

## 2. Önce ne oku

1. `README.md`: durum, mimari, çalıştırma.
2. `docs/README.md`: bütün dokümanların haritası. Uzun dosyalar için bölüm
   dizini var.
3. Göreve göre:
   - **kontrol:** `docs/KONTROLCU_OLCUMLERI.md`;
   - **veri:** `docs/VERI_TOPLAMA.md` (son tur en altta) ve
     `tools/veri/README.md`;
   - **sistem:** `docs/DEVIR.md`.

**`docs/DURUM.md` (~1800 satır) ve `docs/VERI_TOPLAMA.md` (~1500 satır)
baştan sona okunmaz.** Dizinden bölümü bul, ara (grep), sadece o kısmı oku.

---

## 3. Kesin kurallar

1. **Önce plan, sonra onay, sonra uygulama.** Mevcut koda ya da yapılandırmaya
   dokunan her değişiklikten önce yaz:
   - ne yapacağını,
   - hangi dosyaları değiştireceğini.

   Kapsam: `src/`, `tools/`'daki çalışan araçlar, `eland_params.yaml`.
   Onaysız kod değiştirme. Yalnız yeni dosya ekleyen çevrimdışı analizler
   (yeni bir betik, rapor) bunun dışında.
2. **Mevcut uçuş akışını değiştirme.**
   - Yeni davranış bir parametreyle seçilir: ROS parametresi, ortam
     değişkeni ya da seçenek.
   - **Varsayılanı kapalı.**
   - Kapalıyken davranışın **bire bir eskisi gibi** olduğunu **bir koşuyla
     göster**.
   - Örnek yöntem: yeni koşunun `run_sim.log`'u ile eski koşununki, sayılar
     silinince `diff` boş.
3. **Varsayılan davranış değişiyorsa açıkça yaz:** commit mesajında
   ("VARSAYILAN DAVRANIŞ DEĞİŞTİ"), dokümanda ve raporda.
   - Örnek: `commit_irtifa_yasasi` `v6.1`'de `true` oldu.
   - Düğümün kendi varsayılanı `false` kaldı, yaml'da `true`.
4. **Ölçmediğini ya da koşmadığını "yapıldı / çalışıyor" diye yazma.**
   - Her sonucun yanında nasıl doğrulandığı.
   - Etiketler: **ölçülen** (koşuldu), **_hesap** (formül/geometri),
     **_tahmin** (varsayım).
   - Bir şey ölçülemediyse "ölçülmedi" de.
5. **Tek koşu kanıt değil.**
   - Aynı ayar koşudan koşuya değişiyor; örneğin APPROACH'a girilip
     girilmemesi.
   - Sınır bölgesinde tek koşu işaretin kendisini bile yanlış verdi.
   - Karşılaştırmayı eşli koşularla ve tekrarla yap.
6. **Sormadan dokunma:**
   - segmentasyon / algı zinciri (`eland_perception`);
   - araç hız kestirimi (`tracker_node` LSQ penceresi);
   - PX4 parametreleri. Bu makinede `MPC_Z_V_AUTO_DN = 2.0`; bugünkü
     hâliyle kalıyor.
7. **Sürüm disiplini:** biten her modül commit, ardından annotated tag ve
   push.
   - Tag biçimi `vX.Y-kisa-konu`, mesajında manşet ölçüm.
   - Yalnız küçük doküman düzeltmeleri etiket almaz.
   - Commit mesajı **ne ve neden**, sayıyla.
   - Son etiket: `git describe --tags`.
8. **Gizli bilgi depoya girmez:** token, şifre, anahtar. Bir dosyada görürsen
   commit'leme, kullanıcıya söyle.
9. **Veri raporları** (Tur 4 kararları):
   - birincil başarı `basarili_v10` (temas < 1.0 m/s);
   - `basarili`'nin anlamı değişmez;
   - W5 yalnız 1.0 seviyesiyle değerlendirilir;
   - temas hızının ortancası ve en büyüğü her zaman verilir;
   - toplu koşu listelerinde her satır `RUN_SIM_MOD_TEKRAR=2` ile başlar;
   - raporda yeniden deneme gereken koşular sayılır:
     `grep -l 'deneme [2-9])' <kok>/*/*/*/run_sim.log`.

---

## 4. Ortam ve komutlar

| | |
|---|---|
| Çalışma alanı | `~/ros2_ws` (WSL2 Ubuntu). Windows'tan `\\wsl.localhost\ubuntu\home\<kullanıcı>\ros2_ws` |
| PX4 | `~/PX4-Autopilot`, commit `f63b0d6b6f` (`v1.17.0-alpha1-1670`). `px4_msgs` ve `px4-ros2-interface-lib` `dependencies.repos`'ta sabit; üçü birlikte yükseltilir, ayrı ayrı değil |
| Veri | `~/eland_veri/` (GitHub'da değil) |

```bash
# derleme
source /opt/ros/jazzy/setup.bash && cd ~/ros2_ws && colcon build && source install/setup.bash
colcon build --packages-select eland_mode        # yalnız bir paket

# simülasyon
./src/eland_sim/scripts/dene.sh otomatik         # kipler: hud, otomatik, toplu, ruzgar, tanim, olcum
./src/eland_sim/scripts/run_sim.sh --headless --auto [--params DOSYA] [--world veri_w3]
python3 tools/make_params.py /tmp/p.yaml node.param=değer     # koşu başına parametre dosyası

# veri
RUN_SIM_MOD_TEKRAR=2 tools/veri/kosu.sh TOHUM KOL DUNYA [node.param=değer ...]
setsid nohup tools/veri/toplu.sh LISTE ~/eland_veri/_gunlukler/AD.log >/dev/null 2>&1 &
PYTHONPATH=/usr/lib/python3/dist-packages python3 tools/veri/birlestir.py
```

- **Sim başlatmadan önce açık bir sim var mı bak:** `pgrep -x px4; pgrep -x ruby`.
  `run_sim.sh` makinedeki PX4/Gazebo'yu kapatır. Başkasının oturumu açıksa
  sor. `kosu.sh` açık sim görünce reddeder.
- **Parametreler:** `src/eland_sim/config/eland_params.yaml`, yorumlu.
  - `make_params.py` ve `kosu.sh` **kaynaktaki** yaml'ı okur.
  - Etkileşimli `run_sim.sh` (`--params`'sız) **kurulu** kopyayı okur.
  - Yaml'ı değiştirince: `colcon build --packages-select eland_sim`.
- **Kurulum gerekmeyenler:** `src/eland_sim/scripts/` ve `tools/`
  kaynaktan çalışır.
- **Günlükler:**
  - `/tmp/eland_logs/` her koşuda üzerine yazılır.
  - Kayıtlı bölüm klasörü kendi kopyalarını tutar (`run_sim.log`,
    `pipeline.log`, `px4.log`).

---

## 5. Tuzaklar (hepsi yaşandı)

**Ortam (WSL):**
- **`/tmp` silinir.** WSL boşta kalınca dağıtımı yeniden başlatıyor. Kalıcı
  dosyayı ve toplu koşu günlüğünü `/tmp`'ye yazma; `~/eland_veri/_gunlukler/`
  kullan.
- **Windows tarafından düzenlemenin iki yan etkisi:**
  - CRLF satır sonu: bash betiği çalışmaz.
  - Çalıştırma izni (exec biti) düşer.
  - Düzenledikten sonra `sed -i 's/\r$//'` ve `chmod +x`. İzni
    `git ls-files -s` ile karşılaştır.
- **`wsl.exe` komut satırındaki `$DEĞİŞKEN`leri ve döngüleri bozar.**
  Windows'tan çağırırken komutları bir betik dosyasına yaz, onu çalıştır.
- **`pkill -f AD`, komut satırında AD geçen çağıran kabuğu da öldürür.** Süreç
  adlarını betiğin içine yaz.
- **Saat zıplaması:** `systemd-timesyncd` ile Hyper-V saati çekişince ROS
  zamanlayıcıları ~5 s duruyor. Süre ölçümünde `time.monotonic()` kullan.
- **numpy 2 / scipy çakışması:** kullanıcı dizinindeki numpy 2, sistem
  scipy'siyle çakışıyor. scipy kullanan betiklerde
  `PYTHONPATH=/usr/lib/python3/dist-packages`.
- **PX4 portları:** iki koşu arasında ~8-10 s bekle.

**Simülasyon ve ölçüm:**
- **Mod komutu kaybolabilir** (Tur 4'te 2/48). `run_sim.sh`'nin tek
  best-effort komutu bazen tutmuyor; mod kayıtlı, araç havada, `nav_state` 23
  olmuyor. Toplu listelerde `RUN_SIM_MOD_TEKRAR=2`.
- **Sızan düğümler:** betikle durdurulan koşuda `tracker_node` /
  `obstacle_driver` sağ kalıyordu; birikince EKF bozuldu.
  - `run_sim.sh` bunları artık kapatıyor (`v6.3`).
  - `kosu.sh`'nin işaretli temizliği yedek olarak duruyor.
  - Uzun koşudan sonra yine `ps` ile bak.
- **PX4 `landed` bayrağı gerçek temastan 3-5 s geç.** Temas anı ve hızı
  Gazebo'dan alınır.
- **Var olmayan bir şeye yayın yapmak hata vermez.** Örneğin Gazebo model
  adı PX4'te `_0` ekiyle (`x500_seg_cam_down_0`). Bir bozucu deneyinde önce
  bozucunun gerçekten uygulandığını ölç.
- **Varsayılan değişince karşılaştırma kollarının betikleri de değişmeli.**
  Eski kol yoksa sessizce yeni varsayılanı ölçer.

---

## 6. Sözlük (karışan terimler)

| Terim | Anlam |
|---|---|
| **Kol 0, K1-K5** (veri) | veri toplama kolları. Kol 0: modun kendi yasası. K1 sabit hız, K2 kâhin sabit ıraksama, K3 rastgele, K4 40 m basamak/çoklu sinüs, K5 tesis tanımlama (kare dalga), K5r rüzgârlı K5 |
| **Karar K1-K5** | `VERI_TOPLAMA.md`'nin 2026-10-03 karar tablosu (ada çevresi sınıfı, rüzgâr, PX4 parametreleri...). Kollarla aynı adı taşır, ayrı şeylerdir |
| **K1-K14** (`PLAN.md`) | ilk fazların mimari kararları |
| **O1-O3** | veri toplama için mevcut koda eklemelerin onay maddeleri (`VERI_TOPLAMA.md` "Onay bekleyenler"). O1 `run_sim.sh`'ye dünya/model seçimi, O2 modda veri toplama kipi, O3 K5 tesis testi. O1 ve O2 verildi, O2b verilmedi |
| **Tur N** | kontrolcüyü tasarlayan sohbetle bir alışveriş turu: istek, yapılan, rapor (`docs/geri_bildirim/`) |
| **W1-W8** | sabit ada dünyaları (`src/eland_sim/worlds/veri/`). W1 negatif (aday yok), W5 4 m yüksek platform |
| **`veri_ada_tNNNN`** | tohumdan rastgele ada dünyası (`~/eland_veri/dunyalar/`) |
| **`_r2p5`** | 2.5 m/s rüzgârlı eş dünya |
| **SEARCH / APPROACH / VALIDATE / HOLD / ABORT / COMMIT** | modun durumları. VALIDATE = adayın üstünde alçalma (kontrolcünün fazı), COMMIT = son 2 m, geri dönüşsüz |
| **ρ (rho), `view_bounded`** | kapsama oranı: görüntü merkezinin altındaki güvenli bölgenin piksel payı; bölge kadraj kenarına değmiyorsa `view_bounded` |
| **D, ıraksama** | `v/h` [1/s]; ρ̇/ρ = 2D (bölge kadraja sığarken) |
| **v_tavan** | alçalma hızı tavanı, `clamp(0.20·√A, 0.3, 1.5)` |
| **devir** | veri kipinde politikanın moda bıraktığı an (Gazebo hedef yüksekliği < 2.5 m) |
| **diğer sohbet** | proje sahibinin kontrolcü tasarım sohbeti; kararlar oradan gelir |

---

## 7. Nereye ne yazılır

Tablo: `docs/README.md` §3. Kısaca:
- kontrolcü ölçümü → `docs/KONTROLCU_OLCUMLERI.md`;
- veri işi → `docs/VERI_TOPLAMA.md` yeni tur;
- sistem işi → `docs/DURUM.md` yeni bölüm;
- yeni araç → `tools/README.md` ya da `tools/veri/README.md`;
- yeni sütun → `tools/veri/data_dictionary.md`.

## 8. Yedek ve geri dönüş

- **Her `vX.Y` etiketi çalışan bir durum.** `git checkout <etiket>`.
- **Doküman düzenlemesinden önceki çalışan sürüm:** etiket ve dal
  `yedek-calisan-2026-10-05` / `yedek/calisan-2026-10-05`.
- **Proje sahibinin makinesinde ayrıca yedek:** `~/yedekler/`. İçinde
  kaynak, kurulu derleme, git paketi, PX4 yerel değişiklikleri.
