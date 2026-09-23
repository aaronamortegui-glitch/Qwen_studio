"""Build docs/QwenStudio.pdf — the written explanation of the system.

    .venv\\Scripts\\python.exe herramientas\\explicativo.py

Needs reportlab (a tool-only dependency; the app itself does not use it) and
Inter Tight, which it fetches from Google Fonts the first time and caches in
herramientas/.fuentes/ rather than committing 600 KB of TTF that only this
script reads.

The document is set in the same palette as the interface, for the same reason
the interface has one: a thing that explains an exploration should look like
the exploration.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, KeepTogether,
                                NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fuentes")

HUESO = colors.HexColor("#f7f9f2")
TINTA = colors.HexColor("#0a211f")
LIMA = colors.HexColor("#d8ff85")
VERDE = colors.HexColor("#2a4e45")
TENUE = colors.HexColor("#4a5d59")
LINEA = colors.HexColor("#dde3d6")
SUAVE = colors.HexColor("#eef3e4")

MARGEN = 20 * mm


# ------------------------------------------------------------------ fuentes

def _fuentes() -> tuple[str, str]:
    """Register Inter Tight, downloading it once. Falls back to Helvetica."""
    os.makedirs(FUENTES, exist_ok=True)
    quiere = {"400": "InterTight.ttf", "600": "InterTight-Bold.ttf"}
    faltan = [w for w, f in quiere.items() if not os.path.exists(os.path.join(FUENTES, f))]
    if faltan:
        try:
            req = urllib.request.Request(
                "https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;600",
                headers={"User-Agent": "Mozilla/4.0"})       # UA viejo -> devuelve ttf
            css = urllib.request.urlopen(req, timeout=30).read().decode()
            for bloque in css.split("@font-face")[1:]:
                u = re.search(r"https://[^)]*\.ttf", bloque)
                w = re.search(r"font-weight:\s*(\d+)", bloque)
                if u and w and w.group(1) in quiere:
                    urllib.request.urlretrieve(u.group(0),
                                               os.path.join(FUENTES, quiere[w.group(1)]))
        except Exception as e:
            print(f"  ! no pude bajar Inter Tight ({e}); sigo con Helvetica")
    try:
        pdfmetrics.registerFont(TTFont("IT", os.path.join(FUENTES, quiere["400"])))
        pdfmetrics.registerFont(TTFont("IT-B", os.path.join(FUENTES, quiere["600"])))
        return "IT", "IT-B"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


R, B = _fuentes()

# ------------------------------------------------------------------ estilos

def _p(size, leading, color=TINTA, font=None, space=0, **kw):
    return ParagraphStyle(f"s{size}{leading}{color}{space}{kw}", fontName=font or R,
                          fontSize=size, leading=leading, textColor=color,
                          spaceAfter=space, alignment=TA_LEFT, **kw)


CUERPO = _p(10, 15.6, TINTA, space=8)
TENUE_P = _p(9.4, 14.6, TENUE, space=7)
H2 = _p(19, 23, TINTA, B, space=9)
H3 = _p(11.5, 15, TINTA, B, space=5)
OJO = _p(11.5, 17.5, VERDE, space=10)
PIE = _p(7.8, 10, TENUE)


CELDA = _p(9, 12.4)
CELDA_B = _p(9, 12.4, font=None, space=0)


def _seccion(titulo, primero):
    """An H2 and whatever comes next, kept together.

    A heading at the foot of a page with its text on the next one is the
    easiest way to make a document look broken without being broken.
    """
    return KeepTogether([Paragraph(titulo, H2), primero])


def _tabla(filas, anchos, cabecera=True):
    """Every cell is wrapped in a Paragraph.

    A bare string in a reportlab Table does not wrap to the width: it runs over
    the next column without warning. Only a Paragraph breaks the line, so no
    naked text goes in here.
    """
    celda_h = ParagraphStyle("celda_h", parent=CELDA, fontName=B)
    envuelto = [[Paragraph(str(c), celda_h if (cabecera and i == 0) else CELDA)
                 if not hasattr(c, "wrap") else c
                 for c in fila]
                for i, fila in enumerate(filas)]
    t = Table(envuelto, colWidths=anchos, hAlign="LEFT")
    est = [
        ("FONT", (0, 0), (-1, -1), R, 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), TINTA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINEA),
    ]
    if cabecera:
        est += [("BACKGROUND", (0, 0), (-1, 0), SUAVE)]
    t.setStyle(TableStyle(est))
    return t


# ------------------------------------------------------------------ paginas

def _marca(canvas, x, y, lado, fondo, figura):
    """The mark, drawn once and reused by both page templates.

    The coordinates are the interface's SVG on a 48-unit canvas, so the app's
    icon and the document's are the same shape rather than two similar ones
    drifting apart with every touch-up.
    """
    import math
    u = lado / 48.0
    canvas.setFillColor(fondo)
    canvas.roundRect(x, y, lado, lado, 12 * u, fill=1, stroke=0)

    # the pdf's y axis goes up and the svg's goes down, so y becomes 48 - y
    cx, cy, rm, grosor, largo = 22.8, 48 - 21.8, 10.9, 4.6, 9.0
    canvas.setStrokeColor(figura)
    canvas.setLineWidth(grosor * u)
    canvas.setLineCap(1)
    canvas.circle(x + cx * u, y + cy * u, rm * u, fill=0, stroke=1)
    ang = math.radians(45)
    x1, y1 = cx + rm * math.cos(ang), cy - rm * math.sin(ang)
    x2, y2 = x1 + largo * math.cos(ang), y1 - largo * math.sin(ang)
    canvas.line(x + x1 * u, y + y1 * u, x + x2 * u, y + y2 * u)


def _fondo(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(HUESO)
    canvas.rect(0, 0, *A4, fill=1, stroke=0)
    # the mark, small, top left
    x, y, s = MARGEN, A4[1] - MARGEN + 3 * mm, 6.5 * mm
    _marca(canvas, x, y, s, TINTA, LIMA)

    canvas.setFont(R, 7.8)
    canvas.setFillColor(TENUE)
    canvas.drawString(x + s + 3 * mm, y + 1.8 * mm, "QwenStudio")
    canvas.drawRightString(A4[0] - MARGEN, y + 1.8 * mm,
                           "An exploration · not an official tool · non-commercial licence")
    canvas.setStrokeColor(LINEA)
    canvas.setLineWidth(0.5)
    canvas.line(MARGEN, y - 2.5 * mm, A4[0] - MARGEN, y - 2.5 * mm)
    canvas.drawCentredString(A4[0] / 2, MARGEN - 6 * mm, str(doc.page))
    canvas.restoreState()


def _portada(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(TINTA)
    canvas.rect(0, 0, *A4, fill=1, stroke=0)

    s = 26 * mm
    x, y = MARGEN, A4[1] - MARGEN - s
    _marca(canvas, x, y, s, HUESO, VERDE)

    canvas.setFillColor(HUESO)
    canvas.setFont(R, 44)
    canvas.drawString(MARGEN, y - 26 * mm, "QwenStudio")
    canvas.setFont(R, 14.5)
    canvas.setFillColor(colors.HexColor("#a9bdb6"))
    for i, ln in enumerate([
            "Running an open image model entirely on your own machine:",
            "what it takes, what it gives you, and where it is worse."]):
        canvas.drawString(MARGEN, y - 38 * mm - i * 7 * mm, ln)

    canvas.setFillColor(LIMA)
    canvas.roundRect(MARGEN, 52 * mm, A4[0] - 2 * MARGEN, 30 * mm, 4 * mm, fill=1, stroke=0)
    canvas.setFillColor(TINTA)
    canvas.setFont(B, 10.5)
    canvas.drawString(MARGEN + 8 * mm, 74 * mm, "This is an exploration, not a product.")
    canvas.setFont(R, 9.3)
    for i, ln in enumerate([
            "Not an official Superside tool, not affiliated with or endorsed by Superside,",
            "and not endorsed by the Qwen team or Alibaba. Qwen-Image 2.1 is published under",
            "the Qwen Research License: personal and research use only."]):
        canvas.drawString(MARGEN + 8 * mm, 67 * mm - i * 5 * mm, ln)

    canvas.setFillColor(colors.HexColor("#6f8a83"))
    canvas.setFont(R, 8.4)
    canvas.drawString(MARGEN, 34 * mm,
                      "Qwen-Image 2.1  ·  diffusers  ·  Qwen3-VL-8B  ·  CLIPSeg  ·  MCP")
    canvas.drawString(MARGEN, 29 * mm,
                      "Measured on an RTX 5090 Laptop, 24 GB  ·  September 2026")
    canvas.restoreState()


# ------------------------------------------------------------------ contenido

def construir() -> str:
    docs = os.path.join(APP, "docs")
    os.makedirs(docs, exist_ok=True)
    salida = os.path.join(docs, "QwenStudio.pdf")

    doc = BaseDocTemplate(salida, pagesize=A4, title="QwenStudio",
                          author="An exploration", subject="Local Qwen-Image 2.1",
                          leftMargin=MARGEN, rightMargin=MARGEN,
                          topMargin=MARGEN, bottomMargin=MARGEN)
    marco = Frame(MARGEN, MARGEN, A4[0] - 2 * MARGEN, A4[1] - 2 * MARGEN - 6 * mm,
                  id="cuerpo", showBoundary=0)
    doc.addPageTemplates([
        PageTemplate(id="portada", frames=[marco], onPage=_portada),
        PageTemplate(id="normal", frames=[marco], onPage=_fondo),
    ])

    an = A4[0] - 2 * MARGEN
    f = []

    # --- portada (vacia: la dibuja onPage) --------------------------------
    # NextPageTemplate is mandatory: the first template stays active until it
    # is changed, and the cover would be painted over the whole document
    f += [Spacer(1, 1), NextPageTemplate("normal"), PageBreak()]

    # --- 1. what it is -----------------------------------------------------
    f += [CondPageBreak(45 * mm),
          Paragraph("What this is", H2),
          Paragraph("An image generation and editing app that runs Qwen-Image 2.1 on one "
                    "machine, with nothing in between. No ComfyUI, no cloud, no account, no "
                    "API key. You clone it, double-click an installer, and 31 GB of weights "
                    "come down once.", OJO),
          Paragraph("The installer downloads its own Python. It touches no system Python, "
                    "installs nothing globally, and changes no PATH. Delete the folder and "
                    "every trace is gone. Before installing anything it reads the hardware "
                    "and picks a profile from it — which PyTorch wheel, which dtype, "
                    "whether to quantise, how much to offload, what resolution to cap at — "
                    "so a 10 GB card and a 48 GB card both get something that runs.", CUERPO),
          Spacer(1, 5 * mm),
          Paragraph("Installing it", H3),
          _tabla([
              ["Step", "Windows", "macOS"],
              ["1. Get the folder", "clone it, or unzip QwenStudio.zip", "the same"],
              ["2. Install", "double-click INSTALL.bat", "run ./install.command"],
              ["3. Start it", "double-click RUN.bat", "run ./run.command"],
          ], [an * .26, an * .37, an * .37]),
          Spacer(1, 3 * mm),
          Paragraph("The installer builds a private .venv with uv, probes the machine "
                    "and writes config.json from what it finds. The first start "
                    "downloads about 31 GB of weights into modelos/ and is the only "
                    "slow one; everything after that is local. The page opens by "
                    "itself at 127.0.0.1:7860, results land in salidas/, and "
                    "python bootstrap.py prints what this particular machine will get "
                    "— profile, resolution ceilings, expected times — before anything "
                    "is installed at all.", CUERPO),
          Paragraph("Needed: an NVIDIA card with 8 GB or more, or an Apple Silicon Mac "
                    "with 24 GB of unified memory; 40 GB of free disk; 32 GB of system "
                    "RAM is comfortable. Below that it still installs, and says what it "
                    "will cost.", TENUE_P),
          Spacer(1, 5 * mm),
          Paragraph("Two ways to use it", H3),
          Paragraph("<b>By hand.</b> A page opens at 127.0.0.1:7860. Twelve use cases, each "
                    "showing only the inputs it needs, each opening with a worked example "
                    "already in its boxes and the result of that exact example beside it. "
                    "The first screen shows this + this = this instead of an empty form.",
                    CUERPO),
          Paragraph("<b>By agent.</b> Point Claude Code, Codex or any MCP client at the "
                    "folder. Twelve tools — generate, edit, describe, batch, pose library, "
                    "prompt library — drive the same engine the interface drives. The "
                    "model loads once and both share it, so the page can stay open while an "
                    "agent works through a list of prompts.", CUERPO),
          Paragraph("That second door is the point. Everything the interface can do is an "
                    "HTTP endpoint; the agent layer is thin on purpose. This is not a wrapper "
                    "around a script, it is a local service with two front doors.", CUERPO),
          Spacer(1, 5 * mm),
          Paragraph("What it does", H3),
          _tabla([
              ["Group", "Use case", "What goes in"],
              ["Text to image", "New image", "nothing but the prompt"],
              ["", "Text in the image", "words in quotes come out as lettering"],
              ["From a photo", "New portrait", "person photos"],
              ["", "Character in a scene", "person + a photo of the setting"],
              ["", "Pose my character", "person + pose + optional style and setting"],
              ["", "Transparent cutout", "person → PNG with a real alpha channel"],
              ["", "Free", "everything, nothing assumed"],
              ["Edit a photo", "Apply a look", "image + a treatment picked from a grid"],
              ["", "Tell it what to change", "image + a sentence + up to three references"],
              ["", "Match a style", "image + a picture whose manner you want"],
              ["", "Enlarge", "image, redrawn larger rather than stretched"],
              ["", "Replace something", "image + a selection + what goes there"],
          ], [an * .22, an * .3, an * .48]),
          Spacer(1, 4 * mm),
          Paragraph("An edit selects its region from words or from a brush painted at the "
                    "photo's real resolution. What you leave untouched comes back byte for "
                    "byte — the test suite checks that rather than assuming it.", TENUE_P),
          Spacer(1, 9 * mm)]

    # --- 2. against the closed ones ---------------------------------------
    f += [CondPageBreak(45 * mm),
          Paragraph("How this differs from a closed model", H2),
          Paragraph("Not “better”. Different in ways that decide whether it fits "
                    "what you are doing.", OJO),
          _tabla([
              ["", "QwenStudio, locally", "A hosted closed model"],
              ["Where the image goes",
               "nowhere — no upload, no retention, no terms about your inputs",
               "to a server, under whatever the terms say today"],
              ["Cost per image", "electricity", "per call, forever"],
              ["Works offline", "yes, once the weights are down", "no"],
              ["The prompt you sent",
               "exactly what you wrote, plus scaffolding you can read in a file",
               "rewritten by a layer you cannot see"],
              ["Refusals", "none of its own",
               "a moderation policy that changes without notice"],
              ["Reproducibility", "same seed, same weights, same image, in a year",
               "the model is swapped underneath you"],
              ["Identity from a photo", "reference images, no training run",
               "usually not offered at all"],
              ["Speed", "62 s at 1 MP, 239 s at 2K, on a 24 GB laptop GPU",
               "seconds"],
              ["Peak quality", "very good", "usually better"],
              ["Licence to sell the output", "no — Qwen Research License", "usually yes"],
          ], [an * .22, an * .4, an * .38]),
          Spacer(1, 5 * mm),
          Paragraph("The honest summary: a closed model is faster, often prettier, and "
                    "legally simpler to sell. This one is private, free to run, reproducible, "
                    "inspectable and yours — and the prompt scaffolding that makes "
                    "identity transfer work is written in a file you can open and argue with.",
                    CUERPO),
          Paragraph("That last point carries the most weight. Every rule this app applies "
                    "was measured rather than assumed, and the ones that turned out wrong are "
                    "still written down. A closed model hands you a result. This hands you a "
                    "result and the reason.", CUERPO),
          Spacer(1, 9 * mm)]

    # --- 3. how it works ---------------------------------------------------
    f += [CondPageBreak(45 * mm),
          Paragraph("How it works", H2),
          Paragraph("Four reference slots, one job each", H3),
          Paragraph("The model accepts several reference images. Left to itself it blends "
                    "them; the app gives each one a job and says so in the prompt, so they "
                    "compose instead of fighting.", CUERPO),
          _tabla([
              ["Slot", "Gives", "Stays out of it"],
              ["Person", "the face and identity", "everything else"],
              ["Pose", "posture, limbs, head tilt",
               "build and height — those stay the person's"],
              ["Style", "grade, contrast, grain, quality of light",
               "its subject, setting and composition"],
              ["Scene", "place, wardrobe, framing, lighting", "the face"],
          ], [an * .14, an * .43, an * .43]),
          Spacer(1, 4 * mm),
          Paragraph("Each reference is tagged &lt;image1&gt;, &lt;image2&gt;… and the tag "
                    "is repeated inside its own instruction, because the text encoder reserves "
                    "one vision slot per tag and that binding is what keeps them apart. The "
                    "list handed to the pipeline and the numbering in the prompt are built in "
                    "the same function, so they cannot drift apart, and every response names "
                    "which slot got which tag.", CUERPO),
          Spacer(1, 4 * mm),
          Paragraph("Three models, one GPU", H3),
          Paragraph("The 7B image transformer, Qwen3-VL for description and CLIPSeg for "
                    "segmentation all want the same card. A small registry knows which can "
                    "coexist and swaps the rest out. The image pipeline is never unmounted: "
                    "with model offload its weights live in CPU memory and cost about 0.4 GB "
                    "idle, so evicting it would only buy a reload. For batch work a setting "
                    "keeps everything mounted and skips the swapping.", CUERPO),
          Paragraph("Describing an image costs no extra download, which is the neatest thing "
                    "in the build: the image model's text encoder <i>is</i> Qwen3-VL-8B, and "
                    "the checkpoint already carries the vision tower and the language head. "
                    "The same 16 GB do both jobs.", CUERPO),
          Spacer(1, 4 * mm),
          Paragraph("Where the images go, and how they got there", H3),
          Paragraph("Everything written lands in one folder, and the gallery reads that "
                    "folder rather than a database, so the disk is the single source of "
                    "truth: delete a file there and it disappears from the gallery.", CUERPO),
          Paragraph("The results column is not empty the first time it is opened. It "
                    "carries thirty-one images this install produced, in two groups, each one clickable for "
                    "the prompt, the seed and the settings behind it, and for a button that "
                    "opens the use case it came from with that prompt already written. Five "
                    "of them build on each other — a character invented from a "
                    "paragraph, carried into a portrait, a scene and a cutout, and two of "
                    "those images then edited — because one tool doing a day’s work "
                    "argues better than eight unrelated demonstrations. It steps aside as "
                    "soon as there is work of the user’s own to show.", CUERPO),
          Paragraph("Twelve paths and a handful of tools do not fit on one screen, so the "
                    "footer carries an index of all of them, and each entry is named the "
                    "way someone would ask for it rather than the way the panel is "
                    "labelled. Nobody looking to remove a background guesses that it lives "
                    "under “transparent cutout”, so that is what the index calls "
                    "it, and clicking opens that path already set up. The same footer "
                    "carries the two sentences that matter before an image leaves the "
                    "machine: this is a beta to experiment with, and the model’s "
                    "licence is non-commercial.", CUERPO),
          Paragraph("Each result carries its own recipe, written into the PNG as tEXt "
                    "chunks: the exact prompt, the seed, the steps, the decoder, the LoRA, "
                    "the reference order. Click any image and it opens, with the prompt "
                    "ready to copy, to put back in the box, or the image itself ready to "
                    "become the input of the next step. Into the file rather than a sidecar "
                    "or a database, so it survives the file being moved, copied or sent to "
                    "someone.", CUERPO),
          Spacer(1, 3 * mm),
          Paragraph("Looks, and what was left out", H3),
          Paragraph("A treatment is picked from a grid rather than typed, and every "
                    "thumbnail in it is that effect applied to this install's own reference "
                    "photo, generated on this machine. A look can be confined to a painted "
                    "region instead of covering the frame. Enlarging is its own path: "
                    "the image goes back in as its own reference and is redrawn larger, "
                    "which recovers detail instead of interpolating pixels. It was left "
                    "out of the interface for a while because under bf16 it took 754 "
                    "seconds for one image, and twelve minutes is not a feature. With "
                    "nf4 and a tiled VAE the same job takes 156 seconds, and the button "
                    "came back when the number did.", CUERPO),
          Spacer(1, 3 * mm),
          Paragraph("LoRAs, and a trap worth knowing", H3),
          Paragraph("Drop .safetensors into the loras folder and a selector appears with a "
                    "weight beside it. The catch is generational: the relight LoRAs "
                    "circulating publicly were trained for Qwen-Image-Edit 2509 and 2511, a "
                    "different architecture, and do not transfer to Qwen-Image 2.1. None is "
                    "shipped as a use case here because none has been verified against this "
                    "model. Loading one aimed elsewhere is treated as a user error rather "
                    "than a crash. Reference-based identity already works without any LoRA, "
                    "which is why there is no training step in this project at all.", CUERPO),
          Spacer(1, 3 * mm),
          Paragraph("Editing without touching the rest", H3),
          Paragraph("An edit crops around the mask with padding, regenerates that crop at "
                    "full resolution, and pastes it back through a feathered edge. Detail "
                    "lands where the edit is instead of being spread thin over the whole "
                    "frame, and the untouched area is preserved exactly.", CUERPO),
          Paragraph("Both editing paths run through that same routine, so a look confined "
                    "to a painted region and a replacement are one operation with two "
                    "prompts. The region can be named in words — CLIPSeg finds it, SAM 2 "
                    "sharpens the edge — or painted by hand at the photograph's real "
                    "resolution. A replacement needs a region; a look does not, and without "
                    "one it grades the whole frame.", CUERPO),
          Spacer(1, 3 * mm),
          Paragraph("Knowing what the card is doing", H3),
          Paragraph("The header carries a live reading of the card: memory used against "
                    "memory fitted, refreshed while work runs, with a button that drops the "
                    "cached allocations without unloading the model. Before each image of a "
                    "batch the app can wait for the card to come back under a temperature "
                    "you set. That is not protection from damage — the firmware enforces "
                    "its own limits and nothing here can override them — but a long "
                    "unattended run finishes sooner if it is not being throttled the whole "
                    "way, and a number on screen beats guessing.", CUERPO),
          Paragraph("Deleting from the gallery moves the file to a bin folder on disk "
                    "rather than unlinking it. A grid of thumbnails that look alike is "
                    "exactly where an irreversible click loses the good one; emptying the "
                    "bin stays the user’s decision.", CUERPO),
          Spacer(1, 9 * mm)]

    # --- 4. how to use it well ---------------------------------------------
    f += [CondPageBreak(45 * mm),
          Paragraph("Using it well", H2),
          Paragraph("An open model takes instruction differently from a hosted one, "
                    "and the differences are not guessable. Each line below was "
                    "measured on the same picture with the same seed, changing one "
                    "thing at a time.", OJO),
          _tabla([
              ["Do this", "Because"],
              ["One photo of the person when a scene is loaded too",
               "several are read as several different people, and several people "
               "is what comes back"],
              ["Name the attribute, never the person",
               "“replace the woman with the man” changes nothing; “replace the face, "
               "the hair and the beard” works"],
              ["Prefer “put X from &lt;image2&gt; on…”",
               "that construction gave the strongest exchange; “replace” and "
               "“change” graft, “edit to match” does nothing"],
              ["Name the clothing when changing who someone is",
               "the original garment anchors the original person; body and build "
               "changed nothing on their own"],
              ["Put what matters last",
               "the end of the prompt carries the most weight, which is why the "
               "app appends pose and scene after your words"],
              ["Write a negative prompt before raising CFG",
               "without one, CFG is a no-op: byte-identical output, same time"],
              ["Leave reference images alone",
               "they are encoded near 1 MP regardless; 0.26, 0.92 and 2.0 MP gave "
               "identical results"],
          ], [an * .34, an * .66]),
          Spacer(1, 4 * mm),
          Paragraph("Sixteen steps is the default, swept by eye at 1 MP on subjects "
                    "built to break first. The examples that ship were rendered "
                    "higher, because a thumbnail that undersells the result is worse "
                    "than no thumbnail. Resolution is capped by how many references "
                    "are in play, not by the card alone — the app shows the ceiling "
                    "before it runs, and refuses rather than reaching for it.",
                    TENUE_P),
          Spacer(1, 9 * mm)]

    # --- 5. what was measured ----------------------------------------------
    f += [CondPageBreak(45 * mm),
          Paragraph("What we measured", H2),
          Paragraph("All of it in one long session on an RTX 5090 Laptop with 24 GB. Where a "
                    "belief turned out to be wrong, the wrong version is kept.", OJO)]

    hallazgos = [
        ("Reference order decides everything.",
         "Identity transfers when the person is &lt;image1&gt;. With the scene first, the "
         "scene dominates and the face does not change at all — and it fails silently, "
         "producing a plausible image that is simply the wrong person. The app fixes the "
         "order: person, pose, style, scene."),
        ("A scene with a person in it will hand you that person.",
         "The identity clause sits at the start of the prompt and the scene reference, closer "
         "to the end, outranks it. With a female scene and a male reference, the result came "
         "back as the woman from the scene: right size, right light, wrong human. The fix is "
         "recency — repeat the identity after the scene clause. Same seed, same inputs, "
         "correct face."),
        ("A reference is ignored unless the prompt names what to take from it.",
         "With a scene loaded and a neutral prompt, the scene contributed nothing. The "
         "scaffolding clause alone was not enough. The app now describes the scene with "
         "Qwen3-VL and appends that description, which is what makes the path work at all."),
        ("“Replace X” is read as “add X on top of X”.",
         "Asking for a denim jacket over the mask of a yellow sweater returned the jacket "
         "open, with the sweater underneath. The mask had room for both and the model used "
         "it. Saying the garment is closed and that nothing shows underneath is what turns a "
         "layer into a replacement."),
        ("Prompts go positive but imperative.",
         "At the default cfg of 1 there is no negative guidance, so “ignore the "
         "background” just injects the concept. But softening the verb breaks it too: "
         "“the face is hers” does not transfer, “the subject's face must "
         "match &lt;image1&gt; exactly” does."),
        ("A negative prompt does not exist below cfg 1.",
         "The pipeline accepts a negative prompt at any cfg, and at 1 it is silently "
         "inert: same seed, byte-identical image, identical time, because the second "
         "forward pass is never run. Raised to 3 with something to push against, the "
         "same prompt turned a blurred watch movement into resolved jewels and screws "
         "for 80% more time. The control is offered only above 1, because a control "
         "that looks like it works and does not is worse than no control."),
        ("Style is a description, not a picture.",
         "Handing the model a painting as &lt;image2&gt; and asking for its style barely "
         "moves the image, and what does come across is the painting's subject: a "
         "lighthouse landed in a portrait, and a botanical watercolour replaced the "
         "sitter with its own rosemary and fig. Naming the technique in words — flat "
         "colours, no gradients, crisp geometric edges — is what works. So the app "
         "reads the reference with Qwen3-VL first, asking only how the picture is made "
         "and never what it shows, and sends that sentence with a single image."),
        ("Steps are cheap on the clock and not cheap in the picture.",
         "At 1 MP the clock barely moves between 8 and 25 steps — 18 s to 38 s — "
         "which made steps look free. The picture disagrees: 8 is mush, 12 leaves a watch "
         "movement soft, 16 resolves its screws, and 20 and 25 add nothing. Measuring "
         "the wrong quantity is how a default ends up at 12."),
        ("int8 quantisation was counterproductive.",
         "The hypothesis was that it would save memory. Measured: 2.8 s/step and 24.1 GB "
         "peak, against 1.26 s/step and 21.2 GB unquantised — bitsandbytes int8 casts "
         "bf16 to fp16 and back on every matmul. It is not in the profile ladder at all."),
        ("An edit names the attribute, never the person.",
         "“Replace the woman with the man from &lt;image2&gt;” changes nothing, twice "
         "over. “Replace the face, the hair and the beard” works. It is the rule "
         "in QwenLM’s own system_prompt_edit.txt, and the failure it prevents is the "
         "one they name: under-editing, an output so close to the input that it looks "
         "like nothing ran. Two more of theirs, learned here the expensive way: the "
         "change goes before the preservation, and the preservation stays generic — "
         "listing the place, the light and the framing made the model repaint them, and "
         "what it repainted was the reference’s."),
        ("The verb decides more than the documentation admits.",
         "Same picture, same reference, same seed, the same attributes named, only the "
         "verb changed. “Put X from &lt;image2&gt; on …” did the most and "
         "“swap X for …” came close; “replace” and "
         "“change” grafted the new feature onto the old face instead of "
         "exchanging it; “give” and “edit to match” did almost "
         "nothing. Replace is the verb every example uses, this one included, and it "
         "sits in the middle."),
        ("One example is a template; two are a rule.",
         "The prompt rewriter was given one worked example of an edit "
         "instruction and copied its wording exactly, asking for a beard on a "
         "reference that had none. Two examples differing only in what the "
         "reference showed, and it began adapting the list instead of "
         "reproducing it. The same sentence that teaches a form also teaches "
         "that the form is fixed, unless something shows it is not."),
        ("Close anything else using the GPU first.",
         "Starting with VRAM half full makes generation crawl with no error: utilisation "
         "reads 100%, power draw stays low, nothing finishes. Half an hour went to a "
         "forgotten ComfyUI process before the app learned to warn about it."),
    ]
    for titulo, texto in hallazgos:
        f.append(KeepTogether([Paragraph(titulo, H3), Paragraph(texto, CUERPO),
                               Spacer(1, 2.5 * mm)]))

    # the heading and its table do not separate: a lone "Numbers" at the foot
    # of a page says nothing
    f += [Spacer(1, 3 * mm),
          KeepTogether([Paragraph("Numbers", H3),
          _tabla([
              ["", ""],
              ["1 MP (1024 px), 16 steps, warm", "26 s, 7.3 GB peak"],
              ["2 MP (1440 px), 16 steps", "51 s, 7.3 GB peak"],
              ["4 MP (2048 px, 2K native), 16 steps", "122 s, 7.5 GB peak"],
              ["A look or an edit, 1 MP", "26 s, 9.2 GB peak"],
              ["Rescale to 2K", "156 s, 18.2 GB peak"],
              ["Model load, first call", "27–35 s"],
              ["Segmentation, three phrases", "0.9 s"],
              ["Describe an image (Qwen3-VL, 4-bit)", "5–9 s, 7.1 GB"],
              ["Package size, without weights", "22 MB"],
              ["Weights", "~31 GB, downloaded once"],
          ], [an * .55, an * .45], cabecera=False)]),
          Spacer(1, 4 * mm),
          Paragraph("Those figures are nf4 on both the transformer and the text encoder, "
                    "which on this architecture is not the poor mode but the good one: "
                    "faster than bf16, half the memory, and the only way 2K works at all. "
                    "The same seed in bf16 and in nf4 gives two different pictures, so a "
                    "recipe only reproduces within one precision.", TENUE_P),
          Spacer(1, 3 * mm),
          Paragraph("Two ceilings, not one. Generating at 2K peaks at 7.5 GB; rescaling to "
                    "2K, where the picture is its own reference, peaks at 18.2. The profile "
                    "carries both numbers, because quoting only the first is how a card "
                    "gets promised a size it will page on.", TENUE_P),
          Spacer(1, 3 * mm),
          Paragraph("ComfyUI is still about four times faster for the same image: it uses "
                    "int8_convrot weights with kernels built for them, a better memory "
                    "manager, and prefix caching of text and reference tokens worth roughly "
                    "1.7× on edits by itself. If raw speed matters more than being "
                    "self-contained, use ComfyUI. This exists to be self-contained.",
                    TENUE_P),
          Spacer(1, 9 * mm)]

    # --- 5. how it is checked, and licences --------------------------------
    f += [CondPageBreak(45 * mm),
          Paragraph("How it is checked", H2),
          Paragraph("Nineteen cases run against the live app. They check the shape of what "
                    "came back, not just the absence of an exception: a 1024 square returned "
                    "when 16:9 was asked for is broken even though nothing raised.", CUERPO),
          Paragraph("Where the instruction can be read off the image — a blazer, a "
                    "kitchen, a garment that is no longer yellow — Qwen3-VL looks at the "
                    "result and the case fails if the model did not do what was asked. That "
                    "is what caught the layered-jacket bug: the image was the right size, the "
                    "mask was right, and the edit was wrong. Shape checking alone would have "
                    "passed it.", CUERPO),
          Spacer(1, 6 * mm),
          CondPageBreak(45 * mm),
          Paragraph("Licences", H2),
          _tabla([
              ["", ""],
              ["Qwen-Image 2.1",
               "Qwen Research License — non-commercial. This is the binding one."],
              ["Qwen3-VL-8B", "ships inside the same checkpoint, same licence"],
              ["CLIPSeg", "MIT"],
              ["Inter Tight", "SIL Open Font License 1.1"],
              ["This code", "MIT — but the model it drives is not"],
          ], [an * .3, an * .7], cabecera=False),
          Spacer(1, 5 * mm),
          Paragraph("Nothing made with this belongs in client work without a separate licence "
                    "from Alibaba. The interface borrows a palette and a typeface as a visual "
                    "reference; the mark is an original symbol drawn for this repository and "
                    "no trademark is used. Superside is a trademark of its owner, and this is "
                    "an independent exploration with no claim of association.", TENUE_P),
          Spacer(1, 8 * mm),
          Paragraph("The macOS path is written but has never been run. Only Windows with CUDA "
                    "has been verified, and the unified-memory thresholds for Apple Silicon "
                    "are judgment rather than measurement. Treat them as a starting point.",
                    TENUE_P)]

    doc.build(f)
    return salida


if __name__ == "__main__":
    p = construir()
    print(f"  {os.path.relpath(p, APP)}  {os.path.getsize(p)/1024:.0f} KB")
    sys.exit(0)
