(() => {
  const DATA = window.PEAL_DATA;
  const calling = DATA.calling;
  const $ = id => document.getElementById(id);
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const SVGNS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs = {}, parent) => {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };

  // ---------- numbers on the board ----------
  const ONES = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
    'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
  const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
  const words = n => n >= 100 ? 'one hundred' + (n % 100 ? ' and ' + words(n % 100) : '')
    : n < 20 ? ONES[n] : TENS[Math.floor(n / 10)] + (n % 10 ? '-' + ONES[n % 10] : '');
  const nb = [...calling].filter(c => c === 'b').length, ns = [...calling].filter(c => c === 's').length;
  const fill = (k, v) => document.querySelectorAll(`[data-k="${k}"]`).forEach(e => { e.textContent = v; });
  fill('bobs', nb); fill('bobsWords', words(nb)); fill('calls', nb + ns);
  const boardInner = document.querySelector('.board-inner');
  boardInner.setAttribute('aria-label', boardInner.getAttribute('aria-label').replace('BOBS', nb));

  // ---------- the rows ----------
  const { rows } = Ring.expand(calling);                 // 5040 rows, rows[0] = rounds
  const leadOfRow = i => Math.floor(i / 14);
  // the stream actually rung: four rows of rounds, the 5039 changes, rounds (change 5040), two more rounds
  const PRE = 4, R8 = [1, 2, 3, 4, 5, 6, 7, 8];
  const stream = [R8, R8, R8, R8, ...rows.slice(1).map(r => r.concat(8)), R8, R8, R8];
  const LAST = PRE + 5038;                               // index of the closing rounds (change 5040)
  const changeNo = i => i < PRE ? 0 : Math.min(i - PRE + 1, 5040);
  const peakRow = i => i - PRE + 1;                      // index into rows[] (5040 = closing rounds)

  // ---------- timing ----------
  const H = 10260 / (5040 * 8 + 2520);                   // seconds per blow at peal speed (2 h 51 min)
  const tRow = i => (i * 8 + Math.floor(i / 2)) * H;     // open handstroke gap before each handstroke
  const rowAt = t => {                                   // last row starting at or before peal-time t
    let i = Math.floor(t / (8.5 * H)); if (i < 0) return 0;
    while (i > 0 && tRow(i) > t) i--;
    while (i + 1 < stream.length && tRow(i + 1) <= t) i++;
    return i;
  };
  const fmtTime = s => { s = Math.max(0, Math.floor(s)); return `${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; };

  // ---------- player ----------
  let audio = null, playing = false, speed = 1;
  let pos = 0;               // peal-time (s) when paused
  let origin = 0;            // audio time at which peal-time 0 would have sounded (at current speed)
  let nextBlow = 0;          // global blow index to schedule next
  let follow = 7;
  const blowTime = b => { const i = Math.floor(b / 8); return tRow(i) + (b % 8) * H; };
  const now = () => playing ? (audio.ctx.currentTime - origin) * speed : pos;

  function ensureAudio() {
    if (audio) return audio;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    audio = Bells.create(Ctx);
    return audio;
  }
  function firstBlowAtOrAfter(t) {
    const i = rowAt(t); let b = i * 8;
    while (blowTime(b) < t - 1e-9) b++;
    return b;
  }
  function start() {
    if (!ensureAudio()) { $('play').textContent = 'No audio'; return; }
    audio.ctx.resume();
    if (pos >= tRow(stream.length - 1) + 8 * H) pos = 0;
    origin = audio.ctx.currentTime + 0.12 - pos / speed;
    nextBlow = firstBlowAtOrAfter(pos);
    playing = true; $('play').textContent = 'Stand';
  }
  function stop() { if (!playing) return; pos = now(); playing = false; $('play').textContent = 'Ring'; }
  function seek(t) { const was = playing; stop(); pos = Math.max(0, t); if (was) start(); draw(true); }
  function schedule() {
    if (!playing) return;
    const horizon = now() + 0.25 * speed;
    const maxB = stream.length * 8;
    while (nextBlow < maxB && blowTime(nextBlow) <= horizon) {
      const i = Math.floor(nextBlow / 8), bell = stream[i][nextBlow % 8];
      const when = origin + blowTime(nextBlow) / speed;
      if (when > audio.ctx.currentTime - 0.02) {
        const src = audio.strike(bell, Math.max(when, audio.ctx.currentTime), speed >= 10 ? 0.55 : speed >= 3 ? 0.75 : 1);
        if (speed >= 3) src.stop(when + (speed >= 10 ? 1.4 : 3));
      }
      nextBlow++;
    }
    if (nextBlow >= maxB && now() > blowTime(maxB - 1) + 2) { stop(); pos = 0; }
  }
  setInterval(() => { schedule(); if (playing && performance.now() - lastFrame > 250) draw(false); }, 30);

  $('play').addEventListener('click', () => playing ? stop() : start());
  $('restart').addEventListener('click', () => seek(0));
  document.querySelectorAll('[data-speed]').forEach(b => b.addEventListener('click', () => {
    const t = now(); speed = +b.dataset.speed;
    document.querySelectorAll('[data-speed]').forEach(x => x.classList.toggle('on', x === b));
    if (playing) { playing = false; pos = t; start(); }
  }));

  // ropes
  const ropes = [];
  for (let b = 1; b <= 8; b++) {
    const r = document.createElement('button');
    r.className = 'rope' + (b === 1 ? ' treble' : '') + (b === follow ? ' followed' : '');
    r.setAttribute('aria-label', `Follow bell ${b}`);
    r.innerHTML = '<span class="line"></span><span class="sally"></span><span class="tail"></span><span class="num">' + (b === 1 ? 'T' : b === 8 ? '8' : b) + '</span>';
    r.addEventListener('click', () => { if (b === 1 || b === 8) return; follow = b; ropes.forEach((x, k) => x.classList.toggle('followed', k + 1 === follow)); draw(true); });
    $('ropes').appendChild(r); ropes.push(r);
  }

  // ---------- drawing the rows ----------
  const cv = $('rowsCanvas'), cx = cv.getContext('2d');
  const strip = $('strip'), sx = strip.getContext('2d');
  let C = {};
  function readColours() {
    C = { ink: css('--ink'), muted: css('--muted'), rowInk: css('--row-ink'), red: css('--red'), blue: css('--blue'),
      gilt: css('--gilt'), rule: css('--rule'), hl: css('--hl'), wall: css('--wall'), wall2: css('--wall-2'), panel: css('--panel') };
  }
  readColours();
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { readColours(); draw(true); drawStrip(); });

  function sizeCanvas(c, ctx) {
    const dpr = window.devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return [w, h];
  }

  let lastRow = -1, lastBlow = -1, lastCallShown = -1;
  function draw(force) {
    const t = now();
    const i = rowAt(t), j = Math.min(7, Math.floor((t - tRow(i)) / H));
    const frac = i + 1 < stream.length ? Math.min(1, (t - tRow(i)) / (tRow(i + 1) - tRow(i))) : 0;
    // ropes: each bell's rope sits at hand or back according to its last stroke
    const blowIdx = i * 8 + j;
    if (blowIdx !== lastBlow) {
      if (lastBlow < 0 || Math.abs(blowIdx - lastBlow) > 16) {
        for (let k = 0; k < 8; k++) {
          const r = ropes[stream[i][k] - 1], last = k <= j ? i : i - 1;
          r.classList.toggle('hand', t > 0 && last >= 0 && last % 2 === 0); r.classList.toggle('back', t > 0 && last >= 0 && last % 2 === 1);
        }
      } else {
        for (let b = lastBlow + 1; b <= blowIdx; b++) {
          const ri = Math.floor(b / 8), bell = stream[ri][b % 8], r = ropes[bell - 1];
          r.classList.toggle('hand', ri % 2 === 0); r.classList.toggle('back', ri % 2 === 1);
        }
      }
      ropes.forEach((r, k) => r.classList.toggle('struck', stream[i][j] === k + 1 && (t - tRow(i)) < 8 * H));
      lastBlow = blowIdx;
    }
    if (!force && i === lastRow && !playing) return;
    lastRow = i;
    // stats
    const ch = changeNo(i);
    $('sRow').textContent = ch.toLocaleString('en-GB');
    $('sLead').textContent = i < PRE ? '—' : Math.min(360, leadOfRow(peakRow(i)) + 1);
    $('sTime').textContent = fmtTime(Math.max(0, t - tRow(PRE)));
    $('sLeft').textContent = i < PRE ? 'Rounds' : i > LAST ? "That's all." : `${(5040 - ch).toLocaleString('en-GB')} changes to go`;
    // the conductor calls a bob or single as the treble comes down to lead: about three rows before the lead end
    const cb = $('callbox');
    let shown = '';
    if (i >= PRE && i <= LAST) {
      const r = peakRow(i), L = leadOfRow(r), pin = r % 14;
      if (calling[L] !== 'p' && pin >= 10 && pin <= 13) shown = calling[L] === 'b' ? 'Bob' : 'Single';
    }
    if (i === PRE - 2) shown = 'Go';
    if (i > LAST && i <= LAST + 1) shown = "That's all";
    if (i >= stream.length - 1) shown = 'Stand';
    if (shown) { cb.textContent = shown; cb.classList.remove('quiet'); } else cb.classList.add('quiet');

    const [w, h] = sizeCanvas(cv, cx);
    cx.clearRect(0, 0, w, h);
    const rowH = 20, left = 50, right = 34, colW = Math.min(30, (w - left - right) / 8);
    const x0 = left + ((w - left - right) - colW * 8) / 2;
    const cy = Math.round(h * 0.36);
    const yOf = k => cy + (k - i - frac) * rowH;
    const xOf = p => x0 + (p + 0.5) * colW;
    const lo = Math.max(0, i - Math.ceil(cy / rowH) - 1), hi = Math.min(stream.length - 1, i + Math.ceil((h - cy) / rowH) + 1);
    // current row band
    cx.fillStyle = C.hl; cx.fillRect(0, yOf(i) - rowH / 2, w, rowH);
    // lead-end rules, lead numbers and calls
    cx.font = '500 11px "DM Mono", ui-monospace, Menlo, monospace'; cx.textBaseline = 'middle';
    for (let k = lo; k <= hi; k++) {
      if (k < PRE || k > LAST) continue;
      const r = peakRow(k);
      if (r % 14 === 0 && r < 5040) {
        cx.strokeStyle = C.rule; cx.lineWidth = 1;
        cx.beginPath(); cx.moveTo(x0 - 4, yOf(k) - rowH / 2 + .5); cx.lineTo(x0 + colW * 8 + 4, yOf(k) - rowH / 2 + .5); cx.stroke();
        cx.fillStyle = C.muted; cx.textAlign = 'right'; cx.fillText(String(leadOfRow(r) + 1), x0 - 10, yOf(k));
      }
      if (r % 14 === 13 && calling[leadOfRow(r)] !== 'p') {
        const c = calling[leadOfRow(r)];
        cx.fillStyle = c === 's' ? C.red : C.gilt; cx.textAlign = 'left'; cx.font = '600 14px "DM Mono", ui-monospace, Menlo, monospace';
        cx.fillText(c === 's' ? 's' : '–', x0 + colW * 8 + 8, yOf(k) + rowH / 2);
        cx.font = '500 11px "DM Mono", ui-monospace, Menlo, monospace';
      }
    }
    // lines: treble and the followed bell
    for (const [bell, colour, lw] of [[1, C.red, 1.6], [follow, C.blue, 2.2]]) {
      cx.strokeStyle = colour; cx.lineWidth = lw; cx.lineJoin = 'round'; cx.beginPath();
      for (let k = lo; k <= hi; k++) { const p = stream[k].indexOf(bell); k === lo ? cx.moveTo(xOf(p), yOf(k)) : cx.lineTo(xOf(p), yOf(k)); }
      cx.stroke();
    }
    // digits
    cx.textAlign = 'center';
    for (let k = lo; k <= hi; k++) {
      const y = yOf(k), cur = k === i;
      cx.font = (cur ? '600 15px' : '400 14px') + ' "DM Mono", ui-monospace, Menlo, monospace';
      for (let p = 0; p < 8; p++) {
        const b = stream[k][p];
        if (b === 1 || b === follow) {
          if (cur) { cx.fillStyle = b === 1 ? C.red : C.blue; cx.beginPath(); cx.arc(xOf(p), y, 3.2, 0, 7); cx.fill(); }
          continue;
        }
        if (cur && p === j && t - tRow(i) < 8 * H) { cx.fillStyle = C.gilt; cx.beginPath(); cx.arc(xOf(p), y, 9, 0, 7); cx.fill(); cx.fillStyle = C.wall; }
        else cx.fillStyle = cur ? C.ink : C.rowInk;
        cx.fillText(b === 8 ? '8' : String(b), xOf(p), y + 1);
      }
    }
    // fade top and bottom
    const g1 = cx.createLinearGradient(0, 0, 0, 60); g1.addColorStop(0, C.wall); g1.addColorStop(1, C.wall + '00');
    cx.fillStyle = g1; cx.fillRect(0, 0, w, 60);
    const g2 = cx.createLinearGradient(0, h - 50, 0, h); g2.addColorStop(0, C.wall + '00'); g2.addColorStop(1, C.wall);
    cx.fillStyle = g2; cx.fillRect(0, h - 50, w, 50);
    drawStripMarker(i);
  }

  // ---------- the strip ----------
  let stripBase = null;
  function drawStrip() {
    const [w, h] = sizeCanvas(strip, sx);
    sx.clearRect(0, 0, w, h);
    sx.fillStyle = C.wall2; sx.fillRect(0, 10, w, h - 20);
    for (let L = 0; L < 360; L++) {
      if (calling[L] === 'p') continue;
      const x = (L + 0.5) / 360 * w;
      sx.fillStyle = calling[L] === 's' ? C.red : C.gilt;
      const tall = calling[L] === 's';
      sx.fillRect(Math.round(x) - (tall ? 1.5 : 1), tall ? 2 : 10, tall ? 3 : 2, tall ? h - 4 : h - 20);
    }
    stripBase = sx.getImageData(0, 0, strip.width, strip.height);
  }
  function drawStripMarker(i) {
    if (!stripBase) return;
    const w = strip.clientWidth, h = strip.clientHeight;
    sx.putImageData(stripBase, 0, 0);
    const r = Math.max(0, Math.min(5039, peakRow(i)));
    const x = (i < PRE ? 0 : (r / 5040)) * w;
    sx.fillStyle = C.ink + '22'; sx.fillRect(0, 10, x, h - 20);
    sx.fillStyle = C.blue; sx.fillRect(Math.round(x) - 1, 0, 3, h);
  }
  function stripSeek(ev) {
    const rect = strip.getBoundingClientRect();
    const L = Math.max(0, Math.min(359, Math.floor((ev.clientX - rect.left) / rect.width * 360)));
    seekLead(L);
  }
  const seekLead = L => seek(L === 0 ? 0 : tRow(PRE + L * 14 - 1));
  strip.addEventListener('pointerdown', stripSeek);

  let lastFrame = 0;
  function frame() { lastFrame = performance.now(); draw(false); requestAnimationFrame(frame); }
  window.addEventListener('resize', () => { drawStrip(); draw(true); });

  // ---------- the plain course figure ----------
  function leadFigure() {
    const host = $('leadFig');
    let lh = Ring.ROUNDS;
    const cw = 13, rh = 13.5, padX = 14, padY = 8;
    for (let L = 0; L < 5; L++) {
      const { rows: rs, next } = Ring.lead(lh, 'p');
      const all = rs.concat([next]);
      const W = padX + cw * 7 + 6, Hh = padY * 2 + rh * all.length;
      const s = el('svg', { viewBox: `0 0 ${W} ${Hh}`, width: W, height: Hh, 'aria-hidden': 'true' }, host);
      const X = p => padX + p * cw + cw / 2, Y = k => padY + k * rh + rh / 2;
      for (const [bell, cls, lw] of [[1, 'var(--red)', 1.5], [7, 'var(--blue)', 2]]) {
        el('polyline', { points: all.map((r, k) => `${X(r.indexOf(bell))},${Y(k)}`).join(' '), fill: 'none', stroke: cls, 'stroke-width': lw, 'stroke-linejoin': 'round' }, s);
      }
      all.forEach((r, k) => r.forEach((b, p) => {
        if (b === 1 || b === 7) return;
        const tx = el('text', { x: X(p), y: Y(k) + 4, 'text-anchor': 'middle', 'font-size': 11.5, 'font-family': '"DM Mono", ui-monospace, Menlo, monospace', fill: k === all.length - 1 ? 'var(--muted)' : 'var(--ink)', opacity: k === all.length - 1 ? .5 : 1 }, s);
        tx.textContent = b;
      }));
      el('path', { d: `M3 ${Y(0)} h8`, stroke: 'var(--gilt)', 'stroke-width': 2 }, s);
      lh = next;
    }
  }

  // ---------- the three lead ends ----------
  function callsFigure() {
    const host = $('callsFig');
    const names = { p: 'Plain lead', b: 'Bob', s: 'Single' };
    const ends = { p: '7.1', b: '3.1', s: '3.123' };
    for (const c of 'pbs') {
      const d = document.createElement('div');
      d.innerHTML = `<h3 style="color:${c === 'p' ? 'var(--ink)' : c === 'b' ? 'var(--gilt)' : 'var(--red)'}">${names[c]}</h3><div class="pn">… ${ends[c]}</div>`;
      const { rows: rs, next } = Ring.lead(Ring.ROUNDS, c);
      const all = rs.slice(11).concat([next]);
      const cw = 22, rh = 26, W = 7 * cw + 20, Hh = all.length * rh + 12;
      const s = el('svg', { viewBox: `0 0 ${W} ${Hh}`, 'aria-hidden': 'true' }, d);
      const X = p => 10 + p * cw + cw / 2, Y = k => 8 + k * rh + rh / 2;
      // places made between rows
      for (let k = 0; k + 1 < all.length; k++) {
        for (let p = 0; p < 7; p++) if (all[k][p] === all[k + 1][p]) {
          el('line', { x1: X(p), y1: Y(k) + 7, x2: X(p), y2: Y(k + 1) - 7, stroke: 'var(--gilt)', 'stroke-width': 3, 'stroke-linecap': 'round' }, s);
        }
      }
      for (let b = 1; b <= 7; b++) {
        el('polyline', { points: all.map((r, k) => `${X(r.indexOf(b))},${Y(k)}`).join(' '), fill: 'none', stroke: b === 1 ? 'var(--red)' : 'var(--rule)', 'stroke-width': b === 1 ? 1.5 : 1 }, s);
      }
      all.forEach((r, k) => r.forEach((b, p) => {
        const tx = el('text', { x: X(p), y: Y(k) + 4.5, 'text-anchor': 'middle', 'font-size': 13, 'font-family': '"DM Mono", ui-monospace, Menlo, monospace', fill: b === 1 ? 'var(--red)' : 'var(--ink)', 'font-weight': k === all.length - 1 ? 600 : 400 }, s);
        tx.textContent = b;
      }));
      const cap = document.createElement('div'); cap.className = 'pn';
      cap.textContent = 'next lead head ' + next.join('');
      d.appendChild(cap);
      host.appendChild(d);
    }
  }

  // ---------- Thompson's board ----------
  function thompson() {
    const m = Ring.qsetModel();
    const svg = $('qboard');
    let bobbed = new Set(), prevCount = 72, merging = null;
    const CELL = 100, RAD = 28;
    const pos = [];
    let COLS = 0;
    function layout() {
      const cols = svg.clientWidth && svg.clientWidth < 560 ? 6 : 9;
      if (cols === COLS) return false;
      COLS = cols;
      svg.setAttribute('viewBox', `0 0 ${COLS * CELL} ${Math.ceil(72 / COLS) * CELL + 20}`);
      m.courses.forEach((c, ci) => {
        const cxx = (ci % COLS) * CELL + CELL / 2, cyy = Math.floor(ci / COLS) * CELL + CELL / 2 + 6;
        c.forEach((lead, k) => {
          const a = -Math.PI / 2 + k * 2 * Math.PI / 5;
          pos[lead] = [cxx + RAD * Math.cos(a), cyy + RAD * Math.sin(a)];
        });
      });
      return true;
    }
    layout();
    const gEdges = el('g', {}, svg), gHover = el('g', {}, svg), gDots = el('g', {}, svg);
    const edges = [], dots = [], rings = [];
    for (let i = 0; i < 360; i++) {
      const [x1, y1] = pos[i], [x2, y2] = pos[m.plain[i]];
      edges[i] = el('line', { x1, y1, x2, y2, 'stroke-width': 1.6, 'stroke-linecap': 'round' }, gEdges);
    }
    for (let i = 0; i < 360; i++) {
      const g = el('g', { class: 'dot', tabindex: 0, role: 'button', 'aria-label': `Lead head ${m.lhs[i]}` }, gDots);
      el('circle', { cx: pos[i][0], cy: pos[i][1], r: 15, fill: 'transparent' }, g);
      rings[i] = el('circle', { cx: pos[i][0], cy: pos[i][1], r: 9.5, fill: 'none', 'stroke-width': 2 }, g);
      dots[i] = el('circle', { cx: pos[i][0], cy: pos[i][1], r: 6.5 }, g);
      g.addEventListener('click', () => { stopMerge(); toggle(m.qset[i], true); });
      g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); stopMerge(); toggle(m.qset[i], true); } });
      g.addEventListener('pointerenter', () => hover(m.qset[i]));
      g.addEventListener('pointerleave', () => hover(-1));
      g.addEventListener('focus', () => hover(m.qset[i]));
      g.addEventListener('blur', () => hover(-1));
    }
    function place() {
      for (let i = 0; i < 360; i++) {
        const [x1, y1] = pos[i], [x2, y2] = pos[m.plain[i]];
        Object.entries({ x1, y1, x2, y2 }).forEach(([k, v]) => edges[i].setAttribute(k, v));
        for (const c of [dots[i], rings[i], dots[i].parentNode.firstChild]) { c.setAttribute('cx', x1); c.setAttribute('cy', y1); }
      }
    }
    window.addEventListener('resize', () => { if (layout()) { place(); hover(-1); } });
    function hover(q) {
      while (gHover.firstChild) gHover.removeChild(gHover.firstChild);
      if (q < 0) return;
      const mem = m.qsets[q];
      for (let a = 0; a < mem.length; a++) {
        const [x1, y1] = pos[mem[a]], [x2, y2] = pos[mem[(a + 1) % mem.length]];
        el('line', { x1, y1, x2, y2, stroke: 'var(--gilt)', 'stroke-width': 1.5, 'stroke-dasharray': '4 4', opacity: .9 }, gHover);
      }
      mem.forEach(i => el('circle', { cx: pos[i][0], cy: pos[i][1], r: 13, fill: 'none', stroke: 'var(--gilt)', 'stroke-width': 2 }, gHover));
    }
    const PALETTE = ['#8a6a9e', '#4f8f7c', '#b07a3c', '#6d7fa6', '#a35d6a', '#7d8f4e', '#5f8aa0', '#9c6b52', '#7a6aa0', '#9a8a4a', '#54806a', '#a0707e'];
    function render() {
      const { id, sizes } = Ring.blocks(m, bobbed);
      const order = sizes.map((s, k) => k).sort((a, b) => sizes[b] - sizes[a] || a - b);
      const colour = [];
      const big = sizes.length <= 12 || sizes[order[0]] > 5;
      order.forEach((k, r) => {
        colour[k] = big && r === 0 ? 'var(--gilt)' : big && r === 1 ? 'var(--blue)' : big && r === 2 ? 'var(--red)' : PALETTE[k % PALETTE.length];
      });
      for (let i = 0; i < 360; i++) {
        const isB = bobbed.has(m.qset[i]);
        dots[i].setAttribute('fill', colour[id[i]]);
        rings[i].setAttribute('stroke', isB ? 'var(--ink)' : 'none');
        edges[i].setAttribute('stroke', isB ? 'transparent' : colour[id[i]]);
        edges[i].setAttribute('opacity', .45);
      }
      const n = sizes.length;
      $('tCount').textContent = n;
      document.querySelector('.count small').textContent = n === 1 ? 'round block' : 'round blocks';
      const rb = sizes[id[m.rounds]];
      $('tInfo').textContent = `Rounds' block: ${rb} lead${rb === 1 ? '' : 's'}, ${(rb * 14).toLocaleString('en-GB')} rows · ${bobbed.size * 5} bobs`;
      return n;
    }
    function toggle(q, explain) {
      const before = prevCount;
      bobbed.has(q) ? bobbed.delete(q) : bobbed.add(q);
      const n = render(); prevCount = n;
      if (explain) {
        const d = n - before;
        const what = d === -4 ? 'Five blocks became one' : d === -2 ? 'Three blocks became one' : d === 0 ? 'The blocks rearranged, but the count stayed the same'
          : d === 2 ? 'A block split into three' : d === 4 ? 'A block split into five' : 'The count changed';
        $('tMsg').textContent = `${bobbed.has(q) ? 'Bobbed' : 'Unbobbed'} a Q-set (five leads in five courses). ${what}: ${d > 0 ? '+' : d < 0 ? '−' : '±'}${Math.abs(d)}. Still ${n % 2 ? 'odd' : 'even'}.`;
      }
      return n;
    }
    function stopMerge() { if (merging) { clearInterval(merging); merging = null; } }
    $('tMerge').addEventListener('click', () => {
      stopMerge();
      let stale = 0, steps = 0;
      $('tMsg').textContent = 'Merging…';
      merging = setInterval(() => {
        const before = prevCount;
        if (before <= 2 || stale > 600) {
          stopMerge();
          $('tMsg').textContent = before <= 2
            ? `Two blocks, after ${steps} Q-sets. From here every Q-set leaves two blocks or splits one further. None can make one.`
            : `Stuck at ${before}. Click "Merge for me" again to keep going.`;
          return;
        }
        for (let tries = 0; tries < 40; tries++) {
          const q = Math.floor(Math.random() * 72);
          const n = toggle(q, false);
          if (n < before || (n === before && Math.random() < 0.35)) { stale = n < before ? 0 : stale + 1; steps++; $('tMsg').textContent = `Merging… ${n} blocks`; return; }
          toggle(q, false);
          stale++;
        }
      }, 120);
    });
    $('t357').addEventListener('click', () => {
      stopMerge();
      bobbed = new Set(DATA.thompson.map(lh => m.qset[m.idx.get(lh)]));
      prevCount = render();
      $('tMsg').textContent = `${bobbed.size} Q-sets bobbed. One block of 357 leads, and three leads stranded: three bobs in a row, a B-block.`;
    });
    $('tClear').addEventListener('click', () => { stopMerge(); bobbed = new Set(); prevCount = render(); $('tMsg').textContent = 'All plain: 72 courses, each a round block of its own.'; });
    prevCount = render();
  }

  // ---------- the composition grid and the check ----------
  function composition() {
    const grid = $('compGrid');
    let lh = Ring.ROUNDS;
    for (let L = 0; L < 360; L++) {
      const b = document.createElement('button');
      const c = calling[L];
      b.className = c === 'p' ? '' : c;
      b.textContent = c === 'b' ? '–' : c === 's' ? 's' : '';
      b.title = `Lead ${L + 1} from ${lh.join('')}${c === 'b' ? ', bob' : c === 's' ? ', single' : ''}`;
      b.addEventListener('click', () => { seekLead(L); document.querySelector('.player').scrollIntoView({ behavior: 'smooth', block: 'center' }); });
      grid.appendChild(b);
      lh = Ring.lead(lh, c).next;
    }
    $('callingText').textContent = calling;
    $('verifyBtn').addEventListener('click', () => {
      const t0 = performance.now();
      const r = Ring.check(calling);
      const ms = (performance.now() - t0).toFixed(0);
      const ok = r.rows === 5040 && r.distinct === 5040 && r.round;
      $('verifyOut').innerHTML = ok
        ? `<b>True.</b> ${r.rows.toLocaleString('en-GB')} rows, ${r.distinct.toLocaleString('en-GB')} different, and it comes round. ${r.bobs} bobs, ${r.singles} singles. Checked in ${ms} ms.`
        : `<b>False!</b> ${r.distinct} different rows out of ${r.rows}.`;
    });
  }

  leadFigure(); callsFigure(); thompson(); composition();
  drawStrip(); draw(true); requestAnimationFrame(frame);
  if (document.fonts) document.fonts.ready.then(() => { drawStrip(); draw(true); });
})();
