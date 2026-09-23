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
    cuantizacion_te: str     # el text encoder sigue al transformer: a medias sale peor
    offload: str
    vram_limite_gb: float  # techo duro del asignador; lo que pase muere como excepcion
    res_max: int           # sin referencia
    res_max_ref: int       # con una foto delante, que cuesta el doble largo
    res_max_multi: int     # con varias: cada una suma activaciones
    nivel: str               # XL | L | M | S | MINIMO | INVIABLE
    torch_index: str         # indice de pip para instalar torch
    avisos: list
    viable: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


# El transformer son 7B y el text encoder Qwen3-VL 8B. En bf16 los dos juntos
# pasan de 30 GB, asi que salvo en tarjetas muy grandes siempre hay offload o
# cuantizacion de por medio.
DESCARGA_GB = 34      # 31 el modelo + ~0.8 los auxiliares


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
    # La tabla sale de lo medido el 2026-09-22 en una RTX 5090 Laptop (24 GB),
    # retrato CON foto de referencia, 30 pasos, misma semilla:
    #
    #   bf16          1 MP   73 s  23.9 GB  |  4 MP  no termina, pagina
    #   nf4 solo TE   1 MP  112 s  19.0 GB  |  cuantizar a medias es lo peor
    #   nf4 ambos     1 MP   56 s  12.9 GB  |  4 MP  467 s, 24.0 GB de pico
    #   int8 ambos    1 MP  pagina 24.1 GB  |  bnb int8 no es el Q8 de GGUF
    #
    # Re-medido el 2026-09-23 con nf4 y el tiling del VAE puesto, muestreando
    # nvidia-smi cada 0.2 s. Los picos cambiaron tanto que la tabla anterior ya
    # no describia esta app:
    #
    #   generar 1 MP   26 s    7.3 GB      generar 2 MP   51 s   7.3 GB
    #   generar 4 MP  122 s    7.5 GB      editar  1 MP   26 s   9.2 GB
    #   reescalar a 2K (la imagen es su propia referencia)  156 s  18.2 GB
    #
    # Generar a 2K cuesta 7.5 GB y editar a 2K cuesta 18.2. Son dos techos
    # distintos y antes habia uno solo, que es como se prometio 2048 a tarjetas
    # que luego paginaban en cuanto se les ponia una foto delante.
    #
    # Lo que este archivo decia antes se midio sin referencia y prometia 2048
    # en 24 GB. Con referencia eso no se sostiene. Y al revés de lo que ponia:
    # en 24 GB nf4 no es el modo pobre, es el bueno -- mas rapido que bf16,
    # la mitad de memoria, unica via a 2K, y a la misma semilla la calidad no
    # se distingue. bf16 solo gana si los pesos caben enteros.
    if backend == "cuda":
        # Tres tamanos y no uno: solo, con una referencia delante, y con
        # varias. Medido en 24 GB -- 7.5 GB generando a 2K, 18.2 reescalando,
        # 19.2 en un retrato, y dos referencias a 2K se llevaron el kernel.
        # Los de una y varias van por debajo de lo que sobrevivio, no en el
        # borde, porque el borde ya demostro lo que cuesta.
        if vram >= 40:
            # aqui si caben los 29.6 GB de pesos sin trocear
            nivel, dtype, cuant, off = "XL", "bfloat16", "none", "none"
            res, res_ref, res_multi = 2048, 2048, 1536
        elif vram >= 20:
            nivel, dtype, cuant, off = "L", "bfloat16", "int4", "model"
            res, res_ref, res_multi = 2048, 1536, 1024
        elif vram >= 12:
            nivel, dtype, cuant, off = "M", "bfloat16", "int4", "model"
            res, res_ref, res_multi = 2048, 1024, 1024
        elif vram >= 8:
            nivel, dtype, cuant, off = "S", "bfloat16", "int4", "sequential"
            res, res_ref, res_multi = 1536, 1024, 1024
        else:
            nivel, dtype, cuant, off = "MINIMO", "bfloat16", "int4", "sequential"
            res, res_ref, res_multi = 1024, 1024, 1024
            avisos.append(f"Only {vram:.0f} GB of VRAM. It will run, but slowly, and a "
                          f"reference photo may not fit at all.")
        if ram < 24:
            avisos.append(f"With {ram:.0f} GB of RAM, offloading to system memory is "
                          f"tight; 32 GB or more is comfortable.")

    elif backend == "mps":
        # bitsandbytes no soporta MPS, asi que en Mac no hay cuantizacion:
        # el ajuste es dtype y offload.
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

    # medido: cuantizar solo uno de los dos es peor que no cuantizar ninguno
    # (nf4 solo en el text encoder dio 112 s contra 73 s en bf16), asi que el
    # encoder sigue al transformer y no se decide por separado
    cuant_te = cuant

    # El techo duro del asignador. Dos pantallazos azules el 2026-09-23, mismo
    # bugcheck y mismos parametros, los dos empujando la VRAM contra el muro de
    # una tarjeta de 24 GB: el driver se rompe bajo una reserva imposible y,
    # con el hipervisor de por medio, se lleva el kernel en vez de reiniciarse
    # solo. Reservar por debajo del total no es prudencia, es la diferencia
    # entre una excepcion de Python y un reinicio.
    #
    # La reserva es proporcional y no fija: 4 GB sobre 24 es el margen justo,
    # 4 GB sobre 8 seria media tarjeta. Un 15%, con techo de 4 para que una
    # tarjeta grande no regale de mas y suelo de 1.5 para que una pequena
    # conserve algo. El escritorio, el navegador y lo que el propio driver
    # reserva viven en ese hueco.
    #
    # Solo CUDA: set_per_process_memory_fraction no existe en MPS, asi que en
    # Mac no hay techo que poner y el campo va a cero.
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
    # ASCII puro: esto se imprime en la consola del instalador, que en Windows
    # abre en cp1252 y convierte cualquier caracter bonito en un interrogante
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
