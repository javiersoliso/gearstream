// Pruebas del capítulo 3 del curso (Derivar e integrar con números): lo que el capítulo afirma, comprobado con
// señales inventadas donde la respuesta se conoce. Las pruebas de la integral corren también contra tu ejercicio.
//   node tools/test_derivar.js              # la cuenta del curso
//   node tools/test_derivar.js --ejercicio  # tu integral, en docs/curso/ejercicios/cap03.js
'use strict';
const path = require('path');
const assert = require('assert');

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a.toFixed(5)} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
const rango = (n, hz) => Array.from({ length: n }, (_, i) => i / hz);
const tamano = (x) => { const m = x.reduce((a, b) => a + b, 0) / x.length; return Math.sqrt(x.reduce((a, b) => a + (b - m) ** 2, 0) / x.length); };

// números al azar repetibles, con forma de campana
let estado = 12345;
const u = () => { estado = (estado * 16807) % 2147483647; return estado / 2147483647; };
const normal = () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u());

// ---------- derivar y suavizar: lo que el capítulo afirma ----------
console.log('Derivar y suavizar');
const hz = 100, dt = 1 / hz, n = 2000, t = rango(n, hz);
const adelante = (x, k) => (x[k + 1] - x[k]) / dt, central = (x, k) => (x[k + 1] - x[k - 1]) / (2 * dt);
const sen = t.map((s) => Math.sin(2 * Math.PI * 0.25 * s)), cos = t.map((s) => 2 * Math.PI * 0.25 * Math.cos(2 * Math.PI * 0.25 * s));
let eA = 0, eC = 0;
for (let k = 1; k < n - 1; k++) { eA = Math.max(eA, Math.abs(adelante(sen, k) - cos[k])); eC = Math.max(eC, Math.abs(central(sen, k) - cos[k])); }
assert.ok(eC < eA / 10, `la central cae mucho más cerca (${eC.toFixed(5)} contra ${eA.toFixed(5)})`);
ok(`la diferencia central cae más cerca que la de adelante: ${eC.toFixed(5)} contra ${eA.toFixed(5)}`);

const x2 = t.map((s) => 0.5 * 3 * s * s);                     // aceleración constante de 3
near((x2[501] - 2 * x2[500] + x2[499]) / (dt * dt), 3, 1e-6, 'la segunda diferencia da la aceleración');
ok('la segunda diferencia de x = ½·3·t² da 3');

const sigma = 0.01, ruido = t.map(() => sigma * normal());
const derRuido = []; for (let k = 1; k < n - 1; k++) derRuido.push(central(ruido, k));
near(tamano(derRuido), sigma / (Math.sqrt(2) * dt), 0.05, 'derivar agranda el ruido por 1/(√2·Δt)');
ok(`derivar vuelve un ruido de ${sigma} en ${tamano(derRuido).toFixed(2)} (σ/(√2·Δt) = ${(sigma / (Math.sqrt(2) * dt)).toFixed(2)})`);

const olvida = (x, a) => { const y = [x[0]]; for (let k = 1; k < x.length; k++) y.push(y[k - 1] + a * (x[k] - y[k - 1])); return y; };
const escalon = t.map((s) => (s >= 5 ? 1 : 0));
const llega = (a) => olvida(escalon, a).findIndex((v) => v > 0.63) / hz - 5;
assert.ok(llega(0.05) > llega(0.2) && llega(0.015) > llega(0.05), 'cuanto más suave, más tarde llega');
assert.ok(tamano(olvida(ruido, 0.05)) < tamano(ruido) / 3, 'suavizar frena el ruido');
ok(`cuanto más suave, más tarde: α = 0.2 llega en ${llega(0.2).toFixed(2)} s, α = 0.05 en ${llega(0.05).toFixed(2)} s, α = 0.015 en ${llega(0.015).toFixed(2)} s`);

const media = (x, m, k) => { let s = 0; for (let i = k - m; i < k; i++) s += x[i]; return s / m; };
const lento = t.map((s) => 3 * Math.sin(2 * Math.PI * 0.4 * s)), golpe = lento.map((v, k) => v + (k === 700 ? 2 : 0));
const alto = golpe.map((v, k) => (k >= 4 ? v - media(golpe, 4, k) : 0));
assert.strictEqual(alto.reduce((m, v, k) => (Math.abs(v) > Math.abs(alto[m]) ? k : m), 0), 700, 'el golpe es lo más grande');
ok('la señal menos su promedio de 40 ms deja el golpe, aunque la mano se mueva');

const suave = (s) => 3 * s * s - 2 * s * s * s;
near(suave(0), 0, 1e-12, 'empieza en 0'); near(suave(1), 1, 1e-12, 'termina en 1');
near((suave(1e-6) - suave(0)) / 1e-6, 0, 1e-4, 'pendiente cero al empezar'); near((suave(1) - suave(1 - 1e-6)) / 1e-6, 0, 1e-4, 'pendiente cero al terminar');
ok('3u² − 2u³ va de 0 a 1 con pendiente cero en los dos extremos');

// ---------- integrar: lo que tiene que cumplir cualquiera que lo escriba ----------
function integrarDelCurso(tt, tasa) {
  const out = [0];
  for (let k = 1; k < tt.length; k++) out.push(out[k - 1] + tasa[k] * (tt[k] - tt[k - 1]));
  return out;
}

function probar(integrar, nombre) {
  console.log(`Integrar (${nombre})`);
  const ult = (a) => a[a.length - 1];
  const tiempos = rango(301, 100), diez = tiempos.map(() => 10);
  const e = integrar(tiempos, diez);
  assert.strictEqual(e.length, tiempos.length, 'devuelve un valor por muestra');
  near(e[0], 0, 1e-9, 'empieza en 0');
  near(ult(e), 30, 1e-6, '10 °/s durante 3 s son 30°');
  ok('10 °/s durante 3 s dan 30°');

  const dejar = (k) => k % 7 !== 3 && !(k > 100 && k < 160);
  const t2 = tiempos.filter((_, k) => dejar(k));
  near(ult(integrar(t2, t2.map(() => 10))), 30, 1e-6, 'con muestras perdidas siguen siendo 30°');
  ok('si se pierden muestras siguen siendo 30°: Δt sale del reloj');

  const t60 = rango(6001, 100);
  near(ult(integrar(t60, t60.map(() => 0.3))), 18, 1e-6, 'un sesgo de 0.3 °/s en un minuto son 18°');
  ok('un sesgo de 0.3 °/s se vuelve 18° en un minuto (b·t)');

  const finales = [];
  for (let i = 0; i < 300; i++) finales.push(ult(integrar(t60, t60.map(() => 2 * normal()))));
  const predicho = 2 * Math.sqrt(60 * 0.01);
  near(tamano(finales), predicho, 0.15 * predicho, 'el ruido crece como σ√(t·Δt)');
  ok(`el ruido de 2 °/s deja ${tamano(finales).toFixed(2)}° en un minuto (σ√(t·Δt) = ${predicho.toFixed(2)}°)`);

  const t10 = rango(1001, 100), vel = integrar(t10, t10.map(() => 0.05));
  near(ult(integrar(t10, vel)), 2.5, 0.01, 'integrar dos veces es b·t²/2');
  ok('un sesgo de 0.05 m/s² integrado dos veces son 2.5 m en 10 s (b·t²/2)');

  for (const f of [0.5, 2, 8]) {
    const tt = rango(801, 400), ang = integrar(tt, tt.map((s) => 100 * Math.sin(2 * Math.PI * f * s)));
    near((Math.max(...ang) - Math.min(...ang)) / 2, 100 / (2 * Math.PI * f), 0.3, `a ${f} Hz la amplitud es a/(2πf)`);
  }
  ok('integrar una onda de 100 °/s da ±31.8° a 0.5 Hz, ±8° a 2 Hz y ±2° a 8 Hz (a/(2πf))');

  // velocidad cero: lo que sobra al final se reparte, como en tools/analyze_drawing.py
  const dur = 1.2, tz = rango(241, 200), acc = tz.map((s) => { const q = s / dur; return 60 / dur ** 2 * 60 * q * (1 - q) * (1 - 2 * q) + 150; });
  const v = integrar(tz, acc), vz = v.map((x, k) => x - (k / (v.length - 1)) * ult(v));
  const crudo = Math.abs(ult(integrar(tz, v)) - 60), arreglado = Math.abs(ult(integrar(tz, vz)) - 60);
  assert.ok(arreglado < crudo / 10, `con velocidad cero el error baja (${arreglado.toFixed(1)} contra ${crudo.toFixed(1)} mm)`);
  ok(`velocidad cero: el error de un trazo de 60 mm baja de ${crudo.toFixed(0)} mm a ${arreglado.toFixed(1)} mm`);
}

if (process.argv.includes('--ejercicio')) {
  probar(require(path.join(__dirname, '..', 'docs', 'curso', 'ejercicios', 'cap03.js')).integrar, 'tu ejercicio');
} else {
  probar(integrarDelCurso, 'del curso');
}
console.log('\nTodo pasa.');
