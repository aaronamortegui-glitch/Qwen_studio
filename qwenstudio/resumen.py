"""Contact sheet: the inputs and the result on one image.

A generation with three references is hard to judge from the output alone —
you cannot tell which reference contributed what, or whether one was ignored.
This lays them side by side with the operator between them, so the whole
recipe reads at a glance and can be kept or shared as a single file.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

FONDO = (243, 245, 249)
TEXTO = (27, 28, 30)
TENUE = (69, 72, 80)
ACENTO = (11, 87, 208)


def _fuente(tam: int, negrita: bool = False):
    for nombre in (("arialbd.ttf", "seguisb.ttf") if negrita else ("arial.ttf", "segoeui.ttf")):
        try:
            return ImageFont.truetype(nombre, tam)
        except Exception:
            continue
    return ImageFont.load_default()


def _escalar(img: Image.Image, alto: int) -> Image.Image:
    """Scale to a given height keeping the aspect ratio. Never distorts, and
    never pads: the cell takes the width the image actually needs."""
    copia = img.convert("RGB")
    ancho = max(1, round(copia.width * alto / copia.height))
    return copia.resize((ancho, alto), Image.LANCZOS)


def hoja(entradas: list[tuple[str, Image.Image]], salida: Image.Image,
         prompt: str = "", pie: str = "", lado: int = 300) -> Image.Image:
    """entradas: [(label, image), ...]  ->  one sheet ending in `salida`.

    The result is drawn larger than the inputs: it is what you are actually
    looking at, the references are there for context.
    """
    if not entradas:
        entradas = []

    alto_out = int(lado * 1.6)
    pad, cab, sep = 14, 26, 34
    f_pie = _fuente(13)
    f_lab = _fuente(13, True)
    f_op = _fuente(26, True)

    # cada celda se escala a una altura comun y conserva su proporcion, asi que
    # su ancho lo decide la imagen. Nada se estira ni se rellena con bandas.
    ins = [(et, _escalar(im, lado)) for et, im in entradas]
    out = _escalar(salida, alto_out)

    ancho = pad + sum(im.width + sep for _, im in ins) + out.width + pad
    alto_bloque = max([alto_out] + [im.height for _, im in ins])
    alto_prompt = 0
    if prompt:
        alto_prompt = 6 + len(_envolver(prompt, f_pie, ancho - 2 * pad)) * 17
    alto = pad + cab + alto_bloque + 8 + (20 if pie else 0) + alto_prompt + pad

    hoja = Image.new("RGB", (ancho, alto), FONDO)
    d = ImageDraw.Draw(hoja)

    y_centro = pad + cab + alto_bloque // 2
    x = pad
    for i, (etiqueta, im) in enumerate(ins):
        y = y_centro - im.height // 2
        d.text((x, y - cab + 6), etiqueta, font=f_lab, fill=TENUE)
        hoja.paste(im, (x, y))
        x += im.width
        signo = "+" if i < len(ins) - 1 else "="
        d.text((x + sep // 2 - 7, y_centro - 16), signo, font=f_op, fill=ACENTO)
        x += sep

    y = y_centro - out.height // 2
    d.text((x, y - cab + 6), "result", font=f_lab, fill=ACENTO)
    hoja.paste(out, (x, y))

    yy = pad + cab + alto_bloque + 8
    if pie:
        d.text((pad, yy), pie, font=f_pie, fill=TENUE)
        yy += 20
    if prompt:
        for ln in _envolver(prompt, f_pie, ancho - 2 * pad):
            d.text((pad, yy), ln, font=f_pie, fill=TENUE)
            yy += 17
    return hoja


def _envolver(texto: str, fuente, ancho: int) -> list[str]:
    palabras, lineas, actual = texto.split(), [], ""
    for w in palabras:
        prueba = f"{actual} {w}".strip()
        if fuente.getlength(prueba) <= ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = w
        if len(lineas) >= 4:          # el prompt completo vive en la UI, aqui solo un resumen
            break
    if actual and len(lineas) < 4:
        lineas.append(actual)
    if len(lineas) == 4:
        lineas[-1] = lineas[-1][:110] + "..."
    return lineas
