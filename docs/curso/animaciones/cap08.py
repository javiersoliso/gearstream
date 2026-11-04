"""Animaciones del capítulo 8 (Fusión de sensores, y por qué el rumbo se va), una por concepto.

    python docs/curso/animaciones/render.py cap08            # todas, a GIF en docs/curso/media/cap08/
    python -m manim -ql docs/curso/animaciones/cap08.py Resorte   # una, rápido, para mirarla

Los números salen de la misma cuenta que la página fusion.html y sus pruebas: datos_cap08.js corre
server/web/fusionmath.js y mocapmath.js con node y le pasa el JSON a este archivo.
"""
import json
import os
import subprocess

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap08.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)

VERDAD, GIRO, ACEL, FILTRO, ERROR = WHITE, BLUE, YELLOW, GREEN, RED


def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


def flecha(a, b, color, w=7):
    """Una flecha plana en 3D: Arrow3D es una malla y redibujarla en cada cuadro tarda horas."""
    return Arrow(a, b, buff=0, color=color, stroke_width=w, max_tip_length_to_length_ratio=0.15)


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


# ---------------------------------------------------------------------------------------------------------
class DosTestigos(Scene):
    """Fusión de sensores: el giroscopio es bueno en lo rápido y el acelerómetro en lo lento."""

    def construct(self):
        d = D["testigos"]
        t, verdad = np.array(d["t"]), np.array(d["verdad"])
        titulo = texto("Dos testigos que mienten distinto", 34).to_edge(UP)
        ax = Axes(x_range=[0, 60, 10], y_range=[-40, 100, 20], x_length=11.5, y_length=5.2, tips=False,
                  axis_config={"include_numbers": True, "font_size": 20}).next_to(titulo, DOWN, buff=0.35)
        xl = texto("s", 20).next_to(ax.x_axis, RIGHT, buff=0.15)
        yl = texto("ángulo de la mano (°)", 20).next_to(ax.y_axis, UP, buff=0.1).shift(RIGHT * 1.2)
        self.play(Write(titulo), Create(ax), FadeIn(xl, yl))

        def leyenda(s, color, i):
            return texto(s, 22, color=color).move_to(ax.c2p(1, 94 - 11 * i), aligned_edge=LEFT)

        lv = leyenda("lo que hizo tu mano", VERDAD, 0)
        g_v = linea(ax, t, verdad, VERDAD, 3)
        self.play(Create(g_v), FadeIn(lv), run_time=3)

        g_g = linea(ax, t, d["giro"], GIRO, 3)
        lg = leyenda(f"giroscopio sumado: suave, pero se va b·t = {d['b']} °/s × 60 s = 30°", GIRO, 1)
        self.play(Create(g_g), FadeIn(lg), run_time=3)
        gap = DoubleArrow(ax.c2p(59, verdad[-1]), ax.c2p(59, d["giro"][-1]), buff=0, color=GIRO, stroke_width=4,
                          tip_length=0.18)
        self.play(GrowFromCenter(gap))
        self.wait(1)

        g_a = linea(ax, t, d["acel"], ACEL, 2)
        la = leyenda("acelerómetro: no se va, pero salta con cada sacudida", ACEL, 2)
        self.play(Create(g_a), FadeIn(la), run_time=3)
        self.wait(1)

        rms = lambda est: float(np.sqrt(np.mean((np.array(est) - verdad)[250:] ** 2)))
        g_f = linea(ax, t, d["filtro"], FILTRO, 3)
        lf = leyenda(f"juntos (k = 1/s): ni se va ni salta, {rms(d['filtro']):.1f}° de error", FILTRO, 3)
        self.play(g_g.animate.set_stroke(opacity=0.25), g_a.animate.set_stroke(opacity=0.25), FadeOut(gap))
        self.play(Create(g_f), FadeIn(lf), run_time=3)
        moral = texto("El giroscopio es bueno en lo rápido y malo en lo lento; el acelerómetro, al revés.", 22)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeIn(moral))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Resorte(Scene):
    """El filtro complementario: integrar el giroscopio y atar la estimación a la medida con un resorte."""

    def construct(self):
        d = D["resorte"]
        t, b = np.array(d["t"]), d["b"]
        curva = lambda k: np.array(d["curvas"][str(k) if str(k) in d["curvas"] else repr(k)])
        titulo = texto("El filtro complementario: un resorte", 34).to_edge(UP)
        formula = MathTex(r"\theta \leftarrow \theta + \omega\,\Delta t + k\,\Delta t\,(\theta_{\text{medido}} - \theta)",
                          font_size=36).next_to(titulo, DOWN, buff=0.25)
        self.play(Write(titulo))
        self.play(Write(formula))

        # arriba: la mano quieta en 0; la medida se queda ahí y la estimación se corre
        recta = NumberLine(x_range=[-0.25, 2.25, 0.5], length=9, include_numbers=True, font_size=20,
                           decimal_number_config={"num_decimal_places": 1}).shift(UP * 0.55)
        rl = texto("error (°)", 18).next_to(recta, RIGHT, buff=0.2)
        tr = ValueTracker(0)
        k0 = 0.5
        e = lambda: float(np.interp(tr.get_value(), t, curva(k0)))
        med = Dot(recta.n2p(0), color=ACEL, radius=0.11)
        ml = texto("la medida", 20, color=ACEL).next_to(med, DOWN, buff=0.35).shift(LEFT * 0.6)
        est = always_redraw(lambda: Dot(recta.n2p(e()), color=FILTRO, radius=0.11))
        el = always_redraw(lambda: texto("la estimación", 20, color=FILTRO).next_to(recta.n2p(e()), UP, buff=0.75))

        def resorte():
            x0, x1 = recta.n2p(0), recta.n2p(e())
            n = 14
            pts = [x0 + (x1 - x0) * i / n + UP * (0.32 + (0.12 if i % 2 else -0.12) * (0 < i < n)) for i in range(n + 1)]
            return VMobject(stroke_color=GREY_B, stroke_width=3).set_points_as_corners(
                [x0, x0 + UP * 0.32] + pts[1:-1] + [x1 + UP * 0.32, x1])

        muelle = always_redraw(resorte)
        sesgo = always_redraw(lambda: Arrow(recta.n2p(e()) + DOWN * 0.2, recta.n2p(e()) + DOWN * 0.2 + RIGHT * 1.4,
                                            buff=0, color=GIRO, stroke_width=5, max_tip_length_to_length_ratio=0.2))
        sl = always_redraw(lambda: texto("el sesgo b la corre", 18, color=GIRO).next_to(sesgo, DOWN, buff=0.08))
        tira = always_redraw(lambda: Arrow(recta.n2p(e()) + UP * 0.32, recta.n2p(e()) + UP * 0.32 + LEFT * 1.4 * k0 * e() / b,
                                           buff=0, color=ERROR, stroke_width=5, max_tip_length_to_length_ratio=0.2)
                             if e() > 0.02 else VectorizedPoint(recta.n2p(e())))
        self.play(Create(recta), FadeIn(rl, med, ml))
        self.add(muelle, est, el, sesgo, sl, tira)

        # abajo: el error contra el tiempo
        ax = Axes(x_range=[0, 15, 5], y_range=[0, 2.2, 0.5], x_length=9, y_length=2.4, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18}).to_edge(DOWN, buff=0.85)
        axl = texto("s", 18).next_to(ax.x_axis, RIGHT, buff=0.1)
        traza = always_redraw(lambda: ax.plot(lambda x: float(np.interp(x, t, curva(k0))),
                                              x_range=[0, max(0.05, tr.get_value()), 0.05], color=FILTRO, stroke_width=4))
        self.play(Create(ax), FadeIn(axl))
        self.add(traza)
        self.play(tr.animate.set_value(15), run_time=7, rate_func=linear)

        tope = DashedLine(ax.c2p(0, b / k0), ax.c2p(15, b / k0), color=FILTRO, dash_length=0.12)
        topel = MathTex(r"b/k", font_size=30, color=FILTRO).next_to(tope, RIGHT, buff=0.1)
        cuenta = MathTex(r"e' = b - k\,e = 0 \;\Rightarrow\; e = b/k", font_size=36).move_to(formula)
        self.play(Create(tope), Write(topel))
        self.play(ReplacementTransform(formula, cuenta))
        nota = texto("Cuando el resorte tira tanto como el sesgo corre, el error deja de crecer.", 22)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeIn(nota))
        self.wait(1.5)

        otras = VGroup()
        for k, c in [(0.25, BLUE_B), (1, TEAL), (2, GREEN_E)]:
            g = ax.plot(lambda x, k=k: float(np.interp(x, t, curva(k))), x_range=[0, 15, 0.05], color=c, stroke_width=3)
            lt = MathTex(rf"k = {k}", font_size=20, color=c).next_to(ax.c2p(15, b / k), RIGHT, buff=0.1)
            otras.add(g, lt)
        topel_k = MathTex(r"k = 0.5", font_size=20, color=FILTRO).next_to(ax.c2p(15, b / k0), RIGHT, buff=0.1)
        self.play(FadeOut(topel), FadeIn(topel_k), FadeOut(nota))
        self.play(LaggedStart(*[Create(m) for m in otras], lag_ratio=0.3), run_time=3)
        moral = texto("Más rígido, menos error por el sesgo… pero más atado a lo que salte la medida.", 22)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeIn(moral))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Valle(Scene):
    """No hay un k bueno para todo: el error rms contra k tiene forma de valle."""

    def construct(self):
        con, sin = np.array(D["valle"]["con"]), np.array(D["valle"]["sin"])
        titulo = texto("¿Qué tan fuerte tirar? El valle", 34).to_edge(UP)
        ax = Axes(x_range=[-2, 2, 1], y_range=[0, 15, 5], x_length=10, y_length=4.8, tips=False,
                  axis_config={"font_size": 20}, y_axis_config={"include_numbers": True})\
            .next_to(titulo, DOWN, buff=0.5).shift(RIGHT * 0.4)
        marcas = VGroup(*[texto(s, 20).next_to(ax.c2p(i, 0), DOWN, buff=0.15)
                          for i, s in zip(range(-2, 3), ["0.01", "0.1", "1", "10", "100"])])
        xl = texto("k (por segundo), escala logarítmica", 20).next_to(marcas, DOWN, buff=0.15)
        yl = texto("error rms (°)", 20).next_to(ax.y_axis, UP, buff=0.1)
        self.play(Write(titulo), Create(ax), FadeIn(marcas, xl, yl))

        lx = np.log10(con[:, 0])
        g = linea(ax, lx, np.minimum(con[:, 1], 15), ERROR, 4)
        i = ValueTracker(0)
        punto = always_redraw(lambda: Dot(ax.c2p(np.interp(i.get_value(), np.arange(len(lx)), lx),
                                                 np.interp(i.get_value(), np.arange(len(lx)), con[:, 1])), color=ERROR))
        lectura = always_redraw(lambda: texto(
            f"k = {10 ** np.interp(i.get_value(), np.arange(len(lx)), lx):.2f}/s  →  "
            f"{np.interp(i.get_value(), np.arange(len(lx)), con[:, 1]):.2f}° de error", 22)
            .move_to(ax.c2p(0, 13.5)))
        self.add(punto, lectura)
        self.play(Create(g), i.animate.set_value(len(lx) - 1), run_time=6, rate_func=linear)
        self.remove(punto, lectura)

        bk = ax.plot(lambda x: 0.5 / 10 ** x, x_range=[np.log10(0.5 / 15), 0, 0.01], color=GIRO, stroke_width=3)
        bk = DashedVMobject(bk, num_dashes=30)
        izq = texto("k chico: manda el giroscopio\ny el error es b/k", 20, color=GIRO).move_to(ax.c2p(-1.55, 1.6))
        der = texto("k grande: manda el acelerómetro\ny el error salta con él", 20, color=ACEL).move_to(ax.c2p(1.2, 10.5))
        self.play(Create(bk), FadeIn(izq))
        self.play(FadeIn(der))
        j = int(np.argmin(con[:, 1]))
        fondo = Dot(ax.c2p(lx[j], con[j, 1]), color=WHITE, radius=0.09)
        fl = texto(f"el fondo: k ≈ {con[j, 0]:.0f}/s, {con[j, 1]:.1f}°", 20).move_to(ax.c2p(0.05, 3.3))
        self.play(FadeIn(fondo, scale=2), FadeIn(fl))
        self.wait(1.5)

        g2 = linea(ax, np.log10(sin[:, 0]), np.minimum(sin[:, 1], 15), TEAL, 4)
        j2 = int(np.argmin(sin[:, 1]))
        fondo2 = Dot(ax.c2p(np.log10(sin[j2, 0]), sin[j2, 1]), color=TEAL, radius=0.09)
        fl2 = texto(f"sin sacudidas: k ≈ {sin[j2, 0]:.0f}/s, {sin[j2, 1]:.2f}°", 20, color=TEAL)\
            .move_to(ax.c2p(1.5, 1.5))
        self.play(FadeOut(der), Create(g2), run_time=2)
        self.play(FadeIn(fondo2, scale=2), FadeIn(fl2))
        moral = texto("No hay un k bueno para todo: depende de cuánto miente cada testigo.", 24)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeIn(moral))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
# la orientación del reloj, igual que fusionmath.js: R = Ry(rumbo) · Rz(incl) · Rx(torn) · B (y arriba)
def orientacion(incl, rumbo, torn):
    e, h, p = np.radians([incl, rumbo, torn])
    rx = lambda v: np.array([v[0], v[1] * np.cos(p) - v[2] * np.sin(p), v[1] * np.sin(p) + v[2] * np.cos(p)])
    rz = lambda v: np.array([v[0] * np.cos(e) - v[1] * np.sin(e), v[0] * np.sin(e) + v[1] * np.cos(e), v[2]])
    ry = lambda v: np.array([v[0] * np.cos(h) + v[2] * np.sin(h), v[1], -v[0] * np.sin(h) + v[2] * np.cos(h)])
    R = lambda v: ry(rz(rx(np.array(v, float))))
    return [R([1, 0, 0]), R([0, 0, -1]), R([0, 1, 0])]


def leida(incl, rumbo, torn):
    return [c[1] * 9.81 for c in orientacion(incl, rumbo, torn)]


for _k, _a in [("base", (20, 0, 0)), ("rumbo", (20, 70, 0)), ("incl", (50, 0, 0)), ("torn", (20, 0, 40))]:
    assert np.allclose(leida(*_a), D["gravedad"][_k], atol=2e-3), _k     # la misma cuenta que la página


def m(v):
    """De los ejes de fusionmath (y arriba) a los de Manim (z arriba)."""
    return np.array([v[0], -v[2], v[1]])


class GravedadNoVeRumbo(ThreeDScene):
    """Una flecha no cambia si giras alrededor de ella: la gravedad no ve el rumbo."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-50 * DEGREES, zoom=0.9)
        incl, rumbo, torn = ValueTracker(20), ValueTracker(0), ValueTracker(0)
        cols = lambda: orientacion(incl.get_value(), rumbo.get_value(), torn.get_value())
        codo = np.array([-0.3, 0, -0.6])
        L = 2.6
        muneca = lambda: codo + L * m(cols()[0])

        piso = NumberPlane(x_range=[-4, 4, 1], y_range=[-4, 4, 1], background_line_style={"stroke_opacity": 0.25})\
            .shift(IN * 1.6)
        arriba = flecha(np.array([-3.2, 2.2, -1.6]), np.array([-3.2, 2.2, 1.0]), GIRO)
        antebrazo = always_redraw(lambda: Line(codo, muneca(), color=GREY_B, stroke_width=14))
        colores = [RED, GREEN, BLUE]
        ejes = [always_redraw(lambda i=i: flecha(muneca(), muneca() + 0.95 * m(cols()[i]), colores[i], 5)) for i in range(3)]
        self.add(piso)
        self.play(Create(arriba), Create(antebrazo))
        self.play(*[Create(a) for a in ejes])

        titulo = texto("Lo que la gravedad no ve", 34).to_edge(UP)
        al = texto("arriba", 22, color=GIRO).move_to(np.array([-3.2, 2.2, 1.35]))
        tabla = VGroup(texto("el reloj lee (m/s²)", 22))
        nums = []
        for i, (nom, c) in enumerate(zip("xyz", colores)):
            num = DecimalNumber(leida(20, 0, 0)[i], num_decimal_places=2, font_size=30, color=c)
            fila = VGroup(texto(nom, 24, color=c), num).arrange(RIGHT, buff=0.3)
            tabla.add(fila)
            nums.append(num)
        tabla.arrange(DOWN, aligned_edge=LEFT, buff=0.2).to_corner(UR).shift(DOWN * 0.8)
        self.add_fixed_in_frame_mobjects(titulo, tabla)
        self.add_fixed_orientation_mobjects(al)
        self.play(Write(titulo), FadeIn(al, tabla))
        for i, num in enumerate(nums):
            # set_value rehace las cifras: hay que volver a fijarlas en la pantalla, o se van a la escena 3D
            num.add_updater(lambda d, i=i: (d.set_value(leida(incl.get_value(), rumbo.get_value(), torn.get_value())[i]),
                                            self.renderer.camera.add_fixed_in_frame_mobjects(d)))

        rotulo = texto("", 26)
        self.add_fixed_in_frame_mobjects(rotulo)

        def decir(s, color=WHITE):
            nuevo = texto(s, 26, color=color).to_edge(DOWN, buff=0.4)
            self.add_fixed_in_frame_mobjects(nuevo)
            self.play(FadeOut(rotulo), FadeIn(nuevo), run_time=0.6)
            return nuevo

        rotulo = decir("inclinar: las cifras cambian")
        self.play(incl.animate.set_value(55), run_time=2)
        self.play(incl.animate.set_value(20), run_time=1.5)
        rotulo = decir("atornillar: también cambian")
        self.play(torn.animate.set_value(45), run_time=2)
        self.play(torn.animate.set_value(0), run_time=1.5)
        rotulo = decir("girar alrededor de arriba (el rumbo): ¡no cambia nada!", YELLOW)
        self.play(rumbo.animate.set_value(120), run_time=3)
        self.play(rumbo.animate.set_value(-80), run_time=3)
        self.play(rumbo.animate.set_value(0), run_time=1.5)
        rotulo = decir("Una flecha no cambia si giras alrededor de ella: la gravedad no ve el rumbo.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Triad(ThreeDScene):
    """TRIAD: con dos direcciones conocidas (arriba y el antebrazo) se arma la orientación entera."""

    def construct(self):
        self.set_camera_orientation(phi=66 * DEGREES, theta=-40 * DEGREES, zoom=0.95)
        titulo = texto("TRIAD: dos flechas conocidas dan la orientación entera", 30).to_edge(UP)
        self.add_fixed_in_frame_mobjects(titulo)
        self.play(Write(titulo))
        O = np.array([0, 0, -0.8])
        elev, L = 25 * DEGREES, 2.6
        psi = ValueTracker(70 * DEGREES)
        F = lambda: np.array([np.cos(elev) * np.cos(psi.get_value()), np.cos(elev) * np.sin(psi.get_value()), np.sin(elev)])
        piso = NumberPlane(x_range=[-4, 4, 1], y_range=[-4, 4, 1], background_line_style={"stroke_opacity": 0.2})\
            .shift(O)
        a = flecha(O, O + OUT * 2.2, GIRO)
        f = always_redraw(lambda: flecha(O, O + L * F(), GREY_A))
        self.add(piso)
        self.play(Create(a), Create(f))
        rot = []

        def decir(s, color=WHITE, size=24):
            nuevo = texto(s, size, color=color).to_edge(DOWN, buff=0.35)
            self.add_fixed_in_frame_mobjects(nuevo)
            if rot:
                self.play(FadeOut(rot[-1]), FadeIn(nuevo), run_time=0.6)
            else:
                self.play(FadeIn(nuevo), run_time=0.6)
            rot.append(nuevo)

        nombres = VGroup(texto("arriba", 22, color=GIRO).move_to(O + OUT * 2.5),
                         texto("antebrazo", 22, color=GREY_A).move_to(O + 1.18 * L * F()))
        self.add_fixed_orientation_mobjects(*nombres)
        self.play(FadeIn(nombres))
        decir("El reloj sabe dos cosas: dónde es arriba y que el antebrazo es su eje x.")
        self.wait(2)
        cono = Circle(radius=L * np.cos(elev), color=GREY_B, stroke_opacity=0.7).shift(O + OUT * L * np.sin(elev))
        cono = DashedVMobject(cono, num_dashes=40)
        decir("Pero arriba no dice hacia qué lado apunta el antebrazo: todo el círculo da lo mismo.")
        self.play(FadeOut(nombres[1]))
        self.play(Create(cono))
        self.play(psi.animate.set_value(430 * DEGREES), run_time=5, rate_func=smooth)
        decir("Así que se supone un rumbo ψ: el de la última vez, o el frente.")
        self.play(psi.animate.set_value(390 * DEGREES), run_time=1.5)
        fl = texto("antebrazo", 22, color=GREY_A).move_to(O + 1.18 * L * F())
        self.add_fixed_orientation_mobjects(fl)
        self.play(FadeIn(fl))
        self.wait(1)

        up = np.array([0, 0, 1.0])
        bdir = lambda: np.cross(up, F()) / np.linalg.norm(np.cross(up, F()))
        b = always_redraw(lambda: flecha(O, O + 1.8 * bdir(), GREEN))
        c = always_redraw(lambda: flecha(O, O + 1.8 * np.cross(up, bdir()), ORANGE))
        decir("b = arriba × antebrazo: perpendicular a los dos.", GREEN)
        self.play(Create(b))
        decir("c = arriba × b: la tercera. Tres flechas perpendiculares entre sí.", ORANGE)
        self.play(Create(c))
        bc = VGroup(texto("b", 26, color=GREEN).move_to(O + 2.1 * bdir()),
                    texto("c", 26, color=ORANGE).move_to(O + 2.1 * np.cross(up, bdir())))
        self.add_fixed_orientation_mobjects(*bc)
        self.play(FadeIn(bc))
        self.begin_ambient_camera_rotation(rate=0.12)
        formula = MathTex(r"R = [\,a\ b\ c\,]_{\text{mundo}}\,[\,a\ b\ c\,]_{\text{reloj}}^{\mathsf T}", font_size=38)\
            .to_corner(UR).shift(DOWN * 0.9)
        self.add_fixed_in_frame_mobjects(formula)
        decir("En el reloj se arma el mismo trío; la orientación es lo que lleva uno al otro.")
        self.play(Write(formula))
        self.wait(4)
        self.stop_ambient_camera_rotation()


# ---------------------------------------------------------------------------------------------------------
class MetodoDeProyeccion(Scene):
    """El método de proyección: rumbo = ∫ yaw dt y el resto de la gravedad; con el antebrazo vertical se pierde."""

    def construct(self):
        titulo = texto("El método de proyección y el brazo que cuelga", 32).to_edge(UP)
        self.play(Write(titulo))
        # de costado: el antebrazo baja hasta colgar; desde arriba: su sombra en el piso, que da el rumbo
        codo = LEFT * 3.6 + UP * 1.2
        elev = ValueTracker(-30)
        L = 2.4
        punta = lambda: codo + L * np.array([np.cos(np.radians(elev.get_value())), np.sin(np.radians(elev.get_value())), 0])
        piso = Line(LEFT * 6.2 + DOWN * 1.6, LEFT * 0.8 + DOWN * 1.6, color=GREY_B)
        brazo = always_redraw(lambda: Line(codo, punta(), color=GREY_A, stroke_width=10))
        sombra = always_redraw(lambda: Line([codo[0], -1.6, 0], [punta()[0], -1.6, 0], color=ACEL, stroke_width=10))
        guias = always_redraw(lambda: VGroup(DashedLine(codo, [codo[0], -1.6, 0], stroke_opacity=0.4),
                                             DashedLine(punta(), [punta()[0], -1.6, 0], stroke_opacity=0.4)))
        lc = texto("de costado", 22).next_to(piso, DOWN, buff=0.2)
        el = always_redraw(lambda: texto(f"elevación {elev.get_value():.0f}°", 22).next_to(codo, UP, buff=0.3))

        centro = RIGHT * 3.2 + DOWN * 0.1
        disco = Circle(radius=1.9, color=GREY_B, stroke_opacity=0.5).move_to(centro)
        rng = np.random.default_rng(4)
        ruido = ValueTracker(0)

        def rumbo_visto():
            c = np.cos(np.radians(elev.get_value()))
            return np.radians(35) + 0.012 * np.sin(17.3 * ruido.get_value()) / max(c, 0.012) \
                + 0.01 * np.sin(29.1 * ruido.get_value() + 1) / max(c, 0.012)

        flecha = always_redraw(lambda: Arrow(centro, centro + 1.9 * np.cos(np.radians(elev.get_value()))
                                             * np.array([np.cos(rumbo_visto()), np.sin(rumbo_visto()), 0]),
                                             buff=0, color=ACEL, stroke_width=6, max_tip_length_to_length_ratio=0.25))
        raya = always_redraw(lambda: DashedLine(centro, centro + 1.9 * np.array([np.cos(rumbo_visto()),
                                                                                  np.sin(rumbo_visto()), 0]),
                                                color=ACEL, stroke_opacity=0.6))
        la = texto("desde arriba: la sombra da el rumbo", 22).next_to(disco, DOWN, buff=0.25)
        self.play(Create(piso), FadeIn(lc, el), Create(brazo), Create(sombra), Create(guias))
        self.play(Create(disco), FadeIn(la), Create(raya), Create(flecha))
        dicho = texto("El rumbo es hacia dónde apunta la sombra del antebrazo en el piso.", 24).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(dicho))
        self.play(elev.animate.set_value(-89.3), ruido.animate.set_value(12), run_time=5, rate_func=linear)
        dicho2 = texto("Colgando, la sombra es un punto: un temblor la hace girar entera.", 24,
                       color=ERROR).to_edge(DOWN, buff=0.3)
        self.play(FadeOut(dicho), FadeIn(dicho2), ruido.animate.set_value(20), run_time=2, rate_func=linear)
        self.wait(1)
        self.play(*[FadeOut(x) for x in [piso, lc, el, brazo, sombra, guias, disco, la, raya, flecha, dicho2]])

        p = D["proyeccion"]
        t = np.array(p["t"])
        a1 = Axes(x_range=[0, round(t[-1], 2), 2], y_range=[-90, -30, 30], x_length=9.4, y_length=1.7, tips=False,
                  axis_config={"font_size": 18}, y_axis_config={"include_numbers": True})
        a2 = Axes(x_range=[0, round(t[-1], 2), 2], y_range=[0, 80, 40], x_length=9.4, y_length=2.2, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18})
        VGroup(a1, a2).arrange(DOWN, buff=0.55).next_to(titulo, DOWN, buff=0.4).shift(RIGHT * 0.4)
        l1 = texto("elevación del\nantebrazo (°)", 18).next_to(a1, LEFT, buff=0.3)
        l2 = texto("error del\nantebrazo (°)", 18).next_to(a2, LEFT, buff=0.3)
        cam = texto("caminando, los brazos colgando (un paso de 8.75 s)", 20).next_to(a1, UP, buff=0.1)
        vert = DashedLine(a1.c2p(0, -80), a1.c2p(t[-1], -80), color=ERROR, stroke_opacity=0.7)
        vl = texto("casi vertical", 16, color=ERROR).next_to(vert, RIGHT, buff=0.1)
        self.play(Create(a1), FadeIn(l1, cam), Create(linea(a1, t, p["elev"], WHITE, 3)), Create(vert), FadeIn(vl),
                  run_time=2)
        med = lambda k: float(np.median(p[k]))
        gp = linea(a2, t, np.minimum(p["proyeccion"], 80), ORANGE, 3)
        gf = linea(a2, t, p["fusion"], FILTRO, 3)
        lp = texto(f"proyección: mediana {med('proyeccion'):.0f}°", 20, color=ORANGE).move_to(a2.c2p(t[-1] * 0.26, 70))
        lf = texto(f"fusión: mediana {med('fusion'):.1f}°", 20, color=FILTRO).move_to(a2.c2p(t[-1] * 0.26, 54))
        self.play(Create(a2), FadeIn(l2), Create(gp), FadeIn(lp), run_time=3)
        self.play(Create(gf), FadeIn(lf), run_time=2)
        f = MathTex(r"\text{rumbo} = \textstyle\int \text{yaw}\,dt", font_size=30).to_edge(DOWN, buff=0.55)
        moral = texto("Sirve para apuntar; caminando, con el brazo colgando, se pierde.", 22).to_edge(DOWN, buff=0.15)
        self.play(Write(f), FadeIn(moral))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Mahony(Scene):
    """Mahony: el mismo resorte en 3D. e = arriba medido × arriba predicho es el giro que falta."""

    def construct(self):
        titulo = texto("Mahony: el resorte, en 3D", 34).to_edge(UP)
        self.play(Write(titulo))
        c = LEFT * 3.3 + DOWN * 0.6
        R = 2.0
        circ = Circle(radius=R, color=GREY_B, stroke_opacity=0.5).move_to(c)
        medido = Arrow(c, c + R * UP, buff=0, color=ACEL, stroke_width=6)
        ml = texto("amarillo: arriba medido (la gravedad)", 20, color=ACEL).move_to(c + DOWN * 2.45)
        ang = ValueTracker(50)
        dir_ = lambda: np.array([-np.sin(np.radians(ang.get_value())), np.cos(np.radians(ang.get_value())), 0])
        pred = always_redraw(lambda: Arrow(c, c + R * dir_(), buff=0, color=GIRO, stroke_width=6))
        pl = texto("azul: arriba predicho (lo que cree la estimación)", 20, color=GIRO).next_to(ml, DOWN, aligned_edge=LEFT)
        arco = always_redraw(lambda: Arc(radius=0.7, start_angle=PI / 2, angle=np.radians(ang.get_value()),
                                         arc_center=c, color=WHITE))
        self.play(Create(circ), GrowArrow(medido), FadeIn(ml))
        self.add(pred, pl, arco)
        self.wait(0.5)
        eje = VGroup(Circle(radius=0.16, color=ERROR, stroke_width=4), Dot(radius=0.05, color=ERROR)).move_to(c)
        f1 = MathTex(r"e = \hat g_{\text{medido}} \times \hat g_{\text{predicho}}", font_size=34).move_to(RIGHT * 3.3 + UP * 2.2)
        n1 = texto("e sale de la pantalla: es el eje del giro que falta,\ny mide sen(ángulo)", 20, color=ERROR)\
            .next_to(f1, DOWN, buff=0.2)
        self.play(FadeIn(eje, scale=2), Write(f1), FadeIn(n1))
        barra_ax = Axes(x_range=[0, 3, 1], y_range=[0, 1, 0.5], x_length=4.6, y_length=2.0, tips=False,
                        axis_config={"include_numbers": True, "font_size": 16}).next_to(n1, DOWN, buff=0.45)
        bl = texto("|e| contra el tiempo (s), Kp = 2", 18).next_to(barra_ax, DOWN, buff=0.2)
        f2 = MathTex(r"q \leftarrow q \otimes \exp\!\big((\omega + K_p\,e)\,\Delta t/2\big)", font_size=34)\
            .next_to(bl, DOWN, buff=0.35)
        self.play(Create(barra_ax), FadeIn(bl), Write(f2))
        # girar alrededor de e, Kp·|e| por segundo: dθ/dt = −Kp sen θ
        ts, th = [0.0], [np.radians(50)]
        for _ in range(300):
            th.append(th[-1] - 0.01 * 2 * np.sin(th[-1]))
            ts.append(ts[-1] + 0.01)
        tt = ValueTracker(0)
        traza = always_redraw(lambda: barra_ax.plot(lambda x: float(np.sin(np.interp(x, ts, th))),
                                                    x_range=[0, max(0.02, tt.get_value()), 0.02], color=ERROR))
        self.add(traza)
        ang.add_updater(lambda a: a.set_value(np.degrees(np.interp(tt.get_value(), ts, th))))
        self.add(ang)
        self.play(tt.animate.set_value(3), run_time=5, rate_func=linear)
        ang.clear_updaters()
        self.wait(1)
        self.play(*[FadeOut(x) for x in [circ, medido, ml, pred, pl, arco, eje, f1, n1, barra_ax, bl, f2, traza]])

        d = D["mahony"]
        t = np.array(d["t"])
        ax = Axes(x_range=[0, 60, 10], y_range=[-5, 30, 5], x_length=10.5, y_length=4.6, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18}).next_to(titulo, DOWN, buff=0.5)
        yl = texto("error de inclinación (°)", 20).next_to(ax.y_axis, UP, buff=0.1).shift(RIGHT * 1.2)
        xl = texto("s", 18).next_to(ax.x_axis, RIGHT, buff=0.1)
        sub = texto("un minuto apuntando, con ruido y con sesgo en el giroscopio", 20).next_to(ax, DOWN, buff=0.15)
        self.play(Create(ax), FadeIn(yl, xl, sub))
        g0 = linea(ax, t, d["incl0"], ERROR, 3)
        g2 = linea(ax, t, d["incl2"], FILTRO, 4)
        l0 = texto(f"Kp = 0 (solo integrar): se va {d['incl0'][-1]:.0f}°", 22, color=ERROR).move_to(ax.c2p(22, 24))
        mx = max(abs(x) for x in d["incl2"] if x is not None)
        l2 = texto(f"Kp = 2: nunca pasa de {mx:.1f}°", 22, color=FILTRO).move_to(ax.c2p(45, 4))
        self.play(Create(g0), FadeIn(l0), run_time=3)
        self.play(Create(g2), FadeIn(l2), run_time=3)
        moral = texto("El resorte endereza la inclinación. ¿Y el rumbo?", 24).to_edge(DOWN, buff=0.2)
        self.play(FadeIn(moral))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class DerivaDelRumbo(Scene):
    """Por qué el rumbo se va: el sesgo alrededor de la vertical no tiene quién lo corrija."""

    def construct(self):
        titulo = texto("Por qué el rumbo se va", 34).to_edge(UP)
        self.play(Write(titulo))
        d = D["mahony"]
        t = np.array(d["t"])
        ax = Axes(x_range=[0, 60, 10], y_range=[-5, 30, 5], x_length=10.5, y_length=3.6, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18}).next_to(titulo, DOWN, buff=0.5)
        yl = texto("error de rumbo con Kp = 2 (°)", 20).next_to(ax.y_axis, UP, buff=0.1).shift(RIGHT * 1.6)
        xl = texto("s", 18).next_to(ax.x_axis, RIGHT, buff=0.1)
        self.play(Create(ax), FadeIn(yl, xl))
        rumbo = linea(ax, t, [x if x is not None else np.nan for x in d["rumbo2"]], ERROR, 4)
        pred = DashedVMobject(linea(ax, t, d["pred"], WHITE, 3)["line_graph"], num_dashes=60)
        lr = texto(f"el rumbo de la fusión: {d['rumbo2'][-1]:.1f}°", 22, color=ERROR).move_to(ax.c2p(18, 24))
        lp = MathTex(rf"\textstyle\int b\cdot\hat g\,dt = {d['pred'][-1]:.1f}^\circ", font_size=30).move_to(ax.c2p(18, 17))
        self.play(Create(rumbo), FadeIn(lr), run_time=3)
        self.play(Create(pred), Write(lp), run_time=2)
        n = texto("La parte del sesgo que gira alrededor de la vertical: la gravedad no la ve, nadie la corrige.", 22)\
            .next_to(ax, DOWN, buff=0.3)
        self.play(FadeIn(n))
        self.wait(2)
        self.play(*[FadeOut(x) for x in [ax, yl, xl, rumbo, pred, lr, lp, n]])

        # en el cursor: 0.3 °/s durante 10 s, con la pantalla a 2.4 m
        esc = 2.4                                  # unidades de Manim por metro
        yo = LEFT * 3.0 + DOWN * 0.6
        pant = Line(yo + RIGHT * esc * 2.4 + UP * 1.6, yo + RIGHT * esc * 2.4 + DOWN * 1.6, color=GREY_A, stroke_width=6)
        pl = texto("la pantalla, a 2.4 m", 20).next_to(pant, RIGHT, buff=0.2)
        p = Dot(yo, color=WHITE)
        plb = texto("tú (desde arriba)", 20).next_to(p, DOWN, buff=0.2)
        th = ValueTracker(0)
        rayo = always_redraw(lambda: Line(yo, yo + esc * 2.4 * np.array([1, np.tan(np.radians(th.get_value())), 0]),
                                          color=ACEL, stroke_width=3))
        bien = DashedLine(yo, yo + RIGHT * esc * 2.4, color=WHITE, stroke_opacity=0.6)
        cursor = always_redraw(lambda: Dot(rayo.get_end(), color=ACEL, radius=0.1))
        reloj = always_redraw(lambda: texto(f"{th.get_value() / 0.29:.1f} s  →  {th.get_value():.1f}°  →  "
                                            f"{240 * np.tan(np.radians(th.get_value())):.0f} cm", 26)
                              .next_to(titulo, DOWN, buff=0.5))
        self.play(Create(pant), FadeIn(pl, p, plb), Create(bien), Create(rayo), FadeIn(cursor))
        self.add(reloj)
        self.play(th.animate.set_value(2.9), run_time=6, rate_func=linear)
        moral = texto("Unas décimas de °/s que nadie corrige: unos 12 cm de cursor en 10 s.", 24).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(moral))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Recentrar(Scene):
    """Recentrar: el rumbo es relativo; se fija un frente y se vuelve a él, con un botón o de a poco."""

    def construct(self):
        hz, dur, deriva, tau = 20, 60, 0.4, 12.0
        t = np.arange(0, dur, 1 / hz)
        s = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
        mano = 40 * (s((t - 8) / 2) - s((t - 22) / 2))          # giras 40° a la izquierda y vuelves
        est = mano + deriva * t                                   # lo que cree la fusión
        boton = est - np.where(t >= 40, est[int(40 * hz)] - mano[int(40 * hz)], 0)
        poco, off = np.zeros_like(t), 0.0
        for i in range(len(t)):                                   # avatar.js: autoCenterStep, τ = 12 s
            poco[i] = est[i] - off
            off += poco[i] * min(1, (1 / hz) / tau)

        titulo = texto("Recentrar: el rumbo es relativo", 34).to_edge(UP)
        ax = Axes(x_range=[0, 60, 10], y_range=[-20, 80, 20], x_length=10.5, y_length=4.6, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18}).next_to(titulo, DOWN, buff=0.5)
        yl = texto("rumbo (°)", 20).next_to(ax.y_axis, UP, buff=0.1)
        xl = texto("s", 18).next_to(ax.x_axis, RIGHT, buff=0.1)
        frente = DashedLine(ax.c2p(0, 0), ax.c2p(60, 0), stroke_opacity=0.5)
        fl = texto("el frente", 18).next_to(frente, RIGHT, buff=0.1)
        self.play(Write(titulo), Create(ax), FadeIn(yl, xl), Create(frente), FadeIn(fl))

        def ley(txt, color, i):
            return texto(txt, 20, color=color).move_to(ax.c2p(21, 77 - 7 * i), aligned_edge=LEFT)

        g = linea(ax, t, mano, WHITE, 4)
        self.play(Create(g), FadeIn(ley("tu mano: giras 40° y vuelves", WHITE, 0)), run_time=2.5)
        g1 = linea(ax, t, est, ERROR, 3)
        self.play(Create(g1), FadeIn(ley(f"sin recentrar: se va {deriva} °/s", ERROR, 1)), run_time=2.5)
        g2 = linea(ax, t, boton, ORANGE, 3)
        marca = Arrow(ax.c2p(40, -18), ax.c2p(40, -3), buff=0, color=ORANGE, stroke_width=4)
        self.play(Create(g2), GrowArrow(marca), FadeIn(ley("con un botón (R) en el segundo 40, mirando al frente", ORANGE, 2)),
                  run_time=2.5)
        g3 = linea(ax, t, poco, FILTRO, 3)
        self.play(Create(g3), FadeIn(ley(f"de a poco, τ = {tau:.0f} s", FILTRO, 3)), run_time=2.5)
        n = texto("De a poco no hace falta botón, pero también se come los giros que dejas puestos mucho rato:\n"
                  "por eso conviene hacerlo cuando la mano descansa.", 20).next_to(ax, DOWN, buff=0.3)
        self.play(FadeIn(n))
        self.wait(3)
