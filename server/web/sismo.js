// Sismógrafo: el juego. Una línea viene corriendo por el papel y tu muñeca mueve la aguja: mantenla encima.
//
// Es una "tarea de seguimiento" de las que usaba McRuer en los años 60 para medir a los pilotos: la línea
// es una suma de senos imprevisible (sismomath.js) y al final se ve, frecuencia por frecuencia, cuánto de
// cada onda seguiste y con cuánto retraso. Tu cuerpo cierra el lazo (ves el error, corriges ~200 ms
// después) sin que lo pienses; aquí se mide ese lazo.
//
//   Botón atrás del reloj, Espacio o un toque: empezar. Bisel o 1 2 3: nivel. E: eje (inclinar, girar,
//   atornillar). V: ver la línea que viene o ir a ciegas. M: muñeca. R: recentrar.
'use strict';

const { T, LEAD, LEVELS, makeTarget, targetAt, analyze } = SismoMath;
const AXES = [
  { key: 'pitch', name: 'inclinar', how: 'sube y baja la muñeca', deg: 25 },
  { key: 'yaw', name: 'girar', how: 'mueve la muñeca a la derecha (sube) y a la izquierda (baja)', deg: 25 },
  { key: 'roll', name: 'atornillar', how: 'atornilla (sube) y desatornilla (baja)', deg: 60 },
];
const BAND = 0.12;                      // media anchura de la banda, en medias alturas (3° inclinando)
const PX_S = 170;                       // el papel corre a 170 px/s
const COUNT = 3;                        // s de cuenta atrás
const C = { line: '#ffd166', in: '#5dcaa5', out: '#f0997b', grid: '#1c2230', text: '#9aa3b2', ink: '#ece9e1', blue: '#58c4dd' };

const wrist = new Wrist();
const S = {
  grav: null, lastT: null, ang: { yaw: 0, pitch: 0, roll: 0 },
  axis: 0, level: 1, preview: true,
  state: 'idle', t0: 0, comps: makeTarget(1), trail: [], result: null,
  connected: false, watch: false, lastSample: 0, hzCount: 0, hz: 0, hzT: performance.now(),
};
const $ = (id) => document.getElementById(id);
try {
  const saved = JSON.parse(localStorage.getItem('gearstream.sismo') || '{}');
  if (saved.axis >= 0 && saved.axis < AXES.length) S.axis = saved.axis;
  if (saved.level >= 0 && saved.level < LEVELS.length) S.level = saved.level;
  if (typeof saved.preview === 'boolean') S.preview = saved.preview;
} catch { /* sin preferencias guardadas */ }
function saveOpts() {
  try { localStorage.setItem('gearstream.sismo', JSON.stringify({ axis: S.axis, level: S.level, preview: S.preview })); } catch { /* nada */ }
}
function bestKey() { return `${AXES[S.axis].key}-${S.level}-${S.preview ? 've' : 'ciega'}`; }
function loadBest() { try { return JSON.parse(localStorage.getItem('gearstream.sismo.best') || '{}'); } catch { return {}; } }

// ---------- la aguja ----------
function onGyro(t, v) {
  if (S.lastT === null || !S.grav) { S.lastT = t; return; }
  let dt = (t - S.lastT) / 1000; S.lastT = t;
  if (!(dt > 0) || dt > 0.1) dt = 0.01;
  const { yaw, pitch, roll } = wrist.rates([v.x, v.y, v.z], S.grav);
  S.ang.yaw -= yaw * dt;                // derecha positiva
  S.ang.pitch += pitch * dt;            // arriba positiva
  if (Math.abs(roll) > 1) S.ang.roll += roll * dt;
  S.hzCount++;
}
function recenter() { S.ang.yaw = 0; S.ang.pitch = 0; S.ang.roll = 0; }
const needle = () => S.ang[AXES[S.axis].key] / AXES[S.axis].deg;          // en medias alturas, + arriba

// ---------- rondas ----------
function start() {
  if (S.state === 'count' || S.state === 'play') return;
  S.comps = makeTarget(S.level);
  S.trail = []; S.result = null;
  recenter();
  S.t0 = performance.now() + COUNT * 1000;
  S.state = 'count';
  $('card').style.display = 'none';
  showOpts();
}
function gameTime(now) { return (now - S.t0) / 1000; }
function finish() {
  const r = analyze(S.trail, S.comps, BAND);
  if (!r) { freeze(); return; }
  S.result = r;
  const best = loadBest(), k = bestKey(), prev = best[k];
  r.best = prev === undefined || r.inBand > prev;
  r.prev = prev;
  if (r.best) { best[k] = r.inBand; try { localStorage.setItem('gearstream.sismo.best', JSON.stringify(best)); } catch { /* nada */ } }
  S.state = 'result';
  showResult();
  showOpts();
}
function freeze(why) {
  S.state = 'frozen';
  $('big').textContent = '';
  $('score').textContent = why || 'el reloj se congeló · toca su pantalla y empieza otra vez';
  showOpts();
}
// con la pestaña escondida el navegador casi no dibuja cuadros: la ronda no se puede medir
document.addEventListener('visibilitychange', () => { if (document.hidden && busy()) freeze('cambiaste de pestaña · empieza otra vez'); });

// ---------- tarjeta del final ----------
function showResult() {
  const r = S.result, ax = AXES[S.axis];
  const pct = Math.round(100 * r.inBand), ms = Math.round(1000 * r.delay);
  $('verdict').textContent = pct >= 85 ? 'Sismógrafo humano' : pct >= 65 ? 'Buen pulso' : pct >= 40 ? 'Ahí vas' : 'Terremoto';
  $('cardsub').textContent = `${ax.name} · ${LEVELS[S.level].name} · ${S.preview ? 'viendo la línea' : 'a ciegas'} · `
    + (r.best ? (r.prev === undefined ? 'primer récord' : `¡récord! (antes ${Math.round(100 * r.prev)} %)`) : `récord: ${Math.round(100 * r.prev)} %`);
  const cell = (v, l) => `<div><b>${v}</b><span>${l}</span></div>`;
  $('nums').innerHTML = cell(`${pct} %`, 'dentro de la banda')
    + cell(`${(r.rms * ax.deg).toFixed(1)}°`, 'error típico')
    + cell(ms >= 0 ? `${ms} ms` : `${-ms} ms`, ms >= 0 ? 'llegas tarde' : 'te adelantas')
    + cell(`${Math.round(100 * r.remnant)} %`, 'ruido tuyo');
  $('explain').innerHTML = 'Cada barra es una de las ondas que formaban la línea, de la lenta a la rápida: su altura es el error que te '
    + 'quedó en esa onda (0 % = la borraste, 100 % = como si no hubieras hecho nada). La curva punteada es lo que predice tu retraso '
    + `solo: con τ = ${Math.abs(ms)} ms, el error crece como <b>2·|sin(π f τ)|</b>. Si las barras se pegan a la curva, tu error es casi `
    + 'solo un retraso (el tuyo más el de la cadena). Si se apartan, hay algo más: seguiste menos o de más, o llegaste tarde distinto '
    + 'en esa onda. El ruido es lo que hiciste fuera de las ondas de la línea; lo muy lento se cuenta como onda, así que es un piso.';
  $('card').style.display = 'block';
  drawChart();
}
function drawChart() {
  const cv = $('chart'), g = cv.getContext('2d'), d = Math.min(devicePixelRatio, 2);
  const W = cv.clientWidth, H = cv.clientHeight;
  cv.width = W * d; cv.height = H * d; g.setTransform(d, 0, 0, d, 0, 0);
  const r = S.result, fs = r.freqs, fmax = Math.max(...fs.map((f) => f.f)) * 1.12;
  const L = 34, B = 30, top = 10, ymax = 1.5;
  const X = (f) => L + (W - L - 8) * f / fmax, Y = (e) => top + (H - top - B) * (1 - Math.min(e, ymax) / ymax);
  g.clearRect(0, 0, W, H);
  g.font = '11px system-ui'; g.fillStyle = C.text; g.strokeStyle = C.grid; g.lineWidth = 1;
  for (const e of [0, 0.5, 1, 1.5]) {
    g.beginPath(); g.moveTo(L, Y(e)); g.lineTo(W - 8, Y(e)); g.stroke();
    g.textAlign = 'right'; g.fillText(`${Math.round(e * 100)}%`, L - 4, Y(e) + 4);
  }
  g.strokeStyle = C.blue; g.setLineDash([4, 4]); g.lineWidth = 1.5; g.beginPath();   // predicción por el retraso
  for (let i = 0; i <= 100; i++) { const f = fmax * i / 100, e = 2 * Math.abs(Math.sin(Math.PI * f * r.delay)); i ? g.lineTo(X(f), Y(e)) : g.moveTo(X(f), Y(e)); }
  g.stroke(); g.setLineDash([]);
  const bw = Math.max(8, Math.min(26, (W - L) / fs.length / 3));
  g.textAlign = 'center';
  for (const f of fs) {
    g.fillStyle = f.error < 0.5 ? C.in : f.error < 1 ? C.line : C.out;
    g.fillRect(X(f.f) - bw / 2, Y(f.error), bw, Y(0) - Y(f.error));
    g.fillStyle = C.text; g.fillText(`${f.f.toFixed(2)}`, X(f.f), H - B + 14);
    g.fillStyle = C.ink; g.fillText(`${Math.round(f.delay * 1000)}`, X(f.f), Y(f.error) - 5);
  }
  g.fillStyle = C.text; g.textAlign = 'left'; g.fillText('Hz (encima de cada barra: tu retraso en ms a esa onda, si es de menos de media vuelta)', L, H - 4);
}

// ---------- botones y teclas ----------
function showOpts() {
  const busy = S.state === 'count' || S.state === 'play';
  $('axis').innerHTML = `<small>eje</small>${AXES[S.axis].name}`;
  $('level').innerHTML = `<small>nivel</small>${LEVELS[S.level].name}`;
  $('preview').innerHTML = `<small>línea</small>${S.preview ? 'la veo venir' : 'a ciegas'}`;
  $('hand').innerHTML = `<small>reloj</small>${handName(wrist.hand)}`;
  for (const id of ['axis', 'level', 'preview', 'hand']) $(id).disabled = busy;
  const best = loadBest()[bestKey()];
  $('help').innerHTML = `<b>${AXES[S.axis].name}</b>: ${AXES[S.axis].how}. Mantén la bola sobre la línea amarilla.`
    + (best !== undefined ? ` Récord aquí: <b>${Math.round(100 * best)} %</b>.` : '')
    + '<br><b>Botón atrás</b> del reloj, Espacio o un toque: empezar · bisel o 1 2 3: nivel · E: eje · V: ver o a ciegas · M: muñeca · R: recentrar';
  if (S.state === 'idle') $('score').textContent = 'Sigue la línea';
}
function setAxis(i) { if (busy()) return; S.axis = (i + AXES.length) % AXES.length; recenter(); saveOpts(); showOpts(); }
function setLevel(i) { if (busy()) return; S.level = Math.max(0, Math.min(LEVELS.length - 1, i)); S.comps = makeTarget(S.level); saveOpts(); showOpts(); }
function togglePreview() { if (busy()) return; S.preview = !S.preview; saveOpts(); showOpts(); }
function toggleHand() { if (busy()) return; wrist.toggleHand(); recenter(); showOpts(); }
const busy = () => S.state === 'count' || S.state === 'play';
$('axis').addEventListener('click', () => setAxis(S.axis + 1));
$('level').addEventListener('click', () => setLevel((S.level + 1) % LEVELS.length));
$('preview').addEventListener('click', togglePreview);
$('hand').addEventListener('click', toggleHand);
$('c').addEventListener('pointerdown', start);
$('card').addEventListener('pointerdown', start);
addEventListener('keydown', (e) => {
  if (e.repeat) return;
  if (e.code === 'Space' || e.key === 'Enter') { e.preventDefault(); start(); }
  else if (e.key === 'e' || e.key === 'E') setAxis(S.axis + 1);
  else if (e.key === 'v' || e.key === 'V') togglePreview();
  else if (e.key === 'm' || e.key === 'M') toggleHand();
  else if (e.key === 'r' || e.key === 'R') recenter();
  else if (['1', '2', '3'].includes(e.key)) setLevel(Number(e.key) - 1);
});
showOpts();

// ---------- datos del reloj ----------
function connect() {
  const ws = new WebSocket(`ws://${location.host}/ui`);
  ws.onopen = () => { S.connected = true; };
  ws.onclose = () => { S.connected = false; S.watch = false; setTimeout(connect, 1500); };
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === 'watch') S.watch = !!msg.connected;
    else if (msg.type === 'hello') { S.watch = true; S.lastT = null; }
    else if (msg.type === 'data' && Array.isArray(msg.samples)) {
      for (const s of msg.samples) {
        if (!Array.isArray(s) || s.length < 3 || !s[2] || typeof s[2] !== 'object') continue;
        const [name, t, v] = s;
        if (name === 'BUTTON') { if (v.key === 'back' && v.pressed === true) start(); continue; }
        if (name === 'BEZEL') { setLevel(S.level + (v.direction === 'CW' ? 1 : -1)); continue; }
        if (typeof v.x !== 'number') continue;
        S.lastSample = performance.now(); S.watch = true;
        if (name === 'GRAVITY') S.grav = [v.x, v.y, v.z];
        else if (name === 'GYROSCOPE') onGyro(t, v);
      }
    }
  };
}
connect();

// ---------- dibujo ----------
const cv = $('c'), g = cv.getContext('2d');
function resize() { const d = Math.min(devicePixelRatio, 2); cv.width = innerWidth * d; cv.height = innerHeight * d; g.setTransform(d, 0, 0, d, 0, 0); }
addEventListener('resize', () => { resize(); if (S.state === 'result') drawChart(); });
resize();

function frame(now) {
  requestAnimationFrame(frame);
  if (now - S.hzT >= 1000) { S.hz = S.hzCount * 1000 / (now - S.hzT); S.hzCount = 0; S.hzT = now; }
  const stale = now - S.lastSample > 600;
  const W = innerWidth, H = innerHeight, cy = H * 0.54, half = H * 0.36, x0 = Math.min(W * 0.3, 420);
  const toY = (u) => cy - u * half;
  const playing = S.state === 'count' || S.state === 'play';
  const tg = playing ? gameTime(now) : S.state === 'idle' ? -1 : (S.trail.length ? S.trail[S.trail.length - 1].t : 0);
  const y = needle();

  if (S.state === 'count' && tg >= 0) S.state = 'play';
  if (S.state === 'play') {
    if (stale) freeze();
    else {
      S.trail.push({ t: tg, y });
      if (tg >= LEAD + T + 0.15) finish();
    }
  }

  g.fillStyle = '#10131a'; g.fillRect(0, 0, W, H);
  g.strokeStyle = C.grid; g.lineWidth = 1;                       // papel cuadriculado que corre
  const off = ((tg * PX_S) % 60 + 60) % 60;
  for (let x = -off; x < W; x += 60) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); }
  for (let k = -3; k <= 3; k++) { g.beginPath(); g.moveTo(0, toY(k / 3)); g.lineTo(W, toY(k / 3)); g.stroke(); }

  // la línea: lo que ya pasó a la izquierda de la aguja, lo que viene a la derecha (si se ve)
  const xEnd = S.preview || !playing ? W : x0;
  const lineAt = (x) => targetAt(S.comps, Math.min(tg + (x - x0) / PX_S, LEAD + T + 0.15));
  g.lineCap = 'round'; g.lineJoin = 'round';
  g.strokeStyle = '#ffd1662a'; g.lineWidth = 2 * BAND * half;
  g.beginPath(); for (let x = 0; x <= xEnd; x += 4) { const yy = toY(lineAt(x)); x ? g.lineTo(x, yy) : g.moveTo(x, yy); } g.stroke();
  g.strokeStyle = C.line; g.lineWidth = 2;
  g.beginPath(); for (let x = 0; x <= xEnd; x += 4) { const yy = toY(lineAt(x)); x ? g.lineTo(x, yy) : g.moveTo(x, yy); } g.stroke();
  if (!S.preview && playing) { g.fillStyle = '#ffd16618'; g.fillRect(x0 + 2, 0, W - x0, H); }

  // tu rastro, verde dentro de la banda y coral fuera
  g.lineWidth = 3;
  for (let i = 1; i < S.trail.length; i++) {
    const a = S.trail[i - 1], b = S.trail[i];
    const xa = x0 + (a.t - tg) * PX_S, xb = x0 + (b.t - tg) * PX_S;
    if (xb < 0) continue;
    g.strokeStyle = Math.abs(b.y - targetAt(S.comps, b.t)) <= BAND ? C.in : C.out;
    g.beginPath(); g.moveTo(xa, toY(a.y)); g.lineTo(xb, toY(b.y)); g.stroke();
  }

  // la aguja
  const inside = Math.abs(y - targetAt(S.comps, Math.max(tg, 0))) <= BAND;
  const by = Math.max(14, Math.min(H - 14, toY(y)));
  g.strokeStyle = '#ece9e133'; g.lineWidth = 1; g.beginPath(); g.moveTo(x0, 0); g.lineTo(x0, H); g.stroke();
  g.fillStyle = (playing ? (inside ? C.in : C.out) : C.blue) + '44';
  g.beginPath(); g.arc(x0, by, 20, 0, 2 * Math.PI); g.fill();
  g.fillStyle = playing ? (inside ? C.in : C.out) : C.blue;
  g.beginPath(); g.arc(x0, by, 9, 0, 2 * Math.PI); g.fill();

  // marcador
  if (S.state === 'count') { $('big').textContent = String(Math.ceil(-tg)); }
  else if (S.state === 'play') {
    $('big').textContent = tg < 0.6 ? '¡ya!' : '';
    const meas = S.trail.filter((s) => s.t >= LEAD);
    const ok = meas.filter((s) => Math.abs(s.y - targetAt(S.comps, s.t)) <= BAND).length;
    const left = Math.max(0, LEAD + T - tg);
    $('score').textContent = meas.length ? `${Math.round(100 * ok / meas.length)} % · ${left.toFixed(0)} s` : `${left.toFixed(0)} s`;
  } else $('big').textContent = '';
  if (S.state === 'result') $('score').textContent = '';

  $('conn').textContent = !S.connected ? 'sin servidor: reintentando…' : !S.watch ? 'servidor sí · reloj no conectado'
    : stale ? 'el reloj no manda datos · toca su pantalla' : `reloj · ${S.hz.toFixed(0)} Hz`;
}
requestAnimationFrame(frame);
