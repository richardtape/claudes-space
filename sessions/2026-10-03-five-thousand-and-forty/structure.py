from ringing import *
from collections import Counter

# lead transformations as rows from rounds
P = lead(ROUNDS, 'p')[1]; B = lead(ROUNDS, 'b')[1]; S = lead(ROUNDS, 's')[1]
nxt = lambda x, c: compose(x, {'p': P, 'b': B, 's': S}[c])

# all treble-leading rows, split by parity
TL = [r for r in permutations(ROUNDS) if r[0] == 1]
even = [r for r in TL if parity(r) == 0]
odd = [r for r in TL if parity(r) == 1]
print(len(TL), len(even), len(odd))

# reachable LHs by p,b from rounds
seen = {ROUNDS}; st = [ROUNDS]
while st:
    x = st.pop()
    for c in 'pb':
        y = nxt(x, c)
        if y not in seen: seen.add(y); st.append(y)
print('bobs-only reachable LHs:', len(seen), 'all even:', all(parity(r) == 0 for r in seen))

# bob Q-sets: x -> b, the lead whose plain successor equals x's bob successor
pred_plain = {nxt(x, 'p'): x for x in even}
def qset(x):
    q = [x]
    while True:
        y = pred_plain[nxt(q[-1], 'b')]
        if y == x: return q
        q.append(y)
sizes = Counter(len(qset(x)) for x in even)
print('bob Q-set sizes:', sizes)

# cycles of plain successor on even LHs
def cycles(succ, nodes):
    seen = set(); n = 0
    for x in nodes:
        if x in seen: continue
        n += 1
        while x not in seen:
            seen.add(x); x = succ[x]
    return n
succ = {x: nxt(x, 'p') for x in even}
print('plain courses:', cycles(succ, even))

# rows of a lead: does bob/single lead share rows with plain lead?
lp = lead(ROUNDS, 'p')[0]; lb = lead(ROUNDS, 'b')[0]; ls = lead(ROUNDS, 's')[0]
print('plain vs bob differing rows:', [(fmt(a), fmt(b)) for a, b in zip(lp, lb) if a != b])
print('bob vs single rows identical:', lb == ls)

# relative permutation of bob vs plain lead end
inv = lambda r: tuple(sorted(range(1, len(r) + 1), key=lambda i: r[i - 1]))
t = compose(B, inv(P))
print('B, P:', fmt(B), fmt(P), ' B·P^-1 =', fmt(t))
# cycle type of t as a permutation of positions
def ctype(r):
    seen = set(); out = []
    for i in range(1, len(r) + 1):
        if i in seen: continue
        n = 0; j = i
        while j not in seen: seen.add(j); j = r[j - 1]; n += 1
        out.append(n)
    return sorted(out, reverse=True)
print('cycle type of B·P^-1:', ctype(t), ' of S·P^-1:', ctype(compose(S, inv(P))))

# Thompson's parity, empirically: toggle random sets of Q-sets, count round blocks
import random
qsets = []; done = set()
for x in even:
    if x in done: continue
    q = qset(x); qsets.append(q); done.update(q)
print('number of bob Q-sets:', len(qsets))
random.seed(1)
counts = Counter()
for trial in range(20000):
    bobbed = set()
    for q in qsets:
        if random.random() < random.choice([0.1, 0.3, 0.5]): bobbed.update(q)
    succ = {x: nxt(x, 'b' if x in bobbed else 'p') for x in even}
    assert len(set(succ.values())) == 360
    counts[cycles(succ, even)] += 1
print('round-block counts seen (20000 random bob choices):', sorted(counts.items())[:12], '...')
print('any odd?', any(k % 2 for k in counts))
