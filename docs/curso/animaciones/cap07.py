"""Animaciones del capítulo 7 (De 3D a 2D: el cursor), una por concepto.

    python docs/curso/animaciones/render.py cap07 ArcoDTheta ...     # a GIF en docs/curso/media/cap07/
    python -m manim -ql docs/curso/animaciones/cap07.py Ganancia     # una, rápido, para mirarla

La cadena del cursor es la de tools/air_mouse.py, importada tal cual: Motion.feed_gyro corre de verdad con tasas
inventadas. datos_cap07.js da el rayo y el cursor de la animación de apuntar (server/web/mocapmath.js) y este archivo
comprueba, antes de dibujar nada, que la copia de JS de tools/test_cursor.js da lo mismo que el código en Python.
"""
import json
import os
import subprocess
import sys

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "..", "tools"))
from air_mouse import Motion, OneEuro, clamp, make_config     # noqa: E402  los de verdad

D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap07.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)
GRADO = np.pi / 180
RAYO, CURSOR, MUNECA, FILTRO, CRUDO = YELLOW, TEAL, BLUE, GREEN, GREY_B
DT = 0.01


def cadena(yaw, pitch=None, **cfg):
    """Tasas en °/s → lo que se mueve el cursor en cada muestra, con Motion.feed_gyro de verdad."""
    m = Motion(make_config(**cfg))
    m.calibrated = True
    pitch = np.zeros(len(yaw)) if pitch is None else pitch
    out, t = [], 1000.0
    for y, p in zip(yaw, pitch):
        m.feed_gravity(t, 0.0, 0.0, 9.81)
        m.feed_accel(t, 0.0, 0.0, 9.81)
        s = m.feed_gyro(t, float(p), 0.0, float(y), bias_ok=False)
        out.append((s.dx, s.dy))
        t += 1000 * DT
    return np.array(out)


_e = OneEuro(2.0, 0.01, 1.0)
assert np.allclose([_e(x, DT) for x in D["prueba"]], D["euro"])
assert np.allclose(cadena(D["prueba"]), D["cadenaYaw"])
assert np.allclose(cadena(np.zeros(len(D["prueba"])), D["prueba"]), D["cadenaPitch"])


_TEXTOS = {}


def texto(s, size=30, **kw):
    """Text tarda: lo que se rehace en cada cuadro repite casi siempre las mismas cadenas, y copiar es barato."""
    clave = (s, size, tuple(sorted((k, str(v)) for k, v in kw.items())))
    if clave not in _TEXTOS:
        _TEXTOS[clave] = Text(s, font_size=size, **kw)
    return _TEXTOS[clave].copy()


def cada(func, n=4):
    """Como always_redraw, pero rehace solo uno de cada n cuadros: para las cifras, que no necesitan más."""
    m = func()
    cuenta = [0]

    def rehacer(mm):
        cuenta[0] += 1
        if cuenta[0] % n == 0:
            mm.become(func())
    m.add_updater(rehacer)
    return m


def flecha(a, b, color, w=6):
    return Arrow(np.asarray(a, float), np.asarray(b, float), buff=0, color=color, stroke_width=w,
                 max_tip_length_to_length_ratio=0.15)


def ejes(x, y, ancho=9.5, alto=4.0, numeros=True, **kw):
    return Axes(x_range=x, y_range=y, x_length=ancho, y_length=alto, tips=False,
                axis_config={"include_numbers": numeros, "font_size": 18}, **kw)


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


class Escena(Scene):
    def decir(self, s, color=WHITE, size=24):
        nuevo = texto(s, size, color=color)
        if nuevo.width > 13.2:
            nuevo.scale_to_fit_width(13.2)
        nuevo.to_edge(DOWN, buff=0.3)
        viejo = getattr(self, "_rotulo", None)
        self.play(*([FadeOut(viejo)] if viejo else []), FadeIn(nuevo), run_time=0.5)
        self._rotulo = nuevo


# ---------------------------------------------------------------------------------------------------------
class ArcoDTheta(Escena):
    """Girar θ radianes a distancia D recorre un arco D·θ; un grado son D·π/180."""

    def construct(self):
        d, E = 2.4, 2.1                              # metros, y unidades de pantalla por metro
        O = np.array([-5.8, -2.5, 0])
        th = ValueTracker(0.0)
        punta = lambda a: O + d * E * np.array([np.cos(a), np.sin(a), 0])
        titulo = texto("El arco: D · θ", 34).to_edge(UP)
        self.play(Write(titulo))
        base = DashedLine(O, punta(0), color=GREY_B)
        etiqueta = texto("D = 2.4 m", 22, color=GREY_B).next_to(base, DOWN, buff=0.12)
        muneca = Dot(O, radius=0.1, color=MUNECA)
        self.play(Create(base), FadeIn(muneca, etiqueta))
        rayo = always_redraw(lambda: Line(O, punta(th.get_value()), color=RAYO, stroke_width=4))
        arco = always_redraw(lambda: Arc(radius=d * E, start_angle=0, angle=max(th.get_value(), 1e-4), arc_center=O,
                                         color=RED, stroke_width=7))
        punto = always_redraw(lambda: Dot(punta(th.get_value()), radius=0.09, color=RED))

        def lectura():
            a = th.get_value()
            return VGroup(texto(f"θ = {a / GRADO:.1f}°", 28), texto(f"θ = {a:.3f} rad", 28),
                          texto(f"arco = {100 * d * a:.1f} cm", 28, color=RED)).arrange(DOWN, aligned_edge=LEFT, buff=0.22) \
                .move_to([3.6, 1.2, 0], aligned_edge=LEFT).shift(LEFT * 0.6)
        cifras = cada(lectura)
        formula = MathTex(r"\text{arco} = D\cdot\theta", font_size=44).move_to([4.2, -0.6, 0])
        self.add(rayo, arco, punto)
        self.play(FadeIn(cifras), Write(formula))
        self.decir("Girar es recorrer un arco: la punta del rayo se mueve D por cada radián")
        self.play(th.animate.set_value(10 * GRADO), run_time=2)
        self.wait(0.6)
        self.play(th.animate.set_value(40 * GRADO), run_time=2.2)
        self.wait(0.6)
        self.decir("Un radián es el ángulo cuyo arco mide lo mismo que el radio: 57.3°")
        self.play(th.animate.set_value(1.0), run_time=1.5)
        recta = Line(O, O + RIGHT * d * E, color=RED, stroke_width=7)
        copia = Arc(radius=d * E, start_angle=0, angle=1.0, arc_center=O, color=RED, stroke_width=7)
        self.play(Transform(copia, recta), run_time=1.6)
        self.wait(0.6)
        self.play(FadeOut(copia))
        self.decir("Por eso θ va en radianes. Un grado son π/180 radianes")
        self.play(th.animate.set_value(1 * GRADO), run_time=1.6)
        uno = MathTex(r"1^\circ \;\to\; D\cdot\frac{\pi}{180}", f"= {100 * d * GRADO:.2f}" + r"\text{ cm}", font_size=38).next_to(formula, DOWN, buff=0.45)
        self.play(Write(uno))
        self.decir("cursorTrack usa este número: K = D · π/180 metros por grado")
        self.wait(2)


class RayoTangente(Escena):
    """En una pared plana el rayo pega en D·tan θ, más lejos que el arco."""

    def construct(self):
        d, E = 2.4, 1.55
        O = np.array([-6.3, -2.6, 0])
        muro = O[0] + d * E
        th = ValueTracker(0.0)
        titulo = texto("El rayo pega en D · tan θ", 34).to_edge(UP)
        self.play(Write(titulo))
        pared = Line([muro, O[1] - 0.2, 0], [muro, O[1] + 3.5 * 1.42, 0], color=GREY_B, stroke_width=5)
        base = DashedLine(O, [muro, O[1], 0], color=GREY_B)
        tag = texto("D = 2.4 m", 20, color=GREY_B).next_to(base, DOWN, buff=0.1)
        origen = Dot(O, radius=0.09, color=MUNECA)
        self.play(Create(pared), Create(base), FadeIn(tag, origen))
        alto_rayo = lambda: O[1] + d * np.tan(th.get_value()) * E
        alto_arco = lambda: O[1] + d * th.get_value() * E
        rayo = always_redraw(lambda: Line(O, [muro, alto_rayo(), 0], color=RAYO, stroke_width=3))
        p_rayo = always_redraw(lambda: Dot([muro, alto_rayo(), 0], radius=0.09, color=RAYO))
        p_arco = always_redraw(lambda: Dot([muro, alto_arco(), 0], radius=0.09, color=CURSOR))
        ax = ejes([0, 40, 10], [0, 2.2, 0.5], ancho=5.4, alto=3.5).move_to([3.7, 0.15, 0])
        lx = texto("θ (°)", 18).next_to(ax, DOWN, buff=0.08).shift(RIGHT * 2.4)
        ly = texto("metros", 18).next_to(ax, UP, buff=0.05).shift(LEFT * 2.3)
        gr = np.linspace(0, 40, 81)
        c1 = linea(ax, gr, d * np.tan(gr * GRADO), RAYO)
        c2 = linea(ax, gr, d * gr * GRADO, CURSOR)
        n1 = texto("rayo: D · tan θ", 20, color=RAYO).move_to(ax.c2p(13, 1.75))
        n2 = texto("cursor: D · θ", 20, color=CURSOR).move_to(ax.c2p(29, 0.62))
        self.add(rayo, p_rayo, p_arco)
        self.play(Create(ax), FadeIn(lx, ly), Create(c1), Create(c2), FadeIn(n1, n2), run_time=1.6)

        def cifras():
            a = th.get_value()
            r, c = d * np.tan(a), d * a
            return VGroup(texto(f"θ = {a / GRADO:.0f}°", 24), texto(f"rayo  {100 * r:.1f} cm", 24, color=RAYO),
                          texto(f"cursor {100 * c:.1f} cm", 24, color=CURSOR),
                          texto(f"se separan {100 * (r - c):.1f} cm", 24, color=RED)).arrange(RIGHT, buff=0.4).to_edge(UP, buff=1.0).shift(RIGHT * 2.2).scale(0.82)
        lect = cada(cifras)
        marca = always_redraw(lambda: Dot(ax.c2p(th.get_value() / GRADO, d * np.tan(th.get_value())), radius=0.06, color=RAYO))
        self.add(lect, marca)
        self.decir("Con 10° casi no se distinguen: 42.3 cm contra 41.9 cm")
        self.play(th.animate.set_value(10 * GRADO), run_time=2)
        self.wait(0.8)
        self.decir("Con 13° ya hay un centímetro entre los dos: tan θ − θ ≈ θ³/3")
        self.play(th.animate.set_value(13.2 * GRADO), run_time=1.2)
        self.wait(0.8)
        # de dónde sale θ³/3: la pendiente de tan θ es 1/cos²θ = 1 + tan²θ, la del arco es 1; la resta, tan²θ ≈ θ²,
        # sumada desde 0 da exactamente tan θ − θ (y θ³/3 si se cambia tan²θ por θ²)
        a = 13.2 * GRADO
        assert abs(np.sum(np.tan(np.linspace(0, a, 20001)[:-1] + a / 40000) ** 2) * a / 20000 - (np.tan(a) - a)) < 1e-9
        assert abs(a ** 3 / 3 / (np.tan(a) - a) - 1) < 0.03
        self.decir("Por cada Δθ, el rayo avanza D(1 + tan²θ)·Δθ y el cursor D·Δθ")
        self.wait(2)
        self.decir("La diferencia crece a D·tan²θ ≈ D·θ²; sumar θ² desde 0 da θ³/3")
        self.wait(2)
        self.decir("Con 40° el rayo va por 2.01 m y el cursor por 1.68 m")
        self.play(th.animate.set_value(40 * GRADO), run_time=2.4)
        self.wait(1)
        self.remove(rayo, p_rayo, p_arco, lect, marca)
        self.play(*[FadeOut(m) for m in (pared, base, tag, origen, ax, lx, ly, c1, c2, n1, n2, titulo, self._rotulo)])
        self._rotulo = None

        # en 2D: los íconos de las esquinas de la animación de apuntar, sin ruido
        A = D["apuntar"]
        S = A["pantalla"]
        E2 = 5.6
        titulo2 = texto(f"En la pantalla de la simulación, a {A['D']:.2f} m", 32).to_edge(UP)
        marco = Rectangle(width=S["w"] * E2, height=S["h"] * E2, color=GREY_B).shift(DOWN * 0.1)
        P = lambda q: marco.get_center() + E2 * np.array([q[0], q[1], 0])
        iconos = VGroup(*[VGroup(Square(0.34, color=GREY_B), texto(n, 18, color=GREY_B).next_to(P((x, y)), DOWN if y > 0 else UP, buff=0.26))
                          for n, x, y in S["icons"]])
        for g, (n, x, y) in zip(iconos, S["icons"]):
            g[0].move_to(P((x, y)))
        self.play(Write(titulo2), Create(marco), FadeIn(iconos))
        k = ValueTracker(0)
        n_fin = next(i for i, t in enumerate(A["t"]) if t >= 5.4)
        tramo = lambda serie: VMobject().set_points_as_corners([P(q) for q in serie[:max(2, int(k.get_value()) + 1)]])
        t_rayo = always_redraw(lambda: tramo(A["rayo"]).set_stroke(RAYO, 3))
        t_cur = always_redraw(lambda: tramo(A["cursor"]).set_stroke(CURSOR, 3))
        d_rayo = always_redraw(lambda: Dot(P(A["rayo"][int(k.get_value())]), radius=0.07, color=RAYO))
        d_cur = always_redraw(lambda: Dot(P(A["cursor"][int(k.get_value())]), radius=0.07, color=CURSOR))
        self.add(t_rayo, t_cur, d_rayo, d_cur)
        self.decir("Amarillo: donde pega el rayo. Verde: el cursor, D por los ángulos sumados")
        self.play(k.animate.set_value(n_fin), run_time=5, rate_func=linear)
        err = []
        for t0, _, nombre in A["marcas"][:4]:
            i = int(np.argmin(np.abs(np.array(A["t"]) - t0)))
            err.append(100 * np.hypot(*(np.array(A["rayo"][i]) - np.array(A["cursor"][i]))))
        self.decir(f"En los íconos de la derecha se separan {err[1]:.1f} y {err[2]:.1f} cm; a la izquierda, {err[0]:.1f} y {err[3]:.1f} cm")
        self.wait(2.5)


class DosAngulos(Escena):
    """(sen yaw·cos pitch, sen pitch, −cos yaw·cos pitch): la flecha que apunta con esos dos ángulos."""

    def construct(self):
        az, el, E = 20 * GRADO, 30 * GRADO, 2.5
        c = np.array([np.sin(az) * np.cos(el), np.sin(el), np.cos(az) * np.cos(el)])
        der = np.array([np.cos(az), 0, -np.sin(az)])
        arr = np.cross(c, der)
        centro = np.array([-2.9, -0.75, 0])
        pr = lambda p: centro + E * np.array([np.dot(p, der), np.dot(p, arr), 0])
        direccion = lambda y, p: np.array([np.sin(y) * np.cos(p), np.sin(p), -np.cos(y) * np.cos(p)])
        yaw, pit = ValueTracker(0.0), ValueTracker(0.0)
        Y, Pp = yaw.get_value, pit.get_value
        titulo = texto("De dos ángulos a una dirección", 34).to_edge(UP)
        self.play(Write(titulo))
        ang = np.linspace(0, 2 * np.pi, 73)
        piso = VMobject().set_points_as_corners([pr((np.cos(a), 0, np.sin(a))) for a in ang]).set_stroke(GREY_B, 2)
        ejes3 = VGroup(DashedLine(pr((0, 0, 0)), pr((1.2, 0, 0)), color=GREY_C), DashedLine(pr((0, 0, 0)), pr((0, 1.2, 0)), color=GREY_C),
                       DashedLine(pr((0, 0, 0)), pr((0, 0, -1.25)), color=GREY_C))
        rot = VGroup(texto("derecha +x", 18, color=GREY_B).next_to(pr((1.2, 0, 0)), DOWN, buff=0.1),
                     texto("arriba +y", 18, color=GREY_B).next_to(pr((0, 1.2, 0)), UP, buff=0.05),
                     texto("adelante −z", 18, color=GREY_B).next_to(pr((0, 0, -1.25)), LEFT, buff=0.08))
        self.play(Create(piso), Create(ejes3), FadeIn(rot))
        d = lambda: direccion(Y(), Pp())
        sombra_p = lambda: np.array([d()[0], 0, d()[2]])
        fl = always_redraw(lambda: flecha(pr((0, 0, 0)), pr(d()), RAYO, 7))
        sombra = always_redraw(lambda: Line(pr((0, 0, 0)), pr(sombra_p()), color=BLUE, stroke_width=6))
        caida = always_redraw(lambda: DashedLine(pr(d()), pr(sombra_p()), color=BLUE_B, stroke_width=2))
        arco_y = always_redraw(lambda: VMobject().set_points_as_corners(
            [pr(0.45 * direccion(a, 0)) for a in np.linspace(0, Y() + 1e-4, 24)]).set_stroke(RED, 4))
        arco_p = always_redraw(lambda: VMobject().set_points_as_corners(
            [pr(0.6 * direccion(Y(), a)) for a in np.linspace(0, Pp() + 1e-4, 24)]).set_stroke(GREEN, 4))
        self.add(sombra, caida, arco_y, arco_p, fl)

        def cifras():
            v = d()
            return VGroup(texto(f"yaw = {Y() / GRADO:+.0f}°", 26, color=RED), texto(f"pitch = {Pp() / GRADO:+.0f}°", 26, color=GREEN),
                          texto(f"x = {v[0]:+.2f}", 24), texto(f"y = {v[1]:+.2f}", 24), texto(f"z = {v[2]:+.2f}", 24),
                          texto(f"largo = {np.linalg.norm(v):.2f}", 24, color=RAYO),
                          texto(f"sombra = {np.hypot(v[0], v[2]):.2f}", 24, color=BLUE)).arrange(DOWN, aligned_edge=LEFT, buff=0.14).move_to([3.1, 1.15, 0], aligned_edge=LEFT)
        lect = cada(cifras)
        formula = MathTex(r"\big(\sin y\cos p,\ \sin p,\ -\cos y\cos p\big)", font_size=34).move_to([4.0, -1.75, 0])
        self.add(lect)
        self.play(Write(formula))
        self.decir("El yaw gira la flecha sobre el piso: seno a un lado, coseno adelante")
        self.play(yaw.animate.set_value(35 * GRADO), run_time=2)
        self.wait(0.4)
        self.decir("El pitch la levanta: sube sen p, y la sombra se achica a cos p")
        self.play(pit.animate.set_value(30 * GRADO), run_time=2)
        self.wait(0.4)
        self.play(pit.animate.set_value(65 * GRADO), run_time=1.6)
        self.wait(0.4)
        self.decir("Por eso x y z llevan cos p: la flecha siempre mide 1")
        self.play(yaw.animate.set_value(-60 * GRADO), run_time=2)
        self.play(pit.animate.set_value(18 * GRADO), run_time=1.4)
        self.decir("aimDir (el juego) y point3 (Dibuja) hacen esta misma cuenta")
        self.wait(2)


class Ganancia(Escena):
    """Píxeles por grado: el número que convierte el giro de la muñeca en movimiento del cursor."""

    def construct(self):
        titulo = texto("Ganancia: píxeles por grado", 34).to_edge(UP)
        self.play(Write(titulo))
        th = ValueTracker(0.0)
        C, R = np.array([-5.0, -0.6, 0]), 1.7
        base = DashedLine(C, C + R * RIGHT, color=GREY_B)
        brazo = always_redraw(lambda: Line(C, C + R * np.array([np.cos(th.get_value() * GRADO), np.sin(th.get_value() * GRADO), 0]), color=RAYO, stroke_width=6))
        arco = always_redraw(lambda: Arc(radius=0.9, start_angle=0, angle=max(th.get_value() * GRADO, 1e-4), arc_center=C, color=RED, stroke_width=5))
        grados = cada(lambda: texto(f"{th.get_value():.1f}°", 30, color=RED).move_to(C + DOWN * 0.7))
        self.play(Create(base), FadeIn(Dot(C, radius=0.08, color=MUNECA)))
        self.add(brazo, arco, grados)
        x0, x1 = -2.3, 5.9
        filas = [(12, CURSOR, "12 px/° (ratón aéreo, lento)", 1.3), (16, BLUE, "16 px/° (Dibuja)", -0.1), (30, ORANGE, "30 px/° (ratón aéreo, rápido)", -1.5)]
        escala = lambda px: x0 + (x1 - x0) * px / 1920
        for g, col, nom, y in filas:
            self.add(Line([x0, y, 0], [x1, y, 0], color=GREY_C, stroke_width=3), texto(nom, 20, color=col).move_to([x0, y + 0.42, 0], aligned_edge=LEFT))
            self.add(always_redraw(lambda g=g, col=col, y=y: Dot([escala(min(1920, g * th.get_value())), y, 0], radius=0.11, color=col)))
            self.add(cada(lambda g=g, col=col, y=y: texto(f"{min(1920, g * th.get_value()):.0f} px", 20, color=col).move_to([x1, y + 0.42, 0], aligned_edge=RIGHT)))
        self.add(texto("0", 18, color=GREY_B).move_to([x0, -2.0, 0]), texto("1920 px", 18, color=GREY_B).move_to([x1 - 0.3, -2.0, 0]))
        self.decir("Los mismos 10° de muñeca: 120, 160 o 300 píxeles")
        self.play(th.animate.set_value(10), run_time=2)
        self.wait(1)
        self.decir("Cruzar 1920 píxeles cuesta 64° a 30 px/°, y 160° a 12 px/°")
        self.play(th.animate.set_value(64), run_time=3)
        self.wait(1)
        laser = (0.6 * GRADO) * (1920 / 0.53)
        self.decir(f"Un láser a 60 cm de un monitor de 53 cm y 1920 px serían {laser:.0f} px/°: D·π/180 por px/m")
        self.wait(3)


class Recortar(Escena):
    """Limitar un valor entre un mínimo y un máximo."""

    def construct(self):
        titulo = texto("Recortar a un rango", 34).to_edge(UP)
        self.play(Write(titulo))
        lim = 30
        a1 = ejes([-50, 50, 25], [-40, 40, 20], ancho=4.6, alto=3.6).move_to([-4.2, 0.1, 0])
        ent = np.linspace(-50, 50, 101)
        c1 = linea(a1, ent, [clamp(float(v), -lim, lim) for v in ent], RAYO, 4)
        n1 = texto("clamp(v, −30, 30)", 22, color=RAYO).next_to(a1, UP, buff=0.1)
        self.play(Create(a1), FadeIn(n1), Create(c1))
        self.decir("Dentro del rango no cambia nada; fuera, se queda en el tope")
        self.wait(1.2)
        # la mira del juego suma la muñeca y recorta en cada paso
        t = np.arange(0, 8.001, 0.01)
        muneca = np.where(t < 2.4, 40 * t / 2.4, np.where(t < 2.8, 40, np.where(t < 5.2, 40 * (5.2 - t) / 2.4, 0)))
        mira, m = [], 0.0
        paso = np.diff(muneca, prepend=0.0)
        for dth in paso:
            m = clamp(m + dth, -lim, lim)
            mira.append(m)
        mira = np.array(mira)
        a2 = ejes([0, 8, 2], [-20, 50, 10], ancho=7.0, alto=3.6).move_to([2.9, 0.1, 0])
        tope = DashedLine(a2.c2p(0, lim), a2.c2p(8, lim), color=RED)
        ntope = texto("tope de 30°", 18, color=RED).next_to(a2.c2p(6.9, lim), UP, buff=0.06)
        lx = texto("segundos", 18).next_to(a2, DOWN, buff=0.05).shift(RIGHT * 2.9)
        self.play(Create(a2), Create(tope), FadeIn(ntope, lx))
        k = ValueTracker(2)
        c_m = always_redraw(lambda: linea(a2, t[:int(k.get_value()):8], muneca[:int(k.get_value()):8], MUNECA, 4))
        c_a = always_redraw(lambda: linea(a2, t[:int(k.get_value()):8], mira[:int(k.get_value()):8], RAYO, 4))
        self.add(c_m, c_a)
        self.add(texto("muñeca", 20, color=MUNECA).move_to(a2.c2p(2.6, 46)), texto("mira", 20, color=RAYO).move_to(a2.c2p(5.7, 8)))
        self.decir("La mira del juego suma la muñeca y se recorta en cada muestra")
        self.play(k.animate.set_value(len(t) - 1), run_time=5, rate_func=linear)
        self.decir(f"La muñeca siguió {40 - lim}° contra el tope: al volver, la mira queda corrida {abs(mira[-1]):.0f}°")
        self.wait(2)
        self.remove(c_m, c_a)
        self.clear()
        self.add(titulo)
        filas = [("el borde de la pantalla", "AirMouse._clamp: x entre vx y vx + vw − 1"),
                 ("la velocidad máxima", "feed_gyro: 4000 px/s, los dos ejes por igual"),
                 ("la mira del juego", "onGyro: ±30° de yaw y ±18° de pitch"),
                 ("una pausa de red", "feed_gyro: dt de 5 ms o más; de 100 ms para arriba, se descarta"),
                 ("una pausa al reproducir", "timeline: 400 ms como mucho")]
        tabla = VGroup(*[VGroup(texto(a, 26, color=RAYO), texto(b, 22, color=GREY_A)).arrange(DOWN, aligned_edge=LEFT, buff=0.08) for a, b in filas]).arrange(DOWN, aligned_edge=LEFT, buff=0.26).move_to(DOWN * 0.15)
        self.play(LaggedStart(*[FadeIn(f, shift=RIGHT * 0.3) for f in tabla], lag_ratio=0.25), run_time=2.4)
        self.wait(2.5)


class Subpixel(Escena):
    """El cursor vive en píxeles enteros: se guardan los decimales y se redondea al mandar."""

    def construct(self):
        titulo = texto("Movimientos de menos de un píxel", 34).to_edge(UP)
        self.play(Write(titulo))
        n = 201
        pasos = -cadena(np.full(n, 3.0))[:, 0]        # girar 3 °/s hacia un lado; el cursor avanza
        p_dec = np.cumsum(pasos)
        p_ent = np.round(p_dec)
        p_mal = np.cumsum(np.round(pasos))
        t = np.arange(n) * DT
        por = pasos[100]
        cab = texto(f"A 3 °/s, cada muestra mueve {por:.3f} px: menos de uno", 26, color=RAYO).next_to(titulo, DOWN, buff=0.2)
        self.play(FadeIn(cab))
        # ampliación: ocho píxeles
        lado, x0, y0 = 0.95, -5.6, 1.15
        celdas = VGroup(*[Square(lado, color=GREY_C, stroke_width=2).move_to([x0 + i * lado, y0, 0]) for i in range(9)])
        nums = VGroup(*[texto(str(i), 18, color=GREY_B).move_to([x0 + i * lado, y0 - 0.72, 0]) for i in range(9)])
        k = ValueTracker(0)
        idx = lambda: int(k.get_value())
        pinta = always_redraw(lambda: Square(lado, fill_color=CURSOR, fill_opacity=0.55, stroke_width=0).move_to([x0 + p_ent[idx()] * lado, y0, 0]))
        real = always_redraw(lambda: Dot([x0 + p_dec[idx()] * lado, y0, 0], radius=0.09, color=RAYO))
        lect = cada(lambda: VGroup(texto(f"P = {p_dec[idx()]:.2f}", 26, color=RAYO), texto(f"se manda {p_ent[idx()]:.0f}", 26, color=CURSOR)).arrange(DOWN, aligned_edge=LEFT, buff=0.14).move_to([2.9, y0, 0], aligned_edge=LEFT), n=2)
        self.play(FadeIn(celdas, nums))
        self.add(pinta, real, lect)
        self.decir("P guarda los decimales; a la pantalla va P redondeado")
        self.play(k.animate.set_value(32), run_time=5, rate_func=linear)
        self.wait(0.5)
        ax = ejes([0, 2, 0.5], [0, 60, 20], ancho=8.8, alto=2.1).move_to([0.6, -1.65, 0])
        ly = texto("píxeles", 18).next_to(ax, LEFT, buff=0.12)
        self.play(Create(ax), FadeIn(ly))
        j = ValueTracker(2)
        c1 = always_redraw(lambda: linea(ax, t[:int(j.get_value())], p_ent[:int(j.get_value())], CURSOR, 4))
        c2 = always_redraw(lambda: linea(ax, t[:int(j.get_value())], p_mal[:int(j.get_value())], RED, 4))
        self.add(c1, c2)
        self.decir("Si se redondeara cada paso, 0.264 sería siempre 0: el cursor no se movería")
        self.play(j.animate.set_value(n - 1), run_time=4, rate_func=linear)
        self.add(texto(f"guardando decimales: {p_dec[-1]:.1f} px", 20, color=CURSOR).move_to(ax.c2p(0.62, 46)),
                 texto(f"redondeando cada paso: {p_mal[-1]:.0f} px", 20, color=RED).move_to(ax.c2p(1.45, 11)))
        pasos5 = -cadena(np.full(n, 5.0))[:, 0]
        self.wait(1.5)
        self.decir(f"Y a 5 °/s, {pasos5[100]:.3f} sube a 1: iría ×{np.round(pasos5).sum() / pasos5.sum():.2f} de rápido")
        self.wait(2.5)


class ZonaMuerta(Escena):
    """Por debajo de una rapidez el cursor no se mueve; si se resta en vez de cortar, no hay salto."""

    def construct(self):
        titulo = texto("Zona muerta", 34).to_edge(UP)
        self.play(Write(titulo))
        dz = 0.8
        a = ejes([0, 3, 1], [0, 3, 1], ancho=4.8, alto=3.5).move_to([-3.9, 0.25, 0])
        lx = texto("giro (°/s)", 18).next_to(a, DOWN, buff=0.08)
        ly = texto("lo que pasa (°/s)", 18).next_to(a, UP, buff=0.08)
        self.play(Create(a), FadeIn(lx, ly))
        banda = Rectangle(width=a.c2p(dz, 0)[0] - a.c2p(0, 0)[0], height=3.5, stroke_width=0, fill_color=GREY, fill_opacity=0.25).move_to(a.c2p(dz / 2, 1.5))
        nz = texto("0.8", 18, color=GREY_A).move_to(a.c2p(dz / 2, 1.4))
        self.play(FadeIn(banda, nz))
        corta = VGroup(Line(a.c2p(0, 0), a.c2p(dz, 0), color=RED, stroke_width=5), DashedLine(a.c2p(dz, 0), a.c2p(dz, dz), color=RED),
                       Line(a.c2p(dz, dz), a.c2p(3, 3), color=RED, stroke_width=5))
        resta = VGroup(Line(a.c2p(0, 0), a.c2p(dz, 0), color=FILTRO, stroke_width=5), Line(a.c2p(dz, 0), a.c2p(3, 3 - dz), color=FILTRO, stroke_width=5))
        n1 = texto("cortar: las páginas", 20, color=RED).move_to(a.c2p(1.4, 2.75))
        n2 = texto("restar: el ratón aéreo", 20, color=FILTRO).move_to(a.c2p(2.1, 0.75))
        self.decir("Cortar: bajo el borde cero, y sobre el borde lo que venga. Hay un salto")
        self.play(Create(corta), FadeIn(n1))
        self.wait(0.8)
        self.decir("Restar: bajo el borde cero, y sobre el borde lo que sobra. Sale de cero sin saltar")
        self.play(Create(resta), FadeIn(n2))
        self.wait(0.8)
        # un giro que crece muy despacio, por la cadena de verdad y cortando
        n = 300
        t = np.arange(n) * DT
        giro = 2.0 * t / t[-1]
        pasos = -cadena(giro)[:, 0] / DT                      # px/s
        sinz = -cadena(giro, deadzone=0.0)[:, 0] / DT
        cortado = np.where(sinz / 12 > dz, sinz, 0.0)
        b = ejes([0, 3, 1], [0, 30, 10], ancho=5.4, alto=3.5).move_to([3.3, 0.25, 0])
        ly2 = texto("cursor (px/s)", 18).next_to(b, UP, buff=0.08)
        lx2 = texto("segundos: el giro sube de 0 a 2 °/s", 18).next_to(b, DOWN, buff=0.08)
        self.play(Create(b), FadeIn(ly2, lx2))
        k = ValueTracker(2)
        c1 = always_redraw(lambda: linea(b, t[:int(k.get_value())], cortado[:int(k.get_value())], RED, 3))
        c2 = always_redraw(lambda: linea(b, t[:int(k.get_value())], pasos[:int(k.get_value())], FILTRO, 4))
        self.add(c1, c2)
        salto = cortado[cortado > 0][0]
        self.decir(f"Un giro que crece despacio: cortando, el cursor arranca de golpe a {salto:.0f} px/s")
        self.play(k.animate.set_value(n - 1), run_time=4, rate_func=linear)
        self.wait(1)
        # para qué sirve, y lo que cuesta
        rng = np.random.default_rng(4)
        nq = 2000
        quieto = 0.3 + 0.1 * rng.standard_normal(nq)
        sin_dz = np.abs(cadena(quieto, deadzone=0.0)[:, 0].sum())
        con_dz = np.abs(cadena(quieto)[:, 0].sum())
        self.decir(f"Con 0.3 °/s de sesgo sobrante, en 20 s: sin zona muerta {sin_dz:.0f} px, con zona muerta {con_dz:.0f} px")
        self.wait(2.5)
        self.decir("Pero no puede ser grande: restar 0.8 quita 40 % a 2 °/s y 4 % a 20 °/s")
        self.wait(2.5)


class CurvaDeAceleracion(Escena):
    """La ganancia crece con la rapidez: lento para atinar, rápido para cruzar la pantalla."""

    def construct(self):
        titulo = texto("Curva de aceleración", 34).to_edge(UP)
        self.play(Write(titulo))
        g_lo, g_hi, v_lo, v_hi = 12, 30, 10, 120
        u = lambda v: np.clip((v - v_lo) / (v_hi - v_lo), 0, 1)
        gan = lambda v: g_lo + (g_hi - g_lo) * (3 * u(v) ** 2 - 2 * u(v) ** 3)
        a = ejes([0, 160, 40], [0, 36, 12], ancho=6.2, alto=3.0).move_to([-3.2, 0.8, 0])
        lx = texto("rapidez (°/s)", 18).next_to(a, DOWN, buff=0.08)
        ly = texto("ganancia (px/°)", 18).next_to(a, UP, buff=0.08)
        vs = np.linspace(0, 160, 161)
        c = linea(a, vs, gan(vs), RAYO, 4)
        marcas = VGroup(DashedLine(a.c2p(v_lo, 0), a.c2p(v_lo, g_lo), color=GREY_B), DashedLine(a.c2p(v_hi, 0), a.c2p(v_hi, g_hi), color=GREY_B))
        self.play(Create(a), FadeIn(lx, ly), Create(c), Create(marcas))
        f = MathTex(r"g = g_{lo} + (g_{hi}-g_{lo})\,(3u^2-2u^3)", font_size=34).move_to([3.7, 2.0, 0])
        f2 = MathTex(r"u = \frac{v - v_{lo}}{v_{hi}-v_{lo}}", font_size=34).next_to(f, DOWN, buff=0.2)
        self.play(Write(f), Write(f2))
        v = ValueTracker(0.0)
        punto = always_redraw(lambda: Dot(a.c2p(v.get_value(), float(gan(v.get_value()))), radius=0.09, color=RED))
        lect = cada(lambda: texto(f"{v.get_value():.0f} °/s  →  {float(gan(v.get_value())):.1f} px/°", 26, color=RED).move_to([3.7, 0.15, 0]))
        self.add(punto, lect)
        self.decir("Bajo 10 °/s, 12 px/° para atinar; sobre 120 °/s, 30 px/° para cruzar")
        self.play(v.animate.set_value(65), run_time=2)
        self.wait(0.5)
        self.play(v.animate.set_value(150), run_time=2)
        self.wait(0.6)
        # los mismos grados, en dos tiempos, por la cadena de verdad
        def vuelta(T):
            n = int(round(T * 100))
            q = np.arange(n + 50) / n
            r = np.where(q < 1, 20 / T * 6 * q * (1 - q), 0.0)
            return np.abs(np.cumsum(cadena(r)[:, 0])), r
        p_l, r_l = vuelta(4.0)
        p_r, r_r = vuelta(0.25)
        x0, esc = -5.6, 10.8 / 600
        filas = [(p_l, f"20° en 4 s (pico de {r_l.max():.1f} °/s)", CURSOR, -2.05), (p_r, f"20° en 0.25 s (pico de {r_r.max():.0f} °/s)", ORANGE, -2.75)]
        s = ValueTracker(0.0)
        for p, nom, col, y in filas:
            self.add(texto(nom, 20, color=col).move_to([x0, y + 0.28, 0], aligned_edge=LEFT))
            self.add(always_redraw(lambda p=p, col=col, y=y: Line([x0, y, 0], [x0 + 1e-3 + esc * p[int(s.get_value() * (len(p) - 1))], y, 0], color=col, stroke_width=9)))
            self.add(cada(lambda p=p, col=col, y=y: texto(f"{p[int(s.get_value() * (len(p) - 1))]:.0f} px", 20, color=col).next_to([x0 + esc * p[int(s.get_value() * (len(p) - 1))], y, 0], RIGHT, buff=0.12)))
        if getattr(self, "_rotulo", None):
            self.play(FadeOut(self._rotulo))
            self._rotulo = None
        self.play(s.animate.set_value(1), run_time=3.5, rate_func=linear)
        self.wait(3)


class Filtro1Euro(Escena):
    """Un suavizado cuyo corte sube con la rapidez: quieto suaviza mucho, rápido casi nada."""

    def construct(self):
        titulo = texto("Filtro 1€", 34).to_edge(UP)
        self.play(Write(titulo))
        f = MathTex(r"\alpha = \frac{1}{1 + \frac{1}{2\pi f_c \Delta t}}", r"\qquad f_c = f_{min} + \beta\,|\dot x|", font_size=34).next_to(titulo, DOWN, buff=0.12)
        self.play(Write(f))
        # el α del filtro es el promedio que olvida del capítulo 3 con τ = 1/(2π f_c): α = Δt / (τ + Δt)
        tau = 1 / (2 * np.pi * 2.0)
        assert np.isclose(OneEuro.alpha(2.0, DT), DT / (tau + DT))
        f2 = MathTex(r"\tau = \frac{1}{2\pi f_c} \quad\Rightarrow\quad \alpha = \frac{\Delta t}{\tau + \Delta t}", font_size=32)\
            .next_to(f, DOWN, buff=0.15)
        self.decir("Corte f_c: lo más lento que f_c pasa; lo más rápido se achica")
        self.wait(1.5)
        self.play(Write(f2))
        self.decir(f"τ es la constante de tiempo del capítulo 3: a 2 Hz, {1000 * tau:.0f} ms")
        self.wait(2)
        rng = np.random.default_rng(11)
        n = 200
        t = np.arange(n) * DT
        verdad = np.where(t >= 1.0, 100.0, 0.0)
        cruda = verdad + 1.5 * rng.standard_normal(n)
        e = OneEuro(2.0, 0.01, 1.0)
        fijo_a = OneEuro.alpha(2.0, DT)
        euro, fc, fijo, y = [], [], [], None
        for x in cruda:
            euro.append(e(float(x), DT))
            fc.append(2.0 + 0.01 * abs(e.dx))
            y = x if y is None else y + fijo_a * (x - y)
            fijo.append(y)
        euro, fc, fijo = map(np.array, (euro, fc, fijo))

        def lineas(ax, hasta):
            h = max(2, int(hasta))
            return VGroup(linea(ax, t[:h], cruda[:h], CRUDO, 2), linea(ax, t[:h], fijo[:h], RED, 4), linea(ax, t[:h], euro[:h], FILTRO, 4))
        # quieto: de cerca
        a = ejes([0, 1, 0.25], [-6, 6, 3], ancho=9.5, alto=3.0).move_to([0.6, -0.65, 0])
        ly = texto("tasa (°/s)", 18).next_to(a, LEFT, buff=0.12)
        self.play(Create(a), FadeIn(ly))
        k = ValueTracker(2)
        c = always_redraw(lambda: lineas(a, k.get_value()))
        self.add(c)
        tam = lambda v: float(np.std(v[20:100]))
        self.decir(f"Quieto: temblor de {tam(cruda):.1f} °/s. Los dos filtros lo bajan a unas {tam(euro):.1f} °/s")
        self.play(k.animate.set_value(100), run_time=2.5, rate_func=linear)
        self.wait(1.2)
        self.remove(c)
        self.play(FadeOut(a), FadeOut(ly))
        # arranque: de lejos
        b = ejes([0.8, 1.5, 0.2], [-10, 110, 50], ancho=9.5, alto=2.2).move_to([0.6, -0.1, 0])
        ly2 = texto("tasa (°/s)", 18).next_to(b, LEFT, buff=0.12)
        a2 = ejes([0.8, 1.5, 0.2], [0, 20, 10], ancho=9.5, alto=1.1).next_to(b, DOWN, buff=0.28)
        ly3 = texto("f_c (Hz)", 18).next_to(a2, LEFT, buff=0.12)
        self.play(Create(b), Create(a2), FadeIn(ly2, ly3))
        i0 = 80
        ti = t[i0:141]
        idx = ValueTracker(i0 + 2)
        par = lambda s: s[i0:max(i0 + 2, int(idx.get_value()))]
        tt = lambda: t[i0:max(i0 + 2, int(idx.get_value()))]
        c2 = always_redraw(lambda: VGroup(linea(b, tt(), par(cruda), CRUDO, 2), linea(b, tt(), par(fijo), RED, 4), linea(b, tt(), par(euro), FILTRO, 4),
                                          linea(a2, tt(), par(fc), FILTRO, 3)))
        self.add(c2)
        llega = lambda v: (np.argmax((t >= 1.0) & (v > 63)) - 100) * DT * 1000
        self.decir(f"Arrancar a 100 °/s: el corte fijo de 2 Hz tarda {llega(fijo):.0f} ms en llegar a 63 %; el 1€, {llega(euro):.0f} ms")
        self.play(idx.animate.set_value(i0 + len(ti) - 1), run_time=4, rate_func=linear)
        self.wait(1)
        self.add(texto("sin filtrar", 18, color=CRUDO).move_to(b.c2p(0.92, 40)), texto("corte fijo, 2 Hz", 18, color=RED).move_to(b.c2p(1.38, 60)),
                 texto("1€", 22, color=FILTRO).move_to(b.c2p(0.95, 88)))
        self.decir(f"El corte sube de {fc[50:100].mean():.0f} a {fc.max():.0f} Hz mientras la tasa cambia, y vuelve a bajar")
        self.wait(3)


class MapaLineal(Escena):
    """Una matriz 2×2 lleva (yaw, pitch) a (x, y): ganancias distintas por eje y ejes cruzados a 75°."""

    def construct(self):
        titulo = texto("Calibrar los dos ejes", 34).to_edge(UP)
        self.play(Write(titulo))
        a, b, ang = 5.3, 6.9, 75 * GRADO
        A = np.array([[a, b * np.cos(ang)], [0, b * np.sin(ang)]]) / 6.0     # a escala, para dibujar
        Am = A * 6.0
        centro = np.array([-2.9, -0.3, 0])
        U = 0.55
        P2 = lambda v: centro + U * np.array([v[0], v[1], 0])
        m = ValueTracker(0.0)                                 # 0: identidad; 1: A

        def transf(v):
            s = m.get_value()
            return ((1 - s) * np.eye(2) + s * A) @ np.asarray(v, float)

        def malla():
            g = VGroup()
            for i in range(-4, 5, 2):
                g.add(Line(P2(transf((i, -4))), P2(transf((i, 4))), color=BLUE_D, stroke_width=1.5))
                g.add(Line(P2(transf((-4, i))), P2(transf((4, i))), color=BLUE_D, stroke_width=1.5))
            return g
        circ = np.linspace(0, 2 * np.pi, 73)
        red = always_redraw(malla)
        e1 = always_redraw(lambda: flecha(P2((0, 0)), P2(transf((2.5, 0))), RED, 6))
        e2 = always_redraw(lambda: flecha(P2((0, 0)), P2(transf((0, 2.5))), FILTRO, 6))
        cir = always_redraw(lambda: VMobject().set_points_as_corners([P2(transf((3 * np.cos(c), 3 * np.sin(c)))) for c in circ]).set_stroke(RAYO, 4))
        self.add(red, e1, e2, cir)
        self.decir("Si cada eje valiera lo mismo, un círculo de la muñeca sería un círculo en el trazo")
        izq = VGroup(texto("1° de yaw", 22, color=RED), texto("1° de pitch", 22, color=FILTRO)).arrange(DOWN, aligned_edge=LEFT).move_to([2.7, 2.2, 0], aligned_edge=LEFT)
        self.play(FadeIn(izq))
        self.wait(1.2)
        self.decir("Medido al escribir: 5.3 mm por grado de yaw, 6.9 por grado de pitch, cruzados a 75°")
        self.play(m.animate.set_value(1.0), run_time=3)
        mat = MathTex(r"M = \begin{pmatrix}" + f"{Am[0, 0]:.2f} & {Am[0, 1]:.2f}" + r"\\" + f"{Am[1, 0]:.2f} & {Am[1, 1]:.2f}" + r"\end{pmatrix}\ \text{mm/}^\circ", font_size=36).move_to([4.1, 0.75, 0])
        col = texto("cada columna: adónde va un grado", 20, color=GREY_A).next_to(mat, DOWN, buff=0.18)
        self.play(Write(mat), FadeIn(col))
        self.wait(1.5)
        razon = VGroup(texto(f"{b:.1f} / {a:.1f} = ×{b / a:.2f} en vertical", 24, color=FILTRO)).next_to(col, DOWN, buff=0.3)
        self.play(FadeIn(razon))
        self.decir("El círculo sale elipse y torcido. La ganancia sola no lo arregla: falta el cruce")
        self.wait(2)
        self.decir("Hoy el cursor usa yaw y pitch tal cual: para él, la malla sigue recta")
        self.play(m.animate.set_value(0.0), run_time=2)
        self.wait(1)
        self.decir("Para copiar lo que hace el dedo tendría que usar esa misma M")
        inv = MathTex(r"\binom{x}{y} = g\, M \binom{\text{yaw}}{\text{pitch}}", font_size=36).next_to(razon, DOWN, buff=0.3)
        self.play(Write(inv))
        self.play(m.animate.set_value(1.0), run_time=2)
        self.wait(1)
        self.decir("Esto todavía no está aplicado: hoy solo hay gain_x y gain_y, sin cruce")
        self.wait(2.5)


class Potencias(Escena):
    """2^k es duplicar k veces; log2(x) cuenta cuántas veces hay que duplicar para llegar a x."""

    def construct(self):
        titulo = texto("Potencias y logaritmos", 34).to_edge(UP)
        self.play(Write(titulo))
        y0, H, x0, paso = -2.3, 4.6 / 256, -4.7, 1.18
        base = Line([x0 - 0.6, y0, 0], [x0 + 8.6 * paso, y0, 0], color=GREY_B)
        self.play(Create(base))
        barras = VGroup()
        for k in range(9):
            v = 2 ** k
            bar = Rectangle(width=0.8, height=max(v * H, 0.02), stroke_width=0, fill_color=BLUE, fill_opacity=0.85).move_to([x0 + k * paso, y0, 0], aligned_edge=DOWN)
            eti = VGroup(texto(str(v), 22).next_to(bar, UP, buff=0.08), MathTex(f"2^{k}", font_size=28, color=RAYO).move_to([x0 + k * paso, y0 - 0.38, 0]))
            barras.add(VGroup(bar, eti))
        self.decir("Duplicar k veces, empezando en 1: eso es 2 elevado a k")
        for k, b in enumerate(barras):
            self.play(GrowFromEdge(b[0], DOWN), FadeIn(b[1]), run_time=0.45)
        self.wait(0.6)
        self.decir("El logaritmo es la pregunta al revés: ¿cuántas veces duplico para llegar?")
        self.wait(1.2)
        marca = SurroundingRectangle(barras[6], color=RAYO, buff=0.06)
        f1 = MathTex(r"\log_2 64 = 6", font_size=44).move_to([-1.8, 2.0, 0])
        self.play(Create(marca), Write(f1))
        self.wait(1.4)
        self.play(FadeOut(marca))
        f2 = MathTex(r"\log_2 3 = " + f"{np.log2(3):.3f}", font_size=44).next_to(f1, DOWN, buff=0.2)
        self.decir("No hace falta llegar justo: 3 está entre 2 y 4, y su logaritmo entre 1 y 2")
        self.play(Write(f2))
        self.wait(1.6)
        f3 = MathTex(r"\log_2(8\cdot 4) = 3 + 2 = 5", font_size=40).next_to(f2, DOWN, buff=0.2)
        self.decir("Multiplicar por 8 y por 4 es duplicar 3 veces y después 2: los logaritmos se suman")
        self.play(Write(f3))
        self.wait(2)
        self.decir(f"Por eso crece tan poco: de 1 a 1000 solo hay {np.log2(1000):.2f} duplicaciones")
        self.wait(2.5)

        # exponentes que no son enteros, la base e y ln
        self.play(*[FadeOut(m) for m in (barras, base, f1, f2, f3, self._rotulo)])
        self._rotulo = None
        ax = ejes([-2, 3, 1], [0, 10, 2], ancho=7.4, alto=4.8).move_to([-2.4, -0.3, 0])
        xs = np.linspace(-2, 3, 201)
        xe = xs[xs <= np.log(10)]
        dos = linea(ax, xs, 2 ** xs, BLUE, 4)
        puntos = VGroup(*[Dot(ax.c2p(k, 2 ** k), radius=0.07, color=RAYO) for k in range(-2, 4)])
        n2 = MathTex("2^x", color=BLUE, font_size=34).move_to(ax.c2p(2.75, 4.6))
        self.play(Create(ax), FadeIn(puntos))
        self.decir("Los enteros son duplicar; la curva 2^x llena lo que hay en medio")
        self.play(Create(dos), FadeIn(n2), run_time=1.5)
        panel = []

        def anotar(tex, color=WHITE):
            m = MathTex(tex, font_size=36, color=color).move_to([3.9, 2.3 - 0.75 * len(panel), 0], aligned_edge=LEFT).shift(LEFT * 1.4)
            panel.append(m)
            self.play(Write(m))

        def marca(x, y, color):
            return VGroup(DashedLine(ax.c2p(x, 0), ax.c2p(x, y), color=color), DashedLine(ax.c2p(-2, y), ax.c2p(x, y), color=color),
                          Dot(ax.c2p(x, y), radius=0.07, color=color))

        m1 = marca(0.5, 2 ** 0.5, RAYO)
        self.play(Create(m1))
        anotar(r"2^{1/2} = " + f"{2 ** 0.5:.3f}")
        self.decir(f"Media duplicación: {2 ** 0.5:.3f} · {2 ** 0.5:.3f} = {(round(2 ** 0.5, 3)) ** 2:.2f}, casi 2")
        self.wait(1.5)
        anotar(r"2^{1/12} = " + f"{2 ** (1 / 12):.4f}")
        self.decir(f"Doce pasos seguidos de ×{2 ** (1 / 12):.4f} también dan 2 (capítulo 11)")
        self.wait(1.8)
        m2 = marca(-1, 0.5, RAYO)
        self.play(Create(m2))
        anotar(r"2^{-1} = \tfrac12")
        self.decir("Hacia atrás se divide: cada paso a la izquierda, la mitad")
        self.wait(1.5)
        ese = linea(ax, xe, np.exp(xe), ORANGE, 4)
        ne = MathTex("e^x", color=ORANGE, font_size=34).move_to(ax.c2p(1.55, 7.6))
        self.play(FadeOut(m1, m2), Create(ese), FadeIn(ne), run_time=1.5)
        anotar(r"e = " + f"{np.e:.3f}", ORANGE)
        self.decir(f"Con base e = {np.e:.3f}, el número del capítulo 3, la curva es e^x", ORANGE)
        self.wait(1.5)
        m3 = marca(np.log(2), 2, ORANGE)
        self.play(Create(m3))
        anotar(r"\ln 2 = " + f"{np.log(2):.3f}", ORANGE)
        self.decir(f"ln es la pregunta al revés con base e: e a la {np.log(2):.3f} da 2", ORANGE)
        self.wait(1.8)
        assert np.isclose(np.log(37.0), np.log(2) * np.log2(37.0))
        anotar(r"\ln x = " + f"{np.log(2):.3f}" + r"\,\log_2 x")
        self.decir("Cambiar de base es multiplicar por un número fijo")
        self.wait(2.5)


class LeyDeFitts(Escena):
    """El tiempo para atinar crece con log2(D/W + 1); dividido por el tiempo da bits por segundo."""

    def construct(self):
        titulo = texto("Ley de Fitts", 34).to_edge(UP)
        self.play(Write(titulo))
        y = 1.75
        E = 8.6 / 1600
        Dv, Wv = ValueTracker(300.0), ValueTracker(100.0)
        x0 = -5.5
        ini = Dot([x0, y, 0], radius=0.09, color=WHITE)
        blanco = always_redraw(lambda: Rectangle(width=Wv.get_value() * E, height=0.75, stroke_width=0, fill_color=RED, fill_opacity=0.8).move_to([x0 + Dv.get_value() * E, y, 0]))
        regla = always_redraw(lambda: DoubleArrow([x0, y - 0.62, 0], [x0 + Dv.get_value() * E, y - 0.62, 0], buff=0, stroke_width=3, color=GREY_B, tip_length=0.14))
        idn = lambda: np.log2(Dv.get_value() / Wv.get_value() + 1)
        lect = cada(lambda: texto(f"D = {Dv.get_value():.0f} px   W = {Wv.get_value():.0f} px   ID = log2(D/W + 1) = {idn():.2f} bits", 24).move_to([0, y - 1.05, 0]))
        self.add(ini, blanco, regla, lect)
        self.decir("Lejos y chico es difícil. Lo que cuenta es D/W, no los píxeles")
        self.wait(1)
        self.play(Dv.animate.set_value(700), run_time=1.5)
        self.wait(0.5)
        self.play(Dv.animate.set_value(1500), run_time=1.5)
        self.decir("D/W + 1 se duplicó dos veces: dos bits más")
        self.wait(1.2)
        self.play(Dv.animate.set_value(600), Wv.animate.set_value(200), run_time=1.8)
        self.decir("Agrandar todo por igual no cambia nada: D = 600 y W = 200 es D/W = 3 otra vez")
        self.wait(1.4)
        # datos inventados: dos ajustes con la misma recta de forma, MT = a + b·ID
        rng = np.random.default_rng(5)
        ids = np.repeat([2.0, 3.0, 4.0], 6)
        ajustes = {"ajuste A": (0.30, 0.34, CURSOR), "ajuste B": (0.20, 0.22, ORANGE)}
        self.play(*[FadeOut(m) for m in (ini, blanco, regla, lect)])
        ax = ejes([1, 5, 1], [0, 2.4, 0.8], ancho=6.4, alto=4.2).move_to([-2.6, 0.05, 0])
        lx = texto("ID (bits)", 18).next_to(ax, DOWN, buff=0.05)
        ly = texto("tiempo (s)", 18).next_to(ax, UP, buff=0.04).shift(LEFT * 2.3)
        self.play(Create(ax), FadeIn(lx, ly))
        self.decir("Con 18 blancos inventados por ajuste: el tiempo crece en línea recta con el ID")
        panel = VGroup()
        for nombre, (a, b, col) in ajustes.items():
            mt = a + b * ids + 0.06 * rng.standard_normal(len(ids))
            pts = VGroup(*[Dot(ax.c2p(i + rng.uniform(-0.08, 0.08), v), radius=0.05, color=col) for i, v in zip(ids, mt)])
            recta = Line(ax.c2p(1.5, a + 1.5 * b), ax.c2p(4.5, a + 4.5 * b), color=col, stroke_width=3)
            tp = float(np.mean(ids / mt))
            panel.add(texto(f"{nombre}: {tp:.1f} bits por segundo", 24, color=col))
            self.play(LaggedStart(*[FadeIn(p) for p in pts], lag_ratio=0.04), Create(recta), run_time=1.3)
        panel.arrange(DOWN, aligned_edge=LEFT, buff=0.2).move_to([3.7, -0.1, 0])
        f = MathTex(r"TP = \frac{ID}{\text{tiempo}}", font_size=38).next_to(panel, UP, buff=0.25)
        self.play(Write(f), FadeIn(panel))
        self.decir("Un número por ajuste: más bits por segundo es mejor, sin decir \"se siente mejor\"")
        self.wait(3)
