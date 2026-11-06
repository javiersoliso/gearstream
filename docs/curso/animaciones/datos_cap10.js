// Los números de las animaciones del capítulo 10 que salen de código JS: el detector de giros de verdad
// (server/web/flick.js), corrido sobre señales inventadas, y el clic de la animación de apuntar del mocap
// (server/web/mocapmath.js). cap10.py lo corre y lee el JSON que imprime; tools/test_gestos.js lo usa como módulo
// y comprueba lo que dice. Lo que hace game.js con el empujón no se puede importar (es código de página): aquí va
// copiado en `Empujon`, y la prueba revisa que sus constantes sigan siendo las de game.js.
//   node docs/curso/animaciones/datos_cap10.js > datos.json
'use strict';
const path = require('path');
const web = path.join(__dirname, '..', '..', '..', 'server', 'web');
const { FlickDetector, FLICK_DEFAULTS } = require(path.join(web, 'flick.js'));
const M = require(path.join(web, 'mocapmath.js'));

const r1 = (v) => +v.toFixed(1), r3 = (v) => +v.toFixed(3);

// números al azar repetibles, con forma de campana
function azar(semilla) {
  let e = semilla;
  const u = () => { e = (e * 16807) % 2147483647; return e / 2147483647; };
  return { u, normal: () => Math.sqrt(-2 * Math.log(u() + 1e-12)) * Math.cos(2 * Math.PI * u()) };
}

const campana = (t, t0, a, s) => a * Math.exp(-0.5 * ((t - t0) / s) ** 2);   // un giro: sube y baja, s en ms
const instantes = (ms) => Array.from({ length: ms / 10 + 1 }, (_, i) => i * 10);   // 100 muestras por segundo

// corre el detector y guarda, además de cada giro, cuándo empezó y cuándo se cerró y el umbral en cada muestra
function correr(det, ts, W) {
  const eventos = [], umbral = [];
  let t0 = null;
  ts.forEach((t, k) => {
    const antes = det.cur;
    const f = det.update(t, W[k]);
    if (!antes && det.cur) t0 = t;
    umbral.push(r1(det.threshold()));
    if (f) eventos.push({ t: f.t, dir: f.dir, pico: +f.peak.toFixed(2), t0, fin: t });
  });
  return { eventos, umbral };
}

// la misma cuenta que FlickDetector, pero con un solo umbral: para ver qué arregla el segundo
function conUnSoloUmbral(ts, x, umbral) {
  const eventos = [];
  let dentro = false;
  ts.forEach((t, k) => {
    const arriba = Math.abs(x[k]) > umbral;
    if (arriba && !dentro) eventos.push(t);
    dentro = arriba;
  });
  return eventos;
}

// 1. un pico: dos giros en 3 s, uno hacia cada lado, encima de un apuntar lento
function pico() {
  const a = azar(11), ts = instantes(3000);
  const wx = ts.map((t) => campana(t, 800, 700, 30) + campana(t, 1900, -620, 32) + 20 * Math.sin(2 * Math.PI * 0.7 * t / 1000) + 4 * a.normal());
  const W = wx.map((v) => [v, 12 * a.normal(), 12 * a.normal()]);
  const r = correr(new FlickDetector(), ts, W);
  return { t: ts, wx: wx.map(r1), ...r };
}

// 2. histéresis: un giro lento con temblor, que se pasea por el borde del umbral
function histeresis() {
  const a = azar(5), ts = instantes(3000), entrar = 100;
  const wx = ts.map((t) => campana(t, 1500, 160, 170) + 25 * Math.sin(2 * Math.PI * 12 * t / 1000) + 6 * a.normal());
  const det = new FlickDetector({ minOn: entrar, rel: 0, refractory: 0 });
  const dos = correr(det, ts, wx.map((v) => [v, 0, 0]));
  return { t: ts, wx: wx.map(r1), entrar, salir: entrar / 2, unSolo: conUnSoloUmbral(ts, wx, entrar), dos: dos.eventos };
}

// 3. periodo refractario: un giro y su rebote, con los 90 ms y sin ellos
function refractario() {
  const ts = instantes(1200);
  const senal = (tRebote, ancho) => ts.map((t) => campana(t, 500, 700, 28) + campana(t, tRebote, -340, ancho));
  const W = (x) => x.map((v) => [v, 0, 0]);
  const corto = senal(565, 14), largo = senal(610, 30);
  return {
    t: ts, wx: corto.map(r1), wxLargo: largo.map(r1), ms: FLICK_DEFAULTS.refractory,
    con: correr(new FlickDetector(), ts, W(corto)).eventos,
    sin: correr(new FlickDetector({ refractory: 0 }), ts, W(corto)).eventos,
    reboteLargo: correr(new FlickDetector(), ts, W(largo)).eventos,
  };
}

// 4. el umbral que se adapta: una persona fuerte y una suave, con 12 giros cada una y un giro de vuelta,
// más chico, 260 ms después de cada uno. Para comparar, el mismo detector con umbral fijo de 70 y de 300.
function adaptar() {
  const persona = (semilla, fuerza, vuelta) => {
    const a = azar(semilla), golpes = [];
    for (let i = 0; i < 12; i++) golpes.push({ t: 500 + 700 * i, a: fuerza * (1 + 0.09 * a.normal()) });
    const ts = instantes(9000);
    const wx = ts.map((t) => golpes.reduce((s, g) => s + campana(t, g.t, g.a, 30) + campana(t, g.t + 260, -vuelta, 30), 0) + 3 * a.normal());
    const W = wx.map((v) => [v, 0, 0]);
    const contar = (eventos) => ({
      giros: eventos.filter((e) => golpes.some((g) => Math.abs(e.t - g.t) <= 40)).length,
      deSobra: eventos.filter((e) => !golpes.some((g) => Math.abs(e.t - g.t) <= 40)).length,
    });
    const r = correr(new FlickDetector(), ts, W);
    const fijo = (minOn) => contar(correr(new FlickDetector({ minOn, rel: 0 }), ts, W).eventos);
    return { t: ts, wx: wx.map(r1), umbral: r.umbral, eventos: r.eventos, adaptado: contar(r.eventos), fijo70: fijo(70), fijo300: fijo(300) };
  };
  return { fuerte: persona(21, 900, 190), suave: persona(22, 230, 50) };
}

// el umbral solo se mueve con los giros que se aceptan: si después giras por debajo de él, no baja
function umbralTrabado() {
  const det = new FlickDetector();
  const ts = instantes(20000);
  const fuerza = (t) => (t < 9000 ? 900 : 230);
  const wx = ts.map((t) => { const i = Math.round((t - 500) / 700), g = 500 + 700 * i; return campana(t, g, fuerza(g), 30); });
  const r = correr(det, ts, wx.map((v) => [v, 0, 0]));
  return { fuertes: r.eventos.filter((e) => e.t < 9000).length, suaves: r.eventos.filter((e) => e.t >= 9000).length, umbral: r1(det.threshold()) };
}

// 5. dominancia: giros de muñeca y movimientos de todo el brazo, cada uno con un detector nuevo
function dominancia() {
  const a = azar(33), casos = [];
  const uno = (wx, otro) => {
    const ts = instantes(400);
    const W = ts.map((t) => [campana(t, 200, wx, 30), campana(t, 200, otro, 30), campana(t, 200, otro * 0.6, 30)]);
    return correr(new FlickDetector(), ts, W).eventos.length > 0;
  };
  for (let i = 0; i < 16; i++) { const wx = 350 + 550 * a.u(), otro = wx * (0.1 + 0.5 * a.u()); casos.push({ tipo: 'muneca', wx: r1(wx), otro: r1(otro), acepta: uno(wx, otro) }); }
  for (let i = 0; i < 16; i++) { const wx = 150 + 450 * a.u(), otro = wx * (0.85 + 1.2 * a.u()); casos.push({ tipo: 'brazo', wx: r1(wx), otro: r1(otro), acepta: uno(wx, otro) }); }
  return { factor: FLICK_DEFAULTS.dominance, casos };
}

// 6. el clic de tornillo: la animación de apuntar del mocap, sin ruido, como la leería el reloj
function tornillo() {
  const imu = M.synth('apuntar', 'l', { noise: false });
  const ts = Array.from({ length: imu.n }, (_, k) => Math.round(k * 1000 / imu.hz));
  const W = ts.map((_, k) => [imu.gyr[3 * k], imu.gyr[3 * k + 1], imu.gyr[3 * k + 2]]);
  const r = correr(new FlickDetector(), ts, W);
  const giros = r.eventos.filter((e) => e.dir > 0);
  return {
    t: ts, wx: W.map((w) => r1(w[0])), otro: W.map((w) => r1(Math.max(Math.abs(w[1]), Math.abs(w[2])))),
    eventos: r.eventos, picoIda: Math.max(...giros.map((e) => e.pico)),
    picoVuelta: Math.max(...r.eventos.filter((e) => e.dir < 0).map((e) => e.pico)),
    otroMax: r1(Math.max(...W.map((w) => Math.max(Math.abs(w[1]), Math.abs(w[2]))))), umbralFinal: r.umbral[r.umbral.length - 1],
  };
}

// 7. el empujón: copia de onAccel y aimAt de server/web/game.js (la prueba revisa que sus constantes sean esas)
const PUSH_ON = 4.0, PUSH_OFF = 0.4, PUSH_MAX_MS = 220, PUSH_REFRACTARIO = 350, MIRA_ANTES = 120;
class Empujon {
  constructor() { this.push = null; this.hasta = -Infinity; this.picos = []; this.pmax = 25; }
  feed(t, af) {                                   // t en ms, af = (acelerómetro − gravedad)·antebrazo en m/s²
    if (!this.push) {
      if (af > PUSH_ON && t > this.hasta) this.push = { t0: t, peak: af };
      return null;
    }
    this.push.peak = Math.max(this.push.peak, af);
    if (af < PUSH_ON * PUSH_OFF || t - this.push.t0 > PUSH_MAX_MS) {
      const p = this.push;
      this.push = null;
      this.hasta = t + PUSH_REFRACTARIO;
      this.picos.push(p.peak); if (this.picos.length > 12) this.picos.shift();
      const s = [...this.picos].sort((a, b) => a - b);
      this.pmax = Math.max(12, 1.1 * s[Math.floor(0.8 * (s.length - 1))]);
      return { t0: p.t0, fin: t, pico: p.peak, u: Math.max(0, Math.min(1, (p.peak - PUSH_ON) / Math.max(1, this.pmax - PUSH_ON))) };
    }
    return null;
  }
}

function empujon() {
  const a = azar(44), ts = instantes(2000);
  const af = ts.map((t) => campana(t, 1000, 16, 50) + campana(t, 1160, -9, 50) + 0.15 * a.normal());
  const rampa = (u) => { const x = Math.max(0, Math.min(1, u)); return x * x * (3 - 2 * x); };
  const yaw = ts.map((t) => 8 + 7 * rampa((t - 860) / 250) + 0.08 * a.normal());   // empujar arrastra la mira 7°
  const det = new Empujon();
  let ev = null;
  ts.forEach((t, k) => { ev = det.feed(t, af[k]) || ev; });
  const en = (t) => yaw[ts.findIndex((s) => s >= t)];
  return {
    t: ts, af: af.map((v) => +v.toFixed(2)), yaw: yaw.map((v) => +v.toFixed(2)), on: PUSH_ON, off: PUSH_ON * PUSH_OFF, antes: MIRA_ANTES,
    t0: ev.t0, fin: ev.fin, pico: +ev.pico.toFixed(1), miraBuena: 8,
    miraAntes: +en(ev.t0 - MIRA_ANTES).toFixed(1), miraCruce: +en(ev.t0).toFixed(1), miraFin: +en(ev.fin).toFixed(1),
  };
}

// 8. el tempo: seis intervalos de unos 500 ms y un giro que no se detectó, con el detector de verdad
function tempo() {
  const a = azar(8), intervalos = [500, 510, 490, 1000, 505, 495];
  const golpes = [400];
  intervalos.forEach((d) => golpes.push(golpes[golpes.length - 1] + d));
  const ts = instantes(golpes[golpes.length - 1] + 300);
  const wx = ts.map((t) => golpes.reduce((s, g, i) => s + campana(t, g, i % 2 ? -600 : 600, 30), 0) + 3 * a.normal());
  const det = new FlickDetector();
  const r = correr(det, ts, wx.map((v) => [v, 0, 0]));
  const iv = det.beats.slice(1).map((b, i) => b - det.beats[i]);
  const promedio = iv.reduce((s, v) => s + v, 0) / iv.length;
  const orden = [...iv].sort((x, y) => x - y), mediana = orden[Math.floor(orden.length / 2)];
  return {
    t: ts, wx: wx.map(r1), eventos: r.eventos, intervalos: iv, orden, mediana, promedio: r1(promedio),
    bpm: r1(det.tempo()), bpmPromedio: r1(60000 / promedio), bpmDeVerdad: 120,
  };
}

// 9 y 10. aciertos contra falsas alarmas y AUC: 20 gestos y 2 minutos de uso normal, inventados. Cada número es
// el pico de un gesto, o de algo que no era un gesto. Un pellizco es un golpe de 10 ms de base y 6 m/s²: con una
// muestra cada 10 ms, el pico que se ve depende de dónde cae la muestra. Un giro dura mucho más que eso.
function barrido() {
  const a = azar(77), MINUTOS = 2;
  const lognormal = (mediana, s) => mediana * Math.exp(s * a.normal());
  const pellizco = {
    nombre: 'pellizco', unidad: 'm/s²',
    pos: Array.from({ length: 20 }, () => { const d = 10 * a.u() - 5; return 6 * (1 + 0.15 * a.normal()) * (1 - Math.abs(d) / 5); }),
    neg: Array.from({ length: 40 * MINUTOS }, () => lognormal(0.9, 0.45)),
  };
  const giro = {
    nombre: 'giro', unidad: '°/s',
    pos: Array.from({ length: 20 }, () => { const d = 10 * a.u() - 5; return 700 * (1 + 0.15 * a.normal()) * Math.exp(-0.5 * (d / 30) ** 2); }),
    neg: Array.from({ length: 40 * MINUTOS }, () => lognormal(40, 0.45)),
  };
  for (const g of [pellizco, giro]) {
    const umbrales = [...new Set([...g.pos, ...g.neg])].sort((x, y) => y - x);
    g.curva = [[0, 0], ...umbrales.map((T) => [g.neg.filter((v) => v >= T).length / MINUTOS, g.pos.filter((v) => v >= T).length])];
    g.auc = auc(g.pos, g.neg);
    const peorNeg = Math.max(...g.neg);
    g.peorNeg = peorNeg;
    g.aciertosSinFalsas = g.pos.filter((v) => v > peorNeg).length;
    g.pos = g.pos.map(r3); g.neg = g.neg.map(r3);
  }
  return { minutos: MINUTOS, pellizco, giro };
}

// lo mismo que auc de tools/analyze_drawing.py: P(positivo > negativo), con los empates a la mitad
function auc(pos, neg) {
  let s = 0;
  for (const p of pos) for (const n of neg) s += p > n ? 1 : p === n ? 0.5 : 0;
  return s / (pos.length * neg.length);
}

// lo que ve una muestra cada `paso` ms de un golpe: la fracción del pico de verdad, peor y mejor caso
function muestreoDeUnGolpe(forma, paso) {
  let peor = 1, mejor = 0;
  for (let d = -paso / 2; d <= paso / 2; d += 0.1) { const v = forma(d); peor = Math.min(peor, v); mejor = Math.max(mejor, v); }
  return { peor: r3(peor), mejor: r3(mejor) };
}

function calcular() {
  return {
    pico: pico(), histeresis: histeresis(), refractario: refractario(), adaptar: adaptar(), trabado: umbralTrabado(),
    dominancia: dominancia(), tornillo: tornillo(), empujon: empujon(), tempo: tempo(), barrido: barrido(),
    muestreo: {
      pellizco: muestreoDeUnGolpe((d) => Math.max(0, 1 - Math.abs(d) / 5), 10),
      giro: muestreoDeUnGolpe((d) => Math.exp(-0.5 * (d / 30) ** 2), 10),
    },
  };
}

module.exports = { calcular, Empujon, auc, azar, campana, instantes, correr, conUnSoloUmbral };
if (require.main === module) console.log(JSON.stringify(calcular()));
