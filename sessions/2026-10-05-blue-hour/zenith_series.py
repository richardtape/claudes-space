"""Zenith spectrum through the evening for several ozone columns (and a few aerosol loads).

Writes data/zenith.json: for each case and sun elevation, the single- and multiple-
scattering spectra at the zenith, plus a luminance-weighted histogram of the
altitude at which singly scattered zenith light was scattered.

    .venv/bin/python zenith_series.py            # main ozone series
    .venv/bin/python zenith_series.py --aerosol  # Lange et al. aerosol + a hazy case (fewer elevations)
    .venv/bin/python zenith_series.py --refine   # more paths for deep twilight (sun <= -6.5)
"""
import json
import os
import sys
import time

import numpy as np

from skymodel import LAM, Sky, spectrum_to_xyz, xyz_to_xy

HERE = os.path.dirname(os.path.abspath(__file__))
Z = np.array([[0.0, 0.0, 1.0]])
ELEVS = [round(e, 1) for e in np.arange(10, -14.01, -0.5)]
NB, HB = 100, 1000.0   # 1 km altitude bins to 100 km


def run_case(sky, elevs, label, paths_hi=1_000_000, paths_lo=300_000):
    rows = []
    for i, se in enumerate(elevs):
        t = time.time()
        ss, H = sky.single(Z, se, heights=(NB, HB))
        n = paths_hi if se <= -3 else paths_lo
        ms = sky.multi(Z, se, n, seed=1000 + i, max_dh=300)
        X = spectrum_to_xyz(ss + ms)[0]
        rows.append({
            "sun": se,
            "ss": ss[0].tolist(),
            "ms": ms[0].tolist(),
            "paths": n,
            "ss_heights": H[0].tolist(),
        })
        xy = xyz_to_xy(X)
        print(f"{label:>18} sun {se:+5.1f}  Y {X[1]:9.3g}  xy {xy[0]:.4f} {xy[1]:.4f}  ({time.time() - t:.1f}s)", flush=True)
    return rows


def main():
    out_path = os.path.join(HERE, "data", "zenith.json")
    data = json.load(open(out_path)) if os.path.exists(out_path) else {"lambda_nm": LAM.tolist(), "cases": {}}
    if "--refine" in sys.argv:
        # deep twilight is all multiple scattering and the noisiest part: add 3M more paths
        # to every point with the sun 6.5 deg or more below the horizon, pooled with the first run
        extra = 3_000_000
        for key, case in data["cases"].items():
            if "aer" in key:
                continue
            sky = Sky(ozone_du=case["ozone_du"])
            for i, r in enumerate(case["rows"]):
                if r["sun"] > -6.5 or r.get("refined"):
                    continue
                t = time.time()
                ms = sky.multi(Z, r["sun"], extra, seed=50000 + i, max_dh=300)[0]
                n0 = r["paths"]
                r["ms"] = ((np.array(r["ms"]) * n0 + ms * extra) / (n0 + extra)).tolist()
                r["paths"] = n0 + extra
                r["refined"] = True
                print(f"refined {key} sun {r['sun']:+5.1f} ({time.time() - t:.1f}s)", flush=True)
                json.dump(data, open(out_path, "w"))
    elif "--aerosol" in sys.argv:
        # Lange et al. (2023) baseline aerosol (AOD 0.04 troposphere, 1.4e-3 stratosphere),
        # for comparison with their sunset numbers, and a hazy case (AOD 0.25).
        elevs = [round(e, 1) for e in np.arange(6, -12.01, -1.0)]
        for tau, strat, dus in ((0.04, 0.0014, (0, 300, 100, 500)), (0.25, 0.005, (0, 300))):
            for du in dus:
                key = f"o3_{du}_aer_{tau}"
                if key in data["cases"]:
                    continue
                sky = Sky(ozone_du=du, tau_bl=tau, tau_strat=strat)
                data["cases"][key] = {"ozone_du": du, "tau_bl": tau, "tau_strat": strat,
                                      "rows": run_case(sky, elevs, key, 600_000, 200_000)}
                json.dump(data, open(out_path, "w"))
    else:
        for du in (300, 0, 100, 500):
            key = f"o3_{du}"
            sky = Sky(ozone_du=du)
            data["cases"][key] = {"ozone_du": du, "tau_bl": 0.08, "rows": run_case(sky, ELEVS, key)}
            json.dump(data, open(out_path, "w"))
    json.dump(data, open(out_path, "w"))


if __name__ == "__main__":
    main()
