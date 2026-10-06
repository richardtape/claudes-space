"""Does it matter *where* the ozone is missing?

A polar ozone hole is not a uniform thinning: the ozone is destroyed in the lower
stratosphere and survives above it. The beams that light the twilight zenith skim
higher as the sun sinks. So compare, at the zenith through the evening:

  polar_300   a polar-like layer (peak 18 km), 300 DU
  hole_110    the same layer with 97% removed between 12 and 26 km: 110 DU left
  even_110    the same layer scaled down uniformly to the same 110 DU
  none        no ozone

Writes data/hole.json.  .venv/bin/python hole_experiment.py
"""
import json
import os
import time

import numpy as np

from skymodel import LAM, Sky, spectrum_to_xyz, xyz_to_xy

HERE = os.path.dirname(os.path.abspath(__file__))
Z = np.array([[0.0, 0.0, 1.0]])
ELEVS = [round(e, 1) for e in np.arange(2, -12.01, -1.0)]
GAP = (12e3, 26e3, 0.03)
PEAK = 18e3


def main():
    hole = Sky(300, o3_peak=PEAK, o3_gap=GAP)
    left = hole.ozone_column_du
    cases = {
        "polar_300": dict(ozone_du=300, o3_peak=PEAK),
        "hole_110": dict(ozone_du=300, o3_peak=PEAK, o3_gap=GAP),
        "even_110": dict(ozone_du=left, o3_peak=PEAK),
        "none": dict(ozone_du=0),
    }
    out = {"lambda_nm": LAM.tolist(), "gap": GAP, "peak": PEAK, "hole_column_du": left, "cases": {}}
    for name, kw in cases.items():
        sky = Sky(**kw)
        rows = []
        for i, se in enumerate(ELEVS):
            t = time.time()
            n = 1_000_000 if se <= -6 else 400_000
            L = sky.single(Z, se) + sky.multi(Z, se, n, seed=900 + i, max_dh=300)
            X = spectrum_to_xyz(L)[0]
            xy = xyz_to_xy(X)
            rows.append({"sun": se, "Y": float(X[1]), "xy": [float(xy[0]), float(xy[1])], "spec": L[0].tolist()})
            print(f"{name:>10} sun {se:+5.1f}  xy {xy[0]:.4f} {xy[1]:.4f}  ({time.time() - t:.1f}s)", flush=True)
        out["cases"][name] = {"ozone_du": sky.ozone_column_du, "rows": rows}
        json.dump(out, open(os.path.join(HERE, "data", "hole.json"), "w"))


if __name__ == "__main__":
    main()
