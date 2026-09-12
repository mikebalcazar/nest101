"""Exportador DXF — hojas de nesting + planos de pieza."""
import ezdxf
from ezdxf.enums import TextEntityAlignment
from typing import List
from core.nesting import Hoja
from core.pieza import Pieza

CAPAS = {
    "HOJA":      (8,  "Contorno de hoja"),
    "CORTE":     (1,  "Contorno de corte de pieza"),
    "BARRENO":   (5,  "Barrenos"),
    "RANURA":    (3,  "Ranuras"),
    "TEXTO":     (7,  "Etiquetas"),
    "COTA":      (4,  "Cotas"),
    # #076 — la trayectoria de la sierra: cada línea es un corte de lado a lado.
    "CORTE_1":   (1,  "Sierra: corte de tiras"),
    "CORTE_2":   (2,  "Sierra: trozar la tira"),
    "CORTE_3":   (4,  "Sierra: despunte"),
}


def _doc():
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # mm
    for nombre, (color, desc) in CAPAS.items():
        doc.layers.add(nombre, color=color)
    return doc


def exportar_nesting(hojas: List[Hoja], path: str, sep_hojas: float = 200.0):
    doc = _doc()
    msp = doc.modelspace()
    ox = 0.0
    for h in hojas:
        msp.add_lwpolyline(
            [(ox, 0), (ox + h.ancho, 0), (ox + h.ancho, h.alto), (ox, h.alto)],
            close=True, dxfattribs={"layer": "HOJA"})
        msp.add_text(
            f"HOJA {h.idx} · {h.material} {h.espesor}mm · {h.ancho:.0f}x{h.alto:.0f} · "
            f"aprov {h.aprovechamiento*100:.1f}%",
            height=25, dxfattribs={"layer": "TEXTO"}
        ).set_placement((ox, h.alto + 40), align=TextEntityAlignment.LEFT)

        for c in h.colocaciones:
            x, y, w, hh = ox + c.x, c.y, c.w, c.h
            msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + hh), (x, y + hh)],
                               close=True, dxfattribs={"layer": "CORTE"})
            p = c.pieza
            etq = f"{p.codigo} {p.nombre}"
            msp.add_text(etq, height=min(18, hh / 4),
                         dxfattribs={"layer": "TEXTO"}).set_placement(
                (x + w / 2, y + hh / 2 + 10), align=TextEntityAlignment.MIDDLE_CENTER)
            msp.add_text(f"{p.largo:.0f} x {p.ancho:.0f}" + (" (R)" if c.rotada else ""),
                         height=min(14, hh / 5),
                         dxfattribs={"layer": "TEXTO"}).set_placement(
                (x + w / 2, y + hh / 2 - 14), align=TextEntityAlignment.MIDDLE_CENTER)
            _ops(msp, p, x, y, c.rotada, w, hh)
        ox += h.ancho + sep_hojas
    doc.saveas(path)
    return path


def _ops(msp, p: Pieza, x0, y0, rotada, w, h):
    """Dibuja barrenos y ranuras dentro del rectángulo colocado."""
    def T(px, py):
        return (x0 + (py if rotada else px), y0 + (px if rotada else py))
    for b in p.barrenos:
        if b.cara != "A":
            continue
        cx, cy = T(b.x, b.y)
        msp.add_circle((cx, cy), b.dia / 2, dxfattribs={"layer": "BARRENO"})
    for r in p.ranuras:
        a, bb = T(r.x1, r.y1), T(r.x2, r.y2)
        msp.add_line(a, bb, dxfattribs={"layer": "RANURA"})


def exportar_piezas_detalle(piezas: List[Pieza], path: str, cols: int = 4, sep: float = 120.0):
    """Un plano por pieza única, en malla, con cotas y operaciones."""
    doc = _doc()
    msp = doc.modelspace()
    ancho_col = max(p.largo for p in piezas) + sep
    alto_fila = max(p.ancho for p in piezas) + sep + 80
    for i, p in enumerate(piezas):
        cx = (i % cols) * ancho_col
        cy = -(i // cols) * alto_fila
        msp.add_lwpolyline([(cx, cy), (cx + p.largo, cy), (cx + p.largo, cy + p.ancho),
                            (cx, cy + p.ancho)], close=True, dxfattribs={"layer": "CORTE"})
        _ops(msp, p, cx, cy, False, p.largo, p.ancho)
        msp.add_text(f"{p.codigo} · {p.nombre} · x{p.cantidad}", height=18,
                     dxfattribs={"layer": "TEXTO"}).set_placement(
            (cx, cy + p.ancho + 45), align=TextEntityAlignment.LEFT)
        msp.add_text(f"{p.largo:.1f} x {p.ancho:.1f} x {p.espesor:.1f} · {p.material}",
                     height=14, dxfattribs={"layer": "TEXTO"}).set_placement(
            (cx, cy + p.ancho + 20), align=TextEntityAlignment.LEFT)
        # cotas
        dim = msp.add_linear_dim(base=(cx, cy - 30), p1=(cx, cy), p2=(cx + p.largo, cy),
                                 dxfattribs={"layer": "COTA"})
        dim.render()
        dim2 = msp.add_linear_dim(base=(cx - 30, cy), p1=(cx, cy), p2=(cx, cy + p.ancho),
                                  angle=90, dxfattribs={"layer": "COTA"})
        dim2.render()
    doc.saveas(path)
    return path


# #072 — aquí vivía `exportar_iso()`: un DXF con los isométricos armado y
# explosionado de cada gabinete. Mike lo quitó: «no exportes isométricos DXF.
# En ningún momento. Ya con la vista isométrica del plano PDF es suficiente.»
#
# Tenía razón: un isométrico en DXF no se corta ni se arma —es un dibujo, no
# una trayectoria— y el PDF de planos ya trae esa vista en cada gabinete. Se
# borra la función entera y no sólo la llamada, para que no vuelva sola.
#
# Lo que sí falta y no lo tapa el PDF es poder GIRAR el mueble en el celular
# en obra. Eso no es un DXF: es un archivo 3D (ver el backlog).


def exportar_sierra(hojas: List[Hoja], path: str, sep_hojas: float = 200.0):
    """#076 — el mismo acomodo, pero dibujando LA TRAYECTORIA DE LA SIERRA.

    En el archivo de fresa lo que importa es el contorno de cada pieza: la fresa
    lo recorre. En el de sierra lo que importa son **los cortes**, que atraviesan
    el tablero de lado a lado y van numerados en el orden en que se hacen. Cada
    etapa en su capa, para poder apagarlas y ver una a la vez:

        CORTE_1  saca las tiras          CORTE_2  trocea cada tira
        CORTE_3  despunta lo que sobra de alto dentro de la tira

    Los barrenos y las ranuras NO se dibujan aquí: una sierra no los hace. Van
    en el archivo de fresa, que es la máquina que sí los puede hacer.
    """
    doc = _doc()
    msp = doc.modelspace()
    ox = 0.0
    for h in hojas:
        msp.add_lwpolyline(
            [(ox, 0), (ox + h.ancho, 0), (ox + h.ancho, h.alto), (ox, h.alto)],
            close=True, dxfattribs={"layer": "HOJA"})
        msp.add_text(
            f"HOJA {h.idx} · {h.material} {h.espesor}mm · {h.ancho:.0f}x{h.alto:.0f} · "
            f"aprov {h.aprovechamiento*100:.1f}% · {len(h.cortes)} cortes",
            height=25, dxfattribs={"layer": "TEXTO"}
        ).set_placement((ox, h.alto + 40), align=TextEntityAlignment.LEFT)

        for c in h.colocaciones:
            x, y, w, hh = ox + c.x, c.y, c.w, c.h
            msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + hh), (x, y + hh)],
                               close=True, dxfattribs={"layer": "CORTE"})
            p = c.pieza
            msp.add_text(f"{p.codigo} {p.nombre}", height=min(18, hh / 4),
                         dxfattribs={"layer": "TEXTO"}).set_placement(
                (x + w / 2, y + hh / 2 + 10), align=TextEntityAlignment.MIDDLE_CENTER)
            msp.add_text(f"{p.largo:.0f} x {p.ancho:.0f}" + (" (R)" if c.rotada else ""),
                         height=min(14, hh / 5),
                         dxfattribs={"layer": "TEXTO"}).set_placement(
                (x + w / 2, y + hh / 2 - 14), align=TextEntityAlignment.MIDDLE_CENTER)

        for k in h.cortes:
            capa = f"CORTE_{k.etapa}"
            if k.eje == "y":
                a, b = (ox + k.desde, k.pos), (ox + k.hasta, k.pos)
            else:
                a, b = (ox + k.pos, k.desde), (ox + k.pos, k.hasta)
            msp.add_line(a, b, dxfattribs={"layer": capa})
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            msp.add_text(str(k.n), height=16, dxfattribs={"layer": capa}).set_placement(
                (mx, my + 6), align=TextEntityAlignment.MIDDLE_CENTER)
        ox += h.ancho + sep_hojas
    doc.saveas(path)
    return path
