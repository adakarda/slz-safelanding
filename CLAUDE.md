# CLAUDE.md

Bu depoda çalışan Claude Code için giriş. Kurallar, komutlar, tuzaklar ve
sözlük `AGENTS.md`'de; başka ajanlarla ortak tek kaynak orası:

@AGENTS.md

## Claude Code'a özel notlar

- **Bağlam:** uzun dokümanları okuma.
  - `docs/README.md`'deki bölüm dizininden yeri bul.
  - Grep ile git, yalnız o bölümü oku.
  - Kontrolcüyle ilgili her sayı önce `docs/KONTROLCU_OLCUMLERI.md`'de.
- **Onay:** mevcut koda dokunacak işte önce planı yaz, onay bekle
  (AGENTS.md §3.1).
  - Plan şunları söylesin: hangi dosyalar, hangi parametre, varsayılan ne,
    kapalıyken eski davranış nasıl gösterilecek.
- **Uzun koşular** (`toplu.sh`, onlarca dakika):
  - Ayrık başlat (`setsid nohup ... &`).
  - Günlüğü `~/eland_veri/_gunlukler/`'e yaz.
  - Bitişi bir bekleme komutuyla izle.
  - Bitince sayıları tablo hâlinde ver.
- **Windows tarafından düzenleme** (`\\wsl.localhost\...`) exec bitini
  düşürür. Düzenlediğin betiklerin iznini kontrol et:
  `git ls-files -s` ile `stat -c %a`.
- **Bitirince:**
  - Commit mesajı ne ve neden, sayıyla.
  - Modülse annotated tag ve push (AGENTS.md §3.7).
  - Kullanıcıya hangi etiketi attığını söyle.
