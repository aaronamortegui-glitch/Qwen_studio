"""Build the text-to-image showcase sheet from docs/muestra/.

    .venv\\Scripts\\python.exe herramientas\\hoja_muestra.py

One image per starting point in the prompt library, laid out in a grid with the
label under each. The point is that the library's starting points are not
suggestions someone typed — every one of them has been run, and this is what
came out.

Each cell keeps its own aspect ratio inside a fixed box, letterboxed on the
page background rather than stretched, because a showcase that distorts its own
output is arguing against itself.
"""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUESTRA = os.path.join(APP, "docs", "muestra")

HUESO = (247, 249, 242)
TINTA = (10, 33, 31)
TENUE = (74, 93, 89)
LINEA = (221, 227, 214)

CELDA = 360
PIE = 34
HUECO = 14
MARGEN = 20


def _fuente(tam: int, negrita: bool = False):
    for n in (("interTight-Bold.ttf", "seguisb.ttf", "arialbd.ttf") if negrita
              else ("InterTight.ttf", "segoeui.ttf", "arial.ttf")):
        for base in (os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fuentes"),
                     r"C:\Windows\Fonts"):
            try:
                return ImageFont.truetype(os.path.join(base, n), tam)
            except Exception:
                continue
    return ImageFont.load_default()


def main() -> None:
    sys.path.insert(0, APP)
    from qwenstudio.prompts import BASES

    entradas = []
    for caso in ("blank", "sign"):
        for etiqueta, _ in BASES[caso]:
            slug = etiqueta.lower().replace(" ", "_")
            ruta = os.path.join(MUESTRA, f"{caso}_{slug}.jpg")
            if os.path.exists(ruta):
                entradas.append((etiqueta, ruta))
    if not entradas:
        raise SystemExit(f"  no hay imagenes en {MUESTRA}\n"
                         f"  generalas primero con la app en marcha")

    cols = 4
    filas = (len(entradas) + cols - 1) // cols
    an = MARGEN * 2 + cols * CELDA + (cols - 1) * HUECO
    al = MARGEN * 2 + filas * (CELDA + PIE) + (filas - 1) * HUECO + 46

    hoja = Image.new("RGB", (an, al), HUESO)
    d = ImageDraw.Draw(hoja)
    d.text((MARGEN, MARGEN - 4), "Text to image, one run per starting point",
           font=_fuente(21, True), fill=TINTA)
    d.text((MARGEN, MARGEN + 24),
           "Every prompt in the library's starting points, generated on this machine at "
           "30 steps. Nothing retried, nothing picked from a batch.",
           font=_fuente(13), fill=TENUE)

    f_et = _fuente(14, True)
    y0 = MARGEN + 46
    for i, (etiqueta, ruta) in enumerate(entradas):
        cx = MARGEN + (i % cols) * (CELDA + HUECO)
        cy = y0 + (i // cols) * (CELDA + PIE + HUECO)
        im = Image.open(ruta).convert("RGB")
        # fitted inside the cell keeping its aspect ratio: a contact sheet that
        # distorts its own output contradicts itself
        im.thumbnail((CELDA, CELDA), Image.LANCZOS)
        caja = Image.new("RGB", (CELDA, CELDA), (238, 243, 228))
        caja.paste(im, ((CELDA - im.width) // 2, (CELDA - im.height) // 2))
        hoja.paste(caja, (cx, cy))
        d.rectangle([cx, cy, cx + CELDA - 1, cy + CELDA - 1], outline=LINEA)
        d.text((cx + 2, cy + CELDA + 8), etiqueta, font=f_et, fill=TINTA)

    destino = os.path.join(APP, "docs", "muestra-t2i.jpg")
    hoja.save(destino, "JPEG", quality=84, optimize=True)
    print(f"  {len(entradas)} imagenes  ->  {os.path.relpath(destino, APP)}  "
          f"({os.path.getsize(destino)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
