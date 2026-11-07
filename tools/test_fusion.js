// Pruebas del capítulo 8 del curso (server/web/fusionmath.js): lo que el capítulo afirma, comprobado con
// números. Las mismas pruebas del filtro complementario corren contra tu solución del ejercicio.
//   node tools/test_fusion.js              # la cuenta del curso
//   node tools/test_fusion.js --ejercicio  # tu filtro, en docs/curso/ejercicios/cap08.js
'use strict';
const path = require('path');
const assert = require('assert');
const web = path.join(__dirname, '..', 'server', 'web');
const F = require(path.join(web, 'fusionmath.js'));
const M = require(path.join(web, 'mocapmath.js'));

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a.toFixed(4)} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);

// ---------- el filtro complementario: lo que tiene que cumplir cualquiera que lo escriba ----------
function filtro(complementario, nombre) {
  console.log(`Filtro complementario (${nombre})`);
  const hz = 100, n = 6000;
  const cte = (v) => new Float64Array(n).fill(v);
  const run = (giro, med, k, th0) => Array.from(complementario(giro, med, hz, k, th0));

  // 1. sin resorte (k = 0) es integrar: 10 °/s durante 60 s son 600°, sin importar lo que diga la medida
  let est = run(cte(10), cte(0), 0, 0);
  assert.strictEqual(est.length, n, 'devuelve una estimación por muestra');
  // (da igual si out[i] es la estimación antes o después de usar la muestra i: un paso de diferencia)
  near(est[0], 0, 10 / hz + 1e-9, 'arranca donde le dicen');
  near(run(cte(0), cte(3), 0, 7)[0], 7, 1e-9, 'arranca en th0, no en 0 ni en la primera medida');
  near(run(cte(0), cte(3), 0, 7)[n - 1], 7, 1e-9, 'con k = 0 y sin giro se queda en th0');
  near(est[n - 1], 600, 10 / hz + 1e-6, 'k = 0: 10 °/s durante 60 s son 600°');
  ok('con k = 0 integra el giroscopio');

  // 2. la mano quieta en 20°, un giroscopio con sesgo b: el error deja de crecer en b/k
  for (const [b, k] of [[0.5, 0.5], [0.5, 2], [2, 1], [-1, 4]]) {
    est = run(cte(b), cte(20), k, 20);
    const e30 = est[30 * hz] - 20, e60 = est[n - 1] - 20;
    // el orden de avanzar y tirar, o un resorte exacto, corren b/k en un k·Δt: los dos están bien
    near(e60, b / k, Math.abs(b / k) * (k / hz + 0.01) + 1e-3, `b = ${b} °/s, k = ${k}/s: el error se queda en b/k`);
    near(e30, e60, 0.01 * Math.abs(b / k) + 1e-3, `b = ${b}, k = ${k}: a los 30 s y a los 60 s es el mismo`);
  }
  ok('con sesgo b el error se queda quieto en b/k');

  // 3. resorte muy rígido: sigue a la medida, aunque el giroscopio diga otra cosa
  est = run(cte(0), cte(5), 50, 0);
  near(est[n - 1], 5, 1e-3, 'k = 50/s: termina en la medida');
  ok('con k grande sigue a la medida');

  // 4. lo de verdad: la muñeca simulada; con k = 1 el error rms es más chico que el de cada testigo solo
  const s = F.inclinacion({});
  const ev = (xs) => F.errores(Float64Array.from(xs), s.verdad, 500);
  const fus = ev(run(s.giro, s.acel, 1, s.verdad[0])).rms;
  const gir = ev(run(s.giro, s.acel, 0, s.verdad[0])).rms, ace = ev(s.acel).rms;
  assert.ok(fus < gir / 5 && fus < ace / 5, `k = 1: la fusión (${fus.toFixed(2)}°) le gana por 5× al giroscopio (${gir.toFixed(2)}°) y a la gravedad (${ace.toFixed(2)}°)`);
  ok(`la fusión (${fus.toFixed(2)}°) le gana al giroscopio solo (${gir.toFixed(1)}°) y al acelerómetro solo (${ace.toFixed(1)}°)`);
}

if (process.argv.includes('--ejercicio')) {
  const archivo = path.join(__dirname, '..', 'docs', 'curso', 'ejercicios', 'cap08.js');
  try {
    filtro(require(archivo).complementario, 'tu solución');
  } catch (e) {
    console.error(`\n  ✗ ${e.message}\n\n  Edita ${path.relative(process.cwd(), archivo)} y vuelve a correr esto.`);
    process.exit(1);
  }
  console.log('\n¡Pasa! Tu filtro hace lo mismo que el del curso.');
  process.exit(0);
}

filtro(F.complementario, 'el del curso');

// ---------- lo que el capítulo afirma ----------
console.log('Lo que dice el capítulo');
const s = F.inclinacion({});
const g = F.soloGiro(s.giro, s.hz, s.verdad[0]);
near(g[s.n - 1] - s.verdad[s.n - 1], s.b * s.dur, 1.5, 'el giroscopio solo se va b·t');
ok(`giroscopio solo: ${(g[s.n - 1] - s.verdad[s.n - 1]).toFixed(1)}° a los 60 s (b·t = ${(s.b * s.dur).toFixed(0)}°)`);
const acel = F.errores(s.acel, s.verdad, 0);
assert.ok(Math.abs(acel.medio) < 0.5 && acel.max > 20, 'el acelerómetro no se desvía en promedio, pero salta con cada sacudida');
ok(`acelerómetro solo: promedio ${acel.medio.toFixed(2)}°, pero salta hasta ${acel.max.toFixed(0)}°`);

const v = F.valle(s, 30, 500), fondo = v.reduce((a, b) => (b.rms < a.rms ? b : a));
assert.ok(fondo.k > 0.3 && fondo.k < 3, `el fondo del valle está cerca de k = 1/s (${fondo.k.toFixed(2)})`);
assert.ok(v[0].rms > 5 * fondo.rms && v[v.length - 1].rms > 5 * fondo.rms, 'los dos lados del valle son mucho peores');
ok(`el valle: ${v[0].rms.toFixed(1)}° con k = 0.01, ${fondo.rms.toFixed(2)}° con k = ${fondo.k.toFixed(2)}, ${v[v.length - 1].rms.toFixed(1)}° con k = 50`);
// sin sacudidas el valle se corre a la derecha: conviene tirar más fuerte
const tranquilo = F.valle(F.inclinacion({ sacudidas: 0 }), 30, 500).reduce((a, b) => (b.rms < a.rms ? b : a));
assert.ok(tranquilo.k > 2 * fondo.k, `sin sacudidas el mejor k crece (${tranquilo.k.toFixed(2)} contra ${fondo.k.toFixed(2)})`);
ok(`sin sacudidas el mejor k pasa de ${fondo.k.toFixed(2)} a ${tranquilo.k.toFixed(2)}`);

// la gravedad no ve el rumbo: cambiarlo no mueve ni una cifra de lo que lee el reloj
for (const [i, r, t] of [[0, 0, 0], [30, 0, 0], [-50, 0, 40], [80, 0, -120]]) {
  const a = F.gravedadLeida(i, r, t);
  near(Math.hypot(...a), 9.81, 1e-9, 'la gravedad mide siempre g');
  for (const rr of [45, 170, -90]) {
    const b = F.gravedadLeida(i, rr, t);
    for (let j = 0; j < 3; j++) near(b[j], a[j], 1e-12, 'el rumbo no cambia la gravedad leída');
  }
  near(F.elevacion([1, 0, 0], a), i, 1e-9, 'la elevación sale de la gravedad leída');
}
assert.ok(Math.abs(F.gravedadLeida(30, 0, 0)[0] - F.gravedadLeida(0, 0, 0)[0]) > 4, 'inclinar sí la cambia');
ok('de los tres giros, la gravedad ve inclinar y atornillar, y no ve el rumbo');

// en 3D (el mocap apuntando, con ruido y sesgo): Mahony deja quieta la inclinación y el rumbo se va ∫ b·ĝ dt
const v3 = (a) => [a[0], a[1], a[2]];
const imu = M.synth('apuntar', 'l', { noise: true, loops: 6 });
const X0 = v3(imu.truth.X), Z0 = v3(imu.truth.Z), frame0 = [X0, M.vec.cross(Z0, X0), Z0], psi0 = M.headingOf(v3(imu.truth.F));
const media = (a, i0, i1) => { let s2 = 0, c = 0; for (let i = i0; i < i1; i++) if (!Number.isNaN(a[i])) { s2 += Math.abs(a[i]); c++; } return s2 / c; };
const pred = F.derivaPredicha(imu), n = imu.n;
for (const kp of [0, 2]) {
  const e = F.erroresAntebrazo(imu.truth.F, M.reconstruct(imu, 'l', { kp, frame0, psi0 }).F);
  const incl = media(e.incl, n - 500, n), rumbo = e.rumbo[n - 1];
  if (kp === 0) {
    assert.ok(incl > 10, `sin resorte (Kp = 0) la inclinación también se va (${incl.toFixed(1)}°)`);
    ok(`Kp = 0: la inclinación se va ${incl.toFixed(0)}° en un minuto`);
  } else {
    assert.ok(incl < 1, `con Kp = 2 la inclinación queda quieta (${incl.toFixed(2)}°)`);
    assert.ok(Math.abs(rumbo) > 10, `con Kp = 2 el rumbo se va igual (${rumbo.toFixed(1)}°)`);
    near(rumbo, pred[n - 1], 1, 'el rumbo se va casi exactamente ∫ b·ĝ dt');
    ok(`Kp = 2: inclinación ${incl.toFixed(2)}°, rumbo ${rumbo.toFixed(1)}° (∫ b·ĝ dt = ${pred[n - 1].toFixed(1)}°)`);
  }
}

// las tasas en vivo: subir la mano en la muñeca izquierda (antebrazo +x, gravedad +z) es positivo
near(F.subida([0, -30, 0], [0, 0, 9.8], [1, 0, 0]), 30, 1e-9, 'subir la mano es positivo');
near(F.subida([0, 30, 0], [0, 0, 9.8], [-1, 0, 0]), 30, 1e-9, 'en la derecha también');
near(F.giroVertical([3, 4, 5], [0, 0, 9.8]), 5, 1e-9, 'el giro vertical es la parte de ω a lo largo de arriba');
ok('las tasas en vivo tienen el signo de wrist.js');
console.log('\nTodo pasa.');
