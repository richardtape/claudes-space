"""Linear finite elements for a drum made of reflected copies of a base triangle.

The base triangle is cut into N^2 small triangles.  Every tile is an isometric copy
of that mesh, so the global mesh is conforming and every tile carries the same
local node numbering.  That local numbering is what makes transplantation a
plain n x n matrix acting on per-tile arrays.

Dirichlet boundary (the membrane is fixed at the rim).
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from geometry import unfold


def base_mesh(N):
    """Nodes as barycentric index triples (i, j, k), i+j+k = N, weight on V0, V1, V2.
    Returns (bary, tris): bary is (n, 3) floats, tris is a list of node-index triples."""
    idx = {}
    bary = []
    for i in range(N + 1):
        for j in range(N + 1 - i):
            idx[(i, j)] = len(bary)
            bary.append((i / N, j / N, (N - i - j) / N))
    tris = []
    for i in range(N):
        for j in range(N - i):
            tris.append((idx[(i, j)], idx[(i + 1, j)], idx[(i, j + 1)]))
            if i + j < N - 1:
                tris.append((idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)]))
    return np.array(bary), np.array(tris)


def on_edge(bary, k):
    """Local nodes lying on edge k (opposite vertex k): barycentric weight k is 0."""
    return np.isclose(bary[:, k], 0.0)


class Drum:
    def __init__(self, perms, tri, N):
        self.perms, self.tri, self.N = perms, tri, N
        self.bary, self.ltris = base_mesh(N)
        nl = len(self.bary)
        place = unfold(perms, tri)
        local_xy = self.bary @ tri                       # base-triangle coordinates
        h = np.c_[local_xy, np.ones(nl)]
        keymap, xy = {}, []
        self.n = nt = len(perms[0])
        self.l2g = np.zeros((nt, nl), dtype=int)          # tile, local node -> global node
        for p, M in enumerate(place):
            P = (M @ h.T).T[:, :2]
            for n, (x, y) in enumerate(P):
                key = (round(x, 9), round(y, 9))
                if key not in keymap:
                    keymap[key] = len(xy)
                    xy.append((x, y))
                self.l2g[p, n] = keymap[key]
        self.xy = np.array(xy)
        ng = len(xy)
        # Dirichlet nodes: on any boundary edge of any tile
        fixed = np.zeros(ng, dtype=bool)
        for p in range(nt):
            for k in range(3):
                if perms[k][p] == p:
                    fixed[self.l2g[p, on_edge(self.bary, k)]] = True
        self.fixed = fixed
        self.free = np.flatnonzero(~fixed)
        # Global triangles
        self.gtris = np.vstack([self.l2g[p][self.ltris] for p in range(nt)])
        self.K, self.M = self._assemble()

    def _assemble(self):
        xy, T = self.xy, self.gtris
        ng = len(xy)
        rows, cols, kv, mv = [], [], [], []
        for t in T:
            P = xy[t]
            B = np.array([P[1] - P[0], P[2] - P[0]]).T          # 2x2
            area = abs(np.linalg.det(B)) / 2
            G = np.linalg.inv(B).T @ np.array([[-1, 1, 0], [-1, 0, 1]])   # gradients of hat functions
            Ke = area * G.T @ G
            Me = area / 12 * (np.ones((3, 3)) + np.eye(3))
            for a in range(3):
                for b in range(3):
                    rows.append(t[a]); cols.append(t[b])
                    kv.append(Ke[a, b]); mv.append(Me[a, b])
        K = sp.csr_matrix((kv, (rows, cols)), shape=(ng, ng))
        M = sp.csr_matrix((mv, (rows, cols)), shape=(ng, ng))
        f = self.free
        return K[f][:, f].tocsc(), M[f][:, f].tocsc()

    def eigs(self, m):
        """Lowest m eigenpairs of K u = lam M u, M-orthonormal, as full global vectors."""
        lam, U = spla.eigsh(self.K, k=m, M=self.M, sigma=0, which="LM")
        order = np.argsort(lam)
        lam, U = lam[order], U[:, order]
        full = np.zeros((len(self.xy), m))
        full[self.free] = U
        return lam, full

    def per_tile(self, full):
        """Global vectors (ng, m) -> per-tile local arrays (m, n_tiles, nl)."""
        return np.transpose(full[self.l2g], (2, 0, 1))

    def area(self):
        P = self.xy[self.gtris]
        u, v = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
        return 0.5 * np.abs(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]).sum()
