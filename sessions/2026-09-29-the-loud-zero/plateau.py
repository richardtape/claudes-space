import time, json, numpy as np
from sandpile import *
res = {}
t0 = time.time()
for n in range(8, 321):
    e = identity_c(square(n))
    mid = e[n // 2]
    c = n // 2
    if mid[c] != 2:
        res[n] = 0; continue
    lo = c
    while lo > 0 and mid[lo - 1] == 2: lo -= 1
    hi = c
    while hi < n - 1 and mid[hi + 1] == 2: hi += 1
    res[n] = hi - lo + 1
json.dump(res, open("plateau.json", "w"))
print(f"done in {time.time()-t0:.0f}s")
for n in [16, 32, 64, 100, 128, 200, 256, 300, 320]:
    print(n, res[n], f"{res[n]/n:.4f}")
