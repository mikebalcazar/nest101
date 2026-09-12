"""Rasterizado y limpieza de planos escaneados / bitmaps."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

BITMAPS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


# ---------------------------------------------------------------- rasterizado
def pdf_a_imagenes(pdf: Path, dpi: int = 300, out_dir: Path | None = None) -> List[Path]:
    from .pdf import abrir

    out_dir = out_dir or pdf.parent / "_raster"
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = abrir(pdf)
    zoom = dpi / 72.0
    salidas = []
    try:
        for i, page in enumerate(doc, start=1):
            salidas.append(page.guardar_imagen(
                out_dir / f"{pdf.stem}_p{i:02d}.png", zoom=zoom))
    finally:
        doc.close()
    return salidas


def cargar_entrada(path: Path, dpi: int = 300) -> List[Path]:
    """Acepta PDF o bitmap. Regresa lista de PNG, uno por pagina."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return pdf_a_imagenes(path, dpi=dpi)
    if path.suffix.lower() in BITMAPS:
        return [path]
    raise ValueError(f"Formato no soportado: {path.suffix}")


# ------------------------------------------------------------- preprocesado
def _deskew(gray: np.ndarray, max_ang: float = 8.0) -> Tuple[np.ndarray, float]:
    """Endereza el escaneo usando la orientacion dominante de las lineas."""
    bordes = cv2.Canny(gray, 50, 150, apertureSize=3)
    lineas = cv2.HoughLinesP(bordes, 1, np.pi / 720, threshold=200,
                             minLineLength=max(80, gray.shape[1] // 12), maxLineGap=12)
    if lineas is None:
        return gray, 0.0
    angs = []
    for x1, y1, x2, y2 in lineas[:, 0]:
        a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        a = (a + 90) % 180 - 90          # -90..90
        if abs(a) < max_ang:             # casi horizontal
            angs.append(a)
        elif abs(abs(a) - 90) < max_ang: # casi vertical
            angs.append(a - np.sign(a) * 90)
    if not angs:
        return gray, 0.0
    ang = float(np.median(angs))
    if abs(ang) < 0.15:
        return gray, 0.0
    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    rot = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_REPLICATE)
    return rot, ang


def _recorta_margenes(gray: np.ndarray, pad: int = 24) -> np.ndarray:
    inv = 255 - gray
    _, bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ys, xs = np.nonzero(bw)
    if len(xs) == 0:
        return gray
    x0, x1 = max(0, xs.min() - pad), min(gray.shape[1], xs.max() + pad)
    y0, y1 = max(0, ys.min() - pad), min(gray.shape[0], ys.max() + pad)
    return gray[y0:y1, x0:x1]


def preprocesar(png: Path, out: Path | None = None, recortar: bool = True,
                max_lado: int = 2400) -> Path:
    """Gris -> deskew -> normaliza iluminacion -> recorta -> redimensiona."""
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise IOError(f"No se pudo leer {png}")

    img, _ang = _deskew(img)

    # fondo del escaneo (manchas, sombras) fuera
    fondo = cv2.morphologyEx(img, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31)))
    img = cv2.divide(img, fondo, scale=255)
    img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)

    if recortar:
        img = _recorta_margenes(img)

    h, w = img.shape
    if max(h, w) > max_lado:
        s = max_lado / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)

    out = Path(out) if out else png.with_name(png.stem + "_prep.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(out), img):
        raise IOError(f"No se pudo escribir {out}")
    return out


def tiles(png: Path, cols: int = 2, filas: int = 1, solape: float = 0.12) -> List[Path]:
    """Parte un plano ancho en mosaicos con solape (para planos largos)."""
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    h, w = img.shape
    tw, th = w // cols, h // filas
    ox, oy = int(tw * solape), int(th * solape)
    salidas = []
    for r in range(filas):
        for c in range(cols):
            x0, y0 = max(0, c * tw - ox), max(0, r * th - oy)
            x1, y1 = min(w, (c + 1) * tw + ox), min(h, (r + 1) * th + oy)
            p = png.with_name(f"{png.stem}_t{r}{c}.png")
            cv2.imwrite(str(p), img[y0:y1, x0:x1])
            salidas.append(p)
    return salidas
