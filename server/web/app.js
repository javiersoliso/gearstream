'use strict';

// ---------- Metadata per source ----------

const LABELS = {
  HRM: 'Ritmo cardiaco', HRM_RAW: 'PPG crudo', ACCELERATION: 'Acelerómetro', GYROSCOPE: 'Giroscopio',
  LINEAR_ACCELERATION: 'Aceleración lineal', GRAVITY: 'Gravedad', GYROSCOPE_ROTATION_VECTOR: 'Vector de rotación',
  GYROSCOPE_UNCALIBRATED: 'Giroscopio sin calibrar', MAGNETIC: 'Magnetómetro', MAGNETIC_UNCALIBRATED: 'Magnetómetro sin calibrar',
  ORIENTATION: 'Orientación', MOTION: 'Movimiento (W3C)', PRESSURE: 'Barómetro', LIGHT: 'Luz ambiental',
  PROXIMITY: 'Proximidad', ULTRAVIOLET: 'Ultravioleta', PEDOMETER: 'Podómetro', WRIST_UP: 'Muñeca arriba',
  SLEEP_MONITOR: 'Sueño', SLEEP_DETECTOR: 'Detector de sueño', STRESS_MONITOR: 'Estrés', GPS: 'GPS',
  BATTERY: 'Batería', BEZEL: 'Bisel',
};
const UNITS = {
  HRM: 'lpm', ACCELERATION: 'm/s²', LINEAR_ACCELERATION: 'm/s²', GRAVITY: 'm/s²', GYROSCOPE: '°/s',
  GYROSCOPE_UNCALIBRATED: '°/s', MAGNETIC: 'µT', MAGNETIC_UNCALIBRATED: 'µT', ORIENTATION: '°',
  PRESSURE: 'hPa', LIGHT: 'lux', BATTERY: '%',
};
const ORDER = Object.keys(LABELS);
const XYZ = ['x', 'y', 'z'];
// Fields drawn on the chart (one y-axis per card, so only fields sharing a scale).
const CHART_FIELDS = {
  ACCELERATION: XYZ, LINEAR_ACCELERATION: XYZ, GRAVITY: XYZ, GYROSCOPE: XYZ, GYROSCOPE_UNCALIBRATED: XYZ,
  MAGNETIC: XYZ, MAGNETIC_UNCALIBRATED: XYZ, MOTION: XYZ, GYROSCOPE_ROTATION_VECTOR: ['x', 'y', 'z', 'w'],
  ORIENTATION: ['alpha', 'beta', 'gamma'], HRM: ['heartRate'], HRM_RAW: ['lightType', 'lightIntensity'],
  PRESSURE: ['pressure'], LIGHT: ['lightLevel'], ULTRAVIOLET: ['ultravioletLevel'], BATTERY: ['level'],
  PROXIMITY: ['proximityState'], STRESS_MONITOR: ['stressScore'], PEDOMETER: ['cumulativeTotalStepCount'],
  GPS: [], WRIST_UP: [], BEZEL: [], SLEEP_MONITOR: [], SLEEP_DETECTOR: [],
};

// Slow sources: the last value holds until "now" instead of ending at the last sample.
const HOLD = new Set(['HRM', 'BATTERY', 'PEDOMETER', 'PRESSURE', 'LIGHT', 'PROXIMITY', 'ULTRAVIOLET', 'STRESS_MONITOR']);
// Angles that wrap 360 -> 0: break the line instead of drawing a vertical jump.
const WRAPS = new Set(['alpha']);

function chartPoints(name, v) {
  if (name === 'HRM_RAW') return { [v.lightType || 'intensidad']: v.lightIntensity };
  if (name === 'HRM') return { heartRate: v.heartRate > 0 ? v.heartRate : NaN };  // <=0 = sin contacto
  if (name === 'BATTERY') return { level: v.level * 100 };  // Tizen da 0..1
  let fields = CHART_FIELDS[name];
  if (!fields) {
    const first = Object.keys(v).find((k) => typeof v[k] === 'number' && !/time/i.test(k));
    fields = first ? [first] : [];
  }
  const out = {};
  for (const f of fields) if (typeof v[f] === 'number') out[f] = v[f];
  return out;
}

// ---------- State ----------

const MAX_WINDOW_MS = 30000;
// What phones cannot keep up with is rasterising the strokes (measured ~90 ms/frame at 3x density
// with round joins), so: density capped, cards drawn only while on screen, and only when data changed.
const DPR = Math.min(window.devicePixelRatio || 1, 1.5);
const sources = new Map();
const cardSource = new WeakMap();  // card element -> source, for the visibility observer
const visibility = new IntersectionObserver((entries) => {
  for (const e of entries) {
    const s = cardSource.get(e.target);
    if (s) s.visible = e.isIntersecting;
  }
  dirty = true;
});
let latestT = 0;          // watch clock (ms) of the newest sample
let pausedT = null;
let windowMs = 10000;
let serverUp = false;
let watchUp = false;
let hello = null;
let watchUrls = [];
let totalHzCount = 0;
let totalHz = 0;
let layoutDirty = true;
let dirty = true;         // charts need a redraw (new data, hover, window, pause...)
let lastBatchT = 0;       // bridge clock when the newest batch was sent (exact leg if same machine)
let lastMsgAt = 0;        // performance.now() of the last data message, for the burst meter
let maxGapMs = 0, maxGapShown = 0;
let maxBatch = 0, maxBatchShown = 0;

const $ = (sel, el = document) => el.querySelector(sel);

function getSource(name) {
  let s = sources.get(name);
  if (!s) {
    s = { name, state: 'waiting', detail: '', hw: null, count: 0, hzCount: 0, hz: 0, last: null, lastT: 0,
          series: new Map(), el: null, hoverX: null, visible: true };
    sources.set(name, s);
    layoutDirty = true;
  }
  return s;
}

function addSample(name, t, v) {
  const s = getSource(name);
  s.count++;
  s.hzCount++;
  totalHzCount++;
  s.last = v;
  s.lastT = t;
  if (s.state !== 'on') { s.state = 'on'; layoutDirty = true; }
  if (t > latestT) latestT = t;
  if (!v || typeof v !== 'object') return;
  const pts = chartPoints(name, v);
  for (const key in pts) {
    let ser = s.series.get(key);
    if (!ser) {
      ser = { t: [], v: [], slot: Math.min(s.series.size + 1, 8) };
      s.series.set(key, ser);
      if (s.el) buildLegend(s);
    }
    ser.t.push(t);
    ser.v.push(pts[key]);
  }
}

function handle(msg) {
  switch (msg.type) {
    case 'server': watchUrls = msg.watchUrls || []; renderEmpty(); break;
    case 'watch': watchUp = msg.connected; break;
    case 'hello':
      // New watch session: its clock may differ, so drop old points.
      hello = msg;
      latestT = 0;
      for (const s of sources.values()) for (const ser of s.series.values()) { ser.t.length = 0; ser.v.length = 0; }
      break;
    case 'status': {
      const s = getSource(msg.source);
      s.state = msg.state;
      s.detail = msg.detail || '';
      if (msg.hw) s.hw = msg.hw;
      layoutDirty = true;
      break;
    }
    case 'data': {
      for (const [name, t, v] of msg.samples) addSample(name, t, v);
      if (msg.t) lastBatchT = msg.t;
      const now = performance.now();
      if (lastMsgAt) maxGapMs = Math.max(maxGapMs, now - lastMsgAt);
      lastMsgAt = now;
      maxBatch = Math.max(maxBatch, msg.samples.length);
      dirty = true;
      break;
    }
  }
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ui`);
  ws.onopen = () => { serverUp = true; };
  ws.onclose = () => { serverUp = false; watchUp = false; setTimeout(connect, 1000); };
  ws.onmessage = (e) => handle(JSON.parse(e.data));
}

// ---------- Formatting ----------

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

function color(slot) { return `var(--series-${slot})`; }

// ---------- Layout ----------

function isUnavailable(s) { return (s.state === 'error' || s.state === 'unsupported') && !s.count; }

function buildCard(s) {
  const card = document.createElement('article');
  card.className = 'card';
  card.innerHTML = `
    <header><h2></h2><span class="sub"></span><span class="hz"></span></header>
    ${s.name === 'HRM' ? '<div class="hero"><span></span><small>lpm</small></div>' : ''}
    <ul class="legend"></ul>
    <div class="plot"><canvas></canvas><div class="tip" hidden></div></div>
    <dl class="fields"></dl>
    <div class="state"></div>`;
  $('h2', card).textContent = LABELS[s.name] || s.name;
  $('.sub', card).textContent = s.name + (UNITS[s.name] ? ` · ${UNITS[s.name]}` : '');
  const canvas = $('canvas', card);
  canvas.addEventListener('mousemove', (e) => { s.hoverX = e.offsetX; dirty = true; });
  canvas.addEventListener('mouseleave', () => { s.hoverX = null; dirty = true; });
  s.el = { card, canvas, ctx: canvas.getContext('2d'), plot: $('.plot', card), tip: $('.tip', card),
           legend: $('.legend', card), fields: $('.fields', card), hz: $('.hz', card), state: $('.state', card),
           hero: $('.hero span', card) };
  cardSource.set(card, s);
  visibility.observe(card);
  buildLegend(s);
}

function buildLegend(s) {
  const { legend } = s.el;
  legend.innerHTML = '';
  for (const [key, ser] of s.series) {
    const li = document.createElement('li');
    li.innerHTML = `<i style="background:${color(ser.slot)}"></i><span></span><b></b>`;
    li.children[1].textContent = key;
    ser.valueEl = li.children[2];
    legend.appendChild(li);
  }
  s.el.plot.hidden = s.series.size === 0;
}

function relayout() {
  layoutDirty = false;
  const grid = $('#grid');
  const sorted = [...sources.values()].sort((a, b) => {
    const ia = ORDER.indexOf(a.name), ib = ORDER.indexOf(b.name);
    return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib) || a.name.localeCompare(b.name);
  });
  const unavailable = [];
  for (const s of sorted) {
    if (isUnavailable(s)) {
      if (s.el) s.el.card.remove();
      unavailable.push(s);
      continue;
    }
    if (!s.el) buildCard(s);
    grid.appendChild(s.el.card);  // appendChild moves existing nodes into sorted order
  }
  const list = $('#unavailableList');
  list.innerHTML = '';
  for (const s of unavailable) {
    const li = document.createElement('li');
    li.textContent = LABELS[s.name] || s.name;
    const detail = document.createElement('span');
    detail.textContent = `${s.name} · ${s.state === 'unsupported' ? 'no soportado' : s.detail || 'error'}`;
    li.appendChild(detail);
    list.appendChild(li);
  }
  $('#unavailable').hidden = unavailable.length === 0;
  renderEmpty();
}

function renderEmpty() {
  const anyData = [...sources.values()].some((s) => s.count > 0);
  $('#empty').hidden = anyData;
  const ul = $('#urls');
  ul.innerHTML = '';
  for (const url of watchUrls) {
    const li = document.createElement('li');
    li.textContent = url;
    ul.appendChild(li);
  }
}

// ---------- Text (≈7 Hz) ----------

function renderText() {
  if (layoutDirty) relayout();

  const conn = $('#conn');
  conn.className = 'pill ' + (!serverUp ? 'critical' : watchUp ? 'good' : '');
  conn.textContent = !serverUp ? 'Servidor desconectado' : watchUp ? 'Reloj conectado' : 'Esperando reloj';
  const d = hello && hello.device;
  $('#device').textContent = d ? [d.model_name, d['platform.version'] && `Tizen ${d['platform.version']}`, hello.app]
    .filter(Boolean).join(' · ') : '';
  $('#total').textContent = `${totalHz} muestras/s`;
  // Shown signed on purpose: a negative value means the clock anchoring is off, which is worth seeing.
  const fmtMs = (ms) => Math.abs(ms) < 2000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
  let lagText = '';
  if (latestT && watchUp && pausedT === null) {
    lagText = `retraso ${fmtMs(Date.now() - latestT)}`;
    if (lastBatchT) lagText += ` (desde el puente ${fmtMs(Date.now() - lastBatchT)})`;
    if (maxGapShown) lagText += ` · ráfaga máx ${Math.round(maxGapShown)} ms / ${maxBatchShown} muestras`;
  }
  $('#lag').textContent = lagText;
  if ($('#empty').hidden === false && [...sources.values()].some((s) => s.count > 0)) renderEmpty();

  for (const s of sources.values()) {
    if (!s.el) continue;
    s.el.hz.textContent = s.count ? `${s.hz} Hz` : '';
    for (const ser of s.series.values()) {
      if (ser.valueEl) ser.valueEl.textContent = fmt(ser.v[ser.v.length - 1]);
    }
    if (s.el.hero) {
      const hr = s.last && s.last.heartRate;
      s.el.hero.textContent = hr > 0 ? hr : s.last ? 'sin contacto' : '—';
    }
    // Everything not already on the chart goes to the field list.
    const charted = new Set(CHART_FIELDS[s.name] || [...s.series.keys()]);
    const rows = [];
    if (s.last && typeof s.last === 'object') {
      for (const [k, v] of Object.entries(s.last)) if (!charted.has(k)) rows.push([k, fmt(v)]);
    }
    if (!s.series.size && s.count) {
      rows.push(['eventos', String(s.count)]);
      rows.push(['último', `hace ${Math.max(0, ((latestT - s.lastT) / 1000)).toFixed(1)} s`]);
    }
    const html = rows.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`).join('');
    if (s.el.fields.innerHTML !== html) s.el.fields.innerHTML = html;
    s.el.state.textContent = s.count ? '' : s.state === 'error' ? `Error: ${s.detail}` : 'Esperando datos…';
  }
}

function escapeHtml(str) {
  return str.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

// ---------- Charts ----------

let palette = {};
function readPalette() {
  const cs = getComputedStyle(document.documentElement);
  palette = { surface: cs.getPropertyValue('--surface-1').trim(), grid: cs.getPropertyValue('--grid').trim(),
              axis: cs.getPropertyValue('--axis').trim(), muted: cs.getPropertyValue('--muted').trim() };
  for (let i = 1; i <= 8; i++) palette[i] = cs.getPropertyValue(`--series-${i}`).trim();
}

function lowerBound(arr, x) {
  let lo = 0, hi = arr.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (arr[mid] < x) lo = mid + 1; else hi = mid; }
  return lo;
}

function niceStep(range, count) {
  const raw = range / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const n = raw / mag;
  return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag;
}

const PAD = { l: 48, r: 8, t: 6, b: 18 };

function drawChart(s, t1) {
  const { canvas, ctx, tip } = s.el;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  if (canvas.width !== Math.round(w * DPR) || canvas.height !== Math.round(h * DPR)) {
    canvas.width = Math.round(w * DPR);
    canvas.height = Math.round(h * DPR);
  }
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const t0 = t1 - windowMs;
  const pw = w - PAD.l - PAD.r, ph = h - PAD.t - PAD.b;
  let lo = Infinity, hi = -Infinity;
  const hold = HOLD.has(s.name);
  for (const ser of s.series.values()) {
    // One point before the window so the line enters from the left edge.
    ser.i0 = Math.max(0, lowerBound(ser.t, t0) - 1);
    ser.i1 = lowerBound(ser.t, t1 + 1);
    for (let i = ser.i0; i < ser.i1; i++) {
      const v = ser.v[i];
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  if (!Number.isFinite(lo)) { tip.hidden = true; return; }
  if (hi - lo < 1e-9) { lo -= 1; hi += 1; }
  const span = hi - lo;
  lo -= span * 0.08;
  hi += span * 0.08;
  const X = (t) => PAD.l + ((t - t0) / windowMs) * pw;
  const Y = (v) => PAD.t + (1 - (v - lo) / (hi - lo)) * ph;

  // Grid + y ticks
  ctx.font = '11px system-ui, -apple-system, "Segoe UI", sans-serif';
  ctx.fillStyle = palette.muted;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  ctx.lineWidth = 1;
  const step = niceStep(hi - lo, 3);
  const decimals = Math.max(0, -Math.floor(Math.log10(step)));
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    const y = Math.round(Y(v)) + 0.5;
    ctx.strokeStyle = palette.grid;
    ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(w - PAD.r, y); ctx.stroke();
    ctx.fillText((Math.abs(v) < step / 1e6 ? 0 : v).toFixed(decimals), PAD.l - 6, y);
  }
  ctx.strokeStyle = palette.axis;
  ctx.beginPath(); ctx.moveTo(PAD.l, PAD.t + ph + 0.5); ctx.lineTo(w - PAD.r, PAD.t + ph + 0.5); ctx.stroke();
  ctx.textBaseline = 'top';
  ctx.textAlign = 'left';
  ctx.fillText(`−${windowMs / 1000} s`, PAD.l, PAD.t + ph + 4);
  ctx.textAlign = 'right';
  ctx.fillText('ahora', w - PAD.r, PAD.t + ph + 4);

  // Lines (min/max per pixel column when there are more points than pixels)
  ctx.save();
  ctx.beginPath();
  ctx.rect(PAD.l, 0, pw, h);
  ctx.clip();
  // Bevel joins and butt caps rasterise ~25% cheaper than round ones at no visible cost at 1.5 px.
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'bevel';
  ctx.lineCap = 'butt';
  for (const [key, ser] of s.series) {
    ctx.strokeStyle = palette[ser.slot];
    ctx.beginPath();
    let pen = false, col = -1, cmin = 0, cmax = 0, imin = 0, imax = 0, prev = NaN;
    const dense = ser.i1 - ser.i0 > pw * 2;
    const wraps = WRAPS.has(key);
    // Dense mode: one pixel column = its min and max, in the order they happened (2 segments, not 3).
    const flushCol = () => {
      if (imin <= imax) { ctx.lineTo(col, cmin); ctx.lineTo(col, cmax); }
      else { ctx.lineTo(col, cmax); ctx.lineTo(col, cmin); }
    };
    for (let i = ser.i0; i < ser.i1; i++) {
      const v = ser.v[i];
      const gap = !Number.isFinite(v) || (wraps && Math.abs(v - prev) > 180);
      if (gap) {
        if (dense && pen && col >= 0) flushCol();
        pen = false; col = -1;
        if (!Number.isFinite(v)) continue;
      }
      prev = v;
      const x = X(ser.t[i]), y = Y(v);
      if (dense) {
        const c = Math.floor(x);
        if (c === col) {
          if (y < cmin) { cmin = y; imin = i; }
          if (y > cmax) { cmax = y; imax = i; }
          continue;
        }
        if (pen) flushCol(); else { ctx.moveTo(x, y); pen = true; }
        col = c; cmin = cmax = y; imin = imax = i;
        continue;
      }
      if (pen) ctx.lineTo(x, y); else ctx.moveTo(x, y);
      pen = true;
    }
    if (dense && pen && col >= 0) flushCol();
    if (hold && pen) ctx.lineTo(X(t1), Y(prev));
    ctx.stroke();
  }
  ctx.restore();

  // Hover: crosshair + nearest point per series
  const hx = s.hoverX;
  if (hx === null || hx < PAD.l || hx > w - PAD.r) { tip.hidden = true; return; }
  const th = t0 + ((hx - PAD.l) / pw) * windowMs;
  ctx.strokeStyle = palette.axis;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(Math.round(hx) + 0.5, PAD.t); ctx.lineTo(Math.round(hx) + 0.5, PAD.t + ph); ctx.stroke();
  let rows = '';
  for (const [key, ser] of s.series) {
    let i = lowerBound(ser.t, th);
    if (i >= ser.i1 || (i > ser.i0 && th - ser.t[i - 1] < ser.t[i] - th)) i--;
    if (i < ser.i0 || i >= ser.i1) continue;
    const v = ser.v[i];
    if (Number.isFinite(v)) {
      ctx.beginPath();
      ctx.arc(X(ser.t[i]), Y(v), 4, 0, Math.PI * 2);
      ctx.fillStyle = palette[ser.slot];
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = palette.surface;
      ctx.stroke();
    }
    rows += `<div><i style="background:${color(ser.slot)}"></i>${escapeHtml(key)} <b>${fmt(v)}</b></div>`;
  }
  tip.innerHTML = `<div class="muted">${((th - t1) / 1000).toFixed(2)} s</div>${rows}`;
  tip.hidden = false;
  const left = hx > w / 2 ? hx - tip.offsetWidth - 12 : hx + 12;
  tip.style.left = `${Math.max(0, left)}px`;
}

function trim() {
  const cutoff = (pausedT ?? latestT) - MAX_WINDOW_MS - 2000;
  for (const s of sources.values()) {
    for (const ser of s.series.values()) {
      const i = lowerBound(ser.t, cutoff);
      if (i > 2000) { ser.t.splice(0, i); ser.v.splice(0, i); }
    }
  }
}

let lastDraw = 0;
function frame(now) {
  // Redraw only when something changed, at most ~30 times a second: batches arrive 50x/s and the
  // raster cost per draw is what a phone cannot afford at 60 fps.
  if (dirty && now - lastDraw >= 33) {
    dirty = false;
    lastDraw = now;
    const t1 = pausedT ?? latestT;
    for (const s of sources.values()) {
      if (s.el && s.series.size && s.visible && s.el.card.isConnected) drawChart(s, t1);
    }
  }
  requestAnimationFrame(frame);
}

// ---------- Controls ----------

function setPaused(on) {
  pausedT = on ? latestT : null;
  dirty = true;
  const btn = $('#pause');
  btn.textContent = on ? 'Reanudar' : 'Pausar';
  btn.setAttribute('aria-pressed', String(on));
}

function init() {
  readPalette();
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { readPalette(); dirty = true; });
  window.addEventListener('resize', () => { dirty = true; });

  for (const btn of document.querySelectorAll('.seg button')) {
    btn.addEventListener('click', () => {
      windowMs = Number(btn.dataset.win) * 1000;
      dirty = true;
      for (const b of document.querySelectorAll('.seg button')) b.setAttribute('aria-pressed', String(b === btn));
    });
  }
  $('#pause').addEventListener('click', () => setPaused(pausedT === null));
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && e.target === document.body) { e.preventDefault(); setPaused(pausedT === null); }
  });

  // Rates use the watch clock: browser timers get throttled and would under-count.
  let rateT = 0;
  setInterval(() => {
    const dt = latestT - rateT;
    if (rateT && dt > 0) {
      totalHz = Math.round((totalHzCount * 1000) / dt);
      for (const s of sources.values()) s.hz = Math.round((s.hzCount * 1000) / dt);
    } else if (rateT && dt <= 0) {
      totalHz = 0;
      for (const s of sources.values()) s.hz = 0;
    }
    rateT = latestT;
    totalHzCount = 0;
    for (const s of sources.values()) s.hzCount = 0;
    maxGapShown = maxGapMs; maxBatchShown = maxBatch;
    maxGapMs = 0; maxBatch = 0;
    trim();
  }, 1000);
  setInterval(renderText, 150);

  connect();
  requestAnimationFrame(frame);
}

init();
