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

# ids the JS builds, or that come from the browser rather than the markup
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
# the settings panel's controls are painted by pintarAjustes() from OPCIONES,
# so none of them is in the markup: they are read from there so the list does
# not have to be maintained by hand
IDS_DINAMICOS |= {
    "aj_" + k for k in
    re.findall(re.escape("['") + "([a-z_]+)','(?:check|num|sel|vae|muestreo)'",
               open(RUTA, encoding="utf-8").read())
}

# Rules that set a dark colour without a background of their own because they
# inherit one from their parent, and the parent does have a fixed light one.
# The check below looks at one rule at a time and cannot know that, so they are
# listed here with the reason.
FONDO_HEREDADO = {
    ".caso[aria-pressed=true] small",   # el fondo lima lo pone .caso[aria-pressed=true]
}


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

    # --- 2. tokens defined only inside a theme block ----------------------
    # the bare :root block has to carry them all, or the default theme is left
    # without that colour
    raiz = re.search(r":root\{(.*?)\}", css, re.S)
    en_raiz = set(re.findall(r"(--[a-z0-9-]+)\s*:", raiz.group(1))) if raiz else set()
    for t in sorted(usados & definidos):
        if t not in en_raiz:
            fallos.append(f"token definido solo en un bloque de tema: {t}")

    # --- 3. $('#id') against the ids in the markup ------------------------
    ids_html = set(re.findall(r'\bid="([A-Za-z][\w-]*)"', cuerpo))
    pedidos = set(re.findall(r"\$\('#([\w-]+)'\)", cuerpo))
    pedidos |= set(re.findall(r"getElementById\('([\w-]+)'\)", cuerpo))
    for i in sorted(pedidos - ids_html - IDS_DINAMICOS):
        fallos.append(f"el JS pide #{i} y no existe en el marcado")

    # --- 4. id duplicados --------------------------------------------------
    todos = re.findall(r'\bid="([A-Za-z][\w-]*)"', cuerpo)
    for i in sorted({x for x in todos if todos.count(x) > 1}):
        fallos.append(f"id duplicado en el marcado: #{i}")

    # --- 5. every dialog, with a panel and a way out -----------------------
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

    # --- 6. hidden against an explicit display -----------------------------
    # the browser sheet gives [hidden]{display:none}, which loses against any
    # display set in a class. Without an !important rule, putting the attribute
    # on a flex does not hide it, and nobody finds out until they see it
    if "[hidden]{display:none!important}" not in css:
        ocultados = set(re.findall(r"\$\('#([\w-]+)'\)\.hidden\s*=", cuerpo))
        ocultados |= set(re.findall(r"getElementById\('([\w-]+)'\)\.hidden\s*=", cuerpo))
        if ocultados:
            fallos.append("falta [hidden]{display:none!important} y el JS oculta "
                          + ", ".join(f"#{x}" for x in sorted(ocultados)[:6]))

    # --- 7. a dark colour as text, with no dark-theme version --------------
    # it reads fine in light and comes out ink on ink in dark; --ac-2 and
    # --link exist for exactly this
    oscuros = {}
    for t, v in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})", raiz.group(1) if raiz else ""):
        r_, g_, b_ = (int(v[i:i + 2], 16) for i in (1, 3, 5))
        if (0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_) < 110:
            oscuros[t] = v
    bloques_oscuros = "".join(re.findall(r"\[data-theme=\"dark\"\]\{(.*?)\}", css, re.S))
    bloques_oscuros += "".join(re.findall(r"prefers-color-scheme:\s*dark\)\{(.*?)\n\}\}", css, re.S))
    for t, v in oscuros.items():
        if re.search(re.escape(t) + r"\s*:", bloques_oscuros):
            continue                       # sí tiene version oscura
        for m in re.finditer(r"([^{};]*)\{([^{}]*?(?<![-\w])color:\s*var\("
                             + re.escape(t) + r"\)[^{}]*)\}", css):
            sel, bloque = m.group(1).strip().splitlines()[-1].strip(), m.group(2)
            # dark text on a fixed light background (a lime pill) is fine in
            # both themes: what fails is on a surface that changes with the
            # theme, or with no background at all
            if sel in FONDO_HEREDADO:
                continue
            fondo = re.search(r"background(?:-color)?:\s*var\((--[a-z0-9-]+)\)", bloque)
            if fondo and not re.search(re.escape(fondo.group(1)) + r"\s*:", bloques_oscuros):
                continue
            fallos.append(f"color:var({t}) ({v}, oscuro) en `{sel[:40]}`: "
                          "sin version para el tema oscuro")

    # --- 8. innerHTML+= on a container that is also appended to ------------
    # assigning innerHTML reparses the whole container and replaces the nodes
    # already placed with fresh copies, which lose the onclick handlers set in
    # code. It really happened: in the prompt library only the last category's
    # buttons responded.
    for m in re.finditer(r"(\w+)\.innerHTML\s*\+=", cuerpo):
        cont = m.group(1)
        ventana = cuerpo[max(0, m.start() - 1500):m.start() + 1500]
        if re.search(re.escape(cont) + r"\.append\(", ventana) and ".onclick" in ventana:
            linea = cuerpo[:m.start()].count(chr(10)) + 1
            fallos.append(f"{cont}.innerHTML+= junto a {cont}.append() con "
                          f"onclick cerca (linea ~{linea} del cuerpo): "
                          "los manejadores ya puestos se pierden")

    # --- 9. what the user reads, in English --------------------------------
    # the whole repository is English now, comments included; this rule guards
    # the visible text, which is the half a reader sees
    for m in re.finditer(r"<(?:b|small|label|h2|h3|p)>([^<>{}$`]{8,})<", cuerpo):
        t = m.group(1)
        if re.search(r"\b(el|la|los|las|una|para|con|que|por|desde|cuando)\b", t):
            fallos.append(f"texto visible en castellano: {t.strip()[:56]}")

    return fallos


# What the server sends to the screen: errors, warnings and statuses. The rule
# is the same as for the markup, but the check above could not see it because it
# lives in another file, and a Spanish warning escaped through that gap.
SERVIDOR = ("app.py", "motor.py", "segmentacion.py", "vision.py", "hardware.py",
            "inpaint.py", "efectos.py")
SALIDA_AL_USUARIO = [
    re.compile(r'"error":\s*f?"([^"]{8,})"'),
    re.compile(r'raise\s+\w*(?:Error|Exception)\(\s*f?"([^"]{8,})"'),
    re.compile(r'(?:estado\.)?mensaje\s*=\s*f?"([^"]{8,})"'),
    re.compile(r'\.append\(\s*"([^"]{8,})"'),
]
CASTELLANO = re.compile(
    r"\b(el|la|los|las|una|unos|unas|para|con|sin|que|por|desde|cuando|hay|esto|"
    r"esta|este|pude|puede|debe|tiene|solo|pero|como|donde|archivo|imagen|modelo"
    r"|invalido|valido|vacio|error de|fallo|cargar el|guardar"
    r"|nada|todo)\b")
# words that are the same in both languages, or proper nouns
PERDON = re.compile(r"^[A-Za-z0-9_./-]+$")


def revisar_js() -> list[str]:
    """Parse the page's JavaScript, which nothing else does.

    An apostrophe inside a single-quoted string closes it, and the browser then
    throws one SyntaxError and abandons the whole script: settings never load,
    no handler binds, and the page looks merely stale rather than broken. That
    shipped once, from the word "model’s" in a setting description. `node
    --check` parses without running, so browser globals do not matter.

    Silent when node is absent: a missing tool is not a finding.
    """
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        return []

    s = open(RUTA, encoding="utf-8").read()
    trozos = re.findall(r"<script>(.*?)</script>", s, re.S)
    if not trozos:
        return ["no se encontro ningun <script> en la pagina"]

    fallos: list[str] = []
    for n, js in enumerate(trozos, 1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            tmp = f.name
        try:
            r = subprocess.run([node, "--check", tmp], capture_output=True,
                               text=True, timeout=60)
            if r.returncode:
                linea = ""
                for l in (r.stderr or "").splitlines():
                    if "SyntaxError" in l:
                        linea = l.strip()
                        break
                fallos.append(f"el <script> {n} no parsea: {linea or 'ver node --check'}")
        except Exception as e:
            fallos.append(f"no se pudo comprobar el <script> {n}: {type(e).__name__}")
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return fallos


def revisar_servidor() -> list[str]:
    fallos: list[str] = []
    for nombre in SERVIDOR:
        ruta = os.path.join(APP, "qwenstudio", nombre)
        if not os.path.exists(ruta):
            continue
        codigo = open(ruta, encoding="utf-8").read()
        vistos = set()
        for patron in SALIDA_AL_USUARIO:
            for m in patron.finditer(codigo):
                # what sits inside {} is code, not text: a variable called
                # `para` is not the Spanish preposition
                t = re.sub(r"\{[^{}]*\}", " ", m.group(1)).strip()
                if not t or PERDON.match(t) or t in vistos:
                    continue
                if CASTELLANO.search(t.lower()):
                    vistos.add(t)
                    linea = codigo[:m.start()].count(chr(10)) + 1
                    fallos.append(f"{nombre}:{linea} mensaje al usuario en "
                                  f"castellano: {t[:52]}")
    return fallos


def main() -> None:
    fallos = revisar() + revisar_js() + revisar_servidor()
    if not fallos:
        print("  interfaz.py y el servidor: sin hallazgos")
        sys.exit(0)
    print(f"  {len(fallos)} hallazgo(s):")
    for f in fallos:
        print(f"    - {f}")
    sys.exit(1)


if __name__ == "__main__":
    main()
