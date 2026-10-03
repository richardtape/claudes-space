import time, numpy as np
from sandpile import *
for n in [128, 256, 512]:
    ref = np.load(f"img/identity_square_{n}.npy"); m = square(n)
    for fast in (False, True):
        t = time.time(); e = identity_c(m, fast); dt = time.time() - t
        print(n, "C+linsolve" if fast else "C only   ", f"{dt:6.2f}s", "match:", (e == ref).all())
for f in [disc, triangle, annulus]:
    m = f(96); print(f.__name__, (identity(m) == identity_c(m)).all())
