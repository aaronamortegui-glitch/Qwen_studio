import base64, json, time, urllib.request
src = r"D:\ComfyUI_QI21\ComfyUI_windows_portable\ComfyUI\input\escena_cocina.png"
b64 = "data:image/png;base64," + base64.b64encode(open(src,"rb").read()).decode()

def post(ruta, payload, t=3600):
    req=urllib.request.Request(f"http://127.0.0.1:7860{ruta}",
        data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=t).read())

print("--- mascara ---")
t0=time.time()
r = post("/api/mascara", {"imagen":b64, "frase":"the yellow sweater", "crecer":8})
print(f"{time.time()-t0:.1f}s", {k:v for k,v in r.items() if k!='preview'})
print("preview:", r.get("preview"))

print("--- inpaint ---")
t0=time.time()
r = post("/api/inpaint", {"imagen":b64, "frase":"the yellow sweater",
    "prompt":"A dark green leather biker jacket with a zipper, same lighting and shadows.",
    "megapixeles":1, "steps":25, "seed":1234, "crecer":8, "padding":0.35})
print(f"{time.time()-t0:.0f}s")
if r.get("error"): print("ERROR:", r["error"])
else:
    print("crop", r["crop"], "-> generado", r["generado"], "| caja", r["caja"])
    for im in r["imagenes"]: print("IMAGEN:", im["archivo"], im["tam"])
