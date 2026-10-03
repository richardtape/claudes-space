// Eight synthesised tower bells. Each bell is rendered once into an AudioBuffer by
// additive synthesis of the partials of a "true-harmonic" church bell, measured relative
// to the nominal: hum (two octaves down), prime (an octave down), tierce (a minor third
// above the prime, which gives bells their minor-key colour), quint, nominal and the
// upper partials. Each partial is a slightly detuned pair, so it beats slowly, as real
// bells (which are never perfectly round) do. Higher partials die away faster.
const Bells = (() => {
  // [ratio to nominal, amplitude, decay multiplier]
  const PARTIALS = [
    [0.250, 0.50, 2.6], [0.500, 0.42, 1.8], [0.600, 0.46, 1.4], [0.750, 0.10, 1.0],
    [1.000, 1.00, 1.0], [1.256, 0.26, 0.60], [1.335, 0.10, 0.50], [1.498, 0.20, 0.42],
    [2.000, 0.12, 0.32], [2.520, 0.07, 0.22], [3.010, 0.05, 0.16],
  ];
  const TENOR = 622.25;            // nominal of the tenor, E-flat
  const SCALE = [12, 11, 9, 7, 5, 4, 2, 0]; // semitones above the tenor, treble first

  function nominal(bell) { return TENOR * Math.pow(2, SCALE[bell - 1] / 12); }

  function render(ctx, bell, seconds) {
    const sr = ctx.sampleRate, n = Math.floor(sr * seconds);
    const buf = ctx.createBuffer(1, n, sr), d = buf.getChannelData(0);
    const f0 = nominal(bell);
    const t60 = 3.6 + 3.4 * (bell - 1) / 7;   // the nominal's ring time: treble 3.6 s, tenor 7 s
    let seed = 1234 + bell * 77;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (const [ratio, amp, dm] of PARTIALS) {
      const f = f0 * ratio;
      if (f > sr / 2.2) continue;
      const k = 6.91 / (t60 * dm);
      for (const [df, a] of [[1, amp], [1 + 0.0011 + 0.0007 * rnd(), amp * 0.45]]) {
        const w = 2 * Math.PI * f * df / sr, ph = rnd() * 6.283, kd = Math.exp(-k / sr);
        // sin(w i + ph) * exp(-k i/sr), by recurrence for speed
        let env = a, s1 = Math.sin(ph - w), s2 = Math.sin(ph - 2 * w);
        const c = 2 * Math.cos(w);
        for (let i = 0; i < n; i++) {
          const s0 = c * s1 - s2; s2 = s1; s1 = s0;
          d[i] += s0 * env; env *= kd;
          if (env < 1e-5) break;
        }
      }
    }
    // the strike: a few milliseconds of bright noise
    let lp = 0;
    for (let i = 0; i < sr * 0.012; i++) {
      lp += 0.5 * ((rnd() * 2 - 1) - lp);
      d[i] += lp * 0.5 * Math.exp(-i / (sr * 0.0025));
    }
    // soft attack, fade tail, normalise
    let peak = 0;
    const att = Math.floor(sr * 0.0015), fade = Math.floor(sr * 0.4);
    for (let i = 0; i < n; i++) {
      if (i < att) d[i] *= i / att;
      if (i > n - fade) d[i] *= (n - i) / fade;
      peak = Math.max(peak, Math.abs(d[i]));
    }
    const g = 0.32 / peak;
    for (let i = 0; i < n; i++) d[i] *= g;
    return buf;
  }

  function impulse(ctx, seconds, decay) {
    const sr = ctx.sampleRate, n = Math.floor(sr * seconds);
    const buf = ctx.createBuffer(2, n, sr);
    for (let ch = 0; ch < 2; ch++) {
      const d = buf.getChannelData(ch); let s = 99 + ch;
      for (let i = 0; i < n; i++) {
        s = (s * 16807) % 2147483647;
        d[i] = ((s / 2147483647) * 2 - 1) * Math.pow(1 - i / n, decay);
      }
    }
    return buf;
  }

  // An instrument: eight bells placed round a circle, through a little room.
  function create(Ctx) {
    const ctx = new Ctx();
    const master = ctx.createGain(); master.gain.value = 0.9;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -14; comp.ratio.value = 3;
    master.connect(comp); comp.connect(ctx.destination);
    const verb = ctx.createConvolver(); verb.buffer = impulse(ctx, 2.6, 3.2);
    const wet = ctx.createGain(); wet.gain.value = 0.32;
    verb.connect(wet); wet.connect(master);
    const buffers = [], outs = [];
    for (let b = 1; b <= 8; b++) {
      buffers[b] = render(ctx, b, 5.5 + 0.5 * (b - 1) / 7);
      const pan = ctx.createStereoPanner ? ctx.createStereoPanner() : ctx.createGain();
      if (pan.pan) pan.pan.value = 0.55 * Math.sin((b - 0.5) / 8 * 2 * Math.PI);
      pan.connect(master); pan.connect(verb);
      outs[b] = pan;
    }
    function strike(bell, when, gain = 1) {
      const src = ctx.createBufferSource(); src.buffer = buffers[bell];
      const g = ctx.createGain(); g.gain.value = gain;
      src.connect(g); g.connect(outs[bell]);
      src.start(when);
      return src;
    }
    return { ctx, strike, master };
  }
  return { create, nominal, render, PARTIALS };
})();
if (typeof module !== 'undefined') module.exports = Bells;
