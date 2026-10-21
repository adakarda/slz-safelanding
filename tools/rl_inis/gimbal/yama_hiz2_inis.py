"""Amendment 25: hiz2_tur.py also trains the gimbal variant (c23 + gimbal, 3 seeds) and waits for the gimbal AirSim
and evaluation step (gimbal/hazir); inis_sina.sh passes --gimbal through to run_airsim.sh.

    python3 yama_hiz2_inis.py
"""
import os

H = os.path.expanduser('~')


def yama(p, pairs, atomik=False):
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        if new in s:
            continue
        assert s.count(old) == 1, (p, old)
        s = s.replace(old, new)
    if atomik:
        tmp = p + '.yeni'
        open(tmp, 'w', encoding='utf-8').write(s)
        os.chmod(tmp, os.stat(p).st_mode)
        os.replace(tmp, p)
    else:
        open(p, 'w', encoding='utf-8').write(s)
    print('yamandi:', p)


yama(f'{H}/rl_inis/hiz2/hiz2_tur.py', [
    ('import subprocess\nimport sys\n', 'import subprocess\nimport sys\nimport time\n'),
    ("    env = json.loads(arama.secenek(args, '--env-json') or '{}')\n"
     "    out = _degerlendirme(args)\n"
     "    return out + ['--env-json', json.dumps({'v_lateral': env['v_lateral']})] if 'v_lateral' in env else out\n",
     "    env = json.loads(arama.secenek(args, '--env-json') or '{}')\n"
     "    out = _degerlendirme(args)\n"
     "    fiz = {k: env[k] for k in ('v_lateral', 'gimbal') if k in env}   # what changes the flight, not the reward\n"
     "    if fiz:\n"
     "        out += ['--env-json', json.dumps(fiz)]\n"
     "    if env.get('gimbal'):\n"
     "        out += ['--kalkan2']        # amendment 25b is judged with the locking shield (amendment 22)\n"
     "    return out\n"),
    ("    arama.log('yanal hiz turu basladi (Duzeltme 24)')\n",
     "    hazir = f'{H}/rl_inis/gimbal/hazir'           # amendment 25: AirSim + gimbal and its evaluation go first\n"
     "    while not os.path.exists(hazir):\n"
     "        time.sleep(60)\n"
     "    arama.log('yanal hiz ve gimbal egitim turu basladi (Duzeltme 24, 25b)')\n"),
    ("            isler.append(arama.Is('Y', ad, args, t, f'{arama.K}/{ad}_s{t}', degerlendir=('val_b32', 10), tam=True))\n",
     "            isler.append(arama.Is('Y', ad, args, t, f'{arama.K}/{ad}_s{t}', degerlendir=('val_b32', 10), tam=True))\n"
     "    g_args = ['--reward', 'zemin_v1', '--env-json', json.dumps({**C23, 'gimbal': True})]   # amendment 25b\n"
     "    for t in (0, 1, 2):\n"
     "        isler.append(arama.Is('Y', 'g', g_args, t, f'{arama.K}/g_s{t}', degerlendir=('val_b32', 10), tam=True))\n"),
    ("    print(subprocess.run(['python3', f'{H}/rl_inis/hiz2/h24_karar.py'], capture_output=True, text=True).stdout, flush=True)\n",
     "    print(subprocess.run(['python3', f'{H}/rl_inis/hiz2/h24_karar.py'], capture_output=True, text=True).stdout, flush=True)\n"
     "    print(subprocess.run(['python3', f'{H}/rl_inis/gimbal/h25b_karar.py'], capture_output=True, text=True).stdout,\n"
     "          flush=True)\n"),
])
yama(f'{H}/ros2_ws/src/eland_airsim/scripts/inis_sina.sh', [
    ('\t--hizli-son) RL+=(--hizli-son "$2"); RL_AD="${RL_AD}_hs$2"; shift ;;\n',
     '\t--hizli-son) RL+=(--hizli-son "$2"); RL_AD="${RL_AD}_hs$2"; shift ;;\n'
     '\t--gimbal) RL+=(--gimbal); RL_AD="${RL_AD}_gimbal" ;;\n'),
], atomik=True)
