"""Score the frozen coastline drawing against Natural Earth 1:50m land.

Land overlap is measured on an equal-area grid (Lambert cylindrical: x = lon,
y = sin lat), so every pixel is the same ~79 km^2 of the Earth's surface.
Line accuracy is measured with nearest-point distances on the sphere.

Writes analysis/drawing_scores.json and analysis/drawing_vertices.json.
"""
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import RAW, R_KM, SESSION, chord_to_km, densify, gc_km, ne_rings, unit, wrap180  # noqa: E402

W, H = 3600, 1800
PIX_KM2 = 4 * np.pi * R_KM ** 2 / (W * H)

spec = importlib.util.spec_from_file_location("drawn", SESSION / "drawing" / "drawn_world.frozen.py")
drawn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drawn)

RING_CONTINENT = {
    "Africa": "Africa", "Madagascar": "Africa", "Eurasia": "Eurasia", "North America": "North America",
    "South America": "South America", "Australia": "Oceania", "Antarctica": "Antarctica",
}
ISLAND_CONTINENT = {
    "Greenland": "North America", "Iceland": "Eurasia", "Great Britain": "Eurasia", "Ireland": "Eurasia",
    "Sicily": "Eurasia", "Sardinia": "Eurasia", "Corsica": "Eurasia", "Crete": "Eurasia", "Cyprus": "Eurasia",
    "Novaya Zemlya": "Eurasia", "Spitsbergen": "Eurasia", "Nordaustlandet": "Eurasia",
    "Severnaya Zemlya": "Eurasia", "New Siberian Islands": "Eurasia", "Sri Lanka": "Eurasia",
    "Hainan": "Eurasia", "Taiwan": "Eurasia", "Honshu": "Eurasia", "Hokkaido": "Eurasia", "Kyushu": "Eurasia",
    "Shikoku": "Eurasia", "Sakhalin": "Eurasia", "Borneo": "Eurasia", "Sumatra": "Eurasia", "Java": "Eurasia",
    "Sulawesi": "Eurasia", "Luzon": "Eurasia", "Mindanao": "Eurasia", "Palawan": "Eurasia", "Samar": "Eurasia",
    "Panay": "Eurasia", "Negros": "Eurasia", "Leyte": "Eurasia", "Mindoro": "Eurasia", "Timor": "Eurasia",
    "Seram": "Eurasia", "Flores": "Eurasia", "Sumbawa": "Eurasia", "Halmahera": "Eurasia",
    "New Guinea": "Oceania", "New Britain": "Oceania", "Tasmania": "Oceania", "North Island": "Oceania",
    "South Island": "Oceania", "New Caledonia": "Oceania", "Viti Levu": "Oceania",
    "Hawaii (Big Island)": "Oceania", "Falklands": "South America", "Tierra del Fuego": "South America",
    "Chiloe": "South America",
}
NE_CONTINENT = {
    "Africa": "Africa", "Europe": "Eurasia", "Asia": "Eurasia", "North America": "North America",
    "South America": "South America", "Oceania": "Oceania", "Antarctica": "Antarctica",
}
CONTINENTS = ["Africa", "Eurasia", "North America", "South America", "Oceania", "Antarctica"]


def continent_of_ring(name):
    return RING_CONTINENT.get(name) or ISLAND_CONTINENT.get(name) or "North America"


def to_px(ring):
    lon = np.array([p[0] for p in ring], float)
    lat = np.array([p[1] for p in ring], float)
    x = (lon + 180.0) / 360.0 * W
    y = (1 - np.sin(np.radians(lat))) / 2 * H
    return x, y


def fill(img, ring, value):
    x, y = to_px(ring)
    draw = ImageDraw.Draw(img)
    for shift in (0, -W, W):
        xs = x + shift
        if xs.max() < 0 or xs.min() > W:
            continue
        draw.polygon(list(zip(xs.tolist(), y.tolist())), fill=value)


def raster_truth():
    img = Image.new("L", (W, H), 0)
    holes = []
    for outer, hs, _ in ne_rings("ne_50m_land"):
        fill(img, outer, 1)
        holes += hs
    for h in holes:
        fill(img, h, 0)
    return np.array(img, bool)


def raster_drawn():
    img = Image.new("L", (W, H), 0)
    for ring in drawn.LAND.values():
        fill(img, ring, 1)
    for ring in drawn.LAKES.values():
        fill(img, ring, 0)
    return np.array(img, bool)


def raster_drawn_labels():
    img = Image.new("L", (W, H), 0)
    for name, ring in drawn.LAND.items():
        fill(img, ring, 1 + CONTINENTS.index(continent_of_ring(name)))
    for ring in drawn.LAKES.values():
        fill(img, ring, 0)
    return np.array(img, np.uint8)


def raster_continents(truth):
    """Label every true-land pixel with its continent (from NE countries), then let
    every other pixel take the label of the nearest labelled land pixel."""
    img = Image.new("L", (W, H), 0)
    for outer, _, props in ne_rings("ne_50m_admin_0_countries", holes=False):
        c = NE_CONTINENT.get(props.get("CONTINENT"))
        if c:
            fill(img, outer, 1 + CONTINENTS.index(c))
    lab = np.array(img, np.uint8)
    lab[~truth] = 0
    _, (iy, ix) = distance_transform_edt(lab == 0, return_indices=True)
    return lab[iy, ix]


def coast_points(rings):
    pts = []
    for r in rings:
        pts += densify(r, 0.05)
    a = np.array(pts)
    return a[:, 0], a[:, 1]


def main():
    truth = raster_truth()
    mine = raster_drawn()
    labels = raster_continents(truth)

    def stats(mask):
        t, d = truth & mask, mine & mask
        inter = (t & d).sum()
        union = (t | d).sum()
        return {
            "true_km2": float(t.sum() * PIX_KM2), "drawn_km2": float(d.sum() * PIX_KM2),
            "overlap_km2": float(inter * PIX_KM2),
            "iou": float(inter / union) if union else None,
            "recall": float(inter / t.sum()) if t.sum() else None,
            "precision": float(inter / d.sum()) if d.sum() else None,
        }

    everything = np.ones_like(truth)
    out = {"pixel_km2": PIX_KM2, "world": stats(everything)}
    out["world_without_antarctica"] = stats(labels != 1 + CONTINENTS.index("Antarctica"))
    out["by_continent"] = {c: stats(labels == 1 + i) for i, c in enumerate(CONTINENTS)}

    # Distances along the line.
    true_rings = [o for o, hs, _ in ne_rings("ne_50m_land")] + [h for _, hs, _ in ne_rings("ne_50m_land") for h in hs]
    tlon, tlat = coast_points(true_rings)
    ttree = cKDTree(unit(tlon, tlat))

    drawn_rings = list(drawn.LAND.values()) + list(drawn.LAKES.values())
    dpts = []
    for r in drawn_rings:
        dpts += densify([(p[0], p[1]) for p in r], 0.05)
    dlon, dlat = np.array(dpts).T
    dlon = wrap180(dlon)
    dtree = cKDTree(unit(dlon, dlat))

    verts = []
    for name, ring in list(drawn.LAND.items()) + [(k, v) for k, v in drawn.LAKES.items()]:
        for lon, lat, label in ring:
            if lat < -89.9:
                continue
            verts.append({"ring": name, "lon": lon, "lat": lat, "label": label})
    vlon = wrap180(np.array([v["lon"] for v in verts]))
    vlat = np.array([v["lat"] for v in verts])
    dist, idx = ttree.query(unit(vlon, vlat))
    vkm = chord_to_km(dist)
    for v, d, i in zip(verts, vkm, idx):
        v["coast_km"] = round(float(d), 1)
        v["nearest_coast"] = [round(float(tlon[i]), 3), round(float(tlat[i]), 3)]

    # Missed coast: how much of the true coastline lies far from anything I drew.
    tdist, _ = dtree.query(unit(tlon, tlat))
    tkm = chord_to_km(tdist)
    ddist, _ = ttree.query(unit(dlon, dlat))
    dkm = chord_to_km(ddist)

    def q(a):
        return {p: round(float(np.percentile(a, p)), 1) for p in (10, 25, 50, 75, 90, 99)}

    out["vertex_to_true_coast_km"] = q(vkm)
    out["vertex_count"] = len(verts)
    out["true_coast_to_drawn_km"] = q(tkm)
    out["drawn_line_to_true_coast_km"] = q(dkm)
    for thr in (25, 50, 100, 250):
        out[f"true_coast_within_{thr}km_of_drawn"] = float((tkm <= thr).mean())
        out[f"drawn_line_within_{thr}km_of_true"] = float((dkm <= thr).mean())

    by_ring = defaultdict(list)
    for v in verts:
        by_ring[v["ring"]].append(v["coast_km"])
    out["median_vertex_km_by_ring"] = {k: round(float(np.median(v)), 1) for k, v in by_ring.items()}

    # Named vertices that are towns: compare with GeoNames.
    out["named_places"] = match_named(verts)

    (SESSION / "analysis" / "drawing_scores.json").write_text(json.dumps(out, indent=1))
    (SESSION / "analysis" / "drawing_vertices.json").write_text(json.dumps(verts, ensure_ascii=False))

    # Raster of agreement for a quick picture: 0 sea, 1 drawn only, 2 true only, 3 both.
    agree = mine.astype(np.uint8) + 2 * truth.astype(np.uint8)
    np.save(SESSION / "analysis" / "agreement_raster.npy", agree)
    print(json.dumps({k: v for k, v in out.items() if k not in ("named_places", "median_vertex_km_by_ring")}, indent=1))
    print("named:", {k: v for k, v in out["named_places"].items() if k != "rows"})


def match_named(verts):
    """Match vertex labels to GeoNames places with the same primary name (exact,
    case-insensitive, over name and ascii name; alternate names gave false matches such
    as Skagen -> Schagen). Where a name is shared, take the namesake nearest my point,
    which flatters me slightly; it's what I meant in nearly every case. Matches more
    than 300 km away are treated as a different place of the same name."""
    names = defaultdict(list)
    with open(RAW / "geonames" / "cities15000.txt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            lat, lon = float(p[4]), float(p[5])
            keys = {p[1].lower(), p[2].lower()}
            for k in keys:
                names[k].append((lon, lat, p[1], p[8], int(p[14] or 0)))
    rows = []
    for v in verts:
        lab = v["label"]
        if not lab:
            continue
        cands = names.get(lab.lower())
        if not cands:
            continue
        lon = wrap180(v["lon"])
        d = [gc_km(lon, v["lat"], c[0], c[1]) for c in cands]
        j = int(np.argmin(d))
        if d[j] > 300:
            continue  # a namesake on another continent: not the place I meant
        c = cands[j]
        rows.append({"label": lab, "ring": v["ring"], "km": round(float(d[j]), 1), "geonames": c[2], "cc": c[3],
                     "pop": c[4], "drawn": [v["lon"], v["lat"]], "true": [c[0], c[1]],
                     "homonyms": len(cands)})
    km = np.array([r["km"] for r in rows])
    return {"count": len(rows), "median_km": float(np.median(km)), "mean_km": float(km.mean()),
            "p90_km": float(np.percentile(km, 90)), "within_25km": float((km <= 25).mean()),
            "within_50km": float((km <= 50).mean()), "rows": rows}


if __name__ == "__main__":
    main()
