"""#086 — La librería de módulos: categorías de gabinetes ya resueltos.

Mike: *«haz el módulo de la librería de módulos. Aunque ahorita haya uno de
ejemplo nada más, tú lo vas a organizar en carpetas en los archivos del
software, pero visualmente debe tener una nueva categoría y ya los módulos.
Ej. Gabinetes para IKEDA, y es una categoría con varios gabinetes ya de tamaños
predeterminados para aceptar diferentes componentes de IKEDA como entrepaños,
cajones, charolas, etc. Ya con los barrenos y todo.»*

Y sobre las medidas de IKEDA: *«yo los voy a hacer, esos no van incluidos, pero
era un ejemplo de la categoría. Ahorita solo pon uno de ejemplo para que se vea
dónde se agregan nuevos módulos o librerías.»*

Así que aquí no hay medidas inventadas de ninguna marca. Hay **una categoría de
ejemplo hecha con las medidas del taller**, que sí son reales, y el lugar
señalado donde se agregan las demás.

---

## Cómo está organizado

Un módulo es **un archivo JSON con un gabinete adentro**. Una categoría es
**una carpeta con módulos**. Nada de base de datos: se copia una carpeta y se
copió la librería completa.

    assets/modulos/<categoria>/                de fábrica, viaja con la app
        categoria.json                         nombre, descripción, orden
        <modulo>.json                          un gabinete

    ~/Taller 101/modulos/<categoria>/          las del taller
        categoria.json
        <modulo>.json

**Las dos se leen juntas y las del taller mandan.** Si el taller crea un módulo
con el mismo archivo que uno de fábrica, gana el suyo — así puede corregir un
módulo de fábrica sin que la siguiente actualización se lo deshaga, porque las
actualizaciones sólo reescriben la carpeta de instalación.

Y por eso mismo lo que el taller guarda va **siempre** del lado del taller:
escribir en la carpeta de instalación sería escribir en un lugar que la próxima
versión borra.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import List, Optional

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FABRICA = os.path.join(RAIZ, "assets", "modulos")
CATEGORIA = "categoria.json"


def carpeta_taller() -> str:
    from .taller import carpeta
    return os.path.join(str(carpeta()), "modulos")


def slug(t: str) -> str:
    """Un nombre de carpeta que sobreviva a Windows, a macOS y a un zip."""
    t = (t or "").strip().lower()
    t = (t.replace("á", "a").replace("é", "e").replace("í", "i")
          .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:48] or "sin-nombre"


def _leer(ruta: str) -> Optional[dict]:
    try:
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        # Un archivo roto se salta y ya. Una librería con un JSON mal escrito
        # tiene que seguir abriendo con los demás módulos, no dejar al taller
        # sin librería por una coma de más.
        return None


def _categorias_de(base: str, propia: bool) -> List[dict]:
    if not os.path.isdir(base):
        return []
    out = []
    for nombre in sorted(os.listdir(base)):
        carp = os.path.join(base, nombre)
        if not os.path.isdir(carp):
            continue
        meta = _leer(os.path.join(carp, CATEGORIA)) or {}
        modulos = []
        for arch in sorted(os.listdir(carp)):
            if arch == CATEGORIA or not arch.endswith(".json"):
                continue
            m = _leer(os.path.join(carp, arch))
            if not m or not isinstance(m.get("gabinete"), dict):
                continue
            g = m["gabinete"]
            modulos.append({
                "id": f"{nombre}/{arch[:-5]}",
                "archivo": arch[:-5],
                "nombre": m.get("nombre") or arch[:-5],
                "nota": m.get("nota", ""),
                "propia": propia,
                "gabinete": g,
            })
        out.append({
            "id": nombre,
            "nombre": meta.get("nombre") or nombre.replace("-", " ").title(),
            "nota": meta.get("nota", ""),
            "orden": int(meta.get("orden", 100)),
            "propia": propia,
            "modulos": modulos,
        })
    return out


def categorias() -> List[dict]:
    """Las de fábrica y las del taller, mezcladas. Las del taller mandan."""
    por_id = {c["id"]: c for c in _categorias_de(FABRICA, False)}
    for c in _categorias_de(carpeta_taller(), True):
        vieja = por_id.get(c["id"])
        if not vieja:
            por_id[c["id"]] = c
            continue
        # misma categoría en los dos lados: se juntan los módulos y el del
        # taller pisa al de fábrica cuando comparten archivo
        mios = {m["archivo"] for m in c["modulos"]}
        c["modulos"] += [m for m in vieja["modulos"] if m["archivo"] not in mios]
        c["nombre"] = c["nombre"] or vieja["nombre"]
        c["nota"] = c["nota"] or vieja["nota"]
        c["orden"] = vieja["orden"]
        por_id[c["id"]] = c
    return sorted(por_id.values(), key=lambda c: (c["orden"], c["nombre"].lower()))


def modulo(mid: str) -> Optional[dict]:
    cat, _, arch = (mid or "").partition("/")
    for c in categorias():
        if c["id"] != cat:
            continue
        for m in c["modulos"]:
            if m["archivo"] == arch:
                return m
    return None


def guardar(categoria: str, nombre: str, gabinete: dict, nota: str = "") -> dict:
    """Guarda un módulo del lado del taller, creando la categoría si hace falta.

    Siempre del lado del taller, nunca en `assets/`: la carpeta de instalación
    la reescribe cada actualización.
    """
    cid = slug(categoria)
    carp = os.path.join(carpeta_taller(), cid)
    os.makedirs(carp, exist_ok=True)
    ruta_cat = os.path.join(carp, CATEGORIA)
    if not os.path.isfile(ruta_cat):
        _escribir(ruta_cat, {"nombre": (categoria or cid).strip()[:60],
                             "nota": "", "orden": 200})
    arch = slug(nombre)
    destino = os.path.join(carp, arch + ".json")
    # Dos módulos con el mismo nombre no se pisan: el segundo lleva sufijo.
    n = 1
    while os.path.isfile(destino):
        n += 1
        arch = f"{slug(nombre)}-{n}"
        destino = os.path.join(carp, arch + ".json")
    _escribir(destino, {"nombre": (nombre or arch).strip()[:60], "nota": nota,
                        "cuando": time.time(), "gabinete": gabinete})
    return {"id": f"{cid}/{arch}", "categoria": cid, "archivo": arch}


def borrar(mid: str) -> bool:
    """Sólo se borra lo del taller. Lo de fábrica no se toca: viene en la app."""
    cat, _, arch = (mid or "").partition("/")
    if not cat or not arch or "/" in arch or ".." in mid:
        return False
    ruta = os.path.join(carpeta_taller(), slug(cat), slug(arch) + ".json")
    if not os.path.isfile(ruta):
        return False
    os.remove(ruta)
    carp = os.path.dirname(ruta)
    # Categoría que se queda sin módulos: se lleva su categoria.json y se va.
    # Una categoría vacía en pantalla es una fila que no hace nada.
    if not [f for f in os.listdir(carp) if f.endswith(".json") and f != CATEGORIA]:
        for f in os.listdir(carp):
            os.remove(os.path.join(carp, f))
        os.rmdir(carp)
    return True


def _escribir(ruta: str, datos: dict) -> None:
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)          # nunca dejar el archivo a medias
