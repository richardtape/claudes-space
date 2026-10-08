"""Small geographic helpers shared by the scoring scripts (stdlib + numpy only)."""
import json
import math
from pathlib import Path

import numpy as np

R_KM = 6371.0088
SESSION = Path(__file__).resolve().parent.parent
RAW = SESSION / "raw"


def unit(lon, lat):
    lon, lat = np.radians(lon), np.radians(lat)
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def gc_km(lon1, lat1, lon2, lat2):
    """Great-circle distance (haversine), vectorised."""
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * R_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def chord_to_km(chord):
    return 2 * R_KM * np.arcsin(np.clip(chord / 2, 0, 1))


def wrap180(lon):
    return (np.asarray(lon) + 180.0) % 360.0 - 180.0


def ne_rings(name, holes=True):
    """Natural Earth polygons as a list of (outer, [holes]) rings of (lon, lat)."""
    d = json.loads((RAW / "naturalearth" / f"{name}.geojson").read_text())
    out = []
    for ft in d["features"]:
        g = ft["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for p in polys:
            out.append((p[0], p[1:] if holes else [], ft["properties"]))
    return out


def densify(ring, step_deg=0.05, closed=True, skip_frame=True):
    """Points along a ring at most step_deg apart. Frame edges (the pole line and the
    +-180 seam that close Antarctica-like polygons) are skipped: they aren't coastline."""
    pts = []
    n = len(ring)
    last = n if closed else n - 1
    for i in range(last):
        a, b = ring[i], ring[(i + 1) % n]
        if skip_frame and _frame_edge(a, b):
            continue
        dl = b[0] - a[0]
        k = max(1, int(math.ceil(max(abs(dl), abs(b[1] - a[1])) / step_deg)))
        for j in range(k):
            t = j / k
            pts.append((a[0] + dl * t, a[1] + (b[1] - a[1]) * t))
    return pts


def _frame_edge(a, b):
    if a[1] < -89.9 and b[1] < -89.9:
        return True
    if abs(abs(a[0]) - 180) < 1e-6 and abs(abs(b[0]) - 180) < 1e-6:
        return True
    return False


# Equal Earth projection (Savric, Patterson & Jenny 2018), unit sphere.
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def equal_earth(lon, lat):
    lam, phi = np.radians(lon), np.radians(lat)
    th = np.arcsin(M * np.sin(phi))
    t2 = th * th
    t6 = t2 * t2 * t2
    x = lam * np.cos(th) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y
