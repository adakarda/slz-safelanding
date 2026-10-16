"""The simulated down-looking camera, by ray-plane intersection.

Same camera as the Gazebo RGB sensor on x500_seg_cam_rgb_down: 640x480,
HFOV 1.74 rad (99.7 deg), fixed to the body, looking straight down. Same ray
model as v3_golge.gt_kare(): a pixel (u, v) looks along

    d_body = (-y_d, -x_r, -1),   x_r = (u + 0.5 - W/2) / f,   y_d = (v + 0.5 - H/2) / f

in the FLU body frame, f = (W/2) / tan(HFOV/2). The optical-axis component of
d_body is 1, so the ray parameter t at the ground IS the z-depth a Gazebo depth
camera reports for that pixel.

WHAT THE POLICY SEES
The policy gets a 128x128 image. On the vehicle it will come from cv2.resize(
label_image, (128, 128), INTER_NEAREST) of the 320x240 label topic, so here the
128x128 rays are exactly the label pixels that resize would pick. Training and
deployment then sample the ground at the same points.
"""
import math

import cv2
import numpy as np

HFOV = 1.74
SENSOR_W, SENSOR_H = 640, 480
LABEL_W, LABEL_H = 320, 240


def nearest_source_index(src, dst):
    """Source pixel index cv2.resize(INTER_NEAREST) takes for each output pixel."""
    return np.minimum(np.floor(np.arange(dst) * (src / dst)).astype(np.intp), src - 1)


def body_rays(w, h, cols=None, rows=None, hfov=HFOV):
    """(len(rows), len(cols), 3) body-frame rays for the given pixel columns/rows of a w x h image."""
    f = (w / 2) / math.tan(hfov / 2)
    cols = np.arange(w) if cols is None else cols
    rows = np.arange(h) if rows is None else rows
    u, v = np.meshgrid(cols + 0.5, rows + 0.5)
    xr, yd = (u - w / 2) / f, (v - h / 2) / f
    return np.stack([-yd, -xr, -np.ones_like(xr)], -1)


def policy_rays(size=128):
    """Rays of the policy image: the label pixels INTER_NEAREST keeps."""
    return body_rays(LABEL_W, LABEL_H,
                     cols=nearest_source_index(LABEL_W, size),
                     rows=nearest_source_index(LABEL_H, size))


def rotation(tilt_vec, yaw):
    """Body->world rotation of a multicopter whose thrust axis is tilt_vec.

    tilt_vec is the body z axis in world coordinates (unnormalised), e.g.
    (a_x, a_y, g) for a vehicle accelerating with a. Heading is kept at yaw.
    """
    b3 = np.asarray(tilt_vec, float)
    b3 = b3 / np.linalg.norm(b3)
    c1 = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    b2 = np.cross(b3, c1)
    b2 /= np.linalg.norm(b2)
    b1 = np.cross(b2, b3)
    return np.stack([b1, b2, b3], 1)


def ground_hits(rays, cam_pos, R):
    """World (X, Y) where each ray meets z = 0, and its z-depth; inf if it never does."""
    d = rays @ R.T
    down = -d[..., 2]
    t = np.where(down > 1e-6, cam_pos[2] / np.maximum(down, 1e-6), np.inf)
    X = cam_pos[0] + t * d[..., 0]
    Y = cam_pos[1] + t * d[..., 1]
    return X, Y, t


class Camera:
    """Renders what the policy sees, and the full-resolution views tests need."""

    def __init__(self, size=128, hfov=HFOV):
        self.size = size
        self.rays = policy_rays(size)
        self.hfov = hfov

    def semantic_depth(self, scene, cam_pos, R):
        X, Y, t = ground_hits(self.rays, cam_pos, R)
        sem = np.full(t.shape, 7, np.uint8)
        ok = np.isfinite(t)
        sem[ok] = scene.classes_at(X[ok], Y[ok])
        return sem, t

    def inside_fraction(self, scene, cam_pos, R):
        X, Y, t = ground_hits(self.rays, cam_pos, R)
        return float((np.isfinite(t) & scene.inside(X, Y)).mean())

    @staticmethod
    def label_image(scene, cam_pos, R, w=LABEL_W, h=LABEL_H):
        """Full w x h class image, for comparison with Gazebo frames."""
        X, Y, t = ground_hits(body_rays(w, h), cam_pos, R)
        out = np.full(t.shape, 7, np.uint8)
        ok = np.isfinite(t)
        out[ok] = scene.classes_at(X[ok], Y[ok])
        return out

    @staticmethod
    def rgb_image(scene, cam_pos, R, w=SENSOR_W, h=SENSOR_H):
        """The photo as the RGB sensor would see it (bilinear), black off the photo."""
        if scene.photo is None:
            raise ValueError('scene was loaded without its photo')
        X, Y, t = ground_hits(body_rays(w, h), cam_pos, R)
        H, W = scene.photo.shape[:2]
        mx = ((X / scene.size[0] + 0.5) * W - 0.5).astype(np.float32)
        my = ((0.5 - Y / scene.size[1]) * H - 0.5).astype(np.float32)
        mx[~np.isfinite(t)] = -1
        return cv2.remap(scene.photo, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
