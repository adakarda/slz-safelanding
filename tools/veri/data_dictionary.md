# Veri sözlüğü — iniş kayıtları

Kaydedici: `tools/veri/kaydedici.py`. Her iniş (ep) bir klasör:
`duzenli.csv`, `maske_olaylari.csv`, `karar_olaylari.csv`,
`durum_gecisleri.csv`, `ep_ozet.json`, `kosul.yaml`, `ep.mat`, `maskeler.npz`.

## Etiketler

- **ölçülen** — bir sensörden ya da simülatörden doğrudan okunan değer.
- **`_hesap`** — ölçülenlerden hesaplanan değer (türev, geri çatım, geometri).
- **`_tahmin`** — model ya da varsayım içeren değer.
- **`_yas_ms`** — o satırın zamanında, değerin dayandığı son mesajın yaşı (ms).
  Izgara 50 Hz'dir; daha yavaş gelen kanallarda değer tutulur ve yaşı büyür.

## Zaman ve çerçeveler

- **Zaman:** `t_gz` simülasyon saatidir (s, Gazebo `/world/<w>/clock`).
  ROS ve PX4 mesajları, kaydediciye ulaştıkları andaki sim saatiyle
  damgalanır (alma zamanı). Maske ve gerçek konum kendi yakalama
  damgalarını taşır.
- **PX4 yerel çerçevesi (EKF):** NED; x kuzey, y doğu, z aşağı. Orijin EKF
  orijinidir, yani kalkıştaki zemin noktası; altındaki zemin değildir.
- **Dünya çerçevesi (Gazebo):** ENU; x doğu, y kuzey, z yukarı.
- **İşaretler:** dikey hızlar **aşağı pozitif** (`vz_ekf`, `v_cmd`, `v_ref`,
  `vz_gercek_hesap`). Yükseklikler **yukarı pozitif** (`h_*`).

## duzenli.csv — 50 Hz ızgara

| Sütun | Birim | Kaynak | Not |
|---|---|---|---|
| ep_id, dunya_id, tohum, kol | — | koşul | |
| t_gz | s | ızgara | sim saati, 0.02 s adım |
| durum | — | `/eland/state.state` | 0 SEARCH, 1 APPROACH, 2 VALIDATE, 3 HOLD, 4 ABORT, 5 COMMIT; mod etkin değilken boş |
| nav_state | — | `/fmu/out/vehicle_status_v4` | 23 = acil iniş modu |
| h_ekf | m | `vehicle_local_position.z`, işareti çevrilmiş | **kalkış noktasına göre**, yere göre değil |
| vz_ekf | m/s | `vehicle_local_position.vz` | aşağı + |
| vx, vy | m/s | `vehicle_local_position` | NED kuzey / doğu |
| roll, pitch, yaw | rad | `vehicle_attitude.q` | FRD→NED, ZYX Euler |
| v_cmd | m/s | `/fmu/in/trajectory_setpoint.velocity[2]` | modun PX4'e verdiği dikey hız komutu, aşağı +. Yalnız VALIDATE/COMMIT'te ve 200 ms'den tazeyse dolu; mod iniş sonrası tamamlanınca boş |
| v_ref | m/s | `/eland/state.commanded_descent_mps` | alçalma yasasının referansı; durum ≤ 10 Hz yayınlanır |
| aktif_girdi | — | `/eland/state.area_law_active` | 1 alan oranı yasası, 0 irtifa yedeği |
| I_hesap | m/s | `v_cmd − v_ref − Kp·(v_ref − vz_ekf)` | **geri çatım**; yalnız VALIDATE'te ve çıkış doymamışken. Kp koşuldan |
| h_gercek_zemin | m | Gazebo model z − altındaki yüzeyin yüksekliği − dinlenme ofseti | yerdeyken 0 |
| h_gercek_hedef | m | Gazebo model z − hedef yüzeyin yüksekliği − dinlenme ofseti | açık alanda = h_gercek_zemin |
| vz_gercek_hesap | m/s | Gazebo z'nin türevi (`np.gradient`) | aşağı +; simülatör hız yayınlamıyor |
| landed, ground_contact | 0/1 | `/fmu/out/vehicle_land_detected` | PX4 iniş algılayıcısı; gerçek temastan 3-5 s geç (ölçülen), temas anı için kullanmayın |
| yatay_hata_m | m | EKF konumu ile o an yayınlanan son geçerli aday arası yatay mesafe | COMMIT'te mod hedefi dondurur; aday yayını sürer |
| yatay_hata_hedef_gercek_m | m | Gazebo konumu ile hedef yüzey merkezi | yalnız dünya yaml'ında hedef varsa |

Türetilmiş sütunların (`I_hesap`, `yatay_hata_*`) kendi yaş sütunu yoktur;
girdilerinin yaşlarına bakın.

## maske_olaylari.csv — maske başına (~10 Hz), ızgaraya yuvarlanmadan

| Sütun | Birim | Not |
|---|---|---|
| t_yakalama | s | maskenin başlık damgası = Gazebo'nun kareyi işlediği sim zamanı |
| t_alma | s | kaydediciye ulaştığı sim zamanı |
| maske_yasi_ms | ms | t_alma − t_yakalama |
| rho | — | görüntü merkezinin altındaki 8-bağlı güvenli bölgenin piksel payı (dedektörün `area_ratio` tanımı) |
| view_bounded | 0/1 | bölge hiçbir kare kenarına değmiyor |
| bolge_piksel | px | bölgenin piksel sayısı |
| ic_daire_yaricapi_px | px | bölgeye sığan en büyük daire; kare kenarı sınır sayılır |
| ic_daire_merkez_px | px | aynı mesafe, görüntü merkezinde |
| sinir_uzunlugu_px | px | bölgenin dış kontur uzunluğu, kare kenarı dahil |
| sinir_ic_piksel | px | bölge sınır pikselleri, kare kenarı hariç (başka sınıfa karşı) |
| merkez_x, merkez_y | px | bölge ağırlık merkezi (x sağa, y aşağı) |
| bbox_x0/x1/y0/y1 | px | bölgenin sınır kutusu |
| kenara_degen_taraf_sayisi | 0-4 | |
| sinif_siniri_piksel | px | bütün karede sınıf sınırı pikseli |
| merkez_sinif | — | görüntü merkezindeki pikselin sınıfı |
| h_kamera_gercek | m | yakalama anında kameranın altındaki yüzeye yüksekliği (model z + 0.10 m) |
| h_gercek_zemin | m | yakalama anında, duzenli.csv'deki tanım |
| rho_hesap | — | `A_gercek / (4.22 · h_kamera_gercek²)`; A_gercek dünya yaml'ından. Yalnız bölge kadraja sığarken anlamlı |

Görüntü: 320×240, yatay FOV 99.7°, üstü = aracın burnu. Ham maskeler
`maskeler.npz` içinde (`maskeler` N×240×320 uint8, `t_yakalama`, `t_alma`);
öznitelikler `tools/veri/ozellik.py` ile yeniden hesaplanabilir.

## karar_olaylari.csv — aday başına (~1.8 Hz)

`t_alma`, `t_damga` (adayın dayandığı haritanın damgası), `gecerli`,
`aday_id`, `x_yerel` / `y_yerel` (m, harita = PX4 yerel ENU), `radius_m`
(seçilen noktaya sığan daire), `area_m2` (40×40 m haritayla sınırlı), `area_ratio`,
`view_bounded`, `risk`, `secilen_nokta_hata_m` (adayın dünya konumu ile hedef yüzey
merkezi arası; yalnız hedefli dünyalarda).

## durum_gecisleri.csv

`t_gz`, `onceki`, `sonraki`, `neden` (modun yazdığı gerekçe).

## ep_ozet.json

| Alan | Not |
|---|---|
| t_mod_devrede | nav_state'in 23'e geçtiği an |
| t_validate, t_commit | ilk VALIDATE / COMMIT |
| t_px4_landed, t_px4_ground_contact | PX4 bayrağının 0→1 geçişi |
| t_temas_gercek | Gazebo yüksekliğinin ilk kez 0.03 m altına indiği an |
| temas_dikey_hiz_gercek_hesap_mps | temastan önceki 0.3 s'deki en büyük aşağı hız |
| ground_contact_gecikmesi_s, landed_gecikmesi_s | PX4 bayrağı − gerçek temas |
| commit_h_ekf_m, commit_h_gercek_hedef_m | COMMIT'e girerken iki irtifa |
| inis_suresi_mod_landed_s, alcalma_suresi_validate_landed_s | |
| abort_sayisi, hold_sayisi, abort_hold_nedenleri, kor_inis | |
| aday_kayip_* | mod etkinken 3 s'den uzun geçerli adaysız aralıklar |
| basarili, basari_olcutu, temas_yeri_uygun | landed + kör değil + temas yeri uygun (hedefli dünyada hedef yüzey, açık alanda temastan önceki maskede merkez inilebilir) |
| z_dinlenme_m, z_dinlenme_kaynak | model orijininin yerde dururkenki yüksekliği |
| yerel_dunya_ofset_en_m | dünya (doğu, kuzey) = ofset + yerel (doğu, kuzey); bölümün ortancası |
| sureklilik | kanal başına mesaj sayısı, hız, en uzun boşluk, jitter, kayıp tahmini |
| maske_damga_geri_gitme, clock_geri_gitme | zaman damgası geri gitme sayısı |

## ep.mat

MATLAB `load('ep.mat')`: `duzenli`, `maske`, `karar`, `gecis` yapıları
(sütunlar alan olarak) ve `ozet_json` (metin; `jsondecode` ile açılır).
Biçim v7 (sıkıştırılmış). Bu makinede MATLAB yok; dosya yalnızca
`scipy.io.loadmat` ile geri okunarak doğrulandı.
