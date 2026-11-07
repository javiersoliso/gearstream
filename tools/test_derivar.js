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
const llega = (a) => olvida(escalon, a).findIndex((v) => v > 1 - Math.exp(-1)) / hz - 5;
assert.ok(llega(0.05) > llega(0.2) && llega(0.015) > llega(0.05), 'cuanto más suave, más tarde llega');
assert.ok(tamano(olvida(ruido, 0.05)) < tamano(ruido) / 3, 'suavizar frena el ruido');
ok(`cuanto más suave, más tarde: α = 0.2 llega en ${llega(0.2).toFixed(2)} s, α = 0.05 en ${llega(0.05).toFixed(2)} s, α = 0.015 en ${llega(0.015).toFixed(2)} s`);

// la exponencial: después de 1/α pasos queda casi 1/e, y el tiempo que eso toma es τ = Δt/α
const salto = t.map((_, k) => (k === 0 ? 0 : 1));                              // de 0 a 1 en la segunda muestra
const quedan = [[0.2, 0.328], [0.05, 0.358], [0.002, 0.3675]].map(([a, q]) => {
  const pasos = Math.round(1 / a), y = olvida(salto, a);
  near(1 - y[pasos], (1 - a) ** pasos, 1e-12, `cada paso deja (1 − α) de lo que falta (α = ${a})`);
  near((1 - a) ** pasos, q, 0.0005, `después de 1/α pasos con α = ${a}`);
  return (1 - a) ** pasos;
});
assert.ok(quedan[0] < quedan[1] && quedan[1] < quedan[2] && quedan[2] < Math.exp(-1), 'se acerca a 1/e desde abajo');
near((1 - 1e-6) ** 1e6, Math.exp(-1), 1e-6, 'con α muy chico, 1/e');
near(Math.E, 2.718, 0.0005, 'e');
near(1 - Math.exp(-1), 0.63, 0.005, 'en un τ se cierra el 63%');
near(1 - Math.exp(-2), 0.86, 0.005, 'en dos, el 86%');
near(1 - Math.exp(-3), 0.95, 0.005, 'en tres, el 95%');
for (const [a, tau, tol] of [[0.002, 5, 0.001], [0.05, 0.2, 0.012]]) {
  near(dt / a, tau, 1e-9, `τ = Δt/α con α = ${a}`);
  near(1 - olvida(salto, a)[Math.round(tau / dt)], Math.exp(-1), tol, `con α = ${a} a 100 Hz, en τ = ${tau} s falta casi 1/e`);
}
near(dt / (dt / 20), 20, 1e-9, 'Motion.feed_gyro, que se acerca Δt/20 s por muestra: τ = 20 s');
{
  const fc = 2, alfa = 1 / (1 + 1 / (2 * Math.PI * fc * dt));                 // OneEuro.alpha de tools/air_mouse.py
  near(alfa, dt / (dt + 1 / (2 * Math.PI * fc)), 1e-12, 'OneEuro.alpha es Δt/(Δt + 1/(2πf_c))');
  near(dt / alfa, dt + 1 / (2 * Math.PI * fc), 1e-12, 'su τ es Δt + 1/(2πf_c)');
}
ok(`la exponencial: 1/α pasos dejan ${quedan.map((q) => q.toFixed(4)).join(', ')} → 1/e = ${Math.exp(-1).toFixed(4)}; en 1, 2 y 3 τ se cierra el 63%, 86% y 95%`);

// derivar amplifica: la resta de dos muestras con ruidos que no dependen uno del otro mide σ√2
{
  const restas = []; for (let k = 1; k < n - 1; k++) restas.push(ruido[k + 1] - ruido[k - 1]);
  near(tamano(restas), sigma * Math.SQRT2, 0.05 * sigma * Math.SQRT2, 'la resta de dos ruidos mide σ√2');
  ok(`x[k+1] − x[k−1] con ruido ${sigma} mide ${tamano(restas).toFixed(4)} (σ√2 = ${(sigma * Math.SQRT2).toFixed(4)}); sobre 2Δt, σ/(√2·Δt)`);
}

// una onda: un ángulo ±A que da f vueltas por segundo cambia a lo sumo 2πf·A por segundo
for (const [f, A] of [[0.5, 31.83], [2, 7.96], [8, 1.99]]) {
  let mx = 0;
  for (let k = 0; k < 4000; k++) { const s = k / 4000 / f; mx = Math.max(mx, Math.abs((A * Math.sin(2 * Math.PI * f * (s + 1e-7)) - A * Math.sin(2 * Math.PI * f * s)) / 1e-7)); }
  near(mx, 2 * Math.PI * f * A, 0.001 * 2 * Math.PI * f * A, `la tasa más alta de ±${A}° a ${f} Hz es 2πf·A`);
  near(2 * Math.PI * f * A, 100, 0.1, `±${A}° a ${f} Hz es lo que deja una tasa de 100 °/s`);
}
ok('un ángulo ±A a f vueltas por segundo cambia a lo sumo 2πf·A por segundo: con tasa a, A = a/(2πf)');

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

  // con una tasa que cambia, repartir el tiempo por igual entre las muestras ya no cierra: se ve el hueco
  const t3 = tiempos.filter((_, k) => !(k > 100 && k < 160));
  near(ult(integrar(t3, t3.map((t) => (t < 0.5 ? 0 : 20)))), 50, 0.3, 'con un hueco y una tasa que cambia, 0 °/s y después 20 °/s dan 50°');
  ok('con un hueco y una tasa que cambia también sale bien: cada Δt es el suyo, no el promedio');

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
