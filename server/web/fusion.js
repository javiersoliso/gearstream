// Capítulo 8 del curso: las figuras de fusion.html. La cuenta está en fusionmath.js (una dimensión) y en
// mocapmath.js (Mahony en 3D); aquí solo se dibuja y se conecta al reloj.
//   A: los dos testigos solos. B: el resorte (antebrazos de costado y el error contra b/k). C: el valle.
//   D: lo que la gravedad no ve. E: Mahony en el mocap. F: en vivo con tu reloj, y la prueba de la mesa.
'use strict';

const FM = FusionMath;
const $ = (id) => document.getElementById(id);
const C = { verdad: '#ece9e1', giro: '#9db4ff', acel: '#ffd166', fus: '#f0997b', rumbo: '#58c4dd', grid: '#232a38', axis: '#3a4458', dim: '#9aa3b2', ink: '#ece9e1' };
const XYZ = ['#a99bff', '#f28ab2', '#ff9a6b'];
const KPS = [0, 0.1, 0.3, 0.5, 1, 2, 5, 10];
const kDe = (v) => 0.01 * Math.pow(5000, v / 1000);          // el control (0..1000) → k de 0.01 a 50 por segundo
const vDe = (k) => 1000 * Math.log(k / 0.01) / Math.log(5000);
const fmtK = (k) => (k < 0.1 ? k.toFixed(3) : k < 10 ? k.toFixed(2) : k.toFixed(0));
const gr = (x, d = 1) => `${x.toFixed(d)}°`;

const S = {
  b: 0.5, sac: 1, k: 1, sim: null, valle: null, playB: true, tB: 0,
  kp: 2, anim: 'apuntar', imus: {},
  vivoD: false,
  // en vivo
  connected: false, watch: false, lastSample: 0, grav: null, acc: null, lastT: null, hand: loadHand(),
  fB: 0, buf: [], thG: null, thF: null, mesa: null,
};

// ---------- dibujo de gráficas ----------
function fit(cv, h) {
  const d = Math.min(window.devicePixelRatio || 1, 2), w = Math.max(280, cv.clientWidth || 600);
  if (cv.width !== Math.round(w * d) || cv.height !== Math.round(h * d)) { cv.width = Math.round(w * d); cv.height = Math.round(h * d); }
  cv.style.height = `${h}px`;
  const g = cv.getContext('2d');
  g.setTransform(d, 0, 0, d, 0, 0); g.clearRect(0, 0, w, h);
  return { g, W: w, H: h };
}
function niceStep(span, n) {
  const raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p;
}
// ejes: X {min, max, log, label}, Y {min, max, label}; devuelve las funciones de mundo → píxel
function axes(g, W, H, X, Y) {
  const L = 44, R = W - 10, T = 10, B = H - 26;
  const lx = (v) => (X.log ? Math.log10(v) : v);
  const x = (v) => L + (lx(v) - lx(X.min)) / (lx(X.max) - lx(X.min)) * (R - L);
  const y = (v) => B - (v - Y.min) / (Y.max - Y.min) * (B - T);
  g.font = '11px system-ui, sans-serif'; g.lineWidth = 1;
  const ys = niceStep(Y.max - Y.min, 5);
  for (let v = Math.ceil(Y.min / ys) * ys; v <= Y.max + 1e-9; v += ys) {
    g.strokeStyle = Math.abs(v) < 1e-9 ? C.axis : C.grid; g.beginPath(); g.moveTo(L, y(v)); g.lineTo(R, y(v)); g.stroke();
    g.fillStyle = C.dim; g.textAlign = 'right'; g.textBaseline = 'middle'; g.fillText(`${+v.toFixed(2)}`, L - 6, y(v));
  }
  const xt = [];
  if (X.log) for (let e = Math.ceil(Math.log10(X.min)); e <= Math.log10(X.max) + 1e-9; e++) xt.push(Math.pow(10, e));
  else { const xs = niceStep(X.max - X.min, 6); for (let v = Math.ceil(X.min / xs) * xs; v <= X.max + 1e-9; v += xs) xt.push(v); }
  g.textAlign = 'center'; g.textBaseline = 'top';
  for (const v of xt) {
    g.strokeStyle = C.grid; g.beginPath(); g.moveTo(x(v), T); g.lineTo(x(v), B); g.stroke();
    g.fillStyle = C.dim; g.fillText(`${+v.toFixed(2)}`, x(v), B + 5);
  }
  g.textAlign = 'right'; g.fillText(X.label || '', L - 6, B + 5);
  g.save(); g.translate(11, (T + B) / 2); g.rotate(-Math.PI / 2); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(Y.label || '', 0, 0); g.restore();
  return { x, y, L, R, T, B };
}
// una serie: n puntos, xAt(i), yAt(i); NaN corta la línea. Se dibuja ~2 puntos por píxel.
function line(g, m, n, xAt, yAt, color, lw, dash) {
  const step = Math.max(1, Math.floor(n / ((m.R - m.L) * 2)));
  g.save();
  g.beginPath(); g.rect(m.L, m.T - 1, m.R - m.L, m.B - m.T + 2); g.clip();
  g.strokeStyle = color; g.lineWidth = lw || 1.5; g.setLineDash(dash || []); g.lineJoin = 'round';
  g.beginPath();
  let pen = false;
  for (let i = 0; i < n; i += step) {
    const v = yAt(i);
    if (!Number.isFinite(v)) { pen = false; continue; }
    const px = m.x(xAt(i)), py = m.y(v);
    if (pen) g.lineTo(px, py); else { g.moveTo(px, py); pen = true; }
  }
  g.stroke(); g.restore();
}
function rango(arrs, minSpan, sym) {
  let lo = Infinity, hi = -Infinity;
  for (const a of arrs) for (let i = 0; i < a.length; i++) if (Number.isFinite(a[i])) { lo = Math.min(lo, a[i]); hi = Math.max(hi, a[i]); }
  if (!Number.isFinite(lo)) { lo = -1; hi = 1; }
  if (sym) { const m = Math.max(Math.abs(lo), Math.abs(hi), minSpan / 2); return { min: -m * 1.08, max: m * 1.08 }; }
  const c = (lo + hi) / 2, h = Math.max(hi - lo, minSpan) / 2 * 1.08;
  return { min: c - h, max: c + h };
}

// ---------- A: los dos testigos ----------
function rehacer() {
  S.sim = FM.inclinacion({ b: S.b, sacudidas: S.sac });
  S.giroSolo = FM.soloGiro(S.sim.giro, S.sim.hz, S.sim.verdad[0]);
  S.valle = FM.valle(S.sim, 48, 500);
  refiltrar();
}
function refiltrar() {
  S.fus = FM.complementario(S.sim.giro, S.sim.acel, S.sim.hz, S.k, S.sim.verdad[0]);
  S.errFus = S.fus.map((v, i) => v - S.sim.verdad[i]);
}
function dibujaA() {
  const s = S.sim, { g, W, H } = fit($('figA'), 260);
  const Y = rango([s.verdad, s.acel, S.giroSolo], 40);
  const m = axes(g, W, H, { min: 0, max: s.dur, label: 's' }, { ...Y, label: 'grados' });
  const t = (i) => i / s.hz;
  line(g, m, s.n, t, (i) => s.acel[i], C.acel, 1.2);
  line(g, m, s.n, t, (i) => S.giroSolo[i], C.giro, 2);
  line(g, m, s.n, t, (i) => s.verdad[i], C.verdad, 2);
  const eg = S.giroSolo[s.n - 1] - s.verdad[s.n - 1], ea = FM.errores(s.acel, s.verdad, 0);
  $('readA').innerHTML = `giroscopio solo: <b class="c-giro">${gr(eg)}</b> de error a los 60 s (b·t = ${gr(S.b * 60, 0)}) · acelerómetro solo: en promedio <b class="c-acel">${gr(ea.medio, 2)}</b>, pero salta hasta <b class="c-acel">${gr(ea.max, 0)}</b>`;
  $('bOut').textContent = `${S.b.toFixed(2)} °/s`; $('sacOut').textContent = `× ${S.sac.toFixed(2)}`;
}

// ---------- B: el resorte ----------
function resorte(g, P, Q, k) {
  const dx = Q[0] - P[0], dy = Q[1] - P[1], d = Math.hypot(dx, dy);
  if (d < 3) return;
  const ux = dx / d, uy = dy / d, nx = -uy, ny = ux, coils = 9, amp = 5;
  g.strokeStyle = C.fus; g.globalAlpha = 0.9; g.lineWidth = 0.8 + 2.4 * Math.max(0, Math.min(1, (Math.log10(k) + 2) / 3.7));
  g.beginPath(); g.moveTo(P[0], P[1]);
  for (let i = 1; i < coils * 2; i++) {
    const f = i / (coils * 2), s = i % 2 ? amp : -amp;
    g.lineTo(P[0] + ux * d * f + nx * s, P[1] + uy * d * f + ny * s);
  }
  g.lineTo(Q[0], Q[1]); g.stroke(); g.globalAlpha = 1;
}
function dibujaB1() {
  const s = S.sim, { g, W, H } = fit($('figB1'), 300);
  const i = Math.min(s.n - 1, Math.floor(S.tB * s.hz));
  const ox = Math.min(W * 0.14, 70), oy = H * 0.66, L = Math.min(W - ox - 60, (oy - 16) / Math.sin(62 * Math.PI / 180));
  const tip = (deg) => [ox + L * Math.cos(deg * Math.PI / 180), oy - L * Math.sin(deg * Math.PI / 180)];
  // escala: un arco con marcas cada 15°
  g.strokeStyle = C.grid; g.lineWidth = 1; g.font = '11px system-ui, sans-serif'; g.fillStyle = C.dim; g.textAlign = 'left'; g.textBaseline = 'middle';
  g.beginPath(); g.arc(ox, oy, L + 6, -60 * Math.PI / 180, 30 * Math.PI / 180); g.stroke();
  for (let a = -30; a <= 60; a += 15) {
    const p = tip(a), q = [ox + (L + 12) * Math.cos(a * Math.PI / 180), oy - (L + 12) * Math.sin(a * Math.PI / 180)];
    g.beginPath(); g.moveTo(p[0] + (q[0] - p[0]) * 0.5, p[1] + (q[1] - p[1]) * 0.5); g.lineTo(q[0], q[1]); g.stroke();
    g.fillText(`${a}°`, q[0] + 4, q[1]);
  }
  const brazo = (deg, col, lw, alpha) => {
    const p = tip(Math.max(-35, Math.min(65, deg))); g.globalAlpha = alpha || 1; g.strokeStyle = col; g.lineWidth = lw; g.lineCap = 'round';
    g.beginPath(); g.moveTo(ox, oy); g.lineTo(p[0], p[1]); g.stroke();
    g.fillStyle = col; g.beginPath(); g.arc(p[0], p[1], lw + 1.5, 0, 2 * Math.PI); g.fill(); g.globalAlpha = 1;
    return p;
  };
  brazo(S.giroSolo[i], C.giro, 2, 0.55);
  brazo(s.verdad[i], C.verdad, 6, 0.35);
  const pa = brazo(s.acel[i], C.acel, 2);
  const pf = brazo(S.fus[i], C.fus, 3);
  resorte(g, pf, pa, S.k);
  g.fillStyle = C.ink; g.beginPath(); g.arc(ox, oy, 5, 0, 2 * Math.PI); g.fill();
  g.fillStyle = C.dim; g.textAlign = 'left'; g.textBaseline = 'top'; g.font = '12px system-ui, sans-serif';
  g.fillText(`t = ${(i / s.hz).toFixed(1)} s · codo`, 8, H - 18);
}
function dibujaB2() {
  const s = S.sim, { g, W, H } = fit($('figB2'), 170);
  const bk = S.b / S.k, Y = rango([S.errFus, [bk, -bk, 2]], 2, true);
  const m = axes(g, W, H, { min: 0, max: s.dur, label: 's' }, { ...Y, label: 'error (°)' });
  line(g, m, 2, (i) => i * s.dur, () => bk, C.ink, 1, [5, 5]);
  line(g, m, s.n, (i) => i / s.hz, (i) => S.errFus[i], C.fus, 1.5);
  g.strokeStyle = '#ece9e155'; g.lineWidth = 1; g.beginPath(); g.moveTo(m.x(S.tB), m.T); g.lineTo(m.x(S.tB), m.B); g.stroke();
}
function leeB() {
  const e = FM.errores(S.fus, S.sim.verdad, 2000);
  $('kOut').textContent = `${fmtK(S.k)} /s`;
  $('readB').innerHTML = `después de los 20 s el error promedio es <b class="c-fus">${gr(e.medio, 2)}</b> y b/k = <b>${gr(S.b / S.k, 2)}</b> · error típico (rms) <b class="c-fus">${gr(e.rms, 2)}</b>, el más grande <b>${gr(e.max, 1)}</b>`;
  $('fKOut').textContent = `${fmtK(S.k)} /s`;
}

// ---------- C: el valle ----------
function dibujaC() {
  const v = S.valle, { g, W, H } = fit($('figC'), 230);
  const top = Math.max(...v.map((p) => p.rms)) * 1.1;
  const m = axes(g, W, H, { min: 0.01, max: 50, log: true, label: 'k (1/s)' }, { min: 0, max: top, label: 'error rms (°)' });
  if (S.b > 0) line(g, m, 200, (i) => 0.01 * Math.pow(5000, i / 199), (i) => S.b / (0.01 * Math.pow(5000, i / 199)), C.ink, 1, [5, 5]);
  line(g, m, v.length, (i) => v[i].k, (i) => v[i].rms, C.fus, 2.5);
  const mine = FM.errores(S.fus, S.sim.verdad, 500).rms, best = v.reduce((a, b) => (b.rms < a.rms ? b : a));
  g.fillStyle = C.ink; g.beginPath(); g.arc(m.x(best.k), m.y(best.rms), 3, 0, 2 * Math.PI); g.fill();
  g.fillStyle = C.fus; g.strokeStyle = C.bg || '#10131a'; g.lineWidth = 2;
  g.beginPath(); g.arc(m.x(S.k), m.y(Math.min(mine, top)), 7, 0, 2 * Math.PI); g.fill(); g.stroke();
  g.font = '12px system-ui, sans-serif'; g.fillStyle = C.dim; g.textBaseline = 'top';
  g.textAlign = 'left'; g.fillText('manda el sesgo', m.L + 8, m.T + 4);
  g.textAlign = 'right'; g.fillText('mandan las sacudidas', m.R - 6, m.T + 4);
  $('readC').innerHTML = `el fondo, para esta muñeca: k = <b>${fmtK(best.k)} /s</b>, con <b>${gr(best.rms, 2)}</b> · el tuyo: k = <b class="c-fus">${fmtK(S.k)} /s</b>, con <b class="c-fus">${gr(mine, 2)}</b>`;
}

// ---------- D: lo que la gravedad no ve ----------
function dibujaD() {
  const narrow = $('figD').clientWidth < 520, { g, W, H } = fit($('figD'), narrow ? 520 : 320);
  const incl = +$('dIncl').value, torn = +$('dTorn').value, rumbo = +$('dRumbo').value;
  $('dInclOut').textContent = `${incl}°`; $('dTornOut').textContent = `${torn}°`; $('dRumboOut').textContent = `${rumbo}°`;
  // angosto (teléfono): el reloj arriba y las cifras debajo
  const IW = narrow ? W : Math.min(230, W * 0.42), cx = narrow ? W / 2 : (W - IW) / 2, cy = narrow ? 150 : H * 0.5;
  const sc = narrow ? Math.min(W * 0.4, 140) : Math.min(cx * 0.95, H * 0.44), top = narrow ? 290 : 0;
  const az = -32 * Math.PI / 180, el = 26 * Math.PI / 180;
  const P = (p) => {
    const x1 = p[0] * Math.cos(az) + p[2] * Math.sin(az), z1 = -p[0] * Math.sin(az) + p[2] * Math.cos(az);
    return [cx + sc * x1, cy - sc * (p[1] * Math.cos(el) - z1 * Math.sin(el)), p[1] * Math.sin(el) + z1 * Math.cos(el)];
  };
  const add = (a, b, s) => [a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s];
  const seg = (a, b, col, lw, alpha) => { const p = P(a), q = P(b); g.globalAlpha = alpha || 1; g.strokeStyle = col; g.lineWidth = lw; g.lineCap = 'round'; g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(q[0], q[1]); g.stroke(); g.globalAlpha = 1; };
  const flecha = (a, b, col, lw) => {
    seg(a, b, col, lw); const p = P(a), q = P(b), ang = Math.atan2(q[1] - p[1], q[0] - p[0]);
    g.fillStyle = col; g.beginPath(); g.moveTo(q[0], q[1]);
    g.lineTo(q[0] - 10 * Math.cos(ang - 0.4), q[1] - 10 * Math.sin(ang - 0.4)); g.lineTo(q[0] - 10 * Math.cos(ang + 0.4), q[1] - 10 * Math.sin(ang + 0.4)); g.fill();
  };
  // el piso, con una rosa de rumbos
  const y0 = -0.6;
  g.strokeStyle = C.grid; g.lineWidth = 1; g.beginPath();
  for (let a = 0; a <= 360; a += 6) { const p = P([Math.cos(a * Math.PI / 180) * 1.15, y0, Math.sin(a * Math.PI / 180) * 1.15]); a ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]); }
  g.stroke();
  for (let a = 0; a < 360; a += 30) seg([Math.cos(a * Math.PI / 180) * 1.05, y0, Math.sin(a * Math.PI / 180) * 1.05], [Math.cos(a * Math.PI / 180) * 1.15, y0, Math.sin(a * Math.PI / 180) * 1.15], C.axis, 1);
  const [X, Y, Z] = FM.orientacion(incl, rumbo, torn);
  // la sombra del antebrazo en el piso: eso es el rumbo
  seg([-0.95 * X[0], y0, -0.95 * X[2]], [0.4 * X[0], y0, 0.4 * X[2]], '#2a3242', 8);
  flecha([0.75, y0, -0.75], [0.75, y0 + 1.25, -0.75], C.acel, 2.5);
  const lab = P([0.75, y0 + 1.3, -0.75]); g.fillStyle = C.acel; g.font = '12px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText('arriba', lab[0], lab[1] - 6);
  // antebrazo, mano y reloj
  seg(add([0, 0, 0], X, -0.95), add([0, 0, 0], X, 0.36), '#4a5368', 13);
  const hp = P(add([0, 0, 0], X, 0.44)); g.fillStyle = '#4a5368'; g.beginPath(); g.arc(hp[0], hp[1], 9, 0, 2 * Math.PI); g.fill();
  const c0 = add([0, 0, 0], Z, 0.08), hx = 0.2, hy = 0.18, hz = 0.05;
  const corner = (sx, sy, sz) => add(add(add(c0, X, sx * hx), Y, sy * hy), Z, sz * hz);
  const faces = [
    { n: Z, v: [[-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], col: '#1d9e75' },
    { n: Z.map((v) => -v), v: [[-1, -1, -1], [-1, 1, -1], [1, 1, -1], [1, -1, -1]], col: '#2b303a' },
    { n: X, v: [[1, -1, -1], [1, 1, -1], [1, 1, 1], [1, -1, 1]], col: '#3a3f4a' },
    { n: X.map((v) => -v), v: [[-1, -1, -1], [-1, -1, 1], [-1, 1, 1], [-1, 1, -1]], col: '#3a3f4a' },
    { n: Y, v: [[-1, 1, -1], [-1, 1, 1], [1, 1, 1], [1, 1, -1]], col: '#444a56' },
    { n: Y.map((v) => -v), v: [[-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1]], col: '#444a56' },
  ].map((f) => { const pts = f.v.map((c) => P(corner(...c))); return { ...f, pts, z: pts.reduce((s, p) => s + p[2], 0) / 4 }; })
    .sort((a, b) => a.z - b.z);
  for (const f of faces) {
    g.fillStyle = f.col; g.strokeStyle = '#10131a'; g.lineWidth = 1;
    g.beginPath(); f.pts.forEach((p, j) => (j ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.closePath(); g.fill(); g.stroke();
  }
  [X, Y, Z].forEach((ax, j) => {
    flecha(c0, add(c0, ax, 0.42), XYZ[j], 2);
    const p = P(add(c0, ax, 0.5)); g.fillStyle = XYZ[j]; g.font = '12px system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('xyz'[j], p[0], p[1]);
  });
  // lo que lee el reloj
  let gv = FM.gravedadLeida(incl, rumbo, torn), vivo = false;
  if (S.vivoD && S.grav && performance.now() - S.lastSample < 1500) { gv = S.grav; vivo = true; }
  const x0 = narrow ? 8 : W - IW + 8, bw = IW - 76;
  g.textAlign = 'left'; g.textBaseline = 'alphabetic'; g.fillStyle = C.ink; g.font = '13px system-ui, sans-serif';
  g.fillText(vivo ? 'tu reloj lee (m/s²), en vivo' : 'el reloj lee (m/s²)', x0, top + 34);
  for (let j = 0; j < 3; j++) {
    const yb = top + 70 + j * 48, mid = x0 + 14 + bw / 2, val = gv[j], w = Math.max(-1, Math.min(1, val / 9.81)) * bw / 2;
    g.fillStyle = XYZ[j]; g.font = '14px system-ui, sans-serif'; g.fillText('xyz'[j], x0, yb + 5);
    g.fillStyle = '#10131a'; g.fillRect(x0 + 14, yb - 9, bw, 18);
    g.fillStyle = XYZ[j]; g.fillRect(Math.min(mid, mid + w), yb - 9, Math.abs(w), 18);
    g.fillStyle = C.axis; g.fillRect(mid - 0.5, yb - 13, 1, 26);
    g.fillStyle = C.ink; g.font = '13px ui-monospace, Consolas, monospace'; g.textAlign = 'right';
    g.fillText(val.toFixed(2).padStart(6), W - 4, yb + 5); g.textAlign = 'left';
  }
  g.fillStyle = C.dim; g.font = '12px system-ui, sans-serif';
  if (!vivo) g.fillText(rumbo === 0 ? 'mueve el rumbo: no cambia nada' : 'el rumbo no cambió nada', x0, top + 70 + 3 * 48);
  else g.fillText('gíralo plano, como una perilla', x0, top + 70 + 3 * 48);
}

// ---------- E: Mahony en el mocap ----------
function imuDe(anim) {
  if (!S.imus[anim]) S.imus[anim] = synth(anim, 'l', { noise: true, loops: Math.max(1, Math.round(60 / ANIMS[anim].dur)) });
  return S.imus[anim];
}
function dibujaE() {
  const imu = imuDe(S.anim), v3 = (a) => [a[0], a[1], a[2]];
  const X0 = v3(imu.truth.X), Z0 = v3(imu.truth.Z), frame0 = [X0, vec.cross(Z0, X0), Z0];
  const rec = reconstruct(imu, 'l', { kp: S.kp, frame0, psi0: headingOf(v3(imu.truth.F)) });
  const e = FM.erroresAntebrazo(imu.truth.F, rec.F), pred = FM.derivaPredicha(imu), n = imu.n;
  const { g, W, H } = fit($('figE'), 250);
  const Y = rango([e.incl, e.rumbo, pred], 10, true);
  const m = axes(g, W, H, { min: 0, max: imu.dur, label: 's' }, { ...Y, label: 'error (°)' });
  const t = (i) => i / imu.hz;
  line(g, m, n, t, (i) => pred[i], C.ink, 1.2, [5, 5]);
  line(g, m, n, t, (i) => e.rumbo[i], C.rumbo, 2);
  line(g, m, n, t, (i) => e.incl[i], C.fus, 2);
  let si = 0, c = 0, last = NaN;
  for (let i = n - imu.hz; i < n; i++) { si += Math.abs(e.incl[i]); c++; }
  for (let i = n - 1; i >= 0; i--) if (!Number.isNaN(e.rumbo[i])) { last = e.rumbo[i]; break; }
  $('kpOut').textContent = `${S.kp}`;
  $('readE').innerHTML = `en el último segundo: inclinación <b class="c-fus">${gr(si / c, 2)}</b> de error · rumbo <b class="c-rumbo">${gr(last)}</b> · lo que gira el sesgo alrededor de la vertical, ∫ b·ĝ dt = <b>${gr(pred[n - 1])}</b>`;
}

// ---------- F: en vivo ----------
const forearm = () => forearmOf(S.hand);
function onGyro(t, v) {
  if (!S.grav || !S.acc) return;
  if (S.lastT === null) { S.lastT = t; return; }
  let dt = (t - S.lastT) / 1000; S.lastT = t;
  if (!(dt > 0) || dt > 0.1) dt = 0.01;
  const w = [v.x, v.y, v.z], f = forearm();
  const rate = FM.subida(w, S.grav, f) + S.fB;
  const ref = FM.elevacion(f, S.grav), med = FM.elevacion(f, S.acc);
  if (S.thG === null) { S.thG = ref; S.thF = ref; }
  S.thG += rate * dt;
  S.thF = FM.paso(S.thF, rate, med, dt, S.k);
  const now = performance.now() / 1000;
  S.buf.push([now, ref, med, S.thG, S.thF]);
  while (S.buf.length && S.buf[0][0] < now - 20) S.buf.shift();
  if (S.mesa && S.mesa.fase !== 'listo') mesaPaso(dt, FM.giroVertical(w, S.grav) + S.fB);
}
function recentrar() { S.thG = null; S.thF = null; }
function dibujaF() {
  const { g, W, H } = fit($('figF'), 250);
  const vivo = S.watch && performance.now() - S.lastSample < 1500 && S.buf.length > 2;
  if (!vivo) {
    const m = axes(g, W, H, { min: -20, max: 0, label: 's' }, { min: -45, max: 45, label: 'grados' });
    g.fillStyle = C.dim; g.font = '14px system-ui, sans-serif'; g.textAlign = 'center';
    g.fillText(!S.connected ? 'sin servidor: abre esta página desde GearStream' : !S.watch ? 'el servidor está, el reloj no: conéctalo' : 'el reloj no manda datos: toca su pantalla', (m.L + m.R) / 2, (m.T + m.B) / 2);
    $('readF').textContent = '';
    return;
  }
  const b = S.buf, now = performance.now() / 1000;
  const Y = rango([b.map((r) => r[1]), b.map((r) => r[2]), b.map((r) => r[3]), b.map((r) => r[4])].map((a) => a.map((v) => Math.max(-95, Math.min(95, v)))), 30);
  const m = axes(g, W, H, { min: -20, max: 0, label: 's' }, { ...Y, label: 'grados' });
  const t = (i) => b[i][0] - now;
  line(g, m, b.length, t, (i) => b[i][2], C.acel, 1.2);
  line(g, m, b.length, t, (i) => b[i][3], C.giro, 2);
  line(g, m, b.length, t, (i) => b[i][1], C.verdad, 2);
  line(g, m, b.length, t, (i) => b[i][4], C.fus, 2);
  const r = b[b.length - 1];
  $('readF').innerHTML = `ahora: gravedad del reloj <b>${gr(r[1])}</b> · acelerómetro <b class="c-acel">${gr(r[2])}</b> · giroscopio sumado <b class="c-giro">${gr(r[3])}</b> · tu filtro <b class="c-fus">${gr(r[4])}</b>`;
}
// la prueba de la mesa: 10 s para medir el sesgo vertical, 50 s para ver cuánto se va el rumbo
function mesaEmpezar() { S.mesa = { fase: 'sesgo', t: 0, suma: 0, rumbo: 0, bv: 0, f0: null }; $('mesa').disabled = true; }
function mesaPaso(dt, wv) {
  const M = S.mesa;
  M.t += dt;
  if (M.fase === 'sesgo') {
    M.suma += wv * dt;
    if (M.t >= 10) { M.bv = M.suma / M.t; M.fase = 'deriva'; M.t = 0; M.f0 = S.thF; }
  } else if (M.fase === 'deriva') {
    M.rumbo += wv * dt;
    if (M.t >= 50) { M.fase = 'listo'; M.f1 = S.thF; $('mesa').disabled = false; $('mesa').textContent = 'otra vez'; }
  }
}
function leeMesa() {
  const M = S.mesa, o = $('mesaOut');
  if (!M) { o.textContent = ''; return; }
  if (M.fase === 'sesgo') o.textContent = `midiendo el sesgo… ${Math.max(0, 10 - M.t).toFixed(0)} s`;
  else if (M.fase === 'deriva') o.innerHTML = `sesgo vertical <b>${M.bv.toFixed(3)} °/s</b> · el rumbo ya se fue <b>${gr(M.rumbo, 2)}</b>… faltan ${Math.max(0, 50 - M.t).toFixed(0)} s`;
  else o.innerHTML = `sesgo vertical <b>${M.bv.toFixed(3)} °/s</b> · predicho: ${M.bv.toFixed(3)} × 50 s = <b>${gr(M.bv * 50, 2)}</b> · medido: <b>${gr(M.rumbo, 2)}</b> · tu filtro se inclinó <b class="c-fus">${gr(M.f1 - M.f0, 2)}</b>`;
}

// ---------- el reloj ----------
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
        if (typeof v.x !== 'number' || typeof v.y !== 'number' || typeof v.z !== 'number') continue;
        S.lastSample = performance.now(); S.watch = true;
        if (name === 'GRAVITY') S.grav = [v.x, v.y, v.z];
        else if (name === 'ACCELERATION') S.acc = [v.x, v.y, v.z];
        else if (name === 'GYROSCOPE') onGyro(t, v);
      }
    }
  };
}
if (location.protocol.startsWith('http')) connect();
function leeEstado() {
  const stale = performance.now() - S.lastSample > 1500;
  $('estado').textContent = !S.connected ? 'sin servidor' : !S.watch ? 'reloj no conectado' : stale ? 'reloj sin datos' : 'reloj en vivo';
}

// ---------- el código, leído de los archivos de verdad ----------
async function codigo() {
  try {
    const fm = await (await fetch('fusionmath.js')).text();
    const p = fm.match(/ {2}function paso\([\s\S]*?\n {2}\}/);
    $('codPaso').textContent = p ? p[0].replace(/^ {2}/gm, '') : 'no encontré paso() en fusionmath.js';
    const mm = await (await fetch('mocapmath.js')).text();
    const a = mm.indexOf("if (method === 'fusion') {"), b = mm.indexOf('} else {', a);
    $('codMahony').textContent = a >= 0 && b > a ? mm.slice(mm.lastIndexOf('\n', a) + 1, b + 1).replace(/^ {6}/gm, '') : 'no encontré la rama de fusión en mocapmath.js';
  } catch {
    $('codPaso').textContent = $('codMahony').textContent = 'abre esta página desde el servidor de GearStream para ver el código';
  }
}

// ---------- controles ----------
function todo() { dibujaA(); dibujaB1(); dibujaB2(); leeB(); dibujaC(); dibujaD(); dibujaE(); dibujaF(); }
$('b').addEventListener('input', (e) => { S.b = +e.target.value; rehacer(); dibujaA(); dibujaB2(); leeB(); dibujaC(); });
$('sac').addEventListener('input', (e) => { S.sac = +e.target.value; rehacer(); dibujaA(); dibujaB2(); leeB(); dibujaC(); });
$('k').value = Math.round(vDe(S.k));
$('k').addEventListener('input', (e) => { S.k = kDe(+e.target.value); refiltrar(); dibujaB2(); leeB(); dibujaC(); if (!S.playB) dibujaB1(); });
$('playB').addEventListener('click', () => { S.playB = !S.playB; $('playB').setAttribute('aria-pressed', S.playB); $('playB').textContent = S.playB ? 'pausa' : 'seguir'; });
$('figB2').addEventListener('pointerdown', (e) => {
  const r = e.target.getBoundingClientRect(), x = (e.clientX - r.left) / r.width;
  S.tB = Math.max(0, Math.min(S.sim.dur, (x * r.width - 44) / (r.width - 54) * S.sim.dur)); dibujaB1(); dibujaB2();
});
for (const id of ['dIncl', 'dTorn', 'dRumbo']) $(id).addEventListener('input', dibujaD);
$('dVivo').addEventListener('click', () => { S.vivoD = !S.vivoD; $('dVivo').setAttribute('aria-pressed', S.vivoD); dibujaD(); });
$('kp').value = KPS.indexOf(S.kp);
$('kp').addEventListener('input', (e) => { S.kp = KPS[+e.target.value]; dibujaE(); });
$('anim').addEventListener('change', (e) => { S.anim = e.target.value; dibujaE(); });
$('fB').addEventListener('input', (e) => { S.fB = +e.target.value; $('fBOut').textContent = `${S.fB.toFixed(2)} °/s`; });
$('fBOut').textContent = '0.00 °/s';
const manoTxt = () => { $('fHand').textContent = handName(S.hand); };
$('fHand').addEventListener('click', () => { S.hand = S.hand === 'right' ? 'left' : 'right'; saveHand(S.hand); manoTxt(); recentrar(); });
manoTxt();
$('fRe').addEventListener('click', recentrar);
$('mesa').addEventListener('click', mesaEmpezar);

// solo se anima lo que se ve
const visible = {};
const io = new IntersectionObserver((es) => { for (const e of es) visible[e.target.id] = e.isIntersecting; });
for (const id of ['figB1', 'figD', 'figF']) io.observe($(id));
let lastNow = performance.now();
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.1, (now - lastNow) / 1000); lastNow = now;
  if (S.playB) S.tB = (S.tB + dt * 1.5) % S.sim.dur;
  if (visible.figB1 && S.playB) { dibujaB1(); dibujaB2(); }
  if (visible.figD && S.vivoD) dibujaD();
  if (visible.figF) dibujaF();
  leeMesa();
}
let pend = 0;
new ResizeObserver(() => { cancelAnimationFrame(pend); pend = requestAnimationFrame(todo); }).observe(document.querySelector('main'));
setInterval(leeEstado, 500);
rehacer(); todo(); codigo(); leeEstado();
requestAnimationFrame(frame);
