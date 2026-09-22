"""Build the showcase: what the app shows before you have made anything.

    .venv\\Scripts\\python.exe herramientas\\vitrina.py            (generate + pack)
    .venv\\Scripts\\python.exe herramientas\\vitrina.py --empacar   (pack only)

Eighteen pieces, each one produced by a path the app actually offers and, where
there is a starting point for that path, by that starting point rather than a
prompt written for the occasion. What you see when you open the app is
therefore what you get when you press the button.

Five of them build on each other on purpose: a character is invented from a
paragraph, that face is carried into a portrait, a scene and a cutout, and two
of the earlier images are then edited. The chain is the argument -- this is one
tool, not eight unrelated demos.

The recipe is never retyped. It is read back out of the tEXt chunk of the PNG
the app wrote, which is the same place the gallery reads it from, so the
showcase cannot drift from what the app actually did. The pieces are saved as
JPEG at 1100px: eighteen PNGs would be forty megabytes of repository for
thumbnails that are looked at three hundred pixels wide.

Needs the app running. Regenerating everything takes about twenty minutes on an
RTX 5090 and leaves the full-resolution PNGs in salidas/.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request

APP = os.environ.get("QWENSTUDIO", "http://127.0.0.1:7860")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDAS = os.path.join(RAIZ, "salidas")
EJEMPLOS = os.path.join(RAIZ, "ejemplos")
DESTINO = os.path.join(EJEMPLOS, "vitrina")
MANIFIESTO = os.path.join(EJEMPLOS, "vitrina.json")
REGISTRO = os.path.join(DESTINO, "_origen.json")
LADO = 1100

sys.path.insert(0, RAIZ)
from qwenstudio.prompts import BASES            # noqa: E402


def base(caso: str, nombre: str) -> str:
    for n, t in BASES[caso]:
        if n == nombre:
            return t
    raise SystemExit(f"no such starting point: {caso}/{nombre}")


IDENTIDAD = " The face of the subject must match the reference exactly."

# clave -> lo que hay que pedirle a la app y como se presenta despues.
#   titulo  el nombre en la ficha
#   caso    el camino de la interfaz al que pertenece
#   que     la frase que explica que se hizo, en la ficha y bajo la miniatura
PIEZAS: list[dict] = [
    # --- la cadena: una persona inventada y todo lo que se hace con ella ----
    {"clave": "personaje", "titulo": "A person from text", "caso": "blank",
     "ratio": "3:4", "seed": 5103,
     "prompt": "A studio headshot of a woman in her early sixties with close-cropped "
               "silver hair, dark brown eyes and deep laughter lines, wearing a charcoal "
               "linen shirt, framed from the chest up and square to camera against a "
               "seamless mid-grey backdrop, a large softbox just off the lens axis with a "
               "reflector filling the shadow side, sharp focus on the eyes, shot on an "
               "85mm lens.",
     "que": "A person invented from nothing but this paragraph. Everything below reuses "
            "this face as a reference, so the same character walks through the rest of "
            "the app."},

    {"clave": "retrato", "titulo": "New portrait", "caso": "portrait",
     "ratio": "3:4", "seed": 5201, "persona": "personaje",
     "prompt": "An editorial magazine portrait of the subject, wearing a black tailored "
               "blazer over a crisp white shirt, standing in a sunlit concrete gallery "
               "with tall windows, framed three-quarter length with room to one side, "
               "hard daylight raking from the left and deep shadow on the far side, shot "
               "on medium format with an 80mm lens." + IDENTIDAD,
     "que": "The same face, a new photograph: different wardrobe, different room, "
            "different light. The reference is tagged as the person, so identity is what "
            "carries over and nothing else."},

    {"clave": "escena", "titulo": "Into another photo", "caso": "scene",
     "ratio": "auto", "seed": 5301, "persona": "personaje", "escena": "interior",
     "prompt": "A colour photograph of the subject in that setting, wearing that "
               "wardrobe, framed and lit exactly as the reference is. The face of the "
               "subject must match the first reference exactly.",
     "que": "Two images the app made earlier, put together: the character from one and "
            "the bookshop from the other. The scene brings the place, the wardrobe and "
            "the light; the person brings only the face."},

    {"clave": "pose", "titulo": "Posed and graded", "caso": "pose",
     "ratio": "auto", "seed": 5302, "persona": "personaje", "estilo": "paisaje",
     "pose_lib": "fb_pockets",
     "prompt": "A colour photograph of the subject in that posture, wearing a camel wool "
               "overcoat over a charcoal roll-neck, on a wide empty beach under a low "
               "grey sky, graded like the style reference. The face of the subject must "
               "match the first reference exactly.",
     "que": "Three references, one job each: the face, a skeleton from the pose library "
            "for the posture, and the shoreline for the grade. The prompt only has to "
            "name the wardrobe."},

    {"clave": "recorte", "titulo": "Transparent cutout", "caso": "cutout",
     "ratio": "3:4", "seed": 5202, "persona": "personaje", "transparencia": True,
     "prompt": "Full body colour cutout of the subject, standing square to camera in a "
               "plain charcoal t-shirt and dark jeans, even studio light with no cast "
               "shadow, clean edges around the hair and the clothing." + IDENTIDAD,
     "que": "The same character on a real alpha channel, ready to drop into a layout. "
            "The transparency comes from the model, not from cutting the background out "
            "afterwards."},

    # --- lo que este modelo hace mejor que la mayoria ----------------------
    {"clave": "cartel", "titulo": "Poster", "caso": "sign", "ratio": "3:4", "seed": 3109,
     "prompt": base("sign", "Poster"),
     "que": "Words inside double quotes come out as lettering. This is the thing this "
            "model does better than most of its size."},

    {"clave": "neon", "titulo": "Neon sign", "caso": "sign", "ratio": "3:2", "seed": 3110,
     "prompt": base("sign", "Neon"),
     "que": "The same mechanism at night: the glow and the spelling are asked for in one "
            "sentence."},

    # --- las tres ediciones, sobre imagenes de esta misma vitrina ----------
    {"clave": "cambio", "titulo": "Replace something", "caso": "replace",
     "seed": 6101, "fuente": "paisaje", "endpoint": "/api/inpaint",
     "frase": "the sky",
     "prompt": "A towering wall of dark storm cloud lit from behind, the light breaking "
               "through in a narrow band above the horizon.",
     "que": "The sky named in words, nothing painted. CLIPSeg finds it, SAM 2 follows "
            "the edge, and only that region is regenerated — the shoreline below it "
            "is the same file."},

    {"clave": "arcilla", "titulo": "A look, one region", "caso": "look",
     "seed": 6104, "fuente": "retrato", "endpoint": "/api/efecto",
     "efecto": "clay", "frase": "the woman", "difuminado": 16, "padding": 0.15,
     "que": "The same grid of looks, confined to one region: the subject named in words "
            "and turned to clay, the room around her left as the photograph it was. "
            "Replacing something and applying a look are one operation underneath."},

    {"clave": "grado", "titulo": "A look, whole frame", "caso": "look",
     "seed": 6102, "fuente": "interior", "endpoint": "/api/efecto", "efecto": "cine",
     "que": "A look over the whole frame: teal into the shadows, the skin kept clean, "
            "the highlights rolling off. Picked from the grid, not typed."},

    # --- los puntos de partida de texto a imagen, tal cual vienen ----------
    {"clave": "producto", "titulo": "Product", "caso": "blank", "ratio": "3:2", "seed": 3101,
     "prompt": base("blank", "Product"),
     "que": "The Product starting point, unedited. A single softbox falling off into near "
            "black is the whole lighting instruction."},

    {"clave": "bodegon", "titulo": "Still life", "caso": "blank", "ratio": "3:2", "seed": 3108,
     "prompt": base("blank", "Still life"),
     "que": "The Still life starting point, with the palette held to ochre and grey by "
            "the prompt."},

    {"clave": "comida", "titulo": "Food", "caso": "blank", "ratio": "1:1", "seed": 3105,
     "prompt": base("blank", "Food"),
     "que": "The Food starting point. One hard source raking from behind is what makes "
            "the broth shine."},

    {"clave": "paisaje", "titulo": "Landscape", "caso": "blank", "ratio": "3:2", "seed": 3102,
     "prompt": base("blank", "Landscape"),
     "que": "The Landscape starting point. The long exposure is asked for in words, not "
            "applied afterwards."},

    {"clave": "interior", "titulo": "Interior", "caso": "blank", "ratio": "3:2", "seed": 3103,
     "prompt": base("blank", "Interior"),
     "que": "The Interior starting point. Warm lamps against the blue outside the window "
            "is a colour contrast the model holds on its own."},

    {"clave": "arquitectura", "titulo": "Architecture", "caso": "blank", "ratio": "3:4",
     "seed": 4203, "prompt": base("blank", "Architecture"),
     "que": "The Architecture starting point. Asking for straight verticals is what keeps "
            "a 24mm from falling over."},

    {"clave": "animal", "titulo": "Animal", "caso": "blank", "ratio": "3:2", "seed": 3104,
     "prompt": base("blank", "Animal"),
     "que": "The Animal starting point. Naming the 300mm lens is what compresses the "
            "background into soft colour."},

    {"clave": "ilustracion", "titulo": "Illustration", "caso": "blank", "ratio": "1:1",
     "seed": 3106, "prompt": base("blank", "Illustration"),
     "que": "The Illustration starting point: four flat colours and no gradients. Not "
            "everything this model does is photographic."},
]


# ---------------------------------------------------------------- la app

def _data_url(ruta: str) -> str:
    ext = os.path.splitext(ruta)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    with open(ruta, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def _pedir(ruta: str, carga: dict, timeout: int = 3600) -> dict:
    req = urllib.request.Request(APP + ruta, data=json.dumps(carga).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def generar() -> dict:
    """Run every piece through the app. Returns clave -> file it produced."""
    hechas: dict[str, str] = {}
    for p in PIEZAS:
        t0 = time.time()
        fuente = p.get("fuente")
        if fuente:                                   # una edicion
            carga = {"imagen": _data_url(hechas[fuente]),
                     "steps": 30, "seed": p["seed"], "variantes": 1,
                     "megapixeles": 1,
                     "difuminado": p.get("difuminado", 12),
                     "padding": p.get("padding", 0.35)}
            if p.get("efecto"):
                carga["efecto"] = p["efecto"]
            if p.get("frase"):
                carga["frase"] = p["frase"]
            if p.get("prompt"):
                carga["prompt"] = p["prompt"]
                carga.update(crecer=8, umbral=0.5)
            r = _pedir(p["endpoint"], carga)
        else:                                        # una generacion
            carga = {"prompt": p["prompt"], "steps": 30, "seed": p["seed"],
                     "variantes": 1, "megapixeles": 1, "lora": None, "fuerza_lora": 1.0,
                     "personas": [_data_url(hechas[p["persona"]])] if p.get("persona") else [],
                     "escena": _data_url(hechas[p["escena"]]) if p.get("escena") else None,
                     "estilo": _data_url(hechas[p["estilo"]]) if p.get("estilo") else None,
                     "estilo_modo": "look", "pose_lib": p.get("pose_lib"), "pose_url": None,
                     "ratio": p.get("ratio", "auto"),
                     "transparencia": bool(p.get("transparencia"))}
            r = _pedir("/api/generar", carga)

        if r.get("error"):
            raise SystemExit(f"  {p['clave']}: {r['error']}")
        archivo = os.path.join(SALIDAS, os.path.basename(r["imagenes"][0]["archivo"]))
        hechas[p["clave"]] = archivo
        print(f"  {p['clave']:14} {r['imagenes'][0]['tam']:>10}  {round(time.time()-t0)}s")

    os.makedirs(DESTINO, exist_ok=True)
    with open(REGISTRO, "w", encoding="utf-8") as f:
        json.dump({k: os.path.basename(v) for k, v in hechas.items()}, f, indent=1)
    return hechas


# ------------------------------------------------------------- el paquete

def _receta(png: str) -> dict:
    from PIL import Image
    with Image.open(png) as im:
        t = dict(getattr(im, "text", None) or {})
    return {k: v for k, v in t.items() if v not in ("", "None")}


def _encoger(origen: str, destino: str) -> int:
    from PIL import Image
    with Image.open(origen) as im:
        if im.mode == "RGBA":
            # un tablero de transparencia dice la verdad donde un blanco liso
            # haria pasar un PNG con alfa por una foto normal
            fondo = Image.new("RGB", im.size, (255, 255, 255))
            c = 24
            for y in range(0, im.height, c):
                for x in range(0, im.width, c):
                    if ((x // c) + (y // c)) % 2:
                        fondo.paste((236, 238, 232), (x, y, x + c, y + c))
            fondo.paste(im, mask=im.split()[3])
            im = fondo
        im = im.convert("RGB")
        if max(im.size) > LADO:
            e = LADO / max(im.size)
            im = im.resize((round(im.width * e), round(im.height * e)), Image.LANCZOS)
        im.save(destino, quality=88, optimize=True)
    return os.path.getsize(destino)


def empacar(hechas: dict | None = None) -> None:
    if hechas is None:
        if not os.path.exists(REGISTRO):
            raise SystemExit("nothing generated yet: run without --empacar")
        with open(REGISTRO, encoding="utf-8") as f:
            hechas = {k: os.path.join(SALIDAS, v) for k, v in json.load(f).items()}

    os.makedirs(DESTINO, exist_ok=True)
    for f in os.listdir(DESTINO):
        if f.endswith(".jpg"):
            os.remove(os.path.join(DESTINO, f))

    titulos = {p["clave"]: p["titulo"] for p in PIEZAS}
    salida, total = [], 0
    for p in PIEZAS:
        png = hechas.get(p["clave"])
        if not png or not os.path.exists(png):
            print(f"  missing: {p['clave']}")
            continue
        jpg = p["clave"] + ".jpg"
        total += _encoger(png, os.path.join(DESTINO, jpg))
        pieza = {"clave": p["clave"], "titulo": p["titulo"], "caso": p["caso"],
                 "que": p["que"], "archivo": "/vitrina/" + jpg, "meta": _receta(png)}
        if p.get("fuente"):
            # la foto de partida es otra pieza de la vitrina: se apunta a ella
            # en vez de duplicar el archivo, y de paso queda dicho que una cosa
            # se hizo encima de la otra
            pieza["antes"] = "/vitrina/" + p["fuente"] + ".jpg"
            pieza["antes_de"] = titulos[p["fuente"]]
        salida.append(pieza)

    with open(MANIFIESTO, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=1, ensure_ascii=False)
    print(f"  {len(salida)} pieces, {round(total/1024/1024, 1)} MB in ejemplos/vitrina")
    sin = [p["clave"] for p in salida if not p["meta"].get("prompt")]
    if sin:
        print("  no prompt stored in the PNG:", ", ".join(sin))


if __name__ == "__main__":
    if "--empacar" in sys.argv:
        empacar()
    else:
        empacar(generar())
