"""Render one thumbnail per effect, from this install's own reference photo.

    .venv\\Scripts\\python.exe herramientas\\generar_efectos.py [base.jpg]

A gallery of looks is only useful if the thumbnails are this model doing this
effect. A stock image from somewhere else shows you what someone else's
pipeline produced, which is exactly the thing you are trying to find out about.

`--solo id,id` rebuilds only a few: adding one effect should not cost a
regeneration of the whole grid, which at 25 steps is several minutes of card.

Needs the app running. Writes ejemplos/efectos/<id>.jpg plus the base it
started from, so swapping the reference is one command.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time
import urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(APP, "ejemplos", "efectos")
BASE_POR_DEFECTO = os.path.join(DESTINO, "_base.jpg")
LADO = 480          # the grid never shows them any larger
# Anything that ships as an example is generated well above the app's own
# default. At 12 steps the fine detail is still soft, and a thumbnail that
# undersells the effect is worse than no thumbnail. Do not lower this.
PASOS = 25


def _url(ruta: str) -> str:
    ext = os.path.splitext(ruta)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    with open(ruta, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def _pedir(ruta: str, carga: dict, timeout: int = 2400):
    req = urllib.request.Request("http://127.0.0.1:7860" + ruta,
                                 data=json.dumps(carga).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _base_del_efecto(e: dict, base: str, tmp: str) -> str:
    """The picture THIS thumbnail starts from.

    Most start from the shared base. The repairing ones cannot: over a photo
    that is already sharp they appear to do nothing, so they start from the
    same photo broken on purpose -- blurred, or shrunk and blown back up --
    and the thumbnail then shows what the effect repairs. The one that makes
    photographs starts from a drawing, for the same reason.
    """
    from PIL import Image, ImageFilter

    desde = e.get("miniatura_desde")
    if desde:
        ruta = os.path.join(APP, *desde.split("/"))
        if os.path.exists(ruta):
            return ruta
        print(f"    ({desde} is missing, using the shared base)", flush=True)

    danar = e.get("miniatura_danar")
    if not danar:
        return base
    im = Image.open(base).convert("RGB")
    if danar == "desenfoque":
        im = im.filter(ImageFilter.GaussianBlur(radius=max(im.width, im.height) / 190))
    elif danar == "resolucion":
        chico = im.resize((im.width // 6, im.height // 6), Image.BILINEAR)
        im = chico.resize(im.size, Image.BILINEAR)
    ruta = os.path.join(tmp, f"_base_{e['id']}.jpg")
    im.save(ruta, "JPEG", quality=88)
    return ruta


def main() -> None:
    from PIL import Image
    os.makedirs(DESTINO, exist_ok=True)

    args = sys.argv[1:]
    solo: set[str] = set()
    if "--solo" in args:
        i = args.index("--solo")
        solo = {x for x in args[i + 1].split(",") if x}
        args = args[:i] + args[i + 2:]

    base = args[0] if args else BASE_POR_DEFECTO
    if not os.path.exists(base):
        raise SystemExit(f"  the base image is missing: {base}\n"
                         f"  pass one as an argument or leave it at {BASE_POR_DEFECTO}")
    if os.path.abspath(base) != os.path.abspath(BASE_POR_DEFECTO):
        im = Image.open(base).convert("RGB")
        im.thumbnail((1024, 1024), Image.LANCZOS)
        im.save(BASE_POR_DEFECTO, "JPEG", quality=90)
        base = BASE_POR_DEFECTO
    print(f"  base: {base}\n")

    efectos = _pedir_get("/api/efectos")
    hechos = 0
    for e in efectos:
        if solo and e["id"] not in solo:
            continue
        if not e["listo"]:
            print(f"  {e['nombre']:<18} saltado (falta {e['lora']})", flush=True)
            continue
        partida = _base_del_efecto(e, base, tempfile.gettempdir())
        t0 = time.time()
        r = _pedir("/api/efecto", {"imagen": _url(partida), "efecto": e["id"],
                                   "steps": PASOS, "seed": 700})
        if r.get("error"):
            print(f"  {e['nombre']:<18} ERROR {r['error'][:70]}", flush=True)
            continue
        origen = os.path.join(APP, "salidas",
                              os.path.basename(r["imagenes"][0]["archivo"]))
        im = Image.open(origen).convert("RGB")
        im.thumbnail((LADO, LADO), Image.LANCZOS)
        destino = os.path.join(DESTINO, f"{e['id']}.jpg")
        im.save(destino, "JPEG", quality=84, optimize=True)
        hechos += 1
        print(f"  {e['nombre']:<18} ok  {os.path.getsize(destino)/1024:5.0f} KB"
              f"  [{time.time()-t0:.0f}s]", flush=True)

    print(f"\n  {hechos} miniaturas en {DESTINO}")
    for k in sorted(solo - {e['id'] for e in efectos}):
        print(f"  there is no effect called {k}")


def _pedir_get(ruta: str):
    with urllib.request.urlopen("http://127.0.0.1:7860" + ruta, timeout=60) as r:
        return json.loads(r.read())


if __name__ == "__main__":
    main()
