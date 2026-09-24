"""Hardware detection and the choice of an execution profile.

It does not depend on torch: it runs before anything is installed, so it can
decide WHAT to install. It uses only the standard library plus system tools
(nvidia-smi, sysctl, wmic) and, when torch is already available, uses it to
refine the answer.

The profile decides four things:
    backend        cuda | mps | cpu
    dtype          bfloat16 | float16 | float32
    quantisation   none | int8 | int4   (CUDA only: neither backend has MPS)
                   int8 is quanto, int4 is bitsandbytes nf4 -- see motor.py
    offload        none | model | sequential

The weight download is the same in every profile (~33 GB from Qwen's diffusers
repo). What changes is how they are loaded.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict

GB = 1024 ** 3


# ------------------------------------------------------------------ sondeo

def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _ram_bytes() -> int:
    s = platform.system()
    if s == "Darwin":
        out = _run(["sysctl", "-n", "hw.memsize"])
        return int(out) if out.isdigit() else 0
    if s == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
        except Exception:
            return 0
    if s == "Windows":
        out = _run(["powershell", "-NoProfile", "-Command",
                    "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        m = re.search(r"\d+", out)
        if m:
            return int(m.group())
        out = _run(["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"])
        m = re.search(r"\d{6,}", out)
        return int(m.group()) if m else 0
    return 0


def _nvidia() -> tuple[str, int]:
    """(name, VRAM in bytes) of the first NVIDIA GPU, or ('', 0)."""
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if not out:
        return "", 0
    first = out.splitlines()[0]
    partes = [p.strip() for p in first.split(",")]
    if len(partes) < 2 or not partes[1].isdigit():
        return "", 0
    return partes[0], int(partes[1]) * 1024 * 1024


def _apple_silicon() -> tuple[bool, str]:
    if platform.system() != "Darwin":
        return False, ""
    chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    arm = platform.machine() in ("arm64", "aarch64")
    return arm, chip


def _disco_libre(path: str) -> int:
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return 0


# ------------------------------------------------------------------ perfil

@dataclass
class Perfil:
    so: str
    maquina: str
    acelerador: str          # human-readable description
    backend: str             # cuda | mps | cpu
    vram_gb: float           # dedicated VRAM, or unified memory on a Mac
    ram_gb: float
    disco_libre_gb: float
    dtype: str
    cuantizacion: str
    cuantizacion_te: str     # the text encoder follows the transformer: half and half is worse
    offload: str
    vram_limite_gb: float  # hard allocator ceiling; past it the run dies as an exception
    res_max: int           # with no reference
    res_max_ref: int       # with one photo in front, which costs twice the sequence
    res_max_multi: int     # with several: each one adds activations
    nivel: str               # XL | L | M | S | MINIMO | INVIABLE
    torch_index: str         # the pip index torch is installed from
    avisos: list
    viable: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


# The transformer is 7B and the text encoder is Qwen3-VL 8B. In bf16 the two
# together pass 30 GB, so on anything but a very large card there is always
# either offloading or quantisation in the way.
DESCARGA_GB = 34      # 31 for the model + ~0.8 for the auxiliaries


def detectar(destino_modelos: str | None = None) -> Perfil:
    so = platform.system()
    maquina = f"{platform.machine()} - {platform.processor() or 'cpu'}"
    ram = _ram_bytes() / GB
    disco = _disco_libre(destino_modelos or os.path.expanduser("~")) / GB
    avisos: list[str] = []

    nombre_gpu, vram_b = _nvidia()
    es_arm_mac, chip = _apple_silicon()

    if vram_b:
        backend = "cuda"
        acelerador = nombre_gpu
        vram = vram_b / GB
        torch_index = "https://download.pytorch.org/whl/cu128"
    elif es_arm_mac:
        backend = "mps"
        acelerador = chip or "Apple Silicon"
        # on Apple Silicon the memory is unified: the GPU uses system RAM
        vram = ram
        torch_index = ""     # the default PyPI wheel already carries MPS
        avisos.append("Unified memory: the GPU shares system RAM, so close heavy "
                      "applications before generating.")
    else:
        backend = "cpu"
        acelerador = platform.processor() or "CPU"
        vram = 0.0
        torch_index = ""

    # --- choosing the level ------------------------------------------------
    # The table comes from what was measured on 2026-09-22 on an RTX 5090
    # Laptop (24 GB), a portrait WITH a reference photo, 30 steps, same seed:
    #
    #   bf16           1 MP   73 s  23.9 GB  |  4 MP  never finishes, pages
    #   nf4 encoder    1 MP  112 s  19.0 GB  |  quantising halfway is worst
    #   nf4 both       1 MP   56 s  12.9 GB  |  4 MP  467 s, 24.0 GB peak
    #   int8 both      1 MP  pages  24.1 GB  |  bnb int8 is not GGUF's Q8
    #
    # Re-measured on 2026-09-23 with nf4 and VAE tiling on, sampling nvidia-smi
    # every 0.2 s. The peaks moved so far that the older table no longer
    # described this app:
    #
    #   generate 1 MP   26 s   7.3 GB      generate 2 MP   51 s   7.3 GB
    #   generate 4 MP  122 s   7.5 GB      edit      1 MP   26 s   9.2 GB
    #   rescale to 2K (the picture is its own reference)  156 s  18.2 GB
    #
    # Generating at 2K costs 7.5 GB and editing at 2K costs 18.2. Those are two
    # different ceilings and there used to be one, which is how 2048 came to be
    # promised to cards that paged the moment a photo went in front of them.
    #
    # What this file said before was measured without a reference and promised
    # 2048 on 24 GB. With a reference that does not hold. And the opposite of
    # what it claimed: on 24 GB nf4 is not the poor mode but the good one --
    # faster than bf16, half the memory, the only way to 2K, and at the same
    # seed indistinguishable by eye. bf16 only wins when the weights fit whole.
    if backend == "cuda":
        # Three sizes and not one: alone, with one reference in front of it,
        # and with several. Measured on 24 GB -- 7.5 GB generating at 2K, 18.2
        # rescaling, 19.2 on a portrait, and two references at 2K took the
        # kernel down. The one- and several-reference numbers sit below what
        # survived rather than at the edge, because the edge has already shown
        # what it costs.
        if vram >= 40:
            # here the 29.6 GB of weights do fit without being broken up
            nivel, dtype, cuant, off = "XL", "bfloat16", "none", "none"
            res, res_ref, res_multi = 2048, 2048, 1536
        elif vram >= 20:
            # int8 here and four bits below it: the eight-bit path peaked at
            # 12.1 GB on this portrait against nf4's 10.1, which a 20 GB card
            # has room for and a 12 GB one does not.
            nivel, dtype, cuant, off = "L", "bfloat16", "int8", "model"
            # 1536 with a reference was inherited from the night 2K with one
            # took the machine down, and never revisited. Walked again on
            # 2026-09-23 with the allocator ceiling in place, which turns the
            # wall into an exception: 1536 peaks at 14.7 GB, 1792 at 17.0,
            # and 2048 is the wall. So 1792, with 3.3 GB to spare.
            res, res_ref, res_multi = 2048, 1792, 1024
        elif vram >= 12:
            nivel, dtype, cuant, off = "M", "bfloat16", "int4", "model"
            res, res_ref, res_multi = 2048, 1024, 1024
        elif vram >= 8:
            # "model" and not "sequential": see the note below
            nivel, dtype, cuant, off = "S", "bfloat16", "int4", "model"
            res, res_ref, res_multi = 1536, 1024, 1024
        else:
            nivel, dtype, cuant, off = "MINIMO", "bfloat16", "int4", "model"
            res, res_ref, res_multi = 1024, 1024, 1024
            avisos.append(f"Only {vram:.0f} GB of VRAM. It will run, but slowly, and a "
                          f"reference photo may not fit at all.")
        # Sequential offload does NOT work with nf4 weights. Reproduced on
        # 2026-09-23 at 0.5 MP and 8 steps: "NotImplementedError: Cannot copy
        # out of meta tensor; no data!" -- accelerate cannot move layer by
        # layer what bitsandbytes has already quantised. These two profiles
        # carried it, so cards under 12 GB could not produce a single image,
        # and nobody saw it because the only card here has 24.
        #
        # "model" moves whole components rather than layers and does work with
        # nf4. On a small card it will be tight -- the text encoder in nf4 is
        # ~4.7 GB -- but tight and working beats roomy and broken. Unmeasured:
        # there is nothing here to measure it on.
        if ram < 24:
            avisos.append(f"With {ram:.0f} GB of RAM, offloading to system memory is "
                          f"tight; 32 GB or more is comfortable.")

    elif backend == "mps":
        # bitsandbytes has no MPS support, so on a Mac there is no
        # quantisation: the levers are dtype and offload.
        if vram >= 64:
            nivel, dtype, cuant, off = "XL", "bfloat16", "none", "none"
            res, res_ref, res_multi = 2048, 2048, 2048
        elif vram >= 48:
            nivel, dtype, cuant, off = "L", "bfloat16", "none", "model"
            res, res_ref, res_multi = 2048, 2048, 2048
        elif vram >= 32:
            nivel, dtype, cuant, off = "M", "bfloat16", "none", "sequential"
            res, res_ref, res_multi = 1536, 1536, 1536
        elif vram >= 24:
            nivel, dtype, cuant, off = "S", "float16", "none", "sequential"
            res, res_ref, res_multi = 1024, 1024, 1024
            avisos.append("With 24 GB unified, layers are swapped constantly; a 1024 px "
                          "image can take several minutes.")
        else:
            nivel, dtype, cuant, off = "INVIABLE", "float16", "none", "sequential"
            res, res_ref, res_multi = 1024, 1024, 1024
            avisos.append(f"With {vram:.0f} GB unified the model does not fit usefully. "
                          f"A Mac needs 24 GB at minimum, 32 GB to be comfortable.")
    else:
        nivel, dtype, cuant, off = "INVIABLE", "float32", "none", "sequential"
        res, res_ref, res_multi = 1024, 1024, 1024
        avisos.append("No compatible GPU. On CPU a single image can take over half an "
                      "hour; not a practical way to use this.")

    if disco < DESCARGA_GB + 5:
        avisos.append(f"{disco:.0f} GB free; the weights need ~{DESCARGA_GB} GB, plus "
                      f"room to work.")

    # measured: quantising only one of the two is worse than quantising
    # neither (nf4 on the text encoder alone gave 112 s against 73 s in bf16),
    # so the encoder follows the transformer and is not decided separately
    cuant_te = cuant

    # The allocator's hard ceiling. Two blue screens on 2026-09-23, same
    # bugcheck and the same parameters, both while pushing the VRAM of a 24 GB
    # card against its wall: the driver breaks under an allocation it cannot
    # serve and, with the hypervisor in the path, takes the kernel down instead
    # of resetting itself. Reserving below the total is not caution, it is the
    # difference between a Python exception and a reboot.
    #
    # The reserve is proportional rather than fixed: 4 GB out of 24 is the
    # right margin, 4 GB out of 8 would be half the card. 15%, capped at 4 so a
    # large card does not give away more than it needs, floored at 1.5 so a
    # small one keeps something. The desktop, the browser and whatever the
    # driver itself reserves all live in that gap.
    #
    # CUDA only: set_per_process_memory_fraction does not exist on MPS, so on a
    # Mac there is no ceiling to set and the field is zero.
    if backend == "cuda":
        limite = round(vram - min(4.0, max(1.5, vram * 0.15)), 1)
    else:
        limite = 0.0

    viable = nivel != "INVIABLE" and disco >= DESCARGA_GB

    return Perfil(so=so, maquina=maquina, acelerador=acelerador, backend=backend,
                  vram_gb=round(vram, 1), ram_gb=round(ram, 1), disco_libre_gb=round(disco, 1),
                  dtype=dtype, cuantizacion=cuant, cuantizacion_te=cuant_te,
                  vram_limite_gb=limite,
                  offload=off, res_max=res, res_max_ref=res_ref,
                  res_max_multi=res_multi, nivel=nivel,
                  torch_index=torch_index, avisos=avisos, viable=viable)


def resumen(p: Perfil) -> str:
    # Pure ASCII: this prints in the installer's console, which on Windows
    # opens in cp1252 and turns any pretty character into a question mark
    L = [
        f"  System         {p.so} - {p.maquina}",
        f"  Accelerator    {p.acelerador}",
        f"  Backend        {p.backend}",
        f"  {'Unified mem' if p.backend=='mps' else 'VRAM':<14} {p.vram_gb:.1f} GB",
        f"  RAM            {p.ram_gb:.1f} GB",
        f"  Free disk      {p.disco_libre_gb:.1f} GB   (~{DESCARGA_GB} GB needed)",
        "",
        f"  Profile        {p.nivel}",
        f"  dtype          {p.dtype}",
        f"  Quantisation   {p.cuantizacion}",
        f"  Offload        {p.offload}",
        (f"  VRAM ceiling   {p.vram_limite_gb:.1f} GB of {p.vram_gb:.1f}"
         if p.vram_limite_gb else ""),
        f"  Max resolution {p.res_max}"
        + (f" ({p.res_max_ref} with a reference photo)"
           if p.res_max_ref != p.res_max else ""),
    ]
    if p.avisos:
        L.append("")
        for a in p.avisos:
            L.append(f"  ! {a}")
    return "\n".join(L)


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else None
    p = detectar(destino)
    print(resumen(p))
    print()
    print("viable:", p.viable)
