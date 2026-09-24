"""Describe and reason about images with Qwen3-VL-8B.

No extra download: the image model's text encoder *is* Qwen3-VL-8B, and the
checkpoint on disk carries the vision tower (`model.visual`), the language
tower and `lm_head`, declared as `Qwen3VLForConditionalGeneration`. The same
16 GB serve both jobs.

Loaded in 4-bit by default. Captioning tolerates that far better than image
generation does, and it keeps the VLM small enough to sit beside the 7B DiT
instead of forcing a swap on every call.
"""

from __future__ import annotations

import os
import threading

_lock = threading.Lock()
_estado: dict = {"modelo": None, "processor": None, "error": "", "device": "cuda"}

# What to ask for. The wording matters: Qwen-Image 2.1 responds to natural,
# declarative description, so the prompt-writing tasks aim at that rather than
# at comma-separated tags.
TAREAS = {
    "prompt": (
        "Write a single detailed prompt that would let an image model recreate this "
        "photograph. Describe the subject, clothing, pose, setting, lighting, camera "
        "framing and mood in natural declarative English. One paragraph, no lists, no "
        "preamble, no quotation marks."),
    "describe": (
        "Describe this image in plain English: what is in it, how it is lit, how it is "
        "framed. Two or three sentences."),
    "caption": (
        "Write a training caption for this image: one natural sentence describing the "
        "subject and everything around them. No preamble."),
    "edit": (
        "Look at this image and suggest three specific, concrete edits that would "
        "improve it or make it more interesting. For each one give the short phrase "
        "naming what to select and the instruction for what to put there. Be practical."),
    "scene": (
        "Describe this photograph as a setting: the place, the clothing the person "
        "wears, the framing, and the quality and direction of the light. One sentence, "
        "in natural English, no preamble. Do not describe the person's face or identity."),
    "select": (
        "List the distinct objects and regions in this image that could be selected "
        "and edited separately. Give each as a short noun phrase, one per line, no "
        "numbering."),
}


def disponible() -> bool:
    return _estado["modelo"] is not None


def error() -> str:
    return _estado["error"]


def cargar(ruta_modelos: str, device: str = "cuda", bits: int = 4) -> None:
    """Load the VLM from the weights already on disk. Safe to call repeatedly."""
    with _lock:
        if _estado["modelo"] is not None:
            return
        try:
            import torch
            from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

            pesos = os.path.join(ruta_modelos, "text_encoder")
            proc_dir = os.path.join(ruta_modelos, "processor")
            kw: dict = {"dtype": torch.bfloat16}
            if device == "cuda" and bits in (4, 8):
                from transformers import BitsAndBytesConfig
                kw["quantization_config"] = (
                    BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                       bnb_4bit_compute_dtype=torch.bfloat16)
                    if bits == 4 else BitsAndBytesConfig(load_in_8bit=True))
                kw["device_map"] = {"": 0}
            m = Qwen3VLForConditionalGeneration.from_pretrained(pesos, **kw)
            if "device_map" not in kw:
                m = m.to(device)
            m.eval()
            proc = AutoProcessor.from_pretrained(proc_dir)
            _estado.update(modelo=m, processor=proc, error="", device=device)
        except Exception as e:
            _estado["error"] = f"{type(e).__name__}: {e}"


def descargar_de_memoria() -> None:
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


# How to turn a loose request into something this model reads well. The order is
# not decoration: the subject first because it carries the most weight, and the
# optics last because they carry the least. These rules were measured in this
# project rather than chosen as a matter of taste.
# The same, for editing, which is not the same job. A text-to-image request
# describes a photograph that does not exist; an edit names a change to one that
# does. None of the rules below is a matter of style: each cost an afternoon.
#
# The first three are QwenLM's, from the system_prompt_edit.txt in their repo,
# and all three were checked here on 2026-09-23 against the same person swap.
# What the reference is asked before anything is rewritten. Short and concrete:
# the rewriter only needs to know what is there in order to name it instead of
# guessing. Without this it wrote "the jacket and pants" about a t-shirt.
MIRAR_REFERENCIA = (
    "Describe only what this person looks like, in one sentence: the hair, the "
    "facial hair if any, and the clothing they are wearing with its colour and "
    "material. Name what you can see and nothing else. No preamble.")

REDACTAR_EDICION = """You rewrite instructions for an image editing model.
Rewrite the request below as one or two plain English sentences telling the model
what to change.

Rules, each of which decides whether the edit happens at all:
- Name the ATTRIBUTE that changes, never the person or the object as a whole.
  "Replace the woman with the man" changes nothing; "replace the face, the hair
  and the beard" works. If clothing should change too, say so separately.
- Prefer "put X from <image2> on ..." or "swap X for ...". Measured against the
  same picture and seed with only the verb changed: put and swap did the most,
  replace and change grafted the new feature onto the old face instead of
  exchanging it, and "give" and "edit to match" did almost nothing.
- When the request is to change WHO someone is, write two clauses, not one:
  put the face, the hair and the beard from <image2> on this person, AND change
  the clothing to something concrete. Measured: face, hair and beard alone
  grafted a beard onto the original face; adding the body and the build changed
  nothing further; listing "the clothing" among the things to copy left the
  original garment untouched; giving the clothing its own verb and its own
  concrete target produced the whole exchange. While the original jacket stays,
  the jacket holds the original person in place.
- Name only the features the reference actually has, and the list changes with
  the reference. Two rewrites of the same request, differing only in what the
  reference was found to show:
    reference is a bearded man in a maroon t-shirt ->
      "Put the face, the hair and the beard from <image2> on this person, and
       change the clothing to a maroon short-sleeved t-shirt."
    reference is a woman with cropped silver hair in a black blazer ->
      "Put the face and the hair from <image2> on this person, and change the
       clothing to a black blazer over a white shirt."
  Never ask for a beard on a reference that has none, and never invent a
  garment that is not there.
- Say "on this person", not "on the person in <image1>". Naming the subject of
  the picture being edited weakens the edit even when the tag is right, because
  the noun "person" is what the model ignores, wherever it appears. Tag the
  references; point at the target.
- Lead with the change. Anything about what stays goes after it, never before.
- Say what stays in general terms and do not describe it. Listing the place, the
  light and the framing makes the model repaint them, and what it repaints is
  the reference's, not the picture's.
- Refer to reference pictures as <image1>, <image2>, <image3>, never as "the
  first photo" or "the other one". Point at them instead of describing what is
  in them: a reference carries a likeness better than any sentence about it.
- Say only what should be there. There is no negative guidance here, so a thing
  you forbid is a thing you summoned.
- Ask for only what was requested. Do not add operations of your own.
- Keep any words the request put in double quotes exactly as they are, quotes
  included: those come out as lettering in the image.
- No preamble, no explanation, no lists. Return the instruction and nothing else.

Request: """


REDACTAR = """You rewrite prompts for an image model. Rewrite the request below as
one paragraph of natural declarative English, in this order: the subject, then the
clothing and the telling details, then the place, then the framing, then the light,
then the lens or the medium.

Rules:
- Say only what should be in the picture. Never write what should be absent: there
  is no negative guidance, so a thing you forbid is a thing you summoned.
- Name things that can be seen. "A brass diving helmet" works; "beautiful" and
  "masterpiece" give the model nothing to draw.
- Keep any words the request put in double quotes exactly as they are, quotes
  included: those come out as lettering in the image.
- Keep every concrete fact from the request. Add detail where it is silent, and
  invent nothing that contradicts it.
- Say "the subject" rather than he or she unless the request names a gender.
- No preamble, no explanation, no lists, no quotation marks around the whole
  answer. Return the paragraph and nothing else.

Request: """

# Added to either block when a reference photograph is loaded.
#
# Measured on 2026-09-23: the same request, the same seed, the same reference,
# with and without forty words of appearance wrapped around it. The bare version
# came back the more like the person. Text and reference go into the same
# encoder -- `encode_prompt` takes the condition images too -- so a written face
# and a photographed face arrive as rival descriptions of one thing and the
# model averages them. Who it is was settled when the photograph went in.
CON_REFERENCIA = """

Also, a photograph of the subject is already loaded:
- Their face, hair, build and skin are decided. Do not describe any of them, not
  even to say they should stay. Write the wardrobe, the place, the framing, the
  light and the lens, and let the photograph say who it is.
- Do not write "the same face", "identical features" or any other instruction to
  keep the likeness. The app adds that sentence itself, last, where it weighs
  most."""


def redactar(texto: str, max_tokens: int = 320,
             edicion: bool = False, contexto: str = "",
             con_referencia: bool = False) -> str:
    """Rewrite a loose request into a prompt this model reads well.

    `edicion` switches the rules: describing a picture that does not exist and
    naming a change to one that does are different jobs, and the rules that
    decide whether an edit happens at all are not the rules that make a good
    photograph.

    Text only, and the VLM is already resident for describing images, so the
    rewrite costs nothing extra to load and never leaves the machine.
    """
    if _estado["modelo"] is None:
        raise RuntimeError(_estado["error"] or "the vision model is not loaded")
    if not texto.strip():
        return ""

    import torch
    m, proc = _estado["modelo"], _estado["processor"]
    pie = texto.strip()
    if contexto.strip():
        # the facts go AFTER the request: the rewriter has to use them to name
        # things, not mistake them for what was asked
        pie += (chr(10) * 2 + "What the reference picture <image2> actually "
                "shows: " + contexto.strip())
    mensajes = [{"role": "user",
                 "content": [{"type": "text",
                              "text": (REDACTAR_EDICION if edicion else REDACTAR)
                                      + (CON_REFERENCIA if con_referencia else "")
                                      + pie}]}]
    plantilla = proc.apply_chat_template(mensajes, tokenize=False,
                                         add_generation_prompt=True)
    entradas = proc(text=[plantilla], return_tensors="pt")
    entradas = {k: v.to(m.device) for k, v in entradas.items()}
    with torch.inference_mode():
        salida = m.generate(**entradas, max_new_tokens=max_tokens, do_sample=False)
    nuevos = salida[0][entradas["input_ids"].shape[1]:]
    return proc.decode(nuevos, skip_special_tokens=True).strip().strip('"')


def preguntar(imagen, tarea: str = "prompt", extra: str = "",
              max_tokens: int = 320) -> str:
    """Run one of TAREAS (or a free question in `extra`) against the image."""
    if _estado["modelo"] is None:
        raise RuntimeError(_estado["error"] or "the vision model is not loaded")

    import torch
    m, proc = _estado["modelo"], _estado["processor"]
    instruccion = TAREAS.get(tarea, TAREAS["describe"])
    if extra.strip():
        instruccion = extra.strip() if tarea == "free" else f"{instruccion}\n\n{extra.strip()}"

    mensajes = [{"role": "user", "content": [
        {"type": "image"}, {"type": "text", "text": instruccion}]}]
    texto = proc.apply_chat_template(mensajes, tokenize=False, add_generation_prompt=True)
    entradas = proc(text=[texto], images=[imagen.convert("RGB")], return_tensors="pt")
    entradas = {k: v.to(m.device) for k, v in entradas.items()}

    with torch.inference_mode():
        salida = m.generate(**entradas, max_new_tokens=max_tokens, do_sample=False)
    nuevos = salida[0][entradas["input_ids"].shape[1]:]
    return proc.decode(nuevos, skip_special_tokens=True).strip()
