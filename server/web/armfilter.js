// Filtro de partículas para la dirección del brazo (hombro → codo) a partir de un solo reloj.
//
// El reloj fija la orientación del antebrazo f; el codo e = s + L_u·u queda en una esfera alrededor
// del hombro s, con u desconocido (2 grados de libertad). Derivando dos veces la posición del reloj
// p = e + L_w·f, con el torso quieto:
//
//     p̈ = ë + L_w·f̈      f̈ = α × f + ω × (ω × f)      p̈ = R·a_lin
//  ⇒  ë = R·a_lin − L_w·f̈ =: z          (aceleración del codo, medida sin ver el codo)
//
// En la esfera, la componente radial de ë es la centrípeta: ë·u = −|ė|²/L_u. Una partícula con un u
// equivocado no cumple esa ecuación cuando hay movimiento: ese residuo es la verosimilitud. La parte
// tangencial de z mueve cada partícula; un muelle débil hacia la postura de reposo (el prior) y los
// límites articulares (codo, pronación, hombro, no atravesar el torso) completan el modelo. En reposo
// z ≈ 0 no distingue nada y el filtro vuelve al prior, que es lo mejor que se puede hacer sin más datos.
//
// El sesgo del acelerómetro empujaría las partículas para siempre (la deriva de integrar dos veces).
// Por eso, cuando la muñeca está quieta (giro y aceleración pequeños un rato), se aplica una
// actualización de velocidad cero: el codo también está quieto, las velocidades se frenan y lo que
// queda en el acelerómetro se aprende como sesgo (en el marco del reloj) y se resta de ahí en adelante.
//
// Marco del mundo: Y arriba, el frente del cuerpo hacia +Z, el lado izquierdo hacia +X (brazo izquierdo).
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ArmFilter = api.ArmFilter;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const DEG = Math.PI / 180;

  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = (a) => Math.hypot(a[0], a[1], a[2]);
  const normalize = (a) => { const n = norm(a) || 1; return [a[0] / n, a[1] / n, a[2] / n]; };
  const mulMV = (R, v) => [R[0] * v[0] + R[1] * v[1] + R[2] * v[2], R[3] * v[0] + R[4] * v[1] + R[5] * v[2], R[6] * v[0] + R[7] * v[1] + R[8] * v[2]];

  // Postura de reposo: el codo cuelga y se adelanta con el antebrazo (la regla que usaba el avatar).
  const defaultPrior = (f) => normalize([0.12 + 0.8 * f[0], -1 + 0.8 * f[1], 0.8 * f[2]]);

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const DEFAULTS = {
    n: 400, seed: 7,
    Lu: 0.30,                    // hombro → codo (m)
    Lf: 0.25,                    // codo → muñeca (m)
    Lw: 0.22,                    // codo → reloj (m)
    shoulder: [0.21, 1.42, 0],
    // ajustados con tools/test_armfilter.js (brazo sintético a tres velocidades)
    sigmaR: 0.3,                 // ruido del residuo radial (m/s²): acelerómetro + error de la gravedad estimada
    sigmaRel: 0.3,               // el error del modelo crece con la aceleración: σ = sigmaR + sigmaRel·|z|
    sigmaQ: 0.3,                 // ruido de proceso en la aceleración del codo (m/s² por √s)
    damping: 1.0,                // 1/s: las velocidades del brazo se apagan solas
    spring: 1.5,                 // 1/s²: tirón débil hacia la postura de reposo
    omegaSmooth: 0.35,           // suavizado de ω antes de derivarlo (α = dω/dt amplifica ruido)
    cosMaxFlex: Math.cos(150 * DEG),
    pronSlack: -0.25,            // la bisagra no puede quedar a más de ~105° de la pantalla (pronación límite)
    infeasibleWeight: 0.02,
    resampleFrac: 0.5,
    roughen: 0.015,              // rad: dispersión añadida al remuestrear
    stillOmega: 0.2,             // rad/s: por debajo, la muñeca cuenta como quieta…
    stillAcc: 0.35,              // m/s²: …si además la aceleración (sin sesgo) es pequeña…
    stillTime: 0.15,             // s: …durante este tiempo seguido
    biasRate: 0.5,               // 1/s: aprendizaje del sesgo del acelerómetro en quietud
    zuptDamping: 15,             // 1/s: frenado de las partículas en quietud
    springStill: null,           // muelle en quietud (null = el mismo que en movimiento)
    axisBody: [1, 0, 0],         // eje del antebrazo hacia la mano, en el marco del reloj
    screenBody: [0, 0, 1],       // normal de la pantalla, en el marco del reloj
    prior: defaultPrior,
  };

  function inTorso(p) { return p[0] < 0.18 && p[0] > -0.22 && p[1] > 0.95 && p[1] < 1.5 && Math.abs(p[2]) < 0.11; }

  // ¿Es anatómicamente posible el brazo u con el antebrazo f y la pantalla del reloj mirando a N?
  function feasible(u, f, N, o) {
    if (dot(u, f) < o.cosMaxFlex) return false;                       // codo más flexionado que el límite
    const h = cross(f, u), hn = norm(h);                               // eje de la bisagra hacia afuera (lateral)
    if (hn > 0.26) {                                                   // codo doblado > ~15°: la bisagra está definida
      const nd = dot(N, f), Np = [N[0] - nd * f[0], N[1] - nd * f[1], N[2] - nd * f[2]], npn = norm(Np);
      if (npn > 1e-3 && dot(h, Np) / (hn * npn) < o.pronSlack) return false;   // torsión imposible del antebrazo
    }
    if (u[2] < -0.8) return false;                                     // brazo demasiado hacia atrás
    if (u[0] < -0.3 && u[2] < 0) return false;                         // atrás y cruzando hacia el cuerpo
    const s = o.shoulder;
    const e = [s[0] + o.Lu * u[0], s[1] + o.Lu * u[1], s[2] + o.Lu * u[2]];
    if (inTorso(e)) return false;
    if (inTorso([e[0] + o.Lf * f[0], e[1] + o.Lf * f[1], e[2] + o.Lf * f[2]])) return false;
    return true;
  }

  class ArmFilter {
    constructor(opts = {}) {
      this.o = Object.assign({}, DEFAULTS, opts);
      const n = this.o.n;
      this.U = new Float64Array(3 * n);       // direcciones del brazo (unitarias, mundo)
      this.V = new Float64Array(3 * n);       // velocidad del codo (m/s, tangente a la esfera)
      this.W = new Float64Array(n);           // pesos
      this.rand = mulberry32(this.o.seed);
      this.axisB = this.o.axisBody.slice();
      this.ready = false;
      this.omS = null;
      this.bB = [0, 0, 0];                    // sesgo de la aceleración lineal, en el reloj
      this.stillT = 0;
      this.est = { u: null, spread: NaN, neff: n, resid: 0, accel: 0, feasibleFrac: 1 };
    }

    randn() {
      let u = 0, v = 0;
      while (u === 0) u = this.rand();
      while (v === 0) v = this.rand();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    }

    setAxis(axisBody) { this.axisB = axisBody.slice(); this.reset(); }
    reset() { this.ready = false; this.omS = null; this.stillT = 0; }

    // El avatar recentra el rumbo girando el mundo alrededor de Y: las partículas giran con él.
    rotateY(theta) {
      const c = Math.cos(theta), s = Math.sin(theta), n = this.o.n;
      for (const A of [this.U, this.V]) {
        for (let i = 0; i < n; i++) {
          const j = 3 * i, x = A[j], z = A[j + 2];
          A[j] = c * x + s * z; A[j + 2] = -s * x + c * z;
        }
      }
      if (this.omS) { const x = this.omS[0], z = this.omS[2]; this.omS = [c * x + s * z, this.omS[1], -s * x + c * z]; }
      if (this.est.u) { const u = this.est.u; this.est.u = [c * u[0] + s * u[2], u[1], -s * u[0] + c * u[2]]; }
    }

    _init(f, N) {
      const o = this.o, up = o.prior(f);
      for (let i = 0; i < o.n; i++) {
        let u = up;
        for (let k = 0; k < 30; k++) {
          const c = normalize([up[0] + 0.5 * this.randn(), up[1] + 0.5 * this.randn(), up[2] + 0.5 * this.randn()]);
          if (feasible(c, f, N, o)) { u = c; break; }
        }
        this.U.set(u, 3 * i); this.V.fill(0, 3 * i, 3 * i + 3); this.W[i] = 1 / o.n;
      }
      this.ready = true;
    }

    // R: matriz reloj → mundo (9 números, por filas). omegaB: rad/s en el reloj. aLinB: m/s² en el reloj, sin gravedad.
    step(R, omegaB, aLinB, dt) {
      if (!(dt > 0) || dt > 0.1) dt = 0.01;
      const o = this.o, n = o.n, U = this.U, V = this.V, W = this.W;
      const f = normalize(mulMV(R, this.axisB)), N = normalize(mulMV(R, o.screenBody));
      if (!this.ready) this._init(f, N);

      const om = mulMV(R, omegaB);
      if (!this.omS) this.omS = om.slice();
      const k = o.omegaSmooth;
      const omS = [this.omS[0] + k * (om[0] - this.omS[0]), this.omS[1] + k * (om[1] - this.omS[1]), this.omS[2] + k * (om[2] - this.omS[2])];
      const alpha = [(omS[0] - this.omS[0]) / dt, (omS[1] - this.omS[1]) / dt, (omS[2] - this.omS[2]) / dt];
      this.omS = omS;
      const a1 = cross(alpha, f), a2 = cross(omS, cross(omS, f));
      // quietud: ¿la muñeca no gira ni acelera? entonces el codo tampoco se mueve (velocidad cero)
      const bB = this.bB, ac = [aLinB[0] - bB[0], aLinB[1] - bB[1], aLinB[2] - bB[2]];
      if (norm(omegaB) < o.stillOmega && norm(ac) < o.stillAcc) this.stillT += dt; else this.stillT = 0;
      const zupt = this.stillT >= o.stillTime;
      if (zupt) { const g = Math.min(1, o.biasRate * dt); for (let c = 0; c < 3; c++) bB[c] += g * (aLinB[c] - bB[c]); }
      const aw = mulMV(R, [aLinB[0] - bB[0], aLinB[1] - bB[1], aLinB[2] - bB[2]]);
      const z = [aw[0] - o.Lw * (a1[0] + a2[0]), aw[1] - o.Lw * (a1[1] + a2[1]), aw[2] - o.Lw * (a1[2] + a2[2])];

      const up = o.prior(f);
      const sig = o.sigmaR + o.sigmaRel * norm(z);
      const inv2s2 = 1 / (2 * sig * sig), sq = (zupt ? 0.2 : 1) * o.sigmaQ * Math.sqrt(dt);
      const kp = (zupt && o.springStill !== null ? o.springStill : o.spring) * o.Lu;
      const drive = zupt ? 0 : 1, damp = zupt ? o.zuptDamping : o.damping;
      let wsum = 0, feas = 0;
      for (let i = 0; i < n; i++) {
        const j = 3 * i;
        let u0 = U[j], u1 = U[j + 1], u2 = U[j + 2], v0 = V[j], v1 = V[j + 1], v2 = V[j + 2];
        // 1) verosimilitud: la componente radial de la aceleración del codo debe ser la centrípeta
        const zr = z[0] * u0 + z[1] * u1 + z[2] * u2;
        const r = zr + (v0 * v0 + v1 * v1 + v2 * v2) / o.Lu;
        let wi = W[i] * Math.exp(-r * r * inv2s2);
        // 2) predicción: la parte tangencial de z mueve el codo, más el muelle hacia el reposo y amortiguación
        const pr = up[0] * u0 + up[1] * u1 + up[2] * u2;
        v0 += (drive * (z[0] - zr * u0) + kp * (up[0] - pr * u0) - damp * v0) * dt + sq * this.randn();
        v1 += (drive * (z[1] - zr * u1) + kp * (up[1] - pr * u1) - damp * v1) * dt + sq * this.randn();
        v2 += (drive * (z[2] - zr * u2) + kp * (up[2] - pr * u2) - damp * v2) * dt + sq * this.randn();
        let vr = v0 * u0 + v1 * u1 + v2 * u2; v0 -= vr * u0; v1 -= vr * u1; v2 -= vr * u2;
        u0 += v0 * dt / o.Lu; u1 += v1 * dt / o.Lu; u2 += v2 * dt / o.Lu;
        const un = Math.hypot(u0, u1, u2) || 1; u0 /= un; u1 /= un; u2 /= un;
        vr = v0 * u0 + v1 * u1 + v2 * u2; v0 -= vr * u0; v1 -= vr * u1; v2 -= vr * u2;
        // 3) límites articulares
        if (feasible([u0, u1, u2], f, N, o)) feas++; else wi *= o.infeasibleWeight;
        U[j] = u0; U[j + 1] = u1; U[j + 2] = u2; V[j] = v0; V[j + 1] = v1; V[j + 2] = v2;
        W[i] = wi; wsum += wi;
      }
      if (!(wsum > 0) || !Number.isFinite(wsum)) {   // ninguna partícula explica la medición: empezar de nuevo
        this._init(f, N);
        return this._estimate(0, z, 0);
      }
      let s2 = 0;
      for (let i = 0; i < n; i++) { W[i] /= wsum; s2 += W[i] * W[i]; }
      const neff = 1 / s2;
      if (neff < n * o.resampleFrac) this._resample();
      return this._estimate(neff, z, feas / n);
    }

    _resample() {
      const o = this.o, n = o.n, U = this.U, V = this.V, W = this.W;
      const U2 = new Float64Array(3 * n), V2 = new Float64Array(3 * n);
      let c = W[0], i = 0;
      const start = this.rand() / n;
      for (let m = 0; m < n; m++) {                 // remuestreo sistemático
        const t = start + m / n;
        while (t > c && i < n - 1) { i++; c += W[i]; }
        let u0 = U[3 * i] + o.roughen * this.randn(), u1 = U[3 * i + 1] + o.roughen * this.randn(), u2 = U[3 * i + 2] + o.roughen * this.randn();
        const un = Math.hypot(u0, u1, u2) || 1; u0 /= un; u1 /= un; u2 /= un;
        let v0 = V[3 * i], v1 = V[3 * i + 1], v2 = V[3 * i + 2];
        const vr = v0 * u0 + v1 * u1 + v2 * u2; v0 -= vr * u0; v1 -= vr * u1; v2 -= vr * u2;
        U2[3 * m] = u0; U2[3 * m + 1] = u1; U2[3 * m + 2] = u2; V2[3 * m] = v0; V2[3 * m + 1] = v1; V2[3 * m + 2] = v2;
      }
      this.U.set(U2); this.V.set(V2); W.fill(1 / n);
    }

    _estimate(neff, z, feasibleFrac) {
      const o = this.o, n = o.n, U = this.U, W = this.W;
      let m0 = 0, m1 = 0, m2 = 0;
      for (let i = 0; i < n; i++) { m0 += W[i] * U[3 * i]; m1 += W[i] * U[3 * i + 1]; m2 += W[i] * U[3 * i + 2]; }
      const u = normalize([m0, m1, m2]);
      let sp = 0;
      for (let i = 0; i < n; i++) {
        const d0 = U[3 * i] - u[0], d1 = U[3 * i + 1] - u[1], d2 = U[3 * i + 2] - u[2];
        sp += W[i] * (d0 * d0 + d1 * d1 + d2 * d2);
      }
      this.est = { u, spread: Math.sqrt(sp) * o.Lu, neff, accel: norm(z), feasibleFrac, still: this.stillT >= o.stillTime, bias: this.bB.slice() };
      return this.est;
    }

    elbow(i) {   // posición del codo de la partícula i (para dibujar la nube)
      const o = this.o, s = o.shoulder;
      return [s[0] + o.Lu * this.U[3 * i], s[1] + o.Lu * this.U[3 * i + 1], s[2] + o.Lu * this.U[3 * i + 2]];
    }
  }

  return { ArmFilter, feasible, defaultPrior, DEFAULTS };
});
