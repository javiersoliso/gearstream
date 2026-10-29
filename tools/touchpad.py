"""Lector del trackpad de precisión de Windows (HID, página 0x0D uso 0x05) por Raw Input.

El navegador solo ve el cursor moverse; Windows, leyendo el dispositivo HID, da cada dedo: si toca (Tip
Switch), su identificador, su posición absoluta en las unidades del trackpad y el Scan Time (el reloj del
propio trackpad, en unidades de 100 µs). Con eso el dedo índice es un esfero: posición, lápiz abajo y
lápiz arriba.

    from touchpad import TouchpadReader
    r = TouchpadReader(callback)        # callback(evento) desde un hilo propio
    r.start(); ...; r.stop()

Cada evento: {"t_ms": reloj de pared, "scan": Scan Time (100 µs, da la vuelta en 65536), "count": dedos
en el informe, "fingers": [(id, toca, x, y), ...]} con x, y en unidades lógicas; r.extents da el rango y
los milímetros por unidad. Un hilo con una ventana solo-mensajes recibe WM_INPUT aunque otra ventana
tenga el foco (RIDEV_INPUTSINK).
"""
import ctypes
import threading
import time
from ctypes import wintypes as W

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid")

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
WM_INPUT, WM_CLOSE, WM_DESTROY = 0x00FF, 0x0010, 0x0002
RIDEV_INPUTSINK, RIDEV_REMOVE = 0x00000100, 0x00000001
RID_INPUT, RIDI_PREPARSEDDATA, RIDI_DEVICEINFO = 0x10000003, 0x20000005, 0x2000000B
RIM_TYPEHID = 2
HWND_MESSAGE = W.HWND(-3)
HIDP_INPUT = 0
HIDP_OK = 0x00110000
PAGE_DIGITIZER, PAGE_DESKTOP = 0x0D, 0x01
U_TIP, U_CONTACT_ID, U_SCAN, U_COUNT = 0x42, 0x51, 0x56, 0x54
U_X, U_Y = 0x30, 0x31


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", W.HINSTANCE), ("hIcon", W.HICON), ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH),
                ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", W.USHORT), ("usUsage", W.USHORT), ("dwFlags", W.DWORD), ("hwndTarget", W.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", W.DWORD), ("dwSize", W.DWORD), ("hDevice", W.HANDLE), ("wParam", W.WPARAM)]


class RID_DEVICE_INFO_HID(ctypes.Structure):
    _fields_ = [("dwVendorId", W.DWORD), ("dwProductId", W.DWORD), ("dwVersionNumber", W.DWORD),
                ("usUsagePage", W.USHORT), ("usUsage", W.USHORT)]


class RID_DEVICE_INFO(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("dwType", W.DWORD), ("hid", RID_DEVICE_INFO_HID), ("_pad", ctypes.c_byte * 8)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", W.USHORT), ("UsagePage", W.USHORT), ("InputReportByteLength", W.USHORT),
                ("OutputReportByteLength", W.USHORT), ("FeatureReportByteLength", W.USHORT), ("Reserved", W.USHORT * 17),
                ("NumberLinkCollectionNodes", W.USHORT), ("NumberInputButtonCaps", W.USHORT),
                ("NumberInputValueCaps", W.USHORT), ("NumberInputDataIndices", W.USHORT),
                ("NumberOutputButtonCaps", W.USHORT), ("NumberOutputValueCaps", W.USHORT),
                ("NumberOutputDataIndices", W.USHORT), ("NumberFeatureButtonCaps", W.USHORT),
                ("NumberFeatureValueCaps", W.USHORT), ("NumberFeatureDataIndices", W.USHORT)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", W.USHORT), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte), ("BitField", W.USHORT),
                ("LinkCollection", W.USHORT), ("LinkUsage", W.USHORT), ("LinkUsagePage", W.USHORT),
                ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte),
                ("IsAbsolute", ctypes.c_ubyte), ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte),
                ("BitSize", W.USHORT), ("ReportCount", W.USHORT), ("Reserved2", W.USHORT * 5),
                ("UnitsExp", W.ULONG), ("Units", W.ULONG), ("LogicalMin", W.LONG), ("LogicalMax", W.LONG),
                ("PhysicalMin", W.LONG), ("PhysicalMax", W.LONG),
                ("Usage", W.USHORT), ("UsageMax", W.USHORT), ("_r", W.USHORT * 6)]


assert ctypes.sizeof(HIDP_VALUE_CAPS) == 72 and ctypes.sizeof(RID_DEVICE_INFO) == 32

user32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.restype = W.HWND
user32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
user32.GetRawInputData.argtypes = [W.HANDLE, W.UINT, W.LPVOID, ctypes.POINTER(W.UINT), W.UINT]
user32.GetRawInputDeviceInfoW.argtypes = [W.HANDLE, W.UINT, W.LPVOID, ctypes.POINTER(W.UINT)]
user32.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
for f in ("HidP_GetUsageValue",):
    getattr(hid, f).restype = ctypes.c_long
hid.HidP_GetUsageValue.argtypes = [ctypes.c_int, W.USHORT, W.USHORT, W.USHORT, ctypes.POINTER(W.ULONG), W.LPVOID,
                                   ctypes.c_char_p, W.ULONG]
hid.HidP_GetUsages.restype = ctypes.c_long
hid.HidP_GetUsages.argtypes = [ctypes.c_int, W.USHORT, W.USHORT, ctypes.POINTER(W.USHORT), ctypes.POINTER(W.ULONG),
                               W.LPVOID, ctypes.c_char_p, W.ULONG]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidP_GetCaps.argtypes = [W.LPVOID, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.restype = ctypes.c_long
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS), ctypes.POINTER(W.USHORT), W.LPVOID]


def _mm(cap):
    """milímetros que mide el eje según Units/UnitsExp del HID, o None si no se entiende"""
    system, length = cap.Units & 0xF, (cap.Units >> 4) & 0xF
    e = cap.UnitsExp & 0xF
    e = e - 16 if e >= 8 else e
    span = cap.PhysicalMax - cap.PhysicalMin
    if length != 1 or span <= 0:
        return None
    if system == 1:                       # SI lineal: centímetros
        return span * 10 ** e * 10
    if system == 3:                       # inglés lineal: pulgadas
        return span * 10 ** e * 25.4
    return None


class TouchpadReader:
    def __init__(self, callback):
        self.callback = callback
        self.hwnd = None
        self.thread = None
        self.devices = {}           # hDevice -> (preparsed buffer, fingers [link], report length)
        self.extents = None         # {"x": (min, max, mm), "y": (min, max, mm)}
        self.error = None
        self.reports = 0
        self._ready = threading.Event()
        self._remaining = 0

    # ---------- descripción del dispositivo ----------
    def _describe(self, hdev):
        info = RID_DEVICE_INFO(); info.cbSize = 32; sz = W.UINT(32)
        user32.GetRawInputDeviceInfoW(hdev, RIDI_DEVICEINFO, ctypes.byref(info), ctypes.byref(sz))
        if info.dwType != RIM_TYPEHID or (info.hid.usUsagePage, info.hid.usUsage) != (PAGE_DIGITIZER, 0x05):
            return None
        n = W.UINT(0)
        user32.GetRawInputDeviceInfoW(hdev, RIDI_PREPARSEDDATA, None, ctypes.byref(n))
        pre = ctypes.create_string_buffer(n.value)
        user32.GetRawInputDeviceInfoW(hdev, RIDI_PREPARSEDDATA, pre, ctypes.byref(n))
        caps = HIDP_CAPS()
        if hid.HidP_GetCaps(pre, ctypes.byref(caps)) != HIDP_OK:
            return None
        nv = W.USHORT(caps.NumberInputValueCaps)
        vcaps = (HIDP_VALUE_CAPS * max(1, nv.value))()
        hid.HidP_GetValueCaps(HIDP_INPUT, vcaps, ctypes.byref(nv), pre)
        fingers, ext = [], {}
        for c in vcaps[:nv.value]:
            if c.UsagePage == PAGE_DESKTOP and c.Usage in (U_X, U_Y) and not c.IsRange:
                if c.Usage == U_X and c.LinkCollection not in fingers:
                    fingers.append(c.LinkCollection)
                key = "x" if c.Usage == U_X else "y"
                if key not in ext:
                    ext[key] = (c.LogicalMin, c.LogicalMax, _mm(c))
        fingers.sort()
        self.extents = ext
        return pre, fingers, caps.InputReportByteLength

    # ---------- un informe ----------
    def _parse(self, hdev, data):
        dev = self.devices.get(hdev)
        if dev is None:
            dev = self.devices[hdev] = self._describe(hdev)
        if not dev:
            return
        pre, fingers, rlen = dev
        size, count = int.from_bytes(data[0:4], "little"), int.from_bytes(data[4:8], "little")
        t = time.time() * 1000
        for k in range(count):
            rep = bytes(data[8 + k * size: 8 + (k + 1) * size])
            val = W.ULONG(0)
            scan = val.value if hid.HidP_GetUsageValue(HIDP_INPUT, PAGE_DIGITIZER, 0, U_SCAN, ctypes.byref(val), pre, rep, size) == HIDP_OK else None
            val = W.ULONG(0)
            cnt = val.value if hid.HidP_GetUsageValue(HIDP_INPUT, PAGE_DIGITIZER, 0, U_COUNT, ctypes.byref(val), pre, rep, size) == HIDP_OK else 0
            # modo híbrido: un cuadro con N dedos puede venir repartido en varios informes (los siguientes traen 0)
            if cnt:
                self._remaining = cnt
            take = min(self._remaining, len(fingers))
            self._remaining -= take
            out = []
            for link in fingers[:take]:
                vals = {}
                for page, usage, name in ((PAGE_DESKTOP, U_X, "x"), (PAGE_DESKTOP, U_Y, "y"), (PAGE_DIGITIZER, U_CONTACT_ID, "id")):
                    v = W.ULONG(0)
                    if hid.HidP_GetUsageValue(HIDP_INPUT, page, link, usage, ctypes.byref(v), pre, rep, size) == HIDP_OK:
                        vals[name] = v.value
                ulist = (W.USHORT * 16)()
                ulen = W.ULONG(16)
                tip = False
                if hid.HidP_GetUsages(HIDP_INPUT, PAGE_DIGITIZER, link, ulist, ctypes.byref(ulen), pre, rep, size) == HIDP_OK:
                    tip = U_TIP in ulist[:ulen.value]
                if "x" in vals and "y" in vals:
                    out.append((vals.get("id", link), tip, vals["x"], vals["y"]))
            self.reports += 1
            self.callback({"t_ms": t, "scan": scan, "count": cnt, "fingers": out})

    # ---------- hilo con ventana solo-mensajes ----------
    def _run(self):
        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                sz = W.UINT(0)
                user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(sz), ctypes.sizeof(RAWINPUTHEADER))
                buf = ctypes.create_string_buffer(sz.value)
                if user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(sz), ctypes.sizeof(RAWINPUTHEADER)) == sz.value:
                    head = RAWINPUTHEADER.from_buffer_copy(buf.raw[:ctypes.sizeof(RAWINPUTHEADER)])
                    if head.dwType == RIM_TYPEHID:
                        try:
                            self._parse(head.hDevice, buf.raw[ctypes.sizeof(RAWINPUTHEADER):])
                        except Exception as e:      # un informe raro no debe tumbar el hilo
                            self.error = f"informe no entendido: {e}"
            elif msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        self._proc = WNDPROC(wndproc)                    # mantener viva la referencia
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName="GearStreamTouchpad")
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, "GearStreamTouchpad", "touchpad", 0, 0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
        rid = RAWINPUTDEVICE(PAGE_DIGITIZER, 0x05, RIDEV_INPUTSINK, self.hwnd)
        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)):
            self.error = f"Windows no dejó registrar el trackpad (error {ctypes.get_last_error()})"
            self._ready.set()
            return
        self._ready.set()
        msg = W.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        rid = RAWINPUTDEVICE(PAGE_DIGITIZER, 0x05, RIDEV_REMOVE, None)
        user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self._ready.wait(3)
        return self.error is None

    def stop(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)


if __name__ == "__main__":          # prueba: 10 s mostrando lo que llega
    seen = []

    def cb(ev):
        seen.append(ev)
        if len(seen) % 25 == 1:
            print(f"{len(seen):5d} informes · scan {ev['scan']} · dedos {ev['fingers']}", flush=True)
    r = TouchpadReader(cb)
    print("registrado" if r.start() else f"error: {r.error}")
    print("toca el trackpad durante 10 s…", flush=True)
    time.sleep(10)
    r.stop()
    if len(seen) > 2:
        dt = (seen[-1]["t_ms"] - seen[0]["t_ms"]) / 1000
        print(f"{len(seen)} informes en {dt:.1f} s = {len(seen) / dt:.0f} por segundo · extensión {r.extents}")
    else:
        print(f"{len(seen)} informes · extensión {r.extents} · {r.error or ''}")
