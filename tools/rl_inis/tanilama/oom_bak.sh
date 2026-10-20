#!/bin/bash
dmesg | grep -iE 'oom|killed process|Out of memory' | tail -10
echo "== systemd/distro"; ps -eo pid,lstart,cmd | head -5
K=$HOME/rl_inis/kos
ls -la --time-style=+%H:%M $K/messi_a1_s0/ckpt $K/da_P0/ckpt 2>/dev/null | tail -12
echo "== a1"; tail -3 $K/a1_devam.out; grep -v -i warn $K/messi_a1_s0/egitim.log | tail -2
echo "== da"; tail -3 $K/da_kollar.out; tail -2 $K/da_P0/egitim.log
echo "== a2b"; tail -3 $K/a2b_kuyruk.out
ls /tmp | head
