"""Draw a stratified sample of world cities from GeoNames and write blind prompts.

Prints nothing about coordinates. Writes:
  cities/sample_truth.json   the sealed answers (opened only by score.py)
  cities/batches/batch_K.txt the names the guessers see, in shuffled order
  cities/batches/retest_K.txt a second, differently shuffled pass over a subset
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "raw" / "geonames"
SEED = 20261007

TIERS = [  # (name, min population, max population)
    ("T1", 5_000_000, 10**12),
    ("T2", 1_000_000, 5_000_000),
    ("T3", 250_000, 1_000_000),
    ("T4", 50_000, 250_000),
    ("T5", 15_000, 50_000),
]
PER_CONTINENT = {"T2": 19, "T3": 19, "T4": 19, "T5": 19}
CONTINENTS = ["AF", "AS", "EU", "NA", "SA", "OC"]
KEEP_CODES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG", "PPLS", "PPLF", "PPLR", "PPLL"}
BATCH_SIZE = 90
RETEST_PER_TIER = 20


def load():
    countries, continent = {}, {}
    for line in (RAW / "countryInfo.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split("\t")
        countries[f[0]] = f[4]
        continent[f[0]] = f[8]
    admin1 = {}
    for line in (RAW / "admin1CodesASCII.txt").read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        admin1[f[0]] = f[1]
    rows = []
    for line in (RAW / "cities15000.txt").read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if f[7] not in KEEP_CODES:
            continue
        cc = f[8]
        if cc not in continent:
            continue
        rows.append({
            "gid": int(f[0]), "name": f[1], "ascii": f[2], "lat": float(f[4]), "lon": float(f[5]),
            "code": f[7], "cc": cc, "country": countries[cc], "continent": continent[cc],
            "admin1": admin1.get(f"{cc}.{f[10]}", ""), "pop": int(f[14] or 0),
        })
    return rows


def tier_of(pop):
    for name, lo, hi in TIERS:
        if lo <= pop < hi:
            return name
    return None


def main():
    rng = random.Random(SEED)
    rows = load()
    by = defaultdict(list)
    for r in rows:
        t = tier_of(r["pop"])
        if t:
            r["tier"] = t
            by[(t, r["continent"])].append(r)

    avail = Counter({k: len(v) for k, v in by.items()})
    print("available per (tier, continent):")
    for t, *_ in TIERS:
        print(" ", t, {c: avail[(t, c)] for c in CONTINENTS})

    chosen = []
    # T1: every city of five million or more.
    for c in CONTINENTS:
        chosen += by[("T1", c)]
    # T2-T5: equal numbers per continent; any shortfall is made up from Asia and Africa,
    # which have the most cities to spare.
    for t, n in PER_CONTINENT.items():
        short = 0
        picked_ids = set()
        for c in CONTINENTS:
            pool = by[(t, c)]
            k = min(n, len(pool))
            pick = rng.sample(pool, k)
            chosen += pick
            picked_ids |= {r["gid"] for r in pick}
            short += n - k
        spare = [r for c in ("AS", "AF", "EU") for r in by[(t, c)] if r["gid"] not in picked_ids]
        chosen += rng.sample(spare, short)

    # Two places with the same name in the same region would make a question ambiguous.
    keyc = Counter((r["name"], r["admin1"], r["cc"]) for r in rows)
    chosen = [r for r in chosen if keyc[(r["name"], r["admin1"], r["cc"])] == 1]

    rng.shuffle(chosen)
    for i, r in enumerate(chosen, 1):
        r["id"] = i
    print("sampled", len(chosen), Counter(r["tier"] for r in chosen), Counter(r["continent"] for r in chosen))

    (HERE / "sample_truth.json").write_text(json.dumps(chosen, ensure_ascii=False, indent=0))

    def line(r):
        place = r["name"] if r["admin1"] in ("", r["name"]) else f"{r['name']}, {r['admin1']}"
        return f"{r['id']}. {place}, {r['country']}"

    out = HERE / "batches"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.txt"):
        old.unlink()
    nb = (len(chosen) + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(nb):
        part = chosen[b::nb]
        (out / f"batch_{b + 1}.txt").write_text("\n".join(line(r) for r in part) + "\n", encoding="utf-8")
        print(f"batch_{b + 1}: {len(part)} places")

    # Retest: a stratified subset, re-shuffled and split differently, so no retest batch
    # shares its neighbours or its order with the first pass.
    retest = []
    for t, *_ in TIERS:
        pool = [r for r in chosen if r["tier"] == t]
        retest += rng.sample(pool, min(RETEST_PER_TIER, len(pool)))
    rng.shuffle(retest)
    half = len(retest) // 2
    for k, part in enumerate((retest[:half], retest[half:]), 1):
        (out / f"retest_{k}.txt").write_text("\n".join(line(r) for r in part) + "\n", encoding="utf-8")
        print(f"retest_{k}: {len(part)} places")


if __name__ == "__main__":
    sys.exit(main())
