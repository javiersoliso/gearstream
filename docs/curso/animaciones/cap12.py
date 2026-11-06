"""Animaciones del capítulo 12 (Aprender de datos), una por concepto.

    python docs/curso/animaciones/render.py cap12 Escena ...             # a GIF en docs/curso/media/cap12/
    python -m manim -ql docs/curso/animaciones/cap12.py Sobreajuste      # una, rápido, para mirarla

Los datos son inventados: las grabaciones de verdad no se publican. La sesión de escritura sale de datos_cap12.py,
que la pasa por tools/reconstruct_drawing.py sin cambiarle nada; la primera vez tarda unos minutos y queda guardada
en media/sim12/. Ridge, MLP, shape_sim, r2, strokes_from, groups_by_pause, knn_loo, fstat, confusion, signals y
window_features son los del repo, importados tal cual. Lo general lo comprueba tools/test_aprender.js.
"""
import os
import sys

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "..", "..", "tools"))
import datos_cap12 as D                                                               # noqa: E402
from analyze_dataset import confusion, fstat, knn_loo, signals, window_features       # noqa: E402  los de verdad
from analyze_drawing import groups_by_pause, r2, strokes_from                         # noqa: E402
from reconstruct_drawing import LAGS, MLP, Ridge, shape_sim                           # noqa: E402

REAL, RECO = "#58c4dd", "#f0997b"      # cian y coral, los de tools/render_letters_gif.py
DATO, MODELO, ERROR, BIEN, GRIS = YELLOW, BLUE, RED, GREEN, GREY_B
COLORES = [BLUE, YELLOW, GREEN, PURPLE, ORANGE, RED_B]


def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


def nota(s, size=22):
    return texto(s, size).to_edge(DOWN, buff=0.15)


def ejes(x, y, ancho=10.5, alto=2.2, numeros=True, **kw):
    return Axes(x_range=x, y_range=y, x_length=ancho, y_length=alto, tips=False,
                axis_config={"include_numbers": numeros, "font_size": 18}, **kw)


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


def curva(p, color, w=3):
    m = VMobject(stroke_color=color, stroke_width=w)
    m.set_points_as_corners(np.asarray(p, float))
    return m


def en_ejes(ax, xs, ys):
    return np.array([ax.c2p(a, b) for a, b in zip(xs, ys)])


def trozos(ax, xs, ys, color, w=3, x_rango=None, y_rango=None):
    """una curva cortada donde se sale de los ejes: no se dibuja lo que no cabe"""
    x0, x1 = x_rango or (ax.x_range[0], ax.x_range[1])
    y0, y1 = y_rango or (ax.y_range[0], ax.y_range[1])
    dentro = (np.asarray(xs) >= x0) & (np.asarray(xs) <= x1) & (np.asarray(ys) >= y0) & (np.asarray(ys) <= y1)
    g, ini = VGroup(), None
    for i, d in enumerate(list(dentro) + [False]):
        if d and ini is None:
            ini = i
        if not d and ini is not None:
            if i - ini >= 2:
                g.add(curva(en_ejes(ax, xs[ini:i], ys[ini:i]), color, w))
            ini = None
    return g


def letra(pares, ix, centro, alto=1.4, w=3, paso=3):
    """la letra real y la redibujada; cada trazo redibujado arranca donde arranca el real, sin retoques"""
    ids = [i for i in ix if i in pares]
    reales = [pares[i][0] for i in ids]
    recon = [pares[i][0][0] + pares[i][1] for i in ids]
    r = np.vstack(reales)
    c = (r.max(0) + r.min(0)) / 2
    k = alto / max(np.ptp(r[:, 1]), np.ptp(r[:, 0]), 1e-6)
    conv = lambda p: np.asarray(centro) + np.column_stack([(p[::paso, 0] - c[0]) * k, -(p[::paso, 1] - c[1]) * k, np.zeros(len(p[::paso]))])
    return VGroup(*[curva(conv(p), REAL, w) for p in reales]), VGroup(*[curva(conv(p), RECO, w) for p in recon])


def indices(letras, nombre):
    for b in ("mayúsculas", "minúsculas"):
        for n, ix in letras[b]:
            if n == nombre:
                return ix
    raise KeyError(nombre)


def barra(ax_izq, largo, alto, color):
    return Rectangle(width=max(largo, 1e-3), height=alto, stroke_width=0, fill_color=color, fill_opacity=0.9)\
        .move_to(ax_izq, aligned_edge=LEFT)


def elipses(Q, centro, niveles, ax, color=GRIS):
    """curvas de nivel de (w − c)ᵀ Q (w − c) = nivel"""
    val, vec = np.linalg.eigh(Q)
    g = VGroup()
    u = np.linspace(0, 2 * np.pi, 240)
    for c in niveles:
        p = (vec @ np.vstack([np.sqrt(c / val[0]) * np.cos(u), np.sqrt(c / val[1]) * np.sin(u)])).T + centro
        g.add(trozos(ax, p[:, 0], p[:, 1], color, 1.5))
    return g


def gestos(semilla=4, escala=(1, 1, 1, 1), corrimiento=(0, 0, 0, 0)):
    """gestos inventados: 6 gestos × 15 tomas, con 4 medidas que llevan el nombre de las de event_features"""
    medias = {"2 dedos": (1.2, 45, 1.0, 2.0), "3 dedos": (1.8, 50, 1.0, 2.5), "4 dedos": (2.4, 55, 1.0, 3.0),
              "5 dedos": (2.8, 58, 1.0, 3.0), "puño": (3.9, 85, 1.1, 6.0), "brazo": (5.5, 150, 1.3, 35.0)}
    sd = np.array([0.25, 13, 0.3, 1.5])
    rng = np.random.default_rng(semilla)
    X, y = [], []
    for nombre, m in medias.items():
        for _ in range(15):
            f = np.array(m) + rng.normal(0, 1, 4) * sd
            f[2] = max(1, round(f[2]))
            X.append(f * np.array(escala) + np.array(corrimiento))
            y.append(nombre)
    return np.array(X), y, list(medias), ["golpe máx (m/s²)", "giro x máx (°/s)", "nº de golpes", "cambio de gravedad (°)"]


# ---------------------------------------------------------------------------------------------------------
class LetrasRedibujadas(Scene):
    """La pregunta guía: letras que el modelo nunca vio, reales y redibujadas, con su parecido de forma."""

    def construct(self):
        r = D.todo()["principal"]
        pares, letras = r["pares"]["ridge"], r["letras"]
        orden = sorted(r["parecidos"]["ridge"], key=lambda p: -p[1])
        elegidas = [orden[int(round(k))] for k in np.linspace(0, len(orden) - 1, 14)]
        titulo = texto("¿Puede el reloj redibujar una letra que nunca vio?", 32).to_edge(UP)
        self.play(Write(titulo))
        reales, recos, cifras = VGroup(), VGroup(), VGroup()
        for j, (nombre, p) in enumerate(elegidas):
            c = np.array([-5.7 + 1.9 * (j % 7), 1.45 - 2.75 * (j // 7), 0])
            a, b = letra(pares, indices(letras, nombre), c, alto=1.5)
            reales.add(a)
            recos.add(b)
            cifras.add(texto(f"{p:.2f}", 20).move_to(c + DOWN * 1.15))
        leyenda = VGroup(texto("el dedo (trackpad)", 20, color=REAL), texto("lo que redibuja el reloj", 20, color=RECO))\
            .arrange(RIGHT, buff=0.6).next_to(titulo, DOWN, buff=0.12)
        self.play(FadeIn(leyenda), LaggedStart(*[Create(a) for a in reales], lag_ratio=0.08), run_time=2.5)
        self.play(LaggedStart(*[Create(b) for b in recos], lag_ratio=0.08), run_time=3)
        self.play(FadeIn(cifras))
        s = r["resumen"]["ridge"]
        self.play(FadeIn(nota(f"De la mejor a la peor. Datos inventados: mediana {s['parecido_mediano']:.2f}, "
                              f"{s['letras_sobre_0.8']} de {s['n']} letras por encima de 0.8.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class LoQueVeElReloj(Scene):
    """Pregunta 1: el dedo hace la letra, la muñeca solo una parte, y el reloj está en la muñeca."""

    def construct(self):
        e = D.todo()
        ses, tr = e["sesion"], e["trazos"]
        i = indices(ses["letras"], "S")[0]
        sel = (ses["t"] * 1000 >= tr[i][0, 0]) & (ses["t"] * 1000 <= tr[i][-1, 0])
        t, dt = ses["t"][sel] - ses["t"][sel][0], 1 / D.HZ_SIM
        dedo = np.cumsum(ses["V"][sel], axis=0) * dt
        muneca = np.cumsum(ses["H"][sel], axis=0) * dt
        largo = lambda p: np.hypot(*np.diff(p, axis=0).T).sum()
        razon = largo(muneca) / largo(dedo)
        titulo = texto("El reloj va en la muñeca, no en el dedo", 34).to_edge(UP)
        k = 3.6 / np.ptp(dedo[:, 1])
        c1, c2 = np.array([-4.6, 0.1, 0]), np.array([-0.4, 0.1, 0])
        conv = lambda p, c: c + np.column_stack([(p[:, 0] - (p[:, 0].max() + p[:, 0].min()) / 2) * k, -(p[:, 1] - (p[:, 1].max() + p[:, 1].min()) / 2) * k, np.zeros(len(p))])
        P1, P2 = conv(dedo, c1), conv(muneca, c2)
        l1 = texto("el dedo", 24, color=REAL).move_to(c1 + UP * 2.35)
        l2 = texto("la muñeca, a la misma escala", 24, color=RECO).move_to(c2 + UP * 2.35)
        ax = ejes([0, np.ceil(t[-1] * 2) / 2, 0.5], [0, 250, 50], ancho=3.9, alto=2.6).move_to(RIGHT * 4.6 + UP * 0.2)
        l3 = texto("rapidez (mm/s)", 20).next_to(ax, UP, buff=0.15)
        v1, v2 = np.hypot(*ses["V"][sel].T), np.hypot(*ses["H"][sel].T)
        paso = 12
        self.play(Write(titulo), FadeIn(l1, l2, l3), Create(ax))
        q = ValueTracker(2)
        n = lambda: int(q.get_value())
        t1 = always_redraw(lambda: curva(P1[:n():paso], REAL, 4) if n() > 2 * paso else VMobject())
        t2 = always_redraw(lambda: curva(P2[:n():paso], RECO, 4) if n() > 2 * paso else VMobject())
        g1 = always_redraw(lambda: curva(en_ejes(ax, t[:n():paso], v1[:n():paso]), REAL, 3) if n() > 2 * paso else VMobject())
        g2 = always_redraw(lambda: curva(en_ejes(ax, t[:n():paso], v2[:n():paso]), RECO, 3) if n() > 2 * paso else VMobject())
        d1 = always_redraw(lambda: Dot(P1[n() - 1], radius=0.08, color=WHITE))
        d2 = always_redraw(lambda: Dot(P2[n() - 1], radius=0.08, color=WHITE))
        self.add(t1, t2, g1, g2, d1, d2)
        self.play(q.animate.set_value(len(t)), run_time=7, rate_func=linear)
        self.wait(0.5)
        self.play(FadeIn(nota(f"Inventado: la muñeca recorre {razon:.2f} del largo del dedo, y solo lo lento.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Rasgos(Scene):
    """Un trozo de señal se vuelve unos pocos números, y esos números se pueden comparar."""

    def construct(self):
        fs, seg = 100, 6
        rng = np.random.default_rng(1)
        n = seg * fs
        t = np.arange(3 * n) / fs
        gyr, la = rng.normal(0, 1.0, (3 * n, 3)), rng.normal(0, 0.05, (3 * n, 3))
        gyr[n:2 * n, 1] += 60 * np.sin(2 * np.pi * 0.8 * t[n:2 * n])                # muñeca lenta
        la[n:2 * n, 1] += 0.4 * np.sin(2 * np.pi * 0.8 * t[n:2 * n])
        tecla = np.sin(2 * np.pi * 6 * t[2 * n:]) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * t[2 * n:]))
        gyr[2 * n:, 1] += 18 * tecla                                                # teclear
        la[2 * n:, :] += 0.5 * tecla[:, None] + rng.normal(0, 0.25, (n, 3))
        grv = np.tile([0.0, 0.0, 9.81], (3 * n, 1))
        la_, _, golpe, _, _ = signals(grv + la, gyr, grv)
        nombres = ["reposo", "muñeca lenta", "teclear"]
        titulo = texto("Rasgos: un trozo de señal en pocos números", 34).to_edge(UP)
        a1 = ejes([0, 18, 3], [-80, 80, 40], ancho=11.6, alto=1.7).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 0.4)
        l1 = texto("giro y\n(°/s)", 18).next_to(a1, LEFT, buff=0.15)
        sen = curva(en_ejes(a1, t[::2], gyr[::2, 1]), GRIS, 1.5)
        marcas = VGroup(*[texto(nm, 18, color=COLORES[k]).move_to(a1.c2p(3 + 6 * k, 74)) for k, nm in enumerate(nombres)])
        a2 = ejes([0, 50, 10], [0, 12, 3], ancho=5.2, alto=3.1).move_to(RIGHT * 3.4 + DOWN * 1.35)
        x2 = texto("giro y rms (°/s)", 18).next_to(a2, DOWN, buff=0.08)
        y2 = texto("frecuencia\ndominante\n(Hz)", 18).next_to(a2, LEFT, buff=0.15)
        self.play(Write(titulo), Create(a1), FadeIn(l1, marcas), Create(sen), Create(a2), FadeIn(x2, y2), run_time=2.5)
        etiquetas = ["giro x rms", "giro y rms", "giro z rms", "acel. lineal rms", "golpe rms", "frecuencia dominante", "energía > 8 Hz"]
        unidades = ["°/s", "°/s", "°/s", "m/s²", "m/s²", "Hz", "%"]
        nombres_col = VGroup(*[texto(e, 19) for e in etiquetas]).arrange(DOWN, aligned_edge=LEFT, buff=0.11).move_to(LEFT * 4.5 + DOWN * 1.35)
        self.play(FadeIn(nombres_col))
        caja = Rectangle(width=a1.c2p(1, 0)[0] - a1.c2p(0, 0)[0], height=1.7, stroke_color=WHITE, stroke_width=3)
        valores, puntos = VGroup(), VGroup()
        self.add(caja, valores, puntos)
        for a in range(0, 3 * n - fs + 1, fs // 2):
            f = window_features(la_, gyr, golpe, a, a + fs)
            caja.move_to(a1.c2p(a / fs + 0.5, 0))
            valores.become(VGroup(*[texto(f"{v:.1f} {u}", 19, color=DATO).next_to(nombres_col[k], RIGHT, buff=0.25).align_to(nombres_col, RIGHT).shift(RIGHT * 1.45)
                                    for k, (v, u) in enumerate(zip(f, unidades))]))
            k = min(2, (a + fs // 2) // n)
            if a % n <= n - fs:                               # solo las ventanas que caen enteras en una actividad
                puntos.add(Dot(a2.c2p(min(f[1], 50), min(f[5], 12)), radius=0.07, color=COLORES[k]))
            self.wait(0.17)
        self.play(FadeOut(caja), FadeIn(nota("Cien muestras por eje se vuelven siete números: cada actividad cae en su sitio.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Segmentar(Scene):
    """strokes_from y groups_by_pause sobre toques inventados: dónde se corta y dónde no."""

    def construct(self):
        filas = []

        def tramo(t0, t1):
            for t in np.arange(t0, t1, 0.007):
                filas.append((t * 1000, 0, 1, 1, 0.0, 0.0))
            filas.append((t1 * 1000, 0, 1, 0, 0.0, 0.0))

        def seguido(tramos):                                  # un mismo apoyo con huecos: sin fila de tip = 0 en medio
            for t0, t1 in tramos:
                for t in np.arange(t0, t1, 0.007):
                    filas.append((t * 1000, 0, 1, 1, 0.0, 0.0))
            filas.append((tramos[-1][1] * 1000, 0, 1, 0, 0.0, 0.0))

        seguido([(0.2, 0.75), (0.79, 1.2)])                   # hueco de 40 ms: no corta
        seguido([(1.5, 1.9), (1.98, 2.3)])                    # hueco de 80 ms: corta
        tramo(2.55, 2.562)                                    # un roce de dos filas: se descarta
        tramo(3.6, 4.2)
        tramo(4.5, 4.9)
        tramo(6.1, 6.9)
        touch = np.array(filas)
        tr = strokes_from(touch, 1)
        gr = groups_by_pause(tr)
        titulo = texto("Segmentar: dónde empieza y dónde termina cada cosa", 32).to_edge(UP)
        ax = ejes([0, 7.5, 1], [0, 1, 1], ancho=12, alto=0.9, y_axis_config={"include_numbers": False}).move_to(UP * 1.75)
        ax.y_axis.set_opacity(0)
        lx = texto("tiempo (s)", 18).next_to(ax.c2p(7.5, 0), DOWN, buff=0.4).shift(LEFT * 0.35)
        ticks = VGroup(*[Line(ax.c2p(r[0] / 1000, 0.05), ax.c2p(r[0] / 1000, 0.9), color=GRIS, stroke_width=1) for r in touch[touch[:, 3] == 1][::2]])
        self.play(Write(titulo), Create(ax), FadeIn(lx), FadeIn(ticks))
        n0 = nota("Cada rayita es una lectura del trackpad con el dedo apoyado.")
        self.play(FadeIn(n0))
        self.wait(1.5)
        # los dos huecos, de cerca
        z1 = ejes([0.65, 0.9, 0.05], [0, 1, 1], ancho=5, alto=0.7, y_axis_config={"include_numbers": False}).move_to(LEFT * 3.4 + DOWN * 0.2)
        z2 = ejes([1.82, 2.07, 0.05], [0, 1, 1], ancho=5, alto=0.7, y_axis_config={"include_numbers": False}).move_to(RIGHT * 3.4 + DOWN * 0.2)
        z1.y_axis.set_opacity(0)
        z2.y_axis.set_opacity(0)
        vistas = VGroup()
        for z, (a, b) in ((z1, (0.65, 0.9)), (z2, (1.82, 2.07))):
            for rr in touch[touch[:, 3] == 1]:
                if a <= rr[0] / 1000 <= b:
                    vistas.add(Line(z.c2p(rr[0] / 1000, 0.05), z.c2p(rr[0] / 1000, 0.9), color=GRIS, stroke_width=2))
        apoyado = touch[touch[:, 3] == 1, 0]
        hueco = lambda a, b: np.diff(apoyado[(apoyado >= a * 1000) & (apoyado <= b * 1000)]).max()
        e1 = texto(f"hueco de {hueco(0.65, 0.9):.0f} ms: sigue el mismo trazo", 21, color=BIEN).next_to(z1, UP, buff=0.12)
        e2 = texto(f"hueco de {hueco(1.82, 2.07):.0f} ms: corta (más de 60 ms)", 21, color=ERROR).next_to(z2, UP, buff=0.12)
        self.play(FadeOut(n0), Create(z1), Create(z2), FadeIn(vistas), FadeIn(e1, e2))
        self.wait(2.5)
        # los trazos que salen de la cuenta
        bandas = VGroup()
        for k, s in enumerate(tr):
            bandas.add(Rectangle(width=ax.c2p(s[-1, 0] / 1000, 0)[0] - ax.c2p(s[0, 0] / 1000, 0)[0], height=0.8, stroke_width=0,
                                 fill_color=COLORES[k % 6], fill_opacity=0.6).move_to(ax.c2p((s[0, 0] + s[-1, 0]) / 2000, 0.47)))
        self.play(FadeIn(bandas, lag_ratio=0.2), run_time=1.5)
        n1 = nota(f"{len(tr)} trazos: la rayita suelta tiene menos de 3 lecturas y no cuenta.")
        self.play(FadeIn(n1))
        self.wait(2.5)
        # los grupos
        self.play(FadeOut(z1, z2, vistas, e1, e2, n1))
        llaves = VGroup()
        for k, g in enumerate(gr):
            a, b = g[0][0, 0] / 1000, g[-1][-1, 0] / 1000
            base = Line(ax.c2p(a, 0), ax.c2p(b, 0))
            ll = Brace(base, DOWN, buff=0.45)
            llaves.add(VGroup(ll, texto(f"letra {k + 1}: {len(g)} trazo{'s' if len(g) > 1 else ''}", 21).next_to(ll, DOWN, buff=0.1)))
        self.play(LaggedStart(*[FadeIn(x) for x in llaves], lag_ratio=0.3), run_time=2)
        pausas = [(gr[i + 1][0][0, 0] - gr[i][-1][-1, 0]) / 1000 for i in range(len(gr) - 1)]
        f = texto("una pausa de más de 0.9 s separa dos grupos: aquí " + " y ".join(f"{p:.1f} s" for p in pausas), 24).move_to(DOWN * 1.3)
        self.play(FadeIn(f))
        self.play(FadeIn(nota("Solo dos umbrales de tiempo: 60 ms para los trazos, 0.9 s para los grupos.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Estandarizar(Scene):
    """Con unidades distintas la distancia solo ve el rasgo de números grandes."""

    def construct(self):
        rng = np.random.default_rng(6)
        A = np.column_stack([rng.normal(120, 35, 14), rng.normal(1.0, 0.18, 14)])
        B = np.column_stack([rng.normal(130, 35, 14), rng.normal(2.2, 0.18, 14)])
        X = np.vstack([A, B])
        y = [0] * 14 + [1] * 14
        nuevo = np.array([B[:, 0].max() - 1.5, 1.05])          # elegido para que se vea: cae junto a un puño en giro
        mu, sd = X.mean(0), X.std(0) + 1e-9                  # como Ridge.fit y knn_loo
        Z, zn = (X - mu) / sd, (nuevo - mu) / sd
        vecino_crudo = int(np.argmin(np.linalg.norm(X - nuevo, axis=1)))
        vecino_z = int(np.argmin(np.linalg.norm(Z - zn, axis=1)))
        titulo = texto("Estandarizar: que cada rasgo pese parecido", 34).to_edge(UP)
        # crudo: las dos medidas a la misma escala, como las ve la distancia
        a1 = ejes([0, 240, 40], [-60, 60, 20], ancho=9.6, alto=4.8).move_to(DOWN * 0.15 + RIGHT * 0.3)
        x1 = texto("giro rms (°/s)", 20).next_to(a1, DOWN, buff=0.08)
        y1 = texto("golpe\n(m/s²)", 20).next_to(a1, LEFT, buff=0.15)
        puntos = VGroup(*[Dot(a1.c2p(*p), radius=0.07, color=COLORES[c]) for p, c in zip(X, y)])
        nd = Star(5, outer_radius=0.14, color=WHITE, fill_opacity=1).move_to(a1.c2p(*nuevo))
        nombres = VGroup(texto("pellizco", 22, color=COLORES[0]), texto("puño", 22, color=COLORES[1]), texto("nuevo (es un pellizco)", 22))\
            .arrange(RIGHT, buff=0.5).next_to(titulo, DOWN, buff=0.1)
        self.play(Write(titulo), Create(a1), FadeIn(x1, y1, nombres), FadeIn(puntos), FadeIn(nd))
        n1 = nota(f"A la misma escala el golpe casi no se ve: va de {X[:, 1].min():.1f} a {X[:, 1].max():.1f}, el giro de {X[:, 0].min():.0f} a {X[:, 0].max():.0f}.")
        self.play(FadeIn(n1))
        self.wait(2)
        l1 = Circle(0.2, color=WHITE, stroke_width=3).move_to(a1.c2p(*X[vecino_crudo]))
        d_crudo = np.linalg.norm(X - nuevo, axis=1)
        n2 = nota(f"El vecino es un puño, a {d_crudo[14:].min():.1f}; el pellizco más cerca está a {d_crudo[:14].min():.1f}: manda el giro.")
        assert y[vecino_crudo] == 1 and y[vecino_z] == 0
        self.play(Create(l1), FadeOut(n1), FadeIn(n2))
        self.wait(2.5)
        f = MathTex(r"z = \frac{x - \text{promedio}}{\text{desviaci\'on est\'andar}}", font_size=34).move_to(UP * 2.2 + RIGHT * 3.8)
        a2 = ejes([-3, 3, 1], [-2.4, 2.4, 1], ancho=7.2, alto=4.6).move_to(DOWN * 0.15 + RIGHT * 0.3)
        x2 = texto("giro, estandarizado", 20).next_to(a2, DOWN, buff=0.08)
        y2 = texto("golpe,\nestandarizado", 20).next_to(a2, LEFT, buff=0.15)
        self.play(FadeOut(l1, n2), FadeOut(nombres), FadeIn(f))
        self.play(ReplacementTransform(a1, a2), ReplacementTransform(x1, x2), ReplacementTransform(y1, y2),
                  *[p.animate.move_to(a2.c2p(*z)) for p, z in zip(puntos, Z)], nd.animate.move_to(a2.c2p(*zn)), run_time=2.5)
        l2 = Circle(0.2, color=WHITE, stroke_width=3).move_to(a2.c2p(*Z[vecino_z]))
        n3 = nota(f"Ahora el vecino es un {'puño' if y[vecino_z] else 'pellizco'}: los dos rasgos pesan parecido.")
        self.play(Create(l2), FadeIn(n3))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class MinimosCuadrados(Scene):
    """La recta que hace más chica la suma de los cuadrados de los errores."""

    def construct(self):
        rng = np.random.default_rng(3)
        x = np.sort(rng.uniform(-18, 18, 12))
        v = 5.3 * x + rng.normal(0, 16, 12) + 8
        e, coef = r2(v[:, None], x[:, None])
        pend, corte = coef[0, 0], coef[1, 0]
        titulo = texto("Mínimos cuadrados: la recta de menor suma de cuadrados", 30).to_edge(UP)
        ax = ejes([-20, 20, 10], [-140, 140, 70], ancho=6.0, alto=4.8).move_to(LEFT * 3.2 + DOWN * 0.45)
        lx = texto("giro de la muñeca (°/s)", 18).next_to(ax, DOWN, buff=0.06)
        ly = texto("dedo (mm/s)", 18).next_to(ax.y_axis, UP, buff=0.04)
        puntos = VGroup(*[Dot(ax.c2p(a, b), radius=0.07, color=DATO) for a, b in zip(x, v)])
        suma = lambda m: float(((v - m * x - corte) ** 2).sum())
        ms = np.linspace(0, 11, 111)
        a2 = ejes([0, 11, 2], [0, 1.1 * suma(11) / 1000, 50], ancho=4.6, alto=3.0).move_to(RIGHT * 4.0 + DOWN * 0.8)
        l2 = texto("suma de cuadrados (miles)", 18).next_to(a2, UP, buff=0.1)
        l3 = texto("pendiente (mm por grado)", 18).next_to(a2, DOWN, buff=0.06)
        self.play(Write(titulo), Create(ax), FadeIn(lx, ly), FadeIn(puntos), Create(a2), FadeIn(l2, l3))
        q = ValueTracker(1.0)

        def recta_():
            m = q.get_value()
            x0, x1 = max(-20, (-140 - corte) / m), min(20, (140 - corte) / m)      # hasta donde llegan los ejes
            return Line(ax.c2p(x0, m * x0 + corte), ax.c2p(x1, m * x1 + corte), color=MODELO, stroke_width=4)

        recta = always_redraw(recta_)

        def cuadrados():
            g = VGroup()
            for a, b in zip(x, v):
                p0, p1 = ax.c2p(a, b), ax.c2p(a, q.get_value() * a + corte)
                lado = p1[1] - p0[1]
                g.add(Polygon(p0, p1, p1 + RIGHT * abs(lado), p0 + RIGHT * abs(lado), stroke_width=1, stroke_color=ERROR, fill_color=ERROR, fill_opacity=0.3))
            return g

        cu = always_redraw(cuadrados)
        par = curva(en_ejes(a2, ms, [suma(m) / 1000 for m in ms]), GRIS, 3)
        punto = always_redraw(lambda: Dot(a2.c2p(q.get_value(), suma(q.get_value()) / 1000), radius=0.09, color=ERROR))
        valor = always_redraw(lambda: texto(f"pendiente {q.get_value():.1f} · suma {suma(q.get_value()):,.0f}".replace(",", " "), 22).move_to(RIGHT * 4.0 + UP * 1.5))
        self.add(cu, recta)
        self.play(Create(par), FadeIn(punto, valor))
        self.play(q.animate.set_value(10), run_time=3.5, rate_func=linear)
        self.play(q.animate.set_value(pend), run_time=3.5)
        self.wait(1)
        f = MathTex(r"\min_W \lVert XW - V \rVert^2", font_size=40).move_to(RIGHT * 4.0 + UP * 2.45)
        self.play(Write(f))
        n = nota(f"Fondo del valle: {pend:.2f} mm por grado (los datos se inventaron con 5.3).")
        self.play(FadeIn(n))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class RCuadrado(Scene):
    """R²: lo que el modelo explica de la variación total."""

    def construct(self):
        titulo = texto("R²: qué fracción de la variación explica el modelo", 32).to_edge(UP)
        ax = ejes([-20, 20, 10], [-200, 200, 100], ancho=6.2, alto=5.0).move_to(LEFT * 3.1 + DOWN * 0.35)
        lx = texto("giro de la muñeca (°/s)", 18).next_to(ax, DOWN, buff=0.06)
        self.play(Write(titulo), Create(ax), FadeIn(lx))
        rng = np.random.default_rng(9)
        x = np.sort(rng.uniform(-18, 18, 14))
        ruido = rng.normal(0, 1, 14)
        juegos = [("poco ruido", 5.3 * x + 8 * ruido), ("mucho ruido", 5.3 * x + 50 * ruido), ("sin relación", 42 * ruido)]
        base = np.array([1.9, 0.0, 0])
        ancho = 3.9
        tt = texto("variación total", 22).move_to(base + UP * 2.1 + RIGHT * 1.9)
        rr = texto("lo que queda sin explicar", 22, color=ERROR).move_to(base + UP * 0.8 + RIGHT * 1.9)
        f = MathTex(r"R^2 = 1 - \frac{\sum (v - \hat v)^2}{\sum (v - \bar v)^2}", font_size=36).move_to(base + DOWN * 1.1 + RIGHT * 1.9)
        self.play(FadeIn(tt, rr), Write(f))
        previo = VGroup()
        for k, (nombre, v) in enumerate(juegos):
            val, coef = r2(v[:, None], x[:, None])
            pred = coef[0, 0] * x + coef[1, 0]
            m = v.mean()
            puntos = VGroup(*[Dot(ax.c2p(a, b), radius=0.07, color=DATO) for a, b in zip(x, v)])
            media = DashedLine(ax.c2p(-20, m), ax.c2p(20, m), color=GRIS)
            alos = VGroup(*[Line(ax.c2p(a, b), ax.c2p(a, m), color=GRIS, stroke_width=3) for a, b in zip(x, v)])
            recta = Line(ax.c2p(-20, coef[0, 0] * -20 + coef[1, 0]), ax.c2p(20, coef[0, 0] * 20 + coef[1, 0]), color=MODELO, stroke_width=4)
            resto = VGroup(*[Line(ax.c2p(a, b), ax.c2p(a, c), color=ERROR, stroke_width=3) for a, b, c in zip(x, v, pred)])
            tot, res = ((v - m) ** 2).sum(), ((v - pred) ** 2).sum()
            b1 = barra(base + UP * 1.6, ancho, 0.42, GRIS)
            b2 = barra(base + UP * 0.3, ancho * res / tot, 0.42, ERROR)
            rot = texto(nombre, 24, color=DATO).next_to(ax, UP, buff=0.05)
            self.play(FadeOut(previo), FadeIn(puntos, rot), run_time=0.7)
            self.play(Create(media), Create(alos), FadeIn(b1), run_time=1.2)
            self.wait(0.7)
            self.play(Create(recta), ReplacementTransform(alos.copy(), resto), FadeIn(b2), run_time=1.5)
            cifra = texto(f"R² = {val:.2f}", 32, color=BIEN).move_to(base + DOWN * 2.6 + RIGHT * 1.9)
            self.play(FadeIn(cifra))
            self.wait(2.2)
            previo = VGroup(puntos, media, alos, recta, resto, b1, b2, rot, cifra)
        self.play(FadeIn(nota("1 es que explica todo; 0, que no le gana a decir siempre el promedio.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Sobreajuste(Scene):
    """Con números de sobra el modelo se aprende el ruido: el error visto baja y el nuevo sube."""

    def construct(self):
        rng = np.random.default_rng(12)
        real = lambda u: np.sin(2.4 * u) + 0.4 * u
        x = np.sort(rng.uniform(-1, 1, 12))
        v = real(x) + rng.normal(0, 0.18, 12)
        xn = rng.uniform(-1, 1, 400)
        vn = real(xn) + rng.normal(0, 0.18, 400)
        titulo = texto("Sobreajuste: memorizar no es aprender", 34).to_edge(UP)
        ax = ejes([-1, 1, 0.5], [-2, 2, 1], ancho=6.2, alto=4.6).move_to(LEFT * 3.2 + DOWN * 0.3)
        a2 = ejes([0, 11, 1], [0, 6, 1], ancho=4.8, alto=3.6, numeros=False).move_to(RIGHT * 4.0 + DOWN * 0.2)
        a2.x_axis.add_numbers(font_size=18)
        alto_log = lambda e: np.log10(max(e, 1e-3)) + 3         # el eje va en potencias de 10, de 0.001 a 1000
        for k, nm in enumerate(("0.001", "0.01", "0.1", "1", "10", "100", "1000")):
            a2.add(texto(nm, 16).next_to(a2.c2p(0, k), LEFT, buff=0.1))
        lx = texto("grado del polinomio", 18).next_to(a2, DOWN, buff=0.3)
        ly = texto("error rms", 18).next_to(a2.y_axis, UP, buff=0.18)
        puntos = VGroup(*[Dot(ax.c2p(a, b), radius=0.08, color=DATO) for a, b in zip(x, v)])
        self.play(Write(titulo), Create(ax), Create(a2), FadeIn(lx, ly), FadeIn(puntos))
        ley = VGroup(texto("con los datos vistos", 20, color=BIEN), texto("con datos nuevos", 20, color=ERROR)).arrange(RIGHT, buff=0.4).move_to(RIGHT * 4.0 + UP * 2.55)
        self.play(FadeIn(ley))
        ajuste, ev, en = VMobject(), [], []
        rx = np.linspace(-1, 1, 3000)
        g1, g2 = VGroup(), VGroup()
        self.add(g1, g2)
        rot = None
        for d in range(1, 12):
            p = np.polynomial.Chebyshev.fit(x, v, d, domain=[-1, 1])
            ev.append(np.sqrt(np.mean((p(x) - v) ** 2)))
            en.append(np.sqrt(np.mean((p(xn) - vn) ** 2)))
            nuevo_aj = trozos(ax, rx, p(rx), MODELO, 4)
            r_ = texto(f"grado {d}", 24).next_to(ax, UP, buff=0.05)
            g1.add(Dot(a2.c2p(d, alto_log(ev[-1])), radius=0.07, color=BIEN))
            g2.add(Dot(a2.c2p(d, alto_log(en[-1])), radius=0.07, color=ERROR))
            self.remove(ajuste)
            if rot:
                self.remove(rot)
            ajuste, rot = nuevo_aj, r_
            self.add(ajuste, rot)
            self.wait(1.0 if d in (1, 3, 5, 11) else 0.6)
        mejor = int(np.argmin(en)) + 1
        self.play(FadeIn(nota(f"Grado 11 pasa por los 12 puntos: error visto casi 0. Con datos nuevos, el mejor fue {mejor}.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class PruebaJusta(Scene):
    """El mismo modelo, medido de cuatro maneras."""

    def construct(self):
        e = D.todo()
        lam = e["principal"]["lams"][0]
        j = e["justa"][lam]
        titulo = texto("Prueba justa: lo que se mide es lo que no se vio", 32).to_edge(UP)
        filas, cols = 6, 26
        nombres = ["A", "A", "B", "B", "c", "d"]
        rng = np.random.default_rng(2)
        c0 = np.array([-6.1, 1.9, 0])
        s = 0.2
        celdas = VGroup(*[VGroup(*[Square(s, stroke_width=0.8, stroke_color=GREY_D, fill_color=GRIS, fill_opacity=0.35).move_to(c0 + RIGHT * c * (s + 0.02) + DOWN * f * (s + 0.3))
                                   for c in range(cols)]) for f in range(filas)])
        marcas = VGroup(*[texto(n, 18).next_to(celdas[f], LEFT, buff=0.12) for f, n in enumerate(nombres)])
        ley = texto("cada fila, un trazo; cada cuadro, un instante (10 ms)", 19).next_to(celdas, UP, buff=0.14).align_to(celdas, LEFT)
        ley2 = VGroup(Square(0.18, fill_color=GRIS, fill_opacity=0.6, stroke_width=0), texto("entrena", 19), Square(0.18, fill_color=RECO, fill_opacity=1, stroke_width=0), texto("mide", 19))\
            .arrange(RIGHT, buff=0.12).next_to(celdas, DOWN, buff=0.15).align_to(celdas, LEFT)
        self.play(Write(titulo), FadeIn(celdas, marcas, ley, ley2))
        modos = ["mismos datos", "instantes al azar", "grupos de trazos", "letras nunca vistas"]
        rotulos = {"mismos datos": "los mismos datos", "instantes al azar": "instantes al azar", "grupos de trazos": "grupos de trazos", "letras nunca vistas": "letras nunca vistas"}
        comentarios = ["Medir con lo que ya vio no dice nada.",
                       "El instante de al lado se entrenó: casi la misma ventana. Se ve mejor de lo que es.",
                       "Trazos enteros afuera, pero sus letras hermanas se quedan adentro.",
                       "El examen de verdad: un abecedario entero afuera."]
        izq = np.array([0.1, 1.75, 0])
        self.add(*[])
        ancho = 3.6
        previo = None
        barras = VGroup()
        for k, m in enumerate(modos):
            anim = []
            for f in range(filas):
                for c in range(cols):
                    if m == "mismos datos":
                        mide = True
                    elif m == "instantes al azar":
                        mide = rng.random() < 0.2
                    elif m == "grupos de trazos":
                        mide = f in (1, 4)
                    else:
                        mide = f >= 4
                    celdas[f][c].set_fill(RECO if mide else GRIS, 1 if mide else 0.35)
            y = izq + DOWN * 0.95 * k
            nom = texto(rotulos[m], 22).move_to(y + UP * 0.25, aligned_edge=LEFT)
            b = barra(y + DOWN * 0.1, ancho * max(j[m], 0), 0.26, RECO)
            cifra = texto(f"{j[m]:.2f}", 22).next_to(b, RIGHT, buff=0.12)
            n = nota(comentarios[k])
            self.play(FadeIn(nom), GrowFromEdge(b, LEFT), FadeIn(cifra), FadeIn(n) if previo is None else ReplacementTransform(previo, n), run_time=1)
            previo = n
            self.wait(2.4)
        tit = texto(f"R² de la velocidad (ridge, λ = {lam:g}), datos inventados", 19).next_to(ley2, DOWN, buff=0.3).align_to(ley2, LEFT)
        self.play(FadeIn(tit))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Retardos(Scene):
    """Trece miradas alrededor de cada instante: ±240 ms, cada 40 ms."""

    def construct(self):
        e = D.todo()
        ses, tr = e["sesion"], e["trazos"]
        i = indices(ses["letras"], "S")[0]
        t0, t1 = tr[i][0, 0] / 1000, tr[i][-1, 0] / 1000
        sel = (ses["t"] >= t0 - 0.35) & (ses["t"] <= t1 + 0.35)
        t = ses["t"][sel] - t0
        H = ses["H"][sel, 0]
        V = ses["V"][sel, 0]
        titulo = texto("Rasgos con retardos: el antes y el después", 34).to_edge(UP)
        dur = t1 - t0
        a1 = ejes([-0.4, dur + 0.4, 0.4], [-260, 260, 130], ancho=11.4, alto=2.6).next_to(titulo, DOWN, buff=0.28).shift(RIGHT * 0.5)
        l1 = VGroup(texto("dedo", 20, color=REAL), texto("muñeca", 20, color=RECO), texto("(mm/s)", 18)).arrange(DOWN, buff=0.08).next_to(a1, LEFT, buff=0.15)
        self.play(Write(titulo), Create(a1), FadeIn(l1))
        self.play(Create(curva(en_ejes(a1, t[::8], V[::8]), REAL, 2.5)), Create(curva(en_ejes(a1, t[::8], H[::8]), RECO, 2.5)), run_time=1.5)
        q = ValueTracker(0.25)
        lags = LAGS / 1000

        def mirada():
            c = q.get_value()
            g = VGroup(Line(a1.c2p(c, -260), a1.c2p(c, 260), color=WHITE, stroke_width=2))
            g.add(Rectangle(width=a1.c2p(c + 0.24, 0)[0] - a1.c2p(c - 0.24, 0)[0], height=a1.y_length, stroke_width=0, fill_color=WHITE, fill_opacity=0.08).move_to(a1.c2p(c, 0)))
            for l in lags:
                g.add(Dot(a1.c2p(c + l, np.interp(c + l, t, H)), radius=0.06, color=DATO))
            return g

        m = always_redraw(mirada)
        self.add(m)
        n1 = nota(f"Para cada instante, {len(LAGS)} miradas: de {LAGS[0]} a +{LAGS[-1]} ms, cada {LAGS[1] - LAGS[0]} ms, con interpolación.".replace("-", "−"))
        self.play(FadeIn(n1))
        self.play(q.animate.set_value(dur - 0.25), run_time=5, rate_func=linear)
        f = MathTex(rf"{len(LAGS)} \times (3 + 3 + 3) + 3 = {len(LAGS) * 9 + 3}", font_size=34).move_to(LEFT * 3.4 + DOWN * 1.2)
        g = texto("yaw-pitch-roll, giro crudo y aceleración\nen cada mirada, más la postura", 20).next_to(f, DOWN, buff=0.15)
        self.play(Write(f), FadeIn(g))
        # el resultado por ventana
        v = e["ventanas"]
        a2 = ejes([0, 5, 1], [0, 1, 0.25], ancho=4.8, alto=2.1, numeros=False).move_to(RIGHT * 3.6 + DOWN * 1.65)
        a2.y_axis.add_numbers(font_size=16, x_values=[0, 0.5, 1])
        barras, ks = VGroup(), list(v)
        for k, ms in enumerate(ks):
            med = D.mediana(v[ms]["parecidos"])
            b = Rectangle(width=0.6, height=a2.c2p(0, med)[1] - a2.c2p(0, 0)[1], stroke_width=0, fill_color=RECO, fill_opacity=0.9)\
                .move_to(a2.c2p(k + 0.5, 0), aligned_edge=DOWN)
            barras.add(VGroup(b, texto(f"{med:.2f}", 16).next_to(b, UP, buff=0.04), texto(f"±{ms}", 15).next_to(a2.c2p(k + 0.5, 0), DOWN, buff=0.1)))
        tt = texto("parecido mediano según la ventana (ms)", 18).next_to(a2, UP, buff=0.3)
        self.play(FadeOut(n1), Create(a2), FadeIn(tt), LaggedStart(*[FadeIn(b) for b in barras], lag_ratio=0.2), run_time=2)
        self.play(FadeIn(nota("Aquí la muñeca va atrasada: sin mirar después del instante, el modelo llega tarde.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
def dos_rasgos(semilla=2, n=60, parecidos=0.08, ruido=0.7):
    """dos rasgos casi iguales: mínimos cuadrados los pone a pelear y ridge los calma"""
    rng = np.random.default_rng(semilla)
    a = rng.normal(size=n)
    X = np.column_stack([a + parecidos * rng.normal(size=n), a + parecidos * rng.normal(size=n)])
    return X, (X.sum(1) * 0.5 + 3 + ruido * rng.normal(size=n))[:, None]


class RidgeCastigo(Scene):
    """Ridge: el error más λ veces el tamaño de los coeficientes; W se va al origen por un camino."""

    def construct(self):
        X, Y = dos_rasgos()
        lams = 10 ** np.linspace(-3, 4.5, 121)
        W = np.array([Ridge(l).fit(X, Y).W[:, 0] for l in lams])
        Z = (X - X.mean(0)) / (X.std(0) + 1e-9)
        Q = Z.T @ Z
        titulo = texto("Ridge: un castigo a los coeficientes grandes", 34).to_edge(UP)
        lim = 2.4
        ax = ejes([-lim + 1, lim + 1, 1], [-lim + 1, lim + 1, 1], ancho=5.6, alto=5.6).move_to(LEFT * 3.4 + DOWN * 0.45)
        l1 = texto("w1", 22).next_to(ax.x_axis, RIGHT, buff=0.1)
        l2 = texto("w2", 22).next_to(ax.y_axis, UP, buff=0.05)
        cont = elipses(Q, W[0, :2], [3, 15, 45, 100], ax)
        self.play(Write(titulo), Create(ax), FadeIn(l1, l2), Create(cont), run_time=2)
        f = MathTex(r"(X^{\mathsf T}X + \lambda I)\,W = X^{\mathsf T}V", font_size=38).move_to(RIGHT * 3.6 + UP * 2.2)
        self.play(Write(f))
        ols = Dot(ax.c2p(*W[0, :2]), radius=0.09, color=ERROR)
        tx = texto("sin castigo: mínimos cuadrados", 20, color=ERROR).move_to(RIGHT * 3.6 + UP * 1.3)
        self.play(FadeIn(ols, tx))
        n1 = nota(f"Dos rasgos casi iguales: un valle largo. Su fondo está en ({W[0, 0]:.2f}, {W[0, 1]:.2f}).")
        self.play(FadeIn(n1))
        self.wait(2)
        q = ValueTracker(0)
        idx = lambda: min(len(lams) - 1, int(q.get_value()))
        camino = always_redraw(lambda: curva(en_ejes(ax, W[:idx() + 1, 0], W[:idx() + 1, 1]), MODELO, 4) if idx() > 1 else VMobject())
        punto = always_redraw(lambda: Dot(ax.c2p(*W[idx(), :2]), radius=0.09, color=MODELO))

        def circulo():
            r_ = np.linalg.norm(W[idx(), :2])
            return Circle(radius=r_ * (ax.c2p(1, 0)[0] - ax.c2p(0, 0)[0]), color=GREEN, stroke_width=2).move_to(ax.c2p(0, 0))

        cir = always_redraw(circulo)
        val = VGroup()
        self.play(FadeOut(n1))
        self.add(cir, camino, punto, val)
        for k in range(0, len(lams), 3):                       # a saltos: un Text por cuadro tarda mucho
            val.become(VGroup(texto(f"λ = {lams[k]:.3g}", 26), texto(f"w1 = {W[k, 0]:+.2f}", 24, color=MODELO),
                              texto(f"w2 = {W[k, 1]:+.2f}", 24, color=MODELO), texto(f"término constante = {W[k, 2]:.2f}", 24))
                       .arrange(DOWN, aligned_edge=LEFT, buff=0.14).move_to(RIGHT * 3.6 + DOWN * 0.4))
            self.play(q.animate.set_value(k), run_time=0.2, rate_func=linear)
        self.play(FadeIn(nota(f"λ grande: W va a 0 y queda el promedio ({float(Y.mean()):.2f}), que no se castiga.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ControlLambda(Scene):
    """El control λ, con letras nunca vistas: de copiar el ruido a una raya quieta."""

    def construct(self):
        e = D.todo()
        L = e["lambda"]
        filas = L["filas"]
        letras = e["principal"]["letras"]
        titulo = texto("El control λ: de copiar el ruido a una raya quieta", 32).to_edge(UP)
        nombres = ["G", "M", "S", "W"]
        centros = [np.array([-5.3 + 3.55 * k, 1.25, 0]) for k in range(4)]
        reales = VGroup(*[letra(filas[0]["pares"], indices(letras, n), c, alto=1.9)[0] for n, c in zip(nombres, centros)])
        lg = [np.log10(f["lam"]) for f in filas]
        ax = ejes([-3, 9, 1], [-1, 1, 0.5], ancho=7.6, alto=2.0, numeros=False).move_to(DOWN * 2.0 + RIGHT * 1.6)
        ax.y_axis.add_numbers(font_size=16, x_values=[-1, -0.5, 0, 0.5, 1])
        for k in (-3, 0, 3, 6, 9):
            ax.add(texto(f"10^{k}".replace("-", "−"), 15).next_to(ax.c2p(k, -1), DOWN, buff=0.1))
        lr = VGroup(texto("R² con lo visto", 18, color=BIEN), texto("R² con letras nunca vistas", 18, color=RECO), texto("parecido mediano", 18, color=DATO))\
            .arrange(DOWN, aligned_edge=LEFT, buff=0.1).next_to(ax, LEFT, buff=0.2).shift(UP * 0.1)
        self.play(Write(titulo), Create(ax), FadeIn(lr), Create(reales), run_time=2)
        c1 = trozos(ax, np.array(lg), np.array([f["r2_entreno"] for f in filas]), BIEN, 3, y_rango=(-1, 1.001))
        c2 = trozos(ax, np.array(lg), np.array([f["r2_prueba"] for f in filas]), RECO, 3, y_rango=(-1, 1.001))
        c3 = trozos(ax, np.array(lg), np.array([f["parecido"] for f in filas]), DATO, 3, y_rango=(-1, 1.001))
        self.play(Create(c1), Create(c2), Create(c3), run_time=1.5)
        recos, marca, rot = VGroup(), Line(ax.c2p(-3, -1), ax.c2p(-3, 1), color=WHITE, stroke_width=2), VMobject()

        def dentro_de(g, c):
            """lo que se sale de la casilla de la letra no se dibuja: con λ chico el garabato es enorme"""
            out = VGroup()
            for m in g:
                p = np.array(m.get_anchors())
                ok = (np.abs(p[:, 0] - c[0]) <= 1.7) & (np.abs(p[:, 1] - c[1]) <= 1.35)
                ini = None
                for i, d in enumerate(list(ok) + [False]):
                    if d and ini is None:
                        ini = i
                    if not d and ini is not None:
                        if i - ini >= 2:
                            out.add(curva(p[ini:i], RECO, 3))
                        ini = None
            return out

        self.add(recos, marca)
        for f in filas:
            recos.become(VGroup(*[dentro_de(letra(f["pares"], indices(letras, n), c, alto=1.9)[1], c) for n, c in zip(nombres, centros)]))
            l = np.log10(f["lam"])
            marca.become(Line(ax.c2p(l, -1), ax.c2p(l, 1), color=WHITE, stroke_width=2))
            nuevo = texto(f"λ = {f['lam']:.3g}", 24).move_to(DOWN * 0.45 + RIGHT * 4.9)
            self.remove(rot)
            rot = nuevo
            self.add(rot)
            self.wait(0.42)
        mejor = max(filas, key=lambda f: f["r2_prueba"])
        self.wait(1)
        self.play(FadeIn(nota(f"Entrenando con {L['letras_entreno']} letras. El mejor λ para letras nuevas ronda {mejor['lam']:.0f}: ni ruido ni raya.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class PredecirVelocidad(Scene):
    """Lo que el reloj siente depende de cómo se mueve el dedo, no de dónde está: aprender velocidad e integrar."""

    def construct(self):
        e = D.todo()
        par = e["principal"]["pares"]["ridge"]
        letras = e["principal"]["letras"]
        i = indices(letras, "S")[0]
        real, reco = par[i]
        real = real - real[0]
        n = len(real)
        titulo = texto("Aprender cómo se mueve, no dónde está", 34).to_edge(UP)
        pad = Rectangle(width=6.0, height=3.8, stroke_color=GRIS, stroke_width=2).move_to(LEFT * 3.4 + UP * 0.6)
        lp = texto("el trackpad", 19, color=GRIS).next_to(pad, UP, buff=0.08)
        k = 1.4 / np.ptp(real[:, 1])
        c1, c2 = pad.get_center() + LEFT * 1.6 + UP * 0.6, pad.get_center() + RIGHT * 1.4 + DOWN * 0.6
        conv = lambda p, c: c + np.column_stack([p[:, 0] * k, -p[:, 1] * k, np.zeros(len(p))]) - np.array([k * (p[:, 0].max() + p[:, 0].min()) / 2, -k * (p[:, 1].max() + p[:, 1].min()) / 2, 0])
        s1, s2 = conv(real, c1), conv(real, c2)
        self.play(Write(titulo), Create(pad), FadeIn(lp))
        q = ValueTracker(2)
        d = lambda: int(q.get_value())
        t1 = always_redraw(lambda: curva(s1[:d():2], REAL, 4) if d() > 5 else VMobject())
        t2 = always_redraw(lambda: curva(s2[:d():2], REAL, 4) if d() > 5 else VMobject())

        def flecha(s):
            a = s[min(d(), n - 2)]
            b = s[min(d() + 7, n - 1)]
            return Arrow(a, a + (b - a) * 4, buff=0, color=DATO, stroke_width=4, max_tip_length_to_length_ratio=0.3)

        f1, f2 = always_redraw(lambda: flecha(s1)), always_redraw(lambda: flecha(s2))
        self.add(t1, t2, f1, f2)
        der = VGroup(texto("Dos sitios del trackpad,", 24), texto("el mismo movimiento:", 24)).arrange(DOWN, aligned_edge=LEFT).move_to(RIGHT * 3.5 + UP * 2.0)
        der2 = VGroup(texto("la posición es distinta", 24, color=ERROR), texto("la velocidad es la misma", 24, color=DATO), texto("el reloj siente lo mismo", 24)).arrange(DOWN, aligned_edge=LEFT, buff=0.14).next_to(der, DOWN, buff=0.3).align_to(der, LEFT)
        self.play(FadeIn(der))
        self.play(q.animate.set_value(n - 1), FadeIn(der2, lag_ratio=0.5), run_time=4.5, rate_func=linear)
        self.remove(f1, f2)
        self.wait(1.5)
        # integrar la predicción
        self.play(FadeOut(pad, lp, der, der2, t1, t2))
        self.remove(t1, t2)
        ax = ejes([0, (n - 1) / 100, 0.5], [-260, 260, 130], ancho=6.3, alto=2.6).move_to(LEFT * 3.2 + UP * 0.8)
        vr = np.gradient(real, 0.01, axis=0)
        vp = np.gradient(reco, 0.01, axis=0)
        tt = np.arange(n) / 100
        lv = VGroup(texto("velocidad en x, real", 19, color=REAL), texto("predicha", 19, color=RECO)).arrange(RIGHT, buff=0.4).next_to(ax, UP, buff=0.1)
        self.play(Create(ax), FadeIn(lv), Create(curva(en_ejes(ax, tt[::2], vr[::2, 0]), REAL, 2.5)), Create(curva(en_ejes(ax, tt[::2], vp[::2, 0]), RECO, 2.5)), run_time=1.5)
        c = np.array([3.6, 0.5, 0])
        k2 = 3.2 / np.ptp(real[:, 1])
        centro = (real.max(0) + real.min(0)) / 2
        conv2 = lambda p: c + np.column_stack([(p[:, 0] - centro[0]) * k2, -(p[:, 1] - centro[1]) * k2, np.zeros(len(p))])
        P1, P2 = conv2(real), conv2(reco)
        self.play(Create(curva(P1[::2], REAL, 3)), run_time=1)
        q2 = ValueTracker(2)
        d2 = lambda: int(q2.get_value())
        tr = always_redraw(lambda: curva(P2[:d2():2], RECO, 4) if d2() > 5 else VMobject())
        cu = always_redraw(lambda: Line(ax.c2p(tt[d2() - 1], -260), ax.c2p(tt[d2() - 1], 260), color=WHITE, stroke_width=2))
        f = MathTex(r"\text{trazo}[k] = \sum_{j<k} \hat v[j]\,\Delta t", font_size=32).move_to(LEFT * 3.2 + DOWN * 1.35)
        self.add(tr, cu)
        self.play(Write(f))
        self.play(q2.animate.set_value(n), run_time=5, rate_func=linear)
        self.remove(cu)
        pos, vel = D.mediana(e["posicion"]), D.mediana(e["velocidad"])
        tabla = texto(f"Mismos rasgos, mismas letras nunca vistas: posición {pos:.2f} · velocidad integrada {vel:.2f}", 22).move_to(DOWN * 2.45)
        self.play(FadeIn(tabla))
        self.play(FadeIn(nota("Cada trazo arranca del punto que da el trackpad. Integrar acumula error: el final se va.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class DescensoPorGradiente(Scene):
    """Un paso chico hacia abajo, muchas veces. Y lo que pasa si el paso es grande."""

    def construct(self):
        rng = np.random.default_rng(8)
        n = 200
        a = rng.normal(size=n)
        Z = np.column_stack([a + 0.5 * rng.normal(size=n), a + 0.5 * rng.normal(size=n)])
        Z = (Z - Z.mean(0)) / Z.std(0)
        y = Z @ np.array([1.0, 0.4]) + 0.3 * rng.normal(size=n)
        y = y - y.mean()
        w_opt = np.linalg.solve(Z.T @ Z, Z.T @ y)
        Q = Z.T @ Z / n
        E = lambda w: float(((Z @ w - y) ** 2).mean())
        grad = lambda w: 2 * Z.T @ (Z @ w - y) / n
        L = 2 * np.linalg.eigvalsh(Q).max()
        titulo = texto("Descenso por el gradiente: un paso chico a la vez", 32).to_edge(UP)
        ax = ejes([-2, 3, 1], [-2, 3, 1], ancho=5.4, alto=5.4).move_to(LEFT * 3.5 + DOWN * 0.45)
        cont = elipses(Q, w_opt, [0.05, 0.2, 0.5, 1, 1.8, 2.8, 4, 5.5], ax)
        a2 = ejes([0, 30, 10], [0, 8, 2], ancho=4.8, alto=2.6, numeros=False).move_to(RIGHT * 3.9 + DOWN * 1.3)
        a2.x_axis.add_numbers(font_size=16)
        for k, nm in ((0, "0.000001"), (2, "0.0001"), (4, "0.01"), (6, "1"), (8, "100")):     # el eje va en potencias de 10
            a2.add(texto(nm, 15).next_to(a2.c2p(0, k), LEFT, buff=0.1))
        l2 = texto("error que falta, por paso", 19).next_to(a2, UP, buff=0.1)
        f = MathTex(r"W \leftarrow W - \alpha\,\nabla E", font_size=38).move_to(RIGHT * 3.9 + UP * 2.2)
        f2 = MathTex(r"\nabla E = \tfrac{2}{n}\,X^{\mathsf T}(XW - V)", font_size=30).next_to(f, DOWN, buff=0.15)
        self.play(Write(titulo), Create(ax), Create(cont), Create(a2), FadeIn(l2), Write(f), Write(f2), run_time=2)
        minimo = Dot(ax.c2p(*w_opt), radius=0.08, color=BIEN)
        self.add(minimo)
        rot, previo = VMobject(), VGroup()
        pasos = [(0.05, MODELO), (0.45, DATO), (1.05 * 2 / L, ERROR)]
        for alfa, color in pasos:
            w = np.array([-1.6, 2.6])
            ruta = [w.copy()]
            for _ in range(30):
                w = w - alfa * grad(w)
                ruta.append(w.copy())
            ruta = np.array(ruta)
            falta = [max(E(p) - E(w_opt), 1e-9) for p in ruta]
            nuevo = texto(f"α = {alfa:.2f}", 26, color=color).move_to(RIGHT * 3.9 + UP * 0.65)
            self.play(FadeOut(previo), FadeOut(rot), FadeIn(nuevo), run_time=0.5)
            rot = nuevo
            ruta_g, err_g = VGroup(), VGroup()
            self.add(ruta_g, err_g)
            for k in range(1, 31):
                ok = np.all(np.abs(ruta[k] - 0.5) <= 2.5)
                ok0 = np.all(np.abs(ruta[k - 1] - 0.5) <= 2.5)
                if ok and ok0:
                    ruta_g.add(Line(ax.c2p(*ruta[k - 1]), ax.c2p(*ruta[k]), color=color, stroke_width=3))
                    ruta_g.add(Dot(ax.c2p(*ruta[k]), radius=0.045, color=color))
                ly = np.log10(falta[k])
                if -6 <= ly <= 2:
                    err_g.add(Dot(a2.c2p(k, ly + 6), radius=0.045, color=color))
                self.wait(0.13)
            previo = VGroup(ruta_g, err_g)
            self.wait(1)
        self.play(FadeIn(nota(f"Con α mayor que 2 / curvatura máxima = {2 / L:.2f}, cada paso se pasa y el error crece.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class MLPConHistoria(MLP):
    """MLP.fit copiado línea por línea, guardando el error de cada época. curva_red() comprueba que da lo mismo."""

    def fit(self, X, Y):
        self.historia = []
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
            Ht = np.tanh(Z[tr] @ P["W1"] + P["b1"]); entreno = ((Ht @ P["W2"] + P["b2"] - T[tr]) ** 2).mean()
            self.historia.append((ep, entreno, loss, {k: v.copy() for k, v in P.items()}))
            if loss < best - 1e-5:
                best, best_P, wait = loss, {k: v.copy() for k, v in P.items()}, 0
            else:
                wait += 1
                if wait > 25:
                    break
        self.P = best_P
        return self


def curva_red():
    """rapidez de la muñeca → rapidez del dedo: la curva de datos_cap12.py, con ruido, y pocos datos"""
    rng = np.random.default_rng(21)
    v = rng.uniform(-220, 220, 84)
    h = D.parte_de_la_muneca(np.abs(v)) * v
    x = h + rng.normal(0, 4, len(v))
    y = v + rng.normal(0, 8, len(v))
    X, Y = x[:, None], np.column_stack([y, y])
    ajuste = dict(hidden=24, l2=1e-3, epochs=1500, lr=2e-2, seed=0)
    con, sin = MLPConHistoria(**ajuste).fit(X, Y), MLP(**ajuste).fit(X, Y)
    assert np.allclose(con.predict(X), sin.predict(X)), "la copia de MLP.fit se desvió del original"
    return x, y, X, Y, con


class RedNeuronal(Scene):
    """Una capa oculta: muchas curvas tanh sumadas; se entrena por el gradiente y se para cuando la validación se estanca."""

    def construct(self):
        x, y, X, Y, red = curva_red()
        ridge = Ridge(1.0).fit(X, Y)
        titulo = texto("Una red neuronal pequeña: una capa de curvas", 34).to_edge(UP)
        # diagrama
        ent = VGroup(*[Circle(0.13, color=DATO, fill_opacity=0.8).move_to([-6.3, 1.5 - 0.6 * k, 0]) for k in range(6)])
        ocu = VGroup(*[Circle(0.13, color=MODELO, fill_opacity=0.8).move_to([-4.8, 1.8 - 0.6 * k, 0]) for k in range(7)])
        sal = VGroup(*[Circle(0.13, color=RECO, fill_opacity=0.8).move_to([-3.3, 0.3 - 0.6 * k + 0.3, 0]) for k in range(2)])
        lineas = VGroup(*[Line(a.get_center(), b.get_center(), stroke_width=0.7, color=GREY_D) for a in ent for b in ocu],
                        *[Line(a.get_center(), b.get_center(), stroke_width=0.7, color=GREY_D) for a in ocu for b in sal])
        d = 120
        cuenta = d * 64 + 64 + 64 * 2 + 2
        e1 = texto("120\nrasgos", 17).next_to(ent, DOWN, buff=0.14)
        e2 = texto("64 tanh", 17).next_to(ocu, DOWN, buff=0.14)
        e3 = texto("velocidad\n(x, y)", 17).next_to(sal, DOWN, buff=0.14).shift(DOWN * 0.72)
        f = MathTex(r"\hat v = W_2 \tanh(W_1 x + b_1) + b_2", font_size=30).move_to(LEFT * 4.7 + UP * 2.55)
        self.play(Write(titulo), FadeIn(lineas, ent, ocu, sal, e1, e2, e3), Write(f), run_time=2)
        ax = ejes([-200, 200, 100], [-260, 260, 130], ancho=5.0, alto=2.7).move_to(RIGHT * 3.6 + UP * 1.15)
        lx = texto("rapidez de la muñeca (mm/s)", 17).next_to(ax, DOWN, buff=0.03)
        ly = texto("del dedo", 17).next_to(ax, UP, buff=0.04)
        dentro = np.abs(x) <= 200
        puntos = VGroup(*[Dot(ax.c2p(a, b), radius=0.04, color=DATO) for a, b in zip(x[dentro], y[dentro])])
        self.play(Create(ax), FadeIn(lx, ly), FadeIn(puntos))
        rx = np.linspace(-200, 200, 200)
        pr = ridge.predict(rx[:, None])[:, 0]
        cr = trozos(ax, rx, pr, GRIS, 3)
        lr_ = texto("recta (ridge)", 18, color=GRIS).move_to(ax.c2p(112, -205))
        self.play(Create(cr), FadeIn(lr_))
        hist = red.historia
        ult = len(hist) - 1
        mejor = int(np.argmin([h[2] for h in hist]))
        tope = float(np.ceil(max(hist[2][1], hist[2][2]) * 20) / 20)   # el eje empieza a contar desde la tercera época
        a2 = ejes([0, max(hist[-1][0] + 1, 10), max(10, 10 * round(len(hist) / 40))], [0, tope, tope / 2], ancho=5.0, alto=1.75).move_to(RIGHT * 3.6 + DOWN * 2.05)
        ta = VGroup(texto("error en entrenamiento", 17, color=BIEN), texto("en validación", 17, color=ERROR)).arrange(RIGHT, buff=0.3).next_to(a2, UP, buff=0.04)
        self.play(Create(a2), FadeIn(ta))
        ajuste, g1, g2 = VMobject(), VGroup(), VGroup()
        self.add(g1, g2)
        marcas = sorted(set(np.unique(np.round(np.linspace(0, ult, 44)).astype(int))) | {mejor})

        def predice(P):
            H = np.tanh(((rx[:, None] - red.mu) / red.sd) @ P["W1"] + P["b1"])
            return ((H @ P["W2"] + P["b2"]) * red.ys + red.ym)[:, 0]

        anterior = None
        for k in marcas:
            ep, en, va, P = hist[k]
            self.remove(ajuste)
            ajuste = trozos(ax, rx, predice(P), RECO, 3.5)
            self.add(ajuste)
            if anterior is not None:
                if max(anterior[1], anterior[2]) <= tope:
                    g1.add(Line(a2.c2p(anterior[0], anterior[1]), a2.c2p(ep, en), color=BIEN, stroke_width=3))
                    g2.add(Line(a2.c2p(anterior[0], anterior[2]), a2.c2p(ep, va), color=ERROR, stroke_width=3))
            anterior = (ep, en, va)
            self.wait(0.17)
        self.remove(ajuste)
        ajuste = trozos(ax, rx, predice(hist[mejor][3]), RECO, 3.5)
        self.add(ajuste)
        se = hist[mejor][0]
        mk = DashedLine(a2.c2p(se, 0), a2.c2p(se, tope), color=WHITE)
        self.play(Create(mk))
        self.play(FadeIn(nota(f"Se queda con la época {se}, la mejor en validación. La real tiene {cuenta} números; ridge, {121 * 2}.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class MasDatos(Scene):
    """¿Quién gana si hay más datos? El mismo examen, entrenando con 1, 3 y 10 veces más letras."""

    def construct(self):
        e = D.todo()
        filas = e["datos"]
        titulo = texto("¿Y con diez veces más datos?", 34).to_edge(UP)
        ax = ejes([0, 3, 1], [0.5, 1, 0.1], ancho=7.0, alto=4.4, numeros=False).move_to(LEFT * 1.6 + DOWN * 0.2)
        ax.y_axis.add_numbers(font_size=18, x_values=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        xs = [0.5, 1.5, 2.5]
        for x, f in zip(xs, filas):
            ax.add(texto(f"×{f['vueltas']}\n{f['instantes']} instantes", 17).next_to(ax.c2p(x, 0.5), DOWN, buff=0.1))
        ly = texto("parecido\nmediano", 18).next_to(ax, LEFT, buff=0.12)
        self.play(Write(titulo), Create(ax), FadeIn(ly))
        for nombre, color, etiqueta in (("ridge", MODELO, "ridge"), ("red", RECO, "red")):
            ys = [f[nombre] for f in filas]
            puntos = VGroup(*[Dot(ax.c2p(a, b), radius=0.09, color=color) for a, b in zip(xs, ys)])
            lin = curva(en_ejes(ax, xs, ys), color, 4)
            cifras = VGroup(*[texto(f"{b:.2f}", 19, color=color).next_to(ax.c2p(a, b), UP if nombre == "red" and ys[i] >= filas[i]["ridge"] or nombre == "ridge" and ys[i] > filas[i]["red"] else DOWN, buff=0.14) for i, (a, b) in enumerate(zip(xs, ys))])
            self.play(Create(lin), FadeIn(puntos), FadeIn(cifras), run_time=1.5)
            self.add(texto(etiqueta, 22, color=color).next_to(ax.c2p(xs[-1], ys[-1]), RIGHT, buff=0.2))
            self.wait(1)
        der = VGroup(texto("Ridge: 242 números,", 21), texto("una sola solución.", 21), texto("Red: 7874 números,", 21), texto("necesita ver más.", 21))\
            .arrange(DOWN, aligned_edge=LEFT, buff=0.1).move_to(RIGHT * 4.9 + UP * 0.6)
        self.play(FadeIn(der))
        self.play(FadeIn(nota("Datos inventados, con una curva puesta a propósito: no dice nada de tu mano.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ParecidoDeForma(Scene):
    """Comparar punto a punto castiga dónde está y qué tan grande es; el parecido de forma mira la forma."""

    def construct(self):
        e = D.todo()
        par = e["principal"]["pares"]["ridge"]
        letras = e["principal"]["letras"]
        a = par[indices(letras, "S")[0]][0]
        a = (a - a[0])[::3]
        z = par[indices(letras, "Z")[0]][0]
        z = (z - z[0])
        z = np.column_stack([np.interp(np.linspace(0, 1, len(a)), np.linspace(0, 1, len(z)), z[:, i]) for i in (0, 1)])
        giro = np.radians(30)
        R = np.array([[np.cos(giro), -np.sin(giro)], [np.sin(giro), np.cos(giro)]])
        c = a.mean(0)
        u = np.linspace(0, 1, len(a))
        casos = [("igual, en otro sitio", a + [14, 8]),
                 ("más chica (×0.6)", a * 0.6 + [20, 0]),
                 ("girada 30°", (a - c) @ R.T + c),
                 ("con deriva de 13 mm", a + np.outer(u, [12, -6])),
                 ("otra letra", z)]
        titulo = texto("¿Qué número dice si dos letras se parecen?", 34).to_edge(UP)
        centro = np.array([-3.6, -0.15, 0])
        k = 3.3 / np.ptp(a[:, 1])
        m0 = (a.max(0) + a.min(0)) / 2
        conv = lambda p: centro + np.column_stack([(p[:, 0] - m0[0] - 6) * k, -(p[:, 1] - m0[1]) * k, np.zeros(len(p))])
        real = curva(conv(a), REAL, 4)
        f = MathTex(r"\text{parecido} = \frac{a\cdot b}{|a|\,|b|}", font_size=38).move_to(RIGHT * 3.7 + UP * 2.15)
        f2 = texto("a y b: las dos formas, cada una\nmenos su promedio", 20).next_to(f, DOWN, buff=0.15)
        self.play(Write(titulo), Create(real), Write(f), FadeIn(f2))
        cab = VGroup(texto("distancia", 21).move_to(RIGHT * 4.75 + UP * 0.45), texto("parecido", 21).move_to(RIGHT * 6.1 + UP * 0.45))
        self.play(FadeIn(cab))
        reco, rayas = None, VGroup()
        filas = VGroup()
        for i, (nombre, b) in enumerate(casos):
            sim = shape_sim([a], [b])
            dist = float(np.sqrt(((a - b) ** 2).sum(1).mean()))
            nueva = curva(conv(b), RECO, 4)
            ry = VGroup(*[Line(conv(a[j:j + 1])[0], conv(b[j:j + 1])[0], color=GRIS, stroke_width=1) for j in range(0, len(a), max(1, len(a) // 14))])
            fila = VGroup(texto(nombre, 20).move_to(RIGHT * 1.0 + DOWN * 0.5 * i, aligned_edge=LEFT),
                          texto(f"{dist:.1f} mm", 20, color=ERROR).move_to(RIGHT * 4.75 + DOWN * 0.5 * i),
                          texto(f"{sim:.2f}", 20, color=BIEN).move_to(RIGHT * 6.1 + DOWN * 0.5 * i))
            if reco is None:
                self.play(Create(nueva), Create(ry), FadeIn(fila), run_time=1.2)
            else:
                self.play(ReplacementTransform(reco, nueva), ReplacementTransform(rayas, ry), FadeIn(fila), run_time=1.2)
            reco, rayas = nueva, ry
            filas.add(fila)
            self.wait(1.6)
        self.play(FadeIn(nota("Distancia: rms punto a punto. El parecido no ve sitio ni tamaño; un giro o una deriva, sí.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class CuantoCreo(Scene):
    """53 letras dan una mediana con su temblor: volver a sacar las letras al azar lo mide."""

    def construct(self):
        e = D.todo()
        a = np.array([v for _, v in e["ventanas"][240]["parecidos"]])
        b = np.array([v for _, v in e["ventanas"][160]["parecidos"]])
        d = D.remuestrear(a, b)
        lo, hi = np.percentile(d, [2.5, 97.5])
        dif = np.median(a) - np.median(b)
        titulo = texto("Con 53 letras, ¿cuánto creo en una diferencia?", 32).to_edge(UP)
        r = max(0.12, np.abs(d).max())
        a1 = ejes([0, 53, 10], [0, 1, 0.5], ancho=5.6, alto=2.0).move_to(LEFT * 3.5 + UP * 1.3)
        orden = np.argsort(-a)
        l1 = VGroup(texto("ventana ±240 ms", 18, color=MODELO), texto("±160 ms", 18, color=RECO)).arrange(RIGHT, buff=0.3).next_to(a1, UP, buff=0.06)
        d1 = VGroup(*[Dot(a1.c2p(i + 0.5, min(1, max(0, a[k]))), radius=0.04, color=MODELO) for i, k in enumerate(orden)])
        d2 = VGroup(*[Dot(a1.c2p(i + 0.5, min(1, max(0, b[k]))), radius=0.04, color=RECO) for i, k in enumerate(orden)])
        self.play(Write(titulo), Create(a1), FadeIn(l1), FadeIn(d1, d2, lag_ratio=0.01), run_time=2)
        txt = VGroup(texto(f"medianas: {np.median(a):.3f} y {np.median(b):.3f}", 23),
                     texto(f"diferencia: {dif:+.3f}".replace("-", "−"), 23, color=DATO),
                     texto(f"una letra sola varía ±{a.std():.2f}", 23)).arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to(RIGHT * 3.4 + UP * 1.3)
        self.play(FadeIn(txt, lag_ratio=0.4))
        self.wait(1.5)
        ancho = float(np.ceil(np.abs(d).max() * 20) / 20)      # que quepan todas las remuestras
        bordes = np.linspace(-ancho, ancho, 41)
        a2 = ejes([-ancho, ancho, 0.05], [0, 1, 1], ancho=11.0, alto=1.9, y_axis_config={"include_numbers": False}).move_to(DOWN * 1.5 + RIGHT * 0.1)
        a2.y_axis.set_opacity(0)
        l2 = texto("diferencia de medianas, sacando otra vez 53 letras al azar (con repetición)", 19).next_to(a2, UP, buff=0.04)
        self.play(Create(a2), FadeIn(l2))
        h, gr = None, VGroup()
        self.add(gr)
        for n in (30, 100, 300, 1000, 3000, 10000):
            c, _ = np.histogram(d[:n], bordes)
            c = c / max(1, c.max())
            nuevo = VGroup(*[Rectangle(width=a2.c2p(bordes[1], 0)[0] - a2.c2p(bordes[0], 0)[0], height=max(v * 1.8, 0.001), stroke_width=0.5, stroke_color=BLACK, fill_color=MODELO, fill_opacity=0.85)
                             .move_to(a2.c2p((bordes[i] + bordes[i + 1]) / 2, 0), aligned_edge=DOWN) for i, v in enumerate(c)])
            cuenta = texto(f"{n} veces", 20).move_to(a2.c2p(ancho * 0.8, 0.8))
            gr.become(VGroup(nuevo, cuenta))
            self.wait(0.6)
        cero = Line(a2.c2p(0, 0), a2.c2p(0, 1), color=WHITE, stroke_width=3)
        banda = Line(a2.c2p(lo, 0), a2.c2p(hi, 0), color=DATO, stroke_width=9)
        self.play(Create(cero), Create(banda))
        t = np.array(e["tardes"])
        puntos = VGroup(*[Dot(a2.c2p(v, 0.0) + DOWN * 0.52, radius=0.06, color=RECO) for v in t[:, 0] - t[:, 1] if abs(v) <= ancho])
        n1 = nota(f"El 95 % cae entre {lo:+.3f} y {hi:+.3f}, y el cero está adentro: no se distingue del ruido.".replace("-", "−"))
        self.play(FadeIn(n1))
        self.wait(2.5)
        self.play(FadeOut(n1), FadeIn(puntos, lag_ratio=0.2), FadeIn(nota("Cada punto: otra sesión inventada. Esa repetición es la que en la vida real falta.")), run_time=1.5)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class VecinosCercanos(Scene):
    """Un gesto nuevo pregunta a los k más cercanos, y votan más los más cerca."""

    def construct(self):
        X, y, clases, medidas = gestos()
        X2 = X[:, :2]
        nuevo = np.array([3.3, 72.0])
        pred = knn_loo(np.vstack([X2, nuevo]), y + ["?"])[-1]     # el voto del nuevo es la última fila
        A = np.vstack([X2, nuevo])
        mu, sd = A.mean(0), A.std(0) + 1e-9
        Z = (A - mu) / sd
        d = np.linalg.norm(Z[:-1] - Z[-1], axis=1)
        nn = np.argsort(d)[:3]
        votos = {}
        for j in nn:
            votos[y[j]] = votos.get(y[j], 0) + 1 / (1 + d[j])
        assert max(votos, key=votos.get) == pred
        titulo = texto("Vecinos más cercanos: los parecidos votan", 34).to_edge(UP)
        ax = ejes([-2, 3, 1], [-2, 4, 1], ancho=7.4, alto=4.9).move_to(LEFT * 2.5 + DOWN * 0.45)
        lx = texto("golpe máx, estandarizado", 18).next_to(ax, DOWN, buff=0.05)
        ly = texto("giro x máx, estandarizado", 18).next_to(ax.y_axis, UP, buff=0.05)
        color = {c: COLORES[i] for i, c in enumerate(clases)}
        visibles = [(p, c) for p, c in zip(Z[:-1], y) if -2 <= p[0] <= 3 and -2 <= p[1] <= 4]
        puntos = VGroup(*[Dot(ax.c2p(*p), radius=0.07, color=color[c]) for p, c in visibles])
        ley = VGroup(*[VGroup(Dot(radius=0.07, color=color[c]), texto(c, 20)).arrange(RIGHT, buff=0.12) for c in clases]).arrange(DOWN, aligned_edge=LEFT, buff=0.1).move_to(RIGHT * 4.7 + UP * 1.7)
        self.play(Write(titulo), Create(ax), FadeIn(lx, ly, ley), FadeIn(puntos, lag_ratio=0.01), run_time=2)
        estrella = Star(5, outer_radius=0.17, color=WHITE, fill_opacity=1).move_to(ax.c2p(*Z[-1]))
        self.play(FadeIn(estrella, scale=2))
        radio = d[nn[-1]] * (ax.c2p(1, 0)[0] - ax.c2p(0, 0)[0])
        escala_y = (ax.c2p(0, 1)[1] - ax.c2p(0, 0)[1]) / (ax.c2p(1, 0)[0] - ax.c2p(0, 0)[0])
        circ = Ellipse(width=2 * radio, height=2 * radio * escala_y, color=WHITE, stroke_width=2).move_to(ax.c2p(*Z[-1]))
        self.play(Create(circ))
        rayas = VGroup(*[Line(ax.c2p(*Z[-1]), ax.c2p(*Z[j]), color=color[y[j]], stroke_width=4) for j in nn])
        filas = VGroup(*[texto(f"{y[j]}: distancia {d[j]:.2f}, voto {1 / (1 + d[j]):.2f}", 20, color=color[y[j]]) for j in nn]).arrange(DOWN, aligned_edge=LEFT, buff=0.1).move_to(RIGHT * 4.45 + DOWN * 1.0)
        f = MathTex(r"\text{voto} = \frac{1}{1 + d}", font_size=32).next_to(filas, UP, buff=0.2)
        self.play(Create(rayas), Write(f), FadeIn(filas, lag_ratio=0.4), run_time=2)
        res = texto(f"gana: {pred}", 28).next_to(filas, DOWN, buff=0.22)
        self.play(FadeIn(res))
        self.wait(1.5)
        p = knn_loo(X2, y)
        acierto = np.mean([a == b for a, b in zip(y, p)])
        self.play(FadeIn(nota(f"k = 3. El modelo son los gestos guardados. Dejando uno fuera, con 2 rasgos: {acierto * 100:.0f} %.")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class MatrizDeConfusion(Scene):
    """Qué gesto se toma por cuál: dejando uno fuera, toma por toma."""

    def construct(self):
        X, y, clases, medidas = gestos()
        pred = knn_loo(X, y)
        cm = np.array(confusion(y, pred, clases))
        titulo = texto("Matriz de confusión: qué se confunde con qué", 34).to_edge(UP)
        n, s = len(clases), 0.82
        c0 = np.array([-3.4, 1.75, 0])
        pos = lambda i, j: c0 + RIGHT * s * j + DOWN * s * 0.86 * i
        celdas = VGroup(*[VGroup(*[Rectangle(width=s - 0.04, height=s * 0.86 - 0.04, stroke_width=0, fill_color=GREY_E, fill_opacity=1).move_to(pos(i, j)) for j in range(n)]) for i in range(n)])
        filas = VGroup(*[texto(c, 20).next_to(pos(i, 0), LEFT, buff=0.5) for i, c in enumerate(clases)])
        cols = VGroup(*[texto(c.replace(" dedos", "d"), 20).next_to(pos(0, j), UP, buff=0.32) for j, c in enumerate(clases)])
        ly = texto("lo que era", 20, color=GRIS).next_to(filas, LEFT, buff=0.25).rotate(PI / 2)
        lx = texto("lo que dijo el modelo", 20, color=GRIS).next_to(cols, UP, buff=0.08)
        self.play(Write(titulo), FadeIn(celdas, filas, cols, lx, ly))
        conteo = np.zeros((n, n), int)
        numeros = VGroup()
        self.add(numeros)
        idx = {c: i for i, c in enumerate(clases)}
        rng = np.random.default_rng(0)
        for k, m in enumerate(rng.permutation(len(y))):
            i, j = idx[y[m]], idx[pred[m]]
            conteo[i, j] += 1
            if k % 3 == 2 or k == len(y) - 1:
                for a in range(n):
                    for b in range(n):
                        v = conteo[a, b]
                        col = interpolate_color(ManimColor(GREY_E), ManimColor(GREEN if a == b else RED), min(1, v / 15 if a == b else v / 6))
                        celdas[a][b].set_fill(col, 1)
                numeros.become(VGroup(*[texto(str(conteo[a, b]), 22).move_to(pos(a, b)) for a in range(n) for b in range(n) if conteo[a, b]]))
                self.wait(0.16)
        assert (conteo == cm).all()
        acierto = np.trace(cm) / cm.sum()
        der = VGroup(texto(f"aciertos: {np.trace(cm)} de {cm.sum()}", 23), texto(f"{acierto * 100:.0f} % (al azar: {100 / n:.0f} %)", 23)).arrange(DOWN, aligned_edge=LEFT).move_to(RIGHT * 5.0 + UP * 0.9)
        self.play(FadeIn(der))
        a, b = np.unravel_index(np.argmax(cm - np.diag(np.diag(cm))), cm.shape)
        caja = Rectangle(width=s, height=s * 0.86, stroke_color=WHITE, stroke_width=4).move_to(pos(a, b))
        self.play(Create(caja))
        self.play(FadeIn(nota(f"Diagonal: aciertos. Lo más confundido: {clases[a]} tomado por {clases[b]} ({cm[a, b]} veces).")))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class FDeAnova(Scene):
    """Cuánto separa una medida: la variación entre gestos sobre la variación dentro de cada uno."""

    def construct(self):
        X, y, clases, medidas = gestos()
        F = fstat(X, y)
        titulo = texto("La F: ¿qué medidas sirven para distinguir?", 34).to_edge(UP)
        yy = np.array(y)
        rng = np.random.default_rng(1)
        paneles = []
        for k, (col, rango, xc) in enumerate(((0, [0, 7, 1], -3.5), (2, [0, 3, 1], 3.5))):
            ax = ejes([0, 6, 1], rango, ancho=5.8, alto=3.4, numeros=False).move_to(RIGHT * xc + UP * 0.45)
            ax.y_axis.add_numbers(font_size=16)
            eti = VGroup(*[texto(c.replace(" dedos", "d"), 16).next_to(ax.c2p(i + 0.5, rango[0]), DOWN, buff=0.08) for i, c in enumerate(clases)])
            nom = texto(medidas[col], 22).next_to(ax, UP, buff=0.08)
            puntos = VGroup(*[Dot(ax.c2p(clases.index(c) + 0.5 + rng.uniform(-0.25, 0.25), v), radius=0.045, color=COLORES[clases.index(c)]) for v, c in zip(X[:, col], y)])
            m = X[:, col].mean()
            total = DashedLine(ax.c2p(0, m), ax.c2p(6, m), color=WHITE)
            medias = VGroup(*[Line(ax.c2p(i + 0.12, X[yy == c, col].mean()), ax.c2p(i + 0.88, X[yy == c, col].mean()), color=WHITE, stroke_width=5) for i, c in enumerate(clases)])
            entre = VGroup(*[Line(ax.c2p(i + 0.5, m), ax.c2p(i + 0.5, X[yy == c, col].mean()), color=DATO, stroke_width=4) for i, c in enumerate(clases)])
            paneles.append((ax, eti, nom, puntos, total, medias, entre, col))
        self.play(Write(titulo), *[Create(p[0]) for p in paneles], *[FadeIn(p[1], p[2]) for p in paneles], run_time=1.5)
        self.play(*[FadeIn(p[3], lag_ratio=0.005) for p in paneles], run_time=1.5)
        self.play(*[Create(p[4]) for p in paneles], *[Create(p[5]) for p in paneles], run_time=1.2)
        self.play(*[Create(p[6]) for p in paneles], run_time=1.2)
        f = MathTex(r"F = \frac{\sum_g n_g(\bar x_g - \bar x)^2 / (G-1)}{\sum_g \sum_i (x_i - \bar x_g)^2 / (N-G)}", font_size=28).move_to(DOWN * 2.6)
        self.play(Write(f))
        cifras = VGroup(*[texto(f"F = {F[p[7]]:.1f}", 28, color=DATO).next_to(p[0], DOWN, buff=0.36) for p in paneles])
        self.play(FadeIn(cifras))
        orden = np.argsort(F)[::-1]
        lista = texto(" · ".join(f"{medidas[j].split(' (')[0]} {F[j]:.1f}" for j in orden), 22)
        self.play(FadeIn(lista.to_edge(DOWN, buff=0.15)))
        self.wait(3.5)


# ---------------------------------------------------------------------------------------------------------
def acierto_con_otra(g):
    """un modelo de una persona (k = 3, como en main() de analyze_dataset) probado con otra que tiene g veces su fuerza"""
    clases = ["2 dedos", "4 dedos", "puño", "brazo"]            # los que esta persona sí distingue
    X, y, _, medidas = gestos()
    B, yb, _, _ = gestos(semilla=9, escala=(g, g, 1, g))
    k = [i for i, c in enumerate(y) if c in clases]
    X, y, B, yb = X[k], [y[i] for i in k], B[k], [yb[i] for i in k]
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Za, Zb = (X - mu) / sd, (B - mu) / sd
    pred = []
    for z in Zb:
        d = np.linalg.norm(Za - z, axis=1)
        votos = {}
        for j in np.argsort(d)[:3]:
            votos[y[j]] = votos.get(y[j], 0) + 1 / (1 + d[j])
        pred.append(max(votos, key=votos.get))
    return X, y, B, yb, clases, medidas, float(np.mean([a == b for a, b in zip(yb, pred)]))


class OtraPersona(Scene):
    """Dejar uno fuera no sale de la sesión: otra mano cae en otro sitio, y cuánto se pierde hay que medirlo."""

    def construct(self):
        X, y, B, yb, clases, medidas, _ = acierto_con_otra(1.0)
        acierto_a = np.mean([a == b for a, b in zip(y, knn_loo(X, y))])
        titulo = texto("Si acierta con mis datos, ¿acierta con otra persona?", 32).to_edge(UP)
        ax = ejes([0, 7, 1], [0, 220, 50], ancho=7.0, alto=4.5).move_to(LEFT * 2.6 + DOWN * 0.5)
        lx = texto(medidas[0], 18).next_to(ax, DOWN, buff=0.05)
        ly = texto("giro x máx (°/s)", 18).next_to(ax.y_axis, UP, buff=0.05)
        color = {c: COLORES[i] for i, c in enumerate(clases)}
        pa = VGroup(*[Dot(ax.c2p(a, b), radius=0.06, color=color[c]) for (a, b), c in zip(X[:, :2], y) if 0 <= a <= 7 and 0 <= b <= 220])
        self.play(Write(titulo), Create(ax), FadeIn(lx, ly), FadeIn(pa, lag_ratio=0.01), run_time=2)
        t1 = VGroup(texto("una persona, una sesión,", 22), texto("dejando uno fuera:", 22), texto(f"{acierto_a * 100:.0f} %", 40, color=BIEN)).arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to(RIGHT * 4.3 + UP * 1.4)
        self.play(FadeIn(t1))
        self.wait(2)
        self.play(pa.animate.set_opacity(0.3), run_time=0.6)
        otra, cifra = VGroup(), VGroup()
        self.add(otra, cifra)
        for g in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
            _, _, Bg, ybg, _, _, acierto = acierto_con_otra(g)
            otra.become(VGroup(*[Triangle(color=color[c], fill_opacity=0.9).scale(0.08).move_to(ax.c2p(a, b)) for (a, b), c in zip(Bg[:, :2], ybg) if 0 <= a <= 7 and 0 <= b <= 220]))
            cifra.become(VGroup(texto("otra persona, mismo modelo,", 22), texto(f"con {g:.1f} veces tu fuerza:", 22), texto(f"{acierto * 100:.0f} %", 40, color=ERROR if acierto < 0.9 else BIEN)).arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to(RIGHT * 4.3 + DOWN * 1.0))
            self.wait(1.3)
        self.play(FadeIn(nota("Dejar uno fuera no sale de la sesión. La prueba justa deja afuera a la persona entera.")))
        self.wait(3)
