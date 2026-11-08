// Las poses de la grabación del curso, todas a la vez: una tarjeta por paso de curso-protocol.json con el
// muñeco haciendo lo que pide, y una vista grande (arrastra para girar) del paso elegido. Las tarjetas se
// dibujan con un solo renderer fuera de pantalla y se copian a su lienzo.
'use strict';

const $ = (id) => document.getElementById(id);
const fromUrl = new URLSearchParams(location.search).get('mano');
const S = { side: fromUrl ? (fromUrl === 'derecha' ? 'r' : 'l') : (loadHand() === 'right' ? 'r' : 'l'), steps: [], sel: 0, t0: performance.now(), prep: 3 };
const durOf = (st) => (st.cues ? st.cues.n * st.cues.period + 0.6 : st.secs);
// cada paso en bucle con su "prepárate" (t < 0, el reloj de la mesa baja ahí) y hasta 12 s de paso
const loopT = (sec, st) => (sec % (S.prep + Math.min(durOf(st), 12))) - S.prep;
const demoOf = (st) => st.demo || st.id;

// vista grande
const big = new THREE.WebGLRenderer({ canvas: $('big'), antialias: true });
big.setPixelRatio(Math.min(devicePixelRatio, 2));
const bigStage = StickDemo.create(), bigCam = new THREE.PerspectiveCamera(40, 1, 0.02, 40);
const ctl = new THREE.OrbitControls(bigCam, big.domElement); ctl.enableDamping = true;
function resize() { const w = $('bigwrap').clientWidth, h = $('bigwrap').clientHeight; big.setSize(w, h, false); bigCam.aspect = w / h; bigCam.updateProjectionMatrix(); }
new ResizeObserver(resize).observe($('bigwrap'));

// tarjetas
const TW = 320, TH = 220;
const small = new THREE.WebGLRenderer({ antialias: true }); small.setSize(TW, TH, false);
const smallStage = StickDemo.create(), smallCam = new THREE.PerspectiveCamera(40, TW / TH, 0.02, 40);
const tiles = [];

function select(i) {
  S.sel = i; S.t0 = performance.now();
  const st = S.steps[i];
  bigStage.set(demoOf(st), 0, S.side);
  const c = bigStage.aim(bigCam, null, S.side); ctl.target.set(...c.look); ctl.update();
  tiles.forEach((t, j) => t.el.classList.toggle('on', j === i));
  $('title').textContent = `${i + 1} · ${st.line}`;
  $('meta').textContent = [st.secs ? `${st.secs} s` : `${st.cues.n} pitidos, uno cada ${st.cues.period} s`,
    st.metronome ? `metrónomo ${st.metronome} Hz` : '', st.caps ? `cap. ${st.caps.join(', ')}` : ''].filter(Boolean).join(' · ');
  $('ballwrap').style.display = st.metronome ? 'block' : 'none';
}

function sideUI() { $('hand').textContent = 'Reloj: muñeca ' + (S.side === 'l' ? 'izquierda' : 'derecha'); }
$('hand').addEventListener('click', () => { S.side = S.side === 'l' ? 'r' : 'l'; saveHand(S.side === 'l' ? 'left' : 'right'); sideUI(); select(S.sel); });
addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') select((S.sel + 1) % S.steps.length);
  else if (e.key === 'ArrowLeft') select((S.sel + S.steps.length - 1) % S.steps.length);
  else if (e.key === 'm' || e.key === 'M') $('hand').click();
});

fetch('curso-protocol.json').then((r) => r.json()).then((p) => {
  S.steps = p.steps; S.prep = p.prep_s;
  const total = p.steps.reduce((a, st) => a + durOf(st) + p.prep_s, 0);
  $('sub').textContent = `${p.steps.length} pasos, unos ${Math.round(total / 60)} minutos. ${p.intro}`;
  p.steps.forEach((st, i) => {
    const el = document.createElement('button'); el.className = 'tile';
    const cv = document.createElement('canvas'); cv.width = TW; cv.height = TH;
    const up = document.createElement('span'); up.className = 'up';
    el.append(cv, up);
    const cap = document.createElement('div'); cap.className = 'cap';
    cap.innerHTML = `<b>${i + 1}</b> ${st.line}`;
    el.append(cap);
    el.addEventListener('click', () => { select(i); scrollTo({ top: 0, behavior: 'smooth' }); });
    $('grid').append(el);
    tiles.push({ el, ctx: cv.getContext('2d'), up, st });
  });
  sideUI(); resize(); select(0);
  requestAnimationFrame(frame);
});

let rr = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const st = S.steps[S.sel], dur = durOf(st), t = loopT((now - S.t0) / 1000, st);
  const info = bigStage.set(demoOf(st), t, S.side);
  ctl.update(); big.render(bigStage.scene, bigCam);
  $('upbig').textContent = st.id.startsWith('cara') ? `arriba: ${info.up}` : '';
  $('time').textContent = t < 0 ? `prepárate… ${Math.ceil(-t)}` : `${t.toFixed(1)} / ${dur.toFixed(0)} s`;
  const cue = st.cues && ((t - 0.3) % st.cues.period + st.cues.period) % st.cues.period < 0.25 && t > 0.25;
  $('beep').style.opacity = cue ? 1 : 0;
  if (st.metronome) $('ball').style.top = `${(1 - demoBall(t, st.metronome)) * 150}px`;
  // las tarjetas: unas pocas por cuadro, cada una con su propio reloj
  for (let n = 0; n < 6 && tiles.length; n++, rr = (rr + 1) % tiles.length) {
    const tl = tiles[rr], tt = loopT(now / 1000 + rr * 0.7, tl.st);
    const inf = smallStage.set(demoOf(tl.st), tt, S.side);
    smallStage.aim(smallCam, null, S.side);
    small.render(smallStage.scene, smallCam);
    tl.ctx.drawImage(small.domElement, 0, 0);
    tl.up.textContent = tl.st.id.startsWith('cara') ? `arriba ${inf.up}` : '';
  }
}
