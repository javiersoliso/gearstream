// Tornillo y tempo: el giro del antebrazo (ω_x del reloj) hace girar un tornillo que entra (horario) o
// sale (antihorario) de una tabla, con la rosca: profundidad = ángulo / 360 × paso. Los giros rápidos
// se detectan con flick.js; un giro fuerte (> 200 °/s) es un "comando" que avanza una vuelta entera, y
// el ritmo de los giros da el tempo. Con el tempo fijado suena un metrónomo a ese ritmo.
'use strict';

const COMMAND_DPS = 200;              // °/s: un giro así es intencional (apuntando con el ratón nunca pasaste de 117)
const PITCH_PX = 14;                  // px que avanza el tornillo por vuelta (en el dibujo)
const MAX_TURNS = 9;                  // vueltas hasta quedar entero dentro

const det = new FlickDetector();
const S = { bias: [0, 0, 0], depthTurns: 0, flashes: [], dots: [], connected: false, watch: false, lastSample: 0,
            hzCount: 0, hz: 0, hzT: performance.now(), locked: null, metroNext: 0 };
const $ = (id) => document.getElementById(id);

// ---------- sonido ----------
let actx = null;
function tick(freq, dur = 0.05, vol = 0.18) {
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const o = actx.createOscillator(), g = actx.createGain();
    o.frequency.value = freq; g.gain.setValueAtTime(vol, actx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + dur);
    o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime + dur);
  } catch { /* sin audio */ }
}

// ---------- datos ----------
let lastAngle = 0;
function onGyro(t, v) {
  const raw = [v.x, v.y, v.z];
  const w = raw.map((x, i) => x - S.bias[i]);
  if (Math.hypot(...w) < 2) for (let i = 0; i < 3; i++) S.bias[i] += 0.003 * (raw[i] - S.bias[i]);
  const f = det.update(t, w);
  const turned = (det.angle - lastAngle) / 360; lastAngle = det.angle;
  S.depthTurns = Math.max(0, Math.min(MAX_TURNS, S.depthTurns + turned));
  if (f) {
    S.dots.push({ t: performance.now(), dir: f.dir, peak: f.peak }); if (S.dots.length > 24) S.dots.shift();
    tick(f.dir > 0 ? 1100 : 700);
    if (f.peak >= COMMAND_DPS) {
      S.depthTurns = Math.max(0, Math.min(MAX_TURNS, S.depthTurns + f.dir));
      flash(f.dir > 0 ? '⟳ atornillar' : '⟲ desatornillar', f.dir > 0 ? '#58c4dd' : '#f0997b');
    }
  }
  S.hzCount++;
}

function flash(text, color) {
  const el = $('flash'); el.textContent = text; el.style.color = color; el.style.opacity = 1;
  clearTimeout(flash.t); flash.t = setTimeout(() => { el.style.opacity = 0; }, 500);
}

function toggleLock() {
  if (S.locked) { S.locked = null; return; }
  const bpm = det.tempo(performance.timeOrigin + performance.now());
  if (bpm) { S.locked = bpm; S.metroNext = performance.now(); }
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ui`);
  ws.onopen = () => { S.connected = true; };
  ws.onclose = () => { S.connected = false; S.watch = false; setTimeout(connect, 1500); };
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === 'watch') S.watch = !!msg.connected;
    else if (msg.type === 'data' && Array.isArray(msg.samples)) {
      for (const s of msg.samples) {
        if (!Array.isArray(s) || s.length < 3 || !s[2] || typeof s[2] !== 'object') continue;
        const [name, t, v] = s;
        if (name === 'BUTTON') { if (v.key === 'back' && v.pressed === true) toggleLock(); continue; }
        if (name === 'GYROSCOPE' && typeof v.x === 'number') { S.lastSample = performance.now(); S.watch = true; onGyro(t, v); }
      }
    }
  };
}
connect();
addEventListener('keydown', (e) => {
  if (e.code === 'Space') { e.preventDefault(); toggleLock(); }
  if (e.key === 'i' || e.key === 'I') { det.o.sign = -det.o.sign; flash(det.o.sign > 0 ? 'sentido normal' : 'sentido invertido', '#ece9e1'); }
  if (e.key === '0') S.depthTurns = 0;
});

// ---------- dibujo ----------
const cv = $('c'), ctx = cv.getContext('2d');
function resize() { const d = Math.min(devicePixelRatio, 2); cv.width = innerWidth * d; cv.height = innerHeight * d; ctx.setTransform(d, 0, 0, d, 0, 0); }
addEventListener('resize', resize); resize();

function drawHead(cx, cy, r, ang) {          // cabeza vista desde arriba, con la ranura en cruz girando
  ctx.save(); ctx.translate(cx, cy);
  ctx.fillStyle = '#2a3242'; ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.fill();
  ctx.strokeStyle = '#58c4dd'; ctx.lineWidth = 3; ctx.stroke();
  ctx.rotate(ang * Math.PI / 180);
  ctx.fillStyle = '#0f1218';
  ctx.fillRect(-r * 0.75, -r * 0.12, r * 1.5, r * 0.24);
  ctx.fillRect(-r * 0.12, -r * 0.75, r * 0.24, r * 1.5);
  ctx.restore();
}

function drawSide(x, yBoard, turns, ang) {   // vista lateral: tabla y tornillo con rosca que avanza
  const W = 220, boardH = 150, len = PITCH_PX * (MAX_TURNS + 1.5), shaft = 22;
  ctx.fillStyle = '#5b4632'; ctx.fillRect(x - W / 2, yBoard, W, boardH);
  ctx.strokeStyle = '#7a5f43'; ctx.lineWidth = 1;
  for (let k = 1; k < 6; k++) { ctx.beginPath(); ctx.moveTo(x - W / 2, yBoard + k * boardH / 6); ctx.lineTo(x + W / 2, yBoard + k * boardH / 6 + 6); ctx.stroke(); }
  const tip = yBoard + turns * PITCH_PX;          // la punta entra en la tabla una rosca por vuelta
  const top = tip - len;
  ctx.fillStyle = '#c9ced8';
  ctx.beginPath(); ctx.moveTo(x - shaft / 2, top); ctx.lineTo(x + shaft / 2, top); ctx.lineTo(x + shaft / 2, tip - 10); ctx.lineTo(x, tip + 8); ctx.lineTo(x - shaft / 2, tip - 10); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = '#8a92a3'; ctx.lineWidth = 2;                // rosca: rayas que se desplazan con el ángulo
  const phase = ((ang % 360) + 360) % 360 / 360 * PITCH_PX;
  for (let y = top + phase; y < tip - 8; y += PITCH_PX) { ctx.beginPath(); ctx.moveTo(x - shaft / 2, y); ctx.lineTo(x + shaft / 2, y + 5); ctx.stroke(); }
  ctx.fillStyle = '#d7dbe3'; ctx.fillRect(x - 34, top - 12, 68, 14);   // cabeza de lado
  ctx.fillStyle = '#9aa3b2'; ctx.font = '13px system-ui'; ctx.textAlign = 'center';
  ctx.fillText(`${turns.toFixed(1)} de ${MAX_TURNS} vueltas dentro`, x, yBoard + boardH + 24);
}

function drawDots(x0, y, w) {                // los últimos giros en el tiempo: azul horario, naranja antihorario
  const now = performance.now(), span = 6000;
  ctx.strokeStyle = '#2a3242'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + w, y); ctx.stroke();
  for (const d of S.dots) {
    const k = 1 - (now - d.t) / span; if (k < 0) continue;
    const r = 4 + Math.min(10, d.peak / 40);
    ctx.fillStyle = d.dir > 0 ? '#58c4dd' : '#f0997b'; ctx.globalAlpha = 0.3 + 0.7 * k;
    ctx.beginPath(); ctx.arc(x0 + w * k, y + (d.dir > 0 ? -10 : 10), r, 0, 2 * Math.PI); ctx.fill();
  }
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#6c7686'; ctx.font = '12px system-ui'; ctx.textAlign = 'right';
  ctx.fillText('ahora', x0 + w, y + 34); ctx.textAlign = 'left'; ctx.fillText('hace 6 s', x0, y + 34);
}

function frame(now) {
  requestAnimationFrame(frame);
  if (now - S.hzT >= 1000) { S.hz = S.hzCount * 1000 / (now - S.hzT); S.hzCount = 0; S.hzT = now; }
  const W = innerWidth, H = innerHeight;
  ctx.clearRect(0, 0, W, H);
  const headR = Math.min(W, H) * 0.13;
  drawHead(W * 0.32, H * 0.42, headR, det.angle);
  drawSide(W * 0.32 + headR * 2.6, H * 0.45, S.depthTurns, det.angle);
  drawDots(W * 0.58, H * 0.78, W * 0.36);
  // velocímetro del giro: barra horizontal con la marca del umbral de comando
  const wx = det.cur ? det.cur.dir * det.cur.peak : 0;
  const bx = W * 0.58, by = H * 0.62, bw = W * 0.36;
  ctx.fillStyle = '#1c2230'; ctx.fillRect(bx, by, bw, 10);
  const k = Math.max(-1, Math.min(1, wx / 400));
  ctx.fillStyle = k > 0 ? '#58c4dd' : '#f0997b';
  ctx.fillRect(bx + bw / 2, by, k * bw / 2, 10);
  ctx.fillStyle = '#ece9e1';
  for (const s of [-1, 1]) ctx.fillRect(bx + bw / 2 + s * (COMMAND_DPS / 400) * bw / 2 - 1, by - 4, 2, 18);
  ctx.fillStyle = '#6c7686'; ctx.font = '12px system-ui'; ctx.textAlign = 'center';
  ctx.fillText(`giro: ${Math.abs(wx).toFixed(0)} °/s · umbral de comando ${COMMAND_DPS}`, bx + bw / 2, by + 30);
  // tempo y metrónomo
  const bpm = det.tempo(performance.timeOrigin + now);
  if (S.locked) {
    $('bpmN').textContent = S.locked.toFixed(0);
    $('bpmS').textContent = `tempo fijado · ${(S.locked / 2).toFixed(0)} ciclos por minuto · Espacio para soltarlo`;
    if (now >= S.metroNext) { tick(1500, 0.03, 0.25); S.metroNext += 60000 / S.locked; if (S.metroNext < now) S.metroNext = now + 60000 / S.locked; }
  } else {
    $('bpmN').textContent = bpm ? bpm.toFixed(0) : '–';
    $('bpmS').textContent = bpm ? `≈ ${(bpm / 2).toFixed(0)} ciclos por minuto (ida y vuelta) · Espacio para fijarlo` : 'gira a un ritmo constante para medirlo';
  }
  const stale = now - S.lastSample > 1500;
  $('conn').textContent = !S.connected ? 'sin servidor: reintentando…' : !S.watch ? 'servidor sí · reloj no conectado'
    : stale ? 'reloj conectado · sin muestras (toca la pantalla del reloj)' : `reloj · ${S.hz.toFixed(0)} Hz${det.o.sign < 0 ? ' · sentido invertido' : ''}`;
}
requestAnimationFrame(frame);
