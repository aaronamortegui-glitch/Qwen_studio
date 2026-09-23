"""Where the probe scripts find their input images.

These are the throwaway scripts the measurements in the README came out of.
They need a photograph of a person and a couple of ordinary scene photographs.
Nothing personal ships in this repository, so the files are looked up at run
time instead of being written down:

    QWENSTUDIO_REF       a photograph of a person
                         (default: the first image under entradas/)
    QWENSTUDIO_ESCENAS   a folder holding the scene photographs
                         (default: entradas/)

A missing file stops the script with the name of the variable to set, so a run
never half-finishes against the wrong picture and gets read as a result.
"""
from __future__ import annotations

import base64
import glob
import os

APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENTRADAS = os.path.join(APP, "entradas")
EXTENSIONES = (".jpg", ".jpeg", ".png", ".webp")


def _primera(carpeta: str) -> str:
    for f in sorted(glob.glob(os.path.join(carpeta, "**", "*"), recursive=True)):
        if f.lower().endswith(EXTENSIONES):
            return f
    return ""


def persona() -> str:
    """Path to a photograph of a person."""
    ruta = os.environ.get("QWENSTUDIO_REF") or _primera(ENTRADAS)
    if not ruta or not os.path.exists(ruta):
        raise SystemExit("point QWENSTUDIO_REF at a photograph of a person, "
                         "or drop one into entradas/")
    return ruta


def escena(nombre: str) -> str:
    """Path to a scene photograph, by file name."""
    carpeta = os.environ.get("QWENSTUDIO_ESCENAS") or ENTRADAS
    ruta = os.path.join(carpeta, nombre)
    if not os.path.exists(ruta):
        raise SystemExit(f"{nombre} is not in {carpeta}: point QWENSTUDIO_ESCENAS "
                         f"at a folder that has it")
    return ruta


def data_url(ruta: str, mime: str = "") -> str:
    """The file as a data: URL, which is how the HTTP API takes images."""
    if not mime:
        mime = "image/jpeg" if ruta.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(ruta, "rb").read()).decode()
