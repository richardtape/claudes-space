import sys, time
from compose_sat import *

def extra(m):
    lits = [m.var[x, 's'] for x in TL]
    enc = CardEnc.equals(lits=lits, bound=int(sys.argv[1]) if len(sys.argv) > 1 else 2, top_id=m.n, encoding=EncType.seqcounter)
    m.n = enc.nv
    return enc.clauses

t = time.time()
sol = solve(extra)
print('time', round(time.time() - t, 1), 's')
if sol:
    c = calling(sol)
    rows, end = touch(c)
    print('rows', len(rows), 'distinct', len(set(rows)), 'round', end == ROUNDS, 'bobs', c.count('b'), 'singles', c.count('s'))
    print(c)
