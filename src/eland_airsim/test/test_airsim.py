"""eland_airsim: class rules, segmentation decoding and frame conversion, without AirSim."""
import math
import re

import numpy as np

from eland_airsim import donusum, siniflar


def test_ci_pattern_matches_any_case():
    pat = re.compile('.*(' + siniflar.ci('car') + ').*')
    assert pat.match('SM_Car_01') and pat.match('policeCAR') and not pat.match('Cat_02')


def test_rules_priority_matches_airsim_order():
    got = siniflar.classify_names(['Lawn_3', 'Road_Main', 'House_A_Roof', 'CarPark_Car_1', 'Tree_Oak', 'Sky'])
    assert got == {'Lawn_3': 0, 'Road_Main': 2, 'House_A_Roof': 3, 'CarPark_Car_1': 5, 'Tree_Oak': 2}


def test_airsimnh_names_that_fooled_the_first_rules():
    names = ['Landscape', 'Garden_Chair_01', 'Car_Porch_Prefab', 'Pool_Table_01', 'Swimming_Pool_Floor',
             'Fir_01', 'Fireplace_01', 'Street_Sign_02', 'DeerBothBP3', 'Car_01']
    assert siniflar.classify_names(names) == {
        'Landscape': 0, 'Garden_Chair_01': 3, 'Car_Porch_Prefab': 3, 'Pool_Table_01': 3,
        'Swimming_Pool_Floor': 4, 'Fir_01': 2, 'Fireplace_01': 3, 'Street_Sign_02': 3, 'DeerBothBP3': 5,
        'Car_01': 5}


def test_palette_and_decode_roundtrip():
    pal = siniflar.palette()
    assert pal.shape == (256, 3) and tuple(pal[1]) == (153, 108, 6)
    labels = np.array([[0, 1, 2, 3], [4, 5, 6, 7]], np.uint8)
    rgb = pal[labels]
    for order, img in (('rgb', rgb), ('bgr', rgb[..., ::-1])):
        assert np.array_equal(siniflar.decode(img, pal, order), labels)
    classes = siniflar.labels_to_classes(labels)
    assert classes.tolist() == [[7, 0, 1, 2], [3, 4, 5, 6]]


def test_unmatched_colour_is_unknown():
    pal = siniflar.palette()
    img = np.full((2, 2, 3), 200, np.uint8)
    assert np.all(siniflar.decode(img, pal, 'rgb') == 0)


def test_ned_to_enu_position_and_yaw():
    # 10 m north, 5 m east, 20 m up; nose to the east (yaw +90 deg in NED)
    w, z = math.cos(math.pi / 4), math.sin(math.pi / 4)
    pos, q = donusum.ned_pose_to_enu(10.0, 5.0, -20.0, w, 0.0, 0.0, z)
    assert np.allclose(pos, (5.0, 10.0, 20.0))
    R = donusum.quat_to_matrix(*q)
    assert np.allclose(R @ [1, 0, 0], [1, 0, 0], atol=1e-9)    # FLU forward -> ENU east
    assert np.allclose(R @ [0, 0, 1], [0, 0, 1], atol=1e-9)    # FLU up -> ENU up


def test_level_frd_is_identity_flu_when_facing_north():
    pos, q = donusum.ned_pose_to_enu(0, 0, 0, 1.0, 0.0, 0.0, 0.0)
    R = donusum.quat_to_matrix(*q)
    assert np.allclose(R @ [1, 0, 0], [0, 1, 0], atol=1e-9)    # nose north = ENU +y


def test_camera_matrix_hfov():
    fx, fy, cx, cy = donusum.camera_matrix(640, 480, 99.7)
    assert abs(2 * math.degrees(math.atan(320 / fx)) - 99.7) < 1e-9 and (cx, cy) == (320, 240) and fx == fy
