"""MCP server for QwenStudio.

Lets any MCP client (Claude, Codex, an editor, a script) drive the app. It is a
thin layer over the local HTTP server, deliberately: the model stays loaded in
one process and the UI and the agent share it, instead of each paying 35 s of
load and 20 GB of VRAM.

Start the app first, then point the client here:

    {"mcpServers": {"qwenstudio": {
        "command": "D:\\\\QwenStudio\\\\.venv\\\\Scripts\\\\python.exe",
        "args": ["-m", "qwenstudio.mcp_server"],
        "cwd": "D:\\\\QwenStudio"}}}

Images are passed as paths on this machine, not base64: an agent that just
produced a file should hand over the path, and inlining megabytes through the
tool protocol helps nobody. Results come back as paths too.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVIDOR = os.environ.get("QWENSTUDIO_URL", "http://127.0.0.1:7860")
SALIDAS = os.path.join(APP, "salidas")

# mcp 2.x renombro FastMCP a MCPServer; se acepta cualquiera de las dos para
# no atarse a una version concreta del SDK.
try:
    from mcp.server.mcpserver import MCPServer as _Servidor   # mcp >= 2
except ImportError:                                            # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Servidor        # mcp 1.x

mcp = _Servidor("qwenstudio")


# ------------------------------------------------------------------ helpers

def _data_url(ruta: str) -> str:
    ruta = os.path.abspath(os.path.expanduser(ruta))
    if not os.path.exists(ruta):
        raise ValueError(f"file not found: {ruta}")
    tipo = mimetypes.guess_type(ruta)[0] or "image/png"
    if not tipo.startswith("image/"):
        raise ValueError(f"not an image: {ruta}")
    with open(ruta, "rb") as f:
        return f"data:{tipo};base64," + base64.b64encode(f.read()).decode()


def _pedir(ruta: str, payload: dict | None = None, timeout: int = 3600):
    url = f"{SERVIDOR}{ruta}"
    try:
        if payload is None:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read())
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"QwenStudio is not answering at {SERVIDOR} ({e}). "
            f"Start it with EJECUTAR.bat and try again.") from e


def _rutas(resp: dict) -> dict:
    """Turn the app's /salidas/... URLs into absolute paths the client can open."""
    if "imagenes" in resp:
        for im in resp["imagenes"]:
            im["path"] = os.path.join(SALIDAS, os.path.basename(im["archivo"]))
    if "preview" in resp:
        resp["preview_path"] = os.path.join(SALIDAS, os.path.basename(resp["preview"]))
    return resp


# ------------------------------------------------------------------ tools

@mcp.tool()
def status() -> dict:
    """Hardware profile, whether the weights are downloaded and whether the model is loaded.

    Worth calling first: generation is refused until the weights are on disk,
    and the first call after start pays ~35 s of model loading.
    """
    e = _pedir("/api/estado")
    return {"profile": e["perfil"], "weights_ready": e["pesos_listos"],
            "engine": e["motor"], "download": e["descarga"],
            "warnings": e.get("avisos_perfil", [])}


@mcp.tool()
def list_poses() -> list:
    """The pose library: ids usable as `pose_id`, with their framing."""
    return [{"id": p["id"], "label": p["label"], "framing": p["framing"],
             "tags": p.get("tags", [])} for p in _pedir("/api/poses")]


@mcp.tool()
def list_loras() -> list:
    """LoRA files available in the app's loras/ folder."""
    return _pedir("/api/loras")


@mcp.tool()
def generate(prompt: str,
             person_images: list[str] | None = None,
             scene_image: str | None = None,
             pose_id: str | None = None,
             pose_image: str | None = None,
             ratio: str = "auto",
             megapixels: float = 1.0,
             steps: int = 25,
             seed: int = 0,
             variants: int = 1,
             transparent: bool = False,
             lora: str | None = None,
             lora_strength: float = 1.0) -> dict:
    """Generate an image, optionally preserving a person's identity.

    person_images: paths to photos of the subject. With `scene_image`, pass
        exactly ONE: several are read as several different people and end up as
        several people in the frame.
    scene_image: a photo supplying setting, wardrobe, framing and lighting.
    pose_id: an id from `list_poses`. pose_image: a photo to derive a skeleton
        from instead.
    ratio: "auto" (from the reference) or 1:1, 4:3, 3:4, 3:2, 2:3, 16:9, 9:16.
    transparent: output a PNG with a real alpha channel.

    The reference order that makes identity transfer work is applied for you.
    Returns the generated file paths.
    """
    payload = {
        "prompt": prompt,
        "personas": [_data_url(p) for p in (person_images or [])],
        "escena": _data_url(scene_image) if scene_image else None,
        "pose_lib": pose_id,
        "ratio": ratio, "megapixeles": megapixels, "steps": steps,
        "seed": seed, "variantes": variants, "transparencia": transparent,
        "lora": lora, "fuerza_lora": lora_strength,
    }
    if pose_image and not pose_id:
        r = _pedir("/api/pose", {"imagen": _data_url(pose_image)})
        if r.get("error"):
            raise RuntimeError(r["error"])
        payload["pose_url"] = r["esqueleto"]

    resp = _pedir("/api/generar", payload)
    if resp.get("error"):
        raise RuntimeError(resp["error"])
    return _rutas(resp)


@mcp.tool()
def generate_batch(prompts: list[str],
                   person_images: list[str] | None = None,
                   scene_image: str | None = None,
                   pose_id: str | None = None,
                   ratio: str = "auto",
                   megapixels: float = 1.0,
                   steps: int = 25,
                   seed: int = 0,
                   transparent: bool = False,
                   lora: str | None = None,
                   lora_strength: float = 1.0) -> dict:
    """Run a list of prompts in one go, sharing the same references.

    Made for exactly what a script wants to do: write N variations of a prompt
    and get N images. The image model stays mounted for the whole run instead of
    being cycled per call, so a batch of ten costs ten generations rather than
    ten generations plus ten reloads.

    Up to 64 prompts. The seed advances by one per prompt, so a rerun with the
    same seed reproduces the set.
    """
    resp = _pedir("/api/lote", {
        "prompts": prompts,
        "personas": [_data_url(p) for p in (person_images or [])],
        "escena": _data_url(scene_image) if scene_image else None,
        "pose_lib": pose_id, "ratio": ratio, "megapixeles": megapixels,
        "steps": steps, "seed": seed, "transparencia": transparent,
        "lora": lora, "fuerza_lora": lora_strength,
    }, timeout=7200)
    if resp.get("error"):
        raise RuntimeError(resp["error"])
    return _rutas(resp)


@mcp.tool()
def unmount(keep: str | None = None) -> dict:
    """Free the GPU by unmounting the heavy models.

    keep: "imagen", "vision" or "segmenta" to leave one mounted. Normally the
    app handles this on its own; this is for when you want the card back for
    something else.
    """
    return _pedir("/api/desmontar", {"excepto": keep})


@mcp.tool()
def prompt_library() -> list:
    """Example prompts by category, written for how this model reads English."""
    return _pedir("/api/prompts")


@mcp.tool()
def describe_image(image: str, task: str = "prompt", question: str = "") -> dict:
    """Look at an image with Qwen3-VL and write about it.

    task: "prompt" (a prompt that would recreate it), "describe", "caption",
    "edit" (three concrete edit suggestions), "select" (regions worth editing),
    or "free" with your own `question`.
    """
    resp = _pedir("/api/describir", {"imagen": _data_url(image), "tarea": task,
                                     "extra": question}, timeout=900)
    if resp.get("error"):
        raise RuntimeError(resp["error"])
    return resp


@mcp.tool()
def preview_selection(image: str, select: str = "", mask: str | None = None,
                      grow: int = 8, threshold: float = 0.5) -> dict:
    """Return a preview of the region an edit would touch, tinted.

    select: what to pick out, in words ("the jacket", "the background").
    mask: instead of words, the path to a black and white image where white is
        the region to edit. It is used as given, without growing, and the
        segmenter is never loaded.

    Cheap compared to generating, so it is the right way to check that the
    selection catches what you meant before spending a minute on an edit.
    """
    resp = _pedir("/api/mascara", {"imagen": _data_url(image), "frase": select,
                                   "mascara": _data_url(mask) if mask else None,
                                   "crecer": grow, "umbral": threshold})
    if resp.get("error"):
        raise RuntimeError(resp["error"])
    return _rutas(resp)


@mcp.tool()
def inpaint(image: str, prompt: str, select: str = "", mask: str | None = None,
            reference_images: list[str] | None = None,
            megapixels: float = 1.0, steps: int = 25, seed: int = 0,
            variants: int = 1, grow: int = 8, feather: int = 12,
            threshold: float = 0.5, padding: float = 0.35,
            lora: str | None = None, lora_strength: float = 1.0) -> dict:
    """Replace part of an image, described in words.

    prompt: what should be there instead.
    select: what to replace, in words ("the jacket", "the hair", "the background").
    mask: instead of words, the path to a black and white image the same size as
        `image`, where white marks what to replace. Used exactly as given.
    reference_images: optional photos of what to put there.

    Give one of `select` or `mask`. A mask wins if both arrive.

    The region is cropped around the mask, regenerated at full resolution and
    stitched back through a feathered edge, so detail lands where the edit is
    instead of being spread over the whole frame.
    """
    resp = _pedir("/api/inpaint", {
        "imagen": _data_url(image), "frase": select, "prompt": prompt,
        "mascara": _data_url(mask) if mask else None,
        "referencias": [_data_url(p) for p in (reference_images or [])],
        "megapixeles": megapixels, "steps": steps, "seed": seed,
        "variantes": variants, "crecer": grow, "difuminado": feather,
        "umbral": threshold, "padding": padding,
        "lora": lora, "fuerza_lora": lora_strength,
    })
    if resp.get("error"):
        raise RuntimeError(resp["error"])
    return _rutas(resp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
