"""Minimal pure-Python sdb client (Tizen's ADB-like protocol) over TCP, so the bridge runs anywhere
Python does (Windows, Termux on Android) without sdb.exe.

Wire format, confirmed by proxying the official sdb against an SM-R800:
  24-byte header <cmd, arg0, arg1, len, sum(payload), cmd ^ 0xffffffff> + payload
  CNXN(0x100000, 0x40000, "host::\\0") -> AUTH token -> AUTH signature (or public key) -> CNXN "device::<model>::0"
  OPEN(local, 0, "shell:<cmd>\\0") -> OKAY(remote, local) -> WRTE... (each acked with OKAY) -> CLSE

Key: the official sdb's ~/.tizen/sdbkey when present (already authorised); otherwise one generated in pure
Python in ~/.gearstream/sdbkey.json, which makes the watch ask to allow this computer/phone the first time.
"""
import asyncio
import base64
import json
import random
import re
import socket
import struct
import subprocess
import time
from pathlib import Path

A_CNXN, A_AUTH, A_OPEN, A_OKAY, A_CLSE, A_WRTE = (struct.unpack("<I", c)[0] for c in
                                                  (b"CNXN", b"AUTH", b"OPEN", b"OKAY", b"CLSE", b"WRTE"))
AUTH_TOKEN, AUTH_SIGNATURE, AUTH_RSAPUBLICKEY = 1, 2, 3
KEY_FILE = Path.home() / ".gearstream" / "sdbkey.json"
SDB_KEY_FILE = Path.home() / ".tizen" / "sdbkey"
SHA1_DIGEST_INFO = bytes.fromhex("3021300906052b0e03021a05000414")


# ---------- RSA (pure Python, only what ADB-style auth needs) ----------

def _is_probable_prime(n, rounds=40):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        x = pow(random.randrange(2, n - 1), d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits):
    rng = random.SystemRandom()
    while True:
        p = rng.getrandbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if _is_probable_prime(p):
            return p


def _der_read(data, pos):
    """Returns (tag, value, next_pos) for one DER element."""
    tag, length = data[pos], data[pos + 1]
    pos += 2
    if length & 0x80:
        n = length & 0x7F
        length = int.from_bytes(data[pos:pos + n], "big")
        pos += n
    return tag, data[pos:pos + length], pos + length


def _key_from_pkcs8_pem(text):
    der = base64.b64decode("".join(line for line in text.splitlines() if "-----" not in line))
    _, info, _ = _der_read(der, 0)                    # PrivateKeyInfo SEQUENCE
    pos = _der_read(info, 0)[2]                       # version
    pos = _der_read(info, pos)[2]                     # algorithm
    _, octets, _ = _der_read(info, pos)               # OCTET STRING -> RSAPrivateKey
    _, rsa, _ = _der_read(octets, 0)
    ints, pos = [], 0
    while pos < len(rsa) and len(ints) < 4:
        _, value, pos = _der_read(rsa, pos)
        ints.append(int.from_bytes(value, "big"))
    _, n, e, d = ints
    return {"n": n, "e": e, "d": d}


def load_or_create_key():
    # The official sdb's key is already authorised by the watch: reuse it (copy it to the phone too).
    if SDB_KEY_FILE.exists():
        return _key_from_pkcs8_pem(SDB_KEY_FILE.read_text())
    if KEY_FILE.exists():
        return json.loads(KEY_FILE.read_text())
    e = 65537
    while True:
        p, q = _prime(1024), _prime(1024)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e and (p * q).bit_length() == 2048:
            break
    key = {"n": p * q, "e": e, "d": pow(e, -1, phi)}
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(json.dumps(key))
    return key


def sign_token(key, token):
    """PKCS#1 v1.5 signature of an already-hashed SHA-1 token (what ADB's RSA_sign(NID_sha1) produces)."""
    k = 256
    payload = SHA1_DIGEST_INFO + token
    em = b"\x00\x01" + b"\xff" * (k - 3 - len(payload)) + b"\x00" + payload
    return pow(int.from_bytes(em, "big"), key["d"], key["n"]).to_bytes(k, "big")


def public_key_blob(key, comment="gearstream@bridge"):
    """Android's RSAPublicKey struct (len, n0inv, n[], rr[], e), base64 + comment."""
    n, words = key["n"], 64
    n0inv = (-pow(n, -1, 1 << 32)) % (1 << 32)
    rr = pow(1 << 2048, 2, n)
    blob = struct.pack("<II", words, n0inv) + n.to_bytes(256, "little") + rr.to_bytes(256, "little")
    blob += struct.pack("<I", key["e"])
    return base64.b64encode(blob) + f" {comment}\x00".encode()


# ---------- Protocol ----------

class Stream:
    def __init__(self):
        self.remote_id = None
        self.opened = asyncio.get_running_loop().create_future()
        self.queue = asyncio.Queue()  # bytes chunks; None = closed
        # Round-trip stats: the watch may not send the next WRTE until we OKAY the previous one,
        # so (next WRTE arrival - our OKAY) ≈ network round trip (+ wait for the next line).
        self.okay_at = None
        self.rtt_min = float("inf")
        self.rtt_sum = 0.0
        self.rtt_n = 0
        self.line_count = 0    # not "lines": that is the async generator below
        self.packet_count = 0

    async def lines(self):
        buf = b""
        while True:
            chunk = await self.queue.get()
            if chunk is None:
                break
            buf += chunk
            *complete, buf = buf.split(b"\n")
            for line in complete:
                yield line.rstrip(b"\r").decode(errors="replace")
        if buf:
            yield buf.decode(errors="replace")


class SdbConnection:
    def __init__(self, host, port=26101):
        self.host, self.port = host, port
        self.streams = {}
        self.next_id = 1
        self.model = "?"
        self.on_auth_prompt = lambda: print("Acepta la conexión en el reloj (aviso de RSA)...")

    async def connect(self, timeout=60):
        self.reader, self.writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 10)
        key = load_or_create_key()
        self._send(A_CNXN, 0x100000, 0x40000, b"host::\x00")
        sent_signature = False
        while True:
            cmd, a0, a1, payload = await asyncio.wait_for(self._read_packet(), timeout)
            if cmd == A_AUTH and a0 == AUTH_TOKEN:
                if not sent_signature:
                    self._send(A_AUTH, AUTH_SIGNATURE, 0, sign_token(key, payload))
                    sent_signature = True
                else:  # signature not recognised: offer our public key, the watch shows a prompt
                    self.on_auth_prompt()
                    self._send(A_AUTH, AUTH_RSAPUBLICKEY, 0, public_key_blob(key))
            elif cmd == A_CNXN:
                parts = payload.rstrip(b"\x00").decode(errors="replace").split("::")
                self.model = parts[1] if len(parts) > 1 else "?"
                break
        self.reader_task = asyncio.create_task(self._dispatch())
        return self

    def _send(self, cmd, a0, a1, payload=b""):
        header = struct.pack("<6I", cmd, a0, a1, len(payload), sum(payload) & 0xFFFFFFFF, cmd ^ 0xFFFFFFFF)
        self.writer.write(header + payload)

    async def _read_packet(self):
        cmd, a0, a1, length, _, _ = struct.unpack("<6I", await self.reader.readexactly(24))
        payload = await self.reader.readexactly(length) if length else b""
        return cmd, a0, a1, payload

    async def _dispatch(self):
        try:
            while True:
                cmd, a0, a1, payload = await self._read_packet()
                stream = self.streams.get(a1)
                if stream is None:
                    continue
                if cmd == A_OKAY and stream.remote_id is None:
                    stream.remote_id = a0
                    stream.opened.set_result(True)
                elif cmd == A_WRTE:
                    now = time.monotonic()
                    if stream.okay_at is not None:
                        rtt = (now - stream.okay_at) * 1000
                        stream.rtt_min = min(stream.rtt_min, rtt)
                        stream.rtt_sum += rtt
                        stream.rtt_n += 1
                    stream.line_count += payload.count(b"\n")
                    stream.packet_count += 1
                    stream.queue.put_nowait(payload)
                    self._send(A_OKAY, a1, a0)
                    stream.okay_at = time.monotonic()
                elif cmd == A_CLSE:
                    if not stream.opened.done():
                        stream.opened.set_result(False)
                    stream.queue.put_nowait(None)
                    self.streams.pop(a1, None)
        except (asyncio.IncompleteReadError, ConnectionError):
            for stream in self.streams.values():
                if not stream.opened.done():
                    stream.opened.set_result(False)
                stream.queue.put_nowait(None)
            self.streams.clear()

    async def shell(self, command):
        """Starts `command` on the watch; returns a Stream whose .lines() yields its output."""
        local_id = self.next_id
        self.next_id += 1
        stream = self.streams[local_id] = Stream()
        self._send(A_OPEN, local_id, 0, f"shell:{command}\x00".encode())
        if not await asyncio.wait_for(stream.opened, 15):
            raise ConnectionError(f"el reloj rechazó: {command}")
        return stream

    async def run(self, command):
        stream = await self.shell(command)
        return "\n".join([line async for line in stream.lines()])

    def stats(self):
        """Round-trip and coalescing figures since the last call, over the busiest streams
        (slow streams wait up to a full sample period for their next line, which would inflate
        the mean). None until at least one busy stream has data."""
        streams = [s for s in self.streams.values() if s.rtt_n >= 20]
        result = None
        if streams:
            result = {
                "rtt_min_ms": min(s.rtt_min for s in streams),
                "rtt_mean_ms": sum(s.rtt_sum for s in streams) / sum(s.rtt_n for s in streams),
                "lines_per_packet": sum(s.line_count for s in streams) / sum(s.packet_count for s in streams),
            }
        for s in self.streams.values():
            s.rtt_min, s.rtt_sum, s.rtt_n, s.line_count, s.packet_count = float("inf"), 0.0, 0, 0, 0
        return result

    def close(self):
        self.writer.close()


# ---------- Finding the watch ----------

HOTSPOT_SUBNETS = ("192.168.43", "192.168.225", "192.168.49", "192.168.137", "192.168.0", "192.168.1", "10.0.0")


def local_ipv4s():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:  # Linux/Android (Termux): ask each interface directly, /proc/net is off-limits to apps there
        import fcntl
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            for _, name in socket.if_nameindex():
                try:
                    res = fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", name.encode()[:15]))  # SIOCGIFADDR
                    ips.add(socket.inet_ntoa(res[20:24]))
                except OSError:
                    pass
    except (ImportError, OSError, AttributeError):
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # sends nothing; picks the default route's address
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    # Android (Termux): the hotspot interface is not the default route and the ioctl above may be
    # denied, but the system's `ip`/`ifconfig` still list every address.
    for cmd in (["ip", "-4", "-o", "addr"], ["/system/bin/ip", "-4", "-o", "addr"], ["ifconfig"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        ips.update(re.findall(r"inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)", out))
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.")))


async def find_watch(port=26101, timeout=0.5, concurrency=256):
    """Hosts with the sdb port open on this machine's /24 subnets and the usual hotspot ranges."""
    subnets = []
    for ip in local_ipv4s():
        subnet = ip.rsplit(".", 1)[0]
        if subnet not in subnets:
            subnets.append(subnet)
    for subnet in HOTSPOT_SUBNETS:
        if subnet not in subnets:
            subnets.append(subnet)
    sem = asyncio.Semaphore(concurrency)
    found = []

    async def probe(host):
        async with sem:
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
            except (OSError, asyncio.TimeoutError):
                return
            writer.close()
            found.append(host)

    await asyncio.gather(*(probe(f"{subnet}.{i}") for subnet in subnets for i in range(1, 255)))
    return found


async def _demo(host):
    conn = await SdbConnection(host).connect()
    print("conectado a", conn.model)
    print(await conn.run("echo hola desde $(cat /etc/hostname 2>/dev/null || echo reloj)"))
    conn.close()


if __name__ == "__main__":
    import sys
    asyncio.run(_demo(sys.argv[1] if len(sys.argv) > 1 else "192.168.0.XX"))
