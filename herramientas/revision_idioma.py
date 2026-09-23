"""Catch Spanish left in the repository: comments, docstrings, text of any kind.

Everything committed here is in English. The identifiers are not -- `motor`,
`imagen`, `salidas` are the existing names and stay -- so this looks at prose
only, and knows which Spanish words are also names in this codebase.

It exists because the rule was broken twice without anyone noticing. The first
check only looked at whole-line comments and missed every trailing one after
code; the second missed console strings entirely. It reads every tracked Python
file, every markdown document, the launchers and .gitignore. Run it before a
commit:

    .venv/Scripts/python.exe herramientas/revision_idioma.py

Exits 0 with nothing found, 1 with a list.
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Spanish words that carry prose. English homographs (sin, no, sale, con, ...)
# are deliberately absent: they cost more in noise than they catch.
CASTELLANO = set("""
que para del los las una unos unas este esta estos estas ese esa eso cuando
donde porque tambien aunque entonces hasta desde pero cada toda todas nada
algo hace hacer hacen tiene tienen puede pueden debe deben estar estan muy
mismo misma asi aqui alli cuales sino segun entre hacia despues dentro fuera
siempre nunca peor pequeno nueva vieja rapido lento carpeta pantalla memoria
techo altura columna usuario cambio cambios valor numero primero segundo
tercera queda pasa vale cuesta sigue ademas mientras hallazgos ninguno ninguna
falta faltan guardar guardado abrir cerrar listo generando siguiente anterior
sobre bien mejor grande nuevo linea ancho prueba pruebas hay responde limpio
sucio cambios commitear respaldo fecha ahora aun todavia ninguno cuantos
tamano copiados funciona funcionan usa usan pesos cuantizados cuantizada
arranca arrancar corre corren sirve sirven pone ponen quita quitan
""".split())

# ...and the ones that are identifiers here, so a line naming a function or a
# JSON key is not read as a sentence.
NOMBRES = set("""
motor imagen imagenes entrada entradas salida salidas texto archivo archivos
nombre tarjeta caja lista carga error pose poses efecto efectos estilo escena
persona personas prompt resumen receta mascara frase padding variantes semilla
todos solo quien cual antes vitrina marca segmenta vision interfaz recursos
inpaint muestreo turbo ajustes config perfil nivel destino origen raiz sello
""".split())

PALABRAS = CASTELLANO - NOMBRES
UMBRAL = 2          # two carrying words in one fragment is a sentence

# inline code, URLs, file paths and snake_case names are not prose, and they
# are full of words that look Spanish because the identifiers here are Spanish
CODIGO = re.compile(r"`[^`]*`|https?://\S+|\S*[/\\]\S*|\b\w+_\w+\b")
# a regular expression that happens to list Spanish words is not a sentence
REGEX = re.compile(r"\\b|\(\?:|\\w|\\s|\\S")
LETRAS = re.compile(r"[^\W\d_]+", re.UNICODE)
# interfaz.py is one long Python string holding HTML, CSS and JS, so its
# comments are not Python comments and no check ever read them. Sixty lines
# of Spanish lived in there. // is matched only when nothing precedes it on
# the line but whitespace or code, never inside a URL.
WEB = re.compile(r"(?<![:/])//(.*)$|/\*(.*?)\*/")


def _castellano(frag: str) -> list[str]:
    """The Spanish words in a fragment, once the code has been taken out."""
    frag = CODIGO.sub(" ", frag)
    return [w for w in LETRAS.findall(frag.lower()) if w in PALABRAS]


def _es_prosa(s: str) -> bool:
    """A string worth reading as a sentence: not a route, a key or a pattern."""
    return " " in s.strip() and not REGEX.search(s)


# the documents and launchers that ship: their comments are read too
OTROS = (".md", ".bat", ".command", ".sh")
COMENTARIO = re.compile(r"^\s*(?:rem|::|#)\s?(.*)$", re.I)


def _archivos(patron: str) -> list[str]:
    salida = subprocess.run(["git", "ls-files", patron], cwd=APP,
                            capture_output=True, text=True).stdout
    return [f for f in salida.split("\n") if f.strip()]


def revisar_textos() -> list[str]:
    """Markdown in full, launchers and .gitignore by their comment lines."""
    fallos = []
    for rel in _archivos("*"):
        p = pathlib.PurePath(rel)
        if p.suffix.lower() not in OTROS and p.name != ".gitignore":
            continue
        try:
            texto = open(os.path.join(APP, rel), encoding="utf-8").read()
        except OSError:
            continue
        for i, linea in enumerate(texto.splitlines(), 1):
            if p.suffix.lower() == ".md":
                frag = linea
            else:
                m = COMENTARIO.match(linea)
                frag = m.group(1) if m else ""
            if len(_castellano(frag)) >= UMBRAL:
                fallos.append(f"{rel}:{i} line in Spanish: {linea.strip()[:60]}")
    return fallos


def revisar() -> list[str]:
    fallos = []
    for rel in _archivos("*.py"):
        ruta = os.path.join(APP, rel)
        try:
            codigo = open(ruta, encoding="utf-8").read()
        except OSError:
            continue

        # comments, including the trailing ones the first check never saw and
        # the JS and CSS ones living inside a Python string
        for i, linea in enumerate(codigo.splitlines(), 1):
            m = re.search(r"#(.*)$", linea)
            if m and len(_castellano(m.group(1))) >= UMBRAL:
                fallos.append(f"{rel}:{i} comment in Spanish: {linea.strip()[:60]}")
                continue
            w = WEB.search(linea)
            if w and len(_castellano(w.group(1) or w.group(2) or "")) >= UMBRAL:
                fallos.append(f"{rel}:{i} web comment in Spanish: {linea.strip()[:60]}")

        try:
            arbol = ast.parse(codigo)
        except SyntaxError as e:
            fallos.append(f"{rel}:{e.lineno} does not parse: {e.msg}")
            continue

        for nodo in ast.walk(arbol):
            # docstrings
            if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                doc = ast.get_docstring(nodo)
                if doc and len(_castellano(doc)) >= UMBRAL:
                    fallos.append(f"{rel}:{getattr(nodo, 'lineno', 0)} docstring in "
                                  f"Spanish: {doc.strip().splitlines()[0][:60]}")
            # strings: console output and anything the user reads
            elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                v = nodo.value
                if (6 <= len(v) <= 400 and _es_prosa(v)
                        and len(_castellano(v)) >= UMBRAL):
                    fallos.append(f"{rel}:{nodo.lineno} string in Spanish: "
                                  f"{v.replace(chr(10), ' ')[:60]}")
    return fallos


def main() -> None:
    fallos = revisar() + revisar_textos()
    if not fallos:
        print("  the repository is in English: nothing found")
        sys.exit(0)
    print(f"  {len(fallos)} finding(s):")
    for f in fallos:
        print(f"    - {f}")
    sys.exit(1)


if __name__ == "__main__":
    main()
