// Giros rápidos del antebrazo ("atornillar" y "desatornillar") y el tempo de esos giros.
//
// El antebrazo es el eje x del reloj, así que girar la muñeca como con un destornillador es ω_x, la
// componente x del giroscopio. Mirando desde el codo hacia los dedos (como miras un tornillo), ω_x > 0
// es sentido horario: atornillar. Un giro rápido es un pico de |ω_x| que domina a los otros dos ejes
// (si el brazo entero se mueve, ω_y y ω_z también crecen y no cuenta). El umbral se adapta a tus giros.
// El tempo es el intervalo mediano entre giros seguidos: BPM = 60000 / intervalo.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else Object.assign(root, api);
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DEFAULTS = {
    minOn: 70,          // °/s: umbral mínimo para empezar un giro
    rel: 0.35,          // el umbral sube a esta fracción de tus picos recientes
    dominance: 1.3,     // en el pico, |ω_x| debe superar a |ω_y| y |ω_z| por este factor
    refractory: 90,     // ms tras un giro sin aceptar otro
    tempoN: 6,          // intervalos para el tempo
    tempoReset: 2500,   // ms sin giros: el tempo se reinicia
    sign: 1,            // −1 si el reloj está al revés
  };

  class FlickDetector {
    constructor(opts = {}) {
      this.o = Object.assign({}, DEFAULTS, opts);
      this.cur = null;          // giro en curso
      this.peaks = [];          // picos recientes para el umbral adaptativo
      this.last = -Infinity;    // instante del último giro
      this.beats = [];          // instantes de los giros (para el tempo)
      this.angle = 0;           // giro acumulado (grados): la rosca del tornillo
      this.lastT = null;
    }

    threshold() {
      if (!this.peaks.length) return this.o.minOn;
      const s = [...this.peaks].sort((a, b) => a - b);
      return Math.max(this.o.minOn, this.o.rel * s[Math.floor(s.length / 2)]);
    }

    // t en ms, w = [ωx, ωy, ωz] en °/s ya sin sesgo. Devuelve un giro {t, dir: +1|−1, peak} al terminar uno.
    // live = false para muestras atrasadas (una ráfaga tras una pausa del Wi-Fi del reloj): cuentan para el
    // ángulo, pero no dan giros ni tempo, que llegarían tarde.
    update(t, w, live = true) {
      const wx = this.o.sign * w[0];
      if (this.lastT !== null) {
        const dt = Math.min(0.1, Math.max(0, (t - this.lastT) / 1000));
        this.angle += wx * dt;
      }
      this.lastT = t;
      const ax = Math.abs(wx), other = Math.max(Math.abs(w[1]), Math.abs(w[2]));
      const thr = this.threshold();
      if (!this.cur) {
        if (ax > thr && t - this.last > this.o.refractory) this.cur = { t0: t, peak: ax, tPeak: t, dir: Math.sign(wx), other };
        return null;
      }
      if (Math.sign(wx) === this.cur.dir && ax > this.cur.peak) { this.cur.peak = ax; this.cur.tPeak = t; this.cur.other = other; }
      if (ax < thr * 0.5 || Math.sign(wx) !== this.cur.dir || t - this.cur.t0 > 600) {
        const c = this.cur;
        this.cur = null;
        if (c.peak < this.o.dominance * c.other) return null;          // se movió todo el brazo, no fue la muñeca
        if (!live) return null;
        this.last = c.tPeak;
        this.peaks.push(c.peak); if (this.peaks.length > 12) this.peaks.shift();
        if (this.beats.length && c.tPeak - this.beats[this.beats.length - 1] > this.o.tempoReset) this.beats = [];
        this.beats.push(c.tPeak); if (this.beats.length > this.o.tempoN + 1) this.beats.shift();
        return { t: c.tPeak, dir: c.dir, peak: c.peak };
      }
      return null;
    }

    // tempo en giros por minuto (cada giro, en cualquier sentido, es un pulso) o null
    tempo(now) {
      const b = this.beats;
      if (b.length < 3 || (now !== undefined && now - b[b.length - 1] > this.o.tempoReset)) return null;
      const iv = b.slice(1).map((x, i) => x - b[i]).sort((x, y) => x - y);
      return 60000 / iv[Math.floor(iv.length / 2)];
    }
  }

  return { FlickDetector, FLICK_DEFAULTS: DEFAULTS };
});
