"""Animaciones del capítulo 1 (Qué es un sensor), una por concepto.

    python docs/curso/animaciones/render.py cap01 EjesDelReloj Acelerometro ...   # a GIF en docs/curso/media/cap01/
    python -m manim -ql docs/curso/animaciones/cap01.py Ruido                     # una, rápido, para mirarla

Lo que no se inventa: el ruido, el sesgo y las lecturas con movimiento salen de synth (server/web/mocapmath.js), que
datos_cap01.js corre con node, y el reposo y el sesgo los decide Motion de tools/air_mouse.py, importado tal cual, con
una grabación inventada. Lo que las escenas afirman lo comprueba tools/test_sensor.js.
"""
import json
import math
import os
import random
import subprocess
import sys

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "..", "tools"))
from air_mouse import G0, STILL_DEG, Motion, make_config     # noqa: E402  los de verdad

D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap01.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)
CX, CY, CZ = RED, GREEN, BLUE          # los ejes del reloj, como en el capítulo 5
G = 9.81                               # la de mocapmath.js
EXTRA = np.array(D["extra"])           # lo que synth le suma a la verdad del giroscopio: sesgo + ruido, por eje
MEDIDA, GRAV, MALO, BIEN, SUAVE = YELLOW, GREEN, RED, GREEN, GREY_B
MONO = "Consolas"


# ---------- dibujo ----------
def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


def lecturas(filas, size=24, color=WHITE, dec=2, col=None, horizontal=False, buff=0.16):
    """Etiquetas fijas con números que cambian. Cada Text nuevo tarda casi un segundo, así que lo que cambia en cada
    cuadro va en un DecimalNumber. filas: (etiqueta, función, decimales, color)."""
    g = VGroup()
    for nom, f, *resto in filas:
        d = resto[0] if resto else dec
        c = resto[1] if len(resto) > 1 else color
        e = texto(nom, size, color=c)
        n = DecimalNumber(f(), num_decimal_places=d, font_size=size * 1.7, color=c)

        def poner(m, e=e, f=f):
            m.set_value(f())
            if col is None:
                m.next_to(e, RIGHT, buff=0.14)
            else:
                m.move_to(e.get_left() + RIGHT * col, aligned_edge=LEFT)

        poner(n)
        n.add_updater(poner)
        g.add(VGroup(e, n))
    return g.arrange(RIGHT if horizontal else DOWN, aligned_edge=UP if horizontal else LEFT, buff=buff)


def ejes(x, y, ancho=9.5, alto=3.6, numeros=True, **kw):
    return Axes(x_range=x, y_range=y, x_length=ancho, y_length=alto, tips=False,
                axis_config={"include_numbers": numeros, "font_size": 18}, **kw)


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


def rotulo(s, color=WHITE, size=24):
    nuevo = texto(s, size, color=color)
    if nuevo.width > 13.2:                                    # en dos líneas, cortando cerca de la mitad
        corte = min((i for i, c in enumerate(s) if c == " "), key=lambda i: abs(i - len(s) / 2))
        nuevo = VGroup(texto(s[:corte], size - 1, color=color), texto(s[corte + 1:], size - 1, color=color)).arrange(DOWN, buff=0.1)
    return nuevo.to_edge(DOWN, buff=0.14)


class Escena(Scene):
    def titulo(self, s, size=34):
        t = texto(s, size).to_edge(UP, buff=0.3)
        self.play(Write(t), run_time=0.8)
        return t

    def decir(self, s, color=WHITE, size=24, espera=2.5):
        nuevo = rotulo(s, color, size)
        viejo = getattr(self, "letrero", None)
        self.play(*([FadeOut(viejo)] if viejo is not None else []), FadeIn(nuevo), run_time=0.5)
        self.letrero = nuevo
        if espera:
            self.wait(espera)


class Escena3D(ThreeDScene):
    def decir(self, s, color=WHITE, size=24, espera=2.0):
        nuevo = rotulo(s, color, size)
        self.add_fixed_in_frame_mobjects(nuevo)
        viejo = getattr(self, "letrero", None)
        self.play(*([FadeOut(viejo)] if viejo is not None else []), FadeIn(nuevo), run_time=0.5)
        self.letrero = nuevo
        if espera:
            self.wait(espera)

    def fijo(self, func):
        """Algo fijo en la pantalla que se rehace en cada cuadro (las cifras, por ejemplo)."""
        m = func()
        self.add_fixed_in_frame_mobjects(m)
        m.add_updater(lambda mm: (mm.become(func()), self.renderer.camera.add_fixed_in_frame_mobjects(mm)))
        return m

    def titulo(self, s, size=32):
        t = texto(s, size).to_edge(UP, buff=0.3)
        self.add_fixed_in_frame_mobjects(t)
        self.play(Write(t), run_time=0.8)
        return t


def flecha(a, b, color, w=6):
    return Arrow(np.asarray(a, float), np.asarray(b, float), buff=0, color=color, stroke_width=w,
                 max_tip_length_to_length_ratio=0.18)


def reloj(R=np.eye(3), escala=1.0, largo=2.1, con_ejes=True):
    """El reloj de costado: caja con pantalla azul, correa a lo largo de y y botones del lado +x."""
    caja = Prism(dimensions=[1.5, 1.5, 0.32], fill_opacity=1, fill_color=GREY_D, stroke_width=1, stroke_color=GREY_B)
    caja[1].set_fill(BLUE_D)
    correa = VGroup(*[Prism(dimensions=[0.95, 1.1, 0.1], fill_opacity=1, fill_color=GREY_E, stroke_width=0.5, stroke_color=GREY_C)
                      .shift(UP * s * 1.3 + IN * 0.05) for s in (1, -1)])
    boton = VGroup(*[Prism(dimensions=[0.14, 0.2, 0.14], fill_opacity=1, fill_color=RED_D, stroke_width=0).shift(RIGHT * 0.8 + UP * s)
                     for s in (0.3, -0.3)])
    g = VGroup(correa, caja, boton)
    if con_ejes:
        g.add(*[flecha(ORIGIN, largo * e, c) for e, c in ((RIGHT, CX), (UP, CY), (OUT, CZ))])
    g.scale(escala, about_point=ORIGIN)
    g.apply_matrix(R, about_point=ORIGIN)
    return g


def Rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def Rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def tasa(Rp, Rn, dt):
    """Lo que leería el giroscopio entre dos orientaciones: la cuenta de synth en mocapmath.js, en °/s."""
    r = Rp.T @ Rn
    ang = math.acos(max(-1, min(1, (np.trace(r) - 1) / 2)))
    if ang < 1e-9:
        return np.zeros(3)
    return np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]) * ang / (2 * math.sin(ang)) / (2 * dt) * 180 / math.pi


class Barras(VGroup):
    """Tres barras horizontales que salen de un cero central, con su número. Lo fijo se dibuja una sola vez."""

    def __init__(self, valores, tope, unidad, dec=1, ancho=3.2, alto=0.34, centro=ORIGIN):
        super().__init__()
        self.tope, self.ancho, self.alto, self.valores = tope, ancho, alto, valores
        self.llenos, self.numeros = VGroup(), VGroup()
        for i, (nombre, c) in enumerate(zip("xyz", (CX, CY, CZ))):
            y = (1 - i) * 0.68
            caja = Rectangle(width=ancho, height=alto, stroke_width=1, stroke_color=SUAVE).move_to(UP * y)
            lleno = Rectangle(width=0.01, height=alto - 0.06, stroke_width=0, fill_color=c, fill_opacity=0.9).move_to(UP * y)
            cero = Line(UP * (y + alto / 2), UP * (y - alto / 2), color=WHITE, stroke_width=2)
            n = texto(nombre, 24, color=c).next_to(caja, LEFT, buff=0.15)
            d = DecimalNumber(0, num_decimal_places=dec, font_size=36, include_sign=True).next_to(caja, RIGHT, buff=0.15)
            u = texto(unidad, 20, color=SUAVE).move_to(caja.get_right() + RIGHT * (1.2 + 0.18 * dec) + DOWN * 0.0, aligned_edge=LEFT)
            self.llenos.add(lleno)
            self.numeros.add(d)
            self.add(caja, lleno, cero, n, d, u)
        self.move_to(centro)
        self.add_updater(lambda m: m.poner())
        self.poner()

    def poner(self):
        for i, v in enumerate(self.valores()):
            b, d = self.llenos[i], self.numeros[i]
            largo = max(0.01, min(1, abs(v) / self.tope)) * self.ancho / 2
            cero_x = self.get_cero_x()
            b.stretch_to_fit_width(largo).move_to([cero_x + (largo / 2 if v >= 0 else -largo / 2), b.get_center()[1], 0])
            izq = d.get_left()
            d.set_value(v)
            d.move_to(izq, aligned_edge=LEFT)

    def get_cero_x(self):
        return self.submobjects[2].get_center()[0]


# ---------------------------------------------------------------------------------------------------------
class EjesDelReloj(Escena3D):
    """Tres direcciones pegadas al reloj, que se mueven con él; en la otra mano x apunta al revés."""

    def construct(self):
        # la cuenta de watchOf: y = z × x; en la izquierda x va a la mano, en la derecha al codo
        for lado, s in (("l", 1), ("r", -1)):
            L = D["lados"][lado]
            assert np.allclose(np.cross(L["Z"], L["X"]), L["Y"], atol=1e-9)
            assert abs(np.dot(L["X"], L["F"]) - s) < 1e-9
        self.set_camera_orientation(phi=62 * DEGREES, theta=-62 * DEGREES, zoom=0.95)
        self.titulo("Los ejes del reloj")
        g = reloj()
        etq = VGroup(*[texto(n, 30, color=c) for n, c in zip("xyz", (CX, CY, CZ))])
        puntas = [g[3 + i] for i in range(3)]
        for e, p in zip(etq, puntas):
            e.move_to(p.get_end() * 1.15)
            e.add_updater(lambda m, a=p: m.move_to(a.get_end() * 1.15))
        self.add_fixed_orientation_mobjects(*etq)
        self.play(FadeIn(g), FadeIn(etq))
        self.decir("Tres direcciones pegadas al reloj: x, y, z. Z sale de la pantalla.", espera=2)
        self.decir("Cada sensor da un número por eje, medido en estas direcciones.", espera=1)
        self.play(Rotate(g, 55 * DEGREES, axis=UP, about_point=ORIGIN), run_time=2)
        self.play(Rotate(g, -70 * DEGREES, axis=RIGHT, about_point=ORIGIN), run_time=2)
        self.decir("Si el reloj gira, los ejes giran con él: no son los del cuarto.", espera=1)
        self.play(Rotate(g, 70 * DEGREES, axis=RIGHT, about_point=ORIGIN), run_time=1.5)
        self.play(Rotate(g, -55 * DEGREES, axis=UP, about_point=ORIGIN), run_time=1.5)

        brazo = flecha(LEFT * 4.4 + IN * 0.7, RIGHT * 4.2 + IN * 0.7, ORANGE, 12)
        mano = texto("mano", 26, color=ORANGE).move_to(RIGHT * 4.75 + IN * 0.7)
        codo = texto("codo", 26, color=ORANGE).move_to(LEFT * 4.95 + IN * 0.7)
        self.add_fixed_orientation_mobjects(mano, codo)
        self.play(FadeIn(brazo), FadeIn(mano, codo))
        self.decir("En la mano izquierda, x apunta del codo a la mano. Los botones miran a la mano.", espera=2.5)
        self.play(Rotate(g, PI, axis=OUT, about_point=ORIGIN), run_time=2.5)
        self.decir("En la derecha, puesto igual, botones hacia el codo: x e y salen al revés.", espera=2.5)
        self.decir("Z sigue saliendo de la pantalla. Por eso wrist.js pide en qué mano lo llevas.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class Acelerometro(Escena):
    """Mide lo que empuja al reloj: aceleración más gravedad, hacia arriba."""

    def construct(self):
        self.titulo("El acelerómetro: una bolita con resortes")
        a = ValueTracker(0.0)        # m/s², hacia arriba
        th = ValueTracker(0.0)       # cuánto se ladea, en radianes
        alt = ValueTracker(0.0)      # altura de la caja en pantalla
        centro = lambda: LEFT * 3.4 + DOWN * 0.1 + UP * alt.get_value()
        lado = 2.2
        X = lambda: np.array([np.cos(th.get_value()), -np.sin(th.get_value()), 0])
        Z = lambda: np.array([np.sin(th.get_value()), np.cos(th.get_value()), 0])
        f = lambda: (G + a.get_value()) * UP                  # mocapmath.js: f = a + G hacia arriba
        lectura = lambda: np.array([float(np.dot(X(), f())), 0.0, float(np.dot(Z(), f()))])

        def caja():
            c = centro()
            esquinas = [c + (sx * X() + sz * Z()) * lado / 2 for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            lx, _, lz = lectura()
            bola = c - (lx * X() + lz * Z()) * 0.055          # la bolita se queda atrás de lo que la empuja
            resortes = VGroup(*[Line(e, bola, color=SUAVE, stroke_width=2) for e in esquinas])
            return VGroup(Polygon(*esquinas, color=WHITE, stroke_width=4), resortes, Dot(bola, radius=0.16, color=MEDIDA),
                          flecha(c + X() * (lado / 2 + 0.1), c + X() * (lado / 2 + 0.75), CX, 5),
                          flecha(c + Z() * (lado / 2 + 0.1), c + Z() * (lado / 2 + 0.75), CZ, 5))

        dibujo = always_redraw(caja)
        mesa = Line(LEFT * 5.6, LEFT * 1.2, color=SUAVE, stroke_width=6).shift(DOWN * 1.27)
        barras = Barras(lectura, 14, "m/s²", dec=2, centro=RIGHT * 3.0 + UP * 1.3)
        largo = lecturas([("largo de los tres (m/s²):", lambda: float(np.linalg.norm(lectura())), 2, MEDIDA)], 24).move_to(RIGHT * 3.2 + DOWN * 0.25)
        self.play(Create(mesa))
        self.add(dibujo, barras, largo)
        self.decir("Quieto sobre la mesa marca 9.81, no cero. La mesa lo sostiene: la bolita cuelga.", espera=2.5)
        formula = texto("acelerómetro = lo que acelera\n+ g hacia arriba", 24).move_to(RIGHT * 3.2 + DOWN * 1.35)
        self.play(Write(formula))
        self.wait(1.5)

        self.decir("Si lo sueltas, cae con a = −9.81: nada lo sostiene y marca cero.", espera=0.2)
        self.play(FadeOut(mesa), run_time=0.3)
        self.play(a.animate.set_value(-G), run_time=0.15)
        self.play(alt.animate.set_value(-1.1), run_time=0.7, rate_func=rate_functions.ease_in_quad)
        self.wait(1.2)
        self.play(a.animate.set_value(0), alt.animate.set_value(0), FadeIn(mesa), run_time=0.6)
        self.wait(0.4)

        self.decir("Si la mano lo sube con a = +3, marca 12.81: aceleración más gravedad.", espera=0.2)
        self.play(a.animate.set_value(3), run_time=0.3)
        self.play(alt.animate.set_value(1.0), run_time=1.2, rate_func=rate_functions.ease_in_quad)
        self.wait(1.0)
        self.play(a.animate.set_value(0), alt.animate.set_value(0), run_time=0.6)
        self.wait(0.3)

        self.decir("Ladeado, los 9.81 se reparten entre x y z, pero el largo no cambia.", espera=0.2)
        self.play(FadeOut(mesa), run_time=0.3)
        self.play(th.animate.set_value(35 * DEGREES), run_time=2)
        self.wait(1.2)
        self.play(th.animate.set_value(-50 * DEGREES), run_time=2.5)
        self.wait(1.2)
        self.play(th.animate.set_value(0), run_time=1.2)
        f2 = MathTex(r"|a| = \sqrt{x^2 + y^2 + z^2}", font_size=32, color=MEDIDA).move_to(formula)
        self.play(ReplacementTransform(formula, f2))
        self.decir("Con la mano quieta ese largo da unos 9.81, en cualquier posición.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class Giroscopio(Escena3D):
    """Tres números que dicen qué tan rápido gira alrededor de cada eje, no cuánto giró."""

    def construct(self):
        self.set_camera_orientation(phi=62 * DEGREES, theta=-62 * DEGREES, zoom=0.8)
        self.titulo("El giroscopio: qué tan rápido gira")
        dt = 1 / 30
        plan = [(1.0, (0, 0, 0)), (1.0, (0, 0, 90)), (1.8, (0, 0, 0)), (1.0, (-60, 0, 0)), (1.8, (0, 0, 0)),
                (1.0, (0, 45, 45)), (1.5, (0, 0, 0))]
        Rs, marcas = [np.eye(3)], []
        for dur, w in plan:
            for _ in range(int(round(dur / dt))):
                wr = np.radians(w) * dt
                n = np.linalg.norm(wr)
                paso = np.eye(3)
                if n > 0:
                    k = wr / n
                    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
                    paso = np.eye(3) + np.sin(n) * K + (1 - np.cos(n)) * K @ K
                Rs.append(Rs[-1] @ paso)                      # el giro va en los ejes del reloj
            marcas.append(len(Rs) - 1)
        Rs = [Rs[0]] + Rs + [Rs[-1]]
        lects = [tasa(Rs[k - 1], Rs[k + 1], dt) for k in range(1, len(Rs) - 1)]
        assert abs(lects[marcas[1] - 10][2] - 90) < 1e-6 and abs(lects[marcas[3] - 10][0] + 60) < 1e-6
        k = ValueTracker(0)
        idx = lambda: min(len(lects) - 1, int(k.get_value()))
        desplazo = np.array([-1.3, 1.0, 0.0])
        g = always_redraw(lambda: reloj(Rs[idx() + 1], escala=0.95).shift(desplazo))
        self.add(g)
        cifras = Barras(lambda: lects[idx()], 100, "°/s", dec=0, ancho=2.6, centro=RIGHT * 3.7 + UP * 1.0)
        self.add_fixed_in_frame_mobjects(cifras)
        cifras.add_updater(lambda m: self.renderer.camera.add_fixed_in_frame_mobjects(m))
        self.add(cifras)
        self.decir("Quieto, los tres marcan cero (en un giroscopio ideal).", espera=0)

        def correr(hasta, seg):
            self.play(k.animate.set_value(hasta), run_time=seg, rate_func=linear)

        correr(marcas[0], 1.0)
        self.decir("Gira alrededor de z a 90 °/s: solo se mueve la barra z.", espera=0)
        correr(marcas[1], 1.5)
        self.decir("Se detiene: vuelve a cero, aunque quedó girado 90°.", espera=0)
        correr(marcas[2], 2.2)
        self.decir("Alrededor de x, para el otro lado: la barra x, con signo menos.", espera=0)
        correr(marcas[3], 1.5)
        correr(marcas[4], 1.5)
        self.decir("Alrededor de una dirección entre y y z: las dos barras a la vez.", espera=0)
        correr(marcas[5], 1.5)
        correr(marcas[6], 1.5)
        self.decir("Mide qué tan rápido, en °/s. Cuánto giró en total no lo dice.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class SensorDeGravedad(Escena):
    """No es un sensor: es una cuenta de Samsung que dice dónde es arriba."""

    def construct(self):
        self.titulo("El sensor de gravedad no es un sensor")
        acc, grav = np.array(D["acc"]), np.array(D["grav"])
        hz, n = D["hz"], acc.shape[1]
        t = np.arange(n) / hz
        ang = np.degrees(np.arccos(np.clip((acc * grav).sum(0) / np.linalg.norm(acc, axis=0) / np.linalg.norm(grav, axis=0), -1, 1)))
        # el recuadro de arriba: de dónde sale
        cajas = VGroup()
        for i, (nom, c) in enumerate((("acelerómetro", ORANGE), ("giroscopio", BLUE))):
            cajas.add(VGroup(RoundedRectangle(width=2.6, height=0.62, corner_radius=0.1, color=c), texto(nom, 22, color=c)))
            cajas[-1][1].move_to(cajas[-1][0])
        cajas.arrange(DOWN, buff=0.18).move_to(LEFT * 4.7 + UP * 2.1)
        cuenta = VGroup(RoundedRectangle(width=3.4, height=1.1, corner_radius=0.1, color=SUAVE, fill_color=GREY_E, fill_opacity=1),
                        texto("cuenta de Samsung\n(no se puede ver)", 21)).move_to(UP * 2.1)
        cuenta[1].move_to(cuenta[0])
        salida = VGroup(RoundedRectangle(width=2.9, height=0.62, corner_radius=0.1, color=GRAV), texto("«gravedad»: arriba", 21, color=GRAV))\
            .move_to(RIGHT * 4.6 + UP * 2.1)
        salida[1].move_to(salida[0])
        fl = VGroup(*[Arrow(c.get_right(), cuenta.get_left(), buff=0.08, stroke_width=3, max_tip_length_to_length_ratio=0.15) for c in cajas],
                    Arrow(cuenta.get_right(), salida.get_left(), buff=0.08, stroke_width=3, max_tip_length_to_length_ratio=0.15))
        self.play(FadeIn(cajas), run_time=0.6)
        self.decir("Adentro del reloj solo hay dos sensores que midan movimiento.", espera=1.5)
        self.play(GrowArrow(fl[0]), GrowArrow(fl[1]), FadeIn(cuenta))
        self.play(GrowArrow(fl[2]), FadeIn(salida))
        self.decir("La gravedad es una cuenta interna con esos dos. Nos llega como si fuera un sensor.", espera=2.5)

        a1 = ejes([0, 10, 1], [-16, 24, 8], ancho=10, alto=2.1)
        a2 = ejes([0, 10, 1], [0, 60, 20], ancho=10, alto=1.2)
        VGroup(a1, a2).arrange(DOWN, buff=0.3).shift(RIGHT * 1.15 + DOWN * 0.8)
        l1 = texto("eje y\n(m/s²)", 18).next_to(a1, LEFT, buff=0.3)
        l2 = texto("entre los\ndos (°)", 18).next_to(a2, LEFT, buff=0.3)
        assert acc[1].max() < 24 and acc[1].min() > -16 and ang.max() < 60, (acc[1].min(), acc[1].max(), ang.max())
        self.play(Create(a1), Create(a2), FadeIn(l1, l2), run_time=0.8)
        ga = linea(a1, t, acc[1], ORANGE, 2)
        gg = linea(a1, t, grav[1], GRAV, 3)
        self.decir("Con el movimiento de apuntar del mocap: el acelerómetro salta (naranja)...", espera=0)
        self.play(Create(ga), run_time=3, rate_func=linear)
        self.decir("...y la gravedad (verde) solo sigue dónde queda arriba. Apunta hacia ARRIBA.", espera=0)
        self.play(Create(gg), run_time=3, rate_func=linear)
        self.wait(1)
        gd = linea(a2, t, ang, MEDIDA, 2)
        self.decir(f"Abajo, el ángulo entre los dos: mediana {np.median(ang):.1f}°, y hasta {ang.max():.0f}° en un movimiento brusco.", espera=0)
        self.play(Create(gd), run_time=2.5, rate_func=linear)
        self.wait(2.5)
        self.decir("Aquí la gravedad es inventada y perfecta. La del reloj es una estimación, sin auditar.", espera=3)
        self.decir("Por eso solo se le cree con la mano quieta, y si deja de llegar 500 ms, se usa el acelerómetro.", espera=3.5)


# ---------------------------------------------------------------------------------------------------------
class Ruido(Escena):
    """Sin mover nada, dos medidas seguidas no dan lo mismo: se reparten alrededor de un centro."""

    def construct(self):
        self.titulo("Ruido: lo que cambia aunque nada se mueva")
        x = EXTRA[2]
        hz = 100
        n = 240
        a1 = ejes([0, n / hz, 0.4], [-0.8, 1.4, 0.4], ancho=7.6, alto=4.2, numeros=False).shift(LEFT * 2.3 + DOWN * 0.3)
        a1.y_axis.add_numbers(font_size=18)
        e1 = texto(f"giroscopio z (°/s), reloj quieto, {n / hz:.1f} s", 20).next_to(a1, UP, buff=0.12)
        self.play(Create(a1), FadeIn(e1))
        puntos = VGroup()
        self.add(puntos)
        bordes = np.arange(-0.8, 1.41, 0.11)
        base_x = a1.get_right()[0] + 0.5
        escala = 3.2 / 34

        def histo(m):
            c, _ = np.histogram(x[:m], bins=bordes)
            g = VGroup()
            for i, v in enumerate(c):
                y0, y1 = a1.c2p(0, bordes[i])[1], a1.c2p(0, bordes[i + 1])[1]
                if v:
                    g.add(Rectangle(width=v * escala, height=(y1 - y0) * 0.9, stroke_width=0, fill_color=BLUE, fill_opacity=0.85)
                          .move_to([base_x + v * escala / 2, (y0 + y1) / 2, 0]))
            return g

        tope = np.histogram(x[:n], bins=bordes)[0].max()
        escala = 3.2 / tope
        assert x[:n].max() < 1.4 and x[:n].min() > -0.8, (x[:n].min(), x[:n].max())
        e2 = texto("cuántas veces cae cada valor", 20).move_to([base_x + 1.6, e1.get_center()[1], 0])
        self.play(FadeIn(e2), Create(Line([base_x, a1.get_bottom()[1], 0], [base_x, a1.get_top()[1], 0], color=SUAVE)))
        k0 = int(np.argmax(np.abs(np.diff(x[:20]))))           # el par más visible del comienzo
        par = VGroup(*[Dot(a1.c2p(k / hz, x[k]), radius=0.08, color=MEDIDA) for k in (k0, k0 + 1)])
        self.play(FadeIn(par, scale=2))
        self.decir(f"Dos medidas seguidas, sin mover nada: {x[k0]:+.2f} y {x[k0 + 1]:+.2f} °/s.", espera=2.5)
        h = VGroup()
        self.add(h)
        self.decir("Cada medida trae su pizca de azar. A esa parte se le llama ruido.", espera=0)
        for m in range(4, n + 1, 4):
            puntos.add(*[Dot(a1.c2p(k / hz, x[k]), radius=0.035, color=MEDIDA) for k in range(m - 4, m)])
            nuevo = histo(m)
            self.remove(h)
            h = nuevo
            self.add(h)
            self.wait(0.08)
        self.wait(1)
        self.decir("No se puede predecir una medida, pero se amontonan alrededor de un centro.", espera=1)
        c = float(np.median(x[:n]))
        centro = DashedLine(a1.c2p(0, c), [base_x + 3.2, a1.c2p(0, c)[1], 0], color=WHITE, stroke_width=3)
        self.play(Create(centro))
        self.decir(f"El centro de este tramo es {c:+.2f} °/s, y no es cero: de eso se habla más adelante.", espera=3.5)


# ---------------------------------------------------------------------------------------------------------
class TamanoTipico(Escena):
    """RMS: la raíz del promedio de los cuadrados. Restando antes el promedio, la desviación estándar."""

    def construct(self):
        self.titulo("¿Cuánto ruido es mucho? El tamaño típico")
        x = EXTRA[1]
        v = x[:10]
        s = 1.5                                                # unidades de pantalla por °/s
        paso = 1.15
        izq = -6.0
        y0 = 1.7
        assert np.abs(v).max() * s < paso
        cero = Line([izq - 0.2, y0, 0], [izq + paso * 10, y0, 0], color=SUAVE)
        n0 = texto("0", 18).next_to(cero, LEFT, buff=0.1)
        palos = VGroup(*[Line([izq + paso * i + 0.2, y0, 0], [izq + paso * i + 0.2, y0 + s * q, 0], color=BLUE, stroke_width=5) for i, q in enumerate(v)])
        puntos = VGroup(*[Dot([izq + paso * i + 0.2, y0 + s * q, 0], radius=0.05, color=MEDIDA) for i, q in enumerate(v)])
        self.play(Create(cero), FadeIn(n0), Create(palos), FadeIn(puntos))
        self.decir("Diez muestras en °/s. Promediarlas no dice cuánto van y vienen.", espera=2)

        def cuadros(w):
            return VGroup(*[Square(side_length=abs(s * q), stroke_width=1, stroke_color=WHITE, fill_color=BLUE, fill_opacity=0.55)
                            .move_to([izq + paso * i + 0.2, y0 + s * q / 2, 0]) for i, q in enumerate(w)])

        def lado(area_media, color, nombre):
            q = Square(side_length=s * math.sqrt(area_media), stroke_width=3, stroke_color=color, fill_color=color, fill_opacity=0.5)\
                .move_to(RIGHT * 0.3 + DOWN * 1.75)
            et = texto(f"{nombre} = {math.sqrt(area_media):.2f} °/s", 26, color=color).next_to(q, RIGHT, buff=0.35)
            return q, et

        c1 = cuadros(v)
        self.play(ReplacementTransform(palos.copy(), c1), run_time=1.2)
        self.decir("Cada muestra se eleva al cuadrado: el signo se va y lo grande pesa más.", espera=1.5)
        q1, t1 = lado(float(np.mean(v ** 2)), MEDIDA, "RMS")
        self.play(ReplacementTransform(c1.copy(), q1), run_time=1.8)
        self.play(FadeIn(t1))
        f1 = MathTex(r"\mathrm{RMS} = \sqrt{\text{promedio de } x^2}", font_size=32).move_to(LEFT * 4.2 + DOWN * 1.35)
        self.play(Write(f1))
        self.decir("El cuadrado promedio, y luego su lado: es el RMS, la raíz cuadrática media.", espera=2.5)
        self.play(FadeOut(c1))

        m = float(v.mean())
        media = DashedLine([izq - 0.2, y0 + s * m, 0], [izq + paso * 10, y0 + s * m, 0], color=GREEN, stroke_width=3)
        self.play(Create(media))
        self.decir(f"Pero casi todo ese tamaño es el centro, {m:+.2f}: las muestras no van y vienen tanto.", espera=2)
        w = v - m
        palos2 = VGroup(*[Line([izq + paso * i + 0.2, y0, 0], [izq + paso * i + 0.2, y0 + s * q, 0], color=BLUE, stroke_width=5) for i, q in enumerate(w)])
        puntos2 = VGroup(*[Dot([izq + paso * i + 0.2, y0 + s * q, 0], radius=0.05, color=MEDIDA) for i, q in enumerate(w)])
        self.play(Transform(palos, palos2), Transform(puntos, puntos2), media.animate.shift(UP * (-s * m)), run_time=1.5)
        c2 = cuadros(w)
        self.play(FadeIn(c2))
        q2, t2 = lado(float(np.mean(w ** 2)), GREEN, "desviación estándar")
        q2.shift(LEFT * 0.0)
        t2.next_to(t1, DOWN, buff=0.25).align_to(t1, LEFT)
        q2.align_to(q1, DOWN).align_to(q1, LEFT)
        self.play(ReplacementTransform(c2.copy(), q2), FadeIn(t2), run_time=1.5)
        self.play(FadeOut(c2))
        self.decir("Restando antes el promedio, el mismo cuadrado da la desviación estándar: σ.", espera=2.5)
        # con todas las muestras
        rms, med, sd = math.sqrt(np.mean(x ** 2)), x.mean(), x.std()
        f2 = MathTex(rf"\mathrm{{RMS}}^2 = \text{{promedio}}^2 + \sigma^2", font_size=32).next_to(f1, DOWN, buff=0.25)
        self.play(Write(f2))
        assert abs(rms ** 2 - med ** 2 - sd ** 2) < 1e-9
        self.decir(f"Con las {len(x)} muestras: {rms:.2f}² = {abs(med):.2f}² + {sd:.2f}². El ruido se mide con σ.", espera=3)
        pp = [x[:k].max() - x[:k].min() for k in (10, 100, 800)]
        ds = [x[:k].std() for k in (10, 100, 800)]
        self.decir(f"El pico a pico crece si miras más: {pp[0]:.1f}, {pp[1]:.1f}, {pp[2]:.1f} con 10, 100 y 800 muestras. σ: {ds[0]:.2f}, {ds[1]:.2f}, {ds[2]:.2f}.", espera=4)


# ---------------------------------------------------------------------------------------------------------
class Sesgo(Escena):
    """Un zoom: con la mano quieta el giroscopio tiembla alrededor de algo que no es cero."""

    def construct(self):
        self.titulo("Sesgo: un error que no se va")
        hz = 100
        x = EXTRA[1]                                           # sesgo de synth en y: −0.4 °/s
        t = np.arange(len(x)) / hz
        mover = 260 * np.exp(-((t - 0.8) / 0.25) ** 2) - 180 * np.exp(-((t - 2.0) / 0.3) ** 2)
        lectura = x + mover
        quieto = t >= 3.2
        R = ValueTracker(300.0)
        ax = ejes([0, 8, 1], [-1, 1, 1 / 3], ancho=10, alto=3.9, numeros=False).shift(RIGHT * 1.0 + UP * 0.1)
        ax.x_axis.add_numbers(font_size=18)
        marcas = VGroup()
        for f in (-1, -2 / 3, 2 / 3, 1):
            d = DecimalNumber(f * 300, num_decimal_places=1, font_size=20).next_to(ax.c2p(0, f), LEFT, buff=0.15)
            d.add_updater(lambda m, f=f: m.set_value(f * R.get_value()).next_to(ax.c2p(0, f), LEFT, buff=0.15))
            marcas.add(d)
        e = texto("giroscopio y (°/s)", 20).rotate(PI / 2).next_to(ax, LEFT, buff=0.85)
        et = texto("t (s)", 18).next_to(ax.x_axis, RIGHT, buff=0.12)
        cero = texto("0", 18).next_to(ax.c2p(0, 0), LEFT, buff=0.15)
        self.play(Create(ax), FadeIn(e, et, marcas, cero))
        g1 = linea(ax, t[~quieto], lectura[~quieto] / 300, BLUE, 3)
        curva = always_redraw(lambda: linea(ax, t[quieto], x[quieto] / R.get_value(), BLUE, 2))
        self.play(Create(g1), run_time=2)
        self.add(curva)
        self.decir("Un movimiento y luego la mano quieta. A esta escala, quieta es cero.", espera=2)
        self.play(FadeOut(g1), run_time=0.5)
        self.decir("Hagamos zoom: de ±300 a ±1.5 °/s.", espera=0)
        self.play(R.animate.set_value(1.5), run_time=3.5, rate_func=rate_functions.ease_in_out_sine)
        b = float(np.median(x[quieto]))
        centro = Line(ax.c2p(3.2, b / 1.5), ax.c2p(8, b / 1.5), color=MEDIDA, stroke_width=4)
        etq = texto(f"mediana {b:+.2f} °/s", 24, color=MEDIDA).move_to(ax.c2p(1.6, -0.55))
        self.play(Create(centro), FadeIn(etq))
        self.decir("Tiembla, y además alrededor de algo que no es cero: eso es el sesgo.", espera=2.5)
        f = MathTex(r"\text{medida} = \text{verdad} + \text{sesgo} + \text{ruido}", font_size=34).move_to(ax.c2p(4, 0.82))
        self.play(Write(f))
        self.wait(1.5)
        vuelta = 360 / 86164
        self.decir(f"¿Será la Tierra? Da una vuelta al día: {vuelta:.4f} °/s, unas {abs(b) / vuelta:.0f} veces menos.", espera=1)
        tierra = Line(ax.c2p(3.2, vuelta / 1.5), ax.c2p(8, vuelta / 1.5), color=GREEN, stroke_width=4)
        lt = texto("la Tierra", 22, color=GREEN).next_to(ax.c2p(1.7, 0.0), UP, buff=0.1)
        self.play(Create(tierra), FadeIn(lt))
        self.wait(2)
        self.decir("A esta escala la Tierra cae sobre el cero. Y si das vuelta el reloj, cambia de signo;", espera=2.5)
        self.decir("el sesgo no, porque es del sensor y se mueve con él.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class Umbral(Escena):
    """Una línea que separa quieto de movimiento: ni muy baja ni muy alta."""

    def construct(self):
        self.titulo("Umbral: una línea que separa")
        hz = 100
        ruido = (EXTRA - EXTRA.mean(axis=1, keepdims=True))[:, :800]
        t = np.arange(800) / hz
        lento = 7 * np.exp(-((t - 3.2) / 0.8) ** 2) + 3.2 * np.exp(-((t - 6.3) / 0.4) ** 2)
        w = np.abs(ruido + np.array([[1.0], [0.3], [0.2]]) * lento).max(axis=0)   # como feed_gyro: el eje que más marca
        mueve = lento > 0.05                                   # la verdad de esta señal inventada
        ax = ejes([0, 8, 1], [0, 8, 2], ancho=10, alto=3.4).shift(RIGHT * 0.9 + UP * 0.45)
        e = texto("cuánto marca\n(°/s)", 19).next_to(ax, LEFT, buff=0.25)
        assert w.max() < 8
        g = linea(ax, t, w, BLUE, 2)
        self.play(Create(ax), FadeIn(e), Create(g))
        L = ValueTracker(0.4)
        recta = always_redraw(lambda: DashedLine(ax.c2p(0, L.get_value()), ax.c2p(8, L.get_value()), color=MEDIDA, stroke_width=4))
        y_f = ax.get_bottom()[1] - 0.62

        def franja():
            q = w < L.get_value()
            cortes = np.flatnonzero(np.diff(q.astype(int))) + 1
            b = VGroup()
            for i, j in zip([0, *cortes], [*cortes, len(q)]):
                x0, x1 = ax.c2p(t[i], 0)[0], ax.c2p(t[min(j, len(t) - 1)], 0)[0]
                b.add(Rectangle(width=max(0.012, x1 - x0), height=0.3, stroke_width=0, fill_color=BIEN if q[i] else MALO, fill_opacity=0.9)
                      .move_to([(x0 + x1) / 2, y_f, 0]))
            return b

        def malas():
            q = w < L.get_value()
            return 100 * np.mean(~q[~mueve]), 100 * np.mean(q[mueve])

        fr = always_redraw(franja)
        le = lecturas([("línea (°/s):", lambda: L.get_value(), 1), ("quieta que parece moverse (%):", lambda: malas()[0], 0),
                       ("movimiento perdido (%):", lambda: malas()[1], 0)], 19, MEDIDA, horizontal=True, buff=0.65).next_to(ax, UP, buff=0.12).set_x(0)
        ef = VGroup(texto("quieto", 18, color=BIEN), texto("movimiento", 18, color=MALO)).arrange(DOWN, buff=0.03).next_to([ax.get_left()[0], y_f, 0], LEFT, buff=0.25)
        self.add(recta, fr, le)
        self.play(FadeIn(ef))
        self.decir("Quieta nunca da cero. Se traza una línea: por debajo cuenta como quieto.", espera=2.5)
        self.decir("Muy baja: el ruido la cruza todo el rato y la mano quieta parece moverse.", espera=2)
        self.play(L.animate.set_value(6), run_time=3.5)
        self.decir("Muy alta: un movimiento lento pasa por quieto.", espera=2.5)
        self.play(L.animate.set_value(STILL_DEG), run_time=2.5)
        self.decir(f"Motion.feed_gyro usa {STILL_DEG} °/s en cada eje, y pide 50 muestras seguidas por debajo.", espera=3.5)
        self.decir("El número no sale de una fórmula: se elige mirando el ruido y lo que quieres detectar.", espera=3.5)


# ---------------------------------------------------------------------------------------------------------
def grabacion(segundos, gyro, acel=None, grav=None, hz=100, semilla=7):
    """Corre una grabación inventada por el Motion de verdad; devuelve la historia de lo que decidió."""
    cfg = make_config()
    m = Motion(cfg)
    r = random.Random(semilla)
    hist = []
    for k in range(int(segundos * hz)):
        s = k / hz
        t = 1000.0 + k * 1000 / hz
        gv = grav(s) if grav else (0.0, 0.0, G)
        av = acel(s, r) if acel else (r.gauss(0, 0.03), r.gauss(0, 0.03), G + r.gauss(0, 0.03))
        w = gyro(s, r)
        m.feed_gravity(t, *gv)
        m.feed_accel(t, *av)
        ya = m.calibrated
        m.feed_gyro(t, *w)
        fila = {"s": s, "w": w, "bias": list(m.bias), "listo": m.calibrated}
        if k % 10 == 9:
            fila["ventana"] = m._rest_window(t) if not ya else None
            if m.calib_acc:
                fila["a"] = max(abs(a - G0) for _, a, _ in m.calib_acc)
                fila["j"] = max(j for _, _, j in m.calib_acc)
            if len(m.calib_gdir) >= 2:
                fila["g"] = max(max(c) - min(c) for c in list(zip(*[q[1:] for q in m.calib_gdir])))
        hist.append(fila)
    return m, hist


class AprenderSesgo(Escena):
    """El reposo lo decide Motion._rest_window; la mediana de ese segundo es el sesgo y después se sigue de a poco."""

    def construct(self):
        self.titulo("Aprender el sesgo cuando la mano descansa")
        b = (0.41, -0.27, 0.12)

        def giro(s, r):
            mov = 5 * math.sin(2 * math.pi * 0.9 * s) if s < 2.2 else 4.0 if s < 3.8 else 0.0     # se mueve, gira parejo, descansa
            return (b[0] + mov + r.gauss(0, 0.25), b[1] + r.gauss(0, 0.25), b[2] + r.gauss(0, 0.25))

        def acel(s, r):
            e = 0.5 * math.sin(2 * math.pi * 0.9 * s) if s < 2.2 else 0.0
            return (r.gauss(0, 0.03), r.gauss(0, 0.03), G + e + r.gauss(0, 0.03))

        m, hist = grabacion(7.0, giro, acel)
        cfg = m.cfg
        ts = np.array([h["s"] for h in hist])
        wx = np.array([h["w"][0] for h in hist])
        ax = ejes([0, 7, 1], [-6, 6, 2], ancho=7.4, alto=3.6).shift(LEFT * 2.5 + DOWN * 0.35)
        e = texto("giroscopio x (°/s), t en s", 20).next_to(ax, UP, buff=0.1)
        self.play(Create(ax), FadeIn(e))
        g = linea(ax, ts, wx, BLUE, 2)
        self.play(Create(g), run_time=2)
        self.decir("Una grabación inventada: la mano se mueve, gira parejo y descansa.", espera=1.5)
        self.decir("Cada 10 muestras, Motion._rest_window mira el último segundo.", espera=0.5)

        pruebas = [("pico a pico", "p", f"< {cfg.calib_p2p}"), ("|mediana|", "m", f"< {cfg.bias_max}"), ("|largo − g|", "a", "< 1"),
                   ("sacudida", "j", "< 0.6"), ("gravedad", "g", "< 0.05")]

        ahora = {"f": None}
        lim = {"p": cfg.calib_p2p, "m": cfg.bias_max, "a": 1.0, "j": 0.6, "g": 0.05}

        def valor(k):
            f = ahora["f"]
            if f is None:
                return None
            _, p2p, med = f["ventana"]
            return {"p": p2p, "m": max(abs(q) for q in med) if med else None, "a": f.get("a"), "j": f.get("j"), "g": f.get("g")}[k]

        filas = VGroup()
        for i, (nom, k, txt) in enumerate(pruebas):
            nombre = texto(nom, 22).move_to(RIGHT * 2.9 + UP * (1.35 - 0.48 * i), aligned_edge=LEFT)
            n = DecimalNumber(0, num_decimal_places=2, font_size=36).move_to(RIGHT * 4.9 + UP * (1.35 - 0.48 * i), aligned_edge=LEFT)
            l = texto(txt, 20, color=SUAVE).move_to(RIGHT * 5.85 + UP * (1.35 - 0.48 * i), aligned_edge=LEFT)

            def poner(m, k=k, nombre=nombre):
                v = valor(k)
                c = BIEN if v is not None and v < lim[k] else MALO
                if v is not None:
                    izq = m.get_left()
                    m.set_value(v).move_to(izq, aligned_edge=LEFT)
                m.set_color(c)
                nombre.set_color(c)

            n.add_updater(poner)
            filas.add(VGroup(nombre, n, l))
        veredictos = {}

        def letrero(v):
            if v not in veredictos:
                veredictos[v] = texto(f"«{v}»", 26, color=BIEN if v == "ok" else MALO).move_to(RIGHT * 4.6 + DOWN * 1.25)
            return veredictos[v]

        ventanas = [h for h in hist if h.get("ventana")]
        actual = VGroup()
        marco_v = VGroup()
        self.add(filas, actual, marco_v)
        fin = next(i for i, h in enumerate(ventanas) if h["ventana"][0] == "ok")
        for h in ventanas[:fin + 1]:
            self.remove(actual, marco_v)
            s0, s1 = max(0.0, h["s"] - 1), h["s"]
            marco_v = Rectangle(width=ax.c2p(s1, 0)[0] - ax.c2p(s0, 0)[0], height=3.6, stroke_width=2, stroke_color=MEDIDA, fill_color=MEDIDA, fill_opacity=0.14)\
                .move_to(ax.c2p((s0 + s1) / 2, 0))
            ahora["f"] = h
            actual = letrero(h["ventana"][0])
            filas.update(0)
            self.add(actual, marco_v)
            self.wait(0.13)
        ok = ventanas[fin]
        sesgo = ok["ventana"][2]
        self.wait(1)
        rl = Line(ax.c2p(ok["s"] - 1, sesgo[0]), ax.c2p(ok["s"], sesgo[0]), color=MEDIDA, stroke_width=5)
        self.play(Create(rl))
        self.decir(f"El primer segundo que pasa todo termina en {ok['s'] + 0.01:.2f} s: sesgo x = {sesgo[0]:+.2f} °/s (de verdad, {b[0]:+.2f}).", espera=3)
        self.decir(f"La mediana: en los tres ejes da {sesgo[0]:+.2f}, {sesgo[1]:+.2f}, {sesgo[2]:+.2f}. Motion._calibrate la guarda.", espera=3)
        for fila in filas:
            fila[1].clear_updaters()
        self.play(FadeOut(VGroup(ax, e, g, rl, marco_v, actual, filas)))

        # después se sigue de a poco: el reloj se calienta y el sesgo sube
        verdad = lambda s: 0.4 + 0.3 * (1 - math.exp(-s / 90))
        m2, h2 = grabacion(240.0, lambda s, r: (verdad(s) + r.gauss(0, 0.25), b[1] + r.gauss(0, 0.25), b[2] + r.gauss(0, 0.25)))
        s2 = np.array([h["s"] for h in h2])[::50]
        est = np.array([h["bias"][0] for h in h2])[::50]
        ver = np.array([verdad(s) for s in s2])
        a2 = ejes([0, 240, 60], [0.3, 0.8, 0.1], ancho=9.6, alto=3.7).shift(RIGHT * 0.8 + DOWN * 0.2)
        e2 = texto("sesgo x (°/s)", 20).rotate(PI / 2).next_to(a2, LEFT, buff=0.6)
        et = texto("t (s)", 18).next_to(a2.x_axis, DOWN, buff=0.35).align_to(a2, RIGHT)
        self.play(Create(a2), FadeIn(e2, et))
        gv = linea(a2, s2, ver, WHITE, 3)
        self.decir("El sesgo cambia con la temperatura. Inventemos un reloj que se calienta (blanco).", espera=0)
        self.play(Create(gv), run_time=2)
        self.wait(1.5)
        ge = linea(a2, s2[est > 0], est[est > 0], MEDIDA, 3)
        self.decir(f"Motion.feed_gyro lo sigue mientras la mano esté quieta: un promedio de {cfg.bias_tau:.0f} s.", espera=0)
        self.play(Create(ge), run_time=4, rate_func=linear)
        atras = np.abs(est[est > 0] - ver[est > 0])[len(est) // 4:].max()
        self.wait(1)
        self.decir(f"Va detrás, a lo sumo {atras:.3f} °/s, y no se mueve más de 0.05 °/s por segundo.", espera=3)
        self.decir("No hay que volver a medirlo: cada rato quieto lo corrige solo.", espera=3)
