"""Measures how many samples per second actually get through the sdb link and whether grouping
samples on the watch helps. Run it from the machine that can reach the watch (on a phone hotspot
that is the phone itself: hotspot clients cannot see each other).

    python tools/batch_test.py --device 192.168.0.XX

sdb delivers one packet per stream per round trip, so on a slow link a 100 Hz sensor only gets
~1000/RTT_ms samples/s through unless each packet carries several. The modes compared:
  normal              sensorctl as the bridge runs it today
  batch_latency=100   ask the sensor stack to deliver samples in 100 ms bursts
  dd obs=460          group sensorctl's output into ~10-line blocks (if dd exists on the watch)
  awk cada 10         same idea with awk (if awk exists on the watch)
"""
import argparse
import asyncio
import time

from sdb_client import SdbConnection

MODES = [
    ("normal", "echo 0 | sensorctl test accelerometer --interval=10"),
    ("batch_latency=100", "echo 0 | sensorctl test accelerometer --interval=10 --batch_latency=100"),
    ("dd obs=460", "echo 0 | sensorctl test accelerometer --interval=10 | dd obs=460 2>/dev/null"),
    ("awk cada 10", "echo 0 | sensorctl test accelerometer --interval=10 | "
                    "awk '{b=b $0 \"\\n\"; if (NR%10==0) {printf \"%s\", b; fflush(); b=\"\"}}'"),
]


async def measure(conn, label, cmd, seconds):
    await conn.run("pkill sensorctl; pkill dd; pkill awk")
    await asyncio.sleep(0.3)
    stream = await conn.shell(cmd)
    conn.stats()  # reset the round-trip counters
    t0 = time.time()
    lines = 0
    first = last = None
    stats = {}
    try:
        while time.time() - t0 < seconds:
            try:
                chunk = await asyncio.wait_for(stream.queue.get(), 1.0)
            except asyncio.TimeoutError:
                continue
            if chunk is None:
                break
            for raw in chunk.split(b"\n"):
                parts = raw.split()
                if len(parts) == 4 and parts[0].isdigit():
                    lines += 1
                    ts = int(parts[0]) / 1000
                    if first is None:
                        first = ts
                    last = ts
        stats = conn.stats() or {}  # before the kill: a closed stream drops out of the statistics
    finally:
        await conn.run("pkill sensorctl; pkill dd; pkill awk")
    rate = lines / seconds
    covered = (last - first) / 1000 if first is not None and last else 0.0
    rtt = (f"{stats['rtt_min_ms']:.0f}-{stats['rtt_mean_ms']:.0f} ms" if stats else "?")
    per_packet = f"{stats['lines_per_packet']:.1f}" if stats else "?"
    print(f"[{label:>18}] {rate:5.0f} muestras/s · cubren {covered:4.1f} s de {seconds} s · "
          f"ida y vuelta {rtt} · {per_packet} muestras/paquete", flush=True)
    return rate


async def main():
    parser = argparse.ArgumentParser(description="Prueba de agrupamiento de muestras por sdb")
    parser.add_argument("--device", required=True, help="IP del reloj")
    parser.add_argument("--seconds", type=int, default=6, help="duración de cada modo")
    args = parser.parse_args()

    host, _, port = args.device.partition(":")
    try:
        conn = await SdbConnection(host, int(port or 26101)).connect(timeout=120)
    except (OSError, asyncio.TimeoutError) as e:
        print(f"no pude conectar con {host}: {type(e).__name__}. Revisa que el reloj esté despierto, con "
              f"Depuración activada, en la misma red que este equipo y con esa IP (Ajustes > Conexiones > Wi-Fi).")
        return
    print(f"conectado a {conn.model}; midiendo {len(MODES)} modos, ~{args.seconds + 1} s cada uno", flush=True)
    results = {}
    try:
        for label, cmd in MODES:
            results[label] = await measure(conn, label, cmd, args.seconds)
    finally:
        conn.close()
    good = [label for label, rate in results.items() if rate >= 90]
    if good:
        print("llegan los 100 Hz con:", ", ".join(good))
    else:
        print("ningún modo llega a 100 Hz en esta red")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
