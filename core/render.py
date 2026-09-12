"""Render isométrico con z-buffer real (numpy) → PNG.

Sustituye al painter's algorithm, que da resultados incorrectos cuando piezas
largas tienen centroide lejano pero bordes cercanos (travesaños, entrepaños).
"""
import numpy as np
from PIL import Image
from typing import List, Tuple
from . import iso as ISO


def _rasterizar_tri(zbuf, idbuf, p0, p1, p2, d0, d1, d2, fid):
    """Rasteriza un triángulo con interpolación baricéntrica de profundidad."""
    H, W = zbuf.shape
    minx = max(int(np.floor(min(p0[0], p1[0], p2[0]))), 0)
    maxx = min(int(np.ceil(max(p0[0], p1[0], p2[0]))) + 1, W)
    miny = max(int(np.floor(min(p0[1], p1[1], p2[1]))), 0)
    maxy = min(int(np.ceil(max(p0[1], p1[1], p2[1]))) + 1, H)
    if minx >= maxx or miny >= maxy:
        return
    xs = np.arange(minx, maxx) + 0.5
    ys = np.arange(miny, maxy) + 0.5
    X, Y = np.meshgrid(xs, ys)
    den = ((p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1]))
    if abs(den) < 1e-9:
        return
    w0 = ((p1[1] - p2[1]) * (X - p2[0]) + (p2[0] - p1[0]) * (Y - p2[1])) / den
    w1 = ((p2[1] - p0[1]) * (X - p2[0]) + (p0[0] - p2[0]) * (Y - p2[1])) / den
    w2 = 1.0 - w0 - w1
    dentro = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    if not dentro.any():
        return
    prof = w0 * d0 + w1 * d1 + w2 * d2
    sub_z = zbuf[miny:maxy, minx:maxx]
    sub_i = idbuf[miny:maxy, minx:maxx]
    mask = dentro & (prof > sub_z)
    sub_z[mask] = prof[mask]
    sub_i[mask] = fid


def encuadre(solidos: List[ISO.Solido], ancho_px=2200, margen_px=40):
    """Devuelve (esc, bx0, by0, ancho_px, alto_px) y la función 3D→píxel."""
    pts = [ISO.proyectar(*p) for s in solidos
           for cara, _k in ISO.caras(s) for p in cara]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    esc = (ancho_px - 2 * margen_px) / max(bx1 - bx0, 1e-6)
    alto_px = int((by1 - by0) * esc) + 2 * margen_px

    def a_px(p3):
        px, py = ISO.proyectar(*p3)
        return ((px - bx0) * esc + margen_px,
                alto_px - margen_px - (py - by0) * esc)
    return esc, alto_px, a_px


def render(solidos: List[ISO.Solido], ancho_px=2200, margen_px=40,
           fondo=(255, 255, 255), contorno=(45, 48, 52),
           transparente=False) -> Image.Image:
    # --- recolectar caras visibles ---
    caras = []          # (puntos3d, color)
    for s in solidos:
        base = s.color or ISO.COLOR.get(s.grupo, (0.8, 0.8, 0.8))
        for cara, k in ISO.caras(s):        # las 6 caras (#005)
            col = tuple(int(255 * max(0.0, min(1.0, v * k))) for v in base)
            caras.append((cara, col))
    if not caras:
        return Image.new("RGBA" if transparente else "RGB", (10, 10),
                         (0, 0, 0, 0) if transparente else fondo)

    esc, alto_px, a_px = encuadre(solidos, ancho_px, margen_px)
    zbuf = np.full((alto_px, ancho_px), -1e18, dtype=np.float64)
    idbuf = np.full((alto_px, ancho_px), -1, dtype=np.int32)

    for fid, (cara, _col) in enumerate(caras):
        P = [a_px(p) for p in cara]
        D = [ISO.profundidad(*p) for p in cara]
        _rasterizar_tri(zbuf, idbuf, P[0], P[1], P[2], D[0], D[1], D[2], fid)
        _rasterizar_tri(zbuf, idbuf, P[0], P[2], P[3], D[0], D[2], D[3], fid)

    # --- colorear ---
    paleta = np.array([fondo] + [c for _, c in caras], dtype=np.uint8)
    img = paleta[idbuf + 1]

    # --- contorno: donde cambia el id de cara ---
    borde = np.zeros_like(idbuf, dtype=bool)
    borde[:, 1:] |= idbuf[:, 1:] != idbuf[:, :-1]
    borde[1:, :] |= idbuf[1:, :] != idbuf[:-1, :]
    img[borde] = contorno

    # #025 — con fondo transparente la miniatura sirve igual en tema claro y
    # oscuro. El z-buffer ya dice exactamente dónde hay pieza: idbuf >= 0.
    if transparente:
        rgba = np.zeros((alto_px, ancho_px, 4), dtype=np.uint8)
        rgba[..., :3] = img
        rgba[..., 3] = np.where(idbuf >= 0, 255, 0)
        rgba[borde, 3] = 255            # el contorno también se ve
        return Image.fromarray(rgba, "RGBA")
    return Image.fromarray(img, "RGB")


def render_a_archivo(solidos, path, ancho_px=2200):
    im = render(solidos, ancho_px=ancho_px)
    im.save(path, "PNG")
    return path, im.size


def visibilidad(solidos, ancho_px=1400):
    """Píxeles visibles por sólido. Sirve para verificar que ninguna pieza
    quede totalmente oculta en el explosionado."""
    import numpy as np
    caras, dueno = [], []
    for i, s in enumerate(solidos):
        for cara, _k in ISO.caras(s):
            caras.append(cara)
            dueno.append(i)
    esc, alto_px, a_px = encuadre(solidos, ancho_px, 20)
    zbuf = np.full((alto_px, ancho_px), -1e18)
    idbuf = np.full((alto_px, ancho_px), -1, dtype=np.int32)
    for fid, cara in enumerate(caras):
        P = [a_px(p) for p in cara]
        D = [ISO.profundidad(*p) for p in cara]
        _rasterizar_tri(zbuf, idbuf, P[0], P[1], P[2], D[0], D[1], D[2], fid)
        _rasterizar_tri(zbuf, idbuf, P[0], P[2], P[3], D[0], D[2], D[3], fid)
    out = {}
    for fid in range(len(caras)):
        n = int((idbuf == fid).sum())
        i = dueno[fid]
        out[i] = out.get(i, 0) + n
    return {solidos[i].codigo + "/" + solidos[i].etiqueta: n for i, n in sorted(out.items())}
