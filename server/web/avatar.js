// Avatar 3D del brazo izquierdo a partir del reloj. Un solo IMU en la muñeca fija la ORIENTACIÓN del
// antebrazo (3 grados de libertad): inclinación y torsión vienen de la gravedad (absolutas), el rumbo
// de integrar el giroscopio (relativo, con corrección lenta). La posición del codo no se mide: se estima
// con una regla de postura (el brazo cuelga y se adelanta con el antebrazo). Tres vistas sobre un solo
// canvas WebGL recortado por viewport: orbital, POV desde la cabeza y plano cerrado del brazo.
'use strict';

const UP = new THREE.Vector3(0, 1, 0);
const L_UPPER = 0.30, L_FORE = 0.25, L_HAND = 0.09;
const SHOULDER_L = new THREE.Vector3(0.21, 1.42, 0);
const SHOULDER_R = new THREE.Vector3(-0.21, 1.42, 0);
const GRAVITY_GAIN = 0.1;          // fracción del error de gravedad corregida por muestra (100 Hz → ~0.1 s)
const BIAS_RATE = 0.002;           // aprendizaje del sesgo del giroscopio con la muñeca quieta
const STILL_DPS = 2.0;             // |ω| por debajo del cual se considera quieta
const CENTER_TAU_S = 12;           // auto-centrado del rumbo: constante de tiempo

const S = {
  q: new THREE.Quaternion(),       // sensor → mundo (sin rumbo corregido)
  qOff: new THREE.Quaternion(),    // corrección de rumbo (giro alrededor de Y)
  bias: new THREE.Vector3(),
  lastGyroT: null, gyroCount: 0, hzCount: 0, hzT: performance.now(), hz: 0,
  rates: { yaw: 0, pitch: 0, roll: 0 },
  handSign: 1, autoCenter: true, connected: false, watch: false, lastSampleAt: 0,
};

// ---------- orientación ----------
const _w = new THREE.Vector3(), _dq = new THREE.Quaternion(), _um = new THREE.Vector3(), _up = new THREE.Vector3(), _ax = new THREE.Vector3(), _qi = new THREE.Quaternion();

function onGyro(t, v) {
  if (S.lastGyroT !== null) {
    let dt = (t - S.lastGyroT) / 1000;
    if (!(dt > 0) || dt > 0.1) dt = 0.01;
    _w.set(v.x - S.bias.x, v.y - S.bias.y, v.z - S.bias.z);
    const mag = _w.length();
    if (mag < STILL_DPS) S.bias.lerp(new THREE.Vector3(v.x, v.y, v.z), BIAS_RATE);
    if (mag > 1e-6) {
      _dq.setFromAxisAngle(_w.clone().divideScalar(mag), THREE.MathUtils.degToRad(mag) * dt);
      S.q.multiply(_dq);           // q ← q ⊗ δq, tasas en el cuerpo
    }
    // tasas en el marco de la gravedad para las lecturas (°/s)
    _qi.copy(S.q).invert();
    _up.copy(UP).applyQuaternion(_qi);                      // arriba, visto desde el sensor
    const f = new THREE.Vector3(0, S.handSign, 0);           // eje del antebrazo (sensor)
    const side = new THREE.Vector3().crossVectors(_up, f).normalize();
    S.rates.yaw = _w.dot(_up);
    S.rates.pitch = _w.dot(side);
    S.rates.roll = _w.dot(f);
  }
  S.lastGyroT = t;
  S.gyroCount++; S.hzCount++;
  if (S.gyroCount === 120) resetHeading();                  // tras ~1 s la gravedad ya fijó la inclinación: el frente es hacia donde apuntas
}

function onGravity(v) {
  _um.set(v.x, v.y, v.z);
  if (_um.lengthSq() < 1) return;
  _um.normalize();
  _qi.copy(S.q).invert();
  _up.copy(UP).applyQuaternion(_qi);                        // arriba predicho en el sensor
  _ax.crossVectors(_um, _up);                               // eje que lleva lo predicho hacia lo medido
  const s = _ax.length();
  if (s > 1e-6) {
    _dq.setFromAxisAngle(_ax.divideScalar(s), Math.asin(Math.min(1, s)) * GRAVITY_GAIN);
    S.q.multiply(_dq);
  }
  S.q.normalize();
}

function displayQ() { return S.qOff.clone().multiply(S.q); }
function forearmDir(qd) { return new THREE.Vector3(0, S.handSign, 0).applyQuaternion(qd); }
function headingOf(f) { return Math.atan2(f.x, f.z); }      // 0 = hacia +Z (el frente del muñeco)

function resetHeading() {
  const th = headingOf(forearmDir(displayQ()));
  S.qOff.premultiply(new THREE.Quaternion().setFromAxisAngle(UP, -th));
}

function autoCenterStep(dt) {
  if (!S.autoCenter) return;
  const th = headingOf(forearmDir(displayQ()));
  S.qOff.premultiply(new THREE.Quaternion().setFromAxisAngle(UP, -th * Math.min(1, dt / CENTER_TAU_S)));
}

// ---------- escena ----------
const canvas = document.getElementById('gl');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setScissorTest(true);
const scene = new THREE.Scene();
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
scene.background = new THREE.Color(dark ? 0x1b1b1d : 0xf4f3ef);
scene.fog = new THREE.Fog(scene.background, 4, 9);
scene.add(new THREE.HemisphereLight(0xffffff, 0x777766, 0.9));
const sun = new THREE.DirectionalLight(0xffffff, 0.7); sun.position.set(1.5, 3, 2); scene.add(sun);
scene.add(new THREE.GridHelper(4, 16, dark ? 0x555555 : 0xbbbbbb, dark ? 0x333333 : 0xdddddd));

const M = {
  body: new THREE.MeshStandardMaterial({ color: dark ? 0x9a9a9a : 0xc9c7bf, roughness: 0.8 }),
  joint: new THREE.MeshStandardMaterial({ color: dark ? 0xcfcfcf : 0x8a8a84, roughness: 0.6 }),
  est: new THREE.MeshStandardMaterial({ color: 0x8c8c8c, roughness: 0.7, transparent: true, opacity: 0.85 }),
  meas: new THREE.MeshStandardMaterial({ color: 0x1d9e75, roughness: 0.5 }),
  hand: new THREE.MeshStandardMaterial({ color: 0x5dcaa5, roughness: 0.6 }),
  watch: new THREE.MeshStandardMaterial({ color: 0x222222, roughness: 0.3, metalness: 0.4 }),
  face: new THREE.MeshStandardMaterial({ color: 0x378add, emissive: 0x113355, roughness: 0.2 }),
};
const unitCyl = new THREE.CylinderGeometry(1, 1, 1, 14);

function limb(mat, r) { const m = new THREE.Mesh(unitCyl, mat); m.scale.set(r, 1, r); scene.add(m); return m; }
function joint(mat, r) { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), mat); scene.add(m); return m; }
function between(mesh, a, b, r) {
  const d = new THREE.Vector3().subVectors(b, a); const len = d.length();
  mesh.position.copy(a).addScaledVector(d, 0.5);
  mesh.quaternion.setFromUnitVectors(UP, d.divideScalar(len));
  mesh.scale.set(r, len, r);
}

// cuerpo estático
const head = joint(M.body, 0.105); head.position.set(0, 1.68, 0);
const neck = limb(M.body, 0.035); between(neck, new THREE.Vector3(0, 1.5, 0), new THREE.Vector3(0, 1.6, 0), 0.035);
const torso = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.5, 0.2), M.body); torso.position.set(0, 1.22, 0); scene.add(torso);
const pelvis = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.16, 0.2), M.body); pelvis.position.set(0, 0.9, 0); scene.add(pelvis);
for (const x of [-0.1, 0.1]) {
  const thigh = limb(M.body, 0.06); between(thigh, new THREE.Vector3(x, 0.85, 0), new THREE.Vector3(x, 0.45, 0), 0.06);
  const shin = limb(M.body, 0.05); between(shin, new THREE.Vector3(x, 0.45, 0), new THREE.Vector3(x, 0.05, 0), 0.05);
  joint(M.joint, 0.055).position.set(x, 0.45, 0);
  const foot = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.06, 0.24), M.body); foot.position.set(x, 0.03, 0.06); scene.add(foot);
}
for (const s of [SHOULDER_L, SHOULDER_R]) joint(M.joint, 0.06).position.copy(s);
// brazo derecho colgando
const rUpper = limb(M.body, 0.045); between(rUpper, SHOULDER_R, new THREE.Vector3(-0.23, 1.12, 0.02), 0.045);
const rFore = limb(M.body, 0.038); between(rFore, new THREE.Vector3(-0.23, 1.12, 0.02), new THREE.Vector3(-0.24, 0.86, 0.05), 0.038);
joint(M.joint, 0.045).position.set(-0.23, 1.12, 0.02);
const rHand = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.1, 0.03), M.body); rHand.position.set(-0.24, 0.8, 0.06); scene.add(rHand);

// brazo izquierdo: hombro y codo estimados (gris), antebrazo y mano medidos (verde)
const lUpper = limb(M.est, 0.045);
const lElbow = joint(M.joint, 0.045);
const lFore = limb(M.meas, 0.038);
const lWrist = joint(M.joint, 0.036);
const lHand = new THREE.Mesh(new THREE.BoxGeometry(0.075, L_HAND, 0.03), M.hand); scene.add(lHand);
const watchBody = new THREE.Mesh(new THREE.CylinderGeometry(0.026, 0.026, 0.012, 24), M.watch); scene.add(watchBody);
const watchFace = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.002, 24), M.face); scene.add(watchFace);
const axes = new THREE.AxesHelper(0.12); scene.add(axes);

const E = new THREE.Vector3(), W = new THREE.Vector3(), H = new THREE.Vector3(), F = new THREE.Vector3(), U = new THREE.Vector3(), N = new THREE.Vector3();
const _rz = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), Math.PI);
const _rx = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2);

function poseArm() {
  const qd = displayQ();
  F.copy(forearmDir(qd));                                   // dirección codo → mano
  // regla de postura: el brazo cuelga y se adelanta con el antebrazo
  U.set(0.12, -1, 0).addScaledVector(F, 0.8).normalize();
  E.copy(SHOULDER_L).addScaledVector(U, L_UPPER);
  W.copy(E).addScaledVector(F, L_FORE);
  H.copy(W).addScaledVector(F, L_HAND);
  between(lUpper, SHOULDER_L, E, 0.045);
  lElbow.position.copy(E);
  between(lFore, E, W, 0.038);
  lWrist.position.copy(W);
  const qMesh = qd.clone(); if (S.handSign < 0) qMesh.multiply(_rz);   // +y local del mesh = hacia la mano
  lHand.position.copy(W).addScaledVector(F, L_HAND / 2 + 0.02); lHand.quaternion.copy(qMesh);
  N.set(0, 0, 1).applyQuaternion(qd);                       // normal de la pantalla del reloj
  watchBody.position.copy(W).addScaledVector(F, -0.03).addScaledVector(N, 0.028);
  watchBody.quaternion.copy(qMesh).multiply(_rx);           // eje del cilindro (y local) → normal (z)
  watchFace.position.copy(watchBody.position).addScaledVector(N, 0.007); watchFace.quaternion.copy(watchBody.quaternion);
  axes.position.copy(watchBody.position); axes.quaternion.copy(qd);
}

// ---------- vistas ----------
const camOrbit = new THREE.PerspectiveCamera(42, 1, 0.05, 30); camOrbit.position.set(1.4, 1.7, 2.3);
const controls = new THREE.OrbitControls(camOrbit, document.getElementById('vOrbit'));
controls.target.set(0.1, 1.2, 0); controls.enableDamping = true; controls.update();
const camPov = new THREE.PerspectiveCamera(95, 1, 0.02, 30); camPov.position.set(0, 1.62, 0.06);
camPov.lookAt(0, 1.0, 1.4);
const camArm = new THREE.PerspectiveCamera(40, 1, 0.02, 30);
const views = [
  { el: document.getElementById('vOrbit'), cam: camOrbit },
  { el: document.getElementById('vPov'), cam: camPov },
  { el: document.getElementById('vArm'), cam: camArm },
];

function fitCanvas() {
  const r = canvas.parentElement.getBoundingClientRect();
  renderer.setSize(r.width, r.height, false);
  canvas.style.width = r.width + 'px'; canvas.style.height = r.height + 'px';
}
addEventListener('resize', fitCanvas); fitCanvas();

function renderViews() {
  const base = canvas.parentElement.getBoundingClientRect();
  for (const v of views) {
    const r = v.el.getBoundingClientRect();
    const w = Math.max(1, r.width), h = Math.max(1, r.height);
    const left = r.left - base.left, bottom = base.bottom - r.bottom;
    v.cam.aspect = w / h; v.cam.updateProjectionMatrix();
    renderer.setViewport(left, bottom, w, h); renderer.setScissor(left, bottom, w, h);
    renderer.render(scene, v.cam);
  }
}

const numOrbit = document.getElementById('numOrbit'), numArm = document.getElementById('numArm');
const fmt = (x, d = 0) => (x >= 0 ? '+' : '') + x.toFixed(d);
function readouts() {
  const elev = THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(F.y, -1, 1)));
  const head = THREE.MathUtils.radToDeg(headingOf(F));
  const side = new THREE.Vector3().crossVectors(UP, F); const sl = side.length();
  let roll = 0;
  if (sl > 1e-3) { side.divideScalar(sl); const upP = new THREE.Vector3().crossVectors(F, side).normalize(); roll = THREE.MathUtils.radToDeg(Math.atan2(N.dot(side), N.dot(upP))); }   // 0 = pantalla hacia arriba
  numArm.textContent = `elevación ${fmt(elev)}°\nrumbo ${fmt(head)}°\ntorsión ${fmt(roll)}°\nω yaw ${fmt(S.rates.yaw)}  pitch ${fmt(S.rates.pitch)}  roll ${fmt(S.rates.roll)} °/s`;
  numOrbit.textContent = `${S.hz.toFixed(0)} Hz · sesgo ${S.bias.x.toFixed(2)} ${S.bias.y.toFixed(2)} ${S.bias.z.toFixed(2)} °/s`;
}

let lastFrame = performance.now();
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.1, (now - lastFrame) / 1000); lastFrame = now;
  if (now - S.hzT >= 1000) { S.hz = S.hzCount * 1000 / (now - S.hzT); S.hzCount = 0; S.hzT = now; }
  autoCenterStep(dt);
  poseArm();
  // cámara del brazo: sigue al codo desde delante y un poco arriba
  camArm.position.copy(E).add(new THREE.Vector3(0.55, 0.25, 0.75));
  camArm.lookAt(new THREE.Vector3().addVectors(E, W).multiplyScalar(0.5));
  controls.update();
  readouts();
  renderViews();
}
requestAnimationFrame(frame);

// ---------- controles ----------
document.getElementById('reset').addEventListener('click', resetHeading);
addEventListener('keydown', (e) => { if (e.key === 'r' || e.key === 'R') resetHeading(); });
document.getElementById('autoCenter').addEventListener('change', (e) => { S.autoCenter = e.target.checked; });
document.getElementById('handSign').addEventListener('change', (e) => { S.handSign = Number(e.target.value); resetHeading(); });
document.getElementById('showAxes').addEventListener('change', (e) => { axes.visible = e.target.checked; });

// ---------- datos ----------
const estado = document.getElementById('estado');
function setEstado() {
  estado.textContent = !S.connected ? 'sin servidor: reintentando…' : !S.watch ? 'servidor sí · reloj no conectado' : (performance.now() - S.lastSampleAt > 1500 ? 'reloj conectado · sin muestras (¿pantalla apagada o sensores pausados?)' : 'en vivo');
}
setInterval(setEstado, 500);

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
        if (typeof v.x !== 'number' || typeof v.y !== 'number' || typeof v.z !== 'number') continue;
        if (name === 'GYROSCOPE') onGyro(t, v);
        else if (name === 'GRAVITY') onGravity(v);
        else continue;
        S.lastSampleAt = performance.now();
      }
    }
  };
}
connect();
