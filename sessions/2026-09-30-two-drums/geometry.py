"""Unfold a gluing pattern into the plane by reflecting a base triangle.

Tile 0 is the base triangle.  If tile p is glued to tile q across edge k, then
q's placement is p's placement composed with the reflection of the base
triangle in its edge k.  Edge k is the edge opposite vertex k.
"""
import itertools
import math

import numpy as np

from fano import INVOLUTIONS, generated_order, perm_lines, perm_points


def triangle(alpha, beta):
    """Base triangle with angle alpha at V0, beta at V1 and edge V0V1 of length 1."""
    gamma = math.pi - alpha - beta
    # Law of sines: |V0V2| = sin(beta)/sin(gamma)
    r = math.sin(beta) / math.sin(gamma)
    return np.array([[0.0, 0.0], [1.0, 0.0], [r * math.cos(alpha), r * math.sin(alpha)]])


def reflection(P, Q):
    """Affine reflection in the line PQ as a 3x3 matrix."""
    d = (Q - P) / np.linalg.norm(Q - P)
    R = 2 * np.outer(d, d) - np.eye(2)
    t = P - R @ P
    M = np.eye(3)
    M[:2, :2] = R
    M[:2, 2] = t
    return M


def unfold(perms, tri):
    """Return a list of placements (3x3 affine matrices), one per tile."""
    refl = [reflection(tri[(k + 1) % 3], tri[(k + 2) % 3]) for k in range(3)]
    place = {0: np.eye(3)}
    stack = [0]
    while stack:
        p = stack.pop()
        for k, perm in enumerate(perms):
            q = perm[p]
            if q != p and q not in place:
                place[q] = place[p] @ refl[k]
                stack.append(q)
    n = len(perms[0])
    assert len(place) == n, 'gluing graph is not connected'
    return [place[i] for i in range(n)]


def tile_vertices(place, tri):
    h = np.c_[tri, np.ones(3)]
    return [(M @ h.T).T[:, :2] for M in place]


def _overlap(T1, T2, eps=1e-9):
    """True if two triangles share interior area (separating axis test)."""
    for T in (T1, T2):
        for i in range(3):
            e = T[(i + 1) % 3] - T[i]
            n = np.array([-e[1], e[0]])
            a, b = T1 @ n, T2 @ n
            if a.max() <= b.min() + eps * np.linalg.norm(n) or b.max() <= a.min() + eps * np.linalg.norm(n):
                return False
    return True


def _segments_overlap(s, t, eps=1e-9):
    """True if two segments are collinear and overlap in a piece of positive length."""
    (p0, p1), (q0, q1) = s, t
    d = p1 - p0
    L = np.linalg.norm(d)
    u = d / L
    nrm = np.array([-u[1], u[0]])
    if abs((q0 - p0) @ nrm) > eps or abs((q1 - p0) @ nrm) > eps:
        return False
    a, b = sorted(((q0 - p0) @ u, (q1 - p0) @ u))
    return min(b, L) - max(a, 0) > eps


def check(perms, tri):
    """Classify the unfolded drum: 'overlap', 'slit' or 'ok'."""
    place = unfold(perms, tri)
    V = tile_vertices(place, tri)
    n = len(perms[0])
    for i, j in itertools.combinations(range(n), 2):
        if _overlap(V[i], V[j]):
            return "overlap", V
    # Boundary edges: edge k of tile p where perms[k][p] == p.
    bnd = [(V[p][(k + 1) % 3], V[p][(k + 2) % 3]) for p in range(n) for k in range(3) if perms[k][p] == p]
    for s, t in itertools.combinations(bnd, 2):
        if _segments_overlap(s, t):
            return "slit", V
    return "ok", V


def boundary_loop(perms, V, ndigits=9):
    """Walk the boundary with the interior on the left.  Returns (vertices, pinch)
    where vertices is the closed walk (a vertex where the boundary touches itself
    appears twice) and pinch says whether that happens.  Collinear points are dropped."""
    n = len(perms[0])
    key = lambda P: (round(float(P[0]), ndigits), round(float(P[1]), ndigits))
    out_edges = {}
    for p in range(n):
        T = V[p]
        ccw = (T[1] - T[0])[0] * (T[2] - T[0])[1] - (T[1] - T[0])[1] * (T[2] - T[0])[0] > 0
        for k in range(3):
            if perms[k][p] == p:
                a, b = T[(k + 1) % 3], T[(k + 2) % 3]
                if not ccw:
                    a, b = b, a
                out_edges.setdefault(key(a), []).append(key(b))
    pinch = any(len(v) > 1 for v in out_edges.values())
    total = sum(len(v) for v in out_edges.values())
    start = next(iter(out_edges))
    walk, cur, prev = [start], start, None
    used = 0
    while True:
        opts = out_edges[cur]
        if prev is None or len(opts) == 1:
            nxt = opts[0]
        else:
            din = np.subtract(cur, prev)
            def turn(w):                                   # signed angle from din to (w - cur)
                d = np.subtract(w, cur)
                return math.atan2(din[0] * d[1] - din[1] * d[0], din @ d)
            nxt = min(opts, key=turn)                       # most clockwise
        opts.remove(nxt)
        used += 1
        prev, cur = cur, nxt
        if cur == start and not out_edges[cur]:
            break
        walk.append(cur)
    assert used == total, "boundary is not a single closed walk"
    W = np.array(walk)
    keep = []
    m = len(W)
    for i in range(m):
        a, b, c = W[i - 1], W[i], W[(i + 1) % m]
        cr = (b - a)[0] * (c - b)[1] - (b - a)[1] * (c - b)[0]
        if abs(cr) > 1e-9 or (b - a) @ (c - b) < 0:
            keep.append(W[i])
    return np.array(keep), pinch


def boundary_polygon(perms, V, ndigits=9):
    return boundary_loop(perms, V, ndigits)[0]


def _signature(poly):
    """(interior angle, following edge length) at each vertex, polygon made CCW."""
    P = np.asarray(poly, dtype=float)
    n = len(P)
    sig = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        u, v = a - b, c - b
        ang = math.atan2(u[0] * v[1] - u[1] * v[0], u @ v)   # angle from (b->c) to (b->a), CCW interior
        ang = (-ang) % (2 * math.pi)
        sig.append((ang, np.linalg.norm(c - b)))
    return sig


def congruent(polyA, polyB, tol=1e-7):
    """True if the two polygons are congruent (rotation, translation or reflection)."""
    sA, sB = _signature(polyA), _signature(polyB)
    n = len(sA)
    if n != len(sB):
        return False
    # mirror of A, re-oriented CCW: reverse order, each angle now followed by the previous edge
    mA = [(sA[i][0], sA[i - 1][1]) for i in range(n - 1, -1, -1)]
    for S in (sA, mA):
        for r in range(n):
            if all(abs(S[(i + r) % n][0] - sB[i][0]) < tol and abs(S[(i + r) % n][1] - sB[i][1]) < tol for i in range(n)):
                return True
    return False
