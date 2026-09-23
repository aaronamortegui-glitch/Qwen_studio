"""QwenStudio's installer. It runs INSIDE the venv the launcher created.

It touches no system Python: the venv and its interpreter live inside the app's
folder, fetched by uv. This script:

  1. detects the hardware and picks the profile
  2. installs torch for that backend (cu128 on NVIDIA, the default MPS on Mac)
  3. installs diffusers from git (QwenImage21Pipeline lands in 0.41, which is
     not on PyPI yet) along with the rest of the dependencies
  4. installs bitsandbytes only when there is CUDA (it does not exist for MPS)
  5. writes the profile into config.json

The weights are NOT downloaded here: that happens on first run, so installing
is quick and the profile can be reviewed before committing to ~33 GB.
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

# the diffusers commit with QwenImage21Pipeline already merged (PR #14804).
# Pinned so the installer is reproducible; raise it when 0.41.0 ships.
DIFFUSERS = "git+https://github.com/huggingface/diffusers.git@main"

COMUNES = [
    "transformers>=5.5",
    # diffusers requires peft to load a LoRA. Without it, load_lora_weights
    # raises "PEFT backend is required" and the whole function is missing --
    # which is exactly what happened until a LoRA-backed effect uncovered it.
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
    """Install with uv when it is available (far faster), otherwise with pip."""
    if os.path.exists(UV):
        # link-mode=copy: when uv's cache and the app are on different drives
        # hardlinks cannot be used and uv warns on every package.
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
    """The screen for machines that are not up to it.

    Saying it flatly is an open goal; the dog says the same thing and leaves
    the decision to the user, which is why the install stays available.
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


# What this installer did not say and what cost an afternoon: how long each
# thing takes on the machine it has just detected, and where the real ceiling
# is. The figures in the L row were measured here on 2026-09-23 (nf4 on both
# components, 16 steps, VAE tiling on); the rest are scaled from them and are
# said to be extrapolations, because they are.
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
    if p.vram_limite_gb:
        lineas.append("")
        lineas.append("  The expensive corner is three reference pictures at once")
        lineas.append("  -- a person, a pose and a style together. On the card this")
        lineas.append("  was measured on that reached 21 GB of 24, which is why")
        lineas.append("  several references drop to a smaller size automatically.")

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
