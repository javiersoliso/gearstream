"""Animaciones del capítulo 0 (Un número que cambia), una por concepto.

    python docs/curso/animaciones/render.py cap00 Senal Muestreo ...   # a GIF en docs/curso/media/cap00/
    python -m manim -ql docs/curso/animaciones/cap00.py Muestreo       # una, rápido, para mirarla

Las señales son inventadas, con números de reloj de verdad. Lo que no se inventa: la línea del Sismógrafo es wave de
server/web/sismomath.js (datos_cap00.js la corre con node y aquí se compara), `norm` y las constantes de tiempo son
las de tools/air_mouse.py, importadas tal cual, y `map_time` es el método de tools/sdb_bridge.py, leído del archivo
(sdb_bridge.py no se puede importar sin websockets). Lo que las escenas afirman lo comprueba tools/test_muestreo.js.
"""
import ast
import json
import math
import os
import statistics
import subprocess
import sys
import types

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(AQUI, "..", "..", "..", "tools")
sys.path.insert(0, TOOLS)
from air_mouse import BASELINE_RISE_MS_PER_S, GAP_MS, STALE_MS, norm as norm_px     # noqa: E402  las de verdad

D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap00.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)
SENAL, MUESTRA, ERROR, BIEN, SUAVE = BLUE, YELLOW, RED, GREEN, GREY_B
MONO = "Consolas"


# ---------- la cuenta ----------
def wave(t):
    """sismomath.js:wave con los componentes de datos_cap00.js."""
    t = np.asarray(t, float)
    return sum(c["a"] * np.sin(2 * np.pi * c["f"] * t + c["ph"]) for c in D["comps"])


assert np.allclose(wave(D["ts"]), D["ys"])


def cargar_map_time():
    """Bridge.map_time tal cual está en tools/sdb_bridge.py, con un reloj de pared de mentira."""
    arbol = ast.parse(open(os.path.join(TOOLS, "sdb_bridge.py"), encoding="utf-8").read())
    constantes = {n.targets[0].id: ast.literal_eval(n.value) for n in arbol.body if isinstance(n, ast.Assign)
                  and getattr(n.targets[0], "id", "") in ("OFFSET_LEAK_MS", "MAX_TS_JUMP_MS")}
    clase = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "Bridge")
    metodo = next(n for n in clase.body if isinstance(n, ast.FunctionDef) and n.name == "map_time")
    reloj = types.SimpleNamespace(ahora_s=0.0)
    reloj.time = lambda: reloj.ahora_s
    entorno = dict(constantes, time=reloj)
    exec(compile(ast.Module([metodo], []), "sdb_bridge.py", "exec"), entorno)
    return entorno["map_time"], reloj, constantes


# ---------- dibujo ----------
def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


def codigo(s, size=22, **kw):
    return Text(s, font_size=size, font=MONO, **kw)


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


def apilar(a1, a2, buff):
    """Uno debajo del otro, con el mismo cero: los instantes de los dos quedan en la misma vertical."""
    a2.next_to(a1, DOWN, buff=buff)
    a2.shift(RIGHT * (a1.c2p(0, 0)[0] - a2.c2p(0, 0)[0]))
    return VGroup(a1, a2)


def linea(ax, xs, ys, color, w=3, **kw):
    return ax.plot_line_graph(np.asarray(xs, float), np.asarray(ys, float), add_vertex_dots=False, line_color=color,
                              stroke_width=w, **kw)


class Escena(Scene):
    """Un título arriba y un solo rótulo abajo a la vez."""

    def titulo(self, s, size=34):
        t = texto(s, size).to_edge(UP, buff=0.3)
        self.play(Write(t), run_time=0.8)
        return t

    def decir(self, s, color=WHITE, size=24, espera=2.5):
        nuevo = texto(s, size, color=color)
        if nuevo.width > 13.2:                                # en dos líneas, cortando cerca de la mitad
            corte = min((i for i, c in enumerate(s) if c == " "), key=lambda i: abs(i - len(s) / 2))
            nuevo = VGroup(texto(s[:corte], size - 1, color=color), texto(s[corte + 1:], size - 1, color=color)).arrange(DOWN, buff=0.1)
        nuevo.to_edge(DOWN, buff=0.14)
        viejo = getattr(self, "rotulo", None)
        if viejo is not None:
            self.play(FadeOut(viejo), FadeIn(nuevo), run_time=0.5)
        else:
            self.play(FadeIn(nuevo), run_time=0.5)
        self.rotulo = nuevo
        if espera:
            self.wait(espera)


# ---------------------------------------------------------------------------------------------------------
class Senal(Escena):
    """Un punto que sube y baja, y su historia: un número que cambia con el tiempo."""

    def construct(self):
        self.titulo("Un número que cambia")
        T = 12
        ax = ejes([0, T, 2], [-1, 1, 0.5], ancho=9.3, alto=4.4).shift(RIGHT * 1.0 + DOWN * 0.1)
        et = texto("t (s)", 20).next_to(ax.x_axis, RIGHT, buff=0.12)
        riel_x = ax.c2p(0, 0)[0] - 2.1
        riel = Line([riel_x, ax.c2p(0, -1)[1], 0], [riel_x, ax.c2p(0, 1)[1], 0], color=SUAVE, stroke_width=3)
        marcas = VGroup(*[Line([riel_x - 0.1, ax.c2p(0, v)[1], 0], [riel_x + 0.1, ax.c2p(0, v)[1], 0], color=SUAVE)
                          for v in (-1, -0.5, 0, 0.5, 1)])
        self.play(Create(riel), Create(marcas))
        tt = ValueTracker(0)
        alto = lambda: ax.c2p(0, float(wave(tt.get_value())))[1]
        punto = always_redraw(lambda: Dot([riel_x, alto(), 0], radius=0.13, color=MUESTRA))
        lect = lecturas([("x =", lambda: float(wave(tt.get_value())), 2, MUESTRA)], 26).next_to(riel, UP, buff=0.15)
        self.add(punto, lect)
        self.decir("Un punto que sube y baja: en cada instante es un solo número.", espera=0)
        self.play(tt.animate.set_value(2.5), run_time=2.5, rate_func=linear)
        self.play(tt.animate.set_value(0), run_time=1.2)
        self.play(Create(ax), FadeIn(et), run_time=0.8)
        fin = always_redraw(lambda: DashedLine([riel_x, alto(), 0], ax.c2p(tt.get_value(), float(wave(tt.get_value()))),
                                               color=SUAVE, stroke_width=2))
        traza = always_redraw(lambda: ax.plot(lambda s: float(wave(s)), x_range=[0, max(0.05, tt.get_value()), 0.05],
                                              color=SENAL, stroke_width=4))
        self.add(traza, fin)
        self.decir("Si guardas ese número para cada instante, tienes una curva: x(t).", espera=0)
        self.play(tt.animate.set_value(T), run_time=9, rate_func=linear)
        f = MathTex(r"x(t)", font_size=44, color=SENAL).move_to(ax.c2p(10.8, 0.8))
        self.play(Write(f))
        self.decir("Eso es una señal: un número que cambia con el tiempo.", espera=2)
        self.decir("Esta es la línea del Sismógrafo. El giro de tu muñeca es otra.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class Unidades(Escena):
    """La misma curva con otros números en el costado: cambiar de unidad es multiplicar."""

    def construct(self):
        self.titulo("Cada número viene con su medida")
        # un giro inventado que llega a 300 °/s
        giro = lambda t: 300 * np.exp(-((t - 1.6) / 0.55) ** 2) - 150 * np.exp(-((t - 3.6) / 0.6) ** 2)
        ax = ejes([0, 5, 1], [-300, 300, 100], ancho=8.5, alto=3.8, numeros=False, y_axis_config={"include_ticks": True})\
            .shift(RIGHT * 1.6 + UP * 0.05)
        ax.x_axis.add_numbers(font_size=18)
        curva = ax.plot(giro, x_range=[0, 5, 0.02], color=SENAL, stroke_width=4)
        marcas = [-300, -200, -100, 0, 100, 200, 300]

        def costado(factor, dec):
            return VGroup(*[texto(f"{v * factor:.{dec}f}", 18).next_to(ax.c2p(0, v), LEFT, buff=0.15) for v in marcas])

        lado = costado(1, 0)
        unidad = texto("°/s", 26, color=MUESTRA).next_to(ax, LEFT, buff=1.0)
        self.play(Create(ax), Create(curva), FadeIn(lado), FadeIn(unidad))
        pico = Dot(ax.c2p(1.6, float(giro(1.6))), color=MUESTRA)
        valor = texto(f"{giro(1.6):.0f} °/s", 26, color=MUESTRA).next_to(pico, UR, buff=0.1)
        self.play(FadeIn(pico, scale=2), FadeIn(valor))
        self.decir("Trescientos ¿qué? Sin unidad, el número no dice nada.")
        for factor, dec, nombre, formula, frase in (
                (1 / 360, 2, "vueltas/s", r"\times\ \tfrac{1}{360}", "Una vuelta son 360°: se divide entre 360."),
                (60 / 360, 0, "vueltas/min", r"\times\ 60", "Un minuto son 60 s: se multiplica por 60.")):
            nuevo = costado(factor, dec)
            nuevo_u = texto(nombre, 24, color=MUESTRA).next_to(ax, LEFT, buff=0.85)
            nuevo_v = texto(f"{giro(1.6) * factor:.{2 if dec else 0}f} {nombre}", 26, color=MUESTRA).next_to(pico, UR, buff=0.1)
            f = MathTex(formula, font_size=36, color=BIEN).move_to(ax.c2p(4.1, 240))
            self.play(Write(f))
            self.play(Transform(lado, nuevo), Transform(unidad, nuevo_u), Transform(valor, nuevo_v), run_time=1.2)
            self.decir(frase)
            self.play(FadeOut(f))
        self.decir("La curva no se movió. Solo cambiaron los números del costado.", espera=3)
        self.play(FadeOut(VGroup(ax, curva, lado, unidad, pico, valor)))

        # en el código
        cuentas = [("int(parts[0]) / 1000", f"µs a ms:  1 234 567 µs = {1234567 / 1000:.3f} ms", "Bridge.read_sensor"),
                   ("60000 / intervalo", f"ms entre giros a giros por minuto:  500 ms = {D['giros_por_minuto']:.0f} por minuto",
                    "FlickDetector"),
                   ("ceil(px · 65536 / tamaño)", f"píxeles a 0..65535:  960 de 1920 = {norm_px(960, 0, 1920)}", "norm")]
        filas = VGroup()
        for c, que, donde in cuentas:
            filas.add(VGroup(codigo(c, 26, color=MUESTRA), texto(que, 22), texto(donde, 18, color=SUAVE))
                      .arrange(DOWN, aligned_edge=LEFT, buff=0.12))
        filas.arrange(DOWN, aligned_edge=LEFT, buff=0.45).move_to(UP * 0.1)
        for fila in filas:
            self.play(FadeIn(fila, shift=RIGHT * 0.2), run_time=0.7)
            self.wait(0.8)
        self.decir("En el código, cambiar de unidad es siempre una multiplicación o una división.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class Muestreo(Escena):
    """Medir cada Δt: más medidas por segundo, menos se pierde; y entre dos medidas no se sabe."""

    def construct(self):
        self.titulo("Muestrear: medir cada cierto tiempo")
        T = 6
        x = lambda t: wave(3 * np.asarray(t, float) + 3)
        ax = ejes([0, T, 1], [-1.25, 1.25, 0.5], ancho=10, alto=3.7).shift(RIGHT * 0.5 + DOWN * 0.45)
        curva = ax.plot(lambda s: float(x(s)), x_range=[0, T, 0.02], color=SENAL, stroke_width=3)
        f1 = MathTex(r"t_k = t_0 + k\,\Delta t", font_size=34).move_to(LEFT * 4.8 + UP * 2.3)
        f2 = MathTex(r"f = \frac{1}{\Delta t}", font_size=34).next_to(f1, RIGHT, buff=0.8)
        self.play(Create(ax), Create(curva))
        self.decir("La señal no para. La computadora solo puede guardar algunos de sus valores.", espera=1)
        self.play(Write(f1), Write(f2))
        grupo = lect = relleno = None
        dt_denso = np.linspace(0, T, 1201)
        for f in (1, 2, 5, 20):
            tk = np.arange(0, T + 1e-9, 1 / f)
            xk = x(tk)
            palos = VGroup(*[Line(ax.c2p(t, 0), ax.c2p(t, v), color=MUESTRA, stroke_width=2) for t, v in zip(tk, xk)])
            puntos = VGroup(*[Dot(ax.c2p(t, v), radius=0.07 if f < 20 else 0.045, color=MUESTRA) for t, v in zip(tk, xk)])
            recta = np.interp(dt_denso, tk, xk)
            error = np.abs(recta - x(dt_denso)).max()
            nuevo = VGroup(palos, puntos)
            texto_f = texto(f"f = {f} Hz   Δt = {1000 / f:.0f} ms   {len(tk)} muestras   error {error:.3f}", 21,
                            color=MUESTRA).next_to(f2, RIGHT, buff=0.4)
            assert texto_f.get_right()[0] < 6.9
            trazo = np.concatenate([[ax.c2p(t, v) for t, v in zip(dt_denso, x(dt_denso))],
                                    [ax.c2p(t, v) for t, v in zip(dt_denso[::-1], recta[::-1])]])
            nuevo_r = Polygon(*trazo, stroke_width=0, fill_color=ERROR, fill_opacity=0.5)
            if grupo is None:
                self.play(LaggedStart(*[FadeIn(p, scale=2) for p in puntos], lag_ratio=0.1), FadeIn(palos), FadeIn(texto_f))
                grupo, lect = nuevo, texto_f
                self.add(grupo)
                self.decir("Lo que hizo la señal entre una medida y otra se pierde (en rojo).", espera=0)
                relleno = nuevo_r
                self.play(FadeIn(relleno))
                self.wait(2)
            else:
                self.play(FadeOut(grupo), FadeOut(relleno), FadeOut(lect), FadeIn(nuevo), FadeIn(nuevo_r), FadeIn(texto_f), run_time=0.8)
                grupo, relleno, lect = nuevo, nuevo_r, texto_f
                self.wait(1.6)
        self.decir("Más muestras por segundo, menos rojo: la frecuencia de muestreo se mide en Hz.", espera=2)

        # entre dos medidas no se sabe
        f = 2
        tk = np.arange(0, T + 1e-9, 1 / f)
        xk = x(tk)
        otra1 = lambda s: x(s) + 0.42 * np.sin(2 * np.pi * f * s)
        otra2 = lambda s: x(s) - 0.3 * np.sin(2 * np.pi * 2 * f * s)
        assert np.allclose(otra1(tk), xk) and np.allclose(otra2(tk), xk)
        assert max(np.abs(otra1(dt_denso)).max(), np.abs(otra2(dt_denso)).max()) < 1.25
        puntos = VGroup(*[Dot(ax.c2p(t, v), radius=0.08, color=MUESTRA) for t, v in zip(tk, xk)])
        texto_f = texto(f"f = {f} Hz   Δt = {1000 / f:.0f} ms   {len(tk)} muestras", 22, color=MUESTRA).next_to(f2, RIGHT, buff=0.4)
        self.play(FadeOut(grupo), FadeOut(relleno), FadeOut(lect), FadeIn(puntos), FadeIn(texto_f))
        self.decir("¿Qué pasó entre dos medidas? Mira tres señales con las mismas muestras.", espera=0.5)
        c1 = ax.plot(lambda s: float(otra1(s)), x_range=[0, T, 0.01], color=BIEN, stroke_width=3)
        c2 = ax.plot(lambda s: float(otra2(s)), x_range=[0, T, 0.01], color=ORANGE, stroke_width=3)
        self.play(Create(c1), run_time=2)
        self.play(Create(c2), run_time=2)
        self.decir("Las muestras no pueden distinguirlas. Lo de en medio solo se puede suponer.", espera=3.5)


# ---------------------------------------------------------------------------------------------------------
class MarcaDeTiempo(Escena):
    """Contar muestras no alcanza: cada una trae su hora y Δt no siempre es el mismo."""

    def construct(self):
        self.titulo("Cada muestra trae su hora")
        rng = np.random.default_rng(4)
        x = lambda t: wave(np.asarray(t, float) * 3 + 1.0)
        dts = 10 + rng.normal(0, 1.0, 400).round()            # ms, parejos pero no iguales
        tk = np.cumsum(dts) - dts[0]
        hueco = (tk > 1500) & (tk < 2000)                     # medio segundo que no llegó
        tq, xq = tk[~hueco & (tk <= 4000)] / 1000, x(tk[~hueco & (tk <= 4000)] / 1000)
        deltas = np.diff(tq) * 1000
        contar = np.arange(len(tq)) * 0.01
        a1 = ejes([0, 4, 1], [-0.7, 0.7, 0.7], ancho=9.5, alto=1.8)
        a2 = ejes([0, 4, 1], [-0.7, 0.7, 0.7], ancho=9.5, alto=1.8)
        VGroup(a1, a2).arrange(DOWN, buff=0.75).shift(RIGHT * 1.35 + DOWN * 0.15)
        l1 = texto("contando muestras:\nt = k · 10 ms", 19).next_to(a1, LEFT, buff=0.3)
        l2 = texto("con la hora\nde cada una", 19).next_to(a2, LEFT, buff=0.3)
        verdad = [a.plot(lambda s: float(x(s)), x_range=[0, 4, 0.02], color=WHITE, stroke_width=2, stroke_opacity=0.4) for a in (a1, a2)]
        self.play(Create(a1), Create(a2), FadeIn(l1, l2), Create(verdad[0]), Create(verdad[1]))
        self.decir(f"Se pierde medio segundo de muestras. La curva blanca es lo que pasó de verdad.", espera=1)
        g1 = linea(a1, contar, xq, ERROR, 4)
        g2 = VGroup(linea(a2, tq[tq < 1.6], xq[tq < 1.6], BIEN, 4), linea(a2, tq[tq > 1.9], xq[tq > 1.9], BIEN, 4))
        self.play(Create(g1), run_time=2.5)
        self.decir(f"Si solo cuentas, todo llega antes: terminas en {contar[-1]:.2f} s en vez de {tq[-1]:.2f} s.")
        self.play(Create(g2), run_time=2.5)
        banda = Rectangle(width=a2.c2p(tq[tq > 1.6][0] + (deltas.max() / 1000), 0)[0] - a2.c2p(tq[tq > 1.6][0], 0)[0], height=1.8,
                          stroke_width=0, fill_color=ERROR, fill_opacity=0.2)\
            .move_to(a2.c2p(tq[np.argmax(deltas)] + deltas.max() / 2000, 0))
        self.play(FadeIn(banda))
        self.decir("Con su hora, cada muestra cae donde debe y el hueco se ve como hueco.")
        f = MathTex(r"\Delta t_k = t_{k+1} - t_k", font_size=34).to_corner(UR).shift(DOWN * 0.1 + LEFT * 0.2)
        self.play(Write(f))
        self.decir(f"Δt: mediana {np.median(deltas):.0f} ms, de {deltas[deltas < GAP_MS].min():.0f} a {deltas[deltas < GAP_MS].max():.0f} ms, "
                   f"y un hueco de {deltas.max():.0f} ms.", MUESTRA, espera=3)
        self.decir(f"Motion.feed_gyro resta las horas; pasando de {GAP_MS} ms, lo trata como un hueco.", espera=3.5)


# ---------------------------------------------------------------------------------------------------------
class InterpolacionLineal(Escena):
    """La recta entre dos muestras, y cómo lleva a dos sensores a una misma rejilla."""

    def construct(self):
        self.titulo("Entre dos muestras: la recta que las une")
        t0, t1, x0, x1 = 20.0, 30.0, 1.2, 2.2
        ax = ejes([15, 35, 5], [0, 3, 1], ancho=7.0, alto=3.5).shift(LEFT * 2.6 + DOWN * 0.4)
        et = texto("t (ms)", 18).next_to(ax.x_axis, DOWN, buff=0.35).align_to(ax, RIGHT)
        p0, p1 = Dot(ax.c2p(t0, x0), color=MUESTRA, radius=0.1), Dot(ax.c2p(t1, x1), color=MUESTRA, radius=0.1)
        l0 = MathTex(r"(t_k,\,x_k)", font_size=28, color=MUESTRA).next_to(p0, DOWN + LEFT, buff=0.05)
        l1 = MathTex(r"(t_{k+1},\,x_{k+1})", font_size=28, color=MUESTRA).next_to(p1, UP, buff=0.1)
        recta = Line(p0.get_center(), p1.get_center(), color=SENAL, stroke_width=4)
        self.play(Create(ax), FadeIn(et), FadeIn(p0, p1, l0, l1))
        self.decir("Con dos muestras y nada más, lo más simple es suponer una recta.", espera=0.5)
        self.play(Create(recta))
        f = MathTex(r"x(t) \approx x_k + u\,(x_{k+1}-x_k)", font_size=32).move_to(RIGHT * 3.9 + UP * 1.5)
        g = MathTex(r"u = \frac{t - t_k}{t_{k+1}-t_k}", font_size=32).next_to(f, DOWN, buff=0.3)
        self.play(Write(f), Write(g))
        tt = ValueTracker(t0)
        u = lambda: (tt.get_value() - t0) / (t1 - t0)
        xv = lambda: x0 + u() * (x1 - x0)
        punto = always_redraw(lambda: Dot(ax.c2p(tt.get_value(), xv()), color=BIEN, radius=0.11))
        guia = always_redraw(lambda: DashedLine(ax.c2p(tt.get_value(), 0), ax.c2p(tt.get_value(), xv()), color=BIEN, stroke_width=2))
        lect = lecturas([("t (ms) =", lambda: tt.get_value(), 1), ("u =", u), ("x ≈", xv)], 24, BIEN, col=1.6).next_to(g, DOWN, buff=0.35)
        self.add(guia, punto, lect)
        self.decir("u dice qué parte del camino llevas: 0 en la primera muestra, 1 en la segunda.", espera=0)
        self.play(tt.animate.set_value(t1), run_time=3, rate_func=there_and_back)
        self.play(tt.animate.set_value(24), run_time=1)
        self.wait(2)
        self.play(FadeOut(VGroup(ax, et, p0, p1, l0, l1, recta, f, g)), FadeOut(punto, guia, lect))
        self.remove(punto, guia, lect)

        # dos sensores, una rejilla
        rng = np.random.default_rng(9)
        x = lambda t: wave(np.asarray(t, float) / 12 + 4.0)
        y = lambda t: 0.8 * wave(np.asarray(t, float) / 9 + 8.0) + 0.1
        ta = np.cumsum(10 + rng.normal(0, 1.2, 11)) - 7
        tb = np.cumsum(10 + rng.normal(0, 1.2, 11)) - 3
        rej = np.arange(10, 101, 10.0)
        a1 = ejes([0, 120, 10], [-0.6, 0.6, 0.6], ancho=10, alto=1.85, numeros=False)
        a2 = ejes([0, 120, 10], [-0.6, 0.6, 0.6], ancho=10, alto=1.85)
        apilar(a1, a2, 0.35).shift(RIGHT * 1.2 + UP * 0.3)
        assert max(ta.max(), tb.max()) < 120
        la = texto("sensor A", 20, color=SENAL).next_to(a1, LEFT, buff=0.3)
        lb = texto("sensor B", 20, color=ORANGE).next_to(a2, LEFT, buff=0.3)
        pa = VGroup(*[Dot(a1.c2p(t, float(x(t))), radius=0.06, color=SENAL) for t in ta])
        pb = VGroup(*[Dot(a2.c2p(t, float(y(t))), radius=0.06, color=ORANGE) for t in tb])
        self.play(FadeIn(a1, a2, la, lb), FadeIn(pa, pb))
        self.decir("Dos sensores miden, cada uno a su hora. Sus muestras no caen en los mismos instantes.", espera=1.5)
        ra = linea(a1, ta, x(ta), SENAL, 2)
        rb = linea(a2, tb, y(tb), ORANGE, 2)
        verticales = VGroup(*[DashedLine(a1.c2p(t, 0.6), a2.c2p(t, -0.6), color=WHITE, stroke_width=1.5, stroke_opacity=0.6) for t in rej])
        self.play(Create(ra), Create(rb))
        self.play(Create(verticales))
        self.decir("Se elige una rejilla pareja y se lee cada recta en esos instantes.", espera=0.5)
        ga = np.interp(rej, ta, x(ta))
        gb = np.interp(rej, tb, y(tb))
        qa = VGroup(*[Dot(a1.c2p(t, v), radius=0.085, color=BIEN) for t, v in zip(rej, ga)])
        qb = VGroup(*[Dot(a2.c2p(t, v), radius=0.085, color=BIEN) for t, v in zip(rej, gb)])
        self.play(LaggedStart(*[FadeIn(q, scale=2) for q in [*qa, *qb]], lag_ratio=0.06), run_time=2)
        self.play(FadeOut(pa, pb, ra, rb))
        self.decir("Interpolar para cambiar de instantes es remuestrear; ahora se comparan punto a punto.", espera=1.5)
        self.decir("Es np.interp en analyze_drawing.py, analyze_dataset.py y export_mocap.py.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class Cuantizar(Escena):
    """Redondear a escalones: el error no pasa de medio escalón, y a veces no se nota."""

    def construct(self):
        self.titulo("Cuantizar: redondear a escalones")
        T = 6
        x = lambda t: wave(3 * np.asarray(t, float) + 3)
        s = np.linspace(0, T, 1201)
        a1 = ejes([0, T, 1], [-0.75, 0.75, 0.25], ancho=9.5, alto=2.8, numeros=False)
        a2 = ejes([0, T, 1], [-0.15, 0.15, 0.15], ancho=9.5, alto=1.3)
        apilar(a1, a2, 0.35).shift(RIGHT * 1.2 + DOWN * 0.1)
        l1 = texto("señal", 20, color=SENAL).next_to(a1, LEFT, buff=0.3)
        l2 = texto("error", 20, color=ERROR).next_to(a2, LEFT, buff=0.3)
        curva = a1.plot(lambda v: float(x(v)), x_range=[0, T, 0.02], color=SENAL, stroke_width=3)
        self.play(Create(a1), Create(a2), FadeIn(l1, l2), Create(curva))
        self.decir("Si solo hay ciertos valores, cada medida cae en el escalón más cercano.", espera=0.5)
        g1 = g2 = lect = None
        for q in (0.25, 0.1, 0.05):
            r = np.round(x(s) / q) * q
            e = r - x(s)
            h1 = linea(a1, s, r, MUESTRA, 3)
            h2 = linea(a2, s, np.clip(e, -0.15, 0.15), ERROR, 2)
            niveles = len(np.unique(r))
            lt = texto(f"escalón {q}    {niveles} niveles usados    error máximo {np.abs(e).max():.3f}", 24, color=MUESTRA)\
                .next_to(a1, UP, buff=0.1)
            if q == 0.25:
                assert np.abs(e).max() <= q / 2 + 1e-9
                banda = DashedVMobject(Line(a2.c2p(0, q / 2), a2.c2p(T, q / 2), color=WHITE), num_dashes=40)
                self.play(Create(h1), Create(h2), FadeIn(lt), run_time=1.5)
                g1, g2, lect = h1, h2, lt
                self.decir("El error nunca pasa de medio escalón.", espera=2.5)
            else:
                self.play(FadeOut(g1, g2, lect), FadeIn(h1, h2, lt), run_time=0.8)
                g1, g2, lect = h1, h2, lt
                self.wait(1.8)
        self.decir("Escalón más chico, error más chico. La resolución es el tamaño del escalón.", espera=2.5)
        self.play(FadeOut(a1, a2, l1, l2, curva, g1, g2, lect))

        # dos ejemplos del código
        barra = Rectangle(width=10, height=0.6, stroke_width=1).shift(UP * 1.5)
        izq = barra.get_left()
        franjas = VGroup(*[Rectangle(width=10 / 8, height=0.6, stroke_width=1, fill_opacity=0.7, fill_color=[BLUE_E, BLUE_C][i % 2])
                           .move_to(izq + RIGHT * (10 / 8 * (i + 0.5))) for i in range(8)])
        nums = VGroup(*[texto(str(i + 1), 22).move_to(f) for i, f in enumerate(franjas)])
        ratio = lambda u: min(8, max(1, 1 + math.floor(min(u, 0.9999) * 8)))
        for u, r in D["franjas"]:
            assert ratio(u) == r, (u, r)                      # igual que musica.js
        tit = texto("Música: la altura del lápiz, de 0 a 1, se vuelve un entero del 1 al 8", 24).next_to(barra, UP, buff=0.55)
        self.play(FadeIn(tit), FadeIn(franjas, nums))
        uu = ValueTracker(0.03)
        cursor = always_redraw(lambda: Triangle(color=MUESTRA, fill_opacity=1).scale(0.14).rotate(PI)
                               .move_to(izq + RIGHT * 10 * uu.get_value() + UP * 0.45))
        lect = lecturas([("u =", lambda: uu.get_value(), 2), ("da", lambda: ratio(uu.get_value()), 0)], 26, MUESTRA, horizontal=True, buff=1.0)\
            .next_to(barra, DOWN, buff=0.35)
        self.add(cursor, lect)
        self.play(uu.animate.set_value(0.97), run_time=4, rate_func=linear)
        self.decir("Ocho valores: aquí se pierde mucho, a propósito. Se oye como notas separadas.", espera=2)
        self.remove(cursor, lect)
        ancho, n = 1920, 65536
        assert all((norm_px(p, 0, ancho) * ancho) >> 16 == p for p in range(ancho))
        pix = VGroup(texto(f"Ratón: {ancho} píxeles van a 0..{n - 1}", 24),
                     texto(f"{n / ancho:.0f} escalones por píxel: al volver, los {ancho} píxeles caen en su sitio", 24, color=BIEN),
                     codigo("(norm(px) * tamaño) >> 16 == px", 24, color=MUESTRA))\
            .arrange(DOWN, buff=0.22).shift(DOWN * 1.35)
        self.play(FadeIn(pix))
        self.decir("Aquí no se pierde nada: el escalón es más chico que lo que se puede ver.", espera=3.5)


# ---------------------------------------------------------------------------------------------------------
class LecturasNuevas(Escena):
    """Pedir 200 muestras por segundo no da 200 lecturas distintas."""

    def construct(self):
        self.titulo("¿200 muestras son 200 medidas?")
        pide, renueva = 200, 115                              # por segundo; 115 es lo que se midió en el reloj
        rng = np.random.default_rng(3)
        t_mide = np.arange(0, 1.2, 1 / renueva)
        v_mide = np.cumsum(rng.normal(0, 0.6, len(t_mide)))
        v_mide += 1 - v_mide[t_mide <= 0.1].min()             # todo por encima de la línea de abajo
        t_pide = np.arange(0, 1.0, 1 / pide)
        cual = np.searchsorted(t_mide, t_pide + 1e-12, side="right") - 1
        leidas = v_mide[cual]
        por_segundo = len(np.unique(leidas)) / 1.0          # la cuenta de analyze_drawing.py
        ver = t_pide <= 0.1 + 1e-9
        ax = ejes([0, 100, 10], [0, float(v_mide[t_mide <= 0.1].max()) + 0.5, 1], ancho=10.5, alto=3.3, numeros=False)\
            .shift(DOWN * 0.45)
        ax.x_axis.add_numbers(font_size=18)
        et = texto("t (ms)", 18).next_to(ax.x_axis, DOWN, buff=0.35).align_to(ax, RIGHT)
        escalera = []
        for i in range(len(t_mide) - 1):
            if t_mide[i] > 0.1:
                break
            b = min(t_mide[i + 1], 0.1)
            escalera += [(t_mide[i] * 1000, v_mide[i]), (b * 1000, v_mide[i])]
        g = linea(ax, *zip(*escalera), SUAVE, 3)
        self.play(Create(ax), FadeIn(et))
        self.decir(f"Un modelo simple: por dentro el sensor renueva su valor unas {renueva} veces por segundo.", espera=0.3)
        self.play(Create(g), run_time=2)
        self.wait(1)
        self.decir(f"Se le pide uno cada {1000 / pide:.0f} ms. Si no cambió, devuelve lo mismo que antes.", espera=0.5)
        puntos = VGroup()
        self.add(puntos)
        cuenta = {"nuevas": 0, "rep": 0}
        lect = lecturas([("muestras:", lambda: cuenta["nuevas"] + cuenta["rep"], 0), ("lecturas nuevas:", lambda: cuenta["nuevas"], 0, MUESTRA),
                         ("repetidas:", lambda: cuenta["rep"], 0, ERROR)], 26, horizontal=True, buff=0.9).next_to(ax, UP, buff=0.2)
        self.add(lect)
        vistos = set()
        for t, v in zip(t_pide[ver], leidas[ver]):
            es_nueva = v not in vistos
            vistos.add(v)
            cuenta["nuevas" if es_nueva else "rep"] += 1
            puntos.add(Dot(ax.c2p(t * 1000, v), radius=0.1, color=MUESTRA if es_nueva else ERROR))
            lect.update(0)                                    # wait no corre los updaters
            self.wait(0.3)
        self.wait(1)
        self.decir("Una repetida no trae información: es la misma medida otra vez.", espera=2.5)
        total = VGroup(texto(f"En un segundo: {len(t_pide)} muestras", 28), texto(f"{por_segundo:.0f} lecturas nuevas", 28, color=MUESTRA))\
            .arrange(RIGHT, buff=0.7).next_to(ax, UP, buff=0.2)
        self.play(FadeOut(lect), FadeIn(total))
        self.decir("analyze_drawing.py las cuenta con np.unique: filas distintas entre los segundos grabados.", espera=3.5)


# ---------------------------------------------------------------------------------------------------------
class ResumirVentana(Escena):
    """Un tramo de muestras en pocos números, y qué le pasa a cada uno con un valor raro."""

    def construct(self):
        self.titulo("Resumir una ventana de muestras")
        rng = np.random.default_rng(12)
        v = np.round(3 + rng.normal(0, 0.45, 21), 2)
        n = len(v)
        ax = ejes([0, n + 1, 5], [0, 12, 2], ancho=7.6, alto=4.4, numeros=False).shift(LEFT * 2.5 + DOWN * 0.35)
        ax.y_axis.add_numbers(font_size=18)
        ancho = ax.x_length / (n + 1) * 0.72
        pos = {i: i + 1 for i in range(n)}
        extra = ValueTracker(float(v.max()))
        mayor = int(np.argmax(v))

        def valores():
            w = v.copy()
            w[mayor] = extra.get_value()
            return w

        def barra(i, k, color=SENAL):
            alto = ax.c2p(0, valores()[i])[1] - ax.c2p(0, 0)[1]
            return Rectangle(width=ancho, height=alto, stroke_width=0, fill_color=color, fill_opacity=0.85)\
                .move_to(ax.c2p(k, 0), aligned_edge=DOWN)

        barras = VGroup(*[barra(i, i + 1) for i in range(n)])
        self.play(Create(ax), LaggedStart(*[GrowFromEdge(b, DOWN) for b in barras], lag_ratio=0.04), run_time=1.5)
        self.decir("Veintiuna muestras seguidas son una ventana. ¿Con qué número te quedas?", espera=1)

        tabla = lecturas([("promedio", lambda: valores().mean(), 2, MUESTRA), ("mediana", lambda: statistics.median(valores()), 2, BIEN),
                          ("máximo", lambda: valores().max(), 2, ORANGE), ("pico a pico", lambda: valores().max() - valores().min(), 2, PURPLE_A)],
                         26, col=2.35, buff=0.3).move_to(RIGHT * 4.3 + UP * 0.6)
        l_prom = always_redraw(lambda: DashedLine(ax.c2p(0, valores().mean()), ax.c2p(n + 1, valores().mean()), color=MUESTRA, stroke_width=3))
        self.add(tabla)
        self.play(Create(l_prom))
        self.wait(1.5)
        # ordenarlas: la del medio es la mediana
        orden = np.argsort(v, kind="stable")
        self.decir("La mediana: se ordenan y se toma la del medio.", espera=0.2)
        self.play(*[barras[i].animate.move_to(ax.c2p(k + 1, 0), aligned_edge=DOWN) for k, i in enumerate(orden)], run_time=2)
        medio = int(orden[n // 2])
        assert v[medio] == statistics.median(v)
        self.play(barras[medio].animate.set_fill(BIEN))
        l_med = always_redraw(lambda: Line(ax.c2p(0, statistics.median(valores())), ax.c2p(n + 1, statistics.median(valores())), color=BIEN, stroke_width=3))
        self.play(Create(l_med))
        self.wait(1.5)
        # un valor raro
        self.decir("Ahora una sola muestra rara: un salto, un dato malo.", espera=0.2)
        raro = 11.5
        barras[mayor].add_updater(lambda b: b.become(barra(mayor, n)))
        self.play(extra.animate.set_value(raro), run_time=2.5)
        barras[mayor].clear_updaters()
        self.wait(1)
        w = valores()
        self.decir(f"El promedio subió {w.mean() - v.mean():.2f} y el máximo se fue. La mediana no se movió.", espera=3)
        self.decir("Cada uno engaña a su modo: el promedio y el máximo, con un solo valor raro.", espera=2.5)
        self.decir("La mediana, al revés: no ve un suceso corto. Por eso se miran varios juntos.", espera=3)
        self.decir("Motion._rest_window mira un segundo con pico a pico y mediana a la vez.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class Latencia(Escena):
    """Cuánto tarda cada muestra en llegar; un atasco deja una tanda de muestras viejas."""

    def construct(self):
        self.titulo("Latencia: de la medida a la laptop")
        rng = np.random.default_rng(21)
        paso = 50
        t_mide = np.arange(0, 1000, paso, dtype=float)
        lat = 30 + rng.gamma(2.0, 9.0, len(t_mide))
        atasco = (t_mide >= 450) & (t_mide <= 600)            # el Wi-Fi se traba y todo sale junto
        llegada = t_mide + lat
        llegada[atasco] = 1000 - 40 + 8 * np.arange(atasco.sum())
        lat = llegada - t_mide
        izq, der = -5.6, 5.8
        x_de = lambda t: izq + (der - izq) * t / 1100
        y_r, y_l = 1.45, -1.05
        reloj = Line([izq, y_r, 0], [der, y_r, 0], color=SUAVE)
        laptop = Line([izq, y_l, 0], [der, y_l, 0], color=SUAVE)
        l1 = texto("el reloj mide", 22).next_to(reloj, UP, buff=0.15).align_to(reloj, LEFT)
        l2 = texto("la laptop la usa", 22).next_to(laptop, DOWN, buff=0.15).align_to(laptop, LEFT)
        self.play(Create(reloj), Create(laptop), FadeIn(l1, l2))
        self.decir("Cada flecha es una muestra: sale cuando se mide y llega un rato después.", espera=0.5)

        # la cuenta de AirMouse.on_data: la línea de base baja de golpe y sube a lo sumo 30 ms por segundo
        base, ahora_prev, lags = None, None, []
        for a, t in sorted(zip(llegada, t_mide)):
            edad = a - t
            base = edad if base is None else min(edad, base + BASELINE_RISE_MS_PER_S * max(0.0, a - ahora_prev) / 1000)
            ahora_prev = a
            lags.append((t, edad - base))
        lag = dict(lags)
        tarde = [t for t in t_mide if lag[t] > STALE_MS]

        lect = texto("", 24)
        for k, t in enumerate(t_mide):
            if atasco[k]:
                continue
            f = Arrow([x_de(t), y_r, 0], [x_de(llegada[k]), y_l, 0], buff=0, color=SENAL, stroke_width=3, max_tip_length_to_length_ratio=0.06)
            self.remove(lect)
            lect = texto(f"esta tardó {lat[k]:.0f} ms", 24, color=SENAL).next_to(reloj, UP, buff=0.15).align_to(reloj, RIGHT)
            self.add(lect)
            self.play(Create(f), run_time=0.22)
        self.remove(lect)
        self.decir("Casi todas tardan parecido. Pero el Wi-Fi a veces se traba.", espera=0.5)
        for k, t in enumerate(t_mide):
            if atasco[k]:
                color = ERROR if t in tarde else ORANGE
                self.play(Create(Arrow([x_de(t), y_r, 0], [x_de(llegada[k]), y_l, 0], buff=0, color=color, stroke_width=3,
                                       max_tip_length_to_length_ratio=0.06)), run_time=0.4)
        peor = lat[atasco].max()
        self.decir(f"Salen juntas: la peor tardó {peor:.0f} ms. La latencia no es un número fijo.", espera=2.5)
        self.decir(f"AirMouse.on_data compara con la edad mínima reciente: {len(tarde)} pasan de {STALE_MS} ms de más.", espera=1.5)
        self.decir("Esas no mueven el cursor: una muestra vieja llega tarde para apuntar.", espera=3)
        self.decir("Bridge.report imprime el retraso: la edad de la muestra más nueva.", espera=3)


# ---------------------------------------------------------------------------------------------------------
class AlinearRelojes(Escena):
    """Ningún reloj es el de verdad: el desfase se saca de la entrega más rápida vista."""

    def construct(self):
        self.titulo("Dos relojes que cuentan distinto")
        map_time, reloj, K = cargar_map_time()
        rng = np.random.default_rng(5)
        n = 150
        desfase = 1_700_000_000.0                             # ms: inventado, y solo lo sabe esta animación
        t_med = 1000.0 + 10.0 * np.arange(n)
        lat = 14 + rng.gamma(1.6, 12.0, n)
        lat[:12] = np.linspace(145, 120, 12)                  # lo atrasado que había al arrancar
        lat[97] = 9.0                                         # la entrega más rápida
        puente = types.SimpleNamespace(last_ts_ms={}, offsets_ms={})
        llegada = t_med + desfase + lat
        visto = []
        for ts, a in zip(t_med, llegada):
            reloj.ahora_s = a / 1000
            map_time(puente, "GYROSCOPE", ts)
            visto.append(puente.offsets_ms["GYROSCOPE"])
        visto = np.array(visto)
        rel = lambda v: np.asarray(v) - desfase               # todo relativo al desfase de verdad

        e1 = VGroup(texto("llegada − medida  =", 30), texto("desfase", 30, color=BIEN), texto("+", 30), texto("latencia", 30, color=SENAL))\
            .arrange(RIGHT, buff=0.2).move_to(UP * 2.35)
        self.play(Write(e1))
        self.decir("El reloj cuenta desde que encendió; la laptop, desde 1970. La resta mezcla dos cosas.", espera=2)
        ax = ejes([0, n, 25], [0, 160, 40], ancho=9.8, alto=3.7).shift(RIGHT * 1.3 + DOWN * 0.65)
        l = texto("llegada − medida\n(ms, sobre el\ndesfase real)", 18).next_to(ax, LEFT, buff=0.3)
        et = texto("muestra", 18).next_to(ax.x_axis, DOWN, buff=0.32).align_to(ax, RIGHT)
        self.play(Create(ax), FadeIn(l, et))
        puntos = VGroup(*[Dot(ax.c2p(i, rel(llegada[i] - t_med[i])), radius=0.04, color=SENAL) for i in range(n)])
        escalera = [(0, rel(visto[0]))]
        for i in range(1, n):
            escalera += [(i, rel(visto[i - 1])), (i, rel(visto[i]))]
        g = linea(ax, *zip(*escalera), MUESTRA, 4)
        self.decir("La latencia nunca es negativa: todos los puntos quedan sobre el desfase.", espera=0.3)
        self.play(LaggedStart(*[FadeIn(p) for p in puntos], lag_ratio=0.02), Create(g), run_time=5, rate_func=linear)
        self.wait(0.5)
        base = DashedLine(ax.c2p(0, 0), ax.c2p(n, 0), color=BIEN, stroke_width=4)
        self.play(Create(base))
        falta = float(rel(visto[-1]))
        self.decir(f"Bridge.map_time guarda el mínimo. Queda {falta:.1f} ms sobre el desfase real (verde).", espera=3)
        self.decir("Esos ms no se ven nunca: la latencia se mide desde la entrega más rápida.", espera=3)
        self.decir(f"Anclar en la primera muestra habría dado {rel(llegada[0] - t_med[0]):.0f} ms de más.", espera=3)
        # un salto de horas no mueve el ancla
        antes = puente.offsets_ms["GYROSCOPE"]
        ultimo = t_med[-1]
        reloj.ahora_s = (ultimo + 10 + desfase + 30) / 1000
        map_time(puente, "GYROSCOPE", ultimo + 3 * 3600 * 1000)
        assert puente.offsets_ms["GYROSCOPE"] == antes
        self.decir(f"Una marca de 3 horas de más no lo mueve: un salto de más de {K['MAX_TS_JUMP_MS'] / 1000:.0f} s se ignora.", espera=3)
        fuga = K["OFFSET_LEAK_MS"] * 100 * 60
        self.decir(f"Y sube {K['OFFSET_LEAK_MS']} ms por muestra ({fuga:.1f} ms por minuto a 100 Hz) por si un reloj atrasa.", espera=3.5)


# ---------------------------------------------------------------------------------------------------------
class AgruparMuestras(Escena):
    """Un paquete por ida y vuelta: N muestras por paquete multiplican el caudal por N."""

    def construct(self):
        self.titulo("Un paquete por cada ida y vuelta")
        rtt, dt = 60, 10                                      # ms: Wi-Fi lento y 100 muestras por segundo
        f = 1000 / dt
        izq, der = -5.0, 5.9
        x_de = lambda t: izq + (der - izq) * t / 300
        filas = {}
        for y, N, color in ((1.95, 1, ERROR), (0.5, 6, BIEN)):
            guia = Line([izq, y - 0.35, 0], [der, y - 0.35, 0], color=SUAVE)
            medidas = VGroup(*[Dot([x_de(t), y + 0.48, 0], radius=0.04, color=MUESTRA) for t in range(0, 300, dt)])
            nombre = texto(f"N = {N}", 24, color=color).next_to(guia, LEFT, buff=0.25)
            filas[N] = (y, guia, medidas, nombre, color)
            self.play(Create(guia), FadeIn(medidas, nombre), run_time=0.6)
        self.decir(f"El reloj mide cada {dt} ms. La red deja pasar un paquete cada {rtt} ms.", espera=1.5)
        for N in (1, 6):
            y, guia, medidas, nombre, color = filas[N]
            cajas = VGroup()
            for k, t in enumerate(range(0, 300, rtt)):
                caja = Rectangle(width=x_de(rtt) - x_de(0) - 0.14, height=0.42, color=color, stroke_width=3)\
                    .move_to([x_de(t + rtt / 2), y, 0])
                adentro = VGroup(*[Dot(radius=0.05, color=MUESTRA) for _ in range(N)]).arrange(RIGHT, buff=0.1).move_to(caja)
                cajas.add(VGroup(caja, adentro))
            self.play(LaggedStart(*[FadeIn(c, shift=RIGHT * 0.3) for c in cajas], lag_ratio=0.3), run_time=2)
            pasa = min(N / (rtt / 1000), f)
            lect = texto(f"{N} muestra{'s' if N > 1 else ''} por paquete: pasan {pasa:.0f} por segundo", 24, color=color)\
                .next_to(guia, DOWN, buff=0.1).align_to(guia, LEFT)
            self.play(FadeIn(lect))
            self.wait(1.5)
        self.decir("Caudal = muestras por paquete / ida y vuelta. Hasta llegar a lo que el reloj mide.", espera=1.5)
        form = MathTex(r"\text{caudal} = \frac{N}{\text{ida y vuelta}}", font_size=30).move_to(LEFT * 4.7 + DOWN * 1.85)
        ax = ejes([0, 9, 1], [0, 120, 40], ancho=5.4, alto=1.75, numeros=True).move_to(RIGHT * 0.6 + DOWN * 1.85)
        Ns = np.arange(1, 9)
        caudal = np.minimum(Ns / (rtt / 1000), f)
        retraso = Ns * dt
        barras = VGroup(*[Rectangle(width=0.32, height=ax.c2p(0, c)[1] - ax.c2p(0, 0)[1], stroke_width=0, fill_color=BIEN, fill_opacity=0.85)
                          .move_to(ax.c2p(n, 0), aligned_edge=DOWN) for n, c in zip(Ns, caudal)])
        puntos = VGroup(*[Dot(ax.c2p(n, r), radius=0.06, color=ERROR) for n, r in zip(Ns, retraso)])
        ley = VGroup(texto("muestras/s", 18, color=BIEN), texto("retraso añadido, ms", 18, color=ERROR)).arrange(DOWN, aligned_edge=LEFT, buff=0.08)\
            .next_to(ax, RIGHT, buff=0.3)
        self.play(Write(form), Create(ax), FadeIn(ley))
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in barras], lag_ratio=0.1), run_time=1.5)
        self.play(LaggedStart(*[FadeIn(p, scale=2) for p in puntos], lag_ratio=0.1), run_time=1.5)
        self.decir(f"El precio: la primera del paquete espera a las otras, hasta N muestras: {6 * dt} ms con N = 6.", espera=3.5)
        self.decir("Es --batch de sdb_bridge.py: un awk en el reloj que junta N líneas antes de soltarlas.", espera=3.5)
