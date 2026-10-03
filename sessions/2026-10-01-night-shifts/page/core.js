// Pure logic for the strip book, shared by the page and tests/core.test.js.
(function (root) {
  "use strict";

  var LINES = 14;

  // "12345 67890 1234", "#12345678901234", "1234567890-1234" -> [1,2,...] or null
  function parseNumber(text) {
    if (typeof text !== "string") return null;
    var digits = text.replace(/[^0-9]/g, "");
    if (digits.length !== LINES) return null;
    if (/[^0-9\s#.\-–—]/.test(text.replace(/^No\.?/i, ""))) return null;
    return digits.split("").map(Number);
  }

  function formatNumber(digits) {
    var s = digits.join("");
    return s.slice(0, 5) + " " + s.slice(5, 10) + " " + s.slice(10);
  }

  // Small deterministic PRNG so "tonight's sonnet" is the same for everyone on a date.
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function randomNumber(rand) {
    var out = [];
    for (var k = 0; k < LINES; k++) out.push(Math.floor(rand() * 10));
    return out;
  }

  // The night belongs to the evening it started: before 6 a.m. counts as the previous date.
  function nightOf(date) {
    var d = new Date(date.getTime());
    if (d.getHours() < 6) d.setDate(d.getDate() - 1);
    return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
  }

  function tonightsNumber(date) {
    return randomNumber(mulberry32(nightOf(date)));
  }

  function turn(digits, k, step) {
    var out = digits.slice();
    out[k] = (out[k] + step + 10) % 10;
    return out;
  }

  function compose(sonnets, digits) {
    return digits.map(function (d, k) { return sonnets[d].lines[k]; });
  }

  function distinctWorkers(digits) {
    var seen = {};
    digits.forEach(function (d) { seen[d] = true; });
    return Object.keys(seen).length;
  }

  // Which named thing this number is, if any.
  function describe(digits, sonnets) {
    var s = digits.join("");
    if (s === "12345678901234") return { kind: "hidden" };
    if (/^(\d)\1{13}$/.test(s)) return { kind: "original", digit: digits[0], title: sonnets[digits[0]].title };
    return { kind: "mixed", workers: distinctWorkers(digits) };
  }

  var api = {
    LINES: LINES, parseNumber: parseNumber, formatNumber: formatNumber, mulberry32: mulberry32,
    randomNumber: randomNumber, nightOf: nightOf, tonightsNumber: tonightsNumber, turn: turn,
    compose: compose, distinctWorkers: distinctWorkers, describe: describe
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NightCore = api;
})(this);
