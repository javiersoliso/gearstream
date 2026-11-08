// Pruebas del capítulo 7 del curso (De 3D a 2D: el cursor): lo que el capítulo afirma, comprobado con números. Las
// funciones que viven en páginas o en Python no se pueden cargar desde node: aquí hay una copia de su cuenta, una
// comprobación de que su texto sigue diciendo lo mismo y, en docs/curso/animaciones/cap07.py, otra de que la copia da
// lo mismo que air_mouse.py corriendo de verdad.
//   node tools/test_cursor.js              # la cuenta del curso
//   node tools/test_cursor.js --ejercicio  # tu ángulo, en docs/curso/ejercicios/cap07.js
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const raiz = path.join(__dirname, '..');
const M = require(path.join(raiz, 'server', 'web', 'mocapmath.js'));
const { Wrist } = require(path.join(raiz, 'server', 'web', 'wrist.js'));
const { timeline } = require(path.join(raiz, 'server', 'web', 'trazos.js'));

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a.toFixed(5)} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
const fuente = (...p) => fs.readFileSync(path.join(raiz, ...p), 'utf8');
const dice = (texto, frase, donde) => assert.ok(texto.includes(frase), `${donde} ya no dice: ${frase}`);
const GRADO = Math.PI / 180;
const tamano = (x) => { const m = x.reduce((a, b) => a + b, 0) / x.length; return Math.sqrt(x.reduce((a, b) => a + (b - m) ** 2, 0) / x.length); };

// ---------- copias de la cuenta de tools/air_mouse.py ----------
const CFG = { g_lo: 12, g_hi: 30, v_lo: 10, v_hi: 120, mincutoff: 2, beta: 0.01, dcutoff: 1, deadzone: 0.8, max_speed: 4000 };

function clamp(v, lo, hi) {
  if (v !== v) return lo;
  return v < lo ? lo : v > hi ? hi : v;
}

class OneEuro {
  constructor(mincutoff, beta, dcutoff) { Object.assign(this, { mincutoff, beta, dcutoff, x: null, dx: 0 }); }
  static alpha(fc, dt) { return 1 / (1 + 1 / (2 * Math.PI * fc * dt)); }
  paso(x, dt) {
    if (this.mincutoff <= 0) return x;
    if (this.x === null) { this.x = x; this.dx = 0; return x; }
    const d = (x - this.x) / dt, ad = OneEuro.alpha(this.dcutoff, dt);
    this.dx = ad * d + (1 - ad) * this.dx;
    const a = OneEuro.alpha(this.mincutoff + this.beta * Math.abs(this.dx), dt);
    this.x = a * x + (1 - a) * this.x;
    return this.x;
  }
}

function ganancia(v, c = CFG) {
  const u = clamp((v - c.v_lo) / (c.v_hi - c.v_lo), 0, 1);
  return c.g_lo + (c.g_hi - c.g_lo) * (3 * u * u - 2 * u * u * u);
}

// de las tasas de yaw y pitch (°/s) a lo que se mueve el cursor en cada muestra, como Motion.feed_gyro: filtro, zona
// muerta que resta, curva de aceleración, ganancia y tope de velocidad. La primera muestra no mueve nada.
function cadena(yaw, pitch, dt = 0.01, opts = {}) {
  const c = Object.assign({}, CFG, opts), fx = new OneEuro(c.mincutoff, c.beta, c.dcutoff), fy = new OneEuro(c.mincutoff, c.beta, c.dcutoff);
  const out = [];
  for (let k = 0; k < yaw.length; k++) {
    const rx = fx.paso(yaw[k], dt), ry = fy.paso(pitch[k], dt), rho = Math.hypot(rx, ry);
    const q = rho <= c.deadzone ? 0 : (rho - c.deadzone) / rho, ax = rx * q, ay = ry * q, g = ganancia(Math.hypot(ax, ay), c);
    let dx = -g * ax * dt, dy = -g * ay * dt;
    const rapidez = Math.hypot(dx, dy) / dt;
    if (rapidez > c.max_speed) { const f = c.max_speed / rapidez; dx *= f; dy *= f; }
    out.push(k === 0 ? [0, 0] : [dx, dy]);
  }
  return out;
}

module.exports = { CFG, OneEuro, cadena, clamp, ganancia };
if (require.main !== module) return;

const totalX = (pasos) => pasos.reduce((s, p) => s + p[0], 0);
const repetir = (n, v) => new Array(n).fill(v);

// números al azar repetibles, con forma de campana
let estado = 12345;
const u = () => { estado = (estado * 16807) % 2147483647; return estado / 2147483647; };
const normal = () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u());

// ---------- el arco y el rayo ----------
console.log('El arco y el rayo');
const D = 2.4, arco = (g) => D * g * GRADO, rayo = (g) => D * Math.tan(g * GRADO);
near(arco(1) * 100, 4.19, 0.005, 'un grado a 2.4 m');
ok(`a 2.4 m un grado son ${(arco(1) * 100).toFixed(2)} cm de arco`);
near(rayo(10), 0.42, 0.005, 'el rayo a 10°'); near(arco(10), 0.42, 0.005, 'el arco a 10°');
near(rayo(40), 2.01, 0.005, 'el rayo a 40°'); near(arco(40), 1.68, 0.005, 'el arco a 40°');
ok(`a 10° el rayo va ${(rayo(10) * 100).toFixed(1)} cm y el arco ${(arco(10) * 100).toFixed(1)} cm; a 40°, ${rayo(40).toFixed(2)} m y ${arco(40).toFixed(2)} m`);

function cursorDeUnGiro(grados, hz = 100, tasa = 10) {          // un yaw parejo: el cursor va hacia +x con yaw negativo
  const n = Math.round(grados / tasa * hz), r = new Float32Array(n * 3);
  for (let k = 0; k < n; k++) r[3 * k + 1] = -tasa;
  return M.cursorTrack(r, hz, [0, 0, 0], D * GRADO);
}
// de dónde sale θ³/3: el punto en la pared avanza D·Δθ/cos²θ = D(1 + tan²θ)Δθ; la diferencia con el arco, sumada
{
  const th = 13.2 * GRADO, h = 1e-6, n = 20000;
  near((Math.tan(0.3 + h) - Math.tan(0.3 - h)) / (2 * h), 1 + Math.tan(0.3) ** 2, 1e-6, 'la pendiente de tan θ es 1 + tan²θ');
  near(1 / Math.cos(0.3) ** 2, 1 + Math.tan(0.3) ** 2, 1e-12, '1/cos² = 1 + tan²');
  let suma = 0;
  for (let i = 0; i < n; i++) suma += Math.tan((i + 0.5) * th / n) ** 2 * th / n;
  near(suma, Math.tan(th) - th, 1e-9, 'sumar tan²θ·Δθ da tan θ − θ');
  near(th ** 3 / 3 / (Math.tan(th) - th), 1, 0.03, 'y cambiando tan²θ por θ², θ³/3');
  ok(`la diferencia crece a tan²θ por radián; a 13.2°, tan θ − θ = ${(Math.tan(th) - th).toFixed(5)} y θ³/3 = ${(th ** 3 / 3).toFixed(5)}`);
}
const c10 = cursorDeUnGiro(10), c40 = cursorDeUnGiro(40);
near(c10[c10.length - 3], arco(10), 1e-5, 'cursorTrack da D·θ a 10°');
near(c40[c40.length - 3], arco(40), 1e-5, 'cursorTrack da D·θ a 40°');
ok('`cursorTrack` con K = D·π/180 da el arco, no el rayo');

function separacion(Dm, sep) {                                  // gira hasta que el cursor y el rayo se separan sep
  const hz = 100, tasa = 1, n = 60 * 100, r = new Float32Array(n * 3);
  for (let k = 0; k < n; k++) r[3 * k + 1] = -tasa;
  const tr = M.cursorTrack(r, hz, [0, 0, 0], Dm * GRADO);
  for (let k = 0; k < n; k++) {
    const g = (k + 1) / hz * tasa;
    if (Dm * Math.tan(g * GRADO) - tr[3 * k] >= sep) return g;
  }
  return NaN;
}
const a1 = separacion(D, 0.01);
assert.ok(a1 > 12.8 && a1 < 13.4, `el centímetro llega a los 13° (${a1})`);
ok(`con D = 2.4 m el rayo y el cursor se separan 1 cm a ${a1.toFixed(1)}° (θ³/3 predice ${(Math.cbrt(3 * 0.01 / D) / GRADO).toFixed(1)}°)`);

const AP = M.ANIMS.apuntar, imu = M.synth('apuntar', 'l', { noise: false }), rec = M.reconstruct(imu, 'l', {});
const el0 = M.build(AP.pose(0, 'l')).arms.l.el, p0 = AP.target(0), Dcodo = M.vec.len(M.vec.sub(p0, el0));
const tr = M.cursorTrack(rec.rates, imu.hz, p0, Dcodo * GRADO);
const errIcono = AP.marks.slice(0, 4).map(([t0, , nombre]) => { const k = Math.round(t0 * imu.hz), p = AP.target(t0); return [nombre, Math.hypot(tr[3 * k] - p[0], tr[3 * k + 1] - p[1]) * 100]; });
const anguloIcono = (x) => Math.atan2(AP.screen.c[0] + x - el0[0], el0[2] - AP.screen.c[2]) / GRADO;
near(anguloIcono(0.55), 19, 0.5, 'los íconos de la derecha'); near(anguloIcono(-0.55), -8, 0.5, 'los de la izquierda');
near(Dcodo, 2.4, 0.15, 'el codo está a unos 2.4 m de la pantalla');
assert.ok(Math.max(...errIcono.map((e) => e[1])) < 4, 'en las esquinas la separación es de unos 3 cm');
ok(`en la simulación (D = ${Dcodo.toFixed(2)} m), la separación en los íconos: ${errIcono.map(([n, e]) => `${n} ${e.toFixed(1)} cm`).join(', ')}`);

// ---------- de dos ángulos a una dirección ----------
console.log('De dos ángulos a una dirección');
const juego = fuente('server', 'web', 'game.js'), dibuja = fuente('server', 'web', 'dibuja.js');
dice(juego, 'Math.sin(y) * Math.cos(p), Math.sin(p), -Math.cos(y) * Math.cos(p)', 'game.js');
dice(dibuja, 'Math.sin(y) * Math.cos(p), Math.sin(p), -Math.cos(y) * Math.cos(p)', 'dibuja.js');
const dir = (yaw, pitch) => { const y = yaw * GRADO, p = pitch * GRADO; return [Math.sin(y) * Math.cos(p), Math.sin(p), -Math.cos(y) * Math.cos(p)]; };
for (const [y, p] of [[0, 0], [30, 18], [-75, 40], [120, -60]]) near(M.vec.len(dir(y, p)), 1, 1e-12, 'mide 1');
near(dir(0, 0)[2], -1, 1e-12, 'adelante es −z'); near(dir(90, 0)[0], 1, 1e-12, 'derecha es +x'); near(dir(0, 90)[1], 1, 1e-12, 'arriba es +y');
near(Math.hypot(dir(30, 40)[0], dir(30, 40)[2]), Math.cos(40 * GRADO), 1e-12, 'la sombra en el piso mide cos pitch');
ok('(sen yaw·cos pitch, sen pitch, −cos yaw·cos pitch) mide 1 y es la de `aimDir` y `point3`');

// ---------- ganancia ----------
console.log('Ganancia');
const raton = fuente('tools', 'air_mouse.py');
for (const [op, v] of [['--g-lo', '12.0'], ['--g-hi', '30.0'], ['--v-lo', '10.0'], ['--v-hi', '120.0'], ['--mincutoff', '2.0'], ['--beta', '0.01'],
  ['--dcutoff', '1.0'], ['--deadzone', '0.8'], ['--max-speed', '4000.0']]) dice(raton, `a("${op}", type=float, default=${v}`, 'air_mouse.py');
dice(fuente('server', 'web', 'calibra.js'), 'const DEFAULT_GAIN = { kx: 16, ky: 16 };', 'calibra.js');
ok('los valores por omisión son los del capítulo: 12 y 30 px/°, 10 y 120 °/s, 0.8 °/s, 2 Hz, 0.01, 1 Hz, 4000 px/s');
const pxPorGrado = (Dm, pxPorMetro) => Dm * GRADO * pxPorMetro, monitor = 1920 / 0.53;
near(pxPorGrado(0.6, monitor), 38, 0.5, 'un láser a 60 cm de un monitor');
ok(`un láser a 60 cm de un monitor de 53 cm y 1920 px son ${pxPorGrado(0.6, monitor).toFixed(0)} px/°; a 2.4 m, ${pxPorGrado(2.4, monitor).toFixed(0)} px/°`);
near(1920 / 12, 160, 1e-9, 'cruzar la pantalla despacio'); near(1920 / 30, 64, 1e-9, 'cruzar la pantalla rápido');
ok('cruzar 1920 px son 160° a 12 px/° y 64° a 30 px/°');

// ---------- recortar ----------
console.log('Recortar');
dice(raton, 'return lo if v < lo else hi if v > hi else v', 'air_mouse.py');
dice(raton, 'x, y = clamp(x, vx, vx + vw - 1), clamp(y, vy, vy + vh - 1)', 'air_mouse.py');
dice(raton, 'dt = clamp(delta, 5, GAP_MS) / 1000.0', 'air_mouse.py');
dice(juego, 'const AIM_LIMIT = { yaw: 30, pitch: 18 };', 'game.js');
assert.strictEqual(clamp(5, 0, 3), 3); assert.strictEqual(clamp(-1, 0, 3), 0); assert.strictEqual(clamp(2, 0, 3), 2); assert.strictEqual(clamp(NaN, 0, 3), 0);
ok('`clamp` deja pasar lo que está en el rango, corta lo que no, y un NaN se vuelve el mínimo');
const [, [dx1, dy1]] = cadena([0, 3000], [0, 4000], 0.01, { mincutoff: 0 });
near(Math.hypot(dx1, dy1) / 0.01, 4000, 1e-6, 'el tope de velocidad');
near(dy1 / dx1, 4 / 3, 1e-9, 'el tope no cambia la dirección');
ok('el tope de 4000 px/s achica los dos ejes por igual: la dirección no cambia');
const veces = timeline([{ k: 'x', t: 0 }, { k: 'x', t: 100 }, { k: 'x', t: 5100 }, { k: 'x', t: 5200 }]).map((e) => e.at);
assert.deepStrictEqual(veces, [0, 100, 500, 600]);
ok('`timeline` recorta una pausa de 5 s a 400 ms');
let mira = 0, muneca = 0;
for (let k = 0; k < 400; k++) { muneca += 0.1; mira = clamp(mira + 0.1, -30, 30); }     // 40° contra el tope de 30°
for (let k = 0; k < 400; k++) { muneca -= 0.1; mira = clamp(mira - 0.1, -30, 30); }     // y de vuelta
near(muneca, 0, 1e-9, 'la muñeca volvió'); near(mira, -10, 1e-9, 'la mira quedó corrida lo que se recortó');
ok('si la muñeca sigue 10° contra el tope y vuelve, la mira queda corrida 10°');

// ---------- menos de un píxel ----------
console.log('Menos de un píxel');
dice(raton, 'mx, my = round(nx) - round(self.P[0]), round(ny) - round(self.P[1])', 'air_mouse.py');
const lento = cadena(repetir(201, -3), repetir(201, 0));
const unPaso = lento[100][0];
near(unPaso, 0.264, 0.002, 'a 3 °/s cada muestra mueve 0.26 px');
const conDecimales = totalX(lento), perdido = lento.reduce((s, p) => s + Math.round(p[0]), 0);
assert.strictEqual(perdido, 0, 'redondeando cada paso no se mueve');
near(conDecimales, 52.8, 0.5, 'guardando los decimales');
ok(`a 3 °/s, ${unPaso.toFixed(3)} px por muestra: en 2 s son ${conDecimales.toFixed(1)} px con decimales y ${perdido} redondeando cada paso`);
const medio = cadena(repetir(201, -5), repetir(201, 0));
const doble = medio.reduce((s, p) => s + Math.round(p[0]), 0) / totalX(medio);
near(doble, 2, 0.05, 'redondear hacia arriba duplica');
ok(`a 5 °/s, ${medio[100][0].toFixed(3)} px por muestra: redondear cada paso va ×${doble.toFixed(2)} de rápido`);

// ---------- zona muerta ----------
console.log('Zona muerta');
dice(raton, 'k = (rho - dz) / rho', 'air_mouse.py');
dice(fuente('server', 'web', 'wrist.js'), 'if (Math.hypot(yaw, pitch) < 0.6) { yaw = 0; pitch = 0; }', 'wrist.js');
dice(juego, 'if (Math.hypot(yaw, pitch) < 0.8) { yaw = 0; pitch = 0; }', 'game.js');
const paginas = (r) => new Wrist('left').rates([0, 0, r], [0, 0, 9.81]).yaw;
near(paginas(0.59), 0, 1e-9, 'bajo 0.6 corta'); near(paginas(0.61), 0.61, 1e-9, 'sobre 0.6 salta');
ok(`las páginas cortan: de ${paginas(0.59)} °/s saltan a ${paginas(0.61)} °/s al pasar 0.6`);
const resta = (r) => { const q = r <= CFG.deadzone ? 0 : (r - CFG.deadzone) / r; return r * q; };
near(resta(0.8), 0, 1e-12, 'en el borde da cero'); near(resta(0.81), 0.01, 1e-9, 'y sale de cero sin salto');
ok('el ratón aéreo resta: justo después del borde da 0.01 °/s, sin salto');
const quieto = Array.from({ length: 2000 }, () => 0.3 + 0.1 * normal());
near(totalX(cadena(quieto, repetir(2000, 0))), 0, 1e-9, 'el sesgo que queda no arrastra');
const arrastre = Math.abs(totalX(cadena(quieto, repetir(2000, 0), 0.01, { deadzone: 0 })));
near(arrastre, 72, 2, 'sin zona muerta arrastra');
ok(`0.3 °/s de sesgo con temblor mueven el cursor ${arrastre.toFixed(0)} px en 20 s sin zona muerta, y ni uno con ella`);
near(1 - resta(2) / 2, 0.4, 1e-9, 'lo que cuesta'); near(1 - resta(20) / 20, 0.04, 1e-9, 'lo que cuesta rápido');
ok('la zona muerta cuesta 40 % a 2 °/s y 4 % a 20 °/s');

// ---------- curva de aceleración ----------
console.log('Curva de aceleración');
near(ganancia(0), 12, 1e-12, 'lento'); near(ganancia(10), 12, 1e-12, 'empieza en v_lo'); near(ganancia(65), 21, 1e-12, 'a la mitad'); near(ganancia(120), 30, 1e-12, 'termina en v_hi'); near(ganancia(500), 30, 1e-12, 'rápido');
ok('la ganancia va de 12 a 30 px/° entre 10 y 120 °/s, y vale 21 a la mitad');
// una vuelta de 20° que arranca y frena suave, en T segundos, más medio segundo para que el filtro termine
const veinte = (T) => { const n = Math.round(T * 100), r = Array.from({ length: n + 50 }, (_, k) => { const q = k / n; return q < 1 ? 20 / T * 6 * q * (1 - q) : 0; }); return Math.abs(totalX(cadena(r, repetir(r.length, 0)))); };
const [pxLento, pxRapido] = [veinte(4), veinte(0.25)];
assert.ok(pxRapido > 2 * pxLento, 'los mismos grados, más píxeles');
ok(`los mismos 20° son ${pxLento.toFixed(0)} px en 4 s (pico de 7.5 °/s) y ${pxRapido.toFixed(0)} px en 0.25 s (pico de 120 °/s)`);

// ---------- el filtro 1€ ----------
console.log('El filtro 1€');
near(OneEuro.alpha(2, 0.01), 0.1116, 0.0001, 'α a 2 Hz');
near(OneEuro.alpha(12, 0.01), 0.4298, 0.0001, 'α a 12 Hz');
ok(`a 100 muestras por segundo, α = ${OneEuro.alpha(2, 0.01).toFixed(3)} con f_c = 2 Hz y ${OneEuro.alpha(12, 0.01).toFixed(3)} con f_c = 12 Hz`);
const hz = 100, dt = 1 / hz, temblor = (n) => Array.from({ length: n }, () => 1.5 * normal());
const f = (x, filtro) => x.map((v) => filtro(v));
const fijo = (fc) => { let y = null; const a = OneEuro.alpha(fc, dt); return (x) => (y = y === null ? x : y + a * (x - y)); };
const euro = (b) => { const e = new OneEuro(2, b, 1); return (x) => e.paso(x, dt); };
const ruido = temblor(3000);
const [rFijo, rEuro] = [tamano(f(ruido, fijo(2)).slice(100)), tamano(f(ruido, euro(0.01)).slice(100))];
assert.ok(rEuro < tamano(ruido) / 2, 'quieto el filtro baja el temblor');
const escalon = ruido.slice(0, 200).map((v, k) => v + (k >= 50 ? 100 : 0));
const llega = (y) => (y.findIndex((v, k) => k >= 50 && v > 63) - 50) * dt * 1000;
const [tFijo, tEuro] = [llega(f(escalon, fijo(2))), llega(f(escalon, euro(0.01)))];
assert.ok(tEuro < tFijo / 2, 'el 1€ llega antes');
ok(`temblor de ${tamano(ruido).toFixed(2)} °/s: fijo a 2 Hz deja ${rFijo.toFixed(2)}, 1€ deja ${rEuro.toFixed(2)}; al arrancar a 100 °/s, el fijo tarda ${tFijo.toFixed(0)} ms y el 1€ ${tEuro.toFixed(0)} ms`);
// la frecuencia de corte: τ = 1/(2π f_c) y α = Δt/(τ + Δt); lo más lento que f_c pasa, lo más rápido se achica
const tau = (fc) => 1 / (2 * Math.PI * fc);
for (const fc of [1, 2, 12]) near(OneEuro.alpha(fc, dt), dt / (tau(fc) + dt), 1e-12, `α = Δt/(τ + Δt) a ${fc} Hz`);
near(tau(2) * 1000, 80, 0.5, 'a 2 Hz, τ = 80 ms');
near(tFijo, tau(2) * 1000, 15, 'el corte fijo llega al 63 % en un τ');
const pasa = (hzSeno) => { const y = f(Array.from({ length: 2000 }, (_, k) => Math.sin(2 * Math.PI * hzSeno * k * dt)), fijo(2)).slice(1000); return Math.max(...y); };
assert.ok(pasa(0.5) > 0.9 && pasa(10) < 0.3, `a 0.5 Hz pasa ${pasa(0.5).toFixed(2)}, a 10 Hz ${pasa(10).toFixed(2)}`);
ok(`τ = 1/(2π f_c): ${(tau(2) * 1000).toFixed(0)} ms a 2 Hz, y α = Δt/(τ + Δt); una oscilación de 0.5 Hz pasa ${(100 * pasa(0.5)).toFixed(0)} %, una de 10 Hz ${(100 * pasa(10)).toFixed(0)} %`);

// ---------- calibrar los dos ejes ----------
console.log('Calibrar los dos ejes');
dice(fuente('README.md'), '5.3 mm de trazo por grado de yaw y 6.9 por grado de pitch, con los ejes cruzados (75° entre sí)', 'README.md');
const A = [[5.3, 6.9 * Math.cos(75 * GRADO)], [0, 6.9 * Math.sin(75 * GRADO)]];      // columnas: un grado de yaw y uno de pitch
const det = A[0][0] * A[1][1] - A[0][1] * A[1][0], inv = [[A[1][1] / det, -A[0][1] / det], [-A[1][0] / det, A[0][0] / det]];
const por = (B, v) => [B[0][0] * v[0] + B[0][1] * v[1], B[1][0] * v[0] + B[1][1] * v[1]];
near(6.9 / 5.3, 1.3, 0.005, 'la vertical necesita ×1.3');
// un círculo del dedo: los ángulos que lo hacen son inv·c; el cursor los recibe, y lo que importa es qué tan redondo sale
const razon = (B) => { const r = Array.from({ length: 3600 }, (_, i) => Math.hypot(...por(B, por(inv, [Math.cos(i * GRADO / 10), Math.sin(i * GRADO / 10)])))); return Math.max(...r) / Math.min(...r); };
const I2 = [[1, 0], [0, 1]];
near(razon(I2), 1.46, 0.01, 'hoy el cursor recibe yaw y pitch tal cual: sale elipse');
near(razon(A), 1, 1e-9, 'con M, el cursor copia el círculo del dedo');
assert.ok(razon(inv) > razon(I2), 'con la inversa saldría peor que hoy');
const circulo = Array.from({ length: 360 }, (_, i) => Math.hypot(...por(A, [Math.cos(i * GRADO), Math.sin(i * GRADO)])));
ok(`con 5.3 y 6.9 mm/° a 75°: ×${(6.9 / 5.3).toFixed(2)} en vertical; un círculo de la muñeca sale con radios de ${Math.min(...circulo).toFixed(1)} a ${Math.max(...circulo).toFixed(1)} mm, y para copiar el círculo del dedo el cursor tiene que usar M: razón de ejes ${razon(I2).toFixed(2)} hoy, ${razon(A).toFixed(2)} con M, ${razon(inv).toFixed(2)} con la inversa`);
const cal = fuente('server', 'web', 'calibrate.js');
dice(cal, 'if (rV > 1.3 && V.reentriesPerTrial <= 0.5 && V.medOvershootW <= 0.5) {', 'calibrate.js');
dice(cal, "prop('gain_y', val('gain_y') * Math.min(rV, 1.5)", 'calibrate.js');
ok('`suggest` propone más ganancia vertical si tarda más de ×1.3 sin pasarse, y sube a lo sumo ×1.5');

// ---------- potencias, logaritmos y Fitts ----------
console.log('Potencias, logaritmos y Fitts');
near(2 ** 10, 1024, 0, 'duplicar diez veces'); near(Math.log2(1024), 10, 1e-12, 'el logaritmo cuenta'); near(Math.log2(3), 1.585, 0.0005, 'no hace falta que sea entero');
near(Math.log2(8 * 4), Math.log2(8) + Math.log2(4), 1e-12, 'multiplicar es sumar');
ok(`2^10 = 1024, log2(1024) = 10, log2(3) = ${Math.log2(3).toFixed(3)}, y log2(8·4) = 3 + 2`);
near(2 ** 0.5, 1.414, 0.0005, 'media duplicación'); near((2 ** 0.5) ** 2, 2, 1e-12, 'dos medias son una');
near(2 ** (1 / 12), 1.0595, 0.00005, 'un doceavo'); near((2 ** (1 / 12)) ** 12, 2, 1e-12, 'doce doceavos son una');
near(2 ** -1, 0.5, 0, 'hacia atrás se divide'); near(Math.E, 2.718, 0.0005, 'la base e');
near(Math.log(2), 0.693, 0.0005, 'ln 2'); near(Math.exp(Math.log(2)), 2, 1e-12, 'e a la ln 2 da 2');
for (const x of [3, 37, 0.2]) near(Math.log(x), Math.log(2) * Math.log2(x), 1e-12, 'ln x = ln 2 · log2 x');
ok(`2^(1/2) = ${(2 ** 0.5).toFixed(3)}, 2^(1/12) = ${(2 ** (1 / 12)).toFixed(4)}, 2^(−1) = 0.5, e = ${Math.E.toFixed(3)}, ln 2 = ${Math.log(2).toFixed(3)} y ln x = ${Math.log(2).toFixed(3)}·log2 x`);
dice(cal, 'const ID = Math.log2(trial.D / W + 1);', 'calibrate.js');
dice(cal, 'ID, TP: ID / (MT / 1000),', 'calibrate.js');
const ID = (d, w) => Math.log2(d / w + 1);
near(ID(300, 100), 2, 1e-12, 'D = 3W'); near(ID(700, 100), 3, 1e-12, 'D = 7W');
near(ID(1500, 100), 4, 1e-12, 'D = 15W'); near(ID(600, 200), ID(300, 100), 1e-12, 'solo importa D/W');
ok('ID = 2, 3 y 4 bits con D/W = 3, 7 y 15; y agrandar todo por igual no cambia nada');

// ---------- el ejercicio ----------
const delCurso = (Dm, sep) => Math.cbrt(3 * sep / Dm) / GRADO;
function probar(fn, nombre) {
  console.log(`¿A qué ángulo se separan? (${nombre})`);
  const g = fn(2.4, 0.01);
  assert.ok(g > 12.5 && g < 13.8, `con D = 2.4 m y 1 cm tienen que salir unos 13° (salió ${g})`);
  ok(`D = 2.4 m, 1 cm: ${g.toFixed(1)}°`);
  for (const [Dm, sep] of [[2.4, 0.01], [2.4, 0.03], [0.6, 0.01], [5, 0.02]]) {
    const real = separacion(Dm, sep), tuyo = fn(Dm, sep);
    near(tuyo, real, 0.6, `D = ${Dm} m, ${sep * 100} cm: lo que da cursorTrack`);
    ok(`D = ${Dm} m, ${sep * 100} cm: tu ${tuyo.toFixed(1)}°, y con \`cursorTrack\` ${real.toFixed(1)}°`);
  }
  near(fn(4.8, 0.01) / fn(2.4, 0.01), Math.cbrt(0.5), 0.02, 'duplicar la distancia');
  ok('el doble de distancia separa antes: el ángulo se divide por ∛2');
}
if (process.argv.includes('--ejercicio')) {
  probar(require(path.join(raiz, 'docs', 'curso', 'ejercicios', 'cap07.js')).anguloDeSeparacion, 'tu ejercicio');
} else {
  probar(delCurso, 'del curso');
}
console.log('\nTodo pasa.');
