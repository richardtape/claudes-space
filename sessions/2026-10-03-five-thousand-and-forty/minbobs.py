"""How few bobs can a true 5040 of Grandsire Triples with exactly two singles have?
usage: minbobs.py MAXBOBS [parts]"""
import sys, time
from compose_sat import *

B = int(sys.argv[1])

def extra(m):
    out = []
    for lits, op, bound in [([m.var[x, 's'] for x in TL], 'eq', 2), ([m.var[x, 'b'] for x in TL], 'le', B)]:
        f = CardEnc.equals if op == 'eq' else CardEnc.atmost
        enc = f(lits=lits, bound=bound, top_id=m.n, encoding=EncType.seqcounter if op == 'eq' else EncType.totalizer)
        m.n = enc.nv
        out += enc.clauses
    return out

t = time.time()
sol = solve(extra, verbose=False, limit=100000)
dt = round(time.time() - t, 1)
if sol:
    c = calling(sol)
    rows, end = touch(c)
    assert len(set(rows)) == 5040 and end == ROUNDS
    print(f'B<={B}: FOUND in {dt}s  bobs={c.count("b")} singles={c.count("s")}  {c}')
else:
    print(f'B<={B}: UNSAT in {dt}s')
