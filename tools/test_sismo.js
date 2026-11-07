// Pruebas de la muñeca (wrist.js) y de la matemática del juego del sismógrafo (sismomath.js), con datos
// sintéticos donde la respuesta se conoce.
//   node tools/test_sismo.js
'use strict';
const path = require('path');
const assert = require('assert');
const web = path.join(__dirname, '..', 'server', 'web');
const { Wrist } = require(path.join(web, 'wrist.js'));
const M = require(path.join(web, 'sismomath.js'));

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a.toFixed(4)} vs ${b} (±${tol})`);

// ---- muñeca: el mismo gesto da el mismo signo en las dos manos si se elige bien la mano ----
// Antebrazo horizontal, pantalla hacia arriba: la gravedad (arriba) es +z del reloj.
// Izquierda: antebrazo +x. Subir la mano gira el antebrazo hacia arriba: eje f × g = x × z = −y.
// Derecha (botones hacia el codo): antebrazo −x; subir la mano: eje (−x) × z = +y.
const up = [0, 0, 9.8];
const still = (w) => { for (let i = 0; i < 3; i++) w.bias[i] = 0; return w; };
near(still(new Wrist('left')).rates([0, -30, 0], up).pitch, 30, 1e-9, 'izquierda: subir la mano es pitch +');
near(still(new Wrist('right')).rates([0, 30, 0], up).pitch, 30, 1e-9, 'derecha: subir la mano es pitch +');
near(still(new Wrist('left')).rates([0, 30, 0], up).pitch, -30, 1e-9, 'derecha leída como izquierda: arriba sale abajo (el espejo)');
// girar a la derecha (horario visto desde arriba = −z) da el mismo yaw en las dos manos
near(still(new Wrist('left')).rates([0, 0, -30], up).yaw, -30, 1e-9, 'izquierda: yaw');
near(still(new Wrist('right')).rates([0, 0, -30], up).yaw, -30, 1e-9, 'derecha: yaw (no depende de la mano)');
// atornillar (horario visto desde el codo = giro positivo alrededor del antebrazo)
near(still(new Wrist('left')).rates([40, 0, 0], up).roll, 40, 1e-9, 'izquierda: atornillar');
near(still(new Wrist('right')).rates([-40, 0, 0], up).roll, 40, 1e-9, 'derecha: atornillar');

// ---- sismógrafo ----
let seed = 7;
const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const comps = M.makeTarget(2, rand);
assert.ok(comps.reduce((s, c) => s + c.a, 0) <= 0.75 + 1e-9, 'la línea nunca pasa de 0.75');
near(M.targetAt(comps, M.LEAD + 3), M.wave(comps, M.LEAD + 3), 1e-12, 'después de la entrada la línea es la onda');
near(M.wave(comps, 5), M.wave(comps, 5 + M.T), 1e-9, 'la línea se repite cada T');

// cuadros a ~60 Hz con un poco de jitter, como requestAnimationFrame
function play(fn, noise = 0) {
  const out = [];
  for (let t = 0; t <= M.LEAD + M.T + 0.2; t += 1 / 60 + (rand() - 0.5) * 0.004) out.push({ t, y: fn(t) + noise * (rand() - 0.5) });
  return out;
}
// llegar 200 ms tarde
let a = M.analyze(play((t) => M.targetAt(comps, t - 0.2)), comps, 0.1);
near(a.delay, 0.2, 0.012, 'retraso por correlación');
for (const f of a.freqs) { near(f.delay, 0.2, 0.012, `retraso a ${f.f} Hz`); near(f.gain, 1, 0.02, `ganancia a ${f.f} Hz`); }
assert.ok(a.remnant < 0.02, 'sin ruido no hay remanente');
// el ejercicio del capítulo 11: llegar 0.25 s tarde deja |1 − H| = 2|sen(π f τ)| en cada onda
a = M.analyze(play((t) => M.targetAt(comps, t - 0.25)), comps, 0.1);
near(a.delay, 0.25, 0.012, 'ejercicio: τ');
for (const f of a.freqs) near(f.error, 2 * Math.abs(Math.sin(Math.PI * f.f * 0.25)), 0.03, `ejercicio: |1 − H| a ${f.f} Hz`);
// adelantarse 100 ms (con vista previa)
a = M.analyze(play((t) => M.wave(comps, t + 0.1)), comps, 0.1);
near(a.delay, -0.1, 0.012, 'adelantarse sale negativo');
// seguir solo la mitad: ganancia 0.5 y error 0.5 en todas las frecuencias
a = M.analyze(play((t) => 0.5 * M.wave(comps, t)), comps, 0.1);
for (const f of a.freqs) { near(f.gain, 0.5, 0.02, 'media ganancia'); near(f.error, 0.5, 0.02, 'medio error'); }
// perfecto: todo dentro de la banda, error cero
a = M.analyze(play((t) => M.wave(comps, t)), comps, 0.05);
near(a.inBand, 1, 1e-9, 'perfecto: siempre dentro'); near(a.rms, 0, 0.002, 'perfecto: error rms');
// ruido grande: el remanente crece
a = M.analyze(play((t) => M.wave(comps, t), 1.2), comps, 0.1);
assert.ok(a.remnant > 0.3, `con ruido el remanente debe crecer (${a.remnant.toFixed(2)})`);
// un congelón de medio segundo en la ventana medida anula la ronda
const frozen = play((t) => M.wave(comps, t)).filter((s) => s.t < 8 || s.t > 8.5);
assert.strictEqual(M.analyze(frozen, comps, 0.1), null, 'congelón: sin análisis');

// ---- lo que el capítulo 11 explica de la cuenta ----
// el remanente es 1 − Σ|Y|²/2 / varianza: una onda de amplitud b fuera de la línea, con vueltas enteras, deja b²/2 sin explicar
{
  const b = 0.2, fx = 37 / M.T;
  assert.ok(!comps.some((c) => Math.abs(c.f - fx) < 1e-9), 'la onda extra no es de la línea');
  a = M.analyze(play((t) => M.wave(comps, t) + b * Math.sin(2 * Math.PI * fx * t)), comps, 0.1);
  const linea = comps.reduce((s, c) => s + c.a * c.a / 2, 0);
  near(a.remnant, (b * b / 2) / (linea + b * b / 2), 0.01, 'remanente = varianza que sobra / varianza total');
}
// la cuerda entre H = e^{−iθ} y 1 mide 2 sen(θ/2)
for (let th = 0.1; th < 6.2; th += 0.3) near(Math.hypot(1 - Math.cos(th), Math.sin(th)), 2 * Math.abs(Math.sin(th / 2)), 1e-12, 'cuerda');
// la parábola por tres puntos encuentra la cima de una parábola exacta
{
  const c = (x) => 0.9 - 3 * (x - 0.2537) ** 2, h = 0.01, x0 = 0.25;
  const [cm, c0, cp] = [c(x0 - h), c(x0), c(x0 + h)];
  near(x0 + h * 0.5 * (cm - cp) / (cm - 2 * c0 + cp), 0.2537, 1e-12, 'parábola por tres puntos');
}
// Nyquist: con 10 muestras por segundo, 7 Hz deja las mismas muestras que −3 Hz (3 Hz con la fase dada vuelta)
for (let n = 0; n < 20; n++) near(Math.sin(2 * Math.PI * 7 * n / 10 + 0.3), Math.sin(2 * Math.PI * -3 * n / 10 + 0.3), 1e-9, 'el disfraz');
// octavas: doce semitonos iguales dan ×2, el la 69 suena a 440 Hz y el do 60 a 261.6 Hz
const midiHz = (m) => 440 * Math.pow(2, (m - 69) / 12);       // la de musica.js, que no la exporta
assert.ok(require('fs').readFileSync(path.join(web, 'musica.js'), 'utf8').includes('const midiHz = (m) => 440 * Math.pow(2, (m - 69) / 12);'), 'la copia es la de musica.js');
near(Math.pow(Math.pow(2, 1 / 12), 12), 2, 1e-12, 'doce semitonos son una octava');
near(midiHz(69), 440, 1e-12, 'la 69'); near(midiHz(60), 261.63, 0.01, 'do central'); near(midiHz(81) / midiHz(69), 2, 1e-12, 'una octava');
console.log('OK');
