"""Render one thumbnail per effect, from this install's own reference photo.

    .venv\\Scripts\\python.exe herramientas\\generar_efectos.py [base.jpg]

A gallery of looks is only useful if the thumbnails are this model doing this
effect. A stock image from somewhere else shows you what someone else's
pipeline produced, which is exactly the thing you are trying to find out about.

Needs the app running. Writes ejemplos/efectos/<id>.jpg plus the base it
started from, so swapping the reference is one command.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(APP, "ejemplos", "efectos")
BASE_POR_DEFECTO = os.path.join(DESTINO, "_base.jpg")
LADO = 480          # la rejilla nunca las muestra mas grandes


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


def main() -> None:
    from PIL import Image
    os.makedirs(DESTINO, exist_ok=True)

    base = sys.argv[1] if len(sys.argv) > 1 else BASE_POR_DEFECTO
    if not os.path.exists(base):
        raise SystemExit(f"  falta la imagen base: {base}\n"
                         f"  pasala como argumento o dejala en {BASE_POR_DEFECTO}")
    if os.path.abspath(base) != os.path.abspath(BASE_POR_DEFECTO):
        im = Image.open(base).convert("RGB")
        im.thumbnail((1024, 1024), Image.LANCZOS)
        im.save(BASE_POR_DEFECTO, "JPEG", quality=90)
        base = BASE_POR_DEFECTO
    print(f"  base: {base}\n")

    efectos = _pedir_get("/api/efectos")
    hechos = 0
    for e in efectos:
        if not e["listo"]:
            print(f"  {e['nombre']:<18} saltado (falta {e['lora']})", flush=True)
            continue
        t0 = time.time()
        r = _pedir("/api/efecto", {"imagen": _url(base), "efecto": e["id"],
                                   "steps": 25, "seed": 700})
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


def _pedir_get(ruta: str):
    with urllib.request.urlopen("http://127.0.0.1:7860" + ruta, timeout=60) as r:
        return json.loads(r.read())


if __name__ == "__main__":
    main()
