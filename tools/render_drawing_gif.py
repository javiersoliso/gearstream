"""GIF de una grabación de draw_recorder.py: el trazo real del dedo (trackpad) y lo que reconstruye el reloj.

    python tools/render_drawing_gif.py recordings/dibujo-AAAAMMDD-HHMMSS [--out docs/media/reconstruccion.gif]

Cada grupo de trazos (separados por pausas) se anima a la vez. Cian: el dedo en el trackpad, la verdad.
Coral: el reloj, con UNA sola calibración lineal para todo el dibujo (ángulos de muñeca integrados más la
aceleración integrada dos veces), la misma que da el R² global de analyze_drawing.py. El reloj no sabe
dónde empieza cada trazo en el trackpad, solo su forma: cada trazo coral arranca donde arranca el real.
También imprime la calibración del giro (mm de trazo por grado de muñeca en cada eje y el cruce entre
ejes), que es lo que sirve para ajustar el ratón aéreo.
"""
import argparse
import os
import sys

import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from analyze_drawing import (groups_by_pause, load_sensor, load_touch, r2, strokes_from,  # noqa: E402
                             watch_features)

TRUE_C, PRED_C, BG, FG = "#58c4dd", "#f0997b", "#11151c", "#9aa3b2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "media", "reconstruccion.gif"))
    ap.add_argument("--frames", type=int, default=56)
    ap.add_argument("--hold", type=int, default=16)
    ap.add_argument("--fps", type=int, default=14)
    ap.add_argument("--cols", type=int, default=9)
    args = ap.parse_args()

    touch = load_touch(args.folder)
    acc, gyr, grv = (load_sensor(args.folder, n) for n in ("ACCELERATION", "GYROSCOPE", "GRAVITY"))
    tips = touch[touch[:, 3] == 1]
    ids, counts = np.unique(tips[:, 2], return_counts=True)
    strokes = strokes_from(touch, ids[np.argmax(counts)])

    feats = [watch_features(s, acc, gyr, grv) for s in strokes]
    fit = [(f[1], np.hstack([f[2], f[3]]), f[2]) for s, f in zip(strokes, feats) if f is not None and s[-1, 0] - s[0, 0] >= 250]
    Y = np.vstack([a for a, _, _ in fit])
    score, coef = r2(Y, np.vstack([b for _, b, _ in fit]))
    score_rot, coef_rot = r2(Y, np.vstack([c for _, _, c in fit]))

    # calibración del giro: x_mm, y_mm ≈ A · (yaw, pitch) en grados
    A = coef_rot[:2].T * np.pi / 180                      # filas: x, y del trazo; columnas: yaw, pitch
    U, S, Vt = np.linalg.svd(A)
    yaw_mm, pitch_mm = np.linalg.norm(A[:, 0]), np.linalg.norm(A[:, 1])
    cross = np.degrees(np.arccos(abs(A[:, 0] @ A[:, 1]) / (yaw_mm * pitch_mm)))
    print(f"ajuste global: giro solo R² {score_rot:.2f} · giro + aceleración R² {score:.2f}")
    print(f"calibración del giro: {yaw_mm:.2f} mm por grado de yaw (horizontal), {pitch_mm:.2f} mm por grado de pitch (vertical)")
    print(f"  → para el mismo trazo mueves {pitch_mm / yaw_mm:.2f} veces menos la muñeca en vertical que en horizontal")
    print(f"  ángulo entre las direcciones que dibujan yaw y pitch: {cross:.0f}° (90° = sin cruce)")
    print(f"  matriz A (mm por grado) = [[{A[0, 0]:+.2f}, {A[0, 1]:+.2f}], [{A[1, 0]:+.2f}, {A[1, 1]:+.2f}]]")

    # trazos reconstruidos: misma calibración para todos, anclados en el punto de apoyo real
    recon = []
    for s, f in zip(strokes, feats):
        if f is None:
            recon.append((s[:, 4:6], None, s[:, 0]))
            continue
        t, _, ang, pos = f
        X = np.hstack([ang, pos, np.ones((len(t), 1))])
        pred = X @ coef
        pred = pred - pred[0] + s[0, 4:6]
        true = np.stack([np.interp(t, s[:, 0], s[:, 4]), np.interp(t, s[:, 0], s[:, 5])], axis=1)
        recon.append((true, pred, t))

    groups = groups_by_pause(strokes)
    idx, k = [], 0
    for g in groups:
        idx.append(list(range(k, k + len(g))))
        k += len(g)
    keep = [ix for ix in idx if sum(np.hypot(*np.diff(recon[i][0], axis=0).T).sum() for i in ix) > 8]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    n = len(keep)
    cols = min(args.cols, n)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(1.45 * cols, 1.45 * rows + 0.55), facecolor=BG)
    axes = np.atleast_1d(axes).ravel()
    fig.suptitle("cian: tu dedo en el trackpad  ·  coral: lo que reconstruye el reloj (una sola calibración)",
                 color=FG, fontsize=8.5, y=0.985)
    panels = []
    for ax_i, ax in enumerate(axes):
        ax.set_facecolor(BG)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        if ax_i >= n:
            continue
        ix = keep[ax_i]
        pts = np.vstack([recon[i][0] for i in ix])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        c, half = (lo + hi) / 2, max(hi - lo) / 2 * 1.35 + 2
        ax.set_xlim(c[0] - half, c[0] + half); ax.set_ylim(c[1] + half, c[1] - half)
        ax.set_aspect("equal")
        lines = []
        for i in ix:
            lt, = ax.plot([], [], color=TRUE_C, lw=1.8, solid_capstyle="round")
            lp, = ax.plot([], [], color=PRED_C, lw=1.3, alpha=0.95, solid_capstyle="round")
            lines.append((i, lt, lp))
        dur = np.array([max(1.0, recon[i][2][-1] - recon[i][2][0]) for i in ix])
        panels.append((lines, np.concatenate([[0], np.cumsum(dur)])))
    fig.tight_layout(rect=(0, 0, 1, 0.95), pad=0.25)

    def frame(k):
        f = min(1.0, k / args.frames)
        out = []
        for lines, cum in panels:
            tt = f * cum[-1]
            for j, (i, lt, lp) in enumerate(lines):
                true, pred, t = recon[i]
                part = np.clip((tt - cum[j]) / max(1e-9, cum[j + 1] - cum[j]), 0, 1)
                m = max(1, int(round(part * len(true)))) if part > 0 else 0
                lt.set_data(true[:m, 0], true[:m, 1])
                if pred is not None:
                    lp.set_data(pred[:m, 0], pred[:m, 1])
                out += [lt, lp]
        return out

    anim = FuncAnimation(fig, frame, frames=args.frames + args.hold, blit=False)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    anim.save(args.out, writer=PillowWriter(fps=args.fps), dpi=90, savefig_kwargs={"facecolor": BG})
    frame(args.frames)
    png = os.path.splitext(args.out)[0] + ".png"
    fig.savefig(png, dpi=110, facecolor=BG)
    print(f"GIF: {args.out} ({os.path.getsize(args.out) / 1e6:.1f} MB) · último cuadro: {png}")


if __name__ == "__main__":
    main()
