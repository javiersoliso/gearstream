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

// ---------- multiplicar matrices (2D, por filas): aplicar una y después la otra ----------
console.log('Multiplicar matrices');
const mm = (A, B) => A.map((fila) => B[0].map((_, j) => fila.reduce((s, a, k) => s + a * B[k][j], 0)));
const mv = (A, w) => A.map((fila) => fila.reduce((s, a, k) => s + a * w[k], 0));
const T = (A) => A[0].map((_, j) => A.map((fila) => fila[j]));
const R2 = (a) => [[Math.cos(a), -Math.sin(a)], [Math.sin(a), Math.cos(a)]];
const A2 = R2(30 * D), B2 = [[1.5, 0], [0, 0.6]], BA = mm(B2, A2), AB = mm(A2, B2), w2 = [2, 1];
nearV(mv(BA, w2), mv(B2, mv(A2, w2)), 1e-12, 'B(Av) = (BA)v');
nearV([BA[0][0], BA[1][0]], mv(B2, [A2[0][0], A2[1][0]]), 1e-12, 'cada columna de BA es B por una columna de A');
nearV([BA[0][0], BA[1][0]], [1.30, 0.30], 0.005, 'la flecha verde termina en (1.30, 0.30)');
assert.ok(Math.abs(AB[0][1] - BA[0][1]) > 0.4, 'AB no es BA');
const I2 = [[1, 0], [0, 1]], RtR = mm(T(A2), A2);
RtR.forEach((fila, i) => nearV(fila, I2[i], 1e-12, 'RᵀR = I'));
for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) near(RtR[i][j], A2[0][i] * A2[0][j] + A2[1][i] * A2[1][j], 1e-12, 'RᵀR es la tabla de productos punto entre columnas');
mm(R2(-30 * D), A2).forEach((fila, i) => nearV(fila, I2[i], 1e-12, 'la inversa de un giro es girar al revés'));
T(A2).forEach((fila, i) => nearV(fila, R2(-30 * D)[i], 1e-12, 'Rᵀ es girar −θ'));
ok(`BA = [[${BA[0].map((c) => c.toFixed(2))}], [${BA[1].map((c) => c.toFixed(2))}]] ≠ AB; RᵀR es la tabla de productos punto y da I; R⁻¹ = Rᵀ`);

// ---------- el eje: dos planos que se cortan ----------
const Rx = (a) => [[1, 0, 0], [0, Math.cos(a), -Math.sin(a)], [0, Math.sin(a), Math.cos(a)]];
const Rz = (a) => [[Math.cos(a), -Math.sin(a), 0], [Math.sin(a), Math.cos(a), 0], [0, 0, 1]];
const Rg = mm(Rz(60 * D), Rx(90 * D)), resta = (a, b) => a.map((c, i) => c - b[i]);
const corte = M.vec.unit(M.vec.cross(resta(x, mv(Rg, x)), resta(y, mv(Rg, y))));
nearV(mv(Rg, corte), corte, 1e-12, 'los dos planos se cortan en la flecha que el giro no mueve');
ok(`90° en x y después 60° en z: los dos planos se cortan en (${corte.map((c) => c.toFixed(2))}), que el giro no mueve`);

// ---------- un giro chiquito es casi sumar: de ahí sale q + ½ q ⊗ (0, ω) Δt ----------
near(Math.cos(0.02), 0.9998, 1e-6, 'cos 0.02'); near(Math.sin(0.02), 0.019999, 1e-6, 'sen 0.02');
{
  const q0 = [0.6, 0.48, 0, 0.64], w = [0.4, -1.1, 2.0], dt = 0.01;
  const suma = qmul(q0, [0, ...w]).map((c, i) => q0[i] + 0.5 * c * dt), casi = qmul(q0, [1, ...w.map((c) => c * dt / 2)]);
  nearV(suma, casi, 1e-12, 'q ⊗ (1, ωΔt/2) = q + ½ q ⊗ (0, ω) Δt');
}
ok('con 0.02 rad, cos = 0.9998 y sen = 0.019999; y q ⊗ (1, ωΔt/2) = q + ½ q ⊗ (0, ω) Δt');

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

  // la regla de ⊗ con punto y cruz, y girar una flecha con q ⊗ (0, v) ⊗ q*
  const regla = (a, b) => { const av = a.slice(1), bv = b.slice(1), c = M.vec.cross(av, bv);
    return [a[0] * b[0] - dot(av, bv), ...[0, 1, 2].map((i) => a[0] * bv[i] + b[0] * av[i] + c[i])]; };
  const conj = (q) => [q[0], -q[1], -q[2], -q[3]];
  for (const [k, a] of casos) {
    const q = cuaternion(k, a);
    nearV(regla(q, qx), qmul(q, qx), 1e-12, 'qmul es la regla de punto y cruz');
    nearV(qmul(qmul(q, [0, ...v]), conj(q)), [0, ...rot(v, k, a)], 1e-9, 'q ⊗ (0, v) ⊗ q* gira v');
    nearV(qmul(q, conj(q)), [1, 0, 0, 0], 1e-9, 'q* es el giro al revés');
  }
  ok('qmul es (a0 b0 − a·b, a0 b + b0 a + a × b), y q ⊗ (0, v) ⊗ q* gira v igual que rot');

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
