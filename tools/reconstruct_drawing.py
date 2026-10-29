"""Redibujar con el reloj: un modelo aprende a traducir lo que siente el reloj a la velocidad del dedo.

    python tools/reconstruct_drawing.py recordings/dibujo-AAAAMMDD-HHMMSS

Para cada instante de un trazo (rejilla de 10 ms) se describe el reloj en una ventana de ±240 ms: giros en el
marco del puntero (yaw, pitch alrededor de la gravedad y el antebrazo; roll alrededor del antebrazo), giro
crudo, aceleración lineal y postura (dirección de la gravedad). El objetivo es la velocidad del dedo en el
trackpad (mm/s, suavizada). Se integra la velocidad predicha a lo largo del trazo para redibujarlo. Se le
da cuándo apoya y levanta el dedo (el trackpad; el reloj no lo ve) y el punto donde empieza cada trazo.

Prueba justa: se entrena sin las letras que se van a redibujar (mayúsculas con el resto, minúsculas con el
resto). Modelos: (0) la calibración lineal de posición de analyze_drawing (referencia), (1) regresión
ridge de velocidad, (2) una red pequeña (una capa oculta tanh, Adam, numpy) sobre los mismos rasgos.
Guarda las reconstrucciones fuera de muestra en <grabación>/reconstruccion.npz para render_letters_gif.py.
"""
import json
import os
import sys

import numpy as np
from scipy.signal import savgol_filter

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from analyze_drawing import AX, interp3, load_sensor, load_touch, r2, strokes_from, watch_features  # noqa: E402

DT = 10.0                               # ms de la rejilla
LAGS = np.arange(-240, 241, 40)         # ms: ±240 ms de contexto (mejor y más estable que ±80 y ±160 en la prueba)


def frame_rates(w, g):
    """yaw, pitch, roll (rad/s) como el ratón aéreo"""
    roll = w @ AX
    gpf = g @ AX
    yaw = (np.einsum("ij,ij->i", w, g) - roll * gpf) / np.maximum(1 - gpf ** 2, 0.09)
    ph = np.cross(AX, g)
    ph = ph / np.maximum(np.linalg.norm(ph, axis=1, keepdims=True), 1e-6)
    return np.stack([yaw, np.einsum("ij,ij->i", w, ph), roll], axis=1)


def stroke_data(s, acc, gyr, grv, bias):
    t = np.arange(s[0, 0], s[-1, 0], DT)
    if len(t) < 6:
        return None
    feats = []
    for lag in LAGS:
        tl = t + lag
        w = np.radians(interp3(gyr, tl) - bias)
        g = interp3(grv, tl)
        g = g / np.linalg.norm(g, axis=1, keepdims=True)
        la = interp3(acc, tl) - interp3(grv, tl)
        feats += [frame_rates(w, g), w, la]
    g0 = interp3(grv, t)
    feats.append(g0 / np.linalg.norm(g0, axis=1, keepdims=True))
    X = np.hstack(feats)
    pos = np.stack([np.interp(t, s[:, 0], s[:, 4]), np.interp(t, s[:, 0], s[:, 5])], axis=1)
    win = min(len(t) - (1 - len(t) % 2), 9)
    sm = savgol_filter(pos, win, 2, axis=0) if win >= 5 else pos
    V = np.gradient(sm, DT / 1000, axis=0)
    return t, X, V, pos


class Ridge:
    def __init__(self, lam):
        self.lam = lam

    def fit(self, X, Y):
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Z = np.hstack([(X - self.mu) / self.sd, np.ones((len(X), 1))])
        I = np.eye(Z.shape[1]); I[-1, -1] = 0
        self.W = np.linalg.solve(Z.T @ Z + self.lam * I, Z.T @ Y)
        return self

    def predict(self, X):
        return np.hstack([(X - self.mu) / self.sd, np.ones((len(X), 1))]) @ self.W


class MLP:
    """una capa oculta tanh; Adam; parada temprana con un 15 % de validación"""
    def __init__(self, hidden=64, l2=1e-3, epochs=400, lr=3e-3, seed=0):
        self.h, self.l2, self.epochs, self.lr, self.rng = hidden, l2, epochs, lr, np.random.default_rng(seed)

    def fit(self, X, Y):
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        self.ym, self.ys = Y.mean(0), Y.std(0) + 1e-9
        Z, T = (X - self.mu) / self.sd, (Y - self.ym) / self.ys
        idx = self.rng.permutation(len(Z)); nv = len(Z) // 7
        va, tr = idx[:nv], idx[nv:]
        d = Z.shape[1]
        P = {"W1": self.rng.normal(0, 1 / np.sqrt(d), (d, self.h)), "b1": np.zeros(self.h),
             "W2": self.rng.normal(0, 1 / np.sqrt(self.h), (self.h, 2)), "b2": np.zeros(2)}
        m = {k: np.zeros_like(v) for k, v in P.items()}; v2 = {k: np.zeros_like(v) for k, v in P.items()}
        best, best_P, wait, step = np.inf, None, 0, 0
        for ep in range(self.epochs):
            for b in np.array_split(self.rng.permutation(tr), max(1, len(tr) // 256)):
                H = np.tanh(Z[b] @ P["W1"] + P["b1"]); O = H @ P["W2"] + P["b2"]
                E = (O - T[b]) / len(b)
                G = {"W2": H.T @ E + self.l2 * P["W2"], "b2": E.sum(0)}
                dH = (E @ P["W2"].T) * (1 - H ** 2)
                G["W1"] = Z[b].T @ dH + self.l2 * P["W1"]; G["b1"] = dH.sum(0)
                step += 1
                for k in P:
                    m[k] = 0.9 * m[k] + 0.1 * G[k]; v2[k] = 0.999 * v2[k] + 0.001 * G[k] ** 2
                    P[k] -= self.lr * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v2[k] / (1 - 0.999 ** step)) + 1e-8)
            Hv = np.tanh(Z[va] @ P["W1"] + P["b1"]); loss = ((Hv @ P["W2"] + P["b2"] - T[va]) ** 2).mean()
            if loss < best - 1e-5:
                best, best_P, wait = loss, {k: v.copy() for k, v in P.items()}, 0
            else:
                wait += 1
                if wait > 25:
                    break
        self.P = best_P
        return self

    def predict(self, X):
        H = np.tanh(((X - self.mu) / self.sd) @ self.P["W1"] + self.P["b1"])
        return (H @ self.P["W2"] + self.P["b2"]) * self.ys + self.ym


def shape_sim(true_list, pred_list):
    a = np.vstack([t - t[0] for t in true_list]); b = np.vstack(pred_list)
    a, b = (a - a.mean(0)).ravel(), (b - b.mean(0)).ravel()
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def main():
    folder = sys.argv[1]
    touch = load_touch(folder)
    acc, gyr, grv = (load_sensor(folder, n) for n in ("ACCELERATION", "GYROSCOPE", "GRAVITY"))
    bias = np.median(gyr[:, 1:], axis=0)
    tips = touch[touch[:, 3] == 1]
    ids, counts = np.unique(tips[:, 2], return_counts=True)
    strokes = strokes_from(touch, ids[np.argmax(counts)])
    letters = json.load(open(os.path.join(folder, "letters.json"), encoding="utf-8"))
    upper = {i for _, ix in letters["mayúsculas"] for i in ix}
    lower = {i for _, ix in letters["minúsculas"] for i in ix}
    data = {i: stroke_data(s, acc, gyr, grv, bias) for i, s in enumerate(strokes)}
    data = {i: d for i, d in data.items() if d is not None}
    pos_feats = {i: watch_features(strokes[i], acc, gyr, grv, step=DT) for i in data}
    print(f"{len(data)} trazos utilizables · {sum(len(d[0]) for d in data.values())} instantes · {data[next(iter(data))][1].shape[1]} rasgos por instante")

    folds = {"mayúsculas": upper, "minúsculas": lower}
    out = {"baseline": {}, "ridge": {}, "red": {}}
    for fname, test in folds.items():
        train = [i for i in data if i not in test]
        Xtr = np.vstack([data[i][1] for i in train]); Vtr = np.vstack([data[i][2] for i in train])
        # (0) referencia: calibración lineal de posición entrenada sin estas letras
        tr_pf = [i for i in train if pos_feats[i] is not None]
        Yp = np.vstack([pos_feats[i][1] for i in tr_pf]); Xp = np.vstack([np.hstack([pos_feats[i][2], pos_feats[i][3]]) for i in tr_pf])
        _, coef = r2(Yp, Xp)
        # (1) ridge con λ elegida por validación cruzada de 5 grupos de trazos dentro del entrenamiento
        groups = np.array_split(np.random.default_rng(1).permutation(train), 5)
        best_lam, best_err = None, np.inf
        for lam in (0.3, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000):
            errs = []
            for k in range(5):
                tr_k = [i for j, g in enumerate(groups) if j != k for i in g]
                mdl = Ridge(lam).fit(np.vstack([data[i][1] for i in tr_k]), np.vstack([data[i][2] for i in tr_k]))
                errs.append(np.mean(np.vstack([(mdl.predict(data[i][1]) - data[i][2]) ** 2 for i in groups[k]])))
            if np.mean(errs) < best_err:
                best_lam, best_err = lam, np.mean(errs)
        ridge = Ridge(best_lam).fit(Xtr, Vtr)
        net = MLP().fit(Xtr, Vtr)
        for i in test:
            if i not in data:
                continue
            t, X, V, pos = data[i]
            for name, mdl in (("ridge", ridge), ("red", net)):
                v = mdl.predict(X)
                rec = np.vstack([[0, 0], np.cumsum(v[:-1], axis=0) * DT / 1000])
                out[name][i] = (pos, rec)
            pf = pos_feats[i]
            if pf is not None:
                pred = np.hstack([pf[2], pf[3], np.ones((len(pf[0]), 1))]) @ coef
                out["baseline"][i] = (np.stack([np.interp(pf[0], strokes[i][:, 0], strokes[i][:, 4]),
                                                np.interp(pf[0], strokes[i][:, 0], strokes[i][:, 5])], axis=1), pred - pred[0])
        print(f"  pliegue {fname}: ridge λ={best_lam}, red entrenada con {len(Xtr)} instantes")

    print("\nparecido de forma por letra, letras NUNCA vistas por el modelo (1 = idéntica):")
    summary = {}
    for name, label in (("baseline", "calibración lineal de posición"), ("ridge", "ridge sobre velocidad"), ("red", "red neuronal sobre velocidad")):
        sims, lens = [], []
        for block in ("mayúsculas", "minúsculas"):
            for lname, ix in letters[block]:
                pairs = [out[name][i] for i in ix if i in out[name]]
                if not pairs:
                    continue
                sims.append(shape_sim([p[0] for p in pairs], [p[1] for p in pairs]))
                lt = sum(np.hypot(*np.diff(p[0], axis=0).T).sum() for p in pairs)
                lp = sum(np.hypot(*np.diff(p[1], axis=0).T).sum() for p in pairs)
                lens.append(lp / max(lt, 1e-9))
        summary[name] = {"parecido_mediano": float(np.median(sims)), "largo_relativo": float(np.median(lens)),
                         "letras_sobre_0.8": int(sum(s > 0.8 for s in sims)), "n": len(sims)}
        print(f"  {label:<32} mediana {np.median(sims):.2f} · letras por encima de 0.8: {sum(s > 0.8 for s in sims)}/{len(sims)} · largo reconstruido/real {np.median(lens):.2f}")
    best = max(("ridge", "red"), key=lambda k: summary[k]["parecido_mediano"])
    np.savez_compressed(os.path.join(folder, "reconstruccion.npz"),
                        **{f"{k}_{i}_true": v[0] for k in out for i, v in out[k].items()},
                        **{f"{k}_{i}_pred": v[1] for k in out for i, v in out[k].items()})
    with open(os.path.join(folder, "reconstruccion.json"), "w", encoding="utf-8") as f:
        json.dump({"mejor": best, **summary}, f, ensure_ascii=False, indent=1)
    print(f"\nmejor modelo: {best} · reconstrucciones guardadas en {folder}/reconstruccion.npz")


if __name__ == "__main__":
    main()
