"""Build the showcase: what the app shows before you have made anything.

    .venv\\Scripts\\python.exe herramientas\\vitrina.py            (generate + pack)
    .venv\\Scripts\\python.exe herramientas\\vitrina.py --empacar   (pack only)

Thirty pieces in two groups. The first eighteen show what each path of the app
does, and where a path has a starting point they use that starting point rather
than a prompt written for the occasion, so what you see on opening is what you
get from pressing the button. The other twelve change the visual language
instead of the task -- pixel art, game key art, a sitcom still, riso, ink, a
patent drawing -- because the range is an argument the use cases cannot make.

Their prompts follow the order Qwen-Image's own guide recommends, subject
first, then style, detail, composition and light; the pixel-art ones also name
the scale and the palette, which is what the pixel-art guides ask for. None of
them names a trademark or reproduces anyone's character: what is asked for is
the visual language, not somebody else's property.

Five of them build on each other on purpose: a character is invented from a
paragraph, that face is carried into a portrait, a scene and a cutout, and two
of the earlier images are then edited. The chain is the argument -- this is one
tool, not eight unrelated demos.

The recipe is never retyped. It is read back out of the tEXt chunk of the PNG
the app wrote, which is the same place the gallery reads it from, so the
showcase cannot drift from what the app actually did. The pieces are saved as
JPEG at 1100px: thirty PNGs would be seventy megabytes of repository for
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
# Anything that ships as an example is generated well above the app's own
# default: at 12 steps the fine detail is still soft, and a showcase piece
# that undersells the model is worse than an empty column. Do not lower it.
PASOS = 30
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

# key -> what to ask the app for, and how it is presented afterwards.
#   titulo  the name on the card
#   caso    the interface path it belongs to
#   que     the sentence explaining what was done, on the card and under the
#           thumbnail
#   grupo   en cual de las dos rejillas aparece
CAMINOS = "What each path does"
ESTILOS = "How far the style stretches"

PIEZAS: list[dict] = [
    # --- the chain: an invented person and everything done with them -------
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

    # --- what this model does better than most -----------------------------
    {"clave": "cartel", "titulo": "Poster", "caso": "sign", "ratio": "3:4", "seed": 3109,
     "prompt": base("sign", "Poster"),
     "que": "Words inside double quotes come out as lettering. This is the thing this "
            "model does better than most of its size."},

    {"clave": "neon", "titulo": "Neon sign", "caso": "sign", "ratio": "3:2", "seed": 3110,
     "prompt": base("sign", "Neon"),
     "que": "The same mechanism at night: the glow and the spelling are asked for in one "
            "sentence."},

    # --- the three edits, over pictures from this same showcase -------------
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

    # --- the same text to image, but changing visual language rather than ---
    # the task. The prompts follow the structure published by
    # la guia de Qwen-Image (sujeto primero, luego estilo, detalle, encuadre y
    # luz) y, en pixel art, las convenciones de Civitai: nombrar la escala,
    # naming the palette and naming the view.
    {"clave": "pixel", "titulo": "Pixel art", "caso": "blank", "grupo": ESTILOS,
     "ratio": "3:2", "seed": 7101,
     "prompt": "Pixel art of a hooded traveller standing at the mouth of a moss-covered "
               "stone shrine, 16-bit style, limited palette of mossy green, slate grey "
               "and torchlight amber, visible square pixels and dithered shading, clean "
               "edges, side view, game asset style.",
     "que": "Asked for the way the pixel-art guides ask for it: name the era, name the "
            "palette, name the view. The dithering is in the prompt, not a filter."},

    {"clave": "isometrico", "titulo": "Isometric tiles", "caso": "blank", "grupo": ESTILOS,
     "ratio": "1:1", "seed": 7102,
     "prompt": "Isometric pixel art of a small harbour town with tiled roofs, a "
               "lighthouse and fishing boats, 32x32 tile style, limited seaside palette "
               "of terracotta, sea green and sand, crisp square pixels, top-down "
               "isometric view, game map style.",
     "que": "The same technique at another scale and projection. Holding the grid across "
            "a whole town is the hard part, and it holds."},

    {"clave": "concepto", "titulo": "Game key art", "caso": "blank", "grupo": ESTILOS,
     "ratio": "16:9", "seed": 7103,
     "prompt": "Painted key art for an adventure game, a lone figure on a cliff path "
               "looking down at a valley of ruins and low cloud, digital matte painting, "
               "broad confident brushwork, cool blue valley against a warm sky, wide "
               "cinematic composition with the figure small in the lower third, late "
               "afternoon light.",
     "que": "Concept art rather than a photograph. The brief asks for brushwork and for "
            "the figure to be small in frame, and both survive."},

    {"clave": "lowpoly", "titulo": "Low-poly render", "caso": "blank", "grupo": ESTILOS,
     "ratio": "3:2", "seed": 7204,
     "prompt": "Low-poly 3D render of a roadside diner at night, late-1990s console "
               "aesthetic, visible flat polygons and low-resolution textures, vertex "
               "lighting with hard colour banding, the word \"DINER\" glowing in red "
               "neon above the door, three-quarter view, deep blue night sky.",
     "que": "A deliberately crude look is harder than a polished one, because the model "
            "has to hold back. The sign is spelled because the word was given in quotes "
            "\u2014 the first take invented letters and got them wrong."},

    {"clave": "sitcom", "titulo": "Sitcom still", "caso": "blank", "grupo": ESTILOS,
     "ratio": "4:3", "seed": 7105,
     "prompt": "Film still from a 1990s multi-camera sitcom, four friends laughing "
               "around a worn orange couch in a warm apartment living room, brick wall "
               "and fairy lights behind them, flat bright three-point studio lighting "
               "with soft shadows, 4:3 television framing, slight video grain.",
     "que": "The look of a decade rather than of any particular show: flat studio light, "
            "4:3 framing and video grain are what the eye actually recognises."},

    {"clave": "cine", "titulo": "Cinematic still", "caso": "blank", "grupo": ESTILOS,
     "ratio": "16:9", "seed": 7106,
     "prompt": "Cinematic film still of a woman in a rain-soaked phone booth at night, "
               "anamorphic widescreen, shallow focus with oval bokeh from the street "
               "behind, teal shadows and warm sodium highlights, subject framed "
               "off-centre to the right, hard rim light through the glass.",
     "que": "Anamorphic is a shape and a bokeh, not a filter. Naming the oval bokeh and "
            "the off-centre framing is what makes it read as cinema."},

    {"clave": "anime", "titulo": "Anime key visual", "caso": "blank", "grupo": ESTILOS,
     "ratio": "3:4", "seed": 7107,
     "prompt": "Anime key visual of a student standing on a railway overbridge at dusk, "
               "modern television animation style, clean cel shading with hard shadow "
               "edges, saturated sunset gradient behind, wind in the hair, centred "
               "three-quarter framing, lens flare along the rails.",
     "que": "Cel shading means hard shadow edges. Saying so is what stops it drifting "
            "into a painting."},

    {"clave": "comic", "titulo": "Comic panel", "caso": "blank", "grupo": ESTILOS,
     "ratio": "3:4", "seed": 7108,
     "prompt": "Comic book panel of a detective pushing open an office door, American "
               "comics ink style, heavy black spotting and cross-hatching, visible "
               "halftone dots in the flat colour, bold panel border, low angle looking "
               "up, harsh light from the corridor behind.",
     "que": "Halftone dots and ink spotting are printing artefacts. Named explicitly, the "
            "model reproduces the process and not just the drawing."},

    {"clave": "acuarela", "titulo": "Watercolour", "caso": "blank", "grupo": ESTILOS,
     "ratio": "1:1", "seed": 7109,
     "prompt": "Watercolour botanical study of three sprigs of rosemary and a split fig, "
               "loose wet-on-wet washes with visible paper grain and pigment blooms, "
               "muted sage and dusty pink, arranged with generous white space around "
               "them, even north light.",
     "que": "The prompt describes what the medium does physically \u2014 blooms, paper "
            "grain \u2014 instead of asking for a watercolour and hoping."},

    {"clave": "riso", "titulo": "Risograph poster", "caso": "sign", "grupo": ESTILOS,
     "ratio": "3:4", "seed": 7110,
     "prompt": "Risograph poster for a jazz night, two spot colours only, fluorescent "
               "pink and deep blue overprinted with visible misregistration and paper "
               "texture, bold geometric shapes of a double bass, the words \"LATE SET\" "
               "set large in condensed type across the lower third, flat even "
               "reproduction.",
     "que": "Two inks, deliberate misregistration, and lettering that still has to come "
            "out spelled. A printing fault turned into a style."},

    {"clave": "arcilla_stop", "titulo": "Stop-motion still", "caso": "blank", "grupo": ESTILOS,
     "ratio": "3:2", "seed": 7111,
     "prompt": "Stop-motion still of a small felt fox in a knitted scarf standing on a "
               "miniature wooden bridge, handmade puppet with visible clay fingerprints "
               "and fabric fibres, shallow macro focus on the face, warm practical "
               "lantern light from the left, shot on a miniature set.",
     "que": "Fingerprints and fibres are the whole trick: they say handmade object under "
            "a real light, not a rendered character."},

    {"clave": "plano", "titulo": "Patent drawing", "caso": "blank", "grupo": ESTILOS,
     "ratio": "4:3", "seed": 7112,
     "prompt": "Technical patent drawing of a hand-cranked coffee grinder, black ink line "
               "work on aged cream paper, cross-section with numbered callouts and dashed "
               "hidden edges, orthographic front and side views side by side, flat even "
               "reproduction with no shading.",
     "que": "Orthographic, no shading, numbered callouts. A drawing whose job is to be "
            "read rather than admired \u2014 a different discipline entirely."},
    {"clave": "restyle", "titulo": "Match a style", "caso": "restyle", "grupo": CAMINOS,
     "seed": 6105, "fuente": "retrato", "endpoint": "/api/estilo",
     "ref_estilo": "acuarela",
     "que": "The portrait remade in the manner of the watercolour below it — same "
            "person, same pose, same framing, a different medium. The reference is "
            "never passed to the generator as a picture: it is read first, and only "
            "the description of how it is made travels, because handing the model the "
            "painting hands it the rosemary and the fig as well."},
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


def generar(solo: set[str] | None = None) -> dict:
    """Run every piece through the app. Returns clave -> file it produced.

    With `solo`, only those are regenerated and the rest are taken from the
    last run: adding one piece should not cost thirty generations. A piece
    another one is built on has to exist already, which it does whenever the
    whole set has been run once.
    """
    hechas: dict[str, str] = {}
    if solo and os.path.exists(REGISTRO):
        with open(REGISTRO, encoding="utf-8") as f:
            hechas = {k: os.path.join(SALIDAS, v) for k, v in json.load(f).items()}

    for p in PIEZAS:
        if solo and p["clave"] not in solo:
            continue
        t0 = time.time()
        fuente = p.get("fuente")
        if fuente:                                   # una edicion
            carga = {"imagen": _data_url(hechas[fuente]),
                     "steps": PASOS, "seed": p["seed"], "variantes": 1,
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
            if p.get("ref_estilo"):
                carga["estilo"] = _data_url(hechas[p["ref_estilo"]])
            r = _pedir(p["endpoint"], carga)
        else:                                        # una generacion
            carga = {"prompt": p["prompt"], "steps": PASOS, "seed": p["seed"],
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
            # a transparency checkerboard tells the truth where flat white
            # would pass an alpha PNG off as an ordinary photograph
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
                 "grupo": p.get("grupo", CAMINOS),
                 "que": p["que"], "archivo": "/vitrina/" + jpg, "meta": _receta(png)}
        if p.get("fuente"):
            # the source photograph is another showcase piece: it is pointed
            # at rather than duplicated, and that also says one thing was made
            # on top of the other
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
    elif "--solo" in sys.argv:
        claves = {x for x in sys.argv[sys.argv.index("--solo") + 1].split(",") if x}
        faltan = claves - {p["clave"] for p in PIEZAS}
        if faltan:
            raise SystemExit("  no such pieces: " + ", ".join(sorted(faltan)))
        empacar(generar(claves))
    else:
        empacar(generar())
