// Pruebas del capítulo 1 del curso (Qué es un sensor): lo que el capítulo afirma, comprobado con señales inventadas
// donde la respuesta se conoce. Las pruebas del reposo corren también contra tu ejercicio.
//   node tools/test_sensor.js              # la cuenta del curso
//   node tools/test_sensor.js --ejercicio  # tu búsqueda, en docs/curso/ejercicios/cap01.js
// Solo necesita node. Si además hay python, compara con Motion de tools/air_mouse.py: repite la grabación inventada
// con --replay y prueba el seguimiento y la recuperación del sesgo.
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert');
const { spawnSync } = require('child_process');

const RAIZ = path.join(__dirname, '..');
const WEB = path.join(RAIZ, 'server', 'web');
const M = require(path.join(WEB, 'mocapmath.js'));
const { Wrist, forearmOf } = require(path.join(WEB, 'wrist.js'));
const S = require(path.join(WEB, 'sismomath.js'));

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
const omitida = (msg) => console.log(`  - omitida: ${msg}`);
const G = 9.81;

// números al azar repetibles, con forma de campana
let estado = 12345;
const u = () => { estado = (estado * 16807) % 2147483647; return estado / 2147483647; };
const normal = () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u());

const promedio = (x) => x.reduce((a, b) => a + b, 0) / x.length;
const rms = (x) => Math.sqrt(promedio(x.map((v) => v * v)));
const desviacion = (x) => { const m = promedio(x); return rms(x.map((v) => v - m)); };
const mediana = (x) => { const s = [...x].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const picoAPico = (x) => Math.max(...x) - Math.min(...x);
const columna = (a, i) => { const o = []; for (let k = i; k < a.length; k += 3) o.push(a[k]); return o; };

function enPython(codigo, entrada) {
  for (const py of [process.env.PYTHON, 'python', 'python3'].filter(Boolean)) {
    const r = spawnSync(py, ['-I', '-c', codigo], { input: JSON.stringify(entrada), encoding: 'utf8', cwd: RAIZ, maxBuffer: 1 << 26 });
    if (!r.error && r.status === 0) return JSON.parse(r.stdout);
  }
  return null;
}

// ---------- los ejes ----------
console.log('Los ejes del reloj');
const { cross, dot } = M.vec;
for (const [lado, signo] of [['l', 1], ['r', -1]]) {
  const w = M.watchOf(M.build(M.ANIMS.apuntar.pose(0, lado)), lado);
  cross(w.Z, w.X).forEach((v, i) => near(v, w.Y[i], 1e-9, 'y = z × x'));
  near(dot(w.X, w.F), signo, 1e-9, 'x y el antebrazo');
}
ok('watchOf: en la mano izquierda x apunta a la mano, en la derecha al codo, e y = z × x en las dos');
assert.deepStrictEqual([forearmOf('left')[0], forearmOf('right')[0]], [1, -1], 'wrist.js');
ok('wrist.js: el antebrazo es +x en la izquierda y −x en la derecha');

// ---------- acelerómetro ----------
console.log('Acelerómetro');
const limpio = M.synth('apuntar', 'l', {});
const quieto = [...Array(limpio.n).keys()].sort((a, b) => Math.hypot(limpio.gyr[3 * a], limpio.gyr[3 * a + 1], limpio.gyr[3 * a + 2]) - Math.hypot(limpio.gyr[3 * b], limpio.gyr[3 * b + 1], limpio.gyr[3 * b + 2]))[0];
const a0 = [0, 1, 2].map((i) => limpio.acc[3 * quieto + i]), g0 = [0, 1, 2].map((i) => limpio.grav[3 * quieto + i]);
near(Math.hypot(...a0), G, 0.01, 'quieto, el largo del acelerómetro es g');
a0.forEach((v, i) => near(v, g0[i], 0.01, 'quieto, acelerómetro y gravedad coinciden'));
assert.ok(a0[2] > 9, 'con la pantalla hacia arriba z es positivo: los dos apuntan hacia ARRIBA');
ok(`con la mano quieta synth da |a| = ${Math.hypot(...a0).toFixed(3)} m/s² y z positivo con la pantalla arriba: apunta hacia arriba`);
// lo que acelera + g hacia arriba, en un reloj de costado ladeado th
const lee = (a, th) => [-Math.sin(th) * (G + a), 0, Math.cos(th) * (G + a)];
near(lee(0, 0)[2], 9.81, 1e-12, 'sobre la mesa');
near(Math.hypot(...lee(-G, 0)), 0, 1e-12, 'en caída libre');
near(lee(3, 0)[2], 12.81, 1e-12, 'subiendo con a = 3');
for (const th of [0.3, 0.6, -0.87]) near(Math.hypot(...lee(0, th)), G, 1e-12, 'el largo no cambia al ladearlo');
ok('sobre la mesa 9.81, en caída libre 0, subiendo con a = +3 da 12.81, y ladeado el largo sigue en 9.81');

// ---------- giroscopio ----------
console.log('Giroscopio');
// la cuenta de synth entre la orientación de antes y la de después, para un giro alrededor de z
const Rz = (a) => [[Math.cos(a), Math.sin(a), 0], [-Math.sin(a), Math.cos(a), 0], [0, 0, 1]];   // columnas: los ejes del reloj
function tasa(P, N, dt) {
  const r = (i, j) => dot(P[i], N[j]);
  const ang = Math.acos(Math.max(-1, Math.min(1, (r(0, 0) + r(1, 1) + r(2, 2) - 1) / 2)));
  const k = ang / (2 * Math.sin(ang)) / (2 * dt) * 180 / Math.PI;
  return [(r(2, 1) - r(1, 2)) * k, (r(0, 2) - r(2, 0)) * k, (r(1, 0) - r(0, 1)) * k];
}
const dt = 0.01, a90 = 90 * Math.PI / 180;
const leido = tasa(Rz(-a90 * dt), Rz(a90 * dt), dt);
near(leido[2], 90, 1e-6, '90 °/s alrededor de z'); near(leido[0], 0, 1e-9, 'nada en x'); near(leido[1], 0, 1e-9, 'nada en y');
ok('girar a 90 °/s alrededor de z solo marca en z, con signo positivo si gira antihorario visto desde la punta de z');

// ---------- ruido y sesgo ----------
console.log('Ruido y sesgo');
const conRuido = M.synth('tablet', 'l', { noise: true }), sinRuido = M.synth('tablet', 'l', {});
const resta = (nom, i) => columna(conRuido[nom], i).map((v, k) => v - columna(sinRuido[nom], i)[k]);
[0, 1, 2].forEach((i) => {
  const e = resta('gyr', i);
  near(desviacion(e), 0.3, 0.03, 'el ruido del giroscopio en synth');
  near(mediana(e), conRuido.bias[i], 0.05, 'la mediana quieta da el sesgo');
});
near(desviacion(resta('acc', 2)), 0.05, 0.006, 'el ruido del acelerómetro en synth');
near(desviacion(resta('grav', 2)), 0.02, 0.003, 'el ruido de la gravedad en synth');
ok('en synth, el giroscopio tiene σ = 0.3 °/s y sesgos de 0.6, −0.4 y 0.3 °/s; el acelerómetro σ = 0.05 m/s²');
const e = resta('gyr', 1);
near(rms(e) ** 2, promedio(e) ** 2 + desviacion(e) ** 2, 1e-9, 'RMS² = promedio² + σ²');
near(rms(e), 0.5, 0.03, 'con 0.4 de centro y 0.3 de ruido el RMS es 0.5');
ok(`RMS² = promedio² + σ²: ${rms(e).toFixed(2)}² = ${Math.abs(promedio(e)).toFixed(2)}² + ${desviacion(e).toFixed(2)}²`);
const pp = [10, 100, 800].map((n) => picoAPico(e.slice(0, n))), ds = [10, 100, 800].map((n) => desviacion(e.slice(0, n)));
assert.ok(pp[0] < pp[1] && pp[1] < pp[2], 'el pico a pico crece con la cantidad de muestras');
near(ds[1], ds[2], 0.05, 'σ no');
ok(`el pico a pico crece (${pp.map((v) => v.toFixed(1)).join(', ')}) y σ se queda (${ds.map((v) => v.toFixed(2)).join(', ')}) con 10, 100 y 800 muestras`);
// el error de la línea del Sismógrafo: analyze usa la misma raíz del promedio de los cuadrados
const comps = S.makeTarget(1, () => 0.5), corrida = [];
for (let t = 0; t <= 23; t += 0.02) corrida.push({ t, y: S.wave(comps, t) + 0.1 });
near(S.analyze(corrida, comps, 0.2).rms, 0.1, 0.002, 'sismomath.analyze mide el error con RMS');
ok('sismomath.analyze: un error constante de 0.1 da RMS 0.1');
const vuelta = 360 / 86164;
near(vuelta, 0.0042, 0.0001, 'la Tierra');
ok(`la Tierra gira ${vuelta.toFixed(4)} °/s: 0.4 °/s es ${(0.4 / vuelta).toFixed(0)} veces más`);
// sesgo aprendido por Wrist.rates
const m = new Wrist('left');
for (let k = 0; k < 500; k++) m.rates([0.4, -0.3, 0.2], [0, 0, G]);
near(m.bias[0], 0.4 * (1 - 0.998 ** 500), 1e-9, 'el promedio que olvida de Wrist.rates');
const b0 = m.bias[0];
m.rates([100, 0, 0], [0, 0, G]);
assert.strictEqual(m.bias[0], b0, 'moviéndose no aprende');
ok(`Wrist.rates aprende con α = 0.002: en 5 s a 100 Hz llega al ${(100 * m.bias[0] / 0.4).toFixed(0)}%, y moviéndose no aprende`);

// ---------- umbral ----------
console.log('Umbral');
const ruido3 = [0, 1, 2].map((i) => { const x = resta('gyr', i), c = promedio(x); return x.map((v) => v - c); });
const mayor = ruido3[0].map((_, k) => Math.max(...ruido3.map((r) => Math.abs(r[k]))));
const cruza = (L) => 100 * mayor.filter((v) => v >= L).length / mayor.length;
assert.ok(cruza(0.4) > 30, 'muy baja, el ruido la cruza');
assert.ok(cruza(1.5) < 1, 'en 1.5 °/s casi nunca');
ok(`con σ = 0.3 °/s, el ruido cruza una línea en 0.4 °/s el ${cruza(0.4).toFixed(0)}% de las muestras y en 1.5 °/s el ${cruza(1.5).toFixed(1)}%`);

// ---------- el reposo: Motion._rest_window y Motion._calibrate, línea por línea ----------
const fuente = fs.readFileSync(path.join(RAIZ, 'tools', 'air_mouse.py'), 'utf8');
const defecto = (opcion) => fuente.match(new RegExp(`"--${opcion}", type=float, default=([\\w.]+)`))[1];
const STILL = Number(fuente.match(/^STILL_DEG = ([\d.]+)/m)[1]), G0 = Number(fuente.match(/^G0 = ([\d.]+)/m)[1]);
const P2P = Number(defecto('calib-p2p')), TAU = Number(defecto('bias-tau'));
assert.strictEqual(defecto('bias-max'), 'STILL_DEG', '--bias-max es STILL_DEG');
assert.deepStrictEqual([P2P, STILL, TAU, G0], [2.5, 1.5, 20, 9.807], 'los valores que da el capítulo');

function reposoDelCurso(giro, acel, grav) {
  const ev = [...giro.map((s) => ['g', s]), ...acel.map((s) => ['a', s]), ...grav.map((s) => ['v', s])];
  const orden = { g: 0, a: 1, v: 2 };
  ev.sort((p, q) => p[1].t - q[1].t || orden[p[0]] - orden[q[0]]);
  const calib = [], acc = [], gdir = [];
  let prev = null, n = 0, gravT = -Infinity;
  const veredictos = {};
  for (const [tipo, s] of ev) {
    if (tipo === 'v') {
      const l = Math.hypot(s.x, s.y, s.z);
      gdir.push([s.t, s.x / l, s.y / l, s.z / l]); gravT = s.t;
    } else if (tipo === 'a') {
      const l = Math.hypot(s.x, s.y, s.z);
      acc.push([s.t, l, prev && s.t - prev.t <= 100 ? Math.hypot(s.x - prev.x, s.y - prev.y, s.z - prev.z) : 0]);
      prev = s;
      if (s.t - gravT >= 500) gdir.push([s.t, s.x / l, s.y / l, s.z / l]);
    } else {
      calib.push([s.t, s.x, s.y, s.z]);
      if (++n % 10) continue;
      const t = s.t;
      for (const d of [calib, acc, gdir]) while (d.length && d[0][0] < t - 1000) d.shift();
      if (calib.length < 80) continue;
      const cols = [1, 2, 3].map((i) => calib.map((r) => r[i]));
      const p2p = Math.max(...cols.map(picoAPico)), med = cols.map(mediana);
      let v = 'ok';
      if (p2p >= P2P) v = 'movimiento';
      else if (Math.max(...med.map(Math.abs)) >= STILL) v = 'giro constante';
      else if (acc.length && Math.max(...acc.map((r) => Math.abs(r[1] - G0))) >= 1) v = 'aceleración';
      else if (acc.length && Math.max(...acc.map((r) => r[2])) >= 0.6) v = 'sacudida';
      else if (gdir.length >= 2 && Math.max(...[1, 2, 3].map((i) => picoAPico(gdir.map((r) => r[i])))) >= 0.05) v = 'gravedad inestable';
      veredictos[v] = (veredictos[v] || 0) + 1;
      if (v === 'ok') return { t, sesgo: med, veredictos };
    }
  }
  return null;
}

// una grabación inventada: una trampa por cada condición y al final el reposo
const SESGO = [0.41, -0.27, 0.12], T0 = 1700000000000;
function grabar(final = 11, reposo = 8) {
  const giro = [], acel = [], grav = [];
  for (let k = 0; k < final * 100; k++) {
    const s = k / 100, t = T0 + k * 10;
    const mov = s < 2 ? 40 * Math.sin(2 * Math.PI * 1.3 * s) : s < 3.5 ? 5 : 0;     // se mueve; gira parejo a 5 °/s
    const g = s >= 6.5 && s < reposo ? 0.09 * (s - 6.5) : 0;                         // gravedad que se va de lado, sin giro
    const az = s >= 3.5 && s < 5 ? 1.4 : s < 2 ? 3 * Math.sin(2 * Math.PI * 1.3 * s) : 0;   // empuje parejo: |a| lejos de g
    const golpe = s >= 5 && s < 6.5 && k % 37 === 0 ? 0.75 : 0;                      // golpecitos: sacudida sin salir de ±1
    giro.push({ t, x: SESGO[0] + mov + 0.25 * normal(), y: SESGO[1] + 0.25 * normal(), z: SESGO[2] + 0.25 * normal() });
    acel.push({ t, x: 0.03 * normal() + golpe, y: 0.03 * normal(), z: G + az + 0.03 * normal() });
    grav.push({ t, x: G * Math.sin(g), y: 0, z: G * Math.cos(g) });
  }
  return { giro, acel, grav };
}

function replay(rec) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cap01-'));
  try {
    for (const [nombre, datos] of [['GYROSCOPE', rec.giro], ['ACCELERATION', rec.acel], ['GRAVITY', rec.grav]]) {
      const filas = datos.map((s) => [s.t, s.t + 25, s.x, s.y, s.z].join(','));
      fs.writeFileSync(path.join(dir, `${nombre}.csv`), ['t_watch_ms,t_recv_ms,x,y,z', ...filas].join('\n') + '\n');
    }
    for (const py of [process.env.PYTHON, 'python', 'python3'].filter(Boolean)) {
      const r = spawnSync(py, ['-I', path.join('tools', 'air_mouse.py'), '--replay', dir], { encoding: 'utf8', cwd: RAIZ, maxBuffer: 1 << 26 });
      const m = !r.error && /sesgo: inicial \(([^)]*)\)/.exec(r.stdout || '');
      if (m) return m[1].trim().split(/\s+/).map(Number);
    }
    return null;
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function probar(primerReposo, nombre) {
  console.log(`El primer segundo quieto (${nombre})`);
  const rec = grabar();
  const curso = reposoDelCurso(rec.giro, rec.acel, rec.grav);
  assert.ok(curso, 'la grabación tiene un reposo');
  assert.deepStrictEqual(Object.keys(curso.veredictos).sort(), ['aceleración', 'giro constante', 'gravedad inestable', 'movimiento', 'ok', 'sacudida'],
    'la grabación pasa por todas las trampas');
  const mio = primerReposo(rec.giro, rec.acel, rec.grav);
  assert.ok(mio, 'hay un segundo quieto en la grabación');
  near(mio.t, curso.t, 150, 'cae en el mismo segundo que Motion._calibrate (ms)');
  ok(`encuentra el reposo a los ${((mio.t - T0) / 1000).toFixed(2)} s, después de todas las trampas (el reposo empieza a los 8 s)`);
  mio.sesgo.forEach((v, i) => near(v, curso.sesgo[i], 0.06, `el sesgo del eje ${'xyz'[i]}`));
  mio.sesgo.forEach((v, i) => near(v, SESGO[i], 0.1, `cerca del sesgo de verdad en ${'xyz'[i]}`));
  ok(`el sesgo da ${mio.sesgo.map((v) => v.toFixed(2)).join(', ')} °/s (el de verdad: ${SESGO.join(', ')})`);
  const nunca = grabar(7.9, 7.9);
  assert.strictEqual(primerReposo(nunca.giro, nunca.acel, nunca.grav), null, 'sin reposo devuelve null');
  ok('si la grabación nunca descansa, no inventa un sesgo');
  const py = replay(rec);
  if (py) {
    py.forEach((v, i) => near(v, curso.sesgo[i], 0.006, `--replay en el eje ${'xyz'[i]}`));
    py.forEach((v, i) => near(v, mio.sesgo[i], 0.06, `--replay contra el tuyo en el eje ${'xyz'[i]}`));
    ok(`repitiendo la grabación con --replay, Motion._calibrate toma ${py.join(', ')} °/s: lo mismo`);
  } else omitida('no hay python para repetir la grabación con --replay');
}

// ---------- después del primer reposo ----------
console.log('Seguir el sesgo');
// feed_gyro: k = dt/τ, con el paso limitado a 0.05 °/s por segundo
const paso = (b, raw, d) => b + Math.max(-0.05 * d, Math.min(0.05 * d, d / TAU * (raw - b)));
let b = 0, seg = 0;
while (seg < 10) { b = paso(b, 3, 0.01); seg += 0.01; }
near(b, 0.5, 0.001, 'el paso limitado: 0.05 °/s por segundo durante 10 s');
ok('un error grande se sigue a 0.05 °/s por segundo: 10 s corrigen 0.5 °/s');
b = 0; seg = 0;
while (seg < TAU) { b = paso(b, 0.5, 0.01); seg += 0.01; }
near(b, 0.5 * (1 - Math.exp(-1)), 0.01, 'un error chico se cierra con τ = 20 s');
ok(`un error chico se cierra como un promedio de ${TAU} s: en ${TAU} s corrige el ${(100 * b / 0.5).toFixed(0)}%`);
const real = enPython([
  'import json,math,random,sys',
  'sys.path.insert(0,"tools")',
  'import air_mouse as A',
  'def correr(bias0, verdad, dur):',
  '    m=A.Motion(A.make_config()); r=random.Random(3)',
  '    m.calibrated=True; m.bias=[bias0,0.0,0.0]',
  '    salto=None',
  '    for k in range(int(dur*100)):',
  '        t=1000.0+k*10; s=k/100',
  '        m.feed_gravity(t,0,0,9.81); m.feed_accel(t,0,0,9.81)',
  '        m.feed_gyro(t,verdad(s)+r.gauss(0,0.05),r.gauss(0,0.05),r.gauss(0,0.05))',
  '        if salto is None and m.recoveries: salto=s',
  '    return m.bias[0],m.bias_max_step,salto',
  'lento=correr(0.0,lambda s:0.5,20.0)',
  'grande=correr(-0.6,lambda s:1.0,10.0)',
  'print(json.dumps({"lento":lento,"grande":grande}))'].join('\n'), {});
if (real) {
  near(real.lento[0], 0.5 * (1 - Math.exp(-1)), 0.03, 'Motion sigue el sesgo con τ = 20 s');
  assert.ok(real.lento[1] <= 0.05 * 0.01 + 1e-12, 'Motion no da pasos de más de 0.05 °/s por segundo');
  ok(`Motion de verdad: en 20 s sigue un error de 0.5 °/s hasta ${real.lento[0].toFixed(2)} °/s`);
  near(real.grande[0], 1.0, 0.05, 'Motion recupera el sesgo de golpe');
  assert.ok(real.grande[2] >= 3 && real.grande[2] <= 5, `la recuperación llega unos segundos después (${real.grande[2]} s)`);
  ok(`Motion._recover_bias: con el sesgo errado en 1.6 °/s lo reemplaza a los ${real.grande[2].toFixed(1)} s`);
} else omitida('no hay python para probar Motion de verdad');

if (process.argv.includes('--ejercicio')) {
  probar(require(path.join(RAIZ, 'docs', 'curso', 'ejercicios', 'cap01.js')).primerReposo, 'tu ejercicio');
} else {
  probar(reposoDelCurso, 'del curso');
}
console.log('\nTodo pasa.');
