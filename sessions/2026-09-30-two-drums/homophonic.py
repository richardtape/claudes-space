"""Check isospectrality and homophony of 21_1 numerically."""
import math, sys, time
import numpy as np
from PIL import Image, ImageDraw
from fem import Drum
from geometry import check, triangle
from pair21 import PA, PB, vertex_orbits

x = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
m = int(sys.argv[3]) if len(sys.argv) > 3 else 80
tri = triangle(math.radians(120 - x), math.radians(60))

def special_node(D, P):
    """Global node at vertex V1 of the tiles in the closed 6-cycle of colours (0, 2)."""
    from fem import base_mesh
    bary = D.bary
    v1 = int(np.flatnonzero(np.isclose(bary[:, 1], 1.0))[0])   # local node at V1
    # tiles in the cycle: those not fixed by colour 0 or 2 and lying on the 6-orbit
    nodes = set()
    for p in range(len(P[0])):
        if P[0][p] != p and P[2][p] != p:
            # walk the orbit and see if it closes
            nodes.add(D.l2g[p, v1])
    # the interior one is the node that 6 tiles share
    counts = {nd: sum(D.l2g[p, v1] == nd for p in range(len(P[0]))) for nd in nodes}
    return max(counts, key=counts.get), counts

t0 = time.time()
A, B = Drum(PA, tri, N), Drum(PB, tri, N)
lA, UA = A.eigs(m); lB, UB = B.eigs(m)
print(f"V2={x}  N={N}  dof A {len(A.free)} B {len(B.free)}  areas {A.area():.4f} {B.area():.4f}  ({time.time()-t0:.1f}s)")
print(f"max relative eigenvalue difference over {m} modes: {np.max(np.abs(lA-lB)/lA):.2e}")
sa, ca = special_node(A, PA); sb, cb = special_node(B, PB)
print("special node in A shared by", ca[sa], "tiles; in B by", cb[sb])
va, vb = UA[sa], UB[sb]
print("mode  lambda     phiA(s)^2     phiB(s)^2")
for k in range(12):
    print(f"{k+1:4d} {lA[k]:9.4f}  {va[k]**2:.10f}  {vb[k]**2:.10f}")
gaps = np.diff(lA) / lA[1:]
print(f"smallest relative gap: {gaps.min():.1e}")
print(f"max |phiA(s)^2 - phiB(s)^2| / max phi^2 over {m} modes: {np.max(np.abs(va**2-vb**2))/np.max(va**2):.2e}")
# compare: a random interior node
rng = np.random.default_rng(1)
i = rng.choice(A.free)
print(f"for contrast, a random node of A vs the special node of B: {np.max(np.abs(UA[i]**2 - vb**2))/np.max(vb**2):.2e}")

# drawing
for name, P in (("A", PA), ("B", PB)):
    s, V = check(P, tri)
    pts = np.vstack(V); mn, mx = pts.min(0), pts.max(0)
    sc = 560 / (mx - mn).max()
    im = Image.new("RGB", (600, 600), "white"); d = ImageDraw.Draw(im)
    for i, T in enumerate(V):
        Q = [(20 + (u - mn[0]) * sc, 580 - (v - mn[1]) * sc) for u, v in T]
        d.polygon(Q, fill=(200, 220, 240), outline=(60, 60, 60))
        cx, cy = np.mean(Q, axis=0); d.text((cx - 4, cy - 5), str(i), fill="red")
    S = (A if name == "A" else B).xy[sa if name == "A" else sb]
    d.ellipse([20 + (S[0]-mn[0])*sc - 5, 580 - (S[1]-mn[1])*sc - 5, 20 + (S[0]-mn[0])*sc + 5, 580 - (S[1]-mn[1])*sc + 5], fill="black")
    im.save(f"img/pair21_{name}_{int(x)}.png")
