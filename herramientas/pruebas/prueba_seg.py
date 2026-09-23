import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from qwenstudio import segmentacion as SEG, inpaint as IN

from _fuentes import escena
src = escena("escena_cocina.png")
img = Image.open(src).convert("RGB")
t0=time.time(); SEG.cargar("cuda"); print(f"carga Florence: {time.time()-t0:.0f}s | err: {SEG._estado['error'] or 'ninguno'}")
if not SEG.disponible(): sys.exit(1)

for texto in ["the yellow sweater", "her face", "the hair"]:
    try:
        t0=time.time(); m = SEG.mascara(img, texto)
        px = sum(1 for v in m.getdata() if v>127)
        caja = IN.bbox_de_mascara(m)
        print(f"  '{texto:<20}' {time.time()-t0:5.1f}s  cubre {px*100/(m.width*m.height):5.1f}%  caja {caja}")
        m.save(rf"D:\QwenStudio\salidas\mask_{texto.replace(' ','_')}.png")
    except Exception as e:
        print(f"  '{texto}' FALLO: {type(e).__name__}: {e}")
