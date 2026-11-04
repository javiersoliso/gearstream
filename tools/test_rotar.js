// Pruebas del capítulo 5 del curso (Rotar): lo que el capítulo afirma sobre rot, qmul y qcols de
// server/web/mocapmath.js, comprobado con números. Las pruebas del cuaternión corren también contra tu ejercicio.
//   node tools/test_rotar.js              # la cuenta del curso
//   node tools/test_rotar.js --ejercicio  # tu cuaternión, en docs/curso/ejercicios/cap05.js
'use strict';
const path = require('path');
const assert = require('assert');
const M = require(path.join(__dirname, '..', 'server', 'web', 'mocapmath.js'));
const { rot, dot, len } = M.vec, { qmul, qcols } = M.quat;

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a.toFixed(6)} vs ${b} (±${tol})`);
const nearV = (a, b, tol, msg) => a.forEach((x, i) => near(x, b[i], tol, `${msg} [${i}]`));
const ok = (msg) => console.log(`  ✓ ${msg}`);
const aplicar = (cols, v) => [0, 1, 2].map((i) => cols[0][i] * v[0] + cols[1][i] * v[1] + cols[2][i] * v[2]);
const porMatriz = (A, B) => [0, 1, 2].map((j) => aplicar(A, B[j]));     // columnas de A·B
const D = Math.PI / 180;

// ---------- lo que vale para cualquier giro (no depende del ejercicio) ----------
console.log('Giros');
const v = [0.3, -0.5, 0.8], x = [1, 0, 0], y = [0, 1, 0];
for (const [k, a] of [[[1, 2, 2], 70 * D], [[0, 0, 1], 180 * D], [[-1, 0.3, 0.2], -33 * D]]) {
  near(len(rot(v, k, a)), len(v), 1e-12, 'girar no cambia el largo');
  near(dot(rot(v, k, a), k), dot(v, k), 1e-12, 'la parte a lo largo del eje no se mueve');
}
ok('rot (Rodrigues) no cambia el largo y deja quieta la parte a lo largo del eje');
const xy = rot(rot(v, x, 90 * D), y, 90 * D), yx = rot(rot(v, y, 90 * D), x, 90 * D);
assert.ok(Math.hypot(xy[0] - yx[0], xy[1] - yx[1], xy[2] - yx[2]) > 0.5, 'x y luego y no es lo mismo que al revés');
ok(`90° en x y luego en y: (${xy.map((c) => c.toFixed(2))}); al revés: (${yx.map((c) => c.toFixed(2))}). No conmutan`);

// ---------- el cuaternión: lo que tiene que cumplir cualquiera que lo escriba ----------
function cuaternionDelCurso(eje, angulo) {
  const n = Math.hypot(...eje), s = Math.sin(angulo / 2) / n;
  return [Math.cos(angulo / 2), eje[0] * s, eje[1] * s, eje[2] * s];
}

function probar(cuaternion, nombre) {
  console.log(`El cuaternión (${nombre})`);
  const casos = [[[1, 2, 2], 70 * D], [[0, 0, 3], 180 * D], [[-1, 0.3, 0.2], -33 * D], [[0, 1, 0], 359 * D]];
  for (const [k, a] of casos) {
    const q = cuaternion(k, a);
    assert.strictEqual(q.length, 4, 'devuelve cuatro números');
    near(Math.hypot(...q), 1, 1e-9, 'tiene largo 1');
    nearV(aplicar(qcols(q), v), rot(v, k, a), 1e-9, `gira igual que rot (eje ${k}, ${(a / D).toFixed(0)}°)`);
  }
  ok('largo 1, y gira igual que Rodrigues');

  const qx = cuaternion(x, 90 * D), qy = cuaternion(y, 90 * D);
  porMatriz(qcols(qy), qcols(qx)).forEach((col, j) => nearV(qcols(qmul(qy, qx))[j], col, 1e-9, 'qmul es multiplicar matrices'));
  nearV(aplicar(qcols(qmul(qy, qx)), v), xy, 1e-9, 'q_y ⊗ q_x es x y luego y');
  ok('componer giros es multiplicar: qcols(q_y ⊗ q_x) = R_y · R_x');

  const q1 = cuaternion([1, 2, 2], 70 * D), q2 = cuaternion([1, 2, 2], 70 * D + 2 * Math.PI);
  nearV(q2, q1.map((c) => -c), 1e-9, 'una vuelta más da −q');
  qcols(q2).forEach((col, j) => nearV(col, qcols(q1)[j], 1e-9, 'q y −q son el mismo giro'));
  ok('una vuelta entera cambia q por −q, que es el mismo giro');

  // integrar: 100 giros chiquitos de ω durante 1 s son un solo giro de |ω| alrededor de ω
  const w = [0.4, -1.1, 2.0], hz = 100, wn = Math.hypot(...w);
  let q = [1, 0, 0, 0];
  for (let i = 0; i < hz; i++) {
    q = qmul(q, cuaternion(w, wn / hz));
    const n = Math.hypot(...q); q = q.map((c) => c / n);
  }
  nearV(aplicar(qcols(q), v), rot(v, w, wn), 1e-9, 'muchos giros chiquitos dan el grande');
  ok('integrar 100 muestras de ω da el giro de |ω|·t alrededor de ω');
}

if (process.argv.includes('--ejercicio')) {
  const archivo = path.join(__dirname, '..', 'docs', 'curso', 'ejercicios', 'cap05.js');
  probar(require(archivo).cuaternion, 'tu ejercicio');
} else {
  probar(cuaternionDelCurso, 'del curso');
}
console.log('\nTodo pasa.');
