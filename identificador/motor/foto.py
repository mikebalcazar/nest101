"""FOTO de un plano impreso: enderezar la hoja y encontrar las vistas sin PDF.

Una foto trae tres problemas que un escaneo no tiene:
  1. perspectiva  (la hoja sale como trapecio)
  2. iluminacion desigual (sombra de la lampara, brillo del papel)
  3. resolucion floja: el dibujo ocupa una fraccion de los pixeles

Aqui se corrigen los tres. La deteccion de vistas usa OCR (tesseract) para hallar los
rotulos "ALZADO A", "CORTE A", "PLANTA": es el equivalente raster de `sheet.py`.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

RE_VISTA = re.compile(r"\b(ALZADO|ELEVACI[OÓ]N|CORTE|SECCI[OÓ]N|PLANTA|DETALLE|AXONOM)", re.I)
TIPO_POR_PALABRA = [
    ("elevacion", re.compile(r"ALZADO|ELEVACI", re.I)),
    ("corte", re.compile(r"CORTE|SECCI", re.I)),
    ("planta", re.compile(r"PLANTA", re.I)),
    ("detalle", re.compile(r"DETALLE", re.I)),
    ("axonometrico", re.compile(r"AXONOM|ISOM", re.I)),
]


@dataclass
class VistaFoto:
    titulo: str
    tipo: str
    rect: Tuple[int, int, int, int]      # x0,y0,x1,y1 en la imagen enderezada
    rect_rotulo: Tuple[int, int, int, int]
    confianza: float


# ------------------------------------------------------- enderezar la hoja
def _cuadrilatero(gray: np.ndarray) -> Optional[np.ndarray]:
    """Busca el contorno de la hoja: el cuadrilatero claro mas grande."""
    h, w = gray.shape
    chico = cv2.resize(gray, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
    suave = cv2.GaussianBlur(chico, (5, 5), 0)
    _, bw = cv2.threshold(suave, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    area_min = 0.25 * chico.shape[0] * chico.shape[1]
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(c) < area_min:
            break
        aprox = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(aprox) == 4:
            return (aprox.reshape(4, 2) * 4).astype(np.float32)
    return None


def _ordenar(pts: np.ndarray) -> np.ndarray:
    """Esquinas en orden: sup-izq, sup-der, inf-der, inf-izq."""
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def enderezar(png: Path, out: Path, ancho_objetivo: int = 2600) -> Tuple[Path, bool]:
    """Corrige la perspectiva de la hoja. Si no encuentra la hoja, sigue derecho."""
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise IOError(png)
    quad = _cuadrilatero(img)
    corregida = False
    if quad is not None:
        p = _ordenar(quad)
        anc = int(max(np.linalg.norm(p[1] - p[0]), np.linalg.norm(p[2] - p[3])))
        alt = int(max(np.linalg.norm(p[3] - p[0]), np.linalg.norm(p[2] - p[1])))
        if anc > 50 and alt > 50:
            destino = np.array([[0, 0], [anc, 0], [anc, alt], [0, alt]], dtype=np.float32)
            img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(p, destino), (anc, alt))
            corregida = True
    # sube resolucion antes de limpiar: el dibujo viene chico
    if img.shape[1] < ancho_objetivo:
        f = ancho_objetivo / img.shape[1]
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
    return out, corregida


def limpiar(png: Path, out: Path, bloque: int = 41) -> Path:
    """Quita sombra de lampara y sube el contraste de la linea sin quemar el trazo."""
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    fondo = cv2.morphologyEx(img, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (bloque, bloque)))
    img = cv2.divide(img, fondo, scale=255)
    img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(img)
    cv2.imwrite(str(out), img)
    return out


# ------------------------------------------------------- vistas por OCR
_IDIOMA_CACHE = None


def _idioma_disponible() -> str:
    """spa si esta instalado; si no, eng. Los planos mexicanos leen mejor con spa."""
    global _IDIOMA_CACHE
    if _IDIOMA_CACHE is None:
        try:
            r = subprocess.run(["tesseract", "--list-langs"], capture_output=True,
                               text=True, timeout=20).stdout
            _IDIOMA_CACHE = "spa+eng" if "spa" in r.split() else "eng"
        except Exception:
            _IDIOMA_CACHE = "eng"
    return _IDIOMA_CACHE


def _ocr(png: Path, idioma: Optional[str] = None, psm: int = 11) -> List[dict]:
    """Palabras con caja. Requiere tesseract instalado."""
    idioma = idioma or _idioma_disponible()
    try:
        salida = subprocess.run(
            ["tesseract", str(png), "stdout", "-l", idioma, "--psm", str(psm), "tsv"],
            capture_output=True, text=True, timeout=180).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    filas = [l.split("\t") for l in salida.splitlines()]
    if not filas or filas[0][0] != "level":
        return []
    cab = filas[0]
    out = []
    for f in filas[1:]:
        if len(f) != len(cab):
            continue
        d = dict(zip(cab, f))
        txt = (d.get("text") or "").strip()
        if not txt:
            continue
        try:
            out.append({"texto": txt, "conf": float(d["conf"]),
                        "x": int(d["left"]), "y": int(d["top"]),
                        "w": int(d["width"]), "h": int(d["height"])})
        except (ValueError, KeyError):
            continue
    return out


def detectar_vistas(png: Path, margen: float = 0.06,
                    alto_ventana: float = 0.4) -> List[VistaFoto]:
    """Busca rotulos tipo 'ALZADO A' / 'CORTE A' y les asigna el dibujo de ARRIBA."""
    palabras = [p for p in _ocr(png) if p["conf"] > 30]
    rotulos = [p for p in palabras if RE_VISTA.search(p["texto"])]
    if not rotulos:
        return []
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    H, W = img.shape
    # tinta de la hoja, para acotar el recuadro de cada vista
    _, bw = cv2.threshold(255 - img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    vistas = []
    for r in sorted(rotulos, key=lambda p: p["x"]):
        titulo = r["texto"]
        # pega la letra/numero que sigue ("ALZADO" + "A")
        for p in palabras:
            if 0 < p["x"] - (r["x"] + r["w"]) < 60 and abs(p["y"] - r["y"]) < r["h"]:
                titulo += " " + p["texto"]
        tipo = next((t for t, rx in TIPO_POR_PALABRA if rx.search(r["texto"])), "otro")

        # banda horizontal: primero se acota con los rotulos vecinos, y luego
        # se recorta al bloque de tinta que esta REALMENTE encima del rotulo
        # (si no, un rotulo se traga las notas y las vistas de al lado).
        otros = [o for o in rotulos if o is not r]
        izq = max([o["x"] + o["w"] for o in otros if o["x"] + o["w"] < r["x"]] + [0])
        der = min([o["x"] for o in otros if o["x"] > r["x"] + r["w"]] + [W])
        tope = max(1, r["y"] - 8)
        # ventana vertical: el dibujo de una vista esta JUSTO encima de su rotulo,
        # no en toda la hoja. Asi no se cuelan las notas ni la vista de arriba.
        piso = max(0, tope - int(H * alto_ventana))
        izq, der = _bloque_de_tinta(bw[piso:tope, :], izq, der,
                                    r["x"] + r["w"] // 2, W)
        banda = bw[piso:tope, izq:der]
        ys, xs = np.nonzero(banda)
        if len(xs) < 50:
            continue
        mx, my = int(W * margen * 0.5), int(H * margen * 0.5)
        x0 = max(0, izq + int(xs.min()) - mx); x1 = min(W, izq + int(xs.max()) + mx)
        y0 = max(0, piso + int(ys.min()) - my); y1 = min(H, piso + int(ys.max()) + my)
        vistas.append(VistaFoto(titulo=titulo, tipo=tipo, rect=(x0, y0, x1, y1),
                                rect_rotulo=(r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]),
                                confianza=min(1.0, r["conf"] / 100)))
    return vistas


def _bloque_de_tinta(banda: np.ndarray, izq: int, der: int, x_centro: int, W: int,
                     hueco_max: float = 0.03, minimo: float = 0.12) -> Tuple[int, int]:
    """Columnas con tinta que forman un bloque continuo alrededor de `x_centro`.
    `minimo` es alto a proposito: cuenta como tinta la columna DENSA del dibujo,
    no el texto delgado de las notas ni la linea guia que las apunta. Un hueco de
    mas de `hueco_max` del ancho de la hoja corta el bloque."""
    perfil = banda[:, izq:der].sum(axis=0)
    if perfil.size == 0:
        return izq, der
    umbral = max(1.0, perfil.max() * minimo)
    con_tinta = perfil > umbral
    hueco = max(8, int(W * hueco_max))
    c = min(max(x_centro - izq, 0), len(con_tinta) - 1)
    if not con_tinta[c]:                       # el rotulo puede caer en blanco
        cercanos = np.nonzero(con_tinta)[0]
        if not len(cercanos):
            return izq, der
        c = int(cercanos[np.argmin(np.abs(cercanos - c))])
    i = c
    while i > 0:
        j = i - 1
        while j > 0 and not con_tinta[j] and i - j < hueco:
            j -= 1
        if con_tinta[j]:
            i = j
        else:
            break
    k = c
    while k < len(con_tinta) - 1:
        j = k + 1
        while j < len(con_tinta) - 1 and not con_tinta[j] and j - k < hueco:
            j += 1
        if con_tinta[j]:
            k = j
        else:
            break
    return izq + i, izq + k + 1


def recortar(png: Path, v: VistaFoto, out_dir: Path, px_objetivo: int = 2000) -> Path:
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    x0, y0, x1, y1 = v.rect
    crop = img[y0:y1, x0:x1]
    lado = max(crop.shape)
    if lado < px_objetivo:
        f = px_objetivo / lado
        crop = cv2.resize(crop, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"foto_{re.sub(r'[^A-Za-z0-9]+', '_', v.titulo)[:28]}.png"
    cv2.imwrite(str(p), crop)
    return p


def texto_de_la_hoja(png: Path, conf_min: float = 45) -> List[str]:
    """Texto suelto de la hoja (notas, membrete) para dárselo al modelo como pista."""
    vistos, out = set(), []
    for p in _ocr(png, psm=6):
        t = p["texto"]
        if p["conf"] >= conf_min and len(t) > 2 and t.lower() not in vistos:
            vistos.add(t.lower())
            out.append(t)
    return out
