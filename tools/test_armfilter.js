// Prueba del filtro del codo con un brazo sintético de verdad conocida.
//   node tools/test_armfilter.js
// Se genera un movimiento anatómicamente válido (hombro, flexión del codo, rotación del húmero y
// pronación), se calculan las mediciones que daría el reloj (orientación, giroscopio, aceleración
// lineal) con ruido y sesgo, y se compara el error del codo: filtro frente a la regla de reposo.
'use strict';
const assert = require('assert');
const path = require('path');
const { ArmFilter, feasible, defaultPrior, DEFAULTS } = require(path.join(__dirname, '..', 'server', 'web', 'armfilter.js'));

const DEG = Math.PI / 180;
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => Math.hypot(a[0], a[1], a[2]);
const normalize = (a) => { const n = norm(a); return [a[0] / n, a[1] / n, a[2] / n]; };
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const scale = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
function rotate(v, axis, ang) {                       // Rodrigues
  const k = normalize(axis), c = Math.cos(ang), s = Math.sin(ang);
  return add(add(scale(v, c), scale(cross(k, v), s)), scale(k, dot(k, v) * (1 - c)));
}
function mulTM(A, B) {                                 // Aᵀ·B, matrices por filas
  const C = new Array(9).fill(0);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) C[3 * i + j] += A[3 * k + i] * B[3 * k + j];
  return C;
}
const mulTV = (R, v) => [R[0] * v[0] + R[3] * v[1] + R[6] * v[2], R[1] * v[0] + R[4] * v[1] + R[7] * v[2], R[2] * v[0] + R[5] * v[1] + R[8] * v[2]];
function logR(Q) {                                     // vector de rotación de una matriz de rotación
  const tr = Q[0] + Q[4] + Q[8], ang = Math.acos(Math.max(-1, Math.min(1, (tr - 1) / 2)));
  const w = [Q[7] - Q[5], Q[2] - Q[6], Q[3] - Q[1]];
  const k = ang < 1e-6 ? 0.5 : ang / (2 * Math.sin(ang));
  return scale(w, k);
}
let seed = 12345;
const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
const randn = () => Math.sqrt(-2 * Math.log(rnd() || 1e-12)) * Math.cos(2 * Math.PI * rnd());

// ---------- brazo sintético ----------
function pose(t, still, speed = 1) {
  // a partir de `still` el brazo frena en 1 s con desaceleración constante (frenar en seco daría un pico
  // de aceleración que ningún brazo real tiene) y se queda quieto; `speed` acelera el baile
  const ramp = 1, x = still ? Math.min(Math.max((t - still) / ramp, 0), 1) : 0;
  const T = (still && t > still ? still + ramp * (x - x * x / 2) : t) * speed;
  const flex = (35 + 30 * Math.sin(2 * Math.PI * 0.25 * T)) * DEG;           // levantar hacia delante
  const abd = (25 + 20 * Math.sin(2 * Math.PI * 0.17 * T + 1)) * DEG;         // separar hacia el lado
  const u = normalize([Math.sin(abd), -Math.cos(abd) * Math.cos(flex), Math.cos(abd) * Math.sin(flex)]);
  let h = sub([1, 0, 0], scale(u, u[0])); h = normalize(h);                   // bisagra lateral ⟂ u
  h = rotate(h, u, 20 * DEG * Math.sin(2 * Math.PI * 0.3 * T));               // rotación del húmero
  const beta = (70 + 35 * Math.sin(2 * Math.PI * 0.4 * T + 0.5)) * DEG;       // flexión del codo
  const f = normalize(rotate(u, scale(h, -1), beta));
  const hl = normalize(cross(f, u));                                          // bisagra lateral exacta
  const Nw = normalize(rotate(hl, f, 30 * DEG * Math.sin(2 * Math.PI * 0.2 * T)));   // pronación
  const y = cross(Nw, f);
  const R = [f[0], y[0], Nw[0], f[1], y[1], Nw[1], f[2], y[2], Nw[2]];       // columnas: x = f, y, z = pantalla
  const s = DEFAULTS.shoulder;
  const e = add(s, scale(u, DEFAULTS.Lu));
  return { u, f, R, e, p: add(e, scale(f, DEFAULTS.Lw)), N: Nw };
}

function run({ seconds = 40, still = 30, speed = 1, gyroNoise = 0.15 * DEG, accNoise = 0.08, accBias = [0.05, -0.03, 0.04], filter = {} } = {}) {
  const dt = 0.01, steps = Math.round(seconds / dt);
  const P = []; for (let k = -1; k <= steps + 1; k++) P.push(pose(k * dt, still, speed));
  const filt = new ArmFilter(Object.assign({ seed: 3 }, filter));
  const errF = [], errP = [], errFs = [], errPs = [], spreads = [];
  for (let k = 1; k <= steps; k++) {
    const prev = P[k - 1], cur = P[k], next = P[k + 1];
    const acc = scale(add(sub(next.p, scale(cur.p, 2)), prev.p), 1 / (dt * dt));      // p̈ en el mundo
    const aLinB = add(add(mulTV(cur.R, acc), [accNoise * randn(), accNoise * randn(), accNoise * randn()]), accBias);
    const wB = scale(logR(mulTM(prev.R, next.R)), 1 / (2 * dt));                   // ω en el reloj
    const omegaB = add(wB, [gyroNoise * randn(), gyroNoise * randn(), gyroNoise * randn()]);
    const est = filt.step(cur.R, omegaB, aLinB, dt);
    for (const v of [...est.u, est.spread]) assert.ok(Number.isFinite(v), 'el filtro devolvió un número no finito');
    const t = k * dt;
    if (t < 3) continue;                                                             // calentamiento
    const eF = norm(sub(add(DEFAULTS.shoulder, scale(est.u, DEFAULTS.Lu)), cur.e));
    const eP = norm(sub(add(DEFAULTS.shoulder, scale(defaultPrior(cur.f), DEFAULTS.Lu)), cur.e));
    (t < still ? errF : errFs).push(eF); (t < still ? errP : errPs).push(eP);
    spreads.push(est.spread);
  }
  const rms = (a) => Math.sqrt(a.reduce((s, x) => s + x * x, 0) / a.length);
  const med = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
  return { rmsF: rms(errF), rmsP: rms(errP), medF: med(errF), medP: med(errP), rmsFs: rms(errFs), rmsPs: rms(errPs), spread: med(spreads) };
}

module.exports = { pose, run, logR, mulTM, mulTV, dot, cross, norm, add, sub, scale };
if (require.main !== module) return;

// ---------- pruebas ----------
const cm = (x) => (100 * x).toFixed(1) + ' cm';

// 1) límites articulares
const o = DEFAULTS;
assert.ok(feasible([0, -1, 0], [0, 0, 1], [1, 0, 0], o), 'codo colgando, antebrazo al frente, pulgar arriba: posible');
assert.ok(!feasible([0, -1, 0], [0, 0, 1], [-1, 0, 0], o), 'la pantalla mirando hacia el cuerpo con el codo doblado es imposible');
assert.ok(!feasible([-1, 0, 0], [0, 0, 1], [1, 0, 0], o), 'el codo dentro del pecho es imposible');
assert.ok(!feasible([0, -1, 0], [0, 1, 0], [1, 0, 0], o), 'el codo flexionado 180° es imposible');
console.log('límites articulares: ok');

// 2) brazo sintético a tres velocidades (1 = paseo lento, 4 = baile)
for (const speed of [1, 2.5, 4]) {
  const r = run({ seconds: 20, still: 15, speed });
  console.log(`velocidad ${speed}: en movimiento filtro ${cm(r.rmsF)} · regla ${cm(r.rmsP)} | quieto filtro ${cm(r.rmsFs)} · regla ${cm(r.rmsPs)} | nube ${cm(r.spread)}`);
  assert.ok(r.rmsF < 0.85 * r.rmsP, `velocidad ${speed}: en movimiento el filtro debe mejorar al menos un 15 % a la regla`);
  assert.ok(r.rmsFs < r.rmsPs + 0.05, `velocidad ${speed}: quieto, el filtro no debe alejarse más de 5 cm de la regla`);
}

// 3) sin ruido de sesgo y con más ruido: que no se rompa
const r2 = run({ seconds: 20, still: 15, speed: 2.5, gyroNoise: 0.5 * DEG, accNoise: 0.3, accBias: [0.15, -0.1, 0.1] });
console.log(`ruido x3:    con filtro ${cm(r2.rmsF)} · regla de reposo ${cm(r2.rmsP)}`);
assert.ok(r2.rmsF < r2.rmsP, 'con más ruido el filtro sigue sin empeorar a la regla');

console.log('OK');
