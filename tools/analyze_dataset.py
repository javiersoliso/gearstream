"""Análisis del dataset de gestos grabado con dataset_capture.py (o dataset.html).

    python tools/analyze_dataset.py recordings/AAAAMMDD-HHMMSS

Tres preguntas:
  1. Gestos con pitido (pellizcos de 2 a 5 dedos, doble pellizco, puño, brazo): ¿se distinguen entre sí?
     Para cada pitido se busca el instante del gesto y se describen 200 ms antes y 400 ms después con
     unas pocas medidas físicas; un vecino más cercano (k = 3) con dejar-uno-fuera dice cuántos acierta.
  2. Actividades continuas (reposo, ratón, teclear, muñeca lenta y rápida): ventanas de 1 s, se entrena
     con la primera parte de cada paso y se prueba con la última (y el segundo rato de ratón entero).
  3. Pellizco usando el ratón de verdad: aciertos en los pitidos frente a falsas alarmas por minuto
     mientras se apunta normal o se teclea.

Todo se calcula sobre el marco del reloj: x es el antebrazo (hacia la mano), z sale de la pantalla.
Aceleración lineal = acelerómetro − gravedad. Guarda un resumen en <sesión>/analysis.json.
Ojo: todo sale de una sola sesión grabada por bloques; para saber si generaliza hace falta otra sesión.
"""
import json
import os
import sys

import numpy as np

FS = 100.0                    # Hz de la rejilla común
DT = 1000.0 / FS
EVENT_STEPS = ["pinza2", "pinza2_doble", "pinza3", "pinza4", "pinza5", "puno", "brazo"]
CONT_STEPS = ["reposo", "raton", "teclear", "muneca_lenta", "muneca_rapida"]


def load_csv(path):
    a = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=(0, 2, 3, 4))
    a = a[np.argsort(a[:, 0])]
    keep = np.concatenate([[True], np.diff(a[:, 0]) > 0])
    return a[keep]


def load(folder):
    acc, gyr, grv = (load_csv(os.path.join(folder, f"{n}.csv")) for n in ("ACCELERATION", "GYROSCOPE", "GRAVITY"))
    t0 = max(acc[0, 0], gyr[0, 0], grv[0, 0])
    t1 = min(acc[-1, 0], gyr[-1, 0], grv[-1, 0])
    t = np.arange(t0, t1, DT)
    res = lambda a: np.stack([np.interp(t, a[:, 0], a[:, k]) for k in (1, 2, 3)], axis=1)
    labels = [json.loads(l) for l in open(os.path.join(folder, "labels.jsonl"), encoding="utf-8")]
    dropped = {l["target_trial"] for l in labels if l.get("step") == "_descartar"}
    labels = [l for l in labels if not l["step"].startswith("_") and l.get("trial") not in dropped]
    return t, res(acc), res(gyr), res(grv), labels


def movavg(x, n):
    """media móvil causal de n muestras por columna"""
    c = np.cumsum(np.vstack([np.zeros((1, x.shape[1])), x]), axis=0)
    out = np.empty_like(x)
    for i in range(len(x)):
        lo = max(0, i - n)
        out[i] = (c[i] - c[lo]) / max(1, i - lo) if i > lo else x[i]
    return out


def signals(acc, gyr, grv):
    la = acc - grv                                              # aceleración lineal (m/s²)
    hp = la - movavg(la, 4)                                     # lo que cambia en 40 ms
    golpe = np.linalg.norm(hp, axis=1)
    n, w = len(la), 15
    c = np.cumsum(np.vstack([np.zeros((1, 3)), la]), axis=0)
    lento = np.zeros(n)
    for i in range(w, n - w):
        before = (c[i - 4] - c[i - w]) / (w - 4)
        after = (c[i + w] - c[i + 4]) / (w - 4)
        lento[i] = np.linalg.norm(after - before)
    limpio = golpe / (lento + 0.5)                              # golpe con el brazo quieto
    return la, hp, golpe, lento, limpio


def idx(t, ms):
    return int(np.clip(np.searchsorted(t, ms), 0, len(t) - 1))


# ---------- 1. gestos con pitido ----------
FEATURES = ["golpe máx", "golpe limpio máx", "giro x máx (antebrazo)", "giro y máx", "giro z máx",
            "acel. lineal x rms", "acel. lineal y rms", "acel. lineal z rms", "giro total rms",
            "nº de golpes", "cambio lento", "cambio de gravedad (°)", "acel. x con signo"]


def event_features(t, la, gyr, grv, golpe, lento, limpio, cue):
    a, b = idx(t, cue + 100), idx(t, cue + 1300)
    c = a + int(np.argmax(limpio[a:b]))
    lo, hi = max(0, c - 20), min(len(t), c + 40)
    pk = golpe[lo:hi].max()
    seg = golpe[max(0, c - 20):min(len(t), c + 60)]
    peaks, last = 0, -99
    for i in range(1, len(seg) - 1):                          # golpes separados ≥ 80 ms por encima de medio pico
        if seg[i] > 0.5 * pk and seg[i] >= seg[i - 1] and seg[i] >= seg[i + 1] and i - last >= 8:
            peaks += 1
            last = i
    g0 = grv[max(0, c - 50):c].mean(axis=0)
    g1 = grv[c + 50:min(len(t), c + 100)].mean(axis=0) if c + 50 < len(t) else grv[c]
    ang = np.degrees(np.arccos(np.clip(np.dot(g0, g1) / (np.linalg.norm(g0) * np.linalg.norm(g1)), -1, 1)))
    wseg, lseg = gyr[lo:hi], la[lo:hi]
    xs = lseg[:, 0]
    return [pk, limpio[c], *np.abs(wseg).max(axis=0), *np.sqrt((lseg ** 2).mean(axis=0)),
            np.sqrt((wseg ** 2).sum(axis=1).mean()), peaks, lento[c], ang, xs[np.argmax(np.abs(xs))]], t[c]


def knn_loo(X, y, k=3):
    Z = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    pred = []
    for i in range(len(Z)):
        d = np.linalg.norm(Z - Z[i], axis=1)
        d[i] = np.inf
        nn = np.argsort(d)[:k]
        votes = {}
        for j in nn:
            votes[y[j]] = votes.get(y[j], 0) + 1 / (1 + d[j])
        pred.append(max(votes, key=votes.get))
    return pred


def fstat(X, y):
    """F de ANOVA por medida: varianza entre gestos / varianza dentro de cada gesto"""
    classes = sorted(set(y))
    out = []
    for j in range(X.shape[1]):
        v = X[:, j]
        groups = [v[np.array(y) == c] for c in classes]
        m = v.mean()
        between = sum(len(g) * (g.mean() - m) ** 2 for g in groups) / (len(groups) - 1)
        within = sum(((g - g.mean()) ** 2).sum() for g in groups) / (len(v) - len(groups))
        out.append(between / (within + 1e-12))
    return out


def confusion(y, pred, classes):
    rows = []
    for c in classes:
        rows.append([sum(1 for a, b in zip(y, pred) if a == c and b == p) for p in classes])
    return rows


# ---------- 2. actividades continuas ----------
CONT_FEATURES = ["giro x rms", "giro y rms", "giro z rms", "acel. lineal rms", "golpe rms", "frecuencia dominante (Hz)",
                 "energía > 8 Hz (%)"]


def window_features(la, gyr, golpe, a, b):
    w, l = gyr[a:b], la[a:b]
    mag = np.linalg.norm(w, axis=1)
    mag = mag - mag.mean()
    spec = np.abs(np.fft.rfft(mag * np.hanning(len(mag)))) ** 2
    freqs = np.fft.rfftfreq(len(mag), 1 / FS)
    band = (freqs >= 0.3) & (freqs <= 15)
    fdom = freqs[band][np.argmax(spec[band])] if band.any() else 0.0
    ls = np.abs(np.fft.rfft((l - l.mean(axis=0)) * np.hanning(len(l))[:, None], axis=0)) ** 2
    lf = np.fft.rfftfreq(len(l), 1 / FS)
    hf = ls[lf > 8].sum() / (ls.sum() + 1e-12)
    return [*np.sqrt((w ** 2).mean(axis=0)), np.sqrt((l ** 2).sum(axis=1).mean()), np.sqrt((golpe[a:b] ** 2).mean()), fdom, 100 * hf]


def main():
    folder = sys.argv[1]
    t, acc, gyr, grv, labels = load(folder)
    la, hp, golpe, lento, limpio = signals(acc, gyr, grv)
    by_step = {l["step"]: l for l in labels}
    summary = {"session": os.path.basename(folder), "fs_hz": FS}
    print(f"sesión {os.path.basename(folder)}: {len(t) / FS:.0f} s a {FS:.0f} Hz, {len(labels)} pasos\n")

    # 1
    X, y, times = [], [], []
    for st in EVENT_STEPS:
        lab = by_step.get(st)
        if not lab:
            continue
        for cue in lab["cues_ms"]:
            f, tc = event_features(t, la, gyr, grv, golpe, lento, limpio, cue)
            X.append(f), y.append(st), times.append(tc - cue)
    X = np.array(X, dtype=float)
    Xl = np.sign(X) * np.log1p(np.abs(X))
    pred = knn_loo(Xl, y)
    classes = [c for c in EVENT_STEPS if c in set(y)]
    acc_all = np.mean([a == b for a, b in zip(y, pred)])
    print("1. GESTOS CON PITIDO (vecino más cercano, dejar-uno-fuera)")
    print(f"   aciertos: {acc_all * 100:.0f} % de {len(y)} gestos (al azar: {100 / len(classes):.0f} %)")
    cm = confusion(y, pred, classes)
    w = max(len(c) for c in classes)
    print("   " + " " * (w + 2) + " ".join(f"{c[:6]:>6}" for c in classes) + "   ← predicho")
    for c, row in zip(classes, cm):
        print(f"   {c:<{w}}  " + " ".join(f"{v:>6}" for v in row))
    F = fstat(Xl, y)
    order = np.argsort(F)[::-1]
    print("   medidas que más separan los gestos (F de ANOVA):")
    for j in order[:6]:
        print(f"     {FEATURES[j]:<26} F = {F[j]:6.1f}")
    print("   media por gesto de las tres mejores:")
    for c in classes:
        m = X[np.array(y) == c].mean(axis=0)
        print(f"     {c:<{w}}  " + " · ".join(f"{FEATURES[j]} {m[j]:.2f}" for j in order[:3]))
    print(f"   el gesto llega {np.median(times):.0f} ms después del pitido (mediana)\n")
    summary["eventos"] = {"aciertos": acc_all, "clases": classes, "confusion": cm,
                          "features": FEATURES, "F": dict(zip(FEATURES, F)),
                          "medias": {c: X[np.array(y) == c].mean(axis=0).tolist() for c in classes}}
    # dedos: ¿2 frente a 3-4-5?
    sub = [i for i, c in enumerate(y) if c in ("pinza2", "pinza3", "pinza4", "pinza5")]
    if sub:
        ys = [y[i] for i in sub]
        ps = knn_loo(Xl[sub], ys)
        print(f"   solo pellizcos de 2, 3, 4 y 5 dedos: {np.mean([a == b for a, b in zip(ys, ps)]) * 100:.0f} % (al azar 25 %)\n")
        summary["eventos"]["solo_dedos"] = float(np.mean([a == b for a, b in zip(ys, ps)]))

    # 2
    print("2. ACTIVIDADES CONTINUAS (ventanas de 1 s; entrena con el principio, prueba con el final)")
    win, hop = int(FS), int(FS / 2)
    train, test = [], []
    for st in CONT_STEPS + ["raton2"]:
        lab = by_step.get(st)
        if not lab:
            continue
        a, b = idx(t, lab["t0"] + 500), idx(t, lab["t1"])
        starts = list(range(a, b - win, hop))
        name = "raton" if st == "raton2" else st
        cut = int(0.6 * len(starts))
        for k, s in enumerate(starts):
            row = (window_features(la, gyr, golpe, s, s + win), name)
            if st == "raton2":
                test.append(row)                                      # el segundo rato de ratón, entero, de prueba
            elif k < cut:
                train.append(row)
            elif k > cut:                                             # una ventana de hueco: no se solapan
                test.append(row)
    Xtr = np.array([r[0] for r in train])
    Xte = np.array([r[0] for r in test])
    mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0) + 1e-9
    Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
    ytr, yte = [r[1] for r in train], [r[1] for r in test]
    pred2 = []
    for z in Zte:
        d = np.linalg.norm(Ztr - z, axis=1)
        nn = np.argsort(d)[:3]
        votes = {}
        for j in nn:
            votes[ytr[j]] = votes.get(ytr[j], 0) + 1
        pred2.append(max(votes, key=votes.get))
    cls2 = [c for c in CONT_STEPS if c in set(yte)]
    acc2 = np.mean([a == b for a, b in zip(yte, pred2)])
    print(f"   aciertos: {acc2 * 100:.0f} % de {len(yte)} ventanas de prueba (al azar {100 / len(cls2):.0f} %)")
    cm2 = confusion(yte, pred2, cls2)
    w2 = max(len(c) for c in cls2)
    print("   " + " " * (w2 + 2) + " ".join(f"{c[:6]:>6}" for c in cls2) + "   ← predicho")
    for c, row in zip(cls2, cm2):
        print(f"   {c:<{w2}}  " + " ".join(f"{v:>6}" for v in row))
    print("   media por actividad:")
    for c in cls2:
        m = np.array([r[0] for r in train + test if r[1] == c]).mean(axis=0)
        print(f"     {c:<{w2}}  " + " · ".join(f"{n} {v:.1f}" for n, v in zip(CONT_FEATURES, m)))
    summary["continuas"] = {"aciertos": acc2, "clases": cls2, "confusion": cm2}
    for st, f_target in (("muneca_lenta", 0.5), ("muneca_rapida", 2.0)):
        lab = by_step.get(st)
        if lab:
            a, b = idx(t, lab["t0"] + 500), idx(t, lab["t1"])
            w3 = gyr[a:b]
            axis = int(np.argmax((w3 ** 2).mean(axis=0)))
            sig = w3[:, axis] - w3[:, axis].mean()
            spec = np.abs(np.fft.rfft(sig * np.hanning(len(sig)))) ** 2
            freqs = np.fft.rfftfreq(len(sig), 1 / FS)
            band = (freqs > 0.2) & (freqs < 10)
            fd = freqs[band][np.argmax(spec[band])]
            amp = np.sqrt(2) * sig.std()
            print(f"   {st}: pedida {f_target} Hz → medida {fd:.2f} Hz en el eje {'xyz'[axis]} del giro, amplitud ±{amp:.0f} °/s (≈ ±{amp / (2 * np.pi * fd):.0f}° de muñeca)")
            summary[st] = {"pedida_hz": f_target, "medida_hz": float(fd), "eje": "xyz"[axis], "amplitud_dps": float(amp)}
    print()

    # 3
    print("3. PELLIZCO USANDO EL RATÓN DE VERDAD")
    def spikes(T, a, b):
        out, last = [], -1e9
        for i in range(max(1, a), min(b, len(t) - 1)):
            v = limpio[i]
            if v > T and v >= limpio[i - 1] and v >= limpio[i + 1] and t[i] - last > 100:
                out.append(t[i])
                last = t[i]
        return out
    calm = [by_step[s] for s in ("raton", "raton2") if s in by_step]
    calm_min = sum(l["t1"] - l["t0"] for l in calm) / 60000
    typing = by_step.get("teclear")
    rows3 = []
    print(f"   {'umbral':>6} | pellizcos 2 dedos | falsas alarmas/min apuntando | tecleando | dobles: detectados · falsos/min apuntando")
    for T in (1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        p2 = by_step.get("pinza2")
        hits = sum(1 for c in p2["cues_ms"] if spikes(T, idx(t, c + 100), idx(t, c + 1300))) if p2 else 0
        fa = sum(len(spikes(T, idx(t, l["t0"]), idx(t, l["t1"])) ) for l in calm) / max(calm_min, 1e-9)
        ty = len(spikes(T, idx(t, typing["t0"]), idx(t, typing["t1"]))) / ((typing["t1"] - typing["t0"]) / 60000) if typing else float("nan")
        dbl = by_step.get("pinza2_doble")
        def pairs(sp):
            n, i = 0, 0
            while i < len(sp) - 1:
                if 100 <= sp[i + 1] - sp[i] <= 600:
                    n, i = n + 1, i + 2
                else:
                    i += 1
            return n
        dh = sum(1 for c in dbl["cues_ms"] if pairs(spikes(T, idx(t, c + 100), idx(t, c + 1600)))) if dbl else 0
        dfa = sum(pairs(spikes(T, idx(t, l["t0"]), idx(t, l["t1"]))) for l in calm) / max(calm_min, 1e-9)
        n2 = len(p2["cues_ms"]) if p2 else 0
        nd = len(dbl["cues_ms"]) if dbl else 0
        print(f"   {T:6.1f} | {hits:2d}/{n2} | {fa:5.1f} | {ty:5.1f} | {dh:2d}/{nd} · {dfa:4.1f}")
        rows3.append({"umbral": T, "pellizcos": hits, "de": n2, "falsas_min_apuntando": fa, "falsas_min_tecleando": ty,
                      "dobles": dh, "dobles_de": nd, "dobles_falsos_min": dfa})
    summary["pellizco_en_uso"] = rows3
    with open(os.path.join(folder, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)
    print(f"\nresumen guardado en {os.path.join(folder, 'analysis.json')}")


if __name__ == "__main__":
    main()
