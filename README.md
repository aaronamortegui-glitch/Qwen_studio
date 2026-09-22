# QwenStudio

Local image generation and editing with Qwen-Image 2.1. No ComfyUI, no cloud,
no account. Install with a double click, run with a double click.

    INSTALL.bat         (Windows)        RUN.bat
    install.command     (macOS)          ./run.command

The installer downloads **uv**, which brings its own Python 3.12 into this
folder — nothing on your system is touched. The model weights (~31 GB) download
on first run, with a resumable progress bar.

Interface at <http://127.0.0.1:7860>.

> Qwen-Image 2.1 is under the **Qwen Research License**: non-commercial use
> only unless you obtain a separate licence. Fine for personal work; check
> before shipping anything to a client.

---

## What it does

Eight use cases in three groups, each showing only the inputs it needs:

| Group | Use case | Inputs |
|---|---|---|
| Text to image | **New image** | nothing but the prompt |
| | **Text in the image** | words in quotes come out as lettering |
| From a photo | **New portrait** | person photos |
| | **Character in a scene** | person + a photo of the setting |
| | **Pose my character** | person + pose + optional style and setting |
| | **Transparent cutout** | person → PNG with real alpha |
| | **Free** | everything, nothing assumed |
| Edit a photo | **Replace something** | image + a selection + what to put there |

The selection for an edit comes from **words** (`the yellow sweater`, segmented
by CLIPSeg) or from a **brush**: paint over the region on the image itself, at
its real resolution, with an eraser and an adjustable size. A painted mask is
used exactly as drawn — no growing, no threshold — and the segmenter is never
loaded, which is 150 MB and one model fewer competing for VRAM.

Every use case opens with a **worked example**: the inputs it takes, already
in their boxes, and the contact sheet of a real run with exactly those inputs,
so the first screen shows *this + this = this* instead of an empty form. Drop
your own photo over any box and the example steps aside.

> The example ships a photograph of a real person. Whoever receives this
> package receives it too. To swap it, replace the files in `ejemplos/` and
> regenerate the sheets: `person.jpg`, `scene.jpg`, `style.jpg` are the
> inputs, `out_<case>.jpg` the contact sheet each case shows.

Plus a **pose library** (30 skeletons: close-up, half and full body, across
portrait, casual, business, fashion, seated and sports), a **prompt library**
(additive snippets, one clause of a photograph each, built to stack), **image
description and reasoning** with Qwen3-VL, **LoRA** loading, the seven official
aspect ratios, 2K native output, a **before/after slider** on every edit, and a
**contact sheet** per run showing inputs + result.

On a machine that cannot run this usefully — no compatible GPU, or under 10 GB
of VRAM — the installer and the app both say so plainly, with a puppy, and then
let you through anyway.

---

## The four reference slots

Each one does exactly one job, so they compose without fighting:

| slot | gives | stays out of it |
|---|---|---|
| **Person** | the face and identity | everything else |
| **Pose** | posture, limbs, head tilt | build and height — those stay the person's |
| **Style** | grade, contrast, grain, quality of light | its subject, setting and composition |
| **Scene** | place, wardrobe, framing, lighting | the face |

The prompt is assembled from whichever slots you filled: no pose, no skeleton
clause. Every reference is tagged `<image1>`, `<image2>`… and the tag is
repeated inside its instruction, because the text encoder reserves one vision
slot per tag and the binding is what keeps them apart.

Style has a toggle for when one photo should define the whole look — clothing
and place included. It works, but it makes the Scene slot redundant, so it is
not the default. Note that Style and Scene both mention lighting: with both
filled they compete, and which one wins has not been measured.

## Things worth knowing

**Reference order is not yours to choose, and that is deliberate.** Identity
transfers when the person is `<image1>`; with the scene first the scene
dominates and the face does not change at all — it fails silently, producing a
plausible image that is simply the wrong person. The app always orders
person → pose → style → scene.

**A scene with a person in it will hand you that person.** The identity clause
sits at the start of the prompt and the scene reference, closer to the end,
outranks it: with a female scene and a male reference the result came back as
the woman from the scene, at the right size, looking perfectly plausible. The
fix is recency — the prompt now repeats, *after* the scene clause, that the one
person in the result is the subject from `<image1>`. Same seed, same inputs,
correct face.

**With a scene, use one photo of the person.** Several photos of the same
person are read as several *different* people, and you get several people in
the frame.

**Prompts go positive but imperative.** There is no negative guidance at
cfg 1, so "ignore the background" just injects the concept. But softening the
verb breaks it too: "the face is hers" does not transfer, "the subject's face
must match `<image1>` exactly" does. The scaffolding says "the subject" rather
than he or she: a pronoun that disagrees with the reference photo is one more
thing for the model to resolve, and it does not always resolve it your way.

**Describing an image costs no extra download.** The image model's text
encoder *is* Qwen3-VL-8B, and the checkpoint on disk carries the vision tower
and the language head. The same 16 GB serve both jobs; it loads in 4-bit so it
can sit beside the DiT.

**Close anything else using the GPU first.** Starting with VRAM half full makes
generation crawl with no error: utilisation reads 100%, power draw stays low,
and nothing finishes. The app warns when it sees this.

---

## Measured here (RTX 5090 Laptop, 24 GB)

| | |
|---|---|
| 1024 px, 25 steps, warm | **55 s** |
| VRAM peak | 21.3 GB |
| model load (first call) | 27–35 s |
| segmentation, 3 phrases | 0.9 s |
| describe an image (Qwen3-VL 4-bit) | 5–9 s, 7.1 GB |

Three load configurations were compared. Keeping the transformer and text
encoder both resident — even with the text encoder in 4-bit — does **not** fit
in 24 GB: weights alone reach 20.8 GB and activations push it into thrashing.
The default (bf16 + model offload) is the fastest of the three on this card.

ComfyUI is still ~4× faster for the same image, because it uses
`int8_convrot` weights with kernels built for them and a much better memory
manager. If raw speed matters more than being self-contained, use ComfyUI.

---

## Control it from an agent

An MCP server exposes the app to Claude, Codex or any MCP client:

```json
{"mcpServers": {"qwenstudio": {
  "command": "D:\\QwenStudio\\.venv\\Scripts\\python.exe",
  "args": ["-m", "qwenstudio.mcp_server"],
  "cwd": "D:\\QwenStudio"}}}
```

Ten tools: `status`, `list_poses`, `list_loras`, `prompt_library`,
`describe_image`, `generate`, `generate_batch`, `preview_selection`, `inpaint`,
`unmount`.

`inpaint` and `preview_selection` take either `select` (words) or `mask` (the
path to a black and white image, white where the edit goes), so a script that
already knows the region does not have to describe it back into words.

Images go in and out as file paths, not base64. Start the app first: the MCP
server is a thin layer over it, so the model loads once and the UI and the
agent share it. `generate_batch` runs a list of prompts with the model mounted
throughout — made for scripts that write the prompts elsewhere.

---

## Layout

    qwenstudio/hardware.py       hardware detection and load profile
    qwenstudio/motor.py          weights download and the diffusers pipeline
    qwenstudio/segmentacion.py   text-driven segmentation (CLIPSeg)
    qwenstudio/inpaint.py        crop-and-stitch
    qwenstudio/poses.py          pose library
    qwenstudio/prompts.py        prompt library
    qwenstudio/vision.py         describe and reason (Qwen3-VL, no extra download)
    qwenstudio/recursos.py       mount/unmount the models sharing the GPU
    qwenstudio/resumen.py        contact sheet
    qwenstudio/app.py            local HTTP server
    qwenstudio/interfaz.py       the interface
    qwenstudio/mcp_server.py     MCP server
    herramientas/                build the pose library from your own photos
    poses/ loras/ modelos/ salidas/

## Profiles

Hardware is detected before anything is installed, and decides dtype,
quantisation, offload and maximum resolution. The download is the same in every
profile; the profile changes how it is loaded.

| VRAM (CUDA) | dtype | quant | offload | max |
|---|---|---|---|---|
| ≥ 40 GB | bf16 | — | — | 2048 |
| 20–40 | bf16 | — | model | 2048 |
| 16–20 | bf16 | — | sequential | 1536 |
| 10–16 | bf16 | nf4 | sequential | 1024 |

On Apple Silicon there is no quantisation (bitsandbytes has no MPS backend);
the profile adjusts dtype and offload instead, and refuses under 24 GB of
unified memory. **The macOS path is written but untested** — only
Windows/CUDA has been verified.
