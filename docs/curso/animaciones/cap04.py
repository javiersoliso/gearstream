"""Animaciones del capítulo 4 (La gravedad dice dónde es arriba), una por concepto.

    python docs/curso/animaciones/render.py cap04                  # todas, a GIF en docs/curso/media/cap04/
    python -m manim -ql docs/curso/animaciones/cap04.py SeisPosturas  # una, rápido, para mirarla

Lo que leen el acelerómetro y la gravedad en la animación de apuntar sale de server/web/mocapmath.js (synth), y la
gravedad en cada postura, de server/web/fusionmath.js (gravedadLeida): datos_cap04.js los corre con node. Lo que las
escenas afirman lo comprueba tools/test_gravedad.js.
"""
import json
import os
import subprocess
import sys

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from cap05 import Escena3D, Rx, Ry, flecha, reloj, texto      # noqa: E402  los mismos relojes y flechas del capítulo 5
from cap08 import m as al_manim, orientacion                  # noqa: E402  la orientación de fusionmath.js

D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap04.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)
G = 9.81
GRAV, ACEL, LINEAL, CX, CY, CZ = BLUE, YELLOW, ORANGE, RED, GREEN, BLUE
GRADO = np.pi / 180


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


def ejes(x, y, ancho=9.5, alto=2.2, **kw):
    return Axes(x_range=x, y_range=y, x_length=ancho, y_length=alto, tips=False,
                axis_config={"include_numbers": True, "font_size": 18}, **kw)


# ---------------------------------------------------------------------------------------------------------
class QueMideElAcelerometro(Scene):
    """Quieto marca 9.81 hacia arriba: siente lo que lo sostiene, no la caída."""

    def construct(self):
        titulo = texto("¿Qué mide el acelerómetro?", 34).to_edge(UP)
        self.play(Write(titulo))
        y0 = ValueTracker(0.0)          # dónde está la caja
        f = ValueTracker(G)             # lo que lee (m/s², positivo hacia arriba)
        x0 = -2.6
        alto = 3.6

        def caja():
            arriba = y0.get_value() + alto / 2
            largo = 0.55 + 0.12 * f.get_value()                 # el resorte se estira con la lectura
            pts = [np.array([x0, arriba, 0])]
            n = 12
            for i in range(1, n):
                pts.append(np.array([x0 + (0.18 if i % 2 else -0.18), arriba - largo * i / n, 0]))
            pts.append(np.array([x0, arriba - largo, 0]))
            return VGroup(Rectangle(width=2.2, height=alto, color=GREY_A).move_to([x0, y0.get_value(), 0]),
                          VMobject(stroke_color=GREY_B, stroke_width=3).set_points_as_corners(pts),
                          Dot(pts[-1], radius=0.22, color=ACEL))

        c = always_redraw(caja)
        barra_y = -2.2
        escala = 0.26
        base = np.array([3.6, barra_y, 0])
        barra = always_redraw(lambda: Rectangle(width=0.8, height=max(0.01, escala * f.get_value()), fill_color=ACEL,
                                                fill_opacity=0.85, stroke_width=0)
                              .move_to(base + UP * escala * f.get_value() / 2))
        cero = Line(base + LEFT * 0.7, base + RIGHT * 0.7, color=GREY_B)
        marca = DashedLine(base + LEFT * 0.7 + UP * escala * G, base + RIGHT * 0.7 + UP * escala * G, stroke_opacity=0.6)
        lm = texto("9.81", 20).next_to(marca, RIGHT, buff=0.1)
        lect = always_redraw(lambda: texto(f"lee {f.get_value():.2f} m/s² hacia arriba", 24, color=ACEL).move_to(RIGHT * 3.6 + UP * 2.2))
        self.play(FadeIn(c, cero, marca, lm, barra, lect))
        rot = {}

        def decir(s, color=WHITE):
            n = texto(s, 24, color=color).to_edge(DOWN, buff=0.2)
            self.play(*([FadeOut(rot["n"])] if rot else []), FadeIn(n), run_time=0.5)
            rot["n"] = n

        decir("Adentro hay una masita colgada de un resorte: lo que mide es cuánto se estira.")
        self.wait(2)
        decir("Quieto en la mesa: el resorte la sostiene. Marca 9.81 hacia arriba.")
        self.wait(2.5)
        decir("Cayendo: nada la sostiene, el resorte se afloja. Marca 0.", ACEL)
        self.play(f.animate.set_value(0), run_time=0.5)
        self.play(y0.animate.set_value(-1.0), run_time=1.2, rate_func=rate_functions.ease_in_quad)
        self.wait(1)
        self.play(y0.animate.set_value(0), f.animate.set_value(G), run_time=1)
        decir("Subiendo con 3 m/s²: el resorte se estira más. Marca 12.81.")
        self.play(f.animate.set_value(G + 3), run_time=0.5)
        self.play(y0.animate.set_value(0.8), run_time=1.5, rate_func=rate_functions.ease_in_quad)
        self.wait(1)
        self.play(y0.animate.set_value(0), f.animate.set_value(G), run_time=1)
        formula = MathTex(r"\text{lectura} = \vec a + \vec g", font_size=38).move_to(RIGHT * 3.6 + UP * 1.5)
        self.play(Write(formula))
        decir("Siente lo que lo sostiene, no la caída: es la fuerza específica.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ArribaSinIntegrar(Scene):
    """Normalizada, la gravedad es la vertical en los ejes del reloj: absoluta, sin integrar nada."""

    def construct(self):
        titulo = texto("La gravedad dice dónde es arriba", 34).to_edge(UP)
        self.play(Write(titulo))
        th = ValueTracker(0.0)
        ci, cd = LEFT * 3.4 + DOWN * 0.2, RIGHT * 2.2 + DOWN * 0.2

        def reloj2d(centro, a):
            cuerpo = RoundedRectangle(corner_radius=0.2, width=2.0, height=0.9, color=GREY_A, fill_opacity=0.15)
            ex = flecha(ORIGIN, RIGHT * 1.6, CX, 5)
            ez = flecha(ORIGIN, UP * 1.6, CZ, 5)
            return VGroup(cuerpo, ex, ez).rotate(a, about_point=ORIGIN).shift(centro)

        mundo = always_redraw(lambda: reloj2d(ci, th.get_value()))
        arriba_mundo = flecha(ci + LEFT * 1.9 + DOWN * 1.2, ci + LEFT * 1.9 + UP * 1.2, GRAV, 7)
        la = texto("arriba", 22, color=GRAV).next_to(arriba_mundo, UP, buff=0.1)
        adentro = reloj2d(cd, 0)
        # en los ejes del reloj, arriba es (sen θ, cos θ): con θ > 0 el eje x sube, como en gravedadLeida
        g = lambda: np.array([np.sin(th.get_value()), np.cos(th.get_value()), 0])
        fg = always_redraw(lambda: flecha(cd, cd + 1.9 * g(), GRAV, 7))
        t1 = texto("en el mundo: el reloj se inclina", 22).next_to(ci, UP, buff=1.85)
        t2 = texto("desde el reloj: la gravedad se inclina", 22).next_to(cd, UP, buff=1.85)
        lect = always_redraw(lambda: VGroup(
            texto(f"g_x = {G * g()[0]:+.2f}", 24, color=CX), texto(f"g_z = {G * g()[1]:+.2f}", 24, color=CZ),
            texto(f"|g| = {G * np.linalg.norm(g()):.2f}", 24)).arrange(DOWN, aligned_edge=LEFT, buff=0.15).move_to(RIGHT * 5.6 + DOWN * 0.2))
        self.play(FadeIn(mundo, adentro, t1, t2, la), GrowArrow(arriba_mundo), Create(fg))
        self.add(lect)
        f = MathTex(r"\hat g = \frac{\vec g}{|\vec g|}", font_size=36).to_edge(DOWN, buff=0.75).shift(LEFT * 0.2)
        n = texto("Dividida por su largo, es la dirección de arriba en los ejes del reloj.", 24).to_edge(DOWN, buff=0.2)
        self.play(th.animate.set_value(40 * GRADO), run_time=2.5)
        self.play(Write(f), FadeIn(n))
        self.play(th.animate.set_value(-30 * GRADO), run_time=2.5)
        self.play(th.animate.set_value(20 * GRADO), run_time=2)
        self.wait(1)
        self.remove(lect)
        self.play(*[FadeOut(x) for x in [mundo, adentro, t1, t2, la, arriba_mundo, fg, f, n]])

        # 60 s con el reloj quieto a 20°: sumar el giroscopio se va, la gravedad no
        rng = np.random.default_rng(4)
        hz = 50
        t = np.arange(0, 60, 1 / hz)
        giro = 20 + np.cumsum(0.3 + rng.normal(0, 0.3, len(t))) / hz
        grav = 20 + rng.normal(0, 0.15, len(t))
        ax = ejes([0, 60, 10], [0, 50, 10], alto=3.8).next_to(titulo, DOWN, buff=0.7)
        yl = texto("ángulo calculado (°)", 20).next_to(ax.y_axis, UP, buff=0.1).shift(RIGHT * 1.1)
        xl = texto("s", 18).next_to(ax.x_axis, RIGHT, buff=0.1)
        self.play(Create(ax), FadeIn(yl, xl))
        v = DashedLine(ax.c2p(0, 20), ax.c2p(60, 20), stroke_opacity=0.6)
        lv = texto("el reloj quieto, a 20°", 20).move_to(ax.c2p(14, 13))
        self.play(Create(v), FadeIn(lv))
        lg = texto(f"el giroscopio sumado, con un sesgo de 0.3 °/s: {giro[-1]:.0f}°", 22, color=ERROR_C).move_to(ax.c2p(26, 46))
        self.play(Create(linea(ax, t[::5], giro[::5], ERROR_C, 3)), FadeIn(lg), run_time=2.5)
        lr = texto("la gravedad: no se va, porque no acumula nada", 22, color=GRAV).move_to(ax.c2p(40, 8))
        self.play(Create(linea(ax, t[::5], grav[::5], GRAV, 3)), FadeIn(lr), run_time=2.5)
        moral = texto("Con la mano quieta, cada lectura vale por sí sola: nada se acumula.", 24).to_edge(DOWN, buff=0.2)
        self.play(FadeIn(moral))
        self.wait(3)


ERROR_C = RED


# ---------------------------------------------------------------------------------------------------------
class SeisPosturas(Escena3D):
    """La inclinación: el ángulo entre un eje del reloj y la vertical, en las seis posturas."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-55 * DEGREES, zoom=0.9)
        self.titulo("La inclinación, en seis posturas")
        a, b = ValueTracker(0.0), ValueTracker(0.0)
        R = lambda: Rx(b.get_value()) @ Ry(a.get_value())
        cubo = always_redraw(lambda: reloj(1.2, R()))
        lados = always_redraw(lambda: VGroup(*[flecha(ORIGIN, 1.5 * R()[:, i], c, 5) for i, c in enumerate([CX, CY, CZ])]))
        arriba = flecha(np.array([-2.8, 1.6, -1.2]), np.array([-2.8, 1.6, 1.2]), GRAV, 7)
        la = texto("arriba", 22, color=GRAV).move_to(np.array([-2.8, 1.6, 1.55]))
        self.add_fixed_orientation_mobjects(la)
        self.play(FadeIn(cubo), Create(lados), Create(arriba), FadeIn(la))

        def tabla():
            g = R().T @ np.array([0, 0, G])
            ang = np.degrees(np.arccos(np.clip(g[2] / G, -1, 1)))
            filas = [texto(f"{n}  {v:+.2f}", 24, color=c) for n, v, c in zip("xyz", g, [CX, CY, CZ])]
            return VGroup(texto("la gravedad que lee (m/s²)", 20), *filas,
                          texto(f"inclinación de z: {ang:.0f}°", 24, color=YELLOW))\
                .arrange(DOWN, aligned_edge=LEFT, buff=0.14).to_corner(UR).shift(DOWN * 0.9)

        self.fijo(tabla)
        f = MathTex(r"\text{inclinación} = \arccos(\hat g \cdot \text{eje})", font_size=34).to_corner(UL).shift(DOWN * 0.9)
        self.add_fixed_in_frame_mobjects(f)
        self.play(Write(f))
        self.decir("z arriba: toda la gravedad cae en z. Inclinación 0°.")
        self.wait(1.5)
        self.decir("x arriba: ahora toda cae en x. z queda acostado: 90°.")
        self.play(a.animate.set_value(-PI / 2), run_time=2)
        self.wait(1)
        self.decir("Boca abajo: z marca −9.81. Inclinación 180°.")
        self.play(a.animate.set_value(-PI), run_time=2)
        self.wait(1)
        self.decir("x abajo: otra vez 90°.")
        self.play(a.animate.set_value(-1.5 * PI), run_time=2)
        self.wait(1)
        self.play(a.animate.set_value(-2 * PI), run_time=1.5)
        self.decir("y arriba: 90°.")
        self.play(b.animate.set_value(PI / 2), run_time=2)
        self.wait(1)
        self.decir("y abajo: 90°. Seis posturas, y ninguna necesitó integrar nada.")
        self.play(b.animate.set_value(-PI / 2), run_time=3)
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
class InclinacionConSigno(Scene):
    """El producto punto da un ángulo sin signo; atan2 de dos componentes dice para qué lado."""

    def construct(self):
        titulo = texto("arccos no dice para qué lado; atan2 sí", 34).to_edge(UP)
        self.play(Write(titulo))
        phi = ValueTracker(0.0)
        c = LEFT * 4.3 + DOWN * 0.4
        g = lambda: np.array([np.sin(phi.get_value()), np.cos(phi.get_value()), 0])     # (g_y, g_z)
        anillo = Circle(radius=1.7, color=GREY_B, stroke_opacity=0.5).move_to(c)
        ey = flecha(c, c + RIGHT * 1.7, CY, 5)
        ez = flecha(c, c + UP * 1.7, CZ, 5)
        fg = always_redraw(lambda: flecha(c, c + 1.7 * g(), GRAV, 7))
        ly = texto("y", 22, color=CY).next_to(ey, RIGHT, buff=0.08)
        lz = texto("z", 22, color=CZ).next_to(ez, UP, buff=0.08)
        lt = texto("la gravedad en los ejes del reloj\nal girar alrededor del antebrazo", 20).next_to(anillo, DOWN, buff=0.3)
        self.play(Create(anillo), GrowArrow(ey), GrowArrow(ez), FadeIn(ly, lz, lt), Create(fg))
        ax = ejes([-180, 180, 90], [-180, 180, 90], ancho=6.4, alto=4.4).move_to(RIGHT * 2.9 + DOWN * 0.2)
        xl = texto("giro de verdad (°)", 18).next_to(ax, DOWN, buff=0.1)
        self.play(Create(ax), FadeIn(xl))
        ang = np.linspace(-179.5, 179.5, 300)
        rad = np.radians(ang)
        fa = MathTex(r"\arccos(\hat g \cdot z)", font_size=30, color=ORANGE).move_to(ax.c2p(-95, 150))
        fb = MathTex(r"\operatorname{atan2}(g_y, g_z)", font_size=30, color=GREEN).move_to(ax.c2p(95, -150))
        self.play(phi.animate.set_value(-179.5 * GRADO), run_time=1)
        cuenta = ValueTracker(0)
        tr1 = always_redraw(lambda: linea(ax, ang[:max(2, int(cuenta.get_value()))],
                                          np.degrees(np.arccos(np.cos(rad)))[:max(2, int(cuenta.get_value()))], ORANGE, 9))
        tr2 = always_redraw(lambda: linea(ax, ang[:max(2, int(cuenta.get_value()))],
                                          np.degrees(np.arctan2(np.sin(rad), np.cos(rad)))[:max(2, int(cuenta.get_value()))], GREEN, 3))
        phi.add_updater(lambda p: p.set_value(rad[min(299, int(cuenta.get_value()))]))
        self.add(phi, tr1, tr2)
        self.play(FadeIn(fa, fb))
        self.play(cuenta.animate.set_value(299), run_time=6, rate_func=linear)
        phi.clear_updaters()
        n = texto("A la derecha y a la izquierda arccos da lo mismo: el signo solo lo guarda atan2.", 24).to_edge(DOWN, buff=0.2)
        self.play(FadeIn(n))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class AceleracionLineal(Scene):
    """Acelerómetro − gravedad: lo que empuja de verdad, sin el peso."""

    def construct(self):
        titulo = texto("Aceleración lineal: lo que empujas, sin el peso", 32).to_edge(UP)
        self.play(Write(titulo))
        p = ValueTracker(0.0)
        o = LEFT * 4.6 + DOWN * 1.6
        esc = 0.3
        fg = flecha(o, o + UP * G * esc, GRAV, 7)
        fl = always_redraw(lambda: flecha(o + UP * G * esc, o + UP * G * esc + RIGHT * esc * p.get_value(), LINEAL, 7)
                           if p.get_value() > 0.2 else VectorizedPoint(o + UP * G * esc))
        fa = always_redraw(lambda: flecha(o, o + UP * G * esc + RIGHT * esc * p.get_value(), ACEL, 7))
        lg = texto("gravedad", 22, color=GRAV).next_to(fg, LEFT, buff=0.1)
        self.play(GrowArrow(fg), FadeIn(lg), Create(fa))
        self.add(fl)
        lect = always_redraw(lambda: VGroup(
            texto(f"lo que empujas: {p.get_value():.1f} m/s²", 24, color=LINEAL),
            texto(f"el acelerómetro: {np.hypot(G, p.get_value()):.2f} m/s²", 24, color=ACEL),
            texto(f"se inclina {np.degrees(np.arctan2(p.get_value(), G)):.0f}° respecto de arriba", 24))
            .arrange(DOWN, aligned_edge=LEFT, buff=0.18).move_to(RIGHT * 2.8 + UP * 1.2))
        self.add(lect)
        self.play(p.animate.set_value(6), run_time=3)
        f = MathTex(r"\text{aceleración lineal} = \text{acelerómetro} - \text{gravedad}", font_size=34).move_to(RIGHT * 2.8 + DOWN * 0.3)
        self.play(Write(f))
        n = texto("Si tomas el acelerómetro como arriba, mientras empujas te equivocas.", 24).to_edge(DOWN, buff=0.2)
        self.play(FadeIn(n))
        self.wait(2)
        self.remove(lect, fl)
        self.play(*[FadeOut(x) for x in [fg, fa, lg, f, n]])

        t = np.array(D["t"])
        a1 = ejes([0, 10, 2], [0, 20, 5], alto=1.9)
        a2 = ejes([0, 10, 2], [0, 60, 20], alto=1.9)
        VGroup(a1, a2).arrange(DOWN, buff=0.45).next_to(titulo, DOWN, buff=0.35).shift(RIGHT * 1.4)
        l1 = texto("largo (m/s²)", 18).next_to(a1, LEFT, buff=0.25)
        l2 = texto("el acelerómetro se\naparta de arriba (°)", 18).next_to(a2, LEFT, buff=0.25)
        sub = texto("10 s de la animación de apuntar del mocap", 20).next_to(a1, UP, buff=0.05)
        self.play(Create(a1), Create(a2), FadeIn(l1, l2, sub))
        self.play(Create(linea(a1, t, D["grav"], GRAV, 3)), run_time=1)
        self.play(Create(linea(a1, t, D["acc"], ACEL, 2.5)), run_time=2)
        self.play(Create(linea(a2, t, D["desvio"], RED, 3)), run_time=2)
        mx, med = max(D["desvio"]), float(np.median(D["desvio"]))
        n2 = texto(f"La mediana es {med:.1f}°, pero en los movimientos bruscos llega a {mx:.0f}°.", 24).to_edge(DOWN, buff=0.2)
        self.play(FadeIn(n2))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class BrazoColgando(Scene):
    """arriba · antebrazo reconoce el brazo caído: el ratón aéreo se pausa pasados los 60°."""

    def construct(self):
        titulo = texto("¿Cómo sabe el programa que el brazo cuelga?", 32).to_edge(UP)
        self.play(Write(titulo))
        # como AirMouse._pose_gate: a = −(arriba·antebrazo); pausa si a > 0.87 por 300 ms, sigue si a < 0.80 por 300 ms
        dt = 1 / 30
        t = np.arange(0, 12, dt)
        puntos = [0, 1.5, 3.5, 5.5, 6.5, 8, 8.8, 10.5, 12]
        grados = [10, 10, 75, 75, 57, 57, 40, 40, 40]             # bajo la horizontal: lo que hace el brazo
        baja = np.interp(t, puntos, grados)
        a = np.sin(np.radians(baja))
        pausa = np.zeros(len(t), bool)
        alto_desde = bajo_desde = None
        estado = False
        for i, (ti, ai) in enumerate(zip(t, a)):
            if ai > 0.87:
                alto_desde = ti if alto_desde is None else alto_desde
                if ti - alto_desde >= 0.3:
                    estado = True
            else:
                alto_desde = None
            if ai < 0.80:
                bajo_desde = ti if bajo_desde is None else bajo_desde
                if ti - bajo_desde >= 0.3:
                    estado = False
            else:
                bajo_desde = None
            pausa[i] = estado
        k = ValueTracker(0)
        i = lambda: min(len(t) - 1, int(k.get_value()))
        codo = LEFT * 4.6 + UP * 1.3
        L = 2.9
        punta = lambda: codo + L * np.array([np.cos(np.radians(baja[i()])), -np.sin(np.radians(baja[i()])), 0])
        horizontal = DashedLine(codo, codo + RIGHT * 3.2, stroke_opacity=0.5)
        brazo = always_redraw(lambda: Line(codo, punta(), color=GREY_A, stroke_width=12))
        punto = Dot(codo, color=WHITE, radius=0.12)
        arriba = flecha(codo + LEFT * 1.3 + DOWN * 1.0, codo + LEFT * 1.3 + UP * 0.6, GRAV, 6)
        la = texto("arriba", 20, color=GRAV).next_to(arriba, UP, buff=0.08)
        self.play(Create(horizontal), Create(brazo), FadeIn(punto, la), GrowArrow(arriba))
        ax = Axes(x_range=[0, 12, 2], y_range=[0, 1, 0.2], x_length=7.2, y_length=3.6, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18}).move_to(RIGHT * 2.8 + DOWN * 0.1)
        u1 = DashedLine(ax.c2p(0, 0.87), ax.c2p(12, 0.87), color=RED)
        u2 = DashedLine(ax.c2p(0, 0.80), ax.c2p(12, 0.80), color=GREEN)
        l1 = texto("se pausa: 0.87 (60°)", 18, color=RED).next_to(ax.c2p(0.1, 0.87), UR, buff=0.04)
        l2 = texto("sigue: 0.80 (53°)", 18, color=GREEN).next_to(ax.c2p(0.1, 0.80), DR, buff=0.04)
        yl = MathTex(r"a = -\,\hat g \cdot \text{antebrazo}", font_size=30).next_to(ax, UP, buff=0.1)
        self.play(Create(ax), Create(u1), Create(u2), FadeIn(l1, l2), Write(yl))
        pts = [ax.c2p(x, y) for x, y in zip(t, a)]               # una vez, no en cada cuadro
        curva = always_redraw(lambda: VMobject(stroke_color=YELLOW, stroke_width=4).set_points_as_corners(pts[:max(2, i() + 1)]))
        rot = always_redraw(lambda: texto("EN PAUSA: el brazo cuelga" if pausa[i()] else "el cursor se mueve", 28,
                                          color=RED if pausa[i()] else GREEN).move_to(LEFT * 3.7 + DOWN * 2.3))
        lect = always_redraw(lambda: texto(f"{baja[i()]:.0f}° bajo la horizontal", 22).move_to(LEFT * 3.7 + DOWN * 1.75))
        self.add(curva, rot, lect)
        self.play(k.animate.set_value(len(t) - 1), run_time=12, rate_func=linear)
        n = texto("Dos umbrales y 300 ms: entre 53° y 60° se queda como estaba, y no parpadea.", 24).to_edge(DOWN, buff=0.2)
        self.play(FadeIn(n))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class LoQueNoVe(Escena3D):
    """Girar alrededor de la vertical no cambia la gravedad: la gravedad no ve el rumbo."""

    def construct(self):
        self.set_camera_orientation(phi=62 * DEGREES, theta=-60 * DEGREES, zoom=0.9)
        self.titulo("Lo que la gravedad nunca va a decir")
        r = ValueTracker(0.0)
        incl = 30
        R = lambda: np.column_stack([al_manim(c) for c in orientacion(incl, r.get_value(), 0)])
        disco = Circle(radius=2.6, color=GREY_B, fill_opacity=0.1, stroke_opacity=0.6).shift(IN * 0.9)
        marcas = VGroup(*[Line(2.45 * np.array([np.cos(a), np.sin(a), 0]) + IN * 0.9, 2.6 * np.array([np.cos(a), np.sin(a), 0]) + IN * 0.9,
                               color=GREY_B) for a in np.arange(0, 2 * PI, PI / 6)])
        cubo = always_redraw(lambda: reloj(1.1, R()))
        arriba = flecha(np.array([0, 0, 0.7]), np.array([0, 0, 2.5]), GRAV, 7)
        la = texto("arriba", 22, color=GRAV).move_to(np.array([0, 0, 2.8]))
        self.add_fixed_orientation_mobjects(la)
        rumbo = always_redraw(lambda: flecha(IN * 0.9, IN * 0.9 + 2.3 * np.array([*(R()[:2, 0] / np.linalg.norm(R()[:2, 0])), 0]), YELLOW, 7))
        self.play(Create(disco), Create(marcas), FadeIn(cubo), Create(arriba), FadeIn(la), Create(rumbo))

        def tabla():
            g = [c[1] * G for c in orientacion(incl, r.get_value(), 0)]
            return VGroup(texto(f"rumbo {r.get_value() % 360:.0f}°", 26, color=YELLOW), texto("la gravedad que lee (m/s²)", 20),
                          *[texto(f"{n}  {v:+.2f}", 24, color=c) for n, v, c in zip("xyz", g, [CX, CY, CZ])])\
                .arrange(DOWN, aligned_edge=LEFT, buff=0.14).to_corner(UR).shift(DOWN * 0.9)

        self.fijo(tabla)
        self.decir("El rumbo: hacia dónde apunta algo en horizontal, como la aguja de una brújula.", YELLOW)
        self.wait(2)
        self.decir("Gira el reloj alrededor de la vertical, con la misma inclinación...")
        self.play(r.animate.set_value(200), run_time=5, rate_func=linear)
        self.decir("...y las tres cifras no se mueven. La gravedad no ve el rumbo.", GRAV)
        self.play(r.animate.set_value(90), run_time=3)
        self.decir("Una flecha no cambia si giras alrededor de ella.")
        self.play(r.animate.set_value(360), run_time=4, rate_func=linear)
        self.wait(2.5)
