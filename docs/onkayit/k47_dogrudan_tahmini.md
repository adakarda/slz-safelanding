# K47 ön kaydı: y_dogrudan çevrimdışı inceleme (incelemeden ÖNCE, 2026-10-15)

Koşu yok; adım 2'nin kayıtlı bölümleri.

## Tahmin (tasarım sohbeti, K47; aynen)

hata_2m_dogrudan W5 pencereli ortancası ≥ +1 m (neden: A0 EKF ölçekli).

## Nasıl değerlendirilecek (Claude Code'un okuması; incelemeden önce)

- hata_2m_dogrudan = gerçek hedef yüksekliği (kâhin, `gozlemci.csv`
  `h_kahin_m`) ilk kez ≤ 2.0 m olduğunda `h_dogrudan_m − h_kahin_m`
  (`gecerli` = 1 satır).
- Birincil örnek: y_dogrudan kolu, W5 tohum 5–10, grup = koşunun kendi v1
  grubu (K16, resmî), pencereli. Aynı sayı gözlenen gruba göre de yazılır.
  Ek bilgi: doğrudan tahmin her kolda hesaplandığı için bütün kolların W5
  pencereli koşularında da ortanca yazılır.
- `adim2_satirlar.csv`'de bu sütun önceden hesaplandı, ama değerleri bu
  dosya commit'lenene kadar okunmadı.
- Hata serisi: doğrudan, gözlemci ve kâhin; gözlemci başladıktan sonra zamana
  ve gerçek yüksekliğe göre (bantlar 8 / 6 / 4 / 3 / 2 m).
