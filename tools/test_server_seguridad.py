"""Quién puede hablar con el servidor (server/server.py): las páginas de esta laptop y los programas sí; una
página de otro sitio abierta en tu navegador, o una que se hace pasar por localhost (DNS rebinding), no.
Levanta el servidor de verdad en un puerto libre, solo en esta laptop y sin grabar.

    python -I tools/test_server_seguridad.py
"""
import asyncio
import http.client
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import server  # noqa: E402
from websockets.asyncio.client import connect  # noqa: E402
from websockets.exceptions import InvalidStatus  # noqa: E402


class Req:
    def __init__(self, **headers):
        self.headers = headers


class RefuseTests(unittest.TestCase):
    def test_rules(self):
        self.assertIsNone(server.refuse(Req(Host="localhost:8765")))                       # un programa: sin Origin
        self.assertIsNone(server.refuse(Req(Host="127.0.0.1:8765", Origin="http://localhost:8765")))
        self.assertIsNone(server.refuse(Req(Host="[::1]:8765", Origin="http://[::1]:8765")))
        self.assertIn("Origin", server.refuse(Req(Host="localhost:8765", Origin="https://otro-sitio.example")))
        self.assertIn("Origin", server.refuse(Req(Host="localhost:8765", Origin="null")))     # una página abierta desde un archivo
        self.assertIn("Host", server.refuse(Req(Host="otro-sitio.example:8765", Origin="http://otro-sitio.example:8765")))
        self.assertIn("Host", server.refuse(Req()))


class LiveServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        cls.tmp = tempfile.mkdtemp(prefix="gearstream-seguridad-")
        cls.proc = subprocess.Popen([sys.executable, "-I", os.path.join(ROOT, "server", "server.py"), "--host", "127.0.0.1",
                                     "--port", str(cls.port), "--out", cls.tmp, "--no-record"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", cls.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.out = cls.proc.communicate(timeout=10)[0]

    def get(self, host):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("GET", "/", headers={"Host": host})
        status = c.getresponse().status
        c.close()
        return status

    def ws(self, origin):
        async def go():
            async with connect(f"ws://127.0.0.1:{self.port}/ui", origin=origin, open_timeout=5):
                return "abierto"
        try:
            return asyncio.run(go())
        except InvalidStatus as e:
            return e.response.status_code

    def test_pages_from_this_laptop(self):
        self.assertEqual(self.get(f"localhost:{self.port}"), 200)
        self.assertEqual(self.ws(f"http://localhost:{self.port}"), "abierto")

    def test_programs_without_origin(self):
        self.assertEqual(self.ws(None), "abierto")

    def test_page_from_another_site(self):
        self.assertEqual(self.ws("https://otro-sitio.example"), 403)

    def test_dns_rebinding(self):
        self.assertEqual(self.get(f"otro-sitio.example:{self.port}"), 403)

    def test_only_this_laptop(self):
        lan = [ip for ip in server.lan_ips()]
        for ip in lan:                                   # escuchando en 127.0.0.1, tus IP de red no responden
            with self.assertRaises(OSError):
                socket.create_connection((ip, self.port), 0.5).close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
