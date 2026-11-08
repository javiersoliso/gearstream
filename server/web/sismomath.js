// La matemática del juego del sismógrafo: la línea que hay que seguir y lo que tu brazo hizo con ella.
//
// La línea es una suma de senos r(t) = Σ a_k sin(2π f_k t + φ_k) con f_k = k/T: todas dan un número entero
// de vueltas en T segundos, así que r se repite cada T y en una ventana de T segundos cada seno cae justo
// en una casilla de la transformada de Fourier, sin fugas. Con fases al azar la línea parece imprevisible.
//
// Al terminar, con tu aguja y(t):
//   retraso τ:   el desplazamiento que más alinea y(t) con r(t − τ) (correlación); τ > 0 llegas tarde,
//                τ < 0 te adelantas (pasa cuando ves la línea venir).
//   por frecuencia, H_k = Y(f_k) / R(f_k):
//     |H_k|            cuánto de esa onda reprodujiste (1 = toda),
//     −∠H_k / (2π f_k) tu retraso a esa frecuencia, si es de menos de media vuelta de la onda,
//     |1 − H_k|        el error que te quedó a esa frecuencia, relativo a la onda (0 = la borraste).
//   remanente: la parte de tu movimiento que no está en ninguna de las frecuencias de la línea (temblor,
//              correcciones): tu "ruido". Es un piso: lo muy lento se fuga a esas casillas y cuenta como seguido.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SismoMath = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const T = 20;              // s: periodo de la línea y duración de lo que se mide
  const LEAD = 2;            // s: antes de medir, la línea crece desde cero
  const LEVELS = [
    { name: 'tranquilo', k: [1, 2, 3, 4] },             // 0.05 a 0.2 Hz
    { name: 'normal', k: [1, 2, 3, 5, 8] },             // hasta 0.4 Hz
    { name: 'sismo', k: [2, 3, 5, 8, 13, 17] },         // hasta 0.85 Hz
  ];
  const PEAK = 0.75;         // la suma de amplitudes, en medias alturas de pantalla: nunca se sale

  function makeTarget(level, rand) {
    rand = rand || Math.random;
    const ks = LEVELS[level].k;
    const raw = ks.map((k) => 1 / (1 + k / T / 0.25));   // las ondas rápidas, más chicas
    const s = PEAK / raw.reduce((a, b) => a + b, 0);
    return ks.map((k, i) => ({ k, f: k / T, a: raw[i] * s, ph: 2 * Math.PI * rand() }));
  }

  function wave(comps, t) {
    let y = 0;
    for (const c of comps) y += c.a * Math.sin(2 * Math.PI * c.f * t + c.ph);
    return y;
  }

  // la línea en t segundos desde el arranque: entra suave durante LEAD
  function targetAt(comps, t) {
    if (t <= 0) return 0;
    const u = Math.min(1, t / LEAD);
    return wave(comps, t) * u * u * (3 - 2 * u);
  }

  // samples: [{t, y}] (t en s desde el arranque, y en las mismas unidades que la línea). band: media anchura
  // de la banda. Devuelve null si faltan datos (el reloj se congeló) en la ventana medida.
  function analyze(samples, comps, band) {
    const S = samples.filter((s) => s.t >= LEAD - 0.1 && s.t <= LEAD + T + 0.1);
    if (S.length < 2 || S[0].t > LEAD + 0.1 || S[S.length - 1].t < LEAD + T - 0.1) return null;
    for (let i = 1; i < S.length; i++) if (S[i].t - S[i - 1].t > 0.3) return null;
    const dt = 0.01, n = Math.round(T / dt);
    const t = new Float64Array(n), y = new Float64Array(n), r = new Float64Array(n);
    let j = 0;
    for (let i = 0; i < n; i++) {                       // a 100 Hz parejos, por interpolación lineal
      const ti = LEAD + i * dt;
      while (j < S.length - 2 && S[j + 1].t < ti) j++;
      const a = S[j], b = S[j + 1];
      const u = b.t > a.t ? Math.min(1, Math.max(0, (ti - a.t) / (b.t - a.t))) : 0;
      t[i] = ti; y[i] = a.y + u * (b.y - a.y); r[i] = wave(comps, ti);
    }
    let se = 0, inside = 0;
    for (let i = 0; i < n; i++) { const e = y[i] - r[i]; se += e * e; if (Math.abs(e) <= band) inside++; }

    // retraso: correlación de y(t) con r(t − τ); r se conoce en cualquier t, así que no hay bordes
    const ym = y.reduce((a, b) => a + b, 0) / n;
    let yv = 0;
    for (let i = 0; i < n; i++) yv += (y[i] - ym) ** 2;
    const corrAt = (tau) => {
      let sxy = 0, sxx = 0;
      for (let i = 0; i < n; i++) { const x = wave(comps, t[i] - tau); sxy += x * (y[i] - ym); sxx += x * x; }
      return sxx > 0 && yv > 0 ? sxy / Math.sqrt(sxx * yv) : 0;
    };
    const lags = [];
    for (let L = -0.8; L <= 1.2 + 1e-9; L += 0.01) lags.push([L, corrAt(L)]);
    let bi = 0;
    for (let i = 1; i < lags.length; i++) if (lags[i][1] > lags[bi][1]) bi = i;
    let delay = lags[bi][0];
    if (bi > 0 && bi < lags.length - 1) {                // refinamiento con una parábola por tres puntos
      const [c0, c1, c2] = [lags[bi - 1][1], lags[bi][1], lags[bi + 1][1]];
      const d = c0 - 2 * c1 + c2;
      if (d < 0) delay += 0.01 * 0.5 * (c0 - c2) / d;
    }

    // por frecuencia: DFT exacta en f_k (cada seno da vueltas enteras en la ventana)
    const dft = (x, f) => {
      let re = 0, im = 0;
      for (let i = 0; i < n; i++) { const p = 2 * Math.PI * f * t[i]; re += x[i] * Math.cos(p); im -= x[i] * Math.sin(p); }
      return [2 * re / n, 2 * im / n];
    };
    let explained = 0;
    const freqs = comps.map((c) => {
      const [yr, yi] = dft(y, c.f), [rr, ri] = dft(r, c.f);
      const den = rr * rr + ri * ri;
      const hr = (yr * rr + yi * ri) / den, hi = (yi * rr - yr * ri) / den;   // H = Y / R
      const phase = Math.atan2(hi, hr);
      explained += (yr * yr + yi * yi) / 2;                                    // potencia de y en f_k
      return { f: c.f, amp: c.a, gain: Math.hypot(hr, hi), phase, delay: -phase / (2 * Math.PI * c.f),
               error: Math.hypot(1 - hr, hi) };
    });
    const yvar = yv / n;
    return {
      inBand: inside / n, rms: Math.sqrt(se / n), delay, corr: lags[bi][1], freqs,
      remnant: yvar > 0 ? Math.max(0, 1 - explained / yvar) : 0,
    };
  }

  return { T, LEAD, LEVELS, makeTarget, wave, targetAt, analyze };
});
