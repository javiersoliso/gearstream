"""Unit tests for tools/sdb_bridge.py: the /dev/input decoder, the BEZEL/BUTTON mapping and the
bridge's hello/status/data messages, against a fake sdb connection. No watch, no sockets.

    python -I tools/test_sdb_bridge.py
"""
import asyncio
import contextlib
import io
import json
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script dir from sys.path
import sdb_bridge  # noqa: E402
from sdb_bridge import (EV_ABS, EV_KEY, EV_REL, EV_SYN, INPUT_EVENT, KEY_BACK, KEY_POWER, READY,  # noqa: E402
                        REL_WHEEL, Bridge, decode_input_events, input_sample, parse_inputs,
                        resolve_input_nodes)

BEZEL_CMD = "stty raw -echo; echo READY; cat /dev/input/event14"


def ev(etype, code, value, sec=1700000000, usec=123456):
    """One packed input_event as the watch's kernel writes it."""
    return INPUT_EVENT.pack(sec, usec, etype, code, value)


SYN = ev(EV_SYN, 0, 0)


class FakeStream:
    """What SdbConnection.shell() returns: a queue of raw byte chunks, None when the watch closes it."""

    def __init__(self, chunks=(), close=True):
        self.queue = asyncio.Queue()
        for chunk in chunks:
            self.queue.put_nowait(chunk)
        if close:
            self.queue.put_nowait(None)


class FakeConn:
    model = "SM-R800"

    def __init__(self, streams=None, listing=""):
        self.streams = streams or {}   # substring of the command -> FakeStream
        self.listing = listing         # what run() answers (an Exception instance raises)
        self.commands = []

    async def shell(self, cmd):
        self.commands.append(cmd)
        for key, stream in self.streams.items():
            if key in cmd:
                return stream
        return FakeStream()

    async def run(self, cmd):
        self.commands.append(cmd)
        if isinstance(self.listing, Exception):
            raise self.listing
        return self.listing

    def stats(self):
        return None

    def close(self):
        pass


class FakeWs:
    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(json.loads(text))


class FakeConnect:
    """Stands in for websockets' connect(): an async context manager yielding a FakeWs."""
    last = None

    def __init__(self, url, **kwargs):
        self.url = url
        self.ws = FakeWs()
        FakeConnect.last = self

    async def __aenter__(self):
        return self.ws

    async def __aexit__(self, *exc):
        return False


def bridge(conn, **kw):
    return Bridge(conn, interval=10, flush_ms=20, sensors=[], **kw)


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def states(b, source):
    return [(m["state"], m["detail"]) for m in b.pending_status if m["source"] == source]


class SdbBridgeTests(unittest.TestCase):

    def test_struct_layout(self):
        self.assertEqual(INPUT_EVENT.size, 16)
        packed = INPUT_EVENT.pack(1, 500000, 2, 8, -2)
        self.assertEqual(len(packed), 16)
        self.assertEqual(INPUT_EVENT.unpack(packed), (1, 500000, 2, 8, -2))
        self.assertLess(INPUT_EVENT.unpack(packed)[4], 0)
        # 0x0a bytes are ordinary data in every field: nothing is line-oriented here.
        lf = INPUT_EVENT.pack(0x0A0A0A0A, 10, EV_REL, REL_WHEEL, 10)
        self.assertEqual(lf.count(b"\n"), 6)
        self.assertEqual(INPUT_EVENT.unpack(lf), (0x0A0A0A0A, 10, EV_REL, REL_WHEEL, 10))
        self.assertEqual(decode_input_events(lf), ([(0x0A0A0A0A, 10, EV_REL, REL_WHEEL, 10)], b""))

    def test_decode_split_chunks(self):
        events = [(1, 1, EV_REL, REL_WHEEL, 1), (0x0A0A0A0A, 10, EV_REL, 0, 10), (2, 2, EV_KEY, KEY_BACK, 1)]
        data = b"".join(INPUT_EVENT.pack(*e) for e in events)
        self.assertEqual(len(data), 48)
        out, rest, pos = [], b"", 0
        for size in (1, 7, 16, 3, 21):
            rest += data[pos:pos + size]
            pos += size
            got, rest = decode_input_events(rest)
            out += got
            self.assertLess(len(rest), 16)
        self.assertEqual(pos, 48)
        self.assertEqual(out, events)
        self.assertEqual(rest, b"")
        # A partial record stays in the leftover untouched.
        got, rest = decode_input_events(data[:20])
        self.assertEqual((got, rest), ([events[0]], data[16:20]))

    def test_bezel_mapping(self):
        self.assertEqual(input_sample("bezel", EV_REL, REL_WHEEL, 1, "cw"),
                         ("BEZEL", {"direction": "CW", "steps": 1, "raw": 1}))
        self.assertEqual(input_sample("bezel", EV_REL, REL_WHEEL, -2, "cw"),
                         ("BEZEL", {"direction": "CCW", "steps": 2, "raw": -2}))
        self.assertEqual(input_sample("bezel", EV_REL, REL_WHEEL, 1, "ccw")[1]["direction"], "CCW")
        self.assertEqual(input_sample("bezel", EV_REL, REL_WHEEL, -2, "ccw")[1],
                         {"direction": "CW", "steps": 2, "raw": -2})
        self.assertEqual(input_sample("bezel", EV_REL, REL_WHEEL, 3, "cw")[1]["steps"], 3)   # not clamped
        self.assertIsNone(input_sample("bezel", EV_REL, 0, 37, "cw"))          # position number
        self.assertIsNone(input_sample("bezel", EV_SYN, 0, 0, "cw"))
        self.assertIsNone(input_sample("bezel", EV_ABS, 0, 120, "cw"))
        self.assertIsNone(input_sample("bezel", EV_KEY, KEY_BACK, 1, "cw"))    # another device's event
        self.assertIsNone(input_sample("bezel", EV_REL, REL_WHEEL, 0, "cw"))

    def test_button_mapping(self):
        self.assertEqual(input_sample("back", EV_KEY, KEY_BACK, 1), ("BUTTON", {"key": "back", "pressed": True}))
        self.assertEqual(input_sample("back", EV_KEY, KEY_BACK, 0), ("BUTTON", {"key": "back", "pressed": False}))
        self.assertEqual(input_sample("home", EV_KEY, KEY_POWER, 1), ("BUTTON", {"key": "home", "pressed": True}))
        self.assertEqual(input_sample("home", EV_KEY, KEY_POWER, 0)[1]["pressed"], False)
        self.assertIsNone(input_sample("back", EV_KEY, KEY_BACK, 2))         # autorepeat
        self.assertIsNone(input_sample("home", EV_KEY, KEY_BACK, 1))         # kind-specific code
        self.assertIsNone(input_sample("back", EV_KEY, KEY_POWER, 1))
        self.assertIsNone(input_sample("back", EV_SYN, 0, 0))
        self.assertIsNone(input_sample("back", EV_REL, REL_WHEEL, 1))

    def test_reader_pushes_samples(self):
        data = READY + SYN + ev(EV_REL, REL_WHEEL, 1) + ev(EV_REL, 0, 37) + SYN + ev(EV_KEY, KEY_BACK, 1) + SYN
        conn = FakeConn({"event14": FakeStream([data]), "event12": FakeStream([data])})
        b = bridge(conn, inputs=("bezel", "back"))
        with quiet():
            asyncio.run(b.read_input("bezel"))
            asyncio.run(b.read_input("back"))
        self.assertEqual(conn.commands, [BEZEL_CMD, "stty raw -echo; echo READY; cat /dev/input/event12"])
        self.assertEqual(len(b.buffer), 2)
        (s1, t1, v1), (s2, t2, v2) = b.buffer
        self.assertEqual((s1, v1), ("BEZEL", {"direction": "CW", "steps": 1, "raw": 1}))
        self.assertEqual((s2, v2), ("BUTTON", {"key": "back", "pressed": True}))
        for t in (t1, t2):
            self.assertIsInstance(t, int)
            self.assertLess(abs(t - time.time() * 1000), 1000)
        self.assertEqual(b.latest_ms, 0)                      # inputs do not feed the latency report
        self.assertEqual(b.counts, {"BEZEL": 1, "BUTTON": 1})
        self.assertEqual(states(b, "BEZEL")[0], ("on", "/dev/input/event14 (tizen_detent)"))
        self.assertEqual(states(b, "BUTTON")[0], ("on", "atrás /dev/input/event12 (gpio_keys)"))
        # The fake closes both streams afterwards: that is reported, since the bridge is not closing.
        self.assertEqual(states(b, "BEZEL")[-1][0], "error")
        self.assertIn("lectura terminada", states(b, "BEZEL")[-1][1])

    def test_reader_split_across_chunks_with_newlines(self):
        # 0x0a inside the events and chunk boundaries everywhere, including inside READY itself.
        tail = ev(EV_REL, REL_WHEEL, -1, sec=0x0A0A0A0A, usec=10) + SYN + ev(EV_REL, REL_WHEEL, 2, usec=0x0A)
        data = b"READ" + b"Y" + b"\n" + tail
        chunks = [data[i:i + 5] for i in range(0, len(data), 5)]
        conn = FakeConn({"event14": FakeStream(chunks)})
        b = bridge(conn, inputs=("bezel",))
        with quiet():
            asyncio.run(b.read_input("bezel"))
        self.assertEqual([(s, v) for s, _, v in b.buffer],
                         [("BEZEL", {"direction": "CCW", "steps": 1, "raw": -1}),
                          ("BEZEL", {"direction": "CW", "steps": 2, "raw": 2})])
        self.assertEqual(states(b, "BEZEL")[0][0], "on")

    def test_reader_noise_before_ready(self):
        data = b"stty: standard input: Inappropriate ioctl\r\n" + READY + ev(EV_KEY, KEY_BACK, 1) + SYN
        conn = FakeConn({"event12": FakeStream([data])})
        b = bridge(conn, inputs=("back",))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            asyncio.run(b.read_input("back"))
        self.assertEqual([(s, v) for s, _, v in b.buffer], [("BUTTON", {"key": "back", "pressed": True})])
        self.assertEqual(states(b, "BUTTON")[0][0], "on")
        self.assertIn("aviso en /dev/input/event12: stty: standard input: Inappropriate ioctl", out.getvalue())

    def test_reader_error_status(self):
        def run_reader(chunks, close=True, inputs=("bezel",), kind="bezel"):
            conn = FakeConn({"event": FakeStream(chunks, close=close)})
            b = bridge(conn, inputs=inputs)
            with quiet():
                asyncio.run(b.read_input(kind))
            self.assertEqual(b.buffer, [])
            return states(b, sdb_bridge.INPUT_DEVICES[kind][2])

        # (a) cat fails before any marker (or the whole line arrives after it: same message)
        st = run_reader([b"cat: can't open '/dev/input/event14': Permission denied\r\n"])
        self.assertEqual(st[-1][0], "error")
        self.assertIn("no se pudo leer /dev/input/event14", st[-1][1])
        self.assertIn("Permission denied", st[-1][1])
        st = run_reader([READY + b"cat: can't open '/dev/input/event14': Permission denied\n"])
        self.assertEqual([s for s, _ in st], ["on", "error"])
        self.assertIn("no se pudo leer /dev/input/event14: cat: can't open", st[-1][1])
        # (b) text where events should be: stty raw did not take
        st = run_reader([READY + b"garbage text that is not events...."])
        self.assertEqual(st[-1][0], "error")
        self.assertIn("datos no reconocidos en /dev/input/event14", st[-1][1])
        # (c) nothing at all, then closed
        st = run_reader([])
        self.assertEqual(st, [("error", "no se pudo leer /dev/input/event14: el reloj cerró sin responder")])
        # (d) never answers: the reader gives up after INPUT_READY_S
        with mock.patch.object(sdb_bridge, "INPUT_READY_S", 0.05):
            st = run_reader([b"..."], close=False)
        self.assertEqual(st[-1][0], "error")
        self.assertIn("sin respuesta de /dev/input/event14", st[-1][1])
        # (e) one BUTTON node failing keeps BUTTON on, with the failure in the detail
        conn = FakeConn({"event12": FakeStream([READY + ev(EV_KEY, KEY_BACK, 1)], close=False),
                         "event0": FakeStream([b"cat: can't open '/dev/input/event0': Permission denied\n"])})
        b = bridge(conn, inputs=("back", "home"))

        async def both():
            task = asyncio.create_task(b.read_input("back"))
            await b.read_input("home")
            await asyncio.sleep(0.02)
            task.cancel()
        with quiet():
            asyncio.run(both())
        self.assertEqual(states(b, "BUTTON")[-1][0], "on")
        self.assertIn("atrás /dev/input/event12 (gpio_keys)", states(b, "BUTTON")[-1][1])
        self.assertIn("inicio: no se pudo leer /dev/input/event0", states(b, "BUTTON")[-1][1])
        self.assertEqual([(s, v) for s, _, v in b.buffer], [("BUTTON", {"key": "back", "pressed": True})])

    def test_hello_and_status_lists_inputs(self):
        b = bridge(FakeConn(), inputs=("bezel", "back", "home"))
        hello = b.hello_message()
        self.assertEqual(hello["available"], ["HRM", "BEZEL", "BUTTON"])
        self.assertEqual(hello["app"], "sdb-bridge 1.2")
        status = {m["source"]: m for m in b.status_messages()}
        self.assertEqual(status["BEZEL"]["state"], "waiting")
        self.assertEqual(status["BEZEL"]["detail"], "/dev/input/event14 (tizen_detent)")
        self.assertEqual(status["BUTTON"]["state"], "waiting")
        self.assertEqual(status["BUTTON"]["detail"],
                         "atrás /dev/input/event12 (gpio_keys) · inicio /dev/input/event0 (power-keys)")
        b.input_names["home"] = "s2mpw02-power-keys"         # as the /sys listing reports it
        self.assertIn("inicio /dev/input/event0 (s2mpw02-power-keys)", b.input_status_message("BUTTON")["detail"])

        b = bridge(FakeConn(), inputs=("back",))
        self.assertEqual(b.hello_message()["available"], ["HRM", "BUTTON"])
        sources = [m["source"] for m in b.status_messages()]
        self.assertIn("BUTTON", sources)
        self.assertNotIn("BEZEL", sources)
        self.assertEqual({m["source"]: m for m in b.status_messages()}["BUTTON"]["detail"],
                         "atrás /dev/input/event12 (gpio_keys)")

        b = Bridge(FakeConn(), interval=10, flush_ms=20, sensors=["gyroscope", "accelerometer"])
        hello = b.hello_message()
        self.assertEqual(set(hello), {"type", "app", "t", "available", "device"})     # 1.1's shape
        self.assertEqual(hello["available"], ["GYROSCOPE", "ACCELERATION", "HRM"])
        self.assertEqual(hello["device"], {"model_name": "SM-R800", "transport": "sdb/sensorctl"})
        self.assertIsInstance(hello["t"], int)
        sources = [m["source"] for m in b.status_messages()]
        self.assertEqual(sources, ["GYROSCOPE", "ACCELERATION", "HRM"] + list(sdb_bridge.UNAVAILABLE))
        self.assertEqual(b.status_messages()[0]["detail"], "sensorctl 10 ms")

    def test_resolve_nodes(self):
        listing = ("/sys/class/input/event0 hrm_sensor\n"
                   "/sys/class/input/event3 tizen_detent\r\n"
                   "/sys/class/input/event5 gpio_keys\n"
                   "/sys/class/input/event7 s2mpw02-power-keys\n"
                   "/sys/class/input/event13 sec_touchscreen\n")
        names = {}
        self.assertEqual(resolve_input_nodes(listing, names),
                         {"bezel": "/dev/input/event3", "back": "/dev/input/event5", "home": "/dev/input/event7"})
        self.assertEqual(names, {"bezel": "tizen_detent", "back": "gpio_keys", "home": "s2mpw02-power-keys"})
        without_power = "\n".join(line for line in listing.splitlines() if "power" not in line)
        self.assertEqual(resolve_input_nodes(without_power)["home"], "/dev/input/event0")
        defaults = {"bezel": "/dev/input/event14", "back": "/dev/input/event12", "home": "/dev/input/event0"}
        self.assertEqual(resolve_input_nodes(""), defaults)
        self.assertEqual(resolve_input_nodes("/sys/class/input/event* \n"), defaults)   # unmatched glob
        # First match wins when a name repeats.
        self.assertEqual(resolve_input_nodes("/sys/class/input/event2 gpio_keys\n/sys/class/input/event9 gpio_keys")["back"],
                         "/dev/input/event2")

        async def resolve(listing):
            b = bridge(FakeConn(listing=listing), inputs=("bezel",))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                await b.resolve_nodes()
            return b, out.getvalue()
        b, out = asyncio.run(resolve(listing))
        self.assertEqual(b.input_node("bezel"), "/dev/input/event3")
        self.assertEqual(b.input_names["home"], "s2mpw02-power-keys")
        self.assertEqual(out, "")
        self.assertEqual(b.conn.commands, [sdb_bridge.INPUT_LIST_CMD])
        b, out = asyncio.run(resolve(ConnectionError("rechazado")))
        self.assertEqual(b.input_node("bezel"), "/dev/input/event14")
        self.assertIn("no pude listar /sys/class/input: uso los nodos medidos", out)
        b, out = asyncio.run(resolve(""))
        self.assertEqual(b.input_node("back"), "/dev/input/event12")
        self.assertIn("uso los nodos medidos", out)

    def test_inputs_flag(self):
        self.assertEqual(parse_inputs("none"), ())
        self.assertEqual(parse_inputs("bezel, back"), ("bezel", "back"))
        self.assertEqual(parse_inputs("bezel,back,home"), ("bezel", "back", "home"))
        self.assertEqual(parse_inputs("home,home"), ("home",))
        with self.assertRaises(ValueError) as cm:
            parse_inputs("foo")
        self.assertIn("entradas desconocidas: foo", str(cm.exception))
        with self.assertRaises(ValueError):
            parse_inputs("bezel,none")

    def test_batch_message_shape(self):
        b = bridge(FakeConn())
        self.assertIsNone(b.data_message())
        b.push("GYROSCOPE", 1234, {"x": 0.1, "y": 0.2, "z": 0.3})
        b.push("BEZEL", 5000, {"direction": "CW", "steps": 1, "raw": 1}, latency=False)
        b.push("BUTTON", 5001, {"key": "back", "pressed": True}, latency=False)
        b.push("GYROSCOPE", 1244, {"x": 0.1, "y": 0.2, "z": 0.3})
        msg = b.data_message()
        self.assertEqual(set(msg), {"type", "t", "samples"})
        self.assertEqual(msg["type"], "data")
        self.assertIsInstance(msg["t"], int)
        self.assertLess(abs(msg["t"] - time.time() * 1000), 1000)
        self.assertEqual(msg["samples"], [
            ["GYROSCOPE", 1234, {"x": 0.1, "y": 0.2, "z": 0.3}],
            ["BEZEL", 5000, {"direction": "CW", "steps": 1, "raw": 1}],
            ["BUTTON", 5001, {"key": "back", "pressed": True}],
            ["GYROSCOPE", 1244, {"x": 0.1, "y": 0.2, "z": 0.3}],
        ])
        json.dumps(msg)
        self.assertEqual(b.latest_ms, 1244)                   # the inputs' larger stamps did not move it
        self.assertIsNone(b.data_message())
        self.assertEqual(b.counts, {"GYROSCOPE": 2, "BEZEL": 1, "BUTTON": 1})

    def test_run_sends_hello_status_and_data(self):
        conn = FakeConn({"event5": FakeStream([READY + ev(EV_REL, REL_WHEEL, -1)], close=False),
                         "event12": FakeStream([READY + ev(EV_KEY, KEY_BACK, 1), ev(EV_KEY, KEY_BACK, 0)], close=False),
                         "dlogutil": FakeStream()},
                        listing="/sys/class/input/event5 tizen_detent\n/sys/class/input/event12 gpio_keys\n")
        b = bridge(conn, inputs=("bezel", "back"), bezel_positive="ccw")
        with mock.patch.object(sdb_bridge, "connect", FakeConnect), quiet():
            asyncio.run(b.run("ws://test/watch"))
        self.assertTrue(b.closing)
        self.assertEqual(FakeConnect.last.url, "ws://test/watch")
        self.assertEqual(conn.commands[0], sdb_bridge.INPUT_LIST_CMD)
        self.assertIn("stty raw -echo; echo READY; cat /dev/input/event5", conn.commands)
        sent = FakeConnect.last.ws.sent
        self.assertEqual(sent[0]["type"], "hello")
        self.assertEqual(sent[0]["available"], ["HRM", "BEZEL", "BUTTON"])
        bezel = [m for m in sent if m["type"] == "status" and m["source"] == "BEZEL"]
        self.assertEqual([(m["state"], m["detail"]) for m in bezel],
                         [("waiting", "/dev/input/event5 (tizen_detent)"), ("on", "/dev/input/event5 (tizen_detent)")])
        button = [m for m in sent if m["type"] == "status" and m["source"] == "BUTTON"]
        self.assertEqual([m["state"] for m in button], ["waiting", "on"])
        data = [m for m in sent if m["type"] == "data"]
        self.assertEqual(len(data), 1)
        self.assertEqual([(s, v) for s, _, v in data[0]["samples"]], [
            ("BEZEL", {"direction": "CW", "steps": 1, "raw": -1}),       # --bezel-positive ccw
            ("BUTTON", {"key": "back", "pressed": True}),
            ("BUTTON", {"key": "back", "pressed": False}),
        ])
        # Statuses go out before the data of the same flush, and nothing after the hello precedes them.
        kinds = [m["type"] for m in sent]
        self.assertEqual(kinds[0], "hello")
        self.assertLess(kinds.index("data"), len(kinds))
        self.assertTrue(all(k == "status" for k in kinds[1:kinds.index("data")]))

    def test_run_without_inputs_is_1_1(self):
        conn = FakeConn({"dlogutil": FakeStream()})
        b = bridge(conn)
        with mock.patch.object(sdb_bridge, "connect", FakeConnect), quiet():
            asyncio.run(b.run("ws://test/watch"))
        self.assertEqual(conn.commands, ["dlogutil SHealthServiceCommon"])     # no /sys listing, no cat
        sent = FakeConnect.last.ws.sent
        self.assertEqual(sent[0]["available"], ["HRM"])
        self.assertEqual([m["source"] for m in sent[1:]], ["HRM"] + list(sdb_bridge.UNAVAILABLE))


class ConnectRetryTests(unittest.TestCase):
    """The watch accepting the TCP connection and closing it before answering must not kill the bridge."""

    def test_watch_closing_mid_handshake_is_retryable_and_closes_the_socket(self):
        import sdb_client

        async def scenario():
            async def slam(reader, writer):        # a watch that reads our CNXN and hangs up without a word
                await reader.read(64)
                writer.close()
            server = await asyncio.start_server(slam, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            conn = sdb_client.SdbConnection("127.0.0.1", port)
            with mock.patch.object(sdb_client, "load_or_create_key", lambda: None):
                with self.assertRaises(sdb_bridge.RETRYABLE) as caught:
                    await conn.connect(timeout=5)
            server.close()
            await server.wait_closed()
            return caught.exception, conn.writer.is_closing()

        err, closed = asyncio.run(scenario())
        self.assertIsInstance(err, EOFError)       # IncompleteReadError: what crashed the .exe before
        self.assertTrue(closed)

    def test_connect_watch_retries_and_explains_after_three_hang_ups(self):
        attempts = []

        class Flaky:
            def __init__(self, host, port):
                pass

            async def connect(self, timeout):
                attempts.append(timeout)
                if len(attempts) <= 3:
                    raise asyncio.IncompleteReadError(b"", 24)
                return "conectado"

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            got = asyncio.run(sdb_bridge.connect_watch("10.0.0.2", 26101, connection=Flaky, wait=0))
        self.assertEqual(got, "conectado")
        self.assertEqual(len(attempts), 4)
        self.assertEqual(out.getvalue().count("cierra la conexión sin contestar"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
