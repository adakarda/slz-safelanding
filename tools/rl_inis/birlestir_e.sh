#!/bin/bash
# Faz 6 bitince (ve D'nin ilk iki egitimi kodu yukledikten sonra) hiz-e dalini airsim'e birlestir.
# Eski ayarlarin davranisi ayni (51 test); D'nin egitim ve degerlendirmeleri etkilenmez.
{
while pgrep -f '[f]az6_zemin_v2\.sh' >/dev/null; do sleep 60; done
sleep 420
cd $HOME/ros2_ws
if [ "$(git rev-parse --abbrev-ref HEAD)" != airsim ]; then echo "[birlestir] dal airsim degil; durdu"; exit 1; fi
if git merge --ff-only -q hiz-e; then
	echo "[birlestir] $(date +%H:%M) hiz-e ileri sarildi: $(git log --oneline -1)"
else
	git merge -q --no-edit hiz-e && echo "[birlestir] $(date +%H:%M) hiz-e birlestirildi: $(git log --oneline -1)" \
		|| { git merge --abort; echo "[birlestir] cakisma; elle bakilacak"; exit 1; }
fi
grep -q diag_actions src/eland_rl/eland_rl/env.py && echo "[birlestir] diag_actions ana dalda"
exit
}
