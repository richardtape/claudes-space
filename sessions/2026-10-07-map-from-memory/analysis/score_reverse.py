"""Score the reverse lookups: coordinates in, place name out.

Each answer gets one grade:
  right      after folding case, accents and punctuation, the name equals the true
             place's GeoNames name, ASCII name or an alternate name, or differs only in
             spelling (similarity >= 0.85 with spaces removed: Koilwar / Koelwar);
  same spot  otherwise, the named place (looked up in GeoNames cities500, in the
             country given, nearest namesake) is within 3 km of the point: a parent
             city, a district, or a duplicate record;
  neighbour  the named place is 3-25 km from the point;
  wrong      further than 25 km, or the name can't be found in cities500.

Writes analysis/reverse_results.json and analysis/reverse_scores.json.
"""
import csv
import difflib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import RAW, SESSION, gc_km  # noqa: E402

TIERS = ["T1", "T2", "T3", "T4", "T5"]
DROP = {"city", "town", "of", "the", "municipality", "district", "county", "shi", "xian", "qu"}


def fold(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("'", "").replace("’", "").replace("ʻ", "")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    words = [w for w in s.split() if w not in DROP]
    return " ".join(words) or s


def main():
    truth = {r["id"]: r for r in json.loads((SESSION / "cities" / "sample_truth.json").read_text())}
    want = {t["gid"] for t in truth.values()}
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
                index[k].append((float(p[5]), float(p[4]), p[8], int(p[0]), p[1]))
    assert set(gid_names) == want, "some sample places are missing from cities500"

    guesses = {}
    for path in sorted((SESSION / "cities" / "guesses").glob("reverse_*.tsv")):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                guesses[int(row["id"])] = {**row, "batch": path.stem}
    missing = sorted(set(truth) - set(guesses))
    print("missing reverse answers:", len(missing))

    rows = []
    for i, t in sorted(truth.items()):
        if i not in guesses:
            continue
        g = guesses[i]
        place = g["place"].strip()
        key = fold(place)
        # also try the part before a comma or bracket ("Pikine, Dakar" / "Bahri (Khartoum North)")
        alts = {key, fold(re.split(r"[,(]", place)[0])}
        inner = re.findall(r"\(([^)]*)\)", place)
        alts |= {fold(x) for x in inner}
        tnames = gid_names[t["gid"]]
        exact = bool(alts & tnames)
        squash = {a.replace(" ", "") for a in alts}
        fuzzy = max(difflib.SequenceMatcher(None, a, b.replace(" ", "")).ratio() for a in squash for b in tnames)
        exact = exact or fuzzy >= 0.85
        cc_ok = g["country"].strip().upper() == t["cc"]
        near_km, near_name = None, None
        cands = [c for a in alts for c in index.get(a, []) if c[2] == g["country"].strip().upper()]
        if cands:
            d = [float(gc_km(t["lon"], t["lat"], c[0], c[1])) for c in cands]
            j = int(np.argmin(d))
            near_km, near_name = round(d[j], 2), cands[j][4]
        try:
            p = float(g["p_correct"])
        except ValueError:
            p = float("nan")
        rows.append({
            "id": i, "name": t["name"], "cc": t["cc"], "tier": t["tier"], "continent": t["continent"],
            "place": place, "country": g["country"].strip().upper(), "region": g["region"].strip(),
            "p_correct": p, "name_ok": exact, "country_ok": cc_ok,
            "near_km": 0.0 if exact else near_km, "near_name": t["name"] if exact else near_name,
            "batch": g["batch"],
        })
        nk = rows[-1]["near_km"]
        rows[-1]["grade"] = ("right" if exact else "same spot" if nk is not None and nk <= 3
                             else "neighbour" if nk is not None and nk <= 25 else "wrong")

    def summ(sub):
        if not sub:
            return None
        ok = np.array([r["name_ok"] for r in sub])
        near = np.array([r["near_km"] is not None and r["near_km"] <= 3 for r in sub])
        p = np.array([r["p_correct"] for r in sub]) / 100
        grades = {gname: round(float(np.mean([r["grade"] == gname for r in sub])), 3)
                  for gname in ("right", "same spot", "neighbour", "wrong")}
        return {"n": len(sub), "grades": grades, "name_right": round(float(ok.mean()), 3),
                "right_or_same_spot": round(float((ok | near).mean()), 3),
                "country_right": round(float(np.mean([r["country_ok"] for r in sub])), 3),
                "mean_p_correct": round(float(np.nanmean(p)), 3),
                "unresolved_wrong": round(float(np.mean([(not r["name_ok"]) and r["near_km"] is None for r in sub])), 3)}

    scores = {"all": summ(rows), "by_tier": {t: summ([r for r in rows if r["tier"] == t]) for t in TIERS},
              "by_continent": {c: summ([r for r in rows if r["continent"] == c])
                               for c in ("AF", "AS", "EU", "NA", "SA", "OC")}}

    # Calibration of p_correct.
    bins = [(0, 10), (10, 30), (30, 50), (50, 70), (70, 90), (90, 101)]
    cal = []
    for lo, hi in bins:
        sub = [r for r in rows if lo <= r["p_correct"] < hi]
        if sub:
            cal.append({"bin": f"{lo}-{min(hi, 100)}", "n": len(sub),
                        "mean_p": round(float(np.mean([r["p_correct"] for r in sub])) / 100, 3),
                        "hit_rate": round(float(np.mean([r["name_ok"] for r in sub])), 3)})
    scores["calibration"] = cal
    p = np.array([r["p_correct"] for r in rows]) / 100
    y = np.array([r["name_ok"] for r in rows], float)
    scores["brier"] = round(float(np.mean((p - y) ** 2)), 4)

    # Pair with the forward test: places named exactly forward but missed in reverse.
    fwd = {r["id"]: r for r in json.loads((SESSION / "analysis" / "city_results.json").read_text())}
    both = [(fwd[r["id"]]["err_km"] <= 5, r["name_ok"]) for r in rows]
    scores["paired"] = {
        "forward_within_5km": int(sum(a for a, _ in both)),
        "forward_within_5km_and_reverse_right": int(sum(a and b for a, b in both)),
        "forward_within_5km_but_reverse_wrong": int(sum(a and not b for a, b in both)),
        "forward_wrong_but_reverse_right": int(sum((not a) and b for a, b in both)),
    }

    (SESSION / "analysis" / "reverse_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    (SESSION / "analysis" / "reverse_scores.json").write_text(json.dumps(scores, indent=1))
    print(json.dumps(scores, indent=1))


if __name__ == "__main__":
    main()
