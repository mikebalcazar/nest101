"""Exportador XLSX — lista de corte, resumen de material y canto."""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from typing import List
from core.pieza import Pieza
from core import idioma as _IDI            # #085
from core.nesting import Hoja

HDR = PatternFill("solid", fgColor="0080C1")      # azul Taller 101
HDR_F = Font(color="FFFFFF", bold=True, size=10)
B = Border(*[Side(style="thin", color="D1D5DB")] * 4)

# #095 — Las CIFRAS, también en el Excel.
#
# Norma de la suite: los números van en Fira Sans; nunca en Raleway, que trae
# cifras «old style». Aquí no se puede empotrar la fuente —un .xlsx usa las que
# tenga instaladas la máquina que lo abre—, así que se pide Fira Sans por
# nombre. Si el taller no la tiene, Excel sustituye: por eso se deja escrito
# `Calibri` como segunda, que es la de fábrica y también trae cifras alineadas.
# Lo que NO puede pasar es que una celda numérica salga en Raleway.
CIFRA = "Fira Sans"
CIFRA_SI_NO = "Calibri"


def _cifras(wb):
    """Pone Fira Sans en toda celda que sea número o fórmula.

    Va al final y de una pasada, no columna por columna, por la misma razón que
    el lienzo envuelto de los PDF: es el único sitio por donde pasan todas las
    celdas, y la columna que alguien agregue mañana entra sola. Se conserva lo
    que la celda ya tuviera —negrita en los totales, color en los encabezados—:
    sólo se cambia la familia.
    """
    for ws in wb.worksheets:
        for fila in ws.iter_rows():
            for c in fila:
                v = c.value
                es_num = isinstance(v, (int, float)) and not isinstance(v, bool)
                es_form = isinstance(v, str) and v.startswith("=")
                if not (es_num or es_form):
                    continue
                f = c.font
                c.font = Font(name=CIFRA, size=f.size, bold=f.bold,
                              italic=f.italic, color=f.color)


def _hoja(ws, headers, anchos):
    # #085 — los encabezados pasan por el idioma del taller. Es el único lugar
    # donde se escriben, así que basta con éste.
    headers = [_IDI.t(h) for h in headers]
    ws.append(headers)
    for i, (h, a) in enumerate(zip(headers, anchos), start=1):
        c = ws.cell(row=1, column=i)
        c.fill, c.font = HDR, HDR_F
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = a
    ws.freeze_panes = "A2"


def exportar(piezas: List[Pieza], hojas: List[Hoja], path: str, proyecto: str = "Proyecto",
             costeo: List[dict] = None, cubiertas: List = None):
    wb = Workbook()

    # ---- Lista de corte ----
    ws = wb.active
    ws.title = _IDI.t("Lista de corte")
    _hoja(ws, ["Código", "Mueble", "Pieza", "Material", "Esp.", "Largo", "Ancho",
               "Cant.", "Área m² un.", "Área m² tot.", "Canto ML", "Cantos (I/S/Iz/D)", "Nota"],
          [12, 16, 26, 18, 7, 9, 9, 7, 11, 12, 10, 18, 30])
    for p in piezas:
        ws.append([p.codigo, p.mueble, p.nombre, p.material, p.espesor,
                   round(p.largo, 1), round(p.ancho, 1), p.cantidad,
                   round(p.area_m2, 4), round(p.area_m2 * p.cantidad, 4),
                   round(p.ml_canto * p.cantidad, 3),
                   "/".join("X" if c else "-" for c in p.canto), p.nota])
    r = ws.max_row + 1
    ws.cell(r, 7, "TOTAL").font = Font(bold=True)
    ws.cell(r, 8, f"=SUM(H2:H{r-1})").font = Font(bold=True)
    ws.cell(r, 10, f"=SUM(J2:J{r-1})").font = Font(bold=True)
    ws.cell(r, 11, f"=SUM(K2:K{r-1})").font = Font(bold=True)

    # ---- Resumen por material ----
    ws2 = wb.create_sheet(_IDI.t("Resumen material"))
    _hoja(ws2, ["Material", "Espesor", "Piezas", "Área m²", "Hojas requeridas",
                "Aprovech. prom."], [22, 10, 10, 12, 16, 14])
    agg = {}
    for p in piezas:
        k = (p.material, p.espesor)
        a = agg.setdefault(k, [0, 0.0])
        a[0] += p.cantidad
        a[1] += p.area_m2 * p.cantidad
    hojas_mat = {}
    for h in hojas:
        k = (h.material, h.espesor)
        d = hojas_mat.setdefault(k, [0, 0.0])
        d[0] += 1
        d[1] += h.aprovechamiento
    for k, v in agg.items():
        n, ap = hojas_mat.get(k, (0, 0))
        ws2.append([k[0], k[1], v[0], round(v[1], 3), n,
                    f"{(ap/n*100):.1f}%" if n else "-"])

    # ---- Detalle de hojas ----
    ws3 = wb.create_sheet(_IDI.t("Hojas nesting"))
    _hoja(ws3, ["Hoja", "Material", "Esp.", "Dim. hoja", "Piezas", "Aprovech.", "Desperdicio m²"],
          [8, 22, 8, 16, 9, 12, 16])
    for h in hojas:
        desp = (h.ancho * h.alto - h.area_usada) / 1e6
        ws3.append([h.idx, h.material, h.espesor, f"{h.ancho:.0f}x{h.alto:.0f}",
                    len(h.colocaciones), f"{h.aprovechamiento*100:.1f}%", round(desp, 3)])

    # ---- Cantos ----
    ws4 = wb.create_sheet(_IDI.t("Canto"))
    _hoja(ws4, ["Espesor canto", "Material", "ML total"], [16, 22, 12])
    canto = {}
    for p in piezas:
        for c in p.canto:
            if c:
                canto[(c, p.material)] = canto.get((c, p.material), 0) + 0
    tmp = {}
    for p in piezas:
        esp_c = max(p.canto) if any(p.canto) else 0
        if esp_c:
            tmp[(esp_c, p.material)] = tmp.get((esp_c, p.material), 0) + p.ml_canto * p.cantidad
    for (e, m), ml in sorted(tmp.items()):
        ws4.append([f"{e} mm", m, round(ml, 2)])

    # ---- Costeo ----
    if costeo:
        ws5 = wb.create_sheet(_IDI.t("Costeo"))
        _hoja(ws5, ["Material", "Esp.", "Hojas", "$ / hoja", "Costo material",
                    "ML canto", "$ / ML", "Costo canto", "Costo total"],
              [24, 8, 8, 12, 15, 11, 10, 13, 13])
        for r in costeo:
            ws5.append([r["material"], r["espesor"], r["hojas"], r["precio_hoja"],
                        r["costo_material"], r["ml_canto"], r["precio_canto_ml"],
                        r["costo_canto"], r["costo_total"]])
        n = ws5.max_row
        ws5.cell(n + 1, 8, "TOTAL").font = Font(bold=True)
        ws5.cell(n + 1, 9, f"=SUM(I2:I{n})").font = Font(bold=True)
        for row in ws5.iter_rows(min_row=2, max_row=n + 1, min_col=4, max_col=9):
            for cel in row:
                cel.number_format = '"$"#,##0.00'
        for row in ws5.iter_rows(min_row=2, max_row=n, min_col=6, max_col=6):
            for cel in row:
                cel.number_format = "0.00"

    for w in wb.worksheets:
        for row in w.iter_rows(min_row=1, max_row=w.max_row, max_col=w.max_column):
            for c in row:
                c.border = B
    # ---- Cubiertas (#028) ----
    # Van en su propia hoja porque no se piden como los tableros: la piedra y la
    # superficie sólida se cotizan por medida con el marmolista, con sus metros
    # lineales de nariz aparte.
    if cubiertas:
        ws = wb.create_sheet(_IDI.t("Cubiertas"))
        _hoja(ws, ["Tramo", "Material", "Espesor", "Largo", "Fondo", "m²",
                   "Alto nariz", "ML nariz", "ML doblado", "Sobre los muebles", "Nota"],
              [10, 26, 9, 10, 9, 9, 11, 10, 12, 34, 42])
        for i, t in enumerate(cubiertas, start=1):
            etiqueta = f"C{i}" + (f"  ({t.parte}/{t.partes})" if t.partes > 1 else "")
            ws.append([etiqueta, t.material, t.espesor, t.largo, t.fondo,
                       round(t.area_m2, 3), t.alto_nariz, t.ml_nariz,
                       t.ml_doblado or "", ", ".join(t.muebles), t.nota])
        for fila in ws.iter_rows(min_row=1, max_row=ws.max_row):
            for c in fila:
                c.border = B
        ws.append([])
        f0 = ws.max_row + 1
        ws.append([_IDI.t("TOTALES POR MATERIAL")])
        ws.cell(row=f0, column=1).font = Font(bold=True)
        ws.append(["", "Material", "Espesor", "Largo total", "", "m²",
                   "", "ML nariz", "ML doblado"])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
        from core.cubierta import resumen as _res
        for r in _res(cubiertas):
            ws.append(["", r["material"], r["espesor"], r["largo_total"], "",
                       r["m2"], "", r["ml_nariz"], r["ml_doblado"] or ""])

    _cifras(wb)
    wb.save(path)
    return path
