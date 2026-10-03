import json, numpy as np
from sandpile import *
res = {}
for n in range(8, 321):
    e = identity_c(square(n)); c = n // 2
    row = e[c - 1] if n % 2 else e[c]          # odd: step just off the seam row
    ok = (row == 2); 
    if n % 2: ok[c] = ok[c] or row[c] == 1      # the vertical seam cell
    if not ok[c]: res[n] = 0; continue
    lo = c
    while lo > 0 and ok[lo - 1]: lo -= 1
    hi = c
    while hi < n - 1 and ok[hi + 1]: hi += 1
    res[n] = hi - lo + 1
json.dump(res, open("plateau2.json", "w"))
