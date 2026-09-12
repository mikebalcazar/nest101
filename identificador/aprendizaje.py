"""#031 — Lo que el taller le va enseñando al lector de planos.

Vive aparte de `motor/vision.py` por una razón concreta: **esto sí viaja en el
instalador y aquello no**. La llamada al modelo de visión y sus librerías se
quedaron del lado del servicio; la memoria de las correcciones es del taller y
tiene que estar en la máquina del taller.

Cada vez que alguien corrige una lectura en el diálogo —«esto no es un cajón,
son dos puertas»— la corrección se guarda aquí, y viaja junto con el siguiente
plano de ese mismo despacho. El servicio no guarda nada de nadie: si mañana se
cambia de servidor, la memoria del taller se queda donde estaba.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# claude-sonnet-4-5 quedó retirado; con ese id la lectura falla en toda máquina.
MODELO_DEFAULT = os.environ.get("IDENTIFICADOR_MODELO", "claude-sonnet-5")

TOPE_CORRECCIONES = 200      # lo viejo deja de ayudar y sólo engorda el prompt
EN_EL_PROMPT = 20            # cuántas se le mandan al modelo


def carpeta() -> Path:
    """Con el perfil del equipo, junto a los modelos guardados de #026.

    Nunca dentro del programa: la app se instala en Program Files, que es de
    sólo lectura para el usuario. Escribir ahí es exactamente como fallaba el
    arranque antes de la 0.4.3.
    """
    crudo = os.environ.get("T101_PERFILES")
    if crudo:
        return Path(crudo)
    return Path.home() / "Taller 101" / "perfiles"


def perfil_guardado(despacho: str) -> Optional[dict]:
    """Lo aprendido de un despacho, para mandarlo con el próximo plano."""
    p = carpeta() / f"{despacho}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return None                     # un perfil roto no debe impedir leer


def como_prompt(perfil: Optional[dict]) -> str:
    """El perfil, escrito para que el modelo lo entienda."""
    if not perfil:
        return ""
    ejemplos = (perfil.get("correcciones") or [])[-EN_EL_PROMPT:]
    if not ejemplos:
        return ""
    out = [f"## Aprendido de planos de {perfil.get('nombre', 'este despacho')}",
           "El usuario ya corrigio estas lecturas. Respeta el criterio:"]
    for e in ejemplos:
        out.append(f"- {e.get('contexto', '')} -> {e.get('correccion', '')}")
    return "\n".join(out)


def guardar(despacho: str, preguntas, respuestas: dict) -> None:
    """Guarda las correcciones de esta lectura. Escritura atómica."""
    from .motor import ambiguedad

    nuevos = ambiguedad.para_perfil(preguntas, respuestas)
    if not nuevos:
        return
    base = carpeta()
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"{despacho}.json"
    perfil = perfil_guardado(despacho) or {"nombre": despacho, "correcciones": []}
    for n in nuevos:
        n["fecha"] = datetime.now(timezone.utc).isoformat()
    perfil["correcciones"] = (perfil.get("correcciones", []) + nuevos)[-TOPE_CORRECCIONES:]
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(perfil, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
