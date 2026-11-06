// Pruebas del capítulo 0 del curso (Un número que cambia): lo que el capítulo afirma, comprobado con señales
// inventadas donde la respuesta se conoce. Las pruebas de la interpolación corren también contra tu ejercicio.
//   node tools/test_muestreo.js              # la cuenta del curso
//   node tools/test_muestreo.js --ejercicio  # tu interpolación, en docs/curso/ejercicios/cap00.js
// Solo necesita node. Si además hay python, compara con el código de verdad: Bridge.map_time, norm y np.interp.
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { spawnSync } = require('child_process');

const RAIZ = path.join(__dirname, '..');
const WEB = path.join(RAIZ, 'server', 'web');
const S = require(path.join(WEB, 'sismomath.js'));
const { FlickDetector } = require(path.join(WEB, 'flick.js'));
const musica = {};
new Function('self', fs.readFileSync(path.join(WEB, 'musica.js'), 'utf8'))(musica);

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
const omitida = (msg) => console.log(`  - omitida: ${msg}`);

// números al azar repetibles
let estado = 12345;
const u = () => { estado = (estado * 16807) % 2147483647; return estado / 2147483647; };
const normal = () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u());

// python, si lo hay: corre `codigo` con `entrada` por stdin y devuelve lo que imprime en JSON
function enPython(codigo, entrada) {
  for (const py of [process.env.PYTHON, 'python', 'python3'].filter(Boolean)) {
    const r = spawnSync(py, ['-I', '-c', codigo], { input: JSON.stringify(entrada), encoding: 'utf8', cwd: RAIZ, maxBuffer: 1 << 26 });
    if (!r.error && r.status === 0) return JSON.parse(r.stdout);
  }
  return null;
}

// ---------- interpolar: la del curso ----------
function interpolarDelCurso(t, ts, xs) {
  const n = ts.length;
  if (t <= ts[0]) return xs[0];
  if (t >= ts[n - 1]) return xs[n - 1];
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (ts[m] <= t) lo = m; else hi = m; }
  return xs[lo] + (t - ts[lo]) / (ts[lo + 1] - ts[lo]) * (xs[lo + 1] - xs[lo]);
}

// ---------- unidades ----------
console.log('Unidades');
near(300 / 360, 0.83, 0.005, '300 °/s en vueltas por segundo');
near(300 / 360 * 60, 50, 1e-9, '300 °/s en vueltas por minuto');
ok('300 °/s son 0.83 vueltas/s y 50 vueltas por minuto');
const flick = new FlickDetector();
flick.beats = [0, 500, 1000, 1500];
near(flick.tempo(), 120, 1e-9, 'un giro cada 500 ms');
ok('FlickDetector.tempo: un giro cada 500 ms son 120 por minuto');

// ---------- muestreo ----------
console.log('Muestreo y marcas de tiempo');
const comps = S.makeTarget(1, (() => { let e = 2027; return () => { e = (e * 16807) % 2147483647; return e / 2147483647; }; })());
const onda = (t) => S.wave(comps, t);
const pierde = (f) => {
  const ts = Array.from({ length: 6 * f + 1 }, (_, k) => k / f), xs = ts.map((t) => onda(3 * t + 3));
  let peor = 0;
  for (let i = 0; i <= 1200; i++) { const t = i * 6 / 1200; peor = Math.max(peor, Math.abs(interpolarDelCurso(t, ts, xs) - onda(3 * t + 3))); }
  return peor;
};
assert.ok(pierde(1) > pierde(2) && pierde(2) > pierde(5) && pierde(5) > pierde(20), 'más muestras, menos se pierde');
ok(`más muestras, menos se pierde: ${[1, 2, 5, 20].map((f) => `${f} Hz → ${pierde(f).toFixed(3)}`).join(', ')}`);

const f2 = 2, tk = Array.from({ length: 13 }, (_, k) => k / f2);
const otra = (t) => onda(3 * t + 3) + 0.42 * Math.sin(2 * Math.PI * f2 * t);
for (const t of tk) near(otra(t), onda(3 * t + 3), 1e-9, 'la otra señal pasa por las mismas muestras');
assert.ok(Math.abs(otra(0.125) - onda(3 * 0.125 + 3)) > 0.4, 'y entre medio es distinta');
ok('dos señales distintas pueden tener exactamente las mismas muestras');

const dts = Array.from({ length: 450 }, () => 10 + Math.round(normal()));
const tiempos = []; dts.reduce((a, d) => { tiempos.push(a); return a + d; }, 0);
const quedan = tiempos.filter((t) => !(t > 1500 && t < 2000) && t <= 4000);
const hueco = Math.max(...quedan.slice(1).map((t, k) => t - quedan[k]));
assert.ok(hueco >= 500, `el hueco se ve en Δt (${hueco} ms)`);
assert.ok((quedan.length - 1) * 10 < quedan[quedan.length - 1] - 400, 'contando muestras se termina antes de tiempo');
ok(`se pierde medio segundo: contando muestras se llega a ${((quedan.length - 1) / 100).toFixed(2)} s, la hora dice ${(quedan[quedan.length - 1] / 1000).toFixed(2)} s`);

function probar(interpolar, nombre) {
  console.log(`Interpolar (${nombre})`);
  const ts = [0, 10, 30, 35, 80], xs = [1, 3, -1, 4, 4];
  ts.forEach((t, k) => near(interpolar(t, ts, xs), xs[k], 1e-12, `en la muestra ${k} da la muestra`));
  ok('en cada muestra da justo la muestra');
  near(interpolar(5, ts, xs), 2, 1e-12, 'a mitad de camino da el punto medio');
  near(interpolar(20, ts, xs), 1, 1e-12, 'con muestras disparejas la cuenta usa su propio Δt');
  near(interpolar(-5, ts, xs), 1, 1e-12, 'antes de la primera da la primera');
  near(interpolar(99, ts, xs), 4, 1e-12, 'después de la última da la última');
  ok('entre muestras sigue la recta, con Δt disparejos, y en los extremos se queda en la primera o la última');

  const tt = [], xx = [];
  let a = 0;
  for (let k = 0; k < 500; k++) { a += 5 + 10 * u(); tt.push(a); xx.push(normal()); }
  const pedidos = Array.from({ length: 1000 }, () => -20 + (a + 40) * u());
  const mios = pedidos.map((t) => interpolar(t, tt, xx));
  pedidos.forEach((t, k) => near(mios[k], interpolarDelCurso(t, tt, xx), 1e-9, `en t = ${t}`));
  ok('coincide con la cuenta del curso en mil instantes al azar');
  const np = enPython('import json,sys\ntry:\n import numpy as np\nexcept ImportError:\n print("null"); sys.exit()\nd=json.load(sys.stdin)\nprint(json.dumps(np.interp(d["t"],d["ts"],d["xs"]).tolist()))',
    { t: pedidos, ts: tt, xs: xx });
  if (np) { np.forEach((v, k) => near(mios[k], v, 1e-9, `np.interp en t = ${pedidos[k]}`)); ok('y con np.interp de verdad en esos mil instantes'); }
  else omitida('no hay python con numpy para comparar con np.interp');
}

// qué tan bien adivina la recta: un movimiento de ±100 que va y viene 2 veces por segundo
console.log('Qué tan bien adivina la recta');
const fallaA = (hz) => {
  const ts = Array.from({ length: 2 * hz + 1 }, (_, k) => k / hz), xs = ts.map((t) => 100 * Math.sin(2 * Math.PI * 2 * t));
  let peor = 0;
  for (let i = 0; i <= 20000; i++) { const t = i / 10000; peor = Math.max(peor, Math.abs(interpolarDelCurso(t, ts, xs) - 100 * Math.sin(2 * Math.PI * 2 * t))); }
  return peor;
};
near(fallaA(100), 0.2, 0.01, 'a 100 Hz la recta se equivoca 0.2');
near(fallaA(20), 4.9, 0.05, 'a 20 Hz se equivoca 4.9');
ok(`±100 que va y viene 2 veces por segundo: la recta falla hasta ${fallaA(100).toFixed(2)} a 100 Hz y ${fallaA(20).toFixed(2)} a 20 Hz`);

// ---------- cuantizar ----------
console.log('Cuantizar');
for (const q of [0.25, 0.1, 0.05]) {
  let peor = 0;
  for (let i = 0; i < 6000; i++) { const x = onda(i / 1000 + 3); peor = Math.max(peor, Math.abs(Math.round(x / q) * q - x)); }
  assert.ok(peor <= q / 2 + 1e-12, `el error no pasa de medio escalón (${peor} con ${q})`);
}
ok('redondeando, el error nunca pasa de medio escalón');
const franja = (v) => musica.ratiosOf(1, [0, (1 - v) * 100], [100, 100])[0];
assert.deepStrictEqual([0, 0.13, 0.26, 0.5, 0.9, 1].map(franja), [1, 2, 3, 5, 8, 8], 'las franjas de musica.js');
assert.strictEqual(new Set(Array.from({ length: 1001 }, (_, i) => franja(i / 1000))).size, 8, 'ocho valores');
ok('musica.js: de 0 a 1 salen ocho valores, del 1 al 8');
// norm de tools/air_mouse.py: píxel → 0..65535 y de vuelta
const norm = (px, origen, tam) => Math.max(0, Math.min(65535, Math.ceil((px - origen) * 65536 / Math.max(1, tam))));
for (const tam of [1366, 1920, 2560, 3840]) for (let px = 0; px < tam; px++) assert.strictEqual(Math.floor(norm(px, 0, tam) * tam / 65536), px, `píxel ${px} de ${tam}`);
near(65536 / 1920, 34, 0.2, '34 escalones por píxel');
ok('norm: a 1920 píxeles hay 34 escalones por píxel y todos los píxeles vuelven a su sitio');
assert.strictEqual(norm(960, 0, 1920), 32768, 'la mitad de la pantalla');

// ---------- lecturas nuevas ----------
console.log('Lecturas nuevas');
const lecturas = Array.from({ length: 200 }, (_, k) => Math.floor(k / 200 * 115 + 1e-9));   // la última renovación del sensor
assert.strictEqual(new Set(lecturas).size, 115, '115 lecturas distintas');
ok('si el sensor se renueva 115 veces por segundo, 200 muestras traen 115 lecturas nuevas');
// analyze_drawing.py cuenta filas distintas en toda la grabación: un valor que vuelve no cuenta otra vez
const cambios = (x) => 1 + x.slice(1).filter((v, k) => v !== x[k]).length, distintas = (x) => new Set(x).size;
assert.strictEqual(cambios([1, 1, 2, 2, 3]), distintas([1, 1, 2, 2, 3]), 'sin valores que vuelvan son lo mismo');
assert.ok(distintas([1, 2, 1, 2]) < cambios([1, 2, 1, 2]), 'un valor que vuelve se cuenta una sola vez');
ok('contar filas distintas (np.unique) y contar cambios solo difieren si un valor exacto vuelve');

// ---------- resumir una ventana ----------
console.log('Resumir una ventana');
const mediana = (x) => { const s = [...x].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const promedio = (x) => x.reduce((a, b) => a + b, 0) / x.length;
const ventana = Array.from({ length: 21 }, () => 3 + 0.45 * normal()), rara = [...ventana];
rara[ventana.indexOf(Math.max(...ventana))] = 11.5;
assert.ok(promedio(rara) - promedio(ventana) > 0.3, 'un valor raro arrastra el promedio');
near(mediana(rara), mediana(ventana), 1e-12, 'y no mueve la mediana');
ok(`un valor raro sube el promedio ${(promedio(rara) - promedio(ventana)).toFixed(2)} y no mueve la mediana`);
const corto = Array.from({ length: 100 }, (_, k) => (k >= 40 && k < 50 ? 80 : 0));
assert.strictEqual(mediana(corto), 0, 'la mediana no ve un suceso corto');
assert.strictEqual(Math.max(...corto), 80, 'el máximo sí');
ok('la mediana no ve un suceso de 0.1 s en un segundo; el pico a pico sí');
flick.beats = [0, 500, 1000, 4000, 4500, 5000, 5500];
near(flick.tempo(), 120, 1e-9, 'una pausa rara no cambia los giros por minuto');
ok('FlickDetector.tempo usa la mediana: una pausa rara en medio no cambia el resultado');

// ---------- latencia y relojes ----------
console.log('Latencia y relojes');
const fuente = fs.readFileSync(path.join(RAIZ, 'tools', 'sdb_bridge.py'), 'utf8');
const FUGA = Number(fuente.match(/^OFFSET_LEAK_MS = ([\d.]+)/m)[1]), SALTO = Number(fuente.match(/^MAX_TS_JUMP_MS = (\d+)/m)[1]);
assert.strictEqual(FUGA, 0.0003, 'la fuga del capítulo');
assert.strictEqual(SALTO, 5000, 'el salto del capítulo');
// Bridge.map_time, línea por línea
function mapTime(b, sensor, tsMs, ahoraMs) {
  const prev = b.last[sensor];
  if (prev !== undefined && Math.abs(tsMs - prev) > SALTO) return Math.round(ahoraMs);
  b.last[sensor] = tsMs;
  const offset = ahoraMs - tsMs, cur = b.offsets[sensor];
  b.offsets[sensor] = cur === undefined || offset < cur ? offset : cur + FUGA;
  return Math.round(tsMs + b.offsets[sensor]);
}
const DESFASE = 1.7e9;
const med = Array.from({ length: 150 }, (_, k) => 1000 + 10 * k);
const lat = med.map((_, k) => (k < 12 ? 145 - 2 * k : k === 97 ? 9 : 14 + 40 * u()));
const b = { last: {}, offsets: {} };
const pasos = med.map((t, k) => { const a = t + DESFASE + lat[k]; mapTime(b, 'G', t, a); return { t, a, off: b.offsets.G }; });
near(b.offsets.G, DESFASE + 9, 53 * FUGA + 1e-6, 'el desfase se queda en la entrega más rápida más la fuga');
near(pasos[0].off, DESFASE + 145, 1e-6, 'la primera muestra da la entrega más lenta');
ok(`el mínimo queda ${(b.offsets.G - DESFASE).toFixed(3)} ms sobre el desfase de verdad; anclar en la primera daría ${lat[0]} ms`);
const antes = b.offsets.G, hora = 3 * 3600 * 1000;
const llega = med[149] + 10 + DESFASE + 30;
assert.strictEqual(mapTime(b, 'G', med[149] + hora, llega), Math.round(llega), 'se marca con su llegada');
assert.strictEqual(b.offsets.G, antes, 'un salto de horas no mueve el ancla');
ok('una marca de 3 horas de más no mueve el desfase y se marca con la hora de llegada');
near(FUGA * 100 * 60, 1.8, 1e-9, 'la fuga son 1.8 ms por minuto a 100 Hz');
ok('la fuga de 0.0003 ms por muestra son 1.8 ms por minuto a 100 Hz');

const mt = enPython([
  'import ast,json,sys,types',
  'a=ast.parse(open("tools/sdb_bridge.py",encoding="utf-8").read())',
  'env={n.targets[0].id:ast.literal_eval(n.value) for n in a.body if isinstance(n,ast.Assign) and getattr(n.targets[0],"id","") in ("OFFSET_LEAK_MS","MAX_TS_JUMP_MS")}',
  'c=next(n for n in a.body if isinstance(n,ast.ClassDef) and n.name=="Bridge")',
  'm=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=="map_time")',
  'r=types.SimpleNamespace(s=0.0); r.time=lambda:r.s; env["time"]=r',
  'exec(compile(ast.Module([m],[]),"x","exec"),env)',
  'b=types.SimpleNamespace(last_ts_ms={},offsets_ms={})',
  'out=[]',
  'for t,now in json.load(sys.stdin):',
  '    r.s=now/1000; env["map_time"](b,"G",t); out.append(b.offsets_ms["G"])',
  'print(json.dumps(out))'].join('\n'), pasos.map((p) => [p.t, p.a]));
if (mt) { mt.forEach((v, k) => near(v, pasos[k].off, 1e-3, `Bridge.map_time en la muestra ${k}`)); ok('coincide con Bridge.map_time de verdad, muestra por muestra'); }
else omitida('no hay python para comparar con Bridge.map_time');
const nm = enPython('import json,sys\nsys.path.insert(0,"tools")\nimport air_mouse\nprint(json.dumps([air_mouse.norm(p,0,1920) for p in json.load(sys.stdin)]))', Array.from({ length: 1920 }, (_, i) => i));
if (nm) { nm.forEach((v, p) => assert.strictEqual(v, norm(p, 0, 1920), `norm(${p})`)); ok('norm coincide con la de tools/air_mouse.py en los 1920 píxeles'); }
else omitida('no hay python para comparar con norm');

// AirMouse.on_data: la línea de base baja de golpe y sube a lo sumo 30 ms por segundo
const air = fs.readFileSync(path.join(RAIZ, 'tools', 'air_mouse.py'), 'utf8');
const SUBE = Number(air.match(/^BASELINE_RISE_MS_PER_S = ([\d.]+)/m)[1]), VIEJA = Number(air.match(/^STALE_MS, FRESH_MS, GAP_MS, GAP_BLANK_MS = (\d+)/m)[1]);
assert.strictEqual(SUBE, 30, 'sube 30 ms por segundo'); assert.strictEqual(VIEJA, 300, 'vieja desde 300 ms');
let base = null, ant = 0;
const lag = (edad, ahora) => { base = base === null ? edad : Math.min(edad, base + SUBE * Math.max(0, ahora - ant) / 1000); ant = ahora; return edad - base; };
for (let a = 0; a < 1000; a += 50) lag(40, a);
assert.ok(lag(400, 1000) > VIEJA, 'tras un atasco, la muestra de 400 ms pasa de 300 de más');
ok('una muestra que llega 360 ms más vieja de lo normal pasa de los 300 ms y no mueve el cursor');

// ---------- agrupar ----------
console.log('Agrupar muestras');
// cada ida y vuelta sale un paquete con hasta N de lo que el reloj ya juntó
function simular(N, rtt, dt, dur) {
  let hechas = 0, pasan = 0, peor = 0;
  const hora = [];
  for (let t = 0; t <= dur; t += 1) {
    if (t % dt === 0) { hora.push(t); hechas++; }
    if (t % rtt === 0 && t > 0) {
      const juntas = Math.floor(hechas / N) * N;        // el awk suelta de a N líneas
      const salen = Math.min(N, juntas - pasan);
      for (let i = 0; i < salen; i++) peor = Math.max(peor, t - hora[pasan + i]);
      pasan += salen;
    }
  }
  return { porSegundo: pasan / (dur / 1000), peor };
}
near(simular(1, 60, 10, 60000).porSegundo, 1000 / 60, 0.1, 'un paquete cada 60 ms deja pasar 17 por segundo');
near(simular(6, 60, 10, 60000).porSegundo, 100, 0.5, 'con 6 por paquete pasan las 100');
ok(`un paquete cada 60 ms: N = 1 deja pasar ${simular(1, 60, 10, 60000).porSegundo.toFixed(1)} por segundo, N = 6 deja ${simular(6, 60, 10, 60000).porSegundo.toFixed(1)}`);
assert.ok(simular(6, 60, 10, 60000).peor <= 60, 'la que más espera no pasa de (N − 1)·Δt más el turno de salir');
ok(`con N = 6, la que más espera lleva ${simular(6, 60, 10, 60000).peor} ms cuando sale: (N − 1)·Δt más el turno de salir`);

if (process.argv.includes('--ejercicio')) {
  probar(require(path.join(RAIZ, 'docs', 'curso', 'ejercicios', 'cap00.js')).interpolar, 'tu ejercicio');
} else {
  probar(interpolarDelCurso, 'del curso');
}
console.log('\nTodo pasa.');
