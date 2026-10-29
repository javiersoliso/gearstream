"""¿Se distingue el gesto grabado con guided_capture.py del movimiento normal?

    python tools/analyze_gesture.py recordings/captura-pellizco-AAAAMMDD-HHMMSS

Para cada pitido busca el pico de dos señales en la ventana [pitido + 0.1 s, pitido + 1.3 s] (lo que
tarda la mano en reaccionar), y en la fase de movimiento normal el pico de las mismas señales en todas
las ventanas de igual duración. Si los picos del gesto quedan por encima de casi todo el movimiento
normal, un umbral lo detecta. Señales, sobre el acelerómetro (m/s²):
  · golpe: magnitud de la aceleración menos su media de los últimos 40 ms (lo que cambia de golpe)
  · tirón: magnitud de la diferencia entre muestras seguidas (la derivada, sin escalar por el tiempo,
    porque a 200 Hz las marcas de tiempo del reloj llegan en ráfagas)
"""
import csv
import json
import os
import statistics
import sys


def load(folder):
    rows = []
    with open(os.path.join(folder, "samples.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["source"] == "ACCELERATION":
                rows.append((float(r["t_ms"]), float(r["x"]), float(r["y"]), float(r["z"])))
    with open(os.path.join(folder, "cues.json")) as f:
        cues = json.load(f)
    return rows, cues


def features(rows, win=8):
    """golpe y tirón por muestra."""
    hit, jerk = [0.0] * len(rows), [0.0] * len(rows)
    for i in range(len(rows)):
        lo = max(0, i - win)
        n = i - lo
        if n:
            m = [sum(rows[k][c] for k in range(lo, i)) / n for c in (1, 2, 3)]
            hit[i] = sum((rows[i][c + 1] - m[c]) ** 2 for c in range(3)) ** 0.5
        if i:
            jerk[i] = sum((rows[i][c] - rows[i - 1][c]) ** 2 for c in (1, 2, 3)) ** 0.5
    return {"golpe": hit, "tirón": jerk}


def window_peak(ts, values, t0, t1):
    best, at = 0.0, None
    for t, v in zip(ts, values):
        if t0 <= t <= t1 and v > best:
            best, at = v, t
    return best, at


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else None
    if not folder:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recordings")
        caps = sorted(d for d in os.listdir(base) if d.startswith("captura-"))
        if not caps:
            sys.exit("no hay capturas en recordings/")
        folder = os.path.join(base, caps[-1])
    rows, cues = load(folder)
    ts = [r[0] for r in rows]
    span = (ts[-1] - ts[0]) / 1000
    print(f"{os.path.basename(folder)}: {len(rows)} muestras en {span:.0f} s ({len(rows) / span:.0f}/s), {len(cues['cues_ms'])} pitidos")
    f = features(rows)
    a, b = cues["phases_ms"]["normal"]
    L = 1200
    for name, vals in f.items():
        g = [window_peak(ts, vals, c + 100, c + 100 + L) for c in cues["cues_ms"]]
        peaks = [p for p, _ in g]
        lags = [t - c for (p, t), c in zip(g, cues["cues_ms"]) if t is not None]
        normal = []
        t = a
        while t + L <= b:
            normal.append(window_peak(ts, vals, t, t + L)[0])
            t += L / 2
        normal.sort()
        q = lambda xs, p: xs[min(len(xs) - 1, int(p * (len(xs) - 1)))]
        thr = q(normal, 0.95) if normal else float("inf")    # ≈ 1 falsa alarma cada ~10 ventanas
        caught = sum(1 for p in peaks if p > thr)
        print(f"\n{name}:")
        print(f"  gesto   picos: mín {min(peaks):.2f} · mediana {statistics.median(peaks):.2f} · máx {max(peaks):.2f}")
        if normal:
            print(f"  normal  picos: mediana {statistics.median(normal):.2f} · p90 {q(normal, 0.9):.2f} · máx {max(normal):.2f}  ({len(normal)} ventanas)")
            print(f"  umbral en el p95 del movimiento normal ({thr:.2f}): detecta {caught}/{len(peaks)} gestos")
        if lags:
            print(f"  el pico llega {statistics.median(lags):.0f} ms después del pitido (mediana)")
    print("\nlectura: si 'detecta' es alto (≥ 16/20) con un umbral por encima del movimiento normal, el gesto se ve.")


if __name__ == "__main__":
    main()
