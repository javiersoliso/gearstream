// Mocap con un reloj: el escenario (la cuenta está en mocapmath.js).
//   Animaciones (caminar, tablet, apuntar): el esqueleto cian es la verdad; de su muñeca sale lo que leería
//   el reloj (giroscopio, acelerómetro, gravedad, con ruido si quieres); con esas lecturas se reconstruye el
//   antebrazo coral. Si cae encima del cian, la extracción tiene sentido.
//   Tus grabaciones (tools/export_mocap.py, servidas en /grabaciones/): el antebrazo del reloj lo mueven tus
//   datos; el resto del cuerpo está de pie, quieto.
//   Apuntar: el rayo del antebrazo pega en una pantalla virtual (cursor cian, la verdad) y el cursor coral es el
//   del reloj, calculado como el ratón aéreo: x = −∫yaw, y = ∫pitch.
// Abajo, las gráficas de cada sensor como en un programa de captura, con la línea del momento actual.
'use strict';

const $ = (id) => document.getElementById(id);
const { cross, sub, len } = vec;
const COL = { joint: 0x58c4dd, bone: 0xcfd6e4, ghost: 0xf0997b, up: 0xffd166, w: 0x9db4ff, lin: 0x5dcaa5 };
const XYZ = ['#a99bff', '#f28ab2', '#ff9a6b'], RYP = ['#a99bff', '#ffd166', '#f28ab2'];
const GHOSTS = ['fusion', 'proyeccion', 'no'];
const GHOST_NAME = { fusion: 'Fusión', proyeccion: 'Proyección', no: 'Sin reconstrucción' };
const SPEEDS = [1, 0.5, 0.25, 2];
const S = {
  src: 'caminar', take: null, side: loadHand() === 'right' ? 'r' : 'l', noise: true, ghost: 'fusion',
  playing: true, speed: 1, t: 0, cam: 'orbita', imu: null, rec: null, dur: 1, scales: null, cursor: null,
};
let LAST = null;                           // el último cuadro (lo usa el modo comercial, mocapfilm.js)
const filming = () => typeof FILM !== 'undefined' && FILM.on;

// ---------- escena ----------
const stage = $('stage');
const R = new THREE.WebGLRenderer({ canvas: $('c3'), antialias: true, alpha: true });   // transparente: el modo comercial pinta el fondo
R.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b0e14); scene.fog = new THREE.Fog(0x0b0e14, 7, 18);
scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x1a1f2a, 0.9));
const keyL = new THREE.DirectionalLight(0xffffff, 0.7); keyL.position.set(3, 5, -2); scene.add(keyL);
const grid = new THREE.GridHelper(14, 28, 0x2a3344, 0x161c27); scene.add(grid);
const cam = new THREE.PerspectiveCamera(42, 1, 0.02, 60); cam.position.set(1.9, 1.6, -2.5);
const ctl = new THREE.OrbitControls(cam, R.domElement); ctl.target.set(0, 1, 0); ctl.enableDamping = true;
function resize() { const w = stage.clientWidth, h = stage.clientHeight; R.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(stage); resize();

function skeleton(color, size, max) {
  const pts = new THREE.InstancedMesh(new THREE.SphereGeometry(size, 10, 8), new THREE.MeshBasicMaterial({ color }), max);
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(max * 6), 3));
  const lines = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 }));
  pts.frustumCulled = false; lines.frustumCulled = false;
  scene.add(pts, lines);
  return { pts, lines, geo };
}
const _m = new THREE.Matrix4();
function draw(sk, pts, segs, scale) {
  sk.pts.count = pts.length;
  pts.forEach((p, i) => { _m.makeScale(scale, scale, scale).setPosition(p[0], p[1], p[2]); sk.pts.setMatrixAt(i, _m); });
  sk.pts.instanceMatrix.needsUpdate = true;
  const a = sk.geo.attributes.position.array;
  segs.forEach(([p, q], i) => { a.set(p, i * 6); a.set(q, i * 6 + 3); });
  sk.geo.setDrawRange(0, segs.length * 2); sk.geo.attributes.position.needsUpdate = true;
}
const body = skeleton(COL.joint, 0.02, 64), bodyColor = body.lines.material;
bodyColor.color.set(COL.bone);
const ghost = skeleton(COL.ghost, 0.016, 24);
const headM = new THREE.Mesh(new THREE.SphereGeometry(0.095, 14, 10), new THREE.MeshBasicMaterial({ color: COL.bone, wireframe: true, transparent: true, opacity: 0.5 }));
scene.add(headM);
const watch = new THREE.Group();
const caseM = new THREE.Mesh(new THREE.BoxGeometry(0.046, 0.012, 0.046), new THREE.MeshStandardMaterial({ color: 0x3a3f4a, roughness: 0.4, metalness: 0.4 }));
const face = new THREE.Mesh(new THREE.BoxGeometry(0.038, 0.002, 0.038), new THREE.MeshStandardMaterial({ color: 0x1d9e75, emissive: 0x0b4a37 }));
face.position.y = 0.007; watch.add(caseM, face); watch.matrixAutoUpdate = false; scene.add(watch);
const tablet = new THREE.Mesh(new THREE.BoxGeometry(0.25, 0.008, 0.17), new THREE.MeshStandardMaterial({ color: 0x202634, emissive: 0x16324a, roughness: 0.3 }));
tablet.matrixAutoUpdate = false; scene.add(tablet);
function arrow(col) { const a = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(), 0.1, col, 0.03, 0.016); scene.add(a); return a; }
const aUp = arrow(COL.up), aW = arrow(COL.w), aLin = arrow(COL.lin);
// pantalla virtual (apuntar): un lienzo con íconos y los dos cursores, pegado a un plano delante del cuerpo
const SCR = ANIMS.apuntar.screen, SPX = 400;
const scrCanvas = document.createElement('canvas'); scrCanvas.width = SCR.w * SPX; scrCanvas.height = SCR.h * SPX;
const scrCtx = scrCanvas.getContext('2d'), scrTex = new THREE.CanvasTexture(scrCanvas);
const screenM = new THREE.Mesh(new THREE.PlaneGeometry(SCR.w, SCR.h), new THREE.MeshBasicMaterial({ map: scrTex }));
screenM.position.set(SCR.c[0], SCR.c[1], SCR.c[2]); scene.add(screenM);
const rayGeo = new THREE.BufferGeometry(); rayGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
const ray = new THREE.Line(rayGeo, new THREE.LineBasicMaterial({ color: COL.joint, transparent: true, opacity: 0.55 }));
ray.frustumCulled = false; scene.add(ray);
const trueTrail = [], watchTrail = [], ICON_COL = ['#58c4dd', '#ffd166', '#5dcaa5', '#c39bf0'];
const toPx = (p) => [(p[0] - (SCR.c[0] - SCR.w / 2)) * SPX, (SCR.c[1] + SCR.h / 2 - p[1]) * SPX];
function paintScreen(tp, wp, click) {
  const g = scrCtx, W = scrCanvas.width, H = scrCanvas.height;
  g.fillStyle = '#101826'; g.fillRect(0, 0, W, H);
  g.strokeStyle = '#2a3a55'; g.lineWidth = 6; g.strokeRect(3, 3, W - 6, H - 6);
  g.textAlign = 'center'; g.font = '20px system-ui';
  SCR.icons.forEach(([name, x, y], i) => {
    const [u, v] = toPx([SCR.c[0] + x, SCR.c[1] + y, 0]);
    const over = Math.hypot(tp[0] - SCR.c[0] - x, tp[1] - SCR.c[1] - y) < 0.09;
    g.fillStyle = over && click > 0.4 ? '#ffffff' : over ? ICON_COL[i] : ICON_COL[i] + '55';
    g.beginPath(); g.roundRect(u - 32, v - 32, 64, 64, 14); g.fill();
    g.fillStyle = '#cfd6e4'; g.fillText(name, u, v + 58);
  });
  const line = (pts, col) => {
    if (pts.length < 2) return;
    g.strokeStyle = col; g.lineWidth = 3; g.beginPath();
    pts.forEach((p, i) => { const [u, v] = toPx(p); if (i) g.lineTo(u, v); else g.moveTo(u, v); });
    g.stroke();
  };
  line(trueTrail, '#58c4dd99'); line(watchTrail, '#f0997b99');
  const [tu, tv] = toPx(tp), [wu, wv] = toPx(wp);
  g.strokeStyle = '#58c4dd'; g.lineWidth = 4; g.beginPath(); g.arc(tu, tv, 15, 0, 2 * Math.PI); g.stroke();
  g.fillStyle = '#f0997b'; g.beginPath(); g.arc(wu, wv, 9, 0, 2 * Math.PI); g.fill();
  g.textAlign = 'left'; g.font = '17px system-ui';             // qué es cada línea
  g.strokeStyle = '#58c4dd'; g.lineWidth = 4; g.beginPath(); g.moveTo(20, H - 46); g.lineTo(48, H - 46); g.stroke();
  g.fillStyle = '#9fdcef'; g.fillText('rayo (real)', 56, H - 40);
  g.strokeStyle = '#f0997b'; g.beginPath(); g.moveTo(20, H - 20); g.lineTo(48, H - 20); g.stroke();
  g.fillStyle = '#f5b9a3'; g.fillText('reloj (calculado)', 56, H - 14);
  scrTex.needsUpdate = true;
}
const TRAIL = 90, trailGeo = new THREE.BufferGeometry();
trailGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(TRAIL * 3), 3));
const trailCol = new Float32Array(TRAIL * 3);
for (let i = 0; i < TRAIL; i++) { const f = i / (TRAIL - 1); trailCol.set([0.04 + 0.3 * f, 0.06 + 0.7 * f, 0.08 + 0.8 * f], i * 3); }
trailGeo.setAttribute('color', new THREE.BufferAttribute(trailCol, 3));
const trail = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({ vertexColors: true })); trail.frustumCulled = false; scene.add(trail);
const trailPts = [];
const V3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);
const basis = (x, y, z, p) => new THREE.Matrix4().makeBasis(V3(x), V3(y), V3(z)).setPosition(p[0], p[1], p[2]);

// ---------- datos ----------
const maxAbs = (arr, floor) => { let m = floor; for (const v of arr) if (Math.abs(v) > m) m = Math.abs(v); return m; };
function prepare() {
  if (S.src === 'take') {
    const T = S.take;
    S.imu = { hz: T.hz, n: T.n, acc: Float32Array.from(T.acc), gyr: Float32Array.from(T.gyr), grav: Float32Array.from(T.grav), truth: null };
    S.rec = reconstruct(S.imu, S.side, { method: S.ghost === 'proyeccion' ? 'proyeccion' : 'fusion' });
  } else {
    S.imu = synth(S.src, S.side, { noise: S.noise });
    const tr = S.imu.truth, three = (a) => [a[0], a[1], a[2]];
    const X0 = three(tr.X), Z0 = three(tr.Z);
    S.rec = reconstruct(S.imu, S.side, { method: S.ghost === 'proyeccion' ? 'proyeccion' : 'fusion', frame0: [X0, cross(Z0, X0), Z0], psi0: headingOf(three(tr.F)) });
  }
  S.dur = S.imu.n / S.imu.hz;
  S.t %= S.dur;
  S.cursor = null;
  if (S.src === 'apuntar') {               // como el ratón aéreo, alineado con el rayo al empezar
    const A = ANIMS.apuntar, el0 = build(A.pose(0, S.side)).arms[S.side].el, p0 = A.target(0);
    S.cursor = cursorTrack(S.rec.rates, S.imu.hz, p0, len(sub(p0, el0)) * Math.PI / 180);
  }
  trueTrail.length = 0; watchTrail.length = 0;
  S.scales = { g: maxAbs(S.imu.gyr, 60), a: maxAbs(S.imu.acc, 12), r: maxAbs(S.rec.rates, 60) };
  trailPts.length = 0;
  ui();
}
const idx = () => Math.max(0, Math.min(S.imu.n - 1, Math.floor(S.t * S.imu.hz)));
const at = (arr, k) => [arr[3 * k], arr[3 * k + 1], arr[3 * k + 2]];
const angle = (a, b) => Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))) * 180 / Math.PI;

// ---------- un cuadro ----------
function scene3(dtReal) {
  const k = idx(), recF = at(S.rec.F, k), recZ = at(S.rec.Z, k), kS = S.side === 'l' ? -1 : 1;
  let P;
  if (S.src === 'take') {
    P = idlePose(S.t);
    P.arms[S.side] = { over: { F: recF, d: recZ, flex: 14 }, fist: 0.2 };
  } else P = ANIMS[S.src].pose(S.t, S.side);
  const b = build(P), w = watchOf(b, S.side), js = S.cam === 'muneca' ? 0.4 : 1;   // de cerca, bolitas más chicas
  LAST = { b, P, w, k };
  if (!filming()) for (const o of [body.pts, body.lines, headM, aUp, trail, grid]) o.visible = true;
  draw(body, b.pts, b.segs, js);
  headM.position.set(b.head[0], b.head[1], b.head[2]);
  tablet.visible = !!b.tablet;
  if (b.tablet) tablet.matrix.copy(basis(b.tablet.u, b.tablet.n, cross(b.tablet.u, b.tablet.n), b.tablet.c));
  watch.matrix.copy(basis(w.X, w.Z, w.Y.map((v) => -v), w.p));
  // apuntar: el rayo de verdad y los dos cursores en la pantalla
  screenM.visible = ray.visible = !!S.cursor;
  let cursorErr = null;
  if (S.cursor) {
    const a = ANIMS.apuntar.path(S.t), tp = a.p, wp = at(S.cursor, k), wr = b.arms[S.side].wr;
    if (trueTrail.length && k < S.lastK) { trueTrail.length = 0; watchTrail.length = 0; }   // dio la vuelta
    trueTrail.push(tp); watchTrail.push(wp);
    if (trueTrail.length > 70) { trueTrail.shift(); watchTrail.shift(); }
    rayGeo.attributes.position.array.set([...wr, ...tp]); rayGeo.attributes.position.needsUpdate = true;
    paintScreen(tp, wp, a.click);
    cursorErr = Math.hypot(tp[0] - wp[0], tp[1] - wp[1]) * 100;
  }
  S.lastK = k;
  // el antebrazo reconstruido, desde el mismo codo
  const showGhost = S.src === 'take' || S.ghost !== 'no';
  ghost.pts.visible = ghost.lines.visible = showGhost;
  let err = null;
  if (showGhost) {
    const el = b.arms[S.side].el, wr = vec.add(el, vec.mul(recF, 0.27)), h = hand(wr, recF, recZ, kS, 0.3);
    draw(ghost, [el, wr, ...h.pts], [[el, wr], ...h.segs], js);
    if (S.imu.truth) err = angle(at(S.imu.truth.F, k), recF);
  }
  // flechas en el reloj: gravedad (arriba), giro ω y aceleración sin gravedad, pasadas al mundo con los ejes del reloj
  const toWorld = (v) => [0, 1, 2].map((i) => w.X[i] * v[0] + w.Y[i] * v[1] + w.Z[i] * v[2]);
  const pv = V3(w.p);
  aUp.position.copy(pv); aUp.setDirection(new THREE.Vector3(0, 1, 0)); aUp.setLength(0.22, 0.035, 0.018);
  const gw = at(S.imu.gyr, k), gm = Math.hypot(...gw);
  aW.visible = gm > 5;
  if (aW.visible) { aW.position.copy(pv); aW.setDirection(V3(toWorld(gw)).normalize()); aW.setLength(0.05 + Math.min(0.35, gm / 900), 0.03, 0.016); }
  const la = at(S.imu.acc, k).map((v, i) => v - S.imu.grav[3 * k + i]), lm = Math.hypot(...la);
  aLin.visible = lm > 0.6;
  if (aLin.visible) { aLin.position.copy(pv); aLin.setDirection(V3(toWorld(la)).normalize()); aLin.setLength(Math.min(0.45, 0.04 + lm / 30), 0.03, 0.016); }
  // estela del reloj
  trailPts.push(w.p); if (trailPts.length > TRAIL) trailPts.shift();
  const ta = trailGeo.attributes.position.array, off = TRAIL - trailPts.length;
  for (let i = 0; i < TRAIL; i++) ta.set(trailPts[Math.max(0, i - off)] || w.p, i * 3);
  trailGeo.attributes.position.needsUpdate = true;
  camera(b, P, w, dtReal);
  return { k, err, gm, lm, cursorErr };
}

// ---------- cámaras ----------
const last = new THREE.Vector3(0, 1, 0);
function camera(b, P, w, dt) {
  if (filming()) { FILM.camera(b, P, w); return; }
  const tgt = new THREE.Vector3(b.pelvis[0], b.pelvis[1] + 0.18, b.pelvis[2]);
  const fwd = new THREE.Vector3(-Math.sin(P.H), 0, -Math.cos(P.H)), right = new THREE.Vector3(Math.cos(P.H), 0, -Math.sin(P.H));
  if (S.cam === 'orbita') {
    const d = tgt.clone().sub(last); cam.position.add(d); ctl.target.add(d); last.copy(tgt);
  } else {
    let pos, look = tgt;
    if (S.cam === 'frente') pos = tgt.clone().addScaledVector(fwd, 2.6).add(new THREE.Vector3(0, 0.25, 0));
    else if (S.cam === 'lado') pos = tgt.clone().addScaledVector(right, 2.6).add(new THREE.Vector3(0, 0.25, 0));
    else {                                 // muñeca: detrás, arriba y por fuera del antebrazo, mirando a lo largo de él
      const a = b.arms[S.side], F = V3(a.F), up = new THREE.Vector3(0, 1, 0);
      const Fh = new THREE.Vector3(F.x, 0, F.z);                 // solo el rumbo: el giro de la muñeca no mueve la cámara
      if (Fh.lengthSq() < 1e-3) Fh.copy(fwd);
      Fh.normalize();
      const out = new THREE.Vector3().crossVectors(up, Fh).multiplyScalar(S.side === 'l' ? 1 : -1);
      look = V3(a.wr).addScaledVector(F, 0.12);
      pos = V3(a.wr).addScaledVector(Fh, -0.55).addScaledVector(up, 0.3).addScaledVector(out, 0.2);
    }
    const a = 1 - Math.exp(-dt * 6);
    cam.position.lerp(pos, a); ctl.target.lerp(look, a); last.copy(tgt);
  }
  ctl.update();
}

// ---------- gráficas ----------
const gc = $('g'), g2 = gc.getContext('2d');
function graphs() {
  const d = Math.min(devicePixelRatio, 2), W = gc.clientWidth, H = gc.clientHeight;
  if (gc.width !== Math.round(W * d) || gc.height !== Math.round(H * d)) { gc.width = Math.round(W * d); gc.height = Math.round(H * d); }
  g2.setTransform(d, 0, 0, d, 0, 0);
  g2.fillStyle = '#0f131b'; g2.fillRect(0, 0, W, H);
  const PAST = 4, AHEAD = 2, L = 150, plotW = W - L - 12, X0 = L;
  const xOf = (t) => X0 + (t - (S.t - PAST)) / (PAST + AHEAD) * plotW;
  const loop = S.src !== 'take', n = S.imu.n, hz = S.imu.hz;
  const sample = (arr, t, i) => {
    let k = Math.floor(t * hz);
    if (loop) k = ((k % n) + n) % n; else if (k < 0 || k >= n) return null;
    return arr[3 * k + i];
  };
  const rows = [
    { name: 'giroscopio', unit: '°/s', arr: S.imu.gyr, s: S.scales.g, cols: XYZ, names: ['x', 'y', 'z'] },
    { name: 'acelerómetro', unit: 'm/s²', arr: S.imu.acc, s: S.scales.a, cols: XYZ, names: ['x', 'y', 'z'] },
    { name: 'gravedad', unit: 'm/s²', arr: S.imu.grav, s: 10, cols: XYZ, names: ['x', 'y', 'z'] },
    { name: 'lo que extraemos', unit: '°/s', arr: S.rec.rates, s: S.scales.r, cols: RYP, names: ['roll', 'yaw', 'pitch'] },
  ];
  const rh = (H - 8) / rows.length, k = idx();
  // etiquetas de la toma o de la animación
  const marks = S.src === 'take' ? (S.take.etiquetas || []).map((e) => [e.desde, e.hasta, e.texto]) : (ANIMS[S.src].marks || []);
  g2.font = '11px system-ui';
  for (const [a0, a1, txt] of marks) {
    for (const off of loop ? [-S.dur, 0, S.dur] : [0]) {
      const x0 = Math.max(X0, xOf(a0 + off)), x1 = Math.min(X0 + plotW, xOf(a1 + off));
      if (x1 <= x0) continue;
      g2.fillStyle = 'rgba(255,209,102,0.07)'; g2.fillRect(x0, 4, x1 - x0, H - 8);
      g2.fillStyle = '#ffd166'; g2.fillText(txt, x0 + 4, 14);
    }
  }
  rows.forEach((r, ri) => {
    const y0 = 4 + ri * rh, mid = y0 + rh / 2, amp = rh * 0.42;
    g2.strokeStyle = '#1e2533'; g2.lineWidth = 1;
    g2.beginPath(); g2.moveTo(X0, y0 + rh); g2.lineTo(X0 + plotW, y0 + rh); g2.stroke();
    g2.strokeStyle = '#273042'; g2.beginPath(); g2.moveTo(X0, mid); g2.lineTo(X0 + plotW, mid); g2.stroke();
    g2.fillStyle = '#cfd6e4'; g2.font = '12px system-ui'; g2.fillText(`${r.name}`, 12, y0 + 16);
    g2.fillStyle = '#6f7888'; g2.font = '11px system-ui'; g2.fillText(`±${Math.round(r.s)} ${r.unit}`, 12, y0 + 30);
    for (let i = 0; i < 3; i++) {
      g2.strokeStyle = r.cols[i]; g2.lineWidth = 1.4; g2.beginPath();
      let pen = false;
      for (let x = 0; x <= plotW; x += 2) {
        const t = S.t - PAST + (x / plotW) * (PAST + AHEAD), v = sample(r.arr, t, i);
        if (v === null) { pen = false; continue; }
        const y = mid - Math.max(-1.1, Math.min(1.1, v / r.s)) * amp;
        if (pen) g2.lineTo(X0 + x, y); else { g2.moveTo(X0 + x, y); pen = true; }
      }
      g2.stroke();
      g2.fillStyle = r.cols[i];
      g2.fillText(`${r.names[i]} ${r.arr[3 * k + i].toFixed(r.unit === 'm/s²' ? 1 : 0)}`, 12 + i * 44, y0 + 46);
    }
  });
  const xp = xOf(S.t);
  g2.strokeStyle = '#e8e6df'; g2.lineWidth = 1; g2.beginPath(); g2.moveTo(xp, 4); g2.lineTo(xp, H - 4); g2.stroke();
}

// ---------- interfaz ----------
function ui() {
  for (const el of document.querySelectorAll('.aim-only')) el.style.display = S.src === 'apuntar' ? '' : 'none';
  document.querySelectorAll('[data-src]').forEach((b) => b.classList.toggle('on', b.dataset.src === S.src));
  document.querySelectorAll('[data-cam]').forEach((b) => b.classList.toggle('on', b.dataset.cam === S.cam));
  $('play').textContent = S.playing ? '⏸' : '▶';
  $('speed').textContent = '×' + S.speed;
  $('noise').classList.toggle('on', S.noise && S.src !== 'take');
  $('noise').style.opacity = S.src === 'take' ? 0.4 : 1;
  $('ghost').textContent = GHOST_NAME[S.src === 'take' && S.ghost === 'no' ? 'fusion' : S.ghost];
  $('hand').textContent = 'Reloj: muñeca ' + (S.side === 'l' ? 'izquierda' : 'derecha');
  if (S.src !== 'take') $('takes').value = '';
}
function setSrc(key) {
  S.src = key; S.take = null; S.t = 0;
  if (key === 'apuntar') {                 // por encima del hombro del brazo que apunta, mirando a la pantalla
    const s = S.side === 'l' ? -1 : 1;
    S.cam = 'orbita'; cam.position.set(1.1 * s, 1.85, 1.5); ctl.target.set(0, 1.25, -1.0); last.set(0, 1.16, 0);
  }
  prepare();
}
document.querySelectorAll('[data-src]').forEach((b) => b.addEventListener('click', () => setSrc(b.dataset.src)));
document.querySelectorAll('[data-cam]').forEach((b) => b.addEventListener('click', () => { S.cam = b.dataset.cam; ui(); }));
$('play').addEventListener('click', () => { S.playing = !S.playing; ui(); });
$('speed').addEventListener('click', () => { S.speed = SPEEDS[(SPEEDS.indexOf(S.speed) + 1) % SPEEDS.length]; ui(); });
$('time').addEventListener('input', (e) => { S.t = (+e.target.value / 1000) * S.dur; });
$('noise').addEventListener('click', () => { if (S.src === 'take') return; S.noise = !S.noise; prepare(); });
$('ghost').addEventListener('click', () => { S.ghost = GHOSTS[(GHOSTS.indexOf(S.ghost) + 1) % GHOSTS.length]; prepare(); });
$('hand').addEventListener('click', () => { S.side = S.side === 'l' ? 'r' : 'l'; prepare(); });
$('takes').addEventListener('change', async (e) => {
  const id = e.target.value;
  if (!id) return;
  try {
    const take = await (await fetch('/grabaciones/' + id + '.json')).json();
    S.take = take; S.src = 'take'; S.side = take.mano === 'r' ? 'r' : 'l'; S.t = 0;
    prepare();
  } catch { $('label').textContent = 'no pude abrir esa toma'; }
});
addEventListener('keydown', (e) => {
  if (e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); $('play').click(); }
  else if (['1', '2', '3'].includes(e.key)) setSrc(['caminar', 'tablet', 'apuntar'][+e.key - 1]);
  else if (e.key === 'f' || e.key === 'F') FILM.toggle();
  else if (e.key === 'Escape' && filming()) FILM.toggle();
  else if (e.key === 'm' || e.key === 'M') $('hand').click();
  else if (e.key === 'n' || e.key === 'N') $('noise').click();
  else if (e.key === 'g' || e.key === 'G') $('ghost').click();
  else if (e.key === 'c' || e.key === 'C') { const cs = ['orbita', 'frente', 'lado', 'muneca']; S.cam = cs[(cs.indexOf(S.cam) + 1) % cs.length]; ui(); }
});
fetch('/grabaciones/index.json').then((r) => (r.ok ? r.json() : Promise.reject())).then((list) => {
  const sel = $('takes'), groups = {};
  for (const t of list) (groups[t.sesion] = groups[t.sesion] || []).push(t);
  for (const [ses, items] of Object.entries(groups)) {
    const og = document.createElement('optgroup'); og.label = ses;
    for (const t of items) { const o = document.createElement('option'); o.value = t.id; o.textContent = `${t.nombre} · ${t.dur} s`; og.append(o); }
    sel.append(og);
  }
}).catch(() => { $('takes').options[0].textContent = 'Sin grabaciones (tools/export_mocap.py)'; });

// ---------- bucle ----------
let prevT = performance.now();
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.1, (now - prevT) / 1000); prevT = now;
  if (S.playing) S.t = (S.t + dt * S.speed) % S.dur;
  $('time').value = Math.round(S.t / S.dur * 1000);
  const st = scene3(dt);
  if (filming()) FILM.update(dt);
  R.render(scene, cam);
  if (!filming()) graphs();
  const name = S.src === 'take' ? `${S.take.nombre} (${S.take.sesion})` : ANIMS[S.src].name;
  $('hud').innerHTML = `<b>${name}</b> · ${S.t.toFixed(2)} / ${S.dur.toFixed(1)} s<br>`
    + (st.err !== null ? `antebrazo reconstruido: <b>${st.err.toFixed(1)}°</b> del real<br>` : S.src === 'take' ? 'antebrazo: <b>de tus datos</b><br>' : '')
    + (st.cursorErr !== null ? `cursor del reloj: <b>${st.cursorErr.toFixed(1)} cm</b> del rayo<br>` : '')
    + `giro <b>${Math.round(st.gm)}</b> °/s · empujón <b>${st.lm.toFixed(1)}</b> m/s²`;
  const marks = S.src === 'take' ? (S.take.etiquetas || []).map((e) => [e.desde, e.hasta, e.texto]) : (ANIMS[S.src].marks || []);
  const cur = marks.find(([a, b]) => S.t >= a && S.t <= b);
  $('label').textContent = cur ? cur[2] : '';
}
prepare();
requestAnimationFrame(frame);
