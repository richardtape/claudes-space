"""Bin the spectral inputs onto the model's wavelength grid (380-780 nm, 10 nm bins).

Inputs (in raw/, downloaded 2026-10-05):
  ciexyz31_1.csv  CIE 1931 2-degree colour matching functions, 1 nm (CVRL, cvrl.ucl.ac.uk)
  ASTMG173.csv    ASTM G-173-03 reference spectra; the 'extraterrestrial' column is the
                  top-of-atmosphere solar irradiance, W m^-2 nm^-1 (copy bundled with pvlib 0.16.1)
  sg5.dat         Serdyuchenko & Gorshelev ozone absorption cross sections, 0.01 nm,
                  193-293 K (IUP Bremen; Serdyuchenko et al. 2014, AMT 7, 625)

Rayleigh scattering by air is computed, not tabulated: Bodhaine et al. (1999) recipe
(Peck & Reeder refractive index, Bates King factors), cited from memory and checked
against the textbook optical depth at 550 nm in tests.

Output: data/spectral.json
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

L0, L1, DL = 380, 780, 10
CENTRES = np.arange(L0, L1 + 1, DL, dtype=float)


def bin_average(x, y, centre, half=DL / 2):
    """Mean of y over [centre-half, centre+half), trapezoid-weighted on the source grid."""
    lo, hi = centre - half, centre + half
    grid = np.linspace(lo, hi, 201)
    return float(np.trapezoid(np.interp(grid, x, y), grid) / (hi - lo))


def load_cmf():
    d = np.loadtxt(os.path.join(RAW, "ciexyz31_1.csv"), delimiter=",")
    lam = d[:, 0]
    return [[bin_average(lam, d[:, k], c) for c in CENTRES] for k in (1, 2, 3)]


def load_sun():
    rows = []
    with open(os.path.join(RAW, "ASTMG173.csv")) as f:
        next(f), next(f)
        for line in f:
            p = line.strip().split(",")
            rows.append((float(p[0]), float(p[1])))
    a = np.array(rows)
    return [bin_average(a[:, 0], a[:, 1], c) for c in CENTRES]


def load_ozone(column=9):
    """Cross section in m^2 per molecule. Column 9 is 223 K (stratospheric)."""
    lam, sig = [], []
    with open(os.path.join(RAW, "sg5.dat"), encoding="latin-1") as f:
        for i, line in enumerate(f):
            if i < 45:
                continue
            p = line.split()
            w = float(p[0])
            if w < L0 - 10:
                continue
            if w > L1 + 10:
                break
            lam.append(w)
            sig.append(float(p[column - 1]) * 1e-4)  # cm^2 -> m^2
    lam, sig = np.array(lam), np.array(sig)
    return [bin_average(lam, sig, c) for c in CENTRES]


def rayleigh_cross_section(lam_nm, co2=0.00036):
    """Rayleigh scattering cross section of dry air, m^2 per molecule (Bodhaine et al. 1999)."""
    l = lam_nm / 1000.0  # micrometres
    s2 = 1.0 / l**2
    n300 = 1 + 1e-8 * (8060.51 + 2480990 / (132.274 - s2) + 17455.7 / (39.32957 - s2))
    n = 1 + (n300 - 1) * (1 + 0.54 * (co2 - 0.0003))
    Ns = 2.546899e19 * 1e6  # molecules per m^3 at 288.15 K, 1013.25 hPa
    F_N2 = 1.034 + 3.17e-4 * s2
    F_O2 = 1.096 + 1.385e-3 * s2 + 1.448e-4 * s2**2
    c = co2 * 100
    F = (78.084 * F_N2 + 20.946 * F_O2 + 0.934 * 1.0 + c * 1.15) / (78.084 + 20.946 + 0.934 + c)
    lam_m = lam_nm * 1e-9
    return 24 * math.pi**3 * (n**2 - 1) ** 2 / (lam_m**4 * Ns**2 * (n**2 + 2) ** 2) * F


def main():
    cmf = load_cmf()
    out = {
        "lambda_nm": CENTRES.tolist(),
        "bin_width_nm": DL,
        "cmf_xyz": cmf,
        "sun_w_m2_nm": load_sun(),
        "ozone_sigma_m2": load_ozone(),
        "rayleigh_sigma_m2": [rayleigh_cross_section(c) for c in CENTRES],
        "sources": {
            "cmf": "CIE 1931 2-degree CMFs, CVRL ciexyz31_1.csv, bin-averaged",
            "sun": "ASTM G-173-03 extraterrestrial column (via pvlib 0.16.1 data), bin-averaged",
            "ozone": "Serdyuchenko & Gorshelev 2014, 223 K column, bin-averaged",
            "rayleigh": "Bodhaine et al. 1999 formula, at bin centre",
        },
    }
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    with open(os.path.join(HERE, "data", "spectral.json"), "w") as f:
        json.dump(out, f, indent=1)
    for i in range(0, len(CENTRES), 5):
        print(f"{CENTRES[i]:5.0f} nm  sun {out['sun_w_m2_nm'][i]:.3f}  "
              f"O3 {out['ozone_sigma_m2'][i]:.3e}  Ray {out['rayleigh_sigma_m2'][i]:.3e}  "
              f"ybar {cmf[1][i]:.4f}")


if __name__ == "__main__":
    main()
