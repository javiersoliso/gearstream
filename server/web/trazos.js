// Los dibujos de Dibuja como lista de operaciones: se guardan solos en el servidor, se vuelven a abrir y se
// reproducen como timelapse. Lo comparten dibuja.js y el visor (visor.html, también el exportado).
//
// Un dibujo es una operación por línea (JSON Lines), en el orden en que pasaron; t es ms desde el inicio:
//   {k:'h', v:1, start, hand, view:[ancho, alto]}     cabecera
//   {k:'s', id, m, c, t}                              empieza el trazo id en el modo m (1, 2 o 3) con color c
//                                                     (raw: true si sus puntos 3D ya son las bolitas, sin rellenar)
//   {k:'p', id, pts:[[x, y, t], ...]}                 puntos del trazo (en 3D [x, y, z, t])
//   {k:'z', m, t}                                     deshacer el último trazo del modo m
//   {k:'c', t}                                        borrar todo
// 2D y 1D en píxeles de la ventana de la cabecera; 3D en metros. En 3D los puntos se rellenan cada 2 cm con
// bolitas (como al dibujar), así que reproducir da exactamente el mismo dibujo.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else Object.assign(root, api);
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const STEP3 = 0.02, MAXFILL = 40;
  const ptTime = (p) => p[p.length - 1];

  // texto guardado (JSON Lines) o un rescate de la versión vieja → lista de operaciones
  function parseDrawing(text) {
    text = String(text || '').trim();
    if (!text) return [];
    if (text[0] === '{' && text.indexOf('\n') < 0) {
      const one = JSON.parse(text);
      if (one.format === 'gearstream-dibujo-rescate') return fromRescue(one);
      return [one];
    }
    return text.split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));
  }

  // rescate: las bolitas en orden (ya rellenas) y los trazos 2D/1D de la pestaña vieja, sin tiempos
  function fromRescue(r) {
    const ops = [{ k: 'h', v: 1, rescued: true, view: r.view || null }];
    let id = 0, t = 0, cur = null, prev = null;
    for (const [x, y, z, c] of r.blobs || []) {
      const far = !prev || Math.hypot(x - prev[0], y - prev[1], z - prev[2]) > 3 * STEP3;
      if (!cur || far || c !== cur.c) {
        t += 300;
        cur = { k: 's', id: ++id, m: 3, c: c || '#ece9e1', t, raw: true };
        ops.push(cur, { k: 'p', id, pts: [] });
      }
      t += 4;
      ops[ops.length - 1].pts.push([x, y, z, t]);
      prev = [x, y, z];
    }
    for (const s of r.strokes2 || []) {
      t += 300;
      ops.push({ k: 's', id: ++id, m: s.mode, c: s.color, t });
      ops.push({ k: 'p', id, pts: (s.pts || []).map(([x, y]) => [x, y, (t += 8)]) });
    }
    return ops;
  }

  const toJSONL = (ops) => ops.map((o) => JSON.stringify(o)).join('\n') + '\n';

  // el estado visible tras aplicar operaciones. hooks.blob(pos, color) por cada bolita 3D nueva y
  // hooks.truncate3(n) cuando quedan solo las n primeras (deshacer, borrar).
  class Drawing {
    constructor(hooks) { this.hooks = hooks || {}; this.reset(); }
    reset() {
      this.s2 = []; this.s3 = []; this.byId = new Map(); this.blobs = 0;
      if (this.hooks.truncate3) this.hooks.truncate3(0);
    }
    apply(op) {
      if (op.k === 's') {
        const s = { id: op.id, mode: op.m, color: op.c, pts: [], start: this.blobs, last: null, raw: !!op.raw };
        (op.m === 3 ? this.s3 : this.s2).push(s);
        this.byId.set(op.id, s);
      } else if (op.k === 'p') {
        const s = this.byId.get(op.id);
        if (s) for (const p of op.pts) this.point(s, p);
      } else if (op.k === 'z') {
        const list = op.m === 3 ? this.s3 : this.s2;
        for (let i = list.length - 1; i >= 0; i--) {
          if (list[i].mode !== op.m) continue;
          const [s] = list.splice(i, 1);
          this.byId.delete(s.id);
          if (op.m === 3) { this.blobs = s.start; if (this.hooks.truncate3) this.hooks.truncate3(this.blobs); }
          break;
        }
      } else if (op.k === 'c') this.reset();
    }
    point(s, p) {
      if (s.mode !== 3) { s.pts.push([p[0], p[1]]); return; }
      const q = [p[0], p[1], p[2]];
      if (!s.last || s.raw) this.blob(s, q);
      else {
        const a = s.last, n = Math.min(MAXFILL, Math.ceil(Math.hypot(q[0] - a[0], q[1] - a[1], q[2] - a[2]) / STEP3));
        for (let k = 1; k <= n; k++) this.blob(s, [a[0] + (q[0] - a[0]) * k / n, a[1] + (q[1] - a[1]) * k / n, a[2] + (q[2] - a[2]) * k / n]);
      }
      s.last = q;
    }
    blob(s, q) {
      this.blobs++;
      s.pts.push(q);
      if (this.hooks.blob) this.hooks.blob(q, s.color);
    }
  }

  // para reproducir: cada operación (y cada punto por separado) con su momento en ms de reproducción;
  // las pausas largas se acortan a maxGap para que el timelapse no se quede quieto
  function timeline(ops, maxGap) {
    maxGap = maxGap === undefined ? 400 : maxGap;
    const out = [];
    let at = 0, last = null;
    const step = (t) => {
      if (typeof t === 'number' && last !== null) at += Math.max(0, Math.min(maxGap, t - last));
      if (typeof t === 'number') last = t;
      return at;
    };
    for (const op of ops) {
      if (op.k === 'p') for (const p of op.pts) out.push({ at: step(ptTime(p)), op: { k: 'p', id: op.id, pts: [p] } });
      else if (op.k !== 'h') out.push({ at: step(op.t), op });
    }
    return out;
  }

  // los modos que tienen algo dibujado al final
  function modesOf(ops) {
    const d = new Drawing();
    for (const op of ops) d.apply(op);
    const m = new Set();
    for (const s of d.s2) if (s.pts.length) m.add(s.mode);
    if (d.blobs) m.add(3);
    return [...m].sort();
  }

  return { parseDrawing, toJSONL, Drawing, timeline, modesOf };
});
