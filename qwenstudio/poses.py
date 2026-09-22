"""Pose library.

Skeletons ship pre-extracted, so the app needs no pose detector at runtime. A
detector is only required to turn a *user's* photo into a skeleton, and that
path degrades gracefully when one is not installed.

Layout:
    poses/
      index.json          catalogue: id, label, framing, tags
      <id>.png            OpenPose skeleton, ready to feed as a reference
      thumbs/<id>.jpg     small preview for the picker
"""

from __future__ import annotations

import json
import os

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "poses")
INDEX = os.path.join(DIR, "index.json")


def catalogo() -> list[dict]:
    """The catalogue, filtered to entries whose skeleton actually exists."""
    if not os.path.exists(INDEX):
        return []
    try:
        with open(INDEX, encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return []
    out = []
    for it in items:
        if os.path.exists(os.path.join(DIR, it["id"] + ".png")):
            it = dict(it)
            it["skeleton"] = f"/poses/{it['id']}.png"
            it["thumb"] = (f"/poses/thumbs/{it['id']}.jpg"
                           if os.path.exists(os.path.join(DIR, "thumbs", it["id"] + ".jpg"))
                           else it["skeleton"])
            out.append(it)
    return out


def ruta(pose_id: str) -> str | None:
    """Absolute path of a library skeleton, or None if the id is unknown.

    The id is sanitised: it is used to build a filesystem path from a request.
    """
    pose_id = os.path.basename(str(pose_id))
    p = os.path.join(DIR, pose_id + ".png")
    return p if os.path.exists(p) else None
