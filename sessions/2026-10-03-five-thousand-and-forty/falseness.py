from ringing import *
from collections import Counter, defaultdict
exec(open('structure.py').read().split('# relative permutation')[0].split("print(len(TL)")[0])

# index: for each row, which (even LH, call-class) leads contain it
L = {c: lead(ROUNDS, c)[0] for c in 'pb'}
where = defaultdict(list)
for x in even:
    for c in 'pb':
        for i, r in enumerate(L[c]):
            row = compose(x, r)
            if c == 'b' and i != 13: continue  # bob only differs at row 13
            where[row].append((x, c, i))
# an odd lead from g: which even leads does it hit, at which row indices
g = odd[5]
for c in 'pb':
    hits = Counter()
    for i, r in enumerate(L[c]):
        for (x, cc, j) in where[compose(g, r)]:
            hits[(fmt(x), cc)] += 1
    print('odd lead', fmt(g), c, '->', dict(hits))
