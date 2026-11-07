# Animaciones del capítulo 11 (Frecuencia), con Manim (https://www.manim.community).
#
#   python docs/curso/animaciones/render.py            # todas, a 720p, y los GIF de docs/curso/media/cap11/
#   manim -pql docs/curso/animaciones/cap11.py Enrollar  # una sola, en baja, para probar
#
# La línea del sismógrafo es la misma que arma server/web/sismomath.js (makeTarget/wave): suma de senos con
# f_k = k/T, las ondas rápidas más chicas, la suma de amplitudes igual a 0.75. Las fases salen de una semilla
# fija para que el video sea siempre el mismo.
import os
import sys
import wave as wavfile

import numpy as np
from manim import *

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools"))
from analyze_dataset import FS, window_features      # noqa: E402  la de verdad, para la frecuencia dominante

T = 20.0                       # s, como sismomath.T
PEAK = 0.75
KS = [1, 2, 3, 4]              # nivel "tranquilo"
LINEA, AGUJA, PRUEBA, ERROR = YELLOW, BLUE, TEAL, RED


def make_target(ks=KS, seed=3):
    rng = np.random.default_rng(seed)
    raw = np.array([1 / (1 + k / T / 0.25) for k in ks])
    a = raw * PEAK / raw.sum()
    return [(k / T, ai, 2 * np.pi * rng.random()) for k, ai in zip(ks, a)]


COMPS = make_target()


def r(t, comps=COMPS):
    t = np.asarray(t, dtype=float)
    return sum(a * np.sin(2 * np.pi * f * t + ph) for f, a, ph in comps)


def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


def write_wav(path, x, rate=44100):
    x = np.clip(x / max(1e-9, np.abs(x).max()) * 0.8, -1, 1)
    with wavfile.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def sound_path(name):
    folder = os.path.join(config.media_dir, "sonidos")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, name)


# ---------------------------------------------------------------------------------------------------------
class SumaDeSenos(Scene):
    """Pregunta 1: una línea que parece al azar y aun así se repite cada 20 s."""

    def construct(self):
        titulo = texto("La línea del sismógrafo son cuatro ondas", 34).to_edge(UP)
        self.play(Write(titulo))
        filas = VGroup()
        for i, (f, a, ph) in enumerate(COMPS):
            ax = Axes(x_range=[0, T, 5], y_range=[-0.4, 0.4, 0.4], x_length=9, y_length=0.9, tips=False,
                      axis_config={"stroke_opacity": 0.4})
            g = ax.plot(lambda t, f=f, a=a, ph=ph: a * np.sin(2 * np.pi * f * t + ph), color=PRUEBA)
            etiqueta = texto(f"{KS[i]} vuelta{'s' if KS[i] > 1 else ''} en 20 s", 22).next_to(ax, LEFT, buff=0.3)
            filas.add(VGroup(ax, g, etiqueta))
        filas.arrange(DOWN, buff=0.25).next_to(titulo, DOWN, buff=0.4).shift(RIGHT * 0.9)
        for fila in filas:
            self.play(Create(fila[0]), Create(fila[1]), FadeIn(fila[2]), run_time=0.9)
        self.wait(0.5)

        ax = Axes(x_range=[0, T, 5], y_range=[-0.8, 0.8, 0.4], x_length=11, y_length=3, tips=False,
                  axis_config={"include_numbers": True, "font_size": 20}).to_edge(DOWN, buff=0.6)
        suma = ax.plot(lambda t: r(t), color=LINEA, stroke_width=4)
        signo = texto("sumadas:", 26).next_to(ax, UP, buff=0.15).align_to(ax, LEFT)
        self.play(*[ReplacementTransform(fila[1].copy(), suma) for fila in filas], FadeIn(signo), run_time=2)
        self.wait(0.5)
        self.play(FadeOut(filas), FadeOut(signo), titulo.animate.become(
            texto("Parece al azar...", 34).to_edge(UP)))
        self.wait(0.5)

        ax2 = Axes(x_range=[0, 2 * T, 5], y_range=[-0.8, 0.8, 0.4], x_length=12, y_length=3, tips=False,
                   axis_config={"include_numbers": True, "font_size": 20}).move_to(ax)
        uno = ax2.plot(lambda t: r(t), x_range=[0, T], color=LINEA, stroke_width=4)
        dos = ax2.plot(lambda t: r(t), x_range=[T, 2 * T], color=LINEA, stroke_width=4)
        self.play(ReplacementTransform(ax, ax2), ReplacementTransform(suma, uno))
        self.play(Create(dos), run_time=2.5, rate_func=linear)
        cajas = VGroup(*[Rectangle(width=ax2.x_length / 2, height=3.2, stroke_color=WHITE, stroke_opacity=0.6)
                         .move_to(ax2.c2p(T / 2 + k * T, 0)) for k in (0, 1)])
        self.play(Create(cajas), titulo.animate.become(
            texto("...pero se repite cada T = 20 s", 34).to_edge(UP)))
        nota = texto("porque cada onda da un número entero de vueltas en T", 26).next_to(titulo, DOWN)
        self.play(FadeIn(nota))
        self.play(Indicate(dos, color=WHITE), Indicate(uno, color=WHITE))
        self.wait(2)


# ---------------------------------------------------------------------------------------------------------
class FlechaQueGira(Scene):
    """Un número complejo es una flecha; un seno es su sombra. Multiplicar: largos por, ángulos más."""

    def construct(self):
        centro = LEFT * 4 + DOWN * 0.3
        A, f, ph = 1.6, 0.5, PI / 3
        t = ValueTracker(0)
        circ = Circle(radius=A, color=WHITE, stroke_opacity=0.35).move_to(centro)
        ax = Axes(x_range=[0, 4, 1], y_range=[-1, 1, 1], x_length=7, y_length=2 * A, tips=False,
                  axis_config={"stroke_opacity": 0.5}).next_to(circ, RIGHT, buff=0.8)
        ax.shift(UP * (centro[1] - ax.c2p(0, 0)[1]))
        ang = lambda: 2 * PI * f * t.get_value() + ph
        punta = lambda: centro + A * np.array([np.cos(ang()), np.sin(ang()), 0])
        flecha = always_redraw(lambda: Arrow(centro, punta(), buff=0, color=PRUEBA, stroke_width=6))
        sombra = always_redraw(lambda: ax.plot(lambda s: np.sin(2 * PI * f * s + ph), x_range=[0, max(1e-3, t.get_value())],
                                               color=LINEA, stroke_width=4))
        guia = always_redraw(lambda: DashedLine(punta(), ax.c2p(t.get_value(), np.sin(ang())), stroke_opacity=0.6))
        titulo = texto("Un seno es la sombra de una flecha que gira", 34).to_edge(UP)
        self.play(Write(titulo), Create(circ), Create(ax))
        self.add(flecha, sombra, guia)
        largo = texto("largo = amplitud", 24, color=PRUEBA).next_to(circ, DOWN)
        fase = texto("ángulo al empezar = fase", 24, color=PRUEBA).next_to(largo, DOWN, buff=0.15)
        self.play(FadeIn(largo), FadeIn(fase))
        self.play(t.animate.set_value(4), run_time=6, rate_func=linear)
        self.wait(0.5)
        self.play(*[FadeOut(m) for m in (circ, ax, flecha, sombra, guia, largo, fase)])
        self.remove(flecha, sombra, guia)

        plano = ComplexPlane(x_range=[-2, 3], y_range=[-0.5, 2.2], background_line_style={"stroke_opacity": 0.25})
        plano.scale(1.6).shift(DOWN * 0.5)
        self.play(titulo.animate.become(texto("Multiplicar flechas: los largos se multiplican, los ángulos se suman", 28)
                                        .to_edge(UP)), Create(plano))
        z1, z2 = 1.5 * np.exp(1j * np.radians(25)), 1.2 * np.exp(1j * np.radians(50))
        p = lambda z: plano.n2p(z)
        a1 = Arrow(p(0), p(z1), buff=0, color=PRUEBA, stroke_width=6)
        a2 = Arrow(p(0), p(z2), buff=0, color=BLUE, stroke_width=6)
        a3 = Arrow(p(0), p(z1 * z2), buff=0, color=LINEA, stroke_width=6)
        l1 = MathTex(r"1.5\,\angle 25^\circ", color=PRUEBA, font_size=34).next_to(a1.get_end(), RIGHT)
        l2 = MathTex(r"1.2\,\angle 50^\circ", color=BLUE, font_size=34).next_to(a2.get_end(), LEFT)
        l3 = MathTex(r"1.5\cdot1.2 = 1.8\,\angle (25^\circ{+}50^\circ)", color=LINEA, font_size=34)\
            .next_to(a3.get_end(), UP)
        self.play(GrowArrow(a1), FadeIn(l1))
        self.play(GrowArrow(a2), FadeIn(l2))
        self.play(TransformFromCopy(VGroup(a1, a2), a3), FadeIn(l3))
        self.wait(1)
        # la misma flecha con las dos notaciones: largo a y ángulo φ
        euler = VGroup(MathTex(r"a\angle\varphi = a\,e^{i\varphi}", font_size=36),
                       MathTex(r"a\,e^{i\varphi}\cdot b\,e^{i\psi} = ab\,e^{i(\varphi+\psi)}", font_size=32, color=LINEA))\
            .arrange(DOWN, aligned_edge=LEFT, buff=0.2).move_to(LEFT * 4.4 + UP * 2.4)
        self.play(Write(euler[0]))
        self.wait(1)
        self.play(Write(euler[1]))
        self.wait(1.5)
        div = VGroup(
            texto("Dividir dos ondas, Y / R, dice:", 26),
            texto("cuánto más chica es Y (el largo)  y  cuánto atrasada (el ángulo)", 26, color=LINEA),
        ).arrange(DOWN).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(div))
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
class ElNumeroI(Scene):
    """i es la flecha de largo 1 hacia arriba; e^{iθ} = cos θ + i sen θ es la flecha de largo 1 y ángulo θ."""

    def decir(self, s, size=24):
        nuevo = texto(s, size).to_edge(DOWN, buff=0.3)
        viejo = getattr(self, "_rotulo", None)
        self.play(*([FadeOut(viejo)] if viejo else []), FadeIn(nuevo), run_time=0.5)
        self._rotulo = nuevo

    def construct(self):
        titulo = texto("Una flecha del plano es un número", 34).to_edge(UP)
        plano = ComplexPlane(x_range=[-2, 2], y_range=[-1.6, 1.6], background_line_style={"stroke_opacity": 0.25})
        plano.scale(1.55).move_to(LEFT * 3.5 + DOWN * 0.35)
        p = plano.n2p
        self.play(Write(titulo), Create(plano))
        renglon = lambda m, y: m.move_to(RIGHT * 3.2 + UP * y)

        # 1.5 + 1i: lo horizontal cuenta unos, lo vertical cuenta íes
        z = 1.5 + 1j
        fz = Arrow(p(0), p(z), buff=0, color=PRUEBA, stroke_width=6)
        gx = DashedLine(p(0), p(z.real), color=PRUEBA, stroke_opacity=0.7)
        gy = DashedLine(p(z.real), p(z), color=PRUEBA, stroke_opacity=0.7)
        lz = MathTex(r"1.5 + 1\,i", font_size=34, color=PRUEBA).next_to(p(z), UR, buff=0.08)
        self.play(GrowArrow(fz), Create(gx), Create(gy), FadeIn(lz))
        self.decir("La flecha que llega a (1.5, 1) se escribe 1.5 + 1 i")
        self.wait(1)
        fi = Arrow(p(0), p(1j), buff=0, color=LINEA, stroke_width=6)
        li = MathTex("i", font_size=36, color=LINEA).next_to(p(1j), LEFT, buff=0.12)
        self.play(GrowArrow(fi), FadeIn(li))
        self.decir("i es la flecha de largo 1 que apunta hacia arriba")
        self.wait(1.5)

        # multiplicar por i gira 90°: dos veces, media vuelta
        uno = Arrow(p(0), p(1), buff=0, color=WHITE, stroke_width=6)
        self.play(FadeOut(fz, gx, gy, lz), GrowArrow(uno))
        r1 = renglon(MathTex(r"i \cdot 1 = i", font_size=38), 1.6)
        r2 = renglon(MathTex(r"i \cdot i = -1", font_size=38), 0.8)
        self.decir("Multiplicar por i gira 90°")
        self.play(Rotate(uno, PI / 2, about_point=p(0)), Write(r1), run_time=1.5)
        self.wait(0.5)
        self.decir("Dos veces, media vuelta: por eso i · i = −1")
        self.play(Rotate(uno, PI / 2, about_point=p(0)), Write(r2), run_time=1.5)
        self.wait(1)
        fz2 = Arrow(p(0), p(z), buff=0, color=PRUEBA, stroke_width=6)
        r3 = renglon(MathTex(r"i\,(1.5 + 1\,i) = -1 + 1.5\,i", font_size=34, color=PRUEBA), 0.0)
        self.play(FadeOut(uno), GrowArrow(fz2))
        self.play(Rotate(fz2, PI / 2, about_point=p(0)), Write(r3), run_time=1.5)
        assert abs(1j * z - (-1 + 1.5j)) < 1e-12
        self.decir("Gira cualquier flecha: 1.5 + 1 i, girada 90°, es −1 + 1.5 i")
        self.wait(2)

        # la flecha de largo 1 y ángulo θ
        self.play(FadeOut(fz2, fi, li, r1, r2, r3))
        circ = Circle(radius=np.linalg.norm(p(1) - p(0)), color=WHITE, stroke_opacity=0.4).move_to(p(0))
        th = ValueTracker(0.35)
        punta = lambda: np.exp(1j * th.get_value())
        fu = always_redraw(lambda: Arrow(p(0), p(punta()), buff=0, color=LINEA, stroke_width=6))
        cx = always_redraw(lambda: Line(p(0), p(punta().real), color=RED, stroke_width=5))
        sy = always_redraw(lambda: Line(p(punta().real), p(punta()), color=GREEN, stroke_width=5))
        arco = always_redraw(lambda: Arc(radius=0.4, start_angle=0, angle=th.get_value(), arc_center=p(0), color=WHITE))
        self.play(Create(circ))
        self.add(cx, sy, fu, arco)
        # piezas sueltas y no partes de un MathTex: aquí manim no encuentra los grupos de las partes
        e1 = renglon(VGroup(MathTex(r"e^{i\theta} =", font_size=40), MathTex(r"\cos\theta", font_size=40, color=RED),
                            MathTex(r"+\,i", font_size=40), MathTex(r"\sin\theta", font_size=40, color=GREEN)).arrange(RIGHT, buff=0.15), 1.6)
        self.decir("La flecha de largo 1 y ángulo θ llega a (cos θ, sen θ)")
        self.play(th.animate.set_value(1.1), run_time=2)
        self.play(Write(e1[1:]))
        self.decir("En números: cos θ + i sen θ. Se escribe e^(iθ)")
        self.play(Write(e1[0]), th.animate.set_value(2.2), run_time=2)
        self.wait(1)
        e2 = renglon(MathTex(r"e^{i\alpha}\, e^{i\beta} = e^{i(\alpha+\beta)}", font_size=36), 0.7)
        self.decir("Como una potencia: multiplicar suma los ángulos, como e^a · e^b = e^(a+b)")
        self.play(Write(e2))
        self.wait(2.5)
        e3 = renglon(MathTex(r"a\angle\varphi = a\,e^{i\varphi}", font_size=38, color=PRUEBA), -0.2)
        largo = always_redraw(lambda: Arrow(p(0), p(1.5 * punta()), buff=0, color=PRUEBA, stroke_width=6))
        self.play(th.animate.set_value(np.radians(25)), run_time=1.2)
        self.add(largo)
        self.play(Write(e3))
        self.decir("Con largo a: a·e^(iφ) es la flecha a∠φ de antes")
        self.wait(2.5)

        # e^{−2πift}: el ángulo baja con el tiempo, la flecha gira al revés
        self.play(FadeOut(largo, e2, e3))
        self.remove(largo)
        f, t = 0.5, ValueTracker(0)
        th.set_value(0)
        e4 = renglon(MathTex(r"e^{-2\pi i f t}:\ \text{largo 1, ángulo } -2\pi f t", font_size=34), 0.4)
        reloj = always_redraw(lambda: texto(f"f = {f} Hz    t = {t.get_value():.1f} s", 24).move_to(RIGHT * 3.2 + DOWN * 0.6))
        self.play(Write(e4))
        self.add(reloj)
        th.add_updater(lambda m: m.set_value(-2 * PI * f * t.get_value()))
        self.add(th)
        self.decir("e^(−2πift) gira f vueltas por segundo, como las agujas del reloj")
        self.play(t.animate.set_value(2), run_time=4, rate_func=linear)
        self.wait(1.5)
        self.decir("Multiplicar una señal por ella: x(t) da el largo, y el ángulo gira")
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
class Enrollar(Scene):
    """Pregunta 2 (DFT): enrollar la línea alrededor de un círculo a la frecuencia de prueba y mirar su centro."""

    def construct(self):
        N, scale = 2000, 2.1
        ts = np.linspace(0, T, N, endpoint=False)
        g = r(ts)
        f = ValueTracker(0.02)
        centro = LEFT * 3.3 + DOWN * 0.2
        plano = NumberPlane(x_range=[-1, 1, 0.5], y_range=[-1, 1, 0.5], x_length=2 * scale, y_length=2 * scale,
                            background_line_style={"stroke_opacity": 0.2}).move_to(centro)

        def z(fv):
            return g * np.exp(-2j * np.pi * fv * ts)

        def curva():
            zz = z(f.get_value())
            pts = [plano.c2p(c.real, c.imag) for c in zz[::2]]
            return VMobject(stroke_color=LINEA, stroke_width=2).set_points_as_corners(pts)

        def masa():
            c = z(f.get_value()).mean()
            return Dot(plano.c2p(c.real, c.imag), color=RED, radius=0.09)

        fs = np.linspace(0, 0.3, 601)
        mag = np.array([2 * abs(z(fv).mean()) for fv in fs])
        ax = Axes(x_range=[0, 0.3, 0.05], y_range=[0, 0.3, 0.1], x_length=6, y_length=3, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18}).to_edge(RIGHT, buff=0.5).shift(DOWN * 0.3)
        xl = texto("frecuencia de prueba (Hz)", 20).next_to(ax, DOWN, buff=0.35)
        yl = texto("cuánto hay: el espectro", 20).next_to(ax, UP, buff=0.15).align_to(ax, LEFT)
        espectro = always_redraw(lambda: ax.plot(lambda x: np.interp(x, fs, mag), x_range=[0, max(1e-3, f.get_value()), 0.0005],
                                                 color=RED, stroke_width=3))
        etiqueta = always_redraw(lambda: texto(f"f = {f.get_value():.3f} Hz", 26).next_to(plano, UP, buff=0.2))

        titulo = texto("¿Cuánto hay de cada onda? Enróllala y mira el centro", 32).to_edge(UP)
        self.play(Write(titulo), Create(plano), Create(ax), FadeIn(xl), FadeIn(yl))
        linea = always_redraw(curva)
        punto = always_redraw(masa)
        self.add(linea, punto, espectro, etiqueta)
        explica = texto("x(t)·e^(−2πift): una flecha que gira a −f,\ncon el largo x(t). El punto rojo es el promedio", 20).next_to(plano, DOWN).to_edge(LEFT, buff=0.3)
        self.play(FadeIn(explica))
        self.play(f.animate.set_value(0.05), run_time=4, rate_func=smooth)
        self.wait(1)
        a1 = COMPS[0][1]
        c1 = abs(z(0.05).mean())
        assert abs(c1 - a1 / 2) < 1e-9          # vueltas enteras: queda justo la mitad de la amplitud
        nota = texto(f"1 vuelta en 20 s: el promedio queda a {c1:.3f} del centro,\nla mitad de la amplitud {a1:.3f}", 20, color=RED).next_to(explica, DOWN, buff=0.15).to_edge(LEFT, buff=0.3)
        self.play(FadeIn(nota))
        self.wait(2)
        nota2 = texto("La otra mitad del seno gira al doble y se anula:\npor eso X lleva un 2, y 1/N es el promedio", 20, color=RED).next_to(explica, DOWN, buff=0.15).to_edge(LEFT, buff=0.3)
        self.play(FadeOut(nota), FadeIn(nota2))
        self.wait(2.5)
        self.play(FadeOut(nota2))
        self.play(f.animate.set_value(0.3), run_time=14, rate_func=linear)
        picos = VGroup(*[texto(f"{k}", 20, color=PRUEBA).next_to(ax.c2p(k / T, np.interp(k / T, fs, mag)), UP, buff=0.1)
                         for k in KS])
        self.play(FadeIn(picos), titulo.animate.become(
            texto("Un pico por onda, en k/T: eso es la transformada de Fourier", 32).to_edge(UP)))
        formula = MathTex(r"X(f) = \frac{2}{N}\sum_n x_n\, e^{-2\pi i f t_n}", font_size=40)\
            .next_to(ax, UP, buff=0.6)
        self.play(Write(formula))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Fuga(Scene):
    """Pregunta 3: vueltas enteras en la ventana caen en una sola casilla; si no, la onda se reparte."""

    def construct(self):
        N = 400
        ts = np.linspace(0, T, N, endpoint=False)
        ks = np.arange(0, 9)

        def espectro(x):
            return np.array([2 * abs((x * np.exp(-2j * np.pi * (k / T) * ts)).mean()) for k in ks])

        def fila(vueltas, ventana=None, color=LINEA):
            x = np.sin(2 * np.pi * vueltas / T * ts)
            if ventana is not None:
                x = x * ventana
            axs = Axes(x_range=[0, T, 5], y_range=[-1, 1, 1], x_length=6, y_length=1.6, tips=False,
                       axis_config={"stroke_opacity": 0.5})
            sig = axs.plot_line_graph(ts, x, add_vertex_dots=False, line_color=color, stroke_width=3)
            axb = Axes(x_range=[-0.5, 8.5, 1], y_range=[0, 1, 0.5], x_length=4.5, y_length=1.6, tips=False,
                       axis_config={"stroke_opacity": 0.5}).next_to(axs, RIGHT, buff=0.8)
            barras = VGroup(*[Rectangle(width=0.35, height=max(1e-3, axb.y_length * v), fill_color=color, fill_opacity=0.9,
                                        stroke_width=0).move_to(axb.c2p(k, 0), aligned_edge=DOWN)
                              for k, v in zip(ks, espectro(x))])
            nums = VGroup(*[texto(str(k), 16).next_to(axb.c2p(k, 0), DOWN, buff=0.1) for k in ks])
            return VGroup(axs, sig, axb, barras, nums)

        titulo = texto("¿Por qué vueltas enteras en la ventana?", 34).to_edge(UP)
        self.play(Write(titulo))
        a = fila(3).shift(UP * 1.3)
        la = texto("3 vueltas en 20 s", 24).next_to(a, LEFT, buff=0.2)
        self.play(Create(a[0]), Create(a[1]), FadeIn(la))
        self.play(Create(a[2]), FadeIn(a[4]), LaggedStart(*[GrowFromEdge(b, DOWN) for b in a[3]], lag_ratio=0.1))
        ok = texto("toda en la casilla 3", 22, color=GREEN).next_to(a[2], UP, buff=0.1).to_edge(RIGHT, buff=0.2)
        self.play(FadeIn(ok))

        b = fila(3.5, color=ORANGE).shift(DOWN * 1.4)
        lb = texto("3.5 vueltas", 24).next_to(b, LEFT, buff=0.2)
        self.play(Create(b[0]), Create(b[1]), FadeIn(lb))
        self.play(Create(b[2]), FadeIn(b[4]), LaggedStart(*[GrowFromEdge(x, DOWN) for x in b[3]], lag_ratio=0.1))
        fuga = texto("se fuga a las vecinas", 22, color=ORANGE).next_to(b[2], UP, buff=0.1).to_edge(RIGHT, buff=0.2)
        self.play(FadeIn(fuga))
        corte = Dot(b[0].c2p(T, np.sin(2 * np.pi * 3.5)), color=RED, radius=0.12)
        self.play(Flash(corte, color=RED), FadeIn(corte))
        salto = texto("el final no empalma: salta la pendiente", 20, color=RED).next_to(b[0], DOWN, buff=0.1)
        self.play(FadeIn(salto))
        self.wait(1.5)

        hann = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N) / N)
        c = fila(3.5, ventana=hann, color=PURPLE_A).move_to(b)
        self.play(titulo.animate.become(texto("Remedio: apagar los bordes (ventana de Hann)", 34).to_edge(UP)),
                  FadeOut(salto), FadeOut(corte), FadeOut(fuga))
        self.play(ReplacementTransform(b, c), lb.animate.become(texto("3.5 vueltas · Hann", 24).next_to(c, LEFT, buff=0.2)),
                  run_time=2)
        menos = texto("menos fuga lejos del pico", 22, color=PURPLE_A).next_to(c[2], UP, buff=0.1).to_edge(RIGHT, buff=0.2)
        self.play(FadeIn(menos))
        nota = texto("La línea no la necesita: cada una de sus ondas da vueltas enteras en T.", 24).to_edge(DOWN)
        self.play(FadeIn(nota))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class FrecuenciaDominante(Scene):
    """El pico más alto del espectro: el ritmo principal. window_features lo saca del largo del giro, |ω|."""

    def decir(self, s, size=24):
        nuevo = texto(s, size).to_edge(DOWN, buff=0.25)
        viejo = getattr(self, "_rotulo", None)
        self.play(*([FadeOut(viejo)] if viejo else []), FadeIn(nuevo), run_time=0.5)
        self._rotulo = nuevo

    def construct(self):
        n = int(2 * FS)                                       # dos segundos, a la rejilla de analyze_dataset.py
        t = np.arange(n) / FS
        rng = np.random.default_rng(4)
        gyr = rng.normal(0, 3, (n, 3))
        gyr[:, 1] += 90 * np.sin(2 * np.pi * 2.5 * t + 0.4) + 8 * np.sin(2 * np.pi * 9 * t)   # va y viene a 2.5 Hz, con temblor
        freqs = np.fft.rfftfreq(n, 1 / FS)
        banda = (freqs >= 0.3) & (freqs <= 15)

        def espectro(x):                                      # las líneas de window_features
            x = x - x.mean()
            return np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2

        e_y = espectro(gyr[:, 1])
        mag = np.linalg.norm(gyr, axis=1)
        e_m = espectro(mag)
        f_y = freqs[banda][np.argmax(e_y[banda])]
        f_m = freqs[banda][np.argmax(e_m[banda])]
        assert f_m == window_features(np.zeros((n, 3)), gyr, np.zeros(n), 0, n)[5]   # lo mismo que el código
        titulo = texto("La frecuencia dominante: el pico más alto", 34).to_edge(UP)
        a1 = Axes(x_range=[0, 2, 0.5], y_range=[-120, 120, 60], x_length=10.5, y_length=1.9, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18}).move_to(RIGHT * 0.6 + UP * 1.55)
        l1 = texto("giro y\n(°/s)", 18).next_to(a1, LEFT, buff=0.2)
        lt = texto("s", 18).next_to(a1.x_axis, RIGHT, buff=0.1)
        a2 = Axes(x_range=[0, 15, 1], y_range=[0, 1.1, 0.5], x_length=10.5, y_length=2.1, tips=False,
                  axis_config={"include_numbers": False}).move_to(RIGHT * 0.6 + DOWN * 1.55)
        a2.x_axis.add_numbers(range(0, 16, 1), font_size=16)
        l2 = texto("cuánto hay", 18).next_to(a2, LEFT, buff=0.2)
        lf = texto("Hz", 18).next_to(a2.x_axis, RIGHT, buff=0.1)
        self.play(Write(titulo), Create(a1), FadeIn(l1, lt))
        s_y = a1.plot_line_graph(t, gyr[:, 1], add_vertex_dots=False, line_color=PRUEBA, stroke_width=3)
        self.play(Create(s_y), run_time=1.5)
        self.decir("Dos segundos de la muñeca que va y viene, con un temblor encima")
        self.wait(1.5)
        ancho = a2.c2p(0.5, 0)[0] - a2.c2p(0, 0)[0]

        def barras(e, color):
            e = e / e[banda].max()
            return VGroup(*[Rectangle(width=0.8 * ancho, height=max(1e-3, a2.y_length / 1.1 * v), stroke_width=0, fill_color=color,
                                      fill_opacity=0.9).move_to(a2.c2p(fr, 0), aligned_edge=DOWN)
                            for fr, v in zip(freqs, e) if fr <= 15])
        b_y = barras(e_y, PRUEBA)
        self.play(Create(a2), FadeIn(l2, lf))
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in b_y], lag_ratio=0.03), run_time=1.5)
        self.decir("El espectro: cuánto hay de cada frecuencia, con la ventana de Hann")
        self.wait(1.5)
        pico = VGroup(Arrow(a2.c2p(f_y, 1.45), a2.c2p(f_y, 1.05), buff=0, color=LINEA, stroke_width=4),
                      texto(f"{f_y:.1f} Hz", 22, color=LINEA).move_to(a2.c2p(f_y + 1.3, 1.3)))
        self.play(FadeIn(pico))
        self.decir("Su pico más alto es la frecuencia dominante: el ritmo principal")
        self.wait(2.5)
        # lo que hace el código: el largo del giro, sin signo
        s_m = a1.plot_line_graph(t, mag, add_vertex_dots=False, line_color=LINEA, stroke_width=3)
        b_m = barras(e_m, LINEA)
        l1b = texto("|ω|\n(°/s)", 18, color=LINEA).move_to(l1)
        self.play(FadeOut(pico), ReplacementTransform(s_y, s_m), ReplacementTransform(l1, l1b), run_time=1.5)
        self.decir("window_features la saca de |ω|, el largo del giro, que no tiene signo")
        self.wait(1.5)
        self.play(ReplacementTransform(b_y, b_m), run_time=1.5)
        pico2 = VGroup(Arrow(a2.c2p(f_m, 1.45), a2.c2p(f_m, 1.05), buff=0, color=LINEA, stroke_width=4),
                       texto(f"{f_m:.1f} Hz", 22, color=LINEA).move_to(a2.c2p(f_m + 1.3, 1.3)))
        self.play(FadeIn(pico2))
        self.decir(f"Ida y vuelta son dos jorobas de |ω|: la dominante sale al doble, {f_m:.0f} Hz")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class RespuestaH(Scene):
    """Pregunta 4: H = Y/R por onda; llegar tarde τ gira H, y el error |1 − H| = 2|sen(πfτ)| crece con f."""

    def construct(self):
        plano = ComplexPlane(x_range=[-1.5, 1.5], y_range=[-1.5, 1.5], background_line_style={"stroke_opacity": 0.2})
        plano.scale(1.35).to_edge(LEFT, buff=0.6).shift(DOWN * 0.3)
        p = plano.n2p
        circ = Circle(radius=np.linalg.norm(p(1) - p(0)), color=WHITE, stroke_opacity=0.4).move_to(p(0))
        titulo = texto("Para cada onda: H = Y / R", 34).to_edge(UP)
        self.play(Write(titulo), Create(plano), Create(circ))

        uno = Arrow(p(0), p(1), buff=0, color=LINEA, stroke_width=6)
        l1 = texto("R / R = 1: la onda de la línea", 22, color=LINEA).next_to(p(1), DOWN + RIGHT, buff=0.1)
        self.play(GrowArrow(uno), FadeIn(l1))
        H = 0.8 * np.exp(-1j * np.radians(40))
        flecha = Arrow(p(0), p(H), buff=0, color=AGUJA, stroke_width=6)
        lh = texto("H = Y / R: tu aguja", 22, color=AGUJA).next_to(p(H), DOWN, buff=0.15)
        self.play(GrowArrow(flecha), FadeIn(lh))
        datos = VGroup(
            MathTex(r"|H| = 0.8", r"\ \text{: seguiste el 80\%}", font_size=32),
            MathTex(r"-\angle H / 2\pi f", r"\ \text{: tu retraso}", font_size=32),
            MathTex(r"|1 - H|", r"\ \text{: el error que quedó}", font_size=32, color=ERROR),
        ).arrange(DOWN, aligned_edge=LEFT).to_edge(RIGHT, buff=0.6).shift(UP * 0.8)
        err = Line(p(H), p(1), color=ERROR, stroke_width=6)
        for d in datos[:2]:
            self.play(FadeIn(d))
        self.play(Create(err), FadeIn(datos[2]))
        self.wait(2)

        self.play(FadeOut(VGroup(datos, l1, lh)), titulo.animate.become(
            texto("Si solo llegas tarde τ = 0.25 s: |H| = 1 y la fase gira 2πfτ", 30).to_edge(UP)))
        tau = 0.25
        fv = ValueTracker(0.0)
        Hf = lambda: np.exp(-2j * np.pi * fv.get_value() * tau)
        flecha2 = always_redraw(lambda: Arrow(p(0), p(Hf()), buff=0, color=AGUJA, stroke_width=6))
        err2 = always_redraw(lambda: Line(p(Hf()), p(1), color=ERROR, stroke_width=6))
        self.play(ReplacementTransform(flecha, flecha2), ReplacementTransform(err, err2))
        self.add(flecha2, err2)

        ax = Axes(x_range=[0, 2, 0.5], y_range=[0, 2, 0.5], x_length=5.2, y_length=3.4, tips=False,
                  axis_config={"include_numbers": True, "font_size": 18}).to_edge(RIGHT, buff=0.5).shift(DOWN * 0.4)
        xl = texto("frecuencia (Hz)", 20).next_to(ax, DOWN, buff=0.3)
        yl = MathTex(r"|1-H|", color=ERROR, font_size=30).next_to(ax, UP, buff=0.1).align_to(ax, LEFT)
        self.play(Create(ax), FadeIn(xl), FadeIn(yl))
        traza = always_redraw(lambda: ax.plot(lambda x: 2 * abs(np.sin(np.pi * x * tau)),
                                              x_range=[0, max(1e-3, fv.get_value())], color=ERROR, stroke_width=4))
        lbl = always_redraw(lambda: texto(f"f = {fv.get_value():.2f} Hz", 24).next_to(plano, UP, buff=0.1))
        self.add(traza, lbl)
        self.play(fv.animate.set_value(2), run_time=9, rate_func=linear)
        formula = MathTex(r"|1-H| = 2\,|\sin(\pi f \tau)|", font_size=38, color=ERROR).next_to(ax, UP, buff=0.55)
        self.play(Write(formula))
        sismo = [k / T for k in (2, 3, 5, 8, 13, 17)]
        puntos = VGroup(*[Dot(ax.c2p(x, 2 * abs(np.sin(np.pi * x * tau))), color=LINEA) for x in sismo])
        ln = texto("las ondas del\nnivel sismo", 20, color=LINEA).next_to(puntos[-1], RIGHT, buff=0.2).shift(DOWN * 0.35)
        self.play(FadeIn(puntos), FadeIn(ln))
        moral = texto("Lentas: casi no importa llegar tarde. Rápidas: el retraso es casi todo el error.", 24)\
            .to_edge(DOWN, buff=0.25)
        self.play(FadeIn(moral))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class RetrasoPorCorrelacion(Scene):
    """Tu retraso global: desplazar la línea τ y quedarse con el τ que más se parece a tu aguja."""

    def construct(self):
        rng = np.random.default_rng(2)
        ts = np.linspace(0, 10, 1000)
        tau_real = 0.25
        ruido = np.convolve(rng.normal(0, 0.05, ts.size), np.ones(15) / 15, mode="same")
        y = r(ts - tau_real) + ruido
        ym = y - y.mean()

        def corr(tau):
            x = r(ts - tau)
            x = x - x.mean()               # las dos centradas, como en sismomath.js
            return float((x * ym).sum() / np.sqrt((x * x).sum() * (ym * ym).sum()))

        taus = np.linspace(-0.8, 1.2, 201)
        cs = np.array([corr(v) for v in taus])
        ax = Axes(x_range=[0, 10, 2], y_range=[-0.8, 0.8, 0.4], x_length=11, y_length=2.6, tips=False,
                  axis_config={"stroke_opacity": 0.5}).to_edge(UP, buff=1.2)
        titulo = texto("¿Con cuánto retraso sigues la línea?", 34).to_edge(UP)
        linea = ax.plot(lambda t: r(t), color=LINEA, stroke_width=3)
        aguja = ax.plot_line_graph(ts, y, add_vertex_dots=False, line_color=AGUJA, stroke_width=3)
        ll = texto("línea", 22, color=LINEA).next_to(ax, LEFT, buff=0.2).shift(UP * 0.4)
        la = texto("tu aguja", 22, color=AGUJA).next_to(ll, DOWN)
        self.play(Write(titulo), Create(ax))
        self.play(Create(linea), FadeIn(ll))
        self.play(Create(aguja), FadeIn(la), run_time=2)
        self.wait(0.5)
        # una señal de N muestras es una flecha de N números: el producto punto y el largo valen igual
        flechas = VGroup(
            texto(f"Cada señal son {ts.size} muestras: una flecha de {ts.size} números.", 24),
            texto("El producto punto y el largo del capítulo 2 valen igual:", 24),
            MathTex(r"\text{parecido} = \frac{x \cdot y}{|x|\,|y|} = \cos(\text{ángulo entre las dos})", font_size=34),
            texto("x y y, las dos centradas: cada una menos su promedio", 20, color=GREY_B),
        ).arrange(DOWN, buff=0.2).to_edge(DOWN, buff=0.45)
        self.play(FadeIn(flechas[:2]))
        self.wait(1.5)
        self.play(Write(flechas[2]), FadeIn(flechas[3]))
        self.wait(3)
        self.play(FadeOut(flechas))

        tau = ValueTracker(-0.8)
        movida = always_redraw(lambda: ax.plot(lambda t: r(t - tau.get_value()), color=LINEA, stroke_width=3))
        self.play(FadeOut(linea), FadeIn(movida))
        axc = Axes(x_range=[-0.8, 1.2, 0.4], y_range=[0.4, 1, 0.2], x_length=8, y_length=2.4, tips=False,
                   axis_config={"include_numbers": True, "font_size": 18}).to_edge(DOWN, buff=0.8)
        xl = MathTex(r"\tau\ \text{(s)}", font_size=30).next_to(axc, RIGHT)
        yl = texto("parecido (correlación)", 20).next_to(axc, UP, buff=0.1).align_to(axc, LEFT)
        traza = always_redraw(lambda: axc.plot(lambda v: max(0.4, np.interp(v, taus, cs)),
                                               x_range=[-0.8, max(-0.799, tau.get_value())], color=GREEN, stroke_width=4))
        # Text y no MathTex: un MathTex nuevo en cada cuadro compila LaTeX cada vez (horas de render)
        val = always_redraw(lambda: texto(f"τ = {tau.get_value():.2f} s", 26).next_to(ax, DOWN, buff=0.1))
        self.play(Create(axc), FadeIn(xl), FadeIn(yl))
        self.add(traza, val)
        self.play(tau.animate.set_value(1.2), run_time=7, rate_func=linear)
        self.play(tau.animate.set_value(taus[cs.argmax()]), run_time=1.5)
        pico = Dot(axc.c2p(taus[cs.argmax()], cs.max()), color=GREEN)
        nota = texto(f"el máximo: τ = {taus[cs.argmax()]:.2f} s, llegas un cuarto de segundo tarde", 24, color=GREEN)\
            .next_to(axc, UP, buff=0.5)
        self.play(FadeIn(pico), Flash(pico), FadeIn(nota))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Remanente(Scene):
    """Pregunta 5: lo que moviste que no está en ninguna onda de la línea es tu ruido."""

    def construct(self):
        rng = np.random.default_rng(5)
        n = 2000
        ts = np.linspace(0, T, n, endpoint=False)
        seguido = sum(0.9 * a * np.sin(2 * np.pi * f * (ts - 0.25) + ph) for f, a, ph in COMPS)
        temblor = 0.04 * np.sin(2 * np.pi * 4.5 * ts + 1) + np.convolve(rng.normal(0, 0.12, n), np.ones(40) / 40, "same")
        deriva = 0.06 * np.sin(2 * np.pi * 0.023 * ts)
        y = seguido + temblor + deriva

        def ejes():
            return Axes(x_range=[0, T, 5], y_range=[-0.8, 0.8, 0.4], x_length=10, y_length=1.7, tips=False,
                        axis_config={"stroke_opacity": 0.5})

        titulo = texto("Tu ruido: lo que no está en ninguna onda de la línea", 32).to_edge(UP)
        a1, a2, a3 = ejes(), ejes(), ejes()
        VGroup(a1, a2, a3).arrange(DOWN, buff=0.45).next_to(titulo, DOWN, buff=0.35).shift(RIGHT * 1.4)
        g1 = a1.plot_line_graph(ts, y, add_vertex_dots=False, line_color=AGUJA, stroke_width=3)
        # la parte en las casillas de la línea, como la cuenta `analyze`: lo lento se fuga a ellas y queda adentro
        coef = [2 / n * (y * np.exp(-2j * np.pi * f * ts)).sum() for f, _, _ in COMPS]
        proy = sum((c * np.exp(2j * np.pi * f * ts)).real for c, (f, _, _) in zip(coef, COMPS))
        g2 = a2.plot_line_graph(ts, proy, add_vertex_dots=False, line_color=LINEA, stroke_width=3)
        g3 = a3.plot_line_graph(ts, y - proy, add_vertex_dots=False, line_color=ERROR, stroke_width=3)
        e1 = texto("tu aguja", 22, color=AGUJA).next_to(a1, LEFT, buff=0.2)
        e2 = texto("sus partes en\n0.05, 0.1, 0.15, 0.2 Hz", 18, color=LINEA).next_to(a2, LEFT, buff=0.2)
        e3 = texto("lo que sobra", 22, color=ERROR).next_to(a3, LEFT, buff=0.2)
        self.play(Write(titulo))
        self.play(Create(a1), Create(g1), FadeIn(e1), run_time=2)
        self.play(Create(a2), TransformFromCopy(g1, g2), FadeIn(e2), run_time=2)
        self.play(Create(a3), TransformFromCopy(g1, g3), FadeIn(e3), run_time=2)
        rem = 1 - sum(abs(2 / n * (y * np.exp(-2j * np.pi * f * ts)).sum()) ** 2 / 2 for f, _, _ in COMPS) / y.var()    # la cuenta del juego (`analyze`)
        nota = texto(f"Temblor y correcciones: el {rem * 100:.0f} % de tu movimiento. Eso es el remanente.\nLa deriva lenta casi no entra: se fuga a las ondas.", 22)\
            .to_edge(DOWN, buff=0.3)
        self.play(FadeIn(nota))
        self.wait(3)
        cuenta = VGroup(MathTex(r"\text{remanente} = 1 - \frac{1}{\operatorname{var}(y)}\sum_k \frac{|Y_k|^2}{2}", font_size=30),
                        texto("Una onda de amplitud |Y| tiene varianza |Y|²/2, y ondas distintas suman", 20))\
            .arrange(DOWN, buff=0.12).to_edge(DOWN, buff=0.12).shift(RIGHT * 1.2)
        self.play(FadeOut(nota), FadeIn(cuenta))
        self.wait(4)


# ---------------------------------------------------------------------------------------------------------
class Nyquist(Scene):
    """Pregunta 6: con f_s muestras por segundo, lo más rápido que f_s/2 se disfraza de lento."""

    def construct(self):
        fs = 10
        f = ValueTracker(1.0)
        ax = Axes(x_range=[0, 1, 0.1], y_range=[-1.3, 1.3, 1], x_length=11, y_length=3.6, tips=False,
                  axis_config={"stroke_opacity": 0.5}).shift(DOWN * 0.4)
        tn = np.arange(0, 1 + 1e-9, 1 / fs)
        titulo = texto("10 muestras por segundo", 34).to_edge(UP)
        self.play(Write(titulo), Create(ax))
        onda = always_redraw(lambda: ax.plot(lambda t: np.sin(2 * np.pi * f.get_value() * t + 0.3), x_range=[0, 1, 0.002],
                                             color=PRUEBA, stroke_width=3))
        puntos = always_redraw(lambda: VGroup(*[Dot(ax.c2p(t, np.sin(2 * np.pi * f.get_value() * t + 0.3)), color=LINEA, radius=0.09)
                                                 for t in tn]))
        alias = lambda: (f.get_value() + fs / 2) % fs - fs / 2
        disfraz = always_redraw(lambda: ax.plot(lambda t: np.sin(2 * np.pi * alias() * t + 0.3), x_range=[0, 1, 0.002],
                                                color=LINEA, stroke_width=3, stroke_opacity=0.9 if f.get_value() > fs / 2 else 0)
                                .set_stroke(opacity=0.9 if f.get_value() > fs / 2 else 0))
        lbl = always_redraw(lambda: texto(
            f"onda de {f.get_value():.1f} Hz" + (f"  →  las muestras dicen {abs(alias()):.1f} Hz" if f.get_value() > fs / 2 + 0.05 else ""),
            26, color=PRUEBA).next_to(ax, UP, buff=0.2))
        self.add(onda, puntos, lbl)
        self.wait(1)
        self.play(f.animate.set_value(4.0), run_time=4, rate_func=linear)
        abajo = [None]

        def decir(s, color=WHITE, size=24):
            nuevo = texto(s, size, color=color).to_edge(DOWN, buff=0.3)
            self.play(*([FadeOut(abajo[0])] if abajo[0] else []), FadeIn(nuevo), run_time=0.5)
            abajo[0] = nuevo
        self.play(f.animate.set_value(5.0), run_time=2)
        decir("A 5 Hz, media vuelta entre muestra y muestra: dos muestras por vuelta")
        self.wait(2)
        decir("el límite: f_s / 2 = 5 Hz (Nyquist)", LINEA, 26)
        self.wait(1)
        self.add(disfraz)
        self.play(f.animate.set_value(7.0), run_time=4, rate_func=linear)
        decir("7 Hz: 0.7 de vuelta por muestra, que se ve como 0.3 hacia atrás: 3 Hz")
        self.wait(3)
        self.play(f.animate.set_value(9.0), run_time=3, rate_func=linear)
        decir("9 Hz: 0.9 de vuelta se ve como 0.1 hacia atrás: 1 Hz")
        self.wait(2.5)
        decir("La regla: se le resta f_s hasta que cae entre −f_s/2 y f_s/2")
        self.wait(3)
        decir("No desaparecen: se disfrazan. Con el reloj a 100 muestras/s, el límite es 50 Hz.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
C_BAJO = 261.6256 / 2 ** 7     # 2.04 Hz: el do siete octavas por debajo del central (musica.js)
RAZONES = [1, 3, 2]            # el pulso [1 ; 3 ; 2]


def tren_de_pulsos(f0s, dur_por_paso, rate=44100):
    """Clics de las tres voces, con f₀ que se dobla en cada paso: golpes lentos → un acorde."""
    out = []
    fase = np.zeros(len(RAZONES))
    clic = np.exp(-np.arange(int(0.004 * rate)) / (0.0008 * rate))
    for f0 in f0s:
        n = int(dur_por_paso * rate)
        x = np.zeros(n + clic.size)
        for v, k in enumerate(RAZONES):
            per = rate / (k * f0)
            t = (1 - fase[v]) * per if fase[v] > 0 else 0.0
            while t < n:
                i = int(t)
                x[i:i + clic.size] += clic * (1.0 if k == 1 else 0.6)
                t += per
            fase[v] = ((n - (t - per)) / per) % 1
        out.append(x[:n])
    return np.concatenate(out)


class RitmoYArmonia(Scene):
    """Pregunta 7: [1 ; 3 ; 2] lento es un polirritmo; rápido, un acorde. La misma figura a distinta velocidad."""

    def construct(self):
        pasos = [C_BAJO * 2 ** i for i in range(7)]     # 2.04 Hz … 130.8 Hz (do3)
        dur = 3.0
        write_wav(sound_path("ritmo.wav"), tren_de_pulsos(pasos, dur))
        titulo = texto("Pulsos [1 ; 3 ; 2]: tres voces que coinciden cada 1/f₀", 32).to_edge(UP)
        self.play(Write(titulo))
        filas = VGroup()
        for k, color in zip(RAZONES, (LINEA, PRUEBA, BLUE)):
            ax = NumberLine(x_range=[0, 2, 0.5], length=10, include_ticks=False, stroke_opacity=0.5)
            golpes = VGroup(*[Dot(ax.n2p(j / k), radius=0.11, color=color) for j in range(2 * k + 1)])
            filas.add(VGroup(ax, golpes, MathTex(rf"{k}\,f_0", font_size=34, color=color).next_to(ax, LEFT)))
        filas.arrange(DOWN, buff=0.8).shift(DOWN * 0.2)
        juntos = VGroup(*[DashedLine(filas[0][0].n2p(c) + UP * 0.5, filas[-1][0].n2p(c) + DOWN * 0.5, stroke_opacity=0.5)
                          for c in (0, 1, 2)])
        ventana = texto("se muestran 2 ciclos de f₀", 20).next_to(filas, DOWN, buff=0.4)
        self.play(*[Create(fl) for fl in filas], Create(juntos), FadeIn(ventana))
        self.wait(0.3)
        self.add_sound(sound_path("ritmo.wav"))
        cursor = Line(UP * 2.2, DOWN * 2.6, color=WHITE, stroke_width=2)
        for i, f0 in enumerate(pasos):
            lbl = texto(f"f₀ = {f0:.2f} Hz" if f0 < 10 else f"f₀ = {f0:.1f} Hz", 28).to_edge(DOWN, buff=0.35)
            nota = ("golpes: un polirritmo de 3 contra 2" if f0 < 8 else
                    "ya casi no se cuentan..." if f0 < 20 else
                    "ya no son golpes: es una nota, do con sus armónicos 2 (do) y 3 (sol)")
            n = texto(nota, 24, color=GREEN if f0 >= 20 else WHITE).next_to(lbl, UP, buff=0.15)
            self.add(lbl, n)
            if f0 < 8:      # el cursor recorre los dos ciclos mientras suenan
                c = cursor.copy().move_to(filas[0][0].n2p(0)).set_y(filas.get_center()[1])
                self.add(c)
                self.play(c.animate.move_to(filas[0][0].n2p(2)).set_y(filas.get_center()[1]),
                          run_time=min(dur, 2 / f0), rate_func=linear)
                self.remove(c)
                if 2 / f0 < dur:
                    self.wait(dur - 2 / f0)
            else:
                self.play(*[Indicate(fl[1], scale_factor=1.15) for fl in filas], run_time=dur)
            self.remove(lbl, n)
        fin = texto("Ritmo y armonía son lo mismo a distinta velocidad.", 30).to_edge(DOWN, buff=0.5)
        self.play(FadeIn(fin))
        self.wait(2)


class Octavas(Scene):
    """Pregunta 8: subir una octava es ×2; un semitono, ×2^(1/12)."""

    def construct(self):
        rate = 44100
        dos = [65.406 * 2 ** i for i in range(5)]      # do2 … do6
        tonos = []
        for f in dos:
            t = np.arange(int(1.0 * rate)) / rate
            env = np.minimum(1, t / 0.01) * np.exp(-t * 2.5)
            tonos.append(env * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)))
        write_wav(sound_path("octavas.wav"), np.concatenate(tonos))

        titulo = texto("Subir una octava es multiplicar por 2", 34).to_edge(UP)
        self.play(Write(titulo))
        lin = NumberLine(x_range=[0, 1100, 100], length=12, include_numbers=True, font_size=18).shift(UP * 1.2)
        ll = texto("Hz, escala normal", 20).next_to(lin, DOWN, buff=0.45)
        log = NumberLine(x_range=[np.log2(65.406), np.log2(65.406 * 16) + 0.01, 1], length=10, include_ticks=True)\
            .shift(DOWN * 1.5)
        lg = texto("cada salto, ×2 (escala logarítmica)", 20).next_to(log, DOWN, buff=0.6)
        self.play(Create(lin), FadeIn(ll), Create(log), FadeIn(lg))
        self.add_sound(sound_path("octavas.wav"))
        en_hz = VGroup()
        for i, f in enumerate(dos):
            en_hz.add(Dot(lin.n2p(f), color=LINEA))
            self.add(en_hz[-1])
            d2 = Dot(log.n2p(np.log2(f)), color=LINEA, radius=0.1)
            n = texto(f"do · {f:.0f} Hz", 18, color=LINEA).next_to(d2, UP)
            self.play(FadeIn(d2, scale=2), FadeIn(n), run_time=0.4)
            self.wait(0.6)
        nota = texto("En hercios los saltos crecen; en octavas son iguales: el oído cuenta multiplicando.", 24)\
            .to_edge(DOWN, buff=0.2)
        self.play(FadeIn(nota))
        self.wait(1.5)
        semi = VGroup(*[Line(log.n2p(np.log2(261.63) + s / 12) + DOWN * 0.15, log.n2p(np.log2(261.63) + s / 12) + UP * 0.15,
                             color=PRUEBA) for s in range(13)])
        f1 = MathTex(r"\text{semitono} = \times 2^{1/12} \approx \times 1.0595", font_size=34, color=PRUEBA)
        f2 = MathTex(r"f(m) = 440 \cdot 2^{(m-69)/12}\ \text{Hz}", font_size=34)
        VGroup(f1, f2).arrange(DOWN, buff=0.4).move_to(UP * 1.0)
        self.play(FadeOut(nota), FadeOut(lin, ll, en_hz))
        self.play(Create(semi), Write(f1))
        self.play(Write(f2))
        self.wait(3)
