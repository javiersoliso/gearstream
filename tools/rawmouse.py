"""Lector del ratón crudo de Windows por Raw Input: cada movimiento del sensor tal como lo manda el ratón
(cuentas, sin la aceleración del puntero de Windows) y sus botones, a la tasa del propio ratón.

    from rawmouse import MouseReader
    r = MouseReader(callback)       # callback(evento) desde un hilo propio
    r.start(); ...; r.stop()

Cada evento: {"t_ms": reloj de pared, "dev": identificador del dispositivo, "dx", "dy": cuentas,
"down": True/False si cambió el botón izquierdo en este informe (None si no), "flags": usButtonFlags}.
El trackpad también genera eventos de ratón; "dev" permite separarlos del ratón de verdad.
"""
import ctypes
import threading
import time
from ctypes import wintypes as W

from touchpad import HWND_MESSAGE, RAWINPUTDEVICE, RAWINPUTHEADER, RID_INPUT, RIDEV_INPUTSINK, RIDEV_REMOVE, \
    WM_CLOSE, WM_DESTROY, WM_INPUT, WNDCLASSW, WNDPROC, kernel32, user32

RIM_TYPEMOUSE = 0
RI_MOUSE_LEFT_DOWN, RI_MOUSE_LEFT_UP = 0x0001, 0x0002
MOUSE_MOVE_ABSOLUTE = 0x0001


class MouseReader:
    def __init__(self, callback):
        self.callback = callback
        self.hwnd = None
        self.error = None
        self.reports = 0
        self._ready = threading.Event()

    def _run(self):
        hsize = ctypes.sizeof(RAWINPUTHEADER)

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                sz = W.UINT(0)
                user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(sz), hsize)
                buf = ctypes.create_string_buffer(sz.value)
                if user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(sz), hsize) == sz.value:
                    head = RAWINPUTHEADER.from_buffer_copy(buf.raw[:hsize])
                    if head.dwType == RIM_TYPEMOUSE:
                        m = buf.raw[hsize:]
                        flags = int.from_bytes(m[0:2], "little")
                        bflags = int.from_bytes(m[4:6], "little")
                        dx = int.from_bytes(m[12:16], "little", signed=True)
                        dy = int.from_bytes(m[16:20], "little", signed=True)
                        if not flags & MOUSE_MOVE_ABSOLUTE:      # los ratones de verdad mandan movimiento relativo
                            down = True if bflags & RI_MOUSE_LEFT_DOWN else False if bflags & RI_MOUSE_LEFT_UP else None
                            self.reports += 1
                            self.callback({"t_ms": time.time() * 1000, "dev": int(head.hDevice or 0), "dx": dx, "dy": dy,
                                           "down": down, "flags": bflags})
            elif msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        self._proc = WNDPROC(wndproc)
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName="GearStreamRawMouse")
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, "GearStreamRawMouse", "mouse", 0, 0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
        rid = RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, self.hwnd)       # página genérica, uso ratón
        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)):
            self.error = f"Windows no dejó registrar el ratón (error {ctypes.get_last_error()})"
            self._ready.set()
            return
        self._ready.set()
        msg = W.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        rid = RAWINPUTDEVICE(0x01, 0x02, RIDEV_REMOVE, None)
        user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(3)
        return self.error is None

    def stop(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)


if __name__ == "__main__":       # prueba: 6 s mostrando lo que llega
    seen = []
    r = MouseReader(seen.append)
    print("registrado" if r.start() else f"error: {r.error}")
    print("mueve el ratón 6 s…", flush=True)
    time.sleep(6)
    r.stop()
    devs = {}
    for e in seen:
        devs.setdefault(e["dev"], []).append(e)
    for d, evs in devs.items():
        span = (evs[-1]["t_ms"] - evs[0]["t_ms"]) / 1000 if len(evs) > 1 else 0
        print(f"dispositivo {d}: {len(evs)} informes" + (f", {len(evs) / span:.0f}/s" if span else ""))
