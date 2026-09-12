"""#031 — El escritorio hablándole al servicio de Taller 101.

Lo único que sale de la máquina del taller es el plano; lo único que regresa es
el resultado en JSON. La llave de API vive en el servidor y nunca se distribuye.

Se usa `urllib` de la biblioteca estándar a propósito: una dependencia menos que
empaquetar, y lo que hace falta —subir un archivo y leer un JSON— no justifica
traer `requests` ni `httpx` al instalador.
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

ESPERA = 300.0          # s — un plano grande con seis vistas tarda minutos


AQUI_MISMO = "http://127.0.0.1:8080"     # donde lo deja «Iniciar servicio.bat»
_visto = {"url": "", "cuando": 0.0}
VIGENCIA = 20.0          # s que dura el hallazgo antes de volver a buscar


def _hay_algo(url: str, segundos: float = 1.5) -> bool:
    """¿Contesta un servicio de Taller 101 en esa dirección?"""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/v1/salud", timeout=segundos) as r:
            return bool(json.loads(r.read().decode("utf-8")).get("ok") is not None)
    except Exception:                                           # noqa: BLE001
        return False


def _ajustes() -> dict:
    """Dónde vive el servicio. Tres formas, de la más explícita a la más cómoda.

    1. La variable de entorno, para probar.
    2. `%USERPROFILE%\Taller 101\servicio.json`, para dejarlo fijo.
    3. **Buscarlo aquí mismo**: si alguien abrió «Iniciar servicio.bat» en esta
       computadora, está en el 8080 y se usa sin configurar nada.

    La tercera existe porque las dos primeras piden que el usuario edite algo
    antes de poder usar la función, y eso es una llamada de soporte por
    instalación. Con el servicio abierto, «Leer plano» simplemente funciona.
    """
    lic = os.environ.get("T101_LICENCIA", "")
    url = os.environ.get("T101_PLANOS_URL", "")
    if url:
        return {"url": url, "licencia": lic, "como": "variable de entorno"}

    p = Path.home() / "Taller 101" / "servicio.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("url"):
            return {"url": str(d["url"]), "licencia": str(d.get("licencia") or lic),
                    "como": "servicio.json"}
    except Exception:                                           # noqa: BLE001
        pass

    ahora = time.time()
    if _visto["url"] and ahora - _visto["cuando"] < VIGENCIA:
        return {"url": _visto["url"], "licencia": lic, "como": "aquí mismo"}
    if _hay_algo(AQUI_MISMO):
        _visto.update(url=AQUI_MISMO, cuando=ahora)
        return {"url": AQUI_MISMO, "licencia": lic, "como": "aquí mismo"}
    return {"url": "", "licencia": lic, "como": None}


class ServicioNoDisponible(RuntimeError):
    """No se pudo hablar con el servicio. El mensaje es para que lo lea Mike."""


def configurado() -> bool:
    return bool(_ajustes()["url"])


def _cuerpo_multipart(archivo: Path, campos: dict) -> tuple:
    """Arma un multipart/form-data a mano. Es menos código que una dependencia."""
    frontera = "----t101" + uuid.uuid4().hex
    partes = []
    for k, v in campos.items():
        if v is None:
            continue
        partes.append(
            f"--{frontera}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
            .encode("utf-8"))
    tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
    partes.append(
        f"--{frontera}\r\nContent-Disposition: form-data; name=\"archivo\"; "
        f"filename=\"{archivo.name}\"\r\nContent-Type: {tipo}\r\n\r\n".encode("utf-8"))
    partes.append(archivo.read_bytes())
    partes.append(f"\r\n--{frontera}--\r\n".encode("utf-8"))
    return b"".join(partes), f"multipart/form-data; boundary={frontera}"


def leer(archivo: Path, despacho: Optional[str] = None,
         url: Optional[str] = None, licencia: Optional[str] = None,
         espera: float = ESPERA) -> dict:
    """Manda el plano al servicio y devuelve el JSON del resultado."""
    aj = _ajustes()
    destino = (url or aj["url"]).rstrip("/")
    if not destino:
        raise ServicioNoDisponible(
            "No está configurado el servicio de lectura de planos.")
    lic = licencia if licencia is not None else aj["licencia"]

    # Lo aprendido de este despacho viaja CON el plano: el servicio no guarda
    # nada de ningún taller, así que la memoria vive aquí y se manda cada vez.
    perfil = None
    if despacho:
        from . import aprendizaje
        d = aprendizaje.perfil_guardado(despacho)
        if d:
            perfil = json.dumps(d, ensure_ascii=False)
    cuerpo, tipo = _cuerpo_multipart(archivo, {"despacho": despacho,
                                               "perfil": perfil})
    cab = {"Content-Type": tipo}
    if lic:
        cab["Authorization"] = f"Bearer {lic}"
    req = urllib.request.Request(destino + "/v1/leer", data=cuerpo,
                                 headers=cab, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=espera) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = ""
        try:
            detalle = json.loads(e.read().decode("utf-8")).get("detail", "")
        except Exception:                                       # noqa: BLE001
            pass
        if e.code in (401, 403):
            raise ServicioNoDisponible(
                "El servicio rechazó la licencia de este equipo." +
                (f" ({detalle})" if detalle else "")) from e
        raise ServicioNoDisponible(
            f"El servicio contestó {e.code}." + (f" {detalle}" if detalle else "")) from e
    except urllib.error.URLError as e:
        raise ServicioNoDisponible(
            "No se pudo contactar al servicio de lectura de planos. "
            "Revisa la conexión a internet.") from e


def salud(url: Optional[str] = None) -> dict:
    destino = (url or _ajustes()["url"]).rstrip("/")
    if not destino:
        return {"ok": False, "motivo": "sin configurar"}
    try:
        with urllib.request.urlopen(destino + "/v1/salud", timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                      # noqa: BLE001
        return {"ok": False, "motivo": str(e)}
