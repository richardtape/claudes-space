"""Render the whole sky (both halves, by symmetry about the sun's azimuth) for a range of
sun elevations and ozone columns. Saves CIE XYZ on an (azimuth, elevation) grid.

Single scattering is computed on the fine grid; multiple scattering by Monte Carlo on a
coarse grid (it is smooth) and interpolated onto the fine one in make_images.py.

    .venv/bin/python render_frames.py            # all ozone cases
    .venv/bin/python render_frames.py 300        # one case
"""
import math
import os
import sys
import time

import numpy as np

from skymodel import Sky, spectrum_to_xyz, LIB, _p, NL

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "raw", "frames")

ELEVS = [round(e, 1) for e in np.arange(10, -14.01, -0.5)]
AZ = np.arange(0, 181, 1.0)                     # degrees from the sun's azimuth
V = np.linspace(0, 1, 121)
EL = 90 * (0.25 * V + 0.75 * V**2)              # dense near the horizon
MS_AZ = np.array([0, 5, 10, 20, 30, 45, 60, 80, 100, 120, 140, 160, 180.0])
MS_EL = np.array([0, 1.5, 4, 8, 14, 24, 40, 62, 90.0])
MS_PATHS = 16000          # x3 once the sun is 6 deg down, where the sky is all multiple scattering


def dirs(az_deg, el_deg):
    A, E = np.meshgrid(np.radians(az_deg), np.radians(el_deg), indexing="ij")
    return np.stack([np.cos(E) * np.cos(A), np.cos(E) * np.sin(A), np.sin(E)], axis=-1)


def direct_sun(sky, se):
    """Transmittance spectrum of the direct beam from the observer towards the sun."""
    if se < -1.0:
        return np.zeros(NL)
    lc, ec = np.zeros(3), np.zeros(3)
    ok = LIB.sun_columns_test(0.0, math.radians(max(se, 0.0)), _p(lc), _p(ec))
    if not ok & 1:
        return np.zeros(NL)
    return np.exp(-(sky.sext * ec[:, None]).sum(axis=0))


def render_case(du):
    os.makedirs(OUT, exist_ok=True)
    sky = Sky(ozone_du=du)
    D = dirs(AZ, EL).reshape(-1, 3)
    Dm = dirs(MS_AZ, MS_EL).reshape(-1, 3)
    for i, se in enumerate(ELEVS):
        path = os.path.join(OUT, f"o3_{du}_sun_{se:+05.1f}.npz")
        if os.path.exists(path):
            continue
        t = time.time()
        ss = sky.single(D, se)
        ms = sky.multi(Dm, se, MS_PATHS * (3 if se <= -6 else 1), seed=7000 + i, max_dh=300)
        np.savez_compressed(
            path,
            ss_xyz=spectrum_to_xyz(ss).reshape(len(AZ), len(EL), 3).astype(np.float32),
            ms_xyz=spectrum_to_xyz(ms).reshape(len(MS_AZ), len(MS_EL), 3).astype(np.float32),
            ms_spec=ms.reshape(len(MS_AZ), len(MS_EL), NL).astype(np.float32),
            direct=direct_sun(sky, se),
            az=AZ, el=EL, ms_az=MS_AZ, ms_el=MS_EL, sun=se, ozone_du=du,
        )
        print(f"o3 {du:3d}  sun {se:+5.1f}  {time.time() - t:5.1f}s", flush=True)


if __name__ == "__main__":
    cases = [int(a) for a in sys.argv[1:]] or [300, 0, 100]
    for du in cases:
        render_case(du)
