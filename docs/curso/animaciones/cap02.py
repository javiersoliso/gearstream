"""Animaciones del capítulo 2 (Vectores y marcos), una por concepto.

    python docs/curso/animaciones/render.py cap02                     # todas, a GIF en docs/curso/media/cap02/
    python -m manim -ql docs/curso/animaciones/cap02.py ProductoPunto   # una, rápido, para mirarla

Los vectores son inventados, con números de reloj de verdad (9.81 m/s²). La cuenta es la de server/web/mocapmath.js:
datos_cap02.js la corre con node y este archivo comprueba que su copia da lo mismo antes de dibujar nada. wrap_deg es
la de tools/air_mouse.py, importada tal cual; lo que las escenas afirman lo comprueba tools/test_marcos.js.
"""
import json
import os
import subprocess
import sys

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "..", "tools"))
from air_mouse import wrap_deg      # noqa: E402  la de verdad

D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap02.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)
CX, CY, CZ = RED, GREEN, BLUE          # los ejes del reloj
GRADO = np.pi / 180
G = 9.81


# ---------- la cuenta, igual que mocapmath.js ----------
def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def Rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def R_eje(k, a):
    k = unit(k)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def watch_of(F, d, lado):
    """watchOf de mocapmath.js: x hacia la mano en la izquierda, hacia el codo en la derecha; z sale del dorso."""
    X = np.array(F, float) if lado == "l" else -np.array(F, float)
    Z = np.array(d, float)
    return X, np.cross(Z, X), Z


_a, _b = np.array(D["a"], float), np.array(D["b"], float)
assert np.isclose(_a @ _b, D["dot"]) and np.allclose(np.cross(_a, _b), D["cross"])
assert np.isclose(np.linalg.norm(_a), D["len"]) and np.allclose(unit(_a), D["unit"])
for _lado, _nombre in (("l", "izquierda"), ("r", "derecha")):
    for _e, _w in zip(watch_of([0, 0, -1], [0, 1, 0], _lado), "XYZ"):
        assert np.allclose(_e, D[_nombre][_w])
assert np.allclose([np.degrees(np.arctan2(-F[0], -F[2])) for F in ([1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, -1.0])], D["rumbos"])
assert wrap_deg(350) == -10 and wrap_deg(180) == -180 and wrap_deg(10 - 350) == 20


# ---------- dibujo ----------
def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


def flecha(a, b, color, w=6):
    return Arrow(np.asarray(a, float), np.asarray(b, float), buff=0, color=color, stroke_width=w,
                 max_tip_length_to_length_ratio=0.15)


def reloj(lado=1.1, R=None, centro=ORIGIN):
    """Un cubo con la cara de arriba azul y la del frente roja, para ver cómo quedó girado."""
    c = Cube(side_length=lado, fill_opacity=0.9, fill_color=GREY_D, stroke_width=1, stroke_color=GREY_B)
    c[1].set_fill(BLUE_D)                 # OUT: arriba (z)
    c[3].set_fill(RED_D)                  # RIGHT: x
    c[4].set_fill(GREEN_D)                # UP: y
    if R is not None:
        c.apply_matrix(R, about_point=ORIGIN)
    return c.shift(centro)


def ejes(R=np.eye(3), largo=1.6, centro=ORIGIN, w=6):
    centro = np.asarray(centro, float)
    return VGroup(*[flecha(centro, centro + largo * R[:, i], c, w) for i, c in enumerate([CX, CY, CZ])])


def ejes_mundo(largo=3.0):
    return VGroup(*[DashedLine(-0.4 * e, largo * e, stroke_opacity=0.45) for e in np.eye(3)])


def terna(v, dec=2):
    return "(" + ", ".join(num(x, dec) for x in v) + ")"


def num(x, dec=2):
    return f"{round(float(x), dec) + 0.0:.{dec}f}".replace("-", "−")       # + 0.0: sin "−0.00"


class Escena3D(ThreeDScene):
    def decir(self, s, color=WHITE, size=24):
        nuevo = texto(s, size, color=color)
        if nuevo.width > 13.4:
            nuevo.scale_to_fit_width(13.4)
        nuevo.to_edge(DOWN, buff=0.35)
        self.add_fixed_in_frame_mobjects(nuevo)
        viejo = getattr(self, "_rotulo", None)
        self.play(*([FadeOut(viejo)] if viejo else []), FadeIn(nuevo), run_time=0.6)
        self._rotulo = nuevo

    def fijo(self, func):
        """Algo fijo en la pantalla que se rehace en cada cuadro (las cifras, por ejemplo)."""
        m = func()
        self.add_fixed_in_frame_mobjects(m)
        m.add_updater(lambda mm: (mm.become(func()), self.renderer.camera.add_fixed_in_frame_mobjects(mm)))
        return m

    def titulo(self, s, size=32):
        t = texto(s, size).to_edge(UP)
        self.add_fixed_in_frame_mobjects(t)
        self.play(Write(t))
        return t

    def rotulos(self, *pares):
        """Etiquetas en el espacio que siempre miran a la cámara: (texto, posición, color)."""
        g = [texto(s, 26, color=c).move_to(p) for s, p, c in pares]
        self.add_fixed_orientation_mobjects(*g)
        return VGroup(*g)


class Escena2D(Scene):
    def decir(self, s, color=WHITE, size=24):
        nuevo = texto(s, size, color=color)
        if nuevo.width > 13.4:
            nuevo.scale_to_fit_width(13.4)
        nuevo.to_edge(DOWN, buff=0.3)
        viejo = getattr(self, "_rotulo", None)
        self.play(*([FadeOut(viejo)] if viejo else []), FadeIn(nuevo), run_time=0.6)
        self._rotulo = nuevo


# ---------------------------------------------------------------------------------------------------------
class UnVector(Escena3D):
    """Un vector: una flecha con dirección y largo, escrita como tres números en unos ejes."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-50 * DEGREES, zoom=0.9, frame_center=OUT * 0.9)
        self.titulo("Un vector: una flecha, tres números")
        self.add(ejes_mundo(3.2))
        self.rotulos(("x", 3.45 * RIGHT, CX), ("y", 3.45 * UP, CY), ("z", 3.45 * OUT, CZ))
        p = [ValueTracker(0.0), ValueTracker(0.0), ValueTracker(0.0)]
        v = lambda: np.array([q.get_value() for q in p])

        def camino():
            x, y, z = v()
            return VGroup(Line(ORIGIN, [x, 0, 0], color=CX, stroke_width=5), Line([x, 0, 0], [x, y, 0], color=CY, stroke_width=5),
                          Line([x, y, 0], [x, y, z], color=CZ, stroke_width=5))

        pasos = always_redraw(camino)
        self.add(pasos)
        self.fijo(lambda: texto(f"v = {terna(v(), 1)}", 30, color=YELLOW).to_corner(UL).shift(DOWN * 0.8))
        self.decir("Para llegar a la punta: tanto en x, tanto en y, tanto en z.")
        for q, val in zip(p, (2.4, 1.6, 1.8)):
            self.play(q.animate.set_value(val), run_time=1.2)
        fv = always_redraw(lambda: flecha(ORIGIN, v(), YELLOW, 7) if np.linalg.norm(v()) > 0.1 else VectorizedPoint())
        self.add(fv)
        self.decir("Tres números, uno por eje, alcanzan para decir cualquier flecha.", YELLOW)
        self.wait(1.5)
        self.play(*[q.animate.set_value(val) for q, val in zip(p, (-1.5, 2.2, 1.0))], run_time=2.5)
        self.play(*[q.animate.set_value(val) for q, val in zip(p, (1.8, 0.2, 1.0))], run_time=2.5)
        self.decir("Otra flecha, otros tres números.")
        self.wait(1)
        w = np.array([-0.6, 1.8, 1.0])
        self.remove(pasos)
        a = v()
        fw = flecha(ORIGIN, w, ORANGE, 7)
        lw = texto(f"w = {terna(w, 1)}", 30, color=ORANGE).to_corner(UL).shift(DOWN * 1.35)
        self.add_fixed_in_frame_mobjects(lw)
        self.play(GrowArrow(fw), FadeIn(lw))
        self.decir("Una flecha no tiene lugar: moverla entera no cambia sus números.", ORANGE)
        self.play(fw.animate.shift(a), run_time=2)
        s = flecha(ORIGIN, a + w, WHITE, 7)
        ls = texto(f"v + w = {terna(a + w, 1)}", 30).to_corner(UL).shift(DOWN * 1.9)
        self.add_fixed_in_frame_mobjects(ls)
        self.decir("Por eso se suman poniendo una a continuación de la otra: número a número.")
        self.play(GrowArrow(s), FadeIn(ls))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class LargoDeUnVector(Escena3D):
    """El largo: Pitágoras dos veces, primero en el piso y después con la altura."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-40 * DEGREES, zoom=1.0)
        self.titulo("El largo de un vector: Pitágoras, dos veces")
        self.add(ejes_mundo(2.8))
        x, y, z = v = np.array([2.0, 1.0, 2.0])
        piso = np.array([x, y, 0])
        d = np.hypot(x, y)
        l = np.linalg.norm(v)
        fv = flecha(ORIGIN, v, YELLOW, 7)
        self.play(GrowArrow(fv))
        lv = texto(f"v = {terna(v, 0)}", 28, color=YELLOW).to_corner(UL).shift(DOWN * 0.8)
        self.add_fixed_in_frame_mobjects(lv)
        self.play(FadeIn(lv))
        self.decir("En el piso: un triángulo recto con catetos x e y.", ORANGE)
        self.play(Create(Line(ORIGIN, [x, 0, 0], color=CX, stroke_width=5)), Create(Line([x, 0, 0], piso, color=CY, stroke_width=5)))
        diag = Line(ORIGIN, piso, color=ORANGE, stroke_width=7)
        self.play(Create(diag))
        f1 = MathTex(r"d = \sqrt{x^2+y^2} = \sqrt{" + f"{x:.0f}^2+{y:.0f}^2" + "} = " + f"{d:.2f}", font_size=32, color=ORANGE)\
            .next_to(lv, DOWN, buff=0.25).align_to(lv, LEFT)
        self.add_fixed_in_frame_mobjects(f1)
        self.play(Write(f1))
        self.decir("De pie sobre esa diagonal, otro triángulo recto: catetos d y z.", CZ)
        self.play(Create(Line(piso, v, color=CZ, stroke_width=5)))
        self.wait(1)
        f2 = MathTex(r"|v| = \sqrt{d^2+z^2} = \sqrt{x^2+y^2+z^2} = " + f"{l:.0f}", font_size=32, color=YELLOW)\
            .next_to(f1, DOWN, buff=0.25).align_to(lv, LEFT)
        self.add_fixed_in_frame_mobjects(f2)
        self.play(Write(f2))
        self.wait(1.5)
        tabla = VGroup(texto("la gravedad, leída con el reloj quieto:", 22))
        for R in (np.eye(3), Rx(50 * GRADO), Ry(35 * GRADO) @ Rx(-70 * GRADO)):
            g = R.T @ np.array([0, 0, G])
            tabla.add(texto(f"{terna(g)}   largo {np.linalg.norm(g):.2f}", 22, color=BLUE_B))
        tabla.arrange(DOWN, aligned_edge=LEFT, buff=0.14).next_to(f2, DOWN, buff=0.4).align_to(lv, LEFT)
        self.add_fixed_in_frame_mobjects(tabla)
        self.decir("Los tres números cambian con la postura; el largo, no.", BLUE_B)
        self.play(FadeIn(tabla))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class VectorUnitario(Escena2D):
    """Dividir un vector por su largo deja solo la dirección."""

    def construct(self):
        S = 1.25                                        # unidades del dibujo por unidad de largo
        O = LEFT * 3.2 + DOWN * 0.35
        titulo = texto("Dividir por el largo deja solo la dirección", 32).to_edge(UP)
        self.play(Write(titulo))
        circulo = Circle(radius=S, color=GREY_B, stroke_width=3).move_to(O)
        lineas = VGroup(Line(O + LEFT * 3.3, O + RIGHT * 3.3, stroke_opacity=0.35), Line(O + DOWN * 2.7, O + UP * 2.7, stroke_opacity=0.35))
        vs = [np.array(p, float) for p in [(2.2, 0.9), (-0.8, 2.0), (-2.1, -1.0), (0.7, -1.9), (0.5, -0.2)]]
        cols = [YELLOW, ORANGE, TEAL, PINK, GREEN]
        t = ValueTracker(0)

        def punta(v):
            n = np.linalg.norm(v)
            largo = n + (1 - n) * t.get_value()
            return O + S * np.array([*(v / n * largo), 0])

        fl = [always_redraw(lambda v=v, c=c: flecha(O, punta(v), c, 6)) for v, c in zip(vs, cols)]
        self.play(FadeIn(lineas), *[FadeIn(f) for f in fl])
        self.decir("Cinco flechas de largos distintos.")
        self.wait(1)
        self.play(Create(circulo))
        f = MathTex(r"\hat v = \frac{v}{|v|}", font_size=44).move_to(RIGHT * 3.6 + UP * 2.1)
        self.play(Write(f))
        self.decir("Dividir cada una por su largo: todas llegan al círculo de radio 1.")
        self.play(t.animate.set_value(1), run_time=3)
        self.wait(1)
        g = np.array([3.1, -5.2, 7.7])
        n = np.linalg.norm(g)
        panel = VGroup(texto("una lectura de la gravedad:", 22), texto(terna(g, 1), 24, color=BLUE_B),
                       texto(f"largo {n:.2f}", 24, color=BLUE_B), texto("dividida por su largo:", 22),
                       texto(terna(g / n), 24, color=YELLOW), texto(f"largo {np.linalg.norm(g / n):.2f}", 24, color=YELLOW))\
            .arrange(DOWN, aligned_edge=LEFT, buff=0.16).next_to(f, DOWN, buff=0.4)
        self.play(FadeIn(panel))
        self.decir("Lo que sobrevive es la dirección: hacia dónde es arriba, vista desde el reloj.", YELLOW)
        self.wait(2.5)
        libre = MathTex(r"x^2+y^2+z^2 = 1", font_size=34).next_to(panel, DOWN, buff=0.35).align_to(panel, LEFT)
        self.play(Write(libre))
        self.decir("De largo 1, x e y deciden z (salvo el signo): la dirección son dos números.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class SenoYCoseno(Escena2D):
    """Una flecha de largo 1 con ángulo θ llega a (cos θ, sen θ)."""

    def construct(self):
        R = 1.9
        O = LEFT * 4.2 + DOWN * 0.3
        titulo = texto("Seno y coseno: adónde llega una flecha de largo 1", 32).to_edge(UP)
        self.play(Write(titulo))
        th = ValueTracker(0.001)
        p = lambda a=None: np.array([np.cos(th.get_value() if a is None else a), np.sin(th.get_value() if a is None else a), 0])
        circ = Circle(radius=R, color=GREY_B, stroke_width=2).move_to(O)
        cruz = VGroup(Line(O + LEFT * 2.3, O + RIGHT * 2.3, stroke_opacity=0.4), Line(O + DOWN * 2.3, O + UP * 2.3, stroke_opacity=0.4))
        ax = Axes(x_range=[0, 2 * PI, PI / 2], y_range=[-1, 1, 0.5], x_length=6.4, y_length=3.0, tips=False,
                  axis_config={"font_size": 18}, y_axis_config={"include_numbers": True, "font_size": 18})\
            .move_to(RIGHT * 3.0 + DOWN * 0.1)
        marcas = VGroup(*[texto(s, 18).next_to(ax.c2p(a, 0), DOWN, buff=0.45 if a > 6 else 0.14)
                          for s, a in (("90°", PI / 2), ("180°", PI), ("270°", 3 * PI / 2), ("360°", 2 * PI))])
        self.play(Create(circ), FadeIn(cruz), Create(ax), FadeIn(marcas))
        flech = always_redraw(lambda: flecha(O, O + R * p(), YELLOW, 7))
        cat = always_redraw(lambda: VGroup(Line(O, O + R * p() * RIGHT, color=CX, stroke_width=7),
                                           Line(O + R * p() * RIGHT, O + R * p(), color=CY, stroke_width=7)))
        self.add(cat, flech)

        def traza(f, color):
            def hacer():
                a = np.linspace(0, max(th.get_value(), 0.002), 90)
                return VMobject(color=color, stroke_width=4).set_points_as_corners([ax.c2p(x, f(x)) for x in a])
            return always_redraw(hacer)

        self.add(traza(np.cos, CX), traza(np.sin, CY))
        lect = always_redraw(lambda: VGroup(
            texto(f"θ = {np.degrees(th.get_value()):.0f}° = {th.get_value():.2f} radianes", 21),
            texto(f"cos θ = {num(np.cos(th.get_value()))}", 21, color=CX),
            texto(f"sen θ = {num(np.sin(th.get_value()))}", 21, color=CY))
            .arrange(RIGHT, buff=0.35).move_to(RIGHT * 2.5 + UP * 2.35))
        self.add(lect)
        self.decir("El coseno es lo que avanza en x; el seno, lo que sube en y.")
        self.play(th.animate.set_value(PI), run_time=5, rate_func=linear)
        self.decir("Media vuelta: π radianes son 180°.")
        self.play(th.animate.set_value(2 * PI), run_time=5, rate_func=linear)
        self.decir("Una vuelta: 2π radianes, lo que mide el círculo de radio 1.")
        self.wait(1.5)
        self.play(th.animate.set_value(40 * GRADO), run_time=2)
        recta = Line(O + RIGHT * R + DOWN * 0.4, O + RIGHT * R + UP * 2.3, color=GREY_B)
        t40 = np.tan(40 * GRADO)
        sube = Line(O + RIGHT * R, O + RIGHT * R + UP * R * t40, color=ORANGE, stroke_width=8)
        rayo = DashedLine(O, O + R * np.array([1, t40, 0]), color=ORANGE)
        self.play(Create(recta), Create(rayo), Create(sube))
        f = MathTex(r"\tan\theta = \frac{\sin\theta}{\cos\theta} = " + f"{t40:.2f}", font_size=36, color=ORANGE)\
            .move_to(RIGHT * 3.2 + DOWN * 2.45)
        self.play(Write(f))
        self.decir("La tangente es cuánto sube por cada 1 que avanza: seno sobre coseno.", ORANGE)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class PorQueAtan2(Escena2D):
    """y/x no distingue una flecha de su opuesta; atan2(y, x) devuelve el ángulo en los cuatro cuadrantes."""

    def construct(self):
        R = 1.75
        O = LEFT * 4.3 + DOWN * 0.45
        titulo = texto("Del punto al ángulo: ¿por qué atan2?", 32).to_edge(UP)
        self.play(Write(titulo))
        th = ValueTracker(-179.5)
        p = lambda: np.array([np.cos(th.get_value() * GRADO), np.sin(th.get_value() * GRADO), 0])
        circ = Circle(radius=R, color=GREY_B, stroke_width=2).move_to(O)
        cruz = VGroup(Line(O + LEFT * 2.1, O + RIGHT * 2.1, stroke_opacity=0.4), Line(O + DOWN * 2.1, O + UP * 2.1, stroke_opacity=0.4))
        ax = Axes(x_range=[-180, 180, 90], y_range=[-180, 180, 90], x_length=6.0, y_length=4.1, tips=False,
                  axis_config={"font_size": 18, "include_numbers": True}).move_to(RIGHT * 3.1 + DOWN * 0.55)
        lx = texto("ángulo de verdad (°)", 18).next_to(ax, DOWN, buff=0.1)
        self.play(Create(circ), FadeIn(cruz), Create(ax), FadeIn(lx))
        fl = always_redraw(lambda: flecha(O, O + R * p(), YELLOW, 7))
        op = always_redraw(lambda: DashedLine(O, O - R * p(), color=GREY_B))
        self.add(op, fl)

        visto = {"t": -179.5}                           # lo ya recorrido se queda dibujado aunque la flecha vuelva

        def traza(f, color, cortes, w=5):
            def hacer():
                g = VGroup()
                t = visto["t"] = max(visto["t"], th.get_value())
                for a, b in cortes:
                    if t > a:
                        xs = np.linspace(a, min(b, t), 60)
                        g.add(VMobject(color=color, stroke_width=w).set_points_as_corners([ax.c2p(x, f(x)) for x in xs]))
                return g
            return always_redraw(hacer)

        a2 = lambda x: np.degrees(np.arctan2(np.sin(x * GRADO), np.cos(x * GRADO)))
        a1 = lambda x: np.degrees(np.arctan(np.sin(x * GRADO) / np.cos(x * GRADO)))
        self.add(traza(a2, GREEN, [(-179.5, 179.5)], 7), traza(a1, RED, [(-179.5, -90.1), (-89.9, 89.9), (90.1, 179.5)], 4))

        def lectura():
            x, y = p()[:2]
            yx = "no existe (x = 0)" if abs(x) < 0.01 else num(y / x)
            r1 = "?" if abs(x) < 0.01 else f"{num(np.degrees(np.arctan(y / x)), 0)}°"
            return VGroup(texto(f"(x, y) = ({num(x)}, {num(y)})   y/x = {yx}", 22, color=YELLOW),
                          VGroup(texto(f"atan(y/x) = {r1}", 22, color=RED),
                                 texto(f"atan2(y, x) = {num(np.degrees(np.arctan2(y, x)), 0)}°", 22, color=GREEN)).arrange(RIGHT, buff=0.5))\
                .arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to(RIGHT * 3.0 + UP * 2.35)

        self.add(always_redraw(lectura))
        self.decir("La punta da una vuelta. Rojo: el ángulo de y/x. Verde: atan2.")
        self.play(th.animate.set_value(179.5), run_time=9, rate_func=linear)
        self.decir("Rojo solo vive entre −90° y 90°: la mitad de las direcciones no existen para él.", RED)
        self.wait(1)
        self.play(th.animate.set_value(45), run_time=1.5)
        self.wait(0.5)
        self.play(th.animate.set_value(-135), run_time=2)
        self.decir("(1, 1) y (−1, −1) dan el mismo y/x, pero son flechas opuestas.", RED)
        self.wait(2)
        self.play(th.animate.set_value(90), run_time=2)
        self.decir("Y con x = 0 no se puede dividir. atan2 mira los dos números por separado.", GREEN)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class AngulosQueDanLaVuelta(Escena2D):
    """350° y −10° son el mismo ángulo: las diferencias se llevan a [−180°, 180°) antes de usarlas."""

    def construct(self):
        R = 2.0
        O = LEFT * 3.9 + DOWN * 0.4
        titulo = texto("Ángulos que dan la vuelta", 34).to_edge(UP)
        self.play(Write(titulo))
        circ = Circle(radius=R, color=GREY_B, stroke_width=2).move_to(O)
        cruz = VGroup(Line(O + LEFT * 2.3, O + RIGHT * 2.3, stroke_opacity=0.4), Line(O + DOWN * 2.3, O + UP * 2.3, stroke_opacity=0.4))
        self.play(Create(circ), FadeIn(cruz))
        punta = lambda a: O + R * np.array([np.cos(a * GRADO), np.sin(a * GRADO), 0])
        a = ValueTracker(0)
        b = ValueTracker(0)
        fa = always_redraw(lambda: flecha(O, punta(a.get_value()), YELLOW, 7))
        fb = always_redraw(lambda: flecha(O, punta(b.get_value()), ORANGE, 4))
        self.add(fa, fb)
        la = always_redraw(lambda: texto(f"{a.get_value():.0f}°".replace("-", "−"), 28, color=YELLOW).move_to(RIGHT * 1.6 + UP * 2.2))
        lb = always_redraw(lambda: texto(f"{b.get_value():.0f}°".replace("-", "−"), 28, color=ORANGE).move_to(RIGHT * 3.6 + UP * 2.2))
        self.add(la, lb)
        self.decir("Una flecha da casi toda la vuelta; la otra retrocede un poquito.")
        self.play(a.animate.set_value(350), b.animate.set_value(-10), run_time=4)
        self.decir("Terminan en el mismo lugar: 350° y −10° son el mismo ángulo.", YELLOW)
        self.wait(2)
        self.play(b.animate.set_value(10), run_time=1.5)
        self.remove(lb, la)
        l1 = texto("350° y 10°: separados por muy poco", 26).move_to(RIGHT * 2.7 + UP * 2.2)
        promedio = (350 + 10) / 2
        ingenuo = flecha(O, punta(promedio), RED, 7)
        l2 = texto(f"promedio sin cuidado: (350 + 10) / 2 = {promedio:.0f}°", 24, color=RED).next_to(l1, DOWN, buff=0.3)
        self.play(FadeIn(l1))
        self.decir("Si los promedio sin cuidado...", RED)
        self.play(GrowArrow(ingenuo), FadeIn(l2))
        self.decir("...el promedio apunta justo al revés.", RED)
        self.wait(2)
        dif = wrap_deg(10 - 350)
        bien = wrap_deg(350 + dif / 2)
        f = MathTex(r"\mathrm{wrap}(a) = a - 360\left\lfloor\frac{a+180}{360}\right\rfloor", font_size=34).next_to(l2, DOWN, buff=0.35)
        l3 = texto(f"10 − 350 = −340, y wrap(−340) = {dif:.0f}", 24, color=GREEN).next_to(f, DOWN, buff=0.3)
        l4 = texto(f"350 + {dif:.0f} / 2 = 360, y wrap(360) = {bien:.0f}°", 24, color=GREEN).next_to(l3, DOWN, buff=0.2)
        self.decir("La diferencia se lleva a [−180°, 180°) antes de usarla: wrap_deg.", GREEN)
        self.play(Write(f))
        self.play(FadeIn(l3))
        correcto = flecha(O, punta(bien), GREEN, 7)
        self.play(FadeIn(l4), GrowArrow(correcto))
        self.wait(2.5)
        viejos = [m for m in self.mobjects if m is not titulo and m is not self._rotulo]
        self.play(*[FadeOut(m) for m in viejos])

        # un ángulo que crece parejo, leído en [−180°, 180°): la lectura salta y la diferencia, envuelta, no
        ts = np.arange(0, 12.01, 0.25)
        ang = 120 + 40 * ts
        leido = np.array([wrap_deg(x) for x in ang])
        crudo = np.diff(leido)
        envuelto = np.array([wrap_deg(x) for x in crudo])
        a1 = Axes(x_range=[0, 12, 2], y_range=[-180, 180, 180], x_length=9.5, y_length=2.2, tips=False,
                  axis_config={"font_size": 18, "include_numbers": True})
        a2 = Axes(x_range=[0, 12, 2], y_range=[-360, 40, 100], x_length=9.5, y_length=2.2, tips=False,
                  axis_config={"font_size": 18}, y_axis_config={"include_numbers": True, "font_size": 18})
        VGroup(a1, a2).arrange(DOWN, buff=0.45).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 1.4)
        l1 = texto("el ángulo\nleído (°)", 20).next_to(a1, LEFT, buff=0.3)
        l2 = texto("cuánto cambió\nen cada muestra (°)", 20).next_to(a2, LEFT, buff=0.3)
        self.play(Create(a1), Create(a2), FadeIn(l1, l2))
        tramos = VGroup()
        ini = 0
        for k in np.nonzero(np.abs(crudo) > 180)[0]:
            tramos.add(a1.plot_line_graph(ts[ini:k + 1], leido[ini:k + 1], add_vertex_dots=False, line_color=YELLOW, stroke_width=4))
            ini = k + 1
        tramos.add(a1.plot_line_graph(ts[ini:], leido[ini:], add_vertex_dots=False, line_color=YELLOW, stroke_width=4))
        self.decir("Algo gira parejo, 10° por muestra. La lectura salta al pasar por 180°.", YELLOW)
        self.play(Create(tramos), run_time=2.5)
        c1 = a2.plot_line_graph(ts[1:], crudo, add_vertex_dots=False, line_color=RED, stroke_width=4)
        c2 = a2.plot_line_graph(ts[1:], envuelto, add_vertex_dots=False, line_color=GREEN, stroke_width=5)
        self.decir(f"Restar sin cuidado da {num(crudo.min(), 0)}° en cada salto: un giro que no ocurrió.", RED)
        self.play(Create(c1), run_time=2)
        self.wait(1)
        self.decir(f"Con wrap_deg siempre da {envuelto.max():.0f}°: lo que giró de verdad.", GREEN)
        self.play(Create(c2), run_time=2)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ProductoPunto(Escena2D):
    """a·b = Σ aᵢbᵢ = |a||b| cos θ: cuánto de un vector va en la dirección del otro."""

    def construct(self):
        O = LEFT * 3.6 + DOWN * 0.9
        titulo = texto("El producto punto: la sombra de una flecha sobre otra", 32).to_edge(UP)
        self.play(Write(titulo))
        base = 12 * GRADO
        b = 3.0 * np.array([np.cos(base), np.sin(base), 0])
        bu = unit(b)
        th = ValueTracker(65)
        a = lambda: 2.5 * np.array([np.cos(base + th.get_value() * GRADO), np.sin(base + th.get_value() * GRADO), 0])
        guia = DashedLine(O - 3.0 * bu, O + 3.6 * bu, stroke_opacity=0.35)
        fb = flecha(O, O + b, ORANGE, 7)
        lb = texto("b", 28, color=ORANGE).move_to(O + b + 0.3 * DOWN)
        fa = always_redraw(lambda: flecha(O, O + a(), YELLOW, 7))
        la = always_redraw(lambda: texto("a", 28, color=YELLOW).move_to(O + a() * 1.12))
        sombra = always_redraw(lambda: Line(O, O + (a() @ bu) * bu + 0.001 * bu,
                                            color=GREEN if a() @ bu >= 0 else RED, stroke_width=12))
        caida = always_redraw(lambda: DashedLine(O + a(), O + (a() @ bu) * bu + 0.001 * RIGHT, color=GREY_B))
        self.play(FadeIn(guia), GrowArrow(fb), FadeIn(lb))
        self.add(sombra, caida, fa, la)
        f = MathTex(r"a\cdot b = \sum_i a_i b_i = |a|\,|b|\cos\theta", font_size=36).move_to(RIGHT * 3.5 + UP * 2.4)
        self.play(Write(f))

        def panel():
            v = a()
            suma = v @ b
            otra = np.linalg.norm(v) * np.linalg.norm(b) * np.cos(th.get_value() * GRADO)
            return VGroup(texto(f"θ = {th.get_value():.0f}°", 26),
                          texto(f"a = ({num(v[0])}, {num(v[1])})", 24, color=YELLOW),
                          texto(f"b = ({num(b[0])}, {num(b[1])})", 24, color=ORANGE),
                          texto(f"a₁b₁ + a₂b₂ = {num(suma)}", 24),
                          texto(f"|a||b| cos θ = {num(otra)}", 24),
                          texto(f"sombra de a sobre b = {num(v @ bu)}", 24, color=GREEN if v @ bu >= 0 else RED))\
                .arrange(DOWN, aligned_edge=LEFT, buff=0.16).move_to(UP * 0.3, aligned_edge=LEFT).shift(RIGHT * 1.6)

        self.add(always_redraw(panel))
        self.decir("Multiplicar número a número y sumar da lo mismo que el largo por el coseno.")
        self.wait(2)
        self.play(th.animate.set_value(20), run_time=2.5)
        self.decir("Casi alineadas: casi todo a va en la dirección de b.", GREEN)
        self.wait(1)
        self.play(th.animate.set_value(90), run_time=3)
        self.decir("En ángulo recto no hay sombra: a no tiene nada en la dirección de b. Da cero.")
        self.wait(2.5)
        self.play(th.animate.set_value(150), run_time=3)
        self.decir("Pasados los 90° va en contra: el producto punto es negativo.", RED)
        self.wait(2)
        self.play(th.animate.set_value(50), run_time=3)
        self.decir("Esa sombra se llama proyección: cuánto de una flecha va en la dirección de otra.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ProductoCruz(Escena3D):
    """a × b forma ángulo recto con los dos y mide |a||b| sen θ, el área del paralelogramo."""

    def construct(self):
        self.set_camera_orientation(phi=66 * DEGREES, theta=-62 * DEGREES, zoom=0.9)
        self.titulo("El producto cruz: una flecha en ángulo recto con las dos")
        a = np.array([2.0, 0, 0])
        th = ValueTracker(40)
        b = lambda: 1.5 * np.array([np.cos(th.get_value() * GRADO), np.sin(th.get_value() * GRADO), 0])
        c = lambda: np.cross(a, b())
        fa = flecha(ORIGIN, a, YELLOW, 7)
        fb = always_redraw(lambda: flecha(ORIGIN, b(), ORANGE, 7))
        area = always_redraw(lambda: Polygon(ORIGIN, a, a + b(), b(), color=TEAL, fill_opacity=0.35, stroke_width=2))
        fc = always_redraw(lambda: flecha(ORIGIN, c(), WHITE, 7) if np.linalg.norm(c()) > 0.12 else VectorizedPoint())
        self.add(area, fa, fb)
        self.decir("Dos flechas forman un paralelogramo.", TEAL)
        self.wait(1)
        self.add(fc)
        self.fijo(lambda: VGroup(
            texto(f"θ = {th.get_value():.0f}°", 26),
            texto(f"área = {abs(a[0] * b()[1]):.2f}", 24, color=TEAL),
            texto(f"|a||b| |sen θ| = {num(3.0 * abs(np.sin(th.get_value() * GRADO)))}", 24),
            texto(f"a × b = {terna(c())}", 24))
            .arrange(DOWN, aligned_edge=LEFT, buff=0.15).move_to(RIGHT * 1.9 + UP * 1.9, aligned_edge=LEFT))
        f = MathTex(r"a\times b = \begin{pmatrix} a_y b_z - a_z b_y\\ a_z b_x - a_x b_z\\ a_x b_y - a_y b_x\end{pmatrix}", font_size=30)\
            .to_corner(UL).shift(DOWN * 0.85)
        self.add_fixed_in_frame_mobjects(f)
        self.play(Write(f))
        self.decir("a × b sale del plano, en ángulo recto con las dos, y mide esa área.")
        self.wait(1.5)
        self.play(th.animate.set_value(90), run_time=2.5)
        self.decir("El área es la mayor cuando forman ángulo recto: |a||b|.", TEAL)
        self.wait(1.5)
        self.play(th.animate.set_value(180), run_time=3.5)
        self.decir("Alineadas no hay paralelogramo: el producto cruz da cero.")
        self.wait(2)
        self.play(th.animate.set_value(300), run_time=3.5)
        self.decir("Del otro lado apunta para abajo: importa quién va primero.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ReglaManoDerecha(Escena3D):
    """x × y = z fija hacia dónde apunta el producto cruz; un eje dado vuelta es un espejo."""

    def construct(self):
        self.set_camera_orientation(phi=66 * DEGREES, theta=-65 * DEGREES, zoom=0.85)
        self.titulo("¿Hacia cuál de los dos lados? La regla de la mano derecha")
        ca, cb = np.array([-3.0, 0, -0.6]), np.array([3.0, 0, -0.6])
        A = ejes(np.eye(3), 1.9, ca)
        rot_a = self.rotulos(("x", ca + 2.2 * RIGHT, CX), ("y", ca + 2.2 * UP, CY), ("z", ca + 2.2 * OUT, CZ))
        curva = Arc(radius=0.9, start_angle=0, angle=PI / 2, color=YELLOW, stroke_width=6).add_tip(tip_length=0.2).shift(ca)
        self.play(Create(A), FadeIn(rot_a))
        self.decir("Los dedos van de x hacia y; el pulgar dice dónde queda z: x × y = z.", YELLOW)
        self.play(Create(curva), run_time=1.5)
        self.wait(1.5)
        la = texto("x × y = z", 26, color=WHITE).to_corner(UL).shift(DOWN * 0.85 + RIGHT * 0.8)
        self.add_fixed_in_frame_mobjects(la)
        self.play(FadeIn(la))
        self.decir("Es un acuerdo, no una ley: elegimos la mano derecha y hay que cumplirlo siempre.")
        self.wait(2.5)

        # a la derecha: otra mano es un giro; un eje dado vuelta, un espejo
        sx, sy = ValueTracker(1.0), ValueTracker(1.0)
        a = ValueTracker(0)

        def marco():
            R = Rz(a.get_value())
            x, y = sx.get_value() * R[:, 0], sy.get_value() * R[:, 1]
            return VGroup(*[flecha(cb, cb + 1.9 * e, c, 6) for e, c in ((x, CX), (y, CY)) if np.linalg.norm(e) > 0.06],
                          flecha(cb, cb + 1.9 * np.array([0, 0, 1.0]), CZ, 6))

        B = always_redraw(marco)
        self.add(B)
        lb = texto("en la otra mano: x e y se dan vuelta", 24).to_corner(UR).shift(DOWN * 0.85 + LEFT * 0.1)
        self.add_fixed_in_frame_mobjects(lb)
        self.decir("En la otra mano, x e y se dan vuelta y z se queda.")
        self.play(FadeIn(lb))
        self.play(a.animate.set_value(PI), run_time=3)
        nx = np.array([-1.0, 0, 0])
        ny = np.array([0, -1.0, 0])
        l2 = texto(f"(−x) × (−y) = {terna(np.cross(nx, ny), 0)} = z: es un giro", 24, color=GREEN).next_to(lb, DOWN, buff=0.15).align_to(lb, RIGHT)
        self.add_fixed_in_frame_mobjects(l2)
        self.decir("Eso es un giro de 180° alrededor de z: sigue siendo x × y = z.", GREEN)
        self.play(FadeIn(l2))
        self.wait(2.5)
        self.play(a.animate.set_value(0), run_time=1.5)
        self.play(FadeOut(lb, l2))
        l3 = texto("un solo eje dado vuelta", 24).to_corner(UR).shift(DOWN * 0.85 + LEFT * 0.1)
        l4 = texto(f"(−x) × y = {terna(np.cross(nx, [0, 1.0, 0]), 0)} = −z: es un espejo", 24, color=RED).next_to(l3, DOWN, buff=0.15).align_to(l3, RIGHT)
        self.add_fixed_in_frame_mobjects(l3, l4)
        self.decir("Dar vuelta un solo eje no se consigue girando: es un espejo.", RED)
        self.play(FadeIn(l3), sx.animate.set_value(-1), run_time=2)
        self.play(FadeIn(l4))
        self.wait(2)

        # el mismo giro, leído en los dos marcos
        t = ValueTracker(0)
        r = 1.2
        giro = lambda c, s: c + r * np.array([s * np.cos(t.get_value()), np.sin(t.get_value()), 0])
        pa = always_redraw(lambda: VGroup(Line(ca, giro(ca, 1), color=YELLOW, stroke_width=5), Dot(giro(ca, 1), color=YELLOW, radius=0.17)))
        pb = always_redraw(lambda: VGroup(Line(cb, giro(cb, -1), color=YELLOW, stroke_width=5), Dot(giro(cb, -1), color=YELLOW, radius=0.17)))
        ra = Circle(radius=r, stroke_opacity=0.4, color=GREY_B).shift(ca)
        rb = Circle(radius=r, stroke_opacity=0.4, color=GREY_B).shift(cb)
        self.play(FadeOut(curva), Create(ra), Create(rb))
        self.add(pa, pb)
        vuelta = 4.0                                    # segundos por vuelta
        tasa = 360 / vuelta
        v1 = texto(f"alrededor de z: +{tasa:.0f} °/s", 24, color=GREEN).to_edge(DOWN, buff=1.0).shift(LEFT * 3.4)
        v2 = texto(f"en el espejo: −{tasa:.0f} °/s", 24, color=RED).to_edge(DOWN, buff=1.0).shift(RIGHT * 3.4)
        self.add_fixed_in_frame_mobjects(v1, v2)
        self.decir("En el espejo, el giro alrededor de z va al revés: cambia de signo.", RED)
        self.play(FadeIn(v1, v2), t.animate.set_value(2 * PI), run_time=vuelta, rate_func=linear)
        self.wait(2)


# ---------------------------------------------------------------------------------------------------------
class MarcoDeReferencia(Escena3D):
    """El mismo vector tiene números distintos en el marco del reloj y en el del mundo."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-48 * DEGREES, zoom=0.95)
        self.titulo("¿x, y, z de quién? El marco de referencia")
        self.add(ejes_mundo(2.7))
        a = ValueTracker(90 * GRADO)
        extra = ValueTracker(0)
        R = lambda: R_eje([0.5, 1, 0.2], extra.get_value()) @ Rx(a.get_value())
        cubo = always_redraw(lambda: reloj(0.9, R()))
        fl = always_redraw(lambda: ejes(R(), 1.7))
        arriba = np.array([0, 0, 1.0])
        g = flecha(ORIGIN, 2.45 * arriba, YELLOW, 9)
        lg = self.rotulos(("gravedad", 2.8 * arriba + 0.2 * RIGHT, YELLOW))
        self.add(cubo, fl)
        self.play(GrowArrow(g), FadeIn(lg))

        def panel():
            M = R()
            lee = M.T @ (G * arriba)
            return VGroup(texto(f"en el mundo: {terna(G * arriba)}", 24),
                          texto(f"en el reloj: {terna(lee + 0.0)}", 24, color=YELLOW),
                          texto(f"largo: {np.linalg.norm(lee):.2f}", 24))\
                .arrange(DOWN, aligned_edge=LEFT, buff=0.14).to_corner(UL).shift(DOWN * 0.8)

        self.fijo(panel)
        self.decir("El reloj de canto, con su y hacia arriba: lee (0, 9.81, 0).", CY)
        self.wait(2)
        self.play(a.animate.set_value(0), run_time=4)
        self.decir("Acostado, con su z hacia arriba: lee (0, 0, 9.81).", CZ)
        self.wait(2)
        self.decir("La gravedad no se movió: se movieron los ejes con los que se la mide.", YELLOW)
        self.wait(1)
        self.play(extra.animate.set_value(70 * GRADO), run_time=3.5)
        self.wait(0.5)
        self.play(extra.animate.set_value(-40 * GRADO), run_time=3.5)
        self.decir("Tres ejes de largo 1, en ángulo recto: eso es un marco de referencia.")
        self.wait(1.5)
        self.play(extra.animate.set_value(25 * GRADO), run_time=3)
        self.decir("La flecha es una sola; sus tres números dependen del marco.", YELLOW)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class CoordenadasEnUnaBase(Escena2D):
    """Con ejes unitarios en ángulo recto cada coeficiente es un producto punto; si no, hay que resolver un sistema."""

    def construct(self):
        S = 1.7
        O = LEFT * 4.6 + DOWN * 1.9
        titulo = texto("Escribir una flecha como suma de otras dos", 32).to_edge(UP)
        self.play(Write(titulo))
        P = lambda v: O + S * np.array([v[0], v[1], 0])
        ang = lambda d: np.array([np.cos(d * GRADO), np.sin(d * GRADO)])

        # ejes en ángulo recto
        e1, e2 = ang(-10), ang(80)
        v = 1.5 * ang(0) + 1.2 * ang(55)
        c1, c2 = v @ e1, v @ e2
        f1, f2 = flecha(P([0, 0]), P(e1), CX, 7), flecha(P([0, 0]), P(e2), CY, 7)
        fv = flecha(P([0, 0]), P(v), YELLOW, 7)
        self.play(GrowArrow(f1), GrowArrow(f2), GrowArrow(fv))
        self.decir("Con dos ejes de largo 1 en ángulo recto, la sombra es el coeficiente.")
        s1 = Line(P([0, 0]), P(c1 * e1), color=CX, stroke_width=11)
        s2 = Line(P([0, 0]), P(c2 * e2), color=CY, stroke_width=11)
        d1 = DashedLine(P(v), P(c1 * e1), color=GREY_B)
        d2 = DashedLine(P(v), P(c2 * e2), color=GREY_B)
        self.play(Create(s1), Create(d1), Create(s2), Create(d2), run_time=2)
        p1 = VGroup(texto("ejes en ángulo recto", 24), texto(f"v·e₁ = {num(c1)}", 24, color=CX), texto(f"v·e₂ = {num(c2)}", 24, color=CY),
                    texto(f"{num(c1)} e₁ + {num(c2)} e₂ = v", 24, color=YELLOW))\
            .arrange(DOWN, aligned_edge=LEFT, buff=0.16).move_to(RIGHT * 3.5 + UP * 1.6)
        assert np.allclose(c1 * e1 + c2 * e2, v)
        self.play(FadeIn(p1))
        self.wait(2.5)
        self.play(FadeOut(s1, s2, d1, d2, f1, f2, p1))

        # ejes torcidos
        a, b = ang(0), ang(55)
        s = a @ b
        al, be = 1.5, 1.2
        fa, fb = flecha(P([0, 0]), P(a), CX, 7), flecha(P([0, 0]), P(b), CY, 7)
        la = texto("a", 26, color=CX).next_to(P(a), DOWN, buff=0.12)
        lb = texto("b", 26, color=CY).next_to(P(b), LEFT, buff=0.12)
        self.decir("Ahora dos ejes que no forman ángulo recto: 55° entre ellos.")
        self.play(GrowArrow(fa), GrowArrow(fb), FadeIn(la, lb))
        sombra = Line(P([0, 0]), P((v @ a) * a), color=RED, stroke_width=9)
        caida = DashedLine(P(v), P((v @ a) * a), color=RED)
        self.play(Create(sombra), Create(caida))
        p2 = VGroup(texto(f"sombra sobre a: v·a = {num(v @ a)}", 24, color=RED)).move_to(RIGHT * 3.0 + UP * 2.2)
        self.play(FadeIn(p2))
        self.decir(f"La sombra da {num(v @ a)}, y ese no es el coeficiente de a.", RED)
        self.wait(2)
        pa = Line(P([0, 0]), P(al * a), color=CX, stroke_width=11)
        pb = Line(P(al * a), P(v), color=CY, stroke_width=11)
        self.play(FadeOut(sombra, caida), Create(pa), Create(pb), run_time=2)
        p3 = texto(f"de verdad: v = {num(al, 1)} a + {num(be, 1)} b", 24, color=YELLOW).next_to(p2, DOWN, buff=0.2).align_to(p2, LEFT)
        self.play(FadeIn(p3))
        self.decir("Hay que caminar paralelo a cada eje: una parte de b también cae sobre a.")
        self.wait(2)
        f = MathTex(r"v\cdot a &= \alpha + \beta\,s\\ v\cdot b &= \alpha\,s + \beta\\ \alpha &= \frac{v\cdot a - (v\cdot b)\,s}{1-s^2}",
                    font_size=34).next_to(p3, DOWN, buff=0.3).align_to(p2, LEFT)
        l5 = texto(f"s = a·b = {num(s)}", 24).next_to(f, DOWN, buff=0.2).align_to(p2, LEFT)
        l6 = texto(f"α = ({num(v @ a)} − {num(v @ b)} · {num(s)}) / {num(1 - s * s)} = {num((v @ a - (v @ b) * s) / (1 - s * s))}", 22, color=GREEN)\
            .next_to(l5, DOWN, buff=0.14).align_to(p2, LEFT)
        self.play(Write(f), FadeIn(l5))
        self.decir("Dos ecuaciones, dos incógnitas: un sistema chico, y sale el coeficiente.", GREEN)
        self.play(FadeIn(l6))
        self.wait(3.5)


# ---------------------------------------------------------------------------------------------------------
class CambioDeMarco(Escena3D):
    """Las coordenadas en el mundo de un vector del reloj son productos punto; los nueve números forman una matriz."""

    def construct(self):
        self.set_camera_orientation(phi=66 * DEGREES, theta=-52 * DEGREES, zoom=1.15, frame_center=OUT * 0.55)
        self.titulo("Del reloj al mundo: nueve números")
        self.add(ejes_mundo(2.2))
        R = R_eje([1, 0.6, 0.9], 35 * GRADO)
        X, Y, Z = R[:, 0], R[:, 1], R[:, 2]
        vr = np.array([1.2, 0.5, 1.0])
        vm = R @ vr
        cubo = reloj(0.7, R)
        fe = ejes(R, 1.5, ORIGIN, 5)
        self.play(FadeIn(cubo), Create(fe))
        lr = texto(f"en el reloj: {terna(vr, 1)}", 26, color=YELLOW).to_corner(UL).shift(DOWN * 0.8)
        self.add_fixed_in_frame_mobjects(lr)
        self.decir("Una flecha que el reloj lee como (1.2, 0.5, 1.0). ¿Cuánto vale en el mundo?")
        self.play(FadeIn(lr))
        self.wait(1.5)
        p1, p2 = vr[0] * X, vr[0] * X + vr[1] * Y
        tramos = VGroup(Line(ORIGIN, p1, color=CX, stroke_width=8), Line(p1, p2, color=CY, stroke_width=8), Line(p2, vm, color=CZ, stroke_width=8))
        self.decir("Quiere decir: 1.2 de X, más 0.5 de Y, más 1.0 de Z.")
        for t in tramos:
            self.play(Create(t), run_time=1)
        self.play(GrowArrow(flecha(ORIGIN, vm, YELLOW, 7)))
        celdas = VGroup()
        for i in range(3):
            for j, c in enumerate([CX, CY, CZ]):
                celdas.add(texto(num(R[i, j]).rjust(5), 24, color=c).move_to([j * 1.0, -i * 0.42, 0]))
        heads = VGroup(*[texto(n, 22, color=c).move_to([j * 1.0, 0.46, 0]) for j, (n, c) in enumerate(zip("XYZ", [CX, CY, CZ]))])
        marcoM = VGroup(celdas, heads)
        cajaL = Line(UP * 0.62 + LEFT * 0.55, DOWN * 1.1 + LEFT * 0.55, stroke_width=3)
        cajaR = cajaL.copy().shift(RIGHT * 3.1)
        tabla = VGroup(marcoM, cajaL, cajaR).to_corner(UR).shift(DOWN * 0.85 + LEFT * 0.2)
        self.add_fixed_in_frame_mobjects(tabla)
        self.decir("Cada eje del reloj son tres números del mundo: nueve en total, una matriz.")
        self.play(FadeIn(tabla))
        self.wait(2.5)
        lm = texto(f"en el mundo: {terna(vm)}", 26, color=YELLOW).next_to(lr, DOWN, buff=0.15).align_to(lr, LEFT)
        self.add_fixed_in_frame_mobjects(lm)
        self.play(FadeIn(lm))
        fila = SurroundingRectangle(VGroup(*celdas[0:3]), color=WHITE, buff=0.07)
        self.add_fixed_in_frame_mobjects(fila)
        par = lambda x: num(x, 3) if x >= 0 else f"({num(x, 3)})"
        l0 = texto(f"{par(R[0, 0])}·1.2 + {par(R[0, 1])}·0.5 + {par(R[0, 2])}·1.0 = {num(vm[0])}", 24).to_edge(DOWN, buff=1.15)
        self.add_fixed_in_frame_mobjects(l0)
        self.decir("Cada número del mundo es un producto punto: una fila por la flecha.")
        self.play(Create(fila), FadeIn(l0))
        self.wait(3)
        l1 = texto(f"v·X = {num(vm @ X)}   v·Y = {num(vm @ Y)}   v·Z = {num(vm @ Z)}", 24, color=GREEN).to_edge(DOWN, buff=0.78)
        self.add_fixed_in_frame_mobjects(l1)
        self.decir("Y de vuelta, del mundo al reloj: productos punto con X, Y y Z.", GREEN)
        self.play(FadeOut(fila), FadeIn(l1))
        self.wait(3.5)


# ---------------------------------------------------------------------------------------------------------
class SeisCaras(Escena3D):
    """El reloj quieto en seis posturas: los números de la gravedad cambian, su largo no."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-50 * DEGREES, zoom=0.95)
        self.titulo("Seis caras hacia arriba")
        arriba = np.array([0, 0, 1.0])
        estado = {"R": np.eye(3), "eje": np.array([1.0, 0, 0])}
        a = ValueTracker(0)
        R = lambda: R_eje(estado["eje"], a.get_value()) @ estado["R"]
        cubo = always_redraw(lambda: reloj(1.1, R()).shift(LEFT * 2.6))
        fl = always_redraw(lambda: ejes(R(), 1.5, LEFT * 2.6, 5))
        g = flecha(LEFT * 2.6, LEFT * 2.6 + 2.3 * arriba, YELLOW, 8)
        self.add(cubo, fl, g)
        self.rotulos(("arriba", LEFT * 2.6 + 2.6 * arriba, YELLOW))
        cabeza = texto("lectura (m/s²)          largo    ángulo con la anterior", 20).to_corner(UR).shift(DOWN * 0.85 + LEFT * 0.1)
        self.add_fixed_in_frame_mobjects(cabeza)
        self.play(FadeIn(cabeza))
        self.decir("Lo que lee la gravedad en cada postura, y el ángulo entre posturas seguidas.")
        filas = VGroup()
        anterior = None

        def anotar():
            nonlocal anterior
            lee = (R().T @ (G * arriba)).round(10) + 0.0
            n = np.linalg.norm(lee)
            ang = "" if anterior is None else f"{np.degrees(np.arctan2(np.linalg.norm(np.cross(anterior, lee)), anterior @ lee)):.0f}°"
            fila = VGroup(texto(terna(lee), 22, color=BLUE_B), texto(f"{n:.2f}", 22), texto(ang, 22, color=GREEN))
            fila[0].move_to(cabeza.get_left() + RIGHT * 1.42 + DOWN * (0.42 + 0.38 * len(filas)))
            fila[1].move_to(cabeza.get_left() + RIGHT * 3.28 + DOWN * (0.42 + 0.38 * len(filas)))
            fila[2].move_to(cabeza.get_left() + RIGHT * 4.75 + DOWN * (0.42 + 0.38 * len(filas)))
            self.add_fixed_in_frame_mobjects(fila)
            self.play(FadeIn(fila), run_time=0.4)
            filas.add(fila)
            anterior = lee

        def girar(eje, ang, nota=True):
            nonlocal anterior
            estado["eje"] = np.array(eje, float)
            a.set_value(0)
            self.play(a.animate.set_value(ang), run_time=1.6)
            estado["R"] = R_eje(eje, ang) @ estado["R"]
            a.set_value(0)
            if nota:
                anotar()
            else:
                anterior = (R().T @ (G * arriba)).round(10) + 0.0

        anotar()
        for _ in range(3):
            girar([1, 0, 0], PI / 2)
        girar([1, 0, 0], PI / 2, nota=False)  # vuelve a la primera cara, para seguir hacia las otras dos
        girar([0, 1, 0], PI / 2)
        girar([0, 1, 0], PI)
        self.decir("Los números cambian, pero el largo es siempre 9.81: 90° entre vecinas y 180° entre opuestas.", YELLOW, 22)
        self.wait(3.5)
