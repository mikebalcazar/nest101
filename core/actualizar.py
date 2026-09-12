"""#087 — Saber si hay versión nueva, y de dónde bajarla.

Mike: *«necesito replicar para que haya un link de actualización de aplicación…
que se pueda descargar la última versión desde el programa»*.

Es el mismo mecanismo de draw101, en el mismo repo: `mikebalcazar/descargas`.

## El contrato — comprobado, no supuesto

La primera versión de este archivo leía un formato plano que yo había deducido
de la nota del proyecto. **Estaba mal.** Se clonó el repo público y se miró lo
que draw101 ya publica, que es esto:

    https://raw.githubusercontent.com/mikebalcazar/descargas/main/nest101.json

        { "nest101": {
            "version": "0.15.4", "fecha": "2026-09-08",
            "notas": ["renglón", "renglón"],
            "pagina": "…#readme",
            "windows": { "archivo": "nest101-0.15.4-setup.exe",
                         "bytes": 179479165, "sha256": "…",
                         "url":    "…/releases/download/nest101-0.15.4/…exe",
                         "ultima": "…/releases/tag/nest101-ultima" } } }

Toda la familia comparte un repo, así que el bloque cuelga **del nombre de la
app**. Con el formato que yo había supuesto, este programa no habría entendido
ni un solo archivo publicado: habría dicho «estás en la última» para siempre,
que es la peor manera de fallar — callada.

Y **`ultima` es una PÁGINA**: el enlace del instalador con su versión viene
dentro del JSON, con su huella. Eso también lo suponía al revés.

Desde #090 la release fija guarda además **una copia sin número en el nombre**
—`nest101-setup.exe`—, que da un enlace directo que no cambia nunca. Lo pidió
Mike para poder mandarlo por WhatsApp. Es `url_fija`, y es el mismo archivo.

## Tres decisiones

**No se descarga solo, ni se instala solo.** El programa dice «hay una nueva» y
enseña el enlace. Un instalador de 180 MB bajándose sin permiso en el taller,
con la máquina a media exportación, es una interrupción, no un servicio.

**Si no hay internet, no pasa nada.** Este taller trabaja sin red la mitad del
tiempo. Cualquier fallo de red se traga y se contesta «no se pudo revisar» —
nunca un error en pantalla, y nunca bloquea el arranque.

**Comparar versiones se hace por número, no por texto.** `"0.9.0" > "0.15.3"`
es verdad como texto y mentira como versión, y es exactamente el rango donde
está este programa.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Optional, Tuple

USUARIO = "mikebalcazar"
REPO = "descargas"
APP = "nest101"

URL_ESTADO = f"https://raw.githubusercontent.com/{USUARIO}/{REPO}/main/{APP}.json"
# La página fija de «la última». Es una PÁGINA, no un archivo: el enlace del
# archivo viene dentro del JSON, con su versión y su huella. Se comprobó
# leyendo lo que draw101 ya publicó en el repo, no suponiéndolo.
URL_ULTIMA = f"https://github.com/{USUARIO}/{REPO}/releases/tag/{APP}-ultima"
# El enlace DIRECTO que no cambia nunca: el archivo de la release fija va sin
# número en el nombre. Sirve para mandarlo por WhatsApp o ponerlo en una página.
URL_FIJA = (f"https://github.com/{USUARIO}/{REPO}/releases/download/"
            f"{APP}-ultima/{APP}-setup.exe")
URL_TODAS = f"https://github.com/{USUARIO}/{REPO}/releases"
URL_DESCARGA = URL_ULTIMA          # hasta que el JSON diga el archivo exacto

ESPERA = 6                    # segundos; si no contesta, no contestó
_CACHE: dict = {}
_VIGENCIA = 15 * 60           # no se pregunta más de una vez cada cuarto de hora


def _partes(v: str) -> Tuple[int, ...]:
    """«0.15.3» → (0, 15, 3). Lo que no sea número se ignora."""
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:4]) or (0,)


def mas_nueva(candidata: str, instalada: str) -> bool:
    """Si `candidata` es posterior a `instalada`, comparando por número.

    Como texto, «0.9.0» sale después de «0.15.3». Aquí no.
    """
    a, b = _partes(candidata), _partes(instalada)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def leer_estado(d) -> dict:
    """Saca lo que interesa del `<app>.json` publicado.

    **El formato es el que ya escribe draw101 en el repo**, comprobado
    clonándolo, no supuesto:

        { "nest101": { "version": "…", "fecha": "…",
                       "notas": ["…", "…"],
                       "pagina": "…",
                       "windows": { "archivo": "…", "bytes": 0,
                                    "sha256": "…", "url": "…",
                                    "ultima": "…" } } }

    Toda la familia comparte un repo, y por eso el bloque va **colgado del
    nombre de la app**: `avisos.json` es común y los `.json` son uno por
    programa, pero con la misma forma. Inventar aquí un formato plano habría
    metido dos contratos distintos en el mismo repo, y el segundo se rompe el
    día que alguien toca el primero.

    Se acepta también la forma plana por si un archivo viejo la trae: cuesta
    tres líneas y evita que una publicación a medias deje la app muda.
    """
    out = {}
    if not isinstance(d, dict):
        return out
    bloque = d.get(APP) if isinstance(d.get(APP), dict) else d
    win = bloque.get("windows") if isinstance(bloque.get("windows"), dict) else bloque

    out["version"] = str(bloque.get("version", "") or "")
    out["fecha"] = str(bloque.get("fecha", "") or "")
    # Las notas vienen como lista de renglones: se juntan para enseñarlas.
    n = bloque.get("notas", "")
    out["notas"] = "\n".join(str(x) for x in n) if isinstance(n, list) else str(n or "")

    out["sha256"] = str(win.get("sha256", "") or "")
    out["bytes"] = int(win.get("bytes") or 0)
    # El enlace del archivo viene con su versión adentro. Si faltara, queda la
    # página fija, que siempre existe y nunca lleva a un 404.
    out["url"] = str(win.get("url") or bloque.get("pagina") or URL_ULTIMA)
    # El enlace fijo, si el publicador lo escribió. Es el mismo archivo; cambia
    # sólo en que su nombre no lleva versión.
    out["url_fija"] = str(win.get("fijo") or URL_FIJA)
    return out


def revisar(instalada: str, forzar: bool = False) -> dict:
    """Pregunta si hay versión nueva. Nunca levanta una excepción.

    Devuelve siempre un diccionario con las mismas llaves, haya red o no: quien
    lo pinta no tiene que distinguir entre «no hay nueva» y «no se pudo».
    """
    ahora = time.time()
    if not forzar and _CACHE.get("cuando", 0) + _VIGENCIA > ahora:
        d = dict(_CACHE["dato"])
        d["hay"] = bool(d.get("version")) and mas_nueva(d["version"], instalada)
        d["instalada"] = instalada
        return d

    base = {"hay": False, "instalada": instalada, "version": "", "notas": "",
            "fecha": "", "bytes": 0, "sha256": "",
            "url": URL_ULTIMA, "url_fija": URL_FIJA,
            "url_todas": URL_TODAS, "error": ""}
    try:
        import urllib.request
        pet = urllib.request.Request(
            URL_ESTADO, headers={"User-Agent": f"{APP}/{instalada}",
                                 "Cache-Control": "no-cache"})
        with urllib.request.urlopen(pet, timeout=ESPERA) as r:
            d = json.loads(r.read().decode("utf-8"))
        base.update(leer_estado(d))
        _CACHE.update({"cuando": ahora, "dato": dict(base)})
    except Exception as e:                                       # noqa: BLE001
        # Sin red no hay error que enseñar: hay un taller trabajando sin red.
        base["error"] = f"{type(e).__name__}"
        return base

    base["hay"] = bool(base["version"]) and mas_nueva(base["version"], instalada)
    return base


# --------------------------------------------------------------- #092 política
#
# Mike: *«también una revisión de actualizaciones automáticas»* — como draw101,
# que revisa al arrancar y una vez al día.
#
# Las tres decisiones viven en el perfil del taller, no en el proyecto: son de
# la máquina, no de la cocina.
#
#   revisar_solo   apagar del todo la revisión. Un taller sin internet no tiene
#                  por qué esperar seis segundos cada arranque.
#   ignorada       «esta versión no me interesa». Deja de avisar de ESA, no de
#                  las siguientes — que es la diferencia entre posponer y
#                  quedarse mudo para siempre.
#   ultima_revismasion  cuándo se preguntó por última vez.
CADA = 24 * 60 * 60          # una vez al día es de sobra: no salen dos por día


def politica() -> dict:
    from .taller import leer
    d = leer()
    return {"revisar_solo": bool(d.get("revisar_actualizaciones", True)),
            # #093 — bajarla sola. De fábrica encendida: el caso normal es que
            # el taller quiera la última y no que quiera decidir 180 MB.
            "descargar_solo": bool(d.get("descargar_actualizaciones", True)),
            "ignorada": str(d.get("version_ignorada", "") or ""),
            "cuando": float(d.get("ultima_revision", 0) or 0)}


def guardar_politica(revisar=None, ignorada=None, cuando=None,
                     descargar=None) -> dict:
    from .taller import leer, guardar
    d = leer()
    if revisar is not None:
        d["revisar_actualizaciones"] = bool(revisar)
    if descargar is not None:
        d["descargar_actualizaciones"] = bool(descargar)
    if ignorada is not None:
        d["version_ignorada"] = str(ignorada or "")
    if cuando is not None:
        d["ultima_revision"] = float(cuando)
    try:
        guardar(d)
    except OSError:
        pass                 # sin permiso de escritura se sigue trabajando
    return politica()


def toca_revisar() -> bool:
    """Si corresponde preguntar ahora: apagada no, y no más de una vez al día."""
    p = politica()
    return p["revisar_solo"] and (time.time() - p["cuando"]) > CADA


def revisar_si_toca(instalada: str) -> dict:
    """La revisión del arranque. Respeta el interruptor y la versión ignorada."""
    p = politica()
    if not p["revisar_solo"]:
        return {"hay": False, "instalada": instalada, "version": "",
                "notas": "", "fecha": "", "bytes": 0, "sha256": "",
                "url": URL_ULTIMA, "url_fija": URL_FIJA, "url_todas": URL_TODAS,
                "error": "", "apagada": True}
    if not toca_revisar() and _CACHE.get("dato"):
        r = dict(_CACHE["dato"])
        r["instalada"] = instalada
        r["hay"] = bool(r.get("version")) and mas_nueva(r["version"], instalada)
    else:
        r = revisar(instalada)
        if not r["error"]:
            guardar_politica(cuando=time.time())
    r["apagada"] = False
    # Una versión ignorada deja de avisar, pero se sigue viendo en Ayuda: la
    # diferencia entre «ahora no» y «nunca más» la pone el usuario, no la app.
    r["ignorada"] = bool(p["ignorada"] and p["ignorada"] == r.get("version"))
    if r["ignorada"]:
        r["hay"] = False
    # #093 — si hay versión nueva y el taller lo tiene encendido, se empieza a
    # bajar aquí mismo, en segundo plano. La revisión no espera a la descarga:
    # contesta igual de rápido con o sin red.
    if r["hay"] and p["descargar_solo"]:
        arrancar_descarga(r)
    r["descargar_solo"] = p["descargar_solo"]
    r["descarga"] = estado_descarga()
    return r


# --------------------------------------------------------------- #092 descarga
def descargar(url: str, sha256: str, destino: str, avisar=None) -> str:
    """Baja el instalador y **comprueba su huella antes de darlo por bueno**.

    Un instalador que se bajó a medias arranca y falla raro, y eso cuesta una
    tarde de diagnóstico. Si la huella no cuadra, el archivo se borra: más vale
    no tener nada que tener algo roto con cara de bueno.
    """
    import hashlib
    import urllib.request
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    parcial = destino + ".parcial"
    h = hashlib.sha256()
    leidos = 0
    pet = urllib.request.Request(url, headers={"User-Agent": f"{APP}"})
    with urllib.request.urlopen(pet, timeout=60) as r, open(parcial, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        while True:
            trozo = r.read(1024 * 256)
            if not trozo:
                break
            f.write(trozo)
            h.update(trozo)
            leidos += len(trozo)
            if avisar:
                avisar(leidos, total)
    if sha256 and h.hexdigest() != sha256:
        os.remove(parcial)
        raise ValueError("el archivo bajado no cuadra con su huella; "
                         "se borró en vez de dejarlo a medias")
    os.replace(parcial, destino)
    return destino


# --------------------------------------------------------- #093 bajarla sola
#
# Mike: *«ya hay que implementarle que solita revise si hay actualizaciones y
# que si hay, las descargue»*.
#
# La revisión sola ya existía (#092). Lo que faltaba es el segundo paso: que en
# cuanto encuentre una, se la traiga, **sin dejar de contestar mientras**.
#
# Tres cosas que no cambian, porque cambiarlas sería otra app:
#
# **Bajar no es instalar.** El instalador queda en disco y la app lo dice; correrlo
# lo sigue decidiendo la persona. Un instalador que arranca solo a media
# exportación se lleva por delante el trabajo de la tarde.
#
# **La descarga vive en un hilo aparte.** Si ocupara el hilo del servidor, la
# ventana se quedaría tiesa los 180 MB. El hilo es `daemon`: cerrar la app no
# espera a que termine de bajar.
#
# **Un fallo no se reintenta en bucle.** Se anota el error y ahí se queda hasta
# la próxima revisión —o hasta que la persona pulse bajar—. Un taller con red
# intermitente no necesita que su programa la muela a peticiones.
_BAJADA = {"estado": "ocioso",     # ocioso · bajando · lista · error
           "version": "", "archivo": "", "leidos": 0, "total": 0,
           "porcentaje": 0, "error": ""}
_CANDADO = threading.Lock()


def estado_descarga() -> dict:
    """Cómo va la descarga. Se puede preguntar cuantas veces se quiera."""
    with _CANDADO:
        return dict(_BAJADA)


def _anotar(**kw) -> None:
    with _CANDADO:
        _BAJADA.update(kw)


def destino_de(version: str) -> str:
    """Dónde queda el instalador de una versión.

    En la carpeta del taller, no en Temp: si algo sale mal, el archivo sigue
    ahí y se puede instalar a mano sin volver a bajar 180 MB. Es además la
    única carpeta desde la que el escritorio acepta ejecutar un instalador.
    """
    from .taller import carpeta
    return os.path.join(str(carpeta()), "descargas",
                        f"{APP}-{version}-setup.exe")


def ya_bajada(r: dict) -> str:
    """La ruta del instalador si ya está completo en disco; si no, cadena vacía.

    Se compara el tamaño con el que declara el `.json`. La huella no se vuelve
    a calcular: ya se comprobó al bajarlo, y rehacer el sha256 de 180 MB en
    cada arranque cuesta segundos y no dice nada nuevo.
    """
    ver = str(r.get("version") or "")
    if not ver:
        return ""
    d = destino_de(ver)
    try:
        if os.path.isfile(d) and (not r.get("bytes")
                                  or os.path.getsize(d) == int(r["bytes"])):
            return d
    except OSError:
        pass
    return ""


def arrancar_descarga(r: dict, forzar: bool = False) -> dict:
    """Empieza a bajar el instalador en segundo plano. Devuelve el estado.

    Es idempotente a propósito: la interfaz pregunta cada pocos segundos y el
    arranque también llama aquí, así que llamar de más tiene que ser gratis.
    No se empieza dos veces, no se vuelve a bajar lo que ya está, y un error
    anterior no se reintenta solo (`forzar` es lo que la persona pulsa).
    """
    ver = str(r.get("version") or "")
    if not ver:
        return estado_descarga()

    hecho = ya_bajada(r)
    if hecho:
        _anotar(estado="lista", version=ver, archivo=hecho, error="",
                leidos=int(r.get("bytes") or 0), total=int(r.get("bytes") or 0),
                porcentaje=100)
        return estado_descarga()

    with _CANDADO:
        misma = _BAJADA["version"] == ver
        if _BAJADA["estado"] == "bajando":
            return dict(_BAJADA)
        if _BAJADA["estado"] == "error" and misma and not forzar:
            return dict(_BAJADA)
        _BAJADA.update({"estado": "bajando", "version": ver, "archivo": "",
                        "leidos": 0, "total": int(r.get("bytes") or 0),
                        "porcentaje": 0, "error": ""})

    destino = destino_de(ver)
    url = str(r.get("url") or URL_FIJA)
    sha = str(r.get("sha256") or "")

    def avisar(leidos: int, total: int) -> None:
        t = total or int(r.get("bytes") or 0)
        _anotar(leidos=leidos, total=t,
                porcentaje=int(leidos * 100 / t) if t else 0)

    def trabajo() -> None:
        try:
            descargar(url, sha, destino, avisar=avisar)
        except ValueError as e:            # la huella no cuadró; ya se borró
            _anotar(estado="error", error=str(e))
        except Exception as e:                                   # noqa: BLE001
            _anotar(estado="error", error=f"no se pudo bajar ({type(e).__name__})")
        else:
            _anotar(estado="lista", archivo=destino, porcentaje=100, error="")

    threading.Thread(target=trabajo, name="bajar-actualizacion",
                     daemon=True).start()
    return estado_descarga()
