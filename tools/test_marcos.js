// Pruebas del capítulo 2 del curso (Vectores y marcos): lo que el capítulo afirma, comprobado con las funciones de
// server/web/mocapmath.js y server/web/wrist.js. Las pruebas del ángulo corren también contra tu ejercicio.
//   node tools/test_marcos.js              # la cuenta del curso
//   node tools/test_marcos.js --ejercicio  # tus ángulos, en docs/curso/ejercicios/cap02.js
'use strict';
const path = require('path');
const assert = require('assert');
const web = path.join(__dirname, '..', 'server', 'web');
const M = require(path.join(web, 'mocapmath.js'));
const { forearmOf } = require(path.join(web, 'wrist.js'));
const { dot, cross, len, unit, mul, add, sub, rot } = M.vec;

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b} (±${tol})`);
const nearV = (a, b, tol, msg) => a.forEach((x, i) => near(x, b[i], tol, `${msg} [${i}]`));
const ok = (msg) => console.log(`  ✓ ${msg}`);
const D = Math.PI / 180, G = 9.81;

// números al azar repetibles, con forma de campana
let estado = 2024;
const u = () => { estado = (estado * 16807) % 2147483647; return estado / 2147483647; };
const normal = () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u());

// ---------- vectores y largo ----------
console.log('Vectores y largo');
near(len([2, 1, 2]), 3, 1e-12, 'Pitágoras dos veces');
near(len([2, 1, 2]), Math.sqrt(Math.hypot(2, 1) ** 2 + 2 ** 2), 1e-12, 'primero el piso, después la altura');
near(Math.hypot(2, 1), 2.236, 0.001, 'la diagonal del piso');
ok('|(2, 1, 2)| = 3: Pitágoras en el piso (√5 = 2.24) y otra vez con la altura');
const leida = [3.1, -5.2, 7.7];
const uv = unit(leida);
near(len(uv), 1, 1e-12, 'unitario');
near(dot(uv, leida), len(leida), 1e-12, 'misma dirección');
ok(`dividir por el largo: (${leida}) mide ${len(leida).toFixed(2)} y queda (${uv.map((c) => c.toFixed(2))}), de largo 1`);
near(Math.abs(uv[2]), Math.sqrt(1 - uv[0] ** 2 - uv[1] ** 2), 1e-12, 'x e y dicen z salvo el signo');
ok('de largo 1, x e y deciden z salvo el signo: para la dirección bastan dos números');

// ---------- ángulos ----------
console.log('Ángulos');
const axesOf = (H) => ({ fwd: [-Math.sin(H), 0, -Math.cos(H)], right: [Math.cos(H), 0, -Math.sin(H)] });   // copia de mocapmath.js
for (const grados of [-170, -100, -20, 0, 35, 120, 179]) near(M.headingOf(axesOf(grados * D).fwd), grados, 1e-9, 'headingOf deshace axesOf');
ok('atan2 recupera el ángulo en los cuatro cuadrantes: headingOf deshace axesOf de −170° a 179°');
near(Math.atan(1 / 1) / D, Math.atan(-1 / -1) / D, 1e-12, 'y/x no distingue flechas opuestas');
near(Math.atan2(1, 1) / D, 45, 1e-12, 'atan2 de (1, 1)');
near(Math.atan2(-1, -1) / D, -135, 1e-12, 'atan2 de (−1, −1)');
near(Math.atan2(1, 0) / D, 90, 1e-12, 'atan2 con x = 0');
ok('(1, 1) y (−1, −1) dan el mismo y/x; atan2 dice 45° y −135°, y con x = 0 dice 90° sin dividir');
near(Math.sin(30 * D) / Math.cos(30 * D), Math.tan(30 * D), 1e-12, 'tan = sen/cos');

const wrap = (a) => a - 360 * Math.floor((a + 180) / 360);        // copia de wrap_deg (tools/air_mouse.py); cap02.py usa la de verdad
near(wrap(350), -10, 1e-12, '350° es −10°');
near(wrap(-10), -10, 1e-12, '−10° se queda');
near(wrap(180), -180, 1e-12, '180° queda en −180°: el intervalo es [−180°, 180°)');
near(wrap(10 - 350), 20, 1e-12, 'de 350° a 10° hay 20°');
near((350 + 10) / 2, 180, 1e-12, 'el promedio ingenuo');
near(wrap(350 + wrap(10 - 350) / 2), 0, 1e-12, 'el promedio con cuidado');
near((350 + -10) / 2, 170, 1e-12, 'el promedio ingenuo del mismo ángulo');
ok('wrap_deg: 350° → −10°; de 350° a 10° hay 20°, y su promedio es 0°, no 180°');
near(Math.floor(1.4), 1, 0, '⌊1.4⌋'); near(Math.floor(-0.4), -1, 0, '⌊−0.4⌋');
near(Math.floor((10 - 350 + 180) / 360), -1, 0, '⌊(−340 + 180)/360⌋'); near(-340 - 360 * -1, 20, 0, 'wrap(−340)');
ok('⌊ ⌋ redondea hacia abajo: ⌊1.4⌋ = 1, ⌊−0.4⌋ = −1, y con −340 da −1: −340 + 360 = 20');

// ---------- producto punto ----------
console.log('Producto punto');
const a = [2, 1, 2], b = [-1, 3, 0.5];
const ang = Math.acos(dot(a, b) / (len(a) * len(b)));
near(dot(a, b), a[0] * b[0] + a[1] * b[1] + a[2] * b[2], 1e-12, 'suma de productos');
near(dot(a, b), len(a) * len(b) * Math.cos(ang), 1e-12, '|a||b| cos θ');
for (const t of [0, 40, 90, 140, 180]) {
  const c = [Math.cos(t * D), Math.sin(t * D), 0], e = [1, 0, 0];
  near(dot(mul(c, 2), mul(e, 3)), 6 * Math.cos(t * D), 1e-12, `a·b a ${t}°`);
}
near(dot([1, 2, 0], [-2, 1, 0]), 0, 1e-12, 'en ángulo recto da cero');
ok('Σ aᵢbᵢ = |a||b| cos θ; da cero en ángulo recto y negativo pasados los 90°');
// por qué: |a − b|² desarrollado deja la suma escrita con largos, que no cambian al girar; con a sobre x es el coseno
near(dot(a, b), (len(a) ** 2 + len(b) ** 2 - len(sub(a, b)) ** 2) / 2, 1e-12, 'Σ aᵢbᵢ = ½(|a|² + |b|² − |a − b|²)');
for (const [eje, grados] of [[[0, 0, 1], 70], [[1, 2, -1], 133], [[-3, 0.5, 2], -40]]) {
  const ar = rot(a, unit(eje), grados * D), br = rot(b, unit(eje), grados * D);
  near(dot(ar, br), dot(a, b), 1e-12, `girar las dos juntas ${grados}° no cambia la suma`);
  near(len(ar), len(a), 1e-12, 'ni los largos');
}
{
  const la = 2.4, lb = 2.8, th = 50 * D, a2 = [la, 0, 0], b2 = [lb * Math.cos(th), lb * Math.sin(th), 0];
  near(dot(a2, b2), la * lb * Math.cos(th), 1e-12, 'con a sobre x, la suma es |a||b| cos θ');
  near(dot(a2, b2), 4.32, 0.005, 'los números de la animación');
}
ok('Σ aᵢbᵢ = ½(|a|² + |b|² − |a − b|²): no cambia al girar las dos juntas, y con a sobre x da |a||b| cos θ');
const sombra = mul(unit(b), dot(a, unit(b)));
near(dot(sub(a, sombra), b), 0, 1e-12, 'lo que queda es perpendicular');
ok('a menos su sombra sobre b queda en ángulo recto con b');

// ---------- producto cruz ----------
console.log('Producto cruz');
const c = cross(a, b);
near(dot(c, a), 0, 1e-12, 'perpendicular a a');
near(dot(c, b), 0, 1e-12, 'perpendicular a b');
near(len(c), len(a) * len(b) * Math.sin(ang), 1e-12, '|a||b| sen θ');
nearV(cross(b, a), mul(c, -1), 1e-12, 'al revés apunta al otro lado');
near(len(cross([2, 0, 0], [1, 1.5, 0])), 2 * 1.5, 1e-12, 'área: base por altura');
ok('a × b forma ángulo recto con los dos, mide |a||b| sen θ (el área) y b × a apunta al revés');
near(len(cross([1, 0, 0], [Math.cos(15 * D), Math.sin(15 * D), 0])), 0.26, 0.005, 'dos flechas de largo 1 a 15°');
ok('dos flechas de largo 1 a 15° dan |f × u| = 0.26: el límite de feasible (armfilter.js)');

// ---------- la mano derecha ----------
console.log('Regla de la mano derecha');
const x = [1, 0, 0], y = [0, 1, 0], z = [0, 0, 1];
nearV(cross(x, y), z, 0, 'x × y = z');
nearV(cross(y, z), x, 0, 'y × z = x');
nearV(cross(z, x), y, 0, 'z × x = y');
nearV(cross(mul(x, -1), y), mul(z, -1), 0, 'un eje dado vuelta');
nearV(cross(mul(x, -1), mul(y, -1)), z, 0, 'dos ejes dados vuelta');
ok('x × y = z; con un eje dado vuelta da −z (espejo), con dos da z (giro)');
const det = (p, q, r) => dot(cross(p, q), r);
const F = unit([0.3, 0.2, -1]);
const brazo = { wr: [0, 1, 0], F, d: unit(sub([0, 1, 0], mul(F, F[1]))), el: [0, 1, 0.27] };
const dos = { arms: { l: brazo, r: brazo } };
const L = M.watchOf(dos, 'l'), R = M.watchOf(dos, 'r');
near(det(L.X, L.Y, L.Z), 1, 1e-12, 'izquierda: x × y = z');
near(det(R.X, R.Y, R.Z), 1, 1e-12, 'derecha: x × y = z');
nearV(R.X, mul(L.X, -1), 1e-12, 'x se da vuelta');
nearV(R.Y, mul(L.Y, -1), 1e-12, 'y se da vuelta');
nearV(R.Z, L.Z, 1e-12, 'z se queda');
nearV(rot(L.X, L.Z, Math.PI), R.X, 1e-12, 'es un giro de 180° alrededor de z');
nearV(rot(L.Y, L.Z, Math.PI), R.Y, 1e-12, 'también y');
near(det(mul(L.X, -1), L.Y, L.Z), -1, 1e-12, 'dar vuelta solo x es un espejo');
nearV(forearmOf('left'), x, 0, 'antebrazo a la izquierda');
nearV(forearmOf('right'), mul(x, -1), 0, 'antebrazo a la derecha');
ok('en la otra mano x e y se dan vuelta y z se queda: un giro de 180° alrededor de z, no un espejo');

// ---------- marcos ----------
console.log('Marcos y coordenadas');
for (const key of Object.keys(M.ANIMS)) {
  for (const side of ['l', 'r']) {
    const A = M.ANIMS[key];
    for (const t of [0, A.dur / 3, A.dur / 2]) {
      const w = M.watchOf(M.build(A.pose(t, side)), side);
      near(len(w.X), 1, 1e-9, 'X de largo 1');
      near(len(w.Y), 1, 1e-9, 'Y de largo 1');
      near(len(w.Z), 1, 1e-9, 'Z de largo 1');
      near(dot(w.X, w.Y), 0, 1e-9, 'X e Y en ángulo recto');
      near(dot(w.X, w.Z), 0, 1e-9, 'X y Z en ángulo recto');
      near(det(w.X, w.Y, w.Z), 1, 1e-9, 'x × y = z');
    }
  }
}
ok(`watchOf da siempre un marco: tres ejes de largo 1, en ángulo recto y con x × y = z (${Object.keys(M.ANIMS).length} animaciones, las dos manos)`);

// la gravedad no se mueve: se mueven los ejes del reloj
const arriba = [0, 0, G], lee = (X, Y, Z) => [dot(arriba, X), dot(arriba, Y), dot(arriba, Z)];
const Rx = (t) => [rot(x, x, t), rot(y, x, t), rot(z, x, t)];
nearV(lee(...Rx(90 * D)), [0, G, 0], 1e-12, 'con su y hacia arriba lee (0, 9.81, 0)');
nearV(lee(...Rx(0)), [0, 0, G], 1e-12, 'plano lee (0, 0, 9.81)');
for (const t of [10, 33, 71]) near(len(lee(...Rx(t * D))), G, 1e-12, 'el largo no cambia');
ok('la misma gravedad se lee (0, 9.81, 0) y (0, 0, 9.81) según cómo esté el reloj, y su largo no cambia');

// ejes unitarios en ángulo recto: cada coordenada es un producto punto
const v = [0.7, -1.2, 2.0];
const cf = [dot(v, L.X), dot(v, L.Y), dot(v, L.Z)];
nearV(add(add(mul(L.X, cf[0]), mul(L.Y, cf[1])), mul(L.Z, cf[2])), v, 1e-12, 'la suma vuelve a dar v');
near(len(cf), len(v), 1e-12, 'el largo no depende del marco');
ok('en un marco cada coordenada es un producto punto, y el largo no cambia');

// ejes torcidos: la sombra ya no sirve y hay que resolver dos ecuaciones
const pa = [1, 0, 0], pb = [Math.cos(55 * D), Math.sin(55 * D), 0], s = dot(pa, pb);
const al = 1.5, be = 1.2, vo = add(mul(pa, al), mul(pb, be));
near(dot(vo, pa), al + be * s, 1e-12, 'v·a = α + β s');
near(dot(vo, pb), al * s + be, 1e-12, 'v·b = α s + β');
near((dot(vo, pa) - dot(vo, pb) * s) / (1 - s * s), al, 1e-12, 'despejar α');
near((dot(vo, pb) - dot(vo, pa) * s) / (1 - s * s), be, 1e-12, 'despejar β');
assert.ok(Math.abs(dot(vo, pa) - al) > 0.5, 'la sombra no es el coeficiente');
ok(`con ejes a 55°: v = 1.5 a + 1.2 b, pero v·a = ${dot(vo, pa).toFixed(2)}; hay que resolver el sistema`);

// cambiar de marco: nueve números, y productos punto para los dos lados
const mulMV = (A, w) => [A[0] * w[0] + A[1] * w[1] + A[2] * w[2], A[3] * w[0] + A[4] * w[1] + A[5] * w[2], A[6] * w[0] + A[7] * w[1] + A[8] * w[2]];   // copia de armfilter.js
const Rm = [L.X[0], L.Y[0], L.Z[0], L.X[1], L.Y[1], L.Z[1], L.X[2], L.Y[2], L.Z[2]];
const enReloj = [1.2, 0.5, 1.0], enMundo = mulMV(Rm, enReloj);
nearV(enMundo, add(add(mul(L.X, 1.2), mul(L.Y, 0.5)), mul(L.Z, 1.0)), 1e-12, 'x de X más y de Y más z de Z');
nearV([dot(enMundo, L.X), dot(enMundo, L.Y), dot(enMundo, L.Z)], enReloj, 1e-12, 'de vuelta al reloj con productos punto');
ok('la matriz por el vector da x de X más y de Y más z de Z; y de vuelta, productos punto con X, Y y Z');

const imu = M.synth('apuntar', 'l', { noise: false });
const W = M.watchOf(M.build(M.ANIMS.apuntar.pose(0, 'l')), 'l');
nearV([imu.grav[0], imu.grav[1], imu.grav[2]], [G * W.X[1], G * W.Y[1], G * W.Z[1]], 1e-3, 'synth: producto punto con los ejes');
ok('synth lee la gravedad así: un producto punto de arriba con cada eje del reloj');

// ---------- el ejercicio: seis caras ----------
const anguloPuntoDelCurso = (p, q) => Math.acos(Math.max(-1, Math.min(1, dot(p, q) / (len(p) * len(q))))) / D;
const anguloAtan2DelCurso = (p, q) => Math.atan2(len(cross(p, q)), dot(p, q)) / D;

function probar({ anguloPunto, anguloAtan2 }, nombre) {
  console.log(`El ángulo entre dos posturas (${nombre})`);
  const caras = [[G, 0, 0], [-G, 0, 0], [0, G, 0], [0, -G, 0], [0, 0, G], [0, 0, -G]];
  const lectura = (cara) => cara.map((n) => 1.003 * n + 0.03 * normal());        // inventadas: un poco de error de escala y ruido
  let peor = 0;
  for (let i = 0; i < 6; i++) {
    for (let j = i + 1; j < 6; j++) {
      const esperado = dot(caras[i], caras[j]) < 0 ? 180 : 90;
      const p = lectura(caras[i]), q = lectura(caras[j]);
      for (const f of [anguloPunto, anguloAtan2]) {
        const r = f(p, q);
        assert.ok(Number.isFinite(r), 'da un número');
        near(r, esperado, 1, `caras ${i} y ${j}`);
        peor = Math.max(peor, Math.abs(r - esperado));
      }
      near(len(p), 1.003 * G, 0.1, 'el largo es casi 9.81');
    }
  }
  ok(`90° entre caras vecinas y 180° entre opuestas (con ruido, el peor error es ${peor.toFixed(2)}°)`);
  near(anguloPunto(caras[4], caras[4]), 0, 1e-6, 'la misma flecha');
  near(anguloAtan2(caras[4], caras[4]), 0, 1e-6, 'la misma flecha');
  for (let i = 0; i < 2000; i++) {
    const w = [normal(), normal(), normal()];
    assert.ok(Number.isFinite(anguloPunto(w, w)), 'acos no se sale de [−1, 1]');
    assert.ok(Number.isFinite(anguloPunto(w, mul(w, -3))), 'tampoco con flechas opuestas');
  }
  ok('una flecha consigo misma da 0°, sin que el redondeo saque a acos de [−1, 1]');
  for (let i = 0; i < 200; i++) {
    const p = [normal(), normal(), normal()], q = [normal(), normal(), normal()];
    near(anguloPunto(p, q), anguloAtan2(p, q), 1e-6, 'las dos cuentas dan lo mismo');
  }
  ok('con 200 pares al azar las dos cuentas dan lo mismo');
}

if (process.argv.includes('--ejercicio')) {
  probar(require(path.join(__dirname, '..', 'docs', 'curso', 'ejercicios', 'cap02.js')), 'tu ejercicio');
} else {
  probar({ anguloPunto: anguloPuntoDelCurso, anguloAtan2: anguloAtan2DelCurso }, 'del curso');
}
console.log('\nTodo pasa.');
