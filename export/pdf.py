"""Exportador PDF — carátula, vistas del gabinete y hojas de nesting a escala."""
from reportlab.lib.pagesizes import landscape, A3
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.units import mm
from typing import List
from core.nesting import Hoja
from core.modelos import Gabinete
from core.config import Estandar
from core import iso as ISO
from core import marca as M
from core import idioma as _IDI            # #085

PW, PH = landscape(A3)
MG = 15 * mm


def _titulo(c, t, sub=""):
    x = MG + M.dibujar(c, MG, PH - MG - 4 * mm, 19) + 11
    c.setFillColorRGB(0.1, 0.12, 0.15)
    c.setFont(M.TXT_B, 15)
    c.drawString(x, PH - MG - 4 * mm, t)
    if sub:
        c.setFont(M.TXT, 9)
        c.setFillColorRGB(0.4, 0.42, 0.45)
        c.drawString(MG, PH - MG - 11 * mm, sub)
    c.setStrokeColorRGB(*M.AZUL)
    c.setLineWidth(1.1)
    c.line(MG, PH - MG - 14 * mm, PW - MG, PH - MG - 14 * mm)
    c.setFillColorRGB(0, 0, 0)


def _vistas_gabinete(c, g: Gabinete, std: Estandar, x0, y0, esc):
    """Dibuja frente, lateral y planta esquemáticos."""
    from core.modelos import alturas
    e = std.mat_cuerpo.espesor
    total, hc, hz = alturas(g, std)       # #001
    S = lambda v: v * esc

    c.setFont(M.TXT_B, 8)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    c.setLineWidth(0.8)
    # ---- FRENTE ----
    c.drawString(x0, y0 + S(g.alto) + 6, f"{_IDI.t('FRENTE')}  {g.ancho:.0f} x {g.alto:.0f}")
    c.rect(x0, y0, S(g.ancho), S(g.alto))
    if hz:
        c.setLineWidth(0.4)
        c.rect(x0, y0, S(g.ancho), S(hz))
    # divisiones de frentes
    from core.modelos import _repartir_frentes
    yy = y0 + S(g.alto)
    c.setLineWidth(0.4)
    for m in _repartir_frentes(g, hc, std):
        yy -= S(m["alto_mod"])
        c.line(x0, yy, x0 + S(g.ancho), yy)
        f = m["frente"]
        if f.tipo == "puerta" and f.n > 1:
            for k in range(1, f.n):
                xx = x0 + S(g.ancho * k / f.n)
                c.line(xx, yy, xx, yy + S(m["alto_mod"]))
        c.setFont(M.TXT, 6)
        c.drawString(x0 + 3, yy + 4, f"{_IDI.t(f.tipo)} {m['alto_frente']:.0f}")
        c.setFont(M.TXT_B, 8)

    # ---- LATERAL ----
    xl = x0 + S(g.ancho) + 25 * mm
    c.drawString(xl, y0 + S(g.alto) + 6, f"{_IDI.t('LATERAL')}  {g.prof:.0f} x {g.alto:.0f}")
    c.setLineWidth(0.8)
    c.rect(xl, y0, S(g.prof), S(g.alto))
    c.setLineWidth(0.4)
    c.rect(xl + S(std.mat_frente.espesor), y0 + S(hz), S(g.prof - std.mat_frente.espesor), S(hc))
    # entrepaños
    if g.n_entrepanos:
        for i in range(1, g.n_entrepanos + 1):
            yy = y0 + S(hz) + S(hc * i / (g.n_entrepanos + 1))
            c.line(xl + S(std.mat_frente.espesor), yy, xl + S(g.prof), yy)

    # ---- PLANTA ----
    xp = xl + S(g.prof) + 25 * mm
    c.setFont(M.TXT_B, 8)
    c.drawString(xp, y0 + S(g.prof) + 6, f"{_IDI.t('PLANTA')}  {g.ancho:.0f} x {g.prof:.0f}")
    c.setLineWidth(0.8)
    c.rect(xp, y0, S(g.ancho), S(g.prof))
    c.setLineWidth(0.4)
    c.rect(xp, y0, S(e), S(g.prof))
    c.rect(xp + S(g.ancho - e), y0, S(e), S(g.prof))


def _iso_en_pagina(c, solidos, x_pt, y_pt, w_pt, h_pt, tmpdir, nombre,
                   etiquetas=False, ancho_px=2400):
    """Renderiza el isométrico con z-buffer y lo coloca en la página.
    Devuelve la función 3D -> coordenadas de página (para globos y cotas)."""
    import os
    from core import render as R
    im = R.render(solidos, ancho_px=ancho_px)
    esc, alto_px, a_px = R.encuadre(solidos, ancho_px=ancho_px)
    ruta = os.path.join(tmpdir, nombre)
    im.save(ruta, "PNG")

    k = min(w_pt / im.size[0], h_pt / im.size[1])
    dw, dh = im.size[0] * k, im.size[1] * k
    ox = x_pt + (w_pt - dw) / 2
    oy = y_pt + (h_pt - dh) / 2
    c.drawImage(ruta, ox, oy, width=dw, height=dh, mask=None)

    def a_pagina(p3):
        px, py = a_px(p3)
        return (ox + px * k, oy + dh - py * k)
    return a_pagina


def _globos(c, solidos, a_pagina, g, r=7.0, salida=16.0):
    """Globo de referencia con línea guía, desplazado en la dirección de explosión."""
    for s in solidos:
        cx, cy = a_pagina(s.centro)
        v = ISO.EXPLOSION.get(s.grupo, (0, 0, 0))
        d = max(g.ancho, g.alto, g.prof) * 0.12
        bx, by = a_pagina((s.centro[0] + v[0] * d,
                           s.centro[1] + v[1] * d,
                           s.centro[2] + v[2] * d))
        n = ((bx - cx) ** 2 + (by - cy) ** 2) ** 0.5 or 1.0
        ux, uy = (bx - cx) / n, (by - cy) / n
        gx, gy = cx + ux * salida, cy + uy * salida
        c.setStrokeColorRGB(0.25, 0.25, 0.25)
        c.setLineWidth(0.4)
        c.line(cx, cy, gx - ux * r, gy - uy * r)
        c.setFillColorRGB(1, 1, 1)
        c.circle(gx, gy, r, stroke=0, fill=1)
        c.setStrokeColorRGB(0.15, 0.15, 0.15)
        c.setLineWidth(0.6)
        c.circle(gx, gy, r, stroke=1, fill=0)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(M.TXT_B, 5.4)
        c.drawCentredString(gx, gy - 1.9, s.codigo[:4])


def _pagina_cocina(c, proyecto_obj, proyecto: str, tmpdir: str):
    """#010 — isométrico de la cocina completa con globos de identificación."""
    gabs = proyecto_obj.gabinetes
    if not gabs:
        return
    # #068 — los globos se numeran por ORDEN DE INSTALACIÓN, no por el orden en
    # que se capturaron los muebles. Antes el globo 1 podía ser el de en medio.
    from core.modelos import orden_instalacion
    sol, ancla = [], []
    for i, k in enumerate(orden_instalacion(gabs), start=1):
        g = gabs[k]
        std = proyecto_obj.estandar_de(g)
        s = ISO.colocar(ISO.solidos_gabinete(g, std), g, std)
        sol += s
        xs = [q.x for q in s] + [q.x + q.dx for q in s]
        ys = [q.y for q in s] + [q.y + q.dy for q in s]
        zs = [q.z + q.dz for q in s]
        ancla.append((i, g, k, ((min(xs) + max(xs)) / 2,
                                (min(ys) + max(ys)) / 2, max(zs))))

    _titulo(c, f"{proyecto} — {_IDI.t('ISOMÉTRICO DE LA COCINA')}",
            f"{len(gabs)} {_IDI.t('gabinetes')} · "
            f"{sum(max(1, g.cantidad) for g in gabs)} {_IDI.t('piezas de mobiliario')}")
    leyenda_w = 66 * mm
    disp_w = PW - 2 * MG - leyenda_w
    disp_h = PH - 2 * MG - 26 * mm
    a_pag = _iso_en_pagina(c, sol, MG, MG, disp_w, disp_h, tmpdir, "iso_cocina.png",
                           ancho_px=2800)

    # globos sobre cada gabinete
    for i, g, _k, pt in ancla:
        px, py = a_pag(pt)
        py += 13
        c.setStrokeColorRGB(0.2, 0.2, 0.2)
        c.setLineWidth(0.5)
        c.line(px, py - 9, px, py - 3)
        c.setFillColorRGB(*M.AZUL)
        c.circle(px, py + 3, 8.5, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(M.TXT_B, 9)
        c.drawCentredString(px, py + 0.2, str(i))

    # tabla de referencia
    lx = PW - MG - leyenda_w + 4 * mm
    ly = PH - MG - 24 * mm
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont(M.TXT_B, 8)
    c.drawString(lx, ly, "GABINETES")
    ly -= 12
    for i, g, k, _pt in ancla:
        c.setFillColorRGB(*M.AZUL)
        c.circle(lx + 5, ly + 2.5, 6, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(M.TXT_B, 7)
        c.drawCentredString(lx + 5, ly + 0.3, str(i))
        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.setFont(M.TXT, 7)
        c.drawString(lx + 15, ly, g.nombre[:26] + (f"  ×{g.cantidad}" if g.cantidad > 1 else ""))
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont(M.TXT, 6.5)
        c.drawString(lx + 15, ly - 7.5,
                     f"{g.ancho:.0f}×{g.alto:.0f}×{g.prof:.0f}"
                     + (f"  ·  {_IDI.t('giro')} {g.rot}°" if g.rot else "")
                     + f"  ·  {_IDI.t('piezas')} {k + 1}.xx")
        ly -= 17
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont(M.TXT, 7)
    c.drawString(MG, MG - 4, "Isométrico verdadero (30°) · z-buffer · medidas en mm")
    c.setFillColorRGB(0, 0, 0)
    c.showPage()


def _pagina_iso(c, g: Gabinete, std: Estandar, proyecto: str, tmpdir: str):
    import re
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", g.nombre)
    sol = ISO.solidos_gabinete(g, std)

    # ---------- ARMADO ----------
    _titulo(c, f"{proyecto} · {g.nombre} — {_IDI.t('ISOMÉTRICO ARMADO')}",
            f"{g.ancho:.0f} x {g.alto:.0f} x {g.prof:.0f} mm · "
            f"{_IDI.t('vista desde frente-izquierda-superior')}")
    disp_w, disp_h = PW - 2 * MG, PH - 2 * MG - 26 * mm
    _iso_en_pagina(c, sol, MG, MG, disp_w, disp_h, tmpdir, f"iso_{slug}_arm.png")
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont(M.TXT, 7)
    c.drawString(MG, MG - 4, "Isométrico verdadero (30°) · z-buffer · medidas en mm")
    c.setFillColorRGB(0, 0, 0)
    c.showPage()

    # ---------- EXPLOSIONADO ----------
    exp = ISO.explotar(sol, 0.32, g)
    _titulo(c, f"{proyecto} · {g.nombre} — {_IDI.t('DESPIECE EXPLOSIONADO')}",
            f"{_IDI.t('Secuencia de armado')} · {_IDI.t('ensamble')} {std.ensamble} · "
            f"{len(sol)} {_IDI.t('componentes')}")
    leyenda_w = 62 * mm
    disp_w2 = PW - 2 * MG - leyenda_w
    a_pag = _iso_en_pagina(c, exp, MG, MG, disp_w2, disp_h, tmpdir,
                           f"iso_{slug}_exp.png", ancho_px=2600)
    _globos(c, exp, a_pag, g)

    # leyenda
    lx = PW - MG - leyenda_w + 4 * mm
    ly = PH - MG - 24 * mm
    c.setFont(M.TXT_B, 8)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(lx, ly, "COMPONENTES")
    ly -= 11
    c.setFont(M.TXT, 6.5)
    filas, orden_f = {}, []
    for s in sol:
        k = (s.codigo, round(s.dx), round(s.dy), round(s.dz))
        if k not in filas:
            filas[k] = [s, 0]
            orden_f.append(k)
        filas[k][1] += 1
    for k in orden_f:
        s, n = filas[k]
        col = ISO.COLOR.get(s.grupo, (0.8, 0.8, 0.8))
        c.setFillColorRGB(*col)
        c.rect(lx, ly - 1.5, 7, 6, stroke=0, fill=1)
        c.setFillColorRGB(0.15, 0.15, 0.15)
        etq = s.etiqueta.rsplit(" ", 1)[0] if n > 1 else s.etiqueta
        c.drawString(lx + 11, ly, f"{s.codigo}  {etq}" + (f"  (x{n})" if n > 1 else ""))
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawRightString(PW - MG - 2 * mm, ly, f"{s.dx:.0f}·{s.dy:.0f}·{s.dz:.0f}")
        ly -= 9.5
    c.setFillColorRGB(0, 0, 0)

    # orden de armado
    ly -= 8
    c.setFont(M.TXT_B, 8)
    c.drawString(lx, ly, "ORDEN DE ARMADO")
    ly -= 11
    tiene_cajon = any(f.tipo == "cajon" for f in g.frentes)
    tiene_puerta = any(f.tipo == "puerta" for f in g.frentes)
    tapa_full = g.tapa_completa if g.tapa_completa is not None else (g.tipo == "aereo")
    pasos = ["Barrenar costados (sistema 32)",
             f"Piso a costados ({std.ensamble} + tarugo)",
             "Tapa superior" if tapa_full else "Travesaños superiores",
             "Escuadrar y colocar respaldo en ranura"]
    if tiene_cajon:
        pasos += ["Correderas a costados", "Armar cajas de cajón"]
    if tiene_puerta:
        pasos += ["Bisagras y ajuste de puertas"]
    if tiene_cajon:
        pasos += ["Frentes de cajón (holgura 3 mm)"]
    if g.n_entrepanos:
        pasos += ["Entrepaños regulables"]
    if g.tipo == "base" and g.con_zoclo:
        pasos += ["Patas niveladoras y zoclo"]
    else:
        pasos += ["Colgadores / riel de fijación a muro"]
    c.setFont(M.TXT, 6.5)
    for i, p in enumerate(pasos, 1):
        c.drawString(lx, ly, f"{i}. {p}")
        ly -= 9
    c.showPage()


def _paginas_mueble(c, gabinetes: List[Gabinete], std: Estandar, proyecto: str,
                    tmpdir: str, proyecto_obj=None, orden=""):
    """Las páginas de UN mueble: la cocina completa y luego gabinete por gabinete.

    #071 — el orden de estas páginas es el orden de la lista, y nada más. Por eso
    cada página lleva escrito **cuál gabinete es y de cuántos** (`orden`): si un
    PDF llega revuelto o incompleto, en obra se ve en el encabezado en vez de
    descubrirlo armando.
    """
    if proyecto_obj is not None and len(gabinetes) > 0:
        _pagina_cocina(c, proyecto_obj, proyecto, tmpdir)

    # #068 — en el orden en que se instalan, de izquierda a derecha vistos de
    # frente, y NO en el orden en que se capturaron. El código de sus piezas
    # (`k+1.xx`) va escrito en la página: es lo que amarra el plano con la lista
    # de corte, que sí va por número de captura.
    from core.modelos import orden_instalacion
    idx = orden_instalacion(gabinetes)
    n = len(idx)
    for i, k in enumerate(idx, start=1):
        g = gabinetes[k]
        pos = (f"{orden}{_IDI.t('gabinete')} {i} {_IDI.t('de')} {n} · "
               f"{_IDI.t('piezas')} {k + 1}.xx · " if n else orden)
        _titulo(c, f"{proyecto} · {g.nombre}",
                f"{pos}{_IDI.t(g.tipo).upper()} · "
                f"{g.ancho:.0f} x {g.alto:.0f} x {g.prof:.0f} mm · "
                f"{_IDI.t('cant.')} {g.cantidad} · {_IDI.t('ensamble')} {std.ensamble}")
        disp_w = PW - 2 * MG - 50 * mm          # descuenta las 2 separaciones entre vistas
        disp_h = PH - 2 * MG - 32 * mm
        esc = min(disp_h / max(g.alto, g.prof), disp_w / (2 * g.ancho + g.prof))
        y_base = MG + 12 * mm + (disp_h - max(g.alto, g.prof) * esc) / 2
        _vistas_gabinete(c, g, std, MG, y_base, esc)
        c.setFont(M.TXT, 7)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(MG, MG, f"{_IDI.t('Escala aprox')} 1:{1/esc*(1/mm)*10:.0f} · {_IDI.t('medidas en mm')}")
        c.setFillColorRGB(0, 0, 0)
        c.showPage()
        _pagina_iso(c, g, std, proyecto, tmpdir)


def exportar_proyecto(muebles, hojas: List[Hoja], path: str, proyecto="Proyecto"):
    """#071 — TODOS los muebles del proyecto en un solo PDF, en su orden.

    Mike lo pidió así, en un archivo: en instalación se arma con el PDF en la
    mano, y repartido en varios archivos el orden se pierde entre carpetas.

    `muebles` es la lista de `Proyecto`, una por pestaña, tal como están en el
    proyecto. Cada uno conserva **su propio estándar**: las medidas de sus
    páginas se calculan con el suyo, no con el del primero.

    Las hojas de nesting van al final y son las del proyecto entero, una sola
    vez — que es la razón de despiezar junto.
    """
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="despz_")
    # #085 — el lienzo va envuelto: todo lo que se escriba en el plano pasa
    # por el diccionario del idioma del taller.
    c = _IDI.LienzoTraducido(pdfcanvas.Canvas(path, pagesize=(PW, PH)))
    total = len(muebles)
    for j, pr_m in enumerate(muebles, start=1):
        etiqueta = f"{proyecto} · {pr_m.nombre}" if total > 1 else proyecto
        _paginas_mueble(c, pr_m.gabinetes, pr_m.estandar, etiqueta, tmpdir, pr_m,
                        orden=(f"mueble {j} de {total} · " if total > 1 else ""))
    # #076 — las hojas de nesting salieron de aquí: van en corte_fresa.pdf y
    # corte_sierra.pdf, uno por máquina. Este archivo es el del que ARMA.
    c.save()
    shutil.rmtree(tmpdir, ignore_errors=True)
    return path


def exportar(gabinetes: List[Gabinete], hojas: List[Hoja], std: Estandar,
             path: str, proyecto="Proyecto", proyecto_obj=None):
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="despz_")
    # #085 — el lienzo va envuelto: todo lo que se escriba en el plano pasa
    # por el diccionario del idioma del taller.
    c = _IDI.LienzoTraducido(pdfcanvas.Canvas(path, pagesize=(PW, PH)))
    _paginas_mueble(c, gabinetes, std, proyecto, tmpdir, proyecto_obj)
    c.save()
    shutil.rmtree(tmpdir, ignore_errors=True)
    return path


def _paginas_hojas(c, hojas: List[Hoja]):
    for h in hojas:
        _titulo(c, f"Hoja {h.idx} · {h.material}",
                f"{h.ancho:.0f} x {h.alto:.0f} x {h.espesor:.0f} mm · "
                f"aprovechamiento {h.aprovechamiento*100:.1f}% · {len(h.colocaciones)} piezas")
        esc = min((PW - 2 * MG) / h.ancho, (PH - 2 * MG - 25 * mm) / h.alto)
        x0 = MG + ((PW - 2 * MG) - h.ancho * esc) / 2
        y0 = MG + ((PH - 2 * MG - 25 * mm) - h.alto * esc) / 2
        S = lambda v: v * esc
        c.setLineWidth(1)
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.rect(x0, y0, S(h.ancho), S(h.alto))
        for col in h.colocaciones:
            c.setStrokeColorRGB(0.75, 0.15, 0.15)
            c.setLineWidth(0.6)
            c.rect(x0 + S(col.x), y0 + S(col.y), S(col.w), S(col.h))
            p = col.pieza
            c.setFillColorRGB(0.15, 0.15, 0.15)
            fs = max(4, min(8, S(col.h) / 5))
            c.setFont(M.TXT_B, fs)
            c.drawCentredString(x0 + S(col.x + col.w / 2), y0 + S(col.y + col.h / 2) + 2,
                                p.codigo)
            c.setFont(M.TXT, fs - 0.5)
            c.drawCentredString(x0 + S(col.x + col.w / 2), y0 + S(col.y + col.h / 2) - fs,
                                f"{p.largo:.0f}x{p.ancho:.0f}" + (" R" if col.rotada else ""))
        c.showPage()


# =====================================================================
# #076 — un PDF por máquina, porque son dos cortes distintos
# =====================================================================

def exportar_hojas(hojas: List[Hoja], path: str, proyecto="Proyecto",
                   titulo="CORTE EN FRESA / ROUTER"):
    """Las hojas de nesting solas, sin los planos de los muebles.

    Hasta la 0.12.0 iban dentro de `planos.pdf`, mezcladas con las páginas de
    armado. Son dos lectores distintos: el instalador usa los planos y el
    cortador usa las hojas, y cada uno tenía que buscar lo suyo entre lo del
    otro. Y desde #076 hay dos cortes distintos, así que ya no cabían.
    """
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="despz_")
    # #085 — el lienzo va envuelto: todo lo que se escriba en el plano pasa
    # por el diccionario del idioma del taller.
    c = _IDI.LienzoTraducido(pdfcanvas.Canvas(path, pagesize=(PW, PH)))
    _portada_corte(c, hojas, proyecto, titulo)
    _paginas_hojas(c, hojas)
    c.save()
    shutil.rmtree(tmpdir, ignore_errors=True)
    return path


def _portada_corte(c, hojas, proyecto, titulo):
    """Cuántas hojas de cada material, para pedir el material antes de cortar."""
    _titulo(c, f"{proyecto} — {titulo}",
            f"{len(hojas)} hojas · aprovechamiento medio "
            f"{(sum(h.aprovechamiento for h in hojas) / len(hojas) * 100) if hojas else 0:.1f}%")
    porm = {}
    for h in hojas:
        k = (h.material, h.espesor, h.ancho, h.alto)
        porm[k] = porm.get(k, 0) + 1
    y = PH - MG - 26 * mm
    c.setFont(M.TXT_B, 9)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(MG, y, "MATERIAL A PEDIR")
    y -= 16
    for (mat, esp, an, al), n in sorted(porm.items(), key=lambda kv: -kv[1]):
        c.setFont(M.TXT_B, 10)
        c.drawString(MG, y, f"{n}")
        c.setFont(M.TXT, 9)
        c.drawString(MG + 22, y, f"hoja(s) de {mat}  ·  {an:.0f} × {al:.0f} × {esp:.0f} mm")
        y -= 15
    y -= 10
    c.setFont(M.TXT_B, 9)
    c.drawString(MG, y, "HOJAS")
    y -= 16
    for h in hojas:
        c.setFont(M.TXT, 8.5)
        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.drawString(MG, y, f"Hoja {h.idx}")
        c.drawString(MG + 46, y, h.material)
        c.drawString(MG + 200, y, f"{len(h.colocaciones)} piezas")
        c.drawString(MG + 265, y, f"aprov {h.aprovechamiento*100:.1f}%")
        if h.cortes:
            c.drawString(MG + 340, y, f"{len(h.cortes)} cortes · {len(h.tiras)} tiras")
        y -= 13
        if y < MG + 20:
            break
    c.setFillColorRGB(0, 0, 0)
    c.showPage()


def exportar_sierra(hojas: List[Hoja], path: str, proyecto="Proyecto"):
    """#076 — el plan de corte de la sierra lineal, con la secuencia escrita.

    Una sierra no recorre contornos: hace cortes que atraviesan el tablero. Lo
    que el operador necesita no es el dibujo de las piezas, es **en qué orden
    corta y en qué medida para cada corte**. Por eso cada hoja lleva su tabla:
    número de corte, a cuánto, y qué sale de ahí.
    """
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="despz_")
    # #085 — el lienzo va envuelto: todo lo que se escriba en el plano pasa
    # por el diccionario del idioma del taller.
    c = _IDI.LienzoTraducido(pdfcanvas.Canvas(path, pagesize=(PW, PH)))
    _portada_corte(c, hojas, proyecto, "CORTE EN SIERRA LINEAL")
    for h in hojas:
        _pagina_sierra(c, h)
    c.save()
    shutil.rmtree(tmpdir, ignore_errors=True)
    return path


ETAPA = {1: ("1", "saca la tira", (0.75, 0.15, 0.15)),
         2: ("2", "trozar la tira", (0.10, 0.35, 0.70)),
         3: ("3", "despunte", (0.55, 0.45, 0.10))}


def _pagina_sierra(c, h: Hoja):
    _titulo(c, f"Hoja {h.idx} · {h.material}",
            f"{h.ancho:.0f} x {h.alto:.0f} x {h.espesor:.0f} mm · "
            f"aprovechamiento {h.aprovechamiento*100:.1f}% · "
            f"{len(h.tiras)} tiras · {len(h.cortes)} cortes")
    tabla_w = 74 * mm
    disp_w = PW - 2 * MG - tabla_w
    disp_h = PH - 2 * MG - 25 * mm
    esc = min(disp_w / h.ancho, disp_h / h.alto)
    x0 = MG
    y0 = MG + (disp_h - h.alto * esc) / 2
    S = lambda v: v * esc

    c.setLineWidth(1)
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.rect(x0, y0, S(h.ancho), S(h.alto))
    # las piezas, en gris: aquí el protagonista es el corte
    for col in h.colocaciones:
        c.setStrokeColorRGB(0.72, 0.72, 0.72)
        c.setLineWidth(0.4)
        c.rect(x0 + S(col.x), y0 + S(col.y), S(col.w), S(col.h))
        p = col.pieza
        fs = max(4, min(8, S(col.h) / 5))
        c.setFillColorRGB(0.25, 0.25, 0.25)
        c.setFont(M.TXT_B, fs)
        c.drawCentredString(x0 + S(col.x + col.w / 2), y0 + S(col.y + col.h / 2) + 2,
                            p.codigo)
        c.setFont(M.TXT, fs - 0.5)
        c.drawCentredString(x0 + S(col.x + col.w / 2), y0 + S(col.y + col.h / 2) - fs,
                            f"{p.largo:.0f}x{p.ancho:.0f}" + (" R" if col.rotada else ""))
    # y encima, los cortes numerados
    for k in h.cortes:
        _et, _n, rgb = ETAPA.get(k.etapa, ("", "", (0, 0, 0)))
        c.setStrokeColorRGB(*rgb)
        c.setLineWidth(1.6 if k.etapa == 1 else 0.9)
        if k.eje == "y":
            a = (x0 + S(k.desde), y0 + S(k.pos))
            b = (x0 + S(k.hasta), y0 + S(k.pos))
        else:
            a = (x0 + S(k.pos), y0 + S(k.desde))
            b = (x0 + S(k.pos), y0 + S(k.hasta))
        c.line(a[0], a[1], b[0], b[1])
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        c.setFillColorRGB(*rgb)
        c.circle(mx, my, 5.2, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(M.TXT_B, 5.6)
        c.drawCentredString(mx, my - 1.9, str(k.n))

    # tabla de la secuencia
    lx = PW - MG - tabla_w + 3 * mm
    ly = PH - MG - 24 * mm
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont(M.TXT_B, 8)
    c.drawString(lx, ly, "SECUENCIA DE CORTE")
    ly -= 13
    c.setFont(M.TXT, 6.5)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.drawString(lx, ly, "medida desde el borde de referencia")
    ly -= 12
    for k in h.cortes:
        if ly < MG + 10:
            c.setFillColorRGB(0.45, 0.45, 0.45)
            c.setFont(M.TXT, 6.5)
            c.drawString(lx, ly, "…continúa")
            break
        _et, _n, rgb = ETAPA.get(k.etapa, ("", "", (0, 0, 0)))
        c.setFillColorRGB(*rgb)
        c.circle(lx + 4, ly + 2.2, 4.4, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(M.TXT_B, 5.2)
        c.drawCentredString(lx + 4, ly + 0.5, str(k.n))
        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.setFont(M.TXT_B, 7)
        eje = "largo" if k.eje == "y" else "cruz"
        c.drawString(lx + 12, ly, f"{eje} {k.pos:.0f}")
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont(M.TXT, 6.3)
        c.drawString(lx + 52, ly, k.nota[:34])
        ly -= 10
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont(M.TXT, 7)
    c.drawString(MG, MG - 4,
                 "Corte de lado a lado · rojo: saca tiras · azul: trocea · "
                 "ocre: despunte · medidas en mm")
    c.setFillColorRGB(0, 0, 0)
    c.showPage()
