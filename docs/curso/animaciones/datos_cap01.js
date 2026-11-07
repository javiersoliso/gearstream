// Los números de referencia de las animaciones del capítulo 1, de la misma cuenta que usa el mocap
// (server/web/mocapmath.js: watchOf y synth). cap01.py lo corre y dibuja lo que sale.
//   node docs/curso/animaciones/datos_cap01.js
'use strict';
const path = require('path');
const M = require(path.join(__dirname, '..', '..', '..', 'server', 'web', 'mocapmath.js'));

const redondear = (a) => Array.from(a, (v) => Math.round(v * 1e5) / 1e5);
const columna = (a, i) => { const o = []; for (let k = i; k < a.length; k += 3) o.push(a[k]); return o; };

// el reloj en las dos muñecas, con la misma pose
const pose = M.ANIMS.apuntar.pose(0, 'l');
const lados = {};
for (const lado of ['l', 'r']) {
  const w = M.watchOf(M.build(M.ANIMS.apuntar.pose(0, lado)), lado);
  lados[lado] = { X: w.X, Y: w.Y, Z: w.Z, F: w.F };
}

// lo que el mocap le suma a la verdad: la resta de la lectura con ruido menos la lectura limpia
const limpio = M.synth('tablet', 'l', {}), sucio = M.synth('tablet', 'l', { noise: true });
const resta = (a, b) => Array.from(a, (v, k) => v - b[k]);
const extra = resta(sucio.gyr, limpio.gyr);

// el mismo reloj quieto, 40 vueltas seguidas (320 s): para sumar muchos azares y ver crecer la suma
const limpioL = M.synth('tablet', 'l', { loops: 40 }), sucioL = M.synth('tablet', 'l', { noise: true, loops: 40 });
const extraL = resta(sucioL.gyr, limpioL.gyr);

// una lectura con movimiento: acelerómetro y gravedad en el mismo instante
const mov = M.synth('apuntar', 'l', { noise: true });

process.stdout.write(JSON.stringify({
  lados,
  sesgo: sucio.bias,
  extra: [0, 1, 2].map((i) => redondear(columna(extra, i))),
  largo: redondear(columna(extraL, 2)),
  hz: mov.hz,
  acc: [0, 1, 2].map((i) => redondear(columna(mov.acc, i))),
  grav: [0, 1, 2].map((i) => redondear(columna(mov.grav, i))),
  gyr: [0, 1, 2].map((i) => redondear(columna(mov.gyr, i))),
}));
