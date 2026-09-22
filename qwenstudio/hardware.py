"""Deteccion de hardware y eleccion del perfil de ejecucion.

No depende de torch: corre antes de instalar nada, para poder decidir QUE
instalar. Usa solo la stdlib mas utilidades del sistema (nvidia-smi, sysctl,
wmic) y, si torch ya esta disponible, lo aprovecha para afinar.

El perfil decide cuatro cosas:
    backend      cuda | mps | cpu
    dtype        bfloat16 | float16 | float32
    cuantizacion none | int8 | int4        (solo CUDA: bitsandbytes no va en MPS)
    offload      none | model | sequential

La descarga de pesos es la misma en todos los perfiles (~33 GB del repo
diffusers de Qwen). Lo que cambia es como se cargan.
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
    """(nombre, VRAM en bytes) de la primera GPU NVIDIA, o ('', 0)."""
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
    acelerador: str          # descripcion legible
    backend: str             # cuda | mps | cpu
    vram_gb: float           # VRAM dedicada, o memoria unificada en Mac
    ram_gb: float
    disco_libre_gb: float
    dtype: str
    cuantizacion: str
    offload: str
    res_max: int
    nivel: str               # XL | L | M | S | MINIMO | INVIABLE
    torch_index: str         # indice de pip para instalar torch
    avisos: list
    viable: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


# El transformer son 7B y el text encoder Qwen3-VL 8B. En bf16 los dos juntos
# pasan de 30 GB, asi que salvo en tarjetas muy grandes siempre hay offload o
# cuantizacion de por medio.
DESCARGA_GB = 33


def detectar(destino_modelos: str | None = None) -> Perfil:
    so = platform.system()
    maquina = f"{platform.machine()} · {platform.processor() or 'cpu'}"
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
        # en Apple Silicon la memoria es unificada: la GPU usa la RAM del sistema
        vram = ram
        torch_index = ""     # el wheel por defecto de PyPI ya trae MPS
        avisos.append("Unified memory: the GPU shares system RAM, so close heavy "
                      "applications before generating.")
    else:
        backend = "cpu"
        acelerador = platform.processor() or "CPU"
        vram = 0.0
        torch_index = ""

    # --- eleccion de nivel -------------------------------------------------
    # Nota medida el 2026-09-21 en una RTX 5090 Laptop (24 GB): cuantizar a int8
    # con bitsandbytes resulto CONTRAPRODUCENTE -- 2.8 s/paso y 24.1 GB de pico,
    # contra 1.26 s/paso y 21.2 GB sin cuantizar. bnb int8 castea bf16<->fp16 en
    # cada matmul. Por eso int8 no aparece en la escalera: el transformer en
    # bf16 son 14.2 GB y cabe de sobra si el text encoder se descarga tras
    # codificar, que es justo lo que hace el offload de modelo.
    if backend == "cuda":
        if vram >= 40:
            nivel, dtype, cuant, off, res = "XL", "bfloat16", "none", "none", 2048
        elif vram >= 20:
            nivel, dtype, cuant, off, res = "L", "bfloat16", "none", "model", 2048
        elif vram >= 16:
            nivel, dtype, cuant, off, res = "M", "bfloat16", "none", "sequential", 1536
        elif vram >= 10:
            # aqui el transformer bf16 ya no entra; nf4 es la unica via y ademas
            # bnb en 4 bits es mas rapido que en 8
            nivel, dtype, cuant, off, res = "S", "bfloat16", "int4", "sequential", 1024
        else:
            nivel, dtype, cuant, off, res = "MINIMO", "bfloat16", "int4", "sequential", 1024
            avisos.append(f"Only {vram:.0f} GB of VRAM. It will run, but slowly and with "
                          f"quality reduced by 4-bit quantisation.")
        if ram < 24:
            avisos.append(f"With {ram:.0f} GB of RAM, offloading to system memory is "
                          f"tight; 32 GB or more is comfortable.")

    elif backend == "mps":
        # bitsandbytes no soporta MPS, asi que en Mac no hay cuantizacion:
        # el ajuste es dtype y offload.
        if vram >= 64:
            nivel, dtype, cuant, off, res = "XL", "bfloat16", "none", "none", 2048
        elif vram >= 48:
            nivel, dtype, cuant, off, res = "L", "bfloat16", "none", "model", 2048
        elif vram >= 32:
            nivel, dtype, cuant, off, res = "M", "bfloat16", "none", "sequential", 1536
        elif vram >= 24:
            nivel, dtype, cuant, off, res = "S", "float16", "none", "sequential", 1024
            avisos.append("With 24 GB unified, layers are swapped constantly; a 1024 px "
                          "image can take several minutes.")
        else:
            nivel, dtype, cuant, off, res = "INVIABLE", "float16", "none", "sequential", 1024
            avisos.append(f"With {vram:.0f} GB unified the model does not fit usefully. "
                          f"A Mac needs 24 GB at minimum, 32 GB to be comfortable.")
    else:
        nivel, dtype, cuant, off, res = "INVIABLE", "float32", "none", "sequential", 1024
        avisos.append("No compatible GPU. On CPU a single image can take over half an "
                      "hour; not a practical way to use this.")

    if disco < DESCARGA_GB + 5:
        avisos.append(f"{disco:.0f} GB free; the weights need ~{DESCARGA_GB} GB, plus "
                      f"room to work.")

    viable = nivel != "INVIABLE" and disco >= DESCARGA_GB

    return Perfil(so=so, maquina=maquina, acelerador=acelerador, backend=backend,
                  vram_gb=round(vram, 1), ram_gb=round(ram, 1), disco_libre_gb=round(disco, 1),
                  dtype=dtype, cuantizacion=cuant, offload=off, res_max=res, nivel=nivel,
                  torch_index=torch_index, avisos=avisos, viable=viable)


def resumen(p: Perfil) -> str:
    L = [
        f"  Sistema        {p.so} · {p.maquina}",
        f"  Acelerador     {p.acelerador}",
        f"  Backend        {p.backend}",
        f"  {'Unified' if p.backend=='mps' else 'VRAM':<14} {p.vram_gb:.1f} GB",
        f"  RAM            {p.ram_gb:.1f} GB",
        f"  Disco libre    {p.disco_libre_gb:.1f} GB   (hacen falta ~{DESCARGA_GB} GB)",
        "",
        f"  Perfil         {p.nivel}",
        f"  dtype          {p.dtype}",
        f"  Cuantizacion   {p.cuantizacion}",
        f"  Offload        {p.offload}",
        f"  Resolucion max {p.res_max}",
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
