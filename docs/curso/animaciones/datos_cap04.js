// Los números de las animaciones del capítulo 4: lo que leerían el acelerómetro y la gravedad del reloj en la
// animación de apuntar, de la misma cuenta que usa el mocap (server/web/mocapmath.js: synth), y las lecturas de
// las posturas (fusionmath.js: gravedadLeida). cap04.py lo corre y lee el JSON que imprime.
//   node docs/curso/animaciones/datos_cap04.js
'use strict';
const path = require('path');
const web = path.join(__dirname, '..', '..', '..', 'server', 'web');
const M = require(path.join(web, 'mocapmath.js'));
const F = require(path.join(web, 'fusionmath.js'));

const imu = M.synth('apuntar', 'l', { noise: false });
const v3 = (a, k) => [a[3 * k], a[3 * k + 1], a[3 * k + 2]];
const paso = Math.round(imu.hz / 50);
const out = { t: [], acc: [], grav: [], lineal: [], desvio: [] };
for (let k = 0; k < imu.n; k += paso) {
  const a = v3(imu.acc, k), g = v3(imu.grav, k), l = M.vec.sub(a, g);
  const c = M.vec.dot(a, g) / (M.vec.len(a) * M.vec.len(g));
  out.t.push(+(k / imu.hz).toFixed(3));
  out.acc.push(+M.vec.len(a).toFixed(3));
  out.grav.push(+M.vec.len(g).toFixed(3));
  out.lineal.push(+M.vec.len(l).toFixed(3));
  out.desvio.push(+(Math.acos(Math.max(-1, Math.min(1, c))) * 180 / Math.PI).toFixed(2));   // cuánto se equivoca "arriba = acelerómetro"
}
out.rumbo = [0, 90, 200].map((r) => F.gravedadLeida(30, r, 0).map((x) => +x.toFixed(4)));   // la misma inclinación, tres rumbos
process.stdout.write(JSON.stringify(out));
