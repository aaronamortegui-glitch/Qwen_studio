# Working on QwenStudio

For an agent — Claude Code, Codex, anything else — that has to run this app or
change it. The README is the study: why every decision is what it is, and every
number that was measured. This file is the operating manual: what to do, what
never to do, and the handful of rules that are not guessable from the code.

Read this first, then the README section you need.

---

## What this is

A local application around **Qwen-Image 2.1**: a 7B single-stream DiT whose text
encoder is **Qwen3-VL 8B**, which the app also uses as its vision-language model
for describing images and rewriting prompts. No ComfyUI, no cloud, no API key.
One Python process serves an HTML page on `127.0.0.1:7860` and holds the model.

It is an exploration, not a product. Some paths are measured and solid; one is
documented as unreliable on purpose. Do not present the unreliable one as
working.

---

## Rules for working in this repository

**Everything committed is in English.** Code, comments, docstrings, UI strings,
console output, README, commit messages. The identifiers are Spanish (`motor`,
`imagen`, `salidas`) — that is the existing naming, leave it alone; prose is
English. A single Spanish comment is a regression, not the old convention.

**Nothing personal goes in.** No photographs of real people, no outputs made
from them, no personal LoRA weights, no paths that carry someone's name. The
probe scripts under `herramientas/pruebas/` resolve their inputs at run time
through `_fuentes.py` (`QWENSTUDIO_REF`, `QWENSTUDIO_ESCENAS`) precisely so no
file name has to be written down. Keep it that way.

**Test in threes, not in hundreds.** Three to six images per experiment. A
large batch on a local card costs an hour and teaches the same thing.

**Check the UI after touching it.** `herramientas/revision_ui.py` parses
`interfaz.py` and catches the failures that are invisible until someone opens
the page: an id the JS asks for and the markup never defines, a CSS token used
and never declared, a dialog with no background or no way to close, and — via
`node --check` on the page's script blocks — a syntax error. One stray
apostrophe inside a JS string once took the entire page's JavaScript down, and
nothing else caught it.

**Restore `config.json` after calibrating.** Anything that writes a ceiling
into it must put the real one back. A config left describing a machine that is
not this one is how a card gets pushed past its wall.

---

## Running it

```
RUN.bat            Windows
./run.command      macOS
```

First run downloads ~31 GB of weights into `modelos/`. `INSTALL.bat` /
`install.command` build `.venv` with uv and write `config.json` by probing the
hardware. `python bootstrap.py` prints what this machine will get — profile,
ceilings, expected times — without starting anything.

To restart cleanly, kill by port, not by name or memory: two servers on 7860 is
a confusing state, and only one of them holds the model.

---

## Two ways to drive it

### MCP

```json
{"mcpServers": {"qwenstudio": {
  "command": "D:\\QwenStudio\\.venv\\Scripts\\python.exe",
  "args": ["-m", "qwenstudio.mcp_server"],
  "cwd": "D:\\QwenStudio"}}}
```

Twelve tools: `status`, `list_poses`, `list_loras`, `list_looks`,
`prompt_library`, `describe_image`, `generate`, `generate_batch`,
`preview_selection`, `inpaint`, `apply_look`, `unmount`.

Images go in and out as **file paths, not base64**. The MCP server is a thin
layer over the HTTP app, so **start the app first**: the model loads once and
the UI and the agent share it. `generate_batch` keeps the model mounted across
a list of prompts, which is the case where something else writes the prompts.

`inpaint`, `apply_look` and `preview_selection` take either `select` (words) or
`mask` (a path to a black and white image, white where the edit goes), so a
caller that already knows the region does not have to describe it back into
words.

### HTTP

`POST` JSON to `127.0.0.1:7860`. Images are `data:` URLs in, file paths out.

| endpoint | does | key fields |
|---|---|---|
| `/api/generar` | new image, optionally holding an identity | `prompt`, `personas[]`, `escena`, `pose_lib`, `estilo`, `ratio`, `megapixeles`, `steps`, `seed`, `variantes`, `transparencia`, `lora` |
| `/api/editar` | instruction edit over the whole frame | `imagen`, `prompt`, `referencias[]` |
| `/api/inpaint` | regenerate a region and stitch it back | `imagen`, `prompt`, `mascara` or `frase`, `padding` |
| `/api/efecto` | apply a look, whole frame or region | `imagen`, `efecto`, `mascara` or `frase` |
| `/api/estilo` | match another picture's technique | `imagen`, `estilo` |
| `/api/reescalar` | enlarge with detail added | `imagen`, `objetivo` |
| `/api/mejorar_prompt` | rewrite a prompt with the VLM | `prompt`, `edicion`, `referencia` |
| `/api/describir` | read an image with Qwen3-VL | `imagen`, `tarea` |
| `/api/mascara` | preview what a phrase selects | `imagen`, `frase` |
| `/api/estado` | profile, VRAM, whether weights are present | — |

`GET /api/estado` before anything heavy. `POST /api/desmontar` frees the card.

Deep links open the UI where you want it: `?caso=pose`, `?abrir=poses`,
`?tema=dark`.

---

## The ceilings — the part that must not be guessed

Every profile carries four numbers, written into `config.json` by
`hardware.py`. Read them from `/api/estado`; do not hardcode them.

| field | meaning |
|---|---|
| `res_max` | longest side with no reference image |
| `res_max_ref` | with one reference (it costs twice the sequence) |
| `res_max_multi` | with two or more (each adds activations) |
| `vram_limite_gb` | hard allocator ceiling, CUDA only |

CUDA profiles:

| VRAM | level | quantisation | offload | res / ref / multi |
|---|---|---|---|---|
| ≥ 40 GB | XL | none (bf16) | none | 2048 / 2048 / 1536 |
| ≥ 20 GB | L | **int8** | model | 2048 / **1792** / 1024 |
| ≥ 12 GB | M | nf4 | model | 2048 / 1024 / 1024 |
| ≥ 8 GB | S | nf4 | model | 1536 / 1024 / 1024 |
| < 8 GB | MINIMO | nf4 | model | 1024 / 1024 / 1024 |

**Those are sides, and what the card actually spends is area.** The side for
one reference was measured on a 3:4 frame, and a square at the same side is a
third more pixels: with one reference 1600x1600 (2.40 MP) fits and 1651x1651
(2.60 MP) does not. So the allowance with exactly one reference is the area of
a 3:4 frame at that side -- 2.30 MP on the L profile -- and the app refuses
anything larger rather than letting it fail halfway. The smaller profiles keep
the full square, because there the one-reference side equals the
several-reference one and *that* was measured square.

Four things about this table are load-bearing:

- **`vram_limite_gb` is not advisory.** It is applied with
  `torch.cuda.set_per_process_memory_fraction`, so an over-large request raises
  `OutOfMemoryError` *at allocation time*. The earlier design — a watcher
  thread that cancelled between denoising steps — did not work, because the
  spike happens inside a step. Two blue screens came out of that: the driver
  breaks on an allocation it cannot serve and, with the hypervisor in the path,
  takes the kernel down instead of resetting. The reserve is 15% of the card,
  capped at 4 GB and floored at 1.5 (on a 24 GB card: 20.3 usable of 23.9).
  **Do not raise it to reach a resolution.**
- **Sequential offload is incompatible with nf4.** `NotImplementedError: Cannot
  copy out of meta tensor` — accelerate cannot move layer by layer what
  bitsandbytes has already quantised. Every quantised profile uses `model`.
- **Reference images are capped at ~1 MP** before they are sent, which keeps a
  12 MP phone photo out of memory on the way in. It does **not** decide the
  size the model sees: the pipeline resizes every condition image to the area
  of the output, so that is set by `output_resolution` and shrinking a
  reference first is a no-op. The image *being edited* is never capped.
- **References share a budget with the output.** Each one costs what the
  output costs, so the count and the size trade against each other. Measured
  on 24 GB: 2 references at 1.00 MP, 3 at 0.66, 4 at 0.50, 6 at 0.32, 8 at
  0.25, and ten at no size tried. `/api/generar` divides the allowance and
  refuses more than eight with a sentence rather than an out-of-memory. The
  model card's "up to ten" is about the weights, not about a card.

- **An out-of-memory error hands the card back before returning.** It used to
  keep the failed allocation's blocks -- 18.4 GB reserved with nothing running
  -- so the request after a refused one failed for the previous one's reason.
  If you catch an error about size, the next call is safe to make.

**int8 on a card with room for it, nf4 below.** This file used to argue that
nf4 was not a compromise, from a measurement of speed, memory and texture.
Against a *face* int8 is the better of the two, which is why the 20 GB profile
changed. nf4 stays on the smaller profiles: 10.1 GB fits on a 12 GB card and
12.1 does not.

**Editing needs both halves of guidance or neither.** `true_cfg_scale` above
1.0 does nothing unless a negative prompt comes with it -- the pipeline warns
about exactly this -- and the editing paths used to pass the scale alone,
hardcoded at 1.0. Every edit ran with no guidance, which on a whole frame
repaints it: mottled concrete where the source was smooth, and a
black-and-white look that came back in colour. The app now passes both from
settings on the whole-frame path. If you call the engine directly, pass both
or expect that.

**With the adapter, guidance stays off.** It is distilled without
classifier-free guidance and its card says so. `_cfg()` already returns
`(1.0, "")` when turbo is on; do not override it.

---

## Writing the prompt: what was measured

These are not style preferences. Each was measured with the same picture, the
same reference and the same seed; the README has the tables.

1. **Name the attribute, never the person.** "Replace the woman with the man
   from `<image2>`" changes nothing. "Replace the face, the hair and the beard
   with those from `<image2>`, and change the clothing to a dark t-shirt" works.
2. **The verb matters more than the docs suggest.** `put X on …` is strongest,
   then `swap X for …`; `replace` and `change` graft rather than exchange;
   `give …` and `edit … to match …` do almost nothing.
3. **To change who someone is, name the clothing.** Face, hair and beard gave a
   beard on the original face. Adding body and build changed nothing further.
   Adding the garment did the whole exchange — the original jacket anchors the
   original person.
4. **Operation first, preservation after**, and keep the preservation generic.
   Listing the place, the light and the framing made the model repaint them,
   from the reference rather than the target. The app's own clause says
   "everything else stays as it is" and stops there.
5. **Last word wins.** The model weighs the end of the prompt most, which is
   why pose, scene and transparency clauses are appended after the user's text.
6. **CFG without a negative prompt is a no-op** — byte-identical output, same
   time. `true_cfg_scale` only does something with a negative.
7. **A reference face costs steps.** 16 is the default because that is where
   texture resolves; identity does not. Measured at one seed: 16 gives a
   thinner, younger version of the person, 24 is close, 28 is them. Any request
   with `personas` runs at 28 unless `steps` is passed explicitly.
8. **Keep the prompt short when a face has to survive.** Thirty-five words
   naming the wardrobe, the place and the light works. Sixty words describing a
   generic photograph of a generic person does not — the model has an opinion
   about that person and it is not yours.
9. **The rewriter looks before it writes.** Asked to swap a person, text alone
   guessed "the jacket and pants" about a photo of a man in a t-shirt. Reading
   the reference with Qwen3-VL first gets "a maroon short-sleeved t-shirt".

10. **Everything that touches the reference is part of the identity path.**
   `pipe.vae` decodes the output and encodes the condition images, so tiling
   switched on for the decode also chopped the reference on the way in. It is
   off below 2 MP and the encode is never tiled at all, at any size. If you
   touch the VAE, the offload, the quantisation or the sampler, run the `same
   man` case before believing the result.
11. **Do not conclude about identity from a texture measurement.** Every one of
   the five regressions found on 2026-09-23 came from exactly that.

Tried and useless, so nobody tries again: enlarging the reference, naming who
stays instead of who arrives, and adding an identity tail after the instruction
— that last one makes it worse, because with `<image2>` in the final sentence
the model returns `<image2>` whole.

---

## What works and what does not

Solid, and covered by the suite: text to image, portrait from a photo, a
character in a scene, pose from the library, style reference, style matching,
instruction edits, background swap, inpainting by phrase or brush, looks over
the whole frame or a region, enlarging, the CFG detail pass, description,
batches.

**Known and not fixed** — `PENDIENTE.md` has the detail:

- **Transparent cutouts are seed-dependent.** Asking the model to paint
  transparency got from 0.7% to 16–47% opaque by naming the opaque subject
  last, but a busy background still defeats it. The real fix is building the
  alpha from the segmenter instead of asking for it.
- **Person swap is direction-dependent.** The prompting half is solved (the
  rules above); it still fails one way round on some pairs. The model card
  lists face swaps among its own weak points. It is deliberately **not** in the
  test suite — do not add a test that will be flaky, and do not describe this
  as working.

---

## Testing

```
.venv\Scripts\python.exe herramientas\pruebas\todos_los_caminos.py
```

21 cases, every path the app offers, each asserting something measured rather
than "no exception": that the alpha channel is actually transparent, that the
painted region changed and the rest did not, that CFG without a negative is
byte-identical. It takes about twenty minutes on a 24 GB card and needs the app
running.

Do not restart the server mid-suite — it produces failures that are not real.

Two audits need no GPU and take a second each:

```
python herramientas/revision_ui.py        after touching interfaz.py
python herramientas/revision_idioma.py    before every commit
```

The second one reads every tracked Python file and fails on Spanish in a
comment, a docstring or a string the user sees. It knows the identifiers are
Spanish and ignores them. It exists because the English rule was broken twice
without anyone noticing: the first check only looked at whole-line comments
and missed every trailing one, the second missed console output entirely.

---

## Layout

```
qwenstudio/app.py          HTTP server, endpoints, settings
qwenstudio/motor.py        weights, pipeline, prompt scaffolding
qwenstudio/interfaz.py     the whole page: markup, CSS and JS in one file
qwenstudio/hardware.py     probes the machine, writes the profile
qwenstudio/vision.py       Qwen3-VL: describing, rewriting
qwenstudio/recursos.py     who has to release the GPU before who
qwenstudio/inpaint.py      crop, regenerate, stitch back
qwenstudio/segmentacion.py phrase to mask
qwenstudio/mcp_server.py   the twelve MCP tools
herramientas/              tooling: tests, docs, packaging, screenshots
referencia/                the outside material the study drew on
```

Every generated image carries its own recipe in its metadata, and
`GET /api/receta` reads it back. When reproducing something, take the recipe
from the file rather than from a description of it.
