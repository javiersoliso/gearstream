// Calibración del clic por giro de muñeca: de tus giros salen tus umbrales.
//
// El ratón aéreo (tools/air_mouse.py, FlickClicker) corta el giro del antebrazo (roll) en lóbulos: un tramo
// con |roll| > 60 °/s hasta que baja de 25 °/s o cambia de sentido. Durante la calibración manda cada lóbulo
// con lo que midió: pico (°/s), duración (ms), ángulo (°), sentido, cuánto se movió el cursor en proporción
// al pico (rho/pico) y cuánto estuvo quieta la muñeca antes (ms). Aquí se usan dos tandas:
//   fondo: apuntando normal, sin clics. Lo que NO debe ser un clic.
//   giros: un giro por pitido. Lo que SÍ debe serlo; en cada ventana el lóbulo más fuerte es tu giro y el
//          de sentido contrario que le sigue es la vuelta (que el ratón se traga).
// Los umbrales quedan entre las dos tandas, con margen hacia tus giros: el umbral de pico por debajo de tu
// giro más flojo, la duración, el ángulo y el movimiento permitidos por encima de lo que hiciste, y el
// sentido el que usaste (si siempre fue el mismo). Al final se comprueba: cuántos de tus giros pasarían y
// cuántos lóbulos del fondo harían un clic falso.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else Object.assign(root, api);
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const MIN_FLICK = 120;                 // °/s: un pico menor no es un giro de clic, es un movimiento
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const median = (a) => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

  // ¿haría clic este lóbulo con estos ajustes? (las mismas puertas que FlickClicker._decide)
  function passes(l, p) {
    return l.peak >= p.flick_thr && l.ms <= p.flick_max_ms && Math.abs(l.deg) >= p.flick_deg_min && Math.abs(l.deg) <= p.flick_deg_max
      && l.rho_ratio <= p.flick_dom && l.quiet_ms >= p.flick_quiet_ms && (p.flick_dir === 'any' || l.sign === (p.flick_dir === 'cw' ? 1 : -1));
  }

  // rounds: por cada pitido, los lóbulos de su ventana en orden; background: los lóbulos del fondo
  function fitFlick(rounds, background) {
    const mains = [], warnings = [];
    for (const lobes of rounds) {
      if (!lobes.length) continue;
      const main = lobes.reduce((a, b) => (b.peak > a.peak ? b : a));
      if (main.peak >= MIN_FLICK) mains.push(main);
    }
    if (mains.length < Math.max(4, Math.ceil(rounds.length * 0.6))) {
      return { ok: false, mains, warnings: [`Vi ${mains.length} giros en ${rounds.length} pitidos: gira más rápido, un cuarto de vuelta y de vuelta.`] };
    }
    const pos = mains.filter((m) => m.sign > 0).length;
    const dir = pos >= 0.8 * mains.length ? 'cw' : pos <= 0.2 * mains.length ? 'ccw' : 'any';
    if (dir === 'any') warnings.push('Giraste a veces en un sentido y a veces en el otro: aceptaré los dos.');
    const peaks = mains.map((m) => m.peak), lo = Math.min(...peaks);
    const p = {
      flick_dir: dir,
      flick_max_ms: clamp(Math.ceil(1.4 * Math.max(...mains.map((m) => m.ms)) / 10) * 10, 100, 500),
      flick_dom: clamp(Math.round((1.3 * Math.max(...mains.map((m) => m.rho_ratio)) + 0.05) * 100) / 100, 0.3, 0.9),
      flick_deg_min: clamp(Math.floor(0.5 * Math.min(...mains.map((m) => Math.abs(m.deg)))), 3, 40),
      flick_deg_max: clamp(Math.ceil(1.5 * Math.max(...mains.map((m) => Math.abs(m.deg)))), 30, 180),
      flick_quiet_ms: clamp(Math.round(Math.min(120, 0.7 * Math.min(...mains.map((m) => m.quiet_ms))) / 10) * 10, 50, 120),
    };
    // el umbral de pico: bajo tu giro más flojo, y sobre lo más fuerte del fondo que pasaría las otras puertas
    let thr = Math.min(0.6 * median(peaks), 0.85 * lo);
    const rivals = background.filter((l) => passes(l, { ...p, flick_thr: 0 })).map((l) => l.peak);
    const bgMax = rivals.length ? Math.max(...rivals) : 0;
    if (bgMax * 1.15 > thr) {
      if (bgMax * 1.15 <= 0.9 * lo) thr = bgMax * 1.15;
      else {
        thr = (bgMax + lo) / 2;
        warnings.push(`Apuntando hiciste giros de ${Math.round(bgMax)} °/s y tu clic más flojo fue de ${Math.round(lo)} °/s: `
          + 'gira más rápido o apunta más suave, si no habrá clics falsos.');
      }
    }
    p.flick_thr = Math.round(clamp(thr, 80, 800));
    const detected = mains.filter((m) => passes(m, p)).length;
    const falsos = background.filter((l) => passes(l, p)).length;
    return { ok: true, params: p, detected, total: mains.length, beeps: rounds.length, falsos, bgCount: background.length, bgMax, mains, warnings };
  }

  return { fitFlick, passesFlick: passes, MIN_FLICK };
});
