// Prueba de la calibración del clic por giro (server/web/clickcal.js) con lóbulos sintéticos donde la
// respuesta se conoce: tus giros deben pasar todos, el fondo (apuntar) ninguno.
//   node tools/test_clickcal.js
'use strict';
const path = require('path');
const assert = require('assert');
const { fitFlick, passesFlick } = require(path.join(__dirname, '..', 'server', 'web', 'clickcal.js'));

let seed = 3;
const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const lobe = (peak, ms, deg, sign, rho_ratio, quiet_ms) => ({ peak, ms, deg: sign * deg, sign, rho_ratio, quiet_ms });
const flickRound = (sign = 1) => [lobe(260 + 140 * rand(), 90 + 50 * rand(), 25 + 20 * rand(), sign, 0.05 + 0.15 * rand(), 300 + 500 * rand()),
                                  lobe(200 + 80 * rand(), 100 + 40 * rand(), 22 + 15 * rand(), -sign, 0.1, 0)];    // el giro y su vuelta
const pointing = () => Array.from({ length: 25 }, () => lobe(65 + 90 * rand(), 60 + 200 * rand(), 5 + 25 * rand(), rand() < 0.5 ? 1 : -1,
                                                               0.4 + 1.2 * rand(), 300 * rand()));

// giros horarios claros y un fondo de apuntar normal
let r = fitFlick(Array.from({ length: 8 }, () => flickRound(1)), pointing());
assert.ok(r.ok, 'con 8 giros claros la calibración sale');
assert.strictEqual(r.params.flick_dir, 'cw', 'siempre horario: solo el horario hace clic');
assert.strictEqual(r.detected, r.total, `todos tus giros pasan (${r.detected}/${r.total})`);
assert.strictEqual(r.falsos, 0, `apuntando, ningún clic falso (${r.falsos})`);
assert.ok(r.params.flick_thr >= 80 && r.params.flick_thr < Math.min(...r.mains.map((m) => m.peak)), 'el umbral queda bajo tu giro más flojo');
console.log('giros horarios:', JSON.stringify(r.params), `${r.detected}/${r.total} detectados, ${r.falsos} falsos`);

// la vuelta del giro nunca pasa: no sale de una muñeca quieta
for (const round of Array.from({ length: 8 }, () => flickRound(1))) assert.ok(!passesFlick(round[1], r.params), 'la vuelta no hace clic');

// giros antihorarios
r = fitFlick(Array.from({ length: 8 }, () => flickRound(-1)), pointing());
assert.strictEqual(r.params.flick_dir, 'ccw');

// mezclados: acepta los dos sentidos y lo avisa
r = fitFlick(Array.from({ length: 8 }, (_, i) => flickRound(i % 2 ? 1 : -1)), pointing());
assert.strictEqual(r.params.flick_dir, 'any');
assert.ok(r.warnings.length > 0);

// giros flojos que se confunden con apuntar: avisa
const weak = Array.from({ length: 8 }, () => [lobe(150 + 20 * rand(), 120, 20, 1, 0.1, 400)]);
const rough = [lobe(170, 110, 20, 1, 0.1, 400), ...pointing()];
r = fitFlick(weak, rough);
assert.ok(r.ok && r.warnings.some((w) => w.includes('clics falsos')), 'si tu fondo se parece a tu clic, lo dice');

// casi sin giros: no inventa umbrales
r = fitFlick(Array.from({ length: 8 }, (_, i) => (i < 2 ? flickRound(1) : [])), pointing());
assert.ok(!r.ok && r.warnings[0].includes('gira más rápido'));
console.log('OK');
