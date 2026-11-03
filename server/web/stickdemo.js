// El muñeco que muestra cada paso de la grabación del curso (las poses están en cursodemos.js): puntos y
// huesos en tubos con un brillo suave (sin esfera en la cabeza), el reloj con sus ejes x y z, la gravedad
// cuando importa, y la mesa con la laptop. Un escenario se puede dibujar con cualquier renderer (poses.html
// usa uno solo para todas las tarjetas): stage.set(id, t, side), stage.aim(camera, null, side) y
// renderer.render(stage.scene, camera).
'use strict';

const StickDemo = (() => {
  const COL = { joint: 0x58c4dd, bone: 0xcfd6e4, up: 0xffd166, desk: 0x1a2130, flash: 0xffd166, ray: 0x58c4dd };
  const AXC = ['#a99bff', '#f28ab2', '#ff9a6b'];          // x, y, z como en las gráficas del mocap
  const V3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);
  const basis = (x, y, z, p) => new THREE.Matrix4().makeBasis(V3(x), V3(y), V3(z)).setPosition(p[0], p[1], p[2]);
  const CAMS = {                             // en diagonal, del lado del reloj (k = ±1), como el teléfono
    cuerpo: (k) => ({ pos: [2.2 * k, 1.5, -1.75], look: [0.05 * k, 1.0, -0.2] }),
    brazo: (k) => ({ pos: [1.05 * k, 1.45, -0.95], look: [0.12 * k, 1.17, -0.15] }),
  };
  // de cerca: la cámara se pone respecto de la mano del reloj (o del reloj en la mesa) al empezar el paso
  const NEAR = {
    mano: (k) => [0.6 * k, 0.23, -0.42],
    perfil: (k) => [0.8 * k, 0.07, -0.02],   // inclinar: la mano sube y baja
    arriba: (k) => [0.3 * k, 0.72, -0.12],   // girar: a un lado y al otro
    gesto: (k, a) => {                       // pellizco y puño: del lado del pulgar, un poco adelante
      const thumb = vec.mul(vec.cross(a.F, a.d), -a.k);
      return [0, 1, 2].map((i) => thumb[i] * 0.4 + a.F[i] * 0.12 + a.d[i] * 0.06);
    },
    mesa: (k) => [0.5 * k, 0.45, 0.55],      // el reloj solo en la mesa, con la laptop detrás
  };
  const JOINT = { cuerpo: 1, brazo: 0.75, mano: 0.45, perfil: 0.45, arriba: 0.45, gesto: 0.4 };   // de cerca, bolitas más chicas

  function texGlow() {
    const c = document.createElement('canvas'); c.width = c.height = 64;
    const g = c.getContext('2d'), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.3, 'rgba(255,255,255,0.4)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  }
  function texText(s, color) {
    const c = document.createElement('canvas'); c.width = c.height = 64;
    const g = c.getContext('2d');
    g.font = 'bold 44px system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillStyle = color; g.fillText(s, 32, 34);
    return new THREE.CanvasTexture(c);
  }

  function create() {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0e14); scene.fog = new THREE.Fog(0x0b0e14, 4, 11);
    scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x1a1f2a, 0.9));
    const key = new THREE.DirectionalLight(0xffffff, 0.7); key.position.set(3, 5, -2); scene.add(key);
    scene.add(new THREE.GridHelper(10, 20, 0x2a3344, 0x161c27));
    const glowT = texGlow();
    const add = (o) => { o.frustumCulled = false; scene.add(o); return o; };
    const MAX = 64;
    const joints = add(new THREE.InstancedMesh(new THREE.SphereGeometry(0.016, 10, 8), new THREE.MeshBasicMaterial({ color: COL.joint }), MAX));
    const glowGeo = new THREE.BufferGeometry(); glowGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAX * 3), 3));
    const glows = add(new THREE.Points(glowGeo, new THREE.PointsMaterial({ size: 0.075, map: glowT, color: 0x6fd6ff, transparent: true, opacity: 0.45, blending: THREE.AdditiveBlending, depthWrite: false })));
    // huesos como tubos (como el modo comercial): de cerca, los dedos se ven como dedos
    const bones = add(new THREE.InstancedMesh(new THREE.CylinderGeometry(1, 1, 1, 8), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x1d4a5c, roughness: 0.4 }), MAX));
    const boneCol = new THREE.Color(COL.bone), pickCol = new THREE.Color(0xffb020);
    for (let i = 0; i < MAX; i++) bones.setColorAt(i, boneCol);
    // el reloj: caja, pantalla verde, brillo, y sus tres ejes con letra
    const watch = new THREE.Group(); watch.matrixAutoUpdate = false; scene.add(watch);
    watch.add(new THREE.Mesh(new THREE.BoxGeometry(0.046, 0.012, 0.046), new THREE.MeshStandardMaterial({ color: 0x3a3f4a, roughness: 0.4, metalness: 0.4 })));
    const face = new THREE.Mesh(new THREE.BoxGeometry(0.038, 0.002, 0.038), new THREE.MeshStandardMaterial({ color: 0x1d9e75, emissive: 0x1d9e75, emissiveIntensity: 0.6 }));
    face.position.y = 0.007; watch.add(face);
    const wGlow = add(new THREE.Sprite(new THREE.SpriteMaterial({ map: glowT, color: 0x3fffd2, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false })));
    wGlow.scale.set(0.11, 0.11, 1);
    const axes = AXC.map((c, i) => {
      const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
      const line = add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color: c })));
      const label = add(new THREE.Sprite(new THREE.SpriteMaterial({ map: texText('xyz'[i], c), transparent: true, depthWrite: false })));
      label.scale.set(0.055, 0.055, 1);
      return { line, label };
    });
    const gArrow = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(), 0.2, COL.up, 0.035, 0.018); scene.add(gArrow);
    const rayGeo = new THREE.BufferGeometry(); rayGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
    const ray = add(new THREE.Line(rayGeo, new THREE.LineBasicMaterial({ color: COL.ray, transparent: true, opacity: 0.4 })));
    const flash = add(new THREE.Sprite(new THREE.SpriteMaterial({ map: glowT, color: COL.flash, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false })));
    flash.scale.set(0.22, 0.22, 1);
    // la mesa (con patas) y la laptop abierta mirando al muñeco
    const D = DESK, deskM = new THREE.MeshStandardMaterial({ color: COL.desk, roughness: 0.8 });
    const top = new THREE.Mesh(new THREE.BoxGeometry(D.w, 0.03, D.z0 - D.z1), deskM);
    top.position.set(0, D.y - 0.015, (D.z0 + D.z1) / 2); scene.add(top);
    for (const [x, z] of [[-1, D.z0 + 0.04], [1, D.z0 + 0.04], [-1, D.z1 - 0.04], [1, D.z1 - 0.04]]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.03, D.y - 0.03, 0.03), deskM);
      leg.position.set(x * (D.w / 2 - 0.04), (D.y - 0.03) / 2, z); scene.add(leg);
    }
    const lapM = new THREE.MeshStandardMaterial({ color: 0x2a3140, roughness: 0.5, metalness: 0.3 });
    const base = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.014, 0.22), lapM); base.position.set(-0.12, D.y + 0.007, -0.86); scene.add(base);
    const lid = new THREE.Group(); lid.position.set(-0.12, D.y + 0.014, -0.97); lid.rotation.x = 0.28; scene.add(lid);
    const lidM = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.21, 0.01), lapM); lidM.position.y = 0.105; lid.add(lidM);
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.29, 0.18), new THREE.MeshBasicMaterial({ color: 0x163a4a })); scr.position.set(0, 0.105, 0.006); lid.add(scr);

    const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _y = new THREE.Vector3(0, 1, 0);
    let info = { up: null };

    function set(id, t, side) {
      const demo = DEMOS[id];
      const r = demo.at(t, side), b = build(r.P), js = JOINT[demo.cam] || 1;
      // puntos, brillo y huesos
      for (const o of [joints, bones]) o.visible = r.body !== false;
      glows.visible = r.body !== false && js >= 0.7;     // de cerca el brillo tapa los dedos
      joints.count = b.pts.length;
      glows.material.size = 0.075 * js;
      const gp = glowGeo.attributes.position.array;
      b.pts.forEach((p, i) => { _m.makeScale(js, js, js).setPosition(p[0], p[1], p[2]); joints.setMatrixAt(i, _m); gp.set(p, i * 3); });
      joints.instanceMatrix.needsUpdate = true;
      glowGeo.setDrawRange(0, b.pts.length); glowGeo.attributes.position.needsUpdate = true;
      // en el pellizco, pulgar e índice en amarillo: los segmentos que coinciden con los de esa mano
      let pick = [];
      if (r.flashAt === 'pinza') {
        const A = r.P.arms[side], arm = b.arms[side], h = hand(arm.wr, arm.F, arm.d, arm.k, A.fist || 0, A.pinch);
        const i = arm.k > 0 ? 0 : 3;                    // el índice: el dedo del lado del pulgar
        pick = [h.pts[2 * i], h.pts[2 * i + 1], h.pts[8], h.pts[9]];
      }
      const same = (p, q) => Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]) + Math.abs(p[2] - q[2]) < 1e-9;
      bones.count = b.segs.length;
      b.segs.forEach(([p, q], i) => {
        const dir = V3(q).sub(V3(p)), L = dir.length(), rad = Math.min(0.011, Math.max(0.0042, L * 0.05));
        _q.setFromUnitVectors(_y, dir.clone().normalize());
        _m.compose(V3(p).addScaledVector(dir, 0.5), _q, _s.set(rad, L, rad));
        bones.setMatrixAt(i, _m);
        bones.setColorAt(i, pick.some((x) => same(x, q)) ? pickCol : boneCol);
      });
      bones.instanceMatrix.needsUpdate = true; bones.instanceColor.needsUpdate = true;
      // el reloj, en la muñeca o en la mesa
      const w = r.watch === 'muneca' ? watchOf(b, side) : r.watch;
      watch.matrix.copy(basis(w.X, w.Z, w.Y.map((v) => -v), w.p));
      wGlow.position.set(w.p[0], w.p[1], w.p[2]);
      [w.X, w.Y, w.Z].forEach((e, i) => {
        const L = i === 2 ? 0.1 : 0.08, tip = [w.p[0] + e[0] * L, w.p[1] + e[1] * L, w.p[2] + e[2] * L];
        axes[i].line.geometry.attributes.position.array.set([...w.p, ...tip]); axes[i].line.geometry.attributes.position.needsUpdate = true;
        axes[i].label.position.set(w.p[0] + e[0] * (L + 0.02), w.p[1] + e[1] * (L + 0.02), w.p[2] + e[2] * (L + 0.02));
      });
      gArrow.visible = !!r.gravity;
      if (r.gravity) gArrow.position.set(w.p[0], w.p[1] + 0.01, w.p[2]);
      // apuntar: el rayo del antebrazo
      ray.visible = !!r.ray;
      if (r.ray) {
        const arm = b.arms[side], end = [arm.wr[0] + arm.F[0] * 1.6, arm.wr[1] + arm.F[1] * 1.6, arm.wr[2] + arm.F[2] * 1.6];
        rayGeo.attributes.position.array.set([...arm.wr, ...end]); rayGeo.attributes.position.needsUpdate = true;
      }
      // el destello del gesto, en la mano del reloj o entre las dos manos
      flash.material.opacity = 0.9 * (r.flash || 0);
      if (r.flash) {
        const arm = b.arms[side], o = b.arms[side === 'l' ? 'r' : 'l'], S = vec.cross(arm.F, arm.d);
        const p = r.flashAt === 'manos' ? arm.wr.map((v, i) => (v + o.wr[i]) / 2)
          : r.flashAt === 'pinza' ? arm.wr.map((v, i) => v + arm.F[i] * 0.115 - arm.k * S[i] * 0.035 - arm.d[i] * 0.035)
            : arm.wr.map((v, i) => v + arm.F[i] * 0.1);
        flash.position.set(p[0], p[1], p[2]);
        flash.scale.setScalar(r.flashAt === 'pinza' ? 0.08 : 0.22);
      }
      info = { up: upAxis(w), cam: demo.cam, id, side };
      return info;
    }

    // la cámara del paso; las de cerca miran la mano (o el reloj en la mesa) de la pose en t = 0
    const near = {};
    function aim(camera, which, side) {
      const name = which || info.cam || 'cuerpo', k = side === 'l' ? -1 : 1;
      let c;
      if (NEAR[name]) {
        const key = `${info.id}/${side}/${name}`;
        if (!near[key]) {
          const r0 = DEMOS[info.id].at(0, side), b0 = build(r0.P), a0 = b0.arms[side];
          const look = r0.watch === 'muneca' ? a0.wr.map((v, i) => v + a0.F[i] * (name === 'gesto' ? 0.09 : 0.06)) : r0.watch.p;
          near[key] = { look, pos: look.map((v, i) => v + NEAR[name](k, a0)[i]) };
        }
        c = near[key];
      } else c = CAMS[name](k);
      camera.position.set(...c.pos); camera.lookAt(...c.look);
      return c;
    }

    return { scene, set, aim, info: () => info };
  }

  return { create, CAMS };
})();
