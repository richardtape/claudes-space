"""Derived numbers from data/zenith.json: colours, ozone's share of the blue, multiple
scattering fraction, the spectral 'bite'. Prints a summary and writes data/derived.json,
which build_page.py inlines into the page.

Ozone's share uses the metric of Lange, Rozanov & von Savigny (2023, ACP 23, 14829):
d1, d2 = distance of the with-ozone and without-ozone zenith chromaticities from the
equal-energy white point (1/3, 1/3); share r = (d1 - d2) / d1. Past sunset the
no-ozone point can swing round to the yellow side of white, where an unsigned distance
misleads, so a signed variant (d2 projected onto the direction of the with-ozone
point) is reported alongside.
"""
import json
import math
import os

import numpy as np

from skymodel import CMF, M_XYZ_TO_SRGB, srgb_encode, spectrum_to_xyz, xyz_to_xy, cct_mccamy

HERE = os.path.dirname(os.path.abspath(__file__))
E_WHITE = np.array([1 / 3, 1 / 3])


def swatch(xyz, level=0.82):
    """sRGB hex of a colour shown at fixed brightness (max channel = level), gamut-clipped
    by desaturating towards its own grey."""
    rgb = M_XYZ_TO_SRGB @ xyz
    Y = xyz[1]
    mn = rgb.min()
    if mn < 0:
        rgb = Y + (rgb - Y) * (Y / (Y - mn))
    rgb = rgb / max(rgb.max(), 1e-30) * level
    s = srgb_encode(rgb)
    return "#" + "".join(f"{int(round(v * 255)):02x}" for v in s)


def share(xy_with, xy_without, white=E_WHITE):
    v1 = xy_with - white
    v2 = xy_without - white
    d1 = float(np.hypot(*v1))
    d2 = float(np.hypot(*v2))
    d2s = float(v2 @ v1 / d1)
    return (d1 - d2) / d1, (d1 - d2s) / d1


def main():
    Z = json.load(open(os.path.join(HERE, "data", "zenith.json")))
    lam = np.array(Z["lambda_nm"])
    out = {"lambda_nm": lam.tolist(), "cases": {}}
    for key, case in Z["cases"].items():
        rows = []
        for r in case["rows"]:
            ss, ms = np.array(r["ss"]), np.array(r["ms"])
            tot = ss + ms
            X = spectrum_to_xyz(tot)
            xy = xyz_to_xy(X)
            H = np.array(r["ss_heights"])
            rows.append({
                "sun": r["sun"],
                "Y": float(X[1]),
                "xy": [round(float(xy[0]), 5), round(float(xy[1]), 5)],
                "cct": round(float(cct_mccamy(xy)), 0),
                "ms_frac": round(float(spectrum_to_xyz(ms)[1] / X[1]), 4),
                "swatch": swatch(X),
                "spec": [float(v) for v in tot],
                "heights": (H / H.sum()).round(5).tolist() if H.sum() > 0 else None,
            })
        out["cases"][key] = {"ozone_du": case["ozone_du"], "tau_bl": case["tau_bl"], "rows": rows}

    # ozone's share of the blue, per sun elevation, for each ozone case against 0 DU
    shares = {}
    base = {r["sun"]: r for r in out["cases"].get("o3_0", {}).get("rows", [])}
    for key, case in out["cases"].items():
        if case["ozone_du"] == 0 or not key.startswith("o3_") or "aer" in key:
            continue
        s = []
        for r in case["rows"]:
            b = base.get(r["sun"])
            if b is None:
                continue
            u, sg = share(np.array(r["xy"]), np.array(b["xy"]))
            s.append({"sun": r["sun"], "r": round(u, 4), "r_signed": round(sg, 4),
                      "ratio": [round(a / c, 5) if c > 0 else None for a, c in zip(r["spec"], b["spec"])]})
        shares[str(case["ozone_du"])] = s
    out["shares"] = shares
    # aerosol-sensitivity cases, if present
    aer = {}
    for key, case in out["cases"].items():
        if "aer" not in key or case["ozone_du"] == 0:
            continue
        zero = {r["sun"]: r for r in out["cases"].get(key.replace(f"o3_{case['ozone_du']}", "o3_0"), {}).get("rows", [])}
        aer[key] = [{"sun": r["sun"], "r": round(share(np.array(r["xy"]), np.array(zero[r["sun"]]["xy"]))[0], 4),
                     "r_signed": round(share(np.array(r["xy"]), np.array(zero[r["sun"]]["xy"]))[1], 4),
                     "xy": r["xy"], "xy0": zero[r["sun"]]["xy"]}
                    for r in case["rows"] if r["sun"] in zero]
    out["aerosol_shares"] = aer
    # the shape-of-the-hole experiment (hole_experiment.py), if it has been run
    hp = os.path.join(HERE, "data", "hole.json")
    if os.path.exists(hp):
        H = json.load(open(hp))
        out["hole"] = {"gap": H["gap"], "peak": H["peak"], "cases": {}}
        for name, case in H["cases"].items():
            out["hole"]["cases"][name] = {
                "ozone_du": round(case["ozone_du"], 1),
                "rows": [{"sun": r["sun"], "xy": [round(v, 4) for v in r["xy"]],
                          "swatch": swatch(spectrum_to_xyz(np.array(r["spec"])))} for r in case["rows"]],
            }
    # tangent height of the sunbeam that reaches the median once-scattering height
    tang = {}
    for r in out["cases"]["o3_300"]["rows"]:
        if r["sun"] < 0 and r["heights"]:
            c = np.cumsum(r["heights"])
            hmed = float(np.searchsorted(c, 0.5)) + 0.5
            tang[r["sun"]] = round((6371 + hmed) * math.cos(math.radians(-r["sun"])) - 6371, 1)
    out["median_tangent_km"] = tang
    json.dump(out, open(os.path.join(HERE, "data", "derived.json"), "w"))

    # summary
    for du, s in shares.items():
        print(f"ozone {du} DU vs none: share of blueness (Lange metric / signed)")
        for row in s:
            if row["sun"] in (10, 5, 0, -1, -2, -3, -4, -6, -8, -10, -12, -14):
                print(f"   sun {row['sun']:+5.1f}  r {row['r']:6.3f}  signed {row['r_signed']:6.3f}")
    for key, case in out["cases"].items():
        print(key)
        for r in case["rows"]:
            if r["sun"] in (10, 0, -3, -6, -9, -12):
                print(f"   sun {r['sun']:+5.1f}  Y {r['Y']:9.3g}  xy {r['xy']}  CCT {r['cct']:7.0f}  MS {r['ms_frac']:.2f}  {r['swatch']}")


if __name__ == "__main__":
    main()
