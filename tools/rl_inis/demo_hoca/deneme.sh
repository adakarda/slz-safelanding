#!/bin/bash
# Gosterim duzeninin denemesi: Duzeltme 31 turu bitince (egitim/degerlendirme yokken) hoca_demo.sh ile ayni secenekler +
# otomatik havada baslangic ve RL tetigi. Ekran goruntusu alinir, sonra kapatilir.
{
S=$HOME/ros2_ws/src/eland_airsim/scripts; D=$HOME/rl_inis/demo/hoca
M=$HOME/rl_inis/kos/arama/t2_c13_f_kayarak_kalkan/model.zip
while pgrep -f '[t]ur31\.py|[e]land_rl\.train|[f]aktor\.py' >/dev/null; do sleep 60; done
if pgrep -x px4 >/dev/null || pgrep -f '[r]un_airsim\.sh' >/dev/null; then echo "[deneme] sim calisiyor, cikiyorum"; exit 1; fi
L=$D/deneme_$(date +%H%M); mkdir -p $L
echo "[deneme] $(date +%H:%M) basladi"
bash $S/run_airsim.sh --baslangic 29.5,123.1 --havada -1.7,-51.7,30 --rl "$M" --kalkan 10 --gimbal \
	--v3 --seg-model $HOME/v4_seg/best_v4.pth --seg-adi v4 --izle --station --trigger --log-dir $L/calisma > $L/run.out 2>&1 &
R=$!
for _ in $(seq 1 600); do
	grep -qE "hazir\. Kapatmak|HATA" $L/run.out 2>/dev/null && break
	kill -0 $R 2>/dev/null || break
	sleep 1
done
grep -E "v3 dugumu|policy |havada:|secildi|HATA|BEKCI|istasyon|station" $L/run.out | sed 's/^/   /'
sleep 8
powershell.exe -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; \$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; \$i=New-Object System.Drawing.Bitmap \$b.Width,\$b.Height; \$g=[System.Drawing.Graphics]::FromImage(\$i); \$g.CopyFromScreen(\$b.Location,[System.Drawing.Point]::Empty,\$b.Size); \$i.Save('C:\\Users\\arda_\\rl_gorsel\\hoca\\gosterim_deneme_1.png')" 2>/dev/null
if grep -q "hazir\. Kapatmak" $L/run.out; then
	PYTHONPATH="$HOME/ros2_ws/src/eland_airsim:${PYTHONPATH:-}" $HOME/airsim-venv/bin/python -m eland_airsim.inis_sina \
		--out $L/inis.json > $L/inis_sina.log 2>&1
	python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('   sonuc', d.get('sonuc'), '| sure', d.get('sure_s'), 's | sinif', d.get('inis_sinifi'))" $L/inis.json
	powershell.exe -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; \$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; \$i=New-Object System.Drawing.Bitmap \$b.Width,\$b.Height; \$g=[System.Drawing.Graphics]::FromImage(\$i); \$g.CopyFromScreen(\$b.Location,[System.Drawing.Point]::Empty,\$b.Size); \$i.Save('C:\\Users\\arda_\\rl_gorsel\\hoca\\gosterim_deneme_2.png')" 2>/dev/null
fi
echo "   v4 dugumu: $(grep -m1 -o 'v3 yuklendi[^;]*' $L/calisma/v3.log 2>/dev/null)"
kill -TERM $R 2>/dev/null; wait $R 2>/dev/null
echo "[deneme] $(date +%H:%M) bitti"
exit
}
