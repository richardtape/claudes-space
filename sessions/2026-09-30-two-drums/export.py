"""Compute everything the page needs and write page_data.json (+ verify_data.json for tests).

GWW pair (BCDS 7_3, right isosceles triangle, legs 1):
  modes of drum A solved on a fine mesh (N_FINE per tile), sampled on the page mesh
  (N_PAGE per tile).  Drum B is NOT stored: the page builds it from A with the
  transplantation T3.  verify_data.json holds B solved directly, for the node test.
Homophonic pair (BCDS 21_1, 30-60-90 triangle): both drums stored.
Shape map: status grid for the three 7-tile families from shapes.json.
"""
import base64
import json
import math
import time

import numpy as np

from fano import classes, perm_lines, perm_points
from fem import Drum, base_mesh
from geometry import boundary_loop, check, triangle, unfold
from pair21 import PA as PA21, PB as PB21

t_start = time.time()


def q16(arr):
    """Per-mode int16 quantisation.  arr: (m, ...) -> (base64 string, scales list)."""
    m = arr.shape[0]
    flat = arr.reshape(m, -1)
    scale = np.abs(flat).max(1)
    qv = np.round(flat / scale[:, None] * 32767).astype("<i2")
    return base64.b64encode(qv.tobytes()).decode(), [float(s) for s in scale]


def sample(D_fine, U_fine, n_fine, n_page):
    """Per-tile local arrays on the page mesh, from fine-mesh global vectors."""
    step = n_fine // n_page
    bary_f, _ = base_mesh(n_fine)
    idx_f = {(round(b[0] * n_fine), round(b[1] * n_fine)): i for i, b in enumerate(bary_f)}
    bary_p, _ = base_mesh(n_page)
    pick = [idx_f[(round(b[0] * n_page) * step, round(b[1] * n_page) * step)] for b in bary_p]
    a = D_fine.per_tile(U_fine)                 # (m, tiles, nl_fine)
    return a[:, :, pick]


def fix_sign(a):
    """Make the largest-magnitude value of every mode positive."""
    flat = a.reshape(a.shape[0], -1)
    s = np.sign(flat[np.arange(len(flat)), np.abs(flat).argmax(1)])
    return a * s[:, None, None]


def drum_geometry(perms, tri):
    place = unfold(perms, tri)
    _, V = check(perms, tri)
    loop, _ = boundary_loop(perms, V)
    return {"place": [[round(float(x), 9) for x in M[:2].ravel()] for M in place],
            "outline": [[round(float(x), 6), round(float(y), 6)] for x, y in loop]}


out = {}

# ---------------------------------------------------------------- GWW (7_3)
cls, _, _ = classes()
t = cls[1][2]
PA, PB = [perm_points(g) for g in t], [perm_lines(g) for g in t]
tri = triangle(math.radians(45), math.radians(90))
N_FINE, N_PAGE, M = 64, 16, 160
A, B = Drum(PA, tri, N_FINE), Drum(PB, tri, N_FINE)
lA, UA = A.eigs(M)
lB, UB = B.eigs(M)
print(f"GWW solved at N={N_FINE}: rel diff {np.max(np.abs(lA - lB) / lA):.1e}  ({time.time() - t_start:.0f}s)")
lam_fine, _ = Drum(PA, tri, 128).eigs(M)
print(f"GWW eigenvalues at N=128 ({time.time() - t_start:.0f}s)")
a = fix_sign(sample(A, UA, N_FINE, N_PAGE))
b = fix_sign(sample(B, UB, N_FINE, N_PAGE))
T3 = np.load("T_incidence.npy").astype(int)
T4 = np.load("T_non-incidence.npy").astype(int)
# mode type: same pattern on every tile up to sign  <=>  a Dirichlet mode of the half-square
full = A.per_tile(UA)
tri_mode = [bool(max(np.abs(np.abs(full[k][i]) - np.abs(full[k][0])).max() for i in range(7))
                 / np.abs(full[k]).max() < 1e-6) for k in range(M)]
modes_b64, scales = q16(a)
out["gww"] = {
    "tri": tri.round(12).tolist(), "n": N_PAGE, "tiles": 7, "m": M,
    "lam": [round(float(x), 6) for x in lam_fine],
    "triMode": [i for i, f in enumerate(tri_mode) if f],
    "A": drum_geometry(PA, tri), "B": drum_geometry(PB, tri),
    "permsA": PA, "permsB": PB,
    "T3": T3.tolist(), "T4": T4.tolist(),
    "modes": modes_b64, "scales": scales,
}
print("GWW triangle modes:", [i + 1 for i in out["gww"]["triMode"]])
print("half-square Dirichlet eigenvalues pi^2(m^2+n^2):",
      sorted(round(math.pi ** 2 * (p * p + q * q), 3) for p in range(1, 9) for q in range(1, p) if math.pi ** 2 * (p * p + q * q) < lam_fine[-1]))
print("computed at those positions:", [round(float(lam_fine[i]), 3) for i in out["gww"]["triMode"]])

# The pretender pair 7_2 (right angle at V2, legs 1): only outlines and eigenvalues
t72 = cls[0][2]
QA, QB = [perm_points(g) for g in t72], [perm_lines(g) for g in t72]
tri72 = triangle(math.radians(45), math.radians(45)) * math.sqrt(2)
l72, _ = Drum(QA, tri72, 128).eigs(40)
l72b, _ = Drum(QB, tri72, 64).eigs(40)
l72b_check, _ = Drum(QA, tri72, 64).eigs(40)
print(f"7_2 pair at N=64: rel diff {np.max(np.abs(l72b - l72b_check) / l72b):.1e}")
out["pretender"] = {"tri": tri72.round(12).tolist(), "lam": [round(float(x), 6) for x in l72],
                    "A": drum_geometry(QA, tri72), "B": drum_geometry(QB, tri72)}

# ---------------------------------------------------------------- homophonic (21_1)
tri21 = triangle(math.radians(90), math.radians(60))       # 90 at V0, 60 at V1, 30 at V2
N21_FINE, N21_PAGE, M21 = 32, 8, 120
H1, H2 = Drum(PA21, tri21, N21_FINE), Drum(PB21, tri21, N21_FINE)
h1l, h1U = H1.eigs(M21)
h2l, h2U = H2.eigs(M21)
print(f"21_1 solved at N={N21_FINE}: rel diff {np.max(np.abs(h1l - h2l) / h1l):.1e}  ({time.time() - t_start:.0f}s)")


def special(D, P):
    bary = D.bary
    v1 = int(np.flatnonzero(np.isclose(bary[:, 1], 1.0))[0])
    nodes = [D.l2g[p, v1] for p in range(len(P[0]))]
    best = max(set(nodes), key=nodes.count)
    tile = nodes.index(best)
    return best, tile


s1, tile1 = special(H1, PA21)
s2, tile2 = special(H2, PB21)
print("homophony check:", np.max(np.abs(h1U[s1] ** 2 - h2U[s2] ** 2)) / np.max(h1U[s1] ** 2))
ha = fix_sign(sample(H1, h1U, N21_FINE, N21_PAGE))
hb = fix_sign(sample(H2, h2U, N21_FINE, N21_PAGE))
ma, sa = q16(ha)
mb, sb = q16(hb)
v1_page = int(np.flatnonzero(np.isclose(base_mesh(N21_PAGE)[0][:, 1], 1.0))[0])
out["homo"] = {
    "tri": tri21.round(12).tolist(), "n": N21_PAGE, "tiles": 21, "m": M21,
    "lam": [round(float(x), 6) for x in h1l],
    "A": drum_geometry(PA21, tri21), "B": drum_geometry(PB21, tri21),
    "modesA": ma, "scalesA": sa, "modesB": mb, "scalesB": sb,
    "special": {"A": {"tile": int(tile1), "node": v1_page, "xy": H1.xy[s1].round(9).tolist()},
                "B": {"tile": int(tile2), "node": v1_page, "xy": H2.xy[s2].round(9).tolist()}},
}

# ---------------------------------------------------------------- shape map
sh = json.load(open("shapes.json"))
code = {"ok": "o", "pinch": "p", "congruent": "c", "one": "1", "slit": "s", "overlap": "x"}
names = {0: "7₂", 1: "7₃", 2: "7₁"}
out["shapes"] = {"steps": sh["steps"], "families": []}
for c in sh["classes"]:
    ci = c["cls"]
    tt = cls[ci][2]
    out["shapes"]["families"].append({
        "name": names[ci],
        "permsA": [perm_points(g) for g in tt], "permsB": [perm_lines(g) for g in tt],
        "grid": "".join(code[st] for _, _, st in c["grid"]),
        "tally": c["tally"],
    })

json.dump(out, open("page_data.json", "w"), separators=(",", ":"))
qb, sbs = q16(b)
json.dump({"gwwB": qb, "gwwBscales": sbs, "lamA": lA.tolist(), "lamB": lB.tolist()},
          open("verify_data.json", "w"))
print(f"page_data.json {len(open('page_data.json').read()) / 1e3:.0f} kB  ({time.time() - t_start:.0f}s total)")
