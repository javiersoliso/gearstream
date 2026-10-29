// El lápiz suena. Dos modos (N los cambia):
//
// PULSOS. Un pulso es una frecuencia: f₀ golpes por segundo. Varios pulsos son razones sobre ese pulso:
//   pulsos = [1 ; a ; b ; c] → golpes a f₀, a·f₀, b·f₀, c·f₀
// y cada dimensión del lápiz pone una casilla: en 1D la altura da a; en 2D x da a e y da b; en 3D x, y y la
// profundidad dan a, b y c (enteros del 1 al 8, una franja por número). Todos los pulsos cuentan desde el
// mismo instante, así que coinciden cada 1/f₀ s: [1 ; 3 ; 2] es un polirritmo de tres contra dos. El bisel
// dobla o parte f₀ por la mitad, y f₀ siempre cae en la nota do: 2.04 Hz (123 golpes por minuto) es un do siete
// octavas por debajo del do central; seis clics más arriba es do3 (130.8 Hz). Pasando de ~20 golpes por
// segundo el oído ya no oye golpes sino una nota, y las mismas razones se vuelven un acorde de armónicos de
// do: 2 = do, 3 = sol, 5 = mi, 7 = si bemol. 3:2 es una quinta, 5:4 una tercera mayor, 2:1 una octava. Ritmo
// y armonía son lo mismo a distinta velocidad.
//
// ARPA. La altura del lápiz es la nota (pentatónica de do: do re mi sol la, nunca desafina); cada vez que el
// lápiz cruza a otra nota la toca, como pasar el dedo por un arpa. Cada color del bisel es un instrumento y
// debajo suena un colchón de acordes do – sol – la menor – fa.
//
// Todo sale de los puntos del dibujo (y de las operaciones de pulso guardadas), así que reproducir un dibujo
// suena igual que cuando lo hiciste.
(function (root) {
  'use strict';

  const MODES = ['pulsos', 'arpa', 'off'];
  const PENTA = [0, 2, 4, 7, 9];
  const NOTES = 16;
  const CHORDS = [[48, 55, 64, 67], [43, 50, 59, 67], [45, 52, 60, 64], [41, 48, 57, 65]];   // C G Am F
  const BAR = 2.6;
  const MAXR = 8;
  const C0 = 16.3516;                                // do0 en Hz; el pulso es do0 · 2^k
  const HARM = ['do', 'do', 'sol', 'do', 'mi', 'sol', 'si♭', 'do'];   // el armónico r de do
  // voz 0: el pulso base (grave, como un bombo); voces 1-3: una por dimensión, cada una con su color y lado
  const VOICES = [{ car: 140, tau: 0.07, gain: 0.55, pan: 0 }, { car: 880, tau: 0.03, gain: 0.32, pan: -0.55 },
    { car: 2100, tau: 0.018, gain: 0.26, pan: 0.55 }, { car: 4300, tau: 0.01, gain: 0.22, pan: 0 }];
  const TIMBRES = {
    '#58c4dd': { name: 'campana', parts: [[1, 1, 'sine'], [2.76, 0.35, 'sine'], [5.4, 0.12, 'sine']], a: 0.003, d: 2.2, oct: 1 },
    '#f0997b': { name: 'arpa', parts: [[1, 1, 'triangle'], [2, 0.25, 'sine']], a: 0.002, d: 1.3, oct: 0 },
    '#5dcaa5': { name: 'marimba', parts: [[1, 1, 'sine'], [4, 0.3, 'sine']], a: 0.002, d: 0.6, oct: 0 },
    '#ffd166': { name: 'glockenspiel', parts: [[1, 1, 'sine'], [3, 0.4, 'sine'], [6.2, 0.2, 'sine']], a: 0.001, d: 1.6, oct: 1 },
    '#c39bf0': { name: 'sintetizador', parts: [[1, 0.5, 'sawtooth'], [1.006, 0.5, 'sawtooth']], a: 0.01, d: 0.9, oct: 0, lp: 1800 },
    '#f4a6b8': { name: 'chip', parts: [[1, 0.45, 'square']], a: 0.002, d: 0.35, oct: 1, lp: 3200 },
    '#ece9e1': { name: 'piano', parts: [[1, 1, 'triangle'], [2, 0.3, 'sine'], [3, 0.1, 'sine']], a: 0.002, d: 1.5, oct: 0 },
    '#ff6b6b': { name: 'bajo', parts: [[1, 1, 'triangle'], [2, 0.25, 'sawtooth']], a: 0.004, d: 0.9, oct: -1, lp: 900 },
  };
  // el generador de pulsos: cada voz golpea cuando floor(n·f/sr) cambia, con n las muestras desde el inicio,
  // así todas cuentan desde el mismo cero y coinciden exactamente. Cada golpe es un seno corto que se apaga.
  const WORKLET = `
    class Pulsos extends AudioWorkletProcessor {
      constructor(o) {
        super(); const v = o.processorOptions.voices;
        this.n = 0; this.f = v.map(() => 0); this.cnt = v.map(() => 0); this.env = v.map(() => 0); this.ph = v.map(() => 0);
        this.car = v.map((x) => x.car); this.tau = v.map((x) => x.tau);
        this.port.onmessage = (e) => { this.f = e.data; };
      }
      process(inputs, outputs) {
        const out = outputs[0], len = out[0].length;
        for (let v = 0; v < out.length; v++) {
          const ch = out[v], f = this.f[v] || 0, dec = Math.exp(-1 / (this.tau[v] * sampleRate)), w = 2 * Math.PI * this.car[v] / sampleRate;
          let env = this.env[v], ph = this.ph[v], cnt = this.cnt[v];
          for (let i = 0; i < len; i++) {
            if (f > 0) { const c = Math.floor((this.n + i) * f / sampleRate); if (c !== cnt) { cnt = c; env = 1; ph = 0; } }
            ch[i] = env * Math.sin(ph); ph += w; env *= dec;
          }
          this.env[v] = env; this.ph[v] = ph % (2 * Math.PI); this.cnt[v] = cnt;
        }
        this.n += len;
        return true;
      }
    }
    registerProcessor('pulsos', Pulsos);`;
  const midiHz = (m) => 440 * Math.pow(2, (m - 69) / 12);
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const ratio = (u) => clamp(1 + Math.floor(clamp(u, 0, 0.9999) * MAXR), 1, MAXR);

  // dónde cae el punto, normalizado a 0..1 por dimensión: 1D [altura], 2D [x, altura], 3D [x, altura, lejos]
  function unit(mode, p, view) {
    if (mode === 3) return [(p[0] + 3) / 6, (p[1] + 1) / 3, (Math.hypot(p[0], p[1], p[2]) - 0.8) / 6];
    const up = 1 - p[1] / view[1];
    return mode === 2 ? [p[0] / view[0], up] : [up];
  }
  const ratiosOf = (mode, p, view) => unit(mode, p, view).map(ratio);

  class Musica {
    constructor() {
      this.ctx = null; this.strokes = new Map(); this.lastActive = -1e9; this.pad = null; this.chord = -1;
      this.k = -3; this.live = null; this.sentF = '';      // do 7 octavas bajo el central: 2.04 Hz
      try { const m = localStorage.getItem('gearstream.musica'); this.mode = MODES.includes(m) ? m : 'pulsos'; } catch { this.mode = 'pulsos'; }
    }
    get f0() { return C0 * Math.pow(2, this.k); }
    timbre(color) { return TIMBRES[color] || TIMBRES['#ece9e1']; }
    get ready() { return !!this.ctx && this.ctx.state === 'running'; }
    // el navegador solo deja sonar después de un toque o una tecla
    unlock() {
      if (!this.ctx) {
        const AC = root.AudioContext || root.webkitAudioContext;
        if (!AC) return;
        const ctx = this.ctx = new AC();
        this.master = ctx.createGain(); this.master.gain.value = 0.8;
        const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -16; comp.ratio.value = 4;
        this.master.connect(comp); comp.connect(ctx.destination);
        this.out = comp;
        this.verb = ctx.createConvolver(); this.verb.buffer = this.impulse(2.8);
        const wet = ctx.createGain(); wet.gain.value = 0.9; this.verb.connect(wet); wet.connect(this.master);
        this.buildPulses();
        setInterval(() => this.tick(), 100);
      }
      if (this.ctx.state === 'suspended') this.ctx.resume();
    }
    async buildPulses() {
      const ctx = this.ctx;
      try { await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([WORKLET], { type: 'text/javascript' }))); } catch { return; }
      const node = new AudioWorkletNode(ctx, 'pulsos', { numberOfInputs: 0, outputChannelCount: [VOICES.length], processorOptions: { voices: VOICES } });
      const split = ctx.createChannelSplitter(VOICES.length);
      node.connect(split);
      this.vg = VOICES.map((v, i) => {
        const g = ctx.createGain(); g.gain.value = 0;
        const pn = ctx.createStereoPanner(); pn.pan.value = v.pan;
        const sg = ctx.createGain(); sg.gain.value = 0.18;
        split.connect(g, i); g.connect(pn); pn.connect(this.master); pn.connect(sg); sg.connect(this.verb);
        return g;
      });
      this.pulses = node;
    }
    impulse(sec) {                       // eco de sala: ruido que se apaga
      const n = Math.round(this.ctx.sampleRate * sec), b = this.ctx.createBuffer(2, n, this.ctx.sampleRate);
      for (let c = 0; c < 2; c++) { const d = b.getChannelData(c); for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 3); }
      return b;
    }
    stream() {                           // para grabar video con sonido
      if (!this.ctx) return null;
      if (!this.dest) { this.dest = this.ctx.createMediaStreamDestination(); this.out.connect(this.dest); }
      return this.dest.stream;
    }
    setMode(mode) {
      this.mode = MODES.includes(mode) ? mode : 'pulsos';
      try { localStorage.setItem('gearstream.musica', this.mode); } catch { /* nada */ }
      this.silence();
    }
    mute(on) { this.muted = on; if (this.master) this.master.gain.setTargetAtTime(on ? 0 : 0.8, this.ctx.currentTime, 0.05); }
    nextMode() { this.setMode(MODES[(MODES.indexOf(this.mode) + 1) % MODES.length]); return this.mode; }
    step(d) { this.k = clamp(this.k + d, -5, 4); this.sendPulses(); return this.f0; }   // el bisel: ×2 o ÷2, de 0.5 Hz a do4
    pulse(f) { if (f > 0) { this.k = Math.round(Math.log2(f / C0)); this.sendPulses(); } }

    // ---- trazos: lo que dibuja la página o la reproducción ----
    stroke(id, info) {
      const s = { mode: info.mode, color: info.color, mu: info.mu || this.mode, deg: null, t: -1, ratios: null };
      this.strokes.set(id, s);
      if (s.mu === 'pulsos') { if (info.f0 > 0) this.k = Math.round(Math.log2(info.f0 / C0)); this.live = s; }
    }
    point(id, p, view) {
      const s = this.strokes.get(id);
      if (!s || !this.ready) return;
      this.lastActive = this.ctx.currentTime;
      if (s.mu === 'pulsos') { s.ratios = ratiosOf(s.mode, p, view); this.live = s; this.sendPulses(); }
      else if (s.mu === 'arpa') this.harp(s, p, view);
    }
    end(id) {
      const s = this.strokes.get(id);
      this.strokes.delete(id);
      if (s && this.live === s) { this.live = null; this.sendPulses(); }
    }
    silence() { this.strokes.clear(); this.live = null; this.sendPulses(); this.padOff(); }

    sendPulses() {
      if (!this.pulses) return;
      const s = this.live, on = !!(s && s.ratios);
      const f = on ? [this.f0, ...s.ratios.map((r) => r * this.f0)] : [];
      const key = f.join(',');
      if (key !== this.sentF) { this.pulses.port.postMessage(VOICES.map((_, i) => f[i] || 0)); this.sentF = key; }
      const t = this.ctx.currentTime;
      this.vg.forEach((g, i) => g.gain.setTargetAtTime(on && i < f.length ? VOICES[i].gain : 0, t, 0.03));
    }
    harp(s, p, view) {
      const u = unit(s.mode, p, view), h = s.mode === 1 ? u[0] : u[1];
      const deg = Math.round(clamp(h, 0, 1) * (NOTES - 1)), now = this.ctx.currentTime;
      if (deg === s.deg || now - s.t < 0.05) return;
      const T = this.timbre(s.color);
      const midi = 48 + 12 * Math.floor(deg / 5) + PENTA[deg % 5] + 12 * T.oct;
      const vel = s.deg === null ? 0.32 : clamp(0.16 + 0.04 * Math.abs(deg - s.deg), 0.16, 0.3);
      let pan = 0, cutoff = 6000, send = 0.3;
      if (s.mode === 2) pan = clamp(u[0] * 2 - 1, -1, 1);
      if (s.mode === 3) { const dist = Math.hypot(p[0], p[1], p[2]); pan = clamp(p[0] / 3, -1, 1); cutoff = 7000 / (1 + dist / 3); send = clamp(0.25 + dist / 12, 0.25, 0.8); }
      s.deg = deg; s.t = now;
      this.note(midiHz(midi), T, pan, Math.min(cutoff, T.lp || 1e5), vel, send);
    }
    note(f, T, pan, cutoff, vel, send) {
      const ctx = this.ctx, t = ctx.currentTime;
      const env = ctx.createGain();
      env.gain.setValueAtTime(0, t); env.gain.linearRampToValueAtTime(vel, t + T.a); env.gain.exponentialRampToValueAtTime(0.0001, t + T.d);
      const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = cutoff;
      const pn = ctx.createStereoPanner(); pn.pan.value = pan;
      lp.connect(env); env.connect(pn); pn.connect(this.master);
      const sg = ctx.createGain(); sg.gain.value = send; pn.connect(sg); sg.connect(this.verb);
      for (const [mul, amp, type] of T.parts) {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = type; o.frequency.value = f * mul; g.gain.value = amp / T.parts.length;
        o.connect(g); g.connect(lp); o.start(t); o.stop(t + T.d + 0.05);
      }
    }
    // arpa: el colchón de acordes suena mientras hay notas y se apaga dos segundos después
    tick() {
      if (!this.ready) return;
      const now = this.ctx.currentTime, active = this.mode === 'arpa' && now - this.lastActive < 2;
      const k = Math.floor(now / BAR) % CHORDS.length;
      if (active && (!this.pad || k !== this.chord)) { this.padOff(); this.padOn(CHORDS[k]); this.chord = k; }
      else if (!active && this.pad) this.padOff();
    }
    padOn(chord) {
      const ctx = this.ctx, t = ctx.currentTime, g = ctx.createGain(), lp = ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 700;
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.05, t + 0.9);
      lp.connect(g); g.connect(this.master); g.connect(this.verb);
      const oscs = [];
      for (const m of chord) for (const det of [-6, 6]) {
        const o = ctx.createOscillator(); o.type = 'sawtooth'; o.frequency.value = midiHz(m); o.detune.value = det;
        o.connect(lp); o.start(t); oscs.push(o);
      }
      this.pad = { g, oscs };
    }
    padOff() {
      if (!this.pad) return;
      const t = this.ctx.currentTime, { g, oscs } = this.pad;
      g.gain.cancelScheduledValues(t); g.gain.setValueAtTime(g.gain.value, t); g.gain.linearRampToValueAtTime(0, t + 1.2);
      for (const o of oscs) o.stop(t + 1.3);
      this.pad = null;
    }
  }

  // lo que se ve en pantalla: "pulso 2.04 Hz · 123 por minuto · do, 7 octavas bajo el central · [1 ; 3 ; 5] = do sol mi"
  function describe(music, mode, p, view) {
    if (music.mode === 'off') return '♪ sin sonido';
    if (music.mode === 'arpa') return '♪ arpa';
    const f = music.f0, below = 4 - music.k;
    const what = f < 16 ? `${Math.round(60 * f)} por minuto · do, ${below} octavas bajo el central` : `nota do${music.k}`;
    const rs = p ? ratiosOf(mode, p, view) : [];
    return `♪ pulso ${f < 10 ? f.toFixed(2) : f.toFixed(1)} Hz · ${what} · [1 ; ${rs.join(' ; ')}] = ${['do', ...rs.map((r) => HARM[r - 1])].join(' ')}`;
  }

  Object.assign(root, { Musica, TIMBRES, ratiosOf, describeMusic: describe, MAX_RATIO: MAXR });
})(typeof self !== 'undefined' ? self : this);
