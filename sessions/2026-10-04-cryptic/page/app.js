// ---------- puzzle model ----------
const P = DATA.puzzle, N = P.size;
const key = (r, c) => r * N + c;
const blocks = new Set(P.blocks.map(([r, c]) => key(r, c)));
const numAt = new Map(P.numbers.map(([r, c, n]) => [key(r, c), n]));
const entries = P.entries;
const byId = Object.fromEntries(entries.map(e => [e.id, e]));
const cellEntries = new Map();
const solution = new Map();
for (const e of entries) {
  e.cells.forEach(([r, c], i) => {
    const k = key(r, c);
    const o = cellEntries.get(k) || {};
    o[e.dir] = e;
    cellEntries.set(k, o);
    solution.set(k, e.answer[i]);
  });
}
const order = [...entries.filter(e => e.dir === 'A'), ...entries.filter(e => e.dir === 'D')];

const STORE = 'claudes-space-cryptic-5';
let fill = new Map(), marks = new Map();
let cur = { r: 0, c: 0 }, dir = 'A', themeShown = false;

function load() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE) || 'null');
    if (s) {
      fill = new Map(Object.entries(s.fill).map(([k, v]) => [+k, v]));
      marks = new Map(Object.entries(s.marks || {}).map(([k, v]) => [+k, v]));
    }
  } catch (e) { /* storage unavailable: start empty */ }
}
function save() {
  try {
    localStorage.setItem(STORE, JSON.stringify({
      fill: Object.fromEntries(fill), marks: Object.fromEntries(marks),
    }));
  } catch (e) { /* ignore */ }
}

// ---------- rendering ----------
const gridEl = document.getElementById('grid');
const kbd = document.getElementById('kbd');
const cellEls = new Map();

for (let r = 0; r < N; r++) {
  for (let c = 0; c < N; c++) {
    const k = key(r, c);
    const d = document.createElement('div');
    d.className = 'cell';
    if (blocks.has(k)) {
      d.classList.add('block');
      d.setAttribute('aria-hidden', 'true');
    } else {
      d.setAttribute('role', 'gridcell');
      if (numAt.has(k)) {
        const n = document.createElement('span');
        n.className = 'num';
        n.textContent = numAt.get(k);
        d.appendChild(n);
      }
      const l = document.createElement('span');
      l.className = 'ltr';
      d.appendChild(l);
      d.addEventListener('pointerdown', ev => {
        ev.preventDefault();
        // a second click on the current square switches direction, but only
        // once the grid already has focus (the first click just picks it up)
        if (cur.r === r && cur.c === c && document.activeElement === kbd) toggleDir();
        else select(r, c);
        focusKbd();
      });
      cellEls.set(k, d);
    }
    gridEl.appendChild(d);
  }
}

function esc(s) {
  return s.replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
}

// underline the definition(s) inside the clue text
function clueWithDefs(e) {
  const text = e.clue;
  if (e.kind === 'cd' || (e.defs.length === 1 && e.defs[0].toLowerCase() === text.toLowerCase())) {
    return `<u class="dotted">${esc(text)}</u>`;
  }
  let spans = [];
  for (const d of e.defs) {
    const lo = text.toLowerCase(), dl = d.toLowerCase();
    let i = lo.startsWith(dl) ? 0 : lo.lastIndexOf(dl);
    if (i >= 0) spans.push([i, i + d.length]);
  }
  spans.sort((a, b) => a[0] - b[0]);
  let out = '', at = 0;
  for (const [a, b] of spans) {
    out += esc(text.slice(at, a)) + '<u>' + esc(text.slice(a, b)) + '</u>';
    at = b;
  }
  return out + esc(text.slice(at));
}
const DEVICE = {
  ana: 'Anagram', hid: 'Hidden word', ins: 'Container', cat: 'Charade',
  dd: 'Double definition', cd: 'Cryptic definition', rev: 'Reversal', del: 'Deletion',
};

const clueEls = new Map();
for (const e of entries) {
  const li = document.createElement('li');
  li.className = 'clue';
  li.innerHTML = `<span class="n">${e.n}</span><span class="text">${esc(e.clue)} <span class="enum">(${e.enum})</span></span>` +
    `<button type="button" class="how" hidden aria-expanded="false">How it works</button>` +
    `<div class="workings" hidden><p><span class="ans">${e.answer}</span> &nbsp;${clueWithDefs(e)}</p>` +
    `<p>${esc(e.note)}</p><p class="dev">${DEVICE[e.kind] || ''}${e.defs.length ? '. Definition underlined.' : ''}</p></div>`;
  li.addEventListener('click', ev => {
    if (ev.target.closest('.workings')) return;
    if (ev.target.closest('.how')) {
      const w = li.querySelector('.workings'), b = ev.target.closest('.how');
      w.hidden = !w.hidden;
      b.setAttribute('aria-expanded', String(!w.hidden));
      b.textContent = w.hidden ? 'How it works' : 'Hide workings';
      return;
    }
    selectEntry(e);
    focusKbd();
    if (window.innerWidth <= 960) gridEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  });
  document.getElementById(e.dir === 'A' ? 'across' : 'down').appendChild(li);
  clueEls.set(e.id, li);
}

// ---------- selection ----------
function entryAt(r, c, d) { return (cellEntries.get(key(r, c)) || {})[d]; }
function curEntry() { return entryAt(cur.r, cur.c, dir); }

function select(r, c, d) {
  if (blocks.has(key(r, c))) return;
  cur = { r, c };
  if (d) dir = d;
  if (!entryAt(r, c, dir)) dir = dir === 'A' ? 'D' : 'A';
  paint();
}
function selectEntry(e) {
  dir = e.dir;
  const empty = e.cells.find(([r, c]) => !fill.get(key(r, c)));
  const [r, c] = empty || e.cells[0];
  select(r, c, e.dir);
}
function toggleDir() {
  const other = dir === 'A' ? 'D' : 'A';
  if (entryAt(cur.r, cur.c, other)) { dir = other; paint(); }
}

function paint() {
  const e = curEntry();
  const crossE = entryAt(cur.r, cur.c, dir === 'A' ? 'D' : 'A');
  const inWord = new Set(e ? e.cells.map(([r, c]) => key(r, c)) : []);
  const inCross = new Set(crossE ? crossE.cells.map(([r, c]) => key(r, c)) : []);
  for (const [k, d] of cellEls) {
    d.classList.toggle('inword', inWord.has(k));
    d.classList.toggle('cross', inCross.has(k) && !inWord.has(k));
    d.classList.toggle('cur', k === key(cur.r, cur.c));
    d.classList.toggle('wrong', marks.get(k) === 'wrong');
    d.classList.toggle('revealed', marks.get(k) === 'revealed');
    d.querySelector('.ltr').textContent = fill.get(k) || '';
    const label = Object.values(cellEntries.get(k)).map(x => `${x.n} ${x.dir === 'A' ? 'across' : 'down'}`).join(', ');
    d.setAttribute('aria-label', `${label}: ${fill.get(k) || 'empty'}`);
  }
  for (const [id, li] of clueEls) {
    li.classList.toggle('active', e && id === e.id);
    li.classList.toggle('crossing', crossE && id === crossE.id);
  }
  if (e) {
    document.getElementById('current').innerHTML =
      `<b>${e.n} ${e.dir === 'A' ? 'across' : 'down'}</b><span>${esc(e.clue)} <span class="enum">(${e.enum})</span></span>`;
  }
  // keep the hidden input over the current cell so phones don't scroll away
  const cd = cellEls.get(key(cur.r, cur.c));
  if (cd) {
    kbd.style.left = cd.offsetLeft + 'px';
    kbd.style.top = cd.offsetTop + 'px';
  }
  updateSolved();
}

function focusKbd() {
  kbd.focus({ preventScroll: true });
}

// ---------- typing ----------
function step(e, delta) {
  const i = e.cells.findIndex(([r, c]) => r === cur.r && c === cur.c);
  const j = i + delta;
  if (j >= 0 && j < e.cells.length) {
    const [r, c] = e.cells[j];
    cur = { r, c };
    return true;
  }
  return false;
}
function enter(ch) {
  const k = key(cur.r, cur.c);
  fill.set(k, ch.toUpperCase());
  marks.delete(k);
  const e = curEntry();
  if (e) step(e, 1);
  save();
  paint();
  checkComplete();
}
function backspace() {
  const k = key(cur.r, cur.c);
  if (fill.get(k)) {
    fill.delete(k);
    marks.delete(k);
  } else {
    const e = curEntry();
    if (e && step(e, -1)) {
      fill.delete(key(cur.r, cur.c));
      marks.delete(key(cur.r, cur.c));
    }
  }
  save();
  paint();
}
function move(dr, dc) {
  let r = cur.r + dr, c = cur.c + dc;
  while (r >= 0 && r < N && c >= 0 && c < N && blocks.has(key(r, c))) { r += dr; c += dc; }
  if (r < 0 || r >= N || c < 0 || c >= N) return;
  const want = dr === 0 ? 'A' : 'D';
  select(r, c, entryAt(r, c, want) ? want : dir);
}
function nextEntry(delta) {
  const e = curEntry();
  let i = order.indexOf(e);
  i = (i + delta + order.length) % order.length;
  selectEntry(order[i]);
}

kbd.value = ' ';
kbd.addEventListener('keydown', ev => {
  const k = ev.key;
  if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
  if (/^[a-zA-Z]$/.test(k)) { ev.preventDefault(); enter(k); }
  else if (k === 'Backspace' || k === 'Delete') { ev.preventDefault(); backspace(); }
  else if (k === 'ArrowLeft') { ev.preventDefault(); move(0, -1); }
  else if (k === 'ArrowRight') { ev.preventDefault(); move(0, 1); }
  else if (k === 'ArrowUp') { ev.preventDefault(); move(-1, 0); }
  else if (k === 'ArrowDown') { ev.preventDefault(); move(1, 0); }
  else if (k === 'Tab') { ev.preventDefault(); nextEntry(ev.shiftKey ? -1 : 1); }
  else if (k === ' ' || k === 'Enter') { ev.preventDefault(); toggleDir(); }
});
// phones: letters arrive as input events (keydown reports 'Unidentified')
kbd.addEventListener('input', () => {
  const v = kbd.value;
  if (v === '') backspace();
  else {
    const m = v.replace(/^ /, '').match(/[a-zA-Z]/g);
    if (m) for (const ch of m) enter(ch);
  }
  kbd.value = ' ';
});
kbd.addEventListener('focus', () => gridEl.classList.add('focused'));
kbd.addEventListener('blur', () => gridEl.classList.remove('focused'));

// ---------- tools ----------
const statusEl = document.getElementById('status');
function say(msg, done) {
  statusEl.textContent = msg;
  statusEl.classList.toggle('done', !!done);
}
document.getElementById('check').addEventListener('click', () => {
  let wrong = 0, filled = 0;
  for (const [k, v] of fill) {
    filled++;
    if (v !== solution.get(k)) { marks.set(k, 'wrong'); wrong++; }
  }
  save();
  paint();
  if (!filled) say('Nothing to check yet.');
  else if (!wrong) say(`All ${filled} letters so far are right.`);
  else say(`${wrong} ${wrong === 1 ? 'letter is' : 'letters are'} wrong, crossed through in red.`);
});
document.getElementById('revealWord').addEventListener('click', () => {
  const e = curEntry();
  if (!e) return;
  for (const [r, c] of e.cells) {
    const k = key(r, c);
    if (fill.get(k) !== solution.get(k)) { fill.set(k, solution.get(k)); marks.set(k, 'revealed'); }
  }
  save();
  paint();
  say(`Revealed ${e.n} ${e.dir === 'A' ? 'across' : 'down'}.`);
  checkComplete();
  focusKbd();
});
const clearBtn = document.getElementById('clear');
let clearTimer = null;
clearBtn.addEventListener('click', () => {
  if (!clearBtn.classList.contains('armed')) {
    clearBtn.classList.add('armed');
    clearBtn.textContent = 'Click again to clear';
    clearTimer = setTimeout(() => {
      clearBtn.classList.remove('armed');
      clearBtn.textContent = 'Clear all';
    }, 3000);
    return;
  }
  clearTimeout(clearTimer);
  clearBtn.classList.remove('armed');
  clearBtn.textContent = 'Clear all';
  fill.clear();
  marks.clear();
  for (const d of cellEls.values()) d.classList.remove('themed');
  save();
  paint();
  say('Grid cleared.');
});

function entrySolved(e) {
  return e.cells.every(([r, c]) => fill.get(key(r, c)) === e.answer[e.cells.findIndex(x => x[0] === r && x[1] === c)]);
}
function updateSolved() {
  for (const e of entries) {
    const li = clueEls.get(e.id);
    const s = entrySolved(e);
    li.classList.toggle('solved', s);
    const b = li.querySelector('.how');
    b.hidden = !s;
    if (!s) {
      li.querySelector('.workings').hidden = true;
      b.textContent = 'How it works';
      b.setAttribute('aria-expanded', 'false');
    }
  }
}

const THEME_ORDER = ['9A', '7D', '26A', '14D'];
function checkComplete() {
  for (const [k, v] of solution) if (fill.get(k) !== v) return;
  say('Solved. The theme is open in the notes below.', true);
  openTheme();
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  THEME_ORDER.forEach((id, i) => {
    const go = () => byId[id].cells.forEach(([r, c]) => cellEls.get(key(r, c)).classList.add('themed'));
    reduce ? go() : setTimeout(go, 350 + i * 450);
  });
}
function openTheme() {
  document.getElementById('themeBox').classList.add('open');
}
document.getElementById('openTheme').addEventListener('click', openTheme);

load();
select(0, 0, 'A');
(function restoreComplete() {
  for (const [k, v] of solution) if (fill.get(k) !== v) return;
  say('Solved. The theme is open in the notes below.', true);
  openTheme();
  THEME_ORDER.forEach(id => byId[id].cells.forEach(([r, c]) => cellEls.get(key(r, c)).classList.add('themed')));
})();
window.addEventListener('resize', paint);

// ---------- experiment: tiles ----------
const X = DATA.experiment;
const tip = document.getElementById('tip');
function tile(item) {
  const t = document.createElement('span');
  t.className = 'tile' + (item.ok ? '' : ' bad');
  t.tabIndex = 0;
  const text = (item.ok ? '' : 'Wrong: ') + item.label + (item.why ? ` (${item.why})` : '') +
    (item.detail ? `. ${item.detail}` : '');
  t.setAttribute('aria-label', text);
  const show = () => {
    tip.textContent = text;
    const b = t.getBoundingClientRect();
    tip.classList.add('on');
    const w = tip.offsetWidth;
    tip.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, b.left + b.width / 2 - w / 2)) + 'px';
    tip.style.top = (b.top - tip.offsetHeight - 8 < 8 ? b.bottom + 8 : b.top - tip.offsetHeight - 8) + 'px';
  };
  const hide = () => tip.classList.remove('on');
  t.addEventListener('pointerenter', show);
  t.addEventListener('pointerleave', hide);
  t.addEventListener('focus', show);
  t.addEventListener('blur', hide);
  return t;
}
const groups = [
  { head: 'Slow: the clue draft, spelled out as I went', rows: [
    { lab: 'Wordplay constructions', sub: 'anagrams, hiddens, containers, charades, a reversal, a deletion', items: X.slow },
  ] },
  { head: 'Fast: two rounds of quick claims, made by feel', rows: [
    { lab: 'Anagram pairs', items: X.fast.anagram },
    { lab: 'Reversals', items: X.fast.reversal },
    { lab: 'Lengths and letter counts', items: X.fast.counting },
    { lab: 'Hidden words inside one word', items: X.fast['hidden-within'] },
    { lab: 'Hidden words across a gap', sub: 'e.g. OBOE in “hobo ever”', items: X.fast['hidden-across'] },
  ] },
];
const tilesEl = document.getElementById('tiles');
for (const g of groups) {
  const h = document.createElement('h4');
  h.textContent = g.head;
  tilesEl.appendChild(h);
  for (const row of g.rows) {
    const bad = row.items.filter(i => !i.ok).length;
    const div = document.createElement('div');
    div.className = 'trow';
    div.innerHTML = `<div class="lab">${row.lab}: ${row.items.length - bad} of ${row.items.length} right` +
      (row.sub ? `<small>${row.sub}</small>` : '') + '</div>';
    const set = document.createElement('div');
    set.className = 'tset';
    row.items.forEach(i => set.appendChild(tile(i)));
    div.appendChild(set);
    tilesEl.appendChild(div);
  }
}
// table view
const allRows = [];
for (const g of groups) for (const row of g.rows) for (const i of row.items) allRows.push([row.lab, i]);
document.getElementById('claimTable').innerHTML = '<table><thead><tr><th>Claim</th><th>Kind</th><th>Result</th></tr></thead><tbody>' +
  allRows.map(([lab, i]) => `<tr><td>${esc(i.label)}${i.why ? `<br><small>${esc(i.why)}</small>` : ''}</td><td>${lab}</td>` +
    `<td class="${i.ok ? '' : 'x'}">${i.ok ? 'right' : 'wrong'}</td></tr>`).join('') + '</tbody></table>';

// ---------- experiment: the three transpositions ----------
const SWAPS = [
  { word: 'bear', phrase: 'the zebra roams' },
  { word: 'mole', phrase: 'home lesson' },
  { word: 'tuba', phrase: 'cut back' },
];
function swapFigure({ word, phrase }) {
  const chars = phrase.toLowerCase().split('');
  const letters = chars.map((ch, i) => ({ ch, i })).filter(x => /[a-z]/.test(x.ch));
  const W = word.toLowerCase(), k = W.length, sorted = W.split('').sort().join('');
  let start = -1;
  for (let s = 0; s + k <= letters.length; s++) {
    if (letters.slice(s, s + k).map(x => x.ch).sort().join('') === sorted) { start = s; break; }
  }
  const win = letters.slice(start, start + k);
  const box = 30, gapX = 4, spaceW = 14, topY = 6, botY = 104;
  // x position of each phrase character
  let x = 2;
  const xs = chars.map(ch => {
    const at = x;
    x += ch === ' ' ? spaceW : box + gapX;
    return at;
  });
  const width = x;
  const winMid = (xs[win[0].i] + xs[win[k - 1].i] + box) / 2;
  const claimX = i => winMid - (k * (box + gapX) - gapX) / 2 + i * (box + gapX);
  const used = new Set();
  const map = W.split('').map(ch => {
    const j = win.findIndex((w, idx) => w.ch === ch && !used.has(idx));
    used.add(j);
    return j;
  });
  let svg = `<svg viewBox="0 0 ${Math.max(width, claimX(k) + 4)} ${botY + box + 6}" width="${Math.max(width, claimX(k) + 4)}" role="img" aria-label="${word} claimed in ${phrase}; the letters are there in a different order">`;
  map.forEach((j, i) => {
    const x1 = claimX(i) + box / 2, x2 = xs[win[j].i] + box / 2;
    const crossed = j !== i;
    svg += `<path class="wire${crossed ? ' x' : ''}" d="M${x1} ${botY} C ${x1} ${botY - 34}, ${x2} ${topY + box + 34}, ${x2} ${topY + box}"/>`;
  });
  chars.forEach((ch, i) => {
    if (ch === ' ') return;
    const hit = win.some(w => w.i === i);
    svg += `<rect class="box${hit ? ' hit' : ''}" x="${xs[i]}" y="${topY}" width="${box}" height="${box}" rx="2"/>` +
      `<text class="t" x="${xs[i] + box / 2}" y="${topY + box / 2 + 7}" text-anchor="middle">${ch}</text>`;
  });
  W.split('').forEach((ch, i) => {
    svg += `<rect class="box claim" x="${claimX(i)}" y="${botY}" width="${box}" height="${box}" rx="2"/>` +
      `<text class="t tw" x="${claimX(i) + box / 2}" y="${botY + box / 2 + 7}" text-anchor="middle">${ch.toUpperCase()}</text>`;
  });
  svg += '</svg>';
  const there = win.map(w => w.ch.toUpperCase()).join('\u2011');
  return `<figure class="swap">${svg}<figcaption>I claimed <b>${word.toUpperCase()}</b> was hidden in &ldquo;${phrase}&rdquo;. ` +
    `What's actually there is ${there}. Red lines cross where the order is wrong.</figcaption></figure>`;
}
document.getElementById('swaps').innerHTML = SWAPS.map(swapFigure).join('');
