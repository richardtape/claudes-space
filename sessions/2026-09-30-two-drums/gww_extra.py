"""(1) Is the GWW pair homophonic at any pair of mesh nodes?
(2) Compare with 7_2 built from the same seven half-squares: area, perimeter, corners, spectrum."""
import math
import numpy as np
from fano import classes, perm_lines, perm_points
from fem import Drum
from geometry import boundary_polygon, check, triangle, _signature

cls, _, _ = classes()
tri = triangle(math.radians(45), math.radians(90))
def drums(ci, tri):
    t = cls[ci][2]
    return [perm_points(g) for g in t], [perm_lines(g) for g in t]

PA, PB = drums(1, tri)
N, m = 16, 60
A, B = Drum(PA, tri, N), Drum(PB, tri, N)
lA, UA = A.eigs(m); lB, UB = B.eigs(m)
# (1) normalised squared mode values at every free node
fa = UA[A.free] ** 2; fb = UB[B.free] ** 2           # (nodes, m)
w = 1 / np.maximum(fa.mean(0), 1e-30)                # weight modes equally
best = (np.inf, None, None)
ea, eb = (fa * w).sum(1), (fb * w).sum(1)              # "loudness" of each node
keep_a, keep_b = ea > 0.25 * np.median(ea), eb > 0.25 * np.median(eb)
fa, fb = fa[keep_a], fb[keep_b]
xa, xb = A.xy[A.free][keep_a], B.xy[B.free][keep_b]
ea, eb = ea[keep_a], eb[keep_b]
for s in range(0, len(fa), 200):
    d = (((fa[s:s+200, None, :] - fb[None, :, :]) ** 2) * w).sum(-1) / (ea[s:s+200, None] + eb[None, :])
    i, j = np.unravel_index(np.argmin(d), d.shape)
    if d[i, j] < best[0]:
        best = (d[i, j], s + i, j)
# scale: typical distance between random pairs
rng = np.random.default_rng(0)
ri, rj = rng.integers(0, len(fa), 4000), rng.integers(0, len(fb), 4000)
typ = np.median((((fa[ri] - fb[rj]) ** 2) * w).sum(-1) / (ea[ri] + eb[rj]))
print(f"(1) best-matching node pair: distance {best[0]:.3g} vs median random pair {typ:.3g}  (ratio {best[0]/typ:.3g})")
pa_xy, pb_xy = xa[best[1]], xb[best[2]]
print("    at A", np.round(pa_xy, 3), " B", np.round(pb_xy, 3))
# same test on 21_1 for calibration is in homophonic.py: there it is ~1e-14.

# (2) The pretender: 7_2 with the same triangle
tri72 = triangle(math.radians(45), math.radians(45)) * math.sqrt(2)   # right angle at V2, legs 1
QA, QB = drums(0, tri72)
assert check(QA, tri72)[0] == "ok"
C = Drum(QA, tri72, N)
print(f"    7_2 drum area {C.area():.4f} vs GWW {A.area():.4f}")
lC, _ = C.eigs(m)
def invariants(P, tri):
    _, V = check(P, tri)
    poly = boundary_polygon(P, V)
    sig = _signature(poly)
    per = sum(L for _, L in sig)
    corner = sum((math.pi**2 - th**2) / (24 * math.pi * th) for th, _ in sig)
    return per, corner, sorted(round(math.degrees(th)) for th, _ in sig)
for name, P, T in (("GWW A", PA, tri), ("GWW B", PB, tri), ("7_2 A", QA, tri72), ("7_2 B", QB, tri72)):
    per, cor, angs = invariants(P, T)
    print(f"(2) {name}: perimeter {per:.6f}  corner term {cor:.6f}  angles {angs}")
print("    first eigenvalues GWW :", np.round(lA[:8], 3))
print("    first eigenvalues 7_2 :", np.round(lC[:8], 3))
print(f"    max rel. difference GWW A vs 7_2 over {m}: {np.max(np.abs(lA-lC)/lA):.3f}, mean {np.mean(np.abs(lA-lC)/lA):.4f}")
