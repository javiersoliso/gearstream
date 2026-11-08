// Los números de las animaciones del capítulo 8, sacados de la misma cuenta que la página y las pruebas
// (server/web/fusionmath.js y mocapmath.js). cap08.py lo corre y lee el JSON que imprime.
//   node docs/curso/animaciones/datos_cap08.js > datos.json
'use strict';
const path = require('path');
const web = path.join(__dirname, '..', '..', '..', 'server', 'web');
const F = require(path.join(web, 'fusionmath.js'));
const M = require(path.join(web, 'mocapmath.js'));

const cada = (a, paso) => Array.from(a).filter((_, i) => i % paso === 0).map((v) => +v.toFixed(4));
const v3 = (a, k = 0) => [a[3 * k], a[3 * k + 1], a[3 * k + 2]];
const ang = (a, b) => Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))) * 180 / Math.PI;

// 1. los dos testigos: un minuto de la muñeca inventada (b = 0.5 °/s), a 25 muestras por segundo
const sim = F.inclinacion();
const testigos = {
  t: cada(sim.t, 4), verdad: cada(sim.verdad, 4), acel: cada(sim.acel, 4),
  giro: cada(F.soloGiro(sim.giro, sim.hz, sim.verdad[0]), 4),
  filtro: cada(F.complementario(sim.giro, sim.acel, sim.hz, 1, sim.verdad[0]), 4),
  b: sim.b,
};

// 2. el resorte: la mano quieta, un giroscopio con sesgo b = 0.5 °/s, varios k; el error durante 15 s
const n15 = 1500, cte = (v) => new Float64Array(n15).fill(v);
const resorte = { t: cada(Float64Array.from({ length: n15 }, (_, i) => i / 100), 5), b: 0.5, curvas: {} };
for (const k of [0.25, 0.5, 1, 2]) resorte.curvas[k] = cada(F.complementario(cte(0.5), cte(0), 100, k, 0), 5);

// 3. el valle: el error rms para k de 0.01 a 50 por segundo, con sacudidas y sin ellas
const valle = {
  con: F.valle(sim, 60, 500).map((p) => [+p.k.toFixed(5), +p.rms.toFixed(4)]),
  sin: F.valle(F.inclinacion({ sacudidas: 0 }), 60, 500).map((p) => [+p.k.toFixed(5), +p.rms.toFixed(4)]),
};

// 5. Mahony en 3D (apuntar, con ruido y sesgo): la inclinación con Kp = 0 y Kp = 2, el rumbo y ∫ b·ĝ dt
const imu = M.synth('apuntar', 'l', { noise: true, loops: 6 });
const X0 = v3(imu.truth.X), Z0 = v3(imu.truth.Z), frame0 = [X0, M.vec.cross(Z0, X0), Z0], psi0 = M.headingOf(v3(imu.truth.F));
const errs = (kp) => F.erroresAntebrazo(imu.truth.F, M.reconstruct(imu, 'l', { kp, frame0, psi0 }).F);
const e0 = errs(0), e2 = errs(2), paso3 = Math.round(imu.hz / 10);
const sinNaN = (a) => Array.from(a, (v) => (Number.isNaN(v) ? null : +v.toFixed(3))).filter((_, i) => i % paso3 === 0);
const mahony = {
  t: Array.from({ length: imu.n }, (_, i) => +(i / imu.hz).toFixed(3)).filter((_, i) => i % paso3 === 0),
  incl0: sinNaN(e0.incl), incl2: sinNaN(e2.incl), rumbo2: sinNaN(e2.rumbo), pred: sinNaN(F.derivaPredicha(imu)),
};

// el método de proyección contra la fusión, caminando (sin ruido): el error del antebrazo y su elevación
const cam = M.synth('caminar', 'l', { noise: false });
const c0 = [v3(cam.truth.X), M.vec.cross(v3(cam.truth.Z), v3(cam.truth.X)), v3(cam.truth.Z)];
const cpsi = M.headingOf(v3(cam.truth.F));
const recs = { fusion: M.reconstruct(cam, 'l', { method: 'fusion', frame0: c0, psi0: cpsi }),
  proyeccion: M.reconstruct(cam, 'l', { method: 'proyeccion', frame0: c0, psi0: cpsi }) };
const paso4 = Math.round(cam.hz / 20), proyeccion = { t: [], elev: [], fusion: [], proyeccion: [] };
for (let k = 0; k < cam.n; k += paso4) {
  const Fv = v3(cam.truth.F, k);
  proyeccion.t.push(+(k / cam.hz).toFixed(3));
  proyeccion.elev.push(+(Math.asin(Math.max(-1, Math.min(1, Fv[1]))) * 180 / Math.PI).toFixed(2));
  for (const m of ['fusion', 'proyeccion']) proyeccion[m].push(+ang(Fv, v3(recs[m].F, k)).toFixed(2));
}

// 4. lo que lee de la gravedad un reloj inclinado, atornillado y con rumbo (para comprobar la figura)
const gravedad = (incl, rumbo, torn) => F.gravedadLeida(incl, rumbo, torn).map((v) => +v.toFixed(3));

process.stdout.write(JSON.stringify({
  testigos, resorte, valle, mahony, proyeccion,
  gravedad: { base: gravedad(20, 0, 0), rumbo: gravedad(20, 70, 0), incl: gravedad(50, 0, 0), torn: gravedad(20, 0, 40) },
}));
