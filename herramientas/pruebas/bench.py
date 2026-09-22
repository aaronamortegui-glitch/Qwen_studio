"""Compara configuraciones de carga midiendo carga, VRAM y tiempo por imagen."""
import json, os, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from qwenstudio.motor import Motor

REF = Image.open(r"D:\AIToolkit\AI-Toolkit\datasets\eliana_qwen21\Eliohwx_03.jpg").convert("RGB")
TXT = "A professional studio headshot, plain light gray background, soft even lighting."

base = json.load(open("config.json", encoding="utf-8"))

CONFIGS = [
 ("actual: bf16 + offload model",      {"cuantizacion":"none","cuantizacion_te":"none","offload":"model"}),
 ("TE int8, DiT bf16, SIN offload",    {"cuantizacion":"none","cuantizacion_te":"int8","offload":"none"}),
 ("TE nf4,  DiT bf16, SIN offload",    {"cuantizacion":"none","cuantizacion_te":"int4","offload":"none"}),
]

pico=[0]; stop=threading.Event()
def mon():
    while not stop.is_set():
        try:
            o=subprocess.run(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],
                             capture_output=True,text=True,timeout=5).stdout.strip().splitlines()[0]
            pico[0]=max(pico[0],int(o))
        except Exception: pass
        time.sleep(0.5)
threading.Thread(target=mon,daemon=True).start()

quiero = sys.argv[1] if len(sys.argv)>1 else None
for nombre, over in CONFIGS:
    if quiero and quiero not in nombre: continue
    cfg = dict(base); cfg.update(over)
    print(f"\n=== {nombre} ===", flush=True)
    pico[0]=0; t0=time.time()
    m = Motor(cfg); m.cargar()
    tc = time.time()-t0
    if not m.listo:
        print(f"  FALLO: {m.error[:200]}"); continue
    print(f"  carga {tc:.0f}s | VRAM tras cargar {pico[0]} MiB", flush=True)
    tiempos=[]
    for i in range(2):                     # la 1a incluye calentamiento
        pico[0]=0; t0=time.time()
        img,_ = m.generar(personas=[REF], pose=None, escena=None, texto=TXT,
                          steps=25, seed=31337+i, res=1024)
        tiempos.append(time.time()-t0)
        print(f"  gen {i+1}: {tiempos[-1]:6.1f}s | VRAM pico {pico[0]} MiB", flush=True)
    img.save(f"salidas/bench_{nombre.split(':')[0].replace(' ','_').replace(',','')}.png")
    print(f"  --> en caliente: {tiempos[-1]:.1f}s", flush=True)
    del m
    import gc, torch; gc.collect(); torch.cuda.empty_cache(); time.sleep(3)
stop.set()
