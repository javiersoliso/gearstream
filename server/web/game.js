// Revienta globos: apuntas con la muñeca y empujas la mano hacia la pantalla para lanzar un dardo.
// La fuerza del empujón es la profundidad (el eje Z): suave llega cerca, fuerte llega lejos. En el camino
// revienta el primer globo que toca (antes solo miraba al llegar, y un dardo fuerte atravesaba los cercanos);
// al llegar, también el que esté a esa profundidad cerca de la mira. Los dorados valen el triple.
// Todo lo que se repite en cada cuadro reutiliza geometrías, materiales y pedacitos de confeti: nada
// se crea por cuadro, así el juego sigue fluido.
//
// Apuntar: las mismas tasas que el ratón aéreo, referidas a la gravedad (yaw alrededor de la vertical,
// pitch alrededor del eje horizontal perpendicular al antebrazo), integradas a ángulos de mira.
// Empujar: aceleración lineal a lo largo del antebrazo, a_f = (ACC − GRAV)·x̂ (x del reloj = hacia la
// mano). Un empujón hacia delante empieza con a_f positiva; un giro brusco de muñeca da centrípeta
// negativa (hacia el codo), así que no dispara. La fuerza se escala sola con tus últimos empujones.
'use strict';

const DEG = Math.PI / 180;
const AXIS = forearmOf(loadHand());   // antebrazo hacia la mano, en el marco del reloj (wrist.js: izquierda +x, derecha −x)
const ROUND_S = 60;
// contrarreloj: empiezas con 30 s, cada globo te da tiempo y fallar te quita; cada vez salen más y duran menos
const CONTRA = { start: 30, gain: [1, 2, 3], gold: 5, miss: 1, cap: 60 };
const MODES = { clasico: { name: 'Clásico', how: '60 segundos' }, contra: { name: 'Contrarreloj', how: 'cada globo te da tiempo' } };
const LANES = [                        // profundidad (m), puntos, color
  { d: 3.5, pts: 100, color: 0x5dcaa5, name: 'cerca' },
  { d: 7, pts: 200, color: 0xffd166, name: 'medio' },
  { d: 11, pts: 300, color: 0xf0997b, name: 'lejos' },
];
const PUSH_ON = 4.0;                   // m/s² a lo largo del antebrazo para empezar un empujón
const AIM_LIMIT = { yaw: 30, pitch: 18 };
const LATE_MS = 400;                   // muestras más viejas vienen de una ráfaga tras una pausa del reloj
const HIT_ASSIST = 0.08;               // m que se suman al radio del globo: perdona un poco sin volver "imanes" a los cercanos
const GOLD = { color: 0xffc94a, chance: 0.08, mult: 3 };

// ---------- estado ----------
const S = {
  grav: null, bias: [0, 0, 0], lastGyroT: null,
  yaw: 0, pitch: 0, aimHist: [],       // mira (grados) y su historia para lanzar con la mira de antes del empujón
  push: null, refractoryUntil: 0, peaks: [], pmax: 25, live: 0,
  playing: false, score: 0, combo: 0, tEnd: 0, tStart: 0, mode: 'clasico', best: { clasico: 0, contra: 0 },
  connected: false, watch: false, hz: 0, hzCount: 0, hzT: performance.now(), lastSample: 0,
};
const BEST_KEY = { clasico: 'gearstream-globos-best', contra: 'gearstream-globos-best-contra' };
try { for (const m in BEST_KEY) S.best[m] = Number(localStorage.getItem(BEST_KEY[m])) || 0; } catch { /* sin almacenamiento */ }
const contra = () => S.playing && S.mode === 'contra';
const elapsedS = () => (performance.now() - S.tStart) / 1000;
const lifeScale = () => (contra() ? Math.max(0.55, 1 - elapsedS() / 120) : 1);   // en contrarreloj duran menos con el tiempo

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => Math.hypot(a[0], a[1], a[2]);

// ---------- escena ----------
const canvas = document.getElementById('gl');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
function gradient(stops, w, h, radial) {   // una textura de lienzo: el cielo y el brillo de los dardos
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d'), gr = radial ? g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2) : g.createLinearGradient(0, 0, 0, h);
  for (const [at, col] of stops) gr.addColorStop(at, col);
  g.fillStyle = gr; g.fillRect(0, 0, w, h);
  return new THREE.CanvasTexture(c);
}
scene.background = gradient([[0, '#0b1430'], [0.55, '#1c2a4d'], [0.8, '#2b2a4a'], [1, '#191c2c']], 2, 256);
scene.fog = new THREE.Fog(0x1d2440, 10, 24);
const BASE = new THREE.Vector3(0, 1.6, 0);   // donde está tu cabeza; la cámara tiembla alrededor al reventar
const camera = new THREE.PerspectiveCamera(60, 1, 0.05, 60);
camera.position.copy(BASE);
camera.lookAt(0, 1.6, -1);
scene.add(new THREE.HemisphereLight(0xdfe9ff, 0x2a2140, 0.95));
const sun = new THREE.DirectionalLight(0xfff1dc, 0.75); sun.position.set(2, 5, 2); scene.add(sun);
const rim = new THREE.DirectionalLight(0x8fb8ff, 0.35); rim.position.set(-3, 2, -6); scene.add(rim);
const GLOW = gradient([[0, 'rgba(255,255,255,1)'], [0.35, 'rgba(255,255,255,0.35)'], [1, 'rgba(255,255,255,0)']], 64, 64, true);
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
const balloonGeo = new THREE.SphereGeometry(1, 32, 20);
const knotGeo = new THREE.ConeGeometry(0.13, 0.2, 10);
const STRING_N = 8;
const stringMat = new THREE.LineBasicMaterial({ color: 0xdfe3ec, transparent: true, opacity: 0.55 });
const easeOutBack = (x) => 1 + 2.2 * Math.pow(x - 1, 3) + 1.2 * Math.pow(x - 1, 2);
// ¿se ve encimado? Desde tus ojos, dos globos se tapan si sus direcciones están más juntas que la suma de sus
// radios aparentes (un cercano puede tapar a uno lejano aunque en 3D estén lejos)
const _dirA = new THREE.Vector3(), _dirB = new THREE.Vector3();
function clearSpot(pos, r) {
  _dirA.copy(pos).sub(BASE);
  const da = _dirA.length(), angA = Math.atan(1.25 * r / da);
  _dirA.divideScalar(da);
  for (const b of balloons) {
    _dirB.copy(b.mesh.position).sub(BASE);
    const db = _dirB.length(), angB = Math.atan(1.25 * b.r / db);
    if (_dirA.angleTo(_dirB.divideScalar(db)) < 1.3 * (angA + angB)) return false;
  }
  return true;
}
function spawnBalloon(now) {
  let lane, dir, r;
  for (let tries = 0; ; tries++) {     // hasta 12 lugares al azar; si todos tapan a otro, este globo espera
    if (tries === 12) return false;
    lane = LANES[Math.floor(Math.random() * LANES.length)];
    dir = aimDir((Math.random() * 2 - 1) * 22, -8 + Math.random() * 20);
    r = 0.32 + 0.06 * Math.random();
    if (clearSpot(_spot.copy(BASE).addScaledVector(dir, lane.d), r)) break;
  }
  const golden = Math.random() < GOLD.chance;
  const color = golden ? GOLD.color : lane.color;
  const mat = new THREE.MeshPhysicalMaterial({ color, roughness: 0.3, clearcoat: 0.9, clearcoatRoughness: 0.2,
    emissive: color, emissiveIntensity: golden ? 0.3 : 0.07 });
  const mesh = new THREE.Mesh(balloonGeo, mat);
  mesh.scale.setScalar(0.001);
  mesh.position.copy(BASE).addScaledVector(dir, lane.d);
  const knot = new THREE.Mesh(knotGeo, mat); knot.position.y = -1.06; knot.rotation.x = Math.PI; mesh.add(knot);
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(STRING_N * 3), 3));
  const string = new THREE.Line(sg, stringMat);
  mesh.add(string);
  scene.add(mesh);
  const life = (golden ? 4500 : 6000 + Math.random() * 2000) * lifeScale();
  balloons.push({ mesh, mat, string, lane, golden, r, born: now, life, phase: Math.random() * 6, sway: golden ? 0.35 : 0.08 });
  return true;
}
const _spot = new THREE.Vector3();
function removeBalloon(b) {
  scene.remove(b.mesh); b.mat.dispose(); b.string.geometry.dispose();
  balloons.splice(balloons.indexOf(b), 1);
}

// confeti, ondas y chispas: piezas que se reciclan
const bits = [], bitPool = [];
const confettiGeo = new THREE.PlaneGeometry(0.08, 0.045);
function burst(pos, color, n, speed, life, gravity) {
  for (let i = 0; i < n; i++) {
    const m = bitPool.pop() || new THREE.Mesh(confettiGeo, new THREE.MeshBasicMaterial({ transparent: true, side: THREE.DoubleSide, depthWrite: false }));
    m.material.color.set(Array.isArray(color) ? color[i % color.length] : color);
    m.material.opacity = 1; m.position.copy(pos); m.scale.setScalar(0.7 + 0.6 * Math.random());
    m.rotation.set(Math.random() * 6, Math.random() * 6, Math.random() * 6);
    const v = new THREE.Vector3(Math.random() - 0.5, Math.random() - 0.25, Math.random() - 0.5).normalize().multiplyScalar(speed * (0.6 + 0.8 * Math.random()));
    scene.add(m);
    bits.push({ m, v, spin: (Math.random() - 0.5) * 18, t: 0, life: life * (0.7 + 0.6 * Math.random()), gravity });
  }
}
const rings = [], ringPool = [];
const ringGeo = new THREE.RingGeometry(0.85, 1, 48);
function shockwave(pos, color, r) {
  const m = ringPool.pop() || new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide }));
  m.material.color.set(color); m.position.copy(pos); m.lookAt(camera.position);
  scene.add(m); rings.push({ m, r, t: 0 });
}
function shake(amp, ms) { S.shakeAmp = Math.max(S.shakeAmp || 0, amp); S.shakeUntil = performance.now() + ms; S.shakeMs = ms; }

function pop(b) {
  const c = b.golden ? GOLD.color : b.lane.color, pos = b.mesh.position;
  burst(pos, b.golden ? [GOLD.color, 0xffffff, 0xffe9a8] : [c, 0xffffff, c], b.golden ? 34 : 22, 3.2, 0.9, 5);
  shockwave(pos, c, b.r);
  shake(b.golden ? 0.05 : 0.025, 160);
  removeBalloon(b);
  const step = Math.min(S.combo, 8);
  sound((520 + 120 * LANES.indexOf(b.lane)) * (1 + 0.06 * step), 0.12, 'triangle');
  sound((1040 + 240 * LANES.indexOf(b.lane)) * (1 + 0.06 * step), 0.07, 'sine');
  if (b.golden) sound(1320, 0.25, 'square');
}

// ---------- dardos ----------
const darts = [];
const dartGeo = new THREE.SphereGeometry(0.07, 12, 8);
const dartMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
const TRAIL = 7;
const trailMats = Array.from({ length: TRAIL }, (_, i) => new THREE.MeshBasicMaterial({ color: 0xbfe6ff, transparent: true, opacity: 0.45 * (1 - i / TRAIL), depthWrite: false }));
function throwDart(power, yawDeg, pitchDeg) {
  const u = Math.max(0, Math.min(1, (power - PUSH_ON) / Math.max(1, S.pmax - PUSH_ON)));
  const depth = 2 + 10.5 * u;
  const dir = aimDir(yawDeg, pitchDeg);
  const m = new THREE.Mesh(dartGeo, dartMat);
  m.position.copy(BASE).addScaledVector(dir, 0.4);
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: 0x9fd8ff, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  glow.scale.setScalar(0.45); m.add(glow);
  const trail = trailMats.map((mat, i) => { const t = new THREE.Mesh(dartGeo, mat); t.scale.setScalar(1 - i / (TRAIL + 2)); t.position.copy(m.position); scene.add(t); return t; });
  scene.add(m);
  const hist = Array.from({ length: TRAIL * 2 }, () => m.position.clone());   // posiciones recientes, recicladas
  darts.push({ m, glow, trail, hist, dir, depth, along: 0.4, t: 0, dur: 0.18 + depth / 28 });
  showLast(u);
  sound(300 + 400 * u, 0.06, 'sine');
}
function removeDart(d) {
  scene.remove(d.m); d.glow.material.dispose();
  for (const t of d.trail) scene.remove(t);
  darts.splice(darts.indexOf(d), 1);
}
// el primer globo que toca el tramo del dardo entre dos cuadros (distancia del centro al segmento)
const _seg = new THREE.Vector3(), _rel = new THREE.Vector3(), _closest = new THREE.Vector3();
function sweepHit(from, to) {
  _seg.copy(to).sub(from);
  const L2 = _seg.lengthSq();
  let hit = null, bestS = Infinity;
  for (const b of balloons) {
    _rel.copy(b.mesh.position).sub(from);
    const s = L2 > 0 ? Math.max(0, Math.min(1, _rel.dot(_seg) / L2)) : 0;
    _closest.copy(from).addScaledVector(_seg, s);
    if (_closest.distanceTo(b.mesh.position) < 1.1 * b.mesh.scale.x + HIT_ASSIST && s < bestS) { bestS = s; hit = b; }   // scale.x: el radio, también mientras aparece
  }
  return hit;
}
function score(hit) {
  S.combo += 1;
  const mult = (hit.golden ? GOLD.mult : 1) * (S.combo >= 3 ? 2 : 1);
  const pts = hit.lane.pts * mult;
  if (S.playing) S.score += pts;
  floatText(hit.mesh.position, `+${pts}`, hit.golden ? GOLD.color : hit.lane.color, hit.golden || S.combo >= 3);
  if (S.combo >= 3) floatText(hit.mesh.position, `racha ${S.combo}`, 0xffffff, false, 34);
  if (contra()) {
    const gain = hit.golden ? CONTRA.gold : CONTRA.gain[LANES.indexOf(hit.lane)];
    S.tEnd = Math.min(performance.now() + CONTRA.cap * 1000, S.tEnd + gain * 1000);
    floatText(hit.mesh.position, `+${gain} s`, 0x9fe8ff, false, S.combo >= 3 ? 66 : 34);
  }
  pop(hit);
}
function landDart(d) {                 // llegó sin tocar nada en el camino: el aterrizaje generoso de siempre
  let hit = null, best = Infinity;
  for (const b of balloons) {
    const v = b.mesh.position.clone().sub(BASE);
    const along = v.dot(d.dir);
    const lateral = v.clone().addScaledVector(d.dir, -along).length();
    const depthErr = Math.abs(along - d.depth);
    if (lateral < b.r + 0.3 && depthErr < 1.7 && depthErr < best) { best = depthErr; hit = b; }
  }
  if (hit) score(hit);
  else {
    S.combo = 0;
    burst(d.m.position, [0x8a93a6, 0xc4cad6], 7, 0.9, 0.45, 2);   // un soplo: no le diste a nada
    if (contra()) { S.tEnd -= CONTRA.miss * 1000; floatText(d.m.position, `−${CONTRA.miss} s`, 0xff8a8a, false); }
  }
}

// ---------- puntos flotando ----------
const fxLayer = document.createElement('div');
Object.assign(fxLayer.style, { position: 'fixed', inset: '0', pointerEvents: 'none', overflow: 'hidden' });
document.body.append(fxLayer);
const _proj = new THREE.Vector3();
function floatText(pos, text, color, big, dy = 0) {
  _proj.copy(pos).project(camera);
  if (_proj.z > 1) return;
  const el = document.createElement('div');
  el.textContent = text;
  Object.assign(el.style, {
    position: 'absolute', left: `${((_proj.x + 1) / 2 * innerWidth).toFixed(0)}px`, top: `${((1 - _proj.y) / 2 * innerHeight + dy).toFixed(0)}px`,
    transform: 'translate(-50%, -50%) scale(0.6)', font: `800 ${big ? 34 : 24}px system-ui, sans-serif`,
    color: '#' + color.toString(16).padStart(6, '0'), textShadow: '0 2px 10px #000a, 0 0 18px #0006',
    transition: 'transform 0.9s cubic-bezier(.17,.89,.32,1.28), opacity 0.9s ease-in', opacity: '1', whiteSpace: 'nowrap',
  });
  fxLayer.append(el);
  requestAnimationFrame(() => { el.style.transform = 'translate(-50%, -190%) scale(1.05)'; el.style.opacity = '0'; });
  setTimeout(() => el.remove(), 950);
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
function showLast(u) { $('last').style.bottom = `calc(${(100 * u).toFixed(1)}% - 2px)`; }
function hud(now) {
  const left = S.playing ? Math.max(0, (S.tEnd - now) / 1000) : S.mode === 'contra' ? CONTRA.start : ROUND_S;
  $('score').firstChild.nodeValue = `${S.score} `;
  $('time').textContent = `${left.toFixed(0)} s${S.mode === 'contra' ? ' · contrarreloj' : ''} · récord ${S.best[S.mode]}`;
  $('time').style.color = contra() && left < 6 ? '#ff8a8a' : '';
  const stale = now - S.lastSample > 500;
  $('conn').textContent = !S.connected ? 'sin servidor: reintentando…' : !S.watch ? 'servidor sí · reloj no conectado'
    : stale ? 'el reloj no manda datos · toca su pantalla (apagada, el reloj frena el Wi-Fi)' : `reloj · ${S.hz.toFixed(0)} Hz`;
  const live = Math.max(0, Math.min(1, (S.live - PUSH_ON) / Math.max(1, S.pmax - PUSH_ON)));
  $('live').style.height = `${(100 * live).toFixed(1)}%`;
  const p = _aim.copy(BASE).addScaledVector(aimDir(S.yaw, S.pitch), 5).project(camera);
  $('reticle').style.left = `${((p.x + 1) / 2 * innerWidth).toFixed(1)}px`;
  $('reticle').style.top = `${((1 - p.y) / 2 * innerHeight).toFixed(1)}px`;
}

// ---------- partida ----------
function start() {
  for (const b of [...balloons]) removeBalloon(b);
  const now = performance.now();
  S.score = 0; S.combo = 0; S.playing = true; S.tStart = now;
  S.tEnd = now + (S.mode === 'contra' ? CONTRA.start : ROUND_S) * 1000;
  recenter();
  $('panel').style.display = 'none';
  sound(660, 0.15, 'square');
}
function finish() {
  const lasted = elapsedS();
  S.playing = false;
  const record = S.score > S.best[S.mode];
  if (record) { S.best[S.mode] = S.score; try { localStorage.setItem(BEST_KEY[S.mode], String(S.score)); } catch { /* sin almacenamiento */ } }
  $('panel').style.display = '';
  $('panel').querySelector('h1').textContent = `¡${S.score} puntos!${record ? ' Récord' : ''}`
    + (S.mode === 'contra' ? ` · aguantaste ${lasted.toFixed(0)} s` : '');
  $('go').textContent = 'Botón atrás del reloj (o Espacio) para jugar otra vez.';
  showMode();
}
// el modo se elige en el panel: girando el bisel del reloj, o con ← →
const modeEl = document.createElement('div');
Object.assign(modeEl.style, { margin: '12px 0 0', padding: '10px 14px', borderRadius: '10px', background: '#0006', fontWeight: '600' });
$('panel').insertBefore(modeEl, $('go'));
const rulesEl = $('panel').querySelector('ol').nextElementSibling;   // "Tienes 60 segundos…": cambia con el modo
function showMode() {
  const m = MODES[S.mode], other = MODES[S.mode === 'clasico' ? 'contra' : 'clasico'];
  rulesEl.textContent = S.mode === 'contra'
    ? `Empiezas con ${CONTRA.start} s: cada globo te suma tiempo (cerca +1, medio +2, lejos +3, dorado +${CONTRA.gold}) y fallar te quita ${CONTRA.miss}. Aguanta todo lo que puedas: cada vez salen más y duran menos.`
    : 'Tienes 60 segundos. La barra de la izquierda muestra la fuerza de cada empujón: practica un poco antes de empezar.';
  modeEl.innerHTML = `Modo: <span style="color:#9fe8ff">${m.name}</span> · ${m.how} · récord ${S.best[S.mode]}`
    + `<div style="font-weight:400;font-size:13px;opacity:0.75">Gira el bisel (o ← →) para ${other.name.toLowerCase()}.</div>`;
}
function toggleMode() {
  if (S.playing) return;
  S.mode = S.mode === 'clasico' ? 'contra' : 'clasico';
  showMode();
  sound(S.mode === 'contra' ? 880 : 660, 0.08, 'sine');
}
showMode();
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
    if (af > PUSH_ON && now > S.refractoryUntil && Date.now() - t < LATE_MS) S.push = { t0: t, peak: af };   // un empujón atrasado no lanza
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
        if (name === 'BEZEL') { toggleMode(); continue; }   // solo con el panel abierto: jugando no hace nada
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
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') toggleMode();
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
  const hard = contra() ? elapsedS() : 0;                 // contrarreloj: más globos y más seguido mientras aguantas
  if (now >= nextSpawn && balloons.length < 7 + Math.min(2, Math.floor(hard / 30))) {
    nextSpawn = now + (!S.playing ? 1800 : spawnBalloon(now) ? Math.max(380, 900 - 6 * hard) : 150);   // sin hueco: reintenta pronto
  }
  for (const b of [...balloons]) {
    const age = now - b.born, grow = easeOutBack(Math.min(1, age / 380)), leave = Math.min(1, Math.max(0, (b.life - age) / 400));
    const s = b.r * grow * leave;        // aparece con un rebote y se encoge al irse
    b.mesh.scale.set(s, s * 1.15, s);
    b.mesh.position.y += 0.12 * dt;
    b.mesh.position.x += b.sway * Math.sin(now / 700 + b.phase) * dt;
    b.mesh.rotation.z = 0.08 * Math.sin(now / 900 + b.phase);
    const a = b.string.geometry.attributes.position.array;   // el hilo se mece, más abajo más
    for (let i = 0; i < STRING_N; i++) {
      const u = i / (STRING_N - 1);
      a[3 * i] = 0.12 * u * u * Math.sin(now / 520 + b.phase + u * 2.4); a[3 * i + 1] = -1.15 - 1.55 * u; a[3 * i + 2] = 0;
    }
    b.string.geometry.attributes.position.needsUpdate = true;
    if (age > b.life) removeBalloon(b);
  }
  for (const d of [...darts]) {
    d.t += dt;
    const k = Math.min(1, d.t / d.dur), along = 0.4 + (d.depth - 0.4) * k;
    const from = _from.copy(BASE).addScaledVector(d.dir, d.along);
    d.m.position.copy(BASE).addScaledVector(d.dir, along);
    d.along = along;
    d.hist.unshift(d.hist.pop().copy(d.m.position));
    d.trail.forEach((t, i) => t.position.copy(d.hist[2 * i + 1]));
    const hit = sweepHit(from, d.m.position);
    if (hit) { score(hit); removeDart(d); continue; }
    if (k >= 1) { landDart(d); removeDart(d); }
  }
  for (const p of [...bits]) {
    p.t += dt; p.v.y -= p.gravity * dt; p.v.multiplyScalar(1 - 1.6 * dt);
    p.m.position.addScaledVector(p.v, dt); p.m.rotation.x += p.spin * dt; p.m.rotation.y += 0.7 * p.spin * dt;
    p.m.material.opacity = Math.max(0, 1 - p.t / p.life);
    if (p.t > p.life) { scene.remove(p.m); bits.splice(bits.indexOf(p), 1); bitPool.push(p.m); }
  }
  for (const w of [...rings]) {
    w.t += dt;
    const k = w.t / 0.32;
    w.m.scale.setScalar(w.r * (1 + 2.6 * k)); w.m.material.opacity = Math.max(0, 0.8 * (1 - k));
    if (k >= 1) { scene.remove(w.m); rings.splice(rings.indexOf(w), 1); ringPool.push(w.m); }
  }
  camera.position.copy(BASE);           // un temblor corto al reventar, que se apaga solo
  if (now < (S.shakeUntil || 0)) {
    const a = S.shakeAmp * (S.shakeUntil - now) / S.shakeMs;
    camera.position.x += a * (Math.random() * 2 - 1); camera.position.y += a * (Math.random() * 2 - 1);
  } else S.shakeAmp = 0;
  hud(now);
  renderer.render(scene, camera);
}
const _from = new THREE.Vector3(), _aim = new THREE.Vector3();
requestAnimationFrame(frame);
