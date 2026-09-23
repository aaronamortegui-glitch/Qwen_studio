"""Motor de inferencia: descarga de pesos y pipeline de Qwen-Image 2.1.

Sin ComfyUI. Usa QwenImage21Pipeline de diffusers directamente, configurada
segun el perfil que dejo el instalador en config.json.

El andamiaje de prompt viene de lo medido el 2026-09-21 (ver NOTAS del proyecto):
  - la persona va primero: si la escena va primera, la identidad no se transfiere
  - con escena, UNA sola foto de la persona; varias y el modelo las lee como
    sujetos distintos y mete varias personas en la imagen
  - positivo pero imperativo: "the face is hers" no transfiere, "must match
    <image1> exactly" si
"""

from __future__ import annotations

import json
import os
import threading
import time

REPO = "Qwen/Qwen-Image-2.1"

# Los 7 aspect ratios que el model card declara como soportados.
RATIOS = {"1:1": 1.0, "4:3": 4/3, "3:4": 3/4, "3:2": 3/2, "2:3": 2/3, "16:9": 16/9, "9:16": 9/16}


# Los tamanos 2K que publica la plantilla oficial del modelo. Calcularlos desde
# el presupuesto de pixeles daba entre un 1 y un 3 por ciento menos en todos los
# ratios salvo el cuadrado, y estos son los que el modelo tiene validados, asi
# que en 2K mandan ellos y no la formula.
OFICIAL_2K = {
    "1:1": (2048, 2048), "4:3": (2400, 1792), "3:4": (1792, 2400),
    "3:2": (2528, 1696), "2:3": (1696, 2528), "16:9": (2752, 1536),
    "9:16": (1536, 2752),
}


def dimensiones(ratio: str, megapixeles: float) -> tuple[int, int]:
    """Ancho y alto para un ratio y un presupuesto de pixeles, en multiplos de 32
    (que es lo que pide el VAE 16x con bloques de 2x2)."""
    import math
    if megapixeles >= 4 and ratio in OFICIAL_2K:
        return OFICIAL_2K[ratio]
    r = RATIOS.get(ratio, 1.0)
    area = megapixeles * 1024 * 1024
    w = round(math.sqrt(area * r) / 32) * 32
    h = round(math.sqrt(area / r) / 32) * 32
    return max(256, w), max(256, h)


# Los auxiliares viajan con los pesos y viven en modelos/aux, no en el cache
# global de HuggingFace: la carpeta de la app tiene que ser autocontenida y
# despues de la primera descarga nada mas debe necesitar red.
AUXILIARES = [
    ("CIDAS/clipseg-rd64-refined", "selecting by words"),
    ("facebook/sam2.1-hiera-tiny", "sharpening the edge"),
]
# los dos repos publican los mismos pesos en .bin y en .safetensors; bajar
# ambos duplicaba 600 MB para nada
AUX_PATRONES = ["*.json", "*.txt", "*.safetensors", "*.model"]


def ruta_aux(ruta_modelos: str) -> str:
    return os.path.join(ruta_modelos, "aux")


# lo que hace falta para inferencia; se deja fuera cualquier cosa suelta del repo
PATRONES = [
    "transformer/*", "text_encoder/*", "vae/*",
    "processor/*", "scheduler/*", "*.json",
]


# ------------------------------------------------------------------ prompt

def construir_prompt(n_persona: int, con_pose: bool, con_escena: bool, texto: str,
                     con_estilo: bool = False, estilo_modo: str = "look") -> str:
    """Assemble the scaffolding around the user's text.

    Each reference gets its job spelled out, because the model will otherwise
    borrow whatever it likes from each one. Two clauses matter in particular:

      - a skeleton says where the limbs go, nothing about build. Without saying
        so, the body gets invented; the proportions are pinned to the person.
    Each reference does exactly one job, so they compose without fighting:
    person gives the face, pose gives the posture, style gives the photographic
    treatment, scene gives the place and the wardrobe. `estilo_modo="todo"` is
    the escape hatch for when one photo should define the whole look, at the
    cost of making the scene slot redundant.
    """
    partes = []
    # Lo que se dice DESPUES del encargo del usuario. Va aparte porque el sitio
    # es el argumento: en este modelo lo ultimo pesa mas, y una identidad
    # enterrada al principio la pisa cualquier cosa que venga detras.
    cola = ""
    idxs = ", ".join(f"<image{k+1}>" for k in range(n_persona)) if n_persona else ""
    i = n_persona
    if n_persona:
        partes.append(f"{idxs} show the subject. The subject's face and identity must match {idxs} "
                      f"exactly: "
                      f"same facial structure, same features, same skin tone.")
    if con_pose:
        i += 1
        partes.append(f"<image{i}> is an OpenPose skeleton. The body posture, limb positions and "
                      f"head tilt must follow that skeleton exactly.")
        if n_persona:
            partes.append(f"The subject's body proportions, build and height stay those of {idxs}; "
                          f"the skeleton gives only the pose.")
            # Mismo arreglo que la escena, que aqui faltaba. El orden era
            # identidad, pose, proporciones y luego el texto del usuario, asi
            # que lo ULTIMO que lee el modelo es el encargo y no de quien es la
            # cara. Medido el 2026-09-23 sobre tres encuadres: sin esta linea
            # la cara se despega y la complexion adelgaza. Va en positivo y al
            # final, porque lo ultimo es lo que manda.
            cola = (f"The one person in the result is the subject from {idxs}: the "
                    f"same face, the same beard and hair, the same build and the same "
                    f"weight, only placed in that posture.")
    if con_estilo:
        i += 1
        if estilo_modo == "look":
            partes.append(f"<image{i}> is a style reference. Take from it only the photographic "
                          f"treatment: the colour grading, the contrast, the grain, the quality "
                          f"of light and the lens character. Its subject, its setting and its "
                          f"composition stay out of the result.")
        else:
            partes.append(f"<image{i}> is the reference for the look of the photograph. Reproduce "
                          f"its clothing, its location and background, its lighting, its colour "
                          f"grading and its overall mood. The person in the result is the one from "
                          f"{idxs or 'the first reference'}, wearing that clothing in that place.")
    if con_escena:
        i += 1
        partes.append(f"<image{i}> supplies the setting, the wardrobe, the framing and the lighting, "
                      f"which must be reproduced as they are. "
                      f"The output is one photograph of a single person.")
        if n_persona:
            # Medido el 2026-09-21: con una escena que ya tiene a alguien dentro, el
            # modelo devuelve A ESA PERSONA. La clausula de identidad esta al
            # principio del prompt y la escena, mas cerca del final, le gana. Se
            # repite la identidad despues de la escena, en positivo, porque lo
            # ultimo que se lee es lo que manda.
            # Esta linea existe desde el 2026-09-21 por recencia, pero estaba
            # en `partes`, o sea ANTES del encargo del usuario: el arreglo
            # quedo a medias y lo ultimo seguia siendo el texto. Ahora va
            # donde dice su propio comentario que tiene que ir.
            cola = (f"The one person in the result is the subject from {idxs}, with "
                    f"that subject's face, hair and build, standing in that setting "
                    f"and wearing that wardrobe.")
    return (" ".join(partes) + " " + texto.strip() + " " + cola).strip()


class Cancelado(Exception):
    """Alguien pulso Stop. No es un fallo: es la respuesta pedida."""


# Lo que esta pasando dentro de la pipeline, para que la UI lo cuente. Un dict
# plano y un Event bastan: hay un solo trabajo a la vez, protegido por el lock
# de la app.
PROGRESO: dict = {"activo": False, "paso": 0, "total": 0, "empezo": 0.0,
                  "primer_paso": 0.0}
PARAR = threading.Event()


def cancelar() -> None:
    PARAR.set()


def progreso() -> dict:
    """Paso actual y una estimacion de lo que falta, medida sobre la marcha."""
    p = dict(PROGRESO)
    # el ritmo se mide desde el PRIMER paso, no desde que se monto el trabajo:
    # antes del bucle esta la codificacion del texto, que en una tarjeta con
    # offload tarda lo suyo y hacia que la cuenta atras empezara disparatada
    if p["activo"] and p["paso"] > 1 and p["primer_paso"]:
        por_paso = (time.time() - p["primer_paso"]) / (p["paso"] - 1)
        p["restante"] = max(0, round((p["total"] - p["paso"]) * por_paso))
    else:
        p["restante"] = None
    return p


def _vigilante(total: int):
    """El callback que diffusers llama al final de cada paso."""
    PARAR.clear()
    PROGRESO.update(activo=True, paso=0, total=int(total), empezo=time.time(),
                    primer_paso=0.0)

    def cb(tuberia, paso, tiempo, kw):
        PROGRESO["paso"] = int(paso) + 1
        if PROGRESO["paso"] == 1:
            PROGRESO["primer_paso"] = time.time()
        if PARAR.is_set():
            raise Cancelado()
        return kw
    return cb


def _fin():
    PROGRESO.update(activo=False, paso=0, total=0, primer_paso=0.0)
    # El asignador de PyTorch se queda con lo que libera, asi que entre una
    # imagen y la siguiente la tarjeta sigue ocupada aunque aqui no pase nada y
    # el escritorio no recupera nada. Devolverlo cuesta unos milisegundos --
    # la siguiente generacion vuelve a reservar -- y es lo que hace que la
    # maquina se pueda usar mientras esta app esta abierta.
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def avisos_de_uso(n_persona: int, con_escena: bool,
                  espera_persona: bool = True) -> list[str]:
    """Lo que conviene decir antes de generar. En ingles: lo lee el usuario."""
    a = []
    if con_escena and n_persona > 1:
        a.append("With a scene, use ONE photo of the person. Several are read as several "
                 "different people, and several people end up in the picture.")
    if espera_persona and n_persona == 0:
        # solo donde el caso tiene ranura de persona: decirselo a quien eligio
        # texto a imagen es informarle de lo que acaba de pedir
        a.append("No person photo, so this is text to image and there is no identity to "
                 "carry over.")
    return a


# ------------------------------------------------------------------ pesos

class Descarga:
    """Estado compartido para que la UI pueda mostrar el avance."""

    def __init__(self):
        self.activa = False
        self.bytes = 0
        self.total = 0
        self.mensaje = ""
        self.error = ""
        self.lista = False


def _tamano_remoto() -> int:
    from huggingface_hub import HfApi
    try:
        info = HfApi().model_info(REPO, files_metadata=True)
        return sum((s.size or 0) for s in info.siblings
                   if s.rfilename.split("/")[0] in ("transformer", "text_encoder", "vae",
                                                    "processor", "scheduler")
                   or s.rfilename.endswith(".json"))
    except Exception:
        return 33 * 1024 ** 3


def tamano_local(ruta: str) -> int:
    t = 0
    for base, _, files in os.walk(ruta):
        for f in files:
            try:
                t += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    return t


def descargar(ruta: str, estado: Descarga) -> None:
    """Baja los pesos. Reanudable: huggingface_hub salta lo que ya esta."""
    from huggingface_hub import snapshot_download

    estado.activa, estado.error, estado.mensaje = True, "", "checking the size..."
    os.makedirs(ruta, exist_ok=True)
    estado.total = _tamano_remoto()

    parar = threading.Event()

    def vigilar():
        while not parar.is_set():
            estado.bytes = tamano_local(ruta)
            time.sleep(2)

    hilo = threading.Thread(target=vigilar, daemon=True)
    hilo.start()
    try:
        estado.mensaje = "downloading the weights..."
        snapshot_download(repo_id=REPO, local_dir=ruta, allow_patterns=PATRONES,
                          max_workers=4)

        # los dos pequenos, al lado y no en el cache del usuario
        aux = ruta_aux(ruta)
        os.makedirs(aux, exist_ok=True)
        for repo, para in AUXILIARES:
            estado.mensaje = f"downloading {repo.split('/')[-1]} — {para}..."
            try:
                snapshot_download(repo_id=repo, cache_dir=aux,
                                  allow_patterns=AUX_PATRONES, max_workers=4)
            except Exception as e:
                # no son imprescindibles para generar: si fallan, la app arranca
                # igual y lo dice cuando alguien pida una mascara
                estado.mensaje = f"warning: could not download {repo} ({type(e).__name__})"

        estado.lista = True
        estado.mensaje = "weights ready"
    except Exception as e:
        estado.error = str(e)
        estado.mensaje = "the download failed"
    finally:
        parar.set()
        estado.bytes = tamano_local(ruta)
        estado.activa = False


def pesos_completos(ruta: str) -> bool:
    need = [os.path.join(ruta, d) for d in ("transformer", "text_encoder", "vae", "processor")]
    if not all(os.path.isdir(d) for d in need):
        return False
    # heuristica: el text encoder son ~17 GB repartidos en shards
    return tamano_local(ruta) > 25 * 1024 ** 3


# ------------------------------------------------------------------ vram

def vram_ocupada_por_otros(umbral_gb: float = 1.5) -> tuple[float, list[str]]:
    """(GB en uso, procesos que la ocupan) segun nvidia-smi.

    Arrancar con la VRAM a medias es la forma mas facil de que esto parezca
    colgado: la utilizacion marca 100%, el consumo se queda bajo y no avanza,
    porque el asignador esta moviendo pesos en vez de calcular. Vale la pena
    avisar antes que dejar al usuario mirando una barra parada.
    """
    import subprocess
    try:
        usada = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=6).stdout.strip().splitlines()[0]
        gb = int(usada) / 1024
        if gb < umbral_gb:
            return gb, []
        procs = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=6).stdout.strip().splitlines()
        return gb, [p.strip() for p in procs if p.strip()]
    except Exception:
        return 0.0, []


def estado_vram() -> dict:
    """Lo que hay en la tarjeta ahora mismo, separando lo nuestro de lo ajeno.

    Torch sabe lo que ha reservado este proceso; nvidia-smi sabe el total. La
    diferencia es lo que ocupa cualquier otra cosa, y es el numero que de
    verdad decide si una generacion va a ir o a arrastrarse.
    """
    import subprocess
    fuera = {"hay": False}
    try:
        campos = ("memory.used,memory.total,utilization.gpu,power.draw,"
                  "temperature.gpu,power.limit,"
                  "clocks_throttle_reasons.sw_thermal_slowdown,"
                  "clocks_throttle_reasons.hw_thermal_slowdown,name")
        linea = subprocess.run(
            ["nvidia-smi", f"--query-gpu={campos}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=6).stdout.strip().splitlines()[0]
        (usada, total, util, vatios, grados, tope_w,
         sw_term, hw_term, nombre) = [c.strip() for c in linea.split(",")]

        def _num(x, f=float):
            try:
                return f(x)
            except Exception:
                return None

        # nvidia-smi responde "Active" o "Not Active", y "Not Active" contiene
        # "active": buscar la subcadena marcaba estrangulamiento siempre
        recorta = any(x.strip().lower() == "active" for x in (sw_term, hw_term))
        fuera.update(hay=True, usada_gb=round(int(usada) / 1024, 1),
                     total_gb=round(int(total) / 1024, 1), utilizacion=int(util),
                     vatios=_num(vatios, lambda x: round(float(x))),
                     tope_vatios=_num(tope_w, lambda x: round(float(x))),
                     grados=_num(grados, int), estrangulada=recorta,
                     tarjeta=nombre)
    except Exception:
        return fuera

    try:
        import torch
        if torch.cuda.is_available():
            nuestra = torch.cuda.memory_reserved() / 1024 ** 3
            fuera["nuestra_gb"] = round(nuestra, 1)
            fuera["ajena_gb"] = max(0.0, round(fuera["usada_gb"] - nuestra, 1))
    except Exception:
        pass
    return fuera


def vaciar_cache() -> dict:
    """Devolver a la tarjeta lo que torch tiene reservado y no usa."""
    antes = estado_vram().get("usada_gb")
    try:
        import gc

        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    despues = estado_vram().get("usada_gb")
    return {"antes_gb": antes, "despues_gb": despues,
            "liberado_gb": round((antes or 0) - (despues or 0), 1)}


def esperar_a_que_enfrie(limite_c: int = 80, maximo_s: int = 120) -> dict:
    """Wait until the card drops below `limite_c`, up to `maximo_s` seconds.

    Not protection from damage: the firmware already throttles at its own
    limit and nothing here can override that. This is for the unattended case
    -- a long batch at three in the morning -- where letting the card breathe
    between images keeps it out of thermal throttling and the whole run
    finishes sooner than it would while being slowed down.
    """
    import time as _t
    inicio = _t.time()
    e = estado_vram()
    if not e.get("hay") or e.get("grados") is None:
        return {"esperado_s": 0, "grados": None}
    partida = e["grados"]
    while e.get("grados", 0) >= limite_c and (_t.time() - inicio) < maximo_s:
        _t.sleep(3)
        e = estado_vram()
    return {"esperado_s": round(_t.time() - inicio), "grados_antes": partida,
            "grados": e.get("grados"), "limite": limite_c}


# ------------------------------------------------------------------ pipeline

class Motor:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.pipe = None
        self.vae_actual = "stock"
        self.cargando = False
        self.error = ""
        self._lora = None          # (ruta, fuerza) actualmente aplicada
        self.atencion = "sdpa"
        self._cb = None            # si la pipeline admite callback_on_step_end
        self._sched_base = None    # the scheduler config the weights shipped with
        self._muestreo = "base"    # which MUESTREO entry is installed right now

    @property
    def listo(self) -> bool:
        return self.pipe is not None

    # Measured on 2026-09-23, warm, 1 MP, same seed. Against base at 16 steps:
    # generation 28 s -> 20 s, and a black-and-white edit that has to keep a
    # face 29 s -> 19 s, with the face indistinguishable. At its advertised 4
    # steps it returns ghost hands whichever shift_terminal it is given, so the
    # number that ships is 8 and it is not a knob.
    TURBO_PASOS = 8
    TURBO_ARCHIVO = "turbo.safetensors"

    def _poner_techo_vram(self) -> None:
        """Cap what this process may allocate, below the card's real total.

        Two blue screens on 2026-09-23, same bugcheck and the same four
        parameters, both while pushing a 24 GB card against its wall. The
        driver breaks under an allocation it cannot serve and, with the
        hypervisor in the path, takes the kernel down instead of resetting
        itself. A watcher thread cannot prevent that: cancellation lands
        between denoising steps and the spike happens inside one.

        The allocator can. Past this fraction PyTorch raises
        `torch.cuda.OutOfMemoryError` at the moment of the allocation, which is
        an exception the app catches and reports, and the machine stays up.

        It does not cover what the driver reserves outside this process, which
        is why the profile leaves 4 GB rather than shaving the last hundred
        megabytes.
        """
        limite = float(self.cfg.get("vram_limite_gb") or 0)
        if limite <= 0:
            return
        try:
            import torch
            if not torch.cuda.is_available():
                return
            total = torch.cuda.get_device_properties(0).total_memory / 2**30
            frac = min(0.98, max(0.1, limite / total))
            torch.cuda.set_per_process_memory_fraction(frac, 0)
            self.techo_vram = round(total * frac, 1)
        except Exception as e:
            # sin techo se puede trabajar; callarselo no
            print(f"  [vram] no se pudo poner el techo: {type(e).__name__}: {e}",
                  flush=True)

    def turbo_disponible(self) -> bool:
        """True when the turbo adapter is sitting in modelos/.

        It lives there and not in loras/ because it is an engine setting, like
        the alternative VAE: it changes how everything is made rather than
        adding a look, so it has no business in the effects list.
        """
        return os.path.exists(os.path.join(self.cfg["ruta_modelos"],
                                           self.TURBO_ARCHIVO))

    def vae_disponible(self) -> bool:
        """True when the alternative VAE weights are sitting in modelos/."""
        return os.path.exists(os.path.join(self.cfg["ruta_modelos"], "vae_hdr.safetensors"))

    def _pesos_vae(self, pipe, cual: str) -> str:
        """Load the chosen VAE weights into `pipe` before any offload hook exists.

        Doing this after enable_model_cpu_offload leaves tensors on CPU: with
        offload the weights belong to accelerate, and load_state_dict writes
        underneath its hooks. Measured the hard way.
        """
        if cual != "hdr":
            return "stock"
        ruta = os.path.join(self.cfg["ruta_modelos"], "vae_hdr.safetensors")
        if not os.path.exists(ruta):
            return "stock"
        try:
            from safetensors.torch import load_file
            sd = load_file(ruta)
            actual = pipe.vae.state_dict()
            sd = {k: v.to(dtype=actual[k].dtype) for k, v in sd.items()}
            pipe.vae.load_state_dict(sd, strict=True)
            del sd
            return "hdr"
        except Exception as e:
            self.aviso_vram = (self.aviso_vram + " " if self.aviso_vram else "") + \
                f"the HDR decoder could not be loaded ({type(e).__name__}), using the stock one"
            return "stock"

    def usar_offload(self, cual: str) -> str:
        """Where the weights live between calls. Swapping costs a reload.

        Measured warm at 1 MP: "model" 26 s, "none" 19 s. The 27% is paid for
        in 1.6 GB of resident weights, which is why it is not simply the
        default: without the offload, 2.25 MP with a reference no longer fits
        under the allocator ceiling and comes back as an error instead of an
        image.
        """
        cual = cual if cual in ("model", "none", "sequential") else "model"
        if cual == "sequential" and self.cfg.get("cuantizacion") in ("int4", "int8"):
            cual = "model"
        if self.cfg.get("offload") == cual:
            return cual
        self.cfg["offload"] = cual
        if self.pipe is not None:
            self.liberar()
            self.cargar()
        return cual

    def usar_vae(self, cual: str) -> str:
        """Pick the decoder. Returns the one actually in use.

        Switching with the model already mounted costs a reload, because the
        swap has to happen before the offload hooks are installed. Asking for
        the one already loaded costs nothing, which is the common case: every
        request asks, and almost every request already has what it wants.
        """
        cual = "hdr" if cual == "hdr" else "stock"
        if cual == "hdr" and not self.vae_disponible():
            cual = "stock"
        if self.pipe is None:
            self.cfg["vae"] = cual
            return cual
        if getattr(self, "vae_actual", "stock") == cual:
            return cual
        self.cfg["vae"] = cual
        self.liberar()
        self.cargar()
        return getattr(self, "vae_actual", "stock")

    def cargar(self) -> None:
        if self.pipe is not None or self.cargando:
            return
        self.cargando, self.error = True, ""
        self.aviso_vram = ""
        try:
            gb, procs = vram_ocupada_por_otros()
            if gb >= 1.5:
                self.aviso_vram = (
                    f"{gb:.1f} GB of VRAM are already in use by another process"
                    + (f" ({len(procs)} found)" if procs else "")
                    + ". Close it first: starting with the memory half full makes "
                      "generation crawl without any error message.")
            import torch
            from diffusers import QwenImage21Pipeline

            self._poner_techo_vram()

            # Un config.json de antes puede traer todavia "sequential", y con
            # nf4 eso no arranca: accelerate no mueve por capas lo que
            # bitsandbytes ya cuantizo. Se corrige aqui en vez de fallar con
            # un mensaje sobre tensores meta que no le dice nada a nadie.
            if (self.cfg.get("offload") == "sequential"
                    and self.cfg.get("cuantizacion") in ("int4", "int8")):
                print("  [offload] sequential no funciona con pesos cuantizados; "
                      "se usa 'model'", flush=True)
                self.cfg["offload"] = "model"

            dtype = {"bfloat16": torch.bfloat16,
                     "float16": torch.float16,
                     "float32": torch.float32}[self.cfg["dtype"]]
            ruta = self.cfg["ruta_modelos"]
            kwargs = {"torch_dtype": dtype}

            # Cuantizacion POR COMPONENTE. Medido el 2026-09-21 en 24 GB:
            #   transformer bf16 (14.2 GB) + text encoder bf16 (17.5 GB) = 31.7 GB,
            #   no caben juntos, de ahi el offload y sus ~40 s por llamada.
            # Cuantizar solo el text encoder los hace caber residentes: el DiT
            # se queda intacto (es donde vive la calidad de imagen) y el coste
            # cae sobre la comprension del prompt, que lo aguanta mucho mejor.
            cuant = self.cfg.get("cuantizacion", "none")          # transformer
            cuant_te = self.cfg.get("cuantizacion_te", "none")    # text encoder
            mapa = {}
            if cuant in ("int8", "int4"):
                mapa["transformer"] = cuant
            if cuant_te in ("int8", "int4"):
                mapa["text_encoder"] = cuant_te
            if mapa:
                from diffusers import PipelineQuantizationConfig
                from diffusers import BitsAndBytesConfig as DiffBnb
                from transformers import BitsAndBytesConfig as TrfBnb

                def _cfg(clase, modo):
                    if modo == "int8":
                        return clase(load_in_8bit=True)
                    return clase(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_compute_dtype=dtype)

                quant_mapping = {}
                if "transformer" in mapa:
                    quant_mapping["transformer"] = _cfg(DiffBnb, mapa["transformer"])
                if "text_encoder" in mapa:
                    quant_mapping["text_encoder"] = _cfg(TrfBnb, mapa["text_encoder"])
                kwargs["quantization_config"] = PipelineQuantizationConfig(
                    quant_mapping=quant_mapping)

            pipe = QwenImage21Pipeline.from_pretrained(ruta, **kwargs)

            # antes de cualquier gancho de offload: despues ya no vale
            self.vae_actual = self._pesos_vae(pipe, self.cfg.get("vae", "hdr"))

            # SageAttention es opcional a proposito. Diffusers trae el backend
            # registrado, pero el paquete no: PyPI solo publica la 1.x (kernels
            # Triton, que en Windows no viene) y la 2.x hay que compilarla. Si
            # alguien la instala a mano, se aprovecha; si no, SDPA y a seguir.
            self.atencion = "sdpa"
            if self.cfg.get("backend") == "cuda":
                try:
                    import sageattention  # noqa: F401
                    pipe.transformer.set_attention_backend("sage")
                    self.atencion = "sage"
                except Exception:
                    pass

            # El pico de memoria a 4 MP no es la difusion: es el decodificado
            # del VAE al final. Medido hoy, 19.2 GB durante los pasos y 24.0 GB
            # justo en el decode. Trocear ataca ese pico y no toca el resto.
            try:
                pipe.vae.enable_tiling()
                pipe.vae.enable_slicing()
            except Exception:
                pass

            off = self.cfg.get("offload", "none")
            backend = self.cfg.get("backend", "cpu")
            if off == "sequential":
                pipe.enable_sequential_cpu_offload()
            elif off == "model":
                pipe.enable_model_cpu_offload()
            elif backend == "cuda":
                pipe.to("cuda")
            elif backend == "mps":
                pipe.to("mps")

            self.pipe = pipe
            self._sched_base, self._muestreo = None, "base"
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
        finally:
            self.cargando = False

    # What ComfyUI offers in its sampler and scheduler dropdowns is, for this
    # model, a handful of fields on FlowMatchEulerDiscreteScheduler. They cost
    # no memory and no time, which makes them the only lever left that can
    # change a result without making it slower. Only one sigma schedule may be
    # on at a time; diffusers asserts that.
    # Measured on 2026-09-23, same prompt and seed at 16 steps, all five that
    # FlowMatchEuler exposes. Only two survived:
    #
    #   karras, exponential  smeared, unusable. Their sigma remapping fights
    #                        this model's use_dynamic_shifting, which is on.
    #   beta                 needs scipy, which is not a dependency here, so
    #                        it raised ImportError and fell back to base.
    #   ancestral            works, and trades prompt adherence for texture:
    #                        far more skin detail on a face (sharpness 7.5
    #                        against 3.8) but it dropped a background the
    #                        prompt asked for, and it was the flatter of the
    #                        two on a lettering job. An option, not a default.
    #
    # Shipping the three that break would be shipping three traps, so they are
    # not here. The mechanism still refuses gracefully if one is asked for.
    MUESTREO = {
        "base": {},
        "ancestral": {"stochastic_sampling": True},
        # what the turbo LoRA ships in its own scheduler config. Judging a
        # 4-step adapter under the 30-step model's terminal shift is not a
        # measurement of the adapter, it is a measurement of the mismatch.
        "turbo": {"shift_terminal": None},
    }

    def ajustar_muestreo(self, nombre: str) -> str:
        """Rebuild the scheduler with one of MUESTREO. Returns what was applied.

        Always rebuilt from the config the weights shipped with, never from
        the running one, so the flags cannot pile up across calls.
        """
        if self.pipe is None:
            return ""
        cambios = self.MUESTREO.get(nombre)
        if cambios is None:
            return ""
        if getattr(self, "_muestreo", None) == nombre:
            return nombre
        if getattr(self, "_sched_base", None) is None:
            self._sched_base = dict(self.pipe.scheduler.config)
        cfg = dict(self._sched_base)
        cfg.update(cambios)
        try:
            self.pipe.scheduler = type(self.pipe.scheduler).from_config(cfg)
            self._muestreo = nombre
            return nombre
        except Exception as e:
            # a rejected combination leaves the shipped scheduler in place,
            # which is the one that is known to work
            print(f"  [sampling] {nombre} refused: {type(e).__name__}: {e}", flush=True)
            self.pipe.scheduler = type(self.pipe.scheduler).from_config(self._sched_base)
            self._muestreo = "base"
            return ""

    def generar(self, *, personas, pose, escena, texto, steps, seed,
                estilo=None, estilo_modo="look", cfg=1.0, negativo="",
                ancho=None, alto=None, res=1024, transparencia=False):
        """personas/pose/escena son PIL.Image o None. Devuelve (PIL.Image, prompt).

        ancho/alto explicitos mandan sobre el ratio derivado. Si van en None, la
        pipeline saca la proporcion de la ULTIMA referencia (image[-1]), no de la
        primera: con persona -> pose -> escena, manda la escena.
        """
        import torch

        if self.pipe is None:
            raise RuntimeError(self.error or "the model is not loaded")

        refs = list(personas)
        if pose is not None:
            refs.append(pose)
        if estilo is not None:
            refs.append(estilo)
        if escena is not None:
            refs.append(escena)

        prompt = construir_prompt(len(personas), pose is not None, escena is not None, texto,
                                  con_estilo=estilo is not None, estilo_modo=estilo_modo)
        if transparencia:
            # La forma que publica la ficha del modelo: envuelve, no anade al
            # final. Medido el 2026-09-22 con la misma semilla, 68.4% de alfa
            # frente al 65.7% de la version propia que habia aqui. La
            # diferencia es pequena, pero es la del autor del modelo y no sale
            # peor, asi que no hay razon para inventarse otra.
            # ...y despues, el sujeto opaco, porque lo ultimo manda. Medido el
            # 2026-09-23: sin esta ultima frase, una foto de referencia con el
            # fondo abarrotado sale al 0.7% de opacidad -- es decir, entera
            # transparente, sujeto incluido. Es el mismo fallo que el noir, que
            # devolvia una foto negra al pedir "la mayor parte en sombra": hay
            # que nombrar lo que SI se ve, no solo lo que no.
            prompt = ("This is an RGBA image with transparency. " + prompt.strip()
                      + " The image has an alpha channel and the background is "
                        "transparent. The person is fully opaque, solid and "
                        "completely visible, filling the frame.")

        gen = torch.Generator(device="cpu").manual_seed(int(seed))
        kw = dict(prompt=prompt, num_inference_steps=int(steps),
                  true_cfg_scale=float(cfg), generator=gen,
                  output_resolution=int(res))
        # A negative prompt only exists above 1.0: at 1.0 the second forward
        # pass is not run, so passing one would cost nothing and do nothing,
        # which is worse than not offering it.
        if float(cfg) > 1.0 and negativo.strip():
            kw["negative_prompt"] = negativo.strip()
        if refs:
            kw["image"] = refs
        if ancho and alto:
            kw["width"], kw["height"] = int(ancho), int(alto)
        elif not refs:
            kw["width"] = kw["height"] = int(res)

        if self._admite_callback():
            kw["callback_on_step_end"] = _vigilante(steps)
        try:
            out = self.pipe(**kw)
        finally:
            _fin()
        return out.images[0], prompt

    def _admite_callback(self) -> bool:
        """No todas las pipelines lo aceptan; se comprueba una vez."""
        if self._cb is None:
            import inspect
            try:
                self._cb = ("callback_on_step_end"
                            in inspect.signature(self.pipe.__call__).parameters)
            except Exception:
                self._cb = False
        return self._cb

    def editar(self, *, imagen, texto, steps, seed, res=1024,
               referencias=None, ancho=None, alto=None, modo="material"):
        """Plain edit of one image: no identity scaffolding.

        Used by the inpainting path, where `imagen` is already the crop around
        the mask and the whole frame is meant to be regenerated. Extra
        `referencias` (a person, a garment) ride along after it.
        """
        import torch

        if self.pipe is None:
            raise RuntimeError(self.error or "the model is not loaded")

        refs = [imagen] + list(referencias or [])
        prompt = texto.strip()
        if len(refs) > 1 and modo == "estilo":
            # aqui la referencia no dice de que esta hecha una cosa: dice como
            # se pinta todo. Se nombra lo que se conserva y lo que se sustituye,
            # porque lo que no se nombra el modelo lo negocia por su cuenta.
            extras = ", ".join(f"<image{i+2}>" for i in range(len(refs) - 1))
            prompt = (f"<image1> is the picture whose content is kept: the same subject, "
                      f"the same pose, the same composition and the same framing. "
                      f"{extras} is the style reference. Redraw everything in <image1> in "
                      f"the visual language of {extras}: its medium and its surface, its "
                      f"brushwork and mark-making, its texture, its palette, and the way it "
                      f"draws edges, light and shadow. "
                      + (f"{prompt} " if prompt else "")
                      + f"The result shows what <image1> shows, made the way {extras} was "
                      f"made.")
        elif len(refs) > 1 and modo == "libre":
            # Edicion por instruccion, que es lo que este modelo sabe hacer y
            # esta app no usaba: los demas caminos recortan una region y la
            # pegan de vuelta. Aqui va la foto entera y el modelo decide donde
            # tocar.
            #
            # La forma la fija el prompt de sistema que el propio Space de
            # Viggle usa para reescribir instrucciones de edicion, cuyas reglas
            # son tres y las tres importan:
            #
            #   - la operacion primero, lo que se conserva despues;
            #   - la conservacion en generico, nunca enumerada;
            #   - y la razon: "say what stays, without repainting it" --
            #     describir en concreto lo que no cambia hace que el modelo lo
            #     REGENERE.
            #
            # Aqui estaba al reves y enumerado -- "the same place, the same
            # light, the same framing" -- y el resultado era exactamente el
            # fallo que ese documento llama over-describing: devolvia el sitio,
            # la luz y el encuadre de la referencia en vez de editar el
            # destino.
            extras = ", ".join(f"<image{i+2}>" for i in range(len(refs) - 1))
            una = len(refs) == 2
            prompt = (f"Edit <image1>. {prompt} "
                      f"{extras} {'is reference material' if una else 'are reference material'}, "
                      f"not the picture being edited. "
                      f"Everything else in <image1> is unchanged.")
        elif modo == "estilo" and prompt:
            # una sola imagen y la tecnica en palabras. Lo que se conserva va
            # delante y la manera de pintarlo al final, porque en este modelo
            # lo ultimo es lo que mas pesa.
            prompt = (f"Keep what <image1> shows: the same subject, the same pose, "
                      f"the same composition and the same framing. Change only how "
                      f"the picture is made. Redraw all of it this way: {prompt} "
                      f"Nothing of the original photograph's surface remains.")
        elif len(refs) > 1:
            extras = ", ".join(f"<image{i+2}>" for i in range(len(refs) - 1))
            una = len(refs) == 2
            # "show what to put there" era demasiado vago. La regla medida en
            # este proyecto es que una referencia se ignora si el prompt no
            # nombra QUE hay que tomar de ella, asi que se nombra.
            # Medido el 2026-09-22: decir que la referencia "debe aparecer en la
            # region" hace que el modelo la copie entera, fondo incluido. La
            # referencia describe COMO es la cosa que pide el texto, no que
            # pegar: por eso va subordinada al prompt y no al reves.
            prompt = (f"<image1> is the region being edited. What is built there is what "
                      f"this text describes: {prompt.strip()} "
                      f"{extras} {'shows' if una else 'show'} how it should look — take "
                      f"the colour, the material and the pattern from "
                      f"{'it' if una else 'them'}, and nothing else. The result keeps the "
                      f"shape, the lighting, the shadows and the perspective of <image1>.")

        gen = torch.Generator(device="cpu").manual_seed(int(seed))
        kw = dict(prompt=prompt, image=refs, num_inference_steps=int(steps),
                  true_cfg_scale=1.0, generator=gen, output_resolution=int(res))
        if ancho and alto:
            kw["width"], kw["height"] = int(ancho), int(alto)
        if self._admite_callback():
            kw["callback_on_step_end"] = _vigilante(steps)
        try:
            out = self.pipe(**kw)
        finally:
            _fin()
        return out.images[0], prompt

    # ------------------------------------------------------------------ lora

    def aplicar_lora(self, ruta: str | None, fuerza: float = 1.0,
                     turbo: bool = False) -> None:
        """Attach the engine and user adapters, swap them, or detach them.

        Two slots, because they answer different questions: turbo changes how
        fast everything is made, and the user's LoRA changes what it looks
        like, so asking for one must not silently drop the other. Reloading
        costs seconds, so the current (path, strength, turbo) is remembered and
        a repeat is a no-op.
        """
        if self.pipe is None:
            return
        objetivo = (ruta, float(fuerza) if ruta else 0.0, bool(turbo))
        if objetivo == self._lora:
            return
        try:
            if self._lora is not None:
                self.pipe.unload_lora_weights()
                self._lora = None

            nombres: list[str] = []
            pesos: list[float] = []
            if turbo and self.turbo_disponible():
                self.pipe.load_lora_weights(self.cfg["ruta_modelos"],
                                            weight_name=self.TURBO_ARCHIVO,
                                            adapter_name="turbo")
                nombres.append("turbo")
                pesos.append(1.0)
            if ruta:
                self.pipe.load_lora_weights(os.path.dirname(ruta),
                                            weight_name=os.path.basename(ruta),
                                            adapter_name="user")
                nombres.append("user")
                pesos.append(float(fuerza))
            if nombres:
                self.pipe.set_adapters(nombres, adapter_weights=pesos)
            self._lora = objetivo
        except Exception as e:
            # a LoRA for another architecture is a user error, not a crash:
            # report it and carry on with the base model
            self._lora = None
            raise RuntimeError(f"could not apply the LoRA: {e}") from e

    def liberar(self) -> None:
        """Drop the pipeline and give the VRAM back. The next call reloads it."""
        if self.pipe is None:
            return
        try:
            self.pipe.to("cpu")
        except Exception:
            pass
        self.pipe = None
        self._lora = None
        self._sched_base, self._muestreo = None, "base"
        try:
            import gc

            import torch
            gc.collect()
            torch.cuda.empty_cache()
        except Exception:
            pass
