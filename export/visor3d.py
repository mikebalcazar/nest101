"""#073 — El mueble en 3D, en un archivo suelto que se abre en el celular.

Lo que pidió Mike: **un archivo que se mande y se vea girando en el teléfono
del instalador, sin internet y sin instalar nada.** No un servidor, no una app.

Por qué un HTML y no un formato 3D:

- `.usdz` es de Apple: el iPhone lo abre de un toque, y el Android **no lo abre
  nunca**. No hay app de fábrica que lo lea.
- `.glb` es el de Google: el Android tampoco lo abre tocándolo — pide app o un
  enlace a un servidor, que es justo lo que no queremos.

Lo único que los dos teléfonos traen de fábrica y sabe dibujar en 3D es **el
navegador**. Así que el visor ES el archivo: un HTML con el motor 3D, la
geometría y los colores adentro. Se manda por WhatsApp, se abre, se gira con el
dedo. Sin red, sin cuenta, sin instalar.

Pesa ~800 KB, casi todo el motor. Es el mismo Three.js que ya viaja dentro de la
app —no se agrega ninguna librería— y la misma geometría del 3D de la pantalla:
las mismas piezas, los mismos colores de material, los mismos chaflanes.

El motor viene en versión «módulo», que el navegador **no carga desde un archivo
local** (lo bloquea por seguridad de origen). Por eso `_motor()` le da la vuelta:
convierte su `export{...}` final en un `window.THREE = {...}` y queda un script
normal, que sí corre con doble clic y desde WhatsApp.
"""
from __future__ import annotations

import json
import os
import re
from typing import List

from core.config import Estandar
from core.modelos import Gabinete
from core import iso as ISO

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MOTOR = None


def _ruta_three() -> str:
    for c in (os.path.join(RAIZ, "ui", "vendor", "three.module.min.js"),
              os.path.join(RAIZ, "vendor", "three.module.min.js"),
              os.path.join(os.path.dirname(RAIZ), "ui", "vendor", "three.module.min.js")):
        if os.path.isfile(c):
            return c
    raise FileNotFoundError("no encuentro three.module.min.js")


def _motor() -> str:
    """Three.js como script clásico, para que corra desde un archivo local.

    Un `<script type="module">` que importa de `file://` lo bloquea el navegador
    —origen nulo—, y ahí se acaba el visor sin decir por qué. Se cambia el
    `export{a as Scene,...}` del final por un objeto global y el problema
    desaparece: ya no hay módulos que importar.
    """
    global _MOTOR
    if _MOTOR:
        return _MOTOR
    src = open(_ruta_three(), encoding="utf-8").read()
    m = re.search(r"export\s*\{([^}]*)\}\s*;?\s*$", src)
    if not m:
        raise ValueError("three.module.min.js no termina en export{...}: "
                         "cambió de forma y hay que revisar el visor")
    pares = []
    for trozo in m.group(1).split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        if " as " in trozo:
            local, fuera = [t.strip() for t in trozo.split(" as ")]
        else:
            local = fuera = trozo
        pares.append(f"{json.dumps(fuera)}:{local}")
    cuerpo = src[:m.start()]
    _MOTOR = ("(function(){\n" + cuerpo
              + "\nwindow.THREE={" + ",".join(pares) + "};\n})();")
    return _MOTOR


def _piezas(g: Gabinete, std: Estandar) -> List[dict]:
    sol = ISO.pintar_por_material(ISO.solidos_gabinete(g, std), std)
    fuera = []
    for s in sol:
        col = s.color or ISO.COLOR.get(s.grupo) or (0.8, 0.8, 0.8)
        fuera.append({
            "x": round(s.x, 1), "y": round(s.y, 1), "z": round(s.z, 1),
            "dx": round(s.dx, 1), "dy": round(s.dy, 1), "dz": round(s.dz, 1),
            "cod": s.codigo, "gru": s.grupo, "nom": s.etiqueta,
            "mat": s.material or "", "ch": s.chaflan or "",
            "col": [round(c, 4) for c in col],
            "exp": list(ISO.EXPLOSION.get(s.grupo, (0, 0, 0))),
        })
    return fuera


def modelo(gabinetes: List[Gabinete], std: Estandar, proyecto="Mueble") -> dict:
    ms = []
    for g in gabinetes:
        ms.append({
            "nombre": g.nombre,
            "tipo": g.tipo,
            "medidas": [round(g.ancho, 1), round(g.alto, 1), round(g.prof, 1)],
            "cantidad": int(g.cantidad or 1),
            "d": max(g.ancho, g.alto, g.prof),
            "piezas": _piezas(g, std),
        })
    return {"proyecto": proyecto, "gabinetes": ms}


def exportar(gabinetes: List[Gabinete], std: Estandar, path: str,
             proyecto="Mueble") -> str:
    datos = modelo(gabinetes, std, proyecto)
    html = PLANTILLA.replace("/*__MOTOR__*/", _motor()) \
                    .replace("/*__DATOS__*/", json.dumps(datos, ensure_ascii=False)) \
                    .replace("__TITULO__", _esc(proyecto))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


PLANTILLA = r"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>__TITULO__ · Taller 101</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { margin:0; height:100%; overflow:hidden;
    background:#15171a; color:#e8e6e1;
    font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  /* width/height al 100% NO sobran: el lienzo es un elemento reemplazado y con
     sólo `inset:0` toma su tamaño INTRÍNSECO —el del búfer, que en un celular
     es el doble por la densidad de pantalla— y se sale por abajo y por la
     derecha. El mueble queda centrado en un lienzo gigante del que sólo se ve
     la esquina de arriba a la izquierda. */
  #lienzo { position:fixed; inset:0; width:100%; height:100%;
            touch-action:none; display:block; }
  .barra { position:fixed; left:0; right:0; padding:10px 12px;
    background:linear-gradient(#15171aee,#15171a00); z-index:2; }
  .barra.abajo { bottom:0; top:auto;
    background:linear-gradient(#15171a00,#15171aee 45%); padding-bottom:16px; }
  .barra.arriba { top:0; }
  h1 { margin:0; font-size:15px; font-weight:600; letter-spacing:.01em; }
  .sub { font-size:11.5px; color:#9a978f; margin-top:2px; }
  .fila { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  button { font:inherit; font-size:12.5px; color:#e8e6e1; background:#262a2f;
    border:1px solid #363b41; border-radius:7px; padding:7px 11px; cursor:pointer; }
  button.on { background:#c2410c; border-color:#c2410c; color:#fff; }
  label { font-size:11.5px; color:#9a978f; }
  input[type=range] { flex:1; min-width:120px; accent-color:#c2410c; }
  #pieza { position:fixed; left:12px; bottom:96px; z-index:3; max-width:70vw;
    background:#1f2226ee; border:1px solid #363b41; border-radius:9px;
    padding:8px 11px; font-size:12.5px; display:none; }
  #pieza b { display:block; font-size:13px; margin-bottom:2px; }
  #pieza span { color:#9a978f; }
  .ayuda { font-size:11px; color:#6f6c66; margin-top:6px; }
</style></head>
<body>
<canvas id="lienzo"></canvas>

<div class="barra arriba">
  <h1 id="titulo">__TITULO__</h1>
  <div class="sub" id="sub"></div>
</div>

<div id="pieza"></div>

<div class="barra abajo">
  <div class="fila" id="selector" style="margin-bottom:8px"></div>
  <div class="fila">
    <label for="exp">Despiece</label>
    <input type="range" id="exp" min="0" max="100" value="0">
    <button id="bReset">Centrar</button>
  </div>
  <div class="ayuda">Gira con un dedo · acerca con dos · toca una pieza para ver cuál es</div>
</div>

<script>/*__MOTOR__*/</script>
<script>
const DATOS = /*__DATOS__*/;

const lienzo = document.getElementById("lienzo");
const rend = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true });
rend.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
const escena = new THREE.Scene();
escena.background = new THREE.Color(0x15171a);
const cam = new THREE.PerspectiveCamera(38, 1, 10, 60000);

escena.add(new THREE.HemisphereLight(0xffffff, 0x3a3a3a, 2.1));
const sol = new THREE.DirectionalLight(0xffffff, 1.5);
sol.position.set(1, 2, 1.4);
escena.add(sol);
const sol2 = new THREE.DirectionalLight(0xffffff, 0.5);
sol2.position.set(-1.2, 0.6, -1);
escena.add(sol2);

let grupo = null, mallas = [], centro = new THREE.Vector3(), radio = 1000, actual = 0;

/* El chaflán del uñero: el mismo perfil de cinco puntos que la app (#066).
   La pieza se corta recta y el corte a 45 se hace después, pero si aquí se ve
   recta nadie sabe cuál canto lleva el corte. */
function geo(p) {
  if (!p.ch) return new THREE.BoxGeometry(p.dx, p.dz, p.dy);
  const c = Math.min(p.dy, p.dz), A = p.dz / 2, F = p.dy / 2;
  const f = new THREE.Shape();
  if (p.ch === "inf") {
    f.moveTo(-F, -A); f.lineTo(F - c, -A); f.lineTo(F, -A + c);
    f.lineTo(F, A); f.lineTo(-F, A);
  } else {
    f.moveTo(-F, -A); f.lineTo(F, -A); f.lineTo(F, A - c);
    f.lineTo(F - c, A); f.lineTo(-F, A);
  }
  const g = new THREE.ExtrudeGeometry(f, { depth: p.dx, bevelEnabled: false });
  g.translate(0, 0, -p.dx / 2);
  g.rotateY(-Math.PI / 2);
  g.computeVertexNormals();
  return g;
}

function construir(i) {
  actual = i;
  if (grupo) { escena.remove(grupo); }
  const gab = DATOS.gabinetes[i];
  grupo = new THREE.Group();
  mallas = [];
  gab.piezas.forEach((p) => {
    const m = new THREE.Mesh(geo(p), new THREE.MeshLambertMaterial({
      color: new THREE.Color(p.col[0], p.col[1], p.col[2]) }));
    // el motor 3D usa Y hacia arriba; el despiece usa Z. Se cambian aquí y en
    // ningún otro lado, para no tener dos convenios peleados.
    m.position.set(p.x + p.dx / 2, p.z + p.dz / 2, p.y + p.dy / 2);
    m.userData = { p, base: m.position.clone(),
                   exp: new THREE.Vector3(p.exp[0], p.exp[2], p.exp[1]) };
    grupo.add(m);
    mallas.push(m);
    const bordes = new THREE.LineSegments(
      new THREE.EdgesGeometry(m.geometry, 35),
      new THREE.LineBasicMaterial({ color: 0x2b2b2b, transparent: true, opacity: 0.55 }));
    bordes.position.copy(m.position);
    bordes.userData = { seguir: m };
    grupo.add(bordes);
  });
  escena.add(grupo);

  const esf = new THREE.Box3().setFromObject(grupo)
    .getBoundingSphere(new THREE.Sphere());
  centro.copy(esf.center);
  radio = esf.radius;
  document.getElementById("sub").textContent =
    `${gab.nombre} · ${gab.medidas[0]} × ${gab.medidas[1]} × ${gab.medidas[2]} mm` +
    (gab.cantidad > 1 ? ` · ${gab.cantidad} piezas iguales` : "") +
    ` · ${gab.piezas.length} componentes`;
  document.querySelectorAll("#selector button").forEach((b, j) =>
    b.classList.toggle("on", j === i));
  ocultarPieza();
  centrar();
}

/* --- cámara: un dedo gira, dos acercan ---
   La distancia sale de la esfera que envuelve al mueble y del lado MÁS ANGOSTO
   de la pantalla. En un celular vertical el ángulo horizontal es mucho menor
   que el vertical: calculándolo sólo con el vertical, el mueble se sale por los
   lados y se ve un muro gris. Se guarda el acercamiento como factor (`k`) para
   que al girar el teléfono se reencuadre sin perder el zoom. */
/* El frente del mueble es y=0, y en el motor 3D eso cae en −Z. La cámara tiene
   que quedar del lado del frente y a la derecha: con el ángulo de la app se
   veía el mueble POR DETRÁS, que es justo lo que no le sirve a nadie en obra. */
const VISTA = { th: Math.PI - 0.72, fi: 1.12 };
const orb = { th: VISTA.th, fi: VISTA.fi, k: 1 };
function ajuste() {
  const vfov = cam.fov * Math.PI / 180;
  const hfov = 2 * Math.atan(Math.tan(vfov / 2) * cam.aspect);
  return (radio * 1.12) / Math.sin(Math.min(vfov, hfov) / 2);
}
function aplicar() {
  const r = ajuste() * orb.k;
  const s = Math.sin(orb.fi);
  cam.position.set(centro.x + r * s * Math.sin(orb.th),
                   centro.y + r * Math.cos(orb.fi),
                   centro.z + r * s * Math.cos(orb.th));
  cam.near = Math.max(1, r / 800);
  cam.far = r * 12;
  cam.updateProjectionMatrix();
  cam.lookAt(centro);
}
function centrar() {
  orb.th = VISTA.th; orb.fi = VISTA.fi; orb.k = 1;
  aplicar();
}

let dedos = new Map(), sep0 = 0, r0 = 0, movido = 0;
lienzo.addEventListener("pointerdown", (e) => {
  lienzo.setPointerCapture(e.pointerId);
  dedos.set(e.pointerId, { x: e.clientX, y: e.clientY });
  movido = 0;
  if (dedos.size === 2) { sep0 = separacion(); r0 = orb.k; }
});
lienzo.addEventListener("pointermove", (e) => {
  const d = dedos.get(e.pointerId);
  if (!d) return;
  const dx = e.clientX - d.x, dy = e.clientY - d.y;
  d.x = e.clientX; d.y = e.clientY;
  movido += Math.abs(dx) + Math.abs(dy);
  if (dedos.size === 1) {
    orb.th -= dx * 0.008;
    orb.fi = Math.min(Math.PI - 0.06, Math.max(0.06, orb.fi - dy * 0.008));
  } else if (dedos.size === 2 && sep0 > 0) {
    orb.k = Math.min(4, Math.max(0.25, r0 * sep0 / separacion()));
  }
  aplicar();
});
function separacion() {
  const v = [...dedos.values()];
  if (v.length < 2) return sep0 || 1;
  return Math.max(1, Math.hypot(v[0].x - v[1].x, v[0].y - v[1].y));
}
function soltar(e) {
  if (dedos.size === 1 && movido < 9) tocar(e);
  dedos.delete(e.pointerId);
}
lienzo.addEventListener("pointerup", soltar);
lienzo.addEventListener("pointercancel", (e) => dedos.delete(e.pointerId));
lienzo.addEventListener("wheel", (e) => {
  e.preventDefault();
  orb.k = Math.min(4, Math.max(0.25, orb.k * (e.deltaY > 0 ? 1.12 : 0.89)));
  aplicar();
}, { passive: false });

/* --- tocar una pieza para saber cuál es --- */
const rayo = new THREE.Raycaster();
function tocar(e) {
  const c = lienzo.getBoundingClientRect();
  rayo.setFromCamera(new THREE.Vector2(
    ((e.clientX - c.left) / c.width) * 2 - 1,
    -((e.clientY - c.top) / c.height) * 2 + 1), cam);
  const h = rayo.intersectObjects(mallas, false);
  if (!h.length) return ocultarPieza();
  const p = h[0].object.userData.p;
  const caja = document.getElementById("pieza");
  caja.innerHTML = `<b>${p.nom || p.cod}</b>` +
    `<span>${p.cod}${p.mat ? " · " + p.mat : ""}<br>` +
    `${Math.round(Math.max(p.dx, p.dy, p.dz))} × ` +
    `${Math.round([p.dx, p.dy, p.dz].sort((a, b) => a - b)[1])} mm` +
    `${p.ch ? " · canto a 45°" : ""}</span>`;
  caja.style.display = "block";
}
function ocultarPieza() { document.getElementById("pieza").style.display = "none"; }

/* --- despiece --- */
document.getElementById("exp").addEventListener("input", (e) => {
  const f = (+e.target.value / 100) * 0.42 * radio;
  grupo.children.forEach((o) => {
    const m = o.userData.seguir || o;
    if (!m.userData.base) return;
    const q = m.userData.base.clone().addScaledVector(m.userData.exp, f);
    o.position.copy(q);
  });
});
document.getElementById("bReset").addEventListener("click", () => {
  document.getElementById("exp").value = 0;
  document.getElementById("exp").dispatchEvent(new Event("input"));
  centrar();
});

/* --- varios gabinetes: un botón por cada uno --- */
if (DATOS.gabinetes.length > 1) {
  const sel = document.getElementById("selector");
  DATOS.gabinetes.forEach((g, i) => {
    const b = document.createElement("button");
    b.textContent = g.nombre;
    b.onclick = () => { construir(i); document.getElementById("exp").value = 0; };
    sel.appendChild(b);
  });
}

function medir() {
  const w = innerWidth, h = innerHeight;
  rend.setSize(w, h, false);
  cam.aspect = w / h;
  cam.updateProjectionMatrix();
  if (grupo) aplicar();          // al girar el teléfono se vuelve a encuadrar
}
addEventListener("resize", medir);
medir();
construir(0);
(function pintar() { requestAnimationFrame(pintar); rend.render(escena, cam); })();
</script>
</body></html>
"""
