// Los números de referencia de las animaciones del capítulo 5, de la misma cuenta que usa el mocap
// (server/web/mocapmath.js: rot, qmul y qcols). cap05.py lo corre y compara su propia cuenta con esta.
//   node docs/curso/animaciones/datos_cap05.js
'use strict';
const path = require('path');
const M = require(path.join(__dirname, '..', '..', '..', 'server', 'web', 'mocapmath.js'));
const { rot } = M.vec, { qmul, qcols } = M.quat;
const D = Math.PI / 180;
const q = (eje, ang) => { const n = Math.hypot(...eje), s = Math.sin(ang / 2) / n; return [Math.cos(ang / 2), eje[0] * s, eje[1] * s, eje[2] * s]; };

const v = [0.3, -0.5, 0.8], k = [1, 2, 2];
const qa = q([1, 0, 0], 90 * D), qb = q([0, 1, 0], 90 * D);
process.stdout.write(JSON.stringify({
  rot: rot(v, k, 70 * D),                               // Rodrigues
  xLuegoY: rot(rot(v, [1, 0, 0], 90 * D), [0, 1, 0], 90 * D),
  yLuegoX: rot(rot(v, [0, 1, 0], 90 * D), [1, 0, 0], 90 * D),
  qmul: qmul(qb, qa),                                   // primero x, después y
  qcols: qcols(qmul(qb, qa)),
  qcolsDeK: qcols(q(k, 70 * D)),
  // girar una flecha con el cuaternión: q ⊗ (0, v) ⊗ q*, con q* = (w, −x, −y, −z)
  qvq: (() => { const qk = q(k, 70 * D), qc = [qk[0], -qk[1], -qk[2], -qk[3]]; return qmul(qmul(qk, [0, ...v]), qc).slice(1); })(),
}));
