// Dibuja con el reloj, en 1D, 2D y 3D.
//
// Lápiz: mantener el botón atrás del reloj (o Espacio) = lápiz abajo. Bisel: cambia el color.
// Apuntar: como el ratón aéreo; tasas del giroscopio referidas a la gravedad (yaw alrededor de la vertical,
// pitch alrededor del eje horizontal perpendicular al antebrazo) integradas a ángulos. Es la "sombra" de un
// puntero, lo que mejor reconstruye tus trazos en los datos.
//   1D: sismógrafo. Un solo ángulo (pitch, yaw o roll; E lo cambia) mueve la aguja arriba y abajo; el papel corre solo.
//   2D: lienzo. Yaw → x, pitch → y.
//   3D: la dirección (yaw, pitch) es un rayo desde tus ojos y la profundidad sale de girar el antebrazo
//       (roll, como atornillar: horario aleja, antihorario acerca). Arrastra con el ratón para orbitar.
//   Modo creativo (F, en 3D): vuelas libre como en Minecraft creativo (WASD, E sube, Q baja, arrastrar con
//       el ratón para mirar, rueda para avanzar) y el lápiz va delante de ti, apuntado con la muñeca.
//   (El botón de inicio del reloj es también el de encendido: mantenerlo abre el asistente o el menú de
//   apagado y puede reiniciar el reloj, así que la página no lo usa.)
'use strict';

const AX = [1, 0, 0];                   // antebrazo = x del reloj
const COLORS = ['#58c4dd', '#f0997b', '#5dcaa5', '#ffd166', '#c39bf0', '#f4a6b8', '#ece9e1', '#ff6b6b'];
const PX_PER_DEG = 16;                  // 2D: píxeles por grado de muñeca
const DEPTH_PER_DEG = 0.02;             // 3D: metros por grado de giro del antebrazo
const S = {
  mode: 2, grav: null, bias: [0, 0, 0], lastT: null,
  yaw: 0, pitch: 0, roll: 0, pen: false, color: 0,
  creative: false, view: false, depthSign: 1, camYaw: 0, camPitch: 0, keys: new Set(),
  connected: false, watch: false, lastSample: 0, hzCount: 0, hz: 0, hzT: performance.now(),
};
const $ = (id) => document.getElementById(id);
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => Math.hypot(a[0], a[1], a[2]);

// ---------- orientación ----------
function onGyro(t, v) {
  if (S.lastT === null || !S.grav) { S.lastT = t; return; }
  let dt = (t - S.lastT) / 1000; S.lastT = t;
  if (!(dt > 0) || dt > 0.1) dt = 0.01;
  const raw = [v.x, v.y, v.z];
  const w = raw.map((x, i) => x - S.bias[i]);
  if (norm(w) < 2) for (let i = 0; i < 3; i++) S.bias[i] += 0.002 * (raw[i] - S.bias[i]);
  const gn = norm(S.grav), g = S.grav.map((x) => x / gn);
  const roll = dot(w, AX), gpf = dot(g, AX);
  let yaw = (dot(w, g) - roll * gpf) / Math.max(1 - gpf * gpf, 0.09);
  const c = cross(AX, g), cn = norm(c);
  let pitch = cn > 0.3 ? dot(w, c.map((x) => x / cn)) : 0;
  if (Math.hypot(yaw, pitch) < 0.6) { yaw = 0; pitch = 0; }
  if (S.view && S.mode === 3) {           // botón de inicio mantenido: la muñeca mueve la cámara
    S.camYaw += 1.5 * yaw * dt * Math.PI / 180;
    S.camPitch = Math.max(-1.4, Math.min(1.4, S.camPitch + 1.5 * pitch * dt * Math.PI / 180));
    setCamRotation();
    S.hzCount++;
    return;
  }
  S.yaw -= yaw * dt;                    // derecha positiva
  S.pitch += pitch * dt;                // arriba positiva
  if (Math.abs(roll) > 1) S.roll += roll * dt;
  S.hzCount++;
  sample();
}

function recenter() { S.yaw = 0; S.pitch = 0; S.roll = 0; }
function setPen(down) {
  if (down === S.pen) return;
  S.pen = down;
  if (down) startStroke(); else endStroke();
  $('pen').firstChild.nodeValue = down ? 'lápiz abajo ' : 'lápiz arriba ';
}
function nextColor(d) {
  S.color = (S.color + d + COLORS.length) % COLORS.length;
  $('swatch').style.background = COLORS[S.color];
}
nextColor(0);

// ---------- 2D y 1D: lienzo ----------
const c2 = $('c2'), g2 = c2.getContext('2d');
const strokes2 = [];                    // {mode, color, pts:[[x,y]]}
let paperX = 0;                         // 1D: cuánto ha corrido el papel
function resize2() { const d = Math.min(devicePixelRatio, 2); c2.width = innerWidth * d; c2.height = innerHeight * d; g2.setTransform(d, 0, 0, d, 0, 0); }
addEventListener('resize', resize2); resize2();
// 1D: qué ángulo escribe la aguja. Pulsa otra vez el botón 1D (o E) para cambiarlo.
const AXES1 = [
  { key: 'pitch', name: 'inclinar', how: 'sube y baja la muñeca', px: 16 },
  { key: 'yaw', name: 'girar', how: 'mueve la muñeca a izquierda (abajo) y derecha (arriba)', px: 16 },
  { key: 'roll', name: 'atornillar', how: 'gira el antebrazo como un destornillador', px: 6 },
];
let axis1 = 0;
function point2() {
  if (S.mode === 2) return [innerWidth / 2 + S.yaw * PX_PER_DEG, innerHeight / 2 - S.pitch * PX_PER_DEG];
  const a = AXES1[axis1];
  return [paperX, innerHeight / 2 - S[a.key] * a.px];               // 1D: la x es el tiempo
}

// ---------- 3D: espacio ----------
const c3 = $('c3');
const R = new THREE.WebGLRenderer({ canvas: c3, antialias: true });
R.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x10131a); scene.fog = new THREE.Fog(0x10131a, 8, 22);
scene.add(new THREE.HemisphereLight(0xfff4e6, 0x6a5a8a, 0.9));
const sun = new THREE.DirectionalLight(0xffffff, 0.6); sun.position.set(3, 6, 4); scene.add(sun);
const grid = new THREE.GridHelper(20, 20, 0x2c3546, 0x1c2230); grid.position.y = -1.4; scene.add(grid);
const cam = new THREE.PerspectiveCamera(60, 1, 0.05, 100); cam.position.set(0, 0, 0); cam.lookAt(0, 0, -1);
const orbit = new THREE.OrbitControls(cam, c3); orbit.target.set(0, 0, -3); orbit.enabled = false;
const MAXB = 40000;
const blob = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.035, 0), new THREE.MeshStandardMaterial({ flatShading: true, roughness: 0.6 }), MAXB);
blob.count = 0; blob.instanceMatrix.setUsage(THREE.DynamicDrawUsage); scene.add(blob);
const tip = new THREE.Mesh(new THREE.IcosahedronGeometry(0.06, 0), new THREE.MeshStandardMaterial({ color: 0xffffff, flatShading: true, emissive: 0x222222 }));
scene.add(tip);
const ray = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: 0x3a4658 }));
scene.add(ray);
const _m = new THREE.Matrix4(), _c = new THREE.Color();
function resize3() { R.setSize(innerWidth, innerHeight, false); cam.aspect = innerWidth / innerHeight; cam.updateProjectionMatrix(); }
addEventListener('resize', resize3); resize3();
function point3() {
  const y = S.yaw * Math.PI / 180, p = S.pitch * Math.PI / 180;
  const depth = Math.max(0.8, Math.min(9, 3 + S.depthSign * S.roll * DEPTH_PER_DEG));   // atornillar aleja; I lo invierte
  const local = new THREE.Vector3(Math.sin(y) * Math.cos(p), Math.sin(p), -Math.cos(y) * Math.cos(p)).multiplyScalar(depth);
  if (!S.creative) return local;
  return local.applyQuaternion(cam.quaternion).add(cam.position);    // creativo: el lápiz va delante de la cámara
}

// ---------- modo creativo: vuelo libre ----------
function setCamRotation() { cam.rotation.set(S.camPitch, S.camYaw, 0, 'YXZ'); }
function creativeStep(dt) {
  const k = S.keys, speed = (k.has('ShiftLeft') || k.has('ShiftRight') ? 6 : 2.5) * dt;
  const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(cam.quaternion); fwd.y = 0; fwd.normalize();
  const right = new THREE.Vector3(1, 0, 0).applyQuaternion(cam.quaternion); right.y = 0; right.normalize();
  if (k.has('KeyW')) cam.position.addScaledVector(fwd, speed);
  if (k.has('KeyS')) cam.position.addScaledVector(fwd, -speed);
  if (k.has('KeyD')) cam.position.addScaledVector(right, speed);
  if (k.has('KeyA')) cam.position.addScaledVector(right, -speed);
  if (k.has('KeyE')) cam.position.y += speed;
  if (k.has('KeyQ')) cam.position.y -= speed;
  if (S.pen && k.size) sample();                                       // volar con el lápiz abajo también traza
}
function setCreative(on) {
  S.creative = on && S.mode === 3;
  orbit.enabled = false;
  cam.position.set(0, 0, 0); S.camYaw = 0; S.camPitch = 0; setCamRotation();
  $('creative').classList.toggle('on', S.creative);
  setMode(S.mode, true);
}
function setView(on) {                   // botón de inicio: modo cámara (activa el creativo si hace falta)
  if (S.mode !== 3) return;
  if (on && !S.creative) setCreative(true);
  S.view = on;
  if (on) endStroke();
  $('pen').firstChild.nodeValue = on ? 'cámara: la muñeca gira la vista ' : (S.pen ? 'lápiz abajo ' : 'lápiz arriba ');
}
let drag = null;
c3.addEventListener('pointerdown', (e) => { if (S.creative) { drag = [e.clientX, e.clientY]; c3.setPointerCapture(e.pointerId); } });
c3.addEventListener('pointermove', (e) => {
  if (!S.creative || !drag) return;
  S.camYaw -= (e.clientX - drag[0]) * 0.004;
  S.camPitch = Math.max(-1.4, Math.min(1.4, S.camPitch - (e.clientY - drag[1]) * 0.004));
  drag = [e.clientX, e.clientY]; setCamRotation();
});
c3.addEventListener('pointerup', () => { drag = null; });
c3.addEventListener('wheel', (e) => {
  if (!S.creative) return;
  e.preventDefault();
  cam.position.addScaledVector(new THREE.Vector3(0, 0, -1).applyQuaternion(cam.quaternion), -e.deltaY * 0.004);
}, { passive: false });
let last3 = null;
function addBlob(pos) {
  if (blob.count >= MAXB) return;
  _m.makeTranslation(pos.x, pos.y, pos.z); blob.setMatrixAt(blob.count, _m);
  blob.setColorAt(blob.count, _c.set(COLORS[S.color])); blob.count++;
  blob.instanceMatrix.needsUpdate = true; if (blob.instanceColor) blob.instanceColor.needsUpdate = true;
}

// ---------- trazos ----------
let cur = null;
function startStroke() {
  if (S.mode === 3) { last3 = null; return; }
  cur = { mode: S.mode, color: COLORS[S.color], pts: [point2()] };
  strokes2.push(cur);
}
function endStroke() { cur = null; last3 = null; }
function sample() {
  if (!S.pen || S.view) return;
  if (S.mode === 3) {
    const p = point3();
    if (!last3) { addBlob(p); last3 = p; return; }
    const d = p.distanceTo(last3), n = Math.min(40, Math.ceil(d / 0.02));     // rellenar huecos: trazo continuo
    for (let k = 1; k <= n; k++) addBlob(last3.clone().lerp(p, k / n));
    last3 = p;
  } else if (cur) cur.pts.push(point2());
}

// ---------- modos, teclado y ratón ----------
function setMode(m, keepCreative) {
  endStroke(); S.mode = m;
  if (!keepCreative && S.creative && m !== 3) { S.creative = false; S.view = false; $('creative').classList.remove('on'); }
  $('creative').style.display = m === 3 ? '' : 'none';
  document.querySelectorAll('#modes button[data-m]').forEach((b) => b.classList.toggle('on', Number(b.dataset.m) === m));
  document.querySelector('#modes button[data-m="1"]').textContent = '1D ' + AXES1[axis1].name;
  c3.style.display = m === 3 ? 'block' : 'none'; c2.style.display = m === 3 ? 'none' : 'block';
  if (!S.creative) { orbit.enabled = false; cam.position.set(0, 0, 0); cam.lookAt(0, 0, -1); }
  const depthTxt = S.depthSign > 0 ? 'horario aleja' : 'horario acerca';
  $('help').innerHTML = (S.creative && m === 3)
    ? '<b>Creativo</b>: vuela con <b>W A S D</b>, <b>E</b> sube, <b>Q</b> baja (Mayús: rápido), arrastra para mirar, rueda para avanzar. '
      + 'El lápiz va delante de ti: apúntalo con la muñeca, '
      + 'atornilla para alejarlo (' + depthTxt + ', <b>I</b> invierte) y mantén el botón atrás para pintar. <b>F</b>: salir'
      + '<br>R: recentrar · C: borrar · Z: deshacer · Espacio: lápiz sin reloj'
    : {
    1: '<b>1D · ' + AXES1[axis1].name + '</b>: mantén el botón atrás y ' + AXES1[axis1].how + ': la aguja escribe y el papel corre solo. '
      + '<b>E</b> o el botón 1D otra vez: cambiar de eje.',
    2: '<b>2D</b>: mantén el botón atrás y apunta con la muñeca para dibujar. Bisel: color.',
    3: '<b>3D</b>: apunta con la muñeca; atornilla para alejar o acercar el lápiz (' + depthTxt + ', <b>I</b> invierte). Mantén el botón atrás para pintar. '
      + '<b>F</b>: modo creativo (volar). <b>O</b>: orbitar con el ratón.',
  }[m] + '<br>R: recentrar · C: borrar · Z: deshacer · S: guardar imagen · Espacio: lápiz sin reloj';
}
function nextAxis1() { axis1 = (axis1 + 1) % AXES1.length; recenter(); setMode(1); }
document.querySelectorAll('#modes button[data-m]').forEach((b) => b.addEventListener('click', () => {
  const m = Number(b.dataset.m);
  if (m === 1 && S.mode === 1) nextAxis1(); else setMode(m);
}));
$('creative').addEventListener('click', () => setCreative(!S.creative));
addEventListener('keydown', (e) => {
  if (S.creative && ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyE', 'KeyQ', 'ShiftLeft', 'ShiftRight'].includes(e.code)) { S.keys.add(e.code); return; }
  if (e.repeat) return;
  if (e.key === 'f' || e.key === 'F') { if (S.mode === 3) setCreative(!S.creative); return; }
  if (e.key === 'i' || e.key === 'I') { S.depthSign = -S.depthSign; setMode(S.mode, true); return; }
  if (e.code === 'Space') { e.preventDefault(); setPen(true); }
  else if (e.key === 'r' || e.key === 'R') recenter();
  else if (e.key === 'c' || e.key === 'C') { strokes2.length = 0; blob.count = 0; blob.instanceMatrix.needsUpdate = true; }
  else if (e.key === 'z' || e.key === 'Z') { if (S.mode === 3) { blob.count = Math.max(0, blob.count - 300); blob.instanceMatrix.needsUpdate = true; } else strokes2.pop(); }
  else if (e.key === 's' || e.key === 'S') save();
  else if ((e.key === 'e' || e.key === 'E') && S.mode === 1) nextAxis1();
  else if (e.key === 'o' || e.key === 'O') { if (S.mode === 3 && !S.creative) { orbit.enabled = !orbit.enabled; if (orbit.enabled) { cam.position.set(4, 2.5, 3); orbit.target.set(0, 0, -3); orbit.update(); } else { cam.position.set(0, 0, 0); cam.lookAt(0, 0, -1); } } }
  else if (['1', '2', '3'].includes(e.key)) setMode(Number(e.key));
});
addEventListener('keyup', (e) => { S.keys.delete(e.code); if (e.code === 'Space') setPen(false); });
addEventListener('blur', () => S.keys.clear());
function save() {
  const a = document.createElement('a');
  if (S.mode === 3) { R.render(scene, cam); a.href = c3.toDataURL('image/png'); } else a.href = c2.toDataURL('image/png');
  a.download = `dibujo-${S.mode}d.png`; a.click();
}

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
        if (name === 'BUTTON') {
          if (v.key === 'back') setPen(v.pressed === true);
          continue;
        }
        if (name === 'BEZEL') { nextColor(v.direction === 'CW' ? 1 : -1); continue; }
        if (typeof v.x !== 'number') continue;
        S.lastSample = performance.now(); S.watch = true;
        if (name === 'GRAVITY') S.grav = [v.x, v.y, v.z];
        else if (name === 'GYROSCOPE') onGyro(t, v);
      }
    }
  };
}
connect();

// ---------- bucle ----------
function draw2(now) {
  const W = innerWidth, H = innerHeight;
  if (S.mode === 1) paperX += 120 * (1 / 60);                       // el papel corre ~120 px/s
  g2.fillStyle = '#10131a'; g2.fillRect(0, 0, W, H);
  g2.save();
  if (S.mode === 1) {
    const shift = Math.max(0, paperX - W * 0.8); g2.translate(-shift, 0);
    g2.strokeStyle = '#1c2230'; g2.lineWidth = 1;
    for (let x = Math.floor(shift / 60) * 60; x < shift + W; x += 60) { g2.beginPath(); g2.moveTo(x, 0); g2.lineTo(x, H); g2.stroke(); }
    for (let y = H / 2 % 40; y < H; y += 40) { g2.beginPath(); g2.moveTo(shift, y); g2.lineTo(shift + W, y); g2.stroke(); }
  }
  g2.lineCap = 'round'; g2.lineJoin = 'round';
  for (const s of strokes2) {
    if (s.mode !== S.mode || s.pts.length < 2) continue;
    g2.strokeStyle = s.color; g2.lineWidth = 4; g2.beginPath(); g2.moveTo(...s.pts[0]);
    for (const p of s.pts) g2.lineTo(...p);
    g2.stroke();
  }
  const [x, y] = point2();                                           // la punta del lápiz
  g2.fillStyle = S.pen ? COLORS[S.color] : 'transparent'; g2.strokeStyle = COLORS[S.color]; g2.lineWidth = 2;
  g2.beginPath(); g2.arc(x, y, S.pen ? 6 : 9, 0, 2 * Math.PI); S.pen ? g2.fill() : g2.stroke();
  g2.restore();
}
function frame(now) {
  requestAnimationFrame(frame);
  if (now - S.hzT >= 1000) { S.hz = S.hzCount * 1000 / (now - S.hzT); S.hzCount = 0; S.hzT = now; }
  if (S.mode === 1 && S.pen && cur) cur.pts.push(point2());         // en 1D el papel corre aunque la muñeca no se mueva
  const dt = Math.min(0.05, (now - (frame.last || now)) / 1000); frame.last = now;
  if (S.mode === 3) {
    if (S.creative) creativeStep(dt);
    const p = point3(); tip.position.copy(p); tip.material.color.set(COLORS[S.color]);
    const hand = new THREE.Vector3(0.15, -0.25, -0.1).applyQuaternion(cam.quaternion).add(cam.position);
    ray.geometry.setFromPoints([S.creative ? hand : new THREE.Vector3(0, -0.25, 0), p]);
    tip.visible = !S.view;
    if (orbit.enabled) orbit.update();
    R.render(scene, cam);
  } else draw2(now);
  const stale = now - S.lastSample > 600;
  $('conn').textContent = !S.connected ? 'sin servidor: reintentando…' : !S.watch ? 'servidor sí · reloj no conectado'
    : stale ? 'el reloj no manda datos · toca su pantalla' : `reloj · ${S.hz.toFixed(0)} Hz`;
}
setMode(2);
requestAnimationFrame(frame);
