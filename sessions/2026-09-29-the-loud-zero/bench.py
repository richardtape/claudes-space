import time, numpy as np
from sandpile import *
for n in [128, 256, 512]:
    m = square(n); t = time.time(); e = identity_fast(m); dt = time.time() - t
    ref = np.load(f"img/identity_square_{n}.npy")
    print(n, f"{dt:.1f}s", "matches slow version:", (e == ref).all())
# also check the shapes with irregular masks agree
for f in [disc, triangle, annulus]:
    m = f(96); print(f.__name__, (identity(m) == identity_fast(m)).all())
