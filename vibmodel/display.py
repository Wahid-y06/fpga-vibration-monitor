"""Pixel-exact model of rtl/vib_display.v (4-bit RGB per channel)."""
from __future__ import annotations

import numpy as np

from .reference import bar_height

X0, SP, BW, MK = 60, 112, 64, 8
BASE = 440
STRIP_Y0, STRIP_Y1 = 16, 40
W, H = 640, 480

LEVEL_RGB = {0: (0x0, 0xB, 0x2), 1: (0xF, 0xC, 0x0), 2: (0xF, 0x1, 0x1)}
C_BG, C_GRID, C_AXIS = (0x1, 0x1, 0x2), (0x3, 0x3, 0x4), (0xC, 0xC, 0xC)
C_WARN, C_CRIT = (0xF, 0xD, 0x0), (0xF, 0x0, 0x0)


def render(energy, warn, crit, levels, overall) -> np.ndarray:
    n = len(energy)
    hb = [bar_height(e) for e in energy]
    hw = [bar_height(v) for v in warn]
    hc = [bar_height(v) for v in crit]
    strip_x1 = X0 + (n - 1) * SP + BW
    img = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            hit_bar = hit_warn = hit_crit = False
            bar_lv = 0
            for c in range(n):
                x0 = X0 + c * SP
                if x0 <= x < x0 + BW and y < BASE and y >= BASE - hb[c]:
                    hit_bar, bar_lv = True, levels[c]
                if x + MK >= x0 and x < x0 + BW + MK:
                    if y in (BASE - hc[c], BASE - hc[c] - 1):
                        hit_crit = True
                    if y in (BASE - hw[c], BASE - hw[c] - 1):
                        hit_warn = True
            if STRIP_Y0 <= y < STRIP_Y1 and X0 <= x < strip_x1:
                rgb = LEVEL_RGB[overall]
            elif hit_crit:
                rgb = C_CRIT
            elif hit_warn:
                rgb = C_WARN
            elif hit_bar:
                rgb = LEVEL_RGB[bar_lv]
            elif y in (BASE, BASE + 1) and X0 - 20 <= x < strip_x1 + 20:
                rgb = C_AXIS
            elif STRIP_Y1 < y < BASE and (BASE - y) & 31 == 0:
                rgb = C_GRID
            else:
                rgb = C_BG
            img[y, x] = rgb
    return img


def read_ppm(path) -> np.ndarray:
    with open(path, encoding="ascii") as fh:
        tokens = fh.read().split()
    assert tokens[0] == "P3", "not an ASCII PPM"
    w, h = int(tokens[1]), int(tokens[2])
    values = np.array(tokens[4:4 + w * h * 3], dtype=np.uint8)
    return values.reshape(h, w, 3)


def to_png(img4: np.ndarray, path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.imsave(path, (img4.astype(np.float32) / 15.0).clip(0, 1))
