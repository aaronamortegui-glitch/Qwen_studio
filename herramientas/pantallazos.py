"""Retake every screenshot in docs/, from this build, in one command.

    .venv\\Scripts\\python.exe herramientas\\pantallazos.py           (all of them)
    .venv\\Scripts\\python.exe herramientas\\pantallazos.py vitrina    (just one)

The README shows nine screens. Taken by hand they rot quietly: one of them sat
there for a week showing a LoRA selector that had been removed from that screen
weeks earlier, and nothing in the repository could have told us. Every screen
here is reachable by a deep link, so a script can take all nine and the docs
stop drifting from the build.

Headless Chrome, so nothing appears on screen and nothing takes focus while
someone is using the machine. It needs the app running, and it does not touch
the GPU: it only loads the page.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

APP = os.environ.get("QWENSTUDIO", "http://127.0.0.1:7860")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(RAIZ, "docs")

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium",
]

ANCHO = 1343          # el ancho con el que se tomaron los primeros
ALTO = 931

# nombre -> (enlace directo, alto)
PANTALLAS: dict[str, tuple[str, int]] = {
    "ui-portrait": ("?caso=portrait", ALTO),
    "ui-text":     ("?caso=sign", ALTO),
    "ui-vitrina":  ("?caso=blank", 1150),
    # el pie queda al final de una pagina larga: se toma entera y se recorta.
    # La altura se mide en vez de fijarla: la vitrina crece y una ventana corta
    # hacia que el recorte cayera sobre las miniaturas en vez de sobre el pie.
    "ui-indice":   ("?caso=look", 0),
    "ui-brush":    ("?caso=replace&abrir=mask", ALTO),
    "ui-poses":    ("?caso=pose&abrir=poses", ALTO),
    "ui-looks":    ("?caso=look&abrir=efectos", ALTO),
    "ui-restyle":  ("?caso=restyle", ALTO),
    # los tres ajustes de motor viven abajo del panel: se toma entero
    "ui-settings": ("?abrir=ajustes", ALTO),
    "ui-gallery":  ("?abrir=galeria", ALTO),
    "ui-dark":     ("?caso=portrait&tema=dark", ALTO),
    # la ficha de una receta necesita un archivo concreto, asi que su enlace se
    # arma en tiempo de ejecucion con lo ultimo que haya en salidas/
    "ui-recipe":   ("?receta=", ALTO),
}


def _ultimo_resultado() -> str:
    """El nombre del archivo mas reciente de la galeria, para la ficha."""
    import json
    import urllib.request
    with urllib.request.urlopen(APP + "/api/galeria", timeout=30) as r:
        d = json.loads(r.read())
    items = d.get("items") or []
    return items[0]["nombre"] if items else ""


def _chrome() -> str:
    for c in CHROME:
        if os.path.exists(c) or shutil.which(c):
            return c
    raise SystemExit("no Chrome or Chromium found; install one or set CHROME")


def tomar(nombre: str, enlace: str, alto: int, chrome: str) -> None:
    destino = os.path.join(DOCS, nombre + ".png")
    # virtual-time-budget deja correr los temporizadores de la pagina: los
    # dialogos se abren con setTimeout y las miniaturas cargan en diferido
    if alto == 0:
        alto = _alto_de_pagina(enlace, chrome)
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=1", f"--window-size={ANCHO},{alto}",
           "--virtual-time-budget=9000", f"--screenshot={destino}",
           APP + "/" + enlace]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not os.path.exists(destino):
        raise SystemExit(f"{nombre}: nothing written\n{r.stderr[-400:]}")
    if nombre == "ui-indice":
        alto = _recortar_al_pie(destino)
    kb = round(os.path.getsize(destino) / 1024)
    print(f"  {nombre:14} {ANCHO}x{alto}  {kb} KB  {round(time.time()-t0)}s")


def _alto_de_pagina(enlace: str, chrome: str) -> int:
    """Cuanto mide la pagina de verdad, para que quepa entera en la captura."""
    import json
    import tempfile
    d = tempfile.mkdtemp()
    cmd = [chrome, "--headless=new", "--disable-gpu", f"--window-size={ANCHO},1200",
           "--virtual-time-budget=9000", "--dump-dom", APP + "/" + enlace]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    # --dump-dom no da la altura: se pide a la propia app cuantas piezas hay y
    # se acota generosamente. Mas simple y no falla en silencio.
    try:
        import urllib.request
        with urllib.request.urlopen(APP + "/api/vitrina", timeout=30) as r:
            n = len(json.load(r))
    except Exception:
        n = 30
    return 1800 + n * 130


def _recortar_al_pie(ruta: str) -> int:
    """Deja solo el pie: la pagina entera mide tres mil pixeles y no se lee."""
    from PIL import Image
    import numpy as np
    with Image.open(ruta) as im:
        a = np.asarray(im.convert("RGB"))
        fondo = a[-5, 5].astype(int)
        filas = np.where((np.abs(a.astype(int) - fondo).sum(axis=2) > 12).any(axis=1))[0]
        fin = int(filas.max()) + 14 if len(filas) else a.shape[0]
        ini = max(0, fin - 640)
        im.crop((0, ini, im.width, fin)).save(ruta)
    return fin - ini


def main() -> None:
    quiere = set(a.lstrip("-") for a in sys.argv[1:])
    chrome = _chrome()
    os.makedirs(DOCS, exist_ok=True)
    for nombre, (enlace, alto) in PANTALLAS.items():
        if quiere and nombre not in quiere and nombre.removeprefix("ui-") not in quiere:
            continue
        if enlace.endswith("receta="):
            ultimo = _ultimo_resultado()
            if not ultimo:
                print(f"  {nombre:14} skipped: salidas/ is empty")
                continue
            enlace += ultimo
        tomar(nombre, enlace, alto, chrome)


if __name__ == "__main__":
    main()
