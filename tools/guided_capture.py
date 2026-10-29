"""Grabación guiada de un gesto: el programa pita y pide el gesto N veces, luego pide un rato de
movimiento normal sin el gesto. Sirve para averiguar si un gesto (por ejemplo, juntar pulgar e índice)
se distingue en los sensores del reloj y para diseñar su detector.

    python tools/sdb_bridge.py --interval 5 --batch 10 --sensors accelerometer,gyroscope --inputs none
    python tools/guided_capture.py --label pellizco

Lee el mismo canal que el dashboard (ws://localhost:8765/ui), así que el puente y el servidor tienen
que estar corriendo. Con --device IP lee el acelerómetro directo del reloj por sdb, a 200 Hz
(--interval 5): más rápido que por el puente, que a 5 ms no da abasto. Así el puente tiene que estar
parado, porque el reloj solo acepta una conexión. Guarda en recordings/captura-<etiqueta>-<fecha>/: samples.csv (fuente, t_ms, x, y,
z, con t en el reloj de la laptop) y cues.json (instantes de cada pitido y de cada fase). recordings/
no se sube a git: son datos personales.
"""
import argparse
import asyncio
import csv
import json
import os
import sys
import time

try:
    import winsound
except ImportError:          # fuera de Windows no hay pitido; queda el aviso en pantalla
    winsound = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = ("ACCELERATION", "GYROSCOPE", "GRAVITY")


def now_ms():
    return time.time() * 1000


class _null:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


def beep(freq=880, ms=120):
    if winsound:
        winsound.Beep(freq, ms)
    else:
        print("\a", end="", flush=True)


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="ws://localhost:8765/ui")
    ap.add_argument("--label", default="pellizco")
    ap.add_argument("--reps", type=int, default=20, help="cuántas veces se pide el gesto")
    ap.add_argument("--period", type=float, default=2.5, help="segundos entre pitidos")
    ap.add_argument("--rest", type=float, default=25, help="segundos de movimiento normal sin el gesto")
    ap.add_argument("--device", help="IP del reloj: leer el acelerómetro directo por sdb (sin puente)")
    ap.add_argument("--interval", type=int, default=5, help="ms entre muestras con --device")
    args = ap.parse_args()

    samples = []
    if args.device:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from sdb_client import SdbConnection
        conn = await SdbConnection(args.device).connect(timeout=30)
        await conn.run("pkill -INT sensorctl; sleep 0.3; pkill sensorctl")
        stream = await conn.shell(f"echo 0 | sensorctl test accelerometer --interval={args.interval}")
        raw_rows, offset = [], [None]       # (t_reloj_ms, x, y, z); reloj del reloj → laptop: mínimo de (llegada − marca)

        async def sdb_reader():
            buf = b""
            while True:
                chunk = await stream.queue.get()
                if chunk is None:
                    return
                arrival = now_ms()
                buf += chunk
                *lines, buf = buf.split(b"\n")
                last = None
                for line in lines:
                    p = line.split()
                    if len(p) == 4 and p[0].isdigit():
                        last = int(p[0]) / 1000
                        raw_rows.append((last, float(p[1]), float(p[2]), float(p[3])))
                if last is not None:
                    d = arrival - last
                    offset[0] = d if offset[0] is None else min(offset[0], d)
                    while raw_rows[len(samples):]:
                        r = raw_rows[len(samples)]
                        samples.append(("ACCELERATION", r[0], r[1], r[2], r[3]))
        task = asyncio.create_task(sdb_reader())
    else:
        conn = None
    from websockets.asyncio.client import connect
    async with (connect(args.url, max_size=None) if not args.device else _null()) as ws:
        async def reader():
            if ws is None:
                return
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if msg.get("type") != "data":
                    continue
                for s in msg.get("samples", []):
                    if isinstance(s, list) and len(s) >= 3 and s[0] in SOURCES and isinstance(s[2], dict):
                        v = s[2]
                        samples.append((s[0], s[1], v.get("x"), v.get("y"), v.get("z")))
        if not args.device:
            task = asyncio.create_task(reader())

        print(f"""
=== Grabación guiada: {args.label} ===
0. En el reloj: Ajustes > Pantalla > Tiempo de espera, ponlo en 5 minutos, y toca la pantalla para
   encenderla. Con la pantalla apagada el reloj frena los sensores (de 200 a unas 45 muestras/s).
1. Ponte el reloj en la muñeca izquierda y levanta la mano como si apuntaras con el ratón aéreo.
2. Cada vez que oigas el pitido y veas  >>> {args.label.upper()} <<<, haz el gesto UNA vez:
   junta pulgar e índice de la mano del reloj en un toque seco y suelta. Sin mover el brazo.
3. Son {args.reps} pitidos, uno cada {args.period:g} s. Después te pido {args.rest:g} s de movimiento normal.
""")
        want = 0.75 * 1000 / args.interval if args.device else 1
        while True:
            await asyncio.to_thread(input, "Pulsa Enter cuando estés listo… ")
            n0 = len(samples)
            await asyncio.sleep(1.0)
            rate = len(samples) - n0
            if rate >= want:
                print(f"   llegan {rate} muestras/s: bien", flush=True)
                break
            if rate == 0:
                print("   no llega nada del reloj: ¿corren el servidor y el puente (o está bien la IP)?", flush=True)
            else:
                print(f"   solo llegan {rate} muestras/s: la pantalla del reloj está apagada. Tócala y pulsa Enter otra vez.", flush=True)
        for n in (3, 2, 1):
            print(f"   {n}…", flush=True)
            await asyncio.sleep(1)
        cues, phases = [], {}
        phases["gesto"] = [now_ms(), None]
        for i in range(1, args.reps + 1):
            t = now_ms()
            cues.append(t)
            print(f"   >>> {args.label.upper()} <<<   ({i}/{args.reps})", flush=True)
            await asyncio.to_thread(beep)
            await asyncio.sleep(max(0.0, args.period - (now_ms() - t) / 1000))
        phases["gesto"][1] = now_ms()

        print(f"""
Ahora NO hagas el gesto durante {args.rest:g} s. Muévete normal: apunta como con el ratón, gira la
muñeca, deja caer el brazo y vuelve a subirlo, aprieta el puño, mueve los dedos, teclea con la otra mano.
""", flush=True)
        await asyncio.to_thread(beep, 440, 300)
        phases["normal"] = [now_ms(), None]
        left = args.rest
        while left > 0:
            print(f"   quedan {left:.0f} s", flush=True)
            await asyncio.sleep(min(5, left))
            left -= 5
        phases["normal"][1] = now_ms()
        await asyncio.to_thread(beep, 660, 300)
        await asyncio.sleep(0.5)
        task.cancel()
    if conn is not None:
        await conn.run("pkill -INT sensorctl; sleep 0.3; pkill sensorctl")
        conn.close()
        off = offset[0] or 0.0                # marcas del reloj → reloj de la laptop
        samples[:] = [(s[0], s[1] + off, s[2], s[3], s[4]) for s in samples]

    out = os.path.join(ROOT, "recordings", f"captura-{args.label}-{time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "samples.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "t_ms", "x", "y", "z"])
        w.writerows(samples)
    with open(os.path.join(out, "cues.json"), "w") as f:
        json.dump({"label": args.label, "cues_ms": cues, "phases_ms": phases, "period_s": args.period}, f, indent=1)
    n = {src: sum(1 for s in samples if s[0] == src) for src in SOURCES}
    print(f"\nListo: {len(cues)} gestos y {args.rest:g} s de movimiento normal.")
    print(f"muestras: " + ", ".join(f"{k} {v}" for k, v in n.items() if v))
    print(f"guardado en {out}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\ncancelado")
        sys.exit(1)
