"""Abelian sandpile on a grid region, grains that fall off the edge vanish (the "sink").

A site with 4+ grains topples: it gives one grain to each of its 4 neighbours.
Order of topplings doesn't matter (the abelian property), so we topple every
unstable site as many times as it can in one vectorised sweep.
"""
import numpy as np
from PIL import Image

# colours for heights 0..3 (and a background for sites outside the region)
PALETTE = np.array([
    [ 18,  22,  38],   # 0  deep ink
    [ 46, 110, 160],   # 1  blue
    [236, 184,  86],   # 2  sand
    [214,  76,  62],   # 3  red
], dtype=np.uint8)
OUTSIDE = np.array([250, 247, 240], dtype=np.uint8)


def stabilize(h, mask=None, count=False):
    """Topple until every site has < 4 grains. Returns (h, topplings or None)."""
    h = h.astype(np.int64).copy()
    if mask is None:
        mask = np.ones(h.shape, dtype=bool)
    h[~mask] = 0
    odo = np.zeros(h.shape, dtype=np.int64) if count else None
    while True:
        t = h >> 2  # h // 4
        if not t.any():
            break
        h -= t << 2
        h[1:, :] += t[:-1, :]
        h[:-1, :] += t[1:, :]
        h[:, 1:] += t[:, :-1]
        h[:, :-1] += t[:, 1:]
        h[~mask] = 0  # anything landing outside the region falls in the sink
        if count:
            odo += t
    return h, odo


def identity(mask):
    """Identity of the sandpile group: (6 - (6)°)° where 6 means 6 grains everywhere."""
    six = np.where(mask, 6, 0)
    s, _ = stabilize(six, mask)
    e, _ = stabilize(six - s, mask)
    return e


def render(h, mask=None, scale=1, path=None):
    img = PALETTE[np.clip(h, 0, 3)]
    if mask is not None:
        img[~mask] = OUTSIDE
    im = Image.fromarray(img)
    if scale != 1:
        im = im.resize((h.shape[1] * scale, h.shape[0] * scale), Image.NEAREST)
    if path:
        im.save(path)
    return im


# --- regions -----------------------------------------------------------------

def square(n):
    return np.ones((n, n), dtype=bool)


def rect(r, c):
    return np.ones((r, c), dtype=bool)


def disc(n):
    y, x = np.mgrid[0:n, 0:n] + 0.5 - n / 2
    return x * x + y * y <= (n / 2) ** 2


def diamond(n):
    y, x = np.mgrid[0:n, 0:n] + 0.5 - n / 2
    return np.abs(x) + np.abs(y) <= n / 2


def triangle(n):
    y, x = np.mgrid[0:n, 0:n] + 0.5
    return np.abs(x - n / 2) <= y / 2


def annulus(n, inner=0.45):
    y, x = np.mgrid[0:n, 0:n] + 0.5 - n / 2
    r2 = x * x + y * y
    return (r2 <= (n / 2) ** 2) & (r2 >= (inner * n / 2) ** 2)


# --- faster stabilisation ------------------------------------------------------
# The odometer u (how often each site topples) is the least u >= 0 with h - L u <= 3,
# where L is the grid Laplacian (4 on the diagonal, -1 per neighbour, sink = boundary).
# Since L u >= h - 3 and L^{-1} is entrywise non-negative, w = L^{-1}(h - 3) is a lower
# bound on u.  Toppling floor(max(w, 0)) first is therefore "legal" in aggregate, and
# ordinary toppling finishes the job with far fewer sweeps.

def _laplacian(mask):
    import scipy.sparse as sp
    idx = -np.ones(mask.shape, dtype=np.int64)
    idx[mask] = np.arange(mask.sum())
    rows, cols, vals = [np.arange(mask.sum())], [np.arange(mask.sum())], [np.full(mask.sum(), 4.0)]
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        a = np.roll(idx, (-dr, -dc), axis=(0, 1))
        # kill wrap-around
        if dr == 1: a[-1, :] = -1
        if dr == -1: a[0, :] = -1
        if dc == 1: a[:, -1] = -1
        if dc == -1: a[:, 0] = -1
        ok = mask & (a >= 0)
        rows.append(idx[ok]); cols.append(a[ok]); vals.append(np.full(ok.sum(), -1.0))
    n = mask.sum()
    return sp.csc_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)), idx


def stabilize_fast(h, mask=None):
    from scipy.sparse.linalg import spsolve
    if mask is None:
        mask = np.ones(h.shape, dtype=bool)
    L, idx = _laplacian(mask)
    w = spsolve(L, (h[mask] - 3).astype(float))
    u0 = np.maximum(np.floor(w - 1e-9), 0).astype(np.int64)
    flat = h[mask].astype(np.int64) - (L @ u0).round().astype(np.int64)
    h2 = np.zeros(h.shape, dtype=np.int64)
    h2[mask] = flat
    out, _ = stabilize(h2, mask)
    return out


def identity_fast(mask):
    six = np.where(mask, 6, 0)
    s = stabilize_fast(six, mask)
    return stabilize_fast(six - s, mask)


# --- C inner loop ----------------------------------------------------------------
import ctypes, os
_lib = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), "libtopple.dylib"))
_lib.stabilize.restype = ctypes.c_int64
_lib.stabilize.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]


def stabilize_c(h, mask=None, return_count=False):
    if mask is None:
        mask = np.ones(h.shape, dtype=bool)
    R, C = h.shape
    hp = np.zeros((R + 2, C + 2), dtype=np.int32)
    mp = np.zeros((R + 2, C + 2), dtype=np.uint8)
    hp[1:-1, 1:-1] = np.where(mask, h, 0)
    mp[1:-1, 1:-1] = mask
    n = _lib.stabilize(hp.ctypes.data, mp.ctypes.data, R, C)
    out = hp[1:-1, 1:-1].astype(np.int64)
    return (out, n) if return_count else out


def stabilize_best(h, mask=None):
    """Linear-solve lower bound on the odometer, then the C loop finishes."""
    from scipy.sparse.linalg import spsolve
    if mask is None:
        mask = np.ones(h.shape, dtype=bool)
    L, _ = _laplacian(mask)
    w = spsolve(L, (h[mask] - 3).astype(float))
    u0 = np.maximum(np.floor(w - 1e-9), 0).astype(np.int64)
    h2 = np.zeros(h.shape, dtype=np.int64)
    h2[mask] = h[mask].astype(np.int64) - (L @ u0).round().astype(np.int64)
    return stabilize_c(h2, mask)


def identity_c(mask, fast=True):
    st = stabilize_best if fast else stabilize_c
    six = np.where(mask, 6, 0)
    return st(six - st(six, mask), mask)
