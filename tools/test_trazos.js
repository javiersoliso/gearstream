// Pruebas del formato de los dibujos (server/web/trazos.js): aplicar, deshacer, guardar y leer, rescatar y
// reproducir tienen que dar exactamente el mismo dibujo.
//   node tools/test_trazos.js
'use strict';
const path = require('path');
const assert = require('assert');
const { parseDrawing, toJSONL, Drawing, timeline, modesOf } = require(path.join(__dirname, '..', 'server', 'web', 'trazos.js'));

function render(ops) {                     // aplica todo y cuenta bolitas como lo haría la página
  let blobs = [];
  const d = new Drawing({ blob: (q, c) => blobs.push([...q, c]), truncate3: (n) => { blobs = blobs.slice(0, n); } });
  for (const op of ops) d.apply(op);
  return { d, blobs };
}

const ops = [
  { k: 'h', v: 1, start: '2026-10-29T01:00:00.000Z', hand: 'right', view: [1920, 1080] },
  { k: 's', id: 1, m: 3, c: '#58c4dd', t: 0 },
  { k: 'p', id: 1, pts: [[0, 0, -3, 0], [0.1, 0, -3, 10], [0.1, 0, -3, 20]] },   // 10 cm: 5 bolitas de relleno; el punto repetido no añade
  { k: 's', id: 2, m: 2, c: '#ffd166', t: 3000 },
  { k: 'p', id: 2, pts: [[100, 100, 3000], [120, 130, 3016]] },
  { k: 's', id: 3, m: 3, c: '#f0997b', t: 9000 },
  { k: 'p', id: 3, pts: [[1, 1, -3, 9000], [1, 1.04, -3, 9010]] },
  { k: 'z', m: 3, t: 9500 },                                                     // deshace el trazo 3 entero
];
let r = render(ops);
assert.strictEqual(r.blobs.length, 6, `3D: 1 + 5 bolitas de relleno (${r.blobs.length})`);
assert.ok(r.blobs.every((b) => b[3] === '#58c4dd'), 'las bolitas llevan el color de su trazo');
assert.strictEqual(r.d.s2.length, 1); assert.deepStrictEqual(r.d.s2[0].pts, [[100, 100], [120, 130]]);
assert.deepStrictEqual(modesOf(ops), [2, 3]);
assert.strictEqual(render([...ops, { k: 'c', t: 10000 }]).blobs.length, 0, 'borrar deja todo vacío');

// guardar y leer da lo mismo
const back = parseDrawing(toJSONL(ops));
assert.deepStrictEqual(back, ops, 'JSON Lines ida y vuelta');

// reproducir punto a punto da el mismo dibujo, y las pausas largas se acortan
const ev = timeline(ops, 400);
const rr = render(ev.map((e) => e.op));
assert.deepStrictEqual(rr.blobs, r.blobs, 'la reproducción da las mismas bolitas');
assert.deepStrictEqual(rr.d.s2.map((s) => s.pts), r.d.s2.map((s) => s.pts), 'y los mismos trazos 2D');
assert.ok(ev[ev.length - 1].at <= 20 + 400 + 16 + 400 + 10 + 400 + 1, `pausas acortadas (${ev[ev.length - 1].at} ms)`);
for (let i = 1; i < ev.length; i++) assert.ok(ev[i].at >= ev[i - 1].at, 'el tiempo de reproducción no retrocede');

// rescate de la versión vieja: bolitas en orden, cortadas en trazos donde hay saltos
const rescue = JSON.stringify({
  format: 'gearstream-dibujo-rescate', view: [1920, 1080],
  blobs: [[0, 0, -3, '#ece9e1'], [0.02, 0, -3, '#ece9e1'], [0.04, 0, -3, '#ece9e1'], [2, 2, -3, '#ece9e1'], [2.02, 2, -3, '#ece9e1']],
  strokes2: [{ mode: 2, color: '#58c4dd', pts: [[1, 2], [3, 4]] }],
});
const ro = parseDrawing(rescue);
assert.strictEqual(ro.filter((o) => o.k === 's' && o.m === 3).length, 2, 'el salto de 2 m separa dos trazos');
const rescued = render(ro);
assert.strictEqual(rescued.blobs.length, 5, `las bolitas rescatadas son las mismas (${rescued.blobs.length})`);
assert.deepStrictEqual(rescued.d.s2[0].pts, [[1, 2], [3, 4]]);
console.log('OK');
