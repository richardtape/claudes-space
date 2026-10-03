"""For each of the 3 Sunada classes from GL(3,2), which base-triangle shapes give two
flat, non-congruent drums?  Scans ordered angle triples on a grid of step 180/STEPS
degrees.  Writes shapes.json for the page.

Status per grid point: 'ok' (both flat, simple polygons, not congruent), 'pinch'
(both flat and not congruent, but a rim touches itself at a point), 'congruent' (both flat but
the same shape), 'one' (exactly one drum flat), 'slit', 'overlap'.
"""
import json, math, sys
from fano import classes, perm_lines, perm_points
from geometry import boundary_loop, check, congruent, triangle

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 90
cls, _, _ = classes()
out = []
for ci, (_, _, t) in enumerate(cls):
    PA = [perm_points(g) for g in t]; PB = [perm_lines(g) for g in t]
    grid, tally = [], {}
    for i in range(1, STEPS):
        for j in range(1, STEPS - i):
            tri = triangle(math.pi * i / STEPS, math.pi * j / STEPS)
            sa, VA = check(PA, tri); sb, VB = check(PB, tri)
            if sa == "ok" and sb == "ok":
                (pa, pin_a), (pb, pin_b) = boundary_loop(PA, VA), boundary_loop(PB, VB)
                if congruent(pa, pb):
                    st = "congruent"
                elif pin_a or pin_b:
                    st = "pinch"
                else:
                    st = "ok"
            elif sa == "ok" or sb == "ok":
                st = "one"
            elif "overlap" in (sa, sb):
                st = "overlap"
            else:
                st = "slit"
            tally[st] = tally.get(st, 0) + 1
            grid.append([i, j, st])
    print(f"class {ci}: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())) + f"  (of {len(grid)})")
    out.append({"cls": ci, "grid": grid, "tally": tally})
json.dump({"steps": STEPS, "classes": out}, open("shapes.json", "w"))
