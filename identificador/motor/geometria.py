"""Lectura GEOMETRICA de una elevacion vectorial: donde acaba un gabinete y donde
empieza otro.

Hallazgo clave sobre planos de Revit/AutoCAD: la elevacion SI distingue cuerpo de
frente, solo que no con texto sino con el grosor del tablero dibujado.

    |        |        ||        |        |
    0       600     1200      1800     2400
    ^        ^        ^^
  costado  junta   DOS laterales pegados
  (19mm)  simple    (19+19 = 38mm)

  - linea sola            -> junta entre dos FRENTES del mismo gabinete
  - par de lineas ~19mm   -> UN lateral: costado del mueble
  - par de lineas ~38mm   -> DOS laterales pegados: frontera entre gabinetes

Esto resuelve por geometria la pregunta que el plano no contesta con palabras
("¿este pano de 1.20 es un gabinete de 2 puertas o dos gabinetes de 1?").
En planos escaneados no hay esta informacion: ahi mandan las heuristicas del LLM
y, si no alcanzan, el dialogo con el usuario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

from . import pdf as P

# espesores de tablero que usa el taller (mm). 16 y 19 son los comunes.
ESPESOR_MIN, ESPESOR_MAX = 9.0, 30.0
DOBLE_MIN, DOBLE_MAX = 30.0, 52.0
TOL_CLUSTER_PT = 1.2          # dos lineas mas cerca que esto son la misma
SEPARA_GRUPO_MM = 60.0        # mas lejos que esto ya es otro elemento


ANCHO_MIN_GABINETE_MM = 200.0


def _recortar_extremos(grupos, mm_por_pt):
    """Tira las lineas sueltas de los extremos que no son costado del mueble
    (linea de muro, testigo de cota, canto del lavabo). Un costado real casi
    siempre trae su espesor de tablero dibujado."""
    def espesor(g):
        return (g[-1][0] - g[0][0]) * mm_por_pt

    while len(grupos) > 2 and espesor(grupos[0]) < ESPESOR_MIN:
        hueco = (grupos[1][0][0] - grupos[0][-1][0]) * mm_por_pt
        if hueco < ANCHO_MIN_GABINETE_MM and espesor(grupos[1]) >= ESPESOR_MIN:
            grupos = grupos[1:]
        else:
            break
    while len(grupos) > 2 and espesor(grupos[-1]) < ESPESOR_MIN:
        hueco = (grupos[-1][0][0] - grupos[-2][-1][0]) * mm_por_pt
        if hueco < ANCHO_MIN_GABINETE_MM and espesor(grupos[-2]) >= ESPESOR_MIN:
            grupos = grupos[:-1]
        else:
            break
    return grupos


@dataclass
class Junta:
    x_mm: float                                    # desde el costado izquierdo del mueble
    tipo: Literal["costado", "divisor", "junta_frente", "ambiguo"]
    espesor_mm: float
    n_lineas: int
    confianza: float
    evidencia: str


@dataclass
class Analisis:
    ancho_mm: float
    alto_frente_mm: float
    juntas: List[Junta] = field(default_factory=list)
    espesor_detectado_mm: Optional[float] = None
    particion: List[Tuple[float, float]] = field(default_factory=list)  # (x0,x1) por gabinete
    frentes_por_gabinete: List[List[Tuple[float, float]]] = field(default_factory=list)

    def resumen(self) -> str:
        p = ", ".join(f"{a:.0f}-{b:.0f}" for a, b in self.particion)
        return (f"ancho {self.ancho_mm:.0f}mm, tablero {self.espesor_detectado_mm or '?'}mm, "
                f"{len(self.particion)} gabinete(s): {p}")


# ---------------------------------------------------------------- extraccion
def _verticales(page: P.Pagina, rect: P.Rect):
    out = []
    for dr in page.dibujos():
        rc = dr["rect"]
        if not (rc.x0 >= rect.x0 - 2 and rc.x1 <= rect.x1 + 2
                and rc.y0 >= rect.y0 - 2 and rc.y1 <= rect.y1 + 2):
            continue
        for it in dr["items"]:
            if it[0] != "l":
                continue
            a, b = it[1], it[2]
            if abs(a.x - b.x) < 0.4 and abs(a.y - b.y) > 3:
                out.append((a.x, min(a.y, b.y), max(a.y, b.y),
                            dr.get("width") or 0.0, dr.get("dashes")))
    return out


def _banda_frentes(verts) -> Optional[Tuple[float, float]]:
    """La banda vertical donde viven los frentes: el (y0,y1) que mas se repite."""
    if not verts:
        return None
    conteo: Dict[Tuple[int, int], int] = {}
    for _x, y0, y1, _w, _d in verts:
        k = (round(y0 / 3), round(y1 / 3))
        conteo[k] = conteo.get(k, 0) + 1
    (ky0, ky1), n = max(conteo.items(), key=lambda kv: kv[1])
    if n < 3:
        return None
    ys = [(y0, y1) for _x, y0, y1, _w, _d in verts
          if round(y0 / 3) == ky0 and round(y1 / 3) == ky1]
    return (sum(y for y, _ in ys) / len(ys), sum(y for _, y in ys) / len(ys))


# ---------------------------------------------------------------- analisis
def analizar(page: P.Pagina, rect: P.Rect, mm_por_pt: float,
             tol_banda: float = 6.0) -> Optional[Analisis]:
    """Analiza la carpinteria de una elevacion vectorial dentro de `rect`."""
    verts = _verticales(page, rect)
    banda = _banda_frentes(verts)
    if not banda:
        return None
    by0, by1 = banda

    # Solo las lineas que EMPIEZAN Y ACABAN en la banda de frentes.
    # Asi se van: las lineas de cota (bajan hasta la cadena), las marcas de corte
    # (cruzan toda la vista) y las flechas de referencia.
    utiles = [v for v in verts
              if abs(v[1] - by0) <= tol_banda and abs(v[2] - by1) <= tol_banda]
    if len(utiles) < 3:
        return None

    # 1. cluster por x
    xs = sorted(v[0] for v in utiles)
    clusters: List[List[float]] = []
    for x in xs:
        if clusters and x - clusters[-1][-1] <= TOL_CLUSTER_PT:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    centros = [(sum(c) / len(c), len(c)) for c in clusters]

    # 2. agrupa clusters vecinos: un lateral son 2 lineas separadas ~espesor
    grupos: List[List[Tuple[float, int]]] = []
    for c in centros:
        if grupos and (c[0] - grupos[-1][-1][0]) * mm_por_pt <= SEPARA_GRUPO_MM:
            grupos[-1].append(c)
        else:
            grupos.append([c])

    grupos = _recortar_extremos(grupos, mm_por_pt)
    if len(grupos) < 2:
        return None
    x_izq = grupos[0][0][0]
    ancho_mm = (grupos[-1][-1][0] - x_izq) * mm_por_pt

    juntas: List[Junta] = []
    espesores: List[float] = []
    for i, g in enumerate(grupos):
        x0, x1 = g[0][0], g[-1][0]
        esp = (x1 - x0) * mm_por_pt
        pos = (x0 - x_izq) * mm_por_pt
        nl = sum(n for _x, n in g)
        borde = i == 0 or i == len(grupos) - 1
        if esp < ESPESOR_MIN:
            tipo, conf, ev = ("costado" if borde else "junta_frente"), 0.7, \
                f"linea sola ({esp:.0f}mm)"
            if borde:
                conf = 0.75
        elif ESPESOR_MIN <= esp <= ESPESOR_MAX:
            tipo, conf = ("costado" if borde else "divisor"), 0.9
            ev = f"un lateral de {esp:.0f}mm"
            espesores.append(esp)
        elif DOBLE_MIN < esp <= DOBLE_MAX:
            tipo, conf, ev = "divisor", 0.95, f"dos laterales pegados ({esp:.0f}mm)"
            espesores.append(esp / 2)
        else:
            tipo, conf, ev = "ambiguo", 0.4, f"grupo de {esp:.0f}mm con {nl} lineas"
        juntas.append(Junta(x_mm=round(pos, 1), tipo=tipo, espesor_mm=round(esp, 1),
                            n_lineas=nl, confianza=conf, evidencia=ev))

    esp_det = round(sum(espesores) / len(espesores), 1) if espesores else None

    # 3. particion en gabinetes: cortan los costados y los divisores
    cortes = [j.x_mm for j in juntas if j.tipo in ("costado", "divisor", "ambiguo")]
    cortes = sorted(set([0.0] + cortes + [round(ancho_mm, 1)]))
    particion = [(a, b) for a, b in zip(cortes, cortes[1:]) if b - a > 40]

    # 4. frentes dentro de cada gabinete: los cortan las juntas simples
    frentes = []
    for a, b in particion:
        internos = [j.x_mm for j in juntas if j.tipo == "junta_frente" and a < j.x_mm < b]
        bordes = sorted([a] + internos + [b])
        frentes.append([(p, q) for p, q in zip(bordes, bordes[1:]) if q - p > 40])

    return Analisis(ancho_mm=round(ancho_mm, 1),
                    alto_frente_mm=round((by1 - by0) * mm_por_pt, 1),
                    juntas=juntas, espesor_detectado_mm=esp_det,
                    particion=particion, frentes_por_gabinete=frentes)


def como_evidencia(a: Analisis) -> str:
    """Texto que se le pasa al modelo de vision como evidencia dura."""
    lineas = [
        "EVIDENCIA GEOMETRICA (medida directamente del PDF vectorial, es confiable):",
        f"- Ancho del mueble: {a.ancho_mm:.0f} mm. Alto del frente: {a.alto_frente_mm:.0f} mm.",
    ]
    if a.espesor_detectado_mm:
        lineas.append(f"- Espesor de tablero detectado: {a.espesor_detectado_mm:.0f} mm.")
    lineas.append("- Lecturas verticales (x desde el costado izquierdo):")
    for j in a.juntas:
        lineas.append(f"    x={j.x_mm:7.0f} mm  {j.tipo:<12} {j.evidencia}")
    lineas.append(f"- Particion de gabinetes que sale de esa geometria: "
                  f"{[f'{x0:.0f}-{x1:.0f}' for x0, x1 in a.particion]}")
    for i, fs in enumerate(a.frentes_por_gabinete, start=1):
        lineas.append(f"    gabinete {i}: {len(fs)} frente(s) "
                      f"{[f'{q-p:.0f}mm' for p, q in fs]}")
    lineas.append("Usa esta particion salvo que el dibujo diga claramente otra cosa; "
                  "si la contradices, explica por que en `notas` y baja la confianza.")
    return "\n".join(lineas)
