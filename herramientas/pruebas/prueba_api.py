import base64, json, time, urllib.request, os
from _fuentes import persona
ref = persona()
b64 = base64.b64encode(open(ref,"rb").read()).decode()
payload = {
  "personas": ["data:image/jpeg;base64,"+b64],
  "prompt": "A photograph of her on a sunlit city street, wearing a navy coat, shallow depth of field.",
  "ratio": "16:9", "megapixeles": 1, "steps": 25, "seed": 4242,
  "variantes": 1, "transparencia": False,
}
t0=time.time()
req=urllib.request.Request("http://127.0.0.1:7860/api/generar",
    data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
r=json.loads(urllib.request.urlopen(req, timeout=3600).read())
print(f"{time.time()-t0:.0f}s")
if r.get("error"): print("ERROR:", r["error"])
else:
    for im in r["imagenes"]: print("IMAGEN:", im["archivo"], "| tam", im.get("tam"), "| seed", im["seed"])
    print("orden:", r["orden"])
