"""Uses the Galaxy Watch as an air mouse for this Windows laptop WITHOUT an app on the watch: the
gyroscope moves the cursor, the back button (or a tap on the watch face) clicks, the bezel (or
rolling the forearm) scrolls. Reads the dashboard feed (ws://.../ui), so the bridge and the server
keep running as usual, or talks sdb to the watch directly (--source sdb, exclusive: stops the dashboard).

    python tools/sdb_bridge.py --device 192.168.0.XX --flush-ms 10 --sensors accelerometer,gyroscope,gravity
    python tools/air_mouse.py                          # ws://localhost:8765/ui, moves the real cursor
    python tools/air_mouse.py --dry-run                # prints "mover/clic/rueda" instead of moving
    python tools/air_mouse.py --source sdb --device 192.168.0.XX
    python tools/air_mouse.py --replay recordings/20261024-235450 [--realtime]   # offline report, exit 1 on creep/false clicks
    python tools/air_mouse.py --calibrate axes|tap|forearm
    http://localhost:8765/calibrate.html               # live tuning page, talks to ws://127.0.0.1:8766 (--control-port)

Why these choices: the bezel and the buttons ARE readable over sdb (the bridge reads /dev/input and
emits BEZEL and BUTTON samples), so --click auto uses the back button and --scroll auto the bezel
whenever the bridge's hello offers them; there is still no finger-pinch signal (no EMG), so the tap
on the glass (sharp spike on accel z while the wrist is still) and the forearm roll remain as
fallbacks and are selectable live from the calibration page through the control channel. The roll
by construction moves the cursor nothing (the pointer axes are yaw about the vertical projected
perpendicular to the forearm, and pitch about the axis perpendicular to the forearm, so a pure roll
has no component on either at any tilt).
Fail-safes, all on by default: Ctrl+C/Break/console close release every button, --dry-run, the
cursor parked by the physical mouse in the top-left corner exits (code 3), a wrist shake or the Pause
key pauses, a 0.5 s watchdog (also checked on arrival, so a backlog after a long block of this
process is discarded, never applied), stale samples never move the cursor, the physical mouse always
wins, arm hanging down pauses, 4000 px/s cap per sample and per wall-clock second, a locked desktop
(GetCursorPos failing) pauses, every click is one SendInput call [DOWN, UP], and a watch button held
down is released on every pause, on a mode change, on shutdown and after 10 s.
The physical-mouse yield never trusts a GetCursorPos taken right after SendInput (it can still return
the previous target: the raw-input thread applies the move later); it explains the live cursor from
the ring of targets sent in the last 250 ms, a 2 px rounding tolerance or a position it is stuck at,
and only yields to a position none of those explain (at once beyond 6 px, after 100 ms below). The
echo explanation is short-lived on purpose: a hand pulling the mouse back along our own trace lands
on older targets too, so a cursor that keeps needing an older target for 100 ms yields as well.
The gyro bias is only taken from a window that looks like rest (p2p < 1 °/s, |median| < --bias-max,
accelerometer norm ≈ g and steady): a steady slow rotation never becomes the bias.
A "flick to click" (sharp pitch impulse) was considered and left out of v1: on the recording it is
indistinguishable from the start of a deliberate move, so it would either fire while pointing or need
a latency worse than the tap's 250 ms.
"""
import argparse
import asyncio
import atexit
import csv
import ipaddress
import json
import math
import os
import re
import signal
import statistics
import sys
import time
import urllib.parse
import traceback
from collections import Counter, deque, namedtuple

VERSION = "1.2"
SOURCES = ("GYROSCOPE", "ACCELERATION", "GRAVITY")
SHORT = {"GYROSCOPE": "GYR", "ACCELERATION": "ACC", "GRAVITY": "GRV"}
INPUTS = ("BEZEL", "BUTTON")
IGNORED = ("HRM", "PRESSURE", "LIGHT", "LINEAR_ACCELERATION")
G0 = 9.807
OFFSET_LEAK_MS = 0.0003   # same as sdb_bridge.py: lets the clock anchor follow a slow watch clock
FOREARM = {"+y": (0.0, 1.0, 0.0), "-y": (0.0, -1.0, 0.0), "+x": (1.0, 0.0, 0.0), "-x": (-1.0, 0.0, 0.0)}
STALE_MS, FRESH_MS, GAP_MS, GAP_BLANK_MS = 300, 150, 100, 300
# The latency baseline (minimum sample age) falls instantly and rises at most this fast per second of
# arrival time, so a backlog delivered after a stall stays "stale" instead of re-anchoring it.
BASELINE_RISE_MS_PER_S = 30.0
ABS_STALE_MS = 1000       # loopback only: a sample older than this is stale whatever the baseline says
MAX_AGE_MS = 86_400_000   # a timestamp more than a day away from now is garbage, not a sample
STILL_DEG = 1.5           # deg/s: below this on every axis the wrist counts as still
KILL_CORNER_S = 1.5       # s the physical mouse must stay parked in the kill corner (ticks are 50 ms)
KILL_CORNER_TICKS = round(KILL_CORNER_S / 0.05)
RECOVER_S = 3.0           # s of rest-looking raw gyro with the bias off by > STILL_DEG before resetting it
BUDGET_S = 0.25           # wall-clock cap: at most max_speed * BUDGET_S px may be applied in one burst
ACCEL_STALE_S = 2.0       # s without accelerometer (gyro still arriving) before taps are disabled
INPUT_STALE_MS = 1000     # a bezel/button sample older than this is not applied (a release always is)
BUTTON_FREEZE_S = 0.15    # cursor frozen after a button DOWN: a quick press/release is a clean click, not a drag
BUTTON_HOLD_MAX_S = 10.0  # a watch button held longer is released (the bridge may have died mid-press)
# physical-mouse yield (see _observe_cursor)
YIELD_TOL_PX = 2          # Chebyshev tolerance for "that is ours" (mapping rounding, 1-px jitter)
YIELD_JUMP_PX = 6         # a deviation this large is a real mouse at once (no second look)
YIELD_PERSIST_S = 0.1     # smaller deviations must persist this long (two observations); so must an echo
ECHO_MS = 250             # how long a sent target may still be "in flight" in the raw-input thread
ECHO_S = ECHO_MS / 1000.0 # the same in the monotonic clock's unit (every comparison uses this one)
ECHO_RUN_MAX = 3          # looks in a row at a target two or more behind that still count as an echo
STUCK_S = 0.1             # cursor unchanged this long while our targets moved on = clamped: adopt it
YIELD_QUIET_S = 1.0       # resume this long after the physical mouse went quiet
WHEEL_MAX_PER_SAMPLE = 100   # notches one bezel sample may produce (a corrupt `steps` must not spin the page)
WHEEL_MAX_NOTCHES = 273      # |n * WHEEL_DELTA| must fit the signed 16 bits of WM_MOUSEWHEEL (32767 // 120)
RELEASE_RETRY_S = 1.0     # a button UP that SendInput refused (elevated window in front) is retried this often
STATE_HZ = 25             # control channel: state messages per second
PROFILE_DEFAULT = os.path.join("~", ".gearstream", "airmouse.json")
CONTROL_ORIGINS = ["http://localhost:8765", "http://127.0.0.1:8765", None]   # see control_origins()
INF = float("inf")


def emit(text):
    """print() that survives a redirected cp1252 console (the messages use · → °)."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(enc, "replace").decode(enc), flush=True)


def log(msg):
    emit(f"{time.strftime('%H:%M:%S')} {msg}")


def _jsonable(v):
    """Numbers the page can parse: JSON has no inf/nan (JSON.parse rejects Python's 'Infinity')."""
    if isinstance(v, float):
        return round(v, 3) if math.isfinite(v) else None
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    return v


# ---------- small math ----------

def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm3(a):
    return math.sqrt(dot(a, a))


def normalize(a):
    n = norm3(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-9 else None


def wrap_deg(a):
    return a - 360.0 * math.floor((a + 180.0) / 360.0)


def clamp(v, lo, hi):
    if v != v:                       # NaN compares False with everything: never let it through
        return lo
    return lo if v < lo else hi if v > hi else v


def norm(px, origin, size):
    """Pixel -> 0..65535 for MOUSEEVENTF_ABSOLUTE; (n*size)>>16 == px for every px (size < 65536)."""
    return max(0, min(65535, math.ceil((px - origin) * 65536 / max(1, size))))


class OneEuro:
    def __init__(self, mincutoff, beta, dcutoff):
        self.mincutoff, self.beta, self.dcutoff = mincutoff, beta, dcutoff
        self.x = None
        self.dx = 0.0

    def reset(self):
        self.x = None
        self.dx = 0.0

    @staticmethod
    def alpha(fc, dt):
        return 1.0 / (1.0 + 1.0 / (2 * math.pi * fc * dt))

    def __call__(self, x, dt):
        if self.mincutoff <= 0:
            return x
        if self.x is None:
            self.x, self.dx = x, 0.0
            return x
        d = (x - self.x) / dt
        ad = self.alpha(self.dcutoff, dt)
        self.dx = ad * d + (1 - ad) * self.dx
        a = self.alpha(self.mincutoff + self.beta * abs(self.dx), dt)
        self.x = a * x + (1 - a) * self.x
        return self.x


# ---------- signal processing: bias, gravity, roll, pointer rates ----------

class GyroStep:
    """What one gyro sample produced (all rates in deg/s, deltas in px)."""
    __slots__ = ("gap", "delta", "dt", "omega", "omega_mag", "yaw", "pitch", "roll", "rf", "rho",
                 "dx", "dy", "speed", "theta", "theta_dot", "e", "gf", "stationary", "calibrated",
                 "just_calibrated", "zero_remainder", "recovered")

    def __init__(self):
        self.gap = False
        self.delta = None
        self.dt = 0.01
        self.omega = (0.0, 0.0, 0.0)
        self.omega_mag = self.yaw = self.pitch = self.roll = self.rho = 0.0
        self.rf = (0.0, 0.0)
        self.dx = self.dy = self.speed = 0.0
        self.theta = self.theta_dot = self.e = self.gf = 0.0
        self.stationary = self.calibrated = self.just_calibrated = self.zero_remainder = self.recovered = False


class Motion:
    def __init__(self, cfg):
        self.cfg = cfg
        self.fhat = FOREARM[cfg.forearm]
        self.body = cfg.frame == "body"
        self.bias = [0.0, 0.0, 0.0]
        self.bias_p2p = INF            # p2p of the window that produced the current bias
        self.calibrated = False
        self.calib_warned = False
        self.background = False
        self.calib = deque(maxlen=300)       # (t, x, y, z) raw gyro over the last 1 s
        self.calib_acc = deque(maxlen=300)   # (t, |a|, |jerk| per sample)
        self.calib_gdir = deque(maxlen=300)  # (t, gx, gy, gz) unit gravity (GRAVITY, else accel)
        self.calib_start = None
        self.calib_n = 0
        self.calib_waited = 0
        self.calib_reject = Counter()
        self.recover_since = None
        self.recoveries = 0
        self.bias_updates = 0
        self.bias_max_step = 0.0
        self.ghat = (0.0, 0.0, 1.0)
        self.phat = (1.0, 0.0, 0.0)
        self.g_meas = None
        self.g_meas_t = -INF
        self.a_meas = None
        self.a_norm = None
        self.a_t = None
        self.theta = self.theta0 = 0.0
        self.fx = OneEuro(cfg.mincutoff, cfg.beta, cfg.dcutoff)
        self.fy = OneEuro(cfg.mincutoff, cfg.beta, cfg.dcutoff)
        self.last_t = None
        self.still_run = 0
        self.quiet_since = None

    # -- inputs other than the gyro --
    def feed_gravity(self, t, x, y, z):
        g = normalize((x, y, z))
        if g:
            self.g_meas, self.g_meas_t = g, t
            self.calib_gdir.append((t, *g))

    def feed_accel(self, t, x, y, z):
        prev, prev_t = self.a_meas, self.a_t
        self.a_meas, self.a_t = (x, y, z), t
        self.a_norm = norm3(self.a_meas)
        jerk = math.dist(prev, self.a_meas) if prev is not None and t - prev_t <= GAP_MS else 0.0
        self.calib_acc.append((t, self.a_norm, jerk))
        if self.g_meas is None or t - self.g_meas_t >= 500:   # no GRAVITY stream: direction from the accel
            g = normalize(self.a_meas)
            if g:
                self.calib_gdir.append((t, *g))

    def gravity_measurement(self, t):
        if self.g_meas is not None and t - self.g_meas_t < 500:
            return self.g_meas
        return normalize(self.a_meas) if self.a_meas else None

    def reset_filters(self):
        self.fx.reset()
        self.fy.reset()

    def start_calibration(self, background=False):
        self.calibrated = self.calibrated and background
        self.background = background
        self.calib.clear()
        self.calib_start = None
        self.calib_n = 0
        self.calib_waited = 0

    def _rest_window(self, t):
        """(verdict, p2p, medians) of the last 1 s of raw gyro: "ok" when it looks like the wrist at rest.

        Rest means: p2p < 1 deg/s per axis (no movement), |median| < --bias-max per axis (a steady slow
        rotation is not rest even though its p2p is small), accelerometer norm within 1 m/s2 of g with a
        small per-sample jerk, and a steady gravity direction (component p2p < 0.05, ~3 deg)."""
        while self.calib and self.calib[0][0] < t - 1000:
            self.calib.popleft()
        while self.calib_acc and self.calib_acc[0][0] < t - 1000:
            self.calib_acc.popleft()
        while self.calib_gdir and self.calib_gdir[0][0] < t - 1000:
            self.calib_gdir.popleft()
        if len(self.calib) < 80:
            return "corto", None, None
        cols = list(zip(*[s[1:] for s in self.calib]))
        p2p = max(max(c) - min(c) for c in cols)
        med = [statistics.median(c) for c in cols]
        if p2p >= self.cfg.calib_p2p:
            return "movimiento", p2p, med
        if max(abs(m) for m in med) >= self.cfg.bias_max:
            return "giro constante", p2p, med
        if self.calib_acc:
            if max(abs(a - G0) for _, a, _ in self.calib_acc) >= 1.0:
                return "aceleración", p2p, med
            if max(j for _, _, j in self.calib_acc) >= 0.6:
                return "sacudida", p2p, med
        if len(self.calib_gdir) >= 2:
            gcols = list(zip(*[s[1:] for s in self.calib_gdir]))
            if max(max(c) - min(c) for c in gcols) >= 0.05:
                return "gravedad inestable", p2p, med
        return "ok", p2p, med

    def _calibrate(self, t, x, y, z):
        """First 1-s window that looks like rest -> per-axis median. No fallback: a window that does not
        look like rest is never accepted; in the background the previous bias is kept after 10 s."""
        self.calib.append((t, x, y, z))
        self.calib_n += 1
        if self.calib_start is None:
            self.calib_start = t
        if self.calib_n % 10:
            return False
        verdict, p2p, med = self._rest_window(t)
        if verdict != "ok":
            if verdict != "corto":
                self.calib_reject[verdict] += 1
            waited = int((t - self.calib_start) // 10000)
            if waited > self.calib_waited:
                self.calib_waited = waited
                if self.background:
                    self.background = False             # give up: keep the bias we had
                    self.calib_warned = "background"
                else:
                    self.calib_warned = verdict          # the caller nags the user; keep waiting
            return False
        if self.background and p2p > self.bias_p2p + 0.2:   # must be at least as quiet as the current one
            self.calib_reject["menos quieto"] += 1
            return False
        self.bias = list(med)
        self.bias_p2p = p2p
        if not self.calibrated:
            g = self.gravity_measurement(t) or (0.0, 0.0, 1.0)
            self.ghat = g
            self.theta = self.theta0 = self.roll_from_gravity(g)
        self.calibrated = True
        self.background = False
        self.calib_warned = False
        self.recover_since = None
        return True

    def _recover_bias(self, t, x, y, z):
        """Large-error recovery: the raw gyro has looked like rest for RECOVER_S while the corrected rate
        still reads >= STILL_DEG on some axis (so the slow tracker cannot engage) -> take the medians."""
        self.calib.append((t, x, y, z))
        self.calib_n += 1
        if self.calib_n % 10:
            return False
        verdict, p2p, med = self._rest_window(t)
        if verdict != "ok" or max(abs(m - b) for m, b in zip(med, self.bias)) < STILL_DEG:
            self.recover_since = None
            return False
        if self.recover_since is None:
            self.recover_since = t
            return False
        if t - self.recover_since < RECOVER_S * 1000:
            return False
        self.bias = list(med)
        self.bias_p2p = p2p
        self.recover_since = None
        self.recoveries += 1
        return True

    def roll_from_gravity(self, g):
        f = self.cfg.forearm
        if f == "+y":
            return math.degrees(math.atan2(-g[0], g[2]))
        if f == "-y":
            return math.degrees(math.atan2(g[0], g[2]))
        if f == "+x":
            return math.degrees(math.atan2(g[1], g[2]))
        return math.degrees(math.atan2(-g[1], g[2]))

    def feed_gyro(self, t, x, y, z, bias_ok=True, theta0_ok=True):
        s = GyroStep()
        delta = None if self.last_t is None else t - self.last_t
        self.last_t = t
        s.delta = delta
        s.gap = delta is not None and delta > GAP_MS
        # the real interval of this step (clamped): a 60 ms sample integrates 60 ms, not the median
        dt = clamp(delta, 5, GAP_MS) / 1000.0 if delta is not None and not s.gap else 0.01
        s.dt = dt
        if s.gap:
            self.reset_filters()
            self.still_run = 0
            self.recover_since = None
        if not self.calibrated or self.background:
            s.just_calibrated = self._calibrate(t, x, y, z) and not self.background
            if not self.calibrated:
                return s
        else:
            s.recovered = self._recover_bias(t, x, y, z)
        s.calibrated = True
        b = self.bias
        w = (x - b[0], y - b[1], z - b[2])
        s.omega = w
        s.omega_mag = norm3(w)
        # stationary -> slow bias update, clamped to 0.05 deg/s per axis per second
        self.still_run = self.still_run + 1 if max(abs(w[0]), abs(w[1]), abs(w[2])) < STILL_DEG else 0
        s.stationary = self.still_run >= 50
        if s.stationary and bias_ok and not s.gap:
            k, lim = dt / self.cfg.bias_tau, 0.05 * dt
            for i, raw in enumerate((x, y, z)):
                step = clamp(k * (raw - b[i]), -lim, lim)
                b[i] += step
                self.bias_max_step = max(self.bias_max_step, abs(step))
            self.bias_updates += 1
        # gravity direction: propagate with the gyro, pull toward the measurement while quiet
        g = self.ghat
        quiet = s.omega_mag < 30 and (self.a_norm is None or abs(self.a_norm - 9.81) < 1.0)
        if delta is not None and not s.gap:
            wr = (math.radians(w[0]), math.radians(w[1]), math.radians(w[2]))
            c = cross(wr, g)
            g = normalize((g[0] - c[0] * dt, g[1] - c[1] * dt, g[2] - c[2] * dt)) or g
            gm = self.gravity_measurement(t)
            if quiet and gm is not None:
                k = 2.0 * dt
                g = normalize((g[0] + k * (gm[0] - g[0]), g[1] + k * (gm[1] - g[1]), g[2] + k * (gm[2] - g[2]))) or g
        self.ghat = g
        s.gf = dot(g, self.fhat)
        # pointer frame: pitch about the axis perpendicular to the forearm and the up vector; yaw about
        # the up vector projected perpendicular to the forearm (scaled so a yaw about the vertical keeps
        # its full rate at any tilt) -> a pure roll about the forearm has no component on either
        gp = (0.0, 0.0, 1.0) if self.body else g
        c = cross(self.fhat, gp)
        n = norm3(c)
        if n >= 0.3:
            self.phat = (c[0] / n, c[1] / n, c[2] / n)
        s.roll = dot(w, self.fhat)
        gpf = dot(gp, self.fhat)
        s.yaw = (dot(w, gp) - s.roll * gpf) / max(1.0 - gpf * gpf, 0.09)
        s.pitch = dot(w, self.phat)
        # roll angle and its neutral
        s.theta_dot = s.roll
        if delta is not None and not s.gap:
            k = 1.0 if quiet and abs(s.gf) < 0.85 else 0.0
            self.theta = wrap_deg(self.theta + s.theta_dot * dt + k * dt * wrap_deg(self.roll_from_gravity(g) - self.theta))
        s.theta = self.theta
        # filter, deadzone, gain
        rfx, rfy = self.fx(s.yaw, dt), self.fy(s.pitch, dt)
        s.rf = (rfx, rfy)
        rho = math.hypot(rfx, rfy)
        s.rho = rho
        if theta0_ok and abs(s.theta_dot) < 20 and rho < 30:
            self.theta0 = wrap_deg(self.theta0 + (dt / 5.0) * wrap_deg(self.theta - self.theta0))
        s.e = wrap_deg(self.theta - self.theta0)
        dz = self.cfg.deadzone
        if rho <= dz:
            rdx = rdy = 0.0
            if self.quiet_since is None:
                self.quiet_since = t
            s.zero_remainder = t - self.quiet_since >= 150
        else:
            self.quiet_since = None
            k = (rho - dz) / rho
            rdx, rdy = rfx * k, rfy * k
        v = math.hypot(rdx, rdy)
        cfg = self.cfg
        if cfg.accel and cfg.v_hi > cfg.v_lo:
            u = clamp((v - cfg.v_lo) / (cfg.v_hi - cfg.v_lo), 0.0, 1.0)
            gain = cfg.g_lo + (cfg.g_hi - cfg.g_lo) * (3 * u * u - 2 * u * u * u)
        else:
            gain = cfg.g_lo
        if delta is None or s.gap:
            return s
        dx = -gain * cfg.gain * cfg.gain_x * rdx * dt
        dy = -gain * cfg.gain * cfg.gain_y * rdy * dt
        speed = math.hypot(dx, dy) / dt
        if speed > cfg.max_speed:
            f = cfg.max_speed / speed
            dx, dy, speed = dx * f, dy * f, cfg.max_speed
        s.dx, s.dy, s.speed = dx, dy, speed
        return s


# ---------- gesture detectors (sample time, raw bias-corrected signals) ----------

class TapDetector:
    """Sharp spike on accel z while the wrist is still before and after; decided 250 ms later.

    The pre-tap gyro gate is checked when the candidate appears (that window is already in the gyro
    deque), so a bump while pointing never arms: no freeze, no rewind. Only the post gate waits."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.acc = deque(maxlen=150)     # (t, a_z, d)   d = per-10-ms difference
        self.gyro = deque(maxlen=200)    # (t, |omega|)
        self.last_cand_t = -INF
        self.pending = None
        self.candidates = self.shape_ok = self.gate_ok = self.confirmed = 0
        self.expired = 0

    def reset(self):
        self.pending = None

    def pre_max(self, tt):
        return max((m for t, m in self.gyro if tt - 200 <= t <= tt - 20), default=INF)

    def feed_accel(self, t, az, armed):
        if self.acc:
            pt, paz, _ = self.acc[-1]
            d = (az - paz) * 10.0 / clamp(t - pt, 5, GAP_MS)   # normalised to the nominal 10 ms interval
        else:
            d = 0.0
        self.acc.append((t, az, d))
        if abs(d) > self.cfg.tap_thr and t - self.last_cand_t >= 150:
            self.last_cand_t = t
            self.candidates += 1
            pre = self.pre_max(t)
            cand = {"t": t, "peak": d, "armed": armed and self.pending is None and pre < self.cfg.tap_pre,
                    "pre_at_arm": pre}
            if self.pending is None:
                self.pending = cand
            return cand
        return None

    def feed_gyro(self, t, omega_mag):
        self.gyro.append((t, omega_mag))
        p = self.pending
        if p is None or t < p["t"] + self.cfg.tap_post_ms:
            return None
        if not self.acc or self.acc[-1][0] < p["t"] + 200:
            if t > p["t"] + self.cfg.tap_post_ms + 300:   # the accelerometer stream stopped: never wait forever
                self.pending = None
                self.expired += 1
                p.update(width=0, baseline=INF, pre_max=p["pre_at_arm"], post_max=INF, verdict="sin acelerómetro")
                return p
            return None
        self.pending = None
        return self.decide(p)

    def decide(self, p):
        cfg, tt = self.cfg, p["t"]
        width = sum(1 for t, _, d in self.acc if tt - 80 <= t <= tt + 80 and abs(d) > cfg.tap_thr / 2)
        pre = [az for t, az, _ in self.acc if tt - 200 <= t <= tt - 100]
        post = [az for t, az, _ in self.acc if tt + 100 <= t <= tt + 200]
        baseline = abs(statistics.fmean(post) - statistics.fmean(pre)) if pre and post else INF
        pre_max = self.pre_max(tt)
        post_max = max((m for t, m in self.gyro if tt + 80 <= t <= tt + cfg.tap_post_ms), default=INF)
        polarity = cfg.tap_polarity == "any" or (p["peak"] < 0) == (cfg.tap_polarity == "neg")
        shape = width <= cfg.tap_width and baseline < 0.8 and polarity
        gates = pre_max < cfg.tap_pre and post_max < cfg.tap_post
        self.shape_ok += shape
        self.gate_ok += shape and gates
        # "confirmed" is signal-level (shape and gates): the replay regression test counts it even
        # while the state machine is paused; the click itself only fires when the tap was armed
        self.confirmed += shape and gates
        p.update(width=width, baseline=baseline, pre_max=pre_max, post_max=post_max,
                 verdict=("confirmado" if p["armed"] else "confirmado (sin clic: pausa)") if shape and gates
                 else "forma" if not shape else "giro")
        return p


class DwellDetector:
    def __init__(self, cfg):
        self.cfg = cfg
        self.reset()
        self.last_fire = -INF
        self.fires = 0

    def reset(self):
        self.travel = 0.0
        self.seen_fast = False
        self.hold_start = None
        self.hold_pos = None

    def feed(self, t, rho, pos, moved_px, enabled):
        self.travel += moved_px
        if rho > 4.0:
            self.seen_fast = True
        if rho >= self.cfg.dwell_speed or not enabled:   # a hold while disabled (tap freeze, pause) does not count
            self.hold_start = None
            return False
        if self.hold_start is None or math.hypot(pos[0] - self.hold_pos[0], pos[1] - self.hold_pos[1]) >= 6:
            self.hold_start, self.hold_pos = t, pos
            return False
        armed = self.travel >= self.cfg.dwell_arm and self.seen_fast
        if armed and t - self.hold_start >= self.cfg.dwell_time * 1000 and t - self.last_fire >= 1000:
            self.last_fire = t
            self.fires += 1
            self.reset()
            return True
        return False


class RollScroller:
    """Forearm roll beyond 25 deg from the neutral, reached as a ramp slower than --scroll-max-rate
    after a short quiet hold, with the pointer rates quiet; exits (never wraps) beyond 90 deg."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.active = False
        self.hist_e = deque(maxlen=200)    # (t, |e|) over 600 ms
        self.hist_r = deque(maxlen=100)    # (t, |theta_dot|, rho) over 300 ms
        self.t_enter = -INF
        self.n_prev = 0
        self.last_tick = -INF
        self.rate_acc = 0.0
        self.entries = self.up = self.down = 0
        self.max_e = 0.0
        self.quiet_since = None
        self.ramp_start = None             # (t, hold_ms): when the wrist last got busy, after how long a quiet hold
        self.rejected = Counter()

    def reset(self):
        self.active = False
        self.hist_e.clear()
        self.hist_r.clear()
        self.quiet_since = None
        self.ramp_start = None

    def feed(self, t, e, theta_dot, rho, allowed):
        """Returns a list of events: ("enter", e), ("wheel", n), ("exit", timeout)."""
        cfg, ae = self.cfg, abs(e)
        self.max_e = max(self.max_e, ae)
        self.hist_e.append((t, ae))
        self.hist_r.append((t, abs(theta_dot), rho))
        while self.hist_e and self.hist_e[0][0] < t - 600:
            self.hist_e.popleft()
        while self.hist_r and self.hist_r[0][0] < t - 300:
            self.hist_r.popleft()
        if abs(theta_dot) < 10 and rho < 5:
            self.quiet_since = t if self.quiet_since is None else self.quiet_since
        else:
            if self.quiet_since is not None:
                self.ramp_start = (t, t - self.quiet_since)
            self.quiet_since = None
        events = []
        if not self.active:
            if not allowed or ae < cfg.scroll_enter:
                return events
            if ae > cfg.scroll_max_deg:
                return events
            past = [v for ts, v in self.hist_e if ts <= t - 500]
            ramp = past and ae - past[-1] >= 20
            m_th = statistics.fmean(v for _, v, _ in self.hist_r)
            m_r = statistics.fmean(v for _, _, v in self.hist_r)
            dominant = m_th >= 10 and m_th >= 1.5 * m_r and max(v for _, _, v in self.hist_r) < 60
            if not (ramp and dominant):
                return events
            if max(v for _, v, _ in self.hist_r) > cfg.scroll_max_rate:       # a fling, not a scroll
                self.rejected["rápido"] += 1
                return events
            rs = self.ramp_start   # the movement must have started within 1 s, out of a >= 150 ms quiet hold
            if rs is None or t - rs[0] > 1000 or rs[1] < 150:
                self.rejected["sin pausa previa"] += 1
                return events
            self.active, self.t_enter, self.n_prev, self.last_tick, self.rate_acc = True, t, 0, -INF, 0.0
            self.entries += 1
            events.append(("enter", e))
            return events
        timeout = t - self.t_enter > cfg.scroll_timeout * 1000
        if ae < cfg.scroll_exit or ae > cfg.scroll_max_deg or timeout:
            self.active = False
            events.append(("exit", timeout))
            return events
        sign = 1 if e < 0 else -1
        if cfg.scroll_invert:
            sign = -sign
        if cfg.scroll_mode == "ratchet":
            n = int((ae - cfg.scroll_enter) // cfg.scroll_deg_per_notch)
            if n < self.n_prev:
                # hysteresis: step down one notch only once |e| is 2 deg below that notch's boundary
                if ae < cfg.scroll_enter + self.n_prev * cfg.scroll_deg_per_notch - 2.0:
                    self.n_prev -= 1
            elif n > self.n_prev and t - self.last_tick >= 40:
                self.n_prev += 1
                self.last_tick = t
                events.append(("wheel", sign))
        else:
            dt = clamp(t - self.hist_r[-2][0], 5, 25) / 1000.0 if len(self.hist_r) > 1 else 0.01
            self.rate_acc += min(8.0, 0.12 * (ae - cfg.scroll_enter)) * dt
            whole = int(self.rate_acc)
            if whole >= 1:
                self.rate_acc -= whole
                events.append(("wheel", sign * whole))
        for ev in events:
            if ev[0] == "wheel":
                if ev[1] > 0:
                    self.up += ev[1]
                else:
                    self.down -= ev[1]
        return events


class ShakeDetector:
    """Lobes above 600 deg/s with >= 4 sign reversals of the dominant axis within 700 ms."""

    def __init__(self, cfg):
        self.hist = deque(maxlen=200)
        self.last_toggle = -INF
        self.toggles = 0

    def reset(self):
        self.hist.clear()

    def feed(self, t, omega):
        self.hist.append((t, omega))
        while self.hist and self.hist[0][0] < t - 700:
            self.hist.popleft()
        if t - self.last_toggle < 1000 or norm3(omega) <= 600:
            return None
        start, first = next((ts, w) for ts, w in self.hist if norm3(w) > 600)
        axis = max(range(3), key=lambda i: abs(first[i]))
        reversals, sign = 0, 0
        for _, w in self.hist:
            if abs(w[axis]) > 200:
                s = 1 if w[axis] > 0 else -1
                if sign and s != sign:
                    reversals += 1
                sign = s
        if reversals >= 4:
            self.hist.clear()
            self.last_toggle = t
            self.toggles += 1
            return start
        return None


# ---------- pointers ----------

def corner_of(kind, bounds, monitors=None, primary=None):
    """The kill corner: the virtual screen's corner when a monitor actually covers it, otherwise the
    primary monitor's corner (Windows confines the cursor to the union of the monitors, not to their
    bounding box, so a corner in dead space could never be reached by the physical mouse)."""
    vx, vy, vw, vh = bounds
    x = vx if kind in ("tl", "bl") else vx + vw - 1
    y = vy if kind in ("tl", "tr") else vy + vh - 1
    if not monitors or any(mx <= x < mx + mw and my <= y < my + mh for mx, my, mw, mh in monitors):
        return (x, y), False
    px, py, pw, ph = primary or monitors[0]
    return (px if kind in ("tl", "bl") else px + pw - 1, py if kind in ("tl", "tr") else py + ph - 1), True


class DryRunPointer:
    """Prints what would happen (<= 10 "mover" lines/s) and keeps a log; never touches user32 input.
    The cursor is simulated, so the kill corner, the physical-mouse yield and the Pause key are not
    exercised in a dry run (main() says so)."""

    def __init__(self, bounds=(0, 0, 1920, 1080), quiet=False, monitors=None):
        self.bounds = tuple(bounds)
        self.monitors = monitors
        vx, vy, vw, vh = self.bounds
        self.pos = (vx + vw // 2, vy + vh // 2)
        self.held = set()
        self.log = []
        self.quiet = quiet
        self.partial_insert = False
        self.fail_cursor = False        # tests: GetCursorPos failing (locked desktop, UAC prompt)
        self.block_release = False      # tests: SendInput refusing the UP (UIPI), so the button stays held
        self._last_print = 0.0

    def cursor_pos(self):
        return None if self.fail_cursor else self.pos

    def refresh_bounds(self):
        return self.bounds

    def corner(self, kind):
        return corner_of(kind, self.bounds, self.monitors)[0]

    def _say(self, text, force=False):
        now = time.monotonic()
        if force or (not self.quiet and now - self._last_print >= 0.1):
            self._last_print = now
            emit(text)

    def move_to(self, x, y):
        vx, vy, vw, vh = self.bounds
        self.pos = (int(clamp(x, vx, vx + vw - 1)), int(clamp(y, vy, vy + vh - 1)))
        self.log.append(("move", self.pos[0], self.pos[1]))
        self._say(f"mover ({self.pos[0]},{self.pos[1]})")

    def move_by(self, dx, dy):
        self.move_to(self.pos[0] + dx, self.pos[1] + dy)

    def click(self):
        self.log.append(("click", self.pos[0], self.pos[1]))
        if self.partial_insert:
            self.held.add("left")
        self._say(f"clic en ({self.pos[0]},{self.pos[1]})", force=True)

    def press(self, button):
        self.log.append(("down", button))
        self.held.add(button)
        self._say(f"botón {BUTTON_NAMES[button]} abajo en ({self.pos[0]},{self.pos[1]})", force=True)

    def release(self, button):
        if self.block_release:          # like Win32Pointer.release when SendInput inserted nothing
            self.log.append(("up", button, "bloqueado"))
            return
        self.log.append(("up", button))
        self.held.discard(button)
        self._say(f"botón {BUTTON_NAMES[button]} arriba en ({self.pos[0]},{self.pos[1]})", force=True)

    def wheel(self, n):
        self.log.append(("wheel", n))
        self._say(f"rueda {n:+d}", force=True)

    def release_all(self):
        for b in list(self.held):
            self.log.append(("up", b))
            self.held.discard(b)
        self.log.append(("release",))

    def pause_key_pressed(self):
        return False


MOUSEEVENTF_MOVE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0001, 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0008, 0x0010, 0x0020, 0x0040
MOUSEEVENTF_WHEEL, MOUSEEVENTF_VIRTUALDESK, MOUSEEVENTF_ABSOLUTE = 0x0800, 0x4000, 0x8000
WHEEL_DELTA, EXTRA, VK_PAUSE = 120, 0x47535431, 0x13   # 'GST1' tags our events in dwExtraInfo
E_ACCESSDENIED = 0x80070005                            # SetProcessDpiAwareness: "already set"
BUTTON_FLAGS = {"left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
                "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
                "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP)}
BUTTON_NAMES = {"left": "izquierdo", "right": "derecho", "middle": "central"}


_WIN32 = None


def _win32():
    global _WIN32
    if _WIN32 is not None:
        return _WIN32
    import ctypes
    from ctypes import wintypes

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                    ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_void_p)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        _anonymous_ = ("u",)
        _fields_ = [("type", ctypes.c_ulong), ("u", _U)]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = (ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = ctypes.c_uint
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
    user32.MonitorFromPoint.restype = ctypes.c_void_p
    _WIN32 = (ctypes, wintypes, user32, MOUSEINPUT, INPUT)
    return _WIN32


def make_dpi_aware():
    """Per-monitor v2 -> per-monitor -> system; otherwise GetSystemMetrics lies at 125 %."""
    if sys.platform != "win32":
        return "n/a"
    ctypes, _, user32, _, _ = _win32()
    try:
        f = user32.SetProcessDpiAwarenessContext
        f.argtypes, f.restype = (ctypes.c_void_p,), ctypes.c_bool
        if f(ctypes.c_void_p(-4)):
            return "por monitor v2"
    except (AttributeError, OSError):
        pass
    try:
        r = ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        if r in (0, E_ACCESSDENIED, E_ACCESSDENIED - 2 ** 32):   # E_ACCESSDENIED = already set
            return "por monitor"
    except (AttributeError, OSError):
        pass
    try:
        if user32.SetProcessDPIAware():
            return "sistema"
    except (AttributeError, OSError):
        pass
    return "sin DPI"


def virtual_screen():
    if sys.platform != "win32":
        return (0, 0, 1920, 1080)
    _, _, user32, _, _ = _win32()
    return tuple(user32.GetSystemMetrics(i) for i in (76, 77, 78, 79))


class Win32Pointer:
    def __init__(self):
        self.ctypes, self.wintypes, self.user32, self.MOUSEINPUT, self.INPUT = _win32()
        self.bounds = virtual_screen()
        self.held = set()
        self._uipi_logged = -INF
        self._pause_down = False
        self._corner_fallback = {}
        self._corners = {}

    def cursor_pos(self):
        """(x, y), or None while the input desktop is not ours (lock screen, UAC prompt): GetCursorPos
        fails there and the POINT would read (0, 0), which is the kill corner on most layouts."""
        pt = self.wintypes.POINT()
        if not self.user32.GetCursorPos(self.ctypes.byref(pt)):
            return None
        return (pt.x, pt.y)

    def refresh_bounds(self):
        self.bounds = virtual_screen()
        self._corners.clear()
        return self.bounds

    def _on_monitor(self, x, y):
        return bool(self.user32.MonitorFromPoint(self.wintypes.POINT(int(x), int(y)), 0))   # MONITOR_DEFAULTTONULL

    def corner(self, kind):
        if kind in self._corners:
            return self._corners[kind]
        vx, vy, vw, vh = self.bounds
        x = vx if kind in ("tl", "bl") else vx + vw - 1
        y = vy if kind in ("tl", "tr") else vy + vh - 1
        primary = (0, 0, self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1))   # always at the origin
        c, fallback = corner_of(kind, self.bounds, None if self._on_monitor(x, y) else [primary], primary)
        if fallback and self._corner_fallback.get(kind) != c:
            self._corner_fallback[kind] = c
            log(f"la esquina {kind} de la pantalla virtual ({x},{y}) no está en ningún monitor: "
                f"uso la del monitor principal ({c[0]},{c[1]}) como interruptor de emergencia")
        self._corners[kind] = c
        return c

    def _send(self, *mis):
        arr = (self.INPUT * len(mis))(*[self.INPUT(type=0, mi=m) for m in mis])
        n = self.user32.SendInput(len(mis), arr, self.ctypes.sizeof(self.INPUT))
        if n != len(mis):
            err = self.ctypes.get_last_error()
            now = time.monotonic()
            if err == 5 and now - self._uipi_logged >= 5:
                self._uipi_logged = now
                log("entrada bloqueada (ventana elevada en primer plano) — ejecuta como administrador si lo necesitas")
        return n

    def move_to(self, x, y):
        vx, vy, vw, vh = self.bounds
        self._send(self.MOUSEINPUT(norm(x, vx, vw), norm(y, vy, vh), 0,
                                   MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, EXTRA))

    def move_by(self, dx, dy):
        self._send(self.MOUSEINPUT(int(dx), int(dy), 0, MOUSEEVENTF_MOVE, 0, EXTRA))

    def click(self):
        n = self._send(self.MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, EXTRA),
                       self.MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, EXTRA))
        if n == 1:
            self.held.add("left")

    def press(self, button):
        """DOWN only (a watch button held = a drag); `held` remembers it until the UP was inserted."""
        if self._send(self.MOUSEINPUT(0, 0, 0, BUTTON_FLAGS[button][0], 0, EXTRA)) == 1:
            self.held.add(button)

    def release(self, button):
        if self._send(self.MOUSEINPUT(0, 0, 0, BUTTON_FLAGS[button][1], 0, EXTRA)) == 1:
            self.held.discard(button)

    def wheel(self, n):
        # mouseData is a signed 16-bit delta inside a DWORD: beyond ±273 notches it would wrap and scroll
        # the other way, so the notches are clamped here whatever the caller asked for
        n = int(clamp(n, -WHEEL_MAX_NOTCHES, WHEEL_MAX_NOTCHES))
        self._send(self.MOUSEINPUT(0, 0, (n * WHEEL_DELTA) & 0xFFFFFFFF, MOUSEEVENTF_WHEEL, 0, EXTRA))

    def release_all(self):
        """Only what a partial insert or a press left down, never a blind UP; the button stays in `held`
        until the UP was actually inserted, so a later call (atexit, console handler) retries it."""
        for b in list(self.held):
            for attempt in range(5):
                if self._send(self.MOUSEINPUT(0, 0, 0, BUTTON_FLAGS[b][1], 0, EXTRA)) == 1:
                    self.held.discard(b)
                    break
                time.sleep(0.05)
            else:
                log(f"no pude soltar el botón {BUTTON_NAMES[b]} (entrada bloqueada): suéltalo con el ratón físico")

    def pause_key_pressed(self):
        down = bool(self.user32.GetAsyncKeyState(VK_PAUSE) & 0x8000)
        edge = down and not self._pause_down
        self._pause_down = down
        return edge


# ---------- the air mouse ----------

class AirMouse:
    def __init__(self, cfg, pointer, clock=time.monotonic):
        self.cfg, self.pointer, self.clock = cfg, pointer, clock
        self.motion = Motion(cfg)
        self.tap, self.dwell = TapDetector(cfg), DwellDetector(cfg)
        self.scroll, self.shake = RollScroller(cfg), ShakeDetector(cfg)
        self.shadow = RollScroller(cfg)    # signal-level scroll metric: fed even while paused (replay report)
        self.P = None
        self.last_set = None
        self.force_move = False
        self.rel_pending = [0, 0]
        self.rel_step = (0, 0)
        self.ring = deque(maxlen=150)      # (t, P_x, P_y) after each gyro sample
        self.events = []
        self.pause_reasons = {}
        self.pause_count = Counter()
        self.pause_durations = []
        self.frozen_until = -INF
        self.pending_reset = False
        self.gap_blank_until = -INF
        self.now = self.now_ms = 0.0
        self.baseline = None               # minimum sample age seen (falls instantly, rises slowly)
        self.baseline_now = None
        self.last_gyro_arrival = None
        self.last_accel_arrival = None
        self.accel_lost = False
        self.last_gyro_t = None
        self.first_gyro_t = None
        self.idle_since = None
        self.stall_len = None
        self.stalls = []
        self.stalls_on_arrival = 0
        self.fresh_since = None
        self.last_lag = 0.0
        self.msg_count = 0
        self.resume_msg = -1
        self.resume_jump = 0.0
        self.msg_travel = 0.0
        self.px_budget = 0.0
        self.budget_now = None
        self.capped = 0
        self.counts, self.rate_t0 = Counter(), None
        self.stale_count = self.malformed = self.unknown = 0
        self.ages, self.lags = deque(maxlen=300), deque(maxlen=300)
        self.bridge_lag = None
        self.bridge_lag_min = None         # smallest bridge->here delay seen (clock offset + fastest delivery)
        self.bridge_lag_now = None
        self.travel = self.max_speed = self.frozen_s = 0.0
        self.clicks = self.moves = 0
        self.kill_requested = False
        self.corner_ticks = 0
        self.last_bounds_refresh = None
        self.yield_until = None
        self.click_times = deque(maxlen=1000)
        self.clicks_disabled_until = -INF
        self.last_click_t = -INF
        self.last_click_pos = None
        self.tap_pos = None
        self.pose_high_since = self.pose_low_since = None
        self.loopback = True
        self.motion_hook = None
        self.calib_mode = None
        self.calib_done = False
        self.calib_g = deque(maxlen=300)
        self.gravity_state = None
        self.bias_log_at = None
        self.tap_times, self.dwell_times, self.shake_times, self.gaps = [], [], [], []
        self.recal_check_at = None
        self.failed = None
        self.time_label = lambda: time.strftime("%H:%M:%S")
        self.gesture_file = self.gesture_csv = None
        if getattr(cfg, "log_gestures", None):
            self.gesture_file = open(cfg.log_gestures, "w", newline="", encoding="utf-8")
            self.gesture_csv = csv.writer(self.gesture_file)
            self.gesture_csv.writerow(["t_s", "kind", "peak", "width", "baseline", "pre_max", "post_max", "verdict"])
        # bezel / buttons (from the bridge's hello) and the effective click/scroll modes
        self.available = set()
        self.input_errors = set()
        self.click_mode = self.scroll_mode = None
        self.held = None                   # (button, monotonic since) while a watch button is down
        self.button_freeze_until = -INF
        self.wheel_notches = 0             # roll + bezel, as sent to the pointer
        self.wheel_clamped = 0             # bezel samples whose notches exceeded WHEEL_MAX_PER_SAMPLE
        self.dropped_actions = 0           # queued clicks/wheels/buttons not sent because the user owned the cursor
        self.release_retry_at = -INF
        self.bridge_baseline = None        # minimum (our clock - bridge clock at send) seen: the inputs' age reference
        self.bridge_baseline_now = None
        self.control = None                # the ControlServer, when run_live started one
        self._resolve_modes()
        # physical-mouse yield: targets in flight, the last position seen and since when, foreign sightings
        self.sent = deque(maxlen=32)       # (monotonic, (x, y), (mx, my)) targets sent to the pointer
        self.anchor = None                 # the cursor position read last
        self.anchor_since = None           # when the cursor was first seen at `anchor` (unchanged since)
        self.anchor_moved = False          # a target was sent after that sighting
        self.foreign_since = None
        self.yield_cp = None
        self.last_cursor = None
        self.echo_late = 0                 # sightings of an older target exactly (the raw-input thread behind us)
        self.echo_run = 0                  # consecutive looks explained by a target two or more behind
        self.echo_run = 0                  # consecutive sightings explained only by an older target
        self.stuck_waits = self.stuck_adopts = 0   # sightings of an unchanged cursor while targets moved on / adoptions
        # control channel: events, state deltas, rates, raw ring for --record-gesture
        self.event_queue = deque(maxlen=256)
        self.last_step = GyroStep()
        self.state_dx = self.state_dy = 0.0
        self.hz_counts, self.hz, self.hz_t0 = Counter(), {}, None
        self.raw_ring = deque(maxlen=1200)   # (source, t_ms, x, y, z): the last ~4 s of the three sensors

    # -- logging --
    def say(self, msg):
        emit(f"{self.time_label()} {msg}")

    def event(self, kind, **detail):
        """Queues a control-channel event (drained by the ControlServer broadcaster; JSON-safe numbers)."""
        self.event_queue.append({"type": "event", "t": round(time.time() * 1000), "kind": kind,
                                 "detail": {k: _jsonable(v) for k, v in detail.items()}})

    def t_s(self, t):
        return (t - (self.first_gyro_t or t)) / 1000.0

    def log_gesture(self, t, kind, peak="", width="", baseline="", pre="", post="", verdict=""):
        fmt = lambda v: f"{v:.2f}" if isinstance(v, float) and math.isfinite(v) else ("inf" if v == INF else v)
        row = [f"{self.t_s(t):.3f}", kind, fmt(peak), width, fmt(baseline), fmt(pre), fmt(post), verdict]
        if self.gesture_csv:
            self.gesture_csv.writerow(row)
        if self.calib_mode == "tap" and kind == "tap":
            self.say("tap candidato " + " ".join(f"{k}={v}" for k, v in zip(
                ("t_s", "kind", "pico", "ancho", "base", "giro_pre", "giro_post", "veredicto"), row) if k != "kind"))

    # -- state helpers --
    @property
    def paused(self):
        return bool(self.pause_reasons)

    @property
    def inputs_allowed(self):
        """Bezel and buttons need no gyro calibration (a click works before the bias is found)."""
        return not self.paused and self.calib_mode is None

    def frozen(self, t):
        return (t < self.frozen_until or self.scroll.active or self.now < self.button_freeze_until
                or (self.tap.pending is not None and self.tap.pending["armed"]))

    def _resolve_modes(self):
        """`auto` picks by what the bridge offers; a change releases a held button and leaves a roll scroll."""
        cfg = self.cfg
        usable = self.available - self.input_errors   # a reader the bridge could not attach is not on offer
        click = ("button" if "BUTTON" in usable else "tap") if cfg.click == "auto" else cfg.click
        scroll = ("bezel" if "BEZEL" in usable else "roll") if cfg.scroll == "auto" else cfg.scroll
        if self.held is not None:
            b = self.held[0]
            if (b == "left" and click != "button") or (b != "left" and cfg.home_key != b):
                self._release_held("modo")
        if self.scroll_mode == "roll" and scroll != "roll" and self.scroll.active:
            self._scroll_exit(timeout=False)
        changed = (click, scroll) != (self.click_mode, self.scroll_mode)
        first = self.click_mode is None
        self.click_mode, self.scroll_mode = click, scroll
        if changed and not first:
            self.tap.reset()
            self.dwell.reset()
            self.scroll.reset()
            self.say(f"modos: clic por {click}, scroll por {scroll}")

    def _pause(self, reason):
        if reason in self.pause_reasons:
            return
        self.pause_reasons[reason] = self.now
        self.pause_count[reason] += 1
        self.say(f"pausa: {reason}")
        self.event("pause", reason=reason)
        if self.tap.pending is not None and self.tap.pending["armed"]:
            self.tap.pending["armed"] = False      # a pause before the decision rejects the tap
            self.frozen_until = -INF
        if self.scroll.active:
            self._scroll_exit(timeout=False)
        self.dwell.reset()
        self._release_held("pausa")               # a drag must not outlive the control we have over the cursor

    def _resume(self, reason, note="", cp=None):
        since = self.pause_reasons.pop(reason, None)
        if since is None:
            return
        self.pause_durations.append((reason, self.now - since))
        if not self.pause_reasons:
            self.say("reanudado" + (f" ({note})" if note else ""))
            self.event("resume", reason=reason, note=note or None)
            self.motion.reset_filters()
            self.resume_msg = self.msg_count
            if self.P is not None:
                cp = self.pointer.cursor_pos() if cp is None else cp
                if cp is not None:
                    self._resync(cp)

    def _resync(self, cp):
        self.P = [float(cp[0]), float(cp[1])]
        self.last_set = (cp[0], cp[1])
        self.rel_pending = [0, 0]
        self.ring.clear()                  # positions before a resync are not where the cursor is now
        self.sent.clear()
        self.echo_run = 0
        self.anchor = self.last_set
        self.stuck_since = self.foreign_since = None

    def _release_held(self, reason):
        """Lets go of a watch button that is down. A DOWN still queued (never sent) is simply dropped;
        one already sent gets its UP directly (pauses happen in tick(), with no flush following)."""
        if self.held is None:
            return
        b, since = self.held
        self.held = None
        self.button_freeze_until = -INF
        queued = next((i for i, ev in enumerate(self.events) if ev[0] == "down" and ev[1] == b), None)
        if queued is not None:
            del self.events[queued]
        else:
            self.pointer.release(b)
            self.say(f"suelto el botón {BUTTON_NAMES[b]} ({reason})")
        self.event("held_release", button=b, reason=reason, held_ms=round((self.now - since) * 1000))

    # -- physical-mouse yield --
    def _observe_cursor(self, cp, now):
        """Explains the live cursor position or yields to it. Called before every move (in _flush) and
        on every tick; never right after a SendInput, whose read-back may still be the previous target.
        Explanations, in order: our newest target (exactly); an older target still in flight (ECHO_MS)
        or the last position confirmed as ours, which the thread has simply not left yet (an echo) or
        cannot leave (clamped at a monitor edge: after STUCK_S it is adopted, so the rubber band stays
        one flush long); our newest target within YIELD_TOL_PX (mapping rounding, acceleration: adopt);
        an older target within the tolerance. Anything else is the user's hand: a jump of YIELD_JUMP_PX
        yields at once, a smaller deviation after YIELD_PERSIST_S. The order matters: the echo and anchor
        checks come before the tolerance, so a stale read never re-anchors P (that was the half gain)."""
        if cp is None:
            return
        self.last_cursor = cp
        if self.P is None or self.last_set is None:
            self.anchor = cp
            return
        recent = [e for e in self.sent if now - e[0] <= ECHO_S]
        tol = YIELD_TOL_PX
        if self.cfg.move == "relative":            # pointer acceleration can multiply a relative delta
            tol += 4 * sum(max(abs(m[0]), abs(m[1])) for _, _, m in recent)
        near = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= tol
        if self.yield_until is not None:
            if cp != self.yield_cp:                # the mouse is still moving: wait for a quiet second
                self.yield_cp = cp
                self.yield_until = now + YIELD_QUIET_S
            elif now >= self.yield_until:
                self.yield_until = None
                self._resync(cp)
                self._resume("ratón físico", cp=cp)
            return
        if cp == self.last_set:
            if cp != self.anchor:
                self.anchor, self.stuck_since = cp, None
            self.foreign_since = None
            self.echo_run = 0
            return
        if cp == self.anchor:                      # not moved since our last confirmed position although we sent more
            if self.stuck_since is None:
                self.stuck_since = now
            elif now - self.stuck_since >= STUCK_S:
                self.P[0] += cp[0] - self.last_set[0]
                self.P[1] += cp[1] - self.last_set[1]
                self.last_set = cp
                self.sent.clear()
                self.stuck_adopts += 1
            else:
                self.echo_late += 1
            self.foreign_since = None
            return
        if self._echo(cp, recent, exact=True):     # an older target: the raw-input thread is behind us
            return
        if near(cp, self.last_set):                # mapping rounding / pointer acceleration: adopt it
            self.P[0] += cp[0] - self.last_set[0]
            self.P[1] += cp[1] - self.last_set[1]
            self.last_set = cp
            self.anchor, self.stuck_since, self.foreign_since = cp, None, None
            self.echo_run = 0
            return
        if self._echo(cp, recent, exact=False, near=near):
            return
        explanations = [self.last_set] + [xy for _, xy, _ in recent] + [self.anchor]
        dev = min(max(abs(cp[0] - x), abs(cp[1] - y)) for x, y in explanations)
        if self.cfg.no_yield:
            if self.foreign_since is None:
                self.foreign_since = now
            return
        if dev >= YIELD_JUMP_PX or (self.foreign_since is not None and now - self.foreign_since >= YIELD_PERSIST_S):
            self._yield(cp, dev, now, "salto" if dev >= YIELD_JUMP_PX else "persistente")
        elif self.foreign_since is None:
            self.foreign_since = now

    def _echo(self, cp, recent, exact, near=None):
        """Explains `cp` as an older target still in flight. The raw-input thread applies our moves in order,
        so a sighting of target j retires everything older than j (the next look can only be at j or newer);
        and a cursor that keeps landing two or more targets behind for ECHO_RUN_MAX looks in a row is not an
        echo (a real one resolves in one look) but a hand pushing against us: stop explaining it."""
        match = None
        for i in range(len(recent) - 1, -1, -1):          # newest first
            xy = recent[i][1]
            if (cp == xy) if exact else near(cp, xy):
                match = i
                break
        if match is None:
            return False
        behind = len(recent) - 1 - match
        self.echo_run = self.echo_run + 1 if behind >= 2 else 0
        if self.echo_run > ECHO_RUN_MAX:
            return False
        while self.sent and self.sent[0] is not recent[match]:
            self.sent.popleft()
        self.echo_late += 1
        self.foreign_since = None
        return True

    def _yield(self, cp, dev, now, how):
        self.yield_until = now + YIELD_QUIET_S
        self.yield_cp = cp
        self._pause("ratón físico")
        self._resync(cp)
        self.event("yield", cursor=list(cp), desviacion_px=round(dev), como=how)

    def _stall(self, since):
        """No gyro for longer than --idle-timeout of wall-clock time: pause until the data is fresh again."""
        self.idle_since = since
        self.stall_len = None
        self.fresh_since = None
        self._pause("sin datos")

    def _toggle_user_pause(self, how):
        if "usuario" in self.pause_reasons:
            self.say(f"{how}: reanudo")
            self._resume("usuario")
        else:
            self.say(f"{how}: pausa")
            self._pause("usuario")
        self._beep()

    def _beep(self):
        if getattr(self.cfg, "beep", False) and sys.platform == "win32":
            try:
                import winsound
                winsound.Beep(880, 40)
            except Exception:
                pass

    def _corner(self):
        return self.pointer.corner(self.cfg.kill_corner)

    def _clamp(self, x, y):
        vx, vy, vw, vh = self.pointer.bounds
        x, y = clamp(x, vx, vx + vw - 1), clamp(y, vy, vy + vh - 1)
        k = self.cfg.kill_corner
        if k != "none":
            cx, cy = self._corner()
            if abs(x - cx) < 4 and abs(y - cy) < 4:   # our own moves never enter the kill-corner inset
                sx = 4 if k in ("tl", "bl") else -4   # toward the inside of that corner's monitor
                sy = 4 if k in ("tl", "tr") else -4
                if 4 - abs(x - cx) <= 4 - abs(y - cy):
                    x = cx + sx
                else:
                    y = cy + sy
        return x, y

    # -- messages --
    def handle_message(self, msg, now, now_ms=None):
        self.now = now
        self.now_ms = time.time() * 1000 if now_ms is None else now_ms
        if not isinstance(msg, dict):
            self.malformed += 1
            return
        kind = msg.get("type")
        if kind == "hello":
            self.on_hello(msg)
        elif kind == "watch":
            self.on_watch(bool(msg.get("connected")))
        elif kind == "status":
            source, state = msg.get("source"), msg.get("state")
            if source == "GRAVITY":
                self.gravity_state = state
            elif source in INPUTS:
                before = set(self.input_errors)
                if state == "error":
                    self.input_errors.add(source)
                else:
                    self.input_errors.discard(source)
                if self.input_errors != before:
                    if state == "error":
                        self.say(f"{source} en error: {msg.get('detail') or 'sin detalle'}")
                    self._resolve_modes()
        elif kind == "data":
            self.on_data(msg)

    def on_hello(self, msg):
        avail = msg.get("available")
        self.available = {s for s in avail if isinstance(s, str)} if isinstance(avail, list) else set()
        self.input_errors.clear()
        si = lambda ok: "sí" if ok else "no"
        self.say(f"entradas del reloj: bisel {si('BEZEL' in self.available)} · botón {si('BUTTON' in self.available)}")
        self._resolve_modes()
        self.baseline = None
        self.motion.reset_filters()
        self.motion.theta0 = self.motion.theta
        self.ring.clear()
        self.tap.reset()
        self.dwell.reset()
        self.shake.reset()
        if self.scroll.active:
            self._scroll_exit(timeout=False)
        self.shadow.reset()
        self.rel_pending = [0, 0]
        self.fresh_since = None
        if self.P is not None:
            self.P = [float(self.last_set[0]), float(self.last_set[1])]
        self._pause("calentando")

    def on_watch(self, connected):
        if connected:
            if "reloj desconectado" in self.pause_reasons:
                self._resume("reloj desconectado")
                self.fresh_since = None
                self._pause("calentando")
        else:
            self.say("reloj desconectado: pausa")
            self._pause("reloj desconectado")

    @staticmethod
    def _is_time(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and (not isinstance(v, int) or abs(v) <= 2 ** 53) and math.isfinite(v)

    def _replenish_budget(self):
        """Wall-clock cap: at most max_speed px per monotonic second (plus a BUDGET_S burst), whatever the
        sample clock says, so a backlog can never be applied faster than a live stream."""
        cap = self.cfg.max_speed * BUDGET_S
        if self.budget_now is None:
            self.px_budget = cap
        else:
            self.px_budget = min(cap, self.px_budget + self.cfg.max_speed * max(0.0, self.now - self.budget_now))
        self.budget_now = self.now

    def on_data(self, msg):
        samples = msg.get("samples")
        if not isinstance(samples, list):
            self.malformed += 1
            return
        self.msg_count += 1
        self.msg_travel = 0.0
        self._replenish_budget()
        if "t" in msg and self._is_time(msg["t"]):
            self.bridge_lag = self.now_ms - msg["t"]
            if self.bridge_lag_min is None:
                self.bridge_lag_min = self.bridge_lag
            else:
                rise = BASELINE_RISE_MS_PER_S * max(0.0, self.now_ms - self.bridge_lag_now) / 1000.0
                self.bridge_lag_min = min(self.bridge_lag, self.bridge_lag_min + rise)
            self.bridge_lag_now = self.now_ms
        # latency baseline: the minimum sample age, per-message (newest gyro sample); it falls at once and
        # rises at most BASELINE_RISE_MS_PER_S per second of arrival, so a backlog stays stale
        newest = None
        for s in samples:
            if isinstance(s, (list, tuple)) and len(s) >= 3 and s[0] == "GYROSCOPE" and self._is_time(s[1]) \
                    and abs(self.now_ms - s[1]) <= MAX_AGE_MS and (newest is None or s[1] > newest):
                newest = s[1]
        if newest is not None:
            age = self.now_ms - newest
            if self.baseline is None:
                self.baseline = age
            else:
                rise = BASELINE_RISE_MS_PER_S * max(0.0, self.now_ms - self.baseline_now) / 1000.0
                self.baseline = min(age, self.baseline + rise)
            self.baseline_now = self.now_ms
            self.ages.append(age)
            self.lags.append(age - self.baseline)
        for s in samples:
            if not (isinstance(s, (list, tuple)) and len(s) >= 3):
                self.malformed += 1
                continue
            source, t, values = s[0], s[1], s[2]
            if source not in SOURCES and source not in INPUTS:
                if source not in IGNORED:
                    self.unknown += 1
                continue
            if not self._is_time(t) or abs(self.now_ms - t) > MAX_AGE_MS or not isinstance(values, dict):
                self.malformed += 1
                continue
            if source == "BEZEL":
                self.on_bezel(t, values)
                continue
            if source == "BUTTON":
                self.on_button(t, values)
                continue
            try:
                x, y, z = float(values["x"]), float(values["y"]), float(values["z"])
            except (KeyError, TypeError, ValueError):
                self.malformed += 1
                continue
            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                self.malformed += 1
                continue
            self.feed(source, t, x, y, z, self.now)
        self._flush()
        if self.msg_count == self.resume_msg:   # the message in which a pause ended must move nothing
            self.resume_jump = max(self.resume_jump, self.msg_travel)

    # -- bezel and buttons (bridge wall-clock stamps; no gyro calibration needed) --
    @staticmethod
    def _is_int(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def _bridge_clock_is_ours(self):
        """True when the bridge stamps with this machine's clock (it runs here, or the clocks agree to 0.5 s)."""
        return self.bridge_lag_min is None or abs(self.bridge_lag_min) <= 500

    def _input_stale(self, t):
        """A bezel/button stamp older than INPUT_STALE_MS, measured like the sensors against the smallest
        bridge->here delay seen, so a bridge on another machine (Termux) with its own clock still works."""
        return (self.now_ms - t) - (self.bridge_lag_min or 0.0) > INPUT_STALE_MS

    def on_bezel(self, t, values):
        direction, steps, raw = values.get("direction"), values.get("steps", 1), values.get("raw")
        if direction not in ("CW", "CCW") or not self._is_int(steps) or steps < 1 or (raw is not None and not self._is_int(raw)):
            self.malformed += 1
            return
        steps = min(steps, 10)                          # the kernel sends ±1/±2; more is a decoder gone wrong
        ev = dict(direction=direction, steps=steps, raw=raw, notches=0, applied=False, reason=None)
        if self._input_stale(t):
            self.stale_count += 1
            ev["reason"] = "antiguo"
        elif self.scroll_mode != "bezel":
            ev["reason"] = f"modo {self.scroll_mode}"
        elif not self.inputs_allowed:
            ev["reason"] = "pausa"
        else:
            sign = -1 if direction == "CW" else 1      # CW = forward in the watch's lists = page down = WHEEL_DELTA < 0
            if self.cfg.bezel_invert:
                sign = -sign
            n = max(-100, min(100, sign * steps * self.cfg.bezel_notches))
            self.events.append(("wheel", n))
            self.wheel_notches += abs(n)
            self.say(f"bisel {direction} ×{steps} → rueda {n:+d}")
            ev.update(notches=n, applied=True)
            self.event("wheel", n=n, source="bezel")
        self.event("bezel", **ev)

    def on_button(self, t, values):
        key, pressed = values.get("key"), values.get("pressed")
        if key not in ("back", "home") or not isinstance(pressed, bool):
            self.malformed += 1
            return
        button = "left" if key == "back" else self.cfg.home_key
        ev = dict(key=key, pressed=pressed, action=None, applied=False, reason=None)
        if not pressed and self.held is not None and self.held[0] == button:
            # a release is always honoured (stale or paused): safety beats everything else
            since = self.held[1]
            self.held = None
            self.button_freeze_until = -INF
            self.events.append(("up", button))
            held_ms = round((self.now - since) * 1000)
            self.say(f"botón {key}: suelto → {BUTTON_NAMES[button]} arriba ({held_ms} ms)")
            self._click_done(t, "button", held_ms=held_ms)
            ev.update(action=f"{button}up", applied=True)
        elif key == "back" and self.click_mode != "button":
            ev["reason"] = f"modo {self.click_mode}"
        elif key == "home" and button == "none":
            ev["reason"] = "inicio desactivado"
        elif self._input_stale(t):
            self.stale_count += 1
            ev["reason"] = "antiguo"
        elif not pressed:
            ev["reason"] = "sin pulsación"           # the press happened while paused or in another mode
        elif self.held is not None:
            ev["reason"] = "ya pulsado"
        elif not self.inputs_allowed:
            ev["reason"] = "pausa"
        elif self.now < self.clicks_disabled_until:
            ev["reason"] = "clic desactivado"
        else:
            if self.last_click_pos is not None and t - self.last_click_t < 500 and self.P is not None:
                self._jump_to(*self.last_click_pos)  # double click: same spot
            self.events.append(("down", button))
            self.held = (button, self.now)
            self.button_freeze_until = self.now + BUTTON_FREEZE_S
            self.say(f"botón {key}: pulsado → {BUTTON_NAMES[button]} abajo")
            ev.update(action=f"{button}down", applied=True)
        self.event("button", **ev)

    def feed(self, source, t_ms, x, y, z, now):
        age = self.now_ms - t_ms
        lag = age - (0.0 if self.baseline is None else self.baseline)
        stale = lag > STALE_MS or (self.loopback and self._bridge_clock_is_ours() and age > ABS_STALE_MS)
        self.counts[source] += 1
        self.hz_counts[source] += 1
        self.raw_ring.append((source, t_ms, x, y, z))
        if self.rate_t0 is None:
            self.rate_t0 = now
        if stale:
            self.stale_count += 1
        if source == "GRAVITY":
            self.motion.feed_gravity(t_ms, x, y, z)
            if self.calib_mode == "forearm":
                self._calib_forearm(t_ms, x, y, z)
        elif source == "ACCELERATION":
            self.last_accel_arrival = now
            if self.accel_lost:
                self.accel_lost = False
                self.say("acelerómetro de vuelta: clic por toque activo")
            self.motion.feed_accel(t_ms, x, y, z)
            self._feed_accel(t_ms, z, lag)
        else:
            self._feed_gyro(t_ms, x, y, z, lag, stale, now)

    def _tap_allowed(self, t, lag):
        return ("tap" in self.click_mode and self.motion.calibrated and lag < FRESH_MS and not self.paused
                and not self.scroll.active and t >= self.gap_blank_until and self.now >= self.clicks_disabled_until
                and self.calib_mode is None and not self.accel_lost)

    def _feed_accel(self, t, az, lag):
        cand = self.tap.feed_accel(t, az, self._tap_allowed(t, lag))
        if cand:
            self.event("tap_candidate", peak=cand["peak"], armed=cand["armed"], pre_max=cand["pre_at_arm"])
        if cand and cand["armed"]:
            self._rewind(t - 80)
            self.tap_pos = (self.P[0], self.P[1]) if self.P else None
        elif cand and self.tap.pending is not cand:   # arrived while another candidate was being decided
            self.log_gesture(t, "tap", cand["peak"], verdict="ocupado")
            self.event("tap_rejected", verdict="ocupado", peak=cand["peak"])

    def _feed_gyro(self, t, x, y, z, lag, stale, now):
        prev = self.last_gyro_arrival
        if prev is not None and now - prev > self.cfg.idle_timeout and "sin datos" not in self.pause_reasons:
            # the ticker could not run while this process was blocked: what arrives now is a backlog
            self.stalls_on_arrival += 1
            self._stall(prev)
        self.last_gyro_arrival, self.last_gyro_t, self.last_lag = now, t, lag
        if self.first_gyro_t is None:
            self.first_gyro_t = t
        fresh = lag < FRESH_MS and not stale
        if fresh:
            if self.fresh_since is None:
                self.fresh_since = now
        else:
            self.fresh_since = None
        if "sin datos" in self.pause_reasons:
            if self.stall_len is None:
                self.stall_len = now - self.idle_since     # the stall itself, first message after it
                self.stalls.append(self.stall_len)
            if self.fresh_since is not None and now - self.fresh_since >= 0.3:
                self._resume("sin datos", f"sin datos {self.stall_len:.1f} s")
                self.recal_check_at = now + 10.0
        if "calentando" in self.pause_reasons and self.fresh_since is not None and now - self.fresh_since >= 1.0:
            self._resume("calentando")
        armed_tap = self.tap.pending is not None and self.tap.pending["armed"]
        bias_ok = not (self.scroll.active or armed_tap or t < self.gap_blank_until or stale)
        m = self.motion
        step = m.feed_gyro(t, x, y, z, bias_ok=bias_ok, theta0_ok=not self.scroll.active)
        self.last_step = step
        if m.calib_warned:
            if m.calib_warned == "background":
                self.say("sin reposo en 10 s: mantengo el sesgo anterior")
            else:
                self.say(f"calibrando: sin reposo en {m.calib_waited * 10} s (motivo: {m.calib_warned}); "
                         f"apoya la muñeca en la mesa y mantenla quieta")
            m.calib_warned = False
        if step.just_calibrated:
            self._on_calibrated(now)
        if not m.calibrated:
            return
        if step.recovered:
            self.say(f"sesgo recuperado {m.bias[0]:+.2f} {m.bias[1]:+.2f} {m.bias[2]:+.2f} °/s "
                     f"(el giroscopio llevaba {RECOVER_S:.0f} s en reposo fuera del sesgo)")
            m.reset_filters()
        if step.stationary:
            self.recal_check_at = None
        elif self.recal_check_at is not None and now >= self.recal_check_at:
            self.recal_check_at = None
            self.say("sin reposo tras reanudar: recalibro el sesgo en segundo plano (solo con la muñeca quieta)")
            m.start_calibration(background=True)
        if step.gap:
            self._on_gap(t, step.delta)
        self._pose_gate(t, step.gf)
        # shake is evaluated even while paused: it is how the user resumes
        start = self.shake.feed(t, step.omega)
        if start is not None:
            self.shake_times.append(self.t_s(t))
            if not self.paused or "usuario" in self.pause_reasons:
                self._rewind(start - 100)
            self.frozen_until = max(self.frozen_until, t + 300)
            self.pending_reset = True
            self._toggle_user_pause("sacudida")
        if self.calib_mode == "axes":
            self._calib_axes(step)
        frozen = self.frozen(t)
        if self.pending_reset and not frozen:
            self.pending_reset = False
            m.reset_filters()
            if self.P is not None:
                self.P = [float(round(self.P[0])), float(round(self.P[1]))]
        gest_ok = fresh and not self.paused and t >= self.gap_blank_until and self.calib_mode is None
        # scroll by forearm roll
        if self.scroll_mode == "roll":
            allowed = gest_ok and not frozen and self.tap.pending is None and not stale
            for ev in self.scroll.feed(t, step.e, step.theta_dot, step.rho, allowed):
                if ev[0] == "enter":
                    self._rewind(t - 150)
                    self.say(f"scroll: entro (e={ev[1]:+.0f}°)")
                    self.log_gesture(t, "scroll", peak=ev[1], verdict="entro")
                    self.event("scroll_enter", e=round(ev[1]))
                elif ev[0] == "wheel":
                    self.events.append(("wheel", ev[1]))
                    self.wheel_notches += abs(ev[1])
                    self.say(f"rueda {ev[1]:+d} (e={step.e:+.0f}°)")
                    self.event("wheel", n=ev[1], source="roll")
                else:
                    self._scroll_exit(timeout=ev[1], t=t)
            frozen = self.frozen(t)
            # what the detector would do regardless of pause/freeze: the replay's signal-level metric
            self.shadow.feed(t, step.e, step.theta_dot, step.rho,
                             not stale and t >= self.gap_blank_until and self.calib_mode is None)
        # tap decision (gyro time)
        res = self.tap.feed_gyro(t, step.omega_mag)
        if res is not None:
            self._tap_decided(res, t)
            frozen = self.frozen(t)
        # cursor motion
        moved = 0.0
        self.rel_step = (0, 0)
        apply = (not stale and not frozen and not self.paused and not self.scroll.active
                 and self.msg_count != self.resume_msg and self.calib_mode is None)
        if apply:
            moved = self._apply_delta(t, step)
        elif frozen and not self.paused:
            self.frozen_s += step.dt
        if self.motion_hook and not stale:   # what the pointer chain outputs, applied or not (replay metrics)
            self.motion_hook(t, step.dx, step.dy, self.P[0] if self.P else 0.0, self.P[1] if self.P else 0.0, apply)
        if self.P is not None:
            self.ring.append((t, self.P[0], self.P[1]))
        # dwell
        if "dwell" in self.click_mode and self.P is not None:
            enabled = gest_ok and not frozen and not stale and self.now >= self.clicks_disabled_until
            if self.dwell.feed(t, step.rho, (self.P[0], self.P[1]), moved, enabled):
                self.dwell_times.append(self.t_s(t))
                self._click(t, "dwell")
                self.log_gesture(t, "dwell", verdict="confirmado")

    def _on_calibrated(self, now):
        m = self.motion
        self.say(f"sesgo {m.bias[0]:+.2f} {m.bias[1]:+.2f} {m.bias[2]:+.2f} °/s (ventana en reposo, p2p {m.bias_p2p:.2f})")
        self.bias_log_at = now
        self.bias_initial = tuple(m.bias)
        self.event("calibrated", bias=list(m.bias), p2p=m.bias_p2p)
        cp = self.pointer.cursor_pos()
        if cp is None:
            vx, vy, vw, vh = self.pointer.bounds
            cp = (vx + vw // 2, vy + vh // 2)
        self._resync(cp)
        self.resume_msg = self.msg_count
        if self.pointer.__class__ is Win32Pointer and self.cfg.move == "absolute":
            cp = self.pointer.cursor_pos()
            if cp is not None:               # probe: sends and reads the same point, so a stale echo cannot fool it
                self.pointer.move_to(*cp)
                self.sent.append((now, cp, (0, 0)))
                rb = self.pointer.cursor_pos()
                if rb is not None:
                    off = max(abs(rb[0] - cp[0]), abs(rb[1] - cp[1]))
                    if off >= 1:
                        self.say(f"aviso: mapeo absoluto desviado {off} px")

    def _on_gap(self, t, delta):
        self.say(f"hueco {delta:.0f} ms")
        self.gaps.append((self.t_s(t), delta))
        self.gap_blank_until = t + GAP_BLANK_MS
        if self.tap.pending is not None:
            self.tap.pending["armed"] = False
        if self.scroll.active:
            self._scroll_exit(timeout=False, t=t)
        self.scroll.reset()
        self.shadow.reset()
        self.dwell.reset()
        self.shake.reset()
        self.frozen_until = -INF

    def _pose_gate(self, t, gf):
        a = abs(gf)
        if a > 0.87:
            self.pose_high_since = t if self.pose_high_since is None else self.pose_high_since
            if t - self.pose_high_since >= 300 and "brazo caído" not in self.pause_reasons:
                self._pause("brazo caído")
        else:
            self.pose_high_since = None
        if a < 0.80:
            self.pose_low_since = t if self.pose_low_since is None else self.pose_low_since
            if t - self.pose_low_since >= 300 and "brazo caído" in self.pause_reasons:
                self._resume("brazo caído")
        else:
            self.pose_low_since = None

    def _scroll_exit(self, timeout, t=None):
        self.scroll.active = False
        if timeout:
            self.motion.theta0 = self.motion.theta
        self.say("scroll: salgo" + (" (tiempo agotado)" if timeout else ""))
        self.event("scroll_exit", timeout=bool(timeout))
        if t is not None:
            self.frozen_until = max(self.frozen_until, t + 200)
        self.pending_reset = True

    def _tap_decided(self, p, t):
        self.log_gesture(p["t"], "tap", p["peak"], p["width"], p["baseline"], p["pre_max"], p["post_max"], p["verdict"])
        if p["verdict"].startswith("confirmado"):
            self.tap_times.append(self.t_s(p["t"]))
        else:
            self.event("tap_rejected", verdict=p["verdict"], peak=p["peak"], width=p["width"], baseline=p["baseline"],
                       pre_max=p["pre_max"], post_max=p["post_max"])
        if not p["armed"]:
            return
        if p["verdict"] == "confirmado" and self.now >= self.clicks_disabled_until:
            if self.last_click_pos is not None and p["t"] - self.last_click_t < 500:
                self._jump_to(*self.last_click_pos)   # double click: same spot
            elif self.tap_pos is not None:
                self._jump_to(*self.tap_pos)
            else:
                self.force_move = True
            self._click(p["t"], f"tap, pico {abs(p['peak']):.1f} m/s²")
            self.last_click_t = p["t"]
            self.frozen_until = max(self.frozen_until, p["t"] + 300)
        else:
            self.frozen_until = -INF
            if p["verdict"] == "sin acelerómetro":
                self.say("toque sin decidir: el acelerómetro dejó de llegar")
        self.pending_reset = True

    def _click(self, t, how):
        self.events.append(("click",))
        self._click_done(t, how)

    def _click_done(self, t, how, held_ms=None):
        """Bookkeeping shared by tap, dwell and button clicks (the [DOWN, UP] or the UP is already queued)."""
        self.clicks += 1
        self.last_click_pos = (round(self.P[0]), round(self.P[1])) if self.P else None
        self.last_click_t = t
        self.say(f"clic ({how})")
        self.event("click", how=how.split(",")[0], pos=list(self.last_click_pos) if self.last_click_pos else None,
                   held_ms=held_ms)
        self._beep()
        self.dwell.reset()                 # a tap click must not be followed by a dwell click on the same spot
        self.click_times.append(self.now)
        while self.click_times and self.click_times[0] < self.now - 60:
            self.click_times.popleft()
        if len(self.click_times) >= self.cfg.max_clicks_per_min:
            self.clicks_disabled_until = self.now + 60
            self.click_times.clear()
            self.say("demasiados clics: desactivo clic 60 s")

    def _apply_delta(self, t, step):
        if self.P is None:
            return 0.0
        dx, dy = step.dx, step.dy
        if dx == 0.0 and dy == 0.0:
            if step.zero_remainder:
                self.P = [float(round(self.P[0])), float(round(self.P[1]))]
            return 0.0
        d = math.hypot(dx, dy)
        if d > self.px_budget:             # wall-clock cap (see _replenish_budget)
            f = max(0.0, self.px_budget) / d
            dx, dy, d = dx * f, dy * f, d * f
            self.capped += 1
            if d == 0.0:
                return 0.0
        self.px_budget -= d
        nx, ny = self._clamp(self.P[0] + dx, self.P[1] + dy)
        if self.cfg.move == "relative":    # the delta sent is the clamped integer cursor's, never into the inset
            mx, my = round(nx) - round(self.P[0]), round(ny) - round(self.P[1])
            self.rel_pending[0] += mx
            self.rel_pending[1] += my
            self.rel_step = (mx, my)
        self.P = [nx, ny]
        self.travel += d
        self.msg_travel += d
        self.state_dx += dx
        self.state_dy += dy
        self.max_speed = max(self.max_speed, step.speed)
        return d

    def _jump_to(self, x, y):
        """Put P (and, at the next flush, the cursor) at a known position. Relative mode queues the
        integer difference, so the pointer lands at (round(x), round(y)) whatever was already flushed."""
        if self.cfg.move == "relative":
            self.rel_pending[0] += round(x) - round(self.P[0])
            self.rel_pending[1] += round(y) - round(self.P[1])
        self.P = [float(x), float(y)]
        self.force_move = True

    def _rewind(self, t_target):
        if self.P is None or not self.ring:
            return
        entry = next((e for e in reversed(self.ring) if e[0] <= t_target), self.ring[0])
        self._jump_to(entry[1], entry[2])

    def _flush(self):
        """Reads the cursor BEFORE moving (a read-back right after SendInput may still be the previous
        target: _observe_cursor explains it instead), then sends the new target and the queued buttons.
        Buttons and wheel go out even before the gyro is calibrated (P is None): they need no bias."""
        cp = self.pointer.cursor_pos()
        self._observe_cursor(cp, self.now)
        if self.yield_until is not None or cp is None:   # the user owns the cursor: no move, no DOWN on it
            self._release_held("pausa")
            self.events = [ev for ev in self.events if ev[0] != "down"]
        elif self.P is None:
            pass
        elif self.cfg.move == "relative":
            if self.rel_pending != [0, 0]:
                mx, my = self.rel_pending
                self.pointer.move_by(mx, my)
                self.moves += 1
                self.rel_pending = [0, 0]
                base = self.last_set if self.last_set is not None else (round(self.P[0]) - mx, round(self.P[1]) - my)
                self.last_set = (base[0] + mx, base[1] + my)      # expected; acceleration is adopted at the next look
                self.sent.append((self.now, self.last_set, (mx, my)))
            self.force_move = False
        else:
            rx, ry = round(self.P[0]), round(self.P[1])
            if self.force_move or (rx, ry) != self.last_set:
                self.pointer.move_to(rx, ry)
                self.moves += 1
                self.last_set = (rx, ry)
                self.sent.append((self.now, self.last_set, (0, 0)))
                self.force_move = False
        for ev in self.events:
            if ev[0] == "click":
                self.pointer.click()
            elif ev[0] == "wheel":
                self.pointer.wheel(ev[1])
            elif ev[0] == "down":
                self.pointer.press(ev[1])
            elif ev[0] == "up":
                self.pointer.release(ev[1])
        self.events.clear()

    # -- periodic (monotonic clock) --
    def tick(self, now):
        self.now = now
        if self.kill_requested:
            return
        if self.last_bounds_refresh is None or now - self.last_bounds_refresh >= 2.0:
            self.last_bounds_refresh = now
            self.pointer.refresh_bounds()
        if self.cfg.pause_key != "none" and self.pointer.pause_key_pressed():
            self._toggle_user_pause("tecla Pausa")
        if self.held is not None and now - self.held[1] >= BUTTON_HOLD_MAX_S:
            self.say(f"botón mantenido {BUTTON_HOLD_MAX_S:.0f} s: lo suelto")
            self._release_held(f"{BUTTON_HOLD_MAX_S:.0f} s")
        if self.hz_t0 is None:
            self.hz_t0 = now
        elif now - self.hz_t0 >= 1.0:
            dt = now - self.hz_t0
            self.hz = {SHORT[s]: round(self.hz_counts[s] / dt, 1) for s in SOURCES}
            self.hz_counts.clear()
            self.hz_t0 = now
        if (self.last_gyro_arrival is not None and now - self.last_gyro_arrival > self.cfg.idle_timeout
                and "sin datos" not in self.pause_reasons):
            self._stall(self.last_gyro_arrival)
        if (self.last_accel_arrival is not None and not self.accel_lost and now - self.last_accel_arrival > ACCEL_STALE_S
                and self.last_gyro_arrival is not None and now - self.last_gyro_arrival <= self.cfg.idle_timeout):
            self.accel_lost = True                # the gyro keeps coming: only the taps are lost
            self.say("acelerómetro sin datos: desactivo el clic por toque hasta que vuelva")
            if self.tap.pending is not None and self.tap.pending["armed"]:
                self.tap.pending["armed"] = False
                self.frozen_until = -INF
        if self.bias_log_at is not None and now - self.bias_log_at >= 60:
            self.bias_log_at = now
            m = self.motion.bias
            self.say(f"sesgo {m[0]:+.2f} {m[1]:+.2f} {m[2]:+.2f} °/s")
        cp = self.pointer.cursor_pos()
        if cp is None:                            # lock screen / UAC: no corner test on a made-up (0, 0)
            self.corner_ticks = 0
            self._pause("escritorio no disponible")
            return
        if "escritorio no disponible" in self.pause_reasons:
            self._resume("escritorio no disponible", cp=cp)
        if self.cfg.kill_corner != "none":
            cx, cy = self._corner()
            self.corner_ticks = self.corner_ticks + 1 if abs(cp[0] - cx) <= 2 and abs(cp[1] - cy) <= 2 else 0
            # Hold, not brush: the physical mouse passes through the corner all the time (window controls,
            # menus), so the kill needs KILL_CORNER_S of parking there.
            if self.corner_ticks >= KILL_CORNER_TICKS:
                self.say("interruptor de emergencia: cursor en la esquina → salgo")
                self.pointer.release_all()
                self.kill_requested = True
                return
        if self.P is not None:
            self._observe_cursor(cp, now)

    # -- calibration helpers --
    def _calib_axes(self, step):
        if self.calib_done:
            return
        if abs(step.yaw) > 60:
            self.say(f"primer giro: {'izquierda' if step.yaw > 0 else 'derecha'} (yaw {step.yaw:+.0f} °/s)")
            self.calib_done = True
        elif abs(step.pitch) > 60:
            self.say(f"primer giro: {'arriba' if step.pitch > 0 else 'abajo'} (pitch {step.pitch:+.0f} °/s)")
            self.calib_done = True

    def _calib_forearm(self, t, x, y, z):
        if self.calib_done:
            return
        self.calib_g.append((t, x, y, z))
        while self.calib_g[0][0] < t - 1000:
            self.calib_g.popleft()
        if len(self.calib_g) < 80 or t - self.calib_g[0][0] < 900:
            return
        means = [statistics.fmean(c) for c in zip(*[s[1:] for s in self.calib_g])]
        for i, name in enumerate("xy"):
            if abs(means[i]) > 8.5:
                sign = "-" if means[i] > 0 else "+"
                self.say(f"brazo colgando: gravedad en {name} = {means[i]:+.2f} m/s² → usa --forearm {sign}{name}")
                self.calib_done = True
                return

    # -- reporting --
    def status(self):
        reasons = list(self.pause_reasons)
        ages = sorted(self.ages)
        lags = sorted(self.lags)
        q = lambda v, p: v[min(len(v) - 1, int(p * len(v)))] if v else None
        held = self.held
        return {
            "estado": "calibrando" if not self.motion.calibrated else "pausa" if reasons else "scroll" if self.scroll.active else "activo",
            "pausa": ", ".join(reasons) if reasons else None,
            "scroll": self.scroll.active,
            "clics": self.clicks, "rueda": self.wheel_notches,
            "descartadas": self.stale_count, "malformadas": self.malformed, "desconocidas": self.unknown,
            "mov_px": round(self.travel), "retraso_ms": q(ages, 0.5), "retraso_p95": q(ages, 0.95),
            "lag_ms": q(lags, 0.5), "lag_p95": q(lags, 0.95), "puente_ms": self.bridge_lag,
            "acelerometro": not self.accel_lost,
            "boton": {"held": held[0] if held else None, "ms": round((self.now - held[1]) * 1000) if held else 0},
            "modos": {"click": self.click_mode, "scroll": self.scroll_mode},
            "entradas": {"bezel": "BEZEL" in self.available and "BEZEL" not in self.input_errors,
                         "button": "BUTTON" in self.available and "BUTTON" not in self.input_errors},
            "eco_tarde": self.echo_late,
        }

    def state_message(self):
        """The control channel's `state` (25 Hz): what the page's live meters and tests consume."""
        st = self.status()
        s = self.last_step
        m = self.motion
        msg = {
            "type": "state", "t": round(time.time() * 1000), "estado": st["estado"], "pausa": st["pausa"],
            "rates": {"yaw": s.yaw, "pitch": s.pitch, "roll": s.roll, "yaw_f": s.rf[0], "pitch_f": s.rf[1]},
            "delta": {"dx": self.state_dx, "dy": self.state_dy},
            "cursor": list(self.last_cursor) if self.last_cursor else None,
            "bias": list(m.bias),
            "retraso_ms": st["retraso_ms"] if self.loopback else st["lag_ms"],
            "hz": dict(self.hz), "clics": st["clics"], "rueda": st["rueda"],
            "entradas": st["entradas"], "efectivo": st["modos"], "boton": st["boton"],
            "calibrado": m.calibrated, "eco_tarde": self.echo_late, "descartadas": st["descartadas"],
            "tap": {"candidatos": self.tap.candidates, "confirmados": self.tap.confirmed},
        }
        self.state_dx = self.state_dy = 0.0
        return _jsonable(msg)

    def apply_params(self, clean):
        """Validated tunables (see validate_params) applied live; returns the names that changed."""
        changed = []
        for name, value in clean.items():
            tn = TUNABLES[name]
            stored = (not value) if name == "yield" else int(value) if name == "accel" else value
            old = getattr(self.cfg, tn.attr)
            if old == stored:
                continue
            setattr(self.cfg, tn.attr, stored)
            changed.append(name)
            shown = (lambda v: (not v) if name == "yield" else bool(v) if name == "accel" else v)
            self.say(f"ajuste: {name} {shown(old)} → {shown(stored)}")
        self.cfg.tap_post_ms = max(80, self.cfg.tap_post_ms)
        for f in (self.motion.fx, self.motion.fy):   # the filters copied the values at construction
            f.mincutoff, f.beta, f.dcutoff = self.cfg.mincutoff, self.cfg.beta, self.cfg.dcutoff
        self._resolve_modes()
        return changed

    def record_gesture(self, label, root=None):
        """Writes the last 3 s of the three sensors to recordings/gestures/<label>-<stamp>.csv -> (path, rows)."""
        label = re.sub(r"[^A-Za-z0-9_-]+", "-", str(label)).strip("-")[:32] or "gesto"
        root = root or gestures_dir()
        os.makedirs(root, exist_ok=True)
        newest = max((r[1] for r in self.raw_ring), default=0)
        rows = sorted((r for r in self.raw_ring if r[1] >= newest - 3000), key=lambda r: (r[1], r[0]))
        path = os.path.join(root, f"{label}-{time.strftime('%Y%m%d-%H%M%S')}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["source", "t_ms", "x", "y", "z"])
            for source, t_ms, x, y, z in rows:
                wr.writerow([source, round(t_ms), f"{x:.4f}", f"{y:.4f}", f"{z:.4f}"])
        self.say(f"gesto grabado: {os.path.basename(path)} ({len(rows)} muestras)")
        self.event("gesture", path=repo_relative(path), muestras=len(rows))
        return path, len(rows)

    def status_line(self, now):
        st = self.status()
        dt = max(1e-6, now - (self.rate_t0 or now))
        rates = " ".join(f"{SHORT[src]} {self.counts[src] / dt:.1f} Hz" for src in SOURCES)
        self.counts.clear()
        self.rate_t0 = now
        if st["retraso_ms"] is None:
            lat = "retraso —"
        elif self.loopback:
            lat = f"retraso {st['retraso_ms']:.0f} ms (p95 {st['retraso_p95']:.0f})"
        else:
            lat = f"retraso rel. {st['lag_ms']:.0f} ms (p95 {st['lag_p95']:.0f})"
        parts = [rates, lat]
        if self.loopback and st["puente_ms"] is not None:
            parts.append(f"puente→yo {st['puente_ms']:.0f} ms")
        parts += [f"mov {st['mov_px']} px", f"clics {st['clics']}", f"rueda {st['rueda']}", f"descartadas {st['descartadas']}"]
        if self.accel_lost:
            parts.append("sin acelerómetro")
        if self.held is not None:
            parts.append("botón ↓")
        if self.echo_late:
            parts.append(f"eco tarde {self.echo_late}")
        self.ages.clear()
        self.lags.clear()
        if self.last_gyro_arrival is None:
            state = "esperando reloj…"
        elif st["pausa"]:
            state = f"pausa: {st['pausa']}"
            if "sin datos" in self.pause_reasons:
                state += f" {now - self.idle_since:.1f} s"
        else:
            state = st["estado"]
        return " · ".join(parts + [state])

    def shutdown(self):
        self._release_held("cierre")
        self.pointer.release_all()
        if self.gesture_file:
            self.gesture_file.close()
            self.gesture_file = None


REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def gestures_dir():
    return os.path.join(REPO_ROOT, "recordings", "gestures")


def repo_relative(path):
    try:
        rel = os.path.relpath(path, REPO_ROOT)
    except ValueError:                     # another drive on Windows
        return path
    return path if rel.startswith("..") else rel.replace(os.sep, "/")


def list_gestures(root=None, limit=50):
    """The control channel's `gestures` reply: newest first."""
    root = root or gestures_dir()
    files = []
    try:
        for name in os.listdir(root):
            if name.lower().endswith(".csv"):
                st = os.stat(os.path.join(root, name))
                files.append({"name": name, "bytes": st.st_size, "t": round(st.st_mtime * 1000)})
    except OSError:
        pass
    files.sort(key=lambda f: f["t"], reverse=True)
    return {"type": "gestures", "dir": repo_relative(root), "files": files[:limit]}


# ---------- sources: (msg, monotonic now) ----------

async def ui_source(url, retry_s=2.0):
    """Explicit retry loop (fixed 2 s, one log line per attempt) instead of websockets' silent
    randomised back-off, which grows to 90 s and logs nowhere; a bad URL or a 404 is fatal."""
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidURI, WebSocketException
    attempt, was_connected = 0, False
    while True:
        attempt += 1
        log(f"conectando a {url}…" if attempt == 1 else f"reconectando a {url} (intento {attempt})…")
        try:
            async with connect(url, compression=None, max_queue=64, open_timeout=5) as ws:
                log(f"conectado a {url}")
                attempt, was_connected = 0, True
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except ValueError:
                        continue
                    yield msg, time.monotonic()
                log("el servidor cerró la conexión")
        except InvalidURI:
            raise
        except InvalidHandshake as e:               # 404, wrong path, not a WebSocket server: no point retrying
            raise RuntimeError(f"{url}: {e}") from e
        except ConnectionClosed as e:
            log(f"conexión cerrada ({e.rcvd or e.sent or 'sin código'})")
        except (OSError, TimeoutError, WebSocketException) as e:
            log(f"sin conexión con {url}: {e or type(e).__name__}; reintento en {retry_s:g} s")
        if was_connected:
            yield {"type": "watch", "connected": False}, time.monotonic()
            was_connected = False
        await asyncio.sleep(retry_s)


async def sdb_source(device, interval, flush_ms=10):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sdb_client import SdbConnection
    host, _, port = device.partition(":")
    port = int(port or 26101)
    sensors = (("gyroscope", "GYROSCOPE"), ("accelerometer", "ACCELERATION"), ("gravity", "GRAVITY"))
    while True:
        try:
            conn = await SdbConnection(host, port).connect(timeout=600)
        except (OSError, asyncio.TimeoutError) as e:
            log(f"sdb {host}:{port}: {e or 'sin respuesta'}; reintento en 2 s")
            await asyncio.sleep(2)
            continue
        log(f"conectado por sdb a {host}:{port} · reloj {conn.model}")
        try:
            await asyncio.wait_for(conn.run("pkill sensorctl"), 10)
        except Exception as e:
            log(f"sdb {host}:{port}: {e or type(e).__name__}; reintento en 2 s")
            conn.close()
            await asyncio.sleep(2)
            continue
        offsets, buffer = {}, []

        def map_time(source, ts_ms):      # same anchoring as Bridge.map_time
            offset = time.time() * 1000 - ts_ms
            cur = offsets.get(source)
            offsets[source] = offset if cur is None or offset < cur else cur + OFFSET_LEAK_MS
            return round(ts_ms + offsets[source])

        async def read_sensor(name, source):
            stream = await conn.shell(f"echo 0 | sensorctl test {name} --interval={interval}")
            async for line in stream.lines():
                parts = line.split()
                if len(parts) != 4 or not parts[0].isdigit():
                    continue
                try:
                    buffer.append([source, map_time(source, int(parts[0]) / 1000),
                                   {"x": float(parts[1]), "y": float(parts[2]), "z": float(parts[3])}])
                except ValueError:
                    continue

        readers = [asyncio.create_task(read_sensor(n, s)) for n, s in sensors]
        yield {"type": "hello", "app": f"air-mouse {VERSION}"}, time.monotonic()
        yield {"type": "watch", "connected": True}, time.monotonic()
        try:
            while not all(r.done() for r in readers):
                await asyncio.sleep(flush_ms / 1000)
                if buffer:
                    batch, buffer[:] = buffer[:], []
                    yield {"type": "data", "t": round(time.time() * 1000), "samples": batch}, time.monotonic()
            log("el reloj cerró la conexión")
        finally:
            for r in readers:
                r.cancel()
            try:
                await asyncio.wait_for(conn.run("pkill sensorctl"), 5)
            except Exception:
                pass
            conn.close()
        yield {"type": "watch", "connected": False}, time.monotonic()
        await asyncio.sleep(2)
        log("reconectando…")


# ---------- replay harness ----------

def load_replay(path):
    """Rows of the three CSVs grouped by distinct t_recv_ms into /ui-shaped messages (file order kept)."""
    rows, per_source = [], {}
    for source in SOURCES:
        file = os.path.join(path, f"{source}.csv")
        if not os.path.exists(file):
            continue
        with open(file, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            n = 0
            for r in reader:
                try:
                    rows.append((int(float(r[1])), int(float(r[0])), source, float(r[2]), float(r[3]), float(r[4])))
                    n += 1
                except (ValueError, IndexError):
                    continue
            per_source[source] = n
    rows.sort(key=lambda r: (r[0], r[1]))
    messages = []
    for t_recv, t_watch, source, x, y, z in rows:
        if not messages or messages[-1][0] != t_recv:
            messages.append((t_recv, {"type": "data", "samples": []}))
        messages[-1][1]["samples"].append([source, t_watch, {"x": x, "y": y, "z": z}])
    return messages, per_source


def replay(path, cfg, realtime=False):
    messages, per_source = load_replay(path)
    if not messages:
        emit(f"replay {path}: no hay CSV con muestras")
        return {"duracion_s": 0.0, "error": "sin datos"}
    pointer = DryRunPointer((0, 0, 1920, 1080), quiet=not realtime)
    am = AirMouse(cfg, pointer)
    gyro = [(s[1], s[2]["x"], s[2]["y"], s[2]["z"]) for _, m in messages for s in m["samples"] if s[0] == "GYROSCOPE"]
    t0 = gyro[0][0] if gyro else messages[0][0]
    recv0 = messages[0][0]
    am.time_label = lambda: f"{(am.now_ms - recv0) / 1000:8.2f}s"
    # per 1-s window (by gyro sample time): raw p2p, what the pointer chain output (deadzone/filter/bias,
    # whether or not the state machine let it through) and the integer cursor's excursion
    win_samples, win_travel, win_exc, win_start = {}, Counter(), {}, {}

    def hook(t, dx, dy, px, py, applied):
        k = int((t - t0) // 1000)
        win_travel[k] += math.hypot(dx, dy)
        if k not in win_start:
            win_start[k] = (round(px), round(py))
        sx, sy = win_start[k]
        win_exc[k] = max(win_exc.get(k, 0), max(abs(round(px) - sx), abs(round(py) - sy)))
    am.motion_hook = hook
    for t, x, y, z in gyro:
        win_samples.setdefault(int((t - t0) // 1000), []).append((x, y, z))
    emit(f"replay {path}: {(gyro[-1][0] - t0) / 1000:.1f} s · " +
          " ".join(f"{SHORT[s]} {per_source.get(s, 0)}" for s in SOURCES) +
          f" muestras · mensajes {len(messages)} (máx {max(len(m['samples']) for _, m in messages)} muestras, "
          f"{max(sum(1 for s in m['samples'] if s[0] == 'GYROSCOPE') for _, m in messages)} de giro)")
    next_tick = recv0
    start_mono = time.monotonic()
    for t_recv, msg in messages:
        while next_tick <= t_recv:
            am.tick(next_tick / 1000.0)
            next_tick += 50
        if realtime:
            wait = (t_recv - recv0) / 1000.0 - (time.monotonic() - start_mono)
            if wait > 0:
                time.sleep(min(wait, 5.0))
        am.handle_message(msg, t_recv / 1000.0, t_recv)
    am.tick((t_recv + 50) / 1000.0)
    am.shutdown()
    # ---- windows ----
    rest, tremor = [], []
    for k, s in win_samples.items():
        if len(s) < 80:
            continue
        p2p = max(max(c) - min(c) for c in zip(*s))
        if p2p < 1.0:
            rest.append(k)
        elif p2p < 4.0:
            tremor.append(k)
    rest_px = [win_travel[k] for k in rest]
    rest_exc = max((win_exc.get(k, 0) for k in rest), default=0)
    tremor_px = [win_travel[k] for k in tremor]
    # ---- timing from the rows ----
    dts = Counter()
    gaps = []
    for i in range(1, len(gyro)):
        d = gyro[i][0] - gyro[i - 1][0]
        dts[d] += 1
        if d > GAP_MS:
            gaps.append(((gyro[i - 1][0] - t0) / 1000, d))
    n_dt = max(1, sum(dts.values()))
    dt_hist = {k: round(100 * v / n_dt, 1) for k, v in sorted(dts.items()) if v / n_dt >= 0.005}
    grecv = [t for t, m in messages if any(s[0] == "GYROSCOPE" for s in m["samples"])]
    stalls = [grecv[i] - grecv[i - 1] for i in range(1, len(grecv))]
    ages = sorted(t_recv - s[1] for t_recv, m in messages for s in m["samples"] if s[0] == "GYROSCOPE")
    q = lambda v, p: v[min(len(v) - 1, int(p * len(v)))] if v else 0
    dur = (gyro[-1][0] - t0) / 1000.0
    mins = max(dur / 60.0, 1e-6)
    sin_datos = list(am.stalls)
    if "sin datos" in am.pause_reasons and am.stall_len is None:
        sin_datos.append(am.now - am.idle_since)
    res = {
        "duracion_s": round(dur, 1), "mensajes": len(messages),
        "reposo_ventanas": len(rest), "reposo_px_s_medio": statistics.fmean(rest_px) if rest_px else 0.0,
        "reposo_px_s_max": max(rest_px, default=0.0), "reposo_excursion_px": rest_exc,
        "temblor_ventanas": len(tremor), "temblor_px_s_medio": statistics.fmean(tremor_px) if tremor_px else 0.0,
        "sesgo_inicial": getattr(am, "bias_initial", None), "sesgo_final": tuple(am.motion.bias),
        "sesgo_actualizaciones": am.motion.bias_updates, "sesgo_paso_max": am.motion.bias_max_step,
        "tap_candidatos": am.tap.candidates, "tap_forma": am.tap.shape_ok, "tap_puertas": am.tap.gate_ok,
        "tap_confirmados": am.tap.confirmed, "clics_por_min": am.tap.confirmed / mins, "tap_instantes": am.tap_times,
        "dwell": am.dwell.fires, "dwell_por_min": am.dwell.fires / mins, "dwell_instantes": am.dwell_times,
        "scroll_entradas": am.scroll.entries, "muescas": (am.scroll.up, am.scroll.down), "e_max": am.scroll.max_e,
        "scroll_senal_entradas": am.shadow.entries, "muescas_senal": (am.shadow.up, am.shadow.down),
        "scroll_rechazos": dict(am.shadow.rejected),
        "sacudidas": am.shake.toggles, "sacudidas_instantes": am.shake_times,
        "pausas_sin_datos": len(sin_datos), "pausas_sin_datos_s": sin_datos,
        "pausas_brazo": am.pause_count["brazo caído"],
        "descartadas": am.stale_count, "esquina": int(am.kill_requested),
        "huecos": gaps, "paradas_200ms": sum(1 for s in stalls if s > 200), "dt_hist": dt_hist,
        "retraso_p50": q(ages, 0.5), "retraso_p95": q(ages, 0.95), "retraso_max": ages[-1] if ages else 0,
        "px_total": am.travel, "velocidad_max": am.max_speed, "congelado_s": am.frozen_s, "salto_tras_pausa": am.resume_jump,
        "clics": am.clicks, "movimientos": am.moves, "recortes_presupuesto": am.capped,
        "sesgo_recuperaciones": am.motion.recoveries, "calib_rechazos": dict(am.motion.calib_reject),
        "tap_caducados": am.tap.expired,
    }
    bi, bf = res["sesgo_inicial"], res["sesgo_final"]
    fmt3 = lambda v: "(" + " ".join(f"{c:+.2f}" for c in v) + ")" if v else "—"
    emit(f"reposo (p2p < 1 °/s en 1 s): {len(rest)} ventanas · cursor {res['reposo_px_s_medio']:.2f} px/s medio · "
          f"{res['reposo_px_s_max']:.2f} px/s máx · excursión máx {rest_exc} px (salida de la cadena del puntero, "
          f"también en pausa)")
    emit(f"temblor (1 < p2p < 4 °/s): {len(tremor)} ventanas · {res['temblor_px_s_medio']:.2f} px/s medio")
    emit(f"sesgo: inicial {fmt3(bi)} final {fmt3(bf)} · actualizaciones {am.motion.bias_updates} · "
          f"paso máx {am.motion.bias_max_step:.4f} °/s · recuperaciones {am.motion.recoveries} · "
          f"ventanas de calibración rechazadas {dict(am.motion.calib_reject) or '—'}")
    dwell_txt = (f"{am.dwell.fires} = {res['dwell_por_min']:.2f}/min · instantes {[round(v, 1) for v in am.dwell_times]}"
                 if "dwell" in am.click_mode else "— (usa --click dwell)")
    emit(f"clics falsos: tap candidatos {am.tap.candidates} → forma {am.tap.shape_ok} → puertas giro {am.tap.gate_ok} → "
          f"confirmados {am.tap.confirmed} = {res['clics_por_min']:.2f}/min · instantes {[round(v, 1) for v in am.tap_times]} "
          f"(clics emitidos {am.clicks - am.dwell.fires}, caducados sin acelerómetro {am.tap.expired}) · dwell {dwell_txt}")
    emit(f"scroll: entradas {am.scroll.entries} · muescas +{am.scroll.up}/−{am.scroll.down} · |e| máx {am.scroll.max_e:.0f}° · "
          f"señal (también en pausa): entradas {am.shadow.entries} · muescas +{am.shadow.up}/−{am.shadow.down} · "
          f"rechazos {dict(am.shadow.rejected) or '—'}")
    emit(f"sacudidas {am.shake.toggles} {[round(v, 1) for v in am.shake_times]} · pausas sin datos {len(sin_datos)} "
          f"({', '.join(f'{d:.1f} s' for d in sin_datos) or '—'}; {am.stalls_on_arrival} detectadas al llegar) · "
          f"pausas brazo caído {res['pausas_brazo']} · descartadas por antigüedad {am.stale_count} · esquina {res['esquina']}")
    emit(f"tiempos: dt {dt_hist} · huecos > 100 ms {len(gaps)} "
          f"({', '.join(f'{d:.0f} ms @ {a:.1f} s' for a, d in gaps) or '—'}) · paradas de llegada > 200 ms "
          f"{res['paradas_200ms']} · retraso t_recv−t_watch p50 {res['retraso_p50']} p95 {res['retraso_p95']} máx {res['retraso_max']} ms")
    emit(f"totales: px recorridos {am.travel:.0f} · velocidad máx {am.max_speed:.0f} px/s · tiempo congelado {am.frozen_s:.1f} s · "
          f"salto máx tras pausa {am.resume_jump:.0f} px · movimientos {am.moves} · clics {am.clicks} · "
          f"recortes por presupuesto de px/s {am.capped}")
    res["exit_code"] = 1 if (res["reposo_px_s_medio"] > 0 or rest_exc >= 1 or am.tap.confirmed > 0
                             or am.shadow.entries > 0) else 0
    return res


# ---------- tunables (the control channel's single source of truth) and the profile ----------

Tunable = namedtuple("Tunable", "kind lo hi choices attr label")


def _tun(kind, lo=None, hi=None, choices=None, attr=None, label=""):
    return Tunable(kind, lo, hi, choices, attr, label)


CLICK_MODES = ("auto", "button", "tap", "dwell", "tap+dwell", "none")
SCROLL_MODES = ("auto", "bezel", "roll", "none")
TUNABLES = {
    "gain": _tun("float", 0.1, 5.0, label="ganancia"),
    "gain_x": _tun("float", 0.2, 3.0, label="ganancia horizontal"),
    "gain_y": _tun("float", 0.2, 3.0, label="ganancia vertical"),
    "accel": _tun("bool", label="aceleración"),
    "g_lo": _tun("float", 1.0, 60.0, label="px/° lento"),
    "g_hi": _tun("float", 1.0, 120.0, label="px/° rápido"),
    "v_lo": _tun("float", 0.0, 200.0, label="°/s inicio aceleración"),
    "v_hi": _tun("float", 1.0, 400.0, label="°/s fin aceleración"),
    "mincutoff": _tun("float", 0.0, 10.0, label="suavizado (Hz)"),
    "beta": _tun("float", 0.0, 0.5, label="beta"),
    "dcutoff": _tun("float", 0.1, 10.0, label="dcutoff"),
    "deadzone": _tun("float", 0.0, 5.0, label="zona muerta °/s"),
    "click": _tun("choice", choices=CLICK_MODES, label="clic"),
    "scroll": _tun("choice", choices=SCROLL_MODES, label="scroll"),
    "bezel_invert": _tun("bool", label="invertir bisel"),
    "bezel_notches": _tun("int", 1, 10, label="muescas por detent"),
    "home_key": _tun("choice", choices=("none", "right", "middle"), label="tecla inicio"),
    "tap_thr": _tun("float", 0.5, 15.0, label="umbral de toque"),
    "tap_width": _tun("int", 1, 20, label="ancho de toque"),
    "tap_pre": _tun("float", 1.0, 90.0, label="giro máx. antes"),
    "tap_post": _tun("float", 1.0, 90.0, label="giro máx. después"),
    "tap_post_ms": _tun("int", 80, 600, label="ms hasta decidir"),
    "dwell_time": _tun("float", 0.3, 3.0, label="reposo s"),
    "dwell_speed": _tun("float", 0.2, 10.0, label="reposo °/s"),
    "scroll_enter": _tun("float", 10.0, 80.0, label="entrar scroll °"),
    "scroll_exit": _tun("float", 5.0, 60.0, label="salir scroll °"),
    "scroll_deg_per_notch": _tun("float", 2.0, 20.0, label="° por muesca"),
    "max_speed": _tun("float", 500.0, 10000.0, label="velocidad máx px/s"),
    "calib_p2p": _tun("float", 0.5, 6.0, label="reposo máx. para calibrar"),
    "yield": _tun("bool", attr="no_yield", label="ceder al ratón físico"),   # inverted flag
}
TUNABLES = {k: v._replace(attr=v.attr or k) for k, v in TUNABLES.items()}


def params_dict(cfg):
    out = {}
    for name, tn in TUNABLES.items():
        v = getattr(cfg, tn.attr)
        out[name] = (not v) if name == "yield" else bool(v) if tn.kind == "bool" else v
    return out


def defaults_dict():
    return params_dict(build_parser().parse_args([]))


def validate_params(params, cfg=None):
    """-> (clean, errors). Atomic: the caller applies nothing when `errors` is not empty. Cross checks
    (v_hi > v_lo, scroll_exit < scroll_enter) use `cfg` for the counterpart that is not in the set."""
    clean, errors = {}, []
    if not isinstance(params, dict):
        return clean, ["params debe ser un objeto"]
    for name, v in params.items():
        tn = TUNABLES.get(name)
        if tn is None:
            errors.append(f"{name} desconocido")
            continue
        if tn.kind == "bool":
            if not isinstance(v, bool):
                errors.append(f"{name}: valor inválido")
                continue
        elif tn.kind == "choice":
            if not isinstance(v, str) or v not in tn.choices:
                errors.append(f"{name}: valor inválido")
                continue
        else:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or (isinstance(v, int) and abs(v) > 2 ** 53) or not math.isfinite(v):
                errors.append(f"{name}: valor inválido")
                continue
            if tn.kind == "int":
                if float(v) != int(v):
                    errors.append(f"{name}: valor inválido")
                    continue
                v = int(v)
            else:
                v = float(v)
            if not tn.lo <= v <= tn.hi:
                errors.append(f"{name} fuera de rango ({tn.lo:g}–{tn.hi:g}): {v:g}")
                continue
        clean[name] = v
    current = lambda k: clean[k] if k in clean else (getattr(cfg, k) if cfg is not None else None)
    if ("v_hi" in clean or "v_lo" in clean) and current("v_hi") is not None and current("v_lo") is not None \
            and current("v_hi") <= current("v_lo"):
        errors.append(f"v_hi debe ser mayor que v_lo ({current('v_lo'):g})")
    if ("scroll_exit" in clean or "scroll_enter" in clean) and current("scroll_exit") is not None \
            and current("scroll_enter") is not None and current("scroll_exit") >= current("scroll_enter"):
        errors.append(f"scroll_exit debe ser menor que scroll_enter ({current('scroll_enter'):g})")
    return (clean if not errors else {}), errors


def resolve_profile(path):
    """None when disabled ('none' or empty); otherwise the absolute, ~-expanded path."""
    if not path or str(path).lower() == "none":
        return None
    return os.path.abspath(os.path.expanduser(path))


def save_profile(cfg, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "params": params_dict(cfg)}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


def load_profile_into(cfg, path, explicit_keys=()):
    """Applies the profile's tunables to `cfg`, except those typed on the command line (`explicit_keys`
    are argparse dests). Missing file -> None (silent); unreadable -> None with a log line; otherwise the
    number of values applied (bad values and unknown keys are skipped, one log line each)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        log(f"perfil ilegible: lo ignoro ({path}: {e})")
        return None
    params = data.get("params") if isinstance(data, dict) else None
    if not isinstance(params, dict):
        log(f"perfil ilegible: lo ignoro ({path}: sin 'params')")
        return None
    n = 0
    for name, v in params.items():
        tn = TUNABLES.get(name)
        if tn is None:
            log(f"perfil: {name} desconocido, lo ignoro")
            continue
        if tn.attr in explicit_keys:
            continue
        clean, errors = validate_params({name: v})     # pairs are checked once everything is in
        if errors:
            log(f"perfil: {errors[0]}, lo ignoro")
            continue
        value = clean[name]
        setattr(cfg, tn.attr, (not value) if name == "yield" else int(value) if name == "accel" else value)
        n += 1
    cfg.tap_post_ms = max(80, cfg.tap_post_ms)
    if cfg.v_hi <= cfg.v_lo or cfg.scroll_exit >= cfg.scroll_enter:   # the two halves came from different places
        log("perfil: v_hi/v_lo o scroll_exit/scroll_enter incoherentes, restauro esos valores")
        d = defaults_dict()
        if cfg.v_hi <= cfg.v_lo:
            cfg.v_lo, cfg.v_hi = d["v_lo"], d["v_hi"]
        if cfg.scroll_exit >= cfg.scroll_enter:
            cfg.scroll_enter, cfg.scroll_exit = d["scroll_enter"], d["scroll_exit"]
    return n


# ---------- control channel (ws://127.0.0.1:8766, the calibration page) ----------

def origin_allowed(origin):
    """Browsers send Origin on every WebSocket and apply no CORS to them, so without this any web page open
    in the browser could drive the mouse: only pages served from this machine or the LAN may connect."""
    try:
        host = urllib.parse.urlsplit(origin).hostname
    except ValueError:
        return False
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return bool(host) and host.endswith(".local")
    return ip.is_private or ip.is_loopback or ip.is_link_local


class ControlServer:
    """Hosts the calibration page's channel: `params` on connect and after every change, `state` at
    STATE_HZ while someone listens, the air mouse's events as they happen, and `set`/`cmd`/`get`."""

    def __init__(self, am, port, profile_path=None):
        self.am, self.port, self.profile_path = am, port, profile_path
        self.clients = set()
        self.bound_port = None
        self.ready = asyncio.Event()

    def params_message(self):
        am = self.am
        return {"type": "params", "params": params_dict(am.cfg), "defaults": defaults_dict(),
                "profile": self.profile_path or "", "efectivo": {"click": am.click_mode, "scroll": am.scroll_mode}}

    def dispatch(self, msg):
        """-> list of (to_all, message). Pure apart from the air mouse's own side effects."""
        am = self.am
        if not isinstance(msg, dict):
            return [(False, {"type": "error", "detail": "mensaje no es un objeto"})]
        kind = msg.get("type")
        if kind == "get":
            return [(False, self.params_message())]
        if kind == "set":
            clean, errors = validate_params(msg.get("params"), am.cfg)
            if errors:
                return [(False, {"type": "error", "name": "set", "detail": "; ".join(errors)})]
            am.apply_params(clean)
            return [(True, self.params_message())]
        if kind == "cmd":
            return self.command(msg.get("name"), msg)
        return [(False, {"type": "error", "detail": f"tipo desconocido: {kind}"})]

    def command(self, name, msg):
        am = self.am
        ack = lambda detail=None: [(False, {"type": "ack", "name": name, "detail": detail})]
        err = lambda detail: [(False, {"type": "error", "name": name, "detail": detail})]
        if name == "recalibrate":
            am.motion.start_calibration(background=False)
            am.say("recalibro: apoya la muñeca en la mesa y mantenla quieta…")
            return ack()
        if name == "pause":
            am._pause("usuario")
            return ack()
        if name == "resume":
            am._resume("usuario")
            return ack()
        if name == "save_profile":
            if not self.profile_path:
                return err("perfil desactivado (--profile none)")
            try:
                save_profile(am.cfg, self.profile_path)
            except OSError as e:
                return err(f"no pude guardar el perfil: {e}")
            am.say(f"perfil guardado en {self.profile_path}")
            am.event("profile", action="saved", path=self.profile_path)
            return ack(self.profile_path)
        if name == "load_profile":
            if not self.profile_path:
                return err("perfil desactivado (--profile none)")
            tmp = argparse.Namespace(**vars(am.cfg))   # load into a copy, apply the difference live
            n = load_profile_into(tmp, self.profile_path)
            if n is None:
                return err(f"no hay perfil legible en {self.profile_path}")
            before = params_dict(am.cfg)
            am.apply_params({k: v for k, v in params_dict(tmp).items() if before[k] != v})
            am.event("profile", action="loaded", path=self.profile_path)
            return ack(f"{n} ajustes") + [(True, self.params_message())]
        if name == "reset_defaults":
            am.apply_params(defaults_dict())
            am.event("profile", action="defaults", path=self.profile_path or "")
            return ack() + [(True, self.params_message())]
        if name == "record_gesture":
            try:
                path, n = am.record_gesture(msg.get("label") or "gesto")
            except OSError as e:
                return err(f"no pude grabar el gesto: {e}")
            return ack(path)
        if name == "list_gestures":
            return [(False, list_gestures())]
        return err(f"comando desconocido: {name}")

    async def handler(self, ws):
        from websockets.exceptions import ConnectionClosed
        origin = ws.request.headers.get("Origin") if ws.request is not None else None
        if origin and not origin_allowed(origin):
            log(f"canal de control: conexión rechazada desde {origin}")
            await ws.close(1008, "origen no permitido")
            return
        self.clients.add(ws)
        try:
            await ws.send(json.dumps(self.params_message()))
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    await ws.send(json.dumps({"type": "error", "detail": "JSON inválido"}))
                    continue
                try:
                    outs = list(self.dispatch(msg))
                except Exception as e:             # a bad value must not close the page's socket
                    name = msg.get("type") if isinstance(msg, dict) else None
                    outs = [(False, {"type": "error", "name": name, "detail": f"error interno: {e}"})]
                for to_all, out in outs:
                    if to_all:
                        self._broadcast(out)
                    else:
                        await ws.send(json.dumps(out))
        except ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)

    def _broadcast(self, msg):
        from websockets.asyncio.server import broadcast
        broadcast(list(self.clients), json.dumps(msg))

    async def run(self):
        from websockets.asyncio.server import serve
        try:
            server = await serve(self.handler, "127.0.0.1", self.port, compression=None, max_size=65536)
        except OSError:
            log(f"canal de control: puerto {self.port} ocupado, desactivado")
            return
        async with server:
            self.bound_port = server.sockets[0].getsockname()[1]
            self.ready.set()
            log(f"canal de control en ws://127.0.0.1:{self.bound_port} (página: http://localhost:8765/calibrate.html)")
            while True:
                await asyncio.sleep(1.0 / STATE_HZ)
                while self.am.event_queue:
                    ev = self.am.event_queue.popleft()
                    if self.clients:
                        self._broadcast(ev)
                if self.clients:
                    self._broadcast(self.am.state_message())


# ---------- CLI ----------

def build_parser(explicit_only=False):
    """explicit_only: every default becomes argparse.SUPPRESS, so vars(parse_args()) holds only the flags
    actually typed (the profile fills the rest at startup)."""
    p = argparse.ArgumentParser(description="Ratón aéreo con el Galaxy Watch: el giroscopio mueve el cursor, "
                                            "el botón atrás (o un toque en la esfera) hace clic y el bisel "
                                            "(o rodar el antebrazo) mueve la rueda")
    add = p.add_argument

    def a(*names, **kw):
        if explicit_only:
            kw["default"] = argparse.SUPPRESS
        return add(*names, **kw)
    a("--source", choices=("ui", "sdb"), default="ui", help="ui: ws del servidor; sdb: directo al reloj (exclusivo)")
    a("--url", default="ws://localhost:8765/ui")
    a("--device", default="192.168.0.XX", help="IP[:puerto] del reloj para --source sdb")
    a("--interval", type=int, default=10, help="ms entre muestras en sensorctl (--source sdb)")
    a("--replay", metavar="DIR", help="reproduce una grabación (implica --dry-run) y sale 1 si hay deriva o clics falsos")
    a("--realtime", action="store_true", help="con --replay: al ritmo real")
    a("--dry-run", action="store_true", help="imprime en vez de mover el ratón")
    a("--forearm", choices=tuple(FOREARM), default="+y", help="eje del sensor que apunta del codo a la mano")
    a("--frame", choices=("world", "body"), default="world", help="body: sin compensar la gravedad (prueba A/B)")
    a("--calibrate", choices=("axes", "tap", "forearm"), help="modo diagnóstico, no mueve el ratón")
    a("--self-test", action="store_true", help="DPI, pantalla virtual y un cuadrado de 20 px con el cursor "
                                               "(no ejercita la esquina, el ratón físico ni la tecla Pausa)")
    a("--gain", type=float, default=1.0)
    a("--gain-x", type=float, default=1.0, help="multiplicador horizontal")
    a("--gain-y", type=float, default=1.0, help="multiplicador vertical")
    a("--accel", type=int, default=1, help="0: ganancia fija g-lo")
    a("--max-speed", type=float, default=4000.0, help="px/s")
    a("--g-lo", type=float, default=12.0, help="px por grado a baja velocidad")
    a("--g-hi", type=float, default=30.0)
    a("--v-lo", type=float, default=10.0, help="°/s donde empieza la aceleración")
    a("--v-hi", type=float, default=120.0)
    a("--mincutoff", type=float, default=2.0, help="Hz del filtro 1-Euro (0 = sin filtro)")
    a("--beta", type=float, default=0.01)
    a("--dcutoff", type=float, default=1.0)
    a("--deadzone", type=float, default=0.8, help="°/s, zona muerta radial")
    a("--bias-tau", type=float, default=20.0, help="s, seguimiento lento del sesgo en reposo")
    a("--calib-p2p", type=float, default=2.5, help="°/s pico a pico máx. para aceptar 1 s como reposo al calibrar "
                                                    "(una muñeca apoyada en la mesa late ~1-2; el sesgo usa la mediana)")
    a("--bias-max", type=float, default=STILL_DEG, help="°/s, |mediana| máxima que se acepta como sesgo al calibrar "
                                                         "(el reloj trae el giroscopio compensado: ~0.07)")
    a("--move", choices=("absolute", "relative"), default="absolute")
    a("--click", choices=CLICK_MODES, default="auto",
      help="auto: botón atrás del reloj si el puente lo ofrece (BUTTON en hello), si no toque en la esfera")
    a("--home-key", choices=("none", "right", "middle"), default="none",
      help="qué botón del ratón es la tecla inicio del reloj (abre la lista de apps: opcional)")
    a("--bezel-invert", action="store_true", help="invierte el sentido del scroll del bisel")
    a("--bezel-notches", type=int, default=1, help="muescas de rueda por detent del bisel")
    a("--tap-thr", type=float, default=2.5, help="m/s² por muestra en accel z")
    a("--tap-width", type=int, default=6)
    a("--tap-pre", type=float, default=15.0, help="°/s máx. antes del toque")
    a("--tap-post", type=float, default=20.0, help="°/s máx. después del toque")
    a("--tap-post-ms", type=int, default=250, help="ms hasta decidir (mín. 80)")
    a("--tap-polarity", choices=("any", "neg"), default="any")
    a("--dwell-time", type=float, default=0.7)
    a("--dwell-speed", type=float, default=1.5)
    a("--dwell-arm", type=float, default=40.0)
    a("--scroll", choices=SCROLL_MODES, default="auto",
      help="auto: bisel si el puente lo ofrece (BEZEL en hello), si no rodar el antebrazo")
    a("--scroll-mode", choices=("ratchet", "rate"), default="ratchet")
    a("--scroll-enter", type=float, default=25.0)
    a("--scroll-exit", type=float, default=15.0)
    a("--scroll-deg-per-notch", type=float, default=6.0)
    a("--scroll-timeout", type=float, default=15.0)
    a("--scroll-max-rate", type=float, default=120.0, help="°/s: un giro más rápido es un movimiento, no un scroll")
    a("--scroll-max-deg", type=float, default=90.0, help="°: más allá se sale del scroll (nunca se da la vuelta)")
    a("--scroll-invert", action="store_true", help="muñeca derecha")
    a("--kill-corner", choices=("tl", "tr", "bl", "br", "none"), default="tl")
    a("--idle-timeout", type=float, default=0.5, help="s sin giroscopio antes de pausar")
    a("--no-yield", action="store_true", help="no pausar cuando se mueve el ratón físico")
    a("--pause-key", choices=("pause", "none"), default="pause")
    a("--max-clicks-per-min", type=int, default=60)
    a("--beep", action="store_true")
    a("--status-every", type=float, default=2.0)
    a("--log-gestures", metavar="FILE", help="CSV con cada candidato de gesto y su veredicto")
    a("--control-port", type=int, default=8766, help="ws://127.0.0.1:PUERTO para la página de calibración (0 = sin canal)")
    a("--profile", default=PROFILE_DEFAULT, metavar="PATH",
      help="perfil JSON con los ajustes; los flags escritos en la línea de órdenes mandan; 'none' lo desactiva")
    return p


def make_config(**overrides):
    cfg = build_parser().parse_args([])
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            raise AttributeError(f"opción desconocida: {k}")
        setattr(cfg, k, v)
    cfg.tap_post_ms = max(80, cfg.tap_post_ms)
    return cfg


def self_test(dpi, dry_run=False):
    vx, vy, vw, vh = virtual_screen()
    emit(f"DPI {dpi} · pantalla virtual {vw}x{vh} @({vx},{vy})")
    ptr = Win32Pointer()
    for kind in ("tl", "tr", "bl", "br"):
        cx, cy = ptr.corner(kind)
        emit(f"esquina {kind}: ({cx},{cy})")
    if dry_run:
        emit("--dry-run: no muevo el cursor (el cuadrado de 20 px necesita --self-test sin --dry-run)")
        return
    cp = ptr.cursor_pos()
    if cp is None:
        emit("no puedo leer el cursor (¿escritorio bloqueado?)")
        return
    x0, y0 = cp
    for dx, dy in ((20, 0), (0, 20), (-20, 0), (0, -20)):
        x0, y0 = x0 + dx, y0 + dy
        ptr.move_to(x0, y0)
        time.sleep(0.15)
        rb = ptr.cursor_pos() or ("?", "?")
        emit(f"mover ({x0},{y0}) → leído ({rb[0]},{rb[1]})")
    # the read-back race behind "pausa: ratón físico" every 1-3 s: SendInput queues the move for the
    # raw-input thread and returns; GetCursorPos right after it can still return the previous target
    prev = ptr.cursor_pos()
    stale = late = 0
    for i in range(50):
        tx = x0 + 3 * ((i + 1) % 2)       # alternates x0+3, x0, …: every target differs from the settled position
        ptr.move_to(tx, y0)
        rb = ptr.cursor_pos()
        stale += rb == prev
        time.sleep(0.01)
        rb2 = ptr.cursor_pos()
        late += rb2 == prev
        prev = rb2
    ptr.move_to(x0, y0)
    emit(f"eco tras SendInput: {stale}/50 lecturas inmediatas devolvieron la posición anterior · "
         f"{late}/50 seguían atrasadas 10 ms después")
    emit("ok: sin clics, botones sueltos (la esquina, el ratón físico y la tecla Pausa no se prueban aquí)")


async def run_live(args, pointer):
    am = AirMouse(args, pointer)
    am.calib_mode = args.calibrate
    am.loopback = args.source == "sdb" or any(h in args.url for h in ("localhost", "127.0.0.1", "[::1]"))
    source = sdb_source(args.device, args.interval) if args.source == "sdb" else ui_source(args.url)
    stop = asyncio.Event()
    calib_t0 = None

    def guarded(name, body, fatal=True):
        """Any exception in a task stops the whole run with its traceback printed: a dead consumer would
        otherwise look like a watch that stopped, and a dead ticker would leave the cursor moving with the
        kill corner, the Pause key, the physical-mouse yield and the watchdog all gone. The control
        channel is not fatal: it is printed and stays off, the mouse keeps working."""
        async def run():
            try:
                await body()
            except asyncio.CancelledError:
                raise
            except Exception:
                if fatal:
                    am.failed = name
                emit(f"error en {name}:\n{traceback.format_exc()}")
            finally:
                if fatal:
                    stop.set()
        return run()

    async def consume():
        nonlocal calib_t0
        async for msg, now in source:
            am.handle_message(msg, now)
            if args.calibrate == "tap" and isinstance(msg, dict) and msg.get("type") == "data":
                calib_t0 = calib_t0 or now
                if now - calib_t0 > 20:
                    am.calib_done = True
            if am.kill_requested or am.calib_done:
                break

    async def ticker():
        while not stop.is_set():
            await asyncio.sleep(0.05)
            am.tick(time.monotonic())
            if am.kill_requested:
                stop.set()

    async def reporter():
        while not stop.is_set():
            await asyncio.sleep(args.status_every)
            if not stop.is_set():
                log(am.status_line(time.monotonic()))

    tasks = [asyncio.create_task(guarded("consume", consume)), asyncio.create_task(guarded("ticker", ticker)),
             asyncio.create_task(guarded("reporter", reporter))]
    if getattr(args, "control_port", 0) > 0 and not args.calibrate:
        control = ControlServer(am, args.control_port, resolve_profile(getattr(args, "profile", None)))
        tasks.append(asyncio.create_task(guarded("control", control.run, fatal=False)))
    try:
        await stop.wait()
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        am.shutdown()
    return am


async def main():
    explicit = set(vars(build_parser(explicit_only=True).parse_args()))   # flags actually typed win over the profile
    args = build_parser().parse_args()
    args.tap_post_ms = max(80, args.tap_post_ms)
    for stream in (sys.stdout, sys.stderr):   # a redirected console may be cp1252: never die on "→"
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    dpi = make_dpi_aware()
    emit(f"GearStream ratón aéreo {VERSION}")
    profile = resolve_profile(args.profile)
    if profile and not args.replay and not args.self_test:   # the replay is the regression oracle: flags only
        n = load_profile_into(args, profile, explicit)
        if n is not None:
            log(f"perfil: {profile} ({n} ajustes)")
    if args.replay:
        res = replay(args.replay, args, realtime=args.realtime)
        sys.exit(res.get("exit_code", 1))
    if args.self_test:
        if sys.platform != "win32":
            emit("sin Win32: --self-test no hace nada")
            return
        self_test(dpi, dry_run=args.dry_run)
        return
    if sys.platform != "win32" and not args.dry_run and not args.calibrate:
        emit("sin Win32: uso --dry-run")
        args.dry_run = True
    vx, vy, vw, vh = virtual_screen()
    if args.dry_run or args.calibrate:
        pointer = DryRunPointer((vx, vy, vw, vh))
        log("--dry-run: no muevo el ratón" if args.dry_run else f"--calibrate {args.calibrate}: no muevo el ratón")
        log("cursor simulado: la esquina de emergencia, el ratón físico y la tecla Pausa no se ejercitan en este modo")
    else:
        pointer = Win32Pointer()
    log(f"fuente {args.source} {args.device if args.source == 'sdb' else args.url} · pantalla virtual {vw}x{vh} @({vx},{vy}) · DPI {dpi}")
    atexit.register(pointer.release_all)
    if sys.platform == "win32":
        import ctypes
        handler_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)

        def on_console_ctrl(_ctrl_type):
            pointer.release_all()
            return False
        main.ctrl_handler = handler_type(on_console_ctrl)   # keep a reference alive
        ctypes.WinDLL("kernel32").SetConsoleCtrlHandler(main.ctrl_handler, True)

        def on_break(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGBREAK, on_break)
    if args.calibrate == "forearm":
        log("cuelga el brazo relajado 1 s…")
    elif args.calibrate == "axes":
        log("calibrando: apoya la muñeca en la mesa, quieta 2 s… luego levanta el brazo y haz un giro claro (> 60 °/s)")
    elif args.calibrate == "tap":
        log("calibrando: apoya la muñeca en la mesa, quieta 2 s… luego da 20 toques en la esfera (20 s)")
    else:
        log("calibrando: apoya la muñeca en la mesa, quieta 2 s (una muñeca en el aire tiembla demasiado)…")
    am = await run_live(args, pointer)
    if am.kill_requested:
        sys.exit(3)
    if am.failed:
        log(f"terminado por un error en {am.failed} (botones sueltos)")
        sys.exit(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
