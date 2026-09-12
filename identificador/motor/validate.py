"""Normalizacion de unidades y chequeos geometricos de coherencia."""

from __future__ import annotations

import re
from typing import List, Optional

from .schema import Alzado, Aviso, Cota, Documento, FACTOR_MM, Modulo, TipoModulo, Unidad

# rangos plausibles de carpinteria (mm)
RANGOS = {
    TipoModulo.BASE:   {"ancho": (150, 1500), "alto": (600, 1000), "prof": (300, 700)},
    TipoModulo.AEREO:  {"ancho": (150, 1500), "alto": (300, 1200), "prof": (250, 450)},
    TipoModulo.TORRE:  {"ancho": (300, 1500), "alto": (1600, 2800), "prof": (300, 700)},
    TipoModulo.PANEL:  {"ancho": (10, 1500), "alto": (100, 2800), "prof": (10, 700)},
    TipoModulo.CUBIERTA: {"ancho": (200, 6000), "alto": (15, 120), "prof": (300, 900)},
    TipoModulo.ELECTRO: {"ancho": (150, 1300), "alto": (200, 2200), "prof": (300, 800)},
    TipoModulo.ZOCLO:  {"ancho": (50, 6000), "alto": (60, 200), "prof": (300, 700)},
}

# Regla de Taller 101: un cuerpo nunca lleva mas de 2 puertas.
# (Los cajones no tienen tope: una cajonera puede traer 3, 4 o 5.)
MAX_PUERTAS_POR_CUERPO = 2

NUM = re.compile(r"(\d+(?:[.,]\d+)?)")
# Revit/AutoCAD a veces exportan el punto decimal como glifo aparte: "3 25" = 3.25
NUM_PARTIDO = re.compile(r"^(\d{1,2})[  ](\d{2})$")


def _num(texto: str) -> Optional[float]:
    t = texto.strip()
    m = NUM_PARTIDO.match(t)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = NUM.search(t.replace(" ", ""))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def inferir_unidad(textos: List[str]) -> Unidad:
    """Heuristica: por la magnitud tipica de las cotas de un mueble."""
    vals = [v for v in (_num(t) for t in textos) if v is not None and v > 0]
    if not vals:
        return Unidad.MM
    vals.sort()
    med = vals[len(vals) // 2]
    if med < 4:      # 0.60, 2.40 -> metros
        return Unidad.M
    if med < 40:     # 24, 36 -> pulgadas
        return Unidad.IN
    if med < 400:    # 60, 90 -> centimetros
        return Unidad.CM
    return Unidad.MM


def normalizar_cotas(cotas: List[Cota], unidad: Unidad) -> List[Aviso]:
    avisos: List[Aviso] = []
    f = FACTOR_MM[unidad]
    for c in cotas:
        if c.valor_mm is None:
            v = _num(c.texto)
            if v is None:
                avisos.append(Aviso(nivel="warn", codigo="COTA_ILEGIBLE",
                                    mensaje=f"No se pudo leer numero en cota '{c.texto}'"))
                continue
            c.valor_mm = round(v * f, 1)
    return avisos


def _fuera_de_rango(m: Modulo) -> List[str]:
    r = RANGOS.get(m.tipo)
    if not r:
        return []
    malos = []
    for k, attr in (("ancho", "ancho_mm"), ("alto", "alto_mm"), ("prof", "prof_mm")):
        v = getattr(m, attr)
        if v is None:
            continue
        lo, hi = r[k]
        if not (lo <= v <= hi):
            malos.append(f"{k}={v:.0f}mm fuera de [{lo},{hi}]")
    return malos


def validar_alzado(a: Alzado, tol_mm: float = 12.0) -> List[Aviso]:
    avisos: List[Aviso] = []
    avisos += normalizar_cotas(a.cotas, a.unidad_plano)

    # 1. medidas faltantes / baja confianza
    for i, m in enumerate(a.modulos):
        ref = m.clave or f"{a.id}#{i+1}"
        if m.tipo != TipoModulo.ELECTRO and m.ancho_mm is None:
            avisos.append(Aviso(nivel="error", codigo="SIN_ANCHO",
                                mensaje="Modulo sin ancho: no se puede despiezar", ref=ref))
        if m.tipo not in (TipoModulo.ELECTRO, TipoModulo.ZOCLO) and m.alto_mm is None:
            avisos.append(Aviso(nivel="warn", codigo="SIN_ALTO",
                                mensaje="Modulo sin alto", ref=ref))
        if m.prof_mm is None and m.tipo in (TipoModulo.BASE, TipoModulo.AEREO, TipoModulo.TORRE):
            avisos.append(Aviso(nivel="info", codigo="SIN_PROF",
                                mensaje="Profundidad no cotada en alzado; usar default del catalogo",
                                ref=ref))
        if m.confianza < 0.6:
            avisos.append(Aviso(nivel="warn", codigo="BAJA_CONFIANZA",
                                mensaje=f"Confianza {m.confianza:.2f}; revisar contra plano", ref=ref))
        if m.n_puertas > MAX_PUERTAS_POR_CUERPO:
            avisos.append(Aviso(
                nivel="warn", codigo="EXCEDE_PUERTAS",
                mensaje=(f"{m.n_puertas} puertas en un solo cuerpo; el taller usa maximo "
                         f"{MAX_PUERTAS_POR_CUERPO}. La particion esta mal: hay que partirlo."),
                ref=ref))
        for bad in _fuera_de_rango(m):
            avisos.append(Aviso(nivel="warn", codigo="FUERA_DE_RANGO",
                                mensaje=bad, ref=ref))

    # 2. suma de anchos vs ancho total, fila por fila.
    #    Cuentan todos los cuerpos que ocupan lugar horizontal (bases, paneles,
    #    torres, electros); NO cuentan cubierta ni zoclo, que son corridos.
    if a.ancho_total_mm:
        for grupo, nombre in ((TipoModulo.BASE, "fila baja"), (TipoModulo.AEREO, "fila de aereos")):
            fila = _fila(a.modulos, grupo)
            anchos = [m.ancho_mm for m in fila if m.ancho_mm]
            if len(anchos) >= 2:
                # apilados (mismo x, distinto z, ej. faldon sobre registro) cuentan una vez
                por_x = {}
                for m in fila:
                    if m.ancho_mm is None:
                        continue
                    k = round(m.x_mm) if m.x_mm is not None else id(m)
                    por_x[k] = max(por_x.get(k, 0), m.ancho_mm)
                suma = sum(por_x.values())
                if abs(suma - a.ancho_total_mm) > tol_mm:
                    avisos.append(Aviso(
                        nivel="warn", codigo="SUMA_ANCHOS",
                        mensaje=(f"Suma de {nombre} = {suma:.0f}mm vs ancho total "
                                 f"{a.ancho_total_mm:.0f}mm (dif {suma - a.ancho_total_mm:+.0f}mm)"),
                        ref=a.id))

    # 3. traslapes horizontales en la misma fila
    #    los electrodomesticos ocupan lugar en la fila que les toca por altura
    for fila in (TipoModulo.BASE, TipoModulo.AEREO, TipoModulo.TORRE):
        ms = sorted([m for m in _fila(a.modulos, fila)
                     if m.x_mm is not None and m.ancho_mm], key=lambda m: m.x_mm)
        # los apilados (faldon sobre registro) no son traslape: se quedan los de abajo
        vistos = {}
        for m in ms:
            k = round(m.x_mm)
            if k not in vistos or (m.z_mm or 0) < (vistos[k].z_mm or 0):
                vistos[k] = m
        ms = sorted(vistos.values(), key=lambda m: m.x_mm)
        for p, q in zip(ms, ms[1:]):
            fin = p.x_mm + p.ancho_mm
            if q.x_mm + tol_mm < fin:
                avisos.append(Aviso(nivel="warn", codigo="TRASLAPE",
                                    mensaje=(f"'{p.clave or '?'}' termina en {fin:.0f}mm y "
                                             f"'{q.clave or '?'}' empieza en {q.x_mm:.0f}mm"),
                                    ref=a.id))
            elif q.x_mm - fin > tol_mm * 4:
                avisos.append(Aviso(nivel="info", codigo="HUECO",
                                    mensaje=(f"Hueco de {q.x_mm - fin:.0f}mm entre "
                                             f"'{p.clave or '?'}' y '{q.clave or '?'}'"),
                                    ref=a.id))

    # 3.b cota declarada vs geometria medida (solo laminas vectoriales con escala)
    if a.mm_por_px:
        for i, m in enumerate(a.modulos):
            if not m.bbox_px or len(m.bbox_px) != 4:
                continue
            ref = m.clave or f"{a.id}#{i+1}"
            med_w = (m.bbox_px[2] - m.bbox_px[0]) * a.mm_por_px
            med_h = (m.bbox_px[3] - m.bbox_px[1]) * a.mm_por_px
            for nombre, declarado, medido in (("ancho", m.ancho_mm, med_w),
                                              ("alto", m.alto_mm, med_h)):
                if declarado is None:
                    continue
                dif = medido - declarado
                # 6% o 25mm, lo que sea mayor: el bbox del modelo no es exacto
                tol = max(25.0, declarado * 0.06)
                if abs(dif) > tol:
                    avisos.append(Aviso(
                        nivel="warn", codigo="COTA_VS_GEOMETRIA",
                        mensaje=(f"{nombre}: cota dice {declarado:.0f}mm pero el dibujo mide "
                                 f"{medido:.0f}mm ({dif:+.0f}mm)"), ref=ref))

    # 4. claves duplicadas
    claves = [m.clave for m in a.modulos if m.clave]
    dup = {c for c in claves if claves.count(c) > 1}
    for c in dup:
        avisos.append(Aviso(nivel="warn", codigo="CLAVE_DUPLICADA",
                            mensaje=f"Clave '{c}' repetida", ref=a.id))
    return avisos


OCUPAN_FILA = {TipoModulo.BASE, TipoModulo.AEREO, TipoModulo.TORRE,
               TipoModulo.PANEL, TipoModulo.ELECTRO}


def _fila(modulos: List[Modulo], grupo: TipoModulo) -> List[Modulo]:
    """Modulos que ocupan lugar horizontal en la fila `grupo`.
    Cubierta y zoclo quedan fuera: son elementos corridos, no cuerpos."""
    out = []
    for m in modulos:
        if m.tipo not in OCUPAN_FILA:
            continue
        if m.tipo == grupo or (m.tipo in (TipoModulo.PANEL, TipoModulo.ELECTRO)
                               and _misma_fila(m, grupo)):
            out.append(m)
    return out


def _misma_fila(m: Modulo, grupo: TipoModulo) -> bool:
    """Por altura: lo que arranca abajo del nivel de cubierta va con las bases;
    lo que cuelga arriba va con los aereos."""
    Z_CORTE = 1100.0
    if m.z_mm is None:
        return grupo == TipoModulo.BASE
    return (m.z_mm < Z_CORTE) if grupo == TipoModulo.BASE else (m.z_mm >= Z_CORTE)


def validar(doc: Documento) -> Documento:
    for a in doc.alzados:
        doc.avisos.extend(validar_alzado(a))
    return doc
