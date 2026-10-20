#!/bin/bash
# Kim calisiyor: arama/gozlem orkestratorleri ve egitimler (kendi komut satirini eslestirmemek icin betik dosyasinda).
ps -eo pid,etime,args | grep -E 'arama/arama\.py|gozlem_tur\.py|eland_rl\.train|eland_rl\.evaluate|kuyruk_|havada_sonra|faz7_' | grep -v grep | cut -c1-160
ls ~/rl_inis/kos/arama/t1_c00_b1_kontrol/ckpt 2>/dev/null
free -m | sed -n 2p
