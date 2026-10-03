// node tests/core.test.js  — checks page logic against page_data.json
const assert = require("assert");
const path = require("path");
const core = require(path.join(__dirname, "..", "page", "core.js"));
const data = require(path.join(__dirname, "..", "page_data.json"));
let n = 0;
function ok(name, fn) { fn(); n++; console.log("ok  " + name); }

ok("parse and format round-trip", () => {
  const d = core.parseNumber("No. 12345 67890 1234");
  assert.deepStrictEqual(d, [1,2,3,4,5,6,7,8,9,0,1,2,3,4]);
  assert.strictEqual(core.formatNumber(d), "12345 67890 1234");
  assert.deepStrictEqual(core.parseNumber("#00000000000000"), new Array(14).fill(0));
});
ok("parse rejects wrong lengths and letters", () => {
  assert.strictEqual(core.parseNumber("1234"), null);
  assert.strictEqual(core.parseNumber("123456789012345"), null);
  assert.strictEqual(core.parseNumber("12345abc678901234"), null);
  assert.strictEqual(core.parseNumber(undefined), null);
});
ok("turning wraps both ways", () => {
  const d = new Array(14).fill(9);
  assert.strictEqual(core.turn(d, 3, 1)[3], 0);
  assert.strictEqual(core.turn(new Array(14).fill(0), 3, -1)[3], 9);
  assert.strictEqual(d[3], 9, "turn must not mutate");
});
ok("tonight's sonnet is stable through the night and changes next evening", () => {
  const eve = core.tonightsNumber(new Date(2026, 9, 1, 21, 0));
  const small = core.tonightsNumber(new Date(2026, 9, 2, 3, 30));
  const next = core.tonightsNumber(new Date(2026, 9, 2, 21, 0));
  assert.deepStrictEqual(eve, small);
  assert.notDeepStrictEqual(eve, next);
  eve.forEach(x => assert.ok(Number.isInteger(x) && x >= 0 && x <= 9));
});
ok("compose picks line k from sonnet d", () => {
  const lines = core.compose(data.sonnets, [1,2,3,4,5,6,7,8,9,0,1,2,3,4]);
  assert.strictEqual(lines[0], data.sonnets[1].lines[0]);
  assert.strictEqual(lines[9], data.sonnets[0].lines[9]);
  assert.strictEqual(lines[13], data.sonnets[4].lines[13]);
});
ok("data: ten sonnets of fourteen lines, indexed by digit", () => {
  assert.strictEqual(data.sonnets.length, 10);
  data.sonnets.forEach((s, i) => { assert.strictEqual(s.digit, i); assert.strictEqual(s.lines.length, 14); });
});
ok("describe names originals and the hidden one", () => {
  assert.strictEqual(core.describe(new Array(14).fill(7), data.sonnets).kind, "original");
  assert.strictEqual(core.describe([1,2,3,4,5,6,7,8,9,0,1,2,3,4], data.sonnets).kind, "hidden");
  assert.strictEqual(core.describe([1,1,2,2,3,3,4,4,5,5,6,6,7,7], data.sonnets).workers, 7);
});
ok("random numbers average about 7.7 workers (exact 7.712)", () => {
  const rand = core.mulberry32(42);
  let sum = 0; const N = 20000;
  for (let i = 0; i < N; i++) sum += core.distinctWorkers(core.randomNumber(rand));
  assert.ok(Math.abs(sum / N - data.stats.mean_distinct) < 0.03, sum / N);
});
console.log(n + " checks passed");
