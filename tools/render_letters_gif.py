"""GIF letra por letra: el trazo del dedo en el trackpad (cian) y lo que reconstruye el reloj (coral).

    python tools/render_letters_gif.py recordings/dibujo-AAAAMMDD-HHMMSS [--modo global|forma]

Necesita <grabación>/letters.json: {"mayúsculas": [["A", [31, 32]], ...], "minúsculas": [...]} con los
índices de trazo de cada letra (en el orden de strokes_from). El reloj usa UNA calibración lineal para
toda la grabación (giro de muñeca integrado + aceleración integrada; ver analyze_drawing.py).
  --modo global: tal cual sale de esa calibración (el reloj dibuja más pequeño: ve sobre todo la muñeca).
  --modo forma: además, cada letra se escala con un solo número para igualar su tamaño al real, para
                comparar la forma; así lo dice el título del GIF.
Cada trazo coral arranca donde arranca el real: el reloj ve la forma del trazo, no dónde se apoya el dedo.
El número bajo cada letra es el parecido de forma (correlación, 1 = idéntica).
"""
import argparse
import json
import os
import sys

import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from analyze_drawing import load_sensor, load_touch, r2, strokes_from, watch_features  # noqa: E402

TRUE_C, PRED_C, BG, FG = "#58c4dd", "#f0997b", "#11151c", "#9aa3b2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--modo", choices=("global", "forma"), default="forma")
    ap.add_argument("--out")
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--hold", type=int, default=18)
    ap.add_argument("--fps", type=int, default=14)
    ap.add_argument("--cols", type=int, default=9)
    args = ap.parse_args()
    out = args.out or os.path.join(ROOT, "docs", "media", f"letras-{args.modo}.gif")

    touch = load_touch(args.folder)
    acc, gyr, grv = (load_sensor(args.folder, n) for n in ("ACCELERATION", "GYROSCOPE", "GRAVITY"))
    tips = touch[touch[:, 3] == 1]
    ids, counts = np.unique(tips[:, 2], return_counts=True)
    strokes = strokes_from(touch, ids[np.argmax(counts)])
    feats = [watch_features(s, acc, gyr, grv) for s in strokes]
    fit = [(f[1], np.hstack([f[2], f[3]])) for s, f in zip(strokes, feats) if f is not None and s[-1, 0] - s[0, 0] >= 250]
    _, coef = r2(np.vstack([a for a, _ in fit]), np.vstack([b for _, b in fit]))

    def stroke_pair(i):
        s, f = strokes[i], feats[i]
        if f is None:                                     # trazo cortísimo (un punto): sin reconstrucción
            return s[:, 4:6], None, s[:, 0]
        t, _, ang, pos = f
        pred = np.hstack([ang, pos, np.ones((len(t), 1))]) @ coef
        true = np.stack([np.interp(t, s[:, 0], s[:, 4]), np.interp(t, s[:, 0], s[:, 5])], axis=1)
        return true, pred - pred[0], t

    letters = json.load(open(os.path.join(args.folder, "letters.json"), encoding="utf-8"))
    items = []
    for block in ("mayúsculas", "minúsculas"):
        for name, ix in letters.get(block, []):
            pairs = [stroke_pair(i) for i in ix if i < len(strokes)]
            if not pairs:
                continue
            # parecido de forma de la letra: correlación entre desplazamientos reales y reconstruidos
            tr = np.vstack([p[0] - p[0][0] for p in pairs if p[1] is not None] or [np.zeros((1, 2))])
            pr = np.vstack([p[1] for p in pairs if p[1] is not None] or [np.zeros((1, 2))])
            a_, b_ = (tr - tr.mean(0)).ravel(), (pr - pr.mean(0)).ravel()
            sim = float(a_ @ b_ / (np.linalg.norm(a_) * np.linalg.norm(b_) + 1e-9))
            k = 1.0
            if args.modo == "forma" and np.linalg.norm(b_) > 1e-6:
                k = float(np.linalg.norm(a_) / np.linalg.norm(b_))          # un solo número por letra
            items.append((name, [(p[0], None if p[1] is None else p[0][0] + k * p[1], p[2]) for p in pairs], sim))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    n = len(items)
    cols = min(args.cols, n)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(1.3 * cols, 1.42 * rows + 0.6), facecolor=BG)
    axes = np.atleast_1d(axes).ravel()
    title = ("cian: tu dedo en el trackpad  ·  coral: el reloj (una calibración; tamaño igualado por letra)" if args.modo == "forma"
             else "cian: tu dedo en el trackpad  ·  coral: el reloj (una sola calibración, sin retoques)")
    fig.suptitle(title, color=FG, fontsize=8.5, y=0.99)
    panels = []
    for i, ax in enumerate(axes):
        ax.set_facecolor(BG)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        if i >= n:
            continue
        name, pairs, sim = items[i]
        pts = np.vstack([p[0] for p in pairs] + [p[1] for p in pairs if p[1] is not None])
        lo, hi = np.percentile(pts, 2, axis=0), np.percentile(pts, 98, axis=0)
        c, half = (lo + hi) / 2, max(hi - lo) / 2 * 1.25 + 2
        ax.set_xlim(c[0] - half, c[0] + half); ax.set_ylim(c[1] + half, c[1] - half)
        ax.set_aspect("equal")
        ax.set_title(f"{name}  ", color="#ece9e1", fontsize=10, pad=1, loc="center")
        ax.text(0.98, 1.02, f"{sim:.2f}", transform=ax.transAxes, ha="right", va="bottom", color=FG, fontsize=6.5)
        lines = [(p, ax.plot([], [], color=TRUE_C, lw=1.9, solid_capstyle="round")[0],
                  ax.plot([], [], color=PRED_C, lw=1.4, solid_capstyle="round")[0]) for p in pairs]
        dur = np.array([max(1.0, p[2][-1] - p[2][0]) for p in pairs])
        panels.append((lines, np.concatenate([[0], np.cumsum(dur)])))
    fig.tight_layout(rect=(0, 0, 1, 0.95), pad=0.3, h_pad=0.9)

    def frame(k):
        f = min(1.0, k / args.frames)
        for lines, cum in panels:
            tt = f * cum[-1]
            for j, (p, lt, lp) in enumerate(lines):
                part = np.clip((tt - cum[j]) / max(1e-9, cum[j + 1] - cum[j]), 0, 1)
                m = int(round(part * len(p[0])))
                lt.set_data(p[0][:m, 0], p[0][:m, 1])
                if p[1] is not None:
                    lp.set_data(p[1][:m, 0], p[1][:m, 1])
        return []

    os.makedirs(os.path.dirname(out), exist_ok=True)
    FuncAnimation(fig, frame, frames=args.frames + args.hold).save(out, writer=PillowWriter(fps=args.fps), dpi=85,
                                                                  savefig_kwargs={"facecolor": BG})
    frame(args.frames)
    fig.savefig(os.path.splitext(out)[0] + ".png", dpi=105, facecolor=BG)
    sims = [s for _, _, s in items]
    print(f"{out} ({os.path.getsize(out) / 1e6:.1f} MB) · {n} letras · parecido de forma mediano {np.median(sims):.2f}")
    best = sorted(items, key=lambda x: -x[2])
    print("  mejores:", ", ".join(f"{a} {s:.2f}" for a, _, s in best[:6]), "· peores:", ", ".join(f"{a} {s:.2f}" for a, _, s in best[-6:]))


if __name__ == "__main__":
    main()
