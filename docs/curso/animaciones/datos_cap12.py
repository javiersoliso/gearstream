"""Datos del capítulo 12: una sesión de escritura inventada, pasada por el código de verdad.

    python docs/curso/animaciones/datos_cap12.py            # calcula (o lee) todo e imprime los números del capítulo
    python docs/curso/animaciones/datos_cap12.py --rehacer  # lo mismo, sin leer lo guardado
    python docs/curso/animaciones/datos_cap12.py --referencias  # los números de Python que pega tools/test_aprender.js

Las grabaciones de verdad son datos personales y no se publican, así que aquí se inventa una: 53 letras (A-Z, Ñ y
a-z) escritas con el dedo y lo que sentiría un reloj en la muñeca. Se escribe con el mismo formato que
draw_recorder.py en docs/curso/animaciones/media/sim12/ (carpeta que no se sube) y se le pasa a
tools/reconstruct_drawing.py tal cual, sin cambiarle nada.

Lo que el reloj inventado siente y lo que no, en tres frases:
  - la muñeca hace una parte del movimiento, y solo de lo lento (un filtro de TAU s): el resto lo hacen los dedos;
  - esa parte depende de la rapidez (RHO_LENTO a RHO_RAPIDO) y cambia de una letra a otra, en tamaño (VARIA_LETRA) y
    en dirección (GIRO_LETRA): es la curva que un modelo lineal no puede seguir;
  - la muñeca además se mueve por su cuenta (PASEO_MANO), los dedos dejan una huella chica (FUGA_DEDOS), y el sensor
    suma ruido, sesgo y un atraso fijo.
Los números de calibración (5.3 y 6.9 mm por grado, ejes a 75°, 143 lecturas/s, 200 muestras/s) son los del README;
TAU, las partes de la muñeca, VARIA_LETRA, GIRO_LETRA y PASEO_MANO se ajustaron a mano hasta que la sesión diera
resultados del tamaño de los de la grabación real que publica el README.
Nada de esto prueba algo sobre una mano de verdad: sirve para ver cómo se comporta la cuenta.
"""
import json
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(AQUI, "..", "..", "..", "tools")
sys.path.insert(0, TOOLS)
import reconstruct_drawing as rd                     # noqa: E402  el de verdad
from analyze_drawing import strokes_from             # noqa: E402

CARPETA = os.path.join(AQUI, "media", "sim12")
HZ_SIM, HZ_RELOJ, HZ_PAD = 1000, 200, 143
TAU = 0.16                       # s: la muñeca solo sigue lo lento
RHO_LENTO, RHO_RAPIDO, V_RHO = 0.15, 0.90, 110.0   # parte de la muñeca, según la rapidez (mm/s)
VARIA_LETRA = 0.30               # cuánto cambia esa parte de una letra a otra
GIRO_LETRA = 20.0                # grados: cada letra se escribe con la muñeca un poco girada
PASEO_MANO = 18.0                # mm/s: lo que la muñeca hace por su cuenta, sin que el dedo lo pida
FUGA_DEDOS = 0.06                # huella de los dedos en la muñeca
MM_POR_GRADO = (5.3, 6.9)        # yaw, pitch (README)
EJES_GRADOS = 75.0               # ángulo entre los dos ejes (README)
RUIDO_GIRO, RUIDO_ACEL = 1.0, 0.12     # °/s, m/s²
SESGO = np.array([0.4, -0.3, 0.2])     # °/s
ATRASO = 0.025                   # s
G = 9.81


# ---------- las letras: trazos en una caja de alto 1 ----------
def arco(cx, cy, rx, ry, a0, a1, n=14):
    a = np.radians(np.linspace(a0, a1, n))
    return [(cx + rx * np.cos(u), cy + ry * np.sin(u)) for u in a]


def glifos():
    A = arco
    M = {
        "A": [[(0, 0), (.45, 1), (.9, 0)], [(.18, .4), (.72, .4)]],
        "B": [[(0, 1), (0, 0)], [(0, 1), (.4, 1)] + A(.4, .75, .28, .25, 90, -90) + A(.42, .25, .33, .25, 90, -90) + [(0, 0)]],
        "C": [A(.5, .5, .5, .5, 50, 310, 22)],
        "D": [[(0, 1), (0, 0)], [(0, 1), (.3, 1)] + A(.3, .5, .55, .5, 90, -90, 20) + [(0, 0)]],
        "E": [[(.75, 1), (0, 1), (0, 0), (.75, 0)], [(0, .5), (.6, .5)]],
        "F": [[(.75, 1), (0, 1), (0, 0)], [(0, .5), (.6, .5)]],
        "G": [A(.5, .5, .5, .5, 50, 330, 22) + [(.95, .45), (.55, .45)]],
        "H": [[(0, 1), (0, 0)], [(.8, 1), (.8, 0)], [(0, .5), (.8, .5)]],
        "I": [[(.3, 1), (.3, 0)]],
        "J": [[(.7, 1), (.7, .25)] + A(.4, .25, .3, .25, 0, -180)],
        "K": [[(0, 1), (0, 0)], [(.75, 1), (0, .45), (.8, 0)]],
        "L": [[(0, 1), (0, 0), (.7, 0)]],
        "M": [[(0, 0), (0, 1), (.5, .3), (1, 1), (1, 0)]],
        "N": [[(0, 0), (0, 1), (.8, 0), (.8, 1)]],
        "Ñ": [[(0, 0), (0, .85), (.8, 0), (.8, .85)], [(.1, 1.02), (.3, 1.12), (.5, 1.02), (.7, 1.12)]],
        "O": [A(.5, .5, .5, .5, 90, 450, 26)],
        "P": [[(0, 1), (0, 0)], [(0, 1), (.4, 1)] + A(.4, .72, .3, .28, 90, -90) + [(0, .44)]],
        "Q": [A(.5, .5, .5, .5, 90, 450, 26), [(.55, .3), (1, -.05)]],
        "R": [[(0, 1), (0, 0)], [(0, 1), (.4, 1)] + A(.4, .72, .3, .28, 90, -90) + [(0, .44), (.25, .44), (.75, 0)]],
        "S": [A(.42, .74, .36, .26, 40, 270, 14) + A(.42, .26, .4, .26, 90, -150, 14)],
        "T": [[(0, 1), (.9, 1)], [(.45, 1), (.45, 0)]],
        "U": [[(0, 1), (0, .35)] + A(.4, .35, .4, .35, 180, 360) + [(.8, 1)]],
        "V": [[(0, 1), (.4, 0), (.8, 1)]],
        "W": [[(0, 1), (.28, 0), (.55, .75), (.82, 0), (1.1, 1)]],
        "X": [[(0, 1), (.8, 0)], [(.8, 1), (0, 0)]],
        "Y": [[(0, 1), (.4, .5), (.8, 1)], [(.4, .5), (.4, 0)]],
        "Z": [[(0, 1), (.8, 1), (0, 0), (.8, 0)]],
    }
    x = .6                                             # alto de las minúsculas
    m = {
        "a": [A(.3, .3, .3, .3, 30, 390, 20), [(.6, .6), (.6, 0)]],
        "b": [[(0, 1), (0, 0)], A(.3, .3, .3, .3, 170, -190, 20)],
        "c": [A(.3, .3, .3, .3, 50, 310, 18)],
        "d": [A(.3, .3, .3, .3, 10, 370, 20), [(.6, 1), (.6, 0)]],
        "e": [[(.02, .32), (.58, .32)] + A(.3, .3, .3, .3, 10, 310, 18)],
        "f": [A(.45, .85, .2, .15, 30, 180, 8) + [(.25, 0)], [(.05, .55), (.5, .55)]],
        "g": [A(.3, .3, .3, .3, 10, 370, 20), [(.6, .6), (.6, -.15)] + A(.3, -.15, .3, .2, 0, -160, 10)],
        "h": [[(0, 1), (0, 0)], [(0, .4)] + A(.28, .35, .27, .25, 170, 0, 10) + [(.55, 0)]],
        "i": [[(.1, x), (.1, 0)], [(.1, .82), (.1, .76)]],
        "j": [[(.3, x), (.3, -.1)] + A(.1, -.1, .2, .2, 0, -170, 8), [(.3, .82), (.3, .76)]],
        "k": [[(0, 1), (0, 0)], [(.5, x), (0, .25), (.55, 0)]],
        "l": [[(.1, 1), (.1, 0)]],
        "m": [[(0, x), (0, 0)], [(0, .4)] + A(.22, .38, .22, .22, 170, 0, 9) + [(.44, 0)],
              [(.44, .4)] + A(.66, .38, .22, .22, 170, 0, 9) + [(.88, 0)]],
        "n": [[(0, x), (0, 0)], [(0, .4)] + A(.28, .35, .27, .25, 170, 0, 10) + [(.55, 0)]],
        "o": [A(.3, .3, .3, .3, 90, 450, 20)],
        "p": [[(0, x), (0, -.35)], A(.3, .3, .3, .3, 170, -190, 20)],
        "q": [A(.3, .3, .3, .3, 10, 370, 20), [(.6, x), (.6, -.35)]],
        "r": [[(0, x), (0, 0)], [(0, .35)] + A(.25, .35, .25, .25, 170, 40, 8)],
        "s": [A(.25, .45, .22, .15, 40, 270, 10) + A(.25, .15, .25, .15, 90, -150, 10)],
        "t": [[(.2, .95), (.2, .1)] + A(.35, .1, .15, .1, 180, 300, 6), [(0, x), (.45, x)]],
        "u": [[(0, x), (0, .25)] + A(.27, .25, .27, .25, 180, 360, 10) + [(.54, x)], [(.54, x), (.54, 0)]],
        "v": [[(0, x), (.28, 0), (.56, x)]],
        "w": [[(0, x), (.2, 0), (.4, .45), (.6, 0), (.8, x)]],
        "x": [[(0, x), (.5, 0)], [(.5, x), (0, 0)]],
        "y": [[(0, x), (.28, 0)], [(.56, x), (.28, 0), (.1, -.35)]],
        "z": [[(0, x), (.5, x), (0, 0), (.5, 0)]],
    }
    return M, m


def trazo_denso(puntos, alto_mm, paso=0.25):
    """los puntos de un trazo, en mm, a paso parejo y con las esquinas apenas redondeadas"""
    p = np.array(puntos, float) * alto_mm
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
    u = np.arange(0, s[-1] + paso, paso)
    q = np.stack([np.interp(u, s, p[:, 0]), np.interp(u, s, p[:, 1])], axis=1)
    n = max(3, int(0.6 / paso))
    k = np.exp(-0.5 * (np.arange(-3 * n, 3 * n + 1) / n) ** 2)
    k /= k.sum()
    pad = len(k) // 2
    return np.stack([np.convolve(np.pad(q[:, i], pad, mode="edge"), k, "valid") for i in (0, 1)], axis=1)


def tiempos(q, rapidez):
    """la ley de los dos tercios: en las curvas cerradas el dedo frena (rapidez ∝ radio^(1/3))"""
    d = np.gradient(q, axis=0)
    dd = np.gradient(d, axis=0)
    ds = np.maximum(np.hypot(*d.T), 1e-6)
    curv = np.abs(d[:, 0] * dd[:, 1] - d[:, 1] * dd[:, 0]) / ds ** 3
    v = rapidez * np.clip((1 / np.maximum(curv, 1e-3)) ** (1 / 3) / 3.0, 0.25, 1.6)
    n = 41
    v = np.convolve(np.pad(v, n // 2, mode="edge"), np.ones(n) / n, "valid")[:len(q)]
    k = np.arange(len(q))
    arranque = np.minimum(1, (k + 3) / 40) * np.minimum(1, (len(q) - k + 3) / 40)
    return np.concatenate([[0], np.cumsum(ds[1:] / (v[1:] * arranque[1:]))])


def sesion(semilla=7, vueltas=1):
    """Una sesión: `vueltas` abecedarios de mayúsculas y otros tantos de minúsculas, con pausas entre letras.
    Devuelve lo mismo que hay en una grabación: toques y los tres sensores, y qué trazos forman cada letra."""
    rng = np.random.default_rng(semilla)
    M, m = glifos()
    orden = [("mayúsculas", k, v) for _ in range(vueltas) for k, v in M.items()] + \
            [("minúsculas", k, v) for _ in range(vueltas) for k, v in m.items()]
    ahora, cursor = 1.0, np.array([40.0, 30.0])
    pts_t, pts_p, pts_f, pts_g = [ahora], [cursor.copy()], [1.0], [0.0]
    apoyos = []                                       # (t0, t1) con el dedo apoyado
    letras = {"mayúsculas": [], "minúsculas": []}
    i_trazo = 0
    for bloque, nombre, trazos in orden:
        tam = 30.0 * rng.uniform(0.8, 1.25)
        rap = rng.uniform(55, 130)
        f = float(np.exp(rng.normal(0, VARIA_LETRA)))
        giro = float(np.radians(rng.normal(0, GIRO_LETRA)))
        origen = np.array([rng.uniform(15, 75), rng.uniform(35, 60)])
        idx = []
        for tr in trazos:
            q = trazo_denso(tr, tam) * [1, -1] + origen     # y del trackpad hacia abajo
            tq = tiempos(q, rap)
            dur = 0.15 + np.linalg.norm(q[0] - cursor) / 160 + rng.uniform(0, 0.08)   # la mano va por el aire al comienzo
            u = np.linspace(0, 1, max(4, int(dur * 200)))[1:]
            s = 10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5
            pts_t += list(ahora + u * dur)
            pts_p += list(cursor + np.outer(s, q[0] - cursor))
            pts_f += [f] * len(u)
            pts_g += [giro] * len(u)
            ahora += dur
            apoyos.append((ahora, ahora + tq[-1]))
            pts_t += list(ahora + tq[1:])
            pts_p += list(q[1:])
            pts_f += [f] * (len(q) - 1)
            pts_g += [giro] * (len(q) - 1)
            ahora += tq[-1] + 0.02
            cursor = q[-1]
            idx.append(i_trazo)
            i_trazo += 1
        letras[bloque].append([nombre, idx])
        ahora += rng.uniform(1.0, 1.4)                      # pausa entre letras
        pts_t.append(ahora)
        pts_p.append(cursor.copy())
        pts_f.append(f)
        pts_g.append(giro)
    t = np.arange(0, ahora + 1, 1 / HZ_SIM)
    pt, pp = np.array(pts_t), np.array(pts_p)
    P = np.stack([np.interp(t, pt, pp[:, i]) for i in (0, 1)], axis=1)
    F = np.interp(t, pt, np.array(pts_f))
    Gi = np.interp(t, pt, np.array(pts_g))
    return _reloj(t, P, F, Gi, apoyos, letras, rng)


def paso_bajo(x, tau, dt):
    """un promedio que olvida, en cada columna"""
    a = dt / (tau + dt)
    y = np.empty_like(x)
    y[0] = x[0]
    for k in range(1, len(x)):
        y[k] = y[k - 1] + a * (x[k] - y[k - 1])
    return y


def parte_de_la_muneca(rapidez, f=1.0):
    return f * (RHO_LENTO + (RHO_RAPIDO - RHO_LENTO) * np.tanh(rapidez / V_RHO))


def _reloj(t, P, F, Gi, apoyos, letras, rng):
    dt = 1 / HZ_SIM
    V = np.gradient(P, dt, axis=0)                         # mm/s del dedo
    VL = paso_bajo(V, TAU, dt)
    rho = parte_de_la_muneca(np.hypot(*VL.T), F)
    c, s = np.cos(Gi), np.sin(Gi)
    VG = np.stack([c * VL[:, 0] - s * VL[:, 1], s * VL[:, 0] + c * VL[:, 1]], axis=1)
    paseo = paso_bajo(rng.normal(0, 1, (len(t), 2)), 0.25, dt)
    paseo *= PASEO_MANO / paseo.std(0)
    H = rho[:, None] * VG + FUGA_DEDOS * (V - VL) + paseo  # lo que hace la muñeca (mm/s)
    # de mm/s a giro, H = A·(yaw, pitch), con los ejes cruzados (arriba en la hoja es y negativa del trackpad)
    a, b = MM_POR_GRADO
    c, s = np.cos(np.radians(EJES_GRADOS)), np.sin(np.radians(EJES_GRADOS))
    yaw, pitch = np.linalg.solve(np.array([[a, b * c], [0, b * s]]), np.stack([H[:, 0], -H[:, 1]]))
    roll = 0.25 * yaw + 0.1 * pitch
    # postura: la gravedad va casi por z y se inclina apenas con lo que gira la muñeca
    tilt = np.radians(np.cumsum(pitch - paso_bajo(pitch[:, None], 2.0, dt)[:, 0]) * dt)
    gdir = np.array([0.25, 0.10, 0.96]) + np.outer(tilt, [0.5, 0.0, -0.1])
    gdir /= np.linalg.norm(gdir, axis=1, keepdims=True)
    ax = np.array([1.0, 0, 0])
    ph = np.cross(ax, gdir)
    ph /= np.linalg.norm(ph, axis=1, keepdims=True)
    w = yaw[:, None] * gdir + pitch[:, None] * ph + roll[:, None] * ax
    ah = np.gradient(H, dt, axis=0) / 1000                  # m/s²
    la = np.stack([0.3 * ah[:, 1], ah[:, 0], 0.4 * ah[:, 1]], axis=1)
    tw = np.arange(t[0] + 0.1, t[-1] - 0.1, 1 / HZ_RELOJ)
    muestra = lambda x: np.stack([np.interp(tw - ATRASO, t, x[:, i]) for i in range(x.shape[1])], axis=1)
    n = len(tw)
    gyr = muestra(w) + SESGO + rng.normal(0, RUIDO_GIRO, (n, 3))
    grv = muestra(gdir) * G + rng.normal(0, 0.01, (n, 3))
    acc = grv + muestra(la) + rng.normal(0, RUIDO_ACEL, (n, 3))
    con_t = lambda x: np.column_stack([tw * 1000, x])
    # el trackpad: filas (t_ms, scan, id, tip, x, y), con el dedo apoyado y una última con tip = 0
    filas = []
    for t0, t1 in apoyos:
        tt = np.arange(t0, t1, 1 / HZ_PAD)
        x = np.round(np.interp(tt, t, P[:, 0]) / 0.03) * 0.03
        y = np.round(np.interp(tt, t, P[:, 1]) / 0.03) * 0.03
        filas.append(np.column_stack([tt * 1000, (tt * 10000) % 65536, np.ones(len(tt)), np.ones(len(tt)), x, y]))
        filas.append(np.array([[tt[-1] * 1000 + 7, ((tt[-1] + .007) * 10000) % 65536, 1, 0, x[-1], y[-1]]]))
    return {"touch": np.vstack(filas), "acc": con_t(acc), "gyr": con_t(gyr), "grv": con_t(grv), "letras": letras,
            "t": t, "P": P, "H": H, "V": V}


def grabar(s, carpeta):
    """escribe la sesión como draw_recorder.py, para que reconstruct_drawing.py la lea tal cual"""
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "touch.csv"), "w", newline="") as f:
        f.write("t_ms,scan_100us,contact_id,tip,x_mm,y_mm\n")
        for r in s["touch"]:
            f.write(f"{r[0]:.2f},{int(r[1])},{int(r[2])},{int(r[3])},{r[4]:.2f},{r[5]:.2f}\n")
    for nombre, a in (("ACCELERATION", s["acc"]), ("GYROSCOPE", s["gyr"]), ("GRAVITY", s["grv"])):
        with open(os.path.join(carpeta, f"{nombre}.csv"), "w") as f:
            f.write("t_ms,t_watch_ms,x,y,z\n")
            for r in a:
                f.write(f"{r[0]:.2f},0,{r[1]:.5f},{r[2]:.5f},{r[3]:.5f}\n")
    with open(os.path.join(carpeta, "letters.json"), "w", encoding="utf-8") as f:
        json.dump(s["letras"], f, ensure_ascii=False)


def trazos_de(s):
    return strokes_from(s["touch"], 1.0)


def datos_de(s, lags=None):
    """lo que stroke_data da para cada trazo; con `lags` cambia la ventana, como si se cambiara LAGS en el archivo"""
    viejo = rd.LAGS
    if lags is not None:
        rd.LAGS = lags
    try:
        bias = np.median(s["gyr"][:, 1:], axis=0)
        ds = {i: rd.stroke_data(q, s["acc"], s["gyr"], s["grv"], bias) for i, q in enumerate(trazos_de(s))}
    finally:
        rd.LAGS = viejo
    return {i: d for i, d in ds.items() if d is not None}


def redibujar(v):
    """la misma suma de main(): de la velocidad predicha al trazo, empezando en (0, 0)"""
    return np.vstack([[0, 0], np.cumsum(v[:-1], axis=0) * rd.DT / 1000])


def por_letra(pares, letras):
    """parecido de forma de cada letra, igual que main(): [(nombre, parecido), ...] en orden"""
    out = []
    for bloque in ("mayúsculas", "minúsculas"):
        for nombre, ix in letras[bloque]:
            p = [pares[i] for i in ix if i in pares]
            if p:
                out.append((nombre, rd.shape_sim([a for a, _ in p], [b for _, b in p])))
    return out


def r2_de(V, P):
    return float(1 - ((V - P) ** 2).sum() / ((V - V.mean(0)) ** 2).sum())


# ---------- los experimentos: cada número del capítulo sale de aquí ----------
def elegir_lambda(data, train):
    """la búsqueda de main(): 5 grupos de trazos dentro del entrenamiento"""
    groups = np.array_split(np.random.default_rng(1).permutation(train), 5)
    mejor, err = None, np.inf
    for lam in (0.3, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000):
        errs = []
        for k in range(5):
            tr = [i for j, g in enumerate(groups) if j != k for i in g]
            m = rd.Ridge(lam).fit(np.vstack([data[i][1] for i in tr]), np.vstack([data[i][2] for i in tr]))
            errs.append(np.mean(np.vstack([(m.predict(data[i][1]) - data[i][2]) ** 2 for i in groups[k]])))
        if np.mean(errs) < err:
            mejor, err = lam, np.mean(errs)
    return mejor


def pliegues(letras):
    return {b: {i for _, ix in letras[b] for i in ix} for b in ("mayúsculas", "minúsculas")}


def apilar(data, ids, k):
    return np.vstack([data[i][k] for i in ids])


def ridge_nunca_vistas(data, letras, lam=None, posicion=False):
    """ridge con la prueba de main(): cada abecedario lo redibuja un modelo entrenado con el otro. Con `posicion`
    aprende dónde está el dedo respecto al apoyo, en vez de su velocidad."""
    pares = {}
    objetivo = (lambda i: data[i][3] - data[i][3][0]) if posicion else (lambda i: data[i][2])
    for test in pliegues(letras).values():
        train = [i for i in data if i not in test]
        l = lam if lam is not None else elegir_lambda(data, train)
        m = rd.Ridge(l).fit(apilar(data, train, 1), np.vstack([objetivo(i) for i in train]))
        for i in test:
            if i in data:
                p = m.predict(data[i][1])
                pares[i] = (data[i][3], p - p[0] if posicion else redibujar(p))
    return pares


def mediana(lista):
    return float(np.median([v for _, v in lista]))


def experimento_principal():
    """reconstruct_drawing.py tal cual sobre la sesión inventada"""
    import contextlib
    import io
    import re
    s = sesion()
    grabar(s, CARPETA)
    argv, sys.argv = sys.argv, ["reconstruct_drawing.py", CARPETA]
    salida = io.StringIO()
    try:
        with contextlib.redirect_stdout(salida):
            rd.main()
    finally:
        sys.argv = argv
    with open(os.path.join(CARPETA, "reconstruccion.json"), encoding="utf-8") as f:
        resumen = json.load(f)
    z = np.load(os.path.join(CARPETA, "reconstruccion.npz"))
    pares = {m: {int(k.split("_")[1]): (z[k], z[k.replace("_true", "_pred")]) for k in z.files
                 if k.startswith(m + "_") and k.endswith("_true")} for m in ("baseline", "ridge", "red")}
    lams = [float(x) for x in re.findall(r"ridge λ=([\d.]+)", salida.getvalue())]
    return s, {"resumen": resumen, "pares": pares, "lams": lams, "letras": s["letras"],
               "parecidos": {m: por_letra(pares[m], s["letras"]) for m in pares}, "salida": salida.getvalue()}


def experimento_justa(s, lam):
    """el mismo ridge medido de cuatro maneras: R² de la velocidad"""
    data = datos_de(s)
    ids = list(data)
    X, V = apilar(data, ids, 1), apilar(data, ids, 2)
    r = {"mismos datos": r2_de(V, rd.Ridge(lam).fit(X, V).predict(X))}
    rng = np.random.default_rng(3)
    grupo = rng.permutation(len(X)) % 5
    P = np.empty_like(V)
    for k in range(5):
        P[grupo == k] = rd.Ridge(lam).fit(X[grupo != k], V[grupo != k]).predict(X[grupo == k])
    r["instantes al azar"] = r2_de(V, P)
    grupos = np.array_split(rng.permutation(ids), 5)
    Vs, Ps = [], []
    for k in range(5):
        tr = [i for j, g in enumerate(grupos) if j != k for i in g]
        m = rd.Ridge(lam).fit(apilar(data, tr, 1), apilar(data, tr, 2))
        Vs.append(apilar(data, grupos[k], 2))
        Ps.append(m.predict(apilar(data, grupos[k], 1)))
    r["grupos de trazos"] = r2_de(np.vstack(Vs), np.vstack(Ps))
    Vs, Ps = [], []
    for test in pliegues(s["letras"]).values():
        tr = [i for i in ids if i not in test]
        te = [i for i in ids if i in test]
        m = rd.Ridge(lam).fit(apilar(data, tr, 1), apilar(data, tr, 2))
        Vs.append(apilar(data, te, 2))
        Ps.append(m.predict(apilar(data, te, 1)))
    r["letras nunca vistas"] = r2_de(np.vstack(Vs), np.vstack(Ps))
    return r


def experimento_ventanas(s):
    res = {}
    for ms in (0, 80, 160, 240, 400):
        d = datos_de(s, np.arange(-ms, ms + 1, 40))
        res[ms] = {"rasgos": d[next(iter(d))][1].shape[1], "parecidos": por_letra(ridge_nunca_vistas(d, s["letras"]), s["letras"])}
    return res


def experimento_lambda(s, n_letras=3):
    """un λ que va de casi nada a enorme, entrenando con pocas letras para que se note copiar el ruido"""
    data = datos_de(s)
    M = [ix for _, ix in s["letras"]["minúsculas"]]
    rng = np.random.default_rng(5)
    tr = [i for k in rng.choice(len(M), n_letras, replace=False) for i in M[k] if i in data]
    test = [i for _, ix in s["letras"]["mayúsculas"] for i in ix if i in data]
    Xt, Vt = apilar(data, tr, 1), apilar(data, tr, 2)
    Xe, Ve = apilar(data, test, 1), apilar(data, test, 2)
    filas = []
    for lam in 10.0 ** np.arange(-3, 9.01, 0.5):
        m = rd.Ridge(lam).fit(Xt, Vt)
        pares = {i: (data[i][3], redibujar(m.predict(data[i][1]))) for i in test}
        solo = {"mayúsculas": s["letras"]["mayúsculas"], "minúsculas": []}
        filas.append({"lam": float(lam), "r2_entreno": r2_de(Vt, m.predict(Xt)), "r2_prueba": r2_de(Ve, m.predict(Xe)),
                      "parecido": mediana(por_letra(pares, solo)), "pares": pares, "norma": float(np.linalg.norm(m.W[:-1]))})
    return {"filas": filas, "n_entreno": len(Xt), "rasgos": Xt.shape[1], "letras_entreno": n_letras}


def experimento_datos():
    """¿y con más datos? la misma sesión, más larga: 1, 3 y 10 abecedarios de cada clase, con el mismo examen"""
    res = []
    for vueltas in (1, 3, 10):
        s = sesion(semilla=100 + vueltas, vueltas=vueltas)
        d = datos_de(s)
        pr, pn = {}, {}
        for test in pliegues(s["letras"]).values():
            train = [i for i in d if i not in test]
            X, V = apilar(d, train, 1), apilar(d, train, 2)
            ridge = rd.Ridge(elegir_lambda(d, train)).fit(X, V)
            red = rd.MLP().fit(X, V)
            for i in test:
                if i in d:
                    pr[i] = (d[i][3], redibujar(ridge.predict(d[i][1])))
                    pn[i] = (d[i][3], redibujar(red.predict(d[i][1])))
        res.append({"vueltas": vueltas, "instantes": int(sum(len(x[0]) for x in d.values())), "letras": 53 * vueltas,
                    "ridge": mediana(por_letra(pr, s["letras"])), "red": mediana(por_letra(pn, s["letras"]))})
        print(res[-1], flush=True)
    return res


class ValidarPorTrazos:
    """se pone como rng de MLP: su primera permutación deja primero trazos enteros, así que MLP.fit, sin cambiarle
    nada, valida con trazos que no vio en vez de con instantes al azar"""

    def __init__(self, largos, semilla=0):
        self.rng = np.random.default_rng(semilla)
        self.largos, self.primera = largos, True

    def __getattr__(self, nombre):
        return getattr(self.rng, nombre)

    def permutation(self, n):
        if not self.primera or isinstance(n, np.ndarray):
            return self.rng.permutation(n)
        self.primera = False
        ini = np.concatenate([[0], np.cumsum(self.largos)])
        trozos = [np.arange(ini[k], ini[k + 1]) for k in self.rng.permutation(len(self.largos))]
        return np.concatenate(trozos)


def experimento_validacion(s):
    """la misma red con la parada temprana medida de dos maneras"""
    d = datos_de(s)
    res = {}
    for nombre in ("instantes al azar", "trazos enteros"):
        por = []
        for semilla in range(5):
            pares = {}
            for test in pliegues(s["letras"]).values():
                train = [i for i in d if i not in test]
                red = rd.MLP(seed=semilla)
                if nombre == "trazos enteros":
                    red.rng = ValidarPorTrazos([len(d[i][0]) for i in train], semilla)
                red.fit(apilar(d, train, 1), apilar(d, train, 2))
                for i in test:
                    if i in d:
                        pares[i] = (d[i][3], redibujar(red.predict(d[i][1])))
            por.append(mediana(por_letra(pares, s["letras"])))
        res[nombre] = por
    return res


def experimento_otras_tardes(n=12):
    """lo que una sola sesión no puede decir: repetir toda la sesión con otra semilla"""
    filas = []
    for k in range(n):
        s = sesion(semilla=200 + k)
        a = mediana(por_letra(ridge_nunca_vistas(datos_de(s), s["letras"]), s["letras"]))
        b = mediana(por_letra(ridge_nunca_vistas(datos_de(s, np.arange(-160, 161, 40)), s["letras"]), s["letras"]))
        filas.append((a, b))
    return filas


def remuestrear(a, b, n=10000, semilla=11):
    """la diferencia de medianas entre dos modelos, volviendo a sacar las letras al azar con repetición"""
    a, b = np.asarray(a), np.asarray(b)
    k = np.random.default_rng(semilla).integers(0, len(a), (n, len(a)))
    return np.median(a[k], axis=1) - np.median(b[k], axis=1)


def todo(rehacer=False):
    """cada experimento se guarda aparte en media/sim12/: si uno falla, los demás no se repiten"""
    import pickle
    os.makedirs(CARPETA, exist_ok=True)

    def parte(nombre, cuenta):
        f = os.path.join(CARPETA, f"parte-{nombre}.pkl")
        if os.path.exists(f) and not rehacer:
            with open(f, "rb") as h:
                return pickle.load(h)
        v = cuenta()
        with open(f, "wb") as h:
            pickle.dump(v, h)
        return v

    guardada = {}

    def la_sesion():
        if "s" not in guardada:
            guardada["s"] = sesion()
        return guardada["s"]

    princ = parte("principal", lambda: experimento_principal()[1])
    r = {"principal": princ,
         "justa": parte("justa", lambda: {l: experimento_justa(la_sesion(), l) for l in (1.0, princ["lams"][0])}),
         "ventanas": parte("ventanas", lambda: experimento_ventanas(la_sesion())),
         "lambda": parte("lambda", lambda: experimento_lambda(la_sesion())),
         "posicion": parte("posicion", lambda: por_letra(ridge_nunca_vistas(datos_de(la_sesion()), princ["letras"], posicion=True), princ["letras"])),
         "velocidad": parte("velocidad", lambda: por_letra(ridge_nunca_vistas(datos_de(la_sesion()), princ["letras"]), princ["letras"])),
         "validacion": parte("validacion", lambda: experimento_validacion(la_sesion())),
         "datos": parte("datos", experimento_datos),
         "tardes": parte("tardes", experimento_otras_tardes),
         "sesion": parte("sesion", lambda: {k: la_sesion()[k] for k in ("t", "P", "H", "V", "letras")}),
         "trazos": parte("trazos", lambda: trazos_de(la_sesion()))}
    return r


def informe(r):
    p = r["principal"]
    print(p["salida"])
    print("R² de la velocidad según cómo se mida:")
    for lam, d in r["justa"].items():
        print(f"  λ = {lam:g}: " + " · ".join(f"{k} {v:.2f}" for k, v in d.items()))
    print("ventanas (ridge, parecido mediano):")
    for ms, d in r["ventanas"].items():
        print(f"  ±{ms} ms: {d['rasgos']} rasgos, {mediana(d['parecidos']):.3f}")
    print(f"posición directa {mediana(r['posicion']):.3f} · velocidad integrada {mediana(r['velocidad']):.3f}")
    L = r["lambda"]
    print(f"λ, entrenando con {L['letras_entreno']} letras ({L['n_entreno']} instantes, {L['rasgos']} rasgos):")
    for f in L["filas"][::2]:
        print(f"  λ = {f['lam']:.3g}: R² entrenamiento {f['r2_entreno']:.2f}, prueba {f['r2_prueba']:.2f}, parecido {f['parecido']:.2f}, |W| {f['norma']:.1f}")
    print("la red, según con qué se para (5 semillas): " + " · ".join(f"{k} {np.round(v, 3).tolist()}" for k, v in r["validacion"].items()))
    print("más datos:")
    for f in r["datos"]:
        print(f"  ×{f['vueltas']}: {f['instantes']} instantes, ridge {f['ridge']:.3f}, red {f['red']:.3f}")
    a = np.array([v for _, v in p["parecidos"]["ridge"]])
    b = np.array([v for _, v in p["parecidos"]["red"]])
    d = remuestrear(a, b)
    print(f"ridge − red: {np.median(a) - np.median(b):+.3f}, 95 % de las remuestras entre {np.percentile(d, 2.5):+.3f} y {np.percentile(d, 97.5):+.3f}; desviación de una letra {a.std():.3f}")
    v240 = [x for _, x in r["ventanas"][240]["parecidos"]]
    v160 = [x for _, x in r["ventanas"][160]["parecidos"]]
    d = remuestrear(v240, v160)
    print(f"±240 − ±160: {np.median(v240) - np.median(v160):+.3f}, 95 % entre {np.percentile(d, 2.5):+.3f} y {np.percentile(d, 97.5):+.3f}")
    t = np.array(r["tardes"])
    print(f"{len(t)} sesiones más: ±240 mediana {t[:, 0].mean():.3f} ± {t[:, 0].std(ddof=1):.3f}; ±240 − ±160 de {np.min(t[:, 0] - t[:, 1]):+.3f} a {np.max(t[:, 0] - t[:, 1]):+.3f}")


def referencias():
    """lo que tools/test_aprender.js compara con el código de verdad: salidas de Python para entradas pequeñas.
    Node no puede llamar a numpy, así que las pruebas llevan estos números pegados; si cambia tools/, se rehacen aquí."""
    from analyze_dataset import confusion, fstat, knn_loo
    from analyze_drawing import groups_by_pause, r2
    X = np.array([[1.2, 30], [0.4, 12], [2.5, 41], [1.9, 38], [0.7, 9], [3.1, 60], [2.2, 35], [1.1, 20], [2.8, 44], [0.2, 15]], float)
    y = np.array([4.1, 1.0, 7.2, 6.3, 1.9, 9.8, 6.0, 3.5, 7.9, 1.2])
    ref = {"X": X.tolist(), "y": y.tolist(), "ridge": {}}
    for lam in (0.5, 10.0):
        ref["ridge"][str(lam)] = rd.Ridge(lam).fit(X, y[:, None]).W[:, 0].tolist()
    val, coef = r2(y[:, None], X)
    ref["r2"], ref["coef"] = float(val), coef[:, 0].tolist()
    a = np.array([[0, 0], [1, 2], [2, 3], [4, 3], [5, 1], [6, 0]], float)
    b = np.array([[0, 0], [1.5, 1], [2.5, 2], [3, 2.5], [4, 1], [4.5, -1]], float)
    ref["forma"] = {"a": a.tolist(), "b": b.tolist(), "parecido": rd.shape_sim([a], [b])}
    c = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2]
    G = np.array([[1.0, 2], [1.2, 2.2], [0.8, 1.9], [1.1, 3.0], [2.0, 2.5], [2.2, 2.4], [1.9, 2.9], [2.4, 2.1], [3.0, 1.0], [3.3, 1.2], [2.9, .8], [1.3, 2.3]])
    p = knn_loo(G, c)
    ref["gestos"] = {"X": G.tolist(), "y": c, "pred": [int(v) for v in p], "F": fstat(G, c), "confusion": confusion(c, p, [0, 1, 2])}
    filas = []
    tramos = [[0, 200], [240, 400], [480, 600], [800, 816], [1700, 2000], [3000, 3100]]         # huecos de 48 y 88 ms, un roce
    for t0, t1 in tramos:
        filas += [(float(t), 0, 1, 1, 0.0, 0.0) for t in range(t0, t1, 8)]
    tr = strokes_from(np.array(filas), 1)
    ref["toques"] = {"tramos": tramos, "trazos": len(tr), "grupos": [len(g) for g in groups_by_pause(tr)]}
    print(json.dumps(ref, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--referencias" in sys.argv:
        referencias()
    else:
        informe(todo("--rehacer" in sys.argv))
