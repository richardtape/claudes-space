(function () {
  "use strict";
  var C = window.NightCore, DATA = window.NIGHT_DATA, S = DATA.sonnets;
  var ROW_ORDER = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0];
  var SHORT = { 0: "writer", 1: "keeper", 2: "baker", 3: "nurse", 4: "astronomer",
                5: "signalman", 6: "compositor", 7: "parent", 8: "moth-trapper", 9: "gritter" };
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (id) { return document.getElementById(id); };
  var book = $("book"), grid = $("grid");
  var digits = null, tonight = C.tonightsNumber(new Date());
  var strips = [], cells = [];

  function lamp(d) { return "var(--l" + d + ")"; }

  // ---- build the book ----
  for (var k = 0; k < C.LINES; k++) {
    var li = document.createElement("li");
    var b = document.createElement("button");
    b.type = "button"; b.className = "strip"; b.dataset.k = k;
    b.innerHTML = '<span class="lamp" aria-hidden="true"></span><span class="txt"></span>';
    li.appendChild(b); book.appendChild(li); strips.push(b);
    b.addEventListener("click", function (e) {
      var k = +this.dataset.k;
      set(C.turn(digits, k, e.shiftKey ? -1 : 1), [k], e.shiftKey ? -1 : 1);
    });
    b.addEventListener("keydown", function (e) {
      var k = +this.dataset.k, step = 0;
      if (e.key === "ArrowRight") step = 1;
      else if (e.key === "ArrowLeft") step = -1;
      else if (e.key === "ArrowDown" && k < C.LINES - 1) { strips[k + 1].focus(); e.preventDefault(); }
      else if (e.key === "ArrowUp" && k > 0) { strips[k - 1].focus(); e.preventDefault(); }
      if (step) { e.preventDefault(); set(C.turn(digits, k, step), [k], step); }
    });
  }

  // ---- build the timesheet ----
  var head = "<thead><tr><th scope=\"col\"><span class=\"visually-hidden\">Worker</span></th>";
  for (k = 1; k <= C.LINES; k++) head += "<th scope=\"col\" aria-label=\"Line " + k + "\">" + k + "</th>";
  grid.innerHTML = head + "</tr></thead><tbody></tbody>";
  var tbody = grid.querySelector("tbody");
  ROW_ORDER.forEach(function (d) {
    var tr = document.createElement("tr");
    var th = document.createElement("th"); th.scope = "row";
    var who = document.createElement("button");
    who.type = "button"; who.className = "who"; who.style.setProperty("--c", lamp(d));
    who.innerHTML = '<span class="d">' + d + '</span><span class="dot" aria-hidden="true"></span><span class="name">' + SHORT[d] + "</span>";
    who.setAttribute("aria-label", "Read the " + S[d].job + "'s own sonnet");
    who.addEventListener("click", function () { set(new Array(C.LINES).fill(d)); });
    th.appendChild(who); tr.appendChild(th);
    cells[d] = [];
    for (var k = 0; k < C.LINES; k++) {
      var td = document.createElement("td");
      var c = document.createElement("button");
      c.type = "button"; c.className = "cell"; c.style.setProperty("--c", lamp(d));
      c.setAttribute("aria-label", "Line " + (k + 1) + " from the " + S[d].job);
      (function (d, k) {
        c.addEventListener("click", function () {
          if (digits[k] === d) return;
          var next = digits.slice(); next[k] = d; set(next, [k], 1);
        });
      })(d, k);
      td.appendChild(c); tr.appendChild(td); cells[d].push(c);
    }
    tbody.appendChild(tr);
  });

  // ---- state ----
  // Turning forward: the old strip lifts off the spine and swings away, uncovering the next.
  // Turning back: the previous strip swings back over from the spine and lands on the old one.
  function copyOf(strip, cls) {
    var g = strip.cloneNode(true);
    g.className = "strip ghost " + cls;
    g.removeAttribute("data-k"); g.removeAttribute("aria-label");
    g.setAttribute("aria-hidden", "true"); g.tabIndex = -1;
    return g;
  }
  function play(strip, before, step) {
    var li = strip.parentNode, els = [before], mover = before;
    if (step < 0) { mover = copyOf(strip, "in"); els.push(mover); }
    els.forEach(function (e) { li.appendChild(e); });
    var done = function () { els.forEach(function (e) { if (e.isConnected) e.remove(); }); };
    mover.addEventListener("animationend", done);
    setTimeout(done, 900);
  }

  function describe() {
    var info = C.describe(digits, S), same = digits.join("") === tonight.join("");
    if (info.kind === "hidden") return "The eleventh sonnet, the one written first.";
    if (info.kind === "original") return "The " + S[info.digit].job + "'s own sonnet, as written.";
    return (same ? "Tonight's sonnet. " : "") +
      (info.workers === 10 ? "Lines from all ten." : "Lines from " + info.workers + " of the ten.");
  }

  function set(next, changed, step) {
    var animate = digits !== null;
    var old = digits;
    digits = next;
    var moves = [];
    for (var k = 0; k < C.LINES; k++) {
      var d = digits[k], strip = strips[k];
      if (animate && !reduce && old[k] !== d) {
        var dir = (changed && changed.indexOf(k) >= 0 && step < 0) ? -1 : 1;
        moves.push([strip, copyOf(strip, dir < 0 ? "cover" : "out"), dir]);
      }
      strip.querySelector(".txt").textContent = S[d].lines[k];
      strip.querySelector(".lamp").style.setProperty("--c", lamp(d));
      strip.setAttribute("aria-label", S[d].lines[k] + " (line " + (k + 1) + ", the " + S[d].job +
        "). Arrow right or click for the next sonnet's line.");
      ROW_ORDER.forEach(function (r) { cells[r][k].setAttribute("aria-pressed", r === d ? "true" : "false"); });
    }
    moves.forEach(function (m) { play(m[0], m[1], m[2]); });
    $("num").textContent = C.formatNumber(digits);
    $("status").textContent = describe();
    var hash = "#" + digits.join("");
    if (location.hash !== hash) {
      try { history.replaceState(null, "", hash); } catch (e) { /* some file:// setups refuse */ }
    }
  }

  $("shuffle").addEventListener("click", function () { set(C.randomNumber(Math.random)); });
  $("tonight").addEventListener("click", function () { set(tonight.slice()); });
  $("goto").addEventListener("submit", function (e) {
    e.preventDefault();
    var input = $("goto-input"), d = C.parseNumber(input.value);
    if (!d) { input.setAttribute("aria-invalid", "true"); input.focus(); return; }
    input.removeAttribute("aria-invalid"); input.value = "";
    set(d);
  });
  $("goto-input").addEventListener("input", function () { this.removeAttribute("aria-invalid"); });
  window.addEventListener("hashchange", function () {
    var d = C.parseNumber(location.hash);
    if (d && d.join("") !== digits.join("")) set(d);
  });
  var reveal = $("reveal");
  if (reveal) reveal.addEventListener("click", function (e) {
    e.preventDefault(); set(C.parseNumber("12345678901234"));
    book.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
  });

  set(C.parseNumber(location.hash) || tonight.slice());
})();
