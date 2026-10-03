from sandpile import *
from PIL import Image
def hexagon(n):
    y, x = np.mgrid[0:n, 0:n] + 0.5 - n / 2
    a = n / 2
    return (np.abs(y) <= a * 0.866) & (np.abs(y) * 0.577 + np.abs(x) <= a)
def heart(n):
    y, x = np.mgrid[0:n, 0:n] + 0.5
    X = (x - n/2) / (n * 0.42); Y = -(y - n * 0.47) / (n * 0.42)
    return (X**2 + Y**2 - 1)**3 - X**2 * Y**3 <= 0
def rect_(n): 
    m = np.zeros((n, n), bool); m[n//4:3*n//4, :] = True; return m
shapes = {"disc": disc, "diamond": diamond, "triangle": triangle, "annulus": annulus,
          "hexagon": hexagon, "heart": heart, "rect2x1": rect_}
tiles = []
for name, f in shapes.items():
    m = f(300); e = identity_c(m)
    im = render(e, m, scale=1); im.save(f"img/identity_{name}.png"); tiles.append(im)
    print(name, "done", flush=True)
W = 300 * 4 + 30; H = 300 * 2 + 10
out = Image.new("RGB", (W, H), (250, 247, 240))
for i, im in enumerate(tiles):
    out.paste(im, ((i % 4) * 310, (i // 4) * 310))
out.save("img/shapes.png")
