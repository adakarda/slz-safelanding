"""AirSim RPC stress check: the bridge's load (images 10 Hz + ground truth 50 Hz) plus a third client.

    ~/airsim-venv/bin/python -m eland_airsim.rpc_stres [--sure 360] [--host H] [--kamera asagi]

Run against an AirSim that is already up (run_airsim.sh --yalniz-px4). Counts call errors per client and
whether a fresh connection can still be opened after one. Question it answers: do the RPC drops seen in
the Faz 3 batches happen without flight, i.e. are they about load or the WSL <-> Windows link?
"""
import argparse
import collections
import threading
import time

from . import istemci


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sure', type=float, default=360.0)
    ap.add_argument('--host', default='')
    ap.add_argument('--kamera', default='asagi')
    a = ap.parse_args()
    import airsim
    host = a.host or istemci.windows_host()
    sayac = collections.Counter()
    olay = []
    dur = threading.Event()
    t0 = time.time()

    def dongu(ad, hz, cagri):
        c = istemci.connect(host, timeout_s=10)
        while not dur.is_set():
            t = time.monotonic()
            try:
                cagri(c)
                sayac[ad + '_tamam'] += 1
            except Exception as e:  # noqa: BLE001
                sayac[ad + '_hata'] += 1
                olay.append((round(time.time() - t0, 1), ad, type(e).__name__, str(e)[:60]))
                try:
                    c = istemci.connect(host, timeout_s=5)
                    olay.append((round(time.time() - t0, 1), ad, 'yeniden_baglandi', ''))
                except Exception as e2:  # noqa: BLE001
                    olay.append((round(time.time() - t0, 1), ad, 'baglanamadi', type(e2).__name__))
                    time.sleep(2.0)
            time.sleep(max(0.0, 1.0 / hz - (time.monotonic() - t)))

    reqs = [airsim.ImageRequest(a.kamera, airsim.ImageType.Scene, False, False),
            airsim.ImageRequest(a.kamera, airsim.ImageType.Segmentation, False, False)]
    isler = [('goruntu', 10.0, lambda c: c.simGetImages(reqs)),
             ('poz', 50.0, lambda c: c.simGetGroundTruthKinematics()),
             ('olcum', 20.0, lambda c: c.simGetGroundTruthKinematics())]
    th = [threading.Thread(target=dongu, args=i, daemon=True) for i in isler]
    for t in th:
        t.start()
    while time.time() - t0 < a.sure:
        time.sleep(30)
        print(f'[stres] {time.time() - t0:5.0f} s  {dict(sayac)}', flush=True)
    dur.set()
    print('[stres] olaylar (s, istemci, tur, ayrinti):')
    for o in olay[:40]:
        print('   ', o)
    print(f'[stres] SONUC: {sum(v for k, v in sayac.items() if k.endswith("_hata"))} hata, {len(olay)} olay')


if __name__ == '__main__':
    main()
