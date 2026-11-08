"""El ícono de la app: un reloj (anillo turquesa con correa) y un cursor encima, sobre un cuadro oscuro.

    python tools/make_icon.py        # escribe app/icon.png (256 px) y app/icon.ico (16 a 256 px)

Se dibuja a 4 veces el tamaño y se reduce, para que los bordes salgan suaves.
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app"
S = 1024                                     # se dibuja grande y se reduce


def draw():
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(im)
    g.rounded_rectangle([40, 40, S - 40, S - 40], radius=210, fill=(16, 19, 26, 255))
    # la correa, arriba y abajo del reloj
    cx, cy, r = 430, 470, 250
    g.rounded_rectangle([cx - 120, cy - r - 170, cx + 120, cy + r + 170], radius=70, fill=(44, 53, 70, 255))
    # el reloj: caja, anillo turquesa y pantalla
    g.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(29, 34, 46, 255))
    g.ellipse([cx - r + 28, cy - r + 28, cx + r - 28, cy + r - 28], outline=(93, 202, 165, 255), width=46)
    g.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], fill=(15, 110, 86, 255))
    # el cursor, saliendo del reloj hacia abajo a la derecha
    tip = (600, 560)
    arrow = [tip, (tip[0], tip[1] + 330), (tip[0] + 85, tip[1] + 250), (tip[0] + 150, tip[1] + 380),
             (tip[0] + 215, tip[1] + 350), (tip[0] + 150, tip[1] + 222), (tip[0] + 265, tip[1] + 215)]
    g.polygon(arrow, fill=(236, 233, 225, 255), outline=(16, 19, 26, 255))
    g.line(arrow + [arrow[0]], fill=(16, 19, 26, 255), width=26, joint="curve")
    g.polygon(arrow, fill=(236, 233, 225, 255))
    return im


def main():
    big = draw()
    OUT.mkdir(exist_ok=True)
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("app/icon.png y app/icon.ico")


if __name__ == "__main__":
    main()
