"""Find true extents (5040) of Grandsire Triples with a SAT solver.

Model: every treble-leading row x (720 of them) may be a lead head. Variable c[x,k]
says "a lead starts at x and ends with call k" (k in p, b, s). Every one of the
5040 rows must be rung exactly once; every used lead head has exactly one
predecessor; the leads must form a single cycle through rounds (enforced lazily:
solve, find the short cycles, forbid them, solve again).
"""
import sys, itertools, random
from pysat.solvers import Cadical153
from pysat.card import CardEnc, EncType
from ringing import *

K = 'pbs'
LEAD = {k: lead(ROUNDS, k)[0] for k in K}
STEP = {k: lead(ROUNDS, k)[1] for k in K}
TL = [r for r in itertools.permutations(ROUNDS) if r[0] == 1]


class Model:
    def __init__(self):
        self.n = 0
        self.var = {}
        self.clauses = []
        for x in TL:
            for k in K:
                self.var[x, k] = self.new()
            self.var[x, 'u'] = self.new()
        self.build()

    def new(self):
        self.n += 1
        return self.n

    def exactly_one(self, lits):
        enc = CardEnc.equals(lits=lits, bound=1, top_id=self.n, encoding=EncType.seqcounter if len(lits) > 6 else EncType.pairwise)
        self.n = max(self.n, enc.nv)
        self.clauses += enc.clauses

    def at_most_one(self, lits):
        for a, b in itertools.combinations(lits, 2):
            self.clauses.append([-a, -b])

    def build(self):
        v = self.var
        for x in TL:
            # u[x] <-> exactly one call
            self.at_most_one([v[x, k] for k in K])
            self.clauses.append([-v[x, 'u']] + [v[x, k] for k in K])
            for k in K:
                self.clauses.append([-v[x, k], v[x, 'u']])
        # row cover
        cover = {}
        for x in TL:
            for i, r in enumerate(LEAD['p'][:13]):
                cover.setdefault(compose(x, r), []).append(v[x, 'u'])
            cover.setdefault(compose(x, LEAD['p'][13]), []).append(v[x, 'p'])
            rb = compose(x, LEAD['b'][13])
            cover.setdefault(rb, []).extend([v[x, 'b'], v[x, 's']])
        assert len(cover) == 5040
        for r, lits in cover.items():
            self.exactly_one(lits)
        # succession
        preds = {}
        for x in TL:
            for k in K:
                y = compose(x, STEP[k])
                preds.setdefault(y, []).append(v[x, k])
                self.clauses.append([-v[x, k], v[y, 'u']])
        for y in TL:
            self.at_most_one(preds[y])
            self.clauses.append([-v[y, 'u']] + preds[y])
        self.clauses.append([v[ROUNDS, 'u']])

    def decode(self, model):
        s = set(l for l in model if l > 0)
        return {x: k for x in TL for k in K if self.var[x, k] in s}


def cycles_of(sol):
    seen, out = set(), []
    for x in sol:
        if x in seen: continue
        cyc = []
        while x not in seen:
            seen.add(x); cyc.append(x); x = compose(x, STEP[sol[x]])
        out.append(cyc)
    return out


def solve(extra=lambda m: [], seed=0, verbose=True, limit=5000):
    m = Model()
    m.clauses += extra(m)
    s = Cadical153(bootstrap_with=m.clauses)
    it = 0
    while s.solve():
        it += 1
        sol = m.decode(s.get_model())
        cyc = cycles_of(sol)
        if verbose and (it % 20 == 1 or len(cyc) == 1):
            print(f'iter {it}: {len(sol)} leads in {len(cyc)} cycles', file=sys.stderr)
        if len(cyc) == 1:
            return sol
        for c in cyc:
            S = set(c)
            leaving = [m.var[x, k] for x in S for k in K if compose(x, STEP[k]) not in S]
            if ROUNDS in S:
                s.add_clause(leaving)
            else:
                for x in c:
                    s.add_clause([-m.var[x, 'u']] + leaving)
        if it > limit: break
    return None


def calling(sol):
    out, x = [], ROUNDS
    while True:
        k = sol[x]; out.append(k); x = compose(x, STEP[k])
        if x == ROUNDS: return ''.join(out)


if __name__ == '__main__':
    sol = solve()
    if sol:
        c = calling(sol)
        rows, end = touch(c)
        print('leads', len(c), 'rows', len(rows), 'distinct', len(set(rows)), 'comes round', end == ROUNDS)
        print('bobs', c.count('b'), 'singles', c.count('s'))
        print(c)
