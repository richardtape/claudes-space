"""Which triangles (60 degrees at V1, x at V2, 120 - x at V0) make 21_1 flat?"""
import math
from geometry import check, triangle
from pair21 import PA, PB
oks = []
for x10 in range(5, 600, 5):
    x = x10 / 10
    tri = triangle(math.radians(120 - x), math.radians(60))
    sa, _ = check(PA, tri); sb, _ = check(PB, tri)
    if sa == "ok" and sb == "ok":
        oks.append(x)
    elif x10 % 50 == 0:
        print(f"V2 = {x:5.1f}: A {sa}, B {sb}")
print("flat for V2 in", (min(oks), max(oks)) if oks else None, f"({len(oks)} of 119 tried)")
