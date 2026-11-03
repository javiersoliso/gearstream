"""El lanzador de antes ahora es la app: app/gearstream.py (o GearStream.exe).

    python tools/launcher.py        # igual que python app/gearstream.py

Se deja este archivo para que el comando de siempre siga funcionando.
"""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent.parent / "app" / "gearstream.py"), run_name="__main__")
