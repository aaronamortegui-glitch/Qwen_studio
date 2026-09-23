"""Build the distributable zip.

Ships the code, the pose library and the examples. Leaves out everything the
installer recreates or the first run downloads: the virtualenv (4.6 GB), uv,
the model weights (31 GB), and anything generated while using the app.

    .venv\\Scripts\\python.exe herramientas\\empaquetar.py

The result is a few megabytes. Whoever receives it unzips, double-clicks the
installer for their platform, and the weights download on first run.
"""

from __future__ import annotations

import os
import sys
import zipfile

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INCLUIR_ARCHIVOS = [
    "INSTALL.bat", "install.command", "RUN.bat", "run.command",
    "SHORTCUT.bat", "QwenStudio.ico", "bootstrap.py", "README.md", ".gitignore",
    "AGENTS.md", "CLAUDE.md", "PENDIENTE.md",
]
# docs/ travels because the README references it and because the explanatory
# PDF is there: whoever receives the zip without going through GitHub has to be
# able to read it too.
INCLUIR_CARPETAS = ["qwenstudio", "herramientas", "poses", "ejemplos", "docs",
                    "referencia"]

# what does not travel, and why
EXCLUIR_DIRS = {
    ".venv",        # the installer builds it, 4.6 GB
    ".uv",          # the installer downloads it
    "modelos",      # 31 GB, fetched on the first run
    "salidas", "entradas",   # produced by using the app
    "loras",        # the LoRAs belong to the user, not to me
    "__pycache__", ".git",
}
EXCLUIR_SUFIJOS = (".pyc", ".pyo", ".log", ".db", ".db-wal", ".db-shm")
# config.json describes THIS hardware; ajustes.json holds local preferences
EXCLUIR_ARCHIVOS = {"config.json", "ajustes.json", "_meta_gen.json"}


def incluir(ruta_rel: str) -> bool:
    partes = ruta_rel.replace("\\", "/").split("/")
    if any(p in EXCLUIR_DIRS for p in partes):
        return False
    if os.path.basename(ruta_rel) in EXCLUIR_ARCHIVOS:
        return False
    return not ruta_rel.endswith(EXCLUIR_SUFIJOS)


def main() -> None:
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(APP, "QwenStudio.zip")
    n = 0
    total = 0
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in INCLUIR_ARCHIVOS:
            ruta = os.path.join(APP, f)
            if os.path.exists(ruta):
                z.write(ruta, f"QwenStudio/{f}")
                n += 1
                total += os.path.getsize(ruta)
        for carpeta in INCLUIR_CARPETAS:
            base = os.path.join(APP, carpeta)
            if not os.path.isdir(base):
                continue
            for raiz, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in EXCLUIR_DIRS]
                for f in files:
                    abs_ = os.path.join(raiz, f)
                    rel = os.path.relpath(abs_, APP)
                    if incluir(rel):
                        z.write(abs_, f"QwenStudio/{rel.replace(os.sep, '/')}")
                        n += 1
                        total += os.path.getsize(abs_)
        # folders that have to exist, empty, once it is unzipped
        for vacia in ("loras", "salidas", "entradas", "modelos"):
            z.writestr(f"QwenStudio/{vacia}/.keep", "")

    # check: nothing heavy and nothing specific to this machine slipped in
    import zipfile as _z
    dentro = _z.ZipFile(destino).namelist()
    def sospechoso(x):
        if x.endswith("/.keep"):
            return False                      # they make the empty folders, on purpose
        return any(m in x for m in (".venv/", "/modelos/", "config.json",
                                    "ajustes.json", ".pyc"))
    malos = [x for x in dentro if sospechoso(x)]

    print(f"  {n} files, {total/2**20:.1f} MB raw -> "
          f"{os.path.getsize(destino)/2**20:.1f} MB zipped")
    if malos:
        print(f"  ! these should not be in the package: {malos[:6]}")
    print(f"  {destino}")
    print("\n  The recipient unzips it and runs INSTALL.bat (Windows) or")
    print("  install.command (macOS). The weights download on first run.")


if __name__ == "__main__":
    main()
