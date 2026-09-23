"""Draw the QwenStudio mark and write the icon files.

The mark is a Q, drawn as a ring with the tail crossing the stroke, in
Superside's palette
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
    u = n / 48.0                                   # the svg is drawn on 48 units

    import math
    cx, cy, r_ext, grosor, largo, ancho = 22.8, 21.8, 13.2, 4.6, 9.0, 4.6
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=round(12 * u), fill=TINTA)
    d.ellipse([(cx - r_ext) * u, (cy - r_ext) * u,
               (cx + r_ext) * u, (cy + r_ext) * u], fill=LIMA)
    ri = r_ext - grosor
    d.ellipse([(cx - ri) * u, (cy - ri) * u, (cx + ri) * u, (cy + ri) * u], fill=TINTA)

    # the tail starts at the centre of the ring's stroke, not inside the
    # counter: that way it crosses the ring as a real Q does, with no loose
    # lump left over
    rm = r_ext - grosor / 2
    ang = math.radians(45)
    x1, y1 = cx + rm * math.cos(ang), cy + rm * math.sin(ang)
    x2, y2 = x1 + largo * math.cos(ang), y1 + largo * math.sin(ang)
    d.line([x1 * u, y1 * u, x2 * u, y2 * u], fill=LIMA, width=round(ancho * u))
    for px, py in ((x1, y1), (x2, y2)):
        d.ellipse([(px - ancho / 2) * u, (py - ancho / 2) * u,
                   (px + ancho / 2) * u, (py + ancho / 2) * u], fill=LIMA)
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
