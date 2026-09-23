import base64, json, time, urllib.request
from _fuentes import persona
ref = persona()
b64 = "data:image/jpeg;base64," + base64.b64encode(open(ref,"rb").read()).decode()
def post(r,p,t=3600):
    q=urllib.request.Request(f"http://127.0.0.1:7860{r}",data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(q,timeout=t).read())

t0=time.time()
r = post("/api/generar", {
  "personas":[b64], "pose_lib":"hb_arms_cross", "escena":None,
  "prompt":"A photograph of her in that posture, wearing a charcoal blazer, plain studio background, soft even lighting.",
  "ratio":"3:4", "megapixeles":1, "steps":25, "seed":2024, "variantes":1})
print(f"{time.time()-t0:.0f}s")
if r.get("error"): print("ERROR:", r["error"])
else:
    print("orden:", r["orden"])
    for im in r["imagenes"]: print("IMAGEN:", im["archivo"], im.get("tam"))
