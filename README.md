<p align="center">
  <img src="docs/marca.png" width="88" alt="">
</p>

<h1 align="center">QwenStudio</h1>

<p align="center">
  Local image generation and editing with Qwen-Image 2.1.<br>
  No ComfyUI, no cloud, no account, no API key.
</p>

---

> ### This is an exploration, not a product
>
> It was built to answer a question — *how far does an open image model get you
> when you run it entirely on your own machine?* — and the answer is written
> down here, measurements and failures included.
>
> **It is not an official Superside tool, it is not affiliated with or endorsed
> by Superside, and it is not endorsed by the Qwen team or Alibaba.** The
> interface borrows Superside's palette and typeface because the exploration
> happened there and it needed to look like something; the mark in the corner
> is an original symbol drawn for this repository, not the Superside logo.
>
> **Qwen-Image 2.1 is published under the Qwen Research License: personal and
> research use only.** Nothing produced with this belongs in client work
> without a separate licence from Alibaba. Inter Tight is bundled under the
> SIL Open Font License; CLIPSeg is MIT. See [Licences](#licences).

---

## Two ways to use it

**1. By hand.** Double-click and it opens in a window of its own -- no tab
strip, no address bar, its own icon in the taskbar. It is still a browser
underneath, serving `127.0.0.1:7860`, but nothing about it says so. You drop
photos into boxes and press Generate. Nine use cases in three groups, each
showing only the inputs it needs, each opening with a worked example already
loaded.

**2. By agent.** Point Claude Code, Codex or any MCP client at this folder and
ask for what you want. The agent gets ten tools — generate, edit, describe,
batch, pose library, prompt library — and drives the same engine the interface
drives. The model loads once and both share it, so you can have the page open
while an agent works through a list of prompts in the background.

The second way is the one worth understanding: everything the interface can do
is an HTTP endpoint, and everything an agent needs is a thin layer over those
endpoints. The app is not a wrapper around a script — it is a local service
with two front doors.

---

## Install

```bash
git clone https://github.com/aaronamortegui-glitch/Qwen_studio.git QwenStudio
cd QwenStudio
```

Then double-click the installer for your platform:

| | install | run |
|---|---|---|
| **Windows** | `INSTALL.bat` | `RUN.bat` |
| **macOS** | `install.command` | `./run.command` |

The installer downloads **uv**, which brings its own Python 3.12 into this
folder. Nothing on your system is touched: no system Python, no global
packages, no PATH changes. Delete the folder and it is gone.

That includes the models. The image weights, Qwen3-VL, CLIPSeg and SAM 2 all
land in `modelos/`, downloaded on the first run and never again — not in
`~/.cache/huggingface`, where the two small ones used to go. After that first
download the app needs no network at all, which was the whole point and was
quietly untrue until it was checked.

It detects your hardware **before** installing anything and picks the profile
from it — which PyTorch wheel, which dtype, whether to quantise, how much to
offload, what resolution to cap at. The model weights (~31 GB) download on the
first run, with a resumable progress bar, so you can look at the detected
profile before committing the disk.

`SHORTCUT.bat` (Windows) puts a desktop shortcut with the icon on your desktop.
The console window that carries the server starts minimised. It is not hidden:
it is where the download progress, the detected profile and any error appear,
and a local app that fetches 31 GB and can run out of VRAM should not swallow
its own explanation.

---

## What it looks like

<p align="center"><img src="docs/ui-portrait.png" width="820" alt="The main screen: use case groups, a worked example already loaded, and its result"></p>

Every use case opens with a **worked example**: the inputs it takes, already in
their boxes, and the contact sheet of a real run with exactly those inputs. The
first screen shows *this + this = this* instead of an empty form. Drop your own
photo over any box and the example steps aside.

<p align="center"><img src="docs/ui-vitrina.png" width="820" alt="The showcase: thirty-one images this install produced, in two groups, each one clickable for its recipe"></p>

And the results column is not empty on the first run. It opens with **thirty-one
images this install produced**, in two groups — what each path does, and how
far the style stretches — each one clickable for the prompt, the seed and
the settings behind it, and for a button that opens the use case it came from
with that prompt already in the box. Five of them build on each other: a
character is invented from a paragraph, that face is carried into a portrait, a
scene and a cutout, and two of the earlier images are then edited — so the
showcase is one tool doing a day's work, not eight unrelated demos. The second
group changes the visual language rather than the task — pixel art, isometric
tiles, game key art, a sitcom still, riso, ink, a patent drawing — because
range is an argument the use cases cannot make on their own. It steps
aside the moment you generate something of your own, and a link in the header
brings it back. Rebuild it as yours with `herramientas/vitrina.py`.

<p align="center"><img src="docs/ui-indice.png" width="820" alt="The footer: an index of everything the app can do, each entry opening its own panel"></p>

Nine paths and a handful of tools is more than fits on one screen, so the footer
carries **an index of the whole thing** — and each entry is named the way you
would ask for it, not the way the panel is labelled. Someone looking to *remove
the background* will not guess that it lives under **Transparent cutout**, so
that is what the index calls it; clicking takes you there with the case already
set up. Next to it, in one place, the two sentences anyone needs before they
send an image anywhere: this is a beta built to experiment with, and the model's
licence is non-commercial.

<p align="center"><img src="docs/ui-text.png" width="820" alt="Text to image: a screen-printed poster with rendered lettering"></p>

Words in quotes come out as **actual lettering**. This is the thing Qwen-Image
does better than almost anything else you can run locally, and the poster above
was generated on the machine described below, at 35 steps, first try.

<p align="center"><img src="docs/muestra-t2i.jpg" width="880" alt="Fourteen text-to-image results, one per starting point in the prompt library"></p>

Every starting point the prompt library offers for the two text-to-image paths,
run once each at 30 steps. Nothing retried, nothing picked from a batch —
fourteen prompts, fourteen images, in the order they came out. Six of them ask
for lettering (`ATACAMA`, `ROSEWOOD & SONS`, `SINGLE ORIGIN · ETHIOPIA ·
YIRGACHEFFE`, `THE LONG DRY`, `LATE BAR`, `SOUP OF THE DAY`) and all six are
spelled correctly. Regenerate the sheet with
`herramientas\hoja_muestra.py`.

<p align="center"><img src="docs/ui-brush.png" width="820" alt="The mask brush: paint over the region to replace"></p>

An edit can also take **a photo of what goes there**, in the optional Reference
box: paint or name the region, write what it is in a few words, and drop in a
picture of the material. The reference is subordinate to the text on purpose —
an earlier version told the model the reference "must appear in the region" and
it pasted the whole reference photo, landscape and all, into the mask. It now
says the text describes *what* is built and the reference shows *how it looks*,
and only the colour, material and pattern come across.

An edit selects its region from **words** or from a **brush**. Painting happens
at the photo's real resolution; what you leave untouched comes back byte for
byte, which the test suite checks rather than assumes.

**Both editing paths take the brush**, because both are the same operation
underneath: crop around the region, regenerate the crop, feather it back in.
Replacing something needs a region and lets you name it in words instead of
painting it. A look does not need one — leave it alone and the treatment covers
the whole photograph, which is what a grade is for — but painting one confines
the look to that region, so you can relight a face or turn just the subject to
clay and have the rest of the frame come back untouched.

<p align="center"><img src="docs/sam-vs-clipseg.png" width="880" alt="The same selection: original, CLIPSeg alone, and CLIPSeg refined by SAM 2"></p>

When you select by words, **two models do it.** CLIPSeg takes the text and finds
roughly where the thing is; SAM 2 takes CLIPSeg's box and centre and returns the
object that is actually there. Above: the original, CLIPSeg alone, and the pair.
CLIPSeg works at 352×352 and its output, scaled back up, takes in the hair
falling across the garment — the orange blotches in the middle frame. Asking for
`the yellow sweater` went from 28.3% of the frame to 22.2%, and the 6 points it
gave back are the hair.

SAM 2 does not accept text and CLIPSeg does, so each does the half it is good
at. The refiner is `sam2.1-hiera-tiny`: 31M parameters, about 150 MB, eight
seconds to load and under a second to run. If it is missing or fails, the
CLIPSeg mask is used unchanged — a worse mask beats an exception. Turn it off in
Settings. (SAM **3**, which the ComfyUI workflows use and which does take text,
is not in transformers 5.17.)

<p align="center"><img src="docs/ui-poses.png" width="820" alt="The pose library: thirty skeletons, filtered by framing and kind"></p>

Thirty poses. The thumbnail is the photo, because that is what you recognise;
hover and it swaps to the OpenPose skeleton, because that is what the model
actually receives.

<p align="center"><img src="docs/ui-looks.png" width="820" alt="The effects grid: each thumbnail is that look applied to this install's own reference"></p>

Looks are picked from a grid, not typed. Every thumbnail is that effect applied
to this install's own reference photo, generated here — so the grid shows this
model doing this thing, not a screenshot of someone else's pipeline.

<p align="center"><img src="docs/ui-restyle.png" width="820" alt="Match a style: two slots, the photo and the picture whose manner you want"></p>

Match a style asks for two pictures and keeps them straight: the photograph
supplies everything you can see, and the reference supplies only how it is
made. The slot says so, because the first thing anyone tries is dropping in a
picture of a person and expecting the clothes.

<p align="center"><img src="docs/ui-settings.png" width="820" alt="The engine settings: detail pass, decoder, turbo adapter and sampling, each with the measurement behind it"></p>

The four settings that change how every image is made sit together, and each
one carries the measurement that decided its default rather than an adjective.
None of them is on by default, because none of them measured as a free win.

<p align="center"><img src="docs/ui-gallery.png" width="820" alt="The gallery: everything written to the outputs folder"></p>

**Everything you make lands in `salidas/`** and the Gallery reads that folder
directly — there is no database to fall out of sync with the disk. Delete a
file there and it is gone from here. Every tile and every result carries a
download button, and **Open the folder** hands you to the file manager.

Every gallery tile and every result carries a bin that moves the file to
`salidas/_papelera/` rather than unlinking it — in the gallery as a × on the
thumbnail, in the results column as an icon beside Download, so a run that
produced six variants can be cut down to the one worth keeping without
opening anything. A grid of thumbnails that look alike is exactly where a
click you cannot undo loses the good one; the bin stays on disk and emptying
it is your call, not the app's.

<p align="center"><img src="docs/ui-dark.png" width="820" alt="The same screen in dark"></p>

Light by default, dark in Settings, or Auto to follow the system.

---

## What it does

| Group | Use case | Inputs |
|---|---|---|
| **Text to image** | New image | nothing but the prompt |
| | Text in the image | words in quotes come out as lettering |
| **From a photo** | New portrait | person photos |
| | Character in a scene | person + a photo of the setting |
| | Pose my character | person + pose + optional style and setting |
| | Transparent cutout | person → PNG with a real alpha channel |
| | Free | everything, nothing assumed |
| **Edit a photo** | Apply a look | image + a treatment picked from a grid, optionally a painted region |
| | Match a style | image + a picture whose manner you want |
| | Replace something | image + a selection + what goes there |

Plus a **pose library** (30 skeletons across close-up, half and full body), a
**prompt library**, **image description and reasoning** with Qwen3-VL, **LoRA** loading,
the seven official aspect ratios, 2K native output, a **before/after slider**
on every edit, and a **contact sheet** per run showing inputs + result.

Three engine settings sit in the panel, each off or neutral by default because
each was measured to be a trade rather than a free win:

| Setting | What it does | Measured |
|---|---|---|
| **Detail pass (CFG)** | a second forward pass against what you say to keep out | +80% time. Turned a blurred watch movement into resolved jewels and screws. On a portrait at 16 steps it invented a second person the prompt never asked for. **Without a negative prompt it does nothing at all** — identical output, identical time |
| **Turbo adapter** | everything at 8 steps with the Viggle adapter | generation 28 s → 20 s, an edit that must keep a face 29 s → 19 s, face indistinguishable. At the 4 steps it advertises it returns ghost hands. Side by side the base model still made the better picture |
| **Sampling** | `base`, or `ancestral` (stochastic) | ancestral: far more skin texture on a face, but it dropped a background the prompt asked for and came out flatter on lettering. The karras, exponential and beta schedules are not offered — the first two return smears, because their sigma remapping fights the dynamic shifting this model ships with, and the third needs scipy |

On a machine that cannot run this usefully, the installer and the app both say
so plainly — with a puppy — and then let you through anyway.

### Two boxes, because a prompt says two different kinds of thing

**Instruction** says what to make. **Look and feel** says how it should look.
They are separate fields, and the split is not tidiness — it came out of a
prompt that produced a picture nobody asked for.

The box held an editorial portrait in a sunlit concrete gallery. Picking
*Studio headshot* from the library appended a second whole description — a
seamless light grey backdrop, framed from the chest up — so the prompt was
asking for two photographs. The model does not refuse that; it picks one or
splits the difference, and the result looks like a mistake with no error
message.

The categories divide cleanly once you read them:

| kind | categories | what a click does |
|---|---|---|
| a whole subject | Starting points, Portrait, Full body, Lettering, Edits | **becomes the Instruction**, replacing what was there |
| one clause about it | Lighting, Camera, Setting, Clothing, Style and grade | **added to Look and feel** |
| what to edit | What to select | **fills the selection field** |

A subject already names its own framing, backdrop and light, so two of them
contradict. A clause names one thing, so several live together — golden hour
*and* a leather jacket *and* medium format are one photograph. Within a group
a second pick swaps the first out: golden hour after studio light means golden
hour, not a prompt asking for two kinds of light at once.

Both boxes go to the model as one string with the complement last, where the
weight is. Everything that hands over a finished prompt — a recipe, *Describe
an image*, the rewriter — fills the Instruction and clears the complement,
because that text already has its look folded in.

Every entry says on its own button which of the three it is, since the only
other way to find out is to click and lose what you had. Two more things this
turned up: *What to select* holds phrases like *the sweater* and was appending
them to the prompt, which describes a sweater instead of selecting one; and
three paths had no catalogue of their own and fell through to "show
everything", which is how the edit screen came to be offering *Lettering*.

### Keeping the face: what it actually costs

A portrait stopped looking like the person, and the first three guesses were
all wrong. It was not nf4, it was not the VAE and it was not the scaffolding.
Reproducing a shipped example exactly — same reference, same words, same seed,
same step count — gave the same man back on today's quantised build, which ruled
out the model. Two things had drifted, and a third was never right:

**Steps.** The sweep that set the default at 16 was run on a watch movement, a
knurled ring and a hand: texture, which is resolved by 16. A face is not. Same
prompt, same seed, same reference: at 16 the result is a thinner, younger,
more conventional version of the person; at 24 it is close; at 28 it is them.
Every example in this repository that keeps a face was made at 28 or 30, which
nobody had written down. The paths that carry a person now ask for **28**, the
rest keep 16, and the server applies the same floor so an agent gets it too.

**Prompt length.** The example that works is thirty-five words — *a colour
editorial magazine portrait, a black blazer over a white shirt, a sunlit
concrete gallery, hard side light, medium format*. Sixty words describing "a
professional studio headshot... a large softbox just off the lens axis with a
reflector filling the shadow side" is a generic photograph of a generic
person, and the model has a strong opinion about what that person looks like.
Say the wardrobe, the place and the light; let the reference say the face.

**And the identity clause has to be last.** Pose and scene each grew that line
for their own reason and the plain portrait never did, which left the longest
prompts as the ones least protected. It is fixed now on every path that has a
person: whose face it is was decided when the reference was dropped in, so
that sentence is the app's, not something the prompt can outrank.

---

## Working on this model: the rule

A portrait stopped looking like the person it was made from, and finding out
why took a day. Five separate decisions had degraded the likeness. Not one of
them was careless -- each was measured, and each measurement was against the
wrong thing.

| decision | measured against | what it did to a face |
|---|---|---|
| 16 steps | a watch movement, a knurled ring, a hand | at 16 the result is a thinner, younger stranger; at 28 it is them |
| nf4 | speed, memory, and a texture | a little worse than int8, on both the base model and the adapter |
| the hdr decoder | saturation and edge energy | almost nothing, 2.8 levels |
| the turbo adapter rejected | the wrong adapter, and without its sigmas | the conclusion was drawn from a broken setup |
| tiling the VAE | peak memory at 4 MP | 24.5 levels and a different man |
| guidance, when editing | nothing -- it was never measured | the frame repainted, and a look silently ignored |

Sharpness, saturation, gigabytes, seconds. **Not one of them was ever measured
against a likeness**, and identity is the one thing that cannot be recovered
afterwards: a soft picture can be sharpened and a flat one regraded, but a
stranger cannot be turned back into the right person.

So, the rule, in the order it matters:

1. **Identity travels through the reference, and everything that touches the
   reference is part of that path** -- including the knobs that look like they
   are about memory. `pipe.vae` decodes the output *and* encodes the condition
   photographs. Turning on tiling for the decode chopped the face up on the way
   in, and the composition changed at the same seed, which a decoder cannot do.
   The likeness is not lost where you are looking; it is lost where it enters.

2. **Never conclude about identity from a measurement of texture.** Steps,
   quantisation, decoders and samplers were all chosen on sharpness or memory,
   and all five were wrong about faces. If a change could touch a person, the
   test is a person.

3. **Describe what the model has to invent. Never re-describe what the
   reference already supplies.** Both the text and the reference go into the
   same encoder -- `encode_prompt` takes the condition images too -- so a
   written face and a photographed face arrive as rival descriptions of one
   thing and the model averages them. Forty words insisting on the identity
   came back *less* like the person than saying nothing about it.

4. **What is read last weighs most.** The identity clause is the app's, fixed,
   and goes after the user's words, where the weight is. It is not the user's
   to phrase: whose face it is was decided when the photograph was dropped in.

5. **Steps are an identity control, not a quality control.** Texture resolves
   by 16. A face does not. Four independent sources put the base pipeline at
   25-50: the model card's editing example passes 40, the ComfyUI template's
   note says "about 40-50 with euler", the most-shared community workflow ships
   25-27, and the turbo adapter describes itself as five passes "instead of 40".

6. **For a likeness, the eye is the instrument.** Mean pixel difference said 24
   levels and could not say that the 24 levels were a different man; it gave
   the same 11.7-13.3 to six person-swap attempts that the eye separated at a
   glance. Numbers locate the cause *after* somebody has seen that something is
   wrong. On the day this was found, the person looking at the face said "that
   is not him" three times before the first measurement agreed.

And the rule is enforced rather than remembered: the test suite has a `same
man` case that puts the reference and the result side by side and asks the VLM
whether it is one person twice. Every one of the five decisions above would
have failed it on the day it was made.

---

## How this differs from a closed model

Not "better". Different in ways that decide whether it fits what you are doing.

| | QwenStudio, locally | A hosted closed model |
|---|---|---|
| **Where the image goes** | nowhere. No upload, no retention, no terms about your inputs | to a server, under whatever the terms say today |
| **Cost per image** | electricity | per call, forever |
| **Works offline** | yes, once the weights are down | no |
| **The prompt you sent** | exactly what you wrote, plus scaffolding you can read in `motor.py` | rewritten by a layer you cannot see |
| **Refusals** | none of its own | a moderation policy that changes without notice |
| **Reproducibility** | same seed, same weights, same image, in a year | the model is swapped underneath you |
| **Identity from a photo** | reference images, no training run | usually not offered at all |
| **Speed** | 62 s at 1 MP, 239 s at 2K, on a 24 GB laptop GPU | seconds |
| **Peak quality** | very good | usually better |
| **Licence to sell the output** | **no** — Qwen Research License | usually yes |

The honest summary: a closed model is faster, often prettier, and legally
simpler to sell. This is private, free to run, reproducible, inspectable, and
yours — and the prompt scaffolding that makes identity transfer work is written
in a file you can open and argue with.

That last point is the interesting one. Every rule the app applies was measured
rather than assumed, and the ones that surprised us are in **Things worth
knowing** below. A closed model gives you a result; this gives you a result and
the reason.

---

## The four reference slots

Each does exactly one job, so they compose without fighting:

| slot | gives | stays out of it |
|---|---|---|
| **Person** | the face and identity | everything else |
| **Pose** | posture, limbs, head tilt | build and height — those stay the person's |
| **Style** | grade, contrast, grain, quality of light | its subject, setting and composition |
| **Scene** | place, wardrobe, framing, lighting | the face |

The prompt is assembled from whichever slots you filled: no pose, no skeleton
clause. Every reference is tagged `<image1>`, `<image2>`… and the tag is
repeated inside its own instruction, because the text encoder reserves one
vision slot per tag and that binding is what keeps them apart.

The order is not yours to choose, and that is deliberate — see below.

The **Style** slot serves two different jobs, and the interface says which one
you are in. In the generation paths it lends a grade — contrast, grain, the
quality of the light. In **Match a style** it lends a whole visual language,
and it is not handed to the generator as a picture at all. See below.

---

## Match a style

Take a photograph and remake it the way another picture is made: same subject,
same pose, same framing, a different medium.

The naive version of this does not work, and finding out why is the useful
part. Handing the model the painting as `<image2>` and asking for *the style of
`<image2>`* barely moves the image. Worse, what does come across is the
painting's **subject**: a lighthouse from an illustration landed in the middle
of a portrait, and a botanical watercolour replaced the sitter entirely with
its own rosemary and fig. One case in three survived.

What works is words. Measured against three phrasings, the only one that moved
the picture named the technique — *flat vector shapes, a small number of flat
colours, no gradients, no photographic texture, crisp geometric edges*. So the
app reads the reference with Qwen3-VL first, asking only **how** the picture is
made and never what it shows, and sends that description to the generator with
a single image. Three of three keep the sitter that way.

The reference picture is still passed when the vision model could not read it,
which is better than nothing. The description it produced is written into the
result's recipe as `tecnica_leida`, so when a restyle goes wrong you can see
whether it failed at reading or at painting — two different repairs.

---

## Tell it what to change

Every other edit in this app selects a region, regenerates it and stitches it
back. That is right when the change is bounded — a sweater, a sky — and wrong
when it is not: swapping the person in a photograph is not a patch, and a patch
is what it looks like. This path hands the model the whole picture, up to three
references and a sentence, and lets it decide where to touch.

The sentence decides whether anything happens at all, and the rule is not
obvious. Measured on 2026-09-23 with the same picture, the same reference and
the same seed:

| instruction | result |
|---|---|
| *Replace the woman with the man from `<image2>`.* | nothing changed |
| *Replace the woman's face and hair with those from `<image2>`.* | nothing changed |
| *Replace the face, the hair and the beard with those from `<image2>`, and change the clothing to a dark t-shirt.* | **the swap happened** |

**Name the attribute, not the person.** It is the rule in QwenLM's own
`prompt_rewrite/prompts/system_prompt_edit.txt`, and the failure it prevents is
the one they call *under-editing*: an output so close to the input that it
looks like nothing ran.

**And the verb matters more than the documentation suggests.** Same picture,
same reference, same seed, the same attributes named, only the verb changed:

| construction | what it did |
|---|---|
| *put X from `<image2>` on …* | the strongest exchange |
| *swap X for …* | close behind |
| *replace X with …* | grafted the new feature onto the old face |
| *change X to …* | the same |
| *give … the X from …* | almost nothing |
| *edit X to match …* | nothing |

`replace` is the verb every example uses, this README's included, and it sits in
the middle.

**And to change who someone is, name the clothing.** Same picture, same
reference, same seed, only the list of attributes growing:

| named | result |
|---|---|
| face, hair, beard | a beard grafted onto the original face |
| + body and build | no further change at all |
| **+ clothing** | **the whole exchange** |
| *the person* | nothing, as always |

Body and build did nothing; the garment did everything. While the original
jacket stays, the jacket holds the original person in place — the model is
painting what can be seen, not reasoning about who someone is. This one would
not have been guessed. A difference metric could not rank these — all six scored between
11.7 and 13.3 against the source, because global difference is dominated by
light rather than by a face. The eye separates them easily, which is worth
remembering before trusting a number that happens to be easy to compute.

Two more of their rules are built into the clause this app wraps around your
sentence, because both were learned here the expensive way:

- **The operation comes first, the preservation after.** This was the other way
  round at first, and the result was an output that ignored the instruction.
- **Preservation stays generic.** The clause says "everything else is
  unchanged" and does not list what that is. Naming the place, the light and
  the framing made the model reproduce a place, a light and a framing — the
  reference's, not the target's. Their phrasing for this is worth keeping:
  say what stays, without repainting it.

Three things were tried and did not help, which is worth writing down so they
are not tried again: the size of the reference image (0.26, 0.92 and 2.0 MP
gave identical output), naming who stays rather than who arrives, and adding an
identity tail after the instruction — that last one made it worse, because with
`<image2>` in the final sentence the model returns `<image2>` whole.

**The rewriter looks at the reference before it writes about it.** Left to the
text alone it guessed: asked to swap a person, it wrote "change the clothing to
the jacket and pants from `<image2>`" about a photograph of a man in a t-shirt.
It now reads the reference with Qwen3-VL first — one sentence, only what can be
seen — and names the garment that is actually there. Same request, same
reference, with and without that look:

| | the instruction it produced |
|---|---|
| text only | …change the clothing to **the jacket and pants** from `<image2>`. |
| having looked | …change the clothing to **a maroon short-sleeved t-shirt**. |

One example in a rule is a template, and two examples are a rule. With a single
worked example the rewriter copied its exact wording and asked for a beard on a
reference that had none; with two examples differing only in what the reference
showed, it started adapting the list — "the face, the hair and the beard" for
one, "the face and the hair" for the other.

Person swapping remains the hard case and is not reliable in both directions;
the model's own card lists face swaps among its known weak points. Ordinary
edits — a garment, an object, a background — work with an ordinary sentence.

---

## Things worth knowing

Everything here was measured in one long session on the hardware listed further
down. Where a belief turned out to be wrong, the wrong version is left in.

**Reference order decides everything.** Identity transfers when the person is
`<image1>`; with the scene first the scene dominates and the face does not
change at all. It fails *silently*, producing a plausible image that is simply
the wrong person. The app always orders person → pose → style → scene, and
`refs` and the `<imageN>` numbering are built in the same function so they
cannot drift apart. Every response carries an `orden` field naming which slot
got which tag.

**A scene with a person in it will hand you that person.** The identity clause
sits at the start of the prompt and the scene reference, closer to the end,
outranks it: with a female scene and a male reference, the result came back as
the woman from the scene — right size, right light, wrong human. The fix is
recency: the prompt now repeats, *after* the scene clause, that the one person
in the result is the subject from `<image1>`. Same seed, same inputs, correct
face.

**With a scene, use one photo of the person.** Several photos of the same
person are read as several *different* people, and you get several people in
the frame.

**The transparency wording is the model author's, not ours.** The app used to
append its own clause about a cut-out on a transparent background, which
worked. Measured against the wrapper the model card publishes — same seed, same
subject — the official one came out at 68.4% real alpha against 65.7%. A small
margin, but there is no reason to invent wording when the people who trained it
published some, so the prompt is now wrapped rather than suffixed.

**Prompts go positive but imperative.** There is no negative guidance at
cfg 1, so "ignore the background" just injects the concept. But softening the
verb breaks it too: "the face is hers" does not transfer, "the subject's face
must match `<image1>` exactly" does. The scaffolding says "the subject" rather
than he or she — a pronoun that disagrees with the reference photo is one more
thing for the model to resolve, and it does not always resolve it your way.

**A reference is ignored unless the prompt names what to take from it.** With a
scene loaded and a neutral prompt, the scene contributed *nothing* — the
scaffolding clause alone was not enough. The app now describes the scene with
Qwen3-VL and appends that description, which is what makes the path work.

**Crop-and-stitch is for a local change, not for a garment.** Replacing a
sweater with a jacket keeps failing, and sharpening the mask made it plainer
why. The crop taken around the mask still shows the sleeves as context, the
model harmonises with what it can see, and out comes a jacket painted over a
sweater whose arms stayed yellow. Recolouring the same sweater in the same
crop works — 86% of the yellow gone, measured on pixels rather than read off a
description. The rule is the shape of the edit, not its difficulty: a change
that stays inside the crop lands, a change to something that leaves the crop
fights the context. For a whole garment, use the whole-frame path.

**"Replace X" is read as "add X on top of X".** Asking for a denim jacket over
the mask of a yellow sweater returned the jacket *open*, with the sweater
underneath. The mask had room for both and the model used it. Saying the
garment is closed and that nothing is visible underneath is what turns a layer
into a replacement.

**There are two int8s and only one of them works here.** The first attempt
used bitsandbytes' `load_in_8bit`, which is LLM.int8(): mixed precision with an
fp16 path for outliers, casting bf16↔fp16 on every matmul. Measured at 2.8
s/step and 24.1 GB peak against 1.26 s/step and 21.2 GB unquantised — slower
*and* larger than not quantising, which is the opposite of the point. What the
profile uses is quanto's weight-only int8, which stores the weights at eight
bits and computes in bf16. That one is what a 20 GB card gets, and against a
face it holds a likeness better than nf4 does. Same two words, opposite
results, which is why the setting records which one made a picture.

**Describing an image costs no extra download.** The image model's text encoder
*is* Qwen3-VL-8B, and the checkpoint on disk carries the vision tower and the
language head. The same 16 GB serve both jobs; it loads in 4-bit so it can sit
beside the DiT.

**You cannot burn the card with this, and the app says so.** The thermal limit
is enforced by the firmware, below the driver: around 83–88 °C it clocks itself
down and near 95 °C it cuts out, and nothing in user space overrides that. What
does happen is a laptop sitting at 85 °C for two hours on a fifty-image batch,
throttling the whole way and taking twice as long while nobody understands why.
So the meter shows the temperature, says when the card is throttling, and a
setting makes a batch wait between images until it drops below a threshold —
80 °C by default, 0 to turn it off. That is not damage protection. It is the
difference between a long run finishing and a long run crawling.

**Close anything else using the GPU first.** Starting with VRAM half full makes
generation crawl with no error at all: utilisation reads 100%, power draw stays
low, nothing finishes. Half an hour was lost to a forgotten ComfyUI process
before the app learned to warn about it — and then a second time, mid-build,
which is why the header now carries a **VRAM meter** reading `18.2 / 23.9 GB`
and naming how much of that belongs to something else. Click it and the app
unmounts its models and hands the memory back, no restart. When the number is
someone else's, the meter says so, because then the fix is not here.

---

## What it costs, measured

Every number here was taken on an RTX 5090 Laptop, 24 GB, at the settings the
app ships with today: **profile L, int8 on both encoders, twenty-eight steps
where a person is involved and sixteen where none is, the decode tiled only
above 2 MP and the encode never**. One machine, so read the shape rather than
the second decimal.

### The ceilings are areas

The profile stores a side, and for a long time every caller squared it. That
is wrong in a way that only shows on a square frame: the side for one
reference was measured on a 3:4 portrait, and a square at the same side is a
third more pixels. Measured with one reference: 1600x1600, 2.40 MP, fits;
1651x1651, 2.60 MP, reaches 20.2 GB and fails against the 20.3 ceiling; a 3:4
frame at the full 1792 is 2.30 MP and peaks at 17.0.

| profile | card | no reference | one reference | two or more |
|---|---|---|---|---|
| XL | 40 GB and up | 4.00 MP | 3.00 MP | 2.25 MP |
| **L** | **20-24 GB** | **4.00 MP** · 2048 | **2.30 MP** · 1792 on the long side | **1.00 MP** |
| M | 12-20 GB | 4.00 MP | 1.00 MP | 1.00 MP |
| S | 8-12 GB | 2.25 MP | 1.00 MP | 1.00 MP |
| MINIMO | under 8 GB | 1.00 MP | 1.00 MP | 1.00 MP |

**Editing the whole frame is capped lower still: 1.50 MP.** It is the only
path that holds a picture at full size *and* produces one, and it runs with
guidance, which is a second forward pass. Enlarging is the exception
and keeps the 2.30: it has no instruction to steer toward, and what guidance
costs it is exactly the size it exists to produce.

Only the L row is measured. The three-quarters that produces 2.30 from 1792 is
applied only where the one-reference side was raised above the several-reference
one, which is exactly where it came from a 3:4 measurement; on the smaller
profiles the two are equal, that side was measured square, and it keeps the
full area. XL is inferred and errs low: the cost of being wrong there is a
refused size, not a reboot.

Underneath all of them is a limit on what the process may allocate at all.
`torch.cuda.set_per_process_memory_fraction` makes PyTorch raise
`OutOfMemoryError` at the moment of the allocation, which the app catches and
turns into a sentence. The reserve is 15% of the card, capped at 4 GB and
floored at 1.5, so a 24 GB card stops at 20.3 and an 8 GB card at 6.5.

That ceiling exists because on 2026-09-23 this machine blue-screened twice,
the same bugcheck with the same four parameters, both times while a test
pushed a 24 GB card against its wall. There was a guard before it -- a thread
watching `nvidia-smi` that cancelled the run past a threshold -- and it never
fired in time, because cancellation lands between denoising steps and the
allocation spike happens inside one. The allocator can do what the watcher
could not.

**An out-of-memory error now hands the card back.** It did not: a failed
allocation kept its blocks, the card sat at 18.4 GB with nothing running, and
the next large request died in four seconds for the previous one's reason
rather than its own. Measured, then fixed at the one place every failing path
passes through.

On Apple Silicon this field is zero: `set_per_process_memory_fraction` has no
MPS equivalent, and there is no honest way to pretend otherwise.

Between images the cache goes back to the driver, so the card sits at 1.2-1.5
GB with the model still mounted, and it stays there across twenty-five chained
calls. The machine stays usable while the app is open.

### How long it takes

Generating, at twenty-eight steps where a person is involved and sixteen where
none is, against the same job with the adapter at seven:

| path | size | base | adapter | |
|---|---|---|---|---|
| text to image | 2048 × 2048 | 232 s | **72 s** | 3.2× |
| a face, one reference | 1344 × 1792 | 278 s | **55 s** | 5.1× |
| transparent cutout | 1344 × 1792 | 278 s | — | |
| into a scene, two references | 1024 × 1024 | 146 s | — | |
| a pose, two references | 896 × 1184 | 113 s | — | |
| a style, two references | 896 × 1184 | 113 s | — | |

Editing, which runs with guidance and therefore two forward passes. The masked paths work on a crop and keep the frame they were given;
the whole-frame ones are capped at 1.50 MP, which is what guidance costs.

| path | size | time | |
|---|---|---|---|
| masked replacement | 1344 × 1792 | **56 s** | the crop is what is paid for |
| instruction, with a reference | 768 × 1024 | 78 s | two references, so 1 MP |
| instruction, whole frame | 1088 × 1440 | 227 s | guided |
| a look, whole frame | 1088 × 1440 | 155 s | guided |
| restyle | 1088 × 1440 | 186 s | guided |
| enlarge | 1536 × 1536 | 184 s · **97 s** with the adapter | unguided on purpose |

The adapter pays most where the work is largest, because its cost is spread
over seven passes rather than twenty-eight. Five minutes against fifty-five
seconds on a full-size portrait is the difference between iterating at
delivery resolution and not.

And the whole run holds: twenty-five calls back to back, resident VRAM between
them 1.2-1.5 GB throughout, nothing accumulating.

### On a smaller card

Two different things decide this, and only one of them is measurable here.

**What the profile costs** was run on this card, with each profile's own
settings -- its quantisation, its ceilings, its offload -- so these are
measurements, not estimates. They are also, read literally, misleading in a
useful way: the smaller profiles come out *faster*, because they ask for less
work.

| profile | asks for | text to image | a face |
|---|---|---|---|
| **L** · int8 | 2048, one reference 1792 | 2048² **232 s** · 72 turbo | 1344×1792 **278 s** · 55 turbo |
| **M** · nf4 | 2048, one reference 1024 | 2048² **292 s** · 79 turbo | 896×1184 **95 s** · 30 turbo |
| **S** · nf4 | 1536, one reference 1024 | 1536² **163 s** · 46 turbo | 896×1184 **94 s** · 28 turbo |

Note the first column against the second: nf4 is *slower* than int8 at the
same 2048² job, 292 s against 232. This README used to say nf4 was the faster
mode, from a comparison against bf16 rather than against int8. Where a card
has room for int8, int8 is both quicker and better at a likeness; nf4 is what
the smaller cards use because 10.1 GB fits in 12 and 12.1 does not.

**What the card costs** is the part that cannot be measured here, so it is
stated rather than measured: multiply the row by how much slower the card is
at bf16 matrix work, and add margin below 12 GB, where the weights stop fitting
and layers start crossing PCIe on every step of every image. A rough shape, to
be treated as the guess it is:

| your GPU | profile | multiply the row above by |
|---|---|---|
| 40 GB and up | XL | ~0.7 |
| 4090 / 5090, 24 GB | L | 1.0 *(this is the card measured)* |
| 4080 / 3090, 16-24 GB | L | ~1.3-1.8 |
| 4070 / 3080, 12-16 GB | M | ~2-3 |
| 8-12 GB | S | ~4-8, and the bus becomes the limit |
| under 8 GB | MINIMO | it runs; plan in tens of minutes |
| Apple Silicon | M | unmeasured, and there is no card here to measure |

The line that matters is 12 GB. Above it the quantised transformer stays
resident and the card is doing arithmetic; below it, layers move across PCIe on
every step and the card is mostly waiting on the bus.

The app does not make anyone read this. It shows the output size and an
estimate above the Generate button and corrects that estimate from your own
runs, so after one generation it is describing your card rather than mine.

### What to use, and when

| | steps | for |
|---|---|---|
| **base** | 28 | the picture you are keeping, and anything with a face in it |
| **turbo** | 7 | finding the framing and the light |
| text to image | 16 | no reference, so there is no likeness to lose |

**Steps are an identity control before they are a quality control.** The sweep
that set 16 was run on a watch movement, a knurled ring and a hand -- texture,
which is resolved by 16. A face is not: same prompt, same seed, same
reference, at 16 the result is a thinner, younger, more conventional version
of the person, at 24 close, at 28 them. The clock barely notices the
difference at 1 MP; the picture does.

**The turbo adapter is a distillation and behaves like one.** At the five
steps its card advertises it turns a tailored blazer into an overcoat and
pulls the shoulders out of shape; at six the shoulder still goes; **seven
holds**, across six seeds. Its published sigma curve is resampled to whatever
count is asked for, because the shape of that curve is part of the
distillation and dropping it is what used to return ghost hands. It is also
distilled without classifier-free guidance, so turning it on turns guidance
off -- paying twice for a pass the student was never taught to use is the
worst of both worlds.

**int8, not nf4, on a card that has room for it.** This README used to argue
the opposite, from a measurement of speed, memory and texture. Against a face
int8 is the better of the two, and the profile for a 20 GB card and up picks
it. nf4 remains what the smaller profiles use, because 10.1 GB fits on a 12 GB
card and 12.1 does not.

> **A recipe made in one quantisation does not reproduce in another at the
> same seed.** Changing the precision changes every step slightly. The seed in
> a recipe is a promise within one precision, which is why the app records the
> quantisation next to it.

**Time grows with the square of the megapixels, not with the megapixels.**
Attention cost rises with the square of the token count, so going from 1 MP to
4 MP is nearly five times the wait rather than four.

**Why a hosted turbo demo is faster, counted rather than guessed.** The Viggle
Space runs the same adapter this app carries, and it is not one thing:

| | there | here | ours to take? |
|---|---|---|---|
| steps | 4 | 28 with a face, 16 without | only by giving up the likeness |
| guidance | off | on, ×2 | the same trade |
| offload | none | model | 27%, measured |
| references | capped at 1 MP | were uncapped | **taken** |
| GPU | large, resident | 24 GB laptop | no |

Twenty-eight steps with guidance is fifty-six transformer passes against their
four, before hardware enters into it. Two of those five rows are choices about
quality, one is not available, and two were worth taking. Reaching for the
adapter collapses the first two rows to theirs -- seven steps and no guidance,
because a distilled model is trained without it -- which is most of where the
five-fold speed-up comes from.

The reference cap is taken and free: their code encodes every conditioning
image at 1024-area, "as in distillation", and this app was passing whatever
arrived. A 12 MP phone photo went into the attention sequence at twelve times
the area the model was trained to see, and the cost was paid in memory rather
than in quality. Capped, that same photo now peaks at 11.1 GB, the same as a
1 MP one.

The offload is a trade rather than a win: warm at 1 MP it is 26 s with the
model offload and 19 s without, but the 1.6 GB of resident weights come
straight off the top of what a reference-bearing job can ask for, and with one
reference the whole allowance is 2.30 MP. It ships as a setting with both
numbers on it, defaulting to the one that keeps the sizes.

> **Sequential offload does not work with nf4 weights.** Reproduced at 0.5 MP
> and 8 steps: `NotImplementedError: Cannot copy out of meta tensor`. accelerate
> cannot move layer by layer what bitsandbytes has already quantised. The
> profiles for cards under 12 GB had it, which means this app could not produce
> a single image on them — and nobody saw it, because the only card here has 24
> GB. They now use the model offload, and a stale `config.json` is corrected at
> load with a line in the log rather than that message about meta tensors.
> Whether the model offload is enough on an 8 GB card is untested: there is no
> such card here to test it with.

### Editing ran without guidance, for as long as there has been editing

`true_cfg_scale` does nothing on its own. The pipeline says so, in a warning
nobody read: *"true_cfg_scale is passed as 4.0, but classifier-free guidance
is not enabled since no negative_prompt is provided."* Guidance needs both
halves -- a scale above one **and** something to steer away from -- and the
generating path passed both while the editing path passed a hardcoded 1.0 and
no negative prompt at all.

Measured on one source at one seed, whole frame, twenty-eight steps:

| guidance | speckle | moved from the source |
|---|---|---|
| 1.0 | 2.51 | 20.7 |
| 2.5 | 2.51 | 20.7 |
| 4.0 | 2.51 | 20.7 |
| **4.0 with a negative prompt** | **1.33** | **17.5** |

The three identical rows are the whole argument: without the second half the
scale is not doing anything, and the app had been shipping the first half
alone. What it cost was not subtle -- a smooth concrete wall came back mottled
and harsh, and a black-and-white look came back in colour, the effect ignored
entirely. It costs a second forward pass: 47 s becomes 87 at 1 MP.

It hid for so long because every edit path except this one works on a crop
around a mask and pastes it back, so whatever drifted was thrown away with the
rest of the frame. Whole-frame instruction editing was added the week this was
found, and it is the first thing that ever showed it.

**Guidance costs a second pass, so a guided edit is a smaller picture.**
This path is already the most expensive there is: it holds the picture being
edited at full size *and* produces one, because the reference cap deliberately
does not apply to the thing you are editing. Walked down on a portrait,
releasing the card between cells so no measurement pays for the one before it:

| | |
|---|---|
| 2.30 MP · 1344×1792 | out of memory |
| 2.00 MP · 1248×1664 | out of memory |
| 1.75 MP · 1184×1568 | out of memory |
| **1.50 MP · 1088×1440** | **150 s** |
| 1.25 MP · 992×1312 | 117 s |

So whole-frame editing is capped at **1.50 MP** where generating with one
reference gets 2.30. Ask for more and the app scales the frame down rather
than failing halfway through.

**With the adapter, editing is unguided, and that is the one place the adapter
should not be used for a picture you are keeping.** The adapter's weights sit
on top of the second pass and the two together do not fit -- `turbo guided`
ran out of memory at a size `base guided` handled -- so turning it on turns
guidance off. Measured at the same size and seed: 3.38 of speckle against
2.50. It stays useful for finding the framing; the version you keep is the
unhurried one.

**Guided and at that size, it does what it is told.** *Change the jacket to
a bright red one* returns a bright red jacket, with the room, the light, the
shadows across the wall and the face all still there. The version of this
paragraph written two hours earlier said the opposite -- that the framing
drifted and a specific instruction might simply not happen -- and it was
describing the path with guidance on and the size not yet brought down to
what guidance costs. At 2.41 MP that is what happens; at 1.50 it is not.

What remains true is narrower: this path regenerates the whole frame, so
everything outside the change is *re-drawn to look the same* rather than
carried across untouched. A masked edit is the one that guarantees the rest of
the picture is identical, pixel for pixel, because it only ever replaces what
is under the mask. Use the mask when the change is bounded and you care about
the rest; use the whole frame when the change is not bounded, or when a mask
would cut through something the model needs to see.


**ComfyUI is still faster for the same image**, and it is worth being precise
about why, because the obvious answer turned out to be wrong. The PR that added
Qwen-Image 2.1 to ComfyUI,
[Comfy-Org/ComfyUI#16400](https://github.com/Comfy-Org/ComfyUI/pull/16400),
highlights prefix caching of text and reference tokens — worth roughly 1.7× on
edits — and this README used to say that was something diffusers does not do.
It does: `QwenImage21Pipeline.__call__` takes `use_kv_cache`, it defaults to
`True`, and we have been getting it all along. The gap is elsewhere: ComfyUI
runs `int8_convrot` weights with kernels built for them, and its memory manager
is better than what `enable_model_cpu_offload` gives us. If raw speed matters
more than being self-contained, use ComfyUI.

---

## Control it from an agent

[AGENTS.md](AGENTS.md) is the operating manual for an agent working on this
repository: the ceilings it must not exceed, the prompting rules that were
measured, and what is deliberately not reliable. `CLAUDE.md` points at the
same file, so Claude Code and Codex read one thing.

```json
{"mcpServers": {"qwenstudio": {
  "command": "D:\\QwenStudio\\.venv\\Scripts\\python.exe",
  "args": ["-m", "qwenstudio.mcp_server"],
  "cwd": "D:\\QwenStudio"}}}
```

On macOS the command is `.venv/bin/python` and `cwd` is wherever you cloned it.

Twelve tools: `status`, `list_poses`, `list_loras`, `list_looks`,
`prompt_library`, `describe_image`, `generate`, `generate_batch`,
`preview_selection`, `inpaint`, `apply_look`, `unmount`.

`inpaint`, `apply_look` and `preview_selection` take either `select` (words) or `mask` (the
path to a black and white image, white where the edit goes), so a script that
already knows the region does not have to describe it back into words.

Images go in and out as **file paths, not base64**. Start the app first: the
MCP server is a thin layer over it, so the model loads once and the UI and the
agent share it. `generate_batch` runs a list of prompts with the model mounted
throughout — made for the case where something else writes the prompts.

Deep links work too: `?caso=pose` opens the app on that path, `?abrir=poses`
(or `prompts`, `ajustes`, `galeria`, `mask`) opens it with that panel showing,
and `?tema=dark` picks the theme. Useful for sending someone the exact screen,
and for an agent that wants to say "open it here" instead of describing three
clicks.

---

## Every image carries its own recipe

<p align="center"><img src="docs/ui-recipe.png" width="820" alt="Clicking a result shows the prompt and settings that produced it"></p>

Click any result, in the gallery or in the run you just made, and it opens what
produced it: the exact prompt, the seed, the steps, the decoder, the LoRA, the
reference order. Then **copy the prompt**, **put it back in the box**, or
**use the image as input** for the case you are in, which is how you chain a
generation into a look without going through the disk.

The recipe is written into the PNG itself as tEXt chunks, the way ComfyUI and
A1111 do it — not into a sidecar and not into a database. It survives the file
being moved, copied or sent to someone, and there is no second store to fall
out of sync with the folder. A file made before this existed simply says so.

**The prompt library knows where you are.** Each use case sees the categories
that apply to it and, above them, starting points written for that path — a
text-to-image case opens on eight complete prompts, an edit opens on garments
and backgrounds. Offering winter coats to someone who is upscaling a photo
only makes them doubt what the field is for.

**Improve it** rewrites a few loose words into a full prompt, using the
Qwen3-VL that is already resident. Text only, no network, about 19 s, and the
system prompt is built from the rules measured in this project rather than a
generic "make it better":

> *a guy on a bike in the rain, night, cool*

becomes

> *A guy on a bike, wearing a dark waterproof jacket with a hood pulled up,
> gloves, and rain-slicked jeans, leaning forward over the handlebars with a
> wet helmet resting on his lap, the bike's chrome fender gleaming under
> streetlight, standing on a wet cobblestone street at night, framed in a
> medium shot from slightly low angle, caught in a vertical rain curtain with
> streaks of light reflecting off puddles, lit by the warm glow of a single
> sodium streetlamp casting long shadows, captured with a shallow depth of
> field using a 35mm lens.*

Subject, then clothing, then place, then framing, then light, then lens — the
order the model actually weights. The workflow that does this elsewhere sends
your prompt to a translation API and then to a hosted LLM; this one never
leaves the machine.

---

## The HDR VAE

The VAE is the last step: it turns the latent the model produced into pixels.
Swapping it changes nothing about *what* was generated and everything about how
it is rendered.

<p align="center"><img src="docs/vae-ab.png" width="860" alt="The same generation decoded by the stock VAE and by the HDR VAE"></p>

Same seed, same prompt, same latent — only the decoder differs. Stock on the
left, HDR on the right. Measured on the pair above:

| | stock | HDR | change |
|---|---|---|---|
| saturation | 0.2391 | 0.2851 | **+19.2%** |
| gradient energy | 0.0136 | 0.0172 | **+27.1%** |
| contrast | 0.2279 | 0.2292 | +0.5% |
| mean luminance | 0.2409 | 0.2417 | +0.3% |

The last two rows are the interesting ones: it is not simply pushing every
slider. Contrast and exposure sit still while colour and edge detail come up —
you can see it in the rim light on the hair and in the texture of the beard.

It is **on by default** when the file is present, and there is a switch in
Settings. The trade is real and its author states it: SSIM drops from 0.958 to
0.944 and PSNR loses 6 dB. This VAE does not reconstruct the latent more
faithfully, it interprets it with more contrast, more edge and more saturation.
For a portrait that reads as better. For a faithful reproduction of a source
image it is the wrong tool, and that is what the switch is for.

Switching decoder costs a reload, about thirty seconds. That is deliberate:
loading the weights into a mounted pipeline leaves tensors stranded on CPU,
because with model offload the weights belong to accelerate and
`load_state_dict` writes underneath its hooks. The first version did it in
place and the next edit died with *"Expected all tensors to be on the same
device"*. The swap now happens before any hook is installed, which means before
the pipeline finishes loading.

The file is **not part of the 31 GB download**. Put
`qwen21HDRVAE_diffusersFormat_fp16.safetensors` into `modelos/` as
`vae_hdr.safetensors` and the option appears; without it the app uses the stock
VAE and says nothing. It comes from
[Qwen 2.1 HDR VAE](https://civitai.com/models/2955671/qwen-21-hdr-vae), which
publishes it in diffusers format specifically because it is built for the
`QwenImage21Pipeline` path — its own notes say ComfyUI support is uncertain.
It is one of the few places where going through diffusers is the advantage
rather than the cost.

---

## Looks and upscaling

**Apply a look** takes one image and a treatment picked from a grid, and
optionally a region painted with the same brush the replacement path uses. With
no region the look grades the whole frame; with one it goes through the same
crop-and-stitch as a replacement, so everything outside the paint returns
unchanged. The
thumbnails are that effect applied to this install's own reference photo,
generated here, so the grid shows this model doing this thing rather than
someone else's pipeline. Effects needing a LoRA stay visible when the file is
missing and say which one they need, rather than disappearing.

Sixteen looks in five groups: grades, relighting, the three Blender viewport
modes from the
[Look Development Pack](https://civitai.com/models/2953686/look-development-pack-for-qwen-image-21)
(a genuine Qwen-Image 2.1 LoRA), and two groups added from what
[TostUI](https://github.com/camenduru/TostUI) exposes — **Redraw** (Anime,
Photographic, Chibi) and **Repair** (Deblur, More detail). Those six are
prompts rather than weights, so they cost nothing but the writing. Two things
they taught, both worth the regeneration they cost:

- The preservation clause the grading looks use — *the face stays exactly as it
  is* — contradicts a look whose whole job is to redraw, and the model answers
  a contradiction by doing nothing. The redrawing looks name what is actually
  kept instead.
- Three of them showed nothing at all against the shared reference photo,
  because that photo is already a sharp photograph. A thumbnail that undersells
  the effect is worse than no thumbnail, so Photographic now starts from a
  drawing and Deblur and More detail from that same photo broken on purpose.

**Rescaling is in the interface because it got fast enough to be.** The
technique always worked — the image goes back in as its own reference and the
model redraws it larger, which recovers real detail instead of interpolating
pixels — but under bf16 it took **754 seconds**, and twelve minutes for one
upscale is not a feature. Quantised it is **132 seconds** at twenty-eight steps
and **97** with the adapter.

It asks for the whole allowance, which is why it was the first path to find
that the ceiling is an area: it wanted a square at the ceiling side, 3.21 MP
with the source in front of the model, and that could not have worked on any
day. It now lands at 1536 × 1536 from a square source, and keeps the source's
shape when it is not square.

---

## LoRAs

Drop `.safetensors` files into `loras/` and reload. The selector appears under
the prompt only when there is something in the folder, with a weight beside it.

**Check which model a LoRA was trained for.** The relight LoRAs circulating on
Civitai — [dx8152's Qwen-Image-Edit 2509 Relight](https://civitai.com/models/2076009/qwen-image-edit2509-relight),
[Relight_Qwen edit 2511](https://civitai.com/models/2293278/relightqwen-edit-2511) —
are built for **Qwen-Image-Edit 2509/2511**, a different generation with a
different architecture. They are not interchangeable with Qwen-Image 2.1 and
are not shipped as use cases here, because none of them has been verified
against this model. Loading one aimed at another architecture is treated as a
user error rather than a crash: the app says so and carries on unmodified.

If you find or train a LoRA that genuinely targets Qwen-Image 2.1, it drops
straight in. Reference-based identity already works without one, which is why
there is no training step in this project at all.

---

## Mounting and unmounting

Three models want the same GPU: the 7B image transformer, Qwen3-VL for
description, and CLIPSeg for segmentation. The registry in `recursos.py` knows
which can coexist:

```
imagen   ->  unmounts vision and segmenta   (generating peaks near 21 GB)
vision   ->  unmounts segmenta              (7 GB sits beside the idle DiT)
segmenta ->  unmounts vision
```

The image pipeline is never unmounted: with model offload its weights live in
CPU memory and cost about 0.4 GB idle, so evicting it would only buy a reload.
For batch work there is a setting that keeps everything mounted and skips the
swapping entirely.

---

## Testing

```bash
.venv\Scripts\python.exe herramientas\pruebas\todos_los_caminos.py
```

Twenty-one cases, run against the live app. They check the **shape** of what came
back, not just the absence of an exception — a 1024 square returned when 16:9
was asked for is broken even though nothing raised.

Where the instruction can be read off the image, **Qwen3-VL looks at the
result** and the case fails if the model did not do what was asked. That is
what caught the layered-jacket bug above: the image was the right size, the
mask was right, and the edit was wrong.

```bash
.venv\Scripts\python.exe herramientas\revision_ui.py
```

A static pass over the interface, which is one Python string holding HTML, CSS
and JS and therefore type-checked by nobody. It catches the failures that do
not raise: a colour token left behind by a rename (the element just renders
transparent), a `$('#id')` whose element was deleted (the handler silently
never binds), a dialog with no way out, a duplicate id, Spanish text that
escaped into the English interface. Two of those had already shipped in this
file before the script existed, which is why it exists.

```bash
.venv\Scripts\python.exe herramientas\revision_idioma.py
```

The same idea applied to the language rule. Everything committed here is
English, and this reads every tracked Python file looking for Spanish in a
comment, a docstring or a string the user reads -- while knowing that the
identifiers are Spanish and skipping them. It exists because the rule was
broken twice and neither time was noticed: one check only looked at
whole-line comments and missed every trailing one after code, the next
missed console output altogether.

---

## Layout

    qwenstudio/hardware.py       hardware detection and load profile
    qwenstudio/motor.py          weights download, the pipeline, the scaffolding
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
    herramientas/                pose library builder, packager, mark, tests
    docs/                        screenshots and the written explainer
    poses/ loras/ modelos/ salidas/

---

## Profiles

Hardware is detected before anything is installed and decides dtype,
quantisation, offload and maximum resolution. The download is the same in every
profile; the profile changes how it is loaded.

| VRAM (CUDA) | quant | offload | alone | one reference | several | allocator ceiling |
|---|---|---|---|---|---|---|
| ≥ 40 GB | — | — | 2048 | 2048 | 1536 | card − 4 GB |
| 20–40 | int8 | model | 2048 | 1792 | 1024 | card − 4 GB |
| 12–20 | nf4 | model | 2048 | 1024 | 1024 | card − 15% |
| 8–12 | nf4 | model | 1536 | 1024 | 1024 | card − 15% |
| < 8 | nf4 | model | 1024 | 1024 | 1024, and the puppy | card − 1.5 GB |

Those are sides; what a job actually spends is area, and with exactly one
reference the allowance is the area of a 3:4 frame at that side rather than
the square. On this card that is 2.30 MP. The table above is the ladder, and
[What it costs, measured](#what-it-costs-measured) has the areas and the
measurements behind them.

Every quantised profile uses the **model** offload. Sequential offload cannot
move layer by layer what bitsandbytes has already quantised, so the two
smallest profiles used to carry a combination that could not produce a single
image.

The sizes are advisory and the last column is not. A size can be wrong by a
gigabyte and the worst that happens is a sentence on screen; before the
allocator ceiling existed, being wrong by a gigabyte took the machine down.

On Apple Silicon there is no quantisation (bitsandbytes has no MPS backend);
the profile adjusts dtype and offload instead, and refuses under 24 GB of
unified memory. **The macOS path is written but has never been run** — only
Windows/CUDA has been verified, and the unified-memory thresholds are judgment,
not measurement. Treat them as a starting point.

---

## Licences

| | |
|---|---|
| **Qwen-Image 2.1** | Qwen Research License — **non-commercial**. This is the binding one. |
| **Qwen3-VL-8B** | ships inside the same checkpoint, same licence |
| **CLIPSeg** (`CIDAS/clipseg-rd64-refined`) | MIT |
| **Inter Tight** (bundled in `qwenstudio/estatico/fuentes/`) | SIL Open Font License 1.1 |
| **This code** | MIT — but the model it drives is not, and that governs what you may do with the output |

`ejemplos/person.jpg` is a photograph of a real person, supplied by the owner
of this repository; whoever clones it receives that photograph too. The scene
and style references are model output, not photographs of anyone. To swap any
of them, replace the file and regenerate the sheet each case shows.

Superside is a trademark of its owner. This repository is an independent
exploration and uses no Superside trademark; the palette and typeface choices
are a visual reference, not a claim of association.
