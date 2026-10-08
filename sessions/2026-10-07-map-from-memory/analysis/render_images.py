"""Render thumb.png and hero.png: Europe as a small chart, my drawing over the land."""
import importlib.util
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import SESSION, ne_rings  # noqa: E402

SEA, LAND, EDGE, GRAT, INK, PAPER, MEM = "#e1ecee", "#ecdfb2", "#a8996a", "#c9dadf", "#172227", "#f3f6f5", "#a5166e"
LAT0, LAT1 = 30.0, 67.0
C = math.cos(math.radians((LAT0 + LAT1) / 2))
MID = 16.0
HALF = (LAT1 - LAT0) / C / 2
LON0, LON1 = MID - HALF, MID + HALF


def render(size, path, colors=256):
    ss = 3
    S = size * ss
    pad = int(S * 0.045)
    inner = S - 2 * pad
    k = inner / (LAT1 - LAT0)

    def P(lon, lat):
        return pad + (lon - LON0) * k * C, pad + (LAT1 - lat) * k

    im = Image.new("RGB", (S, S), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle([pad, pad, S - pad, S - pad], fill=SEA)
    for lon in range(-20, 61, 10):
        x, _ = P(lon, 0)
        if pad < x < S - pad:
            d.line([(x, pad), (x, S - pad)], fill=GRAT, width=max(1, ss))
    for lat in range(30, 71, 10):
        _, y = P(0, lat)
        if pad < y < S - pad:
            d.line([(pad, y), (S - pad, y)], fill=GRAT, width=max(1, ss))
    for outer, holes, _ in ne_rings("ne_50m_land"):
        if max(p[0] for p in outer) < LON0 - 5 or min(p[0] for p in outer) > LON1 + 5:
            continue
        if max(p[1] for p in outer) < LAT0 - 5 or min(p[1] for p in outer) > LAT1 + 5:
            continue
        d.polygon([P(*p) for p in outer], fill=LAND, outline=EDGE)
        for h in holes:
            d.polygon([P(*p) for p in h], fill=SEA, outline=EDGE)

    spec = importlib.util.spec_from_file_location("drawn", SESSION / "drawing" / "drawn_world.frozen.py")
    drawn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drawn)
    lw = max(2, int(S / 360))
    for ring in list(drawn.LAND.values()) + list(drawn.LAKES.values()):
        pts = [P(p[0], p[1]) for p in ring]
        d.line(pts + [pts[0]], fill=MEM, width=lw, joint="curve")
        for p, (x, y) in zip(ring, pts):
            if p[2] and pad < x < S - pad and pad < y < S - pad:
                r = lw * 0.9
                d.ellipse([x - r, y - r, x + r, y + r], fill=MEM)

    # neatline with a graduated border: mask the outside, then draw the frame
    d.rectangle([0, 0, S, pad], fill=PAPER)
    d.rectangle([0, S - pad, S, S], fill=PAPER)
    d.rectangle([0, 0, pad, S], fill=PAPER)
    d.rectangle([S - pad, 0, S, S], fill=PAPER)
    bw = int(pad * 0.32)
    step = 5
    for a in range(int(math.floor(LON0 / step)) * step, int(LON1) + step, step):
        x0, _ = P(max(a, LON0), 0)
        x1, _ = P(min(a + step, LON1), 0)
        if x1 <= x0:
            continue
        fill = INK if (a // step) % 2 == 0 else PAPER
        d.rectangle([x0, pad - bw, x1, pad], fill=fill, outline=INK)
        d.rectangle([x0, S - pad, x1, S - pad + bw], fill=fill, outline=INK)
    for a in range(int(LAT0), int(LAT1), step):
        _, y1 = P(0, a)
        _, y0 = P(0, min(a + step, LAT1))
        fill = INK if (a // step) % 2 == 0 else PAPER
        d.rectangle([pad - bw, y0, pad, y1], fill=fill, outline=INK)
        d.rectangle([S - pad, y0, S - pad + bw, y1], fill=fill, outline=INK)
    d.rectangle([pad, pad, S - pad, S - pad], outline=INK, width=max(1, ss))

    out = im.resize((size, size), Image.LANCZOS)
    out = out.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out.save(path, optimize=True)
    print(path.name, out.size, f"{path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    render(1100, SESSION / "hero.png", colors=96)
    render(560, SESSION / "thumb.png", colors=64)
