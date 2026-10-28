"""Builds server/web/gearstream-phone.zip, the bundle Termux downloads from the laptop's server
(README, "En el teléfono, sin laptop"). Only code goes in: never recordings or keys."""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "server/server.py", "server/web/index.html", "server/web/app.js", "server/web/style.css",
    "server/web/calibrate.html", "server/web/calibrate.js", "server/web/avatar.html", "server/web/avatar.js", "server/web/armfilter.js",
    "tools/sdb_client.py", "tools/sdb_bridge.py", "tools/batch_test.py",
    "phone/start.sh", "requirements.txt",
]
OUT = os.path.join(ROOT, "server", "web", "gearstream-phone.zip")

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in FILES:
        z.write(os.path.join(ROOT, f), "gearstream/" + f)
print(f"{os.path.relpath(OUT, ROOT)}: {os.path.getsize(OUT)} bytes, {len(FILES)} archivos")
