# K45 ön kaydı: y_kalman_tavan08 (koşulardan ÖNCE, 2026-10-15)

Kol: y_kalman + `emergency_landing_mode.descent_max_mps=0.8` (`descent_min_mps`
varsayılan 0.3). Yalnız parametre. Yasa gözlemci, Kalman σ 0.05 / 0.7 / 0.7.
Koşular: W5 tohum 5–10, W3 tohum 1–3 (9 koşu). Sıra tohum-major, dünyalar
sırayla. K27 (K37 eşiği) bayrakları geçerli.

## Tahminler (tasarım sohbeti, K45; aynen)

1. Gözlenen pencereli: temas ortanca y_kalman'dan ±0.03 m, COMMIT aynı.
2. Gözlenen penceresiz: temas 0.78–0.82, COMMIT yok.
3. Hiçbir koşuda temas > 0.9.
4. Alçalma süresi y_kalman ile y_yavas08 arasında.
5. Sınırlı kare sayısı y_kalman'dan fazla (yavaş iniş = daha çok kare).

## Nasıl değerlendirilecek (Claude Code'un okuması; koşulardan önce)

- Pencere ve kare: `w5_pencere.py` gözlenen ölçümü (VALIDATE ile temas
  arasında view_bounded ve ρ > 0 kare; ≥ 10 → pencereli). (1), (2), (5) yalnız
  W5; W3'te pencere tanımı yok. (3), (4) dokuz koşunun hepsi.
- Karşılaştırma: adım 2'nin aynı tohum ve dünyadaki y_kalman ve y_yavas08
  koşuları (aşağıdaki tablo; `adim2_satirlar.csv`).
- (1) Gözlenen pencereli tavan08 koşularının temas ortancası, gözlenen
  pencereli y_kalman koşularının ortancasından (0.31 m/s, n 4) en çok 0.03 m/s
  farklı. COMMIT: gözlenen pencereli tavan08 koşularının hepsinde COMMIT var
  (y_kalman'da 4/4). Ek olarak tohum tohum aynı tohumun y_kalman koşusuyla
  var/yok karşılaştırması yazılır.
- (2) Gözlenen penceresiz her tavan08 koşusunda 0.78 ≤ temas ≤ 0.82 ve COMMIT yok.
- (3) Dokuz koşunun hepsinde temas ≤ 0.9.
- (4) Tohum başına: alçalma süresi (t_temas_gercek − t_validate) y_kalman'ın
  süresinden büyük ve y_yavas08'in süresinden küçük. Sayılır: k / 9.
- (5) Tohum başına (W5): tavan08'in sınırlı karesi > aynı tohumun y_kalman
  koşusununki. Sayılır: k / 6.
- Tahmin tutmazsa yazılır; kol, parametre ya da ölçüt değiştirilmez.

## Karşılaştırma koşuları (adım 2, ölçülen)

| dünya | tohum | kol | gözlenen (kare) | temas (m/s) | COMMIT | alçalma s |
|---|---|---|---|---|---|---|
| w3 | 1 | y_kalman | — | 0.28 | var | 17.5 |
| w3 | 1 | y_yavas08 | — | 0.80 | var | 22.2 |
| w3 | 2 | y_kalman | — | 0.30 | var | 13.6 |
| w3 | 2 | y_yavas08 | — | 0.80 | var | 18.3 |
| w3 | 3 | y_kalman | — | 0.31 | var | 14.0 |
| w3 | 3 | y_yavas08 | — | 0.80 | var | 17.3 |
| w5 | 5 | y_kalman | penceresiz (6) | 1.01 | yok | 8.5 |
| w5 | 5 | y_yavas08 | penceresiz (9) | 0.78 | yok | 16.4 |
| w5 | 6 | y_kalman | pencereli (16) | 0.30 | var | 11.3 |
| w5 | 6 | y_yavas08 | pencereli (28) | 0.80 | yok | 15.0 |
| w5 | 7 | y_kalman | pencereli (70) | 0.29 | var | 15.9 |
| w5 | 7 | y_yavas08 | pencereli (99) | 0.79 | yok | 19.1 |
| w5 | 8 | y_kalman | penceresiz (0) | 1.47 | yok | 6.1 |
| w5 | 8 | y_yavas08 | penceresiz (0) | 0.80 | yok | 11.7 |
| w5 | 9 | y_kalman | pencereli (40) | 0.31 | var | 13.5 |
| w5 | 9 | y_yavas08 | pencereli (70) | 0.80 | yok | 18.5 |
| w5 | 10 | y_kalman | pencereli (44) | 0.31 | var | 14.6 |
| w5 | 10 | y_yavas08 | pencereli (58) | 0.79 | yok | 18.4 |
