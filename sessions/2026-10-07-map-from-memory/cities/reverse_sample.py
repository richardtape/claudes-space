"""Write the reverse (coordinates -> name) prompts for the same 522 places, and a
four-decimal forward prompt for one batch. Prints nothing about names-to-coordinates."""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "sample_truth.json").read_text())
rng = random.Random(20261008)
rng.shuffle(rows)
out = HERE / "batches"
nb = 6
for b in range(nb):
    part = rows[b::nb]
    lines = [f"{r['id']}. {r['lat']:.2f}, {r['lon']:.2f}" for r in part]
    (out / f"reverse_{b + 1}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"reverse_{b + 1}: {len(part)} points")
