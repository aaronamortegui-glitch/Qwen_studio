"""Build the pose library from source photographs.

Run with a Python that has `easy-dwpose` installed (the ai-toolkit venv on this
machine). Skeletons are extracted once here and ship with the app, so
QwenStudio itself never needs a pose detector at runtime.

    <venv-with-dwpose>\\python.exe herramientas\\build_pose_library.py <source-dir>

Any photographs work as sources. The library's own images were generated with
Qwen-Image 2.1; a folder of real photos does the same job.

Metadata comes from `poses/_meta_gen.json` when the generator wrote one,
otherwise from the filename. A pose whose skeleton comes back empty is skipped:
that is what happens with a tight face close-up, where there is no body for the
detector to find.
"""

from __future__ import annotations

import json
import os
import re
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSES = os.path.join(APP, "poses")
THUMBS = os.path.join(POSES, "thumbs")

ETIQUETAS = {
    "closeup": "Close-up", "half": "Half body", "full": "Full body",
    "portrait": "Portrait", "casual": "Casual", "business": "Business",
    "fashion": "Fashion", "seated": "Seated", "sports": "Sports",
}


def bonito(pose_id: str) -> str:
    limpio = re.sub(r"^(cu|hb|fb|st|sp)_", "", pose_id)
    return limpio.replace("_", " ").capitalize()


def main() -> None:
    src_dir = sys.argv[1] if len(sys.argv) > 1 else None
    if not src_dir or not os.path.isdir(src_dir):
        raise SystemExit(f"usage: {os.path.basename(__file__)} <source-dir>")

    from PIL import Image
    import torch
    from easy_dwpose import DWposeDetector

    os.makedirs(THUMBS, exist_ok=True)
    meta_path = os.path.join(POSES, "_meta_gen.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}

    det = DWposeDetector(device="cuda" if torch.cuda.is_available() else "cpu")

    pat = re.compile(r"POSE2?_?(?:LIB_)?(.+?)_\d+_\.png$")
    fuentes: dict[str, str] = {}
    for f in sorted(os.listdir(src_dir)):
        m = re.match(r"POSE2_(.+?)_\d+_\.png$", f) or re.match(r"POSELIB_(.+?)_\d+_\.png$", f)
        if m:
            fuentes[m.group(1)] = os.path.join(src_dir, f)

    index, fallos, ignorados = [], [], []
    for pose_id, src in fuentes.items():
        # the catalogue is defined by the metadata, not by what is in the
        # conviven salidas de pruebas y de tandas anteriores, y colarlas produce
        # duplicados con encuadre equivocado.
        if meta and pose_id not in meta:
            ignorados.append(pose_id)
            continue
        info = meta.get(pose_id, {})
        encuadre = info.get("encuadre", "half")
        grupo = info.get("grupo", "casual")

        img = Image.open(src).convert("RGB")
        try:
            skel = det(img, output_type="pil", include_hands=True, include_face=True)
        except Exception as e:
            fallos.append((pose_id, str(e)[:70]))
            continue

        # an almost black skeleton means the detector found nothing usable
        if skel.convert("L").getextrema()[1] < 40:
            fallos.append((pose_id, "no body detected"))
            continue

        skel.save(os.path.join(POSES, pose_id + ".png"))
        th = img.copy()
        th.thumbnail((320, 320), Image.LANCZOS)      # keeps aspect ratio
        th.save(os.path.join(THUMBS, pose_id + ".jpg"), quality=86)
        index.append({"id": pose_id, "label": bonito(pose_id),
                      "framing": encuadre, "group": grupo,
                      "framing_label": ETIQUETAS.get(encuadre, encuadre),
                      "group_label": ETIQUETAS.get(grupo, grupo)})
        print(f"  ok    {pose_id:<16} {encuadre:<8} {grupo}")

    orden = {"closeup": 0, "half": 1, "full": 2}
    index.sort(key=lambda x: (orden.get(x["framing"], 9), x["group"], x["label"]))
    with open(os.path.join(POSES, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\n  {len(index)} poses -> {POSES}")
    for pid, why in fallos:
        print(f"  SKIPPED {pid}: {why}")


if __name__ == "__main__":
    main()
