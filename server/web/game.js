// Revienta globos: apuntas con la muñeca y empujas la mano hacia la pantalla para lanzar un dardo.
// La fuerza del empujón es la profundidad (el eje Z): suave llega cerca, fuerte llega lejos.
//
// Apuntar: las mismas tasas que el ratón aéreo, referidas a la gravedad (yaw alrededor de la vertical,
// pitch alrededor del eje horizontal perpendicular al antebrazo), integradas a ángulos de mira.
// Empujar: aceleración lineal a lo largo del antebrazo, a_f = (ACC − GRAV)·x̂ (x del reloj = hacia la
// mano). Un empujón hacia delante empieza con a_f positiva; un giro brusco de muñeca da centrípeta
// negativa (hacia el codo), así que no dispara. La fuerza se escala sola con tus últimos empujones.
'use strict';

const DEG = Math.PI / 180;
const AXIS = [1, 0, 0];               // antebrazo hacia la mano, en el marco del reloj
const ROUND_S = 60;
const LANES = [                        // profundidad (m), puntos, color
  { d: 3.5, pts: 100, color: 0x5dcaa5, name: 'cerca' },
  { d: 7, pts: 200, color: 0xffd166, name: 'medio' },
  { d: 11, pts: 300, color: 0xf0997b, name: 'lejos' },
];
const PUSH_ON = 4.0;                   // m/s² a lo largo del antebrazo para empezar un empujón
const AIM_LIMIT = { yaw: 30, pitch: 18 };

// ---------- estado ----------
const S = {
  grav: null, bias: [0, 0, 0], lastGyroT: null,
  yaw: 0, pitch: 0, aimHist: [],       // mira (grados) y su historia para lanzar con la mira de antes del empujón
  push: null, refractoryUntil: 0, peaks: [], pmax: 25, live: 0,
  playing: false, score: 0, combo: 0, tEnd: 0, best: 0,
  connected: false, watch: false, hz: 0, hzCount: 0, hzT: performance.now(), lastSample: 0,
};
try { S.best = Number(localStorage.getItem('gearstream-globos-best')) || 0; } catch { /* sin almacenamiento */ }

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => Math.hypot(a[0], a[1], a[2]);

// ---------- escena ----------
const canvas = document.getElementById('gl');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x10141c);
scene.fog = new THREE.Fog(0x10141c, 9, 22);
const camera = new THREE.PerspectiveCamera(60, 1, 0.05, 60);
camera.position.set(0, 1.6, 0);
camera.lookAt(0, 1.6, -1);
scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 0.9));
const sun = new THREE.DirectionalLight(0xffffff, 0.6); sun.position.set(2, 5, 2); scene.add(sun);
const grid = new THREE.GridHelper(40, 40, 0x2c3a52, 0x1f2a3c); grid.position.z = -10; scene.add(grid);
for (const lane of LANES) {            // un anillo en el suelo por carril: da la profundidad a simple vista
  const ring = new THREE.Mesh(new THREE.RingGeometry(lane.d - 0.04, lane.d + 0.04, 96, 1, Math.PI * 1.25, Math.PI * 0.5),
    new THREE.MeshBasicMaterial({ color: lane.color, transparent: true, opacity: 0.35, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2; ring.position.set(0, 0.01, 0); scene.add(ring);
}
function resize() {
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
}
addEventListener('resize', resize); resize();

function aimDir(yawDeg, pitchDeg) {    // yaw positivo = derecha, pitch positivo = arriba
  const y = yawDeg * DEG, p = pitchDeg * DEG;
  return new THREE.Vector3(Math.sin(y) * Math.cos(p), Math.sin(p), -Math.cos(y) * Math.cos(p));
}

// ---------- globos ----------
const balloons = [];
const balloonGeo = new THREE.SphereGeometry(1, 24, 16);
function spawnBalloon() {
  const lane = LANES[Math.floor(Math.random() * LANES.length)];
  const dir = aimDir((Math.random() * 2 - 1) * 22, -8 + Math.random() * 20);
  const r = 0.32 + 0.06 * Math.random();
  const mesh = new THREE.Mesh(balloonGeo, new THREE.MeshStandardMaterial({ color: lane.color, roughness: 0.35, metalness: 0.05 }));
  mesh.scale.set(r, r * 1.15, r);
  mesh.position.copy(camera.position).addScaledVector(dir, lane.d);
  const string = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, -1.1, 0), new THREE.Vector3(0, -2.6, 0)]),
    new THREE.LineBasicMaterial({ color: 0xcccccc, transparent: true, opacity: 0.5 }));
  mesh.add(string);
  scene.add(mesh);
  balloons.push({ mesh, lane, r, born: performance.now(), life: 6000 + Math.random() * 2000, phase: Math.random() * 6 });
}
function removeBalloon(b) { scene.remove(b.mesh); balloons.splice(balloons.indexOf(b), 1); }

const bits = [];
function pop(b) {
  const c = b.lane.color;
  for (let i = 0; i < 14; i++) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.05, 6, 4), new THREE.MeshBasicMaterial({ color: c, transparent: true }));
    m.position.copy(b.mesh.position);
    const v = new THREE.Vector3(Math.random() - 0.5, Math.random() - 0.3, Math.random() - 0.5).normalize().multiplyScalar(2 + Math.random() * 2);
    scene.add(m); bits.push({ m, v, t: 0 });
  }
  removeBalloon(b);
  sound(520 + 120 * LANES.indexOf(b.lane), 0.12, 'triangle');
}

// ---------- dardos ----------
const darts = [];
const dartGeo = new THREE.SphereGeometry(0.07, 12, 8);
function throwDart(power, yawDeg, pitchDeg) {
  const u = Math.max(0, Math.min(1, (power - PUSH_ON) / Math.max(1, S.pmax - PUSH_ON)));
  const depth = 2 + 10.5 * u;
  const dir = aimDir(yawDeg, pitchDeg);
  const m = new THREE.Mesh(dartGeo, new THREE.MeshBasicMaterial({ color: 0xffffff }));
  m.position.copy(camera.position).addScaledVector(dir, 0.4);
  scene.add(m);
  darts.push({ m, dir, depth, t: 0, dur: 0.18 + depth / 28 });
  showLast(u);
  sound(300 + 400 * u, 0.06, 'sine');
}
function landDart(d) {
  let hit = null, best = Infinity;
  for (const b of balloons) {
    const v = b.mesh.position.clone().sub(camera.position);
    const along = v.dot(d.dir);
    const lateral = v.clone().addScaledVector(d.dir, -along).length();
    const depthErr = Math.abs(along - d.depth);
    if (lateral < b.r + 0.3 && depthErr < 1.7 && depthErr < best) { best = depthErr; hit = b; }
  }
  if (hit) {
    S.combo += 1;
    const pts = hit.lane.pts * (S.combo >= 3 ? 2 : 1);
    if (S.playing) S.score += pts;
    toast(`+${pts}${S.combo >= 3 ? ' racha ×2' : ''}`, hit.lane.color);
    pop(hit);
  } else {
    S.combo = 0;
  }
}

// ---------- sonido ----------
let actx = null;
function sound(freq, dur, type) {
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const o = actx.createOscillator(), g = actx.createGain();
    o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(0.15, actx.currentTime); g.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + dur);
    o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime + dur);
  } catch { /* sin audio */ }
}

// ---------- HUD ----------
const $ = (id) => document.getElementById(id);
function toast(text, color) {
  const el = $('toast'); el.textContent = text; el.style.color = '#' + color.toString(16).padStart(6, '0');
  el.style.opacity = 1; clearTimeout(toast.t); toast.t = setTimeout(() => { el.style.opacity = 0; }, 600);
}
function showLast(u) { $('last').style.bottom = `calc(${(100 * u).toFixed(1)}% - 2px)`; }
function hud(now) {
  const left = S.playing ? Math.max(0, (S.tEnd - now) / 1000) : ROUND_S;
  $('score').firstChild.nodeValue = `${S.score} `;
  $('time').textContent = `${left.toFixed(0)} s · récord ${S.best}`;
  const stale = now - S.lastSample > 1500;
  $('conn').textContent = !S.connected ? 'sin servidor: reintentando…' : !S.watch ? 'servidor sí · reloj no conectado'
    : stale ? 'reloj conectado · sin muestras (toca la pantalla del reloj)' : `reloj · ${S.hz.toFixed(0)} Hz`;
  const live = Math.max(0, Math.min(1, (S.live - PUSH_ON) / Math.max(1, S.pmax - PUSH_ON)));
  $('live').style.height = `${(100 * live).toFixed(1)}%`;
  const p = new THREE.Vector3().copy(camera.position).addScaledVector(aimDir(S.yaw, S.pitch), 5).project(camera);
  $('reticle').style.left = `${((p.x + 1) / 2 * innerWidth).toFixed(1)}px`;
  $('reticle').style.top = `${((1 - p.y) / 2 * innerHeight).toFixed(1)}px`;
}

// ---------- partida ----------
function start() {
  for (const b of [...balloons]) removeBalloon(b);
  S.score = 0; S.combo = 0; S.playing = true; S.tEnd = performance.now() + ROUND_S * 1000;
  recenter();
  $('panel').style.display = 'none';
  sound(660, 0.15, 'square');
}
function finish() {
  S.playing = false;
  if (S.score > S.best) { S.best = S.score; try { localStorage.setItem('gearstream-globos-best', String(S.best)); } catch { /* sin almacenamiento */ } }
  $('panel').style.display = '';
  $('panel').querySelector('h1').textContent = `¡${S.score} puntos!`;
  $('go').textContent = 'Botón atrás del reloj (o Espacio) para jugar otra vez.';
}
function recenter() { S.yaw = 0; S.pitch = 0; S.aimHist.length = 0; }
function action() { if (S.playing) recenter(); else start(); }

// ---------- sensores ----------
function onGyro(t, v) {
  if (S.lastGyroT === null || !S.grav) { S.lastGyroT = t; return; }
  let dt = (t - S.lastGyroT) / 1000; S.lastGyroT = t;
  if (!(dt > 0) || dt > 0.1) dt = 0.01;
  const raw = [v.x, v.y, v.z];
  const w = [raw[0] - S.bias[0], raw[1] - S.bias[1], raw[2] - S.bias[2]];
  if (norm(w) < 2) for (let i = 0; i < 3; i++) S.bias[i] += 0.002 * (raw[i] - S.bias[i]);   // sesgo aprendido en quietud
  const gn = norm(S.grav), g = [S.grav[0] / gn, S.grav[1] / gn, S.grav[2] / gn];
  const roll = dot(w, AXIS), gpf = dot(g, AXIS);
  let yaw = (dot(w, g) - roll * gpf) / Math.max(1 - gpf * gpf, 0.09);
  const c = cross(AXIS, g), cn = norm(c);
  let pitch = cn > 0.3 ? dot(w, [c[0] / cn, c[1] / cn, c[2] / cn]) : 0;
  if (Math.hypot(yaw, pitch) < 0.8) { yaw = 0; pitch = 0; }                                  // zona muerta
  S.yaw = Math.max(-AIM_LIMIT.yaw, Math.min(AIM_LIMIT.yaw, S.yaw - yaw * dt));
  S.pitch = Math.max(-AIM_LIMIT.pitch, Math.min(AIM_LIMIT.pitch, S.pitch + pitch * dt));
  S.aimHist.push([t, S.yaw, S.pitch]);
  while (S.aimHist.length && t - S.aimHist[0][0] > 400) S.aimHist.shift();
  S.hzCount++;
}

function aimAt(t) {                     // la mira 120 ms antes: el empujón también gira la muñeca
  for (let i = S.aimHist.length - 1; i >= 0; i--) if (S.aimHist[i][0] <= t - 120) return [S.aimHist[i][1], S.aimHist[i][2]];
  return [S.yaw, S.pitch];
}

function onAccel(t, v) {
  if (!S.grav) return;
  const af = (v.x - S.grav[0]) * AXIS[0] + (v.y - S.grav[1]) * AXIS[1] + (v.z - S.grav[2]) * AXIS[2];
  S.live = Math.max(af, S.live * 0.9);
  const now = performance.now();
  if (!S.push) {
    if (af > PUSH_ON && now > S.refractoryUntil) S.push = { t0: t, peak: af };
    return;
  }
  S.push.peak = Math.max(S.push.peak, af);
  if (af < PUSH_ON * 0.4 || t - S.push.t0 > 220) {
    const peak = S.push.peak, [yaw, pitch] = aimAt(S.push.t0);
    S.push = null;
    S.refractoryUntil = now + 350;
    S.peaks.push(peak); if (S.peaks.length > 12) S.peaks.shift();
    const sorted = [...S.peaks].sort((a, b) => a - b);
    S.pmax = Math.max(12, 1.1 * sorted[Math.floor(0.8 * (sorted.length - 1))]);   // se adapta a tu fuerza
    throwDart(peak, yaw, pitch);
  }
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ui`);
  ws.onopen = () => { S.connected = true; };
  ws.onclose = () => { S.connected = false; S.watch = false; setTimeout(connect, 1500); };
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === 'watch') S.watch = !!msg.connected;
    else if (msg.type === 'hello') { S.watch = true; S.lastGyroT = null; }
    else if (msg.type === 'data' && Array.isArray(msg.samples)) {
      for (const s of msg.samples) {
        if (!Array.isArray(s) || s.length < 3 || !s[2] || typeof s[2] !== 'object') continue;
        const [name, t, v] = s;
        if (name === 'BUTTON') { if (v.key === 'back' && v.pressed === true) action(); continue; }
        if (typeof v.x !== 'number') continue;
        S.lastSample = performance.now(); S.watch = true;
        if (name === 'GRAVITY') S.grav = [v.x, v.y, v.z];
        else if (name === 'GYROSCOPE') onGyro(t, v);
        else if (name === 'ACCELERATION') onAccel(t, v);
      }
    }
  };
}
connect();

// ---------- teclado y ratón (para jugar o probar sin reloj) ----------
addEventListener('keydown', (e) => {
  if (e.code === 'Space') { e.preventDefault(); action(); }
  const k = { Digit1: 0, Digit2: 1, Digit3: 2 }[e.code];
  if (k !== undefined) { const u = [0.12, 0.45, 0.82][k]; throwDart(PUSH_ON + u * (S.pmax - PUSH_ON), S.yaw, S.pitch); }
  if (e.key === 'r' || e.key === 'R') recenter();
});
canvas.addEventListener('mousemove', (e) => {
  if (performance.now() - S.lastSample < 1500) return;          // con el reloj vivo manda la muñeca
  S.yaw = ((e.clientX / innerWidth) * 2 - 1) * AIM_LIMIT.yaw;
  S.pitch = -((e.clientY / innerHeight) * 2 - 1) * AIM_LIMIT.pitch;
});

// ---------- bucle ----------
let last = performance.now(), nextSpawn = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  if (now - S.hzT >= 1000) { S.hz = S.hzCount * 1000 / (now - S.hzT); S.hzCount = 0; S.hzT = now; }
  if (S.playing && now >= S.tEnd) finish();
  if (now >= nextSpawn && balloons.length < 7) { spawnBalloon(); nextSpawn = now + (S.playing ? 900 : 1800); }
  for (const b of [...balloons]) {
    const age = now - b.born;
    b.mesh.position.y += 0.12 * dt;
    b.mesh.position.x += 0.08 * Math.sin(now / 700 + b.phase) * dt;
    if (age > b.life) removeBalloon(b);
  }
  for (const d of [...darts]) {
    d.t += dt;
    const k = Math.min(1, d.t / d.dur);
    d.m.position.copy(camera.position).addScaledVector(d.dir, 0.4 + (d.depth - 0.4) * k);
    if (k >= 1) { landDart(d); scene.remove(d.m); darts.splice(darts.indexOf(d), 1); }
  }
  for (const p of [...bits]) {
    p.t += dt; p.v.y -= 6 * dt; p.m.position.addScaledVector(p.v, dt); p.m.material.opacity = Math.max(0, 1 - p.t / 0.6);
    if (p.t > 0.6) { scene.remove(p.m); bits.splice(bits.indexOf(p), 1); }
  }
  hud(now);
  renderer.render(scene, camera);
}
requestAnimationFrame(frame);
