"""Convierte las sesiones grabadas en tomas cortas para reproducirlas en el mocap (server/web/mocap.html).

    python tools/export_mocap.py              # todas las sesiones de recordings/
    python tools/export_mocap.py --max 6      # como mucho 6 tomas sin etiqueta por sesión

Cada toma son acelerómetro, giroscopio y gravedad remuestreados a 50 Hz en una malla común:
  - si la sesión tiene etiquetas (el dataset de gestos, los dibujos), una toma por etiqueta;
  - si no, los tramos de 30 s con más movimiento (el giroscopio más alto), sin huecos en los datos.
Se escriben en recordings/mocap/<id>.json más un índice recordings/mocap/index.json. Todo queda en
recordings/, que no se sube a git: son tus datos.
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent / "recordings"
HZ = 50
RIGHT_SINCE = 1793251800000   # 29 oct, 00:30: desde ahí el reloj iba en la muñeca derecha


def load(folder, name):
    f = folder / f"{name}.csv"
    if not f.exists():
        return None
    head = f.open(encoding="utf-8").readline().strip().split(",")
    tcol = "t_ms" if head[0] == "t_ms" else "t_watch_ms"      # grabador de dibujos: t_ms ya es la hora de pared
    df = pd.read_csv(f, usecols=[tcol, "x", "y", "z"]).dropna()
    df = df.sort_values(tcol).drop_duplicates(tcol)
    return df[tcol].to_numpy(float), df[["x", "y", "z"]].to_numpy(float)


def labels_of(folder):
    f = folder / "labels.jsonl"
    out = []
    if not f.exists():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        text = m.get("step") or m.get("label")
        if not text or str(text).startswith("_") or "t0" not in m or "t1" not in m:
            continue
        if m.get("trial"):
            text = f"{text} {m['trial']}"
        out.append((str(text), float(m["t0"]), float(m["t1"])))
    return out


def resample(t, v, grid):
    return np.stack([np.interp(grid, t, v[:, i]) for i in range(3)], axis=1)


def gap_free(t, a, b, max_gap=500):
    sel = t[(t >= a) & (t <= b)]
    return sel.size > 2 and sel[0] - a < max_gap and b - sel[-1] < max_gap and np.max(np.diff(sel)) < max_gap


def windows(tg, gg, n_max, length=30_000):
    """Los tramos de `length` ms con más giro, sin solaparse."""
    grid = np.arange(tg[0], tg[-1] - length, 1000.0)
    if grid.size == 0:
        return []
    mag = np.linalg.norm(gg, axis=1)
    cum = np.concatenate([[0], np.cumsum(mag)])
    score = []
    for a in grid:
        i0, i1 = np.searchsorted(tg, [a, a + length])
        if i1 - i0 < length / 1000 * 40:                 # menos de 40 Hz de media: hay huecos
            continue
        score.append(((cum[i1] - cum[i0]) / (i1 - i0), a))
    score.sort(reverse=True)
    picked = []
    for s, a in score:
        if s < 15:                                        # casi quieto: no vale la pena
            break
        if all(abs(a - p) >= length for p in picked):
            picked.append(a)
        if len(picked) >= n_max:
            break
    return [(None, a, a + length) for a in sorted(picked)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=6, help="tomas sin etiqueta por sesión")
    args = ap.parse_args()
    out_dir = ROOT / "mocap"
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    index = []
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name != "mocap"):
        acc, gyr, grv = load(folder, "ACCELERATION"), load(folder, "GYROSCOPE"), load(folder, "GRAVITY")
        if not (acc and gyr and grv):
            continue
        labs = labels_of(folder)
        takes = [(txt, a, min(b, a + 60_000)) for txt, a, b in labs] if labs else windows(*gyr, args.max)
        n_ok = 0
        for txt, a, b in takes:
            if b - a < 3000 or not all(gap_free(t, a, b) for t, _ in (acc, gyr, grv)):
                continue
            grid = np.arange(a, b, 1000 / HZ)
            A, W, Gv = (resample(t, v, grid) for t, v in (acc, gyr, grv))
            name = txt or f"tramo {len(index) + 1}"
            tid = re.sub(r"[^A-Za-z0-9_-]+", "-", f"{folder.name}-{name}").strip("-")[:80]
            take = {
                "id": tid, "sesion": folder.name, "nombre": name, "mano": "r" if a >= RIGHT_SINCE else "l",
                "hz": HZ, "t0": a, "n": len(grid),
                "acc": np.round(A, 2).ravel().tolist(), "gyr": np.round(W, 1).ravel().tolist(), "grav": np.round(Gv, 3).ravel().tolist(),
                "etiquetas": [{"texto": t2, "desde": round((x0 - a) / 1000, 2), "hasta": round((x1 - a) / 1000, 2)}
                              for t2, x0, x1 in labs if x1 > a and x0 < b],
            }
            (out_dir / f"{tid}.json").write_text(json.dumps(take, separators=(",", ":")), encoding="utf-8")
            index.append({k: take[k] for k in ("id", "sesion", "nombre", "mano", "t0")} | {"dur": round(len(grid) / HZ, 1)})
            n_ok += 1
        print(f"{folder.name}: {n_ok} tomas")
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(index)} tomas en {out_dir}")


if __name__ == "__main__":
    main()
