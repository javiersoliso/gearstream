"""Tutorial de grabación del dataset de gestos, en la consola. Una línea por paso: mientras se muestra,
se graba; al terminar pasa solo al siguiente.

    python tools/dataset_capture.py              # todos los pasos (unos 5 minutos)
    python tools/dataset_capture.py --from puno  # seguir desde un paso
    python tools/dataset_capture.py --only pinza2,pinza2_doble

Necesita el servidor y el puente corriendo (el lanzador: Conectar). El servidor ya graba todo lo que
llega del reloj; este programa le manda una etiqueta por paso (qué gesto, de cuándo a cuándo y el
instante de cada pitido), que queda en labels.jsonl junto a los CSV de la sesión. Los pasos están en
server/web/gestures-protocol.json, compartidos con la versión web (http://localhost:8765/dataset.html).
Ctrl+C para en cualquier momento; lo ya grabado queda guardado.
"""
import argparse
import asyncio
import json
import os
import sys
import time

try:
    import winsound
except ImportError:
    winsound = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTOCOL_FILE = os.path.join(ROOT, "server", "web", "gestures-protocol.json")


def beep(freq=880, ms=90):
    if winsound:
        winsound.Beep(freq, ms)
    else:
        print("\a", end="", flush=True)


def now_ms():
    return round(time.time() * 1000)


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="ws://localhost:8765/ui")
    ap.add_argument("--from", dest="start", help="empezar en este paso (id)")
    ap.add_argument("--only", help="solo estos pasos, separados por comas")
    args = ap.parse_args()
    with open(PROTOCOL_FILE, encoding="utf-8") as f:
        proto = json.load(f)
    steps = proto["steps"]
    ids = [s["id"] for s in steps]
    if args.start:
        if args.start not in ids:
            sys.exit(f"paso desconocido: {args.start} (hay: {', '.join(ids)})")
        steps = steps[ids.index(args.start):]
    if args.only:
        want = args.only.split(",")
        steps = [s for s in steps if s["id"] in want]
    prep = proto.get("prep_s", 3)

    from websockets.asyncio.client import connect
    counts, acks = {}, []
    async with connect(args.url, max_size=None) as ws:
        async def reader():
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if msg.get("type") == "data":
                    for s in msg.get("samples", []):
                        if isinstance(s, list) and s:
                            counts[s[0]] = counts.get(s[0], 0) + 1
                elif msg.get("type") == "label_ack":
                    acks.append(msg.get("dir"))
        task = asyncio.create_task(reader())

        async def rates(secs=1.0):
            counts.clear()
            await asyncio.sleep(secs)
            return {k: v / secs for k, v in counts.items()}

        async def label(**kw):
            await ws.send(json.dumps({"type": "label", "protocol": proto["protocol"], **kw}))

        hz = await rates()
        acc = hz.get("ACCELERATION", 0)
        print(f"\n=== Dataset de gestos: {len(steps)} pasos, unos {sum(s.get('secs') or s['cues']['n'] * s['cues']['period'] for s in steps) / 60 + len(steps) * prep / 60:.0f} min ===")
        print(f"llegando: acelerómetro {acc:.0f} Hz, giroscopio {hz.get('GYROSCOPE', 0):.0f} Hz, gravedad {hz.get('GRAVITY', 0):.0f} Hz")
        if acc < 1:
            print("no llega nada del reloj: conecta el reloj en el lanzador (Conectar) y vuelve a empezar")
            task.cancel()
            return
        if acc < 70:
            print("pocas muestras: toca la pantalla del reloj para encenderla")
        print("Reloj en la muñeca izquierda, pantalla encendida, ratón aéreo apagado.\n")
        await asyncio.to_thread(input, "Pulsa Enter para empezar… ")
        await label(id=f"inicio-{now_ms()}", step="_inicio", t0=now_ms(), t1=now_ms(), steps=steps, origen="consola")

        for k, st in enumerate(steps, 1):
            print(f"\n[{k}/{len(steps)}]  {st['line']}")
            for c in range(prep, 0, -1):
                print(f"   prepárate… {c}", end="\r", flush=True)
                await asyncio.sleep(1)
            print("   ● grabando        ", flush=True)
            await asyncio.to_thread(beep, 440, 200)
            t0, cues = now_ms(), []
            if "cues" in st:
                n, period = st["cues"]["n"], st["cues"]["period"]
                await asyncio.sleep(0.3)
                for i in range(n):
                    t = now_ms()
                    cues.append(t)
                    print(f"   >>> ¡ahora! ({i + 1}/{n})", end="\r", flush=True)
                    await asyncio.to_thread(beep)
                    await asyncio.sleep(max(0.0, period - (now_ms() - t) / 1000))
                print()
            elif st.get("metronome"):
                half = 0.5 / st["metronome"]          # un pitido arriba (agudo) y otro abajo (grave)
                end, up = time.time() + st["secs"], True
                while time.time() < end:
                    t = time.time()
                    print(f"   {'▲ arriba' if up else '▼ abajo '}", end="\r", flush=True)
                    await asyncio.to_thread(beep, 990 if up else 520, 60)
                    up = not up
                    await asyncio.sleep(max(0.0, half - (time.time() - t)))
                print()
            else:
                end = time.time() + st["secs"]
                while time.time() < end:
                    print(f"   quedan {end - time.time():4.0f} s", end="\r", flush=True)
                    await asyncio.sleep(0.5)
                print()
            await label(id=f"{st['id']}-{k}", step=st["id"], line=st["line"], trial=k, t0=t0, t1=now_ms(),
                        cues_ms=cues, metronome_hz=st.get("metronome"), hz=await rates(0.2))
            await asyncio.to_thread(beep, 660, 120)
            print("   ✓ guardado")
        await label(id=f"fin-{now_ms()}", step="_fin", t0=now_ms(), t1=now_ms())
        await asyncio.sleep(0.5)
        task.cancel()
    where = acks[-1] if acks else "(el servidor no confirmó)"
    print(f"\n¡Dataset grabado! {len(steps)} pasos etiquetados en {where}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nparado; lo grabado hasta aquí queda guardado")
