"""Assemble index.html from page.src.html, copy.html and the computed data.

    .venv/bin/python build_page.py

Needs data/derived.json (analysis.py), data/frames.json (make_images.py) and the
spectral tables. Copy lives in copy.html as <!-- KEY --> ... blocks so the prose
is easy to edit apart from the code.
"""
import json
import math
import os
import re

import numpy as np

from skymodel import (CMF, DOBSON, ESUN, LAM, M_XYZ_TO_SRGB, SIG_O3, SIG_R, aerosol_profile,
                      ozone_profile, srgb_encode, us1976_number_density)

HERE = os.path.dirname(os.path.abspath(__file__))
LANGE_2023 = {"100": 39, "300": 66, "500": 76}   # % at SZA 90, VZA 0 (Lange et al. 2023, sect. 3)


def spectrum_colours():
    out = []
    for k in range(len(LAM)):
        X, Y, Z = CMF[:, k]
        rgb = M_XYZ_TO_SRGB @ np.array([X, Y, Z])
        mn = rgb.min()
        if mn < 0:
            rgb = rgb - mn          # desaturate into gamut (monochromatic light is outside sRGB)
        rgb = rgb / max(rgb.max(), 1e-30)
        b = min(1.0, (X + Y + Z) / CMF.sum(axis=0).max() * 2.2) ** 0.6
        s = srgb_encode(rgb * b)
        out.append("#" + "".join(f"{int(round(v * 255)):02x}" for v in s))
    return out


def ray_tables():
    h = np.arange(0, 100.5, 0.5) * 1000
    n_air, _ = us1976_number_density(h)
    return {
        "dh": 0.5,
        "lam": LAM.tolist(),
        "sigR": SIG_R.tolist(),
        "sigO3": (SIG_O3 * 1.0).tolist(),
        "aer": ((LAM / 550.0) ** -1.3).tolist(),
        "esun": ESUN.tolist(),
        "cmf": CMF.tolist(),
        "air": n_air.tolist(),
        "aerP": aerosol_profile(h, 0.08, 1200, 0.005).tolist(),
        "o3": (ozone_profile(h, 1.0)).tolist(),       # per Dobson unit
    }


def numbers(der, frames, elevs):
    """Values quoted in the prose, computed here so the text and the charts agree."""
    sh = {du: {r["sun"]: r for r in der["shares"][du]} for du in der["shares"]}
    aer = der["aerosol_shares"]
    zen = {k: {r["sun"]: r for r in v["rows"]} for k, v in der["cases"].items()}
    pc = lambda v: str(int(round(100 * v)))
    n = {
        "R300_0": pc(sh["300"][0.0]["r"]),
        "R300_M3": pc(sh["300"][-3.0]["r"]),
        "R100_0": pc(sh["100"][0.0]["r"]),
        "DIM_0": pc(1 - zen["o3_300"][0.0]["Y"] / zen["o3_0"][0.0]["Y"]),
        "DIM_6": pc(1 - zen["o3_300"][-6.0]["Y"] / zen["o3_0"][-6.0]["Y"]),
        "BITE_0": pc(1 - sh["300"][0.0]["ratio"][list(LAM).index(600.0)]),
    }
    for du in ("100", "300", "500"):
        rows = aer.get(f"o3_{du}_aer_0.04")
        n[f"RL{du}_0"] = pc([r["r"] for r in rows if r["sun"] == 0][0]) if rows else "?"
    cl = {r["sun"]: r for r in aer.get("o3_300_aer_0.04", [])}
    n["RC300_M6"] = pc(cl[-6.0]["r"]) if cl else "?"
    n["RC300_DEEP"] = (f"{pc(min(cl[e]['r'] for e in (-8.0, -9.0, -10.0, -11.0, -12.0)))}&ndash;"
                       f"{pc(max(cl[e]['r'] for e in (-8.0, -9.0, -10.0, -11.0, -12.0)))}") if cl else "?"
    n["RS300_PEAK"] = pc(np.mean([sh["300"][e]["r_signed"] for e in (-8.0, -8.5, -9.0, -9.5, -10.0)]))
    tg = der["median_tangent_km"]
    n["TANG_RANGE"] = f"{min(tg[str(e)] for e in (-1.0, -2.0, -4.0, -6.0, -8.0)):.0f} to {max(tg[str(e)] for e in (-1.0, -2.0, -4.0, -6.0, -8.0)):.0f}"
    hz = aer.get("o3_300_aer_0.25")
    n["HAZE_0"] = pc([r["r"] for r in hz if r["sun"] == 0][0]) if hz else "?"
    ill = {e: frames["frames"][f"300/{e}"].get("illuminance", float("nan")) for e in elevs}
    n["ILL"] = ill
    return n


def check_rows(n):
    from skymodel import us1976_number_density
    _, (_, _, P) = us1976_number_density([0.0])
    h = np.arange(0, 100e3 + 25, 25.0)
    na, _ = us1976_number_density(h)
    col = np.trapezoid(na, h)
    tau = float(np.interp(550, LAM, SIG_R) * col)
    ill = n["ILL"]
    # the almanac's sunset: interpolate log-illuminance between -0.5 and -1.0 deg
    f = (0.83 - 0.5) / 0.5
    sunset_almanac = math.exp((1 - f) * math.log(ill[-0.5]) + f * math.log(ill[-1.0]))
    rows = [
        ("Air pressure at 11, 20 and 32 km (US Standard Atmosphere 1976)",
         f"{P[1]:,.0f}, {P[2]:,.0f}, {P[3]:.0f} Pa", "22,632, 5,475, 868 Pa (standard tables)"),
        ("Rayleigh optical depth of the whole atmosphere at 550 nm", f"{tau:.4f}", "0.0973 (Bodhaine et al. 1999)"),
        ("Sun-column look-up table against direct integration, worst case where transmittance &gt; 10<sup>&minus;4</sup>",
         "0.7% error", "&mdash;"),
        ("Once-scattered light with the integration step cut fourfold", "changes &lt; 0.1%", "&mdash;"),
        ("Multiple scattering from two independent Monte Carlo estimators, sun +5&deg; to &minus;4&deg;",
         "agree within 2&ndash;5%", "&mdash;"),
        ("Ozone's share of the zenith's blueness at sunset, with Lange et al.'s aerosol: 100, 300, 500 DU",
         f"{n['RL100_0']}%, {n['RL300_0']}%, {n['RL500_0']}%", "39%, 66%, 76% (Lange et al. 2023)"),
        ("Light on level ground from the whole sky at sunset: sun's centre on the horizon, and at &minus;0.83&deg; (the almanac's sunset, upper limb on a refracted horizon)",
         f"{ill[0.0]:,.0f} and {sunset_almanac:,.0f} lux", "about 330&ndash;585 lux (see notes)"),
        ("Light on level ground when civil twilight ends (sun 6&deg; down)", f"{ill[-6.0]:.1f} lux",
         "about 2&ndash;3.5 lux, often quoted as 3.2&ndash;3.4 (see notes)"),
        ("Light on level ground when nautical twilight ends (sun 12&deg; down)", f"{ill[-12.0]:.3f} lux",
         "about 0.008 lux (widely quoted; from memory)"),
    ]
    return "\n".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows)


def read_copy():
    txt = open(os.path.join(HERE, "copy.html"), encoding="utf-8").read()
    parts = re.split(r"<!--\s*([A-Z_]+)\s*-->", txt)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def main():
    der = json.load(open(os.path.join(HERE, "data", "derived.json")))
    frames = json.load(open(os.path.join(HERE, "data", "frames.json")))
    elevs = [r["sun"] for r in der["cases"]["o3_300"]["rows"]]
    have = frames["elevations"]
    preview = sorted(have) != sorted(elevs) or len(frames["cases"]) < 3
    if preview:   # frames still rendering: borrow the nearest frame so the page can be laid out
        print("PREVIEW: frames incomplete")
        for du in (300, 0, 100):
            src = du if du in frames["cases"] else frames["cases"][0]
            for e in elevs:
                near = min(have, key=lambda h: abs(h - e))
                frames["frames"].setdefault(f"{du}/{e}", frames["frames"][f"{src}/{near}"])
        frames["cases"] = [300, 0, 100]
    zen = {}
    for du in (0, 100, 300, 500):
        rows = {r["sun"]: r for r in der["cases"][f"o3_{du}"]["rows"]}
        zen[du] = [{k: rows[e][k] for k in ("sun", "Y", "xy", "swatch", "ms_frac", "cct")} for e in elevs]
    heights = [{r["sun"]: r for r in der["cases"]["o3_300"]["rows"]}[e]["heights"] for e in elevs]
    share = {}
    for du in ("100", "300", "500"):
        rows = {r["sun"]: r for r in der["shares"][du]}
        share[du] = [rows[e] for e in elevs]
    lange_mine = {}
    for du in ("100", "300", "500"):
        rows = der["aerosol_shares"].get(f"o3_{du}_aer_0.04")
        if rows:
            lange_mine[du] = [r["r"] for r in rows if r["sun"] == 0][0]
    top = max(100 * r["r"] for du in share for r in share[du])
    share_max = min(175, int(math.ceil(top / 25.0) * 25))
    fr = {}
    for du in frames["cases"]:
        fr[du] = [frames["frames"][f"{du}/{e}"] for e in elevs]
    data = {
        "elevs": elevs,
        "start": -4.0,
        "pano": frames["pano"],
        "frames": fr,
        "zenith": zen,
        "heights": heights,
        "share": share,
        "shareMax": share_max,
        "lange": LANGE_2023,
        "langeMine": lange_mine,
        "lambda": LAM.tolist(),
        "specColors": spectrum_colours(),
        "rays": ray_tables(),
        "shareClean": [{"sun": r["sun"], "r": r["r"]} for r in der["aerosol_shares"].get("o3_300_aer_0.04", [])],
        "hole": der.get("hole"),
    }
    page = open(os.path.join(HERE, "page.src.html"), encoding="utf-8").read()
    copy = read_copy()
    for key, val in copy.items():
        page = page.replace("{{" + key + "}}", val)
    n = numbers(der, frames, elevs)
    page = page.replace("{{CHECK_ROWS}}", check_rows(n))
    for key, val in n.items():
        if isinstance(val, str):
            page = page.replace("{{" + key + "}}", val)
    print({k: v for k, v in n.items() if isinstance(v, str)})
    left = re.findall(r"\{\{[A-Z_]+\}\}", page)
    if left:
        raise SystemExit(f"copy missing for {left}")
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = page.replace("/*__DATA__*/", blob)
    open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(page)
    print(f"index.html: {len(page) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
