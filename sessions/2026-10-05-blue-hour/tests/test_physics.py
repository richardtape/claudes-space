"""Checks on the sky model. Run from the session folder:

    ~/Developer/claudes-space/.venv/bin/python -m unittest discover -s tests -v
"""
import ctypes
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skymodel import (DOBSON, LAM, LIB, R_EARTH, SIG_O3, SIG_R, Sky, _p,  # noqa: E402
                      aerosol_profile, ozone_profile, spectrum_to_xyz, us1976_number_density,
                      xyz_to_xy)

ZENITH = np.array([[0.0, 0.0, 1.0]])


def dirs(pairs):
    out = []
    for el, az in pairs:
        e, a = math.radians(el), math.radians(az)
        out.append([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    return np.array(out)


class Atmosphere(unittest.TestCase):
    def test_us1976_pressures(self):
        # Textbook US Standard Atmosphere 1976 base pressures (Pa).
        _, (_, _, P) = us1976_number_density([0.0])
        for got, want in zip(P[1:4], (22632.1, 5474.9, 868.02)):
            self.assertAlmostEqual(got / want, 1.0, delta=2e-4)

    def test_air_column_and_rayleigh_depth(self):
        h = np.arange(0, 100e3 + 25, 25.0)
        n, _ = us1976_number_density(h)
        col = np.trapezoid(n, h)
        self.assertAlmostEqual(col / 2.15e29, 1.0, delta=0.01)
        tau550 = np.interp(550, LAM, SIG_R) * col
        self.assertAlmostEqual(tau550, 0.0973, delta=0.002)   # Bodhaine et al. 1999, sea level

    def test_ozone_column_and_peak(self):
        h = np.arange(0, 100e3 + 25, 25.0)
        o3 = ozone_profile(h, 300)
        self.assertAlmostEqual(np.trapezoid(o3, h) / DOBSON, 300, delta=0.01)
        self.assertTrue(20e3 < h[np.argmax(o3)] < 24e3)
        self.assertTrue(4e18 < o3.max() < 5.5e18)

    def test_chappuis_band(self):
        peak = LAM[np.argmax(SIG_O3)]
        self.assertTrue(590 <= peak <= 610)
        self.assertTrue(4.5e-25 < SIG_O3.max() < 5.5e-25)   # ~5e-21 cm^2

    def test_aerosol_depth(self):
        h = np.arange(0, 100e3 + 25, 25.0)
        self.assertAlmostEqual(np.trapezoid(aerosol_profile(h, 0.08, 1200, 0.005), h), 0.085, delta=1e-3)


class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sky = Sky(300)

    def test_lut_matches_direct_integration(self):
        rng = np.random.default_rng(2)
        worst = 0.0
        for _ in range(1500):
            h = rng.uniform(0, 99e3)
            eh = -math.acos(R_EARTH / (R_EARTH + h))
            e = eh + (math.pi / 2 - eh) * rng.uniform(0, 1) ** 4
            lc, ec = np.zeros(3), np.zeros(3)
            LIB.sun_columns_test(h, e, _p(lc), _p(ec))
            for l in (7, 22, 30):
                te = math.exp(-(self.sky.sext[:, l] * ec).sum())
                tl = math.exp(-(self.sky.sext[:, l] * lc).sum())
                if te > 1e-4:
                    worst = max(worst, abs(math.log(tl / te)))
        self.assertLess(worst, 0.02)

    def test_single_scattering_converged(self):
        D = dirs([(90, 0), (30, 90), (5, 90), (0.5, 0)])
        for se in (10, 0, -4):
            a = spectrum_to_xyz(self.sky.single(D, se, max_dh=25))[:, 1]
            b = spectrum_to_xyz(self.sky.single(D, se, max_dh=6))[:, 1]
            np.testing.assert_allclose(a, b, rtol=2e-3)

    def test_two_monte_carlo_estimators_agree(self):
        # Segment estimator (spectral MIS + guide) against plain delta tracking.
        D = dirs([(90, 0), (10, 0)])
        for se in (5, -3):
            a = spectrum_to_xyz(self.sky.multi(D, se, 300000, seed=5, method="delta"))[:, 1]
            b = spectrum_to_xyz(self.sky.multi(D, se, 20000, seed=6, max_dh=300))[:, 1]
            np.testing.assert_allclose(a, b, rtol=0.06)

    def test_monte_carlo_single_scatter_matches_deterministic(self):
        D = dirs([(90, 0), (30, 90)])
        ss = spectrum_to_xyz(self.sky.single(D, 5))[:, 1]
        mc = spectrum_to_xyz(self.sky.multi(D, 5, 200000, min_order=1, max_order=1, seed=3, method="delta"))[:, 1]
        np.testing.assert_allclose(mc, ss, rtol=0.03)


class Findings(unittest.TestCase):
    def test_ozone_keeps_twilight_zenith_blue(self):
        cols = {}
        for du in (300, 0):
            sky = Sky(du)
            L = sky.single(ZENITH, -5) + sky.multi(ZENITH, -5, 60000, seed=9, max_dh=300)
            cols[du] = xyz_to_xy(spectrum_to_xyz(L))[0]
        # D65 is (0.3127, 0.3290). With ozone the zenith is far to the blue side; without, it is not.
        self.assertLess(cols[300][0], 0.26)
        self.assertGreater(cols[0][0], 0.30)


if __name__ == "__main__":
    unittest.main()
