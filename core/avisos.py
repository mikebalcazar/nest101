"""#091 — Avisos de Taller 101 dentro del programa.

Mike: *«copia las funciones pertinentes para nest101 del menú de ayuda de
draw101»*. Una de ellas son los avisos: noticias que se publican una vez y
llegan a todos los talleres que tengan el programa abierto.

## El formato es el del repo, leído de ahí

`avisos.json` es **común a toda la familia** y vive junto a los `.json` de cada
programa. Se clonó el repo y se copió su forma exacta en vez de deducirla:

    { "avisos": [
        { "id": "2026-09-07-actualizador",
          "fecha": "2026-09-07",
          "nivel": "info",                   info · importante
          "titulo": "…", "texto": "…",
          "desde": "0.19.2",                 versión mínima que lo debe ver
          "caduca": "2026-12-31",
          "en": { "titulo": "…", "texto": "…" },
          "app": "draw101" } ] }

Cuatro cosas se filtran aquí, y cada una tiene su motivo:

- **`app`** — un repo, varios programas. Un aviso de draw101 no tiene nada que
  hacer en nest101.
- **`desde`** — un aviso que explica algo de la 0.16 no le sirve a quien tiene
  la 0.15: le habla de un botón que no existe en su pantalla.
- **`caduca`** — «ya se actualiza solo» deja de ser noticia en tres meses.
- **`en`** — cada aviso trae su traducción. Se escoge con el idioma del taller,
  el mismo de `core/idioma.py`. Un taller en inglés no debería recibir avisos
  en español.

## Lo leído no se repite

Los ids leídos se guardan en el perfil del taller. Es lo único que se guarda:
el aviso en sí no se copia a disco, así que si se corrige un texto publicado,
al taller le llega el corregido.

Los de nivel **`importante`** salen solos al arrancar, una vez. Los demás
esperan a que alguien abra el menú. Un aviso que interrumpe cada arranque deja
de leerse a la tercera.
"""
from __future__ import annotations

import json
import time
from typing import List

from .actualizar import USUARIO, REPO, APP, ESPERA

URL = f"https://raw.githubusercontent.com/{USUARIO}/{REPO}/main/avisos.json"

_CACHE: dict = {}
_VIGENCIA = 30 * 60


def _hoy() -> str:
    return time.strftime("%Y-%m-%d")


def _mio(a: dict, version: str) -> bool:
    """Si este aviso es para este programa, esta versión y esta fecha."""
    from .actualizar import mas_nueva
    if str(a.get("app") or APP) != APP:
        return False
    caduca = str(a.get("caduca") or "")
    if caduca and caduca < _hoy():
        return False
    desde = str(a.get("desde") or "")
    # `desde` es la versión MÍNIMA: se ve si la instalada es esa o posterior.
    if desde and mas_nueva(desde, version):
        return False
    return bool(a.get("titulo") or a.get("texto"))


def _traducir(a: dict) -> dict:
    """El aviso en el idioma del taller. Cada uno trae su propia traducción."""
    from .idioma import activo
    cod = activo()
    tr = a.get(cod) if isinstance(a.get(cod), dict) else {}
    return {
        "id": str(a.get("id") or ""),
        "fecha": str(a.get("fecha") or ""),
        "nivel": str(a.get("nivel") or "info"),
        "titulo": str(tr.get("titulo") or a.get("titulo") or ""),
        "texto": str(tr.get("texto") or a.get("texto") or ""),
    }


def leidos() -> List[str]:
    from .taller import leer
    v = leer().get("avisos_leidos")
    return [str(x) for x in v] if isinstance(v, list) else []


def marcar_leidos(ids) -> List[str]:
    from .taller import leer, guardar
    d = leer()
    ya = set(leidos())
    ya.update(str(x) for x in (ids or []))
    # Se recortan: son ids de texto y no hacen falta los de hace dos años.
    d["avisos_leidos"] = sorted(ya)[-200:]
    try:
        guardar(d)
    except OSError:
        pass
    return d["avisos_leidos"]


def bajar(forzar: bool = False) -> List[dict]:
    """Trae la lista publicada. Sin red devuelve vacío, nunca una excepción."""
    ahora = time.time()
    if not forzar and _CACHE.get("cuando", 0) + _VIGENCIA > ahora:
        return list(_CACHE.get("lista", []))
    try:
        import urllib.request
        pet = urllib.request.Request(
            URL, headers={"User-Agent": APP, "Cache-Control": "no-cache"})
        with urllib.request.urlopen(pet, timeout=ESPERA) as r:
            d = json.loads(r.read().decode("utf-8"))
        lista = d.get("avisos") if isinstance(d, dict) else d
        lista = [a for a in lista if isinstance(a, dict)] if isinstance(lista, list) else []
        _CACHE.update({"cuando": ahora, "lista": lista})
        return list(lista)
    except Exception:                                            # noqa: BLE001
        # Sin internet no hay avisos, y no pasa nada: no son parte del trabajo.
        return list(_CACHE.get("lista", []))


def para_mi(version: str, forzar: bool = False) -> dict:
    """Los avisos que le tocan a este taller, con cuáles están sin leer."""
    vistos = set(leidos())
    lista = [_traducir(a) for a in bajar(forzar) if _mio(a, version)]
    lista.sort(key=lambda a: a["fecha"], reverse=True)
    for a in lista:
        a["leido"] = a["id"] in vistos
    sin_leer = [a for a in lista if not a["leido"]]
    return {
        "avisos": lista,
        "sin_leer": len(sin_leer),
        # Los importantes sin leer son los que salen solos al arrancar.
        "asoman": [a["id"] for a in sin_leer if a["nivel"] == "importante"],
    }
