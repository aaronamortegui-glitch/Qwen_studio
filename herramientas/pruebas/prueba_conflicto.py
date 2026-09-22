import base64, json, time, urllib.request
def b64(p,m="image/png"): return f"data:{m};base64,"+base64.b64encode(open(p,"rb").read()).decode()
I=r"D:\ComfyUI_QI21\ComfyUI_windows_portable\ComfyUI\input"
persona=b64(r"D:\AIToolkit\AI-Toolkit\datasets\eliana_qwen21\Eliohwx_03.jpg","image/jpeg")
estilo =b64(rf"{I}\escena_playa.png")     # calido, atardecer, contrastado
escena =b64(rf"{I}\escena_cocina.png")    # frio, blanco, plano

casos=[("solo_escena", {"escena":escena}),
       ("estilo_y_escena", {"escena":escena,"estilo":estilo,"estilo_modo":"look"})]
for nombre,extra in casos:
    p={"personas":[persona],"prompt":"A photograph of her.","ratio":"1:1",
       "megapixeles":1,"steps":25,"seed":8080,"variantes":1,"resumen":False}
    p.update(extra)
    q=urllib.request.Request("http://127.0.0.1:7860/api/generar",
        data=json.dumps(p).encode(), headers={"Content-Type":"application/json"})
    t0=time.time(); r=json.loads(urllib.request.urlopen(q,timeout=3600).read())
    if r.get("error"): print(nombre,"ERROR:",r["error"])
    else: print(f"{nombre:18s} {time.time()-t0:5.0f}s  {r['imagenes'][0]['archivo']}")
