// Pure functions shared by the page and the Node tests. No DOM here.
(function (root) {
  "use strict";

  function b64ToInt16(b64) {
    const bin = typeof atob === "function" ? atob(b64) : Buffer.from(b64, "base64").toString("binary");
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Int16Array(bytes.buffer);
  }

  // modes[k][tile][node] flattened; each mode was scaled to int16 by its own max.
  function decodeModes(b64, scales, m, tiles, nl) {
    const q = b64ToInt16(b64);
    const out = new Float32Array(m * tiles * nl);
    const per = tiles * nl;
    for (let k = 0; k < m; k++) {
      const s = scales[k] / 32767;
      for (let i = 0; i < per; i++) out[k * per + i] = q[k * per + i] * s;
    }
    return out;
  }

  // Same numbering as fem.base_mesh: node (i, j) has barycentric weights (i/N, j/N, 1 - i/N - j/N).
  function baseMesh(N) {
    const idx = {};
    const bary = [];
    for (let i = 0; i <= N; i++)
      for (let j = 0; j <= N - i; j++) {
        idx[i + "," + j] = bary.length / 3;
        bary.push(i / N, j / N, (N - i - j) / N);
      }
    const tris = [];
    for (let i = 0; i < N; i++)
      for (let j = 0; j < N - i; j++) {
        tris.push(idx[i + "," + j], idx[i + 1 + "," + j], idx[i + "," + (j + 1)]);
        if (i + j < N - 1) tris.push(idx[i + 1 + "," + j], idx[i + 1 + "," + (j + 1)], idx[i + "," + (j + 1)]);
      }
    return { bary: Float64Array.from(bary), tris: Uint16Array.from(tris), nl: bary.length / 3 };
  }

  // Local coordinates of the base-mesh nodes in the base triangle.
  function localXY(mesh, tri) {
    const n = mesh.nl, xy = new Float64Array(2 * n);
    for (let p = 0; p < n; p++) {
      const a = mesh.bary[3 * p], b = mesh.bary[3 * p + 1], c = mesh.bary[3 * p + 2];
      xy[2 * p] = a * tri[0][0] + b * tri[1][0] + c * tri[2][0];
      xy[2 * p + 1] = a * tri[0][1] + b * tri[1][1] + c * tri[2][1];
    }
    return xy;
  }

  function triArea(tri) {
    return Math.abs((tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1]) - (tri[1][1] - tri[0][1]) * (tri[2][0] - tri[0][0])) / 2;
  }

  // Integral of u^2 over the drum (area = whole drum), P1 elements: tri area/6 * (sum u_i^2 + sum_{i<j} u_i u_j) per small triangle.
  function modeNorm2(modes, k, tiles, mesh, area) {
    const nl = mesh.nl, t = mesh.tris, base = k * tiles * nl;
    const a = area / tiles / (t.length / 3) / 6;     // area of one small triangle, over 6
    let s = 0;
    for (let p = 0; p < tiles; p++) {
      const o = base + p * nl;
      for (let e = 0; e < t.length; e += 3) {
        const u = modes[o + t[e]], v = modes[o + t[e + 1]], w = modes[o + t[e + 2]];
        s += u * u + v * v + w * w + u * v + v * w + u * w;
      }
    }
    return s * a;
  }

  function normalize(modes, m, tiles, mesh, area) {
    const per = tiles * mesh.nl;
    for (let k = 0; k < m; k++) {
      const f = 1 / Math.sqrt(modeNorm2(modes, k, tiles, mesh, area));
      for (let i = 0; i < per; i++) modes[k * per + i] *= f;
    }
    return modes;
  }

  // B's mode on tile j = sum_i T[j][i] * (A's mode on tile i), all in base-triangle coordinates.
  function transplant(modesA, T, m, tiles, nl) {
    const out = new Float32Array(modesA.length), per = tiles * nl;
    for (let k = 0; k < m; k++)
      for (let j = 0; j < tiles; j++)
        for (let i = 0; i < tiles; i++) {
          const c = T[j][i];
          if (!c) continue;
          const dst = k * per + j * nl, src = k * per + i * nl;
          for (let n = 0; n < nl; n++) out[dst + n] += c * modesA[src + n];
        }
    return out;
  }

  // T3 transplant scaled to keep unit norm: T3^T T3 = 2I + (signed all-ones), so a mode that is the
  // same on every tile up to sign (a "triangle mode") grows by 3 and every other mode by sqrt(2).
  function transplantGWW(modesA, T, m, tiles, nl, triModes) {
    const out = transplant(modesA, T, m, tiles, nl), per = tiles * nl, tri = new Set(triModes);
    for (let k = 0; k < m; k++) {
      const f = tri.has(k) ? 1 / 3 : Math.SQRT1_2;
      for (let i = 0; i < per; i++) out[k * per + i] *= f;
    }
    return out;
  }

  // Make the largest-magnitude value of each mode positive.
  function fixSign(modes, m, per) {
    for (let k = 0; k < m; k++) {
      let best = 0;
      for (let i = 0; i < per; i++) if (Math.abs(modes[k * per + i]) > Math.abs(best)) best = modes[k * per + i];
      if (best < 0) for (let i = 0; i < per; i++) modes[k * per + i] *= -1;
    }
    return modes;
  }

  // Unfold a gluing pattern: affine placements [a, b, c, d, e, f] with x' = a x + b y + c, y' = d x + e y + f.
  function reflection(P, Q) {
    const dx = Q[0] - P[0], dy = Q[1] - P[1], L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L;
    const r00 = 2 * ux * ux - 1, r01 = 2 * ux * uy, r11 = 2 * uy * uy - 1;
    return [r00, r01, P[0] - (r00 * P[0] + r01 * P[1]), r01, r11, P[1] - (r01 * P[0] + r11 * P[1])];
  }
  function compose(M, N) { // M after N
    return [M[0] * N[0] + M[1] * N[3], M[0] * N[1] + M[1] * N[4], M[0] * N[2] + M[1] * N[5] + M[2],
            M[3] * N[0] + M[4] * N[3], M[3] * N[1] + M[4] * N[4], M[3] * N[2] + M[4] * N[5] + M[5]];
  }
  function apply(M, x, y) { return [M[0] * x + M[1] * y + M[2], M[3] * x + M[4] * y + M[5]]; }
  function unfold(perms, tri) {
    const n = perms[0].length;
    const refl = [0, 1, 2].map(k => reflection(tri[(k + 1) % 3], tri[(k + 2) % 3]));
    const place = new Array(n).fill(null);
    place[0] = [1, 0, 0, 0, 1, 0];
    const stack = [0];
    while (stack.length) {
      const p = stack.pop();
      for (let k = 0; k < 3; k++) {
        const q = perms[k][p];
        if (q !== p && !place[q]) { place[q] = compose(place[p], refl[k]); stack.push(q); }
      }
    }
    return place;
  }
  function tileVerts(place, tri) { return place.map(M => tri.map(v => apply(M, v[0], v[1]))); }
  function triangleFromAngles(alpha, beta) { // degrees at V0 and V1, |V0V1| = 1
    const a = alpha * Math.PI / 180, b = beta * Math.PI / 180, g = Math.PI - a - b;
    const r = Math.sin(b) / Math.sin(g);
    return [[0, 0], [1, 0], [r * Math.cos(a), r * Math.sin(a)]];
  }

  // A bank of damped resonators: sum_k amps[k] sin(2 pi f_k t) exp(-t / tau_k).
  function synth(freqs, amps, taus, sampleRate, dur) {
    const n = Math.floor(sampleRate * dur), out = new Float32Array(n), dt = 1 / sampleRate;
    for (let k = 0; k < freqs.length; k++) {
      const A = amps[k];
      if (!(Math.abs(A) > 1e-7) || freqs[k] > sampleRate * 0.45) continue;
      const w = 2 * Math.PI * freqs[k] * dt, r = Math.exp(-dt / taus[k]);
      const c = 2 * r * Math.cos(w), r2 = r * r;
      let y1 = A * r * Math.sin(w), y2 = 0;   // y[1], y[0]
      out[1] += y1;
      const end = Math.min(n, Math.ceil(taus[k] * sampleRate * 9.3));   // stop near -80 dB
      for (let i = 2; i < end; i++) {
        const y = c * y1 - r2 * y2;
        out[i] += y;
        y2 = y1; y1 = y;
      }
    }
    const ramp = Math.floor(0.002 * sampleRate);
    for (let i = 0; i < ramp && i < n; i++) out[i] *= i / ramp;
    return out;
  }

  const NOTE = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];
  function noteName(f) {
    const midi = 69 + 12 * Math.log2(f / 440), r = Math.round(midi), cents = Math.round((midi - r) * 100);
    const name = NOTE[((r % 12) + 12) % 12] + (Math.floor(r / 12) - 1);
    return { name, cents };
  }

  const api = { b64ToInt16, decodeModes, baseMesh, localXY, triArea, modeNorm2, normalize, transplant, transplantGWW, fixSign,
                unfold, tileVerts, apply, triangleFromAngles, synth, noteName };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Drums = api;
})(this);
