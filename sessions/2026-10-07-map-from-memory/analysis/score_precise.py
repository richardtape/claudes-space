"""Does asking for four decimals buy real precision? Compare precise_3 with batch_3."""
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import SESSION, gc_km  # noqa: E402

truth = {r["id"]: r for r in json.loads((SESSION / "cities" / "sample_truth.json").read_text())}
first = {r["id"]: r for r in json.loads((SESSION / "analysis" / "city_results.json").read_text())}
rows = []
with open(SESSION / "cities" / "guesses" / "precise_3.tsv", encoding="utf-8") as f:
    for g in csv.DictReader(f, delimiter="\t"):
        i = int(g["id"])
        t = truth[i]
        lat, lon = float(g["lat"]), float(g["lon"])
        e4 = float(gc_km(t["lon"], t["lat"], lon, lat))
        # the same answer cut back to two decimals, to separate rounding from knowledge
        e4r = float(gc_km(t["lon"], t["lat"], round(lon, 2), round(lat, 2)))
        floor = float(gc_km(t["lon"], t["lat"], round(t["lon"], 2), round(t["lat"], 2)))
        rows.append({"id": i, "name": t["name"], "tier": t["tier"], "known": g["known"].strip().upper() == "Y",
                     "err4": e4, "err4_rounded": e4r, "err2": first[i]["err_km"], "floor2": floor,
                     "r50": float(g["r50_km"]), "lat": g["lat"], "lon": g["lon"]})

def q(a):
    a = np.array(a)
    return {"n": len(a), "median": round(float(np.median(a)), 3), "p25": round(float(np.percentile(a, 25)), 3),
            "p75": round(float(np.percentile(a, 75)), 3), "under_100m": round(float((a < 0.1).mean()), 3),
            "under_250m": round(float((a < 0.25).mean()), 3)}

out = {}
for key, sel in (("all", lambda r: True), ("known", lambda r: r["known"]), ("unknown", lambda r: not r["known"])):
    sub = [r for r in rows if sel(r)]
    out[key] = {"four_decimals": q([r["err4"] for r in sub]), "same_cut_to_two": q([r["err4_rounded"] for r in sub]),
                "two_decimal_run": q([r["err2"] for r in sub]), "rounding_floor_two": q([r["floor2"] for r in sub])}
# do the 3rd/4th decimals carry information? fraction where 4dp is closer than its own 2dp rounding
out["fourdp_beats_its_own_rounding"] = round(float(np.mean([r["err4"] < r["err4_rounded"] for r in rows])), 3)
out["fourdp_beats_its_own_rounding_unknown"] = round(float(np.mean([r["err4"] < r["err4_rounded"] for r in rows if not r["known"]])), 3)
(SESSION / "analysis" / "precise_scores.json").write_text(json.dumps({"summary": out, "rows": rows}, indent=1, ensure_ascii=False))
print(json.dumps(out, indent=1))
for r in sorted(rows, key=lambda r: r["known"])[:12]:
    print(r["name"], r["known"], round(r["err4"], 3), round(r["err2"], 3), r["lat"], r["lon"], "r50", r["r50"])
