# Reference material

ComfyUI workflows for Qwen-Image 2.1 that were read while building this, kept
here because reading them is how several decisions in this project were made.
They are **not** used by the app — QwenStudio goes through diffusers and has no
ComfyUI dependency — and they are not ours: each belongs to its author on
Civitai.

| File | Source | What came out of reading it |
|---|---|---|
| `qwen21T2IAndEdit_v10.json` | [T2I and editing workflow](https://civitai.com/models/2954383/qwen-image-2-1-t2i-and-editing-workflow) | The official 2K resolution table, the RGBA prompt wrapper, and confirmation that cfg stays at 1 |
| `qwen212KUpscale_v10.json` | [2K upscale workflow](https://civitai.com/models/2952715/qwen-21-2k-upscale-workflow) | The upscale arithmetic and prompt — implemented, then pulled. See below |
| `SeedVR upscale.json` | [T2I + Edit workflows](https://civitai.com/models/2951890/qwen-image-21-workflows-t2i-edit-with-sageattention) | The answer to upscaling is not this model. See below |
| `Qwen Image 2.1 T2I.json` | same pack | Uses SageAttention and `QwenImage21Cache`. See below |
| `qwenImage21Inpainting_v10.json` | [Inpainting workflow](https://civitai.com/models/2956061/qwen-image-21-inpainting-workflow) | It selects with SAM 3 where we use CLIPSeg |
| `qwen21WithPromptEnchancer_v12.json` | [Prompt enhancer](https://civitai.com/models/2951814/qwen-21-with-prompt-enchancer-100percent-of-understanding) | The idea, not the plumbing. See below |

---

## Upscaling: the 2K workflow, and what it taught us

The technique from `qwen212KUpscale_v10.json` is implemented and it works: the
image goes back in as its own reference, the target size is the whole 2K budget
(area scaled towards 2048×2048, capped at four times per side), and the model
redraws it larger. That recovers real detail rather than interpolating pixels.

It is not in the interface because of what it costs. Measured here:

| | |
|---|---|
| 775×1024 → 1792×2048 | **754 s** (12.5 minutes) |
| card | RTX 5090 Laptop, 24 GB, profile L |

Twelve minutes for one upscale is not a feature. 2K is four times the pixels of
a normal run and the weights are swapped throughout, so on any card that needs
offload this is what it costs.

**And the workflows themselves say this is the wrong tool.** The pack that
ships the T2I and Edit graphs also ships `SeedVR upscale.json`, which does not
use Qwen at all: it loads **SeedVR2**, a dedicated restoration model, and runs
the image through that. The same authors reach for a purpose-built upscaler
rather than asking the diffusion model to redraw, which is the honest answer
and the direction to take if upscaling is wanted here. It would mean another
model to download, mount and test, and none of that has been done.

The endpoint stays — `POST /api/reescalar` with `{"imagen": "<data url>"}` —
so anyone with the hardware, or the patience, can use it knowing what they are
in for. It is simply not presented as though it were ready.

## SageAttention: tried, measured, removed

`Qwen Image 2.1 T2I.json` patches attention with `PathchSageAttentionKJ`, and
the app already looks for SageAttention and uses it when present. So it was
installed and tested here.

```
uv pip install sageattention   ->  sageattention==1.0.6, installs fine
import sageattention           ->  ModuleNotFoundError: No module named 'triton'
attention backend after load   ->  still sdpa
```

PyPI publishes only the 1.x line, whose kernels are written in Triton, and
Triton has no Windows wheel. The package installs and then cannot run, which is
worse than not having it: the app's `try/except` catches it and falls back to
SDPA silently. Getting the speed-up on Windows means building SageAttention 2.x
from source. It was uninstalled again rather than left in the environment as a
trap.

## The 8 GB claim

[The all-in-one workflow](https://civitai.com/models/2956235/qwen-image-21all-in-one-multi-functional-workflow-auto-prompt-optimization-runs-on-8gb-vram)
advertises 8 GB, and its page explains nothing. The graph does: 81 nodes built
on `QwenImage21Cache` plus ComfyUI's own memory manager, with `SeedVR2` for
upscaling, `easy sam3ModelLoader` for masks and `TextGenerateLTX2Prompt` for
prompt rewriting. **There is no GGUF in it** and no exotic quantisation — the
8 GB comes from ComfyUI's allocator and the prefix cache, which is the same
reason ComfyUI is about four times faster than this project for the same image.

That cache is the concrete thing diffusers does not do, and it is named in
[the PR that added Qwen-Image 2.1 to ComfyUI](https://github.com/Comfy-Org/ComfyUI/pull/16400):
prefix caching of text and reference tokens, worth roughly 1.7× on edits.

## The prompt enhancer

That workflow sends the prompt through a translation API and then a hosted LLM.
The idea is good; the plumbing is not, for a project whose whole point is that
nothing leaves the machine. QwenStudio does the same rewrite with the Qwen3-VL
already resident for describing images — text only, no network, about 19 s —
with a system prompt built from the rules measured in this project rather than
a generic "make it better". See `qwenstudio/vision.py`.

## SAM 3 for selection

The inpainting workflow selects with SAM 3, a better segmenter than the CLIPSeg
used here. A real improvement, not implemented: another model to download and
mount, and nothing tested against this pipeline. Written down rather than
quietly ignored.

## GGUF

[The GGUF build](https://civitai.com/models/2952547/qwen-image-21-gguf) is for
ComfyUI's GGUF loader and has no path into `QwenImage21Pipeline`, so it is not
usable here without writing that loader. The download of it on this machine
stopped at 4.0 GB and never finished, so nothing about it has been verified
first-hand.
