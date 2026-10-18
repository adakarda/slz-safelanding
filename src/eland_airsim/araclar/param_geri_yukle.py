"""Gazebo rootfs'unun parameters.bson'unu, AirSim kosularindan onceki son Gazebo ucusunun degerlerine geri getir.

    python3 param_geri_yukle.py GAZEBO.ulg ROOTFS/parameters.bson [--yaz]

Neden: run_airsim.sh'in PX4'u (2026-10-18 00:03-03:00) -w verilmedigi icin build/rootfs'ta calisti ve
Gazebo'nun kayitli parametrelerini SYS_AUTOSTART 10016 ile ezdi. Anahtar kumesi: dosyadaki anahtarlar
(PX4'un kaydettigi turden: kalibrasyon, ucus sayaclari, ...) + ULog'da Gazebo'ya ozgu kalici degerler
(COM_RC_LOSS_T, MPC_Z_VEL_MAX_DN, MPC_Z_V_AUTO_DN). Degerler ve turleri ULog'dan. --yaz olmadan yalniz gosterir;
--yaz ile eski dosyayi .airsim_yedek olarak saklar, parameters.bson ve parameters_backup.bson'u yazar.
"""
import os
import shutil
import struct
import sys

from pyulog import ULog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from param_bson import oku  # noqa: E402

ulg, bson_yol = sys.argv[1], sys.argv[2]
yaz = '--yaz' in sys.argv
u = ULog(ulg, message_name_filter_list=[], parse_header_only=True)
gz = u.initial_parameters
mevcut = oku(bson_yol)
anahtar = sorted(set(mevcut) | {'COM_RC_LOSS_T', 'MPC_Z_VEL_MAX_DN', 'MPC_Z_V_AUTO_DN'})
eksik = [k for k in anahtar if k not in gz]
anahtar = [k for k in anahtar if k in gz]
print(f'{len(anahtar)} parametre geri yuklenecek; ULog\'da olmayan (atlanan): {eksik}')
govde = b''
for k in anahtar:
    v = gz[k]
    if isinstance(v, int):
        govde += b'\x10' + k.encode() + b'\0' + struct.pack('<i', v)
    else:
        govde += b'\x01' + k.encode() + b'\0' + struct.pack('<d', float(v))
    if mevcut.get(k) != v:
        print(f'  {k:20s} {str(mevcut.get(k, "-")):>14s} -> {v}')
belge = struct.pack('<i', len(govde) + 5) + govde + b'\0'
if yaz:
    shutil.copy2(bson_yol, bson_yol + '.airsim_yedek')
    for yol in (bson_yol, os.path.join(os.path.dirname(bson_yol), 'parameters_backup.bson')):
        with open(yol, 'wb') as f:
            f.write(belge)
    geri = oku(bson_yol)
    assert all((geri[k] == gz[k]) if isinstance(gz[k], int) else abs(geri[k] - gz[k]) < 1e-5 for k in anahtar)
    print('yazildi ve geri okundu:', bson_yol, '(eski dosya: .airsim_yedek)')
