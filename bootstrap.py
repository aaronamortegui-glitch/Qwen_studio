"""Instalador de QwenStudio. Corre DENTRO del venv que creo el lanzador.

No toca ningun Python del sistema: el venv y su interprete viven dentro de la
carpeta de la app (los baja uv). Este script:

  1. detecta el hardware y elige el perfil
  2. instala torch para ese backend (cu128 en NVIDIA, MPS por defecto en Mac)
  3. instala diffusers desde git (QwenImage21Pipeline llega en 0.41, que aun no
     esta publicada en PyPI) y el resto de dependencias
  4. instala bitsandbytes solo si hay CUDA (no existe para MPS)
  5. guarda el perfil en config.json

Los pesos NO se bajan aqui: eso pasa en el primer arranque, para que instalar
sea rapido y se pueda revisar el perfil antes de comprometer ~33 GB.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP)

from qwenstudio.hardware import detectar, resumen, DESCARGA_GB  # noqa: E402

CONFIG = os.path.join(APP, "config.json")
UV = os.path.join(APP, ".uv", "uv.exe" if os.name == "nt" else "uv")

# commit de diffusers con QwenImage21Pipeline ya mergeado (PR #14804).
# Se fija para que el instalador sea reproducible; subir cuando salga 0.41.0.
DIFFUSERS = "git+https://github.com/huggingface/diffusers.git@main"

COMUNES = [
    "transformers>=5.5",
    "accelerate>=1.0",
    "safetensors>=0.4",
    "huggingface_hub>=1.0",
    "sentencepiece",
    "protobuf",
    "pillow",
    "numpy",
]


def pip(*args: str) -> None:
    """Instala con uv si esta disponible (mucho mas rapido), si no con pip."""
    if os.path.exists(UV):
        # link-mode=copy: si el cache de uv y la app estan en discos distintos
        # no se pueden usar hardlinks y uv avisa en cada paquete.
        cmd = [UV, "pip", "install", "--python", sys.executable, "--link-mode=copy", *args]
    else:
        cmd = [sys.executable, "-m", "pip", "install", *args]
    print(f"\n$ {' '.join(cmd[-min(4, len(cmd)):])}", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"\nFailed installing: {args}\n"
                         f"Check your connection and run the installer again.")


PERRITO = r"""
                  ,--.       ,--.
                 /    \_____/    \
                |   (o)     (o)   |
                |        v        |
                 \     \___/     /
                  '--..______..--'
"""


def lloriquear(nivel: str, acelerador: str, vram: float) -> None:
    """La pantalla para los equipos que no dan la talla.

    Decirlo en seco es una porteria vacia; el perro dice lo mismo y deja que
    decida el usuario, que para eso la instalacion sigue disponible.
    """
    print(PERRITO)
    if nivel == "INVIABLE":
        print("  This machine cannot run the model in any useful way.")
        print("  A 7B diffusion transformer needs a GPU with room for it,")
        print("  and there is not one here.")
    else:
        print("  It will run here, but slowly, and 4-bit quantisation will")
        print("  cost you some quality. Minutes per image, not seconds.")
    print()
    print("  Maybe invest in your future and get something more powerful?")
    print("  The puppy would appreciate it.")
    print()
    print(f"  {acelerador} - {vram:.1f} GB - profile {nivel}")


def main() -> None:
    print("=" * 66)
    print("  QwenStudio - install")
    print("=" * 66)
    print(f"\n  Environment Python: {sys.version.split()[0]}")
    print(f"  Folder:             {APP}\n")

    print("-" * 66)
    print("  Hardware detected")
    print("-" * 66)
    perfil = detectar(APP)
    print(resumen(perfil))
    print()

    if not perfil.viable or perfil.nivel == "MINIMO":
        lloriquear(perfil.nivel, perfil.acelerador, perfil.vram_gb)
        print("\n  The dependencies install either way, in case you move this")
        print("  folder to a better machine later.")
        if input("\n  Continue anyway? [Y/n] ").strip().lower() in ("n", "no"):
            raise SystemExit("\n  Cancelled.")

    # ---- torch segun backend ------------------------------------------
    print("\n" + "-" * 66)
    print("  Installing PyTorch")
    print("-" * 66)
    if perfil.backend == "cuda":
        print("  NVIDIA found: CUDA 12.8 wheel (covers Blackwell / sm_120).")
        pip("torch", "torchvision", "--index-url", perfil.torch_index)
    elif perfil.backend == "mps":
        print("  Apple Silicon: the standard PyPI wheel already carries MPS support.")
        pip("torch", "torchvision")
    else:
        print("  No GPU: CPU wheel.")
        pip("torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu")

    # ---- resto ---------------------------------------------------------
    print("\n" + "-" * 66)
    print("  Installing diffusers and dependencies")
    print("-" * 66)
    print("  diffusers comes from git: QwenImage21Pipeline lands in 0.41.0 and the")
    print("  latest on PyPI is still 0.40.0.")
    pip(DIFFUSERS)
    pip(*COMUNES)

    if perfil.cuantizacion in ("int8", "int4"):
        print("\n" + "-" * 66)
        print(f"  Quantisation {perfil.cuantizacion}: installing bitsandbytes")
        print("-" * 66)
        pip("bitsandbytes>=0.45")

    # ---- verificacion ---------------------------------------------------
    print("\n" + "-" * 66)
    print("  Checking")
    print("-" * 66)
    check = (
        "import torch, diffusers;"
        "print('  torch      ', torch.__version__);"
        "print('  diffusers  ', diffusers.__version__);"
        "print('  cuda       ', torch.cuda.is_available());"
        "print('  mps        ', getattr(torch.backends,'mps',None) and torch.backends.mps.is_available());"
        "from diffusers import QwenImage21Pipeline;"
        "print('  QwenImage21Pipeline  OK')"
    )
    r = subprocess.run([sys.executable, "-c", check])
    if r.returncode != 0:
        print("\n  ! The check failed. The likeliest cause is that this diffusers")
        print("    commit does not carry QwenImage21Pipeline yet. Try the installer")
        print("    again in a few days, or pin another commit in DIFFUSERS.")
        raise SystemExit(1)

    # ---- config ---------------------------------------------------------
    cfg = json.loads(perfil.to_json())
    cfg["modelos_descargados"] = False
    cfg["ruta_modelos"] = os.path.join(APP, "modelos")
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 66)
    print("  Done.")
    print("=" * 66)
    print(f"\n  Profile saved to config.json  (level {perfil.nivel})")
    print(f"\n  The weights (~{DESCARGA_GB} GB) download the first time you run the")
    print("  app, with a resumable progress bar.")
    print("\n  To start:")
    print("     " + ("RUN.bat" if os.name == "nt" else "./run.command"))
    print()


if __name__ == "__main__":
    main()
