"""Rutas de «Leer plano» para el server de Taller 101.

Se montan en `server.py` con dos líneas:

    from identificador.rutas import router as router_plano
    app.include_router(router_plano)

Todo cuelga de /api/plano/. El modelo del proyecto no se toca desde aquí: el
endpoint de importar devuelve gabinetes ya traducidos y la UI los mete al estado,
igual que hace con la biblioteca de modelos.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import adaptador, aprendizaje, cliente, lectura
from .motor import ambiguedad, contrato, validate
from .motor.schema import Alzado, Documento

router = APIRouter(prefix="/api/plano", tags=["leer plano"])

TRABAJOS: Dict[str, dict] = {}
TMP = Path(tempfile.gettempdir()) / "taller101-planos"
TMP.mkdir(parents=True, exist_ok=True)
FORMATOS = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


class Resolucion(BaseModel):
    respuestas: Dict[str, Any] = {}
    materiales: Dict[str, Optional[str]] = {}
    aprender: bool = True


def _avisar(t: dict, titulo: str, detalle: str = ""):
    t.setdefault("progreso", []).append({"titulo": titulo, "detalle": detalle})


# ------------------------------------------------------------------ lectura
def _modo() -> str:
    """Quién lee el plano: el servicio de Taller 101, o esta misma máquina.

    En la app instalada siempre es el servicio: ahí no hay llave de API ni están
    las librerías pesadas. En la máquina de desarrollo, si no hay servicio
    configurado, se lee en local con la llave puesta a mano.
    """
    if cliente.configurado():
        return "servicio"
    return "local"


def _leer(trabajo_id: str, archivo: Path, despacho: Optional[str], backend: str):
    t = TRABAJOS[trabajo_id]
    try:
        t["estado"] = "procesando"
        # #046 — la llave se teclea con el programa ya abierto la primera vez.
        # `vision` la lee del entorno, así que aquí se refresca desde el perfil
        # del taller antes de leer; si no, la primera lectura después de pegarla
        # fallaba y había que reiniciar la app sin saber por qué.
        try:
            from core import taller
            v = taller.llave()
            if v:
                os.environ["ANTHROPIC_API_KEY"] = v
        except Exception:                                       # noqa: BLE001
            pass
        salida = TMP / trabajo_id
        salida.mkdir(parents=True, exist_ok=True)

        if _modo() == "servicio":
            _avisar(t, "Mandando el plano", "servicio de Taller 101")
            crudo = cliente.leer(archivo, despacho=despacho)
            res = lectura.de_json(crudo, salida)
            for v in res["vistas"]:
                if v.get("procesada"):
                    _avisar(t, "Vista leída", v.get("titulo") or "")
        else:
            res = lectura.leer(archivo, salida, despacho=despacho, backend=backend,
                               avisar=lambda ti, de="": _avisar(t, ti, de))

        t.update(estado="listo", documento=res["documento"], vistas=res["vistas"],
                 bbox=res["bbox"], preguntas=res["preguntas"],
                 tipo_origen=res["tipo_origen"], dir=str(salida),
                 terminado=datetime.now(timezone.utc).isoformat())
    except Exception as e:                                    # noqa: BLE001
        t.update(estado="error", error=_en_castellano(e),
                 error_crudo=str(e), traza=traceback.format_exc())


# Lo que puede contestar la API de Anthropic, dicho para un taller.
#
# #053 — Mike se comió tres errores seguidos en inglés técnico: primero un
# `'str' object is not a mapping`, luego «Streaming is required for operations
# that may take longer than 10 minutes». Un carpintero no tiene por qué leer
# eso, y peor: ninguno de los dos decía qué hacer. El mensaje crudo se guarda
# aparte por si hay que diagnosticar.
_EN_CASTELLANO = [
    ("streaming is required",
     "Falla nuestra: la petición al modelo se armó mal. Repórtalo, tiene "
     "arreglo del lado del programa."),
    ("authentication_error",
     "Anthropic no aceptó la llave. Revísala en Ajustes → Leer plano."),
    ("invalid x-api-key",
     "Anthropic no aceptó la llave. Revísala en Ajustes → Leer plano."),
    ("credit balance",
     "La cuenta de Anthropic se quedó sin saldo. Cárgale en "
     "platform.claude.com → Settings → Billing."),
    ("rate_limit",
     "Anthropic está limitando las peticiones. Espera un minuto y vuelve a "
     "intentar."),
    ("overloaded",
     "El modelo está saturado en este momento. Vuelve a intentar en un rato."),
    ("timeout",
     "El plano tardó demasiado. Prueba con una lámina de un solo mueble."),
    ("connection",
     "No hubo conexión a internet mientras se leía el plano."),
    ("object is not a mapping",
     "El modelo contestó a medias. Prueba otra vez; si se repite, la lámina "
     "trae demasiados módulos para una sola pasada."),
]


def _en_castellano(e: Exception) -> str:
    crudo = str(e)
    bajo = crudo.lower()
    for pista, dicho in _EN_CASTELLANO:
        if pista in bajo:
            return dicho
    return crudo


# ------------------------------------------------------------------ rutas
def _llave_puesta() -> bool:
    """#046 — ¿hay llave? Se le pregunta al perfil del taller, no sólo al entorno.

    `server.py` copia la llave al entorno al arrancar, pero si el usuario la
    teclea con el programa ya abierto —que es justo lo que pasa la primera vez—
    el entorno de este proceso puede ir un paso atrás. El archivo es la verdad.
    """
    try:
        from core import taller
        if taller.llave():
            return True
    except Exception:                                           # noqa: BLE001
        pass
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _falla_pesada() -> str:
    """Vacío si la mitad pesada carga; si no, por qué no.

    Vale la pena distinguirlo de «falta la llave»: son dos fallas distintas con
    dos arreglos distintos, y hasta la 0.9.1 las dos daban el mismo mensaje.
    """
    try:
        from .motor import foto, geometria, imaging, sheet, vision   # noqa: F401
        return ""
    except Exception as e:                                      # noqa: BLE001
        return f"{type(e).__name__}: {e}"


@router.get("/salud")
def salud():
    """Si «Leer plano» va a funcionar en este equipo, y por qué no si no.

    El panel lo usa para avisar antes de que el usuario suba un plano y espere
    tres minutos para recibir un error.
    """
    modo = _modo()
    if modo == "servicio":
        s = cliente.salud()
        return {"ok": bool(s.get("ok")), "modo": "servicio", "falta":
                None if s.get("ok") else "servicio",
                "servicio": cliente._ajustes()["url"], "modelo": s.get("modelo"),
                "trabajos": len(TRABAJOS),
                "motivo": None if s.get("ok") else
                          ("No se pudo contactar el servicio de lectura de planos. "
                           f"({s.get('motivo', '')})")}

    # #046 — desde #040 el lector viaja DENTRO de la app, así que aquí ya no se
    # manda a nadie a abrir «Iniciar servicio.bat»: ese mensaje era de cuando la
    # mitad pesada vivía fuera, y dejaba al usuario buscando en su disco una
    # carpeta que su instalador ya no trae. Lo único que puede faltar es la
    # llave — o que las librerías no carguen, que es otra cosa y se dice aparte.
    roto = _falla_pesada()
    if roto:
        return {"ok": False, "modo": "local", "servicio": None, "falta": "librerias",
                "modelo": aprendizaje.MODELO_DEFAULT, "trabajos": len(TRABAJOS),
                "detalle": roto,
                "motivo": ("Este equipo no puede abrir planos: el lector no cargó. "
                           "Vuelve a instalar Taller 101; si sigue igual, manda "
                           f"esta línea — {roto}")}

    hay = _llave_puesta()
    return {"ok": hay, "modo": "local", "servicio": None,
            "modelo": aprendizaje.MODELO_DEFAULT, "trabajos": len(TRABAJOS),
            "falta": None if hay else "llave",
            "motivo": None if hay else
                      ("Falta la llave de Anthropic. Se teclea una vez y se queda "
                       "en este equipo, en tu carpeta de Taller 101.")}


@router.post("/analizar")
async def analizar(tareas: BackgroundTasks,
                   archivo: UploadFile = File(...),
                   despacho: Optional[str] = Form(None),
                   proyecto: Optional[str] = Form(None),
                   backend: str = Form("anthropic")):
    if not archivo.filename.lower().endswith(FORMATOS):
        raise HTTPException(400, "Formato no soportado. Usa PDF, PNG, JPG o TIF.")
    est = salud()
    if not est["ok"]:
        raise HTTPException(400, est["motivo"] or "«Leer plano» no está disponible.")
    tid = uuid.uuid4().hex[:12]
    destino = TMP / f"{tid}_{archivo.filename}"
    with destino.open("wb") as fh:
        shutil.copyfileobj(archivo.file, fh)
    TRABAJOS[tid] = {"id": tid, "estado": "en_cola", "archivo": archivo.filename,
                     "despacho": despacho, "proyecto": proyecto, "progreso": [],
                     "creado": datetime.now(timezone.utc).isoformat()}
    tareas.add_task(_leer, tid, destino, despacho, backend)
    return {"trabajo_id": tid, "estado": "en_cola"}


@router.get("/{tid}")
def estado(tid: str):
    t = TRABAJOS.get(tid)
    if not t:
        raise HTTPException(404, "no existe ese trabajo")
    if t["estado"] != "listo":
        return {k: v for k, v in t.items() if k not in ("documento", "preguntas")}
    doc: Documento = t["documento"]
    pay = contrato.construir(doc, tipo_origen=t["tipo_origen"],
                             proyecto={"nombre": t.get("proyecto")})
    return {"id": tid, "estado": "listo", "archivo": t["archivo"],
            "vistas": t["vistas"], "bbox": t["bbox"],
            "origen": pay["origen"],
            "resultado": pay,
            "materiales_del_plano": adaptador.materiales_del_plano(pay),
            # Las preguntas de material NO van a la lista: el panel las resuelve con
            # el selector del catálogo, que es más útil que escribir el nombre a mano.
            "preguntas": [q.dict() for q in t["preguntas"] if q.tipo != "material"],
            "requiere_dialogo": any(q.obligatoria and q.tipo != "material"
                                    for q in t["preguntas"])}


@router.get("/{tid}/vista/{nombre}")
def imagen(tid: str, nombre: str):
    t = TRABAJOS.get(tid)
    if not t or "dir" not in t:
        raise HTTPException(404, "no existe ese trabajo")
    p = Path(t["dir"]) / nombre
    if not p.exists() or p.parent != Path(t["dir"]):
        raise HTTPException(404, "no existe esa imagen")
    return FileResponse(p, media_type="image/png")


@router.post("/{tid}/importar")
def importar(tid: str, r: Resolucion):
    """Aplica las respuestas y devuelve los gabinetes ya en el modelo de Taller 101."""
    t = TRABAJOS.get(tid)
    if not t or t["estado"] != "listo":
        raise HTTPException(409, "el trabajo no está listo")
    doc: Documento = t["documento"]
    # el mapeo de materiales del panel ES la respuesta a las preguntas de material
    respuestas = dict(r.respuestas)
    for q in t["preguntas"]:
        if q.tipo == "material" and q.ref in r.materiales:
            respuestas[q.id] = {"material": r.materiales[q.ref] or q.ref}
    ambiguedad.aplicar(doc, respuestas)
    doc.avisos = []
    validate.validar(doc)
    pendientes = [q for q in ambiguedad.generar(doc) if q.obligatoria]
    if r.aprender and t.get("despacho"):
        pass  # (el guardado real va más abajo, ya con las respuestas completas)

    pay = contrato.construir(
        doc, tipo_origen=t["tipo_origen"], proyecto={"nombre": t.get("proyecto")},
        pendientes=[{"pregunta": q.id, "titulo": q.titulo} for q in pendientes])
    conv = adaptador.convertir(pay, {k: v for k, v in r.materiales.items() if v})

    if r.aprender and t.get("despacho"):
        aprendizaje.guardar(t["despacho"], t["preguntas"], respuestas)

    t["documento"] = doc
    t["preguntas"] = ambiguedad.generar(doc)
    return {"gabinetes": conv["gabinetes"], "avisos": conv["avisos"] +
            [a.mensaje for a in doc.avisos if a.nivel in ("warn", "error")],
            "resumen": conv["resumen"],
            "pendientes": [q.dict() for q in pendientes],
            "listo": not pendientes}


@router.post("/{tid}/diagnostico")
def diagnostico(tid: str):
    """#055 — Deja en una carpeta todo lo que hizo falta para leer este plano.

    Los recortes que se le mandaron al modelo y lo que contestó, tal cual. Es lo
    que convierte un «no reconocí ningún mueble» —que no se puede investigar sin
    volver a pagar la lectura— en algo que se puede mandar y revisar.

    NO incluye el plano original: pesa, y es de un cliente.
    """
    t = TRABAJOS.get(tid)
    if not t or not t.get("dir"):
        raise HTTPException(404, "no existe ese trabajo")
    origen = Path(t["dir"])
    try:
        from core import taller
        base = taller.carpeta() / "diagnosticos"
    except Exception:                                           # noqa: BLE001
        base = Path.home() / "Taller 101" / "diagnosticos"
    sello = datetime.now().strftime("%Y%m%d-%H%M")
    limpio = "".join(c for c in Path(t.get("archivo") or "plano").stem
                     if c.isalnum() or c in " -_")[:40].strip() or "plano"
    destino = base / f"{limpio} {sello}"
    destino.mkdir(parents=True, exist_ok=True)

    copiados = []
    for p in sorted(origen.iterdir()):
        if p.is_file() and p.suffix.lower() in (".png", ".json", ".txt"):
            shutil.copy2(p, destino / p.name)
            copiados.append(p.name)
    resumen = {
        "archivo": t.get("archivo"), "estado": t.get("estado"),
        "tipo_origen": t.get("tipo_origen"), "vistas": t.get("vistas"),
        "progreso": t.get("progreso"), "error": t.get("error"),
        "error_crudo": t.get("error_crudo"), "traza": t.get("traza"),
        "salud": salud(),
    }
    (destino / "resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=1, default=str),
        encoding="utf-8")
    return {"ok": True, "carpeta": str(destino), "archivos": len(copiados) + 1}


@router.delete("/{tid}")
def cerrar(tid: str):
    t = TRABAJOS.pop(tid, None)
    if t and t.get("dir"):
        shutil.rmtree(t["dir"], ignore_errors=True)
    return {"ok": True}
