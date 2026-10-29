// Tutorial de grabación del dataset de gestos. El servidor ya graba todo lo que llega del reloj (una
// carpeta por sesión); esta página solo dice qué hacer, una línea por paso, y le manda al servidor una
// etiqueta por paso (qué gesto, de cuándo a cuándo, y el instante de cada pitido) que queda en
// labels.jsonl junto a los CSV. Los tiempos son del reloj de esta laptop, igual que los de las muestras.
'use strict';

// los pasos viven en gestures-protocol.json, compartidos con tools/dataset_capture.py (la versión de consola)
let PROTOCOL = 'gestos-v1', PREP_S = 3, STEPS = [];
fetch('gestures-protocol.json').then((r) => r.json()).then((p) => {
  PROTOCOL = p.protocol; PREP_S = p.prep_s; STEPS = p.steps;
  $('line').textContent = `Unos ${Math.round(STEPS.reduce((a, st) => a + (st.secs || st.cues.n * st.cues.period) + PREP_S, 0) / 60)} minutos, ${STEPS.length} pasos. Cada paso es una línea: mientras se muestra, se graba.`;
});

const $ = (id) => document.getElementById(id);
const S = { i: 0, running: false, paused: false, trial: 0, ws: null, counts: {}, hz: {}, saved: 0, timers: [] };

// ---------- conexión y velocidad de los sensores ----------
function connect() {
  const ws = new WebSocket(`ws://${location.host}/ui`);
  S.ws = ws;
  ws.onclose = () => { S.ws = null; setTimeout(connect, 1500); };
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === 'data' && Array.isArray(msg.samples)) {
      for (const s of msg.samples) if (Array.isArray(s)) S.counts[s[0]] = (S.counts[s[0]] || 0) + 1;
    } else if (msg.type === 'label_ack') {
      S.saved += 1;
      $('saved').textContent = `${S.saved} pasos guardados en ${String(msg.dir || '').split(/[\\/]/).slice(-2).join('/')}`;
    }
  };
}
connect();
let hzT = performance.now();
setInterval(() => {
  const now = performance.now(), dt = (now - hzT) / 1000; hzT = now;
  for (const k of ['ACCELERATION', 'GYROSCOPE', 'GRAVITY']) { S.hz[k] = (S.counts[k] || 0) / dt; S.counts[k] = 0; }
  const low = S.hz.ACCELERATION < 70;
  $('rates').className = low ? 'warn' : '';
  $('rates').innerHTML = !S.ws ? 'sin servidor' : (S.hz.ACCELERATION || 0) < 1
    ? 'no llegan datos: conecta el reloj en el lanzador'
    : `acelerómetro <b>${S.hz.ACCELERATION.toFixed(0)} Hz</b> · giroscopio <b>${(S.hz.GYROSCOPE || 0).toFixed(0)} Hz</b>` + (low ? ' · toca la pantalla del reloj' : '');
}, 1000);

function send(label) {
  if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify({ type: 'label', protocol: PROTOCOL, ...label }));
}

// ---------- sonido ----------
let actx = null;
function beep(freq = 880, dur = 0.09) {
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const o = actx.createOscillator(), g = actx.createGain();
    o.frequency.value = freq; g.gain.setValueAtTime(0.2, actx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + dur);
    o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime + dur);
  } catch { /* sin audio */ }
}

// ---------- pasos ----------
const later = (ms, fn) => { const t = setTimeout(fn, ms); S.timers.push(t); return t; };
function clearTimers() { S.timers.forEach(clearTimeout); S.timers = []; cancelAnimationFrame(S.raf); }

function stepDuration(st) { return st.cues ? st.cues.n * st.cues.period + 0.6 : st.secs; }

function runStep() {
  clearTimers();
  if (S.i >= STEPS.length) return finish();
  const st = STEPS[S.i];
  S.running = true;
  $('start').style.display = 'none';
  $('step').textContent = `paso ${S.i + 1} de ${STEPS.length}`;
  $('line').textContent = st.line; $('line').className = 'prep';
  $('metro').style.display = st.metronome ? 'block' : 'none';
  $('fill').style.width = '0%';
  for (let k = 0; k < PREP_S; k++) later(k * 1000, () => { $('state').textContent = `prepárate… ${PREP_S - k}`; });
  later(PREP_S * 1000, () => record(st));
}

function record(st) {
  const dur = stepDuration(st) * 1000, t0 = Date.now(), p0 = performance.now(), cues = [];
  S.trial += 1;
  $('line').className = '';
  $('state').innerHTML = '<span class="rec">● grabando</span>';
  beep(440, 0.2);
  if (st.cues) {
    for (let k = 0; k < st.cues.n; k++) {
      later(300 + k * st.cues.period * 1000, () => {
        cues.push(Date.now()); beep();
        $('now').style.opacity = 1; later(250, () => { $('now').style.opacity = 0; });
      });
    }
  }
  const tick = () => {
    const k = Math.min(1, (performance.now() - p0) / dur);
    $('fill').style.width = `${(100 * k).toFixed(1)}%`;
    if (st.metronome) {                                   // bola: arriba y abajo con un seno a la frecuencia pedida
      const y = 0.5 - 0.5 * Math.cos(2 * Math.PI * st.metronome * (performance.now() - p0) / 1000);
      $('ball').style.top = `${(1 - y) * 196}px`;
    }
    if (k < 1) S.raf = requestAnimationFrame(tick);
  };
  S.raf = requestAnimationFrame(tick);
  later(dur, () => {
    send({ id: `${st.id}-${S.trial}`, step: st.id, line: st.line, trial: S.trial, t0, t1: Date.now(), cues_ms: cues,
           metronome_hz: st.metronome || null, hz: { ...S.hz } });
    beep(660, 0.12);
    S.i += 1;
    if (S.paused) { pauseScreen(); return; }
    runStep();
  });
}

function pauseScreen() {
  clearTimers(); S.running = false;
  $('state').textContent = 'en pausa · Espacio para seguir';
  $('metro').style.display = 'none';
}

function finish() {
  S.running = false;
  $('step').textContent = 'listo';
  $('line').textContent = '¡Dataset grabado! Gracias.';
  $('line').className = '';
  $('state').textContent = 'Cada paso quedó etiquetado junto a los datos de la sesión.';
  $('metro').style.display = 'none';
  $('fill').style.width = '100%';
  send({ id: `fin-${Date.now()}`, step: '_fin', t0: Date.now(), t1: Date.now() });
}

// ---------- teclado ----------
function startOrToggle() {
  if (!S.running && S.i === 0 && !S.started) {
    S.started = true;
    send({ id: `inicio-${Date.now()}`, step: '_inicio', t0: Date.now(), t1: Date.now(), steps: STEPS });
    return runStep();
  }
  if (S.running) {                                    // pausar: si estaba grabando, ese paso se repite
    S.paused = true; pauseScreen();
  } else if (S.i < STEPS.length) {
    S.paused = false; runStep();
  }
}
$('start').addEventListener('click', startOrToggle);
addEventListener('keydown', (e) => {
  if (e.code === 'Space') { e.preventDefault(); startOrToggle(); }
  else if (e.key === 'r' || e.key === 'R') {         // repetir el paso anterior: la etiqueta vieja queda marcada como descartada
    if (S.i > 0) { S.i -= 1; send({ id: `descartar-${Date.now()}`, step: '_descartar', target_trial: S.trial, t0: Date.now(), t1: Date.now() }); }
    S.paused = false; runStep();
  } else if (e.key === 'ArrowRight' && S.started) {
    S.i += 1; S.paused = false; runStep();
  }
});
