"""Are the two discretised drums isospectral?  And what is the transplantation?"""
import math, sys, time
import numpy as np
from fano import classes, perm_lines, perm_points, incidence
from fem import Drum
from geometry import triangle

cls, _, _ = classes()
t = cls[1][2]                         # class 1 = Gordon-Webb-Wolpert with a 45-90-45 triangle
PA = [perm_points(g) for g in t]
PB = [perm_lines(g) for g in t]
tri = triangle(math.radians(45), math.radians(90))      # legs of length 1

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
m = int(sys.argv[2]) if len(sys.argv) > 2 else 60
t0 = time.time()
A, B = Drum(PA, tri, N), Drum(PB, tri, N)
print(f"N={N}: nodes A {len(A.xy)} (free {len(A.free)}), B {len(B.xy)} (free {len(B.free)}); area A {A.area():.6f} B {B.area():.6f}")
lA, UA = A.eigs(m)
lB, UB = B.eigs(m)
print(f"solved in {time.time()-t0:.1f}s")
rel = np.abs(lA - lB) / lA
print("first eigenvalues A:", np.round(lA[:6], 6))
print("first eigenvalues B:", np.round(lB[:6], 6))
print(f"max relative difference over {m} modes: {rel.max():.2e}")
gaps = np.diff(lA) / lA[1:]
print(f"smallest relative gap between consecutive eigenvalues of A: {gaps.min():.2e}")

# Transplantation: express B's mode on tile j as a combination of A's mode on tiles i.
a = A.per_tile(UA); b = B.per_tile(UB)          # (m, 7, nl)
k = 0
X = np.linalg.lstsq(a[k].T, b[k].T, rcond=None)[0].T     # b[k][j] = sum_i X[j,i] a[k][i]
s = np.abs(X).max()
print("T (scaled so the largest entry is 1), from mode 1:\n", np.round(X / s, 6))
T = np.round(X / s)
# Check T on all modes: b_k = c_k T a_k
worst, cs = 0, []
for k in range(m):
    Ta = np.einsum('ji,in->jn', T, a[k])
    c = (Ta * b[k]).sum() / (Ta * Ta).sum()
    cs.append(c)
    worst = max(worst, np.abs(b[k] - c * Ta).max() / np.abs(b[k]).max())
print(f"T reproduces every B mode from the A mode, worst relative residual {worst:.2e}")
print("scale factors |c_k|: min %.6f max %.6f" % (np.min(np.abs(cs)), np.max(np.abs(cs))))
N_inc = incidence()
print("|T| pattern equals incidence matrix?", np.array_equal(np.abs(T), N_inc),
      " equals complement?", np.array_equal(np.abs(T), 1 - N_inc))
print("T^T T =\n", (T.T @ T).astype(int))
