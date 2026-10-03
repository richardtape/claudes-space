"""The homophonic pair 21_1 of Buser, Conway, Doyle & Semmler (1994), from the
permutations in their Table 2 (generators p, q, r of L3(4) acting on the 21
points / 21 lines of the projective plane of order 4)."""
import itertools
import numpy as np

def cycles_to_perm(s, n=21):
    p = list(range(n))
    for a, b in (map(int, c.split()) for c in s.replace(")", "").split("(") if c.strip()):
        p[a], p[b] = b, a
    return tuple(p)

PTS = {"p": "(2 7)(3 11)(5 12)(8 18)(13 14)(15 17)(16 20)",
       "q": "(0 17)(3 8)(4 12)(6 13)(9 19)(14 15)(16 18)",
       "r": "(1 8)(2 16)(4 11)(5 19)(7 14)(10 17)(13 20)"}
LNS = {"p": "(0 1)(4 17)(7 12)(9 16)(10 20)(11 13)(15 19)",
       "q": "(0 20)(3 16)(6 11)(8 15)(9 19)(10 12)(14 18)",
       "r": "(1 8)(2 16)(4 11)(5 19)(7 14)(10 17)(13 20)"}
PA = [cycles_to_perm(PTS[k]) for k in "pqr"]
PB = [cycles_to_perm(LNS[k]) for k in "pqr"]


def compose(a, b):           # (a o b)(i) = a[b[i]]
    return tuple(a[i] for i in b)


def generate(gens_pairs):
    """Generate the group as pairs (perm on points, perm on lines)."""
    e = (tuple(range(21)), tuple(range(21)))
    seen, frontier = {e}, [e]
    while frontier:
        nxt = []
        for x in frontier:
            for g in gens_pairs:
                y = (compose(g[0], x[0]), compose(g[1], x[1]))
                if y not in seen:
                    seen.add(y)
                    nxt.append(y)
        frontier = nxt
    return seen


def vertex_orbits(perms):
    """For each pair of edge colours (k, l), the orbits of <g_k, g_l> on tiles and
    whether each is a closed cycle (interior vertex) or a chain (boundary vertex)."""
    out = {}
    n = len(perms[0])
    for k, l in ((0, 1), (1, 2), (0, 2)):
        seen, orbs = set(), []
        for s in range(n):
            if s in seen:
                continue
            orb, fr = {s}, [s]
            while fr:
                x = fr.pop()
                for g in (perms[k], perms[l]):
                    if g[x] not in orb:
                        orb.add(g[x]); fr.append(g[x])
            seen |= orb
            closed = all(perms[k][x] != x and perms[l][x] != x for x in orb)
            orbs.append((len(orb), "cycle" if closed else "chain"))
        out[(k, l)] = sorted(orbs)
    return out


if __name__ == "__main__":
    G = generate(list(zip(PA, PB)))
    print("group order:", len(G), "(|PSL(3,4)| = 20160)")
    pa = {x[0] for x in G}; pb = {x[1] for x in G}
    print("faithful on points:", len(pa) == len(G), " on lines:", len(pb) == len(G))
    bad = sum(1 for a, b in G if sum(a[i] == i for i in range(21)) != sum(b[i] == i for i in range(21)))
    print("elements whose fixed-point counts on points and lines differ:", bad)
    for name, P in (("A (points)", PA), ("B (lines)", PB)):
        print(name, "edges glued:", sum(sum(P[k][i] > i for i in range(21)) for k in range(3)))
        for kl, orbs in vertex_orbits(P).items():
            print("   colours", kl, orbs)
