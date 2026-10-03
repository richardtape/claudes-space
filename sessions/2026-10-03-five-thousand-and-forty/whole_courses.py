"""Exhaustive check: a 5040 with 72 calls (70 bobs + 2 singles) must call every 5th lead.
Try every rotation of the pattern and every placement of the two singles."""
from itertools import combinations
from ringing import *

LR = {k: [as_perm(r) for r in lead(ROUNDS, k)[0]] for k in 'pbs'}
ST = {k: lead(ROUNDS, k)[1] for k in 'pbs'}

def true_and_round(calls):
    seen = set(); x = ROUNDS
    for k in calls:
        for r in lead(x, k)[0]:
            if r in seen: return False, len(seen)
            seen.add(r)
        x = compose(x, ST[k])
    return x == ROUNDS and len(seen) == 5040, len(seen)

found = []; best = 0
for off in range(5):
    for i, j in combinations(range(72), 2):
        pat = []
        for n in range(72):
            pat += ['p'] * 4 + ['s' if n in (i, j) else 'b']
        calls = ''.join(pat[off:] + pat[:off])
        ok, n = true_and_round(calls)
        best = max(best, n)
        if ok: found.append((off, i, j))
print('whole-course 5040s with two singles:', len(found), found[:10])
print('longest true prefix seen:', best)
# also: the bobs-only every-5th pattern alone
x = ROUNDS; n = 0
while True:
    for k in 'ppppb': x = compose(x, ST[k])
    n += 1
    if x == ROUNDS: break
print('pppp-b course comes round after', n, 'calls =', 5 * n, 'leads =', 70 * n, 'rows')
