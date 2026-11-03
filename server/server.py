"""GearStream server: receives the watch stream, records it to CSV and relays it to the dashboard.

  ws://<ip>:8765/watch  <- the watch (or tools/fake_watch.py) connects here
  ws://<ip>:8765/ui     <- the dashboard connects here
  http://<ip>:8765/     -> dashboard (server/web)
  http://<ip>:8765/dibujos/          -> lista de los dibujos guardados (JSON)
  http://<ip>:8765/dibujos/<nombre>  -> un dibujo (JSON Lines, ver server/web/trazos.js)
  http://<ip>:8765/grabaciones/index.json, /grabaciones/<id>.json -> tomas para el mocap (tools/export_mocap.py)
"""
import argparse
import asyncio
import base64
import csv
import json
import logging
import re
import socket
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

from websockets.asyncio.server import broadcast, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

ROOT = Path(__file__).resolve().parent
WEB_DIR = Path(getattr(sys, "_MEIPASS", ROOT)) / "web"   # empaquetado (app/gearstream.py), las páginas van dentro
DRAW_DIR = ROOT.parent / "recordings" / "dibujos"   # main() lo cambia con --out
DRAW_ID = re.compile(r"^\d{8}-\d{6}$")
DRAW_NAME = re.compile(r"^dibujo-\d{8}-\d{6}\.jsonl$")
TAKE_DIR = ROOT.parent / "recordings" / "mocap"        # main() lo cambia con --out
TAKE_NAME = re.compile(r"^[A-Za-z0-9_-]+\.json$")
CAPT_DIR = ROOT.parent / "recordings" / "capturas"    # cuadros que una página manda para armar un GIF o video
CAPT_NAME = re.compile(r"^[a-z0-9-]{1,40}$")
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


# Port scanners and HEAD probes otherwise print a full traceback per connection.
logging.getLogger("websockets.server").addFilter(lambda r: r.getMessage() != "opening handshake failed")


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def flatten(values, prefix=""):
    out = {}
    for key, value in values.items():
        name = prefix + key
        if isinstance(value, dict):
            out.update(flatten(value, name + "."))
        elif isinstance(value, list):
            out[name] = json.dumps(value, separators=(",", ":"))
        else:
            out[name] = value
    return out


class Recorder:
    """One folder per session, one CSV per source; columns are fixed by the first sample."""

    def __init__(self, root):
        self.root = root
        self.dir = None
        self.files = {}
        self.meta_file = None
        self.labels_file = None

    def _ensure_dir(self):
        if self.dir is None:
            self.dir = self.root / time.strftime("%Y%m%d-%H%M%S")
            self.dir.mkdir(parents=True, exist_ok=True)
            self.meta_file = open(self.dir / "meta.jsonl", "a", encoding="utf-8")
            log(f"grabando en {self.dir}")

    def meta(self, msg):
        if self.root is None:
            return
        self._ensure_dir()
        self.meta_file.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def label(self, msg):
        """Una etiqueta del tutorial de dataset (qué gesto, de cuándo a cuándo) junto a los datos de la sesión."""
        if self.root is None:
            return None
        self._ensure_dir()
        if self.labels_file is None:
            self.labels_file = open(self.dir / "labels.jsonl", "a", encoding="utf-8")
        self.labels_file.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.labels_file.flush()
        return str(self.dir)

    def sample(self, source, t_watch, t_recv, values):
        if self.root is None:
            return
        self._ensure_dir()
        entry = self.files.get(source)
        flat = flatten(values) if isinstance(values, dict) else {"value": values}
        if entry is None:
            fields = list(flat)
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", source)
            fh = open(self.dir / f"{safe}.csv", "w", newline="", encoding="utf-8")
            writer = csv.writer(fh)
            writer.writerow(["t_watch_ms", "t_recv_ms", *fields])
            entry = self.files[source] = (fh, writer, fields)
        _, writer, fields = entry
        writer.writerow([t_watch, round(t_recv), *(flat.get(f, "") for f in fields)])

    def flush(self):
        for fh, _, _ in self.files.values():
            fh.flush()
        if self.meta_file:
            self.meta_file.flush()

    def close(self):
        for fh, _, _ in self.files.values():
            fh.close()
        if self.meta_file:
            self.meta_file.close()
        if self.labels_file:
            self.labels_file.close()


class Drawings:
    """Los dibujos de Dibuja: cada página manda sus operaciones en lotes numerados y aquí se añaden a
    recordings/dibujos/dibujo-<id>.jsonl. El número de lote evita duplicados si un lote se reenvía."""

    def __init__(self):
        self.seq = {}

    def append(self, msg):
        did, seq, lines = msg.get("id"), msg.get("seq"), msg.get("lines")
        if not (isinstance(did, str) and DRAW_ID.match(did) and isinstance(seq, int) and isinstance(lines, list)):
            return False
        if seq <= self.seq.get(did, -1):
            return True                     # ya escrito: solo confirmar
        DRAW_DIR.mkdir(parents=True, exist_ok=True)
        with open(DRAW_DIR / f"dibujo-{did}.jsonl", "a", encoding="utf-8") as f:
            for line in lines:
                if isinstance(line, dict):
                    f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.seq[did] = seq
        return True


class Hub:
    def __init__(self, recorder, watch_urls):
        self.recorder = recorder
        self.drawings = Drawings()
        self.watch_urls = watch_urls
        self.watches = set()
        self.uis = set()
        self.hello = None
        self.status = {}
        self.counts = Counter()
        self.lag_ms = None  # t_recv - t_watch of the newest sample: latency up to this process
        self.bridge_lag_ms = None  # t_recv - batch send time: just the bridge -> server leg

    async def handle(self, ws):
        path = ws.request.path.split("?", 1)[0]
        if path == "/watch":
            await self.handle_watch(ws)
        elif path == "/ui":
            await self.handle_ui(ws)
        else:
            await ws.close(1008, "unknown path")

    async def handle_watch(self, ws):
        peer = ws.remote_address[0]
        self.watches.add(ws)
        log(f"reloj conectado desde {peer}")
        broadcast(self.uis, json.dumps({"type": "watch", "connected": True, "peer": peer}))
        try:
            async for raw in ws:
                t_recv = time.time() * 1000
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                kind = msg.get("type")
                if kind == "hello":
                    self.hello = msg
                    self.status = {}
                    self.recorder.meta(msg)
                    model = msg.get("device", {}).get("model_name", "?")
                    log(f"hello: {model}, sensores disponibles: {', '.join(msg.get('available', []))}")
                elif kind == "status":
                    self.status[msg.get("source")] = msg
                    self.recorder.meta(msg)
                    if msg.get("state") in ("error", "unsupported"):
                        log(f"  {msg.get('source')}: {msg.get('state')} {msg.get('detail', '')}")
                elif kind == "data":
                    for source, t_watch, values in msg.get("samples", []):
                        self.counts[source] += 1
                        self.recorder.sample(source, t_watch, t_recv, values)
                        self.lag_ms = t_recv - t_watch
                    if "t" in msg:
                        self.bridge_lag_ms = t_recv - msg["t"]
                broadcast(self.uis, raw)
        except ConnectionClosed:
            pass  # the watch/bridge dropped (Wi-Fi, Ctrl-C); not an error worth a traceback
        finally:
            self.watches.discard(ws)
            log(f"reloj desconectado ({peer})")
            broadcast(self.uis, json.dumps({"type": "watch", "connected": bool(self.watches)}))

    async def handle_ui(self, ws):
        self.uis.add(ws)
        try:
            await ws.send(json.dumps({"type": "server", "watchUrls": self.watch_urls}))
            await ws.send(json.dumps({"type": "watch", "connected": bool(self.watches)}))
            if self.hello:
                await ws.send(json.dumps(self.hello))
            for st in list(self.status.values()):
                await ws.send(json.dumps(st))
            async for raw in ws:          # el dataset manda etiquetas y Dibuja sus trazos; el resto solo escucha
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("type") == "captura" and len(raw) < 6 * 2**20:
                    name, seq = msg.get("nombre"), msg.get("seq")
                    if isinstance(name, str) and CAPT_NAME.match(name) and isinstance(seq, int) and 0 <= seq < 100000:
                        folder = CAPT_DIR / name
                        folder.mkdir(parents=True, exist_ok=True)
                        (folder / f"{seq:05d}.jpg").write_bytes(base64.b64decode(msg.get("jpg", "")))
                        await ws.send(json.dumps({"type": "captura_ack", "seq": seq}))
                    continue
                if isinstance(msg, dict) and msg.get("type") == "dibujo" and len(raw) < 4 * 2**20:
                    if self.drawings.append(msg):
                        await ws.send(json.dumps({"type": "dibujo_ack", "id": msg["id"], "seq": msg["seq"]}))
                    continue
                if isinstance(msg, dict) and msg.get("type") == "label" and len(raw) < 65536:
                    msg["t_server_ms"] = round(time.time() * 1000)
                    where = self.recorder.label(msg)
                    await ws.send(json.dumps({"type": "label_ack", "id": msg.get("id"), "dir": where}))
        except ConnectionClosed:
            pass
        finally:
            self.uis.discard(ws)

    async def report(self, every=5):
        while True:
            await asyncio.sleep(every)
            self.recorder.flush()
            if self.counts:
                rates = ", ".join(f"{k} {v / every:.0f}" for k, v in sorted(self.counts.items()))
                bridge = f" (puente→servidor {self.bridge_lag_ms:.0f} ms)" if self.bridge_lag_ms is not None else ""
                log(f"Hz: {rates} · retraso {self.lag_ms:.0f} ms{bridge}")
                self.counts.clear()


# Quién puede hablar con el servidor. Host: solo pedidos dirigidos a esta laptop (más tu red si la abres con
# --host 0.0.0.0); otro nombre es una página que se hace pasar por localhost (DNS rebinding). Origin: si quien
# llama es un navegador, la página tiene que venir de esos mismos hosts; si no, cualquier página abierta en tu
# navegador podría leer tus sensores o escribir en tu carpeta (los navegadores dejan abrir WebSockets a otros
# sitios). Sin Origin es un programa (el puente, el ratón aéreo, la app del reloj), no un navegador.
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}    # main() suma las IP de tu red si la abres
REFUSED = Counter()


def host_of(value, url=False):
    """El nombre de máquina, en minúsculas, de un Host ("localhost:8765") o de un Origin ("http://localhost:8765")."""
    try:
        return urllib.parse.urlsplit(value if url else "//" + value).hostname
    except ValueError:
        return None


def refuse(request):
    """Por qué no atender esta petición, o None."""
    host = request.headers.get("Host", "")
    if host_of(host) not in ALLOWED_HOSTS:
        return f"Host {host!r}"
    origin = request.headers.get("Origin")
    if origin is not None and host_of(origin, url=True) not in ALLOWED_HOSTS:
        return f"Origin {origin!r}"
    return None


def serve_static(connection, request):
    why = refuse(request)
    if why:
        REFUSED[why] += 1
        if REFUSED[why] <= 3:                     # avisa, sin llenar el registro si insiste
            log(f"rechazado {request.path}: {why}")
        return connection.respond(403, "Forbidden\n")
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None
    path = request.path.split("?", 1)[0]
    if path == "/":
        path = "/index.html"
    ctype = None
    if path == "/dibujos/":
        files = sorted(DRAW_DIR.glob("dibujo-*.jsonl"), reverse=True) if DRAW_DIR.is_dir() else []
        body = json.dumps([{"name": f.name, "bytes": f.stat().st_size, "mtime": round(f.stat().st_mtime * 1000)}
                           for f in files]).encode()
        ctype = CONTENT_TYPES[".json"]
    elif path.startswith("/grabaciones/"):
        name = path[len("/grabaciones/"):]
        if not TAKE_NAME.match(name) or not (TAKE_DIR / name).is_file():
            return connection.respond(404, "Not found\n")
        body, ctype = (TAKE_DIR / name).read_bytes(), CONTENT_TYPES[".json"]
    elif path.startswith("/dibujos/"):
        name = path[len("/dibujos/"):]
        if not DRAW_NAME.match(name) or not (DRAW_DIR / name).is_file():
            return connection.respond(404, "Not found\n")
        body, ctype = (DRAW_DIR / name).read_bytes(), "application/x-ndjson; charset=utf-8"
    else:
        file = (WEB_DIR / path.lstrip("/")).resolve()
        if WEB_DIR not in file.parents or not file.is_file():
            return connection.respond(404, "Not found\n")
        body = file.read_bytes()
        ctype = CONTENT_TYPES.get(file.suffix, "application/octet-stream")
    headers = Headers([
        ("Content-Type", ctype),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("Connection", "close"),
    ])
    return Response(200, "OK", headers, body)


def lan_ips():
    ips = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # no envía nada; solo elige la interfaz de salida
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


async def main():
    parser = argparse.ArgumentParser(description="GearStream server")
    parser.add_argument("--host", default="0.0.0.0",
                        help="0.0.0.0 abre a tu red (la app del teléfono o del reloj); 127.0.0.1, solo esta laptop")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--out", default=str(ROOT.parent / "recordings"), help="carpeta de grabaciones")
    parser.add_argument("--no-record", action="store_true", help="no guardar CSV")
    args = parser.parse_args()

    global DRAW_DIR, TAKE_DIR, CAPT_DIR
    DRAW_DIR = Path(args.out) / "dibujos"      # los dibujos se guardan aunque no se graben los CSV
    TAKE_DIR = Path(args.out) / "mocap"
    CAPT_DIR = Path(args.out) / "capturas"
    recorder = Recorder(None if args.no_record else Path(args.out))
    local = host_of(args.host) in ("localhost", "127.0.0.1", "::1")
    if args.host in ("0.0.0.0", "::", ""):         # abierto a tu red: también atiende pedidos a tus IP y a tu nombre
        ALLOWED_HOSTS.update(lan_ips(), {socket.gethostname().lower()})
    elif not local:
        ALLOWED_HOSTS.add(host_of(args.host))
    watch_urls = [] if local else [f"ws://{ip}:{args.port}/watch" for ip in lan_ips()]
    hub = Hub(recorder, watch_urls)
    try:
        async with serve(hub.handle, args.host, args.port, process_request=serve_static,
                         compression=None, max_size=8 * 2**20, ping_interval=20, ping_timeout=20):
            log(f"GearStream escuchando en el puerto {args.port}")
            log(f"  dashboard: http://localhost:{args.port}/")
            if local:
                log("  solo esta laptop: para la app del teléfono o del reloj, ábrelo a tu red (--host 0.0.0.0)")
            else:
                log("  abierto a tu red: quien esté en tu Wi-Fi puede ver tus sensores; úsalo solo en redes de confianza")
            for url in watch_urls:
                log(f"  URL para el reloj: {url}")
            await hub.report()
    finally:
        recorder.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
