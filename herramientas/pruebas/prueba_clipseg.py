import sys, time, torch
from PIL import Image
from transformers import CLIPSegProcessor, CLIPSegForImageSegmentation

from _fuentes import escena
src = escena("escena_cocina.png")
img = Image.open(src).convert("RGB")
t0=time.time()
proc = CLIPSegProcessor.from_pretrained("CIDAS/clipseg-rd64-refined")
m = CLIPSegForImageSegmentation.from_pretrained("CIDAS/clipseg-rd64-refined").to("cuda").eval()
print(f"carga CLIPSeg: {time.time()-t0:.0f}s | params {round(sum(x.numel() for x in m.parameters())/1e6)} M")

frases = ["the yellow sweater", "her face", "the hair"]
t0=time.time()
inp = proc(text=frases, images=[img]*len(frases), padding=True, return_tensors="pt").to("cuda")
with torch.inference_mode():
    out = m(**inp).logits
print(f"inferencia: {time.time()-t0:.1f}s para {len(frases)} frases")
for i,f in enumerate(frases):
    logit = out[i] if out.dim()==3 else out
    pr = torch.sigmoid(logit).cpu()
    mask = Image.fromarray((pr.numpy()*255).astype("uint8")).resize(img.size, Image.BILINEAR)
    bin_ = mask.point(lambda v: 255 if v>127 else 0)
    px = sum(1 for v in bin_.getdata() if v>127)
    print(f"  '{f:<20}' cubre {px*100/(img.width*img.height):5.1f}%  caja {bin_.getbbox()}")
    bin_.save(rf"D:\QwenStudio\salidas\clipseg_{f.replace(' ','_')}.png")
