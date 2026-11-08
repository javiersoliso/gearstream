// Pruebas de la calibración del lienzo 2D (server/web/calibra.js): un barrido por el borde de la pantalla
// tiene que quedar dentro de la ventana, centrado y casi llenándola; un barrido chico no cambia nada.
//   node tools/test_calibra.js
'use strict';
const path = require('path');
const assert = require('assert');
const { calibrate, toScreen, DEFAULT_GAIN } = require(path.join(__dirname, '..', 'server', 'web', 'calibra.js'));

// rectángulos de 44° × 30° alrededor de (rumbo 12°, elevación −8°), con temblor y sobrepasos en las esquinas
function sweep(w, h, cx, cy, laps = 2, seed = 3) {
  let s = seed;
  const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647 - 0.5; };
  const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]], pts = [];
  for (let l = 0; l < laps; l++) {
    for (let c = 0; c < 4; c++) {
      const [a, b] = [corners[c], corners[c + 1]];
      for (let i = 0; i < 100; i++) {
        const u = i / 100, over = i > 90 ? 1.04 : 1;          // al llegar a la esquina se pasa un poco
        pts.push([cx + over * (a[0] + (b[0] - a[0]) * u) * w / 2 + 0.6 * rnd(), cy + over * (a[1] + (b[1] - a[1]) * u) * h / 2 + 0.6 * rnd()]);
      }
    }
  }
  return pts;
}

const W = 1920, H = 1080, pts = sweep(44, 30, 12, -8);
const cal = calibrate(pts, W, H);
assert.ok(cal, 'un barrido grande calibra');
assert.ok(Math.abs(cal.cx - 12) < 1 && Math.abs(cal.cy + 8) < 1, `centro (${cal.cx.toFixed(1)}, ${cal.cy.toFixed(1)}) ≈ (12, −8)`);
assert.ok(Math.abs(cal.kx - W * 0.88 / 44) / (W * 0.88 / 44) < 0.06, `kx ${cal.kx.toFixed(1)} ≈ ${(W * 0.88 / 44).toFixed(1)} px/°`);
assert.ok(Math.abs(cal.ky - H * 0.88 / 30) / (H * 0.88 / 30) < 0.06, `ky ${cal.ky.toFixed(1)} ≈ ${(H * 0.88 / 30).toFixed(1)} px/°`);
const xy = pts.map(([y, p]) => toScreen(y - cal.cx, p - cal.cy, cal, W, H));
const xs = xy.map((p) => p[0]).sort((a, b) => a - b), ys = xy.map((p) => p[1]).sort((a, b) => a - b);
const inside = xy.filter(([x, y]) => x >= 0 && x <= W && y >= 0 && y <= H).length / xy.length;
assert.ok(inside > 0.97, `el barrido queda en la ventana (${(100 * inside).toFixed(1)} %)`);
assert.ok(xs[xs.length - 1] - xs[0] > 0.85 * W && ys[ys.length - 1] - ys[0] > 0.85 * H, 'y casi la llena');
console.log(`barrido 44°×30° → ${cal.kx.toFixed(1)} × ${cal.ky.toFixed(1)} px/°, ${(100 * inside).toFixed(1)} % dentro de ${W}×${H}`);

assert.strictEqual(calibrate(sweep(5, 30, 0, 0), W, H), null, 'casi sin rumbo: no calibra');
assert.strictEqual(calibrate(pts.slice(0, 10), W, H), null, 'muy pocas muestras: no calibra');
assert.deepStrictEqual(toScreen(0, 0, DEFAULT_GAIN, W, H), [W / 2, H / 2], 'el centro va al centro');
assert.ok(toScreen(0, 10, DEFAULT_GAIN, W, H)[1] < H / 2, 'arriba es arriba');
assert.ok(calibrate(sweep(400, 300, 0, 0), W, H).kx >= 4 && calibrate(sweep(1, 1, 0, 0).concat(sweep(9, 9, 0, 0)), W, H).kx <= 80, 'ganancias acotadas');
console.log('OK');
