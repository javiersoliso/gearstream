"""Unit tests for tools/air_mouse.py: pure logic with a fake clock and a DryRunPointer, no Win32 calls.

    python -I tools/test_air_mouse.py
"""
import asyncio
import contextlib
import csv
import io
import json
import math
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script dir from sys.path
import air_mouse  # noqa: E402

BIAS = (-0.07, -0.07, -0.07)
GRAV = (0.0, 0.0, 9.807)
ACC = (0.0, 0.0, 9.81)
BOUNDS = (0, 0, 1920, 1080)
ALL = ("GYROSCOPE", "ACCELERATION", "GRAVITY")


def w(x=0.0, y=0.0, z=0.0):
    """Raw gyro reading for a true rate (x, y, z) deg/s on top of the rest bias."""
    return (BIAS[0] + x, BIAS[1] + y, BIAS[2] + z)


def quiet_gyro(rel):
    """Rest: bias plus/minus one 0.07 LSB step."""
    return w(z=0.07 if int(rel * 100) % 2 else 0.0)


def rolled_gravity(theta_deg):
    """Gravity in the sensor frame after rolling theta about +y (forearm +y)."""
    th = math.radians(theta_deg)
    return (-9.807 * math.sin(th), 0.0, 9.807 * math.cos(th))


def tilted_gravity(pitch_deg, roll_deg=0.0):
    """Gravity with the forearm (+y) raised pitch_deg above horizontal, then rolled roll_deg about +y."""
    p, r = math.radians(pitch_deg), math.radians(roll_deg)
    gy, gz = -9.807 * math.sin(p), 9.807 * math.cos(p)
    return (-gz * math.sin(r), gy, gz * math.cos(r))


class LaggyPointer(air_mouse.DryRunPointer):
    """GetCursorPos right after SendInput still returns the previous target: the raw-input thread has not
    applied the move yet (one stale read per move, then the truth)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.stale = None

    def move_to(self, x, y):
        before = self.pos
        super().move_to(x, y)
        self.stale = before

    def cursor_pos(self):
        if self.stale is not None:
            p, self.stale = self.stale, None
            return p
        return super().cursor_pos()


class JitterPointer(air_mouse.DryRunPointer):
    """Every other read is 1 px off (absolute-mapping rounding on a mixed-DPI desktop)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.reads = 0

    def cursor_pos(self):
        self.reads += 1
        p = super().cursor_pos()
        return (p[0] + 1, p[1]) if p is not None and self.reads % 2 else p


class ClampPointer(air_mouse.DryRunPointer):
    """Windows confines the cursor to the monitors, not to their bounding box: here nothing right of x=1000."""

    def move_to(self, x, y):
        super().move_to(min(x, 1000), y)


class Rig:
    """Feeds /ui-shaped messages at 100 Hz (10 ms steps, `batch` gyro samples per message) with a fake clock."""

    def __init__(self, bounds=BOUNDS, monitors=None, pointer=None, **cfg):
        self.cfg = air_mouse.make_config(**cfg)
        self.pointer = (pointer or air_mouse.DryRunPointer)(bounds, quiet=True, monitors=monitors)
        self.pointer._say = lambda *a, **k: None
        self.am = air_mouse.AirMouse(self.cfg, self.pointer)
        self.lines = []
        self.am.say = self.lines.append     # keep the test output clean; messages stay assertable
        self.t = 1_000_000.0       # sample time, ms
        self.next_tick = self.t
        self.lag = 0.0             # arrival - sample time

    def now_ms(self):
        return self.t + self.lag

    def ticks_until(self, now_ms):
        while self.next_tick <= now_ms:
            self.am.tick(self.next_tick / 1000.0)
            self.next_tick += 50

    def send(self, samples, now_ms=None):
        now_ms = self.now_ms() if now_ms is None else now_ms
        self.ticks_until(now_ms)
        self.am.handle_message({"type": "data", "samples": samples}, now_ms / 1000.0, now_ms)

    def msg(self, msg):
        self.am.handle_message(msg, self.now_ms() / 1000.0, self.now_ms())

    def collect(self, seconds, gyro=quiet_gyro, accel=ACC, gravity=GRAV, batch=2, sources=ALL):
        """The messages run() would send, without sending them (sample time advances)."""
        n = int(round(seconds * 100))
        pending, t_start, out = [], self.t, []
        for _ in range(n):
            self.t += 10.0
            rel = (self.t - t_start) / 1000.0
            g = gyro(rel) if callable(gyro) else gyro
            a = accel(rel) if callable(accel) else accel
            v = gravity(rel) if callable(gravity) else gravity
            for src, val in (("GYROSCOPE", g), ("ACCELERATION", a), ("GRAVITY", v)):
                if src in sources:
                    pending.append([src, self.t, {"x": val[0], "y": val[1], "z": val[2]}])
            if len(pending) >= batch * len(sources):
                out.append(pending)
                pending = []
        if pending:
            out.append(pending)
        return out

    def run(self, seconds, gyro=quiet_gyro, accel=ACC, gravity=GRAV, batch=2, deliver_at_end=False, sources=ALL):
        msgs = self.collect(seconds, gyro, accel, gravity, batch, sources)
        if deliver_at_end:
            self.send([s for m in msgs for s in m])
            return
        for m in msgs:
            self.send(m, m[-1][1] + self.lag)

    def idle_ticks(self, seconds):
        """Wall clock advances with ticks only; sample time does not (what arrives later is a backlog)."""
        self.lag += seconds * 1000
        self.ticks_until(self.now_ms())

    def hole(self, seconds):
        """The watch stops sampling for a while: wall clock and sample time both advance, nothing arrives."""
        self.t += seconds * 1000
        self.ticks_until(self.now_ms())

    def calibrate(self, **kw):
        self.run(2.2, **kw)
        assert self.am.motion.calibrated, "la calibración del sesgo no terminó"
        return self

    def hello(self, available=()):
        """The bridge's hello (what it can read on the watch), then 1.2 s of rest so 'calentando' ends."""
        self.msg({"type": "hello", "app": "test", "available": list(available)})
        self.run(1.2)
        return self

    def bezel(self, direction, steps=1, raw=None, age_ms=0):
        values = {"direction": direction, "steps": steps}
        if raw is not None:
            values["raw"] = raw
        self.send([["BEZEL", self.now_ms() - age_ms, values]])

    def button(self, key, pressed, age_ms=0):
        self.send([["BUTTON", self.now_ms() - age_ms, {"key": key, "pressed": pressed}]])

    def events(self, kind):
        return [e["detail"] for e in self.am.event_queue if e["kind"] == kind]

    @property
    def pos(self):
        return self.pointer.pos

    def clicks(self):
        return [e for e in self.pointer.log if e[0] == "click"]

    def wheel(self):
        return [e[1] for e in self.pointer.log if e[0] == "wheel"]

    def moves(self):
        return [e for e in self.pointer.log if e[0] == "move"]

    def downs(self):
        return [e for e in self.pointer.log if e[0] == "down"]

    def ups(self):
        return [e for e in self.pointer.log if e[0] == "up"]


def gain_at(cfg, v):
    u = min(1.0, max(0.0, (v - cfg.v_lo) / (cfg.v_hi - cfg.v_lo)))
    return cfg.g_lo + (cfg.g_hi - cfg.g_lo) * (3 * u * u - 2 * u ** 3)


def spike_accel(at, peak=14.5, after=7.0):
    """Accel z trace with a tap spike at sample index `at` (per-sample index of rel*100)."""
    table = {at: peak, at + 1: after}
    return lambda r: (0.0, 0.0, table.get(int(round(r * 100)), 9.81))


class AirMouseTests(unittest.TestCase):

    def test_rest_no_motion(self):
        rig = Rig().calibrate()
        p0, travel0 = rig.pos, rig.am.travel
        rig.run(5.0)
        self.assertEqual(rig.am.travel, travel0)
        self.assertEqual(rig.pos, p0)
        self.assertEqual(rig.clicks(), [])
        self.assertEqual(rig.wheel(), [])
        self.assertEqual(rig.moves(), [])

    def test_yaw_moves_left(self):
        for forearm in ("+y", "-y"):
            rig = Rig(forearm=forearm).calibrate()
            p0 = rig.pos
            rig.run(0.5, gyro=w(z=30))
            rig.run(0.4)
            dx, dy = rig.pos[0] - p0[0], rig.pos[1] - p0[1]
            v = 30 - rig.cfg.deadzone
            expected = -gain_at(rig.cfg, v) * 15 * v / 30
            self.assertLess(abs(dx - expected), 0.15 * abs(expected), (forearm, dx, expected))
            self.assertLess(abs(dy), 2, (forearm, dy))

    def test_pitch_moves_up(self):
        rig = Rig(forearm="+y").calibrate()
        p0 = rig.pos
        rig.run(0.5, gyro=w(x=30))
        rig.run(0.3)
        self.assertLess(rig.pos[1] - p0[1], -50)
        self.assertLess(abs(rig.pos[0] - p0[0]), 2)
        rig = Rig(forearm="-y").calibrate()
        p0 = rig.pos
        rig.run(0.5, gyro=w(x=30))
        rig.run(0.3)
        self.assertGreater(rig.pos[1] - p0[1], 50)

    def test_tilt_compensation(self):
        side = dict(gravity=(9.807, 0.0, 0.0), accel=(9.81, 0.0, 0.0))
        rig = Rig(frame="world").calibrate(**side)
        p0 = rig.pos
        rig.run(0.5, gyro=w(x=30), **side)
        rig.run(0.3, **side)
        self.assertGreater(abs(rig.pos[0] - p0[0]), 50)
        self.assertLess(abs(rig.pos[1] - p0[1]), 2)
        rig = Rig(frame="body").calibrate(**side)
        p0 = rig.pos
        rig.run(0.5, gyro=w(x=30), **side)
        rig.run(0.3, **side)
        self.assertGreater(abs(rig.pos[1] - p0[1]), 50)
        self.assertLess(abs(rig.pos[0] - p0[0]), 2)

    def test_arm_down_gate_is_one_sided(self):
        # GRAVITY da la dirección de arriba en el reloj (igual que el acelerómetro en reposo). Antebrazo +y:
        # mano arriba = (0, +g, 0) no pausa (hay que poder llegar al borde superior); colgando = (0, −g, 0) sí
        up, down = (0.0, 9.807, 0.0), (0.0, -9.807, 0.0)
        rig = Rig().calibrate()
        rig.run(2.0, gravity=up, accel=up)
        self.assertNotIn("brazo caído", rig.am.pause_reasons)
        rig.run(1.0)                                     # de vuelta a la horizontal (en la realidad la mano pasa por ahí)
        rig.run(2.0, gravity=down, accel=down)
        self.assertIn("brazo caído", rig.am.pause_reasons)
        rig.run(2.0)
        self.assertNotIn("brazo caído", rig.am.pause_reasons)

    def test_roll_gives_no_motion(self):
        # horizontal forearm, and raised 20/30/45 deg (gf = -0.34/-0.5/-0.71): a pure roll about the forearm
        # has no component on the pointer axes at any tilt
        for pitch in (0.0, 20.0, 30.0, 45.0):
            pose = dict(gravity=tilted_gravity(pitch), accel=tilted_gravity(pitch))
            rig = Rig(scroll="none").calibrate(**pose)
            p0 = rig.pos
            rig.run(0.3, gyro=w(y=100), gravity=lambda r: tilted_gravity(pitch, 100 * r),
                    accel=lambda r: tilted_gravity(pitch, 100 * r))
            rig.run(0.5, gravity=tilted_gravity(pitch, 30), accel=tilted_gravity(pitch, 30))
            self.assertLess(math.dist(rig.pos, p0), 2, pitch)
            self.assertLess(rig.am.travel, 2, pitch)
        # a yaw about the vertical keeps its rate (and the cursor its horizontal travel) at 30 deg of tilt
        p = math.radians(30)
        pose = dict(gravity=tilted_gravity(30), accel=tilted_gravity(30))
        rig = Rig(scroll="none").calibrate(**pose)
        p0 = rig.pos
        rig.run(0.5, gyro=w(y=-30 * math.sin(p), z=30 * math.cos(p)), **pose)   # omega = 30 deg/s about ghat
        rig.run(0.4, **pose)
        flat = Rig(scroll="none").calibrate()
        f0 = flat.pos
        flat.run(0.5, gyro=w(z=30))
        flat.run(0.4)
        self.assertLess(abs((rig.pos[0] - p0[0]) - (flat.pos[0] - f0[0])), 0.15 * abs(flat.pos[0] - f0[0]))
        self.assertLess(abs(rig.pos[1] - p0[1]), 3)

    def test_speed_clamp_and_bounds(self):
        for bounds in (BOUNDS, (-1920, 0, 3840, 1080)):
            for move in ("absolute", "relative"):
                rig = Rig(bounds=bounds, move=move).calibrate()
                steps = []
                rig.am.motion_hook = lambda t, dx, dy, px, py, applied: steps.append(math.hypot(dx, dy))
                rig.run(1.0, gyro=w(z=2000))
                rig.run(0.3, gyro=w(x=-2000))
                self.assertLessEqual(max(steps), 40.0 + 1e-6)
                self.assertLessEqual(rig.am.max_speed, rig.cfg.max_speed + 1e-6)
                vx, vy, vw, vh = bounds
                for e in rig.moves():
                    self.assertTrue(vx <= e[1] <= vx + vw - 1 and vy <= e[2] <= vy + vh - 1, e)
                    self.assertFalse(abs(e[1] - vx) < 4 and abs(e[2] - vy) < 4, ("dentro del rincón", move, e))
                self.assertEqual(rig.pos[0], vx, move)      # pinned to the left edge, outside the corner inset
                self.assertLessEqual(rig.pos[1], vy + vh - 1)
                # relative mode: holding still after overshooting into the corner must not trigger the kill
                rig.run(0.6)
                self.assertFalse(rig.am.kill_requested, move)
                self.assertFalse(abs(rig.pos[0] - vx) < 4 and abs(rig.pos[1] - vy) < 4, (move, rig.pos))

    def test_wall_clock_budget(self):
        # 25 messages (0.5 s of samples at the 4000 px/s cap = 2000 px) arriving 1 ms apart of wall time:
        # the per-sample cap allows 2000 px, the wall-clock budget only BUDGET_S * max_speed + 4000 * 0.025
        rig = Rig().calibrate()
        travel0 = rig.am.travel
        base = rig.now_ms()
        for i, m in enumerate(rig.collect(0.5, gyro=w(z=2000))):
            rig.am.handle_message({"type": "data", "samples": m}, (base + i) / 1000.0, base + i)
        burst = rig.am.travel - travel0
        allowed = rig.cfg.max_speed * (air_mouse.BUDGET_S + 0.025)
        self.assertLessEqual(burst, allowed + 1e-6)
        self.assertGreater(burst, rig.cfg.max_speed * air_mouse.BUDGET_S - 1e-6)
        self.assertGreater(rig.am.capped, 0)
        self.assertEqual(rig.am.stale_count, 0)
        self.assertIsNone(rig.am.status()["pausa"])

    def test_backlog_after_stall_never_moves(self):
        # the Python process blocks (QuickEdit, standby) for longer than the 10 s the old baseline window
        # covered, while the arm moves at 200 deg/s: the whole backlog arrives back-to-back before the
        # ticker gets a turn, and must be discarded as stale
        for stall_s, spacing_ms, tick_first in ((12.0, 0.4, False), (12.0, 0.4, True), (20.0, 1.0, False)):
            rig = Rig().calibrate()
            p0, travel0 = rig.pos, rig.am.travel
            msgs = rig.collect(stall_s, gyro=w(z=200))
            arrive = rig.now_ms()
            if tick_first:
                rig.ticks_until(arrive)
                self.assertEqual(rig.am.status()["pausa"], "sin datos")
            for i, m in enumerate(msgs):
                now = arrive + i * spacing_ms
                rig.am.handle_message({"type": "data", "samples": m}, now / 1000.0, now)
            self.assertEqual(rig.am.travel, travel0, (stall_s, tick_first))
            self.assertEqual(rig.pos, p0, (stall_s, tick_first))
            self.assertEqual(rig.am.status()["pausa"], "sin datos", (stall_s, tick_first))
            self.assertEqual(rig.am.stalls_on_arrival, 0 if tick_first else 1)
            self.assertGreater(rig.am.stale_count, len(msgs))
            # live data again (the watch kept sampling while the backlog drained, so those samples are a
            # hole, and what arrives now is as fresh as before): resumes after 0.3 s and moves normally
            rig.t += len(msgs) * spacing_ms
            rig.next_tick = rig.now_ms()
            rig.run(0.5, gyro=w(z=200))
            self.assertIsNone(rig.am.status()["pausa"], (stall_s, tick_first))
            self.assertGreater(rig.am.travel, travel0)
            self.assertLessEqual(rig.am.travel - travel0, rig.cfg.max_speed * (0.5 + air_mouse.BUDGET_S))

    def test_norm_mapping(self):
        for size in (1920, 1080, 3840):
            for px in range(size):
                self.assertEqual((air_mouse.norm(px, 0, size) * size) >> 16, px)
            self.assertEqual((air_mouse.norm(-1920 + 7, -1920, size) * size) >> 16, 7)
        self.assertEqual(air_mouse.norm(5, 0, 0), 65535)         # a 0-wide screen never divides by zero

    def test_tap_click(self):
        for move, batch in (("absolute", 2), ("relative", 2), ("relative", 10)):
            rig = Rig(move=move).calibrate(batch=batch)
            rig.run(1.0, gyro=w(z=8), batch=batch)             # slow pointing, so the rewind has something to undo
            snapshot = rig.pos                                  # position 80 ms before the peak (next 8 samples are quiet)
            rig.run(0.08, batch=batch)
            spike = {0: 14.5, 1: 7.0, 2: 9.9}
            rig.run(0.24, accel=lambda r: (0.0, 0.0, spike.get(int(round(r * 100)) - 1, 9.81)), batch=batch)
            t_tap = rig.t - 230                                 # the 14.5 sample
            self.assertEqual(rig.am.tap.candidates, 1, (move, batch))
            self.assertEqual(rig.clicks(), [], (move, batch))   # not decided before t_tap + 250 ms
            self.assertTrue(rig.am.frozen(rig.t))
            rig.run(0.02, batch=batch)
            self.assertEqual(len(rig.clicks()), 1, (move, batch))
            self.assertLessEqual(math.dist(rig.clicks()[0][1:], snapshot), 2, (move, batch, rig.clicks(), snapshot))
            self.assertEqual(rig.pointer.held, set())
            self.assertTrue(rig.am.frozen(t_tap + 290))
            self.assertFalse(rig.am.frozen(t_tap + 300))
            if move == "relative":                              # P and the real cursor stay together
                rig.run(0.5, batch=batch)
                self.assertLessEqual(math.dist(rig.am.P, rig.pos), 1.0, (move, batch, rig.am.P, rig.pos))
        # second spike 100 ms after the first one: inside the 150 ms refractory
        rig = Rig().calibrate()
        rig.run(1.0, accel=lambda r: (0.0, 0.0, {50: 14.5, 51: 7.0, 60: 14.5, 61: 7.0}.get(int(round(r * 100)), 9.81)))
        self.assertEqual(rig.am.tap.candidates, 1)
        self.assertEqual(len(rig.clicks()), 1)
        # second spike 300 ms later: second click at the same position (Windows pairs them as a double click)
        for move in ("absolute", "relative"):
            rig = Rig(move=move).calibrate()
            rig.run(1.5, accel=lambda r: (0.0, 0.0, {50: 14.5, 51: 7.0, 80: 14.5, 81: 7.0}.get(int(round(r * 100)), 9.81)))
            self.assertEqual(len(rig.clicks()), 2, move)
            self.assertEqual(rig.clicks()[0][1:], rig.clicks()[1][1:], move)
        # |omega| = 200 deg/s 100 ms before the spike: pre-gate rejects, and already at candidate time (no arm)
        rig = Rig().calibrate()
        rig.run(1.5, gyro=lambda r: w(z=200) if int(round(r * 100)) == 40 else w(),
                accel=lambda r: (0.0, 0.0, {50: 14.5, 51: 7.0}.get(int(round(r * 100)), 9.81)))
        self.assertEqual(rig.am.tap.candidates, 1)
        self.assertEqual(rig.clicks(), [])
        self.assertEqual(rig.am.frozen_s, 0.0)
        # |omega| = 50 deg/s 150 ms after the spike: post-gate rejects
        rig = Rig().calibrate()
        rig.run(1.5, gyro=lambda r: w(z=50) if int(round(r * 100)) == 65 else w(),
                accel=lambda r: (0.0, 0.0, {50: 14.5, 51: 7.0}.get(int(round(r * 100)), 9.81)))
        self.assertEqual(rig.am.tap.candidates, 1)
        self.assertEqual(rig.clicks(), [])
        # a 3 m/s2 ramp over 200 ms is not a spike at all
        rig = Rig().calibrate()
        rig.run(1.5, accel=lambda r: (0.0, 0.0, 9.81 + 3.0 * min(1.0, max(0.0, (r - 0.5) / 0.2))))
        self.assertEqual(rig.am.tap.candidates, 0)
        self.assertEqual(rig.clicks(), [])

    def test_bump_while_pointing_does_not_freeze(self):
        # pointing left at 40 deg/s with one 3 m/s2 bump on accel z: the candidate is never armed, so the
        # cursor trace stays monotonic (no 80 ms rewind, no 250 ms freeze)
        rig = Rig().calibrate()
        xs = []
        rig.am.motion_hook = lambda t, dx, dy, px, py, applied: xs.append(px)
        rig.run(1.5, gyro=w(z=40), accel=lambda r: (0.0, 0.0, {70: 12.81, 71: 9.81}.get(int(round(r * 100)), 9.81)))
        self.assertEqual(rig.am.tap.candidates, 1)
        self.assertFalse(rig.am.tap.pending and rig.am.tap.pending["armed"])
        self.assertEqual(rig.am.frozen_s, 0.0)
        self.assertEqual(rig.clicks(), [])
        self.assertTrue(all(b <= a + 1e-9 for a, b in zip(xs, xs[1:])), "la traza del cursor retrocedió")
        self.assertGreater(xs[0] - xs[-1], 500)

    def test_dwell(self):
        rig = Rig(click="dwell").calibrate()
        rig.run(1.0, gyro=w(z=10))
        self.assertGreaterEqual(rig.am.travel, 40)
        rig.run(0.9)
        self.assertEqual(len(rig.clicks()), 1)
        rig.run(5.0)
        self.assertEqual(len(rig.clicks()), 1)
        rig.run(0.12, gyro=w(z=10))                    # ~10 px: not enough to re-arm
        rig.run(1.5)
        self.assertEqual(len(rig.clicks()), 1)
        self.assertEqual(rig.am.tap.candidates, 0)

    def test_tap_then_dwell_is_one_click(self):
        rig = Rig(click="tap+dwell").calibrate()
        rig.run(1.0, gyro=w(z=10))                     # arms the dwell (>= 40 px, rho > 4)
        rig.run(0.2)
        rig.run(0.5, accel=spike_accel(10))
        self.assertEqual(len(rig.clicks()), 1)
        rig.run(2.0)                                   # the 300 ms freeze ends; the hold must not count as a dwell
        self.assertEqual(len(rig.clicks()), 1)
        self.assertEqual(rig.am.dwell.fires, 0)

    def test_roll_scroll(self):
        rate = -50.0 / 0.6                              # 83 deg/s: below --scroll-max-rate
        ramp = dict(gyro=w(y=rate), gravity=lambda r: rolled_gravity(rate * r))
        rig = Rig().calibrate()
        p0 = rig.pos
        rig.run(0.6, **ramp)
        rig.run(1.0, gravity=rolled_gravity(-50))
        self.assertTrue(rig.am.scroll.active)
        self.assertEqual(rig.wheel(), [1, 1, 1, 1])
        self.assertEqual(rig.pos, p0)
        rig.run(0.6, gyro=w(y=-rate), gravity=lambda r: rolled_gravity(-50 - rate * r))
        rig.run(0.5)
        self.assertFalse(rig.am.scroll.active)
        self.assertEqual(rig.wheel(), [1, 1, 1, 1])
        self.assertEqual(rig.pos, p0)
        # the other way, and inverted for the right wrist
        rig = Rig(scroll_invert=True).calibrate()
        rig.run(0.6, gyro=w(y=-rate), gravity=lambda r: rolled_gravity(-rate * r))
        rig.run(1.0, gravity=rolled_gravity(50))
        self.assertEqual(rig.wheel(), [1, 1, 1, 1])
        rig = Rig().calibrate()
        rig.run(0.6, gyro=w(y=-rate), gravity=lambda r: rolled_gravity(-rate * r))
        rig.run(1.0, gravity=rolled_gravity(50))
        self.assertEqual(rig.wheel(), [-1, -1, -1, -1])
        # a static pose at 50 deg from the first sample is the neutral, not a scroll
        rig = Rig().calibrate(gravity=rolled_gravity(50))
        rig.run(2.0, gravity=rolled_gravity(50))
        self.assertEqual(rig.wheel(), [])
        # a 50 deg roll together with 80 deg/s of yaw is an arm movement
        rig = Rig().calibrate()
        rig.run(0.6, gyro=w(y=rate, z=80), gravity=lambda r: rolled_gravity(rate * r))
        rig.run(1.0, gravity=rolled_gravity(-50))
        self.assertEqual(rig.wheel(), [])
        self.assertEqual(rig.am.scroll.entries, 0)
        # with the forearm raised 30 deg the same roll still scrolls and the cursor still does not move
        for pitch in (30.0, -30.0):
            pose = dict(gravity=tilted_gravity(pitch), accel=tilted_gravity(pitch))
            rig = Rig().calibrate(**pose)
            p0 = rig.pos
            rig.run(0.6, gyro=w(y=rate), gravity=lambda r: tilted_gravity(pitch, rate * r),
                    accel=lambda r: tilted_gravity(pitch, rate * r))
            rig.run(1.0, gravity=tilted_gravity(pitch, -50), accel=tilted_gravity(pitch, -50))
            self.assertEqual(rig.am.scroll.entries, 1, pitch)
            self.assertEqual(rig.wheel(), [1, 1, 1, 1], pitch)
            self.assertLess(math.dist(rig.pos, p0), 2, pitch)
            self.assertLess(rig.am.travel, 2, pitch)

    def test_roll_scroll_rejections(self):
        # a 167 deg/s fling (the old test's ramp) is a movement, not a scroll: no entry, no notches
        fast = -50.0 / 0.3
        rig = Rig().calibrate()
        p0 = rig.pos
        rig.run(0.3, gyro=w(y=fast), gravity=lambda r: rolled_gravity(fast * r))
        rig.run(1.0, gravity=rolled_gravity(-50))
        self.assertEqual(rig.am.scroll.entries, 0)
        self.assertEqual(rig.wheel(), [])
        self.assertEqual(rig.am.scroll.rejected["rápido"] >= 1, True)
        self.assertLess(math.dist(rig.pos, p0), 2)
        # a roll that starts straight out of a yaw sweep (no quiet hold before the ramp) does not scroll
        rate = -50.0 / 0.6
        rig = Rig().calibrate()
        rig.run(1.0, gyro=w(z=30))
        rig.run(0.6, gyro=w(y=rate), gravity=lambda r: rolled_gravity(rate * r))
        rig.run(1.0, gravity=rolled_gravity(-50))
        self.assertEqual(rig.am.scroll.entries, 0)
        self.assertGreaterEqual(rig.am.scroll.rejected["sin pausa previa"], 1)
        # a roll past 90 deg exits (never wraps to the other sign): the notches stop and no 'rueda -1' appears
        rate = -120.0 / 1.4
        rig = Rig().calibrate()
        rig.run(1.4, gyro=w(y=rate), gravity=lambda r: rolled_gravity(rate * r))
        rig.run(0.5, gravity=rolled_gravity(-120))
        self.assertEqual(rig.am.scroll.entries, 1)
        self.assertFalse(rig.am.scroll.active)
        self.assertTrue(all(n == 1 for n in rig.wheel()), rig.wheel())
        self.assertLessEqual(len(rig.wheel()), 11)
        rig.run(1.4, gyro=w(y=-rate), gravity=lambda r: rolled_gravity(-120 - rate * r))   # back to neutral
        rig.run(0.5)
        self.assertTrue(all(n == 1 for n in rig.wheel()), rig.wheel())

    def test_scroll_ratchet_hysteresis(self):
        rate = -50.0 / 0.6
        rig = Rig().calibrate()
        rig.run(0.6, gyro=w(y=rate), gravity=lambda r: rolled_gravity(rate * r))
        rig.run(0.5, gravity=rolled_gravity(-50))
        self.assertEqual(rig.wheel(), [1, 1, 1, 1])
        # back to the 25 + 6*3 = 43 deg boundary and hold with a +-1 deg, 4 Hz tremor for 3 s
        back = 7.0 / 0.2
        rig.run(0.2, gyro=w(y=back), gravity=lambda r: rolled_gravity(-50 + back * r))
        trem = lambda r: -43.0 + math.sin(2 * math.pi * 4 * r)
        trem_dot = lambda r: 2 * math.pi * 4 * math.cos(2 * math.pi * 4 * r)
        rig.run(3.0, gyro=lambda r: w(y=trem_dot(r)), gravity=lambda r: rolled_gravity(trem(r)))
        self.assertTrue(rig.am.scroll.active)
        self.assertLessEqual(len(rig.wheel()), 5, rig.wheel())

    def test_gap_autopause_and_stale(self):
        rig = Rig().calibrate()
        travel0 = rig.am.travel
        rig.run(1.0, gyro=w(z=200), deliver_at_end=True)     # nothing arrives for 1 s, then one 100-sample message
        self.assertEqual(rig.am.status()["pausa"], "sin datos")
        self.assertEqual(rig.am.travel, travel0)
        self.assertGreater(rig.am.stale_count, 0)
        stale = rig.am.stale_count
        rig.run(0.3, gyro=w(z=200))
        self.assertEqual(rig.am.travel, travel0)              # the message that resumes moves nothing
        rig.run(0.3, gyro=w(z=200))
        self.assertIsNone(rig.am.status()["pausa"])
        self.assertGreater(rig.am.travel, travel0)
        self.assertEqual(rig.am.stale_count, stale)
        # a hole in sample time is logged and blanks gestures without raising
        rig.t += 500
        rig.run(0.5)
        self.assertEqual(len(rig.am.gaps), 1)
        self.assertAlmostEqual(rig.am.gaps[0][1], 510, delta=1)

    def test_irregular_interval_integrates_fully(self):
        # one 60 ms gyro interval while sweeping at 100 deg/s must integrate 6 deg, not the 10 ms median
        def sweep(rig, drop):
            rig.calibrate()
            p0 = rig.pos
            t_start, pending = rig.t, []
            for i in range(100):
                rig.t += 10.0
                if drop and 50 <= i < 55:
                    continue
                for src, val in (("GYROSCOPE", w(z=100)), ("ACCELERATION", ACC), ("GRAVITY", GRAV)):
                    pending.append([src, rig.t, {"x": val[0], "y": val[1], "z": val[2]}])
                if len(pending) >= 6:
                    rig.send(pending)
                    pending = []
            rig.run(0.4)
            return rig.pos[0] - p0[0]
        full, dropped = sweep(Rig(), False), sweep(Rig(), True)
        self.assertLess(abs(dropped - full), 0.05 * abs(full) + 2, (full, dropped))
        # a dropped accelerometer sample does not turn a 1.3 m/s2-per-sample ramp into a tap candidate
        rig = Rig().calibrate()
        pending = []
        for i in range(100):
            rig.t += 10.0
            az = 9.81 + 1.3 * max(0, min(4, i - 50))
            for src, val in (("GYROSCOPE", quiet_gyro(i / 100)), ("ACCELERATION", (0.0, 0.0, az)), ("GRAVITY", GRAV)):
                if src == "ACCELERATION" and i == 52:
                    continue
                pending.append([src, rig.t, {"x": val[0], "y": val[1], "z": val[2]}])
            if len(pending) >= 6:
                rig.send(pending)
                pending = []
        self.assertEqual(rig.am.tap.candidates, 0)

    def test_watch_disconnected_and_hello(self):
        rig = Rig().calibrate()
        travel0 = rig.am.travel
        rig.msg({"type": "watch", "connected": False})
        self.assertEqual(rig.am.status()["pausa"], "reloj desconectado")
        rig.run(0.5, gyro=w(z=30))
        self.assertEqual(rig.am.travel, travel0)
        rig.msg({"type": "watch", "connected": True})
        bias = list(rig.am.motion.bias)
        rig.am.motion.theta0 = 40.0
        rig.msg({"type": "hello", "app": "test"})
        self.assertEqual(rig.am.motion.bias, bias)
        self.assertEqual(rig.am.motion.theta0, rig.am.motion.theta)
        self.assertEqual(rig.am.status()["pausa"], "calentando")
        rig.run(0.9, gyro=w(z=30))
        self.assertEqual(rig.am.travel, travel0)
        rig.run(0.5, gyro=w(z=30))
        self.assertIsNone(rig.am.status()["pausa"])
        self.assertGreater(rig.am.travel, travel0)

    def test_yield_and_kill_corner(self):
        rig = Rig().calibrate()
        rig.pointer.pos = (500, 500)
        rig.idle_ticks(0.05)
        self.assertEqual(rig.am.status()["pausa"], "ratón físico")
        self.assertEqual([round(v) for v in rig.am.P], [500, 500])
        rig.run(0.5, gyro=w(z=30))
        self.assertEqual(rig.pos, (500, 500))
        rig.run(0.6, gyro=w(z=30))
        self.assertIsNone(rig.am.status()["pausa"])
        self.assertNotEqual(rig.pos, (500, 500))
        rig.pointer.pos = (1, 1)
        rig.idle_ticks(1.35)                     # brushing or briefly visiting the corner must not kill
        self.assertFalse(rig.am.kill_requested)
        rig.idle_ticks(0.25)                     # parked there for KILL_CORNER_S: kill
        self.assertTrue(rig.am.kill_requested)
        self.assertIn(("release",), rig.pointer.log)

    def test_cursor_unreadable_pauses_instead_of_killing(self):
        # GetCursorPos fails on the lock screen / UAC desktop: the (0, 0) a fresh POINT reads must not
        # count as the kill corner, nor resync P to the top-left
        rig = Rig().calibrate()
        rig.run(0.5, gyro=w(z=30))
        rig.run(0.5)                                     # let the filter tail settle
        p_before, pos_before = list(rig.am.P), rig.pos
        rig.pointer.fail_cursor = True
        rig.run(1.0)                                     # 20 ticks of "no cursor" while the data keeps coming
        self.assertFalse(rig.am.kill_requested)
        self.assertEqual(rig.am.status()["pausa"], "escritorio no disponible")
        self.assertEqual(rig.am.P, p_before)
        rig.run(0.5, gyro=w(z=30))                       # moving the wrist while locked does nothing
        self.assertEqual(rig.pos, pos_before)
        self.assertEqual(rig.am.P, p_before)
        rig.pointer.fail_cursor = False
        rig.pointer.pos = (700, 400)                     # the user moved the mouse while it was locked
        rig.idle_ticks(0.05)
        self.assertIsNone(rig.am.status()["pausa"])
        self.assertEqual([round(v) for v in rig.am.P], [700, 400])
        rig.run(0.5, gyro=w(z=30))
        self.assertNotEqual(rig.pos, (700, 400))

    def test_kill_corner_is_reachable(self):
        # laptop panel (primary, at the origin) next to a taller external monitor raised 216 px: the virtual
        # screen's top-left (0, -216) is dead space the physical mouse can never reach
        monitors = [(0, 0, 1536, 864), (1536, -216, 1920, 1080)]
        bounds = (0, -216, 3456, 1080)
        self.assertEqual(air_mouse.corner_of("tl", bounds, monitors), ((0, 0), True))
        self.assertEqual(air_mouse.corner_of("bl", bounds, monitors), ((0, 863), False))
        self.assertEqual(air_mouse.corner_of("tr", bounds, monitors), ((3455, -216), False))
        self.assertEqual(air_mouse.corner_of("br", bounds, monitors), ((3455, 863), False))
        self.assertEqual(air_mouse.corner_of("tl", bounds, None), ((0, -216), False))
        for move in ("absolute", "relative"):
            rig = Rig(bounds=bounds, monitors=monitors, move=move).calibrate()
            self.assertEqual(rig.am._corner(), (0, 0))
            rig.run(3.0, gyro=w(x=200, z=200))           # up-left into the corner: our moves stay out of the inset
            rig.run(0.6)
            self.assertFalse(rig.am.kill_requested, move)
            for e in rig.moves():
                self.assertFalse(abs(e[1]) < 4 and abs(e[2]) < 4, (move, e))
            rig.pointer.pos = (1, 1)                     # the physical mouse parked there exits
            rig.idle_ticks(air_mouse.KILL_CORNER_S + 0.1)
            self.assertTrue(rig.am.kill_requested, move)

    def test_release_on_shutdown(self):
        rig = Rig().calibrate()
        rig.am.shutdown()
        self.assertIn(("release",), rig.pointer.log)
        self.assertEqual([e for e in rig.pointer.log if e[0] == "up"], [])
        p = air_mouse.DryRunPointer(BOUNDS, quiet=True)
        p.partial_insert = True
        p.click()
        self.assertEqual(p.held, {"left"})
        p.release_all()
        self.assertEqual([e for e in p.log if e[0] == "up"], [("up", "left")])
        self.assertEqual(p.held, set())
        # a watch button pressed (right/middle too) and never released is let go at shutdown
        p = air_mouse.DryRunPointer(BOUNDS, quiet=True)
        p._say = lambda *a, **k: None
        p.press("right")
        p.press("middle")
        p.release("middle")
        self.assertEqual(p.held, {"right"})
        p.release_all()
        self.assertEqual([e for e in p.log if e[0] == "up"], [("up", "middle"), ("up", "right")])
        self.assertEqual(p.held, set())

    def test_win32_release_keeps_button_until_up_is_inserted(self):
        # pure logic on a Win32Pointer that never touches user32: a blocked LEFTUP keeps 'left' in `held`
        # so the next release_all (atexit, console handler) retries it
        ptr = air_mouse.Win32Pointer.__new__(air_mouse.Win32Pointer)
        ptr.MOUSEINPUT = lambda *a: a
        ptr.held = {"left"}
        sent = []
        ptr._send = lambda *mis: sent.append(mis) or 0
        with contextlib.redirect_stdout(io.StringIO()):
            ptr.release_all()
        self.assertEqual(ptr.held, {"left"})
        self.assertEqual(len(sent), 5)
        ptr._send = lambda *mis: sent.append(mis) or 1
        ptr.release_all()
        self.assertEqual(ptr.held, set())
        self.assertEqual(len(sent), 6)
        ptr.release_all()                                 # nothing held: never a blind UP
        self.assertEqual(len(sent), 6)
        self.assertEqual(air_mouse.E_ACCESSDENIED, 0x80070005)
        # right and middle go through BUTTON_FLAGS: press adds to `held` only when inserted, release
        # discards only when inserted, release_all sends each button's own UP flag
        flags = air_mouse.BUTTON_FLAGS
        self.assertEqual(flags["left"], (air_mouse.MOUSEEVENTF_LEFTDOWN, air_mouse.MOUSEEVENTF_LEFTUP))
        self.assertEqual(flags["right"], (0x0008, 0x0010))
        self.assertEqual(flags["middle"], (0x0020, 0x0040))
        sent.clear()
        ptr._send = lambda *mis: sent.append(mis) or 0
        ptr.press("right")
        self.assertEqual(ptr.held, set())
        ptr._send = lambda *mis: sent.append(mis) or 1
        ptr.press("right")
        ptr.press("middle")
        self.assertEqual(ptr.held, {"right", "middle"})
        self.assertEqual([m[0][3] for m in sent[-2:]], [0x0008, 0x0020])
        ptr._send = lambda *mis: sent.append(mis) or 0
        ptr.release("middle")
        self.assertEqual(ptr.held, {"right", "middle"})
        ptr._send = lambda *mis: sent.append(mis) or 1
        ptr.release("middle")
        self.assertEqual(ptr.held, {"right"})
        sent.clear()
        ptr.held = {"left", "right", "middle"}
        ptr.release_all()
        self.assertEqual({m[0][3] for m in sent}, {0x0004, 0x0010, 0x0040})
        self.assertEqual(ptr.held, set())

    def test_shake_toggle(self):
        shake = lambda r: w(x=900 * math.sin(2 * math.pi * 5 * r))     # 5 Hz, +-900 deg/s: a 29 deg wobble
        rig = Rig().calibrate()
        p0 = rig.pos
        rig.run(0.7, gyro=shake)
        rig.run(0.5)
        self.assertEqual(rig.am.shake.toggles, 1)
        self.assertEqual(rig.am.status()["pausa"], "usuario")
        self.assertIn("sacudida: pausa", rig.lines)
        self.assertLess(math.dist(rig.pos, p0), 5)
        rig.run(0.7, gyro=shake)
        rig.run(0.5)
        self.assertEqual(rig.am.shake.toggles, 2)
        self.assertIsNone(rig.am.status()["pausa"])
        rig = Rig().calibrate()
        rig.run(0.4, gyro=shake)                        # only 3 reversals
        rig.run(1.0)
        self.assertEqual(rig.am.shake.toggles, 0)
        self.assertIsNone(rig.am.status()["pausa"])

    def test_calibration_waits_for_rest(self):
        # started while pointing (+-8 deg/s sinusoids): no bias until the wrist rests, then no creep
        wave = lambda r: w(x=8 * math.cos(2 * math.pi * 0.5 * r), z=8 * math.sin(2 * math.pi * 0.5 * r))
        rig = Rig()
        rig.run(12.0, gyro=wave)
        self.assertFalse(rig.am.motion.calibrated)
        self.assertGreater(rig.am.motion.calib_reject["movimiento"], 0)
        self.assertTrue(any(l.startswith("calibrando: sin reposo en 10 s") for l in rig.lines), rig.lines)
        self.assertEqual(rig.moves(), [])
        rig.run(2.2)
        self.assertTrue(rig.am.motion.calibrated)
        self.assertLess(max(abs(b - t) for b, t in zip(rig.am.motion.bias, BIAS)), 0.1)
        p0, travel0 = rig.pos, rig.am.travel
        rig.run(3.0)
        self.assertEqual(rig.pos, p0)
        self.assertEqual(rig.am.travel, travel0)
        # started during a steady 5 deg/s yaw (p2p = 0): a constant rotation is not rest
        rig = Rig()
        rig.run(12.0, gyro=w(z=5))
        self.assertFalse(rig.am.motion.calibrated)
        self.assertGreater(rig.am.motion.calib_reject["giro constante"], 0)
        rig.run(2.2)
        self.assertTrue(rig.am.motion.calibrated)
        self.assertLess(max(abs(b - t) for b, t in zip(rig.am.motion.bias, BIAS)), 0.1)
        # a linear shove with the gyro quiet is not rest either
        rig = Rig()
        rig.run(3.0, accel=lambda r: (0.0, 0.0, 9.81 + 2.0 * math.sin(2 * math.pi * 0.5 * r)))
        self.assertFalse(rig.am.motion.calibrated)
        self.assertGreater(rig.am.motion.calib_reject["aceleración"], 0)

    def test_background_recalibration_keeps_bias_while_moving(self):
        rig = Rig().calibrate()
        bias0 = list(rig.am.motion.bias)
        rig.hole(1.0)                                    # the watch stops for 1 s -> 'sin datos'
        self.assertEqual(rig.am.status()["pausa"], "sin datos")
        rig.run(0.6, gyro=w(z=20))                       # resumes while pointing
        self.assertIsNone(rig.am.status()["pausa"])
        rig.run(10.5, gyro=lambda r: w(z=20 * math.cos(2 * math.pi * 0.3 * r)))
        self.assertTrue(any("recalibro el sesgo en segundo plano" in l for l in rig.lines), rig.lines)
        rig.run(1.5, gyro=w(z=5))                        # a steady 5 deg/s pan during the background recal
        self.assertLess(max(abs(a - b) for a, b in zip(rig.am.motion.bias, bias0)), 0.1, rig.am.motion.bias)
        rig.run(10.0, gyro=w(z=5))
        self.assertIn("sin reposo en 10 s: mantengo el sesgo anterior", rig.lines)
        self.assertFalse(rig.am.motion.background)
        self.assertLess(max(abs(a - b) for a, b in zip(rig.am.motion.bias, bias0)), 0.1, rig.am.motion.bias)
        rig.run(1.0)
        p0, travel0 = rig.pos, rig.am.travel
        rig.run(3.0)                                     # at true rest the cursor must not creep
        self.assertEqual(rig.pos, p0)
        self.assertEqual(rig.am.travel, travel0)
        # a background recal while actually at rest does update the bias (and only then)
        rig = Rig().calibrate()
        rig.am.motion.start_calibration(background=True)
        rig.run(2.0)
        self.assertFalse(rig.am.motion.background)
        self.assertLess(max(abs(b - t) for b, t in zip(rig.am.motion.bias, BIAS)), 0.1)

    def test_large_bias_error_recovers_at_rest(self):
        rig = Rig().calibrate()
        rig.am.motion.bias = [5.0, -0.07, -0.07]        # the watch's bias jumped: the slow tracker cannot engage
        rig.run(1.0)
        self.assertGreater(rig.am.travel, 0)             # creeping
        rig.run(4.0)
        self.assertEqual(rig.am.motion.recoveries, 1)
        self.assertLess(max(abs(b - t) for b, t in zip(rig.am.motion.bias, BIAS)), 0.1)
        self.assertTrue(any(l.startswith("sesgo recuperado") for l in rig.lines))
        p0, travel0 = rig.pos, rig.am.travel
        rig.run(3.0)
        self.assertEqual(rig.pos, p0)
        self.assertEqual(rig.am.travel, travel0)
        # a steady 5 deg/s rotation with a good bias (swivel chair) is not mistaken for a bias error
        rig = Rig().calibrate()
        rig.run(5.0, gyro=w(z=5))
        self.assertEqual(rig.am.motion.recoveries, 0)
        self.assertLess(max(abs(b - t) for b, t in zip(rig.am.motion.bias, BIAS)), 0.1)

    def test_tap_without_accelerometer_expires(self):
        rig = Rig().calibrate()
        rig.run(0.1, accel=spike_accel(5))               # candidate armed, then the accelerometer stream dies
        self.assertTrue(rig.am.tap.pending and rig.am.tap.pending["armed"])
        p0 = rig.pos
        rig.run(1.0, gyro=w(z=30), sources=("GYROSCOPE", "GRAVITY"))
        self.assertIsNone(rig.am.tap.pending)
        self.assertEqual(rig.am.tap.expired, 1)
        self.assertEqual(rig.clicks(), [])
        self.assertFalse(rig.am.frozen(rig.t))
        self.assertNotEqual(rig.pos, p0)                 # the cursor is not frozen forever
        rig.run(2.0, gyro=w(z=30), sources=("GYROSCOPE", "GRAVITY"))
        self.assertTrue(rig.am.accel_lost)
        self.assertIn("sin acelerómetro", rig.am.status_line(rig.now_ms() / 1000.0))
        rig.run(0.5, accel=spike_accel(20))              # while lost, a spike must not arm
        self.assertFalse(rig.am.accel_lost)
        rig.run(0.3)
        self.assertEqual(rig.clicks(), [])

    def test_parse_robustness(self):
        rig = Rig().calibrate()
        nan, inf = float("nan"), float("inf")
        bad = [
            "x", [1, 2], ["GYROSCOPE", "t", {"x": 1, "y": 2, "z": 3}], ["GYROSCOPE", True, {"x": 1, "y": 2, "z": 3}],
            ["GYROSCOPE", 1, [1, 2, 3]], ["GYROSCOPE", 1, {"x": 1, "y": 2}], ["GYROSCOPE", 1, {"x": "a", "y": 2, "z": 3}],
            ["GYROSCOPE", 1, {"x": nan, "y": 2, "z": 3}], None,
            ["GYROSCOPE", nan, {"x": 1, "y": 2, "z": 3}], ["GYROSCOPE", inf, {"x": 1, "y": 2, "z": 3}],
            ["GYROSCOPE", -inf, {"x": 1, "y": 2, "z": 3}], ["ACCELERATION", nan, {"x": 1, "y": 2, "z": 3}],
            ["GYROSCOPE", rig.t + 2 * air_mouse.MAX_AGE_MS, {"x": 1, "y": 2, "z": 3}],
        ]
        rig.msg({"type": "data", "t": nan, "samples": bad + [["FOO", 1, {"x": 1, "y": 2, "z": 3}], ["HRM", 1, {"heartRate": 70}]]})
        rig.msg({"type": "data", "samples": "nope"})
        rig.msg({"type": "data"})
        rig.msg("nope")
        rig.msg({"type": "status"})
        rig.msg({"type": "watch"})
        self.assertEqual(rig.am.malformed, len(bad) + 3)
        self.assertEqual(rig.am.unknown, 1)
        self.assertIsNone(rig.am.bridge_lag)
        self.assertEqual(rig.am.status()["pausa"], "reloj desconectado")   # {"type": "watch"} = not connected
        rig.msg({"type": "watch", "connected": True})
        p0 = rig.pos
        rig.run(5.0, gyro=w(z=30))                       # still alive, still moving, nothing poisoned
        self.assertNotEqual(rig.pos, p0)
        self.assertTrue(all(math.isfinite(v) for v in rig.am.P))
        self.assertLess(rig.am.gap_blank_until, rig.t)
        for dq in (rig.am.shake.hist, rig.am.scroll.hist_e, rig.am.scroll.hist_r, rig.am.motion.calib,
                   rig.am.tap.acc, rig.am.tap.gyro, rig.am.ring, rig.am.click_times):
            self.assertIsNotNone(dq.maxlen)
        self.assertLessEqual(len(rig.am.shake.hist), 75)
        self.assertEqual(air_mouse.clamp(nan, 1, 2), 1)

    def test_task_failure_stops_run_and_releases(self):
        # an exception in the consumer (source or handle_message) must end run_live with the traceback
        # printed and the buttons released, never hang with 'pausa: sin datos' scrolling by
        async def dead_source(url):
            yield {"type": "hello"}, 0.0
            yield {"type": "data", "samples": [["GYROSCOPE", 1.0, {"x": 0, "y": 0, "z": 0}]]}, 0.01
            raise RuntimeError("boom")

        async def go(**kw):
            args = air_mouse.make_config(status_every=0.05, control_port=0, **kw)
            pointer = air_mouse.DryRunPointer(BOUNDS, quiet=True)
            return await asyncio.wait_for(air_mouse.run_live(args, pointer), 3.0), pointer

        saved = air_mouse.ui_source
        air_mouse.ui_source = dead_source
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                am, pointer = asyncio.run(go())
            self.assertEqual(am.failed, "consume")
            self.assertIn("boom", out.getvalue())
            self.assertIn(("release",), pointer.log)
            # a dead ticker (kill corner, Pause, yield and watchdog gone) stops the run too
            async def forever(url):
                while True:
                    await asyncio.sleep(0.01)
                    yield {"type": "data", "samples": []}, 0.0
            air_mouse.ui_source = forever
            tick = air_mouse.AirMouse.tick

            def bad_tick(self, now):
                raise ValueError("tick")
            air_mouse.AirMouse.tick = bad_tick
            try:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    am, pointer = asyncio.run(go())
            finally:
                air_mouse.AirMouse.tick = tick
            self.assertEqual(am.failed, "ticker")
            self.assertIn("ValueError: tick", out.getvalue())
            self.assertIn(("release",), pointer.log)
        finally:
            air_mouse.ui_source = saved

    def test_ui_source_reports_each_retry(self):
        out = io.StringIO()

        async def first_attempts():
            gen = air_mouse.ui_source("ws://127.0.0.1:1/ui", retry_s=0.2)   # nothing listens on port 1
            task = asyncio.ensure_future(gen.__anext__())
            try:
                for _ in range(100):                                      # up to 10 s for two attempts
                    await asyncio.sleep(0.1)
                    if task.done() or "(intento 2)" in out.getvalue():
                        break
                return "yielded" if task.done() and not task.cancelled() else "waiting"
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await gen.aclose()
        with contextlib.redirect_stdout(out):
            res = asyncio.run(first_attempts())
        self.assertEqual(res, "waiting")
        self.assertIn("sin conexión con ws://127.0.0.1:1/ui", out.getvalue())
        self.assertIn("reintento en 0.2 s", out.getvalue())
        self.assertIn("reconectando a ws://127.0.0.1:1/ui (intento 2)", out.getvalue())

    def test_replay_report_smoke(self):
        with tempfile.TemporaryDirectory() as d:
            t0 = 1_700_000_000_000
            for name, values in (("GYROSCOPE", lambda i: (BIAS[0], BIAS[1], BIAS[2] + (0.07 if i % 2 else 0))),
                                 ("ACCELERATION", lambda i: ACC), ("GRAVITY", lambda i: GRAV)):
                with open(os.path.join(d, f"{name}.csv"), "w", newline="") as fh:
                    wr = csv.writer(fh)
                    wr.writerow(["t_watch_ms", "t_recv_ms", "x", "y", "z"])
                    for i in range(200):
                        t = t0 + 10 * i
                        wr.writerow([t, t + 5 + 10 * ((i // 2) % 2), *values(i)])
            with contextlib.redirect_stdout(io.StringIO()):
                res = air_mouse.replay(d, air_mouse.make_config())
        for key in ("duracion_s", "reposo_ventanas", "reposo_px_s_medio", "reposo_px_s_max", "tap_candidatos",
                    "tap_confirmados", "clics_por_min", "dwell", "scroll_entradas", "scroll_senal_entradas", "muescas",
                    "sacudidas", "pausas_sin_datos", "descartadas", "huecos", "paradas_200ms", "dt_hist", "px_total",
                    "sesgo_recuperaciones", "recortes_presupuesto"):
            self.assertIn(key, res)
        self.assertEqual(res["exit_code"], 0)
        self.assertGreaterEqual(res["reposo_ventanas"], 1)
        self.assertEqual(res["reposo_px_s_medio"], 0.0)
        self.assertEqual(res["tap_candidatos"], 0)
        self.assertAlmostEqual(res["duracion_s"], 2.0, delta=0.05)

    # ---- 1.2: bezel, buttons, control channel, yield fix ----

    def test_gain_y(self):
        moved = {}
        for gy in (1.0, 2.0):
            rig = Rig(gain_y=gy).calibrate()
            p0 = rig.pos
            rig.run(0.5, gyro=w(x=30))
            rig.run(0.4)
            moved[gy] = (rig.pos[0] - p0[0], rig.pos[1] - p0[1])
            self.assertLess(abs(moved[gy][0]), 2, gy)
        self.assertLess(abs(moved[2.0][1] - 2 * moved[1.0][1]), 0.15 * abs(2 * moved[1.0][1]), moved)
        rig = Rig(gain_y=2.0).calibrate()                 # horizontal untouched
        p0 = rig.pos
        rig.run(0.5, gyro=w(z=30))
        rig.run(0.4)
        flat = Rig().calibrate()
        f0 = flat.pos
        flat.run(0.5, gyro=w(z=30))
        flat.run(0.4)
        self.assertEqual(rig.pos[0] - p0[0], flat.pos[0] - f0[0])
        self.assertEqual(air_mouse.TUNABLES["gain_y"].lo, 0.2)

    def test_auto_modes(self):
        rig = Rig().calibrate()                           # no hello (replay, sdb source): tap and roll
        self.assertEqual((rig.am.click_mode, rig.am.scroll_mode), ("tap", "roll"))
        self.assertEqual(rig.am.status()["modos"], {"click": "tap", "scroll": "roll"})
        self.assertEqual(rig.am.status()["entradas"], {"bezel": False, "button": False})
        rig.hello(["BEZEL", "BUTTON"])
        self.assertEqual((rig.am.click_mode, rig.am.scroll_mode), ("button", "bezel"))
        self.assertIn("entradas del reloj: bisel sí · botón sí", rig.lines)
        self.assertIn("modos: clic por button, scroll por bezel", rig.lines)
        self.assertEqual(rig.am.status()["entradas"], {"bezel": True, "button": True})
        rig.msg({"type": "status", "source": "BEZEL", "state": "error", "detail": "no se pudo leer"})
        self.assertEqual(rig.am.status()["entradas"], {"bezel": False, "button": True})
        rig.msg({"type": "hello", "app": "air-mouse 1.2"})   # the sdb source's hello: no inputs
        self.assertEqual((rig.am.click_mode, rig.am.scroll_mode), ("tap", "roll"))
        rig = Rig(click="tap").calibrate().hello(["BUTTON"])  # an explicit choice is not overridden
        self.assertEqual((rig.am.click_mode, rig.am.scroll_mode), ("tap", "roll"))
        self.assertEqual(rig.am.apply_params({"click": "button"}), ["click"])
        self.assertEqual(rig.am.click_mode, "button")
        self.assertEqual(rig.am.apply_params({"click": "button"}), [])
        rig.am.apply_params({"click": "auto"})
        self.assertEqual(rig.am.click_mode, "button")
        # leaving roll while a roll scroll is active exits it
        rate = -50.0 / 0.6
        rig = Rig().calibrate()
        rig.run(0.6, gyro=w(y=rate), gravity=lambda r: rolled_gravity(rate * r))
        rig.run(0.5, gravity=rolled_gravity(-50))
        self.assertTrue(rig.am.scroll.active)
        rig.am.apply_params({"scroll": "none"})
        self.assertFalse(rig.am.scroll.active)
        self.assertEqual(rig.am.scroll_mode, "none")
        self.assertIn("scroll: salgo", rig.lines)
        rig.run(1.0, gravity=rolled_gravity(-50))
        self.assertEqual(rig.wheel(), [1, 1, 1, 1])     # nothing more after the mode change

    def test_button_click_and_drag(self):
        rig = Rig().calibrate().hello(["BUTTON"])
        self.assertEqual(rig.am.click_mode, "button")
        rig.button("back", True)
        self.assertEqual(rig.downs(), [("down", "left")])
        self.assertEqual(rig.am.status()["boton"]["held"], "left")
        self.assertEqual(rig.events("button")[-1]["action"], "leftdown")
        travel0 = rig.am.travel
        rig.run(0.1, gyro=w(z=30))                       # frozen 150 ms after the DOWN: a click, not a drag
        self.assertEqual(rig.am.travel, travel0)
        rig.run(0.4, gyro=w(z=30))                       # held longer: a drag, the cursor moves normally
        self.assertGreater(rig.am.travel, travel0 + 50)
        self.assertEqual(rig.ups(), [])
        self.assertGreater(rig.am.status()["boton"]["ms"], 400)
        self.assertIn("botón ↓", rig.am.status_line(rig.now_ms() / 1000.0))
        rig.button("back", False)
        self.assertEqual(rig.ups(), [("up", "left")])
        self.assertEqual(rig.am.clicks, 1)
        self.assertIsNone(rig.am.held)
        self.assertEqual(rig.clicks(), [])               # never a [DOWN, UP] pair on top of the drag
        ev = rig.events("click")[-1]
        self.assertEqual(ev["how"], "button")
        self.assertGreater(ev["held_ms"], 400)
        self.assertNotIn("botón ↓", rig.am.status_line(rig.now_ms() / 1000.0))
        # a tap spike in button mode arms nothing (and clicks nothing)
        rig.run(0.5, accel=spike_accel(10))
        self.assertFalse(rig.am.tap.pending and rig.am.tap.pending["armed"])
        rig.run(0.4)
        self.assertEqual(rig.am.clicks, 1)
        # press, release, move, press again within 500 ms: the second DOWN lands where the first click was
        rig.run(0.6)
        rig.button("back", True)
        rig.button("back", False)
        first = rig.clicks()[-1][1:] if rig.clicks() else rig.pos
        self.assertEqual(rig.am.clicks, 2)
        rig.run(0.3, gyro=w(z=30))
        self.assertNotEqual(rig.pos, first)
        rig.button("back", True)
        self.assertEqual(rig.pos, first)
        self.assertEqual(len(rig.downs()), 3)
        rig.button("back", False)
        self.assertEqual(rig.am.clicks, 3)
        # pressing twice without releasing is one press
        rig.run(0.6)
        rig.button("back", True)
        rig.button("back", True)
        self.assertEqual(len(rig.downs()), 4)
        self.assertEqual(rig.events("button")[-1]["reason"], "ya pulsado")
        rig.button("back", False)
        self.assertEqual(len(rig.ups()), 4)

    def test_button_safety(self):
        # the watch disconnects while the button is held: the UP goes out at once
        rig = Rig().calibrate().hello(["BUTTON"])
        rig.button("back", True)
        rig.run(0.2)
        rig.msg({"type": "watch", "connected": False})
        self.assertEqual(rig.ups(), [("up", "left")])
        self.assertIsNone(rig.am.held)
        self.assertEqual(rig.events("held_release")[-1]["reason"], "pausa")
        self.assertEqual(rig.am.clicks, 0)
        # held for 10 s: released, the real release later is ignored
        rig = Rig().calibrate().hello(["BUTTON"])
        rig.button("back", True)
        rig.run(9.5)
        self.assertEqual(rig.ups(), [])
        rig.run(1.0)
        self.assertEqual(rig.ups(), [("up", "left")])
        self.assertIsNone(rig.am.held)
        self.assertIn("botón mantenido 10 s: lo suelto", rig.lines)
        rig.button("back", False)
        self.assertEqual(rig.ups(), [("up", "left")])
        self.assertEqual(rig.events("button")[-1]["reason"], "sin pulsación")
        # shutdown while held
        rig = Rig().calibrate().hello(["BUTTON"])
        rig.button("back", True)
        rig.run(0.1)
        rig.am.shutdown()
        self.assertEqual(rig.ups(), [("up", "left")])
        self.assertIn(("release",), rig.pointer.log)
        self.assertEqual(rig.pointer.held, set())
        # a press while paused (user pause) is not applied
        rig = Rig().calibrate().hello(["BUTTON"])
        rig.am._pause("usuario")
        rig.button("back", True)
        self.assertEqual(rig.downs(), [])
        self.assertEqual(rig.events("button")[-1]["reason"], "pausa")
        rig.am._resume("usuario")
        # a pause with the DOWN still queued (same message): dropped, never sent, no UP needed
        rig.send([["BUTTON", rig.now_ms(), {"key": "back", "pressed": True}],
                  ["GYROSCOPE", rig.t, {"x": 0, "y": 0, "z": 0}]])   # a stale gyro sample is harmless
        self.assertEqual(len(rig.downs()), 1)
        rig.am._pause("usuario")
        self.assertEqual(rig.ups(), [("up", "left")])
        rig.am._resume("usuario")
        # stale press ignored, stale release of a held button honoured
        stale0 = rig.am.stale_count
        rig.button("back", True, age_ms=1500)
        self.assertEqual(len(rig.downs()), 1)
        self.assertEqual(rig.events("button")[-1]["reason"], "antiguo")
        self.assertEqual(rig.am.stale_count, stale0 + 1)
        rig.button("back", True)
        self.assertEqual(len(rig.downs()), 2)
        rig.button("back", False, age_ms=1500)
        self.assertEqual(len(rig.ups()), 2)
        self.assertIsNone(rig.am.held)
        # home key: optional second button; a home press while left is held is ignored
        rig = Rig(home_key="right").calibrate().hello(["BUTTON"])
        rig.button("home", True)
        self.assertEqual(rig.downs(), [("down", "right")])
        rig.button("home", False)
        self.assertEqual(rig.ups(), [("up", "right")])
        self.assertEqual(rig.am.clicks, 1)
        rig.button("back", True)
        rig.button("home", True)
        self.assertEqual(rig.events("button")[-1]["reason"], "ya pulsado")
        self.assertEqual(len(rig.downs()), 2)
        rig.button("back", False)
        rig.button("home", False)
        self.assertEqual(rig.events("button")[-1]["reason"], "sin pulsación")
        rig = Rig().calibrate().hello(["BUTTON"])
        rig.button("home", True)
        self.assertEqual(rig.downs(), [])
        self.assertEqual(rig.events("button")[-1]["reason"], "inicio desactivado")
        # tap mode: the button is reported, not applied
        rig = Rig(click="tap").calibrate().hello(["BUTTON"])
        rig.button("back", True)
        self.assertEqual(rig.downs(), [])
        self.assertEqual(rig.events("button")[-1]["reason"], "modo tap")
        # a mode change while held releases
        rig = Rig().calibrate().hello(["BUTTON"])
        rig.button("back", True)
        rig.run(0.1)
        rig.am.apply_params({"click": "tap"})
        self.assertEqual(rig.ups(), [("up", "left")])
        self.assertEqual(rig.events("held_release")[-1]["reason"], "modo")
        # malformed
        bad0 = rig.am.malformed
        rig.send([["BUTTON", rig.now_ms(), {"key": "back", "pressed": 1}], ["BUTTON", rig.now_ms(), {"key": "x", "pressed": True}],
                  ["BUTTON", rig.now_ms(), [1]], ["BUTTON", "t", {"key": "back", "pressed": True}]])
        self.assertEqual(rig.am.malformed, bad0 + 4)
        self.assertIsNone(rig.am.held)

    def test_bezel_wheel(self):
        rig = Rig().calibrate().hello(["BEZEL"])
        self.assertEqual(rig.am.scroll_mode, "bezel")
        rig.bezel("CW", 1, raw=1)
        self.assertEqual(rig.wheel(), [-1])              # CW = page down = negative WHEEL_DELTA
        rig.bezel("CCW", 2, raw=-2)
        self.assertEqual(rig.wheel(), [-1, 2])
        self.assertEqual(rig.am.status()["rueda"], 3)
        self.assertEqual(rig.events("bezel")[-1], {"direction": "CCW", "steps": 2, "raw": -2, "notches": 2,
                                                   "applied": True, "reason": None})
        self.assertEqual(rig.events("wheel")[-1], {"n": 2, "source": "bezel"})
        self.assertIn("bisel CCW ×2 → rueda +2", rig.lines)
        rig.bezel("CW")                                  # the fake watch's sample: no raw, no steps
        self.assertEqual(rig.wheel(), [-1, 2, -1])
        rig = Rig(bezel_notches=2).calibrate().hello(["BEZEL"])
        rig.bezel("CCW", 2)
        self.assertEqual(rig.wheel(), [4])
        rig = Rig(bezel_notches=2, bezel_invert=True).calibrate().hello(["BEZEL"])
        rig.bezel("CCW", 2)
        self.assertEqual(rig.wheel(), [-4])
        rig.am.apply_params({"bezel_invert": False, "bezel_notches": 1})
        rig.bezel("CCW", 2)
        self.assertEqual(rig.wheel(), [-4, 2])
        # roll mode: reported, not applied
        rig = Rig(scroll="roll").calibrate().hello(["BEZEL"])
        rig.bezel("CW")
        self.assertEqual(rig.wheel(), [])
        self.assertEqual(rig.events("bezel")[-1]["applied"], False)
        self.assertEqual(rig.events("bezel")[-1]["reason"], "modo roll")
        # stale and paused samples are not applied
        rig = Rig().calibrate().hello(["BEZEL"])
        rig.bezel("CW", age_ms=1500)
        self.assertEqual(rig.wheel(), [])
        self.assertEqual(rig.events("bezel")[-1]["reason"], "antiguo")
        self.assertEqual(rig.am.stale_count, 1)
        rig.am._pause("usuario")
        rig.bezel("CW")
        self.assertEqual(rig.wheel(), [])
        self.assertEqual(rig.events("bezel")[-1]["reason"], "pausa")
        rig.am._resume("usuario")
        # in bezel mode the forearm roll scrolls nothing (and still moves the cursor nothing)
        rate = -50.0 / 0.6
        p0 = rig.pos
        rig.run(0.6, gyro=w(y=rate), gravity=lambda r: rolled_gravity(rate * r))
        rig.run(1.0, gravity=rolled_gravity(-50))
        self.assertEqual(rig.am.scroll.entries, 0)
        self.assertEqual(rig.wheel(), [])
        self.assertLess(math.dist(rig.pos, p0), 2)
        # malformed
        bad0 = rig.am.malformed
        rig.send([["BEZEL", rig.now_ms(), {"direction": "UP"}], ["BEZEL", rig.now_ms(), {"direction": "CW", "steps": 0}],
                  ["BEZEL", rig.now_ms(), {"direction": "CW", "steps": 1.5}], ["BEZEL", rig.now_ms(), {"direction": "CW", "raw": "1"}]])
        self.assertEqual(rig.am.malformed, bad0 + 4)
        self.assertEqual(rig.wheel(), [])
        # the bezel and the buttons need no gyro calibration (no hello here: a hello pauses 'calentando')
        rig = Rig()
        rig.am.available = {"BEZEL", "BUTTON"}
        rig.am._resolve_modes()
        self.assertFalse(rig.am.motion.calibrated)
        self.assertIsNone(rig.am.P)
        rig.bezel("CW")
        self.assertEqual(rig.wheel(), [-1])
        rig.button("back", True)
        rig.button("back", False)
        self.assertEqual(rig.downs(), [("down", "left")])
        self.assertEqual(rig.ups(), [("up", "left")])
        self.assertEqual(rig.am.clicks, 1)
        self.assertIsNone(rig.events("click")[-1]["pos"])

    def test_yield_echo(self):
        def sweep(rig):
            rig.calibrate()
            rig.run(2.0, gyro=w(z=30))
            rig.run(2.0, gyro=w(z=-30))
            rig.run(0.5)
            return rig
        exact = sweep(Rig())
        self.assertEqual(exact.am.echo_late, 0)
        # (a) a read-back that lags one move never yields and never halves the gain
        laggy = sweep(Rig(pointer=LaggyPointer))
        self.assertEqual(laggy.am.pause_count["ratón físico"], 0, laggy.lines)
        self.assertGreater(laggy.am.echo_late, 0)
        self.assertLess(abs(laggy.am.travel - exact.am.travel), 0.1 * exact.am.travel)
        self.assertEqual(laggy.moves(), exact.moves())
        self.assertIn("eco tarde", laggy.am.status_line(laggy.now_ms() / 1000.0))
        # (b) 1-px jitter on every other read: adopted, never a pause, no extra moves at rest
        jit = sweep(Rig(pointer=JitterPointer))
        self.assertEqual(jit.am.pause_count["ratón físico"], 0)
        n = len(jit.moves())
        jit.run(2.0)
        self.assertEqual(len(jit.moves()), n)
        # (c) a real mouse: an 8-px jump yields at the very next look; 3 px once is nothing; 3 px held is a hand
        rig = Rig().calibrate()
        base = rig.pos
        rig.pointer.pos = (base[0] + 8, base[1])
        rig.idle_ticks(0.05)
        self.assertEqual(rig.am.status()["pausa"], "ratón físico")
        self.assertEqual(rig.events("yield")[-1]["como"], "salto")
        self.assertEqual(rig.events("yield")[-1]["desviacion_px"], 8)
        rig = Rig().calibrate()
        base = rig.pos
        rig.pointer.pos = (base[0] + 3, base[1])
        rig.idle_ticks(0.05)
        self.assertIsNone(rig.am.status()["pausa"])
        rig.pointer.pos = base
        rig.idle_ticks(0.05)
        rig.run(0.5)
        self.assertIsNone(rig.am.status()["pausa"])
        self.assertEqual(rig.am.pause_count["ratón físico"], 0)
        rig.pointer.pos = (base[0] + 3, base[1])
        rig.idle_ticks(0.15)
        self.assertEqual(rig.am.status()["pausa"], "ratón físico")
        self.assertEqual(rig.events("yield")[-1]["como"], "persistente")
        self.assertEqual([round(v) for v in rig.am.P], [base[0] + 3, base[1]])
        # (d) while the hand keeps moving the mouse the pause holds; it ends 1 s after the mouse stops
        for i in range(40):                              # (the 0.5 s watchdog adds 'sin datos' meanwhile)
            rig.pointer.pos = (base[0] + 10 + i, base[1])
            rig.idle_ticks(0.05)
        self.assertIn("ratón físico", rig.am.pause_reasons)
        rig.idle_ticks(0.9)
        self.assertIn("ratón físico", rig.am.pause_reasons)
        rig.idle_ticks(0.15)
        self.assertNotIn("ratón físico", rig.am.pause_reasons)
        self.assertEqual([round(v) for v in rig.am.P], [base[0] + 49, base[1]])
        rig.t += rig.lag                                 # the watch kept sampling: what arrives now is fresh
        rig.lag = 0.0
        rig.run(0.8, gyro=w(z=30))                       # 'sin datos' ends after 0.3 s of fresh data
        self.assertIsNone(rig.am.status()["pausa"])
        self.assertNotEqual(rig.pos, (base[0] + 49, base[1]))
        self.assertEqual(rig.am.pause_count["ratón físico"], 1)    # one yield (persistente), extended by the hand
        # (e) the cursor pinned by Windows while our targets go on: adopted, no pause, bounded rubber band
        rig = Rig(pointer=ClampPointer).calibrate()
        rig.run(1.5, gyro=w(z=-30))
        self.assertEqual(rig.pos[0], 1000)
        self.assertEqual(rig.am.pause_count["ratón físico"], 0)
        self.assertGreaterEqual(rig.am.stuck_adopts, 1)
        self.assertLess(rig.am.P[0], 1000 + 20)
        rig.run(0.3, gyro=w(z=30))
        self.assertLess(rig.pos[0], 1000)
        self.assertEqual(rig.am.pause_count["ratón físico"], 0)
        # (f) --no-yield: the jump is seen (last_cursor) but never pauses
        rig = Rig(no_yield=True).calibrate()
        base = rig.pos
        rig.pointer.pos = (base[0] + 8, base[1])
        rig.idle_ticks(0.1)
        self.assertIsNone(rig.am.status()["pausa"])
        self.assertEqual(rig.am.last_cursor, (base[0] + 8, base[1]))
        # (g) the cursor placed on a point of an EARLIER sweep after a rest: an old target is no echo (ECHO_S)
        rig = Rig().calibrate()
        rig.run(1.0, gyro=w(z=30))
        far = rig.pos
        rig.run(1.0, gyro=w(z=-30))
        rig.run(0.5)
        self.assertGreater(abs(far[0] - rig.pos[0]), 20)
        rig.pointer.pos = far
        rig.idle_ticks(0.05)
        self.assertEqual(rig.am.status()["pausa"], "ratón físico")
        self.assertEqual(rig.events("yield")[-1]["como"], "salto")
        # relative mode: the laggy read-back is just as harmless
        laggy = sweep(Rig(pointer=LaggyPointer, move="relative"))
        self.assertEqual(laggy.am.pause_count["ratón físico"], 0)
        self.assertLessEqual(math.dist(laggy.am.P, laggy.pos), 1.0)

    def test_params_validation(self):
        expected = {"gain", "gain_x", "gain_y", "accel", "g_lo", "g_hi", "v_lo", "v_hi", "mincutoff", "beta", "dcutoff",
                    "deadzone", "click", "scroll", "bezel_invert", "bezel_notches", "home_key", "tap_thr", "tap_width",
                    "tap_pre", "tap_post", "tap_post_ms", "dwell_time", "dwell_speed", "scroll_enter", "scroll_exit",
                    "scroll_deg_per_notch", "max_speed", "calib_p2p", "yield"}
        self.assertEqual(set(air_mouse.TUNABLES), expected)
        actions = {a.dest: a for a in air_mouse.build_parser()._actions}
        defaults = air_mouse.defaults_dict()
        for name, tn in air_mouse.TUNABLES.items():
            self.assertIn(tn.attr, actions, name)
            act = actions[tn.attr]
            if tn.kind == "choice":
                self.assertEqual(tuple(act.choices), tn.choices, name)
            else:
                self.assertIsNone(act.choices, name)
            d = act.default
            self.assertEqual(defaults[name], (not d) if name == "yield" else bool(d) if tn.kind == "bool" else d, name)
            if tn.kind in ("float", "int"):
                self.assertTrue(tn.lo <= defaults[name] <= tn.hi, name)
        self.assertEqual(defaults["click"], "auto")
        self.assertEqual(defaults["scroll"], "auto")
        self.assertEqual(defaults["yield"], True)
        self.assertEqual(json.loads(json.dumps(defaults)), defaults)
        rig = Rig().calibrate()
        v = air_mouse.validate_params
        for bad, text in (({"gain_y": 7}, "gain_y fuera de rango (0.2–3): 7"), ({"gain_y": "x"}, "gain_y: valor inválido"),
                          ({"foo": 1}, "foo desconocido"), ({"tap_width": 1.5}, "tap_width: valor inválido"),
                          ({"accel": 1}, "accel: valor inválido"), ({"gain": float("nan")}, "gain: valor inválido"),
                          ({"gain": float("inf")}, "gain: valor inválido"), ({"click": "nope"}, "click: valor inválido"),
                          ({"yield": "true"}, "yield: valor inválido"), ({"v_hi": 5}, "v_hi debe ser mayor que v_lo"),
                          ({"v_lo": 50, "v_hi": 40}, "v_hi debe ser mayor"), ({"scroll_exit": 30}, "scroll_exit debe ser menor"),
                          ({"gain_y": 1.4, "foo": 1}, "foo desconocido"), (None, "params debe ser un objeto")):
            clean, errors = v(bad, rig.cfg)
            self.assertEqual(clean, {}, bad)
            self.assertTrue(any(text in e for e in errors), (bad, errors))
        good = {"gain_y": 1.4, "mincutoff": 3.0, "yield": False, "accel": False, "click": "button", "tap_width": 8.0,
                "v_lo": 20, "v_hi": 200}
        clean, errors = v(good, rig.cfg)
        self.assertEqual(errors, [])
        self.assertEqual(clean["tap_width"], 8)
        self.assertIsInstance(clean["tap_width"], int)
        self.assertIsInstance(clean["v_lo"], float)
        changed = rig.am.apply_params(clean)
        self.assertEqual(set(changed), set(good))
        self.assertEqual(rig.cfg.gain_y, 1.4)
        self.assertEqual(rig.am.motion.fx.mincutoff, 3.0)
        self.assertEqual(rig.am.motion.fy.mincutoff, 3.0)
        self.assertTrue(rig.cfg.no_yield)
        self.assertEqual(rig.cfg.accel, 0)
        self.assertEqual(rig.am.click_mode, "button")
        self.assertIn("ajuste: gain_y 1.0 → 1.4", rig.lines)
        self.assertIn("ajuste: yield True → False", rig.lines)
        p = air_mouse.params_dict(rig.cfg)
        self.assertEqual(json.loads(json.dumps(p)), p)
        self.assertEqual(p["yield"], False)
        self.assertEqual(p["accel"], False)
        self.assertEqual(p["gain_y"], 1.4)
        self.assertEqual(rig.am.apply_params({"tap_post_ms": 80}), ["tap_post_ms"])
        self.assertEqual(rig.cfg.tap_post_ms, 80)

    def test_profile(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "airmouse.json")
            cfg = air_mouse.make_config(gain_y=1.5, click="button", no_yield=True, accel=0)
            self.assertEqual(air_mouse.save_profile(cfg, path), path)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["params"]["gain_y"], 1.5)
            self.assertEqual(data["params"]["yield"], False)
            cfg2 = air_mouse.make_config()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                n = air_mouse.load_profile_into(cfg2, path)
            self.assertEqual(n, len(air_mouse.TUNABLES))
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(cfg2.gain_y, 1.5)
            self.assertEqual(cfg2.click, "button")
            self.assertTrue(cfg2.no_yield)
            self.assertEqual(cfg2.accel, 0)
            self.assertEqual(air_mouse.params_dict(cfg2), air_mouse.params_dict(cfg))
            # only the typed flags are explicit; they win over the profile
            self.assertEqual(vars(air_mouse.build_parser(explicit_only=True).parse_args(["--gain", "2"])), {"gain": 2.0})
            self.assertEqual(vars(air_mouse.build_parser(explicit_only=True).parse_args(["--no-yield", "--gain-y", "1.1"])),
                             {"no_yield": True, "gain_y": 1.1})
            cfg3 = air_mouse.make_config(gain_y=1.1)
            air_mouse.load_profile_into(cfg3, path, {"gain_y", "no_yield"})
            self.assertEqual(cfg3.gain_y, 1.1)
            self.assertFalse(cfg3.no_yield)
            self.assertEqual(cfg3.click, "button")
            # unknown keys and bad values are skipped with a log line, the rest applies
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "params": {"foo": 1, "gain_y": 99, "accel": "yes", "gain_x": 1.3,
                                                     "v_lo": 150, "v_hi": 100}}, fh)
            cfg4 = air_mouse.make_config()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                n = air_mouse.load_profile_into(cfg4, path)
            self.assertEqual(n, 3)
            self.assertEqual(cfg4.gain_y, 1.0)
            self.assertEqual(cfg4.gain_x, 1.3)
            self.assertEqual((cfg4.v_lo, cfg4.v_hi), (10.0, 120.0))   # an incoherent pair goes back to the defaults
            self.assertIn("foo desconocido", out.getvalue())
            self.assertIn("gain_y fuera de rango", out.getvalue())
            self.assertIn("accel: valor inválido", out.getvalue())
            self.assertIn("incoherentes", out.getvalue())
            # corrupt and missing files
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{{{ no json")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertIsNone(air_mouse.load_profile_into(cfg4, path))
            self.assertIn("perfil ilegible: lo ignoro", out.getvalue())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertIsNone(air_mouse.load_profile_into(cfg4, os.path.join(d, "missing.json")))
            self.assertEqual(out.getvalue(), "")
        self.assertIsNone(air_mouse.resolve_profile("none"))
        self.assertIsNone(air_mouse.resolve_profile(""))
        self.assertTrue(os.path.isabs(air_mouse.resolve_profile("~/x.json")))
        self.assertNotIn("~", air_mouse.resolve_profile(air_mouse.PROFILE_DEFAULT))

    def test_record_gesture(self):
        rig = Rig().calibrate()
        rig.run(4.0, gyro=w(z=5))
        with tempfile.TemporaryDirectory() as d:
            path, n = rig.am.record_gesture("prueba", root=d)
            self.assertTrue(os.path.basename(path).startswith("prueba-"))
            self.assertTrue(path.endswith(".csv"))
            with open(path, newline="", encoding="utf-8") as fh:
                rows = list(csv.reader(fh))
            self.assertEqual(rows[0], ["source", "t_ms", "x", "y", "z"])
            self.assertEqual(len(rows) - 1, n)
            self.assertTrue(890 <= n <= 910, n)
            ts = [int(r[1]) for r in rows[1:]]
            self.assertLessEqual(ts[-1] - ts[0], 3000)
            self.assertEqual(ts, sorted(ts))
            self.assertEqual({r[0] for r in rows[1:]}, set(ALL))
            self.assertEqual(rig.events("gesture")[-1]["muestras"], n)
            path2, _ = rig.am.record_gesture("../x y", root=d)
            self.assertTrue(os.path.basename(path2).startswith("x-y-"), path2)
            self.assertEqual(os.path.dirname(path2), d)
            path3, _ = rig.am.record_gesture("", root=d)
            self.assertTrue(os.path.basename(path3).startswith("gesto-"))
            listing = air_mouse.list_gestures(d)
            self.assertEqual(listing["type"], "gestures")
            self.assertEqual({f["name"] for f in listing["files"]},
                             {os.path.basename(p) for p in (path, path2, path3)})
            self.assertTrue(all(f["bytes"] > 0 and isinstance(f["t"], int) for f in listing["files"]))
            self.assertEqual(listing["files"], sorted(listing["files"], key=lambda f: f["t"], reverse=True))
            self.assertEqual(air_mouse.list_gestures(os.path.join(d, "nope"))["files"], [])

    def test_control_server_roundtrip(self):
        from websockets.asyncio.client import connect
        rig = Rig().calibrate()
        tc = self

        async def until(ws, kind, pred=lambda m: True):
            for _ in range(300):
                m = json.loads(await asyncio.wait_for(ws.recv(), 1.0))
                if m.get("type") == kind and pred(m):
                    return m
            tc.fail(f"sin mensaje {kind}")

        async def go(profile):
            srv = air_mouse.ControlServer(rig.am, 0, profile)
            task = asyncio.create_task(srv.run())
            await asyncio.wait_for(srv.ready.wait(), 2.0)
            try:
                async with connect(f"ws://127.0.0.1:{srv.bound_port}", open_timeout=2) as ws:
                    p = await until(ws, "params")
                    tc.assertEqual(p["params"]["gain_y"], 1.0)
                    tc.assertEqual(p["defaults"], air_mouse.defaults_dict())
                    tc.assertEqual(p["profile"], profile)
                    tc.assertEqual(p["efectivo"], {"click": "tap", "scroll": "roll"})
                    await ws.send(json.dumps({"type": "set", "params": {"gain_y": 1.4, "click": "button"}}))
                    p = await until(ws, "params")
                    tc.assertEqual(p["params"]["gain_y"], 1.4)
                    tc.assertEqual(p["efectivo"]["click"], "button")
                    tc.assertEqual(rig.cfg.gain_y, 1.4)
                    await ws.send(json.dumps({"type": "set", "params": {"gain_y": 7, "gain": 1.2}}))
                    e = await until(ws, "error")
                    tc.assertIn("gain_y fuera de rango", e["detail"])
                    tc.assertEqual(rig.cfg.gain_y, 1.4)
                    tc.assertEqual(rig.cfg.gain, 1.0)                 # atomic: nothing of a bad set applies
                    await ws.send(json.dumps({"type": "cmd", "name": "pause"}))
                    await until(ws, "ack", lambda m: m["name"] == "pause")
                    st = await until(ws, "state", lambda m: m["pausa"] == "usuario")
                    tc.assertEqual(st["estado"], "pausa")
                    await ws.send(json.dumps({"type": "cmd", "name": "resume"}))
                    await until(ws, "ack", lambda m: m["name"] == "resume")
                    await until(ws, "state", lambda m: m["pausa"] is None)
                    await ws.send(json.dumps({"type": "cmd", "name": "save_profile"}))
                    a = await until(ws, "ack", lambda m: m["name"] == "save_profile")
                    tc.assertEqual(a["detail"], profile)
                    tc.assertTrue(os.path.exists(profile))
                    with open(profile, encoding="utf-8") as fh:
                        tc.assertEqual(json.load(fh)["params"]["gain_y"], 1.4)
                    await ws.send(json.dumps({"type": "cmd", "name": "reset_defaults"}))
                    await until(ws, "ack", lambda m: m["name"] == "reset_defaults")
                    p = await until(ws, "params", lambda m: m["params"]["gain_y"] == 1.0)
                    tc.assertEqual(rig.cfg.click, "auto")
                    await ws.send(json.dumps({"type": "cmd", "name": "load_profile"}))
                    await until(ws, "ack", lambda m: m["name"] == "load_profile")
                    await until(ws, "params", lambda m: m["params"]["gain_y"] == 1.4)
                    tc.assertEqual(rig.cfg.click, "button")
                    await ws.send(json.dumps({"type": "cmd", "name": "recalibrate"}))
                    await until(ws, "ack", lambda m: m["name"] == "recalibrate")
                    tc.assertFalse(rig.am.motion.calibrated)
                    await until(ws, "state", lambda m: m["estado"] == "calibrando")
                    await ws.send(json.dumps({"type": "get"}))
                    await until(ws, "params")
                    await ws.send("{not json")
                    e = await until(ws, "error")
                    tc.assertIn("JSON", e["detail"])
                    await ws.send(json.dumps({"type": "bogus"}))
                    e = await until(ws, "error")
                    tc.assertEqual(e["detail"], "tipo desconocido: bogus")
                    await ws.send(json.dumps({"type": "cmd", "name": "nada"}))
                    e = await until(ws, "error")
                    tc.assertIn("comando desconocido", e["detail"])
                    await ws.send(json.dumps({"type": "cmd", "name": "list_gestures"}))
                    g = await until(ws, "gestures")
                    tc.assertIsInstance(g["files"], list)
                    rig.am.event("click", how="button", pos=[1, 2], held_ms=120)
                    ev = await until(ws, "event", lambda m: m["kind"] == "click")
                    tc.assertEqual(ev["detail"], {"how": "button", "pos": [1, 2], "held_ms": 120})
                    tc.assertIsInstance(ev["t"], int)
                for _ in range(50):                               # the handler sees the close a moment later
                    if not srv.clients:
                        break
                    await asyncio.sleep(0.02)
                tc.assertEqual(srv.clients, set())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            # the port is busy: a second server logs it and gives up, nothing raises
            srv2 = air_mouse.ControlServer(rig.am, srv.bound_port, profile)
            srv3 = air_mouse.ControlServer(rig.am, srv.bound_port, profile)
            t2 = asyncio.create_task(srv2.run())
            await asyncio.wait_for(srv2.ready.wait(), 2.0)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                await asyncio.wait_for(srv3.run(), 2.0)
            tc.assertIn(f"puerto {srv.bound_port} ocupado, desactivado", out.getvalue())
            t2.cancel()
            await asyncio.gather(t2, return_exceptions=True)

        with tempfile.TemporaryDirectory() as d:
            t0 = time.monotonic()
            with contextlib.redirect_stdout(io.StringIO()):
                asyncio.run(asyncio.wait_for(go(os.path.join(d, "airmouse.json")), 15.0))
            self.assertLess(time.monotonic() - t0, 5.0)

    def test_state_message_shape(self):
        rig = Rig().calibrate()
        rig.run(1.0, gyro=w(z=10))
        m = rig.am.state_message()
        self.assertEqual(json.loads(json.dumps(m)), m)
        self.assertEqual(set(m), {"type", "t", "estado", "pausa", "rates", "delta", "cursor", "bias", "retraso_ms", "hz",
                                  "clics", "rueda", "entradas", "efectivo", "boton", "calibrado", "eco_tarde",
                                  "descartadas", "tap"})
        self.assertEqual(m["type"], "state")
        self.assertIsInstance(m["t"], int)
        self.assertEqual(m["estado"], "activo")
        self.assertIsNone(m["pausa"])
        self.assertEqual(set(m["rates"]), {"yaw", "pitch", "roll", "yaw_f", "pitch_f"})
        self.assertTrue(all(isinstance(v, float) for v in m["rates"].values()))
        self.assertGreater(m["rates"]["yaw"], 5)                   # +10 °/s about the vertical (moves left)
        self.assertEqual(set(m["delta"]), {"dx", "dy"})
        self.assertLess(m["delta"]["dx"], -20)
        self.assertTrue(isinstance(m["cursor"], list) and len(m["cursor"]) == 2, m["cursor"])
        self.assertLessEqual(abs(m["cursor"][0] - rig.pos[0]), 10)    # the last READ, one flush behind the move
        self.assertEqual(len(m["bias"]), 3)
        self.assertIsInstance(m["retraso_ms"], (int, float))
        self.assertEqual(set(m["hz"]), {"GYR", "ACC", "GRV"})
        self.assertTrue(all(90 <= v <= 110 for v in m["hz"].values()), m["hz"])
        self.assertEqual((m["clics"], m["rueda"]), (0, 0))
        self.assertEqual(m["entradas"], {"bezel": False, "button": False})
        self.assertEqual(m["efectivo"], {"click": "tap", "scroll": "roll"})
        self.assertEqual(m["boton"], {"held": None, "ms": 0})
        self.assertTrue(m["calibrado"])
        self.assertEqual((m["eco_tarde"], m["descartadas"]), (0, 0))
        self.assertEqual(m["tap"], {"candidatos": 0, "confirmados": 0})
        m2 = rig.am.state_message()
        self.assertEqual(m2["delta"], {"dx": 0.0, "dy": 0.0})      # the delta is per state message
        rig.run(0.5)
        self.assertEqual(rig.am.state_message()["cursor"], list(rig.pos))   # at rest the last read is the cursor
        rig.am._pause("usuario")
        m3 = rig.am.state_message()
        self.assertEqual((m3["estado"], m3["pausa"]), ("pausa", "usuario"))
        # events are JSON-safe even with infinite gate values
        rig.am.event("tap_rejected", verdict="forma", pre_max=float("inf"), peak=1.23456)
        ev = rig.am.event_queue[-1]
        self.assertEqual(json.loads(json.dumps(ev))["detail"], {"verdict": "forma", "pre_max": None, "peak": 1.235})
        self.assertIsNotNone(rig.am.event_queue.maxlen)


if __name__ == "__main__":
    unittest.main(verbosity=2)
