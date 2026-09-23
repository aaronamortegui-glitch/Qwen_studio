import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from qwenstudio import vision as V

cfg = json.load(open("config.json", encoding="utf-8"))
from _fuentes import escena
img = Image.open(escena("escena_cocina.png")).convert("RGB")

t0=time.time(); V.cargar(cfg["ruta_modelos"], "cuda", bits=4)
print(f"carga: {time.time()-t0:.0f}s | error: {V.error() or 'ninguno'}")
if not V.disponible(): sys.exit(1)
import subprocess
vram = subprocess.run(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader"],
                      capture_output=True,text=True).stdout.strip()
print("VRAM:", vram)
for tarea in ["prompt","describe","edit"]:
    t0=time.time(); r = V.preguntar(img, tarea)
    print(f"\n--- {tarea} ({time.time()-t0:.0f}s) ---\n{r[:600]}")
