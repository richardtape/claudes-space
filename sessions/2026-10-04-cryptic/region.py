"""region.py GRID SLOT,SLOT,... [--minz Z] [--top K]

Enumerate every way to fill the named slots, with all other cells as they are
in GRID (unfilled cells outside the region are ignored). Ranks fills by their
rarest word, so the list starts with fills that contain no obscurities."""
import argparse
from grid import parse, lights
from fill import load_words

ap = argparse.ArgumentParser()
ap.add_argument('grid')
ap.add_argument('slots')
ap.add_argument('--minz', type=float, default=2.7)
ap.add_argument('--top', type=int, default=40)
ap.add_argument('--ban', default='ban.txt')
a = ap.parse_args()

rows = parse(open(a.grid).read())
W = load_words(a.minz)
ban = {w.strip().upper() for w in open(a.ban).read().replace('\n', ',').split(',') if w.strip()}
L = {f'{n}{d}': cells for n, d, cells in lights(rows)}
names = a.slots.split(',')
cand = {}
for s in names:
    pat = [rows[r][c] for r, c in L[s]]
    cand[s] = [w for w in W if w not in ban and len(w) == len(pat)
               and all(p == '.' or p == ch for p, ch in zip(pat, w))]
names.sort(key=lambda s: len(cand[s]))
sols = []


def rec(i, placed):
    if i == len(names):
        sols.append(dict(placed))
        return
    s = names[i]
    for w in cand[s]:
        if w in placed.values():
            continue
        ok = True
        for (r, c), ch in zip(L[s], w):
            for t, tw in placed.items():
                if (r, c) in L[t] and tw[L[t].index((r, c))] != ch:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            placed[s] = w
            rec(i + 1, placed)
            del placed[s]


rec(0, {})
sols.sort(key=lambda d: -min(W[w] for w in d.values()))
order = a.slots.split(',')
print(len(sols), 'fills')
for d in sols[:a.top]:
    print(f'{min(W[w] for w in d.values()):.2f}  ' + '  '.join(f'{s}:{d[s]}' for s in order))
