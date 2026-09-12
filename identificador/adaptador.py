"""Contrato `t101.gabinetes/1.0`  ->  Gabinete de Taller 101 (core/modelos.py).

Traduce lo que leyó IDENTIFICADOR al modelo que ya usa el DESPIEZADOR. No inventa
criterio de fabricación: eso lo pone el `Estandar` del proyecto (holguras, zoclo,
correderas, respaldo). Aquí sólo se acomodan medidas y frentes.

Equivalencias que hay que tener claras:

    IDENTIFICADOR                     Taller 101
    ─────────────────────────────     ─────────────────────────────────────
    familia base / torre              tipo "base"
    familia aereo                     tipo "aereo"
    medidas.alto (incluye zoclo)      alto            (también es el total)
    medidas.prof (con frente)         prof            (también lo incluye)
    2 puertas de 600                  Frente(tipo="puerta", n=2)   ← una hoja doble
    3 cajones                         3 Frente(tipo="cajon", alto=…)
    panel_ciego / registro            Frente(tipo="puerta", n=1)   ← misma pieza
    zoclo.alto_mm                     altura_zoclo + con_zoclo=True
    posicion.x                        pos_x
    posicion.z (aéreos)               alto_colgado
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Frentes que en el modelo de Taller 101 son "una puerta": misma pieza de tablero,
# lo que cambia es el herraje, y ese lo pone el Estandar.
COMO_PUERTA = {"puerta", "panel_ciego", "registro", "vidrio", "persiana"}
# #056 — Fondo de tabla cuando el plano no lo dice. Son los de Taller 101; el
# dia que el perfil del taller guarde los suyos, salen de ahi.
PROF_POR_TIPO = {"base": 600.0, "aereo": 350.0, "torre": 600.0}

FAMILIA_A_TIPO = {"base": "base", "torre": "base", "panel": "base", "aereo": "aereo"}


def _ordenar_arriba_abajo(frentes: List[dict]) -> List[dict]:
    """Taller 101 lista los frentes de arriba hacia abajo; el contrato los da con
    z_rel medido desde el piso del cuerpo."""
    def clave(f):
        z = (f.get("posicion_mm") or {}).get("z_rel")
        return -(z if z is not None else 0)
    return sorted(frentes, key=clave)


def _agrupar_frentes(frentes: List[dict]) -> Tuple[List[dict], List[str]]:
    """Puertas contiguas de la misma altura = una hoja doble (`n`). Cada cajón va solo."""
    avisos: List[str] = []
    salida: List[dict] = []
    for f in _ordenar_arriba_abajo(frentes):
        tipo = f.get("tipo")
        alto = (f.get("medidas_mm") or {}).get("alto")
        if tipo == "cajon":
            salida.append({"tipo": "cajon", "alto": alto, "n": 1})
            continue
        if tipo not in COMO_PUERTA:
            avisos.append(f"frente '{tipo}' no existe en Taller 101; entra como puerta")
        anterior = salida[-1] if salida else None
        if (anterior and anterior["tipo"] == "puerta"
                and anterior.get("alto") == alto and anterior["n"] < 2):
            anterior["n"] += 1              # el par de puertas es UN frente de 2 hojas
        else:
            salida.append({"tipo": "puerta", "alto": alto, "n": 1})
    return salida, avisos


def _entrepanos(g: dict) -> int:
    n = ((g.get("interior") or {}).get("entrepanos") or {}).get("cantidad")
    return int(n) if n else 0


def a_gabinete(g: dict, mueble: dict, materiales: Optional[Dict[str, str]] = None,
               prefijo: str = "") -> Tuple[dict, List[str]]:
    """Un gabinete del contrato -> dict listo para `S.proyecto.gabinetes`."""
    materiales = materiales or {}
    avisos: List[str] = []
    med = g.get("medidas_exteriores_mm") or {}
    pos = g.get("posicion_mm") or {}
    zoc = g.get("zoclo") or {}
    familia = g.get("familia", "base")
    tipo = FAMILIA_A_TIPO.get(familia, "base")

    # #056 — La profundidad NO se lee de un alzado: ahi se ve el frente de
    # canto. El prompt se lo prohibe al modelo a proposito («no la inventes»),
    # asi que casi siempre llega en null — y un gabinete sin fondo no se puede
    # despiezar. Antes eso salia como un aviso y el mueble entraba inservible.
    #
    # Se pone el fondo de tabla del taller segun el tipo, y se dice que se puso.
    # Es un supuesto razonable y visible, en vez de un hueco silencioso.
    if not med.get("prof"):
        supuesto = PROF_POR_TIPO.get(tipo)
        if supuesto:
            med = {**med, "prof": supuesto}
            avisos.append(f"{g['id']}: el alzado no dice el fondo; se puso "
                          f"{supuesto:.0f} mm ({tipo}). Revisalo.")

    for campo in ("ancho", "alto", "prof"):
        if not med.get(campo):
            avisos.append(f"{g['id']}: sin {campo}; el gabinete no se puede construir")

    frentes, av = _agrupar_frentes(g.get("frentes") or [])
    avisos += [f"{g['id']}: {a}" for a in av]

    lleva_zoclo = tipo == "base" and bool(zoc.get("alto_mm"))
    mat_cuerpo = materiales.get((g.get("material") or {}).get("cuerpo"))
    mat_frente = materiales.get((g.get("material") or {}).get("frentes"))

    d = {
        "nombre": (prefijo + g["id"]) if prefijo else g["id"],
        "tipo": tipo,
        "ancho": med.get("ancho"),
        "alto": med.get("alto"),
        "prof": med.get("prof"),
        "frentes": frentes,
        "n_entrepanos": _entrepanos(g),
        "entrepanos_fijos": False,
        "tapa_completa": None,               # None = el default del tipo
        "con_zoclo": lleva_zoclo,
        "altura_zoclo": zoc.get("alto_mm") if lleva_zoclo else None,
        "alto_derivado": "cuerpo",           # el alto que manda es el total leído
        "cantidad": 1,
        "pos_x": pos.get("x") or 0.0,
        "pos_z": 0.0,
        "rot": 0,
        "alto_colgado": (pos.get("z") if tipo == "aereo" else None),
        "mat_cuerpo": mat_cuerpo,
        "mat_frente": mat_frente,
        "mat_respaldo": None,
        # rastro de dónde salió: el DESPIEZADOR lo ignora, pero queda en el archivo
        "origen_identificador": {
            "mueble": mueble.get("id"),
            "vista": (mueble.get("vista") or {}).get("numero"),
            "plantilla_sugerida": g.get("plantilla_sugerida"),
            "confianza": g.get("confianza"),
            "procedencia": g.get("procedencia"),
            "vecinos": g.get("restricciones"),
        },
    }
    return d, avisos


def convertir(payload: dict, materiales: Optional[Dict[str, str]] = None,
              incluir_corridos: bool = False) -> Dict[str, Any]:
    """Contrato completo -> {gabinetes, avisos, resumen}."""
    if payload.get("esquema") != "t101.gabinetes/1.0":
        raise ValueError(f"esquema no soportado: {payload.get('esquema')}")
    gabinetes: List[dict] = []
    avisos: List[str] = []

    for mueble in payload.get("muebles", []):
        for g in mueble.get("gabinetes", []):
            if not g.get("fabricable", True):
                continue                      # huecos de electrodoméstico: no se fabrican
            d, av = a_gabinete(g, mueble, materiales)
            gabinetes.append(d)
            avisos += av
        if incluir_corridos:
            for c in mueble.get("corridos", []):
                avisos.append(
                    f"{c['id']}: {c.get('tipo')} corrido de "
                    f"{(c.get('medidas_mm') or {}).get('largo', 0):.0f} mm — "
                    "Taller 101 no lo modela como gabinete; queda fuera del import")

    if not payload.get("listo_para_despiezar", True):
        avisos.append(f"{len(payload.get('pendientes', []))} pregunta(s) sin contestar")

    return {
        "gabinetes": gabinetes,
        "avisos": avisos,
        "resumen": {
            "muebles": len(payload.get("muebles", [])),
            "gabinetes": len(gabinetes),
            "puertas": sum(f["n"] for g in gabinetes for f in g["frentes"]
                           if f["tipo"] == "puerta"),
            "cajones": sum(1 for g in gabinetes for f in g["frentes"]
                           if f["tipo"] == "cajon"),
        },
    }


def materiales_del_plano(payload: dict) -> List[str]:
    """Los materiales que trae el plano, para mapearlos al catálogo del proyecto."""
    vistos = []
    for mueble in payload.get("muebles", []):
        for g in mueble.get("gabinetes", []):
            for v in (g.get("material") or {}).values():
                if v and v not in vistos:
                    vistos.append(v)
            for f in g.get("frentes") or []:
                if f.get("material") and f["material"] not in vistos:
                    vistos.append(f["material"])
    return vistos
