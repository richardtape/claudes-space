"""Bobs only: how many of the 360 leads can one round block (through rounds) contain?"""
import random
from qsets import *

def block_sizes(bobbed):
    succ = [BN[i] if qset[i] in bobbed else PN[i] for i in range(360)]
    seen = [False] * 360; sizes = []
    for i in range(360):
        if seen[i]: continue
        n = 0; j = i
        while not seen[j]: seen[j] = True; j = succ[j]; n += 1
        sizes.append((n, i))
    return sizes

def rounds_block(bobbed):
    succ = [BN[i] if qset[i] in bobbed else PN[i] for i in range(360)]
    n = 0; j = 0
    while True:
        j = succ[j]; n += 1
        if j == 0: return n

best = 0; best_set = None
for seed in range(60):
    rnd = random.Random(seed)
    bobbed = set(); cur = rounds_block(bobbed)
    T = 3.0
    for step in range(6000):
        q = rnd.randrange(72)
        t = bobbed ^ {q}; v = rounds_block(t)
        if v >= cur or rnd.random() < pow(2.718, (v - cur) / T):
            bobbed, cur = t, v
            if cur > best:
                best, best_set = cur, set(bobbed)
        T = max(0.05, T * 0.999)
print('largest round block through rounds found:', best, 'leads =', best * 14, 'rows')
print('block sizes in that configuration:', sorted(s for s, _ in block_sizes(best_set)))
print('bobs used:', 5 * len(best_set))

import json
members = [fmt(EVEN[qsets[q][0]]) for q in sorted(best_set)]
json.dump({'blocks': sorted(s for s, _ in block_sizes(best_set)), 'bobbed_qset_members': members}, open('thompson357.json', 'w'))
print('wrote thompson357.json with', len(members), 'Q-sets')
