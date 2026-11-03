// Calibración del lienzo 2D de Dibuja. Barres con la mano el borde de tu pantalla (las cuatro esquinas) y de
// ese barrido, en grados de rumbo y elevación del antebrazo, sale una ganancia por eje (px por grado) y un
// centro, para que tu movimiento cómodo llene la ventana. Sin calibrar son 16 px por grado en los dos ejes:
// cruzar una pantalla de 1920 px pedía 120° de brazo, y un barrido natural de unos 45° llenaba un tercio.
// Con ganancias distintas en x e y un círculo sale ovalado: es el precio de que el barrido llene una pantalla
// ancha.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else Object.assign(root, api);
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DEFAULT_GAIN = { kx: 16, ky: 16 };       // px por grado, sin calibrar
  const MIN_SPAN = 8;                            // grados: con menos el barrido no dice nada
  const K_MIN = 4, K_MAX = 80;

  function quantile(a, q) {
    const s = [...a].sort((x, y) => x - y), i = (s.length - 1) * q, lo = Math.floor(i), hi = Math.min(lo + 1, s.length - 1);
    return s[lo] + (s[hi] - s[lo]) * (i - lo);
  }

  // pts: [[rumbo, elevación], ...] en grados durante el barrido; W, H: la ventana en px; margin: fracción libre en
  // cada borde. Los extremos son los percentiles 2 y 98, así un sobrepaso no achica el lienzo. Devuelve
  // {kx, ky, cx, cy, span} o null si en algún eje casi no hubo movimiento.
  function calibrate(pts, W, H, margin = 0.06) {
    if (pts.length < 20) return null;
    const ys = pts.map((p) => p[0]), ps = pts.map((p) => p[1]);
    const y0 = quantile(ys, 0.02), y1 = quantile(ys, 0.98), p0 = quantile(ps, 0.02), p1 = quantile(ps, 0.98);
    const sy = y1 - y0, sp = p1 - p0;
    if (sy < MIN_SPAN || sp < MIN_SPAN) return null;
    const clamp = (k) => Math.max(K_MIN, Math.min(K_MAX, k));
    return { kx: clamp(W * (1 - 2 * margin) / sy), ky: clamp(H * (1 - 2 * margin) / sp), cx: (y0 + y1) / 2, cy: (p0 + p1) / 2, span: [sy, sp] };
  }

  // rumbo y elevación (grados, ya recentrados) → px en la ventana; arriba positiva
  const toScreen = (yaw, pitch, gain, W, H) => [W / 2 + yaw * gain.kx, H / 2 - pitch * gain.ky];

  return { calibrate, toScreen, DEFAULT_GAIN };
});
