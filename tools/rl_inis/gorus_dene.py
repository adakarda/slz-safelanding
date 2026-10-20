import cv2, numpy as np
from eland_rl.camera import Camera, rotation
from eland_rl.scene import Scene
from eland_rl.policy_node import view_image
sc = Scene.from_messi('/home/arda/v3_test/foto/fotoo/DJI_0097.JPG', '/home/arda/v3_test/maske/fotomask/DJI_0097.png', size_m=(64.02, 42.68))
sem, _ = Camera().semantic_depth(sc, np.array([1.6, -8.1, 24.9]), rotation((0, 0, 1), np.radians(229.3)))
im = np.concatenate([view_image(sem, 3, 24.9, 0.3), view_image(sem, 9, 24.9, 0.3)], 1)
cv2.imwrite('/home/arda/rl_inis/gorus_dene.png', cv2.cvtColor(im, cv2.COLOR_RGB2BGR)); print(im.shape)
