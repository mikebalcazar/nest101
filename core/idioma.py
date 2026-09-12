"""#085 — Idioma del papel: planos, fichas de corte y Excel.

Mike escogió que el idioma alcance **pantalla y papel**: *«un taller en inglés
entrega planos en inglés»*. Así que el mismo diccionario que traduce la
interfaz traduce los encabezados de los PDF y del Excel.

**La clave es el texto en español**, igual que en la interfaz (ver
`ui/idioma.js` para el porqué largo). Aquí eso además tiene una ventaja
concreta: `t("Lista de corte")` se lee en el código exportador sin tener que ir
a buscar qué dice la llave `pdf.titulo3`.

El idioma vive en el perfil del taller, no en el proyecto: es del taller, no de
la cocina. Y de fábrica es **inglés** — nest101 se instala fuera de México y el
que sí habla español lo cambia una vez.

Un texto que no esté en el diccionario sale en español. Eso es a propósito: un
encabezado en español es entendible; una llave sin resolver, no.
"""
from __future__ import annotations

import json
import re
import os
from typing import Dict, Optional

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, "assets", "idioma")

IDIOMAS = {"es": "Español", "en": "English"}
DE_FABRICA = "en"                      # #085 — la app arranca en inglés

_CACHE: Dict[str, Dict[str, str]] = {}
_ACTIVO: Optional[str] = None


def disponibles() -> Dict[str, str]:
    return dict(IDIOMAS)


def diccionario(codigo: str) -> Dict[str, str]:
    if codigo in _CACHE:
        return _CACHE[codigo]
    d: Dict[str, str] = {}
    ruta = os.path.join(CARPETA, f"{codigo}.json")
    if os.path.isfile(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                cargado = json.load(f)
            if isinstance(cargado, dict):
                d = {str(k): str(v) for k, v in cargado.items()}
        except Exception:
            # Un diccionario roto no puede tumbar una exportación: sale en
            # español y ya. El papel importa más que el idioma del papel.
            d = {}
    _CACHE[codigo] = d
    return d


def activo() -> str:
    """El idioma del taller. Se lee del perfil la primera vez que hace falta."""
    global _ACTIVO
    if _ACTIVO is None:
        try:
            from .taller import leer
            _ACTIVO = leer().get("idioma") or DE_FABRICA
        except Exception:
            _ACTIVO = DE_FABRICA
        if _ACTIVO not in IDIOMAS:
            _ACTIVO = DE_FABRICA
    return _ACTIVO


def poner(codigo: str) -> str:
    """Cambia el idioma en caliente. Lo llama el servidor al guardar el perfil."""
    global _ACTIVO
    _ACTIVO = codigo if codigo in IDIOMAS else DE_FABRICA
    return _ACTIVO


def olvidar() -> None:
    """Suelta el idioma cacheado para que se relea del perfil. Para las pruebas."""
    global _ACTIVO
    _ACTIVO = None


_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def t(texto: str, codigo: Optional[str] = None) -> str:
    """El texto en el idioma del taller. Sin traducción, sale en español.

    Además de la búsqueda exacta hay **una** regla, y es la que hace que esto
    sirva para lo que escribe el motor: los números se sacan y se vuelven a
    meter. «Frente de cajón 3» busca «Frente de cajón #» y devuelve «Drawer
    front 3»; «corredera 500 mm» busca «corredera # mm».

    Sin esa regla el diccionario tendría que traer una línea por cada número
    posible, o el motor tendría que hablar inglés — y el motor tiene que seguir
    hablando un solo idioma, que es lo que las pruebas asientan y lo que hace
    que un `.t101x` guardado en un taller abra igual en otro.
    """
    if texto is None:
        return texto
    cod = codigo or activo()
    if cod == "es":
        return texto
    dic = diccionario(cod)
    if texto in dic:
        return dic[texto]
    numeros = _NUM.findall(texto)
    if not numeros:
        return texto
    plantilla = _NUM.sub("#", texto)
    traducida = dic.get(plantilla)
    if traducida is None:
        return texto
    it = iter(numeros)
    return re.sub(r"#", lambda _m: next(it, "#"), traducida)


class LienzoTraducido:
    """Un lienzo de reportlab que traduce lo que se escribe en él.

    #085 — Los PDF se dibujan con decenas de `drawString` sueltos, sin un solo
    punto por donde pase todo el texto. Envolver el lienzo **crea** ese punto:
    cualquier texto que se escriba en un plano pasa por `t()` sin tener que ir
    a tocar cincuenta llamadas, y el que se escriba mañana también.

    Lo que no está en el diccionario sale igual, así que el nombre del cliente
    y el del proyecto pasan intactos: `t()` sólo cambia lo que reconoce.
    """

    def __init__(self, c):
        self._c = c

    def __getattr__(self, nombre):
        return getattr(self._c, nombre)

    # #095 — Y este mismo punto reparte las CIFRAS.
    #
    # Norma de la suite: toda medida, cantidad, precio o fecha va en Fira Sans,
    # que tiene cifras alineadas. Raleway las trae «old style» y en una cota de
    # corte no se leen de un golpe. En pantalla lo resuelve el `unicode-range`
    # del CSS; aquí no existe tal cosa, así que se parte el texto en tramos y
    # cada uno se escribe con la suya. Ver `core/cifras.py`.
    #
    # Va aquí por lo mismo que la traducción: es el único sitio por donde pasa
    # todo el texto de todos los PDF, incluido el que se escriba mañana.

    def _fuente(self):
        return (getattr(self._c, "_fontname", "Helvetica"),
                getattr(self._c, "_fontsize", 10))

    def drawString(self, x, y, texto, *a, **k):
        from .cifras import escribir
        f, tam = self._fuente()
        return escribir(self._c, x, y, t(texto), f, tam, "izq")

    def drawCentredString(self, x, y, texto, *a, **k):
        from .cifras import escribir
        f, tam = self._fuente()
        return escribir(self._c, x, y, t(texto), f, tam, "centro")

    def drawRightString(self, x, y, texto, *a, **k):
        from .cifras import escribir
        f, tam = self._fuente()
        return escribir(self._c, x, y, t(texto), f, tam, "der")

    def stringWidth(self, texto, *a, **k):
        # Se mide lo que se va a imprimir, no el original: si no, el texto en
        # inglés se sale de su columna o le sobra espacio. Y se mide con las DOS
        # fuentes: Fira y Raleway no tienen los mismos anchos, así que medir con
        # una sola deja el número fuera de su columna.
        from .cifras import ancho
        txt = t(texto)
        if a or k:                      # quien llama pidió una fuente concreta
            f = a[0] if a else k.get("fontName", self._fuente()[0])
            tam = a[1] if len(a) > 1 else k.get("fontSize", self._fuente()[1])
            return ancho(self._c, txt, f, tam)
        f, tam = self._fuente()
        return ancho(self._c, txt, f, tam)
