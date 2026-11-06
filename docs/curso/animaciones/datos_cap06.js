// Los números de referencia de las animaciones del capítulo 6, de la cuenta de verdad (server/web/wrist.js: Wrist.rates).
// cap06.py lo corre y compara con estos casos su copia y las versiones en Python (Motion.feed_gyro y frame_rates).
//   node docs/curso/animaciones/datos_cap06.js
'use strict';
const path = require('path');
const { Wrist } = require(path.join(__dirname, '..', '..', '..', 'server', 'web', 'wrist.js'));
const { subida } = require(path.join(__dirname, '..', '..', '..', 'server', 'web', 'fusionmath.js'));

let s = 99;
const u = () => { s = (s * 16807) % 2147483647; return s / 2147483647 - 0.5; };
const casos = [];
for (let i = 0; i < 300; i++) {
  const w = [300 * u(), 300 * u(), 300 * u()], g0 = [u(), u(), u()], n = Math.hypot(...g0), g = g0.map((x) => 9.81 * x / n);
  for (const mano of ['left', 'right']) {
    const f = mano === 'left' ? [1, 0, 0] : [-1, 0, 0];
    casos.push({ w, g, mano, ...new Wrist(mano).rates(w, g), subida: subida(w, g, f) });
  }
}
process.stdout.write(JSON.stringify({ casos }));
