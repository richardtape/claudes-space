"""Mesh convergence of the first few eigenvalues (legs of length 1, area 3.5),
plus which edges of the base triangle the 'triangle modes' treat as Neumann."""
import math, sys, time
import numpy as np
from fano import classes, perm_lines, perm_points
from fem import Drum
from geometry import triangle

cls, _, _ = classes()
t = cls[1][2]
PA = [perm_points(g) for g in t]; PB = [perm_lines(g) for g in t]
tri = triangle(math.radians(45), math.radians(90))
rows = []
for N in (8, 16, 32, 64, 128):
    t0 = time.time()
    A = Drum(PA, tri, N)
    lA, _ = A.eigs(8)
    rows.append((N, lA))
    print(f"N={N:4d} dof={len(A.free):6d} {time.time()-t0:5.1f}s  " + " ".join(f"{x:.6f}" for x in lA))
# Richardson with unknown rate p from the last three
(N1, l1), (N2, l2), (N3, l3) = rows[-3:]
p = np.log2(np.abs(l1 - l2) / np.abs(l2 - l3))
ext = l3 - (l2 - l3) / (2 ** p - 1)
print("observed rates p:", np.round(p, 2))
print("extrapolated   :", " ".join(f"{x:.5f}" for x in ext))
print("extrapolated /4 (legs of length 2, area 14):", " ".join(f"{x:.5f}" for x in ext / 4))
