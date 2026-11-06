// Pruebas del capítulo 9 del curso (El cuerpo en 3D): lo que el capítulo afirma sobre server/web/mocapmath.js y
// server/web/armfilter.js, comprobado con números. La prueba de la cinemática inversa corre también contra tu ejercicio.
// `ik` no se exporta de mocapmath.js: aquí hay una copia, comparada contra `build`, que sí la usa.
//   node tools/test_cuerpo.js              # la cuenta del curso
//   node tools/test_cuerpo.js --ejercicio  # tu cinemática inversa, en docs/curso/ejercicios/cap09.js
'use strict';
const path = require('path');
const assert = require('assert');
const raiz = path.join(__dirname, '..');
const M = require(path.join(raiz, 'server', 'web', 'mocapmath.js'));
const { ArmFilter, feasible, defaultPrior, DEFAULTS } = require(path.join(raiz, 'server', 'web', 'armfilter.js'));
const B = require(path.join(__dirname, 'test_armfilter.js'));      // el brazo de verdad conocida de esa prueba
const { add, sub, mul, dot, cross, len, unit, rot } = M.vec;

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a.toFixed(5)} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
const GRADO = Math.PI / 180;
const dist = (a, b) => len(sub(a, b));
const v3 = (a, k) => [a[3 * k], a[3 * k + 1], a[3 * k + 2]];
const mediana = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
const media = (a) => a.reduce((s, x) => s + x, 0) / a.length;
const tamano = (a) => { const m = media(a); return Math.sqrt(media(a.map((x) => (x - m) ** 2))); };
const rms = (a) => Math.sqrt(media(a.map((x) => x * x)));
const anguloEntre = (a, b) => Math.acos(Math.max(-1, Math.min(1, dot(unit(a), unit(b))))) / GRADO;

// ---------- la cinemática inversa, copia de `ik` en mocapmath.js ----------
function ikDelCurso(a, t, l1, l2, polo) {
  const v = sub(t, a);
  let d = len(v);
  const dir = d > 1e-9 ? mul(v, 1 / d) : [0, -1, 0];
  d = Math.min(Math.max(d, Math.abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4);
  const x = (l1 * l1 - l2 * l2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, l1 * l1 - x * x));
  const pv = sub(polo, a), pd = unit(sub(pv, mul(dir, dot(pv, dir))));
  return { codo: add(add(a, mul(dir, x)), mul(pd, h)), muneca: add(a, mul(dir, d)) };
}

// una pose quieta y derecha, con un brazo a pedido
const poseCon = (brazo) => ({ pelvis: [0, 1, 0], H: 0, legs: { l: { flex: 0, knee: 0 }, r: { flex: 0, knee: 0 } }, arms: { l: brazo, r: { fk: { flex: 0, elbow: 0 } } } });

// el filtro del codo sobre el brazo de verdad conocida de test_armfilter.js; mira() recibe cada paso
function correr({ seconds = 40, still = 15, speed = 2.5, seed = 3, opts = {}, mira = null } = {}) {
  const dt = 0.01, steps = Math.round(seconds / dt), P = [], ruido = new ArmFilter({ seed: 99 });
  for (let k = -1; k <= steps + 1; k++) P.push(B.pose(k * dt, still, speed));
  const f = new ArmFilter(Object.assign({ seed }, opts)), filas = [];
  let remuestreos = 0;
  const propio = f._resample.bind(f);
  f._resample = () => { remuestreos++; propio(); };
  for (let k = 1; k <= steps; k++) {
    const pv = P[k - 1], c = P[k], nx = P[k + 1];
    const acc = mul(add(sub(nx.p, mul(c.p, 2)), pv.p), 1 / (dt * dt));
    const a = add(add(B.mulTV(c.R, acc), [0.08 * ruido.randn(), 0.08 * ruido.randn(), 0.08 * ruido.randn()]), [0.05, -0.03, 0.04]);
    const w = add(mul(B.logR(B.mulTM(pv.R, nx.R)), 1 / (2 * dt)), [0.15 * GRADO * ruido.randn(), 0.15 * GRADO * ruido.randn(), 0.15 * GRADO * ruido.randn()]);
    const e = f.step(c.R, w, a, dt), t = k * dt;
    const codoF = add(DEFAULTS.shoulder, mul(e.u, f.o.Lu)), codoR = add(DEFAULTS.shoulder, mul(defaultPrior(c.f), f.o.Lu));
    const fila = { t, spread: e.spread, neff: e.neff, quieto: !!e.still, errF: dist(codoF, c.e), errR: dist(codoR, c.e), haciaReposo: dist(codoF, codoR), accel: e.accel, remuestreos };
    filas.push(fila);
    if (mira) mira(f, fila, c, k);
  }
  return { filas, remuestreos };
}

module.exports = { correr, ikDelCurso, poseCon, flojo };
if (require.main !== module) return;

// ---------- el esqueleto ----------
console.log('El esqueleto');
const ANIMS = Object.keys(M.ANIMS);
for (const key of ANIMS) {
  for (let i = 0; i < 200; i++) {
    const t = i / 200 * M.ANIMS[key].dur, b = M.build(M.ANIMS[key].pose(t, 'l'));
    for (const s of ['l', 'r']) { near(dist(b.arms[s].sh, b.arms[s].el), 0.29, 1e-9, `${key}: el brazo mide 0.29`); near(dist(b.arms[s].el, b.arms[s].wr), 0.27, 1e-3, `${key}: el antebrazo mide 0.27`); }
  }
}
ok('en las tres animaciones el brazo mide 0.29 m y el antebrazo 0.27 m en todo momento');
assert.strictEqual(DEFAULTS.Lu, 0.30); assert.strictEqual(DEFAULTS.Lf, 0.25); assert.strictEqual(DEFAULTS.Lw, 0.22);
ok('el filtro del codo usa otras medidas: 0.30 m, 0.25 m, y el reloj a 0.22 m del codo');

// ---------- la cinemática directa ----------
console.log('La cinemática directa');
const recto = M.build(poseCon({ fk: { flex: 90, elbow: 0 } })).arms.l;
near(dist(recto.wr, add(recto.sh, [0, 0, -0.56])), 0, 1e-9, 'flex 90 y codo recto: al frente');
const doblado = M.build(poseCon({ fk: { flex: 0, elbow: 90 } })).arms.l;
near(dist(doblado.el, add(doblado.sh, [0, -0.29, 0])), 0, 1e-9, 'el codo cuelga');
near(dist(doblado.wr, add(doblado.el, [0, 0, -0.27])), 0, 1e-9, 'el antebrazo al frente');
ok('flex 90° lleva el brazo al frente; con el brazo colgando, 90° de codo llevan el antebrazo al frente');
const b1 = M.build(poseCon({ fk: { flex: 60, abd: 40, elbow: 50 } })).arms.l;
const U = rot(rot([0, -1, 0], [1, 0, 0], 60 * GRADO), [0, 0, -1], 40 * GRADO), Ualreves = rot(rot([0, -1, 0], [0, 0, -1], 40 * GRADO), [1, 0, 0], 60 * GRADO);
near(dist(b1.el, add(b1.sh, mul(U, 0.29))), 0, 1e-9, 'codo = hombro + L₁·u');
near(dist(b1.wr, add(b1.el, mul(b1.F, 0.27))), 0, 1e-9, 'muñeca = codo + L₂·f');
assert.ok(dist(U, Ualreves) > 0.1, 'el orden importa');
ok(`codo = hombro + L₁·u y muñeca = codo + L₂·f; cambiar el orden de los giros mueve el codo ${(100 * 0.29 * dist(U, Ualreves)).toFixed(1)} cm`);

// ---------- las trayectorias ----------
console.log('Las trayectorias');
const CAM = M.ANIMS.caminar, paso = CAM.dur / 8;
near(CAM.pose(0.3).arms.l.fk.flex, CAM.pose(0.3 + paso).arms.l.fk.flex, 1e-9, 'el brazo se repite cada paso');
near(CAM.pose(0.3).legs.l.flex, CAM.pose(0.3 + paso).legs.l.flex, 1e-9, 'la pierna se repite');
near(CAM.pose(paso / 4).arms.l.fk.flex, -CAM.pose(paso / 4).arms.r.fk.flex, 1e-9, 'los brazos van opuestos');
near(CAM.dur, 2 * Math.PI * 1.4, 1e-9, 'una vuelta a 1 m/s en un círculo de 1.4 m');
ok(`caminar: una vuelta de ${CAM.dur.toFixed(2)} s, ocho ciclos de ${paso.toFixed(2)} s; cada brazo es 20°·sen de la fase y van opuestos`);
const AP = M.ANIMS.apuntar, ap = (t) => AP.path(t).p;
near(dist(ap(1.2), [-0.55, 1.35 + 0.28, -2.5]), 0, 1e-9, 'el primer ícono');
const rapidez = (t) => dist(ap(t + 1e-3), ap(t - 1e-3)) / 2e-3;
near(rapidez(0.6 + 1e-3), 0, 0.02, 'arranca sin golpe'); near(rapidez(1.2 - 1e-3), 0, 0.02, 'llega sin golpe');
for (let u = 6; u < 9; u += 0.1) near(dist(ap(u), [0, 1.35 + 0.2, -2.5]), 0.2, 1e-9, 'el círculo');
ok('apuntar: la curva suave llega y sale de cada ícono sin golpe, y el círculo tiene 20 cm de radio');

// ---------- la ley de los cosenos ----------
console.log('La ley de los cosenos');
const azar = new ArmFilter({ seed: 5 }), u01 = () => azar.rand();
for (let i = 0; i < 1000; i++) {
  const A = [u01(), u01(), 0], Bv = [u01(), u01(), 0], C = [u01(), u01(), 0], a = dist(C, Bv), b = dist(C, A), c = dist(A, Bv);
  const ang = anguloEntre(sub(A, C), sub(Bv, C)) * GRADO;
  near(c * c, a * a + b * b - 2 * a * b * Math.cos(ang), 1e-9, 'c² = a² + b² − 2ab cos C');
  near(Math.acos((a * a + b * b - c * c) / (2 * a * b)), ang, 1e-6, 'con los lados sale el ángulo');
}
ok('c² = a² + b² − 2ab cos C en mil triángulos, y con los tres lados sale el ángulo');
near(3 ** 2 + 4 ** 2 - 2 * 3 * 4 * Math.cos(90 * GRADO), 25, 1e-9, 'a 90° es Pitágoras');
ok('con C = 90° el coseno es cero y queda Pitágoras');

// ---------- la cinemática inversa ----------
console.log('La cinemática inversa');
function compararConBuild() {
  const off = [0.3, -0.5, -0.2];
  for (let i = 0; i < 200; i++) {
    const t = [u01() * 1.2 - 0.6, 0.8 + u01(), u01() * 1.2 - 0.6];
    const b = M.build(poseCon({ ik: { target: () => t, pole: { off } } })).arms.l, sh = b.sh;
    const polo = add(add(add(sh, [0, 0, -off[0]]), [0, off[1], 0]), [off[2], 0, 0]), r = ikDelCurso(sh, t, 0.29, 0.27, polo);
    near(dist(r.codo, b.el), 0, 1e-9, 'la copia da el mismo codo que build');
    near(dist(r.muneca, b.wr), 0, 1e-9, 'la copia da la misma muñeca que build');
  }
}
compararConBuild();
ok('la copia de `ik` da el mismo codo y la misma muñeca que `build`, en 200 objetivos');
const hom = [0, 1.4, 0], obj = [0.2, 1.2, -0.35], eje = unit(sub(obj, hom));
const codos = Array.from({ length: 12 }, (_, i) => ikDelCurso(hom, obj, 0.29, 0.27, add(hom, rot(cross(eje, [1, 0, 0]), eje, i * 30 * GRADO))).codo);
const centro = mul(codos.reduce((s, c) => add(s, c), [0, 0, 0]), 1 / 12), radio = dist(codos[0], centro);
codos.forEach((c) => { near(dist(c, hom), 0.29, 1e-9, 'siempre a L₁'); near(dist(c, obj), 0.27, 1e-9, 'siempre a L₂'); near(dist(c, centro), radio, 1e-9, 'en un círculo'); near(dot(sub(c, centro), eje), 0, 1e-9, 'perpendicular a la recta'); });
near(Math.acos((0.29 ** 2 + 0.27 ** 2 - 0.16) / (2 * 0.29 * 0.27)) / GRADO, 91, 0.5, 'el codo abre 91°');
ok(`hay infinitas maneras: los codos posibles forman un círculo de ${(100 * radio).toFixed(1)} cm de radio alrededor de la recta hombro-muñeca`);

function probarIk(ik, nombre) {
  console.log(`Cinemática inversa (${nombre})`);
  const az = new ArmFilter({ seed: 11 }), u = () => az.rand() * 2 - 1;
  let alcanza = 0, fuera = 0;
  for (let i = 0; i < 1000; i++) {
    const h = [u(), 1 + u(), u()], l1 = 0.2 + 0.3 * az.rand(), l2 = 0.2 + 0.3 * az.rand();
    const t = add(h, mul(unit([u(), u(), u()]), 1.2 * (l1 + l2) * az.rand())), polo = add(h, [u(), u(), u()]);
    const r = ik(h, t, l1, l2, polo);
    assert.ok(r && r.codo && r.muneca, 'devuelve { codo, muneca }');
    near(dist(r.codo, h), l1, 1e-6, 'el codo queda a l1 del hombro');
    near(dist(r.codo, r.muneca), l2, 1e-6, 'la muñeca queda a l2 del codo');
    const d = dist(h, t);
    if (d > Math.abs(l1 - l2) + 1e-3 && d < l1 + l2 - 1e-3) { alcanza++; near(dist(r.muneca, t), 0, 1e-6, 'llega al objetivo'); } else {
      fuera++;
      assert.ok(dist(r.muneca, t) < Math.abs(d - (d > l1 ? l1 + l2 : Math.abs(l1 - l2))) + 1e-3, 'fuera de alcance llega hasta donde puede');
    }
  }
  ok(`mil objetivos: el codo a l1 y la muñeca a l2; llega a los ${alcanza} que están a su alcance, y a los otros ${fuera} se acerca lo que puede`);
  for (let i = 0; i < 100; i++) {
    const t = [u() * 0.6, 1.4 + u() * 0.5, u() * 0.6], off = [0.3, -0.5, -0.2];
    const b = M.build(poseCon({ ik: { target: () => t, pole: { off } } })).arms.l, polo = add(add(add(b.sh, [0, 0, -off[0]]), [0, off[1], 0]), [off[2], 0, 0]);
    const r = ik(b.sh, t, 0.29, 0.27, polo);
    near(dist(r.codo, b.el), 0, 1e-6, 'da lo mismo que build');
    near(dist(r.muneca, b.wr), 0, 1e-6, 'da lo mismo que build');
  }
  ok('da el mismo codo que `build` de mocapmath.js');
}
if (process.argv.includes('--ejercicio')) {
  probarIk(require(path.join(raiz, 'docs', 'curso', 'ejercicios', 'cap09.js')).ik, 'tu ejercicio');
  console.log('\nTodo pasa.');
  process.exit(0);
}
probarIk(ikDelCurso, 'del curso');

// ---------- fabricar ruido ----------
console.log('Fabricar ruido');
const r1 = new ArmFilter({ seed: 7 }), muestras = Array.from({ length: 100000 }, () => r1.randn());
near(media(muestras), 0, 0.02, 'centro en cero'); near(tamano(muestras), 1, 0.02, 'tamaño típico 1');
const dentro = (k) => muestras.filter((x) => Math.abs(x) < k).length / muestras.length;
near(dentro(1), 0.683, 0.01, 'dentro de 1σ'); near(dentro(2), 0.954, 0.01, 'dentro de 2σ');
ok(`Box–Muller: media ${media(muestras).toFixed(3)}, tamaño típico ${tamano(muestras).toFixed(3)}, ${(100 * dentro(1)).toFixed(1)} % a menos de 1σ y ${(100 * dentro(2)).toFixed(1)} % a menos de 2σ`);
const serie = (s) => { const f = new ArmFilter({ seed: s }); return Array.from({ length: 5 }, () => f.randn()); };
assert.deepStrictEqual(serie(7), serie(7), 'la misma semilla, los mismos números');
assert.notDeepStrictEqual(serie(7), serie(8), 'otra semilla, otros números');
const s1 = M.synth('tablet', 'l', { noise: true, seed: 3 }), s2 = M.synth('tablet', 'l', { noise: true, seed: 3 }), s3 = M.synth('tablet', 'l', { noise: true, seed: 4 });
assert.deepStrictEqual(Array.from(s1.gyr.slice(0, 30)), Array.from(s2.gyr.slice(0, 30)));
assert.notDeepStrictEqual(Array.from(s1.gyr.slice(0, 30)), Array.from(s3.gyr.slice(0, 30)));
ok('la misma semilla repite la misma lectura de `synth`, número por número; otra semilla da otra');

// ---------- lo que leería el reloj ----------
console.log('Lo que leería el reloj');
const cam = M.synth('caminar', 'l', { noise: false });
let gravMal = 0;
const mundo = [0, 0, 0], enElMundo = (k) => {
  const X = v3(cam.truth.X, k), Z = v3(cam.truth.Z, k), Y = cross(Z, X), a = v3(cam.acc, k);
  return add(add(mul(X, a[0]), mul(Y, a[1])), mul(Z, a[2]));
};
for (let k = 0; k < cam.n; k++) { gravMal = Math.max(gravMal, Math.abs(len(v3(cam.grav, k)) - 9.81)); const w = enElMundo(k); for (let i = 0; i < 3; i++) mundo[i] += w[i] / cam.n; }
near(gravMal, 0, 1e-3, 'la gravedad mide 9.81');
near(mundo[1], 9.81, 0.02, 'el acelerómetro promedia 9.81 hacia arriba'); near(mundo[0], 0, 0.02, 'nada de lado'); near(mundo[2], 0, 0.02, 'nada de lado');
ok(`caminando una vuelta, el acelerómetro en el mundo promedia (${mundo.map((c) => c.toFixed(2))}): 9.81 hacia arriba, porque lo demás ida y vuelta se cancela`);
const conRuido = M.synth('caminar', 'l', { noise: true }), dif = (i) => Array.from({ length: cam.n }, (_, k) => conRuido.gyr[3 * k + i] - cam.gyr[3 * k + i]);
[0.6, -0.4, 0.3].forEach((b, i) => { near(media(dif(i)), b, 0.02, 'el sesgo'); near(tamano(dif(i)), 0.3, 0.02, 'el ruido'); });
ok('encima van un sesgo de (0.6, −0.4, 0.3) °/s y ruido de 0.3 °/s en el giroscopio');
// giro de verdad conocido: el reloj de la animación integrado con su propio giroscopio vuelve a su orientación
const sinResorte = M.reconstruct(cam, 'l', { kp: 0, frame0: [v3(cam.truth.X, 0), cross(v3(cam.truth.Z, 0), v3(cam.truth.X, 0)), v3(cam.truth.Z, 0)], psi0: 0 });
const errF = (rec, imu, k) => anguloEntre(v3(rec.F, k), v3(imu.truth.F, k));
const peorSinResorte = Math.max(...Array.from({ length: cam.n }, (_, k) => errF(sinResorte, cam, k)));
assert.ok(peorSinResorte < 3, `sumar el ω fabricado vuelve a la animación (${peorSinResorte})`);
ok(`sumando solo el ω fabricado, sin gravedad, el antebrazo no se aparta más de ${peorSinResorte.toFixed(2)}° en toda la vuelta`);

// ---------- probar contra la verdad ----------
console.log('Probar contra la verdad');
const alineado = (imu) => { const X = v3(imu.truth.X, 0), Z = v3(imu.truth.Z, 0); return { frame0: [X, cross(Z, X), Z], psi0: M.headingOf(v3(imu.truth.F, 0)) }; };
const errores = (imu, rec) => Array.from({ length: imu.n }, (_, k) => errF(rec, imu, k));
const ap1 = M.synth('apuntar', 'l', { noise: false }), e1 = errores(ap1, M.reconstruct(ap1, 'l', alineado(ap1)));
assert.ok(mediana(e1) < 1.5, 'sin ruido cae encima');
// un reloj flojo: se mece ±8° sobre la muñeca, alrededor de su z, una vez por segundo; la "verdad" sigue siendo el brazo
function flojo(imu, amp, hz) {
  const out = { ...imu, gyr: imu.gyr.slice(), grav: imu.grav.slice() };
  for (let k = 0; k < imu.n; k++) {
    const t = k / imu.hz, a = amp * GRADO * Math.sin(2 * Math.PI * hz * t), da = amp * 2 * Math.PI * hz * Math.cos(2 * Math.PI * hz * t);
    const g = rot(v3(imu.grav, k), [0, 0, 1], -a), w = rot(v3(imu.gyr, k), [0, 0, 1], -a);
    for (let i = 0; i < 3; i++) { out.grav[3 * k + i] = g[i]; out.gyr[3 * k + i] = w[i]; }
    out.gyr[3 * k + 2] += da;
  }
  return out;
}
const e2 = errores(ap1, M.reconstruct(flojo(ap1, 8, 1), 'l', alineado(ap1)));
assert.ok(Math.max(...e2) > 6 && mediana(e2) > 3 * mediana(e1), 'con el reloj flojo ya no cae encima');
ok(`apuntar: con el reloj pegado, ${mediana(e1).toFixed(2)}° de mediana; con el reloj meciéndose ±8°, ${mediana(e2).toFixed(1)}° y hasta ${Math.max(...e2).toFixed(1)}°. Eso la prueba normal no lo ve`);

const camS = M.synth('caminar', 'l', { noise: true });
const [c1, c2, c3] = [errores(cam, M.reconstruct(cam, 'l', alineado(cam))), errores(cam, M.reconstruct(camS, 'l', alineado(cam))), errores(cam, M.reconstruct(flojo(cam, 8, 1), 'l', alineado(cam)))];
assert.ok(mediana(c1) < 1 && mediana(c2) < 1.5 && mediana(c3) > 4, 'caminando');
ok(`caminar: ${mediana(c1).toFixed(1)}° sin ruido, ${mediana(c2).toFixed(1)}° con ruido, ${mediana(c3).toFixed(1)}° (hasta ${Math.max(...c3).toFixed(1)}°) con el reloj flojo`);

// ---------- la aceleración de un punto que gira ----------
console.log('La aceleración de un punto que gira');
const w0 = 3.5, L = 0.25;
near(w0 * w0 * L, 3.06, 0.01, 'la centrípeta');
ok(`a 200 °/s (${(200 * GRADO).toFixed(2)} rad/s), un punto a 25 cm siente ${((200 * GRADO) ** 2 * L).toFixed(2)} m/s² hacia el eje`);
{
  const h = 1e-4, eje3 = unit([1, 2, 2]), f0 = unit([0.5, -0.2, 0.7]), th = (t) => 1.2 * t + 0.8 * t * t;     // gira con aceleración, ω = 1.2 + 1.6t
  const fp = (t) => rot(f0, eje3, th(t)), t0 = 0.7;
  const dd = mul(add(sub(fp(t0 + h), mul(fp(t0), 2)), fp(t0 - h)), 1 / (h * h));
  const om = mul(eje3, 1.2 + 1.6 * t0), al = mul(eje3, 1.6), f = fp(t0), tang = cross(al, f), cent = cross(om, cross(om, f));
  near(dist(dd, add(tang, cent)), 0, 1e-4, 'f̈ = α × f + ω × (ω × f)');
  near(dot(tang, cent), 0, 1e-9, 'las dos partes son perpendiculares');
  near(dot(cent, sub(f, mul(eje3, dot(f, eje3)))) < 0 ? 1 : 0, 1, 0, 'la centrípeta apunta al eje');
  ok('α × f + ω × (ω × f) da la segunda diferencia de un punto que gira; la segunda parte apunta al eje y la primera es perpendicular');
}
{
  const dt = 1e-3, Lw = DEFAULTS.Lw, Lu = DEFAULTS.Lu, ps = [0.5, 1.3, 2.1, 3.3].map((t) => [B.pose(t - dt, 0, 2.5), B.pose(t, 0, 2.5), B.pose(t + dt, 0, 2.5)]);
  for (const [a, b, c] of ps) {
    const seg = (x, y, z) => mul(add(sub(z, mul(y, 2)), x), 1 / (dt * dt));
    const pp = seg(a.p, b.p, c.p), ff = seg(a.f, b.f, c.f), ee = seg(a.e, b.e, c.e);
    near(dist(ee, sub(pp, mul(ff, Lw))), 0, 1e-6, 'la aceleración del codo sin ver el codo');
    const ve = mul(sub(c.e, a.e), 1 / (2 * dt));
    near(dot(ee, b.u), -dot(ve, ve) / Lu, 2e-3, 'en la esfera, la parte radial es la centrípeta');
  }
  ok('la aceleración del codo sale de la del reloj: ë = p̈ − L_w·f̈; y su parte radial es −|ė|²/L_u');
}

// ---------- límites del cuerpo ----------
console.log('Límites del cuerpo');
const o = DEFAULTS, N0 = [1, 0, 0];
near(Math.acos(o.cosMaxFlex) / GRADO, 150, 1e-9, 'el límite es 150°');
const brazoAbajo = [0, -1, 0], doblarA = (g) => rot(brazoAbajo, [-1, 0, 0], g * GRADO);
assert.ok(feasible(brazoAbajo, doblarA(145), N0, o), 'a 145° se puede');
assert.ok(!feasible(brazoAbajo, doblarA(155), N0, o), 'a 155° no');
ok('el codo se dobla hasta 150°: a 145° se puede y a 155° no');
assert.ok(feasible([0, -1, 0], [0, 0, 1], [1, 0, 0], o), 'la pantalla del lado de la bisagra');
assert.ok(!feasible([0, -1, 0], [0, 0, 1], [-1, 0, 0], o), 'la pantalla al revés');
assert.ok(!feasible([-1, 0, 0], [0, 0, 1], [1, 0, 0], o), 'dentro del pecho');
assert.ok(!feasible([0, -0.3, -0.95], [0, -1, 0], [1, 0, 0], o), 'demasiado atrás');
ok('tampoco: la pantalla del reloj del lado contrario a la bisagra, el codo dentro del pecho o el brazo muy atrás');
assert.strictEqual(o.infeasibleWeight, 0.02);
ok('lo imposible no se borra: su peso se multiplica por 0.02');

// ---------- verosimilitud ----------
console.log('Verosimilitud');
[[1, 0.607], [2, 0.135], [3, 0.011]].forEach(([k, v]) => near(Math.exp(-k * k / 2), v, 0.001, `r = ${k}σ`));
ok('exp(−r²/2σ²) vale 0.607 con r = σ, 0.135 con r = 2σ y 0.011 con r = 3σ');
{
  // dos partículas con pesos iguales y velocidad cero: lo que queda es exactamente la cuenta del capítulo
  const f = new ArmFilter({ n: 2, seed: 1 }), R = [1, 0, 0, 0, 1, 0, 0, 0, 1], u1 = unit([0.3, -1, 0.3]), u2 = unit([0.6, -1, 0.2]);
  f.ready = true; f.omS = [0, 0, 0];
  f.U.set(u1, 0); f.U.set(u2, 3); f.V.fill(0); f.W.fill(0.5);
  const a = [0.4, 2.0, 0.5];
  f.step(R, [0, 0, 0], a, 0.01);
  const sig = o.sigmaR + o.sigmaRel * len(a), p = (u) => Math.exp(-(dot(a, u) ** 2) / (2 * sig * sig));
  near(f.W[0] / f.W[1], p(u1) / p(u2), 1e-9, 'los pesos son los de exp(−r²/2σ²)');
  ok(`dos hipótesis, σ = ${sig.toFixed(2)} m/s²: el cociente de pesos que deja \`step\` es ${(f.W[0] / f.W[1]).toFixed(4)}, el de la fórmula`);
}

// ---------- el filtro de partículas ----------
console.log('El filtro de partículas');
for (const speed of [1, 2.5, 4]) {
  const { filas } = correr({ seconds: 20, still: 15, speed });
  const mov = filas.filter((x) => x.t > 3 && x.t < 15), e = rms(mov.map((x) => x.errF)), r = rms(mov.map((x) => x.errR));
  assert.ok(e < r, `velocidad ${speed}`);
  ok(`moviendo el brazo (velocidad ${speed}): el filtro se equivoca ${(100 * e).toFixed(1)} cm y la regla de reposo ${(100 * r).toFixed(1)} cm`);
}
{
  const uno = correr({ seconds: 15, still: 15, opts: { n: 1 } }).filas.filter((x) => x.t > 3), muchos = correr({ seconds: 15, still: 15 }).filas.filter((x) => x.t > 3);
  const [e1p, e400] = [rms(uno.map((x) => x.errF)), rms(muchos.map((x) => x.errF))];
  assert.ok(e400 < e1p, 'cuatrocientas ganan a una');
  ok(`una sola hipótesis se equivoca ${(100 * e1p).toFixed(1)} cm; 400, ${(100 * e400).toFixed(1)} cm`);
}
const { filas, remuestreos } = correr({ seconds: 40, still: 15 });
const nube = (a, b) => media(filas.filter((x) => x.t >= a && x.t < b).map((x) => x.spread));
const final = filas.filter((x) => x.t > 38), [nubeMov, nubeFin] = [nube(3, 15), nube(38, 40)], inicio = filas[0].spread;
assert.ok(nubeMov < inicio, 'moverse aprieta la nube desde el comienzo');
assert.ok(nubeFin < nubeMov / 2, 'quieto, la nube no se abre: se junta en el reposo');
near(media(final.map((x) => x.haciaReposo)), 0, 0.03, 'quieto vuelve a la postura de reposo');
assert.ok(media(final.map((x) => x.errF)) > 3 * nubeFin, 'y esa nube chica no es certeza');
ok(`la nube: ${(100 * inicio).toFixed(1)} cm al empezar, ${(100 * nubeMov).toFixed(1)} cm moviendo el brazo, ${(100 * nubeFin).toFixed(1)} cm tras 25 s quieto`);
ok(`quieto, el estimado queda a ${(100 * media(final.map((x) => x.haciaReposo))).toFixed(1)} cm del reposo, y el error de verdad es ${(100 * media(final.map((x) => x.errF))).toFixed(1)} cm: la nube chica no es certeza`);

// ---------- tamaño efectivo y remuestreo ----------
console.log('Tamaño efectivo y remuestreo');
const nef = (w) => 1 / w.reduce((s, x) => s + x * x, 0);
near(nef(new Array(400).fill(1 / 400)), 400, 1e-9, 'pesos iguales'); near(nef([1, 0, 0]), 1, 1e-12, 'uno solo'); near(nef([0.5, 0.5, 0, 0]), 2, 1e-12, 'dos');
ok('N_ef = 1/Σw² vale 400 con pesos iguales, 2 con dos que mandan y 1 con uno solo');
assert.strictEqual(o.resampleFrac, 0.5);
assert.ok(remuestreos > 20, 'remuestrea mientras el brazo se mueve');
{
  // se marca cada partícula con la dirección de su índice en un círculo, para saber de quién es clon cada una
  const n = 400, f = new ArmFilter({ n, seed: 4, roughen: 0 }), pesos = Array.from({ length: n }, (_, i) => Math.exp(-(((i - 120) / 25) ** 2)));
  const s = pesos.reduce((a, b) => a + b, 0), w = pesos.map((x) => x / s), marca = (i) => [Math.cos(i * 2 * Math.PI / n), Math.sin(i * 2 * Math.PI / n), 0];
  for (let i = 0; i < n; i++) { f.U.set(marca(i), 3 * i); f.V.fill(0, 3 * i, 3 * i + 3); f.W[i] = w[i]; }
  f._resample();
  const clones = new Array(n).fill(0);
  for (let m = 0; m < n; m++) { const a = Math.atan2(f.U[3 * m + 1], f.U[3 * m]); clones[(Math.round(a * n / (2 * Math.PI)) + n) % n]++; }
  clones.forEach((c, i) => assert.ok(Math.abs(c - n * w[i]) < 1 + 1e-9, `la partícula ${i} tiene ${c} clones y su peso pide ${(n * w[i]).toFixed(2)}`));
  near(f.W[0], 1 / n, 1e-12, 'después pesan lo mismo');
  ok(`remuestreo sistemático: cada partícula queda con n·w clones, redondeado a uno de los dos enteros vecinos; ${clones.filter((c) => c === 0).length} de ${n} se olvidan y todas vuelven a pesar 1/${n}`);
}
const hasta16 = filas.find((x) => x.t >= 16).remuestreos;
assert.ok(hasta16 > 0.9 * remuestreos, 'casi todos con el brazo en movimiento');
ok(`en 40 s con el brazo moviéndose 15 s se remuestreó ${remuestreos} veces (cuando N_ef < 200), ${hasta16} de ellas antes de los 16 s`);
console.log('\nTodo pasa.');
