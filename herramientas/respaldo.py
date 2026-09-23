"""Copy everything the repository holds into a dated folder.

    .venv\\Scripts\\python.exe herramientas\\respaldo.py [destino]

What gets copied is exactly what git tracks, so the backup and the repository
cannot drift: no virtualenv, no 31 GB of weights, no outputs, no config.json
describing this particular machine. If a file is not in the backup it is
because it is not in the repository either, and the fix is the same in both
places.

Writes <destino>/QwenStudio_<date>/ plus a zip of the same content beside it,
and a MANIFIESTO.txt listing every file with its size and the commit it came
from, so a backup can be told apart from the others months later.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import zipfile

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO_POR_DEFECTO = r"D:\QwenStudio_respaldos"


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", APP, *args], capture_output=True, text=True,
                           timeout=60)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _seguidos() -> list[str]:
    """Every file git tracks, staged changes included."""
    salida = _git("ls-files")
    if not salida:
        raise SystemExit("  no git repository here, or git is not answering")
    return [l.strip() for l in salida.splitlines() if l.strip()]


def main() -> None:
    raiz = sys.argv[1] if len(sys.argv) > 1 else DESTINO_POR_DEFECTO
    sello = time.strftime("%Y%m%d_%H%M")
    carpeta = os.path.join(raiz, f"QwenStudio_{sello}")
    os.makedirs(carpeta, exist_ok=True)

    archivos = _seguidos()
    commit = _git("rev-parse", "--short", "HEAD") or "no commit"
    asunto = _git("log", "-1", "--pretty=%s") or ""
    sucio = _git("status", "--porcelain")

    total = 0
    copiados = []
    for rel in archivos:
        origen = os.path.join(APP, rel)
        if not os.path.exists(origen):
            continue
        destino = os.path.join(carpeta, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.copy2(origen, destino)
        n = os.path.getsize(origen)
        total += n
        copiados.append((rel, n))

    manifiesto = os.path.join(carpeta, "MANIFIESTO.txt")
    with open(manifiesto, "w", encoding="utf-8") as f:
        f.write(f"QwenStudio - backup {sello}\n")
        f.write(f"commit    {commit}  {asunto}\n")
        f.write(f"state     {'uncommitted changes' if sucio else 'clean'}\n")
        f.write(f"files     {len(copiados)}\n")
        f.write(f"size      {total/2**20:.1f} MB\n")
        f.write("\n" + "-" * 66 + "\n")
        for rel, n in sorted(copiados):
            f.write(f"{n:>10}  {rel}\n")

    zip_ = os.path.join(raiz, f"QwenStudio_{sello}.zip")
    with zipfile.ZipFile(zip_, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel, _ in copiados:
            z.write(os.path.join(APP, rel), f"QwenStudio/{rel}")
        z.write(manifiesto, "QwenStudio/MANIFIESTO.txt")

    print(f"  {len(copiados)} files, {total/2**20:.1f} MB")
    print(f"  commit {commit}" + ("  (uncommitted changes)" if sucio else ""))
    print(f"  folder   {carpeta}")
    print(f"  zip      {zip_}  ({os.path.getsize(zip_)/2**20:.1f} MB)")


if __name__ == "__main__":
    main()
