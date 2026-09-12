"""Contrato de entrega IDENTIFICADOR -> DESPIEZADOR t101, version 1.0.

REGLA DE ORO DE LA FRONTERA
    IDENTIFICADOR dice QUE mueble es y de que tamano. DESPIEZADOR decide COMO se
    fabrica. El engine nunca escoge sistema de ensamble, holguras ni orden de corte:
    eso vive en el catalogo de plantillas del DESPIEZADOR, que es donde el taller
    cambia de criterio sin volver a leer planos.

Por eso el payload trae:
  1. la geometria del mueble, cerrada y sin ambiguedad (ya paso el dialogo)
  2. la composicion de cada gabinete (frentes, interior) en terminos de carpinteria
  3. las restricciones de contexto (que lateral es vista, cual es compartido, muros)
  4. la PROCEDENCIA de cada dato: plano, geometria, dialogo o default
  5. lo que quedo pendiente, si se exporta incompleto

El punto 4 es lo que permite que alguien, tres semanas despues, sepa si una medida
salio de una cota del plano o de un default que nadie confirmo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .schema import Documento, Frente, Modulo, TipoFrente, TipoModulo

ESQUEMA = "t101.gabinetes/1.0"

# Elementos que corren a lo largo del mueble y no son un cuerpo:
# DESPIEZADOR los despieza como tableros sueltos, no como cajas.
# El ZOCLO solo entra aqui si el taller lo hace corrido; en Taller 101 va integrado
# a cada gabinete, asi que por default se reparte entre los cuerpos (ver `absorber_zoclo`).
CORRIDOS = {TipoModulo.CUBIERTA, TipoModulo.ZOCLO}
NO_FABRICABLE = {TipoModulo.ELECTRO}

FAMILIA = {
    TipoModulo.BASE: "base", TipoModulo.AEREO: "aereo", TipoModulo.TORRE: "torre",
    TipoModulo.PANEL: "panel", TipoModulo.CUBIERTA: "corrido",
    TipoModulo.ZOCLO: "corrido", TipoModulo.ELECTRO: "hueco", TipoModulo.OTRO: "otro",
}


def plantilla_sugerida(m: Modulo) -> str:
    """Que plantilla constructiva le toca. Es SUGERENCIA: DESPIEZADOR manda."""
    fam = FAMILIA.get(m.tipo, "otro").upper()
    if m.tipo in CORRIDOS:
        return "CUBIERTA" if m.tipo == TipoModulo.CUBIERTA else "ZOCLO"
    if m.tipo == TipoModulo.ELECTRO:
        return "HUECO_ELECTRODOMESTICO"
    if m.tipo == TipoModulo.PANEL:
        return "PANEL_REMATE"
    tipos = {f.tipo for f in m.frentes}
    if not m.frentes:
        return f"{fam}_ABIERTO"
    if tipos == {TipoFrente.REGISTRO}:
        return f"{fam}_REGISTRO"
    if tipos <= {TipoFrente.PANEL_CIEGO}:
        return f"{fam}_CIEGO"
    if tipos == {TipoFrente.CAJON}:
        return f"{fam}_CAJONES"
    if TipoFrente.CAJON in tipos and TipoFrente.PUERTA in tipos:
        return f"{fam}_MIXTO"
    if tipos <= {TipoFrente.PUERTA, TipoFrente.VIDRIO}:
        return f"{fam}_PUERTAS"
    return f"{fam}_ESPECIAL"


def _procedencia(m: Modulo, prof_asumida: bool) -> List[dict]:
    """De donde salio cada dato. Sin esto nadie puede auditar un despiece."""
    p = []
    if m.fuente_particion:
        p.append({"campo": "particion", "fuente": m.fuente_particion,
                  "confianza": m.confianza_particion,
                  "detalle": "como se decidio que esto es un cuerpo y no dos"})
    if m.fuente_cotas:
        p.append({"campo": "medidas", "fuente": "plano",
                  "detalle": "cotas usadas: " + ", ".join(m.fuente_cotas)})
    if prof_asumida:
        p.append({"campo": "prof_mm", "fuente": "default",
                  "detalle": "el alzado no cota la profundidad; valor del catalogo"})
    if m.notas:
        p.append({"campo": "lectura", "fuente": "plano", "detalle": m.notas})
    return p


def _frente(f: Frente, idx: int) -> dict:
    d = {
        "orden": idx,
        "tipo": f.tipo.value,
        "medidas_mm": {"ancho": f.ancho_mm, "alto": f.alto_mm},
        "posicion_mm": {"x_rel": f.x_rel_mm, "z_rel": f.z_rel_mm},
        "material": f.material,
        "confianza": round(f.confianza, 2),
        "evidencia": f.evidencia,
    }
    # lo que el frente le exige al herraje, sin escogerlo por el taller
    if f.tipo == TipoFrente.PUERTA:
        d["apertura"] = {"tipo": "abatible", "lado_bisagra": f.bisagra}
    elif f.tipo == TipoFrente.CAJON:
        d["apertura"] = {"tipo": "extraible", "lado_bisagra": None}
    elif f.tipo == TipoFrente.REGISTRO:
        d["apertura"] = {"tipo": "desmontable", "lado_bisagra": None}
    else:
        d["apertura"] = {"tipo": "fijo", "lado_bisagra": None}
    if f.jaladera:
        d["jaladera"] = f.jaladera
    return d


def _restricciones(modulos: List[Modulo], i: int) -> dict:
    """Que tiene cada gabinete a los lados. DESPIEZADOR decide si comparte lateral."""
    m = modulos[i]
    fila = [x for x in modulos
            if x.tipo not in CORRIDOS and x.x_mm is not None and x.ancho_mm
            and (x.z_mm or 0) // 1000 == (m.z_mm or 0) // 1000]
    fila.sort(key=lambda x: x.x_mm)
    if m not in fila:
        return {"lateral_izq": "desconocido", "lateral_der": "desconocido"}
    k = fila.index(m)
    izq = "extremo_vista" if k == 0 else f"contiguo:{fila[k-1].clave or k-1}"
    der = "extremo_vista" if k == len(fila) - 1 else f"contiguo:{fila[k+1].clave or k+1}"
    return {"lateral_izq": izq, "lateral_der": der,
            "posterior": "contra_muro",
            "superior": "bajo_cubierta" if m.tipo == TipoModulo.BASE else "libre",
            "inferior": "sobre_zoclo" if m.tipo == TipoModulo.BASE else "colgado"}


def _interior(m: Modulo) -> dict:
    """Lo que va adentro del cuerpo y que el alzado deja ver."""
    cajones = [f for f in m.frentes if f.tipo == TipoFrente.CAJON]
    return {
        "entrepanos": {"cantidad": m.entrepanos,
                       "tipo": None if m.entrepanos is None else "movil",
                       "nota": None if m.entrepanos is not None
                               else "el alzado no muestra entrepanos; los pone DESPIEZADOR"},
        "cajones": [{"orden": i + 1, "alto_frente_mm": f.alto_mm,
                     "corredera": {"tipo": None, "largo_mm": None,
                                   "nota": "lo define DESPIEZADOR por la profundidad"}}
                    for i, f in enumerate(cajones)],
        "travesanos": None,
    }


def _gabinete(m: Modulo, modulos: List[Modulo], i: int,
              prof_default: Optional[float],
              info_zoclo: Optional[dict] = None) -> dict:
    prof = m.prof_mm if m.prof_mm is not None else prof_default
    lleva_zoclo = info_zoclo is not None and m.tipo in (TipoModulo.BASE, TipoModulo.TORRE)
    return {
        "id": m.clave or f"G{i+1:02d}",
        "familia": FAMILIA.get(m.tipo, "otro"),
        "plantilla_sugerida": plantilla_sugerida(m),
        "fabricable": m.tipo not in NO_FABRICABLE,
        "medidas_exteriores_mm": {"ancho": m.ancho_mm, "alto": m.alto_mm, "prof": prof},
        "posicion_mm": {"x": m.x_mm, "z": m.z_mm},
        "material": {"cuerpo": m.material,
                     "frentes": next((f.material for f in m.frentes if f.material), m.material)},
        "frentes": [_frente(f, k + 1) for k, f in enumerate(m.frentes)],
        "interior": _interior(m),
        "zoclo": (info_zoclo if lleva_zoclo else
                  {"integrado": False, "nota": "este cuerpo no se apoya en piso"}),
        "restricciones": _restricciones(modulos, i),
        "confianza": {"global": round(m.confianza, 2),
                      "particion": m.confianza_particion},
        "procedencia": _procedencia(m, m.prof_mm is None and prof is not None),
    }


def _corrido(m: Modulo, i: int) -> dict:
    return {
        "id": m.clave or f"C{i+1:02d}",
        "tipo": m.tipo.value,
        "plantilla_sugerida": plantilla_sugerida(m),
        "medidas_mm": {"largo": m.ancho_mm, "espesor_o_alto": m.alto_mm, "prof": m.prof_mm},
        "posicion_mm": {"x": m.x_mm, "z": m.z_mm},
        "material": m.material,
        "confianza": round(m.confianza, 2),
        "procedencia": _procedencia(m, False),
    }


def absorber_zoclo(modulos: List[Modulo]) -> Tuple[List[Modulo], Optional[dict]]:
    """Taller 101 hace el zoclo POR GABINETE, no corrido.

    El plano lo dibuja como una franja de punta a punta, asi que aqui se reparte:
    cada cuerpo de piso se baja a z=0, crece de alto lo que mide el zoclo, y se le
    cuelga un bloque `zoclo` con su altura y su retranqueo. El frente NO crece: el
    zoclo va retranqueado debajo de la puerta.
    """
    zoclos = [m for m in modulos if m.tipo == TipoModulo.ZOCLO]
    if not zoclos:
        return modulos, None
    z = zoclos[0]
    alto_z = z.alto_mm
    salida = []
    for m in modulos:
        if m.tipo == TipoModulo.ZOCLO:
            continue
        if m.tipo == TipoModulo.BASE or (m.tipo == TipoModulo.TORRE and (m.z_mm or 0) <= (alto_z or 0) + 5):
            nuevo = m.model_copy(deep=True)
            if alto_z and nuevo.alto_mm:
                nuevo.alto_mm = round(nuevo.alto_mm + alto_z, 1)
            nuevo.z_mm = 0.0
            for f in nuevo.frentes:          # los frentes se corren, no crecen
                if f.z_rel_mm is not None and alto_z:
                    f.z_rel_mm = round(f.z_rel_mm + alto_z, 1)
            salida.append(nuevo)
        else:
            salida.append(m)
    info = {"alto_mm": alto_z, "material": z.material, "integrado": True,
            "retranqueo_mm": None,
            "nota": ("El plano lo dibuja corrido; se reparte por gabinete porque el taller "
                     "lo fabrica integrado. El retranqueo lo pone DESPIEZADOR.")}
    return salida, info


def construir(doc: Documento, *, proyecto: Optional[dict] = None,
              tipo_origen: str = "vectorial", lamina: Optional[str] = None,
              prof_default: Optional[float] = None,
              pendientes: Optional[List[dict]] = None,
              zoclo: str = "integrado") -> dict:
    """Arma el payload que consume DESPIEZADOR.

    `zoclo`: "integrado" (default de Taller 101: cada gabinete trae el suyo) o
    "corrido" (se entrega como tablero suelto en `corridos`).
    """
    muebles = []
    for a in doc.alzados:
        modulos = list(a.modulos)
        info_zoclo = None
        if zoclo == "integrado":
            modulos, info_zoclo = absorber_zoclo(modulos)
        cuerpos = [m for m in modulos if m.tipo not in CORRIDOS]
        corridos = [m for m in modulos if m.tipo in CORRIDOS]
        # el alto total sale de la cota general si existe; si no, de las posiciones.
        # Nunca se estima cuando las posiciones no se conocen: mejor null que un numero falso.
        profs = [m.prof_mm for m in modulos if m.prof_mm]
        if a.alto_total_mm:
            alto_total = a.alto_total_mm
        else:
            apilados = [(m.z_mm or 0) + (m.alto_mm or 0)
                        for m in modulos if m.alto_mm and m.z_mm is not None]
            alto_total = max(apilados) if apilados else None
        muebles.append({
            "id": a.id,
            "nombre": a.titulo,
            "vista": {"numero": a.vista_numero, "tipo": a.tipo_vista,
                      "escala": f"1:{a.escala_den}" if a.escala_den else None},
            "medidas_totales_mm": {
                "ancho": a.ancho_total_mm,
                "alto": alto_total,
                "prof": max(profs) if profs else prof_default},
            "gabinetes": [_gabinete(m, cuerpos, i, prof_default, info_zoclo)
                          for i, m in enumerate(cuerpos)],
            "corridos": [_corrido(m, i) for i, m in enumerate(corridos)],
            "anotaciones": [an.model_dump(exclude={"bbox_px"}) for an in a.anotaciones],
        })

    geom = tipo_origen == "vectorial"
    return {
        "esquema": ESQUEMA,
        "generado": {"por": "IDENTIFICADOR", "fecha": datetime.now(timezone.utc).isoformat(),
                     "modelo_vision": doc.modelo_vision},
        "unidades": "mm",
        "proyecto": proyecto or {},
        "origen": {
            "archivo": doc.archivo, "pagina": doc.pagina, "lamina": lamina,
            "tipo": tipo_origen,
            "geometria_confiable": geom,
            "nota": ("PDF vectorial: la geometria del dibujo se pudo medir y contrastar "
                     "contra las cotas."
                     if geom else
                     "Escaneo o foto: SOLO valen las cotas escritas; el dibujo no se midio."),
        },
        "muebles": muebles,
        "avisos": [av.model_dump() for av in doc.avisos],
        "pendientes": pendientes or [],
        "listo_para_despiezar": not (pendientes or []),
        "contrato": {
            "quien_decide": {
                "IDENTIFICADOR": ["que gabinetes hay", "medidas exteriores",
                                  "composicion de frentes", "materiales del plano",
                                  "contexto y vecinos"],
                "reglas_taller_aplicadas": ["maximo 2 puertas por cuerpo",
                                            f"zoclo {zoclo}"],
                "DESPIEZADOR": ["sistema de ensamble", "espesores por pieza",
                                "holguras y juegos", "herrajes concretos",
                                "cantos", "optimizacion de corte"],
            }
        },
    }
