"""Effects gallery: a look you pick from thumbnails instead of typing.

Every entry is an edit applied to the image you already have, so composition,
framing and identity stay put and only the treatment changes. Two kinds:

  - prompt-only, which need nothing but words and work on any install;
  - LoRA-backed, which need a .safetensors in loras/ and say so, staying out
    of the gallery when the file is not there rather than failing on click.

The thumbnails are generated from whatever reference the install ships, by
`herramientas/generar_efectos.py`, so what you see in the grid is this model
doing this effect rather than a stock image from somewhere else.

The wording follows what was measured elsewhere in this project: say what
should be there, never what should not, and keep the verb imperative. An
effect that says "keep the composition" holds it; one that says "do not change
the composition" reliably changes it.
"""

from __future__ import annotations

import os

DIR = os.path.dirname(os.path.abspath(__file__))
MINIATURAS = os.path.join(DIR, "..", "ejemplos", "efectos")

# id -> (nombre, grupo, prompt, lora o None)
EFECTOS: dict[str, dict] = {
    "bw": {
        "nombre": "Black and white",
        "grupo": "Grade",
        "prompt": "Convert this photograph to black and white with deep true blacks and a "
                  "bright specular highlight, the contrast printed hard, visible film grain. "
                  "The composition, the framing, the pose and the face stay exactly as they "
                  "are.",
    },
    "golden": {
        "nombre": "Golden hour",
        "grupo": "Light",
        "prompt": "Relight this photograph as if it were taken twenty minutes before sunset: "
                  "warm low sun raking in from one side, a golden rim along the hair and the "
                  "shoulders, long soft shadows, the shadows holding a little blue. The "
                  "composition, the framing, the pose and the face stay exactly as they are.",
    },
    "cine": {
        "nombre": "Cinematic",
        "grupo": "Grade",
        "prompt": "Grade this photograph for cinema: teal holding the shadows, warm skin "
                  "kept clean, the highlights rolling off rather than clipping, a slight "
                  "halation around the brightest edges. The composition, the framing, the "
                  "pose and the face stay exactly as they are.",
    },
    "film": {
        "nombre": "35mm film",
        "grupo": "Grade",
        "prompt": "Render this photograph as if shot on 35mm colour negative film: fine "
                  "grain across the frame, the blacks lifted slightly, the colour a touch "
                  "muted and the highlights soft. The composition, the framing, the pose and "
                  "the face stay exactly as they are.",
    },
    "cross": {
        "nombre": "Cross process",
        "grupo": "Grade",
        "prompt": "Grade this photograph as a cross-processed slide: cyan pushed into the "
                  "shadows, yellow into the highlights, the contrast hard and the colour "
                  "shifted away from natural. The composition, the framing, the pose and the "
                  "face stay exactly as they are.",
    },
    "studio": {
        "nombre": "Studio relight",
        "grupo": "Light",
        "prompt": "Relight this photograph with studio strobes: a hard key at forty-five "
                  "degrees carving the face, a soft fill on the shadow side, and a rim "
                  "separating the subject from the background. The composition, the framing, "
                  "the pose and the face stay exactly as they are.",
    },
    "noir": {
        "nombre": "Low key",
        "grupo": "Light",
        # medido: pedir "la mayor parte del cuadro en sombra" se lo toma al pie de
        # la letra y devuelve una foto negra. El encargo tiene que ser lo que SI
        # se ve -- la cara bien expuesta -- y el resto cae solo
        "prompt": "Relight this photograph as low-key noir. The face is the brightest "
                  "thing in the frame, well exposed and fully readable, lit by a single "
                  "hard source from one side that carves a bright edge along the cheekbone "
                  "and the jaw. Everything behind the subject sits far darker than the "
                  "face. The composition, the framing, the pose and the face stay exactly "
                  "as they are.",
    },
    # --------------------------------------------------------- redibujar
    # Estos seis salen de lo que TostUI expone como casos propios. No llevan
    # pesos: son encargos, y por eso cuestan lo que cuesta escribirlos.
    #
    # Ojo con la clausula final. En los de grado se dice que la cara se queda
    # "exactamente como esta" porque solo cambia el tratamiento; aqui cambia la
    # manera de dibujar, asi que pedir eso a la vez se contradice y el modelo
    # resuelve la contradiccion no haciendo nada. Se nombra lo que de verdad se
    # conserva -- quien es, la pose, el encuadre -- y se deja libre el resto.
    "anime": {
        "nombre": "Anime",
        "grupo": "Redraw",
        "prompt": "Redraw this photograph as a frame of modern television anime: clean "
                  "cel shading with hard shadow edges, flat saturated colour, crisp ink "
                  "outlines, and simplified features that still read as the same person. "
                  "The same person, the same pose, the same composition and the same "
                  "framing. Nothing of the photographic surface remains.",
    },
    "realismo": {
        "nombre": "Photographic",
        "grupo": "Redraw",
        "miniatura_desde": "ejemplos/vitrina/anime.jpg",
        "prompt": "Redraw this picture as a photograph taken on a full-frame camera: real "
                  "skin with pores and fine stray hairs, fabric with a visible weave, "
                  "depth of field that falls off behind the subject, and light that "
                  "behaves physically. The same subject, the same pose, the same "
                  "composition and the same framing, made photographically.",
    },
    "chibi": {
        "nombre": "Chibi",
        "grupo": "Redraw",
        # la proporcion es el efecto entero, asi que aqui la composicion SI
        # cambia: se nombra lo que se reconoce (ropa, pose, color de pelo) y no
        # el encuadre, que es lo que en los otros se protege
        "prompt": "Redraw the subject as a chibi character: the head about a third of the "
                  "whole figure, large simplified eyes, a small rounded body and hands, "
                  "clean cel shading and flat bright colour on a simple background. The "
                  "same clothing, the same hair and the same pose, so the person is still "
                  "recognisable.",
    },
    # ------------------------------------------------------------ reparar
    "nitidez": {
        "nombre": "Deblur",
        "grupo": "Repair",
        "miniatura_danar": "desenfoque",
        "prompt": "Redraw this photograph in focus: the subject sharp, the eyes crisp, "
                  "the hair separated into individual strands and the weave of the fabric "
                  "resolved. The composition, the framing, the pose and the face stay "
                  "exactly as they are.",
    },
    "detalle": {
        "nombre": "More detail",
        "grupo": "Repair",
        "miniatura_danar": "resolucion",
        "prompt": "Redraw this photograph with the detail a larger negative would hold: "
                  "eyelashes and single hairs, pores and fine skin texture, clean edges "
                  "on every object and the grain of the materials. The composition, the "
                  "framing, the pose and the face stay exactly as they are.",
    },
    "ventana": {
        "nombre": "Window light",
        "grupo": "Light",
        "prompt": "Relight this photograph with soft daylight from a large window to one "
                  "side: a gentle gradient across the face, open shadows that keep their "
                  "detail, and a cool cast on the shadow side. The composition, the "
                  "framing, the pose and the face stay exactly as they are.",
    },
    "clay": {
        "nombre": "Clay render",
        "grupo": "3D viewport",
        "prompt": "Turn the image into a clay render.",
        "lora": "QI_2.1_BlenderPack.safetensors",
        "fuerza": 1.0,
    },
    "material": {
        "nombre": "Material preview",
        "grupo": "3D viewport",
        "prompt": "Turn the image into a material preview render.",
        "lora": "QI_2.1_BlenderPack.safetensors",
        "fuerza": 1.0,
    },
    "workbench": {
        "nombre": "Workbench",
        "grupo": "3D viewport",
        "prompt": "Turn the image into a workbench render.",
        "lora": "QI_2.1_BlenderPack.safetensors",
        "fuerza": 1.0,
    },
}


def catalogo(dir_loras: str) -> list[dict]:
    """The gallery, with each entry saying whether it can actually run.

    A LoRA-backed effect whose file is missing is reported rather than hidden:
    "this exists and you need that file" is more useful than a gap.
    """
    fuera = []
    for k, e in EFECTOS.items():
        lora = e.get("lora")
        listo = True if not lora else os.path.exists(os.path.join(dir_loras, lora))
        thumb = os.path.join(MINIATURAS, f"{k}.jpg")
        fuera.append({
            "id": k,
            "nombre": e["nombre"],
            "grupo": e["grupo"],
            "prompt": e["prompt"],
            "lora": lora,
            "fuerza": e.get("fuerza", 1.0),
            "listo": listo,
            # only the thumbnail generator reads these; the grid ignores them
            "miniatura_desde": e.get("miniatura_desde"),
            "miniatura_danar": e.get("miniatura_danar"),
            "thumb": f"/efectos/{k}.jpg" if os.path.exists(thumb) else None,
        })
    fuera.sort(key=lambda x: (x["grupo"], x["nombre"]))
    return fuera


def buscar(id_: str) -> dict | None:
    return EFECTOS.get(id_)
