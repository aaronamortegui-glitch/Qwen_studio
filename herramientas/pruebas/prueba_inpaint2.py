import base64, json, time, urllib.request
from _fuentes import escena
src = escena("escena_cocina.png")
b64 = "data:image/png;base64," + base64.b64encode(open(src,"rb").read()).decode()
def post(r,p,t=3600):
    q=urllib.request.Request(f"http://127.0.0.1:7860{r}",data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(q,timeout=t).read())

t0=time.time()
r = post("/api/inpaint", {"imagen":b64, "frase":"her face",
    "prompt":"The same woman wearing round tortoiseshell eyeglasses, same face, same lighting.",
    "megapixeles":1, "steps":25, "seed":555, "crecer":10, "padding":0.5})
print(f"{time.time()-t0:.0f}s")
if r.get("error"): print("ERROR:", r["error"])
else:
    print("caja", r["caja"], "| crop", r["crop"], "-> generado", r["generado"])
    for im in r["imagenes"]: print("IMAGEN:", im["archivo"], im["tam"])
