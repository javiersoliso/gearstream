"""Animaciones del capítulo 10 (Gestos), una por concepto.

    python docs/curso/animaciones/render.py cap10                     # todas, a GIF en docs/curso/media/cap10/
    python -m manim -ql docs/curso/animaciones/cap10.py DosUmbrales   # una, rápido, para mirarla

Las señales son inventadas, con números de reloj de verdad (100 muestras por segundo). Lo que hace cada detector no
se dibuja a mano: datos_cap10.js corre server/web/flick.js y la animación de apuntar del mocap, y datos_cap10.py
corre los detectores de tools/air_mouse.py. El AUC es el de tools/analyze_drawing.py, importado tal cual. Lo que
las escenas afirman lo comprueba tools/test_gestos.js.
"""
import json
import os
import subprocess
import sys

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "..", "..", "tools"))
import datos_cap10                      # noqa: E402  los detectores de air_mouse.py
from analyze_drawing import auc         # noqa: E402  el de verdad

D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap10.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)
P = datos_cap10.calcular()

GIRO, UMBRAL, SALIDA, ACIERTO, ERROR, CRUDO = BLUE, YELLOW, ORANGE, GREEN, RED, GREY_B


def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


_ROTULOS = {}


def rotulo(s, size=30, **kw):
    """Un Text para always_redraw: compilar un Text tarda, así que cada cadena se hace una sola vez."""
    clave = (s, size, str(kw))
    if clave not in _ROTULOS:
        _ROTULOS[clave] = texto(s, size, **kw)
    return _ROTULOS[clave].copy()


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


def ejes(x, y, ancho=9.5, alto=2.2, numeros=True, abajo=False, **kw):
    """Con abajo=True los números del tiempo van debajo de los ejes, donde las curvas que van a los dos lados no los pisan."""
    ax = Axes(x_range=x, y_range=y, x_length=ancho, y_length=alto, tips=False,
              axis_config={"include_numbers": numeros and not abajo, "font_size": 18}, **kw)
    if abajo:
        ax.y_axis.add_numbers(font_size=18)
        for v in np.arange(x[0], x[1] + x[2] / 2, x[2]):
            ax.add(texto(f"{v:g}", 16).next_to(ax.c2p(v, y[0]), DOWN, buff=0.08))
    return ax


def tramo(xs, ys, x0, x1):
    """Las muestras entre x0 y x1, como arreglos."""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    k = (xs >= x0) & (xs <= x1)
    return xs[k], ys[k]


def traza(ax, xs, ys, tr, color, w=3):
    """La curva hasta donde va el ValueTracker `tr`, sin rehacer un gráfico en cada cuadro."""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    y0, y1 = ax.y_range[:2]
    assert ys.min() >= y0 and ys.max() <= y1, f"la curva se sale de los ejes: {ys.min()} .. {ys.max()} en {y0} .. {y1}"
    puntos = np.array([ax.c2p(x, y) for x, y in zip(xs, ys)])
    m = VMobject(color=color, stroke_width=w)

    def seguir(mob):
        k = max(2, int(np.searchsorted(xs, tr.get_value(), side="right")))
        mob.set_points_as_corners(puntos[:k])

    seguir(m)
    m.add_updater(seguir)
    return m


def aparece(mob, tr, t, opacidad=1):
    """`mob` se ve desde que `tr` llega a t."""
    mob.set_opacity(0)

    def ver(m):
        m.set_opacity(opacidad if tr.get_value() >= t else 0)

    mob.add_updater(ver)
    return mob


def franja(ax, x0, x1, color, opacidad=0.2):
    """Una banda vertical de x0 a x1, de arriba abajo de los ejes."""
    y0, y1 = ax.y_range[:2]
    return Polygon(ax.c2p(x0, y0), ax.c2p(x1, y0), ax.c2p(x1, y1), ax.c2p(x0, y1), stroke_width=0, fill_color=color,
                   fill_opacity=opacidad)


def horizontal(ax, y, color, punteada=True, w=2):
    a, b = ax.c2p(ax.x_range[0], y), ax.c2p(ax.x_range[1], y)
    return DashedLine(a, b, color=color, stroke_width=w) if punteada else Line(a, b, color=color, stroke_width=w)


def giros(n, nombre="giro"):
    return f"{n} {nombre}" if n == 1 else f"{n} {nombre}s"


class Base(Scene):
    nota = None

    def decir(self, s, size=24, t=0.5):
        n = texto(s, size).to_edge(DOWN, buff=0.15)
        if n.width > 13.4:                 # el marco mide 14.2: un rótulo largo se achica un poco, no se corta
            assert n.width < 16.5, f"el rótulo es demasiado largo: {s}"
            n.scale_to_fit_width(13.4).to_edge(DOWN, buff=0.15)
        self.play(*([FadeOut(self.nota)] if self.nota else []), FadeIn(n), run_time=t)
        self.nota = n
        return n

    def avanzar(self, tr, hasta, run_time):
        self.play(tr.animate.set_value(hasta), run_time=run_time, rate_func=linear)


# ---------------------------------------------------------------------------------------------------------
class DetectarUnPico(Base):
    """Cruzar el umbral, seguir el máximo, terminar al bajar: un pico es un evento con instante, signo y tamaño."""

    def construct(self):
        d = D["pico"]
        t = np.array(d["t"]) / 1000
        wx, thr = np.array(d["wx"]), np.array(d["umbral"])
        titulo = texto("Detectar un pico", 34).to_edge(UP)
        ax = ejes([0, 3, 0.5], [-800, 800, 400], ancho=11, alto=4.7, abajo=True).next_to(titulo, DOWN, buff=0.35)
        lab = texto("ω_x (°/s)", 20, color=GIRO).next_to(ax, UP, aligned_edge=LEFT, buff=0.02)
        self.play(Write(titulo), Create(ax), FadeIn(lab))
        tr = ValueTracker(0)
        for signo in (1, -1):
            self.add(traza(ax, t, signo * thr, tr, UMBRAL, 2), traza(ax, t, signo * thr / 2, tr, SALIDA, 2))
        self.add(traza(ax, t, wx, tr, GIRO, 3))
        self.decir("Un giro rápido es un pico de ω_x. El detector lo mira muestra a muestra.")

        def punto(ts, color):
            k = int(np.searchsorted(t, ts))
            return Dot(ax.c2p(t[k], wx[k]), radius=0.09, color=color)

        for e, lugar in zip(d["eventos"], ((1.8, 620), (0.95, -620))):
            t0, tp, tf = e["t0"] / 1000, e["t"] / 1000, e["fin"] / 1000
            self.avanzar(tr, t0, 1.6 if e is d["eventos"][0] else 1.8)
            p0 = punto(t0, WHITE)
            self.play(FadeIn(p0, scale=2), run_time=0.3)
            if e is d["eventos"][0]:
                self.decir("1. Pasa el umbral (amarillo): empieza un giro.")
                self.wait(1)
            self.avanzar(tr, tp, 1.0)
            p1 = punto(tp, ACIERTO)
            self.play(FadeIn(p1, scale=2), run_time=0.3)
            if e is d["eventos"][0]:
                self.decir("2. Mientras sube, guarda el máximo.")
                self.wait(1)
            self.avanzar(tr, tf, 1.0)
            p2 = punto(tf, SALIDA)
            self.play(FadeIn(p2, scale=2), run_time=0.3)
            if e is d["eventos"][0]:
                self.decir("3. Baja de la línea naranja: se cierra el giro y sale un evento.")
            signo = "+" if e["dir"] > 0 else "−"
            c = texto(f"t = {e['t'] / 1000:.2f} s · signo {signo} · tamaño {e['pico']:.0f} °/s", 20, color=ACIERTO)\
                .move_to(ax.c2p(*lugar))
            self.play(FadeIn(c), run_time=0.4)
            self.wait(1.2)
        self.avanzar(tr, 3, 0.8)
        self.decir("Un pico no es una muestra: es un evento con instante, signo y tamaño.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class DosUmbrales(Base):
    """Con un solo umbral, un giro con temblor cuenta varias veces; con dos, una."""

    def construct(self):
        d = D["histeresis"]
        t, wx = tramo(np.array(d["t"]) / 1000, d["wx"], 1.0, 2.0)
        titulo = texto("Histéresis: uno para entrar, otro para salir", 32).to_edge(UP)
        a1 = ejes([1, 2, 0.25], [-50, 250, 100], alto=2.5)
        a2 = ejes([1, 2, 0.25], [-50, 250, 100], alto=2.5)
        VGroup(a1, a2).arrange(DOWN, buff=0.4).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 1.4)
        l1 = texto("un solo\numbral", 20, color=ERROR).next_to(a1, LEFT, buff=0.3)
        l2 = texto("dos\numbrales", 20, color=ACIERTO).next_to(a2, LEFT, buff=0.3)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2))
        self.add(horizontal(a1, d["entrar"], UMBRAL), horizontal(a2, d["entrar"], UMBRAL), horizontal(a2, d["salir"], SALIDA))
        tr = ValueTracker(1)
        e = d["dos"][0]
        banda = franja(a2, e["t0"] / 1000, e["fin"] / 1000, ACIERTO, 0.22)

        def ancho_banda(m):
            x1 = min(max(tr.get_value(), e["t0"] / 1000 + 1e-3), e["fin"] / 1000)
            nueva = franja(a2, e["t0"] / 1000, x1, ACIERTO, 0.22 if tr.get_value() >= e["t0"] / 1000 else 0)
            m.become(nueva)

        banda.add_updater(ancho_banda)
        self.add(banda, traza(a1, t, wx, tr, GIRO), traza(a2, t, wx, tr, GIRO))
        for s in d["unSolo"]:
            k = int(np.searchsorted(t, s / 1000))
            self.add(aparece(Dot(a1.c2p(t[k], wx[k]), radius=0.1, color=ERROR), tr, s / 1000))
        k = int(np.searchsorted(t, e["t0"] / 1000))
        self.add(aparece(Dot(a2.c2p(t[k], wx[k]), radius=0.1, color=ACIERTO), tr, e["t0"] / 1000))
        c1 = always_redraw(lambda: rotulo(giros(sum(s / 1000 <= tr.get_value() for s in d["unSolo"])), 26, color=ERROR)
                           .move_to(a1.c2p(1.13, 200)))
        c2 = always_redraw(lambda: rotulo("1 giro" if e["t0"] / 1000 <= tr.get_value() else "0 giros", 26, color=ACIERTO)
                           .move_to(a2.c2p(1.13, 200)))
        self.add(c1, c2)
        self.decir("Un giro lento con temblor, que se pasea por el borde del umbral.")
        self.avanzar(tr, 2, 8)
        self.decir(f"Entra en {d['entrar']} y sale en {d['salir']:.0f}: el temblor ya no alcanza para salir y volver.")
        self.wait(2)
        self.decir(f"Con un umbral, {len(d['unSolo'])} giros. Con dos, {len(d['dos'])}. En flick.js, salir es la mitad de entrar.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class PeriodoRefractario(Base):
    """Tras un giro hay un rebote: 90 ms sin aceptar otro evita contarlo como otro giro."""

    def construct(self):
        d = D["refractario"]
        t, wx, wl = np.array(d["t"], float), np.array(d["wx"]), np.array(d["wxLargo"])
        titulo = texto("Periodo refractario: no contar dos veces", 32).to_edge(UP)
        a1 = ejes([300, 900, 100], [-400, 800, 400], alto=2.3, abajo=True)
        a2 = ejes([300, 900, 100], [-400, 800, 400], alto=2.3, abajo=True)
        VGroup(a1, a2).arrange(DOWN, buff=0.3).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 1.4)
        l1 = texto("sin espera", 20, color=ERROR).next_to(a1, LEFT, buff=0.3)
        l2 = texto(f"con {d['ms']} ms\nde espera", 20, color=ACIERTO).next_to(a2, LEFT, buff=0.3)
        ms = texto("ms", 16).next_to(a2, RIGHT, buff=0.1)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2, ms))
        k = (t >= 300) & (t <= 900)
        tp = d["con"][0]["t"]

        def marcas(tr, ax, eventos, senal, color):
            for e in eventos:
                i = int(np.searchsorted(t, e["t"]))
                self.add(aparece(Dot(ax.c2p(t[i], senal[i]), radius=0.1, color=color), tr, e["fin"]))

        tr = ValueTracker(300)
        self.add(aparece(franja(a2, tp, tp + d["ms"], UMBRAL), tr, tp, 0.25))
        self.add(traza(a1, t[k], wx[k], tr, GIRO), traza(a2, t[k], wx[k], tr, GIRO))
        marcas(tr, a1, d["sin"], wx, ERROR)
        marcas(tr, a2, d["con"], wx, ACIERTO)
        self.add(always_redraw(lambda: rotulo(giros(sum(e["fin"] <= tr.get_value() for e in d["sin"]), "evento"), 24, color=ERROR)
                               .move_to(a1.c2p(800, 520))),
                 always_redraw(lambda: rotulo(giros(sum(e["fin"] <= tr.get_value() for e in d["con"]), "evento"), 24, color=ACIERTO)
                               .move_to(a2.c2p(800, 520))))
        self.decir("La muñeca frena y rebota: el rebote va al revés y también es un pico.")
        self.avanzar(tr, 900, 6)
        self.decir(f"Los {d['ms']} ms se cuentan desde el máximo. El rebote cae adentro y no cuenta.")
        self.wait(3)

        # un rebote que sigue fuerte pasados los 90 ms sí cuenta
        self.play(*[FadeOut(m) for m in self.mobjects if m is not titulo], run_time=0.5)
        self.clear()
        self.add(titulo)
        self.nota = None
        a3 = ejes([300, 900, 100], [-400, 800, 400], alto=4.2, abajo=True).next_to(titulo, DOWN, buff=0.5).shift(RIGHT * 1.0)
        l3 = texto("un rebote\nque dura más", 20, color=SALIDA).next_to(a3, LEFT, buff=0.3)
        self.play(Create(a3), FadeIn(l3), run_time=0.6)
        tr2 = ValueTracker(300)
        tp = d["reboteLargo"][0]["t"]
        self.add(aparece(franja(a3, tp, tp + d["ms"], UMBRAL), tr2, tp, 0.25))
        self.add(traza(a3, t[k], wl[k], tr2, GIRO))
        marcas(tr2, a3, d["reboteLargo"], wl, SALIDA)
        self.add(always_redraw(lambda: rotulo(giros(sum(e["fin"] <= tr2.get_value() for e in d["reboteLargo"]), "evento"), 24, color=SALIDA)
                               .move_to(a3.c2p(800, 520))))
        self.decir("Si el rebote sigue fuerte después de la espera, sí cuenta.")
        self.avanzar(tr2, 900, 4)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class UmbralQueSeAdapta(Base):
    """Una fracción de la mediana de tus picos: se ajusta a tu fuerza sin calibrar."""

    def construct(self):
        d = D["adaptar"]
        titulo = texto("Un umbral que se adapta a tu fuerza", 32).to_edge(UP)
        formula = MathTex(r"\text{umbral} = \max(70,\ 0.35\cdot\text{mediana de tus picos})", font_size=30)\
            .next_to(titulo, DOWN, buff=0.15)
        a1 = ejes([0, 9, 1], [-1200, 1200, 600], alto=2.1, abajo=True)
        a2 = ejes([0, 9, 1], [-300, 300, 150], alto=2.1, abajo=True)
        VGroup(a1, a2).arrange(DOWN, buff=0.3).next_to(formula, DOWN, buff=0.2).shift(RIGHT * 1.4)
        l1 = texto("persona\nfuerte", 20).next_to(a1, LEFT, buff=0.3)
        l2 = texto("persona\nsuave", 20).next_to(a2, LEFT, buff=0.3)
        self.play(Write(titulo), Write(formula), Create(a1), Create(a2), FadeIn(l1, l2))
        tr = ValueTracker(0)
        for ax, p in ((a1, d["fuerte"]), (a2, d["suave"])):
            t = np.array(p["t"]) / 1000
            wx, thr = np.array(p["wx"]), np.array(p["umbral"])
            self.add(traza(ax, t, wx, tr, GIRO, 2), traza(ax, t, thr, tr, UMBRAL, 3), traza(ax, t, -thr, tr, UMBRAL, 3))
            for e in p["eventos"]:
                self.add(aparece(Dot(ax.c2p(e["t"] / 1000, e["dir"] * e["pico"]), radius=0.06, color=ACIERTO), tr, e["fin"] / 1000))
        lectura = always_redraw(lambda: rotulo(
            f"umbral: {d['fuerte']['umbral'][min(900, int(tr.get_value() * 100))]:.0f} °/s", 20, color=UMBRAL)
            .next_to(a1, UP, aligned_edge=RIGHT, buff=0.02))
        lectura2 = always_redraw(lambda: rotulo(
            f"umbral: {d['suave']['umbral'][min(900, int(tr.get_value() * 100))]:.0f} °/s", 20, color=UMBRAL)
            .next_to(a2, UP, aligned_edge=RIGHT, buff=0.02))
        self.add(lectura, lectura2)
        self.decir("Empieza en 70 °/s. Cada giro aceptado entra en la mediana de los últimos 12.")
        self.avanzar(tr, 9, 8)
        f, s = d["fuerte"], d["suave"]
        self.decir(f"Fijo en 70, a la fuerte le sobran {f['fijo70']['deSobra']} giros de vuelta. Adaptado, {f['adaptado']['deSobra']}.")
        self.wait(2.5)
        self.decir(f"Fijo en 300, a la suave le cuenta {s['fijo300']['giros']} de 12. Adaptado, {s['adaptado']['giros']} de 12.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class DominanciaDeUnEje(Base):
    """Un giro de muñeca es |ω_x| mucho mayor que los otros dos; si se mueve el brazo, los otros también crecen."""

    def construct(self):
        d = D["dominancia"]
        titulo = texto("¿Fue la muñeca o todo el brazo?", 32).to_edge(UP)
        ax = ejes([0, 1250, 250], [0, 1000, 250], ancho=6.2, alto=5.0).to_edge(RIGHT, buff=0.5).shift(DOWN * 0.2)
        lx = texto("el mayor de |ω_y|, |ω_z| (°/s)", 18).next_to(ax, DOWN, buff=0.08)
        ly = texto("|ω_x| (°/s)", 18).next_to(ax, UP, aligned_edge=LEFT, buff=0.08)
        barras = ejes([0, 4, 1], [0, 1000, 250], ancho=4.4, alto=3.8, numeros=False).to_edge(LEFT, buff=1.0).shift(DOWN * 0.4)
        barras.y_axis.add_numbers(font_size=18)
        nombres = VGroup(*[texto(s, 20).next_to(barras.c2p(i + 1, 0), DOWN, buff=0.12) for i, s in enumerate(("|ω_x|", "|ω_y|", "|ω_z|"))])
        self.play(Write(titulo), Create(ax), Create(barras), FadeIn(lx, ly, nombres))

        def dibujar(wx, otro):
            valores = (wx, otro, 0.6 * otro)
            colores = (GIRO, CRUDO, CRUDO)
            return VGroup(*[Rectangle(width=0.7, height=barras.c2p(0, v)[1] - barras.c2p(0, 0)[1], stroke_width=0, fill_color=c,
                                      fill_opacity=0.9).move_to(barras.c2p(i + 1, v / 2)) for i, (v, c) in enumerate(zip(valores, colores))])

        muneca = next(c for c in d["casos"] if c["tipo"] == "muneca")
        brazo = next(c for c in d["casos"] if c["tipo"] == "brazo")
        b = dibujar(muneca["wx"], muneca["otro"])
        self.play(GrowFromEdge(b, DOWN))
        self.decir(f"Un giro de muñeca: {muneca['wx']:.0f} °/s en x, {muneca['otro']:.0f} en el mayor de los otros.")
        self.wait(2)
        b2 = dibujar(brazo["wx"], brazo["otro"])
        self.play(Transform(b, b2))
        self.decir(f"Todo el brazo: {brazo['wx']:.0f} °/s en x, pero {brazo['otro']:.0f} en otro eje.")
        self.wait(2)
        f = d["factor"]
        cuna = Polygon(ax.c2p(0, 0), ax.c2p(1000 / f, 1000), ax.c2p(0, 1000), stroke_width=0, fill_color=ACIERTO, fill_opacity=0.18)
        recta = Line(ax.c2p(0, 0), ax.c2p(1000 / f, 1000), color=UMBRAL, stroke_width=3)
        form = MathTex(r"|\omega_x| > 1.3\cdot\max(|\omega_y|,|\omega_z|)", font_size=28).next_to(barras, UP, buff=0.3)
        self.play(FadeIn(cuna), Create(recta), Write(form))
        assert max(c["otro"] for c in d["casos"]) <= 1250 and max(c["wx"] for c in d["casos"]) <= 1000
        puntos = VGroup(*[(Dot if c["tipo"] == "muneca" else Square)(**({"radius": 0.07} if c["tipo"] == "muneca" else {"side_length": 0.13}),
                          color=GIRO if c["tipo"] == "muneca" else ERROR).set_fill(GIRO if c["tipo"] == "muneca" else ERROR, 1)
                          .move_to(ax.c2p(c["otro"], c["wx"])) for c in d["casos"]])
        self.play(LaggedStart(*[FadeIn(p, scale=2) for p in puntos], lag_ratio=0.08), run_time=3.5)
        n_m = sum(c["acepta"] for c in d["casos"] if c["tipo"] == "muneca")
        n_b = sum(c["acepta"] for c in d["casos"] if c["tipo"] == "brazo")
        tot = sum(c["tipo"] == "muneca" for c in d["casos"])
        self.decir(f"Pasan {n_m} de {tot} giros de muñeca (círculos) y {n_b} de {tot} del brazo (cuadrados).")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ClicDeTornillo(Base):
    """El clic de la animación de apuntar del mocap, leído como lo leería el reloj: 714 °/s de ida, 567 de vuelta."""

    def construct(self):
        d = D["tornillo"]
        t, wx = tramo(np.array(d["t"]) / 1000, d["wx"], 0, 6)
        _, otro = tramo(np.array(d["t"]) / 1000, d["otro"], 0, 6)
        titulo = texto("El clic de tornillo", 34).to_edge(UP)
        ax = ejes([0, 6, 1], [-800, 800, 400], ancho=9.2, alto=4.5, abajo=True).next_to(titulo, DOWN, buff=0.5).to_edge(LEFT, buff=0.6)
        l1 = texto("ω_x (°/s)", 20, color=GIRO).next_to(ax, UP, aligned_edge=LEFT, buff=0.02)
        l2 = texto("el mayor de los otros ejes", 20, color=CRUDO).next_to(ax, UP, aligned_edge=RIGHT, buff=0.02)
        self.play(Write(titulo), Create(ax), FadeIn(l1, l2))
        centro = np.array([5.15, 0.6, 0])
        disco = Circle(radius=1.05, color=WHITE, stroke_width=3).move_to(centro)
        vista = texto("el antebrazo,\nvisto desde el codo", 18).next_to(disco, UP, buff=0.2)
        tr = ValueTracker(0)
        angulo = np.cumsum(wx) * 0.01
        ranura = always_redraw(lambda: Line(centro + LEFT * 0.9, centro + RIGHT * 0.9, color=UMBRAL, stroke_width=9)
                               .rotate(-np.radians(np.interp(tr.get_value(), t, angulo)), about_point=centro))
        self.add(disco, ranura, vista)
        self.add(traza(ax, t, otro, tr, CRUDO, 2), traza(ax, t, wx, tr, GIRO, 2))
        for e in d["eventos"]:
            self.add(aparece(Dot(ax.c2p(e["t"] / 1000, e["dir"] * e["pico"]), radius=0.08, color=ACIERTO), tr, e["fin"] / 1000))
        cuenta = always_redraw(lambda: rotulo(f"{sum(e['fin'] / 1000 <= tr.get_value() for e in d['eventos'])} giros", 24, color=ACIERTO)
                               .next_to(disco, DOWN, buff=0.25))
        self.add(cuenta)
        self.decir("El mocap gira 35° en 70 ms y vuelve: así hace clic el avatar. Sale un pico de cada lado.")
        self.avanzar(tr, 6, 8)
        self.decir(f"{d['picoIda']:.0f} °/s de ida, {d['picoVuelta']:.0f} de vuelta, y {d['otroMax']:.0f} en los otros ejes.")
        self.wait(2.5)
        l117 = VGroup(horizontal(ax, 117, ERROR), horizontal(ax, -117, ERROR))
        e117 = texto("rojo: ±117 °/s", 20, color=ERROR).next_to(disco, DOWN, buff=0.75)
        self.play(Create(l117), FadeIn(e117))
        self.decir("Al apuntar, en el dataset, nunca pasó de 117 °/s. Hay un margen enorme.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ToqueEnLaEsfera(Base):
    """Un salto del acelerómetro z con la muñeca quieta antes y después: por eso se decide 250 ms tarde."""

    def construct(self):
        casos, cfg = P["toques"], P["cfg"]
        titulo = texto("El toque en la esfera: decidir tarde", 32).to_edge(UP)
        a1 = ejes([-300, 400, 100], [4, 12, 4], alto=2.2)
        a2 = ejes([-300, 400, 100], [0, 60, 20], alto=2.0)
        VGroup(a1, a2).arrange(DOWN, buff=0.35).next_to(titulo, DOWN, buff=0.45).shift(RIGHT * 1.4)
        l1 = texto("acelerómetro z\n(m/s²)", 18).next_to(a1, LEFT, buff=0.25)
        l2 = texto("giro\n(°/s)", 18).next_to(a2, LEFT, buff=0.25)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2))
        self.add(franja(a2, -200, -20, CRUDO, 0.22), franja(a2, 80, cfg["tap_post_ms"], CRUDO, 0.22),
                 franja(a1, -200, -100, CRUDO, 0.22), franja(a1, 100, 200, CRUDO, 0.22))
        g1 = DashedLine(a2.c2p(-200, cfg["tap_pre"]), a2.c2p(-20, cfg["tap_pre"]), color=UMBRAL)
        g2 = DashedLine(a2.c2p(80, cfg["tap_post"]), a2.c2p(cfg["tap_post_ms"], cfg["tap_post"]), color=UMBRAL)
        self.add(g1, g2)
        for i, c in enumerate(casos):
            t = np.array(c["t"], float) - c["t_cand"]
            k = (t >= -300) & (t <= 400)
            tr = ValueTracker(-300)
            curvas = VGroup(traza(a1, t[k], np.array(c["az"])[k], tr, GIRO), traza(a2, t[k], np.array(c["giro"])[k], tr, SALIDA))
            ahora = always_redraw(lambda: Line(a1.c2p(tr.get_value(), 12), a2.c2p(tr.get_value(), 0), color=WHITE, stroke_width=1.5))
            self.add(curvas, ahora)
            caso = texto(c["nombre"], 24).next_to(titulo, DOWN, buff=0.08)
            self.play(FadeIn(caso), run_time=0.3)
            if i == 0:
                self.decir("Un golpe: el acelerómetro salta y vuelve. ¿Fue un toque? Falta ver qué pasa después.")
                self.avanzar(tr, 0, 2.5)
                self.wait(1)
                self.decir("Las bandas: quieta antes, y quieta hasta 250 ms después. Hay que esperar.")
                self.avanzar(tr, c["t_decide"] - c["t_cand"], 3)
            else:
                self.avanzar(tr, c["t_decide"] - c["t_cand"], 2.2)
            frases = {
                "confirmado": f"Clic, 250 ms después del golpe. Giro antes {c['giro_antes']:.0f} °/s, después {c['giro_despues']:.0f}.",
                "forma": f"No: el acelerómetro no volvió (se corrió {c['linea_base']:.1f} m/s²; el máximo es 0.8).",
                "giro": (f"No: giraba a {c['giro_antes']:.0f} °/s antes (el máximo es {cfg['tap_pre']:.0f})." if c["giro_antes"] >= cfg["tap_pre"]
                         else f"No: giró a {c['giro_despues']:.0f} °/s después (el máximo es {cfg['tap_post']:.0f})."),
            }
            self.decir(frases[c["veredicto"]])
            self.wait(2.2)
            self.play(FadeOut(curvas, ahora, caso), run_time=0.3)
            for m in (*curvas, ahora):
                m.clear_updaters()
        self.decir("Esperar 250 ms es lo que cuesta no confundir un toque con un golpe de la mano.")
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
class ElEmpujon(Base):
    """La aceleración lineal a lo largo del antebrazo, y la mira de 120 ms antes."""

    def construct(self):
        d = D["empujon"]
        t = np.array(d["t"]) / 1000
        x0, x1 = 0.6, 1.4
        tt, af = tramo(t, d["af"], x0, x1)
        _, yaw = tramo(t, d["yaw"], x0, x1)
        titulo = texto("El empujón", 34).to_edge(UP)
        form = MathTex(r"a_f = (\vec a_{\text{acel}} - \vec g)\cdot\hat x", font_size=30).next_to(titulo, DOWN, buff=0.12)
        a1 = ejes([x0, x1, 0.2], [-12, 20, 8], alto=2.2, abajo=True)
        a2 = ejes([x0, x1, 0.2], [6, 18, 4], alto=2.0)
        VGroup(a1, a2).arrange(DOWN, buff=0.35).next_to(form, DOWN, buff=0.2).shift(RIGHT * 1.4)
        l1 = texto("a lo largo del\nantebrazo (m/s²)", 18, color=GIRO).next_to(a1, LEFT, buff=0.25)
        l2 = texto("mira (°)", 18, color=SALIDA).next_to(a2, LEFT, buff=0.25)
        self.play(Write(titulo), Write(form), Create(a1), Create(a2), FadeIn(l1, l2))
        self.add(horizontal(a1, d["on"], UMBRAL), horizontal(a1, d["off"], SALIDA))
        tr = ValueTracker(x0)
        self.add(traza(a1, tt, af, tr, GIRO), traza(a2, tt, yaw, tr, SALIDA))
        self.decir(f"Empieza al pasar {d['on']:.0f} m/s² y termina al bajar de {d['off']:.1f}: otra vez dos umbrales.")
        t0, tf = d["t0"] / 1000, d["fin"] / 1000
        self.avanzar(tr, t0, 2.5)

        def marca(ts, valor, color, lado):
            v = Line(a1.c2p(ts, 20), a2.c2p(ts, 6), color=color, stroke_width=2)
            p = Dot(a2.c2p(ts, valor), radius=0.09, color=color)
            e = texto(f"{valor:.1f}°", 20, color=color).next_to(p, lado, buff=0.12)
            return VGroup(v, p, e)

        m1 = marca(t0, d["miraCruce"], UMBRAL, UP)
        self.play(FadeIn(m1), run_time=0.4)
        self.decir("Cuando pasa el umbral, la mira ya se empezó a correr.")
        self.wait(1.5)
        self.avanzar(tr, tf, 2)
        m2 = marca(tf, d["miraFin"], ERROR, LEFT)
        self.play(FadeIn(m2), run_time=0.4)
        self.decir("Al terminar el empujón se corrió mucho más: empujar también gira la muñeca.")
        self.wait(1.5)
        m3 = marca(t0 - d["antes"] / 1000, d["miraAntes"], ACIERTO, UP)
        self.play(FadeIn(m3), run_time=0.4)
        self.decir(f"Por eso el dardo sale con la mira de {d['antes']} ms antes de empezar: {d['miraAntes']:.1f}°, la que tenías.")
        self.avanzar(tr, x1, 1.5)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class LaSacudida(Base):
    """Muchos cambios de signo rápidos y fuertes en 700 ms: la señal para pausar."""

    def construct(self):
        d = P["sacudidas"]
        titulo = texto("La sacudida: muchas vueltas en poco tiempo", 32).to_edge(UP)
        a1 = ejes([0, 2, 0.5], [-1000, 1000, 500], alto=2.25, abajo=True)
        a2 = ejes([0, 2, 0.5], [-1000, 1000, 500], alto=2.25, abajo=True)
        VGroup(a1, a2).arrange(DOWN, buff=0.4).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 1.4)
        l1 = texto("4 idas y vueltas\npor segundo", 18).next_to(a1, LEFT, buff=0.2)
        l2 = texto("2 idas y vueltas\npor segundo", 18).next_to(a2, LEFT, buff=0.2)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2))
        tr = ValueTracker(0)

        def cambios(c, hasta):
            """Los cambios de signo de ShakeDetector: en los últimos 700 ms, solo lo que pasa de 200 °/s."""
            t, w = np.array(c["t"], float), np.array(c["wx"])
            n, s = 0, 0
            for v in w[(t >= hasta - 700) & (t <= hasta)]:
                if abs(v) > 200:
                    q = 1 if v > 0 else -1
                    n += bool(s and q != s)
                    s = q
            return n

        fuego = d["fuerte"]["fuegos"][0]
        assert cambios(d["fuerte"], fuego["t"]) >= 4
        for ax, c in ((a1, d["fuerte"]), (a2, d["lenta"])):
            t = np.array(c["t"]) / 1000
            for y, col in ((200, SALIDA), (-200, SALIDA), (600, UMBRAL), (-600, UMBRAL)):
                self.add(horizontal(ax, y, col))
            self.add(traza(ax, t, c["wx"], tr, GIRO, 2.5))

        def ventana(ax):
            def hacer():
                x1 = max(tr.get_value(), 0.001)
                return franja(ax, max(0, x1 - 0.7), x1, WHITE, 0.14)
            return always_redraw(hacer)

        self.add(ventana(a1), ventana(a2))
        hasta_fuego = lambda: min(tr.get_value() * 1000, fuego["t"])                                     # noqa: E731
        c1 = always_redraw(lambda: rotulo(giros(cambios(d["fuerte"], hasta_fuego()), "cambio") + " de signo", 20, color=ACIERTO)
                           .next_to(a1, UP, aligned_edge=RIGHT, buff=0.02))
        c2 = always_redraw(lambda: rotulo(giros(cambios(d["lenta"], tr.get_value() * 1000), "cambio") + " de signo", 20, color=ERROR)
                           .next_to(a2, UP, aligned_edge=RIGHT, buff=0.02))
        self.add(c1, c2)
        self.decir("Cuenta los cambios de signo en 700 ms (la banda), solo lo que pasa de 200 °/s.")
        self.avanzar(tr, fuego["t"] / 1000, 4)
        p = Dot(a1.c2p(fuego["t"] / 1000, 0), radius=0.13, color=ACIERTO)
        self.play(FadeIn(p, scale=2), run_time=0.3)
        self.decir("Con 4 cambios y más de 600 °/s, dispara: pausa o reanuda.")
        self.wait(2)
        self.avanzar(tr, 2, 4)
        primero = next(b["hz"] for b in d["barrido"] if b["dispara"])
        ultimo_no = max(b["hz"] for b in d["barrido"] if not b["dispara"])
        self.decir(f"A {ultimo_no:.0f} idas y vueltas por segundo no alcanza; desde {primero} sí. Un giro solo, nunca.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ClicPorPermanencia(Base):
    """Quedarse quieto sobre un punto un rato, después de haber viajado, cuenta como clic."""

    def construct(self):
        d = P["permanencia"]
        t = np.array(d["t"], float)
        x, y, carga, viaje, quieto = (np.array(d[k], float) for k in ("x", "y", "carga", "viajado", "quieto"))
        titulo = texto("Clic por permanencia", 34).to_edge(UP)
        pantalla = Rectangle(width=7.2, height=4.8, color=GREY_B).shift(LEFT * 2.6 + DOWN * 0.2)
        esq = pantalla.get_corner(UL)
        escala = 7.2 / 560
        p2 = lambda a, b: esq + np.array([a * escala, -b * escala, 0])                                    # noqa: E731
        self.play(Write(titulo), Create(pantalla))
        tr = ValueTracker(0)
        cursor = always_redraw(lambda: Dot(p2(np.interp(tr.get_value(), t, x), np.interp(tr.get_value(), t, y)), radius=0.1, color=WHITE))
        camino = VMobject(color=GIRO, stroke_width=3)
        puntos = np.array([p2(a, b) for a, b in zip(x, y)])

        def seguir(m):
            k = max(2, int(np.searchsorted(t, tr.get_value(), side="right")))
            m.set_points_as_corners(puntos[:k])

        seguir(camino)
        camino.add_updater(seguir)

        def anillo():
            c = float(np.interp(tr.get_value(), t, carga))
            centro = p2(np.interp(tr.get_value(), t, x), np.interp(tr.get_value(), t, y))
            if c <= 0.01:
                return VectorizedPoint(centro)
            return Arc(radius=0.4, start_angle=PI / 2, angle=-TAU * c, color=ACIERTO, stroke_width=7, arc_center=centro)

        anillo_m = always_redraw(anillo)
        self.add(camino, anillo_m, cursor)
        lect = always_redraw(lambda: VGroup(
            rotulo(f"viajó {np.interp(tr.get_value(), t, viaje):.0f} px", 24),
            rotulo(f"(pide {d['viaje']:.0f})", 20, color=CRUDO),
            rotulo(f"quieto {np.interp(tr.get_value(), t, quieto):.1f} s", 24),
            rotulo(f"(pide {d['tiempo']} s, a menos de {d['velocidad']} °/s)", 20, color=CRUDO),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.18).to_edge(RIGHT, buff=0.5).shift(UP * 0.6))
        self.add(lect)
        self.decir("Quieto sin haber viajado: no cuenta. Si no, soltar la mano sería un clic.")
        self.avanzar(tr, 800, 2.5)
        self.decir("Primero viaja y va rápido. Eso lo deja listo.")
        self.avanzar(tr, 1800, 3)
        self.decir("Se queda quieto en el mismo lugar (menos de 6 px): se llena el anillo.")
        fuego = d["fuegos"][0]
        self.avanzar(tr, fuego, 3.5)
        p = p2(np.interp(fuego, t, x), np.interp(fuego, t, y))
        onda = Circle(radius=0.15, color=ACIERTO, stroke_width=6).move_to(p)
        self.play(onda.animate.scale(4).set_stroke(opacity=0), run_time=0.6)
        self.decir(f"Clic a los {fuego / 1000:.2f} s. Y no se repite: hay que viajar otra vez.")
        self.avanzar(tr, 4000, 3)
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
class ScrollConElAntebrazo(Base):
    """Girar más de 25° desde la postura neutra, tras una pausa y despacio; cada muesca con histéresis."""

    def construct(self):
        d = P["scroll"]
        titulo = texto("Scroll con el antebrazo", 34).to_edge(UP)
        ax = ejes([0, 3, 0.5], [-10, 60, 10], ancho=8.4, alto=5.0).next_to(titulo, DOWN, buff=0.35).to_edge(LEFT, buff=0.7)
        l1 = texto("giro desde la postura neutra (°)", 18).next_to(ax, UP, aligned_edge=LEFT, buff=0.02)
        self.play(Write(titulo), Create(ax), FadeIn(l1))
        self.add(horizontal(ax, d["entrar"], UMBRAL), horizontal(ax, d["salir"], SALIDA))
        muescas = [d["entrar"] + d["muesca"] * k for k in (1, 2, 3)]
        for m in muescas:
            self.add(horizontal(ax, m, CRUDO, w=1))
        self.add(texto(f"entra: {d['entrar']:.0f}°", 18, color=UMBRAL).move_to(ax.c2p(0.33, d["entrar"] + 3)),
                 texto(f"sale: {d['salir']:.0f}°", 18, color=SALIDA).move_to(ax.c2p(0.33, d["salir"] - 3)))
        # la página que se mueve: una columna de renglones
        marco = Rectangle(width=2.6, height=4.2, color=GREY_B).to_edge(RIGHT, buff=0.7).shift(DOWN * 0.1)
        renglones = VGroup(*[Line(LEFT * 1.0, RIGHT * (1.0 - 0.5 * (i % 3)), color=GREY_B, stroke_width=4).shift(DOWN * 0.5 * i)
                             for i in range(11)])
        renglones.shift(marco.get_top() + DOWN * 0.4 - renglones[0].get_center())

        def adentro(g):
            for r in g:
                r.set_stroke(opacity=1 if marco.get_bottom()[1] + 0.1 < r.get_y() < marco.get_top()[1] - 0.1 else 0)

        renglones.add_updater(adentro)
        adentro(renglones)
        self.add(marco, renglones)
        tr = ValueTracker(0)
        c = d["lento"]
        t = np.array(c["t"]) / 1000
        self.add(traza(ax, t, c["e"], tr, GIRO))
        self.decir("Una pausa, y girar despacio. Al pasar 25° entra en modo scroll.")
        for i, m in enumerate(c["muescas"]):
            ts = m["t"] / 1000
            self.avanzar(tr, ts, 2.6 if i == 0 else 1)
            self.add(Dot(ax.c2p(ts, m["e"]), radius=0.08, color=ACIERTO))
            self.play(renglones.animate.shift(UP * 0.5), run_time=0.25)
            if i == 0:
                self.decir(f"Cada {d['muesca']:.0f}° más es una muesca de la rueda: baja un renglón.")
        self.avanzar(tr, c["salidas"][0] / 1000, 2.5)
        self.decir(f"Volver no sube nada, y al bajar de {d['salir']:.0f}° sale. Entra en 25, sale en 15: histéresis.")
        self.avanzar(tr, 3, 1.5)
        self.wait(2)
        for k, frase in (("rapido", f"De un golpe, más de {d['tasa_max']:.0f} °/s: es un movimiento, no un scroll."),
                         ("sin_pausa", "Sin una pausa antes, tampoco: la mano venía haciendo otra cosa.")):
            c = d[k]
            assert not c["entradas"]
            tr2 = ValueTracker(0)
            curva = traza(ax, np.array(c["t"]) / 1000, c["e"], tr2, ERROR, 2.5)
            self.add(curva)
            self.decir(frase)
            self.avanzar(tr2, 3, 2.5)
            self.wait(1.5)
            self.remove(curva)
        self.wait(1.5)


# ---------------------------------------------------------------------------------------------------------
class ElTempo(Base):
    """60000 / el intervalo mediano: un giro que falta no mueve la mediana, y al promedio sí."""

    def construct(self):
        d = D["tempo"]
        t = np.array(d["t"]) / 1000
        titulo = texto("Tempo: el intervalo mediano", 34).to_edge(UP)
        a1 = ejes([0, 4.5, 0.5], [-800, 800, 400], ancho=11.2, alto=2.0, abajo=True).next_to(titulo, DOWN, buff=0.3)
        a2 = ejes([0, 7, 1], [0, 1200, 400], ancho=5.8, alto=2.4, numeros=False).next_to(a1, DOWN, buff=0.45).to_edge(LEFT, buff=1.0)
        a2.y_axis.add_numbers(font_size=18)
        l2 = texto("intervalos (ms), de menor a mayor", 18).next_to(a2, UP, aligned_edge=LEFT, buff=0.02)
        self.play(Write(titulo), Create(a1))
        tr = ValueTracker(0)
        self.add(traza(a1, t, d["wx"], tr, GIRO, 2.5))
        for e in d["eventos"]:
            self.add(aparece(Dot(a1.c2p(e["t"] / 1000, e["dir"] * e["pico"]), radius=0.07, color=ACIERTO), tr, e["fin"] / 1000))
        self.decir("Cada giro es un pulso, en cualquier sentido. Entre el cuarto y el quinto falta uno.")
        self.avanzar(tr, 4.5, 5)
        self.play(Create(a2), FadeIn(l2))
        barras = VGroup(*[Rectangle(width=0.6, height=a2.c2p(0, v)[1] - a2.c2p(0, 0)[1], stroke_width=0, fill_color=CRUDO, fill_opacity=0.9)
                          .move_to(a2.c2p(i + 1, v / 2)) for i, v in enumerate(d["orden"])])
        numeros = VGroup(*[texto(str(v), 16, color=BLACK).move_to(a2.c2p(i + 1, 130)) for i, v in enumerate(d["orden"])])
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in barras], lag_ratio=0.15), FadeIn(numeros), run_time=1.6)
        self.decir("El intervalo de 1000 ms es un giro que no se detectó, no un cambio de ritmo.")
        self.wait(1.5)
        lp = horizontal(a2, d["promedio"], ERROR)
        lm = horizontal(a2, d["mediana"], ACIERTO, punteada=False)
        k = d["orden"].index(d["mediana"])
        self.play(barras[k].animate.set_fill(ACIERTO), Create(lm), Create(lp))
        self.add(numeros)
        res = VGroup(
            MathTex(r"\text{BPM} = \frac{60000}{\text{intervalo en ms}}", font_size=30),
            texto(f"mediana {d['mediana']} ms: {d['bpm']:.1f} por minuto", 22, color=ACIERTO),
            texto(f"promedio {d['promedio']:.0f} ms: {d['bpmPromedio']:.1f} por minuto", 22, color=ERROR),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.18).next_to(a2, RIGHT, buff=0.6)
        self.play(FadeIn(res))
        self.decir(f"De verdad eran {d['bpmDeVerdad']} por minuto: la mediana no se deja arrastrar.")
        self.wait(3.5)


# ---------------------------------------------------------------------------------------------------------
class MuestrasDeUnGolpe(Base):
    """Una muestra cada 10 ms: a un golpe de 10 ms le pasa por al lado; a un giro de 100 ms, no."""

    def construct(self):
        m = D["muestreo"]
        titulo = texto("Una muestra cada 10 ms", 34).to_edge(UP)
        a1 = ejes([-25, 25, 10], [0, 1.2, 0.5], ancho=5.8, alto=3.9)
        a2 = ejes([-100, 100, 50], [0, 1.2, 0.5], ancho=5.8, alto=3.9)
        VGroup(a1, a2).arrange(RIGHT, buff=0.8).next_to(titulo, DOWN, buff=0.85)
        t1 = texto("un golpe corto (pellizco), en ms", 22).next_to(a1, UP, buff=0.12)
        t2 = texto("un giro, en ms", 22).next_to(a2, UP, buff=0.12)
        pul = lambda x: max(0.0, 1 - abs(x) / 5)                                                          # noqa: E731
        gir = lambda x: float(np.exp(-0.5 * (x / 30) ** 2))                                              # noqa: E731
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(t1, t2))
        self.play(Create(a1.plot(pul, x_range=[-25, 25, 0.25], color=SALIDA, stroke_width=4)),
                  Create(a2.plot(gir, x_range=[-100, 100, 1], color=GIRO, stroke_width=4)))
        fase = ValueTracker(0)

        def peine(ax, f, lim):
            def hacer():
                g = VGroup()
                x = fase.get_value() - 10 * np.ceil((lim + fase.get_value()) / 10)
                while x <= lim:
                    if x >= -lim:
                        g.add(Line(ax.c2p(x, 0), ax.c2p(x, f(x)), color=WHITE, stroke_width=1.5), Dot(ax.c2p(x, f(x)), radius=0.06, color=WHITE))
                    x += 10
                return g
            return always_redraw(hacer)

        def visto(f):
            r = fase.get_value()
            return max(f(r + 10 * k) for k in range(-3, 4))

        self.add(peine(a1, pul, 25), peine(a2, gir, 100))
        c1 = always_redraw(lambda: rotulo(f"lo más alto que se ve: {100 * visto(pul):.0f} %", 22, color=SALIDA).next_to(a1, DOWN, buff=0.1))
        c2 = always_redraw(lambda: rotulo(f"lo más alto que se ve: {100 * visto(gir):.1f} %", 22, color=GIRO).next_to(a2, DOWN, buff=0.1))
        self.add(c1, c2)
        self.decir("El reloj no elige cuándo mide: el golpe cae donde cae entre dos muestras.")
        self.play(fase.animate.set_value(5), run_time=3, rate_func=linear)
        self.wait(1.5)
        self.play(fase.animate.set_value(-5), run_time=4, rate_func=linear)
        self.play(fase.animate.set_value(0), run_time=2, rate_func=linear)
        self.decir(f"Del golpe de 10 ms se ve entre {100 * m['pellizco']['peor']:.0f} % y {100 * m['pellizco']['mejor']:.0f} %; "
                   f"del giro, al menos {100 * m['giro']['peor']:.1f} %.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class AciertosYFalsasAlarmas(Base):
    """Bajar el umbral atrapa más gestos y dispara más veces sin querer. Datos inventados."""

    def construct(self):
        b = D["barrido"]
        titulo = texto("Aciertos contra falsas alarmas", 34).to_edge(UP)
        filas = []
        for g, tope, paso, y in ((b["pellizco"], 7, 1, 1.15), (b["giro"], 900, 150, -1.55)):
            tira = ejes([0, tope, paso], [-1, 1, 1], ancho=6.6, alto=1.7).move_to([-3.0, y, 0])
            tira.y_axis.set_opacity(0)
            curva = ejes([0, 40, 10], [0, 20, 10], ancho=3.9, alto=1.6).move_to([4.2, y + 0.05, 0])
            filas.append((g, tope, tira, curva, ValueTracker(tope)))
        self.play(Write(titulo), *[Create(f[2]) for f in filas], *[Create(f[3]) for f in filas])
        rng = np.random.default_rng(10)          # solo para repartir los puntos en la franja, sin tocar sus valores
        for g, tope, tira, curva, tr in filas:
            pos, neg = np.array(g["pos"]), np.array(g["neg"])
            assert pos.max() <= tope and neg.max() <= tope
            puntos = VGroup(*[Dot(tira.c2p(v, 0.55 + 0.35 * rng.uniform(-1, 1)), radius=0.05, color=ACIERTO) for v in pos],
                            *[Dot(tira.c2p(v, -0.55 + 0.35 * rng.uniform(-1, 1)), radius=0.05, color=ERROR) for v in neg])
            nombre = texto(f"{g['nombre']} ({g['unidad']})", 20).next_to(tira, UP, aligned_edge=LEFT, buff=0.05)
            ejx = texto("falsas alarmas por minuto", 16).next_to(curva, DOWN, buff=0.03)
            ejy = texto("aciertos de 20", 16).next_to(curva, UP, aligned_edge=LEFT, buff=0.03)
            self.add(puntos, nombre, ejx, ejy)
        for g, tope, tira, curva, tr in filas:
            pos, neg = np.array(g["pos"]), np.array(g["neg"])
            c = np.array(g["curva"])
            xs, ys = c[:, 0], c[:, 1]
            pts = np.array([curva.c2p(min(x, 40), y) for x, y in zip(xs, ys)])

            def cuenta(pos=pos, neg=neg, tr=tr):
                T = tr.get_value()
                return float((neg >= T).sum()) / b["minutos"], int((pos >= T).sum())

            camino = VMobject(color=GIRO, stroke_width=3)

            def seguir(m, pts=pts, xs=xs, ys=ys, cuenta=cuenta):
                fa, ac = cuenta()
                m.set_points_as_corners(pts[:max(2, int(((xs <= fa) & (ys <= ac)).sum()))])

            camino.add_updater(seguir)
            seguir(camino)
            self.add(always_redraw(lambda tira=tira, tr=tr: Line(tira.c2p(tr.get_value(), -1), tira.c2p(tr.get_value(), 1), color=UMBRAL, stroke_width=3)),
                     camino,
                     always_redraw(lambda curva=curva, cuenta=cuenta: Dot(curva.c2p(min(cuenta()[0], 40), cuenta()[1]), radius=0.08, color=WHITE)),
                     always_redraw(lambda tira=tira, cuenta=cuenta: VGroup(rotulo(f"{cuenta()[1]} de 20", 18, color=ACIERTO),
                                                                           rotulo(f"{cuenta()[0]:.1f} falsas alarmas por minuto", 18, color=ERROR))
                                   .arrange(RIGHT, buff=0.4).next_to(tira, DOWN, buff=0.05)))
        self.decir("Arriba, verde: 20 gestos. Abajo, rojo: 2 minutos de uso normal. Datos inventados.")
        self.wait(1.5)
        self.play(*[f[4].animate.set_value(0) for f in filas], run_time=7, rate_func=linear)
        self.decir("Muy alto: no atrapa nada. Muy bajo: dispara solo. Se elige por minuto de uso normal.")
        self.wait(2)
        p, g = b["pellizco"], b["giro"]
        self.play(*[f[4].animate.set_value(f[0]["peorNeg"] * 1.001) for f in filas], run_time=2.5)
        self.decir(f"Sin ninguna falsa alarma: pellizco {p['aciertosSinFalsas']} de 20, giro {g['aciertosSinFalsas']} de 20.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ElAUC(Base):
    """La probabilidad de que un positivo dé más señal que un negativo cualquiera."""

    def construct(self):
        b = D["barrido"]
        titulo = texto("AUC: un número para toda la curva", 34).to_edge(UP)
        aes = []
        for g in (b["pellizco"], b["giro"]):
            ax = ejes([0, 1, 0.5], [0, 1, 0.5], ancho=3.7, alto=3.7)
            aes.append(ax)
        VGroup(*aes).arrange(RIGHT, buff=0.8).next_to(titulo, DOWN, buff=0.85).to_edge(LEFT, buff=0.45)
        self.play(Write(titulo), *[Create(a) for a in aes])
        valores, cuentas = [], []
        for ax, g in zip(aes, (b["pellizco"], b["giro"])):
            c = np.array(g["curva"])
            fx, fy = c[:, 0] / c[:, 0].max(), c[:, 1] / 20
            area = float(np.sum(np.diff(fx) * (fy[1:] + fy[:-1]) / 2))
            valor = auc(g["pos"], g["neg"])
            assert abs(area - valor) < 0.01 and abs(valor - g["auc"]) < 0.01, (area, valor, g["auc"])
            valores.append(valor)
            nombre = texto(g["nombre"], 24).next_to(ax, UP, buff=0.1)
            ejx = texto("falsas alarmas (fracción)", 16).next_to(ax, DOWN, buff=0.03)
            diag = DashedLine(ax.c2p(0, 0), ax.c2p(1, 1), color=CRUDO)
            curva = linea(ax, fx, fy, GIRO, 4)
            relleno = Polygon(*[ax.c2p(x, y) for x, y in zip(fx, fy)], ax.c2p(1, 0), ax.c2p(0, 0), stroke_width=0, fill_color=GIRO, fill_opacity=0.3)
            self.play(FadeIn(nombre, ejx), Create(diag), Create(curva), run_time=1.3)
            self.play(FadeIn(relleno), run_time=0.8)
            self.add(texto(f"área {area:.2f}", 26).move_to(ax.c2p(0.68, 0.28)))
            cuentas.append((g, ax))
        self.decir("La diagonal es no distinguir nada: 0.5. Toda la esquina es separar todo: 1.")
        self.wait(2.5)
        # el mismo número, sacando pares al azar
        rng = np.random.default_rng(4)
        g = b["pellizco"]
        pos, neg = np.array(g["pos"]), np.array(g["neg"])
        form = MathTex(r"\text{AUC} = P(\text{positivo} > \text{negativo})", font_size=28).to_edge(RIGHT, buff=0.25).shift(UP * 1.6)
        self.play(Write(form))
        pares = [(rng.choice(pos), rng.choice(neg)) for _ in range(40)]
        i = ValueTracker(1)

        def marcador():
            k = int(i.get_value())
            p, n = pares[k - 1]
            gana = sum(x > y for x, y in pares[:k])
            return VGroup(rotulo("pares de pellizco", 20),
                          rotulo(f"{p:.1f} contra {n:.1f}", 22, color=ACIERTO if p > n else ERROR),
                          rotulo(f"ganó el positivo: {gana} de {k}", 20),
                          rotulo(f"= {gana / k:.2f}", 26)).arrange(DOWN, aligned_edge=LEFT, buff=0.12).to_edge(RIGHT, buff=0.35).shift(DOWN * 0.5)

        self.add(always_redraw(marcador))
        self.play(i.animate.set_value(40), run_time=8, rate_func=linear)
        self.decir(f"Con todos los pares da {valores[0]:.2f}, igual que el área. Para el giro, {valores[1]:.2f}.")
        self.wait(3.5)
