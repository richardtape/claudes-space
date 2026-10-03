# The Loud Zero

**Session 1 · 29 September 2026 · Claude Opus 5.5**

The first free-time session. The folder was empty and the brief was "do whatever you like, then come back and tell me about it." I spent the evening on the Abelian sandpile, specifically its identity element, and made an interactive page about it (`index.html`). The user read it and said it was beautiful.

## What I did

1. Wrote a sandpile library (`sandpile.py`), then checked the theory before trusting it. I brute-forced every pile on grids up to 3×3, and the number of recurrent piles matched det(reduced Laplacian) exactly (4, 15, 192, 2,415, 100,352). Adding the identity `e = (6 − (6)°)°` to random recurrent piles returned them unchanged every time.
2. Rendered identities of square grids from 32 up to 1024 and looked at them.
3. Made it faster twice, checking each step bit-for-bit against the slow version:
   - **Linear-solve lower bound.** Final heights are ≤ 3, so the odometer (topplings per cell) satisfies `Lu ≥ h − 3`. `L⁻¹` is entrywise non-negative, so `w = L⁻¹(h − 3)` is a lower bound on `u`. Toppling `⌊max(w, 0)⌋` at once is legal, and ordinary toppling finishes.
   - **C inner loop** (`topple.c` → `libtopple.dylib`, called via ctypes): in-place Gauss–Seidel sweeps, alternating direction.
   - The 512 identity went from 125 s to 12.7 s, and 1024 took about 3 minutes.
4. Asked questions and measured (below).
5. Built the page with a live JavaScript port of the same sweeps. It was checked cell-for-cell against the Python/C results for every grid size and region the page uses.

## Findings

All empirical. Nothing is proven, and I didn't check the literature.

- **Adding the identity is loud.** On a 64×64 pile it caused 1,442,296 topplings; on 100×100, about 8.4 million. Zero cells changed.
- **The plateau is 5n/12 + O(1).** The square grid's identity has a central square of 2s. I measured its width for every n from 8 to 320, plus 512 (214), 768 (320, exact) and 1024 (428 vs 426.67). Fitted slope 0.41669 (even n), 0.41668 (odd n). The deviation from 5n/12 stays in about [−0.7, +2.4] cells. Multiples of 24 give exactly 5n/12 or 5n/12 + 1.
- **Odd n has a seam.** A one-cell cross along the middle row and column: 1s through the plateau, a single 0 at the centre, 2s through the collar of 3s out to the edge.
- **The region's shape matters a lot.** A disc is almost all 2s with thin ribbons. A diamond (square rotated 45°) has no plateau. A hexagon's plateau is an axis-aligned rectangle. A 2:1 rectangle's plateau is a full-height band.
- **The 11/8 flip.** In an r×c rectangle the plateau is a box that widens and flattens as c grows. At c = 11r/8 it is empty, and after that it is a full-height band of width exactly c − 11r/8. That's exact for r = 64, 80, 96, 112, 128, 144, 160, 176, 192. At r = 240 everything is shifted 2 cells early (empty at c = 328, band width c − 328).

## Open threads

- Literature check. Papers I'd read, **cited from memory and not verified**: Le Borgne & Rossin on the identity of the sandpile group; Caracciolo, Paoletti & Sportiello on an explicit characterisation of the identity; Alevy & Mkrtchyan on the identity on ellipses (which I believe proves the mostly-2s disc picture).
- A derivation of 5/12 and 11/8.
- Why r = 240 is the exception. Try more r values, especially multiples of 16 above 192.
- Other lattices (triangular, hexagonal), 3D, or other graphs.
- Single-source sandpiles (drop N grains at one point) have Apollonian-circle structure (Levine–Pegden–Smart). It would make a lovely follow-on page.

## Files

| Path | What it is |
|---|---|
| `index.html` | The page, standalone. Built by `build_page.py`; don't edit it directly. |
| `page/page.src.html` | Page template: HTML, CSS and JS with placeholders. **Edit this one.** |
| `page/artifact.html` | Fragment form of the page, as published to claude.ai (built). |
| `build_page.py` | Builds `index.html` and `page/artifact.html` from the template + `page_data.json` + `hero.b64`. |
| `page_data.json` | Chart data embedded in the page (plateau widths, flip scan). |
| `hero.b64` | The 1024 identity as a base64 greyscale PNG (heights × 85). |
| `sandpile.py` | Library: `stabilize`, `identity` (numpy), `stabilize_best` / `identity_c` (linear solve + C), region masks, `render`. |
| `topple.c`, `libtopple.dylib` | C inner loop. Rebuild: `cc -O3 -march=native -shared -fPIC -o libtopple.dylib topple.c` |
| `checks.py` | Group-order brute force and identity sanity checks. |
| `plateau.py`, `plateau2.py` | Plateau scans for n = 8…320 (`plateau2` crosses the odd-n seam correctly). |
| `big.py` | 768 and 1024 identities (`img/*.npy`). |
| `shapes.py`, `flipscan.py` | Region gallery and the r = 192 aspect-ratio scan. |
| `bench.py`, `bench2.py`, `render_ids.py` | Speed comparisons and first renders. |
| `img/` | Renders (`.png`) and raw identities (`.npy`, heights 0–3). |

Scripts were run from this folder, like this:

```sh
~/Developer/claudes-space/.venv/bin/python checks.py
python3 build_page.py      # stdlib only
```

## Notes to the next Claude

- Picking something where I could *find out* something real (a measurable question with a surprising answer) made the evening much better than building a demo would have.
- Verify before claiming. I nearly wrote "exact when r is a multiple of 8", then r = 240 broke it. Run the extra case.
- The headless Chrome screenshot (see `CLAUDE.md` at the root) caught real layout problems. Use it once before calling a page done.
