"""Fewest-bob 5040 of Grandsire Triples with exactly two singles, by CP-SAT.

The chain of leads is a single circuit over the 720 treble-leading lead heads, with
unused lead heads skipped by self-loops (AddCircuit). Every row rung exactly once.
usage: cpsat.py SECONDS WORKERS [HINTFILE]
"""
import sys, re, itertools, json, time
from ortools.sat.python import cp_model
from ringing import *

secs, workers = float(sys.argv[1]), int(sys.argv[2])
hint = re.search(r'[pbs]{360}', open(sys.argv[3]).read()).group(0) if len(sys.argv) > 3 else None
K = 'pbs'
LEAD = {k: lead(ROUNDS, k)[0] for k in K}
STEP = {k: lead(ROUNDS, k)[1] for k in K}
TL = [r for r in itertools.permutations(ROUNDS) if r[0] == 1]
ix = {x: i for i, x in enumerate(TL)}

m = cp_model.CpModel()
c = {(x, k): m.NewBoolVar(f'c{ix[x]}{k}') for x in TL for k in K}
skip = {x: m.NewBoolVar(f'skip{ix[x]}') for x in TL}
arcs = []
for x in TL:
    arcs.append((ix[x], ix[x], skip[x]))
    for k in K:
        arcs.append((ix[x], ix[compose(x, STEP[k])], c[x, k]))
m.AddCircuit(arcs)
m.Add(skip[ROUNDS] == 0)
cover = {}
for x in TL:
    for r in LEAD['p'][:13]:
        cover.setdefault(compose(x, r), []).extend([c[x, 'p'], c[x, 'b'], c[x, 's']])
    cover.setdefault(compose(x, LEAD['p'][13]), []).append(c[x, 'p'])
    cover.setdefault(compose(x, LEAD['b'][13]), []).extend([c[x, 'b'], c[x, 's']])
for r, lits in cover.items():
    m.AddExactlyOne(lits)
m.Add(sum(c[x, 's'] for x in TL) == 2)
bobs = sum(c[x, 'b'] for x in TL)
m.Add(bobs >= 71)          # proved separately: 72 calls is impossible
m.Minimize(bobs)

if hint:
    lh = ROUNDS; used = {}
    for k in hint:
        used[lh] = k; lh = compose(lh, STEP[k])
    for x in TL:
        for k in K:
            m.AddHint(c[x, k], used.get(x) == k)
        m.AddHint(skip[x], x not in used)

class CB(cp_model.CpSolverSolutionCallback):
    def __init__(s): super().__init__(); s.t = time.time()
    def on_solution_callback(s):
        sol = {x: k for x in TL for k in K if s.Value(c[x, k])}
        out, x = [], ROUNDS
        while True:
            out.append(sol[x]); x = compose(x, STEP[sol[x]])
            if x == ROUNDS: break
        cal = ''.join(out)
        rows, end = touch(cal)
        ok = len(cal) == 360 and len(set(rows)) == 5040 and end == ROUNDS
        print(f'{time.time() - s.t:7.1f}s  bobs={cal.count("b")} bound={s.BestObjectiveBound():.0f} true={ok}  {cal}', flush=True)

solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = secs
solver.parameters.num_workers = workers
st = solver.Solve(m, CB())
print('status', solver.StatusName(st), 'objective', solver.ObjectiveValue() if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
      'bound', solver.BestObjectiveBound(), 'wall', round(solver.WallTime(), 1), flush=True)
