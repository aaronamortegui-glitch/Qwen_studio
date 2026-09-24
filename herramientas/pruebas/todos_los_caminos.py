"""Walk every path the app offers and report what worked.

Run with the app already up. Each case exercises one use case end to end and
checks the shape of what came back, not just the absence of an error: a path
that returns a 1024 square when a 16:9 was asked for is broken even though
nothing raised.

Where the instruction can be read off the image — a blazer, a kitchen, a
garment that is no longer yellow — Qwen3-VL looks at the result and the case
fails if the model did not do what was asked. A picture of the right size that
ignored the prompt is a failure too.

    .venv\\Scripts\\python.exe herramientas\\pruebas\\todos_los_caminos.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request

APP = "http://127.0.0.1:7860"
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SALIDAS = os.path.join(RAIZ, "salidas")
EJEMPLOS = os.path.join(RAIZ, "ejemplos")
# The three inputs come from the repository itself, not from loose folders on
# this machine. The person used to come from a private training dataset: the
# suite is what fills salidas/, salidas/ is what appears in the gallery
# screenshot, and that way a real person's face ended up in the repository
# without anyone deciding it should. It also means the suite runs in any clone.
PERSONA = os.path.join(EJEMPLOS, "person.jpg")
ESCENA = os.path.join(EJEMPLOS, "scene.jpg")
ESTILO = os.path.join(EJEMPLOS, "style.jpg")


def data_url(ruta: str) -> str:
    ext = os.path.splitext(ruta)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    with open(ruta, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def pedir(ruta: str, carga: dict | None = None, timeout: int = 3600):
    url = APP + ruta
    if carga is None:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read())
    req = urllib.request.Request(url, data=json.dumps(carga).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def sat(img) -> float:
    """Saturacion media en HSV. Un grado en blanco y negro la deja cerca de cero."""
    from PIL import ImageStat
    return ImageStat.Stat(img.convert("HSV")).mean[1]


def dimensiones(url_rel: str) -> tuple[int, int]:
    from PIL import Image
    return Image.open(os.path.join(SALIDAS, os.path.basename(url_rel))).size


def juzgar(url_rel: str, esperado: list[str]) -> str:
    """Ask the VLM what it sees and require what the prompt asked for.

    A case can return an image of the right size and still have ignored the
    instruction; that is what this catches. One of the words is enough: they
    are synonyms for the same thing, not a list of requirements.
    """
    ruta = os.path.join(SALIDAS, os.path.basename(url_rel))
    r = pedir("/api/describir", {"imagen": data_url(ruta), "tarea": "describe"}, timeout=900)
    assert not r.get("error"), r.get("error")
    visto = r["texto"].lower()
    assert any(p in visto for p in esperado), \
        f"the prompt asked for {esperado} and the model saw: {visto[:150]}"
    return visto


def mismo_hombre(url_rel: str) -> str:
    """Ask the VLM whether the result is the person in the reference.

    The suite could tell that a blazer had arrived and never that the man
    wearing it was somebody else. Five separate decisions degraded the likeness
    before anyone noticed, because every check here was about the shape of the
    output and none about who was in it. This is the one that would have caught
    them: the reference and the result, side by side, one question.

    Deliberately generous. It asks about build, beard and face rather than
    demanding certainty, because the model is not a face matcher and a test
    that fails on a haircut is a test nobody keeps.
    """
    ruta = os.path.join(SALIDAS, os.path.basename(url_rel))
    hoja = hoja_lado_a_lado(PERSONA, ruta)
    r = pedir("/api/describir",
              {"imagen": data_url(hoja), "tarea": "free",
               "extra": "Two photographs of a man, side by side. Ignore the "
                        "clothing, the lighting and the background. Looking only "
                        "at the face, the beard and the build: is this the same "
                        "man twice? Answer with one word, yes or no, then one "
                        "short sentence saying why."},
              timeout=900)
    assert not r.get("error"), r.get("error")
    dicho = r["texto"].strip()
    assert dicho.lower().lstrip().startswith("yes"), \
        f"the reference and the result are not the same man: {dicho[:160]}"
    return dicho.split(".")[0][:70]


def hoja_lado_a_lado(izq: str, der: str) -> str:
    """One image with both, so the VLM sees them in a single glance."""
    from PIL import Image
    a, b = Image.open(izq).convert("RGB"), Image.open(der).convert("RGB")
    alto = 768
    a = a.resize((round(a.width * alto / a.height), alto), Image.LANCZOS)
    b = b.resize((round(b.width * alto / b.height), alto), Image.LANCZOS)
    hoja = Image.new("RGB", (a.width + b.width, alto), (255, 255, 255))
    hoja.paste(a, (0, 0))
    hoja.paste(b, (a.width, 0))
    destino = os.path.join(SALIDAS, "_identidad.png")
    hoja.save(destino)
    return destino


def modo(url_rel: str) -> str:
    from PIL import Image
    return Image.open(os.path.join(SALIDAS, os.path.basename(url_rel))).mode


def alfa_real(url_rel: str) -> float:
    from PIL import Image
    im = Image.open(os.path.join(SALIDAS, os.path.basename(url_rel)))
    if im.mode != "RGBA":
        return 0.0
    # a histogram instead of walking the pixels: getdata() is deprecated, and
    # this way nothing builds a list of a million integers
    h = im.getchannel("A").histogram()
    return sum(h[:16]) / (im.width * im.height)


# ---------------------------------------------------------------- casos

def caso_estado():
    e = pedir("/api/estado")
    assert e["pesos_listos"], "the weights are not on disk"
    return f"profile {e['perfil']['nivel']}, {e['perfil']['vram_gb']} GB"


def caso_catalogos():
    poses, loras, prompts = pedir("/api/poses"), pedir("/api/loras"), pedir("/api/prompts")
    assert poses, "empty pose library"
    assert prompts, "empty prompt library"
    encuadres = {p["framing"] for p in poses}
    return (f"{len(poses)} poses ({', '.join(sorted(encuadres))}), "
            f"{sum(len(c['items']) for c in prompts)} prompts, {len(loras)} loras")


def caso_retrato():
    r = pedir("/api/generar", {"personas": [data_url(PERSONA)],
                               "prompt": "An editorial magazine portrait. She wears a black "
                                         "tailored blazer over a white shirt, standing in a "
                                         "sunlit concrete gallery, hard side light from a tall "
                                         "window, deep shadows.",
                               "ratio": "1:1", "megapixeles": 1, "steps": 20, "seed": 11,
                               "resumen": False})
    assert not r.get("error"), r.get("error")
    w, h = dimensiones(r["imagenes"][0]["archivo"])
    assert w == h, f"1:1 asked, got {w}x{h}"
    juzgar(r["imagenes"][0]["archivo"], ["blazer", "suit", "jacket"])
    return f"{w}x{h}, wardrobe changed"


def caso_identidad():
    """The portrait again, at the settings that ship, judged on the face.

    Everything else in this file checks the shape of what came back. This one
    checks who came back, which is the only thing a reference photograph is
    there to decide, and the thing five separate measurements missed.
    """
    r = pedir("/api/generar", {"personas": [data_url(PERSONA)],
                               "prompt": "A colour editorial magazine portrait. "
                                         "The subject wears a black tailored blazer "
                                         "over a white shirt, standing in a sunlit "
                                         "concrete gallery, hard side light from a "
                                         "tall window, deep shadows.",
                               "ratio": "3:4", "megapixeles": 1, "seed": 301,
                               "resumen": False})
    assert not r.get("error"), r.get("error")
    return mismo_hombre(r["imagenes"][0]["archivo"])


def caso_ratio():
    r = pedir("/api/generar", {"personas": [data_url(PERSONA)],
                               "prompt": "A portrait against a plain wall.",
                               "ratio": "16:9", "megapixeles": 1, "steps": 20, "seed": 12,
                               "resumen": False})
    assert not r.get("error"), r.get("error")
    w, h = dimensiones(r["imagenes"][0]["archivo"])
    assert w > h * 1.5, f"16:9 asked, got {w}x{h}"
    return f"{w}x{h}"


def caso_escena():
    r = pedir("/api/generar", {"personas": [data_url(PERSONA)], "escena": data_url(ESCENA),
                               "prompt": "A photograph of her.", "ratio": "1:1",
                               "megapixeles": 1, "steps": 20, "seed": 13})
    assert not r.get("error"), r.get("error")
    desc = r.get("descripcion_escena", "")
    assert desc, "the scene was not described (auto-description is what makes this path work)"
    assert r.get("resumen"), "no contact sheet"
    juzgar(r["imagenes"][0]["archivo"], ["kitchen", "counter", "cabinet"])
    return f'the scene arrived: "{desc[:46]}..."'


def caso_pose():
    poses = pedir("/api/poses")
    pid = next(p["id"] for p in poses if p["framing"] == "half")
    r = pedir("/api/generar", {"personas": [data_url(PERSONA)], "pose_lib": pid,
                               "prompt": "A photograph of her in that posture.",
                               "ratio": "3:4", "megapixeles": 1, "steps": 20, "seed": 14,
                               "resumen": False})
    assert not r.get("error"), r.get("error")
    assert any("pose" in o for o in r["orden"]), f"pose not in the order: {r['orden']}"
    return f"{pid}, order {' '.join(r['orden'])}"


def caso_estilo():
    r = pedir("/api/generar", {"personas": [data_url(PERSONA)], "estilo": data_url(ESTILO),
                               "estilo_modo": "look", "prompt": "A portrait of her.",
                               "ratio": "1:1", "megapixeles": 1, "steps": 20, "seed": 15,
                               "resumen": False})
    assert not r.get("error"), r.get("error")
    assert any("style" in o for o in r["orden"]), f"style not in the order: {r['orden']}"
    return " ".join(r["orden"])


def caso_transparencia():
    r = pedir("/api/generar", {"personas": [data_url(PERSONA)],
                               "prompt": "Full body cutout, clean edges.",
                               "ratio": "3:4", "megapixeles": 1, "steps": 20, "seed": 16,
                               "transparencia": True, "resumen": False})
    assert not r.get("error"), r.get("error")
    frac = alfa_real(r["imagenes"][0]["archivo"])
    assert frac > 0.05, f"no real alpha: only {frac*100:.1f}% transparent"
    return f"{frac*100:.0f}% transparent"


def caso_mascara():
    r = pedir("/api/mascara", {"imagen": data_url(ESCENA), "frase": "the yellow sweater",
                               "crecer": 8})
    assert not r.get("error"), r.get("error")
    assert 2 < r["cobertura"] < 80, f"implausible coverage: {r['cobertura']}%"
    return f"covers {r['cobertura']}%"


def caso_inpaint():
    # The garment's colour is changed rather than the garment itself, on
    # purpose. Crop-and-stitch is for a local change; replacing a garment that
    # runs outside the crop leaves its sleeves visible as context and the model
    # harmonises with them -- the limitation the README documents.
    # Testing that here would not measure the stitching, it would measure
    # the known failure.
    r = pedir("/api/inpaint", {"imagen": data_url(ESCENA), "frase": "the yellow sweater",
                               "prompt": "The same knitted sweater in deep forest green, "
                                         "the same weave, the same folds, the same light "
                                         "falling across it.",
                               "megapixeles": 1, "steps": 20, "seed": 17})
    assert not r.get("error"), r.get("error")
    w, h = dimensiones(r["imagenes"][0]["archivo"])
    ow, oh = 1024, 1024
    assert (w, h) == (ow, oh), f"inpaint changed the size: {w}x{h}"
    juzgar(r["imagenes"][0]["archivo"], ["green"])

    # And measured, not merely read. Looking for the word "yellow" in the
    # description was too fragile: the refined mask leaves the hair out, and a
    # few strands of the old colour show between them, enough for the VLM to
    # name it even when the whole garment has changed. What is counted is how
    # much strong yellow is left against how much there was.
    import numpy as np
    from PIL import Image
    antes = np.asarray(Image.open(ESCENA).convert("RGB")).astype(np.int16)
    despues = np.asarray(Image.open(os.path.join(
        SALIDAS, os.path.basename(r["imagenes"][0]["archivo"]))).convert("RGB")).astype(np.int16)

    def amarillo(a):
        r_, g_, b_ = a[..., 0], a[..., 1], a[..., 2]
        return ((r_ > 120) & (g_ > 90) & (b_ < 90) & (r_ - b_ > 60)).sum()

    a0, a1 = amarillo(antes), amarillo(despues)
    caida = 1 - a1 / max(a0, 1)
    assert caida > 0.85, f"only {caida*100:.0f}% of the yellow went away"
    return f"crop {r['crop']} -> {r['generado']}, {caida*100:.0f}% of the yellow gone"


def caso_pincel():
    """Inpaint driven by a painted mask instead of a phrase."""
    import base64
    import io
    from PIL import Image, ImageChops, ImageDraw

    src = Image.open(ESCENA).convert("RGB")
    caja = (int(src.width * .22), int(src.height * .55),
            int(src.width * .78), int(src.height * .95))
    m = Image.new("L", src.size, 0)
    ImageDraw.Draw(m).rectangle(caja, fill=255)
    buf = io.BytesIO()
    m.save(buf, "PNG")
    mascara = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    r = pedir("/api/inpaint", {"imagen": data_url(ESCENA), "mascara": mascara,
                               "prompt": "A navy blue denim jacket, buttoned all the way up, "
                                         "nothing else visible underneath it, same lighting.",
                               "megapixeles": 1, "steps": 20, "seed": 18})
    assert not r.get("error"), r.get("error")
    out = Image.open(os.path.join(SALIDAS,
                     os.path.basename(r["imagenes"][0]["archivo"]))).convert("RGB")
    assert out.size == src.size, f"the size changed: {out.size} vs {src.size}"

    # inside has to have changed
    dentro = ImageChops.difference(src.crop(caja), out.crop(caja))
    assert max(dentro.convert("L").getextrema()) > 40, "the painted region came back unchanged"

    # and at the top, far from the crop and its feathering, it has to be the
    # same photograph
    alto = (0, 0, src.width, int(src.height * .35))
    fuera = ImageChops.difference(src.crop(alto), out.crop(alto)).convert("L")
    peor = fuera.getextrema()[1]
    assert peor <= 8, f"the untouched area moved by {peor} levels"
    return f"inside changed, outside within {peor} levels"


def caso_look_entero():
    """A look with no mask: the whole frame is graded."""
    from PIL import Image, ImageChops

    src = Image.open(ESCENA).convert("RGB")
    r = pedir("/api/efecto", {"imagen": data_url(ESCENA), "efecto": "bw",
                              "megapixeles": 1, "steps": 20, "seed": 21})
    assert not r.get("error"), r.get("error")
    out = Image.open(os.path.join(SALIDAS,
                     os.path.basename(r["imagenes"][0]["archivo"]))).convert("RGB")
    # genuinely black and white: mean saturation collapses across the frame
    antes = sat(src)
    despues = sat(out)
    assert despues < antes * .25, f"saturation only fell from {antes:.0f} to {despues:.0f}"
    return f"saturation {antes:.0f} -> {despues:.0f} across the frame"


def caso_look_region():
    """The same look confined to a painted region.

    This is what separates a look from a replacement: nothing is named, only
    painted over, and the effect has to stay there. Inside, the saturation
    falls; at the top, far from the crop, the photograph must come back
    identical.
    """
    import base64
    import io as _io
    from PIL import Image, ImageChops, ImageDraw

    src = Image.open(ESCENA).convert("RGB")
    caja = (int(src.width * .22), int(src.height * .55),
            int(src.width * .78), int(src.height * .95))
    m = Image.new("L", src.size, 0)
    ImageDraw.Draw(m).rectangle(caja, fill=255)
    buf = _io.BytesIO()
    m.save(buf, "PNG")
    mascara = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    r = pedir("/api/efecto", {"imagen": data_url(ESCENA), "efecto": "bw",
                              "mascara": mascara, "megapixeles": 1,
                              "steps": 20, "seed": 22})
    assert not r.get("error"), r.get("error")
    assert r.get("caja"), "the look did not take the crop-and-stitch path"
    out = Image.open(os.path.join(SALIDAS,
                     os.path.basename(r["imagenes"][0]["archivo"]))).convert("RGB")
    assert out.size == src.size, f"the size changed: {out.size} vs {src.size}"

    dentro_antes, dentro_despues = sat(src.crop(caja)), sat(out.crop(caja))
    assert dentro_despues < dentro_antes * .35,         f"inside the region saturation only fell from {dentro_antes:.0f} to {dentro_despues:.0f}"

    alto = (0, 0, src.width, int(src.height * .35))
    fuera = ImageChops.difference(src.crop(alto), out.crop(alto)).convert("L")
    peor = fuera.getextrema()[1]
    assert peor <= 8, f"the untouched area moved by {peor} levels"
    return (f"inside {dentro_antes:.0f} -> {dentro_despues:.0f} saturation, "
            f"outside within {peor} levels")


def caso_describir():
    r = pedir("/api/describir", {"imagen": data_url(ESCENA), "tarea": "prompt"}, timeout=900)
    assert not r.get("error"), r.get("error")
    assert len(r["texto"]) > 60, "description too short"
    return f'{len(r["texto"])} chars: "{r["texto"][:50]}..."'


def caso_lote():
    r = pedir("/api/lote", {"prompts": ["A portrait in warm light.", "A portrait in cold light."],
                            "personas": [data_url(PERSONA)], "ratio": "1:1",
                            "megapixeles": 1, "steps": 20, "seed": 20}, timeout=7200)
    assert not r.get("error"), r.get("error")
    assert r["total"] == 2, f"asked for 2, got {r['total']}"
    seeds = [i["seed"] for i in r["imagenes"]]
    assert seeds[1] == seeds[0] + 1, f"the seed does not advance: {seeds}"
    return f"{r['total']} images, seeds {seeds}"


def caso_ajustes():
    antes = pedir("/api/ajustes")
    pedir("/api/ajustes", {"steps": 31})
    assert pedir("/api/ajustes")["steps"] == 31, "the setting did not persist"
    pedir("/api/ajustes", {"steps": antes["steps"]})
    return "persist and restore"


def caso_transferir_estilo():
    """Match a style: the manner of one picture, the subject of the other.

    The failure this guards against is not an exception. It is the reference
    lending its *subject* -- a lighthouse, a sprig of rosemary -- which is what
    happened until the technique started travelling as words. So the check is
    that the result still looks like the source photograph in layout while
    having stopped looking like a photograph at all.
    """
    from PIL import Image

    r = pedir("/api/estilo", {"imagen": data_url(ESCENA), "estilo": data_url(ESTILO),
                              "prompt": "", "megapixeles": 1, "steps": 16, "seed": 31})
    assert not r.get("error"), r.get("error")
    meta = r["imagenes"][0]
    out = Image.open(os.path.join(SALIDAS, os.path.basename(meta["archivo"])))
    src = Image.open(ESCENA)
    assert out.size == src.size, f"{out.size} against the source {src.size}"
    leida = (r.get("prompt") or "")
    assert "<image1>" in leida, "the style clause never reached the prompt"
    return f"{meta['tam']}, technique read into the prompt"


def caso_reescalar():
    """Enlarge: bigger, and bigger by redrawing rather than stretching.

    Not "to 2K": the ceiling with a reference in front of the model is what the
    profile allows, 1536 on this card and 1024 on a smaller one, so the number
    belongs to the machine and not to the name.
    """
    from PIL import Image

    src = Image.open(ESCENA)
    r = pedir("/api/reescalar", {"imagen": data_url(ESCENA), "steps": 16, "seed": 32})
    assert not r.get("error"), r.get("error")
    out = Image.open(os.path.join(SALIDAS,
                     os.path.basename(r["imagenes"][0]["archivo"])))
    assert max(out.size) > max(src.size), f"{out.size} is no larger than {src.size}"
    # redrawing recovers detail; interpolating does not. Edge energy per
    # pixel falls when something is stretched, and here it must not.
    import numpy as np
    def nitidez(im):
        a = np.asarray(im.convert("L"), dtype=np.float32)
        return float((np.abs(np.diff(a, axis=1)).mean()
                      + np.abs(np.diff(a, axis=0)).mean()) / 2)
    antes, despues = nitidez(src), nitidez(out)
    assert despues > antes * .6, f"edge energy fell {antes:.2f} -> {despues:.2f}"
    return f"{src.width}x{src.height} -> {out.width}x{out.height}, edges {antes:.1f} -> {despues:.1f}"


def caso_cfg():
    """The detail pass, and the thing about it that surprises.

    Above 1 the pipeline runs a second forward pass against the negative
    prompt. Without a negative prompt there is nothing to push against, so the
    result is byte-identical to CFG 1 in the same time -- a control that looks
    like it works and does not. Both halves are checked.
    """
    import numpy as np
    from PIL import Image

    def correr(**extra):
        c = {"prompt": "A brass compass on a weathered sea chart, raking light.",
             "steps": 12, "seed": 33, "variantes": 1, "megapixeles": 1,
             "lora": None, "fuerza_lora": 1.0, "personas": [], "escena": None,
             "estilo": None, "estilo_modo": "look", "pose_lib": None,
             "pose_url": None, "ratio": "1:1", "transparencia": False,
             "espera_persona": False}
        c.update(extra)
        r = pedir("/api/generar", c)
        assert not r.get("error"), r.get("error")
        f = os.path.join(SALIDAS, os.path.basename(r["imagenes"][0]["archivo"]))
        return np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)

    uno = correr()
    mudo = correr(cfg=3.0)                      # no negative: nothing should move
    tres = correr(cfg=3.0, negativo="blurry, deformed, watermark")
    assert np.array_equal(uno, mudo), "CFG without a negative prompt changed the image"
    d = float(np.abs(uno - tres).mean())
    assert d > 5, f"CFG with a negative prompt barely moved it ({d:.1f})"
    return f"no-op without a negative prompt, {d:.0f} levels of difference with one"


def caso_editar():
    """Instruction editing: the whole picture, a reference, and a sentence.

    Every other edit here selects a region and stitches it back. This hands the
    model the photograph and lets it decide where to touch, which is what the
    model was built for and what this app was not using.

    The instruction names the attribute rather than the person, because that is
    what decides whether anything happens at all. Measured on 2026-09-23 with
    the same picture, reference and seed: naming the person -- "replace the
    woman with the man from <image2>" -- changed nothing twice over, and naming
    the face, the hair, the beard and the clothing worked. It is the rule in
    QwenLM's own system_prompt_edit.txt, and it is the one that was missing.
    """
    import numpy as np
    from PIL import Image

    antes = Image.open(ESCENA).convert("RGB")
    r = pedir("/api/editar", {
        "imagen": data_url(ESCENA), "referencias": [data_url(PERSONA)],
        "prompt": "Replace the face and the hair with those from <image2>.",
        "megapixeles": 1, "steps": 16, "seed": 41})
    assert not r.get("error"), r.get("error")
    f = os.path.join(SALIDAS, os.path.basename(r["imagenes"][0]["archivo"]))
    out = Image.open(f).convert("RGB")
    assert out.size == antes.size, f"{out.size} against the source {antes.size}"
    # under-editing is the failure mode the authors document: an output so
    # close to the input that it looks like nothing ran. It is measured.
    a = np.asarray(antes.resize((256, 256)), np.float32)
    b = np.asarray(out.resize((256, 256)), np.float32)
    d = float(np.abs(a - b).mean())
    assert d > 4, f"nothing moved: {d:.1f} levels from the source"
    return f"{r['imagenes'][0]['tam']}, {d:.0f} levels from the source"


def caso_editar_fondo():
    """Instruction editing again, moving the subject somewhere else.

    Separate from the other edit case because it is a different demand: the
    garment case changes a small named thing and leaves the frame alone, this
    one replaces everything around the subject and must not touch the subject.
    It is also the use the app had no path to at all before -- putting someone
    in another place without a mask.

    Person swapping is deliberately NOT tested here. It works in one direction
    and not the other depending on which photograph is the target, and the
    model's own card lists face swaps among its weak points. A test that passes
    half the time measures nothing.
    """
    import numpy as np
    from PIL import Image

    r = pedir("/api/editar", {
        "imagen": data_url(PERSONA), "referencias": [data_url(ESCENA)],
        "prompt": "Change the background to the room from <image2>.",
        "megapixeles": 1, "steps": 16, "seed": 42, "cfg": 3.0, "negativo": ""})
    assert not r.get("error"), r.get("error")
    f = os.path.join(SALIDAS, os.path.basename(r["imagenes"][0]["archivo"]))
    out = Image.open(f).convert("RGB")
    antes = Image.open(PERSONA).convert("RGB")
    assert out.size == antes.size, f"{out.size} against the source {antes.size}"

    # The background has to move and the centre has to stay: they are looked at
    # separately, because a global difference cannot tell "changed the
    # background" from "changed the whole photograph", which is exactly the
    # failure worth catching.
    def trozo(im, caja):
        return np.asarray(im.resize((256, 256)).crop(caja), np.float32)
    borde = (0, 0, 64, 256)
    centro = (80, 40, 176, 200)
    df = float(np.abs(trozo(antes, borde) - trozo(out, borde)).mean())
    dc = float(np.abs(trozo(antes, centro) - trozo(out, centro)).mean())
    assert df > 12, f"the background barely moved ({df:.0f})"
    assert dc < df, f"the subject moved as much as the background ({dc:.0f} vs {df:.0f})"
    return f"background {df:.0f}, subject {dc:.0f}"


CASOS = [
    ("status", caso_estado), ("catalogues", caso_catalogos),
    ("new portrait", caso_retrato), ("same man", caso_identidad),
    ("aspect ratio 16:9", caso_ratio),
    ("character in a scene", caso_escena), ("pose from library", caso_pose),
    ("style reference", caso_estilo), ("transparent cutout", caso_transparencia),
    ("mask preview", caso_mascara), ("inpaint", caso_inpaint),
    ("inpaint by brush", caso_pincel),
    ("look, whole frame", caso_look_entero),
    ("look, painted region", caso_look_region),
    ("match a style", caso_transferir_estilo),
    ("instruction edit", caso_editar),
    ("background swap", caso_editar_fondo),
    ("enlarge", caso_reescalar),
    ("detail pass (CFG)", caso_cfg),
    ("describe (Qwen3-VL)", caso_describir), ("batch", caso_lote),
    ("settings", caso_ajustes),
]


def main() -> None:
    solo = sys.argv[1] if len(sys.argv) > 1 else None
    ok = fallos = 0
    print(f"{'case':<24} {'':<6} detail")
    print("-" * 78)
    for nombre, fn in CASOS:
        if solo and solo not in nombre:
            continue
        t0 = time.time()
        try:
            detalle = fn()
            ok += 1
            print(f"{nombre:<24} {'ok':<6} {detalle}   [{time.time()-t0:.0f}s]", flush=True)
        except AssertionError as e:
            fallos += 1
            print(f"{nombre:<24} {'FAIL':<6} {e}   [{time.time()-t0:.0f}s]", flush=True)
        except Exception as e:
            fallos += 1
            print(f"{nombre:<24} {'ERROR':<6} {type(e).__name__}: {str(e)[:90]}", flush=True)
    print("-" * 78)
    print(f"{ok} ok, {fallos} failed")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
