const assert = require('assert');
const R = require('../page/core.js');
let n = 0; const t = (name, f) => { f(); n++; console.log('ok', name); };

t('plain course comes round after 70 rows, true', () => {
  const { rows, end } = R.expand('ppppp');
  assert.strictEqual(rows.length, 70); assert.deepStrictEqual(end, R.ROUNDS);
  assert.strictEqual(new Set(rows.map(R.key)).size, 70);
});
t('plain lead heads match the published ones', () => {
  const lhs = []; let lh = R.ROUNDS;
  for (let i = 0; i < 4; i++) { lh = R.lead(lh, 'p').next; lhs.push(R.key(lh)); }
  assert.deepStrictEqual(lhs, ['1253746', '1275634', '1267453', '1246375']);
});
t('bob and single lead heads agree with python', () => {
  assert.strictEqual(R.key(R.lead(R.ROUNDS, 'b').next), '1752634');
  assert.strictEqual(R.key(R.lead(R.ROUNDS, 's').next), '1572634');
});
t('three bobs come round (the B-block)', () => assert.deepStrictEqual(R.expand('bbb').end, R.ROUNDS));
t('Q-set model: 360 lead heads, 72 courses, 72 Q-sets of 5', () => {
  const m = R.qsetModel();
  assert.strictEqual(m.lhs.length, 360); assert.strictEqual(m.courses.length, 72);
  assert.strictEqual(m.qsets.length, 72); assert.ok(m.qsets.every(q => q.length === 5));
  assert.ok(m.qsets.every(q => new Set(q.map(i => m.course[i])).size === 5));
  assert.strictEqual(R.blocks(m, new Set()).sizes.length, 72);
});
t('parity: random bob choices always give an even number of round blocks', () => {
  const m = R.qsetModel(); let seed = 7;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let k = 0; k < 300; k++) {
    const s = new Set(); for (let q = 0; q < 72; q++) if (rnd() < 0.4) s.add(q);
    assert.strictEqual(R.blocks(m, s).sizes.length % 2, 0);
  }
});
if (process.argv[2]) t('composition is true', () => {
  const c = require('fs').readFileSync(process.argv[2], 'utf8').trim();
  const r = R.check(c); console.log('  ', r);
  assert.strictEqual(r.rows, 5040); assert.strictEqual(r.distinct, 5040); assert.ok(r.round);
});
console.log(n, 'passed');
