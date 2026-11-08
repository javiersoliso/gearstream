// Capítulo 8 del curso: fusión de sensores. La cuenta de la página fusion.html, sin nada de dibujo.
//
// Una dimensión primero: el ángulo con que la mano sube o baja (la elevación del antebrazo). Hay dos testigos:
//   el giroscopio dice qué tan rápido cambia: integrado es suave, pero su sesgo b se acumula como b·t;
//   el acelerómetro dice dónde es arriba: nunca se desvía, pero cada sacudida de la mano lo inclina.
// El filtro complementario integra el giroscopio y tira hacia el acelerómetro con un resorte de rigidez k:
//   θ ← θ + ω·Δt + k·Δt·(θ_medido − θ)
// Con un sesgo b, el error e = θ − θ_verdad cumple e' = b − k·e: deja de crecer cuando e = b/k.
//
// En 3D (el mocap, mocapmath.js) lo mismo se llama Mahony, y ahí aparece lo que la gravedad no ve: el rumbo.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.FusionMath = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const D2R = Math.PI / 180, R2D = 180 / Math.PI, G = 9.81;

  function normal(seed) {                 // números al azar con forma de campana, repetibles
    let a = seed >>> 0;
    const u = () => { a = (a + 0x6D2B79F5) >>> 0; let x = a; x = Math.imul(x ^ (x >>> 15), x | 1); x ^= x + Math.imul(x ^ (x >>> 7), x | 61); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
    return () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u());
  }

  // la elevación de verdad (grados): la mano va y viene despacio y cada 6 s sube rápido y vuelve (medio segundo)
  function verdadera(t) {
    let th = 15 * Math.sin(2 * Math.PI * 0.05 * t) + 8 * Math.sin(2 * Math.PI * 0.13 * t + 1) + 5 * Math.sin(2 * Math.PI * 0.31 * t + 2);
    const u = ((t - 3) % 6 + 6) % 6 / 0.5;
    if (t >= 3 && u < 1) th += 20 * Math.sin(Math.PI * u) ** 2;
    return th;
  }

  // Lo que medirían los dos testigos de esa muñeca, a hz muestras por segundo durante dur segundos.
  //   b: sesgo del giroscopio (°/s). sacudidas: cuánto inclina el acelerómetro cada empujón (1 = un reloj a
  //   25 cm del codo). ruidoGiro (°/s) y ruidoAcel (°): lo que tiemblan aunque nada se mueva.
  function inclinacion(opts) {
    opts = opts || {};
    const hz = opts.hz || 100, dur = opts.dur || 60, n = Math.round(dur * hz), dt = 1 / hz;
    const b = opts.b === undefined ? 0.5 : opts.b, sac = opts.sacudidas === undefined ? 1 : opts.sacudidas;
    const sw = opts.ruidoGiro === undefined ? 0.3 : opts.ruidoGiro, sa = opts.ruidoAcel === undefined ? 0.4 : opts.ruidoAcel;
    const r = 0.25, h = 1e-3, gauss = normal(opts.seed || 11);
    const t = new Float64Array(n), verdad = new Float64Array(n), giro = new Float64Array(n), acel = new Float64Array(n);
    for (let k = 0; k < n; k++) {
      const tk = k * dt, a = verdadera(tk - h), c = verdadera(tk), d = verdadera(tk + h);
      const w = (d - a) / (2 * h), alfa = (d - 2 * c + a) / (h * h);          // °/s y °/s²
      t[k] = tk; verdad[k] = c;
      giro[k] = w + b + sw * gauss();
      // un tirón inventado: la muñeca acelera a r·α y el acelerómetro se inclina atan(r·α / g). Esa cuenta es la de verdad solo
      // con el brazo colgando; aquí se usa en toda postura para tener sacudidas de un tamaño creíble
      acel[k] = c + sac * Math.atan(r * alfa * D2R / G) * R2D + sa * gauss();
    }
    return { hz, n, dur, b, t, verdad, giro, acel };
  }

  // un paso del filtro complementario: integrar el giro y tirar hacia la medida con rigidez k (1/s)
  function paso(th, w, medido, dt, k) {
    return th + w * dt + Math.min(1, k * dt) * (medido - th);
  }
  function complementario(giro, medido, hz, k, th0) {
    const n = giro.length, out = new Float64Array(n), dt = 1 / hz;
    let th = th0 === undefined ? medido[0] : th0;
    for (let i = 0; i < n; i++) { out[i] = th; th = paso(th, giro[i], medido[i], dt, k); }
    return out;
  }
  const soloGiro = (giro, hz, th0) => complementario(giro, giro, hz, 0, th0);

  // error de una estimación desde la muestra `desde`: promedio (con signo), rms y el más grande
  function errores(est, verdad, desde) {
    let s = 0, s2 = 0, mx = 0, m = 0;
    for (let i = desde || 0; i < est.length; i++) {
      const e = est[i] - verdad[i];
      s += e; s2 += e * e; mx = Math.max(mx, Math.abs(e)); m++;
    }
    return { medio: s / m, rms: Math.sqrt(s2 / m), max: mx };
  }

  // el valle: el error rms para muchas rigideces k, de 0.01 a 50 por segundo (escala logarítmica)
  function valle(sim, cuantos, desde) {
    const out = [];
    for (let i = 0; i < cuantos; i++) {
      const k = 0.01 * Math.pow(5000, i / (cuantos - 1));
      out.push({ k, rms: errores(complementario(sim.giro, sim.acel, sim.hz, k, sim.verdad[0]), sim.verdad, desde).rms });
    }
    return out;
  }

  // ---------- con el reloj ----------
  // f: el antebrazo en los ejes del reloj; g: un vector "arriba" (gravedad o acelerómetro), en cualquier escala
  function elevacion(f, g) {
    const n = Math.hypot(g[0], g[1], g[2]);
    return n > 0 ? Math.asin(Math.max(-1, Math.min(1, (f[0] * g[0] + f[1] * g[1] + f[2] * g[2]) / n))) * R2D : 0;
  }
  // qué tan rápido sube la mano (°/s): ω·(f × ĝ)/|f × ĝ|, sin restar ningún sesgo (aquí queremos verlo)
  function subida(w, g, f) {
    const c = [f[1] * g[2] - f[2] * g[1], f[2] * g[0] - f[0] * g[2], f[0] * g[1] - f[1] * g[0]], cn = Math.hypot(...c);
    return cn > 0.3 * Math.hypot(...g) ? (w[0] * c[0] + w[1] * c[1] + w[2] * c[2]) / cn : 0;
  }
  // el giro alrededor de la vertical (°/s), lo que mueve el rumbo y la gravedad no ve
  function giroVertical(w, g) {
    const n = Math.hypot(g[0], g[1], g[2]);
    return n > 0 ? (w[0] * g[0] + w[1] * g[1] + w[2] * g[2]) / n : 0;
  }

  // ---------- en 3D ----------
  // la orientación de un reloj inclinado `incl`, con rumbo `rumbo` y atornillado `torn` (grados), como las
  // columnas X, Y, Z (sus ejes vistos en el mundo; y arriba). Plano en la muñeca: x hacia la mano, z arriba.
  //   R = Ry(rumbo) · Rz(incl) · Rx(torn) · B, con B el reloj plano: x → x, y → −z, z → y
  function orientacion(incl, rumbo, torn) {
    const e = incl * D2R, h = rumbo * D2R, p = torn * D2R;
    const rx = (v) => [v[0], v[1] * Math.cos(p) - v[2] * Math.sin(p), v[1] * Math.sin(p) + v[2] * Math.cos(p)];
    const rz = (v) => [v[0] * Math.cos(e) - v[1] * Math.sin(e), v[0] * Math.sin(e) + v[1] * Math.cos(e), v[2]];
    const ry = (v) => [v[0] * Math.cos(h) + v[2] * Math.sin(h), v[1], -v[0] * Math.sin(h) + v[2] * Math.cos(h)];
    const R = (v) => ry(rz(rx(v)));
    return [R([1, 0, 0]), R([0, 0, -1]), R([0, 1, 0])];
  }
  // lo que lee de la gravedad ese reloj: arriba (0, g, 0) en sus ejes, Rᵀ·arriba = la componente y de cada eje
  function gravedadLeida(incl, rumbo, torn) {
    return orientacion(incl, rumbo, torn).map((col) => col[1] * G);
  }

  // errores de un antebrazo reconstruido (mocap): inclinación con signo y rumbo (grados, NaN si casi vertical)
  function erroresAntebrazo(Fv, Fe) {
    const n = Fv.length / 3, incl = new Float32Array(n), rumbo = new Float32Array(n);
    for (let k = 0; k < n; k++) {
      const v = [Fv[3 * k], Fv[3 * k + 1], Fv[3 * k + 2]], e = [Fe[3 * k], Fe[3 * k + 1], Fe[3 * k + 2]];
      incl[k] = (Math.asin(Math.max(-1, Math.min(1, e[1]))) - Math.asin(Math.max(-1, Math.min(1, v[1])))) * R2D;
      if (Math.hypot(v[0], v[2]) < 0.3 || Math.hypot(e[0], e[2]) < 0.3) { rumbo[k] = NaN; continue; }
      let d = (Math.atan2(-e[0], -e[2]) - Math.atan2(-v[0], -v[2])) * R2D;
      d = ((d + 180) % 360 + 360) % 360 - 180;
      rumbo[k] = d;
    }
    return { incl, rumbo };
  }

  // lo que debería desviarse el rumbo: ∫ b·ĝ dt, la parte del sesgo b que gira alrededor de la vertical.
  // imu: lo de MocapMath.synth (con su sesgo y la orientación de verdad del reloj); devuelve grados
  function derivaPredicha(imu) {
    const { n, hz, bias, truth } = imu, out = new Float32Array(n);
    let s = 0;
    for (let k = 0; k < n; k++) {
      const X = [truth.X[3 * k], truth.X[3 * k + 1], truth.X[3 * k + 2]], Z = [truth.Z[3 * k], truth.Z[3 * k + 1], truth.Z[3 * k + 2]];
      const Yy = Z[2] * X[0] - Z[0] * X[2];                       // (Z × X)_y: el "arriba" en el eje y del reloj
      out[k] = s;
      s += (bias[0] * X[1] + bias[1] * Yy + bias[2] * Z[1]) / hz;
    }
    return out;
  }

  return { inclinacion, verdadera, paso, complementario, soloGiro, errores, valle, elevacion, subida, giroVertical, orientacion, gravedadLeida, erroresAntebrazo, derivaPredicha };
});
