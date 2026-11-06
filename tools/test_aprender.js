// Pruebas del capítulo 12 del curso (Aprender de datos): lo que el capítulo afirma, comprobado con datos inventados
// donde la respuesta se conoce. Las pruebas de ridge corren también contra tu ejercicio.
//   node tools/test_aprender.js              # la cuenta del curso
//   node tools/test_aprender.js --ejercicio  # tu ridge, en docs/curso/ejercicios/cap12.js
//
// El código de verdad es Python (reconstruct_drawing.py, analyze_drawing.py, analyze_dataset.py) y aquí solo hay node,
// así que la cuenta se copia en JavaScript y se compara con REF: lo que dio Python para entradas pequeñas. REF sale de
// `python docs/curso/animaciones/datos_cap12.py --referencias`; si tools/ cambia, hay que rehacerlo.
'use strict';
const path = require('path');
const assert = require('assert');

const REF = {
  X: [[1.2, 30], [0.4, 12], [2.5, 41], [1.9, 38], [0.7, 9], [3.1, 60], [2.2, 35], [1.1, 20], [2.8, 44], [0.2, 15]],
  y: [4.1, 1.0, 7.2, 6.3, 1.9, 9.8, 6.0, 3.5, 7.9, 1.2],
  ridge: { 0.5: [1.5407443758823032, 1.2778812008542295, 4.890000000000001], 10: [0.9679191521783156, 0.9425277779795461, 4.890000000000001] },
  r2: 0.9941573058440707,
  coef: [1.7422811330096322, 0.07668648535964628, -0.24634177907875665],
  forma: { a: [[0, 0], [1, 2], [2, 3], [4, 3], [5, 1], [6, 0]], b: [[0, 0], [1.5, 1], [2.5, 2], [3, 2.5], [4, 1], [4.5, -1]], parecido: 0.9505251699961893 },
  gestos: {
    X: [[1, 2], [1.2, 2.2], [0.8, 1.9], [1.1, 3], [2, 2.5], [2.2, 2.4], [1.9, 2.9], [2.4, 2.1], [3, 1], [3.3, 1.2], [2.9, 0.8], [1.3, 2.3]],
    y: [0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2], pred: [0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 0],
    F: [9.059154929546846, 5.609907120722195], confusion: [[3, 1, 0], [0, 4, 0], [1, 0, 3]],
  },
  toques: { tramos: [[0, 200], [240, 400], [480, 600], [800, 816], [1700, 2000], [3000, 3100]], trazos: 4, grupos: [2, 1, 1] },
};

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);

// números al azar repetibles, con forma de campana
let estado = 12345;
const u = () => { estado = (estado * 16807) % 2147483647; return estado / 2147483647; };
const normal = () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u());
const barajar = (n) => { const p = [...Array(n).keys()]; for (let i = n - 1; i > 0; i--) { const j = Math.floor(u() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; } return p; };

// ---------- álgebra chica ----------
const suma = (x) => x.reduce((a, b) => a + b, 0);
const prom = (x) => suma(x) / x.length;
const desv = (x) => { const m = prom(x); return Math.sqrt(prom(x.map((v) => (v - m) ** 2))); };
const mediana = (x) => { const s = [...x].sort((a, b) => a - b), n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; };
const col = (A, j) => A.map((r) => r[j]);
const punto = (a, b) => suma(a.map((v, i) => v * b[i]));
const norma = (a) => Math.sqrt(punto(a, a));

function resolver(A, b) {                       // Gauss con pivote; b es un vector
  const n = A.length, M = A.map((r, i) => [...r, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let i = c + 1; i < n; i++) if (Math.abs(M[i][c]) > Math.abs(M[p][c])) p = i;
    [M[c], M[p]] = [M[p], M[c]];
    for (let i = c + 1; i < n; i++) {
      const f = M[i][c] / M[c][c];
      for (let j = c; j <= n; j++) M[i][j] -= f * M[c][j];
    }
  }
  const x = Array(n).fill(0);
  for (let i = n - 1; i >= 0; i--) x[i] = (M[i][n] - suma(M[i].slice(i + 1, n).map((v, j) => v * x[i + 1 + j]))) / M[i][i];
  return x;
}

const normales = (A) => A[0].map((_, i) => A[0].map((__, j) => punto(col(A, i), col(A, j))));

// R² como r2 de analyze_drawing.py, pero para cualquier predicción
const r2De = (v, p) => { const m = prom(v); return 1 - suma(v.map((a, i) => (a - p[i]) ** 2)) / suma(v.map((a) => (a - m) ** 2)); };

// mínimos cuadrados con término constante, como r2 de analyze_drawing.py: devuelve [coeficientes..., constante]
function minimos(X, y) {
  const A = X.map((r) => [...r, 1]);
  return resolver(normales(A), A[0].map((_, j) => punto(col(A, j), y)));
}

// Ridge.fit de reconstruct_drawing.py, con cualquier número de rasgos
function ridgeFit(X, y, lam) {
  const k = X[0].length, mu = [], sd = [];
  for (let j = 0; j < k; j++) { mu.push(prom(col(X, j))); sd.push(desv(col(X, j)) + 1e-9); }
  const Z = X.map((r) => [...r.map((v, j) => (v - mu[j]) / sd[j]), 1]);
  const A = normales(Z);
  for (let j = 0; j < k; j++) A[j][j] += lam;           // el término constante no se castiga
  const W = resolver(A, Z[0].map((_, j) => punto(col(Z, j), y)));
  return { W, predict: (Xn) => Xn.map((r) => punto([...r.map((v, j) => (v - mu[j]) / sd[j]), 1], W)) };
}

// ---------- ridge: lo que tiene que cumplir cualquiera que lo escriba ----------
function probarRidge(ridge, nombre) {
  console.log(`Ridge para dos rasgos (${nombre})`);
  for (const lam of [0.5, 10]) {
    const w = ridge(REF.X, REF.y, lam);
    assert.strictEqual(w.length, 3, 'devuelve [w1, w2, b]');
    REF.ridge[lam].forEach((v, i) => near(w[i], v, 1e-6, `λ = ${lam}: el número ${i} de Ridge.fit`));
  }
  ok('da lo mismo que Ridge.fit con λ = 0.5 y λ = 10');

  const casi = ridge(REF.X, REF.y, 1e-9), mc = minimos(REF.X, REF.y);
  const est = (j) => desv(col(REF.X, j));
  near(casi[0] / est(0), mc[0], 1e-5, 'λ → 0: el coeficiente 1 es el de mínimos cuadrados');
  near(casi[1] / est(1), mc[1], 1e-5, 'λ → 0: el coeficiente 2 es el de mínimos cuadrados');
  REF.coef.slice(0, 2).forEach((v, i) => near(casi[i] / est(i), v, 1e-5, `λ → 0: el coeficiente ${i + 1} de lstsq`));
  ok('con λ → 0 da mínimos cuadrados (lo mismo que lstsq en r2)');

  const enorme = ridge(REF.X, REF.y, 1e12);
  near(enorme[0], 0, 1e-8, 'λ enorme: w1 va a 0');
  near(enorme[1], 0, 1e-8, 'λ enorme: w2 va a 0');
  near(enorme[2], prom(REF.y), 1e-9, 'λ enorme: queda el promedio');
  ok(`con λ enorme los coeficientes van a 0 y queda solo el promedio (${prom(REF.y).toFixed(2)})`);

  for (const lam of [0, 1, 100, 1e6]) near(ridge(REF.X, REF.y, lam + 1e-12)[2], prom(REF.y), 1e-9, 'el término constante no se castiga');
  ok('el término constante no se castiga: siempre es el promedio de y');

  let antes = Infinity;
  for (const lam of [0.01, 0.1, 1, 10, 100, 1000]) {
    const w = ridge(REF.X, REF.y, lam), t = Math.hypot(w[0], w[1]);
    assert.ok(t < antes, `el tamaño de W baja con λ (${t} a λ = ${lam})`);
    antes = t;
  }
  ok('el tamaño de W baja cuando λ sube');

  // dos rasgos casi iguales: mínimos cuadrados los pone a pelear, ridge los calma
  const X = [], y = [];
  for (let i = 0; i < 60; i++) { const a = normal(); X.push([a + 0.02 * normal(), a + 0.02 * normal()]); y.push(a + 0.7 * normal()); }
  const sin = ridge(X, y, 1e-9), con = ridge(X, y, 10);
  assert.ok(Math.hypot(con[0], con[1]) < Math.hypot(sin[0], sin[1]) / 2, 'con rasgos casi iguales el castigo achica W');
  near(con[0], con[1], 0.15, 'con rasgos casi iguales ridge reparte parejo');
  ok(`con dos rasgos casi iguales: W pasa de (${sin[0].toFixed(1)}, ${sin[1].toFixed(1)}) a (${con[0].toFixed(2)}, ${con[1].toFixed(2)}) con λ = 10`);
}

if (process.argv.includes('--ejercicio')) {
  probarRidge(require(path.join(__dirname, '..', 'docs', 'curso', 'ejercicios', 'cap12.js')).ridge, 'tu ejercicio');
  console.log('\nTodo pasa.');
  process.exit(0);
}
probarRidge((X, y, lam) => ridgeFit(X, y, lam).W, 'del curso');

// ---------- rasgos ----------
console.log('Rasgos');
{
  const hz = 100, t = Array.from({ length: hz }, (_, i) => i / hz), x = t.map((s) => 20 * Math.sin(2 * Math.PI * 6 * s));
  near(Math.sqrt(prom(x.map((v) => v * v))), 20 / Math.SQRT2, 1e-9, 'el RMS de una onda es a/√2');
  // window_features saca la frecuencia del largo del giro, ya centrado: una muñeca que va y viene a 6 Hz sale en 12 Hz
  const largo = x.map(Math.abs), centro = prom(largo);
  const hann = largo.map((v, i) => (v - centro) * (0.5 - 0.5 * Math.cos(2 * Math.PI * i / (hz - 1))));
  const energia = (f) => (punto(hann, t.map((s) => Math.cos(2 * Math.PI * f * s)))) ** 2 + (punto(hann, t.map((s) => Math.sin(2 * Math.PI * f * s)))) ** 2;
  let dom = 1; for (let f = 1; f <= 15; f++) if (energia(f) > energia(dom)) dom = f;
  assert.strictEqual(dom, 12, 'la frecuencia dominante del largo');
  ok('un segundo de una onda de 6 Hz y 20 °/s: RMS 14.1 y, por usar el largo del giro, frecuencia dominante 12 Hz');
  assert.strictEqual(13 * (3 + 3 + 3) + 3, 120);
  ok('13 miradas × 9 números + 3 de postura = 120 rasgos');
}

// ---------- segmentar: strokes_from y groups_by_pause ----------
console.log('Segmentar');
function trazosDe(filas, hueco = 60) {                  // filas [t_ms, tip]
  const out = []; let cur = [];
  for (const r of filas) {
    if (r[1] === 1 && (!cur.length || r[0] - cur[cur.length - 1][0] < hueco)) cur.push(r);
    else { if (cur.length >= 3) out.push(cur); cur = r[1] === 1 ? [r] : []; }
  }
  if (cur.length >= 3) out.push(cur);
  return out;
}
function gruposDe(trazos, pausa = 900) {
  const gs = []; let cur = [trazos[0]];
  for (const s of trazos.slice(1)) {
    if (s[0][0] - cur[cur.length - 1][cur[cur.length - 1].length - 1][0] > pausa) { gs.push(cur); cur = [s]; } else cur.push(s);
  }
  gs.push(cur);
  return gs;
}
{
  const filas = [];
  for (const [a, b] of REF.toques.tramos) for (let t = a; t < b; t += 8) filas.push([t, 1]);
  const tr = trazosDe(filas);
  assert.strictEqual(tr.length, REF.toques.trazos, 'los trazos de strokes_from');
  assert.deepStrictEqual(gruposDe(tr).map((g) => g.length), REF.toques.grupos, 'los grupos de groups_by_pause');
  ok('corta igual que strokes_from y groups_by_pause: un hueco de 48 ms sigue, uno de 88 ms corta y un roce de 2 lecturas no cuenta');
}

// ---------- estandarizar ----------
console.log('Estandarizar');
{
  const X = [], n = 200;
  for (let i = 0; i < n; i++) X.push([120 + 35 * normal(), 1.5 + 0.2 * normal()]);
  const z = (A) => { const m = [0, 1].map((j) => prom(col(A, j))), s = [0, 1].map((j) => desv(col(A, j)) + 1e-9); return A.map((r) => r.map((v, j) => (v - m[j]) / s[j])); };
  const Z = z(X);
  near(prom(col(Z, 0)), 0, 1e-9, 'promedio 0'); near(desv(col(Z, 1)), 1, 1e-6, 'desviación 1');
  const vecino = (A, i) => { let b = -1, d = Infinity; A.forEach((r, j) => { const e = Math.hypot(r[0] - A[i][0], r[1] - A[i][1]); if (j !== i && e < d) { d = e; b = j; } }); return b; };
  const enOtraUnidad = X.map((r) => [r[0] / 1000, r[1] * 1000]);     // miliunidades: los números grandes cambian de lado
  let igual = 0, igualZ = 0;
  for (let i = 0; i < n; i++) { igual += vecino(X, i) === vecino(enOtraUnidad, i); igualZ += vecino(Z, i) === vecino(z(enOtraUnidad), i); }
  assert.strictEqual(igualZ, n, 'estandarizado, cambiar de unidad no cambia ningún vecino');
  assert.ok(igual < n / 2, `sin estandarizar la unidad decide quién es vecino (${igual} de ${n} iguales)`);
  ok(`cambiar de unidad cambia ${n - igual} de ${n} vecinos con los datos crudos y 0 con los estandarizados`);
}

// ---------- mínimos cuadrados y R² ----------
console.log('Mínimos cuadrados y R²');
{
  const c = minimos(REF.X, REF.y);
  REF.coef.forEach((v, i) => near(c[i], v, 1e-8, `el coeficiente ${i} de r2`));
  const pred = (cc) => REF.X.map((r) => cc[0] * r[0] + cc[1] * r[1] + cc[2]);
  near(r2De(REF.y, pred(c)), REF.r2, 1e-10, 'el R² de r2');
  ok(`da lo mismo que r2 de analyze_drawing.py: R² = ${REF.r2.toFixed(3)}`);
  const res = REF.y.map((v, i) => v - pred(c)[i]);
  for (let j = 0; j < 2; j++) near(punto(res, col(REF.X, j)), 0, 1e-8, 'el error es perpendicular a cada rasgo');
  near(suma(res), 0, 1e-9, 'y a la columna de unos');
  const sc = (cc) => suma(REF.y.map((v, i) => (v - pred(cc)[i]) ** 2));
  for (let i = 0; i < 200; i++) assert.ok(sc(c.map((v) => v + 0.1 * normal())) > sc(c), 'mover los coeficientes sube la suma');
  ok('en el mínimo el error queda perpendicular a los rasgos, y cualquier otro W da más suma de cuadrados');

  const v = [1, 3, 2, 5, 4], m = prom(v);
  near(r2De(v, v), 1, 1e-12, 'modelo perfecto'); near(r2De(v, v.map(() => m)), 0, 1e-12, 'decir siempre el promedio');
  assert.ok(r2De(v, v.map((a) => -a)) < 0, 'peor que el promedio da negativo');
  ok('R²: 1 si acierta todo, 0 si dice siempre el promedio, y negativo si es peor que eso');
  const x = [], y = [];
  for (let i = 0; i < 100; i++) { x.push(normal()); y.push(x[i] + normal()); }
  const cc = minimos(x.map((a) => [a]), y), xc = x.map((a) => a - prom(x)), yc = y.map((a) => a - prom(y));
  near(r2De(y, x.map((a) => cc[0] * a + cc[1])), (punto(xc, yc) / (norma(xc) * norma(yc))) ** 2, 1e-9, 'con un rasgo, R² = correlación²');
  ok('con un solo rasgo, R² es la correlación al cuadrado');
}

// ---------- sobreajuste y prueba justa ----------
console.log('Prueba justa');
{
  const real = (s) => Math.sin(2.4 * s) + 0.4 * s;
  const cheb = (s, d) => { const T = [1, s]; for (let k = 2; k <= d; k++) T.push(2 * s * T[k - 1] - T[k - 2]); return T.slice(0, d + 1); };
  const xs = Array.from({ length: 12 }, (_, i) => -1 + (2 * i + 0.3 + 0.4 * u()) / 12), ys = xs.map((s) => real(s) + 0.18 * normal());
  const nx = Array.from({ length: 400 }, () => 2 * u() - 1), ny = nx.map((s) => real(s) + 0.18 * normal());
  const rms = (a, b) => Math.sqrt(prom(a.map((v, i) => (v - b[i]) ** 2)));
  const ajustar = (d) => { const A = xs.map((s) => cheb(s, d)); return resolver(normales(A), A[0].map((_, j) => punto(col(A, j), ys))); };
  const visto = [], nuevo = [];
  for (let d = 1; d <= 11; d++) { const w = ajustar(d); visto.push(rms(xs.map((s) => punto(cheb(s, d), w)), ys)); nuevo.push(rms(nx.map((s) => punto(cheb(s, d), w)), ny)); }
  for (let i = 1; i < visto.length; i++) assert.ok(visto[i] <= visto[i - 1] + 1e-6, 'más números nunca suben el error visto');
  assert.ok(visto[10] < 1e-5, 'con tantos números como puntos pasa por todos');
  const mejor = nuevo.indexOf(Math.min(...nuevo));
  assert.ok(mejor > 0 && mejor < 9, 'lo mejor con datos nuevos está en el medio');
  assert.ok(nuevo[10] > 3 * nuevo[mejor], 'con todos los números el error nuevo se dispara');
  ok(`12 puntos: el error visto baja hasta ${visto[10].toExponential(0)} con grado 11, y el nuevo sube de ${nuevo[mejor].toFixed(2)} (grado ${mejor + 1}) a ${nuevo[10].toFixed(1)}`);

  // instantes al azar: un modelo que solo copia al instante más cercano parece bueno sin haber aprendido nada
  const trazos = [];
  for (let k = 0; k < 20; k++) { const f = 1 + 3 * u(), ph = 6 * u(); trazos.push(Array.from({ length: 80 }, (_, i) => Math.sin(2 * Math.PI * f * i / 100 + ph))); }
  const filas = trazos.flatMap((tr, k) => tr.map((v, i) => ({ k, i, v, pos: k * 1000 + i })));
  const copiar = (entreno, prueba) => {
    const orden = [...entreno].sort((a, b) => a.pos - b.pos), pos = orden.map((r) => r.pos);
    return prueba.map((p) => { let lo = 0, hi = pos.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (pos[m] <= p.pos) lo = m; else hi = m; } return Math.abs(pos[lo] - p.pos) <= Math.abs(pos[hi] - p.pos) ? orden[lo].v : orden[hi].v; });
  };
  const azar = barajar(filas.length), corte = filas.length / 5;
  const pa = azar.slice(0, corte).map((i) => filas[i]), ea = azar.slice(corte).map((i) => filas[i]);
  const pg = filas.filter((r) => r.k < 4), eg = filas.filter((r) => r.k >= 4);
  const r2a = r2De(pa.map((r) => r.v), copiar(ea, pa)), r2g = r2De(pg.map((r) => r.v), copiar(eg, pg));
  assert.ok(r2a > 0.95, 'con instantes al azar el vecino del lado delata la respuesta');
  assert.ok(r2g < 0.3, 'con trazos enteros afuera no hay de dónde copiar');
  ok(`copiar al instante de al lado da R² = ${r2a.toFixed(2)} con instantes al azar y ${r2g.toFixed(2)} con trazos enteros afuera`);
}

// ---------- retardos ----------
console.log('Rasgos con retardos');
{
  const hz = 100, n = 1500, w = (s) => Math.sin(2.1 * s) + 0.7 * Math.sin(5.3 * s + 1) + 0.4 * Math.sin(11 * s + 2);
  const lags = (ms) => { const out = []; for (let l = -ms; l <= ms; l += 40) out.push(l / 1000); return out; };
  const fila = (s, ls) => ls.map((l) => w(s + l));
  const t = Array.from({ length: n }, (_, i) => 1 + i / hz), v = t.map((s) => w(s + 0.12));      // la muñeca va 120 ms atrás del dedo
  const r2Ventana = (ms) => { const X = t.map((s) => fila(s, lags(ms))); return r2De(v, ridgeFit(X, v, 1e-3).predict(X)); };
  assert.ok(r2Ventana(0) < 0.8, 'sin retardos llega tarde');
  assert.ok(r2Ventana(240) > 0.99, 'con ±240 ms alcanza');
  assert.strictEqual(lags(240).length, 13, 'trece miradas');
  ok(`si la muñeca va 120 ms atrás: R² = ${r2Ventana(0).toFixed(2)} sin retardos, ${r2Ventana(80).toFixed(2)} con ±80 ms y ${r2Ventana(240).toFixed(3)} con ±240 ms`);
}

// ---------- velocidad, no posición ----------
console.log('Predecir la velocidad e integrarla');
{
  const dt = 0.01, X = [], V = [], P = [], V2 = [], tr = [];
  for (let k = 0; k < 40; k++) {                        // el reloj siente la velocidad; cada trazo empieza en otro sitio
    const a = 30 + 40 * u(), f = 0.5 + 1.5 * u(), ph = 6 * u(), inicio = 80 * u();
    let p = inicio; const uno = [];
    for (let i = 0; i < 100; i++) {
      const v = a * Math.sin(2 * Math.PI * f * i * dt + ph);
      X.push([v + 2 * normal()]); V.push(v); P.push(p); uno.push([v, p]);
      p += v * dt;
    }
    tr.push(uno);
  }
  const mv = ridgeFit(X, V, 1e-6), mp = ridgeFit(X, P, 1e-6);
  const r2v = r2De(V, mv.predict(X)), r2p = r2De(P, mp.predict(X));
  assert.ok(r2v > 0.95, 'la velocidad se aprende'); assert.ok(r2p < 0.2, 'la posición no: lo mismo que se siente pasa en cualquier sitio');
  ok(`mismo rasgo: R² = ${r2v.toFixed(2)} para la velocidad y ${r2p.toFixed(2)} para la posición`);
  const uno = tr[0], pred = mv.predict(uno.map((r) => [r[0]]));
  let p = uno[0][1], e = 0;
  uno.forEach((r, i) => { e = Math.max(e, Math.abs(p - r[1])); p += pred[i] * dt; });
  assert.ok(e < 2, 'integrar la velocidad predicha redibuja el trazo');
  ok(`integrar la velocidad predicha redibuja el trazo con un error máximo de ${e.toFixed(2)} mm`);
}

// ---------- descenso por el gradiente ----------
console.log('Descenso por el gradiente');
{
  const n = 200, Z = [], y = [];
  for (let i = 0; i < n; i++) { const a = normal(); Z.push([a + 0.5 * normal(), a + 0.5 * normal()]); y.push(Z[i][0] + 0.4 * Z[i][1] + 0.3 * normal()); }
  const A = normales(Z), b = [punto(col(Z, 0), y), punto(col(Z, 1), y)], opt = resolver(A, b);
  const grad = (w) => [0, 1].map((j) => 2 / n * (A[j][0] * w[0] + A[j][1] * w[1] - b[j]));
  const tr = (A[0][0] + A[1][1]) / n, det = (A[0][0] * A[1][1] - A[0][1] ** 2) / (n * n), L = 2 * (tr / 2 + Math.sqrt(tr * tr / 4 - det));
  const bajar = (alfa, pasos) => { let w = [-1.6, 2.6]; for (let i = 0; i < pasos; i++) { const g = grad(w); w = [w[0] - alfa * g[0], w[1] - alfa * g[1]]; } return w; };
  const w = bajar(0.9 / L, 3000);
  near(w[0], opt[0], 1e-6, 'llega al mismo fondo'); near(w[1], opt[1], 1e-6, 'llega al mismo fondo');
  ok(`con α = ${(0.9 / L).toFixed(2)} llega al mismo W que resolver el sistema`);
  assert.ok(norma(bajar(1.05 * 2 / L, 200)) > 100, 'con α mayor que 2/L se va');
  assert.ok(norma(bajar(0.95 * 2 / L, 3000).map((v, i) => v - opt[i])) < 1e-3, 'con α menor que 2/L llega');
  ok(`el límite del paso es 2 / curvatura máxima = ${(2 / L).toFixed(2)}: por debajo llega, por encima se va`);
}

// ---------- la red: MLP de reconstruct_drawing.py ----------
console.log('Red neuronal pequeña');
{
  assert.strictEqual(120 * 64 + 64 + 64 * 2 + 2, 7874, 'números de la red');
  assert.strictEqual(121 * 2, 242, 'números de ridge');
  ok('la red tiene 7874 números y ridge 242');
  // retropropagación: el gradiente de MLP.fit, contra restar el error a mano
  const d = 3, h = 4, m = 5, P = { W1: [], b1: [], W2: [], b2: [0.1, -0.2] };
  for (let i = 0; i < d; i++) P.W1.push(Array.from({ length: h }, () => normal() / 2));
  for (let i = 0; i < h; i++) { P.b1.push(0.1 * normal()); P.W2.push([normal() / 2, normal() / 2]); }
  const Z = Array.from({ length: m }, () => Array.from({ length: d }, normal)), T = Array.from({ length: m }, () => [normal(), normal()]);
  const adelante = () => { const H = Z.map((z) => P.b1.map((b, k) => Math.tanh(b + suma(z.map((v, i) => v * P.W1[i][k]))))); return { H, O: H.map((r) => [0, 1].map((o) => P.b2[o] + suma(r.map((v, k) => v * P.W2[k][o])))) }; };
  const perdida = () => { const { O } = adelante(); return suma(O.map((r, i) => suma(r.map((v, o) => (v - T[i][o]) ** 2)))) / (2 * m); };
  const { H, O } = adelante();
  const E = O.map((r, i) => r.map((v, o) => (v - T[i][o]) / m));
  const dH = H.map((r, i) => r.map((v, k) => suma([0, 1].map((o) => E[i][o] * P.W2[k][o])) * (1 - v * v)));
  const eps = 1e-6;
  for (let i = 0; i < d; i++) for (let k = 0; k < h; k++) {
    const g = suma(Z.map((z, s) => z[i] * dH[s][k])), v = P.W1[i][k];
    P.W1[i][k] = v + eps; const a = perdida(); P.W1[i][k] = v - eps; const b = perdida(); P.W1[i][k] = v;
    near(g, (a - b) / (2 * eps), 1e-6, 'W1');
  }
  for (let k = 0; k < h; k++) for (let o = 0; o < 2; o++) {
    const g = suma(H.map((r, s) => r[k] * E[s][o])), v = P.W2[k][o];
    P.W2[k][o] = v + eps; const a = perdida(); P.W2[k][o] = v - eps; const b = perdida(); P.W2[k][o] = v;
    near(g, (a - b) / (2 * eps), 1e-6, 'W2');
  }
  ok('la retropropagación de MLP.fit da el mismo gradiente que mover cada número y medir');

  // una capa de tanh sigue una curva que una recta no puede: se entrena solo la capa de salida, sobre tanh fijas
  const f = (s) => 2 * Math.tanh(4 * s);
  const xs = Array.from({ length: 200 }, () => 2 * u() - 1), ys = xs.map((s) => f(s) + 0.05 * normal());
  const nx = Array.from({ length: 200 }, () => 2 * u() - 1), ny = nx.map(f);
  const capa = Array.from({ length: 12 }, (_, k) => [4, -3 + 6 * k / 11]);
  const H2 = (s) => capa.map(([a, b]) => Math.tanh(a * s + b));
  const curva = ridgeFit(xs.map(H2), ys, 1e-3), recta = ridgeFit(xs.map((s) => [s]), ys, 1e-3);
  const rc = r2De(ny, curva.predict(nx.map(H2))), rr = r2De(ny, recta.predict(nx.map((s) => [s])));
  assert.ok(rc > 0.995 && rr < 0.93, 'la capa de curvas le gana a la recta');
  ok(`una curva doblada, con datos nuevos: R² = ${rr.toFixed(3)} con una recta y ${rc.toFixed(3)} con 12 tanh sumadas`);
}

// ---------- parecido de forma: shape_sim ----------
console.log('Parecido de forma');
function parecido(a, b) {                               // shape_sim con un trazo
  const c = (p) => { const q = p.map((r) => [r[0] - p[0][0], r[1] - p[0][1]]); return q; };
  const A = c(a), B = b, cen = (p) => { const m = [prom(col(p, 0)), prom(col(p, 1))]; return p.flatMap((r) => [r[0] - m[0], r[1] - m[1]]); };
  const x = cen(A), y = cen(B);
  return punto(x, y) / (norma(x) * norma(y) + 1e-9);
}
{
  near(parecido(REF.forma.a, REF.forma.b), REF.forma.parecido, 1e-9, 'el parecido de shape_sim');
  ok(`da lo mismo que shape_sim: ${REF.forma.parecido.toFixed(3)}`);
  const s = Array.from({ length: 120 }, (_, i) => { const q = i / 119 * 2 * Math.PI; return [20 * Math.sin(q) + 3 * q, 15 * Math.sin(2 * q)]; });
  const rms = (a, b) => Math.sqrt(prom(a.map((p, i) => (p[0] - b[i][0]) ** 2 + (p[1] - b[i][1]) ** 2)));
  const corrida = s.map((p) => [p[0] + 14, p[1] + 8]), chica = s.map((p) => [0.6 * p[0], 0.6 * p[1]]);
  near(parecido(s, corrida), 1, 1e-6, 'en otro sitio'); near(parecido(s, chica), 1, 1e-6, 'más chica');
  assert.ok(rms(s, corrida) > 15, 'punto a punto no perdona el sitio');
  ok(`la misma forma en otro sitio o más chica da 1, aunque punto a punto esté a ${rms(s, corrida).toFixed(1)} mm`);
  const m = [prom(col(s, 0)), prom(col(s, 1))], th = Math.PI / 6;
  const girada = s.map((p) => { const x = p[0] - m[0], y = p[1] - m[1]; return [Math.cos(th) * x - Math.sin(th) * y, Math.sin(th) * x + Math.cos(th) * y]; });
  near(parecido(s, girada), Math.cos(th), 1e-6, 'un giro de 30° da cos 30°');
  near(parecido(s, s.map((p) => [-p[0], -p[1]])), -1, 1e-6, 'al revés da −1');
  ok('girada 30° da cos 30° = 0.87, y dada vuelta da −1: el parecido sí ve los giros');
}

// ---------- ¿cuánto creo en una diferencia? ----------
console.log('Cuánto creer en una mediana');
{
  const n = 53, sd = 0.2, veces = 4000, med = [];
  for (let k = 0; k < veces; k++) med.push(mediana(Array.from({ length: n }, () => 0.72 + sd * normal())));
  const tiembla = desv(med);
  near(tiembla, 1.2533 * sd / Math.sqrt(n), 0.004, 'la mediana tiembla 1.25·σ/√n');
  ok(`con 53 letras que varían ±${sd}, la mediana tiembla ±${tiembla.toFixed(3)} (1.25·σ/√n = ${(1.2533 * sd / Math.sqrt(n)).toFixed(3)})`);
  // sacar otra vez las letras al azar estima ese temblor sin saber la verdad
  const letras = Array.from({ length: n }, () => 0.72 + sd * normal()), rem = [];
  for (let k = 0; k < veces; k++) rem.push(mediana(Array.from({ length: n }, () => letras[Math.floor(u() * n)])));
  assert.ok(desv(rem) > tiembla / 2.5 && desv(rem) < tiembla * 2.5, `remuestrear da un temblor del mismo orden (${desv(rem).toFixed(3)})`);
  ok(`remuestrear una sola sesión da ±${desv(rem).toFixed(3)}: del mismo orden, sin haber repetido la sesión`);
  let pasa = 0;
  for (let k = 0; k < veces; k++) {                     // dos modelos IGUALES, cada uno con sus 53 letras
    const a = mediana(Array.from({ length: n }, () => 0.72 + sd * normal())), b = mediana(Array.from({ length: n }, () => 0.72 + sd * normal()));
    if (Math.abs(a - b) >= 0.04) pasa++;
  }
  assert.ok(pasa / veces > 0.25, 'una diferencia de 0.04 sale sola');
  ok(`dos modelos iguales, medidos con letras distintas, se separan 0.04 o más el ${(100 * pasa / veces).toFixed(0)} % de las veces`);
}

// ---------- vecinos, confusión y F ----------
console.log('Vecinos, confusión y F');
function vecinosDejandoUno(X, y, k = 3) {               // knn_loo de analyze_dataset.py
  const z = X[0].map((_, j) => { const c = col(X, j), m = prom(c), s = desv(c) + 1e-9; return c.map((v) => (v - m) / s); });
  const Z = X.map((_, i) => z.map((c) => c[i]));
  return Z.map((a, i) => {
    const d = Z.map((b, j) => (j === i ? Infinity : norma(a.map((v, q) => v - b[q]))));
    const nn = d.map((v, j) => [v, j]).sort((p, q) => p[0] - q[0]).slice(0, k), votos = new Map();
    for (const [v, j] of nn) votos.set(y[j], (votos.get(y[j]) || 0) + 1 / (1 + v));
    return [...votos].reduce((m, e) => (e[1] > m[1] ? e : m))[0];
  });
}
const confusion = (y, p, clases) => clases.map((c) => clases.map((q) => y.filter((v, i) => v === c && p[i] === q).length));
function efe(v, y) {                                    // fstat de analyze_dataset.py, una medida
  const clases = [...new Set(y)].sort(), g = clases.map((c) => v.filter((_, i) => y[i] === c)), m = prom(v);
  const entre = suma(g.map((a) => a.length * (prom(a) - m) ** 2)) / (g.length - 1);
  const dentro = suma(g.map((a) => suma(a.map((x) => (x - prom(a)) ** 2)))) / (v.length - g.length);
  return entre / (dentro + 1e-12);
}
{
  const G = REF.gestos, p = vecinosDejandoUno(G.X, G.y);
  assert.deepStrictEqual(p, G.pred, 'los votos de knn_loo');
  ok('los votos dan lo mismo que knn_loo');
  const cm = confusion(G.y, p, [0, 1, 2]);
  assert.deepStrictEqual(cm, G.confusion, 'la tabla de confusion');
  cm.forEach((r, i) => assert.strictEqual(suma(r), G.y.filter((v) => v === i).length, 'cada fila suma las tomas de ese gesto'));
  near((cm[0][0] + cm[1][1] + cm[2][2]) / 12, p.filter((v, i) => v === G.y[i]).length / 12, 1e-12, 'la diagonal son los aciertos');
  ok('cada fila suma las tomas de ese gesto y la diagonal son los aciertos');
  G.F.forEach((f, j) => near(efe(col(G.X, j), G.y), f, 1e-8, `la F de la medida ${j}`));
  ok('la F da lo mismo que fstat');

  const y = [], a = [], b = [], c = [];
  for (let g = 0; g < 4; g++) for (let i = 0; i < 25; i++) { y.push(g); a.push(g * 2 + normal()); b.push(normal()); c.push(1000 * (g * 2 + normal())); }
  assert.ok(efe(a, y) > 30, 'una medida que separa da una F grande');
  let fs = 0; for (let k = 0; k < 300; k++) fs += efe(y.map(() => normal()), y);
  near(fs / 300, 1, 0.15, 'una medida que no separa da F cerca de 1');
  const a2 = a.map((v) => 1000 * v + 5);
  near(efe(a2, y), efe(a, y), 1e-6, 'la F no depende de la unidad');
  ok(`una medida que separa da F = ${efe(a, y).toFixed(0)}, una que no, F ≈ ${(fs / 300).toFixed(2)}; cambiar de unidad no la mueve`);

  // otra persona: mismas clases corridas. Dejar uno fuera no lo ve
  const X = [], Y = [], B = [];
  for (let g = 0; g < 4; g++) for (let i = 0; i < 20; i++) { X.push([g * 2 + 0.4 * normal(), g + 0.2 * normal()]); Y.push(g); B.push([(g * 2 + 0.4 * normal()) * 0.6 + 1.2, (g + 0.2 * normal()) * 1.4 + 0.3]); }
  const aciertoA = vecinosDejandoUno(X, Y).filter((v, i) => v === Y[i]).length / X.length;
  const m = [0, 1].map((j) => prom(col(X, j))), s = [0, 1].map((j) => desv(col(X, j)) + 1e-9), z = (r) => r.map((v, j) => (v - m[j]) / s[j]);
  const ZA = X.map(z), votar = (q) => {
    const nn = ZA.map((r, j) => [norma(r.map((v, i) => v - q[i])), j]).sort((p1, p2) => p1[0] - p2[0]).slice(0, 3), votos = new Map();
    for (const [v, j] of nn) votos.set(Y[j], (votos.get(Y[j]) || 0) + 1 / (1 + v));
    return [...votos].reduce((mm, e) => (e[1] > mm[1] ? e : mm))[0];
  };
  const aciertoB = B.map((r) => votar(z(r))).filter((v, i) => v === Y[i]).length / B.length;
  assert.ok(aciertoA > 0.9 && aciertoB < aciertoA - 0.2, 'otra persona cae fuera de lo que el modelo conoce');
  ok(`dejando uno fuera acierta ${(aciertoA * 100).toFixed(0)} %; con otra persona, la misma cuenta acierta ${(aciertoB * 100).toFixed(0)} %`);
}
console.log('\nTodo pasa.');
