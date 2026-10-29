"""Lanzador de GearStream: una ventana para conectar el reloj sin escribir comandos.

    python tools/launcher.py

Muestra en qué red Wi-Fi está la laptop y su IP, busca el reloj en esa red (o usa la IP que escribas:
en el hotspot del teléfono la búsqueda a veces no lo ve aunque la conexión directa funcione), arranca el
servidor y el puente, y abre el juego, el avatar, el dashboard o el ratón aéreo con un botón.

Elige solo cómo agrupar las muestras: mide el ida y vuelta con ping y, si la red es lenta (el hotspot),
agrupa varias muestras por paquete para llegar a 100 Hz. Para el puente y el ratón con Ctrl+Break, que
ambos atienden para limpiar el reloj antes de salir (un sensorctl cortado de golpe puede dejar trabado el
servicio de sensores del reloj hasta reiniciarlo).
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
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from sdb_client import find_watch, local_ipv4s  # noqa: E402

SETTINGS = os.path.join(os.path.expanduser("~"), ".gearstream", "launcher.json")
WIN = sys.platform == "win32"
PAGES = {"Dibuja": "dibuja.html", "Juego": "game.html", "Tornillo": "tempo.html", "Dataset": "dataset.html", "Avatar": "avatar.html", "Dashboard": "", "Calibración": "calibrate.html"}


def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
    except OSError:
        pass


def wifi_name():
    """SSID de la Wi-Fi conectada (netsh en Windows), o None."""
    if not WIN:
        return None
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=5,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        m = re.match(r"\s*SSID\s*:\s*(.+)$", line)          # "BSSID" no encaja: el patrón empieza en SSID
        if m:
            return m.group(1).strip()
    return None


def ping_ms(host, n=3):
    """Mediana del ida y vuelta en ms con ping del sistema, o None si no responde."""
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


class Child:
    """Un proceso hijo (servidor, puente, ratón) con su salida volcada al registro de la ventana."""

    def __init__(self, name, args, log):
        self.name, self.log = name, log
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if WIN else 0
        self.proc = subprocess.Popen([sys.executable, *args], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
                                     encoding="utf-8", errors="replace", creationflags=flags)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.log(self.name, line.rstrip())
        self.log(self.name, f"(terminó, código {self.proc.wait()})")

    def alive(self):
        return self.proc.poll() is None

    def stop(self, timeout=8):
        """Ctrl+Break primero (el puente y el ratón limpian al recibirlo), a la fuerza si no responde."""
        if not self.alive():
            return
        try:
            if WIN:
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()


class Launcher:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.children = {}
        self.lines = queue.Queue()
        root.title("GearStream")
        root.geometry("640x560")
        root.minsize(520, 460)
        pad = dict(padx=10, pady=4)

        net = ttk.LabelFrame(root, text="Red de esta laptop")
        net.pack(fill="x", **pad)
        self.net_var = tk.StringVar(value="mirando la red…")
        ttk.Label(net, textvariable=self.net_var).pack(anchor="w", padx=8, pady=6)

        watch = ttk.LabelFrame(root, text="Reloj")
        watch.pack(fill="x", **pad)
        row = ttk.Frame(watch)
        row.pack(fill="x", padx=8, pady=6)
        ttk.Label(row, text="IP del reloj").pack(side="left")
        self.ip_var = tk.StringVar(value=self.settings.get("watch_ip", ""))
        entry = ttk.Entry(row, textvariable=self.ip_var, width=18)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: self.connect())
        self.find_btn = ttk.Button(row, text="Buscar en la red", command=self.find)
        self.find_btn.pack(side="left", padx=4)
        self.conn_btn = ttk.Button(row, text="Conectar", command=self.connect)
        self.conn_btn.pack(side="left", padx=4)
        self.status_var = tk.StringVar(value="La IP del reloj sale en el reloj: Ajustes > Conexiones > Wi-Fi > tu red.")
        ttk.Label(watch, textvariable=self.status_var, wraplength=600).pack(anchor="w", padx=8, pady=(0, 6))

        modes = ttk.LabelFrame(root, text="Usar")
        modes.pack(fill="x", **pad)
        row = ttk.Frame(modes)
        row.pack(fill="x", padx=8, pady=6)
        for label in PAGES:
            ttk.Button(row, text=label, command=lambda p=PAGES[label]: self.open_page(p)).pack(side="left", padx=3)
        self.mouse_btn = ttk.Button(row, text="Ratón aéreo: encender", command=self.toggle_mouse)
        self.mouse_btn.pack(side="left", padx=3)
        ttk.Label(modes, text="El juego y el ratón aéreo no van juntos: el ratón movería el cursor mientras juegas.",
                  foreground="#666").pack(anchor="w", padx=8, pady=(0, 6))

        logf = ttk.LabelFrame(root, text="Registro")
        logf.pack(fill="both", expand=True, **pad)
        self.log_box = tk.Text(logf, height=10, wrap="word", font=("Consolas", 9), state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=6, pady=6)

        bottom = ttk.Frame(root)
        bottom.pack(fill="x", **pad)
        ttk.Button(bottom, text="Detener todo", command=self.stop_all).pack(side="right")

        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.after(100, self.drain)
        threading.Thread(target=self.detect_network, daemon=True).start()

    # ---------- registro ----------
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
            if n > 400:
                self.log_box.delete("1.0", f"{n - 400}.0")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
            for line in new:
                self.watch_status(line)
        self.root.after(150, self.drain)

    def watch_status(self, line):
        if "[puente]" not in line:
            return
        if "conectado a ws://" in line:
            self.set_status("Conectado al reloj. Toca la pantalla del reloj si las muestras no llegan.")
        elif " Hz: " in line:
            self.set_status(line.split("] ", 1)[1])
        elif "no responde" in line:
            self.set_status("El reloj no responde: ¿Depuración activada, misma red, Bluetooth del teléfono apagado?")

    def set_status(self, text):
        self.root.after(0, self.status_var.set, text)

    # ---------- red y reloj ----------
    def detect_network(self):
        ssid = wifi_name()
        ips = local_ipv4s()
        text = f"Wi-Fi: {ssid or 'no detectada'}    ·    IP de la laptop: {', '.join(ips) or 'sin IP'}"
        self.root.after(0, self.net_var.set, text)
        self.log("red", text)

    def find(self):
        self.find_btn.configure(state="disabled")
        self.set_status("Buscando relojes con depuración en la red (unos segundos)…")

        def work():
            try:
                hosts = asyncio.run(find_watch())
            except Exception as e:                    # una red rara no debe tumbar la ventana
                hosts = []
                self.log("buscar", f"error: {e}")
            if hosts:
                self.root.after(0, self.ip_var.set, hosts[0])
                self.set_status(f"Encontrado: {', '.join(hosts)}. Pulsa Conectar.")
            else:
                self.set_status("No lo encontré buscando (en el hotspot del teléfono pasa). Escribe la IP que sale "
                                "en el reloj: Ajustes > Conexiones > Wi-Fi > tu red.")
            self.root.after(0, lambda: self.find_btn.configure(state="normal"))
        threading.Thread(target=work, daemon=True).start()

    def connect(self):
        ip = self.ip_var.get().strip()
        if not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}(:\d+)?", ip):
            self.set_status("Escribe una IP como 192.168.0.XX (sale en el reloj: Ajustes > Conexiones > Wi-Fi).")
            return
        self.settings["watch_ip"] = ip
        save_settings(self.settings)
        self.conn_btn.configure(state="disabled")
        self.set_status(f"Midiendo la red hacia {ip}…")

        def work():
            if not port_open("127.0.0.1", 8765):
                self.children["servidor"] = Child("servidor", ["server/server.py"], self.log)
                for _ in range(30):
                    if port_open("127.0.0.1", 8765):
                        break
                    time.sleep(0.2)
            old = self.children.pop("puente", None)
            if old:
                old.stop()
            rtt = ping_ms(ip.split(":")[0])
            batch = 6 if rtt is not None and rtt > 15 else 0
            why = "sin respuesta al ping" if rtt is None else f"ida y vuelta {rtt:.0f} ms"
            self.log("red", f"{why}: " + (f"red lenta, agrupo {batch} muestras por paquete" if batch else "red rápida, sin agrupar"))
            args = ["tools/sdb_bridge.py", "--device", ip, "--flush-ms", "10",
                    "--sensors", "accelerometer,gyroscope,gravity"]
            if batch:
                args += ["--batch", str(batch)]
            self.children["puente"] = Child("puente", args, self.log)
            self.set_status(f"Conectando con el reloj en {ip}… si el reloj pregunta por la depuración, acepta.")
            self.root.after(0, lambda: self.conn_btn.configure(state="normal"))
        threading.Thread(target=work, daemon=True).start()

    # ---------- modos ----------
    def open_page(self, page):
        if not port_open("127.0.0.1", 8765):
            self.set_status("Primero pulsa Conectar (arranca el servidor y el puente).")
            return
        webbrowser.open(f"http://localhost:8765/{page}")

    def toggle_mouse(self):
        m = self.children.get("ratón")
        if m and m.alive():
            threading.Thread(target=m.stop, daemon=True).start()
            self.mouse_btn.configure(text="Ratón aéreo: encender")
            return
        if not port_open("127.0.0.1", 8765):
            self.set_status("Primero pulsa Conectar.")
            return
        self.children["ratón"] = Child("ratón", ["tools/air_mouse.py", "--forearm", "+x"], self.log)
        self.mouse_btn.configure(text="Ratón aéreo: apagar")
        self.set_status("Ratón aéreo encendido: apoya la muñeca 2 s para calibrar. Esquina superior izquierda 1.5 s lo apaga.")

    def stop_all(self, then=None):
        kids = [self.children.pop(k) for k in ("ratón", "puente", "servidor") if k in self.children]
        self.mouse_btn.configure(text="Ratón aéreo: encender")

        def work():
            for c in kids:
                c.stop()
            self.log("lanzador", "todo detenido")
            if then:
                self.root.after(0, then)
        threading.Thread(target=work, daemon=True).start()

    def quit(self):
        self.stop_all(then=self.root.destroy)


def main():
    root = tk.Tk()
    app = Launcher(root)
    if "--selftest" in sys.argv:          # construir la ventana, mirar la red y cerrar (para pruebas)
        def done():
            print("red:", app.net_var.get())
            print("ip guardada:", app.ip_var.get() or "(ninguna)")
            root.destroy()
        root.after(2500, done)
    root.mainloop()


if __name__ == "__main__":
    main()
