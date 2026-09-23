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
    # peft lo exige diffusers para cargar un LoRA. Sin el, load_lora_weights
    # lanza "PEFT backend is required" y la funcion entera no existe, que es
    # justo lo que pasaba hasta que un efecto con LoRA lo destapo.
    "peft>=0.14",
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


# Lo que este instalador no decia y costaba una tarde: cuanto tarda cada cosa
# en la maquina que acaba de detectar, y donde esta el techo de verdad. Las
# cifras de la fila L estan medidas aqui el 2026-09-23 (nf4 en ambos
# componentes, 16 pasos, tiling del VAE); el resto se escala desde ellas y se
# dice que es una extrapolacion, porque lo es.
ESPERA = {           # nivel -> (1 MP, 2K, nota)
    "XL":     ("~18 s", "~80 s", ""),
    "L":      ("26 s", "122 s", "measured on an RTX 5090 Laptop, 24 GB"),
    "M":      ("~40 s", "~3 min", ""),
    "S":      ("~3-6 min", "not advisable", "layers move across PCIe every step"),
    "MINIMO": ("~10 min+", "no", "layers move across PCIe every step"),
}


def expectativas(p) -> str:
    """What this machine will actually feel like, before ~33 GB come down."""
    uno, dos_k, nota = ESPERA.get(p.nivel, ("?", "?", ""))
    lineas = [
        "-" * 66,
        "  What to expect on this machine",
        "-" * 66,
        f"  one image at 1 MP          {uno}",
        f"  one image at 2K            {dos_k}",
        f"  largest size               {p.res_max} px",
        f"  with one reference photo   {p.res_max_ref} px",
        f"  with several               {p.res_max_multi} px",
    ]
    if p.vram_limite_gb:
        lineas.append(f"  VRAM this app may use      {p.vram_limite_gb} GB "
                      f"of {p.vram_gb} GB")
        lineas.append("")
        lineas.append("  Three sizes, because they were measured as three: every")
        lineas.append("  reference photo costs memory on top of the output. And a")
        lineas.append("  hard ceiling under all of them, because on the machine this")
        lineas.append("  was measured on, reaching for the last few gigabytes blue-")
        lineas.append("  screened Windows twice. Past that ceiling the app gets an")
        lineas.append("  error it can report; without it, the driver gets a request")
        lineas.append("  it cannot serve and takes the kernel with it.")
    elif p.backend == "mps":
        lineas.append("")
        lineas.append("  No VRAM ceiling on Apple Silicon: the mechanism that enforces")
        lineas.append("  one is CUDA-only, and claiming otherwise would be a comfort")
        lineas.append("  rather than a guard.")
    if p.cuantizacion == "int4":
        lineas.append("")
        lineas.append("  Weights load in nf4. On this architecture that is not the")
        lineas.append("  poor mode: it is faster than bf16, uses half the memory, and")
        lineas.append("  is the only way 2K works. At the same seed the two are")
        lineas.append("  indistinguishable by eye -- but they are not the same")
        lineas.append("  picture, so a recipe made in bf16 will not reproduce here.")
    if nota:
        lineas.append("")
        lineas.append(f"  ({nota})")
    return chr(10).join(lineas)


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
    print(expectativas(perfil))
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
