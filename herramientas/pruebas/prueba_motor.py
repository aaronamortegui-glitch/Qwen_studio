import json, os, sys, time, subprocess, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from qwenstudio.motor import Motor

cfg = json.load(open("config.json", encoding="utf-8"))
print("perfil:", cfg["nivel"], "|", cfg["dtype"], "| cuant", cfg["cuantizacion"], "| offload", cfg["offload"])

pico=[0]; stop=threading.Event()
def mon():
    while not stop.is_set():
        try:
            o=subprocess.run(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],
                             capture_output=True,text=True,timeout=5).stdout.strip().splitlines()[0]
            pico[0]=max(pico[0],int(o))
        except Exception: pass
        time.sleep(1)
threading.Thread(target=mon,daemon=True).start()

m = Motor(cfg)
t0=time.time(); m.cargar()
print(f"carga: {time.time()-t0:.0f}s | error: {m.error or 'ninguno'} | VRAM {pico[0]} MiB")
if not m.listo: sys.exit(1)

from _fuentes import persona
ref = Image.open(persona()).convert("RGB")
pico[0]=0; t0=time.time()
img, prompt = m.generar(personas=[ref], pose=None, escena=None,
    texto="A professional studio headshot, plain light gray background, soft even lighting.",
    res=1024, steps=25, seed=31337)
os.makedirs("salidas", exist_ok=True)
img.save("salidas/prueba_motor.png")
stop.set()
print(f"generacion: {time.time()-t0:.0f}s | VRAM pico {pico[0]} MiB | {img.size}")
print("prompt:", prompt[:130], "...")
