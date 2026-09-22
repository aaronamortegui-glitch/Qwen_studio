"""Servidor local de QwenStudio.

Sirve la interfaz en http://127.0.0.1:7860 y ejecuta la inferencia en proceso,
sin ComfyUI. Nada sale de la maquina.
"""

from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import re
import subprocess
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
    "steps": 25,
    "megapixeles": 1,
    "vlm_bits": 4,                # 4 u 8; 8 describe algo mejor y ocupa ~13 GB
    "mantener_montado": False,    # no desmontar entre bloques (para lotes)
    # hdr por defecto: medido el 2026-09-22 con la misma semilla, +19% de
    # saturacion y +27% de energia de gradiente sin tocar contraste ni luz
    # media. Si el archivo no esta, usar_vae cae al de serie sin quejarse.
    "vae": "hdr",                 # hdr | stock
}


def leer_ajustes() -> dict:
    a = dict(AJUSTES_DEF)
    try:
        with open(AJUSTES, encoding="utf-8") as f:
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

cfg = json.load(open(CONFIG, encoding="utf-8"))
estado_descarga = M.Descarga()
motor = M.Motor(cfg)
_lock = threading.Lock()


# ------------------------------------------------------------------ recursos

registro.registrar("imagen", montado=lambda: motor.listo,
                   desmontar=motor.liberar, vram_gb=21.3, etiqueta="Qwen-Image 2.1")
registro.registrar("vision", montado=VIS.disponible,
                   desmontar=VIS.descargar_de_memoria, vram_gb=7.1, etiqueta="Qwen3-VL")
registro.registrar("segmenta", montado=SEG.disponible,
                   desmontar=SEG.descargar_de_memoria, vram_gb=0.6, etiqueta="CLIPSeg")


def usar(quien: str) -> list[str]:
    """Free the VRAM the next block needs. See qwenstudio/recursos.py.

    `mantener_montado` skips it: in a batch the models would otherwise cycle in
    and out between images, which costs more than the generations themselves.
    """
    if leer_ajustes().get("mantener_montado"):
        return []
    return registro.usar(quien)


# ------------------------------------------------------------------ util

def _img_de_data_url(data_url: str):
    from PIL import Image
    m = re.match(r"data:image/[\w.+-]+;base64,(.*)$", data_url, re.S)
    if not m:
        raise ValueError("imagen no valida")
    return Image.open(io.BytesIO(base64.b64decode(m.group(1)))).convert("RGB")


def _guardar(img, prefijo="out") -> str:
    os.makedirs(SALIDAS, exist_ok=True)
    nombre = f"{prefijo}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.png"
    img.save(os.path.join(SALIDAS, nombre))
    return nombre


def _esqueleto(img):
    """Deriva un esqueleto OpenPose si hay un python con easy-dwpose a mano."""
    if not os.path.exists(DWPOSE_PY):
        raise RuntimeError("No hay un entorno con easy-dwpose instalado. "
                           "Sube un esqueleto ya hecho en vez de una foto.")
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
        raise RuntimeError((r.stderr or "")[-300:] or "DWpose no genero el esqueleto")
    from PIL import Image
    return Image.open(dst).convert("RGB"), os.path.basename(dst)


# ------------------------------------------------------------------ http

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

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
                                               "cuantizacion", "offload", "res_max",
                                               "vram_gb", "ram_gb")},
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
            return self._send(200, PR.catalogo())

        if p == "/api/poses":
            return self._send(200, P.catalogo())

        if p == "/api/efectos":
            return self._send(200, EF.catalogo(LORAS))

        if p.startswith("/efectos/"):
            f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                             "ejemplos", "efectos", os.path.basename(p[9:]))
            if not os.path.exists(f):
                return self._send(404, b"not found", "text/plain")
            with open(f, "rb") as fh:
                return self._send(200, fh.read(), "image/jpeg")

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
            return self._send(400, {"error": "json invalido"})
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

        if p == "/api/desmontar":
            soltados = registro.desmontar_todo(excepto=b.get("excepto"))
            return self._send(200, {"desmontados": soltados})

        if p == "/api/lote":
            try:
                return self._send(200, self._lote(b))
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})

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
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})

        if p == "/api/liberar_vision":
            VIS.descargar_de_memoria()
            return self._send(200, {"ok": True})

        if p == "/api/mejorar_prompt":
            try:
                return self._send(200, self._mejorar(b))
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})

        if p == "/api/efecto":
            try:
                return self._send(200, self._efecto(b))
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})

        if p == "/api/reescalar":
            try:
                return self._send(200, self._reescalar(b))
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})

        if p == "/api/abrir_carpeta":
            return self._send(200, self._abrir_carpeta())

        if p == "/api/mascara":
            try:
                return self._send(200, self._mascara(b))
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})

        if p == "/api/inpaint":
            try:
                return self._send(200, self._inpaint(b))
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})

        if p == "/api/generar":
            try:
                return self._send(200, self._generar(b))
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})

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

        personas = [_img_de_data_url(d) for d in b.get("personas", [])]
        escena = _img_de_data_url(b["escena"]) if b.get("escena") else None
        pose = None
        if b.get("pose_lib"):
            r = P.ruta(b["pose_lib"])
            pose = Image.open(r).convert("RGB") if r else None

        mp = min(float(b.get("megapixeles", 1)), (int(cfg["res_max"]) ** 2) / (1024 * 1024))
        res = int((mp * 1024 * 1024) ** 0.5)
        ratio = b.get("ratio", "auto")
        ancho, alto = (None, None) if ratio == "auto" else M.dimensiones(ratio, mp)
        steps = int(b.get("steps", 25))
        base = int(b.get("seed", 0)) or int(time.time()) % 100000
        transp = bool(b.get("transparencia"))

        usar("imagen")
        if not motor.listo:
            motor.cargar()
            if not motor.listo:
                return {"error": motor.error or "could not load the model"}

        hechas = []
        with _lock:
            motor.aplicar_lora(os.path.join(LORAS, b["lora"]) if b.get("lora") else None,
                               float(b.get("fuerza_lora", 1.0)))
            for i, texto in enumerate(prompts):
                t0 = time.time()
                img, _ = motor.generar(personas=personas, pose=pose, escena=escena,
                                       texto=str(texto), res=res, ancho=ancho, alto=alto,
                                       transparencia=transp, steps=steps, seed=base + i)
                hechas.append({"archivo": "/salidas/" + _guardar(img, "lote"),
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
            SEG.cargar(dev)
            if not SEG.disponible():
                return None, SEG.error() or "could not load the segmenter"
            m = SEG.mascara(img, frase, umbral=float(b.get("umbral", 0.5)))
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
                         "batch" if n.startswith("lote") else "image")
                filas.append({"archivo": "/salidas/" + n, "nombre": n, "clase": clase,
                              "cuando": int(st.st_mtime), "kb": round(st.st_size / 1024)})
        except OSError:
            pass
        filas.sort(key=lambda r: r["cuando"], reverse=True)
        return {"items": filas[:limite], "total": len(filas), "carpeta": SALIDAS}

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
            return {"error": f"{type(e).__name__}: {e}", "carpeta": SALIDAS}

    def _editar_entero(self, img, texto, b, lora=None, fuerza=1.0, escala=1.0):
        """Edit the whole frame: no mask, no crop, the original as reference.

        `escala` multiplies each side of the output. The aspect ratio always
        comes from the input, so nothing is stretched on the way out.
        """
        import math
        usar("imagen")
        if not motor.listo:
            motor.cargar()
            if not motor.listo:
                return None, (motor.error or "could not load the model")

        tope = int(cfg["res_max"])
        aw = max(256, min(tope, round(img.width * escala / 32) * 32))
        ah = max(256, min(tope, round(img.height * escala / 32) * 32))

        with _lock:
            motor.usar_vae(b.get("vae") or leer_ajustes().get("vae", "hdr"))
            motor.aplicar_lora(os.path.join(LORAS, lora) if lora else None, float(fuerza))
            gen, prompt = motor.editar(imagen=img, texto=texto,
                                       steps=int(b.get("steps", 25)),
                                       seed=int(b.get("seed", 0)) or int(time.time()) % 100000,
                                       res=int(math.sqrt(aw * ah)), ancho=aw, alto=ah)
            if lora:                       # un efecto no deja el LoRA puesto
                motor.aplicar_lora(None, 1.0)
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
        salida = VIS.redactar(texto)
        if not salida:
            return {"error": "the rewrite came back empty"}
        return {"antes": texto, "texto": salida, "segundos": round(time.time() - t0, 1)}

    def _efecto(self, b):
        """Apply one of the gallery looks to a whole image."""
        e = EF.buscar((b.get("efecto") or "").strip())
        if not e:
            return {"error": "unknown effect"}
        lora = e.get("lora")
        if lora and not os.path.exists(os.path.join(LORAS, lora)):
            return {"error": f"this look needs {lora} in loras/"}
        img = _img_de_data_url(b["imagen"])
        t0 = time.time()
        res, err = self._editar_entero(img, e["prompt"], b, lora=lora,
                                       fuerza=e.get("fuerza", 1.0))
        if err:
            return {"error": err}
        gen, prompt = res
        return {"imagenes": [{"archivo": "/salidas/" + _guardar(gen, "efecto"),
                              "tam": f"{gen.width}x{gen.height}"}],
                "prompt": prompt, "efecto": e["nombre"],
                "segundos": round(time.time() - t0, 1)}

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
        return {"imagenes": [{"archivo": "/salidas/" + _guardar(gen, "upscale"),
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
        """Segment, crop around the mask, regenerate at full resolution, stitch back."""
        from PIL import Image
        img = _img_de_data_url(b["imagen"])
        texto = (b.get("prompt") or "").strip()
        m, err = self._resolver_mascara(b, img, crecer_por_defecto=8)
        if err:
            return {"error": err}

        mp = min(float(b.get("megapixeles", 1)), (int(cfg["res_max"]) ** 2) / (1024 * 1024))
        res = int((mp * 1024 * 1024) ** 0.5)
        caja, crop, mcrop = IN.recorte(img, m, padding=float(b.get("padding", 0.35)))

        # the crop keeps its own aspect; the generation matches it so nothing
        # gets squashed on the way back in
        ratio = (caja[2] - caja[0]) / max(1, (caja[3] - caja[1]))
        import math
        area = mp * 1024 * 1024
        aw = max(256, round(math.sqrt(area * ratio) / 32) * 32)
        ah = max(256, round(math.sqrt(area / ratio) / 32) * 32)

        usar("imagen")
        if not motor.listo:
            motor.cargar()
            if not motor.listo:
                return {"error": motor.error or "could not load the model"}

        refs = [_img_de_data_url(d) for d in b.get("referencias", [])]
        base = int(b.get("seed", 0)) or int(time.time()) % 100000
        salidas = []
        with _lock:
            motor.aplicar_lora(os.path.join(LORAS, b["lora"]) if b.get("lora") else None,
                               float(b.get("fuerza_lora", 1.0)))
            for k in range(max(1, min(4, int(b.get("variantes", 1))))):
                gen, prompt = motor.editar(imagen=crop, texto=texto, steps=int(b.get("steps", 25)),
                                           seed=base + k, res=res, referencias=refs,
                                           ancho=aw, alto=ah)
                final = IN.pegar(img, gen, mcrop, caja,
                                 difuminado=int(b.get("difuminado", 12)))
                salidas.append({"archivo": "/salidas/" + _guardar(final, "inpaint"),
                                "seed": base + k, "tam": f"{final.width}x{final.height}"})
        return {"imagenes": salidas, "caja": list(caja), "prompt": prompt,
                "crop": f"{caja[2]-caja[0]}x{caja[3]-caja[1]}", "generado": f"{aw}x{ah}"}

    def _generar(self, b):
        from PIL import Image
        personas = [_img_de_data_url(d) for d in b.get("personas", [])]
        pose = None
        if b.get("pose_lib"):
            ruta = P.ruta(b["pose_lib"])
            pose = Image.open(ruta).convert("RGB") if ruta else None
        elif b.get("pose_url"):
            f = os.path.join(ENTRADAS, os.path.basename(b["pose_url"]))
            pose = Image.open(f).convert("RGB") if os.path.exists(f) else None
        elif b.get("pose"):
            pose = _img_de_data_url(b["pose"])
        escena = _img_de_data_url(b["escena"]) if b.get("escena") else None
        estilo = _img_de_data_url(b["estilo"]) if b.get("estilo") else None

        steps = int(b.get("steps", 25))
        base = int(b.get("seed", 0)) or int(time.time()) % 100000
        variantes = max(1, min(6, int(b.get("variantes", 1))))
        transp = bool(b.get("transparencia"))

        # el perfil limita el area, no el lado: un 16:9 a 4 MP es mas ancho que
        # res_max pero cuesta lo mismo que un cuadrado de res_max
        mp = float(b.get("megapixeles", 1))
        tope_mp = (int(cfg["res_max"]) ** 2) / (1024 * 1024)
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

        usar("imagen")
        if not motor.listo:
            motor.cargar()
            if not motor.listo:
                return {"error": motor.error or "no pude cargar el modelo"}

        hechas, prompt = [], ""
        with _lock:
            motor.usar_vae(b.get("vae") or leer_ajustes().get("vae", "stock"))
            motor.aplicar_lora(os.path.join(LORAS, b["lora"]) if b.get("lora") else None,
                               float(b.get("fuerza_lora", 1.0)))       # una generacion a la vez: la VRAM no da para mas
            for k in range(variantes):
                img, prompt = motor.generar(personas=personas, pose=pose, escena=escena,
                                            estilo=estilo, estilo_modo=b.get("estilo_modo", "look"),
                                            texto=texto, res=res,
                                            ancho=ancho, alto=alto, transparencia=transp,
                                            steps=steps, seed=base + k)
                hechas.append({"archivo": "/salidas/" + _guardar(img), "seed": base + k,
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
                "avisos": M.avisos_de_uso(len(personas), escena is not None),
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
