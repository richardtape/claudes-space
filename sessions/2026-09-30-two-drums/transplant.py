"""Split the transplantation into its incidence part and its non-incidence part."""
import math, sys
import numpy as np
from fano import classes, perm_lines, perm_points, incidence
from fem import Drum
from geometry import triangle

cls, _, _ = classes()
t = cls[1][2]
PA = [perm_points(g) for g in t]; PB = [perm_lines(g) for g in t]
tri = triangle(math.radians(45), math.radians(90))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
m = int(sys.argv[2]) if len(sys.argv) > 2 else 60
A, B = Drum(PA, tri, N), Drum(PB, tri, N)
lA, UA = A.eigs(m); lB, UB = B.eigs(m)
a = A.per_tile(UA); b = B.per_tile(UB)
Inc = incidence()                        # Inc[line, point]

def fit(k, mask):
    """Least-squares X with support mask such that X a_k = b_k tile-wise."""
    X = np.zeros((7, 7))
    for j in range(7):
        cols = np.flatnonzero(mask[j])
        X[j, cols] = np.linalg.lstsq(a[k][cols].T, b[k][j], rcond=None)[0]
    return X

for name, mask in (("incidence", Inc == 1), ("non-incidence", Inc == 0)):
    X = fit(0, mask)
    T = np.sign(np.round(X / np.abs(X).max(), 6))
    res, cs = [], []
    for k in range(m):
        Ta = np.einsum('ji,in->jn', T, a[k])
        nrm = (Ta * Ta).sum()
        c = (Ta * b[k]).sum() / nrm if nrm > 1e-20 else 0.0
        cs.append(c)
        res.append(np.abs(b[k] - c * Ta).max() / np.abs(b[k]).max() if nrm > 1e-20 else np.nan)
    print(f"--- {name}: sign matrix from mode 1\n{T.astype(int)}")
    print(f"  T^T T =\n{(T.T @ T).astype(int)}")
    print(f"  worst residual over modes: {np.nanmax(res):.2e}")
    print(f"  scale factors c_k: {sorted(set(np.round(np.abs(cs), 6)))}")
    np.save(f"T_{name}.npy", T)

# Are some modes copies of one triangle pattern on every tile?
print("\nmode  lambda      max_i,j |  |a_i| - |a_j|  | / max|a|   (0 => same pattern on every tile up to sign)")
for k in range(m):
    ak = a[k]
    dev = max(np.abs(np.abs(ak[i]) - np.abs(ak[0])).max() for i in range(7)) / np.abs(ak).max()
    if dev < 1e-8:
        print(f"{k+1:4d}  {lA[k]:10.4f}  {dev:.1e}")
