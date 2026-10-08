"""Points between the gazetteer's entries: 200 points 15-35 km from sampled towns in a
random direction, and 100 uniformly random points on land (Antarctica excluded).
Truth for each = the nearest GeoNames place of 15,000+ (same feature codes as sample.py).
Writes cities/between_truth.json and cities/batches/between_K.txt (coordinates only)."""
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "analysis"))
sys.path.insert(0, str(HERE))
from geo import RAW, chord_to_km, ne_rings, unit  # noqa: E402
from sample import KEEP_CODES  # noqa: E402

rng = random.Random(20261009)
places = []
with open(RAW / "geonames" / "cities15000.txt", encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("\t")
        if p[7] in KEEP_CODES:
            places.append((float(p[5]), float(p[4]), int(p[0]), p[1], p[8], int(p[14] or 0)))
P = np.array([(a, b) for a, b, *_ in places])
tree = cKDTree(unit(P[:, 0], P[:, 1]))

# land mask on a 0.1 degree grid, to keep random points on land
W, H = 3600, 1800
img = Image.new("L", (W, H), 0)
dr = ImageDraw.Draw(img)
for outer, holes, _ in ne_rings("ne_50m_land"):
    dr.polygon([((lo + 180) * 10, (90 - la) * 10) for lo, la in outer], fill=1)
    for h in holes:
        dr.polygon([((lo + 180) * 10, (90 - la) * 10) for lo, la in h], fill=0)
land = np.array(img, bool)

def on_land(lon, lat):
    return land[min(H - 1, int((90 - lat) * 10)), min(W - 1, int((lon + 180) * 10))]

def destination(lon, lat, bearing, km):
    R = 6371.0088
    d = km / R
    la1, lo1, b = map(math.radians, (lat, lon, bearing))
    la2 = math.asin(math.sin(la1) * math.cos(d) + math.cos(la1) * math.sin(d) * math.cos(b))
    lo2 = lo1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(la1), math.cos(d) - math.sin(la1) * math.sin(la2))
    return (math.degrees(lo2) + 540) % 360 - 180, math.degrees(la2)

sample = [r for r in json.loads((HERE / "sample_truth.json").read_text()) if r["tier"] != "T1"]
pts = []
for r in rng.sample(sample, len(sample)):
    if len(pts) >= 200:
        break
    for _ in range(20):
        lon, lat = destination(r["lon"], r["lat"], rng.uniform(0, 360), rng.uniform(15, 35))
        if on_land(lon, lat):
            pts.append({"kind": "offset", "from_id": r["id"], "lon": lon, "lat": lat})
            break
while len(pts) < 300:
    lat = math.degrees(math.asin(rng.uniform(math.sin(math.radians(-56)), 1)))
    lon = rng.uniform(-180, 180)
    if on_land(lon, lat):
        pts.append({"kind": "random", "lon": lon, "lat": lat})

rng.shuffle(pts)
for i, q in enumerate(pts, 1):
    q["id"] = i
    q["lat"], q["lon"] = round(q["lat"], 2), round(q["lon"], 2)
    d, j = tree.query(unit(q["lon"], q["lat"]), k=10)
    q["nearest"] = [{"gid": places[k][2], "name": places[k][3], "cc": places[k][4], "pop": places[k][5],
                     "lon": places[k][0], "lat": places[k][1], "km": round(float(chord_to_km(dd)), 2)}
                    for dd, k in zip(d, j)]
(HERE / "between_truth.json").write_text(json.dumps(pts, ensure_ascii=False, indent=0))
for b in range(4):
    part = pts[b::4]
    (HERE / "batches" / f"between_{b + 1}.txt").write_text(
        "\n".join(f"{q['id']}. {q['lat']:.2f}, {q['lon']:.2f}" for q in part) + "\n", encoding="utf-8")
    print(f"between_{b + 1}: {len(part)} points")
print("kinds:", {k: sum(q['kind'] == k for q in pts) for k in ('offset', 'random')})
print("median km to nearest town: offset", np.median([q['nearest'][0]['km'] for q in pts if q['kind'] == 'offset']),
      "random", np.median([q['nearest'][0]['km'] for q in pts if q['kind'] == 'random']))
