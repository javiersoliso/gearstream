'use strict';

// Calibración del ratón aéreo. The page talks to the control channel that tools/air_mouse.py hosts
// (ws://127.0.0.1:8766): it shows the live state, changes the tunables on the fly and runs tests that
// use the real Windows cursor driven by the watch, so what gets measured is what the user gets.
// Without the air mouse the page still works for self-testing with the physical mouse.

// ---------- Protocol / constants ----------

const CONTROL_URL = new URLSearchParams(location.search).get('control') || 'ws://127.0.0.1:8766';
const METER_SCALE = 200;      // °/s at the ends of the bipolar meters
const LOG_MAX = 30;
const MATCH_MS = 500;         // page click <-> air-mouse click pairing window
const CLASSIFY_MS = 600;      // after this an unpaired click is a false/lost one
const BEZEL_WHEEL_MS = 300;   // wheel events this soon after a detent belong to it
const PATH_CAP = 20000;

const CLICK_MODES = [['auto', 'auto'], ['button', 'botón atrás'], ['tap', 'toque en la esfera'], ['dwell', 'reposo'],
                     ['tap+dwell', 'toque + reposo'], ['none', 'ninguno']];
const SCROLL_MODES = [['auto', 'auto'], ['bezel', 'bisel'], ['roll', 'rodar el antebrazo'], ['none', 'ninguno']];
const HOME_KEYS = [['none', 'nada'], ['right', 'botón derecho'], ['middle', 'botón central']];
const MODE_NAMES = { auto: 'auto', button: 'botón', tap: 'toque', dwell: 'reposo', 'tap+dwell': 'toque + reposo',
                     none: 'ninguno', bezel: 'bisel', roll: 'rodar el antebrazo' };

// Ranges mirror TUNABLES in air_mouse.py; `def` lets the page render something before the first `params`.
const CONTROLS = [
  { group: 'Sensibilidad', name: 'gain', label: 'Ganancia', type: 'range', min: 0.1, max: 5, step: 0.05, def: 1.0 },
  { group: 'Sensibilidad', name: 'gain_x', label: 'Ganancia horizontal', type: 'range', min: 0.2, max: 3, step: 0.05, def: 1.0 },
  { group: 'Sensibilidad', name: 'gain_y', label: 'Ganancia vertical', type: 'range', min: 0.2, max: 3, step: 0.05, def: 1.0 },
  { group: 'Sensibilidad', name: 'accel', label: 'Aceleración', type: 'check', def: true },
  { group: 'Sensibilidad', name: 'g_lo', label: 'px/° lento', type: 'range', min: 1, max: 60, step: 1, def: 12 },
  { group: 'Sensibilidad', name: 'g_hi', label: 'px/° rápido', type: 'range', min: 1, max: 120, step: 1, def: 30 },
  { group: 'Sensibilidad', name: 'v_lo', label: '°/s inicio aceleración', type: 'range', min: 0, max: 200, step: 1, def: 10 },
  { group: 'Sensibilidad', name: 'v_hi', label: '°/s fin aceleración', type: 'range', min: 0, max: 400, step: 5, def: 120 },
  { group: 'Sensibilidad', name: 'max_speed', label: 'Velocidad máx px/s', type: 'range', min: 500, max: 10000, step: 100, def: 4000 },
  { group: 'Zona muerta y suavizado', name: 'deadzone', label: 'Zona muerta °/s', type: 'range', min: 0, max: 5, step: 0.1, def: 0.8 },
  { group: 'Zona muerta y suavizado', name: 'mincutoff', label: 'Suavizado (mincutoff Hz, menos = más suave)', type: 'range', min: 0, max: 10, step: 0.1, def: 2.0 },
  { group: 'Zona muerta y suavizado', name: 'beta', label: 'Beta (menos retraso al ir rápido)', type: 'range', min: 0, max: 0.5, step: 0.005, def: 0.01 },
  { group: 'Zona muerta y suavizado', name: 'dcutoff', label: 'dcutoff Hz', type: 'range', min: 0.1, max: 10, step: 0.1, def: 1.0 },
  { group: 'Zona muerta y suavizado', name: 'calib_p2p', label: 'Reposo máx. para calibrar °/s', type: 'range', min: 0.5, max: 6, step: 0.1, def: 2.5 },
  { group: 'Clic', name: 'click', label: 'Clic', type: 'select', options: CLICK_MODES, def: 'auto' },
  { group: 'Clic', name: 'home_key', label: 'Tecla inicio', type: 'select', options: HOME_KEYS, def: 'none' },
  { group: 'Clic', name: 'tap_thr', label: 'Toque: umbral m/s²', type: 'range', min: 0.5, max: 15, step: 0.1, def: 2.5 },
  { group: 'Clic', name: 'tap_width', label: 'Toque: anchura máx (muestras)', type: 'range', min: 1, max: 20, step: 1, def: 6 },
  { group: 'Clic', name: 'tap_pre', label: 'Toque: giro máx antes °/s', type: 'range', min: 1, max: 90, step: 1, def: 15 },
  { group: 'Clic', name: 'tap_post', label: 'Toque: giro máx después °/s', type: 'range', min: 1, max: 90, step: 1, def: 20 },
  { group: 'Clic', name: 'tap_post_ms', label: 'Toque: ventana después ms', type: 'range', min: 80, max: 600, step: 10, def: 250 },
  { group: 'Clic', name: 'dwell_time', label: 'Reposo: segundos', type: 'range', min: 0.3, max: 3, step: 0.1, def: 0.7 },
  { group: 'Clic', name: 'dwell_speed', label: 'Reposo: velocidad máx °/s', type: 'range', min: 0.2, max: 10, step: 0.1, def: 1.5 },
  { group: 'Scroll', name: 'scroll', label: 'Scroll', type: 'select', options: SCROLL_MODES, def: 'auto' },
  { group: 'Scroll', name: 'scroll_enter', label: 'Rodar: entra a ° de giro', type: 'range', min: 10, max: 80, step: 1, def: 25 },
  { group: 'Scroll', name: 'scroll_exit', label: 'Rodar: sale por debajo de °', type: 'range', min: 5, max: 60, step: 1, def: 15 },
  { group: 'Scroll', name: 'scroll_deg_per_notch', label: 'Rodar: ° por muesca', type: 'range', min: 2, max: 20, step: 0.5, def: 6 },
  { group: 'Bisel', name: 'bezel_invert', label: 'Invertir sentido', type: 'check', def: false },
  { group: 'Bisel', name: 'bezel_notches', label: 'Muescas por detent', type: 'range', min: 1, max: 10, step: 1, def: 1 },
  { group: 'Seguridad', name: 'yield', label: 'Ceder al ratón físico', type: 'check', def: true },
];
const CONTROL_BY_NAME = new Map(CONTROLS.map((c) => [c.name, c]));

// ---------- Helpers (same as app.js) ----------

const $ = (sel, el = document) => el.querySelector(sel);

function fmt(v) {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return '—';
    if (Number.isInteger(v)) return String(v);
    const a = Math.abs(v);
    return v.toFixed(a >= 1000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : 3);
  }
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

let palette = {};
function readPalette() {
  const cs = getComputedStyle(document.documentElement);
  palette = { surface: cs.getPropertyValue('--surface-1').trim(), grid: cs.getPropertyValue('--grid').trim(),
              axis: cs.getPropertyValue('--axis').trim(), muted: cs.getPropertyValue('--muted').trim() };
  for (let i = 1; i <= 8; i++) palette[i] = cs.getPropertyValue(`--series-${i}`).trim();
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const round2 = (v) => Math.round(v * 100) / 100;
const signed = (v) => (typeof v === 'number' ? (v > 0 ? `+${v}` : v < 0 ? `−${-v}` : '0') : '?');
const sum = (a) => a.reduce((s, v) => s + v, 0);
const mean = (a) => (a.length ? sum(a) / a.length : 0);
function median(a) {
  const s = a.filter(Number.isFinite).sort((x, y) => x - y);
  if (!s.length) return 0;
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
const pad = (n, w) => String(n).padStart(w, '0');
function hhmmss(t) {
  const d = new Date(t);
  return `${pad(d.getHours(), 2)}:${pad(d.getMinutes(), 2)}:${pad(d.getSeconds(), 2)}.${pad(d.getMilliseconds(), 3)}`;
}
const hhmm = (t) => { const d = new Date(t); return `${pad(d.getHours(), 2)}:${pad(d.getMinutes(), 2)}`; };
// Event.timeStamp shares performance.timeOrigin, so this is comparable with the air mouse's wall-clock `t`.
const wallOf = () => Date.now();   // same wall clock as the air mouse's time.time(); handlers run promptly

// ---------- State ----------

let ws = null;
let connected = false;
let params = null;        // last `params` from the air mouse (null until connected)
let defaults = null;
let efectivo = null;
let profile = '';
let latest = null;        // last `state`
let latestAt = 0;         // performance.now() when it arrived
let stateCount = 0, stateHz = 0;
const log = [];           // newest first, max LOG_MAX
let logDirty = false;
let metersDirty = false;

const current = () => params || Object.fromEntries(CONTROLS.map((c) => [c.name, c.def]));

// ---------- Connection ----------

function connect() {
  let sock;
  try { sock = new WebSocket(CONTROL_URL); } catch (e) { setTimeout(connect, 1000); return; }
  ws = sock;
  sock.onopen = () => {
    connected = true;
    send({ type: 'cmd', name: 'list_gestures' });
  };
  sock.onclose = () => {
    if (ws !== sock) return;
    ws = null;
    connected = false;
    latest = null;
    params = null;
    metersDirty = true;
    renderControls(false);  // greys the groups until the next `params`
    setTimeout(connect, 1000);
  };
  sock.onerror = () => {};  // onclose follows
  sock.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch (err) { return; }
    if (msg && typeof msg === 'object') handle(msg);
  };
}

function send(obj) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return false;
  ws.send(JSON.stringify(obj));
  return true;
}

function cmd(name, extra) { return send({ type: 'cmd', name, ...(extra || {}) }); }
function setParams(p) { return send({ type: 'set', params: p }); }

function handle(msg) {
  switch (msg.type) {
    case 'params':
      params = msg.params || {};
      if (msg.defaults) defaults = msg.defaults;
      if (msg.efectivo) efectivo = msg.efectivo;
      if (typeof msg.profile === 'string') profile = msg.profile;
      renderControls(false);
      break;
    case 'state':
      latest = msg;
      latestAt = performance.now();
      stateCount++;
      if (msg.efectivo) efectivo = msg.efectivo;
      metersDirty = true;
      break;
    case 'event':
      addLog(msg);
      onEvent(msg);
      break;
    case 'ack':
      onAck(msg);
      break;
    case 'error':
      if (msg.name === 'record_gesture' || msg.name === 'list_gestures') { showMsg($('#gestoMsg'), msg.detail || 'error', 'critical'); break; }
      showMsg($('#ajustesMsg'), msg.detail || 'error', 'critical');
      if (msg.name === 'set') renderControls(true);
      break;
    case 'gestures':
      renderGestures(msg);
      break;
  }
}

// ---------- Messages / toasts ----------

const msgTimers = new WeakMap();
function showMsg(el, text, cls, ms = 5000) {
  el.textContent = text;
  el.className = 'msg' + (cls ? ` ${cls}` : '');
  clearTimeout(msgTimers.get(el));
  msgTimers.set(el, setTimeout(() => { el.textContent = ''; el.className = 'msg'; }, ms));
}

function onAck(msg) {
  const detail = msg.detail ? `: ${msg.detail}` : '';
  switch (msg.name) {
    case 'record_gesture':
      showMsg($('#gestoMsg'), `gesto guardado${detail}`, 'good');
      cmd('list_gestures');
      break;
    case 'list_gestures':
      break;
    default:
      showMsg($('#ajustesMsg'), `${ACK_NAMES[msg.name] || msg.name}${detail}`, 'good');
  }
}
const ACK_NAMES = { recalibrate: 'recalibrando', pause: 'en pausa', resume: 'reanudado', save_profile: 'perfil guardado',
                    load_profile: 'perfil cargado', reset_defaults: 'valores restaurados' };

// ---------- 1. Estado en vivo ----------

const METERS = [
  { key: 'yaw', label: 'yaw crudo', slot: 1 }, { key: 'yaw_f', label: 'yaw filtrado', slot: 2 },
  { key: 'pitch', label: 'pitch crudo', slot: 1 }, { key: 'pitch_f', label: 'pitch filtrado', slot: 2 },
  { key: 'roll', label: 'roll', slot: 3 },
];
const TILES = [
  ['retraso', (s) => (typeof s.retraso_ms === 'number' ? `${Math.round(s.retraso_ms)} ms` : '—')],
  ['Hz', (s) => (s.hz ? Object.entries(s.hz).map(([k, v]) => `${k} ${Number(v).toFixed(1)}`).join(' · ') : '—')],
  ['clics', (s) => fmt(s.clics)],
  ['rueda', (s) => fmt(s.rueda)],
  ['cursor', (s) => (Array.isArray(s.cursor) ? `${s.cursor[0]}, ${s.cursor[1]}` : '—')],
  ['sesgo', (s) => (Array.isArray(s.bias) ? s.bias.map((b) => Number(b).toFixed(2)).join(' ') : '—')],
  ['eco tarde', (s) => fmt(s.eco_tarde)],
  ['descartadas', (s) => fmt(s.descartadas)],
  ['delta', (s) => (s.delta ? `${Number(s.delta.dx).toFixed(1)}, ${Number(s.delta.dy).toFixed(1)}` : '—')],
];

function buildLive() {
  const meters = $('#meters');
  for (const m of METERS) {
    const row = document.createDocumentFragment();
    const lab = document.createElement('span');
    lab.className = 'lab';
    lab.textContent = m.label;
    const track = document.createElement('div');
    track.className = 'track';
    track.style.setProperty('--c', `var(--series-${m.slot})`);
    track.title = `${m.label}: ±${METER_SCALE} °/s a fondo de escala`;
    const fill = document.createElement('i');
    fill.className = 'fill';
    track.appendChild(fill);
    const val = document.createElement('span');
    val.className = 'val num';
    val.textContent = '—';
    row.append(lab, track, val);
    meters.appendChild(row);
    m.fill = fill;
    m.val = val;
  }
  const tiles = $('#tiles');
  for (const t of TILES) {
    const tile = document.createElement('div');
    tile.className = 'tile' + (t[0] === 'Hz' ? ' wide' : '');
    tile.innerHTML = '<span class="lab"></span><span class="val num">—</span>';
    tile.firstChild.textContent = t[0];
    t.el = tile.lastChild;
    tiles.appendChild(tile);
  }
}

function renderMeters() {
  const r = (latest && latest.rates) || {};
  for (const m of METERS) {
    const v = typeof r[m.key] === 'number' ? r[m.key] : 0;
    const f = clamp(v / METER_SCALE, -1, 1);
    m.fill.style.left = `${f >= 0 ? 50 : 50 + f * 50}%`;
    m.fill.style.width = `${Math.abs(f) * 50}%`;
  }
}

function describeEvent(ev) {
  const d = ev.detail || {};
  const no = d.applied === false ? ` (no aplicado: ${d.reason || '?'})` : '';
  switch (ev.kind) {
    case 'click': return `clic (${d.how || '?'})${Array.isArray(d.pos) ? ` en ${d.pos[0]},${d.pos[1]}` : ''}${typeof d.held_ms === 'number' ? ` · ${Math.round(d.held_ms)} ms` : ''}`;
    case 'yield': return `cede al ratón físico: ${fmt(d.desviacion_px)} px (${d.como || '?'})`;
    case 'bezel': return `bisel ${d.direction || '?'} ×${d.steps ?? 1} raw ${signed(d.raw)} → rueda ${signed(d.notches)}${no}`;
    case 'button': return `${d.key === 'home' ? 'inicio' : 'atrás'} ${d.pressed ? '↓' : '↑'} ${d.action || '—'}${no}`;
    case 'wheel': return `rueda ${signed(d.n)} (${d.source || '?'})`;
    case 'pause': return `pausa: ${d.reason || '?'}`;
    case 'resume': return `reanudado${d.note ? ` (${d.note})` : ''}`;
    case 'tap_candidate': return `toque candidato · pico ${fmt(d.peak)}${d.armed ? ' · armado' : ''}`;
    case 'tap_rejected': return `toque rechazado: ${d.verdict || '?'} · pico ${fmt(d.peak)} ancho ${fmt(d.width)}`;
    case 'scroll_enter': return `scroll por rodar: entra (e ${fmt(d.e)}°)`;
    case 'scroll_exit': return `scroll por rodar: sale${d.timeout ? ' (tiempo agotado)' : ''}`;
    case 'calibrated': return `calibrado · sesgo ${Array.isArray(d.bias) ? d.bias.map((b) => Number(b).toFixed(2)).join(', ') : '?'} · p2p ${fmt(d.p2p)}`;
    case 'held_release': return `suelto el botón ${d.button || '?'} (${d.reason || '?'})`;
    case 'gesture': return `gesto guardado: ${d.path || '?'} (${fmt(d.muestras)} muestras)`;
    case 'profile': return `perfil ${{ saved: 'guardado', loaded: 'cargado', defaults: 'restaurado' }[d.action] || d.action || ''}: ${d.path || ''}`;
    default: return Object.keys(d).length ? JSON.stringify(d) : '';
  }
}

function addLog(ev) {
  log.unshift(ev);
  if (log.length > LOG_MAX) log.length = LOG_MAX;
  logDirty = true;
}

function renderLog() {
  logDirty = false;
  const ol = $('#log');
  ol.innerHTML = log.map((ev) => `<li><span class="t">${escapeHtml(hhmmss(ev.t || Date.now()))}</span><span class="k">${escapeHtml(ev.kind || '?')}</span>— ${escapeHtml(describeEvent(ev))}</li>`).join('');
}

function renderLive() {
  const conn = $('#amConn');
  conn.className = 'pill ' + (connected ? 'good' : 'critical');
  conn.textContent = connected ? 'Ratón aéreo conectado' : 'Ratón aéreo no conectado: arranca python tools/air_mouse.py';
  const fresh = latest && performance.now() - latestAt < 1500;
  const s = fresh ? latest : null;
  let estado = '—', cls = '';
  if (s) {
    if (s.estado === 'pausa') { estado = `pausa: ${s.pausa || '?'}`; cls = 'warning'; }
    else if (s.estado === 'activo') { estado = 'activo'; cls = 'good'; }
    else estado = s.estado || '?';
    if (s.boton && s.boton.held) estado += ` · botón ${s.boton.held} ↓ ${Math.round(s.boton.ms || 0)} ms`;
  } else if (connected) estado = 'sin estado';
  $('#amEstado').textContent = connected ? estado : '';
  const pill = $('#estadoPill');
  pill.className = 'pill ' + cls;
  pill.textContent = estado;
  $('#stateHz').textContent = stateHz ? `${stateHz} estados/s` : '';

  for (const m of METERS) {
    const v = s && s.rates ? s.rates[m.key] : null;
    m.val.textContent = typeof v === 'number' ? `${v.toFixed(1)} °/s` : '—';
  }
  for (const t of TILES) t.el.textContent = s ? t[1](s) : '—';

  const ent = (s && s.entradas) || null;
  const pillIn = (el, name, on) => {
    el.className = 'pill ' + (on === true ? 'good' : '');
    el.textContent = `${name}: ${on === true ? 'sí' : on === false ? 'no' : '—'}`;
  };
  pillIn($('#inBezel'), 'Bisel', ent ? !!ent.bezel : null);
  pillIn($('#inButton'), 'Botón', ent ? !!ent.button : null);
  $('#modos').textContent = efectivo ? `clic por ${MODE_NAMES[efectivo.click] || efectivo.click} · scroll por ${MODE_NAMES[efectivo.scroll] || efectivo.scroll}` : '';
  if (logDirty) renderLog();

  const btn = $('#btnPause');
  btn.textContent = s && s.estado === 'pausa' && /usuario/.test(s.pausa || '') ? 'Reanudar' : 'Pausar';
  for (const b of ['#btnRecal', '#btnPause', '#btnSave', '#btnReset', '#gestureRecord', '#bezelTest']) $(b).disabled = !connected;
}

// ---------- 2. Ajustes ----------

const ctlEls = new Map();   // name -> { c, el, input, out }
const debounce = new Map();
const touched = new Map();  // name -> performance.now() of the last local edit
let dragging = null;

function buildControls() {
  const box = $('#ajustesGroups');
  const groups = new Map();
  for (const c of CONTROLS) {
    let g = groups.get(c.group);
    if (!g) {
      g = document.createElement('fieldset');
      g.className = 'grp';
      const legend = document.createElement('legend');
      legend.textContent = c.group;
      g.appendChild(legend);
      groups.set(c.group, g);
      box.appendChild(g);
    }
    const lab = document.createElement('label');
    lab.className = 'ctl';
    lab.dataset.name = c.name;
    const span = document.createElement('span');
    span.textContent = c.label;
    let input;
    if (c.type === 'select') {
      input = document.createElement('select');
      for (const [v, l] of c.options) {
        const o = document.createElement('option');
        o.value = v;
        o.textContent = l;
        input.appendChild(o);
      }
    } else {
      input = document.createElement('input');
      input.type = c.type === 'check' ? 'checkbox' : 'range';
      if (c.type === 'range') { input.min = c.min; input.max = c.max; input.step = c.step; }
    }
    const out = document.createElement('output');
    out.className = 'num';
    lab.append(span, input, out);
    g.appendChild(lab);
    ctlEls.set(c.name, { c, el: lab, input, out });
    setControl(c.name, c.def);
    const onEdit = () => onControlInput(c);
    input.addEventListener('input', onEdit);
    input.addEventListener('change', onEdit);
    input.addEventListener('pointerdown', () => { dragging = input; });
  }
  document.addEventListener('pointerup', () => { dragging = null; });
  document.addEventListener('pointercancel', () => { dragging = null; });
  // The bezel direction test lives inside the Bisel group.
  groups.get('Bisel').appendChild($('#bezelTestBox'));
}

function readControl(c, input) {
  return c.type === 'range' ? Number(input.value) : c.type === 'check' ? input.checked : input.value;
}

function controlText(c, value) {
  if (c.type === 'check') return value ? 'sí' : 'no';
  if (c.type === 'select') return '';
  const dec = Math.max(0, -Math.floor(Math.log10(c.step) + 1e-9));
  return Number(value).toFixed(dec);
}

function setControl(name, value) {
  const { c, input, out } = ctlEls.get(name);
  if (c.type === 'range') input.value = value;
  else if (c.type === 'check') input.checked = !!value;
  else input.value = String(value);
  out.textContent = controlText(c, value);
}

function onControlInput(c) {
  const { input, el, out } = ctlEls.get(c.name);
  const value = readControl(c, input);
  out.textContent = controlText(c, value);
  touched.set(c.name, performance.now());
  clearTimeout(debounce.get(c.name));
  if (!connected) { showMsg($('#ajustesMsg'), 'ratón aéreo no conectado: el ajuste no se aplica', 'critical'); return; }
  el.classList.add('pending');
  debounce.set(c.name, setTimeout(() => {
    if (!setParams({ [c.name]: value })) el.classList.remove('pending');
  }, 60));
}

// `force` reverts even the control being edited (after an `error`).
function renderControls(force) {
  const p = params || {};
  const now = performance.now();
  for (const [name, { c, el, input }] of ctlEls) {
    el.classList.remove('pending');
    if (!(name in p)) continue;
    const busy = dragging === input || (document.activeElement === input && now - (touched.get(name) || 0) < 400);
    if (force || !busy) setControl(name, p[name]);
  }
  for (const name of ['click', 'scroll']) {
    const eff = efectivo && efectivo[name];
    ctlEls.get(name).out.textContent = eff ? `→ en uso: ${MODE_NAMES[eff] || eff}` : '';
  }
  $('#profile').textContent = profile ? `perfil: ${profile}` : '';
  $('#notchesCtl b').textContent = String(current().bezel_notches ?? 1);
  for (const f of document.querySelectorAll('fieldset.grp')) f.disabled = !connected;
}

function bindButtons() {
  $('#btnRecal').addEventListener('click', () => cmd('recalibrate'));
  $('#btnPause').addEventListener('click', () => cmd(latest && latest.estado === 'pausa' ? 'resume' : 'pause'));
  $('#btnSave').addEventListener('click', () => cmd('save_profile'));
  $('#btnReset').addEventListener('click', () => {
    if (confirm('¿Restaurar todos los valores por defecto? Se pierde el ajuste actual (el perfil guardado no se toca hasta que guardes).')) cmd('reset_defaults');
  });
  $('#bezelFlip').addEventListener('click', flipBezel);
  $('#scrollFlip').addEventListener('click', flipBezel);
  $('#notchesMinus').addEventListener('click', () => setParams({ bezel_notches: clamp(Number(current().bezel_notches || 1) - 1, 1, 10) }));
  $('#notchesPlus').addEventListener('click', () => setParams({ bezel_notches: clamp(Number(current().bezel_notches || 1) + 1, 1, 10) }));
}

function flipBezel() {
  if (!setParams({ bezel_invert: !current().bezel_invert })) showMsg($('#ajustesMsg'), 'ratón aéreo no conectado', 'critical');
}

// Bezel direction test: one turn to the right tells both the bridge's label and the scroll sign.
let bezelArmedUntil = 0;
let bezelTimer = null;

function startBezelTest() {
  if (!connected) { $('#bezelResult').textContent = 'ratón aéreo no conectado'; return; }
  bezelArmedUntil = performance.now() + 5000;
  $('#bezelResult').textContent = 'gira ahora el bisel hacia la derecha (sentido horario)… 5 s';
  $('#bezelFlip').hidden = true;
  clearTimeout(bezelTimer);
  bezelTimer = setTimeout(() => {
    if (!bezelArmedUntil) return;
    bezelArmedUntil = 0;
    $('#bezelResult').textContent = 'no llegó ningún giro: ¿el puente corre con --inputs bezel?';
  }, 5000);
}

function onBezelTest(ev) {
  if (!bezelArmedUntil || performance.now() > bezelArmedUntil) return;
  bezelArmedUntil = 0;
  clearTimeout(bezelTimer);
  const d = ev.detail || {};
  const n = typeof d.notches === 'number' ? d.notches : null;
  const lines = [`llegó raw ${signed(d.raw)} → ${d.direction || '?'} → rueda ${signed(n)}` +
                 (n === null ? '' : n < 0 ? ' (la página bajaría)' : n > 0 ? ' (la página subiría)' : ' (sin rueda)')];
  if (d.applied === false) {
    lines.push(`no aplicado: ${d.reason || '?'}` + (/^modo/.test(d.reason || '') ? ' → activa scroll por bisel en Ajustes' : ''));
  }
  if (d.direction !== 'CW') {
    // One cause, two remedies: fixing the bridge's label also flips the wheel sign, so never apply both.
    lines.push('el puente etiquetó CCW un giro a la derecha. O bien arrancas sdb_bridge.py con --bezel-positive ccw (y el dashboard acierta), o bien pulsas "Invertir bisel" aquí: una de las dos, no las dos');
    $('#bezelFlip').hidden = !(n !== null && n > 0);
  } else if (n !== null && n > 0) {
    lines.push('el scroll iría hacia arriba: invierte el bisel');
    $('#bezelFlip').hidden = false;
  } else if (n !== null && n < 0) lines.push('sentido correcto');
  $('#bezelResult').textContent = lines.join('\n');
}

// ---------- 3. Prueba de objetivos ----------

const SIZES = [24, 56];
const CONDS = [[0, 0], [0, 1], [1, 0], [1, 1]];   // [distance index, size index]

// Deterministic target sequence; pure (also exported on window.calib for checks).
function sequence(aw, ah) {
  const S = Math.min(aw, ah) - 64;
  let dist = [0.30 * S, 0.65 * S];
  for (let attempt = 0; attempt < 12; attempt++) {
    const trials = [];
    let prev = { x: aw / 2, y: ah / 2 };
    let ok = true;
    for (let i = 0; i < 16; i++) {
      // Each (H, V) pair shares a condition so both axes see every distance × size twice; the second
      // block starts with the long distance. (Indexing conditions by i % 4 would tie the size to the axis.)
      const [dIdx, wIdx] = CONDS[((i >> 1) + (i < 8 ? 0 : 2)) % 4];
      const axis = i % 2 === 0 ? 'H' : 'V';
      const D = dist[dIdx], W = SIZES[wIdx];
      const margin = SIZES[1] / 2 + 8;
      const limit = axis === 'H' ? aw : ah;
      const p = axis === 'H' ? prev.x : prev.y;
      let q;
      if (p + D + margin <= limit) q = p + D;
      else if (p - D - margin >= 0) q = p - D;
      else { ok = false; break; }
      const c = axis === 'H' ? { x: q, y: prev.y } : { x: prev.x, y: q };
      trials.push({ i, axis, dIdx, wIdx, D, W, cx: c.x, cy: c.y });
      prev = c;
    }
    if (ok) return trials;
    dist = dist.map((d) => d * 0.8);
  }
  return null;
}

function metrics(tr) {
  const { trial, t0, start, path, tClick, entries, firstEntryT, misses } = tr;
  const tx = trial.cx, ty = trial.cy, W = trial.W;
  let L = 0;
  for (let k = 1; k < path.length; k++) L += Math.hypot(path[k].x - path[k - 1].x, path[k].y - path[k - 1].y);
  const S = Math.hypot(tx - start.x, ty - start.y);
  const ux = S > 0 ? (tx - start.x) / S : 0, uy = S > 0 ? (ty - start.y) / S : 0;
  let over = 0;
  for (const p of path) over = Math.max(over, (p.x - tx) * ux + (p.y - ty) * uy);
  const MT = Math.max(1, tClick - t0);
  const ID = Math.log2(trial.D / W + 1);
  return {
    i: trial.i, axis: trial.axis, dIdx: trial.dIdx, wIdx: trial.wIdx, D: trial.D, W, MT,
    TFE: firstEntryT === null || firstEntryT === undefined ? MT : firstEntryT - t0,
    L, S, eff: S / Math.max(L, S, 1e-9), reentries: Math.max(0, entries - 1), misses,
    overshoot: over, overshootW: over / W, ID, TP: ID / (MT / 1000),
  };
}

function aggregate(rows) {
  const groups = { H: (r) => r.axis === 'H', V: (r) => r.axis === 'V', small: (r) => r.wIdx === 0, large: (r) => r.wIdx === 1,
                   short: (r) => r.dIdx === 0, long: (r) => r.dIdx === 1, total: () => true };
  const out = {};
  for (const [k, f] of Object.entries(groups)) {
    const g = rows.filter(f);
    out[k] = { n: g.length, medMT: median(g.map((r) => r.MT)), medTFE: median(g.map((r) => r.TFE)), meanEff: mean(g.map((r) => r.eff)),
               reentriesPerTrial: g.length ? sum(g.map((r) => r.reentries)) / g.length : 0, misses: sum(g.map((r) => r.misses)),
               medOvershootW: median(g.map((r) => r.overshootW)), meanTP: mean(g.map((r) => r.TP)) };
  }
  return out;
}

function suggest(agg, p) {
  const out = [];
  const val = (name) => Number(p[name] ?? CONTROL_BY_NAME.get(name).def);
  const prop = (param, value, reason) => {
    const c = CONTROL_BY_NAME.get(param);
    out.push({ param, value: round2(clamp(value, c.min, c.max)), reason });
  };
  const H = agg.H, V = agg.V;
  const rV = H.medMT > 0 ? V.medMT / H.medMT : 1;
  const rH = V.medMT > 0 ? H.medMT / V.medMT : 1;
  if (rV > 1.3 && V.reentriesPerTrial <= 0.5 && V.medOvershootW <= 0.5) {
    prop('gain_y', val('gain_y') * Math.min(rV, 1.5), `la vertical tarda ×${rV.toFixed(2)} más que la horizontal sin pasarse`);
  }
  if (rH > 1.3 && H.reentriesPerTrial <= 0.5 && H.medOvershootW <= 0.5) {
    prop('gain_x', val('gain_x') * Math.min(rH, 1.5), `la horizontal tarda ×${rH.toFixed(2)} más que la vertical sin pasarse`);
  }
  const overV = V.reentriesPerTrial >= 1 || V.medOvershootW > 1;
  const overH = H.reentriesPerTrial >= 1 || H.medOvershootW > 1;
  let rule3 = false;
  if (overV && overH) { prop('gain', val('gain') * 0.85, 'se pasa del objetivo en los dos ejes'); rule3 = true; }
  else if (overV) { prop('gain_y', val('gain_y') * 0.85, 'se pasa del objetivo en vertical'); rule3 = true; }
  else if (overH) { prop('gain_x', val('gain_x') * 0.85, 'se pasa del objetivo en horizontal'); rule3 = true; }
  if (agg.total.meanEff < 0.7 || agg.small.reentriesPerTrial >= 1.5) {
    prop('mincutoff', Math.max(0.5, val('mincutoff') * 0.7), 'trayectoria temblorosa: más suavizado');
    if (agg.large.medMT > 0 && agg.small.medMT / agg.large.medMT > 1.8) {
      prop('deadzone', Math.min(2.0, val('deadzone') + 0.3), 'cuesta clavar los objetivos pequeños: más zona muerta');
    }
  }
  if (!rule3 && agg.short.medMT > 0 && agg.long.medMT / agg.short.medMT > 2.2) {
    prop('g_hi', Math.min(120, val('g_hi') * 1.25), 'los trayectos largos son lentos: más aceleración');
  }
  if (agg.long.misses >= 3) prop('g_hi', val('g_hi') * 0.8, 'fallos en los trayectos largos: menos aceleración');
  if (!out.length) out.push({ param: null, value: null, reason: `sin cambios sugeridos: tiempos equilibrados (vertical/horizontal ×${rV.toFixed(2)})` });
  return out;
}

const target = { trials: null, idx: -1, cur: null, rows: [], startEl: null };
const board = { on: false, samples: [], last: null, ctx: null, dirty: false };

const arenaRect = () => $('#arena').getBoundingClientRect();

function resetTargets() {
  const arena = $('#arena');
  for (const el of arena.querySelectorAll('.target')) el.remove();
  target.trials = null;
  target.idx = -1;
  target.cur = null;
  target.rows = [];
  target.startEl = null;
}

function startTargets() {
  resetTargets();
  const arena = $('#arena');
  const trials = sequence(arena.clientWidth, arena.clientHeight);
  if (!trials) { $('#targetProgress').textContent = 'la zona es demasiado pequeña'; return; }
  target.trials = trials;
  const dpr = window.devicePixelRatio || 1;
  const btn = document.createElement('button');
  btn.className = 'target start';
  btn.id = 'startCircle';
  btn.textContent = 'Empieza aquí';
  btn.style.left = `${arena.clientWidth / 2 - 28}px`;
  btn.style.top = `${arena.clientHeight / 2 - 28}px`;
  arena.appendChild(btn);
  target.startEl = btn;
  const dists = [0, 1].map((k) => trials.find((t) => t.dIdx === k).D).map((d) => `${Math.round(d)} px (${Math.round(d * dpr)} px de pantalla)`);
  $('#targetProgress').textContent = `pulsa «Empieza aquí» · distancias ${dists.join(' y ')} · tamaños ${SIZES.join(' y ')} px`;
  $('#targetResults').hidden = true;
}

function beginTrial(i, t, pos) {
  const arena = $('#arena');
  if (target.cur && target.cur.el) target.cur.el.remove();
  const trial = target.trials[i];
  const el = document.createElement('button');
  el.className = 'target';
  el.textContent = String(i + 1);
  el.style.width = el.style.height = `${trial.W}px`;
  el.style.left = `${trial.cx - trial.W / 2}px`;
  el.style.top = `${trial.cy - trial.W / 2}px`;
  arena.appendChild(el);
  target.idx = i;
  target.cur = { trial, t0: t, start: { x: pos.x, y: pos.y }, path: [{ t, x: pos.x, y: pos.y }], entries: 0, inside: false,
                 firstEntryT: null, misses: 0, el };
  $('#targetProgress').textContent = `ensayo ${i + 1}/16 · ${trial.axis === 'H' ? 'horizontal' : 'vertical'} · ${trial.W} px · ${Math.round(trial.D)} px`;
}

function finishTrial(t, pos) {
  const cur = target.cur;
  cur.path.push({ t, x: pos.x, y: pos.y });
  if (!cur.inside) { cur.entries++; if (cur.firstEntryT === null) cur.firstEntryT = t; }
  cur.tClick = t;
  target.rows.push(metrics(cur));
  cur.el.remove();
  target.cur = null;
  if (target.idx + 1 < target.trials.length) beginTrial(target.idx + 1, t, pos);
  else {
    $('#targetProgress').textContent = 'prueba terminada';
    renderResults(target.rows);
  }
}

function onArenaClick(e) {
  if (board.on) return;
  const r = arenaRect();
  const pos = { x: e.clientX - r.left, y: e.clientY - r.top };
  const t = e.timeStamp;
  if (target.startEl && e.target === target.startEl) {
    target.startEl.remove();
    target.startEl = null;
    beginTrial(0, t, pos);
    return;
  }
  const cur = target.cur;
  if (!cur) return;
  if (Math.hypot(pos.x - cur.trial.cx, pos.y - cur.trial.cy) <= cur.trial.W / 2) finishTrial(t, pos);
  else cur.misses++;
}

function onPointerMove(e) {
  if (e.pointerType === 'touch') return;
  const cur = target.cur;
  if (!cur && !board.on) return;
  const r = arenaRect();
  let evs = e.getCoalescedEvents ? e.getCoalescedEvents() : [];
  if (!evs.length) evs = [e];
  for (const ce of evs) {
    const p = { t: ce.timeStamp, x: ce.clientX - r.left, y: ce.clientY - r.top };
    if (cur && cur.path.length < PATH_CAP) {
      cur.path.push(p);
      const inside = Math.hypot(p.x - cur.trial.cx, p.y - cur.trial.cy) <= cur.trial.W / 2;
      if (inside && !cur.inside) { cur.entries++; if (cur.firstEntryT === null) cur.firstEntryT = p.t; }
      cur.inside = inside;
    }
    if (board.on) boardPoint(p);
  }
}

function fmtRow(r) {
  return `<tr><td>${r.i + 1}</td><td>${r.axis}</td><td>${Math.round(r.D)}</td><td>${r.W}</td><td>${Math.round(r.MT)}</td><td>${Math.round(r.TFE)}</td>` +
         `<td>${r.eff.toFixed(2)}</td><td>${r.reentries}</td><td>${r.overshootW.toFixed(2)}</td><td>${r.misses}</td></tr>`;
}

function fmtAgg(name, a) {
  return `<tr class="agg"><td>${escapeHtml(name)}</td><td></td><td></td><td></td><td>${Math.round(a.medMT)}</td><td>${Math.round(a.medTFE)}</td>` +
         `<td>${a.meanEff.toFixed(2)}</td><td>${a.reentriesPerTrial.toFixed(2)}</td><td>${a.medOvershootW.toFixed(2)}</td><td>${a.misses}</td></tr>`;
}

function renderResults(rows) {
  const agg = aggregate(rows);
  const tbl = $('#targetTable');
  tbl.innerHTML = '<thead><tr><th>#</th><th>eje</th><th>D px</th><th>W px</th><th>MT ms</th><th>1.ª entrada ms</th><th>eficiencia</th>' +
                  '<th>reentradas</th><th>sobrepaso/W</th><th>fallos</th></tr></thead>' +
                  `<tbody>${rows.map(fmtRow).join('')}${fmtAgg('H (mediana)', agg.H)}${fmtAgg('V (mediana)', agg.V)}${fmtAgg('total', agg.total)}</tbody>`;
  renderChart(rows);
  const sug = suggest(agg, current());
  const ul = $('#suggestion');
  ul.innerHTML = '';
  for (const s of sug) {
    const li = document.createElement('li');
    const txt = document.createElement('span');
    txt.textContent = s.reason;
    li.appendChild(txt);
    if (s.param) {
      const v = document.createElement('span');
      v.className = 'val';
      v.textContent = `${s.param}: ${fmt(current()[s.param] ?? CONTROL_BY_NAME.get(s.param).def)} → ${s.value}`;
      const b = document.createElement('button');
      b.textContent = 'Aplicar';
      b.addEventListener('click', () => {
        if (setParams({ [s.param]: s.value })) { b.disabled = true; b.textContent = 'Aplicado · repite la prueba'; }
        else showMsg($('#ajustesMsg'), 'ratón aéreo no conectado: no se puede aplicar', 'critical');
      });
      li.append(v, b);
    }
    ul.appendChild(li);
  }
  $('#targetResults').hidden = false;
}

// MT per trial as thin horizontal bars coloured by axis: one axis (ms), legend for the two series,
// text in text tokens, hover tooltip per bar.
function renderChart(rows) {
  const box = $('#targetChart');
  const max = Math.max(1, ...rows.map((r) => r.MT));
  const step = niceStep(max, 4);
  const top = Math.ceil(max / step) * step;
  box.innerHTML = '<ul class="legend"><li><i style="background:var(--series-1)"></i><span>horizontal</span></li>' +
                  '<li><i style="background:var(--series-2)"></i><span>vertical</span></li></ul>' +
                  '<div class="bars"><div class="btitle">tiempo de movimiento por ensayo (ms)</div></div><div class="tip" hidden></div>';
  const bars = $('.bars', box);
  const tip = $('.tip', box);
  for (const r of rows) {
    const lab = document.createElement('span');
    lab.className = 'blab num';
    lab.textContent = String(r.i + 1);
    const track = document.createElement('div');
    track.className = 'btrack';
    const bar = document.createElement('div');
    bar.className = 'bar';
    bar.style.width = `${(r.MT / top) * 100}%`;
    bar.style.background = r.axis === 'H' ? 'var(--series-1)' : 'var(--series-2)';
    bar.addEventListener('mouseenter', () => {
      tip.innerHTML = `<div class="muted">ensayo ${r.i + 1} · ${r.axis === 'H' ? 'horizontal' : 'vertical'} · D ${Math.round(r.D)} · W ${r.W}</div>` +
                      `<div>MT <b>${Math.round(r.MT)} ms</b></div><div>eficiencia <b>${r.eff.toFixed(2)}</b> · reentradas <b>${r.reentries}</b></div>`;
      tip.hidden = false;
      const br = track.getBoundingClientRect(), cr = box.getBoundingClientRect();
      tip.style.top = `${br.top - cr.top - 4}px`;
      tip.style.left = `${Math.min(br.left - cr.left + bar.offsetWidth + 10, cr.width - tip.offsetWidth - 4)}px`;
    });
    bar.addEventListener('mouseleave', () => { tip.hidden = true; });
    track.appendChild(bar);
    bars.append(lab, track);
  }
  const axis = document.createElement('div');
  axis.className = 'baxis num';
  for (let v = 0; v <= top + 1e-9; v += step) {
    const s = document.createElement('span');
    s.textContent = String(Math.round(v));
    axis.appendChild(s);
  }
  bars.appendChild(axis);
}

function niceStep(range, count) {
  const raw = range / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const n = raw / mag;
  return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag;
}

// Pizarra: free drawing of the cursor path to look at tremor.
function sizeBoard() {
  const canvas = $('#board');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    board.ctx = canvas.getContext('2d');
    board.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    redrawBoard();
  }
}

function strokeStyle(ctx) {
  ctx.strokeStyle = palette[1];
  ctx.lineWidth = 2;
  ctx.lineJoin = 'bevel';
  ctx.lineCap = 'butt';
}

function boardPoint(p) {
  const ctx = board.ctx;
  if (board.samples.length >= PATH_CAP) board.samples.shift();
  board.samples.push(p);
  if (ctx && board.last) {
    strokeStyle(ctx);
    ctx.beginPath();
    ctx.moveTo(board.last.x, board.last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  }
  board.last = p;
  board.dirty = true;
}

function redrawBoard() {
  const ctx = board.ctx;
  if (!ctx) return;
  const canvas = $('#board');
  ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  if (board.samples.length < 2) return;
  strokeStyle(ctx);
  ctx.beginPath();
  ctx.moveTo(board.samples[0].x, board.samples[0].y);
  for (let i = 1; i < board.samples.length; i++) ctx.lineTo(board.samples[i].x, board.samples[i].y);
  ctx.stroke();
}

// RMS distance of each sample to the mean of the samples within ±half ms: a high-pass of the path.
function jitterRMS(samples, half = 100) {
  const n = samples.length;
  if (n < 3) return 0;
  let lo = 0, hi = 0, sx = 0, sy = 0, cnt = 0, acc = 0;
  for (let i = 0; i < n; i++) {
    const t = samples[i].t;
    while (hi < n && samples[hi].t <= t + half) { sx += samples[hi].x; sy += samples[hi].y; cnt++; hi++; }
    while (samples[lo].t < t - half) { sx -= samples[lo].x; sy -= samples[lo].y; cnt--; lo++; }
    const mx = sx / cnt, my = sy / cnt;
    acc += (samples[i].x - mx) ** 2 + (samples[i].y - my) ** 2;
  }
  return Math.sqrt(acc / n);
}

function renderBoardStats() {
  if (!board.dirty) return;
  board.dirty = false;
  let L = 0;
  for (let i = 1; i < board.samples.length; i++) L += Math.hypot(board.samples[i].x - board.samples[i - 1].x, board.samples[i].y - board.samples[i - 1].y);
  $('#boardStats').textContent = board.samples.length ? `recorrido ${Math.round(L)} px · temblor ${jitterRMS(board.samples).toFixed(2)} px` : '';
}

function setBoard(on) {
  board.on = on;
  $('#boardToggle').setAttribute('aria-pressed', String(on));
  $('#arena').classList.toggle('boarding', on);
  board.last = null;
  if (on) sizeBoard();
}

function clearBoard() {
  board.samples = [];
  board.last = null;
  board.dirty = true;
  redrawBoard();
  renderBoardStats();
}

// ?demo=1: synthetic trials so the table, chart and suggestions can be checked without a connection.
function demoTrials() {
  const trials = sequence(800, 500);
  const rows = [];
  let seed = 7;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  let start = { x: 400, y: 250 };
  for (const tr of trials) {
    const ID = Math.log2(tr.D / tr.W + 1);
    const MT = (250 + 160 * ID) * (tr.axis === 'V' ? 1.46 : 1) * (0.96 + 0.08 * rnd());
    const n = Math.max(20, Math.round(MT / 10));
    const path = [];
    const dx = tr.cx - start.x, dy = tr.cy - start.y;
    const t0 = 1000;
    for (let k = 0; k <= n; k++) {
      const u = k / n;
      const s = 10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5;
      path.push({ t: t0 + (MT * k) / n, x: start.x + dx * s + (rnd() - 0.5) * 2, y: start.y + dy * s + (rnd() - 0.5) * 2 });
    }
    let tClick = t0 + MT;
    if (tr.i === 2) {  // one small target with two re-entries (overshoot, back in, out, back in)
      const ax = tr.axis === 'H' ? Math.sign(dx) : 0, ay = tr.axis === 'V' ? Math.sign(dy) : 0;
      for (const [off, dt] of [[30, 40], [18, 80], [6, 120], [-4, 160], [-20, 200], [-14, 240], [2, 280]]) {
        path.push({ t: tClick + dt, x: tr.cx + ax * off, y: tr.cy + ay * off });
      }
      tClick += 300;
    }
    let entries = 0, inside = false, firstEntryT = null;
    for (const p of path) {
      const inNow = Math.hypot(p.x - tr.cx, p.y - tr.cy) <= tr.W / 2;
      if (inNow && !inside) { entries++; if (firstEntryT === null) firstEntryT = p.t; }
      inside = inNow;
    }
    rows.push(metrics({ trial: tr, t0, start, path, tClick, entries: Math.max(entries, 1), firstEntryT, misses: tr.i === 9 ? 1 : 0 }));
    start = { x: tr.cx, y: tr.cy };
  }
  return rows;
}

// ---------- 4. Prueba de clic ----------

const clickTest = { page: [], am: [], falsos: 0, perdidos: 0, lastLost: null, latencies: [], held: [],
                    tapCand: 0, rejForma: 0, rejGiro: 0, timer: null, dirty: true };

function onPadDown(e) {
  clickTest.page.push({ tDown: wallOf(e), tUp: null, x: e.offsetX, y: e.offsetY, button: e.button, m: null });
  matchClicks();
}

function onPadUp(e) {
  for (let i = clickTest.page.length - 1; i >= 0; i--) {
    const p = clickTest.page[i];
    if (p.tUp === null && p.button === e.button) { p.tUp = wallOf(e); break; }
  }
  matchClicks();
}

function onClickEvent(ev) {
  const d = ev.detail || {};
  clickTest.am.push({ t: ev.t, how: d.how, pos: d.pos, m: null });
  if (d.how === 'button' && typeof d.held_ms === 'number') clickTest.held.push(d.held_ms);
  matchClicks();
}

// A button click is reported on release, a tap/dwell click when it is sent: pair with the page's up or down accordingly.
function pageTime(p, a) { return a.how === 'button' && p.tUp !== null ? p.tUp : p.tDown; }

function matchClicks() {
  for (const a of clickTest.am) {
    if (a.m) continue;
    let best = null, bestDt = Infinity;
    for (const p of clickTest.page) {
      if (p.m) continue;
      const dt = Math.abs(pageTime(p, a) - a.t);
      if (dt <= MATCH_MS && dt < bestDt) { best = p; bestDt = dt; }
    }
    if (best) {
      a.m = best;
      best.m = a;
      clickTest.latencies.push(pageTime(best, a) - a.t);
    }
  }
  clickTest.dirty = true;
  clearTimeout(clickTest.timer);
  clickTest.timer = setTimeout(classifyClicks, CLASSIFY_MS + 20);
}

function classifyClicks() {
  const now = Date.now();
  let pending = false;
  for (const p of clickTest.page) {
    if (p.m) continue;
    if (p.tUp !== null && now - p.tUp > CLASSIFY_MS) { p.m = 'falso'; clickTest.falsos++; } else pending = true;
  }
  for (const a of clickTest.am) {
    if (a.m) continue;
    if (now - a.t > CLASSIFY_MS) { a.m = 'perdido'; clickTest.perdidos++; clickTest.lastLost = a.pos; } else pending = true;
  }
  clickTest.dirty = true;
  if (pending) clickTest.timer = setTimeout(classifyClicks, CLASSIFY_MS + 20);
}

function renderClickTest() {
  if (!clickTest.dirty) return;
  clickTest.dirty = false;
  $('#pageClicks').textContent = String(clickTest.page.length);
  $('#amClicks').textContent = String(clickTest.am.length);
  $('#clickLatency').textContent = clickTest.latencies.length ? `${Math.round(median(clickTest.latencies))}` : '—';
  $('#falseClicks').textContent = String(clickTest.falsos);
  $('#lostClicks').textContent = String(clickTest.perdidos) + (clickTest.lastLost ? ` (último en ${clickTest.lastLost[0]},${clickTest.lastLost[1]})` : '');
  const eff = efectivo && efectivo.click;
  $('#tapStats').textContent = eff && /tap/.test(eff) || clickTest.tapCand ?
    `toques: candidatos ${clickTest.tapCand} · rechazados por forma ${clickTest.rejForma} · por giro ${clickTest.rejGiro}` : '';
  $('#heldStats').textContent = clickTest.held.length ? `pulsación mediana ${Math.round(median(clickTest.held))} ms` : '';
}

function resetClickTest() {
  Object.assign(clickTest, { page: [], am: [], falsos: 0, perdidos: 0, lastLost: null, latencies: [], held: [], tapCand: 0, rejForma: 0, rejGiro: 0, dirty: true });
  clearTimeout(clickTest.timer);
}

// ---------- 5. Prueba de scroll ----------

const scrollTest = { wheel: [], detents: [], dirty: true };

function buildScrollPanel() {
  const panel = $('#scrollPanel');
  const frag = document.createDocumentFragment();
  for (let i = 1; i <= 200; i++) {
    const div = document.createElement('div');
    div.textContent = `línea ${i}`;
    if (i === 100) { div.className = 'mark'; div.textContent += ' ← línea marcada'; }
    frag.appendChild(div);
  }
  panel.appendChild(frag);
  const mark = $('.mark', panel);
  panel.scrollTop = Math.max(0, panel.scrollTop + mark.getBoundingClientRect().top - panel.getBoundingClientRect().top - (panel.clientHeight - mark.offsetHeight) / 2);
  panel.addEventListener('wheel', (e) => {
    scrollTest.wheel.push({ t: wallOf(e), sign: Math.sign(e.deltaY), dy: e.deltaY });
    if (scrollTest.wheel.length > 500) scrollTest.wheel.shift();
    scrollTest.dirty = true;
  }, { passive: true });
}

function onBezelScroll(ev) {
  const d = ev.detail || {};
  scrollTest.detents.push({ t: ev.t, direction: d.direction, steps: Number(d.steps) || 1, notches: d.notches, applied: d.applied !== false });
  if (scrollTest.detents.length > 500) scrollTest.detents.shift();
  scrollTest.dirty = true;
  setTimeout(() => { scrollTest.dirty = true; }, BEZEL_WHEEL_MS + 50);  // re-count once the wheel events had time to arrive
}

function wheelAfter(d) { return scrollTest.wheel.filter((w) => w.t >= d.t - 50 && w.t <= d.t + BEZEL_WHEEL_MS); }

function renderScrollTest() {
  if (!scrollTest.dirty) return;
  scrollTest.dirty = false;
  const det = scrollTest.detents;
  $('#detents').textContent = String(det.length);
  const applied = det.filter((d) => d.applied);
  const steps = sum(applied.map((d) => d.steps));
  const events = sum(applied.map((d) => wheelAfter(d).length));
  $('#notchesPerDetent').textContent = steps ? (events / steps).toFixed(2) : '—';
  const el = $('#scrollDir');
  const lastCW = [...det].reverse().find((d) => d.direction === 'CW');
  $('#scrollFlip').hidden = true;
  if (!lastCW) { el.textContent = 'gira hacia la derecha (horario): la lista debería bajar'; el.className = 'msg'; return; }
  if (!lastCW.applied) { el.textContent = 'el último giro no se aplicó: activa scroll por bisel en Ajustes'; el.className = 'msg critical'; return; }
  const w = wheelAfter(lastCW);
  if (!w.length) { el.textContent = 'giro recibido pero sin rueda en la lista: pon el cursor sobre la lista'; el.className = 'msg'; return; }
  const sign = Math.sign(sum(w.map((x) => x.sign)));
  if (sign > 0) { el.textContent = 'giro a la derecha → la lista bajó ✔'; el.className = 'msg good'; }
  else if (sign < 0) { el.textContent = 'giro a la derecha → la lista subió: invertido'; el.className = 'msg critical'; $('#scrollFlip').hidden = false; }
  else { el.textContent = 'giro a la derecha → sin desplazamiento neto'; el.className = 'msg'; }
}

function resetScrollTest() {
  scrollTest.wheel = [];
  scrollTest.detents = [];
  scrollTest.dirty = true;
}

// ---------- 6. Grabar gesto ----------

function recordGesture() {
  const input = $('#gestureLabel');
  if (!input.checkValidity()) { showMsg($('#gestoMsg'), 'etiqueta: solo letras, números, _ y - (máx. 32)', 'critical'); return; }
  const label = input.value.trim() || 'empuje';
  if (!cmd('record_gesture', { label })) showMsg($('#gestoMsg'), 'ratón aéreo no conectado', 'critical');
  else showMsg($('#gestoMsg'), 'grabando…', '');
}

function renderGestures(msg) {
  const ul = $('#gestureList');
  const files = Array.isArray(msg.files) ? msg.files : [];
  ul.innerHTML = files.length ? '' : `<li class="muted">sin gestos grabados${msg.dir ? ` en ${escapeHtml(msg.dir)}` : ''}</li>`;
  for (const f of files) {
    const li = document.createElement('li');
    li.textContent = `${f.name} · ${(Number(f.bytes || 0) / 1024).toFixed(1)} KB · ${typeof f.t === 'number' ? hhmm(f.t) : ''}`;
    ul.appendChild(li);
  }
}

// ---------- Event dispatch to the tests ----------

function onEvent(ev) {
  const d = ev.detail || {};
  switch (ev.kind) {
    case 'bezel': onBezelTest(ev); onBezelScroll(ev); break;
    case 'click': onClickEvent(ev); break;
    case 'tap_candidate': clickTest.tapCand++; clickTest.dirty = true; break;
    case 'tap_rejected':
      if (d.verdict === 'forma') clickTest.rejForma++;
      else if (d.verdict === 'giro') clickTest.rejGiro++;
      clickTest.dirty = true;
      break;
    case 'gesture': cmd('list_gestures'); break;
  }
}

// ---------- Render loop ----------

let lastMeter = 0, lastText = 0;
function frame(now) {
  if (metersDirty && now - lastMeter >= 33) {
    metersDirty = false;
    lastMeter = now;
    renderMeters();
  }
  if (now - lastText >= 100) {
    lastText = now;
    renderLive();
    renderClickTest();
    renderScrollTest();
    renderBoardStats();
  }
  requestAnimationFrame(frame);
}

function init() {
  readPalette();
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { readPalette(); redrawBoard(); });
  buildLive();
  buildControls();
  bindButtons();
  renderControls(false);
  buildScrollPanel();

  if (navigator.maxTouchPoints > 0 && innerWidth < 700) for (const el of document.querySelectorAll('.needsCursor')) el.hidden = false;

  $('#bezelTest').addEventListener('click', startBezelTest);
  $('#targetStart').addEventListener('click', () => { if (board.on) setBoard(false); startTargets(); });
  $('#boardToggle').addEventListener('click', () => { setBoard(!board.on); });
  $('#boardClear').addEventListener('click', () => { clearBoard(); if (!board.on) { resetTargets(); $('#targetProgress').textContent = ''; } });
  $('#arena').addEventListener('click', onArenaClick);
  document.addEventListener('pointermove', onPointerMove);
  window.addEventListener('resize', () => { if (board.on) sizeBoard(); });
  const topHdr = $('header.top');
  const setTopH = () => document.documentElement.style.setProperty('--top-h', `${topHdr.offsetHeight}px`);
  setTopH();
  window.addEventListener('resize', setTopH);

  const pad = $('#clickPad');
  pad.addEventListener('mousedown', onPadDown);
  document.addEventListener('mouseup', onPadUp);   // a press on the pad may be released outside it
  pad.addEventListener('contextmenu', (e) => e.preventDefault());
  $('#clickReset').addEventListener('click', resetClickTest);
  $('#scrollReset').addEventListener('click', resetScrollTest);
  $('#gestureRecord').addEventListener('click', recordGesture);

  setInterval(() => { stateHz = stateCount; stateCount = 0; }, 1000);

  if (new URLSearchParams(location.search).get('demo') === '1') {
    target.rows = demoTrials();
    renderResults(target.rows);
    $('#targetProgress').textContent = 'demo: 16 ensayos sintéticos';
  }

  connect();
  requestAnimationFrame(frame);
}

// Pure functions and a manual render, for checks from the console (rAF stops while the tab is hidden).
window.calib = { sequence, metrics, aggregate, suggest, demoTrials, jitterRMS, CONTROLS,
                 render() { renderMeters(); renderLive(); renderClickTest(); renderScrollTest(); renderBoardStats(); } };

init();
