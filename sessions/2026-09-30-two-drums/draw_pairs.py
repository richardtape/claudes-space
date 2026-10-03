"""Quick look: draw drum pairs for a few base triangles (img/pairs_*.png)."""
import json, math
import numpy as np
from PIL import Image, ImageDraw
from fano import classes, perm_lines, perm_points
from geometry import check, triangle

cls, _, _ = classes()

def draw(ax_list, fname, scale=60, pad=20):
    # ax_list: list of (title, V) rows of [A, B]
    rows = []
    for title, VA, VB in ax_list:
        rows.append((title, VA, VB))
    W, H = 900, 260 * len(rows)
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    for r, (title, VA, VB) in enumerate(rows):
        d.text((10, r * 260 + 5), title, fill="black")
        for c, V in enumerate((VA, VB)):
            pts = np.vstack(V)
            mn, mx = pts.min(0), pts.max(0)
            s = min(400 / (mx - mn).max(), 200 / max((mx - mn)[1], 1e-9), 400 / max((mx - mn)[0], 1e-9))
            s = min(s, 210 / max((mx - mn)[1], 1e-9))
            ox, oy = c * 450 + 20, r * 260 + 25
            for i, T in enumerate(V):
                P = [(ox + (x - mn[0]) * s, oy + (mx[1] - y) * s) for x, y in T]
                d.polygon(P, fill=(200, 220, 240), outline=(40, 40, 40))
                cx, cy = np.mean(P, axis=0)
                d.text((cx - 3, cy - 5), str(i), fill="red")
    im.save(fname)

agree = 0; disagree = 0
for ci, (_, _, t) in enumerate(cls):
    PA = [perm_points(g) for g in t]; PB = [perm_lines(g) for g in t]
    sh = json.load(open("shapes.json"))["classes"][ci]["grid"]
    for i, j, sa, sb in sh:
        if sa == sb: agree += 1
        else: disagree += 1
    rows = []
    for name, (a, b) in {"45-45-90": (45, 45), "45-90-45": (45, 90), "30-60-90": (30, 60), "60-30-90": (60, 30), "60-60-60": (60, 60), "60-90-30": (60, 90)}.items():
        tri = triangle(math.radians(a), math.radians(b))
        sa, VA = check(PA, tri); sb, VB = check(PB, tri)
        if sa == "ok":
            rows.append((f"class {ci}  {name}  A:{sa} B:{sb}", VA, VB))
    if rows:
        draw(rows, f"img/pairs_class{ci}.png")
print("A/B agree on status:", agree, " disagree:", disagree)
