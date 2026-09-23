"""Mount and unmount the heavy models that share one GPU.

Three of them take turns on the same card:

    imagen    Qwen-Image 2.1, the 7B DiT. With model offload its weights live
              in CPU RAM and it costs ~0.4 GB while idle, rising to ~21 GB only
              while it generates. Never unmounted: reloading costs ~30 s and
              buys nothing, because idle it is not in the way.
    vision    Qwen3-VL-8B in 4-bit, ~7 GB, resident once mounted.
    segmenta  CLIPSeg, ~0.6 GB, resident once mounted.

Running out of headroom does not raise a clean error: the GPU reports 100%
utilisation, power draw stays low and nothing finishes. So every block declares
what it needs and whatever conflicts is unmounted first.
"""

from __future__ import annotations

import threading

_lock = threading.RLock()

# who needs the card -> who has to let go of it first
CONFLICTOS = {
    "imagen": ("vision", "segmenta"),   # generating climbs to ~21 GB: nothing else fits
    "vision": ("segmenta",),            # 7 GB sit beside the idle DiT
    "segmenta": ("vision",),
}


class Registro:
    def __init__(self):
        self._mods: dict[str, dict] = {}

    def registrar(self, nombre: str, *, montado, desmontar, vram_gb: float = 0.0,
                  etiqueta: str = "") -> None:
        """`montado` is a callable returning bool; `desmontar` frees it."""
        self._mods[nombre] = {"montado": montado, "desmontar": desmontar,
                              "vram_gb": vram_gb, "etiqueta": etiqueta or nombre}

    def usar(self, quien: str) -> list[str]:
        """Free what `quien` conflicts with. Returns what was unmounted."""
        soltados = []
        with _lock:
            for otro in CONFLICTOS.get(quien, ()):
                mod = self._mods.get(otro)
                if mod and mod["montado"]():
                    mod["desmontar"]()
                    soltados.append(otro)
        return soltados

    def desmontar_todo(self, excepto: str | None = None) -> list[str]:
        soltados = []
        with _lock:
            for nombre, mod in self._mods.items():
                if nombre != excepto and mod["montado"]():
                    mod["desmontar"]()
                    soltados.append(nombre)
        return soltados

    def estado(self) -> list[dict]:
        return [{"nombre": n, "etiqueta": m["etiqueta"],
                 "montado": bool(m["montado"]()), "vram_gb": m["vram_gb"]}
                for n, m in self._mods.items()]


registro = Registro()
