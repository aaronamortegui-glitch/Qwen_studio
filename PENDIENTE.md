# What is still open

Written down because it was accumulating in a chat window, which is not a place
things survive. Ordered by what it costs against what it gives.

## Done today, kept here for context

- **nf4 everywhere on CUDA.** Measured on a 24 GB card with a reference photo:
  nf4 on both transformer and text encoder is *faster* than bf16 (56 s against
  73 s), uses half the memory (12.9 GB against 23.9 GB) and is the only way to
  reach 2K natively (467 s, 24.0 GB peak, where bf16 paged for hours). At the
  same seed the two are indistinguishable by eye.
- **Profiles rewritten** around measured memory rather than guesses, and they
  now account for the reference photo, which costs ~6 GB of activations and was
  missing from the old arithmetic.
- **Style transfer**, `modo="estilo"` and `/api/estilo`, with its own case in
  the edit group. Measured on 2026-09-22 with one photograph and three
  pictures: passing the picture as `<image2>` imports its *subject* as well —
  the lighthouse and the botanical study both landed in the result, and the
  watercolour lost the sitter entirely. So the picture is read by the VLM and
  only the technique travels, as words, with a single image. 3 of 3 keep the
  sitter that way, against 1 of 3 before. The reference image is still passed
  when the VLM could not read it, and `ref_estilo: true` forces the old path.

- **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`**, set in `app.py`
  before anything allocates and exported by both launchers.
- **Sampling.** All five fields `FlowMatchEulerDiscreteScheduler` exposes,
  measured on 2026-09-23 at one seed and 16 steps. `use_karras_sigmas` and
  `use_exponential_sigmas` return smears — their sigma remapping fights
  `use_dynamic_shifting`, which this model ships with on. `use_beta_sigmas`
  raises ImportError because scipy is not a dependency here. Only
  `stochastic_sampling` works, and it trades prompt adherence for texture:
  sharpness 7.5 against 3.8 on a face, but it dropped a background the prompt
  had asked for, and it was flatter on a lettering job. So two entries ship,
  `base` and `ancestral`, and the three traps do not.
- **Steps.** Swept by eye at 1 MP on a watch movement, knurling and a hand:
  8 is mush, 12 has a soft movement, 16 resolves screws and jewels, 20 and 25
  add nothing worth the 5 and 11 extra seconds (18 / 21 / 27 / 33 / 38 s). The
  default is now **16**; 12 is a draft. Everything that ships as an example is
  generated at 25 or 30, named `PASOS` in both tools so it is not lowered by
  accident.
- **Six looks from what TostUI exposes**, prompts rather than weights: Anime,
  Photographic, Chibi, Deblur, More detail and Window light. Two notes that
  cost a regeneration to learn. The preservation clause that the grading looks
  use — "the face stays exactly as it is" — contradicts a look whose whole job
  is to redraw, and the model answers a contradiction by doing nothing, so the
  redrawing ones name what is actually kept instead. And three of them showed
  nothing over the shared base photo, because it is already a sharp
  photograph: Photographic now starts its thumbnail from a drawing, and Deblur
  and More detail from that same photo broken on purpose.
- **The e-n-v-y fix DoRA does not earn its place.** Downloaded (106 MB, not
  the 400 that was written here) and run on the terms its workflow asks for:
  strength 1.0, 20 steps, CFG 3. It changes the picture — a different face, a
  different hat, softer skin — but it does not improve on plain CFG 3, and it
  had nothing to fix: **at 20 steps CFG 3 on its own held the prompt**. The
  second person that appeared in the earlier portrait was at 16 steps, so that
  drift belongs to the step count, not to CFG. Not wired into the engine the
  way turbo is; the file simply sits in `loras/` where anyone can pick it from
  the dropdown and judge for themselves, and `loras/*` is ignored by git.
- **Real CFG works, and it is the biggest single lever found.** The pipeline
  accepts `true_cfg_scale` and a negative prompt; this project had run at 1.0
  from the start because that is what the model asks for. Measured at 16 steps
  and one seed: on a watch movement, CFG 3 turned a gold blur into resolved
  jewels, screws and a knurled lid — the largest quality jump of the whole
  session. It is not free and not always right: it costs ~80% more time (29 s
  to 52 s) because the second forward pass is real, on a portrait it invented a
  second person the prompt never asked for, and a letterpress poster came out
  flatter. **CFG without a negative prompt is a no-op** — byte-identical output
  in identical time, because there is nothing to push against. So it ships as
  a setting at 1, with a "What to keep out" box that only appears above 1.

- **Turbo ships as an engine switch, off.** Re-measured fairly, with the
  `shift_terminal: null` its own scheduler config asks for. At the 4 steps it
  advertises it returns ghost hands, with our shift and with its own, so the
  number is **8**. At 8, warm at 1 MP: generation 28 s to 20 s and an edit that
  has to keep a face 29 s to 19 s, with the face indistinguishable — the
  author's warning about identity edits did not appear. It lives in `modelos/`
  beside the alternative VAE rather than in `loras/`, because it changes how
  everything is made instead of adding a look, and `aplicar_lora` now holds two
  adapters so turning it on does not silently drop the user's own. Default off:
  side by side the base model was still the better picture.
- **GGUF is blocked, and now measured rather than assumed.** `from_single_file`
  in diffusers 0.41.0.dev0 refuses `QwenImage21Transformer2DModel`: the class
  is simply not in `SINGLE_FILE_LOADABLE_CLASSES` (which has Flux, SD3, LTX
  and 32 others). Every GGUF build of this model on the hub targets
  ComfyUI-GGUF or stable-diffusion.cpp, which is the dependency this app
  exists to avoid. Revisit when diffusers adds the class, not before.

- **Instruction editing**, `/api/editar` and the "Tell it what to change" case:
  the whole picture, up to three references and a sentence, with no mask and no
  seam. Changing a garment, changing a background and putting someone somewhere
  else all work with an ordinary sentence. Swapping one person for another works
  when the target is the busier photograph and not when it is the cleaner one,
  which is why it is not in the test suite: a case that passes half the time
  measures nothing, and the model's own card lists face swaps among its weak
  points.
- **The rules that decide whether an edit happens**, applied by the rewriter
  rather than written down for someone to remember. Three are QwenLM's, from
  their `system_prompt_edit.txt`: name the attribute and not the person, put
  the change before the preservation, keep the preservation generic. Two were
  measured here and are in nobody's documentation: the verb matters — "put X
  from <image2> on ..." did the most and "replace", which every example uses,
  sat in the middle — and to change who someone is you have to name the
  clothing, because while the original garment stays it holds the original
  person in place. The rewriter reads the reference with the VLM first so it
  names the garment that is there instead of guessing one.

- **The English rule was broken twice and neither time was noticed.** The first
  check only looked at whole-line comments, so every trailing one after code
  went through; the second missed console strings entirely. Around seventy
  fragments - trailing comments, docstrings and console output - were still
  Spanish after the commit that claimed the repository was English. `herramientas/revision_idioma.py`
  now reads every tracked Python file for Spanish in a comment, a docstring or a
  string the user sees, knows the identifiers are Spanish and skips them, and is
  verified against the exact two failures that got past: a trailing comment and
  a `print`.
- **No personal path is written down any more.** Thirteen probe scripts carried
  the absolute path of a private dataset, name included, into a public
  repository. They now resolve their inputs at run time through
  `herramientas/pruebas/_fuentes.py` — `QWENSTUDIO_REF` for the person,
  `QWENSTUDIO_ESCENAS` for the scenes — and stop with the name of the variable
  to set rather than half-running against the wrong picture. `DWPOSE_PY` became
  `QWENSTUDIO_DWPOSE_PY` for the same reason; set it if skeleton extraction from
  a photo is wanted, since nothing else uses it.
- **`AGENTS.md`, with `CLAUDE.md` pointing at it.** The app has shipped an MCP
  server and an agent section in the README for a while, and no file telling an
  agent how to work *on* it: the ceilings it must not raise, the measured
  prompting rules, what is deliberately unreliable.
- **The PDF now covers installing and using it.** It had neither, and three of
  its counts had gone stale (eight use cases, ten tools, nine paths — twelve of
  each), along with a paragraph still saying enlarging was not offered, which it
  has been since nf4 took it from 754 seconds to 156.

## The day the face came back

Five decisions had each taken something off the likeness, and the sum of them
was a different man. Each is listed with what it was measured against when it
was chosen, because that is the part worth remembering.

1. **Sixteen steps**, swept on a watch movement, a knurled ring and a hand.
   Same prompt, same seed, same reference: 16 gives a thinner, younger
   stranger, 24 is close, 28 is them. Now 28 on all twelve paths except the two
   that invent everything from nothing.
2. **The identity clause was not last.** Pose and scene each grew that line for
   their own reason; the plain portrait, which takes the longest prompts, had
   the identity at the start with sixty words of generic photograph after it.
   Now fixed and last wherever there is a person.
3. **The scaffolding competed with the reference.** Forty words describing a
   face, sent into the same encoder that was already being handed one. The bare
   sentence came back the more like the person, and the rewriter no longer
   describes appearance when a reference is loaded.
4. **nf4 rather than int8**, chosen on speed and memory. int8 is better on a
   face at both the base model and the adapter, and it is reachable: not
   through bitsandbytes, whose LLM.int8() splits outliers down a parallel fp16
   path and took encoding one 1024 px reference to 20.14 GB, but through quanto,
   which is weight-only and peaked at 12.1 GB against nf4's 10.1.
5. **The VAE tiled everything, always** -- and this one was worth more than the
   other four together. It went in to cap the decode peak at 4 MP (24.0 GB
   against 7.5) and was switched on at load and never off, so it applied at
   1 MP too, where the whole frame costs 12.1 GB under a 20.3 ceiling. Measured
   at 1 MP: 24.5 levels of difference, slower (56 s against 47), and a worse
   likeness.

   The mechanism is the lesson. `pipe.vae` has two jobs, and `_encode` and
   `_decode` read the same `use_tiling` flag. Tiling for the decode chopped the
   reference on the way IN. The proof is that the composition changed at the
   same seed, which a decoder cannot do: the latent was different because the
   encoder had been handed the face in pieces.

   Both halves are now measured separately. The encode is never tiled, at any
   size. The decode is tiled above 2 MP, and that threshold is no longer a
   guess: at 1536 (2.25 MP) the whole frame OOMs against the ceiling and the
   tiled one peaks at 17.5 GB. And with the encode protected, tiling the decode
   costs 1.0 level at 1280 and 0.0 at 1536 -- all of the damage had been on the
   way in.

Six seeds at the settings that ship now come back as the same man, where before
the fix one of six was a slimmer stranger and the rest were flattered. The
suite has a `same man` case so the next regression of this kind fails a test
instead of taking a day.

**Still open from this:** 2K with a reference. Profile L caps at 1536 with one
reference, and the ceiling is what stops it going higher -- not the decoder,
which tiles happily. The staged engine is the way up, and for the reason the
name hides: it is not about sending anything in parts, it is about freeing the
~9 GB the text encoder occupies so that nothing has to be.


## The staged engine, and how far it got

Every workflow the community shares loads `qwen_image_2.1_int8_convrot` and
`qwen3vl_8b_int8_convrot`. Not one quantises the transformer to four bits, and
the author of the most-shared one runs it on a **3080ti with 16 GB** -- less
than this machine. So "int8 does not fit on 24 GB" was never a property of the
card. It is a property of how this app loads.

ComfyUI's graph gives the text encoder and the transformer **separate
lifetimes**: a Load CLIP node encodes, hands over the conditioning and is
freed; only then does the sampler touch the UNET. One diffusers pipeline holds
both for the whole run, which is why int8 on both dies at the ceiling here.

Four things were established, in order, each by a run rather than by reading:

1. **Freeing late does not work.** Calling `encode_prompt` and then moving the
   text encoder to the CPU throws inside bitsandbytes: by then
   `from_pretrained` has put both models on the card, 20.25 GB allocated, and
   there is no headroom left to move anything anywhere.
2. **The split has to be at load time**, which diffusers allows:
   `from_pretrained(..., transformer=None, vae=None)` gives a text-encoder-only
   pipeline, and `text_encoder=None, tokenizer=None` gives the other half.
   Verified: 368 `Linear8bitLt` modules, 9.3 GB, nothing else resident.
3. **`__call__` will not take precomputed embeddings when there are reference
   images.** It forwards `prompt_embeds` but never `image_pad_mask`, so it
   raises "Pass `image_pad_mask` alongside `prompt_embeds`". The way round is
   to hand the already-computed triple back through `encode_prompt` itself,
   restored in a `finally`. That part works.
4. **Both stages have to share one resize.** `__call__` resizes every condition
   image with `calculate_dimensions(resolution^2, aspect)` rounded to multiples
   of 32, and that same picture feeds the encoder and the VAE. Giving stage 1
   the original and stage 2 the resized one made them disagree about how many
   vision slots the encoder had reserved -- 5168 tokens against 8240 -- and the
   transformer refused the mismatch. The graph does the same thing:
   `LoadAndResizeImage` sits *before* the encode node, not inside it.

**Where it stops today.** The int8 text encoder is 9.3 GB of weights, and
encoding one 1024x1024 reference takes it to 20.14 GB before the transformer is
even loaded: about 11 GB of attention over roughly eight thousand image tokens.
That is the remaining blocker, and it is a narrow one -- the attention
implementation, not the architecture. ComfyUI fits the same encoder and the
same reference into 16 GB, so there is a memory-efficient path here that this
app is not taking. Worth trying, in this order: an explicit
`attn_implementation` on the text encoder, encoding the reference at a smaller
budget than the output, and chunking the encode.

**And what to keep even if the staging never lands:** the community numbers
were right about steps and this repository's were not. The ComfyUI template's
own note says "Qwen Image 2.1 official pipeline uses about 40-50 with euler",
the model card's editing example passes `num_inference_steps=40`, and the
shared workflow ships 25-27. The sweep here settled on 16 because it was run on
a watch movement and a hand.

## Worth an experiment, not a promise

- **An fp8 text encoder would cut the download, nothing else.** The encoder is
  16.3 GB of the 32.5 GB that has to come down, and fp8 safetensors builds of
  Qwen3-VL-8B exist at 9.34 GB — loadable by transformers, unlike GGUF. Worth
  ~7 GB to a small machine. Three caveats: at runtime we already quantise the
  encoder to nf4 at load, so there is no memory or speed gain, only download;
  in this app the encoder does double duty as the VLM that describes photos,
  reads the technique of a style reference and rewrites prompts, so swapping
  it changes those; and the build seen on the hub
  (pottokao/Qwen-Image-2.1-Text-Encoder-Heretic-GGUF) is *abliterated* — the
  refusal directions ablated out of `o_proj` and `down_proj` — which is a
  behaviour change riding along with the size change. A clean fp8 of the
  original would be the thing to look for.

## Known and not fixed

- **The transparent cutout depends on the seed when the source has a busy
  background.** Measured on one photograph: 0.7%, 16.2% and 47.2% opaque across
  seeds, where a clean studio source gives a usable 48-51% every time. Naming
  the opaque subject at the end of the clause moved every case upward and fixed
  none of them reliably. The real repair is to stop asking the model to paint
  transparency and build the alpha from the segmenter, which this app already
  carries for the masking paths: the mask is geometry and does not negotiate.
  The case now states its own limit where it is chosen.
- **A person swap works in one direction and not the other**, depending on
  which photograph is the target rather than on the wording. Every phrasing
  tried moved which direction worked without removing the problem.


## The night the editing was found to have no guidance

Four bugs came out of running every path at what the profile allows, twice,
and then *looking at the pictures* instead of counting the rows that came back
without an error. The suite had been green through all four.

| | what it did | how it was found |
|---|---|---|
| each side clipped against the ceiling on its own | a 1344x1792 edit came back 1024x1024, a square | a size in a table that was not the shape that went in |
| the ceiling read as a side and squared | enlarging asked for 3.21 MP with a reference and could not have worked on any day | it was the only path that asks for the whole allowance |
| a failed allocation kept its blocks | 18.4 GB reserved with nothing running, and the next large request died in four seconds for the previous one's reason | a control that failed faster than it could possibly have run |
| `true_cfg_scale` passed without a negative prompt | **every edit this app ever made ran with no guidance**: whole frames repainted, and a black-and-white look that came back in colour | the eye, on a contact sheet |

The fourth is the one worth remembering. diffusers prints a warning saying
exactly what is wrong -- *"true_cfg_scale is passed as 4.0, but
classifier-free guidance is not enabled since no negative_prompt is
provided"* -- and it had been scrolling past on every edit for as long as
there has been editing here. The README had the same sentence about the
generating path, written weeks ago, and nobody carried it across.

It hid because every other edit path crops around a mask and pastes the crop
back, so whatever drifted was thrown away with the rest of the frame.
Whole-frame instruction editing was added days before this, and it was the
first thing that ever showed it.

**And a lesson about the instrument.** A speckle number -- the picture against
a median of itself -- was invented that night to turn "it looks wrong" into
something sortable. It found the damage, and then it flagged a stack of linen
and a brick wall at 6.8 and 8.1 that were perfect, and cleared a
black-and-white look at 5.6 that was the best result of the run. It is a
texture detector. It is useful for *noticing that something changed* and it
cannot be a pass mark, which is the same mistake as measuring a likeness with
mean pixel difference, made again three weeks later with a different number.

**And the tiles, found the next morning by looking at a fox.** The decode
has been tiled above 2 MP since tiling went in, with whatever tile size
diffusers defaults to, which is 256 pixels. Nobody chose it and nobody looked
at what it does: on a gradient sky and on a blurred background it leaves a
visible grid, and it has been doing that in every 2K image this app has ever
made, in base as much as with the adapter. Every test subject until then had
texture, which hides it. It took someone generating a fox in soft bokeh and
saying the background looked strange.

**Still open after that night:**

- Whole-frame editing regenerates the whole frame. With guidance it keeps the
  framing and does what it is told, but "everything else is unchanged" means
  redrawn to look the same, not carried across. Only the masked paths can
  promise the second thing.
- With the adapter there is no guidance -- the two together do not fit -- so
  editing with turbo on is measurably worse. It is a preview, not a delivery.
- The guided whole-frame ceiling, 1.50 MP, is measured on this card at int8
  and inherited by everything else by the same rule as the other ceilings.
  Nobody has run it on a card that does not have 24 GB.

## The morning after: four more, and one of them was mine

- **The decoder tiled in 256-pixel squares**, which is whatever diffusers
  defaults to, and left a grid on every gradient and every blurred background
  at 2K. Fixed at 768 with a 576 stride, which is where the improvement stops
  -- 1024 measured no better. It costs nothing: the whole generation peaks at
  9.5 GB at every tile size, because the decode runs after the transformer has
  given its memory back.
- **The transparency clause said "the person"** whether or not there was one,
  so asking for an icon asked for somebody to be in it. It names the subject
  now when there is no photograph.
- **The first version of that fix used a variable from another function** and
  raised NameError on every transparent request without a person. It shipped
  nowhere, because it was run before it was believed, which is the only reason
  this line is in the "fixed" list rather than in a bug report from someone
  else.
- **The out-of-memory recovery is only half fixed.** Releasing the exception's
  traceback before collecting works in-process: a walk down the sizes came back
  monotone, each cell paying only for itself. Through the server it does not.
  After a failure while encoding references the card sat at **18.0 GB with
  nothing running**, and only an explicit call to the release endpoint brought it back to
  1.4. So the tensors that failed are still referenced by something the
  handler cannot see -- the pipeline, a cached embedding, another frame. Two
  measurements were thrown away before this was noticed, because they were
  failing for the previous cell's reason and looked like findings. It was
  claimed fixed in the commit of the night before; it is not.
- **The one-reference ceiling was measured with guidance off.** The walk that
  produced 2.30 MP began by turning the adapter on, and the adapter turns
  guidance off -- so every cell in it ran one forward pass where the default
  path runs two. The editing path already carries a separate, guided ceiling
  for exactly this reason; generating does not, because its number looked
  measured and was, against the wrong configuration.
  Walking it again guided gave a monotone column -- 1.50 MP fits, 1.75, 2.00
  and 2.30 do not -- and that column contradicts a portrait at 1344x1792,
  2.30 MP, guided, that ran through the server in 267 s the same afternoon.
  Same area, different shape, opposite outcome, and no explanation for it.
  The unguided column of the same walk is not usable: 2.00 failed between a
  2.30 that passed and a 1.75 that passed, which is carry-over rather than a
  wall, so the in-process recovery is not complete either.
  **Nothing was changed on the strength of this.** A ceiling moved on
  contaminated data with an unexplained counter-example is worse than the
  ceiling that is there.
- **An IndexError at 2048x2048** appeared once, after a turbo-on / turbo-off
  sequence, and has not reproduced: not in eight generations at four tile
  sizes with a LoRA swap between each pair, not in forty-eight isolated
  decodes, not in-process with a traceback waiting for it. Recorded here with
  its conditions rather than called fixed.

## Documentation debt

- The memory table and the measured times belong in the README, the PDF **and
  the Windows and macOS installers** — the installer is where someone reads it
  before losing an afternoon.
- **A recipe made in bf16 does not reproduce in nf4 at the same seed.** Changing
  precision changes every step slightly and thirty steps amplify it into a
  different image. This has to be said next to the seed in the recipe panel.
- macOS is **unmeasured**. There is no Apple Silicon here. Say so rather than
  extrapolating, which this project has been burned by before.
