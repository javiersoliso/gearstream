"""Animaciones del capítulo 9 (El cuerpo en 3D), una por concepto.

    python docs/curso/animaciones/render.py cap09 Esqueleto ...       # a GIF en docs/curso/media/cap09/
    python -m manim -ql docs/curso/animaciones/cap09.py Verosimilitud  # una, rápido, para mirarla

Los números salen de server/web/mocapmath.js y server/web/armfilter.js: datos_cap09.js corre esa cuenta (el cuerpo,
las lecturas del reloj, la reconstrucción y una corrida del filtro del codo sobre el brazo de tools/test_armfilter.js)
y este archivo dibuja lo que da. Su JSON se guarda en media/, y se rehace si cambia alguno de esos archivos.
"""
import json
import os
import subprocess

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..", "..", "..")
FUENTES = [os.path.join(AQUI, "datos_cap09.js"), os.path.join(RAIZ, "server", "web", "mocapmath.js"),
           os.path.join(RAIZ, "server", "web", "armfilter.js"), os.path.join(RAIZ, "tools", "test_cuerpo.js"),
           os.path.join(RAIZ, "tools", "test_armfilter.js")]
CACHE = os.path.join(AQUI, "media", "datos_cap09.json")
if not os.path.exists(CACHE) or os.path.getmtime(CACHE) < max(os.path.getmtime(f) for f in FUENTES):
    salida = subprocess.run(["node", FUENTES[0]], capture_output=True, check=True, text=True, encoding="utf-8").stdout
    with open(CACHE, "w", encoding="utf-8") as f:
        f.write(salida)
with open(CACHE, encoding="utf-8") as f:
    D = json.load(f)

GRADO = np.pi / 180
VERDAD, RECONS, HUESO, NUBE, CRUDO = TEAL, "#FF7F6E", GREY_A, YELLOW, GREY_B
L1, L2 = 0.29, 0.27                                  # el brazo y el antebrazo del mocap


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v * 0


def rot(v, k, a):
    k, v = unit(k), np.asarray(v, float)
    return v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * np.dot(k, v) * (1 - np.cos(a))


def ik(a, t, l1, l2, polo):
    """La cuenta de `ik` de mocapmath.js; abajo se compara con su resultado."""
    a, t, polo = (np.asarray(p, float) for p in (a, t, polo))
    v = t - a
    d = np.linalg.norm(v)
    dire = v / d if d > 1e-9 else np.array([0, -1.0, 0])
    d = min(max(d, abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    x = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = np.sqrt(max(0.0, l1 * l1 - x * x))
    pv = polo - a
    pd = unit(pv - dire * np.dot(pv, dire))
    return a + dire * x + pd * h, a + dire * d, x, h, d


_p = ik([0, 1.4, 0], [0.2, 1.2, -0.35], L1, L2, [0, 1, -0.5])
assert np.allclose(_p[0], D["ikPrueba"]["codo"]) and np.allclose(_p[1], D["ikPrueba"]["muneca"])


def fk_lado(flex, codo):
    """De costado: el brazo cuelga y se levanta flex; el antebrazo sigue al brazo y dobla codo más."""
    f, e = flex * GRADO, (flex + codo) * GRADO
    u = np.array([np.sin(f), -np.cos(f)])
    return L1 * u, L1 * u + L2 * np.array([np.sin(e), -np.cos(e)])


for _c in D["fk"]:
    _a, _b = fk_lado(_c["flex"], _c["elbow"])
    assert np.allclose(_a, _c["codo"]) and np.allclose(_b, _c["muneca"])


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
                 max_tip_length_to_length_ratio=0.2)


def ejes(x, y, ancho=9.5, alto=4.0, numeros=True, **kw):
    return Axes(x_range=x, y_range=y, x_length=ancho, y_length=alto, tips=False,
                axis_config={"include_numbers": numeros, "font_size": 18}, **kw)


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


def monigote(segs, E, base, color=HUESO, w=5, y0=0.0):
    """Los huesos de datos_cap09.js: (x, altura) en metros, con los pies cerca de y0."""
    q = lambda p: np.array([base[0] + E * p[0], base[1] + E * (p[1] - y0), 0])
    return VGroup(*[Line(q(a), q(b), color=color, stroke_width=w) for a, b in segs])


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
class Esqueleto(Escena):
    """Huesos de largo fijo unidos por articulaciones; la pose son los ángulos de cada una."""

    def construct(self):
        titulo = texto("El esqueleto", 34).to_edge(UP)
        self.play(Write(titulo))
        E = 3.2
        frente = monigote(D["frente"], E, (-3.9, -2.75))
        nudos = VGroup(*[Dot(s.get_end(), radius=0.06, color=RED) for s in frente])
        self.play(LaggedStart(*[Create(s) for s in frente], lag_ratio=0.08), run_time=2)
        self.decir("Un cuerpo de palitos: cada hueso mide siempre lo mismo")
        self.play(FadeIn(nudos))
        self.wait(1)
        k = ValueTracker(0)
        lado = always_redraw(lambda: monigote(D["levantar"][int(k.get_value())], E, (1.2, -2.75)))
        self.add(lado)
        izq = texto("de frente", 20, color=GREY_B).move_to([-3.9, 2.8, 0])
        der = texto("de costado", 20, color=GREY_B).move_to([1.2, 2.8, 0])
        self.play(FadeIn(izq, der))
        self.decir("Las articulaciones son lo único que cambia: la pose es una lista de ángulos")
        lect = cada(lambda: VGroup(texto(f"hombro {110 * k.get_value() / 30:.0f}°", 22, color=RED),
                                            texto(f"codo {12 + 60 * k.get_value() / 30:.0f}°", 22, color=RED),
                                            texto("brazo 0.29 m", 22), texto("antebrazo 0.27 m", 22)).arrange(DOWN, aligned_edge=LEFT, buff=0.1).move_to([4.2, 1.4, 0], aligned_edge=LEFT))
        self.add(lect)
        self.play(k.animate.set_value(30), run_time=3)
        self.play(k.animate.set_value(10), run_time=1.6)
        self.wait(0.6)
        self.decir("En el mocap, 0.29 y 0.27 m; en el filtro del codo y el avatar, 0.30 y 0.25 m")
        self.wait(2.5)


class CinematicaDirecta(Escena):
    """De los ángulos a las posiciones, encadenando giros desde el tronco hacia la mano."""

    def construct(self):
        titulo = texto("Cinemática directa", 34).to_edge(UP)
        self.play(Write(titulo))
        E, S = 7.0, np.array([-3.4, 0.75, 0])
        flex, codo = ValueTracker(0.0), ValueTracker(0.0)
        P = lambda q: S + E * np.array([q[0], q[1], 0])
        pts = lambda: fk_lado(flex.get_value(), codo.get_value())
        brazo = always_redraw(lambda: Line(S, P(pts()[0]), color=BLUE, stroke_width=10))
        ante = always_redraw(lambda: Line(P(pts()[0]), P(pts()[1]), color=VERDAD, stroke_width=10))
        nudos = always_redraw(lambda: VGroup(Dot(S, radius=0.11, color=WHITE), Dot(P(pts()[0]), radius=0.11, color=WHITE), Dot(P(pts()[1]), radius=0.11, color=RED)))
        nh = texto("hombro", 20, color=GREY_B).next_to(S, UP, buff=0.14)
        self.add(brazo, ante, nudos)
        self.play(FadeIn(nh))
        f1 = MathTex(r"\text{codo} = \text{hombro} + L_1\,u", font_size=36).move_to([3.5, 2.2, 0])
        f2 = MathTex(r"\text{muñeca} = \text{codo} + L_2\,f", font_size=36).next_to(f1, DOWN, buff=0.2)
        self.play(Write(f1), Write(f2))

        def cifras():
            c, m = pts()
            return VGroup(texto(f"hombro: {flex.get_value():.0f}°", 24, color=BLUE), texto(f"codo: {codo.get_value():.0f}°", 24, color=VERDAD),
                          texto(f"muñeca a {100 * m[0]:+.1f} cm adelante", 22), texto(f"y {100 * m[1]:+.1f} cm de alto", 22)).arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to([1.5, 0.3, 0], aligned_edge=LEFT)
        lect = cada(cifras)
        self.add(lect)
        self.decir("Girar el hombro se lleva todo lo que cuelga de él")
        self.play(flex.animate.set_value(50), run_time=2)
        self.wait(0.4)
        self.decir("Girar el codo mueve solo el antebrazo, a partir de donde quedó")
        self.play(codo.animate.set_value(70), run_time=2)
        self.wait(0.4)
        self.decir("Se va del tronco a la mano: cada hueso parte de donde terminó el anterior")
        self.play(flex.animate.set_value(100), run_time=1.6)
        self.play(flex.animate.set_value(25), codo.animate.set_value(110), run_time=2)
        self.wait(0.5)
        # el orden: primero levantar y después separar, o al revés
        baja = np.array([0, -1.0, 0])
        der, adel = np.array([1.0, 0, 0]), np.array([0, 0, -1.0])
        u1 = rot(rot(baja, der, 60 * GRADO), adel, 40 * GRADO)
        u2 = rot(rot(baja, adel, 40 * GRADO), der, 60 * GRADO)
        self.decir(f"En 3D el orden importa: 60° y 40° al revés dejan el codo {100 * L1 * np.linalg.norm(u1 - u2):.0f} cm más allá", size=24)
        self.wait(2.5)


class Trayectorias(Escena):
    """Cómo se mueve la pose en el tiempo: una fase periódica, curvas suaves entre íconos, un círculo."""

    def construct(self):
        titulo = texto("La pose en el tiempo", 34).to_edge(UP)
        self.play(Write(titulo))
        E = 2.9
        k = ValueTracker(0)
        n = len(D["marcha"])
        cuerpo = always_redraw(lambda: monigote(D["marcha"][int(k.get_value()) % n], E, (-4.7, -2.6)))
        suelo = Line([-6.3, -2.6, 0], [-3.1, -2.6, 0], color=GREY_C)
        self.play(Create(suelo))
        self.add(cuerpo)
        F = D["fase"]
        t, brazo, rodilla = np.array(F["t"]), np.array(F["brazo"]), np.array(F["rodilla"])
        ax = ejes([0, round(t[-1], 1), 1.1], [-30, 60, 30], ancho=7.6, alto=3.4, numeros=False).move_to([2.1, 0.3, 0])
        marcas = VGroup(*[texto(f"{v}°", 16, color=GREY_B).next_to(ax.c2p(0, v), LEFT, buff=0.1) for v in (-30, 0, 30, 60)])
        lx = texto("3 ciclos de 1.10 s", 18, color=GREY_B).next_to(ax, DOWN, buff=0.08)
        self.play(Create(ax), FadeIn(marcas, lx))
        c1, c2 = linea(ax, t, brazo, BLUE, 4), linea(ax, t, rodilla, ORANGE, 4)
        self.play(Create(c1), Create(c2), run_time=1.2)
        self.add(texto("hombro izquierdo: −20°·sen(fase)", 20, color=BLUE).move_to(ax.c2p(1.0, -24)), texto("rodilla", 20, color=ORANGE).move_to(ax.c2p(0.45, 56)))
        cursor = always_redraw(lambda: DashedLine(ax.c2p((k.get_value() % (3 * n)) / (3 * n) * t[-1], -30), ax.c2p((k.get_value() % (3 * n)) / (3 * n) * t[-1], 60), color=RED))
        self.add(cursor)
        self.decir("Caminar: una fase que da vueltas y cada ángulo es una función de ella")
        self.play(k.animate.set_value(3 * n - 1), run_time=5, rate_func=linear)
        self.wait(0.4)
        self.clear()
        self.add(titulo)
        self._rotulo = None
        A = D["apunta"]
        t, x, y = np.array(A["t"]), np.array(A["x"]), np.array(A["y"])
        a2 = ejes([0, 10, 2], [-0.7, 0.7, 0.35], ancho=6.6, alto=3.4).move_to([-3.0, 0.2, 0])
        lx2 = texto("segundos", 18).next_to(a2, DOWN, buff=0.06)
        ly2 = texto("metros en la pantalla", 18).next_to(a2, UP, buff=0.06)
        self.play(Create(a2), FadeIn(lx2, ly2))
        s = ValueTracker(2)
        c_x = always_redraw(lambda: linea(a2, t[:int(s.get_value())], x[:int(s.get_value())], RED, 4))
        c_y = always_redraw(lambda: linea(a2, t[:int(s.get_value())], y[:int(s.get_value())], GREEN, 4))
        W, H, E2 = 1.6, 0.9, 3.5
        C = np.array([3.5, 0.2, 0])
        marco = Rectangle(width=W * E2, height=H * E2, color=GREY_B).move_to(C)
        Q = lambda i: C + E2 * np.array([x[i], y[i], 0])
        traza = always_redraw(lambda: VMobject().set_points_as_corners([Q(i) for i in range(int(s.get_value()))]).set_stroke(RAYO_C, 3))
        punta = always_redraw(lambda: Dot(Q(int(s.get_value()) - 1), radius=0.09, color=RAYO_C))
        self.add(c_x, c_y, texto("x", 22, color=RED).move_to(a2.c2p(9.3, 0.55)), texto("y", 22, color=GREEN).move_to(a2.c2p(9.7, 0.55)))
        self.play(Create(marco))
        self.add(traza, punta)
        self.decir("Apuntar: de ícono en ícono con 3u² − 2u³, sin golpes, y después un círculo")
        self.play(s.animate.set_value(len(t)), run_time=7, rate_func=linear)
        self.wait(2)


RAYO_C = YELLOW


class LeyDeCosenos(Escena):
    """c² = a² + b² − 2ab cos C: con los tres lados de un triángulo se saben sus ángulos."""

    def construct(self):
        titulo = texto("La ley de los cosenos", 34).to_edge(UP)
        self.play(Write(titulo))
        a, b = 4.0, 3.0
        C = np.array([-3.9, -1.7, 0])
        ang = ValueTracker(50 * GRADO)
        A = lambda: C + b * np.array([np.cos(ang.get_value()), np.sin(ang.get_value()), 0])
        B = C + a * RIGHT
        lado_a = Line(C, B, color=BLUE, stroke_width=7)
        lado_b = always_redraw(lambda: Line(C, A(), color=GREEN, stroke_width=7))
        lado_c = always_redraw(lambda: Line(A(), B, color=RED, stroke_width=7))
        arco = always_redraw(lambda: Arc(radius=0.6, start_angle=0, angle=ang.get_value(), arc_center=C, color=YELLOW, stroke_width=4))
        na = texto("a = 4", 22, color=BLUE).next_to(lado_a, DOWN, buff=0.1)
        nb = always_redraw(lambda: texto("b = 3", 22, color=GREEN).move_to((C + A()) / 2 + 0.42 * np.array([-np.sin(ang.get_value()), np.cos(ang.get_value()), 0])))
        nc = always_redraw(lambda: texto("c", 24, color=RED).move_to((A() + B) / 2 + 0.3 * unit(np.cross(B - A(), [0, 0, -1]))))
        self.add(lado_a, lado_b, lado_c, arco)
        self.play(FadeIn(na))
        self.add(nb, nc)
        f = MathTex(r"c^2 = a^2 + b^2 - 2ab\cos C", font_size=42).move_to([3.2, 2.2, 0])
        self.play(Write(f))
        x0, esc = 0.7, 6.0 / 60
        c2 = lambda: a * a + b * b - 2 * a * b * np.cos(ang.get_value())
        barras = always_redraw(lambda: VGroup(
            Line([x0, 0.9, 0], [x0 + esc * (a * a + b * b), 0.9, 0], color=GREY_B, stroke_width=14),
            Line([x0 + esc * (a * a + b * b), 0.45, 0], [x0 + esc * c2() + 1e-3, 0.45, 0], color=YELLOW, stroke_width=14),
            Line([x0, 0.0, 0], [x0 + esc * c2() + 1e-3, 0.0, 0], color=RED, stroke_width=14)))
        rotul = always_redraw(lambda: VGroup(
            texto("a² + b² = 25", 20, color=GREY_B).move_to([x0, 1.2, 0], aligned_edge=LEFT),
            texto(f"−2ab cos C = {round(-2 * a * b * np.cos(ang.get_value()), 1) + 0.0:+.1f}", 20, color=YELLOW).move_to([x0, -0.65, 0], aligned_edge=LEFT),
            texto(f"c² = {c2():.1f}    C = {ang.get_value() / GRADO:.0f}°", 22, color=RED).move_to([x0, -1.05, 0], aligned_edge=LEFT)))
        self.add(barras, rotul)
        self.decir("Con ángulo agudo, c queda más corto de lo que daría Pitágoras")
        self.wait(1)
        self.play(ang.animate.set_value(90 * GRADO), run_time=2)
        self.decir("Con C = 90° el coseno vale cero: es Pitágoras, 3-4-5")
        self.wait(1.2)
        self.play(ang.animate.set_value(135 * GRADO), run_time=2)
        self.decir("Con ángulo obtuso, el coseno es negativo y c sale más largo")
        self.wait(1.2)
        self.decir(f"Y al revés: con brazo 0.29, antebrazo 0.27 y hombro-muñeca 0.40 m, el codo abre {np.arccos((L1**2 + L2**2 - 0.16) / (2 * L1 * L2)) / GRADO:.0f}°")
        self.wait(3)


class CinematicaInversa(Escena):
    """Dado dónde debe ir la muñeca, el codo sale de la ley de los cosenos y de un polo."""

    def construct(self):
        titulo = texto("Cinemática inversa de dos huesos", 34).to_edge(UP)
        self.play(Write(titulo))
        E, S = 6.0, np.array([-4.4, 1.3, 0])
        P = lambda q: S + E * np.array([q[0], q[1], 0])
        ob = ValueTracker(0.0)
        lado = ValueTracker(-1.0)
        objetivo = lambda: np.array([0.30 + 0.12 * np.cos(ob.get_value()), -0.14 - 0.10 * np.sin(ob.get_value()), 0])
        extra = ValueTracker(1.0)
        tgt = lambda: objetivo() * extra.get_value()
        sol = lambda: ik([0, 0, 0], tgt(), L1, L2, [0.1, lado.get_value(), 0])
        recta = always_redraw(lambda: DashedLine(S, P(sol()[1]), color=GREY_B))
        pie = lambda: unit(sol()[1]) * sol()[2]
        altura = always_redraw(lambda: Line(P(pie()), P(sol()[0]), color=YELLOW, stroke_width=4))
        brazo = always_redraw(lambda: Line(S, P(sol()[0]), color=BLUE, stroke_width=9))
        ante = always_redraw(lambda: Line(P(sol()[0]), P(sol()[1]), color=VERDAD, stroke_width=9))
        nudos = always_redraw(lambda: VGroup(Dot(S, radius=0.1, color=WHITE), Dot(P(sol()[0]), radius=0.1, color=WHITE)))
        blanco = always_redraw(lambda: Circle(0.14, color=RED, stroke_width=4).move_to(P(tgt())))
        self.add(recta, altura, brazo, ante, nudos, blanco)
        f1 = MathTex(r"x = \frac{L_1^2 - L_2^2 + d^2}{2d}", font_size=38).move_to([3.7, 2.1, 0])
        f2 = MathTex(r"h = \sqrt{L_1^2 - x^2}", font_size=38).next_to(f1, DOWN, buff=0.22)
        self.play(Write(f1), Write(f2))
        lect = cada(lambda: VGroup(texto(f"d = {100 * sol()[4]:.1f} cm", 24), texto(f"x = {100 * sol()[2]:.1f} cm", 24), texto(f"h = {100 * sol()[3]:.1f} cm", 24, color=YELLOW)).arrange(DOWN, aligned_edge=LEFT, buff=0.1).move_to([2.6, -0.4, 0], aligned_edge=LEFT))
        self.add(lect)
        self.decir("El triángulo tiene sus tres lados: L₁, L₂ y d. El codo sale de la cuenta")
        self.play(ob.animate.set_value(2 * np.pi), run_time=4, rate_func=linear)
        self.decir("Pero hay dos triángulos en el plano. El polo dice hacia qué lado se dobla")
        self.play(lado.animate.set_value(1.0), run_time=0.01)
        self.wait(1.2)
        self.play(lado.animate.set_value(-1.0), run_time=0.01)
        self.wait(0.6)
        self.decir("Si el objetivo está lejos, d se recorta a L₁ + L₂: la muñeca llega hasta donde puede")
        self.play(extra.animate.set_value(1.9), run_time=2.5)
        self.wait(1)
        self.play(extra.animate.set_value(1.0), run_time=1)
        self.clear()
        self.add(titulo)
        self._rotulo = None
        # en 3D, los codos posibles son un círculo alrededor de la recta hombro-muñeca
        az, el, E3 = 0.0, 18 * GRADO, 7.5
        cam = np.array([np.sin(az) * np.cos(el), np.sin(el), np.cos(az) * np.cos(el)])
        der = np.array([np.cos(az), 0, -np.sin(az)])
        arr = np.cross(cam, der)
        centro = np.array([-3.3, 0.8, 0])
        pr = lambda p: centro + E3 * np.array([np.dot(p, der), np.dot(p, arr), 0])
        hombro, obj = np.zeros(3), np.array([0.34, -0.2, -0.2])
        eje = unit(obj - hombro)
        base = np.cross(eje, [1.0, 0, 0])
        giro = ValueTracker(0.0)
        codo_de = lambda a: ik(hombro, obj, L1, L2, rot(base, eje, a))[0]
        anillo = VMobject().set_points_as_corners([pr(codo_de(a)) for a in np.linspace(0, 2 * np.pi, 61)]).set_stroke(YELLOW, 3)
        self.play(Create(anillo), FadeIn(DashedLine(pr(hombro), pr(obj), color=GREY_B)))
        b3 = always_redraw(lambda: Line(pr(hombro), pr(codo_de(giro.get_value())), color=BLUE, stroke_width=9))
        a3 = always_redraw(lambda: Line(pr(codo_de(giro.get_value())), pr(obj), color=VERDAD, stroke_width=9))
        self.add(b3, a3, Dot(pr(hombro), radius=0.1), Dot(pr(obj), radius=0.1, color=RED))
        r = np.linalg.norm(np.cross(codo_de(0) - hombro, eje))
        self.add(texto(f"¿De cuántas maneras? Infinitas: un círculo de {100 * r:.1f} cm de radio", 26).move_to([1.0, 2.5, 0]))
        self.decir("Con el hombro y la muñeca fijos, el codo aún puede dar la vuelta. El polo elige uno")
        self.play(giro.animate.set_value(2 * np.pi), run_time=5, rate_func=linear)
        self.wait(1.5)


class FabricarRuido(Escena):
    """Números al azar con forma de campana (Box–Muller) y una semilla para que el azar se repita."""

    def construct(self):
        titulo = texto("Fabricar ruido", 34).to_edge(UP)
        self.play(Write(titulo))
        f = MathTex(r"z = \sqrt{-2\ln u}\,\cos(2\pi v)", font_size=38).next_to(titulo, DOWN, buff=0.14).shift(LEFT * 3.2)
        self.play(Write(f))
        cuadro = Square(3.2, color=GREY_B).move_to([-4.3, -0.65, 0])
        nu = texto("u y v: uniformes de 0 a 1", 20, color=GREY_B).next_to(cuadro, DOWN, buff=0.08)
        self.play(Create(cuadro), FadeIn(nu))
        uv = np.array(D["uv"])
        z = np.array(D["normales"])
        assert np.allclose(np.sqrt(-2 * np.log(uv[:, 0])) * np.cos(2 * np.pi * uv[:, 1]), z[:len(uv)])
        puntos = VGroup(*[Dot(cuadro.get_corner(DL) + 3.2 * np.array([u, v, 0]), radius=0.022, color=BLUE_B) for u, v in uv])
        bins = np.linspace(-4, 4, 33)
        ancho = bins[1] - bins[0]
        ax = ejes([-4, 4, 1], [0, 0.5, 0.25], ancho=6.6, alto=3.4).move_to([2.9, -0.5, 0])
        self.play(Create(ax))
        k = ValueTracker(10)

        def barras():
            h, _ = np.histogram(z[:int(k.get_value())], bins=bins)
            d = h / max(1, h.sum()) / ancho
            return VGroup(*[Rectangle(width=ax.c2p(ancho, 0)[0] - ax.c2p(0, 0)[0], height=max(1e-3, ax.c2p(0, v)[1] - ax.c2p(0, 0)[1]), stroke_width=0.5, stroke_color=BLACK, fill_color=BLUE, fill_opacity=0.8)
                            .move_to(ax.c2p(b + ancho / 2, 0), aligned_edge=DOWN) for b, v in zip(bins, d)])
        his = always_redraw(barras)
        self.add(his)
        cuenta = cada(lambda: texto(f"{int(k.get_value())} números", 22).next_to(ax, UP, buff=0.05).shift(RIGHT * 2.0))
        self.add(cuenta)
        self.decir("Dos números parejos entran; uno con forma de campana sale")
        self.play(LaggedStart(*[FadeIn(p) for p in puntos], lag_ratio=0.004), k.animate.set_value(400), run_time=3, rate_func=linear)
        self.play(k.animate.set_value(3000), run_time=3, rate_func=linear)
        xs = np.linspace(-4, 4, 121)
        bell = linea(ax, xs, np.exp(-xs ** 2 / 2) / np.sqrt(2 * np.pi), YELLOW, 4)
        self.play(Create(bell))
        dentro = float(np.mean(np.abs(z) < 1))
        self.decir(f"Es la campana de Gauss, con tamaño típico {z.std():.2f}: {100 * dentro:.0f} % cae a menos de 1σ")
        self.wait(2)
        self.remove(his, cuenta)
        self.play(*[FadeOut(m) for m in (ax, bell, cuadro, puntos, nu, f)])
        ax2 = ejes([0, 30, 10], [-3, 3, 1.5], ancho=10, alto=1.5, numeros=False)
        ax3 = ejes([0, 30, 10], [-3, 3, 1.5], ancho=10, alto=1.5, numeros=False)
        ax4 = ejes([0, 30, 10], [-3, 3, 1.5], ancho=10, alto=1.5, numeros=False)
        VGroup(ax2, ax3, ax4).arrange(DOWN, buff=0.22).shift(RIGHT * 0.7 + DOWN * 0.15)
        i = np.arange(30)
        otra = np.array(D["otra"])
        filas = [(ax2, z, "semilla 7", BLUE), (ax3, z, "semilla 7", BLUE), (ax4, otra, "semilla 8", ORANGE)]
        for a, s, nom, col in filas:
            self.play(Create(a), Create(linea(a, i, s[:30], col, 3)), FadeIn(texto(nom, 22, color=col).next_to(a, LEFT, buff=0.15)), run_time=0.9)
        self.decir("Con la misma semilla sale la misma lista: el azar se puede repetir, y la prueba también")
        self.wait(3)


class SintetizarIMU(Escena):
    """De la animación: ω por el giro relativo entre muestras, el acelerómetro por segunda diferencia más la gravedad."""

    def construct(self):
        titulo = texto("Lo que leería el reloj", 34).to_edge(UP)
        self.play(Write(titulo))
        T = np.array(D["trayecto"])
        tt = np.arange(len(T)) / len(T) * D["ciclo"]
        x = T[:, 0]
        ap = ejes([0, 1.2, 0.3], [round(x.min() - 0.1, 1), round(x.max() + 0.1, 1), 0.2], ancho=5.2, alto=2.5).move_to([-3.7, 0.95, 0])
        nombre = texto("la muñeca al caminar: cuánto va adelante (m)", 18, color=GREY_B).next_to(ap, UP, buff=0.06)
        self.play(Create(ap), FadeIn(nombre))
        self.play(Create(linea(ap, tt, x, GREY_B, 3)), run_time=1)
        cresta = int(np.argmax(x))
        paso = 7                                    # muestras separadas de más, para que se vean: Δt ≈ 0.13 s
        i = [cresta - 2 * paso, cresta - paso, cresta]
        Q = lambda j: ap.c2p(tt[j], x[j])
        puntos = VGroup(*[Dot(Q(j), radius=0.08, color=YELLOW) for j in i])
        nombres = VGroup(*[MathTex(n, font_size=30, color=YELLOW).next_to(Q(j), DOWN, buff=0.12) for n, j in zip(("p_-", "p", "p_+"), i)])
        self.play(FadeIn(puntos, nombres))
        previsto = ap.c2p(tt[i[2]], 2 * x[i[1]] - x[i[0]])
        f1 = flecha(Q(i[0]), Q(i[1]), BLUE, 4)
        f2 = flecha(Q(i[1]), previsto, BLUE_B, 3)
        f3 = flecha(previsto, Q(i[2]), RED, 5)
        self.decir("Si nada empujara, seguiría derecho. Lo que falta para llegar es la aceleración")
        self.play(Create(f1))
        self.play(Create(f2))
        self.play(Create(f3))
        fa = MathTex(r"a = \frac{p_+ - 2p + p_-}{\Delta t^2} + g", font_size=34).move_to([-3.9, -1.25, 0])
        fw = MathTex(r"\omega = \frac{\text{eje}\cdot\text{ángulo}}{2\Delta t}", font_size=34).next_to(fa, DOWN, buff=0.12)
        self.play(Write(fa))
        self.wait(1)
        L = D["lectura"]
        t = np.array(L["t"])
        acc, gyr, gyrR = (np.array(L[k]) for k in ("acc", "gyr", "gyrR"))
        aa = ejes([0, 3, 1], [-15, 20, 10], ancho=6.0, alto=2.0).move_to([3.5, 1.25, 0])
        ag = ejes([0, 3, 1], [-200, 200, 100], ancho=6.0, alto=2.0).move_to([3.5, -1.15, 0])
        na = texto("acelerómetro (m/s²)", 18).next_to(aa, UP, buff=0.04)
        ng = texto("giroscopio (°/s)", 18).next_to(ag, UP, buff=0.04)
        self.play(Create(aa), Create(ag), FadeIn(na, ng))
        col = [RED, GREEN, BLUE]
        limpio = VGroup(*[linea(aa, t, acc[:, j], col[j], 2) for j in range(3)], *[linea(ag, t, gyr[:, j], col[j], 2) for j in range(3)])
        self.play(Create(limpio), Write(fw), run_time=2)
        self.decir("ω: el giro relativo entre la muestra de antes y la de después, en los ejes del reloj")
        self.wait(2)
        self.add(texto("x", 20, color=col[0]).next_to(aa, RIGHT, buff=0.1).shift(UP * 0.35), texto("y", 20, color=col[1]).next_to(aa, RIGHT, buff=0.1),
                 texto("z", 20, color=col[2]).next_to(aa, RIGHT, buff=0.1).shift(DOWN * 0.35))
        self.wait(1)
        # lo que se agrega encima es chico al lado del giro: se mira por separado
        extra = gyrR - gyr
        az = ejes([0, 3, 1], [-1.5, 1.5, 0.5], ancho=6.0, alto=2.0).move_to(ag)
        nz = texto("lo que se agrega al giroscopio (°/s)", 18).next_to(az, UP, buff=0.04)
        self.play(FadeOut(limpio[3:]), FadeOut(ag), FadeOut(ng), Create(az), FadeIn(nz))
        self.play(Create(VGroup(*[linea(az, t, extra[:, j], col[j], 2) for j in range(3)])), run_time=1.5)
        self.decir("Y encima ruido y sesgo: 0.3 °/s y (0.6, −0.4, 0.3) °/s en el giroscopio")
        self.wait(3)


class PruebaConVerdad(Escena):
    """Si lo reconstruido cae encima de la animación, la cuenta tiene sentido; no prueba el mundo real."""

    def construct(self):
        titulo = texto("Probar contra la verdad", 34).to_edge(UP)
        self.play(Write(titulo))
        nombres = ["animación", "synth", "reconstruct", "¿cae encima?"]
        cajas = VGroup(*[VGroup(RoundedRectangle(width=2.5, height=0.72, corner_radius=0.1, color=GREY_B), texto(n, 22)) for n in nombres]).arrange(RIGHT, buff=0.75).move_to([0, 2.35, 0])
        pasos = VGroup(*[Arrow(cajas[i].get_right(), cajas[i + 1].get_left(), buff=0.06, stroke_width=3, color=GREY_B) for i in range(3)])
        self.play(LaggedStart(*[FadeIn(c) for c in cajas], lag_ratio=0.2), Create(pasos), run_time=1.4)
        P = D["prueba"]
        t = np.array(P["t"])
        n = len(t)
        V, Rl, Rf = (np.array(P[k]) for k in ("verdad", "reconLimpio", "reconFlojo"))
        E, C = 5.0, np.array([-4.2, 1.1, 0])
        k = ValueTracker(0)
        malo = ValueTracker(0.0)
        recon = lambda: (Rf if malo.get_value() > 0.5 else Rl)[int(k.get_value())]
        P2 = lambda q: C + E * L2 * 1.45 * np.array([q[0], q[1], 0])
        verdad = always_redraw(lambda: Line(C, P2(V[int(k.get_value())]), color=VERDAD, stroke_width=10))
        recons = always_redraw(lambda: Line(C, P2(recon()), color=RECONS, stroke_width=5))
        self.add(verdad, recons, Dot(C, radius=0.09))
        self.add(texto("de verdad", 20, color=VERDAD).move_to([-5.2, -1.7, 0]), texto("reconstruido", 20, color=RECONS).move_to([-3.3, -1.7, 0]))
        ax = ejes([0, 8, 2], [0, 10, 5], ancho=7.0, alto=2.9).move_to([2.6, -0.1, 0])
        ly = texto("error del antebrazo (°)", 18).next_to(ax, UP, buff=0.04)
        lx = texto("segundos", 18).next_to(ax, DOWN, buff=0.04)
        self.play(Create(ax), FadeIn(ly, lx))
        lim, fl = np.array(P["limpio"]), np.array(P["flojo"])
        c1 = always_redraw(lambda: linea(ax, t[:max(2, int(k.get_value()))], lim[:max(2, int(k.get_value()))], VERDAD, 3))
        self.add(c1)
        self.decir(f"Caminando, sin ruido: mediana de {np.median(lim):.1f}°. La cuenta está bien")
        fin = int(np.searchsorted(t, 8.0)) - 1
        self.play(k.animate.set_value(fin), run_time=5, rate_func=linear)
        self.wait(1)
        self.decir("Pero las lecturas salieron del mismo modelo: el reloj pegado al hueso, el brazo rígido")
        vuelta = CurvedArrow(cajas[3].get_bottom() + DOWN * 0.02, cajas[0].get_bottom() + DOWN * 0.02, angle=-0.35, color=RED, stroke_width=3)
        self.play(Create(vuelta))
        self.wait(1.6)
        self.play(FadeOut(vuelta))
        self.remove(c1)
        self.add(linea(ax, t[:fin], lim[:fin], VERDAD, 3))
        malo.set_value(1.0)
        k.set_value(0)
        c2 = always_redraw(lambda: linea(ax, t[:max(2, int(k.get_value()))], fl[:max(2, int(k.get_value()))], RED, 3))
        self.add(c2)
        self.decir(f"Si el reloj se mece ±8° sobre la piel, una vez por segundo: {np.median(fl):.1f}° de mediana")
        self.play(k.animate.set_value(fin), run_time=5, rate_func=linear)
        self.wait(1)
        self.decir("Pasar esta prueba dice que la matemática es coherente, no que el mundo sea así")
        self.wait(3)


class AceleracionDeUnPunto(Escena):
    """Un punto a distancia L acelera α × f·L (tangencial) más ω × (ω × f)·L (centrípeta, hacia el eje)."""

    def construct(self):
        titulo = texto("La aceleración de un punto que gira", 34).to_edge(UP)
        self.play(Write(titulo))
        Lm = 0.25
        R, C = 2.4, np.array([-3.4, -0.35, 0])
        esc = 0.42                                   # unidades de pantalla por m/s²
        th = ValueTracker(20 * GRADO)
        w = ValueTracker(200 * GRADO)                # rad/s
        al = ValueTracker(0.0)                       # rad/s²
        rad = lambda: np.array([np.cos(th.get_value()), np.sin(th.get_value()), 0])
        tan = lambda: np.array([-np.sin(th.get_value()), np.cos(th.get_value()), 0])
        punta = lambda: C + R * rad()
        self.play(Create(Circle(R, color=GREY_C).move_to(C)), FadeIn(Dot(C, radius=0.08)))
        brazo = always_redraw(lambda: Line(C, punta(), color=HUESO, stroke_width=6))
        dot = always_redraw(lambda: Dot(punta(), radius=0.11, color=YELLOW))
        cen = always_redraw(lambda: flecha(punta(), punta() - esc * w.get_value() ** 2 * Lm * rad(), RED, 6))
        tg = always_redraw(lambda: flecha(punta(), punta() + esc * al.get_value() * Lm * tan() + 1e-3 * tan(), GREEN, 6))
        self.add(brazo, dot, cen, tg)
        f1 = MathTex(r"\ddot{p} = \alpha\times f\,L + \omega\times(\omega\times f)\,L", font_size=34).move_to([3.3, 2.2, 0])
        self.play(Write(f1))

        def cifras():
            ww, aa = w.get_value(), al.get_value()
            return VGroup(texto(f"ω = {ww / GRADO:.0f} °/s = {ww:.2f} rad/s", 24), texto(f"α = {aa:.1f} rad/s²", 24),
                          texto(f"centrípeta ω²L = {ww ** 2 * Lm:.2f} m/s²", 24, color=RED), texto(f"tangencial αL = {aa * Lm:.2f} m/s²", 24, color=GREEN),
                          texto("L = 25 cm", 22, color=GREY_B)).arrange(DOWN, aligned_edge=LEFT, buff=0.14).move_to([0.8, 0.45, 0], aligned_edge=LEFT)
        lect = cada(cifras)
        self.add(lect)
        self.decir("A rapidez pareja el punto igual acelera: la velocidad cambia de dirección, hacia el eje")
        self.play(th.animate.set_value(20 * GRADO + 2 * np.pi), run_time=3.5, rate_func=linear)
        self.wait(0.5)
        self.decir("Con el doble de ω, la centrípeta es cuatro veces más grande: va con ω²")
        self.play(w.animate.set_value(400 * GRADO), th.animate.set_value(20 * GRADO + 3 * np.pi), run_time=3, rate_func=linear)
        self.play(w.animate.set_value(200 * GRADO), run_time=0.8)
        self.decir("Si además gira cada vez más rápido, aparece α × f: de costado, a lo largo del círculo")
        self.play(w.animate.set_value(100 * GRADO), run_time=0.6)
        A, w0, th0 = 6.0, w.get_value(), th.get_value()        # de 100 a 300 °/s con α = 6 rad/s², en cámara lenta
        T = (300 * GRADO - w0) / A
        al.set_value(A)

        def rampa(m, q):
            th.set_value(th0 + w0 * T * q + A * (T * q) ** 2 / 2)
            w.set_value(w0 + A * T * q)
        self.play(UpdateFromAlphaFunc(VMobject(), rampa), run_time=3.5, rate_func=linear)
        self.wait(0.6)
        self.play(al.animate.set_value(0.0), w.animate.set_value(200 * GRADO), run_time=0.6)
        self.decir("El filtro resta esto al reloj: queda la aceleración del codo, sin haberlo visto")
        f2 = MathTex(r"\ddot{e} = \ddot{p} - L_w\,\ddot{f}", font_size=38).move_to([3.3, -1.75, 0])
        self.play(Write(f2))
        self.wait(3)


class LimitesDelCuerpo(Escena):
    """El codo no se dobla más de 150° ni al revés, el brazo no atraviesa el torso: lo imposible pesa casi cero."""

    def construct(self):
        titulo = texto("Límites del cuerpo", 34).to_edge(UP)
        self.play(Write(titulo))
        cel = 0.215
        x0, y0 = -6.3, -0.3
        Q = lambda lon, lat: np.array([x0 + (lon + 180) / 10 * cel, y0 + lat / 10 * cel, 0])
        colores = {0: GREEN_D, 1: RED_D, 2: ORANGE, 3: PURPLE_D}
        celdas = {0: VGroup(), 1: VGroup(), 2: VGroup(), 3: VGroup()}
        for lon, lat, c in D["limites"]:
            celdas[c].add(Square(cel, stroke_width=0.5, stroke_color=BLACK, fill_color=colores[c], fill_opacity=0.9).move_to(Q(lon, lat)))
        fondo = VGroup(*[Square(cel, stroke_width=0.5, stroke_color=BLACK, fill_color=GREEN_D, fill_opacity=0.9).move_to(Q(lon, lat)) for lon, lat, _ in D["limites"]])
        marcas = VGroup(texto("atrás", 18, color=GREY_B).next_to(Q(-175, -90), DOWN, buff=0.12), texto("adelante", 18, color=GREY_B).next_to(Q(0, -90), DOWN, buff=0.12),
                        texto("afuera", 18, color=GREY_B).next_to(Q(90, -90), DOWN, buff=0.12), texto("adentro", 18, color=GREY_B).next_to(Q(-90, -90), DOWN, buff=0.12),
                        texto("arriba", 18, color=GREY_B).next_to(Q(-180, 85), LEFT, buff=0.06).rotate(PI / 2), texto("abajo", 18, color=GREY_B).next_to(Q(-180, -85), LEFT, buff=0.06).rotate(PI / 2))
        self.play(FadeIn(fondo), FadeIn(marcas))
        self.decir("Cada cuadrito es una dirección del brazo, con el antebrazo apuntando al frente")
        self.wait(1.2)
        total = len(D["limites"])
        n = {c: len(celdas[c]) for c in celdas}
        pasos = [(1, "codo a más de 150°"), (2, "bisagra al revés"), (3, "muy atrás o en el pecho")]
        fila = []
        for c, nom in pasos:
            if not n[c]:
                continue
            self.play(FadeIn(celdas[c]), run_time=0.9)
            fila.append(VGroup(Square(0.26, fill_color=colores[c], fill_opacity=1, stroke_width=0), texto(f"{nom}: {100 * n[c] / total:.0f} %", 20)).arrange(RIGHT, buff=0.14))
            fila[-1].move_to([2.0, 2.1 - 0.55 * len(fila), 0], aligned_edge=LEFT)
            self.play(FadeIn(fila[-1]), run_time=0.5)
            self.wait(0.8)
        ok = VGroup(Square(0.26, fill_color=GREEN_D, fill_opacity=1, stroke_width=0), texto(f"posible: {100 * n[0] / total:.0f} %", 20)).arrange(RIGHT, buff=0.14).move_to([2.0, 2.1 - 0.55 * (len(fila) + 1), 0], aligned_edge=LEFT)
        self.play(FadeIn(ok))
        r = D["reposoLim"]
        lon, lat = np.arctan2(r[0], r[2]) / GRADO, np.arcsin(r[1]) / GRADO
        punto = Dot(Q(lon, lat), radius=0.1, color=WHITE)
        self.play(FadeIn(punto), FadeIn(texto("reposo", 20).next_to(punto, UP, buff=0.08)))
        self.decir("Un solo reloj no ve el brazo, pero con esto ya no tiene que buscar por todas partes")
        self.wait(1.5)
        f = MathTex(r"w \leftarrow 0.02\, w", font_size=38).move_to([4.2, -1.3, 0])
        self.play(Write(f))
        self.decir("Lo imposible no se borra: su peso se multiplica por 0.02, por si el modelo se equivoca")
        self.wait(3)


class Verosimilitud(Escena):
    """Qué tan probable es la medida si una hipótesis fuera cierta: exp(−r²/2σ²)."""

    def construct(self):
        titulo = texto("Verosimilitud", 34).to_edge(UP)
        self.play(Write(titulo))
        f = MathTex(r"p = e^{-r^2 / 2\sigma^2}", font_size=42).move_to([3.9, 2.25, 0])
        self.play(Write(f))
        ax = ejes([-3, 3, 1], [0, 1.1, 0.5], ancho=7.2, alto=3.7).move_to([-2.6, 0.1, 0])
        lx = texto("residuo r (m/s²)", 18).next_to(ax, DOWN, buff=0.06)
        self.play(Create(ax), FadeIn(lx))
        sR, sRel = D["prior"]["sigmaR"], D["prior"]["sigmaRel"]
        z = ValueTracker(0.0)
        sig = lambda: sR + sRel * z.get_value()
        xs = np.linspace(-3, 3, 121)
        bell = always_redraw(lambda: linea(ax, xs, np.exp(-xs ** 2 / (2 * sig() ** 2)), YELLOW, 4))
        self.add(bell)
        hip = [(0.15, GREEN, "A"), (0.6, BLUE, "B"), (1.2, RED, "C")]
        p = lambda r: float(np.exp(-r * r / (2 * sig() ** 2)))
        puntos = always_redraw(lambda: VGroup(*[Dot(ax.c2p(r, p(r)), radius=0.1, color=c) for r, c, _ in hip]))
        self.add(puntos)

        def barras():
            g = VGroup()
            for i, (r, c, nom) in enumerate(hip):
                y = 0.95 - 0.72 * i
                g.add(texto(f"{nom}: r = {r:.2f}", 22, color=c).move_to([1.75, y + 0.2, 0], aligned_edge=LEFT))
                g.add(Line([1.75, y - 0.1, 0], [1.76 + 3.3 * p(r), y - 0.1, 0], color=c, stroke_width=12))
                g.add(texto(f"{p(r):.3f}", 22, color=c).move_to([6.2, y - 0.1, 0], aligned_edge=RIGHT))
            return g
        panel = always_redraw(barras)
        sigma = cada(lambda: texto(f"|z| = {z.get_value():.1f} m/s²   σ = {sig():.2f} m/s²", 24).move_to([3.9, 1.55, 0]))
        self.add(panel, sigma)
        self.decir("Tres hipótesis del codo. Cuanto más cerca de cero el residuo, más creíble")
        self.wait(2.5)
        self.decir("Con el brazo rápido el modelo se equivoca más: σ = 0.3 + 0.3·|z| y la campana se abre")
        self.play(z.animate.set_value(5.0), run_time=3)
        self.wait(1.5)
        self.play(z.animate.set_value(1.0), run_time=1.5)
        self.wait(0.5)
        r_a, r_c = hip[0][0], hip[2][0]
        cociente = lambda n: float(np.exp(-n * (r_c ** 2 - r_a ** 2) / (2 * sig() ** 2)))
        self.decir(f"Cada muestra multiplica: C pesa {cociente(1):.2f} de A; tras 2 muestras, {cociente(2):.3f}; tras 5, {cociente(5):.5f}")
        self.wait(3)
        self.decir("r es lo que falla la ecuación del codo: ë·u + |ė|²/L_u, que en la esfera debe dar cero")
        self.wait(3)


class FiltroDeParticulas(Escena):
    """Muchas hipótesis del codo a la vez, cada una con un peso."""

    def construct(self):
        titulo = texto("Filtro de partículas", 34).to_edge(UP)
        self.play(Write(titulo))
        N = D["nube"]
        S = np.array(D["shoulder"])
        a = -35 * GRADO
        E, C = 6.0, np.array([-3.4, 1.3, 0])
        pr = lambda p: C + E * np.array([(p[0] - S[0]) * np.cos(a) + (p[2] - S[2]) * np.sin(a), p[1] - S[1], 0])
        t = np.array(N["t"])
        k = ValueTracker(0)
        i = lambda: int(k.get_value())
        puntos = VGroup(*[Dot(pr(p), radius=0.035, color=NUBE) for p in N["codos"][0]])

        def mover(g):
            for d, p in zip(g, N["codos"][i()]):
                d.move_to(pr(p))
        puntos.add_updater(mover)
        verdad = always_redraw(lambda: VGroup(Line(pr(S), pr(N["verdad"][i()]), color=VERDAD, stroke_width=7), Line(pr(N["verdad"][i()]), pr(N["muneca"][i()]), color=VERDAD, stroke_width=7)))
        est = always_redraw(lambda: Line(pr(S), pr(N["est"][i()]), color=RECONS, stroke_width=5))
        rep = always_redraw(lambda: Dot(pr(N["reposo"][i()]), radius=0.08, color=WHITE))
        self.add(verdad, puntos, est, rep, Dot(pr(S), radius=0.09))
        ley = VGroup(texto("el brazo de verdad", 19, color=VERDAD), texto("el codo estimado", 19, color=RECONS), texto("400 codos posibles (se ven 160)", 19, color=NUBE), texto("postura de reposo", 19)).arrange(DOWN, aligned_edge=LEFT, buff=0.06).move_to([1.6, 1.75, 0], aligned_edge=LEFT)
        Sr = D["serie"]
        st = np.array(Sr["t"])
        m = st <= 30
        st, sp, eF, eR = st[m], np.array(Sr["spread"])[m], np.array(Sr["errF"])[m], np.array(Sr["errR"])[m]
        ax = ejes([0, 30, 5], [0, 30, 10], ancho=6.2, alto=2.5).move_to([3.3, -0.55, 0])
        ly = texto("cm", 18).next_to(ax, LEFT, buff=0.1)
        lx = texto("segundos", 18).next_to(ax, DOWN, buff=0.03).shift(RIGHT * 2.3)
        franja = Rectangle(width=ax.c2p(15, 0)[0] - ax.c2p(0, 0)[0], height=2.5, stroke_width=0, fill_color=BLUE, fill_opacity=0.12).move_to(ax.c2p(7.5, 15))
        self.play(FadeIn(ley), Create(ax), FadeIn(ly, lx, franja))
        hasta = lambda: max(2, int(np.searchsorted(st, t[i()])))
        curvas = always_redraw(lambda: VGroup(linea(ax, st[:hasta()], sp[:hasta()], NUBE, 3), linea(ax, st[:hasta()], eF[:hasta()], RECONS, 3)))
        self.add(curvas)
        self.add(texto("ancho de la nube", 18, color=NUBE).move_to(ax.c2p(21, 27)), texto("error del codo", 18, color=RECONS).move_to(ax.c2p(21, 22)))
        lect = cada(lambda: texto(f"t = {t[i()]:.1f} s", 22).move_to([-5.7, -2.1, 0]))
        self.add(lect)
        self.decir("Cada una se mueve con el modelo y se pesa con la medida; las malas se apagan")
        i15 = int(np.searchsorted(t, 15.0))
        self.play(k.animate.set_value(i15), run_time=9, rate_func=linear)
        mov = (st > 3) & (st < 15)
        rms = lambda v: float(np.sqrt(np.mean(np.asarray(v) ** 2)))
        self.decir(f"Moviendo el brazo, el filtro se equivoca {rms(eF[mov]):.1f} cm y la regla de reposo {rms(eR[mov]):.1f} cm")
        self.wait(2)
        self.decir("Quieta la muñeca, no hay aceleración: ninguna hipótesis se distingue de otra")
        self.play(k.animate.set_value(len(t) - 1), run_time=7, rate_func=linear)
        fin = st > 28
        self.decir(f"El resorte junta la nube: {sp[fin].mean():.1f} cm de ancho, pero {eF[fin].mean():.1f} cm de error. No es certeza")
        self.wait(3.5)


class Remuestreo(Escena):
    """Cuando pocos pesos dominan se clonan las partículas buenas y se olvidan las malas."""

    def construct(self):
        titulo = texto("Tamaño efectivo y remuestreo", 34).to_edge(UP)
        self.play(Write(titulo))
        R = D["res"]
        n, w, ini, clones = R["n"], np.array(R["pesos"]), R["inicio"], R["clones"]
        x0, paso = -5.8, 0.5
        y0, H = 0.85, 8.0
        barras = VGroup(*[Rectangle(width=0.38, height=max(0.012, H * v), stroke_width=0, fill_color=NUBE, fill_opacity=0.9).move_to([x0 + i * paso, y0, 0], aligned_edge=DOWN) for i, v in enumerate(w)])
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in barras], lag_ratio=0.02), run_time=1.4)
        neff = 1 / np.sum(w ** 2)
        f = MathTex(r"N_{ef} = \frac{1}{\sum w_i^2}", "=" + f"{neff:.1f}", font_size=38).move_to([3.9, 2.0, 0])
        self.play(Write(f))
        self.decir(f"{n} partículas, pero pocas mandan: valen como {neff:.1f}. Las demás se calculan para nada")
        self.wait(2)
        # la tira: cada partícula ocupa lo que pesa
        izq, ancho, yt = -5.9, 11.8, -0.25
        acum = np.concatenate([[0], np.cumsum(w)])
        trozos = VGroup(*[Rectangle(width=max(0.004, ancho * v), height=0.45, stroke_width=1, stroke_color=BLACK, fill_color=NUBE if i % 2 == 0 else GOLD_E, fill_opacity=0.9).move_to([izq + ancho * acum[i], yt, 0], aligned_edge=LEFT) for i, v in enumerate(w)])
        self.play(FadeIn(trozos))
        self.decir("Se ponen en fila, cada una tan ancha como su peso")
        self.wait(1)
        peine = VGroup(*[Arrow([izq + ancho * (ini + m / n), yt - 0.75, 0], [izq + ancho * (ini + m / n), yt - 0.26, 0], buff=0, stroke_width=3, color=WHITE, max_tip_length_to_length_ratio=0.3) for m in range(n)])
        self.decir(f"Un peine de {n} dientes parejos, con un solo número al azar: cada diente elige una")
        self.play(LaggedStart(*[GrowArrow(p) for p in peine], lag_ratio=0.03), run_time=1.6)
        self.wait(1.4)
        y1 = -2.2
        nuevas = VGroup()
        for i, c in enumerate(clones):
            for j in range(c):
                nuevas.add(Dot([x0 + i * paso, y1 + j * 0.16, 0], radius=0.06, color=NUBE))
        vacias = VGroup(*[Dot([x0 + i * paso, y1, 0], radius=0.03, color=GREY_D) for i, c in enumerate(clones) if c == 0])
        self.play(FadeOut(peine), FadeOut(trozos), FadeIn(nuevas), FadeIn(vacias), run_time=1)
        cero = sum(1 for c in clones if c == 0)
        self.decir(f"Las buenas se clonan, {cero} de {n} se olvidan, y todas vuelven a pesar 1/{n}")
        self.wait(1.2)
        self.play(*[b.animate.stretch_to_fit_height(H / n).align_to([0, y0, 0], DOWN) for b in barras], run_time=1.2)
        self.wait(1.2)
        self.clear()
        self.add(titulo)
        self._rotulo = None
        S = D["serie"]
        t, ne = np.array(S["t"]), np.array(S["neff"], float)
        m = t <= 30
        ax = ejes([0, 30, 5], [0, 400, 100], ancho=10.0, alto=3.8).move_to([0.5, 0.0, 0])
        ly = texto("N_ef", 20).next_to(ax, LEFT, buff=0.1)
        lx = texto("segundos: el brazo se mueve hasta los 15 s", 18).next_to(ax, DOWN, buff=0.05)
        um = DashedLine(ax.c2p(0, 200), ax.c2p(30, 200), color=RED)
        self.play(Create(ax), FadeIn(ly, lx), Create(um))
        self.add(texto("la mitad: 200", 20, color=RED).next_to(ax.c2p(27, 200), DOWN, buff=0.06))
        self.play(Create(linea(ax, t[m], ne[m], NUBE, 2)), run_time=3)
        self.decir(f"Cuando N_ef baja de 200 se remuestrea: {D['remuestreos']} veces, casi todas con el brazo en movimiento")
        self.wait(3)
