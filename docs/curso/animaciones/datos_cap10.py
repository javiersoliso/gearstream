"""Los números de las animaciones del capítulo 10 que salen de código Python: los detectores de verdad de
tools/air_mouse.py (toque, sacudida, permanencia y scroll), corridos sobre señales inventadas con sus valores por
defecto. cap10.py lo importa y tools/test_gestos.js lo corre y comprueba lo que dice.

    python -I docs/curso/animaciones/datos_cap10.py > datos.json

Solo usa la biblioteca estándar, igual que air_mouse.py.
"""
import json
import math
import os
import random
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "..", "tools"))
import air_mouse  # noqa: E402  el de verdad
from air_mouse import DwellDetector, RollScroller, ShakeDetector, TapDetector  # noqa: E402

CFG = air_mouse.make_config()


def r2(v):
    return round(v, 2)


def toque(nombre, golpe, giro, semilla):
    """golpe(t) es lo que suma al acelerómetro z y giro(t) el tamaño del giro, con t en ms desde el toque en 1000."""
    rng = random.Random(semilla)
    det = TapDetector(CFG)
    ts, az, ds, om = [], [], [], []
    cand, fallo = None, None
    for t in range(0, 2001, 10):
        a = 8.0 + golpe(t - 1000) + rng.gauss(0, 0.03)
        w = abs(giro(t - 1000)) + abs(rng.gauss(0, 1.0))
        c = det.feed_accel(t, a, True)
        if c and cand is None:
            cand = c
        r = det.feed_gyro(t, w)
        if r:
            fallo = (t, r)
        ts.append(t)
        az.append(r2(a))
        ds.append(r2(det.acc[-1][2]))
        om.append(r2(w))
    decidido, r = fallo
    return {"nombre": nombre, "t": ts, "az": az, "d": ds, "giro": om, "t_cand": cand["t"], "armado": cand["armed"],
            "t_decide": decidido, "veredicto": r["verdict"], "ancho": r["width"], "linea_base": r2(r["baseline"]),
            "giro_antes": r2(r["pre_max"]), "giro_despues": r2(r["post_max"]), "pico": r2(r["peak"])}


def golpe_seco(u):
    """Un golpe en la esfera: dos o tres muestras y vuelve adonde estaba."""
    return {0: -3.2, 10: 2.0, 20: -0.8}.get(int(u), 0.0)


def toques():
    quieto = lambda u: 0.0                                                 # noqa: E731
    return [
        toque("toque de verdad", golpe_seco, quieto, 1),
        toque("la mano ya venía girando", golpe_seco, lambda u: 40.0 if u < -10 else 0.0, 2),
        toque("la mano se mueve después", golpe_seco, lambda u: 45.0 if u > 60 else 0.0, 3),
        toque("cambió de postura", lambda u: 3.0 if u >= 0 else 0.0, quieto, 4),
    ]


def sacudida(nombre, wx, dur=2000):
    det = ShakeDetector(CFG)
    ts, xs, fuegos = [], [], []
    for t in range(0, dur + 1, 10):
        w = (wx(t), 0.0, 0.0)
        s = det.feed(t, w)
        if s is not None:
            fuegos.append({"t": t, "inicio": s})
        ts.append(t)
        xs.append(r2(w[0]))
    return {"nombre": nombre, "t": ts, "wx": xs, "fuegos": fuegos}


def sacudidas():
    def ida_y_vuelta(f, t0=300, t1=1700):
        return lambda t: 800 * math.sin(2 * math.pi * f * (t - t0) / 1000) if t0 <= t <= t1 else 0.0

    barrido = []
    for decimas in range(10, 61, 5):
        f = decimas / 10
        barrido.append({"hz": f, "dispara": len(sacudida("", ida_y_vuelta(f))["fuegos"]) > 0})
    return {
        "fuerte": sacudida("cuatro vueltas por segundo", ida_y_vuelta(4)),
        "lenta": sacudida("dos vueltas por segundo", ida_y_vuelta(2)),
        "giro": sacudida("un solo giro", lambda t: 900 * math.exp(-0.5 * ((t - 1000) / 30) ** 2)),
        "barrido": barrido,
    }


def permanencia():
    """Se queda quieto, viaja unos 316 px, se queda quieto otra vez, y sigue quieto."""
    rng = random.Random(9)
    det = DwellDetector(CFG)
    x, y = 120.0, 300.0
    ts, xs, ys, carga, viaje, quieto, fuegos = [], [], [], [], [], [], []
    for t in range(0, 4001, 10):
        viaja = 800 <= t < 1800
        dx = 3.0 * (1 - math.cos(2 * math.pi * (t - 800) / 1000)) if viaja else rng.gauss(0, 0.05)
        dy = -1.0 * (1 - math.cos(2 * math.pi * (t - 800) / 1000)) if viaja else rng.gauss(0, 0.05)
        rho = 25.0 * (1 - math.cos(2 * math.pi * (t - 800) / 1000)) / 2 if viaja else 0.5
        x, y = x + dx, y + dy
        if det.feed(t, rho, (x, y), math.hypot(dx, dy), True):
            fuegos.append(t)
        armado = det.travel >= CFG.dwell_arm and det.seen_fast
        lleva = (t - det.hold_start) / (CFG.dwell_time * 1000) if det.hold_start is not None else 0.0
        ts.append(t)
        xs.append(r2(x))
        ys.append(r2(y))
        carga.append(r2(min(1.0, lleva)) if armado else 0.0)
        viaje.append(r2(det.travel))
        quieto.append(r2(lleva * CFG.dwell_time))
    return {"t": ts, "x": xs, "y": ys, "carga": carga, "viajado": viaje, "quieto": quieto, "fuegos": fuegos,
            "tiempo": CFG.dwell_time, "viaje": CFG.dwell_arm, "velocidad": CFG.dwell_speed}


def scroll(nombre, e_de_t, dur=3000, rho=1.0):
    det = RollScroller(CFG)
    ts, es, activo, muescas, entradas, salidas = [], [], [], [], [], []
    prev = e_de_t(0)
    for t in range(0, dur + 1, 10):
        e = e_de_t(t)
        rate = (e - prev) / 0.01
        prev = e
        for ev in det.feed(t, e, rate, rho, True):
            if ev[0] == "enter":
                entradas.append(t)
            elif ev[0] == "wheel":
                muescas.append({"t": t, "e": r2(e), "n": ev[1]})
            else:
                salidas.append(t)
        ts.append(t)
        es.append(r2(e))
        activo.append(det.active)
    return {"nombre": nombre, "t": ts, "e": es, "activo": activo, "muescas": muescas, "entradas": entradas,
            "salidas": salidas, "rechazos": dict(det.rejected)}


def rampa(t0, t1, a, b):
    return lambda t: a + (b - a) * min(1.0, max(0.0, (t - t0) / (t1 - t0)))


def scrolls():
    def ir_y_volver(rate, tope, t0=500, quieto=500):
        sube = 1000 * tope / rate
        return lambda t: rampa(t0, t0 + sube, 0, tope)(t) if t < t0 + sube + quieto else rampa(t0 + sube + quieto, t0 + 2 * sube + quieto, tope, 0)(t)

    def sin_pausa(t):
        return 6 * math.sin(2 * math.pi * 1.4 * t / 1000) + rampa(800, 1500, 0, 40)(t)

    return {
        "lento": scroll("despacio, tras una pausa", ir_y_volver(60, 46)),
        "rapido": scroll("de un golpe", ir_y_volver(300, 46)),
        "sin_pausa": scroll("sin pausa antes", sin_pausa),
        "entrar": CFG.scroll_enter, "salir": CFG.scroll_exit, "muesca": CFG.scroll_deg_per_notch, "tasa_max": CFG.scroll_max_rate,
    }


def histeresis_de_postura():
    """_pose_gate: pausa cuando −gf pasa de 0.87 y vuelve cuando baja de 0.80. En grados bajo la horizontal."""
    return {"entra": r2(math.degrees(math.asin(0.87))), "sale": r2(math.degrees(math.asin(0.80)))}


def calcular():
    return {"toques": toques(), "sacudidas": sacudidas(), "permanencia": permanencia(), "scroll": scrolls(),
            "postura": histeresis_de_postura(),
            "cfg": {"tap_thr": CFG.tap_thr, "tap_width": CFG.tap_width, "tap_pre": CFG.tap_pre, "tap_post": CFG.tap_post,
                    "tap_post_ms": CFG.tap_post_ms}}


if __name__ == "__main__":
    print(json.dumps(calcular()))
