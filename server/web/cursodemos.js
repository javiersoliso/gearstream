// Las poses de la grabación del curso (curso-protocol.json): qué hace el muñeco en cada paso, para copiarlo.
// Cada demo es at(t, side) → { P, watch, ray, flash, gravity }: P es una pose de mocapmath.build; t son los
// segundos desde que empieza a grabar el paso (negativo en el "prepárate"), así los gestos caen en los
// pitidos (el primero a 0.3 s, uno cada `period`) y las muñecas siguen a la bolita del metrónomo
// (y = ½ − ½·cos 2πft). watch: 'muneca' o el reloj suelto en la mesa {p, X, Y, Z}; body: false esconde
// al muñeco.
// Mundo como en mocapmath: y arriba, el cuerpo mira hacia −z con su derecha en +x.
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./mocapmath.js'));
  else Object.assign(root, factory(root));
})(typeof self !== 'undefined' ? self : this, function (M) {
  'use strict';

  const { ANIMS, build } = M, { add, sub, mul, cross, unit, rot } = M.vec;
  const D2R = Math.PI / 180, UP = [0, 1, 0], DOWN = [0, -1, 0], FWD = [0, 0, -1], BACK = [0, 0, 1];
  const smooth = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
  const mix = (a, b, u) => a + (b - a) * u;
  const nlerp = (a, b, u) => unit(add(mul(a, 1 - u), mul(b, u)));
  const kOf = (side) => (side === 'l' ? -1 : 1);
  const other = (side) => (side === 'l' ? 'r' : 'l');
  const ball = (t, f) => 0.5 - 0.5 * Math.cos(2 * Math.PI * f * t);           // la bolita de dataset.js: 0 abajo, 1 arriba
  const sinceCue = (t, period) => ((t - 0.3) % period + period) % period;       // segundos desde el último pitido

  // la mesa con la laptop, delante; el reloj suelto se apoya en ella
  const DESK = { y: 0.74, z0: -0.55, z1: -1.1, w: 1.1 };
  const LEGS = { l: { flex: 2, knee: 4 }, r: { flex: 2, knee: 4 } };
  const rest = () => ({ fk: { flex: 4, abd: 6, elbow: 12 }, pron: 0, fist: 0.2 });
  function stand(t, side, arm, otherArm) {
    const b = Math.sin(2 * Math.PI * t / 4), arms = { l: rest(), r: rest() };
    if (arm) arms[side] = arm;
    if (otherArm) arms[other(side)] = otherArm;
    return { pelvis: [0, 0.98 + 0.003 * b, 0], H: 0, lean: 2, head: 10, legs: LEGS, arms };
  }
  function onDesk(side) {
    const X = [-kOf(side), 0, 0];
    return { p: [0.14 * kOf(side), DESK.y + 0.006, -0.72], X, Y: cross(UP, X), Z: UP };
  }

  // las seis caras, en un orden en que cada una está a 90° de la siguiente (así "despacio" las recorre sin saltos)
  function faces(side) {
    const k = kOf(side), out = [k, 0, 0], med = [-k, 0, 0];
    return [
      { id: 'cara_arriba', F: FWD, d: UP, flex: 12 },
      { id: 'cara_mano', F: FWD, d: out, flex: 12 },
      { id: 'cara_abajo', F: FWD, d: DOWN, flex: 12 },
      { id: 'cara_colgando', F: DOWN, d: out, flex: 2 },
      { id: 'cara_pecho', F: unit(add(med, [0, 0, 0.12])), d: unit([0, 0.12, 1]), flex: 48 },
      { id: 'cara_mano_arriba', F: unit([0, 1, -0.06]), d: BACK, flex: 25, fist: 0 },
    ];
  }
  const faceArm = (f) => ({ over: { F: f.F, d: f.d, flex: f.flex }, fist: f.fist === undefined ? 0.25 : f.fist });

  // muñeca: el antebrazo al frente, palma abajo; la mano se dobla `a` grados alrededor de `axis` y el
  // antebrazo la acompaña un poco (es lo que ve el reloj)
  function wristArm(axis, a, follow) {
    const F = rot(FWD, axis, follow * a * D2R), d = rot(UP, axis, follow * a * D2R);
    return { over: { F, d, flex: 12, hand: { F: rot(FWD, axis, a * D2R), d: rot(UP, axis, a * D2R) } }, fist: 0.15 };
  }
  const LAT = cross(FWD, UP);                  // eje de inclinar: de lado a lado (+x)

  // apuntar quieto, al centro de la pantalla virtual de mocapmath
  function pointing(t, side, fist) {
    const P = ANIMS.apuntar.pose(0, side);
    P.arms[side].fist = fist;
    P.pelvis = [0, 0.98 + 0.003 * Math.sin(2 * Math.PI * t / 4), 0];
    return P;
  }

  // pellizco y puño: la mano al frente un poco arriba, el pulgar arriba, para que se vean los dedos
  function gestureArm(side, fist, pinch) {
    const F = unit([0, 0.2, -1]), d = unit([kOf(side), 0.75, 0.15]);
    return { over: { F, d, flex: 25 }, fist, pinch };
  }

  // palmada: las dos muñecas delante del pecho se juntan en cada pitido
  function clapArms(t, period) {
    const u = sinceCue(t, period), near = Math.min(u, period - u);         // distancia al pitido más cercano
    const s = 0.035 + 0.13 * smooth(near / 0.38);
    const arm = { ik: { target: { off: [0.3, -0.24, 0.19 - s / 2] }, pole: { off: [-0.05, -0.5, -0.45] } }, pron: -8, fist: 0 };
    return { arm, flash: near < 0.06 ? 1 - near / 0.06 : 0 };
  }

  const DEMOS = {
    mesa: {
      cam: 'mesa',
      at(t, side) {                            // solo el reloj: baja durante el "prepárate" y se queda quieto
        const w = onDesk(side), u = smooth((t + 2.6) / 1.5), lift = 0.2 * (1 - u), tilt = 25 * (1 - u) * D2R;
        const X = rot(w.X, w.Y, tilt), Z = rot(w.Z, w.Y, tilt);
        return { P: stand(t, side), body: false, watch: { p: add(w.p, [0, lift, 0]), X, Y: w.Y, Z }, gravity: u >= 1 };
      },
    },
    ponerse: {
      cam: 'brazo',
      at(t, side) {                            // la otra mano abrocha la correa
        const arm = { over: { F: unit([0, -0.25, -1]), d: UP, flex: 14 }, fist: 0.3 };
        const wr = build(stand(t, side, arm)).arms[side].wr, wig = 0.012 * Math.sin(2 * Math.PI * t * 1.3);
        const help = { ik: { target: () => add(wr, [wig, 0.05, 0.02]), pole: { off: [-0.1, -0.5, -0.4] } }, pron: 80, fist: 0.5 };
        return { P: stand(t, side, arm, help), watch: 'muneca' };
      },
    },
    palmadas: {
      cam: 'cuerpo', period: 1.5,
      at(t, side) {
        const c = clapArms(t, 1.5);
        return { P: stand(t, side, c.arm, c.arm), watch: 'muneca', flash: c.flash, flashAt: 'manos' };
      },
    },
    reposo: { cam: 'brazo', at: (t, side) => ({ P: pointing(t, side, 0.5), watch: 'muneca', ray: true }) },
    caras_despacio: {
      cam: 'brazo', gravity: true,
      at(t, side) {
        const fs = faces(side), seg = 20 / fs.length, tt = ((t % 20) + 20) % 20, i = Math.floor(tt / seg);
        const a = fs[i], b = fs[(i + 1) % fs.length], u = smooth(((tt - i * seg) - 1.3) / (seg - 1.3));
        const arm = { over: { F: nlerp(a.F, b.F, u), d: nlerp(a.d, b.d, u), flex: mix(a.flex, b.flex, u) }, fist: 0.25 };
        return { P: stand(t, side, arm), watch: 'muneca', gravity: true };
      },
    },
    sacudir: {
      cam: 'brazo',
      at(t, side) {
        const s = Math.sin(2 * Math.PI * 4.2 * t), c = Math.sin(2 * Math.PI * 5.1 * t + 1);
        const F = rot(FWD, LAT, 7 * c * D2R), d = rot(rot(UP, LAT, 7 * c * D2R), F, 45 * s * D2R);
        const arm = { over: { F, d, flex: 14, hand: { F: rot(F, cross(F, d), 30 * s * D2R), d: rot(d, cross(F, d), 30 * s * D2R) } }, fist: 0 };
        return { P: stand(t, side, arm), watch: 'muneca' };
      },
    },
    brazo: {
      cam: 'cuerpo', period: 3,
      at(t, side) {                            // arriba al frente; con el pitido cae, espera, y sube despacio
        const u = sinceCue(t, 3), down = u < 0.35 ? smooth(u / 0.35) : u < 1.3 ? 1 : 1 - smooth((u - 1.3) / 1.2);
        const arm = { fk: { flex: mix(82, 2, down), abd: 6, elbow: mix(8, 6, down) }, pron: mix(88, 5, down), fist: 0.2 };
        return { P: stand(t, side, arm), watch: 'muneca' };
      },
    },
    muneca_lenta: { cam: 'perfil', metronome: 0.5, at: (t, side) => ({ P: stand(t, side, wristArm(LAT, 32 * (2 * ball(t, 0.5) - 1), 0.25)), watch: 'muneca' }) },
    muneca_rapida: { cam: 'perfil', metronome: 2, at: (t, side) => ({ P: stand(t, side, wristArm(LAT, 24 * (2 * ball(t, 2) - 1), 0.25)), watch: 'muneca' }) },
    girar: { cam: 'arriba', metronome: 0.5, at: (t, side) => ({ P: stand(t, side, wristArm(UP, -28 * (2 * ball(t, 0.5) - 1), 0.3)), watch: 'muneca' }) },
    atornillar: {
      cam: 'mano', metronome: 0.5,
      at(t, side) {                            // el antebrazo entero gira sobre su largo, con la mano
        const a = 60 * (2 * ball(t, 0.5) - 1) * D2R;
        return { P: stand(t, side, { over: { F: FWD, d: rot(UP, FWD, a), flex: 12 }, fist: 0.35 }), watch: 'muneca' };
      },
    },
    pinza2: {
      cam: 'gesto', period: 2,
      at(t, side) {                            // pulgar e índice se juntan con el pitido y se sueltan
        const u = sinceCue(t, 2), p = u < 0.12 ? smooth(u / 0.12) : u < 0.3 ? 1 : 1 - smooth((u - 0.3) / 0.25);
        return { P: stand(t, side, gestureArm(side, 0.1, p)), watch: 'muneca', flash: 0.6 * p, flashAt: 'pinza' };
      },
    },
    puno: {
      cam: 'gesto', period: 2,
      at(t, side) {
        const u = sinceCue(t, 2), p = u < 0.15 ? smooth(u / 0.15) : u < 0.6 ? 1 : 1 - smooth((u - 0.6) / 0.3);
        return { P: stand(t, side, gestureArm(side, p, 0)), watch: 'muneca', flash: p * 0.4, flashAt: 'mano' };
      },
    },
    raton: {
      cam: 'brazo',
      at(t, side) {
        const P = ANIMS.apuntar.pose(((t % 10) + 10) % 10, side);
        P.arms[side].pron = 70; P.arms[side].fist = 0.5;   // sin los clics de la animación: aquí no se pellizca
        return { P, watch: 'muneca', ray: true };
      },
    },
  };
  for (const f of faces('l')) {
    DEMOS[f.id] = { cam: 'brazo', gravity: true, at: (t, side) => ({ P: stand(t, side, faceArm(faces(side).find((g) => g.id === f.id))), watch: 'muneca', gravity: true }) };
  }

  // qué eje del reloj mira al techo: el de mayor componente vertical, con su signo (+z, −y…)
  function upAxis(w) {
    const v = [w.X[1], w.Y[1], w.Z[1]];
    let i = 0;
    for (let j = 1; j < 3; j++) if (Math.abs(v[j]) > Math.abs(v[i])) i = j;
    return (v[i] >= 0 ? '+' : '−') + 'xyz'[i];
  }

  return { DEMOS, DESK, upAxis, demoBall: ball };
});
