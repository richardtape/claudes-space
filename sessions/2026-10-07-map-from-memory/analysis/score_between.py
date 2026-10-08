"""Score the 'between the entries' test: arbitrary land points in, nearest town out.

For each point the truth is the list of the ten nearest GeoNames places of 15,000+
(from cities/between_sample.py). The answer is looked up in GeoNames cities500, in
the country given, taking the namesake nearest the point. Grades:
  nearest    it is the true nearest 15,000+ place (by record, name or close spelling)
  top 3      it is the second or third nearest
  close      it's further down the list, but no more than 10 km further than the nearest
  wrong      anything else, or a name not found in cities500
Writes analysis/between_results.json and analysis/between_scores.json.
"""
import csv
import difflib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import RAW, SESSION, gc_km  # noqa: E402
from score_reverse import fold  # noqa: E402


def main():
    pts = {q["id"]: q for q in json.loads((SESSION / "cities" / "between_truth.json").read_text())}
    want = {n["gid"] for q in pts.values() for n in q["nearest"]}
    gid_names = {}
    index = defaultdict(list)
    with open(RAW / "geonames" / "cities500.txt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            names = {p[1], p[2]} | {a for a in p[3].split(",") if a}
            keys = {fold(n) for n in names if n}
            if int(p[0]) in want:
                gid_names[int(p[0])] = keys
            for k in keys:
                index[k].append((float(p[5]), float(p[4]), p[8], int(p[0]), p[1], int(p[14] or 0)))

    answers = {}
    for path in sorted((SESSION / "cities" / "guesses").glob("between_*.tsv")):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                answers[int(row["id"])] = {**row, "batch": path.stem}
    print("answered", len(answers), "of", len(pts))

    def same(key, gid):
        names = gid_names.get(gid, set())
        if key in names:
            return True
        k = key.replace(" ", "")
        return any(difflib.SequenceMatcher(None, k, n.replace(" ", "")).ratio() >= 0.85 for n in names)

    rows = []
    for i, q in sorted(pts.items()):
        if i not in answers:
            continue
        a = answers[i]
        place = a["place"].strip()
        key = fold(place.split(",")[0].split("(")[0])
        cc = a["country"].strip().upper()
        rank = None
        for j, n in enumerate(q["nearest"]):
            if same(key, n["gid"]):
                rank = j + 1
                break
        cands = [c for c in index.get(key, []) if c[2] == cc]
        named_km, named = None, None
        if rank:
            named_km = q["nearest"][rank - 1]["km"]
            named = q["nearest"][rank - 1]["name"]
        elif cands:
            d = [float(gc_km(q["lon"], q["lat"], c[0], c[1])) for c in cands]
            j = int(np.argmin(d))
            named_km, named = round(d[j], 2), cands[j][4]
        nearest_km = q["nearest"][0]["km"]
        try:
            est = float(a["km"])
        except ValueError:
            est = float("nan")
        try:
            p = float(a["p_nearest"])
        except ValueError:
            p = float("nan")
        grade = ("nearest" if rank == 1 else "top 3" if rank in (2, 3)
                 else "close" if named_km is not None and named_km - nearest_km <= 10 else "wrong")
        rows.append({
            "id": i, "kind": q["kind"], "lat": q["lat"], "lon": q["lon"], "place": place, "country": cc,
            "est_km": est, "p_nearest": p, "rank": rank, "named": named, "named_km": named_km,
            "nearest": q["nearest"][0]["name"], "nearest_cc": q["nearest"][0]["cc"], "nearest_km": nearest_km,
            "excess_km": None if named_km is None else round(named_km - nearest_km, 2), "grade": grade,
            "batch": a["batch"],
        })

    def summ(sub):
        g = {k: round(float(np.mean([r["grade"] == k for r in sub])), 3) for k in ("nearest", "top 3", "close", "wrong")}
        res = [r for r in sub if r["named_km"] is not None]
        ratio = np.array([r["est_km"] / r["named_km"] for r in res if r["named_km"] > 1 and r["est_km"] == r["est_km"]])
        return {
            "n": len(sub), "grades": g,
            "median_nearest_km": round(float(np.median([r["nearest_km"] for r in sub])), 1),
            "median_excess_km": round(float(np.median([r["excess_km"] for r in res])), 2) if res else None,
            "p90_excess_km": round(float(np.percentile([r["excess_km"] for r in res], 90)), 1) if res else None,
            "share_resolved": round(len(res) / len(sub), 3),
            "median_distance_ratio_est_over_actual": round(float(np.median(ratio)), 3) if len(ratio) else None,
            "share_distance_within_25pct": round(float(np.mean(np.abs(ratio - 1) <= 0.25)), 3) if len(ratio) else None,
            "mean_p_nearest": round(float(np.nanmean([r["p_nearest"] for r in sub])) / 100, 3),
        }

    scores = {"all": summ(rows), "offset": summ([r for r in rows if r["kind"] == "offset"]),
              "random": summ([r for r in rows if r["kind"] == "random"])}
    cal = []
    for lo, hi in ((0, 30), (30, 50), (50, 70), (70, 90), (90, 101)):
        sub = [r for r in rows if lo <= r["p_nearest"] < hi]
        if sub:
            cal.append({"bin": f"{lo}-{min(hi, 100)}", "n": len(sub),
                        "mean_p": round(float(np.mean([r["p_nearest"] for r in sub])) / 100, 3),
                        "hit_rate": round(float(np.mean([r["grade"] == "nearest" for r in sub])), 3)})
    scores["calibration"] = cal
    (SESSION / "analysis" / "between_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    (SESSION / "analysis" / "between_scores.json").write_text(json.dumps(scores, indent=1))
    print(json.dumps(scores, indent=1))


if __name__ == "__main__":
    main()
