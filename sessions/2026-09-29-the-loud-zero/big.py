import time, numpy as np
from sandpile import *
for n in [768, 1024]:
    t = time.time(); m = square(n); e = identity_c(m)
    np.save(f"img/identity_square_{n}.npy", e)
    c = n // 2; row = e[c]; lo = c
    while row[lo-1] == 2: lo -= 1
    hi = c
    while row[hi+1] == 2: hi += 1
    print(n, f"{time.time()-t:.0f}s  plateau={hi-lo+1}  5n/12={5*n/12:.2f}", flush=True)
