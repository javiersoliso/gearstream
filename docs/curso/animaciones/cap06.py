"""Animaciones del capítulo 6 (Del reloj al antebrazo: roll, yaw y pitch), una por concepto.

    python docs/curso/animaciones/render.py cap06            # todas, a GIF en docs/curso/media/cap06/
    python -m manim -ql docs/curso/animaciones/cap06.py Yaw    # una, rápido, para mirarla

Los movimientos son inventados. La cuenta es Wrist.rates de server/web/wrist.js: datos_cap06.js la corre con node sobre
600 casos, y este archivo comprueba antes de dibujar nada que su copia da lo mismo, y que también lo dan las versiones
en Python de verdad (Motion.feed_gyro de tools/air_mouse.py y frame_rates de tools/reconstruct_drawing.py), importadas
tal cual. Lo que las escenas afirman lo comprueba tools/test_antebrazo.js.
"""
import json
import os
import subprocess
import sys

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "..", "tools"))
import air_mouse                                # noqa: E402  la de verdad
from reconstruct_drawing import frame_rates     # noqa: E402  la de verdad

D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap06.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)
YAW, PITCH, ROLL = BLUE, GREEN, ORANGE          # los colores de los anillos del capítulo 5
CX, CY, CZ = RED, GREEN, BLUE                   # los ejes del reloj
GRADO = np.pi / 180
ARRIBA = np.array([0, 0, 1.0])


# ---------- la cuenta, igual que wrist.js ----------
def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot(v, k, a):
    k, v = unit(k), np.asarray(v, float)
    return v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * np.dot(k, v) * (1 - np.cos(a))


def forearm(mano):
    return np.array([-1.0, 0, 0]) if mano == "right" else np.array([1.0, 0, 0])


def rates(w, g, mano="left"):
    """Wrist.rates sin sesgo: devuelve yaw, pitch y roll."""
    w, g, f = np.asarray(w, float), unit(g), forearm(mano)
    roll, gpf = w @ f, g @ f
    yaw = (w @ g - roll * gpf) / max(1 - gpf * gpf, 0.09)
    c = np.cross(f, g)
    cn = np.linalg.norm(c)
    pitch = w @ c / cn if cn > 0.3 else 0.0
    if np.hypot(yaw, pitch) < 0.6:
        yaw = pitch = 0.0
    return yaw, pitch, roll


def _comprobar():
    """La copia y las dos versiones en Python contra Wrist.rates, en los 600 casos de datos_cap06.js."""
    cfg = {"left": air_mouse.build_parser().parse_args(["--forearm=+x"]), "right": air_mouse.build_parser().parse_args(["--forearm=-x"])}
    for c in D["casos"]:
        w, g, mano = np.array(c["w"]), np.array(c["g"]), c["mano"]
        assert np.allclose(rates(w, g, mano), (c["yaw"], c["pitch"], c["roll"]))
        gu = unit(g)
        if np.linalg.norm(np.cross(forearm(mano), gu)) <= 0.3 or np.hypot(c["yaw"], c["pitch"]) < 0.6:
            continue                            # ahí las versiones no hacen lo mismo: lo cuenta el capítulo
        m = air_mouse.Motion(cfg[mano])
        m.calibrated, m.ghat = True, tuple(gu)
        s = m.feed_gyro(1000.0, *w)
        assert np.allclose((s.yaw, s.pitch, s.roll), (c["yaw"], c["pitch"], c["roll"]))
        assert np.isclose(c["subida"], c["pitch"])
        if mano == "left":                      # frame_rates solo conoce el +x
            assert np.allclose(frame_rates(w[None], gu[None])[0], (c["yaw"], c["pitch"], c["roll"]))


_comprobar()


def brazo(e, psi=0.0, torn=0.0):
    """Un antebrazo en un mundo con z arriba: elevación e, dirección psi y atornillado torn, en grados. Da F y el dorso."""
    c, s, h = np.cos(e * GRADO), np.sin(e * GRADO), psi * GRADO
    F = np.array([c * np.cos(h), c * np.sin(h), s])
    d0 = np.array([-s * np.cos(h), -s * np.sin(h), c])
    return F, rot(d0, F, torn * GRADO)


def marco(F, d, mano="left", giro=0.0):
    """Los ejes del reloj como watchOf de mocapmath.js, como columnas; `giro`: el reloj mal puesto, girado sobre su z."""
    X = F if mano == "left" else -F
    M = np.column_stack([X, np.cross(d, X), d])
    if giro:
        c, s = np.cos(giro * GRADO), np.sin(giro * GRADO)
        M = M @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return M


def lectura(omega, F, d, mano="left", giro=0.0):
    """Lo que leen el giroscopio y la gravedad, en los ejes del reloj, para un ω del mundo."""
    M = marco(F, d, mano, giro)
    return M.T @ np.asarray(omega, float), M.T @ ARRIBA


# ---------- dibujo ----------
def texto(s, size=30, **kw):
    return Text(s, font_size=size, **kw)


def num(x, dec=0):
    x = round(float(x), dec) + 0.0                # sin "−0"
    return (f"{x:+.{dec}f}" if x else f"{0:.{dec}f}").replace("-", "−")


def terna(v, dec=2):
    return "(" + ", ".join(f"{round(float(x), dec) + 0.0:.{dec}f}".replace("-", "−") for x in v) + ")"


def flecha(a, b, color, w=6, op=1.0):
    return Arrow(np.asarray(a, float), np.asarray(b, float), buff=0, color=color, stroke_width=w, stroke_opacity=op,
                 max_tip_length_to_length_ratio=0.15).set_fill(opacity=op)


def relojito(M, centro, lado=0.72):
    """Una caja aplastada: la cara azul es la pantalla (+z), la roja mira a +x y la verde a +y."""
    c = Cube(side_length=1, fill_opacity=0.95, fill_color=GREY_D, stroke_width=1, stroke_color=GREY_B)
    c[1].set_fill(BLUE_D)
    c[3].set_fill(RED_D)
    c[4].set_fill(GREEN_D)
    c.stretch(0.32, 2, about_point=ORIGIN).scale(lado, about_point=ORIGIN)
    c.apply_matrix(M, about_point=ORIGIN)
    return c.shift(centro)


def dibujo_brazo(F, d, codo=ORIGIN, mano="left", largo=3.0, giro=0.0):
    codo = np.asarray(codo, float)
    punta = codo + largo * F
    return VGroup(Line(codo, punta, color=GREY_B, stroke_width=15), Dot(codo, radius=0.15, color=GREY_A), Dot(punta, radius=0.19, color=GREY_A),
                  relojito(marco(F, d, mano, giro), codo + 0.68 * largo * F + 0.16 * d))


def ejes_reloj(M, centro, largo=1.25, w=5):
    return VGroup(*[flecha(centro, centro + largo * M[:, i], c, w) for i, c in enumerate([CX, CY, CZ])])


def barras(valores, tope=130.0, ancho=2.4):
    """Las tres tasas en °/s: una barra por giro, con su valor."""
    g = VGroup()
    for i, (n, v, c) in enumerate(zip(("yaw", "pitch", "roll"), valores, (YAW, PITCH, ROLL))):
        y = -0.5 * i
        g.add(texto(n, 22, color=c).move_to([-2.05, y, 0]))
        g.add(Line([0, y - 0.19, 0], [0, y + 0.19, 0], color=GREY_B, stroke_width=2))
        largo = float(np.clip(v / tope, -1, 1)) * ancho / 2
        if abs(largo) > 0.01:
            g.add(Rectangle(width=abs(largo), height=0.27, fill_color=c, fill_opacity=0.9, stroke_width=0).move_to([largo / 2, y, 0]))
        g.add(texto(f"{num(v)} °/s", 20).move_to([2.15, y, 0]))
    return g


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


class Escena2D(Scene):
    def decir(self, s, color=WHITE, size=24):
        nuevo = texto(s, size, color=color)
        if nuevo.width > 13.4:
            nuevo.scale_to_fit_width(13.4)
        nuevo.to_edge(DOWN, buff=0.3)
        viejo = getattr(self, "_rotulo", None)
        self.play(*([FadeOut(viejo)] if viejo else []), FadeIn(nuevo), run_time=0.6)
        self._rotulo = nuevo


def en_esquina(m):
    return m.to_corner(UR).shift(DOWN * 0.85 + LEFT * 0.1)


# ---------------------------------------------------------------------------------------------------------
class AntebrazoEsEjeX(Escena3D):
    """En la muñeca izquierda el antebrazo es +x; en la derecha, con el reloj puesto igual, es −x."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-90 * DEGREES, zoom=0.92)
        self.titulo("El antebrazo es un eje del reloj")
        ca, cb = np.array([-5.2, 0, 0.7]), np.array([1.0, 0, 0.7])
        e = ValueTracker(0)
        mal = ValueTracker(0)
        L = 2.6

        def lado(codo, mano, giro=0.0):
            F, d = brazo(e.get_value())
            p = codo + 0.68 * L * F + 0.16 * d
            return VGroup(dibujo_brazo(F, d, codo, mano, L, giro), ejes_reloj(marco(F, d, mano, giro), p + 0.1 * d, 1.0),
                          flecha(codo + L * F, codo + (L + 0.7) * F, YELLOW, 7))

        A = always_redraw(lambda: lado(ca, "left", mal.get_value()))
        B = always_redraw(lambda: lado(cb, "right"))
        self.add(A, B)
        ta = texto("muñeca izquierda", 26).move_to(LEFT * 3.5 + UP * 2.75)
        tb = texto("muñeca derecha", 26).move_to(RIGHT * 3.2 + UP * 2.75)
        leyenda = VGroup(texto("x", 24, color=CX), texto("y", 24, color=CY), texto("z", 24, color=CZ), texto("f: del codo a la mano", 24, color=YELLOW))\
            .arrange(RIGHT, buff=0.35).next_to(VGroup(ta, tb), DOWN, buff=0.15)
        self.add_fixed_in_frame_mobjects(ta, tb, leyenda)
        self.play(FadeIn(ta, tb, leyenda))
        self.decir("En la izquierda, el x del reloj va del codo a la mano: f = +x.", CX)
        self.wait(2.5)
        self.decir("En la derecha, con el reloj puesto igual, x apunta al codo: f = −x.", CX)
        self.wait(2.5)

        def gravedad():
            F, d = brazo(e.get_value())
            ga, gb = lectura(ARRIBA, F, d, "left")[1] * 9.81, lectura(ARRIBA, F, d, "right")[1] * 9.81
            return VGroup(texto(f"gravedad en x: {num(ga[0], 2)}", 24).move_to(LEFT * 3.5 + DOWN * 2.45),
                          texto(f"gravedad en x: {num(gb[0], 2)}", 24).move_to(RIGHT * 3.2 + DOWN * 2.45))

        lect = self.fijo(gravedad)
        self.decir("Con el brazo colgando, f apunta abajo y la gravedad queda sobre el eje x.")
        self.play(e.animate.set_value(-90), run_time=3)
        self.decir("Por eso --calibrate forearm deja el brazo colgando y mira el signo.", YELLOW)
        self.wait(2.5)
        self.play(e.animate.set_value(0), run_time=2)
        lect.clear_updaters()
        self.remove(lect)
        self.play(mal.animate.set_value(10), run_time=2)
        F, d = brazo(0)
        fv = np.array([np.cos(10 * GRADO), -np.sin(10 * GRADO), 0])        # el antebrazo, leído en un reloj girado 10°
        y, p, r = rates(100 * fv, lectura(ARRIBA, F, d, "left", 10)[1])
        nota = texto(f"100 °/s de atornillar dejan {np.hypot(y, p):.1f} °/s fuera del roll", 24, color=RED).move_to(LEFT * 3.0 + DOWN * 2.45)
        self.add_fixed_in_frame_mobjects(nota)
        self.decir("Si el reloj queda girado 10°, x ya no es el antebrazo.", RED)
        self.play(FadeIn(nota))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Roll(Escena3D):
    """La parte del giro alrededor del antebrazo: roll = ω·f."""

    def construct(self):
        self.set_camera_orientation(phi=70 * DEGREES, theta=-78 * DEGREES, zoom=0.95)
        self.titulo("Roll: atornillar")
        codo = np.array([-2.3, 0, -0.4])
        e, t = ValueTracker(15), ValueTracker(0)
        F = lambda: brazo(e.get_value())[0]
        d = lambda: brazo(e.get_value(), 0, t.get_value())[1]
        omega = {"fn": lambda: 100 * F()}
        self.add(always_redraw(lambda: dibujo_brazo(F(), d(), codo)))
        fw = always_redraw(lambda: flecha(codo + 3.0 * F(), codo + 4.5 * F(), ROLL, 8))
        self.add(fw)
        self.fijo(lambda: en_esquina(barras(rates(*lectura(omega["fn"](), F(), d())))))
        self.fijo(lambda: texto(f"elevación {num(e.get_value())}°", 24).to_corner(UL).shift(DOWN * 0.85))
        f = MathTex(r"\text{roll} = \omega\cdot f", font_size=40, color=ROLL).to_corner(UL).shift(DOWN * 1.4)
        self.add_fixed_in_frame_mobjects(f)
        self.play(Write(f))
        self.decir("Atornillar: ω va a lo largo del antebrazo.", ROLL)
        self.play(t.animate.set_value(100 * 2.5), run_time=2.5, rate_func=linear)
        self.decir("Positivo: horario visto desde el codo, como apretar un tornillo.", ROLL)
        self.play(t.animate.set_value(100 * 5), run_time=2.5, rate_func=linear)
        self.decir("A cualquier elevación es lo mismo: f está pegado al reloj.")
        self.play(t.animate.set_value(100 * 8), e.animate.set_value(-35), run_time=3, rate_func=linear)
        self.play(t.animate.set_value(100 * 11), e.animate.set_value(30), run_time=3, rate_func=linear)
        self.remove(fw)
        self.decir("Si ω apunta a otro lado, el roll es su sombra sobre f.", YELLOW)
        om = rot(F(), [0.2, 1, 0.3], 50 * GRADO) * 100
        base = codo + 0.9 * F() + 0.95 * brazo(e.get_value())[1]
        sombra = (om @ F()) * F() / 100 * 2.0
        fo = flecha(base, base + om / 100 * 2.0, YELLOW, 7)
        fs = Line(base, base + sombra, color=ROLL, stroke_width=11)
        caida = DashedLine(base + om / 100 * 2.0, base + sombra, color=GREY_B)
        omega["fn"] = lambda: om
        self.play(GrowArrow(fo))
        self.play(Create(caida), Create(fs))
        n = texto(f"ω·f = {num(om @ F())} °/s de los {np.linalg.norm(om):.0f} °/s de ω", 24, color=ROLL).to_edge(DOWN, buff=1.0)
        self.add_fixed_in_frame_mobjects(n)
        self.play(FadeIn(n))
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Pitch(Escena3D):
    """El giro alrededor del eje horizontal perpendicular al antebrazo: pitch = ω·(f × g)/|f × g|."""

    def construct(self):
        self.set_camera_orientation(phi=72 * DEGREES, theta=-62 * DEGREES, zoom=0.95)
        self.titulo("Pitch: subir y bajar")
        codo = np.array([-0.9, 0, -0.9])
        e = ValueTracker(0)
        tasa = {"w": 0.0}
        F = lambda: brazo(e.get_value())[0]
        d = lambda: brazo(e.get_value())[1]
        c = lambda: np.cross(F(), ARRIBA)
        self.add(always_redraw(lambda: dibujo_brazo(F(), d(), codo)))
        fg = flecha(codo, codo + 2.3 * ARRIBA, YAW, 7)
        ff = always_redraw(lambda: flecha(codo + 3.0 * F(), codo + 3.9 * F(), ROLL, 7))
        fc = always_redraw(lambda: flecha(codo, codo + 2.3 * c(), WHITE, 3) if np.linalg.norm(c()) > 0.05 else VectorizedPoint())
        fp = always_redraw(lambda: flecha(codo, codo + 2.3 * unit(c()), PITCH, 8))
        self.add(fg, ff)
        ley = VGroup(texto("f: antebrazo", 22, color=ROLL), texto("g: arriba", 22, color=YAW), texto("p: de costado", 22, color=PITCH))\
            .arrange(DOWN, aligned_edge=LEFT, buff=0.1).to_corner(UL).shift(DOWN * 0.85)
        self.add_fixed_in_frame_mobjects(ley)
        self.play(FadeIn(ley))
        self.add(fp, fc)

        def bars():
            om = tasa["w"] * unit(c())
            return en_esquina(barras(rates(*lectura(om, F(), d()))))

        self.fijo(bars)
        f = MathTex(r"p = \frac{f\times g}{|f\times g|}", r"\qquad \text{pitch} = \omega\cdot p", font_size=34, color=PITCH)\
            .to_edge(DOWN, buff=1.0)
        self.add_fixed_in_frame_mobjects(f)
        self.play(Write(f))
        self.decir("f × g forma ángulo recto con los dos: es horizontal, de costado.")
        self.wait(2)
        self.decir("Girar alrededor de él sube y baja la mano. Positivo: sube.", PITCH)
        tasa["w"] = 40.0
        self.play(e.animate.set_value(45), run_time=45 / 40, rate_func=linear)
        tasa["w"] = -40.0
        self.play(e.animate.set_value(-30), run_time=75 / 40, rate_func=linear)
        tasa["w"] = 40.0
        self.play(e.animate.set_value(55), run_time=85 / 40, rate_func=linear)
        tasa["w"] = 0.0
        self.fijo(lambda: texto(f"elevación {num(e.get_value())}°    |f × g| = {np.linalg.norm(c()):.2f}", 24).next_to(ley, DOWN, buff=0.2).align_to(ley, LEFT))
        self.decir("f × g se acorta al levantar el brazo (blanca): hay que dividir por su largo.")
        self.wait(2.5)
        self.play(e.animate.set_value(71), run_time=2)
        self.decir("Con el antebrazo casi vertical, f × g casi no existe: wrist.js corta en 0.3.", RED)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Yaw(Escena3D):
    """El giro alrededor de la vertical. El reloj sabe dónde es arriba, y ω·g no alcanza: se lleva parte del roll."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-70 * DEGREES, zoom=0.95)
        self.titulo("Yaw: izquierda y derecha")
        codo = np.array([-0.9, 0, -1.2])
        e, psi, torn = ValueTracker(30), ValueTracker(0), ValueTracker(0)
        om = {"w": np.zeros(3), "fn": lambda: np.zeros(3)}
        F = lambda: brazo(e.get_value(), psi.get_value())[0]
        d = lambda: brazo(e.get_value(), psi.get_value(), torn.get_value())[1]
        self.add(always_redraw(lambda: dibujo_brazo(F(), d(), codo)))
        fg = flecha(codo, codo + 3.0 * ARRIBA, YAW, 8)
        self.add(fg)
        lec = self.fijo(lambda: VGroup(texto("arriba, leído en el reloj:", 22), texto(f"g = {terna(lectura(ARRIBA, F(), d())[1])}", 24, color=YAW))
                        .arrange(DOWN, aligned_edge=LEFT, buff=0.1).to_corner(UL).shift(DOWN * 0.85))
        self.decir("El reloj sí sabe dónde es la vertical: es la gravedad, en sus propios ejes.", YAW)
        self.play(torn.animate.set_value(60), run_time=1.5)
        self.play(torn.animate.set_value(-40), run_time=1.5)
        self.play(torn.animate.set_value(0), run_time=1)
        self.wait(0.5)
        self.fijo(lambda: en_esquina(barras(rates(*lectura(om["fn"](), F(), d())))))
        om["fn"] = lambda: 60 * ARRIBA
        self.decir("Girar alrededor de la vertical: yaw. Positivo: hacia la izquierda.", YAW)
        self.play(psi.animate.set_value(90), run_time=1.5, rate_func=linear)
        self.play(psi.animate.set_value(180), run_time=1.5, rate_func=linear)
        n1 = texto(f"inclinado {e.get_value():.0f}°, el roll marca a·(g·f) = {60 * np.sin(30 * GRADO):.0f}", 22, color=ROLL)
        en_esquina(n1).shift(DOWN * 1.5)
        self.add_fixed_in_frame_mobjects(n1)
        self.decir("Con el antebrazo inclinado, el mismo giro también atornilla un poco.", ROLL)
        self.play(FadeIn(n1), psi.animate.set_value(270), run_time=1.5, rate_func=linear)
        self.play(psi.animate.set_value(360), run_time=1.5, rate_func=linear)
        om["fn"] = lambda: np.zeros(3)
        self.play(FadeOut(n1), run_time=0.3)
        psi.set_value(0)
        self.wait(0.5)

        # ω·g sola: atornillar también la mueve
        om["fn"] = lambda: 100 * F()
        self.decir("¿Alcanza con ω·g? Si atornillo, ω va por f, y f tiene algo de vertical.", RED)
        ingenuo = VGroup(texto(f"ω·g = {100 * np.sin(30 * GRADO):.0f} °/s", 26, color=RED), texto("el yaw de verdad:", 22), texto("(ω·g − roll·(g·f)) / (1 − (g·f)²) = 0", 22, color=YAW))\
            .arrange(DOWN, aligned_edge=LEFT, buff=0.12)
        ingenuo.to_edge(LEFT).shift(DOWN * 0.4)
        self.add_fixed_in_frame_mobjects(ingenuo)
        self.play(FadeIn(ingenuo), torn.animate.set_value(100 * 1.5), run_time=1.5, rate_func=linear)
        self.play(torn.animate.set_value(100 * 4), run_time=2.5, rate_func=linear)
        self.decir("Hay que quitarle lo que ya es roll: eso hace la fórmula.", YAW)
        self.play(torn.animate.set_value(100 * 7), run_time=3, rate_func=linear)
        self.wait(1.5)


# ---------------------------------------------------------------------------------------------------------
class BaseTorcida(Escena2D):
    """g y f no forman ángulo recto: el yaw es un coeficiente en una base torcida, no una sombra."""

    def construct(self):
        titulo = texto("Tres ejes que no son perpendiculares", 32).to_edge(UP)
        self.play(Write(titulo))
        S = 1.55
        O = LEFT * 4.6 + DOWN * 1.9
        a, b = 1.1, 0.8                                    # yaw y lo que hay a lo largo de f, en centenas de °/s
        e = ValueTracker(35)
        gv = np.array([0, 1.0, 0])
        fv = lambda: np.array([np.cos(e.get_value() * GRADO), np.sin(e.get_value() * GRADO), 0])
        w = lambda: a * gv + b * fv()
        P = lambda v: O + S * v
        s = lambda: gv @ fv()
        guia = Line(O + LEFT * 0.4, O + RIGHT * 4.6, stroke_opacity=0.3)
        self.add(guia)
        fg = flecha(O, P(gv), YAW, 7)
        ff = always_redraw(lambda: flecha(O, P(fv()), ROLL, 7))
        lg = texto("g", 26, color=YAW).next_to(P(gv), LEFT, buff=0.15)
        lf = always_redraw(lambda: texto("f", 26, color=ROLL).move_to(P(fv()) + 0.28 * DOWN + 0.1 * RIGHT))
        pun = VGroup(Circle(radius=0.13, color=PITCH, stroke_width=4), Dot(radius=0.05, color=PITCH)).move_to(O)
        lp = texto("p sale de la pantalla", 20, color=PITCH).next_to(O, DOWN, buff=0.25).shift(RIGHT * 0.7)
        self.play(GrowArrow(fg), FadeIn(ff, lg, lf, pun, lp))
        self.decir("p forma ángulo recto con los dos. Queda ver el plano de f y g.")
        self.wait(1.5)
        fw = always_redraw(lambda: flecha(O, P(w()), YELLOW, 7))
        tramos = always_redraw(lambda: VGroup(Line(O, P(a * gv), color=YAW, stroke_width=11), Line(P(a * gv), P(w()), color=ROLL, stroke_width=11)))
        self.add(tramos, fw)
        self.decir("ω = a g + b f: caminar paralelo a cada eje da los coeficientes.", YELLOW)

        def panel():
            om = w() * 100
            f3 = np.array([1.0, 0, 0])
            ang = e.get_value() * GRADO
            g3 = np.array([np.sin(ang), 0, np.cos(ang)])                     # la misma geometría, en los ejes del reloj
            wr = (a * g3 + b * f3) * 100
            y, _, r = rates(wr, g3)
            return VGroup(texto(f"elevación {e.get_value():.0f}°    g·f = {s():.2f}", 24),
                          texto(f"a = {a * 100:.0f} °/s    b = {b * 100:.0f} °/s", 24, color=YELLOW),
                          texto(f"ω·g = {om @ gv:.0f}   (sombra sobre g)", 24, color=RED),
                          texto(f"ω·f = {r:.0f}   (el roll: b + a (g·f))", 24, color=ROLL),
                          texto(f"yaw de rates = {y:.0f}", 24, color=YAW))\
                .arrange(DOWN, aligned_edge=LEFT, buff=0.15).move_to(RIGHT * 0.9 + UP * 1.55, aligned_edge=LEFT)

        self.add(always_redraw(panel))
        sombra = always_redraw(lambda: DashedLine(P(w()), P((w() @ gv) * gv), color=RED))
        s2 = always_redraw(lambda: Line(O + 0.09 * LEFT, P((w() @ gv) * gv) + 0.09 * LEFT, color=RED, stroke_width=7))
        self.play(FadeIn(sombra, s2))
        self.decir("La sombra sobre g es más larga que a: se lleva parte de b.", RED)
        self.wait(2.5)
        f = MathTex(r"\omega\cdot g &= a + b\,s\\ \omega\cdot f &= a\,s + b\\ a &= \frac{\omega\cdot g - (\omega\cdot f)\,s}{1-s^2}", font_size=32)\
            .move_to(RIGHT * 3.3 + DOWN * 1.15)
        self.play(Write(f))
        self.decir("Con s = g·f, dos ecuaciones: el sistema del capítulo 2. Sale a, el yaw.", YAW)
        self.wait(2.5)
        self.play(e.animate.set_value(60), run_time=3)
        self.decir("Cambia la elevación: cambian las sombras, pero rates sigue dando a.", YAW)
        self.wait(1)
        self.play(e.animate.set_value(0), run_time=3.5)
        self.decir("Solo con el antebrazo horizontal son perpendiculares: ahí la sombra sirve.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class CasiVertical(Escena2D):
    """Por qué se divide por 1 − (g·f)², y qué pasa cuando el antebrazo apunta casi al piso."""

    def construct(self):
        titulo = texto("Cuando el antebrazo se acerca a la vertical", 32).to_edge(UP)
        self.play(Write(titulo))
        O = LEFT * 5.3 + DOWN * 1.7
        S = 1.55
        e = ValueTracker(0.0)
        gv = np.array([0, 1.0, 0])
        fv = lambda: np.array([np.cos(e.get_value() * GRADO), np.sin(e.get_value() * GRADO), 0])
        P = lambda v: O + S * v
        area = always_redraw(lambda: Polygon(O, P(fv()), P(fv() + gv), P(gv), color=TEAL, fill_opacity=0.35, stroke_width=2))
        fg = flecha(O, P(gv), YAW, 7)
        ff = always_redraw(lambda: flecha(O, P(fv()), ROLL, 7))
        es = np.arange(0, 89.01, 0.5)
        c = np.cos(es * GRADO)
        a1 = Axes(x_range=[0, 90, 15], y_range=[0, 1, 0.25], x_length=6.2, y_length=1.9, tips=False,
                  axis_config={"font_size": 18}, y_axis_config={"include_numbers": True, "font_size": 18}).move_to(RIGHT * 2.9 + UP * 1.3)
        a2 = Axes(x_range=[0, 90, 15], y_range=[0, 8, 2], x_length=6.2, y_length=1.9, tips=False,
                  axis_config={"font_size": 18, "include_numbers": True}).move_to(RIGHT * 2.9 + DOWN * 1.35)
        l1 = texto("1 − (g·f)²", 20, color=TEAL).next_to(a1, UP, buff=0.08)
        l2 = texto("cuánto se agranda un ruido en el yaw", 20).next_to(a2, UP, buff=0.08)
        lx = texto("elevación del antebrazo (°)", 18).next_to(a2, DOWN, buff=0.12)
        self.add(area, fg, ff)
        self.play(Create(a1), Create(a2), FadeIn(l1, l2, lx))
        c1 = a1.plot_line_graph(es, c ** 2, add_vertex_dots=False, line_color=TEAL, stroke_width=4)
        self.play(Create(c1), run_time=1.5)
        m1 = always_redraw(lambda: Dot(a1.c2p(e.get_value(), np.cos(e.get_value() * GRADO) ** 2), color=WHITE, radius=0.07))
        self.add(m1)
        lect = always_redraw(lambda: VGroup(texto(f"elevación {e.get_value():.1f}°", 22), texto(f"g·f = {np.sin(e.get_value() * GRADO):.3f}", 22),
                                            texto(f"área² = {np.cos(e.get_value() * GRADO) ** 2:.3f}", 22, color=TEAL))
                             .arrange(DOWN, aligned_edge=LEFT, buff=0.1).to_corner(UL).shift(DOWN * 0.8))
        self.add(lect)
        self.decir("1 − (g·f)² es |f × g|²: el área al cuadrado del paralelogramo de f y g.", TEAL)
        self.play(e.animate.set_value(45), run_time=3)
        self.decir("Al levantar el brazo, f y g se acercan y el área se achica.", TEAL)
        self.play(e.animate.set_value(70), run_time=2.5)
        lim = np.degrees(np.arccos(0.3))
        self.decir("Con el antebrazo vertical la base se aplasta y habría que dividir por cero.", RED)
        self.play(e.animate.set_value(88), run_time=2.5)
        self.wait(1)
        sin_min = 1 / c
        con_min = c / np.maximum(c ** 2, 0.09)
        vis = sin_min <= 8
        c2 = a2.plot_line_graph(es[vis], sin_min[vis], add_vertex_dots=False, line_color=RED, stroke_width=4)
        self.decir("Un ruido en ω se agranda 1/cos(elevación): sin freno, crece sin límite.", RED)
        self.play(Create(c2), run_time=2)
        self.wait(1)
        piso = DashedLine(a1.c2p(0, 0.09), a1.c2p(90, 0.09), color=YELLOW)
        vert = VGroup(DashedLine(a1.c2p(lim, 0), a1.c2p(lim, 1), color=YELLOW, stroke_opacity=0.7),
                      DashedLine(a2.c2p(lim, 0), a2.c2p(lim, 8), color=YELLOW, stroke_opacity=0.7))
        c3 = a2.plot_line_graph(es, con_min, add_vertex_dots=False, line_color=GREEN, stroke_width=5)
        self.decir(f"El código divide por no menos de 0.09: a {lim:.1f}° de elevación, {90 - lim:.1f}° de la vertical.", YELLOW)
        self.play(Create(piso), Create(vert))
        self.play(Create(c3), run_time=2)
        self.wait(1)
        self.decir(f"Con eso el ruido se agranda {con_min.max():.1f} veces como mucho, y el yaw se apaga.", GREEN)
        self.play(e.animate.set_value(lim), run_time=2)
        self.wait(1.5)
        self.decir("Ahí el pitch se apaga también: es la singularidad del capítulo 5.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class AtornillarNoMueveElCursor(Escena3D):
    """Un roll puro no tiene nada de yaw ni de pitch, a cualquier inclinación."""

    def construct(self):
        self.set_camera_orientation(phi=70 * DEGREES, theta=-78 * DEGREES, zoom=0.92)
        self.titulo("Atornillar no mueve el cursor")
        codo = np.array([-4.0, 0, -0.5])
        T = 12.0
        ts = np.linspace(0, T, 721)
        elev = 60 * np.sin(2 * np.pi * ts / T)
        b = 100.0
        dt = ts[1] - ts[0]
        naive = np.cumsum(b * np.sin(elev * GRADO)) * dt            # lo que se juntaría usando ω·g como yaw
        tt = ValueTracker(0)
        i = lambda: min(len(ts) - 1, int(tt.get_value() / dt))
        F = lambda: brazo(elev[i()])[0]
        d = lambda: brazo(elev[i()], 0, b * ts[i()])[1]
        self.add(always_redraw(lambda: dibujo_brazo(F(), d(), codo)))
        fw = always_redraw(lambda: flecha(codo + 3.0 * F(), codo + 4.1 * F(), ROLL, 8))
        self.add(fw)
        self.fijo(lambda: en_esquina(barras(rates(*lectura(b * F(), F(), d())))))
        pantalla = Rectangle(width=4.6, height=1.5, color=GREY_B, stroke_width=3).move_to(RIGHT * 4.4 + DOWN * 0.55)
        lp = texto("el cursor", 20).next_to(pantalla, UP, buff=0.08)
        self.add_fixed_in_frame_mobjects(pantalla, lp)
        escala = 2.1 / np.abs(naive).max()

        def cursores():
            c = pantalla.get_center()
            return VGroup(Dot(c + UP * 0.32, color=GREEN, radius=0.11), Dot(c + DOWN * 0.32 + LEFT * (naive[i()] * escala), color=RED, radius=0.11),
                          texto("yaw y pitch de rates", 18, color=GREEN).move_to(c + UP * 0.58), texto("usando ω·g", 18, color=RED).move_to(c + DOWN * 0.6))

        self.fijo(cursores)
        self.fijo(lambda: VGroup(texto(f"elevación {num(elev[i()])}°", 24), texto(f"g·f = {num(np.sin(elev[i()] * GRADO), 2)}", 24),
                                 texto(f"ω·g = {num(b * np.sin(elev[i()] * GRADO))} °/s", 24, color=RED))
                  .arrange(DOWN, aligned_edge=LEFT, buff=0.1).to_corner(UL).shift(DOWN * 0.85))
        self.decir("100 °/s de atornillar mientras el antebrazo sube y baja.", ROLL)
        self.play(tt.animate.set_value(T / 4), run_time=3, rate_func=linear)
        self.decir("Yaw y pitch siguen en cero: atornillar no tiene nada de ellos.", GREEN)
        self.play(tt.animate.set_value(T / 2), run_time=3, rate_func=linear)
        self.decir("ω·g sin corregir sí se mueve, y arrastraría el cursor.", RED)
        self.play(tt.animate.set_value(3 * T / 4), run_time=3, rate_func=linear)
        self.decir("p forma ángulo recto con f, y al yaw se le quitó justo la parte de f.")
        self.play(tt.animate.set_value(T), run_time=3, rate_func=linear)
        self.decir("Por construcción: no depende de la elevación, ni de que g sea exacta.", GREEN)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class ManoEquivocada(Escena2D):
    """Con f al revés, pitch y roll cambian de signo y el yaw no: arriba sale abajo."""

    def construct(self):
        titulo = texto("En la muñeca derecha, si no aviso", 32).to_edge(UP)
        self.play(Write(titulo))
        # la mano dibuja una F en el aire: elevación e y dirección psi, en grados; x de pantalla = −psi
        puntos = np.array([(-12, -14), (-12, 14), (10, 14), (-12, 14), (-12, 1), (6, 1)], float)     # (x, y) en grados
        hz = 100
        vel = 30.0                                                    # grados por segundo
        camino = [puntos[0]]
        for p, q in zip(puntos, puntos[1:]):
            n = int(round(np.linalg.norm(q - p) / vel * hz))
            camino += [p + (q - p) * (k + 1) / n for k in range(n)]
        camino = np.array(camino)
        dt = 1 / hz
        bien = [camino[0].copy()]
        mal = [camino[0] * [1, -1]]                                   # arranca arriba, para que la F al revés quepa en su cuadro
        for p, q in zip(camino, camino[1:]):
            e, psi = p[1], -p[0]
            F, d = brazo(e, psi)
            lado = unit(np.cross(F, ARRIBA))
            om = (-(q[0] - p[0]) / dt) * ARRIBA + ((q[1] - p[1]) / dt) * lado          # ψ̇ alrededor de g, ė alrededor de p
            w, g = lectura(om, F, d, "right")
            for tray, mano in ((bien, "right"), (mal, "left")):
                y, pi, _ = rates(w, g, mano)
                tray.append(tray[-1] + np.array([-y, pi]) * dt)
        bien, mal = np.array(bien), np.array(mal)
        assert np.abs(bien - camino).max() < 1e-6
        F0, d0 = brazo(0)
        w0, g0 = lectura(100 * F0, F0, d0, "right")
        r_bien, r_mal = rates(w0, g0, "right")[2], rates(w0, g0, "left")[2]

        tt = ValueTracker(0)
        n = len(camino)
        centros = [LEFT * 4.5 + UP * 0.2, UP * 0.2, RIGHT * 4.5 + UP * 0.2]
        nombres = [("lo que hace la mano", WHITE), ("con f = −x (avisé)", GREEN), ("con f = +x (no avisé)", RED)]
        ES = 0.1
        cuadros = VGroup(*[Rectangle(width=3.9, height=3.2, color=GREY_B, stroke_width=3).move_to(c) for c in centros])
        rot_ = VGroup(*[texto(s, 24, color=c).next_to(q, UP, buff=0.12) for (s, c), q in zip(nombres, cuadros)])
        self.play(Create(cuadros), FadeIn(rot_))

        def trazo(arr, c0, color):
            def hacer():
                k = max(2, int(tt.get_value() * (n - 1)))
                pts = [c0 + ES * np.array([x, y, 0]) for x, y in arr[:k:4]]
                return VGroup(VMobject(color=color, stroke_width=5).set_points_as_corners(pts + [pts[-1]]),
                              Dot(c0 + ES * np.array([*arr[k - 1], 0]), color=color, radius=0.08))
            return always_redraw(hacer)

        self.add(trazo(camino, centros[0], WHITE), trazo(bien, centros[1], GREEN), trazo(mal, centros[2], RED))
        self.decir("Reloj en la derecha: la mano dibuja una F en el aire.")
        self.play(tt.animate.set_value(0.5), run_time=4, rate_func=linear)
        self.decir("Si no aviso, usa f = +x y el pitch sale con el signo cambiado: arriba es abajo.", RED)
        self.play(tt.animate.set_value(1), run_time=4, rate_func=linear)
        self.wait(1)
        f = MathTex(r"f \to -f:\quad \text{pitch} \to -\text{pitch},\quad \text{roll} \to -\text{roll},\quad \text{yaw} \to \text{yaw}", font_size=34)\
            .move_to(DOWN * 2.15)
        self.play(Write(f))
        self.decir(f"Y atornillar 100 °/s se lee {num(r_mal)} en vez de {num(r_bien)}: sale desatornillar. El yaw no cambia.", RED)
        self.wait(3.5)


# ---------------------------------------------------------------------------------------------------------
class TresFlechas(Escena3D):
    """El antebrazo con sus tres flechas: se enciende la que corresponde, a cualquier elevación."""

    def construct(self):
        self.set_camera_orientation(phi=70 * DEGREES, theta=-70 * DEGREES, zoom=0.95)
        self.titulo("Tres flechas pegadas al antebrazo")
        codo = np.array([-1.6, 0, -1.0])
        e, psi, torn = ValueTracker(25), ValueTracker(0), ValueTracker(0)
        om = {"fn": lambda: np.zeros(3)}
        F = lambda: brazo(e.get_value(), psi.get_value())[0]
        d = lambda: brazo(e.get_value(), psi.get_value(), torn.get_value())[1]
        p = lambda: unit(np.cross(F(), ARRIBA))
        tasas = lambda: rates(*lectura(om["fn"](), F(), d()))
        self.add(always_redraw(lambda: dibujo_brazo(F(), d(), codo)))

        def tres():
            y, pi, r = tasas()
            o = lambda v: float(np.clip(0.4 + abs(v) / 60, 0.4, 1))
            base = codo + 2.04 * F()
            return VGroup(flecha(base, base + 1.8 * ARRIBA, YAW, 8, o(y)), flecha(base, base + 1.8 * p(), PITCH, 8, o(pi)),
                          flecha(codo + 3.0 * F(), codo + 4.2 * F(), ROLL, 8, o(r)))

        self.add(always_redraw(tres))
        self.fijo(lambda: en_esquina(barras(tasas())))
        self.fijo(lambda: texto(f"elevación {num(e.get_value())}°", 24).to_corner(UL).shift(DOWN * 0.85))
        self.decir("Yaw en la vertical, pitch de costado, roll a lo largo.")
        self.wait(1.5)

        def tanda(ee):
            om["fn"] = lambda: 60 * ARRIBA
            self.decir("Giro alrededor de la vertical: se enciende el yaw (y un poco el roll).", YAW)
            self.play(psi.animate.set_value(psi.get_value() + 45), run_time=45 / 60, rate_func=linear)
            om["fn"] = lambda: -60 * ARRIBA
            self.play(psi.animate.set_value(psi.get_value() - 45), run_time=45 / 60, rate_func=linear)
            om["fn"] = lambda: 60 * p()
            self.decir("Subir la mano: se enciende el pitch, y nada más.", PITCH)
            self.play(e.animate.set_value(e.get_value() + 45), run_time=45 / 60, rate_func=linear)
            om["fn"] = lambda: -60 * p()
            self.play(e.animate.set_value(e.get_value() - 45), run_time=45 / 60, rate_func=linear)
            om["fn"] = lambda: 60 * F()
            self.decir("Atornillar: se enciende el roll, y nada más.", ROLL)
            self.play(torn.animate.set_value(torn.get_value() + 120), run_time=2, rate_func=linear)
            om["fn"] = lambda: np.zeros(3)
            self.play(e.animate.set_value(ee), run_time=1.5)

        tanda(-30)
        self.decir("Con otra elevación, las mismas tres cuentas.")
        self.wait(0.5)
        tanda(-30)
        self.decir("Tres números por muestra, sacados de ω, g y f.")
        self.wait(3)
