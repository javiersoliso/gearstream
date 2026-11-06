// Pruebas del capítulo 4 del curso (La gravedad dice dónde es arriba): lo que el capítulo afirma, con la cuenta de
// server/web/mocapmath.js y fusionmath.js. Las pruebas de la inclinación corren también contra tu ejercicio.
//   node tools/test_gravedad.js              # la cuenta del curso
//   node tools/test_gravedad.js --ejercicio  # tu inclinación, en docs/curso/ejercicios/cap04.js
'use strict';
const path = require('path');
const assert = require('assert');
const web = path.join(__dirname, '..', 'server', 'web');
const M = require(path.join(web, 'mocapmath.js'));
const F = require(path.join(web, 'fusionmath.js'));
const { dot, len, sub } = M.vec;

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a.toFixed(5)} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
const G = 9.81, v3 = (a, k) => [a[3 * k], a[3 * k + 1], a[3 * k + 2]];
const R2D = 180 / Math.PI;

// ---------- lo que leen los sensores ----------
console.log('Lo que leen los sensores');
const fuerza = (a) => a + G;                 // componente vertical (hacia arriba) de lectura = a + g, con g = 9.81 hacia arriba
near(fuerza(0), 9.81, 1e-12, 'quieto marca 9.81 hacia arriba');
near(fuerza(-G), 0, 1e-12, 'cayendo marca 0');
near(fuerza(3), 12.81, 1e-12, 'subiendo con 3 m/s² marca 12.81');
ok('quieto 9.81, cayendo 0, subiendo con 3 m/s²: 12.81');

const imu = M.synth('apuntar', 'l', { noise: false });
let maxG = 0, maxDesvio = 0;
const desvios = [];
for (let k = 0; k < imu.n; k++) {
  const a = v3(imu.acc, k), g = v3(imu.grav, k);
  maxG = Math.max(maxG, Math.abs(len(g) - G));
  const d = Math.acos(Math.max(-1, Math.min(1, dot(a, g) / (len(a) * len(g))))) * R2D;
  desvios.push(d); maxDesvio = Math.max(maxDesvio, d);
}
near(maxG, 0, 1e-4, 'el largo de la gravedad es siempre 9.81');
desvios.sort((p, q) => p - q);
const mediana = desvios[desvios.length >> 1];
assert.ok(mediana < 1 && maxDesvio > 40, `mediana ${mediana.toFixed(2)}°, máximo ${maxDesvio.toFixed(1)}°`);
ok(`apuntando, el acelerómetro se aparta de arriba ${mediana.toFixed(1)}° de mediana y ${maxDesvio.toFixed(0)}° en lo brusco`);

// como AirMouse._pose_gate: a = −(arriba·antebrazo) = sen(grados bajo la horizontal)
near(Math.asin(0.87) * R2D, 60.5, 0.1, 'pausa pasados los 60°');
near(Math.asin(0.80) * R2D, 53.1, 0.1, 'sigue por debajo de 53°');
ok('el brazo caído: 0.87 son 60° bajo la horizontal y 0.80 son 53°');

const giro = (phi) => { const g = [0, G * Math.sin(phi), G * Math.cos(phi)]; return { arccos: Math.acos(g[2] / G) * R2D, atan2: Math.atan2(g[1], g[2]) * R2D }; };
near(giro(0.7).arccos, giro(-0.7).arccos, 1e-9, 'arccos no distingue el lado');
near(giro(0.7).atan2, -giro(-0.7).atan2, 1e-9, 'atan2 sí');
assert.ok(giro(0.7).atan2 > 0 && giro(-0.7).atan2 < 0, 'atan2 tiene signo');
ok('arccos da lo mismo a los dos lados; atan2(g_y, g_z) guarda el signo');

// ---------- la inclinación: lo que tiene que cumplir cualquiera que la escriba ----------
function inclinacionDelCurso(g, eje) {
  return Math.acos(Math.max(-1, Math.min(1, dot(g, eje) / (len(g) * len(eje))))) * R2D;
}

function probar(inclinacion, nombre) {
  console.log(`La inclinación (${nombre})`);
  const z = [0, 0, 1];
  for (const [g, esperado] of [[[0, 0, G], 0], [[0, 0, -G], 180], [[G, 0, 0], 90], [[-G, 0, 0], 90], [[0, G, 0], 90], [[0, -G, 0], 90]]) {
    near(inclinacion(g, z), esperado, 1e-6, `la gravedad ${g} da ${esperado}° para z`);
  }
  ok('las seis posturas dan 0°, 180° y cuatro veces 90°');

  near(inclinacion([0, 0, 3], z), 0, 1e-6, 'da igual el largo de g');
  near(inclinacion([3, 0, 3], [0, 0, 5]), 45, 1e-6, 'da igual el largo de los dos');
  ok('da igual el largo de g y del eje');

  assert.ok(Number.isFinite(inclinacion([1e-9, 0, 1], z)), 'no da NaN cerca de 0°');
  // sin recortar, cerca de un tercio de estos vectores da un coseno de 1.0000000000000002 y arccos devuelve NaN
  let semilla = 12345;
  const azar = () => (semilla = (semilla * 1664525 + 1013904223) % 4294967296) / 4294967296 - 0.5;
  for (let i = 0; i < 2000; i++) {
    const v = [azar(), azar(), azar()];
    near(inclinacion(v, v), 0, 1e-5, `el vector ${v} consigo mismo da 0, sin NaN por el redondeo`);
    near(inclinacion(v, v.map((c) => -c)), 180, 1e-5, `el vector ${v} contra su opuesto da 180, sin NaN por el redondeo`);
  }
  ok('no da NaN por el redondeo');

  const base = F.gravedadLeida(30, 0, 0);
  for (const r of [0, 45, 90, 200, 359]) {
    const g = F.gravedadLeida(30, r, 0);
    g.forEach((c, i) => near(c, base[i], 1e-9, `el rumbo ${r}° no cambia la gravedad`));
    near(inclinacion(g, [1, 0, 0]), 60, 1e-6, 'x queda a 60° de la vertical');
  }
  ok('girar el reloj sobre la mesa no cambia ni la gravedad ni la inclinación');
}

if (process.argv.includes('--ejercicio')) {
  probar(require(path.join(__dirname, '..', 'docs', 'curso', 'ejercicios', 'cap04.js')).inclinacion, 'tu ejercicio');
} else {
  probar(inclinacionDelCurso, 'del curso');
}
console.log('\nTodo pasa.');
