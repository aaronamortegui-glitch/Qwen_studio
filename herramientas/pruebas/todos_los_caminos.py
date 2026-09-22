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
SALIDAS = r"D:\QwenStudio\salidas"
PERSONA = r"D:\AIToolkit\AI-Toolkit\datasets\eliana_qwen21\Eliohwx_03.jpg"
ESCENA = r"D:\ComfyUI_QI21\ComfyUI_windows_portable\ComfyUI\input\escena_cocina.png"
ESTILO = r"D:\ComfyUI_QI21\ComfyUI_windows_portable\ComfyUI\input\escena_playa.png"


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


def dimensiones(url_rel: str) -> tuple[int, int]:
    from PIL import Image
    return Image.open(os.path.join(SALIDAS, os.path.basename(url_rel))).size


def juzgar(url_rel: str, esperado: list[str]) -> str:
    """Pregunta al VLM que ve y exige que aparezca lo que el prompt encargo.

    Un caso puede devolver una imagen del tamano correcto y aun asi haber
    ignorado la instruccion; eso es lo que esto detecta. Basta una de las
    palabras: son sinonimos de lo mismo, no una lista de requisitos.
    """
    ruta = os.path.join(SALIDAS, os.path.basename(url_rel))
    r = pedir("/api/describir", {"imagen": data_url(ruta), "tarea": "describe"}, timeout=900)
    assert not r.get("error"), r.get("error")
    visto = r["texto"].lower()
    assert any(p in visto for p in esperado), \
        f"the prompt asked for {esperado} and the model saw: {visto[:150]}"
    return visto


def modo(url_rel: str) -> str:
    from PIL import Image
    return Image.open(os.path.join(SALIDAS, os.path.basename(url_rel))).mode


def alfa_real(url_rel: str) -> float:
    from PIL import Image
    im = Image.open(os.path.join(SALIDAS, os.path.basename(url_rel)))
    if im.mode != "RGBA":
        return 0.0
    px = list(im.getchannel("A").getdata())
    return sum(1 for v in px if v < 16) / len(px)


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
    # Se le cambia el color a la prenda en vez de cambiarla por otra, a
    # proposito. Recortar y recoser sirve para un cambio local; sustituir una
    # prenda que se sale del recorte deja sus mangas a la vista como contexto y
    # el modelo armoniza con ellas -- la limitacion que documenta el README.
    # Probar eso aqui no medía el recosido, medía el fallo conocido.
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

    # Y medido, no solo leido. Buscar la palabra "yellow" en la descripcion era
    # demasiado fragil: la mascara afinada deja el pelo fuera, y entre las hebras
    # asoman unas pocas hebras del color viejo que bastan para que el VLM lo
    # nombre aunque la prenda entera haya cambiado. Se cuenta cuanto amarillo
    # fuerte queda frente al que habia.
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

    # dentro tiene que haber cambiado
    dentro = ImageChops.difference(src.crop(caja), out.crop(caja))
    assert max(dentro.convert("L").getextrema()) > 40, "the painted region came back unchanged"

    # y arriba, lejos del recorte y de su difuminado, tiene que ser la misma foto
    alto = (0, 0, src.width, int(src.height * .35))
    fuera = ImageChops.difference(src.crop(alto), out.crop(alto)).convert("L")
    peor = fuera.getextrema()[1]
    assert peor <= 8, f"the untouched area moved by {peor} levels"
    return f"inside changed, outside within {peor} levels"


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


CASOS = [
    ("status", caso_estado), ("catalogues", caso_catalogos),
    ("new portrait", caso_retrato), ("aspect ratio 16:9", caso_ratio),
    ("character in a scene", caso_escena), ("pose from library", caso_pose),
    ("style reference", caso_estilo), ("transparent cutout", caso_transparencia),
    ("mask preview", caso_mascara), ("inpaint", caso_inpaint),
    ("inpaint by brush", caso_pincel),
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
