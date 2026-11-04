// Mocap con un reloj. Un stickman animado (caminar, usar una tablet, apuntar), lo que leería un reloj en su
// muñeca, y el antebrazo reconstruido solo con esas lecturas, con la misma cuenta de wrist.js:
//   la inclinación del antebrazo y su giro (atornillar) salen de la gravedad: son absolutos;
//   el rumbo (hacia dónde apunta en horizontal) es la integral del yaw: es relativo y se desvía con el sesgo.
// Si el antebrazo reconstruido cae encima del de verdad, la extracción tiene sentido.
//
// Mundo: y arriba; el cuerpo mira hacia −z con su derecha en +x; el rumbo H gira contra el reloj visto desde
// arriba. Ángulos de las animaciones en grados.
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./wrist.js'));
  else Object.assign(root, factory({ Wrist: root.Wrist }));
})(typeof self !== 'undefined' ? self : this, function (deps) {
  'use strict';

  const { Wrist } = deps;
  const G = 9.81, D2R = Math.PI / 180, UP = [0, 1, 0];
  const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const len = (a) => Math.hypot(a[0], a[1], a[2]);
  const unit = (a) => { const n = len(a); return n > 1e-12 ? mul(a, 1 / n) : [0, 0, 0]; };
  const lerp = (a, b, t) => add(a, mul(sub(b, a), t));
  function rot(v, axis, ang) {           // Rodrigues: gira v alrededor de axis
    const k = unit(axis), c = Math.cos(ang), s = Math.sin(ang);
    return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1 - c)));
  }
  const smooth = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
  const env = (t, a, b, c, d) => (t <= a || t >= d ? 0 : t < b ? smooth((t - a) / (b - a)) : t <= c ? 1 : 1 - smooth((t - c) / (d - c)));
  const axesOf = (H) => ({ fwd: [-Math.sin(H), 0, -Math.cos(H)], right: [Math.cos(H), 0, -Math.sin(H)] });

  const LEN = { up: 0.29, fore: 0.27, thigh: 0.44, shank: 0.43, foot: 0.14 };

  // dos huesos: hombro a, objetivo de la muñeca t, el codo se dobla hacia pole
  function ik(a, t, l1, l2, pole) {
    const v = sub(t, a);
    let d = len(v);
    const dir = d > 1e-9 ? mul(v, 1 / d) : [0, -1, 0];
    d = Math.min(Math.max(d, Math.abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4);
    const x = (l1 * l1 - l2 * l2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, l1 * l1 - x * x));
    const pv = sub(pole, a), pd = unit(sub(pv, mul(dir, dot(pv, dir))));
    return { el: add(add(a, mul(dir, x)), mul(pd, h)), wr: add(a, mul(dir, d)) };
  }

  // la mano: cuatro dedos y el pulgar desde la muñeca wr, con el antebrazo F y el dorso d; k = −1 izquierda
  function hand(wr, F, d, k, fist) {
    const S = cross(F, d), thumb = -k, reach = 0.18 - 0.08 * fist, pts = [], segs = [];
    for (const o of [-0.03, -0.01, 0.01, 0.03]) {
      const kn = add(add(wr, mul(F, 0.09)), mul(S, o));
      const tip = add(add(add(wr, mul(F, reach)), mul(S, o)), mul(d, -0.045 * fist));
      pts.push(kn, tip); segs.push([wr, kn], [kn, tip]);
    }
    const tb = add(add(wr, mul(F, 0.03)), mul(S, thumb * 0.03));
    const tt = add(add(add(wr, mul(F, 0.08 - 0.02 * fist)), mul(S, thumb * 0.06)), mul(d, -0.02));
    pts.push(tb, tt); segs.push([wr, tb], [tb, tt]);
    return { pts, segs, S, thumb };
  }

  // la pose de una animación → puntos del esqueleto, segmentos, antebrazos y accesorios. Un brazo con
  // `over: {F, d}` toma el antebrazo de los datos (el reloj) en vez de la animación.
  function build(P) {
    const { fwd, right } = axesOf(P.H);
    const lean = (P.lean || 0) * D2R;
    const pel = P.pelvis;
    const chest = add(pel, mul(rot(UP, right, -lean), 0.4));
    const C = axesOf(P.H + (P.twist || 0) * D2R);
    const upC = rot(UP, C.right, -lean);
    const neck = add(chest, mul(upC, 0.1));
    const head = add(neck, mul(rot(upC, C.right, -(P.head || 0) * D2R), 0.14));
    const pts = [pel, chest, neck, head];
    const segs = [[pel, chest], [chest, neck], [neck, head]];
    const arms = {};
    let tablet = null;
    const rel = (spec, sh, k) => {
      const base = spec.from === 'chest' ? chest : sh, o = spec.off, med = mul(C.right, -k);
      return add(add(add(base, mul(C.fwd, o[0])), mul(upC, o[1])), mul(med, o[2]));
    };
    for (const s of P.tablet === 'r' ? ['r', 'l'] : ['l', 'r']) {
      const k = s === 'l' ? -1 : 1;
      const sh = add(add(chest, mul(C.right, 0.19 * k)), mul(upC, 0.02));
      const A = P.arms[s];
      let el, wr, hinge;
      if (A.over) {
        let U = rot([0, -1, 0], C.right, (A.over.flex || 12) * D2R);
        U = rot(U, C.fwd, -k * 6 * D2R);
        el = add(sh, mul(U, LEN.up));
        const F = unit(A.over.F), d = unit(sub(A.over.d, mul(F, dot(A.over.d, F))));
        wr = add(el, mul(F, LEN.fore));
        const h = hand(wr, F, d, k, A.fist || 0);
        pts.push(sh, el, wr, ...h.pts);
        segs.push([chest, sh], [sh, el], [el, wr], ...h.segs);
        arms[s] = { sh, el, wr, F, d, k };
        continue;
      }
      if (A.ik) {
        const target = typeof A.ik.target === 'function' ? A.ik.target({ tablet, sh, C, upC, chest }) : rel(A.ik.target, sh, k);
        const pole = rel(A.ik.pole, sh, k);
        ({ el, wr } = ik(sh, target, LEN.up, LEN.fore, pole));
        const U = unit(sub(el, sh)), F = unit(sub(wr, el));
        hinge = cross(U, F);
        if (len(hinge) < 0.05) hinge = cross(unit(sub(pole, sh)), U);
        hinge = unit(hinge);
      } else if (A.aim) {                  // apuntar: el antebrazo mira al punto `at`
        let U = rot([0, -1, 0], C.right, A.aim.flex * D2R);
        U = rot(U, C.fwd, -k * (A.aim.abd || 0) * D2R);
        el = add(sh, mul(U, LEN.up));
        wr = add(el, mul(unit(sub(A.aim.at, el)), LEN.fore));
        hinge = unit(cross(U, unit(sub(wr, el))));
      } else {
        const f = A.fk;
        let U = rot([0, -1, 0], C.right, f.flex * D2R);
        U = rot(U, C.fwd, -k * (f.abd || 0) * D2R);
        hinge = rot(C.right, C.fwd, -k * (f.abd || 0) * D2R);
        el = add(sh, mul(U, LEN.up));
        wr = add(el, mul(rot(U, hinge, (f.elbow || 0) * D2R), LEN.fore));
      }
      const F = unit(sub(wr, el));
      // dorso de la mano con el antebrazo "dando la mano" (pronación 0): hacia afuera del cuerpo
      const dn = unit(mul(sub(hinge, mul(F, dot(hinge, F))), k));
      const d = rot(dn, F, -k * (A.pron || 0) * D2R);   // pronación + : la palma mira hacia abajo
      const h = hand(wr, F, d, k, A.fist || 0), S = h.S, thumb = h.thumb;
      pts.push(sh, el, wr, ...h.pts);
      segs.push([chest, sh], [sh, el], [el, wr], ...h.segs);
      arms[s] = { sh, el, wr, F, d, k };
      if (s === P.tablet) {                // la tablet descansa en la palma de la mano sin reloj
        const n = mul(d, -1);
        tablet = { c: add(add(add(wr, mul(F, 0.08)), mul(n, 0.02)), mul(S, thumb * 0.07)), n, u: unit(mul(S, thumb)), v: F };
      }
    }
    for (const s of ['l', 'r']) {
      const k = s === 'l' ? -1 : 1, L = P.legs[s];
      const hip = add(pel, mul(right, 0.1 * k));
      let T = rot([0, -1, 0], right, L.flex * D2R);
      T = rot(T, fwd, -k * (L.abd || 0) * D2R);
      const hg = rot(right, fwd, -k * (L.abd || 0) * D2R);
      const knee = add(hip, mul(T, LEN.thigh));
      const Sh = rot(T, hg, -(L.knee || 0) * D2R);
      const ankle = add(knee, mul(Sh, LEN.shank));
      const toe = add(ankle, mul(rot(Sh, hg, (90 - (L.ankle || 0)) * D2R), LEN.foot));
      pts.push(hip, knee, ankle, toe);
      segs.push([pel, hip], [hip, knee], [knee, ankle], [ankle, toe]);
    }
    return { pts, segs, arms, tablet, head, pelvis: pel };
  }

  // el reloj en la muñeca de un lado: sobre el dorso, un poco antes de la mano. En la izquierda su x apunta a
  // la mano; en la derecha, puesto igual, apunta al codo (por eso wrist.js usa −x ahí).
  function watchOf(b, side) {
    const a = b.arms[side];
    const p = add(add(a.wr, mul(a.F, -0.035)), mul(a.d, 0.02));
    const X = side === 'l' ? a.F : mul(a.F, -1), Z = a.d, Y = cross(Z, X);
    return { p, X, Y, Z, F: a.F, el: a.el };
  }

  // ---------- las animaciones ----------
  // apuntar: una pantalla virtual 2.5 m delante; el rayo del antebrazo del reloj marca el cursor. Visita cuatro
  // íconos (con un "clic": un giro rápido de muñeca, como en el tornillo), vuelve al centro y dibuja un círculo.
  const SCREEN = { c: [0, 1.35, -2.5], w: 1.6, h: 0.9, icons: [['archivos', -0.55, 0.28], ['música', 0.55, 0.28], ['fotos', 0.55, -0.28], ['ajustes', -0.55, -0.28]] };
  function aimPath(t) {
    const ic = SCREEN.icons;
    let x = 0, y = 0, click = 0;
    if (t >= 0.6 && t < 5.4) {
      const i = Math.floor((t - 0.6) / 1.2), u = t - 0.6 - 1.2 * i, m = smooth(Math.min(1, u / 0.6));
      const from = i === 0 ? [0, 0] : [ic[i - 1][1], ic[i - 1][2]];
      x = from[0] + (ic[i][1] - from[0]) * m; y = from[1] + (ic[i][2] - from[1]) * m;
      click = env(u, 0.75, 0.82, 0.86, 0.95);
    } else if (t >= 5.4 && t < 6.0) {
      const m = smooth((t - 5.4) / 0.6);
      x = ic[3][1] * (1 - m); y = ic[3][2] * (1 - m);
    } else if (t >= 6.0 && t < 9.0) {
      const u = (t - 6) / 3, a = 2 * Math.PI * (u - Math.sin(2 * Math.PI * u) / (2 * Math.PI));   // arranca y frena suave
      x = 0.2 * Math.sin(a); y = 0.2 - 0.2 * Math.cos(a);
    }
    return { p: [SCREEN.c[0] + x, SCREEN.c[1] + y, SCREEN.c[2]], click };
  }
  const WALK_R = 1.4, WALK_V = 1.0, WALK_LOOP = 2 * Math.PI * WALK_R / WALK_V, WALK_T = WALK_LOOP / 8;
  const ANIMS = {
    caminar: {
      name: 'Caminar', dur: WALK_LOOP,
      pose(t) {
        const th = 2 * Math.PI * t / WALK_LOOP, ph = 2 * Math.PI * t / WALK_T, s = Math.sin(ph);
        const leg = (q) => ({ flex: 24 * Math.sin(q), knee: 6 + 46 * Math.pow(Math.max(0, Math.cos(q)), 1.5), ankle: 0 });
        return {
          pelvis: [WALK_R * Math.cos(th), 0.97 + 0.02 * Math.cos(2 * ph), WALK_R * Math.sin(th)], H: Math.PI - th,
          lean: 5, twist: 6 * s, head: 4,
          legs: { l: leg(ph), r: leg(ph + Math.PI) },
          arms: {
            l: { fk: { flex: -20 * s, abd: 6, elbow: 26 - 9 * s }, pron: 10, fist: 0.3 },   // el codo se dobla más con el brazo adelante
            r: { fk: { flex: 20 * s, abd: 6, elbow: 26 + 9 * s }, pron: 10, fist: 0.3 },
          },
        };
      },
    },
    tablet: {
      name: 'Usar una tablet', dur: 8,
      pose(t, side) {                      // side: la muñeca del reloj, que toca la pantalla; la otra sostiene
        const tap = side === 'l' ? 'l' : 'r', hold = tap === 'l' ? 'r' : 'l';
        const sw = Math.sin(2 * Math.PI * t / 4);
        const SPOTS = [[-0.06, -0.03], [0.04, 0.02], [0, 0.045], [0.07, -0.02]];
        const ph = (t % 0.5) / 0.5, i = Math.floor(t / 0.5) % 4;
        const mv = smooth(Math.min(1, ph / 0.4)), press = env(ph, 0.45, 0.6, 0.65, 0.85);
        const spot = [SPOTS[(i + 3) % 4][0] + (SPOTS[i][0] - SPOTS[(i + 3) % 4][0]) * mv, SPOTS[(i + 3) % 4][1] + (SPOTS[i][1] - SPOTS[(i + 3) % 4][1]) * mv];
        const arms = {};
        arms[hold] = { ik: { target: { off: [0.32, -0.3 + 0.025 * sw, 0.14] }, pole: { off: [-0.1, -0.5, -0.3] } }, pron: -75 + 12 * Math.sin(2 * Math.PI * t / 4 + 1) };
        arms[tap] = {
          ik: {
            target: ({ tablet, sh }) => {
              const tip = add(add(add(tablet.c, mul(tablet.u, spot[0])), mul(tablet.v, spot[1])), mul(tablet.n, 0.005 + 0.05 * (1 - press)));
              return add(tip, mul(unit(sub(tip, sh)), -0.15));
            },
            pole: { off: [-0.1, -0.5, -0.3] },
          },
          pron: 85, fist: 0.5,
        };
        return { pelvis: [0, 0.98 + 0.004 * sw, 0], H: 0, lean: 6, head: 28, tablet: hold, legs: { l: { flex: 2, knee: 4 }, r: { flex: 2, knee: 4 } }, arms };
      },
    },
    apuntar: {
      name: 'Apuntar', dur: 10, screen: SCREEN,
      marks: [[1.2, 1.8, 'archivos'], [2.4, 3.0, 'música'], [3.6, 4.2, 'fotos'], [4.8, 5.4, 'ajustes'], [6.0, 9.0, 'círculo']],
      target: (t) => aimPath(t).p, path: aimPath,
      pose(t, side) {                      // el brazo del reloj apunta a la pantalla; el otro cuelga
        const a = aimPath(t), b = Math.sin(2 * Math.PI * t / 5), aim = side === 'l' ? 'l' : 'r', rest = aim === 'l' ? 'r' : 'l';
        const arms = {};
        arms[aim] = { aim: { flex: 38, abd: 10, at: a.p }, pron: 70 + 35 * a.click, fist: 0.7 };
        arms[rest] = { fk: { flex: 4, abd: 6, elbow: 12 }, pron: 0, fist: 0.2 };
        return { pelvis: [0, 0.98 + 0.003 * b, 0], H: 0, lean: 3, head: 6, legs: { l: { flex: 2, knee: 4 }, r: { flex: 2, knee: 4 } }, arms };
      },
    },
  };

  // reposo para reproducir grabaciones: de pie, respirando; el brazo del reloj lo mueven los datos
  function idlePose(t) {
    const b = Math.sin(2 * Math.PI * t / 4);
    return {
      pelvis: [0, 0.98 + 0.004 * b, 0], H: 0, lean: 2, head: 6,
      legs: { l: { flex: 1, knee: 3 }, r: { flex: 1, knee: 3 } },
      arms: { l: { fk: { flex: 4, abd: 6, elbow: 12 }, pron: 0, fist: 0.2 }, r: { fk: { flex: 4, abd: 6, elbow: 12 }, pron: 0, fist: 0.2 } },
    };
  }

  // ---------- lo que leería el reloj ----------
  function rng(seed) {
    let a = seed >>> 0;
    const u = () => { a = (a + 0x6D2B79F5) >>> 0; let x = a; x = Math.imul(x ^ (x >>> 15), x | 1); x ^= x + Math.imul(x ^ (x >>> 7), x | 61); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
    return () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u());
  }
  // giroscopio (°/s, en los ejes del reloj), acelerómetro (m/s², fuerza específica: lo que empuja + gravedad)
  // y gravedad (m/s², el vector "arriba" en los ejes del reloj), a hz muestras por segundo
  function synth(key, side, opts) {
    opts = opts || {};
    const A = ANIMS[key], hz = opts.hz || 100, dt = 1 / hz, loops = opts.loops || 1, n = Math.round(A.dur * loops * hz);   // loops: vueltas seguidas
    const W = [];
    for (let k = -1; k <= n; k++) { const t = ((k * dt) % A.dur + A.dur) % A.dur; W.push(watchOf(build(A.pose(t, side)), side)); }
    const gauss = rng(opts.seed || 7), noise = !!opts.noise;
    const bias = noise ? [0.6, -0.4, 0.3] : [0, 0, 0];
    const acc = new Float32Array(n * 3), gyr = new Float32Array(n * 3), grav = new Float32Array(n * 3);
    const tF = new Float32Array(n * 3), tX = new Float32Array(n * 3), tZ = new Float32Array(n * 3);
    for (let k = 0; k < n; k++) {
      const P = W[k], C = W[k + 1], N = W[k + 2];
      const cols = [C.X, C.Y, C.Z], pc = [P.X, P.Y, P.Z], nc = [N.X, N.Y, N.Z];
      const r = (i, j) => dot(pc[i], nc[j]);   // giro relativo entre la muestra anterior y la siguiente
      const ang = Math.acos(Math.max(-1, Math.min(1, (r(0, 0) + r(1, 1) + r(2, 2) - 1) / 2)));
      let w = [0, 0, 0];
      if (ang > 1e-9) w = mul([r(2, 1) - r(1, 2), r(0, 2) - r(2, 0), r(1, 0) - r(0, 1)], ang / (2 * Math.sin(ang)) / (2 * dt) / D2R);
      const a = mul(add(sub(N.p, mul(C.p, 2)), P.p), hz * hz);
      const f = add(a, mul(UP, G));
      for (let i = 0; i < 3; i++) {
        gyr[3 * k + i] = w[i] + bias[i] + (noise ? 0.3 * gauss() : 0);
        acc[3 * k + i] = dot(cols[i], f) + (noise ? 0.05 * gauss() : 0);
        grav[3 * k + i] = G * cols[i][1] + (noise ? 0.02 * gauss() : 0);
        tF[3 * k + i] = C.F[i]; tX[3 * k + i] = C.X[i]; tZ[3 * k + i] = C.Z[i];
      }
    }
    return { hz, n, dur: A.dur * loops, acc, gyr, grav, bias, truth: { F: tF, X: tX, Z: tZ } };
  }

  // ---------- la reconstrucción, solo con giroscopio y gravedad ----------
  // Dos métodos:
  //   'fusion' (el de los trajes de mocap con IMU): la orientación completa del reloj se integra con el
  //     giroscopio, q ← q ⊗ exp(ω dt / 2), y la gravedad corrige la inclinación (filtro de Mahony: el error
  //     entre el "arriba" medido y el predicho se suma al giro). No tiene singularidades; el rumbo se desvía
  //     solo con el sesgo del giroscopio alrededor de la vertical, que la gravedad no ve.
  //   'proyeccion' (el de las páginas, wrist.js): rumbo = ∫ yaw dt y lo demás de la gravedad (TRIAD). Sirve
  //     para apuntar, pero con el antebrazo casi vertical (el brazo colgando) el rumbo no existe y se pierde.
  const qmul = (a, b) => [a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3], a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
    a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1], a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0]];
  const qcols = (q) => {                   // columnas de la matriz: los ejes del reloj vistos en el mundo
    const [w, x, y, z] = q;
    return [[1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)],
      [2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)],
      [2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)]];
  };
  function qfromCols(X, Y, Z) {
    const m00 = X[0], m11 = Y[1], m22 = Z[2], tr = m00 + m11 + m22;
    let q;
    if (tr > 0) { const s = Math.sqrt(tr + 1) * 2; q = [0.25 * s, (Y[2] - Z[1]) / s, (Z[0] - X[2]) / s, (X[1] - Y[0]) / s]; }
    else if (m00 > m11 && m00 > m22) { const s = Math.sqrt(1 + m00 - m11 - m22) * 2; q = [(Y[2] - Z[1]) / s, 0.25 * s, (Y[0] + X[1]) / s, (Z[0] + X[2]) / s]; }
    else if (m11 > m22) { const s = Math.sqrt(1 + m11 - m00 - m22) * 2; q = [(Z[0] - X[2]) / s, (Y[0] + X[1]) / s, 0.25 * s, (Z[1] + Y[2]) / s]; }
    else { const s = Math.sqrt(1 + m22 - m00 - m11) * 2; q = [(X[1] - Y[0]) / s, (Z[0] + X[2]) / s, (Z[1] + Y[2]) / s, 0.25 * s]; }
    const n = Math.hypot(...q);
    return q.map((v) => v / n);
  }
  // marco inicial sin ayuda: "arriba" de la gravedad y el antebrazo con rumbo psi (grados)
  function triad(g, f, psi) {
    const a1 = unit(g), c = cross(a1, f);
    const b1 = len(c) > 1e-3 ? unit(c) : unit(cross(a1, [0, 0, 1])), c1 = cross(a1, b1);
    const se = dot(a1, f), ce = Math.sqrt(Math.max(0, 1 - se * se)), ps = psi * D2R;
    const Fw = add(mul([-Math.sin(ps), 0, -Math.cos(ps)], ce), mul(UP, se));
    const b2r = cross(UP, Fw), b2 = len(b2r) > 1e-3 ? unit(b2r) : [Math.cos(ps), 0, -Math.sin(ps)], c2 = cross(UP, b2);
    const R = (i) => add(add(mul(UP, a1[i]), mul(b2, b1[i])), mul(c2, c1[i]));
    return [R(0), R(1), R(2)];
  }
  function reconstruct(imu, side, opts) {
    opts = opts || {};
    const { hz, n, gyr, grav } = imu, dt = 1 / hz, method = opts.method || 'fusion', KP = opts.kp === undefined ? 2 : opts.kp;
    const wr = new Wrist(side === 'r' ? 'right' : 'left');
    const f = side === 'r' ? [-1, 0, 0] : [1, 0, 0];
    const g0 = [grav[0], grav[1], grav[2]];
    let [X, Y, Z] = opts.frame0 || triad(g0, f, opts.psi0 || 0);
    let q = qfromCols(X, Y, Z), psi = opts.psi0 !== undefined ? opts.psi0 : headingOf(side === 'r' ? mul(X, -1) : X);
    const out = { rates: new Float32Array(n * 3), F: new Float32Array(n * 3), X: new Float32Array(n * 3), Z: new Float32Array(n * 3) };
    for (let k = 0; k < n; k++) {
      const g = [grav[3 * k], grav[3 * k + 1], grav[3 * k + 2]], w = [gyr[3 * k], gyr[3 * k + 1], gyr[3 * k + 2]];
      const r = wr.rates(w, g);            // lo mismo que ven las páginas, para las gráficas
      out.rates[3 * k] = r.roll; out.rates[3 * k + 1] = r.yaw; out.rates[3 * k + 2] = r.pitch;
      if (method === 'fusion') {
        const cols = qcols(q), pred = [cols[0][1], cols[1][1], cols[2][1]];   // "arriba" predicho, en los ejes del reloj
        const e = cross(unit(g), pred);
        const wc = add(mul(w, D2R), mul(e, KP)), th = len(wc) * dt;
        if (th > 1e-12) {
          const ax = unit(wc), s = Math.sin(th / 2);
          q = qmul(q, [Math.cos(th / 2), ax[0] * s, ax[1] * s, ax[2] * s]);
          const nq = Math.hypot(...q); q = q.map((v) => v / nq);
        }
        [X, Y, Z] = qcols(q);
      } else {
        psi += r.yaw * dt;
        if (len(cross(unit(g), f)) > 0.1) [X, Y, Z] = triad(g, f, psi);   // casi vertical: se queda el anterior
      }
      const F = side === 'r' ? mul(X, -1) : X;
      for (let i = 0; i < 3; i++) { out.F[3 * k + i] = F[i]; out.X[3 * k + i] = X[i]; out.Z[3 * k + i] = Z[i]; }
    }
    return out;
  }
  // rumbo de un antebrazo (grados), para arrancar la reconstrucción alineada con la animación
  const headingOf = (F) => Math.atan2(-F[0], -F[2]) / D2R;

  // el cursor como lo calcula el ratón aéreo (y Dibuja en 2D): x = −∫yaw dt, y = ∫pitch dt, en grados, por K
  // metros por grado. Con K = D · π/180 (D, la distancia del codo a la pantalla) un grado de muñeca mueve el
  // cursor lo mismo que el rayo de verdad en ángulos chicos; en ángulos grandes el rayo va como D·tan θ.
  function cursorTrack(rates, hz, start, K) {
    const n = rates.length / 3, out = new Float32Array(n * 3);
    let yaw = 0, pitch = 0;
    for (let k = 0; k < n; k++) {
      yaw += rates[3 * k + 1] / hz; pitch += rates[3 * k + 2] / hz;
      out[3 * k] = start[0] - K * yaw; out[3 * k + 1] = start[1] + K * pitch; out[3 * k + 2] = start[2];
    }
    return out;
  }

  return { ANIMS, build, hand, watchOf, idlePose, synth, reconstruct, headingOf, cursorTrack, vec: { add, sub, mul, dot, cross, len, unit, rot } };
});
