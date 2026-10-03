"""Render thumb.png: both GWW drums in one mode, copper up / verdigris down, dark ground."""
import json, math, sys
import numpy as np
from PIL import Image
from fem import base_mesh

d = json.load(open("page_data.json"))["gww"]
v = json.load(open("verify_data.json"))
N, m, T = d["n"], d["m"], 7
bary, tris = base_mesh(N)
nl = len(bary)
def decode(b64, scales):
    import base64
    q = np.frombuffer(base64.b64decode(b64), dtype="<i2").astype(float).reshape(m, T, nl)
    return q * (np.array(scales)[:, None, None] / 32767)
A, B = decode(d["modes"], d["scales"]), decode(v["gwwB"], v["gwwBscales"])
tri = np.array(d["tri"])
local = bary @ tri
SIZE, SS = 600, 2                      # render at 2x and downsample
W = SIZE * SS
hall, skin, copper, verd, rim = (np.array(c, float) for c in ([20, 25, 34], [35, 43, 56], [229, 140, 83], [79, 186, 171], [195, 202, 214]))
img = np.tile(hall, (W, W, 1))

def place_xy(M):
    M = np.array(M).reshape(2, 3)
    return local @ M[:, :2].T + M[:, 2]

def draw(modes, k, places, ox, oy, scale, sgn):
    vals = modes[k] * sgn
    vmax = np.abs(vals).max()
    for p in range(T):
        P = place_xy(places[p])
        X, Y = ox + P[:, 0] * scale, oy - P[:, 1] * scale
        for a, b, c in tris:
            xs, ys = X[[a, b, c]], Y[[a, b, c]]
            x0, x1 = int(np.floor(xs.min())), int(np.ceil(xs.max()))
            y0, y1 = int(np.floor(ys.min())), int(np.ceil(ys.max()))
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            det = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (ys[1] - ys[0]) * (xs[2] - xs[0])
            l1 = ((gx - xs[0]) * (ys[2] - ys[0]) - (gy - ys[0]) * (xs[2] - xs[0])) / det
            l2 = ((xs[1] - xs[0]) * (gy - ys[0]) - (ys[1] - ys[0]) * (gx - xs[0])) / det
            l0 = 1 - l1 - l2
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            u = (l0 * vals[p, a] + l1 * vals[p, b] + l2 * vals[p, c]) / vmax
            t = np.clip(np.abs(u), 0, 1) ** 0.62
            col = np.where((u >= 0)[..., None], copper, verd)
            rgb = skin + (col - skin) * t[..., None]
            yy, xx = np.nonzero(inside)
            img[y0 + yy, x0 + xx] = rgb[yy, xx]

def outline(places, ox, oy, scale, key):
    from PIL import ImageDraw
    return [(ox + x * scale, oy - y * scale) for x, y in d[key]["outline"]]

k = int(sys.argv[1]) if len(sys.argv) > 1 else 6
scale = W / 6.2
# A in the upper left, B in the lower right
bA = np.array(d["A"]["outline"]); bB = np.array(d["B"]["outline"])
oxA, oyA = W * 0.05 - bA[:, 0].min() * scale, W * 0.06 + bA[:, 1].max() * scale
oxB, oyB = W * 0.95 - bB[:, 0].max() * scale, W * 0.94 + bB[:, 1].min() * scale
draw(A, k, d["A"]["place"], oxA, oyA, scale, 1)
draw(B, k, d["B"]["place"], oxB, oyB, scale, 1)
im = Image.fromarray(img.astype(np.uint8))
from PIL import ImageDraw
dr = ImageDraw.Draw(im)
for key, ox, oy in (("A", oxA, oyA), ("B", oxB, oyB)):
    pts = [(ox + x * scale, oy - y * scale) for x, y in d[key]["outline"]]
    dr.line(pts + [pts[0]], fill=tuple(int(c) for c in rim), width=3 * SS, joint="curve")
im = im.resize((SIZE, SIZE), Image.LANCZOS)
out = sys.argv[2] if len(sys.argv) > 2 else "thumb.png"
im.save(out, optimize=True)
print(out, im.size)
