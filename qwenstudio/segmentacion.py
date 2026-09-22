"""Text-driven segmentation with CLIPSeg (MIT, ~600 MB).

You say "the jacket" and get back a mask, which the inpainting path turns into
a crop box. Several phrases are segmented in one batched pass.

Why not Florence-2: its weights ship with remote code written for transformers
4.x, and this app runs 5.x for diffusers. Loading it failed on three separate
incompatibilities in a row (config generation attributes, `_supports_sdpa`,
then the tokenizer's `additional_special_tokens`). CLIPSeg is supported
natively by transformers, needs no `trust_remote_code`, is a third of the size
and segments three phrases in under a second. Measured 2026-09-21.
"""

from __future__ import annotations

import threading

MODELO = "CIDAS/clipseg-rd64-refined"

_lock = threading.Lock()
_estado: dict = {"modelo": None, "processor": None, "error": "", "device": "cpu"}


def disponible() -> bool:
    return _estado["modelo"] is not None


def error() -> str:
    return _estado["error"]


def cargar(device: str = "cuda", cache: str | None = None) -> None:
    """Load CLIPSeg once. Safe to call repeatedly."""
    with _lock:
        if _estado["modelo"] is not None:
            return
        try:
            from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor
            kw = {"cache_dir": cache} if cache else {}
            proc = CLIPSegProcessor.from_pretrained(MODELO, **kw)
            m = CLIPSegForImageSegmentation.from_pretrained(MODELO, **kw).to(device).eval()
            _estado.update(modelo=m, processor=proc, error="", device=device)
        except Exception as e:
            _estado["error"] = f"{type(e).__name__}: {e}"


def descargar_de_memoria() -> None:
    """Free the VRAM it holds. It is small, but every GB counts next to a 7B DiT."""
    with _lock:
        if _estado["modelo"] is not None:
            try:
                _estado["modelo"].to("cpu")
            except Exception:
                pass
        _estado.update(modelo=None, processor=None)
    try:
        import gc

        import torch
        gc.collect()
        torch.cuda.empty_cache()
    except Exception:
        pass


def mascaras(imagen, frases: list[str], umbral: float = 0.5) -> list:
    """One binary mask (PIL 'L', image-sized) per phrase, in the same order.

    `umbral` is applied to the sigmoid of the logits: lower catches more of the
    object and more of its surroundings.
    """
    from PIL import Image

    if _estado["modelo"] is None:
        cargar(_estado.get("device", "cuda"))
    if _estado["modelo"] is None:
        raise RuntimeError(_estado["error"] or "CLIPSeg is not loaded")
    if not frases:
        return []

    import numpy as np
    import torch

    m, proc, dev = _estado["modelo"], _estado["processor"], _estado["device"]
    img = imagen.convert("RGB")

    entradas = proc(text=frases, images=[img] * len(frases),
                    padding=True, return_tensors="pt").to(dev)
    with torch.inference_mode():
        logits = m(**entradas).logits
    if logits.dim() == 2:                 # a single phrase comes back unbatched
        logits = logits.unsqueeze(0)

    salida = []
    for i in range(len(frases)):
        pr = torch.sigmoid(logits[i]).float().cpu().numpy()
        crudo = Image.fromarray((pr * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR)
        salida.append(crudo.point(lambda v: 255 if v > umbral * 255 else 0))
    return salida


def mascara(imagen, frase: str, umbral: float = 0.5):
    """Mask for one phrase. Raises if nothing passes the threshold."""
    m = mascaras(imagen, [frase], umbral)[0]
    if m.getbbox() is None:
        raise ValueError(f'nothing in the image matched "{frase}" '
                         f'(try a lower threshold or simpler wording)')
    return m
