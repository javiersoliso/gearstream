// Los números de las animaciones del capítulo 9, sacados de la misma cuenta que usan el mocap, el avatar y las pruebas
// (server/web/mocapmath.js, server/web/armfilter.js y tools/test_cuerpo.js). cap09.py lo corre y lee el JSON que imprime.
//   node docs/curso/animaciones/datos_cap09.js
'use strict';
const path = require('path');
const raiz = path.join(__dirname, '..', '..', '..');
const M = require(path.join(raiz, 'server', 'web', 'mocapmath.js'));
const { ArmFilter, feasible, defaultPrior, DEFAULTS } = require(path.join(raiz, 'server', 'web', 'armfilter.js'));
const { correr, ikDelCurso, poseCon, flojo } = require(path.join(raiz, 'tools', 'test_cuerpo.js'));
const { sub, dot, cross, len, unit, add, mul } = M.vec;

const r3 = (v) => +v.toFixed(3);
const v3 = (a, k) => [a[3 * k], a[3 * k + 1], a[3 * k + 2]];
const azul = (a, b) => Math.acos(Math.max(-1, Math.min(1, dot(unit(a), unit(b))))) * 180 / Math.PI;

// los huesos de una pose, vistos de costado (x adelante) o de frente (x a la derecha del cuerpo), sin los dedos
function huesos(b, vista, H = 0) {
  const c = Math.cos(H), s = Math.sin(H), fwd = [-s, 0, -c], right = [c, 0, -s], eje = vista === 'lado' ? fwd : right, p0 = b.pelvis;
  const q = (p) => [r3(dot(sub(p, p0), eje)), r3(p[1])];
  return b.segs.filter(([a, e]) => len(sub(a, e)) > 0.095).map(([a, e]) => [q(a), q(e)]);
}
const parado = M.build(M.idlePose(0));

// levantar un brazo: la pose de reposo con el brazo izquierdo en fk
const levantar = [];
for (let i = 0; i <= 30; i++) {
  const P = M.idlePose(0), u = i / 30;
  P.arms.l = { fk: { flex: 110 * u, abd: 6, elbow: 12 + 60 * u }, pron: 0, fist: 0.2 };
  levantar.push(huesos(M.build(P), 'lado'));
}

// caminar: un ciclo de cuerpo, y las cuentas que lo mueven
const CAM = M.ANIMS.caminar, ciclo = CAM.dur / 8, marcha = [];
for (let i = 0; i < 36; i++) { const t = i / 36 * ciclo, P = CAM.pose(t, 'l'); marcha.push(huesos(M.build(P), 'lado', P.H)); }
const fase = { t: [], brazo: [], rodilla: [] };
for (let i = 0; i <= 120; i++) { const t = i / 120 * 3 * ciclo, P = CAM.pose(t, 'l'); fase.t.push(r3(t)); fase.brazo.push(r3(P.arms.l.fk.flex)); fase.rodilla.push(r3(P.legs.l.knee)); }

// apuntar: la curva suave y el círculo
const AP = M.ANIMS.apuntar, apunta = { t: [], x: [], y: [] };
for (let i = 0; i <= 200; i++) { const t = i / 20, p = AP.path(t).p; apunta.t.push(r3(t)); apunta.x.push(r3(p[0] - AP.screen.c[0])); apunta.y.push(r3(p[1] - AP.screen.c[1])); }

// fk: la cuenta de costado contra build; ik: la copia contra build
const fk = [[0, 0], [90, 0], [0, 90], [40, 70], [110, 45]].map(([flex, elbow]) => {
  const a = M.build(poseCon({ fk: { flex, elbow } })).arms.l, q = (p) => [dot(sub(p, a.sh), [0, 0, -1]), p[1] - a.sh[1]];
  return { flex, elbow, codo: q(a.el), muneca: q(a.wr) };
});
const ikPrueba = ikDelCurso([0, 1.4, 0], [0.2, 1.2, -0.35], 0.29, 0.27, [0, 1, -0.5]);

// ruido: la misma cuenta de ArmFilter.randn, desde sus dos números uniformes
const f1 = new ArmFilter({ seed: 7 }), f2 = new ArmFilter({ seed: 7 }), f3 = new ArmFilter({ seed: 8 });
const uv = Array.from({ length: 3000 }, () => [f1.rand(), f1.rand()]);
const normales = Array.from({ length: 3000 }, () => f2.randn());
const otra = Array.from({ length: 3000 }, () => f3.randn());
// probabilidad: pares de números parejos de ArmFilter.rand, para contar qué fracción cae en cada franja
const f4 = new ArmFilter({ seed: 4 }), azar = Array.from({ length: 2000 }, () => [f4.rand(), f4.rand()]);

// lo que leería el reloj: caminar, sin y con ruido, 3 s a 50 muestras por segundo
const limpio = M.synth('caminar', 'l', { noise: false }), sucio = M.synth('caminar', 'l', { noise: true });
const lectura = { t: [], gyr: [], acc: [], gyrR: [], accR: [] };
for (let k = 0; k < 300; k += 2) {
  lectura.t.push(r3(k / 100));
  lectura.gyr.push(v3(limpio.gyr, k).map(r3)); lectura.acc.push(v3(limpio.acc, k).map(r3));
  lectura.gyrR.push(v3(sucio.gyr, k).map(r3)); lectura.accR.push(v3(sucio.acc, k).map(r3));
}
// el reloj de costado, en tres instantes separados, para ver la segunda diferencia
const reloj = (t) => { const P = CAM.pose(t, 'l'), b = M.build(P), w = M.watchOf(b, 'l'), c = Math.cos(P.H), s = Math.sin(P.H), fw = [-s, 0, -c]; return [r3(dot(sub(w.p, b.pelvis), fw)), r3(w.p[1])]; };
const trayecto = Array.from({ length: 60 }, (_, i) => reloj(i / 60 * ciclo));

// la prueba con verdad: caminando, el antebrazo de verdad y el reconstruido, sin ruido, con ruido y con el reloj flojo
const alineado = (imu) => { const X = v3(imu.truth.X, 0), Z = v3(imu.truth.Z, 0); return { frame0: [X, cross(Z, X), Z], psi0: M.headingOf(v3(imu.truth.F, 0)) }; };
const recs = { limpio: M.reconstruct(limpio, 'l', alineado(limpio)), sucio: M.reconstruct(sucio, 'l', alineado(sucio)), flojo: M.reconstruct(flojo(limpio, 8, 1), 'l', alineado(limpio)) };
const prueba = { t: [], limpio: [], sucio: [], flojo: [], verdad: [], reconLimpio: [], reconFlojo: [] };
for (let k = 0; k < limpio.n; k += 5) {
  const t = k / limpio.hz, H = CAM.pose(t, 'l').H, c = Math.cos(H), s = Math.sin(H), fw = [-s, 0, -c];
  const lado = (F) => [r3(dot(F, fw)), r3(F[1])], Fv = v3(limpio.truth.F, k);
  prueba.t.push(r3(t));
  for (const m of ['limpio', 'sucio', 'flojo']) prueba[m].push(r3(azul(Fv, v3(recs[m].F, k))));
  prueba.verdad.push(lado(Fv)); prueba.reconLimpio.push(lado(v3(recs.limpio.F, k))); prueba.reconFlojo.push(lado(v3(recs.flojo.F, k)));
}

// los límites: para un antebrazo al frente, cada dirección del brazo y por qué se descarta
const fLim = unit([0.1, -0.1, 1]), NLim = [1, 0, 0.1], o = DEFAULTS, limites = [];
for (let lat = -85; lat <= 85; lat += 10) {
  for (let lon = -175; lon <= 175; lon += 10) {
    const a = lat * Math.PI / 180, b = lon * Math.PI / 180, u = [Math.cos(a) * Math.sin(b), Math.sin(a), Math.cos(a) * Math.cos(b)];
    let c = 0;                                   // 0 posible, 1 codo de más de 150°, 2 torsión, 3 atrás o torso
    if (!feasible(u, fLim, NLim, o)) c = dot(u, fLim) < o.cosMaxFlex ? 1 : feasible(u, fLim, NLim, { ...o, pronSlack: -2 }) ? 2 : 3;
    limites.push([lon, lat, c]);
  }
}
const rep = defaultPrior(fLim);

// el filtro: una corrida con el brazo moviéndose 15 s y quieto después; la nube cada 0.1 s
const nube = { t: [], codos: [], verdad: [], est: [], reposo: [], muneca: [], spread: [], neff: [], errF: [], errR: [], quieto: [] };
const serie = { t: [], spread: [], neff: [], errF: [], errR: [], quieto: [] };
const { remuestreos } = correr({
  seconds: 40, still: 15, speed: 2.5,
  mira(f, fila, c, k) {
    if (k % 5 === 0) { serie.t.push(r3(fila.t)); serie.spread.push(r3(100 * fila.spread)); serie.neff.push(Math.round(fila.neff)); serie.errF.push(r3(100 * fila.errF)); serie.errR.push(r3(100 * fila.errR)); serie.quieto.push(fila.quieto ? 1 : 0); }
    if (k % 10 === 0 && fila.t <= 30) {
      const codos = [];
      for (let i = 0; i < 160; i++) codos.push(f.elbow(i).map(r3));
      nube.t.push(r3(fila.t)); nube.codos.push(codos); nube.verdad.push(c.e.map(r3));
      nube.est.push(add(DEFAULTS.shoulder, mul(f.est.u, f.o.Lu)).map(r3)); nube.reposo.push(add(DEFAULTS.shoulder, mul(defaultPrior(c.f), f.o.Lu)).map(r3));
      nube.muneca.push(add(c.e, mul(c.f, f.o.Lf)).map(r3));
    }
  },
});

// el remuestreo sistemático, con 24 partículas, de verdad
const n = 24, res = new ArmFilter({ n, seed: 4, roughen: 0 }), crudo = Array.from({ length: n }, (_, i) => Math.exp(-(((i - 8) / 2.6) ** 2)) + 0.25 * Math.exp(-(((i - 18) / 1.5) ** 2)) + 0.002);
const suma = crudo.reduce((a, b) => a + b, 0), pesos = crudo.map((x) => x / suma), inicio = new ArmFilter({ n, seed: 4 }).rand() / n;
for (let i = 0; i < n; i++) { const a = i * 2 * Math.PI / n; res.U.set([Math.cos(a), Math.sin(a), 0], 3 * i); res.V.fill(0, 3 * i, 3 * i + 3); res.W[i] = pesos[i]; }
res._resample();
const clones = new Array(n).fill(0);
for (let m = 0; m < n; m++) clones[(Math.round(Math.atan2(res.U[3 * m + 1], res.U[3 * m]) * n / (2 * Math.PI)) + n) % n]++;

process.stdout.write(JSON.stringify({
  frente: huesos(parado, 'frente'), levantar, marcha, ciclo, fase, apunta, fk, ikPrueba,
  uv: uv.slice(0, 400), azar, normales, otra, lectura, trayecto, prueba,
  limites, reposoLim: rep, fLim, prior: { sigmaR: DEFAULTS.sigmaR, sigmaRel: DEFAULTS.sigmaRel },
  nube, serie, remuestreos, shoulder: DEFAULTS.shoulder, Lu: DEFAULTS.Lu, res: { n, pesos, inicio, clones },
}));
