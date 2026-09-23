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
AFINADOR = "facebook/sam2.1-hiera-tiny"      # 31M, ~150 MB

_sam: dict = {"modelo": None, "processor": None, "error": ""}

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


def afinador_disponible() -> bool:
    return _sam["modelo"] is not None


def cargar_afinador(device: str = "cuda", cache: str | None = None) -> bool:
    """Load SAM 2, which sharpens a rough mask. Returns whether it is usable."""
    with _lock:
        if _sam["modelo"] is not None:
            return True
        try:
            import torch
            from transformers import Sam2Model, Sam2Processor
            kw = {"cache_dir": cache} if cache else {}
            proc = Sam2Processor.from_pretrained(AFINADOR, **kw)
            m = Sam2Model.from_pretrained(AFINADOR, dtype=torch.float32, **kw)
            m = m.to(device).eval()
            _sam.update(modelo=m, processor=proc, error="", device=device)
            return True
        except Exception as e:
            _sam["error"] = f"{type(e).__name__}: {e}"
            return False


def soltar_afinador() -> None:
    with _lock:
        if _sam["modelo"] is not None:
            try:
                _sam["modelo"].to("cpu")
            except Exception:
                pass
        _sam.update(modelo=None, processor=None)


def afinar(imagen, burda):
    """Sharpen a rough text-driven mask with SAM 2.

    CLIPSeg works at 352x352 and its output, scaled back up, bleeds across
    edges -- measured here, it took in the hair falling over the garment it was
    asked for. SAM 2 does not take text, so CLIPSeg's bounding box and centre
    of mass go in as the prompt and SAM 2 returns the object that is actually
    there.

    Returns the original mask untouched if the refiner is not loaded or the
    rough mask is empty: a worse mask beats an exception.
    """
    if _sam["modelo"] is None:
        return burda
    try:
        import numpy as np
        import torch
        from PIL import Image

        a = np.asarray(burda.convert("L")) > 127
        if not a.any():
            return burda
        ys, xs = np.nonzero(a)
        caja = [[[float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]]]
        centro = [[[[float(xs.mean()), float(ys.mean())]]]]

        m, proc = _sam["modelo"], _sam["processor"]
        ent = proc(images=imagen.convert("RGB"), input_boxes=caja, input_points=centro,
                   input_labels=[[[1]]], return_tensors="pt").to(m.device)
        with torch.inference_mode():
            sal = m(**ent, multimask_output=False)
        ms = proc.post_process_masks(sal.pred_masks.cpu(), ent["original_sizes"].cpu())[0]
        arr = ms[0, 0].numpy() if ms.ndim == 4 else ms[0].numpy()
        fina = Image.fromarray((arr > 0).astype("uint8") * 255)
        if fina.size != imagen.size:
            fina = fina.resize(imagen.size, Image.NEAREST)
        # if SAM comes back with almost nothing it misread the box: the crude
        # mask is the better answer
        if (np.asarray(fina) > 127).mean() < 0.005:
            return burda
        return fina
    except Exception as e:
        _sam["error"] = f"{type(e).__name__}: {e}"
        return burda


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
