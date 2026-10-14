#!/usr/bin/env python3
"""W5: adayın ve temas noktasının platform kenarına gerçek uzaklığı (çevrimdışı).

Salt okunur. Bölüm klasörlerine yazmaz; çıktılar --cikis klasörüne.

Kenar payı: kare hedef yüzeyin kenarına işaretli uzaklık (m). İçeride +,
dışarıda − (kutuya en kısa uzaklık). Merkeze uzaklık değil: köşegende
merkezden 4.5 m olan nokta kenara 1.8 m'dir.

Ölçek modeli: mapping_node IPM'i h_ekf ile yapar (mesafe sensörü yok,
``altitude_agl = -z``). Platformun üstündeki gerçek kamera yüksekliği
h_gercek_hedef'tir. Bir karede platform, aracın EKF yatay konumu V etrafında
s = h_ekf / h_gercek_hedef kat büyük görünür:
    harita_noktasi = V + s · (gercek_nokta − V)
Adayın harita kenar payı (dedektörün ``radius_m``'si, ölçülen) dört yolla
yeniden üretilir:
  1. anlık (``kp_harita_tahmin``): yalnız t_damga'daki V ve s ile büyütülmüş
     kutu. Haritanın belleğini (tau 30 s) yok sayar.
  2. birikimli ideal (``radius_olcekli_tahmin``): her maske karesinde
     kadrajdaki hücrelere ideal geometriden çim / çim dışı kanıt, mapping_node
     gibi sönüm ve kazanan sınıf. ``_olceksiz``: aynısı, doğru yükseklikle.
  3. maske oynatma (``radius_maske_hesap``): kayıtlı maskeler mapping_node'un
     homografisi ve birleştirmesiyle. ``radius_m``'yi tutturması beklenir.
  4. karşı-olgu: aynı oynatma gerçek kamera yüksekliğiyle
     (``_maske_dogru_hesap``) ve buna ek olarak askıdaki karelerden kestirilen
     sabit yaw sapmasıyla (``_maske_dogru_yaw_hesap``, ``yaw_farki_tahmin_deg``).
Ayrıca görülen nokta P = V + (C − V) / s (``p*_tahmin``): C hücresine iz düşen
gerçek nokta. Araç P'ye değil C'ye uçar; kayma = |C − P|.

Kullanım: python3 w5_kenar_payi.py [--kok ~/eland_veri] [--cikis DIR]
Çıktı: w5_kenar_payi.csv (bölüm başına), w5_aday_olaylari.csv (aday başına),
w5_kenar_payi.png. Süre: 21 bölümde birkaç dakika.
"""
import argparse
import glob
import json
import os
import re

import numpy as np
import pandas as pd
import yaml

KOLLAR = ('k1_*', 'k2_*', 'k3_*', 'kol0')
LATCH_M = 2.0          # detector latch_radius_m (eland_params.yaml)


def kenar_payi(x, y, kutu):
    """Kutuya (x0, y0, x1, y1) işaretli uzaklık: içeride +, dışarıda −."""
    x0, y0, x1, y1 = kutu
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    hx, hy = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    dx = np.abs(np.asarray(x, float) - cx) - hx
    dy = np.abs(np.asarray(y, float) - cy) - hy
    ic = (dx <= 0) & (dy <= 0)
    return np.where(ic, -np.maximum(dx, dy),
                    -np.hypot(np.maximum(dx, 0.0), np.maximum(dy, 0.0)))


def olcekli_kutu(kutu, vx, vy, s):
    """V etrafında s kat büyütülmüş kutu (haritadaki platform, _tahmin)."""
    x0, y0, x1, y1 = kutu
    return (vx + s * (x0 - vx), vy + s * (y0 - vy),
            vx + s * (x1 - vx), vy + s * (y1 - vy))


# -- birikimli harita modeli (_tahmin) -------------------------------------
# mapping_node'un kopyası değil, aynı geometrinin sade bir benzetimi:
# her maske karesinde kadraja giren hücreler, ışın platform düzleminde
# kutunun içine düşüyorsa çim, değilse çim dışı kanıt alır; kanıt
# exp(-dt/tau) ile söner, kazanan sınıf seçilir, toplamı min_evidence altı
# bilinmez. Duvar ve örtme yok sayılır (çim dışı sayılır).
HFOV = np.radians(99.7)
IMG_W, IMG_H = 320, 240
FX = (IMG_W / 2.0) / np.tan(HFOV / 2.0)
R_BODY_CAM = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
TAU_S, MIN_KANIT, MAX_EGIM = 30.0, 0.05, np.radians(30.0)
RES, YARI_IZGARA = 0.2, 25.0
_g = np.arange(-YARI_IZGARA + RES / 2, YARI_IZGARA, RES)
GE, GN = np.meshgrid(_g, _g)          # hücre merkezleri, dünya doğu / kuzey


def r_ned_body(roll, pitch, yaw):
    cr, sr, cp, sp, cy, sy = (np.cos(roll), np.sin(roll), np.cos(pitch),
                              np.sin(pitch), np.cos(yaw), np.sin(yaw))
    return np.array([
        [cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
        [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
        [-sp, sr * cp, cr * cp]])


def birikimli_model(d, maske_t, off, kutu, olcekli=True):
    """Kare zamanları maske_t'de; (t, cim_mi, bilinen_mi) üreteci döndürür."""
    sut = ['h_ekf', 'h_gercek_hedef', 'x_ekf_kuzey', 'y_ekf_dogu',
           'roll', 'pitch', 'yaw']
    iz = {c: ara(d, c, maske_t) for c in sut}
    kanit = np.zeros(GE.shape + (2,), np.float32)   # 0 çim dışı, 1 çim
    t_son = None
    x0, y0, x1, y1 = kutu
    for i, t in enumerate(maske_t):
        h, hp = iz['h_ekf'][i], iz['h_gercek_hedef'][i]
        vals = [iz[c][i] for c in sut]
        if t_son is not None:
            kanit *= np.exp(-(t - t_son) / TAU_S)
        t_son = t
        if not np.all(np.isfinite(vals)) or h < 0.1:
            yield t, None
            continue
        R = r_ned_body(iz['roll'][i], iz['pitch'][i], iz['yaw'][i])
        if np.arccos(np.clip(R[2, 2], -1, 1)) > MAX_EGIM:
            yield t, None
            continue
        ve = off[0] + iz['y_ekf_dogu'][i]
        vn = off[1] + iz['x_ekf_kuzey'][i]
        # hücre -> ışın (NED) -> kamera -> piksel
        ned = np.stack([GN - vn, GE - ve, np.full(GE.shape, h)], -1)
        cam = ned @ (R @ R_BODY_CAM)
        z = cam[..., 2]
        with np.errstate(divide='ignore', invalid='ignore'):
            u = FX * cam[..., 0] / z + IMG_W / 2.0
            v = FX * cam[..., 1] / z + IMG_H / 2.0
        gorus = (z > 0) & (u >= 0) & (u < IMG_W) & (v >= 0) & (v < IMG_H)
        # ışının platform düzlemindeki gerçek noktası
        k = (hp / h) if (olcekli and hp > 0.05) else 1.0
        xe, xn = ve + (GE - ve) * k, vn + (GN - vn) * k
        cim = (xe >= x0) & (xe <= x1) & (xn >= y0) & (xn <= y1)
        if not olcekli:
            cim = (GE >= x0) & (GE <= x1) & (GN >= y0) & (GN <= y1)
        kanit[..., 1] += gorus & cim
        kanit[..., 0] += gorus & ~cim
        yield t, kanit


def maske_oynat(d, maske_npz, off, yukseklik='ekf', dyaw_deg=0.0):
    """Kayıtlı maskeleri mapping_node'un homografisi ve birleştirmesiyle
    yeniden oynatır (_hesap). Poz, maskenin alındığı anda (mapping_node da
    o anki son pozu kullanır). Üreteç: (t_yakalama, kanit).
    yukseklik='gercek': IPM yüksekliği olarak kameranın hedef yüzeye gerçek
    yüksekliği (h_gercek_hedef + 0.10 m kamera montajı) kullanılır; platform
    doğru boyda, zemin ise araca doğru sıkışmış çıkar (karşı-olgu).
    dyaw_deg: EKF yaw'ından çıkarılan sabit sapma (yaw_farki ile kestirilir)."""
    import cv2
    z = np.load(maske_npz)
    M, ty, ta = z['maskeler'], z['t_yakalama'], z['t_alma']
    sira = np.argsort(ta)
    sut = ['h_ekf', 'x_ekf_kuzey', 'y_ekf_dogu', 'roll', 'pitch', 'yaw']
    iz = {c: ara(d, c, ta[sira]) for c in sut}
    if yukseklik == 'gercek':
        iz['h_ekf'] = ara(d, 'h_gercek_hedef', ta[sira]) + 0.10
    k_inv = np.linalg.inv(np.array([[FX, 0, IMG_W / 2.0], [0, FX, IMG_H / 2.0],
                                    [0, 0, 1.0]]))
    n = GE.shape[0]
    org_e, org_n = -YARI_IZGARA, -YARI_IZGARA     # hücre (0,0) köşesi, dünya
    kanit = np.zeros((n, n, 8), np.float32)
    t_son = None
    for j, i in enumerate(sira):
        t = ta[i]
        if t_son is not None:
            kanit *= np.exp(-(t - t_son) / TAU_S)
        t_son = t
        vals = [iz[c][j] for c in sut]
        if not np.all(np.isfinite(vals)):
            yield ty[i], None
            continue
        R = r_ned_body(iz['roll'][j], iz['pitch'][j],
                       iz['yaw'][j] - np.radians(dyaw_deg))
        if np.arccos(np.clip(R[2, 2], -1, 1)) > MAX_EGIM:
            yield ty[i], None
            continue
        m = R @ R_BODY_CAM @ k_inv
        alt = max(iz['h_ekf'][j], 0.1)
        d_e = off[0] + iz['y_ekf_dogu'][j] - org_e
        d_n = off[1] + iz['x_ekf_kuzey'][j] - org_n
        sc = alt / RES
        H = np.vstack([sc * m[1, :] + (d_e / RES - 0.5) * m[2, :],
                       sc * m[0, :] + (d_n / RES - 0.5) * m[2, :], m[2, :]])
        proj = cv2.warpPerspective(np.minimum(M[i], 7), H, (n, n), flags=cv2.INTER_NEAREST,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        cov = cv2.warpPerspective(np.ones(M[i].shape, np.uint8), H, (n, n),
                                  flags=cv2.INTER_NEAREST,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        r, c = np.nonzero(cov)
        np.add.at(kanit, (r, c, proj[r, c]), 1.0)
        # model_radius ile aynı biçim: [..., 1] kazanan çimse toplam, değilse
        # [..., 0]; kazanan = argmax (mapping_node.fused_grid)
        tot = kanit.sum(-1)
        cim = kanit.argmax(-1) == 0
        yield ty[i], np.stack([np.where(cim, 0, tot), np.where(cim, tot, 0)], -1)


def yaw_farki(d, maske_npz, off, kutu, t0, t1):
    """Askıdaki karelerden (t0..t1) maske ile geometrinin hizalandığı sabit
    yaw sapması (derece, _tahmin): doğru yükseklikle izdüşülen çimin gerçek
    kutuyla IoU'sunu en büyük yapan dyaw. EKF yaw'ı doğruysa ~0 çıkar.
    Döndürür: (dyaw, o dyaw'daki IoU, dyaw = 0'daki IoU)."""
    z = dict(np.load(maske_npz))
    adaylar = np.arange(-25.0, 25.01, 0.5)
    iou = np.array([_iou(d, z, off, kutu, t0, t1, dy) for dy in adaylar])
    b = int(np.argmax(iou))
    return float(adaylar[b]), float(iou[b]), float(_iou(d, z, off, kutu, t0, t1, 0.0))


def _iou(d, z, off, kutu, t0, t1, dy):
    """Doğru yükseklik ve yaw - dy ile izdüşülen çimin kutuyla ortalama IoU'su."""
    import cv2
    M, ta = z['maskeler'], z['t_alma']
    sec = np.nonzero((ta >= t0) & (ta <= t1))[0]
    if len(sec) == 0:
        return np.nan
    x0, y0, x1, y1 = kutu
    kutu_ic = (GE >= x0) & (GE <= x1) & (GN >= y0) & (GN <= y1)
    k_inv = np.linalg.inv(np.array([[FX, 0, IMG_W / 2.0], [0, FX, IMG_H / 2.0],
                                    [0, 0, 1.0]]))
    n = GE.shape[0]
    g = {c: ara(d, c, ta[sec]) for c in
         ['h_gercek_hedef', 'x_ekf_kuzey', 'y_ekf_dogu', 'roll', 'pitch', 'yaw']}
    top = 0.0
    for j, i in enumerate(sec):
        R = r_ned_body(g['roll'][j], g['pitch'][j], g['yaw'][j] - np.radians(dy))
        m = R @ R_BODY_CAM @ k_inv
        sc = max(g['h_gercek_hedef'][j] + 0.10, 0.1) / RES
        d_e = off[0] + g['y_ekf_dogu'][j] + YARI_IZGARA
        d_n = off[1] + g['x_ekf_kuzey'][j] + YARI_IZGARA
        H = np.vstack([sc * m[1] + (d_e / RES - 0.5) * m[2],
                       sc * m[0] + (d_n / RES - 0.5) * m[2], m[2]])
        p = cv2.warpPerspective(M[i], H, (n, n), flags=cv2.INTER_NEAREST,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=255)
        gor = p != 255
        c = (p == 0) & gor
        k = kutu_ic & gor
        top += (c & k).sum() / max((c | k).sum(), 1)
    return top / len(sec)


def model_radius(kanit, cx, cy):
    """Adaydan en yakın çim olmayan / bilinmeyen hücreye uzaklık ve çim alanı."""
    bilinen = kanit.sum(-1) >= MIN_KANIT
    cim = bilinen & (kanit[..., 1] > kanit[..., 0])
    dis = ~cim
    r = float(np.min(np.hypot(GE[dis] - cx, GN[dis] - cy))) if dis.any() else np.nan
    return r, float(cim.sum() * RES * RES)


def hedef_kutu(dunya_yaml):
    with open(dunya_yaml) as f:
        w = yaml.safe_load(f)
    for yz in w['yuzeyler']:
        if yz['ad'] == w.get('hedef'):
            return tuple(float(v) for v in yz['dikdortgenler'][0]), w
    raise RuntimeError(f'{dunya_yaml}: hedef yüzey yok')


def ara(d, sutun, t):
    """duzenli.csv sütununu t anına doğrusal ara değerle (boşları atlayarak)."""
    m = d[sutun].notna().to_numpy()
    y = d[sutun].to_numpy()[m]
    if sutun == 'yaw':
        y = np.unwrap(y)
    return np.interp(t, d['t_gz'].to_numpy()[m], y, left=np.nan, right=np.nan)


def tekrar_var(ep_dir):
    p = os.path.join(ep_dir, 'run_sim.log')
    if not os.path.exists(p):
        return None
    with open(p, errors='replace') as f:
        return bool(re.search(r'deneme [2-9]\)', f.read()))


def bolum(ep_dir):
    with open(os.path.join(ep_dir, 'kosul.yaml')) as f:
        kos = yaml.safe_load(f)
    with open(os.path.join(ep_dir, 'ep_ozet.json')) as f:
        oz = json.load(f)
    kutu, _ = hedef_kutu(kos['dunya_yaml'])
    mx, my = (kutu[0] + kutu[2]) / 2.0, (kutu[1] + kutu[3]) / 2.0
    d = pd.read_csv(os.path.join(ep_dir, 'duzenli.csv'))
    k = pd.read_csv(os.path.join(ep_dir, 'karar_olaylari.csv'))
    off_e, off_n = oz['yerel_dunya_ofset_en_m']
    t_val = oz.get('t_validate')
    t_tem = oz.get('t_temas_gercek')

    # -- adaylar (gecerli), dünya ENU -------------------------------------
    a = k[k['gecerli'] > 0.5].copy().reset_index(drop=True)
    a['cx'] = a['x_yerel'] + off_e
    a['cy'] = a['y_yerel'] + off_n
    hata_kontrol = float(np.nanmax(np.abs(
        np.hypot(a['cx'] - mx, a['cy'] - my) - a['secilen_nokta_hata_m'])))
    a['kp_aday_hesap'] = kenar_payi(a['cx'], a['cy'], kutu)
    # haritanın damgasındaki araç durumu
    t = a['t_damga'].to_numpy()
    a['vx_gercek'] = ara(d, 'x_gercek', t)
    a['vy_gercek'] = ara(d, 'y_gercek', t)
    a['vx_ekf'] = off_e + ara(d, 'y_ekf_dogu', t)
    a['vy_ekf'] = off_n + ara(d, 'x_ekf_kuzey', t)
    a['h_ekf'] = ara(d, 'h_ekf', t)
    a['h_gercek_hedef'] = ara(d, 'h_gercek_hedef', t)
    a['s_hesap'] = a['h_ekf'] / a['h_gercek_hedef']
    # ölçek modeli; V = EKF konumu (mapping_node onu kullanıyor)
    kp_harita, px, py = [], [], []
    for r in a.itertuples():
        ok = np.isfinite(r.s_hesap) and np.isfinite(r.vx_ekf)
        if not ok:
            kp_harita.append(np.nan); px.append(np.nan); py.append(np.nan)
            continue
        kb = olcekli_kutu(kutu, r.vx_ekf, r.vy_ekf, r.s_hesap)
        kp_harita.append(float(kenar_payi(r.cx, r.cy, kb)))
        px.append(r.vx_ekf + (r.cx - r.vx_ekf) / r.s_hesap)
        py.append(r.vy_ekf + (r.cy - r.vy_ekf) / r.s_hesap)
    a['kp_harita_tahmin'] = kp_harita
    a['px_tahmin'] = px
    a['py_tahmin'] = py
    a['kp_gorulen_tahmin'] = kenar_payi(a['px_tahmin'], a['py_tahmin'], kutu)
    a['kayma_tahmin'] = np.hypot(a['cx'] - a['px_tahmin'],
                                 a['cy'] - a['py_tahmin'])
    a['alan_tahmin'] = (kutu[2] - kutu[0]) * (kutu[3] - kutu[1]) * a['s_hesap'] ** 2
    # birikimli harita: ölçekli (h_ekf ile IPM) ve ölçeksiz (doğru yükseklik)
    mk = pd.read_csv(os.path.join(ep_dir, 'maske_olaylari.csv'))
    maske_t = np.sort(mk['t_yakalama'].dropna().to_numpy())
    td = a['t_damga'].to_numpy()
    npz = os.path.join(ep_dir, 'maskeler.npz')
    t_mod = oz.get('t_mod_devrede') or t_val
    dyaw, dyaw_iou, dyaw0 = yaw_farki(d, npz, (off_e, off_n), kutu,
                                      t_mod - 4.0, t_mod)
    kaynaklar = [
        ('olcekli', lambda: birikimli_model(d, maske_t, (off_e, off_n), kutu, True)),
        ('olceksiz', lambda: birikimli_model(d, maske_t, (off_e, off_n), kutu, False)),
        ('maske', lambda: maske_oynat(d, npz, (off_e, off_n))),
        ('maske_dogru', lambda: maske_oynat(d, npz, (off_e, off_n), 'gercek')),
        ('maske_dogru_yaw', lambda: maske_oynat(d, npz, (off_e, off_n), 'gercek',
                                                dyaw))]
    for ad, uret in kaynaklar:
        rr, aa = np.full(len(a), np.nan), np.full(len(a), np.nan)
        j = 0
        for t, kanit in uret():
            # bu kare, damgası t olan adaylardan önce/aynı anda
            while j < len(a) and td[j] < t - 1e-6:
                j += 1
            jj = j
            while jj < len(a) and abs(td[jj] - t) < 0.051:
                if kanit is not None:
                    rr[jj], aa[jj] = model_radius(kanit, a['cx'].iloc[jj],
                                                  a['cy'].iloc[jj])
                jj += 1
        etk = 'hesap' if ad.startswith('maske') else 'tahmin'
        a[f'radius_{ad}_{etk}'] = rr
        a[f'alan_{ad}_{etk}'] = aa
    a.insert(0, 'ep_id', kos['ep_id'])

    # -- VALIDATE girişindeki aday ve seçildiği an ----------------------------
    once = a[a['t_alma'] <= t_val] if t_val is not None else a.iloc[:0]
    sat = {'ep_id': kos['ep_id'], 'kol': kos['kol'], 'tohum': kos['tohum'],
           'dogus': kos['dogus'], 'hata_kontrol_m': hata_kontrol,
           'aday_sayisi': len(a), 't_validate': t_val, 't_temas': t_tem,
           'yaw_farki_tahmin_deg': dyaw, 'yaw_iou_hesap': dyaw_iou,
           'yaw_iou_sifir_hesap': dyaw0}
    if len(once):
        iv = once.index[-1]
        cv = a.loc[iv]
        # aynı site: geriye doğru latch yarıçapı içinde kaldığı sürece
        i0 = iv
        while i0 > 0 and np.hypot(a.loc[i0 - 1, 'cx'] - cv.cx,
                                  a.loc[i0 - 1, 'cy'] - cv.cy) <= LATCH_M:
            i0 -= 1
        c0 = a.loc[i0]
        sat.update({
            'val_cx': cv.cx, 'val_cy': cv.cy,
            'val_merkez_uzak': cv.secilen_nokta_hata_m,
            'val_kp_aday_hesap': cv.kp_aday_hesap,
            'val_radius_m': cv.radius_m, 'val_area_m2': cv.area_m2,
            'val_s_hesap': cv.s_hesap,
            'val_kp_harita_tahmin': cv.kp_harita_tahmin,
            'val_kp_gorulen_tahmin': cv.kp_gorulen_tahmin,
            'val_kayma_tahmin': cv.kayma_tahmin,
            'val_alan_tahmin': cv.alan_tahmin,
            'val_radius_olcekli_tahmin': cv.radius_olcekli_tahmin,
            'val_radius_olceksiz_tahmin': cv.radius_olceksiz_tahmin,
            'val_alan_olcekli_tahmin': cv.alan_olcekli_tahmin,
            'val_alan_olceksiz_tahmin': cv.alan_olceksiz_tahmin,
            'val_radius_maske_hesap': cv.radius_maske_hesap,
            'val_alan_maske_hesap': cv.alan_maske_hesap,
            'val_radius_maske_dogru_hesap': cv.radius_maske_dogru_hesap,
            'val_alan_maske_dogru_hesap': cv.alan_maske_dogru_hesap,
            'val_radius_maske_dogru_yaw_hesap': cv.radius_maske_dogru_yaw_hesap,
            'val_alan_maske_dogru_yaw_hesap': cv.alan_maske_dogru_yaw_hesap,
            'secim_t': c0.t_damga, 'secim_cx': c0.cx, 'secim_cy': c0.cy,
            'secim_vx': c0.vx_ekf, 'secim_vy': c0.vy_ekf,
            'secim_h_ekf': c0.h_ekf, 'secim_h_gercek_hedef': c0.h_gercek_hedef,
            'secim_s_hesap': c0.s_hesap, 'secim_radius_m': c0.radius_m,
            'secim_area_m2': c0.area_m2,
            'secim_kp_aday_hesap': c0.kp_aday_hesap,
            'secim_kp_harita_tahmin': c0.kp_harita_tahmin,
            'secim_kp_gorulen_tahmin': c0.kp_gorulen_tahmin,
            'secim_kayma_tahmin': c0.kayma_tahmin,
            'secim_alan_tahmin': c0.alan_tahmin,
            'secim_radius_olcekli_tahmin': c0.radius_olcekli_tahmin,
            'secim_radius_olceksiz_tahmin': c0.radius_olceksiz_tahmin,
            'secim_alan_olcekli_tahmin': c0.alan_olcekli_tahmin,
            'secim_alan_olceksiz_tahmin': c0.alan_olceksiz_tahmin,
            'secim_radius_maske_hesap': c0.radius_maske_hesap,
            'secim_alan_maske_hesap': c0.alan_maske_hesap,
            'secim_radius_maske_dogru_hesap': c0.radius_maske_dogru_hesap,
            'secim_alan_maske_dogru_hesap': c0.alan_maske_dogru_hesap,
            'secim_radius_maske_dogru_yaw_hesap': c0.radius_maske_dogru_yaw_hesap,
            'secim_alan_maske_dogru_yaw_hesap': c0.alan_maske_dogru_yaw_hesap,
        })
    # VALIDATE'ten temasa adayın kenar payı
    if t_val is not None and t_tem is not None:
        ar = a[(a['t_alma'] >= t_val) & (a['t_alma'] <= t_tem)]
        if len(once):
            ar = pd.concat([once.iloc[[-1]], ar])
        if len(ar):
            sat['inis_kp_aday_min_hesap'] = float(ar['kp_aday_hesap'].min())
            sat['inis_kp_aday_son_hesap'] = float(ar['kp_aday_hesap'].iloc[-1])
            sat['inis_aday_kayma_max'] = float(np.max(np.hypot(
                ar['cx'] - ar['cx'].iloc[0], ar['cy'] - ar['cy'].iloc[0])))
            sat['son_cx'] = float(ar['cx'].iloc[-1])
            sat['son_cy'] = float(ar['cy'].iloc[-1])

    # -- temas ---------------------------------------------------------------
    if t_tem is not None:
        tx = float(ara(d, 'x_gercek', t_tem))
        ty = float(ara(d, 'y_gercek', t_tem))
        sat.update({
            'temas_x': tx, 'temas_y': ty,
            'temas_merkez_uzak': float(ara(d, 'yatay_hata_hedef_gercek_m', t_tem)),
            'temas_kp_hesap': float(kenar_payi(tx, ty, kutu)),
            'temas_h_gercek_hedef': float(ara(d, 'h_gercek_hedef', t_tem)),
            'temas_h_gercek_zemin': float(ara(d, 'h_gercek_zemin', t_tem)),
        })
        if 'son_cx' in sat:
            sat['temas_adaya_uzak'] = float(np.hypot(tx - sat['son_cx'],
                                                     ty - sat['son_cy']))
    # EKF yatay konumu ile gerçek konum farkı (dünya), mod etkinken
    m = d['x_ekf_kuzey'].notna() & d['x_gercek'].notna()
    if t_val is not None:
        m &= d['t_gz'] >= (oz.get('t_mod_devrede') or t_val)
    if t_tem is not None:
        m &= d['t_gz'] <= t_tem
    if m.any():
        ex = off_e + d.loc[m, 'y_ekf_dogu'] - d.loc[m, 'x_gercek']
        ey = off_n + d.loc[m, 'x_ekf_kuzey'] - d.loc[m, 'y_gercek']
        sat['ekf_yatay_fark_max'] = float(np.hypot(ex, ey).max())
    sat.update({
        'temas_yeri_uygun': oz.get('temas_yeri_uygun'),
        'basarili_v10': oz.get('basarili_v10'),
        'temas_hizi': oz.get('temas_dikey_hiz_gercek_hesap_mps'),
        'abort_sayisi': oz.get('abort_sayisi'),
        'hold_sayisi': oz.get('hold_sayisi'),
        'tekrar': tekrar_var(ep_dir),
    })
    return sat, a, d, kutu


# -- şekil ---------------------------------------------------------------------
RENK = {'yakin': '#eb6834', 'diger': '#2a78d6'}    # dataviz kategorik 2, 1
INK, INK2, SOLUK, IZGARA, YUZEY = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#fcfcfb'


def ciz(ozet, adaylar, kutu, yol, r_kenar=2.0):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': '#c3c2b7',
                         'axes.labelcolor': INK2, 'xtick.color': INK2,
                         'ytick.color': INK2, 'axes.titlesize': 10,
                         'axes.titleweight': 'bold', 'axes.titlelocation': 'left'})
    fig, ax = plt.subplots(1, 3, figsize=(15.5, 5.0),
                           gridspec_kw={'width_ratios': [1.0, 1.45, 1.15]})
    fig.patch.set_facecolor(YUZEY)
    for a in ax:
        a.set_facecolor(YUZEY)
        for k in ('top', 'right'):
            a.spines[k].set_visible(False)
    grup = np.where(ozet['val_kp_aday_hesap'] < r_kenar, 'yakin', 'diger')
    n_y, n_d = int((grup == 'yakin').sum()), int((grup == 'diger').sum())
    etiket = {'yakin': f"VALIDATE'te gerçek kenar payı < {r_kenar:g} m ({n_y})",
              'diger': f'diğer ({n_d})'}

    # (a) üstten görünüş
    a = ax[0]
    x0, y0, x1, y1 = kutu
    for pay, ls in ((0, '-'), (1.0, ':'), (r_kenar, '--')):
        a.plot([x0 + pay, x1 - pay, x1 - pay, x0 + pay, x0 + pay],
               [y0 + pay, y0 + pay, y1 - pay, y1 - pay, y0 + pay],
               color=INK if pay == 0 else SOLUK, lw=1.2 if pay == 0 else 0.9, ls=ls)
    a.text(x1 - r_kenar - 0.1, y1 - r_kenar - 0.15, f'{r_kenar:g} m', color=SOLUK,
           ha='right', va='top', fontsize=8)
    a.text(x1 - 1.0 - 0.1, y1 - 1.0 - 0.15, '1 m', color=SOLUK, ha='right',
           va='top', fontsize=8)
    dogus = {}
    for r, g in zip(ozet.itertuples(), grup):
        c = RENK[g]
        a.plot([r.val_cx, r.temas_x], [r.val_cy, r.temas_y], color=c, lw=1.0, zorder=2)
        a.plot(r.secim_cx, r.secim_cy, 'x', color=c, ms=6, mew=1.4, zorder=3)
        a.plot(r.val_cx, r.val_cy, 'o', mfc=YUZEY, mec=c, ms=7, mew=1.6, zorder=4)
        a.plot(r.temas_x, r.temas_y, 'o', color=c, ms=5, mec=YUZEY, mew=1.0, zorder=5)
        dx, dy = (float(v) for v in r.dogus.split(',')[:2])
        dogus.setdefault((dx, dy), []).append(f't{r.tohum}')
    for (dx, dy), ts in dogus.items():
        a.plot(dx, dy, '^', mfc=YUZEY, mec=INK2, ms=8, mew=1.2)
        a.annotate(f'doğuş {ts[0]}', (dx, dy), xytext=(6, 4),
                   textcoords='offset points', color=INK2, fontsize=8)
    a.set_aspect('equal')
    a.set_xlim(-9, 9)
    a.set_ylim(-11, 9)
    a.set_xlabel('doğu (m, dünya)')
    a.set_ylabel('kuzey (m, dünya)')
    a.set_title('a) Aday ve temas noktaları (üstten)')
    a.legend(handles=[
        Line2D([], [], ls='', marker='x', color=INK2, label='aday, seçildiği an'),
        Line2D([], [], ls='', marker='o', mfc=YUZEY, mec=INK2,
               label='aday, VALIDATE girişi'),
        Line2D([], [], ls='', marker='o', color=INK2, label='gerçek temas (ölçülen)'),
        Line2D([], [], ls='', marker='^', mfc=YUZEY, mec=INK2, label='doğuş')],
        loc='lower right', fontsize=7.5, frameon=False, handletextpad=0.3,
        borderaxespad=0.2)

    # (b) adayın gerçek kenar payı, zaman içinde
    a = ax[1]
    a.axhline(0, color=INK, lw=1.0)
    a.axhline(1.0, color=SOLUK, lw=0.9, ls=':')
    a.axhline(r_kenar, color=SOLUK, lw=0.9, ls='--')
    a.axvline(0, color=IZGARA, lw=1.0)
    for r, g in zip(ozet.itertuples(), grup):
        b = adaylar[adaylar['ep_id'] == r.ep_id]
        b = b[b['t_alma'] <= r.t_temas]
        t = np.append(b['t_alma'].to_numpy(), r.t_temas) - r.t_validate
        k = np.append(b['kp_aday_hesap'].to_numpy(), b['kp_aday_hesap'].iloc[-1])
        a.step(t, k, where='post', color=RENK[g], lw=1.3, alpha=0.85)
        a.plot(r.t_temas - r.t_validate, r.temas_kp_hesap, 'o', color=RENK[g],
               ms=6, mec=YUZEY, mew=1.0, zorder=4)
    a.text(-15.5, r_kenar + 0.06, f'r_class_edge = {r_kenar:g} m', color=SOLUK,
           fontsize=8, va='bottom')
    a.text(-15.5, 1.06, '1 m', color=SOLUK, fontsize=8, va='bottom')
    a.text(-15.5, 0.06, 'platform kenarı', color=INK2, fontsize=8, va='bottom')
    a.text(0.2, 4.15, 'VALIDATE girişi', color=INK2, fontsize=8, va='top')
    a.set_xlim(-16, 28)
    a.set_ylim(-1.4, 4.2)
    a.set_xlabel('t − t_validate (s)')
    a.set_ylabel('adayın gerçek kenar payı (m, _hesap)')
    a.set_title('b) Adayın platform kenarına gerçek uzaklığı; nokta = temas')
    a.grid(axis='y', color=IZGARA, lw=0.6)
    a.set_axisbelow(True)
    a.legend(handles=[Line2D([], [], color=RENK[g], lw=2, label=etiket[g])
                      for g in ('yakin', 'diger')],
             loc='lower right', fontsize=8, frameon=False)

    # (c) VALIDATE girişinde: harita kenar payı -> düzeltmeler -> gerçek
    a = ax[2]
    sut = ['val_radius_m', 'val_radius_maske_dogru_hesap',
           'val_radius_maske_dogru_yaw_hesap', 'val_kp_aday_hesap']
    adlar = ['harita\nradius_m\n(ölçülen)', 'maske,\ndoğru h\n(_hesap)',
             'maske, doğru h\n+ yaw düzeltme\n(_hesap)', 'gerçek\nkenar payı\n(_hesap)']
    xs = np.arange(len(sut))
    a.axhline(r_kenar, color=SOLUK, lw=0.9, ls='--')
    a.axhline(0, color=INK, lw=1.0)
    for g in ('diger', 'yakin'):
        for r in ozet[grup == g].itertuples():
            y = [getattr(r, c) for c in sut]
            a.plot(xs, y, color=RENK[g], lw=1.0, alpha=0.7, marker='o', ms=4.5,
                   mec=YUZEY, mew=0.8)
    o = ozet[grup == 'yakin']
    adlar = [f'{ad}\n{o[c].min():.2f}–{o[c].max():.2f}' for ad, c in zip(adlar, sut)]
    a.set_xticks(xs)
    a.set_xticklabels(adlar, fontsize=8)
    for lb in a.get_xticklabels():
        lb.set_linespacing(1.25)
    a.text(-0.3, 4.15, 'etiketlerin son satırı: turuncu grubun aralığı (m)',
           color=INK2, fontsize=7.5, va='top')
    a.set_xlim(-0.35, len(sut) - 0.65)
    a.set_ylim(-0.4, 4.2)
    a.set_ylabel('adaydan en yakın çim dışı hücreye (m)')
    a.set_title('c) VALIDATE girişinde kenar payı: harita → gerçek')
    a.grid(axis='y', color=IZGARA, lw=0.6)
    a.set_axisbelow(True)
    a.text(len(sut) - 0.7, r_kenar + 0.06, f'{r_kenar:g} m', color=SOLUK,
           fontsize=8, ha='right', va='bottom')
    fig.tight_layout()
    fig.savefig(yol, dpi=150, facecolor=YUZEY)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    ap.add_argument('--cikis', default=os.path.expanduser(
        '~/eland_veri/_w5_kenar_2026-10-14'))
    args = ap.parse_args()
    os.makedirs(args.cikis, exist_ok=True)

    dirs = []
    for kol in KOLLAR:
        dirs += sorted(glob.glob(os.path.join(args.kok, kol, 'veri_w5', '*')))
    satirlar, adaylar = [], []
    kutu = None
    for ep in dirs:
        sat, a, _, kutu = bolum(ep)
        satirlar.append(sat)
        adaylar.append(a)
        print(f"{sat['ep_id']:24s} VALIDATE kenar payı {sat.get('val_kp_aday_hesap', np.nan):5.2f} m, "
              f"temas kenar payı {sat.get('temas_kp_hesap', np.nan):5.2f} m")
    ozet = pd.DataFrame(satirlar)
    adaylar = pd.concat(adaylar)
    adaylar.to_csv(os.path.join(args.cikis, 'w5_aday_olaylari.csv'),
                   index=False, float_format='%.3f')
    ozet.to_csv(os.path.join(args.cikis, 'w5_kenar_payi.csv'), index=False,
                float_format='%.3f')
    ciz(ozet, adaylar, kutu, os.path.join(args.cikis, 'w5_kenar_payi.png'))
    print(f"{len(ozet)} bölüm; run_sim.log tekrarı olan: {int(ozet['tekrar'].fillna(False).sum())}; "
          f"çıktı: {args.cikis}")


if __name__ == '__main__':
    main()
