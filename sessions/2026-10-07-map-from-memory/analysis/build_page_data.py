"""Gather everything the page draws into page/data.js.

Maps are plate carree: x = longitude, y = -latitude, in degrees, the projection in
which a map is nothing but its coordinates. Antarctica gets a south-polar inset
(azimuthal equidistant: r = 90 + latitude, angle = longitude).
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import SESSION, ne_rings  # noqa: E402

OUT = SESSION / "page" / "data.js"


def dp(points, tol):
    """Douglas-Peucker on an (n, 2) array."""
    n = len(points)
    if n < 4:
        return points
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p, q = points[a], points[b]
        seg = q - p
        L = np.hypot(*seg)
        mid = points[a + 1:b]
        d = np.hypot(*(mid - p).T) if L == 0 else np.abs(seg[0] * (mid[:, 1] - p[1]) - seg[1] * (mid[:, 0] - p[0])) / L
        i = int(np.argmax(d))
        if d[i] > tol:
            k = a + 1 + i
            keep[k] = True
            stack += [(a, k), (k, b)]
    return points[keep]


def ring_area(pts):
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def fmt(pts, nd=2):
    return "M" + "L".join(f"{a:.{nd}f} {b:.{nd}f}".replace(".00 ", " ").replace("-0 ", "0 ") for a, b in pts) + "Z"


def plate(rings, tol, min_area):
    out = []
    for ring in rings:
        pts = np.array([[p[0], -p[1]] for p in ring], float)
        if ring_area(pts) < min_area:
            continue
        pts = dp(pts, tol)
        if len(pts) >= 3:
            out.append(fmt(pts))
    return "".join(out)


def polar(lon, lat):
    r = 90.0 + np.asarray(lat, float)
    t = np.radians(np.asarray(lon, float))
    return r * np.sin(t), -r * np.cos(t)  # Greenwich up, 90 E to the right, Ross Sea at the bottom


def main():
    spec = importlib.util.spec_from_file_location("drawn", SESSION / "drawing" / "drawn_world.frozen.py")
    drawn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drawn)

    land50 = ne_rings("ne_50m_land")
    land = [o for o, _, _ in land50 if max(p[1] for p in o) > -60]
    holes = [h for _, hs, _ in land50 for h in hs]
    ant = [o for o, _, _ in land50 if max(p[1] for p in o) <= -60]

    verts = json.loads((SESSION / "analysis" / "drawing_vertices.json").read_text())
    vkm = {(v["ring"], v["lon"], v["lat"]): v["coast_km"] for v in verts}
    drawn_rings = []
    for name, ring in list(drawn.LAND.items()) + list(drawn.LAKES.items()):
        if name == "Antarctica":
            continue
        pts = [[p[0], -p[1], p[2], vkm.get((name, p[0], p[1]))] for p in ring]
        drawn_rings.append({"name": name, "pts": pts})

    # South-polar inset: true Antarctica (fill only) and my ring (pole closure removed).
    ant_paths = []
    for ring in ant:
        x, y = polar([p[0] for p in ring], [p[1] for p in ring])
        pts = dp(np.stack([x, y], 1), 0.05)
        ant_paths.append(fmt(pts))
    mine = [p for p in drawn.ANTARCTICA if p[1] > -89.9]
    x, y = polar([p[0] for p in mine], [p[1] for p in mine])
    ant_mine = [[round(float(a), 2), round(float(b), 2), p[2], vkm.get(("Antarctica", p[0], p[1]))]
                for a, b, p in zip(x, y, mine)]

    cities = json.loads((SESSION / "analysis" / "city_results.json").read_text())
    rev = {r["id"]: r for r in json.loads((SESSION / "analysis" / "reverse_results.json").read_text())}
    crow = []
    for r in cities:
        v = rev[r["id"]]
        crow.append({
            "id": r["id"], "n": r["name"], "a": r["admin1"], "c": r["country"], "cc": r["cc"],
            "t": r["tier"], "p": r["pop"], "lat": round(r["lat"], 4), "lon": round(r["lon"], 4),
            "glat": r["g_lat"], "glon": r["g_lon"], "e": r["err_km"], "r50": r["r50"], "r90": r["r90"],
            "kn": r["known"], "e2": r["retest"]["err_km"] if "retest" in r else None,
            "rv": v["place"], "rvc": v["country"], "rvp": v["p_correct"], "rvg": v["grade"], "rvk": v["near_km"],
        })

    data = {
        "land": plate(land, 0.035, 0.002),
        "holes": plate(holes, 0.035, 0.002),
        "ant": "".join(ant_paths),
        "antMine": ant_mine,
        "drawn": drawn_rings,
        "cities": crow,
        "drawing": json.loads((SESSION / "analysis" / "drawing_scores.json").read_text()),
        "forward": json.loads((SESSION / "analysis" / "city_scores.json").read_text()),
        "reverse": json.loads((SESSION / "analysis" / "reverse_scores.json").read_text()),
    }
    data["drawing"]["named_places"].pop("rows", None)
    p = json.loads((SESSION / "analysis" / "precise_scores.json").read_text())
    data["precise"] = {"summary": p["summary"],
                       "rows": [{"id": r["id"], "n": r["name"], "e4": round(r["err4"], 4), "e2": r["err2"],
                                 "kn": r["known"], "lat": r["lat"], "lon": r["lon"], "r50": r["r50"]}
                                for r in p["rows"]]}
    bpath = SESSION / "analysis" / "between_results.json"
    if bpath.exists():
        data["between"] = {"scores": json.loads((SESSION / "analysis" / "between_scores.json").read_text()),
                           "rows": [{k: r[k] for k in ("id", "kind", "lat", "lon", "place", "country", "est_km",
                                                       "p_nearest", "rank", "named", "named_km", "nearest",
                                                       "nearest_km", "excess_km", "grade")}
                                    for r in json.loads(bpath.read_text())]}
    OUT.parent.mkdir(exist_ok=True)
    txt = "window.MAPDATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    OUT.write_text(txt, encoding="utf-8")
    print(f"wrote {OUT.name}: {len(txt) / 1024:.0f} KB (land {len(data['land']) / 1024:.0f} KB, "
          f"drawn {len(json.dumps(drawn_rings)) / 1024:.0f} KB, cities {len(json.dumps(crow)) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
