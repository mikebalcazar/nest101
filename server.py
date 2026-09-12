"""Backend local de Taller 101. Lo arranca Electron; también corre solo.
    python server.py --port 8760
"""
import os, sys, json, copy, argparse, tempfile
from dataclasses import asdict
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.config import Estandar, Material, CATALOGO_DEFAULT
from core.modelos import (Gabinete, Frente, preset_base, preset_aereo, preset_gaveteros,
                          alturas, alturas_entrepanos, AlturaInvalida,
                          GeometriaInvalida, validar, _repartir_frentes)
from core.proyecto import Proyecto, _gab_obj
from core import iso as ISO
from core import cubierta as CUB
from core import taller as TALLER
# #020 — ezdxf, openpyxl y reportlab NO se importan al arrancar: son ~400 ms con
# archivos ya compilados, y muchísimo más en un equipo donde Python tiene que
# compilar desde el .py. La app abre antes; se cargan la primera vez que se exporta.
def _exportadores():
    from export import dxf, xlsx, pdf, fichas
    return dxf, xlsx, pdf, fichas


RAIZ = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(os.path.expanduser("~"), "Taller 101")
EXT = ".t101x"          # #008: extensión propia (el contenido sigue siendo JSON)
# #087 — una sola versión escrita, la que contesta /api/salud y contra la que se
# compara la que haya publicada. Dos copias del número acaban desfasadas.
VERSION = "10.0.2"          # línea X: compilación de prueba (X.0.2)


def _buscar_ui() -> Optional[str]:
    """La carpeta ui/ cambia de lugar entre desarrollo y app empaquetada."""
    candidatos = [
        os.environ.get("DESPZ_UI"),                       # forzada por Electron
        os.path.join(RAIZ, "ui"),                         # desarrollo y app_py empaquetado
        os.path.join(os.path.dirname(RAIZ), "ui"),        # un nivel arriba
        os.path.join(os.path.dirname(RAIZ), "app", "ui"),
    ]
    for c in candidatos:
        if c and os.path.isfile(os.path.join(c, "index.html")):
            return c
    return None


UI = _buscar_ui()

app = FastAPI(title="Taller 101")

# #031 — «Leer plano» se monta si puede. Si no, la app arranca igual y sin él.
#
# Esto no es prudencia de más: la 0.6.0 no arrancó en la máquina de Mike porque
# a este import le faltaba una librería, y un módulo opcional se llevó por
# delante el programa entero. Una función que no carga tiene que quitarse ella
# sola, no tumbar el despiece.
LEER_PLANO_ERROR = None
try:
    from identificador.rutas import router as router_leer_plano
    app.include_router(router_leer_plano)
except Exception as _e:                                  # noqa: BLE001
    LEER_PLANO_ERROR = f"{type(_e).__name__}: {_e}"
    print(f"aviso: «Leer plano» no se pudo cargar y queda apagado. {LEER_PLANO_ERROR}",
          file=sys.stderr, flush=True)


@app.exception_handler(GeometriaInvalida)
def _geometria_invalida(request, exc):
    """#001 #014: medidas imposibles — mensaje legible, no un 500 ni un DXF con basura."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})

# proyecto en memoria (la UI manda el estado completo en cada cálculo)
ESTADO: Dict[str, Any] = {"proyecto": Proyecto()}


class ProyectoIn(BaseModel):
    nombre: str = "Proyecto"
    cliente: str = ""
    catalogo: Optional[List[dict]] = None
    estandar: Optional[dict] = None
    gabinetes: List[dict] = []


class ExportarIn(BaseModel):
    proyecto: ProyectoIn
    carpeta: Optional[str] = None
    # #072 — el DXF de isométricos ya no se exporta.
    # #076 — y el corte se parte en dos máquinas: la fresa recorre contornos, la
    # sierra lineal sólo hace cortes de lado a lado. Son dos acomodos distintos,
    # así que son dos archivos distintos por máquina.
    salidas: List[str] = ["dxf_fresa", "pdf_fresa", "dxf_sierra", "pdf_sierra",
                          "dxf_piezas", "xlsx", "pdf", "fichas"]


def _a_proyecto(p: ProyectoIn) -> Proyecto:
    d = p.model_dump()
    if not d.get("catalogo"):
        d["catalogo"] = [asdict(m) for m in CATALOGO_DEFAULT]
    if not d.get("estandar"):
        d["estandar"] = asdict(Estandar())
    return Proyecto.from_dict(d)


# --------------------------------------------------------------- meta
@app.get("/api/salud")
def salud():
    return {"ok": True, "version": VERSION, "salida": SALIDA,
            "leer_plano": LEER_PLANO_ERROR or "ok"}


class PerfilIn(BaseModel):
    catalogo: Optional[List[dict]] = None
    estandar: Optional[dict] = None
    idioma: Optional[str] = None                       # #085


class LlaveIn(BaseModel):
    valor: str = ""


def _poner_llave_en_entorno():
    """#040 — el lector de planos pide la llave por variable de entorno.

    La llave vive en un archivo del perfil del equipo; aquí se le pasa al
    proceso que va a leer, que es éste. Se hace en un solo lugar para que
    `identificador` no tenga que saber dónde guarda sus cosas el taller.
    """
    v = TALLER.llave()
    if v:
        os.environ["ANTHROPIC_API_KEY"] = v
    else:
        os.environ.pop("ANTHROPIC_API_KEY", None)


_poner_llave_en_entorno()


# --------------------------------------------------------------- #083 logotipo
#
# El logotipo que firma planos y fichas es el de la EMPRESA que usa el programa,
# con el de nest101 de respaldo. Se guarda en la carpeta de trabajo del taller,
# no en la de instalación: una actualización reescribe la de instalación y le
# borraría el logotipo al taller.
#
# `core.marca` se importa **dentro de cada ruta**, no arriba. Al importarlo
# registra las tipografías, y eso arrastra reportlab entero al arranque — que es
# exactamente lo que #020 evita con `_exportadores()`. Importarlo arriba le
# costaba a la app medio segundo de arranque y metía `defusedxml` en la lista de
# módulos que tienen que viajar en el runtime. Lo cachó `t012`.
def _marca():
    from core import marca
    return marca


@app.get("/api/logo")
def logo_estado():
    MARCA = _marca()
    propio = MARCA.logo_empresa()
    return {"propio": bool(propio),
            "archivo": propio or MARCA.logo_app(),
            "nombre": os.path.basename(propio) if propio else MARCA.APP,
            "carpeta": str(TALLER.carpeta())}


@app.get("/api/logo/imagen")
def logo_imagen():
    """El logotipo en uso, para pintarlo en la interfaz.

    Sin caché: quien lo acaba de cambiar tiene que ver el nuevo. Un logotipo se
    cambia dos veces en la vida de un taller; no hay nada que ahorrar aquí.
    """
    ruta = _marca().logo()
    if not ruta:
        raise HTTPException(404, "no hay logotipo")
    return FileResponse(ruta, headers={"Cache-Control": "no-store"})


@app.put("/api/logo")
async def logo_guardar(archivo: UploadFile = File(...)):
    try:
        ruta = _marca().guardar_logo(await archivo.read(), archivo.filename or "")
    except ValueError as e:
        # 400 y el motivo escrito: «no se pudo» sin decir por qué obliga a
        # adivinar si el archivo estaba mal o el programa está roto.
        raise HTTPException(400, str(e))
    return {"ok": True, "archivo": ruta}


@app.delete("/api/logo")
def logo_quitar():
    return {"ok": True, "habia": _marca().quitar_logo()}


# --------------------------------------------------------------- #087 actualizar
class PoliticaIn(BaseModel):
    revisar: Optional[bool] = None
    ignorada: Optional[str] = None
    descargar: Optional[bool] = None            # #093


@app.get("/api/actualizacion/auto")
def actualizacion_auto():
    """La revisión del arranque: respeta el interruptor y la versión ignorada.

    #092 — Mike: «también una revisión de actualizaciones automáticas». Revisa
    al arrancar y una vez al día; se puede apagar, y se puede ignorar una
    versión concreta sin quedarse mudo para las siguientes.
    """
    from core import actualizar as ACT
    return ACT.revisar_si_toca(VERSION)


@app.put("/api/actualizacion/auto")
def actualizacion_politica(req: PoliticaIn):
    from core import actualizar as ACT
    return ACT.guardar_politica(revisar=req.revisar, ignorada=req.ignorada,
                                descargar=req.descargar)


@app.get("/api/actualizacion/descarga")
def actualizacion_descarga_estado():
    """Cómo va la descarga: `ocioso · bajando · lista · error`, con porcentaje.

    #093 — Es lo que la ventana pregunta cada dos segundos mientras baja. Tiene
    que ser barato: no toca la red ni el disco, solo lee lo que el hilo que
    baja va anotando.
    """
    from core import actualizar as ACT
    return ACT.estado_descarga()


@app.post("/api/actualizacion/descargar")
def actualizacion_descargar():
    """Arranca la descarga y **contesta de inmediato**.

    #093 — Antes bajaba aquí mismo, con la petición abierta los 180 MB: la
    ventana se quedaba sin saber nada durante minutos y sin poder enseñar el
    avance. Ahora esto solo da la orden; el progreso se sigue en
    `GET /api/actualizacion/descarga`.

    El archivo se guarda en la carpeta del taller, no en Temp: si algo sale
    mal, sigue ahí y se puede instalar a mano sin volver a bajarlo.
    """
    from core import actualizar as ACT
    r = ACT.revisar(VERSION)
    if not r.get("version"):
        raise HTTPException(503, r.get("error") or "no se pudo consultar")
    # `forzar`: esto es un clic de la persona, así que un error anterior no lo
    # bloquea. Ahí está la diferencia con la descarga automática.
    return {"ok": True, "version": r["version"], "notas": r.get("notas", ""),
            **ACT.arrancar_descarga(r, forzar=True)}


# --------------------------------------------------------------- #091 avisos
@app.get("/api/avisos")
def avisos_listar(forzar: bool = False):
    from core import avisos as AV
    return AV.para_mi(VERSION, forzar=forzar)


class LeidosIn(BaseModel):
    ids: List[str] = []


@app.post("/api/avisos/leidos")
def avisos_leidos(req: LeidosIn):
    from core import avisos as AV
    return {"leidos": AV.marcar_leidos(req.ids)}


# --------------------------------------------------------------- #091 licencias
@app.get("/api/licencias")
def licencias():
    """Cada componente ajeno que viaja dentro del programa.

    La lista la genera `build/juntar_licencias.py` **de lo que de verdad hay**
    en el runtime empaquetado, no de una lista escrita a mano que se queda vieja.
    """
    ruta = os.path.join(RAIZ, "assets", "licencias.json")
    if not os.path.isfile(ruta):
        return {"componentes": [], "total": 0,
                "error": "no se generó la lista de licencias"}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/actualizacion")
def actualizacion(forzar: bool = False):
    """¿Hay versión nueva? Nunca falla: sin red contesta «no se pudo revisar».

    #093 — El programa sí se baja sola la versión nueva si el taller lo tiene
    encendido, pero **no se instala solo**: correr el instalador cierra el
    programa, y hacerlo sin avisar a media exportación sería imperdonable.

    Esta es la revisión directa, la de «Buscar ahora»: pregunta aunque se haya
    preguntado hace diez minutos. Va acompañada de la política y del estado de
    la descarga para que la ventana pueda pintarse entera de una sola llamada.
    """
    from core import actualizar as ACT
    r = ACT.revisar(VERSION, forzar=forzar)
    p = ACT.politica()
    if r.get("hay") and p["descargar_solo"]:
        ACT.arrancar_descarga(r)
    r["apagada"] = not p["revisar_solo"]
    r["descargar_solo"] = p["descargar_solo"]
    r["descarga"] = ACT.estado_descarga()
    return r


# --------------------------------------------------------------- #085 idioma
@app.get("/api/idioma")
def idioma_estado():
    from core import idioma as IDI
    return {"activo": IDI.activo(), "de_fabrica": IDI.DE_FABRICA,
            "disponibles": IDI.disponibles()}


@app.get("/api/idioma/{codigo}.json")
def idioma_diccionario(codigo: str):
    """El diccionario que usa la interfaz. Es el MISMO que usa el papel.

    Un archivo para pantalla y otro para PDF se desincronizan a la tercera
    palabra que alguien corrige en uno solo.
    """
    from core import idioma as IDI
    if codigo not in IDI.IDIOMAS:
        raise HTTPException(404, f"no hay diccionario «{codigo}»")
    return JSONResponse(IDI.diccionario(codigo),
                        headers={"Cache-Control": "no-store"})


@app.get("/api/llave")
def llave_estado():
    """Si hay llave y cuál, sin enseñarla: una llave en pantalla es una llave
    en la próxima captura de pantalla que alguien mande por WhatsApp."""
    v = TALLER.llave()
    return {"hay": bool(v), "pista": TALLER.pista(v),
            "archivo": str(TALLER.ruta_llave())}


@app.put("/api/llave")
def llave_guardar(req: LlaveIn):
    hay = TALLER.guardar_llave(req.valor)
    _poner_llave_en_entorno()
    return {"hay": hay, "pista": TALLER.pista()}


@app.get("/api/perfil")
def perfil_leer():
    """#037 — la base de materiales del taller, compartida por todos los muebles."""
    return TALLER.leer()


@app.put("/api/perfil")
def perfil_guardar(req: PerfilIn):
    d = TALLER.leer()
    if req.catalogo is not None:
        d["catalogo"] = req.catalogo
    if req.estandar is not None:
        d["estandar"] = req.estandar
    if req.idioma is not None:
        from core import idioma as IDI
        # Se cambia también en caliente: si no, el primer PDF después de
        # cambiar el idioma saldría todavía en el anterior, y nadie relaciona
        # eso con haber tenido que reiniciar.
        d["idioma"] = IDI.poner(req.idioma)
    TALLER.guardar(d)
    return d


@app.post("/api/perfil/fundir")
def perfil_fundir(req: PerfilIn):
    """Mete a la base del taller los materiales que traiga un archivo y no tenga.

    No pisa lo que ya existe: si viene uno con el mismo nombre y otro precio,
    gana el del taller, porque el del taller es el que se va a pagar.
    """
    d, entraron = TALLER.fundir(req.catalogo)
    return {"perfil": d, "agregados": entraron}


@app.get("/api/defaults")
def defaults():
    # #037 — lo de fábrica sólo se usa la primera vez; de ahí en adelante manda
    # el perfil del taller.
    _p = TALLER.leer()
    return {
        "catalogo": _p["catalogo"],
        "estandar": _p["estandar"],
        "presets": [
            {"id": "base", "nombre": "Gabinete bajo", "ancho": 900, "alto": 880, "prof": 600},
            {"id": "aereo", "nombre": "Gabinete aéreo", "ancho": 900, "alto": 700, "prof": 350},
            {"id": "cajonera", "nombre": "Cajonera", "ancho": 600, "alto": 880, "prof": 600},
            {"id": "torre", "nombre": "Torre / despensero", "ancho": 600, "alto": 2100, "prof": 600},
            {"id": "nicho", "nombre": "Nicho abierto aéreo", "ancho": 600, "alto": 700, "prof": 350},
            {"id": "nicho_bajo", "nombre": "Nicho abierto bajo", "ancho": 600, "alto": 880, "prof": 600},
        ],
    }


@app.get("/api/preset/{pid}")
def preset(pid: str):
    if pid == "base":
        g = preset_base()
    elif pid == "aereo":
        g = preset_aereo()
    elif pid == "cajonera":
        g = preset_gaveteros()
    elif pid == "torre":
        g = Gabinete("Torre", "base", 600, 2100, 600,
                     [Frente("cajon", alto=200), Frente("puerta", alto=None, n=1),
                      Frente("puerta", alto=900, n=1)], n_entrepanos=3)
    elif pid == "nicho":            # #024 — sin frentes, un mueble abierto
        g = Gabinete("Nicho abierto", "aereo", 600, 700, 350, [],
                     n_entrepanos=2, tapa_completa=True, con_zoclo=False)
    elif pid == "nicho_bajo":
        g = Gabinete("Nicho bajo", "base", 600, 880, 600, [],
                     n_entrepanos=1, tapa_completa=True, con_zoclo=True)
    else:
        raise HTTPException(404, "preset desconocido")
    d = asdict(g)
    d["frentes"] = [asdict(f) for f in g.frentes]
    return d


# --------------------------------------------------------------- cálculo
@app.post("/api/calcular")
def calcular(p: ProyectoIn):
    pr = _a_proyecto(p)
    if not pr.gabinetes:
        return {"piezas": [], "hojas": [], "costeo": [], "resumen": {}}
    piezas, hojas, _ = pr.calcular()
    costeo = pr.costeo(piezas, hojas)
    return {
        "piezas": [{
            "codigo": x.codigo, "mueble": x.mueble, "nombre": x.nombre,
            "material": x.material, "espesor": x.espesor,
            "largo": round(x.largo, 1), "ancho": round(x.ancho, 1),
            "cantidad": x.cantidad, "area": round(x.area_m2, 4),
            "canto_ml": round(x.ml_canto * x.cantidad, 3),
            "canto": list(x.canto), "veta": x.veta, "nota": x.nota,
        } for x in piezas],
        "hojas": [{
            "idx": h.idx, "material": h.material, "espesor": h.espesor,
            "ancho": h.ancho, "alto": h.alto,
            "aprov": round(h.aprovechamiento, 4),
            "piezas": [{
                "codigo": c.pieza.codigo, "nombre": c.pieza.nombre,
                "x": round(c.x, 1), "y": round(c.y, 1),
                "w": round(c.w, 1), "h": round(c.h, 1), "rot": c.rotada,
            } for c in h.colocaciones],
        } for h in hojas],
        "costeo": costeo,
        "cubiertas": [{                                   # #028
            "material": t.material, "espesor": t.espesor,
            "largo": t.largo, "fondo": t.fondo,
            "m2": round(t.area_m2, 3), "alto_nariz": t.alto_nariz,
            "alto": t.alto, "alto_lomo": t.alto_lomo,
            "ml_nariz": t.ml_nariz, "ml_doblado": t.ml_doblado,
            "muebles": t.muebles, "parte": t.parte, "partes": t.partes,
            "nota": t.nota,
        } for t in pr.cubiertas()],
        "cubiertas_resumen": CUB.resumen(pr.cubiertas()),
        "resumen": {
            "piezas_unicas": len(piezas),
            "piezas_total": sum(x.cantidad for x in piezas),
            "hojas": len(hojas),
            "m2_pieza": round(sum(x.area_m2 * x.cantidad for x in piezas), 3),
            "m2_hoja": round(sum(h.ancho * h.alto for h in hojas) / 1e6, 3),
            "costo_total": round(sum(c["costo_total"] for c in costeo), 2),
        },
    }


@app.post("/api/solidos")
def solidos(p: ProyectoIn):
    """Geometría 3D para el preview: una lista de cajas por gabinete."""
    pr = _a_proyecto(p)
    out = []
    for g in pr.gabinetes:
        std = pr.estandar_de(g)
        sol = ISO.solidos_gabinete(g, std)
        total, cuerpo, hz = alturas(g, std)
        out.append({
            "nombre": g.nombre,
            "bbox": [g.ancho, g.alto, g.prof],
            "alturas": {"total": round(total, 1), "cuerpo": round(cuerpo, 1),
                        "zoclo": round(hz, 1), "derivado": g.alto_derivado},
            "pos": {"x": g.pos_x, "z": g.pos_z, "rot": int(g.rot) % 360,
                    "base": ISO.base_z(g, std)},
            "entrepanos": {                                   # #023
                "alturas": alturas_entrepanos(g, std, cuerpo),
                "hueco": round(cuerpo - 2 * std.mat_cuerpo.espesor, 1),
                "espesor": std.mat_cuerpo.espesor,
                "fijos": bool(g.entrepanos_fijos),
                "paso": std.paso_sistema,
            },
            "frentes": _frentes_info(g, std, cuerpo),          # #023
            "piezas": [{
                "codigo": s.codigo, "grupo": s.grupo, "etiqueta": s.etiqueta,
                "x": s.x, "y": s.y, "z": s.z,
                "dx": s.dx, "dy": s.dy, "dz": s.dz,
                "material": s.material,
                "ref": {"tipo": s.ref_tipo, "i": s.ref_i} if s.ref_tipo else None,
                "color": s.color or ISO.COLOR.get(s.grupo, (0.8, 0.8, 0.8)),
                "color_rol": ISO.COLOR.get(s.grupo, (0.8, 0.8, 0.8)),
                "explosion": ISO.EXPLOSION.get(s.grupo, (0, 0, 0)),
                "chaflan": s.chaflan,                          # #058
            } for s in sol],
        })
    # #028 — la cubierta no es de ningún mueble: es un tramo de la cocina
    cubs = []
    for t in pr.cubiertas():
        m = pr.material(t.material)
        cubs.append({
            "material": t.material, "espesor": t.espesor,
            # `alto` es la cara de ABAJO: la cubierta se apoya sobre el mueble.
            "largo": t.largo, "fondo": t.fondo, "alto": t.alto,
            "alto_lomo": t.alto_lomo,
            "x": t.x, "z": t.z, "rot": t.rot,
            "muebles": t.muebles, "parte": t.parte, "partes": t.partes,
            "alto_nariz": t.alto_nariz, "nota": t.nota,
            "color": ISO.hex_a_rgb(m.color if m else "#8E8B86") or (0.56, 0.55, 0.52),
        })
    return {"gabinetes": out, "cubiertas": cubs}


def _frentes_info(g, std, hc):
    """Alto real de cada frente, para poder acotarlo en el 3D. (#023)

    El motor ya reparte el sobrante entre los frentes sin altura fija; aquí sólo
    se devuelve lo que resultó, junto con si esa altura la escribió el usuario o
    la calculó el reparto.
    """
    out = []
    try:
        mods = _repartir_frentes(g, hc, std)
    except Exception:
        return out
    for i, m in enumerate(mods):
        fr = m["frente"]
        out.append({
            "i": i,
            "tipo": fr.tipo,
            "n": fr.n,
            "alto": round(m["alto_frente"], 1),      # lo que mide la hoja
            "alto_modulo": round(m["alto_mod"], 1),  # el hueco que ocupa
            "y": round(m["y_mod"], 1),               # desde el piso del cuerpo
            "propio": fr.alto is not None,
        })
    return out


# ------------------------------------------------- #025 miniaturas · #026 biblioteca
BIBLIOTECA = os.path.join(SALIDA, "mis-gabinetes.json")
_MINI: Dict[str, bytes] = {}          # caché en memoria; rehacer una es ~40 ms


def _preset(pid: str) -> Gabinete:
    d = preset(pid)
    d = dict(d)
    d["frentes"] = [Frente(**f) for f in d.get("frentes", [])]
    campos = {f for f in Gabinete.__dataclass_fields__}
    return Gabinete(**{k: v for k, v in d.items() if k in campos})


def _png_gabinete(g: Gabinete, std: Estandar, ancho=300) -> bytes:
    """Miniatura isométrica con fondo transparente. (#025)

    Se dibuja con el MISMO motor que hace los planos, así la miniatura no puede
    desfasarse del modelo: si cambia el despiece, cambia la imagen.
    """
    from core import render as R
    import io
    g = copy.deepcopy(g)
    g.pos_x = g.pos_z = 0.0
    g.rot = 0
    sol = ISO.solidos_gabinete(g, std)
    im = R.render(sol, ancho_px=int(ancho), margen_px=max(4, int(ancho) // 26),
                  transparente=True)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _mini_respuesta(clave: str, hacer, cache=True):
    from fastapi import Response
    if cache and clave in _MINI:
        datos = _MINI[clave]
    else:
        datos = hacer()
        if cache:
            if len(_MINI) > 80:
                _MINI.clear()
            _MINI[clave] = datos
    return Response(content=datos, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=300"})


@app.get("/api/miniatura/{pid}.png")
def miniatura_preset(pid: str, w: int = 300):
    w = max(80, min(int(w), 900))
    return _mini_respuesta(f"p:{pid}:{w}",
                           lambda: _png_gabinete(_preset(pid), Estandar(), w))


@app.post("/api/miniatura")
def miniatura_gabinete(req: ExportarIn, w: int = 300):
    """Miniatura de un gabinete cualquiera: el primero del proyecto que se manda."""
    w = max(80, min(int(w), 900))
    pr = _a_proyecto(req.proyecto)
    if not pr.gabinetes:
        raise HTTPException(400, "No se mandó ningún gabinete")
    g = pr.gabinetes[0]
    return _mini_respuesta("", lambda: _png_gabinete(g, pr.estandar_de(g), w), cache=False)


def _leer_biblioteca() -> List[dict]:
    try:
        with open(BIBLIOTECA, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _escribir_biblioteca(lista):
    os.makedirs(os.path.dirname(BIBLIOTECA), exist_ok=True)
    tmp = BIBLIOTECA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lista, f, indent=2, ensure_ascii=False)
    os.replace(tmp, BIBLIOTECA)      # nunca dejar el archivo a medias


class GuardarModeloIn(BaseModel):
    nombre: str = ""
    gabinete: dict


@app.get("/api/biblioteca")
def biblioteca():
    """#026 — los modelos del usuario viven FUERA del proyecto, en su perfil,
    para que estén en todas las cocinas y no sólo en la que se guardó."""
    return {"archivo": BIBLIOTECA, "modelos": _leer_biblioteca()}


@app.post("/api/biblioteca")
def biblioteca_guardar(req: GuardarModeloIn):
    d = dict(req.gabinete)
    for k in ("pos_x", "pos_z", "rot", "alto_colgado"):
        d.pop(k, None)               # la posición es de la cocina, no del modelo
    g = _gab_obj(d)                  # se valida que sea un gabinete de verdad
    validar(g, Estandar())
    nombre = (req.nombre or g.nombre or "Modelo").strip()[:60]
    lista = _leer_biblioteca()
    bid = _slug(nombre).lower() + "-" + str(int(__import__("time").time()))
    d2 = asdict(g)
    d2["frentes"] = [asdict(f) for f in g.frentes]
    for k in ("pos_x", "pos_z", "rot", "alto_colgado"):
        d2.pop(k, None)              # un modelo no tiene lugar en la cocina
    lista.insert(0, {"id": bid, "nombre": nombre, "gabinete": d2,
                     "cuando": __import__("time").time()})
    _escribir_biblioteca(lista[:120])
    return {"id": bid, "nombre": nombre, "total": len(lista[:120])}


# --------------------------------------------------------------- #086 módulos
#
# La librería por categorías. `core/modulos.py` explica cómo está organizada;
# aquí sólo se expone. Lo que se guarda va SIEMPRE a la carpeta del taller: la
# de instalación la reescribe cada actualización.
class GuardarModuloIn(BaseModel):
    categoria: str = ""
    nombre: str = ""
    nota: str = ""
    gabinete: dict


@app.get("/api/modulos")
def modulos_listar():
    from core import modulos as MOD
    cats = MOD.categorias()
    return {"categorias": cats, "carpeta": MOD.carpeta_taller(),
            "total": sum(len(c["modulos"]) for c in cats)}


@app.post("/api/modulos")
def modulos_guardar(req: GuardarModuloIn):
    from core import modulos as MOD
    d = dict(req.gabinete)
    for k in ("pos_x", "pos_z", "rot", "alto_colgado"):
        d.pop(k, None)               # el lugar en la cocina es del proyecto
    g = _gab_obj(d)                  # se valida que sea un gabinete de verdad
    validar(g, Estandar())
    d2 = asdict(g)
    d2["frentes"] = [asdict(f) for f in g.frentes]
    for k in ("pos_x", "pos_z", "rot", "alto_colgado"):
        d2.pop(k, None)
    cat = (req.categoria or "Mis módulos").strip()[:60]
    nom = (req.nombre or g.nombre or "Módulo").strip()[:60]
    r = MOD.guardar(cat, nom, d2, (req.nota or "").strip()[:200])
    return {**r, "nombre": nom, "categoria_nombre": cat}


@app.delete("/api/modulos/{cat}/{arch}")
def modulos_borrar(cat: str, arch: str):
    from core import modulos as MOD
    if not MOD.borrar(f"{cat}/{arch}"):
        raise HTTPException(404, "No existe ese módulo, o es de fábrica y no se borra")
    return {"borrado": f"{cat}/{arch}"}


@app.get("/api/miniatura/modulo/{cat}/{arch}.png")
def miniatura_modulo(cat: str, arch: str, w: int = 300):
    from core import modulos as MOD
    w = max(80, min(int(w), 900))
    m = MOD.modulo(f"{cat}/{arch}")
    if not m:
        raise HTTPException(404, "No existe ese módulo")
    g = _gab_obj(m["gabinete"])
    return _mini_respuesta(f"m:{cat}/{arch}:{w}", lambda: _png_gabinete(g, Estandar(), w))


@app.delete("/api/biblioteca/{bid}")
def biblioteca_borrar(bid: str):
    lista = _leer_biblioteca()
    quedan = [m for m in lista if m.get("id") != bid]
    if len(quedan) == len(lista):
        raise HTTPException(404, "No existe ese modelo")
    _escribir_biblioteca(quedan)
    return {"borrado": bid, "total": len(quedan)}


@app.get("/api/miniatura/biblioteca/{bid}.png")
def miniatura_biblioteca(bid: str, w: int = 300):
    w = max(80, min(int(w), 900))
    m = next((x for x in _leer_biblioteca() if x.get("id") == bid), None)
    if not m:
        raise HTTPException(404, "No existe ese modelo")
    g = _gab_obj(m["gabinete"])
    return _mini_respuesta(f"b:{bid}:{w}", lambda: _png_gabinete(g, Estandar(), w))


# --------------------------------------------------------------- exportación

class ProyectoCompletoIn(BaseModel):
    """#038 — varios muebles que se despiezan como un solo trabajo."""
    nombre: str = "Proyecto"
    cliente: str = ""
    muebles: List[ProyectoIn] = []


class ExportarProyectoIn(ProyectoCompletoIn):
    """#071 — la exportación del proyecto entero, no de la pestaña de enfrente."""
    carpeta: Optional[str] = None
    # #072 — el DXF de isométricos ya no se exporta.
    # #076 — y el corte se parte en dos máquinas: la fresa recorre contornos, la
    # sierra lineal sólo hace cortes de lado a lado. Son dos acomodos distintos,
    # así que son dos archivos distintos por máquina.
    salidas: List[str] = ["dxf_fresa", "pdf_fresa", "dxf_sierra", "pdf_sierra",
                          "dxf_piezas", "xlsx", "pdf", "fichas"]


@app.post("/api/proyecto/calcular")
def proyecto_calcular(req: ProyectoCompletoIn):
    """El despiece del proyecto entero, no mueble por mueble.

    Es la razón de agrupar los muebles: **el nesting se hace una sola vez con
    todas las piezas juntas**. Dos muebles despiezados por separado desperdician
    el retazo de cada hoja; despiezados juntos, las piezas de uno caben en el
    hueco que deja el otro. Esa diferencia es tablero que no se compra.
    """
    todas: List = []
    detalle = []
    for m in req.muebles:
        pr = _a_proyecto(m)
        if not pr.gabinetes:
            continue
        piezas, hojas, _ = pr.calcular()
        detalle.append({"mueble": pr.nombre, "piezas": len(piezas),
                        "hojas": len(hojas)})
        # el código de cada pieza se prefija con el mueble: en el taller hay que
        # saber a cuál va cada corte
        for pz in piezas:
            pz.mueble = f"{pr.nombre} · {pz.mueble}" if pz.mueble else pr.nombre
        todas += piezas

    if not todas:
        return {"piezas": [], "hojas": [], "costeo": [], "resumen": {},
                "muebles": detalle, "ahorro": None}

    base = _a_proyecto(req.muebles[0])
    base.nombre = req.nombre
    base.cliente = req.cliente
    hojas = nestear_todo(base, todas)
    costeo = base.costeo(todas, hojas)
    sueltas = sum(d["hojas"] for d in detalle)
    # se serializa igual que /api/calcular para que la interfaz pinte los
    # resultados del proyecto con el mismo código que los de un mueble
    return {
        "piezas": [{
            "codigo": x.codigo, "mueble": x.mueble, "nombre": x.nombre,
            "material": x.material, "espesor": x.espesor,
            "largo": round(x.largo, 1), "ancho": round(x.ancho, 1),
            "cantidad": x.cantidad, "area": round(x.area_m2, 4),
            "canto_ml": round(x.ml_canto * x.cantidad, 3),
            "canto": list(x.canto), "veta": x.veta, "nota": x.nota,
        } for x in todas],
        "hojas": [{
            "idx": h.idx, "material": h.material, "espesor": h.espesor,
            "ancho": h.ancho, "alto": h.alto,
            "aprov": round(h.aprovechamiento, 4),
            "piezas": [{
                "codigo": c.pieza.codigo, "nombre": c.pieza.nombre,
                "x": round(c.x, 1), "y": round(c.y, 1),
                "w": round(c.w, 1), "h": round(c.h, 1), "rot": c.rotada,
            } for c in h.colocaciones],
        } for h in hojas],
        "costeo": costeo,
        "muebles": detalle,
        # lo que se ahorra por nestear todo junto en vez de mueble por mueble
        "ahorro": {"hojas_sueltas": sueltas, "hojas_juntas": len(hojas),
                   "diferencia": sueltas - len(hojas)},
        "resumen": {
            "muebles": len(detalle),
            "piezas_unicas": len(todas),
            "piezas_totales": sum(x.cantidad for x in todas),
            "hojas": len(hojas),
        },
    }


def nestear_todo(pr: Proyecto, piezas, medidas=None) -> List:
    """Acomoda TODAS las piezas del proyecto de una sola vez.

    Es el mismo nesting del mueble suelto; lo que cambia es que recibe las
    piezas de todos los muebles juntas, que es donde está la ganancia.
    """
    from core.nesting import nestear
    std = copy.deepcopy(pr.estandar)
    std.veta_respetada = True
    return nestear(piezas, std, medidas or pr.hojas_por_material())

@app.post("/api/exportar")
def exportar(req: ExportarIn):
    pr = _a_proyecto(req.proyecto)
    if not pr.gabinetes:
        raise HTTPException(400, "El proyecto no tiene gabinetes")
    carpeta = req.carpeta or os.path.join(SALIDA, _slug(pr.nombre))
    os.makedirs(carpeta, exist_ok=True)
    exp = _exportadores()
    dxf, xlsx, pdf, fichas = exp
    piezas, hojas, _ = pr.calcular()
    costeo = pr.costeo(piezas, hojas)
    std = pr.estandar
    hechos = _archivos_de_corte(exp, carpeta, pr, piezas, hojas, req.salidas, pr.nombre)
    if "dxf_piezas" in req.salidas:
        hechos.append(dxf.exportar_piezas_detalle(piezas, os.path.join(carpeta, "piezas_detalle.dxf")))
    cubs = pr.cubiertas()
    if "xlsx" in req.salidas:
        hechos.append(xlsx.exportar(piezas, hojas, os.path.join(carpeta, "lista_corte.xlsx"),
                                    pr.nombre, costeo, cubs))
    if "pdf" in req.salidas:
        hechos.append(pdf.exportar(pr.gabinetes, hojas, std,
                                   os.path.join(carpeta, "planos.pdf"), pr.nombre, pr))
    if "fichas" in req.salidas:      # #007 #017
        # los colores salen del mismo catálogo que pinta el 3D
        colores = {m.nombre: m.color for m in pr.catalogo}
        hechos.append(fichas.exportar(piezas, os.path.join(carpeta, "fichas_de_corte.pdf"),
                                      pr.nombre, colores))
    return {"carpeta": carpeta, "archivos": [os.path.basename(h) for h in hechos]}


def _hojas_sierra(pr: Proyecto, piezas, medidas=None):
    """#076 — el mismo despiece, acomodado para SIERRA LINEAL.

    No es el acomodo de la fresa con otro nombre. Una fresa entra donde sea y
    recorta el contorno; una sierra sólo hace cortes que atraviesan el tablero
    de lado a lado, así que hay que volver a acomodar con esa restricción y sale
    un poco menos apretado. Mandarle a la sierra el acomodo de la fresa es
    mandarle algo que no se puede cortar.
    """
    from core.nesting import nestear_guillotina
    std = copy.deepcopy(pr.estandar)
    std.veta_respetada = True
    return nestear_guillotina(piezas, std, medidas or pr.hojas_por_material())


def _archivos_de_corte(exp, carpeta, pr, piezas, hojas, salidas, nombre, medidas=None):
    """Los archivos de corte: uno por máquina, DXF y PDF."""
    dxf, xlsx, pdf, fichas = exp
    hechos = []
    if "dxf_fresa" in salidas:
        hechos.append(dxf.exportar_nesting(hojas, os.path.join(carpeta, "corte_fresa.dxf")))
    if "pdf_fresa" in salidas:
        hechos.append(pdf.exportar_hojas(hojas, os.path.join(carpeta, "corte_fresa.pdf"),
                                         nombre, "CORTE EN FRESA / ROUTER"))
    if "dxf_sierra" in salidas or "pdf_sierra" in salidas:
        hs = _hojas_sierra(pr, piezas, medidas)
        if "dxf_sierra" in salidas:
            hechos.append(dxf.exportar_sierra(hs, os.path.join(carpeta, "corte_sierra.dxf")))
        if "pdf_sierra" in salidas:
            hechos.append(pdf.exportar_sierra(hs, os.path.join(carpeta, "corte_sierra.pdf"),
                                              nombre))
    return hechos


def _salidas_de_un_mueble(pr: Proyecto, carpeta: str, salidas, exp) -> List[str]:
    """El juego completo de UN mueble en su carpeta. Es lo mismo que exporta el
    botón de siempre; aquí se reutiliza para la subcarpeta de cada uno (#071)."""
    dxf, xlsx, pdf, fichas = exp
    os.makedirs(carpeta, exist_ok=True)
    piezas, hojas, _ = pr.calcular()
    hechos = _archivos_de_corte(exp, carpeta, pr, piezas, hojas, salidas, pr.nombre)
    if "dxf_piezas" in salidas:
        hechos.append(dxf.exportar_piezas_detalle(piezas, os.path.join(carpeta, "piezas_detalle.dxf")))
    if "xlsx" in salidas:
        hechos.append(xlsx.exportar(piezas, hojas, os.path.join(carpeta, "lista_corte.xlsx"),
                                    pr.nombre, pr.costeo(piezas, hojas), pr.cubiertas()))
    if "pdf" in salidas:
        hechos.append(pdf.exportar(pr.gabinetes, hojas, pr.estandar,
                                   os.path.join(carpeta, "planos.pdf"), pr.nombre, pr))
    if "fichas" in salidas:
        colores = {m.nombre: m.color for m in pr.catalogo}
        hechos.append(fichas.exportar(piezas, os.path.join(carpeta, "fichas_de_corte.pdf"),
                                      pr.nombre, colores))
    return hechos


@app.post("/api/proyecto/exportar")
def proyecto_exportar(req: ExportarProyectoIn):
    """#071 — el proyecto ENTERO a disco: un juego conjunto + uno por mueble.

    Hasta la 0.10.4 sólo se podía ver el despiece del proyecto completo (#038),
    pero para sacar archivos había que ir pestaña por pestaña — y las hojas que
    salían así **no eran las del cálculo conjunto**, sino las de cada mueble por
    separado. Lo que se veía en pantalla y lo que se mandaba al corte no
    coincidían.

    Cómo queda la carpeta, tal como lo pidió Mike:

        <carpeta>/
          planos.pdf              ← TODOS los muebles, un solo archivo, en orden
          corte_fresa.dxf/.pdf    ← el nesting conjunto: es el que se corta
          corte_sierra.dxf/.pdf   ← el mismo despiece, cortable en seccionadora
          piezas_detalle.dxf · lista_corte.xlsx · fichas_de_corte.pdf
          1 - <mueble>/           ← el juego completo de ese mueble, por si se
          2 - <mueble>/              manda suelto a otro taller

    Lo de la raíz es lo que manda para comprar y cortar; las subcarpetas son
    para trabajar un mueble aparte. **Las dos cosas no suman**: si se cortan las
    hojas de la raíz, las de las subcarpetas ya están adentro.
    """
    exp = _exportadores()
    dxf, xlsx, pdf, fichas = exp
    proyectos = [_a_proyecto(m) for m in req.muebles]
    proyectos = [p for p in proyectos if p.gabinetes]
    if not proyectos:
        raise HTTPException(400, "El proyecto no tiene muebles con gabinetes")

    carpeta = req.carpeta or os.path.join(SALIDA, _slug(req.nombre))
    os.makedirs(carpeta, exist_ok=True)

    # --- el juego conjunto ---
    # Ojo: NO se juntan los gabinetes en un solo Proyecto. Cada mueble tiene su
    # propio origen de coordenadas, así que fundirlos amontonaría los muebles en
    # el mismo sitio y uniría cubiertas de tramos que no se tocan. Se calcula
    # cada uno por su lado y se junta lo que sí se junta: las piezas.
    todas, cubs = [], []
    for pr_m in proyectos:
        piezas, _h, _s = pr_m.calcular()
        for pz in piezas:
            pz.mueble = f"{pr_m.nombre} · {pz.mueble}" if pz.mueble else pr_m.nombre
        todas += piezas
        cubs += list(pr_m.cubiertas())

    base = proyectos[0]
    # los tamaños de hoja de TODOS los muebles: si el segundo trae un material
    # que el primero no usa, nestear con sólo el catálogo del primero lo acomoda
    # en una hoja que no es la suya.
    medidas = {}
    for pr_m in proyectos:
        medidas.update(pr_m.hojas_por_material())
    hojas = nestear_todo(base, todas, medidas)
    costeo = base.costeo(todas, hojas)

    hechos = _archivos_de_corte(exp, carpeta, base, todas, hojas, req.salidas,
                                req.nombre, medidas)
    if "dxf_piezas" in req.salidas:
        hechos.append(dxf.exportar_piezas_detalle(todas, os.path.join(carpeta, "piezas_detalle.dxf")))
    if "xlsx" in req.salidas:
        hechos.append(xlsx.exportar(todas, hojas, os.path.join(carpeta, "lista_corte.xlsx"),
                                    req.nombre, costeo, cubs))
    if "pdf" in req.salidas:
        hechos.append(pdf.exportar_proyecto(proyectos, hojas,
                                            os.path.join(carpeta, "planos.pdf"), req.nombre))
    if "fichas" in req.salidas:
        colores = {}
        for pr_m in proyectos:
            for m in pr_m.catalogo:
                colores.setdefault(m.nombre, m.color)
        hechos.append(fichas.exportar(todas, os.path.join(carpeta, "fichas_de_corte.pdf"),
                                      req.nombre, colores))

    # --- y el juego de cada mueble, en su subcarpeta ---
    # El número va delante del nombre para que la carpeta se ordene igual que el
    # proyecto y no alfabéticamente, que es como se pierde el orden de armado.
    sub = []
    for i, pr_m in enumerate(proyectos, start=1):
        cp = os.path.join(carpeta, f"{i} - {_slug(pr_m.nombre)}")
        arch = _salidas_de_un_mueble(pr_m, cp, req.salidas, exp)
        sub.append({"mueble": pr_m.nombre, "carpeta": os.path.basename(cp),
                    "archivos": [os.path.basename(a) for a in arch]})

    return {
        "carpeta": carpeta,
        "archivos": [os.path.basename(h) for h in hechos],
        "muebles": sub,
        "resumen": {"muebles": len(proyectos),
                    "piezas": sum(x.cantidad for x in todas),
                    "hojas": len(hojas)},
    }


@app.post("/api/guardar")
def guardar(req: ExportarIn):
    pr = _a_proyecto(req.proyecto)
    carpeta = req.carpeta or SALIDA
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, _slug(pr.nombre) + EXT)
    pr.guardar(ruta)
    return {"ruta": ruta}


@app.get("/api/abrir")
def abrir(ruta: str):
    if not os.path.exists(ruta):
        raise HTTPException(404, "No existe el archivo")
    return Proyecto.abrir(ruta).to_dict()


def _slug(s):
    import re
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_") or "proyecto"


# --------------------------------------------------------------- UI estática
@app.get("/api/diagnostico")
def diagnostico():
    return {"raiz": RAIZ, "ui": UI, "ui_encontrada": UI is not None,
            "archivos_en_raiz": sorted(os.listdir(RAIZ))[:40],
            "python": sys.version, "ejecutable": sys.executable}


if UI:
    app.mount("/", StaticFiles(directory=UI, html=True), name="ui")
else:
    # Sin interfaz no hay app: se avisa en pantalla en vez de devolver un 404 mudo.
    from fastapi.responses import HTMLResponse

    @app.get("/{_:path}", response_class=HTMLResponse)
    def sin_ui(_: str = ""):
        return f"""<body style="background:#0f1115;color:#e6e8ec;
          font:14px/1.6 system-ui;padding:40px">
          <h2 style="color:#0080C1">No se encontró la interfaz</h2>
          <p>El backend arrancó, pero falta la carpeta <code>ui/</code>
          junto a <code>server.py</code>.</p>
          <p style="color:#9aa1ad">Buscada desde: <code>{RAIZ}</code><br>
          Contenido: <code>{', '.join(sorted(os.listdir(RAIZ))[:20])}</code></p>
          <p>Es un problema de empaquetado. Reinstala la aplicación.</p></body>"""


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8760)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
