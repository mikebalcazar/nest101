"""Analisis de LAMINA (sheet) vectorial: encuentra las vistas dentro de un plano grande.

Los planos reales (Revit/AutoCAD, formato A0/A1) traen varias vistas chiquitas
regadas en la hoja: plantas, elevaciones, axonometricos, cortes. Mandarle la hoja
completa al modelo de vision es tirar el dinero: el dibujo ocupa <5% de los pixeles.

Este modulo:
  1. localiza los rotulos de vista ("05  ELEVACION 01 - BARRA LACTANCIA 02")
  2. deduce el recuadro de dibujo que le corresponde a cada rotulo
  3. clasifica el tipo de vista y lee su escala
  4. recorta y rasteriza cada vista a la resolucion que necesita el modelo
  5. entrega el texto nativo del PDF (cotas, claves) con coordenadas: cero OCR
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from . import pdf as P

PT_A_MM = 25.4 / 72.0

TIPOS = [
    ("elevacion", re.compile(r"ELEVACI[OÓ]N|ALZADO", re.I)),
    ("corte", re.compile(r"\bCORTE\b|SECCI[OÓ]N", re.I)),
    ("planta", re.compile(r"\bPLANTA\b", re.I)),
    ("axonometrico", re.compile(r"AXONOM[EÉ]TRIC|ISOM[EÉ]TRIC|3D", re.I)),
    ("detalle", re.compile(r"\bDETALLE\b", re.I)),
]
RE_ESCALA = re.compile(r"1\s*[:/]\s*(\d+)")
# rotulos que NO son vistas (pie de plano, membrete)
RE_RUIDO = re.compile(r"NOTAS|LOCALIZACI|MAPA|PROYECTO|ESCALA/|SELLO|Gensler|©", re.I)


@dataclass
class Vista:
    numero: Optional[str]
    titulo: str
    tipo: str
    escala: Optional[int]                 # denominador: 25 => 1:25
    rect: P.Rect                    # recuadro del dibujo en pt de pagina
    rect_rotulo: P.Rect
    textos: List[Tuple[Tuple[float, float, float, float], str]] = field(default_factory=list)
    zoom: float = 1.0                     # px del recorte por pt de hoja
    giro: int = 0                         # #051: cuanto hay que girar el recorte
    caja_lectura: object = None           # #054: la caja en el marco de lectura
    rotulo_id: int = 0                    # #054: a que rotulo pertenece

    @property
    def mm_por_pt(self) -> Optional[float]:
        """Cuantos mm reales mide 1 pt de la hoja, dada la escala de la vista."""
        return self.escala * PT_A_MM if self.escala else None

    def id(self) -> str:
        base = (self.numero or "V") + "-" + re.sub(r"[^A-Z0-9]+", "_", self.titulo.upper())[:28]
        return base.strip("_")


def _clasificar(t: str) -> Optional[str]:
    for nombre, rx in TIPOS:
        if rx.search(t):
            return nombre
    return None


# --------------------------------------------------------------------- #051
#
# El eje de lectura de la lamina.
#
# Un plano de CAD se exporta muchas veces con TODO el texto girado 90 grados:
# la hoja se imprime apaisada, pero el PDF guarda las letras corriendo hacia
# abajo. Le paso a Mike con `CAR-06 - CARPINTERIAS - MUEBLE PANTRY.pdf`: las
# seis vistas venian perfectamente rotuladas —«MUEBLE PANTRY - ALZADO»,
# «- SECCION 01», «- DETALLE 02»— y el programa entrego CERO, porque el
# detector solo miraba spans con direccion (1, 0).
#
# En vez de repetir la geometria del detector para cada giro, se giran las
# COORDENADAS: se lleva todo al marco en que el texto corre horizontal, se
# corre ahi el mismo algoritmo de siempre, y al final se regresan los recuadros
# a la hoja. Una sola idea, y el detector no se entera.


class Marco:
    """Convierte entre las coordenadas de la hoja y las de lectura.

    `giro` son los grados que hay que girar la hoja para poder leerla:
    0 ya se lee, 90 significa que el texto corre hacia abajo.
    """

    def __init__(self, giro: int = 0, hoja: Optional[P.Rect] = None):
        self.giro = giro % 360
        # Girar deja coordenadas negativas, y el detector da por hecho que el
        # borde de arriba es y=0 (arranca los techos ahi). Asi que despues de
        # girar se traslada la hoja al origen: el marco de lectura se parece a
        # una hoja normal, y el algoritmo no tiene que enterarse de nada.
        self.dx = self.dy = 0.0
        if hoja is not None:
            xs, ys = [], []
            for x, y in ((hoja.x0, hoja.y0), (hoja.x1, hoja.y0),
                         (hoja.x0, hoja.y1), (hoja.x1, hoja.y1)):
                gx, gy = self._gira(x, y)
                xs.append(gx); ys.append(gy)
            self.dx, self.dy = -min(xs), -min(ys)

    def _gira(self, x: float, y: float) -> Tuple[float, float]:
        if self.giro == 90:                 # texto hacia abajo:  (x,y) -> (y,-x)
            return (y, -x)
        if self.giro == 180:
            return (-x, -y)
        if self.giro == 270:                # texto hacia arriba: (x,y) -> (-y,x)
            return (-y, x)
        return (x, y)

    def _desgira(self, x: float, y: float) -> Tuple[float, float]:
        if self.giro == 90:
            return (-y, x)
        if self.giro == 180:
            return (-x, -y)
        if self.giro == 270:
            return (y, -x)
        return (x, y)

    def pt(self, x: float, y: float) -> Tuple[float, float]:
        gx, gy = self._gira(x, y)
        return (gx + self.dx, gy + self.dy)

    def inv_pt(self, x: float, y: float) -> Tuple[float, float]:
        return self._desgira(x - self.dx, y - self.dy)

    def _caja(self, r, f) -> P.Rect:
        a = f(r[0], r[1])
        b = f(r[2], r[3])
        return P.Rect(min(a[0], b[0]), min(a[1], b[1]),
                            max(a[0], b[0]), max(a[1], b[1]))

    def rect(self, r) -> P.Rect:
        return self._caja(r, self.pt)

    def inv_rect(self, r) -> P.Rect:
        return self._caja(r, self.inv_pt)


def _giro_de_lamina(spans) -> int:
    """Hacia donde corre el texto de la hoja, por mayoria de spans."""
    votos = {0: 0, 90: 0, 270: 0, 180: 0}
    for rect, txt, size, d in spans:
        peso = max(1.0, size) * max(1, len(txt))
        dx, dy = (d or (1.0, 0.0))[:2]
        if abs(dx) >= abs(dy):
            votos[0 if dx >= 0 else 180] += peso
        else:
            votos[90 if dy >= 0 else 270] += peso
    return max(votos, key=lambda k: votos[k])


def _spans(page: P.Pagina):
    """Los renglones de la hoja: `(caja, texto, tamaño, direccion)`.

    #094 — Los arma `motor/pdf.py` a partir de los caracteres sueltos, que es lo
    que da pdfium. Aqui se conserva la misma forma de siempre para que el resto
    del detector no se entere del cambio de libreria.
    """
    return [(r, t.strip(), s, d) for r, t, s, d in page.spans() if t.strip()]


def _ink_rects(page: P.Pagina) -> List[P.Rect]:
    return [d["rect"] for d in page.dibujos()]


def _limite_membrete(hoja: P.Rect, spans) -> float:
    """Borde izquierdo del membrete/pie de plano: todo lo que este a su derecha
    (logo, notas generales, sello, datos del proyecto) no es una vista."""
    x = hoja.x1
    ancho = hoja.x0 + (hoja.x1 - hoja.x0) * 0.65
    for rect, txt, size, _d in spans:
        if RE_RUIDO.search(txt) and rect.x0 > ancho:
            x = min(x, rect.x0 - 20)
    return x


def detectar_vistas(page: P.Pagina, min_size: float = 12.0,
                    holgura: float = 24.0) -> List[Vista]:
    """Encuentra las vistas de la lamina a partir de sus rotulos.

    #051 — Todo lo de aqui abajo trabaja en el MARCO DE LECTURA, no en el de la
    hoja: si el PDF trae el texto girado 90 grados —cosa comun al exportar de
    CAD— se giran las coordenadas al entrar y se regresan al salir. Asi la
    geometria del detector («el numero va a la izquierda del rotulo», «el dibujo
    esta arriba») se escribe una sola vez y vale para las cuatro orientaciones.
    """
    crudos = _spans(page)
    M = Marco(_giro_de_lamina(crudos), page.rect)
    spans = [(M.rect(r), t, s, (1.0, 0.0)) for r, t, s, _d in crudos]
    hoja = M.rect(page.rect)

    # 1. rotulos candidatos: texto grande, clasificable, no ruido de membrete
    rotulos = []
    for rect, txt, size, dirn in spans:
        if size < min_size:
            continue
        if RE_RUIDO.search(txt):
            continue
        tipo = _clasificar(txt)
        if tipo:
            rotulos.append((rect, txt, tipo))
    if not rotulos:
        return []

    # 2. numero de vista: span grande inmediatamente a la izquierda del rotulo
    def numero_de(rect: P.Rect) -> Optional[str]:
        cand = [(r, t) for r, t, s, d in spans
                if t.isdigit() and s >= min_size
                and r.x1 <= rect.x0 + 2 and rect.x0 - r.x1 < 80
                and abs((r.y0 + r.y1) / 2 - (rect.y0 + rect.y1) / 2) < 30]
        cand.sort(key=lambda rt: rect.x0 - rt[0].x1)
        return cand[0][1] if cand else None

    # 3. escala: texto "1 : 25" debajo del rotulo
    def escala_de(rect: P.Rect) -> Optional[int]:
        cand = [(r, t) for r, t, s, d in spans
                if RE_ESCALA.search(t) and r.y0 >= rect.y1 - 4 and r.y0 - rect.y1 < 40
                and r.x0 > rect.x0 - 200 and r.x0 < rect.x1 + 200]
        if not cand:
            return None
        cand.sort(key=lambda rt: rt[0].y0)
        m = RE_ESCALA.search(cand[0][1])
        return int(m.group(1)) if m else None

    # 4. recuadro del dibujo: la tinta que esta ARRIBA del rotulo, en su columna,
    #    hasta toparse con el rotulo anterior de la misma columna.
    ink = [M.rect(r) for r in _ink_rects(page)]
    rotulos.sort(key=lambda r: (round(r[0].x0 / 100), r[0].y0))

    # columnas de la lamina: se agrupan los rotulos por su x0 (tolerancia 40pt)
    xs = sorted({round(r.x0) for r, _t, _ti in rotulos})
    cols: List[float] = []
    for x in xs:
        if not cols or x - cols[-1] > 40:
            cols.append(x)
    MARGEN_IZQ = 130.0   # cabe el numero de vista y las cotas de la izquierda

    # #051 — El limite del membrete nunca se come un rotulo de vista.
    #
    # La regla original supone el membrete de Gensler: una columna a la derecha
    # de la hoja. El despacho de CAR-06 lo pone en una FRANJA ABAJO, y sus
    # textos («NOMBRE DEL PROYECTO», «SELLO Y FIRMA») caen en el tercio derecho
    # del eje de lectura. Con eso el limite se paraba en 1701 y se tragaba
    # «SECCION 02» y «DETALLE 01», que viven mas alla. Dos de las seis vistas.
    #
    # Si hay un rotulo de vista a la derecha del limite, el limite esta mal:
    # ahi no empieza el membrete, porque ahi todavia hay plano.
    lim_der = _limite_membrete(hoja, spans)
    tope_rotulos = max(r.x1 for r, _t, _ti in rotulos) + MARGEN_IZQ
    lim_der = max(lim_der, min(tope_rotulos, hoja.x1))

    def banda(x0: float) -> Tuple[float, float]:
        i = max(i for i, c in enumerate(cols) if x0 >= c - 40)
        izq = cols[i] - MARGEN_IZQ
        der = (cols[i + 1] - MARGEN_IZQ) if i + 1 < len(cols) else lim_der
        der = min(der, lim_der)
        return izq, max(der, izq + 60)      # una banda invertida no mira nada

    # #054 — El techo de una vista lo pone la vista de arriba, aunque su ROTULO
    # este en otra columna.
    #
    # La regla original miraba solo los rotulos: si ninguno caia en la banda, el
    # techo se quedaba en el borde de la hoja y el recorte se tragaba el dibujo
    # de la vista de encima. En `CAR-06` eso hacia que el ALZADO viniera con la
    # PLANTA pegada arriba — y el modelo, mirando dos vistas revueltas y con la
    # orden de no inventar, contestaba de menos.
    #
    # Se resuelve en dos pasadas: primero se calcula cada vista con la regla de
    # siempre, y despues se vuelve a cortar usando las cajas ya conocidas de las
    # demas como techo. Es barato y quita el traslape sin adivinar nada.
    def _armar(techos_extra: Optional[dict] = None) -> List[Vista]:
        salida: List[Vista] = []
        for rect, txt, tipo in rotulos:
            col_x0, col_x1 = banda(rect.x0)
            techo = 0.0
            for r2, t2, _ in rotulos:
                if r2 is rect:
                    continue
                if r2.y1 < rect.y0 and not (r2.x1 < col_x0 or r2.x0 > col_x1):
                    techo = max(techo, r2.y1 + 6)
            if techos_extra:
                for otra in techos_extra.get(id(rect), ()):
                    techo = max(techo, otra)
            piso = rect.y0 - 4

            dentro = [r for r in ink
                      if r.y0 >= techo and r.y1 <= piso
                      and r.x1 > col_x0 and r.x0 < col_x1
                      and r.width < 900 and r.height < 900]
            # texto de la vista (cotas, claves) en la misma ventana
            textos = [(tuple(r), t) for r, t, _s, _d in spans
                      if r.y0 >= techo and r.y1 <= piso
                      and r.x1 > col_x0 and r.x0 < col_x1]
            if not dentro:
                continue
            x0 = min(r.x0 for r in dentro); x1 = max(r.x1 for r in dentro)
            y0 = min(r.y0 for r in dentro); y1 = max(r.y1 for r in dentro)
            for (tx0, ty0, tx1, ty1), _t in textos:      # que quepan las cotas
                x0, y0 = min(x0, tx0), min(y0, ty0)
                x1, y1 = max(x1, tx1), max(y1, ty1)
            caja = P.Rect(x0 - holgura, y0 - holgura, x1 + holgura, y1 + holgura)
            caja = caja & hoja
            if caja.width < 30 or caja.height < 30:
                continue
            v = Vista(numero=numero_de(rect), titulo=txt, tipo=tipo,
                      escala=escala_de(rect), rect=caja, rect_rotulo=rect,
                      textos=textos, giro=M.giro)
            v.caja_lectura = caja            # se guarda para la segunda pasada
            v.rotulo_id = id(rect)
            salida.append(v)
        return salida

    primera = _armar()
    # segunda pasada: la caja de cada vista le pone techo a las de abajo
    extra: dict = {}
    for v in primera:
        for w in primera:
            if v is w:
                continue
            caja_v = v.caja_lectura
            rot_w = next(r for r, _t, _ti in rotulos if id(r) == w.rotulo_id)
            solapa = not (caja_v.x1 <= rot_w.x0 or caja_v.x0 >= rot_w.x1)
            if solapa and caja_v.y1 <= rot_w.y0:
                extra.setdefault(w.rotulo_id, []).append(caja_v.y1 + 6)
    vistas = _armar(extra) if extra else primera

    for v in vistas:                     # de vuelta a coordenadas de la hoja
        v.textos = [(tuple(M.inv_rect(r)), t) for r, t in v.textos]
        v.rect_rotulo = M.inv_rect(v.rect_rotulo)
        v.rect = M.inv_rect(v.rect)
    vistas.sort(key=lambda v: (v.numero or "99"))
    return vistas


def hoja_completa(page: P.Pagina) -> Vista:
    """#049 — La lamina entera tratada como UNA vista, cuando no hay rotulos.

    `detectar_vistas` encuentra las vistas por su rotulo («01 ELEVACION», «CORTE
    A-A»). Cuando un despacho rotula distinto —o no rotula— no encuentra nada, y
    hasta la 0.9.3 eso no daba error: daba **cero modulos** en una pantalla
    vacia, que parece que el plano estaba mal cuando el que no supo leer fue el
    programa.

    Asi que si no hay rotulos se manda la hoja completa, sin el membrete, que es
    exactamente lo que ya hacia el camino de las fotos. El modelo ve mas chico
    cada mueble, pero ve algo, y de ahi se puede corregir.
    """
    spans = _spans(page)
    limite = _limite_membrete(page.rect, spans)
    r = P.Rect(page.rect)
    r.x1 = min(r.x1, limite)
    # la tinta manda sobre el papel: un A1 con el dibujo en una esquina se
    # rasterizaria casi todo en blanco y el mueble saldria diminuto
    tinta = [d for d in _ink_rects(page) if d.x0 < limite]
    if tinta:
        caja = P.Rect(tinta[0])
        for d in tinta[1:]:
            caja |= d
        caja = caja + (-12, -12, 12, 12)          # un respiro alrededor
        caja = caja & r
        if caja.width > 40 and caja.height > 40:
            r = caja
    v = Vista(numero=None, titulo="HOJA COMPLETA", tipo="elevacion", escala=None,
              rect=r, rect_rotulo=P.Rect(0, 0, 0, 0),
              giro=_giro_de_lamina(spans))
    v.textos = [(tuple(rect), txt) for rect, txt, _s, _d in spans
                if P.Rect(rect).intersects(r)]
    return v


def recortar(page: P.Pagina, v: Vista, out_dir: Path, px_objetivo: int = 2000) -> Path:
    """Rasteriza SOLO el recuadro de la vista, escalando para que el lado mayor
    quede en ~px_objetivo (asi el modelo ve el dibujo grande, no la hoja vacia)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    lado = max(v.rect.width, v.rect.height)
    zoom = max(1.0, min(12.0, px_objetivo / lado))
    v.zoom = zoom
    # #051 — el recorte sale DERECHO. La lamina puede traer el texto girado 90
    # grados; si se manda asi, el modelo tiene que leer las cotas de lado y un
    # mueble vertical parece acostado. Se gira al rasterizar, sin pasar por otra
    # libreria ni volver a guardar el PNG.
    return page.guardar_imagen(out_dir / f"vista_{v.id()}.png",
                               zoom=zoom, giro=v.giro, recorte=v.rect)


def mm_por_px(v: Vista) -> Optional[float]:
    """Milimetros reales que mide 1 pixel del recorte. Solo si hay escala."""
    if not v.mm_por_pt:
        return None
    return v.mm_por_pt / v.zoom


def texto_de_vista(v: Vista) -> List[dict]:
    """Texto nativo del PDF dentro de la vista, en coordenadas relativas al recorte."""
    # #051 — las posiciones se dan en el marco del RECORTE YA GIRADO, que es la
    # imagen que el modelo tiene enfrente. Si se mandaran en coordenadas de la
    # hoja, en una lamina girada cada cota diria estar donde no esta, y el
    # modelo tendria que elegir entre lo que ve y lo que le decimos.
    M = Marco(v.giro, v.rect)
    out = []
    for (x0, y0, x1, y1), t in v.textos:
        r = M.rect((x0, y0, x1, y1))
        out.append({"texto": t,
                    "bbox_pt": [round(r.x0, 1), round(r.y0, 1),
                                round(r.x1, 1), round(r.y1, 1)]})
    return out


def abrir(pdf: Path) -> P.Documento:
    """Abre la lamina y **le quita el giro de pagina**.

    #051 — Una hoja de CAD suele venir con `/Rotate 270`: se dibuja vertical y
    se manda a imprimir apaisada. Con eso, `page.rect` contesta 2592x1728 —el
    tamano ya girado— mientras que el texto y la tinta siguen en 1728x2592. Dos
    sistemas de coordenadas a la vez, y todo lo que cruce de uno al otro sale
    mal: el recorte de la vista, el limite del membrete, el clip del pixmap.

    Fue la mitad del fallo de `CAR-06`. Se pone el giro en cero al abrir y de
    ahi en adelante hay UN solo sistema. No se pierde nada: hacia donde se lee
    la hoja se deduce del texto (`_giro_de_lamina`), que ademas es mas confiable
    que el `/Rotate` — hay laminas giradas sin declararlo.
    """
    doc = P.abrir(pdf)
    for page in doc:
        if page.rotation:
            page.set_rotation(0)
    return doc


def es_vectorial(page: P.Pagina, min_dibujos: int = 200) -> bool:
    """Distingue PDF nativo de CAD/Revit vs PDF que solo trae un escaneo."""
    return len(page.dibujos()) >= min_dibujos
