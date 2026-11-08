"""Grabador de dibujos: el dedo índice en el trackpad como esfero, y el reloj a su máxima resolución.

    python tools/draw_recorder.py                     # usa la IP del reloj guardada por el lanzador
    python tools/draw_recorder.py --device 192.168.0.XX
    python tools/draw_recorder.py --no-watch          # solo el trackpad
    python tools/draw_recorder.py --teacher mouse     # el ratón como maestro (clic izquierdo = lápiz)

Lee el trackpad de precisión directo (cada dedo: posición, si toca, Scan Time; ver touchpad.py) y el
reloj directo por sdb, sin el puente: acelerómetro y giroscopio a 5 ms (200 muestras/s, unas 120 lecturas
nuevas) y gravedad a 10 ms. El puente tiene que estar cerrado: el reloj acepta una sola conexión.

En la ventana escribes qué vas a dibujar, pulsas Empezar y dibujas con el dedo índice de la mano del reloj.
Enter pasa al siguiente dibujo (otra etiqueta), Esc termina y guarda. Mientras se graba, el cursor queda
encerrado en el lienzo para que un toque no haga clic en otra ventana.

Con --teacher mouse el maestro es el ratón leído crudo (rawmouse.py: cuentas del sensor sin la aceleración
del puntero, a la tasa del ratón) y el lápiz es el botón izquierdo mantenido; guarda mouse.csv en vez de
touch.csv.

Guarda en recordings/dibujo-AAAAMMDD-HHMMSS/: touch.csv, ACCELERATION.csv, GYROSCOPE.csv, GRAVITY.csv
(t_ms en el reloj de esta laptop, común a todo), labels.jsonl (qué se dibujó y cuándo) y meta.json.
"""
import argparse
import asyncio
import atexit
import csv
import ctypes
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from touchpad import TouchpadReader  # noqa: E402
from rawmouse import MouseReader  # noqa: E402

STREAMS = (("ACCELERATION", "accelerometer", 5), ("GYROSCOPE", "gyroscope", 5), ("GRAVITY", "gravity", 10))
COLORS = ["#58c4dd", "#f0997b", "#5dcaa5", "#ffd166", "#b39ddb", "#f4a6b8", "#9ccc65", "#90caf9"]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def clip_cursor(rect):
    """Encierra el cursor en un rectángulo de pantalla (o lo libera con None)."""
    try:
        ctypes.windll.user32.ClipCursor(ctypes.byref(RECT(*rect)) if rect else None)
    except Exception:
        pass


atexit.register(clip_cursor, None)


class WatchReader:
    """Lee los sensores del reloj directo por sdb en un hilo con su propio bucle asyncio."""

    def __init__(self, host, streams):
        self.host, self.streams = host, streams
        self.rows = {name: [] for name, _, _ in streams}     # (t_reloj_ms, llegada_ms, x, y, z)
        self.counts = {name: 0 for name, _, _ in streams}
        self.state = "conectando…"
        self.recording = False
        self.loop = None
        self.thread = threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True)

    async def _main(self):
        from sdb_client import SdbConnection
        self.loop = asyncio.get_running_loop()
        try:
            self.conn = await SdbConnection(self.host).connect(timeout=20)
        except Exception as e:
            self.state = f"no conecta ({e.__class__.__name__}): ¿el puente sigue abierto? ciérralo"
            return
        await self.conn.run("pkill -INT sensorctl; sleep 0.3; pkill sensorctl")
        self.state = "conectado"
        self._stop = asyncio.Event()
        tasks = [asyncio.create_task(self._read(name, sensor, iv)) for name, sensor, iv in self.streams]
        await self._stop.wait()
        for t in tasks:
            t.cancel()
        try:
            await asyncio.wait_for(self.conn.run("pkill -INT sensorctl; sleep 0.3; pkill sensorctl"), 5)
        except Exception:
            pass
        self.conn.close()
        self.state = "desconectado"

    async def _read(self, name, sensor, interval):
        stream = await self.conn.shell(f"echo 0 | sensorctl test {sensor} --interval={interval}")
        buf = b""
        while True:
            chunk = await stream.queue.get()
            if chunk is None:
                return
            arrival = time.time() * 1000
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for line in lines:
                p = line.split()
                if len(p) == 4 and p[0].isdigit():
                    self.counts[name] += 1
                    if self.recording:
                        self.rows[name].append((int(p[0]) / 1000, arrival, float(p[1]), float(p[2]), float(p[3])))

    def start(self):
        self.thread.start()

    def stop(self):
        if self.loop and hasattr(self, "_stop"):
            self.loop.call_soon_threadsafe(self._stop.set)
            self.thread.join(8)

    def mapped(self):
        """Filas con el reloj del reloj llevado al de la laptop: desfase = mínimo de (llegada − marca), común a
        todos los sensores (comparten reloj), que es el viaje más rápido observado."""
        offs = [a - t for rows in self.rows.values() for t, a, *_ in rows]
        off = min(offs) if offs else 0.0
        return {name: [(t + off, t, x, y, z) for t, _, x, y, z in rows] for name, rows in self.rows.items()}, off


class App:
    def __init__(self, root, args):
        self.root, self.args = root, args
        self.q = queue.Queue()
        self.touch = []                    # eventos del trackpad grabados
        self.recording = False
        self.t_start = None
        self.segments = []                 # {label, t0, t1}
        self.seg = None
        self.last_pt = {}                  # id de dedo -> último punto en el lienzo
        self.touch_count = 0
        self.rate_t = time.time()
        self.rate_touch = self.rate_watch = None

        root.title("GearStream · grabador de dibujos")
        root.geometry("980x780")
        top = ttk.Frame(root); top.pack(fill="x", padx=10, pady=6)
        ttk.Label(top, text="¿Qué vas a dibujar?").pack(side="left")
        self.label_var = tk.StringVar(value="círculo")
        self.entry = ttk.Entry(top, textvariable=self.label_var, width=22)
        self.entry.pack(side="left", padx=6)
        self.btn = ttk.Button(top, text="Empezar", command=self.toggle)
        self.btn.pack(side="left", padx=4)
        ttk.Button(top, text="Siguiente dibujo (Enter)", command=self.next_segment).pack(side="left", padx=4)
        ttk.Button(top, text="Limpiar lienzo", command=self.clear).pack(side="left", padx=4)
        self.status = tk.StringVar(value="arrancando…")
        ttk.Label(root, textvariable=self.status, foreground="#555").pack(anchor="w", padx=12)
        self.canvas = tk.Canvas(root, background="#11151c", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=8)
        self.hint = ttk.Label(root, text="Dibuja con el índice de la mano del reloj. Enter: siguiente dibujo · Esc: terminar y guardar.",
                              foreground="#777")
        self.hint.pack(anchor="w", padx=12, pady=(0, 8))
        root.bind("<Return>", lambda e: self.next_segment())
        root.bind("<Escape>", lambda e: self.finish())
        root.protocol("WM_DELETE_WINDOW", self.finish)

        self.mouse = args.teacher == "mouse"
        self.mpos = [0.0, 0.0]            # posición acumulada del ratón (cuentas)
        self.manchor = [0.0, 0.0]         # dónde estaba al limpiar el lienzo (centro del dibujo)
        self.mdown = False
        self.pad = MouseReader(self.q.put) if self.mouse else TouchpadReader(self.q.put)
        ok = self.pad.start()
        if not ok:
            self.status.set(f"{'ratón' if self.mouse else 'trackpad'}: {self.pad.error}")
        if self.mouse:
            self.hint.configure(text="Escribe con el ratón manteniendo el clic izquierdo. Enter: siguiente dibujo · Esc: terminar y guardar.")
        self.watch = None
        if not args.no_watch:
            self.watch = WatchReader(args.device, STREAMS)
            self.watch.start()
        root.after(30, self.poll)

    # ---------- lienzo ----------
    def to_canvas(self, x, y):
        ext = self.pad.extents or {"x": (0, 1, None), "y": (0, 1, None)}
        (x0, x1, _), (y0, y1, _) = ext["x"], ext["y"]
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        s = min(w / (x1 - x0), h / (y1 - y0))                    # misma escala en x e y: el dibujo no se deforma
        ox, oy = (w - s * (x1 - x0)) / 2, (h - s * (y1 - y0)) / 2
        return ox + s * (x - x0), oy + s * (y - y0)

    def clear(self):
        self.canvas.delete("all")
        self.last_pt.clear()
        if getattr(self, "mouse", False):
            self.manchor = list(self.mpos)

    def mouse_to_canvas(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        s = 0.35                                            # píxeles del lienzo por cuenta del ratón
        return w / 2 + s * (self.mpos[0] - self.manchor[0]), h / 2 + s * (self.mpos[1] - self.manchor[1])

    def color(self):
        return COLORS[len(self.segments) % len(COLORS)]

    # ---------- grabación ----------
    def toggle(self):
        if not self.recording:
            self.recording = True
            self.t_start = time.time() * 1000
            if self.watch:
                self.watch.recording = True
            self.seg = {"label": self.label_var.get().strip() or "sin etiqueta", "t0": self.t_start}
            self.btn.configure(text="Terminar y guardar (Esc)")
            self.clear()
            self.root.update_idletasks()
            c = self.canvas
            clip_cursor((c.winfo_rootx(), c.winfo_rooty(), c.winfo_rootx() + c.winfo_width(), c.winfo_rooty() + c.winfo_height()))
            self.canvas.focus_set()
        else:
            self.finish()

    def next_segment(self):
        if not self.recording:
            return
        t = time.time() * 1000
        self.seg["t1"] = t
        self.segments.append(self.seg)
        self.label_var.set("")
        self.seg = {"label": "sin etiqueta", "t0": t}
        self.clear()
        clip_cursor(None)                                          # para poder escribir la siguiente etiqueta
        self.entry.focus_set()
        self.status.set("escribe qué vas a dibujar ahora y pulsa Enter para seguir")
        self.root.bind("<Return>", lambda e: self.resume_segment())

    def resume_segment(self):
        self.seg["label"] = self.label_var.get().strip() or "sin etiqueta"
        self.seg["t0"] = time.time() * 1000
        self.root.bind("<Return>", lambda e: self.next_segment())
        c = self.canvas
        clip_cursor((c.winfo_rootx(), c.winfo_rooty(), c.winfo_rootx() + c.winfo_width(), c.winfo_rooty() + c.winfo_height()))
        self.canvas.focus_set()

    def finish(self):
        clip_cursor(None)
        if self.recording:
            self.recording = False
            t = time.time() * 1000
            self.seg["t1"] = t
            self.segments.append(self.seg)
            if self.watch:
                self.watch.recording = False
            self.save()
        if self.watch:
            threading.Thread(target=self.watch.stop, daemon=True).start()
        self.pad.stop()
        self.root.after(600, self.root.destroy)

    def save(self):
        out = os.path.join(ROOT, "recordings", f"dibujo-{time.strftime('%Y%m%d-%H%M%S')}")
        os.makedirs(out, exist_ok=True)
        ext = {} if self.mouse else (self.pad.extents or {})
        mmx = (ext["x"][2] / (ext["x"][1] - ext["x"][0])) if ext.get("x") and ext["x"][2] else None
        mmy = (ext["y"][2] / (ext["y"][1] - ext["y"][0])) if ext.get("y") and ext["y"][2] else None
        if self.mouse:
            with open(os.path.join(out, "mouse.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["t_ms", "dev", "dx", "dy", "x", "y", "left", "flags"])
                for ev in self.touch:
                    w.writerow([round(ev["t_ms"], 3), ev["dev"], ev["dx"], ev["dy"], ev["x"], ev["y"], int(ev["left"]), ev["flags"]])
        else:
            with open(os.path.join(out, "touch.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["t_ms", "scan_100us", "contact_count", "contact_id", "tip", "x", "y", "x_mm", "y_mm"])
                for ev in self.touch:
                    for cid, tip, x, y in ev["fingers"]:
                        w.writerow([round(ev["t_ms"], 3), ev["scan"], ev["count"], cid, int(tip), x, y,
                                    round(x * mmx, 4) if mmx else "", round(y * mmy, 4) if mmy else ""])
        rates, offset = {}, None
        if self.watch:
            rows, offset = self.watch.mapped()
            for name, rs in rows.items():
                with open(os.path.join(out, f"{name}.csv"), "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["t_ms", "t_watch_ms", "x", "y", "z"])
                    w.writerows((round(t, 3), round(tw, 3), x, y, z) for t, tw, x, y, z in rs)
                span = (rs[-1][0] - rs[0][0]) / 1000 if len(rs) > 1 else 0
                rates[name] = {"muestras": len(rs), "por_segundo": len(rs) / span if span else 0,
                               "lecturas_nuevas_por_segundo": len(set(r[2:] for r in rs)) / span if span else 0}
        tspan = (self.touch[-1]["t_ms"] - self.touch[0]["t_ms"]) / 1000 if len(self.touch) > 1 else 0
        rates["MOUSE" if self.mouse else "TOUCHPAD"] = {"informes": len(self.touch), "por_segundo": len(self.touch) / tspan if tspan else 0}
        with open(os.path.join(out, "labels.jsonl"), "w", encoding="utf-8") as f:
            for s in self.segments:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"teacher": "mouse" if self.mouse else "trackpad", "touchpad_extents": ext, "mm_per_unit": [mmx, mmy], "watch": None if not self.watch else self.args.device,
                       "watch_offset_ms": offset, "streams": [list(s) for s in STREAMS], "rates": rates}, f, ensure_ascii=False, indent=1)
        print(f"guardado en {out}")
        for k, v in rates.items():
            print(f"  {k}: {v}")

    # ---------- bucle de la interfaz ----------
    def poll(self):
        try:
            while True:
                ev = self.q.get_nowait()
                self.touch_count += 1
                if self.mouse:
                    self.mpos[0] += ev["dx"]; self.mpos[1] += ev["dy"]
                    if ev["down"] is not None:
                        self.mdown = ev["down"]
                    ev["x"], ev["y"], ev["left"] = self.mpos[0], self.mpos[1], self.mdown
                    if self.recording:
                        self.touch.append(ev)
                    p = self.mouse_to_canvas()
                    q = self.last_pt.get("m")
                    if self.mdown:
                        if q:
                            self.canvas.create_line(*q, *p, fill=self.color() if self.recording else "#5a6475", width=3, capstyle="round")
                        self.last_pt["m"] = p
                    else:
                        self.last_pt.pop("m", None)
                    continue
                if self.recording:
                    self.touch.append(ev)
                seen = set()
                for cid, tip, x, y in ev["fingers"]:
                    seen.add(cid)
                    if not tip:
                        self.last_pt.pop(cid, None)
                        continue
                    p = self.to_canvas(x, y)
                    q = self.last_pt.get(cid)
                    if q:
                        self.canvas.create_line(*q, *p, fill=self.color() if self.recording else "#5a6475", width=3, capstyle="round")
                    self.last_pt[cid] = p
                if ev["count"] == 0 and not ev["fingers"]:
                    self.last_pt.clear()
        except queue.Empty:
            pass
        now = time.time()
        if now - self.rate_t >= 1:
            dt = now - self.rate_t
            self.rate_touch = self.touch_count / dt
            self.touch_count = 0
            if self.watch:
                self.rate_watch = {k: v / dt for k, v in self.watch.counts.items()}
                for k in self.watch.counts:
                    self.watch.counts[k] = 0
            self.rate_t = now
            rec = f"● grabando {int((now * 1000 - self.t_start) / 1000)} s · dibujo {len(self.segments) + 1}: «{self.seg['label']}»" if self.recording else "listo para grabar"
            w = "" if not self.watch else (f"reloj: {self.watch.state}" + ("" if not self.rate_watch else
                 " · " + " · ".join(f"{k[:4].lower()} {v:.0f}/s" for k, v in self.rate_watch.items())))
            err = f" · {self.pad.error}" if self.pad.error else ""
            self.status.set(f"{rec} · {'ratón' if self.mouse else 'trackpad'} {self.rate_touch:.0f} informes/s · {w}{err}")
        self.root.after(15, self.poll)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    saved = {}
    for name in ("config.json", "launcher.json"):          # la app guarda la IP en config.json; el lanzador viejo, en launcher.json
        try:
            with open(os.path.join(os.path.expanduser("~"), ".gearstream", name), encoding="utf-8") as f:
                saved = json.load(f)
            if saved.get("watch_ip"):
                break
        except (OSError, ValueError):
            pass
    ap.add_argument("--device", default=saved.get("watch_ip"), help="IP del reloj (por defecto, la del lanzador)")
    ap.add_argument("--no-watch", action="store_true", help="grabar solo el trackpad (o el ratón)")
    ap.add_argument("--teacher", choices=("trackpad", "mouse"), default="trackpad", help="qué da la verdad del trazo")
    ap.add_argument("--selftest", action="store_true", help="abrir, comprobar y cerrar a los 6 s sin grabar")
    args = ap.parse_args()
    if not args.no_watch and not args.device:
        sys.exit("falta la IP del reloj: --device IP (o --no-watch)")
    root = tk.Tk()
    app = App(root, args)
    if args.selftest:
        def done():
            print("estado:", app.status.get())
            print("extensión del trackpad:", getattr(app.pad, "extents", "(modo ratón)"), "· informes del maestro:", app.pad.reports)
            app.finish()
        root.after(6000, done)
    root.mainloop()


if __name__ == "__main__":
    main()
