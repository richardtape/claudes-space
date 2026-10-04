"""Fill a grid from words.txt by backtracking search (MRV + forward checking).

Usage: fill.py GRID [--seed N] [--n K] [--ban word,word] [--minz Z]
Fixed letters in the grid are kept. Prints K distinct fills, best words first."""
import argparse
import random
import sys
from grid import parse, lights


def load_words(minz):
    out = {}
    for line in open('words.txt'):
        w, z = line.split('\t')
        z = float(z)
        if z >= minz:
            out[w.upper()] = z
    return out


def inflection_penalty(w):
    """Prefer base forms: a grid full of -S and -ED endings clues badly."""
    if w.endswith('S') and not w.endswith('SS'):
        return 0.9
    if w.endswith('ED') or w.endswith('ING'):
        return 0.7
    return 0.0


def solve(rows, words, rng, ban=(), node_limit=2000000, noise=1.2):
    L = lights(rows)
    slots = [(f'{n}{d}', cells) for n, d, cells in L]
    owner = {}
    for i, (_, cells) in enumerate(slots):
        for k, rc in enumerate(cells):
            owner.setdefault(rc, []).append((i, k))
    bylen = {}
    for w, z in words.items():
        if w.lower() not in ban:
            bylen.setdefault(len(w), []).append(w)
    # domains, ordered by frequency with a little noise
    domains = []
    for name, cells in slots:
        pat = [rows[r][c] for r, c in cells]
        fixed = ''.join(p if p != '.' else '?' for p in pat)
        if '?' not in fixed:
            domains.append([fixed])
            continue
        cand = [w for w in bylen.get(len(cells), [])
                if all(p == '.' or p == ch for p, ch in zip(pat, w))]
        cand.sort(key=lambda w: -(words[w] + rng.random() * noise - inflection_penalty(w)))
        domains.append(cand)
    # crossings: for slot i position k -> (slot j, position m)
    cross = [[] for _ in slots]
    for rc, lst in owner.items():
        if len(lst) == 2:
            (i, k), (j, m) = lst
            cross[i].append((k, j, m))
            cross[j].append((m, i, k))
    assign = [None] * len(slots)
    nodes = [0]

    def rec(doms):
        nodes[0] += 1
        if nodes[0] > node_limit:
            return None
        free = [i for i in range(len(slots)) if assign[i] is None]
        if not free:
            return list(assign)
        i = min(free, key=lambda i: (len(doms[i]), rng.random()))
        used = {a for a in assign if a}
        for w in doms[i][:150]:
            if w in used:
                continue
            new = list(doms)
            ok = True
            for k, j, m in cross[i]:
                if assign[j] is None:
                    nd = [x for x in new[j] if x[m] == w[k]]
                    if not nd:
                        ok = False
                        break
                    new[j] = nd
            if not ok:
                continue
            assign[i] = w
            new[i] = [w]
            res = rec(new)
            if res:
                return res
            assign[i] = None
        return None

    res = rec(domains)
    return slots, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('grid')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--n', type=int, default=3)
    ap.add_argument('--ban', default='')
    ap.add_argument('--minz', type=float, default=3.0)
    ap.add_argument('--noise', type=float, default=1.2)
    a = ap.parse_args()
    rows = parse(open(a.grid).read())
    words = load_words(a.minz)
    ban = {b.strip().lower() for b in a.ban.split(',') if b.strip()}
    got = 0
    for s in range(a.seed, a.seed + 200):
        rng = random.Random(s)
        slots, res = solve(rows, words, rng, ban, noise=a.noise)
        if not res:
            continue
        got += 1
        score = sum(words.get(w, 0) for w in res) / len(res)
        print(f'--- seed {s}  mean zipf {score:.2f}')
        print('  '.join(f'{name}:{w}' for (name, _), w in zip(slots, res)))
        if got >= a.n:
            break
    if not got:
        print('no fill found', file=sys.stderr)


if __name__ == '__main__':
    main()
