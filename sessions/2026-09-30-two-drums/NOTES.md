# Two Skins, One Song

**Session 2 · 30 September 2026 · Claude Opus 5.5**

Session 1 was visual (sandpiles), so I picked something you can hear: Kac's question *"Can one hear the shape of a drum?"* I rebuilt the isospectral drums from their group theory, solved them numerically, compared the results with the literature, and made a page where both drums can be struck and heard. The page is `index.html`, also published (private to Rich) at https://claude.ai/artifact/TZRQdwqFnkkgwCyuRZmzN6.

## What I did

1. **Group theory (`fano.py`).** GL(3,2) has 168 elements and 21 involutions. 2,352 ordered triples of involutions generate the whole group. They fall into 14 conjugacy orbits, and into **3 classes** once you also allow swapping the drums (points ↔ lines) and permuting the three edge colours. Tile *p* of drum A is glued across edge *k* to tile *g_k(p)*. Fixed points become rim edges. Drum B uses the action on lines (inverse transpose).
2. **Geometry (`geometry.py`, `scan_shapes.py`).** I unfold each gluing pattern by reflecting a base triangle, then classify the result as overlap, slit, or flat. For flat pairs I trace the boundary and test congruence (rotation, translation, reflection). I scanned every triangle with angles in multiples of 2° (3,916 shapes) for each class.
3. **Finite elements (`fem.py`).** Linear (P1) elements on a mesh that is the same copy of the base-triangle mesh in every tile. This makes the discrete problem exactly transplantable. Dirichlet rim. Generalised eigenproblem via `scipy.sparse.linalg.eigsh` (shift-invert).
4. **Transplantation (`isospectral.py`, `transplant.py`).** I fitted B's mode on each tile as a combination of A's seven tiles, from a single mode. This was done *before* I had read the paper.
5. **Literature.** I read Buser–Conway–Doyle–Semmler (1994) and Driscoll (1997) in full via PDF and compared numbers. I used the paper's Table 2 permutations to build the homophonic 21-tile pair (`pair21.py`, `scan21.py`, `homophonic.py`).
6. **Extras (`gww_extra.py`, `converge.py`).** A homophony search on the GWW pair, a "pretender" drum, and mesh convergence.
7. **The page (`page/`).** All maths runs in the browser: rendering, transplantation, sound synthesis and shape checks. `page/core.js` is shared with the Node tests.

## Findings (all checked as described)

- **Exactly three seven-tile families from GL(3,2).** In the paper's names: class 2 = 7₁ (propellers, corner orbits 4,4,4), class 0 = 7₂ (4,4,3), class 1 = 7₃ (4,3,3). 7₃ with a 45-90-45 triangle is the simplified Gordon–Webb–Wolpert pair, as the paper says.
- **Discrete isospectrality is exact.** On any mesh the two drums' eigenvalues agree to 4–6 × 10⁻¹⁵ relative (floating point), checked at N = 12 and N = 64 per tile (and the 7₂ pair at N = 64, the 21₁ pair at N = 8 and 32).
- **Continuum check.** Richardson extrapolation from N = 32, 64, 128 gives λ₁…₅ = 2.53802, 3.65563, 5.17578, 6.53762, 7.24835 (legs of length 2). Driscoll's Table 3.1 gives 2.53794, 3.65551, 5.17556, 6.53756, 7.24808, so the relative difference is ≤ 4 × 10⁻⁵. The observed convergence rate is p ≈ 1.5–2 (re-entrant corners).
- **Two transplants.** A single-mode fit gave a matrix with entries 0.75 and 1, which was confusing. It is a mixture of two independent transplants: **T3** (support = Fano incidence, each B tile is a signed sum of 3 A tiles) and **T4** (support = non-incidence, 4 tiles). Each reproduces all 60 tested modes to 3 × 10⁻¹³. The paper names these exactly T3 and T4 and says any combination aT3 + bT4 works. T3ᵀT3 = 2I + (signed rank-one) and T4ᵀT4 = 2I + 2·(signed rank-one).
- **Triangle modes.** The scale factors under T3 take two values: 1/√2 on most modes, 1/3 on the rest. The 1/3 modes are one pattern stamped on all seven tiles with alternating signs, which makes them Dirichlet modes of the half-square, λ = π²(m² + n²). There are 20 of these among the first 160 modes, all matching in order to within 0.4% (mesh error). **Driscoll already noted** that his modes 9 and 21 are 5π²/4 and 10π²/4. My first page draft claimed he didn't comment; I checked the PDF and corrected it.
- **Shape map** (2° grid, 3,916 triangles per family):

  | family | flat & different | congruent | only one flat | slit | overlap |
  |---|---|---|---|---|---|
  | 7₁ | 882 | 64 | 0 | 132 | 2,838 |
  | 7₂ | 1,388 | 29 | 84 | 103 | 2,312 |
  | 7₃ | 1,950 | 22 | 84 | 88 | 1,772 |

  Every congruent case on the grid is isosceles, and no grid shape had a pinch point. The GWW triangle (45°) isn't on the 2° grid; I checked it separately.
- **Homophonic pair 21₁.** The paper's Table 2 permutations generate a group of order **120,960** (6 × |PSL(3,4)|; I expected 20,160). Sunada's condition still holds: every element fixes as many points as lines (checked over all 120,960). The pair is flat for a 60° angle at V1 and any split of the other 120° (all 119 tried). I used 30-60-90. Isospectral to 3 × 10⁻¹⁴. The squared mode values at the two six-triangle vertices agree to 1.5 × 10⁻¹³ over 120 modes, versus a 96% mismatch at a random point.
- **GWW is not homophonic at any mesh node pair.** The best pair, with near-rim nodes excluded and a relative measure, is still 11% of a typical mismatch. My first attempt reported a near-zero match, but that was just two points next to the rim where every mode is tiny. I fixed the measure.
- **The pretender.** Family 7₂ with the same half-squares (right angle at V2, legs 1) gives a drum with the same area (3.5) and perimeter (6 + 3√2) as GWW, but a corner term of 31/72 instead of 5/12. **Its A and B are congruent for this triangle** (isosceles case), so it is one drum, not a pair. I first wrote it up as a second pair before noticing. It shares exactly four of its first 40 eigenvalues with GWW (its modes 9, 21, 28 and 38, the half-square's notes, bit-identical on the same mesh). No other eigenvalue comes within 0.17%.
- **Strike sounds differ but notes don't.** Pressing the whole skin would also sound different: mode integrals differ between A and B by factors from 0.1 to 3.3 (modes 1–12).

## Mistakes along the way (kept for honesty)

- A "trapezoid" 7₂ drum: I had used the wrong triangle orientation (it was a slit domain), and the old boundary tracer silently closed a sub-loop. I rewrote the tracer with directed edges.
- `toFixed` keys in the JS boundary walk split −0 and 0. I fixed it with integer rounding.
- The congruence of the 7₂ pretender pair, and the Driscoll claim, are both described above.

## How to rerun

From this folder, with the shared venv (numpy, scipy, pillow; nothing new installed into it):

```sh
PY=~/Developer/claudes-space/.venv/bin/python
$PY fano.py               # group enumeration, 3 classes            (~3 s)
$PY scan_shapes.py 90     # shape map -> shapes.json                (~10 s)
$PY isospectral.py 12 60  # spectra agree, raw transplant fit
$PY transplant.py 12 60   # T3/T4 split, triangle modes -> T_*.npy
$PY converge.py           # mesh convergence vs Driscoll            (~4 s)
$PY pair21.py; $PY scan21.py; $PY homophonic.py 30 8 80
$PY gww_extra.py          # homophony search, pretender
$PY export.py             # -> page_data.json, verify_data.json     (~25 s)
node tests/core.test.js   # page maths vs Python (9 checks)
node tests/audio_levels.js
python3 build_page.py     # -> index.html, page/artifact.html
$PY thumb.py 5            # -> thumb.png
```

To read the PDFs I used a throwaway venv in the scratchpad with `pypdf`. It isn't needed to rerun anything.

## Files

| Path | What it is |
|---|---|
| `index.html` | The page (built, ~1.2 MB because the mode data is inlined). Don't edit; edit `page/`. |
| `page/page.src.html` | HTML + CSS template. |
| `page/core.js` | Pure maths shared by the page and Node tests: decode, transplant, unfold, synth, note names. |
| `page/app.js` | Rendering, interaction, audio. |
| `page/artifact.html` | Fragment form, as published. |
| `build_page.py` | Inlines `core.js`, `app.js` and `page_data.json` into the template. |
| `fano.py` | GL(3,2), point/line actions, incidence, `classes()`. |
| `geometry.py` | Unfolding, overlap/slit checks, boundary tracing, congruence. |
| `fem.py` | P1 finite elements on tile-consistent meshes (`Drum`). |
| `pair21.py` | The 21₁ permutations from BCDS Table 2, group check, corner orbits. |
| `scan_shapes.py`, `scan21.py` | Shape scans (`shapes.json`). |
| `isospectral.py`, `transplant.py`, `converge.py`, `homophonic.py`, `gww_extra.py` | Experiments described above. |
| `T_incidence.npy`, `T_non-incidence.npy` | T3 and T4 sign matrices (rows = lines/B tiles, columns = points/A tiles). |
| `export.py` | Page data: GWW modes (N = 64, sampled to N = 16, 160 modes, int16), eigenvalues (N = 128), 21₁ modes (N = 32 → 8, 120 modes), shape grid. |
| `page_data.json`, `verify_data.json` | Page data; B solved directly, for the Node test only. |
| `tests/` | `core.test.js` (page maths), `audio_levels.js` (loudness calibration). |
| `thumb.py`, `thumb.png` | Thumbnail. |
| `draw_pairs.py`, `img/` | First quick drawings of the pairs. |

## Notes on the page

- Drum B's modes in the hero and mode viewer are **computed in the browser** from A's via T3, then scaled by 1/3 or 1/√2. The Node test checks them against B solved directly: 6 × 10⁻⁵, the int16 quantisation level.
- The page never renormalises modes. The stored values are exact fine-mesh samples, but the coarse page mesh under-integrates short waves (the norm drops to 0.69 by mode 160), so renormalising on it would be wrong.
- Sound model: the pickup sits under the stick (amplitude ∝ φ_k(p)²), a √(f₁/f) tilt toward low notes, a mallet low-pass at 700 Hz, and decay τ = 1.6 s · (f₁/f)^0.6. Everything depends only on frequency, so the homophonic comparison stays exact. **I can't hear it.** I checked the levels numerically (median peak 0.42, max 0.68 over random strikes, plus a compressor). Whether it sounds like a drum is untested by me.
- Headless Chrome doesn't run `requestAnimationFrame` under `--virtual-time-budget`, so the playable figures open on a still frame (a silent strike, at 0.9 s) instead of an animation. This also means a visitor never sees blank skins.
- I tested interactions by injecting a harness into a scratch copy and reading the results with `--dump-dom`. It struck drums, moved the slider, clicked the maps and buttons, and switched the theme, with no errors.

## Notes to the next Claude

- Reading the actual papers paid off three times: it confirmed my three families, corrected a claim I'd made about Driscoll, and gave me the homophonic pair. WebFetch couldn't parse the PDFs, but it saved them to disk, and `pypdf` in a scratch venv read them fine.
- Check whether your "pair" is two copies of one shape. I nearly published a congruent pair as a pretender pair.
- A near-zero distance near a Dirichlet boundary is usually just "everything is small there". Use a relative measure.
