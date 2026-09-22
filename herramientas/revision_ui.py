"""Static check of the interface: the mistakes that do not raise.

    .venv\\Scripts\\python.exe herramientas\\revision_ui.py

The interface is one Python string holding HTML, CSS and JS, so nothing in it
is type-checked and nothing fails loudly. The failures are quiet ones: a colour
token that was renamed and left a `var(--old)` behind resolves to nothing and
the element renders transparent; a `$('#id')` whose element was deleted returns
null and the handler silently never binds; a dialog with no way out traps the
user. Two of those shipped in this file before this script existed.

Exits non-zero if it finds anything, so it can gate a commit.
"""

from __future__ import annotations

import os
import re
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA = os.path.join(APP, "qwenstudio", "interfaz.py")

# ids que el JS construye o que vienen del navegador, no del marcado
IDS_DINAMICOS = {
    "lupaImg",          # vive dentro del dialogo de la lupa
    "notaEjemplo",      # el aviso del ejemplo, creado al cargarlo
    "figEjemplo",       # la hoja del ejemplo, creada en la galeria
    "quitaEjemplo",     # su boton
    "igualmente",       # el boton del perrito
    "seleccion",        # el campo de inpaint, creado por construirCampos
    "btnPintar", "btnQuitarMask", "notaMask",
}
IDS_DINAMICOS |= {f"z_{z}" for z in
                  ("person", "pose", "style", "scene", "source", "extra")}
IDS_DINAMICOS |= {f"t_{z}" for z in
                  ("person", "pose", "style", "scene", "source", "extra")}


def _partes(s: str) -> tuple[str, str]:
    i, j = s.index("<style>"), s.index("</style>")
    return s[i:j], s[j:]


def revisar() -> list[str]:
    s = open(RUTA, encoding="utf-8").read()
    css, cuerpo = _partes(s)
    fallos: list[str] = []

    # --- 1. tokens usados que nadie define --------------------------------
    definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
    usados = set(re.findall(r"var\((--[a-z0-9-]+)", s))
    huerfanos = sorted(usados - definidos)
    for t in huerfanos:
        fallos.append(f"token sin definir: var({t})")

    # --- 2. tokens definidos solo dentro de un bloque de tema -------------
    # el bloque :root pelado tiene que traerlos todos, o el tema por defecto
    # se queda sin ese color
    raiz = re.search(r":root\{(.*?)\}", css, re.S)
    en_raiz = set(re.findall(r"(--[a-z0-9-]+)\s*:", raiz.group(1))) if raiz else set()
    for t in sorted(usados & definidos):
        if t not in en_raiz:
            fallos.append(f"token definido solo en un bloque de tema: {t}")

    # --- 3. $('#id') contra los id del marcado ----------------------------
    ids_html = set(re.findall(r'\bid="([A-Za-z][\w-]*)"', cuerpo))
    pedidos = set(re.findall(r"\$\('#([\w-]+)'\)", cuerpo))
    pedidos |= set(re.findall(r"getElementById\('([\w-]+)'\)", cuerpo))
    for i in sorted(pedidos - ids_html - IDS_DINAMICOS):
        fallos.append(f"el JS pide #{i} y no existe en el marcado")

    # --- 4. id duplicados --------------------------------------------------
    todos = re.findall(r'\bid="([A-Za-z][\w-]*)"', cuerpo)
    for i in sorted({x for x in todos if todos.count(x) > 1}):
        fallos.append(f"id duplicado en el marcado: #{i}")

    # --- 5. cada dialogo, con panel y con salida ---------------------------
    dialogos = set(re.findall(r'<dialog id="([\w-]+)"', cuerpo))
    con_panel = set()
    regla_general = False
    for sel in re.findall(r"^([^{]*)\{[^}]*background:var\(--sf\)[^}]*\}", css, re.M):
        if "dialog:not(#lupa)" in sel:
            regla_general = True          # cubre a todos menos la lupa, a proposito
        con_panel |= set(re.findall(r"#([\w-]+)", sel))
    if regla_general:
        con_panel |= dialogos
    for d in sorted(dialogos - con_panel - {"lupa"}):
        fallos.append(f"el dialogo #{d} no tiene fondo: se vera transparente")
    for d in sorted(dialogos):
        cierra = (f"$('#{d}').close()" in cuerpo
                  or f"e.target.id==='{d}'" in cuerpo
                  or f'<dialog id="{d}"' in cuerpo and f"#{d}').close" in cuerpo)
        if not cierra:
            fallos.append(f"el dialogo #{d} no tiene forma de cerrarse")

    # --- 6. hidden contra un display explicito -----------------------------
    # la hoja del navegador da [hidden]{display:none}, que pierde contra
    # cualquier display puesto en una clase. Sin una regla !important, poner
    # el atributo a un flex no lo oculta y nadie se entera hasta verlo
    if "[hidden]{display:none!important}" not in css:
        ocultados = set(re.findall(r"\$\('#([\w-]+)'\)\.hidden\s*=", cuerpo))
        ocultados |= set(re.findall(r"getElementById\('([\w-]+)'\)\.hidden\s*=", cuerpo))
        if ocultados:
            fallos.append("falta [hidden]{display:none!important} y el JS oculta "
                          + ", ".join(f"#{x}" for x in sorted(ocultados)[:6]))

    # --- 7. lo que el usuario lee, en ingles -------------------------------
    # los comentarios van en castellano a proposito; el texto visible no
    for m in re.finditer(r"<(?:b|small|label|h2|h3|p)>([^<>{}$`]{8,})<", cuerpo):
        t = m.group(1)
        if re.search(r"\b(el|la|los|las|una|para|con|que|por|desde|cuando)\b", t):
            fallos.append(f"texto visible en castellano: {t.strip()[:56]}")

    return fallos


def main() -> None:
    fallos = revisar()
    if not fallos:
        print("  interfaz.py: sin hallazgos")
        sys.exit(0)
    print(f"  {len(fallos)} hallazgo(s):")
    for f in fallos:
        print(f"    - {f}")
    sys.exit(1)


if __name__ == "__main__":
    main()
