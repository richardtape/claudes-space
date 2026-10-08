"""Score the blind city guesses against GeoNames.

Reads cities/sample_truth.json (the sealed answers) and cities/guesses/*.tsv.
Writes analysis/city_results.json (one row per guess) and analysis/city_scores.json.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import SESSION, gc_km, ne_rings, wrap180  # noqa: E402

CITIES = SESSION / "cities"
G = 0.1  # country raster resolution, degrees
GW, GH = int(360 / G), int(180 / G)
TIERS = ["T1", "T2", "T3", "T4", "T5"]
TIER_NAMES = {"T1": "5M+", "T2": "1M-5M", "T3": "250k-1M", "T4": "50k-250k", "T5": "15k-50k"}


def load_guesses(prefix):
    out = {}
    for path in sorted((CITIES / "guesses").glob(f"{prefix}_*.tsv")):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                i = int(row["id"])
                assert i not in out, f"duplicate id {i} in {path.name}"
                out[i] = {
                    "lat": float(row["lat"]), "lon": float(row["lon"]),
                    "r50": float(row["r50_km"]), "r90": float(row["r90_km"]),
                    "known": row["known"].strip().upper() == "Y", "batch": path.stem,
                    "raw_lat": row["lat"].strip(), "raw_lon": row["lon"].strip(),
                }
    return out


def country_raster():
    """Rasterise NE 1:50m countries on a 0.1 degree lon/lat grid. Returns the label grid
    (0 = sea), the nearest-country grid, and the list of country names."""
    img = Image.new("I", (GW, GH), 0)
    draw = ImageDraw.Draw(img)
    names = []
    for outer, holes, props in ne_rings("ne_50m_admin_0_countries"):
        name = props["ADMIN"]
        if name not in names:
            names.append(name)
        k = names.index(name) + 1
        for ring, val in [(outer, k)] + [(h, 0) for h in holes]:
            pts = [((lon + 180) / G, (90 - lat) / G) for lon, lat in ring]
            draw.polygon(pts, fill=val)
    lab = np.array(img, np.int32)
    _, (iy, ix) = distance_transform_edt(lab == 0, return_indices=True)
    return lab, lab[iy, ix], names


def cell(lon, lat):
    x = np.clip(((wrap180(lon) + 180) / G).astype(int), 0, GW - 1)
    y = np.clip(((90 - np.asarray(lat)) / G).astype(int), 0, GH - 1)
    return y, x


def summarise(rows):
    if not rows:
        return None
    e = np.array([r["err_km"] for r in rows])
    return {
        "n": len(rows), "median_km": round(float(np.median(e)), 1), "mean_km": round(float(e.mean()), 1),
        "p90_km": round(float(np.percentile(e, 90)), 1),
        "within_10km": round(float((e <= 10).mean()), 3), "within_25km": round(float((e <= 25).mean()), 3),
        "within_50km": round(float((e <= 50).mean()), 3), "within_100km": round(float((e <= 100).mean()), 3),
        "in_r50": round(float(np.mean([r["err_km"] <= r["r50"] for r in rows])), 3),
        "in_r90": round(float(np.mean([r["err_km"] <= r["r90"] for r in rows])), 3),
        "median_r50": round(float(np.median([r["r50"] for r in rows])), 1),
        "median_r90": round(float(np.median([r["r90"] for r in rows])), 1),
        "known_share": round(float(np.mean([r["known"] for r in rows])), 3),
        "right_country": round(float(np.mean([r["right_country"] for r in rows])), 3),
        "in_sea": round(float(np.mean([r["guess_in_sea"] for r in rows])), 3),
    }


def main():
    truth = {r["id"]: r for r in json.loads((CITIES / "sample_truth.json").read_text())}
    first = load_guesses("batch")
    second = load_guesses("retest")
    missing = sorted(set(truth) - set(first))
    assert not missing, f"no guess for {missing}"
    assert set(second) <= set(truth)

    lab, nearest, cnames = country_raster()

    # Country centroids (area-weighted over the raster), for the pull-to-centre test.
    ys, xs = np.nonzero(lab)
    lats = 90 - (ys + 0.5) * G
    lons = (xs + 0.5) * G - 180
    w = np.cos(np.radians(lats))
    cent = {}
    for k in np.unique(lab[lab > 0]):
        m = lab[ys, xs] == k
        # average on the unit sphere to survive the antimeridian
        la, lo, ww = np.radians(lats[m]), np.radians(lons[m]), w[m]
        v = np.array([(ww * np.cos(la) * np.cos(lo)).sum(), (ww * np.cos(la) * np.sin(lo)).sum(), (ww * np.sin(la)).sum()])
        v /= np.linalg.norm(v)
        cent[int(k)] = (float(np.degrees(np.arctan2(v[1], v[0]))), float(np.degrees(np.arcsin(v[2]))))

    def score(t, g):
        err = float(gc_km(t["lon"], t["lat"], g["lon"], g["lat"]))
        dn = (g["lat"] - t["lat"]) * 111.195
        de = float(wrap180(g["lon"] - t["lon"])) * 111.195 * np.cos(np.radians(t["lat"]))
        ty, tx = cell(np.array([t["lon"]]), np.array([t["lat"]]))
        gy, gx = cell(np.array([g["lon"]]), np.array([g["lat"]]))
        tc = int(nearest[ty[0], tx[0]])
        gc = int(lab[gy[0], gx[0]])
        gcn = int(nearest[gy[0], gx[0]])
        return {
            "err_km": round(err, 2), "north_km": round(float(dn), 2), "east_km": round(float(de), 2),
            "true_country_ne": cnames[tc - 1], "guess_country_ne": cnames[gcn - 1] if gcn else None,
            "right_country": gcn == tc, "guess_in_sea": gc == 0, "country_id": tc,
        }

    rows = []
    for i, t in sorted(truth.items()):
        g = first[i]
        r = {k: t[k] for k in ("id", "gid", "name", "admin1", "country", "cc", "continent", "tier", "pop", "lat", "lon")}
        r.update({"g_lat": g["lat"], "g_lon": g["lon"], "r50": g["r50"], "r90": g["r90"], "known": g["known"],
                  "batch": g["batch"], "raw_lat": g["raw_lat"], "raw_lon": g["raw_lon"]})
        r.update(score(t, g))
        if i in second:
            g2 = second[i]
            s2 = score(t, g2)
            r["retest"] = {"g_lat": g2["lat"], "g_lon": g2["lon"], "r50": g2["r50"], "r90": g2["r90"],
                           "known": g2["known"], "err_km": s2["err_km"], "north_km": s2["north_km"],
                           "east_km": s2["east_km"]}
        rows.append(r)

    scores = {"all": summarise(rows)}
    scores["by_tier"] = {t: summarise([r for r in rows if r["tier"] == t]) for t in TIERS}
    scores["by_continent"] = {c: summarise([r for r in rows if r["continent"] == c])
                              for c in ("AF", "AS", "EU", "NA", "SA", "OC")}
    scores["by_known"] = {k: summarise([r for r in rows if r["known"] == (k == "Y")]) for k in ("Y", "N")}
    scores["by_tier_known"] = {f"{t}{k}": summarise([r for r in rows if r["tier"] == t and r["known"] == (k == "Y")])
                               for t in TIERS for k in ("Y", "N")}

    # Bias: mean signed offsets.
    n = np.array([r["north_km"] for r in rows])
    e = np.array([r["east_km"] for r in rows])
    scores["bias"] = {"mean_north_km": round(float(n.mean()), 1), "mean_east_km": round(float(e.mean()), 1),
                      "median_north_km": round(float(np.median(n)), 1), "median_east_km": round(float(np.median(e)), 1),
                      "rms_north_km": round(float(np.sqrt((n ** 2).mean())), 1),
                      "rms_east_km": round(float(np.sqrt((e ** 2).mean())), 1)}

    # Pull towards the country's centre: does the error vector point at the centroid?
    pull = defaultdict(list)
    for r in rows:
        clon, clat = cent[r["country_id"]]
        to_c = np.array([float(wrap180(clon - r["lon"])) * np.cos(np.radians(r["lat"])), clat - r["lat"]])
        err = np.array([r["east_km"], r["north_km"]])
        if np.linalg.norm(to_c) < 1e-6 or np.linalg.norm(err) < 1e-6:
            continue
        cosang = float(to_c @ err / (np.linalg.norm(to_c) * np.linalg.norm(err)))
        # how far the guess sits from the centre, relative to how far the truth does
        dt = float(gc_km(r["lon"], r["lat"], clon, clat))
        dg = float(gc_km(r["g_lon"], r["g_lat"], clon, clat))
        r["toward_centre_cos"] = round(cosang, 3)
        key = "known" if r["known"] else "unknown"
        if r["err_km"] >= 25:  # only errors big enough to have a direction worth reading
            pull[key].append((cosang, dt, dg))
    scores["pull_to_country_centre"] = {
        k: {"n": len(v), "mean_cos": round(float(np.mean([a for a, _, _ in v])), 3),
            "share_pointing_inward": round(float(np.mean([a > 0 for a, _, _ in v])), 3),
            "median_ratio_guess_to_true_distance_from_centre": round(float(np.median([dg / dt for _, dt, dg in v if dt > 1])), 3)}
        for k, v in pull.items()}

    # Heaping: how often do the written coordinates end in round numbers?
    def frac_round(vals, step):
        x = np.array([abs(float(v)) for v in vals])
        return float(np.mean(np.isclose(np.round(x / step) * step, x, atol=1e-9)))

    for k in ("Y", "N"):
        sub = [r for r in rows if r["known"] == (k == "Y")]
        vals = [r["raw_lat"] for r in sub] + [r["raw_lon"] for r in sub]
        scores.setdefault("heaping", {})[k] = {
            "n_coords": len(vals), "share_whole_degree": round(frac_round(vals, 1.0), 3),
            "share_half_degree": round(frac_round(vals, 0.5), 3),
            "share_tenth": round(frac_round(vals, 0.1), 3)}
    scores["heaping"]["chance"] = {"share_whole_degree": 0.01, "share_half_degree": 0.02, "share_tenth": 0.1}

    # Test-retest.
    pairs = [r for r in rows if "retest" in r]
    d12 = np.array([gc_km(r["g_lon"], r["g_lat"], r["retest"]["g_lon"], r["retest"]["g_lat"]) for r in pairs])
    e1 = np.array([r["err_km"] for r in pairs])
    e2 = np.array([r["retest"]["err_km"] for r in pairs])
    mlat = np.array([(r["g_lat"] + r["retest"]["g_lat"]) / 2 for r in pairs])
    mlon = np.array([r["g_lon"] + float(wrap180(r["retest"]["g_lon"] - r["g_lon"])) / 2 for r in pairs])
    em = gc_km(np.array([r["lon"] for r in pairs]), np.array([r["lat"] for r in pairs]), mlon, mlat)
    v1 = np.array([[r["east_km"], r["north_km"]] for r in pairs])
    v2 = np.array([[r["retest"]["east_km"], r["retest"]["north_km"]] for r in pairs])
    big = (e1 > 25) & (e2 > 25)
    cos12 = np.sum(v1 * v2, axis=1) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1) + 1e-9)
    scores["retest"] = {
        "n": len(pairs),
        "median_gap_between_two_guesses_km": round(float(np.median(d12)), 1),
        "median_error_first_km": round(float(np.median(e1)), 1),
        "median_error_second_km": round(float(np.median(e2)), 1),
        "median_error_of_average_km": round(float(np.median(em)), 1),
        "share_gap_smaller_than_error": round(float(np.mean(d12 < np.minimum(e1, e2))), 3),
        "n_both_wrong_by_25km": int(big.sum()),
        "share_same_direction_when_both_wrong": round(float(np.mean(cos12[big] > 0)), 3) if big.any() else None,
        "median_cos_when_both_wrong": round(float(np.median(cos12[big])), 3) if big.any() else None,
        "known_flag_agreement": round(float(np.mean([r["known"] == r["retest"]["known"] for r in pairs])), 3),
        "spearman_err1_err2": round(float(spearman(e1, e2)), 3),
        "by_tier": {t: {"median_gap_km": round(float(np.median(d12[[r["tier"] == t for r in pairs]])), 1),
                        "median_err_km": round(float(np.median(e1[[r["tier"] == t for r in pairs]])), 1)}
                    for t in TIERS},
    }

    (SESSION / "analysis" / "city_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    (SESSION / "analysis" / "city_scores.json").write_text(json.dumps(scores, indent=1))
    print(json.dumps(scores, indent=1))


def spearman(a, b):
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    return np.corrcoef(ra, rb)[0, 1]


if __name__ == "__main__":
    main()
