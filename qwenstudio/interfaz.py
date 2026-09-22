"""QwenStudio web interface.

Driven by use cases: pick what you want to do and only the inputs that matter
show up. The reference ORDER the engine depends on is never exposed, because
getting it wrong fails silently rather than loudly.
"""

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QwenStudio</title>
<style>
/* Superside: fondo hueso, tinta verde casi negra, lima para la accion.
   Medido en superside.com el 2026-09-22 -- #F7F9F2, #0A211F, #D8FF85, #2A4E45,
   Inter Tight, titulares en peso 400 y botones pildora.

   La lima es un color CLARO: solo vive como fondo con tinta oscura encima.
   Como texto sobre blanco no llega ni de lejos al contraste minimo, asi que no
   aparece nunca en un color de letra. */
@font-face{
  font-family:'Inter Tight'; font-style:normal; font-weight:400 600; font-display:swap;
  src:url('/fuentes/InterTight-latin.woff2') format('woff2');
  unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,
    U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,
    U+2215,U+FEFF,U+FFFD;
}
@font-face{
  font-family:'Inter Tight'; font-style:normal; font-weight:400 600; font-display:swap;
  src:url('/fuentes/InterTight-latin-ext.woff2') format('woff2');
  unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,
    U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,
    U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF;
}
:root{
  --hueso:#f7f9f2; --tinta:#0a211f; --lima:#d8ff85; --verde:#2a4e45;
  --bg:var(--hueso); --sf:#fff; --sf-1:#fbfcf8; --sf-2:#eef3e4; --sf-3:#e4ebd6;
  --on-sf:var(--tinta); --on-sf-var:#4a5d59;
  --line:#dde3d6; --line-soft:#e9eee1;
  --ac:var(--lima); --on-ac:var(--tinta);          /* la accion principal */
  --ac-2:var(--verde); --on-ac-2:var(--hueso);     /* la accion secundaria */
  --link:#2a4e45;
  --pestana:var(--sf);
  --ok:#2a7a53; --warn:#8a6100; --bad:#b3261e;
  --bad-cont:#fbeeec; --on-bad-cont:#8c1d18; --warn-cont:#faf3e0;
  --r-xs:8px; --r-s:10px; --r-m:12px; --r-l:16px; --r-xl:20px; --r-full:999px;
  --e1:0 1px 2px rgba(10,33,31,.06), 0 1px 3px rgba(10,33,31,.04);
  --e2:0 2px 6px rgba(10,33,31,.08), 0 1px 2px rgba(10,33,31,.06);
  --e3:0 12px 34px rgba(10,33,31,.18), 0 2px 8px rgba(10,33,31,.10);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#081917; --sf:#0f2624; --sf-1:#122a28; --sf-2:#1a3230; --sf-3:#22403c;
  --on-sf:#eef3e4; --on-sf-var:#a9bdb6;
  --line:#2c4a45; --line-soft:#1e3a36;
  --ac:var(--lima); --on-ac:var(--tinta);
  --ac-2:#cfe0b8; --on-ac-2:var(--tinta);
  --link:#d8ff85;
  --pestana:var(--sf-3);
  --ok:#8fd9a8; --warn:#e0b558; --bad:#f2b8b5;
  --bad-cont:#3a1f1d; --on-bad-cont:#f9dedc; --warn-cont:#2f2718;
  --e1:0 1px 3px rgba(0,0,0,.5); --e2:0 2px 10px rgba(0,0,0,.55);
  --e3:0 14px 40px rgba(0,0,0,.66);
}}
:root[data-theme="dark"]{
  --bg:#081917; --sf:#0f2624; --sf-1:#122a28; --sf-2:#1a3230; --sf-3:#22403c;
  --on-sf:#eef3e4; --on-sf-var:#a9bdb6;
  --line:#2c4a45; --line-soft:#1e3a36;
  --ac:var(--lima); --on-ac:var(--tinta);
  --ac-2:#cfe0b8; --on-ac-2:var(--tinta);
  --link:#d8ff85;
  --pestana:var(--sf-3);
  --ok:#8fd9a8; --warn:#e0b558; --bad:#f2b8b5;
  --bad-cont:#3a1f1d; --on-bad-cont:#f9dedc; --warn-cont:#2f2718;
  --e1:0 1px 3px rgba(0,0,0,.5); --e2:0 2px 10px rgba(0,0,0,.55);
  --e3:0 14px 40px rgba(0,0,0,.66);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--on-sf);
  font:400 15px/1.5 'Inter Tight',Inter,system-ui,-apple-system,'Segoe UI',Arial,sans-serif;
  -webkit-font-smoothing:antialiased;letter-spacing:.1px}
.num{font-variant-numeric:tabular-nums}
a{color:var(--link)}

/* ---- barra superior ---- */
header{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  padding:12px 22px;background:var(--sf);border-bottom:1px solid var(--line-soft);
  position:sticky;top:0;z-index:5}
h1{font-size:19px;margin:0 6px 0 0;font-weight:500;letter-spacing:-.1px;
  display:flex;align-items:center;gap:9px}
h1 .marca{width:26px;height:26px;flex:none}
.chip{font-size:12.5px;color:var(--on-sf-var);background:var(--sf-2);
  border-radius:var(--r-full);padding:6px 13px;display:inline-flex;align-items:center;
  gap:7px;white-space:nowrap}
.pt{width:8px;height:8px;border-radius:50%;background:var(--line);flex:none}
.chip.ok{background:var(--lima);color:var(--tinta)} .chip.ok .pt{background:var(--verde)}
.chip.busy .pt{background:var(--warn);animation:lat 1.1s ease-in-out infinite}
.chip.err{background:var(--bad-cont);color:var(--on-bad-cont)} .chip.err .pt{background:var(--bad)}
@keyframes lat{0%,100%{opacity:1}50%{opacity:.25}}
@media (prefers-reduced-motion:reduce){.chip.busy .pt{animation:none}}

main{display:grid;grid-template-columns:minmax(340px,440px) 1fr;gap:20px;
  padding:20px;align-items:start}
@media(max-width:980px){main{grid-template-columns:1fr;padding:16px}}
.card{background:var(--sf);border-radius:var(--r-l);padding:24px;box-shadow:var(--e1);
  border:1px solid var(--line-soft)}

/* los pasos: el flujo es una secuencia, el numero dice algo */
h2{font-size:13px;margin:0 0 14px;color:var(--on-sf);font-weight:500;
  display:flex;align-items:center;gap:10px;letter-spacing:0}
h2 i{width:22px;height:22px;border-radius:50%;background:var(--lima);
  color:var(--tinta);font:600 12px/22px 'Inter Tight',Inter,sans-serif;font-style:normal;
  text-align:center;flex:none}
.sec{border-top:1px solid var(--line-soft);margin-top:24px;padding-top:20px}
label{display:block;font-size:12.5px;margin:0 0 6px;color:var(--on-sf-var)}
.hint{font-size:12.5px;color:var(--on-sf-var);margin-top:10px;line-height:1.5}
code{background:var(--sf-2);border-radius:5px;padding:1px 5px;font-size:12px}

/* ---- campos ---- */
input,textarea,select{width:100%;padding:12px 14px;border:1px solid var(--line);
  border-radius:var(--r-s);background:var(--sf);color:var(--on-sf);font:inherit;
  transition:border-color .15s,box-shadow .15s}
textarea{min-height:92px;resize:vertical;line-height:1.55}
input:focus,textarea:focus,select:focus{outline:0;border-color:var(--verde);
  box-shadow:0 0 0 3px rgba(42,78,69,.16)}
input[type=range]{padding:0;border:0;background:transparent;accent-color:var(--verde)}
input[type=checkbox],input[type=radio]{width:auto;accent-color:var(--verde)}
:focus-visible{outline:2px solid var(--verde);outline-offset:2px}

/* ---- botones: pildora, como los suyos ---- */
.go{width:100%;margin-top:22px;padding:15px;border:0;border-radius:var(--r-full);
  background:var(--ac);color:var(--on-ac);font:inherit;font-size:15px;font-weight:600;
  cursor:pointer;transition:filter .15s,box-shadow .15s}
.go:hover:not(:disabled){filter:brightness(.96);box-shadow:var(--e2)}
.go:disabled{opacity:.4;cursor:default}
.go.alt{background:var(--tinta);color:var(--hueso);font-size:14px;padding:12px;margin-top:10px}
:root[data-theme="dark"] .go.alt,
:root:not([data-theme="light"]) .go.alt{background:var(--sf-3);color:var(--on-sf)}
.ghost{border:1px solid var(--line);background:transparent;color:var(--on-sf);
  border-radius:var(--r-full);padding:0 17px;height:34px;font:inherit;font-size:13px;
  font-weight:500;cursor:pointer;display:inline-flex;align-items:center;justify-content:center}
.ghost:hover{background:var(--sf-2)}
.pill{border:1px solid var(--line);background:transparent;color:var(--on-sf-var);
  border-radius:var(--r-full);padding:0 16px;height:34px;font:inherit;font-size:13px;
  cursor:pointer;transition:.15s;display:inline-flex;align-items:center}
.pill:hover{background:var(--sf-2)}
.pill[aria-pressed=true]{background:var(--lima);border-color:transparent;
  color:var(--tinta);font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:8px}

/* ---- grupos de casos ---- */
.cats{display:flex;gap:6px;background:var(--sf-2);border-radius:var(--r-full);
  padding:4px;margin-bottom:14px}
.cats button{flex:1;border:0;background:transparent;color:var(--on-sf-var);font:inherit;
  font-size:13px;padding:8px 10px;border-radius:var(--r-full);cursor:pointer;
  white-space:nowrap;transition:.15s}
.cats button:hover{color:var(--on-sf)}
.cats button[aria-pressed=true]{background:var(--pestana);color:var(--on-sf);font-weight:600;
  box-shadow:var(--e1)}
.casos{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:420px){.casos{grid-template-columns:1fr}}
.caso{border:1px solid var(--line-soft);background:var(--sf);border-radius:var(--r-m);
  padding:14px;cursor:pointer;text-align:left;color:var(--on-sf);font:inherit;
  display:flex;gap:12px;align-items:flex-start;transition:.15s}
.caso:hover{background:var(--sf-1);border-color:var(--line)}
.caso[aria-pressed=true]{background:var(--lima);border-color:transparent;color:var(--tinta)}
.caso .ico{color:var(--on-sf-var);flex:none;margin-top:1px}
.caso[aria-pressed=true] .ico,.caso[aria-pressed=true] b,
.caso[aria-pressed=true] small{color:var(--tinta)}
.caso b{display:block;font-size:14px;font-weight:600;margin-bottom:3px}
.caso small{color:var(--on-sf-var);font-size:12.5px;line-height:1.4;display:block}
.caso[aria-pressed=true] small{opacity:.78}

/* ---- zonas de imagen ---- */
.zona{border:1.5px dashed var(--line);border-radius:var(--r-m);background:var(--sf-1);
  padding:16px 18px;display:grid;grid-template-columns:auto 1fr;gap:14px;
  align-items:center;cursor:pointer;transition:.15s;margin-bottom:12px}
.zona:hover,.zona.over{border-color:var(--verde);border-style:solid;background:var(--sf-2)}
.zona .n{width:52px;height:52px;border-radius:var(--r-s);background:var(--sf-2);
  color:var(--verde);display:grid;place-items:center;flex:none}
.zona:hover .n,.zona.over .n{background:var(--lima);color:var(--tinta)}
.zona.opt{background:transparent;border-color:var(--line-soft)}
.zona.opt .n{background:var(--sf-2);color:var(--on-sf-var)}
.zona b{display:block;font-size:14px;font-weight:600}
.zona small{color:var(--on-sf-var);font-size:12.5px;line-height:1.45;display:block;margin-top:2px}
.opt-tag{font-size:11px;font-weight:400;color:var(--on-sf-var);background:var(--sf-2);
  border-radius:var(--r-full);padding:2px 9px;margin-left:6px;vertical-align:1px}
.tira{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 0;grid-column:1/-1}
.tira figure{margin:0;position:relative}
.tira img{width:52px;height:52px;object-fit:cover;background:var(--sf-2);
  border-radius:var(--r-s);display:block}
.tira button{position:absolute;top:-7px;right:-7px;border:0;background:var(--tinta);color:var(--hueso);
  border-radius:50%;width:22px;height:22px;font-size:13px;line-height:22px;cursor:pointer;
  padding:0;box-shadow:var(--e1)}

.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.medida{font-size:13px;color:var(--on-sf-var);text-align:right;padding-top:12px;
  font-variant-numeric:tabular-nums}
.marcas{display:flex;justify-content:space-between;font-size:11px;color:var(--on-sf-var);
  margin-top:4px}
.sw{display:flex;align-items:center;gap:10px;margin-top:16px;cursor:pointer;font-size:14px}
.sw input{width:auto;margin:0}
details>summary{cursor:pointer;font-size:13px;color:var(--link);margin-top:18px;
  user-select:none;padding:10px 0;font-weight:500}
.barraPrompt{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.barraPrompt button{border:1px solid var(--line);background:transparent;color:var(--on-sf);
  border-radius:var(--r-full);padding:0 16px;height:34px;font:inherit;font-size:13px;
  font-weight:500;cursor:pointer;display:inline-flex;align-items:center}
.barraPrompt button:hover{background:var(--sf-2)}
.barraPrompt button:disabled{opacity:.4;cursor:default}

/* ---- avisos ---- */
.nota{background:var(--warn-cont);padding:13px 16px;border-radius:var(--r-s);
  font-size:13px;margin:12px 0;line-height:1.5}
.nota.mal{background:var(--bad-cont);color:var(--on-bad-cont)}
.nota.ejemplo{background:var(--sf-1);color:var(--on-sf);display:flex;gap:12px;
  align-items:center;flex-wrap:wrap;border:1px solid var(--line-soft);
  border-left:4px solid var(--lima)}
.nota.ejemplo .ghost{margin-left:auto}

/* ---- galeria de efectos ---- */
#ef{width:min(960px,95vw);max-width:none}
#efGrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;
  max-height:60vh;overflow:auto;padding:2px}
#efGrid button{border:1px solid var(--line-soft);background:var(--sf-1);
  border-radius:var(--r-s);padding:0;cursor:pointer;overflow:hidden;text-align:left;
  color:var(--on-sf);font:inherit;transition:.15s}
#efGrid button:hover{border-color:var(--verde)}
#efGrid button[aria-pressed=true]{border-color:transparent;outline:2px solid var(--verde);
  outline-offset:-2px}
#efGrid img{width:100%;aspect-ratio:1;object-fit:cover;background:var(--sf-2);display:block}
#efGrid .sinthumb{width:100%;aspect-ratio:1;display:grid;place-items:center;
  background:var(--sf-2);color:var(--on-sf-var);font-size:11px;text-align:center;padding:8px}
#efGrid span{display:block;padding:9px 11px;font-size:12.5px;font-weight:600}
#efGrid small{color:var(--on-sf-var);font-size:11px;font-weight:400;display:block}
#efGrid button[disabled]{opacity:.45;cursor:not-allowed}
.efElegido{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:12px;
  background:var(--sf-1);border:1px solid var(--line-soft);border-radius:var(--r-s);
  padding:10px 12px}
.efElegido img{width:46px;height:46px;border-radius:var(--r-xs);object-fit:cover;flex:none}
.efElegido b{font-size:14px;display:block}
.efElegido small{color:var(--on-sf-var);font-size:12px}

/* ---- galeria ---- */
#gl{width:min(1020px,95vw);max-width:none}
#glGrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:12px;
  max-height:60vh;overflow:auto;padding:2px}
#glGrid figure{margin:0;border:1px solid var(--line-soft);border-radius:var(--r-s);
  overflow:hidden;background:var(--sf-1)}
#glGrid img{width:100%;aspect-ratio:1;object-fit:cover;display:block;cursor:zoom-in;
  background:repeating-conic-gradient(var(--sf-2) 0 25%,transparent 0 50%) 50%/14px 14px}
#glGrid figcaption{padding:7px 9px;font-size:11px;color:var(--on-sf-var);
  display:flex;justify-content:space-between;align-items:center;gap:6px}
#glGrid .tipo{background:var(--sf-2);border-radius:var(--r-full);padding:1px 8px;
  font-size:10px;white-space:nowrap}
#glGrid a{display:inline-flex;align-items:center;color:var(--on-sf-var);text-decoration:none}
#glGrid a:hover{color:var(--link)}
#glPie,#efPie{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:16px}
#glPie code{font-size:11px;overflow-wrap:anywhere}
.iconobtn{border:1px solid var(--line);background:transparent;color:var(--on-sf);
  border-radius:var(--r-full);width:30px;height:30px;display:inline-grid;place-items:center;
  cursor:pointer;padding:0;text-decoration:none}
.iconobtn:hover{background:var(--sf-2)}
.gal figcaption .acciones{display:flex;gap:6px;align-items:center}

/* ---- LoRA a la vista ---- */
.lora{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px;
  background:var(--sf-1);border:1px solid var(--line-soft);border-radius:var(--r-s);
  padding:10px 12px}
.lora label{margin:0;white-space:nowrap}
.lora select{flex:1;min-width:140px}
.lora input{width:74px;flex:none}

/* ---- bienvenida ---- */
.bienvenida{text-align:center;padding:26px 8px 6px}
.bienvenida .marca{width:64px;height:64px;margin-bottom:6px}
.bienvenida h2{display:block;font-size:26px;font-weight:400;letter-spacing:-.2px;
  margin:10px 0 8px;text-transform:none}
.bienvenida p{color:var(--on-sf-var);font-size:14px;line-height:1.55;margin:0 auto 6px;
  max-width:46ch}
.cargando{display:inline-flex;gap:6px;margin:16px 0 4px}
.cargando i{width:9px;height:9px;border-radius:50%;background:var(--verde);
  animation:rebote 1.05s ease-in-out infinite}
.cargando i:nth-child(2){animation-delay:.14s}
.cargando i:nth-child(3){animation-delay:.28s}
@keyframes rebote{0%,70%,100%{transform:translateY(0);opacity:.35}
  35%{transform:translateY(-7px);opacity:1}}
@media (prefers-reduced-motion:reduce){.cargando i{animation:none;opacity:.7}}

/* ---- la pantalla del perrito ---- */
.perrito{text-align:center;padding:12px 8px 4px}
.perrito svg{width:190px;height:190px;max-width:70%}
.perrito h2{display:block;font-size:22px;font-weight:400;letter-spacing:-.2px;
  margin:14px 0 8px;color:var(--on-sf);text-transform:none}
.perrito p{color:var(--on-sf-var);font-size:14px;line-height:1.55;margin:0 auto 6px;
  max-width:44ch}
.perrito .ficha{display:inline-block;background:var(--sf-2);border-radius:var(--r-xs);
  padding:8px 14px;font-size:12px;color:var(--on-sf-var);margin:12px 0 4px}

/* ---- el pincel de mascara ---- */
#mk{width:auto;max-width:min(980px,96vw)}
#mkCentro{text-align:center}
.mkAcciones{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
.mkAcciones .go{width:auto;margin:0;padding:12px 26px}
.lienzo{position:relative;line-height:0;border-radius:var(--r-s);overflow:hidden;
  background:var(--sf-2);margin-bottom:14px;touch-action:none;
  display:inline-block;max-width:100%}
.lienzo img,.lienzo canvas{max-width:100%;max-height:58vh;width:auto;height:auto;display:block}
.lienzo canvas{position:absolute;inset:0;width:100%;height:100%;opacity:.55;cursor:crosshair}
.mkBarra{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.mkBarra input[type=range]{width:140px}
.mkBarra .sep{flex:1}

/* ---- resultados ---- */
.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.gal figure{margin:0;background:var(--sf-1);border-radius:var(--r-m);overflow:hidden;
  border:1px solid var(--line-soft)}
.gal>figure>img{width:100%;display:block;cursor:zoom-in;
  background:repeating-conic-gradient(var(--sf-2) 0 25%,transparent 0 50%) 50%/18px 18px}
.gal figcaption{padding:11px 15px;font-size:12px;color:var(--on-sf-var);
  display:flex;justify-content:space-between;gap:8px;align-items:center}
.ba{position:relative;overflow:hidden;cursor:ew-resize;background:var(--sf-2);touch-action:none}
.ba>img{display:block;width:100%}
.ba .after{position:absolute;inset:0;clip-path:inset(0 0 0 50%)}
.ba .after img{width:100%;height:100%;object-fit:cover;display:block}
.ba .handle{position:absolute;top:0;bottom:0;left:50%;width:3px;background:var(--lima);
  box-shadow:0 0 0 1px rgba(10,33,31,.25)}
.ba .handle::after{content:'';position:absolute;top:50%;left:50%;
  transform:translate(-50%,-50%);width:34px;height:34px;border-radius:50%;
  background:var(--lima);box-shadow:var(--e2)}
.ba .tag{position:absolute;bottom:10px;font-size:11px;background:rgba(10,33,31,.78);
  color:var(--hueso);padding:3px 11px;border-radius:var(--r-full);pointer-events:none}
.ba .tag.l{left:10px}.ba .tag.r{right:10px}
pre{white-space:pre-wrap;font-size:12px;color:var(--on-sf-var);background:var(--sf-1);
  padding:15px;border-radius:var(--r-s);margin:14px 0 0;line-height:1.6}
.barra{height:8px;background:var(--sf-2);border-radius:var(--r-full);overflow:hidden;margin:14px 0}
.barra i{display:block;height:100%;background:var(--verde);width:0;transition:width .4s;
  border-radius:var(--r-full)}

/* ---- dialogos ---- */
dialog{border:0;padding:0;background:transparent;max-width:96vw;max-height:96vh}
dialog>img{max-width:94vw;max-height:94vh;object-fit:contain;border-radius:var(--r-m);display:block}
dialog::backdrop{background:rgba(10,33,31,.5)}
#lib,#pl,#cfg,#mk,#gl,#ef{background:var(--sf);border-radius:var(--r-xl);padding:26px;
  color:var(--on-sf);box-shadow:var(--e3)}
#lib{width:min(900px,94vw);max-width:none}
#pl{width:min(800px,94vw);max-width:none}
#cfg{width:min(500px,94vw);max-width:none}
#lib h3,#pl h3,#cfg h3,#mk h3,#gl h3,#ef h3{margin:0 0 18px;font-size:22px;font-weight:400;
  letter-spacing:-.2px}
#libGrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(132px,1fr));gap:12px;
  max-height:62vh;overflow:auto}
#libGrid button{border:1px solid var(--line-soft);background:var(--sf-1);
  border-radius:var(--r-s);padding:0;cursor:pointer;overflow:hidden;text-align:left;
  color:var(--on-sf);font:inherit;transition:.15s}
#libGrid button:hover{border-color:var(--verde)}
#libGrid img{width:100%;aspect-ratio:3/4;object-fit:cover;background:var(--sf-2);display:block}
#libGrid span{display:block;padding:9px 11px;font-size:12px;font-weight:500}
#libGrid small{color:var(--on-sf-var);font-size:11px;font-weight:400}
#plBody{max-height:64vh;overflow:auto}
#plBody h4{font-size:11px;text-transform:uppercase;letter-spacing:.09em;
  color:var(--on-sf-var);margin:20px 0 9px;font-weight:600}
#plBody h4:first-child{margin-top:0}
#plBody button{display:block;width:100%;text-align:left;border:1px solid var(--line-soft);
  background:var(--sf-1);color:var(--on-sf);border-radius:var(--r-s);padding:13px 15px;
  margin-bottom:8px;cursor:pointer;font:inherit;font-size:13px;line-height:1.5;transition:.15s}
#plBody button:hover{border-color:var(--verde);background:var(--sf-2)}
#plBody button b{display:block;font-size:12px;color:var(--link);margin-bottom:3px;font-weight:600}
.opt{display:flex;align-items:flex-start;gap:14px;padding:15px 0;
  border-bottom:1px solid var(--line-soft)}
.opt:last-of-type{border-bottom:0}
.opt input[type=checkbox]{width:auto;margin:3px 0 0}
.opt input[type=number],.opt select{width:100px;flex:none}
.opt div{flex:1}
.opt b{display:block;font-size:14px;font-weight:600}
.opt small{color:var(--on-sf-var);font-size:12.5px;line-height:1.45;display:block;margin-top:3px}
.modoEstilo{display:inline-flex;align-items:center;gap:6px;margin:8px 12px 0 0;font-size:12px;
  color:var(--on-sf-var);cursor:pointer}
.modoEstilo input{width:auto;margin:0}
</style>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Crect width='48' height='48' rx='12' fill='%230a211f'/%3E%3Crect x='9' y='14' width='18' height='18' rx='5' fill='%23d8ff85'/%3E%3Ccircle cx='30' cy='18' r='9' fill='%23d8ff85'/%3E%3Ccircle cx='30' cy='18' r='5.6' fill='%230a211f'/%3E%3C/svg%3E">
<script>(function(){var t='light';try{t=localStorage.getItem('qs_tema')||'light'}catch(e){}
if(t!=='auto')document.documentElement.setAttribute('data-theme',t);})();</script>
</head><body>

<header>
  <h1><svg class="marca" viewBox="0 0 48 48" role="img" aria-label="QwenStudio"><rect width="48" height="48" rx="12" fill="#0a211f"/><rect x="9" y="14" width="18" height="18" rx="5" fill="#d8ff85"/><circle cx="30" cy="18" r="9" fill="#d8ff85"/><circle cx="30" cy="18" r="5.6" fill="#0a211f"/></svg>QwenStudio</h1>
  <span class="chip num" id="chipProfile">&nbsp;</span>
  <span class="chip" id="chipEngine"><i class="pt"></i><span>starting</span></span>
  <span style="flex:1"></span>
  <button type="button" class="ghost" id="btnGaleria" title="Everything you have made">Gallery</button>
  <button type="button" class="ghost" id="btnAjustes" title="Settings">Settings</button>
</header>

<main>
<div class="card">
  <div id="setup"><div class="bienvenida"><svg class="marca" viewBox="0 0 48 48" role="img" aria-label="QwenStudio"><rect width="48" height="48" rx="12" fill="#0a211f"/><rect x="9" y="14" width="18" height="18" rx="5" fill="#d8ff85"/><circle cx="30" cy="18" r="9" fill="#d8ff85"/><circle cx="30" cy="18" r="5.6" fill="#0a211f"/></svg>
    <h2>Welcome to QwenStudio</h2>
    <p>Local image generation and editing with Qwen-Image 2.1. Nothing leaves
      this machine.</p>
    <div class="cargando"><i></i><i></i><i></i></div>
    <p class="hint">Talking to the engine…</p>
  </div></div>
  <div id="panel" hidden>
    <h2><i>1</i>What do you want to do</h2>
    <div class="cats" id="cats"></div>
    <div class="casos" id="casos"></div>

    <div class="sec" id="secEntradas"><h2 id="tituloEntradas"><i>2</i>Inputs</h2></div>
    <div id="zonas"></div>
    <div id="campos"></div>

    <div class="sec"></div>
    <h2 id="lblPrompt"><i>3</i>Instruction</h2>
    <textarea id="prompt"></textarea>
    <div class="efElegido" id="zonaEfecto" hidden>
      <span id="efMini"></span>
      <span style="flex:1"><b id="efNombre">No look picked yet</b>
        <small id="efDesc">Open the grid and choose one.</small></span>
      <button type="button" class="ghost" id="btnEf">Pick a look</button>
    </div>
    <div class="hint" id="zonaEscalar" hidden>The image is redrawn at a larger size using
      itself as the reference, which recovers real detail instead of interpolating pixels.
      The target is the whole 2K budget: the area is scaled towards 2048&times;2048, capped
      at four times per side.</div>
    <div class="barraPrompt" id="barraPrompt">
      <button type="button" id="btnPl">Prompt library</button>
      <button type="button" id="btnMejorar">Improve it</button>
      <button type="button" id="btnDeshacer" hidden>Undo</button>
      <button type="button" id="btnDesc">Describe an image</button>
      <button type="button" id="btnClear">Clear</button>
    </div>
    <div class="hint">Write it positively. Reference order is handled for you.</div>
    <div class="lora" id="filaLora" hidden>
      <label for="lora">LoRA</label>
      <select id="lora"><option value="">none</option></select>
      <label for="loraw">Weight</label>
      <input type="number" id="loraw" value="1.0" step="0.05" min="0" max="2">
    </div>

    <details id="avanzado">
      <summary>Advanced settings</summary>

      <div class="sec" style="margin-top:8px"><h2>Format</h2></div>
      <div class="chips" id="ratios"></div>
      <div class="grid2" style="margin-top:10px">
        <div><label>Quality</label><select id="mp">
          <option value="1">1 MP · fast</option><option value="2">2 MP · medium</option>
          <option value="4">4 MP · 2K native</option></select></div>
        <div><label>Output</label><div class="medida" id="medida">1024 × 1024</div></div>
      </div>

      <div class="sec" style="margin-top:12px"><h2>Sampling</h2></div>
      <label>Steps · <b id="vSteps">25</b></label>
      <input type="range" id="steps" min="8" max="50" value="25">
      <div class="marcas"><span>8 · draft</span><span>25</span><span>40 · model card</span><span>50</span></div>
      <div class="grid2" style="margin-top:10px">
        <div><label>Seed (0 = random)</label><input type="number" id="seed" value="0"></div>
        <div><label>Variants</label><input type="number" id="variants" value="1" min="1" max="4"></div>
      </div>


      <div id="avInpaint" hidden>
        <div class="sec" style="margin-top:12px"><h2>Mask</h2></div>
        <div class="hint" id="avisoMaskAv" hidden>Grow and Threshold belong to the text
          segmenter. A painted mask is used exactly as drawn, so they do nothing right now.</div>
        <div class="grid2">
          <div><label>Grow (px)</label><input type="number" id="grow" value="8" min="-20" max="60"></div>
          <div><label>Feather (px)</label><input type="number" id="feather" value="12" min="0" max="60"></div>
        </div>
        <div class="grid2" style="margin-top:9px">
          <div><label>Threshold</label><input type="number" id="thr" value="0.5" step="0.05" min="0.1" max="0.9"></div>
          <div><label>Context padding</label><input type="number" id="pad" value="0.35" step="0.05" min="0" max="1.5"></div>
        </div>
      </div>

      <label class="sw"><input type="checkbox" id="transp"> Transparent background (PNG with alpha)</label>
    </details>

    <button class="go" id="go">Generate</button>
    <button class="go alt" id="verMask" hidden>Preview the selection</button>
    <div id="avisos"></div>
  </div>
</div>

<div class="card">
  <h2>Results</h2>
  <div id="vacio" class="hint">Nothing here yet.</div>
  <div class="gal" id="gal"></div>
  <pre id="verPrompt" hidden></pre>
</div>
</main>
<dialog id="lupa"><img id="lupaImg" alt=""></dialog>
<dialog id="lib"><h3>Pose library <small style="font-weight:400;color:var(--on-sf-var);font-size:11.5px">— hover to see the skeleton that gets sent</small></h3>
  <div class="chips" id="libFiltros" style="margin-bottom:10px"></div>
  <div id="libGrid"></div></dialog>
<dialog id="pl"><h3>Prompt library</h3><div id="plBody"></div></dialog>
<dialog id="ef"><h3>Pick a look</h3>
  <div class="hint" style="margin:-10px 0 14px">Each thumbnail is this effect applied to
    the reference photo of this install, generated here. The composition, the framing and
    the face stay; only the treatment changes.</div>
  <div class="chips" id="efFiltros" style="margin-bottom:12px"></div>
  <div id="efGrid"></div>
  <div id="efPie">
    <span class="hint" id="efNota" style="margin:0"></span>
    <span style="flex:1"></span>
    <button class="go alt" type="button" id="efCerrar" style="width:auto;margin:0;
      padding:10px 22px">Close</button>
  </div>
</dialog>
<dialog id="gl"><h3>Gallery</h3>
  <div class="hint" style="margin:-10px 0 14px">Everything this app has written to
    <code>salidas/</code>, newest first. The folder is the gallery: delete a file there
    and it is gone from here.</div>
  <div id="glGrid"></div>
  <div id="glPie">
    <button type="button" class="ghost" id="glCarpeta">Open the folder</button>
    <span class="hint num" id="glCuenta" style="margin:0"></span>
    <span style="flex:1"></span>
    <button class="go alt" type="button" id="glCerrar" style="width:auto;margin:0;
      padding:10px 22px">Close</button>
  </div>
</dialog>
<dialog id="mk"><h3>Paint what to replace</h3>
  <div class="mkBarra">
    <button type="button" class="pill" id="mkPintar" aria-pressed="true">Brush</button>
    <button type="button" class="pill" id="mkBorrar" aria-pressed="false">Eraser</button>
    <label for="mkTam" style="margin:0">Size</label>
    <input type="range" id="mkTam" min="8" max="220" value="60">
    <span class="hint num" id="mkTamV" style="margin:0">60 px</span>
    <span class="sep"></span>
    <button type="button" class="ghost" id="mkLimpiar">Clear</button>
  </div>
  <div id="mkCentro"><div class="lienzo" id="mkLienzo"><img id="mkImg" alt=""><canvas id="mkCv"></canvas></div></div>
  <div class="hint">Paint over everything that should change. What you leave
    untouched is kept pixel for pixel.</div>
  <div class="mkAcciones">
    <button class="go alt" type="button" id="mkCerrar">Cancel</button>
    <button class="go" type="button" id="mkUsar">Use this mask</button>
  </div>
</dialog>
<dialog id="cfg"><h3>Settings</h3>
  <div class="opt"><div><b>Appearance</b>
    <small>Light is the default. Auto follows your system.</small></div>
    <div class="chips" id="tema" style="flex:none">
      <button type="button" class="pill" data-t="light">Light</button>
      <button type="button" class="pill" data-t="dark">Dark</button>
      <button type="button" class="pill" data-t="auto">Auto</button>
    </div></div>
  <div id="cfgBody"></div>
  <div class="hint" id="cfgHw"></div>
  <button class="go" type="button" id="cfgClose">Done</button>
</dialog>

<script>
const $=s=>document.querySelector(s);
// iconos de trazo, heredan el color del texto: un set propio en vez de emojis
const IC={
 portrait:'<circle cx="12" cy="8.5" r="3.6"/><path d="M4.8 20c.6-3.8 3.6-5.8 7.2-5.8s6.6 2 7.2 5.8"/>',
 scene:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 15.5l4.5-4a2 2 0 0 1 2.7 0L16 17"/><circle cx="15.5" cy="9.5" r="1.6"/>',
 pose:'<circle cx="12" cy="4.4" r="2"/><path d="M12 6.6v7M12 8.6L7.5 11M12 8.6l4.5 2.4M12 13.6L8.6 20M12 13.6L15.4 20"/>',
 replace:'<path d="M4 7h9a4 4 0 0 1 0 8H8"/><path d="M10.5 12.5L8 15l2.5 2.5"/><rect x="15" y="4" width="5" height="5" rx="1"/>',
 cutout:'<path d="M12 4v8"/><circle cx="7" cy="16" r="2.6"/><circle cx="17" cy="16" r="2.6"/><path d="M9 14.4L17 5M15 14.4L7 5"/>',
 free:'<path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="9"/>',
 style:'<path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-.9 2-1.8 0-1.6-1.6-1.8-1.6-3 0-.9.7-1.6 1.7-1.6H16a5 5 0 0 0 5-5c0-3.6-4-6.6-9-6.6z"/><circle cx="7.5" cy="11" r="1"/><circle cx="11" cy="7.5" r="1"/><circle cx="15.5" cy="9" r="1"/>',
 upload:'<path d="M12 16V5M8.5 8.5L12 5l3.5 3.5"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
 text:'<path d="M5 8V5.5h14V8"/><path d="M12 5.5v13"/><path d="M8.5 18.5h7"/>',
 descarga:'<path d="M12 4v10M8.5 10.5L12 14l3.5-3.5"/><path d="M5 16v2a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2"/>',
 galeria:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 15l4.5-4a2 2 0 0 1 2.7 0L16 17"/><circle cx="15.5" cy="8.5" r="1.4"/>',
 efecto:'<path d="M12 3.2l2.1 4.6 4.9.6-3.6 3.4 1 4.9-4.4-2.5-4.4 2.5 1-4.9L5 8.4l4.9-.6z"/>',
 escalar:'<path d="M4 10V4h6"/><path d="M20 14v6h-6"/><path d="M4 4l7 7"/><path d="M20 20l-7-7"/>',
 carpeta:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
 sign:'<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M7 9.5h10M7 13h6"/><path d="M12 17v3"/>',
};
const svg=(n,t=20)=>`<svg viewBox="0 0 24 24" width="${t}" height="${t}" fill="none"
  stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
  aria-hidden="true">${IC[n]||''}</svg>`;
const leer=f=>new Promise(r=>{const x=new FileReader();x.onload=()=>r(x.result);x.readAsDataURL(f)});

const ZONAS={
  person:{icon:'portrait', n:'Person', d:'Face photos. These define the identity.'},
  pose:  {icon:'pose', n:'Pose',   d:'Drop a photo, or <a href="#" class="lnkLib">pick from the library</a>.'},
  scene: {icon:'scene', n:'Scene',  d:'Setting, wardrobe, framing and lighting.'},
  style: {icon:'style', n:'Style',  d:'Grade, contrast, grain, quality of light. Place and wardrobe come from Scene.<br><label class="modoEstilo"><input type="radio" name="em" value="todo"> clothing + place + look</label> <label class="modoEstilo"><input type="radio" name="em" value="look" checked> look only</label>'},
  source:{icon:'replace', n:'Image',  d:'The photo you want to edit.'},
  extra: {icon:'upload', n:'Reference', d:'A photo of what should go there.'},
};
const CATS=[
  ['text','Text to image','Words only.'],
  ['photo','From a photo','One or more references.'],
  ['edit','Edit a photo','Change part of one image.'],
];
const CASOS={
  blank:{cat:'text', icon:'text', name:'New image', hint:'No reference at all.',
    mode:'generate', zonas:[], opt:[], ratio:'3:2',
    prompt:'A weathered brass diving helmet resting on an oak workbench, studio product '
      +'photograph, scratched patina and green verdigris in the seams, a coil of hemp rope '
      +'beside it, framed slightly above eye level with the helmet off-centre, a single '
      +'softbox from the left falling off into near black, shot on a 100mm macro lens, '
      +'fine grain.'},
  sign:{cat:'text', icon:'sign', name:'Text in the image', hint:'Posters, signs, packaging.',
    mode:'generate', zonas:[], opt:[], ratio:'3:4',
    prompt:'A vintage screen-printed travel poster for the Atacama desert. The word '
      +'"ATACAMA" runs across the top in tall condensed sans-serif capitals, with '
      +'"ALTIPLANO \u00b7 CHILE" in small spaced letters underneath. Below the type, a lone '
      +'volcano over a white salt flat. Flat four-colour printing in ochre, rust and deep '
      +'teal, visible paper grain, slightly off-register ink.'},

  portrait:{cat:'photo', icon:'portrait', name:'New portrait', hint:'A fresh photo of your character.',
    mode:'generate', zonas:['person'], opt:[], ratio:'3:4',
    prompt:'An editorial magazine portrait of the subject, wearing a black tailored blazer '
      +'over a crisp white shirt, standing in a sunlit concrete gallery with tall windows, '
      +'framed three-quarter length and slightly off-centre, hard side light raking across '
      +'the face and deep shadow on the far side, shot on medium format with an 80mm lens, '
      +'fine grain, colour.'},
  scene:{cat:'photo', icon:'scene', name:'Character in a scene', hint:'Your person, inside another photo.',
    mode:'generate', zonas:['person','scene'], opt:[], ratio:'auto',
    prompt:'A colour photograph of the subject in that setting, wearing that wardrobe, '
      +'framed and lit exactly as the reference is.'},
  pose:{cat:'photo', icon:'pose', name:'Pose my character', hint:'Person + pose, then style or setting.',
    mode:'generate', zonas:['person','pose','style','scene'], opt:['style','scene'], ratio:'auto',
    prompt:'A colour photograph of the subject in that posture, wearing a camel wool '
      +'overcoat over a charcoal roll-neck, on a wide city street at golden hour with the '
      +'traffic blurred behind, framed three-quarter length, warm low sun raking from behind '
      +'and to the left, shallow depth of field, 85mm lens.'},
  cutout:{cat:'photo', icon:'cutout', name:'Transparent cutout', hint:'PNG with a real alpha channel.',
    mode:'generate', zonas:['person'], opt:[], transp:true, ratio:'3:4',
    prompt:'Full body colour cutout of the subject, standing square to camera in a plain '
      +'charcoal t-shirt and dark jeans, even studio light with no cast shadow, clean edges '
      +'around the hair and the clothing.'},
  free:{cat:'photo', icon:'free', name:'Free', hint:'Everything available, nothing assumed.',
    mode:'generate', zonas:['person','pose','style','scene'], opt:['person','pose','style','scene'],
    ratio:'auto', prompt:'', abierto:true},

  look:{cat:'edit', icon:'efecto', name:'Apply a look', hint:'Pick the treatment from a grid.',
    mode:'efecto', zonas:['source'], opt:[], ratio:'auto', prompt:''},
  upscale:{cat:'edit', icon:'escalar', name:'Upscale to 2K', hint:'Redrawn larger, not interpolated.',
    mode:'upscale', zonas:['source'], opt:[], ratio:'auto', prompt:''},

  replace:{cat:'edit', icon:'replace', name:'Replace something', hint:'Name it or paint it, then say what goes there.',
    mode:'inpaint', zonas:['source','extra'], opt:['extra'], ratio:'auto',
    prompt:'A dark green leather biker jacket, zipped all the way up, nothing else visible '
      +'underneath it, the same lighting and the same shadows as the rest of the photograph.'},
};
/* Cada caso viaja con un ejemplo real: las entradas que toma y la hoja de
   contactos de una corrida de verdad con ellas. Asi la primera pantalla ya
   ensena esto + esto = esto, sin esperar un minuto ni adivinar que va en cada
   caja. Los de texto no tienen entradas, solo el resultado. */
const EJ={
  blank:{ins:{}, out:'out_blank.jpg',
    que:'No reference, no photo: the prompt on the left is the whole input.'},
  sign:{ins:{}, out:'out_sign.jpg',
    que:'The words in quotes come out as actual lettering. This is what this model does '
      +'better than most.'},
  portrait:{ins:{person:'person.jpg'}, out:'out_portrait.jpg',
    que:'One close-up in, a full-length editorial portrait out: new wardrobe, new place, '
      +'new light, same face.'},
  scene:{ins:{person:'person.jpg', scene:'scene.jpg'}, out:'out_scene.jpg',
    que:`One face, dropped into someone else's photo: that kitchen, that sweater, that light.`},
  pose:{ins:{person:'person.jpg', style:'style.jpg'}, pose:'hb_arms_cross', out:'out_pose.jpg',
    que:'Three references, one job each: the face, a skeleton for the posture, a beach photo '
      +'for the colour grade. The prompt picks the street.'},
  cutout:{ins:{person:'person.jpg'}, out:'out_cutout.jpg',
    que:'The same photo, cut out onto a real alpha channel.'},
  replace:{ins:{source:'scene.jpg'}, frase:'the yellow sweater', out:'out_replace.jpg',
    que:'The yellow sweater, named in words or painted over with the brush, replaced by a '
      +'green leather jacket; everything else in the photograph is untouched.'},
  free:null,
};
const S={caso:'portrait', img:{}, poseLib:null, ratio:'1:1', esEjemplo:true,
         mascara:null, efecto:null};
const caso=()=>CASOS[S.caso];

/* ---------- zones ---------- */
function construirZonas(){
  const c=caso(), cont=$('#zonas'); cont.innerHTML='';
  c.zonas.forEach((z,i)=>{
    const op=c.opt.includes(z), m=ZONAS[z];
    const d=document.createElement('div');
    d.className='zona'+(op?' opt':''); d.id='z_'+z;
    d.innerHTML=`<div class="n">${svg(m.icon||'upload',21)}</div>
      <div><b>${m.n}${op?' <span class="opt-tag">optional</span>':''}</b><small>${m.d}</small></div>
      <div class="tira" id="t_${z}"></div>`;
    cont.append(d); engancharZona(d,z,z==='person');
  });
  enlazarLib(); repintar();
}
const enlazarLib=()=>document.querySelectorAll('.lnkLib').forEach(a=>a.onclick=e=>{
  e.preventDefault(); e.stopPropagation(); $('#lib').showModal();});
function engancharZona(d,z,multi){
  const inp=document.createElement('input');
  inp.type='file'; inp.accept='image/*'; inp.multiple=!!multi; inp.hidden=true; document.body.append(inp);
  const recibir=async fs=>{
    if(!fs.length)return;
    if(z==='pose')return derivarPose(fs[0]);
    if(multi){S.img[z]=S.img[z]||[]; for(const f of fs)S.img[z].push(await leer(f))}
    else S.img[z]=[await leer(fs[0])];
    // una mascara pintada solo vale para la foto sobre la que se pinto
    if(z==='source'){S.mascara=null; pintarEstadoMask()}
    tocado(); repintar();
  };
  d.onclick=e=>{if(!['BUTTON','A','INPUT','LABEL'].includes(e.target.tagName))inp.click()};
  inp.onchange=()=>{recibir([...inp.files]);inp.value=''};
  d.ondragover=e=>{e.preventDefault();d.classList.add('over')};
  d.ondragleave=()=>d.classList.remove('over');
  d.ondrop=e=>{e.preventDefault();d.classList.remove('over');recibir([...e.dataTransfer.files])};
  d.tabIndex=0;
  d.addEventListener('paste',e=>{const f=[...(e.clipboardData?.files||[])];if(f.length){e.preventDefault();recibir(f)}});
}
async function derivarPose(file){
  const s=$('#z_pose')?.querySelector('small'); const orig=s?.innerHTML;
  if(s)s.textContent='extracting skeleton...';
  try{
    const r=await (await fetch('/api/pose',{method:'POST',body:JSON.stringify({imagen:await leer(file)})})).json();
    if(r.error)alert('Could not extract the pose: '+r.error);
    else{S.img.pose=[r.esqueleto];S.poseLib=null;repintar()}
  }finally{ if(s&&orig){s.innerHTML=orig; enlazarLib()} }
}
function repintar(){
  caso().zonas.forEach(z=>{
    const c=$('#t_'+z); if(!c)return; c.innerHTML='';
    (S.img[z]||[]).forEach((src,i)=>{
      const f=document.createElement('figure'),im=document.createElement('img'),b=document.createElement('button');
      im.src=src; b.textContent='×'; b.type='button';
      b.onclick=e=>{e.stopPropagation();S.img[z].splice(i,1);if(z==='pose')S.poseLib=null;tocado();repintar()};
      f.append(im,b); c.append(f);
    });
  });
}
function construirCampos(){
  const c=caso(), cont=$('#campos'); cont.innerHTML='';
  if(c.mode==='inpaint'){
    cont.innerHTML=`<div class="sec"></div><label>What should be replaced</label>
      <input type="text" id="seleccion" placeholder="the yellow sweater" value="the yellow sweater">
      <div class="hint">Plain words work best: "the jacket", "the hair", "the background".</div>
      <div class="barraPrompt"><button type="button" id="btnPintar">Paint it by hand</button>
        <button type="button" id="btnQuitarMask" hidden>Back to words</button></div>
      <div class="nota" id="notaMask" hidden></div>`;
    $('#btnPintar').onclick=abrirPincel;
    $('#btnQuitarMask').onclick=()=>{S.mascara=null;pintarEstadoMask()};
    pintarEstadoMask();
  }
  const etiqueta = c.mode==='inpaint' ? 'What should go there instead'
    : c.mode==='efecto' ? 'The look'
    : c.mode==='upscale' ? 'What to keep'
    : 'Instruction';
  $('#lblPrompt').innerHTML=`<i>${$('#lblPrompt').dataset.n||'3'}</i>`+etiqueta;
  // en estos dos el prompt no se escribe: uno se escoge y el otro es fijo
  $('#prompt').hidden = c.mode==='efecto';
  $('#barraPrompt').hidden = c.mode==='efecto';
  $('#zonaEfecto').hidden = c.mode!=='efecto';
  $('#zonaEscalar').hidden = c.mode!=='upscale';
  if(c.mode==='efecto') pintarElegido();
  $('#verMask').hidden=c.mode!=='inpaint';
  $('#avInpaint').hidden=c.mode!=='inpaint';
  $('#avanzado').open=!!c.abierto;
}
function aplicarCaso(k){
  S.caso=k; const c=CASOS[k];
  if(CASOS[k].cat!==CAT){
    CAT=CASOS[k].cat;
    [...$('#cats').children].forEach(x=>x.setAttribute('aria-pressed',x.dataset.c===CAT));
    pintarCasos();
  }
  [...$('#casos').children].forEach(b=>b.setAttribute('aria-pressed',b.dataset.k===k));
  $('#prompt').value=c.prompt; $('#transp').checked=!!c.transp;
  S.ratio=c.ratio; marcarRatio();
  const sinEntradas=!c.zonas.length;
  $('#secEntradas').hidden=sinEntradas;
  $('#zonas').hidden=sinEntradas;
  $('#tituloEntradas').innerHTML='<i>2</i>'+(c.mode==='inpaint'?'Image':'Inputs');
  $('#lblPrompt').dataset.n=sinEntradas?'2':'3';
  construirZonas(); construirCampos(); medida();
  if(S.esEjemplo) cargarEjemplo(k); else document.getElementById('notaEjemplo')?.remove();
}
let CAT='photo';
function pintarCasos(){
  const g=$('#casos'); g.innerHTML='';
  Object.entries(CASOS).filter(([,c])=>c.cat===CAT).forEach(([k,c])=>{
    const b=document.createElement('button'); b.className='caso'; b.type='button'; b.dataset.k=k;
    b.setAttribute('aria-pressed', k===S.caso);
    b.innerHTML=`<span class="ico">${svg(c.icon||'free',22)}</span>
      <span><b>${c.name}</b><small>${c.hint}</small></span>`;
    b.onclick=()=>aplicarCaso(k); g.append(b);
  });
}
CATS.forEach(([k,etiqueta,ayuda])=>{
  const b=document.createElement('button'); b.type='button'; b.dataset.c=k;
  b.textContent=etiqueta; b.title=ayuda;
  b.setAttribute('aria-pressed', k===CAT);
  b.onclick=()=>{
    CAT=k;
    [...$('#cats').children].forEach(x=>x.setAttribute('aria-pressed',x.dataset.c===k));
    pintarCasos();
    // al cambiar de grupo se entra por el primero: dejar el caso de otro grupo
    // seleccionado y ningun boton marcado no lo entiende nadie
    const primero=Object.keys(CASOS).find(n=>CASOS[n].cat===k);
    if(primero && CASOS[S.caso].cat!==k) aplicarCaso(primero);
  };
  $('#cats').append(b);
});
pintarCasos();

/* ---------- format ---------- */
const cr=$('#ratios');
['auto','1:1','4:3','3:4','3:2','2:3','16:9','9:16'].forEach(r=>{
  const b=document.createElement('button'); b.className='pill'; b.type='button'; b.dataset.r=r;
  b.textContent=r; b.onclick=()=>{S.ratio=r;marcarRatio();medida()}; cr.append(b);
});
const marcarRatio=()=>[...cr.children].forEach(x=>x.setAttribute('aria-pressed',x.dataset.r===S.ratio));
function medida(){
  const mp=+$('#mp').value;
  if(S.ratio==='auto'){$('#medida').textContent=`~${mp} MP · from the reference`;return}
  const [a,b]=S.ratio.split(':').map(Number),r=a/b,area=mp*1024*1024;
  $('#medida').textContent=`${Math.round(Math.sqrt(area*r)/32)*32} × ${Math.round(Math.sqrt(area/r)/32)*32}`;
}
$('#mp').onchange=medida;
$('#steps').oninput=()=>$('#vSteps').textContent=$('#steps').value;

/* ---------- pose library + loras ---------- */
let POSES=[], filtro='all';
fetch('/api/poses').then(r=>r.json()).then(ls=>{
  POSES=ls;
  const g=$('#libGrid');
  if(!ls.length){g.innerHTML='<div class="hint">Empty. Build it with herramientas/build_pose_library.py</div>';return}
  // filtros: encuadre primero (es lo que decide si la cara sale grande), luego actividad
  const enc=[...new Set(ls.map(p=>p.framing))];
  const grp=[...new Set(ls.map(p=>p.group).filter(Boolean))];
  const f=$('#libFiltros'); f.innerHTML='';
  [['all','All'],...enc.map(e=>[e, ls.find(p=>p.framing===e)?.framing_label||e]),
   ...grp.map(x=>[x, ls.find(p=>p.group===x)?.group_label||x])].forEach(([k,txt])=>{
    const b=document.createElement('button'); b.className='pill'; b.type='button'; b.dataset.f=k;
    b.textContent=txt; b.setAttribute('aria-pressed', k==='all');
    b.onclick=()=>{filtro=k;[...f.children].forEach(x=>x.setAttribute('aria-pressed',x.dataset.f===k));pintarPoses()};
    f.append(b);
  });
  pintarPoses();
});
function pintarPoses(){
  const g=$('#libGrid'); g.innerHTML='';
  POSES.filter(p=>filtro==='all'||p.framing===filtro||p.group===filtro).forEach(p=>{
    const b=document.createElement('button'); b.type='button';
    b.innerHTML=`<img src="${p.thumb}" alt="" data-foto="${p.thumb}" data-skel="${p.skeleton}">
      <span>${p.label}<br>
      <small>${p.framing_label||p.framing}${p.group_label?' · '+p.group_label:''}</small></span>`;
    // la miniatura es la foto (se reconoce de un vistazo); al pasar por encima
    // se ve el esqueleto, que es lo que de verdad recibe el modelo
    const im=b.querySelector('img');
    b.onmouseenter=()=>im.src=im.dataset.skel;
    b.onmouseleave=()=>im.src=im.dataset.foto;
    b.onclick=()=>{S.poseLib=p.id;S.img.pose=[p.skeleton];tocado();repintar();$('#lib').close()};
    g.append(b);
  });
}
$('#lib').onclick=e=>{if(e.target.id==='lib')$('#lib').close()};
fetch('/api/loras').then(r=>r.json()).then(ls=>{
  // la fila solo aparece si hay algo que elegir
  $('#filaLora').hidden = !ls.length;
  ls.forEach(l=>{
    const o=document.createElement('option'); o.value=l; o.textContent=l; $('#lora').append(o);
  });
}).catch(()=>{});

/* ---------- status ---------- */
let pesosListos=false;
async function tick(){
  let e;
  try{ e=await (await fetch('/api/estado')).json() }
  catch(_){
    // el servidor no responde: es lo unico que la pagina no puede arreglar sola
    ponerEstado('err','app not responding');
    $('#setup').innerHTML=`<div class="nota mal"><b>The app stopped responding.</b><br>
      It runs as a local server; if you closed its window, start it again with
      <code>RUN.bat</code> and reload this page.</div>`;
    $('#panel').hidden=true; return;
  }
  const p=e.perfil, m=e.motor;
  $('#chipProfile').textContent=`${p.acelerador} · ${p.vram_gb} GB · ${p.dtype}`;

  if(m.error)            ponerEstado('err','model failed');
  else if(m.cargando)    ponerEstado('busy','loading model');
  else if(m.listo)       ponerEstado('ok','ready');
  else if(e.descarga.activa) ponerEstado('busy','downloading');
  else if(e.pesos_listos)ponerEstado('','model on disk');
  else                   ponerEstado('','weights missing');

  [...$('#mp').options].forEach(o=>o.disabled=(+o.value>(p.res_max*p.res_max)/(1024*1024)+0.01));
  const montados=(e.recursos||[]).filter(r=>r.montado).map(r=>r.etiqueta);
  const hw=`${p.acelerador} · ${p.vram_gb} GB · profile ${p.nivel} · ${p.dtype}`
    +(p.offload!=='none'?` · offload ${p.offload}`:'')
    +(montados.length?` · mounted: ${montados.join(', ')}`:'');
  if($('#cfgHw')) $('#cfgHw').textContent=hw;

  const s=$('#setup'); pesosListos=e.pesos_listos;
  if(e.descarga.activa){
    const pct=e.descarga.total_gb?(e.descarga.gb/e.descarga.total_gb*100):0;
    s.innerHTML=`<h2>Downloading the model</h2>
      <div class="barra"><i style="width:${pct.toFixed(1)}%"></i></div>
      <div class="hint num">${e.descarga.gb} / ${e.descarga.total_gb} GB · ${pct.toFixed(0)}%</div>
      <div class="hint">You can close this and come back — it resumes where it left off.</div>`;
    $('#panel').hidden=true;
  } else if(!e.pesos_listos){
    s.innerHTML=`<h2>One thing left</h2>
      <div class="hint">The model weights (~31 GB) are not on disk yet. They download once
      and stay in <code>modelos\</code>.</div>
      ${e.descarga.error?`<div class="nota mal"><b>The download failed.</b><br>
        ${e.descarga.error}<br>Check your connection and press the button again —
        nothing already downloaded is lost.</div>`:''}
      <button class="go" type="button" onclick="fetch('/api/descargar',{method:'POST'})">
        Download the model</button>`;
    $('#panel').hidden=true;
  } else if(FLOJO.includes(p.nivel) && !perritoVisto()){
    s.innerHTML=pantallaPerrito(p);
    $('#igualmente').onclick=()=>{
      try{ localStorage.setItem('qs_perrito','visto') }catch(_){ PERRITO_SESION=true }
      PERRITO_SESION=true; tick();
    };
    $('#panel').hidden=true;
  } else {
    s.innerHTML='';
    if(m.error) s.innerHTML=`<div class="nota mal"><b>The model could not be loaded.</b><br>
      ${m.error}<br>If it mentions memory, close anything else using the GPU and reload.</div>`;
    else if(m.cargando) s.innerHTML=`<div class="hint">Loading the model into memory — about
      30 seconds the first time.</div>`;
    if(m.aviso_vram) s.innerHTML+=`<div class="nota"><b>Something else is using the GPU.</b><br>
      ${m.aviso_vram}</div>`;
    (e.avisos_perfil||[]).forEach(a=>s.innerHTML+=`<div class="nota">${a}</div>`);
    $('#panel').hidden=false;
  }
}
/* El perro se dibuja aqui y no es un archivo: la app tiene que funcionar sin
   red y sin que nadie borre un png de una carpeta. */
function svgPerrito(){
  return `<svg viewBox="0 0 200 200" role="img" aria-label="a puppy making sad eyes">
    <ellipse cx="46" cy="96" rx="25" ry="42" fill="#8d6244" transform="rotate(-12 46 96)"/>
    <ellipse cx="154" cy="96" rx="25" ry="42" fill="#8d6244" transform="rotate(12 154 96)"/>
    <ellipse cx="100" cy="98" rx="60" ry="56" fill="#b8865f"/>
    <ellipse cx="100" cy="128" rx="34" ry="27" fill="#e3c3a3"/>
    <ellipse cx="76" cy="92" rx="17" ry="19" fill="#fff"/>
    <ellipse cx="124" cy="92" rx="17" ry="19" fill="#fff"/>
    <ellipse cx="78" cy="95" rx="11.5" ry="13" fill="#2b1d14"/>
    <ellipse cx="122" cy="95" rx="11.5" ry="13" fill="#2b1d14"/>
    <circle cx="74" cy="90" r="4.4" fill="#fff"/>
    <circle cx="118" cy="90" r="4.4" fill="#fff"/>
    <circle cx="82" cy="101" r="2.1" fill="#fff" opacity=".75"/>
    <circle cx="126" cy="101" r="2.1" fill="#fff" opacity=".75"/>
    <path d="M64 70 q12 -7 24 1" stroke="#6b4630" stroke-width="4.5" fill="none"
      stroke-linecap="round"/>
    <path d="M136 70 q-12 -7 -24 1" stroke="#6b4630" stroke-width="4.5" fill="none"
      stroke-linecap="round"/>
    <ellipse cx="100" cy="118" rx="9.5" ry="7" fill="#2b1d14"/>
    <path d="M100 125 v7" stroke="#2b1d14" stroke-width="3.4" stroke-linecap="round"/>
    <path d="M100 132 q-11 10 -19 1" stroke="#2b1d14" stroke-width="3.4" fill="none"
      stroke-linecap="round"/>
    <path d="M100 132 q11 10 19 1" stroke="#2b1d14" stroke-width="3.4" fill="none"
      stroke-linecap="round"/>
    <ellipse cx="62" cy="78" rx="5" ry="3" fill="#fff" opacity=".28"/>
  </svg>`;
}
function pantallaPerrito(p){
  const imposible = p.nivel==='INVIABLE';
  const cuerpo = imposible
    ? `<p>This machine cannot run the model in any useful way. A 7B diffusion
         transformer needs a GPU with room for it, and there is not one here.</p>
       <p>Maybe invest in your future and get something more powerful?
         The puppy would appreciate it.</p>`
    : `<p>It will run here, but slowly, and 4-bit quantisation will cost you some
         quality. Expect minutes per image rather than seconds.</p>
       <p>Maybe invest in your future and get something more powerful?
         The puppy would appreciate it.</p>`;
  return `<div class="perrito">${svgPerrito()}
    <h2>${imposible?'This is not going to work':'This is going to hurt'}</h2>
    ${cuerpo}
    <div class="ficha num">${p.acelerador} · ${p.vram_gb} GB · profile ${p.nivel}</div>
    <button class="go" type="button" id="igualmente">
      ${imposible?'Let me try anyway':'I know, let me in'}</button>
  </div>`;
}
const FLOJO=['INVIABLE','MINIMO'];
let PERRITO_SESION=false;
function perritoVisto(){
  if(PERRITO_SESION) return true;
  try{ return localStorage.getItem('qs_perrito')==='visto' }catch(_){ return false }
}
function ponerEstado(clase, txt){
  const c=$('#chipEngine'); c.className='chip'+(clase?' '+clase:'');
  c.innerHTML=`<i class="pt"></i><span>${txt}</span>`;
}
tick(); setInterval(tick,2500);

/* ---------- results, with before/after ---------- */
function tarjeta(im, antes){
  const f=document.createElement('figure');
  if(antes){
    const d=document.createElement('div'); d.className='ba';
    d.innerHTML=`<img src="${antes}" alt="before"><div class="after"><img src="${im.archivo}" alt="after"></div>
      <div class="handle"></div><span class="tag l">before</span><span class="tag r">after</span>`;
    const mover=ev=>{
      const r=d.getBoundingClientRect();
      const x=Math.min(Math.max((ev.clientX-r.left)/r.width,0),1);
      d.querySelector('.after').style.clipPath=`inset(0 0 0 ${x*100}%)`;
      d.querySelector('.handle').style.left=`${x*100}%`;
    };
    let arr=false;
    d.onpointerdown=e=>{arr=true;d.setPointerCapture(e.pointerId);mover(e)};
    d.onpointermove=e=>{if(arr)mover(e)};
    d.onpointerup=e=>{arr=false;try{d.releasePointerCapture(e.pointerId)}catch(_){}};
    f.append(d);
  }else{
    const i=document.createElement('img'); i.src=im.archivo; i.loading='lazy';
    i.onclick=()=>{$('#lupaImg').src=im.archivo;$('#lupa').showModal()};
    f.append(i);
  }
  const c=document.createElement('figcaption');
  const nombre=(im.archivo||'').split('/').pop()||'qwenstudio.png';
  c.innerHTML=`<span>${im.seed!==undefined?'seed '+im.seed:''}${im.tam?' · '+im.tam:''}</span>
    <span class="acciones"><a href="#" class="cmp">compare</a>
      <a class="iconobtn" href="${im.archivo}" download="${nombre}"
         title="Download this image">${svg('descarga',15)}</a></span>`;
  c.querySelector('.cmp').onclick=e=>{e.preventDefault();elegirComparar(im.archivo,c.querySelector('.cmp'))};
  f.append(c); f.dataset.src=im.archivo; return f;
}

/* ---------- la galeria de efectos ---------- */
let EFECTOS=[], efFiltro='all';
function pintarElegido(){
  const e=EFECTOS.find(x=>x.id===S.efecto);
  if(!$('#efNombre')) return;
  $('#efNombre').textContent = e ? e.nombre : 'No look picked yet';
  $('#efDesc').textContent = e ? e.grupo : 'Open the grid and choose one.';
  $('#efMini').innerHTML = e && e.thumb ? `<img src="${e.thumb}" alt="">` : '';
  $('#btnEf').textContent = e ? 'Change' : 'Pick a look';
}
function pintarEfectos(){
  const g=$('#efGrid'); g.innerHTML='';
  EFECTOS.filter(e=>efFiltro==='all'||e.grupo===efFiltro).forEach(e=>{
    const b=document.createElement('button'); b.type='button';
    b.setAttribute('aria-pressed', e.id===S.efecto);
    if(!e.listo) b.disabled=true;
    b.innerHTML=(e.thumb ? `<img src="${e.thumb}" alt="">`
                 : `<span class="sinthumb">no thumbnail yet</span>`)
      +`<span>${e.nombre}<small>${e.listo?e.grupo:'needs '+e.lora}</small></span>`;
    b.onclick=()=>{S.efecto=e.id;pintarEfectos();pintarElegido();$('#ef').close()};
    g.append(b);
  });
}
fetch('/api/efectos').then(r=>r.json()).then(es=>{
  EFECTOS=es;
  const grupos=['all',...new Set(es.map(e=>e.grupo))];
  const f=$('#efFiltros'); f.innerHTML='';
  grupos.forEach(k=>{
    const b=document.createElement('button'); b.className='pill'; b.type='button';
    b.dataset.f=k; b.textContent=k==='all'?'All':k;
    b.setAttribute('aria-pressed',k==='all');
    b.onclick=()=>{efFiltro=k;
      [...f.children].forEach(x=>x.setAttribute('aria-pressed',x.dataset.f===k));
      pintarEfectos()};
    f.append(b);
  });
  const faltan=es.filter(e=>!e.thumb).length;
  $('#efNota').textContent = faltan
    ? `${faltan} without a thumbnail \u2014 run herramientas/generar_efectos.py` : '';
  pintarEfectos(); pintarElegido();
}).catch(()=>{});
$('#btnEf') && ($('#btnEf').onclick=()=>$('#ef').showModal());
$('#efCerrar').onclick=()=>$('#ef').close();
$('#ef').onclick=e=>{if(e.target.id==='ef')$('#ef').close()};

/* ---------- la galeria ---------- */
function cuando(ts){
  const s=(Date.now()/1000)-ts;
  if(s<90) return 'just now';
  if(s<5400) return Math.round(s/60)+' min ago';
  if(s<172800) return Math.round(s/3600)+' h ago';
  return new Date(ts*1000).toLocaleDateString();
}
async function abrirGaleria(){
  const g=$('#glGrid'); g.innerHTML='<div class="hint">Reading the folder…</div>';
  $('#gl').showModal();
  let d;
  try{ d=await (await fetch('/api/galeria')).json(); }
  catch(_){ g.innerHTML='<div class="nota mal">Could not read the folder.</div>'; return; }
  const items=d.items||[];
  $('#glCuenta').textContent = d.total
    ? `${items.length} of ${d.total} file${d.total===1?'':'s'}` : '';
  if(!items.length){
    g.innerHTML='<div class="hint">Nothing here yet. Generate something and it lands '+
      'in this folder.</div>';
    return;
  }
  g.innerHTML='';
  items.forEach(it=>{
    const f=document.createElement('figure');
    const im=document.createElement('img');
    im.src=it.archivo; im.alt=it.nombre; im.loading='lazy';
    im.onclick=()=>{$('#lupaImg').src=it.archivo;$('#lupa').showModal()};
    const c=document.createElement('figcaption');
    c.innerHTML=`<span class="tipo">${it.clase}</span>
      <span class="num" style="flex:1">${cuando(it.cuando)}</span>
      <a href="${it.archivo}" download="${it.nombre}" title="Download">
        ${svg('descarga',15)}</a>`;
    f.append(im,c); g.append(f);
  });
}
$('#btnGaleria').onclick=abrirGaleria;
$('#glCerrar').onclick=()=>$('#gl').close();
$('#gl').onclick=e=>{if(e.target.id==='gl')$('#gl').close()};
$('#glCarpeta').onclick=async()=>{
  const b=$('#glCarpeta'); b.disabled=true;
  try{
    const r=await (await fetch('/api/abrir_carpeta',{method:'POST'})).json();
    if(r.error) alert(r.error+'\n\n'+r.carpeta);
  }finally{ b.disabled=false }
};

/* ---------- the mask brush ----------
   Segmentar por texto acierta con lo que tiene nombre. Para media manga o una
   sombra concreta no hay frase, y el pincel es la unica via. */
function pintarEstadoMask(){
  const hay=!!S.mascara, n=$('#notaMask');
  if(!n) return;
  n.hidden=!hay; $('#btnQuitarMask').hidden=!hay;
  $('#seleccion').disabled=hay;
  $('#btnPintar').textContent=hay?'Edit the mask':'Paint it by hand';
  if(hay) n.innerHTML='<b>Using the mask you painted.</b> The words above are ignored '+
    'while it is here.';
  // grow y threshold pertenecen al segmentador; con el pincel no tocan nada
  ['grow','thr'].forEach(id=>{
    const c=$('#'+id); if(!c) return;
    c.disabled=hay;
    const fila=c.closest('div'); if(fila) fila.style.opacity=hay?'.45':'';
  });
  const av=$('#avisoMaskAv');
  if(av) av.hidden=!hay;
}
let MK={ctx:null, pintando:false, modo:'pintar', tam:60, ratio:1};
function abrirPincel(){
  const src=(S.img.source||[])[0];
  if(!src){alert('Add the image you want to edit first.');return}
  const img=$('#mkImg'), cv=$('#mkCv');
  img.onload=()=>{
    cv.width=img.naturalWidth; cv.height=img.naturalHeight;
    MK.ctx=cv.getContext('2d');
    MK.ctx.clearRect(0,0,cv.width,cv.height);
    MK.ctx.lineCap='round'; MK.ctx.lineJoin='round'; MK.ctx.strokeStyle='#ff3b30';
    if(S.mascara){
      // reabrir lo ya pintado: el blanco del archivo vuelve a ser rojo visible
      const prev=new Image();
      prev.onload=()=>{
        const t=document.createElement('canvas'); t.width=cv.width; t.height=cv.height;
        const tc=t.getContext('2d'); tc.drawImage(prev,0,0,cv.width,cv.height);
        const d=tc.getImageData(0,0,cv.width,cv.height);
        for(let i=0;i<d.data.length;i+=4){
          const on=d.data[i]>127;
          d.data[i]=255; d.data[i+1]=59; d.data[i+2]=48; d.data[i+3]=on?255:0;
        }
        MK.ctx.putImageData(d,0,0);
      };
      prev.src=S.mascara;
    }
    $('#mk').showModal();
  };
  img.src=src;
}
function mkPos(ev){
  const r=$('#mkCv').getBoundingClientRect();
  return [(ev.clientX-r.left)/r.width*$('#mkCv').width,
          (ev.clientY-r.top)/r.height*$('#mkCv').height];
}
function mkTrazo(ev){
  const c=MK.ctx; if(!c) return;
  const [x,y]=mkPos(ev);
  c.globalCompositeOperation = MK.modo==='borrar' ? 'destination-out' : 'source-over';
  c.lineWidth=MK.tam;
  c.lineTo(x,y); c.stroke();
  c.beginPath(); c.moveTo(x,y);
}
(function(){
  const cv=$('#mkCv');
  cv.onpointerdown=e=>{e.preventDefault();MK.pintando=true;cv.setPointerCapture(e.pointerId);
    MK.ctx.beginPath();const[x,y]=mkPos(e);MK.ctx.moveTo(x,y);mkTrazo(e)};
  cv.onpointermove=e=>{if(MK.pintando)mkTrazo(e)};
  cv.onpointerup=e=>{MK.pintando=false;MK.ctx.beginPath();
    try{cv.releasePointerCapture(e.pointerId)}catch(_){}};
  cv.onpointerleave=()=>{MK.pintando=false;MK.ctx&&MK.ctx.beginPath()};
  const modo=m=>{MK.modo=m;
    $('#mkPintar').setAttribute('aria-pressed',m==='pintar');
    $('#mkBorrar').setAttribute('aria-pressed',m==='borrar')};
  $('#mkPintar').onclick=()=>modo('pintar');
  $('#mkBorrar').onclick=()=>modo('borrar');
  $('#mkTam').oninput=e=>{MK.tam=+e.target.value;$('#mkTamV').textContent=MK.tam+' px'};
  $('#mkLimpiar').onclick=()=>MK.ctx&&MK.ctx.clearRect(0,0,$('#mkCv').width,$('#mkCv').height);
  $('#mkCerrar').onclick=()=>$('#mk').close();
  $('#mkUsar').onclick=()=>{
    const cv=$('#mkCv');
    // lo pintado sale blanco sobre negro, que es lo que espera el servidor
    const fuera=document.createElement('canvas');
    fuera.width=cv.width; fuera.height=cv.height;
    const fc=fuera.getContext('2d');
    // el color del pincel es para verlo; lo que sale es blanco donde hay pintura
    // y negro donde no, leido del alfa, no del color
    const src=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
    const out=fc.createImageData(cv.width,cv.height);
    let algo=false;
    for(let i=0;i<src.length;i+=4){
      const v = src[i+3]>10 ? 255 : 0;
      if(v) algo=true;
      out.data[i]=out.data[i+1]=out.data[i+2]=v; out.data[i+3]=255;
    }
    if(!algo){alert('Nothing is painted yet.');return}
    fc.putImageData(out,0,0);
    S.mascara=fuera.toDataURL('image/png');
    pintarEstadoMask(); $('#mk').close();
  };
  $('#mk').onclick=e=>{if(e.target.id==='mk')$('#mk').close()};
})();

/* ---------- actions ---------- */
const comunes=()=>({prompt:$('#prompt').value, steps:+$('#steps').value, seed:+$('#seed').value,
  variantes:+$('#variants').value, megapixeles:+$('#mp').value,
  lora:$('#lora').value||null, fuerza_lora:+$('#loraw').value});

$('#verMask').onclick=async()=>{
  const src=(S.img.source||[])[0];
  if(!src){alert('Add the image you want to edit first.');return}
  const b=$('#verMask'); b.disabled=true;
  b.textContent=S.mascara?'Building the preview...':'Segmenting...';
  try{
    const r=await (await fetch('/api/mascara',{method:'POST',body:JSON.stringify({
      imagen:src, frase:$('#seleccion').value, mascara:S.mascara||null,
      crecer:+$('#grow').value, umbral:+$('#thr').value})})).json();
    if(r.error){alert(r.error);return}
    $('#vacio').hidden=true;
    $('#gal').prepend(tarjeta({archivo:r.preview, tam:'covers '+r.cobertura+'%'}, src));
  }finally{b.disabled=false;b.textContent='Preview the selection'}
};

$('#go').onclick=async()=>{
  if(!pesosListos){alert('The weights are still missing.');return}
  const c=caso(), b=$('#go');
  const falta=c.zonas.filter(z=>!c.opt.includes(z)&&!(S.img[z]||[]).length);
  if(falta.length){alert('Missing: '+falta.map(z=>ZONAS[z].n).join(', '));return}
  const t0=Date.now(); b.disabled=true;
  const tic=setInterval(()=>b.textContent=`Generating... ${((Date.now()-t0)/1000).toFixed(0)}s`,250);
  try{
    let r, antes=null;
    if(c.mode==='efecto'){
      if(!S.efecto){alert('Pick a look first.');return}
      antes=(S.img.source||[])[0];
      r=await (await fetch('/api/efecto',{method:'POST',body:JSON.stringify({
        imagen:antes, efecto:S.efecto, steps:+$('#steps').value,
        seed:+$('#seed').value})})).json();
    }else if(c.mode==='upscale'){
      antes=(S.img.source||[])[0];
      r=await (await fetch('/api/reescalar',{method:'POST',body:JSON.stringify({
        imagen:antes, steps:+$('#steps').value, seed:+$('#seed').value})})).json();
    }else if(c.mode==='inpaint'){
      antes=(S.img.source||[])[0];
      r=await (await fetch('/api/inpaint',{method:'POST',body:JSON.stringify({...comunes(),
        imagen:antes, frase:$('#seleccion').value, mascara:S.mascara||null,
        referencias:S.img.extra||[],
        crecer:+$('#grow').value, difuminado:+$('#feather').value,
        umbral:+$('#thr').value, padding:+$('#pad').value})})).json();
    }else{
      // sin "antes": la escena es una referencia, no una version previa de
      // este resultado. Para comparar entre generaciones esta el boton compare.
      antes=null;
      r=await (await fetch('/api/generar',{method:'POST',body:JSON.stringify({...comunes(),
        personas:S.img.person||[], escena:(S.img.scene||[])[0]||null,
        estilo:(S.img.style||[])[0]||null,
        estilo_modo:(document.querySelector('input[name=em]:checked')||{}).value||'look',
        pose_lib:S.poseLib, pose_url:S.poseLib?null:((S.img.pose||[])[0]||null),
        ratio:S.ratio, transparencia:$('#transp').checked})})).json();
    }
    if(r.error){alert('Error: '+r.error);return}
    $('#vacio').hidden=true;
    $('#avisos').innerHTML=(r.avisos||[]).map(a=>`<div class="nota">${a}</div>`).join('');
    $('#verPrompt').hidden=false;
    $('#verPrompt').textContent=(r.orden?'Order: '+r.orden.join('  |  ')+'\n\n':'')
      +(r.crop?`crop ${r.crop} -> generated ${r.generado}\n\n`:'')+(r.prompt||'');
    r.imagenes.forEach(im=>$('#gal').prepend(tarjeta(im, antes)));
    if(r.resumen) $('#gal').prepend(tarjeta({archivo:r.resumen, tam:'recipe'}, null));
  }catch(e){alert('Failed: '+e)}
  finally{clearInterval(tic);b.disabled=false;b.textContent='Generate'}
};
let pendiente=null, pendienteEl=null;
function elegirComparar(src, el){
  if(!pendiente){
    pendiente=src; pendienteEl=el; el.textContent='comparing…'; el.style.color='var(--link)';
    return;
  }
  if(pendiente===src){                       // clic en el mismo: cancelar
    el.textContent='compare'; el.style.color=''; pendiente=null; pendienteEl=null; return;
  }
  const card=tarjeta({archivo:src, tam:'comparison'}, pendiente);
  $('#gal').prepend(card);
  if(pendienteEl){pendienteEl.textContent='compare'; pendienteEl.style.color=''}
  pendiente=null; pendienteEl=null;
}

$('#lupa').onclick=()=>$('#lupa').close();

/* ---------- prompt library ---------- */
fetch('/api/prompts').then(r=>r.json()).then(cats=>{
  const b=$('#plBody');
  cats.forEach(c=>{
    const h=document.createElement('h4'); h.textContent=c.categoria; b.append(h);
    c.items.forEach(it=>{
      const x=document.createElement('button'); x.type='button';
      x.innerHTML=`<b>${it.etiqueta}</b>${it.texto}`;
      x.onclick=()=>{
        const destino = (caso().mode==='inpaint' && c.categoria==='What to select')
          ? $('#seleccion') : $('#prompt');
        if(!destino) return;
        destino.value = destino.value.trim()
          ? (destino===$('#seleccion') ? it.texto : destino.value.trim()+' '+it.texto)
          : it.texto;
        $('#pl').close();
      };
      b.append(x);
    });
  });
}).catch(()=>{});
$('#btnMejorar').onclick=async()=>{
  const t=$('#prompt').value.trim();
  if(!t){alert('Write a few words first and this will turn them into a full prompt.');return}
  const b=$('#btnMejorar'); b.disabled=true; const antes=b.textContent;
  b.textContent='Rewriting...';
  try{
    const r=await (await fetch('/api/mejorar_prompt',{method:'POST',
      body:JSON.stringify({prompt:t})})).json();
    if(r.error){alert(r.error);return}
    S.promptPrevio=r.antes;              // un solo paso atras, que es lo que hace falta
    $('#prompt').value=r.texto;
    $('#btnDeshacer').hidden=false;
  }finally{ b.disabled=false; b.textContent=antes }
};
$('#btnDeshacer').onclick=()=>{
  if(S.promptPrevio!==undefined) $('#prompt').value=S.promptPrevio;
  $('#btnDeshacer').hidden=true;
};
$('#btnPl').onclick=()=>$('#pl').showModal();
$('#pl').onclick=e=>{if(e.target.id==='pl')$('#pl').close()};
$('#btnClear').onclick=()=>{$('#prompt').value=''};

/* ---------- describe an image with the VLM ---------- */
$('#btnDesc').onclick=async()=>{
  // usa la primera imagen que haya cargada, en el orden en que importan
  const src=(S.img.source||[])[0]||(S.img.scene||[])[0]||(S.img.person||[])[0];
  if(!src){alert('Load an image first — person, scene or the one you are editing.');return}
  const b=$('#btnDesc'); b.disabled=true; const t0=Date.now();
  const tic=setInterval(()=>b.textContent=`Reading... ${((Date.now()-t0)/1000).toFixed(0)}s`,250);
  try{
    const r=await (await fetch('/api/describir',{method:'POST',
      body:JSON.stringify({imagen:src, tarea:'prompt'})})).json();
    if(r.error){alert(r.error);return}
    $('#prompt').value=r.texto;
  }catch(e){alert('Failed: '+e)}
  finally{clearInterval(tic);b.disabled=false;b.textContent='Describe an image'}
};

/* ---------- settings ---------- */
const OPCIONES=[
 ['describir_escena','check','Describe the scene automatically',
  'Measured: with a scene loaded and a prompt that does not mention it, the scene is ignored. This reads it with Qwen3-VL and adds the description. Costs ~6 s.'],
 ['resumen','check','Contact sheet per run','Saves one image with the inputs, the operator and the result.'],
 ['mantener_montado','check','Keep models mounted',
  'Skips unmounting between blocks. Faster for batches, but three models will not fit at once — turn it off if generation stalls.'],
 ['steps','num','Default steps','25 is what ComfyUI recommends, 40 what the model card says.'],
 ['megapixeles','num','Default quality (MP)','1 is fast, 4 is 2K native.'],
 ['vlm_bits','sel','Vision model precision','4-bit uses ~7 GB, 8-bit ~13 GB and describes a little better.'],
 ['vae','vae','Decoder',
  'Measured on the same seed: the HDR decoder gives +19% saturation and +27% edge energy with contrast and exposure unchanged. It interprets rather than reproduces — SSIM drops from 0.958 to 0.944 — so switch to stock for a faithful reproduction. Needs modelos/vae_hdr.safetensors.'],
];
let AJ={};
function aplicarTema(t){
  try{ localStorage.setItem('qs_tema', t) }catch(_){}
  if(t==='auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', t);
  document.querySelectorAll('#tema .pill').forEach(b=>
    b.setAttribute('aria-pressed', b.dataset.t===t));
}
function pintarAjustes(){
  const b=$('#cfgBody'); b.innerHTML='';
  OPCIONES.forEach(([k,tipo,tit,desc])=>{
    const row=document.createElement('label'); row.className='opt';
    let ctrl;
    if(tipo==='check'){ ctrl=`<input type="checkbox" id="aj_${k}" ${AJ[k]?'checked':''}>` }
    else if(tipo==='sel'){ ctrl=`<select id="aj_${k}"><option value="4"${AJ[k]==4?' selected':''}>4-bit</option>
      <option value="8"${AJ[k]==8?' selected':''}>8-bit</option></select>` }
    else if(tipo==='vae'){ ctrl=`<select id="aj_${k}">
      <option value="hdr"${AJ[k]==='hdr'?' selected':''}>HDR</option>
      <option value="stock"${AJ[k]==='stock'?' selected':''}>Stock</option></select>` }
    else { ctrl=`<input type="number" id="aj_${k}" value="${AJ[k]}" min="1" max="60">` }
    row.innerHTML = tipo==='check'
      ? `${ctrl}<div><b>${tit}</b><small>${desc}</small></div>`
      : `<div><b>${tit}</b><small>${desc}</small></div>${ctrl}`;
    b.append(row);
    const el=row.querySelector('#aj_'+k);
    el.onchange=()=>{
      const v = tipo==='check' ? el.checked : (tipo==='vae' ? el.value : +el.value);
      AJ[k]=v;
      fetch('/api/ajustes',{method:'POST',body:JSON.stringify({[k]:v})});
      if(k==='steps') $('#steps').value=v, $('#vSteps').textContent=v;
      if(k==='megapixeles') $('#mp').value=v, medida();
    };
  });
}
/* ---------- the worked example of the selected use case ----------
   Una app debe abrir mostrando lo que hace, no un formulario vacio. Las
   entradas y el resultado son de una corrida real, no un montaje. */
async function aUrlDatos(url){
  const b=await (await fetch(url)).blob();
  return new Promise(r=>{const x=new FileReader();x.onload=()=>r(x.result);x.readAsDataURL(b)});
}
function tocado(){
  if(!S.esEjemplo) return;
  S.esEjemplo=false;
  document.getElementById('notaEjemplo')?.remove();
  document.getElementById('figEjemplo')?.remove();
  $('#vacio').hidden=$('#gal').children.length>0;
}
function limpiarEjemplo(){
  S.esEjemplo=false; S.img={}; S.poseLib=null; repintar();
  document.getElementById('notaEjemplo')?.remove();
  document.getElementById('figEjemplo')?.remove();
  $('#vacio').hidden=$('#gal').children.length>0;
}
async function cargarEjemplo(k){
  const e=EJ[k];
  document.getElementById('notaEjemplo')?.remove();
  document.getElementById('figEjemplo')?.remove();
  S.img={}; S.poseLib=null; S.mascara=null;
  if(!e){ S.esEjemplo=true; repintar(); $('#vacio').hidden=$('#gal').children.length>0; return; }
  try{
    for(const [z,f] of Object.entries(e.ins)) S.img[z]=[await aUrlDatos('/ejemplos/'+f)];
    if(e.pose){ S.poseLib=e.pose; S.img.pose=['/poses/'+e.pose+'.png']; }
    if(e.frase && $('#seleccion')) $('#seleccion').value=e.frase;
    S.esEjemplo=true; repintar();

    const n=document.createElement('div');
    n.className='nota ejemplo'; n.id='notaEjemplo';
    n.innerHTML=`<span><b>Example.</b> ${e.que} Press Generate to run it yourself,
      or drop your own photos over these.</span>
      <button type="button" class="ghost" id="quitaEjemplo">Start empty</button>`;
    $('#zonas').before(n);
    $('#quitaEjemplo').onclick=limpiarEjemplo;

    // el resultado real de esas mismas entradas, ya calculado
    const f=document.createElement('figure'); f.id='figEjemplo';
    const im=document.createElement('img'); im.src='/ejemplos/'+e.out; im.alt='example result';
    im.onclick=()=>{$('#lupaImg').src=im.src;$('#lupa').showModal()};
    const cap=document.createElement('figcaption');
    cap.innerHTML='<span>Example · inputs and result</span><span>generated on this machine</span>';
    f.append(im,cap); $('#gal').prepend(f); $('#vacio').hidden=true;
  }catch(_){ }
}

fetch('/api/ajustes').then(r=>r.json()).then(a=>{
  AJ=a; pintarAjustes();
  $('#steps').value=a.steps; $('#vSteps').textContent=a.steps;
  $('#mp').value=a.megapixeles; medida();
});
let temaGuardado='light';
try{ temaGuardado=localStorage.getItem('qs_tema')||'light' }catch(_){}
aplicarTema(temaGuardado);
document.querySelectorAll('#tema .pill').forEach(b=>b.onclick=()=>aplicarTema(b.dataset.t));
$('#btnAjustes').onclick=()=>$('#cfg').showModal();
$('#cfgClose').onclick=()=>$('#cfg').close();
$('#cfg').onclick=e=>{if(e.target.id==='cfg')$('#cfg').close()};

/* Enlaces directos: ?caso=pose abre la app en ese camino y ?abrir=poses con
   la libreria ya desplegada. Sirve para mandarle a alguien el sitio exacto y
   para que un agente diga "abrelo aqui" en vez de explicar tres clics. */
(function(){
  const q=new URLSearchParams(location.search);
  const c=q.get('caso');
  aplicarCaso(CASOS[c] ? c : 'portrait');
  const t=q.get('tema');
  if(t==='dark'||t==='light'||t==='auto') aplicarTema(t);
  const abrir=q.get('abrir');
  if(abrir==='mask') setTimeout(abrirPincel, 500);
  else if(abrir==='galeria') setTimeout(abrirGaleria, 400);
  else {
    const d={poses:'#lib', prompts:'#pl', ajustes:'#cfg'}[abrir];
    if(d) setTimeout(()=>$(d)?.showModal(), 350);
  }
})();
</script></body></html>
"""
