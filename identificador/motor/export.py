"""Exportadores: JSON de intercambio t101, CSV de modulos y overlay de verificacion."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

import cv2

from .schema import Documento, Modulo, TipoModulo

ESQUEMA = "t101.identificador/v0.1"

# defaults del catalogo Taller 101 cuando el alzado no cota la profundidad
PROF_DEFAULT = {
    TipoModulo.BASE: 600.0,
    TipoModulo.AEREO: 320.0,
    TipoModulo.TORRE: 600.0,
    TipoModulo.CUBIERTA: 620.0,
    TipoModulo.ZOCLO: 550.0,
}

# lo que NO se fabrica
NO_FABRICABLE = {TipoModulo.ELECTRO}


def a_t101(doc: Documento) -> dict:
    """Payload que consume DESPIEZADOR t101 (formato de intercambio, sin despiece)."""
    alzados = []
    for a in doc.alzados:
        mods = []
        for i, m in enumerate(a.modulos):
            prof = m.prof_mm or PROF_DEFAULT.get(m.tipo)
            mods.append({
                "clave": m.clave or f"{a.id}-{i+1:02d}",
                "tipo": m.tipo.value,
                "fabricable": m.tipo not in NO_FABRICABLE,
                "medidas_mm": {"ancho": m.ancho_mm, "alto": m.alto_mm, "prof": prof},
                "prof_asumida": m.prof_mm is None and prof is not None,
                "posicion_mm": {"x": m.x_mm, "z": m.z_mm},
                "frentes": [
                    {"tipo": f.tipo.value, "ancho_mm": f.ancho_mm, "alto_mm": f.alto_mm,
                     "x_rel_mm": f.x_rel_mm, "z_rel_mm": f.z_rel_mm,
                     "bisagra": f.bisagra, "jaladera": f.jaladera,
                     "material": f.material, "confianza": round(f.confianza, 2),
                     "evidencia": f.evidencia}
                    for f in m.frentes
                ],
                "conteo": {"puertas": m.n_puertas, "cajones": m.n_cajones,
                           "entrepanos": m.entrepanos or 0},
                "particion": {"confianza": m.confianza_particion,
                              "fuente": m.fuente_particion},
                "material": m.material,
                "notas": m.notas,
                "confianza": round(m.confianza, 2),
            })
        alzados.append({
            "id": a.id,
            "titulo": a.titulo,
            "vista": {"numero": a.vista_numero, "tipo": a.tipo_vista,
                      "escala": f"1:{a.escala_den}" if a.escala_den else None,
                      "mm_por_px": round(a.mm_por_px, 4) if a.mm_por_px else None},
            "unidad_origen": a.unidad_plano.value,
            "ancho_total_mm": a.ancho_total_mm,
            "altura_libre_mm": a.altura_libre_mm,
            "modulos": mods,
            "anotaciones": [an.model_dump(exclude={"bbox_px"}) for an in a.anotaciones],
        })
    return {
        "esquema": ESQUEMA,
        "origen": {"archivo": doc.archivo, "pagina": doc.pagina, "dpi": doc.dpi,
                   "modelo_vision": doc.modelo_vision},
        "requiere_revision": doc.requiere_revision,
        "avisos": [av.model_dump() for av in doc.avisos],
        "alzados": alzados,
    }


def escribir_json(doc: Documento, out: Path) -> Path:
    out.write_text(json.dumps(a_t101(doc), indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def escribir_csv(doc: Documento, out: Path) -> Path:
    cols = ["alzado", "clave", "tipo", "ancho_mm", "alto_mm", "prof_mm", "x_mm", "z_mm",
            "puertas", "cajones", "entrepanos", "frentes", "material",
            "particion", "confianza", "notas"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for a in doc.alzados:
            for i, m in enumerate(a.modulos):
                w.writerow({
                    "alzado": a.id, "clave": m.clave or f"{a.id}-{i+1:02d}",
                    "tipo": m.tipo.value, "ancho_mm": m.ancho_mm, "alto_mm": m.alto_mm,
                    "prof_mm": m.prof_mm or PROF_DEFAULT.get(m.tipo),
                    "x_mm": m.x_mm, "z_mm": m.z_mm, "puertas": m.n_puertas,
                    "cajones": m.n_cajones, "entrepanos": m.entrepanos,
                    "frentes": " + ".join(
                        f"{f.tipo.value} {f.ancho_mm:.0f}x{f.alto_mm:.0f}"
                        if f.ancho_mm and f.alto_mm else f.tipo.value
                        for f in m.frentes) or "-",
                    "material": m.material,
                    "particion": (f"{m.fuente_particion} {m.confianza_particion:.2f}"
                                  if m.fuente_particion and m.confianza_particion else ""),
                    "confianza": round(m.confianza, 2),
                    "notas": m.notas,
                })
    return out


def overlay(doc: Documento, png: Path, out: Path) -> Path:
    """Dibuja los bbox detectados sobre la imagen: verificacion visual rapida."""
    img = cv2.imread(str(png), cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(png)
    for a in doc.alzados:
        for i, m in enumerate(a.modulos):
            if not m.bbox_px or len(m.bbox_px) != 4:
                continue
            x0, y0, x1, y1 = [int(v) for v in m.bbox_px]
            col = (0, 160, 0) if m.confianza >= 0.6 else (0, 140, 255)
            cv2.rectangle(img, (x0, y0), (x1, y1), col, 2)
            sa = f"{m.ancho_mm:.0f}" if m.ancho_mm else "?"
            sh = f"{m.alto_mm:.0f}" if m.alto_mm else "?"
            et = f"{m.clave or i+1} {sa}x{sh}"
            (tw, th), _ = cv2.getTextSize(et, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            ty = y0 + th + 6
            cv2.rectangle(img, (x0 + 2, ty - th - 3), (x0 + 6 + tw, ty + 3), (255, 255, 255), -1)
            cv2.putText(img, et, (x0 + 4, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1, cv2.LINE_AA)
        for c in a.cotas:
            if c.bbox_px and len(c.bbox_px) == 4:
                x0, y0, x1, y1 = [int(v) for v in c.bbox_px]
                cv2.rectangle(img, (x0, y0), (x1, y1), (200, 0, 200), 1)
    cv2.imwrite(str(out), img)
    return out
