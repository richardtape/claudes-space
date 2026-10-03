(function () {
  "use strict";
  const D = window.Drums;
  const $ = id => document.getElementById(id);
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const DPR = () => Math.min(window.devicePixelRatio || 1, 2);

  // ------------------------------------------------------------------ palette
  const PAL = {};
  let LUT = null, LUT_NODAL = null;
  function rgb(s) {
    s = s.trim();
    if (s[0] === "#") {
      if (s.length === 4) s = "#" + s[1] + s[1] + s[2] + s[2] + s[3] + s[3];
      return [parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16), parseInt(s.slice(5, 7), 16)];
    }
    const m = s.match(/[\d.]+/g);
    return m ? m.slice(0, 3).map(Number) : [128, 128, 128];
  }
  const css = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  function readPalette() {
    const cs = getComputedStyle(document.documentElement);
    for (const k of ["skin", "copper", "verdigris", "rim", "ink", "muted", "rule", "faint", "hall", "panel"])
      PAL[k] = rgb(cs.getPropertyValue("--" + k));
    const mix = (a, b, t) => [0, 1, 2].map(i => Math.round(a[i] + (b[i] - a[i]) * t));
    const pack = c => (255 << 24) | (c[2] << 16) | (c[1] << 8) | c[0];
    LUT = new Uint32Array(1024);
    LUT_NODAL = new Uint32Array(1024);
    for (let i = 0; i < 1024; i++) {
      const t = i / 511.5 - 1, s = Math.pow(Math.min(1, Math.abs(t)), 0.62);
      const c = mix(PAL.skin, t >= 0 ? PAL.copper : PAL.verdigris, s);
      LUT[i] = pack(c) >>> 0;
      const near = Math.abs(t) < 0.045 ? 0.8 * (1 - Math.abs(t) / 0.045) : 0;
      LUT_NODAL[i] = pack(mix(c, PAL.rim, near)) >>> 0;
    }
  }

  // ------------------------------------------------------------------ pairs
  function makePair(cfg) {
    const mesh = D.baseMesh(cfg.n), nl = mesh.nl, per = cfg.tiles * nl, m = cfg.m;
    const lam = cfg.lam, f1 = cfg.f1;
    const freqs = lam.map(l => f1 * Math.sqrt(l / lam[0]));
    const H = freqs.map(f => Math.sqrt(f1 / f) / (1 + Math.pow(f / 700, 2)));   // tilt toward low notes, soft mallet
    const taus = freqs.map(f => 1.6 * Math.pow(f1 / f, 0.6));              // audio decay (s)
    const wv = lam.map(l => 2 * Math.PI * 0.5 * Math.sqrt(l / lam[0]));    // slowed-down visual frequencies
    const tv = lam.map(l => 3.2 * Math.pow(lam[0] / l, 0.35));
    const pair = { ...cfg, mesh, nl, per, freqs, H, taus, wv, tv };
    // Full scale for the bars and the sound: a high percentile of max_k phi_k(x)^2 H_k over nodes.
    const peaks = [], sums = [];
    for (let i = 0; i < per; i += 3) {
      let mx = 0, sum = 0;
      for (let k = 0; k < m; k++) { const v = cfg.modesA[k * per + i]; const a = v * v * H[k]; if (a > mx) mx = a; sum += a; }
      if (sum > 0) { peaks.push(mx); sums.push(sum); }
    }
    peaks.sort((a, b) => a - b); sums.sort((a, b) => a - b);
    pair.barScale = peaks[Math.floor(peaks.length * 0.8)];
    pair.gain = 1.4 / sums[Math.floor(sums.length * 0.9)];
    return pair;
  }
  function phiAt(pair, modes, where) {
    // where: {offs:[o0,o1,o2], w:[w0,w1,w2]} in per-mode offsets
    const out = new Float32Array(pair.m), per = pair.per;
    for (let k = 0; k < pair.m; k++) {
      const b = k * per;
      out[k] = where.w[0] * modes[b + where.offs[0]] + where.w[1] * modes[b + where.offs[1]] + where.w[2] * modes[b + where.offs[2]];
    }
    return out;
  }
  function nodeWhere(pair, tile, node) { const o = tile * pair.nl + node; return { offs: [o, o, o], w: [1, 0, 0] }; }

  const G = DATA.gww;
  const gMesh = D.baseMesh(G.n);
  const gA = D.decodeModes(G.modes, G.scales, G.m, G.tiles, gMesh.nl);
  const gB = D.fixSign(D.transplantGWW(gA, G.T3, G.m, G.tiles, gMesh.nl, G.triMode), G.m, G.tiles * gMesh.nl);
  const PG = makePair({ tri: G.tri, n: G.n, tiles: G.tiles, m: G.m, lam: G.lam, f1: 110, modesA: gA, modesB: gB,
                        placeA: G.A.place, placeB: G.B.place, outlineA: G.A.outline, outlineB: G.B.outline });
  const Hd = DATA.homo;
  const hMesh = D.baseMesh(Hd.n);
  const PH = makePair({ tri: Hd.tri, n: Hd.n, tiles: Hd.tiles, m: Hd.m, lam: Hd.lam, f1: 98,
                        modesA: D.decodeModes(Hd.modesA, Hd.scalesA, Hd.m, Hd.tiles, hMesh.nl),
                        modesB: D.decodeModes(Hd.modesB, Hd.scalesB, Hd.m, Hd.tiles, hMesh.nl),
                        placeA: Hd.A.place, placeB: Hd.B.place, outlineA: Hd.A.outline, outlineB: Hd.B.outline });

  // ------------------------------------------------------------------ skin renderer
  function bbox(pts) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
    return { x0, y0, x1, y1, w: x1 - x0, h: y1 - y0 };
  }

  class SkinView {
    constructor(canvas) { this.canvas = canvas; this.ctx = canvas.getContext("2d"); this.marks = []; }
    // places: affine placements per tile; outline: [[x,y]...]; frame: {W, H, scale, x0, y1, ox, oy}
    setGeometry(pair, places, outline, frame) {
      this.pair = pair; this.places = places; this.outline = outline; this.frame = frame;
      const { W, H } = frame;
      this.canvas.width = W; this.canvas.height = H;
      this.img = this.ctx.createImageData(W, H);
      this.buf = new Uint32Array(this.img.data.buffer);
      this.build();
    }
    toPx(x, y) { const f = this.frame; return [f.ox + (x - f.x0) * f.scale, f.oy + (f.y1 - y) * f.scale]; }
    build() {
      const { pair, places } = this, mesh = pair.mesh, nl = pair.nl, W = this.frame.W, H = this.frame.H;
      const lxy = D.localXY(mesh, pair.tri);
      const nt = places.length, X = new Float64Array(nt * nl), Y = new Float64Array(nt * nl);
      for (let p = 0; p < nt; p++)
        for (let n = 0; n < nl; n++) {
          const [x, y] = D.apply(places[p], lxy[2 * n], lxy[2 * n + 1]);
          const [px, py] = this.toPx(x, y);
          X[p * nl + n] = px; Y[p * nl + n] = py;
        }
      const owner = new Int32Array(W * H).fill(-1);
      const pix = [], o0 = [], o1 = [], o2 = [], w0 = [], w1 = [];
      const t = mesh.tris;
      for (let p = 0; p < nt; p++)
        for (let e = 0; e < t.length; e += 3) {
          const a = p * nl + t[e], b = p * nl + t[e + 1], c = p * nl + t[e + 2];
          const ax = X[a], ay = Y[a], bx = X[b], by = Y[b], cx = X[c], cy = Y[c];
          const det = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
          if (Math.abs(det) < 1e-12) continue;
          const xa = Math.max(0, Math.floor(Math.min(ax, bx, cx))), xb = Math.min(W - 1, Math.ceil(Math.max(ax, bx, cx)));
          const ya = Math.max(0, Math.floor(Math.min(ay, by, cy))), yb = Math.min(H - 1, Math.ceil(Math.max(ay, by, cy)));
          for (let y = ya; y <= yb; y++)
            for (let x = xa; x <= xb; x++) {
              const px = x + 0.5, py = y + 0.5;
              const l1 = ((px - ax) * (cy - ay) - (py - ay) * (cx - ax)) / det;
              const l2 = ((bx - ax) * (py - ay) - (by - ay) * (px - ax)) / det;
              const l0 = 1 - l1 - l2;
              if (l0 < -1e-6 || l1 < -1e-6 || l2 < -1e-6) continue;
              const idx = y * W + x;
              if (owner[idx] >= 0) continue;
              owner[idx] = pix.length;
              pix.push(idx); o0.push(a); o1.push(b); o2.push(c); w0.push(l0); w1.push(l1);
            }
        }
      this.owner = owner;
      this.pix = Int32Array.from(pix); this.o0 = Int32Array.from(o0); this.o1 = Int32Array.from(o1); this.o2 = Int32Array.from(o2);
      this.w0 = Float32Array.from(w0); this.w1 = Float32Array.from(w1);
    }
    draw(U, norm, nodal) {
      if (!this.pix) return;
      const buf = this.buf, pix = this.pix, n = pix.length;
      buf.fill(0);
      const inv = norm > 0 ? 511.5 / norm : 0;
      for (let i = 0; i < n; i++) {
        const w0 = this.w0[i], w1 = this.w1[i];
        let v = 0, cross = false;
        if (U) {
          const a = U[this.o0[i]], b = U[this.o1[i]], c = U[this.o2[i]];
          v = w0 * a + w1 * b + (1 - w0 - w1) * c;
          // a nodal line passes through this mesh triangle only if its corners disagree in sign
          cross = nodal && Math.min(a, b, c) < 0 && Math.max(a, b, c) > 0;
        }
        let j = Math.round(v * inv + 511.5);
        j = j < 0 ? 0 : j > 1023 ? 1023 : j;
        buf[pix[i]] = (cross ? LUT_NODAL : LUT)[j];
      }
      const ctx = this.ctx;
      ctx.putImageData(this.img, 0, 0);
      ctx.beginPath();
      this.outline.forEach(([x, y], i) => { const [px, py] = this.toPx(x, y); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
      ctx.closePath();
      ctx.lineJoin = "round";
      ctx.lineWidth = 1.6 * this.frame.dpr;
      ctx.strokeStyle = css(PAL.rim);
      ctx.stroke();
      for (const mk of this.marks) {
        const [px, py] = this.toPx(mk[0], mk[1]);
        ctx.beginPath(); ctx.arc(px, py, 4.5 * this.frame.dpr, 0, 2 * Math.PI);
        ctx.fillStyle = css(PAL.ink); ctx.fill();
        ctx.lineWidth = 2 * this.frame.dpr; ctx.strokeStyle = css(PAL.skin); ctx.stroke();
      }
    }
    pick(ev) {
      const r = this.canvas.getBoundingClientRect();
      const x = Math.floor((ev.clientX - r.left) / r.width * this.frame.W), y = Math.floor((ev.clientY - r.top) / r.height * this.frame.H);
      // search a small neighbourhood so taps right on the rim still count
      for (let rad = 0; rad <= 6; rad++)
        for (let dy = -rad; dy <= rad; dy++)
          for (let dx = -rad; dx <= rad; dx++) {
            const xx = x + dx, yy = y + dy;
            if (xx < 0 || yy < 0 || xx >= this.frame.W || yy >= this.frame.H) continue;
            const i = this.owner[yy * this.frame.W + xx];
            if (i >= 0) {
              const w0 = this.w0[i], w1 = this.w1[i];
              return { offs: [this.o0[i], this.o1[i], this.o2[i]], w: [w0, w1, 1 - w0 - w1] };
            }
          }
      return null;
    }
  }

  // Lay out two views of a pair at a common scale, both centred in equal-width canvases.
  function layoutDuo(viewA, viewB, pair, maxW = 760) {
    const cssW = viewA.canvas.getBoundingClientRect().width || viewA.canvas.parentElement.getBoundingClientRect().width || 400;
    const dpr = DPR(), W = Math.max(120, Math.min(Math.round(cssW * dpr), maxW));
    const bA = bbox(pair.outlineA), bB = bbox(pair.outlineB);
    const pad = 0.06 * W, bw = Math.max(bA.w, bB.w), bh = Math.max(bA.h, bB.h);
    const scale = (W - 2 * pad) / bw, H = Math.round(bh * scale + 2 * pad);
    for (const [v, b, place, out] of [[viewA, bA, pair.placeA, pair.outlineA], [viewB, bB, pair.placeB, pair.outlineB]]) {
      const ox = (W - b.w * scale) / 2, oy = H - pad - b.h * scale;   // bottom-aligned
      v.setGeometry(pair, place, out, { W, H, scale, x0: b.x0, y1: b.y1, ox, oy, dpr: W / cssW });
    }
  }

  // ------------------------------------------------------------------ animation loop
  const tasks = new Set();
  let rafOn = false;
  function loop(now) {
    for (const t of [...tasks]) if (!t(now)) tasks.delete(t);
    if (tasks.size) requestAnimationFrame(loop); else rafOn = false;
  }
  function addTask(fn) { tasks.add(fn); if (!rafOn) { rafOn = true; requestAnimationFrame(loop); } }

  // ------------------------------------------------------------------ audio
  let actx = null, master = null, soundOn = true;
  function audio() {
    if (!actx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      actx = new AC();
      const comp = actx.createDynamicsCompressor();
      comp.threshold.value = -8; comp.knee.value = 8; comp.ratio.value = 6; comp.attack.value = 0.002; comp.release.value = 0.2;
      master = actx.createGain(); master.gain.value = 0.9;
      master.connect(comp); comp.connect(actx.destination);
    }
    if (actx.state === "suspended") actx.resume();
    return actx;
  }
  function play(samples, delay = 0) {
    if (!soundOn) return;
    const ac = audio();
    if (!ac) return;
    const buf = ac.createBuffer(1, samples.length, ac.sampleRate);
    buf.copyToChannel(samples, 0);
    const src = ac.createBufferSource();
    src.buffer = buf; src.connect(master);
    src.start(ac.currentTime + 0.02 + delay);
  }
  function strikeSound(pair, phi) {
    const ac = audio();
    const sr = ac ? ac.sampleRate : 44100;
    const amps = Array.from(phi, (v, k) => v * v * pair.H[k] * pair.gain);
    return D.synth(pair.freqs, amps, pair.taus, sr, 2.8);
  }

  // ------------------------------------------------------------------ note ladder
  class Ladder {
    constructor(canvas, pair) { this.canvas = canvas; this.ctx = canvas.getContext("2d"); this.pair = pair; this.sides = [null, null]; }
    resize() {
      const cssW = this.canvas.getBoundingClientRect().width || 600, dpr = DPR();
      const cssH = cssW < 520 ? 150 : 180;
      this.canvas.style.height = cssH + "px";
      this.canvas.width = Math.round(cssW * dpr); this.canvas.height = Math.round(cssH * dpr);
      this.dpr = dpr; this.draw(performance.now());
    }
    set(side, phi, t0, still = false) {
      const p = this.pair;
      if (!still) this.sides.forEach(s => { if (s && s.still) { s.still = false; s.t0 = performance.now(); } });
      this.sides[side] = { amp: Array.from(phi, (v, k) => v * v * p.H[k] / p.barScale), t0, still };
      if (still) { this.draw(performance.now()); return; }
      if (this.active) return;
      this.active = true;
      addTask(now => {
        this.draw(now);
        const keep = now - Math.max(...this.sides.map(s => (s ? s.t0 : 0))) < 5000;
        if (!keep) this.active = false;
        return keep;
      });
    }
    draw(now) {
      const { ctx, pair } = this, W = this.canvas.width, Hh = this.canvas.height, d = this.dpr;
      ctx.clearRect(0, 0, W, Hh);
      const fmin = pair.freqs[0] / 1.12, fmax = pair.freqs[pair.m - 1] * 1.04;
      const padL = 6 * d, padR = 6 * d;
      const X = f => padL + (Math.log(f / fmin) / Math.log(fmax / fmin)) * (W - padL - padR);
      const mid = Hh / 2, hb = mid - 16 * d;
      // octave lines on the fundamental's pitch class
      ctx.font = `${12 * d}px ${getComputedStyle(document.body).fontFamily}`;
      ctx.textBaseline = "top";
      for (let f = pair.f1; f <= fmax; f *= 2) {
        const x = Math.round(X(f)) + 0.5;
        ctx.strokeStyle = css(PAL.rule); ctx.lineWidth = d;
        ctx.beginPath(); ctx.moveTo(x, 2 * d); ctx.lineTo(x, Hh - 2 * d); ctx.stroke();
        const nn = D.noteName(f), label = `${nn.name}  ${Math.round(f)} Hz`;
        ctx.fillStyle = css(PAL.muted);
        if (x + 4 * d + ctx.measureText(label).width < W) ctx.fillText(label, x + 4 * d, 2 * d);
      }
      // the shared notes
      ctx.strokeStyle = css(PAL.muted); ctx.lineWidth = Math.max(1, d);
      ctx.beginPath();
      for (const f of pair.freqs) { const x = X(f); ctx.moveTo(x, mid - 4 * d); ctx.lineTo(x, mid + 4 * d); }
      ctx.stroke();
      ctx.strokeStyle = css(PAL.rim); ctx.beginPath(); ctx.moveTo(padL, mid); ctx.lineTo(W - padR, mid); ctx.stroke();
      // bars
      ctx.fillStyle = css(PAL.ink, 0.82);
      const bw = Math.max(1.5 * d, 2);
      this.sides.forEach((s, side) => {
        if (!s) return;
        if (!s.still && now < s.t0) return;
        const t = s.still ? 0 : Math.max(0, (now - s.t0) / 1000);
        for (let k = 0; k < pair.m; k++) {
          const h = Math.min(1, s.amp[k] * Math.exp(-t / pair.taus[k])) * hb;
          if (h < 0.5) continue;
          const x = X(pair.freqs[k]) - bw / 2;
          if (side === 0) ctx.fillRect(x, mid - 5 * d - h, bw, h); else ctx.fillRect(x, mid + 5 * d, bw, h);
        }
      });
    }
  }
  function mismatch(phiA, phiB, pair) {
    let num = 0, den = 0;
    for (let k = 0; k < pair.m; k++) { const a = phiA[k] ** 2 * pair.H[k], b = phiB[k] ** 2 * pair.H[k]; num += Math.abs(a - b); den += a + b; }
    return den ? num / den : 0;
  }

  // ------------------------------------------------------------------ a playable duo
  function playableDuo(pair, canvA, canvB, ladderCanvas, opts = {}) {
    const views = [new SkinView(canvA), new SkinView(canvB)];
    const modes = [pair.modesA, pair.modesB];
    const ladder = new Ladder(ladderCanvas, pair);
    const state = [null, null];
    const lastPhi = [null, null];
    const mVis = Math.min(pair.m, 120);
    const U = [new Float32Array(pair.per), new Float32Array(pair.per)];
    if (opts.marks) { views[0].marks = [opts.marks[0]]; views[1].marks = [opts.marks[1]]; }

    function frame(side, now) {
      const s = state[side], v = views[side], u = U[side];
      if (!s) { v.draw(null, 1); return false; }
      const t = (now - s.t0) / 1000;
      if (t < 0) { return true; }
      u.fill(0);
      const md = modes[side], per = pair.per;
      for (let k = 0; k < mVis; k++) {
        const c = s.coef[k] * Math.sin(pair.wv[k] * t) * Math.exp(-t / pair.tv[k]);
        if (Math.abs(c) < 1e-6 * s.cmax) continue;
        const b = k * per;
        for (let i = 0; i < per; i++) u[i] += c * md[b + i];
      }
      let mx = 0;
      for (let i = 0; i < per; i++) mx = Math.max(mx, Math.abs(u[i]));
      if (t < 0.45 || !s.norm) s.norm = Math.max(s.norm, mx);
      v.draw(u, 0.7 * s.norm || 1);
      if (t > 9) { state[side] = null; v.draw(null, 1); return false; }
      return true;
    }
    function strike(side, phi, delay = 0, silent = false, still = false) {
      const t0 = performance.now() + delay * 1000;
      const coef = new Float32Array(mVis);
      let cmax = 0;
      for (let k = 0; k < mVis; k++) { coef[k] = phi[k] * pair.H[k] / pair.wv[k]; cmax = Math.max(cmax, Math.abs(coef[k])); }
      state[side] = { t0, coef, cmax, norm: 0 };
      lastPhi[side] = phi;
      ladder.set(side, phi, t0, still || reduceMotion);
      if (still) {            // resting picture: one frame of the strike and full-height bars, nothing moving
        frame(side, t0 + 900);
        state[side] = null;
      } else {
        if (!silent) play(strikeSound(pair, phi), delay);
        if (reduceMotion) setTimeout(() => { const s = state[side]; if (s) frame(side, s.t0 + 380); }, delay * 1000);
        else addTask(now => frame(side, now));
      }
      if (opts.onStrike) opts.onStrike(side, lastPhi, still);
    }
    views.forEach((v, side) => {
      v.canvas.addEventListener("pointerdown", ev => {
        const w = v.pick(ev);
        if (!w) return;
        ev.preventDefault();
        strike(side, phiAt(pair, modes[side], w));
      });
    });
    function layout() { layoutDuo(views[0], views[1], pair); views.forEach((v, i) => v.draw(null, 1)); ladder.resize(); }
    function randomWhere(side) {
      const v = views[side];
      for (let tries = 0; tries < 200; tries++) {
        const i = Math.floor(Math.random() * v.pix.length), w0 = v.w0[i], w1 = v.w1[i];
        const w = { offs: [v.o0[i], v.o1[i], v.o2[i]], w: [w0, w1, 1 - w0 - w1] };
        const phi = phiAt(pair, modes[side], w);
        let e = 0; for (let k = 0; k < 8; k++) e += phi[k] * phi[k];
        if (e > 0.15) return w;          // not right at the rim
      }
      return null;
    }
    return { views, ladder, strike, layout, randomWhere, modes, lastPhi };
  }

  // ------------------------------------------------------------------ hero
  const hero = playableDuo(PG, $("heroA"), $("heroB"), $("heroLadder"), {
    onStrike(side, last, still) {
      if (!still && last[0] && last[1]) $("heroReadout").textContent = `The notes line up as always. Their strengths differ by ${Math.round(100 * mismatch(last[0], last[1], PG))}% between your last strikes on A and B.`;
    }
  });
  $("heroBoth").addEventListener("click", () => {
    const wa = hero.randomWhere(0), wb = hero.randomWhere(1);
    if (wa) hero.strike(0, phiAt(PG, PG.modesA, wa));
    if (wb) hero.strike(1, phiAt(PG, PG.modesB, wb), 1.3);
  });
  $("soundToggle").addEventListener("click", ev => {
    soundOn = !soundOn;
    ev.currentTarget.setAttribute("aria-pressed", String(soundOn));
    ev.currentTarget.textContent = soundOn ? "Sound on" : "Sound off";
  });

  // ------------------------------------------------------------------ mode explorer
  const modeViews = [new SkinView($("modeA")), new SkinView($("modeB"))];
  let modeK = 0, modeVisible = false, modeTask = null;
  const triSet = new Set(G.triMode);
  function modeMax(md, k) { let mx = 0; for (let i = 0; i < PG.per; i++) mx = Math.max(mx, Math.abs(md[k * PG.per + i])); return mx; }
  function drawModes(phase = 1) {
    [PG.modesA, PG.modesB].forEach((md, side) => {
      const k = modeK, sl = md.subarray(k * PG.per, (k + 1) * PG.per);
      const u = new Float32Array(PG.per);
      for (let i = 0; i < PG.per; i++) u[i] = sl[i] * phase;
      modeViews[side].draw(u, modeMax(md, k), true);
    });
  }
  function setMode(k) {
    modeK = Math.max(0, Math.min(PG.m - 1, k));
    $("modeRange").value = String(modeK + 1);
    const f = PG.freqs[modeK], nn = D.noteName(f);
    const cents = nn.cents === 0 ? "in tune" : `${nn.cents > 0 ? "+" : "−"}${Math.abs(nn.cents)} cents`;
    $("modeFacts").innerHTML =
      `<div><span>Mode</span> <b>${modeK + 1}</b></div>` +
      `<div><span>λ</span> <b>${PG.lam[modeK].toFixed(3)}</b></div>` +
      `<div><span>Frequency</span> <b>${f.toFixed(1)} Hz</b></div>` +
      `<div><span>Nearest note</span> <b>${nn.name}</b>, ${cents}</div>` +
      (triSet.has(modeK) ? `<div class="badge">A half-square note, the same on every triangle</div>` : "");
    drawModes();
    drawEquation();
  }
  $("modeRange").addEventListener("input", e => setMode(+e.target.value - 1));
  $("modePrev").addEventListener("click", () => setMode(modeK - 1));
  $("modeNext").addEventListener("click", () => setMode(modeK + 1));
  $("modePlay").addEventListener("click", () => {
    const ac = audio(), sr = ac ? ac.sampleRate : 44100;
    play(D.synth([PG.freqs[modeK]], [0.35], [1.4 * Math.pow(PG.f1 / PG.freqs[modeK], 0.4)], sr, 2.6));
  });
  if (!reduceMotion && "IntersectionObserver" in window) {
    new IntersectionObserver(es => {
      modeVisible = es[0].isIntersecting;
      if (modeVisible && !modeTask) {
        const t0 = performance.now();
        modeTask = now => { if (!modeVisible) { modeTask = null; drawModes(); return false; } drawModes(Math.cos((now - t0) / 1000 * 2 * Math.PI / 2.6)); return true; };
        addTask(modeTask);
      }
    }).observe($("modeA"));
  }

  // ------------------------------------------------------------------ mode 9 figure
  const triViews = [new SkinView($("triA")), new SkinView($("triB"))];
  function drawTri() {
    const k = G.triMode[0];
    [PG.modesA, PG.modesB].forEach((md, side) => triViews[side].draw(md.subarray(k * PG.per, (k + 1) * PG.per), modeMax(md, k), true));
  }

  // ------------------------------------------------------------------ Fano plane and construction
  const VEC = [[0, 0, 1], [0, 1, 0], [0, 1, 1], [1, 0, 0], [1, 0, 1], [1, 1, 0], [1, 1, 1]];
  const onLine = (j, i) => (VEC[j][0] * VEC[i][0] + VEC[j][1] * VEC[i][1] + VEC[j][2] * VEC[i][2]) % 2 === 0;
  const LINES = [0, 1, 2, 3, 4, 5, 6].map(j => [0, 1, 2, 3, 4, 5, 6].filter(i => onLine(j, i)));
  const lineName = j => LINES[j].map(i => i + 1).join("");
  const s3 = Math.sqrt(3) / 2;
  const POS = { 3: [0, -100], 1: [-100 * s3, 50], 0: [100 * s3, 50], 5: [-50 * s3, -25], 2: [0, 50], 4: [50 * s3, -25], 6: [0, 0] };
  const SVGNS = "http://www.w3.org/2000/svg";
  const el = (name, attrs = {}, parent) => { const e = document.createElementNS(SVGNS, name); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };

  function drawTiles(svg, places, tri, labels, cls, opts = {}) {
    svg.textContent = "";
    const verts = D.tileVerts(places, tri);
    const all = verts.flat(), b = bbox(all), pad = Math.max(b.w, b.h) * 0.04;
    const S = 100 / (Math.max(b.w, b.h) + 2 * pad);
    const tx = (x, y) => [((x - b.x0 + pad) * S).toFixed(2), ((b.y1 - y + pad) * S).toFixed(2)];
    svg.setAttribute("viewBox", `0 0 ${((b.w + 2 * pad) * S).toFixed(2)} ${((b.h + 2 * pad) * S).toFixed(2)}`);
    const polys = verts.map((T, i) => {
      const poly = el("polygon", { points: T.map(([x, y]) => tx(x, y).join(",")).join(" "), class: "tile", "data-i": i }, svg);
      if (opts.fill) poly.style.fill = opts.fill(i);
      return poly;
    });
    if (labels) verts.forEach((T, i) => {
      const cx = (T[0][0] + T[1][0] + T[2][0]) / 3, cy = (T[0][1] + T[1][1] + T[2][1]) / 3;
      const [x, y] = tx(cx, cy);
      const t = el("text", { x, y, class: "tlabel" + (labels[i].length > 1 ? " small" : "") }, svg);
      t.textContent = labels[i];
    });
    return polys;
  }

  const buildPolysA = drawTiles($("buildA"), G.A.place, G.tri, [0, 1, 2, 3, 4, 5, 6].map(i => String(i + 1)));
  const buildPolysB = drawTiles($("buildB"), G.B.place, G.tri, [0, 1, 2, 3, 4, 5, 6].map(lineName));
  const fano = $("fano");
  const fanoLines = [], fanoPts = [];
  (function drawFano() {
    for (let j = 0; j < 7; j++) {
      const pts = LINES[j];
      let shape, hit;
      if (pts.every(i => [5, 2, 4].includes(i))) {
        shape = el("circle", { cx: 0, cy: 0, r: 50, class: "ln" }, fano);
        hit = el("circle", { cx: 0, cy: 0, r: 50, class: "hit" }, fano);
      } else {
        // the two points farthest apart are the ends of the segment
        let best = null;
        for (const a of pts) for (const c of pts) { const d = Math.hypot(POS[a][0] - POS[c][0], POS[a][1] - POS[c][1]); if (!best || d > best[0]) best = [d, a, c]; }
        const [, a, c] = best;
        shape = el("line", { x1: POS[a][0], y1: POS[a][1], x2: POS[c][0], y2: POS[c][1], class: "ln" }, fano);
        hit = el("line", { x1: POS[a][0], y1: POS[a][1], x2: POS[c][0], y2: POS[c][1], class: "hit" }, fano);
      }
      hit.setAttribute("tabindex", "0");
      hit.setAttribute("aria-label", `Line through points ${LINES[j].map(i => i + 1).join(", ")}`);
      fanoLines.push(shape);
      hit.addEventListener("pointerenter", () => highlight({ line: j }));
      hit.addEventListener("focus", () => highlight({ line: j }));
      hit.addEventListener("click", () => { highlight({ line: j }); selectLine(j); });
    }
    for (let i = 0; i < 7; i++) {
      const c = el("circle", { cx: POS[i][0], cy: POS[i][1], r: 11, class: "pt", tabindex: "0", "aria-label": `Point ${i + 1}` }, fano);
      const t = el("text", { x: POS[i][0], y: POS[i][1] + 0.5 }, fano);
      t.textContent = String(i + 1);
      fanoPts.push(c);
      c.addEventListener("pointerenter", () => highlight({ point: i }));
      c.addEventListener("focus", () => highlight({ point: i }));
    }
    fano.addEventListener("pointerleave", () => highlight({ line: selectedLine }));
  })();
  function highlight(h) {
    const hotPts = new Set(), warmPts = new Set(), hotLines = new Set(), warmLines = new Set();
    if (h.point !== undefined) {
      hotPts.add(h.point);
      LINES.forEach((pts, j) => { if (pts.includes(h.point)) warmLines.add(j); });
    }
    if (h.line !== undefined) {
      hotLines.add(h.line);
      LINES[h.line].forEach(i => warmPts.add(i));
    }
    fanoPts.forEach((c, i) => c.classList.toggle("hot", hotPts.has(i) || warmPts.has(i)));
    fanoLines.forEach((l, j) => l.classList.toggle("hot", hotLines.has(j)));
    buildPolysA.forEach((p, i) => { p.classList.toggle("hot", hotPts.has(i)); p.classList.toggle("warm", warmPts.has(i)); });
    buildPolysB.forEach((p, j) => { p.classList.toggle("hot", hotLines.has(j)); p.classList.toggle("warm", warmLines.has(j)); });
  }
  buildPolysA.forEach((p, i) => p.addEventListener("pointerenter", () => highlight({ point: i })));
  buildPolysB.forEach((p, j) => {
    p.addEventListener("pointerenter", () => highlight({ line: j }));
    p.addEventListener("click", () => selectLine(j));
    p.style.cursor = "pointer";
  });
  $("buildA").addEventListener("pointerleave", () => highlight({ line: selectedLine }));
  $("buildB").addEventListener("pointerleave", () => highlight({ line: selectedLine }));

  // equation: B's triangle j as a signed sum of A's triangles
  let selectedLine = 0;
  const pick = $("linePick");
  for (let j = 0; j < 7; j++) {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = `Triangle ${lineName(j)}`; b.setAttribute("aria-pressed", String(j === 0));
    b.addEventListener("click", () => selectLine(j));
    pick.appendChild(b);
  }
  function selectLine(j) {
    selectedLine = j;
    [...pick.children].forEach((b, i) => b.setAttribute("aria-pressed", String(i === j)));
    highlight({ line: j });
    drawEquation();
  }
  const eqViews = [];
  const single = [[1, 0, 0, 0, 1, 0]];
  const triOutline = G.tri.map(v => [v[0], v[1]]);
  function eqView() {
    const c = document.createElement("canvas");
    const v = new SkinView(c);
    const pairOne = { ...PG, tiles: 1, per: PG.nl };
    const cssW = 112, dpr = DPR(), W = Math.round(cssW * dpr);
    const b = bbox(triOutline), pad = 0.06 * W, scale = (W - 2 * pad) / Math.max(b.w, b.h), H = Math.round(b.h * scale + 2 * pad);
    v.setGeometry(pairOne, single, triOutline, { W, H, scale, x0: b.x0, y1: b.y1, ox: (W - b.w * scale) / 2, oy: pad, dpr });
    return v;
  }
  function drawEquation() {
    const box = $("equation"), k = modeK, j = selectedLine, nl = PG.nl, per = PG.per;
    const row = G.T3[j];
    const terms = [];
    for (let i = 0; i < 7; i++) if (row[i]) terms.push([row[i], i]);
    const pieces = terms.map(([s, i]) => PG.modesA.subarray(k * per + i * nl, k * per + (i + 1) * nl));
    const sum = new Float32Array(nl);
    terms.forEach(([s], t) => { for (let n = 0; n < nl; n++) sum[n] += s * pieces[t][n]; });
    let mx = 0;
    for (const p of [...pieces, sum]) for (let n = 0; n < nl; n++) mx = Math.max(mx, Math.abs(p[n]));
    while (eqViews.length < 4) eqViews.push(eqView());
    box.textContent = "";
    const term = (view, vals, label) => {
      view.draw(vals, mx, true);
      const d = document.createElement("div"); d.className = "term";
      d.appendChild(view.canvas);
      const s = document.createElement("span"); s.textContent = label; d.appendChild(s);
      return d;
    };
    const op = txt => { const s = document.createElement("span"); s.className = "op"; s.textContent = txt; return s; };
    terms.forEach(([s, i], t) => {
      if (t > 0 || s < 0) box.appendChild(op(s > 0 ? "+" : "−"));
      box.appendChild(term(eqViews[t], pieces[t], `A, triangle ${i + 1}`));
    });
    box.appendChild(op("="));
    box.appendChild(term(eqViews[3], sum, `B, triangle ${lineName(j)}`));
    $("eqCaption").textContent = `Mode ${k + 1}. Each picture is one triangle drawn in the same position, so the pieces add like numbers. The sum is drum B's mode on triangle ${lineName(j)}, up to an overall size. Change the mode above and the sum still works.`;
  }

  // ------------------------------------------------------------------ pretenders
  (function pretenders() {
    const P = DATA.pretender;
    const drums = [["7\u2083 A", G.A.place, G.tri], ["7\u2083 B", G.B.place, G.tri], ["7\u2082", P.A.place, P.tri]];
    const q = $("quartet");
    let span = 0;
    drums.forEach(([, pl, tri]) => { const b = bbox(D.tileVerts(pl, tri).flat()); span = Math.max(span, b.w, b.h); });
    drums.forEach(([name, pl, tri]) => {
      const fig = document.createElement("div");
      const svg = document.createElementNS(SVGNS, "svg");
      svg.setAttribute("role", "img"); svg.setAttribute("aria-label", `Drum ${name}`);
      fig.appendChild(svg);
      const lab = document.createElement("div"); lab.className = "who"; lab.textContent = name; fig.appendChild(lab);
      q.appendChild(fig);
      const verts = D.tileVerts(pl, tri), b = bbox(verts.flat()), S = 100 / (span * 1.1);
      svg.setAttribute("viewBox", "0 0 100 100");
      const ox = (100 - b.w * S) / 2, oy = (100 - b.h * S) / 2;
      verts.forEach(T => el("polygon", { points: T.map(([x, y]) => `${(ox + (x - b.x0) * S).toFixed(2)},${(oy + (b.y1 - y) * S).toFixed(2)}`).join(" "), class: "tile" }, svg));
    });
    const chart = $("pretenderChart");
    const triLam = G.triMode.map(i => G.lam[i]);
    const isHalf = l => triLam.some(t => Math.abs(t - l) / l < 1e-6);
    const rows = [["7\u2083 A", G.lam], ["7\u2083 B", G.lam], ["7\u2082", P.lam]];
    const lam1 = G.lam[0], f = l => 110 * Math.sqrt(l / lam1), n = 40;
    const fmin = 100, fmax = Math.max(f(G.lam[n - 1]), f(P.lam[n - 1])) * 1.03;
    const x0 = 70, x1 = 990, X = v => x0 + Math.log(v / fmin) / Math.log(fmax / fmin) * (x1 - x0);
    for (let oct = 110; oct < fmax; oct *= 2) {
      el("line", { x1: X(oct), x2: X(oct), y1: 6, y2: 142, style: "stroke:var(--rule)", "stroke-width": 1 }, chart);
      const t = el("text", { x: X(oct) + 4, y: 162 }, chart); t.textContent = `${D.noteName(oct).name}  ${oct} Hz`;
      if (X(oct) + 70 > 1000) { t.setAttribute("x", X(oct) - 4); t.setAttribute("text-anchor", "end"); }
    }
    rows.forEach(([name, lam], r) => {
      const y = 22 + r * 44 + (r === 2 ? 8 : 0);
      const t = el("text", { x: 0, y: y + 5, class: "lab" }, chart); t.textContent = name;
      for (let k = 0; k < n; k++) {
        const half = isHalf(lam[k]);
        el("line", { x1: X(f(lam[k])), x2: X(f(lam[k])), y1: y - 13, y2: y + 13, style: `stroke:${half ? "var(--copper)" : "var(--ink)"}`, "stroke-width": half ? 2.4 : 1.4 }, chart);
      }
    });
  })();

  // ------------------------------------------------------------------ shape maps
  function triCheck(perms, tri) {
    const n = perms[0].length, place = D.unfold(perms, tri), V = D.tileVerts(place, tri);
    const eps = 1e-9;
    const overlap = (T1, T2) => {
      for (const T of [T1, T2]) for (let i = 0; i < 3; i++) {
        const e = [T[(i + 1) % 3][0] - T[i][0], T[(i + 1) % 3][1] - T[i][1]], nx = -e[1], ny = e[0], L = Math.hypot(nx, ny);
        const pa = T1.map(p => p[0] * nx + p[1] * ny), pb = T2.map(p => p[0] * nx + p[1] * ny);
        if (Math.max(...pa) <= Math.min(...pb) + eps * L || Math.max(...pb) <= Math.min(...pa) + eps * L) return false;
      }
      return true;
    };
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) if (overlap(V[i], V[j])) return { status: "overlap", V };
    const bnd = [];
    for (let p = 0; p < n; p++) for (let k = 0; k < 3; k++) if (perms[k][p] === p) bnd.push([V[p][(k + 1) % 3], V[p][(k + 2) % 3]]);
    for (let a = 0; a < bnd.length; a++) for (let b = a + 1; b < bnd.length; b++) {
      const [p0, p1] = bnd[a], [q0, q1] = bnd[b];
      const dx = p1[0] - p0[0], dy = p1[1] - p0[1], L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L;
      const off = q => (q[0] - p0[0]) * -uy + (q[1] - p0[1]) * ux;
      if (Math.abs(off(q0)) > eps || Math.abs(off(q1)) > eps) continue;
      const s0 = (q0[0] - p0[0]) * ux + (q0[1] - p0[1]) * uy, s1 = (q1[0] - p0[0]) * ux + (q1[1] - p0[1]) * uy;
      if (Math.min(Math.max(s0, s1), L) - Math.max(Math.min(s0, s1), 0) > eps) return { status: "slit", V };
    }
    return { status: "ok", V, bnd };
  }
  function boundaryLoop(perms, V) {
    const r7 = v => Math.round(v * 1e7) + 0;   // integer keys, so -0 and 0 agree
    const key = p => `${r7(p[0])},${r7(p[1])}`, pts = {}, out = {};
    for (let p = 0; p < V.length; p++) {
      const T = V[p], ccw = (T[1][0] - T[0][0]) * (T[2][1] - T[0][1]) - (T[1][1] - T[0][1]) * (T[2][0] - T[0][0]) > 0;
      for (let k = 0; k < 3; k++) if (perms[k][p] === p) {
        let a = T[(k + 1) % 3], b = T[(k + 2) % 3];
        if (!ccw) [a, b] = [b, a];
        pts[key(a)] = a; pts[key(b)] = b;
        (out[key(a)] = out[key(a)] || []).push(key(b));
      }
    }
    const start = Object.keys(out)[0], walk = [start];
    let cur = start, prev = null, guard = 0;
    while (guard++ < 1000) {
      const opts = out[cur];
      let nxt = opts[0];
      if (prev && opts.length > 1) {
        const c = pts[cur], pv = pts[prev], din = [c[0] - pv[0], c[1] - pv[1]];
        const turn = w => { const d = [pts[w][0] - c[0], pts[w][1] - c[1]]; return Math.atan2(din[0] * d[1] - din[1] * d[0], din[0] * d[0] + din[1] * d[1]); };
        nxt = opts.reduce((a, b) => (turn(b) < turn(a) ? b : a));
      }
      opts.splice(opts.indexOf(nxt), 1);
      prev = cur; cur = nxt;
      if (cur === start && !out[cur].length) break;
      walk.push(cur);
    }
    const W = walk.map(k => pts[k]), keep = [];
    for (let i = 0; i < W.length; i++) {
      const a = W[(i - 1 + W.length) % W.length], b = W[i], c = W[(i + 1) % W.length];
      const cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
      if (Math.abs(cr) > 1e-9) keep.push(b);
    }
    return keep;
  }
  function signature(P) {
    return P.map((b, i) => {
      const a = P[(i - 1 + P.length) % P.length], c = P[(i + 1) % P.length];
      const u = [a[0] - b[0], a[1] - b[1]], v = [c[0] - b[0], c[1] - b[1]];
      let ang = -Math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]);
      ang = ((ang % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      return [ang, Math.hypot(v[0], v[1])];
    });
  }
  function congruent(PA, PB) {
    const a = signature(PA), b = signature(PB), n = a.length;
    if (n !== b.length) return false;
    const m = a.map((_, i) => [a[n - 1 - i][0], a[(2 * n - 2 - i) % n][1]]);
    for (const S of [a, m]) for (let r = 0; r < n; r++) {
      let ok = true;
      for (let i = 0; i < n && ok; i++) ok = Math.abs(S[(i + r) % n][0] - b[i][0]) < 1e-7 && Math.abs(S[(i + r) % n][1] - b[i][1]) < 1e-7;
      if (ok) return true;
    }
    return false;
  }

  const SH = DATA.shapes, STEPS = SH.steps;
  const famHTML = fam => `7<sub>${"\u2081\u2082\u2083".indexOf(fam.name.slice(1)) + 1}</sub>`;
  const COLORS = { o: () => css(PAL.ink), c: () => css(PAL.copper), "1": () => css(PAL.muted, 0.45), s: () => css(PAL.rule), x: () => css(PAL.rule), p: () => css(PAL.ink, 0.6) };
  const mapCanv = [];
  let chosen = { fam: 1, a: 45, b: 90 };   // class 1 is 7_3; this triangle gives the half-square pair
  const famOrder = [2, 0, 1];   // 7_1, 7_2, 7_3 in the paper's order
  function corner(W) {
    const pad = 0.07 * W, side = W - 2 * pad, h = side * s3;
    return { C0: [W / 2, pad], C1: [pad, pad + h], C2: [W - pad, pad + h], H: Math.round(h + 2 * pad) };
  }
  function ternary(W, a, b) {  // a at V0, b at V1, degrees
    const { C0, C1, C2 } = corner(W), g = 180 - a - b;
    return [(a * C0[0] + b * C1[0] + g * C2[0]) / 180, (a * C0[1] + b * C1[1] + g * C2[1]) / 180];
  }
  function drawMap(ci) {
    const c = mapCanv[ci], ctx = c.getContext("2d"), fam = SH.families[ci];
    const cssW = Math.min(320, c.getBoundingClientRect().width || 300), dpr = DPR(), W = Math.round(cssW * dpr);
    const cr = corner(W);
    c.width = W; c.height = cr.H;
    ctx.clearRect(0, 0, W, cr.H);
    ctx.beginPath(); ctx.moveTo(...cr.C0); ctx.lineTo(...cr.C1); ctx.lineTo(...cr.C2); ctx.closePath();
    ctx.fillStyle = css(PAL.faint); ctx.fill();
    const step = 180 / STEPS, cell = (W - 2 * 0.07 * W) / STEPS;
    let idx = 0;
    for (let i = 1; i < STEPS; i++)
      for (let j = 1; j < STEPS - i; j++) {
        const st = fam.grid[idx++];
        if (st === "s" || st === "x") continue;
        const [x, y] = ternary(W, i * step, j * step);
        ctx.fillStyle = COLORS[st]();
        const r = st === "c" ? cell * 0.75 : cell * 0.62;
        ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
      }
    ctx.lineWidth = dpr; ctx.strokeStyle = css(PAL.rule);
    ctx.beginPath(); ctx.moveTo(...cr.C0); ctx.lineTo(...cr.C1); ctx.lineTo(...cr.C2); ctx.closePath(); ctx.stroke();
    if (chosen.fam === ci) {
      const [x, y] = ternary(W, chosen.a, chosen.b);
      ctx.beginPath(); ctx.arc(x, y, 7 * dpr, 0, 2 * Math.PI);
      ctx.lineWidth = 2.5 * dpr; ctx.strokeStyle = css(PAL.skin); ctx.stroke();
      ctx.lineWidth = 1.5 * dpr; ctx.strokeStyle = css(PAL.copper); ctx.stroke();
    }
  }
  (function buildMaps() {
    const leg = $("legend");
    leg.innerHTML = [["o", "both drums flat, different shapes"], ["c", "flat but congruent"], ["1", "only one drum flat"], ["x", "overlap or slit"]]
      .map(([k, t]) => `<span><i style="background:${k === "x" ? "var(--faint)" : k === "o" ? "var(--ink)" : k === "c" ? "var(--copper)" : "color-mix(in srgb, var(--muted) 45%, transparent)"}"></i>${t}</span>`).join("");
    const box = $("maps");
    famOrder.forEach(ci => {
      const fam = SH.families[ci];
      const fig = document.createElement("figure");
      const ok = fam.tally.ok || 0, total = Object.values(fam.tally).reduce((a, b) => a + b, 0);
      fig.innerHTML = `<div class="fam">${famHTML(fam)}</div>`;
      const c = document.createElement("canvas");
      c.setAttribute("aria-label", `Map of triangle shapes for family ${fam.name}. Click to build a pair.`);
      fig.appendChild(c);
      const s = document.createElement("div"); s.className = "share";
      s.textContent = `${ok.toLocaleString("en")} of ${total.toLocaleString("en")} shapes work (${(100 * ok / total).toFixed(1)}%)`;
      fig.appendChild(s);
      box.appendChild(fig);
      mapCanv[ci] = c;
      c.addEventListener("pointerdown", ev => {
        const r = c.getBoundingClientRect(), W = c.width, x = (ev.clientX - r.left) / r.width * W, y = (ev.clientY - r.top) / r.height * c.height;
        const { C0, C1, C2 } = corner(W);
        const det = (C1[1] - C2[1]) * (C0[0] - C2[0]) + (C2[0] - C1[0]) * (C0[1] - C2[1]);
        const l0 = ((C1[1] - C2[1]) * (x - C2[0]) + (C2[0] - C1[0]) * (y - C2[1])) / det;
        const l1 = ((C2[1] - C0[1]) * (x - C2[0]) + (C0[0] - C2[0]) * (y - C2[1])) / det;
        const l2 = 1 - l0 - l1;
        if (Math.min(l0, l1, l2) < 0.004) return;
        const prev = chosen.fam;
        chosen = { fam: ci, a: Math.round(l0 * 1800) / 10, b: Math.round(l1 * 1800) / 10 };
        drawMap(ci); if (prev !== ci) drawMap(prev);
        drawPicked();
      });
    });
  })();
  function drawPicked() {
    const fam = SH.families[chosen.fam], tri = D.triangleFromAngles(chosen.a, chosen.b);
    const g = Math.round((180 - chosen.a - chosen.b) * 10) / 10;
    const ca = triCheck(fam.permsA, tri), cb = triCheck(fam.permsB, tri);
    drawTiles($("pickA"), D.unfold(fam.permsA, tri), tri, null, "", {});
    drawTiles($("pickB"), D.unfold(fam.permsB, tri), tri, null, "", {});
    let verdict;
    if (ca.status === "ok" && cb.status === "ok") {
      const same = congruent(boundaryLoop(fam.permsA, ca.V), boundaryLoop(fam.permsB, cb.V));
      verdict = same ? "Both drums lie flat, but they are the same shape, one turned or mirrored. In my scan that happened only for isosceles triangles."
                     : "Both drums lie flat and have different shapes. This is an isospectral pair: the two drums have the same notes.";
    } else if (ca.status === "ok" || cb.status === "ok") {
      verdict = `Drum ${ca.status === "ok" ? "B" : "A"} ${(ca.status === "ok" ? cb : ca).status === "overlap" ? "overlaps itself" : "has two pieces of rim lying along each other"}, so only drum ${ca.status === "ok" ? "A" : "B"} is a flat drum.`;
    } else {
      const st = ca.status === "overlap" || cb.status === "overlap" ? "overlap themselves" : "have pieces of rim lying along each other";
      verdict = `With this triangle the drums ${st}, so neither is a flat drum.`;
    }
    $("pickVerdict").innerHTML = `<div style="font-family:var(--display);font-size:22px">Family ${famHTML(fam)}</div>` +
      `<div class="num">Triangle angles ${chosen.a}°, ${chosen.b}°, ${g}°</div><div>${verdict}</div>`;
    [$("pickA"), $("pickB")].forEach((svg, s) => {
      const st = (s ? cb : ca).status;
      svg.querySelectorAll(".tile").forEach(p => { if (st !== "ok") { p.style.fill = "transparent"; p.style.stroke = "var(--muted)"; } });
    });
  }

  // ------------------------------------------------------------------ homophonic
  const special = Hd.special;
  const homo = playableDuo(PH, $("homoA"), $("homoB"), $("homoLadder"), {
    marks: [special.A.xy, special.B.xy],
    onStrike(side, last) {
      if (last[0] && last[1]) {
        const mm = mismatch(last[0], last[1], PH);
        $("homoReadout").textContent = mm < 0.002
          ? "Struck at the dots: every note has the same strength on both drums (mismatch under 0.2%)."
          : `The strengths of the notes differ by ${Math.round(100 * mm)}% between the two strikes.`;
      }
    }
  });
  $("homoDots").addEventListener("click", () => {
    homo.strike(0, phiAt(PH, PH.modesA, nodeWhere(PH, special.A.tile, special.A.node)));
    homo.strike(1, phiAt(PH, PH.modesB, nodeWhere(PH, special.B.tile, special.B.node)), 1.5);
  });
  $("homoRandom").addEventListener("click", () => {
    const wa = homo.randomWhere(0), wb = homo.randomWhere(1);
    if (wa) homo.strike(0, phiAt(PH, PH.modesA, wa));
    if (wb) homo.strike(1, phiAt(PH, PH.modesB, wb), 1.5);
  });

  // Phones only unlock audio on pointer-up, so resume there too.
  ["pointerup", "touchend", "keydown"].forEach(t => document.addEventListener(t, () => { if (actx && actx.state === "suspended") actx.resume(); }, { passive: true }));

  // ------------------------------------------------------------------ layout, theme, start
  function layoutAll() {
    readPalette();
    hero.layout();
    layoutDuo(modeViews[0], modeViews[1], PG);
    layoutDuo(triViews[0], triViews[1], PG);
    drawModes(); drawTri();
    homo.layout();
    mapCanv.forEach((c, i) => drawMap(i));
    drawEquation();
  }
  let rt = null;
  let lastW = window.innerWidth;
  window.addEventListener("resize", () => {
    if (Math.abs(window.innerWidth - lastW) < 2) return;
    lastW = window.innerWidth;
    clearTimeout(rt); rt = setTimeout(layoutAll, 150);
  });
  const mq = matchMedia("(prefers-color-scheme: dark)");
  (mq.addEventListener ? mq.addEventListener.bind(mq, "change") : mq.addListener.bind(mq))(() => layoutAll());
  new MutationObserver(() => layoutAll()).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  layoutAll();
  setMode(0);
  drawPicked();
  highlight({ line: 0 });
  // One silent strike on each drum so the page opens with the skins moving.
  const centre = (pair, tile) => { const n = pair.n, i = Math.round(n / 3), j = Math.round(n / 3); let idx = 0; for (let a = 0; a < i; a++) idx += n + 1 - a; return nodeWhere(pair, tile, idx + j); };
  hero.strike(0, phiAt(PG, PG.modesA, centre(PG, 2)), 0, true, true);
  hero.strike(1, phiAt(PG, PG.modesB, centre(PG, 4)), 0, true, true);
  homo.strike(0, phiAt(PH, PH.modesA, nodeWhere(PH, special.A.tile, special.A.node)), 0, true, true);
  homo.strike(1, phiAt(PH, PH.modesB, nodeWhere(PH, special.B.tile, special.B.node)), 0, true, true);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { hero.ladder.resize(); homo.ladder.resize(); });
})();
