"""Animaciones del capítulo 3 (Derivar e integrar con números), una por concepto.

    python docs/curso/animaciones/render.py cap03                    # todas, a GIF en docs/curso/media/cap03/
    python -m manim -ql docs/curso/animaciones/cap03.py ErrorAcumulado   # una, rápido, para mirarla

Las señales son inventadas, con números de reloj de verdad (100 muestras por segundo, sesgo de 0.3 °/s). La media
móvil es la de tools/analyze_dataset.py, importada tal cual; lo que las escenas afirman lo comprueba tools/test_derivar.js.
"""
import os
import sys

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "..", "tools"))
from analyze_dataset import movavg      # noqa: E402  la de verdad

TASA, ANGULO, ERROR, SUAVE, CRUDO = BLUE, YELLOW, RED, GREEN, GREY_B


def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


def ejes(x, y, ancho=10.5, alto=2.2, numeros=True, **kw):
    return Axes(x_range=x, y_range=y, x_length=ancho, y_length=alto, tips=False,
                axis_config={"include_numbers": numeros, "font_size": 18}, **kw)


def media_movil(x, n):
    return movavg(np.asarray(x, float)[:, None], n)[:, 0]


# ---------------------------------------------------------------------------------------------------------
class DerivarConNumeros(Scene):
    """Cuánto cambia por segundo: la diferencia hacia adelante y la central."""

    def construct(self):
        x = lambda t: 1.1 * np.sin(0.9 * t) + 0.35 * t
        dx = lambda t: 0.99 * np.cos(0.9 * t) + 0.35
        dt = 0.5
        ts = np.arange(0, 8.01, dt)
        titulo = texto("Derivar con números", 34).to_edge(UP)
        a1 = ejes([0, 8, 1], [-1, 4, 1], alto=2.5)
        a2 = ejes([0, 8, 1], [-1, 2, 1], alto=2.0)
        VGroup(a1, a2).arrange(DOWN, buff=0.5).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 0.6)
        l1 = texto("x", 22).next_to(a1, LEFT, buff=0.25)
        l2 = texto("cuánto cambia\npor segundo", 18).next_to(a2, LEFT, buff=0.2)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2))
        muestras = VGroup(*[Dot(a1.c2p(t, x(t)), radius=0.06, color=ANGULO) for t in ts])
        self.play(LaggedStart(*[FadeIn(m, scale=2) for m in muestras], lag_ratio=0.05), run_time=1.5)

        k = ValueTracker(1)
        tk = lambda: ts[int(k.get_value())]
        adel = always_redraw(lambda: Line(a1.c2p(tk(), x(tk())), a1.c2p(tk() + dt, x(tk() + dt)), color=ERROR, stroke_width=5))
        cent = always_redraw(lambda: Line(a1.c2p(tk() - dt, x(tk() - dt)), a1.c2p(tk() + dt, x(tk() + dt)), color=SUAVE, stroke_width=5))
        punto = always_redraw(lambda: Dot(a1.c2p(tk(), x(tk())), radius=0.1, color=WHITE))
        f1 = MathTex(r"\frac{x[k+1]-x[k]}{\Delta t}", font_size=30, color=ERROR).move_to(a1.c2p(1.1, 3.3))
        f2 = MathTex(r"\frac{x[k+1]-x[k-1]}{2\,\Delta t}", font_size=30, color=SUAVE).move_to(a1.c2p(3.3, 3.3))
        self.add(punto)
        self.play(Create(adel), Write(f1))
        self.play(Create(cent), Write(f2))
        verdad = a2.plot(dx, x_range=[0, 8, 0.02], color=WHITE, stroke_width=2, stroke_opacity=0.5)
        self.play(Create(verdad), run_time=1)
        de_adel, de_cent = VGroup(), VGroup()
        self.add(de_adel, de_cent)
        for i in range(1, len(ts) - 1):
            k.set_value(i)
            t = ts[i]
            de_adel.add(Dot(a2.c2p(t, (x(t + dt) - x(t)) / dt), radius=0.06, color=ERROR))
            de_cent.add(Dot(a2.c2p(t, (x(t + dt) - x(t - dt)) / (2 * dt)), radius=0.06, color=SUAVE))
            self.wait(0.33)
        nota = texto("La central usa la muestra de antes y la de después: cae más cerca de la curva.", 22)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeIn(nota))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class SegundaDiferencia(Scene):
    """La aceleración con tres posiciones: lo que falta para que todo siguiera igual."""

    def construct(self):
        x = lambda t: 0.09 * t ** 3 - 0.75 * t ** 2 + 1.8 * t + 0.4
        acc = lambda t: 0.54 * t - 1.5
        dt = 0.8
        titulo = texto("La segunda diferencia: tres muestras dan la aceleración", 30).to_edge(UP)
        a1 = ejes([0, 6.5, 1], [0, 5, 1], alto=3.0)
        a2 = ejes([0, 6.5, 1], [-2, 3, 1], alto=1.6)
        VGroup(a1, a2).arrange(DOWN, buff=0.45).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 0.6)
        l1 = texto("posición", 20).next_to(a1, LEFT, buff=0.2)
        l2 = texto("aceleración", 20).next_to(a2, LEFT, buff=0.2)
        curva = a1.plot(x, x_range=[0, 6.4, 0.02], color=CRUDO, stroke_width=3)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2), Create(curva))
        tt = ValueTracker(0.8)

        def tres():
            t = tt.get_value()
            p0, p1, p2 = [a1.c2p(s, x(s)) for s in (t - dt, t, t + dt)]
            seguir = a1.c2p(t + dt, 2 * x(t) - x(t - dt))
            return VGroup(Line(p0, p1, color=SUAVE, stroke_width=5), DashedLine(p1, seguir, color=SUAVE),
                          Line(seguir, p2, color=ERROR, stroke_width=7), *[Dot(p, color=ANGULO, radius=0.08) for p in (p0, p1, p2)])

        g = always_redraw(tres)
        self.add(g)
        n1 = texto("Si nada cambiara, seguiría por la punteada. Lo que falta (rojo), dividido por Δt², es la aceleración.", 22)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeIn(n1))
        self.wait(2)
        f = MathTex(r"a[k] = \frac{x[k+1]-2x[k]+x[k-1]}{\Delta t^2}", font_size=30).move_to(a1.c2p(2.0, 4.2))
        self.play(Write(f))
        traza = always_redraw(lambda: a2.plot(acc, x_range=[0.8, max(0.82, tt.get_value()), 0.02], color=ERROR, stroke_width=4))
        self.add(traza)
        self.play(tt.animate.set_value(5.6), run_time=7, rate_func=linear)
        n2 = texto("Así sale de la animación del mocap lo que leería el acelerómetro del reloj.", 22).to_edge(DOWN, buff=0.15)
        self.play(FadeOut(n1), FadeIn(n2))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class IntegrarConNumeros(Scene):
    """Sumar tasa × Δt muestra a muestra da cuánto cambió en total, y Δt lo dice el reloj."""

    def construct(self):
        titulo = texto("Integrar: sumar tasa × Δt", 34).to_edge(UP)
        w = lambda t: 40 * np.sin(0.9 * t) * np.exp(-0.12 * t) + 8
        dt = 0.2
        ts = np.arange(0, 8, dt)
        a1 = ejes([0, 8, 1], [-30, 50, 20], alto=2.3)
        a2 = ejes([0, 8, 1], [0, 120, 40], alto=2.0)
        VGroup(a1, a2).arrange(DOWN, buff=0.5).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 0.6)
        l1 = texto("giroscopio\n(°/s)", 18, color=TASA).next_to(a1, LEFT, buff=0.2)
        l2 = texto("ángulo (°)", 18, color=ANGULO).next_to(a2, LEFT, buff=0.2)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2))
        f = MathTex(r"\theta \approx \sum_k \omega[k]\,\Delta t", font_size=34).to_corner(UR).shift(DOWN * 1.0)
        self.play(Write(f))
        barras, escalones = VGroup(), VGroup()
        self.add(barras, escalones)
        suma = 0.0
        lect = texto("", 22)
        for t in ts:
            v = float(w(t))
            b = Polygon(a1.c2p(t, 0), a1.c2p(t + dt, 0), a1.c2p(t + dt, v), a1.c2p(t, v), stroke_width=1, stroke_color=BLACK,
                        fill_color=TASA if v >= 0 else ERROR, fill_opacity=0.8)
            nuevo = suma + v * dt
            barras.add(b)
            escalones.add(Line(a2.c2p(t, suma), a2.c2p(t + dt, nuevo), color=ANGULO, stroke_width=4))
            suma = nuevo
            self.remove(lect)
            lect = texto(f"esta muestra: {v:+.1f} °/s × {dt} s = {v * dt:+.1f}°      total: {suma:.1f}°", 22).to_edge(DOWN, buff=0.2)
            self.add(lect)
            self.wait(0.15)
        self.wait(1)
        self.remove(lect)
        self.play(FadeOut(barras, escalones))

        # una muestra perdida: el reloj dice cuánto pasó de verdad
        t_ok = np.arange(0, 8, 0.05)
        guardar = np.ones(len(t_ok), bool)
        guardar[40:50] = False                                 # se pierde medio segundo
        tq = t_ok[guardar]
        wq = w(tq)
        fijo = np.cumsum(wq) * 0.05
        real = np.cumsum(wq * np.diff(tq, prepend=tq[0] - 0.05))
        verdad = np.cumsum(w(t_ok)) * 0.05
        hueco = Rectangle(width=a1.c2p(t_ok[50], 0)[0] - a1.c2p(t_ok[40], 0)[0], height=a1.height, color=ERROR, stroke_width=0,
                          fill_opacity=0.18).move_to(a1.c2p((t_ok[40] + t_ok[50]) / 2, 10))
        gw = a1.plot(w, x_range=[0, 8, 0.02], color=TASA, stroke_width=3)
        self.play(Create(gw), FadeIn(hueco))
        gv = linea(a2, t_ok, verdad, WHITE, 3)
        gf = linea(a2, tq, fijo, ERROR, 3)
        gr = linea(a2, tq, real, SUAVE, 3)
        n = texto("Se pierde medio segundo. Con Δt fijo (rojo) falta ese tramo; con el reloj (verde), no.", 22)\
            .to_edge(DOWN, buff=0.2)
        self.play(Create(gv), FadeIn(n))
        self.play(Create(gf), run_time=1.5)
        self.play(Create(gr), run_time=1.5)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ErrorAcumulado(Scene):
    """Un sesgo se vuelve b·t; el ruido, un paseo al azar que crece como √t."""

    def construct(self):
        titulo = texto("Integrar acumula error", 34).to_edge(UP)
        a1 = ejes([0, 60, 10], [0, 20, 5], ancho=5.8, alto=4.0)
        a2 = ejes([0, 60, 10], [-3, 3, 1], ancho=5.8, alto=4.0)
        VGroup(a1, a2).arrange(RIGHT, buff=1.0).next_to(titulo, DOWN, buff=0.75)
        t1 = texto("un sesgo de 0.3 °/s", 24, color=ERROR).next_to(a1, UP, buff=0.15)
        t2 = texto("ruido de 2 °/s a 100 muestras/s", 24, color=TASA).next_to(a2, UP, buff=0.15)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(t1, t2))
        g = linea(a1, [0, 60], [0, 18], ERROR, 5)
        self.play(Create(g), run_time=2.5)
        l1 = MathTex(r"b\,t = 18^\circ", font_size=32, color=ERROR).move_to(a1.c2p(19, 17.5))
        l1b = texto("en una hora: 1080°, tres vueltas", 18, color=ERROR).next_to(l1, DOWN, buff=0.12)
        self.play(Write(l1), FadeIn(l1b))

        rng = np.random.default_rng(2)
        hz, sigma, n = 100, 2.0, 6000
        dt = 1 / hz
        paseos = np.cumsum(rng.normal(0, sigma, (300, n)), axis=1) * dt
        t = np.arange(1, n + 1) * dt
        paso = 30
        grupo = VGroup(*[linea(a2, t[::paso], p[::paso], TASA, 1.2, stroke_opacity=0.5) for p in paseos[:16]])
        self.play(LaggedStart(*[Create(x) for x in grupo], lag_ratio=0.08), run_time=4)
        env = sigma * np.sqrt(t * dt)
        arriba = linea(a2, t[::paso], env[::paso], WHITE, 3)
        abajo = linea(a2, t[::paso], -env[::paso], WHITE, 3)
        self.play(Create(arriba), Create(abajo), run_time=1.5)
        l2 = MathTex(r"\sigma\sqrt{t\,\Delta t}", font_size=34).move_to(a2.c2p(20, 2.4))
        medido = paseos[:, -1].std()
        l2b = texto(f"a los 60 s: {env[-1]:.2f}° predichos, {medido:.2f}° en 300 paseos", 18).next_to(a2, DOWN, buff=0.15)
        self.play(Write(l2), FadeIn(l2b))
        moral = texto("El ruido se cancela en parte y crece como √t; el sesgo crece como t.", 24)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeIn(moral))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class DosVecesIntegrar(Scene):
    """De la aceleración a la posición: un sesgo crece como t²."""

    def construct(self):
        titulo = texto("Integrar dos veces", 34).to_edge(UP)
        b = 0.05
        t = np.linspace(0, 10, 200)
        a1 = ejes([0, 10, 2], [0, 0.1, 0.05], ancho=9.5, alto=1.2)
        a2 = ejes([0, 10, 2], [0, 0.6, 0.2], ancho=9.5, alto=1.3)
        a3 = ejes([0, 10, 2], [0, 3, 1], ancho=9.5, alto=1.5)
        VGroup(a1, a2, a3).arrange(DOWN, buff=0.35).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 1.4)
        l1 = texto("error de aceleración\n(m/s²)", 18).next_to(a1, LEFT, buff=0.25)
        l2 = texto("de velocidad (m/s)", 18).next_to(a2, LEFT, buff=0.25)
        l3 = texto("de posición (m)", 18).next_to(a3, LEFT, buff=0.25)
        self.play(Write(titulo), Create(a1), Create(a2), Create(a3), FadeIn(l1, l2, l3))
        g1 = linea(a1, t, b + 0 * t, ERROR, 4)
        self.play(Create(g1), run_time=1)
        f1 = MathTex(r"b = 0.05", font_size=30, color=ERROR).move_to(a1.c2p(8.5, 0.085))
        self.play(Write(f1))
        g2 = linea(a2, t, b * t, ORANGE, 4)
        f2 = MathTex(r"b\,t = 0.5", font_size=30, color=ORANGE).move_to(a2.c2p(2.2, 0.45))
        self.play(Create(g2), Write(f2), run_time=2)
        g3 = linea(a3, t, b * t ** 2 / 2, ANGULO, 4)
        f3 = MathTex(r"\tfrac12 b\,t^2 = 2.5", font_size=30, color=ANGULO).move_to(a3.c2p(2.8, 2.2))
        self.play(Create(g3), Write(f3), run_time=3)
        moral = texto("Un error que casi no se ve: 2.5 m en 10 s, 90 m en un minuto.", 24)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeIn(moral))
        self.wait(3)


class VelocidadCero(Scene):
    """Si se sabe que está quieto al empezar y al terminar, la velocidad que sobra es error (ZUPT)."""

    def construct(self):
        titulo = texto("Velocidad cero: lo que se sabe sin medir", 34).to_edge(UP)
        dt, dur = 0.005, 1.2
        t = np.arange(0, dur, dt)
        u = t / dur
        x = 60 * (6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3)              # un trazo de 60 mm, quieto en los dos extremos
        v = 60 / dur * 30 * u ** 2 * (1 - u) ** 2
        a = 60 / dur ** 2 * 60 * u * (1 - u) * (1 - 2 * u)
        rng = np.random.default_rng(6)
        medida = a + 150 + rng.normal(0, 40, len(t))                    # mm/s²: un sesgo de 0.15 m/s² y ruido
        v_cruda = np.cumsum(medida) * dt
        v_zupt = v_cruda - np.linspace(0, 1, len(t)) * v_cruda[-1]      # como tools/analyze_drawing.py: watch_features
        x_cruda, x_zupt = np.cumsum(v_cruda) * dt, np.cumsum(v_zupt) * dt

        a1 = ejes([0, 1.2, 0.2], [0, 400, 100], alto=2.2)
        a2 = ejes([0, 1.2, 0.2], [0, 200, 50], alto=2.2)
        VGroup(a1, a2).arrange(DOWN, buff=0.45).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 0.8)
        l1 = texto("velocidad\n(mm/s)", 18).next_to(a1, LEFT, buff=0.2)
        l2 = texto("posición\n(mm)", 18).next_to(a2, LEFT, buff=0.2)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2))
        self.play(Create(linea(a1, t, v, WHITE, 3)), Create(linea(a2, t, x, WHITE, 3)), run_time=1.5)
        leyenda = VGroup(texto("blanco: el trazo de verdad, 60 mm en 1.2 s", 20),
                         texto("rojo: el acelerómetro integrado, con un sesgo de 0.15 m/s²", 20, color=ERROR))\
            .arrange(DOWN, aligned_edge=LEFT, buff=0.1).move_to(a1.c2p(0.03, 395), aligned_edge=UL)
        self.play(FadeIn(leyenda[0]))
        cruda_v = linea(a1, t, v_cruda, ERROR, 3)
        cruda_x = linea(a2, t, x_cruda, ERROR, 3)
        self.play(Create(cruda_v), Create(cruda_x), FadeIn(leyenda[1]), run_time=2)
        fin = DoubleArrow(a1.c2p(1.19, 0), a1.c2p(1.19, v_cruda[-1]), buff=0, color=ERROR, stroke_width=4, tip_length=0.15)
        n1 = texto(f"Pero el dedo está quieto al levantarse: esos {v_cruda[-1]:.0f} mm/s del final son error.", 22).to_edge(DOWN, buff=0.15)
        self.play(GrowFromCenter(fin), FadeIn(n1))
        self.wait(2)
        lz = texto("verde: lo mismo, repartiendo ese error", 20, color=SUAVE).next_to(leyenda, DOWN, aligned_edge=LEFT, buff=0.1)
        self.play(Create(linea(a1, t, v_zupt, SUAVE, 4)), Create(linea(a2, t, x_zupt, SUAVE, 4)), FadeIn(lz), run_time=2.5)
        n2 = texto(f"Error al final: {abs(x_cruda[-1] - x[-1]):.0f} mm sin velocidad cero, {abs(x_zupt[-1] - x[-1]):.1f} mm con ella (ZUPT).", 22)\
            .to_edge(DOWN, buff=0.15)
        self.play(FadeOut(n1), FadeIn(n2))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Suavizar(Scene):
    """Promediar con lo reciente: deja pasar lo lento, frena lo rápido, y llega tarde."""

    def construct(self):
        titulo = texto("Suavizar: promediar con lo reciente", 34).to_edge(UP)
        rng = np.random.default_rng(3)
        hz = 100
        t = np.arange(0, 6, 1 / hz)
        limpia = 0.6 * np.sin(2 * np.pi * 0.25 * t) + 1.2 * (t > 3.5)
        x = limpia + rng.normal(0, 0.22, len(t))
        ax = ejes([0, 6, 1], [-1.5, 2.5, 1], alto=4.2)
        ax.next_to(titulo, DOWN, buff=0.4)
        self.play(Write(titulo), Create(ax))
        cruda = linea(ax, t, x, CRUDO, 1.5)
        self.play(Create(cruda), run_time=2)

        n = 30
        i = ValueTracker(n)
        ventana = always_redraw(lambda: Rectangle(width=ax.c2p(t[int(i.get_value())], 0)[0] - ax.c2p(t[int(i.get_value()) - n], 0)[0],
                                                  height=ax.height, stroke_width=0, fill_color=TASA, fill_opacity=0.2)
                                .move_to(ax.c2p((t[int(i.get_value())] + t[int(i.get_value()) - n]) / 2, 0.5)))
        media = media_movil(x, n)
        traza = always_redraw(lambda: linea(ax, t[n:int(i.get_value()) + 1], media[n:int(i.get_value()) + 1], TASA, 4)
                              if int(i.get_value()) > n + 1 else VectorizedPoint())
        c1 = texto("media móvil: el promedio de las últimas n muestras (n = 30: 0.3 s)", 22, color=TASA).to_edge(DOWN, buff=0.15)
        self.add(ventana, traza)
        self.play(FadeIn(c1))
        self.play(i.animate.set_value(len(t) - 1), run_time=6, rate_func=linear)
        self.remove(ventana)

        def olvida(alfa):
            y = np.zeros_like(x)
            y[0] = x[0]
            for k in range(1, len(x)):
                y[k] = y[k - 1] + alfa * (x[k] - y[k - 1])
            return y

        c2 = MathTex(r"y \leftarrow y + \alpha\,(x - y)", font_size=34).move_to(ax.c2p(4.9, -0.25))
        c2b = texto("un promedio que olvida: no guarda la ventana", 22).to_edge(DOWN, buff=0.15)
        self.play(FadeOut(c1), traza.animate.set_stroke(opacity=0.0), FadeIn(c2b), Write(c2))
        self.remove(traza)
        marcas = VGroup()
        for j, (alfa, c) in enumerate([(0.2, YELLOW), (0.05, ORANGE), (0.015, RED)]):
            g = linea(ax, t, olvida(alfa), c, 4)
            lt = MathTex(rf"\alpha = {alfa}", font_size=24, color=c).next_to(c2, DOWN, buff=0.1 + 0.3 * j)
            self.play(Create(g), FadeIn(lt), run_time=2)
            marcas.add(g, lt)
        flecha = Arrow(ax.c2p(3.5, -1.5), ax.c2p(3.5, -0.8), buff=0, color=WHITE, stroke_width=4)
        n2 = texto("Lo que se pierde: cuanto más suave, más tarde llega al salto de t = 3.5 s.", 24).to_edge(DOWN, buff=0.15)
        self.play(GrowArrow(flecha), FadeOut(c2b), FadeIn(n2))
        self.wait(3)


class DerivarAmplificaRuido(Scene):
    """Dividir por un Δt chico agranda cada temblor: antes de derivar hay que suavizar."""

    def construct(self):
        titulo = texto("Derivar amplifica el ruido", 34).to_edge(UP)
        rng = np.random.default_rng(8)
        hz = 100
        dt = 1 / hz
        t = np.arange(0, 6, dt)
        limpia = np.sin(2 * np.pi * 0.25 * t)
        ruido = 0.01
        x = limpia + rng.normal(0, ruido, len(t))
        central = lambda s: (s[2:] - s[:-2]) / (2 * dt)
        crudo = central(x)
        n = 12
        suave = central(media_movil(x, n))
        verdad = 2 * np.pi * 0.25 * np.cos(2 * np.pi * 0.25 * t)
        a1 = ejes([0, 6, 1], [-1.5, 1.5, 1], ancho=9.5, alto=1.5)
        a2 = ejes([0, 6, 1], [-3, 3, 1.5], ancho=9.5, alto=1.7)
        a3 = ejes([0, 6, 1], [-3, 3, 1.5], ancho=9.5, alto=1.7)
        VGroup(a1, a2, a3).arrange(DOWN, buff=0.3).next_to(titulo, DOWN, buff=0.25).shift(RIGHT * 1.4)
        l1 = texto(f"la señal\n(ruido de {ruido})", 18).next_to(a1, LEFT, buff=0.2)
        l2 = texto("derivada directa", 18, color=ERROR).next_to(a2, LEFT, buff=0.2)
        l3 = texto("suavizar y derivar", 18, color=SUAVE).next_to(a3, LEFT, buff=0.2)
        self.play(Write(titulo), Create(a1), Create(a2), Create(a3), FadeIn(l1))
        self.play(Create(linea(a1, t, x, ANGULO, 3)), run_time=1.5)
        self.play(FadeIn(l2), Create(linea(a2, t[1:-1], crudo, ERROR, 1.5)), run_time=2)
        self.play(Create(linea(a2, t, verdad, WHITE, 2)), run_time=1)
        f = MathTex(r"\frac{\sigma}{\sqrt2\,\Delta t}", rf"= {ruido / (np.sqrt(2) * dt):.2f}", font_size=26, color=ERROR).next_to(l2, DOWN, buff=0.15)
        n1 = texto(f"Un ruido que no se ve: {ruido} se vuelve {(crudo - verdad[1:-1]).std():.2f}. Dividir por Δt = 0.01 agranda cada temblor.", 22)\
            .to_edge(DOWN, buff=0.15)
        self.play(Write(f), FadeIn(n1))
        self.wait(2)
        self.play(FadeIn(l3), Create(linea(a3, t[1:-1], suave, SUAVE, 3)), run_time=2)
        self.play(Create(linea(a3, t, verdad, WHITE, 2)), run_time=1)
        n2 = texto("Antes de derivar hay que suavizar: se paga con un poco de atraso.", 22).to_edge(DOWN, buff=0.15)
        self.play(FadeOut(n1), FadeIn(n2))
        self.wait(3)


class QuitarLoLento(Scene):
    """La señal menos su promedio reciente deja solo los cambios rápidos: un golpe se ve aunque la mano se mueva."""

    def construct(self):
        titulo = texto("Quitar lo lento: que el golpe se vea", 34).to_edge(UP)
        rng = np.random.default_rng(5)
        hz = 100
        t = np.arange(0, 5, 1 / hz)
        lento = 3 * np.sin(2 * np.pi * 0.4 * t) + 1.5 * np.sin(2 * np.pi * 0.9 * t + 1)
        golpes = np.zeros_like(t)
        for t0, a in [(1.3, 2.2), (3.4, -2.6)]:
            golpes += a * np.exp(-((t - t0) / 0.012) ** 2)
        x = lento + golpes + rng.normal(0, 0.04, len(t))
        prom = media_movil(x, 4)
        hp = x - prom
        a1 = ejes([0, 5, 1], [-6, 6, 3], ancho=9.5, alto=2.1)
        a2 = ejes([0, 5, 1], [-3, 3, 1.5], ancho=9.5, alto=2.1)
        VGroup(a1, a2).arrange(DOWN, buff=0.4).next_to(titulo, DOWN, buff=0.3).shift(RIGHT * 1.4)
        l1 = texto("aceleración (m/s²)\ny su promedio", 18).next_to(a1, LEFT, buff=0.2)
        l2 = texto("lo que cambió\nen 40 ms", 18, color=ANGULO).next_to(a2, LEFT, buff=0.2)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1))
        self.play(Create(linea(a1, t, x, CRUDO, 2)), run_time=2)
        n1 = texto("La mano se mueve despacio y hay dos golpes: se pierden en el movimiento.", 22).to_edge(DOWN, buff=0.15)
        self.play(FadeIn(n1))
        self.wait(1.5)
        self.play(Create(linea(a1, t, prom, TASA, 3)), run_time=1.5)
        self.play(FadeIn(l2), Create(linea(a2, t, hp, ANGULO, 3)), run_time=2.5)
        n2 = texto("Paso alto: la señal menos su promedio de 40 ms. Quedan los dos golpes.", 22).to_edge(DOWN, buff=0.15)
        self.play(FadeOut(n1), FadeIn(n2))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class CurvaSuave(Scene):
    """3u² − 2u³ va de 0 a 1 con pendiente cero en los dos extremos."""

    def construct(self):
        titulo = texto("Una curva suave: 3u² − 2u³", 34).to_edge(UP)
        s = lambda u: 3 * u ** 2 - 2 * u ** 3
        a1 = ejes([0, 1, 0.25], [0, 1, 0.5], ancho=5, alto=3.1)
        a2 = ejes([0, 1, 0.25], [0, 1.6, 0.5], ancho=5, alto=3.1)
        VGroup(a1, a2).arrange(RIGHT, buff=1.0).next_to(titulo, DOWN, buff=0.7)
        l1 = texto("adónde va", 22).next_to(a1, UP, buff=0.1)
        l2 = texto("qué tan rápido va", 22).next_to(a2, UP, buff=0.1)
        self.play(Write(titulo), Create(a1), Create(a2), FadeIn(l1, l2))
        g_l = a1.plot(lambda u: u, x_range=[0, 1, 0.01], color=ERROR, stroke_width=4)
        g_s = a1.plot(s, x_range=[0, 1, 0.01], color=SUAVE, stroke_width=4)
        d_l = linea(a2, [0, 0, 1, 1], [0, 1, 1, 0], ERROR, 4)
        d_s = a2.plot(lambda u: 6 * u - 6 * u ** 2, x_range=[0, 1, 0.01], color=SUAVE, stroke_width=4)
        self.play(Create(g_l), Create(d_l), run_time=1.5)
        self.play(Create(g_s), Create(d_s), run_time=1.5)
        riel_y = -3.0
        riel = Line(LEFT * 5, RIGHT * 5, color=GREY_B).shift(UP * riel_y)
        u = ValueTracker(0)
        b1 = always_redraw(lambda: Dot([-5 + 10 * u.get_value(), riel_y + 0.22, 0], color=ERROR, radius=0.14))
        b2 = always_redraw(lambda: Dot([-5 + 10 * s(u.get_value()), riel_y - 0.22, 0], color=SUAVE, radius=0.14))
        self.play(Create(riel), FadeIn(b1, b2))
        self.play(u.animate.set_value(1), run_time=2.5, rate_func=linear)
        self.play(u.animate.set_value(0), run_time=0.01)
        self.wait(0.3)
        self.play(u.animate.set_value(1), run_time=2.5, rate_func=linear)
        n = texto("Recta: arranca y frena de golpe. Curva suave: pendiente cero en los dos extremos.", 22).to_edge(DOWN, buff=0.08)
        self.play(FadeOut(riel, b1, b2), FadeIn(n))
        self.wait(3)


class UnaOnda(Scene):
    """a·sen(2πft + φ): amplitud, frecuencia y fase."""

    def construct(self):
        titulo = texto("Una onda: lo más simple que va y viene", 34).to_edge(UP)
        ax = ejes([0, 4, 1], [-2, 2, 1], alto=3.8)
        ax.next_to(titulo, DOWN, buff=0.75)
        a, f, ph = ValueTracker(1), ValueTracker(0.5), ValueTracker(0)
        onda = always_redraw(lambda: ax.plot(lambda t: a.get_value() * np.sin(2 * PI * f.get_value() * t + ph.get_value()),
                                             x_range=[0, 4, 0.01], color=ANGULO, stroke_width=4))
        formula = MathTex(r"a\,\sin(2\pi f t + \varphi)", font_size=40).next_to(titulo, DOWN, buff=0.15)
        lect = always_redraw(lambda: texto(f"a = {a.get_value():.1f}      f = {f.get_value():.2f} vueltas/s      φ = {ph.get_value():.1f} rad", 24)
                             .to_edge(DOWN, buff=0.75))
        self.play(Write(titulo), Create(ax), Write(formula))
        self.add(onda, lect)

        def decir(s, viejo=None):
            n = texto(s, 24).to_edge(DOWN, buff=0.2)
            self.play(*([FadeOut(viejo)] if viejo else []), FadeIn(n), run_time=0.5)
            return n

        n = decir("La amplitud a: qué tan lejos va.")
        self.play(a.animate.set_value(1.8), run_time=1.5)
        self.play(a.animate.set_value(0.7), run_time=1.5)
        self.play(a.animate.set_value(1.2), run_time=1)
        n = decir("La frecuencia f: cuántas vueltas por segundo.", n)
        self.play(f.animate.set_value(2), run_time=2.5)
        self.play(f.animate.set_value(1), run_time=1.5)
        n = decir("La fase φ: dónde empieza.", n)
        self.play(ph.animate.set_value(2 * PI), run_time=3, rate_func=linear)
        self.play(ph.animate.set_value(1), run_time=1)
        self.wait(2.5)


class IntegrarUnaOnda(Scene):
    """Integrar a·sen(2πft) da amplitud a/(2πf): lo rápido casi no mueve el ángulo."""

    def construct(self):
        titulo = texto("Ir y venir rápido casi no mueve el ángulo", 32).to_edge(UP)
        a = 100
        filas = VGroup()
        izq, der = [], []
        for f in (0.5, 2, 8):
            ai = ejes([0, 2, 1], [-120, 120, 120], ancho=4.6, alto=1.2, numeros=False)
            ad = ejes([0, 2, 1], [-40, 40, 40], ancho=4.6, alto=1.2, numeros=False)
            ai.y_axis.add_numbers(font_size=16)
            ad.y_axis.add_numbers(font_size=16)
            filas.add(VGroup(ai, ad).arrange(RIGHT, buff=0.9))
            izq.append(ai)
            der.append(ad)
        filas.arrange(DOWN, buff=0.25).next_to(titulo, DOWN, buff=0.6)
        h1 = texto("el giroscopio (°/s)", 22, color=TASA).next_to(izq[0], UP, buff=0.1)
        h2 = texto("el ángulo (°)", 22, color=ANGULO).next_to(der[0], UP, buff=0.1)
        self.play(Write(titulo), *[Create(x) for x in izq + der], FadeIn(h1, h2))
        for f, ai, ad in zip((0.5, 2, 8), izq, der):
            lf = texto(f"{f} Hz", 20).next_to(ai, LEFT, buff=0.3)
            gi = ai.plot(lambda t: a * np.sin(2 * PI * f * t), x_range=[0, 2, 0.002], color=TASA, stroke_width=2.5)
            amp = a / (2 * PI * f)
            gd = ad.plot(lambda t: -amp * np.cos(2 * PI * f * t), x_range=[0, 2, 0.002], color=ANGULO, stroke_width=3)
            la = texto(f"±{amp:.1f}°", 20, color=ANGULO).next_to(ad, RIGHT, buff=0.15)
            self.play(FadeIn(lf), Create(gi), run_time=1.3)
            self.play(Create(gd), FadeIn(la), run_time=1.3)
        f = MathTex(r"\int a\sin(2\pi f t)\,dt \;\to\; \text{amplitud}\ \frac{a}{2\pi f}", font_size=30).to_edge(DOWN, buff=0.6)
        self.play(Write(f))
        moral = texto("La misma tasa, 16 veces más rápido: el ángulo es 16 veces más chico.", 22).to_edge(DOWN, buff=0.1)
        self.play(FadeIn(moral))
        self.wait(3)
