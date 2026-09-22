"""Crop-and-stitch inpainting.

The naive way to inpaint is to regenerate the whole image and keep only the
masked part. That wastes the pixel budget: a face occupying 8% of a 1024px
frame gets ~290px of detail no matter how many megapixels you pay for.

Crop-and-stitch instead:
  1. take the mask's bounding box and pad it,
  2. expand it to the target aspect ratio and crop,
  3. generate at FULL resolution over that crop, so every pixel lands on the
     region being edited,
  4. paste back through a feathered mask so the seam disappears.

The generator never sees the rest of the image, which is the point: it cannot
drift what it is not looking at.
"""

from __future__ import annotations

from PIL import Image, ImageFilter, ImageOps


def bbox_de_mascara(mask: Image.Image, umbral: int = 16) -> tuple[int, int, int, int] | None:
    """Bounding box of everything brighter than `umbral`, or None if empty."""
    m = mask.convert("L")
    return m.point(lambda v: 255 if v > umbral else 0).getbbox()


def recorte(
    imagen: Image.Image,
    mask: Image.Image,
    *,
    padding: float = 0.35,
    ratio: float | None = None,
    minimo: int = 256,
) -> tuple[tuple[int, int, int, int], Image.Image, Image.Image]:
    """Return (caja, imagen_recortada, mascara_recortada).

    `padding` grows the box by a fraction of its longest side, so the model gets
    context around the edit instead of a tight crop that it has to guess into.
    `ratio` (width / height) forces the crop's aspect; None keeps the box's own.
    """
    caja = bbox_de_mascara(mask)
    if caja is None:
        raise ValueError("the mask is empty: nothing to inpaint")

    W, H = imagen.size
    x0, y0, x1, y1 = caja
    w, h = x1 - x0, y1 - y0
    pad = int(max(w, h) * padding)
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad

    # enforce a minimum so tiny masks still get usable context
    if (x1 - x0) < minimo:
        c = (x0 + x1) // 2
        x0, x1 = c - minimo // 2, c + minimo // 2
    if (y1 - y0) < minimo:
        c = (y0 + y1) // 2
        y0, y1 = c - minimo // 2, c + minimo // 2

    if ratio:
        w, h = x1 - x0, y1 - y0
        if w / h < ratio:                      # too narrow: widen
            nuevo = int(h * ratio)
            c = (x0 + x1) // 2
            x0, x1 = c - nuevo // 2, c + nuevo // 2
        else:                                  # too wide: heighten
            nuevo = int(w / ratio)
            c = (y0 + y1) // 2
            y0, y1 = c - nuevo // 2, c + nuevo // 2

    # slide the box back inside the image rather than clipping it, so the
    # requested aspect ratio survives near the edges
    w, h = x1 - x0, y1 - y0
    if w > W:
        x0, x1 = 0, W
    elif x0 < 0:
        x0, x1 = 0, w
    elif x1 > W:
        x0, x1 = W - w, W
    if h > H:
        y0, y1 = 0, H
    elif y0 < 0:
        y0, y1 = 0, h
    elif y1 > H:
        y0, y1 = H - h, H

    caja = (max(0, x0), max(0, y0), min(W, x1), min(H, y1))
    return caja, imagen.crop(caja), mask.convert("L").crop(caja)


def pegar(
    original: Image.Image,
    generado: Image.Image,
    mask_recortada: Image.Image,
    caja: tuple[int, int, int, int],
    *,
    difuminado: int = 12,
) -> Image.Image:
    """Paste `generado` back into `original` through a feathered mask."""
    x0, y0, x1, y1 = caja
    destino = (x1 - x0, y1 - y0)

    gen = generado if generado.size == destino else generado.resize(destino, Image.LANCZOS)
    m = mask_recortada if mask_recortada.size == destino else mask_recortada.resize(destino, Image.LANCZOS)
    if difuminado > 0:
        m = m.filter(ImageFilter.GaussianBlur(difuminado))

    out = original.convert("RGB").copy()
    out.paste(gen.convert("RGB"), (x0, y0), m)
    return out


def previsualizar_mascara(imagen: Image.Image, mask: Image.Image,
                          color=(255, 64, 64), alpha: float = 0.45) -> Image.Image:
    """Image with the mask tinted on top, for showing what will be replaced."""
    base = imagen.convert("RGB")
    capa = Image.new("RGB", base.size, color)
    m = mask.convert("L").point(lambda v: int(v * alpha))
    return Image.composite(capa, base, m).convert("RGB") if False else Image.blend(
        base, Image.composite(capa, base, mask.convert("L")), alpha)


def dilatar(mask: Image.Image, pixeles: int) -> Image.Image:
    """Grow (or shrink, if negative) the mask. Useful to cover halos left by a
    segmenter that cuts slightly inside the object."""
    if pixeles == 0:
        return mask
    m = mask.convert("L")
    if pixeles > 0:
        return m.filter(ImageFilter.MaxFilter(2 * pixeles + 1))
    return ImageOps.invert(
        ImageOps.invert(m).filter(ImageFilter.MaxFilter(2 * abs(pixeles) + 1)))
