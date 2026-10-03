"""Two-part 5040s of Grandsire Triples with two singles: part 2 is part 1 transposed by q.
usage: twopart.py MAXBOBS [q-index ...]"""
import sys, time
from compose_sat import *

def involutions():
    out = []
    for r in itertools.permutations(ROUNDS):
        if r[0] == 1 and parity(r) == 1 and compose(r, r) == ROUNDS:
            out.append(r)
    return out

Q = involutions()
B = int(sys.argv[1])
which = [int(a) for a in sys.argv[2:]] or range(len(Q))

for qi in which:
    q = Q[qi]
    def extra(m):
        cl = []
        for x in TL:
            for k in K:
                a, b = m.var[x, k], m.var[compose(q, x), k]
                cl += [[-a, b], [-b, a]]
        for lits, f, bound in [([m.var[x, 's'] for x in TL], CardEnc.equals, 2),
                               ([m.var[x, 'b'] for x in TL], CardEnc.atmost, B)]:
            enc = f(lits=lits, bound=bound, top_id=m.n, encoding=EncType.totalizer if f is CardEnc.atmost else EncType.seqcounter)
            m.n = enc.nv; cl += enc.clauses
        return cl
    t = time.time()
    sol = solve(extra, verbose=False, limit=20000)
    dt = round(time.time() - t, 1)
    if sol:
        c = calling(sol); rows, end = touch(c)
        assert len(set(rows)) == 5040 and end == ROUNDS
        print(f'q={fmt(q)} B<={B}: FOUND {dt}s bobs={c.count("b")} singles at {[i for i, k in enumerate(c) if k == "s"]} {c}', flush=True)
    else:
        print(f'q={fmt(q)} B<={B}: none ({dt}s)', flush=True)
