import json
from sandpile import *
def run(line, ok, c):
    if not ok[c]: return 0
    lo = c
    while lo > 0 and ok[lo-1]: lo -= 1
    hi = c
    while hi < len(line)-1 and ok[hi+1]: hi += 1
    return hi - lo + 1
r = 192; out = []
for c in range(192, 385, 2):
    e = identity_c(rect(r, c))
    w = run(e[r//2], e[r//2] == 2, c//2); h = run(e[:, c//2], e[:, c//2] == 2, r//2)
    out.append([c, w, h])
json.dump({"r": r, "rows": out}, open("flip.json", "w"))
print("done", len(out))
