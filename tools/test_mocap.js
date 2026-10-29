// Prueba del mocap (server/web/mocapmath.js): de una animación se sintetiza lo que leería el reloj y con esas
// lecturas se reconstruye el antebrazo. Sin ruido, el reconstruido debe caer encima del de verdad; con ruido,
// la inclinación sigue exacta (sale de la gravedad) y solo el rumbo se desvía (es la integral del yaw).
//   node tools/test_mocap.js
'use strict';
const path = require('path');
const assert = require('assert');
const M = require(path.join(__dirname, '..', 'server', 'web', 'mocapmath.js'));

const ang = (a, b) => Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))) * 180 / Math.PI;
const pct = (xs, p) => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };

for (const key of Object.keys(M.ANIMS)) {
  for (const side of ['l', 'r']) {
    for (const [noise, method] of [[false, 'fusion'], [true, 'fusion'], [false, 'proyeccion']]) {
      const imu = M.synth(key, side, { noise });
      const t0 = (v) => [v[0], v[1], v[2]];
      const X0 = t0(imu.truth.X), Z0 = t0(imu.truth.Z), Y0 = M.vec.cross(Z0, X0);
      const rec = M.reconstruct(imu, side, { method, frame0: [X0, Y0, Z0], psi0: M.headingOf(t0(imu.truth.F)) });
      const err = [], tilt = [];
      for (let k = 0; k < imu.n; k++) {
        const t = [imu.truth.F[3 * k], imu.truth.F[3 * k + 1], imu.truth.F[3 * k + 2]];
        const r = [rec.F[3 * k], rec.F[3 * k + 1], rec.F[3 * k + 2]];
        err.push(ang(t, r));
        tilt.push(Math.abs(Math.asin(t[1]) - Math.asin(r[1])) * 180 / Math.PI);   // inclinación del antebrazo
      }
      const gmax = Math.max(...Array.from(imu.gyr, Math.abs));
      console.log(`${key.padEnd(10)} ${side} ${method.padEnd(10)} ${noise ? 'con ruido' : 'sin ruido'}: antebrazo mediana ${pct(err, 0.5).toFixed(2)}°, p95 ${pct(err, 0.95).toFixed(2)}°, máx ${Math.max(...err).toFixed(1)}° · inclinación p95 ${pct(tilt, 0.95).toFixed(2)}° · giro máx ${gmax.toFixed(0)} °/s`);
      if (method === 'fusion') {
        if (!noise) {
          assert.ok(pct(err, 0.5) < 1.5, `${key} ${side}: sin ruido el antebrazo reconstruido debe caer encima`);
          assert.ok(pct(err, 0.95) < 5, `${key} ${side}: casi siempre encima`);
        }
        assert.ok(pct(tilt, 0.95) < 2, `${key} ${side}: la inclinación sale de la gravedad y no se desvía`);
      }
    }
  }
}
// apuntar: el cursor del reloj (x = −∫yaw, y = ∫pitch, como el ratón aéreo) contra donde pega el rayo de verdad
const AP = M.ANIMS.apuntar;
for (const side of ['l', 'r']) {
  for (const noise of [false, true]) {
    const imu = M.synth('apuntar', side, { noise });
    const rec = M.reconstruct(imu, side, {});
    const el0 = M.build(AP.pose(0, side)).arms[side].el, p0 = AP.target(0);
    const K = M.vec.len(M.vec.sub(p0, el0)) * Math.PI / 180;
    const tr = M.cursorTrack(rec.rates, imu.hz, p0, K);
    const err = [];
    for (let k = 0; k < imu.n; k++) { const p = AP.target(k / imu.hz); err.push(Math.hypot(tr[3 * k] - p[0], tr[3 * k + 1] - p[1]) * 100); }
    console.log(`apuntar cursor ${side} ${noise ? 'con ruido' : 'sin ruido'}: mediana ${pct(err, 0.5).toFixed(1)} cm, p95 ${pct(err, 0.95).toFixed(1)} cm, máx ${Math.max(...err).toFixed(1)} cm`);
    if (!noise) assert.ok(pct(err, 0.95) < 6, `apuntar ${side}: el cursor del reloj debe ir con el rayo (p95 < 6 cm)`);
  }
}
// en reposo el reloj lee la gravedad en el acelerómetro: |acc| ≈ 9.81 cuando no hay movimiento
const still = M.synth('tablet', 'l', {});
const mag = (k) => Math.hypot(still.acc[3 * k], still.acc[3 * k + 1], still.acc[3 * k + 2]);
assert.ok(Math.abs(mag(0) - 9.81) < 1.5, `acelerómetro en reposo ≈ g (${mag(0).toFixed(2)})`);
console.log('OK');
