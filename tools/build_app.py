"""Arma GearStream.exe con PyInstaller, en un entorno aparte para no tocar tu Python.

    python tools/build_app.py              # crea .venv-build, instala app/requirements.txt y arma dist/GearStream/
    python tools/build_app.py --no-venv    # con el Python actual (así lo hace GitHub Actions)
    python tools/build_app.py --zip        # además deja dist/GearStream-<versión>-windows.zip para Releases

El resultado es una carpeta, dist/GearStream/, con GearStream.exe adentro: arranca más rápido que un solo
.exe autoextraíble y los antivirus la miran con menos sospecha. Dentro van las páginas (server/web, con
three.js) y el ícono. Al final se corre `GearStream.exe prueba` contra lo que se armó: servidor + reloj
simulado + páginas; si falla, el armado falla.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv-build"


def version():
    return re.search(r'VERSION = "([^"]+)"', (ROOT / "app" / "gearstream.py").read_text(encoding="utf-8")).group(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-venv", action="store_true", help="usar el Python actual en vez de .venv-build")
    ap.add_argument("--zip", action="store_true", help="empaquetar también un .zip para descargar")
    args = ap.parse_args()

    py = sys.executable
    if not args.no_venv:
        if not VENV.exists():
            print("creando .venv-build…")
            subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
        py = str(VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))
        subprocess.run([py, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
        subprocess.run([py, "-m", "pip", "install", "-q", "-r", str(ROOT / "app" / "requirements.txt")], check=True)

    sep = ";" if sys.platform == "win32" else ":"           # PyInstaller separa origen y destino así
    cmd = [py, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "GearStream",
           "--icon", str(ROOT / "app" / "icon.ico"),
           "--paths", str(ROOT / "server"), "--paths", str(ROOT / "tools"),
           "--add-data", f"{ROOT / 'server' / 'web'}{sep}web",
           "--add-data", f"{ROOT / 'app' / 'icon.png'}{sep}.",
           "--collect-submodules", "websockets",
           "--exclude-module", "numpy", "--exclude-module", "matplotlib", "--exclude-module", "pandas",
           "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
           str(ROOT / "app" / "gearstream.py")]
    print("armando con PyInstaller…")
    subprocess.run(cmd, check=True, cwd=ROOT)
    exe = ROOT / "dist" / "GearStream" / ("GearStream.exe" if sys.platform == "win32" else "GearStream")

    print("probando el ejecutable (servidor + reloj simulado + páginas)…")
    rc = subprocess.run([str(exe), "prueba"], timeout=120).returncode
    report = Path.home() / ".gearstream" / "prueba.txt"
    if report.exists():
        print(report.read_text(encoding="utf-8").split("\n\n")[0])
    if rc != 0:
        sys.exit("la prueba del ejecutable falló")

    if args.zip:
        base = ROOT / "dist" / f"GearStream-{version()}-windows"
        shutil.make_archive(str(base), "zip", ROOT / "dist", "GearStream")
        print(f"listo: {base}.zip")
    print(f"listo: {exe}")


if __name__ == "__main__":
    main()
