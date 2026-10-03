// node tests/core.test.js  -- checks the page's maths against the Python results.
const D = require("../page/core.js");
const data = require("../page_data.json");
const ver = require("../verify_data.json");
let fails = 0;
const check = (ok, msg) => { console.log((ok ? "ok   " : "FAIL ") + msg); if (!ok) fails++; };

const g = data.gww, mesh = D.baseMesh(g.n), nl = mesh.nl, per = g.tiles * nl;
check(nl === (g.n + 1) * (g.n + 2) / 2, `base mesh has ${nl} nodes`);
const area = D.triArea(g.tri) * g.tiles;
const A = D.decodeModes(g.modes, g.scales, g.m, g.tiles, nl);
const n0 = [...Array(g.m).keys()].map(k => D.modeNorm2(A, k, g.tiles, mesh, area));
// Values are exact fine-mesh samples; the coarse page mesh under-integrates short waves, so the
// quadrature norm drifts below 1 smoothly as k grows. The page therefore never renormalises.
check(n0.slice(0, 3).every(x => Math.abs(x - 1) < 0.02), `modes 1-3 have page-mesh norm within 2% of 1 (${n0.slice(0, 3).map(x => x.toFixed(3))})`);
check(n0[39] < n0[9] && n0[159] < n0[39] && n0[159] > 0.6, `norm drifts down smoothly with k (mode 10 ${n0[9].toFixed(3)}, 40 ${n0[39].toFixed(3)}, 160 ${n0[159].toFixed(3)})`);
const B = D.fixSign(D.transplantGWW(A, g.T3, g.m, g.tiles, nl, g.triMode), g.m, per);
const Bd = D.fixSign(D.decodeModes(ver.gwwB, ver.gwwBscales, g.m, g.tiles, nl), g.m, per);
// compare mode by mode, skipping (near-)degenerate eigenvalues where the basis is arbitrary
let worst = 0, skipped = [];
for (let k = 0; k < g.m; k++) {
  const gap = Math.min(k > 0 ? g.lam[k] - g.lam[k - 1] : Infinity, k < g.m - 1 ? g.lam[k + 1] - g.lam[k] : Infinity) / g.lam[k];
  if (gap < 1e-4) { skipped.push(k + 1); continue; }
  let e = 0, mx = 0;
  for (let i = 0; i < per; i++) { e = Math.max(e, Math.abs(B[k * per + i] - Bd[k * per + i])); mx = Math.max(mx, Math.abs(Bd[k * per + i])); }
  worst = Math.max(worst, e / mx);
}
check(worst < 2e-4, `transplanted and rescaled B equals directly solved B (same scale, no renormalising), worst rel. error ${worst.toExponential(2)} (skipped degenerate modes ${skipped})`);
// unfold
const place = D.unfold(g.permsA, g.tri);
let pe = 0;
place.forEach((M, i) => M.forEach((v, j) => pe = Math.max(pe, Math.abs(v - g.A.place[i][j]))));
check(pe < 1e-9, `JS unfold matches Python placements (max diff ${pe.toExponential(1)})`);
const placeB = D.unfold(g.permsB, g.tri);
let pb = 0;
placeB.forEach((M, i) => M.forEach((v, j) => pb = Math.max(pb, Math.abs(v - g.B.place[i][j]))));
check(pb < 1e-9, `JS unfold matches Python for drum B too`);
// synth
const f = [110, 220], s = D.synth(f, [1, 0.5], [1, 0.5], 44100, 1);
const ref = i => Math.sin(2 * Math.PI * 110 * i / 44100) * Math.exp(-i / 44100) + 0.5 * Math.sin(2 * Math.PI * 220 * i / 44100) * Math.exp(-i / 22050);
let se = 0; for (let i = 100; i < s.length; i++) se = Math.max(se, Math.abs(s[i] - ref(i)));
check(se < 1e-4, `resonator bank matches closed form (max err ${se.toExponential(1)})`);
check(D.noteName(440).name === "A4" && D.noteName(110).name === "A2" && D.noteName(261.63).name === "C4", "note names");
// homophonic
const h = data.homo, mh = D.baseMesh(h.n), ah = D.triArea(h.tri) * h.tiles;
const HA = D.decodeModes(h.modesA, h.scalesA, h.m, h.tiles, mh.nl);
const HB = D.decodeModes(h.modesB, h.scalesB, h.m, h.tiles, mh.nl);
let he = 0, hm = 0;
for (let k = 0; k < h.m; k++) {
  const va = HA[k * h.tiles * mh.nl + h.special.A.tile * mh.nl + h.special.A.node];
  const vb = HB[k * h.tiles * mh.nl + h.special.B.tile * mh.nl + h.special.B.node];
  he = Math.max(he, Math.abs(va * va - vb * vb)); hm = Math.max(hm, va * va);
}
check(he / hm < 1e-3, `homophonic: phi_A(dot)^2 = phi_B(dot)^2 after decoding (rel. err ${(he / hm).toExponential(2)})`);
process.exit(fails ? 1 : 0);
