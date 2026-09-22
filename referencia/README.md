# Reference material

ComfyUI workflows for Qwen-Image 2.1 that were read while building this, kept
here because reading them is how several of the decisions in this project were
made. They are **not** used by the app — QwenStudio goes through diffusers and
has no ComfyUI dependency — and they are not ours: each one belongs to its
author on Civitai.

| File | Source | What was taken from it |
|---|---|---|
| `qwen21T2IAndEdit_v10.json` | [T2I and editing workflow](https://civitai.com/models/2954383/qwen-image-2-1-t2i-and-editing-workflow) | The official 2K resolution table, the RGBA prompt wrapper, and the confirmation that cfg stays at 1 |
| `qwen212KUpscale_v10.json` | [2K upscale workflow](https://civitai.com/models/2952715/qwen-21-2k-upscale-workflow) | The upscale arithmetic and prompt — see below |
| `qwenImage21Inpainting_v10.json` | [Inpainting workflow](https://civitai.com/models/2956061/qwen-image-21-inpainting-workflow) | It selects with SAM 3 where we use CLIPSeg |
| `qwen21WithPromptEnchancer_v12.json` | [Prompt enhancer](https://civitai.com/models/2951814/qwen-21-with-prompt-enchancer-100percent-of-understanding) | The idea, not the mechanism — see below |

---

## The 2K upscale, and why it is not in the interface

The technique is sound and it is implemented: the image goes back in as its own
reference, the target size is the whole 2K budget (area scaled towards
2048×2048, capped at four times per side, which is exactly the arithmetic in
`qwen212KUpscale_v10.json`), and the model redraws it larger. That recovers real
detail rather than interpolating pixels, and it works.

It is not offered in the interface because of what it costs. Measured here:

| | |
|---|---|
| 775×1024 → 1792×2048 | **754 s** (12.5 minutes) |
| card | RTX 5090 Laptop, 24 GB, profile L |

Twelve minutes for one upscale is not a feature, it is a dare. 2K is four times
the pixels of a normal run and the weights get swapped throughout, so on any
card that needs offload this is what it costs. On a 48 GB card with nothing
offloaded it would be a different conversation.

The endpoint stays — `POST /api/reescalar` with `{"imagen": "<data url>"}` —
so anyone with the hardware, or the patience, can use it knowing what they are
in for. It is simply not presented as though it were ready.

## The prompt enhancer

That workflow sends the prompt through a translation API and then a hosted LLM.
The idea is good; the plumbing is not, for a project whose whole point is that
nothing leaves the machine. QwenStudio does the same rewrite with the Qwen3-VL
that is already resident for describing images — text only, no network, about
19 s — with a system prompt built from the rules measured in this project
rather than a generic "make it better". See `qwenstudio/vision.py`.

## SAM 3 for selection

The inpainting workflow selects with SAM 3, which is a better segmenter than
the CLIPSeg used here. It is a real improvement and it is not implemented,
because it is another model to download and mount and none of it has been
tested against this pipeline. Written down rather than quietly ignored.
