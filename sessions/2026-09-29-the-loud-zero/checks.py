import itertools, numpy as np
from sandpile import *

def burn(mask):
    # beta(v) = number of sink-neighbours of v
    p = np.pad(mask, 1)
    return (~p[:-2,1:-1]).astype(int) + (~p[2:,1:-1]) + (~p[1:-1,:-2]) + (~p[1:-1,2:])

def laplacian_det(mask):
    idx = {v: i for i, v in enumerate(zip(*np.nonzero(mask)))}
    L = 4 * np.eye(len(idx))
    for (r, c), i in idx.items():
        for d in ((1,0),(-1,0),(0,1),(0,-1)):
            j = idx.get((r+d[0], c+d[1]))
            if j is not None: L[i, j] = -1
    return round(np.linalg.det(L))

# 1. group order = # spanning trees (matrix-tree theorem), brute force on tiny grids
for shape in [(1,1),(1,2),(2,2),(2,3),(3,3)]:
    m = rect(*shape); b = burn(m); n = m.size
    rec = 0
    for cfg in itertools.product(range(4), repeat=n):
        c = np.array(cfg).reshape(shape)
        if (stabilize(c + b, m)[0] == c).all(): rec += 1
    print(f"{shape}: recurrent configs = {rec:>6}   det(reduced Laplacian) = {laplacian_det(m):>6}")

# 2. identity really is an identity, on a bigger grid
rng = np.random.default_rng(1)
m = square(64); e = identity(m)
print("e + e == e:", (stabilize(e + e, m)[0] == e).all())
ok = 0
for _ in range(20):
    c = stabilize(rng.integers(0, 4, m.shape) + 3, m)[0]   # a random recurrent config
    ok += (stabilize(c + e, m)[0] == c).all()
print(f"c + e == c for {ok}/20 random recurrent c")
_, odo = stabilize(c + e, m, count=True)
print(f"...yet adding e to the last one caused {odo.sum():,} topplings, only to change nothing")
# the all-zero config is NOT recurrent, so e is not 'zero'
print("zeros + e == zeros?", (stabilize(e, m)[0] == 0).all(), " (zero isn't in the group)")
