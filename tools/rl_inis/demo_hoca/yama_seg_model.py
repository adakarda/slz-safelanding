"""Gosterim icin (Arda, 28.10: "hocaya AirSim'i goster; bizim segmentasyon modeli, RL komutlari, kontrol HUD'u").
- run_airsim.sh: --seg-model PATH ve --seg-adi AD (istege bagli; --v3 ile). Segmentasyon dugumu bu agirliklarla calisir.
  Varsayilan (seceneksiz) davranis degismez. Atomik degisim: calisan bir toplu kosu eski kopyasini korur.
- ~/v3_test/v3_airsim.py: model_adi parametresi; paneldeki sol baslik "<ad> (inisi bu yonetiyor)" olur.

    python3 yama_seg_model.py
"""
import os


def yama(p, pairs, atomik=False):
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        if new in s:
            continue
        assert s.count(old) == 1, (p, old)
        s = s.replace(old, new)
    tmp = p + '.yeni'
    open(tmp, 'w', encoding='utf-8').write(s)
    os.chmod(tmp, os.stat(p).st_mode)
    os.replace(tmp, p)
    print('yamandi:', p)


H = os.path.expanduser('~')
yama(f'{H}/ros2_ws/src/eland_airsim/scripts/run_airsim.sh', [
    ('#   --video      gosterim kaydi icin',
     '#   --seg-model PATH [--seg-adi AD]   --v3 ile: segmentasyon dugumu bu agirliklarla (or. best_v4.pth) calisir;\n'
     '#                panelde AD yazar. Yoksa best_v3.pth.\n'
     '#   --video      gosterim kaydi icin'),
    ('HIZLI_SON=""; GIMBAL=0; VIDEO=0\n', 'HIZLI_SON=""; GIMBAL=0; VIDEO=0; SEG_MODEL=""; SEG_ADI=v3\n'),
    ('\t--video) VIDEO=1 ;;\n', '\t--video) VIDEO=1 ;;\n\t--seg-model) SEG_MODEL=$2; shift ;;\n\t--seg-adi) SEG_ADI=$2; shift ;;\n'),
    ('\t"$HOME/v3_test/venv/bin/python" -P "$HOME/v3_test/v3_airsim.py" >"$LOG_DIR/v3.log" 2>&1 &\n',
     '\t"$HOME/v3_test/venv/bin/python" -P "$HOME/v3_test/v3_airsim.py" \\\n'
     '\t\t${SEG_MODEL:+--ros-args -p model_path:=$SEG_MODEL -p model_adi:=$SEG_ADI} >"$LOG_DIR/v3.log" 2>&1 &\n'),
], atomik=True)
yama(f'{H}/v3_test/v3_airsim.py', [
    ("        p('model_path', '/home/arda/v3_test/model/best_v3.pth')\n",
     "        p('model_path', '/home/arda/v3_test/model/best_v3.pth')\n"
     "        p('model_adi', 'v3')                 # panel title; e.g. v4 for best_v4.pth\n"),
    ("        cv2.rectangle(pan, (w + 5, 5), (2 * w - 5, 36), (0, 0, 0), -1)\n",
     "        cv2.rectangle(pan, (5, 5), (w - 5, 36), (0, 0, 0), -1)\n"
     "        cv2.putText(pan, f'{self.get_parameter(\"model_adi\").value} (inisi bu yonetiyor)', (10, 26),\n"
     "                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)\n"
     "        cv2.rectangle(pan, (w + 5, 5), (2 * w - 5, 36), (0, 0, 0), -1)\n"),
])
