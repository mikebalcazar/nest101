"""#094 — La única parte del programa que sabe de PDF por dentro.

Mike: *«cambia a pypdfium2 … empecemos a mover todo al pypdfium2»*.

## Por qué se cambió

PyMuPDF es **AGPL 3.0 o licencia comercial de Artifex**. La AGPL pide que quien
reciba el programa pueda recibir el código fuente de **todo** el programa, no
sólo el de la librería, y entregarle el instalador a un taller cliente cuenta
como entrega. nest101 se va a vender, así que no puede viajar dentro.

pdfium es el motor de PDF de Chrome. Su licencia es **BSD 3-Clause**, y
`pypdfium2` —el envoltorio de Python— es **Apache 2.0 o BSD**. Es el mismo
cambio que ya hizo draw101.

## Por qué existe este archivo y no un buscar-y-reemplazar

Las dos librerías no se parecen:

- **pdfium mide desde ABAJO.** El eje Y crece hacia arriba, como en el PDF de
  verdad. PyMuPDF mide desde arriba, como una pantalla. Todo el lector está
  escrito en coordenadas de pantalla —«el dibujo está ARRIBA del rótulo» es una
  comparación de `y`—, así que si se cambia el origen sin darse cuenta, el
  detector sigue corriendo, no truena, y encuentra las vistas al revés.
- **pdfium no arma renglones.** Da caracteres sueltos con su caja, su tamaño y
  su ángulo. Los *spans* de PyMuPDF —un pedazo de texto con un solo estilo— hay
  que rearmarlos.
- **Y lo que más caro habría salido:** un objeto dentro de un *Form XObject*
  contesta sus coordenadas **en el espacio de la forma, no en el de la hoja**.
  Un plano exportado de Revit o de AutoCAD está lleno de Form XObjects. Medido:
  una caja que PyMuPDF sitúa en (200, 220)-(300, 300) la contesta pdfium como
  (0, 0)-(50, 40), porque el `Do` que la dibuja lleva un `cm` de 2× y +200. Sin
  acumular esa matriz, el lector encontraría toda la tinta amontonada cerca del
  origen — y otra vez sin tronar. Aquí se acumula la cadena de matrices de los
  contenedores; `dibujos()` devuelve coordenadas de hoja, como antes.

Así que el cambio queda **en un solo archivo**, y `sheet.py`, `geometria.py` e
`imaging.py` conservan su lógica intacta. Eso importa porque el lector de planos
es justo la parte que todavía no se ha probado de punta a punta con una llamada
real al modelo: cambiar el motor y la lógica a la vez dejaría dos cosas que ya
no se pueden revisar por separado.

`pruebas/t024_pdfium.py` compara las dos librerías sobre la misma lámina y exige
que contesten lo mismo.
"""
from __future__ import annotations

import ctypes
import math
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple

import pypdfium2 as pdfium
import pypdfium2.raw as _c

# --------------------------------------------------------------------- Rect
#
# `pymupdf.Rect` traía media docena de comodidades que el lector usa en todas
# sus líneas. Se copian aquí las que se usan y ninguna más.


class Rect:
    """Un rectángulo en coordenadas de PANTALLA: y crece hacia abajo.

    Es el mismo convenio de PyMuPDF, y es el que da por hecho todo el lector.
    La conversión desde el eje de pdfium se hace al entrar, una sola vez.
    """

    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self, x0, y0=None, x1=None, y1=None):
        if y0 is None:                       # Rect(otro) o Rect((a,b,c,d))
            x0, y0, x1, y1 = tuple(x0)
        self.x0, self.y0 = float(x0), float(y0)
        self.x1, self.y1 = float(x1), float(y1)

    # -- lectura
    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def __iter__(self) -> Iterator[float]:
        return iter((self.x0, self.y0, self.x1, self.y1))

    def __getitem__(self, i):
        return (self.x0, self.y0, self.x1, self.y1)[i]

    def __len__(self):
        return 4

    def __repr__(self):
        return f"Rect({self.x0:.1f}, {self.y0:.1f}, {self.x1:.1f}, {self.y1:.1f})"

    def __eq__(self, otro):
        try:
            return tuple(self) == tuple(otro)
        except TypeError:
            return NotImplemented

    # -- operaciones
    def __and__(self, otro) -> "Rect":
        """Intersección. Vacía si no se tocan — nunca al revés."""
        o = Rect(otro)
        x0, y0 = max(self.x0, o.x0), max(self.y0, o.y0)
        x1, y1 = min(self.x1, o.x1), min(self.y1, o.y1)
        if x1 < x0 or y1 < y0:
            return Rect(0, 0, 0, 0)
        return Rect(x0, y0, x1, y1)

    def __or__(self, otro) -> "Rect":
        o = Rect(otro)
        return Rect(min(self.x0, o.x0), min(self.y0, o.y0),
                    max(self.x1, o.x1), max(self.y1, o.y1))

    def __ior__(self, otro) -> "Rect":
        return self | otro

    def __add__(self, d) -> "Rect":
        """`r + (-12, -12, 12, 12)` ensancha; es como se pide un respiro."""
        a, b, c, e = d
        return Rect(self.x0 + a, self.y0 + b, self.x1 + c, self.y1 + e)

    def intersects(self, otro) -> bool:
        o = Rect(otro)
        return not (self.x1 <= o.x0 or o.x1 <= self.x0
                    or self.y1 <= o.y0 or o.y1 <= self.y0)


class Punto:
    """Un punto, con `.x` y `.y`. `geometria.py` los lee así."""

    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)

    def __iter__(self):
        return iter((self.x, self.y))

    def __repr__(self):
        return f"Punto({self.x:.1f}, {self.y:.1f})"


# ------------------------------------------------------------------ matrices
def _por(m, n):
    """Compone dos matrices de PDF (a, b, c, d, e, f): primero `m`, luego `n`."""
    a1, b1, c1, d1, e1, f1 = m
    a2, b2, c2, d2, e2, f2 = n
    return (a1 * a2 + b1 * c2,
            a1 * b2 + b1 * d2,
            c1 * a2 + d1 * c2,
            c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2,
            e1 * b2 + f1 * d2 + f2)


def _aplicar(m, x, y) -> Tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _matriz_de(obj) -> Tuple[float, ...]:
    m = _c.FS_MATRIX()
    if not _c.FPDFPageObj_GetMatrix(obj, m):
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return (m.a, m.b, m.c, m.d, m.e, m.f)


def _matriz_acumulada(o) -> Tuple[float, ...]:
    """La matriz que lleva del espacio del objeto al de la HOJA.

    Un objeto dentro de un Form XObject vive en el espacio de la forma. Si la
    forma está dentro de otra, en el de la de más adentro. Se sube por la cadena
    de contenedores multiplicando: sin esto, la tinta de un plano de Revit se
    amontona junto al origen y el detector no encuentra ni una vista.
    """
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    padre = getattr(o, "container", None)
    while padre is not None:
        m = _por(m, _matriz_de(padre.raw))
        padre = getattr(padre, "container", None)
    return m


def _juntar_rectangulo(items):
    """Un camino cerrado de cuatro lados rectos vuelve a ser UN rectángulo.

    pdfium entrega cualquier camino como segmentos sueltos, así que un `re` del
    PDF llega convertido en cuatro líneas. PyMuPDF lo devuelve entero, como
    `("re", Rect, 1)`, y de eso depende `geometria.py`: su detector de
    verticales sólo mira los items `"l"`, así que con los segmentos sueltos
    empezaría a contar los cantos de cada rectángulo como si fueran costados de
    mueble. Cambiar el motor no puede cambiar lo que el lector ve.

    *(Que los lados de un rectángulo no cuenten como verticales es discutible —un
    costado dibujado como rectángulo es un costado— pero eso es una decisión
    sobre el lector, no sobre la librería, y se toma aparte.)*
    """
    if len(items) != 4 or any(it[0] != "l" for it in items):
        return items
    pts = [(it[1].x, it[1].y) for it in items] + [(items[-1][2].x, items[-1][2].y)]
    if abs(pts[0][0] - pts[-1][0]) > 0.01 or abs(pts[0][1] - pts[-1][1]) > 0.01:
        return items                       # no cierra
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        if abs(ax - bx) > 0.01 and abs(ay - by) > 0.01:
            return items                   # algún lado va en diagonal
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if len({round(x, 2) for x in xs}) != 2 or len({round(y, 2) for y in ys}) != 2:
        return items                       # cuatro lados pero no un rectángulo
    return [("re", Rect(min(xs), min(ys), max(xs), max(ys)), 1)]


# ------------------------------------------------------------------- página
class Pagina:
    """Una hoja del plano, en coordenadas de pantalla."""

    def __init__(self, pg: "pdfium.PdfPage"):
        self._pg = pg
        self._alto = pg.get_height()
        self._tp = None

    # -- lo básico
    @property
    def rect(self) -> Rect:
        return Rect(0, 0, self._pg.get_width(), self._alto)

    @property
    def rotation(self) -> int:
        # pdfium cuenta en cuartos de vuelta; el lector habla en grados.
        return (self._pg.get_rotation() or 0) % 360

    def set_rotation(self, grados: int) -> None:
        self._pg.set_rotation(grados % 360)
        self._alto = self._pg.get_height()
        self._tp = None

    def _y(self, y: float) -> float:
        """Del eje de pdfium (desde abajo) al de pantalla (desde arriba)."""
        return self._alto - y

    def _textpage(self):
        if self._tp is None:
            self._tp = self._pg.get_textpage()
        return self._tp

    # -- texto
    def _letras(self):
        """Cada carácter con su caja de pantalla, su centro y su tamaño.

        Se usa `FPDFText_GetLooseCharBox` y no la caja ajustada: la ajustada
        envuelve el trazo del glifo —una «o» de 13 pt mide 9.8 de alto— mientras
        que PyMuPDF devuelve la caja de la FUENTE, con su ascendente y su
        descendente. Sobre la misma hoja, la ajustada queda 4 pt más baja y 1 pt
        más estrecha que la que el lector viene midiendo desde que se escribió.
        """
        tp = self._textpage()
        n = _c.FPDFText_CountChars(tp.raw)
        caja = _c.FS_RECTF()
        for i in range(max(0, n)):
            cod = _c.FPDFText_GetUnicode(tp.raw, i)
            if cod in (0, 10, 13):              # sin mapear, o salto de línea
                yield None
                continue
            if not _c.FPDFText_GetLooseCharBox(tp.raw, i, caja):
                yield None
                continue
            x0, x1 = min(caja.left, caja.right), max(caja.left, caja.right)
            y0 = self._y(max(caja.top, caja.bottom))
            y1 = self._y(min(caja.top, caja.bottom))
            if x1 <= x0 and y1 <= y0:           # caja degenerada: no estorba
                yield None
                continue
            yield (chr(cod), Rect(x0, y0, x1, y1), ((x0 + x1) / 2, (y0 + y1) / 2),
                   float(_c.FPDFText_GetFontSize(tp.raw, i)))

    def spans(self, corte_hueco: float = 0.7
              ) -> List[Tuple[Rect, str, float, Tuple[float, float]]]:
        """Los renglones de texto, rearmados de los caracteres sueltos.

        Devuelve `(caja, texto, tamaño, dirección)` — la forma que el lector ya
        esperaba. La dirección va en coordenadas de pantalla, como en PyMuPDF:
        el texto que corre hacia abajo es `(0, 1)` y el que corre hacia arriba
        `(0, -1)`.

        **La dirección se saca de la geometría, no de `FPDFText_GetCharAngle`.**
        Ese ángulo no es de fiar: en una lámina girada contesta 270° mientras
        sus propias cajas de carácter avanzan hacia arriba, o sea 90°. Con el
        ángulo, `_giro_de_lamina` votaba al revés y los recortes salían de
        cabeza. Lo que sí es cierto es hacia dónde van los caracteres uno tras
        otro, y eso es justo lo que significa el `dir` de PyMuPDF.

        Un renglón se corta cuando cambia el tamaño de letra, cuando hay un
        salto de línea, cuando el salto entre centros pasa de `1 + corte_hueco`
        veces el tamaño —una letra avanza como 0.6 em y un espacio suma 0.3
        más—, o cuando el texto tuerce.
        """
        out: List[Tuple[Rect, str, float, Tuple[float, float]]] = []
        letras: List[str] = []
        caja: Optional[Rect] = None
        tam = 0.0
        centro: Optional[Tuple[float, float]] = None
        rumbo: Optional[Tuple[float, float]] = None   # a dónde va este renglón

        def cerrar():
            nonlocal letras, caja, centro, rumbo
            if caja is not None and "".join(letras).strip():
                # Se ajusta a los cuatro ejes: el texto de un plano de CAD va
                # derecho, y quien lo lee sólo compara |dx| contra |dy| y signos.
                rx, ry = rumbo or (1.0, 0.0)
                d = ((1.0 if rx >= 0 else -1.0, 0.0) if abs(rx) >= abs(ry)
                     else (0.0, 1.0 if ry >= 0 else -1.0))
                out.append((caja, "".join(letras), tam, d))
            letras, caja, centro, rumbo = [], None, None, None

        for dato in self._letras():
            if dato is None:
                cerrar()
                continue
            ch, r, c, s = dato
            em = max(s, 1.0)

            nuevo = caja is None or abs(s - tam) > 0.51
            if not nuevo and centro is not None:
                vx, vy = c[0] - centro[0], c[1] - centro[1]
                largo = math.hypot(vx, vy)
                if largo > (1.0 + corte_hueco) * em:
                    nuevo = True                  # ya no es un espacio: es otro rótulo
                elif rumbo is not None and largo > 0.01:
                    ux, uy = vx / largo, vy / largo
                    # Sigue el mismo renglón si avanza en el mismo sentido y no
                    # se desvía: `·` cerca de 1, `×` cerca de 0.
                    if ux * rumbo[0] + uy * rumbo[1] < 0.85:
                        nuevo = True
            if nuevo:
                cerrar()
                tam = s
            elif centro is not None:
                vx, vy = c[0] - centro[0], c[1] - centro[1]
                largo = math.hypot(vx, vy)
                if rumbo is None and largo > 0.01:
                    rumbo = (vx / largo, vy / largo)
            letras.append(ch)
            caja = r if caja is None else (caja | r)
            centro = c
        cerrar()
        return out

    def texto(self) -> str:
        """El texto de la página, en renglones, como lo daba `page.get_text()`.

        Lo usan las pruebas que comprueban lo que sale impreso: el orden de las
        páginas del plano, el sello de «mueble 1 de 3», la secuencia de corte.
        Los saltos vienen como `\\r\\n` de pdfium; se normalizan.
        """
        tp = self._textpage()
        n = _c.FPDFText_CountChars(tp.raw)
        if n <= 0:
            return ""
        return tp.get_text_range(0, n).replace("\r\n", "\n").replace("\r", "\n")

    # -- tinta
    def dibujos(self) -> List[dict]:
        """Los trazos vectoriales, en coordenadas de hoja.

        Cada uno: `{"rect", "items", "width", "dashes"}`. En `items` van los
        segmentos rectos como `("l", Punto, Punto)` — que es lo único que
        `geometria.py` mira— y las curvas como `("c", ...)`, sin desarrollar.

        La caja se calcula de los puntos ya transformados y **no** con
        `FPDFPageObj_GetBounds`: ése añade el medio grosor del trazo, así que un
        marco de 0.7 pt contestaría 0.35 pt más grande por cada lado que el
        mismo marco leído con PyMuPDF. Sobre una hoja llena de líneas de cota
        esa diferencia mueve los recortes.
        """
        out = []
        for o in self._pg.get_objects(filter=(_c.FPDF_PAGEOBJ_PATH,)):
            m = _por(_matriz_de(o.raw), _matriz_acumulada(o))
            n = _c.FPDFPath_CountSegments(o.raw)
            if n <= 0:
                continue
            pts: List[Tuple[float, float, int]] = []
            cx, cy = ctypes.c_float(), ctypes.c_float()
            for i in range(n):
                seg = _c.FPDFPath_GetPathSegment(o.raw, i)
                if not seg:
                    continue
                _c.FPDFPathSegment_GetPoint(seg, cx, cy)
                px, py = _aplicar(m, cx.value, cy.value)
                pts.append((px, self._y(py), _c.FPDFPathSegment_GetType(seg)))
            if not pts:
                continue

            items = []
            prev: Optional[Tuple[float, float]] = None
            for px, py, tipo in pts:
                if tipo == _c.FPDF_SEGMENT_MOVETO:
                    prev = (px, py)
                    continue
                if prev is not None:
                    clase = "l" if tipo == _c.FPDF_SEGMENT_LINETO else "c"
                    items.append((clase, Punto(*prev), Punto(px, py)))
                prev = (px, py)
            items = _juntar_rectangulo(items)

            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            w = ctypes.c_float()
            _c.FPDFPageObj_GetStrokeWidth(o.raw, w)
            # El grosor también se escala con la matriz: una línea de 1 pt
            # dentro de una forma al 2× se dibuja de 2 pt.
            esc = math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) or 1.0
            nd = _c.FPDFPageObj_GetDashCount(o.raw)
            out.append({
                "rect": Rect(min(xs), min(ys), max(xs), max(ys)),
                "items": items,
                "width": float(w.value) * esc,
                "dashes": "[] 0" if nd <= 0 else f"[{nd} guiones]",
            })
        return out

    # -- raster
    def imagen(self, zoom: float = 1.0, giro: int = 0,
               recorte: Optional[Rect] = None):
        """Rasteriza la página (o un recuadro) y devuelve un `PIL.Image`.

        `giro` son los grados que hay que girar el resultado, en el mismo
        sentido que pedía el lector. `recorte` va en coordenadas de pantalla.
        """
        g = (-int(giro)) % 360
        if g % 90:
            raise ValueError(f"el giro tiene que ser múltiplo de 90: {giro}")

        crop = (0, 0, 0, 0)
        if recorte is not None:
            r = Rect(recorte) & self.rect
            # pdfium recorta con MÁRGENES desde cada borde —izquierda, abajo,
            # derecha, arriba—, y los mide **en la imagen ya girada**. Así que
            # los márgenes de la hoja hay que girarlos con ella: al girar 90° el
            # borde de abajo de la hoja pasa a ser el de la izquierda de la
            # imagen. Sin esto el recorte sale de otro pedazo de la hoja —medido:
            # 1716×498 px donde tocaban 1200×1014— y el modelo recibe media
            # vista sin que nada avise.
            m = [max(0.0, r.x0),                              # izquierda
                 max(0.0, self._alto - r.y1),                 # abajo
                 max(0.0, self._pg.get_width() - r.x1),       # derecha
                 max(0.0, r.y0)]                              # arriba
            k = g // 90
            crop = tuple(m[(i + k) % 4] for i in range(4))
        mapa = self._pg.render(scale=zoom, rotation=g, crop=crop)
        return mapa.to_pil()

    def guardar_imagen(self, destino: Path, zoom: float = 1.0, giro: int = 0,
                       recorte: Optional[Rect] = None) -> Path:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        self.imagen(zoom=zoom, giro=giro, recorte=recorte).save(destino)
        return destino

    def close(self):
        if self._tp is not None:
            self._tp.close()
            self._tp = None


# ---------------------------------------------------------------- documento
class Documento:
    """Un PDF abierto. Se recorre como una lista de páginas."""

    def __init__(self, ruta: Path):
        self._doc = pdfium.PdfDocument(str(ruta))
        self._pgs: List[Optional[Pagina]] = [None] * len(self._doc)

    def __len__(self) -> int:
        return len(self._pgs)

    def __getitem__(self, i: int) -> Pagina:
        if self._pgs[i] is None:
            self._pgs[i] = Pagina(self._doc[i])
        return self._pgs[i]

    def __iter__(self) -> Iterator[Pagina]:
        for i in range(len(self)):
            yield self[i]

    def close(self):
        for p in self._pgs:
            if p is not None:
                p.close()
        self._doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        self.close()
        return False


def abrir(pdf) -> Documento:
    return Documento(Path(pdf))
