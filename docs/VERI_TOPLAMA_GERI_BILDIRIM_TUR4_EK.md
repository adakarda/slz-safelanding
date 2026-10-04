# Geri bildirim (Tur 4 ek) — mod seçme adımına kontrol ve yeniden deneme

> **Bu metin ne:** onayladığın ek madde uygulandı ve doğrulandı.
> `run_sim.sh`'nin mod seçme adımına "seçildi mi" kontrolü ve yeniden deneme
> eklendi; parametreli, **varsayılan kapalı**. Kapalıyken eski davranış bir
> koşuyla gösterildi.
>
> - **Tarih:** 2026-10-04.
> - **Kod (açık depo):** etiket
>   [`v6.5-mod-secim-tekrar`](https://github.com/adakarda/slz-safelanding/tree/v6.5-mod-secim-tekrar),
>   dosya
>   [`src/eland_sim/scripts/run_sim.sh`](https://github.com/adakarda/slz-safelanding/blob/v6.5-mod-secim-tekrar/src/eland_sim/scripts/run_sim.sh).
>   Kayıt: `docs/VERI_TOPLAMA.md`, "Tur 4 ek".
> - **Veri GitHub'da değil:** koşular `~/eland_veri/_tur4_dogrulama/mod_secim/`.

---

## 1. Sorun ve değişiklik

**Sorun:** `--auto`'da mod tek bir best-effort komutla seçiliyordu
(`ros2 topic pub -1`) ve sonucu kontrol edilmiyordu.
- Bu komut Tur 4'te 48 koşunun 2'sinde kayboldu. Mod PX4'e kaydolmuş, araç
  kalkmıştı, ama `nav_state` 23'e geçmedi.
- Tur 2 ve 3'te de görülmüştü.

**Değişiklik** (yalnız `run_sim.sh`; kurulum gerekmiyor):
- **`RUN_SIM_MOD_TEKRAR=N`**, ortam değişkeni. **Varsayılan: yok ya da 0 =
  kapalı.**
  - Komut bir kez gönderilir, kontrol yok. Eskisiyle bire bir aynı: aynı
    komut, yalnız bir işleve taşındı.
- **Açıkken:**
  - Komuttan sonra `px4-listener vehicle_status` ile `nav_state` 0.5 s
    arayla 5 s izlenir.
  - 23 görülürse `mod secildi (nav_state 23, deneme k)` yazılır.
  - Görülmezse `mod secilmedi (nav_state X, deneme k)` yazılır ve komut
    yeniden gönderilir, en çok N kez.
- **`RUN_SIM_MOD_SINAMA=1`** (yalnız sınama): ilk komutu göndermez.
  - Kayıp seyrek olduğu için yeniden deneme yolunu ancak böyle gerçekten
    koşturabildim.
  - Bu da varsayılan kapalı.
- **`kosu.sh` değişmedi.** Ona verilen ortam değişkeni `run_sim.sh`'ye
  geçiyor. Örnek:
  `RUN_SIM_MOD_TEKRAR=2 tools/veri/kosu.sh 1 kol0 veri_w2`.

---

## 2. Doğrulama (ölçülen)

3 Kol 0 koşusu, W2 tohum 1:

| Koşu | `run_sim.log`'da modu seçme satırları | Mod devrede (sim s) | Bölüm |
|---|---|---|---|
| **kapalı** (varsayılan) | `Emergency Landing modu seciliyor...` | 34.16 | indi, 0.30 m/s, başarılı (v < 1.0) |
| açık (`RUN_SIM_MOD_TEKRAR=2`) | + `mod secildi (nav_state 23, deneme 1)` | 32.75 | indi, 0.30 m/s, başarılı |
| sınama (+ `RUN_SIM_MOD_SINAMA=1`) | + `mod secilmedi (nav_state 4, deneme 1)` ve `mod secildi (nav_state 23, deneme 2)` | 41.16 | indi, 0.30 m/s, başarılı |

- **Kapalıyken eski davranış:**
  - Kapalı koşunun `run_sim.log`'u, değişiklikten önce kaydedilmiş aynı
    koşulun (Tur 4 kapalı W2 t1) `run_sim.log`'uyla karşılaştırıldı.
  - Sayılar silinince iki günlük **satır satır aynı** (`diff` boş). Kontrol
    satırı yok, komut bir kez.
- **Sınamada yeniden deneme çalıştı:**
  - Kontrol nav_state 4'ü okudu (AUTO_LOITER, kalkıştan sonraki bekleme).
  - Komutu yeniden gönderdi; mod ikinci denemede seçildi.
  - 5 s bekleme ve ikinci komut modu ~7 s geciktirdi, sonra bölüm normal
    sürdü.
- **Açıkta ilk komut tuttu,** kontrolün ek gecikmesi görülmedi.
- **Ölçülmeyen:** gerçek bir komut kaybında yeniden denemenin işe yaradığı.
  Kayıp seyrek (2/48), bu üç koşuda olmadı. Kayıp yerine sınamada ilk komut
  bilerek gönderilmedi.

---

## 3. Kod

`run_sim.sh`, `trigger` bölümü:

```bash
mod_komutu() {
	ros2 topic pub -1 /fmu/in/vehicle_command px4_msgs/msg/VehicleCommand \
		"{command: 100001, param1: 23.0, target_system: 1, target_component: 1, source_system: 255, source_component: 190, from_external: true}" \
		--qos-reliability best_effort --qos-durability transient_local >/dev/null 2>&1
}
# The nav_state PX4 reports; 23 is the external mode the command asks for.
nav_state_oku() {
	"$PX4_BIN/px4-listener" vehicle_status 2>/dev/null |
		awk '$1 == "nav_state:" {print $2; exit}'
}
if [ "$DO_TRIGGER" = 1 ]; then
	echo "[run_sim] Emergency Landing modu seciliyor..."
	if [ "${RUN_SIM_MOD_TEKRAR:-0}" -gt 0 ] 2>/dev/null; then
		# The one best-effort command got lost in 2 of 48 runs (2026-10-04):
		# mode registered, vehicle up, nav_state never changed. Wait for
		# nav_state 23 and send again, up to RUN_SIM_MOD_TEKRAR more times.
		# RUN_SIM_MOD_SINAMA=1 skips the first send, to exercise the retry.
		for deneme in $(seq 1 $((RUN_SIM_MOD_TEKRAR + 1))); do
			if [ "$deneme" != 1 ] || [ "${RUN_SIM_MOD_SINAMA:-0}" != 1 ]; then
				mod_komutu
			fi
			ns=""
			for _ in $(seq 1 10); do
				ns=$(nav_state_oku)
				[ "$ns" = 23 ] && break
				sleep 0.5
			done
			if [ "$ns" = 23 ]; then
				echo "[run_sim]   mod secildi (nav_state 23, deneme $deneme)"
				break
			fi
			echo "[run_sim]   mod secilmedi (nav_state ${ns:-?}, deneme $deneme)"
		done
	else
		mod_komutu
	fi
fi
```

Önceki hâli: `if` içinde yalnız `echo` ve aynı `ros2 topic pub -1` satırı.
Yardım metnine iki ortam değişkeni eklendi.

---

## 4. Soru

**Veri toplama listelerinde açılsın mı?**
- Varsayılan kapalı kaldı.
- Bundan sonraki toplu koşularda listelere `RUN_SIM_MOD_TEKRAR=2` eklemeyi
  öneriyorum. Kayıp olursa koşu boşa gitmez, kayıp yoksa davranış aynı.
- Varsayılanın kendisinin açılması da mümkün; o, varsayılan davranış
  değişikliği olur.
- Karar senin.
