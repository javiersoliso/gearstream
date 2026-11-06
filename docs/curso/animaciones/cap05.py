"""Animaciones del capítulo 5 (Rotar), una por concepto.

    python docs/curso/animaciones/render.py cap05                 # todas, a GIF en docs/curso/media/cap05/
    python -m manim -ql docs/curso/animaciones/cap05.py Cuaternion  # una, rápido, para mirarla

La cuenta (rot, qmul, qcols) es la de server/web/mocapmath.js: datos_cap05.js la corre con node y este archivo
comprueba que su copia en Python da lo mismo antes de dibujar nada.
"""
import json
import os
import subprocess

import numpy as np
from manim import *

AQUI = os.path.dirname(os.path.abspath(__file__))
D = json.loads(subprocess.run(["node", os.path.join(AQUI, "datos_cap05.js")], capture_output=True, check=True,
                              text=True, encoding="utf-8").stdout)
CX, CY, CZ = RED, GREEN, BLUE          # los ejes del reloj
GRADO = np.pi / 180


# ---------- la cuenta, igual que mocapmath.js ----------
def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot(v, k, a):
    """Rodrigues: gira v alrededor de k un ángulo a."""
    k, v = unit(k), np.asarray(v, float)
    return v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * np.dot(k, v) * (1 - np.cos(a))


def R_eje(k, a):
    return np.column_stack([rot(e, k, a) for e in np.eye(3)])


def quat(k, a):
    return np.array([np.cos(a / 2), *(unit(k) * np.sin(a / 2))])


def qmul(a, b):
    return np.array([a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
                     a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
                     a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
                     a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0]])


def qcols(q):
    w, x, y, z = q
    return [np.array([1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)]),
            np.array([2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)]),
            np.array([2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)])]


def matriz(q):
    return np.column_stack(qcols(q))


_v, _k = [0.3, -0.5, 0.8], [1, 2, 2]
_qa, _qb = quat([1, 0, 0], np.pi / 2), quat([0, 1, 0], np.pi / 2)
assert np.allclose(rot(_v, _k, 70 * GRADO), D["rot"])
assert np.allclose(rot(rot(_v, [1, 0, 0], np.pi / 2), [0, 1, 0], np.pi / 2), D["xLuegoY"])
assert np.allclose(rot(rot(_v, [0, 1, 0], np.pi / 2), [1, 0, 0], np.pi / 2), D["yLuegoX"])
assert np.allclose(qmul(_qb, _qa), D["qmul"])
assert np.allclose(np.column_stack(qcols(qmul(_qb, _qa))), np.column_stack(D["qcols"]))
assert np.allclose(matriz(quat(_k, 70 * GRADO)), R_eje(_k, 70 * GRADO))     # el cuaternión y Rodrigues dan lo mismo


def Rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


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


class Escena3D(ThreeDScene):
    def decir(self, s, color=WHITE, size=24):
        nuevo = texto(s, size, color=color).to_edge(DOWN, buff=0.35)
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


def cifras(valores, colores, size=26, dec=2):
    return VGroup(*[DecimalNumber(v, num_decimal_places=dec, font_size=size, color=c, include_sign=True)
                    for v, c in zip(valores, colores)])


# ---------------------------------------------------------------------------------------------------------
class RotarEnElPlano(Scene):
    """Rotar en el plano: (x, y) → (x cos θ − y sen θ, x sen θ + y cos θ), sin cambiar el largo."""

    def construct(self):
        fondo = NumberPlane(background_line_style={"stroke_opacity": 0.2}, axis_config={"stroke_opacity": 0.4})
        th = ValueTracker(0)
        malla = always_redraw(lambda: NumberPlane(x_range=[-4, 4], y_range=[-4, 4], axis_config={"stroke_opacity": 0},
                                                  background_line_style={"stroke_color": BLUE_D, "stroke_opacity": 0.55})
                              .rotate(th.get_value(), about_point=ORIGIN))
        titulo = texto("Rotar en el plano", 34).to_edge(UP).add_background_rectangle(opacity=0.8)
        self.add(fondo)
        self.play(Write(titulo))
        x, y = 2, 1
        i_ = lambda: np.array([np.cos(th.get_value()), np.sin(th.get_value()), 0])
        j_ = lambda: np.array([-np.sin(th.get_value()), np.cos(th.get_value()), 0])
        fi = always_redraw(lambda: flecha(ORIGIN, i_(), CY, 7))
        fj = always_redraw(lambda: flecha(ORIGIN, j_(), CX, 7))
        fv = always_redraw(lambda: flecha(ORIGIN, x * i_() + y * j_(), YELLOW, 7))
        partes = always_redraw(lambda: VGroup(DashedLine(ORIGIN, x * i_(), color=CY), DashedLine(x * i_(), x * i_() + y * j_(), color=CX)))
        li = MathTex(r"\hat\imath", color=CY, font_size=36).add_updater(lambda m: m.move_to(1.35 * i_() + 0.25 * j_()))
        lj = MathTex(r"\hat\jmath", color=CX, font_size=36).add_updater(lambda m: m.move_to(1.35 * j_() - 0.25 * i_()))
        lv = MathTex(r"v = 2\,\hat\imath + 1\,\hat\jmath", color=YELLOW, font_size=32)\
            .add_updater(lambda m: m.next_to(x * i_() + y * j_(), UR, buff=0.1))
        self.play(GrowArrow(fi), GrowArrow(fj), FadeIn(li, lj))
        self.play(Create(partes), GrowArrow(fv), FadeIn(lv))
        self.add(malla, partes, fi, fj, fv, li, lj, lv)
        lect = always_redraw(lambda: texto(f"θ = {np.degrees(th.get_value()):.0f}°    largo de v = {np.hypot(x, y):.2f}", 24)
                             .to_corner(UL).shift(DOWN * 0.9).add_background_rectangle(opacity=0.8))
        self.add(lect)
        self.play(th.animate.set_value(50 * GRADO), run_time=3)
        f1 = MathTex(r"\hat\imath \to (\cos\theta,\ \sin\theta)", r"\qquad \hat\jmath \to (-\sin\theta,\ \cos\theta)",
                     font_size=32).to_corner(DR).shift(UP * 2.0).add_background_rectangle(opacity=0.8)
        self.play(Write(f1))
        nota = texto("v sigue siendo 2 de la primera más 1 de la segunda: se mueve con ellas", 24)\
            .to_edge(DOWN, buff=0.3).add_background_rectangle(opacity=0.8)
        self.play(FadeIn(nota))
        self.play(th.animate.set_value(140 * GRADO), run_time=3)
        f2 = MathTex(r"x' = x\cos\theta - y\sin\theta", r"\\ y' = x\sin\theta + y\cos\theta", font_size=36)\
            .next_to(f1, DOWN, buff=0.3).align_to(f1, RIGHT).add_background_rectangle(opacity=0.8)
        self.play(Write(f2))
        self.play(th.animate.set_value(30 * GRADO), run_time=3)
        moral = texto("Girar es mover las dos flechas de base: el largo no cambia.", 26)\
            .to_edge(DOWN, buff=0.3).add_background_rectangle(opacity=0.8)
        self.play(FadeOut(nota), FadeIn(moral))
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
class EjeYAngulo(Escena3D):
    """Rodrigues: la parte de v a lo largo del eje se queda; la otra gira como en el plano."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-55 * DEGREES, zoom=0.95)
        self.titulo("Girar alrededor de un eje (Rodrigues)")
        k = unit([0.35, -0.3, 1])
        v = np.array([1.9, 0.6, 0.5])
        par = k * np.dot(k, v)
        th = ValueTracker(0)
        vp = lambda: rot(v, k, th.get_value())
        eje = DashedLine(-2.6 * k, 3.2 * k, color=WHITE, stroke_opacity=0.6)
        fk = flecha(ORIGIN, 1.2 * k, WHITE, 7)
        lk = texto("k", 26).move_to(3.45 * k)
        self.add_fixed_orientation_mobjects(lk)
        self.play(Create(eje), GrowArrow(fk), FadeIn(lk))
        fv = always_redraw(lambda: flecha(ORIGIN, vp(), YELLOW, 7))
        self.play(GrowArrow(fv.copy()), run_time=0.6)
        self.add(fv)
        self.decir("Queremos girar v alrededor del eje k un ángulo θ.")
        fpar = flecha(ORIGIN, par, BLUE, 8)
        circulo = Circle(radius=np.linalg.norm(v - par), color=ORANGE, stroke_opacity=0.6)\
            .apply_matrix(z_to_vector(k)).shift(par)
        fperp = always_redraw(lambda: flecha(par, vp(), ORANGE, 6))
        self.play(GrowArrow(fpar))
        self.decir("La parte de v a lo largo de k, k (k·v), no se mueve.", BLUE)
        self.play(Create(fperp), Create(circulo))
        self.decir("La otra parte gira en el plano perpendicular a k, como en el plano.", ORANGE)
        kv = np.cross(k, v)
        fkv = DashedLine(par, par + kv, color=GREEN)
        lkv = texto("k × v", 22, color=GREEN).move_to(par + 1.15 * kv)
        self.add_fixed_orientation_mobjects(lkv)
        self.play(Create(fkv), FadeIn(lkv))
        self.decir("Sus dos flechas de base: lo perpendicular de v, y k × v.", GREEN)
        formula = MathTex(r"v' = v\cos\theta + (k\times v)\sin\theta + k\,(k\cdot v)(1-\cos\theta)", font_size=34)\
            .to_corner(UL).shift(DOWN * 0.8)
        self.add_fixed_in_frame_mobjects(formula)
        self.play(Write(formula))
        self.begin_ambient_camera_rotation(rate=0.15)
        lect = self.fijo(lambda: texto(f"θ = {np.degrees(th.get_value()) % 360:.0f}°", 26).to_corner(UR).shift(DOWN * 0.8))
        self.play(th.animate.set_value(2 * np.pi), run_time=7, rate_func=linear)
        self.decir("Eso es Rodrigues: las dos partes, juntas. Así gira rot() en mocapmath.js.")
        self.play(th.animate.set_value(2 * np.pi + 70 * GRADO), run_time=2)
        self.wait(2)
        self.stop_ambient_camera_rotation()


# ---------------------------------------------------------------------------------------------------------
class TodoGiroEsUnEje(Escena3D):
    """Todo giro en 3D, por raro que sea, es girar un ángulo alrededor de un solo eje."""

    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-70 * DEGREES, zoom=0.85)
        self.titulo("Todo giro es un solo eje y un ángulo")
        ca, cb = np.array([-2.6, 0, 0]), np.array([2.6, 0, 0])
        A, B = reloj(1.3, centro=ca), reloj(1.3, centro=cb)
        la = texto("dos giros seguidos", 24).to_corner(UL).shift(DOWN * 0.9 + RIGHT * 0.8)
        lb = texto("uno solo", 24).to_corner(UR).shift(DOWN * 0.9 + LEFT * 1.5)
        self.add_fixed_in_frame_mobjects(la, lb)
        self.play(FadeIn(A, B, la, lb))
        self.decir("A la izquierda: 90° alrededor de x y después 60° alrededor de z.")
        self.play(Rotate(A, 90 * GRADO, axis=RIGHT, about_point=ca), run_time=2)
        self.play(Rotate(A, 60 * GRADO, axis=OUT, about_point=ca), run_time=2)
        R = Rz(60 * GRADO) @ Rx(90 * GRADO)
        ang = np.arccos((np.trace(R) - 1) / 2)
        k = unit([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
        eje = Line(cb - 1.6 * k, cb + 1.6 * k, color=YELLOW, stroke_width=5)
        self.decir("A la derecha: el eje que ese giro deja quieto (R k = k).", YELLOW)
        self.play(Create(eje))
        self.decir(f"Un solo giro de {np.degrees(ang):.1f}° alrededor de él deja el cubo igual.", YELLOW)
        self.play(Rotate(B, ang, axis=k, about_point=cb), run_time=3)
        self.wait(1)
        self.decir("Por raro que sea el giro, siempre hay un eje que se queda quieto.")
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
class MatrizDeRotacion(Escena3D):
    """La matriz de rotación: sus columnas son los ejes del reloj vistos en el mundo."""

    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-50 * DEGREES, zoom=0.9)
        self.titulo("La matriz de rotación")
        mundo = VGroup(*[DashedLine(ORIGIN, 2.6 * e, stroke_opacity=0.4) for e in np.eye(3)])
        k = unit([1, 0.6, 0.9])
        a = ValueTracker(0)
        R = lambda: R_eje(k, a.get_value())
        cubo = always_redraw(lambda: reloj(0.9, R()))
        flechas = always_redraw(lambda: ejes(R(), 1.9))
        self.add(mundo)
        self.play(FadeIn(cubo), Create(flechas))

        def tabla():
            M = R()
            cols = VGroup()
            for j, c in enumerate([CX, CY, CZ]):
                col = VGroup(*[DecimalNumber(M[i, j], num_decimal_places=2, font_size=26, color=c, include_sign=True)
                               for i in range(3)]).arrange(DOWN, buff=0.18)
                cols.add(col)
            cols.arrange(RIGHT, buff=0.35)
            izq = VMobject().set_points_as_corners([cols.get_corner(UL) + LEFT * 0.12 + UP * 0.12 + RIGHT * 0.12,
                                                     cols.get_corner(UL) + LEFT * 0.12 + UP * 0.12,
                                                     cols.get_corner(DL) + LEFT * 0.12 + DOWN * 0.12,
                                                     cols.get_corner(DL) + LEFT * 0.12 + DOWN * 0.12 + RIGHT * 0.12])
            der = izq.copy().rotate(PI, about_point=cols.get_center())
            nombres = VGroup(*[texto(n, 22, color=c).next_to(col, UP, buff=0.15) for n, c, col in zip("XYZ", [CX, CY, CZ], cols)])
            return VGroup(texto("R =", 26).next_to(cols, LEFT, buff=0.35), izq, cols, der, nombres)\
                .to_corner(UR).shift(DOWN * 0.8)

        self.fijo(tabla)
        self.decir("Sus columnas son los ejes del reloj (X, Y, Z) vistos en el mundo.")
        self.play(a.animate.set_value(100 * GRADO), run_time=4)
        self.decir("Gira el reloj, y cada columna dice hacia dónde quedó apuntando cada eje.")
        self.play(a.animate.set_value(-40 * GRADO), run_time=4)
        f = MathTex(r"R^{\mathsf T}R = I \;\Rightarrow\; R^{-1} = R^{\mathsf T}", font_size=38).to_corner(UL).shift(DOWN * 0.9)
        self.add_fixed_in_frame_mobjects(f)
        self.decir("Columnas de largo 1 y perpendiculares entre sí (ortonormal):")
        self.play(Write(f))
        self.decir("deshacer el giro, del mundo al reloj, es solo transponer la matriz.")
        self.play(a.animate.set_value(60 * GRADO), run_time=3)
        self.wait(2)


# ---------------------------------------------------------------------------------------------------------
class OrdenNoConmuta(Escena3D):
    """El orden importa: 90° en x y luego en y no da lo mismo que en y y luego en x."""

    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-60 * DEGREES, zoom=0.8)
        self.titulo("El orden importa")
        ca, cb = np.array([-2.7, 0, 0]), np.array([2.7, 0, 0])
        A, B = reloj(1.4, centro=ca), reloj(1.4, centro=cb)
        guias = VGroup(ejes(np.eye(3), 0.8, ca + np.array([-1.3, -1.3, -1.1]), 4),
                       ejes(np.eye(3), 0.8, cb + np.array([-1.3, -1.3, -1.1]), 4))
        la = texto("x, luego y", 26).to_corner(UL).shift(DOWN * 0.9 + RIGHT * 1.0)
        lb = texto("y, luego x", 26).to_corner(UR).shift(DOWN * 0.9 + LEFT * 1.4)
        self.add_fixed_in_frame_mobjects(la, lb)
        self.play(FadeIn(A, B, guias, la, lb))
        self.decir("Los dos cubos empiezan igual. Rojo: x; verde: y; azul: z.")
        self.play(Rotate(A, 90 * GRADO, axis=RIGHT, about_point=ca), Rotate(B, 90 * GRADO, axis=UP, about_point=cb), run_time=2)
        self.play(Rotate(A, 90 * GRADO, axis=UP, about_point=ca), Rotate(B, 90 * GRADO, axis=RIGHT, about_point=cb), run_time=2)
        self.decir("Los mismos dos giros en otro orden: terminan distinto.", YELLOW)
        f = MathTex(r"R_y R_x \neq R_x R_y", font_size=44).to_edge(DOWN, buff=1.1)
        self.add_fixed_in_frame_mobjects(f)
        self.play(Write(f))
        self.wait(1.5)
        self.decir("Los giros en 3D no conmutan (en el plano, sí: 30° y 50° dan 80° igual).")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class VelocidadAngular(Escena3D):
    """La velocidad angular es una flecha: su dirección es el eje del giro y su largo, la rapidez."""

    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-50 * DEGREES, zoom=0.9)
        self.titulo("La velocidad angular es una flecha")
        w = [ValueTracker(0.0), ValueTracker(0.0), ValueTracker(1.5)]
        omega = lambda: np.array([x.get_value() for x in w])
        estado = {"R": np.eye(3)}

        def paso(m, dt):
            o = omega()
            if np.linalg.norm(o) > 1e-9:
                estado["R"] = R_eje(o, np.linalg.norm(o) * dt) @ estado["R"]

        reloj_ = Mobject().add_updater(paso)
        self.add(reloj_)
        cubo = always_redraw(lambda: reloj(1.2, estado["R"]))
        fw = always_redraw(lambda: flecha(ORIGIN, 0.75 * omega(), YELLOW, 8) if np.linalg.norm(omega()) > 0.05 else VectorizedPoint())
        self.add(cubo, fw)
        lect = self.fijo(lambda: VGroup(
            texto(f"ω = ({omega()[0]:.1f}, {omega()[1]:.1f}, {omega()[2]:.1f}) rad/s en el mundo", 22, color=YELLOW),
            texto("lo que lee el giroscopio, en los ejes del reloj:", 20),
            VGroup(*[texto(f"{n} {v:+.2f}", 22, color=c) for n, v, c in
                     zip("xyz", estado["R"].T @ omega(), [CX, CY, CZ])]).arrange(RIGHT, buff=0.4))
            .arrange(DOWN, aligned_edge=LEFT, buff=0.15).to_corner(UL).shift(DOWN * 0.8))
        self.decir("La dirección de ω es el eje del giro; su largo, qué tan rápido gira.")
        self.wait(3)
        self.decir("Más largo, más rápido.")
        self.play(w[2].animate.set_value(3.5), run_time=1.5)
        self.wait(2)
        self.decir("Otra dirección, otro eje.")
        self.play(w[0].animate.set_value(2.5), w[2].animate.set_value(1.0), run_time=2)
        self.wait(3)
        self.decir("Girando quieto alrededor de un eje, el giroscopio lee siempre lo mismo.")
        self.wait(3)
        self.decir("Por eso es una flecha y no un número: hace falta decir alrededor de qué.")
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
class PuntoQueGira(Escena3D):
    """Un punto pegado a algo que gira con ω se mueve a ω × r."""

    def construct(self):
        self.set_camera_orientation(phi=62 * DEGREES, theta=-60 * DEGREES, zoom=0.9)
        self.titulo("¿Hacia dónde va un punto que gira?")
        wz = 1.0
        ang = ValueTracker(0)
        disco = always_redraw(lambda: Circle(radius=2.4, color=GREY_B, fill_opacity=0.15, stroke_opacity=0.6)
                              .rotate(ang.get_value(), about_point=ORIGIN))
        marca = always_redraw(lambda: Line(ORIGIN, 2.4 * np.array([np.cos(ang.get_value()), np.sin(ang.get_value()), 0]),
                                           color=GREY_B, stroke_opacity=0.6))
        fw = flecha(ORIGIN, OUT * 2.2, YELLOW, 8)
        lw = texto("ω", 28, color=YELLOW).move_to(OUT * 2.5)
        self.add_fixed_orientation_mobjects(lw)
        self.add(disco, marca)
        self.play(GrowArrow(fw), FadeIn(lw))
        base = {"cerca": np.array([1.0, 0, 0]), "lejos": np.array([2.0, 0, 0]), "arriba": np.array([1.0, 0, 1.4])}
        pos = lambda b, d=0: Rz(ang.get_value() + d) @ base[b]
        omega = np.array([0, 0, wz])

        def punto(b, color):
            return always_redraw(lambda: VGroup(Dot(pos(b), color=color, radius=0.08),
                                                flecha(ORIGIN, pos(b), GREY_A, 3),
                                                flecha(pos(b), pos(b) + 0.9 * np.cross(omega, pos(b)), ORANGE, 6)))

        p1 = punto("cerca", WHITE)
        self.add(p1)
        self.decir("r va del centro al punto; su velocidad es ω × r, perpendicular a ω y a r.", ORANGE)
        self.play(ang.animate.set_value(PI), run_time=4, rate_func=linear)
        p2 = punto("lejos", WHITE)
        self.add(p2)
        self.decir("El doble de lejos del eje, el doble de rápido.")
        self.play(ang.animate.set_value(2 * PI), run_time=4, rate_func=linear)
        p3 = punto("arriba", WHITE)
        self.add(p3)
        self.decir("Lo que cuenta es la distancia al eje: |ω × r| = |ω| |r| sen φ.")
        self.play(ang.animate.set_value(3 * PI), run_time=4, rate_func=linear)
        self.wait(1.5)


class VistoDesdeElReloj(Scene):
    """Un vector quieto en el mundo, visto desde el reloj que gira con ω, cambia a −ω × v."""

    def construct(self):
        titulo = texto("Visto desde el reloj, el mundo gira al revés", 32).to_edge(UP)
        self.play(Write(titulo))
        ang = ValueTracker(0)
        ci, cd = LEFT * 3.4 + DOWN * 0.3, RIGHT * 3.4 + DOWN * 0.3

        def caja(centro, a):
            sq = RoundedRectangle(corner_radius=0.25, width=2.0, height=2.0, color=GREY_A, fill_opacity=0.15)
            raya = Line(ORIGIN, RIGHT * 1.0, color=CX, stroke_width=6)
            return VGroup(sq, raya).rotate(a, about_point=ORIGIN).shift(centro)

        izq = always_redraw(lambda: caja(ci, ang.get_value()))
        der = caja(cd, 0)
        g_mundo = flecha(ci, ci + DOWN * 1.5, BLUE, 7)
        g_reloj = always_redraw(lambda: flecha(cd, cd + Rz(-ang.get_value()) @ (DOWN * 1.5), BLUE, 7))
        vel = always_redraw(lambda: flecha(cd + Rz(-ang.get_value()) @ (DOWN * 1.5),
                                           cd + Rz(-ang.get_value()) @ (DOWN * 1.5) + 0.6 * np.cross(-OUT, Rz(-ang.get_value()) @ (DOWN * 1.5)),
                                           ORANGE, 6))
        li = texto("en el mundo: el reloj gira,\nla gravedad (azul) queda quieta", 22).next_to(ci, UP, buff=2.1)
        ld = texto("desde el reloj: el reloj quieto,\nla gravedad gira al revés", 22).next_to(cd, UP, buff=2.1)
        self.play(FadeIn(izq, der, li, ld), GrowArrow(g_mundo), Create(g_reloj))
        self.play(ang.animate.set_value(PI / 2), run_time=3, rate_func=linear)
        self.add(vel)
        f = MathTex(r"\frac{dv}{dt}\Big|_{\text{reloj}} = -\,\omega \times v", font_size=40, color=ORANGE).to_edge(DOWN, buff=1.0)
        self.play(Write(f))
        self.play(ang.animate.set_value(2 * PI), run_time=6, rate_func=linear)
        moral = texto("Así se sigue la gravedad con el giroscopio entre una lectura y la otra.", 24).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(moral))
        self.wait(2.5)


# ---------------------------------------------------------------------------------------------------------
def cardan(psi, e, phi):
    """Tres anillos: rumbo (alrededor de la vertical), inclinación y giro (alrededor del antebrazo), en grados."""
    F1 = Rz(psi * GRADO)
    F2 = F1 @ Ry(-e * GRADO)
    F3 = F2 @ Rx(phi * GRADO)
    afuera = Circle(radius=2.5, color=BLUE, stroke_width=6).apply_matrix(F1 @ Rx(PI / 2), about_point=ORIGIN)
    medio = Circle(radius=2.05, color=GREEN, stroke_width=6).apply_matrix(F2, about_point=ORIGIN)
    adentro = Circle(radius=1.6, color=ORANGE, stroke_width=6).apply_matrix(F3 @ Rx(PI / 2), about_point=ORIGIN)
    brazo = flecha(ORIGIN, 3.0 * F3[:, 0], GREY_A, 8)
    marca = flecha(ORIGIN, 1.0 * F3[:, 2], CZ, 5)           # arriba del reloj, para ver el giro
    return VGroup(afuera, medio, adentro, brazo, marca)


class AngulosDeEuler(Escena3D):
    """Tres giros seguidos alrededor de ejes que se van moviendo: rumbo, inclinación y giro."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-35 * DEGREES, zoom=0.85)
        self.titulo("Tres ángulos: rumbo, inclinación y giro")
        a = [ValueTracker(0), ValueTracker(0), ValueTracker(0)]
        anillos = always_redraw(lambda: cardan(*[x.get_value() for x in a]))
        vertical = DashedLine(IN * 3, OUT * 3, stroke_opacity=0.4)
        self.add(vertical)
        self.play(Create(anillos))
        self.fijo(lambda: VGroup(*[texto(f"{n} {x.get_value():.0f}°", 24, color=c) for n, x, c in
                                   zip(["rumbo", "inclinación", "giro"], a, [BLUE, GREEN, ORANGE])])
                  .arrange(DOWN, aligned_edge=LEFT, buff=0.15).to_corner(UL).shift(DOWN * 0.8))
        self.decir("Rumbo: el anillo azul gira alrededor de la vertical y arrastra a los otros.", BLUE)
        self.play(a[0].animate.set_value(55), run_time=2.5)
        self.decir("Inclinación: el verde, alrededor del eje que dejó el azul.", GREEN)
        self.play(a[1].animate.set_value(35), run_time=2.5)
        self.decir("Giro: el naranja, alrededor del antebrazo (la flecha gris).", ORANGE)
        self.play(a[2].animate.set_value(70), run_time=2.5)
        f = MathTex(r"R = R_z(\text{rumbo})\,R_y(-\text{inclinación})\,R_x(\text{giro})", font_size=34).to_corner(UR).shift(DOWN * 0.8)
        self.add_fixed_in_frame_mobjects(f)
        self.play(Write(f))
        self.decir("Fáciles de leer, pero el orden y el punto de partida importan.")
        self.play(a[0].animate.set_value(-30), a[1].animate.set_value(10), a[2].animate.set_value(-40), run_time=3)
        self.wait(2)


class Singularidad(Escena3D):
    """Con el antebrazo colgando, rumbo y giro hacen lo mismo: el rumbo deja de existir."""

    def construct(self):
        self.set_camera_orientation(phi=68 * DEGREES, theta=-35 * DEGREES, zoom=0.85)
        self.titulo("Cuando un ángulo se come al otro")
        a = [ValueTracker(30), ValueTracker(0), ValueTracker(0)]
        anillos = always_redraw(lambda: cardan(*[x.get_value() for x in a]))
        vertical = DashedLine(IN * 3, OUT * 3, stroke_opacity=0.4)
        self.add(vertical, anillos)
        self.fijo(lambda: VGroup(*[texto(f"{n} {x.get_value():.0f}°", 24, color=c) for n, x, c in
                                   zip(["rumbo", "inclinación", "giro"], a, [BLUE, GREEN, ORANGE])])
                  .arrange(DOWN, aligned_edge=LEFT, buff=0.15).to_corner(UL).shift(DOWN * 0.8))
        self.decir("Bajemos el antebrazo hasta que cuelgue: inclinación −90°.", GREEN)
        self.play(a[1].animate.set_value(-90), run_time=3)
        self.decir("Ahora el eje del giro (el antebrazo) quedó sobre la vertical.")
        self.wait(1)
        self.decir("Cambiar el rumbo...", BLUE)
        self.play(a[0].animate.set_value(120), run_time=2.5)
        self.decir("...y el giro hacen lo mismo, con signo contrario: solo cuenta su resta.", ORANGE)
        self.play(a[2].animate.set_value(90), run_time=2.5)
        self.decir("Se perdió una forma de girar: es el bloqueo del cardán (una singularidad).", YELLOW)
        self.wait(2)
        self.play(FadeOut(anillos, vertical))

        # un movimiento suave que pasa cerca de colgar: el rumbo salta 180°
        t = np.linspace(0, 1, 400)
        ang = np.radians(-30 - 120 * t)
        F = np.stack([np.cos(ang), 0.06 * np.ones_like(t), np.sin(ang)], 1)
        F /= np.linalg.norm(F, axis=1, keepdims=True)
        elev, rumbo = np.degrees(np.arcsin(F[:, 2])), np.degrees(np.arctan2(F[:, 1], F[:, 0]))
        a1 = Axes(x_range=[0, 1, 0.25], y_range=[-90, 0, 45], x_length=9, y_length=1.9, tips=False,
                  axis_config={"font_size": 18}, y_axis_config={"include_numbers": True})
        a2 = Axes(x_range=[0, 1, 0.25], y_range=[0, 180, 90], x_length=9, y_length=1.9, tips=False,
                  axis_config={"font_size": 18}, y_axis_config={"include_numbers": True})
        g = VGroup(a1, a2).arrange(DOWN, buff=0.6).shift(DOWN * 0.1 + RIGHT * 0.8)
        l1 = texto("elevación del\nantebrazo (°)", 18).next_to(a1, LEFT, buff=0.3)
        l2 = texto("rumbo (°)", 18).next_to(a2, LEFT, buff=0.3)
        c1 = a1.plot_line_graph(t, elev, add_vertex_dots=False, line_color=GREEN, stroke_width=4)
        c2 = a2.plot_line_graph(t, rumbo, add_vertex_dots=False, line_color=BLUE, stroke_width=4)
        todo = VGroup(g, l1, l2, c1, c2)
        self.add_fixed_in_frame_mobjects(todo)
        self.remove(todo)
        self.decir("Un movimiento suave, de adelante hacia atrás, pasando cerca de colgar.")
        self.play(FadeIn(a1, a2, l1, l2), Create(c1), run_time=2)
        self.play(Create(c2), run_time=2)
        self.decir("El movimiento es suave, pero el rumbo salta 180° en un instante.", YELLOW)
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class Cuaternion(Escena3D):
    """El cuaternión: (cos θ/2, eje·sen θ/2); componer giros es multiplicarlos."""

    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-55 * DEGREES, zoom=0.9)
        self.titulo("Cuatro números para un giro: el cuaternión")
        k = unit([1, 0.4, 1.3])
        th = ValueTracker(0)
        q = lambda: quat(k, th.get_value())
        eje = DashedLine(-2.4 * k, 2.4 * k, color=YELLOW, stroke_opacity=0.7)
        cubo = always_redraw(lambda: reloj(1.4, matriz(q())))
        self.play(Create(eje), FadeIn(cubo))

        def barras():
            vals, nombres, cols = q(), ["w", "x", "y", "z"], [WHITE, CX, CY, CZ]
            g = VGroup()
            for i, (v, n, c) in enumerate(zip(vals, nombres, cols)):
                x0 = i * 1.0
                g.add(Line([x0 - 0.25, 0, 0], [x0 + 0.25, 0, 0], color=GREY_B))
                if abs(v) > 0.005:
                    g.add(Rectangle(width=0.45, height=abs(v) * 1.2, fill_color=c, fill_opacity=0.85, stroke_width=0)
                          .move_to([x0, v * 0.6, 0]))
                g.add(texto(n, 20, color=c).move_to([x0, -1.45, 0]))
                g.add(texto(f"{v:+.2f}", 17).move_to([x0, 1.45, 0]))
            return g.to_corner(UR).shift(DOWN * 0.9 + LEFT * 0.2)

        self.fijo(barras)
        f = MathTex(r"q = \big(\cos\tfrac{\theta}{2},\ k\,\sin\tfrac{\theta}{2}\big)", font_size=36).to_corner(UL).shift(DOWN * 0.8)
        self.add_fixed_in_frame_mobjects(f)
        self.play(Write(f))
        lect = self.fijo(lambda: texto(f"θ = {np.degrees(th.get_value()):.0f}°", 26).next_to(f, DOWN, buff=0.2).align_to(f, LEFT))
        self.decir("Un giro θ alrededor de k: cuatro números, con largo 1.")
        self.play(th.animate.set_value(2 * PI), run_time=7, rate_func=linear)
        self.decir("A los 360° el cubo volvió... pero q = −1. q y −q son el mismo giro.", YELLOW)
        self.wait(2)
        self.play(th.animate.set_value(4 * PI), run_time=5, rate_func=linear)
        self.decir("A los 720°, q vuelve a 1. Por eso va la mitad del ángulo.")
        self.wait(1.5)
        qx, qy = quat([1, 0, 0], PI / 2), quat([0, 1, 0], PI / 2)
        qq = qmul(qy, qx)
        prod = MathTex(r"q_y \otimes q_x = (" + ",\\ ".join(f"{v:.2f}" for v in qq) + ")", font_size=34)\
            .to_corner(UL).shift(DOWN * 2.2)
        self.add_fixed_in_frame_mobjects(prod)
        self.decir("Componer giros es multiplicar: x y luego y es q_y ⊗ q_x, igual que R_y R_x.")
        self.play(Write(prod))
        self.wait(1)
        self.decir("Cuatro números de largo 1: tres libres, como el giro, y nunca se traban.")
        self.wait(3)


# ---------------------------------------------------------------------------------------------------------
class IntegrarOrientacion(Escena3D):
    """Cada muestra gira el cuaternión un poquito, y se normaliza para que no se deforme."""

    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-65 * DEGREES, zoom=0.8)
        self.titulo("Integrar la orientación, muestra por muestra")
        dt, n = 0.05, 140                                   # 20 muestras por segundo, 7 s
        ts = np.arange(n) * dt
        omega = lambda t: np.array([2.5 * np.sin(0.7 * t), 2.0, 1.5 * np.cos(0.5 * t)])      # rad/s, en el reloj
        bien, mal = [np.array([1.0, 0, 0, 0])], [np.array([1.0, 0, 0, 0])]
        for t in ts[:-1]:
            w = omega(t)
            a = np.linalg.norm(w) * dt
            q = qmul(bien[-1], np.array([np.cos(a / 2), *(unit(w) * np.sin(a / 2))]))
            bien.append(q / np.linalg.norm(q))
            mal.append(mal[-1] + 0.5 * qmul(mal[-1], np.array([0, *w])) * dt)            # sumar, sin normalizar
        tt = ValueTracker(0)
        i = lambda: min(n - 1, int(tt.get_value() / dt))
        ca, cb = np.array([-2.6, 0, 0]), np.array([2.6, 0, 0])
        A = always_redraw(lambda: reloj(1.2, matriz(bien[i()]), ca))
        B = always_redraw(lambda: reloj(1.2, matriz(mal[i()]), cb))
        la = MathTex(r"q \leftarrow q \otimes \big(\cos\tfrac{|\omega|\Delta t}{2},\ \hat\omega \sin\tfrac{|\omega|\Delta t}{2}\big)",
                     r"\\ q \leftarrow q\,/\,|q|", font_size=30, color=GREEN).to_corner(UL).shift(DOWN * 0.9)
        lb = MathTex(r"q \leftarrow q + \tfrac12\, q \otimes (0, \omega)\,\Delta t", font_size=30, color=RED)\
            .to_corner(UR).shift(DOWN * 0.9)
        self.add_fixed_in_frame_mobjects(la, lb)
        self.play(FadeIn(A, B), Write(la), Write(lb))
        self.fijo(lambda: VGroup(texto(f"|q| = {np.linalg.norm(bien[i()]):.3f}", 24, color=GREEN).move_to(LEFT * 3.6 + DOWN * 2.3),
                                 texto(f"|q| = {np.linalg.norm(mal[i()]):.3f}", 24, color=RED).move_to(RIGHT * 3.6 + DOWN * 2.3),
                                 texto(f"t = {tt.get_value():.1f} s", 22).move_to(DOWN * 2.3)))
        self.decir("El mismo giroscopio, 20 muestras por segundo. Cada muestra gira un poquito.")
        self.play(tt.animate.set_value(4), run_time=5, rate_func=linear)
        self.decir("A la derecha se suma en vez de girar: |q| crece y el cubo se deforma.", RED)
        self.play(tt.animate.set_value(7 - dt), run_time=5, rate_func=linear)
        self.decir("Girar de verdad y normalizar después de cada paso: siempre un giro.", GREEN)
        self.wait(3)
