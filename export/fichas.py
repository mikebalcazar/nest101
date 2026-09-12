"""#007 #017 — Fichas de pieza en PDF.

Una ficha por pieza: dibujo a escala, cotas, cantos marcados, material y cantidad.

#017 — dos cambios que pidió Mike:
  · Las fichas van **agrupadas por material**, con una banda de encabezado por
    grupo y sus totales. El que corta trabaja por tablero, no por mueble.
  · La pieza se dibuja **del color de su material**, tomado del mismo catálogo
    que colorea el 3D. De un vistazo se ve en qué tablero va cada pieza.

El cubrecanto se dibuja por FUERA del contorno, no encima: sobre una melamina
madera el naranja encima del relleno se confundiría, y por fuera cae siempre
sobre el papel blanco. Además es donde va físicamente: pegado al canto.
"""
from reportlab.lib.pagesizes import landscape, A3
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.units import mm
from typing import Dict, List, Optional
from core.pieza import Pieza
from core import marca as M
from core import idioma as _IDI            # #085

PW, PH = landscape(A3)
MG = 14 * mm
COLS = 4
BANDA = 21           # alto de la banda de material
SEP = 6

ACC = M.AZUL                         # azul de marca
CANTO = M.CANTO                      # naranja: sólo marca el cubrecanto
TXT = M.TINTA
GRIS = M.GRIS
COLOR_DEFECTO = (0.94, 0.93, 0.91)


# --------------------------------------------------------------------- color
def _rgb(hexa: str):
    """'#B98A52' → (0.72, 0.54, 0.32). Devuelve None si no se puede leer."""
    if not hexa:
        return None
    s = str(hexa).lstrip("#").strip()
    if len(s) != 6:
        return None
    try:
        return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None


def _luz(c):
    """Luminancia percibida, para decidir si el texto encima va claro u oscuro."""
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _oscurecer(c, k=0.55):
    return tuple(v * k for v in c)


def _aclarar(c, k=0.30):
    """Mezcla con blanco: k=0.30 deja un 30 % del color. Para bandas legibles."""
    return tuple(v * k + (1 - k) for v in c)


def _tinta(fondo):
    """Color de texto que se lee sobre ese fondo."""
    return (1, 1, 1) if _luz(fondo) < 0.5 else (0.12, 0.12, 0.13)


# ------------------------------------------------------------------ agrupado
def agrupar(piezas: List[Pieza]):
    """Agrupa por material y espesor, en el orden en que aparecen.

    Se respeta el orden de aparición y no el alfabético: así los códigos siguen
    subiendo dentro de cada grupo y la lista se puede seguir contra el despiece.
    """
    grupos, indice = [], {}
    for p in piezas:
        clave = (p.material, round(p.espesor, 1))
        if clave not in indice:
            indice[clave] = len(grupos)
            grupos.append({"material": p.material, "espesor": p.espesor, "piezas": []})
        grupos[indice[clave]]["piezas"].append(p)
    for g in grupos:
        g["n"] = sum(x.cantidad for x in g["piezas"])
        g["m2"] = sum(x.area_m2 * x.cantidad for x in g["piezas"])
        g["ml"] = sum(x.ml_canto * x.cantidad for x in g["piezas"])
    return grupos


# ----------------------------------------------------------------- dibujado
def _encabezado(c, proyecto, pag, total):
    ancho_marca = M.dibujar(c, MG, PH - MG - 3 * mm, 16)
    c.setFillColorRGB(*TXT)
    c.setFont(M.TXT_B, 13)
    c.drawString(MG + ancho_marca + 10, PH - MG - 3 * mm, f"{proyecto} · {_IDI.t('Fichas de corte')}")
    c.setFont(M.TXT, 8.5)
    c.setFillColorRGB(*GRIS)
    c.drawString(MG, PH - MG - 9.5 * mm,
                 _IDI.t("Medidas de CORTE en mm · el color es el del material ·")
                 + " " + _IDI.t("el trazo naranja por fuera marca dónde va cubrecanto"))
    c.drawRightString(PW - MG, PH - MG - 3 * mm, f"{pag} / {total}")
    c.setStrokeColorRGB(*ACC)
    c.setLineWidth(1.1)
    c.line(MG, PH - MG - 12 * mm, PW - MG, PH - MG - 12 * mm)


def _banda(c, g, color, x0, y, ancho):
    """Encabezado de grupo: muestra de color, material y totales. (#017)"""
    # la banda va en un tinte claro del material: si fuera del color pleno, un
    # tablero blanco daría una banda blanca donde la muestra no se vería
    fondo = _aclarar(color, 0.30)
    c.setFillColorRGB(*fondo)
    c.setStrokeColorRGB(*_oscurecer(color, 0.6))
    c.setLineWidth(0.6)
    c.rect(x0, y, ancho, BANDA, stroke=1, fill=1)

    # muestra del color pleno, con contorno, para poder compararla con el tablero
    c.setFillColorRGB(*color)
    c.setStrokeColorRGB(*_oscurecer(color, 0.4))
    c.setLineWidth(0.7)
    c.rect(x0 + 7, y + 5, 17, BANDA - 10, stroke=1, fill=1)

    tinta = _tinta(fondo)
    c.setFillColorRGB(*tinta)
    c.setFont(M.TXT_B, 10.5)
    c.drawString(x0 + 30, y + 7, f"{g['material']}  ·  {g['espesor']:.0f} mm")
    c.setFont(M.TXT, 8.5)
    partes = [f"{len(g['piezas'])} {_IDI.t('piezas distintas')}",
              f"{g['n']} {_IDI.t('en total')}",
              f"{g['m2']:.2f} m²"]
    if g["ml"] > 0.001:
        partes.append(f"{g['ml']:.2f} {_IDI.t('ml de canto')}")
    c.drawRightString(x0 + ancho - 9, y + 7, "   ·   ".join(partes))


def _ficha(c, p: Pieza, x0, y0, w, h, color):
    """Una ficha dentro del rectángulo (x0, y0, w, h)."""
    c.setStrokeColorRGB(0.82, 0.82, 0.85)
    c.setLineWidth(0.6)
    c.roundRect(x0, y0, w, h, 3, stroke=1, fill=0)

    pad = 7
    # --- encabezado de la ficha ---
    c.setFillColorRGB(*TXT)
    c.setFont(M.TXT_B, 11)
    c.drawString(x0 + pad, y0 + h - 14, p.codigo)
    c.setFont(M.TXT, 8)
    c.drawString(x0 + pad + 34, y0 + h - 14, p.nombre[:34])
    c.setFont(M.TXT_B, 12)
    c.setFillColorRGB(*ACC)
    c.drawRightString(x0 + w - pad, y0 + h - 14, f"×{p.cantidad}")

    # --- zona de dibujo ---
    zx, zy = x0 + pad + 16, y0 + 42
    zw, zh = w - 2 * pad - 26, h - 42 - 26
    esc = min(zw / max(p.largo, 1), zh / max(p.ancho, 1))
    dw, dh = p.largo * esc, p.ancho * esc
    px, py = zx + (zw - dw) / 2, zy + (zh - dh) / 2

    # #017 — la pieza va del color de su material
    c.setFillColorRGB(*color)
    c.setStrokeColorRGB(*_oscurecer(color, 0.5))
    c.setLineWidth(0.8)
    c.rect(px, py, dw, dh, stroke=1, fill=1)

    # --- cantos: (largo_inf, largo_sup, ancho_izq, ancho_der) ---
    # por FUERA del contorno: así el naranja nunca compite con el relleno
    d = 2.0
    c.setStrokeColorRGB(*CANTO)
    c.setLineWidth(2.4)
    c.setLineCap(0)
    bordes = [
        (p.canto[0], (px, py - d), (px + dw, py - d)),                 # inferior
        (p.canto[1], (px, py + dh + d), (px + dw, py + dh + d)),       # superior
        (p.canto[2], (px - d, py), (px - d, py + dh)),                 # izquierdo
        (p.canto[3], (px + dw + d, py), (px + dw + d, py + dh)),       # derecho
    ]
    hay_canto = False
    for esp, a, b in bordes:
        if esp:
            hay_canto = True
            c.line(a[0], a[1], b[0], b[1])

    # --- cotas ---
    c.setStrokeColorRGB(*GRIS)
    c.setLineWidth(0.4)
    c.setFont(M.TXT, 7.5)
    yc = py - 9 - d
    c.line(px, yc, px + dw, yc)
    c.line(px, yc - 2, px, yc + 2)
    c.line(px + dw, yc - 2, px + dw, yc + 2)
    c.setFillColorRGB(*TXT)
    c.setFont(M.TXT_B, 8)
    c.drawCentredString(px + dw / 2, yc - 7.5, f"{p.largo:.1f}")

    xc = px - 9 - d
    c.setStrokeColorRGB(*GRIS)
    c.line(xc, py, xc, py + dh)
    c.line(xc - 2, py, xc + 2, py)
    c.line(xc - 2, py + dh, xc + 2, py + dh)
    c.saveState()
    c.translate(xc - 3, py + dh / 2)
    c.rotate(90)
    c.setFillColorRGB(*TXT)
    c.drawCentredString(0, 0, f"{p.ancho:.1f}")
    c.restoreState()

    # --- pie ---
    # el material se repite aquí aunque la banda del grupo ya lo diga: en el taller
    # estas fichas se recortan, y una ficha suelta sin material no sirve de nada
    c.setFont(M.TXT, 7.5)
    c.setFillColorRGB(*TXT)
    c.drawString(x0 + pad, y0 + 19, f"{p.material}  ·  {p.espesor:.0f} mm")
    c.setFillColorRGB(*GRIS)
    c.setFont(M.TXT, 7)
    lf, af = p.terminado
    corte = f"{_IDI.t('corte')} {p.largo:.1f} × {p.ancho:.1f}"
    fin = f"{_IDI.t('terminado')} {lf:.1f} × {af:.1f}" if (lf != p.largo or af != p.ancho) else ""
    c.drawString(x0 + pad, y0 + 10, corte + ("   ·   " + fin if fin else ""))
    if p.mueble:
        c.drawRightString(x0 + w - pad, y0 + 19, p.mueble[:22])
    if hay_canto:
        c.setFillColorRGB(*CANTO)
        c.drawRightString(x0 + w - pad, y0 + 10, f"{_IDI.t('canto')} {p.ml_canto * p.cantidad:.2f} ml")
    if p.veta:
        c.setFillColorRGB(*_tinta(color))
        c.setFont(M.TXT_I, 6.5)
        c.drawCentredString(px + dw / 2, py + dh / 2 - 2, "veta a lo largo")


# ------------------------------------------------------------------ armado
def _plan(grupos, ancho_util, alto_util, w, h):
    """Reparte bandas y fichas en páginas. Devuelve [[(tipo, dato, x, y), …], …].

    Se calcula antes de dibujar para poder numerar «página 2 de 5» bien, y para
    que ningún grupo empiece con su banda al filo de la hoja.
    """
    paginas, actual = [], []
    y = alto_util                      # cursor desde arriba, relativo a MG
    for g in grupos:
        # una banda sola al final de la hoja no sirve: se pasa de página
        if y - (BANDA + 4 + h) < 0 and actual:
            paginas.append(actual)
            actual, y = [], alto_util
        y -= BANDA
        actual.append(("banda", g, MG, MG + y))
        y -= 8
        col = 0
        for p in g["piezas"]:
            if col == 0:
                if y - h < 0:
                    paginas.append(actual)
                    actual, y = [], alto_util
                y -= h
            actual.append(("ficha", (p, g), MG + col * (w + SEP), MG + y))
            col += 1
            if col == COLS:
                col, y = 0, y - SEP
        if col:
            y -= SEP
        y -= 6                          # aire entre grupos
    if actual:
        paginas.append(actual)
    return paginas


def exportar(piezas: List[Pieza], path: str, proyecto="Proyecto",
             colores: Optional[Dict[str, str]] = None):
    """colores: {nombre de material: '#RRGGBB'}, el mismo catálogo del 3D."""
    colores = colores or {}
    grupos = agrupar(piezas)
    color_de = {g["material"]: (_rgb(colores.get(g["material"])) or COLOR_DEFECTO)
                for g in grupos}

    zona_y = PH - MG - 16 * mm
    ancho_util = PW - 2 * MG
    alto_util = zona_y - MG
    w = (ancho_util - (COLS - 1) * SEP) / COLS
    # tres filas por hoja, con espacio para DOS bandas: así un grupo chico puede
    # empezar en la misma hoja donde terminó el anterior en vez de estrenar una
    h = (alto_util - 2 * BANDA - 24 - 2 * SEP) / 3

    paginas = _plan(grupos, ancho_util, alto_util, w, h)

    # #085 — el lienzo va envuelto: todo lo que se escriba en el plano pasa
    # por el diccionario del idioma del taller.
    c = _IDI.LienzoTraducido(pdfcanvas.Canvas(path, pagesize=(PW, PH)))
    for i, pagina in enumerate(paginas):
        if i:
            c.showPage()
        _encabezado(c, proyecto, i + 1, len(paginas))
        for tipo, dato, x, y in pagina:
            if tipo == "banda":
                _banda(c, dato, color_de[dato["material"]], x, y, ancho_util)
            else:
                p, g = dato
                _ficha(c, p, x, y, w, h, color_de[g["material"]])
    c.showPage()
    c.save()
    return path
