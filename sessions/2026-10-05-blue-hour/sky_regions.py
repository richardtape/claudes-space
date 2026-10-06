"""Colours of named parts of the rendered sky, with and without ozone: the Belt of Venus
and the Earth's shadow opposite the sun, the glow above the sunset point, the zenith.

Reads the frames from render_frames.py (total = SS + interpolated MS, as in the images).
    .venv/bin/python sky_regions.py
"""
import os

import numpy as np

from make_images import load, total_xyz
from skymodel import xyz_to_xy

HERE = os.path.dirname(os.path.abspath(__file__))


def at(xyz, az, el, a, e):
    i = int(np.argmin(np.abs(az - a)))
    j = int(np.argmin(np.abs(el - e)))
    return xyz[i, j]


def main():
    print("antisolar sky (azimuth 180): chromaticity x, y by elevation; Y relative to zenith")
    for se in (-1.0, -2.0, -3.0, -4.0, -5.0):
        for du in (300, 0):
            f = load(du, se)
            xyz = total_xyz(f)
            az, el = f["az"], f["el"]
            zen = xyz[0, -1, 1]
            cells = []
            for e in (1, 3, 6, 10, 15, 25):
                v = at(xyz, az, el, 180, e)
                xy = xyz_to_xy(v)
                cells.append(f"{e:2d}deg {xy[0]:.3f},{xy[1]:.3f} ({v[1] / zen:.2f})")
            print(f" sun {se:+.0f} O3 {du:3d}: " + "  ".join(cells))
    print("\nsunward sky (azimuth 0) at 20 deg elevation (where 'purple light' is reported):")
    for se in (-2.0, -3.0, -4.0, -5.0, -6.0):
        row = []
        for du in (300, 0):
            f = load(du, se)
            v = at(total_xyz(f), f["az"], f["el"], 0, 20)
            xy = xyz_to_xy(v)
            row.append(f"O3 {du}: {xy[0]:.3f},{xy[1]:.3f}")
        print(f" sun {se:+.0f}: " + "   ".join(row))


if __name__ == "__main__":
    main()
