"""Análisis de una grabación de draw_recorder.py: el trackpad como verdad, el reloj como aprendiz.

    python tools/analyze_drawing.py recordings/dibujo-AAAAMMDD-HHMMSS

1. Tasas reales: el trackpad por su Scan Time (su propio reloj, 100 µs) mientras el dedo toca; el reloj
   en muestras y lecturas nuevas por segundo.
2. Trazos: del trackpad, cada vez que el dedo apoya y levanta. Dibuja todo en dibujo.png, por grupos
   separados por pausas (letras, figuras), para ver qué se dibujó.
3. Apoyar y levantar el dedo: ¿deja un golpe en el acelerómetro del reloj? Pico del golpe (aceleración
   menos su media de 40 ms) en ±80 ms de cada apoyo y cada levantada, frente a ventanas iguales a mitad
   de un trazo. AUC = probabilidad de que un apoyo dé más golpe que un momento cualquiera del trazo.
4. ¿Cuánto del trazo reconstruye el reloj? En cada trazo se integra:
   - el giro (como el ratón aéreo: yaw alrededor de la vertical, pitch alrededor del eje horizontal
     perpendicular al antebrazo), la "sombra" de un puntero;
   - la aceleración lineal dos veces, con velocidad cero al apoyar y al levantar (el dedo está quieto);
   y se ajusta una transformación lineal a la posición del dedo. R² = fracción del trazo explicada.
"""
import csv
import json
import os
import sys

import numpy as np

AX = np.array([1.0, 0.0, 0.0])            # antebrazo = x del reloj


def load_touch(folder):
    rows = []
    with open(os.path.join(folder, "touch.csv"), newline="") as f:
        for r in csv.DictReader(f):
            rows.append((float(r["t_ms"]), int(r["scan_100us"]) if r["scan_100us"] not in ("", "None") else -1,
                         int(r["contact_id"]), int(r["tip"]), float(r["x_mm"]), float(r["y_mm"])))
    return np.array(rows)


def load_sensor(folder, name):
    a = np.genfromtxt(os.path.join(folder, f"{name}.csv"), delimiter=",", skip_header=1, usecols=(0, 2, 3, 4))
    a = a[np.argsort(a[:, 0])]
    return a[np.concatenate([[True], np.diff(a[:, 0]) > 0])]


def strokes_from(touch, primary):
    """trazos del dedo principal: tramos seguidos con tip = 1 (un hueco de más de 60 ms también corta)"""
    t = touch[touch[:, 2] == primary]
    out, cur = [], []
    for row in t:
        if row[3] == 1 and (not cur or row[0] - cur[-1][0] < 60):
            cur.append(row)
        else:
            if len(cur) >= 3:
                out.append(np.array(cur))
            cur = [row] if row[3] == 1 else []
    if len(cur) >= 3:
        out.append(np.array(cur))
    return out


def groups_by_pause(strokes, pause_ms=900):
    gs, cur = [], [strokes[0]]
    for s in strokes[1:]:
        if s[0, 0] - cur[-1][-1, 0] > pause_ms:
            gs.append(cur)
            cur = [s]
        else:
            cur.append(s)
    gs.append(cur)
    return gs


def auc(pos, neg):
    pos, neg = np.asarray(pos), np.asarray(neg)
    if not len(pos) or not len(neg):
        return float("nan")
    return float(np.mean([(p > neg).mean() + 0.5 * (p == neg).mean() for p in pos]))


def r2(Y, X):
    """R² de ajustar Y (n×2) con X (n×k) más término constante, por mínimos cuadrados"""
    A = np.hstack([X, np.ones((len(X), 1))])
    coef, *_ = np.linalg.lstsq(A, Y, rcond=None)
    res = Y - A @ coef
    tot = ((Y - Y.mean(axis=0)) ** 2).sum()
    return 1 - (res ** 2).sum() / tot if tot > 0 else float("nan"), coef


def main():
    folder = sys.argv[1]
    touch = load_touch(folder)
    acc, gyr, grv = (load_sensor(folder, n) for n in ("ACCELERATION", "GYROSCOPE", "GRAVITY"))
    summary = {"session": os.path.basename(folder)}

    # 1. tasas
    tips = touch[touch[:, 3] == 1]
    ids, counts = np.unique(tips[:, 2], return_counts=True)
    primary = ids[np.argmax(counts)]
    p = tips[tips[:, 2] == primary]
    ds = np.diff(p[:, 1]) % 65536
    ds = ds[(ds > 0) & (ds < 400)]                     # pasos de su reloj dentro de un mismo trazo
    pad_hz = 10000 / np.median(ds)
    span = lambda a: (a[-1, 0] - a[0, 0]) / 1000
    rates = {"trackpad_hz_tocando": pad_hz}
    for name, a in (("acelerómetro", acc), ("giroscopio", gyr), ("gravedad", grv)):
        uniq = len(np.unique(a[:, 1:], axis=0)) / span(a)
        rates[name] = {"muestras_s": len(a) / span(a), "lecturas_nuevas_s": uniq}
    print(f"{os.path.basename(folder)}: {span(acc):.0f} s grabados")
    print(f"1. trackpad: {pad_hz:.0f} lecturas/s con el dedo encima (paso mediano de su reloj {np.median(ds) / 10:.1f} ms)")
    for k in ("acelerómetro", "giroscopio", "gravedad"):
        print(f"   {k}: {rates[k]['muestras_s']:.0f} muestras/s, {rates[k]['lecturas_nuevas_s']:.0f} lecturas nuevas/s")
    summary["tasas"] = rates

    # 2. trazos y dibujo
    strokes = strokes_from(touch, primary)
    groups = groups_by_pause(strokes)
    ink = sum(np.sum(np.hypot(np.diff(s[:, 4]), np.diff(s[:, 5]))) for s in strokes)
    print(f"\n2. {len(strokes)} trazos en {len(groups)} grupos (separados por pausas de más de 0.9 s), {ink / 10:.0f} cm de tinta")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        n = len(groups)
        cols = min(10, n)
        rows_ = int(np.ceil(n / cols))
        fig, axes = plt.subplots(rows_, cols, figsize=(1.6 * cols, 1.4 * rows_ + 0.4), facecolor="#11151c")
        axes = np.atleast_1d(axes).ravel()
        cmap = plt.get_cmap("cool")
        for i, ax in enumerate(axes):
            ax.set_facecolor("#11151c")
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
            if i >= n:
                continue
            g = groups[i]
            for j, s in enumerate(g):
                ax.plot(s[:, 4], s[:, 5], color=cmap(j / max(1, len(g) - 1)), lw=1.6, solid_capstyle="round")
            ax.set_aspect("equal"); ax.invert_yaxis()
            ax.set_title(str(i + 1), color="#9aa3b2", fontsize=7, pad=2)
        fig.tight_layout(pad=0.3)
        png = os.path.join(folder, "dibujo.png")
        fig.savefig(png, dpi=130, facecolor=fig.get_facecolor())
        print(f"   dibujo en {png}")
    except ImportError:
        pass

    # 3. apoyar y levantar
    hp = acc[:, 1:] - np.array([acc[max(0, i - 8):i, 1:].mean(axis=0) if i else acc[0, 1:] for i in range(len(acc))])
    golpe = np.linalg.norm(hp, axis=1)
    ta = acc[:, 0]

    def peak(t0, t1):
        a, b = np.searchsorted(ta, t0), np.searchsorted(ta, t1)
        if b <= a:
            return np.nan, np.nan
        k = a + int(np.argmax(golpe[a:b]))
        return golpe[k], ta[k]
    downs, ups, mids, lag_d, lag_u = [], [], [], [], []
    for s in strokes:
        v, tt = peak(s[0, 0] - 80, s[0, 0] + 80)
        downs.append(v); lag_d.append(tt - s[0, 0])
        v, tt = peak(s[-1, 0] - 80, s[-1, 0] + 80)
        ups.append(v); lag_u.append(tt - s[-1, 0])
        if s[-1, 0] - s[0, 0] > 500:                      # mitad de trazo, lejos de los extremos
            m = (s[0, 0] + s[-1, 0]) / 2
            mids.append(peak(m - 80, m + 80)[0])
    downs, ups, mids = (np.array(x)[~np.isnan(x)] for x in (downs, ups, mids))
    a_d, a_u = auc(downs, mids), auc(ups, mids)
    print(f"\n3. golpe en el acelerómetro (m/s², pico en ±80 ms):")
    print(f"   apoyar el dedo   mediana {np.median(downs):.2f} · AUC frente a mitad de trazo {a_d:.2f}")
    print(f"   levantar el dedo mediana {np.median(ups):.2f} · AUC {a_u:.2f}")
    print(f"   mitad de trazo   mediana {np.median(mids):.2f} ({len(mids)} ventanas)")
    print(f"   el pico cae {np.median(lag_d):+.0f} ms del apoyo y {np.median(lag_u):+.0f} ms de la levantada (mediana; incluye el desfase de relojes)")
    summary["toques"] = {"auc_apoyo": a_d, "auc_levantada": a_u, "mediana_apoyo": float(np.median(downs)),
                         "mediana_levantada": float(np.median(ups)), "mediana_mitad": float(np.median(mids))}

    # 4. reconstrucción
    def interp3(a, t):
        return np.stack([np.interp(t, a[:, 0], a[:, k]) for k in (1, 2, 3)], axis=1)
    rot_all, acc_all, both_all, Y_all, per = [], [], [], [], []
    for s in strokes:
        if s[-1, 0] - s[0, 0] < 250:
            continue
        t = np.arange(s[0, 0], s[-1, 0], 5.0)
        if len(t) < 10:
            continue
        Y = np.stack([np.interp(t, s[:, 0], s[:, 4]), np.interp(t, s[:, 0], s[:, 5])], axis=1)
        Y = Y - Y[0]
        w = np.radians(interp3(gyr, t))
        g = interp3(grv, t)
        g = g / np.linalg.norm(g, axis=1, keepdims=True)
        roll = w @ AX
        gpf = g @ AX
        yaw = (np.einsum("ij,ij->i", w, g) - roll * gpf) / np.maximum(1 - gpf ** 2, 0.09)
        ph = np.cross(AX, g)
        ph = ph / np.maximum(np.linalg.norm(ph, axis=1, keepdims=True), 1e-6)
        pitch = np.einsum("ij,ij->i", w, ph)
        dt = 0.005
        ang = np.stack([np.cumsum(yaw) * dt, np.cumsum(pitch) * dt], axis=1)
        la = interp3(acc, t) - interp3(grv, t)
        v = np.cumsum(la, axis=0) * dt
        v = v - np.outer(np.linspace(0, 1, len(v)), v[-1])          # velocidad cero al apoyar y al levantar
        pos = np.cumsum(v, axis=0) * dt * 1000                      # mm
        rot_all.append(ang); acc_all.append(pos); both_all.append(np.hstack([ang, pos])); Y_all.append(Y)
        per.append((r2(Y, ang)[0], r2(Y, pos)[0], r2(Y, np.hstack([ang, pos]))[0]))
    Yc = np.vstack(Y_all)
    res = {}
    for name, X in (("giro (sombra)", np.vstack(rot_all)), ("aceleración integrada", np.vstack(acc_all)), ("las dos", np.vstack(both_all))):
        res[name] = r2(Yc, X)[0]
    per = np.array(per)
    print(f"\n4. reconstrucción del trazo con el reloj ({len(per)} trazos de más de 0.25 s), R² = fracción explicada:")
    for k, (name, val) in enumerate(res.items()):
        print(f"   {name:<23} una sola transformación para todos: {val:.2f} · ajustada por trazo (mediana): {np.median(per[:, k]):.2f}")
    _, coef = r2(Yc, np.vstack(rot_all))
    mm_per_deg = np.linalg.norm(coef[:2], axis=1) * np.pi / 180
    print(f"   escala del giro: {mm_per_deg[0]:.2f} y {mm_per_deg[1]:.2f} mm de trazo por grado de muñeca")
    summary["reconstruccion"] = {"global": res, "por_trazo_mediana": dict(zip(res, np.median(per, axis=0).tolist()))}
    with open(os.path.join(folder, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
