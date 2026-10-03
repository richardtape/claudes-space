// node tests/audio_levels.js -- synthesise strikes the way the page does and report levels.
const D = require("../page/core.js");
const data = require("../page_data.json");
function pairFrom(d, modes, f1) {
  const mesh = D.baseMesh(d.n), per = d.tiles * mesh.nl, m = d.m;
  const freqs = d.lam.map(l => f1 * Math.sqrt(l / d.lam[0]));
  const H = freqs.map(f => Math.sqrt(f1 / f) / (1 + Math.pow(f / 700, 2)));
  const taus = freqs.map(f => 1.6 * Math.pow(f1 / f, 0.6));
  const sums = [];
  for (let i = 0; i < per; i += 3) { let s = 0; for (let k = 0; k < m; k++) { const v = modes[k * per + i]; s += v * v * H[k]; } if (s > 0) sums.push(s); }
  sums.sort((a, b) => a - b);
  return { per, m, freqs, H, taus, gain: 1.4 / sums[Math.floor(sums.length * 0.9)] };
}
function report(name, d, modes, f1) {
  const p = pairFrom(d, modes, f1), peaks = [], rms = [], low = [];
  for (let trial = 0; trial < 60; trial++) {
    const i = Math.floor(Math.random() * p.per);
    const amps = []; let e = 0;
    for (let k = 0; k < p.m; k++) { const v = modes[k * p.per + i]; amps.push(v * v * p.H[k] * p.gain); e += v * v; }
    if (e < 1e-3) continue;   // rim
    const s = D.synth(p.freqs, amps, p.taus, 44100, 2.8);
    let pk = 0, sq = 0; for (let j = 0; j < s.length; j++) { pk = Math.max(pk, Math.abs(s[j])); if (j < 22050) sq += s[j] * s[j]; }
    peaks.push(pk); rms.push(Math.sqrt(sq / 22050));
    let lo = 0, all = 0; amps.forEach((a, k) => { all += a * a; if (p.freqs[k] < 250) lo += a * a; }); low.push(lo / all);
  }
  const q = (a, f) => a.slice().sort((x, y) => x - y)[Math.floor(f * (a.length - 1))].toFixed(3);
  console.log(`${name}: peak median ${q(peaks, .5)} p95 ${q(peaks, .95)} max ${q(peaks, 1)}; rms(first 0.5 s) median ${q(rms, .5)}; energy below 250 Hz median ${q(low, .5)}`);
}
const g = data.gww, mesh = D.baseMesh(g.n);
const A = D.decodeModes(g.modes, g.scales, g.m, g.tiles, mesh.nl);
report("GWW drum A", g, A, 110);
const h = data.homo, mh = D.baseMesh(h.n);
report("21-tile drum A", h, D.decodeModes(h.modesA, h.scalesA, h.m, h.tiles, mh.nl), 98);
