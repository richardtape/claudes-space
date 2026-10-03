"""Bob Q-sets on the 360 in-course lead heads, and Thompson's parity in action."""
import random
from itertools import permutations
from ringing import *

P = lead(ROUNDS, 'p')[1]; B = lead(ROUNDS, 'b')[1]
EVEN = sorted(r for r in permutations(ROUNDS) if r[0] == 1 and parity(r) == 0)
IDX = {r: i for i, r in enumerate(EVEN)}
PN = [IDX[compose(r, P)] for r in EVEN]       # plain successor
BN = [IDX[compose(r, B)] for r in EVEN]       # bob successor
PPRED = {PN[i]: i for i in range(360)}

# courses: cycles of the plain successor
course = [-1] * 360; courses = []
for i in range(360):
    if course[i] >= 0: continue
    c = []; j = i
    while course[j] < 0:
        course[j] = len(courses); c.append(j); j = PN[j]
    courses.append(c)
# Q-sets: orbits of i -> plain-predecessor of bob-successor
qset = [-1] * 360; qsets = []
for i in range(360):
    if qset[i] >= 0: continue
    q = []; j = i
    while qset[j] < 0:
        qset[j] = len(qsets); q.append(j); j = PPRED[BN[j]]
    qsets.append(q)

def blocks(bobbed):
    succ = [BN[i] if qset[i] in bobbed else PN[i] for i in range(360)]
    seen = [False] * 360; n = 0
    for i in range(360):
        if seen[i]: continue
        n += 1; j = i
        while not seen[j]: seen[j] = True; j = succ[j]
    return n

if __name__ == '__main__':
    print('courses', len(courses), 'qsets', len(qsets))
    print('Q-set members in distinct courses?', all(len({course[j] for j in q}) == 5 for q in qsets))
    print('rounds is lead', IDX[ROUNDS])
    # greedy merging from many random orders
    finals = {}
    for seed in range(200):
        rnd = random.Random(seed)
        bobbed = set(); n = blocks(bobbed)
        while True:
            order = list(range(72)); rnd.shuffle(order)
            for q in order:
                t = bobbed ^ {q}; m = blocks(t)
                if m < n: bobbed, n = t, m; break
            else: break
        finals[n] = finals.get(n, 0) + 1
    print('greedy merge final block counts over 200 random orders:', finals)
