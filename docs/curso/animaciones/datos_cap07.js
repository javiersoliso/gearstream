// Los números de las animaciones del capítulo 7, sacados de la misma cuenta que usan las páginas y las pruebas
// (server/web/mocapmath.js y la copia de la cadena del cursor que tiene tools/test_cursor.js). cap07.py lo corre, dibuja
// con estos números y comprueba que la copia en JS da lo mismo que tools/air_mouse.py.
//   node docs/curso/animaciones/datos_cap07.js
'use strict';
const path = require('path');
const raiz = path.join(__dirname, '..', '..', '..');
const M = require(path.join(raiz, 'server', 'web', 'mocapmath.js'));
const { OneEuro, cadena } = require(path.join(raiz, 'tools', 'test_cursor.js'));

// el rayo de verdad y el cursor (D·θ) en la animación de apuntar, sin ruido
const AP = M.ANIMS.apuntar, imu = M.synth('apuntar', 'l', { noise: false }), rec = M.reconstruct(imu, 'l', {});
const el0 = M.build(AP.pose(0, 'l')).arms.l.el, p0 = AP.target(0), D = M.vec.len(M.vec.sub(p0, el0));
const tr = M.cursorTrack(rec.rates, imu.hz, p0, D * Math.PI / 180);
const paso = 5, apuntar = { D, t: [], rayo: [], cursor: [], pantalla: AP.screen, marcas: AP.marks };
for (let k = 0; k < imu.n; k += paso) {
  const p = AP.target(k / imu.hz);
  apuntar.t.push(+(k / imu.hz).toFixed(3));
  apuntar.rayo.push([p[0] - AP.screen.c[0], p[1] - AP.screen.c[1]]);
  apuntar.cursor.push([tr[3 * k] - AP.screen.c[0], tr[3 * k + 1] - AP.screen.c[1]]);
}

// una señal fija para comparar la copia con la de verdad
const n = 400, prueba = Array.from({ length: n }, (_, k) => 30 * Math.sin(k / 25) + 90 * Math.exp(-(((k - 200) / 30) ** 2)) + 2 * Math.sin(k * 1.7));
const euro = new OneEuro(2, 0.01, 1);
process.stdout.write(JSON.stringify({
  apuntar, prueba,
  euro: prueba.map((x) => euro.paso(x, 0.01)),
  cadenaYaw: cadena(prueba, prueba.map(() => 0)),
  cadenaPitch: cadena(prueba.map(() => 0), prueba),
}));
