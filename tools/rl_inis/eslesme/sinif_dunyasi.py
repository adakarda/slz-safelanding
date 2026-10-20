"""F1 match test, part 1: a copy of the orto_dji0097 world whose photo is its class map.

Each class gets a saturated hue, so the class can be read back from what the
Gazebo RGB camera renders, independently of the environment's own projection.
Writes ~/eland_veri/modeller/orto_dji0097_sinif/ and ~/eland_veri/dunyalar/orto_dji0097_sinif.{sdf,yaml}.
"""
import os
import re

import numpy as np
from PIL import Image

from eland_rl.scene import MESSI_TO_TAXONOMY, lookup_table

# hue per taxonomy class (deg); 7 (void) is black and reads back as unknown
TON = {0: 120, 1: 240, 2: 300, 3: 0, 4: 180, 5: 60, 6: 30}


def renk(ton):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(ton / 360.0, 1.0, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


PALET = np.zeros((8, 3), np.uint8)
for k, t in TON.items():
    PALET[k] = renk(t)

if __name__ == '__main__':
    H = os.path.expanduser('~')
    idx = np.array(Image.open(f'{H}/v3_test/maske/fotomask/DJI_0097.png'))
    sinif = lookup_table(MESSI_TO_TAXONOMY)[idx]
    md = f'{H}/eland_veri/modeller/orto_dji0097_sinif'
    os.makedirs(f'{md}/materials/textures', exist_ok=True)
    Image.fromarray(PALET[sinif]).save(f'{md}/materials/textures/sinif.png', optimize=True)

    kaynak = open(f'{H}/eland_veri/modeller/orto_dji0097/model.sdf').read()
    sdf = kaynak.replace('model://orto_dji0097/materials/textures/dji0097.jpg',
                         'model://orto_dji0097_sinif/materials/textures/sinif.png')
    sdf = sdf.replace('<model name="orto_dji0097">', '<model name="orto_dji0097_sinif">')
    sdf = re.sub(r'<!--.*?-->', '<!-- DJI_0097 class map (eland_rl match test, F1): hue per class, '
                 'same size and pose as orto_dji0097. -->', sdf, count=1, flags=re.S)
    open(f'{md}/model.sdf', 'w').write(sdf)
    open(f'{md}/model.config', 'w').write(
        '<?xml version="1.0"?>\n<model><name>orto_dji0097_sinif</name><version>1.0</version>'
        '<sdf version="1.9">model.sdf</sdf>\n<description>DJI_0097 class map at true scale, '
        'for the eland_rl environment/Gazebo match test.</description></model>\n')

    dn = f'{H}/eland_veri/dunyalar'
    w = open(f'{dn}/orto_dji0097.sdf').read()
    w = w.replace('<world name="orto_dji0097">', '<world name="orto_dji0097_sinif">')
    w = w.replace('<uri>model://orto_dji0097</uri>', '<uri>model://orto_dji0097_sinif</uri>')
    open(f'{dn}/orto_dji0097_sinif.sdf', 'w').write(w)
    y = open(f'{dn}/orto_dji0097.yaml').read()
    y = y.replace('dunya_id: orto_dji0097', 'dunya_id: orto_dji0097_sinif')
    y = y.replace('gz_world: orto_dji0097', 'gz_world: orto_dji0097_sinif')
    open(f'{dn}/orto_dji0097_sinif.yaml', 'w').write(y)
    print('yazildi:', md, f'{dn}/orto_dji0097_sinif.sdf', 'palet', PALET.tolist())
