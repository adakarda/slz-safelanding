"""durum_json.py ciktisi -> panonun dort veri dosyasi (kosular, egriler, degerlendirme, sistem), eski semayla.

    python3 durum_json.py | python3 pano_veri.py ESKI_KOSULAR.json CIKTI_KLASORU

ESKI_KOSULAR.json: panodaki bir onceki kosular.json (aciklama ve etiket metinleri ondan alinir).
Yeni: degerlendirme satirlarinda kural_basari = secili kuralin basarisi (SORA kosularinda SORA, B kosularinda zemin).
"""
import json
import os
import sys
import time

eski = {r['kosu']: r for r in json.load(open(sys.argv[1], encoding='utf-8'))}
out = sys.argv[2]
d = json.load(sys.stdin)
now = time.time()
DURUM = {'bitti': 'Bitti', 'egitimde': 'Eğitimde', 'sirada': 'Sırada', 'degerlendiriliyor': 'Değerlendiriliyor',
         'egitim bitti': 'Eğitim bitti', 'durdu': 'Durdu'}
YONTEM = {'rl': 'RL', 'rl_kalkan': 'RL + kalkan', 'duz_inis': 'Düz alçalma', 'duz_kalkan': 'Düz alçalma + kalkan',
          'kanal': 'SORA kanalı pilotu', 'gorus_kahini': 'Görüş kâhini (üst sınır)', 'rastgele': 'Rastgele'}


def saat(t):
    lt, ln = time.localtime(t), time.localtime(now)
    return time.strftime('%H:%M' if lt.tm_yday == ln.tm_yday else '%d.%m %H:%M', lt)


kosular, egriler, deg = [], [], []
# B queue: two slots; a queued run starts when the earlier of the two running/queued runs ends
slot = []
for i, r in enumerate(d['kosular']):
    ad = r['ad']
    e = eski.get(ad, {})
    adim, hedef = int(r.get('adim') or 0), int(r['hedef'])
    fps = r.get('fps')
    durum = DURUM.get(r.get('durum', 'sirada'), r.get('durum'))
    bas, bit = '', ''
    if r.get('durum') == 'egitimde' and fps:
        t_end = now + max(hedef - adim, 0) / fps
        bit = saat(t_end)
        if ad.startswith('B'):
            slot.append(t_end)
    elif r.get('durum') == 'sirada' and ad.startswith('B'):
        slot.sort()
        t0 = slot.pop(0) if len(slot) >= 2 else now
        t_end = t0 + hedef / 160.0           # measured B speed ~160 steps/s per run
        bas, bit = saat(t0), saat(t_end)
        slot.append(t_end)
    elif r.get('durum') in ('bitti', 'egitim bitti', 'degerlendiriliyor'):
        bit = 'bitti'
    egri = r.get('egri') or []
    kosular.append({
        'kosu': ad, 'sira': i + 1, 'akis': e.get('akis', 'C' if ad.startswith('B') else ('B' if ad.startswith('P') else 'A')),
        'aciklama': e.get('aciklama', r.get('aciklama', '')), 'durum': durum, 'adim': adim, 'hedef': hedef,
        'ilerleme': round(min(adim / hedef, 1.0), 4) if hedef else 0.0, 'hiz_adim_s': fps,
        'tahmini_baslangic': bas, 'tahmini_bitis': bit, 'etiket': e.get('etiket', ''),
        'bolum_sayisi': r.get('bolum', 0), 'bolum_suresi_s': round((r.get('ep_uzunluk') or 0) * 0.25, 1),
        'approx_kl': round(r['kl'], 5) if r.get('kl') is not None else None,
        'son_egitim_sora': round(egri[-1]['sora'] / 100, 4) if egri else None, 'kesintiler': r.get('kesintiler', [])})
    for c in egri:
        egriler.append({'kosu': ad, 'adim': c['adim'], 'sora': round(c['sora'] / 100, 4),
                        'sure_doldu': round(c['timeout'] / 100, 4), 'guvensiz': round(c['guvensiz'] / 100, 4), 'bolum': c['n']})
    for liste, res in (r.get('degerlendirme') or {}).items():
        for y, v in res.items():
            s = v['sonuc']
            n = sum(s.values()) or 1
            deg.append({'anahtar': f'{ad}|{liste}|{y}', 'kosu': ad, 'liste': liste, 'yontem': YONTEM.get(y, y),
                        'sora_basari': round(v['sora'] / 100, 4), 'kural_basari': round(s.get('safe_landing', 0) / n, 4),
                        'guvensiz': round(s.get('unsafe_landing', 0) / n, 4), 'sure_doldu': round(s.get('timeout', 0) / n, 4),
                        'disari': round(s.get('out_of_bounds', 0) / n, 4), 'deneme': n, 'odul': v['odul']})
b = d['bellek_mb']
bitisler = [k['tahmini_bitis'] for k in kosular if k['tahmini_bitis'] not in ('', 'bitti')]
sistem = [{'zaman': d['zaman'], 'bellek_gb': round(b['kullanilan'] / 1024, 1), 'bellek_toplam_gb': round(b['toplam'] / 1024, 1),
           'swap_gb': round(b['swap'] / 1024, 1), 'kosan_egitim': sum(k['durum'] == 'Eğitimde' for k in kosular),
           'sirada': sum(k['durum'] == 'Sırada' for k in kosular), 'tum_bitis': bitisler[-1] if bitisler else 'bitti'}]
for ad, x in (('kosular', kosular), ('egriler', egriler), ('degerlendirme', deg), ('sistem', sistem)):
    json.dump(x, open(os.path.join(out, ad + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(ad, len(x))
