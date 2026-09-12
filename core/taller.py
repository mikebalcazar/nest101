"""#037 — La base de materiales del taller.

Los materiales no son de un proyecto: son del taller. Un tablero de melamina
blanca de 18 mm cuesta lo que cuesta, y si sube de precio sube para todos los
trabajos, no para el que se abra después. Hasta la 0.7.0 cada archivo `.t101x`
se llevaba su propia copia del catálogo, y cambiar un precio significaba abrir
cada mueble y cambiarlo otra vez — con la certeza de que alguno se quedaba viejo.

Así que el catálogo y el estándar constructivo viven en un solo archivo del
equipo, junto a los modelos guardados (#026) y a lo aprendido de cada despacho
(#031):

    ~/Taller 101/perfil.json

Los archivos `.t101x` **siguen guardando su catálogo**, y eso es a propósito:
un mueble que se manda por correo tiene que abrirse completo en otra máquina,
aunque ese taller no tenga los mismos materiales. Al abrirlo, lo que traiga y no
esté en la base se **agrega a la base** — que es justo lo que pidió Mike: si un
proyecto necesita un material nuevo, el material queda para todo el taller.

Qué NO hace: no borra ni cambia lo que ya existe. Abrir un archivo ajeno no
puede pisarte los precios. Si viene un material con el mismo nombre y distinto
precio, gana el tuyo, porque el tuyo es el que vas a pagar.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple

from .config import CATALOGO_DEFAULT, Estandar, Material

# Lo que identifica a un material. El nombre es lo que el carpintero dice en voz
# alta («la melamina blanca de 18»), así que es lo que decide si dos son el mismo.
CLAVE = "nombre"


def carpeta() -> Path:
    return Path(os.environ.get("T101_PERFIL_DIR")
                or (Path.home() / "Taller 101"))


def ruta() -> Path:
    return carpeta() / "perfil.json"


def _de_fabrica() -> dict:
    return {
        "catalogo": [asdict(m) for m in CATALOGO_DEFAULT],
        "estandar": asdict(Estandar()),
        # #085 — El idioma es del TALLER, no de la cocina: quien está frente a
        # la máquina es siempre el mismo. De fábrica, **inglés**: nest101 se
        # instala fuera de México y el que sí habla español lo cambia una vez.
        "idioma": "en",
    }


def _completar_estandar(guardado: Optional[dict]) -> dict:
    """#069 — el estándar guardado, montado encima del de fábrica.

    El perfil del taller se escribió con la versión que estaba instalada ese
    día. Cada versión agrega parámetros —el respaldo de travesaños, la holgura
    del uñero, el material del manguete— y el archivo viejo no los trae. Hasta
    la 0.10.2 se devolvía tal cual: los parámetros nuevos llegaban en blanco a
    la interfaz, volvían al motor como `None`, y `None` es falso.

    O sea: actualizar la app le apagaba el respaldo completo a un taller que
    nunca tocó esa casilla, y el travesaño salía de 864×0 — medida imposible,
    con lo que el mueble entero dejaba de calcular. Un archivo viejo no puede
    apagar opciones que su versión ni siquiera conocía.

    Las llaves que ya no existen se quedan fuera: `Estandar(**d)` truena con
    una de sobra, y no vamos a tirar el perfil del taller por eso.
    """
    return asdict(Estandar.desde(guardado))


def leer() -> dict:
    """El perfil del taller. Si no existe, se crea con lo de fábrica."""
    p = ruta()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("catalogo"):
            d["estandar"] = _completar_estandar(d.get("estandar"))
            # #085 — un perfil escrito antes de que existiera el idioma no lo
            # trae. Se completa con el de fábrica por la misma razón de #069:
            # una llave que falta no puede llegar en blanco a la interfaz.
            d.setdefault("idioma", "en")
            return d
    except Exception:                                           # noqa: BLE001
        pass
    d = _de_fabrica()
    try:
        guardar(d)
    except OSError:
        pass            # sin permiso de escritura se sigue trabajando en memoria
    return d


def guardar(d: dict) -> Path:
    """Escritura atómica: el perfil del taller nunca queda a medias."""
    p = ruta()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return p


def catalogo() -> List[dict]:
    return leer()["catalogo"]


def estandar() -> dict:
    return leer()["estandar"]


def fundir(nuevos: Optional[List[dict]]) -> Tuple[dict, List[str]]:
    """Agrega a la base del taller los materiales que aún no tenga.

    Devuelve el perfil ya guardado y los nombres de los que entraron, para poder
    decírselo al usuario: un material que aparece solo en su lista de precios,
    sin avisar, es peor que uno que falta.
    """
    d = leer()
    tengo = {(m.get(CLAVE) or "").strip().lower() for m in d["catalogo"]}
    entraron = []
    for m in (nuevos or []):
        n = (m.get(CLAVE) or "").strip()
        if not n or n.lower() in tengo:
            continue          # lo que ya existe NO se pisa: gana el precio del taller
        d["catalogo"].append(copy.deepcopy(m))
        tengo.add(n.lower())
        entraron.append(n)
    if entraron:
        guardar(d)
    return d, entraron


def materiales() -> List[Material]:
    """El catálogo como objetos del motor."""
    out = []
    for m in catalogo():
        campos = {k: v for k, v in m.items() if k in Material.__dataclass_fields__}
        out.append(Material(**campos))
    return out


# ---------------------------------------------------------------- #040 la llave
#
# «Leer plano» viaja dentro de la app, pero la llave de API no puede: un
# instalador con la llave adentro es un instalador que la regala — cualquiera
# la saca del .exe y factura a la cuenta de quien la puso.
#
# Así que la llave se teclea una vez y se queda en el perfil del equipo, que es
# de este usuario y de esta máquina. Deliberadamente NO va a `perfil.json`: ese
# archivo se puede querer copiar de una computadora a otra para llevarse el
# catálogo, y la llave no debe viajar de acompañante.


def ruta_llave() -> Path:
    return carpeta() / "llave.txt"


def llave() -> str:
    """La llave guardada, o cadena vacía. El entorno manda, para poder probar."""
    de_fuera = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if de_fuera:
        return de_fuera
    try:
        return ruta_llave().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def guardar_llave(valor: str) -> bool:
    """Guarda o borra la llave. Devuelve si quedó alguna."""
    v = (valor or "").strip()
    p = ruta_llave()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not v:
        try:
            p.unlink()
        except OSError:
            pass
        return False
    tmp = p.with_suffix(".tmp")
    tmp.write_text(v, encoding="utf-8")
    os.replace(tmp, p)
    return True


def pista(v: str = "") -> str:
    """Los últimos caracteres, para que se vea CUÁL llave está puesta sin
    enseñarla entera. Una llave completa en pantalla es una llave en una captura."""
    v = v or llave()
    return ("…" + v[-4:]) if len(v) > 8 else ("puesta" if v else "")
