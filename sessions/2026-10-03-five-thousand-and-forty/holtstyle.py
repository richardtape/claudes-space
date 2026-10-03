"""Holt-style: two singles, at most MAXODD out-of-course leads, at most MAXBOBS bobs.
usage: holtstyle.py MAXBOBS MAXODD"""
import sys, time
from compose_sat import *

B, MAXODD = int(sys.argv[1]), int(sys.argv[2])
ODD = [x for x in TL if parity(x) == 1]

def extra(m):
    cl = []
    for lits, f, bound in [([m.var[x, 's'] for x in TL], CardEnc.equals, 2),
                           ([m.var[x, 'b'] for x in TL], CardEnc.atmost, B),
                           ([m.var[x, 'u'] for x in ODD], CardEnc.atmost, MAXODD)]:
        enc = f(lits=lits, bound=bound, top_id=m.n, encoding=EncType.totalizer if f is CardEnc.atmost else EncType.seqcounter)
        m.n = enc.nv; cl += enc.clauses
    return cl

t = time.time()
sol = solve(extra, verbose=False, limit=100000)
dt = round(time.time() - t, 1)
if sol:
    c = calling(sol); rows, end = touch(c)
    assert len(set(rows)) == 5040 and end == ROUNDS
    print(f'B<={B} odd<={MAXODD}: FOUND {dt}s bobs={c.count("b")} singles at {[i + 1 for i, k in enumerate(c) if k == "s"]} {c}', flush=True)
else:
    print(f'B<={B} odd<={MAXODD}: none ({dt}s)', flush=True)
