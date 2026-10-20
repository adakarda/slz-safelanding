#!/bin/bash
# son izle oturumunun loglarini ozetle
D=$(ls -td $HOME/rl_inis/izle/*/ | head -1)
echo "$D"
tail -n 3 $D/politika.log
grep -i -E 'regist|error|activ|touch|landed|inactive' $D/mod.log | tail -n 8
echo "--- politika.csv (son 3)"
tail -n 3 $D/politika.csv
tail -n 2 $D/rqt.log
