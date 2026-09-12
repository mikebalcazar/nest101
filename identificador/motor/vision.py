"""Capa de vision: manda la imagen del alzado a Claude y regresa JSON estructurado.

Dos backends:
  - `anthropic`  -> API real (necesita ANTHROPIC_API_KEY)
  - `offline`    -> lee un JSON ya extraido de disco (para pruebas / demo sin key)
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

from .schema import json_schema_para_vision

from ..aprendizaje import (MODELO_DEFAULT, carpeta as _carpeta_perfiles,   # noqa: F401
                           como_prompt as _perfil_a_texto,
                           guardar as guardar_aprendizaje,
                           perfil_guardado)
def _raiz() -> Path:
    """Busca hacia arriba la carpeta que tiene prompts/extract.md.

    Asi el motor funciona igual en el repo (src/identificador/) que dentro de
    Taller 101 (app_py/identificador/motor/), sin tocar rutas a mano.
    """
    aqui = Path(__file__).resolve()
    for base in aqui.parents:
        if (base / "prompts" / "extract.md").exists():
            return base
    return aqui.parents[2]


RAIZ = _raiz()
PROMPT = RAIZ / "prompts" / "extract.md"
SIMBOLOGIA = RAIZ / "prompts" / "simbologia.md"
PERFILES = _carpeta_perfiles()

TOOL = {
    "name": "reportar_alzados",
    "description": "Reporta los alzados, modulos, cotas y anotaciones leidos del plano.",
    "input_schema": json_schema_para_vision(),
}


def _prompt_texto(despacho: Optional[str] = None,
                  perfil: Optional[dict] = None) -> str:
    """Prompt base + catalogo de simbologia + lo aprendido del despacho.

    `perfil` es para cuando la lectura corre en el SERVICIO: ahi no hay archivos
    del taller, asi que el escritorio manda lo aprendido junto con el plano. El
    servicio no guarda nada de nadie.
    """
    texto = PROMPT.read_text(encoding="utf-8").replace(
        "{SIMBOLOGIA}", SIMBOLOGIA.read_text(encoding="utf-8"))
    if perfil:
        texto += "\n\n" + _perfil_a_texto(perfil)
    elif despacho:
        texto += "\n\n" + perfil_como_prompt(despacho)
    return texto


def perfil_como_prompt(despacho: str) -> str:
    """Correcciones que el usuario ya hizo en planos de este despacho.
    Los despachos son consistentes: lo aprendido en una lamina sirve en las demas."""
    import json as _json
    p = PERFILES / f"{despacho}.json"
    if not p.exists():
        return ""
    perfil = _json.loads(p.read_text(encoding="utf-8"))
    ejemplos = perfil.get("correcciones", [])[-20:]
    if not ejemplos:
        return ""
    out = [f"## Aprendido de planos de {perfil.get('nombre', despacho)}",
           "El usuario ya corrigio estas lecturas. Respeta el criterio:"]
    for e in ejemplos:
        out.append(f"- {e.get('contexto', '')} -> {e.get('correccion', '')}")
    return "\n".join(out)


def _b64(png: Path) -> str:
    return base64.standard_b64encode(png.read_bytes()).decode()


class VisionError(RuntimeError):
    pass


def extraer_anthropic(png: Path, modelo: str = MODELO_DEFAULT,
                      contexto: Optional[str] = None, max_tokens: int = 32000,
                      despacho: Optional[str] = None,
                      imagenes_extra: Optional[list] = None,
                      perfil: Optional[dict] = None) -> dict:
    """`imagenes_extra` son imagenes de apoyo: en una FOTO se manda tambien la hoja
    completa, porque las notas (material, espesor) viven fuera del recorte y el
    OCR clasico no las lee bien."""
    import anthropic

    client = anthropic.Anthropic()
    contenido = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": _b64(png)}},
    ]
    for extra in (imagenes_extra or []):
        contenido.append({"type": "text",
                          "text": "Imagen de apoyo (hoja completa): usala solo para leer "
                                  "notas, leyendas y otras vistas del mismo mueble."})
        contenido.append({"type": "image",
                          "source": {"type": "base64", "media_type": "image/png",
                                     "data": _b64(Path(extra))}})
    contenido.append({"type": "text", "text": contexto or "Extrae los alzados de esta imagen."})
    # #053 — Se lee en STREAMING, no de un jalón.
    #
    # El SDK se niega a hacer una petición normal cuando `max_tokens` es lo
    # bastante grande como para que la respuesta pudiera tardar más de diez
    # minutos: «Streaming is required for operations that may take longer than
    # 10 minutes». Subir el tope a 32k para que cupiera un plano cargado (#052)
    # disparó justo ese guardia.
    #
    # En streaming la conexión va recibiendo la respuesta conforme se genera, así
    # que no hay una espera larga en silencio que pueda vencer. El resultado es
    # el mismo mensaje completo; sólo cambia cómo viaja.
    #
    # #055 — y NO se confía sólo en `blk.input`. En streaming el SDK va juntando
    # el JSON de la herramienta por pedazos y lo interpreta al final; si eso
    # falla, entrega un diccionario vacío y el programa dice tan campante «no
    # reconocí ningún mueble». Un cero silencioso es peor que un error: manda a
    # buscar el problema al plano, que estaba bien. Así que se guardan también
    # los pedazos crudos y, si lo interpretado viene vacío, se arman aquí.
    pedazos: list = []
    with client.messages.stream(
        model=modelo,
        max_tokens=max_tokens,
        system=_prompt_texto(despacho, perfil),
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "reportar_alzados"},
        messages=[{"role": "user", "content": contenido}],
        timeout=900.0,
    ) as flujo:
        for ev in flujo:
            d = getattr(ev, "delta", None)
            trozo = getattr(d, "partial_json", None)
            if trozo:
                pedazos.append(trozo)
        resp = flujo.get_final_message()
    # #052 — Una respuesta CORTADA no se puede usar, y hay que decirlo.
    #
    # Con `max_tokens` corto, el modelo se queda a media lista de modulos. La
    # respuesta no llega vacia: llega el JSON a medias, y el SDK lo entrega como
    # puede — con el ultimo elemento partido, que suele acabar siendo una cadena
    # suelta dentro de `alzados`. Aguas abajo eso reventaba con
    # «'str' object is not a mapping», que no le dice nada a nadie.
    #
    # Le paso a Mike en la primera lectura de verdad, con `CAR-06`: una
    # despensa con muchos modulos y 8000 tokens de tope.
    if getattr(resp, "stop_reason", None) == "max_tokens":
        raise VisionError(
            "El plano trae más módulos de los que caben en una respuesta. "
            "Prueba con una vista a la vez, o recorta la lámina a un mueble.")
    crudo = None
    for blk in resp.content:
        if blk.type == "tool_use" and blk.name == "reportar_alzados":
            crudo = blk.input
            break
    if not (isinstance(crudo, dict) and crudo.get("alzados")) and pedazos:
        # el SDK no lo pudo armar: se intenta con los pedazos tal como llegaron
        try:
            rearmado = json.loads("".join(pedazos))
            if isinstance(rearmado, dict) and rearmado.get("alzados"):
                crudo = rearmado
        except Exception:                                       # noqa: BLE001
            pass
    if crudo is None:
        raise VisionError("El modelo no regreso tool_use")
    limpio = _limpiar(crudo)
    # se guarda lo que contesto, para poder diagnosticar sin volver a pagar
    limpio["_crudo"] = "".join(pedazos)[:200000]
    return limpio


def _desenvolver(crudo):
    """#056 — El modelo a veces entrega el JSON METIDO EN UNA CADENA.

    En vez de:

        {"alzados": [ {...}, {...} ]}

    contesta:

        {"alzados": "{\\"alzados\\": [ {...}, {...} ]}"}

    o sea, el reporte entero serializado como texto dentro del campo que
    esperaba una lista. Pasa cuando la respuesta es larga, y no es raro.

    Esto es lo que estuvo rompiendo la lectura del plano de Mike desde el
    principio, con tres caras distintas:

      · 0.9.4 — `'str' object is not a mapping`: recorrer la cadena entrega
        letras sueltas, y `Alzado(**"{")` truena.
      · 0.9.6 — «no reconocí ningún mueble»: el filtro de `_limpiar` tiraba las
        letras por no ser diccionarios y dejaba la lista vacia. Un cero en
        silencio, que es peor que el error, porque manda a buscar el problema al
        plano.

    El diagnostico de #055 lo destapo: el archivo crudo traia 7 KB de modulos
    bien leidos y la respuesta interpretada pesaba 20 bytes.

    Se abre la cadena hasta un par de niveles. Si no se puede, se devuelve tal
    cual y el filtro de abajo hace su trabajo.
    """
    for _ in range(3):
        if isinstance(crudo, (str, bytes)):
            try:
                crudo = json.loads(crudo)
                continue
            except Exception:                                   # noqa: BLE001
                return crudo
        if isinstance(crudo, dict) and isinstance(crudo.get("alzados"), (str, bytes)):
            try:
                dentro = json.loads(crudo["alzados"])
            except Exception:                                   # noqa: BLE001
                return crudo
            if isinstance(dentro, dict) and "alzados" in dentro:
                # el reporte completo venia envuelto: se usa el de adentro
                crudo = {**{k: v for k, v in crudo.items() if k != "alzados"},
                         **dentro}
            else:
                crudo = {**crudo, "alzados": dentro}
            continue
        break
    return crudo


def _limpiar(crudo) -> dict:
    """Deja solo lo que tiene la forma esperada.

    El modelo cumple el esquema casi siempre, pero «casi» no basta cuando lo que
    sigue es `Alzado(**a)`: un elemento que no sea diccionario tumba la lectura
    entera y se pierden los alzados que si venian bien. Se tira lo que no sirve
    y se sigue con lo demas.
    """
    crudo = _desenvolver(crudo)
    if not isinstance(crudo, dict):
        raise VisionError("El modelo contestó algo que no se pudo interpretar.")
    alzados = [a for a in (crudo.get("alzados") or []) if isinstance(a, dict)]
    for a in alzados:
        a["modulos"] = [m for m in (a.get("modulos") or []) if isinstance(m, dict)]
    return {**crudo, "alzados": alzados}


DEMO = RAIZ / "samples" / "demo"


def extraer_offline(png: Path, json_path: Optional[Path] = None) -> dict:
    """Backend de prueba: busca el JSON junto a la imagen, o en samples/demo/,
    o el que se le pase. Sirve para correr el pipeline completo sin gastar API."""
    p = Path(json_path) if json_path else png.with_suffix(".vision.json")
    if not p.exists():
        alterno = DEMO / (png.stem + ".vision.json")
        if alterno.exists():
            p = alterno
    if not p.exists():
        raise VisionError(
            f"Backend offline: falta {p}. Corre con --backend anthropic o genera ese JSON."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def extraer(png: Path, backend: str = "anthropic", **kw) -> dict:
    if backend == "offline":
        return _limpiar(extraer_offline(png, kw.get("json_path")))
    return extraer_anthropic(png, modelo=kw.get("modelo", MODELO_DEFAULT),
                             contexto=kw.get("contexto"), despacho=kw.get("despacho"),
                             imagenes_extra=kw.get("imagenes_extra"),
                             perfil=kw.get("perfil"))
