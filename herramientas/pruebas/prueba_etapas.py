# -*- coding: utf-8 -*-
"""Two pipelines, separate lifetimes, and one resize shared by both.

The memory question is answered: loading the text encoder alone, encoding,
dropping it and only then loading the transformer got int8 on both all the way
to the sampling loop, which the single eager pipeline could not do at all.

What broke next was mine. `__call__` resizes every condition image itself --
`calculate_dimensions(resolution^2, aspect)` rounded to multiples of 32 -- and
that same resized image feeds the text encoder and the VAE. Stage 1 got the
original 512x512 and stage 2 the 1024x1024 version, so the two disagreed about
how many vision slots the encoder had reserved: 5168 tokens against 8240.

So the resize happens once, up front, and both stages get the same picture.
That is what the graph does too: LoadAndResizeImage sits before the encode
node, not inside it.
"""
import gc, json, math, os, sys, time

APP = r"D:\QwenStudio"
os.chdir(APP)
sys.path.insert(0, APP)

import torch
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
TEXTO = ("A colour editorial magazine portrait. The subject wears a black tailored "
         "blazer over a white shirt, standing in a sunlit concrete gallery, hard "
         "side light from a tall window, deep shadows, shot on medium format.")
RESOLUCION = 1024

base = json.load(open("config.json", encoding="utf-8-sig"))
torch.cuda.set_per_process_memory_fraction(base["vram_limite_gb"] / 23.86)
RUTA = base["ruta_modelos"]


def vram(etiqueta):
    torch.cuda.synchronize()
    print("    [vram] %-24s reserved %5.1f GB  allocated %5.1f GB"
          % (etiqueta, torch.cuda.memory_reserved() / 2 ** 30,
             torch.cuda.memory_allocated() / 2 ** 30), flush=True)


def limpiar():
    gc.collect()
    torch.cuda.empty_cache()


def preparar(img, resolucion=RESOLUCION):
    """The pipeline's own preprocessing, done once so both stages agree."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    ratio = w / h
    ancho = round(math.sqrt(resolucion * resolucion * ratio) / 32) * 32
    alto = round((ancho / ratio) / 32) * 32
    return img.resize((ancho, alto), Image.LANCZOS)


def _bnb(clase, modo, dtype):
    if modo == "int8":
        return clase(load_in_8bit=True)
    return clase(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                 bnb_4bit_compute_dtype=dtype)


def correr(quant_dit, quant_te, etiqueta):
    from diffusers import QwenImage21Pipeline, PipelineQuantizationConfig
    from diffusers import BitsAndBytesConfig as DiffBnb
    from transformers import BitsAndBytesConfig as TrfBnb

    refs = [preparar(Image.open(os.path.join(APP, "ejemplos", "person.jpg")))]
    print("\n=== %s (DiT %s, TE %s) ===" % (etiqueta, quant_dit, quant_te), flush=True)
    print("  reference prepared at %s" % (refs[0].size,), flush=True)

    # --- stage 1: the text encoder, alone on the card --------------------
    t0 = time.time()
    p1 = QwenImage21Pipeline.from_pretrained(
        RUTA, torch_dtype=torch.bfloat16, transformer=None, vae=None,
        quantization_config=PipelineQuantizationConfig(
            quant_mapping={"text_encoder": _bnb(TrfBnb, quant_te, torch.bfloat16)}))
    print("  stage 1 loaded in %.0fs" % (time.time() - t0), flush=True)
    vram("text encoder resident")

    t1 = time.time()
    trio = p1.encode_prompt(prompt=TEXTO, image=refs, device=torch.device("cuda"))
    print("  encoded in %.0fs" % (time.time() - t1), flush=True)
    trio = tuple(x.detach().to("cpu") if torch.is_tensor(x) else x for x in trio)

    del p1
    limpiar()
    vram("text encoder gone")

    # --- stage 2: the transformer and the VAE ----------------------------
    t2 = time.time()
    p2 = QwenImage21Pipeline.from_pretrained(
        RUTA, torch_dtype=torch.bfloat16, text_encoder=None, tokenizer=None,
        quantization_config=PipelineQuantizationConfig(
            quant_mapping={"transformer": _bnb(DiffBnb, quant_dit, torch.bfloat16)}))
    p2.to("cuda")
    print("  stage 2 loaded in %.0fs" % (time.time() - t2), flush=True)
    vram("transformer resident")

    dev = torch.device("cuda")
    respuestas = [tuple(x.to(dev) if torch.is_tensor(x) else x for x in trio)]
    original = p2.encode_prompt
    p2.encode_prompt = lambda *a, **k: respuestas.pop(0)
    try:
        t3 = time.time()
        gen = torch.Generator(device="cpu").manual_seed(301)
        out = p2(prompt=TEXTO, image=refs, num_inference_steps=28,
                 true_cfg_scale=1.0, generator=gen, output_resolution=RESOLUCION)
        print("  sampled in %.0fs" % (time.time() - t3), flush=True)
        vram("after sampling")
    finally:
        p2.encode_prompt = original

    destino = os.path.join(AQUI, "etapas_%s.png" % etiqueta)
    out.images[0].save(destino)
    print("  %s  %s" % (out.images[0].size, destino), flush=True)
    print("  TOTAL %.0fs" % (time.time() - t0), flush=True)

    del p2
    limpiar()


if __name__ == "__main__":
    correr("int8", "int8", "int8_int8")
    print("\ndone", flush=True)
