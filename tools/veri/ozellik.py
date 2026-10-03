#!/usr/bin/env python3
"""Image-space features of the region a vision-based descent law would use.

Pure numpy/OpenCV so the same numbers can be recomputed offline from the saved
masks (maskeler.npz) without ROS. The region is the one detector_node's
``on_mask`` uses for ``area_ratio``: the 8-connected safe-class component
under the image centre. ``rho`` and ``view_bounded`` here therefore match the
detector's definition exactly; everything else is extra.
"""
import math

import cv2
import numpy as np

#: Safe classes, as in eland_params.yaml detector_node.safe_classes.
SAFE_CLASSES = (0, 1)

#: Column order of the per-mask feature table.
FEATURE_COLUMNS = (
    'rho', 'view_bounded', 'bolge_piksel', 'ic_daire_yaricapi_px',
    'ic_daire_merkez_px', 'sinir_uzunlugu_px', 'sinir_ic_piksel',
    'merkez_x', 'merkez_y', 'bbox_x0', 'bbox_x1', 'bbox_y0', 'bbox_y1',
    'kenara_degen_taraf_sayisi', 'sinif_siniri_piksel', 'merkez_sinif',
)


def footprint_factor(hfov_rad: float, width_px: int, height_px: int) -> float:
    """Ground area seen per unit height squared: area = factor * h**2.

    4.22 for the 99.7 deg, 4:3 segmentation camera.
    """
    t = math.tan(hfov_rad / 2.0)
    return 4.0 * t * t * (height_px / float(width_px))


def class_edge_pixels(mask: np.ndarray) -> int:
    """Pixels with a 4-neighbour of a different class, over the whole frame."""
    edge = np.zeros(mask.shape, dtype=bool)
    edge[:, :-1] |= mask[:, :-1] != mask[:, 1:]
    edge[:, 1:] |= mask[:, 1:] != mask[:, :-1]
    edge[:-1, :] |= mask[:-1, :] != mask[1:, :]
    edge[1:, :] |= mask[1:, :] != mask[:-1, :]
    return int(edge.sum())


def features(mask: np.ndarray, safe_classes=SAFE_CLASSES) -> dict:
    """Features of the safe region under the image centre.

    Definitions (pixels, image coordinates, x right, y down):
      rho                    region pixels / frame pixels (detector's area_ratio)
      view_bounded           1 if the region touches no frame edge
      ic_daire_yaricapi_px   largest circle inside the region; the frame edge
                             counts as a boundary (beyond it is not known)
      ic_daire_merkez_px     the same distance, evaluated at the image centre
      sinir_uzunlugu_px      length of the region's outer contour, frame-edge
                             stretches included
      sinir_ic_piksel        region boundary pixels NOT on the frame edge, i.e.
                             boundary against another class
      merkez_x/y             region centroid
      kenara_degen_taraf_sayisi  how many of the 4 frame edges it touches
      sinif_siniri_piksel    class-boundary pixels in the whole frame
      merkez_sinif           class of the centre pixel
    """
    h, w = mask.shape
    cy, cx = h // 2, w // 2
    out = {k: float('nan') for k in FEATURE_COLUMNS}
    out['sinif_siniri_piksel'] = class_edge_pixels(mask)
    out['merkez_sinif'] = int(mask[cy, cx])

    safe = np.isin(mask, safe_classes).astype(np.uint8)
    _, labels = cv2.connectedComponents(safe, connectivity=8)
    lab = int(labels[cy, cx])
    if lab == 0:
        out.update(rho=0.0, view_bounded=0, bolge_piksel=0,
                   ic_daire_yaricapi_px=0.0, ic_daire_merkez_px=0.0,
                   sinir_uzunlugu_px=0.0, sinir_ic_piksel=0,
                   kenara_degen_taraf_sayisi=0)
        return out

    region = (labels == lab).astype(np.uint8)
    n_px = int(region.sum())
    sides = (bool(region[0, :].any()), bool(region[-1, :].any()),
             bool(region[:, 0].any()), bool(region[:, -1].any()))

    # Zero border = the frame edge is a boundary for the inscribed circle.
    dt = cv2.distanceTransform(np.pad(region, 1), cv2.DIST_L2,
                               cv2.DIST_MASK_PRECISE)[1:-1, 1:-1]
    contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_NONE)
    perimeter = float(sum(cv2.arcLength(c, True) for c in contours))

    # Boundary against another class: region pixels with a 4-neighbour that is
    # inside the frame and outside the region.
    inner = np.zeros_like(region, dtype=bool)
    r = region.astype(bool)
    inner[:, :-1] |= r[:, :-1] & ~r[:, 1:]
    inner[:, 1:] |= r[:, 1:] & ~r[:, :-1]
    inner[:-1, :] |= r[:-1, :] & ~r[1:, :]
    inner[1:, :] |= r[1:, :] & ~r[:-1, :]

    ys, xs = np.nonzero(region)
    out.update(
        rho=n_px / float(h * w),
        view_bounded=int(not any(sides)),
        bolge_piksel=n_px,
        ic_daire_yaricapi_px=float(dt.max()),
        ic_daire_merkez_px=float(dt[cy, cx]),
        sinir_uzunlugu_px=perimeter,
        sinir_ic_piksel=int(inner.sum()),
        merkez_x=float(xs.mean()),
        merkez_y=float(ys.mean()),
        bbox_x0=int(xs.min()), bbox_x1=int(xs.max()),
        bbox_y0=int(ys.min()), bbox_y1=int(ys.max()),
        kenara_degen_taraf_sayisi=int(sum(sides)),
    )
    return out
