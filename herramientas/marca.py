"""Draw the QwenStudio mark and write the icon files.

The mark is a body and a lens fused into one silhouette: the frame you compose
in and the thing you point at it, in Superside's palette
(#0A211F and #D8FF85). It is an original symbol, not the Superside logo: this
is an unofficial exploration and a registered wordmark has no business in it.

    .venv\\Scripts\\python.exe herramientas\\marca.py

Writes QwenStudio.ico (for a Windows shortcut) and docs/marca.png (for the
README). The SVG the interface uses lives inline in qwenstudio/interfaz.py.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TINTA = (10, 33, 31, 255)
LIMA = (216, 255, 133, 255)


def dibujar(lado: int) -> Image.Image:
    """The mark at `lado` pixels, drawn 4x and downsampled.

    Pillow has no anti-aliasing on rounded rectangles, so the only way to get
    a clean edge at 32 px is to draw it at 128 and resize.
    """
    e = 4
    n = lado * e
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = n / 48.0                                   # el svg esta pensado en 48

    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=round(12 * u), fill=TINTA)
    d.rounded_rectangle([round(9 * u), round(14 * u), round(27 * u), round(32 * u)],
                        radius=round(5 * u), fill=LIMA)
    d.ellipse([round(21 * u), round(9 * u), round(39 * u), round(27 * u)], fill=LIMA)
    d.ellipse([round(24.4 * u), round(12.4 * u), round(35.6 * u), round(23.6 * u)], fill=TINTA)
    return im.resize((lado, lado), Image.LANCZOS)


def main() -> None:
    tamanos = [16, 24, 32, 48, 64, 128, 256]
    capas = [dibujar(t) for t in tamanos]
    ico = os.path.join(APP, "QwenStudio.ico")
    capas[-1].save(ico, format="ICO", sizes=[(t, t) for t in tamanos])

    docs = os.path.join(APP, "docs")
    os.makedirs(docs, exist_ok=True)
    png = os.path.join(docs, "marca.png")
    dibujar(256).save(png)

    for p in (ico, png):
        print(f"  {os.path.relpath(p, APP):<22} {os.path.getsize(p)/1024:6.1f} KB")


if __name__ == "__main__":
    main()
