#!/bin/bash
# B kuyrugunu on planda calistir, ciktisi kos/kuyruk_b.out'a
bash $HOME/rl_inis/kuyruk_b.sh > $HOME/rl_inis/kos/kuyruk_b.out 2>&1
tail -n 40 $HOME/rl_inis/kos/kuyruk_b.out
