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


def dimensiones(ratio: str, megapixeles: float) -> tuple[int, int]:
    """Ancho y alto para un ratio y un presupuesto de pixeles, en multiplos de 32
    (que es lo que pide el VAE 16x con bloques de 2x2)."""
    import math
    r = RATIOS.get(ratio, 1.0)
    area = megapixeles * 1024 * 1024
    w = round(math.sqrt(area * r) / 32) * 32
    h = round(math.sqrt(area / r) / 32) * 32
    return max(256, w), max(256, h)


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
            partes.append(f"The one person in the result is the subject from {idxs}, with that "
                          f"subject's face, hair and build, standing in that setting and wearing "
                          f"that wardrobe.")
    return (" ".join(partes) + " " + texto.strip()).strip()


def avisos_de_uso(n_persona: int, con_escena: bool) -> list[str]:
    a = []
    if con_escena and n_persona > 1:
        a.append("Con escena conviene UNA sola foto de la persona: con varias el modelo las lee "
                 "como sujetos distintos y mete varias personas en la imagen.")
    if n_persona == 0:
        a.append("Sin foto de persona esto es texto a imagen; no hay identidad que preservar.")
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

    estado.activa, estado.error, estado.mensaje = True, "", "consultando tamano..."
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
        estado.mensaje = "descargando pesos..."
        snapshot_download(repo_id=REPO, local_dir=ruta, allow_patterns=PATRONES,
                          max_workers=4)
        estado.lista = True
        estado.mensaje = "pesos listos"
    except Exception as e:
        estado.error = str(e)
        estado.mensaje = "fallo la descarga"
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

    @property
    def listo(self) -> bool:
        return self.pipe is not None

    def vae_disponible(self) -> bool:
        """True when the alternative VAE weights are sitting in modelos/."""
        return os.path.exists(os.path.join(self.cfg["ruta_modelos"], "vae_hdr.safetensors"))

    def usar_vae(self, cual: str) -> str:
        """Swap the VAE weights in place. Returns which one is now loaded.

        Loading the state dict into the mounted VAE costs a second off disk;
        building a second pipeline would cost the whole model again.
        """
        if self.pipe is None:
            return getattr(self, "vae_actual", "stock")
        cual = "hdr" if cual == "hdr" else "stock"
        if getattr(self, "vae_actual", "stock") == cual:
            return cual
        import torch
        from safetensors.torch import load_file
        ruta = (os.path.join(self.cfg["ruta_modelos"], "vae_hdr.safetensors") if cual == "hdr"
                else os.path.join(self.cfg["ruta_modelos"], "vae",
                                  "diffusion_pytorch_model.safetensors"))
        if not os.path.exists(ruta):
            return getattr(self, "vae_actual", "stock")
        sd = load_file(ruta)
        destino = self.pipe.vae
        # el archivo HDR viene en fp16 y el VAE montado puede estar en bf16:
        # se castea a lo que ya tiene cada tensor, no al reves
        sd = {k: v.to(dtype=destino.state_dict()[k].dtype) for k, v in sd.items()}
        destino.load_state_dict(sd, strict=True)
        del sd
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
        self.vae_actual = cual
        return cual

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
            self.vae_actual = "stock"
            if self.cfg.get("vae", "stock") == "hdr":
                self.usar_vae("hdr")
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
        finally:
            self.cargando = False

    def generar(self, *, personas, pose, escena, texto, steps, seed,
                estilo=None, estilo_modo="look",
                ancho=None, alto=None, res=1024, transparencia=False):
        """personas/pose/escena son PIL.Image o None. Devuelve (PIL.Image, prompt).

        ancho/alto explicitos mandan sobre el ratio derivado. Si van en None, la
        pipeline saca la proporcion de la ULTIMA referencia (image[-1]), no de la
        primera: con persona -> pose -> escena, manda la escena.
        """
        import torch

        if self.pipe is None:
            raise RuntimeError(self.error or "el modelo no esta cargado")

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
            prompt += (" The subject is cut out on a fully transparent background. "
                       "Output a PNG image with an alpha channel.")

        gen = torch.Generator(device="cpu").manual_seed(int(seed))
        kw = dict(prompt=prompt, num_inference_steps=int(steps),
                  true_cfg_scale=1.0, generator=gen, output_resolution=int(res))
        if refs:
            kw["image"] = refs
        if ancho and alto:
            kw["width"], kw["height"] = int(ancho), int(alto)
        elif not refs:
            kw["width"] = kw["height"] = int(res)

        out = self.pipe(**kw)
        return out.images[0], prompt

    def editar(self, *, imagen, texto, steps, seed, res=1024,
               referencias=None, ancho=None, alto=None):
        """Plain edit of one image: no identity scaffolding.

        Used by the inpainting path, where `imagen` is already the crop around
        the mask and the whole frame is meant to be regenerated. Extra
        `referencias` (a person, a garment) ride along after it.
        """
        import torch

        if self.pipe is None:
            raise RuntimeError(self.error or "el modelo no esta cargado")

        refs = [imagen] + list(referencias or [])
        prompt = texto.strip()
        if len(refs) > 1:
            extras = ", ".join(f"<image{i+2}>" for i in range(len(refs) - 1))
            prompt = (f"<image1> is the region being edited. {extras} show what to put there. "
                      + prompt)

        gen = torch.Generator(device="cpu").manual_seed(int(seed))
        kw = dict(prompt=prompt, image=refs, num_inference_steps=int(steps),
                  true_cfg_scale=1.0, generator=gen, output_resolution=int(res))
        if ancho and alto:
            kw["width"], kw["height"] = int(ancho), int(alto)
        out = self.pipe(**kw)
        return out.images[0], prompt

    # ------------------------------------------------------------------ lora

    def aplicar_lora(self, ruta: str | None, fuerza: float = 1.0) -> None:
        """Attach a LoRA, swap it, or detach it. Cheap when nothing changes.

        Reloading the same adapter on every call would cost seconds, so the
        currently attached (path, strength) is remembered and a repeat is a
        no-op.
        """
        if self.pipe is None:
            return
        objetivo = (ruta, float(fuerza)) if ruta else None
        if objetivo == self._lora:
            return
        try:
            if self._lora is not None:
                self.pipe.unload_lora_weights()
                self._lora = None
            if objetivo:
                import os
                self.pipe.load_lora_weights(os.path.dirname(ruta),
                                            weight_name=os.path.basename(ruta),
                                            adapter_name="user")
                self.pipe.set_adapters(["user"], adapter_weights=[float(fuerza)])
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
        try:
            import gc

            import torch
            gc.collect()
            torch.cuda.empty_cache()
        except Exception:
            pass
