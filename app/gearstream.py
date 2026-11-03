"""GearStream: la app. Una ventana, y un ícono en la bandeja, para conectar el reloj y usarlo sin comandos.

    GearStream.exe                      la ventana          (desde el código: python app/gearstream.py)
    GearStream.exe servidor [...]       el servidor de las páginas y los datos (server/server.py)
    GearStream.exe puente [...]         el puente con el reloj (tools/sdb_bridge.py)
    GearStream.exe raton [...]          el ratón aéreo (tools/air_mouse.py)
    GearStream.exe reloj-simulado       un reloj de mentira, para probar sin reloj (tools/fake_watch.py)
    GearStream.exe prueba               prueba de punta a punta sin ventana: servidor + reloj simulado + páginas

Cada pieza corre en su propio proceso: el mismo ejecutable con un subcomando. Así se pueden parar con
Ctrl+Break, que el puente y el ratón atienden para dejar limpio el reloj (un sensorctl cortado de golpe traba
el servicio de sensores del reloj hasta reiniciarlo).

Ajustes en ~/.gearstream/config.json (o en la pestaña Ajustes). Tus datos (grabaciones, dibujos, tomas) en la
carpeta de datos, por defecto Documentos/GearStream: nunca en la carpeta donde se instaló la app.
"""
import asyncio
import json
import os
import queue
import re
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parent.parent
FROZEN = getattr(sys, "frozen", False)
RES = Path(getattr(sys, "_MEIPASS", ROOT / "app"))      # el ícono: junto a este archivo, o dentro del ejecutable
WIN = sys.platform == "win32"
HOME = Path.home() / ".gearstream"
CONFIG = HOME / "config.json"
DEFAULTS = {
    "watch_ip": "",
    "hand": "left",                 # muñeca del reloj: left | right (en la derecha el antebrazo es −x)
    "port": 8765,
    "batch": "auto",                # muestras por paquete: auto (mide la red) | 0 | 2..10
    "data_dir": str(Path.home() / "Documents" / "GearStream"),
    "tray": True,                   # cerrar la ventana la deja en la bandeja
    "lan": False,                   # el servidor solo en esta laptop (el puente corre aquí); True: abierto a tu Wi-Fi
    "open_on_connect": "",          # página que se abre sola al llegar los datos ("" = ninguna)
    "wizard_done": False,
}
PAGES = [                           # nombre, archivo, para qué sirve (mocap, avatar, dataset y el curso siguen
                                    # en el servidor, solo no van en el menú)
    ("Dibuja", "dibuja.html", "dibuja en 1D, 2D o 3D"),
    ("Sismógrafo", "sismo.html", "juego: sigue la línea"),
    ("Globos", "game.html", "juego: empuja para lanzar"),
    ("Tornillo", "tempo.html", "giros de muñeca y tempo"),
    ("Calibración", "calibrate.html", "ajusta el ratón aéreo"),
    ("Sensores", "", "todos los sensores en vivo"),
]
SUBCOMMANDS = ("servidor", "puente", "raton", "reloj-simulado")
if not FROZEN:                      # desde el código, las piezas viven en server/ y tools/
    sys.path[:0] = [str(ROOT / "server"), str(ROOT / "tools")]


# ---------- ajustes ----------
def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        try:                        # el lanzador viejo (tools/launcher.py) guardaba la IP aquí
            cfg["watch_ip"] = json.loads((HOME / "launcher.json").read_text(encoding="utf-8")).get("watch_ip", "")
        except (OSError, ValueError):
            pass
    return cfg


def save_config(cfg):
    try:
        HOME.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# ---------- red ----------
def wifi_name():
    """La Wi-Fi conectada (netsh en Windows), o None."""
    if not WIN:
        return None
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=5, creationflags=subprocess.CREATE_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        m = re.match(r"\s*SSID\s*:\s*(.+)$", line)          # "BSSID" no encaja: el patrón empieza en SSID
        if m:
            return m.group(1).strip()
    return None


def ping_ms(host, n=3):
    """Mediana del ida y vuelta con el ping del sistema, o None si no responde."""
    args = ["ping", "-n" if WIN else "-c", str(n), "-w" if WIN else "-W", "1000" if WIN else "1", host]
    try:
        out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                             creationflags=subprocess.CREATE_NO_WINDOW if WIN else 0).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    times = [float(x) for x in re.findall(r"(?:tiempo|time)[=<]\s*([\d.]+)\s*ms", out, re.I)]
    return statistics.median(times) if times else None


def port_open(host, port, timeout=0.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------- las piezas, cada una en su proceso ----------
class Child:
    """Un proceso hijo (servidor, puente, ratón, reloj simulado) con su salida mandada al registro."""

    def __init__(self, name, sub, args, log, data_dir):
        self.name, self.log = name, log
        me = [sys.executable] if FROZEN else [sys.executable, str(Path(__file__).resolve())]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", GEARSTREAM_DATA=str(data_dir))
        flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if WIN else 0
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen([*me, sub, *args], cwd=str(data_dir), env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                     errors="replace", creationflags=flags)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.log(self.name, line.rstrip())
        self.log(self.name, f"(terminó, código {self.proc.wait()})")

    def alive(self):
        return self.proc.poll() is None

    def stop(self, timeout=8):
        """Ctrl+Break primero (el puente y el ratón limpian al recibirlo); a la fuerza si no responde."""
        if not self.alive():
            return
        try:
            self.proc.send_signal(signal.CTRL_BREAK_EVENT if WIN else signal.SIGINT)
            self.proc.wait(timeout)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()


def utf8_streams():
    """Las piezas imprimen ° · → …: salida en UTF-8 aunque Windows diga otra cosa (y a un archivo si no hay a dónde)."""
    for name in ("stdout", "stderr"):
        s = getattr(sys, name)
        if s is None:               # ejecutable sin consola y sin tubería
            HOME.mkdir(parents=True, exist_ok=True)
            setattr(sys, name, open(HOME / "gearstream.log", "a", encoding="utf-8", buffering=1))
        else:
            try:
                s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (AttributeError, ValueError):
                pass


def run_tool(sub, argv):
    """Corre una pieza en este proceso, como si fuera su propio script."""
    utf8_streams()
    sys.argv = [sub, *argv]
    if sub == "reloj-simulado":
        import fake_watch
        fake_watch.main()
        return
    if sub == "servidor":
        import server as mod
    elif sub == "puente":
        import sdb_bridge as mod
    else:
        import air_mouse as mod
    try:
        asyncio.run(mod.main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except Exception:               # sin consola, un error suelto abre una ventana que deja la pieza colgada
        import traceback
        traceback.print_exc()       # la salida va al Registro de la app
        sys.exit(1)


# ---------- la prueba de punta a punta ----------
def self_test():
    """Servidor + reloj simulado en un puerto aparte: las páginas responden y los datos llegan a una página."""
    utf8_streams()
    port, lines = 8799, []
    data = Path(tempfile.mkdtemp(prefix="gearstream-prueba-"))
    log = lambda who, text: lines.append(f"[{who}] {text}")      # noqa: E731
    srv = Child("servidor", "servidor", ["--host", "127.0.0.1", "--port", str(port), "--out", str(data / "recordings")], log, data)
    for _ in range(50):
        if port_open("127.0.0.1", port):
            break
        time.sleep(0.2)
    fake = Child("reloj", "reloj-simulado", ["--url", f"ws://127.0.0.1:{port}/watch"], log, data)
    report, ok = [], True
    for page in ("", "mocap.html", "dibuja.html", "vendor/three.min.js", "wrist.js", "curso-protocol.json", "stickdemo.js"):
        try:
            code = urllib.request.urlopen(f"http://127.0.0.1:{port}/{page}", timeout=5).status
        except OSError as e:
            code = str(e)
        report.append(f"página /{page}: {code}")
        ok &= code == 200

    async def count(seconds=2.5):
        from websockets.asyncio.client import connect
        n = 0
        async with connect(f"ws://127.0.0.1:{port}/ui") as ws:
            end = time.time() + seconds
            while time.time() < end:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=end - time.time()))
                except (asyncio.TimeoutError, ValueError):
                    break
                if msg.get("type") == "data":
                    n += len(msg.get("samples", []))
        return n / seconds
    time.sleep(1.0)
    try:
        rate = asyncio.run(count())
    except Exception as e:          # la prueba informa, no revienta
        rate, ok = 0, False
        report.append(f"datos: error {e}")
    report.append(f"datos del reloj simulado en una página: {rate:.0f} muestras/s")
    ok &= rate > 100
    fake.stop(); srv.stop()
    text = ("PRUEBA OK" if ok else "PRUEBA FALLÓ") + f" · GearStream {VERSION}\n" + "\n".join(report) + "\n\n" + "\n".join(lines[-40:])
    print(text)
    HOME.mkdir(parents=True, exist_ok=True)
    (HOME / "prueba.txt").write_text(text, encoding="utf-8")
    return 0 if ok else 1


# ---------- la ventana ----------
SINGLE_PORT = 47615                 # una sola app abierta: la primera escucha aquí, solo en esta laptop


def claim_single_instance():
    """El socket que marca que esta es la app abierta, o None si ya hay otra: a esa le pide que se muestre.
    Dos apps a la vez abren dos puentes y el reloj solo acepta una conexión de depuración: cierra la segunda."""
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", SINGLE_PORT))
    except OSError:
        lock.close()
        try:
            with socket.create_connection(("127.0.0.1", SINGLE_PORT), timeout=2) as c:
                c.sendall(b"show\n")
        except OSError:
            pass
        return None
    lock.listen(4)
    return lock


def run_app():
    lock = claim_single_instance()
    if lock is None:
        return
    import tkinter as tk
    from tkinter import filedialog, ttk

    from sdb_client import find_watch, local_ipv4s

    class App:
        def __init__(self, root):
            self.root, self.cfg = root, load_config()
            self.children, self.lines = {}, queue.Queue()
            self.rate = None                  # muestras por segundo que reporta el puente
            self.tray = None
            root.title("GearStream")
            root.geometry("720x620")
            root.minsize(620, 540)
            try:
                root.iconphoto(True, tk.PhotoImage(file=str(RES / "icon.png")))
            except tk.TclError:
                pass
            style = ttk.Style()
            style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
            style.configure("Sub.TLabel", foreground="#666")
            style.configure("Page.TButton", padding=(6, 8))

            head = ttk.Frame(root, padding=(14, 12, 14, 4))
            head.pack(fill="x")
            ttk.Label(head, text="GearStream", style="Title.TLabel").pack(side="left")
            ttk.Label(head, text="  tu reloj como sensor de movimiento", style="Sub.TLabel").pack(side="left", pady=(8, 0))
            self.state_var = tk.StringVar(value="● servidor apagado   ● reloj sin conectar")
            ttk.Label(head, textvariable=self.state_var, style="Sub.TLabel").pack(side="right", pady=(8, 0))

            tabs = ttk.Notebook(root)
            tabs.pack(fill="both", expand=True, padx=10, pady=6)
            self.tab_home(ttk.Frame(tabs, padding=10), tabs)
            self.tab_settings(ttk.Frame(tabs, padding=12), tabs)
            self.tab_log(ttk.Frame(tabs, padding=8), tabs)

            foot = ttk.Frame(root, padding=(12, 0, 12, 10))
            foot.pack(fill="x")
            ttk.Label(foot, text=f"versión {VERSION} · ajustes en {CONFIG}", style="Sub.TLabel").pack(side="left")
            ttk.Button(foot, text="Detener todo", command=self.stop_all).pack(side="right")

            root.protocol("WM_DELETE_WINDOW", self.close_window)
            root.after(150, self.drain)
            root.after(1000, self.tick)
            threading.Thread(target=self.detect_network, daemon=True).start()
            self.start_tray()
            if not self.cfg.get("wizard_done"):
                root.after(400, self.wizard)

        # ---------- pestañas ----------
        def tab_home(self, f, tabs):
            tabs.add(f, text="Inicio")
            watch = ttk.LabelFrame(f, text="Reloj", padding=10)
            watch.pack(fill="x")
            self.net_var = tk.StringVar(value="mirando la red…")
            ttk.Label(watch, textvariable=self.net_var, style="Sub.TLabel").pack(anchor="w")
            row = ttk.Frame(watch)
            row.pack(fill="x", pady=8)
            ttk.Label(row, text="IP del reloj").pack(side="left")
            self.ip_var = tk.StringVar(value=self.cfg.get("watch_ip", ""))
            entry = ttk.Entry(row, textvariable=self.ip_var, width=18)
            entry.pack(side="left", padx=6)
            entry.bind("<Return>", lambda e: self.connect())
            self.find_btn = ttk.Button(row, text="Buscar en la red", command=self.find)
            self.find_btn.pack(side="left", padx=3)
            self.conn_btn = ttk.Button(row, text="Conectar", command=self.toggle_connect)
            self.conn_btn.pack(side="left", padx=3)
            self.status_var = tk.StringVar(value="La IP sale en el reloj: Ajustes → Conexiones → Wi-Fi → tu red.")
            ttk.Label(watch, textvariable=self.status_var, wraplength=640).pack(anchor="w")
            row2 = ttk.Frame(watch)
            row2.pack(fill="x", pady=(8, 0))
            ttk.Button(row2, text="Primera vez: paso a paso", command=self.wizard).pack(side="left")
            self.sim_btn = ttk.Button(row2, text="Probar sin reloj", command=self.toggle_sim)
            self.sim_btn.pack(side="left", padx=6)

            use = ttk.LabelFrame(f, text="Usar", padding=10)
            use.pack(fill="both", expand=True, pady=(10, 0))
            grid = ttk.Frame(use)
            grid.pack(fill="x")
            for i, (name, page, what) in enumerate(PAGES):
                ttk.Button(grid, text=f"{name}\n{what}", style="Page.TButton", command=lambda p=page: self.open_page(p)).grid(
                    row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
            for c in range(3):
                grid.columnconfigure(c, weight=1)
            mouse = ttk.Frame(use)
            mouse.pack(fill="x", pady=(10, 0))
            self.mouse_btn = ttk.Button(mouse, text="Ratón aéreo: encender", command=self.toggle_mouse)
            self.mouse_btn.pack(side="left")
            ttk.Label(mouse, text="  apoya la muñeca 2 s para calibrar; la esquina superior izquierda 1.5 s lo apaga",
                      style="Sub.TLabel").pack(side="left")

        def tab_settings(self, f, tabs):
            tabs.add(f, text="Ajustes")
            c = self.cfg
            self.hand_var = tk.StringVar(value=c["hand"])
            self.batch_var = tk.StringVar(value=str(c["batch"]))
            self.port_var = tk.StringVar(value=str(c["port"]))
            self.dir_var = tk.StringVar(value=c["data_dir"])
            self.tray_var = tk.BooleanVar(value=bool(c["tray"]))
            self.lan_var = tk.BooleanVar(value=bool(c.get("lan")))
            names = ["(ninguna)"] + [n for n, _, _ in PAGES]
            first = next((n for n, p, _ in PAGES if p == c["open_on_connect"] and c["open_on_connect"]), "(ninguna)")
            self.open_var = tk.StringVar(value=first)

            def row(label, widget, note=""):
                r = ttk.Frame(f)
                r.pack(fill="x", pady=6)
                ttk.Label(r, text=label, width=22).pack(side="left")
                widget(r).pack(side="left")
                if note:
                    ttk.Label(f, text=note, style="Sub.TLabel", wraplength=640).pack(anchor="w", padx=(4, 0))

            def hand(r):
                fr = ttk.Frame(r)
                ttk.Radiobutton(fr, text="izquierda", value="left", variable=self.hand_var, command=self.save_settings).pack(side="left")
                ttk.Radiobutton(fr, text="derecha", value="right", variable=self.hand_var, command=self.save_settings).pack(side="left", padx=8)
                return fr
            row("Muñeca del reloj", hand, "Con el reloj puesto normal, en la derecha el antebrazo es el −x del reloj: "
                                           "el ratón aéreo y las páginas se ajustan solos.")
            row("Muestras por paquete", lambda r: ttk.Combobox(r, textvariable=self.batch_var, width=8, state="readonly",
                                                               values=["auto", "0", "2", "4", "6", "8"]),
                "auto mide la red: en el hotspot del teléfono agrupa varias muestras por paquete para llegar a 100 Hz.")
            row("Puerto del servidor", lambda r: ttk.Spinbox(r, textvariable=self.port_var, from_=1024, to=65535, width=8))

            def folder(r):
                fr = ttk.Frame(r)
                ttk.Entry(fr, textvariable=self.dir_var, width=44).pack(side="left")
                ttk.Button(fr, text="Cambiar…", command=self.pick_dir).pack(side="left", padx=4)
                ttk.Button(fr, text="Abrir", command=lambda: self.open_path(self.dir_var.get())).pack(side="left")
                return fr
            row("Carpeta de tus datos", folder, "Grabaciones, dibujos y tomas del mocap. Son tus datos: no se suben a ningún lado.")
            row("Abrir al conectar", lambda r: ttk.Combobox(r, textvariable=self.open_var, values=names, width=16, state="readonly"))
            row("Al cerrar la ventana", lambda r: ttk.Checkbutton(r, text="seguir en la bandeja", variable=self.tray_var))
            row("Red", lambda r: ttk.Checkbutton(r, text="abrir el servidor a tu Wi-Fi", variable=self.lan_var),
                "Apagado, solo esta laptop habla con el servidor: el reloj llega por el puente, que corre aquí. Préndelo solo "
                "para la app del teléfono o del reloj, y solo en redes de confianza: quien esté en tu Wi-Fi podría ver tus "
                "sensores. Se aplica al volver a arrancar el servidor (Detener todo).")
            bar = ttk.Frame(f)
            bar.pack(fill="x", pady=(16, 0))
            ttk.Button(bar, text="Guardar", command=self.save_settings).pack(side="left")
            ttk.Button(bar, text="Abrir el archivo de ajustes", command=lambda: self.open_path(CONFIG)).pack(side="left", padx=6)
            self.saved_var = tk.StringVar()
            ttk.Label(bar, textvariable=self.saved_var, style="Sub.TLabel").pack(side="left", padx=6)

        def tab_log(self, f, tabs):
            tabs.add(f, text="Registro")
            self.log_box = tk.Text(f, height=10, wrap="word", font=("Consolas", 9), state="disabled")
            self.log_box.pack(fill="both", expand=True)
            ttk.Button(f, text="Copiar todo", command=self.copy_log).pack(anchor="e", pady=(6, 0))

        # ---------- ajustes ----------
        def save_settings(self):
            c = self.cfg
            c["hand"] = self.hand_var.get()
            c["batch"] = self.batch_var.get()
            try:
                c["port"] = max(1024, min(65535, int(self.port_var.get())))
            except ValueError:
                self.port_var.set(str(c["port"]))
            c["data_dir"] = self.dir_var.get().strip() or DEFAULTS["data_dir"]
            c["tray"] = bool(self.tray_var.get())
            c["lan"] = bool(self.lan_var.get())
            c["open_on_connect"] = next((p for n, p, _ in PAGES if n == self.open_var.get()), "")
            save_config(c)
            self.saved_var.set("guardado")
            self.root.after(1800, lambda: self.saved_var.set(""))

        def pick_dir(self):
            d = filedialog.askdirectory(initialdir=self.dir_var.get() or str(Path.home()))
            if d:
                self.dir_var.set(d)
                self.save_settings()

        def open_path(self, path):
            p = Path(path)
            if p.suffix == "":
                p.mkdir(parents=True, exist_ok=True)
            elif not p.exists():
                save_config(self.cfg)
            if WIN:
                os.startfile(str(p))                                   # noqa: S606 (abrir con la app del sistema)
            else:
                webbrowser.open(p.as_uri())

        # ---------- registro y estado ----------
        def log(self, who, text):
            self.lines.put(f"{time.strftime('%H:%M:%S')} [{who}] {text}")

        def drain(self):
            new = []
            while True:
                try:
                    new.append(self.lines.get_nowait())
                except queue.Empty:
                    break
            if new:
                self.log_box.configure(state="normal")
                self.log_box.insert("end", "\n".join(new) + "\n")
                n = int(self.log_box.index("end-1c").split(".")[0])
                if n > 600:
                    self.log_box.delete("1.0", f"{n - 600}.0")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
                for line in new:
                    self.read_bridge(line)
            self.root.after(150, self.drain)

        def read_bridge(self, line):
            if "[puente]" not in line and "[reloj simulado]" not in line:
                return
            text = line.split("] ", 1)[-1]
            if "conectado a ws://" in text:
                self.set_status("Conectado. Si no llegan datos, toca la pantalla del reloj: apagada, frena el Wi-Fi.")
            elif " Hz: " in text:
                m = re.search(r"GYROSCOPE ([\d.]+)", text)
                first = self.rate is None
                self.rate = float(m.group(1)) if m else self.rate
                self.set_status(text)
                if first and self.cfg.get("open_on_connect"):
                    self.open_page(self.cfg["open_on_connect"])
            elif "no responde" in text or "se perdió" in text:
                self.rate = None
                self.set_status("El reloj no responde: ¿depuración activada, misma Wi-Fi, Bluetooth del teléfono apagado?")

        def tick(self):
            srv = port_open("127.0.0.1", self.cfg["port"], 0.2)
            bridge = self.children.get("puente") or self.children.get("reloj simulado")
            watch = (f"● reloj {self.rate:.0f} Hz" if self.rate else "● reloj conectando…") if bridge and bridge.alive() else "● reloj sin conectar"
            self.state_var.set(f"{'● servidor listo' if srv else '● servidor apagado'}   {watch}")
            self.conn_btn.configure(text="Desconectar" if self.children.get("puente") and self.children["puente"].alive() else "Conectar")
            m = self.children.get("ratón")
            if m and not m.alive():         # se cerró solo: el botón no puede seguir diciendo "apagar"
                self.children.pop("ratón")
                self.set_status("El ratón aéreo se cerró: mira la pestaña Registro.")
            self.mouse_btn.configure(text="Ratón aéreo: apagar" if "ratón" in self.children else "Ratón aéreo: encender")
            self.root.after(1000, self.tick)

        def set_status(self, text):
            self.root.after(0, self.status_var.set, text)

        def copy_log(self):
            self.root.clipboard_clear()
            self.root.clipboard_append(self.log_box.get("1.0", "end"))

        # ---------- reloj ----------
        def detect_network(self):
            ssid, ips = wifi_name(), local_ipv4s()
            text = f"Esta laptop: Wi-Fi {ssid or 'no detectada'} · IP {', '.join(ips) or 'sin IP'}"
            self.root.after(0, self.net_var.set, text)
            self.log("red", text)

        def find(self):
            self.find_btn.configure(state="disabled")
            self.set_status("Buscando relojes con la depuración activada en la red (unos segundos)…")

            def work():
                try:
                    hosts = asyncio.run(find_watch())
                except Exception as e:                # una red rara no debe tumbar la ventana
                    hosts = []
                    self.log("buscar", f"error: {e}")
                if hosts:
                    self.root.after(0, self.ip_var.set, hosts[0])
                    self.set_status(f"Encontrado: {', '.join(hosts)}. Pulsa Conectar.")
                else:
                    self.set_status("No lo encontré (en el hotspot del teléfono pasa). Escribe la IP que sale en el reloj: "
                                    "Ajustes → Conexiones → Wi-Fi → tu red.")
                self.root.after(0, lambda: self.find_btn.configure(state="normal"))
            threading.Thread(target=work, daemon=True).start()

        def ensure_server(self):
            port = self.cfg["port"]
            if port_open("127.0.0.1", port):
                return True
            data = Path(self.cfg["data_dir"])
            host = "0.0.0.0" if self.cfg.get("lan") else "127.0.0.1"   # en tu red solo si lo pides en Ajustes
            self.children["servidor"] = Child("servidor", "servidor", ["--host", host, "--port", str(port), "--out", str(data / "recordings")], self.log, data)
            for _ in range(40):
                if port_open("127.0.0.1", port):
                    return True
                time.sleep(0.2)
            self.set_status("El servidor no arrancó: mira la pestaña Registro.")
            return False

        def toggle_connect(self):
            p = self.children.get("puente")
            if p and p.alive():
                self.children.pop("puente")
                self.rate = None
                threading.Thread(target=p.stop, daemon=True).start()
                self.set_status("Desconectado.")
            else:
                self.connect()

        def connect(self):
            ip = self.ip_var.get().strip()
            if not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}(:\d+)?", ip):
                self.set_status("Escribe una IP como 192.168.1.50 (sale en el reloj: Ajustes → Conexiones → Wi-Fi).")
                return
            self.cfg["watch_ip"] = ip
            save_config(self.cfg)
            self.conn_btn.configure(state="disabled")
            self.set_status(f"Midiendo la red hacia {ip}…")

            def work():
                if self.ensure_server():
                    for key in ("puente", "reloj simulado"):
                        old = self.children.pop(key, None)
                        if old:
                            old.stop()
                    batch = self.cfg["batch"]
                    if batch == "auto":
                        rtt = ping_ms(ip.split(":")[0])
                        batch = 6 if rtt is not None and rtt > 15 else 0
                        self.log("red", ("sin respuesta al ping" if rtt is None else f"ida y vuelta {rtt:.0f} ms")
                                 + (f": red lenta, agrupo {batch} muestras por paquete" if batch else ": red rápida, sin agrupar"))
                    args = ["--device", ip, "--flush-ms", "10", "--sensors", "accelerometer,gyroscope,gravity",
                            "--url", f"ws://localhost:{self.cfg['port']}/watch"]
                    if int(batch):
                        args += ["--batch", str(batch)]
                    self.rate = None
                    self.children["puente"] = Child("puente", "puente", args, self.log, Path(self.cfg["data_dir"]))
                    self.set_status(f"Conectando con el reloj en {ip}… si el reloj pregunta por la depuración, acepta.")
                self.root.after(0, lambda: self.conn_btn.configure(state="normal"))
            threading.Thread(target=work, daemon=True).start()

        def toggle_sim(self):
            s = self.children.get("reloj simulado")
            if s and s.alive():
                self.children.pop("reloj simulado")
                threading.Thread(target=s.stop, daemon=True).start()
                self.sim_btn.configure(text="Probar sin reloj")
                self.rate = None
                return

            def work():
                if self.ensure_server():
                    self.children["reloj simulado"] = Child("reloj simulado", "reloj-simulado",
                                                            ["--url", f"ws://localhost:{self.cfg['port']}/watch"], self.log,
                                                            Path(self.cfg["data_dir"]))
                    self.rate = 100.0
                    self.set_status("Reloj simulado: datos de mentira para explorar las páginas sin reloj.")
                    self.root.after(0, lambda: self.sim_btn.configure(text="Parar el reloj simulado"))
            threading.Thread(target=work, daemon=True).start()

        # ---------- usar ----------
        def open_page(self, page):
            def work():
                if self.ensure_server():
                    mano = "derecha" if self.cfg["hand"] == "right" else "izquierda"
                    sep = "&" if "?" in page else "?"           # el curso ya trae ?protocolo=curso
                    webbrowser.open(f"http://localhost:{self.cfg['port']}/{page}{sep}mano={mano}")
            threading.Thread(target=work, daemon=True).start()

        def toggle_mouse(self):
            m = self.children.get("ratón")
            if m and m.alive():
                self.children.pop("ratón")
                threading.Thread(target=m.stop, daemon=True).start()
                self.mouse_btn.configure(text="Ratón aéreo: encender")
                return
            if not port_open("127.0.0.1", self.cfg["port"]):
                self.set_status("Primero conecta el reloj (o prueba sin reloj).")
                return
            forearm = "-x" if self.cfg["hand"] == "right" else "+x"
            gestures = ["--click", "button+flick", "--scroll", "roll"] + (["--scroll-invert"] if self.cfg["hand"] == "right" else [])
            self.children["ratón"] = Child("ratón", "raton", [f"--forearm={forearm}", *gestures, "--url", f"ws://localhost:{self.cfg['port']}/ui"],
                                           self.log, Path(self.cfg["data_dir"]))
            self.mouse_btn.configure(text="Ratón aéreo: apagar")
            self.set_status("Ratón aéreo encendido: apoya la muñeca 2 s para calibrar. Clic: gira rápido el antebrazo "
                            "(o el botón). Scroll: gira despacio y mantén (o el bisel).")

        def stop_all(self, then=None):
            kids = [self.children.pop(k) for k in ("ratón", "puente", "reloj simulado", "servidor") if k in self.children]
            self.mouse_btn.configure(text="Ratón aéreo: encender")
            self.sim_btn.configure(text="Probar sin reloj")
            self.rate = None

            def work():
                for c in kids:
                    c.stop()
                self.log("app", "todo detenido")
                if then:
                    self.root.after(0, then)
            threading.Thread(target=work, daemon=True).start()

        # ---------- primera vez ----------
        def wizard(self):
            w = tk.Toplevel(self.root)
            w.title("Primera vez")
            w.geometry("600x520")
            w.transient(self.root)
            steps = [
                ("Misma Wi-Fi", "Pon el reloj en la misma red que esta laptop: Ajustes → Conexiones → Wi-Fi."),
                ("Modo desarrollador", "En el reloj: Ajustes → Acerca del reloj → Software → toca «Versión de software» 5 veces."),
                ("Depuración", "Luego: Ajustes → Acerca del reloj → Depuración → actívala."),
                ("La IP del reloj", "Pulsa «Buscar en la red» o escribe la IP que sale en el reloj (Wi-Fi → tu red → detalles)."),
                ("Conectar", "Pulsa Conectar y acepta en el reloj el aviso de depuración. Si Windows pregunta por el firewall, "
                             "permite redes privadas."),
                ("Si no llegan datos", "Toca la pantalla del reloj (apagada frena el Wi-Fi) y apaga el Bluetooth del teléfono: "
                                       "si no, el reloj manda todo por el teléfono."),
            ]
            for i, (title, text) in enumerate(steps, 1):
                fr = ttk.Frame(w, padding=(14, 8, 14, 0))
                fr.pack(fill="x")
                ttk.Label(fr, text=f"{i}. {title}", font=("Segoe UI", 11, "bold")).pack(anchor="w")
                ttk.Label(fr, text=text, wraplength=560, style="Sub.TLabel").pack(anchor="w")
                if i == 1:                         # la red de la laptop, que se detecta mientras tanto
                    ttk.Label(fr, textvariable=self.net_var, wraplength=560).pack(anchor="w")
            bar = ttk.Frame(w, padding=14)
            bar.pack(fill="x", side="bottom")
            ttk.Button(bar, text="Buscar en la red", command=self.find).pack(side="left")
            ttk.Button(bar, text="Conectar", command=self.connect).pack(side="left", padx=6)
            ttk.Button(bar, text="Probar sin reloj", command=self.toggle_sim).pack(side="left")

            def done():
                self.cfg["wizard_done"] = True
                save_config(self.cfg)
                w.destroy()
            ttk.Button(bar, text="Listo", command=done).pack(side="right")
            w.protocol("WM_DELETE_WINDOW", done)

        # ---------- bandeja ----------
        def start_tray(self):
            try:
                import pystray
                from PIL import Image
            except ImportError:                      # sin pystray (desde el código): solo la ventana
                return
            ui = lambda f: (lambda icon, item: self.root.after(0, f))   # noqa: E731 (todo cambio, en el hilo de la ventana)
            menu = pystray.Menu(
                pystray.MenuItem("Abrir GearStream", ui(self.show_window), default=True),
                pystray.MenuItem(lambda item: "Desconectar el reloj" if self.children.get("puente") else "Conectar el reloj",
                                 ui(self.toggle_connect)),
                pystray.MenuItem("Ratón aéreo", ui(self.toggle_mouse), checked=lambda item: "ratón" in self.children),
                pystray.Menu.SEPARATOR,
                *[pystray.MenuItem(n, ui(lambda p=p: self.open_page(p))) for n, p, _ in PAGES[:3]],
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir", ui(self.quit)),
            )
            self.tray = pystray.Icon("GearStream", Image.open(RES / "icon.png"), "GearStream", menu)
            self.tray.run_detached()

        def show_window(self):
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

        def close_window(self):
            if self.tray and self.cfg.get("tray", True):
                self.root.withdraw()
                if not getattr(self, "_told", False):
                    self._told = True
                    try:
                        self.tray.notify("GearStream sigue en la bandeja: el reloj y el ratón aéreo siguen andando.", "GearStream")
                    except Exception:
                        pass
            else:
                self.quit()

        def quit(self):
            if self.tray:
                self.tray.stop()
            self.stop_all(then=self.root.destroy)

    def serve_show(app):                # otra app que se abrió pide esta ventana al frente
        while True:
            try:
                c, _ = lock.accept()
            except OSError:
                return
            with c:
                if c.recv(16).startswith(b"show"):
                    app.root.after(0, app.show_window)

    root = tk.Tk()
    app = App(root)
    threading.Thread(target=serve_show, args=(app,), daemon=True).start()
    root.mainloop()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in SUBCOMMANDS:
        run_tool(sys.argv[1], sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "prueba":
        sys.exit(self_test())
    else:
        run_app()


if __name__ == "__main__":
    main()
