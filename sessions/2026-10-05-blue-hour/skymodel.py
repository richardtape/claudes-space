"""Python side of the twilight sky model: atmosphere profiles, ctypes wrapper, colour.

    from skymodel import Sky
    sky = Sky(ozone_du=300)
    L = sky.radiance(dirs, sun_elev_deg=-4, ms_paths=2000)   # (n, 41) W m^-2 sr^-1 nm^-1
"""
import ctypes
import json
import math
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = json.load(open(os.path.join(HERE, "data", "spectral.json")))
LAM = np.array(SPEC["lambda_nm"])
NL = len(LAM)
CMF = np.array(SPEC["cmf_xyz"])            # (3, NL)
ESUN = np.array(SPEC["sun_w_m2_nm"])
SIG_O3 = np.array(SPEC["ozone_sigma_m2"])
SIG_R = np.array(SPEC["rayleigh_sigma_m2"])
DLAM = SPEC["bin_width_nm"]

DOBSON = 2.687e20          # molecules m^-2
KB = 1.380649e-23
R_EARTH = 6371e3
TOP = 100e3
DH = 25.0
THREADS = os.cpu_count() or 4

# ---------------------------------------------------------------- profiles

def us1976_number_density(h_m):
    """US Standard Atmosphere 1976 number density (m^-3) for geometric altitude h (m).
    Layer constants cited from memory; tests check the textbook pressures at 11, 20, 32 km.
    Above 84.852 km geopotential the density continues with the scale height there."""
    g0, M, Rs = 9.80665, 0.0289644, 8.3144598
    r0 = 6356766.0
    bases = [0, 11000, 20000, 32000, 47000, 51000, 71000, 84852]
    lapse = [-6.5e-3, 0.0, 1.0e-3, 2.8e-3, 0.0, -2.8e-3, -2.0e-3]
    T_b, P_b = [288.15], [101325.0]
    for i in range(len(lapse)):
        dHb = bases[i + 1] - bases[i]
        T0, P0, Lr = T_b[-1], P_b[-1], lapse[i]
        T1 = T0 + Lr * dHb
        if Lr == 0:
            P1 = P0 * math.exp(-g0 * M * dHb / (Rs * T0))
        else:
            P1 = P0 * (T1 / T0) ** (-g0 * M / (Rs * Lr))
        T_b.append(T1)
        P_b.append(P1)
    h = np.atleast_1d(np.asarray(h_m, dtype=float))
    H = r0 * h / (r0 + h)
    n = np.empty_like(h)
    for k, Hk in enumerate(H):
        if Hk >= bases[-1]:
            T, P = T_b[-1], P_b[-1]
            scale = Rs * T / (M * g0)
            n[k] = P / (KB * T) * math.exp(-(Hk - bases[-1]) / scale)
            continue
        i = max(j for j in range(len(lapse)) if Hk >= bases[j])
        T0, P0, Lr = T_b[i], P_b[i], lapse[i]
        T = T0 + Lr * (Hk - bases[i])
        if Lr == 0:
            P = P0 * math.exp(-g0 * M * (Hk - bases[i]) / (Rs * T0))
        else:
            P = P0 * (T / T0) ** (-g0 * M / (Rs * Lr))
        n[k] = P / (KB * T)
    return n, (bases, T_b, P_b)


def ozone_profile(h_m, du, peak=22e3, width=4.4e3):
    """Green (1964)-style ozone: the column above h is a logistic in h, so the density
    is a sech^2 bump centred at `peak`. Normalised so the total column is `du` Dobson units."""
    x = (h_m - peak) / width
    bump = 1.0 / (4 * width * np.cosh(x / 2) ** 2)          # integrates to 1 over all h
    total = 1.0 / (1 + math.exp(-peak / width))             # integral over h >= 0
    return du * DOBSON * bump / total


def aerosol_profile(h_m, tau_bl, h_bl, tau_strat, strat_peak=20e3, strat_sigma=5e3):
    """Aerosol extinction at 550 nm (m^-1): boundary-layer exponential plus a thin
    stratospheric background layer."""
    bl = tau_bl / h_bl * np.exp(-h_m / h_bl)
    st = tau_strat * np.exp(-0.5 * ((h_m - strat_peak) / strat_sigma) ** 2) / (strat_sigma * math.sqrt(2 * math.pi))
    return bl + st


# ---------------------------------------------------------------- library

def _lib():
    so = os.path.join(HERE, "libsky.dylib")
    src = os.path.join(HERE, "sky.c")
    if not os.path.exists(so) or os.path.getmtime(so) < os.path.getmtime(src):
        subprocess.check_call(["cc", "-O3", "-shared", "-fPIC", "-framework", "Accelerate", "-o", so, src])
    lib = ctypes.CDLL(so)
    D = ctypes.POINTER(ctypes.c_double)
    lib.sky_init.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_double, D,
                             ctypes.c_int, D, D, D, ctypes.c_double, ctypes.c_double]
    lib.lut_alloc.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
    lib.lut_fill_rows.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.sun_columns_test.argtypes = [ctypes.c_double, ctypes.c_double, D, D]
    lib.single_scatter.argtypes = [ctypes.c_int, D, D, ctypes.c_double, D, ctypes.c_int, ctypes.c_double, D, D]
    lib.set_guide.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    lib.multi_scatter_dt.argtypes = [ctypes.c_int, D, D, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint64, D]
    lib.multi_scatter.argtypes = [ctypes.c_int, D, D, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                  ctypes.c_double, D]
    return lib


def _p(a):
    return a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))


LIB = _lib()
_CURRENT = [None]   # the C side holds one atmosphere at a time


class Sky:
    def __init__(self, ozone_du=300.0, tau_bl=0.08, h_bl=1200.0, tau_strat=0.005, angstrom=1.3,
                 ssa=0.95, g=0.7, albedo=0.1, h_obs=0.0, lut_h=401, lut_x=512, o3_gap=None, o3_peak=22e3):
        """o3_gap=(lo_m, hi_m, keep): multiply the ozone profile by `keep` between lo and hi
        (1 km logistic edges), the shape of a polar ozone hole; ozone_du is then the column
        before the gap is cut."""
        self.params = dict(o3_gap=o3_gap, o3_peak=o3_peak, ozone_du=ozone_du, tau_bl=tau_bl, h_bl=h_bl, tau_strat=tau_strat,
                           angstrom=angstrom, ssa=ssa, g=g, albedo=albedo, h_obs=h_obs)
        h = np.arange(0, TOP + DH, DH)
        self.h = h
        n_air, _ = us1976_number_density(h)
        aer = aerosol_profile(h, tau_bl, h_bl, tau_strat)
        o3 = ozone_profile(h, ozone_du, peak=o3_peak) if ozone_du > 0 else np.zeros_like(h)
        if o3_gap:
            lo, hi, keep = o3_gap
            w = 1 / (1 + np.exp(-(h - lo) / 1000.0)) * 1 / (1 + np.exp((h - hi) / 1000.0))
            o3 = o3 * (1 - (1 - keep) * w)
        self.ozone_column_du = float(np.trapezoid(o3, h) / DOBSON)
        self.dens = np.ascontiguousarray(np.stack([n_air, aer, o3]))
        aer_spec = (LAM / 550.0) ** (-angstrom)
        self.sext = np.ascontiguousarray(np.stack([SIG_R, aer_spec, SIG_O3]))
        self.ssca = np.ascontiguousarray(np.stack([SIG_R, ssa * aer_spec, np.zeros(NL)]))
        self.lut_h, self.lut_x = lut_h, lut_x
        self._activate()

    def _activate(self):
        if _CURRENT[0] is self:
            return
        p = self.params
        LIB.sky_init(R_EARTH, R_EARTH + TOP, p["h_obs"], self.dens.shape[1], DH, _p(self.dens),
                     NL, _p(self.sext), _p(self.ssca), _p(np.ascontiguousarray(ESUN)), p["g"], p["albedo"])
        LIB.lut_alloc(self.lut_h, self.lut_x, TOP / (self.lut_h - 1))
        chunks = np.linspace(0, self.lut_h, THREADS * 4 + 1).astype(int)
        with ThreadPoolExecutor(THREADS) as ex:
            list(ex.map(lambda ab: LIB.lut_fill_rows(int(ab[0]), int(ab[1])), zip(chunks[:-1], chunks[1:])))
        _CURRENT[0] = self

    @staticmethod
    def sun_vector(elev_deg, azim_deg=0.0):
        e, a = math.radians(elev_deg), math.radians(azim_deg)
        return np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])

    def single(self, dirs, sun_elev_deg, max_dh=25.0, heights=None):
        """Single-scattering radiance, (n, NL). heights=(nbins, hbin) also returns a
        luminance-weighted histogram of scattering altitude."""
        self._activate()
        dirs = np.ascontiguousarray(dirs, dtype=float).reshape(-1, 3)
        n = len(dirs)
        out = np.zeros((n, NL))
        sun = self.sun_vector(sun_elev_deg)
        nb, hb = heights if heights else (0, 1.0)
        H = np.zeros((n, max(nb, 1)))
        wl = np.ascontiguousarray(CMF[1])
        chunks = np.array_split(np.arange(n), min(n, THREADS * 8))

        def run(idx):
            if len(idx) == 0:
                return
            a, b = idx[0], idx[-1] + 1
            d = np.ascontiguousarray(dirs[a:b])
            o = np.zeros((b - a, NL))
            hh = np.zeros((b - a, max(nb, 1)))
            LIB.single_scatter(b - a, _p(d), _p(sun), max_dh, _p(o), nb, hb, _p(wl), _p(hh) if heights else None)
            out[a:b] = o
            H[a:b] = hh

        with ThreadPoolExecutor(THREADS) as ex:
            list(ex.map(run, chunks))
        return (out, H) if heights else out

    def multi(self, dirs, sun_elev_deg, npath, min_order=2, max_order=1000, seed=1, max_dh=100.0,
              method="segment"):
        """Monte Carlo radiance from scattering orders min_order..max_order, (n, NL).
        method="segment" integrates sunlight along every path segment (low variance);
        method="delta" is the plain delta-tracking estimator, kept as a cross-check."""
        self._activate()
        dirs = np.ascontiguousarray(dirs, dtype=float).reshape(-1, 3)
        n = len(dirs)
        sun = self.sun_vector(sun_elev_deg)
        out = np.zeros((n, NL))
        # split paths as well as directions so a single direction still uses every core
        reps = max(1, THREADS // n) if n < THREADS else 1
        per = max(1, npath // reps)
        jobs = []
        for r in range(reps):
            for idx in np.array_split(np.arange(n), max(1, min(n, THREADS * 4 // reps))):
                if len(idx):
                    jobs.append((r, idx[0], idx[-1] + 1))
        acc = np.zeros((reps, n, NL))

        def run(job):
            r, a, b = job
            d = np.ascontiguousarray(dirs[a:b])
            o = np.zeros((b - a, NL))
            sd = int(seed) * 1000003 + r * 7919 + a
            if method == "delta":
                LIB.multi_scatter_dt(b - a, _p(d), _p(sun), per, min_order, max_order, sd, _p(o))
            else:
                LIB.multi_scatter(b - a, _p(d), _p(sun), per, min_order, max_order, sd, max_dh, _p(o))
            acc[r, a:b] = o

        with ThreadPoolExecutor(THREADS) as ex:
            list(ex.map(run, jobs))
        return acc.mean(axis=0)


# ---------------------------------------------------------------- colour

M_XYZ_TO_SRGB = np.array([[3.2404542, -1.5371385, -0.4985314],
                          [-0.9692660, 1.8760108, 0.0415560],
                          [0.0556434, -0.2040259, 1.0572252]])


def spectrum_to_xyz(L):
    """Spectral radiance (..., NL) in W m^-2 sr^-1 nm^-1 -> CIE XYZ with Y in cd m^-2."""
    return 683.0 * DLAM * np.tensordot(L, CMF.T, axes=([-1], [0]))


def xyz_to_xy(XYZ):
    s = XYZ.sum(axis=-1, keepdims=True)
    return XYZ[..., :2] / np.where(s > 0, s, 1)


def xyz_to_linear_srgb(XYZ):
    return np.tensordot(XYZ, M_XYZ_TO_SRGB.T, axes=([-1], [0]))


def srgb_encode(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def cct_mccamy(xy):
    """Correlated colour temperature by McCamy's cubic (valid roughly 2000-12500 K)."""
    n = (xy[..., 0] - 0.3320) / (0.1858 - xy[..., 1])
    return 449 * n**3 + 3525 * n**2 + 6823.3 * n + 5520.33


def dominant_wavelength(xy, white=(0.3127, 0.3290)):
    """Dominant (or complementary, negative) wavelength of chromaticity xy relative to D65,
    found by intersecting the ray white->xy with the 1 nm spectral locus."""
    d = np.loadtxt(os.path.join(HERE, "raw", "ciexyz31_1.csv"), delimiter=",")
    d = d[(d[:, 0] >= 380) & (d[:, 0] <= 700)]
    loc = d[:, 1:3] / d[:, 1:4].sum(axis=1, keepdims=True)
    w = np.array(white)
    v = np.asarray(xy) - w
    ang = math.atan2(v[1], v[0])
    angs = np.arctan2(loc[:, 1] - w[1], loc[:, 0] - w[0])
    i = np.argmin(np.abs(np.angle(np.exp(1j * (angs - ang)))))
    j = np.argmin(np.abs(np.angle(np.exp(1j * (angs - ang - math.pi)))))
    # if the forward ray points at the purple line, report the complementary wavelength
    if abs(np.angle(np.exp(1j * (angs[i] - ang)))) < 0.05:
        return float(d[i, 0])
    return -float(d[j, 0])
