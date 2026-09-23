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

## Documentation debt

- The memory table and the measured times belong in the README, the PDF **and
  the Windows and macOS installers** — the installer is where someone reads it
  before losing an afternoon.
- **A recipe made in bf16 does not reproduce in nf4 at the same seed.** Changing
  precision changes every step slightly and thirty steps amplify it into a
  different image. This has to be said next to the seed in the recipe panel.
- macOS is **unmeasured**. There is no Apple Silicon here. Say so rather than
  extrapolating, which this project has been burned by before.
