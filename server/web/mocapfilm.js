// Modo comercial del mocap: el mismo stickman y los mismos datos, filmados como un anuncio. Planos
// coreografiados con cortes, barras de cine, huesos como tubos que brillan, una estela de luz en la muñeca del
// reloj, polvo en el aire, frases cortas y música (musica.js): un colchón de acordes y una nota en cada clic,
// toque o paso. F o el botón Comercial entra y sale; Esc sale. Usa la escena de mocap.js (LAST: el último cuadro).
'use strict';

const FILM = (() => {
  const st = { on: false, built: false, shot: -1, prevT: null, music: null, trail: [], saved: null };
  const Y = (h) => new THREE.Vector3(0, h, 0);
  const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);
  const ease = (u) => (u <= 0 ? 0 : u >= 1 ? 1 : u * u * (3 - 2 * u));
  const midiHz = (m) => 440 * Math.pow(2, (m - 69) / 12);

  // ---------- planos: [desde, hasta, de (contexto → {pos, look}), a] ----------
  const SHOTS = {
    apuntar: [
      [0, 2.4, (c) => ({ pos: c.at(c.pel, [c.fwd, 2.1], [c.side, 1.3], [Y(1), 0.2]), look: c.chest }),
        (c) => ({ pos: c.at(c.pel, [c.fwd, 1.8], [c.side, 0.9], [Y(1), 0.45]), look: c.chest })],
      [2.4, 4.8, (c) => ({ pos: c.at(c.pel, [c.fwd, -1.6], [c.side, 0.95], [Y(1), 0.95]), look: c.scr }),
        (c) => ({ pos: c.at(c.pel, [c.fwd, -1.15], [c.side, 0.75], [Y(1), 0.85]), look: c.scr })],
      [4.8, 6.0, (c) => ({ pos: c.at(c.watch, [c.side, 0.24], [Y(1), 0.1], [c.F, -0.16]), look: c.watch }),
        (c) => ({ pos: c.at(c.watch, [c.side, 0.17], [Y(1), 0.17], [c.F, 0.04]), look: c.watch })],
      [6.0, 9.0, (c) => ({ pos: c.at(c.pel, [c.fwd, -2.2], [c.side, -1.2], [Y(1), 1.5]), look: c.chest.clone().lerp(c.scr, 0.8) }),   // alto, por el otro hombro: la pantalla de frente
        (c) => ({ pos: c.at(c.pel, [c.fwd, -1.7], [c.side, -0.7], [Y(1), 1.2]), look: c.chest.clone().lerp(c.scr, 0.8) })],
      [9.0, 10.0, (c) => ({ pos: c.at(c.pel, [c.fwd, -2.0], [Y(1), 1.2]), look: c.scr }),
        (c) => ({ pos: c.at(c.pel, [c.fwd, -2.8], [Y(1), 2.0]), look: c.scr })],
    ],
    caminar: [
      [0, 3.2, (c) => ({ pos: c.at(c.pel, [c.right, 2.3], [Y(1), 0.35], [c.fwd, -0.4]), look: c.chest }),
        (c) => ({ pos: c.at(c.pel, [c.right, 2.0], [Y(1), 0.25], [c.fwd, 0.4]), look: c.chest })],
      [3.2, 5.2, (c) => ({ pos: c.at(c.watch, [c.side, 0.5], [Y(1), 0.12], [c.fwd, 0.18]), look: c.watch }),
        (c) => ({ pos: c.at(c.watch, [c.side, 0.38], [Y(1), 0.2], [c.fwd, -0.1]), look: c.watch })],
      [5.2, 99, (c) => ({ pos: c.at(c.pel, [c.fwd, 3.0], [Y(1), 0.45]), look: c.at(c.pel, [Y(1), 0.6]) }),
        (c) => ({ pos: c.at(c.pel, [c.fwd, 3.6], [Y(1), 2.2], [c.right, 1.0]), look: c.at(c.pel, [Y(1), 0.5]) })],
    ],
    tablet: [
      [0, 3, (c) => ({ pos: c.at(c.pel, [c.turn(0.6), 2.2], [Y(1), 0.6]), look: c.chest }),
        (c) => ({ pos: c.at(c.pel, [c.turn(1.1), 2.0], [Y(1), 0.5]), look: c.chest })],
      [3, 5.5, (c) => ({ pos: c.at(c.tab, [Y(1), 0.45], [c.side, 0.35], [c.fwd, -0.25]), look: c.tab }),
        (c) => ({ pos: c.at(c.tab, [Y(1), 0.33], [c.side, 0.24], [c.fwd, -0.08]), look: c.tab })],
      [5.5, 99, (c) => ({ pos: c.at(c.pel, [c.fwd, 2.4], [Y(1), 0.1]), look: c.chest }),
        (c) => ({ pos: c.at(c.pel, [c.fwd, 1.7], [Y(1), 0.35]), look: c.chest })],
    ],
  };
  const CAPS = {
    apuntar: [[0.3, 2.3, 'Apunta.'], [2.5, 4.7, 'Un giro de muñeca es un clic.'], [6.1, 8.9, 'Dibuja en el aire.'], [9.05, 9.95, 'Tu reloj ya es un cursor.']],
    caminar: [[0.4, 3.0, 'Cada paso.'], [3.3, 5.1, 'Cada giro de tu muñeca.'], [5.5, 8.6, 'Cien veces por segundo.']],
    tablet: [[0.4, 2.8, 'Toca.'], [3.2, 5.4, 'Cada toque deja una huella.'], [5.7, 7.8, 'Y tu reloj lo siente.']],
  };
  // momentos que suenan: [segundo, nota MIDI, color del instrumento en musica.js]
  function events(src, dur) {
    if (src === 'apuntar') return [0, 1, 2, 3].map((i) => [0.6 + 1.2 * i + 0.82, [72, 76, 79, 84][i], '#58c4dd']).concat([[6.0, 67, '#f0997b'], [9.0, 72, '#58c4dd']]);
    if (src === 'tablet') return Array.from({ length: 16 }, (_, n) => [n * 0.5 + 0.3, [67, 69, 72, 74, 76, 79][n % 6], '#5dcaa5']);
    if (src === 'caminar') return Array.from({ length: 16 }, (_, n) => [n * dur / 16, n % 2 ? 43 : 48, '#ece9e1']);
    return [];
  }

  // ---------- objetos (se crean la primera vez) ----------
  let group, bones, joints, glows, headF, trailMesh, dust, floor;
  function texGlow() {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d'), r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.25, 'rgba(255,255,255,0.45)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }
  function texFloor() {
    const c = document.createElement('canvas'); c.width = c.height = 512;
    const g = c.getContext('2d'), r = g.createRadialGradient(256, 256, 0, 256, 256, 256);
    r.addColorStop(0, 'rgba(70,150,190,0.45)'); r.addColorStop(0.35, 'rgba(40,80,120,0.18)'); r.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = r; g.fillRect(0, 0, 512, 512);
    return new THREE.CanvasTexture(c);
  }
  function build3d() {
    group = new THREE.Group(); scene.add(group);
    const glowT = texGlow();
    const boneM = new THREE.MeshStandardMaterial({ color: 0xe6eef8, emissive: 0x1d4a5c, roughness: 0.35, metalness: 0.15 });
    const cyl = new THREE.CylinderGeometry(1, 1, 1, 10);
    bones = Array.from({ length: 48 }, () => { const m = new THREE.Mesh(cyl, boneM); group.add(m); return m; });
    const jm = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x3a8fb0, roughness: 0.25 });
    const sph = new THREE.SphereGeometry(1, 16, 12);
    joints = Array.from({ length: 48 }, () => { const m = new THREE.Mesh(sph, jm); group.add(m); return m; });
    glows = Array.from({ length: 48 }, () => {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowT, color: 0x6fd6ff, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false }));
      group.add(s); return s;
    });
    headF = new THREE.Mesh(new THREE.SphereGeometry(0.085, 32, 24), new THREE.MeshStandardMaterial({ color: 0xf2f6fb, emissive: 0x16323f, roughness: 0.2, metalness: 0.1 }));
    group.add(headF);
    st.watchGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowT, color: 0x3fffd2, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }));
    st.watchGlow.scale.set(0.28, 0.28, 1); group.add(st.watchGlow);
    st.band = new THREE.Mesh(new THREE.TorusGeometry(0.016, 0.0045, 10, 28), new THREE.MeshStandardMaterial({ color: 0x1b2230, roughness: 0.6 }));
    group.add(st.band);
    trailMesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    trailMesh.frustumCulled = false; group.add(trailMesh);
    const N = 600, p = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) p.set([(Math.random() - 0.5) * 10, Math.random() * 4, (Math.random() - 0.5) * 10 - 1], i * 3);
    const dg = new THREE.BufferGeometry(); dg.setAttribute('position', new THREE.BufferAttribute(p, 3));
    dust = new THREE.Points(dg, new THREE.PointsMaterial({ size: 0.035, map: glowT, color: 0x7fb8ff, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
    dust.frustumCulled = false; group.add(dust);
    floor = new THREE.Mesh(new THREE.PlaneGeometry(9, 9), new THREE.MeshBasicMaterial({ map: texFloor(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    floor.rotation.x = -Math.PI / 2; floor.position.y = 0.003; group.add(floor);
    const rim = new THREE.DirectionalLight(0x58c4dd, 1.1); rim.position.set(-3, 3, 4); group.add(rim);
    const key = new THREE.DirectionalLight(0xffd6ae, 0.9); key.position.set(3, 4, -3); group.add(key);
    st.built = true;
  }

  // ---------- entrar y salir ----------
  function toggle() {
    st.on = !st.on;
    document.body.classList.toggle('film', st.on);
    if (st.on) {
      if (!st.built) build3d();
      st.saved = { bg: scene.background, fog: scene.fog, fov: cam.fov };
      scene.background = null; scene.fog = new THREE.Fog(0x070a10, 6, 17);
      cam.fov = 34; cam.updateProjectionMatrix();
      ctl.enabled = false; st.shot = -1; st.prevT = null; st.trail.length = 0;
      group.visible = true;
      if (typeof Musica !== 'undefined') {
        st.music = st.music || new Musica();
        st.music.unlock(); st.music.mode = 'arpa';         // sin guardar: Dibuja conserva su modo
      }
      const h = document.getElementById('film-hint'); h.style.opacity = 1; setTimeout(() => { h.style.opacity = 0; }, 2500);
    } else {
      scene.background = st.saved.bg; scene.fog = st.saved.fog; cam.fov = st.saved.fov; cam.updateProjectionMatrix();
      group.visible = false; ctl.enabled = true;
      if (st.music) { st.music.mode = 'off'; st.music.padOff(); }
      const b = LAST && LAST.b;
      if (b) ctl.target.set(b.pelvis[0], b.pelvis[1] + 0.18, b.pelvis[2]);
    }
    setTimeout(resize, 0);
  }

  // ---------- la cámara ----------
  function context(b, P, w) {
    const fwd = new THREE.Vector3(-Math.sin(P.H), 0, -Math.cos(P.H)), right = new THREE.Vector3(Math.cos(P.H), 0, -Math.sin(P.H));
    const a = b.arms[S.side], side = right.clone().multiplyScalar(S.side === 'l' ? -1 : 1);
    const chest = V(b.pts[1]), scr = V(ANIMS.apuntar.screen.c);
    const c = {
      pel: V(b.pelvis), chest, fwd, right, side, F: V(a.F), watch: V(w.p), scr,
      mid: chest.clone().lerp(scr, 0.5), tab: b.tablet ? V(b.tablet.c) : chest,
      turn: (ang) => fwd.clone().applyAxisAngle(Y(1), ang),
      at: (base, ...terms) => terms.reduce((acc, [dir, k]) => acc.addScaledVector(dir, k), base.clone()),
    };
    return c;
  }
  function camera(b, P, w) {
    const c = context(b, P, w);
    let shots = SHOTS[S.src];
    if (!shots) {                          // tus grabaciones: una órbita lenta
      const u = S.t / S.dur;
      shots = [[0, 99, () => ({ pos: c.at(c.pel, [c.turn(0.5 + 1.4 * u), 2.3], [Y(1), 0.75]), look: c.at(c.pel, [Y(1), 0.45]) }),
        () => ({ pos: c.at(c.pel, [c.turn(0.5 + 1.4 * u), 2.3], [Y(1), 0.75]), look: c.at(c.pel, [Y(1), 0.45]) })]];
    }
    let i = shots.findIndex(([a, z]) => S.t >= a && S.t < z);
    if (i < 0) i = shots.length - 1;
    const [a, z, from, to] = shots[i], u = ease((S.t - a) / (Math.min(z, S.dur) - a));
    const A = from(c), B = to(c);
    cam.position.copy(A.pos.lerp(B.pos, u));
    cam.lookAt(A.look.lerp(B.look, u));
    if (i !== st.shot) {                   // corte: un parpadeo a negro, como en los anuncios
      if (st.shot !== -1) {
        const dip = document.getElementById('film-dip');
        dip.style.transition = 'none'; dip.style.opacity = 0.9;
        requestAnimationFrame(() => { dip.style.transition = 'opacity .35s ease-out'; dip.style.opacity = 0; });
      }
      st.shot = i;
    }
  }

  // ---------- cada cuadro ----------
  function update(dt) {
    if (!LAST) return;
    const { b, w } = LAST;
    // lo de la vista técnica se esconde; queda el reloj, la tablet y la pantalla
    for (const o of [body.pts, body.lines, ghost.pts, ghost.lines, headM, aUp, aW, aLin, trail, grid]) o.visible = false;
    // huesos como tubos, articulaciones con brillo
    const up = new THREE.Vector3(0, 1, 0), q = new THREE.Quaternion();
    b.segs.forEach(([p0, p1], i) => {
      const A = V(p0), B = V(p1), d = B.clone().sub(A), L = d.length(), m = bones[i];
      m.visible = L > 1e-4;
      if (!m.visible) return;
      const r = L < 0.11 ? 0.0055 : 0.012;
      m.position.copy(A).addScaledVector(d, 0.5); m.quaternion.copy(q.setFromUnitVectors(up, d.normalize())); m.scale.set(r, L, r);
    });
    for (let i = b.segs.length; i < bones.length; i++) bones[i].visible = false;
    b.pts.forEach((p, i) => {
      const r = i > 3 ? 0.012 : 0.018;     // los primeros cuatro son la columna
      joints[i].visible = true; joints[i].position.set(p[0], p[1], p[2]); joints[i].scale.set(r, r, r);
      glows[i].visible = true; glows[i].position.set(p[0], p[1], p[2]); glows[i].scale.set(0.07, 0.07, 1);
    });
    for (let i = b.pts.length; i < joints.length; i++) { joints[i].visible = false; glows[i].visible = false; }
    headF.position.set(b.head[0], b.head[1], b.head[2]);
    st.watchGlow.position.set(w.p[0], w.p[1], w.p[2]);
    const arm = b.arms[S.side], F = V(arm.F);                // la correa abraza el antebrazo bajo el reloj
    st.band.position.copy(V(arm.wr)).addScaledVector(F, -0.035);
    st.band.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), F);
    // estela de luz del reloj: un tubo que se apaga hacia atrás
    st.trail.push(V(w.p)); if (st.trail.length > 70) st.trail.shift();
    if (st.trail.length >= 4) {
      const segs = st.trail.length * 2, rad = 6;
      const geo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(st.trail), segs, 0.007, rad, false);
      const n = geo.attributes.position.count, col = new Float32Array(n * 3), per = rad + 1;
      for (let v = 0; v < n; v++) { const f = Math.pow(Math.floor(v / per) / segs, 1.6); col.set([0.25 * f, 1.0 * f, 0.82 * f], v * 3); }
      geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
      trailMesh.geometry.dispose(); trailMesh.geometry = geo;
    }
    // polvo que sube despacio y el piso que brilla bajo los pies
    const dp = dust.geometry.attributes.position;
    for (let i = 0; i < dp.count; i++) { let y = dp.getY(i) + 0.06 * dt; if (y > 4) y = 0; dp.setY(i, y); }
    dp.needsUpdate = true;
    floor.position.set(b.pelvis[0], 0.003, b.pelvis[2]);
    // frases
    const caps = CAPS[S.src] || [[0.5, Math.min(4.5, S.dur - 0.2), S.take ? S.take.nombre : '']];
    const cur = caps.find(([a, z]) => S.t >= a && S.t <= z), capEl = document.getElementById('film-cap');
    if (cur) {
      capEl.textContent = cur[2];
      capEl.style.opacity = Math.min(1, (S.t - cur[0]) / 0.35, (cur[1] - S.t) / 0.35).toFixed(2);
    } else capEl.style.opacity = 0;
    // música: el colchón sigue sonando y cada evento toca su nota
    const mu = st.music;
    if (mu && mu.ready) {
      mu.lastActive = mu.ctx.currentTime;
      if (st.prevT !== null && S.playing) {
        const a = st.prevT, z = S.t, wrapped = z < a;
        for (const [t, m, color] of events(S.src, S.dur)) {
          if (wrapped ? (t >= a || t < z) : (t >= a && t < z)) mu.note(midiHz(m), mu.timbre(color), S.side === 'l' ? -0.3 : 0.3, 6000, 0.28, 0.6);
        }
      }
    }
    st.prevT = S.t;
  }

  return { get on() { return st.on; }, get shot() { return st.shot; }, toggle, camera, update };
})();

document.getElementById('film').addEventListener('click', () => FILM.toggle());
