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
// Todo se guarda solo en el servidor mientras dibujas (recordings/dibujos/, formato en trazos.js). Abrir:
// tus dibujos guardados. P: reproducirlo como timelapse. X: exportarlo como una página que se ve en cualquier
// lado (visor.html con el dibujo dentro).
//   (El botón de inicio del reloj es también el de encendido: mantenerlo abre el asistente o el menú de
//   apagado y puede reiniciar el reloj, así que la página no lo usa.)
'use strict';

const wrist = new Wrist();               // muñeca izquierda o derecha (M), compartida con las otras páginas
const COLORS = ['#58c4dd', '#f0997b', '#5dcaa5', '#ffd166', '#c39bf0', '#f4a6b8', '#ece9e1', '#ff6b6b'];
const PX_PER_DEG = 16;                  // 2D: píxeles por grado de muñeca
const DEPTH_PER_DEG = 0.02;             // 3D: metros por grado de giro del antebrazo
const S = {
  mode: 2, grav: null, lastT: null,
  yaw: 0, pitch: 0, roll: 0, pen: false, color: 0,
  creative: false, view: false, depthSign: 1, camYaw: 0, camPitch: 0, keys: new Set(),
  connected: false, watch: false, lastSample: 0, hzCount: 0, hz: 0, hzT: performance.now(),
};
const $ = (id) => document.getElementById(id);

// ---------- orientación ----------
function onGyro(t, v) {
  if (S.lastT === null || !S.grav) { S.lastT = t; return; }
  let dt = (t - S.lastT) / 1000; S.lastT = t;
  if (!(dt > 0) || dt > 0.1) dt = 0.01;
  const { yaw, pitch, roll } = wrist.rates([v.x, v.y, v.z], S.grav);
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
function showHand() { $('hand').textContent = handName(wrist.hand); }
function toggleHand() { wrist.toggleHand(); recenter(); showHand(); }
showHand();
$('hand').addEventListener('click', toggleHand);
function setPen(down) {
  if (down && RP.on) { stopReplay(); return; }
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
blob.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAXB * 3), 3);   // con su tamaño: si nace con count 0 queda vacío
blob.count = 0; blob.instanceMatrix.setUsage(THREE.DynamicDrawUsage); blob.instanceColor.setUsage(THREE.DynamicDrawUsage); scene.add(blob);
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
function addBlob(q, color) {
  if (blob.count >= MAXB) return;
  _m.makeTranslation(q[0], q[1], q[2]); blob.setMatrixAt(blob.count, _m);
  blob.setColorAt(blob.count, _c.set(color)); blob.count++;
  blob.instanceMatrix.needsUpdate = true; blob.instanceColor.needsUpdate = true;
}

// ---------- el dibujo: operaciones que se aplican, se guardan y se reproducen (trazos.js) ----------
const D = new Drawing({
  blob: addBlob,                                                       // 3D: las bolitas, cada 2 cm del trazo
  truncate3: (n) => { blob.count = Math.min(n, MAXB); blob.instanceMatrix.needsUpdate = true; },
});
const SAVE = { id: null, t0: 0, ops: [], queue: [], pend: null, seq: 0, outbox: [], base: null };
let nextId = 1, curId = null;
const pad2 = (n) => String(n).padStart(2, '0');
function newSessionId() {
  const d = new Date();
  return `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}-${pad2(d.getHours())}${pad2(d.getMinutes())}${pad2(d.getSeconds())}`;
}
function clock() { if (!SAVE.id) beginSession(); return Math.round(performance.now() - SAVE.t0); }
function beginSession() {                // la primera operación abre el archivo; si abriste un dibujo, va entero delante
  let base = SAVE.base || [];
  SAVE.base = null;
  SAVE.id = newSessionId(); SAVE.ops = []; SAVE.seq = 0;
  let lastT = 0;
  for (const op of base) for (const t of op.k === 'p' ? op.pts.map((p) => p[p.length - 1]) : [op.t]) if (t > lastT) lastT = t;
  SAVE.t0 = performance.now() - (base.length ? lastT + 1000 : 0);
  const head = { k: 'h', v: 1, start: new Date().toISOString(), hand: wrist.hand, view: [innerWidth, innerHeight] };
  if (base.length && base[0].k === 'h') { if (base[0].start) head.from = base[0].start; base = base.slice(1); }
  record(head);
  for (const op of base) record(op);
}
function record(op) { flushPoints(); SAVE.ops.push(op); SAVE.queue.push(op); }
function flushPoints() { if (SAVE.pend) { const p = SAVE.pend; SAVE.pend = null; SAVE.ops.push(p); SAVE.queue.push(p); } }
function emit(op) { op.t = clock(); record(op); D.apply(op); }
function emitPoint(xy) {
  const pt = [...xy, clock()];
  D.apply({ k: 'p', id: curId, pts: [pt] });
  if (SAVE.pend && SAVE.pend.id === curId) SAVE.pend.pts.push(pt);
  else { flushPoints(); SAVE.pend = { k: 'p', id: curId, pts: [pt] }; }
}
function batch() {                       // lo pendiente pasa a un lote numerado para el servidor
  flushPoints();
  if (SAVE.queue.length) SAVE.outbox.push({ id: SAVE.id, seq: SAVE.seq++, lines: SAVE.queue.splice(0), sent: false });
}
function pump() {
  batch();
  const b = SAVE.outbox[0];
  if (b && !b.sent && S.ws && S.ws.readyState === WebSocket.OPEN) {
    S.ws.send(JSON.stringify({ type: 'dibujo', id: b.id, seq: b.seq, lines: b.lines }));
    b.sent = true;
  }
}
setInterval(pump, 1000);
addEventListener('pagehide', pump);
addEventListener('beforeunload', (e) => { batch(); if (SAVE.outbox.length) { pump(); e.preventDefault(); e.returnValue = ''; } });
const currentOps = () => { flushPoints(); return SAVE.id ? SAVE.ops : (SAVE.base || []); };

// ---------- trazos ----------
const r1 = (x) => Math.round(x * 10) / 10, r3 = (x) => Math.round(x * 1000) / 1000;
function startStroke() {
  if (RP.on) return;
  curId = nextId++;
  emit({ k: 's', id: curId, m: S.mode, c: COLORS[S.color] });
  if (S.mode !== 3) emitPoint(point2().map(r1));
}
function endStroke() { curId = null; }
function sample() {
  if (!S.pen || S.view || curId === null || RP.on) return;
  if (S.mode === 3) { const p = point3(); emitPoint([r3(p.x), r3(p.y), r3(p.z)]); }
  else emitPoint(point2().map(r1));
}

// ---------- reproducir: el dibujo vuelve a pasar como timelapse ----------
const RP = { on: false, ev: [], i: 0, t0: 0, speed: 2 };
function startReplay() {
  const ops = currentOps();
  if (!ops.length) { flash('aún no hay nada que reproducir'); return; }
  setPen(false);
  const modes = modesOf(ops);
  if (modes.length && !modes.includes(S.mode)) setMode(modes.includes(3) ? 3 : modes[modes.length - 1]);
  if (S.mode === 3) {                    // vista en órbita alrededor del dibujo, girando sola
    if (S.creative) setCreative(false);
    const c = new THREE.Vector3(); let n = 0;
    for (const s of D.s3) for (let i = 0; i < s.pts.length; i += 5) { c.x += s.pts[i][0]; c.y += s.pts[i][1]; c.z += s.pts[i][2]; n++; }
    if (n) c.divideScalar(n); else c.set(0, 0, -3);
    orbit.enabled = true; orbit.autoRotate = true; orbit.autoRotateSpeed = 1.2;
    orbit.target.copy(c); cam.position.set(c.x + 3.5, c.y + 1.8, c.z + 4.5); orbit.update();
  }
  RP.ev = timeline(ops); RP.i = 0; RP.t0 = performance.now(); RP.on = true;
  D.reset();
  for (const op of ops) if (op.k === 's') nextId = Math.max(nextId, op.id + 1);
}
function stepReplay(now) {
  const at = (now - RP.t0) * RP.speed;
  while (RP.i < RP.ev.length && RP.ev[RP.i].at <= at) D.apply(RP.ev[RP.i++].op);
  if (RP.i >= RP.ev.length) { RP.on = false; orbit.autoRotate = false; }
}
function stopReplay() { RP.t0 = -1e12; stepReplay(performance.now()); }

// ---------- abrir: tus dibujos guardados, o un archivo (.jsonl, el rescate .json o una página exportada) ----------
function openOps(ops, saveNow) {
  if (RP.on) stopReplay();
  setPen(false);
  batch();                               // lo que quedaba del dibujo anterior sale con su propio nombre
  D.reset(); paperX = 0;
  const modeOf = new Map();
  for (const op of ops) {
    if (op.k === 'h') continue;
    D.apply(op);
    if (op.k === 's') { nextId = Math.max(nextId, op.id + 1); modeOf.set(op.id, op.m); }
    if (op.k === 'p' && modeOf.get(op.id) === 1) for (const p of op.pts) paperX = Math.max(paperX, p[0]);   // 1D: el papel sigue donde iba
  }
  SAVE.id = null; SAVE.ops = []; SAVE.base = ops;
  if (saveNow) clock();                  // vino de fuera: se guarda ya como dibujo nuevo
  $('open').style.display = 'none';
  startReplay();
}
async function showOpen() {
  const box = $('open');
  if (box.style.display === 'block') { box.style.display = 'none'; return; }
  box.style.display = 'block';
  const list = $('openlist');
  list.textContent = 'buscando…';
  let files = [];
  try { files = await (await fetch('/dibujos/')).json(); } catch { list.textContent = 'el servidor no respondió'; return; }
  list.textContent = files.length ? '' : 'todavía no hay dibujos guardados';
  for (const f of files) {
    const m = f.name.match(/(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/);
    const row = document.createElement('div'); row.className = 'row';
    const go = document.createElement('button');
    go.textContent = m ? `${m[3]}/${m[2]} ${m[4]}:${m[5]}` : f.name;
    go.title = `${f.name} · ${(f.bytes / 1024).toFixed(0)} KB`;
    go.addEventListener('click', async () => { openOps(parseDrawing(await (await fetch('/dibujos/' + f.name)).text()), false); });
    const size = document.createElement('span'); size.textContent = `${(f.bytes / 1024).toFixed(0)} KB`;
    const view = document.createElement('a'); view.href = 'visor.html?f=' + encodeURIComponent(f.name); view.target = '_blank'; view.textContent = 'visor';
    row.append(go, size, view); list.append(row);
  }
}
$('openbtn').addEventListener('click', showOpen);
$('openfile').addEventListener('change', async (e) => {
  const file = e.target.files[0]; e.target.value = '';
  if (!file) return;
  let text = await file.text();
  const emb = text.match(/<script id="dibujo" type="application\/x-ndjson">([\s\S]*?)<\/script>/);
  if (emb) text = emb[1];
  try { openOps(parseDrawing(text), true); } catch (err) { flash('no entendí ese archivo'); }
});

// ---------- exportar: una página con el dibujo dentro, que se reproduce en cualquier navegador ----------
async function exportPage() {
  const ops = currentOps();
  if (!ops.length) { flash('aún no hay nada que exportar'); return; }
  pump();
  const [visor, lib] = await Promise.all([fetch('visor.html').then((r) => r.text()), fetch('trazos.js').then((r) => r.text())]);
  const data = toJSONL(ops).replace(/</g, '\\u003c');
  const html = visor
    .replace('<script src="trazos.js"></script>', () => '<script>\n' + lib.replace(/<\/script/gi, '<\\/script') + '</script>')
    .replace('<script id="dibujo" type="application/x-ndjson"></script>', () => '<script id="dibujo" type="application/x-ndjson">\n' + data + '</script>');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
  a.download = `dibujo-${SAVE.id || 'abierto'}.html`; a.click();
  flash('exportado: ábrelo en cualquier navegador');
}
function flash(text) { const el = $('flash'); el.textContent = text; el.style.opacity = 1; clearTimeout(flash.t); flash.t = setTimeout(() => { el.style.opacity = 0; }, 2200); }
$('replaybtn').addEventListener('click', () => (RP.on ? stopReplay() : startReplay()));
$('exportbtn').addEventListener('click', exportPage);

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
      + '<br>R: recentrar · C: borrar · Z: deshacer · P: reproducir · X: exportar · Espacio: lápiz sin reloj'
    : {
    1: '<b>1D · ' + AXES1[axis1].name + '</b>: mantén el botón atrás y ' + AXES1[axis1].how + ': la aguja escribe y el papel corre solo. '
      + '<b>E</b> o el botón 1D otra vez: cambiar de eje.',
    2: '<b>2D</b>: mantén el botón atrás y apunta con la muñeca para dibujar. Bisel: color.',
    3: '<b>3D</b>: apunta con la muñeca; atornilla para alejar o acercar el lápiz (' + depthTxt + ', <b>I</b> invierte). Mantén el botón atrás para pintar. '
      + '<b>F</b>: modo creativo (volar). <b>O</b>: orbitar con el ratón.',
  }[m] + '<br>Se guarda solo · P: reproducir · X: exportar · R: recentrar · C: borrar · Z: deshacer · S: imagen · M: muñeca · Espacio: lápiz sin reloj';
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
  else if (e.key === 'c' || e.key === 'C') { if (RP.on) stopReplay(); setPen(false); emit({ k: 'c' }); }
  else if (e.key === 'z' || e.key === 'Z') { if (RP.on) stopReplay(); setPen(false); emit({ k: 'z', m: S.mode }); }
  else if (e.key === 'p' || e.key === 'P') { if (RP.on) stopReplay(); else startReplay(); }
  else if (e.key === 'x' || e.key === 'X') exportPage();
  else if (e.key === 's' || e.key === 'S') save();
  else if ((e.key === 'e' || e.key === 'E') && S.mode === 1) nextAxis1();
  else if (e.key === 'm' || e.key === 'M') toggleHand();
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
  S.ws = ws;
  ws.onopen = () => { S.connected = true; if (SAVE.outbox[0]) SAVE.outbox[0].sent = false; pump(); };   // reenviar lo no confirmado
  ws.onclose = () => { S.connected = false; S.watch = false; setTimeout(connect, 1500); };
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === 'watch') S.watch = !!msg.connected;
    else if (msg.type === 'hello') { S.watch = true; S.lastT = null; }
    else if (msg.type === 'dibujo_ack') {
      const b = SAVE.outbox[0];
      if (b && b.id === msg.id && b.seq === msg.seq) { SAVE.outbox.shift(); pump(); }
    } else if (msg.type === 'data' && Array.isArray(msg.samples)) {
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
  for (const s of D.s2) {
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
  if (RP.on) stepReplay(now);
  if (S.mode === 1 && S.pen && curId !== null && !RP.on) emitPoint(point2().map(r1));   // en 1D el papel corre aunque la muñeca no se mueva
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
  const saved = !SAVE.id ? '' : (SAVE.outbox.length || SAVE.queue.length || SAVE.pend) ? ' · guardando…' : ' · guardado';
  $('conn').textContent = (!S.connected ? 'sin servidor: reintentando…' : !S.watch ? 'servidor sí · reloj no conectado'
    : stale ? 'el reloj no manda datos · toca su pantalla' : `reloj · ${S.hz.toFixed(0)} Hz`) + saved;
  $('replaybtn').textContent = RP.on ? '■ Parar' : '▶ Reproducir';
}
setMode(2);
requestAnimationFrame(frame);
