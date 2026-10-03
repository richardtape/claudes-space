// Change-ringing core for Grandsire Triples. Pure functions; shared with the Node tests.
// A row is an array of bell numbers (1-based) in striking order. Seven working bells;
// the tenor (8) always rings last and is added only for display and sound.
const Ring = (() => {
  const N = 7;
  const ROUNDS = [1, 2, 3, 4, 5, 6, 7];
  const parsePN = s => s.split('.').map(t => new Set([...t].map(Number)));
  const PLAIN = parsePN('3.1.7.1.7.1.7.1.7.1.7.1.7.1');
  const CALLS = { p: PLAIN, b: PLAIN.slice(0, 12).concat(parsePN('3.1')), s: PLAIN.slice(0, 12).concat(parsePN('3.123')) };

  function change(row, places) {
    const r = row.slice();
    for (let i = 0; i < r.length;) {
      if (places.has(i + 1)) { i += 1; continue; }
      const t = r[i]; r[i] = r[i + 1]; r[i + 1] = t; i += 2;
    }
    return r;
  }
  // rows of one lead from lead head lh (inclusive) and the next lead head
  function lead(lh, call) {
    const rows = [lh]; let r = lh;
    for (const ch of CALLS[call]) { r = change(r, ch); rows.push(r); }
    const next = rows.pop();
    return { rows, next };
  }
  // expand a calling string ('p','b','s' per lead) into rows; rows[0] is rounds
  function expand(calling) {
    const rows = []; let lh = ROUNDS;
    for (const c of calling) { const L = lead(lh, c); rows.push(...L.rows); lh = L.next; }
    return { rows, end: lh };
  }
  const key = r => r.join('');
  function check(calling) {
    const { rows, end } = expand(calling);
    const seen = new Set(rows.map(key));
    return { rows: rows.length, distinct: seen.size, round: key(end) === key(ROUNDS),
             bobs: [...calling].filter(c => c === 'b').length, singles: [...calling].filter(c => c === 's').length };
  }
  function parity(row) {
    const r = row.slice(); let p = 0;
    for (let i = 0; i < r.length; i++) while (r[i] !== i + 1) { const j = r[i] - 1; [r[i], r[j]] = [r[j], r[i]]; p ^= 1; }
    return p;
  }
  // x then the transformation that takes rounds to y
  const compose = (x, y) => y.map(b => x[b - 1]);

  // The 360 in-course lead heads, plain and bob successors, courses and bob Q-sets.
  function qsetModel() {
    const perms = [];
    (function gen(pre, rest) {
      if (!rest.length) { perms.push(pre); return; }
      rest.forEach((b, i) => gen(pre.concat(b), rest.slice(0, i).concat(rest.slice(i + 1))));
    })([1], [2, 3, 4, 5, 6, 7]);
    const lhs = perms.filter(r => parity(r) === 0);
    const idx = new Map(lhs.map((r, i) => [key(r), i]));
    const P = lead(ROUNDS, 'p').next, B = lead(ROUNDS, 'b').next;
    const plain = lhs.map(r => idx.get(key(compose(r, P))));
    const bob = lhs.map(r => idx.get(key(compose(r, B))));
    const ppred = []; plain.forEach((j, i) => { ppred[j] = i; });
    const course = new Array(lhs.length).fill(-1), courses = [];
    for (let i = 0; i < lhs.length; i++) {
      if (course[i] >= 0) continue;
      const c = []; let j = i;
      while (course[j] < 0) { course[j] = courses.length; c.push(j); j = plain[j]; }
      courses.push(c);
    }
    const qset = new Array(lhs.length).fill(-1), qsets = [];
    for (let i = 0; i < lhs.length; i++) {
      if (qset[i] >= 0) continue;
      const q = []; let j = i;
      while (qset[j] < 0) { qset[j] = qsets.length; q.push(j); j = ppred[bob[j]]; }
      qsets.push(q);
    }
    return { lhs: lhs.map(key), idx, plain, bob, course, courses, qset, qsets, rounds: idx.get(key(ROUNDS)) };
  }
  // round blocks when the Q-sets in `bobbed` (a Set of Q-set ids) are bobbed
  function blocks(m, bobbed) {
    const n = m.lhs.length, id = new Array(n).fill(-1), sizes = [];
    for (let i = 0; i < n; i++) {
      if (id[i] >= 0) continue;
      let j = i, s = 0;
      while (id[j] < 0) { id[j] = sizes.length; s++; j = bobbed.has(m.qset[j]) ? m.bob[j] : m.plain[j]; }
      sizes.push(s);
    }
    return { id, sizes };
  }

  return { N, ROUNDS, PLAIN, CALLS, change, lead, expand, check, parity, compose, key, qsetModel, blocks };
})();
if (typeof module !== 'undefined') module.exports = Ring;
