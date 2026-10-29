// Prueba del detector de giros con una sesión del dataset de gestos.
//   node tools/test_flick.js recordings/AAAAMMDD-HHMMSS
// En cada paso cuenta los giros, su sentido y el tempo, y lo compara con la frecuencia que da el
// espectro del giro x. En los pasos de giro rápido de muñeca deben salir dos giros por ciclo
// (uno en cada sentido, alternados); en reposo, teclear o el ratón, pocos.
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { FlickDetector } = require(path.join(__dirname, '..', 'server', 'web', 'flick.js'));

const folder = process.argv[2];
if (!folder) { console.error('uso: node tools/test_flick.js recordings/<sesión>'); process.exit(2); }
const rows = fs.readFileSync(path.join(folder, 'GYROSCOPE.csv'), 'utf8').trim().split(/\r?\n/).slice(1)
  .map((l) => l.split(',').map(Number)).map(([t, , x, y, z]) => [t, x, y, z]).sort((a, b) => a[0] - b[0]);
const labels = fs.readFileSync(path.join(folder, 'labels.jsonl'), 'utf8').trim().split(/\r?\n/).map((l) => JSON.parse(l))
  .filter((l) => !l.step.startsWith('_'));

function domFreq(seg) {                       // frecuencia dominante de ω_x entre 0.3 y 8 Hz (DFT directa)
  const n = seg.length, fs_ = 1000 / ((seg[n - 1][0] - seg[0][0]) / (n - 1));
  const m = seg.reduce((s, r) => s + r[1], 0) / n;
  let best = 0, bf = 0;
  for (let f = 0.3; f <= 8; f += 0.01) {
    let re = 0, im = 0;
    for (let i = 0; i < n; i++) { const a = 2 * Math.PI * f * i / fs_; re += (seg[i][1] - m) * Math.cos(a); im -= (seg[i][1] - m) * Math.sin(a); }
    const p = re * re + im * im;
    if (p > best) { best = p; bf = f; }
  }
  return bf;
}

const results = {};
for (const lab of labels) {
  const seg = rows.filter((r) => r[0] >= lab.t0 + 500 && r[0] <= lab.t1);
  if (seg.length < 50) continue;
  // sesgo: mediana del giro en reposo del propio paso no sirve si se mueve; se usa 0 (el sesgo de este reloj es < 0.3 °/s)
  const det = new FlickDetector();
  const flicks = [];
  for (const r of seg) { const f = det.update(r[0], [r[1], r[2], r[3]]); if (f) flicks.push(f); }
  const secs = (seg[seg.length - 1][0] - seg[0][0]) / 1000;
  const cw = flicks.filter((f) => f.dir > 0).length;
  const alt = flicks.slice(1).filter((f, i) => f.dir !== flicks[i].dir).length / Math.max(1, flicks.length - 1);
  const iv = flicks.slice(1).map((f, i) => f.t - flicks[i].t).sort((a, b) => a - b);
  const tempo = iv.length ? 60000 / iv[Math.floor(iv.length / 2)] : null;
  const fdom = domFreq(seg);
  results[lab.step] = { flicks: flicks.length, perMin: 60 * flicks.length / secs, cw, ccw: flicks.length - cw, alt, tempo, fdom };
  console.log(`${lab.step.padEnd(14)} ${String(flicks.length).padStart(3)} giros (${(60 * flicks.length / secs).toFixed(0).padStart(3)}/min) · horario ${cw} · antihorario ${flicks.length - cw} · alternan ${(100 * alt).toFixed(0)} %` +
    (tempo ? ` · tempo ${tempo.toFixed(0)} giros/min` : '') + ` · espectro de ω_x: ${fdom.toFixed(2)} Hz → ${(120 * fdom).toFixed(0)} giros/min si hay dos por ciclo`);
}

// en el giro rápido de muñeca: dos giros por ciclo, alternando sentido, y el tempo cuadra con el espectro
const r = results.muneca_rapida;
if (r) {
  assert.ok(r.alt > 0.8, 'en el giro rápido los sentidos deben alternar');
  assert.ok(Math.abs(r.tempo - 120 * r.fdom) / (120 * r.fdom) < 0.15, 'el tempo debe cuadrar con el espectro (±15 %)');
}
for (const quiet of ['reposo']) if (results[quiet]) assert.ok(results[quiet].flicks <= 1, `${quiet}: no debería haber giros`);
console.log('OK');
