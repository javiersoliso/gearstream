"""Streams the real watch sensors to server.py WITHOUT installing an app: runs the watch's
built-in `sensorctl` over the debug connection (pure-Python sdb client, no sdb.exe needed) and
re-sends the samples with the same protocol as watch-app. Runs on Windows and on Termux.

Needs: watch with Debugging on and reachable over Wi-Fi, and server.py running.

    python tools/sdb_bridge.py                      # finds the watch on the local network
    python tools/sdb_bridge.py --device 192.168.0.XX
    python tools/sdb_bridge.py --inputs none        # sensors only, exactly as 1.1 did

Heart rate: sensorctl is denied HRM (err -13), so BPM is taken from Samsung Health's log while it
is measuring (~1 Hz). Raw PPG is not available this way.

Bezel and buttons: the debug shell can read `/dev/input/event*`, so the bezel (tizen_detent), the
back button (gpio_keys) and the home/power key (s2mpw02-power-keys) are streamed as BEZEL and
BUTTON samples. The shell runs on a pty that rewrites every 0x0a of cat's binary output unless the
line discipline is raw, hence `stty raw -echo; cat <node>` (measured). Each record is a 16-byte
ARM32 `struct input_event` (sec, usec, type, code, value) decoded here; samples are stamped with
the bridge's wall clock on arrival. Which sign of the bezel means clockwise is not yet confirmed
on the real watch: --bezel-positive sets it and the calibration page checks it.
"""
import argparse
import asyncio
import json
import os
import re
import signal
import struct
import sys
import time

from websockets.asyncio.client import connect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I drops the script dir
from sdb_client import SdbConnection, find_watch  # noqa: E402

VERSION = "1.2"

# sensorctl name -> (GearStream source, field names of the numbers after the timestamp)
SENSORS = {
    "accelerometer": ("ACCELERATION", ["x", "y", "z"]),
    "gyroscope": ("GYROSCOPE", ["x", "y", "z"]),
    "gravity": ("GRAVITY", ["x", "y", "z"]),
    "linear_accel": ("LINEAR_ACCELERATION", ["x", "y", "z"]),
    "pressure": ("PRESSURE", ["pressure", "altitude", "temperature", "pressure2"]),
    "light": ("LIGHT", ["lightLevel"]),
}
# Probed on an SM-R800 (Tizen 4.0): not present, or denied to the debug shell.
UNAVAILABLE = {
    "MAGNETIC": ("unsupported", "el reloj no tiene magnetómetro"),
    "GYROSCOPE_ROTATION_VECTOR": ("unsupported", "no disponible en sensorctl"),
    "HRM_RAW": ("error", "permiso denegado al shell de depuración (requiere app firmada)"),
}
# Samsung Health logs every new BPM like: "ProcessNewExerciseHrData(68) > min 71, 1792904774779,000000"
HR_LINE = re.compile(r"ProcessNewExerciseHrData\(\d+\) > min (\d+), (\d+)")
LOG_BACKLOG_S = 2.0  # dlogutil first dumps its whole buffer; lines arriving this early are old
# The clock anchor is a running minimum of (arrival - sensor time); this tiny leak (≈30 ppm at
# 100 Hz) lets it follow the watch's clock if that runs slow instead of locking in forever.
OFFSET_LEAK_MS = 0.0003
MAX_TS_JUMP_MS = 5000  # a sensor clock never legitimately jumps this much between two lines

# ---------- Bezel and buttons over /dev/input ----------
# One kernel input_event as laid out on this ARM32 watch: sec, usec, type, code, value (16 bytes).
INPUT_EVENT = struct.Struct("<IIHHi")
EV_SYN, EV_KEY, EV_REL, EV_ABS = 0, 1, 2, 3
REL_WHEEL, KEY_BACK, KEY_POWER = 8, 158, 116
READY = b"READY\n"  # echoed by the shell right before cat: whatever precedes it is chatter, not events
# kind -> (device name in /sys/class/input/*/device/name (substring match), node measured on the
#          SM-R800 when the listing is unavailable, GearStream source, BUTTON key)
INPUT_DEVICES = {
    "bezel": ("tizen_detent", "/dev/input/event14", "BEZEL", None),
    "back": ("gpio_keys", "/dev/input/event12", "BUTTON", "back"),
    "home": ("power-keys", "/dev/input/event0", "BUTTON", "home"),  # listed as "s2mpw02-power-keys"
}
KEY_CODES = {"back": KEY_BACK, "home": KEY_POWER}
INPUT_LABELS = {"bezel": "", "back": "atrás", "home": "inicio"}  # prefixes in the BUTTON status detail
INPUT_READY_S = 3.0  # no READY marker within this -> error status
INPUT_READY_MAX = 4096  # bytes of chatter tolerated before READY
INPUT_LIST_CMD = 'for d in /sys/class/input/event*; do echo "$d $(cat $d/device/name 2>/dev/null)"; done'
# SIGINT first: a sensorctl killed outright leaves its listener registered in sensord ("Listener is already
# added"), after which no client gets samples until the watch reboots.
CLEANUP_CMD = "pkill -INT sensorctl; sleep 0.5; pkill sensorctl; pkill awk; pkill dlogutil; pkill -f 'cat /dev/inpu[t]'"


def decode_input_events(buf):
    """Every complete 16-byte input_event at the front of `buf` as (sec, usec, type, code, value)
    tuples, plus the leftover bytes (< 16) to prepend to the next chunk."""
    size = INPUT_EVENT.size
    n = len(buf) - len(buf) % size
    return [INPUT_EVENT.unpack_from(buf, i) for i in range(0, n, size)], buf[n:]


def plausible(etype, code):
    """False for bytes that are text rather than events: an error line from cat decodes to type 0x206e."""
    return etype <= 0x1F and code <= 0x2FF


def input_sample(kind, etype, code, value, bezel_positive="cw"):
    """(source, values) for one event of the `kind` reader, or None when it carries nothing for us:
    SYN separators, the bezel's REL position number, key autorepeat, another device's codes."""
    if kind == "bezel":
        if etype != EV_REL or code != REL_WHEEL or value == 0:
            return None
        # Magnitude grows with speed (±2 seen when turned fast): one sample, `steps` detents.
        clockwise = (value > 0) == (bezel_positive == "cw")
        return "BEZEL", {"direction": "CW" if clockwise else "CCW", "steps": min(abs(value), 10), "raw": value}
    if etype != EV_KEY or code != KEY_CODES[kind] or value not in (0, 1):
        return None
    return "BUTTON", {"key": INPUT_DEVICES[kind][3], "pressed": value == 1}


def resolve_input_nodes(listing, names=None):
    """kind -> /dev/input node from the output of INPUT_LIST_CMD (lines like
    "/sys/class/input/event14 tizen_detent"); kinds not listed keep the measured default. The first
    match wins. `names`, when given, collects the full device name of each kind found."""
    nodes = {kind: dev[1] for kind, dev in INPUT_DEVICES.items()}
    found = set()
    for line in listing.splitlines():
        path, _, name = line.strip().partition(" ")
        name = name.strip()
        m = re.fullmatch(r"/sys/class/input/(event\d+)", path)
        if not m or not name:
            continue
        for kind, (device, *_) in INPUT_DEVICES.items():
            if device in name and kind not in found:
                found.add(kind)
                nodes[kind] = f"/dev/input/{m.group(1)}"
                if names is not None:
                    names[kind] = name
    return nodes


def parse_inputs(text):
    """--inputs value -> tuple of kinds in the given order; 'none' -> (); unknown names raise ValueError."""
    names = [s.strip() for s in text.split(",") if s.strip()]
    if names == ["none"]:
        return ()
    unknown = [n for n in names if n not in INPUT_DEVICES]
    if unknown:
        raise ValueError(f"entradas desconocidas: {', '.join(unknown)}; "
                         f"válidas: {', '.join(INPUT_DEVICES)}, none")
    return tuple(dict.fromkeys(names))


def split_ready(buf):
    """(chatter before READY, bytes after it) once the marker and its line end are complete, else
    None. READY\\r\\n is accepted too, so a failed `stty raw` surfaces as unreadable data instead
    of a timeout."""
    i = buf.find(READY.rstrip(b"\n"))
    if i < 0:
        return None
    rest = buf[i + len(READY) - 1:]
    if rest.startswith(b"\r\n"):
        return buf[:i], rest[2:]
    if rest.startswith(b"\n"):
        return buf[:i], rest[1:]
    return None if len(rest) < 2 else (buf[:i], rest)


def snippet(data, limit=120):
    """The first bytes of a stream as one printable line, for logs and status details."""
    return " ".join(data[:limit].decode(errors="replace").split())


class Bridge:
    def __init__(self, conn, interval, flush_ms, sensors, batch=0, inputs=(), bezel_positive="cw"):
        self.conn = conn
        self.interval = interval
        self.flush_s = flush_ms / 1000
        self.sensors = sensors
        # sdb delivers one packet per stream per network round trip (measured: 0.8 samples/packet),
        # so over a slow link (phone hotspot, ~60 ms) a 100 Hz sensor only gets ~17 samples/s through.
        # Grouping N lines on the watch with awk multiplies the throughput by N at the cost of up to
        # N samples of latency. (sensorctl's own --batch_latency is ignored by this watch.)
        self.batch = batch
        self.inputs = tuple(inputs)
        self.bezel_positive = bezel_positive
        self.buffer = []
        self.latest_ms = 0  # wall-clock-mapped time of the newest sample, for the latency report
        # Every source has its own clock (sensorctl's µs counters differ per sensor; Samsung Health
        # stamps HRM with the watch's epoch time). Map each to wall clock with the SMALLEST
        # (arrival - sensor time) seen, i.e. the fastest delivery: anchoring on the first line
        # would pick the oldest line of sensorctl's startup backlog and under-report by ~100 ms.
        self.offsets_ms = {}
        self.last_ts_ms = {}
        self.counts = {}
        self.input_nodes = {}  # kind -> /dev/input node, resolved from /sys when the listing worked
        self.input_names = {}  # kind -> device name as listed
        self.input_state = {}  # kind -> (state, detail) of its reader
        # Readers never touch the websocket: they queue status dicts here and run() sends them
        # at the next flush, in order with the data.
        self.pending_status = []
        self.closing = False

    def map_time(self, source, ts_ms):
        now_ms = time.time() * 1000
        # sensorctl occasionally emits a stale cached event with a timestamp hours off. Such a jump
        # must not move the anchor (a future one would shift every later sample), so it is stamped
        # with its arrival time and otherwise ignored.
        prev = self.last_ts_ms.get(source)
        if prev is not None and abs(ts_ms - prev) > MAX_TS_JUMP_MS:
            return round(now_ms)
        self.last_ts_ms[source] = ts_ms
        offset = now_ms - ts_ms
        cur = self.offsets_ms.get(source)
        if cur is None or offset < cur:
            self.offsets_ms[source] = offset
        else:
            self.offsets_ms[source] = cur + OFFSET_LEAK_MS
        return round(ts_ms + self.offsets_ms[source])

    def push(self, source, t_ms, values, latency=True):
        # Inputs are stamped on arrival, so they carry no delivery delay: with latency=False they
        # leave latest_ms alone and the "retraso" report keeps measuring the sensors.
        self.buffer.append([source, t_ms, values])
        self.counts[source] = self.counts.get(source, 0) + 1
        if latency and t_ms > self.latest_ms:
            self.latest_ms = t_ms

    async def read_sensor(self, name, source, fields):
        # "echo 0 |" answers the "more than 2 sensors, enter the index" prompt (gravity asks it).
        cmd = f"echo 0 | sensorctl test {name} --interval={self.interval}"
        if self.batch > 1:
            cmd += (f" | awk '{{b=b $0 \"\\n\"; if (NR%{self.batch}==0) {{printf \"%s\", b; fflush(); b=\"\"}}}}'")
        stream = await self.conn.shell(cmd)
        async for line in stream.lines():
            parts = line.split()
            if len(parts) != len(fields) + 1 or not parts[0].isdigit():
                continue
            t_ms = self.map_time(source, int(parts[0]) / 1000)
            self.push(source, t_ms, dict(zip(fields, map(float, parts[1:]))))

    async def read_heart_rate(self):
        stream = await self.conn.shell("dlogutil SHealthServiceCommon")
        started = time.time()
        async for line in stream.lines():
            m = HR_LINE.search(line)
            if m and time.time() - started > LOG_BACKLOG_S:
                self.push("HRM", self.map_time("HRM", int(m.group(2))), {"heartRate": int(m.group(1))})

    # ---------- /dev/input readers ----------

    def input_node(self, kind):
        return self.input_nodes.get(kind, INPUT_DEVICES[kind][1])

    def input_detail(self, kind):
        state, detail = self.input_state.get(kind, ("waiting", ""))
        label = INPUT_LABELS[kind]
        if state == "error":
            return f"{label}: {detail}" if label else detail
        name = self.input_names.get(kind, INPUT_DEVICES[kind][0])
        return f"{label} {self.input_node(kind)} ({name})".strip()

    def input_status_message(self, source):
        """The status of BEZEL or BUTTON from its readers. BUTTON merges back and home: it is on
        while either works and error only when every reader failed, with each failure in the detail."""
        kinds = [k for k in self.inputs if INPUT_DEVICES[k][2] == source]
        states = [self.input_state.get(k, ("waiting", ""))[0] for k in kinds]
        state = "on" if "on" in states else "error" if all(s == "error" for s in states) else "waiting"
        return {"type": "status", "source": source, "state": state,
                "detail": " · ".join(self.input_detail(k) for k in kinds)}

    def set_input_state(self, kind, state, detail=""):
        self.input_state[kind] = (state, detail)
        self.pending_status.append(self.input_status_message(INPUT_DEVICES[kind][2]))

    async def resolve_nodes(self):
        """Finds each input's /dev/input node by device name; the measured nodes when /sys is silent."""
        listing = ""
        try:
            listing = await asyncio.wait_for(self.conn.run(INPUT_LIST_CMD), 10)
        except Exception:
            pass
        if not listing.strip():
            print("no pude listar /sys/class/input: uso los nodos medidos")
        self.input_nodes = resolve_input_nodes(listing, self.input_names)

    async def read_input(self, kind):
        """Streams one /dev/input node and pushes its BEZEL or BUTTON samples, stamped on arrival."""
        source = INPUT_DEVICES[kind][2]
        node = self.input_node(kind)
        # The pty rewrites every 0x0a of cat's binary output unless it is raw (measured), so stty
        # comes first. READY separates the shell's own chatter from the events: raw mode turns
        # output processing off before echo runs, so the marker arrives verbatim.
        try:
            stream = await self.conn.shell(f"stty raw -echo; echo READY; cat {node}")
        except Exception as e:
            self.set_input_state(kind, "error", f"no se pudo abrir {node}: {e}")
            return
        buf = b""
        deadline = time.monotonic() + INPUT_READY_S
        while True:  # 1: wait for the marker; chunks are raw bytes, not lines (0x0a is data here)
            remaining = deadline - time.monotonic()
            try:
                if remaining <= 0:
                    raise TimeoutError
                chunk = await asyncio.wait_for(stream.queue.get(), remaining)
            except TimeoutError:
                seen = f": {snippet(buf)}" if buf.strip() else ""
                self.set_input_state(kind, "error", f"sin respuesta de {node} en {INPUT_READY_S:g} s{seen}")
                return
            if chunk is None:
                self.set_input_state(kind, "error",
                                     f"no se pudo leer {node}: {snippet(buf) or 'el reloj cerró sin responder'}")
                return
            buf += chunk
            parts = split_ready(buf)
            if parts is None:
                if len(buf) > INPUT_READY_MAX:
                    self.set_input_state(kind, "error", f"sin marca READY en {node}: {snippet(buf)}")
                    return
                continue
            chatter, buf = parts
            if chatter.strip():  # e.g. a complaint from stty; cat may still work, so only a warning
                print(f"aviso en {node}: {snippet(chatter)}")
            break
        self.set_input_state(kind, "on")
        seen, count = False, 0
        while True:  # 2: 16-byte events, split at any chunk boundary
            head = buf
            events, buf = decode_input_events(buf)
            for _sec, _usec, etype, code, value in events:
                if not plausible(etype, code):
                    text = snippet(head)
                    if seen:                 # a stray byte mid-stream: every record after it is garbage
                        detail = f"flujo desalineado en {node} tras {count} eventos: {text}"
                    elif text.startswith("cat:"):
                        detail = f"no se pudo leer {node}: {text}"
                    else:
                        detail = f"datos no reconocidos en {node} (¿stty raw falló?): {text}"
                    self.set_input_state(kind, "error", detail)
                    return
                seen = True
                count += 1
                sample = input_sample(kind, etype, code, value, self.bezel_positive)
                if sample is not None:
                    self.push(sample[0], round(time.time() * 1000), sample[1], latency=False)
            chunk = await stream.queue.get()
            if chunk is None:
                break
            buf += chunk
        if not self.closing:
            print(f"{source}: el reloj cerró {node}")
            leftover = f": {snippet(buf)}" if buf and not seen else ""
            self.set_input_state(kind, "error", f"lectura terminada{leftover}")

    # ---------- messages ----------

    def hello_message(self):
        available = [SENSORS[n][0] for n in self.sensors] + ["HRM"]
        if "bezel" in self.inputs:
            available.append("BEZEL")
        if {"back", "home"} & set(self.inputs):
            available.append("BUTTON")
        return {
            "type": "hello", "app": f"sdb-bridge {VERSION}", "t": round(time.time() * 1000),
            "available": available,
            "device": {"model_name": self.conn.model, "transport": "sdb/sensorctl"},
        }

    def status_messages(self):
        msgs = [{"type": "status", "source": SENSORS[n][0], "state": "waiting",
                 "detail": f"sensorctl {self.interval} ms"} for n in self.sensors]
        msgs.append({"type": "status", "source": "HRM", "state": "waiting",
                     "detail": "mide el pulso en Samsung Health"})
        msgs += [{"type": "status", "source": src, "state": state, "detail": detail}
                 for src, (state, detail) in UNAVAILABLE.items()]
        for source in ("BEZEL", "BUTTON"):
            if any(INPUT_DEVICES[k][2] == source for k in self.inputs):
                msgs.append(self.input_status_message(source))
        return msgs

    def data_message(self):
        """The next batch for the server (samples in arrival order), or None when nothing arrived."""
        if not self.buffer:
            return None
        batch, self.buffer = self.buffer, []
        # "t" = this machine's clock at send time: lets the server and the dashboard
        # measure the legs after the bridge exactly (no clock anchoring involved).
        return {"type": "data", "t": round(time.time() * 1000), "samples": batch}

    def report(self):
        rates = ", ".join(f"{k} {v / 5:.1f}" for k, v in sorted(self.counts.items()))
        self.counts.clear()
        parts = [f"Hz: {rates or '(sin datos)'}"]
        if self.latest_ms:
            # Age of the newest sample: everything before this point (watch, Wi-Fi, sdb).
            parts.append(f"retraso {time.time() * 1000 - self.latest_ms:.0f} ms")
        stats = self.conn.stats()
        if stats:
            # sdb sends one packet per stream and waits for our OKAY before the next one, so the
            # round trip sets how many samples pile up per packet. ~1 line/packet = network is fine.
            # With --batch the gap between packets is mostly the time to collect N samples, so the
            # figure is labelled accordingly.
            label = "entre paquetes" if self.batch > 1 else "ida y vuelta"
            parts.append(f"{label} {stats['rtt_min_ms']:.0f}-{stats['rtt_mean_ms']:.0f} ms, "
                         f"{stats['lines_per_packet']:.1f} muestras/paquete")
        print(time.strftime("%H:%M:%S"), " · ".join(parts), flush=True)

    async def run(self, url):
        if self.inputs:
            await self.resolve_nodes()
        async with connect(url, compression=None) as ws:
            print(f"conectado a {url} · reloj {self.conn.model}")
            await ws.send(json.dumps(self.hello_message()))
            for msg in self.status_messages():
                await ws.send(json.dumps(msg))

            readers = [asyncio.create_task(self.read_sensor(n, *SENSORS[n])) for n in self.sensors]
            readers.append(asyncio.create_task(self.read_heart_rate()))
            # Input readers live apart: a bezel node closing must not end the session, and the
            # sensors ending must still end it.
            input_tasks = [asyncio.create_task(self.read_input(k)) for k in self.inputs]
            last_report = time.time()
            try:
                while not all(r.done() for r in readers):
                    await asyncio.sleep(self.flush_s)
                    if self.pending_status:
                        status, self.pending_status = self.pending_status, []
                        for msg in status:
                            await ws.send(json.dumps(msg))
                    msg = self.data_message()
                    if msg:
                        await ws.send(json.dumps(msg))
                    if time.time() - last_report >= 5:
                        self.report()
                        last_report = time.time()
                print("el reloj cerró la conexión")
            finally:
                self.closing = True
                for task in readers + input_tasks:
                    task.cancel()


async def main():
    if hasattr(signal, "SIGBREAK"):   # el lanzador pide parar con Ctrl+Break: limpiar el reloj igual que con Ctrl+C
        task, loop = asyncio.current_task(), asyncio.get_running_loop()
        signal.signal(signal.SIGBREAK, lambda *_: loop.call_soon_threadsafe(task.cancel))
    parser = argparse.ArgumentParser(description="Puente reloj -> GearStream (sin instalar app)")
    parser.add_argument("--device", default="auto",
                        help="IP del reloj (puerto 26101); 'auto' lo busca en la red local")
    parser.add_argument("--url", default="ws://localhost:8765/watch")
    parser.add_argument("--interval", type=int, default=10, help="ms entre muestras (10 = 100 Hz)")
    parser.add_argument("--flush-ms", type=int, default=20,
                        help="cada cuánto se envía un lote al servidor (menor = menos retraso, más paquetes)")
    parser.add_argument("--sensors", default=",".join(SENSORS),
                        help="sensores de sensorctl a leer, separados por coma (menos sensores = menos tráfico)")
    parser.add_argument("--batch", type=int, default=0,
                        help="agrupar N muestras por paquete en el reloj (10 en redes lentas como un hotspot; "
                             "0 = sin agrupar, menor retraso)")
    parser.add_argument("--inputs", default=",".join(INPUT_DEVICES),
                        help="entradas a leer por /dev/input, separadas por coma: bezel (bisel), back (botón "
                             "atrás), home (tecla inicio, abre la lista de apps); 'none' las desactiva")
    parser.add_argument("--bezel-positive", choices=("cw", "ccw"), default="cw",
                        help="sentido del bisel que llega con valor positivo (sin confirmar en el reloj real; "
                             "la página de calibración lo comprueba)")
    args = parser.parse_args()

    sensors = [s.strip() for s in args.sensors.split(",") if s.strip()]
    unknown = [s for s in sensors if s not in SENSORS]
    if unknown:
        parser.error(f"sensores desconocidos: {', '.join(unknown)}; válidos: {', '.join(SENSORS)}")
    try:
        inputs = parse_inputs(args.inputs)
    except ValueError as e:
        parser.error(str(e))

    print(f"GearStream puente {VERSION}")
    if inputs:
        print(f"entradas por /dev/input: {', '.join(inputs)} (bisel positivo = {args.bezel_positive})")
    if args.device == "auto":
        print("buscando el reloj en la red (puerto 26101)...")
        hosts = await find_watch()
        if not hosts:
            print("no encontré ningún reloj. Revisa: Depuración activada, misma Wi-Fi que este equipo, "
                  "Bluetooth del teléfono apagado; o pásame la IP con --device")
            return
        if len(hosts) > 1:
            print(f"varios candidatos: {', '.join(hosts)}; uso el primero")
        host, port = hosts[0], 26101
    else:
        host, _, port = args.device.partition(":")
        port = int(port or 26101)
    print(f"conectando a {host}:{port}")

    while True:  # si el reloj se cae (reinicio, Wi-Fi dormido) se vuelve a conectar solo; Ctrl+C sale
        while True:  # the watch's sdbd drops or refuses connections while its radio wakes up: keep trying
            try:
                conn = await SdbConnection(host, port).connect(timeout=600)  # time to accept the prompt on the watch
                break
            except (OSError, asyncio.TimeoutError) as e:
                print(f"el reloj no responde ({e.__class__.__name__}: {e}); reintento en 3 s (Ctrl+C para salir)")
                await asyncio.sleep(3)
        try:
            await conn.run(CLEANUP_CMD)  # leftovers from a previous session
            await Bridge(conn, args.interval, args.flush_ms, sensors, args.batch,
                         inputs=inputs, bezel_positive=args.bezel_positive).run(args.url)
        except (OSError, asyncio.TimeoutError, ConnectionError) as e:
            print(f"se perdió el reloj ({e.__class__.__name__})")
        finally:
            try:
                await asyncio.wait_for(conn.run(CLEANUP_CMD), 5)
            except Exception:
                pass
            conn.close()
        print("vuelvo a conectar con el reloj en 3 s (Ctrl+C para salir)")
        await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
