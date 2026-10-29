// Muñeca izquierda o derecha, y los tres giros de apuntar con el reloj.
//
// En la muñeca izquierda el antebrazo (codo → mano) es el +x del reloj. En la derecha, puesto igual (botones
// hacia el codo), el reloj queda al revés: el antebrazo es −x. Con el antebrazo f bien puesto, las tres tasas
// significan lo mismo en las dos manos (g = arriba, ω = giroscopio):
//   yaw   = giro alrededor de la vertical, sin la parte que es roll (positivo: hacia la izquierda)
//   pitch = ω · (f × g)/|f × g|  (positivo: la mano sube)
//   roll  = ω · f                (positivo: horario visto desde el codo, atornillar)
// Con f al revés, pitch y roll cambian de signo: arriba sale abajo y atornillar sale desatornillar.
// La mano elegida se guarda en el navegador y la comparten todas las páginas.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else Object.assign(root, api);
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const KEY = 'gearstream.hand';
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = (a) => Math.hypot(a[0], a[1], a[2]);

  function loadHand() {
    try { return localStorage.getItem(KEY) === 'right' ? 'right' : 'left'; } catch { return 'left'; }
  }
  function saveHand(hand) {
    try { localStorage.setItem(KEY, hand); } catch { /* sin almacenamiento: solo dura esta visita */ }
  }
  const forearmOf = (hand) => [hand === 'right' ? -1 : 1, 0, 0];
  const handName = (hand) => (hand === 'right' ? 'muñeca derecha' : 'muñeca izquierda');

  class Wrist {
    constructor(hand) {
      this.hand = hand || loadHand();
      this.bias = [0, 0, 0];
    }
    get forearm() { return forearmOf(this.hand); }
    setHand(hand) { this.hand = hand === 'right' ? 'right' : 'left'; saveHand(this.hand); }
    toggleHand() { this.setHand(this.hand === 'right' ? 'left' : 'right'); return this.hand; }
    // raw: giroscopio (°/s), grav: gravedad del reloj (cualquier escala). Devuelve {yaw, pitch, roll} en °/s.
    rates(raw, grav) {
      const w = raw.map((x, i) => x - this.bias[i]);
      if (norm(w) < 2) for (let i = 0; i < 3; i++) this.bias[i] += 0.002 * (raw[i] - this.bias[i]);  // quieto: aprende el sesgo
      const gn = norm(grav);
      if (!(gn > 0)) return { yaw: 0, pitch: 0, roll: 0 };
      const g = grav.map((x) => x / gn), f = this.forearm;
      const roll = dot(w, f), gpf = dot(g, f);
      let yaw = (dot(w, g) - roll * gpf) / Math.max(1 - gpf * gpf, 0.09);
      const c = cross(f, g), cn = norm(c);
      let pitch = cn > 0.3 ? dot(w, c) / cn : 0;
      if (Math.hypot(yaw, pitch) < 0.6) { yaw = 0; pitch = 0; }
      return { yaw, pitch, roll };
    }
  }

  return { Wrist, loadHand, saveHand, forearmOf, handName };
});
