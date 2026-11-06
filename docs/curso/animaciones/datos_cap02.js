// Los números de referencia de las animaciones del capítulo 2, de la misma cuenta que usa el mocap
// (server/web/mocapmath.js: dot, cross, len, unit, watchOf y headingOf). cap02.py lo corre y compara su copia con esta.
//   node docs/curso/animaciones/datos_cap02.js
'use strict';
const path = require('path');
const M = require(path.join(__dirname, '..', '..', '..', 'server', 'web', 'mocapmath.js'));
const { dot, cross, len, unit } = M.vec;

const a = [2, 1, 2], b = [-1, 3, 0.5];
const brazo = { wr: [0, 1, 0], F: [0, 0, -1], d: [0, 1, 0], el: [0, 1, 0.27] };    // un antebrazo hacia adelante, dorso arriba
const dos = { arms: { l: brazo, r: brazo } };
const ejes = (w) => ({ X: w.X, Y: w.Y, Z: w.Z });
process.stdout.write(JSON.stringify({
  a, b, dot: dot(a, b), cross: cross(a, b), len: len(a), unit: unit(a),
  izquierda: ejes(M.watchOf(dos, 'l')), derecha: ejes(M.watchOf(dos, 'r')),
  rumbos: [[1, 0, 0], [0, 0, 1], [-1, 0, -1]].map((F) => M.headingOf(F)),
}));
