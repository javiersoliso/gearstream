// Pruebas del capítulo 10 del curso (Gestos): lo que el capítulo afirma, comprobado con señales inventadas donde la
// respuesta se conoce. Usa el detector de verdad (server/web/flick.js) y, si hay Python, los de tools/air_mouse.py.
// Las pruebas del detector de picos corren también contra tu ejercicio.
//   node tools/test_gestos.js              # la cuenta del curso
//   node tools/test_gestos.js --ejercicio  # tu detector, en docs/curso/ejercicios/cap10.js
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { spawnSync } = require('child_process');

const raiz = path.join(__dirname, '..');
const { FlickDetector, FLICK_DEFAULTS } = require(path.join(raiz, 'server', 'web', 'flick.js'));
const datos = require(path.join(raiz, 'docs', 'curso', 'animaciones', 'datos_cap10.js'));
const { azar, campana, instantes, correr, Empujon, auc } = datos;

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b} (±${tol})`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
const fuente = (...p) => fs.readFileSync(path.join(raiz, ...p), 'utf8');
const tiene = (texto, trozo, donde) => assert.ok(texto.includes(trozo), `${donde} ya no dice «${trozo}»: revisa el capítulo`);

const D = datos.calcular();

// ---------- el detector de picos: lo que tiene que cumplir cualquiera que lo escriba ----------
function detectarDelCurso(t, x, { entrar, salir, refractario }) {
  const picos = [];
  let cur = null, ultimo = -Infinity;
  for (let k = 0; k < t.length; k++) {
    const a = Math.abs(x[k]), s = Math.sign(x[k]);
    if (!cur) {
      if (a > entrar && t[k] - ultimo > refractario) cur = { t: t[k], signo: s, tam: a };
      continue;
    }
    if (s === cur.signo && a > cur.tam) { cur.tam = a; cur.t = t[k]; }
    if (a < salir || s !== cur.signo) { picos.push(cur); ultimo = cur.t; cur = null; }
  }
  return picos;
}

// 10 picos conocidos, de los dos signos y de distinto tamaño, con ruido y un movimiento lento debajo
function diezPicos() {
  const a = azar(2024), t = instantes(12000);
  const verdad = [700, 1800, 2600, 3900, 4700, 5900, 6800, 8100, 9300, 10800].map((s, i) => ({ t: s, signo: i % 3 === 1 ? -1 : 1, tam: 350 + 45 * i }));
  const x = t.map((s) => verdad.reduce((v, p) => v + campana(s, p.t, p.signo * p.tam, 30), 0) + 30 * Math.sin(2 * Math.PI * 0.6 * s / 1000) + 8 * a.normal());
  return { t, x, verdad };
}

function probar(detectar, nombre) {
  console.log(`Detector de picos (${nombre})`);
  const { t, x, verdad } = diezPicos();
  const opc = { entrar: 200, salir: 100, refractario: 90 };
  const picos = detectar(t, x, opc);
  assert.strictEqual(picos.length, 10, `hay 10 picos y contaste ${picos.length}`);
  ok('en una señal con 10 picos conocidos y ruido cuenta exactamente 10');
  picos.forEach((p, i) => {
    near(p.t, verdad[i].t, 30, `el pico ${i + 1} está en su instante`);
    assert.strictEqual(p.signo, verdad[i].signo, `el pico ${i + 1} tiene su signo`);
    near(p.tam, verdad[i].tam, 60, `el pico ${i + 1} tiene su tamaño`);
  });
  ok('cada pico sale con su instante (±30 ms), su signo y su tamaño');

  const h = D.histeresis;
  const conDos = detectar(h.t, h.wx, { entrar: h.entrar, salir: h.salir, refractario: 0 });
  assert.strictEqual(conDos.length, 1, `un temblor en el borde del umbral debe contar 1, y contó ${conDos.length}`);
  ok('un temblor en el borde del umbral no cuenta dos veces: histéresis');

  const r = D.refractario, umbrales = { entrar: 200, salir: 100 };
  const sinEspera = detectar(r.t, r.wx, { ...umbrales, refractario: 0 }), conEspera = detectar(r.t, r.wx, { ...umbrales, refractario: 90 });
  assert.strictEqual(sinEspera.length, 2, `sin espera, el rebote es otro pico (contó ${sinEspera.length})`);
  assert.strictEqual(conEspera.length, 1, `con 90 ms, el rebote no cuenta (contó ${conEspera.length})`);
  ok('el rebote cuenta sin espera y no cuenta con 90 ms: periodo refractario');

  assert.strictEqual(detectar(t, x.map((v) => v / 100), opc).length, 0, 'si nada pasa el umbral, no hay picos');
  ok('si nada pasa el umbral, no hay picos');
}

if (process.argv.includes('--ejercicio')) {
  probar(require(path.join(raiz, 'docs', 'curso', 'ejercicios', 'cap10.js')).detectar, 'tu ejercicio');
  console.log('\nTodo pasa.');
  process.exit(0);
}
probar(detectarDelCurso, 'del curso');

// ---------- el detector de verdad: lo que el capítulo dice de flick.js ----------
console.log('El detector de giros (flick.js)');
assert.deepStrictEqual([FLICK_DEFAULTS.minOn, FLICK_DEFAULTS.rel, FLICK_DEFAULTS.dominance, FLICK_DEFAULTS.refractory], [70, 0.35, 1.3, 90]);
ok('sus números son 70 °/s, 0.35, 1.3 y 90 ms');

{
  const { t, x } = diezPicos();
  const r = correr(new FlickDetector({ minOn: 200, rel: 0 }), t, x.map((v) => [v, 0, 0]));
  const mios = detectarDelCurso(t, x, { entrar: 200, salir: 100, refractario: 90 });
  assert.deepStrictEqual(r.eventos.map((e) => [e.t, e.dir]), mios.map((p) => [p.t, p.signo]));
  ok('FlickDetector y el detector del ejercicio dan los mismos 10 picos, en el mismo instante');
}

{
  const e = D.pico.eventos;
  assert.strictEqual(e.length, 2);
  assert.deepStrictEqual(e.map((x) => x.dir), [1, -1]);
  near(e[0].t, 800, 10, 'el primer giro está en su instante');
  near(D.pico.umbral[D.pico.umbral.length - 1], 0.35 * Math.max(e[0].pico, e[1].pico), 0.1, 'el umbral sale de la mediana');
  near(e[0].pico, 693, 0.5, 'el tamaño del primer giro');
  assert.strictEqual(e[0].fin - e[0].t, 80, 'el detector se entera 80 ms después del máximo');
  ok(`un pico es un evento: t = ${e[0].t / 1000} s, signo +, ${e[0].pico} °/s, 80 ms antes de cerrarse; y el segundo, signo −`);
}

assert.strictEqual(D.histeresis.unSolo.length, 3, 'un solo umbral cuenta 3');
assert.strictEqual(D.histeresis.dos.length, 1, 'dos umbrales cuentan 1');
ok(`histéresis: con un umbral ${D.histeresis.unSolo.length} giros, con dos ${D.histeresis.dos.length}`);

assert.strictEqual(D.refractario.sin.length, 2);
assert.strictEqual(D.refractario.con.length, 1);
assert.strictEqual(D.refractario.reboteLargo.length, 2);
ok('el rebote: 2 eventos sin espera, 1 con 90 ms, y 2 si sigue fuerte después de la espera');

{
  const { fuerte, suave } = D.adaptar;
  assert.deepStrictEqual(fuerte.adaptado, { giros: 12, deSobra: 0 });
  assert.deepStrictEqual(suave.adaptado, { giros: 12, deSobra: 0 });
  assert.strictEqual(fuerte.fijo70.deSobra, 12);
  assert.strictEqual(suave.fijo300.giros, 0);
  near(fuerte.umbral[fuerte.umbral.length - 1], 310, 1, 'el umbral de la fuerte');
  near(suave.umbral[suave.umbral.length - 1], 83, 1, 'el umbral de la suave');
  ok(`el umbral se adapta: la fuerte termina en ${fuerte.umbral[fuerte.umbral.length - 1]} °/s y la suave en ${suave.umbral[suave.umbral.length - 1]} °/s, las dos con 12 de 12`);
  ok('fijo en 70 a la fuerte le sobran 12; fijo en 300 a la suave le cuenta 0');
  assert.strictEqual(D.trabado.suaves, 0);
  assert.strictEqual(D.trabado.fuertes, 13);
  near(D.trabado.umbral, 315, 0.5, 'el umbral trabado');
  ok(`solo se mueve con los giros aceptados: después de ${D.trabado.fuertes} giros fuertes queda en ${D.trabado.umbral} °/s y ninguno suave lo baja`);
}

{
  const det = new FlickDetector();
  assert.strictEqual(det.threshold(), 70);
  det.peaks = [100, 100, 100];
  assert.strictEqual(det.threshold(), 70);
  det.peaks = [300, 1000, 500];
  near(det.threshold(), 175, 1e-9, '0.35 de la mediana');
  ok('el umbral es máx(70, 0.35·mediana): 70 con picos chicos, 175 con mediana 500');
}

{
  const c = D.dominancia.casos;
  assert.ok(c.every((x) => x.acepta === (x.wx >= 1.3 * x.otro)), 'acepta justo cuando |ω_x| ≥ 1.3 × el otro');
  assert.ok(c.filter((x) => x.tipo === 'muneca').every((x) => x.acepta));
  assert.ok(c.filter((x) => x.tipo === 'brazo').every((x) => !x.acepta));
  ok('dominancia: pasan los 16 giros de muñeca y ninguno de los 16 del brazo, justo en la recta de 1.3');
}

{
  const m = D.tornillo;
  assert.strictEqual(m.eventos.length, 8);
  near(m.picoIda, 714, 1, 'el clic del mocap');
  near(m.picoVuelta, 567, 1, 'la vuelta');
  near(m.otroMax, 68, 1, 'los otros ejes');
  near(m.picoIda / 117, 6, 0.2, 'unas seis veces lo de apuntar');
  assert.ok(m.eventos.every((e, i) => i % 2 === 0 || e.t - m.eventos[i - 1].t > 90), 'la vuelta llega a más de 90 ms del máximo');
  ok(`el clic del mocap: 8 giros en 4 clics, ${m.picoIda} °/s de ida, ${m.picoVuelta} de vuelta y ${m.otroMax} en los otros ejes`);
  const mocap = fuente('server', 'web', 'mocapmath.js');
  tiene(mocap, 'click = env(u, 0.75, 0.82, 0.86, 0.95)', 'mocapmath.js');
  tiene(mocap, 'pron: 70 + 35 * a.click', 'mocapmath.js');
  tiene(fuente('server', 'web', 'tempo.js'), 'const COMMAND_DPS = 200;', 'tempo.js');
  ok('el mocap gira 35° en 70 ms, y tempo.js pide 200 °/s para un comando');
}

// ---------- el empujón: la copia de game.js sigue siendo game.js ----------
console.log('El empujón (game.js)');
{
  const g = fuente('server', 'web', 'game.js');
  for (const trozo of ['const PUSH_ON = 4.0;', 'af < PUSH_ON * 0.4', 't - S.push.t0 > 220', 'S.refractoryUntil = now + 350', '<= t - 120',
    'Math.max(12, 1.1 * sorted[Math.floor(0.8 * (sorted.length - 1))])', '(power - PUSH_ON) / Math.max(1, S.pmax - PUSH_ON)',
    'const af = (v.x - S.grav[0]) * AXIS[0] + (v.y - S.grav[1]) * AXIS[1] + (v.z - S.grav[2]) * AXIS[2]']) tiene(g, trozo, 'game.js');
  ok('las constantes de datos_cap10.js son las de game.js: 4 m/s², 0.4, 220 ms, 350 ms, 120 ms, 12 y 1.1');
  const e = D.empujon;
  near(e.miraAntes, e.miraBuena, 0.5, 'la mira de 120 ms antes');
  near(e.miraCruce, 8.9, 0.05, 'la mira al cruzar');
  near(e.miraFin, 14.9, 0.05, 'la mira al terminar');
  ok(`la mira: ${e.miraAntes}° 120 ms antes, ${e.miraCruce}° al cruzar, ${e.miraFin}° al terminar (la buena era ${e.miraBuena}°)`);
  const det = new Empujon();
  const pegar = (t0, a) => { let ev = null; for (let t = t0; t < t0 + 300; t += 10) ev = det.feed(t, campana(t, t0 + 100, a, 50)) || ev; return ev; };
  const uno = pegar(0, 16), doble = pegar(310, 16), tres = pegar(1000, 16);
  assert.ok(uno && tres);
  assert.strictEqual(doble, null, 'dentro de 350 ms no acepta otro');
  ok('350 ms después de un empujón no acepta otro');
  const fuerza = new Empujon();
  for (let i = 0; i < 12; i++) { let t = 1000 * i; for (let k = 0; k < 30; k++, t += 10) fuerza.feed(t, campana(t, 1000 * i + 100, 30, 50)); }
  near(fuerza.pmax, 33, 0.5, 'la escala es 1.1 × el percentil 80');
  ok(`la fuerza se adapta: con empujones de 30 m/s² la escala queda en ${fuerza.pmax.toFixed(1)} m/s² (mínimo 12)`);
}

// ---------- el tempo ----------
console.log('El tempo');
{
  const t = D.tempo;
  assert.strictEqual(t.eventos.length, 7);
  near(t.bpm, 60000 / t.mediana, 0.1, 'BPM = 60000 / mediana');
  near(t.bpm, 117.6, 0.05, 'la mediana da 117.6');
  near(t.promedio, 583, 1, 'el promedio de los intervalos');
  near(t.bpmPromedio, 102.9, 0.05, 'el promedio se deja arrastrar');
  assert.strictEqual(t.mediana, t.orden[3], 'de seis intervalos el detector toma el cuarto');
  ok(`siete giros: la mediana da ${t.bpm} por minuto y el promedio ${t.bpmPromedio}, y de verdad eran 120`);
  const det = new FlickDetector();
  det.beats = [0, 500];
  assert.strictEqual(det.tempo(), null);
  det.beats = [0, 500, 1000];
  assert.strictEqual(det.tempo(1000 + 2600), null);
  near(det.tempo(1100), 120, 1e-9, 'con 3 giros ya hay tempo');
  ok('hacen falta 3 giros, y a los 2500 ms sin giros el tempo se apaga');
}

// ---------- aciertos, falsas alarmas y AUC ----------
console.log('Aciertos contra falsas alarmas');
{
  const { pellizco, giro, minutos } = D.barrido;
  assert.strictEqual(pellizco.pos.length, 20);
  assert.strictEqual(pellizco.neg.length, 40 * minutos);
  assert.strictEqual(giro.aciertosSinFalsas, 20);
  assert.strictEqual(pellizco.aciertosSinFalsas, 10);
  near(pellizco.auc, 0.75, 0.005, 'el AUC del pellizco');
  near(giro.auc, 1, 1e-9, 'el AUC del giro');
  ok(`sin ninguna falsa alarma, con datos inventados: pellizco ${pellizco.aciertosSinFalsas} de 20, giro ${giro.aciertosSinFalsas} de 20`);
  for (const g of [pellizco, giro]) {
    const c = g.curva;
    assert.ok(c.every((p, i) => i === 0 || (p[0] >= c[i - 1][0] && p[1] >= c[i - 1][1])), 'bajar el umbral nunca quita aciertos ni falsas alarmas');
    const fx = c.map((p) => p[0] / c[c.length - 1][0]), fy = c.map((p) => p[1] / 20);
    let area = 0;
    for (let i = 1; i < c.length; i++) area += (fx[i] - fx[i - 1]) * (fy[i] + fy[i - 1]) / 2;
    near(area, g.auc, 1e-9, `el área bajo la curva del ${g.nombre} es el AUC`);
  }
  ok('bajar el umbral solo suma: más aciertos y más falsas alarmas');
  ok(`el área bajo la curva es P(positivo > negativo): ${pellizco.auc.toFixed(2)} el pellizco, ${giro.auc.toFixed(2)} el giro`);
  near(auc([1, 2, 3], [0, 0.5]), 1, 1e-12, 'separar todo es 1');
  near(auc([1, 1], [1, 1]), 0.5, 1e-12, 'no distinguir nada es 0.5');
  near(auc([2, 0], [1]), 0.5, 1e-12, 'la mitad');
  const a = azar(5), grupo = () => Array.from({ length: 2000 }, () => a.normal());
  near(auc(grupo(), grupo()), 0.5, 0.03, 'dos grupos iguales');
  ok('AUC: 0.5 es no distinguir nada, 1 es separar todo; los empates valen la mitad');
  tiene(fuente('tools', 'analyze_drawing.py'), 'np.mean([(p > neg).mean() + 0.5 * (p == neg).mean() for p in pos])', 'analyze_drawing.py');
  ok('auc de analyze_drawing.py hace esa misma cuenta');
  near(D.muestreo.pellizco.peor, 0, 1e-9, 'el golpe puede caer entre dos muestras');
  near(D.muestreo.giro.peor, 0.986, 0.001, 'el giro se ve casi entero');
  ok(`una muestra cada 10 ms: del golpe se ve entre ${100 * D.muestreo.pellizco.peor} % y ${100 * D.muestreo.pellizco.mejor} %, del giro al menos ${(100 * D.muestreo.giro.peor).toFixed(1)} %`);
}

// ---------- tools/air_mouse.py: los detectores de verdad, si hay Python ----------
console.log('Toque, sacudida, permanencia y scroll (air_mouse.py)');
{
  const guion = path.join(raiz, 'docs', 'curso', 'animaciones', 'datos_cap10.py');
  let salida = null;
  for (const py of ['python', 'python3']) {
    const r = spawnSync(py, ['-I', guion], { encoding: 'utf8', maxBuffer: 1 << 26 });
    if (r.status === 0) { salida = r.stdout; break; }
  }
  if (salida === null) {
    console.log('  (no hay Python: estas pruebas se saltan)');
  } else {
    const P = JSON.parse(salida);
    const [bueno, antes, despues, postura] = P.toques;
    assert.strictEqual(bueno.veredicto, 'confirmado');
    assert.strictEqual(bueno.t_decide - bueno.t_cand, 250);
    assert.strictEqual(antes.veredicto, 'giro');
    assert.strictEqual(antes.armado, false);
    assert.strictEqual(despues.veredicto, 'giro');
    assert.strictEqual(despues.armado, true);
    assert.strictEqual(postura.veredicto, 'forma');
    ok('toque: se decide 250 ms después; giro antes, giro después o un cambio de postura no son toque');

    const s = P.sacudidas;
    assert.strictEqual(s.fuerte.fuegos.length, 1);
    assert.strictEqual(s.lenta.fuegos.length, 0);
    assert.strictEqual(s.giro.fuegos.length, 0);
    const primero = s.barrido.find((b) => b.dispara).hz;
    assert.strictEqual(primero, 2.5);
    ok(`sacudida: dispara desde ${primero} idas y vueltas por segundo, no a 2, y nunca con un solo giro`);

    const p = P.permanencia;
    assert.strictEqual(p.fuegos.length, 1);
    assert.ok(p.fuegos[0] > 1800 && p.fuegos[0] < 2500);
    ok(`permanencia: un clic a los ${p.fuegos[0] / 1000} s; quieto antes de viajar no cuenta, y quieto después no se repite`);

    const c = P.scroll;
    assert.deepStrictEqual(c.lento.muescas.map((m) => Math.abs(m.n)), [1, 1, 1]);
    assert.strictEqual(c.lento.entradas.length, 1);
    assert.strictEqual(c.lento.salidas.length, 1);
    assert.deepStrictEqual(c.rapido.entradas, []);
    assert.ok(c.rapido.rechazos['rápido'] > 0);
    assert.deepStrictEqual(c.sin_pausa.entradas, []);
    assert.ok(c.sin_pausa.rechazos['sin pausa previa'] > 0);
    assert.deepStrictEqual([c.entrar, c.salir, c.muesca, c.tasa_max], [25, 15, 6, 120]);
    ok(`scroll: entra en 25°, sale en 15°, 3 muescas en 46°; rechaza lo rápido y lo que no viene de una pausa`);
    near(P.postura.entra, 60.5, 0.1, 'brazo caído');
    near(P.postura.sale, 53.1, 0.1, 'brazo caído');
    ok(`la postura del brazo también tiene histéresis: entra a ${P.postura.entra}° y sale a ${P.postura.sale}°`);
  }
}
console.log('\nTodo pasa.');
