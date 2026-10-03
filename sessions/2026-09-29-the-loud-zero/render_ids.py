import time, numpy as np
from sandpile import *
from PIL import Image
for n in [32, 64, 128, 256, 512]:
    t = time.time(); m = square(n); e = identity(m)
    render(e, m, scale=max(1, 512 // n), path=f"img/identity_square_{n}.png")
    np.save(f"img/identity_square_{n}.npy", e)
    print(n, f"{time.time()-t:.1f}s", "height counts:", np.bincount(e.ravel(), minlength=4))
