import base64, json, time, urllib.request
ref = r"D:\AIToolkit\AI-Toolkit\datasets\eliana_qwen21\Eliohwx_03.jpg"
b64 = base64.b64encode(open(ref,"rb").read()).decode()
payload = {
  "personas": ["data:image/jpeg;base64,"+b64],
  "prompt": "Full body cutout of the person standing, clean edges around hair and clothing.",
  "ratio": "3:4", "megapixeles": 1, "steps": 25, "seed": 808,
  "variantes": 1, "transparencia": True,
}
t0=time.time()
req=urllib.request.Request("http://127.0.0.1:7860/api/generar",
    data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
r=json.loads(urllib.request.urlopen(req, timeout=3600).read())
print(f"{time.time()-t0:.0f}s")
if r.get("error"): print("ERROR:", r["error"])
else:
    for im in r["imagenes"]: print("IMAGEN:", im["archivo"], "| tam", im.get("tam"))
