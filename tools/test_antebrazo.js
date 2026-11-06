// Pruebas del capítulo 6 del curso (Del reloj al antebrazo): lo que el capítulo afirma sobre Wrist.rates de
// server/web/wrist.js, comprobado con giros fabricados donde la respuesta se conoce. Las pruebas de fabricar un giro
// corren también contra tu ejercicio.
//   node tools/test_antebrazo.js              # la cuenta del curso
//   node tools/test_antebrazo.js --ejercicio  # tu ω, en docs/curso/ejercicios/cap06.js
'use strict';
const path = require('path');
const assert = require('assert');
const web = path.join(__dirname, '..', 'server', 'web');
const { Wrist, forearmOf } = require(path.join(web, 'wrist.js'));
const M = require(path.join(web, 'mocapmath.js'));
const { subida } = require(path.join(web, 'fusionmath.js'));
const { dot, cross, len, unit, mul, add, rot } = M.vec;

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
const D = Math.PI / 180;
const rates = (w, g, mano) => new Wrist(mano).rates(w, g);        // uno nuevo cada vez: no arrastra el sesgo que aprende

// Un antebrazo en un mundo con z arriba: elevación e y dirección psi (grados), atornillado torn. Devuelve el marco del
// reloj como lo arma watchOf: en la izquierda x va a la mano, en la derecha al codo, y z sale del dorso.
function brazo(e, psi = 0, torn = 0) {
  const c = Math.cos(e * D), s = Math.sin(e * D), h = psi * D;
  const F = [c * Math.cos(h), c * Math.sin(h), s];
  const d0 = [-s * Math.cos(h), -s * Math.sin(h), c];
  return { F, d: rot(d0, F, torn * D), wr: [0, 0, 0], el: mul(F, -1) };
}
function ejesDe(b, mano) {
  const w = M.watchOf({ arms: { l: b, r: b } }, mano === 'left' ? 'l' : 'r');
  return [w.X, w.Y, w.Z];
}
const lee = (v, E) => E.map((e) => dot(v, e));                     // un vector del mundo, leído en el reloj
const ARRIBA = [0, 0, 1];
const lectura = (omegaMundo, b, mano) => { const E = ejesDe(b, mano); return { w: lee(omegaMundo, E), g: lee(ARRIBA, E) }; };

// ---------- el antebrazo es un eje del reloj ----------
console.log('El antebrazo');
for (const mano of ['left', 'right']) {
  const b = brazo(25, 40, 30), { w: fEnReloj } = lectura(b.F, b, mano);
  fEnReloj.forEach((x, i) => near(x, forearmOf(mano)[i], 1e-12, `el antebrazo leído en el reloj (${mano})`));
}
ok('leído en el reloj, el antebrazo es (1, 0, 0) en la izquierda y (−1, 0, 0) en la derecha');
const colgando = brazo(-90);
near(lectura(colgando.F, colgando, 'left').g[0] * 9.81, -9.81, 1e-9, 'colgando, la izquierda lee x = −9.81');
near(lectura(colgando.F, colgando, 'right').g[0] * 9.81, 9.81, 1e-9, 'colgando, la derecha lee x = +9.81');
ok('con el brazo colgando la gravedad marca x = −9.81 en la izquierda y +9.81 en la derecha');

// ---------- los signos ----------
console.log('Los signos');
const b0 = brazo(0), P = 100;
for (const mano of ['left', 'right']) {
  const dt = 0.001;
  const giro = (omega) => { const n = len(omega); return { F: rot(b0.F, omega, n * D * dt), d: rot(b0.d, omega, n * D * dt) }; };
  const paraArriba = [0, -P, 0], izquierda = [0, 0, P], tornillo = mul(b0.F, P);
  const r1 = rates(...Object.values(lectura(paraArriba, b0, mano)), mano);
  near(r1.pitch, P, 1e-9, 'pitch'); near(r1.yaw, 0, 1e-9, 'sin yaw'); near(r1.roll, 0, 1e-9, 'sin roll');
  assert.ok(giro(paraArriba).F[2] > 0, 'con pitch positivo la mano sube');
  const r2 = rates(...Object.values(lectura(izquierda, b0, mano)), mano);
  near(r2.yaw, P, 1e-9, 'yaw'); near(r2.pitch, 0, 1e-9, 'sin pitch'); near(r2.roll, 0, 1e-9, 'sin roll');
  assert.ok(giro(izquierda).F[1] > 0, 'con yaw positivo la mano va a la izquierda');
  const r3 = rates(...Object.values(lectura(tornillo, b0, mano)), mano);
  near(r3.roll, P, 1e-9, 'roll'); near(r3.yaw, 0, 1e-9, 'sin yaw'); near(r3.pitch, 0, 1e-9, 'sin pitch');
  assert.ok(giro(tornillo).d[1] < 0, 'con roll positivo el dorso se va a la derecha: horario visto desde el codo');
}
ok('en las dos manos: pitch positivo sube la mano, yaw positivo la lleva a la izquierda y roll positivo atornilla');

// ---------- la base no es perpendicular ----------
console.log('La base {g, f, f × g}');
for (const e of [-60, -30, 0, 20, 45, 70]) {
  const b = brazo(e, 15, 35);
  const { g } = lectura(ARRIBA, b, 'left'), f = forearmOf('left');
  near(dot(g, f), Math.sin(e * D), 1e-12, 'g·f es el seno de la elevación');
  near(1 - dot(g, f) ** 2, len(cross(f, g)) ** 2, 1e-12, '1 − (g·f)² = |f × g|²');
  const p = unit(cross(f, g));
  near(dot(p, f), 0, 1e-12, 'p forma ángulo recto con f');
  near(dot(p, g), 0, 1e-12, 'p forma ángulo recto con g');
}
ok('g·f es el seno de la elevación, 1 − (g·f)² es |f × g|² y p forma ángulo recto con f y con g');

// ---------- atornillar no mueve el cursor ----------
console.log('Atornillar no mueve el cursor');
for (const mano of ['left', 'right']) {
  for (let e = -89; e <= 89; e += 4) {
    const b = brazo(e, 30, 20), r = rates(...Object.values(lectura(mul(b.F, 100), b, mano)), mano);
    near(r.yaw, 0, 1e-9, `yaw a ${e}°`); near(r.pitch, 0, 1e-9, `pitch a ${e}°`); near(r.roll, 100, 1e-9, `roll a ${e}°`);
  }
}
ok('100 °/s de roll puro dan yaw 0 y pitch 0 de −89° a 89°, en las dos manos');
{
  const b = brazo(45), { w, g } = lectura(mul(b.F, 100), b, 'left');
  near(dot(w, g), 70.71, 0.01, 'sin corregir, ω·g se lleva parte del roll');
  ok(`sin corregir, ω·g daría ${dot(w, g).toFixed(1)} °/s con el antebrazo a 45°: atornillar movería el cursor`);
  let peor = 0;
  for (let i = 0; i < 400; i++) {
    const gm = unit([Math.sin(i), Math.cos(3 * i), Math.sin(7 * i + 1)]);      // arriba equivocado: cualquiera
    const r = rates(mul([1, 0, 0], 100), gm, 'left');
    peor = Math.max(peor, Math.abs(r.yaw), Math.abs(r.pitch));
  }
  near(peor, 0, 1e-9, 'tampoco con una vertical equivocada');
  ok('y no depende de la vertical: con 400 arribas equivocados el roll puro sigue sin dar yaw ni pitch');
}

// ---------- un reloj girado sobre la muñeca ----------
{
  const d = 10 * D, fVerdad = [Math.cos(d), Math.sin(d), 0];
  const r = rates(mul(fVerdad, 100), [0, 0, 1], 'left');
  near(Math.hypot(r.yaw, r.pitch), 100 * Math.sin(d), 1e-9, 'se escapa el seno del error');
  near(r.roll, 100 * Math.cos(d), 1e-9, 'el roll pierde el coseno');
  ok(`con el reloj girado 10° en la muñeca, 100 °/s de atornillar dejan ${Math.hypot(r.yaw, r.pitch).toFixed(1)} °/s en el cursor`);
}

// ---------- la mano equivocada ----------
console.log('La mano equivocada');
for (const e of [-40, 0, 35]) {
  const b = brazo(e, 20, 10), omega = [31, -47, 62], { w, g } = lectura(omega, b, 'right');
  const bien = rates(w, g, 'right'), mal = rates(w, g, 'left'), izq = rates(...Object.values(lectura(omega, b, 'left')), 'left');
  near(mal.pitch, -bien.pitch, 1e-9, 'pitch cambia de signo');
  near(mal.roll, -bien.roll, 1e-9, 'roll cambia de signo');
  near(mal.yaw, bien.yaw, 1e-9, 'yaw no cambia');
  for (const k of ['yaw', 'pitch', 'roll']) near(bien[k], izq[k], 1e-9, `${k} dice lo mismo en las dos manos`);
}
ok('con f al revés, pitch y roll cambian de signo y el yaw no; bien puesto, las dos manos dicen lo mismo');

// ---------- cerca de la vertical ----------
console.log('Con el antebrazo casi vertical');
const eLim = Math.acos(0.3) / D;
near(eLim, 72.54, 0.01, 'el límite');
near(90 - eLim, 17.46, 0.01, 'el límite, desde la vertical');
ok(`el mínimo de 0.09 empieza a mandar a ${eLim.toFixed(1)}° de elevación, a ${(90 - eLim).toFixed(1)}° de la vertical`);
{
  const a = 100, debajo = brazo(70), encima = brazo(80);
  const r1 = rates(...Object.values(lectura(mul(ARRIBA, a), debajo, 'left')), 'left');
  const r2 = rates(...Object.values(lectura(mul(ARRIBA, a), encima, 'left')), 'left');
  near(r1.yaw, a, 1e-9, 'a 70° el yaw es exacto');
  near(r2.yaw, a * Math.cos(80 * D) ** 2 / 0.09, 1e-9, 'a 80° se apaga');
  ok(`100 °/s alrededor de la vertical dan yaw ${r1.yaw.toFixed(0)} a 70° y ${r2.yaw.toFixed(0)} a 80°: se apaga en vez de explotar`);
  const r3 = rates(...Object.values(lectura([0, -100, 0], encima, 'left')), 'left');
  near(r3.pitch, 0, 1e-12, 'pasado el límite, sin pitch');
  ok('pasado el mismo límite, |f × g| < 0.3 y el pitch queda en cero');
  let peor = 0;
  for (let e = 0; e <= 89; e += 0.5) {
    const c = Math.cos(e * D), s = Math.sin(e * D), g = [s, 0, c], f = [1, 0, 0];
    const u = unit(add(g, mul(f, -s)));                          // el ruido que más molesta: en el plano de f y g, en ángulo recto con f
    peor = Math.max(peor, Math.abs(rates(mul(u, 10), g, 'left').yaw) / 10);
  }
  near(peor, 1 / 0.3, 0.02, 'el ruido se agranda hasta 1/0.3');
  ok(`un ruido se agranda ${peor.toFixed(2)} veces en el peor punto; sin ese mínimo crecería sin límite`);
}
{
  const r = rates([0.3, 0.2, 0.1], [0, 0, 1], 'left');
  near(r.yaw, 0, 0, 'yaw apagado'); near(r.pitch, 0, 0, 'pitch apagado');
  const r2 = rates([1.5, 0.2, 0.1], [0, 0, 1], 'left');
  near(r2.roll, 1.5, 1e-9, 'el roll sigue'); near(r2.yaw, 0, 0, 'yaw apagado');
  ok('por debajo de 0.6 °/s el yaw y el pitch se apagan juntos; el roll no');
}

// ---------- las otras copias de la cuenta ----------
console.log('Las otras copias de la cuenta');
{
  for (let i = 0; i < 300; i++) {
    const w = [90 * Math.sin(i), 120 * Math.cos(2 * i), 70 * Math.sin(5 * i)], g = unit([Math.cos(3 * i), Math.sin(i), Math.cos(i)]);
    near(subida(w, mul(g, 9.81), [1, 0, 0]), (() => { const c = cross([1, 0, 0], g), n = len(c); return n > 0.3 ? dot(w, c) / n : 0; })(), 1e-9, 'subida');
  }
  ok('subida de fusionmath.js da el mismo pitch que Wrist.rates, antes de apagar lo muy lento');
  // la lectura del avatar (avatar.js, onGyro), copiada: usa three.js y no se puede cargar aquí
  const avatar = (w, up, f) => { const side = unit(cross(up, f)); return { yaw: dot(w, up), pitch: dot(w, side), roll: dot(w, f) }; };
  const b = brazo(45), { w, g } = lectura(mul(b.F, 100), b, 'left'), a = avatar(w, g, [1, 0, 0]);
  near(a.yaw, 70.71, 0.01, 'el avatar no corrige');
  const up = lectura([0, -100, 0], brazo(0), 'left'), a2 = avatar(up.w, up.g, [1, 0, 0]), r2 = rates(up.w, up.g, 'left');
  near(a2.pitch, -r2.pitch, 1e-9, 'el pitch del avatar va al revés');
  ok(`las cifras del avatar no corrigen el yaw (${a.yaw.toFixed(1)} °/s de roll puro a 45°) y su pitch tiene el signo contrario`);
}

// ---------- el ejercicio ----------
function fabricarDelCurso(a, b, c, g, f) {
  const p = unit(cross(f, g));
  return add(add(mul(g, a), mul(f, b)), mul(p, c));
}
const rollQueSaleDelCurso = (a, b, g, f) => b + a * dot(g, f);

function probar({ fabricar, rollQueSale }, nombre) {
  console.log(`Fabricar un giro (${nombre})`);
  const trios = [[30, -50, 20], [-80, 120, 45], [15, 15, -90], [200, -10, 5]];
  let casos = 0;
  for (const mano of ['left', 'right']) {
    const f = forearmOf(mano);
    for (let e = -70; e <= 70; e += 10) {
      for (const torn of [0, 35, -120]) {
        const { g } = lectura(ARRIBA, brazo(e, 15, torn), mano);
        for (const [a, b, c] of trios) {
          const w = fabricar(a, b, c, g, f);
          assert.strictEqual(w.length, 3, 'devuelve tres números');
          const r = rates(w, g, mano);
          near(r.yaw, a, 1e-9, `yaw a ${e}°`);
          near(r.pitch, c, 1e-9, `pitch a ${e}°`);
          near(r.roll, rollQueSale(a, b, g, f), 1e-9, `roll a ${e}°`);
          casos++;
        }
      }
    }
  }
  ok(`en ${casos} casos, de −70° a 70° y en las dos manos, rates recupera a (yaw) y c (pitch) exactos`);
  const g45 = lectura(ARRIBA, brazo(45), 'left').g, f = forearmOf('left');
  const r45 = rates(fabricar(100, 50, 0, g45, f), g45, 'left');
  assert.ok(Math.abs(r45.roll - 50) > 10, 'con g·f ≠ 0 el roll no es b');
  ok(`el roll no es b: con el antebrazo a 45°, a = 100 y b = 50 dan roll = ${r45.roll.toFixed(1)}`);
  const g0 = lectura(ARRIBA, brazo(0), 'left').g;
  near(rates(fabricar(100, 50, 0, g0, f), g0, 'left').roll, 50, 1e-9, 'con el antebrazo horizontal sí');
  ok('con el antebrazo horizontal g·f = 0, y ahí el roll sí es b');
}

if (process.argv.includes('--ejercicio')) {
  probar(require(path.join(__dirname, '..', 'docs', 'curso', 'ejercicios', 'cap06.js')), 'tu ejercicio');
} else {
  probar({ fabricar: fabricarDelCurso, rollQueSale: rollQueSaleDelCurso }, 'del curso');
}
console.log('\nTodo pasa.');
