import base64, json, time, urllib.request
def b64(p,m="image/png"): return f"data:{m};base64,"+base64.b64encode(open(p,"rb").read()).decode()
I=r"D:\ComfyUI_QI21\ComfyUI_windows_portable\ComfyUI\input"
persona=b64(r"D:\AIToolkit\AI-Toolkit\datasets\eliana_qwen21\Eliohwx_03.jpg","image/jpeg")
escena =b64(rf"{I}\escena_cocina.png")
casos=[("prompt_neutro","A photograph of her."),
       ("prompt_describe","A photograph of her in that kitchen, wearing the mustard yellow sweater, soft window light.")]
for nombre,txt in casos:
    q=urllib.request.Request("http://127.0.0.1:7860/api/generar",
      data=json.dumps({"personas":[persona],"escena":escena,"prompt":txt,"ratio":"1:1",
        "megapixeles":1,"steps":25,"seed":5150,"variantes":1,"resumen":False}).encode(),
      headers={"Content-Type":"application/json"})
    t0=time.time(); r=json.loads(urllib.request.urlopen(q,timeout=3600).read())
    if r.get("error"): print(nombre,"ERROR:",r["error"])
    else: print(f"{nombre:18s} {time.time()-t0:5.0f}s  {r['imagenes'][0]['archivo']}")
