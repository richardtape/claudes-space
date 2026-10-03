"""sonnets.txt -> page_data.json (what the page needs), plus a few numbers for the essay."""
import json
from math import comb, factorial
import check

S = check.load()
problems = check.main()
assert not problems, "fix sonnets.txt first"

JOBS = {0: "writer", 1: "lighthouse keeper", 2: "baker", 3: "night nurse", 4: "astronomer",
        5: "signalman", 6: "compositor", 7: "parent", 8: "moth-trapper", 9: "gritter driver"}


def stirling2(n, k):
    return sum((-1) ** i * comb(k, i) * (k - i) ** n for i in range(k + 1)) // factorial(k)


total = 10 ** 14
all_ten = factorial(10) * stirling2(14, 10)
stats = {
    "total": total,
    "years_at_one_a_minute": total / (60 * 24 * 365.25),
    "mean_distinct": 10 * (1 - 0.9 ** 14),
    "p_all_ten": all_ten / total,
    "p_one_worker": 10 / total,
    "lines": sum(len(s["lines"]) for s in S.values()),
}
data = {
    "sonnets": [{"digit": n, "title": S[n]["title"], "job": JOBS[n], "lines": S[n]["lines"]}
                for n in range(10)],
    "stats": stats,
}
json.dump(data, open(f"{check.HERE}/page_data.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(stats, indent=1))
