"""Prompt library for Qwen-Image 2.1.

Written for how this model actually behaves, measured over a long session:

  - it reads natural declarative English, not comma-separated tags. "soft light
    falling from a window on the subject's left" beats "soft lighting, window
    light, left";
  - there is no negative guidance at cfg 1, so nothing here is phrased as a
    prohibition. Describe what should be there, never what should not;
  - the verb carries weight. "must match exactly" holds identity where "is the
    same" quietly does not;
  - it renders text. Words inside double quotes come out as lettering, which is
    why "Lettering" is a category here and not a footnote.

Each entry is one clause of a photograph, not a whole photograph: a subject,
then the light, then the lens, then the grade. The app appends whichever you
pick to what is already written, so they are built to stack, and each one names
a thing that can be seen rather than an adjective like "beautiful" that gives
the model nothing to draw.

Nothing here says "she" or "he": the scaffolding calls the person "the subject",
and a snippet that disagrees with the reference photo fights it.
"""

from __future__ import annotations

# categoria -> lista de (etiqueta corta, texto)
BIBLIOTECA: dict[str, list[tuple[str, str]]] = {

    "Portrait": [
        ("Studio headshot", "A professional studio headshot against a seamless light grey "
         "backdrop, framed from the chest up and square to camera, a large softbox just off "
         "the lens axis with a reflector filling the shadow side, sharp focus on the eyes."),
        ("Editorial", "An editorial magazine portrait, framed three-quarter length and slightly "
         "off-centre with room to one side, a hard key light raking across the face and deep "
         "shadow on the far side, shot on medium format with an 80mm lens."),
        ("Corporate", "A corporate profile photograph in a modern glass office, standing with "
         "the city out of focus behind, daylight from a wall of windows on one side, a relaxed "
         "and confident expression, 50mm lens at a wide aperture."),
        ("Environmental", "An environmental portrait in the place where the subject works, the "
         "tools and the room given as much frame as the person, available light only, wide "
         "framing on a 35mm lens."),
        ("Candid", "A candid unposed moment caught mid-movement, the subject looking away from "
         "the camera, warm late afternoon light, shallow depth of field with the background "
         "dissolving into soft shapes."),
        ("Black and white", "A black and white portrait with deep contrast and true blacks, "
         "light raking across the face from one side, visible film grain, printed on fibre "
         "paper."),
        ("Close-up", "A tight close-up filling the frame from the brow to the chin, soft "
         "directional light picking out the texture of the skin, shot on a 100mm lens at a "
         "wide aperture."),
    ],

    "Full body": [
        ("Standing", "Full body photograph, standing square to camera with the whole body from "
         "head to feet inside the frame, weight on one leg, arms relaxed at the sides."),
        ("Walking", "Full body photograph mid-stride walking toward the camera, natural arm "
         "swing, one foot off the ground, the background compressed behind on a long lens."),
        ("Seated", "Full body photograph seated on a plain wooden chair, one leg crossed over "
         "the other, leaning slightly forward with the forearms on the knees."),
        ("Three-quarter", "Framed from the knees up, the body turned thirty degrees away from "
         "the camera while the face returns to it."),
        ("Against a wall", "Full body photograph leaning back against a painted brick wall, one "
         "shoulder taking the weight, late sun throwing a long shadow across the bricks."),
        ("Lookbook", "A fashion lookbook frame, full length on a clean studio cyclorama, the "
         "garment readable from the shoulder seam to the hem."),
    ],

    "Lighting": [
        ("Window light", "Soft daylight falling from a large window just off to one side, a "
         "gentle falloff across the face and a bright catchlight in the eyes."),
        ("Golden hour", "Warm low sun a few minutes before it sets, long shadows across the "
         "ground and a golden rim along the hair and the shoulders."),
        ("Overcast", "Flat overcast daylight, even and almost shadowless, the colours muted "
         "and true, no specular highlights anywhere."),
        ("Three point", "Three point studio lighting: a soft key at forty-five degrees, a "
         "subtle fill on the shadow side, and a hard rim separating the subject from the "
         "background."),
        ("Hard sun", "Direct midday sun overhead, hard-edged shadows under the brow and the "
         "chin, high contrast and saturated colour."),
        ("Candlelight", "Warm candlelight coming from just below the frame, the light "
         "flickering and falling away fast into a deep surrounding dark."),
        ("Backlit", "Strong backlight behind the subject blowing out the edges, a glowing rim "
         "through the hair, the face lifted back up by a reflector held low."),
        ("Neon", "Coloured light from signs out of frame, magenta on one side of the face and "
         "cyan on the other, wet ground throwing the colour back up."),
    ],

    "Camera": [
        ("Portrait lens", "Shot on an 85mm lens at f/1.8, the background reduced to soft "
         "shapes, the plane of focus on the near eye."),
        ("Wide", "Shot on a 24mm lens from slightly low, the setting given room around the "
         "subject, the verticals kept straight."),
        ("Macro", "Shot on a 100mm macro lens, the texture readable at the pore, a very "
         "shallow plane of focus falling off within centimetres."),
        ("Medium format", "Shot on medium format at f/4, the detail holding across the frame "
         "and the tonal transitions long and smooth."),
        ("Telephoto", "Shot on a 200mm lens from far back, the background compressed up "
         "against the subject, the perspective flattened."),
        ("Overhead", "Photographed from directly overhead looking straight down, the subject "
         "flat against the surface below."),
        ("Handheld", "Handheld at a slow shutter, a trace of motion left in the edges, the "
         "imperfection kept rather than corrected."),
    ],

    "Setting": [
        ("Beach", "On a wide sand beach with the sea behind and wet sand holding the "
         "reflection, warm backlight low over the water."),
        ("Forest", "On a narrow forest path with dappled light coming through the canopy, "
         "bright patches moving across the ground."),
        ("Office", "In an open plan office with glass partitions and plants, daylight from "
         "one wall and the rest of the floor falling into shade."),
        ("City street", "On a wide city street at the blue hour, shopfronts lit behind, "
         "traffic reduced to streaks by the exposure."),
        ("Studio", "In a bare photographic studio, a seamless paper backdrop curving up "
         "behind, the stand and the floor left visible at the edges."),
        ("Kitchen", "In a bright modern kitchen with white cabinets and a marble counter, "
         "daylight coming in from the left and bouncing off the stone."),
        ("Interior", "In a warm domestic interior with worn furniture and bookshelves, one "
         "lamp doing most of the work."),
        ("Mountain", "On an exposed ridge above the treeline, cold thin light, the valley "
         "falling away out of focus behind."),
    ],

    "Clothing": [
        ("Tailored", "Wearing a sharply tailored charcoal suit with a white shirt open at "
         "the collar, the cloth holding its shape."),
        ("Casual", "Wearing a soft cotton t-shirt and well-worn jeans, the fabric creased "
         "where it has been sat in."),
        ("Overcoat", "Wearing a camel wool overcoat over a charcoal roll-neck, the coat open "
         "and moving slightly."),
        ("Leather", "Wearing a black leather biker jacket over a plain t-shirt, the leather "
         "creased at the elbows and catching the light along the seams."),
        ("Summer", "Wearing a light cotton summer dress that lifts in the breeze, the weave "
         "translucent where the sun passes through."),
        ("Outdoor", "Wearing a weatherproof shell jacket with the hood down, the fabric matte "
         "and slightly scuffed."),
        ("Knitwear", "Wearing a heavy hand-knitted sweater, the cable pattern catching the "
         "raking light."),
        ("Workwear", "Wearing practical workwear with the sleeves rolled, the fabric showing "
         "honest wear at the cuffs and the knees."),
    ],

    "Style and grade": [
        ("35mm film", "Shot on 35mm colour negative film, fine grain, the blacks lifted "
         "slightly and the highlights rolling off rather than clipping."),
        ("Cinematic", "Cinematic colour grading in a wide aspect, the light motivated by "
         "what is visible in the scene, teal holding the shadows."),
        ("Documentary", "A documentary photograph, nothing staged, available light only, the "
         "framing accepting whatever is in it."),
        ("Fashion", "A fashion editorial frame, hard light and saturated colour, the pose "
         "held and deliberate, styled to the last detail."),
        ("Muted", "A muted desaturated grade, the colours pulled back towards grey, contrast "
         "low and even."),
        ("Cross process", "A cross-processed look, cyan shadows and yellow highlights, the "
         "contrast pushed hard."),
        ("Product", "Clean product photography, even light from a large source, the object "
         "centred and sharp from the nearest edge to the furthest."),
        ("Flat illustration", "A flat vector illustration built from simple shapes in a "
         "limited palette, no gradients, crisp edges."),
    ],

    "Lettering": [
        ("Poster", "A screen-printed travel poster with the word \"ATACAMA\" across the top "
         "in tall condensed sans-serif capitals, flat spot colours and visible paper grain."),
        ("Shop sign", "A hand-painted shop sign reading \"OPEN DAILY\" in gold leaf serif "
         "capitals on dark green glass, a fine drop shadow behind each letter."),
        ("Packaging", "A coffee bag with \"SINGLE ORIGIN\" printed in small spaced capitals "
         "above the roast date, matte kraft paper, one ink colour."),
        ("Chalkboard", "A chalkboard outside a cafe reading \"SOUP OF THE DAY\" in looping "
         "handwritten chalk, the letters smudged where a hand has passed."),
        ("Book cover", "A hardback book cover with the title \"THE LONG DRY\" foil-stamped in "
         "the upper third, generous margins, one illustration below."),
        ("Neon sign", "A neon sign spelling \"LATE BAR\" in warm pink tubing against a wet "
         "brick wall, the glow bleeding out into the surrounding dark."),
    ],

    "Edits (what to put there)": [
        ("Jacket", "A dark green leather biker jacket, zipped all the way up, nothing else "
         "visible underneath it, the same lighting and the same shadows as the rest of the "
         "photograph."),
        ("Shirt", "A crisp white cotton shirt buttoned to the collar, the fabric catching the "
         "light the same way the original garment did."),
        ("Hair", "Dark hair cut short at the sides and left longer on top, falling naturally, "
         "the same hairline and the same light across it."),
        ("Clean background", "A plain seamless studio backdrop in warm mid grey, evenly lit, "
         "the edge light on the subject left exactly as it is."),
        ("Landscape behind", "An open field under a wide overcast sky, thrown well out of "
         "focus, matching the direction of the light already on the subject."),
        ("Sky", "A clear evening sky graduating from warm near the horizon to deep blue "
         "overhead, a few high thin clouds catching the last of the sun."),
        ("Glasses", "Round tortoiseshell eyeglasses sitting naturally on the bridge of the "
         "nose, the frames throwing a small shadow on the cheek."),
        ("A prop", "A ceramic coffee cup held in both hands at chest height, steam rising "
         "from it and catching the light."),
    ],

    "What to select": [
        ("Clothing", "the jacket"),
        ("Top garment", "the sweater"),
        ("Hair", "the hair"),
        ("Face", "the face"),
        ("Background", "the background"),
        ("Whole person", "the person"),
        ("Hands", "the hands"),
        ("Sky", "the sky"),
    ],
}


def catalogo() -> list[dict]:
    """Flat structure for the interface."""
    return [{"categoria": c,
             "items": [{"etiqueta": e, "texto": t} for e, t in items]}
            for c, items in BIBLIOTECA.items()]

# use case -> its own starting points. The first thing seen when the library is
# opened from that path, because an empty field says nothing about what goes in it.
BASES: dict[str, list[tuple[str, str]]] = {
    "blank": [
        ("Product", "A weathered brass diving helmet on an oak workbench, studio product "
         "photograph, scratched patina and green verdigris in the seams, a single softbox "
         "from the left falling off into near black, shot on a 100mm macro lens."),
        ("Landscape", "A basalt shoreline under a low grey sky, black sand and a long "
         "exposure smoothing the surf into mist, the horizon kept level and high in the "
         "frame, shot on a 24mm lens at f/11."),
        ("Interior", "A small second-hand bookshop at closing time, warm lamps against the "
         "blue outside the window, dust in the air, shelves receding out of focus, shot on a "
         "35mm lens at f/2."),
        ("Food", "A bowl of ramen shot from just above the rim, steam caught against a dark "
         "background, the egg cut open, one hard source raking from behind to make the broth "
         "shine, 100mm macro."),
        ("Animal", "A red fox standing still in wet bracken at first light, ears forward, "
         "breath visible, the background compressed to soft colour on a 300mm lens."),
        ("Illustration", "A flat vector illustration of a lighthouse on a cliff, four flat "
         "colours and no gradients, crisp geometric shapes, generous negative space."),
        ("Architecture", "A brutalist concrete stairwell photographed from below, hard "
         "midday light cutting a diagonal across the wall, straight verticals, 24mm."),
        ("Still life", "Three pears on a linen cloth beside a chipped enamel jug, north "
         "light from one side, the palette held to ochre and grey, medium format at f/8."),
    ],
    "sign": [
        ("Poster", 'A screen-printed travel poster. The word "ATACAMA" runs across the top '
         'in tall condensed sans-serif capitals, with "ALTIPLANO \u00b7 CHILE" in small spaced '
         "letters underneath. A lone volcano over a white salt flat below the type. Flat "
         "spot colours in ochre, rust and deep teal, visible paper grain."),
        ("Shop sign", 'A hand-painted shop window reading "ROSEWOOD & SONS" in gold leaf '
         "serif capitals on dark green glass, a fine drop shadow behind each letter, the "
         "street reflected faintly in the pane."),
        ("Packaging", 'A matte kraft coffee bag with "SINGLE ORIGIN" printed in small spaced '
         'capitals above "ETHIOPIA \u00b7 YIRGACHEFFE", one ink colour, photographed square on '
         "under even studio light."),
        ("Book cover", 'A hardback book cover with the title "THE LONG DRY" foil-stamped in '
         "the upper third, generous margins, a single woodcut illustration of a dry riverbed "
         "below it, cloth texture visible."),
        ("Neon", 'A neon sign spelling "LATE BAR" in warm pink tubing mounted on a wet brick '
         "wall at night, the glow bleeding into the surrounding dark and reflecting in the "
         "puddles below."),
        ("Chalkboard", 'A chalkboard outside a cafe reading "SOUP OF THE DAY" in looping '
         "handwritten chalk, the letters smudged where a hand has passed, morning light "
         "across it."),
    ],
    "upscale": [
        ("Photograph", "Enhance this photograph to high resolution while preserving the "
         "original composition, lighting and atmosphere. Recover the real texture of skin, "
         "fabric and hair. Keep the grain structure and the colour exactly as they are."),
        ("Illustration", "Enhance this illustration to high resolution while preserving the "
         "original composition and palette. Keep the line weight crisp and the colour flat; "
         "add no photographic texture."),
        ("Detail pass", "Enhance this image to high resolution while preserving the original "
         "composition, lighting and atmosphere. Resolve the fine detail that is currently "
         "soft: individual hairs, the weave of the cloth, the edges of small objects."),
        ("Keep the grain", "Enhance this image to high resolution while preserving the "
         "original composition, lighting and atmosphere, including the film grain and the "
         "existing softness. Do not make it look digital."),
    ],
    "replace": [
        ("Garment", "A dark green leather biker jacket, zipped all the way up, nothing else "
         "visible underneath it, the same lighting and the same shadows as the rest of the "
         "photograph."),
        ("Background", "A plain seamless studio backdrop in warm mid grey, evenly lit, the "
         "edge light on the subject left exactly as it is."),
        ("Sky", "A clear evening sky graduating from warm near the horizon to deep blue "
         "overhead, a few high thin clouds catching the last of the sun."),
        ("Object", "A ceramic coffee cup held in both hands at chest height, steam rising "
         "from it, lit the same way as everything around it."),
    ],
}

# caso de uso -> que categorias tienen sentido en ese camino
RELEVANTES: dict[str, tuple[str, ...]] = {
    "blank": ("Portrait", "Full body", "Lighting", "Camera", "Setting", "Style and grade",
              "Lettering"),
    "sign": ("Lettering", "Style and grade", "Camera"),
    "portrait": ("Portrait", "Lighting", "Camera", "Setting", "Clothing", "Style and grade"),
    "scene": ("Lighting", "Camera", "Style and grade"),
    "pose": ("Full body", "Lighting", "Camera", "Setting", "Clothing", "Style and grade"),
    "cutout": ("Full body", "Lighting", "Clothing"),
    "replace": ("Edits (what to put there)", "What to select", "Lighting", "Clothing"),
    "upscale": (),
    "look": (),
    "free": tuple(BIBLIOTECA),
}


def catalogo_de(caso: str | None = None) -> list[dict]:
    """The library filtered to one use case, with its own starting points first.

    An unknown case gets everything: a wrong guess should widen the list, not
    empty it.
    """
    fuera = []
    if caso and caso in BASES:
        fuera.append({"categoria": "Starting points",
                      "items": [{"etiqueta": e, "texto": t} for e, t in BASES[caso]]})
    permitidas = RELEVANTES.get(caso or "", tuple(BIBLIOTECA)) if caso else tuple(BIBLIOTECA)
    for c, items in BIBLIOTECA.items():
        if c in permitidas:
            fuera.append({"categoria": c,
                          "items": [{"etiqueta": e, "texto": t} for e, t in items]})
    return fuera
