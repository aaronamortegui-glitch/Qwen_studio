"""Servidor local de QwenStudio.

Sirve la interfaz en http://127.0.0.1:7860 y ejecuta la inferencia en proceso,
sin ComfyUI. Nada sale de la maquina.
"""

from __future__ import annotations

import base64
import io
import json
import math
import mimetypes
import os
import re
import subprocess
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# El asignador de CUDA fragmenta cuando se le piden formas distintas una
# detras de otra, que es exactamente lo que hace esta app: un texto a imagen,
# luego un retrato con referencia, luego un 2K. Con segmentos expandibles el
# bloque reservado se estira en vez de dejar huecos. Va antes de que nada
# reserve memoria, y no cuesta nada cuando no hay CUDA.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, APP)

from qwenstudio import motor as M            # noqa: E402
from qwenstudio.interfaz import HTML         # noqa: E402
from qwenstudio import poses as P            # noqa: E402
from qwenstudio import segmentacion as SEG    # noqa: E402
from qwenstudio import efectos as EF          # noqa: E402
from qwenstudio import inpaint as IN          # noqa: E402
from qwenstudio import vision as VIS          # noqa: E402
from qwenstudio import prompts as PR          # noqa: E402
from qwenstudio.recursos import registro     # noqa: E402
from qwenstudio import resumen as RES         # noqa: E402

PORT = 7860
CONFIG = os.path.join(APP, "config.json")
SALIDAS = os.path.join(APP, "salidas")
LORAS = os.path.join(APP, "loras")
AJUSTES = os.path.join(APP, "ajustes.json")
EJEMPLOS = os.path.join(APP, "ejemplos")

# Ajustes que el usuario puede cambiar en caliente, separados de config.json
# (que lo escribe el instalador y describe el hardware, no las preferencias).
AJUSTES_DEF = {
    "describir_escena": True,     # describir la escena con el VLM antes de generar
    "resumen": True,              # generar la hoja de contacto en cada corrida
    # 16 steps. Swept by eye at 1 MP on one fixed seed, on a subject built to
    # break first -- a watch movement, knurling, a hand: 8 steps is mush, 12
    # still has a soft movement, 16 resolves its screws and jewels, and 20 and
    # 25 add nothing worth 5 and 11 more seconds (18 / 21 / 27 / 33 / 38 s).
    # So the knee is between 12 and 16, and 12 is a draft rather than a result.
    "steps": 16,
    # 1 MP: el tamano con el que se trabaja. 2K ya funciona y esta a un clic;
    # poner 0 aqui significa "lo que aguante la tarjeta detectada".
    "megapixeles": 1,
    # Sampler and scheduler, the FlowMatchEuler fields ComfyUI puts in its
    # dropdowns. "base" is what the weights shipped with. See motor.MUESTREO.
    "muestreo": "base",
    # The turbo adapter, off. It is a third faster on everything measured and
    # it keeps a face, but with the two sheets side by side the base model was
    # the better picture, so speed is something you reach for while iterating
    # rather than what you get without asking.
    # Donde viven los pesos entre llamadas. "" deja mandar al perfil.
    # Medido el 2026-09-23 a 1 MP en caliente: con offload de modelo 26 s, sin
    # offload 19 s -- un 27% -- por 1.6 GB mas residentes. No sale gratis: sin
    # offload, 2.25 MP con una referencia ya no cabe bajo el techo y devuelve
    # un error. Velocidad contra tamano, y el que conserva el tamano manda.
    "offload": "",
    "turbo": False,
    # Pasos cuando el turbo esta puesto. Su autor recomienda 4 y su demo acepta
    # de 3 a 8. Medido aqui el 2026-09-22: a 4 devuelve manos fantasma, con
    # nuestro shift_terminal y con el suyo, y a 8 sale limpio y sigue siendo un
    # tercio mas rapido. Su propia ficha lo admite -- "multi-reference
    # composition, face swaps and identity-document edits can produce
    # duplicated or ghosted figures". Se deja en 4 porque es lo que el modelo
    # pide y el interruptor existe para ir rapido; 8 esta a un numero.
    "turbo_pasos": 4,
    # Detail pass, on. Above 1 the pipeline runs a second forward pass against
    # the negative prompt, which costs ~80% more time and buys detail that is
    # not there otherwise: a watch movement went from a gold blur to resolved
    # jewels and screws. It is not free -- at 16 steps a portrait grew a second
    # person the prompt never asked for, though at 20 it did not -- so the
    # figure is reachable in one click.
    #
    # 3 without the line below would be theatre: with nothing to push against
    # the second pass never runs, and the result is byte-identical in identical
    # time. The default negative is the one measured with, and it is editable
    # in the box under the prompt.
    "cfg": 3,
    "negativo": "blurry, deformed hands, extra fingers, watermark, text artefacts",
    "vlm_bits": 4,                # 4 u 8; 8 describe algo mejor y ocupa ~13 GB
    "mantener_montado": False,    # no desmontar entre bloques (para lotes)
    # hdr por defecto: medido el 2026-09-22 con la misma semilla, +19% de
    # saturacion y +27% de energia de gradiente sin tocar contraste ni luz
    # media. Si el archivo no esta, usar_vae cae al de serie sin quejarse.
    "vae": "hdr",                 # hdr | stock
    # entre imagenes de un lote, esperar a que la tarjeta baje de aqui. 0 lo
    # desactiva. No protege de nada roto: evita que un lote largo se pase la
    # noche estrangulado y tarde el doble
    "limite_c": 80,
    # afinar con SAM 2 la mascara que sale del texto. Medido: CLIPSeg solo se
    # comia el pelo que cae sobre la prenda; con SAM 2 el borde la sigue
    "afinar_mascara": True,
}


def _tope(refs: int) -> int:
    """The profile's resolution ceiling. It depends on how many references.

    Measured on 2026-09-23 on a 24 GB card. No reference, 2K: 7.5 GB. One
    reference, 2K: 18.2 GB rescaling and 19.2 generating a portrait -- already
    at the wall. Two references, 2K: the machine blue-screened, HYPERVISOR_ERROR
    forty seconds in, with no thermal or WHEA event anywhere near it.

    So two or more references drop to 1024, which is the last size actually
    measured with a reference in front of the model (9.2 GB). A formula was
    tried here first -- area divided by the count, side falling as its square
    root -- and thrown out: it produced 1440 for two references, a number
    nobody has ever run. Guessing between a size that works and a size that
    takes the kernel down is not a guess worth making. Raise this when there is
    a measurement, not before.
    """
    base = int(cfg.get("res_max", 1024))
    if refs <= 0:
        return base
    tope = int(cfg.get("res_max_ref", base))
    if refs > 1:
        return min(tope, int(cfg.get("res_max_multi", 1024)))
    return tope


def leer_ajustes() -> dict:
    a = dict(AJUSTES_DEF)
    # el techo del perfil, resuelto aqui para no repetirlo en cada llamada
    if not a.get("megapixeles"):
        tope = int(cfg.get("res_max", 1024))
        a["megapixeles"] = 4 if tope >= 2048 else (2 if tope >= 1536 else 1)
    try:
        with open(AJUSTES, encoding="utf-8-sig") as f:
            a.update({k: v for k, v in json.load(f).items() if k in AJUSTES_DEF})
    except Exception:
        pass
    return a


def guardar_ajustes(nuevos: dict) -> dict:
    a = leer_ajustes()
    a.update({k: v for k, v in nuevos.items() if k in AJUSTES_DEF})
    with open(AJUSTES, "w", encoding="utf-8") as f:
        json.dump(a, f, indent=2)
    return a
ENTRADAS = os.path.join(APP, "entradas")
DWPOSE_PY = r"D:\AIToolkit\AI-Toolkit\venv\Scripts\python.exe"   # opcional

cfg = json.load(open(CONFIG, encoding="utf-8-sig"))
estado_descarga = M.Descarga()
motor = M.Motor(cfg)
_lock = threading.Lock()


# ------------------------------------------------------------------ recursos

registro.registrar("imagen", montado=lambda: motor.listo,
                   desmontar=motor.liberar, vram_gb=21.3, etiqueta="Qwen-Image 2.1")
registro.registrar("vision", montado=VIS.disponible,
                   desmontar=VIS.descargar_de_memoria, vram_gb=7.1, etiqueta="Qwen3-VL")
registro.registrar("segmenta", montado=SEG.disponible,
                   desmontar=lambda: (SEG.descargar_de_memoria(), SEG.soltar_afinador()), vram_gb=0.9, etiqueta="CLIPSeg + SAM 2")


def usar(quien: str) -> list[str]:
    """Free the VRAM the next block needs. See qwenstudio/recursos.py.

    `mantener_montado` skips it: in a batch the models would otherwise cycle in
    and out between images, which costs more than the generations themselves.
    """
    if leer_ajustes().get("mantener_montado"):
        return []
    return registro.usar(quien)


# ------------------------------------------------------------------ util

def _mensaje(e: Exception) -> str:
    """What to tell someone when it failed, in their terms rather than torch's.

    Running out of VRAM is the one failure with an obvious next move, and the
    raw exception buries it under a page of allocator arithmetic. The ceiling
    that produced it is deliberate: the card has more memory than this, and the
    last few gigabytes are left alone because reaching for them took this
    machine down twice.
    """
    nombre = type(e).__name__
    if "OutOfMemory" in nombre or "out of memory" in str(e).lower():
        techo = cfg.get("vram_limite_gb")
        return ("That was too large for this card. Ask for a smaller size, or "
                "remove one of the reference images: each one costs memory on "
                "top of the output."
                + (f" The ceiling is {techo} GB of {cfg.get('vram_gb')}, left "
                   f"deliberately below the total." if techo else ""))
    return f"{nombre}: {e}"


def _cargar_motor() -> str:
    """Make sure the model is up. Returns "" or what went wrong.

    `motor.cargar()` returns at once when another thread is already loading, so
    a second request arriving during the first load used to be told "could not
    load the model" -- which was false, and which anyone gets by pressing
    Generate twice while the weights come up. Waiting is the honest answer.
    """
    usar("imagen")
    if motor.listo:
        return ""
    motor.cargar()
    limite = time.time() + 300
    while motor.cargando and time.time() < limite:
        time.sleep(0.4)
    if motor.listo:
        return ""
    return motor.error or "could not load the model"


def _turbo(b: dict) -> bool:
    """Whether the engine adapter runs for this request.

    The request wins over the setting so a draft can be fast without touching
    the panel, and a missing file means off rather than an error: the adapter
    is not part of the download.
    """
    quiere = b.get("turbo")
    if quiere is None:
        quiere = leer_ajustes().get("turbo")
    return bool(quiere) and motor.turbo_disponible()


def _cfg(b: dict) -> tuple[float, str]:
    """The detail pass, and whether turbo is allowed to leave it on.

    It is not: the turbo adapter is distilled without classifier-free guidance
    and its own card says to keep it off. Running both would pay twice for a
    second pass the student was never taught to use, which is the worst of the
    two worlds -- slower than turbo and worse than the base model.
    """
    if _turbo(b):
        return 1.0, ""
    a = leer_ajustes()
    cfg_v = float(b.get("cfg", a.get("cfg", 1)))
    neg = str(b.get("negativo", a.get("negativo", "")))
    return cfg_v, neg


def _pasos(b: dict) -> int:
    """The step count this request actually runs at.

    Turbo is not a knob. Measured usable at 8 and returning ghost hands at the
    4 it advertises, so when it is on it brings its own number.
    """
    if _turbo(b):
        return int(leer_ajustes().get("turbo_pasos", motor.TURBO_PASOS))
    return int(b.get("steps", leer_ajustes()["steps"]))


def _img_de_data_url(data_url: str):
    from PIL import Image
    m = re.match(r"data:image/[\w.+-]+;base64,(.*)$", data_url, re.S)
    if not m:
        raise ValueError("that image could not be read")
    return Image.open(io.BytesIO(base64.b64decode(m.group(1)))).convert("RGB")


# Lo que el modelo fue destilado para ver. El Space de Viggle lo dice sin
# rodeos -- "condition images are encoded at 1024-area, as in distillation" --
# y es la razon de que a ellos les quepan tres referencias.
#
# Aqui no se encogia ninguna: una foto de movil de 12 MP entraba entera en la
# secuencia de atencion, doce veces lo que el modelo espera, y el coste no lo
# pagaba la calidad sino la memoria. Lo que se recorta es la REFERENCIA, nunca
# la imagen que se edita: esa define el tamano de salida.
REF_MP = 1.0


def _referencia(data_url: str, tope_mp: float = REF_MP):
    """A conditioning image, capped at the area the model was trained on."""
    from PIL import Image
    img = _img_de_data_url(data_url)
    area = img.width * img.height / 1e6
    if tope_mp and area > tope_mp:
        e = (tope_mp / area) ** 0.5
        img = img.resize((max(32, round(img.width * e / 32) * 32),
                          max(32, round(img.height * e / 32) * 32)), Image.LANCZOS)
    return img


# lo que se guarda dentro del archivo, y el orden en que se lee
CAMPOS_META = ("prompt", "caso", "efecto", "seed", "steps", "tam", "ratio",
               "megapixeles", "vae", "lora", "fuerza_lora", "orden", "modelo",
               "tecnica_leida")


def _guardar(img, prefijo="out", meta: dict | None = None) -> str:
    """Save a result, with its recipe written into the PNG itself.

    tEXt chunks rather than a sidecar file: the recipe then survives being
    moved, copied or sent to someone, and there is no second store to fall out
    of sync with the folder.
    """
    from PIL import PngImagePlugin
    os.makedirs(SALIDAS, exist_ok=True)
    nombre = f"{prefijo}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.png"

    info = PngImagePlugin.PngInfo()
    if meta:
        info.add_text("generator", "QwenStudio / Qwen-Image 2.1")
        # una clave que no este en la lista no llega al archivo, y callarselo
        # cuesta caro: cuesta creer que fallo el paso que la calculo
        sobra = [k for k in meta if k not in CAMPOS_META]
        if sobra:
            print(f"  [meta] no se guarda, falta en CAMPOS_META: {', '.join(sobra)}",
                  flush=True)
        for k in CAMPOS_META:
            v = meta.get(k)
            if v is None or v == "" or v == []:
                continue
            info.add_text(k, ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v))
    img.save(os.path.join(SALIDAS, nombre), pnginfo=info)
    return nombre


def _leer_meta(ruta: str) -> dict:
    """Read the recipe back out of a PNG. Empty dict when there is none."""
    try:
        from PIL import Image as _I
        with _I.open(ruta) as im:
            info = getattr(im, "text", None) or {}
            return {k: v for k, v in info.items() if k != "generator"}
    except Exception:
        return {}


def _esqueleto(img):
    """Deriva un esqueleto OpenPose si hay un python con easy-dwpose a mano."""
    if not os.path.exists(DWPOSE_PY):
        raise RuntimeError("No environment with easy-dwpose installed. Upload a "
                           "skeleton you already have instead of a photograph.")
    os.makedirs(ENTRADAS, exist_ok=True)
    src = os.path.join(ENTRADAS, f"src_{uuid.uuid4().hex[:6]}.png")
    dst = os.path.join(ENTRADAS, f"skel_{uuid.uuid4().hex[:6]}.png")
    img.save(src)
    code = ("import sys;from PIL import Image;import torch;from easy_dwpose import DWposeDetector;"
            "d=DWposeDetector(device='cuda' if torch.cuda.is_available() else 'cpu');"
            "d(Image.open(sys.argv[1]).convert('RGB'),output_type='pil',"
            "include_hands=True,include_face=True).save(sys.argv[2])")
    r = subprocess.run([DWPOSE_PY, "-c", code, src, dst], capture_output=True, text=True, timeout=900)
    if not os.path.exists(dst):
        raise RuntimeError((r.stderr or "")[-300:] or "DWpose produced no skeleton")
    from PIL import Image
    return Image.open(dst).convert("RGB"), os.path.basename(dst)


# ------------------------------------------------------------------ http

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def handle_one_request(self):
        """Un cliente que se va no es un fallo del servidor.

        Cerrar una pestana a mitad de peticion levanta ConnectionReset o
        ConnectionAborted, y socketserver lo imprime con traza completa. Con el
        navegador abierto eso son veinte lineas por recarga, y un error de
        verdad se pierde entre ellas.
        """
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._send(200, HTML, "text/html; charset=utf-8")

        if p == "/api/estado":
            d = estado_descarga
            return self._send(200, {
                "perfil": {k: cfg[k] for k in ("acelerador", "backend", "nivel", "dtype",
                                               "cuantizacion", "offload", "res_max", "res_max_ref",
                                               "res_max_multi", "vram_limite_gb",
                                               "vram_gb", "ram_gb")},
                # el boton de turbo solo aparece si el archivo esta: uno que
                # no hace nada es peor que ninguno
                "turbo_disponible": motor.turbo_disponible(),
                "avisos_perfil": cfg.get("avisos", []),
                "pesos_listos": M.pesos_completos(cfg["ruta_modelos"]),
                "descarga": {"activa": d.activa, "gb": round(d.bytes / 2**30, 2),
                             "total_gb": round(d.total / 2**30, 2) if d.total else 0,
                             "mensaje": d.mensaje, "error": d.error},
                "recursos": registro.estado(),
                "motor": {"listo": motor.listo, "cargando": motor.cargando, "error": motor.error,
                          "aviso_vram": getattr(motor, "aviso_vram", ""),
                          "atencion": getattr(motor, "atencion", "sdpa")},
            })

        if p == "/api/loras":
            try:
                return self._send(200, sorted(
                    f for f in os.listdir(LORAS) if f.endswith(".safetensors")))
            except Exception:
                return self._send(200, [])

        if p == "/api/ajustes":
            return self._send(200, leer_ajustes())

        if p == "/api/prompts":
            # filtrada por camino: ofrecer ropa de invierno a quien esta
            # reescalando una foto solo le hace dudar de para que sirve el campo
            caso = (self.path.split("caso=")[1].split("&")[0]
                    if "caso=" in self.path else None)
            return self._send(200, PR.catalogo_de(caso))

        if p == "/api/poses":
            return self._send(200, P.catalogo())

        if p == "/api/gpu":
            return self._send(200, M.estado_vram())

        if p == "/api/efectos":
            return self._send(200, EF.catalogo(LORAS))

        if p == "/api/progreso":
            return self._send(200, M.progreso())

        if p == "/api/vitrina":
            # Lo que la app hizo en esta maquina, con su receta al lado. Es lo
            # que se ve al abrir por primera vez, cuando todavia no hay nada
            # propio que ensenar.
            f = os.path.join(EJEMPLOS, "vitrina.json")
            if not os.path.exists(f):
                return self._send(200, [])
            with open(f, encoding="utf-8") as fh:
                return self._send(200, json.load(fh))

        if p.startswith("/vitrina/"):
            f = os.path.join(EJEMPLOS, "vitrina", os.path.basename(p[9:]))
            if not os.path.exists(f):
                return self._send(404, b"not found", "text/plain")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), "image/jpeg")

        if p.startswith("/efectos/"):
            f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                             "ejemplos", "efectos", os.path.basename(p[9:]))
            if not os.path.exists(f):
                return self._send(404, b"not found", "text/plain")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), "image/jpeg")

        if p.startswith("/api/receta"):
            # La receta de un archivo suelto. La galeria la trae con cada item,
            # pero un resultado recien hecho todavia no ha pasado por ahi y
            # tiene el mismo derecho a decir como se hizo.
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            nombre = os.path.basename((q.get("archivo") or [""])[0])
            ruta = os.path.join(SALIDAS, nombre)
            if not nombre or not os.path.exists(ruta):
                return self._send(404, {"error": "no such file"})
            return self._send(200, {"nombre": nombre, "meta": _leer_meta(ruta)})

        if p == "/api/galeria":
            return self._send(200, self._galeria())

        if p.startswith("/fuentes/"):
            # Inter Tight viaja dentro del paquete: la app tiene que verse igual
            # sin red, y una fuente que se pide a un CDN no cumple eso.
            f = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "estatico", "fuentes", os.path.basename(p[9:]))
            if not os.path.exists(f):
                return self._send(404, b"not found", "text/plain")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), "font/woff2")

        if p.startswith("/ejemplos/"):
            f = os.path.join(EJEMPLOS, os.path.basename(p[10:]))
            if not os.path.exists(f):
                return self._send(404, b"not found", "text/plain")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), mimetypes.guess_type(f)[0] or "image/jpeg")

        if p.startswith("/poses/"):
            rel = p[7:]
            base = os.path.join(P.DIR, "thumbs") if rel.startswith("thumbs/") else P.DIR
            f = os.path.join(base, os.path.basename(rel))
            if not os.path.exists(f):
                return self._send(404, b"not found", "text/plain")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), mimetypes.guess_type(f)[0] or "image/png")

        if p.startswith("/salidas/"):
            f = os.path.join(SALIDAS, os.path.basename(p[9:]))
            if not os.path.exists(f):
                return self._send(404, b"no existe", "text/plain")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), "image/png")

        if p.startswith("/entradas/"):
            f = os.path.join(ENTRADAS, os.path.basename(p[10:]))
            if not os.path.exists(f):
                return self._send(404, b"no existe", "text/plain")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), mimetypes.guess_type(f)[0] or "image/png")

        return self._send(404, b"no existe", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            b = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error": "the request body was not valid JSON"})
        p = self.path.split("?")[0]

        if p == "/api/descargar":
            if not estado_descarga.activa:
                threading.Thread(target=M.descargar,
                                 args=(cfg["ruta_modelos"], estado_descarga), daemon=True).start()
            return self._send(200, {"ok": True})

        if p == "/api/cargar":
            if not motor.listo and not motor.cargando:
                threading.Thread(target=motor.cargar, daemon=True).start()
            return self._send(200, {"ok": True})

        if p == "/api/pose":
            try:
                img, nombre = _esqueleto(_img_de_data_url(b["imagen"]))
                return self._send(200, {"esqueleto": "/entradas/" + nombre})
            except Exception as e:
                return self._send(200, {"error": str(e)})

        if p == "/api/ajustes":
            return self._send(200, guardar_ajustes(b))

        if p == "/api/borrar":
            return self._send(200, self._borrar(b))

        if p == "/api/cancelar":
            # no toca el lock a proposito: el trabajo esta dentro y hay que
            # poder interrumpirlo desde fuera mientras lo tiene cogido
            M.cancelar()
            return self._send(200, {"ok": True})

        if p == "/api/liberar":
            # soltar los modelos y luego devolver a la tarjeta lo reservado:
            # en ese orden, porque vaciar la cache antes de desmontar no suelta
            # nada que siga referenciado
            soltados = registro.desmontar_todo()
            r = M.vaciar_cache()
            r["desmontados"] = soltados
            return self._send(200, r)

        if p == "/api/desmontar":
            soltados = registro.desmontar_todo(excepto=b.get("excepto"))
            return self._send(200, {"desmontados": soltados})

        if p == "/api/lote":
            try:
                return self._send(200, self._lote(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/describir":
            try:
                img = _img_de_data_url(b["imagen"])
                dev = "cuda" if cfg.get("backend") == "cuda" else "cpu"
                usar("vision")
                VIS.cargar(cfg["ruta_modelos"], dev, bits=int(leer_ajustes()["vlm_bits"]))
                if not VIS.disponible():
                    return self._send(200, {"error": VIS.error() or "could not load the vision model"})
                with _lock:
                    txt = VIS.preguntar(img, b.get("tarea", "prompt"),
                                        extra=b.get("extra", ""),
                                        max_tokens=int(b.get("max_tokens", 320)))
                return self._send(200, {"texto": txt})
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/liberar_vision":
            VIS.descargar_de_memoria()
            return self._send(200, {"ok": True})

        if p == "/api/mejorar_prompt":
            try:
                return self._send(200, self._mejorar(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/editar":
            try:
                return self._send(200, self._editar(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/estilo":
            try:
                return self._send(200, self._estilo(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/efecto":
            try:
                return self._send(200, self._efecto(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/reescalar":
            try:
                return self._send(200, self._reescalar(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/abrir_carpeta":
            return self._send(200, self._abrir_carpeta())

        if p == "/api/mascara":
            try:
                return self._send(200, self._mascara(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/inpaint":
            try:
                return self._send(200, self._inpaint(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        if p == "/api/generar":
            try:
                return self._send(200, self._generar(b))
            except M.Cancelado:
                return self._send(200, {"cancelado": True})
            except Exception as e:
                return self._send(200, {"error": _mensaje(e)})

        return self._send(404, {"error": "ruta desconocida"})

    @staticmethod
    def _orden(n_personas, pose, estilo, escena):
        o = [f"<image{i+1}> person" for i in range(n_personas)]
        i = n_personas
        for nombre, obj in (("pose", pose), ("style", estilo), ("scene", escena)):
            if obj is not None:
                i += 1
                o.append(f"<image{i}> {nombre}")
        return o

    def _lote(self, b):
        """Run many prompts with the image model mounted the whole time.

        The arbiter runs ONCE here, not per image: cycling the other models in
        and out between variations would cost more than the generations.
        """
        from PIL import Image
        prompts = [p for p in (b.get("prompts") or []) if str(p).strip()]
        if not prompts:
            return {"error": "give me a list of prompts"}
        prompts = prompts[:64]

        personas = [_referencia(d) for d in b.get("personas", [])]
        escena = _referencia(b["escena"]) if b.get("escena") else None
        pose = None
        if b.get("pose_lib"):
            r = P.ruta(b["pose_lib"])
            pose = Image.open(r).convert("RGB") if r else None

        mp = min(float(b.get("megapixeles", 1)), (_tope(1) ** 2) / (1024 * 1024))
        res = int((mp * 1024 * 1024) ** 0.5)
        ratio = b.get("ratio", "auto")
        ancho, alto = (None, None) if ratio == "auto" else M.dimensiones(ratio, mp)
        steps = _pasos(b)
        base = int(b.get("seed", 0)) or int(time.time()) % 100000
        transp = bool(b.get("transparencia"))

        fallo = _cargar_motor()
        if fallo:
            return {"error": fallo}
        motor.ajustar_muestreo("turbo" if _turbo(b) else
                               str(b.get("muestreo") or leer_ajustes()["muestreo"]))

        hechas = []
        with _lock:
            motor.aplicar_lora(os.path.join(LORAS, b["lora"]) if b.get("lora") else None,
                               float(b.get("fuerza_lora", 1.0)),
                               turbo=_turbo(b))
            for i, texto in enumerate(prompts):
                lim = int(leer_ajustes().get("limite_c", 0))
                if lim and i:
                    espera = M.esperar_a_que_enfrie(lim)
                    if espera.get("esperado_s"):
                        print(f"  [lote] {espera['esperado_s']}s esperando a "
                              f"{espera['grados']}C", flush=True)
                t0 = time.time()
                img, armado = motor.generar(personas=personas, pose=pose, escena=escena,
                                            texto=str(texto), res=res, ancho=ancho,
                                            alto=alto, transparencia=transp, steps=steps,
                                            cfg=_cfg(b)[0], negativo=_cfg(b)[1],
                                            seed=base + i)
                hechas.append({"archivo": "/salidas/" + _guardar(img, "lote", {
                                   "prompt": armado, "caso": "batch", "seed": base + i,
                                   "steps": _pasos(b), "vae": motor.vae_actual,
                                   "tam": f"{img.width}x{img.height}",
                                   "modelo": "Qwen-Image 2.1"}),
                               "seed": base + i, "prompt": str(texto),
                               "tam": f"{img.width}x{img.height}",
                               "segundos": round(time.time() - t0, 1)})
        return {"imagenes": hechas, "total": len(hechas)}

    def _resolver_mascara(self, b, img, crecer_por_defecto=0):
        """The mask comes from the brush when there is one, from the phrase
        otherwise. Returns (mask, error): only one of the two is set."""
        from PIL import Image
        pintada = b.get("mascara")
        if pintada:
            m = _img_de_data_url(pintada).convert("L")
            if m.size != img.size:
                m = m.resize(img.size, Image.NEAREST)
            if not m.getbbox():
                return None, "the painted mask is empty - paint over the area first"
        else:
            frase = (b.get("frase") or "").strip()
            if not frase:
                return None, "paint the area, or describe what to select"
            dev = "cuda" if cfg.get("backend") == "cuda" else "cpu"
            usar("segmentacion")
            SEG.cargar(dev, M.ruta_aux(cfg['ruta_modelos']))
            if not SEG.disponible():
                return None, SEG.error() or "could not load the segmenter"
            m = SEG.mascara(img, frase, umbral=float(b.get("umbral", 0.5)))
            if b.get("afinar", leer_ajustes().get("afinar_mascara", True)):
                if SEG.cargar_afinador(dev, M.ruta_aux(cfg['ruta_modelos'])):
                    m = SEG.afinar(img, m)
        crecer = int(b.get("crecer", crecer_por_defecto))
        # lo pintado ya es lo que el usuario quiere: crecerlo se lo comeria
        if crecer and not pintada:
            m = IN.dilatar(m, crecer)
        return m, None

    @staticmethod
    def _galeria(limite: int = 120):
        """Lo que hay en salidas/, lo mas reciente primero.

        La carpeta ES la galeria: no hay base de datos que se desincronice con
        el disco, y borrar un archivo ahi lo borra aqui.
        """
        filas = []
        try:
            for n in os.listdir(SALIDAS):
                if n.startswith(".") or not n.lower().endswith((".png", ".jpg", ".jpeg")):
                    continue
                ruta = os.path.join(SALIDAS, n)
                try:
                    st = os.stat(ruta)
                except OSError:
                    continue
                clase = ("summary" if n.startswith("resumen") else
                         "edit" if n.startswith("inpaint") else
                         "mask" if n.startswith("mask") else
                         "batch" if n.startswith("lote") else
                         "look" if n.startswith("efecto") else
                         "upscale" if n.startswith("upscale") else "image")
                filas.append({"archivo": "/salidas/" + n, "nombre": n, "clase": clase,
                              "cuando": int(st.st_mtime), "kb": round(st.st_size / 1024),
                              "meta": _leer_meta(ruta)})
        except OSError:
            pass
        filas.sort(key=lambda r: r["cuando"], reverse=True)
        return {"items": filas[:limite], "total": len(filas), "carpeta": SALIDAS}

    @staticmethod
    def _borrar(b):
        """Move one output to salidas/_papelera/ instead of unlinking it.

        Recoverable on purpose: the gallery is a grid of thumbnails that look
        alike, and a click that cannot be undone there is how the good one
        disappears. The folder is the user's; emptying the bin is their call.
        """
        nombre = os.path.basename((b.get("nombre") or "").strip())
        if not nombre or nombre.startswith("."):
            return {"error": "no file given"}
        origen = os.path.join(SALIDAS, nombre)
        # basename ya corta cualquier ../, pero se comprueba el resultado igual
        if not os.path.isfile(origen) or os.path.dirname(os.path.abspath(origen)) != \
                os.path.abspath(SALIDAS):
            return {"error": "that file is not in the outputs folder"}
        papelera = os.path.join(SALIDAS, "_papelera")
        os.makedirs(papelera, exist_ok=True)
        destino = os.path.join(papelera, nombre)
        n = 1
        while os.path.exists(destino):
            raiz, ext = os.path.splitext(nombre)
            destino = os.path.join(papelera, f"{raiz}_{n}{ext}")
            n += 1
        try:
            os.replace(origen, destino)
        except OSError as e:
            return {"error": _mensaje(e)}
        return {"movido": nombre, "a": destino}

    @staticmethod
    def _abrir_carpeta():
        """Open salidas/ in whatever the system uses for folders."""
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(SALIDAS)                      # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", SALIDAS])
            else:
                subprocess.Popen(["xdg-open", SALIDAS])
            return {"ok": True, "carpeta": SALIDAS}
        except Exception as e:
            return {"error": _mensaje(e), "carpeta": SALIDAS}

    def _editar_entero(self, img, texto, b, lora=None, fuerza=1.0, escala=1.0,
                       referencias=None, modo="material"):
        """Edit the whole frame: no mask, no crop, the original as reference.

        `escala` multiplies each side of the output. The aspect ratio always
        comes from the input, so nothing is stretched on the way out.
        """
        import math
        fallo = _cargar_motor()
        if fallo:
            return None, fallo
        motor.ajustar_muestreo("turbo" if _turbo(b) else
                               str(b.get("muestreo") or leer_ajustes()["muestreo"]))

        tope = _tope(1 + len(referencias or []))
        aw = max(256, min(tope, round(img.width * escala / 32) * 32))
        ah = max(256, min(tope, round(img.height * escala / 32) * 32))

        with _lock:
            motor.usar_offload(leer_ajustes().get("offload") or cfg["offload"])
            motor.usar_vae(b.get("vae") or leer_ajustes().get("vae", "hdr"))
            motor.aplicar_lora(os.path.join(LORAS, lora) if lora else None,
                               float(fuerza), turbo=_turbo(b))
            gen, prompt = motor.editar(imagen=img, texto=texto,
                                       steps=_pasos(b),
                                       seed=int(b.get("seed", 0)) or int(time.time()) % 100000,
                                       res=int(math.sqrt(aw * ah)), ancho=aw, alto=ah,
                                       referencias=referencias or [], modo=modo)
            if lora:                       # un efecto no deja el LoRA puesto
                motor.aplicar_lora(None, 1.0, turbo=_turbo(b))
        return (gen, prompt), None

    def _mejorar(self, b):
        """Rewrite a loose request into a prompt this model reads well."""
        texto = (b.get("prompt") or "").strip()
        if not texto:
            return {"error": "write something first, even a few words"}
        dev = "cuda" if cfg.get("backend") == "cuda" else "cpu"
        usar("vision")
        VIS.cargar(cfg["ruta_modelos"], dev, bits=int(leer_ajustes()["vlm_bits"]))
        if not VIS.disponible():
            return {"error": VIS.error() or "could not load the vision model"}
        t0 = time.time()
        # el caso decide las reglas: editar y generar no se piden igual
        salida = VIS.redactar(texto, edicion=bool(b.get("edicion")))
        if not salida:
            return {"error": "the rewrite came back empty"}
        return {"antes": texto, "texto": salida, "segundos": round(time.time() - t0, 1)}

    def _editar_region(self, img, texto, b, lora=None, fuerza=1.0, prefijo="inpaint",
                       caso="replace", extra=None):
        """Crop around the mask, regenerate that crop, stitch it back.

        Shared by the replacement path and by a look applied to part of a photo:
        the arithmetic is identical and only the prompt and the LoRA differ.
        """
        import math
        m, err = self._resolver_mascara(b, img, crecer_por_defecto=8)
        if err:
            return None, err

        mp = min(float(b.get("megapixeles", 1)), (_tope(1) ** 2) / (1024 * 1024))
        res = int((mp * 1024 * 1024) ** 0.5)
        caja, crop, mcrop = IN.recorte(img, m, padding=float(b.get("padding", 0.35)))
        ratio = (caja[2] - caja[0]) / max(1, (caja[3] - caja[1]))
        area = mp * 1024 * 1024
        aw = max(256, round(math.sqrt(area * ratio) / 32) * 32)
        ah = max(256, round(math.sqrt(area / ratio) / 32) * 32)

        fallo = _cargar_motor()
        if fallo:
            return None, fallo
        motor.ajustar_muestreo("turbo" if _turbo(b) else
                               str(b.get("muestreo") or leer_ajustes()["muestreo"]))

        refs = [_referencia(d) for d in b.get("referencias", [])]
        base = int(b.get("seed", 0)) or int(time.time()) % 100000
        salidas, prompt = [], texto
        with _lock:
            motor.usar_offload(leer_ajustes().get("offload") or cfg["offload"])
            motor.usar_vae(b.get("vae") or leer_ajustes().get("vae", "hdr"))
            motor.aplicar_lora(os.path.join(LORAS, lora) if lora else None,
                               float(fuerza), turbo=_turbo(b))
            for k in range(max(1, min(4, int(b.get("variantes", 1))))):
                gen, prompt = motor.editar(imagen=crop, texto=texto,
                                           steps=_pasos(b), seed=base + k,
                                           res=res, referencias=refs, ancho=aw, alto=ah)
                final = IN.pegar(img, gen, mcrop, caja,
                                 difuminado=int(b.get("difuminado", 12)))
                receta = {"prompt": prompt, "caso": caso, "seed": base + k,
                          "steps": _pasos(b), "vae": motor.vae_actual,
                          "lora": lora, "fuerza_lora": fuerza if lora else None,
                          "tam": f"{final.width}x{final.height}",
                          "modelo": "Qwen-Image 2.1"}
                if extra:
                    receta.update(extra)
                salidas.append({"archivo": "/salidas/" + _guardar(final, prefijo, receta),
                                "seed": base + k, "tam": f"{final.width}x{final.height}"})
            if lora:
                # se descarga al salir: cada ejecucion vuelve a aplicar el suyo,
                # y asi ninguno se queda puesto para la siguiente que no lo pida
                motor.aplicar_lora(None, 1.0, turbo=_turbo(b))
        return {"imagenes": salidas, "caja": list(caja), "prompt": prompt,
                "crop": f"{caja[2]-caja[0]}x{caja[3]-caja[1]}", "generado": f"{aw}x{ah}"}, None

    def _efecto(self, b):
        """Apply one of the gallery looks, to the whole frame or to one region."""
        e = EF.buscar((b.get("efecto") or "").strip())
        if not e:
            return {"error": "unknown effect"}
        lora = e.get("lora")
        if lora and not os.path.exists(os.path.join(LORAS, lora)):
            return {"error": f"this look needs {lora} in loras/"}
        img = _img_de_data_url(b["imagen"])
        t0 = time.time()

        # con mascara, el look va solo a esa region y el resto vuelve identico;
        # sin ella, al cuadro entero, que es lo habitual
        if b.get("mascara") or (b.get("frase") or "").strip():
            r, err = self._editar_region(img, e["prompt"], b, lora=lora,
                                         fuerza=e.get("fuerza", 1.0),
                                         prefijo="efecto", caso="look",
                                         extra={"efecto": e["nombre"]})
            if err:
                return {"error": err}
            r["efecto"] = e["nombre"]
            r["segundos"] = round(time.time() - t0, 1)
            return r

        res, err = self._editar_entero(img, e["prompt"], b, lora=lora,
                                       fuerza=e.get("fuerza", 1.0))
        if err:
            return {"error": err}
        gen, prompt = res
        return {"imagenes": [{"archivo": "/salidas/" + _guardar(gen, "efecto", {
                                  "prompt": prompt, "caso": "look", "efecto": e["nombre"],
                                  "seed": b.get("seed"), "steps": b.get("steps", 25),
                                  "vae": motor.vae_actual, "lora": lora,
                                  "fuerza_lora": e.get("fuerza") if lora else None,
                                  "tam": f"{gen.width}x{gen.height}",
                                  "modelo": "Qwen-Image 2.1"}),
                              "tam": f"{gen.width}x{gen.height}"}],
                "prompt": prompt, "efecto": e["nombre"],
                "segundos": round(time.time() - t0, 1)}

    def _editar(self, b):
        """The model's own editing, with the whole picture and an instruction.

        Every other edit path here selects a region, regenerates it and stitches
        it back. That is the right tool when the change is bounded -- a sweater,
        a sky -- and the wrong one when it is not: swapping the person in a
        photograph is not a patch, and a patch is what it looks like.

        This hands over the photograph, up to three references and the sentence,
        and lets the model decide where to touch. No mask, no crop, no seam.
        """
        img = _img_de_data_url(b["imagen"])
        refs = [_referencia(d) for d in b.get("referencias", [])]
        texto = (b.get("prompt") or "").strip()
        if not texto:
            return {"error": "say what to change"}
        if not refs:
            return {"error": "add at least one reference picture"}
        t0 = time.time()
        res, err = self._editar_entero(img, texto, b, referencias=refs, modo="libre")
        if err:
            return {"error": err}
        gen, prompt = res
        return {"imagenes": [{"archivo": "/salidas/" + _guardar(gen, "editar", {
                                  "prompt": prompt, "caso": "edit",
                                  "seed": b.get("seed"), "steps": _pasos(b),
                                  "vae": motor.vae_actual,
                                  "tam": f"{gen.width}x{gen.height}",
                                  "modelo": "Qwen-Image 2.1"}),
                              "tam": f"{gen.width}x{gen.height}"}],
                "prompt": prompt, "segundos": round(time.time() - t0, 1)}

    def _estilo(self, b):
        """Redraw a photograph in the visual language of a reference picture.

        Not the same as applying a look: a look is a treatment this app already
        knows, and this takes the manner of an image the user brings.
        """
        img = _img_de_data_url(b["imagen"])
        ref = b.get("estilo")
        if not ref:
            return {"error": "add the picture whose style you want"}
        t0 = time.time()
        estilo_img = _referencia(ref)

        # Medido: pedir "el estilo de <image2>" no mueve casi nada; nombrar la
        # tecnica si. Asi que primero se lee el cuadro con el VLM y lo que sale
        # -- formas planas, empaste visible, trama de semitono, lo que sea --
        # va al generador como texto, que es a lo que este modelo responde.
        tecnica = ""
        if b.get("leer_estilo", True):
            try:
                dev = "cuda" if cfg.get("backend") == "cuda" else "cpu"
                usar("vision")
                VIS.cargar(cfg["ruta_modelos"], dev, bits=int(leer_ajustes()["vlm_bits"]))
                if VIS.disponible():
                    with _lock:
                        tecnica = VIS.preguntar(
                            estilo_img, "free",
                            extra=("Describe only HOW this picture is made, never what it "
                                   "shows. Name the medium, the mark-making, the surface "
                                   "and texture, how many colours and which, how edges and "
                                   "shadows are drawn, and whether there are gradients. "
                                   "Two sentences, concrete and visual, no adjectives of "
                                   "praise."),
                            max_tokens=140).strip()
            except Exception:
                tecnica = ""

        texto = (b.get("prompt") or "").strip()
        if tecnica:
            texto = (texto + " " if texto else "") + tecnica

        # Con la tecnica leida la referencia sobra, y peor que sobrar: estorba.
        # Se la deja solo cuando no se pudo leer el cuadro.
        refs = [] if tecnica and not b.get("ref_estilo") else [estilo_img]
        res, err = self._editar_entero(img, texto, b,
                                       referencias=refs, modo="estilo")
        if err:
            return {"error": err}
        gen, prompt = res
        return {"imagenes": [{"archivo": "/salidas/" + _guardar(gen, "estilo", {
                                  "prompt": prompt, "caso": "restyle",
                                  "tecnica_leida": tecnica,
                                  "seed": b.get("seed"), "steps": b.get("steps", 25),
                                  "vae": motor.vae_actual,
                                  "tam": f"{gen.width}x{gen.height}",
                                  "modelo": "Qwen-Image 2.1"}),
                              "tam": f"{gen.width}x{gen.height}"}],
                "prompt": prompt, "segundos": round(time.time() - t0, 1)}

    def _reescalar(self, b):
        """Redraw the image larger, using it as its own reference.

        The target is the whole 2K budget rather than a fixed multiplier: area
        scaled to 2048x2048, capped at 4x per side, which is what the 2K
        workflows for this model do.
        """
        import math
        img = _img_de_data_url(b["imagen"])
        objetivo = float(b.get("objetivo", 2048))
        escala = min(4.0, math.sqrt((objetivo * objetivo) / (img.width * img.height)))
        if escala <= 1.02:
            return {"error": "this image is already at or above the target size"}
        texto = (b.get("prompt") or "").strip() or (
            "Enhance this image to high resolution while preserving the original "
            "composition, lighting and atmosphere. Keep the original style, whether it is "
            "a photograph or an illustration.")
        t0 = time.time()
        res, err = self._editar_entero(img, texto, b, escala=escala)
        if err:
            return {"error": err}
        gen, prompt = res
        return {"imagenes": [{"archivo": "/salidas/" + _guardar(gen, "upscale", {
                                  "prompt": prompt, "caso": "upscale",
                                  "seed": b.get("seed"), "steps": b.get("steps", 25),
                                  "vae": motor.vae_actual,
                                  "tam": f"{gen.width}x{gen.height}",
                                  "modelo": "Qwen-Image 2.1"}),
                              "tam": f"{gen.width}x{gen.height}"}],
                "de": f"{img.width}x{img.height}", "escala": round(escala, 2),
                "prompt": prompt, "segundos": round(time.time() - t0, 1)}

    def _mascara(self, b):
        """Preview: resolve the mask and return the tinted overlay."""
        img = _img_de_data_url(b["imagen"])
        m, err = self._resolver_mascara(b, img)
        if err:
            return {"error": err}
        caja = IN.bbox_de_mascara(m)
        cobertura = sum(1 for v in m.getdata() if v > 127) / (m.width * m.height)
        prev = IN.previsualizar_mascara(img, m)
        return {"preview": "/salidas/" + _guardar(prev, "mask"),
                "cobertura": round(cobertura * 100, 1), "caja": caja}

    def _inpaint(self, b):
        """Replace part of an image: same crop-and-stitch as a masked look."""
        img = _img_de_data_url(b["imagen"])
        texto = (b.get("prompt") or "").strip()
        r, err = self._editar_region(img, texto, b,
                                     lora=b.get("lora"),
                                     fuerza=float(b.get("fuerza_lora", 1.0)),
                                     prefijo="inpaint", caso="replace")
        return {"error": err} if err else r

    def _generar(self, b):
        from PIL import Image
        personas = [_referencia(d) for d in b.get("personas", [])]
        pose = None
        if b.get("pose_lib"):
            ruta = P.ruta(b["pose_lib"])
            pose = Image.open(ruta).convert("RGB") if ruta else None
        elif b.get("pose_url"):
            f = os.path.join(ENTRADAS, os.path.basename(b["pose_url"]))
            pose = Image.open(f).convert("RGB") if os.path.exists(f) else None
        elif b.get("pose"):
            pose = _referencia(b["pose"])
        escena = _referencia(b["escena"]) if b.get("escena") else None
        estilo = _referencia(b["estilo"]) if b.get("estilo") else None

        steps = _pasos(b)
        base = int(b.get("seed", 0)) or int(time.time()) % 100000
        variantes = max(1, min(6, int(b.get("variantes", 1))))
        transp = bool(b.get("transparencia"))

        # el perfil limita el area, no el lado: un 16:9 a 4 MP es mas ancho que
        # res_max pero cuesta lo mismo que un cuadrado de res_max
        mp = float(b.get("megapixeles", 1))
        n_refs = (len(personas) + (escena is not None) + (estilo is not None)
                  + (pose is not None))
        tope_mp = (_tope(n_refs) ** 2) / (1024 * 1024)
        mp = min(mp, tope_mp)
        ratio = b.get("ratio", "1:1")
        if ratio == "auto":
            ancho = alto = None
            res = int((mp * 1024 * 1024) ** 0.5)
        else:
            ancho, alto = M.dimensiones(ratio, mp)
            res = int((mp * 1024 * 1024) ** 0.5)

        # Medido el 2026-09-21: con una escena cargada y un prompt que no la
        # menciona, la escena se ignora — gana el contexto de la foto de la
        # persona, que tambien trae fondo, ropa y luz. La clausula de andamiaje
        # sola no basta. Se describe la escena y se anade al texto.
        texto = b.get("prompt", "")
        descripcion = ""
        if escena is not None and b.get("describir_escena", leer_ajustes()["describir_escena"]):
            try:
                usar("vision")
                dev = "cuda" if cfg.get("backend") == "cuda" else "cpu"
                VIS.cargar(cfg["ruta_modelos"], dev, bits=int(leer_ajustes()["vlm_bits"]))
                if VIS.disponible():
                    descripcion = VIS.preguntar(escena, "scene", max_tokens=110)
            except Exception:
                descripcion = ""

        if descripcion:
            texto = (texto.strip() + " " + descripcion).strip()

        fallo = _cargar_motor()
        if fallo:
            return {"error": fallo}
        motor.ajustar_muestreo("turbo" if _turbo(b) else
                               str(b.get("muestreo") or leer_ajustes()["muestreo"]))

        hechas, prompt = [], ""
        with _lock:                # una generacion a la vez: la VRAM no da para mas
            motor.usar_offload(leer_ajustes().get("offload") or cfg["offload"])
            motor.usar_vae(b.get("vae") or leer_ajustes().get("vae", "stock"))
            motor.aplicar_lora(os.path.join(LORAS, b["lora"]) if b.get("lora") else None,
                               float(b.get("fuerza_lora", 1.0)),
                               turbo=_turbo(b))
            for k in range(variantes):
                img, prompt = motor.generar(personas=personas, pose=pose, escena=escena,
                                            estilo=estilo, estilo_modo=b.get("estilo_modo", "look"),
                                            texto=texto, res=res,
                                            ancho=ancho, alto=alto, transparencia=transp,
                                            steps=steps, seed=base + k,
                                            cfg=_cfg(b)[0], negativo=_cfg(b)[1])
                receta = {"prompt": prompt, "caso": b.get("caso", "generate"),
                          "seed": base + k, "steps": steps, "vae": motor.vae_actual,
                          "tam": f"{img.width}x{img.height}", "ratio": b.get("ratio"),
                          "megapixeles": b.get("megapixeles"), "lora": b.get("lora"),
                          "fuerza_lora": b.get("fuerza_lora") if b.get("lora") else None,
                          "orden": self._orden(len(personas), pose, estilo, escena),
                          "modelo": "Qwen-Image 2.1"}
                hechas.append({"archivo": "/salidas/" + _guardar(img, "out", receta),
                               "seed": base + k,
                               "tam": f"{img.width}x{img.height}"})

        hoja_resumen = None
        if b.get("resumen", leer_ajustes()["resumen"]) and hechas:
            try:
                from PIL import Image as _I
                entradas = [("person", personas[0])] if personas else []
                if pose is not None:
                    entradas.append(("pose", pose))
                if estilo is not None:
                    entradas.append(("style", estilo))
                if escena is not None:
                    entradas.append(("scene", escena))
                ultima = _I.open(os.path.join(SALIDAS,
                                 os.path.basename(hechas[-1]["archivo"]))).convert("RGB")
                pie = f"{hechas[-1]['tam']}  ·  seed {hechas[-1]['seed']}  ·  {steps} steps"
                h = RES.hoja(entradas, ultima, prompt=b.get("prompt", ""), pie=pie)
                hoja_resumen = "/salidas/" + _guardar(h, "resumen")
            except Exception:
                hoja_resumen = None

        return {"imagenes": hechas, "prompt": prompt,
                "descripcion_escena": descripcion,
                "avisos": M.avisos_de_uso(len(personas), escena is not None,
                                          bool(b.get("espera_persona", True))),
                "orden": self._orden(len(personas), pose, estilo, escena),
                "resumen": hoja_resumen}


def main():
    os.makedirs(SALIDAS, exist_ok=True)
    os.makedirs(ENTRADAS, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print("=" * 60)
    print(f"  QwenStudio  ->  {url}")
    print(f"  Perfil {cfg['nivel']} · {cfg['acelerador']} · {cfg['dtype']}"
          f" · cuant {cfg['cuantizacion']} · offload {cfg['offload']}")
    print("=" * 60)
    if not M.pesos_completos(cfg["ruta_modelos"]):
        print("\n  Los pesos todavia no estan. Al abrir la pagina te deja bajarlos.\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  cerrando")


if __name__ == "__main__":
    main()
