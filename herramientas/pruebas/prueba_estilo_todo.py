import base64, json, time, urllib.request
import _fuentes as F
b64 = F.data_url
persona=b64(F.persona())
estilo =b64(F.escena("escena_playa.png"))
q=urllib.request.Request("http://127.0.0.1:7860/api/generar",
  data=json.dumps({"personas":[persona],"estilo":estilo,"estilo_modo":"todo",
    "prompt":"A photograph of her.","ratio":"auto","megapixeles":1,
    "steps":25,"seed":333,"variantes":1}).encode(),
  headers={"Content-Type":"application/json"})
t0=time.time(); r=json.loads(urllib.request.urlopen(q,timeout=3600).read())
print(f"{time.time()-t0:.0f}s")
if r.get("error"): print("ERROR:",r["error"])
else:
    print("orden:",r["orden"]); print("resumen:",r.get("resumen"))
    print("PROMPT:",r["prompt"][:400])
    for im in r["imagenes"]: print("IMAGEN:",im["archivo"],im.get("tam"))
