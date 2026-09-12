"""Identidad Taller 101 — un solo lugar para el nombre, el color y la tipografía.

Si alguien cambia la marca, se cambia aquí y no en ocho archivos.

Nota sobre el naranja: NO es color de marca. Marca el cubrecanto en las fichas de
corte y en los planos, donde tiene que distinguirse del azul a simple vista y en
fotocopia. Por eso sobrevivió al cambio de identidad.
"""
import os

# --------------------------------------------------------------- nombre
#
# #079 — Son DOS nombres y no hay que confundirlos:
#
#   APP     = «nest101», el programa. Ventana, instalador, arranque y —desde
#             #081, por decisión de Mike— también el encabezado de los planos
#             y las fichas.
#   NOMBRE  = «Taller 101», el taller. Sigue siendo el dueño de los datos: la
#             carpeta de trabajo, el catálogo y la llave. Ya no firma el papel.
#
# #081 — El programa se llamaba t101xylo hasta la 0.15.2. El nombre nuevo va en
# la misma línea que draw101, el CAD: la familia se nombra <qué hace>101.
#
# La extensión `.t101x` y la carpeta `~/Taller 101` NO cambian: ahí viven los
# proyectos, el catálogo y la llave de un taller que ya está trabajando.
APP = "nest101"
NOMBRE = "Taller 101"
DESCRIPCION = "Despiece de gabinetes para corte CNC"
EXTENSION = ".t101x"

# --------------------------------------------------------------- color
HEX_AZUL = "#0080C1"
AZUL = (0.000, 0.502, 0.757)        # #0080C1 — color de marca
AZUL_CLARO = (0.227, 0.639, 0.863)  # #3AA3DC
TINTA = (0.10, 0.11, 0.13)
GRIS = (0.45, 0.46, 0.49)
LINEA = (0.85, 0.85, 0.87)
CANTO = (0.784, 0.506, 0.227)       # naranja funcional del cubrecanto

# --------------------------------------------------------------- tipografía
# Se registran al importar. Si faltan los TTF (empaquetado incompleto), los
# nombres se quedan en las fuentes base de PDF: el documento sale, sin marca.
TXT = "Helvetica"
TXT_B = "Helvetica-Bold"
TXT_I = "Helvetica-Oblique"
TIT = "Helvetica-Bold"
TIT_R = "Helvetica"

# #095 — Las CIFRAS, aparte. Norma de la suite: toda medida, cantidad, precio,
# fecha u hora se compone en **Fira Sans**, cifras alineadas. Raleway las trae
# «old style» —medido sobre el archivo: el 3, 4, 5, 7 y 9 caen hasta 154
# unidades bajo la línea base y el 6 y el 8 suben 140— y en una cota de corte
# eso no se lee de un golpe. Quién las reparte: `core/cifras.py`.
CIF = "Helvetica"
CIF_B = "Helvetica-Bold"

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = os.path.join(RAIZ, "assets", "fonts")
tipografia_propia = False
cifras_propias = False


# --------------------------------------------------------------- logotipo
#
# #083 — El logotipo del PAPEL es el de la empresa que usa el programa, no el
# del programa. nest101 se instala en talleres que no son Taller 101, y un plano
# que llega a la obra tiene que decir quién lo hizo.
#
# Por eso hay dos:
#
#   logo_app()      nest101. Viaja con la instalación, no se puede borrar, y es
#                   lo que se ve en la ventana y en el arranque.
#   logo()          el de la empresa, si lo puso; si no, el de nest101. Es el
#                   que va en planos y fichas.
#
# El de la empresa vive en la **carpeta de trabajo del taller**, junto al perfil
# y al catálogo — NO en la carpeta de instalación. Una actualización borra y
# reescribe la carpeta de instalación; la de trabajo no se toca. Si el logo
# viviera del otro lado, cada actualización se lo borraría al taller.
LOGO_EMPRESA = "logo-empresa"          # sin extensión: se guarda la que traiga
FORMATOS = (".png", ".jpg", ".jpeg")


def _carpeta_taller():
    """La carpeta de trabajo. Se pide en el momento, no al importar: en las
    pruebas cambia con T101_PERFIL_DIR y un valor cacheado se quedaría viejo."""
    from .taller import carpeta
    return carpeta()


def logo_empresa():
    """El logotipo que puso el taller, o None si no ha puesto ninguno."""
    try:
        base = _carpeta_taller()
    except Exception:
        return None
    for ext in FORMATOS:
        ruta = os.path.join(str(base), LOGO_EMPRESA + ext)
        if os.path.isfile(ruta):
            return ruta
    return None


def logo_app():
    """El logotipo de nest101, el que viaja con la instalación."""
    carpeta = os.path.join(RAIZ, "assets", "marca")
    for nombre in ("logo.png", "logo.jpg", "logo.jpeg"):
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta):
            return ruta
    return None


def logo():
    """El logotipo que firma el papel: el de la empresa, y si no el de nest101.

    Si no hubiera ninguno de los dos devuelve None y todo cae al nombre escrito
    en Sansation — la app nunca depende de un archivo de imagen.
    """
    return logo_empresa() or logo_app()


ANCHO_MAX = 2000        # px; más que esto sólo engorda los PDF
PESO_MAX = 8 * 1024 * 1024


def guardar_logo(datos: bytes, nombre: str = "") -> str:
    """Guarda el logotipo de la empresa en la carpeta de trabajo del taller.

    Se **reescribe con Pillow** en vez de copiar el archivo tal cual, y hay tres
    razones:

    1. Comprobar que de verdad es una imagen. Lo que llega es un archivo que
       eligió una persona; si no abre, más vale decirlo aquí y no cuando esté
       exportando cincuenta planos.
    2. Bajarlo a `ANCHO_MAX`. Un logotipo de 6000 px va incrustado en cada PDF
       y no se ve mejor: pesa.
    3. Dejarlo siempre en PNG con transparencia. El encabezado va sobre papel
       blanco, y un JPG con fondo blanco quemado deja un recuadro visible.

    Se borran antes las otras extensiones: si quedaran un .png y un .jpg, cuál
    gana dependería del orden de la lista, que es la clase de detalle que se
    convierte en un error raro seis meses después.
    """
    if not datos:
        raise ValueError("el archivo llegó vacío")
    if len(datos) > PESO_MAX:
        raise ValueError(f"la imagen pesa {len(datos)//1024//1024} MB; el máximo son 8")
    import io
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(datos))
        im.load()
    except Exception:
        raise ValueError(f"«{nombre or 'el archivo'}» no es una imagen que se pueda leer")
    im = im.convert("RGBA")
    if im.width > ANCHO_MAX:
        im = im.resize((ANCHO_MAX, max(1, round(im.height * ANCHO_MAX / im.width))),
                       Image.LANCZOS)
    base = _carpeta_taller()
    os.makedirs(str(base), exist_ok=True)
    quitar_logo()
    destino = os.path.join(str(base), LOGO_EMPRESA + ".png")
    im.save(destino, "PNG")
    return destino


def quitar_logo() -> bool:
    """Borra el logotipo de la empresa. Vuelve a firmarse con el de nest101."""
    base = _carpeta_taller()
    habia = False
    for ext in FORMATOS:
        ruta = os.path.join(str(base), LOGO_EMPRESA + ext)
        if os.path.isfile(ruta):
            os.remove(ruta)
            habia = True
    return habia


def dibujar(c, x, y, alto=11):
    """Pinta la marca en un PDF y devuelve el ancho que ocupó.

    Con logotipo: la imagen a la altura pedida, respetando su proporción.
    Sin logotipo: el nombre en Sansation, azul de marca.
    """
    ruta = logo()
    if ruta:
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(ruta)
            iw, ih = img.getSize()
            ancho = alto * iw / max(ih, 1)
            c.drawImage(img, x, y - alto * 0.22, width=ancho, height=alto,
                        mask="auto", preserveAspectRatio=True, anchor="sw")
            return ancho
        except Exception:
            pass                            # imagen ilegible: se escribe el nombre
    # #081 — El texto de respaldo dice lo mismo que el logotipo. Desde que
    # nest101 va también en planos y fichas, el logotipo del encabezado es
    # nest101; si aquí siguiera diciendo TALLER 101, el mismo plano saldría
    # firmado de dos maneras según si el archivo del logo está o no.
    texto = APP
    c.setFillColorRGB(*AZUL)
    c.setFont(TIT, alto * 1.18)
    c.drawString(x, y, texto)
    return c.stringWidth(texto, TIT, alto * 1.18)


def _registrar():
    """Registra Raleway (texto), Sansation (títulos) y Fira Sans (cifras)."""
    global TXT, TXT_B, TXT_I, TIT, TIT_R, CIF, CIF_B
    global tipografia_propia, cifras_propias
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        archivos = {
            "Raleway": "Raleway-400.ttf",
            "Raleway-Bold": "Raleway-700.ttf",
            "Raleway-Semi": "Raleway-600.ttf",
            "Raleway-Italic": "Raleway-400i.ttf",
            "Sansation": "Sansation-400.ttf",
            "Sansation-Bold": "Sansation-700.ttf",
        }
        for nombre, archivo in archivos.items():
            ruta = os.path.join(FUENTES, archivo)
            if not os.path.isfile(ruta):
                return                      # incompletas: mejor ninguna que a medias
            pdfmetrics.registerFont(TTFont(nombre, ruta))
        pdfmetrics.registerFontFamily("Raleway", normal="Raleway", bold="Raleway-Bold",
                                      italic="Raleway-Italic", boldItalic="Raleway-Bold")
        TXT, TXT_B, TXT_I = "Raleway", "Raleway-Bold", "Raleway-Italic"
        TIT, TIT_R = "Sansation-Bold", "Sansation"
        tipografia_propia = True

        # #095 — Fira Sans va aparte y en su propio `try`: si faltaran sus dos
        # archivos, el papel sale con las cifras de Raleway —feo pero legible—
        # en vez de no salir. El texto no depende de las cifras.
        cif = {"Cifras": "FiraSans-400.ttf", "Cifras-Semi": "FiraSans-600.ttf"}
        for nombre, archivo in cif.items():
            ruta = os.path.join(FUENTES, archivo)
            if not os.path.isfile(ruta):
                return
            pdfmetrics.registerFont(TTFont(nombre, ruta))
        CIF, CIF_B = "Cifras", "Cifras-Semi"
        cifras_propias = True
    except Exception:
        pass                                # sin tipografía propia se sigue exportando


_registrar()
