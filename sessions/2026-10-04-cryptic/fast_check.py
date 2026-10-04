"""Check the quick-fire letter claims: fast_check.py [logs/fast_claims.json]"""
import json
import re
import sys

L = lambda s: re.sub('[^a-z]', '', s.lower())
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'logs/fast_claims.json'))
results = {}
for kind in ('anagram', 'hidden', 'reversal', 'length', 'nth', 'count'):
    out = []
    for c in d.get(kind, []):
        if kind == 'anagram':
            ok = sorted(L(c[0])) == sorted(L(c[1]))
        elif kind == 'hidden':
            ok = L(c[0]) in L(c[1]) and L(c[0]) != L(c[1])
        elif kind == 'reversal':
            ok = L(c[0])[::-1] == L(c[1])
        elif kind == 'length':
            ok = len(L(c[0])) == c[1]
            if not ok:
                c = c + [f'actually {len(L(c[0]))}']
        elif kind == 'count':
            n = L(c[0]).count(c[1])
            ok = n == c[2]
            if not ok:
                c = c + [f'actually {n}']
        else:
            ok = L(c[0])[c[1] - 1] == c[2]
            if not ok:
                c = c + [f'actually {L(c[0])[c[1] - 1]}']
        out.append((ok, c))
    results[kind] = out
total = wrong = 0
for kind, out in results.items():
    if not out:
        continue
    bad = [c for ok, c in out if not ok]
    total += len(out)
    wrong += len(bad)
    print(f'{kind:<9} {len(out) - len(bad):>2}/{len(out)} right', *(f'\n   x {b}' for b in bad))
print(f'\n{total - wrong}/{total} right, {wrong} wrong')
